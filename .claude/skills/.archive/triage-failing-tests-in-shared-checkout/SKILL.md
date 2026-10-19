---
name: triage-failing-tests-in-shared-checkout
description: Use when a pytest run is red: rerun alone before blaming.
category: testing
---

# Triage a failing test before blaming a change

Before calling a red test a regression from your change, rerun each failing test id alone with `uv run pytest -n 0 FILE -k NAME`. A test that passes alone but fails in a full xdist run is a load-sensitive or wall-clock-timed failure: name it as that, with its assertion, and do not report it as a regression.

For a test that still fails alone, in this order:

1. Check it at its base commit in a detached worktree (`git worktree add -q --detach $TMP BASE`), with `PYTHONPATH=$TMP/src` and the project venv. Print the package `__file__` first to confirm the copy loaded. If it fails at base, it predates your change: say so and name the commit.
2. Attribute it to another agent only when `git diff -- FILE` shows that agent's hunk in the code the failing assertion exercises. For an untracked file, cite its `git status --short` line and its mtime from `stat -c %y`, not a guess about who wrote it.
3. Prove a suspected cause on a copy with the suspect file swapped back to base. Do not swap files in the shared tree.
4. Report every run with its summary line (`N failed, M passed`), including the failing ones. Pipe through `tail`, not `head`, so the summary is not cut off.
5. A failure nobody on your ticket caused is filed as a ticket at the element that owns the file, with the failing ids, the commit each was checked at, and the check that proves it fixed.

Do not write a memory or ticket note naming a cause until step 1 has run. On 2026-10-19 the compacted-turn test was first blamed on a peer's typed change; the base commit `c4f449fc` showed it failing too, and the note had to be corrected.

Regression proof (remove the fix, watch the named assertion fail) is in the `regression-test-mutation-check` skill.
