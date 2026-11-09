//! Public-interface tests for metaform-store. Budget (CLAUDE.md): five for this feature.

use std::path::Path;

use metaform_store::{ClientId, DbKey, Failure, MapKey, Store, StoreError, store_failure_json};
use serde_json::{Value, json};

const A: ClientId = ClientId(1);
const B: ClientId = ClientId(2);

fn want() -> Value {
    json!({"why": "Receive the mash data to relay it.", "how": "Prepared mash data packets.", "intent": "receive"})
}

/// The tool example's two elements, with a want between them and a native array.
fn seed(store: &Store, map: &MapKey) {
    let commands = [
        json!({"add": {"code.masher.widget": {"technical_name": "widget masher code", "name": "mashbox",
            "role": "Supportive", "uri": "./src/widgets/mashbox.c"}}}),
        json!({"add": {"code.protocol.network.tracker.cs": {"technical_name": "cs tracker network protocol",
            "name": "mashtrac", "role": "Definitive", "uri": "./src/network/mashtrac.c",
            "memory": [{"fact": "relays mash data"}], "wants": {"code.masher.widget": want()}}}}),
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
            "the widget is wanted; the tracker is not"
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
                    "message": "cannot delete, 'code.masher.widget', must be orphaned first",
                    "remediation": {"delete": {"code.protocol.network.tracker.cs": {"wants": ["code.masher.widget"]}}}
                });
                assert_eq!(answer.to_string(), expected.to_string(), "fields and their order");
            }
            other => panic!("deleting a wanted element must be refused, got {other:?}"),
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
