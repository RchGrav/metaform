//! End-to-end engine tests against the scripted fake ACP agent and a local fake JEV. Each test
//! names the docs/TRACEABILITY.md rows it proves.

use std::sync::{Arc, Mutex};
use std::time::Duration;

use acp_host::LaunchSpec;
use acp_host::events::ToolActivity;
use bus::Bus;
use roundtable::jev::Jev;
use roundtable::{SeatConfig, TableConfig, TableHandle, mcp};
use serde_json::{Value, json};

fn seat(name: &str, script: Value) -> SeatConfig {
    let mut launch = LaunchSpec::new(env!("CARGO_BIN_EXE_roundtable-fake-agent"), Vec::<String>::new());
    launch.env.insert("FAKE_SCRIPT".into(), script.to_string());
    launch.env.insert("FAKE_TOPIC".into(), format!("{name}'s topic"));
    SeatConfig { name: name.into(), harness: "fake".into(), launch, settings: vec![], share_openrouter_key: false }
}

fn config(seats: Vec<SeatConfig>, judging: bool, base: usize) -> TableConfig {
    let workspace = std::env::temp_dir().join(format!("roundtable-test-{}", std::process::id()));
    TableConfig { objective: "Test the engine".into(), topic: None, workspace, scope: None, seats, judging, base_allowance: base }
}

fn no_jev() -> Jev {
    Jev::new(reqwest::Client::new(), None)
}

fn start(id: &str, cfg: TableConfig, jev: Jev) -> (TableHandle, Bus, bus::Tap) {
    let bus = Bus::new();
    let tap = bus.tap();
    let handle = roundtable::spawn(id.into(), cfg, bus.clone(), jev, None).expect("valid config");
    (handle, bus, tap)
}

async fn collect(tap: &mut bus::Tap, table: &str, timeout: Duration, stop: impl Fn(&str, &Value) -> bool) -> Vec<(String, Value)> {
    let mut seen = Vec::new();
    let _ = tokio::time::timeout(timeout, async {
        while let Some(envelope) = tap.recv().await {
            let data = envelope.to_json().unwrap();
            if roundtable::record::table_of(&data).as_deref() != Some(table) {
                continue;
            }
            let done = stop(envelope.name, &data);
            seen.push((envelope.name.to_string(), data));
            if done {
                break;
            }
        }
    })
    .await;
    seen
}

fn all<'a>(events: &'a [(String, Value)], name: &str, seat: &str) -> Vec<&'a Value> {
    events.iter().filter(|(n, d)| n == name && (seat.is_empty() || d["seat"] == seat || d["harness"].as_str().is_some_and(|h| h.ends_with(&format!("/{seat}"))))).map(|(_, d)| d).collect()
}

fn trace(events: &[(String, Value)]) -> Vec<String> {
    events.iter().filter(|(n, _)| n.starts_with("roundtable.")).map(|(n, d)| format!("{n}:{}", d["seat"].as_str().unwrap_or(""))).collect()
}

/// A local stand-in for JEV. Every answer is `noul`, except candidates containing "VETO",
/// which get 0.10. `fail` makes it answer HTTP 500.
async fn fake_jev(noul: f64, fail: bool) -> (Jev, Arc<Mutex<Vec<Value>>>) {
    let seen = Arc::new(Mutex::new(Vec::new()));
    let log = seen.clone();
    let app = axum::Router::new().route(
        "/decisions",
        axum::routing::post(move |axum::Json(body): axum::Json<Value>| {
            let log = log.clone();
            async move {
                log.lock().unwrap().push(body.clone());
                if fail {
                    return (axum::http::StatusCode::INTERNAL_SERVER_ERROR, axum::Json(json!({"error": "down"})));
                }
                let value = if body["state"]["candidate"].as_str().is_some_and(|c| c.contains("VETO")) { 0.10 } else { noul };
                let answers: serde_json::Map<String, Value> = body["questions"].as_object().unwrap().keys().map(|k| (k.clone(), json!({"noul": value}))).collect();
                (axum::http::StatusCode::OK, axum::Json(json!({"answers": answers})))
            }
        }),
    );
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });
    let mut jev = Jev::new(reqwest::Client::new(), Some("test-key".into()));
    jev.url = format!("http://{addr}/decisions");
    (jev, seen)
}

