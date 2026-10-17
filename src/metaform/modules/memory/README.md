# memory

A memory graph of its own, the MCP reference memory server's, presented at each node of the map and tied to it by joins of type memory.

## Purpose

When the map is wrong or incomplete at a node, an agent records what it learned there in the reference memory server's terms, and the next agent reading that node sees it. The graph is kept apart from the map: a memory entity is never an element and never a namespace segment, and a clear of the project's metaforms keeps it. Memory belongs to no single agent. It ships enabled.

## Template version

Started from template 0.2.0.

## Declaration

`SUPPORTED_OS = ('linux', 'macos', 'windows')`, `DEPENDENCIES = ()`, `SHIPS_DISABLED = False`. `MODULE` declares the nine commands of the reference memory server, `note`, `joins`, `orphaned`, `unjoin`, `rekey`, `graph`, `lock`, `unlock` and `watch`, its `node_read`, its `tables`, and `provides` `memory.note`: `person_note(project, node)`, the person's note at a node whole or None, which dispatch's hand-off carries; and `memory.prompt`: `memory_prompt(project, address=None)`, the owner's memory prompt filled for an element, which dispatch sends in a worker's first turn, CTX-028.

## Common base used

`metaform.module` for the declaration, `Context` and `node_read`; `metaform.data` for its tables, `Tables`, `Table`, `Column` and `Index`, reached through `ctx.store.tables()`, and for the memory layer.

## Prompts

`resources/prompts.xml` holds `instructions`, the owner's memory prompt word for word (CTX-026), at the address `prompt.memory:instructions`, served through the prompt store so an edit saved there is what agents receive, and `instructions_unassigned`, line 2's bullet for an agent with no element (CTX-027). `memory_prompt` fills `{project}`, `{this.address}` and `{this.name}`. The Axiom text the element held until 2026-10-15 is in `resources/instructions-2026-10-11.axiom`, never sent: a home that never served the element keeps it as the prompt's version 1, so it stays readable as the earlier version. `metaform_instructions module=memory` still returns the element unfilled, since the chassis reads module instructions outside the prompt store. The recording lines (`orient`, `connect`, the verb descriptions) split memory, what happened in the work, from knowledge, what is true of the project: drafts awaiting the owner's approval, CTX-029.

## Verbs

`create_entities`, `create_relations`, `add_observations`, `delete_entities`, `delete_observations`, `delete_relations`, `read_graph`, `search_nodes`, `open_nodes`: the reference's names, arguments and results. Each takes `node`, `element:<address>`, or `receiver` and `provider`, a purpose's two addresses, with `address` for a part inside it, to act on that node's memories: a read returns the entities joined to it and every relation with an end among them, so a relation across Addresses shows from both ends (CTX-025); a write names an entity anywhere in the graph, whoever wrote it, and only a name the graph lacks stops it, with the reference's `Entity with name <name> not found` (CTX-022). Without it, the whole graph. `note` reads a node's one note, the person's, which only the web page writes; it takes `node` first, and `provider` beside it names the purpose `node` holds as receiver, with `address` for a part inside it. `joins`, `orphaned`, `unjoin` and `graph` read and manage the joins and the whole graph; `graph` also says of each join whether its memory shows at its node, as a read of the node shows it, which the web GUI draws from, VIEW-031. Over MCP these are the commands of the tool `memory`.

When a correction replaces an address, `metaform memory rekey <old-address> <new-address>` transfers memory attachments and notes by replacing that exact address in their receiver and provider fields. The old address may already be absent from the map. Descendant addresses stay as they are. The command keeps memory join ids, the graph's entities, observations and relations, and each note's text, author and time. It returns the number of joins and notes changed. Existing destination key collisions roll back the whole transfer, leaving both addresses' memory intact. A locked memory's joins stay where they are and are listed under `locked`.

