//! The map as a graph in Ladybug (R-4.16), with maps as partitions of one database (R-4.1,
//! `docs/designs/storage.md` 2.2).
//!
//! Every element is an `Element` node keyed by `<map id>|<stored address>`. Nesting is a
//! `CONTAINS` relationship from each element to its children. Each want is a `WANTS`
//! relationship from receiver to provider carrying `why`, `how` and `intent`. Stored keys and
//! address segments are camelCase; the agent's snake_case form exists only in memory and on
//! the wire (R-4.11).

use std::collections::BTreeMap;

use lbug::{Connection, Database, SystemConfig, Value};
use metaform_core::{Effect, Element, Fields, Map, MapRef, ROOT, agent_name, stored_name};
use serde_json::Value as Json;

use crate::StoreError;

const BUFFER_POOL: u64 = 64 << 20;
const MAX_DB_SIZE: u64 = 16 << 30;
/// Worker threads per open database. Ladybug's default is one per core (32 on the development
/// machine), so 64 open databases ran about 2,400 threads. At 1,000,000 elements a map scan took
/// 28 to 50 ms with 4 threads, 56 to 93 ms with 32, and 82 to 142 ms with 1; small maps were as
/// fast or faster with fewer (`docs/designs/storage.md`, risk 5).
const THREADS: u64 = 4;

/// Element fields with their own column. Every other field is kept, camelCase, in `extra`.
const COLUMNS: [&str; 5] = ["technical_name", "name", "role", "uri", "status"];
/// Want-record fields with their own property. Any other is kept in the record's `extra`.
const WANT_COLUMNS: [&str; 3] = ["why", "how", "intent"];

const DDL: &[&str] = &[
    "CREATE NODE TABLE IF NOT EXISTS Map(id STRING PRIMARY KEY)",
    "CREATE NODE TABLE IF NOT EXISTS Element(key STRING PRIMARY KEY, mapId STRING, address STRING, \
     technicalName STRING, name STRING, role STRING, uri STRING, status STRING, childMap STRING, extra STRING)",
    "CREATE REL TABLE IF NOT EXISTS ROOT(FROM Map TO Element)",
    "CREATE REL TABLE IF NOT EXISTS CONTAINS(FROM Element TO Element)",
    "CREATE REL TABLE IF NOT EXISTS WANTS(FROM Element TO Element, why STRING, how STRING, intent STRING, extra STRING)",
];

/// Open a grouping database with tuned settings and its schema.
pub fn open(path: &std::path::Path) -> Result<Database, StoreError> {
    let config = SystemConfig::default()
        .buffer_pool_size(BUFFER_POOL)
        .max_db_size(MAX_DB_SIZE)
        .max_num_threads(THREADS);
    let db = Database::new(path, config)?;
    {
        let conn = Connection::new(&db)?;
        for ddl in DDL {
            conn.query(ddl)?;
        }
    }
    Ok(db)
}

fn key(map: &str, address: &str) -> String {
    format!("{map}|{}", stored_name(address))
}

pub(crate) fn rows(
    conn: &Connection,
    query: &str,
    params: Vec<(&str, Value)>,
) -> Result<Vec<Vec<Value>>, StoreError> {
    let mut statement = conn.prepare(query)?;
    Ok(conn.execute(&mut statement, params)?.collect())
}

fn run(conn: &Connection, query: &str, params: Vec<(&str, Value)>) -> Result<(), StoreError> {
    rows(conn, query, params).map(|_| ())
}

/// Load one map. A map never written is the empty map (the root alone).
pub fn load(conn: &Connection, map: &str) -> Result<Map, StoreError> {
    let mut elements: BTreeMap<String, Element> = BTreeMap::new();
    let found = rows(
        conn,
        "MATCH (e:Element) WHERE e.mapId = $m \
         RETURN e.address, e.technicalName, e.name, e.role, e.uri, e.status, e.childMap, e.extra",
        vec![("m", map.into())],
    )?;
    for row in found {
        let mut it = row.into_iter();
        let address = agent_name(&text(it.next())?.unwrap_or_default());
        let mut fields = Fields::new();
        for column in COLUMNS {
            if let Some(v) = text(it.next())? {
                fields.insert(column.to_string(), Json::String(v));
            }
        }
        let child_map = text(it.next())?.map(MapRef);
        if let Some(extra) = text(it.next())? {
            for (k, v) in parse_object(&extra)? {
                fields.insert(agent_name(&k), v);
            }
        }
        elements.insert(
            address,
            Element {
                fields,
                wants: BTreeMap::new(),
                child_map,
            },
        );
    }
    let wants = rows(
        conn,
        "MATCH (a:Element)-[w:WANTS]->(b:Element) WHERE a.mapId = $m \
         RETURN a.address, b.address, w.why, w.how, w.intent, w.extra",
        vec![("m", map.into())],
    )?;
    for row in wants {
        let mut it = row.into_iter();
        let receiver = agent_name(&text(it.next())?.unwrap_or_default());
        let provider = agent_name(&text(it.next())?.unwrap_or_default());
        let mut record = Fields::new();
        for column in WANT_COLUMNS {
            if let Some(v) = text(it.next())? {
                record.insert(column.to_string(), Json::String(v));
            }
        }
        if let Some(extra) = text(it.next())? {
            for (k, v) in parse_object(&extra)? {
                record.insert(agent_name(&k), v);
            }
        }
        elements
            .get_mut(&receiver)
            .ok_or_else(|| StoreError::Corrupt(format!("want from missing element {receiver}")))?
            .wants
            .insert(provider, record);
    }
    Ok(Map::from_elements(elements))
}

