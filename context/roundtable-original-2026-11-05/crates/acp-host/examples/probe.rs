//! Launch a harness, open a session, print its configuration options and, optionally, run
//! one prompt and print every event.
//!
//!   cargo run -p acp-host --example probe -- <harness-id> [prompt]
//!
//! <harness-id> is a built-in catalog id (claude-acp, codex-acp, pi-acp, opencode) or a
//! full command line in quotes.

use std::sync::Arc;

use acp_host::events::{HarnessExited, PromptCompleted, PromptFailed};
use acp_host::{Harness, ScopePolicy, launch};
use bus::Bus;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let mut args = std::env::args().skip(1);
    let id = args.next().expect("harness id");
    let prompt = args.next();
    let spec = match launch::builtin().into_iter().find(|entry| entry.id == id) {
        Some(entry) => entry.launch.expect("launch spec"),
        None => acp_host::LaunchSpec::from_command_line(&id)?,
    };

    let bus = Bus::new();
    let mut tap = bus.tap();
    tokio::spawn(async move {
        while let Some(event) = tap.recv().await {
            if event.name != "acp.agent.text" {
                println!("[{}] {} {}", event.seq, event.name, event.to_json().unwrap());
            }
        }
    });

    let workspace = std::env::temp_dir().join("acp-host-probe");
    std::fs::create_dir_all(&workspace)?;
    let mut exited = bus.subscribe::<HarnessExited>();
    let harness = Harness::launch("probe", &id, &spec, bus.clone(), Arc::new(ScopePolicy::new(&workspace))).await?;
    println!("NEGOTIATED: ACP v{}", harness.protocol_version());
    let session = harness.open_session(&workspace, vec![]).await?;
    // PROBE_CONFIG="model=sonnet,mode=default" sets advertised options before prompting.
    if let Ok(settings) = std::env::var("PROBE_CONFIG") {
        for pair in settings.split(',').filter(|pair| !pair.is_empty()) {
            let (key, value) = pair.split_once('=').expect("key=value");
            harness.set_config(&session, key, value).await?;
        }
    }

    if let Some(text) = prompt {
        let mut done = bus.subscribe::<PromptCompleted>();
        let mut failed = bus.subscribe::<PromptFailed>();
        harness.prompt(&session, text)?;
        tokio::select! {
            Some(completed) = done.recv() => println!("\nREPLY: {}", completed.event.reply),
            Some(failure) = failed.recv() => println!("\nFAILED: {}", failure.event.error),
        }
    }
    harness.shutdown();
    if let Some(exit) = exited.recv().await {
        println!("EXITED: code {:?}", exit.event.code);
    }
    Ok(())
}
