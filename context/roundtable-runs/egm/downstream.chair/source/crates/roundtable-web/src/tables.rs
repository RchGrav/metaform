//! Creating tables from a request and turning chair actions into commands.

use std::path::PathBuf;

use anyhow::{Context, Result, anyhow, bail};
use roundtable::jev::Jev;
use roundtable::{Command, SeatConfig, TableConfig, ToolsEndpoint};
use serde::Deserialize;
use serde_json::Value;

use crate::app::AppState;

#[derive(Debug, Deserialize)]
pub struct CreateTable {
    pub objective: String,
    #[serde(default)]
    pub topic: Option<String>,
    pub workspace: PathBuf,
    #[serde(default)]
    pub scope: Option<PathBuf>,
    #[serde(default = "yes")]
    pub judging: bool,
    /// The reply limit (the chair's setting); null or absent for no limit.
    #[serde(default)]
    pub base_allowance: Option<usize>,
    /// The limit for the one reply after a busy skip (default 1,024).
    #[serde(default = "recovery")]
    pub recovery_allowance: usize,
    /// Rounds before the table ends (default 10); null for no limit.
    #[serde(default = "rounds")]
    pub rounds: Option<u64>,
    /// Topics on or off (default off).
    #[serde(default)]
    pub topics: bool,
    pub seats: Vec<SeatRequest>,
}

fn recovery() -> usize {
    roundtable::rules::DEFAULT_RECOVERY
}

fn rounds() -> Option<u64> {
    Some(roundtable::rules::DEFAULT_ROUNDS)
}

fn yes() -> bool {
    true
}

#[derive(Debug, Deserialize)]
pub struct SeatRequest {
    pub name: String,
    /// A catalog id from /api/harnesses ...
    #[serde(default)]
    pub harness: Option<String>,
    /// ... or a full ACP command line (chair only: the API is behind the chair token).
    #[serde(default)]
    pub command: Option<String>,
    /// Shorthand for the `model` session option.
    #[serde(default)]
    pub model: Option<String>,
    /// Extra session options, applied after the harness defaults.
    #[serde(default)]
    pub settings: Vec<(String, String)>,
    /// Resume this earlier session so the agent keeps its identity (see `SeatConfig`).
    #[serde(default)]
    pub resume_session: Option<String>,
    /// Give this agent the OpenRouter key (for OpenRouter-model harnesses such as Pi).
    #[serde(default)]
    pub share_openrouter_key: bool,
}

/// The harnesses a table can seat: ACP autoselection plus the OpenRouter Agent SDK adapter
/// built in this repository (R §9.4, D §7.3 path 2). Listing and table creation both use this,
/// so anything the page offers can be launched.
pub async fn catalog(http: &reqwest::Client) -> (Vec<acp_host::HarnessEntry>, Option<String>) {
    let (mut entries, note) = acp_host::launch::autoselect(http).await;
    entries.insert(0, openrouter_adapter());
    (entries, note)
}

fn openrouter_adapter() -> acp_host::HarnessEntry {
    const ID: &str = "openrouter-acp";
    const NAME: &str = "OpenRouter (Agent SDK)";
    let script = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../adapters/openrouter-acp/dist/index.js");
    // Always an entry: the page shows an unavailable adapter with its reason rather than
    // silently omitting it.
    let mut entry = acp_host::launch::custom(ID, NAME, "node").expect("a bare command parses");
    match script.canonicalize() {
        // Command plus argument vector, so a checkout path containing spaces still launches.
        Ok(script) => entry.launch = Some(acp_host::LaunchSpec::new("node", [script.display().to_string()])),
        Err(error) => {
            entry.launch = None;
            entry.available = false;
            entry.note = Some(format!("{} is missing ({error}); run `npm ci && npm run build` in adapters/openrouter-acp", script.display()));
        }
    }
    entry
}

