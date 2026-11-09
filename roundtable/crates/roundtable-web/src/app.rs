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

use crate::identities::{identities_list, save_context, save_feedback, save_rating};
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
    /// The chair's saved settings (see `roundtable::settings`).
    pub settings: Arc<roundtable::settings::Store>,
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

        let (settings, problems) = roundtable::settings::Store::open(data_dir.join("settings.json"));
        for problem in problems {
            eprintln!("settings: {problem}");
        }
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
            settings: Arc::new(settings),
        }
    }
}

pub fn router(state: AppState) -> Router {
    let api = Router::new()
        .route("/api/harnesses", get(harnesses))
        .route("/api/models", get(models))
        .route("/api/settings", get(get_settings).post(set_settings))
        .route("/api/settings/list", get(crate::settings::list))
        .route("/api/settings/{key}", get(crate::settings::get).put(crate::settings::set).delete(crate::settings::unset))
        .route("/api/tables", get(list_tables).post(create_table))
        .route("/api/tables/{id}/command", post(command))
        .route("/api/events", get(events))
        .route("/api/history", get(history_list))
        .route("/api/identities", get(identities_list))
        .route("/api/history/{id}", get(history_table))
        .layer(middleware::from_fn_with_state(state.clone(), require_chair));
    Router::new()
        .route("/", get(|| async { Html(include_str!("../assets/index.html")) }))
        .route("/settings", get(|| async { Html(include_str!("../assets/settings.html")) }))
        .route("/app.js", get(|| async { ([(header::CONTENT_TYPE, "text/javascript; charset=utf-8")], include_str!("../assets/app.js")) }))
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
            "roundtable.contribution" => println!("  ({} {seat}: {})", if data["judged"] == true { "rejected" } else { "not shared" }, data["reasons"]),
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

#[cfg(test)]
#[path = "app_tests.rs"]
mod tests;
