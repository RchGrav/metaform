# 03 Storage and the data access object

This section defines where Metaform keeps its data, the exact tables that hold it, and the data access object every module imports from the chassis to read and write it.
It covers the base database, the per-project store, the correction stack, layers, provenance, memory, selection, import, export and query. The meaning of the map is in 01-map and the behavior of layers is in 02-layers; this section states how both are stored and reached.

## Terms used in this section

- **Node:** anything a layer item can attach to. The three kinds are an element, a join and a subtype. A type address is where a node sits in the namespace, not a node itself.
- **Identity id:** the stable id of an element, join, subtype or layer item. It never changes, whatever the thing's address or content becomes.
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
  - `metaform.sqlite3`: the base database, STORE-002.
  - `projects/<project id>/metaforms/<metaform id>/store.sqlite3`: one store per metaform, STORE-003 and STORE-041.
  - `projects/<project id>/reports/`: intake reports, process feedback and saved shapes, BASE-045; `reports/` under the home when no project is known.
  - `modules/`: the user place for modules, owned by the chassis loader, not by storage.
  - `skills/`: the installer's source copy of the skill, owned by the installer.
- Acceptance:
  - Run `add project`, a settings `set`, an element write and a memory write from inside a temporary project folder. The folder's file listing, including hidden files, is identical before and after.
  - With `METAFORM_HOME` set to a temporary folder, every file the run creates is under that folder.
- Relates to: STORE-002, STORE-003, STORE-030, CLI-014.
- Status: confirmed.

### STORE-002 The base database holds projects, folders, settings and module state
- Requirement: The base database `metaform.sqlite3` holds the registered projects, the working-folder table, settings with their glue, and module enable state.
- What this means: These are the records that exist before and apart from any project's map. A folder's context is its settings, and the base database is where the home knows every folder without writing into it.
- Why: Settings and folder context must work in folders that belong to no project, and they must survive deleting or re-running a project's store. Keeping them apart from project stores means a project store holds only that project's map and layers.
- How it shows: `metaform` run in any folder reports that folder's project and settings from the base database alone.
- Build:
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
  - A folder's project is its `project` setting when set, otherwise the registered project whose path contains the folder, the deepest match, compared through `path_key`.
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
- Requirement: Each metaform of a registered project has one SQLite store at `projects/<project id>/metaforms/<metaform id>/store.sqlite3` under the home, holding its whole map and every layer attached to it.
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
- Build: Every table in this section follows this rule. Elements have their own table and joins have their own table, one row per join. The only JSON-encoded columns are `settings.value`, which is one setting's value or one member of a list setting, `items.value` and `properties.value`, which are the value of that one item or property, and `extra` on elements, joins, subtypes, items and properties, which is the unknown fields of that one row, STORE-021. None of them may hold a collection: an item's value is one answer about one node, and a list of answers is written as that many items; an `extra` holding an array of records is split, each record stored as its own item, with a notice, BASE-044; a list setting is one row per member, STORE-002. Refs, tags, layer sources, layer fields, selections and the correction stack are each one row per member with an index, never a list in a row.
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
  - Measured at scale: a store built from this section's SQL with 105,000 element rows, 300,000 joins, 50,000 subtypes, 1,000,000 items, 50,000 properties, 300,000 refs, 20 layers, 300 selection rows and a correction stack of 10 layers, on SQLite 3.37 under WSL2, gave these medians:

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
    | `intake_submit`: 500 elements, 1,500 joins, 250 subtypes, 500 descriptor items, one transaction, median of three | | 467 ms |
    | `finish` of a correction layer: 500 element changes, 100 of them relocations with their join removals | | 105 ms |
    | `peel` of that layer | | 69 ms |
    | `discard` of a knowledge layer with 78,737 items | | 3.3 s |
- Acceptance:
  - For every read operation in STORE-025 and every write in STORE-024, `EXPLAIN QUERY PLAN` of each SQL statement it issues contains no `SCAN` of any table other than `layers`, `projects`, `hidden_layers`, `layer_sources`, `layer_tags` and `correction_stack`, and no `SCAN` of `item_text` other than `VIRTUAL TABLE INDEX`. Every other table it touches appears with `SEARCH` on an index or primary key. This test fails if a query or an index is changed so that a lookup on `elements`, `joins`, `subtypes`, `items`, `properties`, `refs`, `selections` or `types` falls back to a scan.
  - On a store loaded to the scale above, each read returning at most one page answers in a median of 5 ms or less, and each whole-list read in a median of 2 ms plus 15 µs per row returned or less. `intake_submit` of 500 elements commits within 1 s, median of three runs, `finish` of a correction layer with 500 changes within 500 ms, and `discard` takes at most 100 µs per row removed. At full scale, each read takes no more than three times as long per row returned as the same read at one-tenth of the scale, so cost follows the answer and not the store's size. Measured: a whole layer 1.5 µs per row at both scales; the trunk `context` 4.3 µs per row at one-tenth and 10.1 µs at full scale.
- Relates to: STORE-004, STORE-025.
- Status: confirmed. The paging arguments and the thresholds, set from the measurements above, are recommended.

### STORE-006 Writes are atomic and safe with many writers
- Requirement: Every write operation is one transaction, and many processes can write to the same store at once without losing or corrupting data.
- What this means: Each agent's MCP server is its own process, so several processes write to one project store at the same time. A write either lands completely or not at all. An interrupted import or correction leaves the store exactly as it was before it started.
- Why: A store that half-applies a write gives agents a map that is neither the old state nor the new one. Agents trust what they read, so partial state is worse than a failed write.
- How it shows: Two agents adding memories to the same node at the same moment both succeed. Killing a process in the middle of an import leaves the store as it was before the import.
- Build:
  - Every connection sets `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON` and `PRAGMA busy_timeout=5000`.
  - Each write operation opens `BEGIN IMMEDIATE`, performs all its statements and commits, or rolls back on any error. Each read operation opens a plain `BEGIN`, a deferred read transaction, so all its statements see one consistent state; in WAL mode readers never wait for the write lock and never block a writer.
  - Import, STORE-027, runs in one transaction.
- Acceptance:
  - Two processes each add 500 items to the same node concurrently. All 1000 items are present afterward.
  - An import killed partway leaves the item count and every current row unchanged.
- Relates to: STORE-027.
- Status: confirmed.

### STORE-007 Identity is a stable id that survives change
- Requirement: Every element, join, subtype and layer item has a stable identity id that never changes, whatever happens to its address, type or content.
- What this means: An element's address names its type. A later intake or correction can type the same element better, which changes its address but not its identity id. Everything attached to it, joins, subtypes, memory and other layer items, points at the identity id, so it follows the element rather than being orphaned. Identity ids also survive export, import, copying and moving a store.
- Why: The address says what kind of thing an element is. The element is this artifact's realization of it. Knowledge about the realization must stay with it when understanding of its type improves.
- How it shows: After an element is relocated from `code.daemon` to `code.manager.gateway.mesh`, its memories and challenges appear at the new address under the same identity id; its joins do not follow, STORE-017.
- Build: Identity ids, and layer ids, are random UUID4 values written as 32 lowercase hex characters without dashes, `uuid.uuid4().hex`, generated by the data access object. A 32-character lowercase hex string is never a valid address or layer name, STORE-008 and STORE-013, so every argument that takes an address or an id, or a layer name or a layer id, reads as an id exactly when it matches `^[0-9a-f]{32}$`. Identity tables hold one row per identity id for as long as the store exists:
  ```sql
  CREATE TABLE element_ids(element_id TEXT PRIMARY KEY);
  CREATE TABLE join_ids(
    join_id  TEXT PRIMARY KEY,
    receiver TEXT NOT NULL REFERENCES element_ids(element_id)
  );
  CREATE TABLE subtype_ids(
    subtype_id TEXT PRIMARY KEY,
    join_id    TEXT NOT NULL REFERENCES join_ids(join_id)
  );
  ```
  Foreign keys point at identity tables, never at version rows, so a correction or a removal never breaks a reference.
- Acceptance:
  - Relocate an element that has two memories and one join as receiver. The memories are found through the new address, the identity id is unchanged, and the join is no longer current.
  - Export a project and import it into an empty home. Every identity id is identical.
- Relates to: STORE-009, STORE-017, STORE-027, MAP-015.
- Status: confirmed.

## The map

