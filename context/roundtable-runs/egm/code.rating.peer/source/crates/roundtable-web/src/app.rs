//! The HTTP surface: the page, a JSON API for the chair, the live event stream and the
//! participant tools endpoint.
//!
//! Security: every /api route needs the chair token (Authorization: Bearer, or `token` in
//! the query for the event stream), and every request must name this server in its Host
//! header (and Origin, when present), which defeats DNS rebinding. Participant tools use
//! their own per-seat tokens and cannot reach the chair API.

use std::collections::HashMap;
use std::convert::Infallible;
use std::io::Write;
use std::net::SocketAddr;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};

use anyhow::Result;
use axum::extract::{Path, Query, Request, State};
use axum::http::{HeaderMap, StatusCode, header};
use axum::middleware::{self, Next};
use axum::response::sse::{Event as SseEvent, Sse};
use axum::response::{Html, IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use bus::Bus;
use futures::{Stream, StreamExt};
use roundtable::TableHandle;
use serde::Deserialize;
use serde_json::{Value, json};
use tokio::sync::mpsc;

use crate::tables;

/// Event history and live subscribers under one lock, so a new stream gets every event
/// exactly once: what was recorded before it registered, then everything after.
#[derive(Default)]
pub struct Hub {
    history: Vec<Value>,
    subscribers: Vec<(Option<String>, mpsc::UnboundedSender<Value>)>,
}

#[derive(Clone)]
pub struct AppState {
    pub bus: Bus,
    pub http: reqwest::Client,
    pub tables: Arc<Mutex<HashMap<String, TableHandle>>>,
    pub hub: Arc<Mutex<Hub>>,
    /// Held in memory only; never written to disk.
    pub openrouter_key: Arc<Mutex<Option<String>>>,
    pub addr: SocketAddr,
    pub data_dir: PathBuf,
    /// The chair credential for this run.
    pub token: String,
}

impl AppState {
    pub fn new(addr: SocketAddr) -> Self {
        let bus = Bus::new();
        let hub = Arc::new(Mutex::new(Hub::default()));
        let tables: Arc<Mutex<HashMap<String, TableHandle>>> = Arc::default();
        let data_dir = std::env::var_os("ROUNDTABLE_HOME")
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from(std::env::var_os("HOME").unwrap_or_default()).join(".roundtable"));
        let _ = std::fs::create_dir_all(&data_dir);

        // The one consumer of the bus for the web layer: history, live streams, accolades and
        // ended-table cleanup all come from this tap.
        let mut tap = bus.tap();
        let (keep, tracked) = (hub.clone(), tables.clone());
        let accolades = data_dir.join("accolades.jsonl");
        let identities = data_dir.join("identities");
        let notices = bus.clone();
        // Seats of each open table, from `roundtable.opened`, to record which harness holds an
        // identity's session when the seat is ready.
        let mut opened: HashMap<String, Value> = HashMap::new();
        tokio::spawn(async move {
            while let Some(envelope) = tap.recv().await {
                let line = roundtable::record::line(&envelope);
                let table = roundtable::record::table_of(&line["data"]);
                // Persistence failures are shown to the chair at that table (fail loudly).
                let loud = |what: &str, error: String| {
                    eprintln!("{what}: {error}");
                    if let Some(id) = &table {
                        notices.publish(roundtable::events::Notice { table: id.clone(), level: "error".into(), text: format!("{what}: {error}") });
                    }
                };
                if envelope.name == "roundtable.opened"
                    && let Some(id) = &table
                {
                    opened.insert(id.clone(), line["data"]["seats"].clone());
                }
                if envelope.name == "roundtable.seat.ready" {
                    let data = &line["data"];
                    let info = table.as_ref().and_then(|id| opened.get(id)).and_then(|seats| seats.as_array()).and_then(|seats| seats.iter().find(|s| s["name"] == data["seat"]));
                    if let Err(error) = save_context(&identities, data, info) {
                        loud("An identity's session could not be recorded", error.to_string());
                    }
                }
                if envelope.name == "roundtable.rating"
                    && let Err(error) = save_rating(&identities, &line["data"])
                {
                    loud("A rating could not be saved to its identity", error.to_string());
                }
                if envelope.name == "roundtable.feedback" {
                    if let Err(error) = save_feedback(&identities, &line["data"]) {
                        loud("Feedback could not be saved to its identity", error.to_string());
                    }
                    let appended = std::fs::OpenOptions::new().create(true).append(true).open(&accolades).and_then(|mut file| writeln!(file, "{line}"));
                    if let Err(error) = appended {
                        loud(&format!("Feedback could not be logged to {}", accolades.display()), error.to_string());
                    }
                }
                if envelope.name == "roundtable.ended"
                    && let Some(id) = &table
                {
                    opened.remove(id);
                    tracked.lock().unwrap().remove(id);
                }
                let mut hub = keep.lock().unwrap();
                hub.subscribers.retain(|(filter, sender)| {
                    filter.is_some() && filter != &table || sender.send(line.clone()).is_ok()
                });
                // Streamed reply text is live-only: the completed reply carries it.
                if envelope.name != "acp.agent.text" {
                    hub.history.push(line);
                }
            }
        });

        let token = std::env::var("ROUNDTABLE_TOKEN").ok().filter(|t| t.len() >= 16).unwrap_or_else(roundtable::random_hex);
        Self {
            bus,
            http: reqwest::Client::builder().user_agent("roundtable/0.1").build().expect("http client"),
            tables,
            hub,
            openrouter_key: Arc::new(Mutex::new(std::env::var("OPENROUTER_API_KEY").ok().filter(|k| !k.is_empty()))),
            addr,
            data_dir,
            token,
        }
    }
}

