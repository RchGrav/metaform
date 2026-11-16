//! Shared helpers for the `metaform` binary's tests: a forwarder child speaking MCP over stdio,
//! the CLI, and stopping a home's server. Kept apart so `server.rs` stays under 500 lines.

#![allow(dead_code)]

use std::collections::VecDeque;
use std::io::{BufRead, BufReader, Write};
use std::path::Path;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::mpsc;
use std::time::Duration;

use serde_json::{Value, json};

pub const BIN: &str = env!("CARGO_BIN_EXE_metaform");

pub fn meta() -> Value {
    json!({
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientInfo": {"name": "test", "version": "0"},
        "io.modelcontextprotocol/clientCapabilities": {}
    })
}

/// One agent harness: a forwarder child speaking MCP 2026-07-28 over its stdio.
pub struct Agent {
    pub child: Child,
    pub stdin: ChildStdin,
    /// Lines from the forwarder's output, read on their own thread so a test can wait for a
    /// notification with a time limit.
    pub lines: mpsc::Receiver<Value>,
    /// Messages that arrived while waiting for a reply: notifications, in order.
    pub notices: VecDeque<Value>,
    pub next: u64,
}

impl Agent {
    pub fn start(home: &Path, project: &Path) -> Agent {
        Agent::spawn(home, &["--project".as_ref(), project.as_os_str()])
    }

    /// A forwarder on a map that belongs to no project (R-4.15).
    pub fn on_map(home: &Path, name: &str) -> Agent {
        Agent::spawn(home, &["--map".as_ref(), name.as_ref()])
    }

    pub fn spawn(home: &Path, target: &[&std::ffi::OsStr]) -> Agent {
        Agent::spawn_with_launcher(home, target, "".as_ref())
    }

    pub fn spawn_with_launcher(
        home: &Path,
        target: &[&std::ffi::OsStr],
        launcher: &std::ffi::OsStr,
    ) -> Agent {
        let mut child = Command::new(BIN)
            .env("METAFORM_LAUNCHER", launcher)
            .args(["mcp", "--home"])
            .arg(home)
            .args(target)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .unwrap();
        let stdin = child.stdin.take().unwrap();
        let stdout = BufReader::new(child.stdout.take().unwrap());
        let (send, lines) = mpsc::channel();
        std::thread::spawn(move || {
            for line in stdout.lines().map_while(Result::ok) {
                if send.send(serde_json::from_str(&line).unwrap()).is_err() {
                    break;
                }
            }
        });
        Agent {
            child,
            stdin,
            lines,
            notices: VecDeque::new(),
            next: 1,
        }
    }

    /// Send a request without waiting for its reply; returns its id.
    pub fn send(&mut self, method: &str, mut params: Value) -> u64 {
        params["_meta"] = meta();
        let id = self.next;
        self.next += 1;
        let message = json!({"jsonrpc": "2.0", "id": id, "method": method, "params": params});
        writeln!(self.stdin, "{message}").unwrap();
        id
    }

    pub fn request(&mut self, method: &str, params: Value) -> Value {
        let id = self.send(method, params);
        loop {
            let message = self
                .lines
                .recv_timeout(Duration::from_secs(10))
                .unwrap_or_else(|_| panic!("no reply to {method}"));
            if message["id"] == json!(id) && message.get("method").is_none() {
                return message;
            }
            self.notices.push_back(message);
        }
    }

    /// The next notification with this method, waiting up to `limit`; None if none comes.
    pub fn notice(&mut self, method: &str, limit: Duration) -> Option<Value> {
        if let Some(at) = self
            .notices
            .iter()
            .position(|m| m["method"] == json!(method))
        {
            return self.notices.remove(at);
        }
        let deadline = std::time::Instant::now() + limit;
        while let Some(left) = deadline.checked_duration_since(std::time::Instant::now()) {
            match self.lines.recv_timeout(left) {
                Ok(m) if m["method"] == json!(method) => return Some(m),
                Ok(m) => self.notices.push_back(m),
                Err(_) => return None,
            }
        }
        None
    }

    /// Open `subscriptions/listen` on this connection's map resource; returns its URI.
    pub fn listen_to_map(&mut self) -> String {
        let listed = self.request("resources/list", json!({}));
        let uri = listed["result"]["resources"][0]["uri"]
            .as_str()
            .unwrap()
            .to_string();
        self.send(
            "subscriptions/listen",
            json!({"notifications": {"resourceSubscriptions": [&uri]}}),
        );
        uri
    }

    /// Call the one tool; returns (is_error, the JSON text it returned). A JSON-RPC error, such as
    /// the forwarder's answer to a request that was in flight when the server restarted, is an
    /// error, returned as its error object.
    pub fn call(&mut self, arguments: Value) -> (bool, Value) {
        let reply = self.request(
            "tools/call",
            json!({"name": "project-map", "arguments": arguments}),
        );
        if let Some(error) = reply.get("error") {
            return (true, error.clone());
        }
        let result = &reply["result"];
        let text = result["content"][0]["text"].as_str().unwrap_or_default();
        (
            result["isError"] == json!(true),
            serde_json::from_str(text).unwrap_or(json!(text)),
        )
    }

    /// A read sent just after the server was stopped. If the forwarder had already passed it to the
    /// old server, it answers with the restart error (`relay.rs`), which tells the agent to read
    /// again. A read is safe to send again, so this sends it once more, as an agent would.
    pub fn read_after_restart(&mut self, arguments: Value) -> (bool, Value) {
        let first = self.call(arguments.clone());
        let restarted = first.0
            && first.1["message"]
                .as_str()
                .is_some_and(|m| m.contains("restarted before answering"));
        if restarted { self.call(arguments) } else { first }
    }

    pub fn stop(mut self) -> String {
        drop(self.stdin);
        let _ = self.child.wait();
        let mut err = String::new();
        let _ = std::io::Read::read_to_string(&mut self.child.stderr.take().unwrap(), &mut err);
        err
    }
}

pub fn stop_server(home: &Path) {
    let _ = Command::new("pkill")
        .arg("-TERM")
        .arg("-f")
        .arg(format!("metaform serve --home {}", home.display()))
        .status();
    for _ in 0..50 {
        if !home.join("server.sock").exists() {
            return;
        }
        std::thread::sleep(std::time::Duration::from_millis(50));
    }
}

/// Run `metaform call` once, with the launcher off; returns (exit code, stdout, stderr).
pub fn cli(home: &Path, args: &[&str], stdin: Option<&str>) -> (i32, String, String) {
    let mut child = Command::new(BIN)
        .env("METAFORM_LAUNCHER", "")
        .arg("call")
        .arg("--home")
        .arg(home)
        .args(args)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    let mut input = child.stdin.take().unwrap();
    if let Some(text) = stdin {
        input.write_all(text.as_bytes()).unwrap();
    }
    drop(input);
    let out = child.wait_with_output().unwrap();
    let text = |b: &[u8]| String::from_utf8_lossy(b).trim().to_string();
    (
        out.status.code().unwrap_or(-1),
        text(&out.stdout),
        text(&out.stderr),
    )
}
