//! Rules on an element's intake fields that need the map (R-3.11 to R-3.13), and the rule that a
//! layer's value is a list (R-6.24). `commands` applies them to every element a write touched.

use serde_json::{Map as JsonMap, Value, json};

use crate::model::{Element, Map};
use crate::names::{self, ROOT};
use crate::refusal::{Code, Refusal};
use crate::specification;

/// The four roles (R-3.13), spelled as a write must spell them.
pub const ROLES: [&str; 4] = ["Definitive", "Supportive", "Notable", "Divergent"];

/// Check one touched element: `technical_name` (R-3.11), then `name` (R-3.12), then `role`
/// (R-3.13). `before` is the map before the write.
pub(crate) fn check(before: &Map, address: &str, element: &Element) -> Result<(), Refusal> {
    check_technical_name(before, address, element)?;
    check_name(before, address, element)?;
    check_role(before, address, element)
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

/// `name` is the project's own name for the element, so it must not equal `technical_name`
/// (R-3.12). The two are compared trimmed, ignoring case.
fn check_name(before: &Map, address: &str, element: &Element) -> Result<(), Refusal> {
    let text = |field: &str| element.fields.get(field).and_then(Value::as_str);
    let (Some(name), Some(technical)) = (text("name"), text("technical_name")) else {
        return Ok(());
    };
    if name.trim().to_lowercase() != technical.trim().to_lowercase() {
        return Ok(());
    }
    Err(Refusal::new(
        Code::CanonicalNameCollisionFailure,
        format!("'{address}': name \"{name}\" is the same as technical_name; name is the project's own name for the element"),
        Some(correction(before, address, element, "name", "<the project's own name for it>")),
    ))
}

/// A write that sets or changes `role` must set one of the four roles (R-3.13). A role the write
/// did not change is not checked, so a stored map with older role names (`DE`, `SE`, `NE`, `CQU`)
/// still accepts unrelated writes.
fn check_role(before: &Map, address: &str, element: &Element) -> Result<(), Refusal> {
    let Some(role) = element.fields.get("role").and_then(Value::as_str) else {
        return Ok(());
    };
    let stored = before.element(address).and_then(|e| e.fields.get("role")).and_then(Value::as_str);
    if stored == Some(role) || ROLES.contains(&role) {
        return Ok(());
    }
    Err(Refusal::new(
        Code::RoleTaxonomyFailure,
        format!("'{address}': role \"{role}\" is not one of: {}", ROLES.join(", ")),
        Some(correction(before, address, element, "role", "<Definitive, Supportive, Notable or Divergent>")),
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
