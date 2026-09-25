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
    project_id TEXT PRIMARY KEY,
    path       TEXT NOT NULL,          -- absolute, resolved
    path_key   TEXT NOT NULL UNIQUE    -- os.path.normcase(path), for comparison
  );
  CREATE TABLE folders(
    path_key TEXT PRIMARY KEY,         -- os.path.normcase of the resolved folder path
    path     TEXT NOT NULL             -- as resolved, for display
  );
  CREATE TABLE settings(
    scope TEXT NOT NULL,               -- 'global' or a folders.path_key
    key   TEXT NOT NULL,
    value TEXT NOT NULL,               -- JSON encoding of the one value
    PRIMARY KEY(scope, key)
  );
  CREATE TABLE glue(
    scope TEXT NOT NULL,
    key   TEXT NOT NULL,
    PRIMARY KEY(scope, key)
  );
  CREATE TABLE module_state(
    module_id TEXT PRIMARY KEY,
    enabled   INTEGER NOT NULL CHECK(enabled IN (0, 1))
  );
  CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);  -- holds schema_version
  ```
  - A folder row is written the first time a folder-scoped setting is stored for it. Reads never write.
  - A folder's project is its `project` setting when set, otherwise the registered project whose path contains the folder, the deepest match, compared through `path_key`.
  - `module_state` has a row only when a user has enabled or disabled a module. With no row, the module's own declaration decides, so a module that ships disabled stays disabled until enabled, the same three-case pattern as settings.
- Acceptance:
  - A read-only command against a home with no base database creates no file.
  - A project registered as `C:\Work\Proj` is found from the folder `c:\work\proj\src` on Windows, and not from a different case on Linux.
  - A module declared as shipping disabled is off with no `module_state` row, on after `enable`, and back to its declared state after its row is removed.
- Relates to: STORE-001, CLI-013, CLI-014, CLI-021, BASE-017.
- Status: confirmed for projects, folders, settings and glue. `module_state` replacing the current `disabled_modules` table is recommended.

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
- Build: The indexes are listed with each table. The data access object issues only the queries listed in STORE-025, each written against those indexes.
- Acceptance: For every read operation in STORE-025, `EXPLAIN QUERY PLAN` of its SQL contains `SEARCH` on an index or primary key for every table it touches and no `SCAN` of a table. This test fails if a query or an index is changed so that a lookup falls back to a scan.
- Relates to: STORE-004, STORE-025.
- Status: confirmed.

### STORE-006 Writes are atomic and safe with many writers
- Requirement: Every write operation is one transaction, and many processes can write to the same store at once without losing or corrupting data.
- What this means: Each agent's MCP server is its own process, so several processes write to one project store at the same time. A write either lands completely or not at all. An interrupted import or revision leaves the store exactly as it was before it started.
- Why: A store that half-applies a write gives agents a map that is neither the old state nor the new one. Agents trust what they read, so partial state is worse than a failed write.
- How it shows: Two agents adding memories to the same node at the same moment both succeed. Killing a process in the middle of an import leaves the store as it was before the import.
- Build:
  - Every connection sets `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON` and `PRAGMA busy_timeout=5000`.
  - Each data access operation opens `BEGIN IMMEDIATE`, performs all its statements and commits, or rolls back on any error.
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
- Build: Identity ids are random UUID4 strings in lowercase hex without dashes, generated by the data access object. Identity tables hold one row per identity id for as long as the store exists:
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
- What this means: The namespace is a tree of types. `code.engine.game.fps` is a type, and so are `code.engine.game`, `code.engine` and `code`, each a complete type in its own right. Writing any address writes the rows for it and for each of its prefixes that is missing. Layer items can attach to any address, whether or not an element has that type, and no address is refused for being invalid.
- Why: Selection, masking and transitive layers travel the type tree from trunk to leaf, so the tree must be stored and walkable. Knowledge layers may link any namespace address, so the store records addresses as given and leaves typology judgments to the agents and workflows that make them.
- How it shows: Attaching a best practice to `code.engine` makes it visible, through the transitive rule, at every element whose address starts with `code.engine.`.
- Build:
  ```sql
  CREATE TABLE types(
    address TEXT PRIMARY KEY,
    parent  TEXT REFERENCES types(address)   -- NULL for a root such as 'code'
  );
  CREATE INDEX types_by_parent ON types(parent);
  ```
  The parent of an address is the address with its last dot-separated segment removed. Rows are inserted with `INSERT OR IGNORE`, root first.
- Acceptance:
  - Writing an element at `code.engine.game.fps` into an empty store creates exactly four `types` rows with the right parents.
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
- Acceptance:
  - Looking up an element by address after it has three revisions returns the third, through `current_elements`.
  - Adding a second element at an address that a current element already holds returns the existing element's id instead of creating a second one.
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
    role        TEXT,                                -- open question 2
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
  - A join may have subtypes at both ends at once.
- Acceptance:
  - A subtype written at the provider end of a join is returned by the subtypes read for that join and end, and by no element or join read.
  - No read that returns elements, or joins by receiver or provider, ever returns a subtype.
  - Writing an item attached to a subtype succeeds and is returned by the node read for that subtype.
- Relates to: STORE-010, STORE-015, MAP-030, MAP-031, MAP-032.
- Status: confirmed for placement and storage. Open questions 3 and 4.

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
- Acceptance:
  - A join with refs `path=a` and `path=b`, revised to keep only `path=b`, reads back with one ref at the current revision and two at the old one.
- Relates to: STORE-004, STORE-017, STORE-025, MAP-021.
- Status: recommended. The lookup by key and value is required by MAP-021.

## Layers

### STORE-013 Layers and their declared behavior
- Requirement: Each layer is a row carrying its name, its module and its declared behavior: mutable or immutable, hideable, and transitive.
- What this means: Everything Metaform holds is a layer, the intake's map included. A layer carries one inferred variable. Declaring behavior on the layer lets the store apply revisions, visibility and propagation the same way for every layer.
- Why: When every layer attaches the same way and declares its behavior, layers compose, and a module can add one without knowing about any other. No module rebuilds revision, hiding or propagation rules of its own.
- How it shows: `list layers` shows each layer with its module and its three properties.
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
    created    TEXT NOT NULL                          -- LAYER-001: creation time, ISO 8601 UTC
  );
  CREATE TABLE hidden_layers(layer_id TEXT PRIMARY KEY REFERENCES layers(layer_id));
  ```
  - A layer's properties are set when it is created and never change.
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
- What this means: An item attaches to a type address, an element, a join or a subtype. Its value is that layer's variable at that node, such as one best practice, one challenge, one verdict or one memory observation. The optional link points at another node. A C verdict links the challenge to the element or join that already handles it, and a memory relation links one node to another. Links are items, so the whole structure stays navigable from any node, and links may form cycles.
- Why: One variable per layer is what lets any set of layers be selected together. Links as items mean a verdict points at the real node instead of copying it, and following links backward from the map shows every challenge a node already covers.
- How it shows: Reading the challenge layer at `code.guard.switch.gateway` by incoming links lists every proposal judged as already handled there.
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
  - `value` holds the item's own fields as one JSON value. The store does not judge the value's content.
