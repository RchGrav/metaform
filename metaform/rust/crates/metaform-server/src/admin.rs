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
//! A folder names a project; it is registered if it is not yet, as an agent's connection does.

use std::path::{Path, PathBuf};
use std::sync::Arc;

use metaform_store::Store;
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
    } else {
        Err("an admin request is settings or set".into())
    };
    result.unwrap_or_else(|error| json!({"ok": false, "error": error}))
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
