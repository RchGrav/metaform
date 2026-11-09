//! Real capture against a short-lived harness. Needs root and an eBPF-capable kernel, so these
//! are ignored by default; run them in a throwaway sandbox:
//!
//! ```text
//! cargo test -p agent-monitor --test live_capture -- --ignored --nocapture
//! ```
//!
//! Each launches a stand-in harness that waits for one line on stdin, attaches the monitor,
//! releases it, and reads the bus until every expected observation has arrived. The harness
//! writes a file, runs a subprocess, connects out, makes an HTTPS POST to a model provider
//! (answered 401: no credentials are sent) and exits with code 3.
#![cfg(feature = "agentsight")]

use std::process::Stdio;

use agent_monitor::{Activity, Capture, Harness, Monitor, MonitorAttached, MonitorUnavailable, Observation};
use bus::Bus;
use tokio::io::AsyncWriteExt;
use tokio::process::Command;

const PYTHON: &str = r#"
import os, subprocess, sys, urllib.request
sys.stdin.readline()
open("/tmp/agent-monitor-live.txt", "w").write("hi")
os.remove("/tmp/agent-monitor-live.txt")
subprocess.run(["sh", "-c", "ls / > /dev/null"])
try:
    urllib.request.urlopen(urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=b'{"model":"openai/gpt-4o-mini","messages":[]}',
        headers={"Content-Type": "application/json"})).read()
except urllib.error.HTTPError as error:
    error.read()  # read the whole response, so the parser sees it complete
    print("https:", error)
sys.exit(3)
"#;

const NODE: &str = r#"
process.stdin.once("data", () => {
  require("fs").writeFileSync("/tmp/agent-monitor-live.txt", "hi");
  require("fs").unlinkSync("/tmp/agent-monitor-live.txt");
  require("child_process").execSync("ls / > /dev/null");
  const request = require("https").request("https://openrouter.ai/api/v1/chat/completions",
    { method: "POST", headers: { "content-type": "application/json" } },
    (response) => { response.resume(); response.on("end", () => process.exit(3)); });
  request.on("error", (error) => { console.error(error); process.exit(4); });
  request.end('{"model":"openai/gpt-4o-mini","messages":[]}');
});
"#;

#[tokio::test]
#[ignore = "needs root and eBPF; run in a sandbox"]
async fn python_harness() {
    observe_harness("python3", &["-c", PYTHON]).await;
}

#[tokio::test]
#[ignore = "needs root, eBPF and node; run in a sandbox"]
async fn node_harness() {
    observe_harness("node", &["-e", NODE]).await;
}

async fn observe_harness(program: &str, args: &[&str]) {
    let bus = Bus::new();
    let mut tap = bus.tap();
    let mut child = Command::new(program).args(args).stdin(Stdio::piped()).spawn().expect("spawn harness");
    let pid = child.id().expect("harness pid");
    let harness = Harness::new(pid, Some(format!("live-{program}")));

    let monitor = Monitor::attach(&bus, harness.clone()).await.unwrap_or_else(|error| panic!("{error}"));
    child.stdin.take().unwrap().write_all(b"go\n").await.unwrap();

    let (mut attached_process, mut attached_tls) = (false, false);
    let (mut spawn, mut file, mut connect, mut request, mut response, mut exit) =
        (false, false, false, false, false, false);
    while !(attached_process && attached_tls && spawn && file && connect && request && response && exit) {
        let envelope = tap.recv().await.expect("bus open");
        println!("{} {}", envelope.name, envelope.to_json().unwrap());
        if let Some(event) = envelope.downcast::<MonitorAttached>() {
            assert_eq!(event.harness, harness);
            attached_process |= event.capture == Capture::Process;
            attached_tls |= event.capture == Capture::Tls;
        }
        if let Some(event) = envelope.downcast::<MonitorUnavailable>() {
            panic!("{event}");
        }
        let Some(event) = envelope.downcast::<Observation>() else { continue };
        assert_eq!(event.harness, harness);
        match &event.activity {
            Activity::ProcessSpawn { command: Some(command), .. } if command.contains("ls /") => spawn = true,
            Activity::FileOpen { path, write: true, .. } if path == "/tmp/agent-monitor-live.txt" => file = true,
            // An outbound connection to an address (the probe reports port 0 for Node's
            // non-blocking connects, so the port is not checked).
            Activity::Network { op, target, .. } if op == "NET_CONNECT" && !target.starts_with("family=") && !target.starts_with("127.") => connect = true,
            Activity::HttpRequest { host: Some(host), .. } if host == "openrouter.ai" => request = true,
            Activity::HttpResponse { status: Some(401), .. } => response = true,
            Activity::ProcessExit { exit_code, .. } if event.pid == Some(pid) => {
                assert_eq!(*exit_code, Some(3));
                exit = true;
            }
            _ => {}
        }
    }
    assert_eq!(child.wait().await.unwrap().code(), Some(3));
    drop(monitor);
}
