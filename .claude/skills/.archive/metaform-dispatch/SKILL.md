---
name: metaform-dispatch
description: Use when editing dispatch resume or spend budgets.
category: development
---

# Dispatch: resume ownership and spend budgets

Automatic resume and spend caps are the two places dispatch can start paid agents, or reset a limit, by mistake. Guard both, and count live candidates before any change lands.

## Automatic resume runs only for sessions this home started

- Every automatic resume (the supervisor's retry, Stay connected, Call's resumed conversation, automatic recovery) passes over any session row whose `origin` is not this home's `origin()`. Explicit `dispatch resume <id> session=<sid>` stays the only path for other homes' rows.
- Check ownership with `foreign(row)`; never decide from the row's `state` or `how` alone. A dead runner reads as ended, which is not the person's stop.
- Any code that writes a session row sets `origin`: runner take() on insert and on resume, and serve open(). A row seeded by hand for a resume test needs `'origin': module.origin()`, or it is foreign and the test proves nothing.
- Legacy rows (no `origin`, before sessions table version 13) are never resumed automatically. Before landing such a change, count the live candidates in the real home, read-only, and report what will stop resuming.
- Prove the guard with a copied home: copy the home, point `METAFORM_HOME` at the copy, and build a fresh context and `Store` per home. Then mutate the guard in a `/tmp` copy as `verify-guard-test-by-mutation` describes. The copy must start nothing.
- Incident and file map: `references/copied-home-incident.md`.

## Spend lives in the project store

- Write every turn's spend to the project-level `spending` table (dispatch tables version 14), never to a per-metaform table. A base removed from the project takes its rows with it, and the cap resets.
- Write from runner `spend()` and `cost_spent()` into `spending`. Read only through `spend_rows(store, filters)`, which runs `carry_spend` first. `spent`, `session_cost`, `run_of` and `dispatch spend` all go through it.
- The per-metaform `spend` stays declared so older runners still load and write; `carry_spend` moves their rows on every read. Do not gate the carry behind a once-only marker, or an old runner's later rows stay out of the budgets for good.
- `carry_spend` may skip a metaform only by its file stamp: `_CARRIED[(project id, base id)]` holds `(st_mtime_ns, st_size)` of the store file AND its `-wal`, taken after the last carry or empty read. Stores run WAL, so a late legacy `spend` write lands in the `-wal` and leaves the main file's mtime alone; checking the main file alone misses it. Build the path with `home.store_file(project, base.name)`, not `home.store_path`, which re-queries the project db per base. A metaform that cannot be read still raises before any skip is decided.
- A metaform that cannot be read raises. Never wrap a budget read in `except StoreError: continue`; a skipped store is a silent reset.
- Tests seed spend straight into the project table: `Store('proj', module='dispatch').tables()` then `tx.insert('spending', {...})` with the SPEND columns.
- A table cannot change place under its own name, so a move is a new table name plus a carry. Store upgrade rules are in `metaform-development`.

## Post-close turn ends the session

- After a ticket closes, dispatch sends the agent a "record what you learned" turn. The agent must answer that turn with its note and stop. An agent that answers it by replaying its ticket's work never ends its session, so it keeps running and agents pile up on the map.
- A scripted or looping agent must treat the post-close turn as its last: check the prompt for the close, write the note, and end. Verify with a closed ticket and a poll of the session row until its state reads ended, before calling the loop fixed.

## Peer notes between worker agents

- A peer note is one `peer:<id>` line in the existing `lines` table, the same JSON in the sender's thread and each receiver's. The sender's copy is written first, so receivers' delivery marks land on it. No table or column is added.
- A receiver takes a note as its next turn, after any turn in flight, through `self.turn(..., peers=...)`. Never `self.steer()`. A note changes no authority: `may_steer` stays as it is.
- Delivery states (`queued`, `delivered`, `read`, `replied`, `failed`) move only forward, through `signals.mark_peer` in one transaction on each copy.
- The logic lives in `peering.py`, loaded lazily the way `runner` is. Never name a module `peers.py`: importing it rebinds the `peers` verb function on the package.
- Caps are counted from the sender's own threads, so a second receiver cannot get around them.

