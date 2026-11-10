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
        json!({"add": {"downstream.reader": {"technical_name": "reader", "name": "reader", "role": "Notable"}}}),
    );
}

#[test]
fn a_deletion_leaves_no_empty_element() {
    // A want creates the element it names (R-5.4). When the want is removed and the element was
    // never filled in, the element and its empty branches go too.
    let contract = Contract::bundled().unwrap();
    let map = seeded(&contract);
    let want = json!({"update": {GAME: {"wants": {"code.nothing.here": {"why": "keep it", "how": "holds it", "direction": "inbound"}}}}});
    let with_stub = write(&contract, &map, want.clone());
    assert!(with_stub.element("code.nothing.here").is_some());
    let removed = write(&contract, &with_stub, json!({"delete": {GAME: {"wants": ["code.nothing.here"]}}}));
    assert!(removed.element("code.nothing.here").is_none());
    assert!(removed.element("code.nothing").is_none());
    // An element that was filled in stays when the last want that names it goes.
    let filled = write(
        &contract,
        &with_stub,
        json!({"update": {"code.nothing.here": {"technical_name": "here nothing", "name": "Placeholder", "role": "Notable"}}}),
    );
    let kept = write(&contract, &filled, json!({"delete": {GAME: {"wants": ["code.nothing.here"]}}}));
    assert!(kept.element("code.nothing.here").is_some());
}

