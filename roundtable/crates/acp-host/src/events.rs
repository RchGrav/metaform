//! Events `acp-host` publishes. Every state change of a harness, a session or a prompt is
//! one of these, so consumers await events instead of polling.

use serde::Serialize;

use bus::Event;

/// Caller-chosen instance name of one launched harness (Roundtable uses `<table>/<seat>`).
/// Not a harness catalog id such as `opencode`.
pub type HarnessId = String;
/// The agent's ACP session id.
pub type SessionId = String;
/// Sequence number of a prompt within one `acp-host` process.
pub type PromptId = u64;

#[derive(Debug, Clone, Serialize)]
pub struct HarnessStarted {
    pub harness: HarnessId,
    pub label: String,
    pub command: String,
    pub pid: Option<u32>,
    /// The ACP version negotiated for this connection (1 or 2). Every message on it uses
    /// that version's schema and semantics.
    pub protocol_version: u16,
    /// Why this connection uses v1: v2 was offered first and the agent declined it, so the
    /// harness was restarted fresh on v1. `None` when v2 was accepted.
    pub v1_fallback: Option<String>,
    pub agent_name: Option<String>,
    pub agent_version: Option<String>,
    pub mcp_http: bool,
    pub load_session: bool,
}
impl Event for HarnessStarted {
    const NAME: &'static str = "acp.harness.started";
}

/// The harness process ended, for any reason.
#[derive(Debug, Clone, Serialize)]
pub struct HarnessExited {
    pub harness: HarnessId,
    pub code: Option<i32>,
    /// Last lines the process wrote to stderr, for diagnosis.
    pub stderr_tail: String,
    /// The error the ACP connection ended with, if it ended with one.
    pub connection_error: Option<String>,
}
impl Event for HarnessExited {
    const NAME: &'static str = "acp.harness.exited";
}

/// One selectable value of a session configuration option.
#[derive(Debug, Clone, Serialize)]
pub struct ConfigChoice {
    pub value: String,
    pub name: String,
}

/// A configuration option the agent advertised for a session (model, mode, ...).
#[derive(Debug, Clone, Serialize)]
pub struct ConfigOption {
    pub id: String,
    pub name: String,
    pub category: Option<String>,
    pub current: Option<String>,
    pub choices: Vec<ConfigChoice>,
}

#[derive(Debug, Clone, Serialize)]
pub struct SessionOpened {
    pub harness: HarnessId,
    pub session: SessionId,
    pub cwd: String,
    pub config_options: Vec<ConfigOption>,
}
impl Event for SessionOpened {
    const NAME: &'static str = "acp.session.opened";
}

/// A configuration option was set, by the client or reported by the agent.
#[derive(Debug, Clone, Serialize)]
pub struct ConfigChanged {
    pub harness: HarnessId,
    pub session: SessionId,
    pub config_options: Vec<ConfigOption>,
}
impl Event for ConfigChanged {
    const NAME: &'static str = "acp.session.config";
}

#[derive(Debug, Clone, Serialize)]
pub struct PromptSent {
    pub harness: HarnessId,
    pub session: SessionId,
    pub prompt: PromptId,
    /// The full text sent, so the record holds what each agent actually received.
    pub text: String,
}
impl Event for PromptSent {
    const NAME: &'static str = "acp.prompt.sent";
}

/// A piece of the agent's visible reply (or of its reasoning, when `thought`).
///
/// Normally `text` continues what was published before. ACP v2 updates are upserts keyed by
/// message: when the agent replaces a message's content with something that does not simply
/// extend it, `replace` is true and `text` is that message's whole new content.
#[derive(Debug, Clone, Serialize)]
pub struct AgentText {
    pub harness: HarnessId,
    pub session: SessionId,
    pub prompt: Option<PromptId>,
    pub text: String,
    pub thought: bool,
    /// The ACP v2 message id. `None` on a v1 connection.
    pub message: Option<String>,
    pub replace: bool,
}
impl Event for AgentText {
    const NAME: &'static str = "acp.agent.text";
}

