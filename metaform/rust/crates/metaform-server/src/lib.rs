//! The functional map server and its forwarder (R-4.4, R-4.5).
//!
//! - `serve`: one long-running process per home. It owns the store (`metaform-store`) and
//!   listens on `<home>/server.sock`. Each connection is one agent's MCP session.
//! - `forward`: what each agent's harness starts over stdio. It connects to the server,
//!   starting it first if no server is running, names its project folder in one handshake
//!   line, and then relays messages both ways, connecting again if the server restarts
//!   ([`relay`]). It never opens a database or writes a file.
//!
//! The handshake is one JSON line before MCP starts: `{"project": "<absolute folder>"}` for a
//! project's main map, or `{"map": "<name>"}` for a map that belongs to no project (R-4.15).

pub mod admin;
pub mod announce;
pub mod call;
pub mod relay;
pub mod start;
pub mod tool;

use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Duration;

use metaform_store::{ClientId, MapKey, Store};
use rmcp::ServiceExt;
use serde_json::{Value, json};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::net::{UnixListener, UnixStream};

/// The exit status of `metaform serve` when another server already owns the home. A forwarder
/// that started that server then connects to the owner instead.
pub const HOME_OWNED: i32 = 3;

/// The socket a home's server listens on.
pub fn socket_path(home: &Path) -> PathBuf {
    home.join("server.sock")
}

/// The home: `METAFORM_HOME` if set, otherwise `~/.metaform` (R-4.1).
pub fn default_home() -> PathBuf {
    std::env::var_os("METAFORM_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            PathBuf::from(std::env::var_os("HOME").unwrap_or_default()).join(".metaform")
        })
}

/// Run the server for `home` until the process is ended. Fails at once if another server
/// owns the home, or if the home holds data this store did not write.
pub async fn serve(home: &Path) -> Result<(), String> {
    let store = open_store(home).await?;
    let store = Arc::new(store);
    let socket = socket_path(home);
    // The store's lock proves this process owns the home, so a socket file left here is stale.
    let _ = std::fs::remove_file(&socket);
    let listener = UnixListener::bind(&socket).map_err(|e| format!("{}: {e}", socket.display()))?;
    restrict(&socket);
    let next = Arc::new(AtomicU64::new(1));
    let mut terminate = tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
        .map_err(|e| e.to_string())?;
    let mut sessions = tokio::task::JoinSet::new();
    loop {
        tokio::select! {
            accepted = listener.accept() => {
                let Ok((stream, _)) = accepted else { continue };
                let client = ClientId(next.fetch_add(1, Ordering::Relaxed));
                sessions.spawn(session(Arc::clone(&store), stream, client));
            }
            Some(_) = sessions.join_next(), if !sessions.is_empty() => {}
            _ = tokio::signal::ctrl_c() => break,
            _ = terminate.recv() => break,
        }
    }
    drop(listener);
    let _ = std::fs::remove_file(&socket);
    // End every session now. A session holds the store, and rmcp can keep a closing session for
    // up to 5 s; waiting for it would hold the home's lock that long after the socket is gone,
    // and a new server would be refused. Then close the store off the async runtime: its writers
    // finish, and its lock is released last.
    sessions.abort_all();
    while sessions.join_next().await.is_some() {}
    tokio::task::spawn_blocking(move || drop(store))
        .await
        .map_err(|e| e.to_string())
}

/// How long a starting server waits for the home's lock. A server that is shutting down removes
/// its socket first and releases the lock a moment later; a forwarder that arrives in between
/// starts a new server, which must wait for that lock rather than give up.
const LOCK_WAIT: Duration = Duration::from_secs(3);

/// Open the home's store, waiting up to `LOCK_WAIT` while another server still holds its lock.
/// If the lock is still held after that, a live server owns the home: give up (`HOME_OWNED`).
async fn open_store(home: &Path) -> Result<Store, String> {
    let deadline = tokio::time::Instant::now() + LOCK_WAIT;
    loop {
        let path = home.to_path_buf();
        let opened = tokio::task::spawn_blocking(move || Store::open(&path))
            .await
            .map_err(|e| e.to_string())?;
        match opened {
            Err(metaform_store::StoreError::Owned(_)) if tokio::time::Instant::now() < deadline => {
                tokio::time::sleep(Duration::from_millis(100)).await;
            }
            other => return other.map_err(|e| e.to_string()),
        }
    }
}

/// Only the owner may connect (the socket inherits nothing wider).
fn restrict(socket: &Path) {
    use std::os::unix::fs::PermissionsExt;
    let _ = std::fs::set_permissions(socket, std::fs::Permissions::from_mode(0o600));
}

async fn session(store: Arc<Store>, stream: UnixStream, client: ClientId) {
    let (read, mut write) = stream.into_split();
    let mut reader = BufReader::new(read);
    let mut line = String::new();
    if reader.read_line(&mut line).await.is_err() {
        return;
    }
    // The CLI's admin request (settings) is answered in one line, and the connection ends.
    if let Ok(request) = serde_json::from_str::<Value>(&line)
        && let Some(body) = request.get("admin")
    {
        let answer = admin::answer(&store, body).await;
        let _ = write.write_all(format!("{answer}\n").as_bytes()).await;
        return;
    }
    let map = match handshake(&store, &line).await {
        Ok(map) => {
            let _ = write.write_all(b"{\"ok\":true}\n").await;
            map
        }
        Err(reason) => {
            let _ = write
                .write_all(format!("{}\n", json!({"ok": false, "error": reason})).as_bytes())
                .await;
            return;
        }
    };
    let handler = tool::MapTool::new(store, map, client);
    if let Ok(running) = handler.serve((reader, write)).await {
        let _ = running.waiting().await;
    }
}