pub fn router(state: AppState) -> Router {
    let api = Router::new()
        .route("/api/harnesses", get(harnesses))
        .route("/api/models", get(models))
        .route("/api/settings", get(get_settings).post(set_settings))
        .route("/api/tables", get(list_tables).post(create_table))
        .route("/api/tables/{id}/command", post(command))
        .route("/api/events", get(events))
        .route("/api/history", get(history_list))
        .route("/api/identities", get(identities_list))
        .route("/api/history/{id}", get(history_table))
        .layer(middleware::from_fn_with_state(state.clone(), require_chair));
    Router::new()
        .route("/", get(|| async { Html(include_str!("../assets/index.html")) }))
        .route("/favicon.ico", get(|| async { StatusCode::NO_CONTENT }))
        .route("/mcp/{table}/{seat}", post(mcp).get(mcp_other).delete(mcp_other))
        .merge(api)
        .layer(middleware::from_fn_with_state(state.clone(), require_host))
        .with_state(state)
}

pub async fn serve(state: AppState, listener: tokio::net::TcpListener) -> Result<()> {
    axum::serve(listener, router(state)).await?;
    Ok(())
}

/// The Host (and Origin, when sent) must name this server.
async fn require_host(State(state): State<AppState>, request: Request, next: Next) -> Response {
    let port = state.addr.port();
    let allowed = [format!("{}", state.addr), format!("localhost:{port}"), format!("127.0.0.1:{port}"), format!("[::1]:{port}")];
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

#[derive(Deserialize)]
struct TokenQuery {
    token: Option<String>,
    table: Option<String>,
}

async fn require_chair(State(state): State<AppState>, Query(query): Query<TokenQuery>, request: Request, next: Next) -> Response {
    let bearer = bearer(request.headers());
    let given = bearer.or(query.token).unwrap_or_default();
    if !constant_time_eq(given.as_bytes(), state.token.as_bytes()) {
        return (StatusCode::UNAUTHORIZED, Json(json!({"error": "the chair token is missing or wrong"}))).into_response();
    }
    next.run(request).await
}

fn bearer(headers: &HeaderMap) -> Option<String> {
    headers.get(header::AUTHORIZATION)?.to_str().ok()?.strip_prefix("Bearer ").map(str::to_string)
}

fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
    a.len() == b.len() && a.iter().zip(b).fold(0u8, |acc, (x, y)| acc | (x ^ y)) == 0
}

async fn harnesses(State(state): State<AppState>) -> Json<Value> {
    let (entries, note) = tables::catalog(&state.http).await;
    let entries: Vec<Value> = entries
        .into_iter()
        .map(|entry| {
            let mut value = serde_json::to_value(&entry).unwrap_or_default();
            value["defaults"] = json!(roundtable::default_settings(&entry.id));
            value
        })
        .collect();
    Json(json!({"harnesses": entries, "note": note}))
}

