# CLAUDE.md

Guidance for agents that work in this folder.

## Register and design guidance

@TASTE.md

`TASTE.md` sets how you write: plain technical English, complete thoughts, the project's own terms, and no invented terms.

@EXPECTATIONS.md

`EXPECTATIONS.md` sets how you handle design gaps: do the engineering work, make supported decisions, and bring only owner-dependent decisions back, with a recommendation.

## Orientation

Read `START_HERE.md` first. It explains how this folder is laid out, which documents govern, and where the known conflicts are recorded (`PROJECT_CONTEXT.md`, `OWNER_REVIEW_SPEC.md`).

The intake procedure and its semantics (`metaform/Intake.md`, the schema and the tool contract) are protected. Do not change them without the owner's direct instruction (from the original repository's `AGENTS.md`, kept in `context/topogee-repo/AGENTS.md`).

`context/` holds preserved source material. Read it; do not edit it.

## Feature commits

Carried over from the original repository's `AGENTS.md` on the owner's instruction (2026-11-09). Until further notice, every feature commit is a commit and a push. Do not ask for permission. This is automatic.

- After a test where the code seems to operate, make a feature commit and push it, before the owner tests. Do not change the code between the test and the commit.
- Name the feature in the commit, using its name in the map's `features` layer. Say what changed since that feature's last commit, what test ran and what it showed. Include only that feature's files.
- If no features are documented or named yet, make a full commit of all changes instead.
- A feature commit means the agent's test passed. It does not mean the owner accepted the feature.
- If a feature breaks after its commit, add a note to `metaform/docs/trouble-log.md` naming that commit. Fix it, test it and make a new commit. Never rewrite a commit. (The earlier log is `context/topogee-repo/docs/trouble-log.md`, which is read-only.)
- Use one branch for each feature. Deployment still needs a direct instruction from the owner.
