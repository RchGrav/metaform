# memory

A memory graph of its own, the MCP reference memory server's, presented at each node of the map and tied to it by joins of type memory.

## Purpose

When the map is wrong or incomplete at a node, an agent records what it learned there in the reference memory server's terms, and the next agent reading that node sees it. The graph is kept apart from the map: a memory entity is never an element and never a namespace segment, and a clear of the project's metaforms keeps it. Memory belongs to no single agent. It ships enabled.

## Template version

Started from template 0.2.0.

## Declaration

`SUPPORTED_OS = ('linux', 'macos', 'windows')`, `DEPENDENCIES = ()`, `SHIPS_DISABLED = False`. `MODULE` declares the nine commands of the reference memory server, `note`, `joins`, `orphaned`, `unjoin` and `graph`, its `node_read` and its `tables`.

## Common base used

`metaform.module` for the declaration, `Context` and `node_read`; `metaform.data` for its tables, `Tables`, `Table`, `Column` and `Index`, reached through `ctx.store.tables()`, and for the memory layer.

## Prompts

`resources/prompts.xml` holds `instructions`, listed in the instructions agents read under "modules available.", MCP-031.

## Verbs

`create_entities`, `create_relations`, `add_observations`, `delete_entities`, `delete_observations`, `delete_relations`, `read_graph`, `search_nodes`, `open_nodes`: the reference's names, arguments and results. Each takes `node`, `element:<address or id>` or `join:<id>`, to act on that node's memories, the entities joined to it and the relations between them; without it, the whole graph. `note` reads or writes a node's one note. `joins`, `orphaned`, `unjoin` and `graph` read and manage the joins and the whole graph; `graph` also says of each join whether its memory shows at its node, as a read of the node shows it, which the web GUI draws from, VIEW-031. Over MCP these are the commands of the tool `memory`.

## Settings

None.

## Events

None of its own. A write to its tables is noted by the chassis as any project-level table's write is, so `map.changed` is fired when the command ends and open pages are told, VIEW-018.

## Sync and async

Every verb is a plain function.

## Layers

`memory`, kind memory, mutable and hideable, with no provenance, made on the first write when the project has a metaform. It holds no memories; memory shows at a node while this layer reaches the node's address, so select, mask, hiding and `--layers` turn it off, LAYER-012. What it held before the graph is carried into the graph and the notes once and left in place.

## Tables

Project-level, in `projects/<project>/modules/memory.sqlite3`, STORE-020: `entities`, `observations`, `relations`, `joins`, `notes` and `carried`, at version 2. Entities, observations and relations are kept as the reference server keeps them, in the order they were made, with no time on them or on the joins; version 1's times are dropped by the chassis's upgrade, which keeps every row. A join of type memory is keyed by the node's namespace address, so a new intake with the same address reconnects it; one whose address the map no longer holds is orphaned and listed by `orphaned`.

## Node read

`node_read` adds under `memory` in `map where` and `map node`: the node's `note`, and while memory shows there, its `entities` and `relations`, and for an element the `joins` it receives and provides that carry memories.

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
metaform memory note element:code.manager.route text="Ask before changing the ejection."
```
