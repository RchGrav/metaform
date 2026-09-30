# 03 Storage and the data access object

This section defines where Metaform keeps its data, the exact tables that hold it, and the data access object every module imports from the chassis to read and write it.
It covers the base database, the per-project store, the correction stack, layers, provenance, memory, selection, import, export and query. The meaning of the map is in 01-map and the behavior of layers is in 02-layers; this section states how both are stored and reached.

## Terms used in this section

- **Node:** anything a layer item can attach to. The two kinds are an element and a join, a subtype join included. A type address is where a node sits in the namespace, not a node itself.
- **Identity id:** the stable id of an element, join or layer item. It never changes: an element's id belongs to its address, which never changes, MAP-015, and a join keeps its id when it is moved, MAP-003.
- **Row:** one stored version of a thing, written by one layer. A thing has one row from the layer that added it and at most one more row from each correction layer that changed or removed it.
- **Correction stack:** the correction layers, in the order they were applied, on top of the intake map, STORE-017.
- **Current:** the version readers get when they ask for a thing by its identity id: the row from the highest correction layer in the stack that touches the thing, or the row that added it when no correction touches it. A thing whose current version is a removal is not current at all.

## Data placement

### STORE-001 All data lives in the Metaform home
- Requirement: All Metaform data is stored under the Metaform home, and nothing is written into a project's folder.
- What this means: The home is `~/.metaform` on every system, resolved from the user's home directory, so on Windows it is `C:\Users\<user>\.metaform`. The environment variable `METAFORM_HOME` replaces it when set. Registering a project, running any command in a project folder, running an intake and writing memory all leave the project folder byte for byte unchanged. No marker file, cache or database is created there.
- Why: Every agent, in any folder or worktree, reaches the same data. A project never carries copies that go stale, get committed by accident, or get picked up by build tooling as if they were source.
- How it shows: After any sequence of commands in a project folder, `git status` in that folder shows nothing new. Deleting `~/.metaform` removes every trace of Metaform's data.
- Build: The chassis resolves the home once per process as `Path(os.environ.get('METAFORM_HOME') or Path.home() / '.metaform').expanduser()`. Every path the chassis writes is built from that value with `pathlib`, never with string joins or `/` literals. Layout under the home:
  - `metaform.sqlite3`: the chassis database, STORE-002, holding nothing of any project.
  - `projects/<project folder>/`: everything of one project, named and laid out as PROJ-026 says: `source.txt`, `project.sqlite3`, one `<metaform name>.metaform.sqlite3` per metaform, `history.sqlite3`, `reports/`, `.metaform/`, `origin/` and the diffs of work.
  - `reports/` under the home: reports when no project is known, BASE-045.
  - `modules/`: the user place for modules, owned by the chassis loader, not by storage.
  - `skills/`: the installer's source copy of the skill, owned by the installer.
- Acceptance:
  - Run `add project`, a settings `set`, an element write and a memory write from inside a temporary project folder. The folder's file listing, including hidden files, is identical before and after.
  - With `METAFORM_HOME` set to a temporary folder, every file the run creates is under that folder.
- Relates to: STORE-002, STORE-003, STORE-030, CLI-014.
- Status: confirmed.

### STORE-002 The chassis database holds what belongs to no project
- Requirement: The chassis database `metaform.sqlite3` holds what belongs to no project: settings with their glue for the global scope and for folders outside every project, the working-folder table for those folders, module enable state, what the installer set up, and nonces. It holds no project, no metaform and nothing a project needs in order to be read, PROJ-026.
- What this means: These are the records that exist before and apart from any project's map. A folder's context is its settings, and the base database is where the home knows every folder without writing into it.
- Why: Settings and folder context must work in folders that belong to no project, and they must survive deleting or re-running a project's store. Keeping them apart from project stores means a project store holds only that project's map and layers.
- How it shows: `metaform` run in any folder reports that folder's project and settings from the base database alone.
- Build: Rich, 2026-09-30, PROJ-026: the `projects`, `metaforms` and `active_metaforms` tables below, and the settings and glue of folders inside a project's source, are the project's own and live in its `project.sqlite3`, in the same form; the chassis database keeps the rest.
  ```sql
  CREATE TABLE projects(
    project_id   TEXT PRIMARY KEY,       -- STORE-031 id rules
    path         TEXT NOT NULL,          -- absolute, resolved
    path_key     TEXT NOT NULL UNIQUE,   -- os.path.normcase(path), for comparison
    target_type  TEXT NOT NULL DEFAULT 'path'
                 CHECK(target_type IN ('path','url','artifact','inline','inferred')),  -- MAP-041
    target_value TEXT NOT NULL           -- the path itself when target_type is path
  );
  CREATE TABLE folders(
    path_key TEXT PRIMARY KEY,         -- os.path.normcase of the resolved folder path
    path     TEXT NOT NULL             -- as resolved, for display
  );
  CREATE TABLE settings(
    scope    TEXT NOT NULL,            -- 'global' or a folders.path_key
    owner    TEXT NOT NULL,            -- 'chassis' or the declaring module id, CLI-024
    key      TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,  -- 0 for a single value; 0, 1, 2 ... for each member of a list value
    value    TEXT NOT NULL,            -- JSON encoding of one value: the setting's value, or one member of a list
    PRIMARY KEY(scope, owner, key, position)
  );
  CREATE TABLE glue(
    scope TEXT NOT NULL,
    owner TEXT NOT NULL,
    key   TEXT NOT NULL,
    PRIMARY KEY(scope, owner, key)
  );
  CREATE TABLE module_state(
    module_id TEXT PRIMARY KEY,
    enabled   INTEGER NOT NULL CHECK(enabled IN (0, 1))
  );
  CREATE TABLE installs(               -- MCP-019: what the installer set up
    tool       TEXT PRIMARY KEY,
    source     TEXT NOT NULL,
    skill_path TEXT,
    installed  TEXT NOT NULL             -- ISO 8601 UTC
  );
  CREATE TABLE metaforms(               -- STORE-041
    metaform_id TEXT PRIMARY KEY,        -- 32 lowercase hex, STORE-007 form
    project_id  TEXT NOT NULL REFERENCES projects(project_id),
    name        TEXT NOT NULL,
    created     TEXT NOT NULL,           -- ISO 8601 UTC
    UNIQUE(project_id, name)
  );
  CREATE TABLE active_metaforms(        -- STORE-041: one active metaform per project
    project_id  TEXT PRIMARY KEY REFERENCES projects(project_id),
    metaform_id TEXT NOT NULL REFERENCES metaforms(metaform_id)
  );
  CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);  -- holds schema_version
  ```
  - A folder row is written the first time a folder-scoped setting is stored for it. Reads never write.
  - A folder's project is its `project` setting when set, otherwise the project found for it by PROJ-026: the folder under `projects/` named for its path or its nearest parent's, whose `source.txt` names that path.
  - A list-valued setting, such as `--modules` or `--layers`, is stored one row per member, in order, never as one list in one row, STORE-004. Reading a setting is one primary-key range read on scope, owner and key.
  - A stored setting is keyed by scope, owner and key, so a module can never read or overwrite another owner's stored value by declaring the same key, CLI-024. The current chassis keys settings by scope and key only; that changes.
  - `module_state` has a row only when a user has enabled or disabled a module. With no row, the module's own declaration decides, so a module that ships disabled stays disabled until enabled, the same three-case pattern as settings.
- Acceptance:
  - A read-only command against a home with no base database creates no file.
  - A project registered as `C:\Work\Proj` is found from the folder `c:\work\proj\src` on Windows, and not from a different case on Linux.
  - A module declared as shipping disabled is off with no `module_state` row, on after `enable`, and back to its declared state after its row is removed.
- Relates to: STORE-001, STORE-031, CLI-013, CLI-014, CLI-021, CLI-024, BASE-017, MAP-041.
- Status: confirmed for projects, folders, settings and glue. The target columns follow MAP-041, which is confirmed. The owner column follows CLI-024, which is confirmed. `module_state` replacing the current `disabled_modules` table is recommended.

### STORE-003 Each metaform has one store
- Requirement: Each metaform of a registered project has one SQLite store, `<metaform name>.metaform.sqlite3` in the project's folder, PROJ-026, holding its whole map and every layer attached to it.
- What this means: Types, elements, joins, subtypes, refs, layers, provenance, layer items, the correction stack, selection and hidden state for one metaform live in one file. A project with two metaforms has two stores, and nothing of one is in the other. Nothing about a map lives in the base database.
- Why: One file per metaform can be exported, copied, backed up or kept aside as a unit, which is what lets a project start over with a new metaform and keep the old one whole, MAP-045. Writers on different projects or metaforms never contend for the same file.
- How it shows: Starting a new metaform creates no rows in the old store. Other projects and all settings are unaffected by anything done in one metaform's store.
- Build: The store is created on the first write to the metaform. A read against a metaform with no store returns empty results and creates no file. Which metaform a project uses is its active metaform, STORE-041.
- Acceptance: A read of a metaform that has never been written leaves no `store.sqlite3` behind.
- Relates to: STORE-001, STORE-027, STORE-041, MAP-045.
- Status: recommended. More than one metaform per project, and every layer belonging to one metaform, are confirmed, MAP-045.

## Storage rules

### STORE-004 One row per thing
- Requirement: Every element, join, subtype, ref, layer item, selection and relation is its own row, and no row holds a collection of things.
- What this means: A join's refs are ref rows pointing at the join, not a list inside the join. A layer's items are item rows, not a document in a layer row. A row may hold the fields of the one thing it is, including one item's structured value, but never a list of other things that could be read or changed on their own.
- Why: A collection packed into a row makes every read load and parse the whole collection to find one member, and every change rewrite all of it. A join holding a thousand refs, or a layer holding a thousand items, in one row is a document squeezed into a table. One row per thing keeps every member reachable and changeable alone.
- How it shows: Adding one memory to a node that already has a thousand memories writes one row. Reading one ref of a join with a thousand refs reads one row.
- Build: Every table in this section follows this rule. Elements have their own table and joins have their own table, one row per join. The only JSON-encoded columns are `settings.value`, which is one setting's value or one member of a list setting, `items.value` and `properties.value`, which are the value of that one item or property, and `extra` on elements, joins, items and properties, which is the unknown fields of that one row, STORE-021. None of them may hold a collection: an item's value is one answer about one node, and a list of answers is written as that many items; an `extra` holding an array of records is split, each record stored as its own item, with a notice, BASE-044; a list setting is one row per member, STORE-002. Refs, tags, layer sources, layer fields, selections and the correction stack are each one row per member with an index, never a list in a row.
- Acceptance:
  - Write a join with 1000 refs, then add one ref. Exactly one row is inserted, and no existing row changes.
  - The schema has no column that holds a list of ids or a list of records of another kind.
  - `set --modules a,b,c` writes three `settings` rows; `add_item` with an `extra` whose value is an array of objects stores one item per object and returns a notice.
- Relates to: STORE-005, STORE-021.
- Status: confirmed.

### STORE-005 Every read goes straight to its answer through an index
- Requirement: Every read the data access object offers is answered through an index, and no read scans a whole table to find its answer.
- What this means: Each question agents ask has an index built for it: a thing by id, an element by address, the joins an element receives, the joins an element provides, the subtypes in a join, all items of a layer, all items at a node, the items that link to a node, and the children of a type. Table size does not change the cost of finding one answer.
- Why: Agents navigate by meaning, one question at a time: who receives this, why, how, what do other layers say here. Each question must go straight to its answer so the structure does the orienting and the agent keeps its inference for the task.
- How it shows: A read at one node of a store with a million items takes about as long as the same read in a store with a thousand.
- Build: The indexes are listed with each table. The data access object issues only the queries listed in STORE-025, each written against those indexes. SQLite is never read by walking records in order: the data access object is the engine around it that reaches every object by key. Some reads are allowed to read a whole table, because the table has at most a few rows per layer or per project and the answer is that table: `layers()` and the project list; `hidden_layers`, `layer_sources` and `correction_stack` during selection resolution and stack reads, STORE-019 and STORE-035; `layer_tags` when resolving `--layers`, where SQLite may choose a scan over the tag index for a table this small; and the starting selection falling back to `layers()` when the folder's `--layers` setting is unset. `search` matches through the FTS5 index of `item_text`, whose plan reports `SCAN item_text VIRTUAL TABLE INDEX`: that is the full-text index answering the match, not a table scan. No other read may scan.
  - Every read that returns a list takes `limit`, default 500, and `after`, the cursor the previous page returned, and returns its next cursor. `limit=0` returns the whole list in one read, for export and for pulling a whole layer. A page is one index range read.
  - Measured at scale, before step 52, when subtypes had a table of their own and an element could be relocated: a store built from this section's SQL with 105,000 element rows, 300,000 joins, 50,000 subtypes, 1,000,000 items, 50,000 properties, 300,000 refs, 20 layers, 300 selection rows and a correction stack of 10 layers, on SQLite 3.37 under WSL2, gave these medians:

    | Read | Rows | Median |
    |---|---|---|
    | `element` by address, with descriptor and refs | 1 | 0.18 ms |
    | `element` by id | 1 | 0.01 ms |
    | `joins` by receiver, in context with the relocation check, busiest receiver | 13 | 0.09 ms |
    | `identity`, busiest provider, selection per receiver | 13 | 0.28 ms |
    | `subtypes`, `where`, `links_to`, `history`, `stack`, `layers`, `has_intake` | 1 to 20 | 0.01 to 0.02 ms |
    | `node` in context / raw | 10 / 5 | 0.15 / 0.09 ms |
    | `effective_selection` at a five-segment address | | 0.04 ms |
    | `context` at a two-segment address | 80 | 0.32 ms |
    | `context` at the trunk `code`, first page | 500 | 5.2 ms |
    | `context` at the trunk `code`, whole | 9,884 | 100 ms |
    | `layer_items`, one page | 500 | 0.46 ms |
    | `layer_items`, a whole knowledge layer | 78,772 | 128 ms |
    | `search`, rare word / common word first page | 1 / 500 | 0.04 / 1.8 ms |
    | `citing` a path | 20 | 0.12 ms |
    | An intake's writes: 500 elements, 1,500 joins, 250 subtypes, 500 descriptor items, one transaction, median of three | | 467 ms |
    | `finish` of a correction layer: 500 element changes, 100 of them relocations with their join removals | | 105 ms |
    | `peel` of that layer | | 69 ms |
    | `discard` of a knowledge layer with 78,737 items | | 3.3 s |
- Acceptance:
  - For every read operation in STORE-025 and every write in STORE-024, `EXPLAIN QUERY PLAN` of each SQL statement it issues contains no `SCAN` of any table other than `layers`, `projects`, `hidden_layers`, `layer_sources`, `layer_tags` and `correction_stack`, and no `SCAN` of `item_text` other than `VIRTUAL TABLE INDEX`. Every other table it touches appears with `SEARCH` on an index or primary key. This test fails if a query or an index is changed so that a lookup on `elements`, `joins`, `current_subtypes`, `items`, `properties`, `refs`, `selections` or `types` falls back to a scan.
  - On a store loaded to the scale above, each read returning at most one page answers in a median of 5 ms or less, and each whole-list read in a median of 2 ms plus 15 µs per row returned or less. an intake of 500 elements written in one transaction commits within 1 s, median of three runs, `finish` of a correction layer with 500 changes within 500 ms, and `discard` takes at most 100 µs per row removed. At full scale, each read takes no more than three times as long per row returned as the same read at one-tenth of the scale, so cost follows the answer and not the store's size. Measured: a whole layer 1.5 µs per row at both scales; the trunk `context` 4.3 µs per row at one-tenth and 10.1 µs at full scale.
- Relates to: STORE-004, STORE-025.
- Status: confirmed. The paging arguments and the thresholds, set from the measurements above, are recommended.

### STORE-006 Writes are atomic and safe with many writers
- Requirement: Every write operation is one transaction, and many processes can write to the same store at once without losing or corrupting data.
- What this means: Each agent's MCP server is its own process, so several processes write to one project store at the same time. A write either lands completely or not at all. An interrupted import or correction leaves the store exactly as it was before it started.
- Why: A store that half-applies a write gives agents a map that is neither the old state nor the new one. Agents trust what they read, so partial state is worse than a failed write.
- How it shows: Two agents adding memories to the same node at the same moment both succeed. Killing a process in the middle of an import leaves the store as it was before the import.
- Build:
  - Every connection sets `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON` and `PRAGMA busy_timeout=30000`.
  - Inside one process, writers to one store take turns on a lock of that store, so SQLite's busy wait, which polls and is not fair, only ever settles writers of different processes. Without it, one of four threads in one process waited past five seconds on Windows and its write failed, Q48. The history database of a project, Q53, takes turns on the same kind of lock.
  - Every SQLite file, the base database, each store, the history database and the prompt database, is opened through one opener, `sqlite.opened`, and no connection to a file is made anywhere else. The opener takes the file's lock, and while holding it checks whether the file exists, opens the connection, checks the schema version, creates the schema of a new file and sends the pragmas; a write keeps the lock to the end of its transaction, a read lets go once its connection is prepared. The reason is the switch to WAL on a new file: SQLite makes it by taking a read lock and then asking for the exclusive lock, and it does not call the busy handler for that upgrade, so the switch fails at once with `database is locked` against any lock another connection holds on the file, however briefly. Four threads adding the same origin to a project with no history database yet met it in about one run of twenty, step 45; a read of a store, of the prompt database or of the base database during the write that creates it met the same failure, step 46. Once a file is in WAL mode the pragma changes nothing and takes no lock, so only the first connection ever makes the switch.
  - A new file is switched to WAL before its schema is written, so the schema lands under WAL and a reader in another process never waits on it or holds a lock across the switch. A read finds the file at one of three stages and is never told it is an earlier Metaform's: no file, or a file of no bytes, is read as an empty database in memory without opening the file; a file with tables and a schema version is read; a file with no tables yet, the header written and the schema not committed, is also read as an empty database in memory, since nothing in it is committed. Only a file that has tables and no schema version is refused as an earlier Metaform's, STORE-029. Before step 46 a reader that arrived during creation was refused with that message.
  - Two processes creating the same file in the same microseconds still race on the switch: each takes its read lock, and the first to ask for the exclusive lock fails at once. Nothing within SQLite lets that upgrade wait, and Metaform does not retry or poll, so that window is known and not closed; it needs two writers, since a reader of another process no longer touches a file before its header is written.
  - Each write operation opens `BEGIN IMMEDIATE`, performs all its statements and commits, or rolls back on any error. Each read operation opens a plain `BEGIN`, a deferred read transaction, so all its statements see one consistent state; in WAL mode readers never wait for the write lock and never block a writer.
  - Import, STORE-027, runs in one transaction.
