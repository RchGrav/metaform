# memory

A memory graph of its own, the MCP reference memory server's, presented at each node of the map and tied to it by joins of type memory.

## Purpose

When the map is wrong or incomplete at a node, an agent records what it learned there in the reference memory server's terms, and the next agent reading that node sees it. The graph is kept apart from the map: a memory entity is never an element and never a namespace segment, and a clear of the project's metaforms keeps it. Memory belongs to no single agent. It ships enabled.

## Template version

Started from template 0.2.0.

## Declaration

`SUPPORTED_OS = ('linux', 'macos', 'windows')`, `DEPENDENCIES = ()`, `SHIPS_DISABLED = False`. `MODULE` declares the nine canonical graph commands plus `read_unread`, `join`, `note`, `joins`, `orphaned`, `unjoin`, `rekey`, `graph`, `lock`, `unlock` and `watch`. It contributes node reads/counts, item reads and tables. Its public providers are `memory.note(project, node)`, `memory.prompt(project, address=None)`, `memory.revision(project, address, provider='')` and `memory.record(ctx, address, entities)`, which writes another module's own record of what happened at an Address as `create_entities` with `node=element:<address>` writes it, under the same rules, naming the calling module as its writer; roundtables keeps a table's outcome with it.

## Common base used

`metaform.module` for the declaration, `Context` and `node_read`; `metaform.data` for its tables, `Tables`, `Table`, `Column` and `Index`, reached through `ctx.store.tables()`, and for the memory layer.

## Prompts

`resources/prompts.xml` holds `memory:instructions`, the authored functional memory maintenance instructions, served through the prompt store while preserving selected edits and source history. `memory_prompt` fills `{project}` and `{element}` if a selected version uses them; `{this}` retains its existing linked-subject meaning. The earlier Axiom text remains readable in prompt history. Shared context receipts suppress unchanged memory instructions across inline startup and resource reads. `memory:counts` receives actual `total`, `unread`, `updated` and `read_unread` bindings; counts never acknowledge a memory body.

## Verbs

`create_entities`, `create_relations`, `add_observations`, `delete_entities`, `delete_observations`, `delete_relations`, `read_graph`, `search_nodes`, `open_nodes`: the reference's names, arguments and results. Each takes `node`, `element:<address>`, or `receiver` and `provider`, a purpose's two addresses, with `address` for a part inside it, to act on that node's memories: a read returns the entities joined to it and every relation with an end among them, so a relation across Addresses shows from both ends (CTX-025); a write names an entity anywhere in the graph, whoever wrote it, and only a name the graph lacks stops it, with the reference's `Entity with name <name> not found` (CTX-022). Without it, the whole graph. `note` reads a node's one note, the person's, which only the web page writes; it takes `node` first, and `provider` beside it names the purpose `node` holds as receiver, with `address` for a part inside it. `joins`, `orphaned`, `unjoin` and `graph` read and manage the joins and the whole graph; `graph` also says of each join whether its memory shows at its node, as a read of the node shows it, which the web GUI draws from, VIEW-031. Over MCP these are the commands of the tool `memory`.

When a correction replaces an address, `metaform memory rekey <old-address> <new-address>` transfers memory attachments and notes by replacing that exact address in their receiver and provider fields. The old address may already be absent from the map. Descendant addresses stay as they are. The command keeps memory join ids, the graph's entities, observations and relations, and each note's text, author and time. It returns the number of joins and notes changed. Existing destination key collisions roll back the whole transfer, leaving both addresses' memory intact. A locked memory's joins stay where they are and are listed under `locked`. When `map refine address=<old> to_address=<new>` renames an element or merges it into another, the module's `map.moved` subscription does the same transfer itself, as a merge: a memory already joined at the new address keeps one join, and two notes are joined as paragraphs, so nothing is orphaned or copied.

`watch`, on Linux, macOS and BSD: the citation watcher, one process per project, which `web start` starts, detached, for each project whose memories cite files, through its `web.started` subscription. No Metaform event says a project file changed (`map.changed` follows writes to the map), so it asks the system: inotify on each folder holding a cited file, or kqueue on each such folder and file, a missing folder watched through the nearest one above it. Each time a cited file changes it works out whether each citation of it holds and stores the result; a `map.changed` from another process naming `memory.citations` adds the folders of new citations. Its record, lock and log are in `run/memory/<project>.json`, `.lock` and `.log`. While it holds its lock a read looks each result up and reads no file; with none running a read stats each cited file, uses the stored result of one that is as it was when worked out, and works out the rest itself, each file split once and each window of the cited span digested once, so a moved citation is found in one pass over the file. A moved citation's reason names the line its text now stands at; that line is left out of what identifies the delivered body and of whether a stored result changed, so an edit above the cited text announces no change and hands no agent the memory again.

