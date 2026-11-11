//! The shape of a command, checked by hand before the schema check (R-5.24).
//!
//! `check` refuses a command that does not have the form the `project-map` tool takes. It reads
//! only the command, never the map. Each message names a place the way an agent writes it:
//! `'code.engine.game'`, `status at 'code.engine.game'`, `the want 'code.bus.data.event' at
//! 'code.engine.game'`. The schema check in `contract.rs` stays after this check as a backstop.
//!
//! The Python and TypeScript forms port this module line for line. Nothing here depends on a
//! schema validator.
//!
//! # Order of checks
//!
//! A command can have several problems. `check` reports the first one it finds, in this order:
//!
//! 1. The number of entries: a command is an object with one entry.
//! 2. The command name: `add`, `update`, `delete`, `orphaned`, `goto`, `map` and `help` are commands. A
//!    key that starts with a period is a raw dump. Any other key is an address to read.
//! 3. The address. For `add`, `update` and `delete` the body must first be an object with one
//!    entry, because that entry's key is the address.
//! 4. The shape of the value at the address.
//! 5. Each field, in the order the command gives them. An object value is an element beneath;
//!    its fields are checked, in order, before the next field of the element above.
//!
//! In a want record the order is: the record is an object, the names it does not take, each field
//! in the command's order, then the fields that are missing. In `delete`, the items of `wants` are
//! checked in the command's order; for each item: it is text, it is not the root, it is an
//! address, it is not a repeat.
//!
//! # Inventory
//!
//! Every rule that `metaform/mcp-tools.proposed.json` and `metaform/metaform.schema.json` enforce
//! on a command. `tests/shape.rs` names the rule each of its rows tests.
//!
//! | Rule | What must be true |
//! | ---- | ----------------- |
//! | C1 | A command is an object with exactly one entry. |
//! | C2 | The key is a command name, a raw dump path or an address. |
//! | A1 | The body of `add` and of `update` is an object with exactly one entry. |
//! | A2 | Its key is `.` or an address. |
//! | A3 | Its value is an object with at least one field. |
//! | D1 | The body of `delete` is an object with exactly one entry. |
//! | D2 | Its key is an address, and not `.`. |
//! | D3 | Its value is `{}` or `{"wants": [...]}` with no other entry. |
//! | D4 | `wants` in `delete` is a list with at least one item. |
//! | D5 | Each item is an address, not `.`, and no item repeats. |
//! | E1 | `map` and `orphaned` take `{}`. |
//! | H1 | `help` takes `{}` or text that is not empty. `Contract::help` refuses a name it does not hold. |
//! | G1 | `goto` takes text that is `.` or an address. |
//! | R1 | A raw dump path is a period alone, or a period and an address. |
//! | R2 | A raw dump takes `{}`. |
//! | L1 | A read's key is an address. |
//! | L2 | A read's body is an object. |
//! | L3 | Each layer name in a read is one segment. |
//! | L4 | Each layer name in a read has `{}` as its value. |
//! | N1 | Every field name is one segment. |
//! | N2 | `technical_name`, `name` and `project` hold text that is not blank, an object or a list. |
//! | N3 | `role` holds text, an object or a list. This check also refuses blank text. |
//! | N4 | `status` follows N2 and is not `missing`, `MISSING`, `BKN`, `broken`, `todo` or `TODO`. |
//! | N5 | `uri` holds text that is not blank, or an object. |
//! | N6 | `why`, `how`, `direction`, `op`, `ef` and `ifd` at an element hold an object or a list. |
//! | N7 | `providers` holds an object. |
//! | N8 | `null` is taken by the fields of `update`'s own element, and by a field N2 to N7 do not name. |
//! | N9 | An object value is an element beneath, and N1 to N10 hold for it. |
//! | N10 | `wants` beneath the command's own element holds want records (W1 to W6) or elements beneath. |
//! | W1 | `wants` at the command's own element is an object keyed by address, and not by `.`. |
//! | W2 | A want record is an object. |
//! | W3 | A want record takes only `why`, `how` and `direction`. |
//! | W4 | `why` and `how` hold text that is not blank. |
//! | W5 | `direction` is `inbound`, `outbound` or `two-way`. |
//! | W6 | A want record outside `update`'s own element has all three fields (WANT_INCOMPLETE). |
//! | W7 | A want record at `update`'s own element has at least one field. |
//! | W8 | `wants` at the command's own element holds at least one want record. |

