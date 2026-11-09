//! End-to-end engine tests against the scripted fake ACP agent and a local fake JEV. Each test
//! names the rows it proves in `context/roundtable-original-2026-11-05/docs/TRACEABILITY.md`,
//! from the repository root. That file's code line numbers refer to the earlier build.

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
    SeatConfig { name: name.into(), harness: "fake".into(), launch, settings: vec![], share_openrouter_key: false, resume_session: None }
}

fn config(seats: Vec<SeatConfig>, topics: bool, base: usize) -> TableConfig {
    let workspace = std::env::temp_dir().join(format!("roundtable-test-{}", std::process::id()));
    // A far round limit, so the topic and turn tests run as long as they need.
    let mut config = TableConfig::new("Test the engine", workspace, seats);
    config.topics = topics;
    config.base_allowance = Some(base);
    config.rounds = Some(1000);
    // The poll tests were written for polls that wait for busy agents.
    config.poll_busy_agents = true;
    config
}

/// A JEV that passes every message.
async fn pass_jev() -> Jev {
    fake_jev(0.95, false).await.0
}

/// A JEV with a key and nothing behind it, for tables that are refused before they start.
fn unreachable_jev() -> Jev {
    let mut jev = Jev::new(reqwest::Client::new(), Some("test-key".into()));
    jev.url = "http://127.0.0.1:9/decisions".into();
    jev
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

/// A local stand-in for JEV. Every noul answer is `noul` and every score is `noul` × 5, except
/// for contributions containing "VETO", which get 0.10 and 0.5. `fail` makes it answer HTTP 500.
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
                let value = if body["state"]["new_message"].as_str().is_some_and(|c| c.contains("VETO")) { 0.10 } else { noul };
                let answers: serde_json::Map<String, Value> = body["questions"]
                    .as_object()
                    .unwrap()
                    .iter()
                    .map(|(k, q)| (k.clone(), if q["type"] == "score" { json!({"score": value * 5.0}) } else { json!({"noul": value}) }))
                    .collect();
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

/// A1, A10, A11, A11b, A13: sequential turns and the owner's next-turn format: the round line,
/// the rejection with every failed check, then the other agents' messages.
#[tokio::test(flavor = "multi_thread")]
async fn a_rejected_agent_gets_the_owners_format_at_its_next_turn() {
    let (jev, _) = fake_jev(0.95, false).await;
    let ada = seat("Ada", json!([{"reply": "VETO this message"}, {"reply": "PASS"}]));
    let bo = seat("Bo", json!([{"reply": "Bo says one"}, {"reply": "PASS"}]));
    let cy = seat("Cy", json!([{"reply": "Cy says two"}, {"reply": "PASS"}]));
    let (table, _bus, mut tap) = start("f1", config(vec![ada, bo, cy], true, 1000), jev);
    let events = collect(&mut tap, "f1", Duration::from_secs(30), |name, data| {
        name == "acp.prompt.sent" && data["harness"] == "f1/Ada" && data["prompt"].as_u64().is_some() && !data["text"].as_str().unwrap().contains("You are an independent participant")
    })
    .await;
    table.send(roundtable::Command::End);
    let t = trace(&events);

    // Sequential: each floor follows the previous agent's outcome.
    let floors: Vec<&str> = all(&events, "roundtable.floor", "").iter().map(|d| d["seat"].as_str().unwrap()).collect();
    assert_eq!(&floors[..3], &["Ada", "Bo", "Cy"], "{t:#?}");
    assert_eq!(all(&events, "roundtable.contribution", "Ada")[0]["accepted"], false, "{t:#?}");

    let prompt = events.last().unwrap().1["text"].as_str().unwrap().to_string();
    let at = |needle: &str| prompt.find(needle).unwrap_or_else(|| panic!("missing {needle:?} in:\n{prompt}"));
    assert!(prompt.starts_with("Round 2 of 1000"), "the turn starts with the round:\n{prompt}");
    let veto = at("We're sorry your message was not able to be submitted for the following reason(s): \n- Contribution (0.10): ");
    for check in ["- Usefulness (0.10): ", "- Relevance (0.10): ", "- Value (0.50): Your message offers no concrete", "- Auditability (0.50): The participants cannot inspect"] {
        assert!(prompt[veto..].contains(check), "every failed check is listed ({check}):\n{prompt}");
    }
    let bo_msg = at(": Bo says one");
    let cy_msg = at(": Cy says two");
    assert!(veto < bo_msg && bo_msg < cy_msg && prompt.trim_end().ends_with("Cy says two"), "owner order:\n{prompt}");
}

/// Owner: a message over the reply limit is blocked, never cut, and does not go to JEV.
#[tokio::test(flavor = "multi_thread")]
async fn a_message_over_the_limit_is_blocked_not_cut() {
    let (jev, seen) = fake_jev(0.95, false).await;
    let ada = seat("Ada", json!([{"reply": "this message is far too long for twenty"}, {"reply": "PASS"}]));
    let (table, _bus, mut tap) = start("f0", config(vec![ada, seat("Bo", json!([{"reply": "PASS"}]))], true, 20), jev);
    let events = collect(&mut tap, "f0", Duration::from_secs(30), |name, data| name == "acp.prompt.sent" && data["harness"] == "f0/Ada" && data["text"].as_str().unwrap().starts_with("Round 2")).await;
    table.send(roundtable::Command::End);
    let blocked = all(&events, "roundtable.contribution", "Ada")[0];
    assert_eq!((blocked["accepted"].as_bool(), blocked["text"].as_str()), (Some(false), Some("this message is far too long for twenty")));
    assert!(seen.lock().unwrap().is_empty(), "a blocked message is not judged");
    let prompt = events.last().unwrap().1["text"].as_str().unwrap();
    assert!(prompt.contains(&roundtable::prompts::too_long(39, 20)), "{prompt}");
}

/// A5, A6, A14, H1: an agent that starts working is skipped and the table moves on at once;
/// its reply when it finishes is its message. Skipped while busy, its next reply gets the
/// recovery limit once (owner's spec).
#[tokio::test(flavor = "multi_thread")]
async fn tool_activity_marks_an_agent_working_and_the_table_moves_on() {
    let ada = seat("Ada", json!([{"reply": "Ada's finished work", "delay_ms": 2500}, {"reply": "PASS"}]));
    let bo = seat("Bo", json!([{"reply": "PASS"}]));
    let cy = seat("Cy", json!([{"reply": "PASS"}]));
    let (table, bus, mut tap) = start("f2", config(vec![ada, bo, cy], false, 512), pass_jev().await);
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
    let next = collect(&mut tap, "f2", Duration::from_secs(20), |name, data| name == "roundtable.floor" && data["seat"] == "Ada").await;
    table.send(roundtable::Command::End);
    let t = trace(&events);
    assert!(!all(&events, "roundtable.work.started", "Ada").is_empty(), "{t:#?}");
    // The table moved on to Bo before Ada finished.
    let work = events.iter().position(|(n, _)| n == "roundtable.work.started").unwrap();
    let bo_floor = events.iter().position(|(n, d)| n == "roundtable.floor" && d["seat"] == "Bo").expect("Bo got the floor");
    let done = events.iter().position(|(n, d)| n == "roundtable.contribution" && d["seat"] == "Ada").unwrap();
    assert!(work < bo_floor && bo_floor < done, "{t:#?}");
    assert_eq!(events[done].1["after_work"], true);
    assert!(!all(&events, "roundtable.skipped", "Ada").is_empty(), "Ada was skipped while busy: {t:#?}");
    assert_eq!(all(&next, "roundtable.floor", "Ada").last().map(|d| d["allowance"].clone()), Some(json!(1024)), "{:#?}", trace(&next));
}

/// A15, A16: with only one participant free the table waits; the free one is told once to review.
#[tokio::test(flavor = "multi_thread")]
async fn a_lone_free_agent_is_asked_to_review_once_while_the_other_works() {
    let busy = seat("Busy", json!([{"reply": "done working", "delay_ms": 3000}, {"reply": "PASS"}]));
    let free = seat("Free", json!([{"reply": "reviewed", "delay_ms": 200}, {"reply": "PASS"}]));
    // A nondefault reply limit (700) for the table.
    let (table, bus, mut tap) = start("f3", config(vec![busy, free], false, 700), pass_jev().await);
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
    // The review request is the review text alone.
    let review_prompt = events.iter().filter(|(n, d)| n == "acp.prompt.sent" && d["harness"] == "f3/Free").map(|(_, d)| d["text"].as_str().unwrap()).find(|t| t.contains("review")).expect("review prompt");
    assert!(review_prompt.trim_end().ends_with(roundtable::prompts::REVIEW), "{review_prompt}");
    let started = events.iter().position(|(n, _)| n == "roundtable.work.started").unwrap();
    // Until Busy's work ends; its message appears later, after JEV's verdict.
    let finished = events.iter().position(|(n, d)| n == "acp.prompt.completed" && d["harness"] == "f3/Busy").unwrap();
    let floors_for_free = events[started..finished].iter().filter(|(n, d)| n == "roundtable.floor" && d["seat"] == "Free").count();
    assert_eq!(floors_for_free, 0, "no discussion turns with only one free: {t:#?}");
}

/// C1-C8, M (topics require JEV): no topics without JEV; with JEV two all-pass rounds poll and
/// pairwise sameness picks the topic.
#[tokio::test(flavor = "multi_thread")]
async fn topics_follow_their_setting_and_the_selection_rules() {
    let pass = |n: &str| seat(n, json!([{"reply": "PASS"}]));
    let (table, _bus, mut tap) = start("f4", config(vec![pass("Ada"), pass("Bo")], false, 512), pass_jev().await);
    let events = collect(&mut tap, "f4", Duration::from_secs(4), |name, _| name == "roundtable.topic.polling").await;
    table.send(roundtable::Command::End);
    assert!(all(&events, "roundtable.topic.polling", "").is_empty(), "no topic mechanism with topics off");
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

/// Owner: "we arent going to be truncating if we add limits in we will block messages for
/// being too long". A topic proposal over its limit is blocked whole and not counted, and the
/// agent is told why at its next turn.
#[tokio::test(flavor = "multi_thread")]
async fn a_topic_proposal_over_its_limit_is_blocked_not_cut() {
    let pass = |n: &str| seat(n, json!([{"reply": "PASS"}]));
    let (jev, _) = fake_jev(0.8, false).await;
    let mut cfg = config(vec![pass("Ada"), pass("Bo")], true, 512);
    cfg.topic_proposal_limit = Some(5);
    let (table, _bus, mut tap) = start("f5b", cfg, jev);
    let events = collect(&mut tap, "f5b", Duration::from_secs(30), |name, data| {
        name == "acp.prompt.sent" && data["harness"] == "f5b/Ada" && data["text"].as_str().unwrap().contains("over the limit of 5 characters")
    })
    .await;
    table.send(roundtable::Command::End);
    let t = trace(&events);
    assert!(all(&events, "roundtable.topic.proposed", "").is_empty(), "nothing over the limit is counted, cut or not: {t:#?}");
    let blocked: Vec<&Value> = events.iter().filter(|(n, d)| n == "roundtable.notice" && d["text"].as_str().unwrap().contains("over the limit of 5")).map(|(_, d)| d).collect();
    assert_eq!(blocked.len(), 2, "{t:#?}");
    let prompt = events.last().unwrap().1["text"].as_str().unwrap();
    assert!(prompt.contains(&roundtable::prompts::too_long(11, 5)), "{prompt}");
}

/// JEV is required (owner): a message JEV could not evaluate is not shared. The chair sees the
/// error, the author hears at its next turn, and the table continues.
#[tokio::test(flavor = "multi_thread")]
async fn a_jev_failure_holds_the_message_and_says_so() {
    let (jev, _) = fake_jev(0.9, true).await;
    let (table, _bus, mut tap) = start("f6", config(vec![seat("Ada", json!([{"reply": "An idea"}, {"reply": "PASS"}])), seat("Bo", json!([{"reply": "PASS"}]))], true, 512), jev);
    let events = collect(&mut tap, "f6", Duration::from_secs(30), |name, data| {
        name == "acp.prompt.sent" && data["harness"] == "f6/Ada" && data["text"].as_str().unwrap().contains("JEV could not evaluate it")
    })
    .await;
    table.send(roundtable::Command::End);
    let t = trace(&events);
    let c = all(&events, "roundtable.contribution", "Ada")[0];
    assert_eq!((c["accepted"].as_bool(), c["judged"].as_bool()), (Some(false), Some(false)), "{t:#?}");
    assert!(events.iter().any(|(n, d)| n == "roundtable.notice" && d["text"].as_str().unwrap().contains("it was not shared")), "{t:#?}");
    let bo_saw = all(&events, "acp.prompt.sent", "Bo").iter().any(|d| d["text"].as_str().unwrap().contains("An idea"));
    assert!(!bo_saw, "an unevaluated message never reaches the others: {t:#?}");
}

/// I-3: advance tells the truth: refused when topics are off.
#[tokio::test(flavor = "multi_thread")]
async fn advance_is_refused_truthfully_without_topics() {
    let (table, _bus, mut tap) = start("f7", config(vec![seat("Ada", json!([{"reply": "PASS", "delay_ms": 300}])), seat("Bo", json!([{"reply": "PASS", "delay_ms": 300}]))], false, 512), pass_jev().await);
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
    let (table, _bus, mut tap) = start("f8", config(vec![gone("Ada"), gone("Bo")], false, 512), pass_jev().await);
    let events = collect(&mut tap, "f8", Duration::from_secs(20), |name, _| name == "roundtable.ended").await;
    let t = trace(&events);
    assert!(events.iter().any(|(n, d)| n == "roundtable.notice" && d["level"] == "error" && d["text"].as_str().unwrap().contains("left the table unexpectedly")), "{t:#?}");
    assert!(table.is_ended(), "{t:#?}");
}

#[test]
fn the_core_rejects_invalid_configurations() {
    let rt = tokio::runtime::Runtime::new().unwrap();
    let _guard = rt.enter();
    let bad = |seats: Vec<SeatConfig>, base: usize| roundtable::spawn("x".into(), config(seats, false, base), Bus::new(), unreachable_jev(), None).err();
    // JEV is required (owner): no table starts without its key.
    let no_key = Jev::new(reqwest::Client::new(), None);
    let two_seats = vec![seat("Sol", json!([])), seat("Bo", json!([]))];
    assert!(roundtable::spawn("x".into(), config(two_seats, false, 512), Bus::new(), no_key, None).is_err(), "no JEV key");
    assert!(bad(vec![], 512).is_some(), "no seats");
    assert!(bad(vec![seat("Sol", json!([])), seat("sol", json!([]))], 512).is_some(), "duplicate names");
    let two = |name: &str| vec![seat(name, json!([])), seat("Bo", json!([]))];
    // Owner: a discussion needs at least two agents.
    assert!(bad(vec![seat("Sol", json!([]))], 512).is_some(), "one seat");
    assert!(bad(two("Sol?1"), 512).is_some(), "unsafe name");
    assert!(bad(two("Sol"), 0).is_some(), "zero base");
    assert!(bad(two("Sol"), 300).is_none(), "the chair's base");
}

/// Names (owner doc) and ratings at the end (O): agents get genesis names from their session
/// ids, peers see those names, and End runs a rating round saved as rating events.
#[tokio::test(flavor = "multi_thread")]
async fn agents_get_genesis_names_and_rate_each_other_at_the_end() {
    let (table, _bus, mut tap) = start("f9", config(vec![seat("Ada", json!([{"reply": "Ada idea"}, {"reply": "PASS"}])), seat("Bo", json!([{"reply": "PASS"}]))], false, 512), pass_jev().await);
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
        let (table, bus, mut tap) = start(id, config(vec![ada, bo, cy], false, 512), pass_jev().await);
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

/// R §7 "All participating agents are polled": a proposer that works with tools while
/// answering is waited for, and its proposal counts once it arrives.
#[tokio::test(flavor = "multi_thread")]
async fn a_proposer_that_works_is_waited_for() {
    let (jev, _) = fake_jev(0.8, false).await;
    let mut cy = seat("Cy", json!([{"reply": "PASS"}]));
    cy.launch.env.insert("FAKE_TOPIC_DELAY_MS".into(), "2000".into());
    let pass = |n: &str| seat(n, json!([{"reply": "PASS"}]));
    let (table, bus, mut tap) = start("p1", config(vec![pass("Ada"), pass("Bo"), cy], true, 512), jev);
    let sent = collect(&mut tap, "p1", Duration::from_secs(30), |name, data| name == "acp.prompt.sent" && data["harness"] == "p1/Cy" && data["text"].as_str().unwrap().contains("Propose the next topic")).await;
    tool_call(&bus, "p1/Cy", &sent.last().unwrap().1);
    let events = collect(&mut tap, "p1", Duration::from_secs(20), |name, _| name == "roundtable.topic").await;
    table.send(roundtable::Command::End);
    let t = trace(&events);
    let proposed = events.iter().position(|(n, d)| n == "roundtable.topic.proposed" && d["seat"] == "Cy").unwrap_or_else(|| panic!("Cy's proposal counted: {t:#?}"));
    let changed = events.iter().position(|(n, _)| n == "roundtable.topic").unwrap_or_else(|| panic!("{t:#?}"));
    assert!(proposed < changed, "the poll waited for Cy: {t:#?}");
}

/// Review round 2, F07: losing JEV's key during a poll stops it; no topic change follows.
#[tokio::test(flavor = "multi_thread")]
async fn losing_jevs_key_mid_poll_stops_topic_selection() {
    let (jev, _) = fake_jev(0.8, false).await;
    let slow = |n: &str| {
        let mut s = seat(n, json!([{"reply": "PASS"}]));
        s.launch.env.insert("FAKE_TOPIC_DELAY_MS".into(), "1500".into());
        s
    };
    let (table, _bus, mut tap) = start("p2", config(vec![slow("Ada"), slow("Bo")], true, 512), jev);
    collect(&mut tap, "p2", Duration::from_secs(30), |name, _| name == "roundtable.topic.polling").await;
    table.send(roundtable::Command::SetJevKey(None));
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
    let (table, _bus, mut tap) = start("p3", config(vec![pass("Ada"), broken, pass("Bo")], false, 512), pass_jev().await);
    let events = collect(&mut tap, "p3", Duration::from_secs(20), |name, data| name == "acp.prompt.sent" && data["harness"] == "p3/Ada").await;
    table.send(roundtable::Command::End);
    let t = trace(&events);
    assert!(!all(&events, "roundtable.seat.failed", "Broken").is_empty(), "{t:#?}");
    let first = all(&events, "acp.prompt.sent", "Ada")[0]["text"].as_str().unwrap();
    assert!(!first.contains("(joining)"), "{first}");
}

/// The owner's roundtable prompt on the first turn, with the owner's participant prompt inside
/// it and the first turn (the round line only) as its delivery. Nothing else.
#[tokio::test(flavor = "multi_thread")]
async fn the_first_turn_carries_the_owners_prompt_with_placeholders_filled() {
    let (jev, _) = fake_jev(0.8, false).await;
    let pass = |n: &str| seat(n, json!([{"reply": "PASS"}]));
    let (table, _bus, mut tap) = start("p4", config(vec![pass("Ada"), pass("Bo")], true, 700), jev);
    let events = collect(&mut tap, "p4", Duration::from_secs(20), |name, data| name == "acp.prompt.sent" && data["harness"] == "p4/Ada").await;
    table.send(roundtable::Command::End);
    let first = all(&events, "acp.prompt.sent", "Ada")[0]["text"].as_str().unwrap().to_string();
    let name = all(&events, "roundtable.seat.ready", "Ada")[0]["name"].as_str().unwrap().to_string();
    let custom = roundtable::prompts::PARTICIPANT_PROMPT.replace("{{roundtable_prompt}}", "Test the engine");
    assert!(first.starts_with(&format!("You are {name}, participating in a roundtable about:\nTest the engine\n\n{custom}")), "{first}");
    assert!(first.ends_with("Current delivery:\nRound 1 of 1000\n"), "{first}");
    assert!(!first.contains("{{"), "{first}");
}

/// Review round 2, F14: an empty rating reply is reported as missing peer ratings.
#[tokio::test(flavor = "multi_thread")]
async fn missing_peer_ratings_are_reported() {
    let mut ada = seat("Ada", json!([{"reply": "PASS", "delay_ms": 200}]));
    ada.launch.env.insert("FAKE_RATING".into(), "{}".into());
    let bo = seat("Bo", json!([{"reply": "PASS", "delay_ms": 200}]));
    let (table, _bus, mut tap) = start("p5", config(vec![ada, bo], false, 512), pass_jev().await);
    let ready = collect(&mut tap, "p5", Duration::from_secs(20), |name, _| name == "roundtable.floor").await;
    let bo_name = all(&ready, "roundtable.seat.ready", "Bo")[0]["name"].as_str().unwrap().to_string();
    table.send(roundtable::Command::End);
    let events = collect(&mut tap, "p5", Duration::from_secs(20), |name, _| name == "roundtable.ended").await;
    let t = trace(&events);
    assert!(table.is_ended(), "{t:#?}");
    assert!(events.iter().any(|(n, d)| n == "roundtable.notice" && d["text"].as_str().unwrap() == format!("Ada did not rate {bo_name}; those ratings are missing.")), "{t:#?}");
    assert_eq!(all(&events, "roundtable.rating", "").len(), 1, "only Bo's rating of Ada: {t:#?}");
}

/// Review round 2, F12: a seat whose harness accepts HTTP MCP gets the tools.
#[tokio::test(flavor = "multi_thread")]
async fn a_seat_gets_the_tools() {
    let bus = Bus::new();
    let mut tap = bus.tap();
    let pass = |n: &str| seat(n, json!([{"reply": "PASS"}]));
    let tools = roundtable::ToolsEndpoint { base_url: "http://127.0.0.1:9/mcp".into() };
    let table = roundtable::spawn("p6".into(), config(vec![pass("Ada"), pass("Bo")], false, 512), bus.clone(), pass_jev().await, Some(tools)).expect("valid config");
    let events = collect(&mut tap, "p6", Duration::from_secs(20), |name, data| name == "acp.prompt.sent" && data["harness"] == "p6/Ada").await;
    table.send(roundtable::Command::End);
    assert!(all(&events, "roundtable.seat.ready", "Ada")[0]["tools"] == true);
}

/// Round 3, N01: a rating card that is not a JSON object is reported, not dropped silently.
#[tokio::test(flavor = "multi_thread")]
async fn a_malformed_rating_card_is_reported() {
    let bo_session = "p7-bo-session";
    let bo_name = roundtable::names::genesis_name(bo_session);
    let mut ada = seat("Ada", json!([{"reply": "PASS", "delay_ms": 200}]));
    ada.launch.env.insert("FAKE_RATING".into(), json!({ bo_name.clone(): null }).to_string());
    let mut bo = seat("Bo", json!([{"reply": "PASS", "delay_ms": 200}]));
    bo.launch.env.insert("FAKE_SESSION".into(), bo_session.into());
    let (table, _bus, mut tap) = start("p7", config(vec![ada, bo], false, 512), pass_jev().await);
    collect(&mut tap, "p7", Duration::from_secs(20), |name, _| name == "roundtable.floor").await;
    table.send(roundtable::Command::End);
    let events = collect(&mut tap, "p7", Duration::from_secs(20), |name, _| name == "roundtable.ended").await;
    let t = trace(&events);
    let expected = format!("Ada's rating for {bo_name:?} is not a JSON object; not recorded.");
    assert!(events.iter().any(|(n, d)| n == "roundtable.notice" && d["text"] == expected.as_str()), "{t:#?}");
}

/// L#13: the advance tool tells the truth: during a topic poll the poll decides, so it refuses.
#[tokio::test(flavor = "multi_thread")]
async fn advance_is_refused_truthfully_during_a_poll() {
    let (jev, _) = fake_jev(0.8, false).await;
    let slow = |n: &str| {
        let mut s = seat(n, json!([{"reply": "PASS"}]));
        s.launch.env.insert("FAKE_TOPIC_DELAY_MS".into(), "2000".into());
        s
    };
    let (table, _bus, mut tap) = start("p8", config(vec![slow("Ada"), slow("Bo")], true, 512), jev);
    collect(&mut tap, "p8", Duration::from_secs(30), |name, _| name == "roundtable.topic.polling").await;
    // The flag is set when the engine loop next turns; the poll lasts two seconds.
    let mut reply = Value::Null;
    for _ in 0..50 {
        reply = mcp::handle(&table, "Ada", &json!({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "advance", "arguments": {}}})).unwrap();
        if reply["result"]["isError"] == true {
            break;
        }
        tokio::task::yield_now().await;
    }
    table.send(roundtable::Command::End);
    assert_eq!(reply["result"]["isError"], true, "{reply}");
    assert!(reply["result"]["content"][0]["text"].as_str().unwrap().contains("topic poll is in progress"), "{reply}");
}

struct Profiles(std::collections::HashMap<String, roundtable::Profile>);
impl roundtable::Identities for Profiles {
    fn profile(&self, session: &str) -> Result<Option<roundtable::Profile>, String> {
        Ok(self.0.get(session).cloned())
    }
}

/// The owner's scoring messages: a returning identity hears its profile on its first turn; each
/// rater gets the receipt; everyone gets the ranking with session points, scorecards and the
/// rating across sessions; then the table ends.
#[tokio::test(flavor = "multi_thread")]
async fn the_owners_scoring_messages_are_sent() {
    let (ada_session, bo_session) = ("p9-ada", "p9-bo");
    let (ada_name, bo_name) = (roundtable::names::genesis_name(ada_session), roundtable::names::genesis_name(bo_session));
    let mut ada = seat("Ada", json!([{"reply": "PASS", "delay_ms": 200}]));
    ada.launch.env.insert("FAKE_SESSION".into(), ada_session.into());
    let mut bo = seat("Bo", json!([{"reply": "PASS", "delay_ms": 200}]));
    bo.launch.env.insert("FAKE_SESSION".into(), bo_session.into());
    let store = Profiles([(ada_session.to_string(), roundtable::Profile { score: 50.0, ratings: 2, sessions: 1 })].into());
    let bus = Bus::new();
    let mut tap = bus.tap();
    let table = roundtable::spawn_with("p9".into(), config(vec![ada, bo], false, 512), bus.clone(), pass_jev().await, None, Some(std::sync::Arc::new(store))).unwrap();
    let start = collect(&mut tap, "p9", Duration::from_secs(20), |name, _| name == "roundtable.floor").await;
    table.send(roundtable::Command::End);
    let events = collect(&mut tap, "p9", Duration::from_secs(30), |name, _| name == "roundtable.ended").await;
    let t = trace(&events);
    assert!(table.is_ended(), "{t:#?}");

    let first_ada = all(&start, "acp.prompt.sent", "Ada")[0]["text"].as_str().unwrap();
    assert!(first_ada.contains("Your profile score is 50. You have 2 ratings across 1 earlier sessions."), "{first_ada}");
    let sent = |seat: &str| all(&events, "acp.prompt.sent", seat).iter().map(|d| d["text"].as_str().unwrap().to_string()).collect::<Vec<_>>();
    for seat in ["Ada", "Bo"] {
        let prompts = sent(seat);
        assert!(prompts.iter().any(|p| p.ends_with("Your private scorecard was received.")), "{seat}: {prompts:#?}");
        let results = prompts.iter().find(|p| p.contains("The ranking from received scorecards")).unwrap_or_else(|| panic!("{seat}: {prompts:#?}"));
        // Both got 4 stars everywhere from one card: 80 points. Ada's rating adds her 50.
        assert!(results.contains(&format!("{ada_name}: 80 points from 1 scorecards; rating 130")), "{results}");
        assert!(results.contains(&format!("{bo_name}: 80 points from 1 scorecards; rating 80")), "{results}");
    }
}

/// Owner's AgentIdentity: an identity carries to a new table by resuming its session, so the
/// agent keeps its genesis name (the name follows from the session id).
#[tokio::test(flavor = "multi_thread")]
async fn a_resumed_seat_keeps_its_identity() {
    let mut ada = seat("Ada", json!([{"reply": "PASS", "delay_ms": 200}]));
    ada.launch.env.insert("FAKE_RESUME".into(), "resume".into());
    ada.resume_session = Some("ada-genesis-session".into());
    let bo = seat("Bo", json!([{"reply": "PASS", "delay_ms": 200}]));
    let (table, _bus, mut tap) = start("p10", config(vec![ada, bo], false, 512), pass_jev().await);
    let events = collect(&mut tap, "p10", Duration::from_secs(20), |name, _| name == "roundtable.floor").await;
    table.send(roundtable::Command::End);
    let t = trace(&events);
    assert!(!all(&events, "acp.session.resumed", "Ada").is_empty(), "{t:#?}");
    let ready = all(&events, "roundtable.seat.ready", "Ada")[0];
    assert_eq!(ready["session"], "ada-genesis-session");
    assert_eq!(ready["name"], roundtable::names::genesis_name("ada-genesis-session"));
}

/// R §7: an agent busy when the poll begins is asked once its work ends, and the poll waits.
#[tokio::test(flavor = "multi_thread")]
async fn an_agent_busy_at_poll_time_is_asked_when_free() {
    let (jev, _) = fake_jev(0.8, false).await;
    let ada = seat("Ada", json!([{"reply": "work finished", "delay_ms": 3000}, {"reply": "PASS"}]));
    let pass = |n: &str| seat(n, json!([{"reply": "PASS"}]));
    let (table, bus, mut tap) = start("p11", config(vec![ada, pass("Bo"), pass("Cy")], true, 512), jev);
    let sent = collect(&mut tap, "p11", Duration::from_secs(20), |name, data| name == "acp.prompt.sent" && data["harness"] == "p11/Ada").await;
    tool_call(&bus, "p11/Ada", &sent.last().unwrap().1);
    let events = collect(&mut tap, "p11", Duration::from_secs(30), |name, _| name == "roundtable.topic").await;
    table.send(roundtable::Command::End);
    let t = trace(&events);
    let polling = events.iter().find(|(n, _)| n == "roundtable.topic.polling").map(|(_, d)| d).unwrap_or_else(|| panic!("{t:#?}"));
    assert!(polling["seats"].as_array().unwrap().iter().any(|s| s == "Ada"), "Ada is polled: {t:#?}");
    let ada_proposed = events.iter().position(|(n, d)| n == "roundtable.topic.proposed" && d["seat"] == "Ada").unwrap_or_else(|| panic!("{t:#?}"));
    let changed = events.iter().position(|(n, _)| n == "roundtable.topic").unwrap();
    assert!(ada_proposed < changed, "{t:#?}");
}

/// Audit D7, R §4.6: a veto notice waits for the agent's next discussion turn. A rating
/// request that comes first does not carry it.
#[tokio::test(flavor = "multi_thread")]
async fn a_veto_notice_waits_for_the_next_discussion_turn() {
    let (jev, _) = fake_jev(0.95, false).await;
    let ada = seat("Ada", json!([{"reply": "VETO this one"}, {"reply": "PASS"}]));
    let bo = seat("Bo", json!([{"reply": "Bo speaks", "delay_ms": 3000}]));
    let (table, _bus, mut tap) = start("d7", config(vec![ada, bo], true, 512), jev);
    let mut events = collect(&mut tap, "d7", Duration::from_secs(30), |name, data| name == "roundtable.floor" && data["seat"] == "Bo").await;
    assert_eq!(all(&events, "roundtable.contribution", "Ada")[0]["accepted"], false, "{:#?}", trace(&events));
    table.send(roundtable::Command::End);
    events.extend(
        collect(&mut tap, "d7", Duration::from_secs(30), |name, data| {
            name == "acp.prompt.sent" && data["harness"] == "d7/Ada" && data["text"].as_str().unwrap().contains("Rate each other participant by name: ")
        })
        .await,
    );
    let rating = events.last().unwrap().1["text"].as_str().unwrap();
    assert!(rating.contains("Rate each other participant by name: "), "{rating}");
    assert!(!rating.contains("We're sorry"), "the rejection belongs to a discussion turn:\n{rating}");
}

/// Audit M10, D §5.2: "`idle` does not necessarily mean background work has ceased". An agent
/// that reports background work after its turn is working: its turns are skipped (R §4.4)
/// until it reports none, and then it speaks again.
#[tokio::test(flavor = "multi_thread")]
async fn reported_background_work_skips_the_agent_until_it_ends() {
    let mut ada = seat("Ada", json!([{"reply": "Ada starts a build", "background_ms": 1500}, {"reply": "PASS"}]));
    ada.launch.env.insert("FAKE_PROTOCOL".into(), "2".into());
    let pass = |n: &str| seat(n, json!([{"reply": "PASS", "delay_ms": 100}]));
    let (table, _bus, mut tap) = start("m10", config(vec![ada, pass("Bo"), pass("Cy")], false, 512), pass_jev().await);
    let floors = std::sync::atomic::AtomicUsize::new(0);
    let events = collect(&mut tap, "m10", Duration::from_secs(30), |name, data| {
        name == "roundtable.floor" && data["seat"] == "Ada" && floors.fetch_add(1, std::sync::atomic::Ordering::SeqCst) == 1
    })
    .await;
    table.send(roundtable::Command::End);
    let t = trace(&events);
    let pos = |name: &str, pred: &dyn Fn(&Value) -> bool| events.iter().position(|(n, d)| n == name && pred(d)).unwrap_or_else(|| panic!("no {name}: {t:#?}"));
    let started = pos("roundtable.background", &|d| d["seat"] == "Ada" && d["items"] == 1);
    let skipped = pos("roundtable.skipped", &|d| d["seat"] == "Ada" && d["reason"] == "working");
    let ended = pos("roundtable.background", &|d| d["seat"] == "Ada" && d["items"] == 0);
    let second: Vec<usize> = events.iter().enumerate().filter(|(_, (n, d))| n == "roundtable.floor" && d["seat"] == "Ada").map(|(i, _)| i).collect();
    assert!(started < skipped && skipped < ended && ended < second[1], "{t:#?}");
}

/// Owner: a table runs its rounds (10 by default), each turn starts with the round line, and
/// after the last round the rating round starts.
#[tokio::test(flavor = "multi_thread")]
async fn the_table_ends_after_its_rounds_with_the_countdown_on_each_turn() {
    let pass = |n: &str| seat(n, json!([{"reply": "PASS"}]));
    let mut cfg = config(vec![pass("Ada"), pass("Bo")], false, 512);
    cfg.rounds = Some(2);
    let (_table, _bus, mut tap) = start("p12", cfg, pass_jev().await);
    let events = collect(&mut tap, "p12", Duration::from_secs(30), |name, _| name == "roundtable.ratings.asked").await;
    let t = trace(&events);
    assert!(events.iter().any(|(n, d)| n == "roundtable.notice" && d["text"] == "The table finished its 2 rounds."), "{t:#?}");
    let turns: Vec<String> = events
        .iter()
        .filter(|(n, d)| n == "acp.prompt.sent" && d["harness"] == "p12/Ada")
        .map(|(_, d)| d["text"].as_str().unwrap().to_string())
        .collect();
    assert!(turns[0].contains("Current delivery:\n1 Round Remains"), "{}", turns[0]);
    assert!(turns[1].starts_with("Final Round"), "{}", turns[1]);
    assert_eq!(all(&events, "roundtable.floor", "").len(), 4, "two rounds of two turns: {t:#?}");
}
