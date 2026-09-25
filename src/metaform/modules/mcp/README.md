# mcp

Serves Metaform's tools to AI tools over MCP.

## Purpose

The mcp module starts the Model Context Protocol server a host launches with `uvx --from <source> metaform mcp serve`. Every surfaced module verb is a tool, and the instructions are composed live from the base text and each module's purpose. It ships enabled.

## Template version

Started from template 0.2.0.

## Declaration

`SUPPORTED_OS = ('linux', 'macos', 'windows')`, `DEPENDENCIES = ('mcp>=2.2',)`, `SHIPS_DISABLED = False`. `MODULE` declares one verb, `serve`, for the CLI only.

## Common base used

`metaform.module` for the declaration, `Context`, the module registry, the command surface, the composed instructions and the per-call context; `metaform.settings` for tool switch schemas and the `set` tool.

## Verbs

`serve`: runs the server over stdio until the host closes it. It is never itself a tool.

## Settings

None of its own. The `set` tool stores any setting for the server's folder.

## Events

None.

## Sync and async

`serve` runs the server's own loop. Coroutine verbs are awaited in that loop, so a host's cancellation reaches them; plain verbs run in a worker thread.

## Layers

None.

## Lifecycle and cleanup

The server runs until its standard input closes. It spawns no tasks of its own.

## Modules relied on

None; it serves the verbs of every module on the surface.

## Systems supported

Linux, macOS and Windows.

## Resources owned

Its standard input and output, for the protocol.

## Installed and direct wheel

In an installed Metaform, uvx gives the server its own environment. A directly run wheel needs the `mcp` package installed, since it is compiled.

## Demonstration

```
metaform mcp serve
```
