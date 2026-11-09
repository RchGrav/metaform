//! One launched ACP harness process and its sessions.
//!
//! Everything the agent does is published on the bus as it happens. Calls here never wait
//! for an agent's turn: [`Harness::prompt`] returns at once and the outcome arrives as a
//! [`PromptCompleted`] or [`PromptFailed`] event. A prompt is never cancelled unless
//! [`Harness::cancel`] is called; dropping a handle does not cancel anything.
//!
//! ACP version: [`Harness::launch`] offers v2 first. If the agent selects v1 or declines v2,
//! the process is ended and a fresh one is connected on v1. Each connection then speaks only
//! its negotiated version: on v1 the `session/prompt` response ends the turn; on v2 that
//! response only means the prompt was accepted, and the turn ends when the session reports
//! `idle` after having been active.

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};

use agent_client_protocol as acp;
use acp::schema::{MaybeUndefined, ProtocolVersion};
use acp::v1::schema as s1;
use acp::v2::schema as s2;
use acp::v2::InitializeOutcome;
use acp::{Agent, ByteStreams, Client, ErrorCode, SelectedInitializeResponse};
use anyhow::{Context, Result, anyhow, bail};
use bus::Bus;
use serde::Serialize;
use tokio::sync::oneshot;
use tokio_util::compat::{TokioAsyncReadCompatExt, TokioAsyncWriteCompatExt};

use crate::events::*;
use crate::launch::LaunchSpec;
use crate::permission::{PermissionAsk, PermissionPolicy, Verdict};
use crate::process::{self, Process};

static NEXT_PROMPT: AtomicU64 = AtomicU64::new(0);

/// The agent's `initialize` answer.
#[derive(Debug, Clone)]
pub struct AgentInit {
    /// The negotiated version, the same as [`Harness::protocol_version`].
    pub protocol_version: ProtocolVersion,
    pub response: InitResponse,
}

/// The `initialize` response, in the schema of the negotiated version.
#[derive(Debug, Clone)]
pub enum InitResponse {
    V1(s1::InitializeResponse),
    V2(s2::InitializeResponse),
}

/// A running harness. Cheap to clone; every clone refers to the same process.
#[derive(Clone)]
pub struct Harness {
    shared: Arc<Shared>,
    conn: Conn,
    init: Arc<AgentInit>,
    stop: Arc<Mutex<Option<oneshot::Sender<()>>>>,
}

#[derive(Clone)]
enum Conn {
    V1(acp::v1::ConnectionTo<Agent>),
    V2(acp::v2::ConnectionTo<Agent>),
}

struct Shared {
    id: HarnessId,
    bus: Bus,
    policy: Arc<dyn PermissionPolicy>,
    sessions: Mutex<HashMap<SessionId, Session>>,
}

#[derive(Default)]
struct Session {
    cwd: Option<PathBuf>,
    /// Opened or resumed on this connection and not closed.
    open: bool,
    /// The configuration options the agent advertised for this session, as last reported.
    options: Vec<Advertised>,
    turn: Turn,
    /// A v1 `session/load` is in progress: the updates arriving now replay history.
    replaying: bool,
}

struct Advertised {
    id: String,
    kind: OptionKind,
}

#[derive(Clone, PartialEq)]
enum OptionKind {
    Select,
    Boolean,
    Other(String),
}

/// The prompt turn in progress on one session.
#[derive(Default)]
struct Turn {
    prompt: Option<PromptId>,
    /// v2: the session reported a non-idle state since the prompt was sent, so the next
    /// `idle` ends this turn. An `idle` before that is a stale state, not this turn's end.
    active: bool,
    text: Transcript,
    thoughts: Transcript,
}

/// Agent text of one turn, as segments: on v1 a new segment starts after each tool call;
/// on v2 each message id is a segment.
#[derive(Default)]
struct Transcript {
    segments: Vec<(Option<String>, String)>,
    split: bool,
}

/// How a v2 snapshot changed a message, for publishing.
enum Patch {
    Append(String),
    Replace(String),
}

impl Transcript {
    fn append(&mut self, message: Option<&str>, text: &str) {
        match message {
            None => {
                if self.split || self.segments.is_empty() {
                    self.segments.push((None, String::new()));
                    self.split = false;
                }
                if let Some((_, segment)) = self.segments.last_mut() {
                    segment.push_str(text);
                }
            }
            Some(id) => self.segment(id).push_str(text),
        }
    }

    fn split(&mut self) {
        self.split = true;
    }

    fn segment(&mut self, id: &str) -> &mut String {
        let index = match self.segments.iter().position(|(message, _)| message.as_deref() == Some(id)) {
            Some(index) => index,
            None => {
                self.segments.push((Some(id.to_string()), String::new()));
                self.segments.len() - 1
            }
        };
        &mut self.segments[index].1
    }

    /// Replace a v2 message's content with a snapshot.
    fn replace(&mut self, id: &str, text: String) -> Patch {
        let segment = self.segment(id);
        let patch = match text.strip_prefix(segment.as_str()) {
            Some(rest) => Patch::Append(rest.to_string()),
            None => Patch::Replace(text.clone()),
        };
        *segment = text;
        patch
    }

    /// The last non-empty block.
    // gate: RT-G09 only the text after the last tool call becomes the message
    fn final_message(&self) -> String {
        self.segments.iter().rev().map(|(_, text)| text.trim_matches(['\n', '\r'])).find(|text| !text.trim().is_empty()).unwrap_or_default().to_string()
    }

    fn reply(&self) -> String {
        self.segments
            .iter()
            .map(|(_, text)| text.trim_matches(['\n', '\r']))
            .filter(|text| !text.trim().is_empty())
            .collect::<Vec<_>>()
            .join("\n\n")
    }
}

