# Resolution of review findings for `upstream.judge.llm` (JEV)

Decisions on GF1–GF10. Each finding is judged against the code in `source/` plus the sibling copies of `turn.rs` and `rules.rs` that the findings cite (the same Roundtable crate is copied into each sibling `source/` folder; JEV's own `source/` contains only `crates/roundtable/src/jev.rs`). For each finding: whether it is right, and what should change in the code or the description, with the reason.

Verified code facts used throughout (from `source/crates/roundtable/src/jev.rs` and the cited sibling `turn.rs`/`rules.rs`):

- `jev.rs:42-59`: `contribution_questions()` builds a `BTreeMap` of **five** questions — three `noul` gates named `contribution`, `usefulness`, `relevance` (lines 43-47), then two `score` questions named `value`, `auditability` (lines 50-53). The header comment `jev.rs:5-7` and the test `jev.rs:191-194` confirm five questions, scores with 6 criteria levels, and no criteria on `relevance`.
- `jev.rs:150-175`: `ask()` returns `Result<BTreeMap<String, f64>, String>` — **one number per question name**, no reasons, no text. It reads `reply["answers"][name][question.kind]` as a float (line 168), range-checks `0.0..=top` (lines 165-170), and errors on out-of-range (line 170) or HTTP failure with the body cut to 300 chars (line 159).
- `rules.rs:13,15` (sibling `code.quota.character`): `GATE_PASS = 0.70` for the three yes/no gates and `SCORE_PASS = 3.0` for the two 0-5 scores.
- `turn.rs:204-226` (sibling `code.gate.quality`, `on_judged`): builds `checks` = gates at `GATE_PASS` chained with scores at `SCORE_PASS`, collects every `failed` check as `(name, value)` pairs, and on failure pushes `prompts::rejected(&failed)` to the seat and broadcasts a rejected `Contribution` whose `reasons` are `format!("{name} {value:.2}")`. **The rejection/reason text is assembled by Roundtable, not returned by JEV.**
- `turn.rs:152-167` (sibling): `!jev.configured()` (no key) → shared unjudged (line 152-153); a `contribution_state` error (message cannot fit) → loud `notice("error", ...)` then shared unjudged (lines 160-165). `on_judged` `Err(reason)` → loud notice + shared unjudged (the "JEV unavailable" branch).
- `jev.rs:1-3`: "No timer: it gets a reply or an error."
- `jev.rs:116-123`: `sameness_question` reads `resources/topic_sameness.md` and replaces `{{foo}}`/`{{bar}}` with `proposals.p{a}`/`proposals.p{b}`.
- `turn.rs:352-354` (sibling `code.selector.topic`): pairs batched under names `p{a}_{b}` from `rules::pairs(...)`.
- `jev.rs:62-72, 74-103`: `HISTORY_ROUNDS=4`, `STATE_PLUS_QUESTION_TOKENS=32_000`, `REQUEST_TOKENS=64_000`, `estimate_tokens` = one token per 3 bytes of JSON (`s.len().div_ceil(3)`), state holds `topic`, `conversation` grouped by round, `new_message`, oldest messages dropped first (line 101). `~typesafe/jev-latest` at `jev.rs:18`, decision route URL `jev.rs:16`.

---

## GF1 (Blocker) — RIGHT

The core claim is right and it is a Blocker: the `code.gate.quality` want at `element.md:15` says JEV "Returns a confidence for each of the three contribution conditions, with reasons for any that fall short, in one request." This is false on three counts, all verified in code:

1. There are **five** questions, not three: three `noul` gates plus two `score` questions (`jev.rs:42-59`).
2. `ask()` returns exactly one `f64` per question name and **no reasons of any kind** — the return type is `Result<BTreeMap<String, f64>, String>` (`jev.rs:152`, `162-174`).
3. The rejection text is built by Roundtable in `on_judged` from the failed `(name, value)` pairs (`turn.rs:204-216`), not by JEV. JEV supplies only numbers; the "reasons" are `format!("{name} {value:.2}")` strings that name which check fell below its threshold and its value.

This also contradicts the document's own `elephant` (`element.md:86`, "five checks") — a genuine internal inconsistency. **Consequence:** a caller reading the want would build a client expecting three confidences and human-readable reason strings, and would reject or mis-parse the five-number reply.

The score range is determined by six ordered criteria levels (`0..=levels.len()-1`, hence `0..=5`), independently of the acceptance cutoff of 3.0. Results are read as floating-point numbers; integer-only scores are not enforced.

**What should change — the description (the want), not the code.** The code is correct and self-consistent (five questions, one number each); the description is the stale artifact. Rewrite `element.md:15` (the `code.gate.quality` want's Function) to state that one request carries five questions (three yes/no gates + two 0-5 scores), that JEV returns one confidence/value per named question with **no** reasons, that the three gates pass at 0.70 and the two scores at 3.0, and that Roundtable (the caller) constructs the rejection text from the failing names and values. Also update `element.md:86` elephant "five checks" is consistent once the want is fixed — keep it. Do **not** change the code to add reasons: the owner statement (`element.md:71-74`) says confidence is consumed as a decision value/number, never as a similarity distance, and archaeology (`element.md:48`) describes `answers[name].noul = probability true` with no reason field. Adding model-generated reasons would require a separately specified and verified interface change; the supplied code does not establish whether the provider supports such a field.

## GF2 (Major) — RIGHT

The `references` note (`element.md:29`) says "the current spec specifies three conditions at 0.70." Verified: the code checks **three** gates at `GATE_PASS = 0.70` (`rules.rs:13-15`) **and** **two** scores at `SCORE_PASS = 3.0` used in `on_judged` (`turn.rs:207-210`). So "three conditions at 0.70" is an incomplete description of the pass criteria — it omits the two score thresholds entirely and implies 0.70 applies to all five checks.

This is Major (an important gap), not a Blocker, because the note is about a comparison to run 1's four-score setup at 0.83; the missing score thresholds mislead about how many checks exist and at what level, which feeds directly into the GF1 confusion.

**What should change — the description.** Amend `element.md:29` (and, consistently, the `owner_statements` note at `element.md:68`) to say the current spec sets **three yes/no gates at 0.70 and two 0-5 scores at 3.0**, i.e. five checks total. The owner statement "0.70 is better for this purpose" (`element.md:67`) is specifically about the `code.gate.quality` threshold and is confirmed by `rules.rs:13`; it remains true, but should be annotated that it governs the gates only, with the scores at 3.0. No code change: thresholds are correct in `rules.rs`.

## GF3 (Major) — RIGHT

All four sub-claims are verified in `jev.rs`:
- `score` question type carries ordered `criteria` levels (`jev.rs:20-40`, `score()` splits instructions from one-level-per-line criteria; test `jev.rs:192-193` shows 6 levels).
- State contents: topic, `HISTORY_ROUNDS=4` completed rounds plus current round (comment `jev.rs:61`, `first = round.saturating_sub(4)` at `jev.rs:80`), and `new_message`, oldest dropped first (`jev.rs:101`).
- Two token limits: `STATE_PLUS_QUESTION_TOKENS=32_000` and `REQUEST_TOKENS=64_000` (`jev.rs:64-66`, enforced at `jev.rs:94`).
- Token estimate one per 3 bytes (`jev.rs:68-72`), and out-of-range answers are errors (`jev.rs:163-171`).

None of this is in `element.md`. This is Major: a caller integrating JEV needs the request shape (`{model, state, questions}`), the two question types and their answer ranges, the state schema, the two token budgets, and the estimation rule. Without it, the `investigations` note (`element.md:39`) about "64K input" is the only hint and it does not say 32K applies to state-plus-longest-question or that answers are range-checked.

**What should change — the description.** Add a layer (e.g. extend `archaeology` or add a `contract`/`interface` layer) documenting: request body `{"model","state","questions"}`; question types `noul` (answer 0..1 probability) and `score` (answer 0..last-criteria-level, ordered levels in `criteria`); the five named question set; state fields (`topic`, `conversation` grouped by round of last 4 completed + current round, `new_message`); `HISTORY_ROUNDS=4`, estimated state-plus-longest-question <= 32,000 and estimated state-plus-all-questions <= 64,000; estimate = ceil(JSON UTF-8 bytes / 3); the outer request envelope and model are omitted from that check, so it is not an exact full-body or provider-token guarantee; oldest messages dropped first; out-of-range or missing answers are errors. No code change — the code is correct; the gap is documentation.

## GF4 (Major) — RIGHT

Verified failure behaviour, none of it in `element.md`:
- No key (`!self.jev.configured()`) → shared unjudged, `turn.rs:152-153` (sibling `code.gate.quality`). The finding's cite `turn.rs:152-167` covers this and the "cannot fit" case.
- Message that cannot fit (`contribution_state` `Err`) → `notice("error", ...)` loudly + shared unjudged, `turn.rs:160-165`.
- JEV error (`on_judged` `Err(reason)`) → loud notice + shared unjudged with "JEV unavailable", `turn.rs:199-203` region (the exact notice line in the sibling is just after `on_judged`'s `Err` arm).
- No timer: `jev.rs:3` "No timer: it gets a reply or an error."
- HTTP error bodies cut to 300 chars: `jev.rs:159`.

This is Major: "shared unjudged on failure" is a security/quality-relevant behaviour (a message that bypasses the gate is broadcast to every participant), and a caller must know that this module adds no evaluation timer and that messages exceeding JEV context budgets or producing evaluation errors are shared unjudged. This does not override the separate character-length rejection earlier in the caller. `element.md` currently says nothing about any failure path.

**What should change — the description.** Add a `failure behaviour` note to the element: no key / oversized message / JEV error all result in the contribution being **shared unjudged** (not rejected), errors produce a loud notice, this module adds no evaluation timer (the injected reqwest client may have its own timeout), and HTTP error diagnostics include only the first 300 characters of the response body. The full response body is read before that truncation, so this is not a download-size cap. Note the design consequence: the `code.gate.quality` want's "decide before broadcast whether a contribution is worth every other participant's input tokens" is **best-effort**, not guaranteed — on any of these failures the gate is bypassed. This reconciles the want with reality. No code change.

## GF5 (Nit) — RIGHT, no change required (for the record)

The `code.selector.topic` want (`element.md:16`) says pairs "may be batched in one request" and JEV "judges whether two proposed topics express the same underlying intent and returns a confidence for each pair." Verified accurate: `sameness_question` uses `resources/topic_sameness.md` with `{{foo}}`/`{{bar}}` replaced (`jev.rs:116-123`), and pairs are batched under names `p{a}_{b}` (`code.selector.topic/.../turn.rs:352-354`). This is a "Nit ... For the record" finding — it is an accurate observation, not a defect. **Decision:** right as a factual note; no change to code or description is required. Optionally add the two citations to the want as supporting detail, but this is a Nit and not necessary.

## GF6 (Major) — PARTLY RIGHT

The missing gate names and incomplete current want are real defects. However, three gates plus two scores are compatible with five checks. The owner statements approve the gate cutoff and explain JEV's role; they do not claim that there can only be three checks. The five-question specification is separately attributed to the owner on 7 November in `jev.rs:5–7`. Preserve the dated statements and annotate their scope rather than treating them as contradictory. The three unnamed gates are `contribution`, `usefulness`, and `relevance`; the two scores are `value` and `auditability`.

**What should change — the description.** Name the three gates (`contribution`, `usefulness`, `relevance`) and the two scores (`value`, `auditability`) in the want and/or a new contract layer, and make the count consistent everywhere: five checks per message (three gates + two scores). The elephant's "five checks" is correct; keep it. Reconcile the owner statement (0.70 for this purpose) as gate-specific (see GF2). No code change.

## GF7 (Major) — RIGHT

Verified: `jev.rs:18` uses `~typesafe/jev-latest` ("The owner's choice: always the newest JEV release"), while archaeology (`element.md:48`) records the pinned dated snapshot `typesafe/jev-1.13` (`-20260917`). The `~` prefix and the move off a pinned snapshot are not explained anywhere in `element.md`. "decision route" in the elephant (`element.md:86`) only makes sense as `POST /api/alpha/decisions` via archaeology (`element.md:48`), but that connection is not stated. This is Major: pinning vs. "latest" changes reproducibility — a dated snapshot gives stable behaviour, `~...-latest` means the model behind the gate can change at any time without a code change, which directly affects the "accuracy falls as irrelevant state grows / leans toward first option" weaknesses in archaeology (`element.md:52`) and the unverified operating characteristics.

**What should change — the description.** Add a note to `elephant` / `archaeology`: the current code calls `~typesafe/jev-latest` through `DECISIONS_URL = https://openrouter.ai/api/alpha/decisions` (`jev.rs:16`); the code passes the leading `~` verbatim and does not define its meaning. The adjacent comment attributes choosing the newest JEV release to the owner; it does not establish which part of the identifier implements provider routing. Mark provider interpretation of `~` as unverified rather than asserting an undocumented syntax rule. State explicitly that archaeology describes a **dated, earlier snapshot** and that the "decision route" is `/api/alpha/decisions`. Mention that `~...-latest` trades reproducibility for always-current behaviour. No code change (the code is the owner's deliberate choice); the gap is the unexplained drift between the documented archaeology model and the running model.

## GF8 (Major) — RIGHT

Verified as a real open inconsistency in `element.md`:
- `investigations` (`element.md:39`): "~$0.42/M input", owner-supplied, unverified.
- `archaeology` (`element.md:56`): "PRICE CONFLICT: the archive records $0.042 per million input tokens; README 5 says ~$0.42. Unverified." — a 10× discrepancy ($0.042 vs $0.42).
- `elephant` (`element.md:86`): "about $0.00005 per message for five checks" — does not say which price it assumes.

This is Major: a 10× price difference changes the cost estimate that justifies "judges each message cheaply before it reaches the group" (`element.md:82`), and the per-message figure is unreconstructable without knowing the assumed price and token count. `element.md:39` already flags that operating characteristics must be verified against OpenRouter.

**What should change — the description.** In `investigations` and `elephant`, state that the price conflict is **unresolved** and must be verified against OpenRouter before any cost claim is relied on; annotate `$0.00005 per message` with the assumed input price (which of $0.042/M or $0.42/M) and the assumed tokens per message, or mark it as an unverified estimate. Do **not** silently pick one price. No code change — cost is not in the code; this is a documentation/verification item. Optionally add a targeted action: verify the live `~typesafe/jev-latest` input price on OpenRouter and record the result.

## GF9 (Nit) — RIGHT

`archaeology` (`element.md:48`) uses the term `noul` ("each question `{type:'noul', ...}`", "`answers[name].noul = probability true`") without explaining what `noul` means, and the request shape `{model, state, questions}` / `criteria:{true,false}` is given only as a compact literal. Verified from `jev.rs:20-33`: a `noul` question is a yes/no question whose answer is "how sure JEV is that the answer is yes (0 to 1)"; the reply is read at `reply["answers"][name]["noul"]` (`jev.rs:168`). The archaeology's `criteria:{true,false}` is the older/pinned-snapshot shape; the current code uses `criteria: Option<Vec<String>>` only for `score` questions and `None` for `noul` (`jev.rs:27-33`). This is a Nit (terminology/readability), not a defect in behaviour.

**What should change — the description.** Add a one-line gloss to `archaeology`: "`noul` = a yes/no question answered as a probability (0..1) that the answer is yes" and note that the request is `{model, state, questions}` where each question has `type`, `instructions`, and (for `score`) ordered `criteria` levels. Also note the pinned-snapshot `criteria:{true,false}` wording differs from the current `noul` (no criteria) / `score` (ordered string levels) shape, which GF3's new contract layer will spell out. No code change.

## GF10 (Nit) — RIGHT

`element.md:3` says "Paths are relative to the Roundtable folder," but the `references` layer (`element.md:28`) contains `~/topogee/docs/roundtables/1-embodied-ai-in-a-3d-physics/Roundtable_1_First_Run_Analysis_and_Failure_Audit.md` — a home-directory absolute-ish path. This breaks the header's own rule. Verified by inspection of the document itself. Nit severity is appropriate (a documentation-path inconsistency, no behavioural impact).

**What should change — the description.** Either (a) restate the header to say reference paths may be absolute/home-relative while code paths are relative to the Roundtable folder, or (b) relocate/copy the referenced run-1 analysis into the Roundtable folder and use a relative path. Recommendation: **(a)** is lower-effort and honest — the run-1 audit is an external historical artifact, not part of the Roundtable tree, so forcing it into the relative-path convention would misrepresent where it lives. Add a note in the reference entry that it is an external document outside the Roundtable folder. No code change.

---

## Summary table

| Finding | Right? | Severity agreed? | Change |
|---|---|---|---|
| GF1 | Right | Blocker | **Description**: rewrite `code.gate.quality` want — five questions, one number each, NO reasons, reasons built by caller; gates 0.70 / scores 3.0. No code change. |
| GF2 | Right | Major | **Description**: note should say three gates at 0.70 AND two scores at 3.0. |
| GF3 | Right | Major | **Description**: document request shape, `noul`/`score` types + ranges, state schema, 32K/64K limits, 1-token/3-byte estimate, range-check errors. |
| GF4 | Right | Major | **Description**: document shared-unjudged failure paths, no timer, 300-char error cut, and that the "before broadcast" gate is best-effort. |
| GF5 | Right (accurate, for the record) | Nit | No change required; optionally add the two citations. |
| GF6 | Partly right | Naming and scope gap accepted | **Description**: name the three gates + two scores; preserve gate-specific owner statements. Three gates plus two scores are compatible with five checks. |
| GF7 | Right | Major | **Description**: explain `~...-latest` vs pinned `jev-1.13`, that the owner intends newest-release selection while provider semantics of `~` remain unverified, and that the "decision route" = `/api/alpha/decisions`. |
| GF8 | Right | Major | **Description**: flag the $0.042 vs $0.42 conflict as unresolved; state the price assumed by $0.00005/message; verify on OpenRouter. |
| GF9 | Right | Nit | **Description**: gloss `noul` = yes/no probability; note current shape differs from the pinned-snapshot `criteria:{true,false}`. |
| GF10 | Right | Nit | **Description**: fix the header rule or mark the run-1 path as external; recommend the latter. |

**Overall:** the description needs corrections for the accepted findings; GF5 confirms existing behavior and GF6 is only partly right because the owner statements do not contradict five checks. The inspected code supports the documented five-check design; the defects are all in `element.md` — stale/incomplete wants, an internal count inconsistency, an unexplained model change, an unresolved price conflict, undocumented contract and failure behaviour, and two nits. No code changes are recommended. The description should be updated and the two open verification items (live model price, `~` semantics) confirmed against OpenRouter.
