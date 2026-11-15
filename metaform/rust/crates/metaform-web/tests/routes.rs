//! The host's routes, against a real server on a new home.
//!
//! The test builds the `metaform` binary, because the host starts the home's server from it, and
//! cargo does not build another package's binary for a test. Run it with `METAFORM_LAUNCHER=`
//! (empty), so the server is started directly and not through a service launcher.
//!
//! The home is a new folder in the system's temporary folder, because a home's socket path must
//! be short. The test ends the server it started, by its process ID, and removes the folder.

use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::Arc;

use metaform_server::Target;
use metaform_server::call::{Answer, call};
use metaform_web::{Config, router};
use serde_json::{Value, json};

/// Builds the `metaform` binary into the folder this test was built into, and returns its path.
fn server_exe() -> PathBuf {
    // target/<profile>/deps/routes-<hash> -> target/<profile>
    let profile = std::env::current_exe().unwrap().parent().unwrap().parent().unwrap().to_path_buf();
    let cargo = std::env::var_os("CARGO").unwrap_or_else(|| "cargo".into());
    let mut build = Command::new(cargo);
    build.args(["build", "-p", "metaform-server", "--bin", "metaform", "--target-dir"]);
    build.arg(profile.parent().unwrap()).current_dir(env!("CARGO_MANIFEST_DIR"));
    if profile.file_name().is_some_and(|name| name == "release") {
        build.arg("--release");
    }
    assert!(build.status().unwrap().success(), "cargo could not build the metaform binary");
    profile.join("metaform")
}

/// The process IDs of the servers started with exactly `serve --home <home>` (Linux: `/proc`).
fn server_pids(home: &Path) -> Vec<u32> {
    let wanted: Vec<&[u8]> = vec![b"serve", b"--home", home.as_os_str().as_encoded_bytes()];
    let Ok(processes) = std::fs::read_dir("/proc") else { return Vec::new() };
    processes
        .filter_map(|entry| entry.ok()?.file_name().to_str()?.parse::<u32>().ok())
        .filter(|pid| {
            let line = std::fs::read(format!("/proc/{pid}/cmdline")).unwrap_or_default();
            let arguments: Vec<&[u8]> = line.split(|byte| *byte == 0).filter(|a| !a.is_empty()).collect();
            arguments.len() == 4 && arguments[1..] == wanted[..]
        })
        .collect()
}

/// Ends the home's server by its process ID and waits until its socket is gone.
fn end_server(home: &Path) {
    for pid in server_pids(home) {
        let _ = Command::new("kill").args(["-TERM", &pid.to_string()]).status();
    }
    for _ in 0..100 {
        if !home.join("server.sock").exists() {
            return;
        }
        std::thread::sleep(std::time::Duration::from_millis(50));
    }
}

/// Ends the server and removes the test's folder, also when an assertion fails.
struct Cleanup {
    dir: PathBuf,
    home: PathBuf,
}

impl Drop for Cleanup {
    fn drop(&mut self) {
        end_server(&self.home);
        let _ = std::fs::remove_dir_all(&self.dir);
    }
}

/// One HTTP request to the host; returns the status and the body. `Host` is `host`.
async fn request(addr: SocketAddr, method: &str, path: &str, host: String, origin: Option<String>, body: Option<Value>) -> (u16, String) {
    let method = method.to_string();
    let path = path.to_string();
    tokio::task::spawn_blocking(move || {
        let mut message = format!("{method} {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n");
        if let Some(origin) = origin {
            message += &format!("Origin: {origin}\r\n");
        }
        let body = body.map(|b| b.to_string()).unwrap_or_default();
        if !body.is_empty() {
            message += &format!("Content-Type: application/json\r\nContent-Length: {}\r\n", body.len());
        }
        let mut stream = TcpStream::connect(addr).unwrap();
        stream.write_all(format!("{message}\r\n{body}").as_bytes()).unwrap();
        let mut answer = String::new();
        stream.read_to_string(&mut answer).unwrap();
        let status = answer.split(' ').nth(1).and_then(|code| code.parse().ok()).unwrap();
        let text = answer.split_once("\r\n\r\n").map(|(_, text)| text.to_string()).unwrap_or_default();
        (status, text)
    })
    .await
    .unwrap()
}

/// Serves the home on a free port and returns the address.
async fn start_host(config: Config) -> SocketAddr {
    let listener = tokio::net::TcpListener::bind(("127.0.0.1", 0)).await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move { axum::serve(listener, router(Arc::new(config), addr)).await });
    addr
}

fn parsed(text: &str) -> Value {
    serde_json::from_str(text).unwrap_or_else(|_| panic!("not JSON: {text}"))
}

