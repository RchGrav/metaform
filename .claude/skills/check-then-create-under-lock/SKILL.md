---
name: check-then-create-under-lock
description: Use when parallel calls race to check then create a thing.
category: development
---

# Check and create under one lock

A check that reads state and the create that writes it must sit inside one cross-process lock held across both. Two transactions with a gap between them let two parallel callers both pass the check and both create.

- Take the lock with `home.file_lock(path)` (`with` block; released when the process ends, crashes included). Lock a file that is never replaced or removed.
- Re-read the state inside the lock and create only while it is still empty. A caller that loses the race resumes what the winner made and says so in a notice.
- Put the closing step (finish, activate) under the same lock, so it closes the state the lock holder built.
- The fast path (state already present) may skip the lock; only check-and-create takes it.
- Read the state inside the lock too: a read taken before the lock can still write after a concurrent close.
- Reproduce before fixing: start N workers that call together, raising N until the unfixed code fails in most of 5 runs. Repeat 5 times before and after, and report both counts.
- A file swap is a check-and-create too: copy a store, then move the copy over the old file. Put the layout check and the swap under one lock file beside the store, and have the lock holder re-read the state on a fresh connection before copying, so a waiter returns the already-upgraded file instead of copying again.
- SQLite: `db.backup()` from a connection inside its own `BEGIN IMMEDIATE` never returns (SQLite reports LOCKED and Python retries forever), and `PRAGMA wal_checkpoint(TRUNCATE)` is refused inside that transaction. Hold the write lock from a separate guard connection through the copy and the swap, then backfill with `PRAGMA wal_checkpoint(PASSIVE)` until its log and checkpointed counts are equal.
- Give each opener its own temp file names (pid plus random hex). Remove leftovers from a crashed run only while the lock is held.
- A test of a WAL-mode branch needs a WAL-mode fixture. A rollback-journal store passes the same test without touching the backfill.
