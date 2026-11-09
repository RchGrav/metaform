//! Tests of the `metaform` binary through its public interface: stdio MCP via the forwarder.
//! Budget (CLAUDE.md): five per feature. Five cover the server and standalone maps, two cover
//! announcements (R-4.10), one covers starting through the launcher (SL-6.1), two cover
//! `metaform call`, the CLI (R-5.14, R-5.17), two cover a server closing or restarting under a
//! forwarder, and the last covers settings through the CLI (R-4.8).
//! Every forwarder runs with `METAFORM_LAUNCHER` empty unless a test names a launcher, so the
//! tests never depend on a `hold` installed on the machine.

mod common;

use std::process::Command;
use std::time::Duration;

use common::{Agent, cli, stop_server};
use serde_json::{Value, json};

/// Happy path: an agent discovers the server, sees exactly one tool, writes and reads.
#[test]
fn one_tool_over_mcp_2026_07_28() {
    let dir = tempfile::tempdir().unwrap();
    let (home, project) = (dir.path().join("home"), dir.path().join("proj"));
    std::fs::create_dir_all(&project).unwrap();
    let mut agent = Agent::start(&home, &project);
    let discover = agent.request("server/discover", json!({}));
    assert!(
        discover["result"]["supportedVersions"]
            .as_array()
            .unwrap()
            .contains(&json!("2026-07-28"))
    );
    let tools = agent.request("tools/list", json!({}));
    let names: Vec<&str> = tools["result"]["tools"]
        .as_array()
        .unwrap()
        .iter()
        .map(|t| t["name"].as_str().unwrap())
        .collect();
    assert_eq!(names, ["project-map"], "Metaform has one tool");
    assert!(
        !agent
            .call(json!({"update": {"code.part": {"name": "part"}}}))
            .0
    );
    assert_eq!(
        agent.call(json!({"code.part": {}})),
        (false, json!({"code.part": {"name": "part"}}))
    );
    agent.stop();
    stop_server(&home);
    assert_eq!(
        std::fs::read_dir(&project).unwrap().count(),
        0,
        "nothing written into the project"
    );
}

/// R-4.4, R-4.5: two agents on one project at once share one server. Neither blocks the
/// other, and each sees the other's committed writes. A refusal reaches the agent with its
/// remediation.
#[test]
fn two_agents_share_one_project() {
    let dir = tempfile::tempdir().unwrap();
    let (home, project) = (dir.path().join("home"), dir.path().join("proj"));
    std::fs::create_dir_all(&project).unwrap();
    let mut first = Agent::start(&home, &project);
    first.request("server/discover", json!({}));
    let mut second = Agent::start(&home, &project);
    second.request("server/discover", json!({}));
    let want =
        json!({"why": "Receive the part.", "how": "Supplies the part.", "direction": "inbound"});
    assert!(
        !first
            .call(json!({"update": {"code.provider.part": {"name": "provider"}}}))
            .0
    );
    assert!(!second.call(json!({"update": {"code.receiver.part": {"name": "receiver", "wants": {"code.provider.part": want}}}})).0);
    let (refused, refusal) = first.call(json!({"delete": {"code.provider.part": {}}}));
    assert!(
        refused,
        "the provider is wanted by the second agent's element"
    );
    assert!(refusal["remediation"].is_object(), "{refusal}");
    assert_eq!(
        second.call(json!({"code.provider.part": {}})).1,
        json!({"code.provider.part": {"name": "provider"}})
    );
    first.stop();
    second.stop();
    stop_server(&home);
}

/// A home holding data this server did not write, such as the Node harness's, is refused
/// and left untouched.
#[test]
fn foreign_home_is_refused_and_untouched() {
    let dir = tempfile::tempdir().unwrap();
    let (home, project) = (dir.path().join("home"), dir.path().join("proj"));
    std::fs::create_dir_all(&home).unwrap();
    std::fs::create_dir_all(&project).unwrap();
    std::fs::write(home.join("metaform.lbug"), b"someone else's database").unwrap();
    let agent = Agent::start(&home, &project);
    let err = agent.stop();
    assert!(err.contains("did not write"), "{err}");
    assert_eq!(
        std::fs::read(home.join("metaform.lbug")).unwrap(),
        b"someone else's database"
    );
    assert!(!home.join("store.format").exists());
}