impl Harness {
    /// Start the process, connect over its stdio and negotiate the ACP version: v2 first,
    /// then, if the agent selects or requires v1, a fresh process on v1.
    ///
    /// `id` names the harness in every event. Permission requests are answered by `policy`.
    pub async fn launch(
        id: impl Into<HarnessId>,
        label: impl Into<String>,
        spec: &LaunchSpec,
        bus: Bus,
        policy: Arc<dyn PermissionPolicy>,
    ) -> Result<Self> {
        let id = id.into();
        let shared = Arc::new(Shared { id: id.clone(), bus: bus.clone(), policy, sessions: Mutex::default() });

        // No timer on initialize: an agent that is slow to start is simply still starting.
        let (conn, process, pid) = connect_v2(spec, &shared).await?;
        let request = s2::InitializeRequest::new(ProtocolVersion::V2, s2::Implementation::new("roundtable", env!("CARGO_PKG_VERSION")));
        let declined = match conn.send_initialize(request).block_task().await {
            Ok(InitializeOutcome::Initialized(init)) => {
                return Ok(Self::started(shared, label.into(), spec, pid, Conn::V2(conn), InitResponse::V2(init), process, None));
            }
            Ok(InitializeOutcome::LowerVersion(mismatch)) => match &mismatch.response {
                SelectedInitializeResponse::V1(_) => format!("the agent selected ACP v1 ({mismatch})"),
                _ => return Err(fail(process, spec, anyhow!("initialize: {mismatch}, which this host does not speak")).await),
            },
            Ok(_) => return Err(fail(process, spec, anyhow!("initialize: unrecognised negotiation outcome")).await),
            Err(error) => match v1_fallback_reason(&error) {
                Some(reason) => reason,
                None => return Err(fail(process, spec, anyhow!("initialize (ACP v2) failed: {error}")).await),
            },
        };
        // The SDK never converts a connection to another version: reconnect fresh on v1.
        let exit = process.end().await;
        tracing::info!(harness = %id, reason = %declined, code = ?exit.code, "ACP v2 declined; restarting the harness on v1");

        let (conn, process, pid) = connect_v1(spec, &shared).await?;
        let request = s1::InitializeRequest::new(ProtocolVersion::V1)
            .client_info(s1::Implementation::new("roundtable", env!("CARGO_PKG_VERSION")));
        let init = match conn.send_request(request).block_task().await {
            Ok(init) => init,
            Err(error) => return Err(fail(process, spec, anyhow!("initialize (ACP v1) failed: {error}")).await),
        };
        if init.protocol_version != ProtocolVersion::V1 {
            let version = init.protocol_version;
            return Err(fail(process, spec, anyhow!("initialize: the agent selected ACP version {version} after declining v2")).await);
        }
        Ok(Self::started(shared, label.into(), spec, pid, Conn::V1(conn), InitResponse::V1(init), process, Some(declined)))
    }

    #[allow(clippy::too_many_arguments)]
    fn started(
        shared: Arc<Shared>,
        label: String,
        spec: &LaunchSpec,
        pid: Option<u32>,
        conn: Conn,
        init: InitResponse,
        process: Process,
        v1_fallback: Option<String>,
    ) -> Self {
        let (protocol_version, agent_info, mcp_http, load_session) = match &init {
            InitResponse::V1(init) => (
                1,
                init.agent_info.as_ref().map(|info| (info.name.clone(), info.version.clone())),
                init.agent_capabilities.mcp_capabilities.http,
                init.agent_capabilities.load_session,
            ),
            InitResponse::V2(init) => (2, Some((init.info.name.clone(), init.info.version.clone())), v2_http_mcp(init), false),
        };
        shared.bus.publish(HarnessStarted {
            harness: shared.id.clone(),
            label,
            command: spec.display(),
            pid,
            protocol_version,
            v1_fallback,
            agent_name: agent_info.as_ref().map(|(name, _)| name.clone()),
            agent_version: agent_info.map(|(_, version)| version),
            mcp_http,
            load_session,
        });
        let Process { stop, exited } = process;
        let exit_shared = shared.clone();
        tokio::spawn(async move {
            let exit = exited.await.ok();
            // Any prompt still in flight ends now, exactly once, before the exit itself.
            exit_shared.fail_open_turns("the harness exited");
            exit_shared.bus.publish(HarnessExited {
                harness: exit_shared.id.clone(),
                code: exit.as_ref().and_then(|exit| exit.code),
                stderr_tail: exit.as_ref().map(|exit| exit.stderr_tail.clone()).unwrap_or_default(),
                connection_error: exit.and_then(|exit| exit.connection_error),
            });
        });
        let version = if protocol_version == 1 { ProtocolVersion::V1 } else { ProtocolVersion::V2 };
        let init = AgentInit { protocol_version: version, response: init };
        Self { shared, conn, init: Arc::new(init), stop: Arc::new(Mutex::new(Some(stop))) }
    }

    pub fn id(&self) -> &str {
        &self.shared.id
    }

    /// The agent's `initialize` response, in its negotiated version's schema.
    pub fn initialize_response(&self) -> &AgentInit {
        &self.init
    }

    /// The ACP version negotiated for this connection: 1 or 2.
    pub fn protocol_version(&self) -> u16 {
        match self.conn {
            Conn::V1(_) => 1,
            Conn::V2(_) => 2,
        }
    }

    /// Whether the agent accepts MCP servers over HTTP in `session/new`.
    pub fn accepts_http_mcp(&self) -> bool {
        match &self.init.response {
            InitResponse::V1(init) => init.agent_capabilities.mcp_capabilities.http,
            InitResponse::V2(init) => v2_http_mcp(init),
        }
    }

    /// Open a session in `cwd`, giving the agent `mcp_servers`.
    ///
    /// If the agent answers that authentication is required, and it advertised a method it
    /// runs itself, that method is used (`authenticate` on v1, `auth/login` on v2) and
    /// `session/new` is sent once more. A second failure is returned.
    pub async fn open_session(&self, cwd: &Path, mcp_servers: Vec<s1::McpServer>) -> Result<SessionId> {
        let (session, options) = match &self.conn {
            Conn::V1(conn) => {
                let request = s1::NewSessionRequest::new(cwd).mcp_servers(mcp_servers);
                let response = match conn.send_request(request.clone()).block_task().await {
                    Err(error) if error.code == ErrorCode::AUTH_REQUIRED => {
                        self.authenticate(&error).await?;
                        conn.send_request(request).block_task().await.context("session/new failed after authenticating")?
                    }
                    other => other.context("session/new failed")?,
                };
                (response.session_id.to_string(), Options::V1(response.config_options.unwrap_or_default()))
            }
            Conn::V2(conn) => {
                let servers = mcp_servers.into_iter().map(mcp_server_v2).collect::<Result<Vec<_>>>()?;
                let request = s2::NewSessionRequest::new(cwd.to_path_buf()).mcp_servers(servers);
                let response = match conn.send_request(request.clone()).block_task().await {
                    Err(error) if error.code == ErrorCode::AUTH_REQUIRED => {
                        self.authenticate(&error).await?;
                        conn.send_request(request).block_task().await.context("session/new failed after authenticating")?
                    }
                    other => other.context("session/new failed")?,
                };
                (response.session_id.to_string(), Options::V2(response.config_options))
            }
        };
        let config_options = self.shared.register(&session, cwd, &options);
        self.shared.bus.publish(SessionOpened {
            harness: self.shared.id.clone(),
            session: session.clone(),
            cwd: cwd.display().to_string(),
            config_options,
        });
        Ok(session)
    }

