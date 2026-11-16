//! Address rules and the conversion between the agent's snake_case and the stored camelCase
//! (R-3.2, R-3.3, R-4.11). Agents see snake_case and full addresses; storage sees camelCase.

use serde_json::{Map as JsonMap, Value};

use crate::refusal::{Code, Refusal};

/// The address of a map's root (R-5.9).
pub const ROOT: &str = ".";

/// The valid root scopes (R-3.3).
pub const ROOT_SCOPES: [&str; 7] = [
    "code",
    "document",
    "media",
    "data",
    "upstream",
    "downstream",
    "layer",
];

/// The root prefixes (R-3.3): what follows them is not located in the project. `upstream` and
/// `downstream` are outside the project being mapped (R-3.7), and `layer` holds layer
/// definitions (R-6.24).
pub const ROOT_PREFIXES: [&str; 3] = ["upstream", "downstream", "layer"];

/// Whether an address belongs to the project itself: the root, or an element not under a root
/// prefix. A Defining Element counts only among these elements.
pub fn in_project(address: &str) -> bool {
    address == ROOT || !ROOT_PREFIXES.contains(&address.split('.').next().unwrap_or_default())
}

pub(crate) fn to_camel(snake: &str) -> String {
    let mut out = String::with_capacity(snake.len());
    let mut upper = false;
    for c in snake.chars() {
        if c == '_' {
            upper = true;
        } else if upper {
            out.extend(c.to_uppercase());
            upper = false;
        } else {
            out.push(c);
        }
    }
    out
}

pub(crate) fn to_snake(camel: &str) -> String {
    let mut out = String::with_capacity(camel.len() + 4);
    for c in camel.chars() {
        if c.is_uppercase() {
            out.push('_');
            out.extend(c.to_lowercase());
        } else {
            out.push(c);
        }
    }
    out
}

/// Convert every segment of an address with `convert`.
pub(crate) fn map_address(address: &str, convert: fn(&str) -> String) -> String {
    if address == ROOT {
        return ROOT.to_string();
    }
    address
        .split('.')
        .map(convert)
        .collect::<Vec<_>>()
        .join(".")
}

/// Why a name would not survive storage, or `None` if it converts back exactly.
pub(crate) fn segment_problem(segment: &str) -> Option<&'static str> {
    if segment.chars().any(char::is_uppercase) {
        return Some("a name in uppercase is refused, not lowercased");
    }
    if to_snake(&to_camel(segment)) == segment {
        return None;
    }
    Some(if segment.contains("__") {
        "repeated underscores do not survive storage"
    } else if segment.ends_with('_') {
        "a trailing underscore does not survive storage"
    } else {
        "an underscore before a digit or symbol does not survive storage"
    })
}

/// The nearest name that survives storage: lowercased, single underscores, digits joined to the
/// word before them.
pub(crate) fn suggest_segment(segment: &str) -> String {
    let lower = segment.to_lowercase();
    let mut out = String::new();
    for word in lower.split('_').filter(|word| !word.is_empty()) {
        let starts_with_letter = word.chars().next().is_some_and(char::is_alphabetic);
        if !out.is_empty() && starts_with_letter {
            out.push('_');
        }
        out.push_str(word);
    }
    out
}

pub(crate) fn join(address: &str, segment: &str) -> String {
    if address == ROOT {
        segment.to_string()
    } else {
        format!("{address}.{segment}")
    }
}

/// The parent of an address; `None` for the root.
pub(crate) fn parent(address: &str) -> Option<&str> {
    if address == ROOT {
        return None;
    }
    Some(address.rsplit_once('.').map_or(ROOT, |(head, _)| head))
}

/// Every prefix of an address, the root first and the address itself last.
pub(crate) fn prefixes(address: &str) -> Vec<String> {
    let mut out = vec![ROOT.to_string()];
    if address == ROOT {
        return out;
    }
    let mut current = String::new();
    for segment in address.split('.') {
        current = if current.is_empty() {
            segment.to_string()
        } else {
            format!("{current}.{segment}")
        };
        out.push(current.clone());
    }
    out
}

/// Whether `child` lies beneath `address`.
pub(crate) fn is_beneath(child: &str, address: &str) -> bool {
    address == ROOT && child != ROOT
        || child.len() > address.len()
            && child.starts_with(address)
            && child.as_bytes()[address.len()] == b'.'
}