/// Storage note risk 3: every acknowledged write survives a SIGKILL of the server, because
/// a write is acknowledged only after its Ladybug transaction commits.
#[test]
fn acknowledged_writes_survive_sigkill() {
    let dir = tempfile::tempdir().unwrap();
    let (home, project) = (dir.path().join("home"), dir.path().join("proj"));
    std::fs::create_dir_all(&project).unwrap();
    let mut agent = Agent::start(&home, &project);
    agent.request("server/discover", json!({}));
    for i in 0..40 {
        let (refused, _) = agent
            .call(json!({"update": {format!("code.crash.part{i}"): {"name": format!("n{i}")}}}));
        assert!(!refused);
    }
    let pattern = format!("metaform serve --home {}", home.display());
    assert!(
        Command::new("pkill")
            .args(["-KILL", "-f", &pattern])
            .status()
            .unwrap()
            .success()
    );
    agent.stop();
    std::thread::sleep(std::time::Duration::from_millis(200));
    let mut again = Agent::start(&home, &project);
    again.request("server/discover", json!({}));
    for i in 0..40 {
        let address = format!("code.crash.part{i}");
        assert_eq!(
            again.call(json!({&address: {}})).1,
            json!({&address: {"name": format!("n{i}")}})
        );
    }
    again.stop();
    stop_server(&home);
}

/// R-4.15: agents open a map that belongs to no project with `--map <name>`. Two forwarders on
/// one name share that map, and it stays apart from the project maps. A name that is not one
/// address segment is refused with the reason. (The happy path and the refusal share one test
/// to stay within the five-test budget.)
#[test]
fn agents_share_a_map_that_belongs_to_no_project() {
    let dir = tempfile::tempdir().unwrap();
    let home = dir.path().join("home");
    let mut first = Agent::on_map(&home, "scout");
    first.request("server/discover", json!({}));
    let mut second = Agent::on_map(&home, "scout");
    second.request("server/discover", json!({}));
    assert!(
        !first
            .call(json!({"update": {"code.plan.route": {"name": "route"}}}))
            .0
    );
    assert_eq!(
        second.call(json!({"code.plan.route": {}})).1,
        json!({"code.plan.route": {"name": "route"}})
    );
    assert!(
        !second
            .call(json!({"update": {"code.plan.camp": {"name": "camp"}}}))
            .0
    );
    assert_eq!(
        first.call(json!({"code.plan.camp": {}})).1,
        json!({"code.plan.camp": {"name": "camp"}})
    );
    let mut other = Agent::on_map(&home, "elsewhere");
    other.request("server/discover", json!({}));
    assert!(
        other.call(json!({"code.plan.route": {}})).0,
        "another map does not hold scout's elements"
    );
    first.stop();
    second.stop();
    other.stop();
    assert!(
        home.join("maps/maps.lbug").exists(),
        "maps of no project share maps/maps.lbug"
    );
    assert!(
        !home.join("projects").exists()
            || std::fs::read_dir(home.join("projects")).unwrap().count() == 0
    );

    let refused = Agent::on_map(&home, "Bad Name").stop();
    assert!(refused.contains("not one address segment"), "{refused}");
    stop_server(&home);
}

