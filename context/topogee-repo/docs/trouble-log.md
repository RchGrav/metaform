# Trouble log

Notes on commits that broke something after they landed, as `AGENTS.md` ("Feature commits") requires. Each entry names the commit, what broke, and the commit that fixed it. No commit is rewritten.

## 2026-11-07: ba1c768 reverted two of Xander's document edits

- **Commit:** ba1c768, "Add the acceptance check for the founder's definition of done", by Jorge.
- **What broke:** the commit also undid 41ecdeb's edits to `.design-review/README.md` (3 lines) and `docs/designs/world-system-spec.md` (11 lines, the opening that describes what is built).
- **Cause:** to squash two local commits, Jorge ran `git reset --soft origin/main` after `origin/main` had moved ahead of the branch's base. The index then held the reverse of the newer commit's changes, and `git commit` committed the whole index, not only the files Jorge had added.
- **Fix:** the next commit restores both files exactly as 41ecdeb left them. The acceptance check itself was not affected.
- **Lesson:** squash with `git reset --soft <branch base>`, never with a moving remote. Before every commit, check `git diff --cached --stat` and stage only your own paths.
