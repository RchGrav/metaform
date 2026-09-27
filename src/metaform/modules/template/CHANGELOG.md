# Changelog

Each change to the module contract, newest first, so a module copied from the template can follow it.

## Unreleased

- The topic `map.changed`: a module that writes to a project's map publishes it with `project`, `metaform_id`, `layer`, `kind` and `building`, and the web GUI's open pages redraw from it; the web module passes it to its server, which pushes it to each page, VIEW-018. helloworld's greeting shows it.
- Nothing polls for a change and nothing a person or an agent waits on blocks behind slow work, QUAL-015; what happened is published.

## 0.3.0

- `Verb` gains `transport`: a transport verb, such as `mcp serve`, runs whatever the folder's command surface, CLI-022 and MCP-004.
- The common base gains `tool_arguments` and `setting_value`, which check a tool call's arguments as the command line does, MCP-005; `on_this_system`, BASE-016; and `feedback`, `save_report`, `list_reports` and `read_report`, BASE-045.
- A write that does not fit is stored as given and its result carries `notices`, each with `where` and `message`; only a call that cannot be read raises `Stop`, BASE-044 and STORE-026.
- Elements, joins and subtypes carry `flag` and `flag_note`, MAP-046 and STORE-042.

## 0.2.0

- `Verb` takes `nouns` as `Noun` records and `switches` as setting keys; `Adverb` is gone, CLI-012 and BASE-035.
- `Context` carries `project`, `store`, `nouns` as a dict, `switches`, `surface`; `Context.data` is gone, keep data as a layer through `ctx.store`, STORE-022.
- `Module` gains `start`, `stop` and `status`; `Status` adds status lines and one notice, BASE-018 and BASE-035.
- A module declares `SHIPS_DISABLED` and `DEPENDENCIES` as literals, read before import, BASE-015 and BASE-017.
- A verb may declare `supported_os` and `surfaces`, BASE-016 and BASE-035.
- A verb returns its result; the CLI and MCP show the same data, BASE-036.