use serde_json::{Map as JsonMap, Value, json};

use crate::names::{self, ROOT};
use crate::refusal::{Code, Refusal};

const ONE_ENTRY: &str = "a command has one entry: add, update, delete, orphaned, goto, map, help, an address to read, or a path that starts with a period for a raw dump";
pub(crate) const HELP_FORM: &str = "help takes {}, the name of a command, or the name of a definition a schema refers to";
/// The command names `help` takes, in the order `{"help": {}}` lists them.
pub(crate) const HELP_NAMES: [&str; 9] =
    ["add", "update", "delete", "orphaned", "goto", "map", "addressed read", "raw dump", "help"];
const DELETE_FORM: &str = "delete takes {} to delete the element, or {\"wants\": [\"<address>\"]} to remove wants";
/// The fields that hold text (N2 to N5).
const TEXT_FIELDS: [&str; 6] = ["technical_name", "name", "role", "status", "project", "uri"];
/// The words that belong to a want, not to an element (N6). `op`, `ef` and `ifd` are older names.
const WANT_WORDS: [&str; 6] = ["why", "how", "direction", "op", "ef", "ifd"];
const WANT_FIELDS: [&str; 3] = ["why", "how", "direction"];
const DIRECTIONS: [&str; 3] = ["inbound", "outbound", "two-way"];
const LEGACY_STATUS: [&str; 6] = ["missing", "MISSING", "BKN", "broken", "todo", "TODO"];

/// Where a set of fields sits in the command.
#[derive(Clone, Copy, PartialEq)]
enum Level {
    /// The fields of the element that `add` names.
    Add,
    /// The fields of the element that `update` names.
    Update,
    /// The fields of an element beneath, written as an object value.
    Beneath,
}

/// Refuse a command that does not have the form the tool takes. See the module text for the order.
pub(crate) fn check(command: &Value) -> Result<(), Refusal> {
    let Some((key, body)) = one_entry(command) else {
        return Err(refuse(ONE_ENTRY, None));
    };
    let check = Check { command };
    match key {
        "map" | "orphaned" if is_empty_object(body) => Ok(()),
        "help" if is_empty_object(body) || body.as_str().is_some_and(|name| !name.is_empty()) => Ok(()),
        "help" => Err(refuse(HELP_FORM, Some(json!({"help": {}})))),
        "map" | "orphaned" => Err(refuse(format!("{key} takes {{}}"), Some(json!({key: {}})))),
        "goto" => match body.as_str() {
            Some(text) if text == ROOT || is_address(text) => Ok(()),
            Some(text) if !text.is_empty() => Err(not_an_address(text)),
            _ => Err(refuse(
                "goto takes one address, such as {\"goto\": \"code.engine.game\"}",
                Some(json!({"goto": "<address>"})),
            )),
        },
        "add" | "update" | "delete" => {
            let Some((address, value)) = one_entry(body) else {
                let first = body.as_object().and_then(|entries| entries.iter().next());
                return Err(refuse(
                    format!("{key} takes one address; send one command for each element"),
                    first.and_then(|(address, value)| accepted(json!({key: {address: value}}))),
                ));
            };
            if key == "delete" {
                return delete(address, value);
            }
            if address != ROOT && !is_address(address) {
                return Err(not_an_address(address));
            }
            let Some(fields) = value.as_object() else {
                return Err(refuse(format!("{key} takes an object of fields at '{address}'"), None));
            };
            if fields.is_empty() {
                return Err(refuse(format!("{key} needs at least one field at '{address}'"), None));
            }
            let level = if key == "add" { Level::Add } else { Level::Update };
            check.fields(fields, address, &[key, address], level)
        }
        path if path.starts_with('.') => {
            if path != ROOT && !is_address(&path[1..]) {
                return Err(not_an_address(path));
            }
            if !is_empty_object(body) {
                return Err(refuse("a raw dump takes {}", Some(json!({path: {}}))));
            }
            Ok(())
        }
        address => read(address, body),
    }
}

