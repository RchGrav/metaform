//! ACP autoselection: find the harnesses that can be launched here and how to launch them.
//!
//! Sources, in order: the official ACP Registry, a built-in catalog of common harnesses (used
//! when the registry cannot be reached), and any command the user supplies. The registry is
//! not a detector of every program on the machine; a user-supplied command covers the rest.

use std::collections::BTreeMap;

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};

pub const REGISTRY_URL: &str = "https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json";

/// How to start one ACP agent process.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct LaunchSpec {
    pub command: String,
    #[serde(default)]
    pub args: Vec<String>,
    /// Variables set for the child, on top of the inherited environment.
    #[serde(default)]
    pub env: BTreeMap<String, String>,
    /// Inherited variables removed from the child's environment.
    #[serde(default)]
    pub env_remove: Vec<String>,
    /// At shutdown, after stdin is closed: true signals the process group if the agent has not
    /// exited within the grace periods (SIGTERM, then SIGKILL); false waits for it to exit on
    /// its own and sends no signal.
    #[serde(default = "force_stop_default")]
    pub force_stop: bool,
}

fn force_stop_default() -> bool {
    true
}

impl LaunchSpec {
    pub fn new(command: impl Into<String>, args: impl IntoIterator<Item = impl Into<String>>) -> Self {
        Self {
            command: command.into(),
            args: args.into_iter().map(Into::into).collect(),
            env: BTreeMap::new(),
            env_remove: Vec::new(),
            force_stop: true,
        }
    }

    /// Parse a shell-like command line ("npx -y pkg --acp"). Quotes group words.
    pub fn from_command_line(line: &str) -> Result<Self> {
        let words = split_words(line).context("unbalanced quotes in command")?;
        let (command, args) = words.split_first().context("empty command")?;
        Ok(Self::new(command.clone(), args.to_vec()))
    }

    pub fn display(&self) -> String {
        std::iter::once(self.command.as_str())
            .chain(self.args.iter().map(String::as_str))
            .collect::<Vec<_>>()
            .join(" ")
    }
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Source {
    Registry,
    Builtin,
    Custom,
}

/// A harness that autoselection found.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HarnessEntry {
    pub id: String,
    pub name: String,
    pub version: Option<String>,
    pub description: Option<String>,
    pub source: Source,
    pub launch: Option<LaunchSpec>,
    /// Whether the launcher it needs (npx, uvx, a binary) is on this machine.
    pub available: bool,
    /// Why it is unavailable, when it is.
    pub note: Option<String>,
}

/// Common harnesses, used when the registry is unreachable. Every version is pinned so a
/// launch is reproducible; the registry supplies newer ones when online.
pub fn builtin() -> Vec<HarnessEntry> {
    let npx = |id: &str, name: &str, package: &str, extra: &[&str]| {
        let mut args = vec!["-y".to_string(), package.to_string()];
        args.extend(extra.iter().map(|arg| arg.to_string()));
        entry(id, name, None, None, Source::Builtin, Some(LaunchSpec::new("npx", args)))
    };
    vec![
        npx("claude-acp", "Claude Code", "@agentclientprotocol/claude-agent-acp@0.101.0", &[]),
        npx("codex-acp", "OpenAI Codex", "@agentclientprotocol/codex-acp@2.5.0", &[]),
        npx("pi-acp", "Pi", "pi-acp@0.0.34", &[]),
        npx("opencode", "OpenCode", "opencode-ai@1.19.5", &["acp"]),
    ]
}

/// Read the ACP Registry document into entries. D §7.1: "`acpr` resolves registry distribution
/// types and launches the agent", so every registry entry starts through `acpr` when it is
/// installed. A binary the user already installed is the exception: it runs from PATH (see
/// `parse_registry_with`).
pub fn parse_registry(document: &serde_json::Value) -> Vec<HarnessEntry> {
    parse_registry_with(document, which::which("acpr").is_ok())
}

