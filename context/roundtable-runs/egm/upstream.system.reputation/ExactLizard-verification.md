# ExactLizard — verification evidence for the accolades review

Companion to `resolution.md`. Line references are to the three files copied into `source/`.
Purpose: make every verdict in `resolution.md` inspectable, and record which cited files are
absent from the copy so unverifiable claims are not silently treated as verified.

## Files present in `source/`
```
crates/roundtable-web/src/app.rs
crates/roundtable/src/turn.rs
docs/owner-sources/roundtable-agent-ratings.md
```

## Files cited by the findings but ABSENT from `source/`
`mcp.rs`, `engine.rs`, `index.html`, `stages.py`, `store.py`, `runner.py`, `prompts.xml`,
`roundtable-accolades.md`, `project_agent.txt`.

Consequences:
- GF1's "feedback tool (mcp.rs:22-36, 84-104)" and "FeedbackGiven keyed by to_session
  (engine.rs:882-898)" are **unverifiable here**. The receiving side is verified instead
  (`roundtable.feedback` at app.rs:103, `to_session`/`to_name` in save_feedback at 536, and the
  participant-tools endpoint app.rs:158, 370-392 dispatching to `roundtable::mcp::handle`).
- GF4's "resume picker (index.html:416-417)" is **unverifiable here**.
- GF2's "roundtable-accolades.md is not in the repo either" is **verified**: it is cited at
  roundtable-agent-ratings.md:160 and is absent. Also absent: the doc's own `../../src/metaform/...`
  links (lines 5, 144). The doc says the primary sources/tests are in "the full archive"
  (line 160), i.e. external.

## Verified claims, by finding

| Finding | Claim | Verified at | Result |
|---|---|---|---|
| GF1 | `accolades.jsonl` appended from feedback | app.rs:69, 103-111 | true |
| GF1 | feedback saved to identity `feedback` list | app.rs:535-545 | true |
| GF1 | session ranking / cross-session rating | turn.rs:516-544 | true |
| GF1 | profile score shown to returning agent | turn.rs:37-50 | true |
| GF1 | "only return weighting missing" | no weighting code in copy; investigations note | consistent |
| GF3 | accolades.jsonl gets ONLY feedback | app.rs:103-111 (rating path is 98-102) | true |
| GF3 | feedback adds no points | app.rs:533-534, test 703-704 | true |
| GF3 | end-of-table ratings add points, not logged to accolades | app.rs:98-102 vs 103-111, save_rating 500-509 | true |
| GF4 | nothing weights return | no such code; app.rs:567 is only a sort | true |
| GF4 | "points used ONLY to sort identities" | **false** — app.rs:483-495, turn.rs:37-50, 521-533 | **refuted** |
| GF5 | "accolade" undefined in element.md | element.md has no definition | true |
| GF6 | `code.server.tool` introduced nowhere but the wants bullet | element.md:15 | true |
| GF7 | header says relative; gap says external | element.md:4 vs 57 | true (contradiction) |
| GF8 | scale documented in-repo | ratings.md:60-61, 98-113, 115-122 | true (so "never reconciled" is about the element, not the repo) |
| GF8 | cross-session rating / profile score missing | turn.rs:37-50, 516-544 | **refuted** — they are built |
| GF9 | jargon undefined in element.md | element.md:42 | true |
| GF10 | `name_length`, `intent`, `upstream.` unexplained | element.md:7-11, 15 | true |
| GF10 | `name_length: 2` vs name "accolades" (9 chars) | element.md:8-9 | **new defect**: inconsistent |

## Independent observations added (not in the findings)
1. `name_length: 2` does not match `"name": "accolades"` — likely a schema/field-semantics bug.
2. The in-repo owner-source doc has its own dangling links, so repointing the uri at it does not
   reach the primary source; the description must still say the archive is external.
3. The scale is already reconciled in `roundtable-agent-ratings.md` (and the doc records an
   omitted worker rubric at line 113 and stale README 100/105 claims at 156-158), so GF8's
   "never reconciled" is a defect of `element.md`, not of the codebase.
4. Points have at least three consumers (profile score/cross-session rating, identities sort,
   resume-picker label), so GF4's "only" is wrong even though its conclusion is right.
5. GF2, GF7, GF10 are all map-schema/path-convention issues and must be resolved as one edit
   plus a schema-level item; resolving them independently produces contradictory paths.
