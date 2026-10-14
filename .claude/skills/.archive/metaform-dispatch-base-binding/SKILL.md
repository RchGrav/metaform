---
name: metaform-dispatch-base-binding
description: Use when dispatch says "No work record" off the active base.
category: development
---

# Dispatch on a non-active base

A store opened without a base names uses the bound base. The bound base comes from `METAFORM_BASE` (whole process) or `on_base()` (one in-process call), and is honoured only when the project has that base. Any new dispatch, runner, page or agent-tool path that opens a store for a ticket must carry the ticket's base this way, or the ticket reads "No work record" outside the active base.

- Do not thread a base argument through each dispatch verb. `harness.child_environment` forwards the bound base, so the runner, the agent and the agent's MCP server inherit it.
- `web/server.py` `chosen_base(given)` returns the page's base only when it is not the active one. On the active base nothing is bound, so a session still follows whichever base becomes active.
- Intake never receives the bound base; it must follow the base its finish activates.
- `web.spawn` strips `METAFORM_BASE`, so a page an agent starts is not pinned to that agent's base.
- Autostart from ordinary changes and retries queues with no base (active); only the page's own request carries its base.
- The mechanism lives in chassis (`data/session.py`, `harness.py`). Changing it is a decision for the person; a dispatch ticket records the gap rather than widening it.
- Pattern for tests: refuse without the variable, act with it. See `test_a_dispatch_verb_bound_to_a_base...` in the dispatch tests and `test_dispatch_from_the_page_runs_on_the_base...` in the web tests.