/// R-4.10, the happy path: agent B listens to its map; agent A writes; B is told after the
/// commit and B's read of the resource shows the write. Nothing polls.
#[test]
fn a_commit_is_announced_to_listeners() {
    let dir = tempfile::tempdir().unwrap();
    let home = dir.path().join("home");
    let mut a = Agent::on_map(&home, "camp");
    a.request("server/discover", json!({}));
    let mut b = Agent::on_map(&home, "camp");
    b.request("server/discover", json!({}));
    let uri = b.listen_to_map();
    assert_eq!(uri, "metaform://map/standalone/camp");
    assert!(
        b.notice(
            "notifications/resources/updated",
            Duration::from_millis(300)
        )
        .is_none(),
        "nothing before a write"
    );

    assert!(
        !a.call(json!({"update": {"code.camp.fire": {"name": "fire"}}}))
            .0
    );
    let updated = b
        .notice("notifications/resources/updated", Duration::from_secs(5))
        .expect("B is told of A's commit");
    assert_eq!(updated["params"]["uri"], json!(uri));
    let read = b.request("resources/read", json!({"uri": uri}));
    let root: Value =
        serde_json::from_str(read["result"]["contents"][0]["text"].as_str().unwrap()).unwrap();
    assert!(
        root["addresses"]
            .as_array()
            .unwrap()
            .contains(&json!("code.camp.fire")),
        "{root}"
    );
    a.stop();
    b.stop();
    stop_server(&home);
}

/// R-4.7 order: a refused write commits nothing and announces nothing; the next good write is
/// announced exactly once, to the writer's own listener too.
#[test]
fn only_commits_are_announced() {
    let dir = tempfile::tempdir().unwrap();
    let home = dir.path().join("home");
    let mut a = Agent::on_map(&home, "notes");
    a.request("server/discover", json!({}));
    let want =
        json!({"why": "Receive the part.", "how": "Supplies the part.", "direction": "inbound"});
    assert!(!a.call(json!({"update": {"code.held.part": {"name": "held", "wants": {"code.base.part": want}}}})).0);
    a.listen_to_map();
    assert!(
        a.call(json!({"delete": {"code.base.part": {}}})).0,
        "deleting a wanted element is refused"
    );
    assert!(
        a.notice(
            "notifications/resources/updated",
            Duration::from_millis(500)
        )
        .is_none(),
        "a refusal is not announced"
    );
    assert!(
        !a.call(json!({"update": {"code.base.part": {"name": "base"}}}))
            .0
    );
    assert!(
        a.notice("notifications/resources/updated", Duration::from_secs(5))
            .is_some(),
        "the writer hears its own commit"
    );
    assert!(
        a.notice(
            "notifications/resources/updated",
            Duration::from_millis(500)
        )
        .is_none(),
        "exactly once"
    );
    a.stop();
    stop_server(&home);
}

/// Launcher step 5 (SL-6.1): with a launcher, the forwarder starts the server as a named user
/// call, with a name stable for the home. When that call already exists, the forwarder starts it
/// again by name rather than creating another. The launcher is a stub script, so the C launcher's
/// runtime never runs in a Rust test: it records its argv, keeps names in a folder, and starts the
/// server detached the way `hold -d` would.
#[test]
fn the_server_starts_through_the_launcher_under_a_stable_name() {
    let dir = tempfile::tempdir().unwrap();
    let (home, calls) = (dir.path().join("home"), dir.path().join("calls"));
    std::fs::create_dir_all(&calls).unwrap();
    let (stub, argv_log) = (dir.path().join("hold"), dir.path().join("argv.log"));
    let script = format!(
        "#!/bin/sh\necho \"$*\" >> '{log}'\n\
         if [ \"$1\" = -d ]; then\n  name=\"$3\"; shift 6\n\
           if [ -e '{calls}'/\"$name\" ]; then echo \"hold: error: call name '$name' already exists\" >&2; exit 5; fi\n\
           printf '%s\\n' \"$@\" > '{calls}'/\"$name\"\n  setsid \"$@\" >/dev/null 2>&1 < /dev/null &\n  exit 0\nfi\n\
         [ -e '{calls}'/\"$1\" ] || exit 127\n\
         set -- $(cat '{calls}'/\"$1\")\nsetsid \"$@\" >/dev/null 2>&1 < /dev/null &\nexit 0\n",
        log = argv_log.display(),
        calls = calls.display()
    );
    std::fs::write(&stub, script).unwrap();
    std::fs::set_permissions(&stub, std::os::unix::fs::PermissionsExt::from_mode(0o755)).unwrap();

    let start = |name: &str| {
        let mut agent =
            Agent::spawn_with_launcher(&home, &["--map".as_ref(), name.as_ref()], stub.as_os_str());
        agent.request("server/discover", json!({}));
        agent
    };
    let mut first = start("ops");
    assert!(
        !first
            .call(json!({"update": {"code.ops.part": {"name": "part"}}}))
            .0
    );
    first.stop();
    let lines = std::fs::read_to_string(&argv_log).unwrap();
    let created = lines.lines().next().unwrap();
    let name = created.split_whitespace().nth(2).unwrap().to_string();
    assert!(
        name.starts_with("metaform-") && name.len() == "metaform-".len() + 12,
        "{created}"
    );
    assert!(
        created.contains("--restart on-failure:3 --")
            && created.ends_with(&format!("serve --home {}", home.display())),
        "{created}"
    );

    stop_server(&home);
    let mut again = start("ops");
    assert_eq!(
        again.call(json!({"code.ops.part": {}})).1,
        json!({"code.ops.part": {"name": "part"}})
    );
    again.stop();
    let lines: Vec<String> = std::fs::read_to_string(&argv_log)
        .unwrap()
        .lines()
        .map(String::from)
        .collect();
    assert_eq!(
        lines.len(),
        3,
        "create, refused duplicate create, rerun by name: {lines:?}"
    );
    assert!(
        lines[1].contains(&format!("--name {name} ")),
        "the same name again: {lines:?}"
    );
    assert_eq!(
        lines[2], name,
        "rerun by name, not a duplicate call: {lines:?}"
    );
    stop_server(&home);
}

