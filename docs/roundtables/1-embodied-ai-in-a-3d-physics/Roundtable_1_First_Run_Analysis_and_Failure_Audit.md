# Roundtable 1: Embodied AI in a 3D Physics Environment

**First-run experiment report and roundtable failure audit**  
**Session:** `code.interface.graphical` · **Date:** 14 October 2026  
**Scope:** 11 models · 71 rounds · 775 scheduled turns · observation-only human chair  
**Source:** `1-embodied-ai-in-a-3d-physics.json`

> **Interpretation:** This was an exploratory first run, not a controlled comparison or a working embodiment demonstration. The human deliberately observed rather than directing the discussion, and deliberately allowed the roundtable to continue after OpenRouter credits ran out. Neither decision should be classified as an orchestration failure.

## Executive assessment

The first run showed **cross-model idea development** and **unassigned functional specialization**. Within two rounds, different seats had begun recurring lines of work: Gemini expanded physical capabilities, Grok named physical and simulation faults, Opus emphasized useful interaction, Fable developed implementation and interface contracts, and Astra repeatedly checked assumptions. Later turns show ideas crossing seats and being refined.

It also exposed major weaknesses in the *roundtable mechanism*: the operator reports an incorrectly constructed OpenRouter prompt; prompt payloads were not retained; prompt lengths grew beyond 71,000 tokens; 68 seat attempts failed with HTTP 402; a model repeated an identical proposal 26 times; several submissions had wrong turn identifiers; the novelty-oriented evaluator rejected administrative warnings and synthesis attempts; and the reporter's native report was lost. These defects limit what can be concluded about model quality or collaboration.

The most important distinction is **productive collaboration despite mechanism failures**, not productive collaboration *because* the failures happened. The full raw record supports an initial analysis but not causal claims about emergence.

## 1. Experimental setup and source integrity

The opening request asked for effective approaches to AI embodiment in a 3D physics environment, including first-person perception, available controls, and what the person sees. Eleven seats participated through ACP and OpenRouter. The user assigned **no specialist roles** and did not intervene turn by turn. A separate Jev evaluator (`typesafe/jev-1.13`) scored each substantive proposal on `new`, `valuable`, `relevant`, and `keep`; all four scores had to reach 0.83 for inclusion.

The record preserves the model/seat identity, slot and round, produced text when available, inclusion status, score tuple, coarse error reason, and timestamp. It **does not preserve the rendered per-model prompts, the full input context for each generation, Jev's full evaluation prompt or raw response, per-call token/cost accounting, or the reporter's execution trace**. The operator additionally reports that the OpenRouter prompt was misconfigured. That report is taken as an operational observation, but the exact prompt defect cannot be reconstructed from this export.

| Measure | Recorded result |
|---|---:|
| Scheduled seat turns | 775 |
| Non-empty submissions | 659 |
| Included by Jev | 340 |
| Excluded by Jev | 314 |
| Excluded for >512 characters | 5 |
| No submission | 116 |
| Rounds | 71 (round 71 ended after its fifth slot) |
| Explicit backward turn references | 185 across 131 submissions |
| Cross-seat backward references | 163 across 119 submissions |
| First submission | 07:05:54 UTC |
| Last submission | 11:20:53 UTC |
| Session end recorded | 15:56:40 UTC |

The 775 scheduled slots equal seventy complete 11-seat rounds plus five slots of round 71. The session metadata spans **8 h 51 m**, but the actual recorded submissions span **4 h 15 m**. The **4 h 35 m 47 s** interval between the last turn and recorded ending is unexplained by the export; it is not evidence by itself of a hang.

### Seat-level results

`Submitted` counts non-empty seat messages; `slots` also includes failures. `Retained %` is the fraction of submitted messages included by Jev, **not a model intelligence score**.

