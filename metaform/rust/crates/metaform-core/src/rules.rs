//! Rules on an element's intake fields that need the map (R-3.11 to R-3.13), and the rule that a
//! layer's value is a list (R-6.24). `commands` applies them to every element a write touched.
//! The grammar of a want's `why` and `how` (R-3.17, R-6.17) is checked here too, for the parts
//! a write sets.

use std::collections::BTreeMap;

use serde_json::{Map as JsonMap, Value, json};

use crate::model::{Element, Map};
use crate::names::{self, ROOT};
use crate::refusal::{Code, Refusal};
use crate::specification;

/// The four roles (R-3.13), spelled as a write must spell them.
pub const ROLES: [&str; 4] = ["Definitive", "Supportive", "Notable", "Divergent"];

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

/// The message of every grammar refusal. It is the only place an agent learns the rule, so it
/// states the whole rule and is the same in every form of Metaform.
pub const GRAMMAR_MESSAGE: &str = "why is one fragment that starts with a base verb; how is one fragment that starts with a verb ending in -s. No leading 'to', no subject, no '-ing' verb, no values. Detail belongs in a knowledge layer.";

/// The text an agent must replace in the remediation of a grammar refusal.
const WHY_PLACEHOLDER: &str = "<base verb phrase, as: drain raw frames from the network interface card>";
const HOW_PLACEHOLDER: &str = "<verb phrase ending in -s, as: holds descriptor pointers across contiguous memory segments>";

/// Base verbs that end in `ing`. A `why` may start with one; any other first word that ends in
/// `ing` is taken as an `-ing` verb form.
const ING_BASE_VERBS: [&str; 14] = [
    "bring", "cling", "ding", "fling", "ping", "ring", "sing", "sling", "spring", "sting", "string", "swing",
    "wring", "zing",
];

/// First words that make the text a clause with a subject, not a verb phrase.
const SUBJECT_WORDS: [&str; 13] = [
    "the", "a", "an", "this", "that", "these", "those", "it", "its", "we", "they", "each", "every",
];

/// The first word of the text: the characters before the first white space, with A to Z lowered
/// and any trailing `.,;:!?` removed.
fn first_word(text: &str) -> String {
    let word = text.trim().split(char::is_whitespace).next().unwrap_or_default();
    word.to_ascii_lowercase().trim_end_matches(['.', ',', ';', ':', '!', '?']).to_string()
}

/// Whether the text holds more than one fragment: `.`, `!`, `?` or `;` followed by white space
/// and then more text. One trailing full stop is not a second fragment.
fn has_many_fragments(text: &str) -> bool {
    let characters: Vec<char> = text.trim().chars().collect();
    characters.windows(2).any(|pair| matches!(pair[0], '.' | '!' | '?' | ';') && pair[1].is_whitespace())
}

/// A letter, for the number rule: A to Z in either case, or any character outside ASCII. The
/// three forms of Metaform use this one definition, so they decide the same.
fn is_letter(character: char) -> bool {
    character.is_ascii_alphabetic() || !character.is_ascii()
}

/// Whether the text holds a number that stands alone: a run of digits 0 to 9, with an optional
/// decimal part, that is not part of a word. The run is part of a word when a letter follows it
/// directly, or when a letter directly precedes it or precedes the digits, `/`, `-` and `_` that
/// join it to the word. `S256`, `OAuth2`, `utf-8`, `HTTP/2` and `x86-64` are words; `5` and `3.9`
/// stand alone. A want states what happens without tunable values (R-3.17).
fn has_lone_number(text: &str) -> bool {
    let characters: Vec<char> = text.chars().collect();
    let digit = |at: usize| characters.get(at).is_some_and(char::is_ascii_digit);
    let mut at = 0;
    while at < characters.len() {
        if !digit(at) {
            at += 1;
            continue;
        }
        let start = at;
        while digit(at) {
            at += 1;
        }
        if characters.get(at) == Some(&'.') && digit(at + 1) {
            at += 1;
            while digit(at) {
                at += 1;
            }
        }
        let letter_after = characters.get(at).is_some_and(|c| is_letter(*c));
        let mut word_start = start;
        while word_start > 0
            && (characters[word_start - 1].is_ascii_digit() || matches!(characters[word_start - 1], '/' | '-' | '_'))
        {
            word_start -= 1;
        }
        let letter_before = word_start > 0 && is_letter(characters[word_start - 1]);
        if !letter_after && !letter_before {
            return true;
        }
    }
    false
}

