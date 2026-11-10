//! The commands of the `project-map` tool: `add`, `update`, `delete`, `orphaned` and addressed
//! reads (R-5.1 to R-5.12, R-5.21 to R-5.25).
//!
//! A command takes a map and returns either a new map with the effect, or a refusal. The input map
//! is never changed, so a failed command changes nothing (R-5.8), and a write manager can put a
//! queue in front of `execute` without changing it.

use std::collections::{BTreeMap, BTreeSet};

use serde_json::{Map as JsonMap, Value, json};

use crate::contract::Contract;
use crate::model::{Effect, Element, Map, flatten, is_want_updates};
use crate::names::{self, ROOT};
use crate::reads::{self, is_project_definitive};
use crate::refusal::{Code, Refusal};
use crate::{rules, shape, specification};

/// What an accepted command produced.
#[derive(Clone, Debug, PartialEq)]
pub enum Outcome {
    /// A read: the result, and the map is unchanged.
    Read(Value),
    /// A write: the new map, the effect that turns the old map into it, and the result.
    Write(Write),
}

#[derive(Clone, Debug, PartialEq)]
pub struct Write {
    pub map: Map,
    pub effect: Effect,
    pub result: Value,
}

impl Outcome {
    /// The result an agent receives.
    pub fn result(&self) -> &Value {
        match self {
            Outcome::Read(result) => result,
            Outcome::Write(write) => &write.result,
        }
    }
}

/// Perform one command on a map. The command's shape is checked by hand (`shape`), then against
/// the contract as a backstop, then its names (R-4.11). Then it is applied to a copy of the map.
pub fn execute(contract: &Contract, map: &Map, command: &Value) -> Result<Outcome, Refusal> {
    shape::check(command)?;
    contract.check_input(command)?;
    names::check_command(command)?;
    let (verb, body) = only(command);
    match verb {
        "orphaned" => Ok(Outcome::Read(reads::orphaned(map))),
        "map" => Ok(Outcome::Read(reads::shallow(map))),
        "goto" => {
            let address = body.as_str().expect("the input schema allows a string");
            reads::goto(map, address).map(Outcome::Read)
        }
        "add" | "update" | "delete" => {
            let (selector, supplied) = only(body);
            if let (true, Value::Object(fields)) = (verb != "delete", supplied) {
                rules::check_layer_values(map, verb, selector, fields)?;
            }
            let mut work = Work {
                contract,
                before: map,
                elements: map.raw().clone(),
                touched: BTreeSet::new(),
                written_wants: Vec::new(),
                add: (verb == "add").then_some((selector, supplied)),
            };
            match verb {
                "add" => work.add(selector, supplied)?,
                "update" => work.update(selector, supplied)?,
                _ => work.delete(selector, supplied)?,
            }
            let (map, effect) = work.finish()?;
            // A successful write answers with its status alone. It does not repeat the command:
            // the agent sent it and has it, and in four recorded intakes the repeat was about
            // 30% of everything the tool delivered (metaform/conformance/replay.py). A refusal
            // still repeats the command, so the agent sees what was refused beside the reason.
            Ok(Outcome::Write(Write {
                map,
                effect,
                result: json!({"status": "ok"}),
            }))
        }
        path if path.starts_with('.') => reads::raw(map, path).map(Outcome::Read),
        address => reads::read(map, address, body).map(Outcome::Read),
    }
}

/// The single entry of an object that the input schema has already checked.
fn only(value: &Value) -> (&str, &Value) {
    let (key, value) = value
        .as_object()
        .and_then(|object| object.iter().next())
        .expect("the input schema allows one entry");
    (key.as_str(), value)
}

/// A copy of the map being changed, and the addresses the change touched.
struct Work<'a> {
    contract: &'a Contract,
    before: &'a Map,
    elements: BTreeMap<String, Element>,
    touched: BTreeSet<String>,
    /// The wants this command wrote, in the order it wrote them: the holder, the other element,
    /// and which of `why` and `how` the command supplied. `finish` checks their grammar.
    written_wants: Vec<(String, String, Vec<&'static str>)>,
    /// The selector and the body of the command when it is an `add`. A grammar refusal for a
    /// want of an element the command made gives the command back as its remediation.
    add: Option<(&'a str, &'a Value)>,
}

