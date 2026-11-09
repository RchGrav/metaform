# Development bootstrap

## What is ready

One current system spec; corrected functional schema; native fixtures; one proposed functional MCP tool contract;
updated intake prompt and agent skill; stored-data and tool-input checks; protected source snapshots and hashes; CI; project MCP docs configuration.
There is no application runtime yet. No fake server or placeholder API is presented as working software.

## Setup

```sh
git clone https://github.com/RchGrav/topogee.git
cd topogee
python -m venv .venv
.venv/bin/python -m pip install -r metaform/requirements-dev.txt
.venv/bin/python metaform/tests/check_contract.py
.venv/bin/python metaform/tests/check_tool_input.py
.venv/bin/python tools/verify_bootstrap.py
.venv/bin/python metaform/validate_metaform.py metaform/owner-skills-example.json
.venv/bin/python metaform/validate_metaform.py metaform/provider-reference-example.json
```

Windows: use `.venv\Scripts\python.exe`. Python is the contract-check utility language, not a decision to implement the product in Python.

## First implementation slices

1. Read the actual specification and primary theory/intake sources. Preserve confirmed semantics; present material proposals visibly. Do not restart the interview or install an agent-modified prompt.
2. Record an evidence-based runtime/WebTransport/Ladybug/MCP/ACP integration choice. Keep a small experiment separate from product claims. Boat is a documentation source to evaluate, not an already selected dependency.
3. Implement independent chassis and explicit module/shared-service lifecycle. Establish one authoritative database owner and public DAO responsibilities. Demonstrate transactions, rollback/restart, stale-write conflicts and caller/project isolation.
4. Implement subscription delivery without recurring polling, then lightweight mailbox and live operator context/tool-surface monitors. Measure control latency under concurrent/loss/slow-consumer load.
5. Implement the native map, three read-only views, the one-receiver working commands, and standalone MCP. Validate command input first, then validate the proposed resulting map against existing data. Verify actual harness interoperability and preserve authored intake semantics.
6. Extend through feature modules: presentation, dispatch/ACP, context, messaging, orchestration, assessment, feature delivery, sensing and composition. Use the full spec's acceptance matrix; do not claim all of it from the bootstrap tests.

## Changes and reviews

Use bounded feature commits with readable problem/change/verification descriptions. Keep PM → spec writer → technical specialist responsibilities visible; no compulsory paid reviewer cascade or arbitrary tool gates. Protected intake schemas/prompts need direct founder instructions to change. Do not bulk-port old implementation code.

## Boat

Boat provides throwaway cloud sandboxes for checks and experiments. It is a development tool, not a product dependency.

- Contract tests in a clean sandbox: `metaform/tools/boat_contract_check.sh`. It uploads a fixed list of contract files, never `reference/`.
- Engine experiments: `experiments/ladybug-concurrency/`, with results in `verification/`.
- Documentation MCP: `.mcp.json` (Claude Code) and `.codex/config.toml` (Codex) declare boat-docs at https://docs.boat.dev/mcp. No credentials are included. `initialize` and `tools/list` were verified on 2026-10-30.

Rules:

- Use `boat run --no-env` unless a task needs account credentials. Other sandboxes receive the account's stored secrets.
- Do not upload `reference/` or intake material without the founder's direct instruction.
- The account is shared with the founder. Stop, prompt or delete only a sandbox whose ID came from your own create call. `boat run` deletes its own sandbox.
- `boat new`, `boat fork` and other ID-taking commands fall back to the shell's current sandbox when the ID is empty. Check the create result before using it.

A fork keeps the stopped source's files (checked 2026-10-30). `boat stop` returns before its snapshot is ready, so a fork can fail at first; retry slowly, because the $20 plan allows 12 sandbox starts per minute.

CI uses `runs-on: boat` through the Boat CI GitHub App (`boat ci connect`). Boat events report no token counts, so the token meter must count at the chassis.

## Reference material

Read reference/README.md before historical sources. `source-register.json` records exact snapshot hashes. Original contract bytes now live in `reference/contract-baseline-2026-10-30/`; the root contract files are the owner-authorized current versions.
Do not execute reference scripts or adopt old SQL schemas, generic MCP routers, role hierarchies or generated field renames merely because they appear in the archive.

CI runs contract and portable-bootstrap checks. Runtime/database/WebTransport/multi-user acceptance tests are added with the corresponding implementation, using actual engines and clients.

## Current intake and tool contracts

[The specification](metaform/SPECIFICATION.md) defines the recorded fields `wants`, `goal`, `function`, and `intent`, one source `uri`, and the working commands. Intake reasoning retains the authored RE/PE/OP/EF/IFD/CQU terms and definitions; recording instructions map them to these fields. [metaform/Intake.xml](metaform/Intake.xml) is the current project prompt. Maintain it here. The sequence diagram is [metaform/intake.mmd](metaform/intake.mmd); the supplied source note is [metaform/docs/mcp-query-source.md](metaform/docs/mcp-query-source.md). The stored JSON is a nested namespace. One tool handles both reads and changes. Its addressed input is a separate contract in [metaform/mcp-tools.proposed.json](metaform/mcp-tools.proposed.json).

[metaform/tool-examples.json](metaform/tool-examples.json) contains request and response examples. [metaform/intake-example.json](metaform/intake-example.json) contains the founder's Mashtrac example with the missing comma corrected and `name_length: 3` present on the widget from the start. `name_length: 4` on `code.protocol.network.tracker.cs` is unchanged. Validate the selected `mashtrac` object, not its host wrapper.

The command checks validate input only. They do not implement database mutations, orphan discovery, or deletion. No application runtime has been added.