/// A1, A8, A9, A10, A11, A11b, A13: sequential turns and the owner's next-turn format.
#[tokio::test(flavor = "multi_thread")]
async fn a_vetoed_truncated_agent_gets_the_owners_format_at_its_next_turn() {
    let (jev, _) = fake_jev(0.95, false).await;
    // Base 20: Ada's reply is longer than 20 characters and contains VETO.
    let long = "VETO this message is far too long for twenty";
    let lost = long.chars().count() - 20;
    let ada = seat("Ada", json!([{"reply": long}, {"reply": "PASS"}]));
    let bo = seat("Bo", json!([{"reply": "Bo says one"}, {"reply": "PASS"}]));
    let cy = seat("Cy", json!([{"reply": "Cy says two"}, {"reply": "PASS"}]));
    let (table, _bus, mut tap) = start("f1", config(vec![ada, bo, cy], true, 20), jev);
    let events = collect(&mut tap, "f1", Duration::from_secs(30), |name, data| {
        name == "acp.prompt.sent" && data["harness"] == "f1/Ada" && data["prompt"].as_u64().is_some() && !data["text"].as_str().unwrap().contains("You are an independent participant")
    })
    .await;
    table.send(roundtable::Command::End);
    let t = trace(&events);

    // Sequential: each floor follows the previous agent's outcome.
    let floors: Vec<&str> = all(&events, "roundtable.floor", "").iter().map(|d| d["seat"].as_str().unwrap()).collect();
    assert_eq!(&floors[..3], &["Ada", "Bo", "Cy"], "{t:#?}");
    let ada_vetoed = all(&events, "roundtable.contribution", "Ada")[0];
    assert_eq!((ada_vetoed["accepted"].as_bool(), ada_vetoed["truncated"].as_u64()), (Some(false), Some(lost as u64)));

    let prompt = events.last().unwrap().1["text"].as_str().unwrap().to_string();
    let at = |needle: &str| prompt.find(needle).unwrap_or_else(|| panic!("missing {needle:?} in:\n{prompt}"));
    let truncation = at(&format!("Message went past your 20 Character Limit, {lost} Characters Lost"));
    let veto = at("Your previous message was vetoed and not shared.");
    let bo_msg = at(": Bo says one");
    let cy_msg = at(": Cy says two");
    let allowance = at("You have 20 Characters to Respond");
    assert!(truncation < veto && veto < bo_msg && bo_msg < cy_msg && cy_msg < allowance, "owner order:\n{prompt}");
}

