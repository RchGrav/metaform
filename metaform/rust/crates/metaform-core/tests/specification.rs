//! The specification layer through the tool (R-6.24 to R-6.27). Budget: at most five tests for
//! this feature. This file holds five; the Markdown round trip is tested with the renderer.

use std::fs;
use std::path::PathBuf;

use metaform_core::{Code, Contract, Map, Outcome, execute, specification};
use serde_json::{Value, json};

const MASHER: &str = "code.masher.widget";

/// The intake example with the specification layer defined, as the store seeds a main map.
fn seeded() -> Map {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../../intake-example.json");
    let document: Value = serde_json::from_slice(&fs::read(path).unwrap()).unwrap();
    let map = Map::from_document(&document).unwrap().1;
    with_layer(&map)
}

fn with_layer(map: &Map) -> Map {
    let contract = Contract::bundled().unwrap();
    let seed = json!({"update": {specification::DEFINITION_ADDRESS: Value::Object(specification::definition())}});
    run(&contract, map, seed).unwrap().0
}

fn run(
    contract: &Contract,
    map: &Map,
    command: Value,
) -> Result<(Map, Value), metaform_core::Refusal> {
    execute(contract, map, &command).map(|outcome| match outcome {
        Outcome::Write(write) => {
            assert_eq!(
                map.apply(&write.effect),
                write.map,
                "the effect of {command}"
            );
            (write.map, write.result)
        }
        Outcome::Read(result) => (map.clone(), result),
    })
}

fn blocks(map: &Map, address: &str) -> Value {
    map.element(address)
        .unwrap()
        .fields
        .get("specification")
        .cloned()
        .unwrap_or(Value::Null)
}

/// Blocks are accepted only at skeleton elements, and at the root once a Defining Element
/// exists (R-6.26). Text is normalized, update replaces, add appends, and `[]` removes the field.
#[test]
fn blocks_follow_the_skeleton_and_are_normalized() {
    let contract = Contract::bundled().unwrap();
    let map = seeded();

    let trunk = run(
        &contract,
        &map,
        json!({"update": {"code.masher": {"specification": [{"text": "Prose."}]}}}),
    )
    .unwrap_err();
    assert_eq!(trunk.code, Code::ElementNotInSkeleton);
    assert_eq!(
        *trunk.remediation.unwrap(),
        json!({"update": {"code.masher": {"technical_name": "<technical_name>", "name": "<name>", "role": "<role>"}}})
    );
    let empty = with_layer(&Map::new());
    let root = run(
        &contract,
        &empty,
        json!({"update": {".": {"specification": [{"text": "Overview."}]}}}),
    )
    .unwrap_err();
    assert_eq!(
        root.code,
        Code::ElementNotInSkeleton,
        "no Defining Element yet"
    );
    let (map, _) = run(
        &contract,
        &map,
        json!({"update": {".": {"specification": [{"text": "Overview."}]}}}),
    )
    .unwrap();
    assert_eq!(blocks(&map, "."), json!([{"text": "Overview."}]));

    let (map, _) = run(
        &contract,
        &map,
        json!({"update": {MASHER: {"specification": [
            {"text": "\r\nThe masher packs widgets.\r\n\r\n"},
            {"level": 1, "title": " Packing ", "text": "Line one.\r\nLine two."}
        ]}}}),
    )
    .unwrap();
    assert_eq!(
        blocks(&map, MASHER),
        json!([{"text": "The masher packs widgets."}, {"level": 1, "title": "Packing", "text": "Line one.\nLine two."}])
    );
    let (map, _) = run(
        &contract,
        &map,
        json!({"add": {MASHER: {"specification": [{"level": 2, "title": "Limits", "text": ""}]}}}),
    )
    .unwrap();
    assert_eq!(
        blocks(&map, MASHER).as_array().unwrap().len(),
        3,
        "add appends"
    );
    let late_intro = run(
        &contract,
        &map,
        json!({"add": {MASHER: {"specification": [{"text": "Late intro."}]}}}),
    )
    .unwrap_err();
    assert_eq!(late_intro.code, Code::FieldMismatch);
    let (map, _) = run(
        &contract,
        &map,
        json!({"update": {MASHER: {"specification": []}}}),
    )
    .unwrap();
    assert_eq!(
        blocks(&map, MASHER),
        Value::Null,
        "an empty list removes the field"
    );

    // Blocks the write did not change are not checked again: intake can still correct the element.
    let (map, _) = run(
        &contract,
        &map,
        json!({"update": {MASHER: {"specification": [{"text": "Kept."}]}}}),
    )
    .unwrap();
    assert!(run(&contract, &map, json!({"update": {MASHER: {"role": null}}})).is_ok());
}

