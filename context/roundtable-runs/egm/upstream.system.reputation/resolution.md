# Resolution of the review findings — element `upstream.system.reputation` ("accolades")

Decisions by **ExactLizard**. Each finding gets a verdict, the reason, and the concrete change
to the description (`element.md`) or to the code. "Right" means the finding identifies a real,
inspectable defect in the description or a real discrepancy with the code; it does not mean I
endorse every clause of the finding verbatim — where a clause is wrong I say so.

## Scope and method (read this first)

The `source/` folder copied for this review contains exactly three files:

- `crates/roundtable-web/src/app.rs`
- `crates/roundtable/src/turn.rs`
- `docs/owner-sources/roundtable-agent-ratings.md`

The findings cite `mcp.rs`, `engine.rs`, `index.html`, `stages.py`, `store.py`, `runner.py`,
`prompts.xml`, `roundtable-accolades.md` and `project_agent.txt`. **None of these are in the
copy.** Claims that depend on them are marked *unverifiable here*; where the receiving side is
visible in `app.rs`/`turn.rs` I verify that instead. `roundtable-agent-ratings.md` itself has
dangling `../../src/metaform/...` links (lines 5, 144) and a dangling link to
`roundtable-accolades.md` (line 160), so even the in-repo doc does not resolve to the primary
source — consistent with the `elephant.gaps` note.

Verified in-repo facts used below:

| Fact | Evidence |
|---|---|
| `accolades.jsonl` is opened under `ROUNDTABLE_HOME` (else `HOME/.roundtable`) | `app.rs:60-69` |
| `roundtable.rating` events go to `save_rating` (points) only | `app.rs:98-102`, `500-509` |
| `roundtable.feedback` events go to `save_feedback` **and** are appended verbatim to `accolades.jsonl` | `app.rs:103-111`, `535-545` |
| Feedback adds no points; end-of-table ratings do | `app.rs:533-534`, `703-704` (test), `500-509` |
| Identity profiles are local files keyed by genesis session, with `points`, `ratings`, `feedback`, `contexts` | `app.rs:426-495`, `457-459` |
| `points` feed `FileIdentities::profile` → `Profile.score` | `app.rs:483-495` |
| Returning agents are shown `session_profile` (score, ratings, sessions) | `turn.rs:37-50` |
| End-of-table rating round computes points per target via `rules::rating_points` | `turn.rs:447-485`, `471` |
| `finish_ratings` builds the session ranking and a cross-session `rating` from the stored profile | `turn.rs:516-544` |
| Points sort the identities list | `app.rs:547-568`, `567` |
| The 0–5 stars + boolean bonus scale and the 10/20/30/40 (+5) weighting are documented | `roundtable-agent-ratings.md:60-61, 98-113, 115-122` |

One framing point that governs GF1, GF6 and GF8: this is an **`upstream.*`** element. Its own
`investigations` note says accolades/identity/return-weighting "reach beyond one Roundtable" and
are "treated as a platform service Roundtable feeds". So the Rust code is legitimately the
*feed* (the `code.server.tool` want) plus a local identity store, not necessarily the whole
upstream service. `elephant.built: "Not built here"` is therefore not simply false — it is
**unqualified and misleading**, which is its own defect. The fix is in the description.

---

## GF1 — Blocker, `elephant.built` "Not built here" contradicts the code

**Verdict: RIGHT, with a qualification on the framing. Change the description, not the code.**

Why right: the want is concretely realized in the copied code. `code.server.tool`'s "let
participants reward one another's good conduct" is realized as the `roundtable.feedback` path:
`app.rs:103-111` consumes the event, `save_feedback` (`app.rs:535-545`) writes it to the
recipient identity's `feedback` list, and the same raw line is appended to
`ROUNDTABLE_HOME/accolades.jsonl` (`app.rs:69`). The identity is local and persistent
(`app.rs:426-495`). Session ranking, a cross-session `rating`, and the profile score shown to a
returning agent are built (`turn.rs:37-50, 516-544`). A reader who takes "Not built here" at
face value would conclude there is no in-repo realisation of the want at all, which is wrong;
that is a legitimate Blocker-level contradiction.

