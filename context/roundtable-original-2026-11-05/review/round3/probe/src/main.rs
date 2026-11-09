
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

#[tokio::main(flavor = "multi_thread")]
async fn main() {
    let base: usize = 1537;
    let busy = seat("Busy", json!([{"reply": "done working", "delay_ms": 3000}, {"reply": "PASS"}]));
    let free = seat("Free", json!([{"reply": "reviewed", "delay_ms": 200}, {"reply": "PASS"}]));
    let cfg = TableConfig {
        objective: "Probe".into(), topic: None,
        workspace: std::env::temp_dir().join("rt-probe-f13"),
        scope: None, seats: vec![busy, free], judging: false, base_allowance: base,
    };
    let bus = Bus::new();
    let mut tap = bus.tap();
    let jev = roundtable::jev::Jev::new(reqwest::Client::new(), None);
    let handle = roundtable::spawn("f13".into(), cfg, bus.clone(), jev, None).unwrap();
    // Wait for Busy's floor+tool activity, then trigger a review for Free.
    let mut busy_sent = None;
    while let Some(env) = tap.recv().await {
        let d = env.to_json().unwrap();
        if env.name == "acp.prompt.sent" && d["harness"] == "f13/Busy" { busy_sent = Some(d); break; }
    }
    let p = busy_sent.unwrap();
    bus.publish(ToolActivity {
        harness: "f13/Busy".into(), session: p["session"].as_str().unwrap().into(),
        prompt: p["prompt"].as_u64(), tool_call: "t1".into(), title: None,
        kind: Some("edit".into()), status: None, locations: vec![],
    });
    let mut review_prompt = None;
    let deadline = tokio::time::Instant::now() + Duration::from_secs(10);
    loop {
        let next = tokio::time::timeout_at(deadline, tap.recv()).await.ok().flatten();
        let Some(env) = next else { break };
        let d = env.to_json().unwrap();
        if env.name == "acp.prompt.sent" && d["harness"] == "f13/Free" {
            let t = d["text"].as_str().unwrap();
            if t.contains("review the materials") { review_prompt = Some(t.to_string()); break; }
        }
    }
    handle.send(roundtable::Command::End);
    match review_prompt {
        Some(t) => {
            let ends = t.trim_end().ends_with(&format!("You have {base} Characters to Respond"));
            println!("F13 review prompt tail: {:?}", t.lines().last());
            println!("F13 custom base {base} honoured: {ends}");
            std::process::exit(if ends {0} else {1});
        }
        None => { println!("F13: no review prompt captured"); std::process::exit(2); }
    }
}