async fn models(State(state): State<AppState>) -> Response {
    let key = state.openrouter_key.lock().unwrap().clone();
    match acp_host::models::openrouter_models(&state.http, key.as_deref()).await {
        Ok(models) => Json(json!({"models": models})).into_response(),
        Err(error) => (StatusCode::BAD_GATEWAY, Json(json!({"error": error.to_string()}))).into_response(),
    }
}

async fn get_settings(State(state): State<AppState>) -> Json<Value> {
    Json(json!({"openrouter_key_set": state.openrouter_key.lock().unwrap().is_some(), "data_dir": state.data_dir}))
}

async fn set_settings(State(state): State<AppState>, Json(body): Json<Value>) -> Json<Value> {
    if let Some(key) = body.get("openrouter_key").and_then(Value::as_str) {
        let key = Some(key.trim().to_string()).filter(|k| !k.is_empty());
        *state.openrouter_key.lock().unwrap() = key.clone();
        for handle in state.tables.lock().unwrap().values() {
            handle.send(roundtable::Command::SetJevKey(key.clone()));
        }
    }
    get_settings(State(state)).await
}

async fn list_tables(State(state): State<AppState>) -> Json<Value> {
    let ids: Vec<String> = state.tables.lock().unwrap().keys().cloned().collect();
    Json(json!({"tables": ids}))
}

async fn create_table(State(state): State<AppState>, Json(request): Json<tables::CreateTable>) -> Response {
    match tables::create(&state, request).await {
        Ok(id) => Json(json!({"id": id})).into_response(),
        Err(error) => (StatusCode::BAD_REQUEST, Json(json!({"error": format!("{error:#}")}))).into_response(),
    }
}

async fn command(State(state): State<AppState>, Path(id): Path<String>, Json(body): Json<Value>) -> Response {
    let Some(handle) = state.tables.lock().unwrap().get(&id).cloned() else {
        return (StatusCode::NOT_FOUND, Json(json!({"error": "no such running table"}))).into_response();
    };
    match tables::command(&body) {
        Ok(command) => {
            if handle.send(command) {
                Json(json!({"ok": true})).into_response()
            } else {
                (StatusCode::GONE, Json(json!({"error": "the table has ended"}))).into_response()
            }
        }
        Err(error) => (StatusCode::BAD_REQUEST, Json(json!({"error": error.to_string()}))).into_response(),
    }
}

/// Whether `id` looks like a table id (`t` + hex), so it can name a folder safely.
fn valid_table_id(id: &str) -> bool {
    id.len() <= 40 && id.starts_with('t') && id[1..].chars().all(|c| c.is_ascii_hexdigit()) && id.len() > 1
}

/// Every table recorded on disk, newest first, with a summary for browsing.
async fn history_list(State(state): State<AppState>) -> Json<Value> {
    let dir = state.data_dir.join("tables");
    let tables = tokio::task::spawn_blocking(move || {
        let mut found = Vec::new();
        for entry in std::fs::read_dir(&dir).into_iter().flatten().flatten() {
            let id = entry.file_name().to_string_lossy().to_string();
            if !valid_table_id(&id) {
                continue;
            }
            let Ok(text) = std::fs::read_to_string(entry.path().join("record.jsonl")) else { continue };
            let mut summary = json!({"id": id, "objective": "", "seats": [], "started_ms": 0, "ended": false, "reason": null, "contributions": 0, "topics": 1});
            let mut last_ms = 0;
            for line in text.lines() {
                let Ok(line) = serde_json::from_str::<Value>(line) else { continue };
                last_ms = line["at_ms"].as_u64().unwrap_or(last_ms);
                let data = &line["data"];
                match line["event"].as_str().unwrap_or_default() {
                    "roundtable.opened" => {
                        summary["objective"] = data["objective"].clone();
                        summary["seats"] = json!(data["seats"].as_array().map(|s| s.iter().map(|x| x["name"].clone()).collect::<Vec<_>>()).unwrap_or_default());
                        summary["started_ms"] = line["at_ms"].clone();
                    }
                    "roundtable.contribution" if data["accepted"] == true => {
                        summary["contributions"] = json!(summary["contributions"].as_u64().unwrap_or(0) + 1);
                    }
                    "roundtable.topic" => summary["topics"] = data["index"].clone(),
                    "roundtable.ended" => {
                        summary["ended"] = json!(true);
                        summary["reason"] = data["reason"].clone();
                    }
                    _ => {}
                }
            }
            summary["last_ms"] = json!(last_ms);
            found.push(summary);
        }
        found.sort_by_key(|s| std::cmp::Reverse(s["started_ms"].as_u64().unwrap_or(0)));
        found
    })
    .await
    .unwrap_or_default();
    Json(json!({"tables": tables}))
}