    /// Complete agent-managed authentication with the first advertised method the agent
    /// runs itself. `cause` is the error that asked for it.
    async fn authenticate(&self, cause: &acp::Error) -> Result<()> {
        let (call, method) = match (&self.conn, &self.init.response) {
            (Conn::V1(conn), InitResponse::V1(init)) => {
                let method = init.auth_methods.iter().find_map(|method| match method {
                    s1::AuthMethod::Agent(agent) => Some(agent.id.clone()),
                    _ => None,
                });
                let Some(method) = method else {
                    bail!("session/new failed: {cause}; the agent advertised no authentication method it runs itself ({})", auth_list(init.auth_methods.iter().map(|m| m.id().to_string())));
                };
                conn.send_request(s1::AuthenticateRequest::new(method.clone()))
                    .block_task()
                    .await
                    .with_context(|| format!("session/new failed: {cause}; authenticate with {method} failed"))?;
                ("authenticate", method.to_string())
            }
            (Conn::V2(conn), InitResponse::V2(init)) => {
                let method = init.auth_methods.iter().find_map(|method| match method {
                    s2::AuthMethod::Agent(agent) => Some(agent.method_id.clone()),
                    _ => None,
                });
                let Some(method) = method else {
                    bail!("session/new failed: {cause}; the agent advertised no authentication method it runs itself ({})", auth_list(init.auth_methods.iter().map(|m| m.method_id().to_string())));
                };
                conn.send_request(s2::LoginAuthRequest::new(method.clone()))
                    .block_task()
                    .await
                    .with_context(|| format!("session/new failed: {cause}; auth/login with {method} failed"))?;
                ("auth/login", method.to_string())
            }
            _ => unreachable!("the connection and its initialize response share a version"),
        };
        self.shared.bus.publish(Authenticated { harness: self.shared.id.clone(), call: call.into(), method });
        Ok(())
    }

    /// Reopen an existing session on this connection: v2 `session/resume`; on v1,
    /// `session/resume` where advertised, else `session/load` (its replayed history is not
    /// republished as new activity). Errors if the agent supports neither.
    ///
    /// `mcp_servers` are given to the agent again, as on `session/new`: a resumed session
    /// has only the MCP servers named in the resume request.
    pub async fn resume_session(&self, cwd: &Path, session_id: &str, mcp_servers: Vec<s1::McpServer>) -> Result<SessionId> {
        let (method, options) = match (&self.conn, &self.init.response) {
            (Conn::V1(conn), InitResponse::V1(init)) => {
                let capabilities = &init.agent_capabilities;
                if capabilities.session_capabilities.resume.is_some() {
                    let request = s1::ResumeSessionRequest::new(session_id.to_string(), cwd).mcp_servers(mcp_servers);
                    let response = conn.send_request(request).block_task().await.context("session/resume failed")?;
                    ("session/resume", Options::V1(response.config_options.unwrap_or_default()))
                } else if capabilities.load_session {
                    let response = self.load_v1(conn, cwd, session_id, mcp_servers).await.context("session/load failed")?;
                    ("session/load", Options::V1(response.config_options.unwrap_or_default()))
                } else {
                    bail!("the agent advertises neither session/resume nor session/load, so session {session_id} cannot be reopened");
                }
            }
            (Conn::V2(conn), InitResponse::V2(init)) => {
                if init.capabilities.session.is_none() {
                    bail!("the agent does not advertise the v2 session methods, so session {session_id} cannot be resumed");
                }
                let servers = mcp_servers.into_iter().map(mcp_server_v2).collect::<Result<Vec<_>>>()?;
                // No replayFrom: the agent keeps its context; history is not replayed.
                let request = s2::ResumeSessionRequest::new(session_id.to_string(), cwd.to_path_buf()).mcp_servers(servers);
                let response = conn.send_request(request).block_task().await.context("session/resume failed")?;
                ("session/resume", Options::V2(response.config_options))
            }
            _ => unreachable!("the connection and its initialize response share a version"),
        };
        let config_options = self.shared.register(session_id, cwd, &options);
        self.shared.bus.publish(SessionResumed {
            harness: self.shared.id.clone(),
            session: session_id.to_string(),
            cwd: cwd.display().to_string(),
            method: method.into(),
            config_options,
        });
        Ok(session_id.to_string())
    }

    /// v1 `session/load`. The agent replays the conversation as `session/update`s before it
    /// answers; those are marked as replay until the answer has been handled in order.
    async fn load_v1(
        &self,
        conn: &acp::v1::ConnectionTo<Agent>,
        cwd: &Path,
        session_id: &str,
        mcp_servers: Vec<s1::McpServer>,
    ) -> Result<s1::LoadSessionResponse, acp::Error> {
        self.shared.sessions.lock().unwrap().entry(session_id.to_string()).or_default().replaying = true;
        let (tx, rx) = oneshot::channel();
        let shared = self.shared.clone();
        let session = session_id.to_string();
        let request = s1::LoadSessionRequest::new(session_id.to_string(), cwd).mcp_servers(mcp_servers);
        // Ordered: every update the agent sent before its answer is handled before this runs.
        let sent = conn.prepare_request(request).on_receiving_result(async move |result| {
            if let Some(state) = shared.sessions.lock().unwrap().get_mut(&session) {
                state.replaying = false;
            }
            let _ = tx.send(result);
            Ok(())
        });
        if let Err(error) = sent {
            if let Some(state) = self.shared.sessions.lock().unwrap().get_mut(session_id) {
                state.replaying = false;
            }
            return Err(error);
        }
        rx.await.unwrap_or_else(|_| Err(acp::Error::internal_error().data("session/load was dropped without an answer")))
    }

    /// Set an advertised configuration option, such as the model, to one of its values.
    ///
    /// Only an option the session advertised is sent; any other id is an error naming the
    /// advertised ones. A boolean option takes "true" or "false".
    pub async fn set_config(&self, session: &str, config_id: &str, value: &str) -> Result<()> {
        let kind = {
            let sessions = self.shared.sessions.lock().unwrap();
            let advertised = sessions.get(session).map(|state| state.options.as_slice()).unwrap_or_default();
            match advertised.iter().find(|option| option.id == config_id) {
                Some(option) => option.kind.clone(),
                None => {
                    let names: Vec<&str> = advertised.iter().map(|option| option.id.as_str()).collect();
                    let names = if names.is_empty() { "none".to_string() } else { names.join(", ") };
                    bail!("session {session} does not advertise the configuration option {config_id:?}; it advertises: {names}");
                }
            }
        };
        let boolean = match &kind {
            OptionKind::Select => None,
            OptionKind::Boolean => Some(value.parse::<bool>().map_err(|_| anyhow!("{config_id} is a boolean option; {value:?} is not true or false"))?),
            OptionKind::Other(kind) => bail!("{config_id} is a {kind:?} option, which this host cannot set"),
        };
        let options = match &self.conn {
            Conn::V1(conn) => {
                let value = match boolean {
                    Some(flag) => s1::SessionConfigOptionValue::boolean(flag),
                    None => s1::SessionConfigOptionValue::value_id(value.to_string()),
                };
                let request = s1::SetSessionConfigOptionRequest::new(session.to_string(), config_id.to_string(), value.clone());
                let response = conn.send_request(request).block_task().await.with_context(|| format!("could not set {config_id} to {value:?}"))?;
                Options::V1(response.config_options)
            }
            Conn::V2(conn) => {
                let value = match boolean {
                    Some(flag) => s2::SessionConfigOptionValue::boolean(flag),
                    None => s2::SessionConfigOptionValue::id(value.to_string()),
                };
                let request = s2::SetSessionConfigOptionRequest::new(session.to_string(), config_id.to_string(), value.clone());
                let response = conn.send_request(request).block_task().await.with_context(|| format!("could not set {config_id} to {value:?}"))?;
                Options::V2(response.config_options)
            }
        };
        let config_options = self.shared.set_options(session, &options);
        self.shared.bus.publish(ConfigChanged { harness: self.shared.id.clone(), session: session.to_string(), config_options });
        Ok(())
    }

