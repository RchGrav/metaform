//! Conformance tests of the public interface against the shared fixtures in `metaform/`.
//! Budget (`context/topogee-repo/CLAUDE.md`): at most five tests for this feature. This file holds four.

use std::fs;
use std::path::PathBuf;

use metaform_core::{Code, Contract, Effect, Map, MapRef, Outcome, Refusal, execute};
use serde_json::{Value, json};

/// A want record with the address of its other element under `end` (`pe` or `re`).
#[allow(dead_code)]
fn with_end(end: &str, address: &str, record: impl std::borrow::Borrow<Value>) -> Value {
    let mut out = serde_json::Map::new();
    out.insert(end.to_string(), Value::String(address.to_string()));
    if let Value::Object(fields) = record.borrow() {
        out.extend(fields.clone());
    }
    Value::Object(out)
}

fn fixture(name: &str) -> Value {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../..")
        .join(name);
    serde_json::from_slice(&fs::read(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display())))
        .unwrap()
}

fn seeded() -> Map {
    Map::from_document(&fixture("intake-example.json"))
        .unwrap()
        .1
}

/// Perform a write, check that its effect turns the old map into the new one, and return the new map.
fn write(contract: &Contract, map: &Map, command: Value) -> Map {
    match execute(contract, map, &command) {
        Ok(Outcome::Write(write)) => {
            assert_eq!(
                map.apply(&write.effect),
                write.map,
                "the effect of {command}"
            );
            write.map
        }
        other => panic!("{command} should write, got {other:?}"),
    }
}

fn read(contract: &Contract, map: &Map, command: Value) -> Value {
    match execute(contract, map, &command) {
        Ok(Outcome::Read(result)) => result,
        other => panic!("{command} should read, got {other:?}"),
    }
}

fn refused(contract: &Contract, map: &Map, command: &Value) -> Refusal {
    match execute(contract, map, command) {
        Err(refusal) => refusal,
        Ok(outcome) => panic!("{command} should be refused, got {outcome:?}"),
    }
}

/// Every request and expected refusal in `metaform/tool-examples.json`.
#[test]
fn tool_examples_give_the_documented_results() {
    let contract = Contract::bundled().unwrap();
    let examples = fixture("tool-examples.json");
    let requests = examples["requests"].as_array().unwrap();
    let error = &examples["referenced_delete_error"];
    // R-5.23: orphaned returns a bare dictionary keyed by address, as the fixture shows.
    let orphans = examples["orphan_result_example"].clone();

    // The add is a separate example, not a replay against the populated map.
    let added = write(&contract, &Map::new(), requests[0].clone());
    let holder = added.element("code.protocol.network.tracker.cs").unwrap();
    assert_eq!(
        holder.wants_json(),
        requests[0]["add"]["code.protocol.network.tracker.cs"]["wants"]
    );
    assert!(
        added.element("code.masher.widget").is_some(),
        "the want creates the element it names"
    );

    enum Expect {
        Refused(Code, Value, Value),
        Ok,
        Result(Value),
    }
    let table = [
        (
            1,
            Expect::Refused(
                Code::DependencyLock,
                error["message"].clone(),
                error["remediation"].clone(),
            ),
        ),
        (2, Expect::Ok),
        (3, Expect::Result(orphans)),
        (4, Expect::Ok),
        (
            5,
            Expect::Result(examples["read_after_role_removal"].clone()),
        ),
        (6, Expect::Ok),
    ];
    assert_eq!(
        table.len() + 1,
        requests.len(),
        "every request is in the table"
    );
    let mut map = seeded();
    for (index, expect) in table {
        let request = &requests[index];
        match (execute(&contract, &map, request), expect) {
            (Err(refusal), Expect::Refused(code, message, remediation)) => {
                assert_eq!(refusal.code, code, "request {index}");
                assert_eq!(
                    Value::String(refusal.reason.clone()),
                    message,
                    "request {index}"
                );
                assert_eq!(
                    refusal.remediation.as_deref(),
                    Some(&remediation),
                    "request {index}"
                );
                let shown = refusal.to_json();
                assert_eq!(shown["code"], "DEPENDENCY_LOCK");
                assert!(refusal.rule().starts_with("R-5.7"));
                assert!(
                    shown.get("rule").is_none(),
                    "the response has no rule field"
                );
            }
            (Ok(Outcome::Write(write)), Expect::Ok) => {
                assert_eq!(map.apply(&write.effect), write.map, "request {index}");
                map = write.map;
            }
            (Ok(Outcome::Read(result)), Expect::Result(expected)) => {
                assert_eq!(result, expected, "request {index}")
            }
            (got, _) => panic!("request {index} gave {got:?}"),
        }
    }
    // R-5.30: goto's summary sheet, against the populated initial state.
    let goto = &examples["goto_example"];
    assert_eq!(
        read(&contract, &seeded(), goto["request"].clone()),
        goto["first_result"]
    );

    // After the four-step delete (R-5.25), the element is gone and its empty branch with it.
    assert_eq!(refused(&contract, &map, &requests[5]).code, Code::NotFound);
    assert!(map.element("code.masher").is_none());
}

