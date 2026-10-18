---
name: partial-commit-in-shared-tree
description: Use when committing in a tree other agents are editing.
category: git-workflow
---

# Commit only your own hunks in a shared tree

Never `git stash`, `git add -A` or `git commit -a` in a checkout another agent is editing. Build your commit from a temporary index so the other edits stay exactly as they were.

1. Make the change and its commit in your own worktree, then export it with `git format-patch -1 --stdout > <patch>`.
2. On the shared tree, use `GIT_INDEX_FILE=<tmp>`: `git read-tree HEAD`, `git apply --cached <patch>`, `git write-tree`, `git commit-tree <tree> -p <old HEAD> -F <message>`, then `git update-ref` from the old HEAD to the new commit. Unset `GIT_INDEX_FILE` and delete the temp index.
3. Confirm with `git status --short -- <your paths>` that only other agents' edits remain, and that the commit stat lists only your files.
4. If a shared test file has moved, a patch hunk can fail. Apply the hunk by hand, then diff the added tail against your worktree's version before running tests.
5. Remove your scratch worktree and branch only after the commit is confirmed.

Record the commit hash and the rollback (`git revert <hash>`) in the ticket note.
