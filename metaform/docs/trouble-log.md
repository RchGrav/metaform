# Trouble log

Notes on commits that broke something after they landed, as `context/topogee-repo/AGENTS.md` ("Feature commits") requires. Each entry names the commit, what broke, and the commit that fixed it. No commit is rewritten. The earlier log is `context/topogee-repo/docs/trouble-log.md` (read-only).

## 2026-11-09: f27cbe4 committed the agent notes folders

- **Commit:** f27cbe4, "Send store failures to agents in the refusal structure (INTERNAL_ERROR)", by Marcus, on branch `store-failure-error-structure`, pushed to `origin` (`RchGrav/metaform`).
- **What broke:** the commit also added `.ida/`, `.jorge/` and `.marcus/` (10 files of agent working notes). Those folders are meant to stay local. They hold no credentials.
- **Cause:** the ignore lines for those folders were committed only on branch `tools-list-size-baseline` (06d31e3). Marcus checked `git status` on that branch, switched to `main`, where the folders are not ignored, and ran `git add -A`.
- **Fix:** the next commit on `store-failure-error-structure` adds the same ignore lines and removes the folders from the index. The files stay on disk and in f27cbe4's history.
- **Lesson:** run `git status` after switching branches and before staging; stage named paths, not `git add -A`.

## 2026-11-10: grammar rules added to the tool without the owner's instruction, and reverted

An agent added a check on the `why` and `how` of a want to the Rust, Node and Python forms (commits `c537aac`, `20b8ffe`, `01a0bca`, `128eb01`): a refusal for the first word, for more than one sentence, for a number, and for more than 14 words. The owner had not asked for it. The semantics of the map are the owner's, were tested by the owner over months and across artifact types, and are described in the owner's preprint, which the agent had not read. The four commits are reverted by `ac480f5`, `2c074fd`, `9ae87f0` and `4424dbf`. After the revert: 69 Rust tests, 5 Node tests and 5 Python tests pass, and conformance is 23 cases, 373 steps, 0 differences in each form, as before the check.

The same agent also performed its test intakes with a brief of its own around `Intake.md`, and in one round told the intake agents to record more elements. Those maps (homes `~/.metaform-climb` to `~/.metaform-climb5`) are not evidence about the owner's procedure.