/// Documents round trip through the in-memory map (R-4.2). Storage is `metaform-store`'s job:
/// the JSON file store that stood here was never decided and is removed (R-4.1).
#[test]
fn documents_round_trip_through_the_map() {
    let document = fixture("intake-example.json");
    let (name, map) = Map::from_document(&document).unwrap();
    assert_eq!(map.to_document(&name), document);

    let (_, canonical) = Map::from_document(&fixture("metaform-canonical.json")).unwrap();
    let mut element = canonical.element("code").unwrap().clone();
    element.child_map = Some(MapRef("maps/code".into()));
    let chained = canonical.apply(&Effect {
        elements: [("code".to_string(), Some(element))].into(),
    });
    assert_eq!(
        chained.element("code").unwrap().child_map,
        Some(MapRef("maps/code".into()))
    );
}

/// Each refusal carries its fixed code and a remediation; a refused command changes nothing.
#[test]
fn refusals_name_the_rule_and_change_nothing() {
    let contract = Contract::bundled().unwrap();
    let map = seeded();
    let want =
        |direction: &str| json!({"op": "Relay it.", "ef": "Supplies data.", "ifd": direction});
    let table = [
        (
            json!({"add": {"Code.relay": {"role": "SE"}}}),
            Code::NameRoundTripFailure,
            Some(json!({"add": {"code.relay": {"role": "SE"}}})),
        ),
        (
            json!({"update": {"code.queue_2": {"name": "q"}}}),
            Code::NameRoundTripFailure,
            Some(json!({"update": {"code.queue2": {"name": "q"}}})),
        ),
        (
            json!({"add": {"widgets.relay": {"name": "r"}}}),
            Code::RootScopeNotAllowed,
            None,
        ),
        (
            json!({"add": {"code.relay": {"wants": [with_end("pe", "code.masher.widget", want("push"))]}}}),
            Code::FieldMismatch,
            None,
        ),
        (
            json!({"update": {"code.masher.widget": {"status": "missing"}}}),
            Code::FieldMismatch,
            None,
        ),
        (json!({"add": {}}), Code::FieldMismatch, None),
        (
            json!({"add": {"code.masher.widget.name": {"name": "n"}}}),
            Code::FieldElementCollision,
            Some(json!({"update": {"code.masher.widget": {"name": null}}})),
        ),
        (
            json!({"update": {"code.relay": {"wants": [{"pe": "code.other", "ifd": "send"}]}}}),
            Code::WantIncomplete,
            Some(
                json!({"update": {"code.relay": {"wants": [{"pe": "code.other", "ifd": "send", "op": "<op>", "ef": "<ef>"}]}}}),
            ),
        ),
        (
            json!({"add": {"code.relay": {"name": "r", "technical_name": "relay code extra"}}}),
            Code::TechnicalNameAlignmentFailure,
            Some(json!({"add": {"code.relay": {"name": "r", "technical_name": "relay"}}})),
        ),
        (
            json!({"add": {"code.cache.response": {"name": "c", "technical_name": "cache response"}}}),
            Code::TechnicalNameAlignmentFailure,
            Some(json!({"add": {"code.cache.response": {"name": "c", "technical_name": "response cache"}}})),
        ),
        (
            json!({"update": {"code.masher.widget": {"technical_name": "masher widget"}}}),
            Code::TechnicalNameAlignmentFailure,
            Some(json!({"update": {"code.masher.widget": {"technical_name": "widget masher"}}})),
        ),
        (
            json!({"update": {"code.masher.widget": {"references": [{"path": "./src/widgets/mashbox.c"}]}}}),
            Code::LayerNotRegistered,
            Some(json!({"map": {}})),
        ),
        (
            json!({"add": {"code.relay": {"role": "Definitive"}}}),
            Code::RoleTaxonomyFailure,
            Some(json!({"add": {"code.relay": {"role": "<AT, DE, SE, NE, CQU, UD or DD>"}}})),
        ),
        (
            json!({"delete": {"code.protocol": {}}}),
            Code::ElementsBeneath,
            Some(json!({"delete": {"code.protocol.network.tracker.cs": {}}})),
        ),
        (
            json!({"code.nowhere": {}}),
            Code::NotFound,
            Some(json!({"map": {}})),
        ),
    ];
    for (command, code, remediation) in table {
        let refusal = refused(&contract, &map, &command);
        assert_eq!(refusal.code, code, "{command}: {}", refusal.reason);
        if remediation.is_some() {
            assert_eq!(
                refusal.remediation.as_deref(),
                remediation.as_ref(),
                "{command}"
            );
        }
        assert!(
            !refusal.reason.is_empty() && !refusal.rule().is_empty(),
            "{command}"
        );
    }
    assert_eq!(map, seeded(), "the input map is never changed");
    let index = read(&contract, &map, json!({"map": {}}));
    assert!(
        !index["addresses"]
            .as_array()
            .unwrap()
            .iter()
            .any(|a| a.as_str().unwrap().starts_with("code.relay"))
    );
}

