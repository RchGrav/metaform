//! Reads: an addressed read (R-5.10, R-5.21), the root read `.` (R-5.11), `orphaned` (R-5.23)
//! and the `goto` summary sheet (R-5.30).
//! Reads never change the map, and every element is named by its full address (R-4.12).

use serde_json::{Map as JsonMap, Value, json};

use crate::model::Map;
use crate::names::ROOT;
use crate::refusal::{Code, Refusal};
use crate::specification;

/// Role values that mark the Definitive element: `definitive`, R-3.13's name, which the intake
/// writes; `DE`, its abbreviation; `defining`, an earlier name of DE in the canonical map.
pub(crate) fn is_definitive(role: Option<&Value>) -> bool {
    role.and_then(Value::as_str).is_some_and(|role| {
        ["de", "defining", "definitive"]
            .iter()
            .any(|name| role.eq_ignore_ascii_case(name))
    })
}

/// The project's own Definitive element at an address: a Definitive role on an element inside the
/// project (`names::in_project`). An element under `upstream`, `downstream` or `layer` is outside the
/// project (R-3.3, R-3.7), so a Definitive role there does not count (R-3.13).
pub(crate) fn is_project_definitive(address: &str, role: Option<&Value>) -> bool {
    crate::names::in_project(address) && is_definitive(role)
}

/// `{"<address>": {}}` returns that element's own fields, keyed by its address: the form in which
/// data is entered (R-5.10). `{"<address>": {"<layer>": {}, ...}}` adds each named layer held
/// there (R-5.21). A layer is named in the slot where it is written: `{"wants": {}}`,
/// `{"specification": {}}`. A named layer the element does not hold comes back empty when it is a
/// layer that applies there, and is left out otherwise.
pub(crate) fn read(map: &Map, address: &str, body: &Value) -> Result<Value, Refusal> {
    let named: Vec<&str> = body
        .as_object()
        .map(|names| names.keys().map(String::as_str).collect())
        .unwrap_or_default();
    let Some(element) = map.element(address) else {
        return Err(not_found(address));
    };
    let mut fields = element.base_fields();
    for name in named {
        if name == "wants" {
            fields.insert("wants".into(), element.wants_json());
        } else if let Some(value) = element.fields.get(name).filter(|v| v.is_array()) {
            fields.insert(name.into(), value.clone());
        } else if specification::definition_of(map, name).is_some()
            && specification::records_allowed(map, address)
        {
            fields.insert(name.into(), Value::Array(Vec::new()));
        }
    }
    Ok(Value::Object(JsonMap::from_iter([(
        address.to_string(),
        Value::Object(fields),
    )])))
}

/// A refusal for an address that holds no element. `map` lists the addresses that exist.
fn not_found(address: &str) -> Refusal {
    Refusal::new(
        Code::NotFound,
        format!("'{address}' does not exist"),
        Some(json!({"map": {}})),
    )
}

/// `{".<path>": {}}` is a raw dump (R-5.34): the stored nested JSON at that path, which is the
/// JSON path `$.<project><path>` with `$.<project>` left off. `{".": {}}` dumps the whole project;
/// `{".code.server": {}}` dumps that element and everything beneath it. Names are in the agent's
/// form (R-4.11). The result is keyed by the path that was asked for. Every layer is included,
/// memory too.
pub(crate) fn raw(map: &Map, path: &str) -> Result<Value, Refusal> {
    let mut value = map.to_tree();
    if path != ROOT {
        for segment in path[1..].split('.') {
            value = match value {
                Value::Object(mut object) => object.remove(segment),
                _ => None,
            }
            .ok_or_else(|| not_found(&path[1..]))?;
        }
    }
    Ok(Value::Object(JsonMap::from_iter([(path.to_string(), value)])))
}

/// `{"map": {}}` returns the shallow graph (R-5.11): every address beneath the root, each want as
/// an edge from the element that holds it to the element it names, and the one Definitive
/// element. No fields and no layers.
pub(crate) fn shallow(map: &Map) -> Value {
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
        .find(|(address, element)| is_project_definitive(address, element.fields.get("role")))
        .map(|(address, _)| address);
    json!({"addresses": addresses, "edges": edges, "definitive": definitive})
}