Qualification, and why it matters: GF1 says the want "is built as the MCP 'feedback' tool
(mcp.rs:22-36, 84-104) ... FeedbackGiven keyed by to_session (engine.rs:882-898)". Those files
are **not in the copy**, so the sending side is *unverifiable here*; what I can confirm is the
receiving side (`roundtable.feedback`, `to_session`/`to_name` in `save_feedback`, and the
`/mcp/{table}/{seat}` participant-tools endpoint at `app.rs:158, 370-392` dispatching to
`roundtable::mcp::handle`). Also, "Not built here" is defensible if read narrowly as "the
upstream/platform accolades service and its return weighting are not in this repo" — the
`investigations` note already says as much. So the contradiction is with the **unqualified**
wording, not with a defensible narrower reading.

What should change — in `element.md`:
1. Rewrite `elephant.built` to split covered from missing (see the consolidated patch at the
   end). State that Roundtable does build the tool, `accolades.jsonl`, local identity profiles,
   the end-of-table rating→points, the session ranking, the cross-session rating and the profile
   score shown to the agent.
2. Move "only the return weighting is missing" into `elephant.gaps` as an explicit, named gap,
   and soften the owner statement's "It weights them higher than other agents to return into the
   project" to *, which is intended but not implemented here* — otherwise the description still
   asserts a behaviour the code does not have. GF1 itself concedes this is the one missing piece.
3. Do **not** implement return weighting as part of this review. The element is an upstream
   service and the `investigations` note says "where it lives and how the weighting is applied is
   not yet specified"; inventing a weighting rule in this repo would pre-empt an unspecified
   platform decision. Record the gap instead.

## GF2 — Major, `Properties.uri` / `archaeology.path` point at a non-existent in-repo path

**Verdict: RIGHT. Change the description.**

Why: `Properties.uri` = `archaeology/src/metaform/modules/roundtables/roundtable/resources/prompts.xml`
and the `archaeology.finding.path` cite the same file. Neither `archaeology/` nor `prompts.xml`
exists in the copy. The only in-repo owner-source artefact is
`docs/owner-sources/roundtable-agent-ratings.md`, which reproduces the scorecard prompt (lines
53-96) and the weighted-points formula (98-113). GF2 is also right that `roundtable-accolades.md`
— cited at line 160 of that doc — is absent. Additional evidence GF2 did not give: the in-repo
doc's own `../../src/metaform/...` links (lines 5, 144) are dangling too, and line 160 says the
primary sources/tests live in "the full archive" — i.e. outside this repo. So no in-repo path
resolves to the primary source.

What should change — in `element.md`: either
- (a) repoint `Properties.uri` and `archaeology.path` to
  `docs/owner-sources/roundtable-agent-ratings.md` **with a note** that this is a paraphrase
  of the owner's archive, not the primary source (which is external), or
- (b) keep the archaeology path but mark it explicitly as an **external** reference
  (`~/roundtable/archaeology/...`) and add a one-line convention for external archaeology
  paths.

Do (a) and note the archive is external; doing only (a) without the note would just trade one
misleading path for another. Coordinate with GF7 — these two must be resolved together, not with
two contradictory edits.

## GF3 — Major, two undocumented data paths into/out of "accolades"

**Verdict: RIGHT. Change the description (documentation gap); no code change needed.**

Why: verified exactly as stated. `accolades.jsonl` receives **only** `roundtable.feedback`
events (`app.rs:103-111`) — the mid-table `feedback` tool — and those explicitly add no points
(`app.rs:533-534`; test `app.rs:703-704`). End-of-table `roundtable.rating` events add points via
`save_rating` (`app.rs:98-102, 500-509`) and are **not** appended to `accolades.jsonl`. The
element is named "accolades", yet it never mentions `accolades.jsonl`, never says the thing that
literally carries the name is the *pointless* mid-table feedback stream, and never says standing
comes from a *different* stream. That is a real, non-obvious discrepancy a reader cannot resolve
from the description. Severity Major is fair given the element's whole subject is this concept.

What should change — in `element.md`: add a short "Data flows" note (see patch): state that an
accolade record is the raw `roundtable.feedback` line appended to `accolades.jsonl` and stored
in the identity's `feedback` list (raw ratings + note, no points), whereas points/cumulative
score come from the separate end-of-table rating and live in the identity's `points`/`ratings`.
This also supplies most of the definition GF5 asks for.