| Seat | Slots | Submitted | Included | Retained | Jev reject | >512 | No reply |
|---|---:|---:|---:|---:|---:|---:|---:|
| Astra | 71 | 71 | 43 | 60.6% | 28 | 0 | 0 |
| Sol | 71 | 71 | 10 | 14.1% | 61 | 0 | 0 |
| Gemini | 71 | 56 | 51 | 91.1% | 5 | 0 | 15 |
| Kimi | 71 | 56 | 14 | 25.0% | 42 | 0 | 15 |
| DeepSeek | 71 | 60 | 19 | 31.7% | 41 | 0 | 11 |
| Opus | 70 | 70 | 50 | 71.4% | 20 | 0 | 0 |
| Sonnet | 70 | 70 | 40 | 57.1% | 29 | 1 | 0 |
| Fable | 70 | 70 | 53 | 75.7% | 14 | 3 | 0 |
| Qwen | 70 | 49 | 6 | 12.2% | 43 | 0 | 21 |
| GLM | 70 | 32 | 18 | 56.2% | 14 | 0 | 38 |
| Grok | 70 | 54 | 36 | 66.7% | 17 | 1 | 16 |

### Failed seat calls by recorded reason

| Recorded reason | Count |
|---|---:|
| HTTP 402: insufficient credits | 59 |
| HTTP 402: prompt exceeds current token affordability | 9 |
| Empty response | 44 |
| HTTP 429: upstream rate limit | 3 |
| Connection reset | 1 |

The **68 HTTP 402** events split into 59 ordinary insufficient-credit errors and nine cases where prompt token counts exceeded what the remaining balance would afford. Those nine errors showed input lengths from **56,837 to 71,825 tokens**; the right-hand limits changed with available funds. This is evidence of an expensive and expanding request payload, **not proof that a model's architectural context window was exceeded**.

## 2. What the models collectively produced

The technical discussion developed a coherent design direction: slow model inference chooses goals or short skills; fast controllers advance physics; the agent observes through its own declared sensing channels; the person can inspect intent, action, evidence and replay; scene edits are distinguished from physical movement. This is an ideation result. Nothing in the record demonstrates implemented controls, measured physics performance, or an embodiment working in the virtual environment.

### Functional differentiation appeared early

- **Astra:** T1 framed the observe/act/verify loop; T12 separated observation from explanation and added stale-scene detection. Later turns disproportionately refined other seats' proposals.
- **Gemini:** T14 proposed spatial/tactile memory and sensing; T25 moved to physical probing; later proposals broadened locomotion, manipulation and material-specific skills.
- **Grok:** T11 challenged preview realism; T22 tracked attention loss; later turns concentrated on contact, kinematics, solver edge cases and diagnosable faults.
- **Opus:** T6 focused on cheap structured perception and a readable user view; T17 defended user-camera ownership; T39 proposed relational targets rather than raw coordinates.
- **Fable:** T8 introduced stable shared object addresses; T19 proposed paused-world deliberation; T41 one declaration per control; T272 model-written reflexes; T503 readable behaviour trees.
- **Sonnet:** T7 introduced the ghost-preview interface, T40 physics-glitch attribution, and later task authority and replay mechanisms.

These were **not assigned responsibilities**. Nevertheless, roles being visible by the first or second round means the evidence cannot distinguish models' initial response tendencies from roles reinforced by deliberation. Both are plausible.

### Observable development across seats

| Idea trajectory | What changed |
|---|---|
| Sonnet **T7** → Grok **T11** → Fable **T283** | Ghost previews gained speculative physics, then human-editable plan geometry. |
| Opus **T149** → Astra **T155** | Deferred event delivery became a causally ordered, acknowledged sequence with resynchronization. |
| Opus **T116** → Fable **T261** → Astra **T265** | Observing human attention led to an audit of watched/unwatched behavior, then a matched-trial caveat. |
| Fable **T272** → Astra **T276** → Fable **T503** → Astra **T507** | Controller reflexes led to questions about bounded execution, readable trees and node cancellation. T276 was rejected by Jev, so the full record—not only accepted material—is required to see that critique. |

Astra made **56 explicit cross-seat backward references**. One-sided references are evidence of engagement with earlier text, not a verified causal graph of the models' internal reasoning. Fixed seat order also matters: later contributors can be judged less novel for making similar initial points. For example, Gemini's T3 closely mirrored T1/T2 and was rejected for low novelty, whereas the earlier similar contributions survived.

### The continuing discussion

At **T182 / round 17**, Opus proposed closing the table because it believed diminishing novelty justified synthesis. Jev rejected the proposal. Only **96** contributions had been retained up to that point; **244 more** were retained afterward. That makes the operator's decision not to force an early ending consequential: additional accepted work did occur. It does **not** show that indefinitely extending a run is always beneficial.

