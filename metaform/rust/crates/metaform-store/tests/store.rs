//! Public-interface tests for metaform-store. Budget (`context/topogee-repo/CLAUDE.md`): five for this feature.

use std::path::Path;

use metaform_store::{ClientId, DbKey, Failure, MapKey, Store, StoreError, store_failure_json};
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

const A: ClientId = ClientId(1);
const B: ClientId = ClientId(2);

fn want() -> Value {
    json!({"op": "Receive the mash data to relay it.", "ef": "Prepared mash data packets.", "ifd": "receive"})
}

/// The tool example's two elements, with a want between them and a native array.
fn seed(store: &Store, map: &MapKey) {
    let commands = [
        json!({"add": {"code.masher.widget": {"technical_name": "widget masher code", "name": "mashbox",
            "role": "SE", "refs": ["./src/widgets/mashbox.c"]}}}),
        json!({"add": {"code.protocol.network.tracker.cs": {"technical_name": "cs tracker network protocol",
            "name": "mashtrac", "role": "DE", "refs": ["./src/network/mashtrac.c"],
            "memory": [{"fact": "relays mash data"}], "wants": [with_end("pe", "code.masher.widget", want())]}}}),
    ];
    for c in commands {
        store
            .execute(A, map, &c)
            .unwrap_or_else(|e| panic!("{c}: {e:?}"));
    }
}

fn reads(store: &Store, map: &MapKey) -> Vec<Value> {
    [
        json!({".": {}}),
        json!({"orphaned": {}}),
        json!({"code.masher.widget": {}}),
        json!({"code.protocol.network.tracker.cs": {}}),
    ]
    .iter()
    .map(|r| {
        store
            .execute(B, map, r)
            .unwrap_or_else(|e| panic!("{r}: {e:?}"))
    })
    .collect()
}

fn project(store: &Store, dir: &Path) -> MapKey {
    let source = dir.join("src-project");
    std::fs::create_dir_all(&source).unwrap();
    MapKey::main(&store.register_project(&source, "demo").unwrap())
}

/// Happy path: writes land in Ladybug as the graph and read back identical after a reopen.
#[test]
fn map_persists_across_reopen() {
    let dir = tempfile::tempdir().unwrap();
    let home = dir.path().join("home");
    let (map, before) = {
        let store = Store::open(&home).unwrap();
        let map = project(&store, dir.path());
        seed(&store, &map);
        let before = reads(&store, &map);
        let orphans: Vec<&String> = before[1].as_object().unwrap().keys().collect();
        assert_eq!(
            orphans,
            ["code.protocol.network.tracker.cs"],
            "the tracker wants the widget; nothing wants the tracker"
        );
        (map, before)
    };
    let store = Store::open(&home).unwrap();
    assert_eq!(reads(&store, &map), before);
    assert_eq!(
        store.check_graph(&map).unwrap(),
        Vec::<String>::new(),
        "R-4.16 nesting is complete"
    );
    let source = dir.path().join("src-project");
    assert_eq!(
        store.register_project(&source, "demo").unwrap(),
        match &map.db {
            DbKey::Project(id) => id.clone(),
            DbKey::Standalone => unreachable!(),
        }
    );
    assert!(
        !source.read_dir().unwrap().any(|_| true),
        "nothing is written into the project folder"
    );
}

#[test]
fn second_server_on_a_home_is_refused() {
    let dir = tempfile::tempdir().unwrap();
    let _first = Store::open(dir.path()).unwrap();
    let Err(error) = Store::open(dir.path()) else {
        panic!("a second store opened an owned home")
    };
    assert!(matches!(error, StoreError::Owned(_)));
    // A store failure reaches an agent in the refusal structure, not as bare text.
    let command = json!({"delete": {"code.masher.widget": {}}});
    let answer = store_failure_json(&command, &error);
    assert_eq!(answer["delete"], command["delete"], "the command is echoed");
    assert_eq!(answer["code"], json!("INTERNAL_ERROR"));
    assert_eq!(answer["status"], json!("error"));
    let message = answer["message"].as_str().unwrap();
    assert!(message.contains("owned by another"), "{message}");
    assert!(message.contains("read the element before you retry"), "{message}");
    assert!(answer.get("rule").is_none(), "the response has no rule field");
}

