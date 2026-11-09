# R5 crosswalk: scope, evidence and delivery

Author: Astra. Positions for R5, not new panel decisions.

Updated through T405 using the supplied continuation and subsequent seat contributions. The chair ended discussion at T416.
The post-discussion clarification below addresses the chair's T417 questions and Opus's T418 synthesis.
References after T296 rely on those supplied records, without an independent transcript check.
Vetoed turns do not establish panel agreement.

## Relies on

- P1 distinguishes owner decisions, panel proposals and implementation evidence.
- The original owner brief appears in `review-evidence.md`, under “Original owner topic brief”.
- P4 and P7 define link identity and binding states.
- `l60-verification.md` records four untested runtime checks.

## Challenges and corrections

| Claim under review | Astra position | Evidence |
|---|---|---|
| The owner must first record the world server | The owner brief already names Rust, LadybugDB and Bevy for the world server. Detailed contracts remain separate. | `review-evidence.md`, original brief |
| The resolver is “not specified”, instead of “not built” | Preserve both evidence categories. The consolidated specification omits its contract. The live map reports its build state. | `TOPOGEE-SPEC.md:556`; `l60-verification.md`, M1 |
| `goto` does not deliver | Correct this wording. It delivers the address summary once per context and subsequent adjustments. | `TOPOGEE-SPEC.md:291` |
| Ladybug implies one database per world | The owner brief names the technology, not database cardinality. Treat that layout as a panel proposal. | `review-evidence.md`, original brief; `panel-07-storage-interface.md` |
| Ratification establishes owner acceptance | Panel agreement and owner acceptance need separate labels. | P1; `DECISIONS.md`, Source precedence |
| P10 can omit deferred panel outputs | Preserve all eight required outputs. Record unresolved device questions within them. | `review-evidence.md`, original brief, Final synthesis |

The missing contract and implementation are separate gaps. Neither establishes a failed runtime test.
A source citation must retain its scope when the panel adjusts a recommendation.

## R5 terminology and status

G1/L-33 has panel support and remains Proposed (`judgment`, untested).
CEL means Composed Element Layer. The proposed link CEL retains only `world` and `instance_id`.

| Term | Meaning or scope | Source |
|---|---|---|
| World link | Boundary between the map server and world server | G2; L-2; `TOPOGEE-SPEC.md:558` reserves the common navigation interface |
| `status` | Derived value in the link runtime, absent from durable CEL fields | T307; Fable T318 |
| `bound` | Matching object and address, with a binding under the current boot token | P4; T314; T321 |
| `stale` | Matching restored object and address, without a binding under the current boot token | T314; T321 |
| `unbound` | No object, an identity mismatch, or an address conflict | T321 |
| Unreachable | Link condition during disconnection, separate from the three status values | T319; T324 |
| Retained `bound` | Diagnostic value during disconnection; authority requires revalidation against the current token | T334 |
| Record count | Number of CEL records, unaffected by removing the `status` field | T341 |

At start, matching restored objects remain `stale` until fresh binding. A blanket reset to `unbound` would erase that distinction (T314).
Disconnection does not establish object loss (T319, T324).

| Claim | Required qualification | Source |
|---|---|---|
| Restart creates no map revision | Both durable records already agree | T320; T327 |
| Recovery submits the missing CEL pair | Retry the original `instance_id` after a world-first crash | T276; T327; T329 |
| Identity repair writes a replacement | Explicit reconciliation precedes replacement | T321; T329 |
| An echo acknowledges application | The echo creates no map write | T308 |
| Boot-token safeguard | Check the event token and validate the action token when the world applies it | T331; T344 |

These are proposed rules. Restart, recovery, lost-acknowledgement retry and obsolete-token checks remain unperformed.
Sol owns their verification record in `l60-verification.md`.

## Application conditions and outcome terms

These conditions remain Proposed (`judgment`, untested). They require an owner decision on the contract, without adding a tool.
The proposed edit target is `mcp-tools.proposed.json:578`, the `UpdateFields` description. That passage does not specify either condition.
`TOPOGEE-SPEC.md:578` concerns agent accolades. It provides no authority for these write proposals.
The source for the proposals is the discussion: T381, T384, T387, T394, T402, T404 and T405.
P10's later command note preserves an open route question. L-21 names `layer`, which the proposed JSON contract does not define.
The owner has not selected the command that carries these conditions. This crosswalk does not settle that contract question.

