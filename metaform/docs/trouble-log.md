# Trouble log

Notes on commits that broke something after they landed, as `context/topogee-repo/AGENTS.md` ("Feature commits") requires. Each entry names the commit, what broke, and the commit that fixed it. No commit is rewritten. The earlier log is `context/topogee-repo/docs/trouble-log.md` (read-only).

## 2026-11-09: f27cbe4 committed the agent notes folders

- **Commit:** f27cbe4, "Send store failures to agents in the refusal structure (INTERNAL_ERROR)", by Marcus, on branch `store-failure-error-structure`, pushed to `origin` (`RchGrav/metaform`).
- **What broke:** the commit also added `.ida/`, `.jorge/` and `.marcus/` (10 files of agent working notes). Those folders are meant to stay local. They hold no credentials.
- **Cause:** the ignore lines for those folders were committed only on branch `tools-list-size-baseline` (06d31e3). Marcus checked `git status` on that branch, switched to `main`, where the folders are not ignored, and ran `git add -A`.
- **Fix:** the next commit on `store-failure-error-structure` adds the same ignore lines and removes the folders from the index. The files stay on disk and in f27cbe4's history.
- **Lesson:** run `git status` after switching branches and before staging; stage named paths, not `git add -A`.