- Acceptance:
  - Two processes each add 500 items to the same node concurrently. All 1000 items are present afterward.
  - An import killed partway leaves the item count and every current row unchanged.
- Relates to: STORE-027.
- Status: confirmed.

### STORE-007 Identity is a stable id that survives change
- Requirement: Every element, join and layer item has a stable identity id that never changes: an element's id belongs to its address, and a join keeps its id whatever it is moved to.
- What this means: An element's address names its type and is its identity, MAP-015: an element cannot be moved, and an element removed and recorded again at its address is the same element, STORE-009. A join can be moved to another receiver, another provider or another parent join and stays the same join, MAP-003. Everything attached, memory, challenges and other layer items, points at the identity id, so it stays with the element at its address and with the join wherever it goes. Identity ids also survive export, import, copying and moving a store.
- Why: The address says what kind of thing an element is, so the element at an address is that Type's realization, and what is known about it stays there. A join is where the map speaks about the artifact, so what is known about a join stays with it when understanding of which receiver it serves improves, Rich 2026-09-27.
- How it shows: After a join is moved from receiver `code.daemon` to receiver `code.manager.gateway.mesh`, its memories and challenges are read with it under the same join id.
- Build: Identity ids, and layer ids, are random UUID4 values written as 32 lowercase hex characters without dashes, `uuid.uuid4().hex`, generated by the data access object. A 32-character lowercase hex string is never a valid address or layer name, STORE-008 and STORE-013, so every argument that takes an address or an id, or a layer name or a layer id, reads as an id exactly when it matches `^[0-9a-f]{32}$`. Identity tables hold one row per identity id for as long as the store exists:
  ```sql
  CREATE TABLE element_ids(element_id TEXT PRIMARY KEY);
  CREATE TABLE join_ids(join_id TEXT PRIMARY KEY);   -- a join's receiver, provider and parent are its rows', so it can be moved
  ```
  Foreign keys point at identity tables, never at version rows, so a correction, a removal or a move never breaks a reference. A subtype join is a join, so its id is a join id, STORE-011.
- Acceptance:
  - Move a join that has two memories to another receiver. The memories are found through the join, whose identity id is unchanged, under the new receiver.
  - Export a project and import it into an empty home. Every identity id is identical.
- Relates to: STORE-009, STORE-010, STORE-011, STORE-017, STORE-027, MAP-003, MAP-015.
- Status: confirmed. An element cannot be moved and a join can, keeping its id: Rich, 2026-09-27.

## The map

### STORE-008 Type addresses are rows in a tree
- Requirement: Every namespace address used in a project is a row in the `types` table, linked to its parent address.
- What this means: The namespace is a tree of types. `code.engine.game.fps` is a type, and so are `code.engine.game`, `code.engine` and `code`, each a complete type in its own right. Writing any address writes the rows for it and for each of its prefixes that is missing. An address names the same Type in every project, so the Type tree is shared by construction: this table is each store's index of the addresses it uses, identical wherever the same address appears, and needs no shared table. Nothing attaches to a bare type address: items attach to elements and joins, and a layer that needs a place at a prefix creates an element there, STORE-039. The store checks only an address's form, per MAP-010 and MAP-013: one or more segments separated by periods, each segment one or more lowercase letters, digits or underscores, and the whole address not a match for `^[0-9a-f]{32}$`, which is the id form of STORE-007. An address in that form is never refused for being functionally invalid.
- Why: Selection, masking and properties travel the type tree from trunk to leaf, so the tree must be stored and walkable. Knowledge layers may link any namespace address, so the store records addresses as given and leaves typology judgments to the agents and workflows that make them.
- How it shows: A best practice attached as a property to the element `code.engine`, created by the knowledge layer when the project has none there, applies at every element whose address starts with `code.engine.`.
- Build:
  ```sql
  CREATE TABLE types(
    address TEXT PRIMARY KEY,
    parent  TEXT REFERENCES types(address)   -- NULL for a root such as 'code'
  );
  CREATE INDEX types_by_parent ON types(parent);
  ```
  The parent of an address is the address with its last dot-separated segment removed. Rows are inserted with `INSERT OR IGNORE`, root first. The form check is the regular expression `^[a-z0-9_]+(\.[a-z0-9_]+)*$`. An address that fails it is stored as given, and the result carries a notice naming the form, BASE-044. Its parents are still derived by removing the last dot-separated segment.
- Acceptance:
  - Writing an element at `code.engine.game.fps` into an empty store creates exactly four `types` rows with the right parents.
  - Writing an element at `Code..Engine` stores it and returns a notice naming the address form; writing one at `media.photo.jpg` succeeds with no notice.
  - Attaching an item at a bare type address creates an element at that address in the writing layer, attaches the item to it, and returns a notice saying so, BASE-044.
- Relates to: STORE-015, STORE-019, LAYER-005, LAYER-007, MAP-010, MAP-011.
- Status: confirmed for the tree and prefix rows. One shared Type tree follows D47: the address is the shared Type, and each store indexes the addresses it uses. No attachment at a bare type address follows D74.

### STORE-009 Elements
- Requirement: Each element is stored as its identity id, its current address, its name_length and its role, and every version of it is kept. Everything else about an element is linked to it.
- What this means: An element is one functional part of the artifact, or an entity outside it, recorded at a type address. The element record is that address with its identity, its `name_length`, the number of trailing address segments read backward to form its proper noun, MAP-012, and its role, AUE, VE, DE, SE or NE, MAP-017. Rich, 2026-09-27: the namespace address is the name index, and the element was meant to be only its address and name_length; roles stay on the element. The element holds no name. The project's own name for a functionality, its glossary or informal name, is on the join, STORE-010 and STORE-011, because joins are what speak to the artifact itself. Everything else is linked to the element: its refs are rows linked to its version, STORE-012, and any other field given for it is kept in its `extra`, STORE-021. An element a knowledge layer creates carries its address and, where the layer gives one, its name_length. It carries no role, D48: a role given for it is kept in its `extra` with a notice, BASE-044. An element a correction layer adds carries a role as the intake's do. An element's identity belongs to its address, and it cannot be moved, MAP-015. When an element is removed and an element is recorded again at the same address, it is the same element: its identity comes back, and with it every record still linked to it, the joins that name it, the items attached to it and its versions. Nothing is copied or relinked, because those records never left.
- Why: Elements are real records that everything else points at. The intake names them by address, so the current address must be one direct lookup, and the identity id, which belongs to the address, keeps attachments with the element whatever layer removes it and records it again.
- How it shows: `element code.bus.event` returns that element's current row in one read.
- Build:
  ```sql
  CREATE TABLE elements(
    row         INTEGER PRIMARY KEY,
    element_id  TEXT NOT NULL REFERENCES element_ids(element_id),
    layer_id    TEXT NOT NULL REFERENCES layers(layer_id),
    address     TEXT NOT NULL REFERENCES types(address),
    name_length INTEGER,                                -- MAP-012: trailing segments read backward as its proper noun
    role        TEXT,                                   -- MAP-017: AUE, VE, DE, SE or NE, stored as given
    extra       TEXT,                                   -- STORE-021
    op          TEXT NOT NULL DEFAULT 'add' CHECK(op IN ('add','change','remove')),  -- STORE-017
    reason      TEXT,
    evidence    TEXT,
    UNIQUE(element_id, layer_id)
  );
  CREATE TABLE current_elements(
    element_id TEXT PRIMARY KEY REFERENCES element_ids(element_id),
    row        INTEGER NOT NULL UNIQUE REFERENCES elements(row),
    address    TEXT NOT NULL UNIQUE,
    role       TEXT                                 -- the current row's role, for the map's entry
  );
  CREATE TABLE address_elements(
    address    TEXT PRIMARY KEY REFERENCES types(address),
    element_id TEXT NOT NULL REFERENCES element_ids(element_id)   -- the element this address last held
  );
  CREATE INDEX elements_by_layer ON elements(layer_id);
  CREATE INDEX current_elements_by_role ON current_elements(role, element_id);
  ```
  The current row carries the address so that address lookup of current elements is one unique-index read, and so that two current elements cannot hold the same address. It carries the role so that the map's entry is one direct read, `roots`, STORE-025: `current_elements_by_role` finds the VE and the DE, and the role is written with the address whenever a row becomes current.
  - An element cannot be moved, MAP-015: no write changes an element row's address. `edit` and `correct` given `address` for an element do not apply it and name it in a notice, STORE-034; the element at a better address is recorded as its own element, and the joins move to it.
  - Identity by address: `address_elements` remembers the element id of every address the store has held, written whenever an element row takes an address, in any layer, and whenever an element becomes current at an address through the correction stack or an import. `add_element` at an address with no current element reads that row first: when the id it names is not current, the new element row is written under that id, so the joins, items, properties and versions still pointing at it are its own again, and nothing is copied or relinked. Only an address never held gets a new id. This is the one mechanism behind a correction layer putting an element back, STORE-017, and a building layer's `remove` followed by another record at the same address, STORE-032.
  - Fields: `add_element(layer, address, name_length=, role=, refs=)` writes the element row with its name_length and role, and the refs as rows owned by that row, STORE-012. A name_length that is not a whole number is kept in the element's `extra`, and a whole number below 1 is stored as given, each with a notice; a role outside the five is stored as given with a notice, BASE-044. A role given in a layer other than the intake or a correction layer is kept in the element's `extra` with a notice, D48. Reads of an element return its identity, address, `reading`, `short_name`, name_length, role, refs and `extra`, MAP-012. While the element's layer can change in place, a building intake or correction layer or a knowledge layer, `edit` changes its name_length and role, STORE-032; once the metaform holds them, a correction layer changes them, STORE-017 and STORE-034.
  - `add_element` at an address a current element already holds returns that element, marked `existing: true`, and writes no element row. `differs` is true when the name_length or role given differ from the element's, and a notice names each of name_length, role and refs given that was not applied, with the layer the element belongs to. The address is the element's identity, so a repeated address is the same element.
  - A role is stored as given, or left out when none is given. The store does not refuse a missing role, STORE-026. The intake writes one role on every element it creates, MAP-017.
- Acceptance:
  - Looking up an element by address after two correction layers changed it returns the version from the higher one, through `current_elements`.
  - Adding a second element at an address that a current element already holds returns the existing element's id, marked existing, and writes no element row.
  - An intake element read back by address returns its name_length, its role and its `short_name`, the address read through name_length, from its own row; the `elements` row has `name_length` and `role` columns and no `name` column, and writing it writes no item.
  - An element a knowledge layer adds with a role reads back with no role and the role in its `extra`, and the call's notice names `role`.
  - An element removed from a building layer and recorded again at the same address has its first identity id, and a join that named it as provider reads back with it as provider again.
  - A memory item attached to an element is absent from `node` after a building layer removes the element, and reads back at the element after it is recorded again at the same address.
- Relates to: STORE-007, STORE-010, STORE-012, STORE-017, STORE-021, STORE-025, MAP-012, MAP-015, MAP-016, MAP-017.
- Status: confirmed: the element record is its identity, address, name_length and role, and the project's name for a functionality is on the join, Rich 2026-09-27; this replaces D78, which linked name, name_length, role and refs to the element as a descriptor item. The role on the current row and its index for `roots`, and the notices, are recommended. One current element per address in a project follows from an element being its address, and an element that cannot be moved follows from it too, Rich 2026-09-27. An element created by a layer other than the intake carries no role, D48: roles are the intake's classification of the artifact. Rich, 2026-09-27: an element removed and recorded again at its address is the same element, with every record related to it.

### STORE-010 Joins are owned by their receiver and run one way
- Requirement: Each join is stored with its receiver, or for a subtype join its parent join, its provider, name, purpose, function, relation, observation and non-goal as separate columns, and points from receiver to provider only.
- What this means: A join is one receiver's purpose served by one provider's encounter function. The receiver owns it. A relationship in the other direction is a different join with its own purpose. Both ends are elements. A join is never stored inside an element row and never as a list. The join carries the project's own name for the functionality it names, where the project has one, MAP-020: the join is where the map speaks about the artifact, and an element's only name is its address read through name_length, STORE-009. A subtype join is a join held inside its parent join, which owns it, STORE-011. A join can be moved, MAP-003: its receiver, provider or parent changes and it stays the same join.
- Why: Each join is one receiver's why served by one provider's how, so its meaning stays single. Receiver, purpose and encounter are different kinds of node with links in one direction, so the receiver, purpose and encounter structure cannot hold a cycle. Keeping each part in its own column lets the store answer the design's own questions directly. The identity of an element X, its C(T), is every current join where X is the provider: who receives it, why, and how. That is one indexed read. Rich, 2026-09-27: a function's join can be moved, so nothing ties a join's identity to its receiver.
- How it shows: `identity code.failsafe.gateway.mesh` lists every receiver of the failsafe with that receiver's purpose and the failsafe's function for it, from one index.
- Build:
  ```sql
  CREATE TABLE joins(
    row         INTEGER PRIMARY KEY,
    join_id     TEXT NOT NULL REFERENCES join_ids(join_id),
    layer_id    TEXT NOT NULL REFERENCES layers(layer_id),
    type        TEXT NOT NULL DEFAULT 'purpose',
    parent      TEXT REFERENCES join_ids(join_id),  -- a subtype join's parent join, STORE-011; NULL on every other join
    receiver    TEXT REFERENCES element_ids(element_id),  -- NULL on a subtype join, which its parent's receiver owns
    provider    TEXT NOT NULL REFERENCES element_ids(element_id),  -- on a subtype join, the element it holds
    name        TEXT,      -- the project's own name for the functionality, MAP-020
    purpose     TEXT,
    function    TEXT,
    ef          TEXT CHECK(ef IN ('Function','Encounter')),  -- MAP-020
    relation    TEXT,
    verb        TEXT,      -- the verb of the relation, MAP-020
    observation TEXT,
    non_goal    TEXT,
    extra       TEXT,                                -- STORE-021
    op          TEXT NOT NULL DEFAULT 'add' CHECK(op IN ('add','change','remove')),  -- STORE-017
    reason      TEXT,
    evidence    TEXT,
    UNIQUE(join_id, layer_id)
  );
  CREATE TABLE current_joins(                        -- joins held by a receiver; never a subtype join, STORE-011
    join_id  TEXT PRIMARY KEY REFERENCES join_ids(join_id),
    row      INTEGER NOT NULL UNIQUE REFERENCES joins(row),
    receiver TEXT NOT NULL,
    provider TEXT NOT NULL
  );
  CREATE INDEX current_joins_by_receiver ON current_joins(receiver);
  CREATE INDEX current_joins_by_provider ON current_joins(provider);
  CREATE INDEX joins_by_layer ON joins(layer_id);
  ```
  - `join_ids` holds only the id, STORE-007, so a change of a join's receiver, provider or parent keeps its id, its history and what is attached to it. Moving a join is a change of those fields: in place in a layer that can change in place, STORE-032, and as a `change` row in a correction layer, STORE-017 and STORE-034.
  - Both ends reference `element_ids`, so only an element is a join end; a subtype join is a join and never an end.
  - Nothing checks for cycles among elements. Two elements may each receive from the other through two joins.
- Acceptance:
  - Two joins, A receives from B and B receives from A, both store and both read back.
  - Writing a join whose provider is a join's id is an error naming the id, since no element has it, and writes nothing.
  - The identity read of an element with 50 provider joins among 100000 joins uses `current_joins_by_provider`.
  - A join written with a name reads back with it, and a join written without one reads back with none.
  - A join moved to another receiver in a knowledge layer keeps its id and its memory, and is returned by the new receiver's `joins` read and not by the old one's.
- Relates to: STORE-007, STORE-009, STORE-011, STORE-025, STORE-034, MAP-001, MAP-002, MAP-003, MAP-020.
- Status: confirmed. The name on the join: Rich, 2026-09-27. A join can be moved and stays the same join: Rich, 2026-09-27; the `parent` column and the nullable receiver are recommended.

