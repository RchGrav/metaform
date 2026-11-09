use std::sync::Arc;
use std::time::Duration;
use acp_host::LaunchSpec;
use acp_host::events::ToolActivity;
use bus::Bus;
use roundtable::{SeatConfig, TableConfig};
use serde_json::json;

fn seat(name: &str, script: serde_json::Value) -> SeatConfig {
    let mut launch = LaunchSpec::new(std::env::var("FAKE_BIN").unwrap(), Vec::<String>::new());
    launch.env.insert("FAKE_SCRIPT".into(), script.to_string());
    launch.env.insert("FAKE_TOPIC".into(), format!("{name}'s topic"));
    SeatConfig { name: name.into(), harness: "fake".into(), launch, settings: vec![], share_openrouter_key: false }
}
fn cfg(seats: Vec<SeatConfig>) -> TableConfig {
    TableConfig { objective: "Probe".into(), topic: None,
        workspace: std::env::temp_dir().join("rt-probe-f15"),
        scope: None, seats, judging: false, base_allowance: 512 }
}

// A worker accepts its contribution immediately (judging off); the other passes. After the
// round closes productive, toggling judging on must not advance the topic as if the round were
// nonproductive.
#[tokio::main(flavor = "multi_thread")]
async fn main() {
    let worker = seat("Worker", json!([
        {"reply": "my accepted contribution"}, // floor: contributes, unjudged -> accepted
        {"reply": "PASS"}
    ]));
    let other = seat("Other", json!([{"reply": "PASS"}]));
    let bus = Bus::new();
    let mut tap = bus.tap();
    let jev = roundtable::jev::Jev::new(reqwest::Client::new(), None);
    let handle = roundtable::spawn("f15".into(), cfg(vec![worker, other]), bus.clone(), jev, None).unwrap();

    // Let one full round run with judging off and capture the round outcome.
    let mut saw_accept = false;
    let mut round_closed = None;
    let deadline = tokio::time::Instant::now() + Duration::from_secs(8);
    loop {
        let next = tokio::time::timeout_at(deadline, tap.recv()).await.ok().flatten();
        let Some(env) = next else { break };
        let d = env.to_json().unwrap();
        if roundtable::record::table_of(&d).as_deref() != Some("f15") { continue; }
        if env.name == "roundtable.contribution" && d["accepted"] == true { saw_accept = true; }
        if env.name == "roundtable.round" { round_closed = Some(d); break; }
    }
    handle.send(roundtable::Command::End);
    let rc = round_closed.map(|d| d["topic_may_advance"].as_bool().unwrap_or(false));
    println!("saw accepted contribution: {saw_accept}");
    println!("round.closed topic_may_advance: {rc:?} (judging off, must be false)");
    let ok = saw_accept && rc == Some(false);
    println!("F15 immediate acceptance counted, no spurious advance: {ok}");
    std::process::exit(if ok {0} else {1});
}
