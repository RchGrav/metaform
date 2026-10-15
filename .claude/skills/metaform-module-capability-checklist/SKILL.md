---
name: metaform-module-capability-checklist
description: Use when adding or removing a module verb, command, prompt, setting, store table or dependency.
category: development
---

# A new module capability ships with its template, changelog and tool reference

Any capability a module can use goes into `src/metaform/modules/template` (code, `resources/prompts.xml`, README) and into its `CHANGELOG.md`, in the same change. Then update the module's README (one bullet per verb: what it does and its effect), its `resources/prompts.xml` tools comment, and the hand-kept tool reference: nothing generates it.

- `docs/reference/metaform-mcp-server.md` lists every tool. No script, source file or test reads it (a grep of `scripts src tests` for its name returned nothing on 2026-10-15), so add the rows yourself: a `### <module>` heading with one line, then one row per tool with what it does and its effect (`read`, `write`, `remove`, `open world` where it applies). Caution clauses go in the description, as existing rows do.
- Specification wording stays a draft in `artifacts/specs-draft/` until the owner approves it (metaform-spec-amendments).
- A new verb that writes or reaches the network must declare its effect in its tool reference row. The guard `test_every_verb_that_reaches_the_network_or_writes_declares_it_in_its_annotation` in `src/metaform/modules/mcp/tests/test_mcp.py` checks it. Run it alone: `.venv/bin/python -m pytest -n 0 -q src/metaform/modules/mcp/tests/test_mcp.py -k reaches_the_network_or_writes_declares`. It can flag a verb you did not touch (`dispatch_spend` failed on 2026-10-15); check with `git log -S` before assuming your change caused it.
- Prove the change with one test per changed line, in the module's `tests/`, run by `-k` name (CLAUDE.md), never the whole suite.
- After changing a tool's description, check the listing with metaform-mcp-tool-listing.
- An agent-facing capability with several operations is one command whose help lists them, and the agents' start message carries one line naming that command and what is available now, never the operations in a long prompt. The person asked for this on the channels feature (2026-10-15): "Use channels for commands."
- A bare call of such a command shows the whole picture (every item and every agent with its work), and the operations stay behind its help.
- A server agents start and stop gets one restart verb (`metaform web restart`, 2026-10-15), never a stop command an agent must follow with a start. Two calls leave the page down when the second one fails or starts from the wrong environment; one call stops and starts it.
