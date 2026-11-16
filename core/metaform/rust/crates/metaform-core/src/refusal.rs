//! Refusals (R-5.24): a fixed error code, a message in plain words, the tested sentence where one
//! applies, and the remediation command that fixes it. The response follows the founder's
//! examples (documentation set, module 6): the rule a code stands for is documentation, kept here
//! in `Code::rule`, and is not a field of the response.

use std::fmt;

use serde_json::{Value, json};

/// The fixed error codes. R-5.24 decides six: TechnicalNameAlignmentFailure,
/// CanonicalNameCollisionFailure, RoleTaxonomyFailure, GrammarConstraintViolation,
/// LayerNotRegistered and DependencyLock. FieldMismatch, RootScopeNotAllowed and
/// FieldElementCollision follow the founder's direction of 2026-11-09 (R-5.24). The others are the
/// functional map server's additions in the same pattern (Proposed in R-5.24 and the server design).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Code {
    TechnicalNameAlignmentFailure,
    CanonicalNameCollisionFailure,
    RoleTaxonomyFailure,
    GrammarConstraintViolation,
    FieldMismatch,
    RootScopeNotAllowed,
    FieldElementCollision,
    LayerNotRegistered,
    DependencyLock,
    NameRoundTripFailure,
    NotFound,
    ElementsBeneath,
    WantIncomplete,
    ElementNotInSkeleton,
    HeadingLevelInvalid,
    HeadingInText,
    LayerDefinitionLocked,
    CodeNotUnique,
    LayerNameCollision,
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
            Code::FieldMismatch => "FIELD_MISMATCH",
            Code::RootScopeNotAllowed => "ROOT_SCOPE_NOT_ALLOWED",
            Code::FieldElementCollision => "FIELD_ELEMENT_COLLISION",
            Code::LayerNotRegistered => "LAYER_NOT_REGISTERED",
            Code::DependencyLock => "DEPENDENCY_LOCK",
            Code::NameRoundTripFailure => "NAME_ROUND_TRIP_FAILURE",
            Code::NotFound => "NOT_FOUND",
            Code::ElementsBeneath => "ELEMENTS_BENEATH",
            Code::WantIncomplete => "WANT_INCOMPLETE",
            Code::ElementNotInSkeleton => "ELEMENT_NOT_IN_SKELETON",
            Code::HeadingLevelInvalid => "HEADING_LEVEL_INVALID",
            Code::HeadingInText => "HEADING_IN_TEXT",
            Code::LayerDefinitionLocked => "LAYER_DEFINITION_LOCKED",
            Code::CodeNotUnique => "CODE_NOT_UNIQUE",
            Code::LayerNameCollision => "LAYER_NAME_COLLISION",
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
            Code::RoleTaxonomyFailure => {
                "R-3.13: a role is Artifact Type, Defining Element, Supporting Element, Coupled Element, Notable Element, Vested Beneficiary, Upstream Dependency or Downstream Dependant."
            }
            Code::GrammarConstraintViolation => {
                "Module 6.4: why is a bare infinitive verb phrase, how is a third-person present verb phrase, and neither has words ending in -ing. Not checked yet (D-14)."
            }
            Code::FieldMismatch => {
                "The command must match the project-map input schema, and every element must match the stored-document schema."
            }
            Code::RootScopeNotAllowed => "R-3.3: a top-level element is in one of the root scopes.",
            Code::FieldElementCollision => {
                "A word on an element is either a field or the name of an element beneath it, not both."
            }
            Code::LayerNotRegistered => {
                "R-6.24, R-6.15: a list is written only to a layer defined beneath layer, or to a system layer (skills, memory, sources)."
            }
            Code::DependencyLock => "R-5.7: delete refuses an element that another element still wants.",
            Code::NameRoundTripFailure => {
                "R-4.11: a name must convert to camelCase and back exactly, and a name in uppercase is refused, not lowercased."
            }
            Code::NotFound => "R-5.10: a read names an element that exists.",
            Code::ElementsBeneath => {
                "R-3.1: an element with elements beneath it cannot be deleted before them."
            }
            Code::WantIncomplete => "R-5.6: a want needs all of its fields: why, how and direction.",
            Code::ElementNotInSkeleton => {
                "R-6.26: layer records are written only at an element with technical_name, name and role, or at the root once the map has a Defining Element."
            }
            Code::HeadingLevelInvalid => {
                "R-6.25: the first titled block is level 1, each level is at most one more than the level before it, and no level is above 4."
            }
            Code::LayerNameCollision => {
                "R-6.24: a layer definition's last segment is the layer's field name, so no two definitions share it."
            }
            Code::CodeNotUnique => {
                "R-6.25: a block's code is unique within its layer across the map, ignoring case, so other text can cite it."
            }
            Code::LayerDefinitionLocked => {
                "R-6.24, R-6.11: a layer defined by the server's code keeps the definition the code gives it; agents write only its records."
            }
            Code::HeadingInText => {
                "R-6.25: block text holds no Markdown heading line outside fenced code; the block's level and title set its heading."
            }
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

    /// The rule the command broke, as its code determines.
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
