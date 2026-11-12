//! The map as a graph in Ladybug (R-4.16), with maps as partitions of one database (R-4.1,
//! `docs/designs/storage.md` 2.2).
//!
//! Every element is an `Element` node keyed by `<map id>|<stored address>`. Nesting is a
//! `CONTAINS` relationship from each element to its children. Each dependency is a `DEPENDS_ON`
//! relationship from receiver to provider carrying `op`, `ef` and `ifd`. Each item of a
//! layer (a non-empty array field, R-6.24) is a `Record` node reached by `HOLDS` from its element,
//! with its position in `ordinal` and the item itself as JSON in `data`. Ladybug stores every
//! property as its own column, so the data is a structure of arrays (R-4.6): a write changes only
//! the rows and columns that changed. Stored keys and address segments are camelCase; the
//! agent's snake_case form exists only in memory and on the wire (R-4.11).

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

/// Element fields with their own column. A non-empty array field is a layer, kept as `Record`
/// nodes. Every other field is kept, camelCase, in `extra`.
const COLUMNS: [&str; 5] = ["technical_name", "name", "role", "uri", "status"];
/// Dependency-record fields with their own property. Any other is kept in the record's `extra`.
const DEPENDENCY_COLUMNS: [&str; 3] = ["op", "ef", "ifd"];

/// What a table connects: a node table keyed by its first property, or a relationship table.
enum Shape {
    Node,
    Rel {
        from: &'static str,
        to: &'static str,
    },
}

/// One table of the map graph. Its properties, in order, are both the DDL and what `open`
/// expects to find in a database made earlier.
struct Table {
    name: &'static str,
    shape: Shape,
    properties: &'static [(&'static str, &'static str)],
}

const TABLES: &[Table] = &[
    Table {
        name: "Map",
        shape: Shape::Node,
        properties: &[("id", "STRING")],
    },
    Table {
        name: "Element",
        shape: Shape::Node,
        properties: &[
            ("key", "STRING"),
            ("mapId", "STRING"),
            ("address", "STRING"),
            ("technicalName", "STRING"),
            ("name", "STRING"),
            ("role", "STRING"),
            ("uri", "STRING"),
            ("status", "STRING"),
            ("childMap", "STRING"),
            ("extra", "STRING"),
        ],
    },
    Table {
        name: "Record",
        shape: Shape::Node,
        properties: &[
            ("key", "STRING"),
            ("mapId", "STRING"),
            ("layer", "STRING"),
            ("ordinal", "INT64"),
            ("data", "STRING"),
        ],
    },
    Table {
        name: "ROOT",
        shape: Shape::Rel {
            from: "Map",
            to: "Element",
        },
        properties: &[],
    },
    Table {
        name: "CONTAINS",
        shape: Shape::Rel {
            from: "Element",
            to: "Element",
        },
        properties: &[],
    },
    Table {
        name: "DEPENDS_ON",
        shape: Shape::Rel {
            from: "Element",
            to: "Element",
        },
        properties: &[
            ("op", "STRING"),
            ("ef", "STRING"),
            ("ifd", "STRING"),
            ("extra", "STRING"),
        ],
    },
    Table {
        name: "HOLDS",
        shape: Shape::Rel {
            from: "Element",
            to: "Record",
        },
        properties: &[],
    },
];

/// Property renames since the first store, applied on open to a database made before them:
/// `(table, old name, new name)`. Each runs only when the old name is present and the new one
/// is not, so it runs once.
const RENAMES: &[(&str, &str, &str)] = &[
    // The dependency fields took the intake's names (founder, 2026-11-12): `why` became `op`,
    // `how` became `ef`, and `direction` became `ifd`. `intent` is an earlier name of `direction`.
    ("DEPENDS_ON", "why", "op"),
    ("DEPENDS_ON", "how", "ef"),
    ("DEPENDS_ON", "direction", "ifd"),
    ("DEPENDS_ON", "intent", "ifd"),
];