OpenRouter availability declined gradually from round 56 onward; **14 non-empty OpenRouter messages still arrived among the final 160 slots**, primarily from DeepSeek, GLM and Qwen. Describing that entire period as ACP-only, as the first retrospective did, is factually inaccurate. The five ACP seats became the consistently responsive group while some OpenRouter seats still contributed intermittently.

| ACP-only comparison | Non-empty | Included | Included share | Mean Jev `new` |
|---|---:|---:|---:|---:|
| Before credit failures | 275 | 148 | 53.8% | 0.805 |
| After failures begin | 77 | 48 | 62.3% | 0.837 |

The post-failure ACP share and mean novelty score were numerically higher. This is **descriptive**, not a finding that losing other participants improved collaboration: topics, context, group composition and the remaining time all changed.

## 3. Mechanism failure register

This register covers **all distinct failure classes directly visible in the exported first run**, plus the operator-reported OpenRouter prompt defect. It does not claim to enumerate hidden runtime faults that were never logged. `Confirmed` means directly supported by JSON; `Reported` is the operator's statement; `Inference` is an interpretation of observed behavior.

### A. Prompt assembly, OpenRouter and model transport

**P01 — OpenRouter prompt construction failure (Reported; high impact).** The operator reports the prompt sent to the OpenRouter seats was wrong. The export contains responses and errors but not the actual fully rendered request or its system/developer/user message arrangement. The exact offending instruction, context assembly step or serialization error therefore remains unknown. **Do not label the repeated output as proof of a particular prompt bug.**

**P02 — Unbounded or oversized provider-side context (Confirmed symptom; high).** OpenRouter errors at **T616, T627 and T680–T746** reported prompt lengths of **56,837–71,825 tokens** against declining affordable-token ceilings. The growing payload was plainly expensive; whether it resulted from full-history replay, duplication, or another assembly fault cannot be established without the prompts.

**P03 — Disproportionate output reservation (Confirmed symptom; medium).** Later HTTP 402 errors said requests reserved **up to 4,000 output tokens** even though the roundtable enforced a **512-character submission** limit. This increased the amount providers had to consider affordable. The export does not establish how many output tokens were actually generated or billed.

**P04 — Provider-credit exhaustion and repeated failed attempts (Confirmed; high).** **68 HTTP 402 failures** were recorded, starting with Grok at T616, Gemini/Kimi at T619/T620, and continuing on other seats. The chair deliberately allowed the overall deliberation to continue. The observed mechanism weakness is repeated futile requests and absent per-seat availability accounting, **not** the lack of a forced global stop.

**P05 — Upstream rate limits and connection loss (Confirmed; medium).** Qwen returned **HTTP 429 at T405, T427 and T669**; Grok experienced one **connection reset at T308**. The record shows no fine-grained retry/backoff trace, so it cannot establish whether recovery was attempted.

**P06 — Empty generations (Confirmed; high).** **44** seat calls returned empty replies: **27 GLM, 9 Qwen, 8 DeepSeek**. Several began well before credit exhaustion (GLM at T43, T54). These represent lost participation for reasons not explained beyond `the reply was empty`.

**P07 — Identical model-response loop (Confirmed; high).** **Kimi returned exactly the same proposal 26 times**, beginning at **T268** and recurring through **T609**. Each was vetoed. That is a generation/prompt-feedback failure symptom and a clear loss of productive turns; no captured input proves whether the cause was model behavior, stale prompt state, caching, or repeated context.

**P08 — Cut-off textual responses (Confirmed; medium).** Qwen's **T9** ends with `UI: agent+`; DeepSeek **T214** contains only `T214: Give the agent a`; GLM's **T461** and **T571** appear to end mid-sentence. These are examples of content-level incompleteness. The export lacks the raw stream/stop reason needed to identify truncation versus provider errors.

**P09 — 512-character contract violations (Confirmed; low/medium).** Exactly **five** submissions were rejected as overlength: **T426, T429, T469, T635, T668**, with recorded lengths of 513–523 characters. The rule operated as specified, but the generation/format interface did not consistently honor it; some otherwise useful proposals were discarded for a small overrun.

