//! The map model. A map is the unit: its own root, its elements and, through the home, its own
//! store location. A project's main map is one map; any element can later point to a child map
//! of its own (`Element::child_map`), so nothing here assumes one map per project.
//!
//! In memory the map is flat, keyed by full address in the agent's snake_case form (R-4.12). The
//! nested tree exists only at the edges: documents (R-4.2) and the Ladybug graph (R-4.1, R-4.16).

use std::collections::{BTreeMap, BTreeSet};

use serde_json::{Map as JsonMap, Value};

use crate::names::{self, ROOT};

/// An element's own fields: scalars and native arrays. Objects are child elements, not fields.
pub type Fields = JsonMap<String, Value>;

/// The location of a map's store, relative to the home, such as `projects/-src-game001`.
/// An element's `child_map` holds one; a project's main map is another.
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct MapRef(pub String);

/// One element at one address (R-3.1).
#[derive(Clone, Debug, Default, PartialEq)]
pub struct Element {
    pub fields: Fields,
    /// The element's wants: an array. Each entry is the address of the wanted element and the
    /// want's own fields. An element may hold several wants on the same element, one for each
    /// artifact: a want's key is its element together with its `ref` (founder, 2026-11-12).
    pub wants: Vec<(String, Fields)>,
    /// The element's own child map, if it has one. The store saves and loads it, but no command
    /// sets it yet.
    pub child_map: Option<MapRef>,
}

/// The intake fields, in R-6.15's order. They come first in an element; every other field follows,
/// sorted by name. One order makes an element's JSON the same after every reload and in every
/// form of Metaform, whatever order its fields were written in.
pub const FIELD_ORDER: [&str; 5] = ["technical_name", "name", "role", "refs", "status"];
/// The element's source links: a list with one uri for each artifact that has this address. It
/// is a field of the element, not a layer, so every read of the element returns it.
pub const REFS: &str = "refs";
/// The want-record fields, in R-6.17's order, first in a want record; any other follows by name.
pub const WANT_ORDER: [&str; 4] = ["why", "how", "direction", "ref"];

/// Put `fields` in canonical order: the names in `first`, in that order, then the rest by name.
fn put_in_order(fields: &mut Fields, first: &[&str]) {
    let mut rest = std::mem::take(fields);
    for name in first {
        if let Some(value) = rest.remove(*name) {
            fields.insert((*name).to_string(), value);
        }
    }
    let mut rest: Vec<(String, Value)> = rest.into_iter().collect();
    rest.sort_by(|a, b| a.0.cmp(&b.0));
    fields.extend(rest);
}

impl Element {
    /// Put the fields and every want record in canonical order (`FIELD_ORDER`, `WANT_ORDER`).
    pub fn put_in_order(&mut self) {
        // A map stored before `refs` held one link in `uri`. It is read as a list of one.
        if let Some(uri) = self.fields.get("uri").filter(|uri| uri.is_string()).cloned()
            && !self.fields.contains_key(REFS)
        {
            self.fields.shift_remove("uri");
            self.fields.insert(REFS.to_string(), Value::Array(vec![uri]));
        }
        put_in_order(&mut self.fields, &FIELD_ORDER);
        for (_, record) in self.wants.iter_mut() {
            put_in_order(record, &WANT_ORDER);
        }
        // The store keeps wants as relationships, which have no order. One fixed order, by the
        // want's key (its element, then its `ref`), makes an element read the same after every
        // reload.
        let uri = |record: &Fields| record.get("ref").and_then(Value::as_str).unwrap_or_default().to_string();
        self.wants.sort_by(|a, b| (a.0.as_str(), uri(&a.1)).cmp(&(b.0.as_str(), uri(&b.1))));
    }

    /// An element with nothing in it: a namespace branch that a write created.
    pub fn is_empty(&self) -> bool {
        self.fields.is_empty() && self.wants.is_empty() && self.child_map.is_none()
    }

    /// The wants as the contract writes them: a list with one record for each providing
    /// element. Each record names that element in `element`, then gives `why`, `how` and `direction`.
    pub fn wants_json(&self) -> Value {
        Value::Array(
            self.wants
                .iter()
                .map(|(other, record)| want_json("element", other, record))
                .collect(),
        )
    }