### STORE-011 Subtype joins live inside one join
- Requirement: A subtype join is a `joins` row of type `subtype` held inside one purpose join and naming the element it holds, with its own encounter function and its own purpose, and its current row is kept apart from the current joins every read of the element graph uses.
- What this means: Annealing combines parts that share the same join into a larger parent functionality, MAP-030. The join carries the purpose and the combined encounter. Each absorbed part stays one ordinary element record, STORE-009, and a subtype join under the purpose join places it, keeping its own encounter function, name, relation, verb, observation, optional non_goal and refs. A subtype join carries its own purpose, the share of the parent's purpose the part serves, in the purpose column as any join's is, corrected 2026-09-29: kept in the extra it was set apart from the join it describes, and a read by purpose did not find it. A part whose purpose the parent's cannot carry does not share the join and is its own element of the outer map, MAP-030. It is a join, so it has a join id, a layer, a history and attachments like any join, and absorbing a join into a parent, or moving a subtype join to another parent, keeps them, MAP-003. Its parent join's receiver owns it. It is never an edge of the outer map, and an element held only by subtype joins is never a root, MAP-031.
- Why: Annealing keeps the root map minimal without discarding functionality. A subtype join exists only because it shares that join with its parent, so it lives there. Before step 52 subtypes had a table of their own, whose rows could only point at a join, so that no query could pull a subtype into the element graph by forgetting a filter. The shape below keeps that true of the subtype join by keeping its current row out of `current_joins`, the table every read of the element graph uses.
- How it shows: `subtypes <join>` lists the subtype joins inside the failsafe's join, each with its own function and the probe it holds. `where code.probe.echo` answers with the probe's element, its subtype join and the join it lives in, not as a root element.
- Build:
  ```sql
  -- A subtype join is a row of `joins`, STORE-010: type 'subtype', `parent` its parent join,
  -- `provider` the element it holds, no receiver, and its own purpose.
  CREATE TABLE current_subtypes(
    join_id  TEXT PRIMARY KEY REFERENCES join_ids(join_id),
    row      INTEGER NOT NULL UNIQUE REFERENCES joins(row),
    parent   TEXT NOT NULL,     -- the join it sits in
    provider TEXT NOT NULL      -- the element it holds
  );
  CREATE INDEX current_subtypes_by_parent ON current_subtypes(parent);
  CREATE INDEX current_subtypes_by_provider ON current_subtypes(provider);
  ```
  - How the shape keeps the reason: a join's current row goes to `current_joins` when the row has no parent and to `current_subtypes` when it has one, in the one place every current row is written, `insert_current`, STORE-017. Every read of the element graph, the joins an element receives or provides, `identity`, the entry's joins in `roots` and the joins `graph` draws, reads `current_joins`, so no read can return a subtype join as an edge of the element graph by forgetting a filter; `subtypes`, `where` and the subtypes of `graph` and `layer_graph` reach subtype joins only through `current_subtypes_by_parent` and `current_subtypes_by_provider`. The element a subtype join holds is an element, so it is in `current_elements`. When subtype joins are its only joins it is the end of no row of `current_joins`, so the element graph built from `current_joins` never reaches it, and the reads that list elements by address or role for the outer map, `graph`, `layer_graph` and `roots`, leave it out through one check, `held_only`, MAP-031.
  - A subtype join's parent is a join held by a receiver: a parent that is a subtype join, that names no join, or that is the join itself cannot be read, STORE-026, and nothing is written, D5 and MAP-032.
  - The element it holds: `add_subtype` names it by address or id. An address with no current element gets one in the writing layer, written with the name_length and role given, STORE-009. An element already there keeps its own name_length and role, and each given that differs is named in a notice, as `add_element` does for an element already at its address. An element already held by another current subtype join is stored as given with a notice naming that subtype join, D4; one read on `current_subtypes_by_provider`.
  - A subtype join's refs are rows owned by its `joins` row, STORE-012; the element's own refs are on the element's row.
  - A subtype join's rows are found by `joins_by_layer` for finishing, peeling, discarding and exporting, STORE-005.
- Acceptance:
  - A subtype join written in a join is returned by the subtypes read for that join, and by no read of joins by receiver or provider.
  - Writing a subtype join with a purpose stores it with the purpose in its `extra`, and returns a notice.
  - No read that returns joins by receiver or provider, or the entry's joins, ever returns a subtype join.
  - Writing an item attached to a subtype join succeeds and is returned by the node read for that join.
  - The element a subtype join holds is one element record, read back by `element` with its id, address, name_length and role; a second subtype join holding it is stored and its notice names the first.
- Relates to: STORE-009, STORE-010, STORE-015, STORE-017, STORE-025, MAP-030, MAP-031, MAP-032.
- Status: confirmed for placement: Rich, 2026-09-27, an element always appears as one element record, annealing places it in its parent's join as a subtype join, and the element itself does not move. The storage shape and `held_only` are recommended. A subtype owns no joins; its joins lift to the parent when it is annealed, D3. A part serving two joins is its own element, D4. A subtype holds no subtypes, D5.

### STORE-012 Refs
- Requirement: Each ref is one key and value row attached to one version row of an element, join, property or layer item, a subtype join's row included.
- What this means: Refs carry type-specific or artifact-specific references, such as `path` pointing at a member file. They belong to the version they were written with, so a reader of a version gets exactly the refs that version had.
- Why: Refs are part of what a version says. Tying them to the version row keeps an earlier version readable exactly as it was after a correction layer changes its refs.
- How it shows: After a correction layer drops a stale path ref from a join, the join's history still shows the path in the intake's version, and the current version does not.
- Build:
  ```sql
  CREATE TABLE refs(
    ref_id    INTEGER PRIMARY KEY,
    owner     TEXT NOT NULL CHECK(owner IN ('element','join','item','property')),
    owner_row INTEGER NOT NULL,   -- elements.row, joins.row, items.row or properties.row
    position  INTEGER NOT NULL,   -- order as written
    key       TEXT NOT NULL,
    value     TEXT NOT NULL
  );
  CREATE INDEX refs_by_owner ON refs(owner, owner_row, position);
  CREATE INDEX refs_by_key_value ON refs(key, value);
  ```
  A `change` row in a correction layer copies forward the refs it keeps, as new rows pointing at the new version row.
  - Refs are written with their owner: the create operations of STORE-024 take a `refs` list of key and value pairs in order. A ref in that list that is not a key and a value, both text, is never refused, STORE-026: every writer that takes `refs` keeps it in the record's `extra` under `refs`, with the notice `A ref is a key and a value, both text; one was not, and kept in the extra under refs.`, `two were not` and so on, counted as PROJ-025 counts; `edit` and `correct` given a new `refs` list do the same. The rule is written once, in the store; the intake tools and the map's write verbs hand `refs` on as given, so an odd ref reaches the store from every writer and is placed there. `add_ref` adds one more ref to a thing's current version in a knowledge layer or a mutable layer at any time, STORE-032. A ref on a thing of the intake layer or of a finished correction layer changes only through a correction layer, STORE-017.
- Acceptance:
  - A join with refs `path=a` and `path=b`, changed by a correction layer to keep only `path=b`, reads back with one ref at the current version and two in its intake version.
  - `add_ref` on a thing in the intake layer writes nothing and returns a notice naming a correction layer, BASE-044.
- Relates to: STORE-004, STORE-017, STORE-025, STORE-032, MAP-021.
- Status: recommended. The lookup by key and value is required by MAP-021.

## Layers

### STORE-013 Layers and their declared behavior
- Requirement: Each layer is a row carrying its name, its module and its declared behavior: mutable or immutable, and hideable.
- What this means: Everything Metaform holds is a layer, the intake's map included. A layer carries one inferred variable. Declaring behavior on the layer lets the store apply corrections and visibility the same way for every layer. Transitivity is not a layer flag: an item is transitive exactly when it is a property, STORE-039, D73.
- Why: When every layer attaches the same way and declares its behavior, layers compose, and a module can add one without knowing about any other. No module rebuilds correction, hiding or propagation rules of its own.
- How it shows: `metaform query layers` and `metaform map layers` show each layer with its id, name, kind, module, completion and its three properties.
- Build:
  ```sql
  CREATE TABLE layers(
    layer_id   TEXT PRIMARY KEY,
    metaform_id TEXT NOT NULL,                        -- STORE-041: the metaform this layer belongs to, equal to its store's metaform
    name       TEXT NOT NULL UNIQUE,
    module     TEXT NOT NULL,
    variable   TEXT NOT NULL CHECK(variable <> ''),   -- LAYER-002: the one question the layer answers
    mutable    INTEGER NOT NULL CHECK(mutable IN (0, 1)),
    hideable   INTEGER NOT NULL CHECK(hideable IN (0, 1)),
    result_id  TEXT,                                  -- MAP-040: the intake result id, on an intake layer
    kind       TEXT NOT NULL DEFAULT 'layer'
               CHECK(kind IN ('layer','intake','memory','correction')),  -- STORE-032, STORE-017
    created    TEXT NOT NULL,                         -- LAYER-001: creation time, ISO 8601 UTC
    ready      TEXT                                   -- STORE-032: NULL while the layer is building, the finish time once finished
  );
  CREATE TABLE hidden_layers(layer_id TEXT PRIMARY KEY REFERENCES layers(layer_id));
  CREATE TABLE layer_fields(                          -- D21: the fields of the layer's one variable, one row per field
    layer_id TEXT NOT NULL REFERENCES layers(layer_id),
    position INTEGER NOT NULL,
    name     TEXT NOT NULL,
    PRIMARY KEY(layer_id, position)
  );
  ```
  - A layer's behavior is declared by the module that creates it, at creation, and never changes, D12.
  - A layer may declare the fields of its variable, such as imperative, why and evidence, one `layer_fields` row per field; an item's value is then one object with those fields. A layer with no declared fields takes any single value.
  - Hiding follows dependencies, D13: a layer whose `layer_sources`, STORE-036, include a hidden layer, directly or through other sources, is left out wherever a hidden layer is. The closure is computed from `hidden_layers` and `layer_sources`, both a few rows per layer, in the same read that resolves the selection.
  - A layer name is one to 128 characters of letters, digits, periods, underscores and hyphens, and is never a match for `^[0-9a-f]{32}$`. Every operation that takes a layer takes a layer reference: a layer id, per STORE-007, or a name, looked up through the `name` unique index.
  - Hiding writes a `hidden_layers` row and is allowed only for a hideable layer. A correction layer is never hideable, STORE-017. Hidden layers are left out of node reads and selection results unless the read asks for them by name.
- Acceptance:
  - Hiding a layer declared not hideable returns the error in STORE-026 and writes nothing.
  - A hidden layer's items are absent from the node read and present when that layer is read by name.
  - Hiding layer S hides layer D whose sources include S, and unhiding S shows D again.
- Relates to: STORE-014, STORE-016, STORE-017, STORE-018, LAYER-001, LAYER-002, LAYER-004, LAYER-006, MAP-040.
- Status: confirmed for mutable and hideable. Declared by the module at creation, D12; hiding follows dependencies, D13; declared variable fields, D21; no transitive flag, D73.

### STORE-014 Everything belongs to the layer that produced it
- Requirement: Every element, join, subtype and layer item records the layer that produced it.
- What this means: The intake's map is the intake's layer, the one that happens to create most of the nodes. A layer that creates a new element and join records them the same way. The core map an agent sees is a selection of the intake's layer, and an element proposed by a blind-spot pass lives in that pass's layer.
- Why: A layer can attach on an element, on a join, or on a new element and join it creates. If creation were special to the intake, layers could not create nodes and modules would not compose. One rule for every layer keeps them interchangeable.
- How it shows: Reading the challenge layer includes the new element and join it proposed. Selecting only the intake layer leaves them out.
- Build: `layer_id` is a required column on `elements`, `joins` and `items`; a subtype join is a `joins` row. The intake writes through the same operations as every other layer.
- Acceptance: An element created by a second layer is absent from a node read whose selection excludes that layer and present when it is included.
- Relates to: STORE-013, STORE-015, STORE-018, LAYER-001.
- Status: confirmed.

### STORE-015 Layer items carry one variable at one node
- Requirement: Each layer item is one row holding one value of its layer's variable, attached to one node, with an optional link to another node.
- What this means: An item attaches to an element or a join, a subtype join included, never to a bare type address, D74. An item about no map node attaches to an element its own layer creates for it, D22. Its value is that layer's variable at that node, such as one best practice, one challenge or one memory observation. The optional link points at another node; a memory relation links one node to another. Links are items, so the whole structure stays navigable from any node, and links may form cycles.
- Why: One variable per layer is what lets any set of layers be selected together. Links as items mean an item points at the real node instead of copying it, and following links backward from the map shows everything that refers to a node.
- How it shows: Reading memory at `code.guard.switch.gateway` by incoming links lists every memory relation that points at it.
- Build:
  ```sql
  CREATE TABLE items(
    row         INTEGER PRIMARY KEY,
    item_id     TEXT NOT NULL,
    layer_id    TEXT NOT NULL REFERENCES layers(layer_id),
    target_kind TEXT NOT NULL CHECK(target_kind IN ('element','join')),
    target_id   TEXT NOT NULL,     -- an identity id
    value       TEXT NOT NULL,     -- JSON: this one item's value, never a list of things
    link_kind   TEXT CHECK(link_kind IN ('element','join')),
    link_id     TEXT,
    extra       TEXT,
    op          TEXT NOT NULL DEFAULT 'add' CHECK(op IN ('add','change','remove')),  -- STORE-017
    reason      TEXT,
    evidence    TEXT,
    UNIQUE(item_id, layer_id)
  );
  CREATE TABLE current_items(
    item_id     TEXT PRIMARY KEY,
    row         INTEGER NOT NULL UNIQUE REFERENCES items(row),
    layer_id    TEXT NOT NULL,
    target_kind TEXT NOT NULL,
    target_id   TEXT NOT NULL,
    link_kind   TEXT,
    link_id     TEXT
  );
  CREATE INDEX current_items_by_layer  ON current_items(layer_id, row);
  CREATE INDEX current_items_by_target ON current_items(target_kind, target_id, layer_id);
  CREATE INDEX current_items_by_link   ON current_items(link_kind, link_id, layer_id);
  CREATE INDEX items_by_layer          ON items(layer_id);
  ```
  - `current_items_by_layer` pages a whole layer in `row` order; a layer at one node is answered by `current_items_by_target`. `items_by_layer` finds a layer's version rows for finishing, peeling, discarding and exporting without a scan, STORE-005.
  - The data access object checks that the target exists in its identity table.
  - `value` is one JSON value: a string, number, boolean, object or null, the answer to the layer's one variable at this node. When the layer declares fields, STORE-013, it is one object with those fields. It never holds a list of answers or a list of records: several answers at one node are several items, STORE-004. The store does not judge its content.
  - `extra` is a JSON object or NULL. It holds any further fields the writer supplies for this one item that are not the variable's answer, STORE-021. An `extra` that is not an object is stored as `{"value": <what was given>}`, with a notice.
- Acceptance:
  - All items of a layer, all items at a node, and all items linking to a node are each returned by one read using the matching index.
  - An item linking from A to B and another from B to A both store and both read back.
- Relates to: STORE-004, STORE-005, STORE-020, LAYER-003, LAYER-015.
- Status: confirmed for attachment to elements and joins, subtype joins included, and for links. No attachment at a bare type address, D74. Declared variable fields, D21. One value per item, never a collection, is confirmed, STORE-004.

### STORE-016 Provenance is one record per layer
- Requirement: Each layer other than memory has exactly one provenance row, recording the module and workflow that created it, the prompt, the model, the role, and whether it was blinded.
- What this means: Everything in a layer was produced the same way, by one producer following one prompt in one role, so one record describes the origin of every item in it. Items are added, changed or removed under the layer's own behavior, and none of that creates provenance. Nothing is recorded per item or per read. Memory is a layer with no provenance, because agents write it freely as working notes.
- Why: Provenance tracks what a feature of the system actually uses. Knowing how a layer was made, by which perspective, under which role, is what lets layers be trusted, compared and reproduced. Two critic layers over the same proposals are two fully described perspectives, blinded or not, one role each. Records per item or per read multiply with every change and serve no feature, and bloat works against a system whose purpose is to give agents only what matters.
- How it shows: `layer challenge.blind --provenance` shows one record. Adding a hundred items to the layer leaves that record unchanged.
- Build:
  ```sql
  CREATE TABLE provenance(
    layer_id TEXT PRIMARY KEY REFERENCES layers(layer_id),
    module   TEXT NOT NULL,
    workflow TEXT,
    prompt   TEXT,                   -- the full text as delivered
    model    TEXT,
    role     TEXT,
    blinded  INTEGER CHECK(blinded IN (0, 1))
  );
  ```
  - The row is written in the same transaction that creates the layer, from the provenance argument of the layer operation, STORE-024. Creating a layer other than memory without provenance writes a provenance row with every field empty except `module`, set to the calling module, and returns a notice, BASE-044.
  - `prompt` holds the prompt text the layer was produced from, as given. An intake layer's `prompt` is empty: every intake comes from the Canonical Intake, whose purpose never changes, so no copy of it is kept, STORE-044. Rich, 2026-09-26: every intake output comes from the same source prompt, whose function is the same each time, unlike prompts written on the fly; that prompt can be improved, but its purpose never changes, so there is no reason to keep a copy with each layer. When the prompt came from a stored prompt, the prompt store's `prompt_uses` row for the layer names the exact version, STORE-044. A version a layer is linked to is never changed or deleted.
  - The layer's report, feedback and shape files are its provenance refs: the `reports` rows with this layer id, STORE-043. A provenance read returns them as refs `report`, `feedback` and `shape` with their file names. They are refs on the one record, not further provenance.
  - A provenance read also returns `prompt_version`, the name, number and id of the stored prompt version the layer was made from, when it has one, STORE-044.
- Acceptance:
  - The store has no provenance table or column keyed by item, element, join or read.
  - Creating a layer with provenance and then writing 100 items leaves exactly one provenance row for that layer, with its fields unchanged.
  - A memory layer has no provenance row.
- Relates to: STORE-013, LAYER-010, REQ-101 to REQ-105 as corrected.
- Status: confirmed. A layer written by a person or a plain import has the same record, with `role` saying who or what wrote it, such as `person` or `import`, and `model` and `prompt` empty, D15. A second run of a workflow creates a new layer with its own record, D16.

