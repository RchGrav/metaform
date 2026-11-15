---
name: metaform-architecture-review
description: Use when auditing architecture, specs or the map store.
category: development
---

# Reviewing Metaform architecture: the code is the reference

Before you cite a specification, check it against `src/metaform/`. Where a spec describes a mechanism the code no longer has, the code is the truth and the spec is what needs updating. Say which is which in the review.

- Label every finding **[V] verified** (read at a file and line, or measured) or **[I] inferred** (follows from the code but was not run). Keep the two apart in the summary. A [V] mark covers only what the cited line shows: a call site that updates a table is [V], but "the same transaction as the map" is a further claim and stays [I] until the transaction boundary is read. Do not promote an inferred property to [V] because the line beside it was verified.
- Specification records can be stale. The storage records (`STORE-004` to `STORE-039` in `specifications/03-storage.md`) still name `current_*` tables and query-plan tests that an op log and an in-memory projection replaced (`STORE-046`, `src/metaform/data/schema.py`). Look up `src/metaform/data/` before quoting a table or index name from a spec.
- Test an API's behaviour in the code before asserting it. Read the class first; a probe that guesses an attribute fails on the guess, not on the product.
- Measure on a copy of the live home, never on the live files or live server, as described in `metaform-web-gui-hang-diagnosis`.
- A finding that a finished base still accepts writes, or that a mechanism the design calls key is not built, is a product finding. Report it with its file and line and leave the decision to the owner.
- Put the review in `docs/architecture/` with a dated name, and list the scripts used in an appendix so the measurements can be rerun.

## Judge working functionality first
- Judge each part by whether the product works for the person: fast, reliable, cheap in tokens, doing what it is for. The code is the reference for what is built; a specification record is evidence of intent, not a rule to defend. Where a record blocks or degrades working functionality, say so and propose the refined record text with its why.
- Before listing gaps in a document, establish what it is. A redesign draft that sets the shape of the next version is reviewed for that shape and its direction; a specification is reviewed for completeness. Ask the owner which it is before reporting a missing command or field as a defect, and record the answer in the review header.
- A specification leaves nothing underspecified: for each operation, state its inputs, its success and failure replies, and what an update does to existing data (replace or add). A step that loads the whole map into one agent's context is a finding against the focus rule in `metaform-context-focus-design`.
- Structure findings as: what must work, what blocks it, what the foundation must be.
- Before calling a record current, check what overtook it: CLAUDE.md as it reads now, `git log --since=DATE`, and the newest reports in `docs/reviews/` and `artifacts/reports/`. The newest explicit decision wins (a later commit, a CLAUDE.md edit, or an uncommitted edit). Refine the record inside that decision and say so, without reopening it. Measure committed code only; quote an uncommitted edit as uncommitted.
- Many records were written by agents and stamped as the owner's. Treat each as evidence of intent, attribute quoted record or report wording to its own document, and never present it as the owner's words.
- A brief may name a report path that does not exist. Resolve it with `ls` and `grep -i`, cite the real file, and name the path the brief gave.
- Record `git rev-parse --short HEAD` when the review starts and again before the write-up. If HEAD moved, re-check every line number and claim the new commit touched. Run `git log START..HEAD` and `git status` after the last write, and put the newer short id beside the start id in the header.
- Every record id in the spec files appears exactly once in the verdict table. Generate the table from the id list and assert the counts match (`ids in table not in specs: []`). A record not assessed against function gets an explicit "carried, not assessed in this pass" verdict, never a default "Kept".
- When plan steps are renumbered, sweep every "step N" cross-reference in the review, the plan and the draft spec in the same pass.
- To date when a prompt or block was filled in, use `git log -S'TEXT' -- FILE`, not a guess.
