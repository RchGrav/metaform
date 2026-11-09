//! The project registry in the chassis database, `metaform.lbug` (documentation set 1.2).
//! It holds each project's name and source folder. A project's own database never stores
//! the project's name (R-4.1).

use std::path::Path;

use lbug::{Connection, Database, Value};

use crate::StoreError;
use crate::graph::rows;
use crate::writer::transact;

pub fn create_schema(db: &Database) -> Result<(), StoreError> {
    let conn = Connection::new(db)?;
    conn.query("CREATE NODE TABLE IF NOT EXISTS Project(id STRING PRIMARY KEY, source STRING, name STRING)")?;
    Ok(())
}

/// Register `source` under `name`, or return its existing id. Runs on the chassis writer.
pub fn register(
    conn: &Connection,
    home: &Path,
    source: &Path,
    name: &str,
) -> Result<String, StoreError> {
    let source_text = source.to_string_lossy().to_string();
    if let Some(id) = find_with(conn, &source_text)? {
        return Ok(id);
    }
    let encoded: String = source_text
        .chars()
        .map(|c| if c.is_ascii_alphanumeric() { c } else { '-' })
        .collect();
    let projects = home.join("projects");
    let id = (1..)
        .map(|n| format!("{encoded}{n:03}"))
        .find(|id| !projects.join(id).exists())
        .expect("an unused number exists");
    let dir = projects.join(&id);
    std::fs::create_dir_all(&dir)?;
    std::fs::write(dir.join("source.txt"), format!("{source_text}\n"))?;
    transact(conn, |c| {
        rows(
            c,
            "CREATE (:Project {id: $id, source: $s, name: $n})",
            vec![
                ("id", id.as_str().into()),
                ("s", source_text.as_str().into()),
                ("n", name.into()),
            ],
        )
        .map(|_| ())
    })?;
    Ok(id)
}

pub fn find(db: &Database, source: &Path) -> Result<Option<String>, StoreError> {
    let conn = Connection::new(db)?;
    find_with(&conn, &source.to_string_lossy())
}

/// One registered project: its id (the folder under `projects/`), its name and its source folder.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Registered {
    pub id: String,
    pub name: String,
    pub folder: String,
}

/// Every registered project, by name and then id. Reads only; registers nothing. A project whose
/// name is missing is listed under its folder's last segment, so one incomplete row cannot hide
/// every project.
pub fn list(db: &Database) -> Result<Vec<Registered>, StoreError> {
    let conn = Connection::new(db)?;
    let mut projects = rows(&conn, "MATCH (p:Project) RETURN p.id, p.name, p.source", vec![])?
        .into_iter()
        .map(|row| {
            let mut cells = row.into_iter();
            let (Some(Value::String(id)), name, Some(Value::String(folder))) =
                (cells.next(), cells.next(), cells.next())
            else {
                return Err(StoreError::Corrupt("a project row has no id or no source".into()));
            };
            let name = match name {
                Some(Value::String(name)) => name,
                _ => Path::new(&folder)
                    .file_name()
                    .map(|n| n.to_string_lossy().to_string())
                    .unwrap_or_default(),
            };
            Ok(Registered { id, name, folder })
        })
        .collect::<Result<Vec<_>, StoreError>>()?;
    projects.sort_by(|a, b| (&a.name, &a.id).cmp(&(&b.name, &b.id)));
    Ok(projects)
}

pub fn source_of(db: &Database, id: &str) -> Result<Option<String>, StoreError> {
    let conn = Connection::new(db)?;
    first_string(rows(
        &conn,
        "MATCH (p:Project {id: $id}) RETURN p.source",
        vec![("id", id.into())],
    )?)
}

fn find_with(conn: &Connection, source: &str) -> Result<Option<String>, StoreError> {
    first_string(rows(
        conn,
        "MATCH (p:Project) WHERE p.source = $s RETURN p.id",
        vec![("s", source.into())],
    )?)
}

fn first_string(found: Vec<Vec<Value>>) -> Result<Option<String>, StoreError> {
    match found.into_iter().next().and_then(|r| r.into_iter().next()) {
        None => Ok(None),
        Some(Value::String(s)) => Ok(Some(s)),
        Some(other) => Err(StoreError::Corrupt(format!(
            "expected a string, got {other:?}"
        ))),
    }
}
