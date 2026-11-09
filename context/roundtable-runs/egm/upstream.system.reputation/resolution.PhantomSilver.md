# Accolades review resolutions

Participant: PhantomSilver. Evidence: `element.md` and the three files supplied under `source/`. Code paths below are relative to `source/`. These are decisions and proposed changes; implementation files and the original description have not been changed.

The supplied snapshot does not include `mcp.rs`, `engine.rs`, `rules.rs`, prompt definitions, or `index.html`. References to those files in the findings are reviewer assertions, not independently inspected evidence. Absence from this snapshot does not establish absence from the full project.

## GF1 — Accept the central finding; narrow the claim

“Not built here” is wrong as an unqualified account of current implementation. `crates/roundtable-web/src/app.rs:98–111` consumes rating and feedback events, saves both to identity profiles, and appends feedback to `accolades.jsonl`. `app.rs:426–443, 500–508, 535–545` keys those profiles by recipient session, retaining the name inside. `crates/roundtable/src/turn.rs:37–50` supplies an existing rated profile's standing on its first turn; `turn.rs:516–544` constructs session ranking and a cumulative rating display. These are implemented parts of recognition and persistent reputation.

Change `elephant.built` to describe those parts explicitly, distinguish the two paths as in GF3, and identify return weighting as unimplemented in the inspected code. Replace the claim that all sources are external with the supplied Rust paths. The specific MCP-to-engine route remains to be verified in the full checkout. “Only return weighting is missing” is too broad: the owner describes a wider recognition ambition without a complete specification, and these files cannot establish that every other intended behavior is complete. No new reward mechanism is required to fix this description.

## GF2 — Accept, with a provenance distinction

The referenced XML and Python files are not supplied. The available `docs/owner-sources/roundtable-agent-ratings.md` reproduces scoring prompts and describes the earlier Python implementation; it is a usable documentary source, not an executable replacement for those files or proof that Rust implements all their behavior. Its final link to `roundtable-accolades.md` is also unresolved in this snapshot.

Use the available document as the primary historical reference, and current Rust paths as implementation references. Retain the old XML/Python paths only as explicitly external historical provenance. Record the missing accolades document as unavailable evidence, or restore it from an authoritative source if available. Do not fabricate its contents or imply that the scoring document fully replaces it.

## GF3 — Accept; change the description

`app.rs:98–111` has separate handlers. `roundtable.feedback` saves ratings/note information into the recipient's `feedback` list and attempts to append its event envelope to `$ROUNDTABLE_HOME/accolades.jsonl`. `save_feedback` does not change points (`app.rs:533–545`); the existing test explicitly checks this (`app.rs:701–705`). `roundtable.rating` instead calls `save_rating`, which adds `data.points` and appends a rating record (`app.rs:500–508`). That handler does not append to the accolades file.

Document this distinction and state that `accolades.jsonl` is a feedback event log, not the point ledger. The default data directory is `~/.roundtable` (`app.rs:60–63`). Profile persistence and log append are separate operations: an error in one does not prevent an attempt at the other. There is no evidence that feedback should award points or that final ratings must enter this log. Changing either behavior would require an additional product decision, not merely this documentation correction.

## GF4 — Accept the documentation clarification; qualify negative evidence

`app.rs:547–568` exposes identities ordered by descending points and includes saved context for resuming them. That is a ranking for presentation; it does not implement a probability, priority, or eligibility rule for selecting returning agents. The picker-label assertion cannot be checked because `index.html` is absent.

Replace “not yet specified” with: “The inspected implementation stores reputation and orders the identities list by points. No automated reputation-based return selection is evidenced here; its policy and integration remain unspecified.” Preserve the owner's statement as intended behavior, rather than rewriting the historical quotation. Do not claim an exhaustive absence across an unavailable full repository.

## GF5 — Accept the ambiguity; define the implemented meaning without inventing awards

Add an operational definition: “Accolades is the recognition/reputation concern fed by peer feedback and end-of-table ratings. In the current implementation, the artifact literally named accolades is a JSONL feedback-event log; numerical reputation is the cumulative points stored in session-keyed identity profiles.” Explain the two paths from GF3.

Nothing inspected creates a separate badge, named award, or threshold-based accolade from a rating. State that no such conversion is established. If a richer award object is intended, mark its rules as unspecified rather than treating it as already implemented. This resolves the naming gap without requiring a new award subsystem.