async fn handshake(store: &Arc<Store>, line: &str) -> Result<MapKey, String> {
    let request: Value = serde_json::from_str(line).map_err(|e| format!("the handshake is not valid JSON: {e}"))?;
    match (request["project"].as_str(), request["map"].as_str()) {
        (Some(folder), None) => open_project(store, folder.to_string()).await,
        (None, Some(name)) => {
            check_map_name(name)?;
            Ok(MapKey::standalone(name))
        }
        _ => Err("the handshake must name exactly one of: a project folder or a map".into()),
    }
}

async fn open_project(store: &Arc<Store>, folder: String) -> Result<MapKey, String> {
    let store = Arc::clone(store);
    tokio::task::spawn_blocking(move || {
        let folder = PathBuf::from(folder);
        let name = folder
            .file_name()
            .map(|n| n.to_string_lossy().to_string())
            .unwrap_or_default();
        store
            .register_project(&folder, &name)
            .map(|id| MapKey::main(&id))
            .map_err(|e| e.to_string())
    })
    .await
    .map_err(|e| e.to_string())?
}

/// A map that belongs to no project is named by one address segment: 1 to 64 characters of
/// lowercase letters, digits and underscores. The map is created on first write.
///
/// Who may open whose private map waits for agent identity (R-8.2). Until then, anyone who can
/// reach the home's socket can open any map in it, the same as a project.
fn check_map_name(name: &str) -> Result<(), String> {
    let ok = (1..=64).contains(&name.len())
        && name
            .bytes()
            .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'_');
    if ok {
        Ok(())
    } else {
        Err(format!(
            "map name {name:?} is not one address segment: use 1 to 64 lowercase letters, digits or underscores"
        ))
    }
}

/// How long a forwarder keeps trying when a server closes the connection before answering the
/// handshake, as one that is shutting down can.
const HANDSHAKE_WAIT: Duration = Duration::from_secs(5);

/// What a forwarder opens: a project's main map, or a map that belongs to no project.
pub enum Target {
    Project(PathBuf),
    Map(String),
}

/// Connect to the home's server, starting it if none answers, and complete the handshake for
/// `target`. Returns the stream, ready for MCP.
pub(crate) async fn open_session(
    home: &Path,
    target: &Target,
    server_exe: &Path,
) -> Result<
    (
        BufReader<tokio::net::unix::OwnedReadHalf>,
        tokio::net::unix::OwnedWriteHalf,
    ),
    String,
> {
    let hello = match target {
        Target::Project(folder) => {
            let folder =
                std::fs::canonicalize(folder).map_err(|e| format!("{}: {e}", folder.display()))?;
            json!({"project": folder.to_string_lossy()})
        }
        Target::Map(name) => json!({"map": name}),
    };
    // A server that is shutting down can accept a connection and close it before it answers the
    // handshake: its socket goes first, but a forwarder can connect in between. That is not a
    // refusal, so connect (or start a server) again until HANDSHAKE_WAIT has passed.
    let deadline = tokio::time::Instant::now() + HANDSHAKE_WAIT;
    let (reader, write, answer) = loop {
        let stream = connect_or_start(home, server_exe).await?;
        let (read, mut write) = stream.into_split();
        let mut reader = BufReader::new(read);
        let mut answer = String::new();
        let sent = write.write_all(format!("{hello}\n").as_bytes()).await;
        let read = match sent {
            Ok(()) => reader.read_line(&mut answer).await,
            Err(e) => Err(e),
        };
        match read {
            Ok(n) if n > 0 => break (reader, write, answer),
            _ if tokio::time::Instant::now() < deadline => tokio::time::sleep(Duration::from_millis(100)).await,
            Ok(_) => return Err("the server closed the connection before answering the handshake".into()),
            Err(e) => return Err(e.to_string()),
        }
    };
    let answer: Value =
        serde_json::from_str(&answer).map_err(|_| format!("the server's handshake answer is not JSON: {answer:?}"))?;
    if answer["ok"] != json!(true) {
        return Err(answer["error"]
            .as_str()
            .unwrap_or("server refused the connection")
            .to_string());
    }
    Ok((reader, write))
}

pub use relay::forward;

pub(crate) async fn connect_or_start(home: &Path, server_exe: &Path) -> Result<UnixStream, String> {
    let socket = socket_path(home);
    if let Ok(stream) = UnixStream::connect(&socket).await {
        return Ok(stream);
    }
    std::fs::create_dir_all(home).map_err(|e| e.to_string())?;
    let mut started = start::start(home, server_exe)?;
    // The end of the shared log: enough to show why a direct start failed.
    let log = || {
        let text = std::fs::read_to_string(home.join("server.log")).unwrap_or_default();
        let lines: Vec<&str> = text.lines().collect();
        lines[lines.len().saturating_sub(5)..].join("\n")
    };
    for _ in 0..100 {
        tokio::time::sleep(Duration::from_millis(50)).await;
        if let Ok(stream) = UnixStream::connect(&socket).await {
            return Ok(stream);
        }
        if let start::Started::Direct(server) = &mut started
            && let Ok(Some(status)) = server.try_wait()
        {
            // Our server ended. If it lost the race for the home to another forwarder's server
            // (exit status HOME_OWNED), that server may still be starting: keep trying to connect
            // until the deadline. Any other reason, such as a foreign home, is final.
            if status.code() != Some(HOME_OWNED) {
                return Err(log());
            }
        }
    }
    Err(match started {
        start::Started::Launcher(name) => format!(
            "the server did not start within 5 s. It runs as the launcher call {name}: see `hold logs {name}`"
        ),
        start::Started::Direct(_) => format!(
            "the server did not start within 5 s. Its log: {}",
            log().trim()
        ),
    })
}