pub async fn create(state: &AppState, request: CreateTable) -> Result<String> {
    let mut entries = None;
    let mut seats = Vec::new();
    for seat in request.seats {
        let name = seat.name.trim().to_string();
        let (label, launch, mut settings) = match (&seat.command, &seat.harness) {
            (Some(command), _) if !command.trim().is_empty() => {
                (command.clone(), acp_host::LaunchSpec::from_command_line(command)?, Vec::new())
            }
            (_, Some(id)) => {
                if entries.is_none() {
                    entries = Some(catalog(&state.http).await.0);
                }
                let entry = entries.as_ref().unwrap().iter().find(|e| &e.id == id).with_context(|| format!("unknown harness {id}"))?;
                let mut launch = entry.launch.clone().with_context(|| format!("{id} cannot be launched here: {}", entry.note.clone().unwrap_or_default()))?;
                for (key, value) in roundtable::default_env(id) {
                    launch.env.entry(key).or_insert(value);
                }
                (id.clone(), launch, roundtable::default_settings(id))
            }
            _ => bail!("seat {name:?} needs a harness or a command"),
        };
        settings.extend(seat.settings);
        if let Some(model) = seat.model.filter(|m| !m.trim().is_empty()) {
            settings.push(("model".into(), model));
        }
        let resume_session = seat.resume_session.filter(|id| !id.trim().is_empty());
        seats.push(SeatConfig { name, harness: label, launch, settings, share_openrouter_key: seat.share_openrouter_key, resume_session });
    }

    let id = format!("t{}", &roundtable::random_hex()[..12]);
    let workspace = if request.workspace.is_absolute() { request.workspace } else { std::env::current_dir()?.join(request.workspace) };
    let config = TableConfig {
        objective: request.objective,
        topic: request.topic,
        workspace,
        scope: request.scope,
        seats,
        judging: request.judging,
        topics: request.topics,
        base_allowance: request.base_allowance,
        recovery_allowance: request.recovery_allowance,
        rounds: request.rounds,
    };
    // The core validates names, uniqueness and the objective; every host gets the same rules.
    config.validate().map_err(|e| anyhow!(e))?;
    roundtable::record::spawn_recorder(&state.bus, id.clone(), &state.data_dir.join("tables").join(&id).join("record.jsonl"))?;
    let key = state.openrouter_key.lock().unwrap().clone();
    let jev = Jev::new(state.http.clone(), key);
    let tools = ToolsEndpoint { base_url: format!("http://{}/mcp", state.addr) };
    let identities: std::sync::Arc<dyn roundtable::Identities> = std::sync::Arc::new(crate::app::FileIdentities { dir: state.data_dir.join("identities") });
    let handle = roundtable::spawn_with(id.clone(), config, state.bus.clone(), jev, Some(tools), Some(identities)).map_err(|e| anyhow!(e))?;
    state.tables.lock().unwrap().insert(id.clone(), handle);
    Ok(id)
}

pub fn command(body: &Value) -> Result<Command> {
    let text = || body.get("text").and_then(Value::as_str).map(str::to_string);
    Ok(match body.get("kind").and_then(Value::as_str).unwrap_or_default() {
        "hold" => Command::Hold,
        "resume" => Command::Resume,
        "guidance" => Command::Guidance(text().filter(|t| !t.trim().is_empty()).context("guidance needs text")?),
        "judging" => Command::SetJudging(body.get("on").and_then(Value::as_bool).context("judging needs on")?),
        "advance" => Command::Advance { by: "the chair".into(), topic: text() },
        "end" => Command::End,
        other => bail!("unknown command {other:?}"),
    })
}

#[cfg(test)]
mod catalog_tests {
    // F (SC1): the adapter the page lists must be one table creation can launch.
    #[test]
    fn openrouter_adapter_is_launchable_or_says_why() {
        let entry = super::openrouter_adapter();
        assert_eq!(entry.id, "openrouter-acp");
        match &entry.launch {
            Some(launch) => {
                assert!(entry.available);
                assert_eq!(launch.command, "node");
                assert!(launch.args[0].ends_with("adapters/openrouter-acp/dist/index.js"), "{:?}", launch.args);
            }
            None => assert!(!entry.available && entry.note.as_deref().is_some_and(|n| n.contains("npm run build"))),
        }
    }
}
