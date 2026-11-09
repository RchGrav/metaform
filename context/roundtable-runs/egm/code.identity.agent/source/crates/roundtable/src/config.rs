//! What a Roundtable needs to start.

use std::path::PathBuf;

use acp_host::LaunchSpec;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SeatConfig {
    /// Display name, unique within the table.
    pub name: String,
    /// Harness catalog id or label, for display.
    pub harness: String,
    pub launch: LaunchSpec,
    /// Advertised session options to set, in order (e.g. mode, then model). A setting that
    /// fails is a loud error and the seat still joins (O: fail loudly; no gates).
    #[serde(default)]
    pub settings: Vec<(String, String)>,
    /// Give this seat's agent the table's OpenRouter key as OPENROUTER_API_KEY (needed by
    /// OpenRouter-model harnesses such as Pi). Off by default: agents never see the key.
    #[serde(default)]
    pub share_openrouter_key: bool,
    /// Resume this earlier session instead of opening a new one, so the agent keeps its
    /// identity: its genesis name follows from its first session's id, and "a resumed session
    /// keeps its name" (owner, archaeology/rich/technical/agent_identity.md). The harness must
    /// be the one that holds that session.
    #[serde(default)]
    pub resume_session: Option<String>,
}

/// What a participant's identity has earned at earlier tables.
#[derive(Debug, Clone, PartialEq)]
pub struct Profile {
    /// Cumulative points from every rating received.
    pub score: f64,
    /// How many peer ratings it has received.
    pub ratings: u64,
    /// How many tables it was rated at.
    pub sessions: u64,
}

/// Where identity profiles are kept. The core only reads them (for the owner's
/// `session_profile` and `session_results` messages); the host stores them, for example by
/// saving each `roundtable.rating` event.
pub trait Identities: Send + Sync {
    /// The profile for the identity whose genesis session is `session`; `Ok(None)` when it has
    /// none yet. `Err` is shown loudly. Profiles are keyed by session, not by name: the name is
    /// derived from the session, and two sessions can derive the same name.
    fn profile(&self, session: &str) -> Result<Option<Profile>, String>;
}

/// Environment variables holding Roundtable's own secrets, removed from every agent. A seat
/// can opt back into `OPENROUTER_API_KEY` only ([`SeatConfig::share_openrouter_key`]); the
/// chair credential (`ROUNDTABLE_TOKEN`) never reaches an agent.
pub const SECRET_ENV: [&str; 3] = ["OPENROUTER_API_KEY", "TYPESAFE_API_KEY", "ROUNDTABLE_TOKEN"];

impl SeatConfig {
    /// The launch specification for this seat: its harness command with Roundtable's secrets
    /// removed from the inherited environment, plus the OpenRouter key when the seat opted in
    /// and one is set. Returns a warning when it opted in without a key to share.
    pub fn launch_spec(&self, openrouter_key: Option<String>) -> (acp_host::LaunchSpec, Option<String>) {
        let mut launch = self.launch.clone();
        for name in SECRET_ENV {
            launch.env.remove(name);
            if !launch.env_remove.iter().any(|n| n == name) {
                launch.env_remove.push(name.to_string());
            }
        }
        let mut warning = None;
        if self.share_openrouter_key {
            match openrouter_key {
                // acp-host applies removals to the inherited environment before explicit
                // variables, so this explicit key reaches the agent.
                Some(key) => {
                    launch.env.insert("OPENROUTER_API_KEY".into(), key);
                }
                None => warning = Some("asked for the OpenRouter key, but none is set".into()),
            }
        }
        (launch, warning)
    }
}

/// Why a configuration cannot start a table.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ConfigError(pub String);

impl std::fmt::Display for ConfigError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

impl std::error::Error for ConfigError {}

/// A seat name: 1 to 40 letters, digits, spaces, `_`, `-` or `.`, not starting or ending
/// with a space. Names are identities in events, records and the tools URL.
pub fn valid_seat_name(name: &str) -> bool {
    (1..=40).contains(&name.chars().count())
        && name.trim() == name
        && name.chars().all(|c| c.is_alphanumeric() || matches!(c, ' ' | '_' | '-' | '.'))
}