## GF4 — Nit, nothing weights agents for return; make "not yet specified" concrete

**Verdict: PARTLY RIGHT. The substantive point is right; one clause is wrong. Change the description; correct the clause.**

Why the substantive point is right: no code in the copy selects, weights, or prioritises an agent
for return into a project. `investigations` says "how the weighting is applied is not yet
specified" — true, but vague. Recording the concrete negative is worthwhile and consistent with
GF1's "only the return weighting is missing".

Why one clause is wrong: "Points are used **only** to sort the identities list (app.rs:547-568)
and to label the resume picker (index.html:416-417)". That is an overstatement I can disprove
from the copy: `points` is read by `FileIdentities::profile` into `Profile.score`
(`app.rs:483-495`), which drives `session_profile` shown to a returning agent (`turn.rs:37-50`)
and the cross-session `rating` in `finish_ratings` (`turn.rs:521-533`). GF1 itself cites those as
built. `index.html` is not in the copy, so the resume-picker label is *unverifiable here*. Points
have at least three consumers, not one.

What should change — in `element.md`: in `investigations` (or `elephant.gaps`), replace "not yet
specified" with a concrete statement: no return-weighting exists; points currently feed (i) the
profile score / cross-session rating shown to the agent (`turn.rs:37-50, 516-544`), (ii) the
sort of `/api/identities` (`app.rs:567`), and (iii) — if the resume picker is confirmed — its
label; none of these constitutes weighting an agent for return. Do not repeat GF4's "only".

## GF5 — Major, "accolade" is never defined

**Verdict: RIGHT. Change the description.**

Why: the word appears in `owner_statements` and the want, but the element gives no definition and
never says how a rating becomes an accolade. A reader can only paraphrase the owner. This is the
root comprehension defect and it amplifies GF3, GF6 and GF8.

What should change — in `element.md`: add a definition, and I can supply it from the code rather
than leaving it abstract:

> An **accolade** is one peer-feedback record: a participant's `feedback` rating of another's
> conduct (0–5 in Efficient, Alert & Aware, Thorough, Coordination, plus a boolean bonus and a
> free-text note), emitted as a `roundtable.feedback` event during the table. It is appended
> verbatim to `ROUNDTABLE_HOME/accolades.jsonl` and stored in the recipient identity's
> `feedback` list. An accolade carries no points; cumulative standing ("reputation") comes from
> the separate end-of-table rating. Recognition is therefore the recorded feedback stream, not
> the score.

