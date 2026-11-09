// A scripted ACP agent for tests. Not a participant anyone should seat for real work.
//
// FAKE_SCRIPT: JSON array of steps, one per prompt (the last repeats). Fields, all optional:
//   reply        text of the turn (default "PASS")
//   first_chunk  streamed at once; the rest of `reply` follows after `delay_ms`
//   delay_ms     pause before the rest of the reply and the end of the turn
//   tool_then    text sent after a tool call, i.e. after `reply` (tests reply extraction)
//   permission   {"kind": "edit", "path": "/x"}: ask the client first; the outcome is
//                appended to the reply as "[permission: <option id or cancelled>]"
//   exit         end the process after the first chunk and `delay_ms` (at least 100), mid-turn
//   grandchild   start `sleep 300` and put "[child:<pid>]" in the first chunk
//   fail         after `delay_ms`, answer the prompt with an internal error (v1 only)
//   background_ms  v2 only: the turn ends with one background tool call reported, which
//                ends `background_ms` later (an `idle` state with an empty background list)
// FAKE_TOPIC: reply to topic-proposal prompts (default "the next topic").
// FAKE_TOPIC_DELAY_MS: pause before that reply (default 0).
// FAKE_RATING: the reply to a rating request, verbatim (default: 4 stars for everyone named).
// FAKE_PROTOCOL: "2" speaks only ACP v2 (the prompt response accepts; `state_update` idle
//   ends the turn). Otherwise only v1, which answers a v2 initialize by selecting v1.
// FAKE_AUTH: "1" advertises the agent-run method "fake-login" and refuses session/new until
//   it is used; "broken" accepts the login but still refuses; "nomethod" refuses and
//   advertises nothing.
// FAKE_RESUME (v1 only): "load" (default) advertises session/load and replays one message
//   and one tool call before answering it; "resume" advertises session/resume; "none"
//   advertises neither. v2 always has session/resume (baseline).
// Every session advertises a select option "model" (any value is accepted) and supports
// session/close. Lines "fake-agent: <what>" on stderr record the calls tests check.

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::time::Duration;

use agent_client_protocol::schema::ProtocolVersion;
use agent_client_protocol::v1::schema as s1;
use agent_client_protocol::v2::schema as s2;
use agent_client_protocol::{Agent, Client, Error, Result, Stdio};
use serde::Deserialize;

#[derive(Deserialize, Clone, Default)]
struct Step {
    #[serde(default)]
    reply: String,
    #[serde(default)]
    first_chunk: Option<String>,
    #[serde(default)]
    delay_ms: u64,
    #[serde(default)]
    tool_then: Option<String>,
    #[serde(default)]
    permission: Option<Permission>,
    #[serde(default)]
    exit: bool,
    #[serde(default)]
    grandchild: bool,
    #[serde(default)]
    fail: bool,
    #[serde(default)]
    background_ms: u64,
}

#[derive(Deserialize, Clone, Default)]
struct Permission {
    kind: String,
    path: String,
}

struct Fake {
    script: Vec<Step>,
    topic: String,
    topic_delay_ms: u64,
    count: AtomicUsize,
    auth: String,
    authenticated: AtomicBool,
    resume: String,
}

impl Fake {
    fn from_env() -> Self {
        let var = |name: &str| std::env::var(name).unwrap_or_default();
        Self {
            script: serde_json::from_str(&var("FAKE_SCRIPT")).unwrap_or_default(),
            topic: std::env::var("FAKE_TOPIC").unwrap_or_else(|_| "the next topic".into()),
            topic_delay_ms: std::env::var("FAKE_TOPIC_DELAY_MS").ok().and_then(|v| v.parse().ok()).unwrap_or(0),
            count: AtomicUsize::new(0),
            auth: var("FAKE_AUTH"),
            authenticated: AtomicBool::new(false),
            resume: std::env::var("FAKE_RESUME").unwrap_or_else(|_| "load".into()),
        }
    }

