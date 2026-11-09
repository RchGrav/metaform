//! Roundtable: independent agents from different harnesses and models collaborate on a
//! user's objective through a turn-based, judged discussion and a shared workspace.
//!
//! This crate is the core, usable as a library by any host (the bundled web interface, a
//! chat channel adapter, the chassis):
//!
//! - [`spawn`] starts a table from a [`TableConfig`] and returns a [`TableHandle`] for chair
//!   commands. Everything the table does is published as [`events`] on a [`bus::Bus`].
//! - [`rules`] holds the pure rules (allowance, reply kinds, rounds, topic scoring).
//! - [`jev`] is the optional judgment client; it fails open.
//! - [`mcp`] answers the participant tools' MCP messages for whichever transport the host
//!   serves; [`record`] writes the discussion record.

pub mod config;
mod engine;
pub mod events;
pub mod jev;
pub mod mcp;
pub mod names;
pub mod prompts;
pub mod record;
pub mod rules;
mod turn;

pub use config::{ConfigError, Identities, Profile, SECRET_ENV, SeatConfig, TableConfig, ToolsEndpoint, default_env, default_settings, valid_seat_name};
pub use engine::{Command, TableHandle, path_segment, random_hex, spawn, spawn_with};