    /// Send a prompt turn. Returns at once; the outcome is published as an event.
    ///
    /// Errors if this session already has a turn in progress (one turn at a time).
    pub fn prompt(&self, session: &str, text: impl Into<String>) -> Result<PromptId> {
        let text = text.into();
        let prompt = NEXT_PROMPT.fetch_add(1, Ordering::Relaxed) + 1;
        {
            let mut sessions = self.shared.sessions.lock().unwrap();
            let state = sessions.entry(session.to_string()).or_default();
            if let Some(running) = state.turn.prompt {
                // gate: RT-G19 one prompt at a time per agent session
                bail!("session {session} is still running prompt {running}");
            }
            state.turn = Turn { prompt: Some(prompt), ..Turn::default() };
        }
        self.shared.bus.publish(PromptSent {
            harness: self.shared.id.clone(),
            session: session.to_string(),
            prompt,
            text: text.clone(),
        });
        let shared = self.shared.clone();
        let session_id = session.to_string();
        // Ordered callbacks: every update the agent sent before its answer is handled first.
        let sent = match &self.conn {
            Conn::V1(conn) => {
                let request = s1::PromptRequest::new(session.to_string(), vec![s1::ContentBlock::Text(s1::TextContent::new(text))]);
                conn.prepare_request(request).on_receiving_result(async move |result| {
                    // v1: the answer ends the turn. The exit path may already have failed it.
                    let Some((reply, final_message)) = shared.take_turn(&session_id, prompt) else { return Ok(()) };
                    match result {
                        Ok(response) => shared.bus.publish(PromptCompleted {
                            harness: shared.id.clone(),
                            session: session_id,
                            prompt,
                            stop_reason: text_of(&response.stop_reason).unwrap_or_else(|| "unknown".into()),
                            reply,
                            final_message,
                        }),
                        Err(error) => shared.bus.publish(PromptFailed {
                            harness: shared.id.clone(),
                            session: session_id,
                            prompt,
                            error: error.to_string(),
                        }),
                    };
                    Ok(())
                })
            }
            Conn::V2(conn) => {
                let request = s2::PromptRequest::new(session.to_string(), vec![s2::ContentBlock::Text(s2::TextContent::new(text))]);
                conn.prepare_request(request).on_receiving_result(async move |result| {
                    // v2: the answer only accepts the prompt; the turn ends on `idle`.
                    if let Err(error) = result {
                        if shared.take_turn(&session_id, prompt).is_some() {
                            shared.bus.publish(PromptFailed {
                                harness: shared.id.clone(),
                                session: session_id,
                                prompt,
                                error: format!("prompt not accepted: {error}"),
                            });
                        } else {
                            tracing::error!(harness = %shared.id, session = %session_id, prompt, %error, "the agent rejected a prompt whose turn had already ended");
                        }
                    }
                    Ok(())
                })
            }
        };
        if let Err(error) = sent {
            self.shared.take_turn(session, prompt);
            return Err(anyhow!("could not send prompt: {error}"));
        }
        Ok(prompt)
    }

    /// Whether this session has a prompt turn in progress.
    pub fn is_busy(&self, session: &str) -> bool {
        self.shared.sessions.lock().unwrap().get(session).is_some_and(|state| state.turn.prompt.is_some())
    }

    /// Ask the agent to stop the session's current turn. Only on an explicit request.
    pub fn cancel(&self, session: &str) -> Result<()> {
        match &self.conn {
            Conn::V1(conn) => conn.send_notification(s1::CancelNotification::new(session.to_string())),
            Conn::V2(conn) => conn.send_notification(s2::CancelSessionNotification::new(session.to_string())),
        }
        .map_err(|error| anyhow!("could not send cancel: {error}"))
    }

    /// End the harness: `session/close` each open session where the agent supports it (each
    /// outcome is a [`SessionClosed`] event), then close the connection and end the process
    /// (see the shutdown sequence in `process.rs`). Returns at once; [`HarnessExited`]
    /// reports the end.
    pub fn shutdown(&self) {
        let Some(stop) = self.stop.lock().unwrap().take() else { return };
        let closes = match &self.init.response {
            InitResponse::V1(init) => init.agent_capabilities.session_capabilities.close.is_some(),
            InitResponse::V2(init) => init.capabilities.session.is_some(),
        };
        let sessions: Vec<SessionId> = if closes {
            self.shared.sessions.lock().unwrap().iter().filter(|(_, state)| state.open).map(|(id, _)| id.clone()).collect()
        } else {
            Vec::new()
        };
        if sessions.is_empty() {
            let _ = stop.send(());
            return;
        }
        let conn = self.conn.clone();
        let shared = self.shared.clone();
        // No timer: closing waits for the agent's answers (an error answer or the connection
        // ending also completes it), then the process shutdown sequence runs.
        tokio::spawn(async move {
            let closes = sessions.into_iter().map(|session| {
                let conn = conn.clone();
                async move {
                    let result = match &conn {
                        Conn::V1(conn) => conn.send_request(s1::CloseSessionRequest::new(session.clone())).block_task().await.map(drop),
                        Conn::V2(conn) => conn.send_request(s2::CloseSessionRequest::new(session.clone())).block_task().await.map(drop),
                    };
                    (session, result)
                }
            });
            for (session, result) in futures::future::join_all(closes).await {
                if let Some(state) = shared.sessions.lock().unwrap().get_mut(&session) {
                    state.open = false;
                }
                shared.bus.publish(SessionClosed {
                    harness: shared.id.clone(),
                    session,
                    error: result.err().map(|error| error.to_string()),
                });
            }
            let _ = stop.send(());
        });
    }
}

/// Configuration options as one version's schema reported them.
enum Options {
    V1(Vec<s1::SessionConfigOption>),
    V2(Vec<s2::SessionConfigOption>),
}

impl Options {
    fn summary(&self) -> (Vec<ConfigOption>, Vec<Advertised>) {
        match self {
            Options::V1(options) => (summarize_v1(options), options.iter().map(advertised_v1).collect()),
            Options::V2(options) => (summarize_v2(options), options.iter().map(advertised_v2).collect()),
        }
    }
}

impl Shared {
    /// Record a session opened or resumed on this connection; returns its option summary.
    fn register(&self, session: &str, cwd: &Path, options: &Options) -> Vec<ConfigOption> {
        let (summary, advertised) = options.summary();
        let mut sessions = self.sessions.lock().unwrap();
        let state = sessions.entry(session.to_string()).or_default();
        state.cwd = Some(cwd.to_path_buf());
        state.open = true;
        state.options = advertised;
        summary
    }

