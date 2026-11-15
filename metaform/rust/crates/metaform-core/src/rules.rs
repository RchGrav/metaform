//! Rules on an element's intake fields that need the map (R-3.11 to R-3.13), and the rule that a
//! layer's value is a list (R-6.24). `commands` applies them to every element a write touched.

use serde_json::{Map as JsonMap, Value, json};

use crate::model::{Element, Map};
use crate::names::{self, ROOT};
use crate::refusal::{Code, Refusal};
use crate::specification;

/// The roles, spelled as a write must spell them (founder, 2026-11-15: a role is written by its
/// full name). A Coupled Element is a Supporting Element whose functionality cannot be changed
/// apart from the elements that want it, so work on it and work on them is not assigned to
/// different worktrees at the same time.
pub const ROLES: [&str; 8] = [
    "Artifact Type",
    "Defining Element",
    "Supporting Element",
    "Coupled Element",
    "Notable Element",
    "Cestui Que Use",
    "Upstream Dependency",
    "Downstream Dependant",
];

/// The role that names what an artifact is. `map` lists the project's elements that hold it.
pub const DEFINING: &str = "Defining Element";

/// What a refusal puts in place of a role that it cannot correct.
pub(crate) const ROLE_PLACEHOLDER: &str = "<Artifact Type, Defining Element, Supporting Element, Coupled Element, Notable Element, Cestui Que Use, Upstream Dependency or Downstream Dependant>";

/// The intake procedure's abbreviations of the roles, each with the role it means. A write that uses
/// one is refused with the same write using the role's name, because an agent that follows the
/// procedure exactly must be given the right command. The store uses the abbreviations to bring
/// a map stored before 2026-11-15 up to date.
pub const ROLE_WORDS: [(&str, &str); 8] = [
    ("AT", "Artifact Type"),
    ("DE", "Defining Element"),
    ("SE", "Supporting Element"),
    ("CE", "Coupled Element"),
    ("NE", "Notable Element"),
    ("CQU", "Cestui Que Use"),
    ("UD", "Upstream Dependency"),
    ("DD", "Downstream Dependant"),
];

/// Check one touched element: `technical_name` (R-3.11), then `role` (R-3.13). `before` is the
/// map before the write.
///
/// R-3.12 (`name` must not equal `technical_name`) is not checked. The intake procedure lets
/// `name` be the standard term when the project has no name of its own for the element. Four
/// test intakes (2026-11-09) were refused there, and each agent then invented a name, which the
/// procedure forbids. The conflict between R-3.12 and the procedure is the owner's to settle
/// (`SPEC.md` D-19).
pub(crate) fn check(before: &Map, address: &str, element: &Element) -> Result<(), Refusal> {
    check_technical_name(before, address, element)?;
    check_role(before, address, element)?;
    check_system_layers(before, address, element)
}

/// A system layer (`skills`, `memory`, `sources`) holds a list of records (R-6.15). A value this
/// write set that is not a list is refused, with the value as one record in the remediation.
fn check_system_layers(before: &Map, address: &str, element: &Element) -> Result<(), Refusal> {
    for layer in specification::SYSTEM_LAYERS {
        let Some(value) = element.fields.get(layer) else {
            continue;
        };
        let stored = before.element(address).and_then(|e| e.fields.get(layer));
        if !value.is_array() && stored != Some(value) {
            return Err(specification::not_a_list("update", layer, address, value));
        }
    }
    Ok(())
}

/// The command that corrects one field. An element this write created is added again with the
/// field corrected, because the refused write stored nothing; an existing one is updated.
fn correction(before: &Map, address: &str, element: &Element, field: &str, value: &str) -> Value {
    if before.element(address).is_some() {
        json!({"update": {address: {field: value}}})
    } else {
        let mut view = element.view();
        view[field] = Value::String(value.to_string());
        json!({"add": {address: view}})
    }
}

