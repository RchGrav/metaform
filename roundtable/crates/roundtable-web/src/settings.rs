//! The chair's settings API, behind the chair token like every /api route:
//!
//!   GET    /api/settings/list      every setting: value, default, source, allowed values, gate
//!   GET    /api/settings/{key}     one setting
//!   PUT    /api/settings/{key}     body {"value": "..."}: save it; reports old and new
//!   DELETE /api/settings/{key}     restore the default ("all" restores every default)
//!
//! A saved setting applies to tables created afterwards; a running table keeps what it
//! started with. A refused value answers 400 with the allowed form. Agents cannot reach this.

use std::collections::BTreeMap;

use axum::Json;
use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use serde_json::{Value, json};

use crate::app::AppState;

fn refused(error: String) -> Response {
    let status = if error.starts_with("no setting is called") { StatusCode::NOT_FOUND } else { StatusCode::BAD_REQUEST };
    (status, Json(json!({"error": error}))).into_response()
}

pub async fn list(State(state): State<AppState>) -> Response {
    match state.settings.list(&BTreeMap::new()) {
        Ok(rows) => Json(json!({"settings": rows})).into_response(),
        Err(error) => refused(error),
    }
}

pub async fn get(State(state): State<AppState>, Path(key): Path<String>) -> Response {
    match state.settings.list(&BTreeMap::new()).map(|rows| rows.into_iter().find(|r| r.key == key)) {
        Ok(Some(row)) => Json(json!(row)).into_response(),
        Ok(None) => refused(format!("no setting is called {key:?}")),
        Err(error) => refused(error),
    }
}

pub async fn set(State(state): State<AppState>, Path(key): Path<String>, Json(body): Json<Value>) -> Response {
    let value = match body.get("value") {
        Some(Value::String(s)) => s.clone(),
        Some(Value::Bool(b)) => if *b { "on" } else { "off" }.to_string(),
        Some(Value::Number(n)) => n.to_string(),
        _ => return refused("the body must be {\"value\": \"...\"}".into()),
    };
    match state.settings.set(&key, &value) {
        Ok(change) => Json(json!({"changed": [change]})).into_response(),
        Err(error) => refused(error),
    }
}

pub async fn unset(State(state): State<AppState>, Path(key): Path<String>) -> Response {
    match state.settings.unset(&key) {
        Ok(changes) => Json(json!({"changed": changes})).into_response(),
        Err(error) => refused(error),
    }
}
