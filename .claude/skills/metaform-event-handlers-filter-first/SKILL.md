---
name: metaform-event-handlers-filter-first
description: Use when map.changed handlers, a runner or the web server burn idle CPU, sleep-poll, or re-read the store on every event.
category: development
---

# Metaform event handlers filter first, then read one record

A handler decides from the event alone whether it concerns it, and does no store read for an event that does not. Idle CPU that rises with the event rate means a handler reads on every event; look there before looking for a loop.

- Writes say what they concern. `map.changed` carries `work_ids`, `session_ids` and `kinds`, each a sorted list. A field present means that dimension is fully known; absent means unknown, so the handler falls back to `tables`. Design and call sites: `references/concern-fields.md`.
- Filter order: the handler's own ticket or session named, act; other tickets or sessions named and nothing else, skip; nothing named, act only when the event touches a table the handler reads.
- Read one record, not the collection. A step on your own ticket reads that ticket; a burst of changes for other sessions reads zero records.
- Never react to your own writes. Events that arrive during pending work merge into that work.
- Set a "something to write" flag only when the event moves the state it guards. A reader's start event that found the position already written set `dirty` anyway and cost one extra write a second after every start (autoticket watch, 2026-10-15). Compare the event's identity and offset with what is held before setting the flag, and test that a no-change start writes nothing.
- Coalesce bursts of your own ticket's changes: a check that is running takes one flag for the changes that arrive meanwhile (`checking` / `check_again`) and runs one more pass after it, never one spawned check per event. `Session.checks` in `dispatch/runner.py` does this; `workflow_answers` does the same with `workflow_reading` / `workflow_again`. A burst of 50 own changes must cost at most twice one change's reads (test it; the unfixed spawn-per-event version gave 50 reads for 50).
- Writes that change no table still name their concern: `changed(tables='dispatch', kinds=['session'])` for a session going busy or idle, the intake phase, an answered question. A `kinds`-only event tells a reader of other kinds to read nothing.
- Known open reads, on the handler's own events only: `answered()` reads every question at its node because the store cannot read one message by id; `workflow_read` reads runs by state because the workflow module has no one-run read and its pause and answer events do not name the run. Fixing either is a change to the map or workflow module, not to the handler.
- Waits are events, not sleeps: `events.listen` for a change naming the thing awaited, or an `asyncio.Event` set by the code that produces it, plus the process exit. Deadlines (silence clock, retry backoff, pacing) stay timers and are named as such.
- Sweep a folder for polling by its sites: `setInterval`, a `setTimeout` inside a check loop, `time.sleep(`, and `for (;;)` or `while` loops that await a timer. Classify each. A stream reader (`reader.read()` looping until `done`) is not polling and stays; so do real deadlines, retry backoff and pacing. Anything that only looks for a state change becomes an event. Pin the kept set in a guard test (see `verify-guard-test-by-mutation`) so a new timer fails it.
- A health or status heartbeat is replaced by asking at the events that say the thing may have gone or come back (a stream's error or open, a failed read), never by a clock.
- A "reads nothing" test opens its quiet window on a signal the code emits (a `threading.Event` set when the store-touch count reaches the point where the setup has settled), never on a fixed sleep. A 1.5 s sleep passed alone and failed in a combined run, because the lease and first write landed after it. Run the new idle tests together with their file once, since load moves timing, and confirm the window still fails on HEAD's files.
- A dirty flag is set by a change, not by an event's arrival. A watcher's start event that reports the position already written must not mark the watch dirty, or every start costs a write. Compare the new value with the recorded one, then set the flag.
- Long-lived servers: uvicorn's `Server.main_loop` wakes ten times a second even when idle. Override it to await an exit `asyncio.Event`; make `should_exit` a property whose setter sets that event (uvicorn's `handle_exit` assigns it), and set a ready event at startup. Keep one shared copy in the chassis, not one per module.
- Before keeping a timer for an upstream, read how the upstream's own UI gets its updates. Paperclip's pages follow a live-events WebSocket (`/api/companies/{id}/events/ws`, `activity.logged` naming the entity id); a timed sync was the wrong design. A timed fallback is kept only for a server that answers the stream with 404.
- Waits on a Windows file lock use the blocking OS call (LockFileEx without LOCKFILE_FAIL_IMMEDIATELY), not a try-lock loop with a sleep.
- Prove it before and after: per-process CPU from `/proc/<pid>/stat` (utime + stime) over 60 s at the live event rate, plus a test where a burst of unrelated events causes zero reads (count `Store._read`). Method: `references/concern-fields.md`.
