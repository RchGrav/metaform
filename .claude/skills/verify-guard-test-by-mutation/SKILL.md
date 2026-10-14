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
- A regression test for a fix gets the same proof: copy `src`, `conftest.py` and `pyproject.toml` to a fresh `/tmp` folder, revert only your own fix lines there, run the test from the copy with `PYTHONPATH=<copy>/src`, and confirm it fails on the defect's own assertion (not an import or setup error). Then make that assertion name the exact output the fix must keep: a check that matched a later reply passed while the lost earlier reply was missing, so it only counts as proof once it requires the held text. Then run it on the fixed tree and confirm it passes. Delete the copy.

Worked example: `references/guard-mutation-example.md`.