### Explanation for the owner

The pair contains `world` and `instance_id`. Together, these identify the world and the object linked to one functional address.
These proposals concern that link record. They do not establish behavior for every repeated write.

| Question | Example | Astra's recommendation and reason |
|---|---|---|
| Should an identical retry succeed? | The map stores pair A, but the reply is lost. The world sends A again. | Return success without another commit. The requested link already exists. |
| What does "pair absent" protect? | A delayed submission for A arrives after a repair stores B. | Check at application. Refuse the delayed submission and preserve B. A prior read cannot protect this interval. |
| What does the repair guard protect? | A repair expects A and proposes B, but another repair has already stored C. | Apply only if A remains current. Otherwise preserve C and report the conflict. |

The pair-absent proposal adds a condition to the existing update operation, checked together with applying the write.
An identical existing pair returns success. A different existing pair produces refusal (T404, T405).
The owner has not accepted these conditions. No runtime check has established them.
T404 and T405 specify outcomes and counts. They do not require a new protocol response type.

| Cause | Condition when the map server applies the submission | Result | Source |
|---|---|---|---|
| Cause 1: missing pair | The CEL pair is absent | Apply the submitted pair, preserving the original `instance_id` during recovery | T329; T384 |
| Cause 1: missing pair | The CEL holds the submitted pair | Return success without a commit | T387; T404; T405 |
| Cause 1: missing pair | The CEL holds a different pair | Refuse without a commit | T387; T391; T404; T405 |
| Cause 2: explicit reconciliation | The expected old pair is still current | Apply the reconciliation | T394; T402; T404 |
| Cause 2: delayed reconciliation | The expected old pair is no longer current | Preserve the current pair | T394 |

Reading before submission does not protect a later application (T381).
A delayed recovery retry must not overwrite a reconciled pair (T381, T384).
The world must not adopt a different pair returned with a refusal. It derives `unbound` for the identity mismatch (T391).

| Cause 1 response | Server successes | Server refusals | Server commits | Source |
|---|---:|---:|---:|---|
| Identical pair | 1 | 0 | 0 | T404; T405 |
| Different pair | 0 | 1 | 0 | T404; T405 |

Both responses count as received submissions. An identical-pair success stays outside the refusal budget (T404, T405).
Server outcomes and world receipts require separate counts. A lost response affects receipts, not the server outcome (T405).
T404 entered the discussion. Sol supported this distinction in T405.
Fable confirmed T405 in T432. The ledger read after T443 records withdrawal of Fable's separate response-type proposal.
Reply encoding remains unspecified. Astra has not rejected a separate type as a possible later proposal (T444).

## Measurement terms

These definitions prevent a missing announcement from concealing a duplicate commit (T368, T380).

| Measure | Observer and limitation | Source |
|---|---|---|
| Submissions received | Map server | T368; T372 |
| Queue acknowledgements | Map server, counted separately from commits | T375; T380 |
| Commits | Queue commit transition; record unknown without that observer | T380; T383 |
| Effect-log entries | Additional evidence only if the owner accepts R-4.13 | T370; T383; R-4.13 |
| Announcements emitted | Map server under R-4.10 | T356; T368 |
| Submissions sent | World | T368; T375 |
| Acknowledgements and announcements received | World; missing receipts do not establish zero commits | T368; T380; T405 |

The proposed build measure requires one commit event per committed write, whether acknowledged or not (T383).
For a matching restart, both committed writes and emitted announcements must be zero (T329, T356, T368).

| Category | Meaning | Source |
|---|---|---|
| Restart | Matching durable records, without an earlier unacknowledged submission | T369; T371 |
| Recovery | Restore the absent CEL pair with the original identity | T327; T329 |
| Repair | Explicitly reconcile an identity mismatch | T321; T329 |
| Retry | Follow an earlier unacknowledged submission | T369; T371 |

The submission's cause determines its category. A retry label cannot hide a restart write (T369, T371).
Test logs correlate `world`, address, pair, `instance_id`, and a distinct attempt label (T375, T388, T390).
The world qualifies `instance_id`, which is unique only within one world. These correlation fields stay outside the CEL (T388, T390).

Sol's verification record owns the proposed checks. The later variants cover these intervals:

- Hold the queue, submit a retry, then release both submissions (T362).
- Delay a recovery retry until after explicit reconciliation (T381).
- Reconcile A to B, then deliver a reconciliation that still expects A (T394).