    fn step(&self, prompt: &str) -> Step {
        if prompt.contains("Propose the next topic") {
            return Step { reply: self.topic.clone(), delay_ms: self.topic_delay_ms, ..Step::default() };
        }
        // Rating requests name the other participants ("Rate each other participant by name: A, B."): rate each 4 stars.
        if let (true, Ok(reply)) = (prompt.contains("Rate each other participant by name: "), std::env::var("FAKE_RATING")) {
            return Step { reply, ..Step::default() };
        }
        if let Some(list) = prompt.split("Rate each other participant by name: ").nth(1).and_then(|rest| rest.split(". Give stars").next()) {
            let cards: serde_json::Map<String, serde_json::Value> = list
                .split(", ")
                .map(|name| (name.to_string(), serde_json::json!({"Efficient": 4, "Alert & Aware": 4, "Thorough": 4, "Coordination": 4, "bonus": false})))
                .collect();
            return Step { reply: serde_json::Value::Object(cards).to_string(), ..Step::default() };
        }
        let n = self.count.fetch_add(1, Ordering::SeqCst);
        self.script.get(n).or(self.script.last()).cloned().unwrap_or(Step { reply: "PASS".into(), ..Step::default() })
    }

    /// Whether session/new must be refused for want of authentication.
    fn needs_auth(&self) -> bool {
        match self.auth.as_str() {
            "1" => !self.authenticated.load(Ordering::SeqCst),
            "broken" | "nomethod" => true,
            _ => false,
        }
    }

    fn login(&self, method: &str) {
        eprintln!("fake-agent: authenticated with {method}");
        self.authenticated.store(true, Ordering::SeqCst);
    }

    fn advertises_login(&self) -> bool {
        matches!(self.auth.as_str(), "1" | "broken")
    }
}

fn note(what: impl std::fmt::Display) {
    eprintln!("fake-agent: {what}");
}

/// Where a turn's output goes, in the connection's own version.
#[derive(Clone)]
enum Out {
    V1(agent_client_protocol::v1::ConnectionTo<Client>, s1::SessionId),
    V2(agent_client_protocol::v2::ConnectionTo<Client>, s2::SessionId),
}

impl Out {
    fn chunk(&self, text: String, message: &str) -> Result<()> {
        match self {
            Out::V1(cx, session) => cx.send_notification(s1::SessionNotification::new(
                session.clone(),
                s1::SessionUpdate::AgentMessageChunk(s1::ContentChunk::new(s1::ContentBlock::Text(s1::TextContent::new(text)))),
            )),
            Out::V2(cx, session) => cx.send_notification(s2::UpdateSessionNotification::new(
                session.clone(),
                s2::SessionUpdate::AgentMessageChunk(s2::ContentChunk::new(s2::ContentBlock::Text(s2::TextContent::new(text)), message)),
            )),
        }
    }

    /// v2 only: a snapshot of a whole message, as v2 agents send after streaming it.
    fn snapshot(&self, text: String, message: &str) -> Result<()> {
        match self {
            Out::V1(..) => Ok(()),
            Out::V2(cx, session) => cx.send_notification(s2::UpdateSessionNotification::new(
                session.clone(),
                s2::SessionUpdate::AgentMessage(s2::AgentMessage::new(message).content(vec![s2::ContentBlock::Text(s2::TextContent::new(text))])),
            )),
        }
    }

    fn tool_call(&self) -> Result<()> {
        match self {
            Out::V1(cx, session) => cx.send_notification(s1::SessionNotification::new(
                session.clone(),
                s1::SessionUpdate::ToolCall(s1::ToolCall::new("tool-1", "a tool call").kind(s1::ToolKind::Other)),
            )),
            Out::V2(cx, session) => cx.send_notification(s2::UpdateSessionNotification::new(
                session.clone(),
                s2::SessionUpdate::ToolCallUpdate(s2::ToolCallUpdate::new("tool-1").title("a tool call".to_string()).kind(s2::ToolKind::Other)),
            )),
        }
    }

    fn state(&self, state: s2::StateUpdate) -> Result<()> {
        match self {
            Out::V1(..) => Ok(()),
            Out::V2(cx, session) => cx.send_notification(s2::UpdateSessionNotification::new(session.clone(), s2::SessionUpdate::StateUpdate(state))),
        }
    }