/// The command being checked. A remediation is this command with one value corrected.
struct Check<'a> {
    command: &'a Value,
}

impl Check<'_> {
    /// The fields of one element (N1 to N10). `path` is the keys from the command to these fields.
    fn fields(&self, fields: &JsonMap<String, Value>, address: &str, path: &[&str], level: Level) -> Result<(), Refusal> {
        for (key, value) in fields {
            if !is_segment(key) {
                return Err(refuse(
                    format!("'{key}' at '{address}' is not a field name: a name is one segment, with no periods, spaces, '$', '[' or ']'"),
                    None,
                ));
            }
            let here = [path, &[key.as_str()]].concat();
            if key == "wants" {
                self.wants(value, address, &here, level)?;
                continue;
            }
            match value {
                Value::Object(beneath) => self.fields(beneath, &names::join(address, key), &here, Level::Beneath)?,
                Value::Null if level == Level::Update => {}
                Value::Array(_) if key != "uri" && key != "providers" => {}
                _ if TEXT_FIELDS.contains(&key.as_str()) => self.text(key, value, address, &here)?,
                _ if WANT_WORDS.contains(&key.as_str()) => {
                    let mut record = want_placeholder();
                    if let (true, Some(text)) = (WANT_FIELDS.contains(&key.as_str()), value.as_str()) {
                        record[key.as_str()] = json!(text);
                    }
                    return Err(refuse(
                        format!("{key} at '{address}' is not a field of an element; why, how and direction belong in a want"),
                        Some(json!({"update": {address: {"wants": {"<address>": record}}}})),
                    ));
                }
                _ if key == "providers" => {
                    return Err(refuse(
                        format!("providers at '{address}' can hold only elements beneath it; wants holds what an element wants"),
                        None,
                    ));
                }
                _ => {}
            }
        }
        Ok(())
    }

    /// A value that is not an object, a list or an accepted `null`, at a field that holds text.
    fn text(&self, key: &str, value: &Value, address: &str, path: &[&str]) -> Result<(), Refusal> {
        match value.as_str().filter(|text| !is_blank(text)) {
            Some(text) if key == "status" && LEGACY_STATUS.contains(&text) => Err(refuse(
                format!("status at '{address}' cannot be \"{text}\"; use un_built for functionality that is not built"),
                accepted(replaced(self.command, path, Some(json!("un_built")))),
            )),
            Some(_) => Ok(()),
            None => {
                let placeholder = if key == "role" {
                    "<Definitive, Supportive, Notable or Divergent>".to_string()
                } else {
                    format!("<{key}>")
                };
                Err(refuse(
                    format!("{key} at '{address}' must be text that is not blank"),
                    Some(replaced(self.command, path, Some(json!(placeholder)))),
                ))
            }
        }
    }

    /// The value of `wants` at an element (W1, N10).
    fn wants(&self, value: &Value, holder: &str, path: &[&str], level: Level) -> Result<(), Refusal> {
        let Some(wants) = value.as_object() else {
            return Err(refuse(
                format!("wants at '{holder}' must be an object of want records keyed by address"),
                Some(replaced(self.command, path, Some(json!({"<address>": want_placeholder()})))),
            ));
        };
        // Beneath the command's own element, `wants` may also be a branch of elements. It holds
        // want records when a value in it gives why, how or direction as a plain value.
        let holds_records = wants.values().any(|record| {
            WANT_FIELDS
                .iter()
                .any(|field| record.get(field).is_some_and(|v| !v.is_object() && !v.is_array()))
        });
        if level == Level::Beneath && !holds_records {
            return self.fields(wants, &names::join(holder, "wants"), path, Level::Beneath);
        }
        if wants.is_empty() {
            // W8: an empty `wants` would be read as an element named "wants" beneath the holder.
            return Err(refuse(
                format!("wants at '{holder}' holds no want record"),
                Some(replaced(self.command, path, Some(json!({"<address>": want_placeholder()})))),
            ));
        }
        for (other, record) in wants {
            if other == ROOT {
                return Err(refuse("the root cannot be wanted", None));
            }
            if !is_address(other) {
                return Err(not_an_address(other));
            }
            let here = [path, &[other.as_str()]].concat();
            self.want(record, other, holder, &here, level == Level::Update)?;
        }
        Ok(())
    }

    /// One want record (W2 to W7). `partial` is true at `update`'s own element, where a record
    /// holds only the fields to adjust.
    fn want(&self, record: &Value, other: &str, holder: &str, path: &[&str], partial: bool) -> Result<(), Refusal> {
        let place = format!("the want '{other}' at '{holder}'");
        let Some(fields) = record.as_object() else {
            return Err(refuse(
                format!("{place} must be a record with why, how and direction"),
                Some(replaced(self.command, path, Some(want_placeholder()))),
            ));
        };
        let extra: Vec<&str> = fields
            .keys()
            .map(String::as_str)
            .filter(|name| !WANT_FIELDS.contains(name))
            .collect();
        if !extra.is_empty() {
            let mut fixed = self.command.clone();
            for name in &extra {
                fixed = replaced(&fixed, &[path, &[*name]].concat(), None);
            }
            return Err(refuse(format!("{place} does not take: {}", extra.join(", ")), accepted(fixed)));
        }
        for (field, value) in fields {
            let here = [path, &[field.as_str()]].concat();
            if field == "direction" {
                if !value.as_str().is_some_and(|direction| DIRECTIONS.contains(&direction)) {
                    return Err(refuse(
                        format!("direction at {place} must be inbound, outbound or two-way"),
                        Some(replaced(self.command, &here, Some(json!("<inbound, outbound or two-way>")))),
                    ));
                }
            } else if !value.as_str().is_some_and(|text| !is_blank(text)) {
                return Err(refuse(
                    format!("{field} at {place} must be text that is not blank"),
                    Some(replaced(self.command, &here, Some(json!(format!("<{field}>"))))),
                ));
            }
        }
        let missing: Vec<&str> = WANT_FIELDS
            .into_iter()
            .filter(|field| !fields.contains_key(*field))
            .collect();
        if partial && fields.is_empty() {
            return Err(refuse(
                format!("{place} has no fields; give why, how or direction"),
                Some(replaced(self.command, path, Some(want_placeholder()))),
            ));
        }
        if !partial && !missing.is_empty() {
            // The same code and message as a want that an update leaves incomplete (R-5.6).
            let mut fixed = self.command.clone();
            for field in &missing {
                fixed = replaced(&fixed, &[path, &[*field]].concat(), Some(json!(format!("<{field}>"))));
            }
            return Err(Refusal::new(
                Code::WantIncomplete,
                format!("'{holder}' wants '{other}': the want has no {}", missing.join(", ")),
                Some(fixed),
            ));
        }
        Ok(())
    }
}

