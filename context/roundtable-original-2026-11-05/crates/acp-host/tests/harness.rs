//! `Harness` against the scripted fake agent: version negotiation (v2 first, fresh v1
//! fallback), v1 and v2 turn completion, reply extraction and ordering, one turn per
//! session, authentication, configuration, permission answering, resume/load, session
//! close at shutdown, a harness exiting mid-turn, and process-group cleanup.
//!
//! The timeouts here only bound how long a broken test can hang; nothing under test waits.

use std::sync::Arc;
use std::time::Duration;

use acp_host::events::{
    AgentState, AgentText, Authenticated, ConfigChanged, ForegroundState, HarnessExited, HarnessStarted, PermissionDecided,
    PromptCompleted, PromptFailed, SessionClosed, SessionResumed,
};
use acp_host::{Harness, LaunchSpec, ScopePolicy};
use bus::{Bus, Event, Subscription};
use serde_json::{Value, json};

const LIMIT: Duration = Duration::from_secs(10);

struct Fake {
    harness: Harness,
    session: String,
    bus: Bus,
    root: std::path::PathBuf,
}

fn spec(script: Value, env: &[(&str, &str)]) -> LaunchSpec {
    let mut spec = LaunchSpec::new(env!("CARGO_BIN_EXE_acp-fake-agent"), Vec::<String>::new());
    spec.env.insert("FAKE_SCRIPT".into(), script.to_string());
    for (name, value) in env {
        spec.env.insert((*name).into(), (*value).into());
    }
    spec
}

fn workspace() -> std::path::PathBuf {
    let nanos = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos();
    let root = std::env::temp_dir().join(format!("acp-host-harness-{}-{nanos}", std::process::id()));
    std::fs::create_dir_all(&root).unwrap();
    root.canonicalize().unwrap()
}

async fn start(script: Value, env: &[(&str, &str)], bus: &Bus) -> (Harness, std::path::PathBuf) {
    let root = workspace();
    let harness = Harness::launch("h", "fake", &spec(script, env), bus.clone(), Arc::new(ScopePolicy::new(&root))).await.unwrap();
    (harness, root)
}

async fn launch_with(script: Value, env: &[(&str, &str)]) -> Fake {
    let bus = Bus::new();
    let (harness, root) = start(script, env, &bus).await;
    let session = harness.open_session(&root, vec![]).await.unwrap();
    Fake { harness, session, bus, root }
}

async fn launch(script: Value) -> Fake {
    launch_with(script, &[]).await
}

async fn next<E: Event + Clone>(subscription: &mut Subscription<E>) -> E {
    E::clone(&tokio::time::timeout(LIMIT, subscription.recv()).await.expect("event did not arrive").expect("bus closed").event)
}

#[tokio::test(flavor = "multi_thread")]
async fn reply_is_complete_and_one_turn_runs_per_session() {
    // The last chunk is sent immediately before the response: it must be in the reply.
    let Fake { harness, session, bus, .. } = launch(json!([{"reply": "Hello world", "first_chunk": "Hello ", "delay_ms": 150}])).await;
    let mut done = bus.subscribe::<PromptCompleted>();
    harness.prompt(&session, "go").unwrap();
    assert!(harness.is_busy(&session));
    assert!(harness.prompt(&session, "again").is_err(), "a second prompt while one runs is refused");
    let completed = next(&mut done).await;
    assert_eq!(completed.reply, "Hello world");
    assert!(!harness.is_busy(&session));
    harness.shutdown();
}

#[tokio::test(flavor = "multi_thread")]
async fn the_reply_has_the_text_before_and_after_a_tool_call() {
    for protocol in ["1", "2"] {
        let Fake { harness, session, bus, .. } =
            launch_with(json!([{"reply": "Let me check.", "tool_then": "Final answer."}]), &[("FAKE_PROTOCOL", protocol)]).await;
        let mut done = bus.subscribe::<PromptCompleted>();
        harness.prompt(&session, "go").unwrap();
        assert_eq!(next(&mut done).await.reply, "Let me check.\n\nFinal answer.", "ACP v{protocol}");
        harness.shutdown();
    }
}

