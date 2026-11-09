//! `roundtable`: the standalone tool.
//!
//!   roundtable [serve] [--host 127.0.0.1] [--port 4180]   web interface; prints its URL with the chair token
//!   roundtable run <table.json> [--port 4180]             run one table headless, printing the chat
//!
//! The OpenRouter key for JEV comes from OPENROUTER_API_KEY or the web interface's settings.
//! Every /api request needs the chair token printed at start (ROUNDTABLE_TOKEN sets it).

mod app;
mod tables;

use std::net::SocketAddr;

use anyhow::{Context, Result, bail};

#[tokio::main]
async fn main() -> Result<()> {
    let mut args: Vec<String> = std::env::args().skip(1).collect();
    let mut flag = |name: &str| -> Option<String> {
        let at = args.iter().position(|a| a == name)?;
        args.remove(at);
        (at < args.len()).then(|| args.remove(at))
    };
    let host = flag("--host").unwrap_or_else(|| "127.0.0.1".into());
    let port: u16 = flag("--port").map(|p| p.parse()).transpose().context("--port")?.unwrap_or(4180);
    let addr: SocketAddr = format!("{host}:{port}").parse().context("--host/--port")?;
    if !addr.ip().is_loopback() {
        eprintln!("warning: listening on {addr}, beyond this machine. Every API call still needs the chair token.");
    }

    // Bind before anything else, so a busy port fails now rather than after agents launch.
    let listener = tokio::net::TcpListener::bind(addr).await.with_context(|| format!("could not listen on {addr}"))?;
    let addr = listener.local_addr()?;
    let state = app::AppState::new(addr);
    match args.first().map(String::as_str) {
        None | Some("serve") => {
            eprintln!("Roundtable on http://{addr}/#token={}", state.token);
            app::serve(state, listener).await
        }
        Some("run") => {
            let path = args.get(1).context("roundtable run <table.json>")?;
            let request: tables::CreateTable = serde_json::from_str(&std::fs::read_to_string(path)?)?;
            let server = tokio::spawn(app::serve(state.clone(), listener));
            let id = tables::create(&state, request).await?;
            tokio::select! {
                _ = app::print_chat(&state, &id) => {}
                result = server => bail!("the server stopped: {result:?}"),
            }
            Ok(())
        }
        Some(other) => bail!("unknown command {other}; use serve or run"),
    }
}