    /// Ask the client for permission; returns the selected option id or "cancelled".
    async fn permission(&self, ask: &Permission) -> Result<String> {
        let title = format!("{} {}", ask.kind, ask.path);
        match self {
            Out::V1(cx, session) => {
                let kind = serde_json::from_value(serde_json::Value::String(ask.kind.clone())).unwrap_or(s1::ToolKind::Other);
                let fields = s1::ToolCallUpdateFields::new().kind(kind).title(title).locations(vec![s1::ToolCallLocation::new(ask.path.clone())]);
                let options = vec![
                    s1::PermissionOption::new("allow-once", "Allow", s1::PermissionOptionKind::AllowOnce),
                    s1::PermissionOption::new("allow-always", "Always allow", s1::PermissionOptionKind::AllowAlways),
                    s1::PermissionOption::new("reject-once", "Reject", s1::PermissionOptionKind::RejectOnce),
                ];
                let request = s1::RequestPermissionRequest::new(session.clone(), s1::ToolCallUpdate::new("perm-1", fields), options);
                let answer = cx.send_request(request).block_task().await?;
                Ok(match answer.outcome {
                    s1::RequestPermissionOutcome::Selected(selected) => selected.option_id.to_string(),
                    _ => "cancelled".into(),
                })
            }
            Out::V2(cx, session) => {
                let kind = serde_json::from_value(serde_json::Value::String(ask.kind.clone())).unwrap_or(s2::ToolKind::Other);
                let tool_call = s2::ToolCallUpdate::new("perm-1").kind(kind).title(title.clone()).locations(vec![s2::ToolCallLocation::new(std::path::PathBuf::from(&ask.path))]);
                let options = vec![
                    s2::PermissionOption::new("allow-once", "Allow", s2::PermissionOptionKind::AllowOnce),
                    s2::PermissionOption::new("allow-always", "Always allow", s2::PermissionOptionKind::AllowAlways),
                    s2::PermissionOption::new("reject-once", "Reject", s2::PermissionOptionKind::RejectOnce),
                ];
                let request = s2::RequestPermissionRequest::new(session.clone(), title, options).subject(s2::RequestPermissionSubject::from(tool_call));
                let answer = cx.send_request(request).block_task().await?;
                Ok(match answer.outcome {
                    s2::RequestPermissionOutcome::Selected(selected) => selected.option_id.to_string(),
                    _ => "cancelled".into(),
                })
            }
        }
    }
}

/// Play one scripted turn's output.
async fn play(step: Step, out: Out) -> Result<()> {
    let mut reply = step.reply.clone();
    if let Some(ask) = &step.permission {
        let picked = out.permission(ask).await?;
        reply = format!("{reply} [permission: {picked}]");
    }
    let mut first = step.first_chunk.clone();
    if step.grandchild {
        let child = std::process::Command::new("sleep").arg("300").spawn().expect("sleep");
        first = Some(format!("[child:{}]", child.id()));
        std::mem::forget(child);
    }
    let mut rest = reply.clone();
    if let Some(first) = &first {
        out.chunk(first.clone(), "m1")?;
        rest = rest.strip_prefix(first.as_str()).unwrap_or(&rest).to_string();
    }
    if step.exit {
        tokio::time::sleep(Duration::from_millis(step.delay_ms.max(100))).await;
        std::process::exit(3);
    }
    tokio::time::sleep(Duration::from_millis(step.delay_ms)).await;
    if !rest.is_empty() {
        out.chunk(rest, "m1")?;
    }
    if !reply.is_empty() {
        out.snapshot(reply, "m1")?;
    }
    if let Some(after) = &step.tool_then {
        out.tool_call()?;
        out.chunk(after.clone(), "m2")?;
    }
    Ok(())
}

fn prompt_text_v1(prompt: &[s1::ContentBlock]) -> String {
    prompt.iter().filter_map(|b| match b {
        s1::ContentBlock::Text(t) => Some(t.text.clone()),
        _ => None,
    }).collect()
}

fn prompt_text_v2(prompt: &[s2::ContentBlock]) -> String {
    prompt.iter().filter_map(|b| match b {
        s2::ContentBlock::Text(t) => Some(t.text.clone()),
        _ => None,
    }).collect()
}

fn model_v1(current: &str) -> Vec<s1::SessionConfigOption> {
    let choices = vec![s1::SessionConfigSelectOption::new("fast", "Fast"), s1::SessionConfigSelectOption::new("smart", "Smart")];
    vec![s1::SessionConfigOption::select("model", "Model", current.to_string(), choices)]
}

fn model_v2(current: &str) -> Vec<s2::SessionConfigOption> {
    let choices = vec![s2::SessionConfigSelectOption::new("fast", "Fast"), s2::SessionConfigSelectOption::new("smart", "Smart")];
    vec![s2::SessionConfigOption::select("model", "Model", current.to_string(), choices)]
}

