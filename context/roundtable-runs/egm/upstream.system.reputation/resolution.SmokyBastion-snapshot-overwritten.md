# Resolution — `upstream.system.reputation`: accolades

Final roundtable resolution. Evidence limited to `source/` copy: `crates/roundtable-web/src/app.rs`, `crates/roundtable/src/turn.rs`, `docs/owner-sources/roundtable-agent-ratings.md`. Files cited in findings but absent from copy (`mcp.rs`, `engine.rs`, `rules.rs`, `stages.py`, `store.py`, `runner.py`, prompts.xml, `index.html`, `roundtable-accolades.md`) are unverifiable here — not thereby false. Description-only fixes throughout; no code change required by any finding.

## Core fact (grounds GF1, GF3, GF5)

Two divergent paths, verified in `app.rs`:
- `roundtable.feedback` (app.rs:103-111) → `save_feedback` (app.rs:535-545, comment 533-534, test 701-705: points stay 0) **and** append to `$ROUNDTABLE_HOME/accolades.jsonl` (app.rs:69). No points.
- `roundtable.rating` (app.rs:98-102) → `save_rating` (app.rs:500-509): adds `points`, pushes `ratings` entry keyed by `to_session`. **Never** written to `accolades.jsonl`.
- Points read only to sort identities (app.rs:567) and show returning agent its standing (turn.rs:37-50); session ranking/cross-session rating built (turn.rs:516-544). MCP endpoint `app.rs:370-395` routes to `roundtable::mcp::handle` and `roundtable.feedback` confirmed at app.rs:103,416 — chain endpoint→event→save/log is verifiable; the tool definition in `mcp.rs` is not.

## Verdicts

**GF1 (Blocker) — Right, narrowed.** `elephant.built "Not built here"` contradicts code for rating accumulation, profile score, ranking, and feedback logging; only return-weighting missing. Fix `elephant.built` to list those built parts and name return-weighting unbuilt. Cite only `app.rs`/`turn.rs`; mark MCP-tool→`FeedbackGiven` route unverifiable until `mcp.rs`/`engine.rs` supplied. "Only return weighting missing" overclaims — owner ambition is underspecified.

**GF2 + GF7 (Major) — Right; one defect, not two.** Dead `archaeology/.../prompts.xml` path plus "paths relative to Roundtable folder" vs external `~/roundtable/archaeology` gap. Fix once: point `Properties.uri`/archaeology path to `docs/owner-sources/roundtable-agent-ratings.md`, retain old paths only as explicitly external provenance, define "Archaeology" layer in one line. Close jointly.

**GF3 (Major) — Right; most important.** Document the split above verbatim in the element. Do not silently log ratings to `accolades.jsonl` — that would be a code/design change needing owner decision.

**GF4 (Nit→concrete) — Right.** State: points affect only display ordering; nothing weights return. Implementing owner's return-weighting intent would be a new feature, not a fix.

**GF5 (Major) — Right.** Define: an accolade is a mid-table feedback record in `accolades.jsonl` + profile `feedback` list; ratings→points is a separate score. (Earlier draft inverted this; corrected per GF3.)

**GF6 (Major) — Right.** Rewrite `code.server.tool` want to name today's deliverables (rating→points saved to identity; feedback→`accolades.jsonl`/feedback list, no points), and introduce `code.server.tool` once. Use the peer tool's actual in-copy name (`feedback`/bus events), not `code.rating.peer`.

**GF8 (Major) — Right, narrowed.** "Cover part of it" must list covered (rating accumulation, profile score shown, session ranking, feedback log) vs missing (return-weighting). Scale sub-point withdrawn: code and `roundtable-agent-ratings.md:60-62` agree on four-category + `bonus` card parsed at turn.rs:447-472. Note: the 10/20/30/40 (+5 bonus) formula is attested only by that doc; its defining files (`stages.py`, `rules.rs:rating_points`) are absent — pin one into the repo to close this.

**GF9 (Major) — Right.** Define or delete `topogee`, retirement, recall, platform service, return-weighting jargon; label the row an open question, not established design.

**GF10 (Nit) — Right as observation, fix out of scope.** `upstream.` prefix/metadata are map-wide conventions. Fix via shared map glossary; make no element change.

## Definition of done (checkable)
1. `element.md` no longer says any built piece is "not built" (GF1/GF6).
2. Every cited path resolves under repo root or is marked external (GF2/GF7).
3. `accolades.jsonl` contains only `roundtable.feedback` lines; profiles accumulate points from ratings (GF3/GF5).
4. Current card shape + formula named, defining file pinned (GF8).
5. `grep element.md topogee|retirement|"platform service"` → each defined or absent (GF9).
6. Map glossary covers prefix/metadata (GF10).