/// Levels start at 1, rise by at most one and stop at 4 (R-6.25). The remediation is the same
/// update with the levels brought into the rules.
#[test]
fn heading_levels_are_enforced() {
    let contract = Contract::bundled().unwrap();
    let map = seeded();
    for (levels, fixed) in [
        (vec![2], vec![1]),
        (vec![1, 3], vec![1, 2]),
        (vec![1, 2, 3, 4, 5], vec![1, 2, 3, 4, 4]),
        (vec![1, 0], vec![1, 1]),
    ] {
        let block = |level: &u64| json!({"level": level, "title": format!("t{level}"), "text": ""});
        let sent: Vec<Value> = levels.iter().map(block).collect();
        let refusal = run(
            &contract,
            &map,
            json!({"update": {MASHER: {"specification": sent}}}),
        )
        .unwrap_err();
        assert_eq!(refusal.code, Code::HeadingLevelInvalid, "{levels:?}");
        let remediation = refusal.remediation.unwrap();
        let got: Vec<u64> = remediation["update"][MASHER]["specification"]
            .as_array()
            .unwrap()
            .iter()
            .map(|b| b["level"].as_u64().unwrap())
            .collect();
        assert_eq!(got, fixed, "{levels:?}");
        assert!(
            run(&contract, &map, (*remediation).clone()).is_ok(),
            "the remediation is accepted"
        );
    }
    let shape = run(
        &contract,
        &map,
        json!({"update": {MASHER: {"specification": [{"level": 1, "text": "no title"}]}}}),
    )
    .unwrap_err();
    assert_eq!(shape.code, Code::FieldMismatch);
    assert!(
        run(&contract, &map, (*shape.remediation.unwrap()).clone()).is_ok(),
        "the example is accepted"
    );
    let reserved = json!([{"level": 1, "title": "Other (`code.x`)", "text": ""}]);
    let refusal = run(
        &contract,
        &map,
        json!({"update": {MASHER: {"specification": reserved}}}),
    )
    .unwrap_err();
    assert_eq!(
        refusal.code,
        Code::FieldMismatch,
        "the element-heading form is reserved"
    );
}

/// Text holds no heading line outside fenced code (R-6.25). The remediation moves the heading into
/// a block of its own.
#[test]
fn heading_lines_in_text_are_refused() {
    let contract = Contract::bundled().unwrap();
    let map = seeded();
    let fenced = json!([{"level": 1, "title": "Shell", "text": "Run:\n\n```sh\n# a comment\n```\n\nThen #42 closes."}]);
    assert!(
        run(
            &contract,
            &map,
            json!({"update": {MASHER: {"specification": fenced}}})
        )
        .is_ok()
    );
    for text in [
        "Intro.\n## Retry\nAfter a lost answer.",
        "Intro.\n\nRetry\n-----\nAfter a lost answer.",
    ] {
        let sent = json!([{"level": 1, "title": "Writes", "text": text}]);
        let refusal = run(
            &contract,
            &map,
            json!({"update": {MASHER: {"specification": sent}}}),
        )
        .unwrap_err();
        assert_eq!(refusal.code, Code::HeadingInText, "{text:?}");
        assert_eq!(
            refusal.remediation.as_deref().unwrap()["update"][MASHER]["specification"],
            json!([
                {"level": 1, "title": "Writes", "text": "Intro."},
                {"level": 2, "title": "Retry", "text": "After a lost answer."}
            ])
        );
    }
}

