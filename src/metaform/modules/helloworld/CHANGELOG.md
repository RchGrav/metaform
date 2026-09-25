# Changelog

Each change to the module contract, newest first, so a module copied from the template can follow it.

## 0.2.0

- `Verb` takes `nouns` as `Noun` records and `switches` as setting keys; `Adverb` is gone, CLI-012 and BASE-035.
- `Context` carries `project`, `store`, `nouns` as a dict, `switches`, `surface`; `Context.data` is gone, keep data as a layer through `ctx.store`, STORE-022.
- `Module` gains `start`, `stop` and `status`; `Status` adds status lines and one notice, BASE-018 and BASE-035.
- A module declares `SHIPS_DISABLED` and `DEPENDENCIES` as literals, read before import, BASE-015 and BASE-017.
- A verb may declare `supported_os` and `surfaces`, BASE-016 and BASE-035.
- A verb returns its result; the CLI and MCP show the same data, BASE-036.