/// A refused write changes nothing, in memory or on disk, and its refusal names a remedy.
#[test]
fn refused_write_changes_nothing() {
    let dir = tempfile::tempdir().unwrap();
    let home = dir.path().join("home");
    let (map, before) = {
        let store = Store::open(&home).unwrap();
        let map = project(&store, dir.path());
        seed(&store, &map);
        let before = reads(&store, &map);
        let command = json!({"delete": {"code.masher.widget": {}}});
        match store.execute(A, &map, &command) {
            Err(Failure::Refused(r)) => {
                // The founder's error structure (`~/brain/mcp_query.md`, `intake_roles.md`):
                // the echoed command, status, code, message and remediation, in that order.
                let answer = metaform_store::refusal_json(&command, &r);
                let expected = json!({
                    "delete": {"code.masher.widget": {}},
                    "status": "error",
                    "code": "DEPENDENCY_LOCK",
                    "message": "cannot delete 'code.masher.widget': 'code.protocol.network.tracker.cs' still wants it. Remove that want first.",
                    "remediation": {"delete": {"code.protocol.network.tracker.cs": {"wants": ["code.masher.widget"]}}}
                });
                assert_eq!(answer.to_string(), expected.to_string(), "fields and their order");
            }
            other => panic!("deleting an element that another element wants must be refused, got {other:?}"),
        }
        assert_eq!(reads(&store, &map), before);
        (map, before)
    };
    assert_eq!(reads(&Store::open(&home).unwrap(), &map), before);
}

/// Maps are partitions: two maps in one database hold the same address independently, and
/// all standalone maps share one database file. Open databases stay within the limit: an idle
/// one closes, and its maps reload intact on next use.
#[test]
fn maps_are_partitions_and_open_databases_are_bounded() {
    let dir = tempfile::tempdir().unwrap();
    let store = Store::open(dir.path()).unwrap();
    let (one, two) = (MapKey::standalone("one"), MapKey::standalone("two"));
    store
        .execute(
            A,
            &one,
            &json!({"update": {"code.part": {"name": "first"}}}),
        )
        .unwrap();
    store
        .execute(
            A,
            &two,
            &json!({"update": {"code.part": {"name": "second"}}}),
        )
        .unwrap();
    store
        .execute(A, &two, &json!({"delete": {"code.part": {}}}))
        .unwrap();
    assert_eq!(
        store.execute(B, &one, &json!({"code.part": {}})).unwrap(),
        json!({"code.part": {"name": "first"}})
    );
    assert!(
        store.execute(B, &two, &json!({"code.part": {}})).is_err(),
        "deleted in map two only"
    );
    let files: Vec<_> = std::fs::read_dir(dir.path().join("maps"))
        .unwrap()
        .map(|e| e.unwrap().file_name())
        .collect();
    assert!(
        files
            .iter()
            .filter(|f| f.to_string_lossy().ends_with(".lbug"))
            .count()
            == 1,
        "{files:?}"
    );
}

/// Writes from a client that floods the queue do not starve another client, and every
/// commit is announced to subscribers in commit order.
#[test]
fn clients_are_served_in_turn_and_commits_are_announced() {
    let dir = tempfile::tempdir().unwrap();
    let store = std::sync::Arc::new(Store::open(dir.path()).unwrap());
    let map = MapKey::standalone("busy");
    let announced = store.subscribe(&map);
    let flood: Vec<_> = (0..8)
        .map(|t| {
            let (store, map) = (store.clone(), map.clone());
            std::thread::spawn(move || {
                for i in 0..10 {
                    let c = json!({"update": {format!("code.flood.t{t}i{i}"): {"name": "x"}}});
                    store.execute(A, &map, &c).unwrap();
                }
            })
        })
        .collect();
    for i in 0..10 {
        store
            .execute(
                B,
                &map,
                &json!({"update": {format!("code.calm.c{i}"): {"name": "y"}}}),
            )
            .unwrap();
    }
    for t in flood {
        t.join().unwrap();
    }
    let order: Vec<String> = announced
        .try_iter()
        .flat_map(|a| {
            a.changed
                .as_object()
                .unwrap()
                .keys()
                .cloned()
                .collect::<Vec<_>>()
        })
        .filter(|k| k.matches('.').count() == 2)
        .collect();
    assert_eq!(order.len(), 90, "every commit announced once");
    let last_calm = order
        .iter()
        .rposition(|k| k.starts_with("code.calm"))
        .unwrap();
    assert!(
        last_calm < 75,
        "client B finished at position {last_calm} of 90"
    );
}