/// Write an effect inside the caller's transaction. Nodes first, then wants, then
/// nesting, then removals, so every relationship finds both of its ends.
pub fn persist(conn: &Connection, map: &str, effect: &Effect) -> Result<(), StoreError> {
    run(conn, "MERGE (:Map {id: $m})", vec![("m", map.into())])?;
    ensure_root(conn, map)?;
    let mut created = Vec::new();
    for (address, element) in &effect.elements {
        if let Some(element) = element
            && upsert(conn, map, address, element)?
        {
            created.push(address.as_str());
        }
    }
    for (address, element) in &effect.elements {
        if let Some(element) = element {
            let k = key(map, address);
            run(
                conn,
                "MATCH (:Element {key: $k})-[w:WANTS]->() DELETE w",
                vec![("k", k.as_str().into())],
            )?;
            for (provider, record) in &element.wants {
                let (columns, extra) = split(record, &WANT_COLUMNS);
                let mut params = vec![
                    ("a", Value::from(k.as_str())),
                    ("b", Value::from(key(map, provider).as_str())),
                    ("extra", opt(extra)),
                ];
                for (name, value) in WANT_COLUMNS.iter().zip(columns) {
                    params.push((name, opt(value)));
                }
                run(
                    conn,
                    "MATCH (a:Element {key: $a}), (b:Element {key: $b}) \
                     CREATE (a)-[:WANTS {why: $why, how: $how, intent: $intent, extra: $extra}]->(b)",
                    params,
                )?;
            }
        }
    }
    for address in created {
        let k = key(map, address);
        if address == ROOT {
            run(
                conn,
                "MATCH (m:Map {id: $m}), (e:Element {key: $k}) CREATE (m)-[:ROOT]->(e)",
                vec![("m", map.into()), ("k", k.as_str().into())],
            )?;
        } else {
            let parent = address.rsplit_once('.').map_or(ROOT, |(head, _)| head);
            run(
                conn,
                "MATCH (p:Element {key: $p}), (e:Element {key: $k}) CREATE (p)-[:CONTAINS]->(e)",
                vec![
                    ("p", key(map, parent).as_str().into()),
                    ("k", k.as_str().into()),
                ],
            )?;
        }
    }
    for (address, element) in &effect.elements {
        if element.is_none() {
            run(
                conn,
                "MATCH (e:Element {key: $k}) DETACH DELETE e",
                vec![("k", key(map, address).as_str().into())],
            )?;
        }
    }
    Ok(())
}

/// Make sure the map's root element and its `ROOT` relationship exist. The root is in every map
/// from the start, so no write ever creates it, and without it the top-level elements would
/// have no `CONTAINS` parent.
fn ensure_root(conn: &Connection, map: &str) -> Result<(), StoreError> {
    let k = key(map, ROOT);
    let found = rows(
        conn,
        "MATCH (e:Element {key: $k}) RETURN e.key",
        vec![("k", k.as_str().into())],
    )?;
    if found.is_empty() {
        run(
            conn,
            "MATCH (m:Map {id: $m}) CREATE (m)-[:ROOT]->(:Element {key: $k, mapId: $m, address: $a})",
            vec![
                ("m", map.into()),
                ("k", k.as_str().into()),
                ("a", ROOT.into()),
            ],
        )?;
    }
    Ok(())
}