#[tokio::test(flavor = "multi_thread")]
async fn a_v2_agent_negotiates_v2_and_its_turn_ends_on_idle() {
    let bus = Bus::new();
    let mut started = bus.subscribe::<HarnessStarted>();
    let (harness, root) = start(json!([{"reply": "Hello world", "first_chunk": "Hello ", "delay_ms": 150}]), &[("FAKE_PROTOCOL", "2")], &bus).await;
    assert_eq!(harness.protocol_version(), 2);
    let started = next(&mut started).await;
    assert_eq!((started.protocol_version, started.v1_fallback), (2, None));
    assert!(harness.accepts_http_mcp());
    let mut states = bus.subscribe::<AgentState>();
    let session = harness.open_session(&root, vec![]).await.unwrap();
    // The new session reports idle before any prompt: not a turn's end.
    let stale = next(&mut states).await;
    assert_eq!((stale.state, stale.prompt), (ForegroundState::Idle, None));

    let mut text = bus.subscribe::<AgentText>();
    let mut done = bus.subscribe::<PromptCompleted>();
    let prompt = harness.prompt(&session, "go").unwrap();
    let running = next(&mut states).await;
    assert_eq!((running.state, running.prompt), (ForegroundState::Running, Some(prompt)));
    // Accepted, running, not finished: the prompt response did not end the turn.
    assert!(harness.is_busy(&session));
    let idle = next(&mut states).await;
    assert_eq!((idle.state, idle.stop_reason.as_deref()), (ForegroundState::Idle, Some("end_turn")));
    let completed = next(&mut done).await;
    assert_eq!((completed.prompt, completed.stop_reason.as_str(), completed.reply.as_str()), (prompt, "end_turn", "Hello world"));
    assert!(!harness.is_busy(&session));
    // The closing snapshot repeats the streamed text: no duplicate is published.
    let mut streamed = String::new();
    while let Ok(Some(piece)) = tokio::time::timeout(Duration::from_millis(50), text.recv()).await {
        assert!(!piece.event.replace);
        assert_eq!(piece.event.message.as_deref(), Some("m1"));
        streamed.push_str(&piece.event.text);
    }
    assert_eq!(streamed, "Hello world");
    harness.shutdown();
}

#[tokio::test(flavor = "multi_thread")]
async fn a_v1_only_agent_is_restarted_fresh_on_v1() {
    let bus = Bus::new();
    let mut tap = bus.tap();
    let (harness, root) = start(json!([{"reply": "one"}]), &[], &bus).await;
    assert_eq!(harness.protocol_version(), 1);
    let session = harness.open_session(&root, vec![]).await.unwrap();
    let mut done = bus.subscribe::<PromptCompleted>();
    harness.prompt(&session, "go").unwrap();
    // v1 semantics: the prompt response ends the turn (the fake sends no state updates).
    assert_eq!(next(&mut done).await.reply, "one");
    let mut started = Vec::new();
    while let Ok(Some(envelope)) = tokio::time::timeout(Duration::from_millis(50), tap.recv()).await {
        if let Some(event) = envelope.downcast::<HarnessStarted>() {
            started.push(event.clone());
        }
        assert!(envelope.downcast::<HarnessExited>().is_none(), "the declined v2 attempt is not a harness exit");
    }
    assert_eq!(started.len(), 1);
    assert_eq!(started[0].protocol_version, 1);
    assert!(started[0].v1_fallback.as_deref().is_some_and(|reason| reason.contains("selected ACP v1")), "{:?}", started[0].v1_fallback);
    harness.shutdown();
}

#[tokio::test(flavor = "multi_thread")]
async fn authentication_is_completed_then_the_session_opens() {
    for (protocol, call) in [("1", "authenticate"), ("2", "auth/login")] {
        let bus = Bus::new();
        let mut authenticated = bus.subscribe::<Authenticated>();
        let (harness, root) = start(json!([]), &[("FAKE_PROTOCOL", protocol), ("FAKE_AUTH", "1")], &bus).await;
        harness.open_session(&root, vec![]).await.unwrap();
        let event = next(&mut authenticated).await;
        assert_eq!((event.call.as_str(), event.method.as_str()), (call, "fake-login"));
        harness.shutdown();
    }
}

