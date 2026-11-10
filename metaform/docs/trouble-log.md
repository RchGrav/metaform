# Trouble log

Notes on commits that broke something after they landed, as `context/topogee-repo/AGENTS.md` ("Feature commits") requires. Each entry names the commit, what broke, and the commit that fixed it. No commit is rewritten. The earlier log is `context/topogee-repo/docs/trouble-log.md` (read-only).

## 2026-11-09: f27cbe4 committed the agent notes folders

- **Commit:** f27cbe4, "Send store failures to agents in the refusal structure (INTERNAL_ERROR)", by Marcus, on branch `store-failure-error-structure`, pushed to `origin` (`RchGrav/metaform`).
- **What broke:** the commit also added `.ida/`, `.jorge/` and `.marcus/` (10 files of agent working notes). Those folders are meant to stay local. They hold no credentials.
- **Cause:** the ignore lines for those folders were committed only on branch `tools-list-size-baseline` (06d31e3). Marcus checked `git status` on that branch, switched to `main`, where the folders are not ignored, and ran `git add -A`.
- **Fix:** the next commit on `store-failure-error-structure` adds the same ignore lines and removes the folders from the index. The files stay on disk and in f27cbe4's history.
- **Lesson:** run `git status` after switching branches and before staging; stage named paths, not `git add -A`.

## 2026-11-10: the intakes of 2026-11-09 stored whole sentences in `why` and `how`

- **Commit:** none broke this. The rule was never built: `GRAMMAR_CONSTRAINT_VIOLATION` existed by name only in the three forms, and its rule text said "Not checked yet (D-14)".
- **What broke:** the test intakes of 2026-11-09 stored whole sentences in `why` and `how`. One example is `"how": "The router stores percent-decoded parameters in the request extensions as UrlParams; Path deserializes them into a tuple."`. Another is `"how": "Returns yes/no confidences and 0 to 5 scores from the JEV model."`, which also holds values. R-3.17 and R-6.17 say each `why` and each `how` is one sentence fragment without tunable values.
- **Cause:** no form delivered the rule to the agent or checked it. The refusal is the only place an agent learns the rule, and no write was refused.
- **Fix:** the Rust, Node and Python forms now check every `why` and `how` that an `add` or `update` writes in a want. A want that breaks the rule is refused with `GRAMMAR_CONSTRAINT_VIOLATION`, the tested sentence, and an `update` remediation with a placeholder in each part that broke the rule. `SPEC.md` states the check under R-5.24 (note of 2026-11-10). Each form has tests, and the conformance case `wants-grammar` compares the three forms.
- **What stays as it was:** stored maps are not checked on load, so the wants stored on 2026-11-09 keep their text until a command writes them again. Words ending in `-ing` after the first word are not checked (D-14).