/// [`parse_registry`] with `acpr`'s presence given. Without `acpr`, npx and uvx entries start
/// with the registry's own package and arguments, and each says so in its note; a binary entry
/// that is not installed is unavailable.
pub fn parse_registry_with(document: &serde_json::Value, acpr: bool) -> Vec<HarnessEntry> {
    let Some(agents) = document.get("agents").and_then(|value| value.as_array()) else {
        return Vec::new();
    };
    agents
        .iter()
        .filter_map(|agent| {
            let text = |key: &str| agent.get(key).and_then(|v| v.as_str()).map(str::to_string);
            let id = text("id")?;
            let name = text("name").unwrap_or_else(|| id.clone());
            let distribution = agent.get("distribution");
            let package = distribution.and_then(|d| package_launch(d, "npx", &["-y"]).or_else(|| package_launch(d, "uvx", &[])));
            let binary = distribution.and_then(|d| d.get("binary")).and_then(|b| b.get(platform_key()));
            let mut found = entry(&id, &name, text("version"), text("description"), Source::Registry, None);
            if let Some((spec, path)) = binary.and_then(installed_binary) {
                // Already installed (by the user, outside the registry): run that copy with
                // the registry's arguments. Its version may differ from the registry's.
                found.launch = Some(spec);
                found.note = Some(format!(
                    "using the installed {}{}",
                    path.display(),
                    found.version.as_ref().map(|v| format!("; the registry lists version {v}")).unwrap_or_default()
                ));
            } else if acpr && (package.is_some() || binary.is_some()) {
                found.launch = Some(LaunchSpec::new("acpr", [id.as_str()]));
            } else if let Some(spec) = package {
                found.note = Some(format!("acpr is not installed; started with {} directly", spec.command));
                found.launch = Some(spec);
            } else if binary.is_some() {
                found.note = Some("binary distribution: install acpr to launch it".into());
            }
            found.available = found.launch.is_some();
            Some(found)
        })
        .collect()
}

/// The registry's platform key for this machine, such as `linux-x86_64`.
fn platform_key() -> String {
    let os = match std::env::consts::OS {
        "macos" => "darwin",
        other => other,
    };
    format!("{os}-{}", std::env::consts::ARCH)
}

/// A registry binary entry (`{"cmd": "./opencode", "args": ["acp"], ...}`) whose program is
/// already on PATH: the launch for that copy and where it is.
fn installed_binary(binary: &serde_json::Value) -> Option<(LaunchSpec, std::path::PathBuf)> {
    let cmd = binary.get("cmd")?.as_str()?;
    let program = std::path::Path::new(cmd).file_name()?.to_str()?;
    let path = which::which(program).ok()?;
    let args: Vec<String> = binary.get("args").and_then(|a| a.as_array()).map(|a| a.iter().filter_map(|v| v.as_str().map(str::to_string)).collect()).unwrap_or_default();
    Some((LaunchSpec::new(path.display().to_string(), args), path))
}

fn package_launch(distribution: &serde_json::Value, runner: &str, prefix: &[&str]) -> Option<LaunchSpec> {
    let spec = distribution.get(runner)?;
    let package = spec.get("package")?.as_str()?;
    let mut args: Vec<String> = prefix.iter().map(|arg| arg.to_string()).collect();
    args.push(package.to_string());
    if let Some(extra) = spec.get("args").and_then(|value| value.as_array()) {
        args.extend(extra.iter().filter_map(|arg| arg.as_str().map(str::to_string)));
    }
    let mut launch = LaunchSpec::new(runner, args);
    if let Some(env) = spec.get("env").and_then(|value| value.as_object()) {
        for (key, value) in env {
            // The registry is a remote document: it may set ordinary variables, never ones
            // that change what code the child loads or how it finds programs.
            if let (Some(value), true) = (value.as_str(), registry_env_allowed(key)) {
                launch.env.insert(key.clone(), value.to_string());
            }
        }
    }
    Some(launch)
}

/// Whether a registry entry may set environment variable `key`.
pub fn registry_env_allowed(key: &str) -> bool {
    let upper = key.to_ascii_uppercase();
    const DENIED: [&str; 8] = ["PATH", "NODE_OPTIONS", "NODE_PATH", "PYTHONPATH", "PYTHONSTARTUP", "BASH_ENV", "ENV", "HOME"];
    !(upper.starts_with("LD_") || upper.starts_with("DYLD_") || upper.starts_with("NPM_CONFIG_") || DENIED.contains(&upper.as_str()))
}

fn entry(
    id: &str,
    name: &str,
    version: Option<String>,
    description: Option<String>,
    source: Source,
    launch: Option<LaunchSpec>,
) -> HarnessEntry {
    let (available, note) = match &launch {
        Some(spec) if which::which(&spec.command).is_ok() => (true, None),
        Some(spec) => (false, Some(format!("{} is not on PATH", spec.command))),
        None => (false, Some("no supported distribution".into())),
    };
    HarnessEntry {
        id: id.to_string(),
        name: name.to_string(),
        version,
        description,
        source,
        launch,
        available,
        note,
    }
}

/// Registry entries when the registry is reachable, otherwise the built-in catalog. Built-in
/// entries the registry does not list are kept, so common harnesses are always offered.
pub async fn autoselect(client: &reqwest::Client) -> (Vec<HarnessEntry>, Option<String>) {
    let fetched = async {
        let response = client.get(REGISTRY_URL).send().await?.error_for_status()?;
        response.json::<serde_json::Value>().await
    }
    .await;
    match fetched {
        Ok(document) => {
            let mut entries = parse_registry(&document);
            for fallback in builtin() {
                if !entries.iter().any(|known| known.id == fallback.id) {
                    entries.push(fallback);
                }
            }
            (entries, None)
        }
        Err(error) => (builtin(), Some(format!("registry unavailable, using built-in catalog: {error}"))),
    }
}

