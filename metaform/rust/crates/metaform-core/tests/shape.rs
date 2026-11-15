//! The shape check (`src/shape.rs`): every rule of its inventory has at least one row here. A row
//! is the rule, a command, and the message and remediation an agent receives.

use metaform_core::{Code, Contract, Map, execute};
use serde_json::{Value, json};

/// A want record with the address of its other element under `end` (`element` or `element`).
#[allow(dead_code)]
fn with_end(end: &str, address: &str, record: impl std::borrow::Borrow<Value>) -> Value {
    let mut out = serde_json::Map::new();
    out.insert(end.to_string(), Value::String(address.to_string()));
    if let Value::Object(fields) = record.borrow() {
        out.extend(fields.clone());
    }
    Value::Object(out)
}

const NOT_AN_ADDRESS: &str = "is not an address: segments are joined by periods, with no spaces, '$', '[' or ']'";
const ONE_ENTRY: &str = "a command has one entry: add, update, delete, orphaned, goto, map, help, an address to read, or a path that starts with a period for a raw dump";
const DELETE_FORM: &str = "delete takes {} to delete the element, or {\"wants\": [\"<address>\"]} to remove wants";
const GOTO_FORM: &str = "goto takes one address, such as {\"goto\": \"code.engine.game\"}";

fn want() -> Value {
    json!({"why": "receive input", "how": "dispatches events", "direction": "receive"})
}

fn placeholder() -> Value {
    json!({"why": "<why>", "how": "<how>", "direction": "<direction>"})
}