/// Settings (R-4.8): a value set globally survives a reopen and bounds the open databases; the
/// default is never written; a bad entry in the file is ignored, and a bad value or unknown key is
/// refused when set.
#[test]
fn a_setting_survives_a_reopen_and_bounds_open_databases() {
    let dir = tempfile::tempdir().unwrap();
    let key = "stores.max_open_databases";
    {
        let store = Store::open(dir.path()).unwrap();
        assert_eq!(store.settings().get(key, None).unwrap().0, json!(metaform_store::DEFAULT_MAX_OPEN));
        assert!(!dir.path().join("settings.json").exists(), "a default is never stored");
        store.settings().set(key, Some(json!(2)), None).unwrap();
        assert!(store.settings().set(key, Some(json!(0)), None).is_err(), "at least 1");
        assert!(store.settings().set("stores.nope", Some(json!(1)), None).is_err(), "undeclared");
    }
    // A stale or hand-edited entry is ignored, not fatal.
    let file = dir.path().join("settings.json");
    let mut text: serde_json::Map<String, Value> = serde_json::from_str(&std::fs::read_to_string(&file).unwrap()).unwrap();
    text.insert("stores.nope".into(), json!(true));
    std::fs::write(&file, Value::Object(text).to_string()).unwrap();
    let store = Store::open(dir.path()).unwrap();
    assert_eq!(store.settings().get(key, None).unwrap().0, json!(2), "kept across a reopen");
    for p in 0..4 {
        let folder = dir.path().join(format!("p{p}"));
        std::fs::create_dir_all(&folder).unwrap();
        let map = project(&store, &folder);
        store.execute(A, &map, &json!({"update": {"code.part": {"name": "x"}}})).unwrap();
    }
    assert!(store.open_databases() <= 2, "the setting bounds open databases: {}", store.open_databases());
}

/// R-009: a database made before the want renames (table `WANTS`; fields `why`, `how`, `intent`) opens with its
/// wants intact. A database whose tables differ in any other way is refused before anything in it
/// is changed, and the refusal says so.
#[test]
fn an_older_database_is_brought_up_to_date_or_refused_unchanged() {
    let dir = tempfile::tempdir().unwrap();
    let home = dir.path().join("home");
    let map = MapKey::standalone("old");
    let file = home.join("maps").join("maps.lbug");
    let raw = |statement: &str| {
        let db = lbug::Database::new(&file, lbug::SystemConfig::default()).unwrap();
        let conn = lbug::Connection::new(&db).unwrap();
        conn.query(statement).unwrap();
    };
    let before = {
        let store = Store::open(&home).unwrap();
        seed(&store, &map);
        reads(&store, &map)
    };
    // Put back the names an earlier build stored: the fields `why`, `how` and `intent`, in a
    // table named `WANTS`.
    raw("ALTER TABLE DEPENDS_ON RENAME op TO why");
    raw("ALTER TABLE DEPENDS_ON RENAME ef TO how");
    raw("ALTER TABLE DEPENDS_ON RENAME ifd TO intent");
    raw("ALTER TABLE DEPENDS_ON RENAME TO WANTS");
    {
        let store = Store::open(&home).unwrap();
        assert_eq!(reads(&store, &map), before, "the wants survive the rename");
        let want = store
            .execute(
                B,
                &map,
                &json!({"goto": "code.protocol.network.tracker.cs"}),
            )
            .unwrap();
        assert!(
            want.to_string().contains("\"ifd\":\"receive\""),
            "{want}"
        );
    }
    raw("ALTER TABLE Element ADD later STRING");
    let store = Store::open(&home).unwrap();
    let command = json!({"code.masher.widget": {}});
    let Err(Failure::Store(error @ StoreError::Schema(_))) = store.execute(B, &map, &command)
    else {
        panic!("a table this build does not know is refused");
    };
    let message = error.to_string();
    assert!(
        message.contains("table Element has (") && message.contains("later STRING"),
        "{message}"
    );
    let answer = store_failure_json(&command, &error);
    assert!(
        !answer.to_string().contains("may or may not be stored"),
        "{answer}"
    );
    drop(store);
    raw("ALTER TABLE Element DROP later");
    let store = Store::open(&home).unwrap();
    assert_eq!(
        reads(&store, &map),
        before,
        "the refused open changed nothing"
    );
}