/// `{"orphaned": {}}` returns a bare dictionary keyed by address: each named element that nothing
/// wants maps to its own fields (R-5.23). Being orphaned does not mean an element should go.
/// Layer definitions are left out: they sit outside the functional skeleton, nothing wants them,
/// and the server keeps them (R-6.24), so listing them would invite a delete that is refused.
pub(crate) fn orphaned(map: &Map) -> Value {
    let wanted = map.wanted();
    Value::Object(
        map.elements()
            .filter(|(address, element)| {
                *address != ROOT
                    && !specification::in_layer_scope(address)
                    && !element.fields.is_empty()
                    && !wanted.contains(address)
            })
            .map(|(address, element)| (address.to_string(), Value::Object(element.base_fields())))
            .collect(),
    )
}

/// Fields that are not layers in the summary sheet: `memory` has its own count, and `skills`
/// deliver their frontmatter.
const NON_LAYER_FIELDS: [&str; 2] = ["memory", "skills"];

/// `{"goto": "<address>"}` returns the summary sheet for the address (R-5.30): the element's
/// own fields and wants, every element that wants it (`wanted_by`) with that element's want, each layer
/// held there with its record count, the frontmatter of the skills at the address (only when it
/// has some), and its memory count. Counts, not records. The root's skills are the base skills an
/// agent learns when it joins the server, so `goto` does not repeat them (R-5.30).
/// Anything keyed by a unique name is a dictionary. Delivering it once per context is the
/// server's job, because it knows the connection.
pub(crate) fn goto(map: &Map, address: &str) -> Result<Value, Refusal> {
    let Some(element) = map.element(address) else {
        return Err(not_found(address));
    };
    let wanted_by: JsonMap<String, Value> = map
        .elements()
        .filter_map(|(holder, holder_element)| {
            (holder != address)
                .then(|| holder_element.wants.get(address))
                .flatten()
                .map(|record| (holder.to_string(), Value::Object(record.clone())))
        })
        .collect();
    let mut layers: JsonMap<String, Value> = element
        .fields
        .iter()
        .filter(|(key, value)| value.is_array() && !NON_LAYER_FIELDS.contains(&key.as_str()))
        .map(|(key, value)| {
            (
                key.clone(),
                json!({"records": value.as_array().map_or(0, Vec::len)}),
            )
        })
        .collect();
    // Every defined layer is listed wherever its records are allowed, even with none yet, so the
    // agent sees where records are due once intake has placed the element (R-6.27).
    let defined = if specification::records_allowed(map, address) {
        specification::definitions(map)
    } else {
        Vec::new()
    };
    for definition in &defined {
        layers
            .entry(definition.layer.clone())
            .or_insert_with(|| json!({"records": 0}));
    }
    let mut skills = JsonMap::new();
    for skill in element
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
    let memory = element
        .fields
        .get("memory")
        .and_then(Value::as_array)
        .map_or(0, Vec::len);
    let mut sheet = json!({
        "at": address,
        "element": element.base_fields(),
        "wants": element.wants_json(),
        "wanted_by": wanted_by,
        "layers": layers,
        "memory": {"records": memory},
    });
    if !skills.is_empty() {
        sheet["skills"] = Value::Object(skills);
    }
    // Where the rules for writing each listed layer are. The sheet names the place and does not
    // carry the rules: an agent that arrives here may never write the layer, and in four
    // recorded intakes the rules reached every agent before it could use them
    // (metaform/conformance/replay.py). The server delivers this part once per context (R-6.27).
    if !defined.is_empty() {
        sheet["instructions"] = Value::Object(
            defined
                .iter()
                .map(|d| {
                    let text = format!("Before you write {}, goto {} for its rules.", d.layer, d.address);
                    (d.layer.clone(), Value::String(text))
                })
                .collect(),
        );
    }
    // At a layer's definition element, the sheet always carries that layer's guidance, so an agent
    // whose context was reset can read it again (R-5.30). Reads stay in the stored form (R-5.10).
    if let Some(definition) = specification::definitions(map)
        .into_iter()
        .find(|d| d.address == address)
    {
        sheet["guidance"] = Value::String(definition.guidance());
        // The guidance holds the definition's instruction, so the sheet's `element` part leaves
        // it out: the same text does not arrive twice. An addressed read still returns it.
        if let Some(Value::Object(element)) = sheet.get_mut("element") {
            element.remove("instruction");
        }
    }
    Ok(sheet)
}
