# mcp

Serves Metaform's tools to AI tools over MCP.

## Purpose

The mcp module starts the Model Context Protocol server a host launches with `uvx --from <source> metaform mcp serve`. Every surfaced module verb is a tool, and the instructions are composed live from the base text and each module's purpose. It ships enabled.

## Template version

Started from template 0.2.0.

## Declaration

`SUPPORTED_OS = ('linux', 'macos', 'windows')`, `DEPENDENCIES = ('mcp>=2.2',)`, `SHIPS_DISABLED = False`. `MODULE` declares one verb, `serve`, for the CLI only, and a transport, so it runs whatever the folder's command surface.

## Common base used

`metaform.module` for the declaration, `Context`, the module registry, the command surface, the composed instructions, the per-call context, the argument checks and the report functions; `metaform.settings` for tool switch schemas and the `set` tool.

## Prompts

`resources/prompts.xml` holds `instructions`, `mcp is active.`, listed in the instructions agents read under "modules available.", and the clear_project texts: `clear_project`, the tool's description; `clear_confirm` and `clear_confirmation`, its arguments' descriptions; `clear_statement`, the exact confirmation it checks; and `clear`, the next step it answers with, MCP-031.

## Verbs

`serve`: runs the server over stdio until the host closes it. It is never itself a tool. Beside the module tools it always serves the chassis tools `set`, `feedback`, `list_reports` and `read_report`, which narrowing never hides, and while the chassis is on the folder's command surface, `add_origin`, `list_origins`, `add_variant`, `list_variants`, `extract`, `prompts`, `prompt` and `clear_project`, the history, prompt and clear commands as tools. `clear_project` requires `confirm=true`, `confirmation="I AM SURE THIS IS WHAT THE USER MEANT DELETE THEIR PROJECT"`, `model` containing the full model designation, and `date` in `YYYY-MM-DD` form. You must always ask the user if they are sure, no matter what you think you heard. Supply these fields only after the user confirms; incomplete or incorrect confirmation returns the caution without clearing anything.

Every call's arguments are read as the command line reads them. A missing required noun is an error with the command line's next step. A text noun or a text setting sent another JSON value, such as `purpose: 12`, reaches the verb as that value's JSON text, with the notice `<name> is text; what was sent was kept as its JSON text.`; a whole-number or true-or-false noun or setting sent another kind cannot be read as that kind and is an error, as on the command line. An argument the tool does not know is kept in the record's `extra` when the verb takes one, otherwise ignored, and named in a notice either way. The chassis tools other than `set` read their arguments by their declared JSON types the same way: a text argument sent another type is kept as its JSON text with the notice, and a whole number, true or false, or a list sent another type stops the call, as does an argument the tool does not declare.

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