That definition also settles "how ratings become one": the mid-table feedback tool is the
accolade path; the end-of-table scorecard is the scoring path. If the map author intends
"accolade" to mean the *upstream recognition/award* instead (per `elephant.design`, "agents earned
recognition"), the description must say that explicitly and mark the in-repo `accolades.jsonl` as
the feed, not the award — either reading is acceptable, but one must be chosen.

## GF6 — Major, `code.server.tool` is never introduced; the want's function is vague

**Verdict: RIGHT. Change the description.**

Why: `code.server.tool` appears only in the single "wants" bullet, with no introduction anywhere
in the element, and "Records a participant's rating of another participant's behavior toward
accolades and identity" does not say what the dependency delivers today. Combined with
`elephant.built: "Not built here"`, the wants section describes a dependency on an element the
description says is absent — an internal inconsistency (GF1 establishes the tool is present).

What should change — in `element.md`: introduce `code.server.tool` with its concrete in-repo
identity (the participant `feedback` MCP tool served at `/mcp/{table}/{seat}`, `app.rs:158,
370-392`) and rewrite the want's Function to state today's deliverable: one `roundtable.feedback`
event per rating → recipient identity's `feedback` list + a line in `accolades.jsonl`. Replace
"toward accolades and identity" with that. This is a description fix; GF1's fix removes the
"not built here" contradiction that makes GF6 read as a paradox.

## GF7 — Major, relative-path header vs. external archaeology gap; "archaeology" undefined

**Verdict: RIGHT. Change the description.**

Why: genuine internal contradiction. The header says "Paths are relative to the Roundtable
folder", so `archaeology/src/...` reads as an in-repo path; `elephant.gaps` says it is in
`~/roundtable/archaeology`, "which is not in this repo". Both cannot hold. "Archaeology" is used
as a layer name and a directory name with no definition, and the source cannot be found in the
copy (GF2). A reader cannot locate the primary material.

What should change — in `element.md`: pick one convention and apply it to header, `Properties.uri`,
`archaeology.path` and `elephant.gaps` together. Preferred: define "archaeology" once as "recovered
material from the owner's earlier Roundtable versions, held in the owner's archive outside this
repository" and prefix external references explicitly (e.g. `~/roundtable/archaeology/...`),
while stating that the header's "relative to the Roundtable folder" rule applies **only** to
in-repo paths. Then repoint the citable in-repo artefact to
`docs/owner-sources/roundtable-agent-ratings.md`. GF2 and GF7 are one edit, not two.

## GF8 — Major, "peer ratings cover part of it" is vague; scale never reconciled

**Verdict: PARTLY RIGHT. Right that the description is vague; wrong about which parts are missing. Change the description; correct the parenthetical.**

Why right: `elephant.built` says "Peer ratings (code.rating.peer) cover part of it" without
enumerating covered vs. missing, and the element never reconciles the archaeology 0–5-star /
boolean-bonus scale with the current one. Both are real comprehension gaps.

Why the parenthetical is wrong: GF8 lists "cross-session rating, profile score, weighting for
return" as the ambiguous covered/missing set. But GF1 (and the code) show **cross-session rating
and profile score are built** — `turn.rs:37-50` (`session_profile`) and `turn.rs:516-544`
(`finish_ratings` uses the stored profile's `score`). Only **weighting for return** is missing.
Repeating GF8's list verbatim would reintroduce the very error GF1 corrects.

On the scale, the description can be reconciled concretely from the in-repo doc: the scale is
unchanged — 0–5 stars in the four categories plus a boolean `bonus`, weighted 10/20/30/40 with
+5 for the bonus (max 105 for one rating) — documented at
`roundtable-agent-ratings.md:60-61, 98-113, 115-122`, and still the shape of the `feedback`/rating
tools. The doc also records two real differences worth citing: the roundtable prompt delivers the
scale *without* the detailed worker rubric or bonus explanation (lines 113, 156-158), and a
stale tasks README still claims an initial 100 / cap 105 (lines 156-158). So the scale is not
"never reconciled" in the repo — it is reconciled in the owner-source doc; the *element* simply
doesn't reference it.

What should change — in `element.md`: rewrite `elephant.built` as an explicit covered/missing
list (see patch) and add one line pointing to `roundtable-agent-ratings.md` for the scale,
rubric-delivery difference and README drift.

## GF9 — Major, undefined jargon in `investigations`

**Verdict: RIGHT in substance, but fix by cross-reference, not by expanding this element. Change the description.**

Why: `topogee`, `deterministic agent identity`, `post-retirement recall`, `platform service`,
`return into a project` and agent `retirement` appear in the `investigations` note with no
definition in this element, and none of them appear in the copied code. A reader cannot tell what
comparison is being drawn. That is a real comprehension defect.

Critical nuance / scope: these are cross-references to **other elements of the functional map**
(the `upstream.*` / deterministic-identity material), not necessarily terms this element should
define. In a map, linking to the owning element is correct; duplicating full definitions in every
element is not. So the fix is a one-line glossary/cross-reference ("see element `<address>`"),
plus — where a term has a concrete in-repo analogue — grounding it: "identity" = a local profile
keyed by genesis session (`app.rs:426-495`), "resuming" = recorded `contexts` (`app.rs:511-531`).
Do not bloat this element with full definitions of `topogee` or `retirement`; point to the element
that owns them. Severity Major is slightly high for what is ultimately a missing cross-reference,
but the finding is right that the note is unreadable as written.

## GF10 — Nit, no "role"; `upstream.` prefix and metadata fields unexplained

**Verdict: PARTLY RIGHT / REDIRECT. The observation is factually right; the finding is aimed at the wrong document. Do not fix inside this element; route to the map-level schema doc.**

Why partly right: this file has no `role` field, and `name_length`, `intent: send`, the `upstream.`
prefix and the `goal:/Function:/Intent:` labels are indeed unexplained *in this file*. I can add a
concrete defect the reviewer missed: **`"name_length": 2` is inconsistent with `"name": "accolades"`**
(9 characters, one word). Unexplained and apparently wrong — worth a map-schema check.

Why redirect: (1) "unlike the others" is **unverifiable here** — only this one element was
provided, so I cannot confirm other elements carry a `role`. (2) `name_length`, `intent` labels,
the `upstream.` address prefix and the notion of a "role" are **map-wide schema conventions**,
not this element's content. The right place to explain them is the functional-map schema /
conventions document (the same place that should define "archaeology" per GF7), not a per-element
file. Adding a speculative `role` field here to satisfy "unlike the others" would be ungrounded.

What should change: add a cross-reference in `element.md` to the map's schema/conventions doc for
these fields, and open a separate schema-level item to (a) explain `name_length`, `intent`, and
the `upstream.` prefix and (b) investigate the `name_length: 2` / `"accolades"` mismatch. Treat
GF10 as a schema note, not a blocker on this element. Severity Nit is appropriate.

---

## Consolidated description patch (apply GF1, GF3, GF5, GF6, GF7, GF8, GF9, GF10 together)

Proposed replacement text for `element.md`. Code needs no change for any finding; the code is
self-consistent and the tests at `app.rs:682-711` already assert the feedback-adds-no-points
rule that GF3 describes.

**Add a "Definition" subsection** (after Properties): the GF5 accolade definition above, plus a
"Data flows" sentence: `roundtable.feedback` (mid-table `feedback` tool) → `accolades.jsonl` +
identity `feedback` list, no points; `roundtable.rating` (end-of-table scorecard) → identity
`points`/`ratings` → cross-session score, no `accolades.jsonl` entry.

**Rewrite the wants bullet**: introduce `code.server.tool` as the participant `feedback` MCP tool
(`/mcp/{table}/{seat}`, app.rs:158, 370-392) and state its concrete deliverable today.

**Rewrite `Properties.uri` and `archaeology.path`**: point at
`docs/owner-sources/roundtable-agent-ratings.md` as the in-repo paraphrase; keep the
`~/roundtable/archaeology/...` primary reference but mark it **external**, define "archaeology",
and state that the "relative to the Roundtable folder" rule applies to in-repo paths only.

**Rewrite `elephant.built`** to:

> Partly built here. In this repo: the `feedback` MCP tool and `accolades.jsonl` (GF3/GF5),
> identity profiles keyed by genesis session (`app.rs:426-495`), end-of-table rating → points
> (`turn.rs:447-485`), the session ranking and cross-session rating (`turn.rs:516-544`), and the
> profile score shown to a returning agent (`turn.rs:37-50`). The 0–5-star/boolean-bonus scale
> and its 10/20/30/40 (+5) weighting are unchanged; see `roundtable-agent-ratings.md:98-122`
> (which also records the omitted worker rubric and the stale README). Not built here: the
> upstream recognition/award service itself, the original archaeology `prompts.xml` system, and
> **any weighting that returns an agent into a project** — points feed only the profile score,
> the `/api/identities` sort (`app.rs:567`) and the resume-picker label, not selection.

**Move to `elephant.gaps`**: the dangling archaeology/prompts.xml path and the missing return
weighting (owner statement's claim marked intended-but-unimplemented).

**In `investigations`**: replace "not yet specified" with the concrete negative from GF4, and
replace the undefined jargon with cross-references to the owning map elements plus the in-repo
analogues (identity = genesis-session profile; resuming = recorded `contexts`).

**Schema note (GF10, GF7)**: add a line pointing to the map-level conventions doc for `upstream.`,
`name_length`, `intent`, `role`, and "archaeology"; flag `name_length: 2` vs `"accolades"` for a
schema-level fix, not an edit to this element.

### Cross-finding dependencies (do not resolve in isolation)
- GF2 + GF7: one path-convention edit.
- GF1 + GF6 + GF8: one rewrite of `elephant.built` / wants; GF8's parenthetical must be corrected
  to avoid re-asserting GF1's error.
- GF3 + GF5: one definition + data-flows note; each supplies what the other lacks.
- GF4 + GF1: both agree return weighting is the single missing piece; GF4's "only" must be dropped.
- GF10 + GF7: both are map-schema concerns; route to the schema doc.
