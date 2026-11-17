# Bugs to fix

Bugs found while working, kept until each is fixed. Each says where it shows, what happens, and where the cause is
when known. When one is fixed it is removed from here and named in the commit. Once the `metaform` project's map is
recorded, each becomes a ticket on the element it concerns.

## Open

1. **`metaform dispatch wait` cannot follow an intake.** Found 2026-11-16. `metaform dispatch wait done
   id=task-<id>` on an intake's work id answers "No work record has the id task-…" at once, because `wait` reads work
   records on the old store and an intake task is not one. A caller waiting for an intake to finish has no command
   for it. Goes with moving dispatch off the old store.
5. **One dispatch test fails.** `test_the_agents_key_read_makes_the_same_few_queries_however_many_sessions_have_ended`
   expects an `intake` field in a session's state (issue 24 of `dispatch-owns-acp.md`).
6. **The map names the harness element after three hard-coded harnesses.** Found by the person 2026-11-16. The
   `metaform` intake recorded `upstream.code.harness.agent` as known as "Claude Code, Codex, Google Antigravity",
   because dispatch's `AGENTS` table names those three and the intake agent reads the code as what the project uses.
   Fixed by step 3 of `dispatch-owns-acp.md` (the registry replaces the table), then a re-intake that refines the map.
7. **Two settings-screen tests fail on `feat/project-tool`.** Found 2026-11-16, failing the same with and without the
   ACP connection work. `tests/test_tui.py::test_a_section_opens_as_a_menu_of_its_settings_and_lists_are_alphabetical`
   still expects Claude Code's `Agent` row among its option settings, which step 0 of `dispatch-owns-acp.md` removed
   from `OWN_OPTIONS`; `test_a_value_outside_its_choices_is_refused_with_them_and_a_staged_row_is_marked` fails with
   `KeyError: 'code_kinds'` at `tests/test_tui.py:319`.
8. **A recovery test fails.** Found 2026-11-16 while removing client files and terminals; it fails the same way at
   `68c1783d`, before that change. `test_liveness.py::test_automatic_recovery_stops_orphans_before_returning_ticket_and_preserves_progress`
   finds an orchestration "runner died" notification line in the transcript that the test does not expect.