#[tokio::main]
async fn main() -> Result<()> {
    let fake = Arc::new(Fake::from_env());
    if std::env::var("FAKE_PROTOCOL").as_deref() == Ok("2") { run_v2(fake).await } else { run_v1(fake).await }
}

async fn run_v1(fake: Arc<Fake>) -> Result<()> {
    let (f1, f2, f3, f4) = (fake.clone(), fake.clone(), fake.clone(), fake.clone());
    Agent
        .v1()
        .name("fake-agent")
        .on_receive_request(
            async move |init: s1::InitializeRequest, responder, _cx| {
                let mut sessions = s1::SessionCapabilities::new().close(s1::SessionCloseCapabilities::new());
                if f1.resume == "resume" {
                    sessions = sessions.resume(s1::SessionResumeCapabilities::new());
                }
                let capabilities = s1::AgentCapabilities::new()
                    .mcp_capabilities(s1::McpCapabilities::new().http(true))
                    .load_session(f1.resume == "load")
                    .session_capabilities(sessions);
                let mut response = s1::InitializeResponse::new(init.protocol_version).agent_capabilities(capabilities);
                if f1.advertises_login() {
                    response = response.auth_methods(vec![s1::AuthMethod::Agent(s1::AuthMethodAgent::new("fake-login", "Fake login"))]);
                }
                responder.respond(response)
            },
            agent_client_protocol::on_receive_request!(),
        )
        .on_receive_request(
            async move |request: s1::AuthenticateRequest, responder, _cx| {
                f2.login(&request.method_id.to_string());
                responder.respond(s1::AuthenticateResponse::new())
            },
            agent_client_protocol::on_receive_request!(),
        )
        .on_receive_request(
            async move |_new: s1::NewSessionRequest, responder, _cx| {
                if f3.needs_auth() {
                    return responder.respond_with_error(Error::auth_required());
                }
                responder.respond(s1::NewSessionResponse::new(session_id()).config_options(model_v1("fast")))
            },
            agent_client_protocol::on_receive_request!(),
        )
        .on_receive_request(
            async move |request: s1::SetSessionConfigOptionRequest, responder, _cx| {
                note(format_args!("set {}", request.config_id));
                match request.value.as_value_id() {
                    Some(value) if request.config_id.to_string() == "model" => responder.respond(s1::SetSessionConfigOptionResponse::new(model_v1(&value.to_string()))),
                    _ => responder.respond_with_error(Error::invalid_params()),
                }
            },
            agent_client_protocol::on_receive_request!(),
        )
        .on_receive_request(
            async move |request: s1::CloseSessionRequest, responder, _cx| {
                note(format_args!("closed {}", request.session_id));
                responder.respond(s1::CloseSessionResponse::new())
            },
            agent_client_protocol::on_receive_request!(),
        )
        .on_receive_request(
            async move |request: s1::LoadSessionRequest, responder, cx| {
                note(format_args!("loaded {}", request.session_id));
                let out = Out::V1(cx, request.session_id.clone());
                out.chunk("replayed history".into(), "")?;
                out.tool_call()?;
                responder.respond(s1::LoadSessionResponse::new().config_options(model_v1("fast")))
            },
            agent_client_protocol::on_receive_request!(),
        )
        .on_receive_request(
            async move |request: s1::ResumeSessionRequest, responder, _cx| {
                note(format_args!("resumed {}", request.session_id));
                responder.respond(s1::ResumeSessionResponse::new().config_options(model_v1("fast")))
            },
            agent_client_protocol::on_receive_request!(),
        )
        .on_receive_request(
            async move |prompt: s1::PromptRequest, responder, cx| {
                let step = f4.step(&prompt_text_v1(&prompt.prompt));
                let out = Out::V1(cx.clone(), prompt.session_id.clone());
                // v1: the turn ends with the prompt response.
                cx.spawn(async move {
                    let fail = step.fail;
                    play(step, out).await?;
                    if fail {
                        return responder.respond_with_error(Error::internal_error());
                    }
                    responder.respond(s1::PromptResponse::new(s1::StopReason::EndTurn))
                })
            },
            agent_client_protocol::on_receive_request!(),
        )
        .connect_to(Stdio::new())
        .await
}

