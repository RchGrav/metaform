//! `metaform-web [--home DIR] [--assets DIR] [--port N] FOLDER...`
//!
//! Serves the graph workspace on http://127.0.0.1:<port>/ for the project folders given.
//! The command that users type to open the workspace is not decided (an owner decision in
//! dev/graph_workspace_graph.md); until then this binary is the host.

use std::path::PathBuf;
use std::process::ExitCode;

use metaform_web::{Config, projects_from, serve};

fn usage(problem: &str) -> ExitCode {
    eprintln!("metaform-web: {problem}");
    eprintln!("usage: metaform-web [--home DIR] [--assets DIR] [--port N] FOLDER...");
    ExitCode::from(2)
}

#[tokio::main]
async fn main() -> ExitCode {
    let mut args = std::env::args_os().skip(1);
    let mut home = metaform_server::default_home();
    let mut assets = PathBuf::from("metaform/workspace/dist");
    let mut port: u16 = 0;
    let mut folders = Vec::new();
    while let Some(arg) = args.next() {
        match arg.to_str() {
            Some("--home") => match args.next() { Some(v) => home = v.into(), None => return usage("--home needs a folder") },
            Some("--assets") => match args.next() { Some(v) => assets = v.into(), None => return usage("--assets needs a folder") },
            Some("--port") => match args.next().and_then(|v| v.to_str()?.parse().ok()) {
                Some(p) => port = p,
                None => return usage("--port needs a number"),
            },
            Some(flag) if flag.starts_with("--") => return usage(&format!("unknown option {flag}")),
            _ => match std::fs::canonicalize(&arg) {
                Ok(folder) => folders.push(folder),
                Err(e) => return usage(&format!("{}: {e}", PathBuf::from(&arg).display())),
            },
        }
    }
    if folders.is_empty() {
        return usage("name at least one project folder");
    }
    if !assets.join("index.html").is_file() {
        return usage(&format!("{} has no index.html; build the workspace first (npm run build)", assets.display()));
    }
    // The server binary sits beside this one in a cargo build.
    let server_exe = match std::env::current_exe() {
        Ok(exe) => exe.with_file_name("metaform"),
        Err(e) => return usage(&e.to_string()),
    };
    let listener = match tokio::net::TcpListener::bind(("127.0.0.1", port)).await {
        Ok(l) => l,
        Err(e) => return usage(&format!("cannot listen on 127.0.0.1:{port}: {e}")),
    };
    let projects = projects_from(&folders);
    if let Ok(addr) = listener.local_addr() {
        println!("Graph workspace: http://{addr}/");
        for p in &projects {
            println!("  {} -> {}", p.id, p.folder.display());
        }
    }
    let config = Config { home, server_exe, assets, projects };
    match serve(config, listener).await {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("metaform-web: {e}");
            ExitCode::FAILURE
        }
    }
}