/// R-5.14 and R-5.17: one complete command line runs one tool command through the server and
/// prints the tool's result. A command can also come from stdin with `-`. Exit 0 on success.
#[test]
fn the_cli_runs_one_tool_command_per_line() {
    let dir = tempfile::tempdir().unwrap();
    let home = dir.path().join("home");
    let (code, out, err) = cli(
        &home,
        &[
            "--map",
            "specs",
            r#"{"update": {"document.spec.world": {"name": "world spec"}}}"#,
        ],
        None,
    );
    assert_eq!(code, 0, "{err}");
    assert_eq!(
        serde_json::from_str::<Value>(&out).unwrap()["status"],
        json!("ok")
    );
    let (code, out, err) = cli(
        &home,
        &["--map", "specs", "-"],
        Some(r#"{"document.spec.world": {}}"#),
    );
    assert_eq!(
        (code, serde_json::from_str::<Value>(&out).unwrap()),
        (0, json!({"document.spec.world": {"name": "world spec"}})),
        "{err}"
    );
    let (code, _, err) = cli(&home, &["--map", "specs", "not json"], None);
    assert_eq!(code, 2, "a usage error exits 2: {err}");
    stop_server(&home);
}

/// A refused command exits 1, and the refusal, with its code and remediation, is still printed.
#[test]
fn a_refused_cli_command_exits_one_and_prints_the_refusal() {
    let dir = tempfile::tempdir().unwrap();
    let home = dir.path().join("home");
    let (code, out, err) = cli(
        &home,
        &["--map", "specs", r#"{"document.spec.missing": {}}"#],
        None,
    );
    assert_eq!(code, 1, "{err}");
    let refusal: Value = serde_json::from_str(&out).unwrap();
    assert_eq!(refusal["code"], json!("NOT_FOUND"));
    assert!(refusal["remediation"].is_object(), "{refusal}");
    stop_server(&home);
}

/// A server that is shutting down can accept a forwarder and close the connection before it
/// answers the handshake. The forwarder connects again, here starting a new server, rather than
/// failing the agent's harness with a closed connection.
#[test]
fn a_forwarder_retries_when_a_closing_server_drops_the_handshake() {
    let dir = tempfile::tempdir().unwrap();
    let (home, project) = (dir.path().join("home"), dir.path().join("proj"));
    std::fs::create_dir_all(&home).unwrap();
    std::fs::create_dir_all(&project).unwrap();
    let socket = home.join("server.sock");
    let closing = std::os::unix::net::UnixListener::bind(&socket).unwrap();
    let dropped = std::thread::spawn(move || {
        let (stream, _) = closing.accept().unwrap();
        // As a closing server does: the socket goes, then the connection, unanswered.
        std::fs::remove_file(&socket).unwrap();
        drop(closing);
        let mut line = String::new();
        std::io::BufRead::read_line(&mut std::io::BufReader::new(&stream), &mut line).unwrap();
        assert!(line.contains("project"), "the forwarder sent its handshake: {line}");
    });
    let mut agent = Agent::start(&home, &project);
    let found = agent.request("server/discover", json!({}));
    dropped.join().unwrap();
    assert_eq!(found["result"]["_meta"]["io.modelcontextprotocol/serverInfo"]["name"], "metaform", "the agent reached a real server: {found}");
    agent.stop();
    stop_server(&home);
}

/// A server restart does not end an agent's session: the forwarder connects again (here starting a
/// new server) and the agent's next call works, on the same map.
#[test]
fn an_agent_session_survives_a_server_restart() {
    let dir = tempfile::tempdir().unwrap();
    let (home, project) = (dir.path().join("home"), dir.path().join("proj"));
    std::fs::create_dir_all(&project).unwrap();
    let mut agent = Agent::start(&home, &project);
    agent.request("server/discover", json!({}));
    assert!(!agent.call(json!({"update": {"code.part": {"name": "before"}}})).0);
    stop_server(&home);
    let (refused, read) = agent.call(json!({"code.part": {}}));
    assert!(!refused, "{read}");
    assert_eq!(read, json!({"code.part": {"name": "before"}}), "the same map, from a new server");
    agent.stop();
    stop_server(&home);
}

/// Settings through the CLI (R-4.8): `set` goes through the server, `settings` shows the value and
/// its source, and a bad value is refused with exit 1. It is a CLI command, not an agent tool.
#[test]
fn settings_are_set_and_shown_through_the_cli() {
    let dir = tempfile::tempdir().unwrap();
    let home = dir.path().join("home");
    let run = |args: &[&str]| {
        let out = Command::new(common::BIN).env("METAFORM_LAUNCHER", "").args(args).arg("--home").arg(&home).output().unwrap();
        (out.status.code().unwrap_or(-1), String::from_utf8_lossy(&out.stdout).to_string(), String::from_utf8_lossy(&out.stderr).to_string())
    };
    let (code, said, _) = run(&["set", "stores.max_open_databases", "5"]);
    assert_eq!(code, 0, "{said}");
    assert!(said.contains("at the next start"), "{said}");
    let (code, said, _) = run(&["settings"]);
    assert_eq!(code, 0);
    let shown: Value = serde_json::from_str(&said).unwrap();
    assert_eq!((shown[0]["value"].clone(), shown[0]["source"].clone()), (json!(5), json!("global")), "{shown}");
    let (code, _, why) = run(&["set", "stores.max_open_databases", "none"]);
    assert_eq!(code, 1);
    assert!(why.contains("whole number"), "{why}");
    stop_server(&home);
}


/// The specification export through the CLI (R-1.2): an agent writes the skeleton and a
/// specification block through the tool, and `metaform specification export` prints the document.
/// `--check` writes TASTE reports to stderr and still exits 0. A folder with no map is refused
/// with exit 2 and is not registered.
#[test]
fn the_specification_exports_as_markdown_through_the_cli() {
    let dir = tempfile::tempdir().unwrap();
    let (home, project) = (dir.path().join("home"), dir.path().join("lab"));
    std::fs::create_dir_all(&project).unwrap();
    let mut agent = Agent::start(&home, &project);
    agent.request("server/discover", json!({}));
    let (refused, said) = agent.call(json!({"add": {"code": {
        "technical_name": "code", "name": "Packet Lab", "role": "DE",
        "specification": [
            {"text": "Packet Lab records frames from the network card."},
            {"level": 1, "title": "Scope", "text": "It MUST record every frame."}
        ]
    }}}));
    assert!(!refused, "{said}");
    agent.stop();
    let run = |args: &[&str]| {
        let out = Command::new(common::BIN).env("METAFORM_LAUNCHER", "").args(args).arg("--home").arg(&home).output().unwrap();
        (out.status.code().unwrap_or(-1), String::from_utf8_lossy(&out.stdout).to_string(), String::from_utf8_lossy(&out.stderr).to_string())
    };
    let folder = project.to_str().unwrap();
    let (code, document, _) = run(&["specification", "export", "--project", folder]);
    assert_eq!(code, 0, "{document}");
    assert_eq!(
        document,
        "# lab\n\n## Packet Lab (`code`)\n\nRole: DE. Technical name: code.\n\nPacket Lab records frames from the network card.\n\n### Scope\n\nIt MUST record every frame.\n"
    );
    let (code, checked, reports) = run(&["specification", "export", "--check", "--project", folder]);
    assert_eq!((code, checked), (0, document), "--check leaves stdout as the document");
    assert!(reports.contains("code block 2 (\"Scope\"): CAPITAL_MODAL: uses \"MUST\""), "{reports}");
    assert!(reports.trim_end().ends_with("Reports are TASTE targets, not errors."), "{reports}");
    let other = dir.path().join("empty");
    std::fs::create_dir_all(&other).unwrap();
    let (code, _, why) = run(&["specification", "export", "--project", other.to_str().unwrap()]);
    assert_eq!(code, 2);
    assert!(why.contains("has no map yet"), "{why}");
    stop_server(&home);
}

/// The specification layer over MCP (R-6.25 to R-6.27): blocks written at a skeleton element come
/// back byte for byte after a server restart, and `goto` delivers the layer's instructions once per
/// context, not once per address.
#[test]
fn specification_blocks_survive_a_restart_and_instructions_arrive_once() {
    let dir = tempfile::tempdir().unwrap();
    let (home, project) = (dir.path().join("home"), dir.path().join("proj"));
    std::fs::create_dir_all(&project).unwrap();
    let mut agent = Agent::start(&home, &project);
    agent.request("server/discover", json!({}));
    // The store seeds this definition into main maps (Jorge's branch); until then the test writes
    // it, which the definition lock allows because it equals the code's definition.
    let seed = json!({"update": {metaform_core::specification::DEFINITION_ADDRESS:
        serde_json::Value::Object(metaform_core::specification::definition())}});
    let (refused, answer) = agent.call(seed);
    assert!(!refused, "{answer}");
    for (address, technical, name, role) in [
        ("code.engine", "engine", "main loop", "Definitive"),
        ("code.render", "render", "painter", "Supportive"),
    ] {
        let fields = json!({"technical_name": technical, "name": name, "role": role});
        let (refused, answer) = agent.call(json!({"update": {address: fields}}));
        assert!(!refused, "{answer}");
    }
    let blocks = json!([
        {"text": "The `main loop` paces every frame — naïve timing is avoided ✓."},
        {"level": 1, "title": "Timing \"budget\"", "text": "Line one.\nLine two with a 'quote' and \\ backslash.\n\n```sh\n# not a heading\n```"},
        {"level": 2, "title": "Limits", "text": ""}
    ]);
    let (refused, answer) = agent.call(json!({"update": {"code.engine": {"specification": blocks.clone()}}}));
    assert!(!refused, "{answer}");

    let (_, first) = agent.call(json!({"goto": "code.engine"}));
    assert!(first["instructions"]["specification"].as_str().unwrap().contains("TASTE"));
    assert_eq!(first["layers"]["specification"], json!({"records": 3}));
    let (_, second) = agent.call(json!({"goto": "code.render"}));
    assert_eq!(second["layers"]["specification"], json!({"records": 0}));
    assert!(second.get("instructions").is_none(), "instructions arrive once per context: {second}");

    stop_server(&home);
    let (refused, read) = agent.call(json!({"code.engine": {"layers": ["specification"]}}));
    assert!(!refused, "{read}");
    assert_eq!(read["code.engine"]["specification"], blocks, "the blocks survive a restart unchanged");
    agent.stop();
    stop_server(&home);
}