#[tokio::test(flavor = "multi_thread")]
async fn authentication_that_does_not_help_or_cannot_run_is_an_error() {
    for protocol in ["1", "2"] {
        let bus = Bus::new();
        let (harness, root) = start(json!([]), &[("FAKE_PROTOCOL", protocol), ("FAKE_AUTH", "broken")], &bus).await;
        let error = harness.open_session(&root, vec![]).await.unwrap_err();
        assert!(format!("{error:#}").contains("after authenticating"), "v{protocol}: {error:#}");
        harness.shutdown();

        let (harness, root) = start(json!([]), &[("FAKE_PROTOCOL", protocol), ("FAKE_AUTH", "nomethod")], &bus).await;
        let error = harness.open_session(&root, vec![]).await.unwrap_err();
        assert!(format!("{error:#}").contains("no authentication method"), "v{protocol}: {error:#}");
        harness.shutdown();
    }
}

#[tokio::test(flavor = "multi_thread")]
async fn only_advertised_options_are_set() {
    for protocol in ["1", "2"] {
        let Fake { harness, session, bus, .. } = launch_with(json!([]), &[("FAKE_PROTOCOL", protocol)]).await;
        let mut changed = bus.subscribe::<ConfigChanged>();
        let error = harness.set_config(&session, "effort", "high").await.unwrap_err().to_string();
        assert!(error.contains("\"effort\"") && error.contains("advertises: model"), "v{protocol}: {error}");
        harness.set_config(&session, "model", "smart").await.unwrap();
        assert_eq!(next(&mut changed).await.config_options[0].current.as_deref(), Some("smart"));
        let mut exited = bus.subscribe::<HarnessExited>();
        harness.shutdown();
        let stderr = next(&mut exited).await.stderr_tail;
        assert!(stderr.contains("set model") && !stderr.contains("set effort"), "the unadvertised option was sent: {stderr}");
    }
}

#[tokio::test(flavor = "multi_thread")]
async fn shutdown_closes_open_sessions_then_ends_the_process() {
    for protocol in ["1", "2"] {
        let Fake { harness, session, bus, .. } = launch_with(json!([]), &[("FAKE_PROTOCOL", protocol)]).await;
        let mut closed = bus.subscribe::<SessionClosed>();
        let mut exited = bus.subscribe::<HarnessExited>();
        harness.shutdown();
        let event = next(&mut closed).await;
        assert_eq!((event.session.as_str(), event.error), (session.as_str(), None));
        let exit = next(&mut exited).await;
        assert!(exit.stderr_tail.contains("closed fake-session"), "v{protocol}: {}", exit.stderr_tail);
        // The agent exits on its own once stdin closes: no signal was needed.
        assert_eq!(exit.code, Some(0), "v{protocol}");
    }
}

#[tokio::test(flavor = "multi_thread")]
async fn sessions_are_resumed_or_loaded_without_republishing_history() {
    // v1 with session/load: the replayed message and tool call are not new activity.
    let bus = Bus::new();
    let mut tap = bus.tap();
    let (harness, root) = start(json!([{"reply": "fresh"}]), &[], &bus).await;
    let mut resumed = bus.subscribe::<SessionResumed>();
    let session = harness.resume_session(&root, "old-session", vec![]).await.unwrap();
    assert_eq!(session, "old-session");
    assert_eq!(next(&mut resumed).await.method, "session/load");
    let mut done = bus.subscribe::<PromptCompleted>();
    harness.prompt(&session, "go").unwrap();
    assert_eq!(next(&mut done).await.reply, "fresh");
    while let Ok(Some(envelope)) = tokio::time::timeout(Duration::from_millis(50), tap.recv()).await {
        if let Some(text) = envelope.downcast::<AgentText>() {
            assert_ne!(text.text, "replayed history", "replayed history was republished");
        }
        assert!(envelope.downcast::<acp_host::events::ToolActivity>().is_none(), "a replayed tool call was republished");
    }
    harness.shutdown();

    for (env, method) in [(("FAKE_RESUME", "resume"), "session/resume"), (("FAKE_PROTOCOL", "2"), "session/resume")] {
        let bus = Bus::new();
        let mut resumed = bus.subscribe::<SessionResumed>();
        let (harness, root) = start(json!([]), &[env], &bus).await;
        harness.resume_session(&root, "old-session", vec![]).await.unwrap();
        let event = next(&mut resumed).await;
        assert_eq!((event.method.as_str(), event.config_options.len()), (method, 1));
        // A resumed session is used like a new one: its advertised options can be set.
        harness.set_config("old-session", "model", "smart").await.unwrap();
        harness.shutdown();
    }

    let bus = Bus::new();
    let (harness, root) = start(json!([]), &[("FAKE_RESUME", "none")], &bus).await;
    let error = harness.resume_session(&root, "old-session", vec![]).await.unwrap_err();
    assert!(error.to_string().contains("neither session/resume nor session/load"), "{error}");
    harness.shutdown();
}