## Broadcast to every running session

- `broadcast [system=true] -- text` tells every running session at once through `tell(row, 'message', ...)` in a thread pool, so one slow session holds no other. It keeps `message`'s rules: `may_steer` and `sender`. Do not add a second fan-out path.
- The person's system agent (session state `about` = `system`) is told only with `system=true`. A session never tells itself.
- The receiving thread's line is named `broadcast:` plus the broadcast id. The kept record is one `lines` row under session and work id `broadcasts`; a filter on `broadcast:` names also matches it, so exclude session `broadcasts`.
- With no session to tell, the verb is refused: "No agent is working on this project."
- A runner started before a broadcast change still receives the message but writes no `broadcast:` line, so its thread shows no mark until it restarts.

## Per-session permission answer mode

- A session's own answer mode (ask each time, approve reads only, approve all) lives in its state line `acp['prompts']`, not in a table. `Session.answering()` resolves session over launch over the project's `dispatch_prompts` setting. `set_prompts` writes a `setting` line and approves each waiting request the mode allows; `continue_thread` restores it on resume.
- The mode is set from the CLI only (`metaform dispatch prompts <id> <mode> [session=] [confirm=true]`, persons_own). Approve all is refused without `confirm=true`.
- Multi-agent tests: fake agents given separate `FAKE_ACP_LOG` files all get session id `fake-session-1`, so a shared log merges their lines. Give each agent its own log and read them apart. `FAKE_ACP_ASK_AGAIN=<file>` makes the fake ask a second request once that file exists.
- The same shared id makes a second runner fail on its sessions row with `UNIQUE constraint failed: dispatch.sessions.session_id`. For many runners at once (load or idle-CPU runs), run them from a `/tmp` copy of the fake that names its session with `os.getpid()`; leave the test fake unchanged.
- A permission answer reaches the agent before it is recorded. `answered()` sets the waiting future first, and `request_permission` spawns its `map.changed` instead of awaiting it. Reading the ticket and writing two rows first took 484 ms; the path now answers in under 100 ms (`test_the_persons_answer_to_its_own_permission_request_reaches_the_runner_within_100_ms`). Keep that order when adding writes to the answer path.

## A stopped agent's ticket stays taken until dispatch reset

- A ticket a stopped or killed agent held stays taken by design (`dispatch release()` does not free it). Any tool that stops agents it started (a demo's Ctrl+C, a probe's teardown) runs `metaform dispatch reset` after stopping them, and again before it starts its own, or the next run refuses with `Work <id> is already taken by claude <pid>`.
- Test it with a kill mid-ticket, then a second start in the same scratch home: `test_a_demo_stopped_or_killed_leaves_no_ticket_taken_for_the_next_run` in `tests/test_cli.py` is the model.
- Scripted lanes that share one rest timer empty a map together. A lane whose ticket closes while another lane rests starts its next ticket at once, so at most one lane rests; the scheduler wakes on `map.changed` and on deadlines, never on a fixed 1 s loop.

## Tests that change a session row or find its runner

- Change an existing `dispatch.sessions` row with `tx.update('sessions', {'session_id': f's-{work_id}'}, {...})`. `tx.insert` on the same key fails with `UNIQUE constraint failed: dispatch.sessions.session_id`. Worker sessions are keyed `s-<work_id>`; the system agent's row is keyed by its own id the same way.
- Find a worker's runner pid from its sessions row (`dict(tx.get('sessions', {'session_id': ...}))['pid']`), not from the test's `RUNNERS` list. The list lookup raised `StopIteration` for a worker the test had opened from the page.

## Every change

- Each change gets a dispatch `CHANGELOG.md` Unreleased entry naming its ticket. A resume-guard change also gets a sentence in the README's "Supervisor and budgets" section; the README's `spend` row changes only when that verb's output changes.
- Running servers and runners keep the old code until restarted; say so in the report.
