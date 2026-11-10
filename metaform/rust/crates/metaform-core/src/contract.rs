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

    /// Refuse a command that does not match the input schema. `shape::check` comes first and gives
    /// the plain message; this check is the backstop for a rule that check does not hold yet.
    pub(crate) fn check_input(&self, command: &Value) -> Result<(), Refusal> {
        if self.input.is_valid(command) {
            return Ok(());
        }
        let (_, detail) = explain(self.input.iter_errors(command));
        Err(Refusal::new(Code::FieldMismatch, format!("the command {detail}"), None))
    }

    /// Refuse an element view that does not match the stored-document schema.
    pub(crate) fn check_element(&self, address: &str, view: &Value) -> Result<(), Refusal> {
        if self.stored.is_valid(view) {
            return Ok(());
        }
        let (path, detail) = explain(self.stored.iter_errors(view));
        let reason = format!("{} {detail}", place(address, &path));
        Err(Refusal::new(Code::FieldMismatch, reason, None))
    }
}

/// A place in an element, named the way an agent writes it: `status at 'code.engine.game'`,
/// `the want 'code.bus' at 'code.engine.game'`. `path` is the validator's JSON pointer into the
/// element; no message shows it.
fn place(address: &str, path: &str) -> String {
    let segments: Vec<String> = path
        .split('/')
        .skip(1)
        .map(|segment| segment.replace("~1", "/").replace("~0", "~"))
        .collect();
    match segments.as_slice() {
        [field] => format!("{field} at '{address}'"),
        [wants, other] if wants == "wants" => format!("the want '{other}' at '{address}'"),
        [wants, other, field] if wants == "wants" => {
            format!("{field} at the want '{other}' at '{address}'")
        }
        _ => format!("'{address}'"),
    }
}

/// Collect the failures beneath `anyOf` and `oneOf`, which only say that a deeper failure exists,
/// each with its path and its description.
fn leaves(error: &ValidationError<'_>, out: &mut Vec<(String, String)>) {
    match error.kind() {
        ValidationErrorKind::AnyOf { context } | ValidationErrorKind::OneOfNotValid { context } => {
            for error in context.iter().flatten() {
                leaves(error, out);
            }
        }
        _ => out.push((error.instance_path().as_str().to_string(), describe(error))),
    }
}

/// The first of the deepest failures: its path and what it breaks, in plain words. The
/// validator's own message is never the answer an agent receives.
fn explain<'a>(errors: impl Iterator<Item = ValidationError<'a>>) -> (String, String) {
    let mut found = Vec::new();
    for error in errors {
        leaves(&error, &mut found);
    }
    let depth = |path: &str| path.matches('/').count();
    let deepest = found.iter().map(|(path, _)| depth(path)).max();
    found
        .into_iter()
        .find(|(path, _)| Some(depth(path)) == deepest)
        .unwrap_or_else(|| (String::new(), "is not valid".into()))
}

