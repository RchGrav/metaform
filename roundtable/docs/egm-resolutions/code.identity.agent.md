# Agent genesis names — review resolutions

Prepared by HybridParrot. These are decisions and proposed changes; the source and `element.md` have not been modified.

## Evidence boundary

The supplied source contains only `crates/roundtable/src/names.rs`, `crates/roundtable/src/config.rs`, and the two word lists. References below are relative to `source/`. The engine, ACP harness, application, UI, and turn-processing files cited by the reviewers are absent. Their reported behavior is distinguished below from behavior verified in this copy. Absence of those files does not disprove a finding, but their line references alone do not establish it.

The central distinction is between a session identity, a generated display name, and a table seat. `Identities::profile` explicitly keys profiles by the genesis session, not the name (`config.rs:42–49`). `SeatConfig.name` is separately configured and must be unique within a table (`config.rs:9–11, 119–129`). The supplied files do not show how that configured seat name relates to the generated name at runtime.

## GF1 — Right about the missing condition; qualify the outcome

**Change the description.** Promise continuity across tables when the same genesis session is successfully resumed, rather than suggesting that choosing the same seat, model, or harness automatically preserves identity. `SeatConfig.resume_session` explicitly distinguishes resuming an earlier session from opening a new one and associates resume with identity continuity (`config.rs:23–28`).

A fresh session is a separate profile key under the documented storage contract. It is not guaranteed to produce a different display name: collisions are explicitly permitted (`names.rs:5–6`, `config.rs:46–48`). Replace “gets a new name and a new profile” with “uses a new session identity, with its own profile history; its generated name may coincide with another identity's name.” The UI behavior and actual engine profile lookup remain unverified because those files are absent. No change to the hash function is warranted.

## GF2 — Partly right: document the input and dependency; do not assert an unverified handshake

**Change the description** to name `SeatConfig.resume_session: Option<String>` as the resume input and state that the selected harness must hold that session. Both points are explicit in `config.rs:23–28`.

`genesis_name` receives a string and deterministically derives a name; it neither opens nor resumes sessions (`names.rs:11–19`). Reusing the same genesis session ID preserves the identity key and reproduces the name; a different ID can coincidentally reproduce the name without preserving identity. The proposed details about the engine using the returned ID, the ACP host preserving the requested ID, capability negotiation, and startup failure without fallback cannot be verified here. They should be documented in the session-start/resume element after checking the cited harness and engine code, with this element linking to that contract. Do not add a silent fresh-session fallback: that would discard the intended identity continuity. No naming-code change follows from the supplied evidence.

## GF3 — Partly right: collisions are established; the categorical interaction failure is unverified

**Expand the documented collision limitation**, but do not publish “two same-named agents cannot rate or give feedback to each other” as an established fact from this source copy. The storage interface confirms session-keyed profiles and permits duplicate generated names (`config.rs:46–48`). No target-resolution implementation is supplied. Whether a collision makes a particular target ambiguous also depends on which candidates the resolver considers, including whether it excludes the sender before matching.

The description should state now that a generated name is not a unique addressing key and cannot by itself guarantee unambiguous peer targeting. Verify the reported rejection behavior in `turn.rs` and `engine.rs` before documenting its exact scope.

As EminentStrike observes, `TableConfig::validate()` rejects duplicate configured seat names (`config.rs:119–129`). This may prevent a collision from reaching peer targeting, but only if the generated names are present when validation runs and remain the names used for addressing. The omitted caller must establish the relationship and ordering; the existence of `validate()` alone does not prove it is invoked after session names are generated. Resolve that boundary before asserting either a table-start failure or a peer-feedback failure.

**If the reported name-only resolver is confirmed, change that code** to carry an unambiguous participant key through rating and feedback submission. Use a unique seat/participant reference within the table and associate persisted ratings with the genesis session key. The display can retain the generated name, with an additional visible disambiguator when needed. Reject an ambiguous legacy name-only request instead of choosing an arbitrary recipient. Keep the deterministic genesis name unchanged; rehashing a collision would defeat its stability. This repair belongs to targeting and feedback, not `genesis_name`.

## GF4 — Right as a reproducibility/documentation nit

**Add a compact algorithm reference to the description**, supported by `names.rs:8–25`:

- Hash the session ID's UTF-8 bytes with 32-bit FNV-1a: offset `2166136261`, prime `16777619`, wrapping multiplication.
- Compute `folded = (h ^ (h >> 16)) & 0xFFFF`.
- Use the high byte as the zero-based adjective index and low byte as the noun index.
- Read `crates/roundtable/resources/names/adjectives.txt` and `nouns.txt` in file order, ignoring blank lines and trimming the selected entry. Uppercase each selected word's first character and concatenate without a separator.
- An unavailable list entry falls back to `agent`, which becomes `Agent` after capitalization. This is defensive behavior, not a collision resolver.

Both supplied lists have 256 nonblank, distinct entries. An independent calculation reproduced the existing test vector: `01a1ae33-9d9f-76e1-bfbf-37eb6d762b7e` gives `DeadeyeQuokka` (indexes 57 and 166). No algorithm change is needed. Keep list contents and ordering stable if existing names must remain stable across software versions.

## GF5 — Right

**Define the session terms in the description.** `names.rs:1–6` already supplies the missing definition: the genesis context is the first session a harness opens for an agent, and that session's ID seeds its identity. “First” refers to the agent's genesis, not the first table in the current run, first message, or configured seat label.

Describe the ID as belonging to the harness-managed agent session; Roundtable's naming function consumes it rather than allocating it. State that resuming means requesting an existing session through `resume_session` on the harness that holds it. Avoid specifying the exact ID-issuing component or protocol path without the omitted session-opening implementation. A different fresh session starts a separate identity even if the operator intends the same model to participate again.

## GF6 — Right about the identity/display distinction; not a reason to replace the algorithm

**Rewrite the want** as: “Give participants a repeatable display name for a genesis-session identity, and preserve that identity and its profile across tables when that session is resumed.” Name the genesis session ID explicitly as the profile identity key (`config.rs:46–49`).

The current want overstates what a 16-bit display mapping provides. Collisions do not merge session-keyed profiles, and a new session does not inherit history merely because its display name matches. Conversely, a name need not be globally unique to be a useful stable display label. No UUID-like replacement name or name-keyed storage change is justified. The engine's actual retention of the genesis ID across resume still requires checking the files absent here.

## GF7 — Right

**Define “chair” and identify the owner of the visibility rule.** Use it for the table operator/controller role, distinct from the evaluator that accepts or rejects contributions. Explain whether a human user, a controlling client, or another actor fills that role in the enclosing system. The configuration comments refer to a chair-set limit and a chair credential (`config.rs:52–55, 154–156`), but do not establish that the chair is always a human or is the evaluator.

The claim that agents see names while the chair sees names and models is not enforced by `names.rs`. Mark it as a presentation/prompting responsibility and link to the element that builds those views. Enforcement cannot be verified from this copy; do not change the hash function to address it.

## GF8 — Right; overlaps GF4 and GF5

**Add the mapping, list paths, and example specified under GF4**, and explain “genesis” using the definition under GF5. `DeadeyeQuokka` demonstrates the capitalized adjective-plus-noun format. Keep these explanations in one place rather than duplicating them for each finding. These are documentation changes, not missing naming functionality.

## GF9 — Partly right

**Mark the visibility rule as a responsibility of another element**, as described under GF7. Name derivation and deciding which model metadata an audience receives are separate behaviors.

The absence of a rationale does not establish a code defect. The supplied files do not state why models are hidden; do not invent an authorial reason such as preventing model bias. Link an authoritative policy rationale if one is available. Until then, label the rule as a stated policy whose rationale and enforcement are outside this source copy.

## GF10 — Right; a concrete historical path is available

**Replace the vague source entry** with `archaeology/rich/technical/agent_identity.md`, explicitly marked as a historical document not included in this copy. Both `names.rs:1` and `config.rs:25` cite that path. Also cite those available source comments for the genesis and resume definitions. Do not claim the historical document has been inspected or create a working-link implication when the file is unavailable.

## Resulting scope

The verified findings call for a more precise element description, including conditional continuity, the session identity key, exact name derivation, and responsibility boundaries. No supplied evidence requires changing `names.rs`. GF3 identifies a plausible code repair in the omitted targeting implementation, conditional on verifying its reported behavior. The runtime claims in GF1–GF3 and the visibility enforcement in GF7/GF9 remain explicitly unverified, rather than being silently treated as proven or dismissed.

---

# Addendum — EminentStrike (second opinion and refinements)

Supporting checks and line-level evidence: `EminentStrike-analysis.md`. I verified the
algorithm numerically, counted and deduplicated the word lists, and re-read `config.rs`.
I concur with HybridParrot's verdicts in substance; the points below tighten them,
resolve two open questions, and add facts the draft did not use.

## Verdict table