#[test]
fn a_second_definitive_is_refused_without_touching_the_first() {
    let contract = Contract::bundled().unwrap();
    let map = seeded(&contract);
    let refusal = refused(
        &contract,
        &map,
        json!({"add": {"code.loop.main": {"technical_name": "main loop", "name": "Frame pump", "role": "Definitive"}}}),
    );
    assert_eq!(refusal.code, Code::RoleTaxonomyFailure);
    assert_eq!(
        refusal.to_json()["remediation"],
        json!({"add": {"code.loop.main": {"technical_name": "main loop", "name": "Frame pump", "role": "<Supportive, Notable or Divergent>"}}})
    );
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

#[test]
fn an_empty_wants_and_a_system_layer_that_is_not_a_list_are_refused() {
    let contract = Contract::bundled().unwrap();
    let map = seeded(&contract);
    let empty = refused(&contract, &map, json!({"update": {GAME: {"wants": {}}}}));
    assert_eq!(empty.code, Code::FieldMismatch);
    assert_eq!(empty.reason, "wants at 'code.engine.game' holds no want record");
    let text = refused(&contract, &map, json!({"update": {GAME: {"sources": "./docs/engine.md"}}}));
    assert_eq!(text.code, Code::FieldMismatch);
    assert_eq!(
        text.to_json()["remediation"],
        json!({"update": {GAME: {"sources": ["./docs/engine.md"]}}})
    );
    write(&contract, &map, json!({"update": {GAME: {"sources": ["./docs/engine.md"]}}}));
}

const GRAMMAR_RULE: &str = "why is one fragment that starts with a base verb; how is one fragment that starts with a verb ending in -s. No leading 'to', no subject, no '-ing' verb, no values, at most 14 words. Detail belongs in a knowledge layer.";
const WHY_PLACEHOLDER: &str = "<base verb phrase, as: drain raw frames from the network interface card>";
const HOW_PLACEHOLDER: &str = "<verb phrase ending in -s, as: holds descriptor pointers across contiguous memory segments>";

#[test]
fn a_written_why_or_how_follows_the_grammar() {
    let contract = Contract::bundled().unwrap();
    let map = seeded(&contract);
    let router = "code.engine.router";

    // The procedure's own example passes, and creates the element the want names.
    let example = json!({"update": {GAME: {"wants": {router: {
        "why": "Receive player input and collision telemetry for frame simulation.",
        "how": "Dispatches subscribed runtime event streams.",
        "direction": "inbound",
    }}}}});
    let map = write(&contract, &map, example);

    // A `how` with a subject is refused. Only `how` broke the rule, so only `how` is in the
    // remediation; the sentence uses the stored `why`. The router has no name.
    let command = json!({"update": {GAME: {"wants": {router: {"how": "The router stores parameters."}}}}});
    let refusal = refused(&contract, &map, command);
    assert_eq!(refusal.code, Code::GrammarConstraintViolation);
    assert_eq!(
        refusal.to_json(),
        json!({
            "code": "GRAMMAR_CONSTRAINT_VIOLATION",
            "message": format!("how starts with a subject. {GRAMMAR_RULE}"),
            "tested_sentence": "code.engine.game (Quake core) requires code.engine.router in order to Receive player input and collision telemetry for frame simulation, which The router stores parameters.",
            "remediation": {"update": {GAME: {"wants": {router: {"how": HOW_PLACEHOLDER}}}}},
        })
    );

    // Both parts break the rule: both are in the remediation, `why` first. The want is stored, so
    // the remediation has only the parts that broke the rule.
    let command = json!({"update": {GAME: {"wants": {router: {"how": "holding pointers", "why": "to drain frames"}}}}});
    let refusal = refused(&contract, &map, command);
    assert_eq!(
        refusal.to_json()["remediation"],
        json!({"update": {GAME: {"wants": {router: {"why": WHY_PLACEHOLDER, "how": HOW_PLACEHOLDER}}}}})
    );
    assert_eq!(
        refusal.to_json()["tested_sentence"],
        "code.engine.game (Quake core) requires code.engine.router in order to to drain frames, which holding pointers."
    );
    // The message names each part and its first fault, `why` first, then states the rule.
    assert_eq!(
        refusal.to_json()["message"],
        format!("why starts with 'to'; how does not start with a verb ending in -s. {GRAMMAR_RULE}")
    );
    // For a `how`, the subject check comes before the `-s` check and the value check.
    let command = json!({"update": {GAME: {"wants": {router: {"why": "to drain frames", "how": "The router stores 5 items."}}}}});
    assert_eq!(
        refused(&contract, &map, command).to_json()["message"],
        "why starts with 'to'; how starts with a subject. why is one fragment that starts with a base verb; how is one fragment that starts with a verb ending in -s. No leading 'to', no subject, no '-ing' verb, no values, at most 14 words. Detail belongs in a knowledge layer."
    );

    // The first want that breaks the rule is reported, in the order the command gives them, and
    // nothing of the command is stored. The want is new, so the remediation has the whole want:
    // a want needs all of its fields.
    let command = json!({"update": {GAME: {"wants": {
        "code.engine.store": {"why": "keep frames", "how": "holds frames on disk", "direction": "inbound"},
        "code.engine.zeta": {"why": "keeping frames", "how": "holds frames", "direction": "inbound"},
        "code.engine.alpha": {"why": "keep 5 frames", "how": "holds frames", "direction": "inbound"},
    }}}});
    let refusal = refused(&contract, &map, command);
    assert_eq!(
        refusal.to_json()["remediation"],
        json!({"update": {GAME: {"wants": {"code.engine.zeta": {
            "why": WHY_PLACEHOLDER, "how": "holds frames", "direction": "inbound",
        }}}}})
    );
    assert_eq!(refusal.to_json()["message"], format!("why starts with an '-ing' verb. {GRAMMAR_RULE}"));
    assert!(map.element("code.engine.store").is_none());

    // A part of 15 words is refused, and the same part with 14 words is accepted.
    let long = "Dispatches inbound messages to the service and gives each caller a peer for outbound requests";
    let command = json!({"update": {GAME: {"wants": {router: {"how": long}}}}});
    let refusal = refused(&contract, &map, command);
    assert_eq!(refusal.to_json()["message"], format!("how is longer than 14 words. {GRAMMAR_RULE}"));
    assert_eq!(refusal.to_json()["remediation"], json!({"update": {GAME: {"wants": {router: {"how": HOW_PLACEHOLDER}}}}}));
    let long = "receive each inbound message from the transport and pass it on to the service loop";
    let command = json!({"update": {GAME: {"wants": {router: {"why": long}}}}});
    assert_eq!(
        refused(&contract, &map, command).to_json()["message"],
        format!("why is longer than 14 words. {GRAMMAR_RULE}")
    );
    let short = "Dispatches inbound messages to the service and gives each caller a peer for requests";
    write(&contract, &map, json!({"update": {GAME: {"wants": {router: {"how": short}}}}}));

    // An `add` is checked in the same way. Its sentence uses the names the command gives.
    let command = json!({"add": {"code.engine.cache": {
        "technical_name": "cache",
        "name": "Frame Cache",
        "role": "Supportive",
        "wants": {GAME: {"why": "to serve frames", "how": "Serves frames.", "direction": "outbound"}},
    }}});
    let refusal = refused(&contract, &map, command);
    assert_eq!(
        refusal.to_json()["tested_sentence"],
        "code.engine.cache (Frame Cache) requires code.engine.game (Quake core) in order to to serve frames, which Serves frames."
    );
    let remediation = refusal.to_json()["remediation"].clone();
    assert_eq!(
        remediation,
        json!({"update": {"code.engine.cache": {"wants": {GAME: {
            "why": WHY_PLACEHOLDER, "how": "Serves frames.", "direction": "outbound",
        }}}}})
    );
    // The remediation is a command the tool accepts once the placeholder is replaced.
    let mut corrected = remediation;
    corrected["update"]["code.engine.cache"]["wants"][GAME]["why"] = json!("serve frames");
    write(&contract, &map, corrected);
}

#[test]
fn a_stored_why_or_how_is_not_checked_again() {
    // A map stored before the check holds whole sentences. It loads, and a write that does not
    // write the old part is accepted.
    let contract = Contract::bundled().unwrap();
    let tree = json!({"code": {"engine": {"game": {
        "technical_name": "game engine",
        "name": "Quake core",
        "role": "Definitive",
        "wants": {"code.engine.router": {
            "why": "The game needs 5 parameters.",
            "how": "The router stores them; Path reads them.",
            "direction": "inbound",
        }},
    }, "router": {}}}});
    let map = Map::from_tree(&tree).unwrap();
    let router = "code.engine.router";
    let map = write(&contract, &map, json!({"update": {GAME: {"status": "built"}}}));
    let map = write(&contract, &map, json!({"update": {GAME: {"wants": {router: {"direction": "outbound"}}}}}));
    // A valid `how` over the stored want is accepted, although the stored `why` is a sentence.
    let map = write(&contract, &map, json!({"update": {GAME: {"wants": {router: {"how": "Stores decoded parameters."}}}}}));
    // The same `why` written again is checked, because the command writes it.
    let again = json!({"update": {GAME: {"wants": {router: {"why": "The game needs 5 parameters."}}}}});
    let refusal = refused(&contract, &map, again);
    assert_eq!(refusal.code, Code::GrammarConstraintViolation);
    assert_eq!(
        refusal.to_json()["remediation"],
        json!({"update": {GAME: {"wants": {router: {"why": WHY_PLACEHOLDER}}}}})
    );
}
