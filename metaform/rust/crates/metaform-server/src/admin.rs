//! The CLI's admin requests: settings (R-4.8). Not an MCP tool (R-5.15), so the agent's one tool
//! stays the only tool.
//!
//! The CLI connects as a forwarder does, but its handshake line is the request itself, and the
//! server answers one JSON line and closes:
//!
//! - `{"admin": {"settings": {"project"?: "<folder>"}}}` answers every setting's value, default,
//!   source and when a change applies, for that project or globally.
//! - `{"admin": {"set": {"key": "<key>", "value"?: <json>, "project"?: "<folder>"}}}` sets a value,
//!   or removes it when `value` is absent, so the next level applies.
//!
//! - `{"admin": {"export": {"project"?: "<folder>", "map"?: "<name>", "check"?: true}}}` answers
//!   the specification document (R-1.2) as `markdown`, and with `check` the TASTE reports as
//!   `reports` (one line each) and `summary`.
//!
//! For settings, a folder names a project and is registered if it is not yet, as an agent's
//! connection does. An export only reads: a folder that is not registered is refused, so an export
//! never creates an empty map.

use std::path::{Path, PathBuf};
use std::sync::Arc;

use metaform_store::{MapKey, Store};
use serde_json::{Value, json};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};

/// Answer one admin request on the server.
pub async fn answer(store: &Arc<Store>, request: &Value) -> Value {
    let store = Arc::clone(store);
    let request = request.clone();
    tokio::task::spawn_blocking(move || answer_now(&store, &request))
        .await
        .unwrap_or_else(|e| json!({"ok": false, "error": e.to_string()}))
}

fn answer_now(store: &Store, request: &Value) -> Value {
    let project = |body: &Value| -> Result<Option<String>, String> {
        let Some(folder) = body["project"].as_str() else { return Ok(None) };
        let folder = PathBuf::from(folder);
        let name = folder.file_name().map(|n| n.to_string_lossy().to_string()).unwrap_or_default();
        store.register_project(&folder, &name).map(Some).map_err(|e| e.to_string())
    };
    let result = if let Some(body) = request.get("settings") {
        project(body).map(|id| json!({"ok": true, "settings": store.settings().list(id.as_deref())}))
    } else if let Some(body) = request.get("set") {
        let Some(key) = body["key"].as_str() else {
            return json!({"ok": false, "error": "set needs a key"});
        };
        project(body).and_then(|id| {
            let value = body.get("value").filter(|v| !v.is_null()).cloned();
            store.settings().set(key, value, id.as_deref())?;
            let applies = metaform_store::settings::declared(key).map_or("", |s| if s.at_start { "at the next start" } else { "at once" });
            Ok(json!({"ok": true, "applies": applies}))
        })
    } else if let Some(body) = request.get("export") {
        export(store, body)
    } else {
        Err("an admin request is settings, set or export".into())
    };
    result.unwrap_or_else(|error| json!({"ok": false, "error": error}))
}

/// The specification document for one project's main map or one standalone map.
fn export(store: &Store, body: &Value) -> Result<Value, String> {
    let (key, title) = match (body["project"].as_str(), body["map"].as_str()) {
        (Some(folder), None) => {
            let folder = PathBuf::from(folder);
            let id = store
                .find_project(&folder)
                .map_err(|e| e.to_string())?
                .ok_or_else(|| format!("{} has no map yet; an agent creates one by working there through the project-map tool", folder.display()))?;
            let title = folder.file_name().map(|n| n.to_string_lossy().to_string()).unwrap_or_default();
            (MapKey::main(&id), title)
        }
        (None, Some(name)) => {
            crate::check_map_name(name)?;
            (MapKey::standalone(name), name.to_string())
        }
        _ => return Err("an export names exactly one of a project folder or a map".into()),
    };
    let map = store.snapshot(&key).map_err(|e| e.to_string())?;
    let mut answer = json!({"ok": true, "markdown": metaform_core::markdown::render(&map, &title)});
    if body["check"] == json!(true) {
        let reports = metaform_core::check::check(&map);
        answer["summary"] = json!(metaform_core::check::summary(&reports));
        answer["reports"] = json!(reports.iter().map(metaform_core::check::Report::line).collect::<Vec<_>>());
    }
    Ok(answer)
}

/// Send one admin request from the CLI, starting the server if none is running.
pub async fn request(home: &Path, server_exe: &Path, body: Value) -> Result<Value, String> {
    let stream = crate::connect_or_start(home, server_exe).await?;
    let (read, mut write) = stream.into_split();
    write.write_all(format!("{}\n", json!({"admin": body})).as_bytes()).await.map_err(|e| e.to_string())?;
    let mut line = String::new();
    BufReader::new(read).read_line(&mut line).await.map_err(|e| e.to_string())?;
    let answer: Value = serde_json::from_str(&line).map_err(|_| format!("the server answered {line:?}"))?;
    if answer["ok"] == json!(true) {
        Ok(answer)
    } else {
        Err(answer["error"].as_str().unwrap_or("the server refused the request").to_string())
    }
}
