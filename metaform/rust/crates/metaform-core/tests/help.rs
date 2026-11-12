//! `help` (R-5.39): the schema of the `help` command itself, the contract's entry for each command,
//! and each definition, one level at a time. Every example here is the owner's, from
//! `metaform/tool-examples.json`.

use metaform_core::{Code, Contract, Map, execute};
use serde_json::{Value, json};

const NAMES: [&str; 9] = ["add", "update", "delete", "orphaned", "goto", "map", "addressed read", "raw dump", "help"];
const MESSAGE: &str = "help takes {}, the name of a command, the name of a definition a schema refers to, or intake";

/// The node that `help` answers with for one name, on an empty map.
fn help(contract: &Contract, name: &str) -> Value {
    let outcome = execute(contract, &Map::new(), &json!({"help": name})).unwrap_or_else(|e| panic!("{name}: {e:?}"));
    let answer = outcome.result()["help"].as_object().unwrap();
    assert_eq!(answer.keys().collect::<Vec<_>>(), [name]);
    answer[name].clone()
}

#[test]
fn help_with_no_name_returns_the_schema_of_help() {
    let contract = Contract::bundled().unwrap();
    // The command names, then `intake`, which lists the sections of the intake procedure.
    let listed: Vec<&str> = NAMES.into_iter().chain(["intake"]).collect();
    assert_eq!(
        execute(&contract, &Map::new(), &json!({"help": {}})).unwrap().result(),
        &json!({"help": {"type": "object", "properties": {"help": {"enum": listed}}, "required": ["help"]}})
    );
}

/// `{"help": "intake"}` lists the sections of the intake procedure in reading order, and
/// `{"help": "intake/<section>"}` returns one section's text. A name the procedure does not
/// hold is refused with the command that lists the sections.
///
/// This test reads the list from the procedure itself. It asserts nothing about which sections
/// exist, what they are named, which are required or what they say, so the founder can edit,
/// rename, add and remove sections without a test failing.
#[test]
fn help_serves_the_intake_procedure_one_section_at_a_time() {
    let contract = Contract::bundled().unwrap();
    let sections = metaform_core::procedure::sections();
    let listing = execute(&contract, &Map::new(), &json!({"help": "intake"})).unwrap();
    let names: Vec<&str> = sections.iter().map(|s| s.name).collect();
    let required: Vec<&str> = sections.iter().filter(|s| s.required).map(|s| s.name).collect();
    assert_eq!(listing.result()["help"]["intake"]["sections"], json!(names));
    assert_eq!(listing.result()["help"]["intake"]["required"], json!(required));
    for section in sections.iter().filter(|s| !s.when.is_empty()) {
        assert_eq!(listing.result()["help"]["intake"]["when"][section.name], json!(section.when));
    }
    for section in &sections {
        let key = format!("intake/{}", section.name);
        let answer = execute(&contract, &Map::new(), &json!({"help": key})).unwrap();
        assert_eq!(answer.result()["help"][&key], json!(section.text));
    }
    let unknown = execute(&contract, &Map::new(), &json!({"help": "intake/no such section"})).unwrap_err();
    assert_eq!(unknown.code, Code::FieldMismatch);
    assert_eq!(unknown.remediation.as_deref(), Some(&json!({"help": "intake"})));
}

/// A command name answers in one piece: what the command does, and examples. Every example is
/// a command the tool takes: none is refused for its form.
#[test]
fn help_with_a_command_name_says_what_it_does_and_gives_examples_the_tool_takes() {
    let contract = Contract::bundled().unwrap();
    for name in NAMES {
        let answer = help(&contract, name);
        assert!(answer["does"].as_str().is_some_and(|text| !text.is_empty()), "{name} says what it does");
        let examples = answer["examples"].as_array().unwrap_or_else(|| panic!("{name} has examples"));
        assert!(!examples.is_empty(), "{name} has an example");
        for example in examples {
            if let Err(refusal) = execute(&contract, &Map::new(), example) {
                assert!(
                    !matches!(refusal.code, Code::FieldMismatch | Code::WantIncomplete),
                    "{name}: the example {example} is refused for its form: {}",
                    refusal.reason
                );
            }
        }
    }
}

/// A definition name answers with the contract's own definition.
#[test]
fn help_with_a_definition_name_returns_the_contracts_definition() {
    let contract = Contract::bundled().unwrap();
    let input = &contract.tool()["inputSchema"];
    for (definition, node) in input["$defs"].as_object().unwrap() {
        assert_eq!(&help(&contract, definition), node, "{definition}");
    }
}

/// A name that help does not hold is refused with the command that lists the names.
#[test]
fn help_with_an_unknown_name_is_refused() {
    let contract = Contract::bundled().unwrap();
    let refusal = execute(&contract, &Map::new(), &json!({"help": "no such name"})).unwrap_err();
    assert_eq!(refusal.code, Code::FieldMismatch);
    assert_eq!(refusal.reason, MESSAGE);
    assert_eq!(refusal.remediation.as_deref(), Some(&json!({"help": {}})));
}