    fn set_options(&self, session: &str, options: &Options) -> Vec<ConfigOption> {
        let (summary, advertised) = options.summary();
        self.sessions.lock().unwrap().entry(session.to_string()).or_default().options = advertised;
        summary
    }

    /// End `prompt` on `session` and return its reply and final message, if it is still the
    /// open turn.
    fn take_turn(&self, session: &str, prompt: PromptId) -> Option<(String, String)> {
        let mut sessions = self.sessions.lock().unwrap();
        let turn = &mut sessions.get_mut(session)?.turn;
        if turn.prompt != Some(prompt) {
            return None;
        }
        turn.prompt = None;
        turn.active = false;
        Some((turn.text.reply(), turn.text.final_message()))
    }

    /// Publish a failure for every prompt still open, closing it.
    fn fail_open_turns(&self, error: &str) {
        let open: Vec<(SessionId, PromptId)> = self
            .sessions
            .lock()
            .unwrap()
            .iter()
            .filter_map(|(session, state)| state.turn.prompt.map(|prompt| (session.clone(), prompt)))
            .collect();
        for (session, prompt) in open {
            if self.take_turn(&session, prompt).is_some() {
                self.bus.publish(PromptFailed { harness: self.id.clone(), session, prompt, error: error.into() });
            }
        }
    }

    fn publish_text(&self, session: String, prompt: Option<PromptId>, message: Option<String>, thought: bool, patch: Patch) {
        let (text, replace) = match patch {
            Patch::Append(text) => (text, false),
            Patch::Replace(text) => (text, true),
        };
        if text.is_empty() && !replace {
            return;
        }
        self.bus.publish(AgentText { harness: self.id.clone(), session, prompt, text, thought, message, replace });
    }

    fn on_update_v1(&self, notification: s1::SessionNotification) {
        let session = notification.session_id.to_string();
        let mut sessions = self.sessions.lock().unwrap();
        let state = sessions.entry(session.clone()).or_default();
        let prompt = state.turn.prompt;
        let replaying = state.replaying;
        match notification.update {
            // Replayed history (session/load) is not new activity: not republished.
            s1::SessionUpdate::AgentMessageChunk(_)
            | s1::SessionUpdate::AgentThoughtChunk(_)
            | s1::SessionUpdate::ToolCall(_)
            | s1::SessionUpdate::ToolCallUpdate(_)
                if replaying => {}
            s1::SessionUpdate::AgentMessageChunk(chunk) => {
                if let s1::ContentBlock::Text(content) = chunk.content {
                    state.turn.text.append(None, &content.text);
                    drop(sessions);
                    self.publish_text(session, prompt, None, false, Patch::Append(content.text));
                }
            }
            s1::SessionUpdate::AgentThoughtChunk(chunk) => {
                if let s1::ContentBlock::Text(content) = chunk.content {
                    drop(sessions);
                    self.publish_text(session, prompt, None, true, Patch::Append(content.text));
                }
            }
            s1::SessionUpdate::ToolCall(call) => {
                state.turn.text.split();
                drop(sessions);
                self.bus.publish(ToolActivity {
                    harness: self.id.clone(),
                    session,
                    prompt,
                    tool_call: call.tool_call_id.to_string(),
                    title: Some(call.title),
                    kind: text_of(&call.kind),
                    status: text_of(&call.status),
                    locations: call.locations.iter().map(|l| l.path.display().to_string()).collect(),
                });
            }
            s1::SessionUpdate::ToolCallUpdate(update) => {
                drop(sessions);
                let fields = update.fields;
                self.bus.publish(ToolActivity {
                    harness: self.id.clone(),
                    session,
                    prompt,
                    tool_call: update.tool_call_id.to_string(),
                    title: fields.title,
                    kind: fields.kind.as_ref().and_then(text_of),
                    status: fields.status.as_ref().and_then(text_of),
                    locations: fields.locations.unwrap_or_default().iter().map(|l| l.path.display().to_string()).collect(),
                });
            }
            s1::SessionUpdate::ConfigOptionUpdate(update) => {
                state.options = update.config_options.iter().map(advertised_v1).collect();
                drop(sessions);
                self.bus.publish(ConfigChanged { harness: self.id.clone(), session, config_options: summarize_v1(&update.config_options) });
            }
            _ => {}
        }
    }

    fn on_update_v2(&self, notification: s2::UpdateSessionNotification) {
        let session = notification.session_id.to_string();
        let mut sessions = self.sessions.lock().unwrap();
        let state = sessions.entry(session.clone()).or_default();
        let prompt = state.turn.prompt;
        match notification.update {
            s2::SessionUpdate::AgentMessageChunk(chunk) => {
                if let s2::ContentBlock::Text(content) = chunk.content {
                    let message = chunk.message_id.to_string();
                    state.turn.text.append(Some(&message), &content.text);
                    drop(sessions);
                    self.publish_text(session, prompt, Some(message), false, Patch::Append(content.text));
                }
            }
            s2::SessionUpdate::AgentMessage(snapshot) => {
                let message = snapshot.message_id.to_string();
                let Some(text) = snapshot_text(snapshot.content) else { return };
                let patch = state.turn.text.replace(&message, text);
                drop(sessions);
                self.publish_text(session, prompt, Some(message), false, patch);
            }
            s2::SessionUpdate::AgentThoughtChunk(chunk) => {
                if let s2::ContentBlock::Text(content) = chunk.content {
                    let message = chunk.message_id.to_string();
                    state.turn.thoughts.append(Some(&message), &content.text);
                    drop(sessions);
                    self.publish_text(session, prompt, Some(message), true, Patch::Append(content.text));
                }
            }
            s2::SessionUpdate::AgentThought(snapshot) => {
                let message = snapshot.message_id.to_string();
                let Some(text) = snapshot_text(snapshot.content) else { return };
                let patch = state.turn.thoughts.replace(&message, text);
                drop(sessions);
                self.publish_text(session, prompt, Some(message), true, patch);
            }
            // v2 has no separate tool_call: tool_call_update is an upsert.
            s2::SessionUpdate::ToolCallUpdate(update) => {
                drop(sessions);
                self.bus.publish(ToolActivity {
                    harness: self.id.clone(),
                    session,
                    prompt,
                    tool_call: update.tool_call_id.to_string(),
                    title: update.title.take(),
                    kind: update.kind.take().as_ref().and_then(text_of),
                    status: update.status.take().as_ref().and_then(text_of),
                    locations: update.locations.take().unwrap_or_default().iter().map(|l| l.path.0.display().to_string()).collect(),
                });
            }
            s2::SessionUpdate::ConfigOptionUpdate(update) => {
                state.options = update.config_options.iter().map(advertised_v2).collect();
                drop(sessions);
                self.bus.publish(ConfigChanged { harness: self.id.clone(), session, config_options: summarize_v2(&update.config_options) });
            }
            s2::SessionUpdate::StateUpdate(update) => {
                let background = update.background().map(<[_]>::len);
                let (foreground, stop_reason) = match &update {
                    s2::StateUpdate::Running(_) => (ForegroundState::Running, None),
                    s2::StateUpdate::Idle(idle) => (ForegroundState::Idle, idle.stop_reason.clone()),
                    s2::StateUpdate::RequiresAction(_) => (ForegroundState::RequiresAction, None),
                    s2::StateUpdate::Other(other) => (ForegroundState::Other(other.state.clone()), None),
                    // Any other state means the foreground work is still active.
                    other => (ForegroundState::Other(state_name(other)), None),
                };
                // Only `idle` after the turn was seen active ends it; anything else, known or
                // not, means the turn is still running.
                let ended = if foreground == ForegroundState::Idle {
                    match prompt {
                        Some(prompt) if state.turn.active => Some(prompt),
                        _ => None,
                    }
                } else {
                    if prompt.is_some() {
                        state.turn.active = true;
                    }
                    None
                };
                drop(sessions);
                let stop_text = stop_reason.as_ref().map(stop_reason_v2);
                self.bus.publish(AgentState {
                    harness: self.id.clone(),
                    session: session.clone(),
                    prompt,
                    state: foreground,
                    stop_reason: stop_text.clone(),
                    background,
                });
                let Some(prompt) = ended else { return };
                let Some((reply, final_message)) = self.take_turn(&session, prompt) else { return };
                match stop_reason {
                    Some(s2::StopReason::Error(error)) => self.bus.publish(PromptFailed {
                        harness: self.id.clone(),
                        session,
                        prompt,
                        error: match error.error {
                            Some(error) => format!("the turn stopped with an error: {} ({})", error.message, error.code),
                            None => "the turn stopped with an error the agent did not describe".into(),
                        },
                    }),
                    _ => self.bus.publish(PromptCompleted {
                        harness: self.id.clone(),
                        session,
                        prompt,
                        stop_reason: stop_text.unwrap_or_else(|| "unreported".into()),
                        reply,
                        final_message,
                    }),
                };
            }
            _ => {}
        }
    }

