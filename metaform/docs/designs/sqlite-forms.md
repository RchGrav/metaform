# The Node and Python forms: one SQLite store, structure of arrays

**Status:** Proposed by an agent, 2026-11-09, for the owner's review. It carries out `SPEC.md` R-4.6: Metaform ships in three forms (Rust, Node, Python); Node and Python store their data in SQLite; every form stores data as a structure of arrays (SoA). The decisions below that R-4.6 does not state are engineering decisions, each with its reason.

## 1. What is the same in every form

An agent cannot tell the forms apart. Each form gives the one tool, `project-map`, over stdio MCP, with the same commands, the same answers and the same refusals, in the same key order. `metaform/conformance/` holds the cases that prove it: the Rust form's recorded answers, which the Node and Python forms must repeat exactly.

Each form has the same command line:

```text
<form> mcp  [--home DIR] [--project DIR]   stdio MCP for an agent harness; DIR defaults to .
<form> call [--home DIR] [--project DIR] '<json command>' | -
                                           one tool command. Exit 0 ok, 1 refused, 2 usage error.
<form> projects [--home DIR]               every registered project: id, name, folder
```

`<form>` is `node metaform/node/src/main.ts` or `python3 -m metaform` (with `metaform/python` on `PYTHONPATH`).

## 2. What differs from the Rust form, and why

| Subject | Rust form | Node and Python forms | Reason |
|---|---|---|---|
| Engine | LadybugDB | SQLite, which both languages have built in | R-4.6. No dependency to install. |
| Process | One server for each home; agents connect through forwarders | No server. Each agent's process opens the database itself. | SQLite lets several processes write one file safely. A server would add a part that SQLite makes unnecessary. |
| Write queue | The server's writer, one queue for each database | SQLite's write lock (section 4) | The lock already puts writers in a line. |
| Change announcements (R-4.10) | Pushed to subscribers after each commit | Not offered, and not advertised in the capabilities | A process cannot learn of another process's commit without polling, and polling is ruled out (`DECISIONS.md`). |
| Graph workspace | `metaform gui` | Not offered | The host needs change announcements. |
| Specification export and import (R-6.28) | `metaform specification` | Not offered yet | It is a CLI command, not part of the agents' form. It can be ported later with no change to the store. |
| Schema check | Hand-written shape check, then the JSON Schema files as a second check | The hand-written shape check only | The shape check gives every message an agent reads. A schema validator would be a dependency whose messages no agent sees. |
| Dependencies | Cargo crates | None | The owner's rule: write our own code. |

## 3. The store

### 3.1 The home

The home is the folder a form writes under. It is `--home`, or `METAFORM_HOME`, or `~/.metaform-sqlite`. The Node and Python forms use one format, so either can open a home the other made.

```text
<home>/store.format              one line: sqlite-soa 1
<home>/metaform.db               the core database: the project registry
<home>/projects/<id>/project.db  one project's maps
<home>/projects/<id>/source.txt  the project's folder, for a person who looks in the home
```

- A form writes the marker as `store.format.<process id>.tmp` and then links it into place, so another process sees the marker complete or not at all. A file with that temporary name does not count as a file in the home.
- A form refuses a home whose `store.format` holds anything else, and a home that has files and no `store.format`. The Rust form's home has a different format and is refused. **Reason:** two engines must never write one home.
- The project id is the Rust form's: the folder's canonical path with every character that is not an ASCII letter or digit replaced by `-`, followed by a three-digit number, the first that is free. **Reason:** one rule for a project's id in every form.
- Nothing is written into a project's own folder, and a project's database never holds the project's name (R-4.1). The name is in the core database only: `project(id, source, name)`.

### 3.2 A project's database

One narrow table for each field and each layer, keyed by element. No table holds an element as one record.

```sql
CREATE TABLE map     (id TEXT PRIMARY KEY);
CREATE TABLE element (key     INTEGER PRIMARY KEY,
                      map     TEXT    NOT NULL REFERENCES map(id),
                      address TEXT    NOT NULL,              -- stored form: camelCase segments (R-4.11)
                      parent  INTEGER REFERENCES element(key), -- NULL only for the root, whose address is "."
                      UNIQUE (map, address));
CREATE TABLE wants   (element   INTEGER NOT NULL REFERENCES element(key) ON DELETE CASCADE,
                      provider  INTEGER NOT NULL REFERENCES element(key),
                      why       TEXT NOT NULL,
                      how       TEXT NOT NULL,
                      direction TEXT NOT NULL,
                      PRIMARY KEY (element, provider)) WITHOUT ROWID;
CREATE TABLE field   (name TEXT PRIMARY KEY);   -- the catalog of field tables
CREATE TABLE layer   (name TEXT PRIMARY KEY);   -- the catalog of layer tables
CREATE TABLE holds   (element INTEGER NOT NULL REFERENCES element(key) ON DELETE CASCADE,
                      layer   TEXT    NOT NULL REFERENCES layer(name),
                      PRIMARY KEY (element, layer)) WITHOUT ROWID;  -- which elements have which layers

-- One of these for each scalar field, made in the transaction that first writes the field:
CREATE TABLE "f_<name>" (element INTEGER PRIMARY KEY REFERENCES element(key) ON DELETE CASCADE,
                         value   TEXT NOT NULL);             -- the value as JSON text
-- One of these for each layer (each field whose value is a list):
CREATE TABLE "l_<name>" (element INTEGER NOT NULL REFERENCES element(key) ON DELETE CASCADE,
                         ordinal INTEGER NOT NULL,
                         data    TEXT NOT NULL,              -- one record as JSON text
                         PRIMARY KEY (element, ordinal)) WITHOUT ROWID;
```