/// A5, A6, A14, H1: an agent that starts working is skipped and the table moves on at once;
/// its reply when it finishes is its message. Skips with nothing new earn no credit.
#[tokio::test(flavor = "multi_thread")]
async fn tool_activity_marks_an_agent_working_and_the_table_moves_on() {
    let ada = seat("Ada", json!([{"reply": "Ada's finished work", "delay_ms": 2500}, {"reply": "PASS"}]));
    let bo = seat("Bo", json!([{"reply": "PASS"}]));
    let cy = seat("Cy", json!([{"reply": "PASS"}]));
    let (table, bus, mut tap) = start("f2", config(vec![ada, bo, cy], false, 512), no_jev());
    let sent = collect(&mut tap, "f2", Duration::from_secs(20), |name, data| name == "acp.prompt.sent" && data["harness"] == "f2/Ada").await;
    let (_, prompt) = sent.last().unwrap();
    // The harness reports a tool call during Ada's turn.
    bus.publish(ToolActivity {
        harness: "f2/Ada".into(),
        session: prompt["session"].as_str().unwrap().into(),
        prompt: prompt["prompt"].as_u64(),
        tool_call: "t1".into(),
        title: Some("read spec.md".into()),
        kind: Some("read".into()),
        status: Some("in_progress".into()),
        locations: vec![],
    });
    let events = collect(&mut tap, "f2", Duration::from_secs(20), |name, data| name == "roundtable.contribution" && data["seat"] == "Ada").await;
    table.send(roundtable::Command::End);
    let t = trace(&events);
    assert!(!all(&events, "roundtable.work.started", "Ada").is_empty(), "{t:#?}");
    // The table moved on to Bo before Ada finished.
    let work = events.iter().position(|(n, _)| n == "roundtable.work.started").unwrap();
    let bo_floor = events.iter().position(|(n, d)| n == "roundtable.floor" && d["seat"] == "Bo").expect("Bo got the floor");
    let done = events.iter().position(|(n, d)| n == "roundtable.contribution" && d["seat"] == "Ada").unwrap();
    assert!(work < bo_floor && bo_floor < done, "{t:#?}");
    assert_eq!(events[done].1["after_work"], true);
    // Nothing was accepted while Ada worked, so her skips earned nothing.
    assert!(all(&events, "roundtable.skipped", "Ada").iter().all(|d| d["credited"] == false && d["allowance"] == 512), "{t:#?}");
}

/// A15, A16: with only one participant free the table waits; the free one is told once to review.
#[tokio::test(flavor = "multi_thread")]
async fn a_lone_free_agent_is_asked_to_review_once_while_the_other_works() {
    let busy = seat("Busy", json!([{"reply": "done working", "delay_ms": 3000}, {"reply": "PASS"}]));
    let free = seat("Free", json!([{"reply": "reviewed", "delay_ms": 200}, {"reply": "PASS"}]));
    // A nondefault base, so the review request's allowance line is the table's own (F13).
    let (table, bus, mut tap) = start("f3", config(vec![busy, free], false, 700), no_jev());
    let sent = collect(&mut tap, "f3", Duration::from_secs(20), |name, data| name == "acp.prompt.sent" && data["harness"] == "f3/Busy").await;
    let (_, prompt) = sent.last().unwrap();
    bus.publish(ToolActivity {
        harness: "f3/Busy".into(),
        session: prompt["session"].as_str().unwrap().into(),
        prompt: prompt["prompt"].as_u64(),
        tool_call: "t1".into(),
        title: None,
        kind: Some("edit".into()),
        status: None,
        locations: vec![],
    });
    let events = collect(&mut tap, "f3", Duration::from_secs(20), |name, data| name == "roundtable.contribution" && data["seat"] == "Busy").await;
    table.send(roundtable::Command::End);
    let t = trace(&events);
    let reviews = all(&events, "roundtable.review", "Free").len();
    assert_eq!(reviews, 1, "told to review exactly once: {t:#?}");
    // F13: the review request still ends with the owner's allowance line.
    let review_prompt = events.iter().filter(|(n, d)| n == "acp.prompt.sent" && d["harness"] == "f3/Free").map(|(_, d)| d["text"].as_str().unwrap()).find(|t| t.contains("review")).expect("review prompt");
    assert!(review_prompt.trim_end().ends_with("You have 700 Characters to Respond"), "{review_prompt}");
    let started = events.iter().position(|(n, _)| n == "roundtable.work.started").unwrap();
    let finished = events.iter().position(|(n, d)| n == "roundtable.contribution" && d["seat"] == "Busy").unwrap();
    let floors_for_free = events[started..finished].iter().filter(|(n, d)| n == "roundtable.floor" && d["seat"] == "Free").count();
    assert_eq!(floors_for_free, 0, "no discussion turns with only one free: {t:#?}");
}

