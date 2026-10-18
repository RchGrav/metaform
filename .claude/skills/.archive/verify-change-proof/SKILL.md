---
name: verify-change-proof
description: Use when proving a guard, install steps or schema change.
category: development
---

# Prove a change by watching it fail, or on planted copies

Do not trust a green guard test, a clean install or a store upgrade until it has been seen to fail on its defect, or has run on planted copies that are not the person's real home.

## Guard tests and regression tests
- A guard that walks source or declarations is proven by flipping one real declaration to the wrong value in a scratch copy, or with `dataclasses.replace` in the test. The reported set must equal the flipped items. Items the walk cannot see go on an explicit allow-list with a reason, and the count of blind items must equal that list. A walk that reports nothing is blind: widen it, then repeat. Worked example: `references/guard-mutation-example.md`.
- A regression test is proven on a `/tmp` copy of `src`, `conftest.py`, `pyproject.toml` and fixtures, with only the fix's own lines reverted, run with `PYTHONPATH` naming the copy's `src`. It must fail on the defect's own assertion, not an import or setup error. Where another agent's uncommitted work holds the fix, take the before copy from `git show HEAD:FILE`. Order the assertions so the defect's check runs first.
- Never edit a shared file in place to probe it. Put probe prints and mutants in the `/tmp` copy, or in a scratch `-p` plugin outside the repo. Restore a line by exact string replacement, never by copying a saved file back.
- A mutant must differ in byte size from the original (a same-size rewrite reuses the stale `.pyc`), and must fail on the assertion the defect should trip: read the `>` and `E` lines.
- A race is proven by repetition: 5 runs before and 5 after, with enough workers that the unfixed code fails most runs. Report both counts.
- A platform branch (`sys.platform == 'win32'`) passes on Linux whatever the fix. Force the branch in a spawned child, and name the platform's CI job as the check that did not run.
- Read the selected count, `N selected`. A line of only `9 deselected` means the test never ran.

## Install steps in a scratch home
- Follow the written guide literally, step by step, under `env -i HOME=SCRATCH PATH=COPIED_TOOLS:/usr/bin:/bin TERM=dumb`. Copy `uv` out of the real `~/.local/bin` first, because that folder also holds the tool under test.
- Give the build and the app their own scratch data home, never the real one. Record `[exit $?]` after each step and name each expected failure in the script.
- Finish with the guide's own uninstall, then confirm the command is gone and the home is removed.
- Strip `DISPLAY` and `WAYLAND_DISPLAY`, set `BROWSER=true`, and feed stdin from a silent pipe.
- Snapshot the real home read-only before and after, and report "no difference" only when the diff is empty.
- Read the README the build actually shipped (unzip it), not the generator's output. Compare with HEAD in a detached worktree, and remove the worktree afterwards.
- List what was not exercised, such as a live AI-tool connection or a command that opens a browser. Never claim it passed.

## Store and schema changes
- Prove on planted copies: old code from `git archive HEAD src`, new code from the working tree, each case on its own copy of the seed. Compare `sqlite_master` SQL, row counts per table and the backup count. Recipe and pitfalls: `references/store-change-proof.md`.
- A version bump is live the moment any process opens the store. List the running Metaform processes first, restart them, and confirm each one acts on the refusal, not only logs it.
- A bump the previous code can still read sets `compatible_from` to the last version that reads it, and is proven by running the old source against an upgraded copy.
- Any change to a CHECK, foreign key, collation or conflict rule is a schema change. It needs approval and a raised version.
- Count what an upgrade creates (elements, links) per project before and after. Migrate a copy of the live store first, and say whether a live migration can be reversed.