No runtime result is established by these proposed checks.

## P10 authority labels

| Item | Label | Source |
|---|---|---|
| JSON map files and map-server persistence ownership | Decided | `DECISIONS.md:12` |
| Fair write queues for every store | Decided | `DECISIONS.md:12` |
| SQLite permission where tabular storage fits | Decided | `DECISIONS.md:12`; R-4.1; T359 |
| Effect log as commit point | Proposed, Alternative G | `TOPOGEE-SPEC.md:239`, `:241`; T360 |
| SQLite as the log medium | `judgment` of fit under the Decided permission | `TOPOGEE-SPEC.md:513`; T359; T360 |
| Acknowledgement only after commit | Earlier proposal detail within R-4.7; the queue itself is Decided | `TOPOGEE-SPEC.md:223`, `:225`; T402 |
| §9 build order | Proposed | `TOPOGEE-SPEC.md:508`; T348 |
| G1/L-33 runtime status | Panel-supported proposal, untested | T307–T348 |
| Application conditions | Proposed, awaiting owner decision | T384; T394; T402; T404 |
| Commit-transition observer | Proposed build measure, without a verified implementation | T380; T383 |
| Resolver contract | Absent from the consolidated specification | `TOPOGEE-SPEC.md:556` |
| Resolver implementation | Reported as not built by the live map | `l60-verification.md`, M1 |

Placement under “Act now” does not establish owner acceptance (T348).
Panel agreement, owner decisions, proposals and verified behavior require separate labels (P1; T313).
The owner can accept the effect-log role and reject SQLite as its medium (T360).

## Most valuable results

- Separate durable identity from binding authority, preserving `stale` across restart without unnecessary writes (G1; T314, T329).
- Check conditions at application, so delayed submissions cannot overwrite a reconciled pair (T381, T384, T394).
- Observe commits independently from receipts, so lost responses cannot conceal duplicate writes (T368, T380, T405).
- Preserve source scope, so panel agreement never substitutes for owner acceptance or runtime evidence (F1–F4; T348, T354, T402).

## Reconciliation observations

These observations concern files read after T443. Earlier review requests are retained below with their resolution.
They are not panel rulings from the vetoed T363.
File owners retain responsibility for their corrections.

- P4 now withdraws its claim that delivery needs no owner ruling. Its section heading still says "closed for P4".
- `README.md` now separates panel agreement from owner acceptance and indexes P10 and this crosswalk.
- Sol corrected C-2's closing status. It now preserves the pending owner contract decision and L-10 verification.
- Sol saved the three later variants as R5-7, R5-8 and R5-9 in `l60-verification.md`.

Basis: P4, “Device CEL delivery under C-2”; README, “Rules for every file”; contradictions, “Decisions Made”; R5 F2 and P10 agreement.

### P10 review after T418

P10 includes the owner explanation and all eight outputs. The table records findings from the first review, with the resolution below.
These findings concern documents, not runtime behavior or panel agreement.
The `bmad-review` checks covered source authority, behavioral edge cases, and structure. Overlapping findings are identified below.

| Lens | Location in P10 | Finding | Required adjustment and evidence |
|---|---|---|---|
| Authority | Output 1 opening; roadmap step 8 | The owner must record the world server again | Preserve the existing brief's Rust, LadybugDB and Bevy scope. Keep detailed contracts Proposed. Source: `review-evidence.md:30`. |
| Authority | Owner question 1; safeguards after the sequence diagram | A separate response type appears necessary | Label it as an additional proposal. T404/T405 establish success without another commit, without requiring a protocol type. |
| Authority | Foundational row 6; Decisions Made | "L-6 to L-33" receives a blanket Proposed label | Preserve Decided map storage and fair queues. Limit Proposed to world and device contract details. Source: `DECISIONS.md:12`. |
| Authority | R5-3 | Zero commits lacks a measurement interval | Specify zero additional commits during retry application. The setup already committed the pair. Source: `l60-verification.md:92`. |
| Authority | Queue-hold check | Announcement counts establish commit counts | Observe commits independently. Report unknown without that observer. Sources: T380, T383. |
| Authority | Proposed-check introduction | Three variants remain described as unrecorded | Refer to Sol's saved R5-7, R5-8 and R5-9 checks. |
| Authority | Owner question 2 | "Today, update sets" implies verified implementation | Describe the proposed update contract. Its description alone establishes no runtime behavior. Source: `mcp-tools.proposed.json:578`. |
| Behavioral | Owner question 1; R5-3 | A response type and zero acknowledgements become test requirements | Preserve the success outcome. Leave protocol response type and acknowledgement counting unresolved. Overlaps authority finding. |
| Behavioral | R5-3 | Counting initial write and retry together contradicts zero commits | Name the retry interval and count the initial write separately. Overlaps authority finding. |
| Behavioral | Queue-hold check | A missing announcement could conceal a duplicate commit | Count commits at the commit transition. Overlaps authority finding. |
| Structure | Owner question 1 | The qualification appears after the apparent requirement | Place the unresolved response-type qualification beside the question. |
| Structure | Foundational rows 4 and 5 | "Owner" resembles the settled Owner decision category | Use "owner decision pending" for the blocked rows. |