| Finding | Verdict | Fix location | Change to HybridParrot's draft |
|---|---|---|---|
| GF1 | Right | description | Add the `#[serde(default)] None` evidence; keep the "new name" correction |
| GF2 | Right in part | description | State recompute-not-store; **reject** the implied silent fallback explicitly |
| GF3 | Right in part | description (+ conditional code) | Reconcile with `config.rs:127-129`; add collision math |
| GF4 | Right | description only | No code change needed — `names.rs:1-6` already documents it; resolve Nit/Major clash with GF8 |
| GF5 | Right | description | Use `names.rs:2-3`'s exact wording for "genesis" |
| GF6 | Right | description | Name the genesis id as the key; note the code already keys profiles by session |
| GF7 | Right | description | Decide what the chair is, don't leave it open |
| GF8 | Right | description | Consolidate with GF4; add the example name |
| GF9 | Partly right | description | Misplacement is the defect; "no reason" is normal for a `rules` layer |
| GF10 | Right | description | Add the second code-cited source `dispatch/names.py` |

## GF1 — refine

Right; change the description. Add the concrete default: `resume_session` is
`#[serde(default)]` and `Option<String>` (`config.rs:27-28`), so **the default is a fresh
session at every table**. Continuity is opt-in, not automatic, and `config.rs:23-28` says
so in its own doc comment. The want at `element.md:16` ("stable identity across tables")
must be qualified to "when the same genesis session is resumed". Keep HybridParrot's
correction that a fresh session is not guaranteed a *different display name* (16-bit
space, collisions permitted) — GF1's "gets a new name" is imprecise. No code change:
`config.rs` documents resume as the intentional mechanism, so the defect is in the map,
not the program.

## GF2 — refine, and one firm disagreement

Right that the mechanism is missing from the description; change the description, not the
code. Two additions:

1. **The name is recomputed, not stored.** `genesis_name` is a pure function of a string
   (`names.rs:11-19`) and the supplied `Profile` (`config.rs:32-40`) holds no name. A
   resumed session "keeps its name" only because the caller supplies the **same genesis
   session id** again. The durable seed is the genesis id; the name is a derived label.
   This is the mechanism GF2/GF5 ask for, and it is why `rules[0]`'s wording is easy to
   misread as "a stored name is carried over".
2. **Do not add a silent fresh-session fallback.** GF2 reports the absence of a fallback
   as missing documentation; it does not explicitly request one. Silently opening a fresh
   session would substitute a different identity while the operator expects a resume.
   Document a hard seat-start failure only after checking the omitted startup code.
   `config.rs:15-16` cannot prove that behavior: those comments concern failed settings
   and explicitly say the seat still joins, so they are not evidence about resume failure.

Keep HybridParrot's boundary: engine/harness internals (id echo, capability negotiation)
belong to the session-start/resume element, cross-referenced, not pasted into `names.rs`'s
element.

## GF3 — the key unresolved contradiction

Right that a limitation is missing, but the reviewer's scenario cannot be published as
fact until the description answers a question it currently leaves open: **which name is
`SeatConfig.name`?** `config.rs:119-129` `validate()` rejects duplicate seat names
case-insensitively as a hard table-start error. Yet `element.md:16` says the manager
"derives the agent's name from its first session id", which may mean the derived genesis
name becomes the seat name. If validation runs after that substitution and admission
requires it to succeed, duplicate names cannot join that table. Validation might instead
run on provisional seat labels before generated names are assigned; the omitted callers
must establish this ordering. The collision statement cannot yet be limited to cross-table
collisions. If instead `SeatConfig.name` is independent of the genesis
name, the description must say which name agents see and which one rating/feedback
resolves. `element.md` states neither.

So the description change is: (a) define the relationship between the genesis name and
the seat name, (b) state where `validate()` applies, (c) then document the collision
consequence for the layer that survives. Add the scale fact: there are only
256 x 256 = 65536 distinct names (all rendered combinations independently enumerated by
HybridParrot), so 300 independent uniformly distributed name draws give a 49.61% chance
of at least one collision. Uniform independent hash outputs are an assumption about the
session-ID population, not a guarantee of FNV-1a. Also,
`names.rs:5-6` says nothing rehashes. Collisions are expected at scale, not exotic.

On the conditional code repair (HybridParrot GF3, last paragraph): agree it belongs to
targeting/feedback, not `genesis_name`. One constraint to add — agents address peers by
name in the rating/feedback tools, so a unique-key-only fix does not remove ambiguity at
the *input* boundary. A repair must either expose a visible disambiguator to agents or
keep rejecting ambiguous name-only requests; it must not silently pick a recipient.