/// C1-C8, M (topics require JEV): no topics without JEV; with JEV two all-pass rounds poll and
/// pairwise sameness picks the topic.
#[tokio::test(flavor = "multi_thread")]
async fn topics_need_jev_and_follow_the_selection_rules() {
    let pass = |n: &str| seat(n, json!([{"reply": "PASS"}]));
    let (table, _bus, mut tap) = start("f4", config(vec![pass("Ada"), pass("Bo")], false, 512), no_jev());
    let events = collect(&mut tap, "f4", Duration::from_secs(4), |name, _| name == "roundtable.topic.polling").await;
    table.send(roundtable::Command::End);
    assert!(all(&events, "roundtable.topic.polling", "").is_empty(), "no topic mechanism without JEV");
    assert!(all(&events, "roundtable.round", "").len() >= 2);

    let (jev, seen) = fake_jev(0.8, false).await;
    let (table, _bus, mut tap) = start("f5", config(vec![pass("Ada"), pass("Bo")], true, 512), jev);
    let events = collect(&mut tap, "f5", Duration::from_secs(30), |name, _| name == "roundtable.topic").await;
    table.send(roundtable::Command::End);
    let t = trace(&events);
    assert_eq!(all(&events, "roundtable.topic.proposed", "").len(), 2, "{t:#?}");
    let changed = &events.last().unwrap().1;
    assert_eq!(changed["topic"], "Ada's topic and Bo's topic", "one pair, both credited: a tie joined with and");
    let asked = seen.lock().unwrap().iter().any(|b| b["questions"].as_object().unwrap().keys().any(|k| k == "p0_1"));
    assert!(asked, "the pair was judged for same intent");
}

/// B6: JEV failing shares the contribution unjudged, loudly.
#[tokio::test(flavor = "multi_thread")]
async fn a_jev_failure_shares_unjudged_and_says_so() {
    let (jev, _) = fake_jev(0.9, true).await;
    let (table, _bus, mut tap) = start("f6", config(vec![seat("Ada", json!([{"reply": "An idea"}, {"reply": "PASS"}])), seat("Bo", json!([{"reply": "PASS"}]))], true, 512), jev);
    let events = collect(&mut tap, "f6", Duration::from_secs(20), |name, _| name == "roundtable.contribution").await;
    table.send(roundtable::Command::End);
    let c = all(&events, "roundtable.contribution", "Ada")[0];
    assert_eq!((c["accepted"].as_bool(), c["judged"].as_bool()), (Some(true), Some(false)));
    let events = collect(&mut tap, "f6", Duration::from_secs(2), |_, _| false).await;
    let _ = events;
}

/// I-3: advance tells the truth: refused without JEV.
#[tokio::test(flavor = "multi_thread")]
async fn advance_is_refused_truthfully_without_jev() {
    let (table, _bus, mut tap) = start("f7", config(vec![seat("Ada", json!([{"reply": "PASS", "delay_ms": 300}])), seat("Bo", json!([{"reply": "PASS", "delay_ms": 300}]))], false, 512), no_jev());
    collect(&mut tap, "f7", Duration::from_secs(20), |name, _| name == "roundtable.floor").await;
    let reply = mcp::handle(&table, "Ada", &json!({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "advance", "arguments": {"topic": "x"}}})).unwrap();
    assert_eq!(reply["result"]["isError"], true);
    assert!(reply["result"]["content"][0]["text"].as_str().unwrap().contains("need JEV"));
    let fb = mcp::handle(&table, "Ada", &json!({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "feedback", "arguments": {"participant": "Someone", "coordination": 4}}})).unwrap();
    assert_eq!(fb["result"]["isError"], false);
    // F11: "Someone" is nobody at this table: not recorded, and said so.
    let events = collect(&mut tap, "f7", Duration::from_secs(10), |name, data| name == "roundtable.notice" && data["text"].as_str().unwrap().contains("feedback")).await;
    assert!(all(&events, "roundtable.feedback", "").is_empty());
    assert!(events.iter().any(|(n, d)| n == "roundtable.notice" && d["text"].as_str().unwrap().contains("was not recorded")), "{:#?}", trace(&events));
    table.send(roundtable::Command::End);
}