/// Rule, command, message, remediation.
fn refused_rows() -> Vec<(&'static str, Value, String, Value)> {
    let game = "code.engine.game";
    let bus = "code.bus.data.event";
    let at_want = format!("the want '{bus}' at '{game}'");
    let read_form = |address: &str| {
        format!("a read names each layer with {{}} as its value, such as {{\"{address}\": {{\"wants\": {{}}}}}}")
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
        ("D3", json!({"delete": {"code.x": {"wants": ["code.y"], "other": 1}}}), DELETE_FORM.into(), json!(null)),
        ("D3", json!({"delete": {"code.x": null}}), DELETE_FORM.into(), json!(null)),
        ("D4", json!({"delete": {"code.x": {"wants": "no"}}}), DELETE_FORM.into(), json!({"delete": {"code.x": {"wants": ["no"]}}})),
        ("D4", json!({"delete": {"code.x": {"wants": []}}}), DELETE_FORM.into(), json!({"delete": {"code.x": {"wants": ["<address>"]}}})),
        ("D5", json!({"delete": {"code.x": {"wants": [7]}}}), DELETE_FORM.into(), json!({"delete": {"code.x": {"wants": ["<address>"]}}})),
        ("D5", json!({"delete": {"code.x": {"wants": ["code y"]}}}), format!("'code y' {NOT_AN_ADDRESS}"), json!(null)),
        ("D5", json!({"delete": {"code.x": {"wants": ["."]}}}), "the root cannot be wanted".into(), json!(null)),
        (
            "D5",
            json!({"delete": {"code.x": {"wants": ["code.y", "code.z", "code.y"]}}}),
            "delete names the want 'code.y' more than once".into(),
            json!({"delete": {"code.x": {"wants": ["code.y", "code.z"]}}}),
        ),
        ("E1", json!({"map": {"x": 1}}), "map takes {}".into(), json!({"map": {}})),
        ("E1", json!({"orphaned": []}), "orphaned takes {}".into(), json!({"orphaned": {}})),
        ("H1", json!({"help": {"x": 1}}), "help takes {}, the name of a command, the name of a definition a schema refers to, or intake".into(), json!({"help": {}})),
        ("H1", json!({"help": ""}), "help takes {}, the name of a command, the name of a definition a schema refers to, or intake".into(), json!({"help": {}})),
        ("G1", json!({"goto": 7}), GOTO_FORM.into(), json!({"goto": "<address>"})),
        ("G1", json!({"goto": ""}), GOTO_FORM.into(), json!({"goto": "<address>"})),
        ("G1", json!({"goto": "code engine"}), format!("'code engine' {NOT_AN_ADDRESS}"), json!(null)),
        ("R1", json!({"..": {}}), format!("'..' {NOT_AN_ADDRESS}"), json!(null)),
        ("R1", json!({".code.": {}}), format!("'.code.' {NOT_AN_ADDRESS}"), json!(null)),
        ("R2", json!({".code": {"wants": {}}}), "a raw dump takes {}".into(), json!({".code": {}})),
        ("L1", json!({"code.$x": {}}), format!("'code.$x' {NOT_AN_ADDRESS}"), json!(null)),
        ("L1", json!({"code..x": {}}), format!("'code..x' {NOT_AN_ADDRESS}"), json!(null)),
        ("L1", json!({"": {}}), format!("'' {NOT_AN_ADDRESS}"), json!(null)),
        ("L2", json!({game: "wants"}), read_form(game), json!({game: {}})),
        (
            "L3",
            json!({"remove": {"code.x": {}}}),
            "'code.x' is not a layer name: a layer name is one segment, with no periods, spaces, '$', '[' or ']'".into(),
            json!(null),
        ),
        ("L4", json!({game: {"wants": []}}), read_form(game), json!({game: {"wants": {}}})),
        ("L4", json!({game: {"wants": [1]}}), read_form(game), json!({game: {"wants": {}}})),
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
            json!({"update": {game: {"role": "<Artifact Type, Defining Element, Supporting Element, Coupled Element, Notable Element, Cestui Que Use, Upstream Dependency or Downstream Dependant>"}}}),
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
        // The intake procedure's words are answered with the same command in the tool's words.
        (
            "W3",
            json!({"add": {game: {"wants": [{"pe": bus, "op": "receive input", "ef": "dispatches events", "ifd": "receive"}]}}}),
            format!("a want at '{game}' takes element, why, how and direction; the command used pe, op, ef, ifd"),
            json!({"add": {game: {"wants": [with_end("element", bus, want())]}}}),
        ),
        (
            "W3",
            json!({"add": {game: {"dependencies": [{"provider": bus, "purpose": "receive input", "ef": "dispatches events", "ifd": "receives"}]}}}),
            format!("dependencies at '{game}' is not a field; wants holds what the procedure calls dependency records"),
            json!({"add": {game: {"wants": [with_end("element", bus, want())]}}}),
        ),
        (
            "N6",
            json!({"update": {game: {"purpose": "receive input", "ef": "dispatches events", "provider": bus, "ifd": "receive"}}}),
            format!("purpose at '{game}' is not a field of an element; element, why, how and direction belong in a want"),
            json!({"update": {game: {"wants": [with_end("element", bus, want())]}}}),
        ),
        (
            "W5",
            json!({"add": {game: {"wants": [{"element": bus, "why": "receive input", "how": "dispatches events", "direction": "receives"}]}}}),
            format!("direction at the want '{bus}' at '{game}' must be send, receive or both"),
            json!({"add": {game: {"wants": [{"element": bus, "why": "receive input", "how": "dispatches events", "direction": "receive"}]}}}),
        ),
        (
            "W1",
            json!({"add": {game: {"wants": {bus: {"why": "receive input", "how": "dispatches events", "direction": "receive"}}}}}),
            format!("wants at '{game}' must be a list of want records; each record names the element it wants in element"),
            json!({"add": {game: {"wants": [{"element": bus, "why": "receive input", "how": "dispatches events", "direction": "receive"}]}}}),
        ),
        (
            "N6",
            json!({"update": {game: {"why": "receive input"}}}),
            format!("why at '{game}' is not a field of an element; element, why, how and direction belong in a want"),
            json!({"update": {game: {"wants": [{"element": "<address>", "why": "receive input", "how": "<how>", "direction": "<direction>"}]}}}),
        ),
        (
            "N6",
            json!({"add": {game: {"direction": "receive"}}}),
            format!("direction at '{game}' is not a field of an element; element, why, how and direction belong in a want"),
            json!({"update": {game: {"wants": [{"element": "<address>", "why": "<why>", "how": "<how>", "direction": "receive"}]}}}),
        ),
        (
            "N7",
            json!({"update": {game: {"providers": ["code.bus"]}}}),
            format!("providers at '{game}' can hold only elements beneath it; wants holds what an element wants"),
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
            json!({"add": {"code.engine": {"game": {"wants": [{"element": bus, "why": "receive input", "how": "", "direction": "receive"}]}}}}),
            format!("how at the want '{bus}' at '{game}' must be text that is not blank"),
            json!({"add": {"code.engine": {"game": {"wants": [{"element": bus, "why": "receive input", "how": "<how>", "direction": "receive"}]}}}}),
        ),
        (
            "N10",
            json!({"add": {"code.engine": {"game": {"wants": ["code.bus"]}}}}),
            format!("a want at '{game}' must be a record with element, why, how and direction"),
            json!({"add": {"code.engine": {"game": {"wants": [with_end("element", "<address>", placeholder())]}}}}),
        ),
        (
            "W1",
            json!({"add": {"code.x": {"wants": ["code.y"]}}}),
            "a want at 'code.x' must be a record with element, why, how and direction".into(),
            json!({"add": {"code.x": {"wants": [with_end("element", "<address>", placeholder())]}}}),
        ),
        ("W1", json!({"update": {game: {"wants": [with_end("element", "code y", want())]}}}), format!("'code y' {NOT_AN_ADDRESS}"), json!(null)),
        ("W1", json!({"update": {game: {"wants": [with_end("element", ".", want())]}}}), "the root cannot be wanted".into(), json!(null)),
        (
            "W2",
            json!({"add": {"code.x": {"wants": [{"why": "receive input"}]}}}),
            "a want at 'code.x' must name the element it wants in element".into(),
            json!({"add": {"code.x": {"wants": [{"element": "<address>", "why": "receive input"}]}}}),
        ),
        (
            "W8",
            json!({"add": {"code.x": {"wants": []}}}),
            "wants at 'code.x' must be a list of want records, each with element, why, how and direction".into(),
            json!({"add": {"code.x": {"wants": [with_end("element", "<address>", placeholder())]}}}),
        ),
        (
            "W3",
            json!({"update": {game: {"wants": [{"element": bus, "why": "receive input", "how": "dispatches events", "direction": "receive", "note": "extra"}]}}}),
            format!("{at_want} does not take: note"),
            json!({"update": {game: {"wants": [with_end("element", bus, want())]}}}),
        ),
        (
            "W3",
            json!({"update": {game: {"wants": [{"element": bus, "goal": "x", "function": "y"}]}}}),
            format!("{at_want} does not take: goal, function"),
            json!(null),
        ),
        (
            "W5",
            json!({"update": {game: {"wants": [{"element": bus, "direction": "sideways"}]}}}),
            format!("direction at {at_want} must be send, receive or both"),
            json!({"update": {game: {"wants": [{"element": bus, "direction": "<send, receive or both>"}]}}}),
        ),
        (
            "W4",
            json!({"update": {game: {"wants": [{"element": bus, "why": "   "}]}}}),
            format!("why at {at_want} must be text that is not blank"),
            json!({"update": {game: {"wants": [{"element": bus, "why": "<why>"}]}}}),
        ),
        (
            "W7",
            json!({"update": {game: {"wants": [{"element": bus}]}}}),
            format!("{at_want} has no fields; give why, how or direction"),
            json!({"update": {game: {"wants": [with_end("element", bus, placeholder())]}}}),
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
        for leak in ["Single(", "Multiple(", "/add", "/update", "/delete", "/goto", "/wants", "must hold at"] {
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
/// shape of the value, then each field in the command's order. A want that `add` leaves
/// incomplete has the code and message of one that `update` leaves incomplete (W6, R-5.6).
#[test]
fn the_first_problem_in_the_fixed_order_is_reported() {
    let contract = Contract::bundled().unwrap();
    let map = Map::new();
    let reason = |command: Value| execute(&contract, &map, &command).unwrap_err().reason;
    // The address comes before the shape of the value, and that before a field.
    assert!(reason(json!({"add": {"code x": "text"}})).starts_with("'code x' is not an address"));
    assert_eq!(reason(json!({"delete": {".": {"wants": "no"}}})), "the root cannot be deleted");
    // Fields are reported in the command's order, whatever their names.
    assert!(reason(json!({"update": {"code.x": {"status": "todo", "name": ""}}})).starts_with("status at"));
    assert!(reason(json!({"update": {"code.x": {"name": "", "status": "todo"}}})).starts_with("name at"));
    // An element beneath is checked before the next field of the element above.
    assert!(reason(json!({"add": {"code.x": {"part": {"refs": 7}, "name": ""}}})).starts_with("refs at 'code.x.part'"));
    // In a want: names it does not take, then fields in order, then missing fields.
    let record = json!({"direction": "up", "why": "", "note": 1});
    assert!(reason(json!({"add": {"code.x": {"wants": [with_end("element", "code.y", &record)]}}})).contains("does not take: note"));
    assert!(reason(json!({"add": {"code.x": {"wants": [{"element": "code.y", "direction": "up", "why": ""}]}}})).starts_with("direction at"));
    let incomplete = execute(&contract, &map, &json!({"add": {"code.x": {"wants": [{"element": "code.y", "why": "receive input"}]}}})).unwrap_err();
    assert_eq!(incomplete.code, Code::WantIncomplete);
    assert_eq!(incomplete.reason, "'code.x' wants 'code.y': the want has no how, direction");
    assert_eq!(
        incomplete.to_json()["remediation"],
        json!({"add": {"code.x": {"wants": [{"element": "code.y", "why": "receive input", "how": "<how>", "direction": "<direction>"}]}}})
    );
}

/// What the rules permit is accepted: `null` at `update`'s own element (N8), lists and elements
/// beneath at the text fields (N2, N9), wants at an element beneath (N10), and every command form.
#[test]
fn commands_of_the_right_shape_pass_the_shape_check() {
    let contract = Contract::bundled().unwrap();
    let mut map = Map::new();
    for command in [
        json!({"add": {"code.engine.game": {"technical_name": "game engine", "name": "Quake core", "role": "Defining Element", "refs": ["./src/engine.c"], "status": "un_built"}}}),
        json!({"update": {"code.engine.game": {"status": null, "refs": null, "note": null, "why": null}}}),
        json!({"update": {"code.engine.game": {"wants": [with_end("element", "code.bus", want())]}}}),
        json!({"update": {"code.engine.game": {"wants": [{"element": "code.bus", "direction": "both"}]}}}),
        json!({"add": {"code": {"engine": {"audio": {"name": "Mixer", "wants": [with_end("element", "code.bus", want())]}}}}}),
        json!({"update": {".": {"note": "the project"}}}),
        json!({"delete": {"code.engine.game": {"wants": ["code.bus"]}}}),
        json!({"delete": {"code.engine.audio": {}}}),
    ] {
        match execute(&contract, &map, &command) {
            Ok(metaform_core::Outcome::Write(write)) => map = write.map,
            other => panic!("{command} should write, got {other:?}"),
        }
    }
    for command in [
        json!({"map": {}}), json!({"orphaned": {}}), json!({"help": {}}), json!({"help": "raw dump"}), json!({"help": "WantRecord"}), json!({"goto": "."}), json!({"goto": "code.engine.game"}),
        json!({".": {}}), json!({".code.engine": {}}), json!({"code.engine.game": {}}),
        json!({"code.engine.game": {"wants": {}, "specification": {}}}),
    ] {
        assert!(execute(&contract, &map, &command).is_ok(), "{command}");
    }
}
