//! Refusals (R-5.24): a fixed error code, a message in plain words, the tested sentence where one
//! applies, and the remediation command that fixes it. The response follows the founder's
//! examples (documentation set, module 6): the rule a code stands for is documentation, kept here
//! in `Code::rule`, and is not a field of the response.

use std::fmt;

use serde_json::{Value, json};

/// The fixed error codes. The first six are R-5.24's (Decided). The others are the functional map
/// server's additions in the same pattern (Proposed in R-5.24 and the server design).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Code {
    TechnicalNameAlignmentFailure,
    CanonicalNameCollisionFailure,
    RoleTaxonomyFailure,
    GrammarConstraintViolation,
    LayerNotRegistered,
    DependencyLock,
    NameRoundTripFailure,
    NotFound,
    ElementsBeneath,
    WantIncomplete,
    InternalError,
}

impl Code {
    /// The code as an agent receives it.
    pub fn as_str(self) -> &'static str {
        match self {
            Code::TechnicalNameAlignmentFailure => "TECHNICAL_NAME_ALIGNMENT_FAILURE",
            Code::CanonicalNameCollisionFailure => "CANONICAL_NAME_COLLISION_FAILURE",
            Code::RoleTaxonomyFailure => "ROLE_TAXONOMY_FAILURE",
            Code::GrammarConstraintViolation => "GRAMMAR_CONSTRAINT_VIOLATION",
            Code::LayerNotRegistered => "LAYER_NOT_REGISTERED",
            Code::DependencyLock => "DEPENDENCY_LOCK",
            Code::NameRoundTripFailure => "NAME_ROUND_TRIP_FAILURE",
            Code::NotFound => "NOT_FOUND",
            Code::ElementsBeneath => "ELEMENTS_BENEATH",
            Code::WantIncomplete => "WANT_INCOMPLETE",
            Code::InternalError => "INTERNAL_ERROR",
        }
    }

    /// The rule each code stands for, with the requirement it comes from.
    pub fn rule(self) -> &'static str {
        match self {
            Code::TechnicalNameAlignmentFailure => {
                "R-3.11: technical_name is the same number of leading words of the reversed, space-separated address."
            }
            Code::CanonicalNameCollisionFailure => "R-3.12: name must not equal technical_name.",
            Code::RoleTaxonomyFailure => "R-3.13: a map has exactly one Definitive element.",
            Code::GrammarConstraintViolation => {
                "The command must match the project-map input schema, and every element must match the stored-document schema and R-3.3's root scopes."
            }
            Code::LayerNotRegistered => {
                "R-6.10: a layer must be registered before data is written to it."
            }
            Code::DependencyLock => "R-5.7: delete refuses an element that something still wants.",
            Code::NameRoundTripFailure => {
                "R-4.11: a name must convert to camelCase and back exactly, and a name in uppercase is refused, not lowercased."
            }
            Code::NotFound => "R-5.10: a read names an element that exists.",
            Code::ElementsBeneath => {
                "R-3.1: an element with elements beneath it cannot be deleted before them."
            }
            Code::WantIncomplete => "R-5.6: a want needs all of its fields: why, how and intent.",
            Code::InternalError => {
                "Server design, Isolation: an unexpected error fails only the request that caused it."
            }
        }
    }
}

impl fmt::Display for Code {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

/// A refused command. A refused command changes nothing (R-5.8).
#[derive(Clone, Debug, PartialEq, thiserror::Error)]
#[error("{code}: {reason}")]
pub struct Refusal {
    pub code: Code,
    pub reason: String,
    /// The tested sentence, where the rule tests one.
    pub sentence: Option<String>,
    /// The command that fixes the problem. `None` where no command can be derived.
    pub remediation: Option<Box<Value>>,
}

impl Refusal {
    pub fn new(code: Code, reason: impl Into<String>, remediation: Option<Value>) -> Self {
        Refusal {
            code,
            reason: reason.into(),
            sentence: None,
            remediation: remediation.map(Box::new),
        }
    }

    /// The rule the command broke, fixed by its code.
    pub fn rule(&self) -> &'static str {
        self.code.rule()
    }

    /// The refusal's own fields, in the founder's order (module 6): `code`, `message`, the
    /// `tested_sentence` where one applies, and `remediation`. The store puts the echoed command
    /// and `"status": "error"` in front (`metaform_store::refusal_json`).
    pub fn to_json(&self) -> Value {
        let mut out = json!({
            "code": self.code.as_str(),
            "message": self.reason,
        });
        if let Some(sentence) = &self.sentence {
            out["tested_sentence"] = Value::String(sentence.clone());
        }
        out["remediation"] = self.remediation.as_deref().cloned().unwrap_or(Value::Null);
        out
    }
}