### STORE-008 Type addresses are rows in a tree
- Requirement: Every namespace address used in a project is a row in the `types` table, linked to its parent address.
- What this means: The namespace is a tree of types. `code.engine.game.fps` is a type, and so are `code.engine.game`, `code.engine` and `code`, each a complete type in its own right. Writing any address writes the rows for it and for each of its prefixes that is missing. An address names the same Type in every project, so the Type tree is shared by construction: this table is each store's index of the addresses it uses, identical wherever the same address appears, and needs no shared table. Nothing attaches to a bare type address: items attach to elements, joins and subtypes, and a layer that needs a place at a prefix creates an element there, STORE-039. The store checks only an address's form, per MAP-010 and MAP-013: one or more segments separated by periods, each segment one or more lowercase letters, digits or underscores, and the whole address not a match for `^[0-9a-f]{32}$`, which is the id form of STORE-007. An address in that form is never refused for being functionally invalid.
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
- Requirement: Each element is stored as its identity id and its current address, and every version of it is kept. Everything else about an element is linked to it.
- What this means: An element is one functional part of the artifact, or an entity outside it, recorded at a type address. The element record is only that address with its identity: it holds no data of its own, and things are linked to it. The informal name, the `name_length` (the number of trailing address segments read backward to form its proper noun) and the role (AUE, VE, DE, SE or NE) that the intake gives for an element are stored as one descriptor item of the intake layer attached to the element, with any refs owned by that item. A knowledge layer that creates an element may attach its own descriptor item the same way.
- Why: Elements are real records that everything else points at. The intake names them by address, so the current address must be one direct lookup, while the identity id keeps attachments stable across retyping.
- How it shows: `element code.bus.event` returns that element's current row in one read.
- Build:
  ```sql
  CREATE TABLE elements(
    row         INTEGER PRIMARY KEY,
    element_id  TEXT NOT NULL REFERENCES element_ids(element_id),
    layer_id    TEXT NOT NULL REFERENCES layers(layer_id),
    address     TEXT NOT NULL REFERENCES types(address),
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
    moved      INTEGER NOT NULL DEFAULT 0           -- STORE-017: stack position of the last address change
  );
  CREATE INDEX elements_by_layer ON elements(layer_id);
  ```
  The current row carries the address so that address lookup of current elements is one unique-index read, and so that two current elements cannot hold the same address.
  - Descriptor: `add_element(layer, address, name=, name_length=, role=, refs=)` writes the element row and, when any of name, name_length, role or refs is given, one item of the same layer attached to the element with `value` `{"descriptor": {"name": ..., "name_length": ..., "role": ...}}` and the refs owned by that item, STORE-015. Reads of an element return its address and identity together with the current descriptor items attached to it, each with its layer name. A descriptor is changed by a correction layer as an item, STORE-017.
  - Roles are also indexed, so the map's entry is one direct read, `roots`, STORE-025:
    ```sql
    CREATE TABLE element_roles(
      element_id TEXT NOT NULL,
      layer_id   TEXT NOT NULL REFERENCES layers(layer_id),
      role       TEXT NOT NULL,
      PRIMARY KEY(element_id, layer_id)
    );
    CREATE INDEX element_roles_by_role  ON element_roles(layer_id, role);
    CREATE INDEX element_roles_by_layer ON element_roles(layer_id, element_id);
    ```
    One row is written with each descriptor item that carries a role, in the same transaction, and changed or removed with it.
  - `add_element` at an address a current element already holds returns that element, marked `existing: true`, writes no element row, and adds the descriptor item in the supplied layer only when that layer holds none for the element yet. The address, not the name, is the element's identity, so a repeated address is the same element.
  - A role is stored as given, or left out when none is given. The store does not refuse a missing role, STORE-026. The intake writes one role on every element it creates, MAP-017.
- Acceptance:
  - Looking up an element by address after two correction layers changed it returns the version from the higher one, through `current_elements`.
  - Adding a second element at an address that a current element already holds returns the existing element's id, marked existing, and writes no element row.
  - An intake element read back by address returns its name, name_length and role from its intake-layer descriptor item, and the `elements` row has no name, name_length or role column.
- Relates to: STORE-007, STORE-010, STORE-017, MAP-015, MAP-016, MAP-017.
- Status: confirmed: the element record holds only identity and address, and name, name_length, role and refs are linked to it as a descriptor item, D78. One current element per address in a project follows from an element being its address. An element created by a layer other than the intake carries no role, D48: roles are the intake's classification of the artifact.

### STORE-010 Joins are owned by their receiver and run one way
- Requirement: Each join is stored with its receiver, provider, purpose, function, relation, observation and non-goal as separate columns, owned by the receiver, and pointing from receiver to provider only.
- What this means: A join is one receiver's purpose served by one provider's encounter function. The receiver owns it. A relationship in the other direction is a different join with its own purpose. Both ends are elements. A join is never stored inside an element row and never as a list.
- Why: Each join is one receiver's why served by one provider's how, so its meaning stays single. Receiver, purpose and encounter are different kinds of node with links in one direction, so the receiver, purpose and encounter structure cannot hold a cycle. Keeping each part in its own column lets the store answer the design's own questions directly. The identity of an element X, its C(T), is every current join where X is the provider: who receives it, why, and how. That is one indexed read.
- How it shows: `identity code.failsafe.gateway.mesh` lists every receiver of the failsafe with that receiver's purpose and the failsafe's function for it, from one index.
- Build:
  ```sql
  CREATE TABLE joins(
    row         INTEGER PRIMARY KEY,
    join_id     TEXT NOT NULL REFERENCES join_ids(join_id),
    layer_id    TEXT NOT NULL REFERENCES layers(layer_id),
    type        TEXT NOT NULL DEFAULT 'purpose',
    receiver    TEXT NOT NULL REFERENCES element_ids(element_id),
    provider    TEXT NOT NULL REFERENCES element_ids(element_id),
    purpose     TEXT,
    function    TEXT,
    relation    TEXT,
    observation TEXT,
    non_goal    TEXT,
    extra       TEXT,                                -- STORE-021
    stack_at    INTEGER NOT NULL DEFAULT 0,          -- STORE-017: top stack position when written
    op          TEXT NOT NULL DEFAULT 'add' CHECK(op IN ('add','change','remove')),  -- STORE-017
    reason      TEXT,
    evidence    TEXT,
    UNIQUE(join_id, layer_id)
  );
  CREATE TABLE current_joins(
    join_id  TEXT PRIMARY KEY REFERENCES join_ids(join_id),
    row      INTEGER NOT NULL UNIQUE REFERENCES joins(row),
    receiver TEXT NOT NULL,
    provider TEXT NOT NULL
  );
  CREATE INDEX current_joins_by_receiver ON current_joins(receiver);
  CREATE INDEX current_joins_by_provider ON current_joins(provider);
  CREATE INDEX joins_by_layer ON joins(layer_id);
  ```
  - `join_ids.receiver` fixes the owner for the life of the join. A correction may change the provider or any text column, never the receiver.
  - Both ends reference `element_ids`. A subtype's id is in `subtype_ids`, so a subtype cannot be a join end.
  - Nothing checks for cycles among elements. Two elements may each receive from the other through two joins.
- Acceptance:
  - Two joins, A receives from B and B receives from A, both store and both read back.
  - Writing a join whose provider is a subtype id fails with the foreign key error mapped in STORE-026.
  - The identity read of an element with 50 provider joins among 100000 joins uses `current_joins_by_provider`.
- Relates to: STORE-009, STORE-011, STORE-025, MAP-001, MAP-002, MAP-003, MAP-020.
- Status: confirmed.

