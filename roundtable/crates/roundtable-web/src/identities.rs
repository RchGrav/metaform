//! Identity profiles: ratings, feedback and session contexts saved per genesis session.

use std::path::PathBuf;

use axum::Json;
use axum::extract::State;
use serde_json::{Value, json};

use crate::app::AppState;

/// The file that holds the profile of the identity whose genesis session is `session`. An
/// identity is its session: the genesis name is derived from the session id and can collide
/// (65,536 names), so profiles are keyed by session and keep the name inside. Bytes outside
/// `[A-Za-z0-9_-]` are written as `%XX`, so no session id can name a path outside `dir`.
pub(crate) fn profile_path(dir: &std::path::Path, session: &str) -> std::io::Result<PathBuf> {
    if session.is_empty() {
        return Err(std::io::Error::new(std::io::ErrorKind::InvalidInput, "an identity needs a session id"));
    }
    let mut file = String::new();
    for byte in session.bytes() {
        if byte.is_ascii_alphanumeric() || byte == b'_' || byte == b'-' {
            file.push(byte as char);
        } else {
            file.push_str(&format!("%{byte:02X}"));
        }
    }
    Ok(dir.join(format!("{file}.json")))
}

/// Change one identity profile under `dir`, keyed by session (see `profile_path`). A missing
/// profile starts empty; one that cannot be read or parsed, or that holds another name, is an
/// error, never silently replaced (F08). The new profile is written to a sibling temporary file
/// and renamed over the old one, so an interrupted write leaves the previous profile intact.
/// Callers run on the one recorder task, so writes to a profile never interleave.
pub(crate) fn update_profile(dir: &std::path::Path, session: &str, name: &str, change: impl FnOnce(&mut Value)) -> std::io::Result<()> {
    use std::io::{Error, ErrorKind};
    if name.is_empty() || !name.chars().all(|c| c.is_ascii_alphanumeric()) {
        return Err(Error::new(ErrorKind::InvalidInput, format!("{name:?} is not a genesis name")));
    }
    let path = profile_path(dir, session)?;
    std::fs::create_dir_all(dir)?;
    let mut profile: Value = match std::fs::read_to_string(&path) {
        Ok(text) => serde_json::from_str(&text).map_err(|e| Error::new(ErrorKind::InvalidData, format!("{} is not valid JSON: {e}", path.display())))?,
        Err(e) if e.kind() == ErrorKind::NotFound => json!({"name": name, "session": session, "points": 0.0, "ratings": [], "feedback": []}),
        Err(e) => return Err(e),
    };
    if !profile.is_object() || !profile["points"].is_number() || !profile["ratings"].is_array() {
        return Err(Error::new(ErrorKind::InvalidData, format!("{} does not have an identity profile's shape", path.display())));
    }
    if profile["name"] != name || profile["session"] != session {
        return Err(Error::new(
            ErrorKind::InvalidData,
            format!("{} belongs to {} (session {}), not {name} (session {session})", path.display(), profile["name"], profile["session"]),
        ));
    }
    change(&mut profile);
    let temporary = path.with_file_name(format!(".{}.tmp", path.file_name().unwrap().to_string_lossy()));
    std::fs::write(&temporary, serde_json::to_string_pretty(&profile)?)?;
    std::fs::rename(&temporary, &path)
}

/// Identity profiles as the files `update_profile` writes: one per genesis session.
pub struct FileIdentities {
    pub dir: PathBuf,
}

impl roundtable::Identities for FileIdentities {
    fn profile(&self, session: &str) -> Result<Option<roundtable::Profile>, String> {
        let path = profile_path(&self.dir, session).map_err(|e| e.to_string())?;
        let text = match std::fs::read_to_string(&path) {
            Ok(text) => text,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(None),
            Err(e) => return Err(format!("{}: {e}", path.display())),
        };
        let profile: Value = serde_json::from_str(&text).map_err(|e| format!("{} is not valid JSON: {e}", path.display()))?;
        let ratings = profile["ratings"].as_array().ok_or_else(|| format!("{} has no ratings list", path.display()))?;
        let score = profile["points"].as_f64().ok_or_else(|| format!("{} has no points", path.display()))?;
        let sessions: std::collections::BTreeSet<String> = ratings.iter().filter_map(|r| r["table"].as_str().map(str::to_string)).collect();
        Ok(Some(roundtable::Profile { score, ratings: ratings.len() as u64, sessions: sessions.len() as u64 }))
    }
}

