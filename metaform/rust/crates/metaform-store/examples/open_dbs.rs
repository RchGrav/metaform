//! Load check for storage note risk 5: memory with many project databases open at once.
//! Run: cargo run --release -p metaform-store --example open_dbs -- <dir> <projects> [cap]
//! It opens one database per project by writing one element to each, and prints the process's
//! resident memory (VmRSS), address space (VmSize) and thread count as the count grows. With a
//! cap below the project count, the least recently used databases close as it goes. Not a test.

use metaform_store::{ClientId, MapKey, Store};
use serde_json::json;

fn status(field: &str) -> String {
    std::fs::read_to_string("/proc/self/status")
        .unwrap_or_default()
        .lines()
        .find(|l| l.starts_with(field))
        .map(|l| l.split_whitespace().skip(1).collect::<Vec<_>>().join(" "))
        .unwrap_or_default()
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let dir = std::path::PathBuf::from(&args[1]);
    let projects: usize = args[2].parse().unwrap();
    let cap: usize = args.get(3).map_or(projects, |c| c.parse().unwrap());
    let store = Store::open_with_limit(&dir.join("home"), cap).unwrap();
    println!("store open: rss {}, size {}", status("VmRSS:"), status("VmSize:"));
    for p in 1..=projects {
        let source = dir.join(format!("project{p}"));
        std::fs::create_dir_all(&source).unwrap();
        let id = store.register_project(&source, &format!("project{p}")).unwrap();
        store
            .execute(ClientId(1), &MapKey::main(&id), &json!({"update": {"code.part": {"name": "part"}}}))
            .unwrap();
        if p.is_power_of_two() || p == projects {
            println!(
                "{p:>3} used: rss {}, size {}, {} threads ({} databases open)",
                status("VmRSS:"),
                status("VmSize:"),
                status("Threads:"),
                store.open_databases()
            );
        }
    }
}