### STORE-011 Subtypes live inside one join
- Requirement: Each subtype is stored in its own table, tied to the one join it shares with its parent, with its own address and its own encounter function, and no purpose.
- What this means: Annealing combines parts that share the same join into a larger parent functionality. The join carries the purpose and the combined encounter, and each absorbed part stays as a subtype under it, keeping its own encounter function. A subtype never has a purpose of its own: a part with its own purpose does not share the join and is its own element, MAP-030. A subtype keeps its own address, name, relation and observation, and layers attach to it directly. It is reachable only through its join, is never a root element, and is never a join end.
- Why: Annealing keeps the root map minimal without discarding functionality. A subtype exists only because it shares that join with its parent, so it lives there. A separate table whose rows can only point at a join makes "excluded from the external graph" a property of the schema, so no query can pull a subtype into the element graph by forgetting a filter.
- How it shows: `subtypes <join>` lists the probes inside the failsafe's join, each with its own function. `where code.probe.echo` answers with the join it lives in, not as a root element.
- Build:
  ```sql
  CREATE TABLE subtypes(
    row         INTEGER PRIMARY KEY,
    subtype_id  TEXT NOT NULL REFERENCES subtype_ids(subtype_id),
    layer_id    TEXT NOT NULL REFERENCES layers(layer_id),
    address     TEXT NOT NULL REFERENCES types(address),
    name        TEXT,
    name_length INTEGER,
    role        TEXT CHECK(role IN ('DE','SE','NE')),
    function    TEXT,      -- its own encounter function; a subtype has no purpose, MAP-030
    relation    TEXT,
    observation TEXT,
    extra       TEXT,
    op          TEXT NOT NULL DEFAULT 'add' CHECK(op IN ('add','change','remove')),  -- STORE-017
    reason      TEXT,
    evidence    TEXT,
    UNIQUE(subtype_id, layer_id)
  );
  CREATE TABLE current_subtypes(
    subtype_id TEXT PRIMARY KEY REFERENCES subtype_ids(subtype_id),
    row        INTEGER NOT NULL UNIQUE REFERENCES subtypes(row),
    join_id    TEXT NOT NULL,
    address    TEXT NOT NULL
  );
  CREATE INDEX current_subtypes_by_join ON current_subtypes(join_id);
  CREATE INDEX current_subtypes_by_address ON current_subtypes(address);
  CREATE INDEX subtypes_by_layer ON subtypes(layer_id);
  ```
  - `subtype_ids.join_id` fixes the join. A subtype never moves to another join.
  - `subtypes_by_layer`, like `elements_by_layer` and `joins_by_layer`, finds a layer's rows for finishing, peeling, discarding and exporting without a scan, STORE-005.
  - A subtype whose address a current subtype or a current element already holds is stored as given, and the result carries a notice naming the other holder, BASE-044. The check is one read on `current_subtypes_by_address` and one on `current_elements`.
- Acceptance:
  - A subtype written in a join is returned by the subtypes read for that join, and by no element or join read.
  - Writing a subtype with a purpose stores the subtype with the purpose in its `extra`, and returns a notice.
  - No read that returns elements, or joins by receiver or provider, ever returns a subtype.
  - Writing an item attached to a subtype succeeds and is returned by the node read for that subtype.
- Relates to: STORE-010, STORE-015, MAP-030, MAP-031, MAP-032.
- Status: confirmed for placement and storage. A subtype owns no joins; its joins lift to the parent when it is annealed, D3. A part serving two joins is its own element, so a subtype lives in exactly one join and its address is held by no other subtype or element, D4. A subtype holds no subtypes, D5: `subtype_ids.join_id` references `join_ids`, so a subtype can only live in a join.

### STORE-012 Refs
- Requirement: Each ref is one key and value row attached to one version row of an element, join, subtype, property or layer item.
- What this means: Refs carry type-specific or artifact-specific references, such as `path` pointing at a member file. They belong to the version they were written with, so a reader of a version gets exactly the refs that version had.
- Why: Refs are part of what a version says. Tying them to the version row keeps an earlier version readable exactly as it was after a correction layer changes its refs.
- How it shows: After a correction layer drops a stale path ref from a join, the join's history still shows the path in the intake's version, and the current version does not.
- Build:
  ```sql
  CREATE TABLE refs(
    ref_id    INTEGER PRIMARY KEY,
    owner     TEXT NOT NULL CHECK(owner IN ('element','join','subtype','item','property')),
    owner_row INTEGER NOT NULL,   -- elements.row, joins.row, subtypes.row, items.row or properties.row
    position  INTEGER NOT NULL,   -- order as written
    key       TEXT NOT NULL,
    value     TEXT NOT NULL
  );
  CREATE INDEX refs_by_owner ON refs(owner, owner_row, position);
  CREATE INDEX refs_by_key_value ON refs(key, value);
  ```
  A `change` row in a correction layer copies forward the refs it keeps, as new rows pointing at the new version row.
  - Refs are written with their owner: the create operations of STORE-024 take a `refs` list of key and value pairs in order. `add_ref` adds one more ref to a thing's current version in a knowledge layer or a mutable layer at any time, STORE-032. A ref on a thing of the intake layer or of a finished correction layer changes only through a correction layer, STORE-017.
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
- Build: `layer_id` is a required column on `elements`, `joins`, `subtypes` and `items`. The intake writes through the same operations as every other layer.
- Acceptance: An element created by a second layer is absent from a node read whose selection excludes that layer and present when it is included.
- Relates to: STORE-013, STORE-015, STORE-018, LAYER-001.
- Status: confirmed.

### STORE-015 Layer items carry one variable at one node
- Requirement: Each layer item is one row holding one value of its layer's variable, attached to one node, with an optional link to another node.
- What this means: An item attaches to an element, a join or a subtype, never to a bare type address, D74. An item about no map node attaches to an element its own layer creates for it, D22. Its value is that layer's variable at that node, such as one best practice, one challenge or one memory observation. The optional link points at another node; a memory relation links one node to another. Links are items, so the whole structure stays navigable from any node, and links may form cycles.
- Why: One variable per layer is what lets any set of layers be selected together. Links as items mean an item points at the real node instead of copying it, and following links backward from the map shows everything that refers to a node.
- How it shows: Reading memory at `code.guard.switch.gateway` by incoming links lists every memory relation that points at it.
- Build:
  ```sql
  CREATE TABLE items(
    row         INTEGER PRIMARY KEY,
    item_id     TEXT NOT NULL,
    layer_id    TEXT NOT NULL REFERENCES layers(layer_id),
    target_kind TEXT NOT NULL CHECK(target_kind IN ('element','join','subtype')),
    target_id   TEXT NOT NULL,     -- an identity id
    value       TEXT NOT NULL,     -- JSON: this one item's value, never a list of things
    link_kind   TEXT CHECK(link_kind IN ('element','join','subtype')),
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
- Status: confirmed for attachment to elements, joins and subtypes, and for links. No attachment at a bare type address, D74. Declared variable fields, D21. One value per item, never a collection, is confirmed, STORE-004.

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
    prompt_version_id TEXT REFERENCES prompt_versions(version_id),
    model    TEXT,
    role     TEXT,
    blinded  INTEGER CHECK(blinded IN (0, 1))
  );
  ```
  - The row is written in the same transaction that creates the layer, from the provenance argument of the layer operation, STORE-024. Creating a layer other than memory without provenance writes a provenance row with every field empty except `module`, set to the calling module, and returns a notice, BASE-044.
  - `prompt` holds the prompt text the layer was produced from, as given. When the prompt came from a stored prompt, `prompt_version_id` names the exact version, STORE-044, and that version's text equals `prompt`. A version a provenance row references is never changed or deleted.
  - The layer's report, feedback and shape files are its provenance refs: the `reports` rows with this layer id, STORE-043. A provenance read returns them as refs `report`, `feedback` and `shape` with their file names. They are refs on the one record, not further provenance.
- Acceptance:
  - The store has no provenance table or column keyed by item, element, join or read.
  - Creating a layer with provenance and then writing 100 items leaves exactly one provenance row for that layer, with its fields unchanged.
  - A memory layer has no provenance row.
- Relates to: STORE-013, LAYER-010, REQ-101 to REQ-105 as corrected.
- Status: confirmed. A layer written by a person or a plain import has the same record, with `role` saying who or what wrote it, such as `person` or `import`, and `model` and `prompt` empty, D15. A second run of a workflow creates a new layer with its own record, D16.

