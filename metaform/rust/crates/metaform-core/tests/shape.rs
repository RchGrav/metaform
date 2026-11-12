//! The shape check (`src/shape.rs`): every rule of its inventory has at least one row here. A row
//! is the rule, a command, and the message and remediation an agent receives.

use metaform_core::{Code, Contract, Map, execute};
use serde_json::{Value, json};

const NOT_AN_ADDRESS: &str = "is not an address: segments are joined by periods, with no spaces, '$', '[' or ']'";
const ONE_ENTRY: &str = "a command has one entry: add, update, delete, orphaned, goto, map, help, an address to read, or a path that starts with a period for a raw dump";
const DELETE_FORM: &str = "delete takes {} to delete the element, or {\"dependencies\": [\"<address>\"]} to remove dependencies";
const GOTO_FORM: &str = "goto takes one address, such as {\"goto\": \"code.engine.game\"}";

fn dependency() -> Value {
    json!({"op": "receive input", "ef": "dispatches events", "ifd": "receive"})
}

fn placeholder() -> Value {
    json!({"op": "<op>", "ef": "<ef>", "ifd": "<ifd>"})
}

/// Rule, command, message, remediation.
fn refused_rows() -> Vec<(&'static str, Value, String, Value)> {
    let game = "code.engine.game";
    let bus = "code.bus.data.event";
    let at_dependency = format!("the dependency '{bus}' at '{game}'");
    let read_form = |address: &str| {
        format!("a read names each layer with {{}} as its value, such as {{\"{address}\": {{\"dependencies\": {{}}}}}}")
    };
    let mut rows = vec![
        ("C1", json!({}), ONE_ENTRY.to_string(), json!(null)),
        ("C1", json!({"add": {}, "map": {}}), ONE_ENTRY.into(), json!(null)),
        ("C1", json!(["add"]), ONE_ENTRY.into(), json!(null)),
        ("C2", json!({"code engine": {}}), format!("'code engine' {NOT_AN_ADDRESS}"), json!(null)),
        ("A1", json!({"add": {}}), "add takes one address; send one command for each element".into(), json!(null)),
        ("A1", json!({"update": "code.x"}), "update takes one address; send one command for each element".into(), json!(null)),
        (
            "A1",
            json!({"add": {"code.a": {"x": "1"}, "code.b": {"x": "2"}}}),
            "add takes one address; send one command for each element".into(),
            json!({"add": {"code.a": {"x": "1"}}}),
        ),
        ("A2", json!({"add": {"code..x": {"name": "n"}}}), format!("'code..x' {NOT_AN_ADDRESS}"), json!(null)),
        ("A2", json!({"update": {"code.x[0]": {"name": "n"}}}), format!("'code.x[0]' {NOT_AN_ADDRESS}"), json!(null)),
        ("A3", json!({"add": {"code.x": "text"}}), "add takes an object of fields at 'code.x'".into(), json!(null)),
        ("A3", json!({"update": {"code.x": []}}), "update takes an object of fields at 'code.x'".into(), json!(null)),
        ("A3", json!({"update": {"code.x": {}}}), "update needs at least one field at 'code.x'".into(), json!(null)),
        ("D1", json!({"delete": {}}), "delete takes one address; send one command for each element".into(), json!(null)),
        (
            "D1",
            json!({"delete": {"code.a": {}, "code.b": {}}}),
            "delete takes one address; send one command for each element".into(),
            json!({"delete": {"code.a": {}}}),
        ),
        ("D2", json!({"delete": {".": {}}}), "the root cannot be deleted".into(), json!(null)),
        ("D2", json!({"delete": {"code x": {}}}), format!("'code x' {NOT_AN_ADDRESS}"), json!(null)),
        ("D3", json!({"delete": {"code.x": {"other": 1}}}), DELETE_FORM.into(), json!(null)),
        ("D3", json!({"delete": {"code.x": {"dependencies": ["code.y"], "other": 1}}}), DELETE_FORM.into(), json!(null)),
        ("D3", json!({"delete": {"code.x": null}}), DELETE_FORM.into(), json!(null)),
        ("D4", json!({"delete": {"code.x": {"dependencies": "no"}}}), DELETE_FORM.into(), json!({"delete": {"code.x": {"dependencies": ["no"]}}})),
        ("D4", json!({"delete": {"code.x": {"dependencies": []}}}), DELETE_FORM.into(), json!({"delete": {"code.x": {"dependencies": ["<address>"]}}})),
        ("D5", json!({"delete": {"code.x": {"dependencies": [7]}}}), DELETE_FORM.into(), json!({"delete": {"code.x": {"dependencies": ["<address>"]}}})),
        ("D5", json!({"delete": {"code.x": {"dependencies": ["code y"]}}}), format!("'code y' {NOT_AN_ADDRESS}"), json!(null)),
        ("D5", json!({"delete": {"code.x": {"dependencies": ["."]}}}), "the root cannot be depended on".into(), json!(null)),
        (
            "D5",
            json!({"delete": {"code.x": {"dependencies": ["code.y", "code.z", "code.y"]}}}),
            "delete names the dependency 'code.y' more than once".into(),
            json!({"delete": {"code.x": {"dependencies": ["code.y", "code.z"]}}}),
        ),
        ("E1", json!({"map": {"x": 1}}), "map takes {}".into(), json!({"map": {}})),
        ("E1", json!({"orphaned": []}), "orphaned takes {}".into(), json!({"orphaned": {}})),
        ("H1", json!({"help": {"x": 1}}), "help takes {}, the name of a command, or the name of a definition a schema refers to".into(), json!({"help": {}})),
        ("H1", json!({"help": ""}), "help takes {}, the name of a command, or the name of a definition a schema refers to".into(), json!({"help": {}})),
        ("G1", json!({"goto": 7}), GOTO_FORM.into(), json!({"goto": "<address>"})),
        ("G1", json!({"goto": ""}), GOTO_FORM.into(), json!({"goto": "<address>"})),
        ("G1", json!({"goto": "code engine"}), format!("'code engine' {NOT_AN_ADDRESS}"), json!(null)),
        ("R1", json!({"..": {}}), format!("'..' {NOT_AN_ADDRESS}"), json!(null)),
        ("R1", json!({".code.": {}}), format!("'.code.' {NOT_AN_ADDRESS}"), json!(null)),
        ("R2", json!({".code": {"dependencies": {}}}), "a raw dump takes {}".into(), json!({".code": {}})),
        ("L1", json!({"code.$x": {}}), format!("'code.$x' {NOT_AN_ADDRESS}"), json!(null)),
        ("L1", json!({"code..x": {}}), format!("'code..x' {NOT_AN_ADDRESS}"), json!(null)),
        ("L1", json!({"": {}}), format!("'' {NOT_AN_ADDRESS}"), json!(null)),
        ("L2", json!({game: "dependencies"}), read_form(game), json!({game: {}})),
        (
            "L3",
            json!({"remove": {"code.x": {}}}),
            "'code.x' is not a layer name: a layer name is one segment, with no periods, spaces, '$', '[' or ']'".into(),
            json!(null),
        ),
        ("L4", json!({game: {"dependencies": []}}), read_form(game), json!({game: {"dependencies": {}}})),
        ("L4", json!({game: {"dependencies": {"x": 1}}}), read_form(game), json!({game: {"dependencies": {}}})),
        ("L4", json!({"search": {"text": "x"}}), read_form("search"), json!({"search": {"text": {}}})),
        (
            "N1",
            json!({"update": {"code.x": {"a.b": 1}}}),
            "'a.b' at 'code.x' is not a field name: a name is one segment, with no periods, spaces, '$', '[' or ']'".into(),
            json!(null),
        ),
        (
            "N3",
            json!({"update": {game: {"role": 7}}}),
            format!("role at '{game}' must be text that is not blank"),
            json!({"update": {game: {"role": "<AT, DE, SE, NE, CQU, UD or DD>"}}}),
        ),
        (
            "N4",
            json!({"update": {game: {"name": "Quake core", "status": "todo"}}}),
            format!("status at '{game}' cannot be \"todo\"; use un_built for functionality that is not built"),
            json!({"update": {game: {"name": "Quake core", "status": "un_built"}}}),
        ),
        (
            "N5",
            json!({"add": {game: {"uri": "./src/engine.c"}}}),
            format!("uri at '{game}' is not a field; refs holds a list with one uri for each artifact that has this address"),
            json!({"add": {game: {"refs": ["./src/engine.c"]}}}),
        ),
        (
            "N5",
            json!({"add": {game: {"refs": "./src/engine.c"}}}),
            format!("refs at '{game}' must be a list with one uri for each artifact that has this address"),
            json!({"add": {game: {"refs": ["./src/engine.c"]}}}),
        ),
        (
            "N5",
            json!({"add": {game: {"refs": []}}}),
            format!("refs at '{game}' must be a list with one uri for each artifact that has this address"),
            json!({"add": {game: {"refs": ["<uri>"]}}}),
        ),
        (
            "W5",
            json!({"add": {game: {"dependencies": {bus: {"op": "receive input", "ef": "dispatches events", "ifd": "receives"}}}}}),
            format!("ifd at the dependency '{bus}' at '{game}' must be send, receive or both"),
            json!({"add": {game: {"dependencies": {bus: {"op": "receive input", "ef": "dispatches events", "ifd": "receive"}}}}}),
        ),
        (
            "W1",
            json!({"add": {game: {"dependencies": [{"pe": bus, "op": "receive input", "ef": "dispatches events", "ifd": "receive"}]}}}),
            format!("dependencies at '{game}' must be an object keyed by the address of each providing element (pe)"),
            json!({"add": {game: {"dependencies": {bus: {"op": "receive input", "ef": "dispatches events", "ifd": "receive"}}}}}),
        ),
        (
            "N6",
            json!({"update": {game: {"op": "receive input"}}}),
            format!("op at '{game}' is not a field of an element; op, ef and ifd belong in a dependency"),
            json!({"update": {game: {"dependencies": {"<address>": {"op": "receive input", "ef": "<ef>", "ifd": "<ifd>"}}}}}),
        ),
        (
            "N6",
            json!({"add": {game: {"ifd": "receive"}}}),
            format!("ifd at '{game}' is not a field of an element; op, ef and ifd belong in a dependency"),
            json!({"update": {game: {"dependencies": {"<address>": {"op": "<op>", "ef": "<ef>", "ifd": "receive"}}}}}),
        ),
        (
            "N7",
            json!({"update": {game: {"providers": ["code.bus"]}}}),
            format!("providers at '{game}' can hold only elements beneath it; dependencies holds what an element depends on"),
            json!(null),
        ),
        (
            "N8",
            json!({"add": {game: {"name": null}}}),
            format!("name at '{game}' must be text that is not blank"),
            json!({"add": {game: {"name": "<name>"}}}),
        ),
        (
            "N8",
            json!({"update": {"code.engine": {"game": {"status": null}}}}),
            format!("status at '{game}' must be text that is not blank"),
            json!({"update": {"code.engine": {"game": {"status": "<status>"}}}}),
        ),
        (
            "N9",
            json!({"add": {"code": {"engine": {"game": {"technical_name": "  "}}}}}),
            format!("technical_name at '{game}' must be text that is not blank"),
            json!({"add": {"code": {"engine": {"game": {"technical_name": "<technical_name>"}}}}}),
        ),
        (
            "N10",
            json!({"add": {"code.engine": {"game": {"dependencies": {bus: {"op": "receive input", "ef": "", "ifd": "receive"}}}}}}),
            format!("ef at the dependency '{bus}' at '{game}' must be text that is not blank"),
            json!({"add": {"code.engine": {"game": {"dependencies": {bus: {"op": "receive input", "ef": "<ef>", "ifd": "receive"}}}}}}),
        ),
        (
            "N10",
            json!({"add": {"code.engine": {"game": {"dependencies": ["code.bus"]}}}}),
            format!("dependencies at '{game}' must be an object of dependency records keyed by address"),
            json!({"add": {"code.engine": {"game": {"dependencies": {"<address>": placeholder()}}}}}),
        ),
        (
            "W1",
            json!({"add": {"code.x": {"dependencies": ["code.y"]}}}),
            "dependencies at 'code.x' must be an object of dependency records keyed by address".into(),
            json!({"add": {"code.x": {"dependencies": {"<address>": placeholder()}}}}),
        ),
        ("W1", json!({"update": {game: {"dependencies": {"code y": dependency()}}}}), format!("'code y' {NOT_AN_ADDRESS}"), json!(null)),
        ("W1", json!({"update": {game: {"dependencies": {".": dependency()}}}}), "the root cannot be depended on".into(), json!(null)),
        (
            "W2",
            json!({"add": {"code.x": {"dependencies": {"code.y": "text"}}}}),
            "the dependency 'code.y' at 'code.x' must be a record with op, ef and ifd".into(),
            json!({"add": {"code.x": {"dependencies": {"code.y": placeholder()}}}}),
        ),
        (
            "W3",
            json!({"update": {game: {"dependencies": {bus: {"op": "receive input", "ef": "dispatches events", "ifd": "receive", "note": "extra"}}}}}),
            format!("{at_dependency} does not take: note"),
            json!({"update": {game: {"dependencies": {bus: dependency()}}}}),
        ),
        (
            "W3",
            json!({"update": {game: {"dependencies": {bus: {"goal": "x", "function": "y"}}}}}),
            format!("{at_dependency} does not take: goal, function"),
            json!(null),
        ),
        (
            "W5",
            json!({"update": {game: {"dependencies": {bus: {"ifd": "sideways"}}}}}),
            format!("ifd at {at_dependency} must be send, receive or both"),
            json!({"update": {game: {"dependencies": {bus: {"ifd": "<send, receive or both>"}}}}}),
        ),
        (
            "W4",
            json!({"update": {game: {"dependencies": {bus: {"op": "   "}}}}}),
            format!("op at {at_dependency} must be text that is not blank"),
            json!({"update": {game: {"dependencies": {bus: {"op": "<op>"}}}}}),
        ),
        (
            "W7",
            json!({"update": {game: {"dependencies": {bus: {}}}}}),
            format!("{at_dependency} has no fields; give op, ef or ifd"),
            json!({"update": {game: {"dependencies": {bus: placeholder()}}}}),
        ),
    ];
    // N2, N4, N5: a blank or non-text value at each field that holds text.
    for field in ["technical_name", "name", "project", "status"] {
        for value in [json!(""), json!(7), json!(true)] {
            rows.push((
                "N2",
                json!({"update": {game: {field: value}}}),
                format!("{field} at '{game}' must be text that is not blank"),
                json!({"update": {game: {field: format!("<{field}>")}}}),
            ));
        }
    }
    for status in ["missing", "MISSING", "BKN", "broken", "todo", "TODO"] {
        rows.push((
            "N4",
            json!({"update": {game: {"status": status}}}),
            format!("status at '{game}' cannot be \"{status}\"; use un_built for functionality that is not built"),
            json!({"update": {game: {"status": "un_built"}}}),
        ));
    }
    rows
}

