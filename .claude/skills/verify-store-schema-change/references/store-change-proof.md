# Store change proof: recipe and pitfalls

Set once:

    V=$(mktemp -d); REPO=/home/rich/metaform; R=$REPO/.venv/bin
    M="env -u METAFORM_ROLE -u METAFORM_SESSION -u METAFORM_WORK -u METAFORM_NODE"

1. Old code: `mkdir -p $V/old && git -C $REPO archive HEAD src | tar -x -C $V/old`. New code is `$REPO/src`. Print the package's `__file__` under each PYTHONPATH to confirm which source loaded.
2. Seed: a fresh `METAFORM_HOME=$V/home`, the module enabled (a disabled module declares no tables, and a store read then raises `declares no tables`), `home.ensure_base(project)`, rows written with the OLD code through `Store(project, module=ID).tables()`.
3. Plant a state in both stores: the project's `main.metaform.sqlite3` (the `meta` row `module:ID` holds JSON with `version` and `tables`) and the module's own `modules/ID.sqlite3`. A version change edits `version`; a dropped table is dropped and its entry removed from `tables`. Do both files, or the record and the schema disagree.
4. Each case: copy the seed to its own folder (`cp -a $V/home $V/h-CASE`), then run `$M METAFORM_HOME=$V/h-CASE PYTHONPATH=SRC $R/python -m metaform MODULE VERB`. Run seed and report scripts with `-I`.
5. Compare: `SELECT name, sql FROM sqlite_master WHERE name LIKE 'MODULE.%' ORDER BY name` before and after, then `cmp`. Count rows in every table. `ls backups`: an upgrade adds one backup; a no-op change adds none.
6. Conflict case: retype a key column by rename, create the new table, copy rows across, drop the old one. Pitfall: copying text ids into an INTEGER column raised `sqlite3.IntegrityError: datatype mismatch`, and the first attempt left the store half-renamed. REAL planted the conflict cleanly. The expected refusal names the table and column, says nothing of the module changed, and gives one next step. Rows and schema must be unchanged after the refused call.
7. Confirm the rest of Metaform still answers: a map read of a node returns its rows, and the page's read routes answer on a scratch port. Start the server through its module entry point, not the launcher, so a launcher fault cannot mask the result.
8. Stop by recorded pid (`kill $PID`). `pkill -f PATTERN` matches the shell that runs it when the pattern is in its own command line, and exits 144.
9. Guard test: a column added with no version bump must fail the snapshot guard, naming the module; a reorder must pass. Give each mutant variant a different byte size (see `verify-guard-test-by-mutation`).
10. A start that fails with no log because a sibling's uncommitted module file is broken: follow `shared-checkout-concurrent-edits`, then say so in the ticket note.