/// Table renames since the first store, applied on open before `RENAMES`: `(old name, new name)`.
/// Each runs only when the old table is present and the new one is not.
const TABLE_RENAMES: &[(&str, &str)] = &[
    // A want record became a dependency (founder, 2026-11-12).
    ("WANTS", "DEPENDS_ON"),
];

impl Table {
    fn ddl(&self) -> String {
        let properties = self.properties.iter().map(|(p, t)| format!("{p} {t}"));
        match self.shape {
            Shape::Node => {
                let mut columns: Vec<String> = properties.collect();
                if let Some(first) = columns.first_mut() {
                    first.push_str(" PRIMARY KEY");
                }
                format!(
                    "CREATE NODE TABLE IF NOT EXISTS {}({})",
                    self.name,
                    columns.join(", ")
                )
            }
            Shape::Rel { from, to } => {
                let columns: Vec<String> = std::iter::once(format!("FROM {from} TO {to}"))
                    .chain(properties)
                    .collect();
                format!(
                    "CREATE REL TABLE IF NOT EXISTS {}({})",
                    self.name,
                    columns.join(", ")
                )
            }
        }
    }
}

/// Open a grouping database with tuned settings and its schema. A database made by an earlier
/// build is brought up to date by `RENAMES`. One whose tables differ from `TABLES` in any other
/// way is refused before anything is changed, read or written.
pub fn open(path: &std::path::Path) -> Result<Database, StoreError> {
    let config = SystemConfig::default()
        .buffer_pool_size(BUFFER_POOL)
        .max_db_size(MAX_DB_SIZE)
        .max_num_threads(THREADS);
    let db = Database::new(path, config)?;
    {
        let conn = Connection::new(&db)?;
        let renames = check_schema(&conn, path)?;
        // One transaction: the renames and any missing tables land together or not at all
        // (DDL rolls back in lbug 0.22.3).
        crate::writer::transact(&conn, |c| {
            for statement in &renames {
                c.query(statement)?;
            }
            for table in TABLES {
                c.query(&table.ddl())?;
            }
            move_layers_out_of_extra(c)
        })?;
    }
    Ok(db)
}

/// The names of the tables that exist in this database.
fn existing_tables(conn: &Connection) -> Result<Vec<String>, StoreError> {
    conn.query("CALL show_tables() RETURN name")?
        .map(|row| match row.as_slice() {
            [Value::String(name)] => Ok(name.clone()),
            other => Err(StoreError::Corrupt(format!(
                "show_tables returned {other:?}"
            ))),
        })
        .collect()
}

/// The properties a table has in this database, as name and type, in order.
fn properties(conn: &Connection, table: &str) -> Result<Vec<(String, String)>, StoreError> {
    // `table_info` takes a literal, not a parameter. `table` comes from `TABLES`, never input.
    conn.query(&format!("CALL table_info('{table}') RETURN name, type"))?
        .map(|row| match row.as_slice() {
            [Value::String(name), Value::String(kind)] => Ok((name.clone(), kind.clone())),
            other => Err(StoreError::Corrupt(format!(
                "table_info('{table}') returned {other:?}"
            ))),
        })
        .collect()
}