    /// The fields an addressed read returns (R-5.10, R-5.21): scalar values and `refs`.
    /// Wants and array-valued layers come back only when a read names them.
    pub fn base_fields(&self) -> Fields {
        self.fields
            .iter()
            .filter(|(name, value)| !value.is_array() || name.as_str() == REFS)
            .map(|(k, v)| (k.clone(), v.clone()))
            .collect()
    }

    /// The element's fields and wants, without child elements, in the agent's form.
    pub fn view(&self) -> Value {
        let mut out = self.fields.clone();
        if !self.wants.is_empty() {
            out.insert("wants".to_string(), self.wants_json());
        }
        Value::Object(out)
    }
}

/// The final value of every element a write touched: the whole element, or `None` if removed.
/// Applying an effect twice gives the same map.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct Effect {
    pub elements: BTreeMap<String, Option<Element>>,
}

impl Effect {
    pub fn is_empty(&self) -> bool {
        self.elements.is_empty()
    }

    /// The effect in the agent's form, keyed by full address.
    pub fn to_json(&self) -> Value {
        Value::Object(
            self.elements
                .iter()
                .map(|(address, element)| {
                    (
                        address.clone(),
                        element.as_ref().map_or(Value::Null, Element::view),
                    )
                })
                .collect(),
        )
    }
}