- Acceptance:
  - All items of a layer, all items at a node, and all items linking to a node are each returned by one read using the matching index.
  - An item linking from A to B and another from B to A both store and both read back.
- Relates to: STORE-004, STORE-005, STORE-020, LAYER-003, LAYER-015.
- Status: confirmed for attachment to elements, joins and subtypes, and for links. Attaching an item at a type address with no element is used by LAYER-005 and MAP-011 but is not in LAYER-003's list of attachment targets; see open question 19. Whether a C verdict's link is stored in `link_kind` and `link_id`, as here, or inside the item's value, as LAYER-015 states, is open question 20. The fields inside a layer's value are open question 7.

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
  - No `UPDATE` or `DELETE` statement in the data access object targets `elements`, `joins`, `subtypes`, or the `items` rows of an immutable layer.
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
  Resolution for an address: start from the root selection, all layers unless the read supplies one; for each prefix from the root segment to the full address, remove the layers masked there, then add the layers selected there; finally remove hidden layers. Each step is one primary-key range read on `selections`. The resolved set is what every node read uses.
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
  - The default memory layer is created on first use: mutable, hideable, not transitive, with no provenance row.
  - Search runs over the memory layer's item values through an SQLite FTS5 table kept in step with `items` by triggers:
    ```sql
    CREATE VIRTUAL TABLE item_text USING fts5(value, content='items', content_rowid='row');
    ```
  - Open nodes: the node's identity read plus two index reads, items at the node and items linking to it.
- Acceptance:
  - Adding an observation to a node that has no memories writes one item row and no other row.
  - A relation from A to B appears when opening A and when opening B.
  - Search finds an observation by a word in it, on Linux, macOS and Windows.
- Relates to: STORE-015, STORE-018, LAYER-012, LAYER-013, REQ-126 as corrected, MCP.
- Status: confirmed for the interface and the nodes. FTS5 for search is recommended. Whether memory can create a node that is not already in the map is open question 10.

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
- Build: `Context.data`, the per-module folder under the home, is removed from the common base. The template module's history becomes items in a mutable layer it declares.
- Acceptance: After exercising every template verb, the home contains no file outside the base database and project stores.
- Relates to: STORE-023, STORE-024, BASE-005, BASE-019.
- Status: recommended. Where an item goes when it is about no map node is open question 11.

