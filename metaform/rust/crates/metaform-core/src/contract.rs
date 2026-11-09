//! The contract: the `project-map` tool's input schema (`metaform/mcp-tools.proposed.json`) and the
//! stored-document schema (`metaform/metaform.schema.json`). Both files stay the single source; the
//! bundled contract compiles them in from their paths, and nothing here copies or changes them.

use jsonschema::error::ValidationErrorKind;
use jsonschema::{ValidationError, Validator};
use serde_json::Value;

use crate::refusal::{Code, Refusal};

const TOOLS: &str = include_str!("../../../../mcp-tools.proposed.json");
const STORED_SCHEMA: &str = include_str!("../../../../metaform.schema.json");

/// A problem with the contract files themselves.
#[derive(Debug, thiserror::Error)]
pub enum ContractError {
    #[error("the contract is not valid JSON: {0}")]
    Json(#[from] serde_json::Error),
    #[error("{0}")]
    Invalid(String),
}

/// The compiled contract.
pub struct Contract {
    tool: Value,
    input: Validator,
    stored: Validator,
}

impl Contract {
    /// The contract as the project's files hold it at build time.
    pub fn bundled() -> Result<Contract, ContractError> {
        Contract::from_json(
            &serde_json::from_str(TOOLS)?,
            &serde_json::from_str(STORED_SCHEMA)?,
        )
    }

    /// A contract from a tool registry with exactly one tool, and a stored-document schema.
    pub fn from_json(tools: &Value, stored_schema: &Value) -> Result<Contract, ContractError> {
        let listed = tools
            .get("tools")
            .and_then(Value::as_array)
            .map(Vec::as_slice)
            .unwrap_or_default();
        let [tool] = listed else {
            return Err(ContractError::Invalid(
                "the contract must declare exactly one tool".into(),
            ));
        };
        let schema = tool
            .get("inputSchema")
            .ok_or_else(|| ContractError::Invalid("the tool has no inputSchema".into()))?;
        let compile = |schema: &Value| {
            jsonschema::validator_for(schema)
                .map_err(|error| ContractError::Invalid(error.to_string()))
        };
        Ok(Contract {
            tool: tool.clone(),
            input: compile(schema)?,
            stored: compile(stored_schema)?,
        })
    }

    /// The tool's declaration: name, description and input schema.
    pub fn tool(&self) -> &Value {
        &self.tool
    }

    /// The tool's name.
    pub fn tool_name(&self) -> &str {
        self.tool
            .get("name")
            .and_then(Value::as_str)
            .unwrap_or_default()
    }

    /// Refuse a command that does not match the input schema.
    pub(crate) fn check_input(&self, command: &Value) -> Result<(), Refusal> {
        if self.input.is_valid(command) {
            return Ok(());
        }
        let reason = explain(self.input.iter_errors(command));
        Err(Refusal::new(Code::GrammarConstraintViolation, reason, None))
    }

    /// Refuse an element view that does not match the stored-document schema.
    pub(crate) fn check_element(&self, address: &str, view: &Value) -> Result<(), Refusal> {
        if self.stored.is_valid(view) {
            return Ok(());
        }
        let reason = format!("'{address}': {}", explain(self.stored.iter_errors(view)));
        Err(Refusal::new(Code::GrammarConstraintViolation, reason, None))
    }
}

/// Collect the failures beneath `anyOf` and `oneOf`, which only say that a deeper failure exists,
/// each with its depth and its description.
fn leaves(error: &ValidationError<'_>, out: &mut Vec<(usize, String)>) {
    match error.kind() {
        ValidationErrorKind::AnyOf { context } | ValidationErrorKind::OneOfNotValid { context } => {
            for error in context.iter().flatten() {
                leaves(error, out);
            }
        }
        _ => out.push((
            error.instance_path().as_str().matches('/').count(),
            describe(error),
        )),
    }
}

/// The first of the deepest failures, in plain words with the path where it happened. The
/// validator's own message is never the answer an agent receives.
fn explain<'a>(errors: impl Iterator<Item = ValidationError<'a>>) -> String {
    let mut found = Vec::new();
    for error in errors {
        leaves(&error, &mut found);
    }
    let deepest = found.iter().map(|(depth, _)| *depth).max();
    found
        .into_iter()
        .find(|(depth, _)| Some(*depth) == deepest)
        .map_or_else(|| "the input is not valid".into(), |(_, text)| text)
}

fn describe(deepest: &ValidationError<'_>) -> String {
    let path = deepest.instance_path().as_str();
    let at = if path.is_empty() {
        "the command".to_string()
    } else {
        format!("'{path}'")
    };
    let detail = match deepest.kind() {
        ValidationErrorKind::Enum { options } => format!("must be one of: {options}"),
        ValidationErrorKind::Required { property } => format!("is missing the field {property}"),
        ValidationErrorKind::Type { kind } => format!("must be of type {kind:?}"),
        ValidationErrorKind::AdditionalProperties { unexpected } => {
            format!("does not take: {}", unexpected.join(", "))
        }
        ValidationErrorKind::MinLength { .. } | ValidationErrorKind::Pattern { .. }
            if deepest.instance().is_string() =>
        {
            format!(
                "the value {} does not have the required form",
                deepest.instance()
            )
        }
        ValidationErrorKind::MinProperties { limit } => format!("must hold at least {limit} entry"),
        ValidationErrorKind::MaxProperties { limit } => {
            format!("must hold at most {limit} entries")
        }
        ValidationErrorKind::MinItems { limit } => format!("must hold at least {limit} item"),
        ValidationErrorKind::UniqueItems => "must not repeat an item".into(),
        ValidationErrorKind::Not { .. } => {
            format!("the value {} is not allowed", deepest.instance())
        }
        ValidationErrorKind::PropertyNames { error } => {
            format!(
                "the name {} is not an address: no '$', '[', ']', spaces or empty segments",
                error.instance()
            )
        }
        kind => format!("breaks the schema's '{}' rule", kind.keyword()),
    };
    format!("{at} {detail}")
}
