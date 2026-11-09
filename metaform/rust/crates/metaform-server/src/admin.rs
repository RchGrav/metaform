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
//! - `{"admin": {"import": {"project"?: "<folder>", "map"?: "<name>", "markdown": "<document>"}}}`
//!   reads a document made by `export` back into the specification layer (R-1.2). Every changed
//!   section becomes one `update` through the tool's own write rules. All of them are first applied
//!   to a copy of the current map, so a document that breaks any rule writes nothing. Answers
//!   `written` (the addresses changed) and `unchanged` (how many sections were already current).
//!
//! For settings, a folder names a project and is registered if it is not yet, as an agent's
//! connection does. An export only reads: a folder that is not registered is refused, so an export
//! never creates an empty map.

use std::path::{Path, PathBuf};
use std::sync::Arc;

use metaform_store::{ClientId, Failure, MapKey, Store};
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
    } else if let Some(body) = request.get("import") {
        import(store, body)
    } else {
        Err("an admin request must be `settings`, `set`, `export` or `import`".into())
    };
    result.unwrap_or_else(|error| json!({"ok": false, "error": error}))
}

/// The map an export or import names, and the document's project title.
fn target(store: &Store, body: &Value, verb: &str) -> Result<(MapKey, String), String> {
    Ok(match (body["project"].as_str(), body["map"].as_str()) {
        (Some(folder), None) => {
            let folder = PathBuf::from(folder);
            let id = store
                .find_project(&folder)
                .map_err(|e| e.to_string())?
                .ok_or_else(|| format!("{} has no map yet; an agent creates it by using the project-map tool in that folder", folder.display()))?;
            let title = folder.file_name().map(|n| n.to_string_lossy().to_string()).unwrap_or_default();
            (MapKey::main(&id), title)
        }
        (None, Some(name)) => {
            crate::check_map_name(name)?;
            (MapKey::standalone(name), name.to_string())
        }
        _ => return Err(format!("an {verb} must name exactly one of: a project folder or a map")),
    })
}

/// The specification document for one project's main map or one standalone map.
fn export(store: &Store, body: &Value) -> Result<Value, String> {
    let (key, title) = target(store, body, "export")?;
    let map = store.snapshot(&key).map_err(|e| e.to_string())?;
    let mut answer = json!({
        "ok": true,
        "markdown": metaform_core::markdown::render(&map, &title),
        "left_out": metaform_core::markdown::left_out(&map),
    });
    if body["check"] == json!(true) {
        let reports = metaform_core::check::check(&map);
        answer["summary"] = json!(metaform_core::check::summary(&reports));
        answer["reports"] = json!(reports.iter().map(metaform_core::check::Report::line).collect::<Vec<_>>());
    }
    Ok(answer)
}

/// Read a document back into the specification layer. Nothing is written unless every changed
/// section passes the write rules against the current map.
fn import(store: &Store, body: &Value) -> Result<Value, String> {
    let (key, title) = target(store, body, "import")?;
    let Some(document) = body["markdown"].as_str() else {
        return Err("an import request must carry the document in its `markdown` field".into());
    };
    let map = store.snapshot(&key).map_err(|e| e.to_string())?;
    let parsed = metaform_core::markdown::parse(document, &map, &title).map_err(|e| e.to_string())?;
    let layer = metaform_core::specification::LAYER;
    let mut commands = Vec::new();
    let mut unchanged = 0;
    for (address, blocks) in &parsed {
        let current = map
            .element(address)
            .and_then(|element| element.fields.get(layer))
            .map(|value| metaform_core::specification::blocks(address, value))
            .transpose()
            .map_err(|refusal| refusal.reason)?
            .unwrap_or_default();
        if &current == blocks {
            unchanged += 1;
            continue;
        }
        let value = metaform_core::specification::to_json(blocks);
        commands.push((address.clone(), json!({"update": {address.as_str(): {layer: value}}})));
    }
    // One write: every section is checked against the map the sections before it made, and
    // all are stored in one transaction or none are. No other write lands in between.
    let sent: Vec<Value> = commands.iter().map(|(_, command)| command.clone()).collect();
    if let Err(failed) = store.execute_all(ClientId(0), &key, &sent) {
        return Err(match (failed.index, &failed.failure) {
            (Some(index), Failure::Refused(refusal)) => format!(
                "'{}': {}: {}; the import wrote nothing",
                commands[index].0,
                refusal.code.as_str(),
                refusal.reason
            ),
            (_, failure) => format!("{failure}; the import may or may not be stored, so export the map before you import again"),
        });
    }
    let written: Vec<String> = commands.into_iter().map(|(address, _)| address).collect();
    Ok(json!({"ok": true, "written": written, "unchanged": unchanged}))
}

/// Send one admin request from the CLI, starting the server if none is running. A refusal by the
/// server is an error, as is a connection failure.
pub async fn request(home: &Path, server_exe: &Path, body: Value) -> Result<Value, String> {
    let answer = exchange(home, server_exe, body).await?;
    if answer["ok"] == json!(true) {
        Ok(answer)
    } else {
        Err(answer["error"].as_str().unwrap_or("the server refused the request").to_string())
    }
}

/// Send one admin request and return the server's answer, refused or not. `Err` means the
/// request did not reach the server or the answer was not JSON.
pub async fn exchange(home: &Path, server_exe: &Path, body: Value) -> Result<Value, String> {
    let stream = crate::connect_or_start(home, server_exe).await?;
    let (read, mut write) = stream.into_split();
    write.write_all(format!("{}\n", json!({"admin": body})).as_bytes()).await.map_err(|e| e.to_string())?;
    let mut line = String::new();
    BufReader::new(read).read_line(&mut line).await.map_err(|e| e.to_string())?;
    serde_json::from_str(&line).map_err(|_| format!("the server answered {line:?}"))
}