### B. Evaluator, communication and discussion process

**E01 — Novelty dominated selection (Confirmed; high).** Jev rejected **314** judged contributions; **303** of those failed the `new` threshold (sometimes alongside other criteria). Novelty filtering successfully excluded repetitions, but also made it easier to discard careful refinements, synthesis, and operational messages. Inclusion rates therefore reflect evaluator preference as well as contributions.

**E02 — Operational warning rejected as off-topic (Confirmed; high).** At **T755**, Sonnet explicitly notified the chair about OpenRouter credit failures and suggested topping up or closing. Jev gave it **`relevant: 0.04`** and excluded it. Health/status communication was being assessed as if it were another embodiment proposal. Whether the chair received a separate warning is not in the record.

**E03 — Closure/summary proposals not given a distinct route (Confirmed behavior; high).** Opus **T182** proposed a pass, closing, and an outline for the report; Jev excluded it. Opus **T83** and Sonnet **T183** offered implementation prioritization/synthesis and were also excluded. A topical novelty score is not an adequate proxy for whether the discussion needs a summary, a health notification, or a voluntary pass. This observation does **not** recommend automatic discussion termination.

**E04 — Fixed order confounds model comparison (Confirmed design confound; medium).** Astra and Sol submitted first in each round; Gemini and other models followed. The strong `new` threshold penalizes later restatements (T3 and T9), so retained percentages cannot fairly rank the models without varying position and context.

**E05 — No reproducible Jev judgment trace (Confirmed missing evidence; high).** The JSON explicitly notes that **the exact state sent to Jev, its raw response and its cost were not stored**. Scores remain observable, but why a threshold was assigned, and whether judging drifted as context grew, cannot be audited from this artifact.

**E06 — No direct proof of each model's received context (Confirmed missing evidence; high).** The export logs a seat's answer, not the full sequence of accepted/rejected submissions and instructions presented to that seat at that moment. Inferences about influence rely on chronological wording and references; they cannot reconstruct the exact accessible context.

### C. Record integrity, lifecycle and reporting

**D01 — Turn-label inconsistencies (Confirmed; high).** **15** generated `T###:` prefixes disagree with the canonical `submissions[].number`; **eight** of these incorrect labels were included. Examples: **T501** labels itself `T502`; **T502** labels itself `T503`; **T572** labels itself `T562`. This produces **nine duplicated self-declared labels**. Canonical JSON numbers remain usable, but citations copied from model text can become ambiguous.

**D02 — `turns_taken` means two different things (Confirmed; medium).** `seats[].turns_taken` tracks scheduled slots (Gemini **71**, GLM **70**), while `summary.kept_by_seat[].taken` tracks non-empty submissions (Gemini **56**, GLM **32**). Without a clear distinction, seat-level performance and failures can be misread.

**D03 — Seat availability not expressed in seat metadata (Confirmed; medium).** Every seat's `gone` field remains null, even after repeated HTTP 402 errors make seats effectively unavailable. The raw submission log reveals the problem; the seat metadata alone does not.

**D04 — Reporter failure and missing native report (Confirmed result; high).** The user reports the reporter seat died. Session JSON records **`report: null`**. The retrospective written afterward demonstrates that the full turn record survived, but the native reporting path did not deliver. The reporter's own error or death event is not available to diagnose the cause.

**D05 — Incomplete per-call observability (Confirmed; high).** The export omits per-provider request bodies, raw responses, token consumption, monetary costs, latency accounting and Jev judge trace. It therefore cannot directly diagnose the reported OpenRouter prompt defect, cost amplification or many response failures.

**D06 — Unexplained terminal interval (Confirmed fact, unknown cause; medium).** The final recorded submission is at **11:20:53 UTC**, whereas `discussion.ended` is **15:56:40 UTC**. The intervening **4 h 35 m 47 s** has no turn events here. It could reflect an idle scheduler, manual waiting, a stalled cycle, or activity not represented in this export. The record is insufficient to decide.

**D07 — Retrospective mischaracterized the final participation window (Confirmed; medium).** The first after-the-fact report said only ACP seats spoke during the final 160 turns; **14 OpenRouter messages actually contain submissions** in that window. This is a report-accuracy defect, not a failure of the participants.

