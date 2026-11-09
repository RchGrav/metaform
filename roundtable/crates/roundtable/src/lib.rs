//! Roundtable: independent agents from different harnesses and models collaborate on a
//! user's objective through a turn-based, judged discussion and a shared workspace.
//!
//! This crate is the core, usable as a library by any host (the bundled web interface, a
//! chat channel adapter, the chassis):
//!
//! - [`spawn`] starts a table from a [`TableConfig`] and returns a [`TableHandle`] for chair
//!   commands. Everything the table does is published as [`events`] on a [`bus::Bus`].
//! - [`rules`] holds the pure rules (allowance, reply kinds, rounds, topic scoring).
//! - [`jev`] is the required judgment client. When a call fails, the message is not shared and
//!   the table continues.
//! - [`mcp`] answers the participant tools' MCP messages for whichever transport the host
//!   serves; [`record`] writes the discussion record.
//!
//! Review IDs in comments point to the earlier build's reviews, under
//! `context/roundtable-original-2026-11-05/` from the repository root:
//! - F01 to F19: review round 2 findings, `review/round2/FINDINGS.md`.
//! - N01: review round 3, `review/round3/VERDICTS.md`.
//! - "audit" IDs such as B28 and Q4: `review/AUDIT-OWNER-DESIGN.md`.
//! - "T" rows such as I-1, and "L K#" items: `docs/TRACEABILITY.md`.

mod agents;
pub mod config;
mod engine;
mod handle;
pub mod events;
pub mod jev;
pub mod mcp;
pub mod names;
pub mod prompts;
pub mod record;
pub mod rules;
pub mod settings;
mod rating;
mod table;
mod topics;
mod turn;

pub use config::{ConfigError, Identities, Profile, SECRET_ENV, SeatConfig, TableConfig, ToolsEndpoint, default_env, default_settings, valid_seat_name};
pub use handle::{TableHandle, path_segment, random_hex, spawn, spawn_with};
pub use table::{Command, MIN_FREE_TO_DISCUSS};