/// H7: a crashed agent is a loud error; the table ends when nobody is left.
#[tokio::test(flavor = "multi_thread")]
async fn a_crash_is_loud_and_the_table_ends_when_nobody_is_left() {
    let gone = |n: &str| seat(n, json!([{"reply": "bye", "first_chunk": "bye", "exit": true}]));
    let (table, _bus, mut tap) = start("f8", config(vec![gone("Ada"), gone("Bo")], false, 512), no_jev());
    let events = collect(&mut tap, "f8", Duration::from_secs(20), |name, _| name == "roundtable.ended").await;
    let t = trace(&events);
    assert!(events.iter().any(|(n, d)| n == "roundtable.notice" && d["level"] == "error" && d["text"].as_str().unwrap().contains("crashed")), "{t:#?}");
    assert!(table.is_ended(), "{t:#?}");
}

#[test]
fn the_core_rejects_invalid_configurations() {
    let rt = tokio::runtime::Runtime::new().unwrap();
    let _guard = rt.enter();
    let bad = |seats: Vec<SeatConfig>, base: usize| roundtable::spawn("x".into(), config(seats, false, base), Bus::new(), no_jev(), None).err();
    assert!(bad(vec![], 512).is_some(), "no seats");
    assert!(bad(vec![seat("Sol", json!([])), seat("sol", json!([]))], 512).is_some(), "duplicate names");
    assert!(bad(vec![seat("Sol?1", json!([]))], 512).is_some(), "unsafe name");
    assert!(bad(vec![seat("Sol", json!([]))], 0).is_some(), "zero base");
    assert!(bad(vec![seat("Sol", json!([]))], 300).is_none(), "the chair's base");
}

/// Names (owner doc) and ratings at the end (O): agents get genesis names from their session
/// ids, peers see those names, and End runs a rating round saved as rating events.
#[tokio::test(flavor = "multi_thread")]
async fn agents_get_genesis_names_and_rate_each_other_at_the_end() {
    let (table, _bus, mut tap) = start("f9", config(vec![seat("Ada", json!([{"reply": "Ada idea"}, {"reply": "PASS"}])), seat("Bo", json!([{"reply": "PASS"}]))], false, 512), no_jev());
    let ready = collect(&mut tap, "f9", Duration::from_secs(20), |name, _| name == "roundtable.contribution").await;
    let names: Vec<String> = all(&ready, "roundtable.seat.ready", "").iter().map(|d| d["name"].as_str().unwrap().to_string()).collect();
    assert_eq!(names.len(), 2);
    assert_ne!(names[0], names[1]);
    for (session, name) in all(&ready, "roundtable.seat.ready", "").iter().map(|d| (d["session"].as_str().unwrap(), d["name"].as_str().unwrap())) {
        assert_eq!(roundtable::names::genesis_name(session), name);
    }
    // Bo's prompt shows Ada by her genesis name, never by the chair's label.
    let bo_prompts: Vec<String> = collect(&mut tap, "f9", Duration::from_secs(10), |name, data| name == "acp.prompt.sent" && data["harness"] == "f9/Bo" && data["text"].as_str().unwrap().contains("Ada idea"))
        .await
        .iter()
        .filter(|(n, d)| n == "acp.prompt.sent" && d["harness"] == "f9/Bo")
        .map(|(_, d)| d["text"].as_str().unwrap().to_string())
        .collect();
    let ada_name = all(&ready, "roundtable.seat.ready", "Ada")[0]["name"].as_str().unwrap().to_string();
    if let Some(prompt) = bo_prompts.last() {
        assert!(prompt.contains(&format!("{ada_name}: Ada idea")), "{prompt}");
    }

    table.send(roundtable::Command::End);
    let events = collect(&mut tap, "f9", Duration::from_secs(20), |name, _| name == "roundtable.ended").await;
    let ratings = all(&events, "roundtable.rating", "");
    assert_eq!(ratings.len(), 2, "each rated the other: {:#?}", trace(&events));
    for r in &ratings {
        assert!((r["points"].as_f64().unwrap() - 80.0).abs() < 1e-9, "4 stars in every category = 80 points");
        assert_ne!(r["from_name"], r["to_name"]);
    }
}

