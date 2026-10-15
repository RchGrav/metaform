# Concern fields on map.changed

What each field means and where it is set (code.dispatcher.agent#38, 2026-10-15).

- Chassis writes tag a write with `Tx.concern(work_id=, session_id=, kind=)` inside the write. `Session.write` hands `tx.about` to `changes.note`, which merges per base like `tables`; `take()` moves them to `_TAKEN`, and `announce` adds `changes.concerns()`.
- One untagged write in the same command leaves `work_ids`, `session_ids` and `kinds` out of that event, so the event is treated as unknown.
- `map/storage.py` tags every ticket write (kind `ticket`) and every message write (kind `message`, with the ticket a question is linked to through `question_work`). Module-table writes through `store.tables()` are untagged, so a workflow pause or answer arrives with `tables` set to `workflow.*` and no ids.
- Dispatch publishes add the fields with `signals.concerning(work_id, session_id, dispatch_tables, signal)`. Kinds come from `KINDS` (dispatch.lines `line`, permissions `permission`, sessions and settings `session`, spending `spend`) plus the signal. An unknown table leaves `kinds` out.
- The runner filter is `runner.concerns(payload, work_id, session_id, tables)`.

Measurement method:

- Live home, read-only: count `map.changed` per second by kind, and CPU per idle runner from `/proc/<pid>/stat`.
- Scratch home in `/tmp`: 10 idle runners on the fake agent, each with its own session id (the fake's `SESSION` must not be shared, or the second runner fails with `UNIQUE constraint failed: dispatch.sessions.session_id`). Replay the live kind mix at the measured rate for 60 s; record mean and max per runner.
- Run a variant with the old payload shape (no ids), since runners not yet restarted still send it.
- Before-copy: a `/tmp` copy of `src` with only your handler edits reverted, loaded with `PYTHONPATH` (not `-I`), and check `module.__file__`.
