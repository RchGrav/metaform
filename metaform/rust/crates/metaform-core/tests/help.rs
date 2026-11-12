//! `help` (R-5.39): the schema of the `help` command itself, the contract's entry for each command,
//! and each definition, one level at a time. Every example here is the owner's, from
//! `metaform/tool-examples.json`.

use std::collections::BTreeSet;

use metaform_core::{Code, Contract, Map, execute};
use serde_json::{Value, json};

const NAMES: [&str; 9] = ["add", "update", "delete", "orphaned", "goto", "map", "addressed read", "raw dump", "help"];
const MESSAGE: &str = "help takes {}, the name of a command, or the name of a definition a schema refers to";

fn fixture(name: &str) -> Value {
    let path = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../..").join(name);
    serde_json::from_slice(&std::fs::read(path).unwrap()).unwrap()
}

/// The node that `help` answers with for one name, on an empty map.
fn help(contract: &Contract, name: &str) -> Value {
    let outcome = execute(contract, &Map::new(), &json!({"help": name})).unwrap_or_else(|e| panic!("{name}: {e:?}"));
    let answer = outcome.result()["help"].as_object().unwrap();
    assert_eq!(answer.keys().collect::<Vec<_>>(), [name]);
    answer[name].clone()
}

/// The name of each definition a schema refers to.
fn refs(schema: &Value, found: &mut BTreeSet<String>) {
    match schema {
        Value::Object(entries) => {
            for (key, value) in entries {
                match value.as_str().and_then(|text| text.strip_prefix("#/$defs/")) {
                    Some(path) if key == "$ref" => {
                        found.insert(path.split('/').next().unwrap().to_string());
                    }
                    _ => refs(value, found),
                }
            }
        }
        Value::Array(items) => items.iter().for_each(|item| refs(item, found)),
        _ => {}
    }
}

/// A whole schema for one command, assembled as an agent can: start from the command's help
/// answer, and ask help for each definition a `$ref` names, until none is missing.
fn assembled(contract: &Contract, name: &str) -> Value {
    let mut schema = help(contract, name);
    let mut definitions = serde_json::Map::new();
    let mut waiting = BTreeSet::new();
    refs(&schema, &mut waiting);
    while let Some(definition) = waiting.pop_first() {
        if !definitions.contains_key(&definition) {
            let node = help(contract, &definition);
            refs(&node, &mut waiting);
            definitions.insert(definition, node);
        }
    }
    if !definitions.is_empty() {
        schema["$defs"] = Value::Object(definitions);
    }
    schema
}

#[test]
fn help_with_no_name_returns_the_schema_of_help() {
    let contract = Contract::bundled().unwrap();
    assert_eq!(
        execute(&contract, &Map::new(), &json!({"help": {}})).unwrap().result(),
        &json!({"help": {"type": "object", "properties": {"help": {"enum": NAMES}}, "required": ["help"]}})
    );
}

#[test]
fn help_with_a_name_returns_one_node_of_the_contract_and_no_pointer_is_a_dead_end() {
    let contract = Contract::bundled().unwrap();
    let input = &contract.tool()["inputSchema"];
    let forms = input["oneOf"].as_array().unwrap();
    // A command name answers with the contract's own entry, and no `$defs`.
    let mut found = BTreeSet::new();
    for name in NAMES {
        let entry = help(&contract, name);
        assert!(forms.contains(&entry), "{name}: the entry is not the contract's");
        assert!(entry.get("$defs").is_none(), "{name}");
        refs(&entry, &mut found);
    }
    let required = |name: &str| forms.iter().find(|form| form["required"] == json!([name])).unwrap();
    assert_eq!(&help(&contract, "add"), required("add"));
    assert_eq!(&help(&contract, "help"), required("help"));
    // A definition name answers with the contract's own definition.
    assert_eq!(help(&contract, "NamespaceNode"), input["$defs"]["NamespaceNode"]);
    for (definition, node) in input["$defs"].as_object().unwrap() {
        assert_eq!(&help(&contract, definition), node, "{definition}");
    }
    // Every `$ref` in any answer names a definition that help answers.
    let mut seen = BTreeSet::new();
    while let Some(definition) = found.pop_first() {
        if seen.insert(definition.clone()) {
            refs(&help(&contract, &definition), &mut found);
        }
    }
    assert!(seen.len() > 5, "{seen:?}");
}

#[test]
fn a_schema_assembled_from_help_answers_takes_the_owners_example() {
    let contract = Contract::bundled().unwrap();
    let examples = fixture("tool-examples.json");
    let requests = &examples["requests"];
    for name in NAMES {
        let schema = assembled(&contract, name);
        let validator = jsonschema::validator_for(&schema).unwrap_or_else(|error| panic!("{name}: {error}"));
        let own: Vec<Value> = match name {
            "add" => vec![requests[0].clone()],
            "update" => vec![requests[4].clone()],
            "delete" => vec![requests[1].clone(), requests[2].clone()],
            "orphaned" => vec![requests[3].clone()],
            "goto" => vec![examples["goto_example"]["request"].clone()],
            "map" => vec![json!({"map": {}})],
            "addressed read" => vec![requests[5].clone()],
            "raw dump" => vec![json!({".": {}})],
            _ => vec![json!({"help": {}}), json!({"help": "add"}), json!({"help": "DependencyRecord"})],
        };
        for example in &own {
            assert!(validator.is_valid(example), "{name}: {example}");
        }
        // It refuses the example of another command.
        let other = if name == "add" { &requests[4] } else { &requests[0] };
        assert!(!validator.is_valid(other), "{name}: {other}");
    }
}

#[test]
fn help_with_any_other_value_is_refused_with_the_remediation() {
    let contract = Contract::bundled().unwrap();
    for value in [json!("nope"), json!("$defs"), json!("oneOf"), json!(7), json!({"x": 1}), json!([]), json!(null), json!("")] {
        let refusal = execute(&contract, &Map::new(), &json!({"help": value})).unwrap_err();
        assert_eq!(refusal.code, Code::FieldMismatch, "{value}");
        assert_eq!(refusal.reason, MESSAGE, "{value}");
        assert_eq!(refusal.remediation.as_deref(), Some(&json!({"help": {}})), "{value}");
    }
}