### STORE-017 Correction layers are stacked in order and are the only way to change the metaform
- Requirement: The metaform changes only through correction layers, applied one on top of another in the order they were finished; they cannot be toggled, and only the top one can be peeled off.
- What this means: The metaform an agent reads is always the intake map with every correction layer applied in order. A correction layer is the only thing that can remove something from the metaform, move a join of it, release a subtype join from its parent join, or add something to it permanently. Knowledge layers extend the metaform only while they are toggled on; only a correction layer changes the metaform itself, and an approved blind-spot entry becomes a permanent record of the metaform, LAYER-015, in the way D89 settles. Correction layers are chronological: each is applied on top of the ones before it. They are never selected, masked, toggled or hidden. A correction layer in the middle of the stack cannot be deleted. To remove one, walk the stack backwards, peeling layers off the top one at a time, then rebuild the ones that were above it; or put another correction layer on top. Each correction layer carries its one provenance record like any layer. Anything built on a thing a correction changed or removed is re-examined, never rewritten, STORE-036.
- Why: The metaform is the shared foundation, so a change to it must be explicit, ordered and traceable. A stack applied in order gives one answer to what the metaform is at every moment, and each change keeps the provenance of the layer that made it. Toggling corrections would give different agents different foundations, and deleting one from the middle would silently change what every later correction was applied to; peeling from the top is the only removal that keeps every remaining layer applied to exactly what it was built against.
- How it shows: `metaform map stack` lists the correction layers in order. After a correction layer that moves a join to another receiver is finished, every read shows the join under the new receiver; `metaform map history <id>` shows the join as the intake wrote it and as each correction layer left it. Peeling a layer that is not on top is refused, naming the top layer.
- Build:
  ```sql
  CREATE TABLE correction_stack(
    position INTEGER PRIMARY KEY,                       -- 1 is the first correction applied
    layer_id TEXT NOT NULL UNIQUE REFERENCES layers(layer_id)
  );
  ```
  - A correction layer is a layer of kind `correction`, immutable and not hideable, with its one provenance record, STORE-013 and STORE-016. It is written through the knowledge-layer tool like any layer, STORE-032: while building, its rows are written and edited freely, and nothing in it is applied.
  - Its rows are versions in the ordinary tables, `elements`, `joins`, `properties` and `items`, with `layer_id` set to the correction layer and `op` saying what the row does:
    - `add`: a new thing with a new identity id, added to the metaform permanently.
    - `change`: a complete new version of an existing thing, under the same identity id. Fields not being changed are copied forward from the thing's current version, and so are its refs unless a complete new list is given, STORE-012. A join's receiver, provider and parent are changes: moving a join, to another receiver, to another provider, into a parent join as a subtype join, MAP-030, or out of its parent join to a receiver again, is a `change` of that join, which stays the same join with its id, its history and everything attached to it, MAP-003 and STORE-034.
    - An element's address is never a change, MAP-015: an element cannot be moved, since its address is its identity. A correction that gives an element another address is stored without it, and a notice says so, STORE-034. When a functionality belongs at a better address, the correction layer adds the element there, an `add` row, and moves the joins to it with `change` rows of those joins; what is attached to the old element stays with it. An element is only a namespace address, so removing it does not drop what is attached: those things are orphaned, and they show again if an element is put back at the same address. Putting an element back at an address whose element was removed is an `add` row that reuses that removed element's identity id, STORE-009, so orphaned things reattach without being rewritten. An `add` at an address that has had more than one removed element reuses the most recently removed one. Element records are only a namespace address and hold no data of their own; things are linked to them, which is why an element's attachments stay at its address and a join's stay with the join.
    - `remove`: the thing is no longer in the metaform.
    Each `change` and `remove` row carries `reason` and, optionally, `evidence`. Rows with `op` `add` in the intake layer, knowledge layers and memory are the things those layers wrote.
  - A correction layer corrects the metaform: the intake layer's things and things added by earlier correction layers. It never changes a knowledge layer's things. Correction layers always beat knowledge layers: they sit underneath, and knowledge layers sit on top of the metaform the stack leaves, LAYER-011.
  - `finish` on a correction layer, in one transaction: checks the rules of STORE-034 against the state after the layer is applied, and names in a notice what the layer leaves orphaned, BASE-044; inserts the layer at the next position on top of `correction_stack`; and applies it to the current tables, `current_elements`, `current_joins`, `current_subtypes`, `current_properties` and `current_items`: each `add` and `change` row becomes the thing's current row, and each `remove` deletes the thing's current row. A join's current row goes to `current_joins` or `current_subtypes` by whether its row has a parent, in `insert_current`, the one place every current row is written, STORE-011. It then writes re-examination marks, STORE-036. No row is left unapplied: the only rule that held a row back was a retype onto an address another element held, and an element's address never changes, so the `unapplied` table is gone with it.
  - `peel(layer)` accepts only the layer at the highest position. In one transaction it deletes that stack row, recomputes the current row of every thing the layer touched from the remaining stack, found through the `_by_layer` indexes, each thing's best remaining version one read on its `UNIQUE(id, layer_id)` index, so a join it moved goes back to where it was, and returns the layer to building, STORE-032, so it can be edited and finished again on top, or discarded. Its provenance record stays. It writes re-examination marks for what it undid, STORE-036. Peeling any other layer changes nothing and returns a notice naming the top layer and how to peel it, BASE-044.
  - The current tables always equal the intake map with the whole stack applied in order, with every knowledge and memory layer's own rows on top, unchanged by any correction; they are what every read uses.
  - `select`, `mask`, `clear`, `hide` and `unhide` on a correction layer change nothing and return a notice, and `--layers` never turns one on, CLI-033. A correction layer's rows are part of every read, in context and raw.
  - Things a correction removes keep their identity rows, STORE-007, and every row of their history.
  - Orphans: a row of a knowledge or memory layer, an item, a property or a join, whose target is no longer current after the stack is applied has nothing left to attach to and is orphaned. A target is an item's node, a property's element, a join's receiver or provider, or a subtype join's parent join or the element it holds. Items on a moved join are not orphaned, because they point at its identity id, which is still current. A knowledge or memory join orphaned because an end was removed shows again when that element is put back at the same address, D80; a join of the metaform that a correction removed stays removed until a correction adds a join. An orphan stays stored. It is absent from every read in context. A raw read returns it with `orphaned: true`. The check is made when a read joins through the current tables; nothing is rewritten when an item becomes orphaned or current again, so peeling the correction that orphaned it shows it again.
- Acceptance:
  - Two correction layers change the same join's purpose; after both are finished, reads show the second one's purpose, and `history` shows the intake's version, then the first, then the second.
  - Peeling the lower of two correction layers changes nothing and returns a notice; peeling the top one restores exactly the reads that held before it was finished, and it can be finished again.
  - `select`, `mask` and `hide` on a correction layer write nothing and return a notice.
  - After a correction layer removes a join, no read in context or raw returns it as current, and `history` still returns every version of it.
  - A correction layer moves an intake join that carries a knowledge layer's item to another receiver, and absorbs another intake join into a parent join. After `finish`, the moved join is read under its new receiver with the same id and the item, and the absorbed join is read among its parent's subtype joins and in no `joins` read; the knowledge layer's rows are unchanged. After `peel`, both joins are read where they were before.
  - A correction giving an element another address is written without it, with a notice naming `address`, and after `finish` the element is at its old address.
  - After a correction layer removes an element that a finished knowledge layer's item is attached to, the item is absent from `node` in context, `node` with `raw=True` returns it with `orphaned: true`, and the knowledge layer's rows are unchanged; peeling the correction shows the item in context again.
- Relates to: STORE-007, STORE-012, STORE-013, STORE-032, STORE-034, STORE-036, LAYER-011, MAP-015.
- Status: confirmed, 2026-09-25, for the model: correction layers are chronological and stacked, the only way to remove, move or permanently add something to the metaform, never toggled, and removed only by peeling from the top or covered by a layer on top. Confirmed also: correction layers sit underneath knowledge layers, never change a knowledge layer's things, and an item left with nothing to attach to is orphaned and not shown. Confirmed, 2026-09-27: an element cannot be moved and a join can, so no correction relocates an element; releasing a subtype join from its parent join is a correction; an approved blind-spot entry becomes a permanent record of the metaform, D89. Open: whether correction layers stay at all, D86. A raw read listing orphans marked as orphaned is recommended. The storage mechanics, the `op` column, applying on `finish`, and `peel` returning a layer to building, are recommended.
### STORE-018 Mutable layers change in place
- Requirement: Items in a mutable layer are updated and deleted in place, with no history kept.
- What this means: Memory is the main mutable layer. An agent adds an observation, changes it, or deletes it, and the store holds only the current state, the way the reference memory server does.
- Why: Memory is agents' working notes. Its value is being cheap to add and fix. One memory at a node fixes a small wrong inference right where agents read it, so the map does not have to be perfect to be useful. History and provenance would make every note heavy.
- How it shows: Updating a memory changes its value; there is no older version to read.
- Build: For a mutable layer's item, update writes the new `value` into the existing `items` row. Delete removes the `current_items` row, the `items` row and its refs in one transaction.
- Acceptance:
  - After ten updates to one memory, the item has one row.
  - After a delete, the item appears in no read.
- Relates to: STORE-017, STORE-020, LAYER-012, REQ-127 as corrected.
- Status: confirmed.

### STORE-019 Selection and mask are stored where the flow changes
- Requirement: Selection and mask are stored as rows at type addresses, and the effective selection at an address is computed from trunk to leaf as `effective = (incoming & mask) | select`.
- What this means: The project selects every layer by default. An address selects nothing of its own and masks nothing by default. A mask row at an address stops a layer flowing into that branch. A select row turns a layer on at that address and below. A read may supply its own root selection, such as a workflow's, and masks still apply. An element takes the effective selection at its address. A join takes its receiver's selection, D17, because the receiver owns the join. A subtype join takes the selection of its parent join's receiver, which owns the join it sits in, and the element it holds takes its own address's, like every element. Selection, masking and the transitive rules of properties are part of the data access object: every read applies them inside the engine, and no caller computes or bypasses them.
- Why: A write is needed only where the flow changes, so the stored data is just the places where it changes. The same selection applies on every path an agent reads through, so an excluded layer cannot leak in through a property or provider path.
- How it shows: With a mask for the C practices layer at `code.installer`, a read at `code.installer.bash` omits C practices, while a read at `code.engine` includes them.
- Build:
  ```sql
  CREATE TABLE selections(
    address  TEXT NOT NULL REFERENCES types(address),
    layer_id TEXT NOT NULL REFERENCES layers(layer_id),
    kind     TEXT NOT NULL CHECK(kind IN ('select','mask')),
    PRIMARY KEY(address, kind, layer_id)
  );
  CREATE INDEX selections_by_layer ON selections(layer_id);
  ```
  Resolution for an address: start from the starting selection: the read's own starting selection when it supplies one, else the layers toggled on by the folder's `--layers` setting, CLI-033, with each tag expanded through `layer_tags`, else every finished layer, STORE-035; for each prefix from the root segment to the full address, remove the layers masked there, then add the layers selected there; finally remove hidden layers and every layer that depends on a hidden layer, STORE-013. Each step is one primary-key range read on `selections`. A read that covers a subtree, such as `context` or `identity`, reads the selection rows of the address's prefixes and of the whole subtree once, the subtree as one primary-key range from `A.` up to but not including `A/`, and resolves every address beneath from those rows in memory, parent before child, so the selection costs a fixed number of reads however many addresses the answer spans. The resolved set is what every node read uses.
- Acceptance:
  - The mask example above gives the stated results.
  - A layer masked at an element's address does not appear in the node read for a join that element receives, nor in the provider read that reaches that element.
- Relates to: STORE-008, STORE-013, STORE-025, REQ-121, REQ-122, LAYER-006, LAYER-007.
- Status: confirmed for the rule, and for joins taking their receiver's selection, D17. Storing it as rows at type addresses, and resolving a subtree from one range read, are recommended.

## Memory

### STORE-020 Memory follows the reference memory server over the map's own nodes
- Requirement: Memory is a mutable layer whose entities are the map's nodes, whose observations are items, and whose relations are linked items, reached through the reference memory server's operations.
- What this means: The operations are those of LAYER-013: create entities, create relations, add observations, delete entities, delete observations, delete relations, read graph, search nodes and open nodes. An entity is an element or a join, a subtype join included, named by its address or its identity id, with its node kind as its type. Creating an entity for a name that is not a node of the map creates a new element at that address in the memory layer, D18. Each observation is one item in the memory layer attached to that node. Each relation is one item attached to the `from` node, linking to the `to` node, with the relation type as its value. Every node is already an entity of the memory layer without any row being written for it. Memories at the map's nodes are open to every agent to read, because they exist to share knowledge.
- Why: Agents already know the memory server's interface. Attaching memory to the map's own nodes means a single memory corrects a wrong inference where agents read it. The reference server keeps its whole graph in one file that it rewrites on every change; this store keeps each observation and relation as its own indexed row.
- How it shows: `memory open code.manager.route` returns the node with its observations and relations, including relations other nodes hold toward it.
- Build:
  - The default memory layer has the name `memory`, kind `memory`, module `memory`, and the variable `What agents have noted at this node.` It is mutable and hideable, with no provenance row. The first memory write operation in a project creates it, inside that operation's transaction. A layer is recognized as memory by its kind, never by its name.
  - Search runs over item values through an SQLite FTS5 table kept in step with `items` by triggers. It indexes every layer's items. A search returns only items of layers in the effective root selection that are ready and not hidden, unless the call names a layer, in which case it searches that layer alone:
    ```sql
    CREATE VIRTUAL TABLE item_text USING fts5(value, content='items', content_rowid='row');
    CREATE TRIGGER items_ai AFTER INSERT ON items BEGIN
      INSERT INTO item_text(rowid, value) VALUES (new.row, new.value);
    END;
    CREATE TRIGGER items_ad AFTER DELETE ON items BEGIN
      INSERT INTO item_text(item_text, rowid, value) VALUES ('delete', old.row, old.value);
    END;
    CREATE TRIGGER items_au AFTER UPDATE OF value ON items BEGIN
      INSERT INTO item_text(item_text, rowid, value) VALUES ('delete', old.row, old.value);
      INSERT INTO item_text(rowid, value) VALUES (new.row, new.value);
    END;
    ```
    Every `items` row is indexed, earlier versions included. `search` joins each match through `current_items` on the row, so only current versions are returned. The default `unicode61` tokenizer treats JSON quotes, braces and colons as separators, so a word inside a JSON value matches as a word. The search text is passed to `MATCH` as one quoted phrase per word, with any double quote in it doubled, so user text is never read as FTS5 query syntax.
  - Open nodes: the node's identity read plus two index reads, items at the node and items linking to it.
- Acceptance:
  - Adding an observation to a node that has no memories writes one item row and no other row.
  - A relation from A to B appears when opening A and when opening B.
  - Search finds an observation by a word in it, on Linux, macOS and Windows.
- Relates to: STORE-015, STORE-018, LAYER-012, LAYER-013, REQ-126 as corrected, MCP.
- Status: confirmed for the interface and for elements and joins as its nodes, per LAYER-013. An absorbed part is an element and its subtype join a join, Rich 2026-09-27, so both are memory nodes as elements and joins are, LAYER-003. No memory at a bare type address, D74. Memory creating a new element for a name not in the map, D18. FTS5 for search, and the default layer's fields, are recommended.

## Extension and module data

### STORE-021 Unknown fields survive
- Requirement: Fields a module adds to an element, join, subtype or item beyond the defined columns are kept in that row's `extra` value and survive reads, corrections, export and import.
- What this means: Modules may define additional join types and content without forcing every join into one closed schema. The defined columns hold what the engine uses. Anything else a writer supplies for that one row is kept alongside, unchanged.
- Why: A module's extension content must not be lost because the chassis does not know it, or modules could not extend the map.
- How it shows: A join written with a field `latency_budget` reads back with it, keeps it through a correction that does not touch it, and keeps it through export and import.
- Build: `extra` is a JSON object of the row's own additional fields. It is carried forward by a correction's `change` row unless that correction changes it.
- Acceptance: The round trip in How it shows holds byte for byte on the field's value.
- Relates to: STORE-004, STORE-027, REQ-017.
- Status: recommended.

### STORE-022 A module keeps its own data as a layer
- Requirement: Everything a module keeps is stored through the data access object as a layer, and no module writes files or databases of its own.
- What this means: A module that needs to remember something declares a layer and writes items to it. Such data is exported, imported and queried with everything else.
- Why: Data held outside the chassis cannot be exported, imported or queried as a whole, and cannot be selected alongside other layers. The current demo module writes its own `history.json` through `Context.data`, which this requirement replaces.
- How it shows: The hello module's greeting history appears as a layer in `list layers` and in an export.
- Build: `Context.data`, the per-module folder under the home, is removed from the common base. The hello module's history becomes items in a mutable layer it declares. Every template verb and handler that reads or writes that layer calls `ctx.require_store()`, so in a folder with no project it stops with `Next: metaform add project <id> <path>`. The template's event subscriber receives a Context built from the publisher's folder and project, BASE-028, and so writes to the same project's store. Its choices function receives a Context and returns no choices when the store is None, CLI-019.
- Acceptance: After exercising every hello verb, the home contains no file outside the base database and project stores.
- Relates to: STORE-023, STORE-024, BASE-005, BASE-019.
- Status: recommended. An item about no map node attaches to an element the module's layer creates for it, D22.

## The data access object