/// R-6.24: a project's main map holds the specification layer's definition exactly as the code
/// defines it, from its first command, and a stored definition that has drifted from the code is
/// brought back on the next server run. A standalone map gets no definition.
#[test]
fn a_main_map_holds_the_specification_layer_definition() {
    use metaform_core::specification::{DEFINITION_ADDRESS, definition};
    let dir = tempfile::tempdir().unwrap();
    let home = dir.path().join("home");
    let defined = |store: &Store, map: &MapKey| {
        store
            .execute(B, map, &json!({ DEFINITION_ADDRESS: {} }))
            .map(|read| read[DEFINITION_ADDRESS].clone())
    };
    let wanted = Value::Object(definition());
    let (map, file) = {
        let store = Store::open(&home).unwrap();
        let map = project(&store, dir.path());
        assert_eq!(
            defined(&store, &map).unwrap()["instruction"],
            wanted["instruction"]
        );
        let standalone = MapKey::standalone("private");
        assert!(
            defined(&store, &standalone).is_err(),
            "a standalone map is not seeded"
        );
        let DbKey::Project(id) = &map.db else {
            unreachable!()
        };
        let file = home.join("projects").join(id).join("project.lbug");
        (map, file)
    };
    {
        // Drift the stored definition as an older build would leave it: other instruction
        // text and a field the code no longer defines.
        let db = lbug::Database::new(&file, lbug::SystemConfig::default()).unwrap();
        let conn = lbug::Connection::new(&db).unwrap();
        conn.query(&format!(
            "MATCH (e:Element) WHERE e.address = '{DEFINITION_ADDRESS}' \
             SET e.extra = '{{\"instruction\": \"old\", \"retired\": \"x\"}}'"
        ))
        .unwrap();
    }
    {
        let store = Store::open(&home).unwrap();
        let read = defined(&store, &map).unwrap();
        assert_eq!(
            read["instruction"], wanted["instruction"],
            "the code's text is restored"
        );
        assert!(
            store.check_graph(&map).unwrap().is_empty(),
            "R-4.16 nesting is complete"
        );
    }
    let db = lbug::Database::new(&file, lbug::SystemConfig::default()).unwrap();
    let conn = lbug::Connection::new(&db).unwrap();
    let rows: Vec<Vec<lbug::Value>> = conn
        .query(&format!(
            "MATCH (e:Element) WHERE e.address = '{DEFINITION_ADDRESS}' RETURN e.extra"
        ))
        .unwrap()
        .collect();
    let [lbug::Value::String(extra)] = rows[0].as_slice() else {
        panic!("{rows:?}");
    };
    assert!(
        !extra.contains("retired"),
        "a field the code no longer defines is removed: {extra}"
    );
}

/// `execute_all`: each command sees the ones before it, all land in one transaction with one
/// announcement, and a refused command leaves the map as it was, with its position named.
#[test]
fn a_batch_is_stored_whole_or_not_at_all() {
    let dir = tempfile::tempdir().unwrap();
    let store = Store::open(dir.path()).unwrap();
    let map = project(&store, dir.path());
    store.execute(B, &map, &json!({".": {}})).unwrap(); // seeds the definition first
    let announced = store.subscribe(&map);
    let element = json!({"add": {"code.pipeline": {"technical_name": "pipeline", "name": "Frame mover", "role": "DE"}}});
    let blocks = |code: &str| {
        json!({"update": {"code.pipeline": {"specification": [{"level": 1, "code": code, "title": "Purpose", "text": "Moves frames."}]}}})
    };
    let results = store
        .execute_all(A, &map, &[element.clone(), blocks("PL-1")])
        .unwrap();
    assert_eq!(results.len(), 2);
    assert_eq!(announced.try_iter().count(), 1, "one announcement for the batch");
    let read = |store: &Store| {
        store
            .execute(B, &map, &json!({"code.pipeline": {"specification": {}}}))
            .unwrap()
    };
    let before = read(&store);
    assert!(before.to_string().contains("PL-1"), "{before}");

    // The second command is refused (a skipped heading level), so the first is not stored.
    let bad = json!({"update": {"code.pipeline": {"specification": [{"level": 2, "title": "Deep", "text": "x"}]}}});
    let failed = store
        .execute_all(A, &map, &[blocks("PL-2"), bad])
        .unwrap_err();
    assert_eq!(failed.index, Some(1));
    assert!(matches!(failed.failure, Failure::Refused(_)));
    assert_eq!(read(&store), before, "nothing from the refused batch is stored");
    drop(store);
    let store = Store::open(dir.path()).unwrap();
    assert_eq!(read(&store), before, "and nothing reached the database");
}