`lock <name>` and `unlock <name>`, CTX-023: a locked memory is read by every agent and changed by none. `add_observations`, `delete_observations`, `delete_entities` and `create_entities` of its name leave it as it is and name it (`Deleted 0 of 1 entities. Locked: <name>`); `unjoin` of its join is refused with the reason; a relation may be made to it, and one that touches it is not deleted by `delete_relations`. `graph` and the read at `metaform://<address>#<n>` mark it `locked`. Only the person locks and unlocks: the verbs are on the command line and the page's memory panel, never MCP tools, and refused to a command an agent runs (`metaform.module.agent_caller`).

`create_entities` skips existing names, including their observations, citations and index associations. `add_observations` extends existing knowledge. `join entity=<name> node=element:<address>` associates an existing entity with another functional entry without copying it. The three canonical delete operations maintain unlocked knowledge directly under the configured controls. Deleting an entity removes its observations, citations, incident relations and functional index associations. Locks continue to protect their entities and associations.

`read_unread` lists unread memories by `name`, `entityType`, `title` and one-line `why`, limited to 160 characters per title and reason. The reason uses the stored why, falling back to the first observation line. It returns applicable withdrawals without memory bodies. Listing never acknowledges an entity or relation body. Search using the task's own words at its functional node, then open relevant matches. Use `read_graph` only when the whole graph is needed. `read_graph`, `search_nodes`, `open_nodes` and item reads remain available for inspection and record the exact bodies they return. One entity indexed at two functional entries shares a receipt; different names remain distinct even with identical observations. MCP response shaping acknowledges only complete bodies that survived shaping. A later concurrent revision stays unread. Completed compaction advances the shared epoch and makes current grounding eligible again.

## Atomic projection

`memory_apply` applies one bounded canonical batch after comparing the exact named target's digest.
It is declared with the remove effect, so normal destructive-operation controls also govern batches.
The command accepts `node`, `entityNames`, `expectedDigest`, `mutationId`, `mutations`.
It returns `mutationId`, `requestHash`, `beforeDigest`, `afterDigest`, `applied: true`, `receiptId`.
The receipt confirms acceptance even when canonical operations change nothing.

Each mutation has `op` plus its canonical argument:

| op | argument |
| --- | --- |
| create_entities | entities |
| delete_entities | entityNames |
| add_observations | observations |
| delete_observations | deletions |
| create_relations | relations |
| delete_relations | relations |
| join | entity |
| unjoin | id |

Payload members retain their canonical shapes, including optional titles, reasons and citations.
Every entity name and relation endpoint must appear in `entityNames`.
Creates skip existing names. Extend existing entities with `add_observations`.
New entities join `node`. Explicit joins index existing entities there.
Unjoin only detaches associations at `node`. Locks remain enforced.
The caller's folder project bounds every operation. Project overrides and extra mutation fields fail.

Limits are 262144 UTF-8 JSON bytes, 128 operations, 256 unique nonempty target names,
1000 total array members including nested arrays, 256 UTF-8 bytes for `mutationId`.
Malformed requests return `MEMORY_INVALID`, bounds return `MEMORY_LIMIT`, scope violations return
`MEMORY_SCOPE`, locked mutations return `MEMORY_LOCKED`.

The digest is lowercase SHA-256 of UTF-8 JSON with recursively sorted object keys, literal Unicode,
no insignificant whitespace. String ordering follows Unicode code points.
The payload has `node: {receiver, provider}`, `entities`, `relations`, `joins`.
Entities sort by name. Each uses its canonical `name`, `entityType`, sorted `observations`, plus sorted
`cites` when present. Missing names use `{name, absent: true}`.
Relations include all incident relations, sorted by `(from, to, relationType)`.
Joins include every index of named entities as `{entity, receiver, provider}`, sorted by those fields.
An element's provider is the empty string. Ordering, provenance, title, why, locks and receipt metadata
are excluded. Obtain canonical entities/incident relations with `open_nodes` without a node filter,
including names absent from that read, and associations with `joins entity=<name>`.
Request hashes use the same encoding on the five supplied fields, sorting only `entityNames`.
Operation order and payload array order remain significant.

