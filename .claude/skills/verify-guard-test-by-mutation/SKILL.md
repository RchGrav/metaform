---
name: verify-guard-test-by-mutation
description: Use when a guard test scans source or declarations, or a regression test must be shown to fail without its fix.
category: development
---

# Prove a guard test can fail before trusting it green

A test that walks code to enforce a rule is only evidence once it has been seen to fail on a deliberate violation. Flip one real declaration to the wrong value in a scratch copy or with `dataclasses.replace` inside the test, run it, and confirm it reports exactly that item. If it reports nothing, the walk is blind to that kind of call: widen it, then repeat.

- Assert the reported set equals the flipped items, not just that the test fails.
- Every item the walk cannot see goes on an explicit allow-list with a reason. Silent gaps are the defect.
- Assert the count of "no sink found" items equals that allow-list, so new blind spots fail the test.
- Never leave a changed declaration in the shared tree.
- A regression test for a fix gets the same proof: copy `src`, `conftest.py`, `pyproject.toml` and `tests/fixtures` to a fresh `/tmp` folder (a test that reads a fixture fails with `FileNotFoundError` without it, a setup error that proves nothing about the defect), revert only your own fix lines there, run the test from the copy with `PYTHONPATH=<copy>/src`, and confirm it fails on the defect's own assertion (not an import or setup error). Then make that assertion name the exact output the fix must keep: a check that matched a later reply passed while the lost earlier reply was missing, so it only counts as proof once it requires the held text. Then run it on the fixed tree and confirm it passes. Delete the copy. When another agent's uncommitted work already holds the fix in the shared tree, the "before" copy must come from `git show HEAD:<file>` for each file the fix touches, plus only the test's own seam (for example a module-level hook the test sets), so a green run on the shared tree proves nothing about the fix; a failure there on the defect's assertion is the proof. Report the copy's result, not the shared tree's. For a fix that changes how many requests a cached call sends, the test's stub must refuse (raise) rather than answer: an answered call is cached for minutes and hides the second request, so the "before" run shows one request where it should show two. Measure the before and after counts from the same test, and the copy's `PYTHONPATH` must win over the editable install.

- To find which of several code paths acted (a subscription, a listing, a follower), put the probe prints only in the `/tmp` copy, never in the shared tree. Editing a shared file in place and restoring it with `cp` still races another session's writes to that file. Read probe output from the run's returned stderr, since the run fixture swaps `sys.stderr`, and confirm with `grep -c` that every probe marker is gone from each file touched.
- A new verb or declaration can trip a registry test: an allow-list of items the walk cannot see, such as `UNSEEN_OPEN_WORLD` in `src/metaform/modules/mcp/tests/test_mcp.py`. Add the entry with a one-line reason, as the sibling verb has one; do not loosen the walk. Run the registry tests by `-k` name, not the whole suite.

- A race is proven by repetition, never one run: run the test 5 times before and 5 times after the fix, with enough concurrent workers that the unfixed code fails most runs (two workers failed 2 of 5 on 2026-10-14, four failed 5 of 5). Report both counts.
- A mutant proves a test only when it fails on the assertion the defect should trip. Read the `>` line and the `E` line of its output: an `AttributeError` or `ImportError` raised by the mutant itself is a false proof, so fix the mutant until the failure is the assertion's.
- An "is absent" check passes vacuously when the code never writes that path. Before trusting it, grep the writing function for the path it actually uses, and confirm a mutant that writes there makes the check fail.
- When the defect's original code was never committed, no git history holds it: write a mutant that reproduces the old behaviour at the one line that differs. Copy the file aside first, restore with `cp -p`, and confirm `cmp` is byte-identical; never `git stash`.

Worked example: `references/guard-mutation-example.md`.
