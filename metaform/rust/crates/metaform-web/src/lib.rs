//! The graph workspace host (dev/graph_workspace_graph.md, section 4; routes from
//! dev/graph_workspace_seam.md, "Host routes").
//!
//! A separate process and an MCP client of the home's server, like `metaform call`. It serves
//! the built web files and three routes:
//! - `GET /api/projects`: every project registered in the home, from the server's admin request
//!   `projects`. The host never opens the store itself (D-10), and it opens only registered
//!   projects, because a connection from a new folder would register it.
//! - `POST /api/projects/<id>/call`: forwards one read command to the server and returns the
//!   result unchanged. A refusal comes back with HTTP 200, as the refusal JSON. Writes are
//!   refused with 403: the workspace only reads, so a web page cannot change the map here.
//! - `GET /api/projects/<id>/events`: Server-Sent Events; one `map-changed` event per commit.
//!
//! Every request must name this server in `Host`, and in `Origin` when one is sent, so another
//! web page cannot reach the map through DNS rebinding. The server binds to 127.0.0.1 only.

use std::convert::Infallible;
use std::net::SocketAddr;
use std::path::PathBuf;
use std::sync::Arc;

use axum::extract::{Path, Request, State};
use axum::http::{StatusCode, header};
use axum::middleware::{self, Next};
use axum::response::sse::{Event, KeepAlive, Sse};
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use futures_util::Stream;
use metaform_server::Target;
use metaform_server::call::{Answer, call};
use serde_json::{Value, json};

/// One registered project, as the server lists it. `id` is the server's, and opaque.
#[derive(Clone, Debug)]
pub struct Project {
    pub id: String,
    pub name: String,
    pub folder: PathBuf,
}

#[derive(Clone)]
pub struct Config {
    /// The home whose server the host talks to.
    pub home: PathBuf,
    /// The `metaform` binary, used to start the server when none answers.
    pub server_exe: PathBuf,
    /// The built web files (`metaform/workspace/dist`).
    pub assets: PathBuf,
}

#[derive(Clone)]
struct AppState {
    config: Arc<Config>,
    addr: SocketAddr,
}

/// Whether a command only reads (R-5.1): `map`, `goto`, `search`, `orphaned`, a raw dump
/// (a key that starts with a period) or an addressed read (a key with a period whose body names
/// only layers, each with `{}`). Everything else may write and is refused.
pub fn is_read(command: &Value) -> bool {
    let Some(object) = command.as_object() else { return false };
    let [(key, body)] = object.iter().collect::<Vec<_>>()[..] else { return false };
    match key.as_str() {
        "map" | "goto" | "search" | "orphaned" => true,
        key if key.starts_with('.') => body.as_object().is_some_and(|b| b.is_empty()),
        key if key.contains('.') => body
            .as_object()
            .is_some_and(|layers| layers.values().all(|v| v.as_object().is_some_and(|o| o.is_empty()))),
        _ => false,
    }
}

pub fn router(config: Arc<Config>, addr: SocketAddr) -> Router {
    let state = AppState { config: Arc::clone(&config), addr };
    Router::new()
        .route("/api/projects", get(projects))
        .route("/api/projects/{id}/call", post(forward))
        .route("/api/projects/{id}/events", get(events))
        .fallback(get(file))
        .layer(middleware::from_fn_with_state(state.clone(), require_host))
        .with_state(state)
}

/// The Host (and Origin, when sent) must name this server (as roundtable-web does).
async fn require_host(State(state): State<AppState>, request: Request, next: Next) -> Response {
    let port = state.addr.port();
    let allowed = [format!("{}", state.addr), format!("localhost:{port}"), format!("127.0.0.1:{port}")];
    let headers = request.headers();
    let host = headers.get(header::HOST).and_then(|v| v.to_str().ok()).unwrap_or_default();
    if !allowed.iter().any(|a| a == host) {
        return (StatusCode::FORBIDDEN, "unexpected Host").into_response();
    }
    if let Some(origin) = headers.get(header::ORIGIN).and_then(|v| v.to_str().ok())
        && !allowed.iter().any(|a| origin == format!("http://{a}"))
    {
        return (StatusCode::FORBIDDEN, "unexpected Origin").into_response();
    }
    next.run(request).await
}

/// The registered projects, read from the server each time, so a project registered after
/// the host started is served without a restart.
async fn registered(state: &AppState) -> Result<Vec<Project>, String> {
    let answer = metaform_server::admin::request(&state.config.home, &state.config.server_exe, json!({"projects": {}})).await?;
    let list = answer["projects"].as_array().ok_or("the server's project list is not a list")?;
    Ok(list
        .iter()
        .filter_map(|p| {
            Some(Project {
                id: p["id"].as_str()?.to_string(),
                name: p["name"].as_str().unwrap_or_default().to_string(),
                folder: PathBuf::from(p["folder"].as_str()?),
            })
        })
        .collect())
}

/// The registered project with this id. `Err` is a response for a missing project or a server
/// failure (boxed, because a response is large).
async fn project(state: &AppState, id: &str) -> Result<Project, Box<Response>> {
    match registered(state).await {
        Ok(all) => all.into_iter().find(|p| p.id == id).ok_or_else(|| Box::new(unknown(id))),
        Err(reason) => Err(Box::new(unreachable(reason))),
    }
}