/// Compare every existing table of `TABLES` with what this build expects, with `RENAMES`
/// applied in memory. Returns the renames to apply, or refuses without changing anything.
/// A table that does not exist yet is not compared; `open` creates it.
fn check_schema(conn: &Connection, path: &std::path::Path) -> Result<Vec<String>, StoreError> {
    let mut existing = existing_tables(conn)?;
    let mut renames = Vec::new();
    // The name each table has in this database now, before any rename runs.
    let mut current: Vec<(&str, &str)> = Vec::new();
    for (old, new) in TABLE_RENAMES {
        let has_new = existing.iter().any(|e| e == new);
        if let Some(name) = existing.iter_mut().find(|e| e == old)
            && !has_new
        {
            *name = new.to_string();
            current.push((new, old));
            renames.push(format!("ALTER TABLE {old} RENAME TO {new}"));
        }
    }
    for table in TABLES
        .iter()
        .filter(|t| existing.iter().any(|e| e == t.name))
    {
        let stored = current.iter().find(|(new, _)| *new == table.name).map_or(table.name, |(_, old)| old);
        let mut found = properties(conn, stored)?;
        for (_, old, new) in RENAMES.iter().filter(|(t, _, _)| *t == table.name) {
            let has_new = found.iter().any(|(name, _)| name == new);
            if let Some(column) = found.iter_mut().find(|(name, _)| name == old)
                && !has_new
            {
                column.0 = new.to_string();
                renames.push(format!("ALTER TABLE {} RENAME {old} TO {new}", table.name));
            }
        }
        let expected: Vec<(String, String)> = table
            .properties
            .iter()
            .map(|(p, t)| (p.to_string(), t.to_string()))
            .collect();
        if found != expected {
            let list = |columns: &[(String, String)]| {
                columns
                    .iter()
                    .map(|(name, kind)| format!("{name} {kind}"))
                    .collect::<Vec<_>>()
                    .join(", ")
            };
            return Err(StoreError::Schema(format!(
                "{}: table {} has ({}); this build expects ({})",
                path.display(),
                table.name,
                list(&found),
                list(&expected)
            )));
        }
    }
    Ok(renames)
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
                dependencies: BTreeMap::new(),
                child_map,
            },
        );
    }
    let dependencies = rows(
        conn,
        "MATCH (a:Element)-[w:DEPENDS_ON]->(b:Element) WHERE a.mapId = $m \
         RETURN a.address, b.address, w.op, w.ef, w.ifd, w.extra",
        vec![("m", map.into())],
    )?;
    for row in dependencies {
        let mut it = row.into_iter();
        let receiver = agent_name(&text(it.next())?.unwrap_or_default());
        let provider = agent_name(&text(it.next())?.unwrap_or_default());
        let mut record = Fields::new();
        for column in DEPENDENCY_COLUMNS {
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
            .ok_or_else(|| StoreError::Corrupt(format!("dependency from missing element {receiver}")))?
            .dependencies
            .insert(provider, record);
    }
    let found = rows(
        conn,
        "MATCH (e:Element)-[:HOLDS]->(r:Record) WHERE e.mapId = $m \
         RETURN e.address, r.layer, r.ordinal, r.data",
        vec![("m", map.into())],
    )?;
    let mut layers: BTreeMap<(String, String), Vec<(i64, Json)>> = BTreeMap::new();
    for row in found {
        let mut it = row.into_iter();
        let address = agent_name(&text(it.next())?.unwrap_or_default());
        let layer = agent_name(&text(it.next())?.unwrap_or_default());
        let ordinal = match it.next() {
            Some(Value::Int64(n)) => n,
            other => {
                return Err(StoreError::Corrupt(format!(
                    "{address}: record ordinal {other:?}"
                )));
            }
        };
        let data = text(it.next())?.unwrap_or_default();
        let item = serde_json::from_str(&data).map_err(|_| {
            StoreError::Corrupt(format!("{address}: record data is not JSON: {data}"))
        })?;
        layers
            .entry((address, layer))
            .or_default()
            .push((ordinal, item));
    }
    // Row order is not guaranteed without ORDER BY, so the ordinal restores each layer's order.
    for ((address, layer), mut items) in layers {
        items.sort_by_key(|(ordinal, _)| *ordinal);
        let element = elements
            .get_mut(&address)
            .ok_or_else(|| StoreError::Corrupt(format!("record of missing element {address}")))?;
        if element.fields.contains_key(&layer) {
            return Err(StoreError::Corrupt(format!(
                "{address}: layer {layer} is in both extra and its records"
            )));
        }
        let items = items.into_iter().map(|(_, item)| item).collect();
        element.fields.insert(layer, Json::Array(items));
    }
    Ok(Map::from_elements(elements))
}

