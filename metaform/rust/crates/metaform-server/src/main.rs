//! `metaform`: the functional map server and the stdio forwarder in one binary.
//!
//! ```text
//! metaform serve [--home DIR]                  run the server for a home (one per home)
//! metaform mcp   [--home DIR] [--project DIR]  stdio MCP for an agent harness; DIR defaults to .
//! metaform mcp   [--home DIR] --map NAME       stdio MCP on a map that belongs to no project
//! metaform call  [--home DIR] [--project DIR | --map NAME] '<json command>' | -
//!                                              one tool command; `-` reads it from stdin.
//!                                              Exit 0 ok, 1 refused, 2 usage or connection error.
//! metaform settings [--home DIR] [--project DIR]          every setting, its value and its source
//! metaform set   [--home DIR] [--project DIR] KEY VALUE   set a setting (VALUE is JSON, or text)
//! metaform unset [--home DIR] [--project DIR] KEY         remove it, so the next level applies
//! ```
//!
//! The home defaults to `METAFORM_HOME`, then `~/.metaform`.

use std::path::PathBuf;
use std::process::ExitCode;

#[tokio::main]
async fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let mut home = metaform_server::default_home();
    let mut project: Option<PathBuf> = None;
    let mut map: Option<String> = None;
    let mut positional: Vec<String> = Vec::new();
    let mut rest = args.iter().skip(1);
    while let Some(arg) = rest.next() {
        if !arg.starts_with("--") {
            positional.push(arg.clone());
            continue;
        }
        let value = rest.next().map(PathBuf::from);
        match (arg.as_str(), value) {
            ("--home", Some(v)) => home = v,
            ("--project", Some(v)) => project = Some(v),
            ("--map", Some(v)) => map = Some(v.to_string_lossy().to_string()),
            _ => return usage(&format!("unknown or incomplete option {arg}")),
        }
    }
    let target = match (project, map) {
        (Some(_), Some(_)) => return usage("give --project or --map, not both"),
        (None, Some(name)) => metaform_server::Target::Map(name),
        (folder, None) => {
            metaform_server::Target::Project(folder.unwrap_or_else(|| PathBuf::from(".")))
        }
    };
    let command = args.first().map(String::as_str);
    if let Some(command @ ("settings" | "set" | "unset")) = command {
        let folder = match &target {
            metaform_server::Target::Project(folder) if args.iter().any(|a| a == "--project") => Some(folder.clone()),
            metaform_server::Target::Map(_) => return usage("settings belong to the home or a project, not a map"),
            _ => None,
        };
        return settings(&home, command, folder, &positional).await;
    }
    if command != Some("call") && !positional.is_empty() {
        return usage(&format!("unexpected argument {}", positional[0]));
    }
    if command == Some("call") {
        return call(&home, &target, &positional).await;
    }
    let result = match args.first().map(String::as_str) {
        Some("serve") => metaform_server::serve(&home).await,
        Some("mcp") => match std::env::current_exe() {
            Ok(exe) => metaform_server::forward(&home, &target, &exe).await,
            Err(e) => Err(e.to_string()),
        },
        _ => return usage("expected serve, mcp, call, settings, set or unset"),
    };
    match result {
        Ok(()) => ExitCode::SUCCESS,
        Err(reason) => {
            eprintln!("metaform: {reason}");
            if reason.contains("owned by another functional map server") {
                ExitCode::from(metaform_server::HOME_OWNED as u8)
            } else {
                ExitCode::FAILURE
            }
        }
    }
}

/// `metaform call`: print the tool's result; exit 0 ok, 1 refused, 2 usage or connection error.
async fn call(
    home: &std::path::Path,
    target: &metaform_server::Target,
    positional: &[String],
) -> ExitCode {
    let [command] = positional else {
        return usage("call takes one JSON command, or - to read it from stdin");
    };
    let text = if command == "-" {
        let mut text = String::new();
        if let Err(e) = std::io::Read::read_to_string(&mut std::io::stdin(), &mut text) {
            return usage(&format!("could not read the command from stdin: {e}"));
        }
        text
    } else {
        command.clone()
    };
    let command: serde_json::Value = match serde_json::from_str(&text) {
        Ok(v @ serde_json::Value::Object(_)) => v,
        _ => return usage("the command must be one JSON object, such as '{\".\": {}}'"),
    };
    let exe = match std::env::current_exe() {
        Ok(exe) => exe,
        Err(e) => return usage(&e.to_string()),
    };
    match metaform_server::call::call(home, target, &exe, command).await {
        Ok(metaform_server::call::Answer::Ok(text)) => {
            println!("{text}");
            ExitCode::SUCCESS
        }
        Ok(metaform_server::call::Answer::Refused(text)) => {
            println!("{text}");
            ExitCode::from(1)
        }
        Err(reason) => {
            eprintln!("metaform: {reason}");
            ExitCode::from(2)
        }
    }
}

/// `metaform settings`, `set` and `unset` (R-4.8), through the server's admin request.
async fn settings(home: &std::path::Path, command: &str, folder: Option<PathBuf>, positional: &[String]) -> ExitCode {
    let project = match folder.map(std::fs::canonicalize).transpose() {
        Ok(p) => p.map(|p| p.to_string_lossy().to_string()),
        Err(e) => return usage(&format!("--project: {e}")),
    };
    let body = match (command, positional) {
        ("settings", []) => serde_json::json!({"settings": {"project": project}}),
        ("set", [key, value]) => {
            let value = serde_json::from_str(value).unwrap_or_else(|_| serde_json::Value::String(value.clone()));
            serde_json::json!({"set": {"key": key, "value": value, "project": project}})
        }
        ("unset", [key]) => serde_json::json!({"set": {"key": key, "project": project}}),
        _ => return usage(&format!("{command} takes {}", match command { "set" => "KEY VALUE", "unset" => "KEY", _ => "no arguments" })),
    };
    let exe = match std::env::current_exe() {
        Ok(exe) => exe,
        Err(e) => return usage(&e.to_string()),
    };
    match metaform_server::admin::request(home, &exe, body).await {
        Ok(answer) => {
            match command {
                "settings" => println!("{}", serde_json::to_string_pretty(&answer["settings"]).unwrap_or_default()),
                _ => println!("done; it applies {}", answer["applies"].as_str().unwrap_or("at once")),
            }
            ExitCode::SUCCESS
        }
        Err(reason) => {
            eprintln!("metaform: {reason}");
            ExitCode::from(1)
        }
    }
}

fn usage(problem: &str) -> ExitCode {
    eprintln!(
        "metaform: {problem}\nusage: metaform serve [--home DIR]\n       metaform mcp  [--home DIR] [--project DIR | --map NAME]\n       metaform call [--home DIR] [--project DIR | --map NAME] '<json command>' | -\n       metaform settings [--home DIR] [--project DIR]\n       metaform set [--home DIR] [--project DIR] KEY VALUE\n       metaform unset [--home DIR] [--project DIR] KEY"
    );
    ExitCode::from(2)
}