fn unreachable(reason: String) -> Response {
    (StatusCode::BAD_GATEWAY, Json(json!({"error": reason}))).into_response()
}

fn unknown(id: &str) -> Response {
    (StatusCode::NOT_FOUND, Json(json!({"error": format!("no project '{id}' in this host")}))).into_response()
}

async fn projects(State(state): State<AppState>) -> Response {
    match registered(&state).await {
        Ok(all) => Json(Value::Array(
            all.iter()
                .map(|p| json!({"id": p.id, "name": p.name, "folder": p.folder.to_string_lossy()}))
                .collect(),
        ))
        .into_response(),
        Err(reason) => unreachable(reason),
    }
}

async fn forward(State(state): State<AppState>, Path(id): Path<String>, Json(command): Json<Value>) -> Response {
    if !is_read(&command) {
        return (StatusCode::FORBIDDEN, Json(json!({"error": "this host forwards reads only"}))).into_response();
    }
    let project = match project(&state, &id).await {
        Ok(p) => p,
        Err(response) => return *response,
    };
    let target = Target::Project(project.folder.clone());
    match call(&state.config.home, &target, &state.config.server_exe, command).await {
        Ok(Answer::Ok(text)) | Ok(Answer::Refused(text)) => match serde_json::from_str::<Value>(&text) {
            Ok(value) => Json(value).into_response(),
            Err(_) => (StatusCode::BAD_GATEWAY, Json(json!({"error": "the server answered with text that is not JSON", "text": text}))).into_response(),
        },
        Err(reason) => (StatusCode::BAD_GATEWAY, Json(json!({"error": reason}))).into_response(),
    }
}

async fn events(State(state): State<AppState>, Path(id): Path<String>) -> Response {
    let project = match project(&state, &id).await {
        Ok(p) => p,
        Err(response) => return *response,
    };
    let target = Target::Project(project.folder.clone());
    match metaform_server::watch::watch(&state.config.home, &target, &state.config.server_exe).await {
        Ok(changes) => Sse::new(map_changed(changes)).keep_alive(KeepAlive::default()).into_response(),
        Err(reason) => unreachable(reason),
    }
}

/// One `map-changed` event per commit (seam rule 1: no diff). The data is `{}` because a browser's
/// EventSource drops an event whose data is empty (HTML, "dispatch the event").
fn map_changed(changes: tokio::sync::mpsc::Receiver<()>) -> impl Stream<Item = Result<Event, Infallible>> {
    futures_util::stream::unfold(changes, |mut changes| async move {
        changes.recv().await.map(|()| (Ok(Event::default().event("map-changed").data("{}")), changes))
    })
}

/// The content type for the file kinds a Vite build writes.
fn content_type(path: &std::path::Path) -> &'static str {
    match path.extension().and_then(|e| e.to_str()) {
        Some("html") => "text/html; charset=utf-8",
        Some("js" | "mjs") => "text/javascript; charset=utf-8",
        Some("css") => "text/css; charset=utf-8",
        Some("json" | "map") => "application/json",
        Some("svg") => "image/svg+xml",
        Some("png") => "image/png",
        Some("woff2") => "font/woff2",
        Some("ico") => "image/x-icon",
        _ => "application/octet-stream",
    }
}

/// Serves a built file. A path that names no file gets `index.html`, so the workspace's own
/// routes load the app. Only plain segments are accepted, so no request reads outside `assets`.
async fn file(State(state): State<AppState>, uri: axum::http::Uri) -> Response {
    let relative = uri.path().trim_start_matches('/');
    let safe = relative
        .split('/')
        .all(|segment| !segment.is_empty() && segment != "." && segment != ".." && !segment.contains('\\'));
    let assets = &state.config.assets;
    let candidate = if safe { assets.join(relative) } else { assets.join("index.html") };
    let path = if candidate.is_file() { candidate } else { assets.join("index.html") };
    match tokio::fs::read(&path).await {
        Ok(bytes) => ([(header::CONTENT_TYPE, content_type(&path))], bytes).into_response(),
        Err(_) => (StatusCode::NOT_FOUND, "not built: run npm run build in metaform/workspace").into_response(),
    }
}

/// Serves until Ctrl-C.
pub async fn serve(config: Config, listener: tokio::net::TcpListener) -> std::io::Result<()> {
    let addr = listener.local_addr()?;
    axum::serve(listener, router(Arc::new(config), addr))
        .with_graceful_shutdown(async {
            let _ = tokio::signal::ctrl_c().await;
        })
        .await
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reads_pass_and_writes_do_not() {
        for read in [
            json!({"map": {}}),
            json!({"goto": "code.store"}),
            json!({".": {}}),
            json!({".code.store": {}}),
            json!({"code.store": {}}),
            json!({"code.store": {"specification": {}}}),
            json!({"search": {"text": "x"}}),
            json!({"orphaned": {}}),
        ] {
            assert!(is_read(&read), "{read}");
        }
        for write in [
            json!({"add": {"code.x": {}}}),
            json!({"update": {}}),
            json!({"delete": "code.x"}),
            json!({"layer": {}}),
            json!({"code.store": {"name": "renamed"}}),
            json!({"code.store": {"specification": [{"text": "x"}]}}),
            json!({".": {"x": 1}}),
            json!({"map": {}, "goto": "code"}),
            json!([]),
        ] {
            assert!(!is_read(&write), "{write}");
        }
    }
}
