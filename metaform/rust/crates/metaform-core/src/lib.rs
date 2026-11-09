//! `metaform-core`: the Metaform map model, address rules, command validation and the commands
//! `add`, `update`, `delete`, `orphaned` and addressed reads. No networking.
//!
//! Behaviour follows `metaform/SPEC.md`; the contract is `metaform/mcp-tools.proposed.json` and
//! `metaform/metaform.schema.json`. A map is the unit: a project's main map is one map, a map can
//! stand alone, and an element can carry a child map (`Element::child_map`).
//!
//! ```text
//! use metaform_core::{Contract, Map, execute};
//! let contract = Contract::bundled().unwrap();
//! let map = Map::new();
//! let outcome = execute(&contract, &map, &serde_json::json!({"orphaned": {}})).unwrap();
//! println!("{}", outcome.result());
//! ```

mod commands;
mod contract;
mod model;
mod names;
mod reads;
mod refusal;
pub mod check;
pub mod markdown;
pub mod specification;

pub use commands::{Outcome, Write, execute};
pub use contract::{Contract, ContractError};
pub use model::{Effect, Element, Fields, Map, MapError, MapRef};
pub use names::{ROOT, ROOT_SCOPES, agent_name, stored_name};
pub use refusal::{Code, Refusal};
