//! The forwarder's relay: stdio to the home's server and back, across a server restart.
//!
//! MCP over stdio is one JSON-RPC message per line. The relay passes each line through, and reads
//! just enough of it to bridge a restart: when the server closes the connection while the agent's
//! harness is still running, the relay connects again (starting a server if none answers) and
//! replays what the new server needs to serve the same session:
//!
//! - the client's `initialize` request and `notifications/initialized`, for clients older than
//!   2026-07-28, which hold a session (the answer to the replayed `initialize` is dropped: the
//!   client already has one);
//! - each open subscription: `subscriptions/listen` (its answer is left to reach the client when the
//!   listen ends, as it would have) and `resources/subscribe` (its answer is dropped).
//!
//! Requests sent before the restart that had no answer get an error, so the client is never left
//! waiting: a write in flight may or may not have committed, and the error says to read the map
//! before sending it again. `goto` always returns the whole sheet, so a restart loses nothing.
//! Without the relay, a server restart ended every agent's MCP session.

use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

use serde_json::{Value, json};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::net::unix::{OwnedReadHalf, OwnedWriteHalf};

use crate::Target;

/// What the relay replays to a new server, and what it is waiting for.
#[derive(Default)]
struct Session {
    initialize: Option<String>,
    initialized: Option<String>,
    /// Open subscriptions, by request id: the line, and whether its answer reaches the client.
    subscriptions: BTreeMap<String, (String, bool)>,
    /// Requests sent and not yet answered, by id.
    pending: BTreeMap<String, Value>,
    /// Answers to replayed requests that the client already has, by id.
    drop_answers: BTreeSet<String>,
}

impl Session {
    /// Note a line from the client before it goes to the server.
    fn note_client_line(&mut self, line: &str) {
        let Ok(message) = serde_json::from_str::<Value>(line) else { return };
        let method = message["method"].as_str().unwrap_or_default();
        let id = message.get("id").filter(|id| !id.is_null());
        match method {
            "initialize" => self.initialize = Some(line.to_string()),
            "notifications/initialized" => self.initialized = Some(line.to_string()),
            "subscriptions/listen" | "resources/subscribe" => {
                if let Some(id) = id {
                    self.subscriptions.insert(id.to_string(), (line.to_string(), method == "subscriptions/listen"));
                }
            }
            "resources/unsubscribe" => self.subscriptions.retain(|_, (_, listen)| *listen),
            "notifications/cancelled" => {
                if let Some(cancelled) = message["params"].get("requestId") {
                    self.subscriptions.remove(&cancelled.to_string());
                }
            }
            _ => {}
        }
        if let (Some(id), false) = (id, method.is_empty()) {
            self.pending.insert(id.to_string(), id.clone());
        }
    }

    /// True if a line from the server goes on to the client.
    fn passes_server_line(&mut self, line: &str) -> bool {
        let Ok(message) = serde_json::from_str::<Value>(line) else { return true };
        let is_answer = message.get("method").is_none();
        let Some(id) = message.get("id").filter(|id| !id.is_null()).map(Value::to_string) else { return true };
        if !is_answer {
            return true;
        }
        self.pending.remove(&id);
        if self.subscriptions.get(&id).is_some_and(|(_, listen)| *listen) {
            // A listen's answer means it ended.
            self.subscriptions.remove(&id);
        }
        !self.drop_answers.remove(&id)
    }

    /// After a restart: the error answers owed to the client, and the lines to replay.
    fn restart(&mut self) -> (Vec<String>, Vec<String>) {
        let owed = std::mem::take(&mut self.pending)
            .into_iter()
            .filter(|(id, _)| !self.subscriptions.contains_key(id) && !self.is_initialize(id))
            .map(|(_, id)| {
                json!({"jsonrpc": "2.0", "id": id, "error": {"code": -32603, "message":
                    "the Metaform server restarted before answering; if this was a change, read the map before sending it again"}})
                .to_string()
            })
            .collect();
        let mut replay = Vec::new();
        if let Some(line) = &self.initialize {
            replay.push(line.clone());
            if let Some(id) = id_of(line) {
                self.drop_answers.insert(id);
            }
        }
        replay.extend(self.initialized.clone());
        for (id, (line, listen)) in &self.subscriptions {
            replay.push(line.clone());
            if !listen {
                self.drop_answers.insert(id.clone());
            }
            if let Some(value) = serde_json::from_str::<Value>(line).ok().and_then(|m| m.get("id").cloned()) {
                self.pending.insert(id.clone(), value);
            }
        }
        (owed, replay)
    }

    fn is_initialize(&self, id: &str) -> bool {
        self.initialize.as_deref().and_then(id_of).as_deref() == Some(id)
    }
}

fn id_of(line: &str) -> Option<String> {
    serde_json::from_str::<Value>(line).ok()?.get("id").filter(|id| !id.is_null()).map(Value::to_string)
}

/// Relay stdio to the home's server for `target`, starting the server if none is running, and
/// connecting again if it restarts while the client is still there.
pub async fn forward(home: &Path, target: &Target, server_exe: &Path) -> Result<(), String> {
    let (reader, writer) = crate::open_session(home, target, server_exe).await?;
    let (mut from_server, mut to_server): (tokio::io::Lines<BufReader<OwnedReadHalf>>, OwnedWriteHalf) = (reader.lines(), writer);
    let mut from_client = BufReader::new(tokio::io::stdin()).lines();
    let mut to_client = tokio::io::stdout();
    let mut session = Session::default();
    let mut client_done = false;
    loop {
        tokio::select! {
            line = from_client.next_line(), if !client_done => match line {
                Ok(Some(line)) => {
                    session.note_client_line(&line);
                    // A failed write shows up as the server's end closing, below.
                    let _ = to_server.write_all(format!("{line}\n").as_bytes()).await;
                }
                _ => {
                    client_done = true;
                    let _ = to_server.shutdown().await;
                }
            },
            line = from_server.next_line() => match line {
                Ok(Some(line)) => {
                    if session.passes_server_line(&line) {
                        to_client.write_all(format!("{line}\n").as_bytes()).await.map_err(|e| e.to_string())?;
                        to_client.flush().await.map_err(|e| e.to_string())?;
                    }
                }
                _ if client_done => return Ok(()),
                _ => {
                    // The server went away while the client is still here: connect again.
                    let (reader, writer) = crate::open_session(home, target, server_exe).await?;
                    (from_server, to_server) = (reader.lines(), writer);
                    let (owed, replay) = session.restart();
                    for line in owed {
                        to_client.write_all(format!("{line}\n").as_bytes()).await.map_err(|e| e.to_string())?;
                    }
                    to_client.flush().await.map_err(|e| e.to_string())?;
                    for line in replay {
                        to_server.write_all(format!("{line}\n").as_bytes()).await.map_err(|e| e.to_string())?;
                    }
                }
            },
        }
    }
}
