# Recall stop case, 2026-10-15

Symptom: an agent recalled from the board appeared in the Agents menu with Resume but not in the dock's stopped list.

Cause: `recallButton` posted only `work_id` and never recorded the stop, so the dock (which reads only recorded stops) had nothing to list.

Fix: the stop posts the session id, records it with `rememberStop`, then `renderAgents()`.

Before run (committed board.js copied in, test fails on the dock count): `assert 0 == 1` on `#helpdesk .stopped-agents .agent-session`, while `#agentbox .stopped-agent button.resume` exists.

After run: 4 of 4 tests in `tests/test_chat_recovery.py` pass headless.

Open item: the intake Stop has the same three-line change and was checked only by reading the code.
