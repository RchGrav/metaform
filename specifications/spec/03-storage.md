# 03 Storage and the data access object

This section defines where Metaform keeps its data, the exact tables that hold it, and the data access object every module imports from the chassis to read and write it.
It covers the base database, the per-project store, revisions, layers, provenance, memory, selection, import, export and query. The meaning of the map is in 01-map and the behavior of layers is in 02-layers; this section states how both are stored and reached.

## Terms used in this section

- **Node:** anything a layer item can attach to. The four kinds are a type address, an element, a join and a subtype.
- **Identity id:** the stable id of an element, join, subtype or layer item. It never changes, whatever the thing's address or content becomes.
- **Row:** one stored revision of a thing. An immutable layer's thing can have several rows, one per revision. Exactly one of them is current.
- **Current pointer:** the row that readers get when they ask for a thing by its identity id.

## Data placement

### STORE-001 All data lives in the Metaform home
- Requirement: All Metaform data is stored under the Metaform home, and nothing is written into a project's folder.
- What this means: The home is `~/.metaform` on every system, resolved from the user's home directory, so on Windows it is `C:\Users\<user>\.metaform`. The environment variable `METAFORM_HOME` replaces it when set. Registering a project, running any command in a project folder, running an intake and writing memory all leave the project folder byte for byte unchanged. No marker file, cache or database is created there.
- Why: Every agent, in any folder or worktree, reaches the same data. A project never carries copies that go stale, get committed by accident, or get picked up by build tooling as if they were source.
- How it shows: After any sequence of commands in a project folder, `git status` in that folder shows nothing new. Deleting `~/.metaform` removes every trace of Metaform's data.
- Build: The chassis resolves the home once per process as `Path(os.environ.get('METAFORM_HOME') or Path.home() / '.metaform').expanduser()`. Every path the chassis writes is built from that value with `pathlib`, never with string joins or `/` literals. Layout under the home:
  - `metaform.sqlite3`: the base database, STORE-002.
  - `projects/<project id>/store.sqlite3`: one store per project, STORE-003.
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
    scope TEXT NOT NULL,               -- 'global' or a folders.path_key
    owner TEXT NOT NULL,               -- 'chassis' or the declaring module id, CLI-024
    key   TEXT NOT NULL,
    value TEXT NOT NULL,               -- JSON encoding of the one value
    PRIMARY KEY(scope, owner, key)
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
  CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);  -- holds schema_version
  ```
  - A folder row is written the first time a folder-scoped setting is stored for it. Reads never write.
  - A folder's project is its `project` setting when set, otherwise the registered project whose path contains the folder, the deepest match, compared through `path_key`.
  - A stored setting is keyed by scope, owner and key, so a module can never read or overwrite another owner's stored value by declaring the same key, CLI-024. The current chassis keys settings by scope and key only; that changes.
  - `module_state` has a row only when a user has enabled or disabled a module. With no row, the module's own declaration decides, so a module that ships disabled stays disabled until enabled, the same three-case pattern as settings.
- Acceptance:
  - A read-only command against a home with no base database creates no file.
  - A project registered as `C:\Work\Proj` is found from the folder `c:\work\proj\src` on Windows, and not from a different case on Linux.
  - A module declared as shipping disabled is off with no `module_state` row, on after `enable`, and back to its declared state after its row is removed.
- Relates to: STORE-001, STORE-031, CLI-013, CLI-014, CLI-021, CLI-024, BASE-017, MAP-041.
- Status: confirmed for projects, folders, settings and glue. The target columns follow MAP-041, which is confirmed. The owner column follows CLI-024, which is confirmed. `module_state` replacing the current `disabled_modules` table is recommended.

### STORE-003 Each project has one store
- Requirement: Each registered project has one SQLite store at `projects/<project id>/store.sqlite3` under the home, holding its whole map and every layer.
- What this means: Types, elements, joins, subtypes, refs, layers, provenance, layer items, selection and hidden state for one project live in one file. Nothing about the project's map lives in the base database.
- Why: One file per project can be exported, copied, backed up or deleted as a unit. Writers on different projects never contend for the same file.
- How it shows: Removing a project's store removes its map and layers and nothing else. Other projects and all settings are unaffected.
- Build: The store is created on the first write to the project. A read against a project with no store returns empty results and creates no file.
- Acceptance: A read of a project that has never been written leaves no `store.sqlite3` behind.
- Relates to: STORE-001, STORE-027.
- Status: recommended.

## Storage rules

### STORE-004 One row per thing
- Requirement: Every element, join, subtype, ref, layer item, selection and relation is its own row, and no row holds a collection of things.
- What this means: A join's refs are ref rows pointing at the join, not a list inside the join. A layer's items are item rows, not a document in a layer row. A row may hold the fields of the one thing it is, including one item's structured value, but never a list of other things that could be read or changed on their own.
- Why: A collection packed into a row makes every read load and parse the whole collection to find one member, and every change rewrite all of it. A join holding a thousand refs, or a layer holding a thousand items, in one row is a document squeezed into a table. One row per thing keeps every member reachable and changeable alone.
- How it shows: Adding one memory to a node that already has a thousand memories writes one row. Reading one ref of a join with a thousand refs reads one row.
- Build: The tables in STORE-008 to STORE-020 follow this rule. The only JSON-encoded columns are `settings.value`, which is one setting's one value, `items.value`, which is one item's value, and `extra` on joins and items, which is the unknown fields of that one row, STORE-021.
- Acceptance:
  - Write a join with 1000 refs, then add one ref. Exactly one row is inserted, and no existing row changes.
  - The schema has no column that holds a list of ids or a list of records of another kind.
- Relates to: STORE-005, STORE-021.
- Status: confirmed.

### STORE-005 Every read goes straight to its answer through an index
- Requirement: Every read the data access object offers is answered through an index, and no read scans a whole table to find its answer.
- What this means: Each question agents ask has an index built for it: a thing by id, an element by address, the joins an element receives, the joins an element provides, the subtypes at one end of a join, all items of a layer, all items at a node, the items that link to a node, and the children of a type. Table size does not change the cost of finding one answer.
- Why: Agents navigate by meaning, one question at a time: who receives this, why, how, what do other layers say here. Each question must go straight to its answer so the structure does the orienting and the agent keeps its inference for the task.
- How it shows: A read at one node of a store with a million items takes about as long as the same read in a store with a thousand.
- Build: The indexes are listed with each table. The data access object issues only the queries listed in STORE-025, each written against those indexes. Some reads are allowed to read a whole table, because the table has one row per layer or per project and the answer is that table: `layers()` and the project list; the full read of `hidden_layers` during selection resolution, STORE-019 and STORE-035; and the starting selection falling back to `layers()` when the folder's `--layers` setting is unset. `search` matches through the FTS5 index of `item_text`, whose plan reports `SCAN item_text VIRTUAL TABLE INDEX`: that is the full-text index answering the match, not a table scan. No other read may scan.
- Acceptance: For every read operation in STORE-025, `EXPLAIN QUERY PLAN` of each SQL statement it issues contains no `SCAN` of any table other than `layers`, `projects` and `hidden_layers`, and no `SCAN` of `item_text` other than `VIRTUAL TABLE INDEX`. Every other table it touches appears with `SEARCH` on an index or primary key. This test fails if a query or an index is changed so that a lookup on `elements`, `joins`, `subtypes`, `items`, `refs`, `selections` or `types` falls back to a scan.
- Relates to: STORE-004, STORE-025.
- Status: confirmed.

### STORE-006 Writes are atomic and safe with many writers
- Requirement: Every write operation is one transaction, and many processes can write to the same store at once without losing or corrupting data.
- What this means: Each agent's MCP server is its own process, so several processes write to one project store at the same time. A write either lands completely or not at all. An interrupted import or revision leaves the store exactly as it was before it started.
- Why: A store that half-applies a write gives agents a map that is neither the old state nor the new one. Agents trust what they read, so partial state is worse than a failed write.
- How it shows: Two agents adding memories to the same node at the same moment both succeed. Killing a process in the middle of an import leaves the store as it was before the import.
- Build:
  - Every connection sets `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON` and `PRAGMA busy_timeout=5000`.
  - Each write operation opens `BEGIN IMMEDIATE`, performs all its statements and commits, or rolls back on any error. Each read operation opens a plain `BEGIN`, a deferred read transaction, so all its statements see one consistent state; in WAL mode readers never wait for the write lock and never block a writer.
  - Import, STORE-027, runs in one transaction.
- Acceptance:
  - Two processes each add 500 items to the same node concurrently. All 1000 items are present afterward.
  - An import killed partway leaves the item count and every current pointer unchanged.
- Relates to: STORE-027.
- Status: confirmed.

### STORE-007 Identity is a stable id that survives change
- Requirement: Every element, join, subtype and layer item has a stable identity id that never changes, whatever happens to its address, type or content.
- What this means: An element's address names its type. A later intake or correction can type the same element better, which changes its address but not its identity id. Everything attached to it, joins, subtypes, memory and other layer items, points at the identity id, so it follows the element rather than being orphaned. Identity ids also survive export, import, copying and moving a store.
- Why: The address says what kind of thing an element is. The element is this artifact's realization of it. Knowledge about the realization must stay with it when understanding of its type improves.
- How it shows: After an element is retyped from `code.daemon` to `code.manager.gateway.mesh`, its memories, joins and challenges all appear at the new address.
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
  Foreign keys point at identity tables, never at revision rows, so a revision or a retirement never breaks a reference.
- Acceptance:
  - Retype an element that has two memories and one join as receiver. The memories and the join are found through the new address, and the identity id is unchanged.
  - Export a project and import it into an empty home. Every identity id is identical.
- Relates to: STORE-009, STORE-017, STORE-027, MAP-015.
- Status: confirmed.

## The map

### STORE-008 Type addresses are rows in a tree
- Requirement: Every namespace address used in a project is a row in the `types` table, linked to its parent address.
- What this means: The namespace is a tree of types. `code.engine.game.fps` is a type, and so are `code.engine.game`, `code.engine` and `code`, each a complete type in its own right. Writing any address writes the rows for it and for each of its prefixes that is missing. Layer items can attach to any address, whether or not an element has that type, pending LAYER-003 and D49. The store checks only an address's form, per MAP-010 and MAP-013: one or more segments separated by periods, each segment one or more lowercase letters, digits or underscores, and the whole address not a match for `^[0-9a-f]{32}$`, which is the id form of STORE-007. An address in that form is never refused for being functionally invalid.
- Why: Selection, masking and transitive layers travel the type tree from trunk to leaf, so the tree must be stored and walkable. Knowledge layers may link any namespace address, so the store records addresses as given and leaves typology judgments to the agents and workflows that make them.
- How it shows: A best practice attached as a property to the element `code.engine`, created by the knowledge layer when the project has none there, applies at every element whose address starts with `code.engine.`.
- Build:
  ```sql
  CREATE TABLE types(
    address TEXT PRIMARY KEY,
    parent  TEXT REFERENCES types(address)   -- NULL for a root such as 'code'
  );
  CREATE INDEX types_by_parent ON types(parent);
  ```
  The parent of an address is the address with its last dot-separated segment removed. Rows are inserted with `INSERT OR IGNORE`, root first. The form check is the regular expression `^[a-z0-9_]+(\.[a-z0-9_]+)*$`. An address that fails it is refused with `StoreError` whose next step names the form, STORE-026.
- Acceptance:
  - Writing an element at `code.engine.game.fps` into an empty store creates exactly four `types` rows with the right parents.
  - Writing an element at `Code..Engine` is refused and writes nothing; writing one at `media.photo.jpg` succeeds.
  - Attaching an item to an address no element has succeeds and creates its `types` rows.
- Relates to: STORE-015, STORE-019, LAYER-005, LAYER-007, MAP-010, MAP-011.
- Status: confirmed for the tree and prefix rows. Whether Type records live in each project store, as here, or are shared across projects, as MAP-010 recommends, is open; see open question 17.

### STORE-009 Elements
- Requirement: Each element is stored with its identity id, current address, informal name, name length and role, and every revision of it is kept.
- What this means: An element is one functional part of the artifact, or an entity outside it, recorded at a type address. The informal name is prose; the address is how everything refers to it. `name_length` is the number of trailing address segments read backward to form its proper noun. Role is one of AUE, VE, DE, SE or NE, or empty for an element that has none.
- Why: Elements are real records that everything else points at. The intake names them by address, so the current address must be one direct lookup, while the identity id keeps attachments stable across retyping.
- How it shows: `element code.bus.event` returns that element's current row in one read.
- Build:
  ```sql
  CREATE TABLE elements(
    row         INTEGER PRIMARY KEY,
    element_id  TEXT NOT NULL REFERENCES element_ids(element_id),
    revision    INTEGER NOT NULL,
    layer_id    TEXT NOT NULL REFERENCES layers(layer_id),
    address     TEXT NOT NULL REFERENCES types(address),
    name        TEXT,
    name_length INTEGER,
    role        TEXT CHECK(role IN ('AUE','VE','DE','SE','NE')),
    extra       TEXT,                                   -- STORE-021
    supersedes  INTEGER REFERENCES elements(row),       -- STORE-017
    reason      TEXT,
    evidence    TEXT,
    retired     INTEGER NOT NULL DEFAULT 0,
    UNIQUE(element_id, revision)
  );
  CREATE TABLE current_elements(
    element_id TEXT PRIMARY KEY REFERENCES element_ids(element_id),
    row        INTEGER NOT NULL UNIQUE REFERENCES elements(row),
    address    TEXT NOT NULL UNIQUE
  );
  CREATE INDEX elements_by_layer ON elements(layer_id);
  ```
  The current pointer carries the address so that address lookup of current elements is one unique-index read, and so that two current elements cannot hold the same address.
  - `add_element` at an address a current element already holds returns that element, marked `existing: true`, and writes nothing, whichever layer holds it. It never changes the existing element's fields. When the supplied name, name_length, role or extra differ from the existing element's, the result lists those field names under `differs`, so the writer knows and can use `revise`, STORE-034. The supplied layer is not recorded on the existing element.
  - A role is stored as given, or NULL when none is given. The store does not refuse a missing role, STORE-026. The intake writes one role on every element it creates, MAP-017.
- Acceptance:
  - Looking up an element by address after it has three revisions returns the third, through `current_elements`.
  - Adding a second element at an address that a current element already holds returns the existing element's id, marked existing, lists the fields that differ, and changes no row.
- Relates to: STORE-007, STORE-010, STORE-017, MAP-015, MAP-016, MAP-017.
- Status: confirmed for the fields. One current element per address in a project is recommended; see open question 1. MAP-017 requires exactly one role on every element, while this table allows an element with no role; whether an element created by a layer other than the intake must carry a role is open, see open question 18.

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
    revision    INTEGER NOT NULL,
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
    supersedes  INTEGER REFERENCES joins(row),
    reason      TEXT,
    evidence    TEXT,
    retired     INTEGER NOT NULL DEFAULT 0,
    UNIQUE(join_id, revision)
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
  - `join_ids.receiver` fixes the owner for the life of the join. A revision may change the provider or any text column, never the receiver.
  - Both ends reference `element_ids`. A subtype's id is in `subtype_ids`, so a subtype cannot be a join end.
  - Nothing checks for cycles among elements. Two elements may each receive from the other through two joins.
- Acceptance:
  - Two joins, A receives from B and B receives from A, both store and both read back.
  - Writing a join whose provider is a subtype id fails with the foreign key error mapped in STORE-026.
  - The identity read of an element with 50 provider joins among 100000 joins uses `current_joins_by_provider`.
- Relates to: STORE-009, STORE-011, STORE-025, MAP-001, MAP-002, MAP-003, MAP-020.
- Status: confirmed.

### STORE-011 Subtypes live inside one join, at one end
- Requirement: Each subtype is stored in its own table, tied to the one join it shares with its parent and to the end of that join it belongs to, with its own address and its own purpose or function.
- What this means: Annealing combines parts that share the same join into a larger parent functionality. The combined node carries the combined purpose or the combined encounter, and each absorbed part stays as a subtype under it. At the provider end a subtype keeps its own encounter function under the combined encounter. At the receiver end it keeps its own purpose under the combined purpose. A subtype keeps its own address, name, relation and observation, and layers attach to it directly. It is reachable only through its join, is never a root element, and is never a join end.
- Why: Annealing keeps the root map minimal without discarding functionality. A subtype exists only because it shares that join with its parent, so it lives there. A separate table whose rows can only point at a join makes "excluded from the external graph" a property of the schema, so no query can pull a subtype into the element graph by forgetting a filter.
- How it shows: `subtypes <join>` lists the probes inside the failsafe's join, each with its own function. `where code.probe.echo` answers with the join and end it lives in, not as a root element.
- Build:
  ```sql
  CREATE TABLE subtypes(
    row         INTEGER PRIMARY KEY,
    subtype_id  TEXT NOT NULL REFERENCES subtype_ids(subtype_id),
    revision    INTEGER NOT NULL,
    layer_id    TEXT NOT NULL REFERENCES layers(layer_id),
    end         TEXT NOT NULL CHECK(end IN ('receiver','provider')),
    address     TEXT NOT NULL REFERENCES types(address),
    name        TEXT,
    name_length INTEGER,
    role        TEXT CHECK(role IN ('DE','SE','NE')),
    purpose     TEXT,      -- its own purpose, at the receiver end
    function    TEXT,      -- its own encounter function, at the provider end
    relation    TEXT,
    observation TEXT,
    extra       TEXT,
    supersedes  INTEGER REFERENCES subtypes(row),
    reason      TEXT,
    evidence    TEXT,
    retired     INTEGER NOT NULL DEFAULT 0,
    UNIQUE(subtype_id, revision)
  );
  CREATE TABLE current_subtypes(
    subtype_id TEXT PRIMARY KEY REFERENCES subtype_ids(subtype_id),
    row        INTEGER NOT NULL UNIQUE REFERENCES subtypes(row),
    join_id    TEXT NOT NULL,
    end        TEXT NOT NULL,
    address    TEXT NOT NULL
  );
  CREATE INDEX current_subtypes_by_join_end ON current_subtypes(join_id, end);
  CREATE INDEX current_subtypes_by_address ON current_subtypes(address);
  ```
  - `subtype_ids.join_id` fixes the join. A subtype never moves to another join.
  - Until MAP-032 is settled, `add_subtype` and `revise` refuse an address that a current subtype or a current element already holds, and a current element's address may not be taken by a new subtype. The check is one read on `current_subtypes_by_address` and one on `current_elements`.
  - A join may have subtypes at both ends at once.
- Acceptance:
  - A subtype written at the provider end of a join is returned by the subtypes read for that join and end, and by no element or join read.
  - No read that returns elements, or joins by receiver or provider, ever returns a subtype.
  - Writing an item attached to a subtype succeeds and is returned by the node read for that subtype.
- Relates to: STORE-010, STORE-015, MAP-030, MAP-031, MAP-032.
- Status: confirmed for placement and storage. The address rule is recommended and follows MAP-032 until open questions 3 and 4 are answered.

### STORE-012 Refs
- Requirement: Each ref is one key and value row attached to one revision row of an element, join, subtype or layer item.
- What this means: Refs carry type-specific or artifact-specific references, such as `path` pointing at a member file. They belong to the revision they were written with, so a reader of a revision gets exactly the refs that revision had.
- Why: Refs are part of what a revision says. Tying them to the revision row keeps an earlier revision readable exactly as it was after a correction changes its refs.
- How it shows: After a join is revised to drop a stale path ref, reading the old revision still shows the path, and the current revision does not.
- Build:
  ```sql
  CREATE TABLE refs(
    ref_id    INTEGER PRIMARY KEY,
    owner     TEXT NOT NULL CHECK(owner IN ('element','join','subtype','item')),
    owner_row INTEGER NOT NULL,   -- elements.row, joins.row, subtypes.row or items.row
    position  INTEGER NOT NULL,   -- order as written
    key       TEXT NOT NULL,
    value     TEXT NOT NULL
  );
  CREATE INDEX refs_by_owner ON refs(owner, owner_row, position);
  CREATE INDEX refs_by_key_value ON refs(key, value);
  ```
  A revision copies forward the refs it keeps, as new rows pointing at the new revision row.
  - Refs are written with their owner: the create operations of STORE-024 take a `refs` list of key and value pairs in order. `add_ref` adds one more ref to a thing's current revision only while that thing's layer is building, by its builder, STORE-032, or when the layer is mutable. After an immutable layer is locked, a ref changes only through `revise`, STORE-017.
- Acceptance:
  - A join with refs `path=a` and `path=b`, revised to keep only `path=b`, reads back with one ref at the current revision and two at the old one.
  - `add_ref` on a thing in a locked immutable layer is refused with `StoreError` naming `revise`.
- Relates to: STORE-004, STORE-017, STORE-025, STORE-032, MAP-021.
- Status: recommended. The lookup by key and value is required by MAP-021.

## Layers

### STORE-013 Layers and their declared behavior
- Requirement: Each layer is a row carrying its name, its module and its declared behavior: mutable or immutable, hideable, and transitive.
- What this means: Everything Metaform holds is a layer, the intake's map included. A layer carries one inferred variable. Declaring behavior on the layer lets the store apply revisions, visibility and propagation the same way for every layer.
- Why: When every layer attaches the same way and declares its behavior, layers compose, and a module can add one without knowing about any other. No module rebuilds revision, hiding or propagation rules of its own.
- How it shows: `metaform query layers` and `metaform map layers` show each layer with its id, name, kind, module, completion and its three properties.
- Build:
  ```sql
  CREATE TABLE layers(
    layer_id   TEXT PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    module     TEXT NOT NULL,
    variable   TEXT NOT NULL CHECK(variable <> ''),   -- LAYER-002: the one question the layer answers
    mutable    INTEGER NOT NULL CHECK(mutable IN (0, 1)),
    hideable   INTEGER NOT NULL CHECK(hideable IN (0, 1)),
    transitive INTEGER NOT NULL CHECK(transitive IN (0, 1)),
    result_id  TEXT,                                  -- MAP-040: the intake result id, on an intake layer
    kind       TEXT NOT NULL DEFAULT 'layer'
               CHECK(kind IN ('layer','intake','memory')),  -- STORE-032
    created    TEXT NOT NULL,                         -- LAYER-001: creation time, ISO 8601 UTC
    locked     TEXT,                                  -- STORE-032: NULL while the layer is building
    build_key  TEXT                                   -- STORE-032: SHA-256 of the build token while building, NULL once locked
  );
  CREATE TABLE hidden_layers(layer_id TEXT PRIMARY KEY REFERENCES layers(layer_id));
  ```
  - A layer's properties are set when it is created and never change.
  - A layer name is one to 128 characters of letters, digits, periods, underscores and hyphens, and is never a match for `^[0-9a-f]{32}$`. Every operation that takes a layer takes a layer reference: a layer id, per STORE-007, or a name, looked up through the `name` unique index.
  - Hiding writes a `hidden_layers` row and is allowed only for a hideable layer. Hidden layers are left out of node reads and selection results unless the read asks for them by name.
- Acceptance:
  - Hiding a layer declared not hideable returns the error in STORE-026 and writes nothing.
  - A hidden layer's items are absent from the node read and present when that layer is read by name.
- Relates to: STORE-014, STORE-016, STORE-017, STORE-018, LAYER-001, LAYER-002, LAYER-004, LAYER-006, MAP-040.
- Status: confirmed for the three properties. Where the properties are declared is open question 5. Hiding by dependency is open question 6.

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
- What this means: An item attaches to a type address, an element, a join or a subtype. Its value is that layer's variable at that node, such as one best practice, one challenge or one memory observation. The optional link points at another node; a memory relation links one node to another. Links are items, so the whole structure stays navigable from any node, and links may form cycles.
- Why: One variable per layer is what lets any set of layers be selected together. Links as items mean an item points at the real node instead of copying it, and following links backward from the map shows everything that refers to a node.
- How it shows: Reading memory at `code.guard.switch.gateway` by incoming links lists every memory relation that points at it.
- Build:
  ```sql
  CREATE TABLE items(
    row         INTEGER PRIMARY KEY,
    item_id     TEXT NOT NULL,
    revision    INTEGER NOT NULL,
    layer_id    TEXT NOT NULL REFERENCES layers(layer_id),
    target_kind TEXT NOT NULL CHECK(target_kind IN ('type','element','join','subtype')),
    target_id   TEXT NOT NULL,     -- types.address, or an identity id
    value       TEXT NOT NULL,     -- JSON: this one item's value
    link_kind   TEXT CHECK(link_kind IN ('type','element','join','subtype')),
    link_id     TEXT,
    extra       TEXT,
    supersedes  INTEGER REFERENCES items(row),
    reason      TEXT,
    evidence    TEXT,
    retired     INTEGER NOT NULL DEFAULT 0,
    UNIQUE(item_id, revision)
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
  CREATE INDEX current_items_by_layer  ON current_items(layer_id, target_kind, target_id);
  CREATE INDEX current_items_by_target ON current_items(target_kind, target_id, layer_id);
  CREATE INDEX current_items_by_link   ON current_items(link_kind, link_id, layer_id);
  ```
  - The data access object checks that an identity target exists in its identity table, and writes `types` rows for a type target, STORE-008.
  - `value` is any JSON value: a string, number, boolean, array, object or null. It is the answer to the layer's one variable at this node. The store does not judge its content.
  - `extra` is a JSON object or NULL. It holds any further fields the writer supplies for this one item that are not the variable's answer, STORE-021. An `extra` that is not an object is refused.
- Acceptance:
  - All items of a layer, all items at a node, and all items linking to a node are each returned by one read using the matching index.
  - An item linking from A to B and another from B to A both store and both read back.
- Relates to: STORE-004, STORE-005, STORE-020, LAYER-003, LAYER-015.
- Status: confirmed for attachment to elements, joins and subtypes, and for links. Attaching an item at a type address with no element is used by LAYER-005 and MAP-011 but is not in LAYER-003's list of attachment targets; see open question 19. The fields inside a layer's value are open question 7.

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
    prompt   TEXT,
    model    TEXT,
    role     TEXT,
    blinded  INTEGER CHECK(blinded IN (0, 1))
  );
  ```
  - The row is written in the same transaction that creates the layer, from the provenance argument of the layer operation, STORE-024. Creating a layer other than memory without provenance is refused, per LAYER-010.
  - `prompt` holds the prompt text the layer was produced from, as given.
- Acceptance:
  - The store has no provenance table or column keyed by item, element, join or read.
  - Creating a layer with provenance and then writing 100 items leaves exactly one provenance row for that layer, with its fields unchanged.
  - A memory layer has no provenance row.
- Relates to: STORE-013, LAYER-010, REQ-101 to REQ-105 as corrected.
- Status: confirmed. What a layer written by a person or by a deterministic import records is open question 8. Whether a second run adds to the same layer is open question 9.

### STORE-017 Immutable layers change by superseding revisions
- Requirement: A thing in an immutable layer is never edited in place; a correction writes a new revision row that supersedes the old one, and the current pointer moves to it.
- What this means: The map is the shared foundation. A correction to an element, join, subtype or item writes a new row with the next revision number, the row it supersedes, the reason and the evidence. The old row stays exactly as it was and stays readable. "Current" is a pointer, and moving it is the correction taking effect. Retiring a thing is a revision with `retired = 1`, and its pointer row is removed. Anything built on a superseded revision is re-examined, never rewritten.
- Why: A change to the foundation must be explicit and traceable. Adding superseding revisions and a pointer is how a graph is corrected without breaking anything that refers to an earlier state, and it keeps every earlier state available for comparison.
- How it shows: `revisions <join>` lists every revision with its reason and evidence. Reading by identity returns the latest; reading a named revision returns that one.
- Build:
  - Revise, in one transaction: read the current row; insert a new row with `revision = old + 1`, `supersedes = old row`, the changed fields, `reason` and `evidence`, and the refs it keeps, STORE-012; update the pointer row to the new row, or delete it when retiring.
  - The pointer tables are the only rows ever updated or deleted in an immutable layer.
  - Revising a thing in a mutable layer returns the error in STORE-026, because a mutable layer changes in place, STORE-018.
- Acceptance:
  - After a revise, the old row's bytes are unchanged, the new row supersedes it, and an identity read returns the new row.
  - A retired join is absent from receiver and provider reads and present in its revision history.
  - No `UPDATE` or `DELETE` statement in the data access object targets `elements`, `joins`, `subtypes`, or the `items` rows of an immutable layer, except inside `edit`, `remove` and `discard` on a building layer, which change only content rows written in that layer and never identity or `types` rows, STORE-032. A building layer was never visible in context, so nothing can depend on it.
- Relates to: STORE-007, STORE-012, STORE-018, LAYER-011, REQ-026, REQ-106 as corrected.
- Status: confirmed. How dependents are found for re-examination is open question 6.

### STORE-018 Mutable layers change in place
- Requirement: Items in a mutable layer are updated and deleted in place, with no revision history kept.
- What this means: Memory is the main mutable layer. An agent adds an observation, changes it, or deletes it, and the store holds only the current state, the way the reference memory server does.
- Why: Memory is agents' working notes. Its value is being cheap to add and fix. One memory at a node fixes a small wrong inference right where agents read it, so the map does not have to be perfect to be useful. History and provenance would make every note heavy.
- How it shows: Updating a memory changes its value; there is no older revision to read.
- Build: For a mutable layer's item, update writes the new `value` into the existing `items` row at revision 1. Delete removes the `current_items` row, the `items` row and its refs in one transaction.
- Acceptance:
  - After ten updates to one memory, the item has one row.
  - After a delete, the item appears in no read.
- Relates to: STORE-017, STORE-020, LAYER-012, REQ-127 as corrected.
- Status: confirmed.

### STORE-019 Selection and mask are stored where the flow changes
- Requirement: Selection and mask are stored as rows at type addresses, and the effective selection at an address is computed from trunk to leaf as `effective = (incoming & mask) | select`.
- What this means: The project selects every layer by default. An address selects nothing of its own and masks nothing by default. A mask row at an address stops a layer flowing into that branch. A select row turns a layer on at that address and below. A read may supply its own root selection, such as a workflow's, and masks still apply. An element takes the effective selection at its address. A join taking its receiver's selection is recommended and open, per LAYER-007. A subtype taking its own address's selection is recommended.
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
  Resolution for an address: start from the starting selection: the read's own starting selection when it supplies one, else the layers toggled on by the folder's `--layers` setting, CLI-033, with each tag expanded through `layer_tags`, else every locked layer, STORE-035; for each prefix from the root segment to the full address, remove the layers masked there, then add the layers selected there; finally remove hidden layers. Each step is one primary-key range read on `selections`. The resolved set is what every node read uses.
- Acceptance:
  - The mask example above gives the stated results.
  - A layer masked at an element's address does not appear in the node read for a join that element receives, nor in the provider read that reaches that element.
- Relates to: STORE-008, STORE-013, STORE-025, REQ-121, REQ-122, LAYER-006, LAYER-007.
- Status: confirmed for the rule. Storing it as rows at type addresses is recommended. The selection of joins and subtypes is open, per LAYER-007 and LAYER open question 6.

## Memory

### STORE-020 Memory follows the reference memory server over the map's own nodes
- Requirement: Memory is a mutable layer whose entities are the map's nodes, whose observations are items, and whose relations are linked items, reached through the reference memory server's operations.
- What this means: The operations are those of LAYER-013: create entities, create relations, add observations, delete entities, delete observations, delete relations, read graph, search nodes and open nodes. An entity is an element, join, subtype or type address, named by its address or its identity id, with its node kind as its type. Each observation is one item in the memory layer attached to that node. Each relation is one item attached to the `from` node, linking to the `to` node, with the relation type as its value. Every node is already an entity of the memory layer without any row being written for it. Memories at the map's nodes are open to every agent to read, because they exist to share knowledge.
- Why: Agents already know the memory server's interface. Attaching memory to the map's own nodes means a single memory corrects a wrong inference where agents read it. The reference server keeps its whole graph in one file that it rewrites on every change; this store keeps each observation and relation as its own indexed row.
- How it shows: `memory open code.manager.route` returns the node with its observations and relations, including relations other nodes hold toward it.
- Build:
  - The default memory layer has the name `memory`, kind `memory`, module `memory`, and the variable `What agents have noted at this node.` It is mutable, hideable and not transitive, with no provenance row. The first memory write operation in a project creates it, inside that operation's transaction. A layer is recognized as memory by its kind, never by its name.
  - Search runs over item values through an SQLite FTS5 table kept in step with `items` by triggers. It indexes every layer's items. A search returns only items of layers in the effective root selection that are locked and not hidden, unless the call names a layer, in which case it searches that layer alone:
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
    Every `items` row is indexed, superseded revisions included. `search` joins each match through `current_items` on the row, so only current revisions are returned. The default `unicode61` tokenizer treats JSON quotes, braces and colons as separators, so a word inside a JSON value matches as a word. The search text is passed to `MATCH` as one quoted phrase per word, with any double quote in it doubled, so user text is never read as FTS5 query syntax.
  - Open nodes: the node's identity read plus two index reads, items at the node and items linking to it.
- Acceptance:
  - Adding an observation to a node that has no memories writes one item row and no other row.
  - A relation from A to B appears when opening A and when opening B.
  - Search finds an observation by a word in it, on Linux, macOS and Windows.
- Relates to: STORE-015, STORE-018, LAYER-012, LAYER-013, REQ-126 as corrected, MCP.
- Status: confirmed for the interface and for elements and joins as its nodes, per LAYER-013. Subtypes and type addresses as memory nodes are recommended; they follow from LAYER-003, where every layer attaches at subtypes. FTS5 for search, and the default layer's fields, are recommended. Whether memory can create a node that is not already in the map is open question 10.

## Extension and module data

### STORE-021 Unknown fields survive
- Requirement: Fields a module adds to an element, join, subtype or item beyond the defined columns are kept in that row's `extra` value and survive reads, revisions, export and import.
- What this means: Modules may define additional join types and content without forcing every join into one closed schema. The defined columns hold what the engine uses. Anything else a writer supplies for that one row is kept alongside, unchanged.
- Why: A module's extension content must not be lost because the chassis does not know it, or modules could not extend the map.
- How it shows: A join written with a field `latency_budget` reads back with it, keeps it through a revision that does not touch it, and keeps it through export and import.
- Build: `extra` is a JSON object of the row's own additional fields. It is carried forward by revise unless the revision changes it.
- Acceptance: The round trip in How it shows holds byte for byte on the field's value.
- Relates to: STORE-004, STORE-027, REQ-017.
- Status: recommended.

### STORE-022 A module keeps its own data as a layer
- Requirement: Everything a module keeps is stored through the data access object as a layer, and no module writes files or databases of its own.
- What this means: A module that needs to remember something declares a layer and writes items to it. Such data is exported, imported and queried with everything else.
- Why: Data held outside the chassis cannot be exported, imported or queried as a whole, and cannot be selected alongside other layers. The template module currently writes its own `history.json` through `Context.data`, which this requirement replaces.
- How it shows: The template module's greeting history appears as a layer in `list layers` and in an export.
- Build: `Context.data`, the per-module folder under the home, is removed from the common base. The template module's history becomes items in a mutable layer it declares. Every template verb and handler that reads or writes that layer calls `ctx.require_store()`, so in a folder with no project it stops with `Next: metaform add project <id> <path>`. The template's event subscriber receives a Context built from the publisher's folder and project, BASE-028, and so writes to the same project's store. Its choices function receives a Context and returns no choices when the store is None, CLI-019.
- Acceptance: After exercising every template verb, the home contains no file outside the base database and project stores.
- Relates to: STORE-023, STORE-024, BASE-005, BASE-019.
- Status: recommended. Where an item goes when it is about no map node is open question 11.

## The data access object

### STORE-023 The data access object is the only way to the data
- Requirement: The chassis provides one data access object, imported by every module from the common base, and it is the only code that opens a store or issues SQL.
- What this means: A module never touches SQLite, table names or files. It asks the data access object for things by address or identity id and gets objects back. The CLI and the MCP module use the same object, so every surface reads and writes identically.
- Why: A module built on the base cannot corrupt the map, cannot drift from the CLI or MCP, and keeps working when the storage underneath changes. Layers only compose if every module writes them the same way.
- How it shows: A module written from the template stores and reads its data with no import of `sqlite3`.
- Build: The public import is `from metaform.data import Store, Node, StoreError`. A verb receives the store for its context's project as `ctx.store`, BASE-028. When the folder resolves to no project, `ctx.store` is None, and `ctx.require_store()` raises `Stop('No project for this folder.', 'metaform add project <id> <path>')`. Every map, intake and memory verb calls `ctx.require_store()`. `Store(project_id)` for an id that is not registered raises `StoreError` with the next step `metaform list projects`. Chassis verbs that act on data, such as `export`, `import` and `query`, resolve the project the same way. Objects returned are frozen dataclasses: `Element`, `Join`, `Subtype`, `Item`, `Layer`, `Provenance`, `Revision`. A `Node` is `(kind, id)` where kind is `type`, `element`, `join` or `subtype` and id is an address or identity id.
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
  | `layer(name, module, variable, *, kind='layer', mutable, hideable, transitive, provenance=None, result_id=None, sources=(), locked=False)` | provenance is a mapping with module, workflow, prompt, model, role, blinded; sources are layer references, STORE-036 | `Layer`: an immutable layer is created building, with its build token returned once, or locked when `locked=True`; a mutable one is created locked, STORE-032; the existing layer when the name exists with the same kind, module, variable, mutable, hideable and transitive, without a token | name exists with any of those different; empty variable; provenance missing for a layer whose kind is not memory |
  | `atomic()` | a context block | every write inside the block commits together when the block ends, or none does if it raises; a layer created in it with `locked=True` becomes visible, locked, at commit | nested `atomic()` joins the outer block |
  | `lock(layer, token)` | | `Layer` with `locked` set; the token stops working | layer unknown; already locked; wrong token |
  | `edit(thing, token, changes)` | thing is an element, join, subtype or item written in a building layer; `changes` per STORE-034 | the changed row, in place, with no revision | layer locked or mutable; wrong token; a key not allowed for the thing's kind |
  | `remove(thing, token)` | thing is an element, join, subtype, item or ref written in a building layer | nothing; the row and the refs and links attached to it are deleted, identity and `types` rows stay | layer locked or mutable; wrong token; the thing is still the receiver, provider or target of a current row in the layer |
  | `discard(layer, token)` | a building layer | nothing; the layer's content is deleted and its identity and type rows stay, STORE-032 | layer unknown; layer locked; layer mutable; wrong token |
  | `add_element(layer, address, *, name=None, name_length=None, role=None, refs=(), extra=None)` | address in the form of STORE-008 | `Element`; the existing current element, marked existing with `differs`, when the address is held, STORE-009 | layer unknown; layer locked and immutable; wrong token for a building layer; malformed address |
  | `add_join(layer, receiver, provider, *, purpose, function, relation, observation, non_goal=None, type='purpose', refs=(), extra=None)` | receiver and provider as address or element id, read as an id exactly when it matches the id form, STORE-007 | `Join` | receiver or provider is not an element; either is a subtype; receiver equals provider, per D11 when confirmed |
  | `add_subtype(layer, join, end, address, *, purpose=None, function=None, relation=None, observation=None, name=None, name_length=None, role=None, refs=(), extra=None)` | end is `receiver` or `provider` | `Subtype` | join unknown; end not one of the two; malformed address |
  | `add_ref(owner, key, value)` | owner is an element, join, subtype or item id | the ref, attached to the owner's current revision | owner unknown; owner's layer locked and immutable, STORE-012; wrong token for a building layer |
  | `add_item(layer, target, value, *, link=None, refs=(), extra=None)` | target and link are `Node`s | `Item` | target or link unknown for identity kinds; `extra` not an object |
  | `add_property(layer, element, value, *, refs=(), extra=None)` | element as address or element id | `Property` | element unknown; a target that is not an element; `extra` not an object |
  | `answer(item_id, state, link=None)` | state A, B or C; link for C | challenge state | per STORE-040 |
  | `approve(item_id)` | a challenge answered B | challenge state and plans | per STORE-040 |
  | `add_plan(layer, element, join)` | a new function element and its join | plan | per STORE-040 |
  | `update_item(item, value)` | an item of a mutable layer | `Item` | layer is immutable; use `edit` while building |
  | `delete_item(item)` | an item of a mutable layer | nothing | layer is immutable; use `remove` while building |
  | `revise(thing, changes, *, reason, evidence=None)` | thing is an element, join, subtype or item id; `changes` per STORE-034 | the new revision | layer is mutable; receiver change requested; a key not allowed for the thing's kind |
  | `retire(thing, *, reason, evidence=None)` | | the retiring revision | layer is mutable; the thing still has current dependents, STORE-034 |
  | `reexamined(layer)` | | nothing | layer unknown, STORE-036 |
  | `select(address, layer)`, `mask(address, layer)`, `clear(address, layer, kind)` | | nothing | layer unknown |
  | `hide(layer)`, `unhide(layer)` | | nothing | layer not hideable |

- Acceptance: For each operation, one test performs it and checks the rows it must write and that no other table changed. Each listed error is produced once and writes nothing.
- Relates to: STORE-009 to STORE-022, STORE-026, STORE-031 to STORE-036, STORE-040.
- Status: confirmed for the set of things written and for building then locking a knowledge layer. Operation names, signatures and the build token are recommended. Every write into a building layer, `add_element`, `add_join`, `add_subtype`, `add_item`, `add_ref`, `edit`, `remove`, `lock` and `discard`, takes the layer's build token; the intake's single `atomic()` write creates its layer locked and needs none.

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
  | `identity(element)` | C(T): every current join where it is the provider | `current_joins_by_provider` |
  | `subtypes(join, end=None)` | the subtypes at one or both ends of a join | `current_subtypes_by_join_end` |
  | `where(address)` | the element, or the join and end holding a subtype, at an address | `current_elements`, `current_subtypes_by_address` |
  | `children(address)` | the next types up the tree, toward the leaves | `types_by_parent` |
  | `layer_items(layer, target=None)` | all of a layer, or a layer at one node | `current_items_by_layer` |
  | `node(target, selection=None, raw=False)` | every layer's items at one node, grouped by layer. In context, the default, only layers in the effective selection that are locked and not hidden; with `raw=True`, every stored layer, building, hidden or masked included | `current_items_by_target`; `selections` primary key |
  | `context(address, selection=None)` | the applying and the visible transitive items at an address, as two lists, STORE-035 | `current_items_by_target`; `types` primary key range |
  | `links_to(target, layer=None)` | items in any layer linking to a node | `current_items_by_link` |
  | `citing(key, value)` | every current element, join, subtype and item whose refs hold that key and value, per MAP-021 | `refs_by_key_value` |
  | `revisions(thing)` | every revision with reason and evidence | `UNIQUE(id, revision)` |
  | `revision(thing, n)` | one named revision | `UNIQUE(id, revision)` |
  | `layers(tag=None, kind=None, module=None)`, `provenance(layer)` | the layers with properties, kind, module, tags, whether each is building or locked, whether it is hidden, and whether it is toggled on for the current context, LAYER-019, filtered by tag, kind and module; one layer's provenance | full read of `layers`, STORE-005, or `layer_tags_by_tag` when filtering by tag; primary key |
  | `effective_selection(address, root=None)` | the resolved layer set at an address, and any unresolved selection rows, STORE-035 | `selections` primary key |
  | `search(text, layer=None)` | items whose value matches, per STORE-020 | `item_text` |
  | `has_intake()` | whether the project holds a locked intake layer, STORE-032 | `layers_by_kind` |
  | `project()` | the project record with its target, STORE-031 | `projects` primary key |

- Joins from layers:
  - Every read that returns a join, `joins`, `identity`, `node`, `context`, `links_to`, `where` for a subtype, and the graph and export reads, returns with each join its `layer_id` and `layer`, the name of the layer it comes from, read from the join row's `layer_id` through the `layers` primary key. Subtypes carry the layer of the join that holds them.
  - The reads that return joins take `selection=None, raw=False` like `node`. In context, the default, a join is returned only when its layer is locked, not hidden, and in the effective selection at its receiver's address, LAYER-007. With `raw=True`, every stored join is returned, each with its layer name.
  - The intake map's joins go through the same filter, so masking the intake layer at an address removes its joins there like any other layer's.
- Acceptance:
  - STORE-005's plan test covers every row of this table.
  - Every join returned by every read in this table carries a non-empty `layer` equal to the name of the layer whose id its row holds.
  - A join added by a locked knowledge layer is returned by `joins(receiver)` in context when that layer is toggled on, is absent when it is toggled off or masked at the receiver's address, and is returned by `joins(receiver, raw=True)` in both cases.
- Relates to: STORE-005, STORE-012, STORE-019, MAP-001, MAP-021, LAYER-016, CLI, MCP.
- Status: confirmed for the questions answered, and for every join showing the layer it comes from. Names, signatures and the in-context filter of joins are recommended.

### STORE-026 Errors name one next step and never judge content
- Requirement: A data access error states what is wrong and names one next command, and the store never refuses a write because of what its text says.
- What this means: Errors come only from the shape: a reference to something that does not exist, a subtype used as a join end, an in-place change to an immutable layer, a revision to a mutable one, hiding a layer that is not hideable. Wording, purpose quality and typology are never checked by the store.
- Why: A check that rejects inference sends agents into retry loops. An agent-built check once turned a five-minute intake into 456 minutes and $750. The shape enforces itself, and nothing gates inference. An error that names the next command keeps an agent on the surface instead of sending it into the source.
- How it shows: `add_join` with an unknown provider answers: `code.probe.echo is not an element in this project. Next: metaform map add-element code.probe.echo`.
- Build: `StoreError(message, next_step)` subclasses the chassis `Stop`. SQLite constraint errors are caught inside the data access object and mapped to a `StoreError` with the next step for that operation. No other exception type leaves the data access object. Form errors, such as a malformed address, STORE-008, or an `extra` that is not an object, are shape errors and are refused like the others.
- Acceptance:
  - Each error in STORE-024's table produces a `StoreError` whose next step is one command.
  - A join whose purpose is an empty string, or whose text is unrelated to its elements, stores without error.
- Relates to: STORE-024, CLI-009, MCP-006.
- Status: confirmed.

## Moving data in and out

### STORE-027 Export and import carry a project whole
- Requirement: `export` writes a project, or chosen layers of it, to one exchange document, and `import` reads such a document into a store, keeping every identity id, revision, provenance record and extension field.
- What this means: Documents are the exchange format only. The store is always the tables above. An intake is never loaded by importing its answer document; the agent builds the map through the write operations. Export and import move a project between homes, back it up, and let a wheel carry data.
- Why: Identity and history must survive moving storage, or everything attached to the map breaks when it moves. Keeping documents out of the working store keeps the one-row-per-thing rules true everywhere.
- How it shows: A project exported from one machine and imported on another answers every read the same way.
- Build:
  - Commands: `metaform export [<project>|all] [file=<file>] [layer=<name>]...` and `metaform import <file> [<project>]`. Every argument is a noun, BASE-043: `file` and `layer` are optional nouns written as `name=value`, because what to export is data the verb acts on, not a setting. The project, or the argument `all`, CLI-002, is the one positional noun of `export`, optional, and is read as the first word that contains no `=`; `import` likewise takes its file and then an optional project positionally. With no project, export takes the folder's project. `all` exports every registered project. With no file, export writes the document to standard output. `layer` may repeat and limits the export to those layers. Import with no project uses the project record in the document; with a project id, it imports into that registered project.
  - The document is JSON: `{"metaform_export": 1, "schema_version": N, "projects": [P, ...]}`. Each `P` is `{"project": {"project_id", "path", "target_type", "target_value"}, "types": [...], "layers": [...], "provenance": [...], "selections": [...], "hidden": [...], "elements": [...], "joins": [...], "subtypes": [...], "items": [...], "refs": [...], "requires": [...]}`.
  - Each list holds one object per row, including every revision. A row object has one member per column of its table, named as the column, except the integer `row`, `owner_row` and `supersedes` columns, plus `current`, true when the row is the one its pointer table points at. `supersedes` is written as the superseded revision number. `hidden` is a list of layer ids. `requires` is a list of objects, `{"kind": "element"|"join"|"subtype"|"item", "id": <identity id>}` or `{"kind": "type", "address": <address>}`. Rows refer to each other by identity id and revision number, never by the store's `row` integers, which are not exported. A ref names its owner by kind, identity id and revision. On import, new `row` values are assigned and every reference is remapped through identity id and revision.
  - A layer-limited export carries that layer's rows and its provenance, plus `requires`: the identity ids and type addresses its rows point at that belong to other layers. Import refuses a document whose `requires` are not present in the target store, naming the first missing one, with the next step to import the project's map first.
  - Importing a project into a home where it is not registered registers it from the document's project record. Importing into a registered project keeps that project's path and target.
  - Import runs in one transaction, STORE-006. Importing a document into a store that already holds the same identity ids with identical rows changes nothing.
- Acceptance:
  - Export, import into an empty home, export again: the two documents are identical.
  - An import killed partway leaves the target store unchanged.
- Relates to: STORE-006, STORE-007, STORE-021, BASE-002, BASE-025.
- Status: confirmed for the requirement. JSON as the document format follows E7. The command grammar and the document shape are recommended. Import into a store holding different rows with the same identity ids is open question 13.

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
- Status: recommended. Whether stores from the current chassis branch, which keep joins as JSON bodies in `objects` and `joins` tables, are migrated is open question 14.

### STORE-030 A directly run wheel keeps its data in its own subfolder
Specified in BASE-023 and BASE-025: a directly run wheel keeps its home in its own subfolder under `~/.metaform`, and installing a wheel can merge its data in through export and import, STORE-027.

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

### STORE-032 Layer kinds, building and locking
- Requirement: Every layer has a kind, intake, memory or layer; an immutable layer is building while its writer works on it and is locked when its writer's task is done; a mutable layer is never building and never locked against change.
- What this means: The kind tells the chassis which rules a layer follows without reading its name: memory has no provenance, and an intake layer is what "has an intake" looks for. There are three ways a layer comes to exist, LAYER-018:
  - The intake layer is written whole, in one atomic write by `intake_submit`, and is locked from the moment it exists, BASE-039.
  - A knowledge layer, or any immutable layer a module builds over several calls, is building while its agent follows its prompt. During that time its builder can add, edit and remove its elements, joins, subtypes, items and refs in place, with no revisions, as freely as memory is edited. No other agent can write to it, and no other agent's read in context sees it. When the task is done, the builder locks it. A locked layer is immutable: it changes only by correction, STORE-017, its one provenance record stays as written, and it can be selected, masked and hidden like any other layer.
  - A mutable layer, memory included, is created ready and stays editable in place forever, STORE-018.
- Why: The model builds a knowledge layer incrementally against its prompt and fixes its own work as it goes, so it needs full freedom to change what it wrote until its task is done. Locking gives the layer a stable identity that can be trusted, compared and selected, and it is what lets anything else depend on it. Writing the intake in one submission means a half-written intake never exists, so the no-intake notice clears only when a whole intake is stored.
- How it shows: While a knowledge layer is building, the building agent reads it by name and sees every change it makes; another agent reading the same element in context sees nothing of it. After `lock`, the layer appears in context reads under the selection, and an attempt to edit it is refused with the next step naming `revise`. During an intake run nothing is stored, so `metaform` status shows the no-intake notice until `intake_submit` succeeds.
- Build:
  - `layers.kind`, `layers.locked` and `layers.build_key`, STORE-013. `CREATE INDEX layers_by_kind ON layers(kind, locked);`
  - `layer(...)` without `locked=True` creates an immutable layer building: `locked` is NULL, and a build token of 32 random bytes, hex encoded, is generated and returned once; `build_key` stores its SHA-256. A mutable layer, including memory, is created with `locked` set and no token, because it has no building phase; its items change through `update_item` and `delete_item`.
  - Every write into a building layer takes the token: `add_element`, `add_join`, `add_subtype`, `add_item`, `add_ref`, `edit`, `remove`, `lock` and `discard`. A missing or wrong token is refused with `StoreError` and writes nothing. The token is how "only the building agent" is enforced without agent identities: the agent that created the layer holds it, and the module keeps it for that agent's session only in the reply to the create call.
  - `edit` changes a row written in the building layer in place. `remove` deletes a row written in it, with its refs and links; it refuses to remove a row that another current row in the same layer still uses as receiver, provider or target. Identity rows, STORE-007, and `types` rows, STORE-008, are never deleted.
  - `lock(layer, token)` sets `locked` to the current time and clears `build_key`. After that the layer's rows change only through `revise` and `retire`.
  - `has_intake()` is true when a layer of kind intake exists with `locked` set. An intake layer is only ever created locked, inside `atomic()`. One indexed read.
  - Node reads in context, `context`, `search` and the default root selection include only locked layers. A read that names a building layer, or uses `raw=True`, sees it.
  - A building layer left by an interrupted run stays building and invisible. Its builder, or the module on the builder's behalf with the token, removes it with `discard`. The intake never leaves a building layer.
  - `discard(layer, token)` deletes, in one transaction, the layer's content: its items; the element, join and subtype revision rows written in it; the refs and links attached to those rows; its provenance row, its source rows, and its layer row. It does not delete identity rows or `types` rows, even those this layer created: STORE-007 keeps every identity id for as long as the store exists, so an id is never reused and a reference to it never points at something else. An identity id whose content was discarded has no current row, so reads by that id return not found and nothing in context shows it. A `types` row with no element under it is an ordinary type in the tree.
- Acceptance:
  - An `intake_submit` whose `atomic()` block raises after writing elements leaves no layer, no elements, and `has_intake()` false.
  - A building layer's items are absent from another caller's node read in context and present in a read that names the layer; after `lock` they are present in context.
  - `edit` with a wrong token, and `edit` on a locked layer, are refused and write nothing; `edit` with the token changes the row in place and adds no revision.
  - After `discard` of a building layer that wrote an element, the element's identity row and its `types` row remain, a read by its identity id returns not found, and `list layers` no longer lists the layer.
  - After a successful `intake_submit`, `has_intake()` is true and the node read in context includes the layer.
- Relates to: STORE-013, STORE-012, STORE-017, STORE-018, STORE-024, MAP-040, LAYER-001, LAYER-018, MCP-009, BASE-039.
- Status: confirmed for the intake as one atomic write, and for a knowledge layer being freely editable by its builder until its task is done, then locked, immutable and selectable. The build token, and the operation names, are recommended.

### STORE-033 Every identity id resolves to its kind in one read
- Requirement: One table maps every identity id to its kind, so operations that take a bare id find the right table in one read.
- What this means: `revise`, `retire`, `revisions`, `revision`, `add_ref` and memory operations take an id without saying whether it is an element, join, subtype or item. The store looks up its kind first.
- Why: Asking the caller for the kind would push storage structure onto every agent, and guessing by trying each table is a scan in disguise.
- How it shows: `metaform map revisions <id>` works for any id.
- Build:
  ```sql
  CREATE TABLE identities(
    id   TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK(kind IN ('element','join','subtype','item'))
  );
  ```
  Every create operation inserts its identity row in the same transaction. The identity tables of STORE-007 stay as the foreign-key targets. Items gain `CREATE TABLE item_ids(item_id TEXT PRIMARY KEY, layer_id TEXT NOT NULL REFERENCES layers(layer_id));`, which `items.item_id` and `current_items.item_id` reference.
- Acceptance: For one id of each kind, `revisions(id)` returns that thing's history, and its query plan uses the `identities` primary key.
- Relates to: STORE-007, STORE-017, STORE-024, STORE-025.
- Status: recommended.

### STORE-034 What a revision may change, and what retiring requires
- Requirement: A revision changes only the fields allowed for its kind, and a thing is retired only when nothing current depends on it.
- What this means: A correction is explicit about what it changes. A retype is a revision that changes an element's address. A node that still has current joins or subtypes pointing at it cannot silently disappear from under them.
- Why: A revision format with no rules lets a correction change a join's owner or orphan the joins of a retired element, which breaks the structure that everything reads through.
- How it shows: `metaform map revise <element id> --address code.probe.echo --reason "..."` retypes an element. Retiring an element that still receives a join is refused, naming that join.
- Build:
  - `changes` is a mapping of field name to new value. Allowed fields: element `address`, `name`, `name_length`, `role`, `extra`; join `provider`, `type`, `purpose`, `function`, `relation`, `observation`, `non_goal`, `extra`; subtype `address`, `name`, `name_length`, `role`, `purpose`, `function`, `relation`, `observation`, `extra`; item `value`, `link`, `extra`; property `value`, `extra`. Any other key is refused. `refs` may be given as the complete new list of key and value pairs; when absent, the current refs are carried forward.
  - A revision that changes an element's address writes the `types` rows for the new address, updates `current_elements.address` in the same transaction, and is refused if another current element holds the new address.
  - Retiring an element is refused while any current join has it as receiver or provider. Retiring a join is refused while it has current subtypes. The error names the first dependent and the next step to retire it. Items attached to a retired node stay stored and are returned only by raw reads and by revision history.
- Acceptance:
  - A revise with the key `receiver` is refused.
  - Retyping an element to an address held by another current element is refused and writes nothing.
  - Retiring an element with a current join is refused; after retiring the join, retiring the element succeeds.
- Relates to: STORE-017, STORE-024, MAP-015.
- Status: recommended.

### STORE-035 Context reads: the applying set, the visible set and the starting selection
- Requirement: The store answers, at any address, which transitive items apply there and which are visible there from above, toward the leaves, after selection, starting from the layers toggled on, LAYER-019.
- What this means: LAYER-005 needs two sets at an address: items at the address and its prefixes that apply, and items above it toward the leaves that are visible without applying. Transitive items attached at an element count as attached at that element's current address. Items attached at joins and subtypes do not travel. The starting selection is the layers toggled on for the working context, LAYER-019; when the folder's `--layers` setting is unset, every locked layer that is not hidden starts selected.
- Why: A broad question at `code` must see every medium in use above it without spreading a branch's specifics to its siblings, and each answer must be one indexed read, STORE-005.
- How it shows: `metaform query context code` lists C++ from `code.engine` and Bash from `code.installer` as visible, and neither as applying.
- Build:
  - The starting selection comes from the folder's `--layers` setting, CLI-033, resolved to layer ids with tags expanded through `layer_tags`, STORE-038. No per-project starting selection is stored.
  - Applying set at A: for each prefix P of A, root first, the current properties, STORE-039, attached to the current element whose address is P, and the current items of transitive layers attached there, filtered by the effective selection at A.
  - Visible set at A: the current properties attached to any current element whose address starts with `A.`, and the current items of transitive layers attached at any type or current element whose address starts with `A.`, each filtered by the effective selection at its own address. The descendant read is a primary-key range on `types.address` from `A.` up to but not including `A/`, the next character after the period, joined to `current_items_by_target` and to `current_elements.address`.
  - Unresolved selection: a select or mask row whose layer is hidden or still building is kept and returned by `effective_selection` in an `unresolved` list, and is not applied.
- Acceptance:
  - The C++ and Bash example gives the stated sets.
  - A transitive item attached at the element `code.engine` applies at `code.engine.game`, and after the element is retyped to `code.runtime` it applies at `code.runtime.game` and not at `code.engine.game`.
  - The plans for both sets use `SEARCH` only.
- Relates to: STORE-005, STORE-019, STORE-025, LAYER-005, LAYER-007.
- Status: recommended. Attachment at a type address with no element depends on open question 19. Whether a project also keeps a stored starting selection of its own, used by every folder where `--layers` is unset, is open question 22.

### STORE-036 Re-examination marks
- Requirement: When a revision supersedes a thing that another layer was built from, that layer is marked for re-examination until someone clears the mark.
- What this means: Dependents are re-examined, never rewritten, LAYER-011. The mark says which source changed and when. Clearing it is an explicit act.
- Why: A layer built on a corrected foundation must say so, or agents trust answers derived from something that no longer holds.
- How it shows: After a join in the intake layer is revised, `metaform map layers` shows the challenge layer built from it with a re-examine mark.
- Build:
  ```sql
  CREATE TABLE layer_sources(
    layer_id        TEXT NOT NULL REFERENCES layers(layer_id),
    source_layer_id TEXT NOT NULL REFERENCES layers(layer_id),
    PRIMARY KEY(layer_id, source_layer_id)
  );
  CREATE INDEX layer_sources_by_source ON layer_sources(source_layer_id);
  CREATE TABLE reexamine(
    layer_id        TEXT NOT NULL REFERENCES layers(layer_id),
    source_layer_id TEXT NOT NULL,
    thing_id        TEXT NOT NULL,
    revision        INTEGER NOT NULL,
    PRIMARY KEY(layer_id, thing_id, revision)
  );
  ```
  `layer(...)` takes `sources`, the layer ids it was built from. `revise` and `retire` insert a `reexamine` row for every layer whose sources include the revised thing's layer. `reexamined(layer)` deletes that layer's rows.
- Acceptance: Revising a thing in layer S marks every layer with S as a source, and no other layer; `reexamined` clears it.
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
- What this means: Tags let layers be found and toggled by what they are for, LAYER-019. They are not layer content, so adding or removing a tag is allowed on a locked layer and does not create a revision or touch provenance.
- Why: An orchestrator toggles layers by tag, so finding every layer with a tag must be one indexed read, STORE-005, and a tag must be changeable after a layer is locked without disturbing the locked content.
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
  - `tag(layer, tag)` inserts a row and is a no-op when the row exists; `untag(layer, tag)` deletes it and is a no-op when it is absent. Both work on building and locked layers, need no build token, and are recorded in no revision.
  - `new-layer` accepts an optional list of tags, written in the same transaction as the layer row.
  - Discarding a building layer deletes its `layer_tags` rows with its other content rows, STORE-032.
  - Resolving a `--layers` value: each name is looked up as a layer reference, STORE-013; a name that is not a layer is read as a tag and expands through `layer_tags_by_tag` to every layer carrying it. A name that is neither is an error naming it.
- Acceptance:
  1. Tagging a locked layer adds the tag, and the layer's revision count and provenance row are unchanged.
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
    revision    INTEGER NOT NULL,
    layer_id    TEXT NOT NULL REFERENCES layers(layer_id),
    element_id  TEXT NOT NULL REFERENCES element_ids(element_id),
    value       TEXT NOT NULL,     -- JSON: the property's value
    extra       TEXT,
    supersedes  INTEGER REFERENCES properties(row),
    reason      TEXT,
    evidence    TEXT,
    retired     INTEGER NOT NULL DEFAULT 0,
    UNIQUE(property_id, revision)
  );
  CREATE TABLE current_properties(
    property_id TEXT PRIMARY KEY,
    row         INTEGER NOT NULL UNIQUE REFERENCES properties(row),
    layer_id    TEXT NOT NULL,
    element_id  TEXT NOT NULL
  );
  CREATE INDEX current_properties_by_element ON current_properties(element_id, layer_id);
  CREATE INDEX current_properties_by_layer   ON current_properties(layer_id, element_id);
  ```
  - Ids, revisions, corrections, refs and `extra` follow the same rules as items, STORE-015 and STORE-021. A property written to a building layer is edited or removed in place until the layer is locked, LAYER-018; after that it changes only by correction.
  - The data access object checks that the element exists and refuses any other target. The element's address, through `current_elements`, places the property in the namespace.
  - Written by `add_property`, STORE-024; read through `node`, `layer` and `context`, STORE-025 and STORE-035.
- Acceptance:
  - A property attached to the element `code.installer` applies at `code.installer.script`, is visible at `code`, and is absent at `code.engine`.
  - Adding a property never writes a row to `joins`, and adding one at a type address, a join or a subtype is refused.
- Relates to: MAP-022, LAYER-005, LAYER-016, STORE-008, STORE-010, STORE-015, STORE-024, STORE-035.
- Status: confirmed that properties are their own transitive records attached only to elements. Creating an element at a prefix to hold a property, linked by the namespace tree with no join, is recommended. The table shape is recommended.

### STORE-040 Challenge states and plans
- Requirement: The store keeps each blind-spot challenge's state, open, answered A, B or C, or plan, and every plan, outside the locked blind-spot layer.
- What this means: A challenge is an item in a critic's locked blind-spot layer, LAYER-015. Its answer and its approval come later and from other actors, so they are recorded next to the item and never as edits to the locked layer. A plan is a new function element, with its join, that is either approved from a B challenge or added directly by an agent as a plan. A challenge with no state row is open.
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
  - `answer(item_id, state, link)` writes or replaces the item's row with state A, B or C. It refuses an item that is not in a blind-spot layer, a state of plan, a C without a link to an existing element or join, and an item already approved.
  - `approve(item_id)` requires state B, sets state to plan and the approval time, and writes a `plans` row with source approved for each new function element the challenge carries, with its join.
  - `add_plan(layer, element, join)` writes a `plans` row with source direct; it needs no approval.
  - Reads that return a challenge item, or an element or join listed in `plans`, add its state next to its layer name: open, A, B, C or plan.
- Acceptance:
  - A C answer without a link is refused, and so is `approve` on a challenge that is open or answered A or C.
  - After `approve`, the blind-spot layer's item rows are unchanged, and reads show the challenge and its element as plan.
- Relates to: LAYER-015, LAYER-018, STORE-015, STORE-025, BASE-038, MAP-044.
- Status: recommended.

## Open questions

1. Can two current elements in one project share a type address, for example two photos that are both `media.photo`? The store currently allows one current element per address, because the intake refers to elements by address.
2. Answered: joins carry no role or kind; a join is always a function encounter, and properties are their own records, MAP-022, STORE-039. Whether hard dependency survives in any form is MAP open question 17.
3. Can a subtype own joins of its own after annealing? If yes, a subtype can be a receiver but never a provider, and `joins.receiver` must accept subtype ids. If no, its joins lift to the parent when it is annealed.
4. Can one element be a subtype in two different joins, such as one probe serving two failsafes? The store currently allows it as two subtype rows with separate identity ids. If not, a uniqueness rule on address within `current_subtypes` enforces it.
5. Are a layer's properties fixed for each kind of layer, so memory is always mutable and never transitive, or chosen by a module for each layer it creates?
6. Does hiding follow dependencies between layers, so a layer built from a hidden layer is hidden too? If yes, the store needs one row per source layer of each layer, and re-examination of dependents after a correction uses the same rows.
7. Does each layer declare the fields of its variable, such as imperative, why and evidence for a best practice, so that readers know them, or is an item's value free-form?
8. What does the provenance record hold for a layer written by a person or by a deterministic import, which has no model, prompt or role?
9. When a second run of the same workflow writes to an existing layer, is it the same layer with one provenance record, or a new layer with its own?
10. Can memory create a node that is not already in the map, as the reference server's create operation does? If yes, it would be a new element in the memory layer.
11. Where does a module's item go when it is about no map node, such as the template's greeting history? One option is an element the module's layer creates for itself.
12. Is JSON the exchange document format, or is XML required for any exchange?
13. On import, when a store already holds a thing with the same identity id but different rows, is the incoming version added as a new revision, kept as a separate layer, or reported and skipped?
14. Are stores written by the current chassis branch migrated, or is pre-1.0 data dropped?
15. The directly run wheel's subfolder naming: see BASE open question 2.
16. What merging does when a wheel is installed: see BASE open question 3.
17. Do Type records live in each project store, as STORE-008 has them, or are they shared across projects, as MAP-010 recommends?
18. Must an element created by a layer other than the intake carry a role? MAP-017 requires exactly one role on every element; STORE-009 allows none.
19. Properties attach only to elements, STORE-039, MAP-022. Can any other layer item attach at a type address that no element holds? The `items.target_kind` value `type` stays until this is answered.
20. Answered: a C answer's link is kept with the challenge state, STORE-040.
21. Resolved by E9: `ctx.store`.
22. Does a project keep a stored starting selection of its own, used in every folder where `--layers` is unset, or is the folder's `--layers` setting, with every locked layer as its default, the only starting selection? The spec now has only the setting; the per-project `root_selection` table and the `select-root` and `clear-root` verbs are removed. (STORE-035, LAYER-019, CLI-033)
