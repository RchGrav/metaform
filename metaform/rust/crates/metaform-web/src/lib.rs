//! The graph workspace host (dev/graph_workspace_graph.md, section 4; routes from
//! dev/graph_workspace_seam.md, "Host routes").
//!
//! A separate process and an MCP client of the home's server, like `metaform call`. It serves
//! the built web files and five routes:
//! - `GET /api/projects`: every project registered in the home, from the server's admin request
//!   `projects`. The host never opens the store itself (D-10), and it opens only registered
//!   projects, because a connection from a new folder would register it.
//! - `POST /api/projects/<id>/call`: forwards one read command to the server and returns the
//!   result unchanged. A refusal comes back with HTTP 200, as the refusal JSON. A write is
//!   refused with 403: writes have their own route, which checks who sends them.
//! - `POST /api/projects/<id>/write`: forwards one `add`, `update` or `delete` command to the
//!   server and returns the tool's answer with HTTP 200: `{"status": "ok"}`, or the refusal JSON.
//!   The request must carry an `Origin` that is `http://` and then exactly its own `Host` value,
//!   which a browser sends only from a page this host served. A request without that `Origin`
//!   gets 403. A host started with `--read-only` answers 403 to every write.
//! - `GET /api/host`: `{"writes": true}`, or `{"writes": false}` for a host started with
//!   `--read-only`, so the page knows whether it can store an edit.
//! - `GET /api/projects/<id>/events`: Server-Sent Events; one `map-changed` event per commit.
//!
//! The host adds one `meta` element (`HOST_MARK`) to the page it serves. The page reads it to know
//! that the host serves it, and then uses these routes and never its simulated data.
//!
//! Every request must name this server in `Host`, and in `Origin` when one is sent, so another
//! web page cannot reach the map through DNS rebinding. The server binds to 127.0.0.1 only.
//! The tests of the routes are in `tests/routes.rs`.

use std::convert::Infallible;
use std::net::SocketAddr;
use std::path::PathBuf;
use std::sync::Arc;

use axum::extract::{Path, Request, State};
use axum::http::{HeaderMap, StatusCode, header};
use axum::middleware::{self, Next};
use axum::response::sse::{Event, KeepAlive, Sse};
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use futures_util::Stream;
use metaform_server::Target;
use metaform_server::call::{Answer, call};
use serde_json::{Value, json};

/// The port the host uses when none is given, so `metaform gui` has the same address each time.
pub const DEFAULT_PORT: u16 = 4170;

/// The element the host adds to `index.html`. The workspace page looks for it by its name
/// (`metaform/workspace/src/main.tsx`), so the two must stay the same.
pub const HOST_MARK: &str = r#"<meta name="metaform-host" content="metaform-web">"#;

/// One registered project, as the server lists it. `id` is the server's, and opaque.
#[derive(Clone, Debug)]
pub struct Project {
    pub id: String,
    pub name: String,
    pub folder: PathBuf,
}

/// What a host needs to serve one home.
#[derive(Clone)]
pub struct Config {
    /// The home whose server the host talks to.
    pub home: PathBuf,
    /// The `metaform` binary, used to start the server when none answers.
    pub server_exe: PathBuf,
    /// The built web files (`metaform/workspace/dist`).
    pub assets: PathBuf,
    /// True when the host was started with `--read-only`: it then refuses every write.
    pub read_only: bool,
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

/// Whether a command is one the write route forwards: one `add`, `update` or `delete`.
pub fn is_write(command: &Value) -> bool {
    let Some(object) = command.as_object() else { return false };
    object.len() == 1 && object.keys().all(|key| matches!(key.as_str(), "add" | "update" | "delete"))
}

/// Why a request may not write, or `None` when it may. A request may write when the host is not
/// read-only and its `Origin` is `http://` and then exactly its `Host` value. `require_host` has
/// already checked that `Host` names this server. `localhost` and `127.0.0.1` do not match each
/// other, because a browser treats them as two origins.
pub fn write_refusal(read_only: bool, headers: &HeaderMap) -> Option<&'static str> {
    if read_only {
        return Some("this host is read-only: it was started with --read-only");
    }
    match header_text(headers, header::ORIGIN) {
        None => Some("a write needs an Origin header, which a browser sends from this host's own page"),
        Some(origin) if origin.strip_prefix("http://") != Some(header_text(headers, header::HOST).unwrap_or_default()) => {
            Some("a write must come from this host's own page: Origin must be http:// and then the request's Host")
        }
        Some(_) => None,
    }
}

