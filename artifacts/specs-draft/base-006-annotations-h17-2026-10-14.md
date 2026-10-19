# BASE-006 and MCP-003: what the declared effect must cover (draft, H17, 2026-10-14)

Draft text for Rich. Nothing in `specifications/` was changed. The code is the reference. This text describes the code as it is after ticket code.server.tool#5.

## Proposed addition to BASE-006, "What this means"

A verb declares what it can reach, including through its subscribers and through any process it starts:
- A verb whose published event starts work that reaches the network declares `open_world`. Example: `intake finish`, whose `intake.finished` subscriber in refactor starts `refactor extend`.
- A connection to 127.0.0.1 is not the open world: the relay, Metaform's own web server, a module's own bridge.
- A verb that sends project text to a third party through `metaform.jev` changes something: the person's credit is spent. Such a verb is never `read`, so no host takes it to be read-only or idempotent. Examples: `refactor associate` and `dispatch signals`.
- Bookkeeping is not a write. That covers a module's tables made on first use, a cache, and what a session was shown.

## Proposed addition to BASE-006, "Verify"

The mcp module's `test_every_verb_that_reaches_the_network_or_writes_declares_it` enables every module and walks the calls of each verb from source. It fails in two cases:
- a verb that reaches the network and does not declare `open_world`;
- a verb declared `read` that reaches a write to the map, a write to the settings, or a send through `metaform.jev`.

## Open for Rich

H17 says that `map add-base`, `map activate` and `map collapse` switch the active map for everyone with no caution. Their annotations are accurate: write, not destructive, not open world. Adding a `caution` would make every CLI and MCP call to them need `confirm`. That includes the `metaform map activate <previous-name>` that `intake finish` names as its next step. Whether these verbs should carry a caution is a design choice. It was not made.
