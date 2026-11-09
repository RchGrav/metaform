//! Tests of the HTTP surface and identity storage.

use super::*;
use crate::identities::*;
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

/// The chair's settings API: a change reports old and new, a bad value is refused with the
/// allowed form, the list shows each value's source, a reset restores the default, and only
/// the chair token reaches it.
#[tokio::test]
async fn the_chair_changes_settings_through_the_api() {
    let mut state = state();
    // Never the owner's real settings file.
    let file = std::env::temp_dir().join(format!("roundtable-web-settings-{}.json", std::process::id()));
    let _ = std::fs::remove_file(&file);
    state.settings = Arc::new(roundtable::settings::Store::open(file).0);
    let token = format!("Bearer {}", state.token);
    let call = |method: &str, uri: &str, body: Option<Value>| {
        let request = axum::http::Request::builder().method(method).uri(uri).header("host", "127.0.0.1:4999").header("authorization", &token).header("content-type", "application/json");
        let request = request.body(body.map(|b| Body::from(b.to_string())).unwrap_or_default()).unwrap();
        let app = router(state.clone());
        async move {
            let response = app.oneshot(request).await.unwrap();
            let status = response.status();
            let bytes = axum::body::to_bytes(response.into_body(), usize::MAX).await.unwrap();
            (status, serde_json::from_slice::<Value>(&bytes).unwrap_or(Value::Null))
        }
    };

    let (code, body) = call("PUT", "/api/settings/shutdown.force_stop", Some(json!({"value": "off"}))).await;
    assert_eq!(code, StatusCode::OK, "{body}");
    assert_eq!(body["changed"][0], json!({"key": "shutdown.force_stop", "old": "on", "new": "off"}));
    let (code, body) = call("PUT", "/api/settings/table.rounds", Some(json!({"value": "-3"}))).await;
    assert_eq!(code, StatusCode::BAD_REQUEST);
    assert!(body["error"].as_str().unwrap().contains("or off"), "{body}");
    assert_eq!(call("GET", "/api/settings/no.such", None).await.0, StatusCode::NOT_FOUND);

    let (_, body) = call("GET", "/api/settings/list", None).await;
    let row = |key: &str| body["settings"].as_array().unwrap().iter().find(|r| r["key"] == key).cloned().unwrap();
    assert_eq!((row("shutdown.force_stop")["source"].clone(), row("table.rounds")["source"].clone()), (json!("saved"), json!("default")));
    assert_eq!(row("permissions.execute")["gate"], "RT-G18");

    let (_, body) = call("DELETE", "/api/settings/all", None).await;
    assert_eq!(body["changed"][0]["new"], "on");
    assert_eq!(status(&state, "GET", "/api/settings/list", &[]).await, StatusCode::UNAUTHORIZED);
    assert_eq!(status(&state, "GET", "/settings", &[]).await, StatusCode::OK, "the page is public; it carries no data");
}
