---
name: metaform-mcp-tool-listing
description: Use when MCP tool listing, needs_project, reads_layers, listed or tool description cuts change.
category: development
---

# MCP tool listing and per-tool arguments

Before registration a folder lists only the verbs that can run without a project: a verb is listed unregistered only when it declares `needs_project=False` (`Verb` in `src/metaform/module.py`, default `True`). Chassis tools that act on a project's records (`ON_PROJECT` in `mcp/server.py`) are listed only once `project_for(folder)` is set. `tools()` stays unfiltered, so a cached name still routes and answers "No project ... call metaform_register".

- Decide `needs_project` by reading each verb body, never by an AST walk: a walk judged nearly every map verb free. Verbs that call `require_store` need a project, even when they look like readers (mcp `a2a_*`, intake `prompt` and `status`). Web mascot verbs that use `ctx.project` (`ask_page`) need one too.
- `project` goes in a tool's arguments only when the verb declares `needs_project=True`. `layers` goes in only on verbs that declare `reads_layers=True` (map's 15 reads, set per verb; a module-level flag was tried and removed as too coarse). `_prepare` refuses either on a tool that lacks it. Record both fields in the template module's code, README and CHANGELOG Unreleased.
- A verb may define `listed(folder)` to stay hidden until the folder's state lets it act (web verbs while the GUI runs, intake verbs while recording, dispatch steer verbs while a session runs). `listing()` reads each check once per listing, so a check reads a file or a row and never the network: `announce()` compares listings after every call. A check that raises lists the verb.
- Descriptions over 160 characters are listed as their first sentence plus caution, by rule, and nothing is reworded. Anything an agent must act on goes in the first sentence. The cut text and the module's prompts.xml rules come once per session with that tool's first result (MCP-039).
- Registering needs no notification code: `announce()` compares the listing after each call and sends one `tools/list_changed`.
- Measure with `artifacts/agent-context-cost/checks.py after` (it writes `costs.jsonl`), which uses `web/server.py` `agent_cost`, the same formula as the page's "What an agent reads here" panel. Tokens are bytes ÷ 4 and are labelled as an estimate. Figures and their conditions: `references/measure-2026-10-15.md`.
- A new verb an agent can call that writes (open world) gets its tool name in `UNSEEN_OPEN_WORLD` in `mcp/tests/test_mcp.py`. That registry test can already fail on other sessions' entries (for example a verb declared read that writes, or entries missing from the lists); name each failing entry and whose ticket it is, and do not claim the registry green.
- Tests: a fresh test home has `workflow` off. A test that asserts a tool name in the unregistered list must name one from an enabled module (`fork_init` was used after `workflow_skills` failed). Test: `test_a_folder_with_no_project_lists_only_what_runs_and_registering_announces_the_rest` in `src/metaform/modules/mcp/tests/test_mcp.py`.
