//! Reads: an addressed read (R-5.10, R-5.21), the root read `.` (R-5.11), `orphaned` (R-5.23)
//! and the `goto` summary sheet (R-5.30).
//! Reads never change the map, and every element is named by its full address (R-4.12).

use serde_json::{Map as JsonMap, Value, json};

use crate::model::Map;
use crate::names::ROOT;
use crate::refusal::{Code, Refusal};

/// Role values that mark the Definitive element: `DE`, as the intake writes it today; `defining`,
/// the earlier spelled-out name of DE in the canonical map; `definitive`, R-3.13's name.
pub(crate) fn is_definitive(role: Option<&Value>) -> bool {
    role.and_then(Value::as_str).is_some_and(|role| {
        ["de", "defining", "definitive"]
            .iter()
            .any(|name| role.eq_ignore_ascii_case(name))
    })
}

/// `{"<address>": {}}` returns that element's own fields, keyed by its address.
pub(crate) fn read(map: &Map, address: &str) -> Result<Value, Refusal> {
    if address == ROOT {
        return Ok(index(map));
    }
    let Some(element) = map.element(address) else {
        return Err(Refusal::new(
            Code::NotFound,
            format!("'{address}' does not exist"),
            Some(json!({".": {}})),
        ));
    };
    Ok(Value::Object(JsonMap::from_iter([(
        address.to_string(),
        Value::Object(element.base_fields()),
    )])))
}

/// `{".": {}}` returns the connected index: every address beneath the root, each want as an edge
/// from the element that holds it to the element it names, and the one Definitive element.
fn index(map: &Map) -> Value {
    let addresses: Vec<&str> = map
        .elements()
        .map(|(address, _)| address)
        .filter(|address| *address != ROOT)
        .collect();
    let edges: Vec<Value> = map
        .elements()
        .flat_map(|(holder, element)| {
            element
                .wants
                .keys()
                .map(move |other| json!([holder, other]))
        })
        .collect();
    let definitive = map
        .elements()
        .find(|(_, element)| is_definitive(element.fields.get("role")))
        .map(|(address, _)| address);
    json!({"addresses": addresses, "edges": edges, "definitive": definitive})
}

/// `{"orphaned": {}}` returns a bare dictionary keyed by address: each named element that nothing
/// wants maps to its own fields (R-5.23). Being orphaned does not mean an element should go.
pub(crate) fn orphaned(map: &Map) -> Value {
    let wanted = map.wanted();
    Value::Object(
        map.elements()
            .filter(|(address, element)| {
                *address != ROOT && !element.fields.is_empty() && !wanted.contains(address)
            })
            .map(|(address, element)| (address.to_string(), Value::Object(element.base_fields())))
            .collect(),
    )
}

/// Fields that are not layers in the summary sheet: `memory` has its own count, and `skills`
/// deliver their frontmatter.
const OWN_PARTS: [&str; 2] = ["memory", "skills"];

/// `{"goto": "<address>"}` returns the summary sheet for the address (R-5.30): the element's
/// own fields and wants, every element that relies on it with that element's want, each layer
/// held there with its record count, the frontmatter of the skills that apply there (its own
/// and the root's, which apply to the whole project), and its memory count. Counts, not records.
/// Anything keyed by a unique name is a dictionary. Delivering it once per context is the
/// server's job, because it knows the connection.
pub(crate) fn goto(map: &Map, address: &str) -> Result<Value, Refusal> {
    let Some(element) = map.element(address) else {
        return Err(Refusal::new(
            Code::NotFound,
            format!("'{address}' does not exist"),
            Some(json!({".": {}})),
        ));
    };
    let relied_on_by: JsonMap<String, Value> = map
        .elements()
        .filter_map(|(holder, other)| {
            (holder != address)
                .then(|| other.wants.get(address))
                .flatten()
                .map(|record| (holder.to_string(), Value::Object(record.clone())))
        })
        .collect();
    let layers: JsonMap<String, Value> = element
        .fields
        .iter()
        .filter(|(key, value)| value.is_array() && !OWN_PARTS.contains(&key.as_str()))
        .map(|(key, value)| {
            (
                key.clone(),
                json!({"records": value.as_array().map_or(0, Vec::len)}),
            )
        })
        .collect();
    let mut skills = JsonMap::new();
    let root = map.element(ROOT).filter(|_| address != ROOT);
    for holder in root.into_iter().chain(std::iter::once(element)) {
        for skill in holder
            .fields
            .get("skills")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
        {
            let front = skill.get("frontmatter").unwrap_or(skill);
            if let Some(name) = front.get("name").and_then(Value::as_str) {
                let mut entry = JsonMap::new();
                for key in ["name", "description"] {
                    if let Some(value) = front.get(key) {
                        entry.insert(key.to_string(), value.clone());
                    }
                }
                if let Some(uri) = skill.get("uri") {
                    entry.insert("uri".to_string(), uri.clone());
                }
                skills.insert(name.to_string(), Value::Object(entry));
            }
        }
    }
    let memory = element
        .fields
        .get("memory")
        .and_then(Value::as_array)
        .map_or(0, Vec::len);
    Ok(json!({
        "at": address,
        "element": element.base_fields(),
        "wants": element.wants_json(),
        "relied_on_by": relied_on_by,
        "layers": layers,
        "skills": skills,
        "memory": {"records": memory},
    }))
}
