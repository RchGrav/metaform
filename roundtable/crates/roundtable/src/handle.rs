//! The host's control surface for a running table, and starting a table.

use std::collections::BTreeMap;
use std::sync::atomic::Ordering;
use std::sync::{Arc, Mutex};

use bus::Bus;
use tokio::sync::mpsc;

use crate::config::{ConfigError, TableConfig, ToolsEndpoint};
use crate::events::*;
use crate::jev::Jev;
use crate::table::{Command, Flags, Table};

/// Control surface of a running table. Cheap to clone.
#[derive(Clone)]
pub struct TableHandle {
    pub id: String,
    commands: mpsc::UnboundedSender<Command>,
    tokens: Arc<BTreeMap<String, String>>,
    seats: Arc<Vec<String>>,
    flags: Arc<Flags>,
}

impl TableHandle {
    /// Send a command. False when the table has ended.
    pub fn send(&self, command: Command) -> bool {
        !self.is_ended() && self.commands.send(command).is_ok()
    }
    pub fn is_ended(&self) -> bool {
        self.flags.ended.load(Ordering::SeqCst)
    }
    /// Whether topics are active (on, and JEV has its key).
    pub fn topics_enabled(&self) -> bool {
        self.flags.topics.load(Ordering::SeqCst)
    }
    /// Whether a topic poll is in progress.
    pub fn polling(&self) -> bool {
        self.flags.polling.load(Ordering::SeqCst)
    }
    /// Seat labels (the chair's), in seat order.
    pub fn seats(&self) -> &[String] {
        &self.seats
    }
    /// Whether `token` is the tools credential issued to `seat` (constant-time compare).
    pub fn seat_token_valid(&self, seat: &str, token: &str) -> bool {
        !self.is_ended() && self.tokens.get(seat).is_some_and(|known| constant_time_eq(known.as_bytes(), token.as_bytes()))
    }
}

fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
    a.len() == b.len() && a.iter().zip(b).fold(0u8, |acc, (x, y)| acc | (x ^ y)) == 0
}

/// 32 random bytes from the operating system, as hex.
pub fn random_hex() -> String {
    let mut bytes = [0u8; 32];
    getrandom::fill(&mut bytes).expect("the operating system's random source");
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

/// Encode text as one URL path segment.
pub fn path_segment(text: &str) -> String {
    text.bytes()
        .map(|b| match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' => (b as char).to_string(),
            _ => format!("%{b:02X}"),
        })
        .collect()
}

/// Start a table. Returns at once; seat startup and everything after are events. Errors only
/// for an invalid configuration.
pub fn spawn(id: String, cfg: TableConfig, bus: Bus, jev: Jev, tools: Option<ToolsEndpoint>) -> Result<TableHandle, ConfigError> {
    spawn_with(id, cfg, bus, jev, tools, None)
}

/// [`spawn`], with a store of identity profiles for the owner's profile and results messages.
pub fn spawn_with(
    id: String,
    cfg: TableConfig,
    bus: Bus,
    jev: Jev,
    tools: Option<ToolsEndpoint>,
    identities: Option<Arc<dyn crate::config::Identities>>,
) -> Result<TableHandle, ConfigError> {
    cfg.validate()?;
    // JEV is required (owner): a table does not start without its key.
    if !jev.configured() {
        return Err(ConfigError("JEV is required and no OpenRouter key is set".into()));
    }
    let (tx, rx) = mpsc::unbounded_channel();
    let (internal_tx, internal_rx) = mpsc::unbounded_channel();
    let tokens: BTreeMap<String, String> = cfg.seats.iter().map(|seat| (seat.name.clone(), random_hex())).collect();
    let flags = Arc::new(Flags::default());
    flags.topics.store(cfg.topics && jev.configured(), Ordering::SeqCst);
    let handle = TableHandle {
        id: id.clone(),
        commands: tx,
        tokens: Arc::new(tokens.clone()),
        seats: Arc::new(cfg.seats.iter().map(|s| s.name.clone()).collect()),
        flags: flags.clone(),
    };
    let tap = bus.tap();
    let live = Arc::new(Mutex::new(Vec::new()));
    let mut table = Table::new(id.clone(), cfg, bus.clone(), jev, internal_tx, live.clone(), flags.clone());
    table.identities = identities;
    let engine = tokio::spawn(async move {
        table.start(&tokens, tools);
        table.run(rx, internal_rx, tap).await;
    });
    // If the engine task dies, say so loudly and stop the agents instead of hanging.
    tokio::spawn(async move {
        if let Err(error) = engine.await {
            if flags.ended.swap(true, Ordering::SeqCst) {
                return;
            }
            for harness in live.lock().unwrap().iter() {
                harness.shutdown();
            }
            bus.publish(Notice { table: id.clone(), level: "error".into(), text: format!("The engine stopped unexpectedly: {error}") });
            bus.publish(TableEnded { table: id, reason: format!("the engine stopped unexpectedly: {error}") });
        }
    });
    Ok(handle)
}