**D08 — Participation and content scopes drifted (Observed interpretation; medium).** The opening was a virtual 3D embodiment interface, but later work moved extensively into real-world robot regulation, human contact, machinery standards and certification. Some ideas are useful future analogies. However, the record does not establish those requirements for the actual virtual playground; they should not silently become implementation requirements.

**D09 — No experimental control for the emergence claim (Confirmed methodological limit).** There is one discussion, one order, and one evaluator configuration. There is no solo-agent baseline, alternate seat order, rerun with corrected prompts, or measurement of what each model would have suggested independently. Role differentiation is observed; its causal origin is not established.

## 4. Failure chronology and points of detection

| Turn / round | Event | Significance |
|---|---|---|
| **T3 / R1** | Gemini's near-repeat of T1/T2 is vetoed for novelty. | Immediate fixed-order/novelty interaction. |
| **T9 / R1** | Qwen submits a visibly cut-off recap; Jev excludes it. | Prompt/response quality problem visible from start. |
| **T43 / R4** | GLM returns an empty reply. | Lost participation predates credit exhaustion. |
| **T83 / R8** | Opus' build-priority synthesis is excluded. | Discussion management competes with novelty scoring. |
| **T182 / R17** | Opus proposes a pass and closing; Jev excludes it. | No separate recognized administrative/synthesis channel. |
| **T214 / R20** | DeepSeek returns only a fragment. | Silent incomplete-generation symptom. |
| **T268 / R25** | Kimi begins a 26-copy repeat sequence. | Stale-response or prompt-feedback problem. |
| **T308 / R28** | Grok connection reset. | Transient transport failure. |
| **T405 / R37** | Qwen 429 rate limit, later repeated. | Upstream throttling. |
| **T426 / R39** | First >512 character rejection. | Length contract not fully adhered to by seat. |
| **T501–503 / R46** | Turn-label collisions. | Provenance ambiguity can survive Jev. |
| **T616 / R56** | Grok HTTP 402; prompt 56,837 > 16,478 affordable tokens. | Prompt-cost failure begins. |
| **T619–620 / R57** | Gemini and Kimi HTTP 402. | Provider availability deteriorates. |
| **T680–746 / R62–68** | Qwen prompt counts climb 65,505 → 71,825. | Request growth observable despite credit pressure. |
| **T755 / R69** | Sonnet sends credit warning; Jev vetoes it. | Operational health message suppressed. |
| **T775 / R71** | Last recorded slot, incomplete round. | Run stops at fifth seat in final round. |
| **15:56:40 UTC** | Chair's ending recorded. | Reporting remains null; final-interval activity unknown. |

## 5. Root-cause boundaries: what is known and unknown

| Claim | Evidence classification | Interpretation |
|---|---|---|
| The OpenRouter prompt was incorrectly built | **Operator reported** | Accept as a stated defect; exact source not in export. |
| OpenRouter requests grew to 71,825 prompt tokens | **Confirmed** | Error messages report sizes; assembly mechanism unavailable. |
| Kimi returned the identical text 26 times | **Confirmed** | Could reflect prompt state, caching, model repetition or their interaction. |
| Poor retained percentage implies a weak model | **Not established** | Fixed order, novelty metric and prompt defects confound comparisons. |
| A model spontaneously acquired a persistent professional role | **Not established** | Unassigned thematic specialization appears, but causal evidence is missing. |
| The credit outage ruined all subsequent reasoning | **Not supported** | Five ACP seats continued, with retained technical proposals; 14 OpenRouter submissions also arrived. |
| The reporter failed but the turn history survived | **Confirmed outcome** | Cause of reporter failure is not retained. |
| The discussion should have ended at T182 | **Not established** | There were 244 later retained contributions. Ending then would have discarded them. |

## 6. Priorities for a second experiment (separate from observed results)

These are **diagnostic follow-ups**, not authorized code changes and not additional behavioral gates.