/// A header's value as text, or `None` when the header is absent or is not text.
fn header_text(headers: &HeaderMap, name: header::HeaderName) -> Option<&str> {
    headers.get(name).and_then(|v| v.to_str().ok())
}

/// The host's routes for one home. `addr` is the address the host listens on.
pub fn router(config: Arc<Config>, addr: SocketAddr) -> Router {
    let state = AppState { config: Arc::clone(&config), addr };
    Router::new()
        .route("/api/host", get(host))
        .route("/api/projects", get(projects))
        .route("/api/projects/{id}/call", post(forward))
        .route("/api/projects/{id}/write", post(write))
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
    let host = header_text(headers, header::HOST).unwrap_or_default();
    if !allowed.iter().any(|a| a == host) {
        return (StatusCode::FORBIDDEN, "unexpected Host").into_response();
    }
    if let Some(origin) = header_text(headers, header::ORIGIN)
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

fn forbidden(reason: &str) -> Response {
    (StatusCode::FORBIDDEN, Json(json!({"error": reason}))).into_response()
}

async fn host(State(state): State<AppState>) -> Response {
    Json(json!({"writes": !state.config.read_only})).into_response()
}

async fn forward(State(state): State<AppState>, Path(id): Path<String>, Json(command): Json<Value>) -> Response {
    if !is_read(&command) {
        return forbidden("this route forwards reads only; a write goes to /write");
    }
    relay(&state, &id, command).await
}

async fn write(State(state): State<AppState>, Path(id): Path<String>, headers: HeaderMap, Json(command): Json<Value>) -> Response {
    if let Some(reason) = write_refusal(state.config.read_only, &headers) {
        return forbidden(reason);
    }
    if !is_write(&command) {
        let reason = "this route forwards one add, update or delete command; a read goes to /call";
        return (StatusCode::BAD_REQUEST, Json(json!({"error": reason}))).into_response();
    }
    relay(&state, &id, command).await
}

/// Sends one command to the home's server for this project and returns the tool's answer
/// unchanged. A refusal by the tool is an answer, so it also has HTTP 200.
async fn relay(state: &AppState, id: &str, command: Value) -> Response {
    let project = match project(state, id).await {
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
    let whole = uri.path().trim_start_matches('/');
    // A folder is asked for with or without a closing slash; the segments are checked without it.
    let relative = whole.strip_suffix('/').unwrap_or(whole);
    let safe = relative
        .split('/')
        .all(|segment| !segment.is_empty() && segment != "." && segment != ".." && !segment.contains('\\'));
    let assets = &state.config.assets;
    let candidate = if safe { assets.join(relative) } else { assets.join("index.html") };
    // A folder that holds its own page, such as `classic`, gets that page. Without the closing
    // slash the browser is sent to the address with it, so the page's relative links resolve.
    if safe && candidate.is_dir() && candidate.join("index.html").is_file() && !whole.ends_with('/') {
        return axum::response::Redirect::permanent(&format!("/{relative}/")).into_response();
    }
    let candidate = if candidate.is_dir() { candidate.join("index.html") } else { candidate };
    let path = if candidate.is_file() { candidate } else { assets.join("index.html") };
    match tokio::fs::read(&path).await {
        Ok(bytes) if path.file_name().is_some_and(|name| name == "index.html") => {
            ([(header::CONTENT_TYPE, content_type(&path))], mark_page(bytes)).into_response()
        }
        Ok(bytes) => ([(header::CONTENT_TYPE, content_type(&path))], bytes).into_response(),
        Err(_) => (StatusCode::NOT_FOUND, "not built: run npm run build in metaform/workspace").into_response(),
    }
}

/// Adds `HOST_MARK` to the page: before `</head>`, or at the end when the page has no `</head>`.
/// The page finds the element in either place.
pub fn mark_page(mut page: Vec<u8>) -> Vec<u8> {
    let at = page.windows(7).position(|w| w.eq_ignore_ascii_case(b"</head>")).unwrap_or(page.len());
    page.splice(at..at, HOST_MARK.bytes());
    page
}

/// Listens on 127.0.0.1. A requested port must be free. With no requested port, the host uses
/// `default`, or any free port when `default` is in use.
pub async fn listen(requested: Option<u16>, default: u16) -> std::io::Result<tokio::net::TcpListener> {
    use tokio::net::TcpListener;
    match requested {
        Some(port) => TcpListener::bind(("127.0.0.1", port)).await,
        None => match TcpListener::bind(("127.0.0.1", default)).await {
            Err(e) if e.kind() == std::io::ErrorKind::AddrInUse => TcpListener::bind(("127.0.0.1", 0)).await,
            other => other,
        },
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

    #[tokio::test]
    async fn listen_uses_the_default_port_or_a_free_one() {
        // A port the system chose is free once its listener is dropped, so the test needs no fixed port.
        let free = listen(Some(0), 0).await.unwrap();
        let default = free.local_addr().unwrap().port();
        drop(free);
        let first = listen(None, default).await.unwrap();
        assert_eq!(first.local_addr().unwrap().port(), default, "the default port when it is free");
        let second = listen(None, default).await.unwrap();
        assert_ne!(second.local_addr().unwrap().port(), default, "another port when the default is in use");
        assert!(listen(Some(default), default).await.is_err(), "a requested port is never replaced");
    }

    #[test]
    fn the_page_gets_the_host_mark() {
        let page = String::from_utf8(mark_page(b"<html><head><title>x</title></HEAD><body></body></html>".to_vec())).unwrap();
        assert_eq!(page, format!("<html><head><title>x</title>{HOST_MARK}</HEAD><body></body></html>"));
        let bare = String::from_utf8(mark_page(b"<p>x</p>".to_vec())).unwrap();
        assert_eq!(bare, format!("<p>x</p>{HOST_MARK}"));
    }

    #[test]
    fn a_write_needs_the_hosts_own_origin() {
        let headers = |host: &str, origin: Option<&str>| {
            let mut headers = HeaderMap::new();
            headers.insert(header::HOST, host.parse().unwrap());
            if let Some(origin) = origin {
                headers.insert(header::ORIGIN, origin.parse().unwrap());
            }
            headers
        };
        let host = "127.0.0.1:4170";
        assert_eq!(write_refusal(false, &headers(host, Some("http://127.0.0.1:4170"))), None);
        assert!(write_refusal(true, &headers(host, Some("http://127.0.0.1:4170"))).unwrap().contains("read-only"));
        assert!(write_refusal(false, &headers(host, None)).unwrap().contains("needs an Origin"));
        for other in ["http://localhost:4170", "https://127.0.0.1:4170", "http://127.0.0.1:4171", "http://127.0.0.1:4170/", "null"] {
            assert!(write_refusal(false, &headers(host, Some(other))).unwrap().contains("own page"), "{other}");
        }
    }

    #[test]
    fn the_write_route_takes_one_add_update_or_delete() {
        for write in [json!({"add": {"code.x": {}}}), json!({"update": {}}), json!({"delete": {"code.x": {}}})] {
            assert!(is_write(&write), "{write}");
        }
        for other in [json!({"map": {}}), json!({"code.store": {"name": "renamed"}}), json!({"add": {}, "delete": {}}), json!({}), json!([])] {
            assert!(!is_write(&other), "{other}");
        }
    }

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