/// One recorded table's events, for replay in the page. Streamed reply chunks are left out
/// (each completed reply carries its text).
async fn history_table(State(state): State<AppState>, Path(id): Path<String>) -> Response {
    if !valid_table_id(&id) {
        return (StatusCode::BAD_REQUEST, Json(json!({"error": "not a table id"}))).into_response();
    }
    let path = state.data_dir.join("tables").join(&id).join("record.jsonl");
    match tokio::fs::read_to_string(&path).await {
        Ok(text) => {
            let lines: Vec<Value> = text
                .lines()
                .filter_map(|line| serde_json::from_str::<Value>(line).ok())
                .filter(|line| line["event"] != "acp.agent.text")
                .collect();
            Json(json!({"id": id, "events": lines})).into_response()
        }
        Err(_) => (StatusCode::NOT_FOUND, Json(json!({"error": "no record for that table"}))).into_response(),
    }
}

/// Snapshot the history and register a live subscriber under one lock.
pub fn subscribe(hub: &Mutex<Hub>, table: Option<String>) -> (Vec<Value>, mpsc::UnboundedReceiver<Value>) {
    let (sender, receiver) = mpsc::unbounded_channel();
    let mut hub = hub.lock().unwrap();
    let past = hub
        .history
        .iter()
        .filter(|line| table.is_none() || roundtable::record::table_of(&line["data"]) == table)
        .cloned()
        .collect();
    hub.subscribers.push((table, sender));
    (past, receiver)
}

/// History, then live events, with no gap and no repeat. `?table=` limits it to one table.
async fn events(State(state): State<AppState>, Query(query): Query<TokenQuery>) -> Sse<impl Stream<Item = Result<SseEvent, Infallible>>> {
    let (past, receiver) = subscribe(&state.hub, query.table.clone());
    let live = futures::stream::unfold(receiver, |mut receiver| async move { receiver.recv().await.map(|line| (line, receiver)) });
    let stream = futures::stream::iter(past).chain(live).map(|line| Ok(SseEvent::default().data(line.to_string())));
    // No keepalive: it is a periodic timer (owner: "there is no such thing as a timer or a deliberation period"). Events flow when something
    // happens; if an intermediary drops an idle stream, EventSource reconnects and the
    // history replay fills the gap (F10).
    Sse::new(stream)
}

/// MCP Streamable HTTP: each POST carries one JSON-RPC message and gets a JSON reply. The
/// seat's token comes in the Authorization header.
async fn mcp(State(state): State<AppState>, Path((table, seat)): Path<(String, String)>, headers: HeaderMap, body: String) -> Response {
    let Some(handle) = state.tables.lock().unwrap().get(&table).cloned() else {
        return StatusCode::NOT_FOUND.into_response();
    };
    if !handle.seat_token_valid(&seat, &bearer(&headers).unwrap_or_default()) {
        return StatusCode::UNAUTHORIZED.into_response();
    }
    let message: Value = match serde_json::from_str(&body) {
        Ok(message) => message,
        Err(error) => {
            return Json(json!({"jsonrpc": "2.0", "id": null, "error": {"code": -32700, "message": error.to_string()}})).into_response();
        }
    };
    let replies: Vec<Value> = match &message {
        Value::Array(batch) => batch.iter().filter_map(|m| roundtable::mcp::handle(&handle, &seat, m)).collect(),
        single => roundtable::mcp::handle(&handle, &seat, single).into_iter().collect(),
    };
    match (message.is_array(), replies.len()) {
        (_, 0) => StatusCode::ACCEPTED.into_response(),
        (false, _) => Json(replies.into_iter().next().unwrap()).into_response(),
        (true, _) => Json(Value::Array(replies)).into_response(),
    }
}

/// No server-initiated stream or session teardown is offered.
async fn mcp_other() -> StatusCode {
    StatusCode::METHOD_NOT_ALLOWED
}