/// Save one end-of-table rating to the rated agent's identity (O: ratings are saved to the
/// agent's identity and carry into future sessions).
pub(crate) fn save_rating(dir: &std::path::Path, data: &Value) -> std::io::Result<()> {
    let (session, name) = (data["to_session"].as_str().unwrap_or_default(), data["to_name"].as_str().unwrap_or_default());
    update_profile(dir, session, name, |profile| {
        let points = profile["points"].as_f64().unwrap_or(0.0) + data["points"].as_f64().unwrap_or(0.0);
        profile["points"] = json!(points);
        if let Some(list) = profile["ratings"].as_array_mut() {
            list.push(json!({"table": data["table"], "from": data["from_name"], "ratings": data["ratings"], "points": data["points"]}));
        }
    })
}

/// Record each table an identity sat at, and the harness and settings that hold its session,
/// so a later table can resume it and the agent keeps its identity (owner's AgentIdentity: "a
/// resumed session keeps its name").
pub(crate) fn save_context(dir: &std::path::Path, ready: &Value, seat: Option<&Value>) -> std::io::Result<()> {
    let (session, name) = (ready["session"].as_str().unwrap_or_default(), ready["name"].as_str().unwrap_or_default());
    update_profile(dir, session, name, |profile| {
        if !profile["contexts"].is_array() {
            profile["contexts"] = json!([]);
        }
        let context = json!({
            "table": ready["table"], "seat": ready["seat"], "session": ready["session"],
            "harness": seat.map(|s| s["harness"].clone()).unwrap_or(Value::Null),
            "settings": seat.map(|s| s["settings"].clone()).unwrap_or(Value::Null),
        });
        if let Some(list) = profile["contexts"].as_array_mut()
            && !list.iter().any(|c| c["table"] == context["table"])
        {
            list.push(context);
        }
    })
}

/// Save feedback given during a table to the rated agent's identity. Feedback does not add
/// points; points come from the end-of-table ratings.
pub(crate) fn save_feedback(dir: &std::path::Path, data: &Value) -> std::io::Result<()> {
    let (session, name) = (data["to_session"].as_str().unwrap_or_default(), data["to_name"].as_str().unwrap_or_default());
    update_profile(dir, session, name, |profile| {
        if !profile["feedback"].is_array() {
            profile["feedback"] = json!([]);
        }
        if let Some(list) = profile["feedback"].as_array_mut() {
            list.push(json!({"table": data["table"], "from": data["from_name"], "ratings": data["ratings"], "note": data["note"]}));
        }
    })
}

pub(crate) async fn identities_list(State(state): State<AppState>) -> Json<Value> {
    let dir = state.data_dir.join("identities");
    let mut list: Vec<Value> = Vec::new();
    let mut errors: Vec<String> = Vec::new();
    for entry in std::fs::read_dir(&dir).into_iter().flatten().flatten() {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("json") {
            continue;
        }
        // An unreadable profile is reported, not skipped silently.
        match std::fs::read_to_string(&path).map_err(|e| e.to_string()).and_then(|t| serde_json::from_str::<Value>(&t).map_err(|e| e.to_string())) {
            Ok(p) => list.push(json!({
                "name": p["name"], "session": p["session"], "points": p["points"],
                "ratings": p["ratings"].as_array().map(|r| r.len()).unwrap_or(0),
                // The latest session, for resuming this identity at a new table.
                "context": p["contexts"].as_array().and_then(|c| c.last()).cloned().unwrap_or(Value::Null),
            })),
            Err(error) => errors.push(format!("{}: {error}", path.display())),
        }
    }
    list.sort_by(|a, b| b["points"].as_f64().partial_cmp(&a["points"].as_f64()).unwrap_or(std::cmp::Ordering::Equal));
    Json(json!({"identities": list, "errors": errors}))
}
