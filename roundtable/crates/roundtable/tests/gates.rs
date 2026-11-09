//! The owner's Gate Burden standard (docs/gate-burden.md) applied to Roundtable's inference
//! gates: every gate in the code carries the comment "gate: <id>" naming its entry in
//! docs/gate-registry.yaml, and every active entry is in the code. A code change that adds a
//! known kind of blocking branch without a gate id fails here (standard §10). A line that only
//! looks like a gate carries "not a gate: <reason>" instead.
//!
//! Limit: the blocking constructs below are the kinds found in the code on 2026-11-07. A new
//! kind of block is caught only once its pattern is added to BLOCKING.

use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};

/// Code that stops, rejects, hides or delays agents' work or output.
const BLOCKING: [&str; 10] = [
    "Verdict::Reject {",
    "\"Not done",
    "Not recorded",
    "not recorded",
    "self.end(",
    "start_rating()",
    "waiting_for_free = true",
    "was not counted",
    "judging_floor = Some",
    "rules::truncate_to(",
];

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../..")
}

/// Registry entries: gate id -> status.
fn registry() -> BTreeMap<String, String> {
    let text = std::fs::read_to_string(root().join("docs/gate-registry.yaml")).expect("docs/gate-registry.yaml");
    let mut entries = BTreeMap::new();
    let mut current: Option<String> = None;
    for line in text.lines() {
        if let Some(id) = line.strip_prefix("- gate_id: ") {
            let id = id.trim().to_string();
            assert!(!entries.contains_key(&id), "{id} is registered twice");
            entries.insert(id.clone(), String::new());
            current = Some(id);
        } else if let (Some(id), Some(status)) = (&current, line.strip_prefix("  status: ")) {
            entries.insert(id.clone(), status.trim().to_string());
        }
    }
    entries
}

/// Source files with their lines, test modules left out.
fn sources() -> Vec<(PathBuf, Vec<String>)> {
    fn walk(dir: &Path, found: &mut Vec<PathBuf>) {
        for entry in std::fs::read_dir(dir).into_iter().flatten().flatten() {
            let path = entry.path();
            if path.is_dir() {
                walk(&path, found);
            } else if path.extension().is_some_and(|e| e == "rs" || e == "ts") {
                found.push(path);
            }
        }
    }
    let mut files = Vec::new();
    for crate_dir in std::fs::read_dir(root().join("crates")).unwrap().flatten() {
        walk(&crate_dir.path().join("src"), &mut files);
    }
    walk(&root().join("adapters/openrouter-acp/src"), &mut files);
    files
        .into_iter()
        .map(|path| {
            let text = std::fs::read_to_string(&path).unwrap();
            let code = text.split("#[cfg(test)]").next().unwrap_or_default();
            (path, code.lines().map(str::to_string).collect())
        })
        .collect()
}

/// Gate ids named on a line: "gate: RT-G07 ..." gives RT-G07.
fn marked(line: &str) -> Option<String> {
    let at = line.find("gate: RT-G")? + "gate: ".len();
    let id: String = line[at..].chars().take_while(|c| c.is_ascii_alphanumeric() || *c == '-').collect();
    Some(id)
}

#[test]
fn every_inference_gate_is_registered_and_marked() {
    let registry = registry();
    assert!(!registry.is_empty(), "the registry has entries");
    let mut in_code = BTreeSet::new();
    let mut unmarked = Vec::new();
    for (path, lines) in sources() {
        for (n, line) in lines.iter().enumerate() {
            if let Some(id) = marked(line) {
                assert!(registry.contains_key(&id), "{}:{} names {id}, which is not in docs/gate-registry.yaml", path.display(), n + 1);
                in_code.insert(id);
            }
            if line.trim_start().starts_with("//") || !BLOCKING.iter().any(|p| line.contains(p)) {
                continue;
            }
            let near = &lines[n.saturating_sub(3)..=n];
            if !near.iter().any(|l| l.contains("gate: RT-G") || l.contains("not a gate:")) {
                unmarked.push(format!("{}:{}: {}", path.display(), n + 1, line.trim()));
            }
        }
    }
    assert!(unmarked.is_empty(), "blocking code with no gate id (standard §10):\n{}", unmarked.join("\n"));
    let missing: Vec<&String> = registry.iter().filter(|(id, status)| status.starts_with("active") && !in_code.contains(*id)).map(|(id, _)| id).collect();
    assert!(missing.is_empty(), "registered active gates with no marker in the code: {missing:?}");
}

/// Every setting that names a gate is listed in that gate's `settings:` line in the registry,
/// and every key a registry entry lists is a declared setting. The settings are the owner's
/// switches for the gates, so the two lists must agree.
#[test]
fn gate_settings_and_the_registry_agree() {
    let text = std::fs::read_to_string(root().join("docs/gate-registry.yaml")).expect("docs/gate-registry.yaml");
    let mut listed: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    let mut current = String::new();
    for line in text.lines() {
        if let Some(id) = line.strip_prefix("- gate_id: ") {
            current = id.trim().to_string();
        } else if let Some(keys) = line.strip_prefix("  settings: ") {
            let keys = keys.trim().trim_start_matches('[').trim_end_matches(']');
            listed.entry(current.clone()).or_default().extend(keys.split(',').map(|k| k.trim().to_string()));
        }
    }
    let registered = registry();
    for setting in roundtable::settings::SETTINGS {
        // Every default must be a valid value of its own setting.
        setting.parse(setting.default).unwrap_or_else(|e| panic!("{}: bad default: {e}", setting.key));
        if let Some(gate) = setting.gate {
            assert!(registered.contains_key(gate), "{} names {gate}, which is not registered", setting.key);
            assert!(listed.get(gate).is_some_and(|keys| keys.contains(setting.key)), "{gate}'s settings line does not list {}", setting.key);
        }
    }
    for (gate, keys) in &listed {
        for key in keys {
            assert!(roundtable::settings::find(key).is_some(), "{gate} lists {key}, which is not a declared setting");
        }
    }
}