/// What a failure breaks. The text holds no path and no name from the validator's code.
fn describe(deepest: &ValidationError<'_>) -> String {
    let listed = |values: &Value| match values.as_array() {
        Some(values) => values
            .iter()
            .map(|value| value.as_str().map_or_else(|| value.to_string(), str::to_string))
            .collect::<Vec<_>>()
            .join(", "),
        None => values.to_string(),
    };
    match deepest.kind() {
        ValidationErrorKind::Enum { options } => format!("must be one of: {}", listed(options)),
        ValidationErrorKind::Required { property } => {
            format!("has no {}", property.as_str().unwrap_or_default())
        }
        ValidationErrorKind::Type { .. } => "holds a value of the wrong type".into(),
        ValidationErrorKind::AdditionalProperties { unexpected } => {
            format!("does not take: {}", unexpected.join(", "))
        }
        ValidationErrorKind::MinLength { .. } | ValidationErrorKind::Pattern { .. } => {
            "must be text that is not blank".into()
        }
        ValidationErrorKind::MinProperties { limit } => format!("must hold at least {limit} entry"),
        ValidationErrorKind::MaxProperties { limit } => {
            format!("must hold at most {limit} entries")
        }
        ValidationErrorKind::MinItems { limit } => format!("must hold at least {limit} item"),
        ValidationErrorKind::UniqueItems => "must not repeat an item".into(),
        ValidationErrorKind::Not { .. } => {
            format!("cannot be {}", deepest.instance())
        }
        ValidationErrorKind::PropertyNames { error } => {
            format!(
                "holds the name {}, which is not valid: no periods, spaces, '$', '[' or ']'",
                error.instance()
            )
        }
        kind => format!("breaks the schema's '{}' rule", kind.keyword()),
    }
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    use super::*;
    use crate::shape;

    /// The shape check and the input schema accept the same commands, so the schema check stays a
    /// backstop that no command reaches. The one known difference is a blank `role`, which only
    /// the shape check refuses. Each command here is built from a few parts, in every combination.
    #[test]
    fn the_shape_check_and_the_input_schema_agree() {
        let contract = Contract::bundled().unwrap();
        let values = [
            json!(null), json!(true), json!(7), json!(""), json!(" \u{a0}"), json!("text"), json!("todo"),
            json!("inbound"), json!([]), json!(["code.y"]), json!(["code.y", "code.y"]), json!({}),
            json!({"x": 1}), json!({"name": "n"}), json!({"name": ""}), json!({"why": "w"}), json!({"wants": {}}),
            json!({"code.y": {"why": "w", "how": "h", "direction": "inbound"}}),
            json!({"code.y": {"why": "w", "how": "h", "direction": "up"}}),
            json!({"code.y": {"why": "w"}}), json!({"code.y": {"why": "w", "note": "n"}}),
            json!({"code.y": {}}), json!({"code.y": "text"}), json!({".": {"why": "w", "how": "h", "direction": "inbound"}}),
            json!({"y": {"why": ["w"]}}), json!({"y": {"why": {"z": 1}}}), json!({"y": {"how": 1}}),
            json!({"a b": {"x": 1}}), json!({"wants": ["code.y"]}), json!({"wants": "code.y"}),
            json!({"wants": ["."]}), json!({"wants": [7]}), json!({"wants": ["code.y"], "x": 1}),
        ];
        let fields = [
            "technical_name", "name", "role", "status", "project", "uri", "providers", "why", "how",
            "direction", "op", "ef", "ifd", "wants", "note", "a.b", "a b",
        ];
        let keys = ["add", "update", "delete", "map", "orphaned", "goto", ".", ".code.x", "..", "code.x", "code..x", "a$", ""];
        let mut commands = vec![json!({}), json!([]), json!("add"), json!({"add": {}, "map": {}})];
        for value in &values {
            for key in keys {
                commands.push(json!({key: value}));
            }
            for verb in ["add", "update", "delete"] {
                for address in [".", "code.x", "code x", ""] {
                    commands.push(json!({verb: {address: value}}));
                }
                commands.push(json!({verb: {"code.x": value, "code.y": value}}));
            }
            for field in fields {
                for verb in ["add", "update"] {
                    commands.push(json!({verb: {"code.x": {field: value}}}));
                    commands.push(json!({verb: {"code.x": {"part": {field: value}}}}));
                    commands.push(json!({verb: {"code.x": {"name": "n", field: value}}}));
                }
                commands.push(json!({"code.x": {field: value}}));
            }
        }
        assert!(commands.len() > 4000, "{}", commands.len());
        for command in &commands {
            let by_hand = shape::check(command).is_ok();
            let by_schema = contract.input.is_valid(command);
            let text = command.to_string();
            let blank_role = text.contains("\"role\":\"\"") || text.contains("\"role\":\" \u{a0}\"");
            // The shape check is stricter than the schema in two places: a blank role, and an
            // empty `wants` at the command's own element (shape.rs, W8).
            let empty_wants = ["add", "update"].iter().any(|verb| {
                command[verb]["code.x"]["wants"].as_object().is_some_and(|w| w.is_empty())
                    || command[verb]["."]["wants"].as_object().is_some_and(|w| w.is_empty())
            });
            assert!(
                by_hand == by_schema || ((blank_role || empty_wants) && by_schema),
                "{command}: the shape check {by_hand}, the schema {by_schema}"
            );
        }
    }
}
