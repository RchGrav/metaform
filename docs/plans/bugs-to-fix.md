# Bugs to fix

Bugs found while working, kept until each is fixed. Each says where it shows, what happens, and where the cause is
when known. When one is fixed it is removed from here and named in the commit. Once the `metaform` project's map is
recorded, each becomes a ticket on the element it concerns.

## Open

1. **`metaform dispatch wait` cannot follow an intake.** Found 2026-11-16. `metaform dispatch wait done
   id=task-<id>` on an intake's work id answers "No work record has the id task-…" at once, because `wait` reads work
   records on the old store and an intake task is not one. A caller waiting for an intake to finish has no command
   for it. Goes with moving dispatch off the old store.
3. **A message to Claude Code shows twice.** Found by the system agent 2026-11-16 (`bug-duplicate-hi.png`). Claude
   Code's adapter starts the CLI with `replay-user-messages`, so every prompt comes back as a `user_message_chunk`,
   and the thread shows it beside the person's own line. Fix in the runner: during a live turn, do not record the
   echo of the prompt just sent; keep `user_message_chunk` lines on a load or resume, which are the history.
5. **One dispatch test fails.** `test_the_agents_key_read_makes_the_same_few_queries_however_many_sessions_have_ended`
   expects an `intake` field in a session's state (issue 24 of `dispatch-owns-acp.md`).
6. **The map names the harness element after three hard-coded harnesses.** Found by the person 2026-11-16. The
   `metaform` intake recorded `upstream.code.harness.agent` as known as "Claude Code, Codex, Google Antigravity",
   because dispatch's `AGENTS` table names those three and the intake agent reads the code as what the project uses.
   Fixed by step 3 of `dispatch-owns-acp.md` (the registry replaces the table), then a re-intake that refines the map.
