---
name: architecture-review-functionality-first
description: Use when auditing Metaform architecture or specs.
category: development
---

# Architecture review: judge working functionality first

Judge each part of the system by whether the product works for the person: fast, reliable, cheap in tokens, doing what it is for. A specification record is evidence of intent, not a rule to defend. Where a record blocks or degrades working functionality, say so and propose the refined record text with its why.

- Structure findings as: what must work, what blocks it, what the foundation must be.
- Before calling a record current, check it against what is newer: CLAUDE.md as it reads now, `git log --since=<date>` for the last few days, and the latest reports in `docs/reviews/` and `artifacts/reports/`. Name what overtook it and what replaced it.
- Newest explicit decision wins: a later commit, a CLAUDE.md edit, or an uncommitted edit in the tree overrides an older record. Refine the record inside that decision and say so; do not reopen the decision. Quote the newer text, but do not measure an uncommitted edit as if it were committed.
- Many records were written by agents and stamped as the owner's. Treat each as evidence of intent, not as the owner's words, and never defend a record that blocks working functionality.
- A brief may name a report path that does not exist. Resolve it with `ls` and `grep -i` and cite the real file, saying which name the brief gave.
- Record `git rev-parse --short HEAD` when the review starts and again before the write-up. If HEAD moved, re-check every line number and every claim about code that the new commit touched.
- Attribute quotes to the document they come from. Never present a record's or report's wording as the owner's own words.
- Mark each finding [V] (verified by reading code, store or git at a cited line) or [I] (inferred, not run).
- To find when a prompt or block was filled in, use `git log -S'<text>' -- <file>`, not a guess.
- A commit can land while the write-up is being drafted. Run `git log <start>..HEAD` and `git status` after the last write, not only before it. Then re-check the claims about files that commit touched, and record the newer short id beside the start id in every document header.
- Every record id in the spec files must appear exactly once in the verdict table. Generate the table from the id list and assert the counts match (`ids in table not in specs: []`). A record not assessed against function gets an explicit "carried, not assessed in this pass" verdict, never a default "Kept". A default verdict hides which records were actually read.
- When plan steps are renumbered, sweep every "step N" cross-reference in the review, the plan and the draft spec in the same pass. One renumbering left 12 stale references in this review's documents.