#[tokio::test(flavor = "multi_thread")]
async fn permissions_inside_scope_are_allowed_once_and_outside_rejected() {
    for protocol in ["1", "2"] {
        let Fake { harness, session, bus, root } = launch_with(
            json!([
                {"reply": "in", "permission": {"kind": "edit", "path": "notes.md"}},
                {"reply": "out", "permission": {"kind": "edit", "path": "/etc/passwd"}}
            ]),
            &[("FAKE_PROTOCOL", protocol)],
        )
        .await;
        let _ = root;
        let mut done = bus.subscribe::<PromptCompleted>();
        let mut decided = bus.subscribe::<PermissionDecided>();
        harness.prompt(&session, "one").unwrap();
        assert_eq!(next(&mut done).await.reply, "in [permission: allow-once]", "one-time allow is preferred (v{protocol})");
        assert!(next(&mut decided).await.allowed);
        harness.prompt(&session, "two").unwrap();
        assert_eq!(next(&mut done).await.reply, "out [permission: reject-once]");
        assert!(!next(&mut decided).await.allowed);
        harness.shutdown();
    }
}

#[tokio::test(flavor = "multi_thread")]
async fn an_exit_mid_turn_fails_the_prompt_once_before_the_exit_event() {
    for protocol in ["1", "2"] {
        let Fake { harness, session, bus, .. } =
            launch_with(json!([{"reply": "partial", "first_chunk": "partial", "exit": true}]), &[("FAKE_PROTOCOL", protocol)]).await;
        let mut tap = bus.tap();
        harness.prompt(&session, "go").unwrap();
        let mut failed = 0;
        let order = tokio::time::timeout(LIMIT, async {
            let mut order = Vec::new();
            while let Some(envelope) = tap.recv().await {
                if envelope.downcast::<PromptFailed>().is_some() {
                    failed += 1;
                    order.push("failed");
                }
                if envelope.downcast::<PromptCompleted>().is_some() {
                    order.push("completed");
                }
                if let Some(exit) = envelope.downcast::<HarnessExited>() {
                    assert_eq!(exit.code, Some(3));
                    order.push("exited");
                    break;
                }
            }
            order
        })
        .await
        .unwrap();
        assert_eq!(order, vec!["failed", "exited"], "v{protocol}");
        assert_eq!(failed, 1);
        assert!(!harness.is_busy(&session));
    }
}

#[cfg(unix)]
#[tokio::test(flavor = "multi_thread")]
async fn shutdown_ends_the_whole_process_group() {
    let Fake { harness, session, bus, .. } = launch(json!([{"reply": "x", "grandchild": true, "delay_ms": 30000}])).await;
    let mut tap = bus.tap();
    harness.prompt(&session, "go").unwrap();
    let child = tokio::time::timeout(LIMIT, async {
        while let Some(envelope) = tap.recv().await {
            if let Some(text) = envelope.downcast::<AgentText>()
                && let Some(pid) = text.text.strip_prefix("[child:").and_then(|t| t.strip_suffix(']'))
            {
                return pid.parse::<u32>().unwrap();
            }
        }
        unreachable!()
    })
    .await
    .unwrap();
    assert!(std::path::Path::new(&format!("/proc/{child}")).exists());
    let mut exited = bus.subscribe::<HarnessExited>();
    harness.shutdown();
    next(&mut exited).await;
    // Reaped by init or a zombie at most; it must not still be running.
    let alive = std::fs::read_to_string(format!("/proc/{child}/stat"))
        .map(|stat| !stat.split(' ').nth(2).is_some_and(|state| state == "Z"))
        .unwrap_or(false);
    assert!(!alive, "the grandchild {child} survived shutdown");
}
