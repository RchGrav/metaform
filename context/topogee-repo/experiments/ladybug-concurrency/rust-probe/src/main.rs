use lbug::{Connection, Database, SystemConfig};
fn cfg(multi: bool) -> SystemConfig {
    SystemConfig::default().buffer_pool_size(64 << 20).max_db_size(16 << 30).enable_multi_writes(multi)
}
fn q(c: &Connection, s: &str) -> String {
    match c.query(s) { Ok(r) => format!("ok: {}", r), Err(e) => format!("ERR: {e}") }
}
fn main() {
    let args: Vec<String> = std::env::args().collect();
    let dir = std::path::PathBuf::from(&args[2]);
    match args[1].as_str() {
        "multi" => {
            for multi in [args[3] == "true"] {
                let p = dir.join(format!("m{multi}.lbug"));
                let db = Database::new(&p, cfg(multi)).unwrap();
                let a = Connection::new(&db).unwrap(); let b = Connection::new(&db).unwrap();
                println!("multi={multi} schema {}", q(&a, "CREATE NODE TABLE N(id INT64 PRIMARY KEY, v STRING)"));
                println!(" a begin {}", q(&a, "BEGIN TRANSACTION"));
                println!(" a create {}", q(&a, "CREATE (:N {id: 1, v: 'a'})"));
                println!(" b begin {}", q(&b, "BEGIN TRANSACTION"));
                eprintln!(" (about to b create)");
                println!(" b create {}", q(&b, "CREATE (:N {id: 2, v: 'b'})"));
                println!(" b create same key {}", q(&b, "CREATE (:N {id: 1, v: 'dup'})"));
                println!(" a commit {}", q(&a, "COMMIT"));
                println!(" b commit {}", q(&b, "COMMIT"));
                println!(" count {}", q(&a, "MATCH (n:N) RETURN count(n)"));
            }
        }
        "hold" => {
            let db = Database::new(dir.join("h.lbug"), cfg(true)).unwrap();
            let c = Connection::new(&db).unwrap();
            let _ = c.query("CREATE NODE TABLE N(id INT64 PRIMARY KEY)");
            println!("holding"); std::thread::sleep(std::time::Duration::from_secs(4));
        }
        "second" => {
            match Database::new(dir.join("h.lbug"), cfg(true)) { Ok(_) => println!("second rw open: OPENED"), Err(e) => println!("second rw open: ERR {e}") }
        }
        "part2" => {
            let db = Database::new(dir.join("p2.lbug"), cfg(false)).unwrap();
            let c = Connection::new(&db).unwrap();
            for s in ["CREATE NODE TABLE E(k STRING PRIMARY KEY, m INT64) PARTITION BY HASH(m) PARTITIONS 4",
                "CREATE REL TABLE W(FROM E TO E, why STRING)",
                "CREATE (:E {k:'1|a', m:1}), (:E {k:'1|b', m:1}), (:E {k:'2|a', m:2})",
                "MATCH (a:E {k:'1|a'}), (b:E {k:'1|b'}) CREATE (a)-[:W {why:'x'}]->(b)",
                "MATCH (a:E {k:'1|a'})-[w:W]->(b) RETURN b.k, w.why",
                "CREATE (:E {k:'1|a', m:2})",
                "MATCH (e:E) WHERE e.m = 1 RETURN count(e)",
                "MATCH (e:E {k:'2|a'}) DETACH DELETE e",
                "MATCH (e:E) RETURN count(e)"] { println!("{s}\n  {}", q(&c, s)); }
        }
        "part" => {
            let db = Database::new(dir.join("p.lbug"), cfg(false)).unwrap();
            let c = Connection::new(&db).unwrap();
            for ddl in [
                "CREATE NODE TABLE E1(k STRING PRIMARY KEY, m STRING) PARTITION BY (m)",
                "CREATE NODE TABLE E2(k STRING, m STRING, PRIMARY KEY(k)) PARTITION BY m",
                "CREATE NODE TABLE E3(k STRING PRIMARY KEY, m INT64) PARTITION BY HASH(m) PARTITIONS 4",
                "CREATE NODE TABLE E4(k STRING PRIMARY KEY, m INT64) WITH (partitions=4)",
                "CREATE NODE TABLE E5 PARTITIONED (k STRING PRIMARY KEY, m INT64)",
                "CALL show_tables() RETURN *",
            ] { println!("{ddl}\n  {}", q(&c, ddl)); }
        }
        _ => {}
    }
}