/// `technical_name` is the same number of leading words of the reversed, space-separated
/// address (R-3.11). The root is the project: it has no address words and no `technical_name`.
fn check_technical_name(before: &Map, address: &str, element: &Element) -> Result<(), Refusal> {
    let Some(technical) = element.fields.get("technical_name").and_then(Value::as_str) else {
        return Ok(());
    };
    if address == ROOT {
        return Err(Refusal::new(
            Code::TechnicalNameAlignmentFailure,
            "'.': the root is the project and has no technical_name",
            Some(json!({"update": {ROOT: {"technical_name": null}}})),
        ));
    }
    let reversed: Vec<&str> = address.split('.').rev().flat_map(|segment| segment.split('_')).collect();
    let words: Vec<&str> = technical.split_whitespace().collect();
    if !words.is_empty() && words.len() <= reversed.len() && words.iter().zip(&reversed).all(|(w, r)| w == r) {
        return Ok(());
    }
    // The suggestion is the reversed address without its root scope words: `code.cache.response`
    // gives "response cache".
    let root_words = address.split('.').next().map_or(0, |root| root.split('_').count());
    let keep = reversed.len().saturating_sub(root_words).max(1);
    let suggested = reversed[..keep.min(reversed.len())].join(" ");
    Err(Refusal::new(
        Code::TechnicalNameAlignmentFailure,
        format!(
            "'{address}': technical_name \"{technical}\" is not the leading words of \"{}\"",
            reversed.join(" ")
        ),
        Some(correction(before, address, element, "technical_name", &suggested)),
    ))
}

/// A write that sets or changes `role` must set one of `ROLES` (R-3.13). A role the write
/// did not change is not checked, so a stored map with older role names (`Definitive`,
/// `Supportive`, `Notable`, `Divergent`) still accepts unrelated writes. A role written in one
/// of the procedure's words is refused with the write that uses the role's name.
fn check_role(before: &Map, address: &str, element: &Element) -> Result<(), Refusal> {
    let Some(role) = element.fields.get("role").and_then(Value::as_str) else {
        return Ok(());
    };
    let stored = before.element(address).and_then(|e| e.fields.get("role")).and_then(Value::as_str);
    if stored == Some(role) || ROLES.contains(&role) {
        return Ok(());
    }
    let meant = ROLE_WORDS.iter().find(|(word, _)| *word == role).map_or(ROLE_PLACEHOLDER, |(_, name)| *name);
    Err(Refusal::new(
        Code::RoleTaxonomyFailure,
        format!("'{address}': role \"{role}\" is not one of: {}", ROLES.join(", ")),
        Some(correction(before, address, element, "role", meant)),
    ))
}

/// Refuse an object written where an element holds a layer's records (R-6.24). An object there
/// would become an element beneath, which cannot share its name with the layer's field; the
/// records stay, and the remediation gives the object as one record. `verb` is `add` or `update`,
/// `address` the element the command names, `fields` what the command supplies for it, and
/// `map` the map before the write.
pub(crate) fn check_layer_values(map: &Map, verb: &str, address: &str, fields: &JsonMap<String, Value>) -> Result<(), Refusal> {
    let defined = specification::definitions(map);
    let is_layer = |name: &str| {
        specification::SYSTEM_LAYERS.contains(&name) || defined.iter().any(|d| d.layer == name)
    };
    layer_values(map, &is_layer, verb, address, fields)
}

fn layer_values(map: &Map, is_layer: &dyn Fn(&str) -> bool, verb: &str, address: &str, fields: &JsonMap<String, Value>) -> Result<(), Refusal> {
    for (key, value) in fields {
        let Value::Object(beneath) = value else {
            continue;
        };
        let holds_records = map
            .element(address)
            .is_some_and(|element| element.fields.get(key).is_some_and(Value::is_array));
        if holds_records && is_layer(key) {
            return Err(specification::not_a_list(verb, key, address, value));
        }
        layer_values(map, is_layer, verb, &names::join(address, key), beneath)?;
    }
    Ok(())
}