### STORE-023 The data access object is the only way to the data
- Requirement: The chassis provides one data access object, imported by every module from the common base, and it is the only code that opens a store or issues SQL.
- What this means: A module never touches SQLite, table names or files. It asks the data access object for things by address or identity id and gets objects back. The CLI and the MCP module use the same object, so every surface reads and writes identically.
- Why: A module built on the base cannot corrupt the map, cannot drift from the CLI or MCP, and keeps working when the storage underneath changes. Layers only compose if every module writes them the same way.
- How it shows: A module written from the template stores and reads its data with no import of `sqlite3`.
- Build: The public import is `from metaform.data import Store, Node, StoreError`. A verb receives the store for its context's project as `ctx.store`, BASE-028. When the folder resolves to no project, `ctx.store` is None, and `ctx.require_store()` raises `Stop('No project for this folder.', 'metaform add project <id> <path>')`. Every map, intake and memory verb calls `ctx.require_store()`. `Store(project_id)` for an id that is not registered raises `StoreError` with the next step `metaform list projects`. Chassis verbs that act on data, such as `export`, `import` and `query`, resolve the project the same way. Objects returned are frozen dataclasses: `Element`, `Join`, `Subtype`, `Item`, `Property`, `Layer`, `Provenance`, `Version`. A `Node` is `(kind, id)` where kind is `element` or `join`, a subtype join being a join, and id is an address or identity id; `type` names a bare type address for a write, STORE-008. `Subtype` is the record of a subtype join, STORE-011: its `join_id`, its `parent`, the `element_id`, `address`, `reading`, `short_name`, `name_length` and `role` of the element it holds, and its own fields.
  - Results: every object the data access object returns has `to_dict()`, giving plain JSON-ready data with identity ids, addresses and every field. The CLI's `--json` output and the MCP tool's JSON result are both that data, BASE-036.
- Acceptance:
  - No module under `src/metaform/modules` imports `sqlite3`.
  - The CLI verb run with `--json` and the MCP tool for the same read return equal JSON for the same arguments.
  - A map verb run in a folder with no project exits 2 with `Next: metaform add project <id> <path>`.
- Relates to: STORE-022, STORE-024, STORE-025, BASE-004, BASE-028, BASE-036, MCP-003.
- Status: confirmed. `ctx.store` as the attribute follows E9. `require_store`, `to_dict` and the no-project behavior are recommended.

### STORE-024 Write operations
- Requirement: The data access object offers exactly these write operations, each one transaction.
- What this means: These are the operations the intake, knowledge modules, critics and memory use to build and keep the map and its layers.
- Why: A small fixed set of writes, each matching a thing in the design, means every writer builds the same shapes and every shape has one way to be built.
- How it shows: The intake module records an intake one object per call, as the agent reasons it, with `layer`, `add_element`, `add_join`, `add_subtype`, `edit` and `remove`, and ends it with `finish`, BASE-039.
- Build:

  | Operation | Inputs | Output | Errors |
  |---|---|---|---|
  | `layer(name, module, variable, *, kind='layer', mutable, hideable, fields=(), tags=(), provenance=None, result_id=None, sources=(), ready=False)` | provenance is a mapping with module, workflow, prompt, model, role, blinded; sources are layer references, STORE-036 | `Layer`: created building, or ready when `ready=True`, STORE-032; the existing layer when the name exists with the same kind, module, variable, mutable and hideable | name exists with any of those different; empty variable; provenance missing for a layer whose kind is not memory |
  | `atomic()` | a context block | every write inside the block commits together when the block ends, or none does if it raises; a layer created in it with `ready=True` becomes visible, ready, at commit | nested `atomic()` joins the outer block |
  | `finish(layer)` | | `Layer` with `ready` set; a correction layer is applied on top of the stack, STORE-017 | layer unknown; already finished; a correction layer failing STORE-034 |
  | `edit(thing, changes)` | thing is an element, join, property or item written in a knowledge layer, or in an intake or correction layer still building, a subtype join being a join; `changes` per STORE-034, a join's `receiver`, `provider` and `parent` included, which move it, MAP-003 | the changed row, in place, with no new version | thing in a finished intake layer, a finished correction layer or memory; a key not allowed for the thing's kind; an element's `address`, which is its identity, MAP-015; a `parent` that is not a join held by a receiver, which cannot be read |
  | `remove(thing)` | thing is an element, join, property, item or ref written in a knowledge layer, or in an intake or correction layer still building, a subtype join being a join | nothing; the row and the refs and links attached to it are deleted, identity and `types` rows stay | thing in a finished intake layer, a finished correction layer or memory; the thing is still the receiver, provider or target of a current row in the layer |
  | `add_work(node, condition, *, note=None, task=None, held=False, reviewed=False)` | a `Node` naming an element or a join, a subtype join included, by address or id; the condition, note and task of MAP-046 | `WorkRecord`, open, attached to the object and to no layer, STORE-042 | a condition outside missing, broken and exclude, or a node that names no current object: stored as given with a notice; a missing condition: stored empty with a notice |
  | `edit_work(work_id, changes)` | changes among `condition`, `note`, `task`, `held`, `reviewed` | the `WorkRecord`, changed in place | a key that is not one of the five: named in a notice and not stored |
  | `finish_work(work_id, resolution=None)` | | the `WorkRecord`, done, with its resolution kept beside it | already done: the first resolution is kept and a notice says so |
  | `discard(layer)` | a knowledge layer, or a correction layer still building | a notice for each element kept because another layer holds something at it; the layer's content is deleted and its identity and type rows stay, STORE-032 | layer unknown; the intake layer; a correction layer on the stack; memory |
  | `add_element(layer, address, *, name_length=None, role=None, refs=(), extra=None)` | address in the form of STORE-008; name_length and role are written on the element's row in `layer`, and refs as rows owned by it, STORE-009 | `Element`; the existing current element, marked existing with `differs`, when the address is held, STORE-009 | layer unknown; layer locked and immutable; malformed address |
  | `add_join(layer, receiver, provider, *, purpose, function, relation, observation, name=None, non_goal=None, type='purpose', refs=(), extra=None)` | receiver and provider as address or element id, read as an id exactly when it matches the id form, STORE-007 | `Join` | receiver or provider is not an element; receiver equals provider, per D11 when confirmed |
  | `add_subtype(layer, join, address, *, purpose=None, function=None, ef=None, relation=None, verb=None, observation=None, non_goal=None, name=None, name_length=None, role=None, refs=(), extra=None)` | `join` is the parent join, held by a receiver; `address` names the element it holds, by address or id, written in `layer` with name_length and role when none is there, STORE-011; a subtype join carries its own purpose, MAP-030 | `Subtype`, the subtype join with the element it holds | a parent that is no join held by a receiver, which cannot be read; malformed address; a purpose given; an element there whose name_length or role differ from those given; an element another subtype join holds |
  | `add_ref(owner, key, value)` | owner is an element, join or item id, a subtype join's included | the ref, attached to the owner's current version | owner unknown; owner in the intake layer or a finished correction layer, STORE-012 |
  | `add_item(layer, target, value, *, link=None, refs=(), extra=None)` | target and link are `Node`s | `Item` | target or link unknown for identity kinds; `extra` not an object |
  | `add_property(layer, element, value, *, refs=(), extra=None)` | element as address or element id | `Property` | element unknown; a target that is not an element; `extra` not an object |
  | `answer(item_id, state, link=None)` | state A, B or C; link for C | challenge state | per STORE-040 |
  | `approve(item_id)` | a challenge answered B | challenge state and plans | per STORE-040 |
  | `add_plan(layer, element, join)` | a new function element and its join | plan | per STORE-040 |
  | `update_item(item, value)` | an item of a mutable layer | `Item` | layer is not memory; use `edit` for a knowledge layer |
  | `delete_item(item)` | an item of a mutable layer | nothing | layer is not memory; use `remove` for a knowledge layer |
  | `correct(layer, thing, changes=None, *, remove=False, reason, evidence=None)` | a building correction layer; thing is an element, join, property or item id of the metaform, a subtype join's included; `changes` per STORE-034, a join's `receiver`, `provider` and `parent` included, which move it | the `change` row, or the `remove` row when `remove=True`, written in the correction layer and applied only when it is finished, STORE-017 | layer not a building correction layer; a key not allowed for the thing's kind; an element's `address`, which is its identity, MAP-015 |
  | `peel(layer)` | the correction layer at the top of the stack | `Layer`, building again, STORE-017 | layer not a correction layer; layer not on top, naming the top layer |
  | `reexamined(layer)` | | nothing | layer unknown, STORE-036 |
  | `select(address, layer)`, `mask(address, layer)`, `clear(address, layer, kind)` | | nothing | layer unknown |
  | `hide(layer)`, `unhide(layer)` | | nothing | layer not hideable |

  The last column lists what does not fit each operation. Every one of them is a notice, BASE-044 and STORE-026: what does not fit is stored as given with a notice, and an operation aimed at something that cannot change writes nothing and returns a notice naming the operation that does it. Only a reference that names nothing, such as an unknown layer, id or join, or an unreadable argument, is a `StoreError`. `approve` keeps its check, since only a person runs it, LAYER-015.
- Acceptance: For each operation, one test performs it and checks the rows it must write and that no other table changed. Each listed condition returns its notice, and one aimed at something that cannot change writes nothing.
- Relates to: STORE-009 to STORE-022, STORE-026, STORE-031 to STORE-036, STORE-040.
- Status: confirmed for the set of things written, for knowledge layers written object by object through one tool with every call naming its layer, and for editing a knowledge layer after it is finished, 2026-09-25, and for the intake recorded one object per call, 2026-09-26. Operation names and signatures are recommended. No write takes a token or checks ownership; the intake layer is created building by `intake_start` and set ready by `intake_finish`, STORE-032.

### STORE-025 Read operations
- Requirement: The data access object offers exactly these reads, each answered through indexes.
- What this means: Each read is one question the design asks.
- Why: Agents navigate by meaning, and each question must go straight to its answer, STORE-005.
- How it shows: `metaform query element code.bus.event`, `metaform map element code.bus.event` and the tool `map_element` each call `element`, per STORE-028 and BASE-038.
- Build:

  | Operation | Answers | Index used |
  |---|---|---|
  | `element(ref)` | one element by address or id, with refs | `current_elements` address or primary key; `refs_by_owner` |
  | `joins(element, as_='receiver' or 'provider')` | the joins an element owns, or provides for | `current_joins_by_receiver`, `current_joins_by_provider` |
  | `identity(element)` | every current join where it is the provider, each as receiver, purpose and function | `current_joins_by_provider` |
  | `subtypes(join)` | the subtype joins in a join, each with the element it holds | `current_subtypes_by_parent` |
  | `where(address, full=False)` | one read of an address, the read an agent orients from, LAYER-017: the element, its address read through name_length and its role; `provides`, what relies on it, every current join where it is the provider, each with its receiver's address, the receiver's purpose, the join's function, ef, relation, verb, name and layer, and the subtype joins it holds; `receives`, what it relies on, every current join it receives, each with its provider's address, the join's function, ef, relation, verb, name and layer, and the subtype joins it holds; `held`, when a subtype join holds the element, that subtype join and the join it sits in, MAP-031, kind `subtype` when it is held only; `work`, its open work records with condition, note and task, STORE-042; and `layers`, what the layers in context hold at it, as `node` gives them. It follows the reading context like every read, LAYER-007. Its `to_dict()` leaves ids and empty fields out, so the read stays small; `full=True` keeps them; `properties`, the properties that apply at the address and those visible there, as `context` gives them, LAYER-005, each with its value, the address it is linked at and its layer, since an agent is told to read a part with this one read before it changes it, MCP-029, and a property linked toward the trunk reaches the part without being held at it, added 2026-09-28 | `current_elements`, `current_joins_by_provider`, `current_joins_by_receiver`, `current_subtypes_by_parent`, `current_subtypes_by_provider`, `work_by_target`, `current_items_by_target` |
  | `children(address)` | the next types up the tree, toward the leaves; the empty address gives the top types | `types_by_parent` |
  | `graph(after, limit)` | a page of the outer map in address order: each element in context that is not held only by subtype joins, MAP-031, with its nearest parent element of the outer map in context, and each join it receives with its subtype joins, for the viewer, VIEW-010 | `current_elements` by address, `current_joins_by_receiver`, `current_subtypes_by_parent`, `current_subtypes_by_provider` |
  | `peel_preview(layer)` | what removing a stacked correction layer would change, and whether it is the top one, VIEW-014 | `elements_by_layer`, `joins_by_layer`, `properties_by_layer`, `items_by_layer`, `current_items_by_target` |
  | `roots()` | the map's entry: the VE and DE elements with their joins, and every root element with its address, role and short name, paged; empty until the intake has finished. A root element has a role and is not held only by subtype joins, MAP-031 | `current_elements_by_role` for VE and DE, then `current_joins_by_receiver` for their joins; root elements, those with a role, by the `current_elements` primary key; `current_subtypes_by_provider` for `held_only` |
  | `layer_items(layer, target=None)` | all of a layer, paged in row order, or a layer at one node | `current_items_by_layer` on `(layer_id, row)`; `current_items_by_target` for one node |
  | `node(target, selection=None, raw=False)` | every layer's items at one node, grouped by layer. In context, the default, only layers in the effective selection that are finished and not hidden; with `raw=True`, every stored layer, building, hidden or masked included | `current_items_by_target`; `selections` primary key |
  | `context(address, selection=None)` | the applying and the visible properties at an address, as two lists, the visible list paged in address order, STORE-035 | `current_elements` address, one lookup per prefix and one range for the subtree; `current_properties_by_element`; `selections` primary key |
  | `links_to(target, layer=None)` | items in any layer linking to a node | `current_items_by_link` |
  | `citing(key, value)` | every current element, join and item whose refs hold that key and value, subtype joins included, per MAP-021 | `refs_by_key_value` |
  | `history(thing)` | every version of a thing: the row that added it, then each correction layer's row in stack order, each with its layer, position, op, reason and evidence | `UNIQUE(id, layer_id)`; `correction_stack` |
  | `stack()` | the correction layers in the order they were applied, each with its provenance | `correction_stack` primary key |
  | `layers(tag=None, kind=None, module=None)`, `provenance(layer)` | the layers with properties, kind, module, tags, whether each is building or ready, whether it is hidden, and whether it is toggled on for the current context, LAYER-019, filtered by tag, kind and module; one layer's provenance | full read of `layers`, STORE-005, or `layer_tags_by_tag` when filtering by tag; primary key |
  | `effective_selection(address, root=None)` | the resolved layer set at an address, and any unresolved selection rows, STORE-035 | `selections` primary key |
  | `search(text, layer=None)` | items whose value matches, per STORE-020 | `item_text` |
  | `has_intake()` | whether the active metaform holds a ready intake layer, STORE-032 | `layers_by_kind` |
  | `intake_recording()` | the intake being recorded in any of the project's metaforms, its metaform and its building layer, as a page of none or one, BASE-039 | `layers_by_kind` in each metaform's store |
  | `layer_graph(layer)` | one layer's own elements that are not held only by subtype joins, the joins it wrote with the subtype joins it wrote in them, building or finished; not a context read, BASE-039 and VIEW-005 | `elements_by_layer`, `current_joins_by_receiver`, `current_subtypes_by_parent`, `current_subtypes_by_provider` |
  | `metaforms(project)`, `active_metaform(project)` | the project's metaforms with their names and creation times, and which one is active, STORE-041 | `metaforms` `UNIQUE(project_id, name)`; `active_metaforms` primary key |
  | `project()` | the project record with its target, STORE-031 | `projects` primary key |

- Paging: every read in this table that returns a list takes `limit=500` and `after=None` and returns `(results, next)`, where `next` is the cursor for the following page or None, STORE-005. The cursor is the last row's key in the read's index order: the row for `layer_items`, the address for `context` and `children`, the identity id for `joins` and `identity`, the FTS rank position for `search`. `limit=0` returns the whole list.
- Joins from layers:
  - Every read that returns an element or a join, a subtype join included, also returns its `open_work`, the conditions of its open work records in row order, STORE-042, empty when it has none; one lookup on `work_by_target`.
  - Every read that returns a join, `joins`, `identity`, `node`, `context`, `links_to`, `where` for a subtype join, and the graph and export reads, returns with each join its `layer_id` and `layer`, the name of the layer it comes from, read from the join row's `layer_id` through the `layers` primary key. A subtype join is a join and carries its own layer.
  - The reads that return joins take `selection=None, raw=False` like `node`. In context, the default, a join is returned only when its layer is finished, not hidden, and in the effective selection at its receiver's address, LAYER-007, and when both its ends are current, STORE-017; a subtype join only when its parent join is returned, its own layer is in the effective selection at its parent's receiver's address, and the element it holds is current. The ends are read through `current_elements` by primary key. With `raw=True`, every stored join is returned, each with its layer name, and one with an end, a parent or an element that is not current is marked `orphaned`.
  - The intake map's joins go through the same filter, so masking the intake layer at an address removes its joins there like any other layer's.
- Acceptance:
  - STORE-005's plan test covers every row of this table.
  - Every join returned by every read in this table carries a non-empty `layer` equal to the name of the layer whose id its row holds.
  - A join added by a finished knowledge layer is returned by `joins(receiver)` in context when that layer is toggled on, is absent when it is toggled off or masked at the receiver's address, and is returned by `joins(receiver, raw=True)` in both cases.
- Relates to: STORE-005, STORE-012, STORE-019, MAP-001, MAP-021, LAYER-016, CLI, MCP.
- Status: confirmed for the questions answered, and for every join showing the layer it comes from. Names, signatures and the in-context filter of joins are recommended.

