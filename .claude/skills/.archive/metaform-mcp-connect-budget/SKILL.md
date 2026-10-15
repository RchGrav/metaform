---
name: metaform-mcp-connect-budget
description: Use when editing MCP connect text or its 2,048-char budget.
category: development
---

# MCP connect message fits 2,048 characters

Claude Code keeps only the first 2,048 characters of the MCP connect message. Text past the cut never reaches the agent, so measure the whole message after any change to it, not just the piece you edited.

The connect text is `connect_instructions` in `src/metaform/modules/mcp/server.py`: the startup instructions first, then the fallback skill index within the room left (`HOST_KEEPS - len(started) - 1`). The index is sent as descriptions if they fit, else names alone, else nothing. When the index is dropped, the names do not come through the connect text. The server cuts long tool descriptions in its listing by rule (MCP-003: first sentence plus caution past 160 characters), so a name placed after the first sentence of `metaform_skills`' description never reaches the agent from the listing. The names come with that tool's first result in a session (MCP-039; BASE-059 amendment 2026-10-15). Do not grow the connect text to carry them.

- Measure with `METAFORM_ROLE` unset. A dispatched agent's shell sets `METAFORM_ROLE=worker`, which drops intake's FIRST RUN notice, so the number is wrong.
- A new startup line takes room from the index. Re-measure the total after adding it, and expect the index to fall to names or to nothing.
- The guard is `test_connect_message_and_index_fit_what_the_host_keeps` in `src/metaform/modules/mcp/tests/test_mcp_skills.py`. With the budget removed it fails at 2785 against 2048.
- Measured 2026-10-14: with the default modules, the names-only index brings the total to 1975. With all eleven shipped modules on and first-run showing, startup alone is about 2041, so the index is dropped and only the `metaform_skills` description carries the names. A mode that adds one more startup line can push a full index out, so re-measure with every module on as well as with the defaults.
- Details of the measurements and the test run: `references/connect-budget-evidence.md`.
