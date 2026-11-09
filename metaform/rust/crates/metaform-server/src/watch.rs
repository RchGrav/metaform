//! A client that hears of each commit to one map, for programs outside the server such as the
//! graph workspace host (`metaform-web`).
//!
//! It connects exactly as `metaform call` does (the same home, launcher and handshake), asks for
//! the connection's one resource (the map), and opens `subscriptions/listen` for that resource's
//! URI (MCP 2026-07-28). The server answers each commit with `notifications/resources/updated`
//! and no content, so a watcher learns only that the map changed and reads it again.

use std::path::Path;

use serde_json::{Value, json};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt};
use tokio::sync::mpsc;

use crate::{Target, open_session};

/// Starts watching the map of `target`. The receiver gets one `()` per commit. It closes when
/// the server closes the connection; dropping it ends the watch at the next commit.
pub async fn watch(
    home: &Path,
    target: &Target,
    server_exe: &Path,
) -> Result<mpsc::Receiver<()>, String> {
    let (mut reader, mut write) = open_session(home, target, server_exe).await?;
    let meta = json!({
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientInfo": {"name": "metaform-watch", "version": env!("CARGO_PKG_VERSION")},
        "io.modelcontextprotocol/clientCapabilities": {}
    });
    let send = |id: u64, method: &str, params: Value| {
        let mut params = params;
        params["_meta"] = meta.clone();
        format!("{}\n", json!({"jsonrpc": "2.0", "id": id, "method": method, "params": params}))
    };

    write
        .write_all(send(1, "resources/list", json!({})).as_bytes())
        .await
        .map_err(|e| e.to_string())?;
    let uri = loop {
        let mut line = String::new();
        if reader.read_line(&mut line).await.map_err(|e| e.to_string())? == 0 {
            return Err("the server closed the connection during resources/list".into());
        }
        let reply: Value = serde_json::from_str(&line).map_err(|_| format!("the server sent {line:?}"))?;
        if reply["id"] == json!(1) {
            if let Some(error) = reply.get("error") {
                return Err(format!("resources/list: {}", error["message"].as_str().unwrap_or("error")));
            }
            break reply["result"]["resources"][0]["uri"]
                .as_str()
                .ok_or("the server lists no map resource")?
                .to_string();
        }
    };

    let listen = send(2, "subscriptions/listen", json!({"notifications": {"resourceSubscriptions": [uri]}}));
    write.write_all(listen.as_bytes()).await.map_err(|e| e.to_string())?;

    let (tx, rx) = mpsc::channel(16);
    tokio::spawn(async move {
        // Keep the write half open: closing it would end the session and the listen.
        let _write = write;
        loop {
            let mut line = String::new();
            match reader.read_line(&mut line).await {
                Ok(0) | Err(_) => return,
                Ok(_) => {}
            }
            let Ok(message) = serde_json::from_str::<Value>(&line) else { continue };
            if message["method"] == json!("notifications/resources/updated")
                && message["params"]["uri"] == json!(uri)
                && tx.send(()).await.is_err()
            {
                return;
            }
        }
    });
    Ok(rx)
}
