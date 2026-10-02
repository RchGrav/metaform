# template

The empty start of every Metaform module. Copy this folder to begin a module; every heading below is one a module's README answers.

## Purpose

What the module is for, in two to four sentences.

## Template version

The template changelog version this module started from: 0.2.0.

## Declaration

`SUPPORTED_OS`, `DEPENDENCIES`, `SHIPS_DISABLED` and `MODULE`, with what each is set to and why.

## Common base used

Which of `metaform.module`, `metaform.settings`, `metaform.data`, `metaform.events` and `metaform.nonce` the module uses, and for what. Through `metaform.nonce` a module hands work to an agent by nonce and closes the nonce when the task is complete, BASE-050; hello's `noncedemo` shows it. Through `metaform.data` a module reads and writes the map's layers and the work records: the condition of an element or a join, a subtype join included, `missing`, `broken` or `exclude`, kept apart from the map with a note and a task, `store.add_work`, `store.edit_work`, `store.finish_work` and `store.work`, MAP-046 and STORE-042; hello's `todo` shows it. Through `metaform.data` a module also declares tables of its own, `Tables`, `Table`, `Column` and `Index`, and reads and writes them in `store.tables()`, STORE-045; hello's `visit`, `note` and `notes` show it. Through `metaform.module` a module adds to the read of a node with `Module(node_read=...)`, a function of the context and the node that returns plain data, shown under the module's id in `map where` and `map node`, or None for nothing, BASE-035; hello's `node_read` shows it.

## Prompts

The prompts in `resources/prompts.xml`, each an element named for the prompt, and where each is served, MCP-031. `instructions` is listed in the instructions agents read under "modules available."; a copy writes its own module name in place of `template`.

## Verbs

Each verb, what it returns, and its CLI form `metaform <id> <verb>` and tool form `<id>_<verb>`.

## Settings

Each setting the module declares, its default, and which verbs read it as a switch.

## Events

The topics the module publishes and those it subscribes to. After any command that changes a project's map, the chassis fires `map.changed` with `project` and `metaform_id`, no id meaning the project's metaforms changed, and the web server does the same after the page's own writes; a module does nothing to announce its writes, and any module can subscribe to it, as the web module does to redraw its open pages, VIEW-018. Work a module does outside a command, in a task it spawned, is announced only when the module publishes `map.changed` itself. Nothing polls for a change, and nothing a person or an agent waits on blocks behind slow work, QUAL-015.

## Sync and async

Which verbs and subscribers are coroutines.

## Layers

The layers the module writes, their mutable and hideable declaration, and their provenance. The tables the module declares in `MODULE.tables`, STORE-045: each table's columns, key, indexes and place, `metaform` beside the map or `project` kept through a clear; the version, and what its `upgrade` moves at each raise; and which verbs read and write each table in `ctx.require_store().tables()`.

## Lifecycle and cleanup

What `start` and `stop` do, the tasks the module spawns, and what unload leaves behind.

## Modules relied on

Other modules this one needs, reached through their verbs and events, never by import.

## Systems supported

The systems in `SUPPORTED_OS`, and any verb that narrows them.

## Resources owned

Files, processes or connections the module owns, and when it releases them.

## Installed and direct wheel

How the module behaves in an installed Metaform and in a directly run wheel.

## Demonstration

A short command sequence that shows the module working.