/// A user-supplied ACP command, for harnesses no catalog lists.
pub fn custom(id: &str, name: &str, command_line: &str) -> Result<HarnessEntry> {
    let launch = LaunchSpec::from_command_line(command_line)?;
    Ok(entry(id, name, None, None, Source::Custom, Some(launch)))
}

fn split_words(line: &str) -> Option<Vec<String>> {
    let mut words = Vec::new();
    let mut current = String::new();
    let mut quote: Option<char> = None;
    let mut started = false;
    for ch in line.chars() {
        match (quote, ch) {
            (Some(q), c) if c == q => quote = None,
            (Some(_), c) => current.push(c),
            (None, '"' | '\'') => {
                quote = Some(ch);
                started = true;
            }
            (None, c) if c.is_whitespace() => {
                if started {
                    words.push(std::mem::take(&mut current));
                    started = false;
                }
            }
            (None, c) => {
                current.push(c);
                started = true;
            }
        }
    }
    if quote.is_some() {
        return None;
    }
    if started {
        words.push(current);
    }
    Some(words)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn registry_entries_resolve_npx_uvx_and_binary() {
        let document = serde_json::json!({"agents": [
            {"id": "a", "name": "A", "distribution": {"npx": {"package": "a-acp@1.0", "args": ["--acp"]}}},
            {"id": "b", "distribution": {"uvx": {"package": "b-acp"}}},
            {"id": "c", "distribution": {"binary": {"linux-x86_64": {"cmd": "./c"}}}}
        ]});
        // D §7.1: with acpr installed, acpr starts every registry entry.
        let entries = parse_registry_with(&document, true);
        for entry in &entries {
            assert_eq!(entry.launch.as_ref().unwrap().display(), format!("acpr {}", entry.id));
        }
        assert_eq!(entries[1].name, "b");
        assert_eq!(entries[2].source, Source::Registry);
        // Without acpr, packages start with the registry's own command, and the note says so.
        let entries = parse_registry_with(&document, false);
        assert_eq!(entries[0].launch.as_ref().unwrap().display(), "npx -y a-acp@1.0 --acp");
        assert_eq!(entries[1].launch.as_ref().unwrap().display(), "uvx b-acp");
        assert!(entries[0].note.as_deref().is_some_and(|n| n.contains("acpr is not installed")));
        assert!(!entries[2].available);
    }

    // A binary-only registry harness the user already installed (OpenCode, for one) runs from
    // PATH with the registry's arguments instead of being reported unavailable.
    #[test]
    fn installed_registry_binaries_are_launchable() {
        let mut binary = serde_json::Map::new();
        binary.insert(platform_key(), serde_json::json!({"archive": "https://example.invalid/x.tgz", "cmd": "./sh", "args": ["acp"]}));
        let mut missing = serde_json::Map::new();
        missing.insert(platform_key(), serde_json::json!({"cmd": "./no-such-acp-binary-anywhere"}));
        let document = serde_json::json!({"agents": [
            {"id": "shell", "version": "9.9", "distribution": {"binary": binary}},
            {"id": "missing", "distribution": {"binary": missing}}
        ]});
        let entries = parse_registry_with(&document, true);
        let launch = entries[0].launch.as_ref().expect("installed copy used");
        assert!(entries[0].available);
        assert_eq!(launch.args, vec!["acp".to_string()]);
        assert!(launch.command.ends_with("/sh"), "{}", launch.command);
        assert!(entries[0].note.as_deref().is_some_and(|n| n.contains("registry lists version 9.9")));
        assert_eq!(entries[1].launch.as_ref().unwrap().display(), "acpr missing");
        assert!(!parse_registry_with(&document, false)[1].available);
    }

    #[test]
    fn registry_cannot_set_loader_or_path_variables() {
        let document = serde_json::json!({"agents": [
            {"id": "a", "distribution": {"npx": {"package": "a", "env": {"LD_PRELOAD": "/x.so", "NODE_OPTIONS": "--require /x", "PATH": "/x", "AGENT_MODE": "acp"}}}}
        ]});
        let entries = parse_registry_with(&document, false);
        let env = &entries[0].launch.as_ref().unwrap().env;
        assert_eq!(env.keys().collect::<Vec<_>>(), vec!["AGENT_MODE"]);
    }

    #[test]
    fn command_lines_split_on_whitespace_and_respect_quotes() {
        let spec = LaunchSpec::from_command_line(r#"node "my agent.js" --flag 'a b'"#).unwrap();
        assert_eq!(spec.command, "node");
        assert_eq!(spec.args, vec!["my agent.js", "--flag", "a b"]);
        assert!(LaunchSpec::from_command_line("node 'open").is_err());
    }
}