## The data access object

### STORE-023 The data access object is the only way to the data
- Requirement: The chassis provides one data access object, imported by every module from the common base, and it is the only code that opens a store or issues SQL.
- What this means: A module never touches SQLite, table names or files. It asks the data access object for things by address or identity id and gets objects back. The CLI and the MCP module use the same object, so every surface reads and writes identically.
- Why: A module built on the base cannot corrupt the map, cannot drift from the CLI or MCP, and keeps working when the storage underneath changes. Layers only compose if every module writes them the same way.
- How it shows: A module written from the template stores and reads its data with no import of `sqlite3`.
- Build: The public import is `from metaform.data import Store, Node, StoreError`. A verb receives the store for its folder's project as `ctx.store`. `Store(project_id)` opens that project's store. Objects returned are frozen dataclasses: `Element`, `Join`, `Subtype`, `Item`, `Layer`, `Provenance`, `Revision`. A `Node` is `(kind, id)` where kind is `type`, `element`, `join` or `subtype` and id is an address or identity id.
- Acceptance:
  - No module under `src/metaform/modules` imports `sqlite3`.
  - The CLI verb and the MCP tool for the same read return equal results for the same arguments.
- Relates to: STORE-022, STORE-024, STORE-025, BASE-004, MCP-003.
- Status: confirmed.

### STORE-024 Write operations
- Requirement: The data access object offers exactly these write operations, each one transaction.
- What this means: These are the operations the intake, knowledge modules, critics and memory use to build and keep the map and its layers.
- Why: A small fixed set of writes, each matching a thing in the design, means every writer builds the same shapes and every shape has one way to be built.
- How it shows: An agent running the intake through MCP builds the whole map with `layer`, `add_element`, `add_join`, `add_subtype` and `add_ref`.
- Build:

  | Operation | Inputs | Output | Errors |
  |---|---|---|---|
  | `layer(name, module, variable, *, mutable, hideable, transitive, provenance=None, result_id=None)` | provenance is a mapping with module, workflow, prompt, model, role, blinded | `Layer`; the existing layer when the name exists with the same properties | name exists with different properties; empty variable; provenance missing for a layer other than memory |
  | `add_element(layer, address, *, name=None, name_length=None, role=None, extra=None)` | address as given | `Element`; the existing current element when the address is held | layer unknown |
  | `add_join(layer, receiver, provider, *, purpose, function, relation, observation, non_goal=None, type='purpose', role=None, extra=None)` | receiver and provider as address or element id | `Join` | receiver or provider is not an element; either is a subtype |
  | `add_subtype(layer, join, end, address, *, purpose=None, function=None, relation=None, observation=None, name=None, name_length=None, role=None, extra=None)` | end is `receiver` or `provider` | `Subtype` | join unknown; end not one of the two |
  | `add_ref(owner, key, value)` | owner is an element, join, subtype or item id | the ref, attached to the owner's current revision | owner unknown |
  | `add_item(layer, target, value, *, link=None, extra=None)` | target and link are `Node`s | `Item` | target or link unknown for identity kinds |
  | `update_item(item, value)` | | `Item` | layer is immutable |
  | `delete_item(item)` | | nothing | layer is immutable |
  | `revise(thing, changes, *, reason, evidence=None)` | thing is an element, join, subtype or item id | the new revision | layer is mutable; receiver change requested |
  | `retire(thing, *, reason, evidence=None)` | | the retiring revision | layer is mutable |
  | `select(address, layer)`, `mask(address, layer)`, `clear(address, layer, kind)` | | nothing | layer unknown |
  | `hide(layer)`, `unhide(layer)` | | nothing | layer not hideable |

- Acceptance: For each operation, one test performs it and checks the rows it must write and that no other table changed. Each listed error is produced once and writes nothing.
- Relates to: STORE-009 to STORE-022, STORE-026.
- Status: confirmed for the set of things written. Operation names and signatures are recommended. The How it shows line assumes the intake writes record by record, which is open, per MAP-040 and MAP open question 9.

