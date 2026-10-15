---
name: verify-store-schema-change
description: Use when changing a store schema, store version or upgrade, or when a store refuses writes with "schema version".
category: development
---

# Prove a store or schema change on planted copies

A change to a module's tables, store version or upgrade path is proven only by opening planted copies of a store with the old code and with the new code, then comparing schema and row counts. Never open the person's real home, or a copy of it that points at real project folders.

- Old code comes from `git archive HEAD src`, new code from the working tree. Each case runs on its own copy of the planted home, with `PYTHONPATH` naming the source it means.
- Compare before and after: row counts per table, `sqlite_master` SQL in name order, and the backup count. A change that should be a no-op (a reorder, a moved constant) must leave all three identical.
- A planted edit that fails midway leaves a half-changed store: restore the seed before the next case.
- A version bump is live the moment any process opens the store. Before raising it, list the Metaform processes still running old code (web GUI, MCP server, runners, `hold list`). Each one refuses writes at the new version until restarted, so restart them and confirm each answers before reporting the change done. An agent cannot restart a running MCP server or web GUI itself: when the agent's own MCP server refuses a write at the new version, record through the CLI (`uv run metaform ...`, which runs the current code) as a stopgap, say in the report that the server needs a restart, and never call the CLI a fix. Migrate a copy of the live store first, and report what a live migration did and whether it can be reversed before running it. A ticket that bumps a version repeats this rule in its own text. A worker that migrates the live store anyway stops and reports before anything else changes: on 2026-10-15 a ref ticket raised the live store to schema 22 against its own copy-first instruction, and processes still on 21 could not record progress until restarted.

- Compare the whole rule set a write must meet, not just the column and index lists: CHECK clauses, foreign keys (with ON DELETE/UPDATE), collations, ON CONFLICT resolutions, generated columns, unique and partial indexes. Clauses compare as SQL tokens, so spacing, quoting, keyword case and comments never count as a difference; a changed meaning does.
- Changing any of those rules is a schema change: it needs the orchestrator's approval and a raised version, or an open store that already holds the old rule fails at its first write instead of being refused at open.
- The snapshot guard records the same fields. Prove it by mutating each kind on a scratch tree (a CHECK, an ON DELETE, a partial WHERE, a COLLATE) and watching it fail, and by a reworded but equivalent clause passing.
- Prove no good store is refused: run the open-time state check for every shipped module over byte copies of the person's stores in a scratch home, before and after, and require identical results.
- SQLite reserves `sqlite_autoindex_*` names: a declared UNIQUE constraint the store lacks cannot be re-created under that name (`object name reserved`). Give it an explicit index name.
- Count what an upgrade creates, not only its schema. A migration that adds map elements, nodes or links changes behaviour: report element and link counts per project before and after, and read the upgrade report and backups under `~/.metaform/backups/upgrade-<n>/<project>/`. An element created with no role and no joins is a defect even when every schema check passes.

Recipe and the pitfalls seen on 2026-10-15: `references/store-change-proof.md`.
