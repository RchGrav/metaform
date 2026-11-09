---
title: "Jorge decisions"
type: decisions
updated: 2026-11-09
---

Newest first. The project's own decision record is `context/topogee-repo/DECISIONS.md` (preserved) and the status lines in `metaform/SPEC.md`.

## JD-004: Agent notes folders are gitignored
- Date: 2026-11-09
- Decision: `.ida/`, `.marcus/` and `.jorge/` are listed in `.gitignore`.
- Reason: they are each agent's local working notes, and without the entry a full feature commit would push them to `origin`.
- Source: owner, in conversation, 2026-11-09 (answering JQ-001).

## JD-003: Feature commits carry over from `~/topogee`
- Date: 2026-11-09
- Decision: the automatic commit-and-push rule after a passing test applies in this folder. It is now the Feature commits section of `CLAUDE.md`, adapted from `context/topogee-repo/AGENTS.md` (founder became owner; the trouble log moved to `metaform/docs/trouble-log.md` because `context/` is read-only).
- Reason: the owner can always see exactly which code and prompt ran in a test.
- Source: owner, in conversation, 2026-11-09.

## JD-002: Four topogee-session memories carried into this project's memory
- Date: 2026-11-09
- Decision: carry-owners-intent, owner-files-reference, spec-is-kept-current (retargeted to `metaform/SPEC.md`) and verify-boat-sandbox-ownership are active memories here. The five project-design memories stay behind because `TASTE.md`, `metaform/SPEC.md` and `PROJECT_CONTEXT.md` (C-14) supersede them.
- Reason: the working rules still apply to Metaform work; the design notes are stale.
- Source: owner, in conversation, 2026-11-09.

## JD-001: Notes folder is `.jorge/`
- Date: 2026-11-09
- Decision: Jorge keeps project notes in `.jorge/` at the project root, separate from memory. The structure is in the skill (`~/.claude/skills/data-expert/SKILL.md`, "My notes folder").
- Reason: memory holds how to work with the owner; a notes folder holds per-project working state, as `.ida/` and `.marcus/` do for the other agents.
- Source: owner, in conversation, 2026-11-09.