/// The form does the work: one write creates every path it needs, add grows, a read returns only
/// the element's own fields in the entry form, `map` is the shallow graph, and a key that starts
/// with a period dumps the stored nested form.
#[test]
fn writes_create_paths_and_reads_return_each_form() {
    let contract = Contract::bundled().unwrap();
    let want =
        json!({"op": "Receive the part.", "ef": "Supplies the part.", "ifd": "receive"});
    let mut map = Map::new();
    map = write(
        &contract,
        &map,
        json!({"update": {"code.new.part": {"name": "part", "wants": [with_end("pe", "code.other.part", &want)]}}}),
    );
    map = write(
        &contract,
        &map,
        json!({"add": {"code.new.part": {"name": "renamed", "sources": ["a"], "wants": [with_end("pe", "code.third.part", &want)]}}}),
    );
    map = write(
        &contract,
        &map,
        json!({"add": {"code.new.part": {"sources": ["b"]}}}),
    );
    map = write(&contract, &map, json!({"update": {".": {"name": "demo"}}}));
    assert_eq!(
        map.element("code.new.part").unwrap().fields["sources"],
        json!(["a", "b"])
    );
    assert_eq!(
        read(&contract, &map, json!({"code.new.part": {}})),
        json!({"code.new.part": {"name": "renamed"}})
    );

    let index = read(&contract, &map, json!({"map": {}}));
    assert_eq!(
        index["addresses"],
        json!([
            "code",
            "code.new",
            "code.new.part",
            "code.other",
            "code.other.part",
            "code.third",
            "code.third.part"
        ])
    );
    assert_eq!(
        index["edges"],
        json!([
            ["code.new.part", "code.other.part"],
            ["code.new.part", "code.third.part"]
        ])
    );
    assert_eq!(index["defining"], json!([]));
    assert!(
        index.get("code.new.part").is_none() && !index.to_string().contains("renamed"),
        "map is the shallow graph: no fields"
    );

    // A key that starts with a period dumps the stored nested form at that path (R-5.31); the
    // same address without the period answers in the entry form (R-5.10).
    let whole = read(&contract, &map, json!({".": {}}));
    assert_eq!(whole["."]["code"]["new"]["part"]["name"], "renamed");
    assert_eq!(
        whole["."]["code"]["new"]["part"]["wants"][0],
        with_end("pe", "code.other.part", &want)
    );
    let part = read(&contract, &map, json!({".code.new": {}}));
    assert_eq!(part[".code.new"]["part"], whole["."]["code"]["new"]["part"]);
    let entry = read(&contract, &map, json!({"code.new.part": {}}));
    assert_eq!(entry["code.new.part"]["name"], "renamed");
    assert!(entry["code.new.part"].get("wants").is_none());
    let missing = refused(&contract, &map, &json!({".code.nowhere": {}}));
    assert_eq!(missing.code, Code::NotFound);
    assert_eq!(missing.remediation.as_deref(), Some(&json!({"map": {}})));
    map = write(
        &contract,
        &map,
        json!({"update": {"code.new.part": {"role": "DE"}}}),
    );
    assert_eq!(
        read(&contract, &map, json!({"map": {}}))["defining"],
        json!(["code.new.part"])
    );

    let remediation = refused(&contract, &map, &json!({"delete": {"code.other.part": {}}}))
        .remediation
        .map(|fix| *fix)
        .unwrap();
    map = write(&contract, &map, remediation);
    assert_eq!(
        read(&contract, &map, json!({"orphaned": {}})),
        json!({"code.new.part": {"name": "renamed", "role": "DE"}})
    );
    map = write(&contract, &map, json!({"delete": {"code.other.part": {}}}));
    assert!(
        map.element("code.other").is_none(),
        "the empty branch goes with its last element"
    );
    assert_eq!(map.element(".").unwrap().fields["name"], "demo");
}

/// A Defining Element counts only among the project's own elements (R-3.3, R-3.7): an element
/// under `upstream` with the role DE is not listed by `map`. A second DE inside the project is
/// accepted, and `map` lists both.
#[test]
fn map_lists_the_defining_elements_of_the_project_only() {
    let contract = Contract::bundled().unwrap();
    let project = json!({"technical_name": "game engine code", "name": "Game Engine", "role": "DE"});
    let chained = json!({"technical_name": "game engine code upstream", "name": "Physics", "role": "DE",
        "refs": ["https://example.com/physics.git"]});
    let map = write(&contract, &Map::new(), json!({"add": {"code.engine.game": project}}));
    let map = write(&contract, &map, json!({"add": {"upstream.code.engine.game": chained}}));
    let map = write(&contract, &map, json!({"add": {"code.engine.audio": {"technical_name": "audio engine code", "name": "Audio", "role": "DE"}}}));
    assert_eq!(read(&contract, &map, json!({"map": {}}))["defining"], json!(["code.engine.audio", "code.engine.game"]));
}