### P10 confirmation after T426

Astra checked the saved P10 again after T426. Opus resolved the substantive findings above.

- Output 1 and roadmap step 8 preserve the world scope already recorded in the owner brief.
- Output 1 preserves Decided map storage and fair queues within rows containing Proposed contract details.
- Blocked rows 4 and 5 now say "Owner decision pending".
- Owner question 2 identifies the proposed contract as an edit target, without claiming built behavior.
- Owner question 1 and output 5 leave response encoding and acknowledgement counting unspecified.
- R5-3 counts success and zero additional commits. R5-7 counts commits independently from announcements.
- The check table references Sol's saved R5-1 through R5-9, all untested.

Astra accepts P10 as the panel synthesis with its proposals and open questions retained. This supplies no owner acceptance or runtime verification.
The phrase "no-commit response" in output 4 names the outcome only, under P10's explicit withdrawal of a required third response type.

### Folder confirmation after T443

Astra confirmed Fable's saved L-33 and T405 counts. The ledger now leaves reply encoding unspecified.
The ledger no longer uses T400 or T411 as accepted agreement. P10 explicitly identifies those turns as vetoed.
README indexes P10 and this crosswalk, removes the next-topic file entry, and separates panel agreement from owner acceptance.

| Writer | File and location | Confirmed correction | Basis |
|---|---|---|---|
| Fable | `ledger.md`, queue-hold check | Commits and announcements count independently. | T380, T383; corrected P10 R5-7 |
| Fable | `ledger.md`, review item 6; `README.md`, final reason for R5 | The world scope is already recorded. Only detailed contracts await acceptance. | `review-evidence.md:30`; corrected P10 output 1 |
| Fable | `ledger.md`, opening State rule | Panel agreement and owner acceptance remain separate. | P1; T348, T354 |
| Fable | `ledger.md`, G1 review row | "Verified document check" supplies no runtime proof. | T433; P10 evidence boundary |

Line check: `review-evidence.md:29` is the Context heading. Line 30 states Rust, LadybugDB and Bevy for the world server.
References in this crosswalk retain line 30, checked against the saved file after T443.

Astra confirms the shared materials as discussion outputs, including the recorded proposals and open decisions.
The corrections close Astra's document findings. They establish no runtime results or owner acceptance.

## Decisions Made

- Astra accepts F1, F3, F4, G2 and G3. F2 retains the separate contract and implementation gaps.
- Astra supports G1 as Proposed, retaining the P4 meanings as runtime state.
- Astra supports the T394 expected-pair guard and the T405 outcome counts, both Proposed and untested.
- Astra accepts corrected P10 as the panel synthesis, with owner decisions and untested proposals kept separate.
- Astra confirms the shared materials after checking Fable's final corrections and Sol's saved evidence boundaries.
- Opus remains synthesis lead. Fable owns the ledger and index; Sol owns contradictions and verification.
- This update adjusts only Astra's R5 crosswalk. It establishes no implementation or runtime verification.

## Open Questions Handed Forward

- P10 carries unreviewed P5, P6, P8 and P9 matters, including device limits, observation requirements and leases.
- P5 retains the link-down signal question and measurement budgets. No new budget is proposed here.
- Chassis data scope remains open under R-2.11.
- The owner decides the application conditions, command route and identical-update contract. T336's expected result remains Proposed (T402; P10 command note).
- The commit-transition observer requires implementation before commit counts can be verified (T380, T383).
- Fable confirmed T405. Astra confirmed the four document corrections in the folder-check table.
- Astra's writing and document checks are complete. No next topic follows R5.