#[tokio::test(flavor = "multi_thread")]
async fn the_write_route_forwards_a_write_only_from_the_hosts_own_page() {
    let exe = server_exe();
    let dir = std::env::temp_dir().join(format!("mfw-{}", std::process::id()));
    let (home, folder) = (dir.join("home"), dir.join("proj"));
    std::fs::create_dir_all(&folder).unwrap();
    let _cleanup = Cleanup { dir: dir.clone(), home: home.clone() };

    // A project is registered when a client first connects from its folder.
    let first = call(&home, &Target::Project(folder.clone()), &exe, json!({"map": {}})).await;
    assert!(matches!(first, Ok(Answer::Ok(_))), "the server did not answer the first read");

    let config = Config { home: home.clone(), server_exe: exe.clone(), assets: dir.join("no-assets"), read_only: false };
    let addr = start_host(config.clone()).await;
    let host = addr.to_string();
    let own = Some(format!("http://{host}"));

    let (status, text) = request(addr, "GET", "/api/host", host.clone(), None, None).await;
    assert_eq!((status, parsed(&text)), (200, json!({"writes": true})));
    let (status, text) = request(addr, "GET", "/api/projects", host.clone(), None, None).await;
    assert_eq!(status, 200, "{text}");
    let id = parsed(&text)[0]["id"].as_str().unwrap().to_string();
    let (call_path, write_path) = (format!("/api/projects/{id}/call"), format!("/api/projects/{id}/write"));
    let add = json!({"add": {"code.x": {"technical_name": "x code", "name": "Example", "role": "Supporting Element"}}});

    // With the host's own Origin the write is forwarded, and the element is in the map.
    let (status, text) = request(addr, "POST", &write_path, host.clone(), own.clone(), Some(add.clone())).await;
    assert_eq!((status, parsed(&text)), (200, json!({"status": "ok"})));
    let (status, text) = request(addr, "POST", &call_path, host.clone(), None, Some(json!({"goto": "code.x"}))).await;
    assert_eq!(status, 200, "{text}");
    assert_eq!(parsed(&text)["element"]["name"], json!("Example"));

    // A refusal by the tool comes back unchanged, with HTTP 200.
    let bad = json!({"update": {"code.x": {"role": "Helper"}}});
    let (status, text) = request(addr, "POST", &write_path, host.clone(), own.clone(), Some(bad)).await;
    let refusal = parsed(&text);
    assert_eq!(status, 200, "{text}");
    assert_eq!(refusal["status"], json!("error"), "{text}");
    assert!(refusal["code"].is_string() && refusal["message"].is_string() && refusal.get("remediation").is_some(), "{text}");

    // Without an Origin, and with another one, the write is refused and nothing is stored.
    let other = json!({"add": {"code.y": {"technical_name": "y code", "name": "Other", "role": "Supporting Element"}}});
    let (status, text) = request(addr, "POST", &write_path, host.clone(), None, Some(other.clone())).await;
    assert_eq!(status, 403, "{text}");
    assert!(parsed(&text)["error"].as_str().unwrap().contains("needs an Origin"), "{text}");
    let foreign = Some("http://example.invalid".to_string());
    let (status, text) = request(addr, "POST", &write_path, host.clone(), foreign, Some(other.clone())).await;
    assert_eq!((status, text.as_str()), (403, "unexpected Origin"));
    // `localhost` is this server, but it is not the Host the request named.
    let localhost = Some(format!("http://localhost:{}", addr.port()));
    let (status, text) = request(addr, "POST", &write_path, host.clone(), localhost.clone(), Some(other.clone())).await;
    assert_eq!(status, 403, "{text}");
    assert!(parsed(&text)["error"].as_str().unwrap().contains("own page"), "{text}");
    // The same Origin is accepted when the request names the same Host. The body is a read, so
    // the route refuses it with 400 and stores nothing.
    let by_name = format!("localhost:{}", addr.port());
    let (status, text) = request(addr, "POST", &write_path, by_name, localhost, Some(json!({"map": {}}))).await;
    assert_eq!(status, 400, "{text}");

    // /call still refuses a write, also with the host's own Origin.
    let (status, text) = request(addr, "POST", &call_path, host.clone(), own.clone(), Some(other.clone())).await;
    assert_eq!(status, 403, "{text}");

    // A read-only host refuses the write and says that it does not write.
    let read_only = start_host(Config { read_only: true, ..config }).await;
    let host = read_only.to_string();
    let (status, text) = request(read_only, "GET", "/api/host", host.clone(), None, None).await;
    assert_eq!((status, parsed(&text)), (200, json!({"writes": false})));
    let own = Some(format!("http://{host}"));
    let (status, text) = request(read_only, "POST", &write_path, host.clone(), own, Some(other)).await;
    assert_eq!(status, 403, "{text}");
    assert!(parsed(&text)["error"].as_str().unwrap().contains("read-only"), "{text}");

    // None of the refused writes reached the map.
    let (_, text) = request(read_only, "POST", &call_path, host, None, Some(json!({"map": {}}))).await;
    let addresses = parsed(&text)["addresses"].clone();
    assert!(addresses.as_array().unwrap().contains(&json!("code.x")), "{text}");
    assert!(!addresses.as_array().unwrap().contains(&json!("code.y")), "{text}");
}
