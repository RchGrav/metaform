# Cleaning up a live SQLite store (Metaform home)

Use this file for any row-changing cleanup of a live store, or a one-off write script against a live Metaform home (`~/.metaform`). Rehearse every such change on a copy first, diff a snapshot before and after, and only then run it on the live file. Snapshot script: `scripts/snapshot_store.py`.

## Read first, on a copy
- Look at a live store read-only: open it with `sqlite3.connect('file:<path>?mode=ro', uri=True)`, list `pragma table_info` for each table, and count rows per table. Never open a live store in write mode just to inspect it.
- Copy the store with its `-wal` and `-shm` files (`cp -a`), so the copy holds every committed row. A store a process may have open: copy it with SQLite's backup API instead, then run the repair on that copy.
- A Metaform home is several stores: copy the home's `metaform.sqlite3*` to a scratch root, and each project's store files under `projects/<id>/` beneath it, then run the script with `METAFORM_HOME=<scratch>` and `python -I`.
- Projects register by their folders, not in the home database. A scratch home without each project's `project.sqlite3` lists no projects.
- Name any helper script something other than `copy.py`: it shadows the stdlib `copy` module that `metaform.home` imports.
- Learn a write verb's arguments from its help or on the copy, never with a placeholder value on the live store (`add-item value="x"`). A verb that accepted the placeholder would have written.

## Snapshot, dry run, diff
- Snapshot before and after with `python -I scripts/snapshot_store.py ROOT`. A row-only cleanup changes count lines only for the tables it writes. A changed schema hash, or a count moving in a table the cleanup never writes, stops the run.
- Have the script read back the records it must not touch and assert they are unchanged before it prints success.
- Dry-run on the copy first and check the printed number against your own count query.
- Read one changed record back on the copy, including its reason text.
- Close legacy records with a status and a reason; never delete them. Retiring a knowledge layer is `Store.discard` (STORE-032): it appends one remove op per item and one for the layer, and deletes no rows. Check the copy diff for ops gained and no table rows lost.

## Versioned stores
- In a versioned store, a current-state read shows the new value while the op log still holds the old one. Verify the live result by reading each changed record's history back, and count the old and new values there, not only the current row.
- The store's own op log is the source of the pre-change state. A remove version keeps the old fields and pairs; build a repair from that log and check it against the backup, not from a remembered count.
- Discarded items have no versioned history, so `map history` on one answers that the id does not exist; read the op log instead.
- Compare every base's rows place for place with the pre-change state before the live run.

## The live run
- Other agents may write the live store during the run. A count that moves in an unrelated table (an event log, for example) is a concurrent write, not a regression; name it in the report.
- Before the live write, copy each live store file set to a timestamped folder outside the live home, on disk a restart does not wipe (not `/tmp`), and name that folder in the report.
- Count the live candidates the same way as on the copy and report the number.
- Make the live run idempotent: a second dry run on the live file must find nothing to change before the run is reported done.
- A change that lets autostart or a scheduler act on records already present runs them the moment it lands: count live candidates from the real home, read-only, before it lands.
