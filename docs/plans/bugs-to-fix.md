# Bugs to fix

Bugs found while working, kept until each is fixed. Each says where it shows, what happens, and where the cause is
when known. When one is fixed it is removed from here and named in the commit. Once the `metaform` project's map is
recorded, each becomes a ticket on the element it concerns.

## Open

1. **`metaform dispatch wait` cannot follow an intake.** Found 2026-11-16. `metaform dispatch wait done
   id=task-<id>` on an intake's work id answers "No work record has the id task-…" at once, because `wait` reads work
   records on the old store and an intake task is not one. A caller waiting for an intake to finish has no command
   for it. Goes with moving dispatch off the old store.
2. **No harness picker after Stop agent.** Found by the system agent 2026-11-16
   (`~/.metaform/workspace/plans/agent-profiles/images/bug-no-picker-after-stop.png`). After Stop agent the chat
   keeps the ended session's window and never offers the harness picker or Call; only a reload recovers. Cause:
   `session/text.js` `drawSession` draws the before-call settings only when there is no session at all, and the
   `DOCK.target` checks in `session/settings.js` `preCallSettings`.
3. **A message to Claude Code shows twice.** Found by the system agent 2026-11-16 (`bug-duplicate-hi.png`). Claude
   Code's adapter starts the CLI with `replay-user-messages`, so every prompt comes back as a `user_message_chunk`,
   and the thread shows it beside the person's own line. Fix in the runner: during a live turn, do not record the
   echo of the prompt just sent; keep `user_message_chunk` lines on a load or resume, which are the history.
4. **Claude Code's "Agent" option in the chat window.** Found 2026-11-16 (`bug-claude-agent-option-subagents.png`).
   It runs the whole session as one of the person's plugin subagents and is confusing even under "More from Claude
   Code". Remove it from the chat window; a Claude Code profile may name one (dispatch plan, step 4).
5. **One dispatch test fails.** `test_the_agents_key_read_makes_the_same_few_queries_however_many_sessions_have_ended`
   expects an `intake` field in a session's state (issue 24 of `dispatch-owns-acp.md`).