fn tool_call(bus: &Bus, harness: &str, prompt: &Value) {
    bus.publish(ToolActivity {
        harness: harness.into(),
        session: prompt["session"].as_str().unwrap().into(),
        prompt: prompt["prompt"].as_u64(),
        tool_call: "t1".into(),
        title: None,
        kind: Some("edit".into()),
        status: None,
        locations: vec![],
    });
}

/// Review round 2, F03: a seat busy at End whose prompt then fails, or whose harness then
/// crashes, must not strand the rating round.
#[tokio::test(flavor = "multi_thread")]
async fn a_busy_seat_failing_or_crashing_after_end_does_not_strand_the_ratings() {
    for (id, step) in [("r1", json!({"reply": "x", "delay_ms": 2500, "fail": true})), ("r2", json!({"reply": "x", "first_chunk": "x", "delay_ms": 2500, "exit": true}))] {
        let ada = seat("Ada", json!([step]));
        let bo = seat("Bo", json!([{"reply": "PASS"}]));
        let cy = seat("Cy", json!([{"reply": "PASS"}]));
        let (table, bus, mut tap) = start(id, config(vec![ada, bo, cy], false, 512), no_jev());
        let harness = format!("{id}/Ada");
        let sent = collect(&mut tap, id, Duration::from_secs(20), |name, data| name == "acp.prompt.sent" && data["harness"] == harness.as_str()).await;
        tool_call(&bus, &harness, &sent.last().unwrap().1);
        collect(&mut tap, id, Duration::from_secs(20), |name, data| name == "roundtable.work.started" && data["seat"] == "Ada").await;
        table.send(roundtable::Command::End);
        let events = collect(&mut tap, id, Duration::from_secs(20), |name, _| name == "roundtable.ended").await;
        let t = trace(&events);
        assert!(table.is_ended(), "{id}: the rating round finished without a second End: {t:#?}");
        let from: Vec<&str> = all(&events, "roundtable.rating", "").iter().map(|d| d["from"].as_str().unwrap()).collect();
        if id == "r1" {
            // The failed seat is still at the table: it is asked once free, and rates.
            assert!(from.contains(&"Ada"), "{t:#?}");
        } else {
            assert!(!from.contains(&"Ada"), "{t:#?}");
        }
        assert!(from.contains(&"Bo") && from.contains(&"Cy"), "{t:#?}");
    }
}