/// Print one table's chat to stdout until it ends (for `roundtable run`).
pub async fn print_chat(state: &AppState, id: &str) {
    let mut tap = state.bus.tap();
    while let Some(envelope) = tap.recv().await {
        let line = roundtable::record::line(&envelope);
        let data = &line["data"];
        if roundtable::record::table_of(data).as_deref() != Some(id) {
            continue;
        }
        let seat = data["seat"].as_str().unwrap_or("");
        match envelope.name {
            "roundtable.contribution" if data["accepted"] == true => println!("[{}] {seat}: {}", data["id"].as_str().unwrap_or(""), data["text"].as_str().unwrap_or("")),
            "roundtable.contribution" => println!("  (vetoed {seat}: {})", data["reasons"]),
            "roundtable.topic" => println!("\n== Topic #{}: {}\n", data["index"], data["topic"].as_str().unwrap_or("")),
            "roundtable.chair" => println!("CHAIR: {}", data["text"].as_str().unwrap_or("")),
            "roundtable.pass" | "roundtable.work.started" | "roundtable.work.finished" | "roundtable.skipped"
            | "roundtable.seat.ready" | "roundtable.seat.failed" | "roundtable.seat.gone" | "roundtable.notice"
            | "roundtable.turn.failed" | "roundtable.feedback" => println!("  · {} {}", envelope.name, data),
            "roundtable.ended" => {
                println!("== ended: {}", data["reason"]);
                break;
            }
            _ => {}
        }
    }
}