### STORE-017 Correction layers are stacked in order and are the only way to change the metaform
- Requirement: The metaform changes only through correction layers, applied one on top of another in the order they were finished; they cannot be toggled, and only the top one can be peeled off.
- What this means: The metaform an agent reads is always the intake map with every correction layer applied in order. A correction layer is the only thing that can remove something from the metaform, relocate it, or add something to it permanently. Knowledge layers extend the metaform only while they are toggled on, and plans stay in their layers; only a correction layer changes the metaform itself. Correction layers are chronological: each is applied on top of the ones before it. They are never selected, masked, toggled or hidden. A correction layer in the middle of the stack cannot be deleted. To remove one, walk the stack backwards, peeling layers off the top one at a time, then rebuild the ones that were above it; or put another correction layer on top. Each correction layer carries its one provenance record like any layer. Anything built on a thing a correction changed or removed is re-examined, never rewritten, STORE-036.
- Why: The metaform is the shared foundation, so a change to it must be explicit, ordered and traceable. A stack applied in order gives one answer to what the metaform is at every moment, and each change keeps the provenance of the layer that made it. Toggling corrections would give different agents different foundations, and deleting one from the middle would silently change what every later correction was applied to; peeling from the top is the only removal that keeps every remaining layer applied to exactly what it was built against.
- How it shows: `metaform map stack` lists the correction layers in order. After a correction layer that retypes an element is finished, every read shows the new address; `metaform map history <id>` shows the element as the intake wrote it and as each correction layer left it. Peeling a layer that is not on top is refused, naming the top layer.
- Build:
  ```sql
  CREATE TABLE correction_stack(
    position INTEGER PRIMARY KEY,                       -- 1 is the first correction applied
    layer_id TEXT NOT NULL UNIQUE REFERENCES layers(layer_id)
  );
  ```
  - A correction layer is a layer of kind `correction`, immutable and not hideable, with its one provenance record, STORE-013 and STORE-016. It is written through the knowledge-layer tool like any layer, STORE-032: while building, its rows are written and edited freely, and nothing in it is applied.
  - Its rows are versions in the ordinary tables, `elements`, `joins`, `subtypes`, `properties` and `items`, with `layer_id` set to the correction layer and `op` saying what the row does:
    - `add`: a new thing with a new identity id, added to the metaform permanently.
    - `change`: a complete new version of an existing thing, under the same identity id. Fields not being changed are copied forward from the thing's current version, and so are its refs unless a complete new list is given, STORE-012. A subtype's address or end and a join's provider are changes. A join's receiver and a subtype's join never change, STORE-034; moving a join to another receiver, or a subtype to another join, is a removal and an add in the same correction layer.
    - Relocating an element, changing its address, is a `change` under the same identity id. Everything attached to the element, items, properties and memories of every layer, always follows it, because they point at its identity id, and at that point what is attached is most likely a property. An element is only a namespace address, so removing it does not drop what is attached: those things are orphaned, and they show again if an element is put back at the same address. Putting an element back at an address whose element was removed is an `add` row that reuses that removed element's identity id, so orphaned things reattach without being rewritten. An `add` at an address that has had more than one removed element reuses the most recently removed one. The element's joins never follow: a join is the face between one receiver and one provider, so relocating either end makes it disappear. Applying the relocation writes, into the same correction layer, a `remove` row for every current join of the metaform, the intake layer's and earlier correction layers', where the element is receiver or provider, and one for each subtype in those joins, so `history` and `peel` see exactly what the relocation removed. A join of a knowledge or memory layer at either end is not removed, because a correction never changes a knowledge layer's things: it is orphaned. `current_elements.moved` holds the stack position of the correction that last changed the element's address, and every join row holds `stack_at`, the top stack position when it was written; a knowledge or memory join is orphaned when either end's `moved` is greater than its `stack_at`. What was attached to a removed or orphaned join is no longer current. A join at the new place is a different join, added in the same correction layer with a new identity id. Element records are only a namespace address and hold no data of their own; things are linked to them, which is why an element's attachments follow it and a join's cannot.
    - `remove`: the thing is no longer in the metaform.
    Each `change` and `remove` row carries `reason` and, optionally, `evidence`. Rows with `op` `add` in the intake layer, knowledge layers and memory are the things those layers wrote.
  - A correction layer corrects the metaform: the intake layer's things and things added by earlier correction layers. It never changes a knowledge layer's things. Correction layers always beat knowledge layers: they sit underneath, and knowledge layers sit on top of the metaform the stack leaves, LAYER-011.
  - `finish` on a correction layer, in one transaction: checks the rules of STORE-034 against the state after the layer is applied; a row that breaks a rule stays in the layer unapplied and is listed in the result as a notice, and every other row is applied, BASE-044; inserts the layer at the next position on top of `correction_stack`; and applies it to the current tables, `current_elements`, `current_joins`, `current_subtypes`, `current_properties` and `current_items`: each `add` and `change` row becomes the thing's current row, and each `remove` deletes the thing's current row. It then writes re-examination marks, STORE-036. A row left unapplied is marked in `unapplied(layer_id, kind, thing_id, reason, PRIMARY KEY(layer_id, kind, thing_id))`, and recomputing the current tables skips it. A retype is left unapplied when another current element holds its address, or an earlier retype in the same layer took it. The `remove` rows applying a relocation writes carry the evidence `generated: relocation`.
  - `peel(layer)` accepts only the layer at the highest position. In one transaction it deletes that stack row, recomputes the current row of every thing the layer touched from the remaining stack, found through the `_by_layer` indexes, each thing's best remaining version one read on its `UNIQUE(id, layer_id)` index, and recomputes `moved` for every element it relocated, and returns the layer to building, STORE-032, so it can be edited and finished again on top, or discarded. Its provenance record stays. It writes re-examination marks for what it undid, STORE-036. Peeling any other layer changes nothing and returns a notice naming the top layer and how to peel it, BASE-044. Peel deletes the layer's `unapplied` marks and the `remove` rows its relocations wrote, so finishing it again derives both from its content as it is then.
  - The current tables always equal the intake map with the whole stack applied in order, with every knowledge and memory layer's own rows on top, unchanged by any correction; they are what every read uses.
  - `select`, `mask`, `clear`, `hide` and `unhide` on a correction layer change nothing and return a notice, and `--layers` never turns one on, CLI-033. A correction layer's rows are part of every read, in context and raw.
  - Things a correction removes keep their identity rows, STORE-007, and every row of their history.
  - Orphans: a row of a knowledge or memory layer, an item, a property or a join, whose target is no longer current after the stack is applied has nothing left to attach to and is orphaned. A target is an item's node, a property's element, or a join's receiver or provider. Items and properties on a relocated element are not orphaned, because they point at its identity id, which is still current. A join of the metaform where a relocated element was receiver or provider is removed by the relocation, and a knowledge or memory join there is orphaned, so items and subtypes on either are orphaned. A knowledge or memory join orphaned because an end was removed shows again when that element is put back at the same address, D80; a join of the metaform that a correction removed stays removed until a correction adds a join. An orphan stays stored. It is absent from every read in context. A raw read returns it with `orphaned: true`. The check is made when a read joins through the current tables; nothing is rewritten when an item becomes orphaned or current again, so peeling the correction that orphaned it shows it again.
- Acceptance:
  - Two correction layers change the same element's name; after both are finished, reads show the second one's name, and `history` shows the intake's version, then the first, then the second.
  - Peeling the lower of two correction layers changes nothing and returns a notice; peeling the top one restores exactly the reads that held before it was finished, and it can be finished again.
  - `select`, `mask` and `hide` on a correction layer write nothing and return a notice.
  - After a correction layer removes a join, no read in context or raw returns it as current, and `history` still returns every version of it.
  - A correction layer relocates an element that is the receiver of one intake join and one knowledge-layer join. After `finish`, the correction layer holds a `remove` row for the intake join, the knowledge join's row is unchanged and absent in context, and both are absent from `joins` in context. After `peel`, both joins are current again and the element is back at its old address.
  - After a correction layer removes an element that a finished knowledge layer's item is attached to, the item is absent from `node` in context, `node` with `raw=True` returns it with `orphaned: true`, and the knowledge layer's rows are unchanged; peeling the correction shows the item in context again.
- Relates to: STORE-007, STORE-012, STORE-013, STORE-032, STORE-034, STORE-036, LAYER-011, MAP-015.
- Status: confirmed for the model: correction layers are chronological and stacked, the only way to remove, relocate or permanently add something to the metaform, never toggled, and removed only by peeling from the top or covered by a layer on top. Confirmed also: correction layers sit underneath knowledge layers, never change a knowledge layer's things, and an item left with nothing to attach to is orphaned and not shown. A raw read listing orphans marked as orphaned is recommended. The storage mechanics, the `op` column, applying on `finish`, explicit `remove` rows for joins a relocation removes, the `moved` and `stack_at` check that orphans knowledge and memory joins, and `peel` returning a layer to building, are recommended.
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
- What this means: The project selects every layer by default. An address selects nothing of its own and masks nothing by default. A mask row at an address stops a layer flowing into that branch. A select row turns a layer on at that address and below. A read may supply its own root selection, such as a workflow's, and masks still apply. An element takes the effective selection at its address. A join takes its receiver's selection, D17, because the receiver owns the join. A subtype takes its own address's selection. Selection, masking and the transitive rules of properties are part of the data access object: every read applies them inside the engine, and no caller computes or bypasses them.
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
- What this means: The operations are those of LAYER-013: create entities, create relations, add observations, delete entities, delete observations, delete relations, read graph, search nodes and open nodes. An entity is an element, join or subtype, named by its address or its identity id, with its node kind as its type. Creating an entity for a name that is not a node of the map creates a new element at that address in the memory layer, D18. Each observation is one item in the memory layer attached to that node. Each relation is one item attached to the `from` node, linking to the `to` node, with the relation type as its value. Every node is already an entity of the memory layer without any row being written for it. Memories at the map's nodes are open to every agent to read, because they exist to share knowledge.
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
- Status: confirmed for the interface and for elements and joins as its nodes, per LAYER-013. Subtypes as memory nodes are recommended; they follow from LAYER-003, where every layer attaches at subtypes. No memory at a bare type address, D74. Memory creating a new element for a name not in the map, D18. FTS5 for search, and the default layer's fields, are recommended.

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
- How it shows: The helloworld module's greeting history appears as a layer in `list layers` and in an export.
- Build: `Context.data`, the per-module folder under the home, is removed from the common base. The helloworld module's history becomes items in a mutable layer it declares. Every template verb and handler that reads or writes that layer calls `ctx.require_store()`, so in a folder with no project it stops with `Next: metaform add project <id> <path>`. The template's event subscriber receives a Context built from the publisher's folder and project, BASE-028, and so writes to the same project's store. Its choices function receives a Context and returns no choices when the store is None, CLI-019.
- Acceptance: After exercising every helloworld verb, the home contains no file outside the base database and project stores.
- Relates to: STORE-023, STORE-024, BASE-005, BASE-019.
- Status: recommended. An item about no map node attaches to an element the module's layer creates for it, D22.

