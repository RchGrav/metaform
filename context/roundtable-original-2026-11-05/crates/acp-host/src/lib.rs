//! Host ACP agent harnesses.
//!
//! - [`launch`]: ACP autoselection. Find harnesses (ACP Registry, built-in catalog, custom
//!   commands) and how to start them.
//! - [`Harness`]: one running harness. Negotiates the ACP version (v2 offered first, v1
//!   otherwise), opens and resumes sessions, sets their configuration, sends prompts,
//!   answers permission requests through a [`PermissionPolicy`], and publishes everything as
//!   [`events`] on a [`bus::Bus`]. Nothing here polls, and nothing cancels an agent's turn
//!   unless asked to.
//! - [`models`]: OpenRouter's current model list.
//!
//! This crate knows nothing about Roundtable, so other tools (and the chassis) can host
//! agents with it.

pub mod events;
mod harness;
pub mod launch;
pub mod models;
pub mod permission;
mod process;

pub use agent_client_protocol::v1::schema as acp_schema;
pub use harness::{AgentInit, Harness, InitResponse};
pub use launch::{HarnessEntry, LaunchSpec};
pub use permission::{AllowAll, PermissionAsk, PermissionPolicy, ScopePolicy, Verdict};
