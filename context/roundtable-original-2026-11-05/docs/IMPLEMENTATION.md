# Roundtable implementation (Rust)

The owner's specification (`README.md`) and ACP integration design (`Roundtable_ACP_Integration_Design.md`) govern. The owner's decisions are recorded with their own words in `docs/TRACEABILITY.md`, which maps every requirement to the code and the test that proves it, and lists what is not done. This file only orients a reader.

## Crates

| Path | Role |
|---|---|
| `crates/bus` | Typed in-process event bus. Publishing never blocks, no subscriber misses an event, and all subscribers see one global order. |
| `crates/acp-host` | ACP autoselection (the ACP Registry, a built-in catalog, custom commands), harness launch over stdio with the official ACP Rust SDK, sessions, permission policy. Everything is published as events. It knows nothing about Roundtable. |
| `crates/agent-monitor` | Independent activity observation with AgentSight. See its crate docs for what runs where. |
| `crates/roundtable` | The Roundtable core library: rules, engine, JEV client, prompts, genesis names, participant tools (MCP, transport-agnostic), record. |
| `crates/roundtable-web` | The standalone tool: `roundtable serve` (web UI) and `roundtable run <table.json>`. |
| `adapters/openrouter-acp` | ACP adapter around the OpenRouter Agent SDK, so OpenRouter models join as ACP agents. |

## Running it

- **Web UI:** `cargo run -p roundtable-web --bin roundtable -- serve`, then open the printed URL. Its `#token=` carries this run's chair token.
- **JEV key:** set `OPENROUTER_API_KEY`, or enter it in Settings (kept in memory only).
- **Where data goes:**
  - each table's record: `~/.roundtable/tables/<id>/record.jsonl`;
  - feedback: `~/.roundtable/accolades.jsonl`;
  - end-of-table ratings: one profile per genesis name in `~/.roundtable/identities/<Name>.json`.

## Using the library

1. Build a `TableConfig`.
2. Call `roundtable::spawn(id, config, bus, jev, tools)`.
3. Drive the table through the returned `TableHandle`.
4. Render it from the events in `roundtable::events`.

A host that offers the participant tools serves `roundtable::mcp::handle` at the URL it passes in `ToolsEndpoint`, and checks each request's bearer token with `TableHandle::seat_token_valid`.

## History of this build

- The first build added mechanisms the owner never asked for: a deliberation timer, a `WORK` reply convention, an 8 s JEV limit copied from the old version, and a round rule that let a lone agent bank allowance.
- The owner rejected them. An independent audit (`review/SPEC-AUDIT.md`) found where the build broke the spec.
- That first version of this file wrongly described plain ACP events as "AgentSight monitoring" when AgentSight was not built.
- The engine was then rewritten against `docs/TRACEABILITY.md`.
- The old Python version is analysed in `docs/archive/`.
