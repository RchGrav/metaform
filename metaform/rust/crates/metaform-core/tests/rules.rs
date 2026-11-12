//! Rules on a write that read the map: the root has no `technical_name`, `name` differs from
//! `technical_name` (R-3.12), a written `role` is one of the four (R-3.13), and a refusal about a
//! layer's records gives a remediation that works and destroys nothing (R-6.24, R-6.26).

use metaform_core::{Code, Contract, Map, Outcome, Refusal, execute};
use serde_json::{Value, json};

const GAME: &str = "code.engine.game";

fn write(contract: &Contract, map: &Map, command: Value) -> Map {
    match execute(contract, map, &command) {
        Ok(Outcome::Write(write)) => write.map,
        other => panic!("{command} should write, got {other:?}"),
    }
}

fn refused(contract: &Contract, map: &Map, command: Value) -> Refusal {
    match execute(contract, map, &command) {
        Err(refusal) => refusal,
        Ok(outcome) => panic!("{command} should be refused, got {outcome:?}"),
    }
}

fn seeded(contract: &Contract) -> Map {
    let game = json!({"technical_name": "game engine", "name": "Quake core", "role": "DE"});
    write(contract, &Map::new(), json!({"add": {GAME: game}}))
}

#[test]
fn the_root_has_no_technical_name() {
    let contract = Contract::bundled().unwrap();
    let map = seeded(&contract);
    let refusal = refused(&contract, &map, json!({"update": {".": {"technical_name": "project"}}}));
    assert_eq!(refusal.code, Code::TechnicalNameAlignmentFailure);
    assert_eq!(refusal.reason, "'.': the root is the project and has no technical_name");
    let remediation = refusal.to_json()["remediation"].clone();
    assert_eq!(remediation, json!({"update": {".": {"technical_name": null}}}));
    write(&contract, &map, remediation);
    write(&contract, &map, json!({"update": {".": {"name": "Quake"}}}));
}

#[test]
fn name_may_equal_technical_name() {
    // R-3.12 is not enforced: the intake procedure lets `name` be the standard term when the
    // project has no name of its own for the element, and a refusal there made agents invent
    // names (SPEC.md D-19).
    let contract = Contract::bundled().unwrap();
    let map = seeded(&contract);
    write(&contract, &map, json!({"update": {GAME: {"name": "game engine"}}}));
    write(
        &contract,
        &map,
        json!({"add": {"downstream.reader": {"technical_name": "reader", "name": "reader", "role": "NE"}}}),
    );
}

#[test]
fn a_deletion_leaves_no_empty_element() {
    // A want creates the element it names (R-5.4). When the want is removed and the element was
    // never filled in, the element and its empty branches go too.
    let contract = Contract::bundled().unwrap();
    let map = seeded(&contract);
    let want = json!({"update": {GAME: {"wants": [{"element": "code.nothing.here", "why": "a", "how": "b", "direction": "receive"}]}}});
    let with_stub = write(&contract, &map, want.clone());
    assert!(with_stub.element("code.nothing.here").is_some());
    let removed = write(&contract, &with_stub, json!({"delete": {GAME: {"wants": ["code.nothing.here"]}}}));
    assert!(removed.element("code.nothing.here").is_none());
    assert!(removed.element("code.nothing").is_none());
    // An element that was filled in stays when the last want that names it goes.
    let filled = write(
        &contract,
        &with_stub,
        json!({"update": {"code.nothing.here": {"technical_name": "here nothing", "name": "Placeholder", "role": "NE"}}}),
    );
    let kept = write(&contract, &filled, json!({"delete": {GAME: {"wants": ["code.nothing.here"]}}}));
    assert!(kept.element("code.nothing.here").is_some());
}

/// A map may hold several Defining Elements: the intake gives one to each artifact type.
#[test]
fn a_second_defining_element_is_accepted() {
    let contract = Contract::bundled().unwrap();
    let map = seeded(&contract);
    let map = write(
        &contract,
        &map,
        json!({"add": {"code.loop.main": {"technical_name": "main loop", "name": "Frame pump", "role": "DE"}}}),
    );
    let index = execute(&contract, &map, &json!({"map": {}})).unwrap();
    assert_eq!(index.result()["defining"], json!(["code.engine.game", "code.loop.main"]));
}