#[test]
fn a_command_of_the_wrong_shape_is_refused_in_plain_words() {
    let contract = Contract::bundled().unwrap();
    let map = Map::new();
    for (rule, command, message, remediation) in refused_rows() {
        let refusal = match execute(&contract, &map, &command) {
            Err(refusal) => refusal,
            Ok(outcome) => panic!("{rule} {command} should be refused, got {outcome:?}"),
        };
        assert_eq!(refusal.code, Code::FieldMismatch, "{rule} {command}");
        assert_eq!(refusal.reason, message, "{rule} {command}");
        assert_eq!(refusal.to_json()["remediation"], remediation, "{rule} {command}");
        for leak in ["Single(", "Multiple(", "/add", "/update", "/delete", "/goto", "/dependencies", "must hold at"] {
            assert!(!refusal.reason.contains(leak), "{rule} {command}: {}", refusal.reason);
        }
        // A remediation with no placeholder is a command the shape check accepts.
        if !remediation.is_null()
            && !remediation.to_string().contains('<')
            && let Err(again) = execute(&contract, &map, &remediation)
        {
            assert_ne!(again.code, Code::FieldMismatch, "{rule} {command}: {remediation} is refused: {}", again.reason);
        }
    }
}

/// The first problem is reported, in the module's order: entries, command name, address, the
/// shape of the value, then each field in the command's order. A dependency that `add` leaves
/// incomplete has the code and message of one that `update` leaves incomplete (W6, R-5.6).
#[test]
fn the_first_problem_in_the_fixed_order_is_reported() {
    let contract = Contract::bundled().unwrap();
    let map = Map::new();
    let reason = |command: Value| execute(&contract, &map, &command).unwrap_err().reason;
    // The address comes before the shape of the value, and that before a field.
    assert!(reason(json!({"add": {"code x": "text"}})).starts_with("'code x' is not an address"));
    assert_eq!(reason(json!({"delete": {".": {"dependencies": "no"}}})), "the root cannot be deleted");
    // Fields are reported in the command's order, whatever their names.
    assert!(reason(json!({"update": {"code.x": {"status": "todo", "name": ""}}})).starts_with("status at"));
    assert!(reason(json!({"update": {"code.x": {"name": "", "status": "todo"}}})).starts_with("name at"));
    // An element beneath is checked before the next field of the element above.
    assert!(reason(json!({"add": {"code.x": {"part": {"refs": 7}, "name": ""}}})).starts_with("refs at 'code.x.part'"));
    // In a dependency: names it does not take, then fields in order, then missing fields.
    let record = json!({"ifd": "up", "op": "", "note": 1});
    assert!(reason(json!({"add": {"code.x": {"dependencies": {"code.y": record}}}})).contains("does not take: note"));
    assert!(reason(json!({"add": {"code.x": {"dependencies": {"code.y": {"ifd": "up", "op": ""}}}}})).starts_with("ifd at"));
    let incomplete = execute(&contract, &map, &json!({"add": {"code.x": {"dependencies": {"code.y": {"op": "receive input"}}}}})).unwrap_err();
    assert_eq!(incomplete.code, Code::DependencyIncomplete);
    assert_eq!(incomplete.reason, "'code.x' depends on 'code.y': the dependency has no ef, ifd");
    assert_eq!(
        incomplete.to_json()["remediation"],
        json!({"add": {"code.x": {"dependencies": {"code.y": {"op": "receive input", "ef": "<ef>", "ifd": "<ifd>"}}}}})
    );
}

