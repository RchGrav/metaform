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
    let game = json!({"technical_name": "game engine", "name": "Quake core", "role": "Definitive"});
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
fn name_must_differ_from_technical_name() {
    let contract = Contract::bundled().unwrap();
    let map = seeded(&contract);
    let update = refused(&contract, &map, json!({"update": {GAME: {"name": " Game Engine "}}}));
    assert_eq!(update.code, Code::CanonicalNameCollisionFailure);
    assert_eq!(
        update.reason,
        "'code.engine.game': name \" Game Engine \" is the same as technical_name; name is the project's own name for the element"
    );
    assert_eq!(
        update.to_json()["remediation"],
        json!({"update": {GAME: {"name": "<the project's own name for it>"}}})
    );
    // An element the write creates is added again with the name corrected.
    let add = refused(
        &contract,
        &map,
        json!({"add": {"code.queue.dead_letter": {"technical_name": "dead letter queue", "name": "dead letter queue", "role": "Notable"}}}),
    );
    assert_eq!(add.code, Code::CanonicalNameCollisionFailure);
    assert_eq!(
        add.to_json()["remediation"],
        json!({"add": {"code.queue.dead_letter": {"technical_name": "dead letter queue", "name": "<the project's own name for it>", "role": "Notable"}}})
    );
    write(&contract, &map, json!({"update": {GAME: {"name": "Game core"}}}));
}

#[test]
fn a_written_role_is_one_of_the_four() {
    let contract = Contract::bundled().unwrap();
    let map = seeded(&contract);
    for role in ["Helper", "definitive", "DE", "SE", "NE", "CQU", "Supportive "] {
        let refusal = refused(&contract, &map, json!({"update": {GAME: {"role": role}}}));
        assert_eq!(refusal.code, Code::RoleTaxonomyFailure, "{role}");
        assert_eq!(
            refusal.reason,
            format!("'code.engine.game': role \"{role}\" is not one of: Definitive, Supportive, Notable, Divergent")
        );
        assert_eq!(
            refusal.to_json()["remediation"],
            json!({"update": {GAME: {"role": "<Definitive, Supportive, Notable or Divergent>"}}})
        );
    }
    let created = refused(&contract, &map, json!({"add": {"code.loop.main": {"name": "Frame pump", "role": "Helper"}}}));
    assert_eq!(
        created.to_json()["remediation"],
        json!({"add": {"code.loop.main": {"name": "Frame pump", "role": "<Definitive, Supportive, Notable or Divergent>"}}}),
        "a refused add stored nothing, so the remediation adds the element again"
    );
    for role in ["Supportive", "Notable", "Divergent", "Definitive"] {
        write(&contract, &map, json!({"update": {GAME: {"role": role}}}));
    }
    // A stored map with older role names loads, keeps its Definitive element and accepts writes
    // that do not change a role. A write that changes one must use the four names.
    let stored = json!({"demo": {"code": {
        "relay": {"name": "Relay", "role": "DE"},
        "queue": {"name": "Queue", "role": "SE"},
        "cache": {"name": "Cache", "role": "CQU"}
    }}});
    let (_, old) = Map::from_document(&stored).unwrap();
    let old = write(&contract, &old, json!({"update": {"code.queue": {"status": "un_built"}}}));
    let old = write(&contract, &old, json!({"update": {"code.relay": {"name": "Relay station", "role": "DE"}}}));
    let index = execute(&contract, &old, &json!({"map": {}})).unwrap();
    assert_eq!(index.result()["definitive"], "code.relay");
    assert_eq!(refused(&contract, &old, json!({"update": {"code.queue": {"role": "NE"}}})).code, Code::RoleTaxonomyFailure);
    let second = refused(&contract, &old, json!({"update": {"code.queue": {"role": "Definitive"}}}));
    assert!(second.reason.contains("'code.relay' already is"), "{}", second.reason);
}

#[test]
fn a_refusal_about_layer_records_gives_a_remediation_that_works() {
    let contract = Contract::bundled().unwrap();
    let map = seeded(&contract);
    let layer = json!({"technical_name": "cpp code layer", "name": "C++ notes", "role": "Supportive", "instruction": "Record what the C++ realization requires."});
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
    let beneath = write(&contract, &map, json!({"add": {"code.pool": {"memory": {"technical_name": "memory pool", "name": "Arena", "role": "Supportive"}}}}));
    assert!(beneath.element("code.pool.memory").is_some());
}