    /// Decide a permission request. Returns the index of the option to select, if any.
    fn decide(&self, session: String, ask: PermissionAsk, offered: &[Choice]) -> Option<usize> {
        let verdict = self.policy.decide(&ask);
        let (mut allowed, mut reason) = match &verdict {
            Verdict::Allow { reason } => (true, reason.clone()),
            // gate: RT-G18 a refused permission request
            Verdict::Reject { reason } => (false, reason.clone()),
        };
        let pick = |kinds: [Choice; 2]| kinds.iter().find_map(|kind| offered.iter().position(|o| o == kind).map(|i| (i, *kind)));
        let allow = || pick([Choice::AllowOnce, Choice::AllowAlways]);
        let reject = || pick([Choice::RejectOnce, Choice::RejectAlways]);
        // Prefer one-time answers: a scope-checked allow must not become a standing rule in the agent.
        let mut option = if allowed { allow() } else { reject() };
        if allowed && option.is_none() {
            allowed = false;
            reason = format!("{reason}; the agent offered no allow option");
            option = reject();
        }
        if let Some((_, kind)) = &option
            && matches!(kind, Choice::AllowAlways | Choice::RejectAlways)
        {
            reason = format!("{reason} (the agent offered only a standing option)");
        }
        self.bus.publish(PermissionDecided {
            harness: self.id.clone(),
            session,
            title: ask.title,
            kind: ask.kind,
            locations: ask.locations.iter().map(|p| p.display().to_string()).collect(),
            allowed,
            reason,
        });
        option.map(|(index, _)| index)
    }

    fn cwd(&self, session: &str) -> PathBuf {
        self.sessions.lock().unwrap().get(session).and_then(|state| state.cwd.clone()).unwrap_or_default()
    }

    fn on_permission_v1(&self, request: s1::RequestPermissionRequest) -> s1::RequestPermissionResponse {
        let session = request.session_id.to_string();
        let fields = &request.tool_call.fields;
        let ask = PermissionAsk {
            title: fields.title.clone(),
            kind: fields.kind.as_ref().and_then(text_of),
            locations: fields.locations.iter().flatten().map(|l| l.path.clone()).collect(),
            cwd: self.cwd(&session),
        };
        let offered: Vec<Choice> = request.options.iter().map(|o| Choice::of(&o.kind)).collect();
        let outcome = match self.decide(session, ask, &offered) {
            Some(index) => s1::RequestPermissionOutcome::Selected(s1::SelectedPermissionOutcome::new(request.options[index].option_id.clone())),
            None => s1::RequestPermissionOutcome::Cancelled,
        };
        s1::RequestPermissionResponse::new(outcome)
    }

    fn on_permission_v2(&self, request: s2::RequestPermissionRequest) -> s2::RequestPermissionResponse {
        let session = request.session_id.to_string();
        let (kind, locations) = match &request.subject {
            Some(s2::RequestPermissionSubject::ToolCall(subject)) => (
                subject.tool_call.kind.clone().take().as_ref().and_then(text_of),
                match &subject.tool_call.locations {
                    MaybeUndefined::Value(locations) => locations.iter().map(|l| l.path.0.clone()).collect(),
                    _ => Vec::new(),
                },
            ),
            // A command names the directory it runs in; the scope check applies to it.
            Some(s2::RequestPermissionSubject::Command(command)) => (Some("execute".into()), vec![command.cwd.0.clone()]),
            _ => (None, Vec::new()),
        };
        let ask = PermissionAsk { title: Some(request.title.clone()), kind, locations, cwd: self.cwd(&session) };
        let offered: Vec<Choice> = request.options.iter().map(|o| Choice::of(&o.kind)).collect();
        let outcome = match self.decide(session, ask, &offered) {
            Some(index) => s2::RequestPermissionOutcome::Selected(s2::SelectedPermissionOutcome::new(request.options[index].option_id.clone())),
            None => s2::CancelledPermissionOutcome::new().into(),
        };
        s2::RequestPermissionResponse::new(outcome)
    }
}

/// A permission option's kind, the same in both versions.
#[derive(Clone, Copy, PartialEq, Eq)]
enum Choice {
    AllowOnce,
    AllowAlways,
    RejectOnce,
    RejectAlways,
    Other,
}

impl Choice {
    fn of<T: Serialize>(kind: &T) -> Self {
        match text_of(kind).as_deref() {
            Some("allow_once") => Self::AllowOnce,
            Some("allow_always") => Self::AllowAlways,
            Some("reject_once") => Self::RejectOnce,
            Some("reject_always") => Self::RejectAlways,
            _ => Self::Other,
        }
    }
}

