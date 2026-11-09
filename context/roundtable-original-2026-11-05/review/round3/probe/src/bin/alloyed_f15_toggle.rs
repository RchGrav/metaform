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
        workspace: std::env::temp_dir().join("rt-probe-alloyed-toggle"),
        scope: None, seats, judging: false, base_allowance: 512 }
}

// The worker starts a tool (its opportunity is counted as SkippedWorking), then returns an
// accepted contribution AFTER work. With judging off that acceptance is immediate. The round
// must close productive (topic_may_advance=false and the acceptance recorded), which only
// happens if resolve_reply recorded the after-work acceptance.
#[tokio::main(flavor = "multi_thread")]
async fn main() {
    let worker = seat("Worker", json!([
        {"reply": ""},
        {"reply": "", "first_chunk": "working", "delay_ms": 800, "tool_then": "here is my accepted contribution"},
        {"reply": "PASS"}
    ]));
    let other = seat("Other", json!([{"reply": ""}, {"reply": "", "delay_ms": 1200}, {"reply": "PASS"}]));
    let bus = Bus::new();
    let mut tap = bus.tap();
    let mut jev = roundtable::jev::Jev::new(reqwest::Client::new(), Some("synthetic-test-key".into()));
    jev.url = "http://127.0.0.1:9/decisions".into();
    let handle = roundtable::spawn("alloyedtoggle".into(), cfg(vec![worker, other]), bus.clone(), jev, None).unwrap();

    // Wait for the worker's floor prompt; inject a tool activity to make it Working.
    let mut worker_sent = None;
    let mut initial_nonproductive_round = false;
    let mut accepter = None;
    let deadline = tokio::time::Instant::now() + Duration::from_secs(10);
    loop {
        let next = tokio::time::timeout_at(deadline, tap.recv()).await.ok().flatten();
        let Some(env) = next else { break };
        let d = env.to_json().unwrap();
        if env.name == "roundtable.round" { initial_nonproductive_round = true; }
        if initial_nonproductive_round && env.name == "acp.prompt.sent" && d["harness"] == "alloyedtoggle/Worker" { worker_sent = Some(d); break; }
    }
    let p = worker_sent.unwrap();
    bus.publish(ToolActivity {
        harness: "alloyedtoggle/Worker".into(), session: p["session"].as_str().unwrap().into(),
        prompt: p["prompt"].as_u64(), tool_call: "t1".into(), title: None,
        kind: Some("edit".into()), status: None, locations: vec![],
    });
    let mut rc = None;
    let mut toggle_observed = false;
    let deadline = tokio::time::Instant::now() + Duration::from_secs(10);
    loop {
        let next = tokio::time::timeout_at(deadline, tap.recv()).await.ok().flatten();
        let Some(env) = next else { break };
        let d = env.to_json().unwrap();
        if env.name == "roundtable.contribution" && d["after_work"] == true && d["accepted"] == true {
            accepter = Some(d.clone());
            handle.send(roundtable::Command::SetJudging(true));
        }
        if env.name == "roundtable.settings" && d["judging"] == true { toggle_observed = true; }
        if env.name == "roundtable.round" { rc = Some(d); break; }
    }
    handle.send(roundtable::Command::End);
    let after = accepter.is_some();
    let may = rc.as_ref().map(|d| d["topic_may_advance"].as_bool().unwrap_or(true));
    println!("after-work accepted contribution seen: {after}");
    println!("round topic_may_advance: {may:?} (must be false: acceptance recorded -> productive)");
    println!("judging enabled before round closed: {toggle_observed}");
    let ok = initial_nonproductive_round && after && toggle_observed && may == Some(false);
    println!("F15 after-work acceptance recorded (no stale nonproductive): {ok}");
    std::process::exit(if ok {0} else {1});
}
