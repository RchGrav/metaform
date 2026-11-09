//! The participant tools (O) as a minimal MCP server, independent of any web framework. A host
//! receives MCP JSON-RPC messages for one seat (e.g. over Streamable HTTP, a JSON reply per
//! POST) and passes them to [`handle`]. Tool calls become [`Command`]s; replies say only what
//! is true at the time of the call.

use std::collections::BTreeMap;

use serde_json::{Value, json};

use crate::handle::TableHandle;
use crate::table::Command;

const PROTOCOL: &str = "2025-06-18";

pub fn tools() -> Value {
    json!([
        {
            "name": "advance",
            "description": "End the current Roundtable topic, normally used by the head of the table. Give `topic` to set the next topic; leave it out to have every participant propose one. Takes effect when the current turn ends. Topics need JEV judging.",
            "inputSchema": {"type": "object", "properties": {"topic": {"type": "string"}}, "additionalProperties": false}
        },
        {
            "name": "feedback",
            "description": "Rate another participant's conduct (0-5 in each category, plus a bonus), naming them as they appear at the table. It is shown to the chair and saved to that participant's identity; if the name matches no participant you are told at your next turn.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "participant": {"type": "string", "description": "The name of the participant you are rating."},
                    "Efficient": {"type": "integer"},
                    "Alert & Aware": {"type": "integer"},
                    "Thorough": {"type": "integer"},
                    "Coordination": {"type": "integer"},
                    "bonus": {"type": "boolean"},
                    "note": {"type": "string"}
                },
                "required": ["participant"]
            }
        }
    ])
}

/// Answer one JSON-RPC message from `seat`. `None` for notifications.
pub fn handle(table: &TableHandle, seat: &str, message: &Value) -> Option<Value> {
    let id = message.get("id").cloned()?;
    let method = message.get("method").and_then(Value::as_str).unwrap_or_default();
    let params = message.get("params").cloned().unwrap_or(Value::Null);
    let result = match method {
        "initialize" => Ok(json!({
            "protocolVersion": params.get("protocolVersion").and_then(Value::as_str).unwrap_or(PROTOCOL),
            "capabilities": {"tools": {"listChanged": false}},
            "serverInfo": {"name": "roundtable", "version": env!("CARGO_PKG_VERSION")}
        })),
        "ping" => Ok(json!({})),
        "tools/list" => Ok(json!({"tools": tools()})),
        "tools/call" => Ok(call(table, seat, &params)),
        other => Err((-32601, format!("method not found: {other}"))),
    };
    Some(match result {
        Ok(result) => json!({"jsonrpc": "2.0", "id": id, "result": result}),
        Err((code, message)) => json!({"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}),
    })
}

fn call(table: &TableHandle, seat: &str, params: &Value) -> Value {
    let args = params.get("arguments").cloned().unwrap_or_else(|| json!({}));
    match params.get("name").and_then(Value::as_str).unwrap_or_default() {
        "advance" => {
            if !table.topics_enabled() {
                // gate: RT-G07 topics are off by default and need JEV
                return text("Not done: this table has no topics. Topics are a table setting and also need JEV judging.", true);
            }
            // The engine refuses an advance during a poll; the reply must say so (L#13: tell the truth).
            if table.polling() {
                // gate: RT-G11 advance is refused during a poll
                return text("Not done: a topic poll is in progress; the poll decides the next topic.", true);
            }
            let topic = args.get("topic").and_then(Value::as_str).map(str::to_string).filter(|t| !t.trim().is_empty());
            let said = match &topic {
                Some(topic) => format!("Requested: when the current turn ends, the topic becomes: {topic}"),
                None => "Requested: when the current turn ends, the topic closes and every participant proposes the next one.".into(),
            };
            // not a gate: the table has ended
            if table.send(Command::Advance { by: seat.to_string(), topic }) { text(&said, false) } else { text("Not done: the table has ended.", true) }
        }
        "feedback" => {
            let Some(to) = args.get("participant").and_then(Value::as_str).map(str::to_string) else {
                // gate: RT-G15 feedback must name a participant
                return text("Not recorded: name the participant you are rating.", true);
            };
            let mut ratings = BTreeMap::new();
            if let Some(object) = args.as_object() {
                for (key, value) in object {
                    if key != "participant" && key != "note" {
                        ratings.insert(key.clone(), value.clone());
                    }
                }
            }
            let note = args.get("note").and_then(Value::as_str).unwrap_or_default().to_string();
            if table.send(Command::Feedback { from: seat.to_string(), to: to.clone(), ratings, note }) {
                text(&format!("Sent your feedback for {to} to the table."), false)
            } else {
                // not a gate: the table has ended
                text("Not recorded: the table has ended.", true)
            }
        }
        other => text(&format!("Unknown tool: {other}"), true),
    }
}

fn text(message: &str, is_error: bool) -> Value {
    json!({"content": [{"type": "text", "text": message}], "isError": is_error})
}