1. **Preserve the actual OpenRouter request payloads.** Capture the assembled message roles, instruction text, context selection, prompt token count, requested `max_tokens`, provider/model, raw response and stop reason for each seat invocation. Use a controlled re-run to isolate the operator-reported prompt defect. Include appropriate redaction when sharing logs.
2. **Separate operational events from discussion proposals in the record and report.** Test delivery of credit warnings, reporter crashes and voluntary passes independently of Jev's topical `new/valuable/relevant/keep` scoring. Do not make continuation contingent on a model's convergence claim.
3. **Track participating, responsive and unavailable states separately.** Confirm that 402, 429, reset and empty generations are described accurately without forcibly terminating the rest of the discussion. Distinguish scheduled slots from actual submissions in the schema.
4. **Reproduce the 26-message Kimi loop using the exact captured prompts.** Compare generation with the same turn context, a fresh context, and any request caching or retry behavior actually configured. Report the observed cause before changing the mechanism.
5. **Audit identifier handling.** Use canonical JSON submission numbers for references and preserve any model-authored `T###` text as content, rather than allowing the generated prefix to redefine provenance.
6. **Run a controlled comparison only after correcting the prompt.** Repeat the same topic with shuffled seat order and a solo-agent baseline, keeping the judging protocol explicit. This will help distinguish independent model tendencies from interaction-driven specialization.
7. **Reconcile evaluator purpose with outcomes.** Measure novel technical proposals, legitimate refinements, synthesis and operational contributions separately in the analysis. This is a measurement proposal, not a requirement to filter, forbid or constrain the agents' open-ended contributions.
8. **Test native report recovery.** Intentionally interrupt the reporter once, confirm the recovery record includes the failure reason, and verify the run can still produce its own summary without replacing the raw history.

## 7. Conclusion

**Successful first-run discovery:** Eleven models developed complementary lines of thought without assigned roles. The chronological archive contains 163 explicit cross-seat references and compelling examples of design proposals being challenged or extended. The five ACP seats continued producing contributions after the OpenRouter credit failures began, and 244 retained proposals followed the first suggestion to end.

**Unsuccessful first-run instrumentation:** Prompt correctness, provider payloads and costs, judge inputs, seat availability, reporter lifecycle and identifier integrity were not all trustworthy or reconstructable. The OpenRouter prompting mistake and the 26-copy Kimi loop make cross-model performance comparisons especially unsafe. The record also captures a judging mechanism that can reject operational warnings and synthesis because they are not novel subject matter.

**Bottom line:** The roundtable is a promising deliberation experiment with a valuable surviving primary record. The first experiment demonstrates *observable complementary collaboration* and *diagnosable mechanism failures*; it does not yet demonstrate a measurable gain over independent models or isolate the cause of the prompt failures. A second run with the actual prompts captured would provide much stronger evidence.

---

## Appendix A. Provenance, counting rules and limitations

- **Primary record:** `1-embodied-ai-in-a-3d-physics.json` supplied by the operator. **SHA-256:** `029742bce7236ccd29ee91d32553a726e50875def9a5f1cf90eb452c3291ae4a`.
- **Time zone:** all times in this report are UTC, directly from the JSON. Session `created` and `ended` are metadata; `submissions[].created` marks the recorded turn time.
- **Submitted:** `kind == "seat"`; **included:** `outcome == "included"`; **no submission:** `outcome == "no submission"`.
- **Cross-seat reference:** a literal `T<number>` found within submission text after stripping an initial `T###:` self-label, pointing backward to a canonical submission number authored by another seat. This captures explicit citations only, not semantic influence without citations.
- **Length failures:** the five entries whose `outcome` is `excluded: over 512`. Their exact messages remain in the JSON.
- **Jev rejection count:** includes only `excluded by Jev`; 303 such contributions have `new` listed in `below_0.83`. An individual rejection can fail multiple criteria, so per-criterion veto counts are not additive.
- **Repeated response:** literal equality after removing initial self-label `T###:`. Kimi produced a 26-item identical-text series; other paraphrases and near-duplicates were not counted as exact duplicates.
- **Identifier mismatch:** leading self-declared `T###:` differs from canonical submission `number`.
- **Limitations:** no token-by-token generation trace, no preserved per-seat final assembled prompt, no per-seat full input transcript, no raw Jev evaluation input/output, no cost breakdown, no instrumented control group, and no 3D test-run telemetry. Every inference that needs one of these is marked accordingly.

*Prepared from the first-run primary record and operator-supplied context. This report assesses the experiment and its observable mechanisms; it does not change system behavior or prescribe new restrictions.*
