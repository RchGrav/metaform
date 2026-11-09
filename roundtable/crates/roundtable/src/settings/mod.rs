//! Settings: every value a table runs with that the owner can change, declared once.
//!
//! The rules follow the owner's settings design (topogee `docs/designs/cli-design.md`, C-9 to
//! C-17):
//! - One declaration per setting ([`SETTINGS`]). Validation, listing, the API, the settings page
//!   and the table configuration all come from it; nothing keeps a second list.
//! - Defaults are home: unsetting a key restores its default, and a reset never leaves a value
//!   empty (C-9).
//! - Only what the owner set is stored; defaults are computed, and every value shows its source
//!   (C-13).
//! - Settings belong to the user: they live in Roundtable's home folder, never in a workspace
//!   (C-14).
//! - Values are validated on the way in and refused loudly; numbers are never clamped; a stored
//!   value that fails validation is reported and replaced by its default (C-16).
//! - A change reports each key's old and new value (C-17).
//!
//! Who may change settings: only the chair, through the chair-token API. Agents' tools cannot
//! read or change them.
//!
//! A setting with a `gate` is the switch or the limit of that inference gate in
//! `docs/gate-registry.yaml`. Changing it is the owner's disposition of the gate.

mod decl;
mod store;

pub use decl::SETTINGS;
pub use store::{Change, Row, Source, Store};

use crate::config::TableConfig;

/// What values a setting accepts.
#[derive(Debug, Clone, Copy)]
pub enum Kind {
    /// on/off; accepts true/false, yes/no, on/off, 1/0 in any case.
    Bool,
    /// A whole number within the range, inclusive.
    Count { min: u64, max: u64 },
    /// A whole number within the range, or "off" for none.
    CountOrOff { min: u64, max: u64 },
    /// One of the listed words, matched in any case, stored in the listed case.
    Choice(&'static [&'static str]),
    /// "workspace", "project", or an absolute path.
    Scope,
}

/// A validated value.
#[derive(Debug, Clone, PartialEq)]
pub enum Value {
    Bool(bool),
    Count(u64),
    Off,
    Word(String),
    Path(std::path::PathBuf),
}

impl Value {
    /// The canonical text form, as stored and shown.
    pub fn text(&self) -> String {
        match self {
            Value::Bool(b) => if *b { "on" } else { "off" }.into(),
            Value::Count(n) => n.to_string(),
            Value::Off => "off".into(),
            Value::Word(w) => w.clone(),
            Value::Path(p) => p.display().to_string(),
        }
    }
    pub fn as_bool(&self) -> bool {
        matches!(self, Value::Bool(true))
    }
    pub fn as_count(&self) -> Option<u64> {
        match self {
            Value::Count(n) => Some(*n),
            _ => None,
        }
    }
}

/// One setting.
pub struct Setting {
    /// Dotted name, e.g. `limits.reply`.
    pub key: &'static str,
    pub kind: Kind,
    /// The default, in the same text form a user would type.
    pub default: &'static str,
    /// One plain sentence: what it does.
    pub summary: &'static str,
    /// The inference gate this setting controls, by registry id.
    pub gate: Option<&'static str>,
    /// Puts the value into a table's configuration.
    pub apply: fn(&mut TableConfig, &Value),
}

impl Setting {
    /// The group is the part of the key before the first dot.
    pub fn group(&self) -> &'static str {
        self.key.split('.').next().unwrap_or(self.key)
    }

    /// Validate and normalise `raw`. The error names the allowed form or range.
    pub fn parse(&self, raw: &str) -> Result<Value, String> {
        let text = raw.trim();
        let lower = text.to_ascii_lowercase();
        match self.kind {
            Kind::Bool => match lower.as_str() {
                "true" | "yes" | "on" | "1" => Ok(Value::Bool(true)),
                "false" | "no" | "off" | "0" => Ok(Value::Bool(false)),
                _ => Err(format!("{} takes on or off, not {text:?}", self.key)),
            },
            Kind::Count { min, max } => parse_count(self.key, text, min, max).map(Value::Count),
            Kind::CountOrOff { min, max } => {
                if lower == "off" || lower == "none" {
                    Ok(Value::Off)
                } else {
                    parse_count(self.key, text, min, max).map(Value::Count).map_err(|e| format!("{e}, or off"))
                }
            }
            Kind::Choice(words) => words
                .iter()
                .find(|w| w.eq_ignore_ascii_case(text))
                .map(|w| Value::Word((*w).to_string()))
                .ok_or_else(|| format!("{} takes one of {}, not {text:?}", self.key, words.join(", "))),
            Kind::Scope => match lower.as_str() {
                "workspace" | "project" => Ok(Value::Word(lower)),
                _ if std::path::Path::new(text).is_absolute() => Ok(Value::Path(text.into())),
                _ => Err(format!("{} takes workspace, project or an absolute path, not {text:?}", self.key)),
            },
        }
    }

    /// The default as a value. Declarations are checked by a test, so this cannot fail.
    pub fn default_value(&self) -> Value {
        self.parse(self.default).unwrap_or_else(|e| panic!("bad default for {}: {e}", self.key))
    }
}

fn parse_count(key: &str, text: &str, min: u64, max: u64) -> Result<u64, String> {
    match text.replace('_', "").parse::<u64>() {
        Ok(n) if (min..=max).contains(&n) => Ok(n),
        _ => Err(format!("{key} takes a whole number from {min} to {max}, not {text:?}")),
    }
}

/// The declaration for `key`.
pub fn find(key: &str) -> Option<&'static Setting> {
    SETTINGS.iter().find(|s| s.key == key)
}

/// The default value of a declared setting, for configuration defaults.
pub(crate) fn default_of(key: &str) -> Value {
    find(key).unwrap_or_else(|| panic!("undeclared setting {key}")).default_value()
}