/// Start the process and put an ACP v2 client connection on its stdio.
async fn connect_v2(spec: &LaunchSpec, shared: &Arc<Shared>) -> Result<(acp::v2::ConnectionTo<Agent>, Process, Option<u32>)> {
    let (stdin, stdout, spawned) = process::spawn(spec)?;
    let pid = spawned.pid;
    let transport = ByteStreams::new(stdin.compat_write(), stdout.compat());
    let (conn_tx, conn_rx) = oneshot::channel();
    let (stop_tx, stop_rx) = oneshot::channel::<()>();
    let (ended_tx, ended_rx) = oneshot::channel();
    let on_update = shared.clone();
    let on_permission = shared.clone();
    let connection = Client
        .v2()
        .on_receive_notification(
            async move |notification: s2::UpdateSessionNotification, _cx| {
                on_update.on_update_v2(notification);
                Ok(())
            },
            acp::on_receive_notification!(),
        )
        .on_receive_request(
            async move |request: s2::RequestPermissionRequest, responder, _cx| responder.respond(on_permission.on_permission_v2(request)),
            acp::on_receive_request!(),
        )
        .connect_with(transport, async move |cx: acp::v2::ConnectionTo<Agent>| {
            let _ = conn_tx.send(cx);
            let _ = stop_rx.await;
            Ok(())
        });
    tokio::spawn(async move {
        let _ = ended_tx.send(connection.await.err().map(|error| error.to_string()));
    });
    let process = spawned.supervise(stop_tx, ended_rx);
    match conn_rx.await {
        Ok(conn) => Ok((conn, process, pid)),
        Err(_) => Err(fail(process, spec, anyhow!("the connection closed before it was established")).await),
    }
}

/// Start the process and put an ACP v1 client connection on its stdio.
async fn connect_v1(spec: &LaunchSpec, shared: &Arc<Shared>) -> Result<(acp::v1::ConnectionTo<Agent>, Process, Option<u32>)> {
    let (stdin, stdout, spawned) = process::spawn(spec)?;
    let pid = spawned.pid;
    let transport = ByteStreams::new(stdin.compat_write(), stdout.compat());
    let (conn_tx, conn_rx) = oneshot::channel();
    let (stop_tx, stop_rx) = oneshot::channel::<()>();
    let (ended_tx, ended_rx) = oneshot::channel();
    let on_update = shared.clone();
    let on_permission = shared.clone();
    let connection = Client
        .v1()
        .on_receive_notification(
            async move |notification: s1::SessionNotification, _cx| {
                on_update.on_update_v1(notification);
                Ok(())
            },
            acp::on_receive_notification!(),
        )
        .on_receive_request(
            async move |request: s1::RequestPermissionRequest, responder, _cx| responder.respond(on_permission.on_permission_v1(request)),
            acp::on_receive_request!(),
        )
        .connect_with(transport, async move |cx: acp::v1::ConnectionTo<Agent>| {
            let _ = conn_tx.send(cx);
            let _ = stop_rx.await;
            Ok(())
        });
    tokio::spawn(async move {
        let _ = ended_tx.send(connection.await.err().map(|error| error.to_string()));
    });
    let process = spawned.supervise(stop_tx, ended_rx);
    match conn_rx.await {
        Ok(conn) => Ok((conn, process, pid)),
        Err(_) => Err(fail(process, spec, anyhow!("the connection closed before it was established")).await),
    }
}

/// End a process that could not be used and describe why, with its exit and stderr.
async fn fail(process: Process, spec: &LaunchSpec, error: anyhow::Error) -> anyhow::Error {
    let exit = process.end().await;
    let mut message = format!("{}: {error}", spec.display());
    if let Some(code) = exit.code {
        message.push_str(&format!("; exit code {code}"));
    }
    if let Some(connection) = exit.connection_error {
        message.push_str(&format!("; connection: {connection}"));
    }
    if !exit.stderr_tail.trim().is_empty() {
        message.push_str(&format!("; stderr:\n{}", exit.stderr_tail));
    }
    anyhow!(message)
}

/// Why an `initialize` error from a v2 offer means the agent speaks v1, if it does.
///
/// - `-32022` (unsupported protocol version) whose data lists v1 among the supported versions;
/// - an answer in the v1 field layout (`agentCapabilities` / `agentInfo`, no v2 `info`) that
///   therefore fails to parse as a v2 response, as from a v1 agent that echoes the version.
fn v1_fallback_reason(error: &acp::Error) -> Option<String> {
    let data = error.data.as_ref();
    if error.code.value() == -32022 {
        let supported = data?.get("supported")?.as_array()?;
        return supported
            .iter()
            .any(|version| version.as_u64() == Some(1))
            .then(|| format!("the agent rejected v2 (-32022) and supports {}", serde_json::Value::Array(supported.clone())));
    }
    if error.code == ErrorCode::PARSE_ERROR {
        let json = data?.get("json")?;
        let legacy = json.get("info").is_none() && (json.get("agentCapabilities").is_some() || json.get("agentInfo").is_some());
        return legacy.then(|| "the agent answered initialize with the v1 field layout".to_string());
    }
    None
}

fn v2_http_mcp(init: &s2::InitializeResponse) -> bool {
    init.capabilities.session.as_ref().and_then(|session| session.mcp.as_ref()).is_some_and(|mcp| mcp.http.is_some())
}

/// The same MCP server in the v2 schema. v2 has no SSE transport.
fn mcp_server_v2(server: s1::McpServer) -> Result<s2::McpServer> {
    let mut value = serde_json::to_value(&server)?;
    match value.get("type").and_then(|kind| kind.as_str()) {
        Some("sse") => bail!("ACP v2 has no SSE MCP transport; cannot give the agent MCP server {value}"),
        // v1 stdio servers carry no `type`; v2 requires it.
        None => {
            if let Some(object) = value.as_object_mut() {
                object.insert("type".into(), "stdio".into());
            }
        }
        Some(_) => {}
    }
    serde_json::from_value(value).context("MCP server cannot be expressed in ACP v2")
}

fn auth_list(methods: impl Iterator<Item = String>) -> String {
    let methods: Vec<String> = methods.collect();
    if methods.is_empty() { "none advertised".into() } else { format!("advertised: {}", methods.join(", ")) }
}

/// The text of a v2 message snapshot; `None` when it leaves the content unchanged.
fn snapshot_text(content: MaybeUndefined<Vec<s2::ContentBlock>>) -> Option<String> {
    match content {
        MaybeUndefined::Undefined => None,
        MaybeUndefined::Null => Some(String::new()),
        MaybeUndefined::Value(blocks) => Some(
            blocks
                .iter()
                .filter_map(|block| match block {
                    s2::ContentBlock::Text(text) => Some(text.text.as_str()),
                    _ => None,
                })
                .collect(),
        ),
    }
}

fn state_name(state: &s2::StateUpdate) -> String {
    serde_json::to_value(state)
        .ok()
        .and_then(|value| value.get("state").and_then(|state| state.as_str()).map(str::to_string))
        .unwrap_or_else(|| "unknown".into())
}