## GF4 and GF8 — one consolidated fix; resolve the severity clash

Both are about the same omission. GF4 rates it **Nit**, GF8 rates it **Major** for
comprehension. My ruling: Major for reproducibility (a reader cannot reconstruct or test
the algorithm from `element.md`), but small in scope — one expanded `rules[0]` sentence
plus one knowledge line. Add the exact verified facts from `EminentStrike-analysis.md`
§2–3: FNV-1a offset/prime, fold, high byte adjective / low byte noun, capitalisation,
list paths, no separator, `DeadeyeQuokka` example (I reproduced it independently:
folded 14758, indices 57/166), and the defensive `agent`→`Agent` fallback.

**No code change is warranted:** `names.rs:1-6` documents the high-level derivation;
the numeric constants and fallback are in `names.rs:11-19`, and list paths are in lines
8-9. GF4/GF8 concern carrying these source facts into the
functional map. Fix `element.md`, leave `names.rs` untouched. Also note the 10 words
shared across the two lists (`shadow`, `ghost`, `steel`, …) do **not** produce duplicate
names, because a name is an ordered (adjective index, noun index) pair and each list's
entries are distinct — a useful precision for anyone auditing collision handling.

## GF5, GF6 — refine

Both right; description only. For GF5 use `names.rs:2-3`'s own definition verbatim in
substance: "genesis context" = the first session a harness opens for the agent, and its
id is the seed of identity; "genesis" in the element title means exactly that; the id is
issued by the harness and *consumed*, not allocated, by Roundtable. "First" is the
agent's genesis, not the first table of the current run.

For GF6 name the **genesis session id** as the real identity key and reframe the want as
HybridParrot proposes. Add: the code is already right — `Identities::profile` keys by
session (`config.rs:45-49`) — so no storage change is justified; the want's fault is
that it calls a collision-prone 16-bit display label a "stable identity". Collisions do
not merge profiles, and a coincidentally matching name does not inherit history.

## GF7 — decide, don't defer

Right; description only. HybridParrot leaves open whether the chair is a human, client,
or evaluator. The supplied code is decisive enough to define it: `config.rs:52-55` says
the chair credential `ROUNDTABLE_TOKEN` "never reaches an agent", and `config.rs:154-156`
says "The chair sets it; agents cannot change it (O)" for reply limits. So the chair is
the **privileged table operator/host**: it holds the chair credential, configures limits
and topics, and is neither a participating agent nor the JEV evaluator (the evaluator
checks each message, `element.md:3`; judging is a separate flag, `config.rs:148-153`).
`code.manager.chat.group` is a *code element*, not the role. Define the chair once in
`element.md` with that disambiguation and mark `rules[1]` as a view/presentation rule
owned by the element that builds participant-visible messages — `names.rs` does not
implement it.

## GF9 — partly right; the actionable part is misplacement

Agree with HybridParrot. Make the reasoning explicit: a `rules` layer in a functional map
records *what* the part must do; rationale belongs in the `elephant` layer. "No reason is
given" is therefore not by itself a defect, and inventing one (model-bias blindness,
etc.) would be worse. The genuine, actionable defect is that `rules[1]` sits in an element
whose `uri` is `names.rs` (`element.md:11`) while `names.rs` only generates names — so the
description should mark it as a cross-element visibility rule with a link to its owner,
or move it there. Severity Nit is correct.

## GF10 — right; add the second checkable source

Replace the vague entry with `archaeology/rich/technical/agent_identity.md`
(`names.rs:1`, `config.rs:25`) and also cite `dispatch/names.py`'s `session_name`
(`names.rs:39`), the reference implementation the test vector is checked against. Both
are outside the supplied source; mark them as historical/not present in this copy, and
remember `element.md:10` says paths are relative to the Roundtable folder. Do not imply
the documents were inspected.

## Cross-cutting observation

`element.md:11` gives this element a single `uri`, `names.rs`. Yet `rules[0]`'s resume
clause, `rules[1]`'s visibility, the session-keyed profiles, and the resume input all
live in `config.rs` and in elements outside this copy. The map should either widen the
element's declared scope or add explicit cross-references. Several findings (GF2, GF3,
GF6, GF7, GF9) are symptoms of this boundary being drawn too narrowly, and a single
"relies on / owned by" annotation would prevent the same class of review finding
recurring.

## Final tally