A digest mismatch returns `MEMORY_CONFLICT`, includes the current digest, and writes nothing.
The same mutation ID and request hash replay the original stored receipt even after later memory or map changes.
Reusing an ID with changed content returns `MEMORY_MUTATION_ID_REUSED`.
Comparison, graph changes, index joins and receipt share one project-table write transaction inside
`Store.atomic()`. Project tables do not enlist in the map transaction, so the batch retains one
`TableTx` throughout. Canonical graph helpers maintain changes and withdrawals within that transaction.
The existing store relay notes notifications after commit. Failed batches emit nothing.
The memory layer and authored-body acknowledgments follow a successful commit.

Project-level `apply_receipts` stores integration metadata outside the memory graph.
Table version 11 adds this table without changing the compatibility floor of 9: older writers can still
read/write graph tables, while only version 11 supplies atomic batch receipts.

## Settings

None.

## Events

A graph mutation uses the existing `map.changed` relay with `memory.changed`, affected `memory:<address>` kinds and the session IDs that already encountered those functional entries. No notice is pushed to any agent when memory changes (2026-10-19, code.dispatcher.agent#72): an agent is told of unread memory only when it reads the node it works on, as one line naming the unread count there and the `read_unread` title-list call, with selective search/open guidance and memory upkeep; nothing is said there when all is read. Being told does not clear body unread state. Entry revisions also drive MCP resource updates and map summaries when an edit or deletion leaves item numbers and totals unchanged. Unrelated events are filtered before reads.

## Sync and async

Every verb is a plain function.

## Layers

`memory`, kind memory, mutable and hideable, with no provenance, made on the first write when the project has a metaform. It holds no memories; memory shows at a node while this layer reaches the node's address, so select, mask, hiding and `--layers` turn it off, LAYER-012. What it held before the graph is carried into the graph and the notes once and left in place.

## Tables

Project-level tables are `entities`, `observations`, `relations`, `joins`, `notes`, `carried`, `citations`, `encounters`, `entry_revisions` and `withdrawals`. Version 9 requires version 9 writers because earlier code does not maintain content-change delivery. Existing graph, note, citation and lock records migrate intact. `encounters` keeps functional entry registrations per actual session and shared epoch; `entry_revisions` identifies content changes; `withdrawals` retains removed identities, not copied memory bodies. Authoritative delivery receipts live in the agents module's shared ledger.

Citation evidence and stale checks keep their existing behavior. A citation may name `path:line`, `path:start-end`, `path:symbol` or a path relative to the project. A citation is checked against its file as it read when the citation was last written: giving it again in a write keeps it as the file reads then, and `add_observations` that adds to a memory does the same for each whole file the memory cites, so a memory brought up to date after its file changed is not stale; a cited line span moves only when given again. Observation and association author/session fields remain available for provenance. Associations stay keyed by functional addresses, so an intake at the same address reconnects them and `orphaned` lists absent entry points.

Local graph reads resolve visibility and functional joins before materializing bodies. Named reads materialize only selected entities and their incident relations. Explicit whole-graph reads stay complete.

## Node read

`node_read` adds the person's note and applicable memory bodies to `map node` and `map where contents=true`; agent contexts receive unread titles and one-line reasons, with bodies available through `search_nodes` and `open_nodes`. Join entry points retain their receiver/provider identity. `node_count` reports totals, actual unread and updated identities, stale evidence and notes, without acknowledging body receipt. The existing memory-layer visibility, selection and masking rules determine what applies.

## Lifecycle and cleanup

No `start` or `stop`, and no tasks.

## Modules relied on

The agents module supplies the public shared epoch and context-receipt service. Dispatch and MCP consume memory providers through the module surface.

## Systems supported

Linux, macOS and Windows.

## Resources owned

None; every read and write goes through the data access object.

## Installed and direct wheel

The same in both.

## Demonstration

```
metaform memory create_entities '[{"name":"route ejection","entityType":"behavior","observations":["Routes are ejected, never packed on delete."]}]' node=element:code.manager.route
metaform memory open_nodes '["route ejection"]' node=element:code.manager.route
metaform map where code.manager.route
metaform memory note element:code.manager.route
```