fn stop_reason_v2(reason: &s2::StopReason) -> String {
    match reason {
        s2::StopReason::Other(other) => other.stop_reason.clone(),
        s2::StopReason::Error(_) => "error".into(),
        // Internally tagged: `{"stopReason": "end_turn"}`.
        reason => serde_json::to_value(reason)
            .ok()
            .and_then(|value| value.get("stopReason").and_then(|reason| reason.as_str()).map(str::to_string))
            .unwrap_or_else(|| "unknown".into()),
    }
}

/// The serde string form of a schema enum or id.
fn text_of<T: Serialize>(value: &T) -> Option<String> {
    match serde_json::to_value(value).ok()? {
        serde_json::Value::String(text) => Some(text),
        serde_json::Value::Number(number) => Some(number.to_string()),
        _ => None,
    }
}

fn advertised_v1(option: &s1::SessionConfigOption) -> Advertised {
    let kind = match &option.kind {
        s1::SessionConfigKind::Select(_) => OptionKind::Select,
        s1::SessionConfigKind::Boolean(_) => OptionKind::Boolean,
        #[allow(unreachable_patterns)]
        _ => OptionKind::Other("unknown".into()),
    };
    Advertised { id: text_of(&option.id).unwrap_or_default(), kind }
}

fn advertised_v2(option: &s2::SessionConfigOption) -> Advertised {
    let kind = match &option.kind {
        s2::SessionConfigKind::Select(_) => OptionKind::Select,
        s2::SessionConfigKind::Boolean(_) => OptionKind::Boolean,
        s2::SessionConfigKind::Other(other) => OptionKind::Other(other.type_.clone()),
        #[allow(unreachable_patterns)]
        _ => OptionKind::Other("unknown".into()),
    };
    Advertised { id: text_of(&option.config_id).unwrap_or_default(), kind }
}

fn summarize_v1(options: &[s1::SessionConfigOption]) -> Vec<ConfigOption> {
    options
        .iter()
        .map(|option| {
            let (current, choices) = match &option.kind {
                s1::SessionConfigKind::Select(select) => {
                    let flat: Vec<_> = match &select.options {
                        s1::SessionConfigSelectOptions::Ungrouped(options) => options.iter().collect(),
                        s1::SessionConfigSelectOptions::Grouped(groups) => groups.iter().flat_map(|g| g.options.iter()).collect(),
                        #[allow(unreachable_patterns)]
                        _ => Vec::new(),
                    };
                    (
                        text_of(&select.current_value),
                        flat.into_iter()
                            .map(|choice| ConfigChoice { value: text_of(&choice.value).unwrap_or_default(), name: choice.name.clone() })
                            .collect(),
                    )
                }
                s1::SessionConfigKind::Boolean(boolean) => (text_of(boolean), Vec::new()),
                #[allow(unreachable_patterns)]
                _ => (None, Vec::new()),
            };
            ConfigOption {
                id: text_of(&option.id).unwrap_or_default(),
                name: option.name.clone(),
                category: option.category.as_ref().and_then(text_of),
                current,
                choices,
            }
        })
        .collect()
}

fn summarize_v2(options: &[s2::SessionConfigOption]) -> Vec<ConfigOption> {
    options
        .iter()
        .map(|option| {
            let (current, choices) = match &option.kind {
                s2::SessionConfigKind::Select(select) => {
                    let flat: Vec<_> = match &select.options {
                        s2::SessionConfigSelectOptions::Ungrouped(options) => options.iter().collect(),
                        s2::SessionConfigSelectOptions::Grouped(groups) => groups.iter().flat_map(|g| g.options.iter()).collect(),
                        #[allow(unreachable_patterns)]
                        _ => Vec::new(),
                    };
                    (
                        text_of(&select.current_value),
                        flat.into_iter()
                            .map(|choice| ConfigChoice { value: text_of(&choice.value).unwrap_or_default(), name: choice.name.clone() })
                            .collect(),
                    )
                }
                s2::SessionConfigKind::Boolean(boolean) => (Some(boolean.current_value.to_string()), Vec::new()),
                _ => (None, Vec::new()),
            };
            ConfigOption {
                id: text_of(&option.config_id).unwrap_or_default(),
                name: option.name.clone(),
                category: option.category.as_ref().and_then(text_of),
                current,
                choices,
            }
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn version_mismatch_listing_v1_falls_back() {
        let error = acp::Error::new(-32022, "Unsupported protocol version").data(serde_json::json!({"requested": 2, "supported": [1]}));
        assert!(v1_fallback_reason(&error).is_some());
        let error = acp::Error::new(-32022, "Unsupported protocol version").data(serde_json::json!({"requested": 2, "supported": [3]}));
        assert!(v1_fallback_reason(&error).is_none(), "an agent that does not list v1 is not a v1 agent");
    }

    #[test]
    fn a_v1_shaped_answer_falls_back_and_other_errors_do_not() {
        let error = acp::Error::parse_error().data(serde_json::json!({
            "error": "missing field `info`", "phase": "deserialization",
            "json": {"protocolVersion": 2, "agentCapabilities": {}, "agentInfo": {"name": "x", "version": "1"}}
        }));
        assert!(v1_fallback_reason(&error).is_some());
        assert!(v1_fallback_reason(&acp::Error::internal_error()).is_none());
        assert!(v1_fallback_reason(&acp::Error::invalid_params()).is_none());
    }

    #[test]
    fn the_reply_is_every_text_segment_in_order() {
        let mut text = Transcript::default();
        text.append(None, "Let me check.");
        text.split();
        text.append(None, "Final ");
        text.append(None, "answer.");
        assert_eq!(text.reply(), "Let me check.\n\nFinal answer.");
        assert_eq!(text.final_message(), "Final answer.");
        let mut text = Transcript::default();
        text.append(Some("a"), "one");
        text.append(Some("b"), "two");
        text.append(Some("a"), " more");
        assert!(matches!(text.replace("b", "two!".into()), Patch::Append(rest) if rest == "!"));
        assert!(matches!(text.replace("a", "uno".into()), Patch::Replace(all) if all == "uno"));
        assert_eq!(text.reply(), "uno\n\ntwo!");
        assert_eq!(text.final_message(), "two!");
        text.append(None, "\n\n");
        assert_eq!(text.final_message(), "two!", "a trailing blank block is not the final message");
    }

    #[test]
    fn stdio_and_http_mcp_servers_convert_to_v2_and_sse_does_not() {
        let http = s1::McpServer::Http(s1::McpServerHttp::new("rt", "http://localhost:1/mcp"));
        assert!(matches!(mcp_server_v2(http).unwrap(), s2::McpServer::Http(_)));
        let stdio = s1::McpServer::Stdio(s1::McpServerStdio::new("tool", "/bin/tool"));
        assert!(matches!(mcp_server_v2(stdio).unwrap(), s2::McpServer::Stdio(_)));
        let sse = s1::McpServer::Sse(s1::McpServerSse::new("old", "http://localhost:1/sse"));
        assert!(mcp_server_v2(sse).is_err());
    }
}