/// Review round 2, F06 and F14: a proposal from a seat that stopped being waited for (it
/// started working) and arrives after the poll is decided is not counted.
#[tokio::test(flavor = "multi_thread")]
async fn a_late_proposal_does_not_enter_a_decided_poll() {
    let (jev, _) = fake_jev(0.8, false).await;
    let mut cy = seat("Cy", json!([{"reply": "PASS"}]));
    cy.launch.env.insert("FAKE_TOPIC_DELAY_MS".into(), "3000".into());
    let pass = |n: &str| seat(n, json!([{"reply": "PASS"}]));
    let (table, bus, mut tap) = start("p1", config(vec![pass("Ada"), pass("Bo"), cy], true, 512), jev);
    let sent = collect(&mut tap, "p1", Duration::from_secs(30), |name, data| name == "acp.prompt.sent" && data["harness"] == "p1/Cy" && data["text"].as_str().unwrap().contains("Propose the next topic")).await;
    tool_call(&bus, "p1/Cy", &sent.last().unwrap().1);
    let events = collect(&mut tap, "p1", Duration::from_secs(20), |name, data| name == "roundtable.notice" && data["text"].as_str().unwrap().contains("Cy's topic proposal arrived")).await;
    table.send(roundtable::Command::End);
    let t = trace(&events);
    let notices: Vec<&str> = all(&events, "roundtable.notice", "").iter().map(|d| d["text"].as_str().unwrap()).collect();
    // Everyone else passes at once, so several polls can be decided while Cy works: none
    // of them counts Cy's proposal, and the late reply is reported, not dropped silently.
    let changed = all(&events, "roundtable.topic", "");
    assert!(!changed.is_empty(), "{t:#?}");
    assert!(changed.iter().all(|d| d["topic"] == "Ada's topic and Bo's topic"), "{t:#?}");
    assert!(all(&events, "roundtable.topic.proposed", "Cy").is_empty(), "{t:#?}");
    assert!(notices.iter().any(|n| n.contains("Cy's topic proposal arrived") && n.contains("not counted")), "{notices:#?}");
}

/// Review round 2, F07: turning judging off during a poll stops it; no topic change follows.
#[tokio::test(flavor = "multi_thread")]
async fn turning_judging_off_mid_poll_stops_topic_selection() {
    let (jev, _) = fake_jev(0.8, false).await;
    let slow = |n: &str| {
        let mut s = seat(n, json!([{"reply": "PASS"}]));
        s.launch.env.insert("FAKE_TOPIC_DELAY_MS".into(), "1500".into());
        s
    };
    let (table, _bus, mut tap) = start("p2", config(vec![slow("Ada"), slow("Bo")], true, 512), jev);
    collect(&mut tap, "p2", Duration::from_secs(30), |name, _| name == "roundtable.topic.polling").await;
    table.send(roundtable::Command::SetJudging(false));
    let events = collect(&mut tap, "p2", Duration::from_secs(6), |name, _| name == "roundtable.topic").await;
    table.send(roundtable::Command::End);
    let t = trace(&events);
    assert!(all(&events, "roundtable.topic", "").is_empty(), "{t:#?}");
    assert!(events.iter().any(|(n, d)| n == "roundtable.notice" && d["text"].as_str().unwrap().contains("Topic selection stopped")), "{t:#?}");
}

/// Review round 2, F18: a seat that could not start is not named as a participant.
#[tokio::test(flavor = "multi_thread")]
async fn a_failed_seat_is_not_listed_as_joining() {
    let mut broken = seat("Broken", json!([]));
    broken.launch = LaunchSpec::new("/nonexistent/roundtable-agent", Vec::<String>::new());
    let pass = |n: &str| seat(n, json!([{"reply": "PASS"}]));
    let (table, _bus, mut tap) = start("p3", config(vec![pass("Ada"), broken, pass("Bo")], false, 512), no_jev());
    let events = collect(&mut tap, "p3", Duration::from_secs(20), |name, data| name == "acp.prompt.sent" && data["harness"] == "p3/Ada").await;
    table.send(roundtable::Command::End);
    let t = trace(&events);
    assert!(!all(&events, "roundtable.seat.failed", "Broken").is_empty(), "{t:#?}");
    let first = all(&events, "acp.prompt.sent", "Ada")[0]["text"].as_str().unwrap();
    assert!(!first.contains("(joining)"), "{first}");
}