### STORE-026 Errors name one next step and never judge content
- Requirement: The data access object never refuses a write for its content; what does not fit is stored as given and noted, and only a call that cannot be read at all is an error, with one next step.
- What this means: Wording, purpose quality, typology, address form and shape mismatches never stop a write. A write that does not fit the pattern is stored as given, and the result carries a notice saying what did not fit and where it went. An operation aimed at something that cannot change in place, such as an intake layer's item, a finished correction layer's row or a correction layer's selection, writes nothing and returns a notice naming the operation that does it; the call still succeeds. Only a call that cannot be read at all, or an operation that would damage the store itself, such as a store whose schema version is newer than the code, is an error, and even then the error tells the agent once what to do and never invites a retry loop, BASE-044.
- Why: A check that rejects inference sends agents into retry loops. An agent-built check once turned a five-minute intake into 456 minutes and $750. The shape enforces itself, and nothing gates inference. An agent must never spend inference retrying, especially during testing.
- How it shows: `add_join` with an unknown provider stores the join, creates an element at the provider's address in the writing layer, and returns `Notice: code.probe.echo was not an element; it was created in layer <layer>.`
- Build: `StoreError(message, next_step)` subclasses the chassis `Stop` and is raised only for a call that cannot be read and for store-protecting failures: an unreadable argument, a store with a newer `schema_version`, STORE-029, a failed transaction. Every other condition is a `Notice(message, where)` added to the operation's result under `notices`, BASE-044. SQLite constraint errors inside the data access object are mapped to a stored-as-given write with a notice where the row can be stored, and to `StoreError` only where it cannot.
- Acceptance:
  - Each condition listed as a notice in STORE-024's table returns a result with that notice and no error, and the row is readable raw afterwards.
  - A join whose purpose is an empty string, or whose text is unrelated to its elements, stores with no notice.
  - A store with `schema_version` 999 raises `StoreError` and writes nothing.
- Relates to: STORE-024, STORE-029, BASE-044, CLI-009, MCP-006.
- Status: confirmed that submissions are never blocked; the notice mechanics are recommended.

### STORE-027 Export and import carry a project whole
- Requirement: `export` writes a project, or chosen layers of it, to one exchange document in which everything carries its unique id, and `import` adds to a store only what it does not already hold, keeping every identity id, every version of every thing, the order of the correction stack, every provenance record and every extension field.
- What this means: Documents are the exchange format only. The store is always the tables above. An intake is never loaded by importing its answer document; the agent builds the map through the write operations. Export and import move a project between homes and let a wheel carry data. Everything exported carries its unique id, so importing something that already exists does nothing: there is no conflict case. Work an agent does is never brought in by import; it is written through the write operations as a new layer, STORE-032. Backup and restore are separate from import and export and are not yet specified.
- Why: Identity and history must survive moving storage, or everything attached to the map breaks when it moves. Keeping documents out of the working store keeps the one-row-per-thing rules true everywhere.
- How it shows: A project exported from one machine and imported on another answers every read the same way.
- Build:
  - Commands: `metaform export [<project>|all] [file=<file>] [metaform=<name>] [layer=<name>]...` and `metaform import <file> [<project>]`. Every argument is a noun, BASE-043: `file` and `layer` are optional nouns written as `name=value`, because what to export is data the verb acts on, not a setting. The project, or the argument `all`, CLI-002, is the one positional noun of `export`, optional, and is read as the first word that contains no `=`; `import` likewise takes its file and then an optional project positionally. With no project, export takes the folder's project. `all` exports every registered project. With no file, export writes the document to standard output. `layer` may repeat and limits the export to those layers. Import with no project uses the project record in the document; with a project id, it imports into that registered project.
  - The document is JSON: `{"metaform_export": 1, "schema_version": N, "projects": [P, ...]}`. Each `P` is `{"project": {"project_id", "path", "target_type", "target_value"}, "metaforms": [M, ...], "active_metaform": <metaform id>}`, and each `M` is `{"metaform": {"metaform_id", "name", "created"}, "types": [...], "layers": [...], "layer_fields": [...], "layer_tags": [...], "layer_sources": [...], "provenance": [...], "selections": [...], "hidden": [...], "elements": [...], "joins": [...], "items": [...], "properties": [...], "refs": [...], "challenge_states": [...], "plans": [...], "work": [...], "requires": [...]}`. By default export carries every metaform of the project; `metaform=<name>` limits it to one.
  - Each list holds one object per row, including every version. A row object has one member per column of its table, named as the column, except the integer `row` and `owner_row` columns. `M` also holds `"correction_stack"`, the correction layer ids in stack order; import rebuilds `correction_stack` from it and recomputes the current tables. `hidden` is a list of layer ids. `requires` is a list of objects, `{"kind": "element"|"join"|"item", "id": <identity id>}` or `{"kind": "type", "address": <address>}`. Rows refer to each other by identity id and layer id, never by the store's `row` integers, which are not exported. A ref names its owner by kind, identity id and layer id. On import, new `row` values are assigned and every reference is remapped through identity id and layer id.
  - A layer-limited export carries that layer's rows and its provenance, plus `requires`: the identity ids and type addresses its rows point at that belong to other layers. Import of a document whose `requires` are not present in the target store imports what it can; rows pointing at a missing identity are stored orphaned, STORE-017, and each missing identity is named in a notice with the next step to import the project's map, BASE-044.
  - Importing a project into a home where it is not registered registers it from the document's project record. Importing into a registered project keeps that project's path and target.
  - Import runs in one transaction, STORE-006. It adds only what the target does not hold, by unique id, with no comparison of content: a metaform whose id exists is not created again, and when another project owns it, nothing of it is written and a notice names that project, BASE-044; a layer whose layer id exists in the target metaform's store is skipped whole, with every row it carries; a thing whose identity id exists is not added again. There is no conflict case. Correction layers the target does not hold are placed on top of its stack in the document's stack order. Import reports how many metaforms, layers and things it added and how many it skipped because they already existed: `import_document` returns `metaforms_added`, `metaforms_skipped`, `layers_added`, `layers_skipped`, `things_added`, `things_skipped` and `notices`, and `metaform import` prints one line per count in that order, the key with its underscore as a space and the count in words as PROJ-025 counts, then one `Notice: <where>: <message>` line per notice:
    ```
    metaforms added: one
    metaforms skipped: no
    layers added: two
    layers skipped: no
    things added: 14
    things skipped: no
    ```
    `import wheel=<name>-<version>`, BASE-042, prints the same lines from the report `pull_wheel` returns.
- Acceptance:
  - Export, import into an empty home, export again: the two documents are identical.
  - An import killed partway leaves the target store unchanged.
  - Importing a document whose layers already exist in the target, with any content, changes nothing and reports them skipped.
- Relates to: STORE-006, STORE-007, STORE-021, STORE-041, BASE-002, BASE-025.
- Status: confirmed for the requirement. JSON as the document format follows E7. Confirmed also: everything exported carries its unique id, importing what already exists does nothing, agent work comes in as a new layer, and backup and restore are separate. The command grammar, the document shape and the order in which imported correction layers are stacked are recommended.

### STORE-028 Query goes through the read operations
- Requirement: Every query surface, the CLI, MCP and modules, answers through the read operations of STORE-025, and there is no general SQL surface.
- What this means: The chassis runs 100 percent on its own and can query its data from the CLI. Those queries are the design's own questions, not free SQL.
- Why: Free SQL would tie every caller to the table layout and bypass selection and hiding, so an excluded layer could leak into what an agent reads.
- How it shows: `metaform query layer-items challenge.blind code.manager.route` returns the same items as the tool `map_layer` with the same arguments, with selection applied.
- Build: The chassis verb is `metaform query <read> [<argument>...] [--json]`, where `<read>` is the name of one read in STORE-025 written with hyphens, such as `element`, `joins`, `identity`, `layer-items`, `node`, `context`, `search`. Its arguments are that read's positional arguments in order, as nouns, and its named options are optional nouns written as `name=value`, BASE-043, such as `metaform query joins code.daemon as=receiver`; none of them is a switch or a setting. The only switch `query` takes is `--json`, a verb control, D32. A read's boolean option such as `raw` is a `bool` noun, `raw=true`, BASE-035, whether or not any module is on, so the chassis verb never reads a module's setting: `metaform query node element:code.daemon raw=true`. `metaform query` alone lists the reads. The map module's read verbs, BASE-038, call the same reads, so every read works on the CLI with no module enabled and over MCP through the map module. Each query read and each MCP read tool calls exactly one read operation.
- Acceptance: A layer masked at an address is absent from that address in every CLI and MCP read.
- Relates to: STORE-019, STORE-025, BASE-002, CLI, MCP.
- Status: recommended.

### STORE-029 The store records its schema version
- Requirement: The base database and every project store record their schema version in a `meta` table, and the chassis reads it before any other access.
- What this means: A chassis that finds a store at a version it does not know says so and names the next step rather than reading it wrongly.
- Why: Stores outlive the code that wrote them. A reader that silently misreads an older or newer layout corrupts what agents are told.
- How it shows: Opening a store written by a newer chassis gives an error naming the version found and the version supported.
- Build: `meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)` with `schema_version`. Each kind of database has its own version, so a change to one kind's layout never refuses another: the metaform store's layout is version 6, since a work record holds the steps an agent plans and those it has done, MAP-053; version 5 was step 52, which made a subtype join a row of `joins` and took out the relocation of elements; the base database, a project's history database and the prompt database are each version 1. Rich, 2026-09-27: schema changes start fresh; a changed layout bumps its own kind's version and no migration code is written. Before step 60 every kind shared one number, and the store's changes refused his whole home, the registry of projects and settings included, whose own layout had not changed.
- Acceptance:
  - A store with `schema_version` set to 999 is refused with a `StoreError`, and nothing is written to it.
  - A home whose base and history databases are at version 1 opens while the store's layout is at version 6, and its projects, settings and origins read back.
- Relates to: STORE-027, REQ-110, BASE-020.
- Status: recommended. Stores written by the current chassis branch, which keep joins as JSON bodies in `objects` and `joins` tables, are not migrated; pre-1.0 data is dropped, D24.

### STORE-030 A directly run wheel keeps its data in its own subfolder
Specified in BASE-023 and BASE-025: a directly run wheel keeps its data in `~/.metaform/wheels/<name>-<version>`, never the main data folder. After the wheel is installed, its data can be pulled into the main folder, where each of its metaforms arrives as its own metaform and nothing is merged, STORE-027.

## Records added by the cold build check

### STORE-031 Project records, ids and targets
- Requirement: A project is registered with an id, a folder and a target, under fixed rules for ids and duplicates.
- What this means: The id names the project in settings and in every command; the project's folder in the home is named by its source's path, PROJ-026, and its `project.sqlite3` holds the id. The folder is where the project's work happens and how a working folder finds its project. The target is the artifact the map describes, MAP-041.
- Why: The id becomes a folder name on three systems, so its form must be safe everywhere. Two projects claiming one id or one folder would send an agent's writes to the wrong map with no error.
- How it shows: `metaform add project notes ~/notes` registers `notes` with target type path and target value the resolved folder. `metaform add project photos ~/pics artifact kitchen_photos` registers a project whose target is the artifact named `kitchen_photos` in that folder.
- Build:
  - Grammar: `metaform add project <id> <path> [<target type> <target value>]`. The target type is one of path, url, artifact, inline or inferred. With no target given, the type is path and the value is the resolved folder. For type inferred, the value may be the word `inferred`.
  - An id matches `^[a-z0-9][a-z0-9_-]{0,63}$`. Uppercase is refused, not folded, so the id is the same on every system.
  - The path is resolved to an absolute path. A path that is not an existing folder is refused, next step `metaform add project <id> <existing folder>`.
  - An id already registered with the same path and target changes nothing and reports `Project <id> is already registered.` An id registered with a different path or target is refused, next step `metaform list projects`. A path already registered under another id is refused, naming that id, next step `metaform list projects`. The current chassis overwrites the path of an existing id; that changes.
  - `project()` returns the project record with id, path, target type and target value. Status shows the target, CLI-028.
- Acceptance:
  - `add project Notes <path>` is refused; `add project notes <path>` twice succeeds once and reports the second as already registered.
  - Registering a second id on a registered path is refused and names the first id.
  - The project record returned by `project()` holds the target type and value given.
- Relates to: STORE-002, STORE-003, MAP-041, CLI-001, CLI-028.
- Status: recommended. The target fields follow MAP-041, confirmed.

### STORE-032 Layer kinds, building and finishing
- Requirement: Every layer has a kind, intake, memory, correction or layer; a knowledge layer is building until its writer finishes it and stays editable through the knowledge-layer tool afterwards; the intake layer is building while it is recorded and, like a finished correction layer, never changes in place once finished; memory is never building.
- What this means: The kind tells the chassis which rules a layer follows without reading its name: memory has no provenance, an intake layer is what "has an intake" looks for, and a correction layer goes on the stack. Layers come to exist in these ways, LAYER-018:
  - The intake layer is created building by `intake_start` and recorded one object per call by the intake tools as the agent reasons it, BASE-039. While it is building, those tools add, edit and remove its objects in place, and no read in context shows it. `intake_finish` marks it ready; from then on it never changes in place, and the metaform changes only through correction layers, STORE-017.
  - A knowledge layer is created by the knowledge-layer tool, the only tool that makes a new layer, and written object by object: elements, joins, subtypes, properties, items and refs are added, edited and removed one at a time, in place, with no history. Every call names the layer. There is no token and no ownership: whoever has the tool can write to any knowledge layer, before or after it is finished. While a knowledge layer is building, no read in context shows it. When its writer's task is done, the writer finishes it; a finished knowledge layer is listed as ready, can be toggled on, selected, masked and hidden like any other layer, and remains editable through the tool. Its one provenance record describes how it was created.
  - A correction layer is made and written through the same tool. Finishing it applies it on top of the correction stack, STORE-017; after that its rows never change in place, and only peeling the top layer returns it to building. It is never toggled, selected, masked or hidden.
  - Memory is created ready on the first memory write and stays editable in place forever, STORE-018.
- Why: The model builds a knowledge layer incrementally against its prompt and fixes its own work as it goes, and a later agent, prompted to, improves it; both need to add, change and remove single objects. Access follows only from having the tool, so there is one rule for every agent and every host, and trusting an agent to name its layer needs no assignment machinery. Finishing marks when a layer is ready to be used, so a half-built layer never reaches an agent's context. The intake and the correction stack are what everything else attaches to, so they change only in the one recorded way. Keeping the intake building while it is recorded means no agent works from a half-recorded map: context reads and `has_intake()` see it only once it is finished.
- How it shows: While a knowledge layer is building, a read that names it shows every change; another agent reading the same element in context sees nothing of it. After `finish`, the layer appears in context reads when toggled on, and an agent with the tool can still edit it, with the change visible on the next read. During an intake run each object is stored as it is recorded, in the building intake layer; `metaform` status says an intake is being recorded, the web GUI draws it as it grows, and context reads see it only after `intake_finish`.
- Build:
  - `layers.kind` and `layers.ready`, STORE-013. `CREATE INDEX layers_by_kind ON layers(kind, ready);`
  - `layer(...)` creates a layer building: `ready` is NULL. `layer(..., ready=True)`, used by the memory module's first write, creates it ready.
  - The writes into a knowledge layer, `add_element`, `add_join`, `add_subtype`, `add_property`, `add_item`, `add_ref`, `edit`, `remove`, `finish` and `discard`, take the layer reference and nothing else to authorize them. For a finished intake layer and a finished correction layer they are not applied, and the result carries a notice naming the correction operation; the call itself succeeds, BASE-044.
  - `edit` changes a row written in the layer in place. `remove` deletes a row written in it, with its refs and links; when another current row in the same layer still uses it as receiver, provider, parent join, held element or target, the row is removed and those rows are orphaned, STORE-017, with a notice listing them. Identity rows, STORE-007, and `types` rows, STORE-008, are never deleted.
  - `finish(layer)` sets `ready` to the current time. For a knowledge layer nothing else changes: `edit` and `remove` still work. For a correction layer it also applies the layer on top of the stack, STORE-017, and from then on its rows never change in place.
  - `has_intake()` is true when a layer of kind intake exists with `ready` set. An intake layer is created building by `intake_start` and set ready by `intake_finish`. One indexed read.
  - `layer_graph(layer)` reads one layer's own elements, joins and subtypes, building or finished, STORE-025; the intake agent reads its building intake back through it, and the web GUI draws it live.
  - Node reads in context, `context`, `search` and the default toggled set include only ready layers. A read that names a building layer, or uses `raw=True`, sees it.
  - A building layer left by an interrupted run stays building and invisible until an agent with the tool finishes it, keeps writing to it, or removes it with `discard`. An intake left building is resumed by the next `intake_start`, BASE-039.
  - `discard(layer)` deletes, in one transaction, a knowledge layer's content: its items; the element, join, subtype and property rows written in it; the refs and links attached to those rows; its provenance row, its source rows, and its layer row. It does not delete identity rows or `types` rows, even those this layer created: STORE-007 keeps every identity id for as long as the store exists, so an id is never reused and a reference to it never points at something else. An identity id whose content was discarded has no current row, so reads by that id return not found and nothing in context shows it. Discarding the intake layer or a correction layer on the stack is refused.
- Acceptance:
  - While an intake is building, `has_intake()` is false, no read in context returns its elements, and `layer_graph` returns them.
  - A building layer's items are absent from another caller's node read in context and present in a read that names the layer; after `finish` they are present in context when the layer is toggled on.
  - After `finish`, `edit` on a knowledge layer's item changes the row in place and adds no version; `edit` on a finished intake layer's item writes nothing and returns a notice naming the correction operation; before the finish it changes the row in place.
  - An element the discarded layer made is kept when another layer holds a property, an item or a join at it. Its row passes to that layer, the first found by property, then item, then join, and the result carries a notice naming the element's address and the layer it now belongs to. Without this the other layer's content stays in the store attached to an element no read returns, so it is lost from every read and nothing says so. An element nothing else holds goes with its layer.
  - After `discard` of a building layer that wrote an element, the element's identity row and its `types` row remain, a read by its identity id returns not found, and `list layers` no longer lists the layer.
  - After `intake_finish`, `has_intake()` is true and the node read in context includes the layer.
- Relates to: STORE-013, STORE-012, STORE-017, STORE-018, STORE-024, MAP-040, LAYER-001, LAYER-018, MCP-009, BASE-038, BASE-039.
- Status: confirmed 2026-09-26 for the intake recorded one object per call while building and never changed in place after its finish; confirmed for knowledge layers written object by object through one tool that alone makes new layers, with every call naming its layer, no ownership, and editing after finishing. Finishing as marking a layer ready is confirmed. The `ready` column and the operation names are recommended.

