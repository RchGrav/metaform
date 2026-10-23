---
name: metaform-git-commits
description: Use when committing or pushing Metaform code to GitHub.
category: development
---

# Metaform git commits

Commit each finished feature or ticket as its own commit, named for that feature. Never lump several tickets' work into one commit, because the person reviews the code on GitHub one feature at a time.

- Before committing, read `git status`. Stage only the files that belong to the feature. Leave another agent's uncommitted edits alone.
- When the person asks for GitHub, push to `origin main`. Pull with `git pull --no-rebase` so history is not rewritten.
- Never run `git stash` in the shared tree.
- When the person asks to discommit, undo the commit and keep the files on disk. Do not start re-splitting commits unless asked.
- If `git pull --no-rebase` stops on a conflict in a shared file such as a module `CHANGELOG.md`, keep both sides' entries (each keeps its own dated heading), `git commit --no-edit`, then re-run ruff, pyright and the touched tests on the merged code before pushing. The merge brings in a peer's commit that was never tested with yours.
- Finished tickets commit themselves: a completion makes the commit and pushes it, without a request from the person. When a finished ticket has no completion commit, that is a fault. File it as a broken ticket at the dispatch merge element and tell the person. Do not commit its files by hand, and do not wait for the person to ask. A fix found after that completion commit is not a completion and nothing will commit it: do not leave an uncommitted edit in the shared tree. Revert it, then route the fix to the peer whose ticket is still working that file (`dispatch note` with the file and the fix), or file a new ticket at the element that owns it.
- Commit and push only what the person asked for, or a finished ticket's own completion commit. A rejected tool use is a stop, not a go-ahead: do not route the same change through a commit and push instead.
- Before a push, run `git log --oneline origin/main..HEAD`. A `git push origin main` sends every local commit ahead of origin, not only the commit you made. If the list holds commits that are neither the person's request nor your own finished ticket, do not push them: report them and ask. On 2026-10-21 a push of one fix also sent 25 other tickets' completion commits that had been ahead of origin.
- A push is done only when `git push` exits 0 and the branch matches origin. Never hide the push's stderr with `2>/dev/null`; a failed push is reported as failed.
- Ticket worktree branches (`metaform/<id>`) begin with a "Snapshot of uncommitted work for ticket ..." commit that copies the shared checkout's uncommitted files into the branch. That commit is not the ticket's work. Before reviewing or merging a branch, list its commits with `git log main..<branch>` and take only the ticket's own commits, leaving the snapshot out. A branch whose only ahead-commit is a snapshot has no work to merge. Why: on 2026-10-21 a merge review held all eight done tickets because every branch carried unrelated skill and prompt edits from the shared tree.
- A finished ticket's completion commit sits on its branch `metaform/<id>`, not on `main`. Before saying a fix is on main, check with `git branch --contains <hash>` or `git log --oneline main`. On 2026-10-21 ticket #76 was marked done, but its two commits were on `metaform/1fc526dfa0f9` only, and local `main` held just the first one.
- A worktree ticket's landing can stop with `error: Untracked working tree file '<path>' would be overwritten by merge`. The untracked copy in the main checkout is the blocker, not the ticket's commit. Before anything moves, compare it byte for byte with the committed copy (`git show HEAD:<path> | cmp -s - <path>`); move it aside only when it matches, and name the move in the ticket step. On 2026-10-21 the roundtable follower wrote `export.json` and `mechanical-report.md` untracked into the main checkout, and ticket code.system.management.knowledge#98 hit this at its landing.
- A commit subject is one line of about 72 characters or fewer that names the change. The ticket reference, the reason and the detail go in the body after a blank line. A subject that carries a whole paragraph is an oversized commit message; a dispatch ticket in this repo was opened to fix exactly that in `merge.py`.
- Report the commit hashes you pushed, and nothing more.
