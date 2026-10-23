---
name: agent-harness-integration
description: Use when adding, swapping or removing an ACP agent harness.
category: development
---

# Agent harness integration in Metaform dispatch

Swap a harness in one change: the vendor's own ACP server, every reference to the old id moved or removed together, and agent events read only from standard ACP messages.

- Confirm the vendor publishes the ACP server and pin its version. Reject third-party wrappers. The ACP registry lists the vendor's official adapter with its version; use that entry, not an npm search hit. If no official server exists, report blocked instead of building one.
- Before changing anything, grep for the old agent id in the dispatch catalog, settings, routing, ticket agents, roundtable seats and pickers.
- Migrate stored choices (saved settings and ticket agent values) to the new id in the same change that deletes the old adapter's code, settings, prompt words, tests and doc lines. Keep the old id as a literal only in that migration code. A path the vendor still reads under the old name (such as its own config folder) belongs to the vendor: keep it and say why, rather than renaming or deleting it. Have the person's decision on that boundary in writing before deleting it.
- Dispatch reads agent events from standard ACP messages for every harness. For compaction, advertise `clientCapabilities.session.compaction: {}` and act on `compaction_update` (see `src/metaform/modules/dispatch/runner.py`).
- Add no hook fallback, heuristic or harness-specific parsing for a missing signal. A harness that lacks an ACP signal has a gap for its wrapper to fix; report it.
- Test only what changed, with the existing fixtures.
