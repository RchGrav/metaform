# helloworld

A demonstration of every Metaform module feature, each working once.

## Purpose

helloworld greets names, keeps each greeting as an item of a layer in the project's store, and publishes an event for every greeting. It exists to show how a module behaves on the CLI and over MCP.

## Template version

Started from template 0.2.0.

## Declaration

`SUPPORTED_OS = ('linux', 'macos', 'windows')`, `DEPENDENCIES = ()`, `SHIPS_DISABLED = True`, so it is off until `metaform enable helloworld`. `MODULE` declares seven verbs, one subscription and a status hook.

## Common base used

`metaform.module` for the declaration and `Context`, `metaform.settings` for its three settings, `metaform.data` for its layer.

## Verbs

- `greet <name> [--loud]`: returns the greeting and publishes `helloworld.greeted`. Tool `helloworld_greet`.
- `wait <seconds>`: waits, then returns `waited <n> s`. Tool `helloworld_wait`.
- `history`: returns the names greeted so far. Tool `helloworld_history`.
- `forget [--confirm]`: deletes the greeting layer. A caution verb. Tool `helloworld_forget`, with `confirm`.
- `beep`: rings the terminal bell, on Windows only.
- `todo <task>`: writes a `tbd` work record on the module's own element, `code.module.helloworld`, with the task; returns the record id. Tool `helloworld_todo`.
- `done <id> <resolution>`: marks that record done, its resolution kept beside it. Tool `helloworld_done`.

## Settings

`--greeting`, default `hello`. `--loud`, default off, also greet's switch. `--favorite`, a select whose choices are the names greeted in this folder's project.

## Events

Publishes `helloworld.greeted` with `{"name": ...}`. Subscribes to it to record the name, and finishes its layer on the first greeting so it is seen in context. It has no code to announce the write: the chassis fires `map.changed` when the greet command ends, so an open web GUI shows the greeting at once, VIEW-018 and QUAL-016.

## Sync and async

`wait` is a coroutine. Every other verb and the subscriber are plain functions.

## Work records

A module keeps the condition of an object as a work record, apart from the map, MAP-046 and STORE-042: `store.add_work(Node('element', address), 'tbd', task=...)`, `store.edit_work(id, {...})` and `store.finish_work(id, resolution)`. `todo` and `done` show it; the status line counts the open ones, `Helloworld: 1 greeted, 1 to do`; the web GUI draws the element ghostly while a tbd record is open and solid once it is done. Every element and join read, a subtype join's included, carries `open_work`, the conditions of its open records.

## Layers

`helloworld.greetings`, a knowledge layer, mutable and hideable, with provenance module `helloworld`, workflow `greet`, role `module`. Its items attach to the element `code.module.helloworld` the layer creates for them.

## Lifecycle and cleanup

No `start` or `stop`, and no tasks. Unloading leaves the layer in the store.

## Modules relied on

None.

## Systems supported

Linux, macOS and Windows. `beep` runs on Windows only.

## Resources owned

None beyond its layer.

## Installed and direct wheel

The same in both: its data lives in the project store of the Metaform home the run uses.

## Demonstration

```
metaform enable helloworld
metaform add project demo .
metaform helloworld greet world --loud
metaform helloworld history
metaform helloworld todo "greet in every language"
metaform helloworld done <id> "greets in Latin now"
metaform helloworld forget --confirm
```