9. **A system agent whose turn fails on a network error stays alive and stuck.** Found 2026-11-16. Session
   `b725fba9…` in `workspace`: its first turn ended with Claude Code's `API Error: Can't reach the API server — check
   your internet or DNS (ENOTFOUND)`. The runner stayed up, idle, for hours, and every Call reused it. Nothing tries
   the turn again, and the person is not told the agent is waiting on them to resend.
10. **Subagent updates are dropped by the SDK's schema.** Found 2026-11-16 in session `474eaaae…`: Claude Code's
    adapter 0.107.x sends `subagent_update` and `session_message`, because the runner offers the `subagents`
    capability, and the Python SDK's `SessionNotification` refuses both kinds, so the whole update is lost (15 times
    in that session). A subagent's work never reaches its thread. Fixed by step 2b of `dispatch-owns-acp.md`: the new
    layer keeps update kinds it does not model as `other` events.
11. **`user_agent` answers a reused system agent with `session_id: null`.** `tasks/runtime.py:189` hard-codes `None`
    when the running system agent is reused. The page copes by finding the running session itself, so it did not
    cause the "Please stand by" fault (fixed in `d71dc909`), but the answer is wrong.
12. **The SDK has no handler for `auth/status_update`.** The web log shows `Unhandled error while handling notification
    method=auth/status_update` with `Method not found`, from a probe on the v1 client. Noise today; step 2b's layer
    handles the login status push.
13. **Harnesses are named in the code outside `AGENTS`.** `PROFILE_ONLY = {'claude': ('agent',)}`
    (`dispatch/__init__.py:655`) and `self.agent == 'claude'` (`runner.py:2464`, a subagent's child id). Both go with
    step 3 of `dispatch-owns-acp.md`: behaviour follows what a harness advertises, never its name.
14. **The system agent is also called "the lead" in the code.** The page and the person call it the system agent;
    `web/server.py` names it the lead (`leads`, `lead_given`, `WORKSPACE` comments). The person's choice, 2026-11-16:
    it is the system agent. New code says system agent; the old names are renamed when that code is next changed.
15. **The clicked-line browser test fails before reaching its end.** Found 2026-11-17, failing the same on the
    committed code at `7734bfef` in a separate worktree.
    `test_what_the_person_last_clicked_is_named_to_their_system_agent_with_their_next_message` times out at
    `test_web.py:6951` (a `wait_for_function`, 15 s), and where it gets past that, its setup
    `agent.store.add_work(..., held=True)` is refused: `StoreError: An explicit hold requires a nonblank hold_reason`.
16. **A queued-message browser test sees an extra 404.**
    `test_a_queued_message_that_fails_puts_back_only_the_persons_words_and_keeps_the_views_context` expects one console
    error (the 409 it causes) and gets a `404 (Not Found)` before it, on the committed code at `7734bfef` too.
17. **"Allow all" also answers the system agent's plan approval.** Found 2026-11-17. With a session set to approve-all
    (the "Allow all" button on a permission card, confirmed), Claude Code's plan approval, its exit-plan permission
    request, is answered at once like a tool permission ("Approve Plan: approved by this session's prompts=approve-all").
    The agent took it as the person's approval and started an architect helper on the plan. A plan approval is the
    person's decision, not a tool's permission. The person's call: whether approve-all leaves plan approval to them.
18. **The system agent starts helpers on a plan without a ticket.** Found 2026-11-17. Its task text
    (`tasks/resources/user_agent.txt`) says to hand a mature plan to the architect agent, and a helper has no ticket by
    design (`dispatch helper`), so the work is not on the board. The person expected a ticket. The person's call:
    whether the system agent writes a ticket for planned work before starting agents on it.
19. **Other system agent behaviours keyed to role 'system' are off for the user_agent task.** Since tasks retired roles
    (2026-10-24), `runner.py` code that checks `self.role == 'system'` or `self.system` (lines about 3249, 3294, 3766
    and the message steering and pre-empting in the `message` op) does not apply to the system agent. The question
    gate and the page's recognition are fixed (2026-11-17); each of the rest needs checking against what the task's
    own instructions now do before it is switched on.
20. **The `metaform` intake surveyed the documentation instead of tracing the code.** Found 2026-11-17 from session
    `aaf50c9d…` (2026-11-16 20:00 to 20:07 UTC, task `task-b0ba7bee…`): 99 project tool calls and about 30 shell
    commands. Before its first writes it read the README, `AGENTS.md`, folder listings, the first 12 lines of each
    module README and the first line of each Python file's docstring; no file was read whole and no function was
    followed. The procedure asks for "a element by element trace operation focused strictly on the functionality".
    Example: it recorded `upstream.code.harness.agent` as "Claude Code, Codex, Gemini CLI" with ref
    `src/metaform/harness.py`, a file that names none of them and is about the AI tools that connect to Metaform's MCP
    server, not ACP; it then grepped for "gemini|antigravity|opencode", found Antigravity in dispatch, and changed the
    name to "Claude Code, Codex, Google Antigravity". The name came from the model's own knowledge, and the type from
    the word "harness" in a docstring. The `metaform-intake-pass` skill it loaded covers only how to record with the
    tool. Not yet checked: the exact payload the intake agent was given around the procedure.
21. **The demo cannot import its map.** `tests/test_cli.py::test_the_demo_project_comes_from_the_package_mapped_with_the_demo_agent_and_is_reused`
    fails: `metaform import src/metaform/demo/map.json` answers "The document has schema version 21; this Metaform
    supports version 23". The demo's map is an old-store document. Found 2026-11-17; not caused by the store's graph
    change, which does not touch import.
