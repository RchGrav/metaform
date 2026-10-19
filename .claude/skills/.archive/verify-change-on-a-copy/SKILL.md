---
name: verify-change-on-a-copy
description: Use when verifying a UI, benchmark, SQLite write, or setup.
category: development
---

# Verify a change on a copy, against a control

A check proves something only when the untouched side ran through the same path as the changed side, everything that moves is held still or measured under a stated load, and the result is counts or numbers rather than impressions. Run every risky check on a copy you can delete before it touches the shared tree or a live store.

## Pick the section that matches the check
- A UI must look the same, browser waits, stacking order, slow page loads, timed windows: `references/ui-browser-checks.md`. The pixel comparison is `scripts/pixel_diff.py BEFORE AFTER --mask x0,y0,x1,y1`.
- A benchmark, frame p95/p99, or a test window on a busy host: `references/timing-on-a-loaded-host.md`.
- A row-changing cleanup of a live SQLite store or Metaform home: `references/live-sqlite-cleanup.md`. The snapshot is `python -I scripts/snapshot_store.py ROOT`.
- A setup script or devcontainer checked against uv.lock: `references/setup-script-clone.md`. The parity check is `scripts/check-lock-parity.sh`.

## Rules across all four
- Run the control first: HEAD against HEAD must come out identical, or the comparison proves nothing.
- Keep before copies and backups where a restart cannot wipe them: inside the project, or in a timestamped folder outside the live home. Not `/tmp`, which a machine restart emptied mid-ticket.
- Never stash, reset or restore over a shared tree. Copy aside, or use a detached worktree, and diff against the copy afterwards.
- A store change that bumps a schema or table version runs its upgrade on the live home the first time any process starts from the edited tree (a Metaform MCP server, a runner, a web server), not when you run your dry run. Before starting any such process from the edited tree, copy the live store, run the upgrade on the copy, and read its counts. A backup the data layer took at the upgrade is a copy source only for the pre-upgrade state.
- Report the numbers, the load (`uptime; nproc`), the round or run count, and every check that did not run.
- Delete each temporary copy, then confirm with `ls -d`.