/// Write an effect inside the caller's transaction. `before` is the map the effect was computed
/// from, so only what changed is written: an element's columns when they changed, each dependency that
/// was added, changed or removed, and each layer record that was added, changed or removed.
/// Nodes first, then dependencies and records, then nesting, then removals, so every relationship finds
/// both of its ends.
pub fn persist(
    conn: &Connection,
    map: &str,
    before: &Map,
    effect: &Effect,
) -> Result<(), StoreError> {
    run(conn, "MERGE (:Map {id: $m})", vec![("m", map.into())])?;
    ensure_root(conn, map)?;
    let empty = Element::default();
    let mut created = Vec::new();
    for (address, element) in &effect.elements {
        let Some(element) = element else { continue };
        let old = before.element(address);
        if old.is_none_or(|old| node_values(old) != node_values(element))
            && upsert(conn, map, address, element)?
        {
            created.push(address.as_str());
        }
    }
    for (address, element) in &effect.elements {
        let Some(element) = element else { continue };
        let old = before.element(address).unwrap_or(&empty);
        persist_dependencies(conn, map, address, old, element)?;
        persist_layers(conn, map, address, old, element)?;
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
            let k = key(map, address);
            run(
                conn,
                "MATCH (:Element {key: $k})-[:HOLDS]->(r:Record) DETACH DELETE r",
                vec![("k", k.as_str().into())],
            )?;
            run(
                conn,
                "MATCH (e:Element {key: $k}) DETACH DELETE e",
                vec![("k", k.as_str().into())],
            )?;
        }
    }
    Ok(())
}

/// What the `Element` node holds for an element: its columns, `extra` and child map. Layers and
/// dependencies are stored apart.
fn node_values(element: &Element) -> (Vec<Option<String>>, Option<String>, Option<&str>) {
    let (columns, extra) = split(&element.fields, &COLUMNS);
    (
        columns,
        extra,
        element.child_map.as_ref().map(|m| m.0.as_str()),
    )
}

/// Store the dependencies that differ between `old` and `new`: a removed or changed dependency's edge is
/// deleted, and an added or changed dependency's edge is created.
fn persist_dependencies(
    conn: &Connection,
    map: &str,
    address: &str,
    old: &Element,
    new: &Element,
) -> Result<(), StoreError> {
    let k = key(map, address);
    for (provider, record) in &old.dependencies {
        if new.dependencies.get(provider) != Some(record) {
            run(
                conn,
                "MATCH (:Element {key: $a})-[w:DEPENDS_ON]->(:Element {key: $b}) DELETE w",
                vec![
                    ("a", k.as_str().into()),
                    ("b", key(map, provider).as_str().into()),
                ],
            )?;
        }
    }
    for (provider, record) in &new.dependencies {
        if old.dependencies.get(provider) == Some(record) {
            continue;
        }
        let (columns, extra) = split(record, &DEPENDENCY_COLUMNS);
        let mut params = vec![
            ("a", Value::from(k.as_str())),
            ("b", Value::from(key(map, provider).as_str())),
            ("extra", opt(extra)),
        ];
        for (name, value) in DEPENDENCY_COLUMNS.iter().zip(columns) {
            params.push((name, opt(value)));
        }
        run(
            conn,
            "MATCH (a:Element {key: $a}), (b:Element {key: $b}) \
             CREATE (a)-[:DEPENDS_ON {op: $op, ef: $ef, ifd: $ifd, extra: $extra}]->(b)",
            params,
        )?;
    }
    Ok(())
}

/// The element's layers: every non-empty array field, by name. An empty array stays in `extra`,
/// so a field written as `[]` reads back as `[]`.
fn layers_of(element: &Element) -> BTreeMap<&str, &[Json]> {
    element
        .fields
        .iter()
        .filter_map(|(name, value)| match value {
            Json::Array(items) if !items.is_empty() => Some((name.as_str(), items.as_slice())),
            _ => None,
        })
        .collect()
}

/// A record's key: the element's key, the stored layer name and the position. `$` cannot occur
/// in an address segment or a layer name, so the key is unambiguous.
fn record_key(element_key: &str, layer: &str, ordinal: usize) -> String {
    format!("{element_key}${layer}${ordinal}")
}