### STORE-033 Every identity id resolves to its kind in one read
- Requirement: One table maps every identity id to its kind, so operations that take a bare id find the right table in one read.
- What this means: `correct`, `history`, `add_ref` and memory operations take an id without saying whether it is an element, join or item; a subtype join's id is a join id, STORE-011. The store looks up its kind first.
- Why: Asking the caller for the kind would push storage structure onto every agent, and guessing by trying each table is a scan in disguise.
- How it shows: `metaform map history <id>` works for any id.
- Build:
  ```sql
  CREATE TABLE identities(
    id   TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK(kind IN ('element','join','item'))
  );
  ```
  Every create operation inserts its identity row in the same transaction. The identity tables of STORE-007 stay as the foreign-key targets. Items gain `CREATE TABLE item_ids(item_id TEXT PRIMARY KEY, layer_id TEXT NOT NULL REFERENCES layers(layer_id));`, which `items.item_id` and `current_items.item_id` reference.
- Acceptance: For one id of each kind, `history(id)` returns that thing's versions, and its query plan uses the `identities` primary key.
- Relates to: STORE-007, STORE-017, STORE-024, STORE-025.
- Status: recommended.

### STORE-034 What a correction may change, and what removal does to what depends on the removed thing
- Requirement: A correction changes only the fields allowed for its kind, never an element's address, and a correction layer that removes a thing orphans everything current that still depends on it and names each in the result; nothing is refused.
- What this means: A correction is explicit about what it changes. An element's address is its identity and never changes, MAP-015. Moving a join is a correction that changes its receiver, its provider, or its parent, which places it inside a parent join as a subtype join, MAP-030, or releases it from its parent join to a receiver again; the join stays the same join, MAP-003. A node that still has current joins or subtype joins pointing at it does not silently disappear from under them: they are orphaned, STORE-017, and named, so one correction layer can remove a thing and what depends on it together, or leave the dependents to a later one, and either way the result says what was left hanging.
- Why: A correction format with no rules lets a correction orphan the joins of a removed element without a word, which breaks the structure that everything reads through; naming each orphan keeps the break visible, and refusing the removal would refuse a submission for its content, BASE-044. An element cannot be moved, since its address is its identity, MAP-015. A function's join can be moved, mostly while annealing, otherwise to fix a serious misinterpretation or to follow a change in the design's structure, because the join is where the map speaks about the artifact and what is known about it stays with it, MAP-003; releasing a subtype join is the same move made backward, as when a part turns out to hold a purpose of its own and so to need its own join, MAP-030.
- How it shows: `metaform map knowledge op=correct layer=<layer> id=<join id> receiver=code.probe.echo reason=...` inside a building correction layer moves the join to that receiver, with everything attached to it, when the layer is finished. The same call with `address=code.probe.echo` and an element's id writes nothing of the address and says that an element cannot be moved and its joins move instead. Finishing a correction layer that removes an element but not the join it still receives removes the element, orphans that join, and names it in a notice.
- Build:
  - `changes` is a mapping of field name to new value. Allowed fields: element `name_length`, `role`, `extra`; join `receiver`, `provider`, `parent`, `type`, `name`, `purpose`, `function`, `ef`, `relation`, `verb`, `observation`, `non_goal`, `extra`; item `value`, `link`, `extra`; property `element`, `value`, `extra`. An element's `address`, and any other key, is not applied and is named in a notice; `edit` takes the same fields, STORE-032. `refs` may be given as the complete new list of key and value pairs; when absent, the current refs are carried forward.
  - Moving a join. `receiver` gives a join held by a receiver another receiver, and `provider` gives it another provider, or gives a subtype join another element to hold. `parent` names the join held by a receiver that the join is to sit in: the join becomes a subtype join, of type `subtype`, with no receiver, and its purpose, when it has one, goes to its `extra`, MAP-030. When its receiver was not the parent's receiver, that receiver's address is kept in its `extra` under `receiver`, with a notice. Each other current join that still names the element it holds, as receiver, provider or held element, is named in a notice and left as it is. A subtype join it held passes to the new parent, named in a notice, MAP-032. `parent` on a subtype join moves it to another parent join. A `parent` that is a subtype join, that is an id of no join, or that is the join itself cannot be read, STORE-026, and nothing is written.
  - Releasing a subtype join. `parent` given empty, with a `receiver`, releases a subtype join from its parent join: it becomes a join of type `purpose` held by that receiver, with no parent, its purpose taken back from its `extra` when it was kept there and no `purpose` is given, and every other field and everything attached to it kept, MAP-003. `parent` given empty without a `receiver` is not applied and a notice names `receiver`, since a join held by no receiver is not a join of the outer map. `receiver` alone on a subtype join is not applied and is named in a notice: the join sits in its parent's join, and `parent` moves or releases it.
  - These checks run at `finish`, against the state after the whole correction layer is applied, so one correction layer can remove an element and its joins, or move several joins, together:
    - no current join has a removed element as receiver or provider;
    - no current subtype join sits in a removed join or holds a removed element;
    - no current property of the metaform is attached to a removed element.
    A join left with a removed element as receiver or provider, a subtype join in a removed join or holding a removed element, and a property on a removed element are orphaned, STORE-017, and named in the notice; the rest of the layer is applied.
  - The checks above apply to things of the metaform, the intake layer and correction layers. Items, properties and joins of knowledge and memory layers attached to a removed thing never block a finish; they are orphaned, STORE-017, and show again if the thing is put back at the same address.
- Acceptance:
  - A correction giving an element the key `address` is written without it and named in a notice, and after the finish the element is at its old address with its id.
  - A correction moving a join to another receiver is applied at the finish: the join keeps its id and its memory and is read under the new receiver; peeling the layer reads it under the old one again.
  - A correction with `parent` makes a join a subtype join of the parent at the finish, keeping its purpose as its own, and peeling the layer restores it under its receiver.
  - A correction with `parent` empty and a `receiver` releases a subtype join at the finish into a purpose join of that receiver, with its id, its memory and its purpose back from its `extra`; peeling the layer puts it back in its parent join.
  - A correction layer removes an element carrying a knowledge layer's property and locks; a later correction layer adds an element at the same address; the property shows again in context under the same element id, with no row of the knowledge layer changed.
  - Finishing a correction layer that removes an element with a current join removes the element and orphans the join, naming it in a notice; nothing is refused.
- Relates to: STORE-017, STORE-024, MAP-003, MAP-015, MAP-030, MAP-032, LAYER-011.
- Status: recommended. That removal orphans and a put-back element shows its attachments again is confirmed, LAYER-011. That an element cannot be moved and a join can, and that releasing an absorbed element's subtype join from its parent join is a correction, are confirmed, 2026-09-27; the fields that move and release a join are recommended. Whether a removed join shows again when its receiver and provider exist again at the same places is D80. Whether correction layers stay at all is open, D86.
### STORE-035 Context reads: the applying set, the visible set and the starting selection
- Requirement: The store answers, at any address, which properties apply there and which are visible there from above, toward the leaves, after selection, starting from the layers toggled on, LAYER-019.
- What this means: LAYER-005 needs two sets at an address: properties at the address and its prefixes that apply, and properties above it toward the leaves that are visible without applying. Only properties are transitive, D73; a property attached at an element counts as attached at that element's current address. Items, and anything attached at joins and subtypes, do not travel. The starting selection is the layers toggled on for the working context, LAYER-019; when the folder's `--layers` setting is unset, every finished layer that is not hidden starts selected.
- Why: A broad question at `code` must see every medium in use above it without spreading a branch's specifics to its siblings, and each answer must be one indexed read, STORE-005.
- How it shows: `metaform query context code` lists C++ from `code.engine` and Bash from `code.installer` as visible, and neither as applying.
- Build:
  - The starting selection comes from the folder's `--layers` setting, CLI-033, resolved to layer ids with tags expanded through `layer_tags`, STORE-038. No per-project starting selection is stored.
  - Applying set at A: for each prefix P of A, root first, the current properties, STORE-039, attached to the current element whose address is P, filtered by the effective selection at A. One unique-index lookup on `current_elements.address` per prefix.
  - Visible set at A: the current properties attached to any current element whose address starts with `A.`, each filtered by the effective selection at its own address. The descendant read is one range on the unique `current_elements.address` index from `A.` up to but not including `A/`, the next character after the period, joined to `current_properties_by_element`, in address order and paged, STORE-025. The selection for every address in the range is resolved from one range read of `selections`, STORE-019.
  - Unresolved selection: a select or mask row whose layer is hidden or still building is kept and returned by `effective_selection` in an `unresolved` list, and is not applied.
- Acceptance:
  - The C++ and Bash example gives the stated sets.
  - A property attached to the element `code.engine` applies at `code.engine.game`, and still does after a correction layer that tried to give the element the address `code.runtime` is finished, since an element cannot be moved, MAP-015.
  - The plans for both sets use `SEARCH` only.
- Relates to: STORE-005, STORE-019, STORE-025, LAYER-005, LAYER-007.
- Status: recommended. No stored per-project starting selection: the folder's `--layers` setting, falling back to every finished layer that is not hidden, is the only starting selection, D71.

### STORE-036 Re-examination marks
- Requirement: When a correction layer changes or removes a thing that another layer was built from, that layer is marked for re-examination until someone clears the mark.
- What this means: Dependents are re-examined, never rewritten, LAYER-011. The mark says which correction layer changed which thing. Clearing it is an explicit act.
- Why: A layer built on a corrected foundation must say so, or agents trust answers derived from something that no longer holds.
- How it shows: After a correction layer changes a join of the intake map, `metaform map layers` shows the challenge layer built from the intake with a re-examine mark.
- Build:
  ```sql
  CREATE TABLE layer_sources(
    layer_id        TEXT NOT NULL REFERENCES layers(layer_id),
    source_layer_id TEXT NOT NULL REFERENCES layers(layer_id),
    PRIMARY KEY(layer_id, source_layer_id)
  );
  CREATE INDEX layer_sources_by_source ON layer_sources(source_layer_id);
  CREATE TABLE reexamine(
    layer_id            TEXT NOT NULL REFERENCES layers(layer_id),
    correction_layer_id TEXT NOT NULL REFERENCES layers(layer_id),
    thing_id            TEXT NOT NULL,
    PRIMARY KEY(layer_id, correction_layer_id, thing_id)
  );
  ```
  `layer(...)` takes `sources`, the layer ids it was built from. Finishing a correction layer, and peeling one, insert a `reexamine` row for every layer whose sources include the layer that added a thing the correction layer changed or removed. `reexamined(layer)` deletes that layer's rows.
- Acceptance: Finishing a correction layer that changes a thing added by layer S marks every layer with S as a source, and no other layer; `reexamined` clears it.
- Relates to: LAYER-011, STORE-017, STORE-024.
- Status: recommended. It depends on D14, where a layer's sources are recorded.
### STORE-037 Each operation opens its own connection
- Requirement: Every data access operation opens its own SQLite connection, uses it for that one transaction, and closes it.
- What this means: Tool calls run in worker threads and several processes share one store. A connection is never shared between threads or kept between operations.
- Why: SQLite connections are not safe to share across threads by default, and a long-held connection holds locks that stall other writers.
- How it shows: Many concurrent tool calls on one store all complete.
- Build: `Store` holds the project id and path, not a connection. Each operation opens a connection with the pragmas of STORE-006, runs its transaction, and closes it in a `finally` block.
- Acceptance: STORE-006's concurrent write test passes with the writes issued from several threads of one process as well as from several processes.
- Relates to: STORE-006, BASE-028, MCP-002.
- Status: recommended.

### STORE-038 Layer tags
- Requirement: A layer's tags are stored one row per tag, indexed by tag, and can be changed at any time.
- What this means: Tags let layers be found and toggled by what they are for, LAYER-019. They are not layer content, so adding or removing a tag is allowed on a finished layer and needs no correction layer and does not touch provenance.
- Why: An orchestrator toggles layers by tag, so finding every layer with a tag must be one indexed read, STORE-005, and a tag must be changeable after a layer is finished without touching its content.
- How it shows: `metaform map tag practices-cpp practices` then `metaform map layers tag=practices` lists that layer.
- Build:
  ```sql
  CREATE TABLE layer_tags(
    layer_id TEXT NOT NULL REFERENCES layers(layer_id),
    tag      TEXT NOT NULL CHECK(length(tag) BETWEEN 1 AND 64),
    PRIMARY KEY(layer_id, tag)
  );
  CREATE INDEX layer_tags_by_tag ON layer_tags(tag, layer_id);
  ```
  - A tag is one to 64 characters of lowercase letters, digits, periods, underscores and hyphens.
  - `tag(layer, tag)` inserts a row and is a no-op when the row exists; `untag(layer, tag)` deletes it and is a no-op when it is absent. Both work on building and finished layers, and write no version rows.
  - The knowledge tool's `create` operation accepts an optional list of tags, written in the same transaction as the layer row.
  - Discarding a building layer deletes its `layer_tags` rows with its other content rows, STORE-032.
  - Resolving a `--layers` value: each name is looked up as a layer reference, STORE-013; a name that is not a layer is read as a tag and expands through `layer_tags_by_tag` to every layer carrying it. A name that is neither is an error naming it.
- Acceptance:
  1. Tagging a finished layer adds the tag, and the layer's rows and provenance row are unchanged.
  2. `EXPLAIN QUERY PLAN` for listing by tag shows `SEARCH layer_tags USING COVERING INDEX layer_tags_by_tag`.
- Relates to: STORE-005, STORE-013, STORE-025, STORE-032, STORE-035, LAYER-019, CLI-033, BASE-038.
- Status: recommended. Tags being editable after locking is recommended; that layers carry tags is confirmed.

### STORE-039 Properties are their own records

- Requirement: Each property is one row holding the element it is attached to, its value and the layer that owns it, and it has no join.
- What this means: A property is an encounter that describes what something is, MAP-022. It attaches only to an element, never to a bare type address or a join, a subtype join included, and travels along the namespace from that element's address by LAYER-005. When a property belongs at a namespace prefix where the project has no element, such as a practice for `code` in general, the layer creates an element at that prefix, as a layer may create a new element, and attaches the property to it. The namespace tree itself links that element to every element above it, so no join is needed, and its properties apply up to the leaves from there. That element is written with `add_element` in the same layer, STORE-024, and needs no join: it applies up toward the leaves and is visible down toward the trunk. It is never stored as a join and never inside an element row. A knowledge layer's property items are rows here; its function items are joins, STORE-010.
- Why: Properties flow along the namespace and functions stay with their receiver, so they need different records. One row per property keeps them directly readable by address and by layer.
- How it shows: `context code.installer.script` lists Bash, attached as a property to the element `code.installer`, as applying; `context code` lists it as visible.
- Build:
  ```sql
  CREATE TABLE properties(
    row         INTEGER PRIMARY KEY,
    property_id TEXT NOT NULL,
    layer_id    TEXT NOT NULL REFERENCES layers(layer_id),
    element_id  TEXT NOT NULL REFERENCES element_ids(element_id),
    value       TEXT NOT NULL,     -- JSON: the property's value
    extra       TEXT,
    op          TEXT NOT NULL DEFAULT 'add' CHECK(op IN ('add','change','remove')),  -- STORE-017
    reason      TEXT,
    evidence    TEXT,
    UNIQUE(property_id, layer_id)
  );
  CREATE TABLE current_properties(
    property_id TEXT PRIMARY KEY,
    row         INTEGER NOT NULL UNIQUE REFERENCES properties(row),
    layer_id    TEXT NOT NULL,
    element_id  TEXT NOT NULL
  );
  CREATE INDEX current_properties_by_element ON current_properties(element_id, layer_id);
  CREATE INDEX current_properties_by_layer   ON current_properties(layer_id, element_id);
  CREATE INDEX properties_by_layer           ON properties(layer_id);
  ```
  - Ids, versions, corrections, refs and `extra` follow the same rules as items, STORE-015 and STORE-021. A property in a knowledge layer is edited or removed in place at any time through the knowledge-layer tool, LAYER-018; a property of the metaform, the intake layer or a finished correction layer, changes only through a correction layer, STORE-017.
  - A property sent to a bare type address goes on an element the layer creates there. A property sent to a join is stored as given, orphaned, STORE-017, so it shows only in raw reads, with a notice; properties attach only to elements. The element's address, through `current_elements`, places the property in the namespace.
  - Written by `add_property`, STORE-024; read through `node`, `layer` and `context`, STORE-025 and STORE-035.
- Acceptance:
  - A property attached to the element `code.installer` applies at `code.installer.script`, is visible at `code`, and is absent at `code.engine`.
  - Adding a property never writes a row to `joins`. Adding one at a type address attaches it to a new element there; adding one at a join stores it orphaned; each returns a notice and nothing is refused.
- Relates to: MAP-022, LAYER-005, LAYER-016, STORE-008, STORE-010, STORE-015, STORE-024, STORE-035.
- Status: confirmed, 2026-09-25, that properties are their own transitive records attached only to elements, and, 2026-09-27, that a property's link to its element can be moved, STORE-034. Creating an element at a prefix to hold a property, linked by the namespace tree with no join, is recommended. The table shape is recommended. How a property is recorded, a value on an element, a link between two elements, or a join of its own kind, is open, D88.