/// `delete` (D2 to D5).
fn delete(address: &str, value: &Value) -> Result<(), Refusal> {
    if address == ROOT {
        return Err(refuse("the root cannot be deleted", None));
    }
    if !is_address(address) {
        return Err(not_an_address(address));
    }
    let Some(fields) = value.as_object() else {
        return Err(refuse(DELETE_FORM, None));
    };
    if fields.is_empty() {
        return Ok(());
    }
    let (Some(wants), 1) = (fields.get("wants"), fields.len()) else {
        return Err(refuse(DELETE_FORM, None));
    };
    let remove = |wants: Vec<&str>| json!({"delete": {address: {"wants": wants}}});
    let items = match wants {
        Value::Array(items) if !items.is_empty() => items,
        Value::String(one) if is_address(one) => return Err(refuse(DELETE_FORM, Some(remove(vec![one])))),
        _ => return Err(refuse(DELETE_FORM, Some(remove(vec!["<address>"])))),
    };
    let mut seen: Vec<&str> = Vec::new();
    for item in items {
        let Some(text) = item.as_str() else {
            return Err(refuse(DELETE_FORM, Some(remove(vec!["<address>"]))));
        };
        if text == ROOT {
            return Err(refuse("the root cannot be wanted", None));
        }
        if !is_address(text) {
            return Err(not_an_address(text));
        }
        if seen.contains(&text) {
            let mut once: Vec<&str> = Vec::new();
            for other in items.iter().filter_map(Value::as_str) {
                if !once.contains(&other) {
                    once.push(other);
                }
            }
            return Err(refuse(
                format!("delete names the want '{text}' more than once"),
                accepted(remove(once)),
            ));
        }
        seen.push(text);
    }
    Ok(())
}