/// A problem loading a map, a document or a home file.
#[derive(Debug, thiserror::Error)]
pub enum MapError {
    #[error("{0}")]
    Invalid(String),
    #[error(transparent)]
    Io(#[from] std::io::Error),
    #[error(transparent)]
    Json(#[from] serde_json::Error),
}

/// One map: a root at `.` and the elements beneath it.
#[derive(Clone, Debug, PartialEq)]
pub struct Map {
    elements: BTreeMap<String, Element>,
}

impl Default for Map {
    fn default() -> Self {
        Map::new()
    }
}

impl Map {
    /// An empty map: the root alone.
    pub fn new() -> Self {
        Map {
            elements: BTreeMap::from([(ROOT.to_string(), Element::default())]),
        }
    }

    /// A map from its elements, keyed by address in the agent's form. A store uses this to
    /// rebuild a map it loaded; the root is added if it is missing.
    pub fn from_elements(mut elements: BTreeMap<String, Element>) -> Self {
        elements.entry(ROOT.to_string()).or_default();
        elements.values_mut().for_each(Element::put_in_order);
        Map { elements }
    }

    pub(crate) fn raw(&self) -> &BTreeMap<String, Element> {
        &self.elements
    }

    /// The element at an address; `.` is the root.
    pub fn element(&self, address: &str) -> Option<&Element> {
        self.elements.get(address)
    }

    /// Every element, the root first, then by address.
    pub fn elements(&self) -> impl Iterator<Item = (&str, &Element)> {
        self.elements
            .iter()
            .map(|(address, element)| (address.as_str(), element))
    }

    /// The map with an effect applied.
    pub fn apply(&self, effect: &Effect) -> Map {
        let mut elements = self.elements.clone();
        for (address, element) in &effect.elements {
            match element {
                Some(element) => elements.insert(address.clone(), element.clone()),
                None => elements.remove(address),
            };
        }
        Map { elements }
    }

    /// Load a document (R-4.2): one top-level key, the project name, over the nested map in the
    /// agent's form. Wants are the contract's list of records.
    pub fn from_document(document: &Value) -> Result<(String, Map), MapError> {
        let object = document.as_object().filter(|object| object.len() == 1);
        let Some((name, root)) = object.and_then(|object| object.iter().next()) else {
            return Err(MapError::Invalid(
                "a document must have one top-level key, the project name".into(),
            ));
        };
        Ok((name.clone(), Map::from_tree(root)?))
    }

    /// The map as a document under the project name, which the registry holds (R-3.10, R-4.2).
    pub fn to_document(&self, name: &str) -> Value {
        Value::Object(JsonMap::from_iter([(name.to_string(), self.to_tree())]))
    }

    /// Load a nested map in the agent's form. Every name must survive storage (R-4.11), every
    /// top-level element must be in a root scope (R-3.3) and every want must name an element.
    pub fn from_tree(root: &Value) -> Result<Map, MapError> {
        let Value::Object(root) = root else {
            return Err(MapError::Invalid("a map must be a JSON object".into()));
        };
        let mut elements = BTreeMap::new();
        flatten(root, ROOT, &mut elements);
        let mut problems = Vec::new();
        for (address, element) in &elements {
            let names = element
                .fields
                .keys()
                .map(|key| (address.as_str(), key.as_str()));
            let segments = address
                .split('.')
                .filter(|_| address != ROOT)
                .map(|segment| (address.as_str(), segment));
            for (at, name) in segments.chain(names) {
                if let Some(why) = names::segment_problem(name) {
                    problems.push(format!("'{at}': '{name}': {why}"));
                }
            }
            if let Err(refusal) = names::check_scope(address) {
                problems.push(refusal.reason);
            }
            for other in element
                .wants
                .iter()
                .map(|(other, _)| other)
                .filter(|other| !elements.contains_key(*other))
            {
                problems.push(format!("'{address}' wants '{other}', which does not exist"));
            }
        }
        if problems.is_empty() {
            Ok(Map::from_elements(elements))
        } else {
            Err(MapError::Invalid(problems.join("\n")))
        }
    }

    /// The nested map in the agent's form, without the project name.
    pub fn to_tree(&self) -> Value {
        let mut root = JsonMap::new();
        for (address, element) in &self.elements {
            let mut node = &mut root;
            if address != ROOT {
                for segment in address.split('.') {
                    let entry = node
                        .entry(segment.to_string())
                        .or_insert_with(|| Value::Object(JsonMap::new()));
                    node = entry
                        .as_object_mut()
                        .expect("an address segment is an object");
                }
            }
            if let Value::Object(view) = element.view() {
                node.extend(view);
            }
        }
        Value::Object(root)
    }

    /// The addresses of the elements whose wants name `address`.
    pub(crate) fn receivers(elements: &BTreeMap<String, Element>, address: &str) -> Vec<String> {
        elements
            .iter()
            .filter(|(holder, element)| {
                holder.as_str() != address && element.wants.iter().any(|(other, _)| other == address)
            })
            .map(|(holder, _)| holder.clone())
            .collect()
    }

    /// Every address that some element wants.
    pub(crate) fn wanted(&self) -> BTreeSet<&str> {
        self.elements
            .values()
            .flat_map(|element| element.wants.iter().map(|(other, _)| other.as_str()))
            .collect()
    }
}

/// One want record in the contract's form: the address of the other element under `end`
/// (`element` for the providing element, `element` for the receiving element), then the record's fields.
pub(crate) fn want_json(end: &str, other: &str, record: &Fields) -> Value {
    let mut out = JsonMap::new();
    out.insert(end.to_string(), Value::String(other.to_string()));
    out.extend(record.clone());
    Value::Object(out)
}

/// A value read as want records: a list of objects that each name the wanted element in
/// `element`. The result keeps every record, in the order given. Anything else named `wants` is
/// not a list of wants.
pub(crate) fn read_wants(value: &Value) -> Option<Vec<(String, Fields)>> {
    let records = value.as_array()?;
    let mut wants = Vec::new();
    for record in records {
        let mut fields = record.as_object()?.clone();
        let Some(Value::String(element)) = fields.shift_remove("element") else {
            return None;
        };
        wants.push((element, fields));
    }
    Some(wants)
}

/// Split a nested object into one element per address. An object value is a child element.
pub(crate) fn flatten(
    node: &JsonMap<String, Value>,
    address: &str,
    out: &mut BTreeMap<String, Element>,
) {
    let mut element = Element::default();
    let mut children = Vec::new();
    for (key, value) in node {
        if key == "wants"
            && let Some(wants) = read_wants(value)
        {
            element.wants = wants;
        } else if let Value::Object(child) = value {
            children.push((names::join(address, key), child));
        } else {
            element.fields.insert(key.clone(), value.clone());
        }
    }
    out.insert(address.to_string(), element);
    for (child_address, child) in children {
        flatten(child, &child_address, out);
    }
}
