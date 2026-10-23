---
name: failing-test-predates-change
description: Use when a test failure or fault may predate your change.
category: development
---

# Prove a failure predates your change, in a throwaway worktree

Before you call a red test pre-existing, or a reported fault already fixed, run the same test at the base commit (or the commit before the fix) in a temporary worktree and read the result. Do not judge it from memory or from the current tree alone.

1. Find the commit: `git log --oneline -S 'SYMBOL' -- FILE` shows the change that introduced or fixed the behaviour.
2. Create the worktree outside the repo: `git worktree add /tmp/mf-prefix-SHORTSHA COMMIT`.
3. Run only the named test there, in that worktree's own environment: `cd /tmp/mf-prefix-SHORTSHA && uv sync --extra dev && .venv/bin/python -m pytest -n 0 path/to/test_file.py -k test_name`. Plain `uv run pytest` inside a worktree runs the main checkout's code, so it proves nothing.
4. Run the same test at HEAD. Record both results in the ticket: the failure at the old commit and the pass at the new one.
5. Remove the worktree: `git worktree remove --force /tmp/mf-prefix-SHORTSHA && git worktree prune`, then `git status --short`.

Run only the single test or its file, never the full suite. A test that fails identically at the base commit is pre-existing: file it as a broken ticket that names that commit.

Worked case (2026-10-21, ticket code.router.assignment#31): `test_personal_start_releases_only_requested_backlog_ticket_before_routing` failed with `Failed: Unassigned worker started` at the pre-fix commit 84ab4782 and passed at HEAD ac9ad302, so the fault was already fixed and no code changed.
