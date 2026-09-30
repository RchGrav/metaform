# memory

Notes agents keep at the map's own nodes, in the reference memory server's operations.

## Purpose

When the map is wrong or incomplete at a node, an agent adds an observation there, and the next agent reads it where it looks. Memory belongs to no single agent. It ships enabled.

## Template version

Started from template 0.2.0.

## Declaration

`SUPPORTED_OS = ('linux', 'macos', 'windows')`, `DEPENDENCIES = ()`, `SHIPS_DISABLED = False`. `MODULE` declares the nine operations of the reference memory server.

## Common base used

`metaform.module` for the declaration and `Context`, `metaform.data` for the memory layer's items.

## Prompts

`resources/prompts.xml` holds `instructions`, `memory is active.`, listed in the instructions agents read under "modules available.", MCP-031.

## Verbs

`create-entities`, `create-relations`, `add-observations`, `delete-entities`, `delete-observations`, `delete-relations`, `read-graph`, `search-nodes`, `open-nodes`. Nodes are written `element:<address or id>` or `join:<id>`; a subtype join is a join, and the element it holds an element. Tools are `memory_<verb>`.

## Settings

None.

## Events

None.

## Sync and async

Every verb is a plain function.

## Layers

`memory`, kind memory, mutable and hideable, with no provenance, made on the first write. An observation is an item at its node; a relation is an item at its `from` node linking to its `to` node.

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
metaform memory add-observations element:code.manager.route "Routes are ejected, never packed on delete."
metaform memory open-nodes element:code.manager.route
```