/// Store the layer records that differ between `old` and `new`, position by position.
fn persist_layers(
    conn: &Connection,
    map: &str,
    address: &str,
    old: &Element,
    new: &Element,
) -> Result<(), StoreError> {
    let k = key(map, address);
    let (old_layers, new_layers) = (layers_of(old), layers_of(new));
    let names: std::collections::BTreeSet<&str> =
        old_layers.keys().chain(new_layers.keys()).copied().collect();
    for name in names {
        let layer = stored_name(name);
        let was = old_layers.get(name).copied().unwrap_or_default();
        let is = new_layers.get(name).copied().unwrap_or_default();
        for ordinal in 0..was.len().max(is.len()) {
            let rk = record_key(&k, &layer, ordinal);
            match (was.get(ordinal), is.get(ordinal)) {
                (Some(a), Some(b)) if a == b => {}
                (Some(_), Some(item)) => run(
                    conn,
                    "MATCH (r:Record {key: $r}) SET r.data = $d",
                    vec![("r", rk.as_str().into()), ("d", item.to_string().into())],
                )?,
                (None, Some(item)) => create_record(conn, map, &k, &layer, ordinal, item)?,
                (Some(_), None) => run(
                    conn,
                    "MATCH (r:Record {key: $r}) DETACH DELETE r",
                    vec![("r", rk.as_str().into())],
                )?,
                (None, None) => {}
            }
        }
    }
    Ok(())
}

/// Create one layer record and the `HOLDS` relationship from its element.
fn create_record(
    conn: &Connection,
    map: &str,
    element_key: &str,
    layer: &str,
    ordinal: usize,
    item: &Json,
) -> Result<(), StoreError> {
    let ordinal_value = i64::try_from(ordinal)
        .map_err(|_| StoreError::Corrupt(format!("{element_key}: layer {layer} is too long")))?;
    run(
        conn,
        "MATCH (e:Element {key: $e}) \
         CREATE (e)-[:HOLDS]->(:Record {key: $r, mapId: $m, layer: $l, ordinal: $o, data: $d})",
        vec![
            ("e", element_key.into()),
            ("r", record_key(element_key, layer, ordinal).as_str().into()),
            ("m", map.into()),
            ("l", layer.into()),
            ("o", Value::Int64(ordinal_value)),
            ("d", item.to_string().into()),
        ],
    )
}

/// Move layers that an earlier build kept in `extra` into `Record` nodes. Runs inside `open`'s
/// schema transaction; an element is rewritten only when its `extra` holds a non-empty array, so
/// after the first open of an older database it changes nothing.
fn move_layers_out_of_extra(conn: &Connection) -> Result<(), StoreError> {
    let found = rows(
        conn,
        "MATCH (e:Element) WHERE e.extra IS NOT NULL RETURN e.key, e.mapId, e.extra",
        vec![],
    )?;
    for row in found {
        let mut it = row.into_iter();
        let (Some(k), Some(map), Some(extra)) = (text(it.next())?, text(it.next())?, text(it.next())?)
        else {
            continue;
        };
        let mut object = parse_object(&extra)?;
        let moved: Vec<(String, Vec<Json>)> = object
            .iter()
            .filter_map(|(name, value)| match value {
                Json::Array(items) if !items.is_empty() => Some((name.clone(), items.clone())),
                _ => None,
            })
            .collect();
        if moved.is_empty() {
            continue;
        }
        for (layer, items) in &moved {
            object.remove(layer);
            for (ordinal, item) in items.iter().enumerate() {
                create_record(conn, &map, &k, layer, ordinal, item)?;
            }
        }
        let rest = (!object.is_empty()).then(|| Json::Object(object).to_string());
        run(
            conn,
            "MATCH (e:Element {key: $k}) SET e.extra = $x",
            vec![("k", k.as_str().into()), ("x", opt(rest))],
        )?;
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
        .filter(|(_, v)| !matches!(v, Json::Array(items) if !items.is_empty()))
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