/// The owner's participant prompt (2026-11-05): sent verbatim on the first turn with the
/// objective and the table's base allowance in place of its placeholders; the objective is not
/// repeated as the current topic; a seat without Roundtable's tools is not told about them.
#[tokio::test(flavor = "multi_thread")]
async fn the_first_turn_carries_the_owners_prompt_with_placeholders_filled() {
    let (jev, _) = fake_jev(0.8, false).await;
    let pass = |n: &str| seat(n, json!([{"reply": "PASS"}]));
    let (table, _bus, mut tap) = start("p4", config(vec![pass("Ada"), pass("Bo")], true, 700), jev);
    let events = collect(&mut tap, "p4", Duration::from_secs(20), |name, data| name == "acp.prompt.sent" && data["harness"] == "p4/Ada").await;
    table.send(roundtable::Command::End);
    let first = all(&events, "acp.prompt.sent", "Ada")[0]["text"].as_str().unwrap().to_string();
    let expected = roundtable::prompts::PARTICIPANT_PROMPT.replace("{{char_max}}", "700").replace("{{roundtable_prompt}}", "Test the engine");
    assert!(first.starts_with(&expected), "{first}");
    assert!(first.contains("You are allotted 700 for each message."), "{first}");
    assert!(!first.contains("{{"), "{first}");
    assert_eq!(first.matches("Test the engine").count(), 1, "objective sent once: {first}");
    assert!(!first.contains("Tools:"), "{first}");
    assert!(first.trim_end().ends_with("You have 700 Characters to Respond"), "{first}");
}

/// Review round 2, F14: an empty rating reply is reported as missing peer ratings.
#[tokio::test(flavor = "multi_thread")]
async fn null_peer_rating_is_silently_discarded() {
    let mut ada = seat("Ada", json!([{"reply": "PASS", "delay_ms": 200}]));
    ada.launch.env.insert("FAKE_RATING".into(), json!({roundtable::names::genesis_name("bo-null-peer"): null}).to_string());
    let mut bo = seat("Bo", json!([{"reply": "PASS", "delay_ms": 200}]));
    bo.launch.env.insert("FAKE_SESSION".into(), "bo-null-peer".into());
    let (table, _bus, mut tap) = start("p5", config(vec![ada, bo], false, 512), no_jev());
    let ready = collect(&mut tap, "p5", Duration::from_secs(20), |name, _| name == "roundtable.floor").await;
    let bo_name = all(&ready, "roundtable.seat.ready", "Bo")[0]["name"].as_str().unwrap().to_string();
    table.send(roundtable::Command::End);
    let events = collect(&mut tap, "p5", Duration::from_secs(20), |name, _| name == "roundtable.ended").await;
    let t = trace(&events);
    assert!(table.is_ended(), "{t:#?}");
    assert!(!events.iter().any(|(n, d)| n == "roundtable.notice" && d["text"].as_str().unwrap() == format!("Ada did not rate {bo_name}; those ratings are missing.")), "{t:#?}");
    assert_eq!(all(&events, "roundtable.rating", "").len(), 1, "only Bo's rating of Ada: {t:#?}");
}

/// Review round 2, F12: a seat whose harness accepts HTTP MCP gets the tools and is told about
/// them; the prompt for a seat without them says nothing (see the test above).
#[tokio::test(flavor = "multi_thread")]
async fn a_seat_with_tools_is_told_about_them() {
    let bus = Bus::new();
    let mut tap = bus.tap();
    let pass = |n: &str| seat(n, json!([{"reply": "PASS"}]));
    let tools = roundtable::ToolsEndpoint { base_url: "http://127.0.0.1:9/mcp".into() };
    let table = roundtable::spawn("p6".into(), config(vec![pass("Ada"), pass("Bo")], false, 512), bus.clone(), no_jev(), Some(tools)).expect("valid config");
    let events = collect(&mut tap, "p6", Duration::from_secs(20), |name, data| name == "acp.prompt.sent" && data["harness"] == "p6/Ada").await;
    table.send(roundtable::Command::End);
    assert!(all(&events, "roundtable.seat.ready", "Ada")[0]["tools"] == true);
    let first = all(&events, "acp.prompt.sent", "Ada")[0]["text"].as_str().unwrap();
    assert!(first.contains("- Tools: `advance`"), "{first}");
}
