---
title: "Jorge open items"
type: open-items
updated: 2026-11-09
---

## Questions

### JQ-001: Should agent notes folders be committed or ignored?
- Status: resolved 2026-11-09: ignored (JD-004)
- Raised: 2026-11-09
- Evidence: `.ida/`, `.marcus/` and `.jorge/` are untracked; `.gitignore` names none of them.
- Next step: ask the owner. Recommendation: add them to `.gitignore` unless the owner wants other agents and clones to see them. See JR-001 for why this matters now.

## Risks

### JR-001: A full feature commit would sweep up agent notes folders
- Status: resolved 2026-11-09: `.gitignore` now excludes the folders (JD-004)
- Raised: 2026-11-09
- Evidence: the Feature commits section of `CLAUDE.md` says to make a full commit of all changes when no features are named yet. The untracked notes folders count as changes.
- Impact: notes would be pushed to `origin` (`github.com/RchGrav/metaform`) without the owner deciding that.
- Next step: until JQ-001 is answered, stage paths explicitly and leave the notes folders out.