- `<name>` is the field's name in the stored form (camelCase). The table name is written as a quoted identifier with every `"` doubled, so no field name can alter a statement. Every value goes in as a bound parameter.
- SQLite ignores the case of ASCII letters in a table name, so `f_fooBar` (the field `foo_bar`) and `f_foobar` (the field `foobar`) would be one table. When a name's table would collide in this way with a table that exists, the later name gets the table `f__<the name in snake_case>` (or `l__...` for a layer). A stored name holds no underscore, so that name is always free. A form finds the table of a stored name by an exact, case-sensitive match in `sqlite_schema`: first `f_<name>`, then `f__<the name in snake_case>`. (Found by the Node build, 2026-11-09.)
- A name that holds the character U+0000 cannot be written in SQL text. Its table name has a period in that place; no stored name holds a period.
- A scalar is stored as JSON text (`"un_built"`, `3`, `true`), so a string, a number and a boolean come back as what they were.
- A layer's records are rows in order, one row for each record. Appending a record writes one row; it does not rewrite the list.
- `holds` has one row for each element that has a layer, including a layer whose list is empty. The Rust form keeps an empty list of a system layer (`"sources": []`) as a field that is present, and a layer table with no rows cannot say that. `holds` also answers which layers an element has without a look in every layer table.
- The foreign keys repeat two rules of the map in the database: a want's provider must exist, and an element that is wanted or has elements beneath it cannot be deleted. The commands refuse these first, with a remediation; the database refuses them again if a defect lets one through.
- A map is a partition: every element row names its map. A project's main map has the id `main`. Chained maps are not built in any form.

### 3.3 Reading a map back

The form loads a map into memory as the flat map of elements that the commands work on, then performs the command exactly as the Rust core does. An element's JSON is built in canonical order: `technical_name`, `name`, `role`, `uri`, `status`, then every other field by name; `why`, `how`, `direction` in a want. Stored order never reaches an agent.

A form keeps the loaded map between commands and reads `PRAGMA data_version` before it uses it. SQLite changes that number when another connection commits, so the form loads again only when the map changed.

## 4. Writes

Every connection sets:

```sql
PRAGMA journal_mode = WAL;     -- readers do not block the writer, and the writer does not block readers
PRAGMA synchronous  = FULL;    -- a commit is on disk before the form answers
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;    -- wait in line for the write lock
```

A write is one transaction:

1. `BEGIN IMMEDIATE`. This takes the write lock before anything is read, so no other process can write between this form's read and its write.
2. Load the map if `data_version` shows it changed.
3. Perform the command on a copy. A refusal ends here with `ROLLBACK`, and nothing is stored (R-5.8).
4. Store the effect as a difference: only the elements the command touched, and for each one only the fields, wants and layer rows that changed.
5. `COMMIT`, then answer. A write is acknowledged only after it commits (R-4.7).

A read is one read transaction, so it sees one committed state.

**What this does not give.** SQLite's line for the write lock is not first come, first served: a waiting process tries again at intervals until `busy_timeout` ends. Under heavy writing by many processes, one process can wait longer than another. R-4.7's fair queue is met in the Rust form. If a write waits more than five seconds, the form answers `INTERNAL_ERROR` and says that the write was not stored.

**Pitfalls the code must avoid.**
- Python's `sqlite3` starts transactions on its own by default. The connection is opened with `isolation_level=None`, and the form writes every `BEGIN`, `COMMIT` and `ROLLBACK` itself.
- A `CREATE TABLE` for a new field or layer happens inside the write transaction. SQLite makes it part of that transaction, so a refused or failed write leaves no empty table.
- A JSON number that is whole, such as `3.0`, is `3` in JavaScript. The forms store and return what their language parses; a caller must not rely on the difference.

## 5. Checks

| Check | What it establishes |
|---|---|
| `python3 metaform/conformance/run.py --form node` and `--form python` | The form's answers equal the Rust form's on every recorded step. It establishes nothing about inputs the cases do not hold. |
| The store's layout test in each form | Each field and each layer has its own table, and no table holds a whole element. |
| The two-process test | Several processes that write the same map at once all have their writes kept. |
| The ended-process test | After a writer is ended with SIGKILL, every acknowledged write is present and the database opens. It does not establish survival of power loss. |
| The shared-home test | A home written by one form reads the same through the other. |