/// One number from a query run straight against a closed store's database file.
fn count(file: &Path, query: &str) -> i64 {
    let db = lbug::Database::new(file, lbug::SystemConfig::default()).unwrap();
    let conn = lbug::Connection::new(&db).unwrap();
    let row = conn.query(query).unwrap().next().unwrap();
    match row.as_slice() {
        [lbug::Value::Int64(n)] => *n,
        other => panic!("{query}: {other:?}"),
    }
}

/// R-4.6: layers are stored as a structure of arrays, one `Record` node per item, and the map
/// reads back byte for byte after a reopen, in canonical field order whatever order it was
/// written in. Changing, shortening or removing a layer leaves exactly its remaining records,
/// and a database made before records existed has its layers moved out of `extra` on open.
#[test]
fn layers_are_records_and_the_map_reads_back_byte_for_byte() {
    let dir = tempfile::tempdir().unwrap();
    let home = dir.path().join("home");
    let file = home.join("maps").join("maps.lbug");
    let map = MapKey::standalone("soa");
    let records = "MATCH (r:Record) WHERE r.mapId = 'soa' RETURN count(r)";
    let dump = |store: &Store| store.execute(B, &map, &json!({".": {}})).unwrap().to_string();
    let written = {
        let store = Store::open(&home).unwrap();
        // A list is a layer's records, so the layer is defined first (R-6.24). `sources` is a
        // system layer (R-6.15) and needs no definition.
        let define = json!({"update": {"layer.knowledge.features": {"instruction": "Tag each element with the groups it belongs to."}}});
        store.execute(A, &map, &define).unwrap();
        let add = json!({"add": {"code.alpha": {
            "role": "SE", "zeta": "last by name", "name": "Alpha part", "technical_name": "alpha",
            "features": [{"b": 1, "a": {"y": 2, "x": [1, 2]}}, "naïve ✓ \"quoted\"", 3],
            "sources": [], "memory": [{"fact": "one"}, {"fact": "two"}]}}});
        store.execute(A, &map, &add).unwrap();
        let written = dump(&store);
        assert!(
            written.contains(r#"{"technical_name":"alpha","name":"Alpha part","role":"SE","features""#),
            "intake fields first, then the rest by name: {written}"
        );
        written
    };
    assert_eq!(count(&file, records), 5, "one record per layer item");
    let store = Store::open(&home).unwrap();
    assert_eq!(dump(&store), written, "byte for byte after a reopen");

    let change = json!({"update": {"code.alpha": {
        "features": [{"b": 1, "a": {"y": 2, "x": [1, 2]}}, "changed"], "memory": null}}});
    store.execute(A, &map, &change).unwrap();
    let changed = dump(&store);
    drop(store);
    assert_eq!(count(&file, records), 2, "a shorter layer and a removed layer leave no records");
    let store = Store::open(&home).unwrap();
    assert_eq!(dump(&store), changed);
    drop(store);

    // A database from before records: the layer back in `extra`, and no Record or HOLDS table.
    let db = lbug::Database::new(&file, lbug::SystemConfig::default()).unwrap();
    let conn = lbug::Connection::new(&db).unwrap();
    for statement in [
        "MATCH (e:Element {key: 'soa|code.alpha'}) SET e.extra = '{\"features\":[{\"b\":1,\"a\":{\"y\":2,\"x\":[1,2]}},\"changed\"],\"sources\":[],\"zeta\":\"last by name\"}'",
        "MATCH (r:Record) DETACH DELETE r",
        "DROP TABLE HOLDS",
        "DROP TABLE Record",
    ] {
        conn.query(statement).unwrap();
    }
    drop(conn);
    drop(db);
    let store = Store::open(&home).unwrap();
    assert_eq!(dump(&store), changed, "the older database reads the same");
    drop(store);
    assert_eq!(count(&file, records), 2, "its layer moved into records");
    assert_eq!(
        count(&file, "MATCH (e:Element) WHERE e.extra CONTAINS 'features' RETURN count(e)"),
        0,
        "and out of extra"
    );

    let store = Store::open(&home).unwrap();
    store.execute(A, &map, &json!({"delete": {"code.alpha": {}}})).unwrap();
    drop(store);
    assert_eq!(count(&file, records), 0, "a deleted element leaves no records");
}