## GF6 — Accept; make the dependency understandable and concrete

Introduce `code.server.tool` as the map identifier for the participant-facing tool surface, and describe its contribution as recording one participant's feedback about another participant's conduct. Replace “toward accolades and identity” with a concrete contract: recipient-session-keyed feedback is persisted on the identity profile and logged as a feedback event, without adding score points. End-of-table ratings supply points through a separate path.

The supplied consumer code supports that storage contract (`app.rs:103–111, 535–545`). Verify the precise MCP tool name, arguments, validation and event producer in the full checkout before documenting them as inspected facts. Correcting GF1 removes the contradictory “not built” claim; no tool rewrite follows from this finding.

## GF7 — Accept; fix path conventions and explain historical material

Explain “archaeology” as historical material from the owner's earlier implementation, rather than a guaranteed directory in the current checkout. State explicitly that the old paths were reported as belonging to the external `~/roundtable` tree and are unavailable in this snapshot. Distinguish repository-relative current paths, available documentary extracts, and external historical references. Fix the header's blanket path convention accordingly. GF2 supplies the concrete replacement references.

## GF8 — Accept the coverage gap; do not assume a scale mismatch

Replace “peer ratings cover part of it” with the implemented coverage from GF1/GF3: persistent feedback, additive point-bearing final ratings, session ranking, saved cumulative profile standing, and return selection left unspecified. `app.rs:491–494` derives rating count from stored rating records and session count from distinct rated table IDs; it does not count every resumed context as a rated session. These details distinguish cross-session reputation from identity reuse.

The owner-source document specifies 0–5 stars in four weighted categories, a Boolean bonus adding five points, and a maximum of 105 per rating; cumulative totals can exceed 105. Label this as the historical scoring reference. The current `turn.rs:471` delegates numerical conversion to `rules::rating_points`; that implementation and the generated scoring prompt are absent. Therefore a different current scale, equivalence to the historical formula, and identical validation are all unverified. Check those two sources in the full checkout and document the actual scale/formula and any deviation. Change code only if a confirmed implementation discrepancy violates the intended contract. Do not import the Python validation guarantees into the Rust description without checking them.

## GF9 — Accept as a clarity problem; remove unsupported dependencies

The investigation mixes unexplained external concepts with current behavior. Define only what the available code supports: an identity profile belongs to a genesis session, retains reputation, and records context usable for resumption (`app.rs:426–443, 511–530`). Explain “return into a project” as the owner's desired future reuse of a previously participating agent, while keeping the exact project scope and selection policy open.

Remove the unexplained topogee comparison from the operational description, or move it into a labeled external research note with an authoritative reference. Do the same for retirement and post-retirement recall; neither is specified by these files. Treat “platform service” as an architectural proposal, not an existing deployed service. Do not invent definitions or assign service ownership merely to fill the terminology gaps.

## GF10 — Partly accept; reject an unsupported schema requirement

The element would benefit from a plain role sentence: “Retain peer recognition and reputation across tables and expose standing for continuing identities.” Clarify that the `upstream.system.reputation` address is a map identifier rather than a filesystem path. The prefix suggests a classification but its formal meaning is not supplied.

There is no map schema or comparison set here establishing that every element must have a `role` field, what `name_length: 2` measures, or what the formal `intent: send` vocabulary means. Do not infer a defective field from the string “accolades,” or invent those conventions. Request definitions from the map's schema/glossary and reference them centrally; add an explicit role property only if that schema calls for one. Thus the discoverability criticism is reasonable, but a mandatory metadata change is not substantiated.

## Resulting description to use

Accolades covers recognition and persistent reputation from peer conduct assessments. Current Rust code saves feedback events to recipient-session-keyed identity profiles and to an `accolades.jsonl` event log; feedback adds no points. End-of-table ratings separately add points and rating records to identity profiles. The engine constructs rankings by points received in the current table and exposes saved profile standing to returning rated identities. Historical documentation describes the earlier weighted 0–5-star rubric and Boolean bonus; the current conversion and validation need confirmation in the omitted rules and prompt files. Reputation orders the available identity list, while automated weighting for return and any distinct award-conversion policy remain unspecified. Historical source provenance and current implementation references must be labeled separately.