## The data access object

### STORE-023 The data access object is the only way to the data
- Requirement: The chassis provides one data access object, imported by every module from the common base, and it is the only code that opens a store or issues SQL.
- What this means: A module never touches SQLite, table names or files. It asks the data access object for things by address or identity id and gets objects back. The CLI and the MCP module use the same object, so every surface reads and writes identically.
- Why: A module built on the base cannot corrupt the map, cannot drift from the CLI or MCP, and keeps working when the storage underneath changes. Layers only compose if every module writes them the same way.
- How it shows: A module written from the template stores and reads its data with no import of `sqlite3`.
- Build: The public import is `from metaform.data import Store, Node, StoreError`. A verb receives the store for its context's project as `ctx.store`, BASE-028. When the folder resolves to no project, `ctx.store` is None, and `ctx.require_store()` raises `Stop('No project for this folder.', 'metaform add project <id> <path>')`. Every map, intake and memory verb calls `ctx.require_store()`. `Store(project_id)` for an id that is not registered raises `StoreError` with the next step `metaform list projects`. Chassis verbs that act on data, such as `export`, `import` and `query`, resolve the project the same way. Objects returned are frozen dataclasses: `Element`, `Join`, `Subtype`, `Item`, `Property`, `Layer`, `Provenance`, `Version`. A `Node` is `(kind, id)` where kind is `element`, `join` or `subtype` and id is an address or identity id.
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
- How it shows: The intake module stores a whole submitted intake with `layer`, `add_element`, `add_join`, `add_subtype` and `add_ref` inside one `atomic()` block, BASE-039.
- Build:

  | Operation | Inputs | Output | Errors |
  |---|---|---|---|
  | `layer(name, module, variable, *, kind='layer', mutable, hideable, fields=(), tags=(), provenance=None, result_id=None, sources=(), ready=False)` | provenance is a mapping with module, workflow, prompt, model, role, blinded; sources are layer references, STORE-036 | `Layer`: created building, or ready when `ready=True`, STORE-032; the existing layer when the name exists with the same kind, module, variable, mutable and hideable | name exists with any of those different; empty variable; provenance missing for a layer whose kind is not memory |
  | `atomic()` | a context block | every write inside the block commits together when the block ends, or none does if it raises; a layer created in it with `ready=True` becomes visible, ready, at commit | nested `atomic()` joins the outer block |
  | `finish(layer)` | | `Layer` with `ready` set; a correction layer is applied on top of the stack, STORE-017 | layer unknown; already finished; a correction layer failing STORE-034 |
  | `edit(thing, changes)` | thing is an element, join, subtype, property or item written in a knowledge layer, or in a correction layer still building; `changes` per STORE-034 | the changed row, in place, with no new version | thing in the intake layer, a finished correction layer or memory; a key not allowed for the thing's kind |
  | `remove(thing)` | thing is an element, join, subtype, property, item or ref written in a knowledge layer, or in a correction layer still building | nothing; the row and the refs and links attached to it are deleted, identity and `types` rows stay | thing in the intake layer, a finished correction layer or memory; the thing is still the receiver, provider or target of a current row in the layer |
  | `discard(layer)` | a knowledge layer, or a correction layer still building | nothing; the layer's content is deleted and its identity and type rows stay, STORE-032 | layer unknown; the intake layer; a correction layer on the stack; memory |
  | `add_element(layer, address, *, name=None, name_length=None, role=None, refs=(), extra=None)` | address in the form of STORE-008; name, name_length, role and refs are written as the element's descriptor item in `layer`, STORE-009 | `Element`; the existing current element, marked existing with `differs`, when the address is held, STORE-009 | layer unknown; layer locked and immutable; wrong token for a building layer; malformed address |
  | `add_join(layer, receiver, provider, *, purpose, function, relation, observation, non_goal=None, type='purpose', refs=(), extra=None)` | receiver and provider as address or element id, read as an id exactly when it matches the id form, STORE-007 | `Join` | receiver or provider is not an element; either is a subtype; receiver equals provider, per D11 when confirmed |
  | `add_subtype(layer, join, address, *, function=None, relation=None, observation=None, name=None, name_length=None, role=None, refs=(), extra=None)` | a subtype has no purpose, MAP-030 | `Subtype` | join unknown; malformed address; a purpose given |
  | `add_ref(owner, key, value)` | owner is an element, join, subtype or item id | the ref, attached to the owner's current version | owner unknown; owner in the intake layer or a finished correction layer, STORE-012 |
  | `add_item(layer, target, value, *, link=None, refs=(), extra=None)` | target and link are `Node`s | `Item` | target or link unknown for identity kinds; `extra` not an object |
  | `add_property(layer, element, value, *, refs=(), extra=None)` | element as address or element id | `Property` | element unknown; a target that is not an element; `extra` not an object |
  | `answer(item_id, state, link=None)` | state A, B or C; link for C | challenge state | per STORE-040 |
  | `approve(item_id)` | a challenge answered B | challenge state and plans | per STORE-040 |
  | `add_plan(layer, element, join)` | a new function element and its join | plan | per STORE-040 |
  | `update_item(item, value)` | an item of a mutable layer | `Item` | layer is not memory; use `edit` for a knowledge layer |
  | `delete_item(item)` | an item of a mutable layer | nothing | layer is not memory; use `remove` for a knowledge layer |
  | `correct(layer, thing, changes=None, *, remove=False, reason, evidence=None)` | a building correction layer; thing is an element, join, subtype, property or item id of the metaform; `changes` per STORE-034 | the `change` row, or the `remove` row when `remove=True`, written in the correction layer and applied only when it is finished, STORE-017 | layer not a building correction layer; a key not allowed for the thing's kind; receiver change requested |
  | `peel(layer)` | the correction layer at the top of the stack | `Layer`, building again, STORE-017 | layer not a correction layer; layer not on top, naming the top layer |
  | `reexamined(layer)` | | nothing | layer unknown, STORE-036 |
  | `select(address, layer)`, `mask(address, layer)`, `clear(address, layer, kind)` | | nothing | layer unknown |
  | `hide(layer)`, `unhide(layer)` | | nothing | layer not hideable |

  The last column lists what does not fit each operation. Every one of them is a notice, BASE-044 and STORE-026: what does not fit is stored as given with a notice, and an operation aimed at something that cannot change writes nothing and returns a notice naming the operation that does it. Only a reference that names nothing, such as an unknown layer, id or join, or an unreadable argument, is a `StoreError`. `approve` keeps its check, since only a person runs it, LAYER-015.
