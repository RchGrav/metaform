//! The discussion record: every event, in order, as JSON lines. Built from a bus tap, so it
//! holds exactly what happened, including every prompt each agent actually received.

use std::io::Write;
use std::path::Path;

use bus::{Bus, Envelope};
use serde_json::json;

/// One record line for an event.
pub fn line(envelope: &Envelope) -> serde_json::Value {
    let at = envelope.at.duration_since(std::time::UNIX_EPOCH).map(|d| d.as_millis() as u64).unwrap_or_default();
    json!({
        "seq": envelope.seq,
        "at_ms": at,
        "event": envelope.name,
        "data": envelope.to_json().unwrap_or(serde_json::Value::Null),
    })
}

/// The table an event belongs to: its `table` field, or the table prefix of a harness id.
/// acp-host names the harness as a "table/seat" string; agent-monitor carries a `{pid, id}`
/// object whose `id` is that same string (F09).
pub fn table_of(data: &serde_json::Value) -> Option<String> {
    if let Some(table) = data.get("table").and_then(|v| v.as_str()) {
        return Some(table.to_string());
    }
    harness_id(data).and_then(|h| h.split_once('/')).map(|(t, _)| t.to_string())
}

/// The harness id of an acp-host or agent-monitor event.
pub fn harness_id(data: &serde_json::Value) -> Option<&str> {
    let harness = data.get("harness")?;
    harness.as_str().or_else(|| harness.get("id").and_then(|id| id.as_str()))
}

/// Append every event of `table` to `path` until the bus closes or the table ends.
pub fn spawn_recorder(bus: &Bus, table: String, path: &Path) -> std::io::Result<()> {
    if let Some(dir) = path.parent() {
        std::fs::create_dir_all(dir)?;
    }
    let mut file = std::fs::OpenOptions::new().create(true).append(true).open(path)?;
    let mut tap = bus.tap();
    tokio::spawn(async move {
        while let Some(envelope) = tap.recv().await {
            let line = line(&envelope);
            if table_of(&line["data"]).as_deref() != Some(table.as_str()) {
                continue;
            }
            let _ = writeln!(file, "{line}");
            if envelope.name == "roundtable.ended" {
                break;
            }
        }
    });
    Ok(())
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    // Review round 2, F09: agent-monitor events carry the harness as {pid, id}.
    #[test]
    fn monitor_events_route_to_their_table() {
        assert_eq!(super::table_of(&json!({"harness": {"pid": 7, "id": "t1/Sol"}, "capture": "process"})).as_deref(), Some("t1"));
        assert_eq!(super::table_of(&json!({"harness": "t2/Ada"})).as_deref(), Some("t2"));
        assert_eq!(super::table_of(&json!({"harness": {"pid": 7, "id": null}})), None);
        assert_eq!(super::table_of(&json!({"table": "t3", "harness": {"pid": 1}})).as_deref(), Some("t3"));
    }
}