### STORE-040 Challenge states and plans
- Requirement: The store keeps each blind-spot challenge's state, open, answered A, B or C, or plan, and every plan, outside the critic's blind-spot layer.
- What this means: A challenge is an item in a critic's blind-spot layer, LAYER-015. Its answer and its approval come later and from other actors, so they are recorded next to the item and never as edits to that layer. A plan is a new function element, with its join, that is either approved from a B challenge or added directly by an agent as a plan. A challenge with no state row is open.
- Why: The blind-spot layer is the critic's work and stays exactly as the critic left it, with its provenance. Keeping answers and approvals beside it lets every read show a challenge's state without changing the layer, and lets one read answer where a project's plans are.
- How it shows: `metaform map node element:<id>` on an element a challenge carries shows `challenge.blind` and `answered B`; after `metaform map approve`, it shows `plan`.
- Build:
  ```sql
  CREATE TABLE challenge_states(
    item_id    TEXT PRIMARY KEY,                     -- the challenge item, STORE-015
    state      TEXT NOT NULL CHECK(state IN ('A','B','C','plan')),
    link_kind  TEXT CHECK(link_kind IN ('element','join')),
    link_id    TEXT,                                 -- for C: the existing element or join
    answered   TEXT NOT NULL,                        -- UTC time of the answer
    approved   TEXT,                                 -- UTC time of approval, set when state becomes plan
    CHECK((state = 'C') = (link_id IS NOT NULL))
  );
  CREATE INDEX challenge_states_by_state ON challenge_states(state);
  CREATE TABLE plans(
    element_id TEXT PRIMARY KEY REFERENCES element_ids(element_id),
    join_id    TEXT REFERENCES join_ids(join_id),
    layer_id   TEXT NOT NULL REFERENCES layers(layer_id),
    source     TEXT NOT NULL CHECK(source IN ('direct','approved')),
    item_id    TEXT                                  -- the challenge, when source is approved
  );
  CREATE INDEX plans_by_layer ON plans(layer_id);
  ```
  - `answer(item_id, state, link)` writes or replaces the item's row with state A, B or C. An item that is not in a blind-spot layer, a state of plan, a C without a link, or an item already approved is stored as given with a notice, BASE-044; `approve` still acts only on a B, since a person runs it.
  - `approve(item_id)` requires state B, sets state to plan and the approval time, and writes a `plans` row with source approved for each new function element the challenge carries, with its join. An approved entry becomes a permanent record of the metaform, LAYER-015; what approval writes into the metaform, and how the user's veto of a green or a yellow answer is recorded, are open, D89, and until they are answered `approve` writes what this bullet states.
  - `add_plan(layer, element, join)` writes a `plans` row with source direct; it needs no approval.
  - Reads that return a challenge item, or an element or join listed in `plans`, add its state next to its layer name: open, A, B, C or plan.
- Acceptance:
  - A C answer without a link is stored with a notice. `approve` on a challenge that is open or answered A or C changes nothing and says why.
  - After `approve`, the blind-spot layer's item rows are unchanged, and reads show the challenge and its element as plan.
- Relates to: LAYER-015, LAYER-018, STORE-015, STORE-025, BASE-038, MAP-044, VIEW-020.
- Status: recommended. An approved entry becoming a permanent record of the metaform, and the user's final veto over green or yellow, are confirmed, 2026-09-27; what they write is open, D89.

### STORE-041 Metaforms and the active metaform
- Requirement: The project's own `project.sqlite3`, PROJ-026, records its metaforms and its one active metaform, each metaform has its own store, and every layer records the metaform it belongs to.
- What this means: A project can have more than one metaform, MAP-045. The base database lists them and records which one is active, so every surface finds the active one without opening any store. Each metaform's layers live in that metaform's store, STORE-003, and each layer row carries its metaform id so the layer names its container in exports and reads.
- Why: The active metaform decides what every agent reads for the project, so it must be one stored choice per project that every folder and every surface sees the same way. A separate store per metaform keeps an old metaform whole and untouched while a new one is built.
- How it shows: `metaform list metaforms` prints one line per metaform, `<name>  <created>`, with `(active)` after the active one. `metaform add metaform fresh` prints `Added metaform fresh to <project>; it is now active. The previous metaform main is kept. To switch back: metaform activate metaform main`. `metaform activate metaform main` prints `Active metaform for <project>: main`.
- Build:
  - The `metaforms` and `active_metaforms` tables, STORE-002. `layers.metaform_id`, STORE-013, equals the id of the metaform whose store holds the layer; the data access object writes it and refuses a layer whose metaform id differs from its store's.
  - The first write to a project that has no metaform creates one named `main`, with a new id, and makes it active, in one transaction on the base database, then creates its store, STORE-003.
  - `add_metaform(project, name)` creates a metaform with a new id and makes it active. The new metaform is empty: no intake layer, no correction stack, no layers. Its store is created on its first write. The name follows the layer name rules, STORE-013, and is unique in the project; a taken name is refused, next step `metaform list metaforms`.
  - `activate_metaform(project, name)` sets the active row. Nothing in any store changes.
  - `ctx.store`, BASE-028, is the store of the active metaform of the context's project. Every read and write goes to it. `has_intake()` answers for it, STORE-032.
  - A metaform is never deleted by these operations.
  - Chassis verbs: `metaform add metaform <name> [<project>]`, `metaform list metaforms [<project>]`, `metaform activate metaform <name> [<project>]`, CLI-031. The map module exposes the same operations as the tools `map_metaforms`, `map_add-metaform` and `map_activate`, BASE-038.
  - Status shows the active metaform, CLI-028.
- Acceptance:
  - After `add metaform fresh`, a read of an element from `main` returns not found, `has_intake()` is false, and `main`'s store file is byte-identical to before.
  - After `activate metaform main`, reads return what they returned before `fresh` was added.
  - Adding a second metaform with a name already in the project stores it under that name with `-2` added, or the next free number, and returns a notice.
- Relates to: STORE-002, STORE-003, STORE-013, STORE-027, STORE-032, MAP-045, CLI-028, CLI-031, BASE-028, BASE-038.
- Status: confirmed for more than one metaform per project, every layer attached to one metaform, one active metaform per project, and starting over with a new empty metaform while the old one is kept. The active metaform as a stored per-project choice, not a folder setting, and the tables, the store per metaform, the name `main`, making a new metaform active, and the verbs, are recommended.

### STORE-042 Work records are their own rows, apart from the map
- Requirement: The condition of an element or a join, a subtype join included, is a work record: its own row in `work`, attached to that one object, never a field of the object and never a layer. It is open until its task is done, and then it is kept with its resolution.
- What this means: The metaform is the intended shape of the project, and the intake layer holds only functional shape, never the condition of its objects. A work record holds the condition, MAP-046: `missing`, `broken` or `exclude`; a note saying what and where; a task saying what it needs; `held`, which keeps it waiting until agents are assigned or take it; and `reviewed`, set once it has been checked for correctness before it is fired off. Marking it done records the resolution beside it; nothing is erased. Any agent writes one at any time, after the intake has finished too; writing one never changes the map and is never a correction. A work record has no layer: it follows the object, so an element removed and recorded again at its address, STORE-009, keeps its records, and discarding a layer leaves them.
- Why: Agents must list what needs doing without scanning the map, the web GUI must show each node's condition, and the map must stay the intended shape while the work on it proceeds.
- How it shows: `metaform map work condition=missing` lists each open missing record with its object's address, or its join's ends, its note and its task. `metaform map node element:code.old.probe` shows `open_work: ["exclude"]`.
- Build:
  ```sql
  CREATE TABLE work(
    row         INTEGER PRIMARY KEY,
    work_id     TEXT NOT NULL UNIQUE,
    target_kind TEXT NOT NULL,
    target_id   TEXT NOT NULL,
    condition   TEXT NOT NULL,
    note        TEXT,
    task        TEXT,
    held        INTEGER NOT NULL DEFAULT 0,
    reviewed    INTEGER NOT NULL DEFAULT 0,
    created     TEXT NOT NULL,
    done        TEXT,
    resolution  TEXT
  );
  CREATE INDEX work_by_target    ON work(target_kind, target_id, row);
  CREATE INDEX work_by_condition ON work(condition, row);
  CREATE INDEX work_by_done      ON work(done, row);
  ```
  - `work_id` is an identity id in its form and its stability, STORE-007: a UUID4 as 32 lowercase hex characters, never changed and never deleted. Its identity row is the `work` row itself, which is unique on `work_id` and stays for as long as the store exists; a work record has no row in `element_ids`, `join_ids` or `identities`, because it is not a thing of the map and is never named by a bare id where the kind must be looked up, STORE-033. `created` and `done` are UTC timestamps; `done` null means open. `target_kind` is `element` or `join` and `target_id` the object's identity id, so the record stays with the object through every version.
  - Writes, STORE-024: `add_work(node, condition, *, note=None, task=None, held=False, reviewed=False)` writes one row for the node, given as a `Node` whose element may be an address, and returns the `WorkRecord`; `edit_work(work_id, changes)` replaces any of `condition`, `note`, `task`, `held` and `reviewed` in place; `finish_work(work_id, resolution=None)` sets `done` and the resolution. Nothing is refused for its content, BASE-044: a condition outside the three is stored as given with a notice naming `condition`; a missing condition is stored as empty text, since `condition` is never null, with a notice naming `condition`; a node that names no current object is stored as given, its kind and id as written, with a notice naming `node`; a note, task or resolution that is not text is stored as JSON text with a notice. Finishing a record already done keeps the first resolution and says so in a notice.
  - Read, STORE-025: `work(node=None, condition=None, open=None)` lists records in row order, paged, each with its object's address or its join's two ends when the object is current; `open=True` lists those not done, `open=False` those done. The map module serves it as `work`, BASE-038, and `metaform query work` reads it, STORE-028. `where` shows an element's open records, each with its condition, note and task, STORE-025.
  - Every read that returns an element or a join, a subtype join included, also returns `open_work`, the conditions of its open records in row order, empty when it has none; one lookup on `work_by_target`.
  - Export and import carry the table as `work`, STORE-027.
- Acceptance:
  - A `missing` record added to an element and a `broken` one to a join write exactly two rows; `work condition=broken` returns the join with its receiver and provider; the element reads back with `open_work` `["missing"]`.
  - `finish_work` with a resolution leaves the row, sets `done`, and the element's `open_work` is empty; `work open=false` returns it with the resolution.
  - The plans of `work condition=missing`, `work node=element:<id>` and `work open=true` use `work_by_condition`, `work_by_target` and `work_by_done`.
  - A condition `sideways` is stored as `sideways` and the call's notice names `condition`.
- Relates to: MAP-046, STORE-007, STORE-009, STORE-024, STORE-025, STORE-027, BASE-038, BASE-044, VIEW-005.
- Status: confirmed, 2026-09-27, for the condition apart from the map, `missing` replacing `missing`, the note and task, the held and reviewed flags, done with a resolution kept, and writable by any agent at any time and never a correction. Open, and built so until answered: its own table rather than a layer, D84, and `missing` as one condition whose task says build or decide, D85. The columns and operations are recommended.

### STORE-043 Reports are files with one row each
- Requirement: Each report, feedback or shape file has one row in the `reports` table of the project's active metaform store, and a row with a layer id is that layer's provenance ref.
- What this means: The files hold the text; the rows make them listable by kind and by layer without reading the folder, and tie them to provenance.
- Why: Reports must be reviewable and part of provenance, and listing them must go straight to the answer like every other read.
- How it shows: `metaform list reports` answers from the table in one indexed read.
- Build:
  ```sql
  CREATE TABLE reports(
    report_id TEXT PRIMARY KEY,      -- the file name
    run_id    TEXT NOT NULL,
    layer_id  TEXT REFERENCES layers(layer_id),
    kind      TEXT NOT NULL CHECK(kind IN ('report','feedback','shape')),
    created   TEXT NOT NULL,         -- UTC ISO 8601
    size      INTEGER NOT NULL
  );
  CREATE INDEX reports_by_layer ON reports(layer_id, kind);
  CREATE INDEX reports_by_time  ON reports(created, report_id);
  ```
  - Feedback with no project is listed from the home's `reports/` folder by reading its file names, since there is no store.
  - A file only grows, by appended sections, so its row's `size` never falls below a size already recorded: when several writers append at once, the row keeps the largest size any of them saw, which is the file's.
- Acceptance: A provenance read of an intake layer submitted with a report and feedback returns exactly those two refs.
- Relates to: BASE-045, STORE-016, STORE-001.
- Status: recommended.

### STORE-044 Prompts are versioned records, and provenance references the exact version
- Requirement: Prompts are stored as their own records with versions, one row per version; editing a prompt creates a new version, and a layer's provenance references the exact version it was created with.
- What this means: A prompt is a named record. Each saved text is a version with a number, a parent version and the time it was saved. The newest version is what future runs use. No version is ever edited or deleted, so the version a provenance record references always shows the exact text that produced the layer.
- Why: Prompts are modifiable, and the metaform improves by improving them. Provenance must stay a true record of how each layer was made, so an edit adds a version and never rewrites the one a layer came from.
- How it shows: `metaform prompts` lists prompts with their current version. `metaform prompt <name>` shows a version's text. Saving an edit in the viewer shows the next version number, and older layers still show their own version.
- Build:
  - Prompts live in one prompt store per Metaform home, `~/.metaform/prompts.sqlite3`, made on first use, Q50: a second intake starts a new metaform, BASE-039, so prompts kept per metaform would lose an edit at the next intake, and one prompt serves every project.
  ```sql
  CREATE TABLE prompts(
    prompt_id TEXT PRIMARY KEY,
    name      TEXT NOT NULL UNIQUE,
    format    TEXT NOT NULL CHECK(format IN ('xml','markdown','text')),
    created   TEXT NOT NULL
  );
  CREATE TABLE prompt_versions(
    version_id TEXT PRIMARY KEY,
    prompt_id  TEXT NOT NULL REFERENCES prompts(prompt_id),
    number     INTEGER NOT NULL,
    parent_id  TEXT REFERENCES prompt_versions(version_id),
    text       TEXT NOT NULL,
    origin     TEXT NOT NULL CHECK(origin IN ('shipped','edited')),
    created    TEXT NOT NULL,
    UNIQUE(prompt_id, number)
  );
  CREATE INDEX prompt_versions_by_prompt ON prompt_versions(prompt_id, number DESC);
  CREATE TABLE prompt_uses(
    project_id  TEXT NOT NULL,
    metaform_id TEXT NOT NULL,
    layer_id    TEXT NOT NULL,
    version_id  TEXT NOT NULL REFERENCES prompt_versions(version_id),
    PRIMARY KEY(project_id, metaform_id, layer_id)
  );
  CREATE INDEX prompt_uses_by_version ON prompt_uses(version_id);
  ```
  - `add_prompt(name, format, text)` creates the prompt and version 1. `add_prompt_version(prompt, text, parent)` creates the next number with the given parent; it never changes an existing row. Saving text identical to the parent returns the parent and a notice, BASE-044.
  - A module's shipped prompt becomes version 1, origin `shipped`, the first time it is served, and the newest version is what is served. When the shipped text later differs from every stored version and the newest version is itself shipped, so nobody has saved an edit since, the shipped text becomes the next version; after an edit, a changed shipped text adds nothing, so an edit is never overwritten.
  - The intake's Canonical Intake is not a stored prompt. It is served as shipped, BASE-039, never kept in the prompt store and never edited, so an intake layer links no version and its provenance keeps no copy of the text, STORE-016. Rich, 2026-09-26: the prompt used for intake is the same every time and is the one prompt that is never edited, so it is not kept.
  - Reads: `prompts()` lists prompts with their newest version, paged; `prompt_version(prompt, number)` returns one version; `prompt_versions(prompt)` lists versions, newest first; `layers_by_prompt_version(version)` lists the layers a version produced, from `prompt_uses_by_version`.
  - A layer created from a stored prompt records the version it used as its row in `prompt_uses`, keyed by its project, metaform and layer, and its provenance keeps the text as delivered, STORE-016. The link lives in the prompt store, since a store's row cannot reference a row in another file, and so no metaform's store changes.
  - These are chassis operations, reached through the data access object, served as the verbs `prompts` and `prompt` and the MCP tools of the same names, and written by the viewer, VIEW-013.
- Acceptance:
  - Saving an edit to a prompt at version 3 creates version 4 with parent 3; version 3's row is byte-for-byte unchanged.
  - A layer created from version 3 is linked to version 3 after version 4 exists, and `layers_by_prompt_version(3)` lists it.
  - Every read above is a SEARCH on the named index, STORE-005.
- Relates to: LAYER-010, STORE-005, STORE-016, BASE-044, VIEW-013.
- Status: confirmed for prompts as their own versioned records, editing creating a new version for future runs, and provenance referencing the exact version. The tables, operation names and verbs are recommended.

## Open questions

1. NEW Does a work record live in a layer, D84, and is `missing` one condition whose task says build or decide, D85? (STORE-042)
2. NEW Do correction layers stay at all, D86? (STORE-017, STORE-034, STORE-036)
3. NEW Is a property a value on an element, a link between two elements, or a join of its own kind, D88? (STORE-039)
4. NEW What does approving a blind-spot entry write into the metaform, and how is the user's veto recorded, D89? (STORE-040)

No other question remains in this section. Earlier questions were answered as follows: one element per address, D10; join roles, MAP-022; subtypes own no joins, sit in one join and hold no subtypes, D3, D4, D5; layer behavior declared by the module, D12; hiding follows dependencies, D13; declared variable fields, D21; provenance for a person or an import, D15; a second run is a new layer, D16; memory creates an element for a name not in the map, D18; an item about no map node attaches to an element its layer creates, D22; JSON exchange, E7; import does nothing for what exists, STORE-027; pre-1.0 data dropped, D24; wheel data, BASE-023 and BASE-025; the shared Type tree is the address itself, D47; no role on non-intake elements, D48; no attachment at a bare type address, D74; the C answer's link, STORE-040; `ctx.store`, E9; no stored starting selection, D71; correction and knowledge layers, STORE-017; a removed knowledge join shows again when its ends are put back, D80, while a removed join of the metaform stays removed until a correction adds one.