/// An addressed read (L1 to L4).
fn read(address: &str, body: &Value) -> Result<(), Refusal> {
    if !is_address(address) {
        return Err(not_an_address(address));
    }
    let form = format!(
        "a read names each layer with {{}} as its value, such as {{\"{address}\": {{\"wants\": {{}}}}}}"
    );
    let Some(layers) = body.as_object() else {
        return Err(refuse(form, Some(json!({address: {}}))));
    };
    for (name, value) in layers {
        if !is_segment(name) {
            return Err(refuse(
                format!("'{name}' is not a layer name: a layer name is one segment, with no periods, spaces, '$', '[' or ']'"),
                None,
            ));
        }
        if !is_empty_object(value) {
            let named: JsonMap<String, Value> = layers.keys().map(|name| (name.clone(), json!({}))).collect();
            return Err(refuse(form, accepted(json!({address: named}))));
        }
    }
    Ok(())
}

fn refuse(message: impl Into<String>, remediation: Option<Value>) -> Refusal {
    Refusal::new(Code::FieldMismatch, message, remediation)
}

fn not_an_address(text: &str) -> Refusal {
    refuse(
        format!("'{text}' is not an address: segments are joined by periods, with no spaces, '$', '[' or ']'"),
        None,
    )
}

/// A corrected command, if this check accepts it. A remediation must not be refused in turn.
fn accepted(command: Value) -> Option<Value> {
    check(&command).is_ok().then_some(command)
}

/// A want record with a placeholder for each value only the agent can supply.
fn want_placeholder() -> Value {
    json!({"why": "<why>", "how": "<how>", "direction": "<direction>"})
}

/// The single entry of an object, or `None` if the value is not an object with one entry.
fn one_entry(value: &Value) -> Option<(&str, &Value)> {
    let entries = value.as_object().filter(|entries| entries.len() == 1)?;
    entries.iter().next().map(|(key, value)| (key.as_str(), value))
}

fn is_empty_object(value: &Value) -> bool {
    value.as_object().is_some_and(JsonMap::is_empty)
}

/// The command with the value at `path` replaced, or removed when `value` is `None`. Every key
/// of `path` but the last names an object in the command.
fn replaced(command: &Value, path: &[&str], value: Option<Value>) -> Value {
    let mut out = command.clone();
    let Some((last, above)) = path.split_last() else {
        return out;
    };
    let mut at = &mut out;
    for key in above {
        at = &mut at[*key];
    }
    if let Some(object) = at.as_object_mut() {
        match value {
            Some(value) => {
                object.insert((*last).to_string(), value);
            }
            None => {
                object.shift_remove(*last);
            }
        }
    }
    out
}

/// One address segment: at least one character, and no period, `$`, `[`, `]` or space.
fn is_segment(text: &str) -> bool {
    !text.is_empty() && !text.chars().any(|c| matches!(c, '.' | '$' | '[' | ']') || is_space(c))
}

/// An address beneath the root: segments joined by periods. The root `.` is not one.
fn is_address(text: &str) -> bool {
    text.split('.').all(is_segment)
}

fn is_blank(text: &str) -> bool {
    text.chars().all(is_space)
}

/// The characters with the Unicode property White_Space, which the schemas' `\s` matches. They
/// are listed so that every form of Metaform uses the same set.
fn is_space(c: char) -> bool {
    matches!(
        c,
        '\u{9}'..='\u{d}'
            | ' '
            | '\u{85}'
            | '\u{a0}'
            | '\u{1680}'
            | '\u{2000}'..='\u{200a}'
            | '\u{2028}'
            | '\u{2029}'
            | '\u{202f}'
            | '\u{205f}'
            | '\u{3000}'
    )
}
