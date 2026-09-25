# map

Reads and writes a project's functional map and its layers, on the CLI and as MCP tools.

## Purpose

The map module exposes the data access object's reads and writes as verbs, so agents read the map and build knowledge layers through tools, and people through `metaform map`. It ships enabled.

## Template version

Started from template 0.2.0.

## Declaration

`SUPPORTED_OS = ('linux', 'macos', 'windows')`, `DEPENDENCIES = ()`, `SHIPS_DISABLED = False`. `MODULE` declares the verbs of BASE-038.

## Common base used

`metaform.module` for the declaration and `Context`, `metaform.settings` for `--raw`, `metaform.data` for every read and write.

## Verbs

Start with `roots`: the map's entry, the VE and the DE with the joins they receive, and every root element; `where` with an empty address returns the same. Reads: `where`, `element`, `joins`, `identity`, `subtypes`, `children`, `layers`, `layer`, `node`, `context`, `links`, `citing`, `history`, `stack`, `metaforms`, `search`, and `findings`, the objects flagged missing, broken or cruft. Writes: `knowledge` with `op=` and `layer=` on every call, `tag`, `untag`, `select`, `mask`, `clear`, `hide`, `unhide`, `reexamined`, `add-metaform`, `activate`, `answer`, and `approve` on the CLI only. Each verb returns its operation's result; every join shows the layer it comes from, and every element, join and subtype its flag. A write that does not fit is stored as given and its result carries `notices`. `knowledge` takes `flag=` and `flag_note=` on `add-element`, `add-join` and `add-subtype`. Tools are `map_<verb>`.

## Settings

`--raw`, default off: read every stored layer, building, hidden and masked ones included.

## Events

None.

## Sync and async

Every verb is a plain function.

## Layers

It writes whatever layer a `knowledge` call names; it creates no layer of its own.

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
metaform map knowledge op=create layer=notes variable="Notes at each node." mutable=true hideable=true module=me
metaform map knowledge op=add-item layer=notes node=element:code.engine value='"Profile first."'
metaform map knowledge op=finish layer=notes
metaform map node element:code.engine
```
