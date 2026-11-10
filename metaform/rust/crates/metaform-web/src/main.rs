//! `metaform-web [--home DIR] [--assets DIR] [--port N] [--read-only]`
//!
//! Serves the graph workspace on http://127.0.0.1:<port>/ for every project registered in the
//! home. A project is registered when an agent first connects from its folder.
//! Without `--port` the port is 4170, or any free port when 4170 is in use. The host prints the
//! address it serves. With `--read-only` the host refuses every write to a map; without it, the
//! page the host serves can store an edit. Users start this binary with `metaform gui` (owner decision, 2026-11-09).

use std::path::PathBuf;
use std::process::ExitCode;

use metaform_web::{Config, DEFAULT_PORT, listen, serve};

fn usage(problem: &str) -> ExitCode {
    eprintln!("metaform-web: {problem}");
    eprintln!("usage: metaform-web [--home DIR] [--assets DIR] [--port N] [--read-only]");
    ExitCode::from(2)
}

#[tokio::main]
async fn main() -> ExitCode {
    let mut args = std::env::args_os().skip(1);
    let mut home = metaform_server::default_home();
    let mut assets: Option<PathBuf> = None;
    let mut port: Option<u16> = None;
    let mut read_only = false;
    while let Some(arg) = args.next() {
        match arg.to_str() {
            Some("--home") => match args.next() { Some(v) => home = v.into(), None => return usage("--home needs a folder") },
            Some("--assets") => match args.next() { Some(v) => assets = Some(v.into()), None => return usage("--assets needs a folder") },
            Some("--port") => match args.next().and_then(|v| v.to_str()?.parse().ok()) {
                Some(p) => port = Some(p),
                None => return usage("--port needs a number"),
            },
            Some("--read-only") => read_only = true,
            _ => return usage(&format!("unexpected argument {}", PathBuf::from(&arg).display())),
        }
    }
    // Without --assets: a `workspace` folder installed beside this binary, then the source tree
    // this binary was built from (metaform/workspace/dist), so `metaform gui` works from any folder.
    let assets = match assets {
        Some(dir) => dir,
        None => {
            let beside = std::env::current_exe().ok().and_then(|exe| exe.parent().map(|d| d.join("workspace")));
            let built = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../../workspace/dist");
            beside.filter(|d| d.join("index.html").is_file()).unwrap_or(built)
        }
    };
    if !assets.join("index.html").is_file() {
        return usage(&format!("{} has no index.html; build the workspace first (npm run build in metaform/workspace)", assets.display()));
    }
    // The server binary sits beside this one in a cargo build.
    let server_exe = match std::env::current_exe() {
        Ok(exe) => exe.with_file_name("metaform"),
        Err(e) => return usage(&e.to_string()),
    };
    let listener = match listen(port, DEFAULT_PORT).await {
        Ok(l) => l,
        Err(e) => return usage(&format!("cannot listen on 127.0.0.1:{}: {e}", port.unwrap_or(DEFAULT_PORT))),
    };
    if let Ok(addr) = listener.local_addr() {
        println!("Graph workspace: http://{addr}/");
    }
    let config = Config { home, server_exe, assets, read_only };
    match serve(config, listener).await {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("metaform-web: {e}");
            ExitCode::FAILURE
        }
    }
}