/// A read can name the layer, and `goto` lists it wherever it applies, with its instruction
/// (R-5.21, R-6.27).
#[test]
fn the_layer_is_readable_and_listed_by_goto() {
    let contract = Contract::bundled().unwrap();
    let map = seeded();
    let (_, read) = run(
        &contract,
        &map,
        json!({MASHER: {"specification": {}}}),
    )
    .unwrap();
    assert_eq!(
        read[MASHER]["specification"],
        json!([]),
        "an applicable layer with no blocks reads empty"
    );
    let wrapped = run(
        &contract,
        &map,
        json!({MASHER: {"layers": ["specification"]}}),
    )
    .unwrap_err();
    assert_eq!(
        wrapped.code,
        Code::FieldMismatch,
        "a layer is named in its own slot, not in a list"
    );
    let (_, plain) = run(&contract, &map, json!({MASHER: {}})).unwrap();
    assert!(
        plain[MASHER].get("specification").is_none(),
        "an unnamed layer stays out of a read"
    );
    let (_, trunk) = run(
        &contract,
        &map,
        json!({"code.masher": {"specification": {}, "dependencies": {}}}),
    )
    .unwrap();
    assert_eq!(
        trunk["code.masher"],
        json!({"dependencies": []}),
        "the layer does not apply at a trunk"
    );

    let sent = json!([{"level": 1, "title": "Packing", "text": "Packs widgets."}]);
    let (map, _) = run(
        &contract,
        &map,
        json!({"update": {MASHER: {"specification": sent.clone()}}}),
    )
    .unwrap();
    let (_, read) = run(
        &contract,
        &map,
        json!({MASHER: {"specification": {}}}),
    )
    .unwrap();
    assert_eq!(read[MASHER]["specification"], sent);
    let (_, dump) = run(&contract, &map, json!({".": {}})).unwrap();
    assert_eq!(
        dump["."]["code"]["masher"]["widget"]["specification"], sent,
        "the raw dump holds each element's blocks in the nested form"
    );
    assert!(dump["."]["layer"]["document"]["specification"]["instruction"].is_string());

    let (_, sheet) = run(&contract, &map, json!({"goto": MASHER})).unwrap();
    assert_eq!(sheet["layers"]["specification"], json!({"records": 1}));
    assert!(sheet.get("skills").is_none(), "no skills at the address, so no skills part: {sheet}");
    // goto delivers the frontmatter of the skills at the address only; the root's are the base
    // skills an agent learns when it joins (R-5.30).
    let base = json!([{"name": "base", "description": "Every agent learns this on joining."}]);
    let local = json!([{"name": "packing", "description": "How widgets are packed.", "uri": "skills/packing/SKILL.md", "body": "long text"}]);
    let (scoped, _) = run(&contract, &map, json!({"update": {".": {"skills": base}}})).unwrap();
    let (scoped, _) = run(&contract, &scoped, json!({"update": {MASHER: {"skills": local}}})).unwrap();
    let (_, here) = run(&contract, &scoped, json!({"goto": MASHER})).unwrap();
    assert_eq!(
        here["skills"],
        json!({"packing": {"name": "packing", "description": "How widgets are packed.", "uri": "skills/packing/SKILL.md"}}),
        "only the address's skills, frontmatter only: {here}"
    );
    // The sheet names where the rules are; the definition element carries them.
    assert_eq!(
        sheet["instructions"]["specification"],
        json!("The rules for writing specification are at layer.document.specification. Read them only when you write specification.")
    );
    let (_, definition) = run(&contract, &map, json!({"goto": "layer.document.specification"})).unwrap();
    let instruction = definition["guidance"].as_str().unwrap();
    assert!(instruction.contains("TASTE") && instruction.contains("\"level\": 1-4"));
    // The read form the instruction teaches must be one the contract accepts.
    let taught = instruction
        .split("Read them with ")
        .nth(1)
        .and_then(|rest| rest.split(". ").next())
        .unwrap()
        .replace("<address>", MASHER);
    let (_, again) = run(&contract, &map, serde_json::from_str(&taught).unwrap())
        .unwrap_or_else(|refusal| panic!("the instruction teaches a refused read {taught}: {refusal:?}"));
    assert_eq!(again[MASHER]["specification"], sent);
    let (_, trunk) = run(&contract, &map, json!({"goto": "code.masher"})).unwrap();
    assert!(trunk["layers"].get("specification").is_none() && trunk.get("instructions").is_none());
}

