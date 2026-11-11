//! `help` (R-5.39): the schema of the `help` command itself, and the schema of each command, taken
//! from the contract. Every example here is the owner's, from `metaform/tool-examples.json`.

use std::collections::BTreeSet;

use metaform_core::{Code, Contract, Map, execute};
use serde_json::{Value, json};

const NAMES: [&str; 9] = ["add", "update", "delete", "orphaned", "goto", "map", "addressed read", "raw dump", "help"];

fn fixture(name: &str) -> Value {
    let path = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../..").join(name);
    serde_json::from_slice(&std::fs::read(path).unwrap()).unwrap()
}

/// The answer to one `help` command on an empty map.
fn help(contract: &Contract, value: Value) -> Value {
    execute(contract, &Map::new(), &json!({"help": value})).unwrap().result().clone()
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

#[test]
fn help_with_no_name_returns_the_schema_of_help() {
    let contract = Contract::bundled().unwrap();
    assert_eq!(
        help(&contract, json!({})),
        json!({"help": {"type": "object", "properties": {"help": {"enum": NAMES}}, "required": ["help"]}})
    );
}

#[test]
fn help_with_a_name_returns_the_contracts_schema_with_the_definitions_it_reaches() {
    let contract = Contract::bundled().unwrap();
    let input = &contract.tool()["inputSchema"];
    let examples = fixture("tool-examples.json");
    let requests = &examples["requests"];
    for name in NAMES {
        let answer = help(&contract, json!(name));
        let schema = &answer["help"][name];
        assert_eq!(answer["help"].as_object().unwrap().len(), 1, "{name}");
        // The form is one entry of the contract's own `oneOf`, as the contract writes it.
        let mut form = schema.clone();
        form.as_object_mut().unwrap().remove("$defs");
        assert!(input["oneOf"].as_array().unwrap().contains(&form), "{name}: the form is not the contract's");
        // `$defs` holds every definition the form reaches, no other, each as the contract writes it.
        let mut reached = BTreeSet::new();
        refs(&form, &mut reached);
        loop {
            let mut more = reached.clone();
            for definition in &reached {
                refs(&input["$defs"][definition], &mut more);
            }
            if more == reached {
                break;
            }
            reached = more;
        }
        let held: BTreeSet<String> = schema["$defs"].as_object().into_iter().flatten().map(|(k, _)| k.clone()).collect();
        assert_eq!(held, reached, "{name}");
        for definition in &held {
            assert_eq!(schema["$defs"][definition], input["$defs"][definition], "{name}: {definition}");
        }
        // The schema stands alone, and takes the owner's example of the command.
        let validator = jsonschema::validator_for(schema).unwrap_or_else(|error| panic!("{name}: {error}"));
        let own: Vec<Value> = match name {
            "add" => vec![requests[0].clone()],
            "update" => vec![requests[4].clone()],
            "delete" => vec![requests[1].clone(), requests[2].clone()],
            "orphaned" => vec![requests[3].clone()],
            "goto" => vec![examples["goto_example"]["request"].clone()],
            "map" => vec![json!({"map": {}})],
            "addressed read" => vec![requests[5].clone()],
            "raw dump" => vec![json!({".": {}})],
            _ => vec![json!({"help": {}}), json!({"help": "add"})],
        };
        for example in &own {
            assert!(validator.is_valid(example), "{name}: {example}");
        }
        // It refuses the examples of the other commands.
        let other = if name == "add" { &requests[4] } else { &requests[0] };
        assert!(!validator.is_valid(other), "{name}: {other}");
    }
    let add = help(&contract, json!("add"));
    let held = add["help"]["add"]["$defs"].as_object().unwrap();
    assert!(["AddFields", "NamespaceNode", "Wants", "WantRecord"].iter().all(|d| held.contains_key(*d)));
    assert!(["DeleteWants", "UpdateFields", "LayerRead", "Empty"].iter().all(|d| !held.contains_key(*d)));
    assert!(help(&contract, json!("goto"))["help"]["goto"].get("$defs").is_none());
}

#[test]
fn help_with_any_other_value_is_refused_with_the_remediation() {
    let contract = Contract::bundled().unwrap();
    for value in [json!("nope"), json!(7), json!({"x": 1}), json!([]), json!(null), json!("")] {
        let refusal = execute(&contract, &Map::new(), &json!({"help": value})).unwrap_err();
        assert_eq!(refusal.code, Code::FieldMismatch, "{value}");
        assert_eq!(refusal.reason, "help takes {} or the name of a command", "{value}");
        assert_eq!(refusal.remediation.as_deref(), Some(&json!({"help": {}})), "{value}");
    }
}