### STORE-025 Read operations
- Requirement: The data access object offers exactly these reads, each answered through indexes.
- What this means: Each read is one question the design asks.
- Why: Agents navigate by meaning, and each question must go straight to its answer, STORE-005.
- How it shows: `metaform where`, `metaform element`, `metaform layer` and the matching MCP tools each call one of these.
- Build:

  | Operation | Answers | Index used |
  |---|---|---|
  | `element(ref)` | one element by address or id, with refs | `current_elements` address or primary key; `refs_by_owner` |
  | `joins(element, as_='receiver' or 'provider')` | the joins an element owns, or provides for | `current_joins_by_receiver`, `current_joins_by_provider` |
  | `identity(element)` | C(T): every current join where it is the provider | `current_joins_by_provider` |
  | `subtypes(join, end=None)` | the subtypes at one or both ends of a join | `current_subtypes_by_join_end` |
  | `where(address)` | the element, or the join and end holding a subtype, at an address | `current_elements`, `current_subtypes_by_address` |
  | `children(address)` | the next types down the tree | `types_by_parent` |
  | `layer_items(layer, target=None)` | all of a layer, or a layer at one node | `current_items_by_layer` |
  | `node(target, selection=None)` | every visible layer's items at one node, grouped by layer, after selection | `current_items_by_target`; `selections` primary key |
  | `links_to(target, layer=None)` | items in any layer linking to a node | `current_items_by_link` |
  | `citing(key, value)` | every current element, join, subtype and item whose refs hold that key and value, per MAP-021 | `refs_by_key_value` |
  | `revisions(thing)` | every revision with reason and evidence | `UNIQUE(id, revision)` |
  | `revision(thing, n)` | one named revision | `UNIQUE(id, revision)` |
  | `layers()`, `provenance(layer)` | the layers with properties; one layer's provenance | primary keys |
  | `effective_selection(address, root=None)` | the resolved layer set at an address | `selections` primary key |
  | `search(text, layer=None)` | items whose value matches | `item_text` |

- Acceptance: STORE-005's plan test covers every row of this table.
- Relates to: STORE-005, STORE-012, STORE-019, MAP-001, MAP-021, CLI, MCP.
- Status: confirmed for the questions answered. Names and signatures are recommended.

### STORE-026 Errors name one next step and never judge content
- Requirement: A data access error states what is wrong and names one next command, and the store never refuses a write because of what its text says.
- What this means: Errors come only from the shape: a reference to something that does not exist, a subtype used as a join end, an in-place change to an immutable layer, a revision to a mutable one, hiding a layer that is not hideable. Wording, purpose quality and typology are never checked by the store.
- Why: A check that rejects inference sends agents into retry loops. An agent-built check once turned a five-minute intake into 456 minutes and $750. The shape enforces itself, and nothing gates inference. An error that names the next command keeps an agent on the surface instead of sending it into the source.
- How it shows: `add_join` with an unknown provider answers: `code.probe.echo is not an element in this project. Next: metaform map element add code.probe.echo`.
- Build: `StoreError(message, next_step)` subclasses the chassis `Stop`. SQLite constraint errors are caught inside the data access object and mapped to a `StoreError` with the next step for that operation. No other exception type leaves the data access object.
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
  - The document is JSON: `{"metaform_export": 1, "schema_version": N, "types": [...], "layers": [...], "provenance": [...], "elements": [...], "joins": [...], "subtypes": [...], "refs": [...], "items": [...], "selections": [...], "hidden": [...]}`. Each list holds one object per row, including every revision and the current pointer flag.
  - Import runs in one transaction, STORE-006. Importing a document into a store that already holds the same identity ids with identical rows changes nothing.
- Acceptance:
  - Export, import into an empty home, export again: the two documents are identical.
  - An import killed partway leaves the target store unchanged.
- Relates to: STORE-006, STORE-007, STORE-021, BASE-002, BASE-025.
- Status: confirmed for the requirement. JSON as the document format is recommended; see open question 12. Import into a store holding different rows with the same identity ids is open question 13.

### STORE-028 Query goes through the read operations
- Requirement: Every query surface, the CLI, MCP and modules, answers through the read operations of STORE-025, and there is no general SQL surface.
- What this means: The chassis runs 100 percent on its own and can query its data from the CLI. Those queries are the design's own questions, not free SQL.
- Why: Free SQL would tie every caller to the table layout and bypass selection and hiding, so an excluded layer could leak into what an agent reads.
- How it shows: `metaform layer challenge.blind --at code.manager.route` returns the same items as the MCP tool, with selection applied.
- Build: Each CLI query verb and each MCP read tool calls exactly one read operation, or a fixed composition of them documented with that verb.
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

## Open questions

1. Can two current elements in one project share a type address, for example two photos that are both `media.photo`? The store currently allows one current element per address, because the intake refers to elements by address.
2. Does a join carry a role of hard dependency, property or supportive as its own field? The Foundation names these roles in the join. The Canonical Intake schema does not emit one. The `role` column is kept until this is settled.
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
19. Can a layer item attach at a type address that no element holds? LAYER-005 and MAP-011 attach practices at addresses such as `code.engine`, while LAYER-003 lists only elements, joins, subtypes, and new elements and joins as targets.
20. Is a C verdict's link to the handling element or join stored in the item's link fields, as STORE-015 has it, or inside the item's value, as LAYER-015 states?
21. The verb context attribute that carries the data access object: `ctx.store`, as STORE-023 has it, or `Context.data` turned into the store, as the chassis section first stated?