async fn run_v2(fake: Arc<Fake>) -> Result<()> {
    let (f1, f2, f3, f4) = (fake.clone(), fake.clone(), fake.clone(), fake.clone());
    Agent
        .v2()
        .name("fake-agent")
        .on_receive_request(
            async move |_init: s2::InitializeRequest, responder, _cx| {
                let session = s2::SessionCapabilities::new().mcp(s2::McpCapabilities::new().http(s2::McpHttpCapabilities::new()));
                let mut response = s2::InitializeResponse::new(ProtocolVersion::V2, s2::Implementation::new("fake-agent", "0"))
                    .capabilities(s2::AgentCapabilities::new().session(session));
                if f1.advertises_login() {
                    response = response.auth_methods(vec![s2::AuthMethod::Agent(s2::AuthMethodAgent::new("fake-login", "Fake login"))]);
                }
                responder.respond(response)
            },
            agent_client_protocol::on_receive_request!(),
        )
        .on_receive_request(
            async move |request: s2::LoginAuthRequest, responder, _cx| {
                f2.login(&request.method_id.to_string());
                responder.respond(s2::LoginAuthResponse::new())
            },
            agent_client_protocol::on_receive_request!(),
        )
        .on_receive_request(
            async move |_new: s2::NewSessionRequest, responder, cx| {
                if f3.needs_auth() {
                    return responder.respond_with_error(Error::auth_required());
                }
                responder.respond(s2::NewSessionResponse::new(session_id()).config_options(model_v2("fast")))?;
                // A new session is idle: a stale idle the client must not take as a turn's end.
                Out::V2(cx, session_id().into()).state(s2::StateUpdate::Idle(s2::IdleStateUpdate::new()))
            },
            agent_client_protocol::on_receive_request!(),
        )
        .on_receive_request(
            async move |request: s2::SetSessionConfigOptionRequest, responder, _cx| {
                note(format_args!("set {}", request.config_id));
                match request.value.as_id() {
                    Some(value) if request.config_id.to_string() == "model" => responder.respond(s2::SetSessionConfigOptionResponse::new(model_v2(&value.to_string()))),
                    _ => responder.respond_with_error(Error::invalid_params()),
                }
            },
            agent_client_protocol::on_receive_request!(),
        )
        .on_receive_request(
            async move |request: s2::CloseSessionRequest, responder, _cx| {
                note(format_args!("closed {}", request.session_id));
                responder.respond(s2::CloseSessionResponse::new())
            },
            agent_client_protocol::on_receive_request!(),
        )
        .on_receive_request(
            async move |request: s2::ResumeSessionRequest, responder, _cx| {
                note(format_args!("resumed {}", request.session_id));
                responder.respond(s2::ResumeSessionResponse::new().config_options(model_v2("fast")))
            },
            agent_client_protocol::on_receive_request!(),
        )
        .on_receive_request(
            async move |prompt: s2::PromptRequest, responder, cx| {
                let step = f4.step(&prompt_text_v2(&prompt.prompt));
                let out = Out::V2(cx.clone(), prompt.session_id.clone());
                // v2: the response only accepts the prompt; `idle` ends the turn.
                responder.respond(s2::PromptResponse::new("user-1"))?;
                cx.spawn(async move {
                    let background = step.background_ms;
                    out.state(s2::StateUpdate::Running(s2::RunningStateUpdate::new()))?;
                    play(step, out.clone()).await?;
                    if background == 0 {
                        return out.state(s2::StateUpdate::Idle(s2::IdleStateUpdate::new().stop_reason(s2::StopReason::EndTurn)));
                    }
                    let work = vec![s2::BackgroundWork::ToolCall(s2::BackgroundToolCall::new("bg-1"))];
                    out.state(s2::StateUpdate::Idle(s2::IdleStateUpdate::new().stop_reason(s2::StopReason::EndTurn).background(work)))?;
                    tokio::time::sleep(std::time::Duration::from_millis(background)).await;
                    out.state(s2::StateUpdate::Idle(s2::IdleStateUpdate::new().background(Vec::new())))
                })
            },
            agent_client_protocol::on_receive_request!(),
        )
        .connect_to(Stdio::new())
        .await
}

/// The session id this fake hands out: FAKE_SESSION, or one unique to this process.
fn session_id() -> String {
    std::env::var("FAKE_SESSION").unwrap_or_else(|_| format!("fake-session-{}", std::process::id()))
}