#[derive(Debug, Clone, Serialize)]
pub struct ToolActivity {
    pub harness: HarnessId,
    pub session: SessionId,
    pub prompt: Option<PromptId>,
    pub tool_call: String,
    pub title: Option<String>,
    pub kind: Option<String>,
    pub status: Option<String>,
    pub locations: Vec<String>,
}
impl Event for ToolActivity {
    const NAME: &'static str = "acp.agent.tool";
}

/// The agent finished a prompt turn: on v1 the `session/prompt` response, on v2 the session
/// reporting `idle` after it was active.
#[derive(Debug, Clone, Serialize)]
pub struct PromptCompleted {
    pub harness: HarnessId,
    pub session: SessionId,
    pub prompt: PromptId,
    pub stop_reason: String,
    /// All agent message text of the turn, in order. Separate blocks (text either side of a
    /// tool call on v1, separate messages on v2) are joined by a blank line.
    pub reply: String,
    /// The turn's last non-empty block: what the agent said once it had finished (after its
    /// last tool call). Narration before tool calls ("Let me read the file") is not in it.
    pub final_message: String,
}
impl Event for PromptCompleted {
    const NAME: &'static str = "acp.prompt.completed";
}

/// The prompt turn ended with an error instead of a stop reason (on v2 also: the prompt was
/// not accepted, or the turn stopped with the `error` stop reason).
#[derive(Debug, Clone, Serialize)]
pub struct PromptFailed {
    pub harness: HarnessId,
    pub session: SessionId,
    pub prompt: PromptId,
    pub error: String,
}
impl Event for PromptFailed {
    const NAME: &'static str = "acp.prompt.failed";
}

/// How a permission request from an agent was answered.
#[derive(Debug, Clone, Serialize)]
pub struct PermissionDecided {
    pub harness: HarnessId,
    pub session: SessionId,
    pub title: Option<String>,
    pub kind: Option<String>,
    pub locations: Vec<String>,
    pub allowed: bool,
    pub reason: String,
}
impl Event for PermissionDecided {
    const NAME: &'static str = "acp.permission";
}

/// Foreground state of an ACP v2 session, from its `state_update`. Only `idle` means the
/// foreground work is done; any other state, including one this host does not know, means
/// it is still active.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ForegroundState {
    Running,
    Idle,
    RequiresAction,
    /// A state this host does not know, by the name the agent sent.
    Other(String),
}

/// An ACP v2 session reported its state. `prompt` is the turn in progress, if any.
#[derive(Debug, Clone, Serialize)]
pub struct AgentState {
    pub harness: HarnessId,
    pub session: SessionId,
    pub prompt: Option<PromptId>,
    pub state: ForegroundState,
    /// Sent with `idle`.
    pub stop_reason: Option<String>,
    /// How many items of background work the agent reports. `None`: not reported, which D §5.2
    /// says is not proof that nothing is running.
    pub background: Option<usize>,
}
impl Event for AgentState {
    const NAME: &'static str = "acp.agent.state";
}

/// An existing session was reopened on this connection.
#[derive(Debug, Clone, Serialize)]
pub struct SessionResumed {
    pub harness: HarnessId,
    pub session: SessionId,
    pub cwd: String,
    /// The ACP method used: `session/resume` or `session/load`.
    pub method: String,
    pub config_options: Vec<ConfigOption>,
}
impl Event for SessionResumed {
    const NAME: &'static str = "acp.session.resumed";
}

/// `session/close` was sent during shutdown. `error` is set when the agent refused it.
#[derive(Debug, Clone, Serialize)]
pub struct SessionClosed {
    pub harness: HarnessId,
    pub session: SessionId,
    pub error: Option<String>,
}
impl Event for SessionClosed {
    const NAME: &'static str = "acp.session.closed";
}

/// The agent required authentication and it was completed with an advertised method.
#[derive(Debug, Clone, Serialize)]
pub struct Authenticated {
    pub harness: HarnessId,
    /// The ACP method used: `authenticate` (v1) or `auth/login` (v2).
    pub call: String,
    pub method: String,
}
impl Event for Authenticated {
    const NAME: &'static str = "acp.harness.authenticated";
}