/// What the rules permit is accepted: `null` at `update`'s own element (N8), lists and elements
/// beneath at the text fields (N2, N9), a `dependencies` branch beneath (N10), and every command form.
#[test]
fn commands_of_the_right_shape_pass_the_shape_check() {
    let contract = Contract::bundled().unwrap();
    let mut map = Map::new();
    for command in [
        json!({"add": {"code.engine.game": {"technical_name": "game engine", "name": "Quake core", "role": "DE", "refs": ["./src/engine.c"], "status": "un_built"}}}),
        json!({"update": {"code.engine.game": {"status": null, "refs": null, "note": null, "op": null}}}),
        json!({"update": {"code.engine.game": {"dependencies": {"code.bus": dependency()}}}}),
        json!({"update": {"code.engine.game": {"dependencies": {"code.bus": {"ifd": "both"}}}}}),
        json!({"add": {"code": {"engine": {"audio": {"name": "Mixer", "dependencies": {"code.bus": dependency()}}}}}}),
        json!({"add": {"code": {"relay": {"dependencies": {"queue": {"name": "Wanted queue"}}}}}}),
        json!({"update": {".": {"note": "the project"}}}),
        json!({"delete": {"code.engine.game": {"dependencies": ["code.bus"]}}}),
        json!({"delete": {"code.engine.audio": {}}}),
    ] {
        match execute(&contract, &map, &command) {
            Ok(metaform_core::Outcome::Write(write)) => map = write.map,
            other => panic!("{command} should write, got {other:?}"),
        }
    }
    assert!(map.element("code.relay.dependencies.queue").is_some(), "dependencies beneath is a branch when it holds no dependency fields");
    for command in [
        json!({"map": {}}), json!({"orphaned": {}}), json!({"help": {}}), json!({"help": "raw dump"}), json!({"help": "DependencyRecord"}), json!({"goto": "."}), json!({"goto": "code.engine.game"}),
        json!({".": {}}), json!({".code.engine": {}}), json!({"code.engine.game": {}}),
        json!({"code.engine.game": {"dependencies": {}, "specification": {}}}),
    ] {
        assert!(execute(&contract, &map, &command).is_ok(), "{command}");
    }
}