`watch`, on Linux, macOS and BSD: the citation watcher, one process per project, which `web start` starts, detached, for each project whose memories cite files, through its `web.started` subscription. No Metaform event says a project file changed (`map.changed` follows writes to the map), so it asks the system: inotify on each folder holding a cited file, or kqueue on each such folder and file, a missing folder watched through the nearest one above it. Each time a cited file changes it works out whether each citation of it holds and stores the result; a `map.changed` from another process naming `memory.citations` adds the folders of new citations. Its record, lock and log are in `run/memory/<project>.json`, `.lock` and `.log`. While it holds its lock a read looks each result up and reads no file; with none running a read stats each cited file, uses the stored result of one that is as it was when worked out, and works out the rest itself, each file split once and each window of the cited span digested once, so a moved citation is found in one pass over the file.

`lock <name>` and `unlock <name>`, CTX-023: a locked memory is read by every agent and changed by none. `add_observations`, `delete_observations`, `delete_entities` and `create_entities` of its name leave it as it is and name it (`Deleted 0 of 1 entities. Locked: <name>`); `unjoin` of its join is refused with the reason; a relation may be made to it, and one that touches it is not deleted by `delete_relations`. `graph` and the read at `metaform://<address>#<n>` mark it `locked`. Only the person locks and unlocks: the verbs are on the command line and the page's memory panel, never MCP tools, and refused under an agent's `METAFORM_ROLE`.

## Settings

None.

## Events

None of its own. A write to its tables is noted by the chassis as any project-level table's write is, so `map.changed` is fired when the command ends and open pages are told, VIEW-018.

## Sync and async

Every verb is a plain function.

## Layers

`memory`, kind memory, mutable and hideable, with no provenance, made on the first write when the project has a metaform. It holds no memories; memory shows at a node while this layer reaches the node's address, so select, mask, hiding and `--layers` turn it off, LAYER-012. What it held before the graph is carried into the graph and the notes once and left in place.

## Tables

Project-level, in `projects/<project>/modules/memory.sqlite3`, STORE-020: `entities`, `observations`, `relations`, `joins`, `notes`, `carried` and `citations`, at version 8, readable by code from version 7, which knows the lock: `entities` keeps `locked_by` and `locked_at`, empty while unlocked, CTX-023. A memory may cite its evidence with `cite` on `create_entities` or `add_observations`, `path:line`, `path:start-end`, `path:symbol` or a path, relative to the project's folder; the write refuses a citation that names nothing there. `citations` keeps what the cited lines read as, hashed, with the file's size and time, and, from version 8, `stale`, `checked_size` and `checked_mtime`: whether the citation holds as last worked out, and the file's size and time it was worked out against. A memory whose evidence no longer matches is said to be stale, with why, in the read, at `metaform://<address>#<n>` and in the node's counts. Over MCP a write answers one line with each memory's `<address>#<n>`, not the reference's result. Observations and joins keep `by`, who wrote them, and `session` and `at`, the agent session that wrote them and when, so the counts can say which memories the last session at a node wrote, MCP-039. Entities, observations and relations are kept as the reference server keeps them, in the order they were made, with no time on them or on the joins; version 1's times are dropped by the chassis's upgrade, which keeps every row. A join of type memory is keyed by the node's namespace address, so a new intake with the same address reconnects it; one whose address the map no longer holds is orphaned and listed by `orphaned`.

## Node read

`node_read` adds under `memory` in `map node` and in `map where` with `contents=true`: the node's `note`, and while memory shows there, its `entities` and `relations`, and for an element the `joins` it receives and provides that carry memories. `node_count` tells an agent orienting on a node, in `map where`, the ticket read and dispatch's hand-off, how many memories are joined at the node and at each direct neighbour, how many of them the last session there wrote, and whether the person left a note, with the `counts` and `note_counts` prompts naming the calls that read them, MCP-039; never what they say.

## Lifecycle and cleanup

No `start` or `stop`, and no tasks.

## Modules relied on

None.

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