- Acceptance: For each operation, one test performs it and checks the rows it must write and that no other table changed. Each listed condition returns its notice, and one aimed at something that cannot change writes nothing.
- Relates to: STORE-009 to STORE-022, STORE-026, STORE-031 to STORE-036, STORE-040.
- Status: confirmed for the set of things written, for knowledge layers written object by object through one tool with every call naming its layer, and for editing a knowledge layer after it is finished. Operation names and signatures are recommended. No write takes a token or checks ownership; the intake's single `atomic()` write creates its layer ready.

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
  | `subtypes(join)` | the subtypes in a join | `current_subtypes_by_join` |
  | `where(address)` | the element, or the join holding a subtype, at an address | `current_elements`, `current_subtypes_by_address` |
  | `children(address)` | the next types up the tree, toward the leaves | `types_by_parent` |
  | `roots()` | the map's entry: the VE and DE elements with their joins, and every root element with its address and role, paged | `element_roles_by_role` for VE and DE in the intake layer, then `current_joins_by_receiver` for their joins; root elements by `element_roles_by_layer` in the intake layer |
  | `layer_items(layer, target=None)` | all of a layer, paged in row order, or a layer at one node | `current_items_by_layer` on `(layer_id, row)`; `current_items_by_target` for one node |
  | `node(target, selection=None, raw=False)` | every layer's items at one node, grouped by layer. In context, the default, only layers in the effective selection that are finished and not hidden; with `raw=True`, every stored layer, building, hidden or masked included | `current_items_by_target`; `selections` primary key |
  | `context(address, selection=None)` | the applying and the visible properties at an address, as two lists, the visible list paged in address order, STORE-035 | `current_elements` address, one lookup per prefix and one range for the subtree; `current_properties_by_element`; `selections` primary key |
  | `links_to(target, layer=None)` | items in any layer linking to a node | `current_items_by_link` |
  | `citing(key, value)` | every current element, join, subtype and item whose refs hold that key and value, per MAP-021 | `refs_by_key_value` |
  | `history(thing)` | every version of a thing: the row that added it, then each correction layer's row in stack order, each with its layer, position, op, reason and evidence | `UNIQUE(id, layer_id)`; `correction_stack` |
  | `stack()` | the correction layers in the order they were applied, each with its provenance | `correction_stack` primary key |
  | `layers(tag=None, kind=None, module=None)`, `provenance(layer)` | the layers with properties, kind, module, tags, whether each is building or ready, whether it is hidden, and whether it is toggled on for the current context, LAYER-019, filtered by tag, kind and module; one layer's provenance | full read of `layers`, STORE-005, or `layer_tags_by_tag` when filtering by tag; primary key |
  | `effective_selection(address, root=None)` | the resolved layer set at an address, and any unresolved selection rows, STORE-035 | `selections` primary key |
  | `search(text, layer=None)` | items whose value matches, per STORE-020 | `item_text` |
  | `has_intake()` | whether the active metaform holds a ready intake layer, STORE-032 | `layers_by_kind` |
  | `metaforms(project)`, `active_metaform(project)` | the project's metaforms with their names and creation times, and which one is active, STORE-041 | `metaforms` `UNIQUE(project_id, name)`; `active_metaforms` primary key |
  | `project()` | the project record with its target, STORE-031 | `projects` primary key |

- Paging: every read in this table that returns a list takes `limit=500` and `after=None` and returns `(results, next)`, where `next` is the cursor for the following page or None, STORE-005. The cursor is the last row's key in the read's index order: the row for `layer_items`, the address for `context` and `children`, the identity id for `joins` and `identity`, the FTS rank position for `search`. `limit=0` returns the whole list.
- Joins from layers:
  - Every read that returns an element, a join or a subtype also returns its `flag` and `flag_note` from `findings`, STORE-042, both null when it is working; one lookup on `findings_by_target`.
  - Every read that returns a join, `joins`, `identity`, `node`, `context`, `links_to`, `where` for a subtype, and the graph and export reads, returns with each join its `layer_id` and `layer`, the name of the layer it comes from, read from the join row's `layer_id` through the `layers` primary key. Subtypes carry the layer of the join that holds them.
  - The reads that return joins take `selection=None, raw=False` like `node`. In context, the default, a join is returned only when its layer is finished, not hidden, and in the effective selection at its receiver's address, LAYER-007, and, for a knowledge or memory join, when neither end's `moved` exceeds its `stack_at`, STORE-017. Both ends are read through `current_elements` by primary key in the same statement. With `raw=True`, every stored join is returned, each with its layer name.
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
  - The document is JSON: `{"metaform_export": 1, "schema_version": N, "projects": [P, ...]}`. Each `P` is `{"project": {"project_id", "path", "target_type", "target_value"}, "metaforms": [M, ...], "active_metaform": <metaform id>}`, and each `M` is `{"metaform": {"metaform_id", "name", "created"}, "types": [...], "layers": [...], "layer_fields": [...], "layer_tags": [...], "layer_sources": [...], "provenance": [...], "selections": [...], "hidden": [...], "elements": [...], "joins": [...], "subtypes": [...], "items": [...], "properties": [...], "refs": [...], "challenge_states": [...], "plans": [...], "element_roles": [...], "findings": [...], "unapplied": [...], "requires": [...]}`. By default export carries every metaform of the project; `metaform=<name>` limits it to one.
  - Each list holds one object per row, including every version. A row object has one member per column of its table, named as the column, except the integer `row` and `owner_row` columns. `M` also holds `"correction_stack"`, the correction layer ids in stack order; import rebuilds `correction_stack` from it and recomputes the current tables. `hidden` is a list of layer ids. `requires` is a list of objects, `{"kind": "element"|"join"|"subtype"|"item", "id": <identity id>}` or `{"kind": "type", "address": <address>}`. Rows refer to each other by identity id and layer id, never by the store's `row` integers, which are not exported. A ref names its owner by kind, identity id and layer id. On import, new `row` values are assigned and every reference is remapped through identity id and layer id.
  - A layer-limited export carries that layer's rows and its provenance, plus `requires`: the identity ids and type addresses its rows point at that belong to other layers. Import of a document whose `requires` are not present in the target store imports what it can; rows pointing at a missing identity are stored orphaned, STORE-017, and each missing identity is named in a notice with the next step to import the project's map, BASE-044.
  - Importing a project into a home where it is not registered registers it from the document's project record. Importing into a registered project keeps that project's path and target.
  - Import runs in one transaction, STORE-006. It adds only what the target does not hold, by unique id, with no comparison of content: a metaform whose id exists is not created again, and when another project owns it, nothing of it is written and a notice names that project, BASE-044; a layer whose layer id exists in the target metaform's store is skipped whole, with every row it carries; a thing whose identity id exists is not added again. There is no conflict case. Correction layers the target does not hold are placed on top of its stack in the document's stack order. Import reports how many metaforms, layers and things it added and how many it skipped because they already existed.
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
- Build: `meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)` with `schema_version`. This section's layout is version 1.
- Acceptance: A store with `schema_version` set to 999 is refused with a `StoreError`, and nothing is written to it.
- Relates to: STORE-027, REQ-110, BASE-020.
- Status: recommended. Stores written by the current chassis branch, which keep joins as JSON bodies in `objects` and `joins` tables, are not migrated; pre-1.0 data is dropped, D24.

### STORE-030 A directly run wheel keeps its data in its own subfolder
Specified in BASE-023 and BASE-025: a directly run wheel keeps its data in `~/.metaform/wheels/<name>-<version>`, never the main data folder. After the wheel is installed, its data can be pulled into the main folder, where each of its metaforms arrives as its own metaform and nothing is merged, STORE-027.

## Records added by the cold build check

### STORE-031 Project records, ids and targets
- Requirement: A project is registered with an id, a folder and a target, under fixed rules for ids and duplicates.
- What this means: The id names the project everywhere: in settings, in `projects/<id>/` under the home, and in every command. The folder is where the project's work happens and how a working folder finds its project. The target is the artifact the map describes, MAP-041.
- Why: The id becomes a folder name on three systems, so its form must be safe everywhere. Two projects claiming one id or one folder would send an agent's writes to the wrong map with no error.
- How it shows: `metaform add project mgm ~/mgm-main` registers `mgm` with target type path and target value the resolved folder. `metaform add project photos ~/pics artifact kitchen_photos` registers a project whose target is the artifact named `kitchen_photos` in that folder.
- Build:
  - Grammar: `metaform add project <id> <path> [<target type> <target value>]`. The target type is one of path, url, artifact, inline or inferred. With no target given, the type is path and the value is the resolved folder. For type inferred, the value may be the word `inferred`.
  - An id matches `^[a-z0-9][a-z0-9_-]{0,63}$`. Uppercase is refused, not folded, so the id is the same on every system.
  - The path is resolved to an absolute path. A path that is not an existing folder is refused, next step `metaform add project <id> <existing folder>`.
  - An id already registered with the same path and target changes nothing and reports `Project <id> is already registered.` An id registered with a different path or target is refused, next step `metaform list projects`. A path already registered under another id is refused, naming that id, next step `metaform list projects`. The current chassis overwrites the path of an existing id; that changes.
  - `project()` returns the project record with id, path, target type and target value. Status shows the target, CLI-028.
- Acceptance:
  - `add project Mgm <path>` is refused; `add project mgm <path>` twice succeeds once and reports the second as already registered.
  - Registering a second id on a registered path is refused and names the first id.
  - The project record returned by `project()` holds the target type and value given.
- Relates to: STORE-002, STORE-003, MAP-041, CLI-001, CLI-028.
- Status: recommended. The target fields follow MAP-041, confirmed.

