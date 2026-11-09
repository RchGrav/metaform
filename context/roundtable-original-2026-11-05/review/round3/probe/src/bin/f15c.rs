use std::sync::{Arc, Mutex};
use std::time::Duration;
use acp_host::LaunchSpec;
use acp_host::events::ToolActivity;
use bus::Bus;
use roundtable::{SeatConfig, TableConfig};
use serde_json::{json, Value};

fn seat(name: &str, script: Value, session: Option<&str>) -> SeatConfig {
    let mut launch = LaunchSpec::new(std::env::var("FAKE_BIN").unwrap(), Vec::<String>::new());
    launch.env.insert("FAKE_SCRIPT".into(), script.to_string());
    launch.env.insert("FAKE_TOPIC".into(), format!("{name}'s topic"));
    if let Some(s) = session { launch.env.insert("FAKE_SESSION".into(), s.into()); }
    SeatConfig { name: name.into(), harness: "fake".into(), launch, settings: vec![], share_openrouter_key: false }
}

async fn fake_jev() -> roundtable::jev::Jev {
    let _seen = Arc::new(Mutex::new(Vec::<Value>::new()));
    let app = axum::Router::new().route("/decisions", axum::routing::post(move |axum::Json(body): axum::Json<Value>| async move {
        let answers: serde_json::Map<String, Value> = body["questions"].as_object().unwrap().keys()
            .map(|k| (k.clone(), json!({"noul": 0.95}))).collect();
        (axum::http::StatusCode::OK, axum::Json(json!({"answers": answers})))
    }));
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });
    let mut jev = roundtable::jev::Jev::new(reqwest::Client::new(), Some("test-key".into()));
    jev.url = format!("http://{addr}/decisions");
    jev
}

// Judging ON with a key: worker works then contributes; on_judged must record the acceptance
// (async after-work path). The round must close productive.
#[tokio::main(flavor = "multi_thread")]
async fn main() {
    let worker = seat("Worker", json!([
        {"reply": "", "first_chunk": "working", "delay_ms": 900, "tool_then": "my accepted contribution"},
        {"reply": "PASS"}
    ]), Some("worker-f15c"));
    let other = seat("Other", json!([{"reply": "", "delay_ms": 1400}, {"reply": "PASS"}]), Some("other-f15c"));
    let bus = Bus::new();
    let mut tap = bus.tap();
    let jev = fake_jev().await;
    let cfg = TableConfig { objective: "Probe".into(), topic: None,
        workspace: std::env::temp_dir().join("rt-probe-f15c"),
        scope: None, seats: vec![worker, other], judging: true, base_allowance: 512 };
    let handle = roundtable::spawn("f15c".into(), cfg, bus.clone(), jev, None).unwrap();

    let mut worker_sent = None;
    let deadline = tokio::time::Instant::now() + Duration::from_secs(12);
    loop {
        let next = tokio::time::timeout_at(deadline, tap.recv()).await.ok().flatten();
        let Some(env) = next else { break };
        let d = env.to_json().unwrap();
        if env.name == "acp.prompt.sent" && d["harness"] == "f15c/Worker" { worker_sent = Some(d); break; }
    }
    let p = worker_sent.unwrap();
    bus.publish(ToolActivity {
        harness: "f15c/Worker".into(), session: p["session"].as_str().unwrap().into(),
        prompt: p["prompt"].as_u64(), tool_call: "t1".into(), title: None,
        kind: Some("edit".into()), status: None, locations: vec![],
    });
    let mut after_accepted = false;
    let mut rc = None;
    let mut toggle_observed = false;
    let deadline = tokio::time::Instant::now() + Duration::from_secs(12);
    loop {
        let next = tokio::time::timeout_at(deadline, tap.recv()).await.ok().flatten();
        let Some(env) = next else { break };
        let d = env.to_json().unwrap();
        if env.name == "roundtable.contribution" && d["after_work"] == true && d["accepted"] == true { after_accepted = true; }
        if env.name == "roundtable.settings" && d["judging"] == true { toggle_observed = true; }
        if env.name == "roundtable.round" { rc = Some(d); break; }
    }
    handle.send(roundtable::Command::End);
    let may = rc.as_ref().map(|d| d["topic_may_advance"].as_bool().unwrap_or(true));
    println!("async after-work accepted (judged): {after_accepted}");
    println!("round topic_may_advance: {may:?} (must be false if acceptance recorded)");
    let ok = after_accepted && may == Some(false);
    println!("F15 async after-work path records acceptance once: {ok}");
    std::process::exit(if ok {0} else {1});
}