/// Whether a `why` or a `how` breaks the grammar of its field (R-3.17, R-6.17). `field` is `why`
/// or `how`. The case of the first letter, one trailing full stop, length, and words ending in
/// `-ing` after the first word are not checked (`SPEC.md` D-14).
pub fn breaks_grammar(field: &str, text: &str) -> bool {
    let first = first_word(text);
    let verb_form = if field == "why" {
        first == "to" || (first.ends_with("ing") && !ING_BASE_VERBS.contains(&first.as_str()))
    } else {
        !first.ends_with('s')
    };
    verb_form || SUBJECT_WORDS.contains(&first.as_str()) || has_many_fragments(text) || has_lone_number(text)
}

/// Check the `why` and `how` that a command wrote in one want. `written` names the parts the
/// command wrote; a part it did not write is not checked, so a stored want with older text
/// still accepts an unrelated write. `elements` is the map as the command would leave it.
///
/// The refusal follows the documentation set, module 6.4. The tested sentence is the wants
/// sentence of R-6.17 with the texts as written, without their trailing full stop. The
/// remediation updates the want with a placeholder in each part that broke the rule. For a want
/// that `before` holds, it has only those parts. For a want this command made, it has the whole
/// want, because the refused command stored nothing and a want needs all of its fields (R-5.6).
pub(crate) fn check_want_grammar(
    before: &Map,
    elements: &BTreeMap<String, Element>,
    holder: &str,
    other: &str,
    written: &[&'static str],
) -> Result<(), Refusal> {
    let Some(record) = elements.get(holder).and_then(|element| element.wants.get(other)) else {
        return Ok(());
    };
    let text = |key: &str| record.get(key).and_then(Value::as_str).unwrap_or_default();
    let mut broken = JsonMap::new();
    for (key, placeholder) in [("why", WHY_PLACEHOLDER), ("how", HOW_PLACEHOLDER)] {
        if written.contains(&key) && !text(key).trim().is_empty() && breaks_grammar(key, text(key)) {
            broken.insert(key.to_string(), json!(placeholder));
        }
    }
    if broken.is_empty() {
        return Ok(());
    }
    let stored = before.element(holder).is_some_and(|element| element.wants.contains_key(other));
    let parts = if stored {
        broken
    } else {
        let mut whole = record.clone();
        whole.extend(broken);
        whole
    };
    let named = |address: &str| {
        let name = elements.get(address).and_then(|element| element.fields.get("name")).and_then(Value::as_str);
        match name {
            Some(name) if !name.trim().is_empty() => format!("{address} ({name})"),
            _ => address.to_string(),
        }
    };
    let part = |key: &str| text(key).trim().trim_end_matches('.').to_string();
    let mut refusal = Refusal::new(
        Code::GrammarConstraintViolation,
        GRAMMAR_MESSAGE,
        Some(json!({"update": {holder: {"wants": {other: parts}}}})),
    );
    refusal.sentence = Some(format!(
        "{} requires {} in order to {}, which {}.",
        named(holder),
        named(other),
        part("why"),
        part("how")
    ));
    Err(refusal)
}

#[cfg(test)]
mod tests {
    use super::breaks_grammar;

    #[test]
    fn a_why_starts_with_a_base_verb() {
        for text in [
            "Receive player input and collision telemetry for frame simulation.",
            "drain raw frames from the network interface card",
            "String the tokens into one line",
            "ping the peer",
            "Verify the S256 challenge of OAuth2 over HTTP/2 as utf-8 on x86-64",
        ] {
            assert!(!breaks_grammar("why", text), "{text}");
        }
        for text in [
            "to drain raw frames",
            "To: drain raw frames",
            "draining raw frames",
            "Parsing, then storing",
            "The router needs parameters",
            "it needs parameters",
            "keep frames. Store them on disk",
            "keep frames; store them on disk",
            "keep frames!\nstore them",
            "score answers from 0 to 5",
            "wait 3.9 seconds",
            "retry 5",
            "list items 1-5",
        ] {
            assert!(breaks_grammar("why", text), "{text}");
        }
    }

    #[test]
    fn a_how_starts_with_a_verb_ending_in_s() {
        for text in [
            "Dispatches subscribed runtime event streams.",
            "holds descriptor pointers across contiguous memory segments",
            "  Stores: frames on disk  ",
            "Verifies S256 challenges for OAuth2 clients.",
            "passes checking results on",
        ] {
            assert!(!breaks_grammar("how", text), "{text}");
        }
        for text in [
            "holding descriptor pointers",
            "hold descriptor pointers",
            "The router stores parameters.",
            "this stores parameters",
            "its parameters are stored",
            "Stores parameters. Decodes them first.",
            "Returns yes/no confidences and 0 to 5 scores from the JEV model.",
            "...",
        ] {
            assert!(breaks_grammar("how", text), "{text}");
        }
    }
}
