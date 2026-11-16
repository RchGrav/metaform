//! Load check for storage note risk 4: many maps as partitions of one database.
//! Run: cargo run --release -p metaform-store --example many_maps -- <dir> <maps> <elements per map>
//! It reports write time and cold-load time for one map after a reopen. Not a test.

use std::time::Instant;

use metaform_store::{ClientId, MapKey, Store};
use serde_json::json;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let dir = std::path::PathBuf::from(&args[1]);
    let maps: usize = args[2].parse().unwrap();
    let per: usize = args[3].parse().unwrap();
    {
        let store = Store::open(&dir).unwrap();
        let start = Instant::now();
        for m in 0..maps {
            let key = MapKey::standalone(&format!("m{m}"));
            let mut parts = serde_json::Map::new();
            for e in 0..per {
                parts.insert(format!("p{e}"), json!({"name": format!("e{e}")}));
            }
            // One command per map: an update creating `per` children under code.group.
            for (name, fields) in parts {
                store
                    .execute(
                        ClientId(1),
                        &key,
                        &json!({"update": {format!("code.group.{name}"): fields}}),
                    )
                    .unwrap();
            }
        }
        let n = maps * per;
        let secs = start.elapsed().as_secs_f64();
        println!(
            "wrote {n} elements in {maps} maps: {secs:.1} s ({:.0} writes/s)",
            n as f64 / secs
        );
    }
    let store = Store::open(&dir).unwrap();
    for probe in [0, maps / 2, maps - 1] {
        let key = MapKey::standalone(&format!("m{probe}"));
        let start = Instant::now();
        let read = store
            .execute(ClientId(2), &key, &json!({"code.group.p0": {}}))
            .unwrap();
        let cold = start.elapsed();
        let start = Instant::now();
        store
            .execute(ClientId(2), &key, &json!({"code.group.p0": {}}))
            .unwrap();
        println!(
            "map m{probe}: cold load + read {cold:?}, warm read {:?} ({read})",
            start.elapsed()
        );
    }
}