impl Work<'_> {
    /// Create the address and every missing branch above it (R-5.4).
    fn ensure(&mut self, address: &str) -> Result<(), Refusal> {
        for prefix in names::prefixes(address) {
            if !self.elements.contains_key(&prefix) {
                names::check_scope(&prefix)?;
                self.elements.insert(prefix.clone(), Element::default());
                self.touched.insert(prefix);
            }
        }
        Ok(())
    }

    fn element_mut(&mut self, address: &str) -> &mut Element {
        self.touched.insert(address.to_string());
        self.elements.get_mut(address).expect("ensured before use")
    }

    /// Write a want. Supplied fields change the current record; the result needs every field
    /// (R-5.6). The element the want names is created if it is not there (R-5.4).
    fn write_want(&mut self, holder: &str, other: &str, change: &Value) -> Result<(), Refusal> {
        let mut record = self.elements[holder]
            .wants
            .get(other)
            .cloned()
            .unwrap_or_default();
        let mut written = Vec::new();
        if let Value::Object(change) = change {
            written.extend(["why", "how"].into_iter().filter(|key| change.contains_key(*key)));
            record.extend(change.clone());
        }
        let filled = |key: &str| {
            record
                .get(key)
                .and_then(Value::as_str)
                .is_some_and(|text| !text.trim().is_empty())
        };
        let missing: Vec<&str> = ["why", "how", "direction"]
            .into_iter()
            .filter(|key| !filled(key))
            .collect();
        if !missing.is_empty() {
            let mut complete = record.clone();
            for key in &missing {
                complete.insert((*key).into(), json!(format!("<{key}>")));
            }
            return Err(Refusal::new(
                Code::WantIncomplete,
                format!(
                    "'{holder}' wants '{other}': the want has no {}",
                    missing.join(", ")
                ),
                Some(json!({"update": {holder: {"wants": {other: complete}}}})),
            ));
        }
        self.ensure(other)?;
        self.element_mut(holder)
            .wants
            .insert(other.to_string(), record);
        self.written_wants.push((holder.to_string(), other.to_string(), written));
        Ok(())
    }

    fn write_wants(&mut self, holder: &str, wants: &JsonMap<String, Value>) -> Result<(), Refusal> {
        for (other, change) in wants {
            self.write_want(holder, other, change)?;
        }
        Ok(())
    }

    /// `add` keeps what is there: arrays grow, and other values are written (R-5.5).
    fn add(&mut self, address: &str, supplied: &Value) -> Result<(), Refusal> {
        let mut supplied_elements = BTreeMap::new();
        flatten(
            supplied.as_object().expect("checked by the input schema"),
            address,
            &mut supplied_elements,
        );
        for (at, supplied) in &supplied_elements {
            self.ensure(at)?;
            let element = self.element_mut(at);
            for (key, value) in &supplied.fields {
                match (element.fields.get_mut(key), value) {
                    (_, Value::Null) => {
                        element.fields.remove(key);
                    }
                    (Some(Value::Array(current)), Value::Array(more)) => {
                        current.extend(more.iter().cloned())
                    }
                    _ => {
                        element.fields.insert(key.clone(), value.clone());
                    }
                }
            }
        }
        for (at, supplied) in &supplied_elements {
            for (other, record) in &supplied.wants {
                self.write_want(at, other, &Value::Object(record.clone()))?;
            }
        }
        Ok(())
    }

    /// `update` writes to a path; `null` removes a field (R-5.5).
    fn update(&mut self, address: &str, supplied: &Value) -> Result<(), Refusal> {
        self.ensure(address)?;
        for (key, value) in supplied.as_object().expect("checked by the input schema") {
            match value {
                Value::Object(wants) if key == "wants" && is_want_updates(wants) => {
                    self.write_wants(address, wants)?
                }
                Value::Null => {
                    self.element_mut(address).fields.remove(key);
                }
                Value::Object(_) => self.update(&names::join(address, key), value)?,
                _ => {
                    self.element_mut(address)
                        .fields
                        .insert(key.clone(), value.clone());
                }
            }
        }
        Ok(())
    }

    /// `delete` removes the named wants, or the element. An element that something still wants is
    /// refused, with the command that removes the want (R-5.7, R-5.25).
    fn delete(&mut self, address: &str, supplied: &Value) -> Result<(), Refusal> {
        if !self.elements.contains_key(address) {
            return Ok(());
        }
        if let Some(Value::Array(wants)) = supplied.get("wants") {
            for other in wants.iter().filter_map(Value::as_str) {
                if self.elements[address].wants.contains_key(other) {
                    self.element_mut(address).wants.remove(other);
                    self.prune(other);
                }
            }
            return Ok(());
        }
        let receivers = Map::receivers(&self.elements, address);
        if let Some(first) = receivers.first() {
            // TASTE wording (Matthew, 2026-11-09): the problem, then what to do. It replaces the
            // founder's sample "cannot delete, '<address>', must be orphaned first"; the refusal's
            // structure and code are unchanged.
            let message = if receivers.len() > 1 {
                format!(
                    "cannot delete '{address}': these elements still want it: {}. Remove their wants first.",
                    receivers.iter().map(|r| format!("'{r}'")).collect::<Vec<_>>().join(", ")
                )
            } else {
                format!("cannot delete '{address}': '{first}' still wants it. Remove that want first.")
            };
            return Err(Refusal::new(
                Code::DependencyLock,
                message,
                Some(json!({"delete": {first: {"wants": [address]}}})),
            ));
        }
        let beneath = self
            .elements
            .keys()
            .filter(|child| names::is_beneath(child, address));
        if let Some(deepest) = beneath.max_by_key(|child| child.matches('.').count()) {
            return Err(Refusal::new(
                Code::ElementsBeneath,
                format!("cannot delete, '{address}', has elements beneath it"),
                Some(json!({"delete": {deepest.as_str(): {}}})),
            ));
        }
        let wanted: Vec<String> = self.elements[address].wants.keys().cloned().collect();
        self.remove(address);
        if let Some(parent) = names::parent(address) {
            self.prune(parent);
        }
        for other in wanted {
            self.prune(&other);
        }
        Ok(())
    }

    /// Remove an element that a deletion left with nothing in it, and then each branch above it
    /// that is left the same way: no fields, no wants, nothing beneath it and nothing that wants
    /// it. A write creates the element a want names (R-5.4); when the last want that names it is
    /// gone and it was never filled in, it goes too, so no empty address stays in the map.
    fn prune(&mut self, address: &str) {
        let mut branch = Some(address.to_string());
        while let Some(at) = branch.filter(|at| at != ROOT) {
            let empty = self.elements.get(&at).is_some_and(Element::is_empty);
            let has_children = self
                .elements
                .keys()
                .any(|child| names::is_beneath(child, &at));
            if !empty || has_children || !Map::receivers(&self.elements, &at).is_empty() {
                break;
            }
            self.remove(&at);
            branch = names::parent(&at).map(str::to_string);
        }
    }

    fn remove(&mut self, address: &str) {
        self.elements.remove(address);
        self.touched.insert(address.to_string());
    }

    /// Check every touched element against the rules that read the map, then build the effect.
    fn finish(mut self) -> Result<(Map, Effect), Refusal> {
        self.normalize_specifications()?;
        for address in &self.touched {
            if let Some(element) = self.elements.get_mut(address) {
                element.put_in_order();
            }
        }
        let defined: Vec<String> = specification::definitions(&Map::from_elements(self.elements.clone()))
            .into_iter()
            .map(|d| d.layer)
            .collect();
        for address in &self.touched {
            let Some(element) = self.elements.get(address) else {
                continue;
            };
            self.check_layers_defined(address, element, &defined)?;
            rules::check(self.before, address, element)?;
            self.check_collisions(address, element)?;
            self.contract.check_element(address, &element.view())?;
        }
        self.check_definitive()?;
        // The grammar of `why` and `how` is checked last, so every earlier refusal stays as it
        // was. The first want that breaks the rule, in the order the command wrote them, is
        // reported.
        for (holder, other, written) in &self.written_wants {
            rules::check_want_grammar(self.before, &self.elements, holder, other, written, self.add)?;
        }
        let mut effect = Effect::default();
        for address in &self.touched {
            let after = self.elements.get(address);
            if after != self.before.element(address) {
                effect.elements.insert(address.clone(), after.cloned());
            }
        }
        Ok((Map::from_elements(self.elements), effect))
    }

    /// Check the layer records a write changed, for every layer the map defines (R-6.24 to
    /// R-6.26). Records must be a list and sit where records are allowed. Records of a
    /// `markdown_blocks` layer are normalized and their heading rules checked; an empty list
    /// removes the field. Records the write did not change are not checked again, so an intake
    /// correction elsewhere is never refused because of them. The code-defined specification
    /// layer definition can only be written as `specification::definition()` (R-6.11, R-6.22).
    fn normalize_specifications(&mut self) -> Result<(), Refusal> {
        if self.touched.contains(specification::DEFINITION_ADDRESS) {
            let after = self.elements.get(specification::DEFINITION_ADDRESS);
            let before = self.before.element(specification::DEFINITION_ADDRESS);
            if after != before
                && after.is_none_or(|e| e.fields != specification::definition() || !e.wants.is_empty())
            {
                return Err(Refusal::new(
                    Code::LayerDefinitionLocked,
                    format!(
                        "'{}' is defined by the server; agents write its records at receiving elements, not its definition",
                        specification::DEFINITION_ADDRESS
                    ),
                    None,
                ));
            }
        }
        let after = Map::from_elements(self.elements.clone());
        // A layer's field name is its key at every receiving element, so two definitions may not
        // share a last segment (R-6.24).
        for address in &self.touched {
            let defines = self
                .elements
                .get(address)
                .is_some_and(|e| e.fields.get("instruction").is_some_and(Value::is_string));
            if !defines || !specification::in_layer_scope(address) {
                continue;
            }
            let layer = address.rsplit('.').next().unwrap_or_default();
            let other = after.elements().find(|(at, element)| {
                *at != address.as_str()
                    && specification::in_layer_scope(at)
                    && at.rsplit('.').next() == Some(layer)
                    && element.fields.get("instruction").is_some_and(Value::is_string)
            });
            if let Some((existing, _)) = other {
                return Err(Refusal::new(
                    Code::LayerNameCollision,
                    format!(
                        "'{address}' would define the layer {layer}, which '{existing}' already defines; a layer's last segment is its field name and must be unique"
                    ),
                    Some(json!({"update": {address.as_str(): {"instruction": null}}})),
                ));
            }
        }
        let definitions = specification::definitions(&after);
        let mut blocks = Vec::new();
        for address in &self.touched {
            let Some(element) = self.elements.get(address) else {
                continue;
            };
            for definition in &definitions {
                let layer = definition.layer.as_str();
                let Some(value) = element.fields.get(layer) else {
                    continue;
                };
                let before = self.before.element(address).and_then(|e| e.fields.get(layer));
                if before == Some(value) {
                    continue;
                }
                let records = specification::records(layer, address, value)?;
                if !records.is_empty() {
                    specification::check_allowed(&after, address, layer)?;
                }
                if definition.format.as_deref() == Some(specification::MARKDOWN_BLOCKS) {
                    let found = specification::blocks_of(layer, address, value)?;
                    specification::check_blocks(address, layer, &found)?;
                    specification::check_codes(&after, address, layer, &found)?;
                    blocks.push((address.clone(), layer.to_string(), found));
                } else if records.is_empty() {
                    blocks.push((address.clone(), layer.to_string(), Vec::new()));
                }
            }
        }
        for (address, layer, found) in blocks {
            let fields = &mut self.elements.get_mut(&address).expect("touched and present").fields;
            if found.is_empty() {
                fields.remove(&layer);
            } else {
                fields.insert(layer, specification::to_json(&found));
            }
        }
        Ok(())
    }

    /// A list at an element is a layer's records, so its name must be a layer: one defined beneath
    /// `layer` (R-6.24) or a system layer (R-6.15). Only lists this write changed are checked, so
    /// older data never blocks an unrelated write.
    fn check_layers_defined(&self, address: &str, element: &Element, defined: &[String]) -> Result<(), Refusal> {
        let before = self.before.element(address);
        for (name, value) in &element.fields {
            if !value.is_array()
                || specification::SYSTEM_LAYERS.contains(&name.as_str())
                || defined.iter().any(|layer| layer == name)
                || before.and_then(|e| e.fields.get(name)) == Some(value)
            {
                continue;
            }
            return Err(Refusal::new(
                Code::LayerNotRegistered,
                format!(
                    "'{name}' at '{address}' is not a layer. A list can be written only to a layer defined beneath the layer root, such as layer.document.specification, or to skills, memory or sources."
                ),
                Some(json!({"map": {}})),
            ));
        }
        Ok(())
    }

    /// The stored map nests fields and child elements in one object, so a field cannot share a
    /// name with a child element.
    fn check_collisions(&self, address: &str, element: &Element) -> Result<(), Refusal> {
        let field_over_child = element
            .fields
            .keys()
            .find(|key| self.elements.contains_key(&names::join(address, key)));
        let child_over_field = names::parent(address).and_then(|parent| {
            let segment = address.rsplit('.').next()?;
            self.elements
                .get(parent)?
                .fields
                .contains_key(segment)
                .then_some(parent)
        });
        let clash = match (field_over_child, child_over_field) {
            (Some(key), _) => Some((address.to_string(), key.clone())),
            (None, Some(parent)) => Some((
                parent.to_string(),
                address.rsplit('.').next().unwrap_or_default().to_string(),
            )),
            _ => None,
        };
        match clash {
            None => Ok(()),
            Some((holder, key)) => Err(Refusal::new(
                Code::FieldElementCollision,
                format!("'{holder}': '{key}' cannot be both a field and an element beneath it"),
                Some(json!({"update": {holder: {key: null}}})),
            )),
        }
    }

    /// A project has one Definitive element (R-3.13). A write that would make a second is refused.
    /// Elements under a root prefix do not count, because those prefixes are outside the project
    /// (R-3.3, R-3.7).
    fn check_definitive(&self) -> Result<(), Refusal> {
        let definitive: Vec<&String> = self
            .elements
            .iter()
            .filter(|(address, element)| is_project_definitive(address, element.fields.get("role")))
            .map(|(address, _)| address)
            .collect();
        if definitive.len() < 2 {
            return Ok(());
        }
        let existing = definitive
            .iter()
            .find(|address| !self.touched.contains(**address))
            .unwrap_or(&definitive[0]);
        let added = definitive
            .iter()
            .find(|address| *address != existing)
            .unwrap_or(&definitive[1]);
        // The remediation gives the new element another role. It never removes the role of the
        // element that is Definitive already: an agent that followed it would lose the one
        // element that says what the project is.
        let other_role = "<Supportive, Notable or Divergent>";
        let remediation = match (self.before.element(added), self.elements.get(*added)) {
            (None, Some(element)) => {
                let mut view = element.view();
                view["role"] = json!(other_role);
                json!({"add": {added.as_str(): view}})
            }
            _ => json!({"update": {added.as_str(): {"role": other_role}}}),
        };
        Err(Refusal::new(
            Code::RoleTaxonomyFailure,
            format!(
                "'{added}' cannot be Definitive: '{existing}' already is, and a map has one Definitive element"
            ),
            Some(remediation),
        ))
    }
}