/// Check that a map's graph has the R-4.16 shape: one root reached by `ROOT`, and every other
/// element reached by exactly one `CONTAINS` from its parent address. Returns the problems found.
pub fn check(conn: &Connection, map: &str) -> Result<Vec<String>, StoreError> {
    let mut problems = Vec::new();
    let roots = rows(
        conn,
        "MATCH (:Map {id: $m})-[:ROOT]->(r:Element) RETURN r.address",
        vec![("m", map.into())],
    )?;
    if roots.len() > 1
        || roots
            .first()
            .and_then(|r| r.first())
            .is_some_and(|a| !matches!(a, Value::String(s) if s == ROOT))
    {
        problems.push(format!(
            "map {map}: ROOT does not reach exactly one '.' element"
        ));
    }
    let elements = rows(
        conn,
        "MATCH (e:Element) WHERE e.mapId = $m AND e.address <> '.' \
         OPTIONAL MATCH (p:Element)-[:CONTAINS]->(e) RETURN e.address, collect(p.address)",
        vec![("m", map.into())],
    )?;
    if !elements.is_empty() && roots.is_empty() {
        problems.push(format!("map {map}: elements exist but no ROOT"));
    }
    for row in elements {
        let address = text(row.first().cloned())?.unwrap_or_default();
        let parent = address
            .rsplit_once('.')
            .map_or(ROOT, |(head, _)| head)
            .to_string();
        let parents: Vec<String> = match row.get(1) {
            Some(Value::List(_, items)) => items
                .iter()
                .filter_map(|v| {
                    if let Value::String(s) = v {
                        Some(s.clone())
                    } else {
                        None
                    }
                })
                .collect(),
            _ => Vec::new(),
        };
        if parents != [parent.clone()] {
            problems.push(format!(
                "{address}: CONTAINS parents {parents:?}, expected [{parent}]"
            ));
        }
    }
    Ok(problems)
}

/// Create or replace one element node. Returns true if it was created.
fn upsert(
    conn: &Connection,
    map: &str,
    address: &str,
    element: &Element,
) -> Result<bool, StoreError> {
    let k = key(map, address);
    let exists = !rows(
        conn,
        "MATCH (e:Element {key: $k}) RETURN e.key",
        vec![("k", k.as_str().into())],
    )?
    .is_empty();
    let (columns, extra) = split(&element.fields, &COLUMNS);
    let mut params = vec![
        ("k", Value::from(k.as_str())),
        (
            "childMap",
            opt(element.child_map.as_ref().map(|m| m.0.clone())),
        ),
        ("extra", opt(extra)),
    ];
    for (name, value) in ["technicalName", "name", "role", "uri", "status"]
        .iter()
        .zip(columns)
    {
        params.push((name, opt(value)));
    }
    let set = "e.technicalName = $technicalName, e.name = $name, e.role = $role, e.uri = $uri, \
               e.status = $status, e.childMap = $childMap, e.extra = $extra";
    if exists {
        run(
            conn,
            &format!("MATCH (e:Element {{key: $k}}) SET {set}"),
            params,
        )?;
    } else {
        params.push(("m", map.into()));
        params.push(("address", stored_name(address).as_str().into()));
        run(
            conn,
            &format!("CREATE (e:Element {{key: $k, mapId: $m, address: $address}}) SET {set}"),
            params,
        )?;
    }
    Ok(!exists)
}

/// The named string columns, in order, and every other field as a camelCase JSON object.
fn split(fields: &Fields, columns: &[&str]) -> (Vec<Option<String>>, Option<String>) {
    let named = columns
        .iter()
        .map(|c| match fields.get(*c) {
            Some(Json::String(s)) => Some(s.clone()),
            Some(other) if !other.is_null() => Some(other.to_string()),
            _ => None,
        })
        .collect();
    let rest: serde_json::Map<String, Json> = fields
        .iter()
        .filter(|(k, _)| !columns.contains(&k.as_str()))
        .map(|(k, v)| (stored_name(k), v.clone()))
        .collect();
    let extra = (!rest.is_empty()).then(|| Json::Object(rest).to_string());
    (named, extra)
}

fn opt(value: Option<String>) -> Value {
    value.map_or(Value::Null(lbug::LogicalType::String), Value::String)
}

fn text(value: Option<Value>) -> Result<Option<String>, StoreError> {
    match value {
        Some(Value::String(s)) => Ok(Some(s)),
        Some(Value::Null(_)) | None => Ok(None),
        Some(other) => Err(StoreError::Corrupt(format!(
            "expected a string, got {other:?}"
        ))),
    }
}

fn parse_object(raw: &str) -> Result<serde_json::Map<String, Json>, StoreError> {
    match serde_json::from_str(raw) {
        Ok(Json::Object(o)) => Ok(o),
        _ => Err(StoreError::Corrupt(format!(
            "extra is not a JSON object: {raw}"
        ))),
    }
}
