//! `metaform call`: one command of the Metaform tool from a single command line (R-5.14, R-5.17).
//!
//! It connects exactly as an agent's forwarder does (the same home, launcher and handshake) and
//! speaks MCP to the server, so the server stays the only way to the data and there is no second
//! protocol. It asks for the tool list, calls the one tool, prints the tool's result text, and
//! closes. A CLI command is not an MCP tool (R-5.15): nothing here adds a tool.

use std::path::Path;

use serde_json::{Value, json};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt};

use crate::{Target, open_session};

/// What the tool answered.
pub enum Answer {
    /// The command succeeded; the tool's result text.
    Ok(String),
    /// The command was refused; the refusal JSON, with its code and remediation.
    Refused(String),
}

/// Run one tool command against `target` and return the tool's answer. An error is a usage,
/// connection or server failure, not a refusal.
pub async fn call(
    home: &Path,
    target: &Target,
    server_exe: &Path,
    command: Value,
) -> Result<Answer, String> {
    let (mut reader, mut write) = open_session(home, target, server_exe).await?;
    let meta = json!({
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientInfo": {"name": "metaform-cli", "version": env!("CARGO_PKG_VERSION")},
        "io.modelcontextprotocol/clientCapabilities": {}
    });
    let mut next = 0u64;
    let mut request = async |method: &str, params: Value| -> Result<Value, String> {
        next += 1;
        let mut params = params;
        params["_meta"] = meta.clone();
        let message = json!({"jsonrpc": "2.0", "id": next, "method": method, "params": params});
        write
            .write_all(format!("{message}\n").as_bytes())
            .await
            .map_err(|e| e.to_string())?;
        loop {
            let mut line = String::new();
            if reader
                .read_line(&mut line)
                .await
                .map_err(|e| e.to_string())?
                == 0
            {
                return Err(format!("the server closed the connection during {method}"));
            }
            let reply: Value =
                serde_json::from_str(&line).map_err(|_| format!("the server sent {line:?}"))?;
            if reply["id"] == json!(next) && reply.get("method").is_none() {
                if let Some(error) = reply.get("error") {
                    return Err(format!(
                        "{method}: {}",
                        error["message"].as_str().unwrap_or("error")
                    ));
                }
                return Ok(reply["result"].clone());
            }
        }
    };
    let tools = request("tools/list", json!({})).await?;
    let name = tools["tools"][0]["name"]
        .as_str()
        .ok_or("the server lists no tool")?
        .to_string();
    let result = request("tools/call", json!({"name": name, "arguments": command})).await?;
    drop(request);
    let _ = write.shutdown().await;
    let text = result["content"][0]["text"]
        .as_str()
        .unwrap_or_default()
        .to_string();
    if result["isError"] != json!(true) {
        return Ok(Answer::Ok(text));
    }
    // A refusal is the store's JSON with a code; any other error text is a server failure.
    match serde_json::from_str::<Value>(&text) {
        Ok(refusal) if refusal.get("code").is_some() => Ok(Answer::Refused(text)),
        _ => Err(text),
    }
}