impl TableConfig {
    /// Check the invariants every host relies on.
    pub fn validate(&self) -> Result<(), ConfigError> {
        if self.objective.trim().is_empty() {
            return Err(ConfigError("the objective is empty".into()));
        }
        if self.seats.is_empty() {
            return Err(ConfigError("a table needs at least one seat".into()));
        }
        if self.base_allowance == Some(0) || self.recovery_allowance == 0 {
            return Err(ConfigError("the reply limits must be at least 1 character".into()));
        }
        if self.rounds == Some(0) {
            return Err(ConfigError("a table needs at least one round".into()));
        }
        let mut seen = std::collections::HashSet::new();
        for seat in &self.seats {
            if !valid_seat_name(&seat.name) {
                return Err(ConfigError(format!(
                    "seat name {:?} must be 1-40 letters, digits, spaces, '_', '-' or '.'",
                    seat.name
                )));
            }
            if !seen.insert(seat.name.to_lowercase()) {
                return Err(ConfigError(format!("two seats are named {:?}", seat.name)));
            }
        }
        Ok(())
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TableConfig {
    /// The user's objective. Governs the whole collaboration.
    pub objective: String,
    /// The first topic. Defaults to the objective.
    #[serde(default)]
    pub topic: Option<String>,
    /// The shared working directory every participant's session starts in.
    pub workspace: PathBuf,
    /// Root that permission requests are checked against; defaults to the workspace.
    #[serde(default)]
    pub scope: Option<PathBuf>,
    pub seats: Vec<SeatConfig>,
    #[serde(default = "default_true")]
    pub judging: bool,
    /// Topics: the next-topic poll and the `advance` tool. Off by default: the table works on
    /// the objective it was sent (owner). On, they also need JEV.
    #[serde(default)]
    pub topics: bool,
    /// The reply limit in characters, or `None` for no limit (the default, the owner's length
    /// experiment). A message over the limit is blocked, never cut (owner). The chair sets it;
    /// agents cannot change it (O).
    #[serde(default)]
    pub base_allowance: Option<usize>,
    /// The limit for the one reply after an agent was skipped while busy (owner's spec).
    #[serde(default = "default_recovery")]
    pub recovery_allowance: usize,
    /// How many rounds the table runs before it ends (owner: 10). `None` is no limit: the mode
    /// where agents keep collaborating and building.
    #[serde(default = "default_rounds")]
    pub rounds: Option<u64>,
}

fn default_recovery() -> usize {
    crate::rules::DEFAULT_RECOVERY
}

fn default_rounds() -> Option<u64> {
    Some(crate::rules::DEFAULT_ROUNDS)
}

fn default_true() -> bool {
    true
}

/// How a host offers the participant tools (`advance`, `feedback`) to agents. Roundtable
/// builds the URL per seat; the host serves it and forwards calls to [`crate::TableHandle`].
#[derive(Debug, Clone)]
pub struct ToolsEndpoint {
    /// Base URL, e.g. `http://127.0.0.1:4180/mcp`. Seats get `{base}/{table}/{seat}`, with their
    /// own token as an `Authorization: Bearer` header.
    pub base_url: String,
}

/// Sensible session settings for well-known harnesses, so permission requests reach the
/// Roundtable's scope policy (Claude: mode `default`, which asks for each permission) or an OS sandbox confines writes to the
/// workspace (Codex: workspace-write).
/// Environment a catalog harness needs so its permission requests reach Roundtable, which
/// approves inside the workspace and refuses outside it (builder policy, T I-1; open with the
/// owner, audit B28).
/// OpenCode reads its configuration from `OPENCODE_CONFIG_CONTENT`; with every permission set
/// to "ask" it sends each one to the ACP client instead of acting on its own (verified live:
/// a write outside the workspace was asked for, refused, and not made).
pub fn default_env(harness_id: &str) -> Vec<(String, String)> {
    match harness_id {
        "opencode" | "opencode-v2" => vec![(
            PERMISSION_ROUTING_ENV[0].into(),
            r#"{"permission":{"edit":"ask","bash":"ask","webfetch":"ask","external_directory":"ask"}}"#.into(),
        )],
        _ => Vec::new(),
    }
}

/// Environment variables that, when set for a seat, route its permission requests to
/// Roundtable in place of a session mode (see [`default_env`]).
pub const PERMISSION_ROUTING_ENV: [&str; 1] = ["OPENCODE_CONFIG_CONTENT"];

pub fn default_settings(harness_id: &str) -> Vec<(String, String)> {
    match harness_id {
        "claude-acp" => vec![("mode".into(), "default".into())],
        "codex-acp" => vec![("mode".into(), "workspace-write".into())],
        _ => Vec::new(),
    }
}