All 10 findings are right or partly right; none is wholly wrong. Every verified fix is a
**description** change. No finding requires a change to `names.rs`. The only possible
code change is GF3's conditional repair in the omitted targeting layer, gated on (1)
verifying `turn.rs`/`engine.rs`, (2) reconciling `config.rs:127-129`, and (3) preserving
name-based peer addressing. The runtime claims in GF1–GF3 and visibility enforcement in
GF7/GF9 stay explicitly unverified.

Two points raised in discussion, verified here and now folded in:

- **Call-graph boundary.** `grep -rn` over the supplied copy finds `genesis_name` once
  (definition, `names.rs:11`) plus three test uses (`names.rs:37,38,42`) — **zero
  production callers** — and `resume_session` only as a field declaration
  (`config.rs:28`), no reader. So `names.rs` is a pure, unwired library in this excerpt;
  all wiring lives in files not provided. This is the precise form of CloudyPeace's
  "a pure function cannot preserve anything" and UnknownArrow's zero-caller observation:
  "description-only" is correct **for this element**, and GF3's operational half is a
  turn/engine code fact that this copy cannot verify or repair. I agree with
  UnknownArrow's refinement and state the boundary this way rather than as a blanket
  "no code change anywhere".
- **GF8 is subsumed, not double-billed.** UnknownArrow and SeriousSiren flag GF8 as a
  duplicate of GF4+GF5. Consistent with GF4/GF8 above: one consolidated description edit
  carries the algorithm line, the definitions, the list paths and the example name.

A note on the shared artifact: this `resolution.md` on disk contains HybridParrot's
draft plus this addendum. Its GF9 verdict is "Partly right" and GF10 "Right" — there is
no REJECT entry here. Claims in discussion about correcting a REJECT verdict or about
other addenda are not reflected in this file; the rulings as written stand.

---

## Correction: GF3's premise was wrong in my original ruling (final round)

EminentStrike raised a contradiction I missed, and I verified it. `TableConfig::validate()` rejects duplicate seat names as a **hard table-start error** (`config.rs:119-129`: `seen.insert(seat.name.to_lowercase())` failing returns `"two seats are named ..."`). The seat name is the operator-chosen `SeatConfig.name` (`config.rs:9-10`, "Display name, unique within the table"). The genesis name from `names.rs` is **not wired into `SeatConfig.name` anywhere in this copy** (`genesis_name` has zero callers here).

Therefore my GF3 ruling ("two same-named agents at one table cannot rate each other") **asserted a consequence whose scenario premise is unproven**. Two readings:
- **(a)** the seat name is the operator's `SeatConfig.name`, disjoint from the genesis name → two seats can never share a name (validation forbids it), and the collision consequence is **cross-table only**; GF3's exact wording ("at one table") is then **not right as written**.
- **(b)** the genesis name is somehow used as the display/rating name (the manager's `element.md:16` intent) → either it must pass `valid_seat_name` + uniqueness (rejecting `DeadeyeQuokka`... no, that's valid; but rejecting two colliding genesis names at seating), which would make the table fail to start, not merely block peer rating.

Under either reading, **GF3's stated failure mode (peer rating blocked by ambiguity) does not follow from its premise.** The correct verdict is therefore **GF3 partly right**: `elephant.gaps` correctly notes collisions and session-keyed storage (true, verified — collision space is 65536, ~49% collision odds at 300 agents), but the *operational* "cannot rate each other at one table" claim is unproven and probably wrong, because seat-name uniqueness blocks that table from starting.

**What should change (revised):** `elephant.gaps` should say **"Two sessions across tables can derive the same name; within one table seat names are unique (`config.rs:119-129`), so collisions matter cross-table, where the operator resumes the same genesis id under a name already used elsewhere."** The peer-rating-by-name ambiguity consequence should move to whichever element actually keys feedback by name, and must be re-derived there after confirming the feedback target is the seat name (uniqueness prevents ambiguity) versus the genesis name. My addendum's "GF3 also implies a code change in the turn element" is **downgraded to conditional**: it needs the turn element to confirm two same-named *seats* can exist, which validation currently prevents.

Net effect on the deliverable: still nine findings right, **GF3 reclassified to partly-right**. My original ruling over-reached by importing an unverified premise from the findings' citations; EminentStrike's `validate()` check is the decisive evidence and the resolution now records it.

Also confirmed independently: GF2's test vector (folded 14758, indices 57/166, `DeadeyeQuokka`) matches EminentStrike's numbers exactly, and no `Profile` field holds a name — so "add a fallback on failed resume" would silently change identity; failing loudly is correct.