/// Refuse a top-level element outside the root scopes (R-3.3).
pub(crate) fn check_scope(address: &str) -> Result<(), Refusal> {
    let scope = address.split('.').next().unwrap_or_default();
    if address == ROOT || ROOT_SCOPES.contains(&scope) {
        return Ok(());
    }
    Err(Refusal::new(
        Code::RootScopeNotAllowed,
        format!(
            "'{address}': the root scope '{scope}' is not one of: {}",
            ROOT_SCOPES.join(", ")
        ),
        None,
    ))
}

/// Checks every name in a command, building the corrected command as it goes.
struct NameCheck {
    problems: Vec<String>,
}

impl NameCheck {
    fn segment(&mut self, segment: &str, address: &str) -> String {
        match segment_problem(segment) {
            None => segment.to_string(),
            Some(why) => {
                self.problems
                    .push(format!("'{address}': '{segment}': {why}"));
                suggest_segment(segment)
            }
        }
    }

    fn address(&mut self, address: &str) -> String {
        if address == ROOT {
            return ROOT.to_string();
        }
        address
            .split('.')
            .map(|segment| self.segment(segment, address))
            .collect::<Vec<_>>()
            .join(".")
    }

    fn fields(&mut self, fields: &JsonMap<String, Value>, address: &str) -> Value {
        let mut out = JsonMap::new();
        for (key, value) in fields {
            let fixed = match value {
                Value::Array(records) if key == "wants" => {
                    Value::Array(records.iter().map(|record| self.want_record(record, address)).collect())
                }
                Value::Object(child) => self.fields(child, &join(address, key)),
                other => other.clone(),
            };
            out.insert(self.segment(key, address), fixed);
        }
        Value::Object(out)
    }

    /// One want record: the address in `element` and each field name are checked.
    fn want_record(&mut self, record: &Value, holder: &str) -> Value {
        let Value::Object(fields) = record else {
            return record.clone();
        };
        Value::Object(
            fields
                .iter()
                .map(|(key, value)| match value {
                    Value::String(provider) if key == "element" => (key.clone(), Value::String(self.address(provider))),
                    _ => (self.segment(key, holder), value.clone()),
                })
                .collect(),
        )
    }
}

/// Refuse a command holding a name that would not survive storage (R-4.11). The remediation is the
/// command with each such name corrected. The command has already passed the input schema.
pub(crate) fn check_command(command: &Value) -> Result<(), Refusal> {
    let Some((verb, body)) = command.as_object().and_then(|object| object.iter().next()) else {
        return Ok(());
    };
    let mut check = NameCheck {
        problems: Vec::new(),
    };
    let fixed_body = match (verb.as_str(), body) {
        ("add" | "update", Value::Object(selected)) => Value::Object(
            selected
                .iter()
                .map(|(address, fields)| {
                    let fixed = match fields {
                        Value::Object(fields) => check.fields(fields, address),
                        other => other.clone(),
                    };
                    (check.address(address), fixed)
                })
                .collect(),
        ),
        ("delete", Value::Object(selected)) => Value::Object(
            selected
                .iter()
                .map(|(address, supplied)| {
                    let mut supplied = supplied.clone();
                    if let Some(Value::Array(wants)) = supplied.get_mut("wants") {
                        for want in wants.iter_mut() {
                            if let Value::String(provider) = want {
                                *provider = check.address(provider);
                            }
                        }
                    }
                    (check.address(address), supplied)
                })
                .collect(),
        ),
        ("goto", Value::String(address)) => Value::String(check.address(address)),
        _ => body.clone(),
    };
    let fixed_verb = match verb.as_str() {
        "add" | "update" | "delete" | "orphaned" | "goto" | "map" | "help" => verb.clone(),
        ROOT => ROOT.to_string(),
        path if path.starts_with('.') => format!(".{}", check.address(&path[1..])),
        address => check.address(address),
    };
    if check.problems.is_empty() {
        return Ok(());
    }
    let mut remediation = JsonMap::new();
    remediation.insert(fixed_verb, fixed_body);
    Err(Refusal::new(
        Code::NameRoundTripFailure,
        check.problems.join("; "),
        Some(Value::Object(remediation)),
    ))
}

/// An address or key in the stored form: every segment in camelCase (R-4.11).
pub fn stored_name(agent_form: &str) -> String {
    map_address(agent_form, to_camel)
}

/// An address or key in the agent's form: every segment in snake_case (R-4.11).
pub fn agent_name(stored_form: &str) -> String {
    map_address(stored_form, to_snake)
}