/// Every layer works the same way (R-6.24): a definition beneath `layer` makes its last segment a
/// layer, whose records follow the skeleton rule and are listed by `goto`. Only a definition with
/// the `markdown_blocks` format gets heading rules. The code-defined specification definition can
/// be written only as the code gives it, so seeding works and nothing else changes it.
#[test]
fn layers_are_defined_in_the_map_and_the_specification_definition_is_locked() {
    let contract = Contract::bundled().unwrap();
    let map = seeded();

    let features = json!({"technical_name": "features knowledge layer", "name": "Features", "role": "SE",
        "instruction": "Tag the element with each feature it belongs to."});
    let (map, _) = run(
        &contract,
        &map,
        json!({"update": {"layer.knowledge.features": features}}),
    )
    .unwrap();
    let (map, _) = run(
        &contract,
        &map,
        json!({"update": {MASHER: {"features": ["packing", {"any": "shape"}]}}}),
    )
    .unwrap();
    let trunk = run(
        &contract,
        &map,
        json!({"update": {"code.masher": {"features": ["packing"]}}}),
    )
    .unwrap_err();
    assert_eq!(trunk.code, Code::ElementNotInSkeleton);
    let scalar = run(
        &contract,
        &map,
        json!({"update": {MASHER: {"features": "packing"}}}),
    )
    .unwrap_err();
    assert_eq!(
        scalar.code,
        Code::FieldMismatch,
        "a layer's value is a list"
    );
    let on_definition = run(
        &contract,
        &map,
        json!({"update": {"layer.knowledge.features": {"specification": [{"text": "x"}]}}}),
    )
    .unwrap_err();
    assert_eq!(
        on_definition.code,
        Code::ElementNotInSkeleton,
        "records do not go on definitions"
    );
    let (_, sheet) = run(&contract, &map, json!({"goto": MASHER})).unwrap();
    assert_eq!(sheet["layers"]["features"], json!({"records": 2}));
    assert_eq!(
        sheet["instructions"]["features"],
        json!("The rules for writing features are at layer.knowledge.features. Read them only when you write features.")
    );
    let (_, definition) = run(&contract, &map, json!({"goto": "layer.knowledge.features"})).unwrap();
    assert_eq!(definition["guidance"], json!("Tag the element with each feature it belongs to."));
    let (_, definition) = run(&contract, &map, json!({"goto": "layer.document.specification"})).unwrap();
    assert!(
        definition["guidance"]
            .as_str()
            .unwrap()
            .starts_with("The specification field is a list of blocks")
    );

    // Block codes are keys: valid form, titled blocks only, unique in the layer ignoring case.
    let coded = json!([{"level": 1, "code": "R-1.2", "title": "Packing", "text": ""}]);
    let (map, _) = run(
        &contract,
        &map,
        json!({"update": {MASHER: {"specification": coded.clone()}}}),
    )
    .unwrap();
    let (_, read) = run(
        &contract,
        &map,
        json!({MASHER: {"specification": {}}}),
    )
    .unwrap();
    assert_eq!(
        read[MASHER]["specification"], coded,
        "the code is stored and read back"
    );
    let elsewhere = json!([{"level": 1, "title": "Relay", "text": "", "code": "r-1.2"}]);
    let dup = run(
        &contract,
        &map,
        json!({"update": {"code.protocol.network.tracker.cs": {"specification": elsewhere}}}),
    )
    .unwrap_err();
    assert_eq!(dup.code, Code::CodeNotUnique);
    assert!(
        dup.reason.contains("'code.masher.widget' block 1"),
        "{}",
        dup.reason
    );
    assert!(
        run(&contract, &map, (*dup.remediation.unwrap()).clone()).is_ok(),
        "the remediation drops the code"
    );
    let twice = json!([{"level": 1, "title": "a", "text": "", "code": "K1"}, {"level": 1, "title": "b", "text": "", "code": "k1"}]);
    assert_eq!(
        run(
            &contract,
            &map,
            json!({"update": {MASHER: {"specification": twice}}})
        )
        .unwrap_err()
        .code,
        Code::CodeNotUnique
    );
    assert!(
        run(
            &contract,
            &map,
            json!({"update": {MASHER: {"specification": coded}}})
        )
        .is_ok(),
        "rewriting its own code is accepted"
    );
    for bad in [
        json!([{"text": "intro", "code": "A1"}]),
        json!([{"level": 1, "title": "t", "text": "", "code": "1A"}]),
        json!([{"level": 1, "title": "t", "text": "", "code": "A 1"}]),
        json!([{"level": 1, "title": "t", "text": "", "code": "A1."}]),
    ] {
        assert_eq!(
            run(
                &contract,
                &map,
                json!({"update": {MASHER: {"specification": bad.clone()}}})
            )
            .unwrap_err()
            .code,
            Code::FieldMismatch,
            "{bad}"
        );
    }

    let shadow = json!({"update": {"layer.code.features": {"instruction": "Another meaning."}}});
    let collision = run(&contract, &map, shadow).unwrap_err();
    assert_eq!(collision.code, Code::LayerNameCollision);
    assert!(
        collision.reason.contains("'layer.knowledge.features'"),
        "{}",
        collision.reason
    );

    let at = specification::DEFINITION_ADDRESS;
    for command in [
        json!({"update": {at: {"instruction": "Write anything."}}}),
        json!({"update": {at: {"format": null}}}),
        json!({"delete": {at: {}}}),
    ] {
        let refusal = run(&contract, &map, command.clone()).unwrap_err();
        assert_eq!(refusal.code, Code::LayerDefinitionLocked, "{command}");
    }
    let reseed = json!({"update": {at: Value::Object(specification::definition())}});
    assert!(
        run(&contract, &map, reseed).is_ok(),
        "writing the code's definition again is accepted"
    );
}
