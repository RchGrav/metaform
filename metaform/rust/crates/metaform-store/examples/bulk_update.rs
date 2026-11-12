//! Load check: one command whose receiver dependencies many providers. A command writes one receiving
//! element (the tool contract), so its dependencies are the only rows that grow with it. Run:
//! cargo run --release -p metaform-store --example bulk_update -- <dir>
//! Not a test.

use metaform_store::{ClientId, MapKey, Store};
use serde_json::json;

fn main() {
    let dir = std::path::PathBuf::from(std::env::args().nth(1).expect("a folder"));
    let store = Store::open(&dir).unwrap();
    let key = MapKey::standalone("dependencies");
    for e in 0..200 {
        store.execute(ClientId(1), &key, &json!({"update": {format!("code.p{e}"): {"name": "provider"}}})).unwrap();
    }
    for count in [1usize, 10, 50, 200] {
        let dependencies: serde_json::Map<String, serde_json::Value> =
            (0..count).map(|e| (format!("code.p{e}"), json!({"op": "uses it", "ef": "calls it", "ifd": "receive"}))).collect();
        let start = std::time::Instant::now();
        store.execute(ClientId(1), &key, &json!({"update": {format!("code.r{count}"): {"name": "receiver", "dependencies": dependencies}}})).unwrap();
        println!("{count:>4} dependencies, one command: {:?}", start.elapsed());
    }
}