/// The file that holds the profile of the identity whose genesis session is `session`. An
/// identity is its session: the genesis name is derived from the session id and can collide
/// (65,536 names), so profiles are keyed by session and keep the name inside. Bytes outside
/// `[A-Za-z0-9_-]` are written as `%XX`, so no session id can name a path outside `dir`.
fn profile_path(dir: &std::path::Path, session: &str) -> std::io::Result<PathBuf> {
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
fn update_profile(dir: &std::path::Path, session: &str, name: &str, change: impl FnOnce(&mut Value)) -> std::io::Result<()> {
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
fn save_rating(dir: &std::path::Path, data: &Value) -> std::io::Result<()> {
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
fn save_context(dir: &std::path::Path, ready: &Value, seat: Option<&Value>) -> std::io::Result<()> {
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
fn save_feedback(dir: &std::path::Path, data: &Value) -> std::io::Result<()> {
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

async fn identities_list(State(state): State<AppState>) -> Json<Value> {
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

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::Body;
    use tower::ServiceExt;

    fn state() -> AppState {
        let mut state = AppState::new("127.0.0.1:4999".parse().unwrap());
        state.token = "a".repeat(64);
        state
    }

    async fn status(state: &AppState, method: &str, uri: &str, headers: &[(&str, &str)]) -> StatusCode {
        let mut request = axum::http::Request::builder().method(method).uri(uri).header("host", "127.0.0.1:4999");
        for (name, value) in headers {
            request = request.header(*name, *value);
        }
        router(state.clone()).oneshot(request.body(Body::empty()).unwrap()).await.unwrap().status()
    }

    #[tokio::test]
    async fn the_chair_api_needs_the_token_and_this_host() {
        let state = state();
        let token = format!("Bearer {}", state.token);
        assert_eq!(status(&state, "GET", "/api/tables", &[]).await, StatusCode::UNAUTHORIZED);
        assert_eq!(status(&state, "GET", "/api/tables", &[("authorization", "Bearer wrong")]).await, StatusCode::UNAUTHORIZED);
        assert_eq!(status(&state, "GET", "/api/tables", &[("authorization", &token)]).await, StatusCode::OK);
        assert_eq!(status(&state, "GET", &format!("/api/tables?token={}", state.token), &[]).await, StatusCode::OK);
        // DNS rebinding: right token, wrong Host or Origin.
        let mut request = axum::http::Request::builder().uri("/api/tables").header("host", "evil.example:4999").header("authorization", &token);
        request = request.header("x", "y");
        let rebound = router(state.clone()).oneshot(request.body(Body::empty()).unwrap()).await.unwrap().status();
        assert_eq!(rebound, StatusCode::FORBIDDEN);
        assert_eq!(status(&state, "GET", "/api/tables", &[("authorization", &token), ("origin", "http://evil.example")]).await, StatusCode::FORBIDDEN);
        // The page itself is public; it carries no data.
        assert_eq!(status(&state, "GET", "/", &[]).await, StatusCode::OK);
        // Creating a table (which can launch a command) is behind the token too.
        assert_eq!(status(&state, "POST", "/api/tables", &[]).await, StatusCode::UNAUTHORIZED);
        // The tools endpoint does not accept the chair token as a seat credential.
        assert_eq!(status(&state, "POST", "/mcp/none/Sol", &[("authorization", &token)]).await, StatusCode::NOT_FOUND);
    }

    #[tokio::test]
    async fn past_tables_are_listed_and_replayed_from_their_records() {
        let mut state = state();
        let home = std::env::temp_dir().join(format!("rt-history-{}", std::process::id()));
        let table = home.join("tables").join("tabc123");
        std::fs::create_dir_all(&table).unwrap();
        std::fs::write(
            table.join("record.jsonl"),
            [
                json!({"seq": 1, "at_ms": 10, "event": "roundtable.opened", "data": {"table": "tabc123", "objective": "Old work", "seats": [{"name": "Sol"}]}}),
                json!({"seq": 2, "at_ms": 11, "event": "acp.agent.text", "data": {"harness": "tabc123/Sol", "text": "chunk"}}),
                json!({"seq": 3, "at_ms": 12, "event": "roundtable.contribution", "data": {"table": "tabc123", "seat": "Sol", "accepted": true, "text": "x"}}),
                json!({"seq": 4, "at_ms": 13, "event": "roundtable.ended", "data": {"table": "tabc123", "reason": "ended by the chair"}}),
            ]
            .iter()
            .map(|l| l.to_string() + "\n")
            .collect::<String>(),
        )
        .unwrap();
        state.data_dir = home;
        let get = |uri: &str| {
            let state = state.clone();
            let uri = uri.to_string();
            async move {
                let request = axum::http::Request::builder().uri(uri).header("host", "127.0.0.1:4999").header("authorization", format!("Bearer {}", state.token));
                let response = router(state).oneshot(request.body(Body::empty()).unwrap()).await.unwrap();
                let status = response.status();
                let bytes = axum::body::to_bytes(response.into_body(), 1 << 20).await.unwrap();
                (status, serde_json::from_slice::<Value>(&bytes).unwrap_or(Value::Null))
            }
        };
        let (status, list) = get("/api/history").await;
        assert_eq!(status, StatusCode::OK);
        let first = &list["tables"][0];
        assert_eq!((first["id"].as_str(), first["objective"].as_str(), first["ended"].as_bool(), first["contributions"].as_u64()), (Some("tabc123"), Some("Old work"), Some(true), Some(1)));
        let (_, replay) = get("/api/history/tabc123").await;
        assert_eq!(replay["events"].as_array().unwrap().len(), 3, "streamed chunks are left out");
        assert_eq!(get("/api/history/..%2Fetc").await.0, StatusCode::BAD_REQUEST);
        assert_eq!(status_of(&state_with_token(), "/favicon.ico").await, StatusCode::NO_CONTENT);
    }

    fn state_with_token() -> AppState {
        state()
    }

    async fn status_of(state: &AppState, uri: &str) -> StatusCode {
        status(state, "GET", uri, &[]).await
    }

    #[tokio::test(flavor = "multi_thread")]
    async fn a_stream_opened_mid_flight_gets_every_event_exactly_once() {
        let state = state();
        let bus = state.bus.clone();
        let publisher = std::thread::spawn(move || {
            for n in 0..3000 {
                bus.publish(roundtable::events::Notice { table: "t".into(), level: "info".into(), text: n.to_string() });
            }
        });
        tokio::time::sleep(std::time::Duration::from_millis(2)).await;
        let (past, mut live) = subscribe(&state.hub, Some("t".into()));
        publisher.join().unwrap();
        let mut seqs: Vec<u64> = past.iter().map(|l| l["seq"].as_u64().unwrap()).collect();
        while seqs.len() < 3000 {
            let line = tokio::time::timeout(std::time::Duration::from_secs(5), live.recv()).await.unwrap().unwrap();
            seqs.push(line["seq"].as_u64().unwrap());
        }
        assert_eq!(seqs, (1..=3000).collect::<Vec<u64>>(), "no gap, no repeat, in order");
    }

    // Review round 2, F08: a profile that cannot be parsed is an error and is left untouched;
    // a missing one starts empty; saving leaves no temporary file behind.
    #[test]
    fn identity_profiles_are_never_silently_replaced() {
        let dir = std::env::temp_dir().join(format!("roundtable-identities-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        let rating = json!({"table": "t1", "from_name": "GenuineSilver", "to_name": "SteelForce", "to_session": "s-1", "ratings": {}, "points": 80.0});
        save_rating(&dir, &rating).unwrap();
        save_rating(&dir, &rating).unwrap();
        let profile: Value = serde_json::from_str(&std::fs::read_to_string(dir.join("s-1.json")).unwrap()).unwrap();
        assert_eq!((profile["points"].as_f64(), profile["name"].as_str()), (Some(160.0), Some("SteelForce")));
        assert_eq!(profile["ratings"].as_array().unwrap().len(), 2);
        assert!(!dir.join(".s-1.json.tmp").exists());

        std::fs::write(dir.join("s-1.json"), "{ truncated").unwrap();
        let error = save_rating(&dir, &rating).unwrap_err();
        assert_eq!(error.kind(), std::io::ErrorKind::InvalidData);
        assert_eq!(std::fs::read_to_string(dir.join("s-1.json")).unwrap(), "{ truncated");

        let feedback = json!({"table": "t1", "from_name": "GenuineSilver", "to_name": "NewName", "to_session": "s-2", "ratings": {"Coordination": 4}, "note": "kept us on track"});
        save_feedback(&dir, &feedback).unwrap();
        let profile: Value = serde_json::from_str(&std::fs::read_to_string(dir.join("s-2.json")).unwrap()).unwrap();
        assert_eq!(profile["points"], 0.0, "feedback adds no points");
        assert_eq!(profile["feedback"][0]["note"], "kept us on track");
        assert!(save_feedback(&dir, &json!({"to_name": "../escape", "to_session": "s-3"})).is_err());
        // A session id cannot name a path outside the directory.
        assert_eq!(profile_path(&dir, "../x/y").unwrap(), dir.join("%2E%2E%2Fx%2Fy.json"));
        assert!(profile_path(&dir, "").is_err());
        std::fs::remove_dir_all(&dir).unwrap();
    }

    // Audit D11: two identities whose sessions derive the same genesis name keep separate
    // profiles; a profile file never takes another identity's ratings.
    #[test]
    fn identities_with_the_same_name_keep_separate_profiles() {
        let dir = std::env::temp_dir().join(format!("roundtable-collide-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        let rate = |session: &str, points: f64| json!({"table": "t1", "from_name": "Ada", "to_name": "HunterChaos", "to_session": session, "ratings": {}, "points": points});
        save_rating(&dir, &rate("s-a", 50.0)).unwrap();
        save_rating(&dir, &rate("s-b", 90.0)).unwrap();
        let store = FileIdentities { dir: dir.clone() };
        let a = roundtable::Identities::profile(&store, "s-a").unwrap().unwrap();
        let b = roundtable::Identities::profile(&store, "s-b").unwrap().unwrap();
        assert_eq!((a.score, b.score), (50.0, 90.0));
        let other = json!({"table": "t1", "from_name": "Ada", "to_name": "OtherName", "to_session": "s-a", "ratings": {}, "points": 1.0});
        assert_eq!(save_rating(&dir, &other).unwrap_err().kind(), std::io::ErrorKind::InvalidData, "a session's profile holds one name");
        std::fs::remove_dir_all(&dir).unwrap();
    }

    // An identity's session and harness are recorded so a later table can resume it.
    #[test]
    fn identity_contexts_are_recorded_for_resuming() {
        let dir = std::env::temp_dir().join(format!("roundtable-contexts-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        let ready = json!({"table": "t1", "seat": "Sol", "name": "AlloyedReaper", "session": "s-1"});
        let seat = json!({"name": "Sol", "harness": "codex-acp", "settings": {"model": "gpt-6.1-sol"}});
        save_context(&dir, &ready, Some(&seat)).unwrap();
        save_context(&dir, &ready, Some(&seat)).unwrap();
        let profile: Value = serde_json::from_str(&std::fs::read_to_string(dir.join("s-1.json")).unwrap()).unwrap();
        assert_eq!(profile["contexts"].as_array().unwrap().len(), 1, "recorded once");
        assert_eq!(profile["contexts"][0]["harness"], "codex-acp");
        let store = FileIdentities { dir: dir.clone() };
        let found = roundtable::Identities::profile(&store, "s-1").unwrap().unwrap();
        assert_eq!((found.ratings, found.sessions), (0, 0));
        assert!(roundtable::Identities::profile(&store, "s-none").unwrap().is_none());
        std::fs::remove_dir_all(&dir).unwrap();
    }
}