### STORE-032 Layer kinds, building and finishing
- Requirement: Every layer has a kind, intake, memory, correction or layer; a knowledge layer is building until its writer finishes it and stays editable through the knowledge-layer tool afterwards; the intake layer and a finished correction layer never change in place; memory is never building.
- What this means: The kind tells the chassis which rules a layer follows without reading its name: memory has no provenance, an intake layer is what "has an intake" looks for, and a correction layer goes on the stack. Layers come to exist in these ways, LAYER-018:
  - The intake layer is written whole, in one atomic write by `intake_submit`, and is finished from the moment it exists, BASE-039. It never changes in place; the metaform changes only through correction layers, STORE-017.
  - A knowledge layer is created by the knowledge-layer tool, the only tool that makes a new layer, and written object by object: elements, joins, subtypes, properties, items and refs are added, edited and removed one at a time, in place, with no history. Every call names the layer. There is no token and no ownership: whoever has the tool can write to any knowledge layer, before or after it is finished. While a knowledge layer is building, no read in context shows it. When its writer's task is done, the writer finishes it; a finished knowledge layer is listed as ready, can be toggled on, selected, masked and hidden like any other layer, and remains editable through the tool. Its one provenance record describes how it was created.
  - A correction layer is made and written through the same tool. Finishing it applies it on top of the correction stack, STORE-017; after that its rows never change in place, and only peeling the top layer returns it to building. It is never toggled, selected, masked or hidden.
  - Memory is created ready on the first memory write and stays editable in place forever, STORE-018.
- Why: The model builds a knowledge layer incrementally against its prompt and fixes its own work as it goes, and a later agent, prompted to, improves it; both need to add, change and remove single objects. Access follows only from having the tool, so there is one rule for every agent and every host, and trusting an agent to name its layer needs no assignment machinery. Finishing marks when a layer is ready to be used, so a half-built layer never reaches an agent's context. The intake and the correction stack are what everything else attaches to, so they change only in the one recorded way. Writing the intake in one submission means a half-written intake never exists, so the no-intake notice clears only when a whole intake is stored.
- How it shows: While a knowledge layer is building, a read that names it shows every change; another agent reading the same element in context sees nothing of it. After `finish`, the layer appears in context reads when toggled on, and an agent with the tool can still edit it, with the change visible on the next read. During an intake run nothing is stored, so `metaform` status shows the no-intake notice until `intake_submit` succeeds.
- Build:
  - `layers.kind` and `layers.ready`, STORE-013. `CREATE INDEX layers_by_kind ON layers(kind, ready);`
  - `layer(...)` creates a layer building: `ready` is NULL. `layer(..., ready=True)`, used only inside `atomic()` by `intake_submit` and by the memory module's first write, creates it ready.
  - The writes into a knowledge layer, `add_element`, `add_join`, `add_subtype`, `add_property`, `add_item`, `add_ref`, `edit`, `remove`, `finish` and `discard`, take the layer reference and nothing else to authorize them. For the intake layer and a finished correction layer they are not applied, and the result carries a notice naming the correction operation; the call itself succeeds, BASE-044.
  - `edit` changes a row written in the layer in place. `remove` deletes a row written in it, with its refs and links; when another current row in the same layer still uses it as receiver, provider or target, the row is removed and those rows are orphaned, STORE-017, with a notice listing them. Identity rows, STORE-007, and `types` rows, STORE-008, are never deleted.
  - `finish(layer)` sets `ready` to the current time. For a knowledge layer nothing else changes: `edit` and `remove` still work. For a correction layer it also applies the layer on top of the stack, STORE-017, and from then on its rows never change in place.
  - `has_intake()` is true when a layer of kind intake exists with `ready` set. An intake layer is only ever created ready, inside `atomic()`. One indexed read.
  - Node reads in context, `context`, `search` and the default toggled set include only ready layers. A read that names a building layer, or uses `raw=True`, sees it.
  - A building layer left by an interrupted run stays building and invisible until an agent with the tool finishes it, keeps writing to it, or removes it with `discard`. The intake never leaves a building layer.
  - `discard(layer)` deletes, in one transaction, a knowledge layer's content: its items; the element, join, subtype and property rows written in it; the refs and links attached to those rows; its provenance row, its source rows, and its layer row. It does not delete identity rows or `types` rows, even those this layer created: STORE-007 keeps every identity id for as long as the store exists, so an id is never reused and a reference to it never points at something else. An identity id whose content was discarded has no current row, so reads by that id return not found and nothing in context shows it. Discarding the intake layer or a correction layer on the stack is refused.
- Acceptance:
  - An `intake_submit` whose `atomic()` block raises after writing elements leaves no layer, no elements, and `has_intake()` false.
  - A building layer's items are absent from another caller's node read in context and present in a read that names the layer; after `finish` they are present in context when the layer is toggled on.
  - After `finish`, `edit` on a knowledge layer's item changes the row in place and adds no version; `edit` on an intake layer's item writes nothing and returns a notice naming the correction operation.
  - After `discard` of a building layer that wrote an element, the element's identity row and its `types` row remain, a read by its identity id returns not found, and `list layers` no longer lists the layer.
  - After a successful `intake_submit`, `has_intake()` is true and the node read in context includes the layer.
- Relates to: STORE-013, STORE-012, STORE-017, STORE-018, STORE-024, MAP-040, LAYER-001, LAYER-018, MCP-009, BASE-038, BASE-039.
- Status: confirmed for the intake as one atomic write, for knowledge layers written object by object through one tool that alone makes new layers, with every call naming its layer, no ownership, and editing after finishing. Finishing as marking a layer ready is confirmed. The `ready` column and the operation names are recommended.

### STORE-033 Every identity id resolves to its kind in one read
- Requirement: One table maps every identity id to its kind, so operations that take a bare id find the right table in one read.
- What this means: `correct`, `history`, `add_ref` and memory operations take an id without saying whether it is an element, join, subtype or item. The store looks up its kind first.
- Why: Asking the caller for the kind would push storage structure onto every agent, and guessing by trying each table is a scan in disguise.
- How it shows: `metaform map history <id>` works for any id.
- Build:
  ```sql
  CREATE TABLE identities(
    id   TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK(kind IN ('element','join','subtype','item'))
  );
  ```
  Every create operation inserts its identity row in the same transaction. The identity tables of STORE-007 stay as the foreign-key targets. Items gain `CREATE TABLE item_ids(item_id TEXT PRIMARY KEY, layer_id TEXT NOT NULL REFERENCES layers(layer_id));`, which `items.item_id` and `current_items.item_id` reference.
- Acceptance: For one id of each kind, `history(id)` returns that thing's versions, and its query plan uses the `identities` primary key.
- Relates to: STORE-007, STORE-017, STORE-024, STORE-025.
- Status: recommended.

