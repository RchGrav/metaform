# Duplicate delivery of one result, 2026-10-19

Symptom: the held-cap result (transition defbd001, 2026-10-19 00:32Z) was delivered once by the orchestration store and queued once by the runner. The system agent still answered it at thread seq 2112 and called it "the same message again" at seq 2116. So the transition dedupe was not the cause.

Four causes in dispatch, each fixed in the working tree on that date:

1. Two drains. Every runner, the MCP server and the web server drain all pending transitions, and the drain does not claim a transition before delivering it. `_notify_user` relayed on every call. Fix: only the call that wrote the notification line relays.
2. Hand-off. `taken_over` requeued the carried turns without their note ids, and `replay_peers` queued the same notes again. Fix: `Session.turn` records every note id it queues in `queued_peer_ids`.
3. Resume or new start. The system role's `user_updates` turn repeated the updates that `replay_peers` delivers as notes. Fix: `Session.updates_due` drops ids already queued and records the ids it gives. It replaced two inline `user_updates` blocks in `Session.begin`.
4. Repeats in one turn. `note_context` put the result's body, raw result and context component beside the note text. Fix: it leaves out what the note text already holds.

Open, separate: a new system conversation (new runner id) gets every notification line ever written through `user_updates`, because receipts are kept per runner.

Also open, not caused by this change: `test_dispatch.py::test_the_runner_taking_a_session_over_says_so_once_and_sends_what_the_old_runner_was_sent` failed on an extra `typed=False` key from an uncommitted `Session.typed` change.