#[test]
fn a_written_role_is_one_of_the_roles() {
    let contract = Contract::bundled().unwrap();
    let map = seeded(&contract);
    for role in ["Helper", "de", "Definitive", "Supportive", "Notable", "Divergent", "AUE", "SE "] {
        let refusal = refused(&contract, &map, json!({"update": {GAME: {"role": role}}}));
        assert_eq!(refusal.code, Code::RoleTaxonomyFailure, "{role}");
        assert_eq!(
            refusal.reason,
            format!("'code.engine.game': role \"{role}\" is not one of: AT, DE, SE, NE, CQU, UD, DD")
        );
        assert_eq!(
            refusal.to_json()["remediation"],
            json!({"update": {GAME: {"role": "<AT, DE, SE, NE, CQU, UD or DD>"}}})
        );
    }
    let created = refused(&contract, &map, json!({"add": {"code.loop.main": {"name": "Frame pump", "role": "Helper"}}}));
    assert_eq!(
        created.to_json()["remediation"],
        json!({"add": {"code.loop.main": {"name": "Frame pump", "role": "<AT, DE, SE, NE, CQU, UD or DD>"}}}),
        "a refused add stored nothing, so the remediation adds the element again"
    );
    for role in ["AT", "SE", "NE", "CQU", "UD", "DD", "DE"] {
        write(&contract, &map, json!({"update": {GAME: {"role": role}}}));
    }
    // A stored map with older role names loads and accepts writes that do not change a role.
    // A write that changes one must use the current names.
    let stored = json!({"demo": {"code": {
        "relay": {"name": "Relay", "role": "Definitive"},
        "queue": {"name": "Queue", "role": "Supportive"}
    }}});
    let (_, old) = Map::from_document(&stored).unwrap();
    let old = write(&contract, &old, json!({"update": {"code.queue": {"status": "un_built"}}}));
    assert_eq!(refused(&contract, &old, json!({"update": {"code.queue": {"role": "Notable"}}})).code, Code::RoleTaxonomyFailure);
    let old = write(&contract, &old, json!({"update": {"code.relay": {"name": "Relay station", "role": "DE"}}}));
    let index = execute(&contract, &old, &json!({"map": {}})).unwrap();
    assert_eq!(index.result()["defining"], json!(["code.relay"]));
}

#[test]
fn a_refusal_about_layer_records_gives_a_remediation_that_works() {
    let contract = Contract::bundled().unwrap();
    let map = seeded(&contract);
    let layer = json!({"technical_name": "cpp code layer", "name": "C++ notes", "role": "SE", "instruction": "Record what the C++ realization requires."});
    let map = write(&contract, &map, json!({"add": {"layer.code.cpp": layer}}));
    let records = json!([{"note": "owns the frame allocator"}]);
    let map = write(&contract, &map, json!({"update": {GAME: {"cpp": records, "memory": [{"note": "kept"}]}}}));

    // Records at a layer definition: no command fixes it.
    let definition = refused(&contract, &map, json!({"update": {"layer.code.cpp": {"cpp": [{"note": "on a definition"}]}}}));
    assert_eq!(definition.code, Code::ElementNotInSkeleton);
    assert_eq!(definition.to_json()["remediation"], Value::Null);

    // An object where the list is: the remediation gives it as a record and removes nothing.
    for (verb, layer) in [("update", "cpp"), ("add", "cpp"), ("update", "memory")] {
        let refusal = refused(&contract, &map, json!({verb: {GAME: {layer: {"note": "an object"}}}}));
        assert_eq!(refusal.code, Code::FieldMismatch, "{verb} {layer}");
        assert_eq!(refusal.reason, format!("'code.engine.game': {layer}: a layer's value must be a list of records"));
        let remediation = refusal.to_json()["remediation"].clone();
        assert_eq!(remediation, json!({verb: {GAME: {layer: [{"note": "an object"}]}}}));
        write(&contract, &map, remediation);
    }
    let nested = refused(&contract, &map, json!({"update": {"code.engine": {"game": {"cpp": {"note": "an object"}}}}}));
    assert_eq!(nested.to_json()["remediation"], json!({"update": {GAME: {"cpp": [{"note": "an object"}]}}}));
    let added = write(&contract, &map, json!({"add": {GAME: {"cpp": [{"note": "an object"}]}}}));
    assert_eq!(added.element(GAME).unwrap().fields["cpp"].as_array().unwrap().len(), 2, "add keeps the stored record");
    // Where the element holds no records of the layer, an object is still an element beneath.
    let beneath = write(&contract, &map, json!({"add": {"code.pool": {"memory": {"technical_name": "memory pool", "name": "Arena", "role": "SE"}}}}));
    assert!(beneath.element("code.pool.memory").is_some());
}

#[test]
fn an_empty_wants_and_a_system_layer_that_is_not_a_list_are_refused() {
    let contract = Contract::bundled().unwrap();
    let map = seeded(&contract);
    for empty in [json!([]), json!({})] {
        let empty = refused(&contract, &map, json!({"update": {GAME: {"wants": empty}}}));
        assert_eq!(empty.code, Code::FieldMismatch);
        assert_eq!(empty.reason, "wants at 'code.engine.game' must be a list of want records, each with element, why, how and direction");
    }
    let text = refused(&contract, &map, json!({"update": {GAME: {"sources": "./docs/engine.md"}}}));
    assert_eq!(text.code, Code::FieldMismatch);
    assert_eq!(
        text.to_json()["remediation"],
        json!({"update": {GAME: {"sources": ["./docs/engine.md"]}}})
    );
    write(&contract, &map, json!({"update": {GAME: {"sources": ["./docs/engine.md"]}}}));
}