### STORE-034 What a correction may change, and what removal requires
- Requirement: A correction changes only the fields allowed for its kind, and a correction layer that removes a thing must also remove everything current that depends on it.
- What this means: A correction is explicit about what it changes. A retype is a correction that changes an element's address; a relocation is a correction that changes a subtype's address, or a join's provider. A node that still has current joins or subtypes pointing at it cannot silently disappear from under them.
- Why: A correction format with no rules lets a correction change a join's owner or orphan the joins of a removed element, which breaks the structure that everything reads through.
- How it shows: `metaform map correct <layer> <element id> address=code.probe.echo reason=...` inside a building correction layer relocates the element, with everything attached to it, when that layer is finished. Finishing a correction layer that removes an element but not the join it still receives removes the element, orphans that join, and names it in a notice.
- Build:
  - `changes` is a mapping of field name to new value. Allowed fields: element `address`, `extra` (an element's name, name_length and role are its descriptor item, corrected as an item); join `provider`, `type`, `purpose`, `function`, `relation`, `observation`, `non_goal`, `extra`; subtype `address`, `name`, `name_length`, `role`, `function`, `relation`, `observation`, `extra`; item `value`, `link`, `extra`; property `element`, `value`, `extra`. Any other key is stored as given in the correction row and not applied, with a notice. `refs` may be given as the complete new list of key and value pairs; when absent, the current refs are carried forward.
  - These checks run at `finish`, against the state after the whole correction layer is applied, so one correction layer can remove an element and its joins, or move several things, together:
    - an element's new address is not held by another current element, and its `types` rows are written;
    - every current join where a relocated element is receiver or provider is removed, with its subtypes, as part of applying the layer, STORE-017;
    - no current join has a removed element as receiver or provider;
    - no current subtype belongs to a removed join;
    - no current property of the metaform is attached to a removed element.
    A row that fails a check stays in the layer unapplied and is named in a notice; the rest of the layer is applied. A join left with a removed element as receiver or provider, a subtype of a removed join, and a property on a removed element are orphaned, STORE-017, and named in the notice.
  - The checks above apply to things of the metaform, the intake layer and correction layers. Items, properties and joins of knowledge and memory layers attached to a removed thing never block a finish; they are orphaned, STORE-017, and show again if the thing is put back at the same address.
- Acceptance:
  - A correction with the key `receiver` is stored unapplied and named in a notice.
  - A correction layer removes an element carrying a knowledge layer's property and locks; a later correction layer adds an element at the same address; the property shows again in context under the same element id, with no row of the knowledge layer changed.
  - Finishing a correction layer that retypes an element to an address held by another current element applies the rest of the layer, leaves that retype unapplied, and names it in a notice.
  - Finishing a correction layer that removes an element with a current join removes the element and orphans the join, naming it in a notice; nothing is refused.
- Relates to: STORE-017, STORE-024, MAP-015, LAYER-011.
- Status: recommended. That removal orphans and a put-back element shows its attachments again is confirmed, LAYER-011. Whether a removed join shows again when its receiver and provider exist again at the same places is open question 24.
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
  - A property attached to the element `code.engine` applies at `code.engine.game`, and after the element is relocated to `code.runtime` it applies at `code.runtime.game` and not at `code.engine.game`.
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
- What this means: A property is an encounter that describes what something is, MAP-022. It attaches only to an element, never to a bare type address, a join or a subtype, and travels along the namespace from that element's address by LAYER-005. When a property belongs at a namespace prefix where the project has no element, such as a practice for `code` in general, the layer creates an element at that prefix, as a layer may create a new element, and attaches the property to it. The namespace tree itself links that element to every element above it, so no join is needed, and its properties apply up to the leaves from there. That element is written with `add_element` in the same layer, STORE-024, and needs no join: it applies up toward the leaves and is visible down toward the trunk. It is never stored as a join and never inside an element row. A knowledge layer's property items are rows here; its function items are joins, STORE-010.
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
  - A property sent to a bare type address goes on an element the layer creates there. A property sent to a join or a subtype is stored as given, orphaned, STORE-017, so it shows only in raw reads, with a notice; properties attach only to elements. The element's address, through `current_elements`, places the property in the namespace.
  - Written by `add_property`, STORE-024; read through `node`, `layer` and `context`, STORE-025 and STORE-035.
- Acceptance:
  - A property attached to the element `code.installer` applies at `code.installer.script`, is visible at `code`, and is absent at `code.engine`.
  - Adding a property never writes a row to `joins`. Adding one at a type address attaches it to a new element there; adding one at a join or a subtype stores it orphaned; each returns a notice and nothing is refused.
- Relates to: MAP-022, LAYER-005, LAYER-016, STORE-008, STORE-010, STORE-015, STORE-024, STORE-035.
- Status: confirmed that properties are their own transitive records attached only to elements. Creating an element at a prefix to hold a property, linked by the namespace tree with no join, is recommended. The table shape is recommended.

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
  - `approve(item_id)` requires state B, sets state to plan and the approval time, and writes a `plans` row with source approved for each new function element the challenge carries, with its join.
  - `add_plan(layer, element, join)` writes a `plans` row with source direct; it needs no approval.
  - Reads that return a challenge item, or an element or join listed in `plans`, add its state next to its layer name: open, A, B, C or plan.
- Acceptance:
  - A C answer without a link is stored with a notice. `approve` on a challenge that is open or answered A or C changes nothing and says why.
  - After `approve`, the blind-spot layer's item rows are unchanged, and reads show the challenge and its element as plan.
- Relates to: LAYER-015, LAYER-018, STORE-015, STORE-025, BASE-038, MAP-044.
- Status: recommended.

### STORE-041 Metaforms and the active metaform
- Requirement: The base database records each project's metaforms and its one active metaform, each metaform has its own store, and every layer records the metaform it belongs to.
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

### STORE-042 Findings flags are one row per flagged object
- Requirement: Each element, join or subtype submitted with a finding flag has one row in `findings`, indexed by flag, and reads show the flag.
- What this means: Working is the default and has no row. A flag is missing, broken or cruft, MAP-046, with an optional note. The flagged object is stored in its layer like any other; the row records the finding about it.
- Why: Findings must be listed directly, for example every cruft object in a project, and shown wherever the object is read, without scanning the map.
- How it shows: `metaform map findings flag=cruft` lists each cruft object with its address, layer and note. `metaform map node element:code.old.probe` shows `flag: cruft`.
- Build:
  ```sql
  CREATE TABLE findings(
    row         INTEGER PRIMARY KEY,
    target_kind TEXT NOT NULL CHECK(target_kind IN ('element','join','subtype')),
    target_id   TEXT NOT NULL,
    layer_id    TEXT NOT NULL REFERENCES layers(layer_id),
    flag        TEXT NOT NULL CHECK(flag IN ('missing','broken','cruft')),
    note        TEXT,
    UNIQUE(target_kind, target_id, layer_id)
  );
  CREATE INDEX findings_by_flag   ON findings(flag, row);
  CREATE INDEX findings_by_target ON findings(target_kind, target_id);
  ```
  - Written by `intake_submit`, BASE-039, in the same `atomic()` block, from each element's, join's and subtype's `flag` and `flag_note`. A flag value outside the three is stored as `broken` with the given value kept in `note` and a notice, BASE-044.
  - `findings(flag=None, layer=None)` lists rows by flag, paged, STORE-025, joined to the object's address or join ends. The map module serves it as `findings`, BASE-038.
  - A knowledge layer may flag objects through the knowledge tool with the same fields; the row's layer id is that layer, so the flag is shown when that layer is toggled on.
- Acceptance:
  - A submission flagging one element `missing` and one join `broken` writes exactly two rows, and `findings flag=broken` returns the join with its receiver and provider.
  - The plan of `findings flag=cruft` uses `findings_by_flag`.
- Relates to: MAP-046, BASE-039, STORE-025.
- Status: confirmed that flags exist and are shown and listed; the table is recommended.

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
    created    TEXT NOT NULL,
    UNIQUE(prompt_id, number)
  );
  CREATE INDEX prompt_versions_by_prompt ON prompt_versions(prompt_id, number DESC);
  CREATE INDEX provenance_by_prompt_version ON provenance(prompt_version_id);
  ```
  - `add_prompt(name, format, text)` creates the prompt and version 1. `add_prompt_version(prompt, text, parent)` creates the next number with the given parent; it never changes an existing row. Saving text identical to the parent returns the parent and a notice, BASE-044.
  - Reads: `prompts()` lists prompts with their newest version, paged; `prompt_version(prompt, number)` returns one version; `prompt_versions(prompt)` lists versions, newest first; `layers_by_prompt_version(version)` lists the layers a version produced, from `provenance_by_prompt_version`.
  - A layer created from a stored prompt records the version it used in its provenance, STORE-016.
  - These are chassis operations, reached through the data access object, served as the verbs `prompts` and `prompt` and the MCP tools of the same names, and written by the viewer, VIEW-013.
- Acceptance:
  - Saving an edit to a prompt at version 3 creates version 4 with parent 3; version 3's row is byte-for-byte unchanged.
  - A layer created from version 3 has `prompt_version_id` naming version 3 after version 4 exists, and `layers_by_prompt_version(3)` lists it.
  - Every read above is a SEARCH on the named index, STORE-005.
- Relates to: LAYER-010, STORE-005, STORE-016, BASE-044, VIEW-013.
- Status: confirmed for prompts as their own versioned records, editing creating a new version for future runs, and provenance referencing the exact version. The tables, operation names and verbs are recommended.

## Open questions

None remain in this section. Earlier questions were answered as follows: one element per address, D10; join roles, MAP-022; subtypes own no joins, sit in one join and hold no subtypes, D3, D4, D5; layer behavior declared by the module, D12; hiding follows dependencies, D13; declared variable fields, D21; provenance for a person or an import, D15; a second run is a new layer, D16; memory creates an element for a name not in the map, D18; an item about no map node attaches to an element its layer creates, D22; JSON exchange, E7; import does nothing for what exists, STORE-027; pre-1.0 data dropped, D24; wheel data, BASE-023 and BASE-025; the shared Type tree is the address itself, D47; no role on non-intake elements, D48; no attachment at a bare type address, D74; the C answer's link, STORE-040; `ctx.store`, E9; no stored starting selection, D71; correction and knowledge layers, STORE-017; a removed knowledge join shows again when its ends are put back, D80, while a removed join of the metaform stays removed until a correction adds one.
