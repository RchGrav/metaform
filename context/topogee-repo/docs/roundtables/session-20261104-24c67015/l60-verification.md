# L-60: Resolver and delivery verification

Author: Sol. R3 evidence with R5 corrections and proposed checks. Updated on 2026-11-04.

**Result:** all four earlier runtime checks and all added R5 link checks are **untested**.
L-10 remains agreed and unverified.
Source review located the specified contracts and missing implementation paths. It did not verify runtime behavior.

R5 edits record panel proposals, not a new implementation review or runtime test.

## Relies on

- P1: distinguish specified contracts, implementation evidence and owner acceptance.
- P2 and L-60: layer visibility, `goto`, resolver composition and ticket delivery require separate evidence.
- P3: link addresses to world entities while preserving the standalone map server.
- P4: deliver device CEL context through the resolver. Keep bindings and enforced limits local.
- Sol T227 and Astra T229: source checks cannot establish runtime verification.

## Challenges

No earlier panel conclusion is challenged.
The available implementation cannot establish the four runtime acceptance conditions below.
This is a verification gap, not an observed runtime failure.

## Evidence boundary

- HEAD: `24a72b37cf76574f1c9b140aad6e10fec0983daf`, branch `intake-3.1`.
- Tracked working and staged differences: none when checked.
- Untracked paths: `.claude/autoharness/`, `mcp-server/.claude/` and this session folder.
- Reviewed implementation scope: `mcp-server/src/`, `mcp-server/test/metaform.test.ts` and `mcp-tools.proposed.json`.
- The codebase graph lists no Topogee index. Its coverage check reports this project as unindexed.
- Direct source reads and text searches supplied the implementation evidence.

The connected Metaform server supplies the live functional map.
Reading that map does not exercise the rebuilt Node server's `goto`, resolver or ticket paths.

## Live map observations

The following read-only calls used the advertised `metaform_catalog` gateway with `tool="map_where"`.
Each call used `contents=true`; M1 also used `full=true`.

| Record | Address | Observed evidence |
|---|---|---|
| M1 | `code.resolver.context` | Its `build-state` layer records “not built”. Its relationships separately describe `goto` summaries and prefix composition. |
| M2 | `data.layer.knowledge` | Its relationships supply selections and negations to the resolver. Its `build-state` layer records registered layers as not built. |
| M3 | `code.interpreter.command` | Its `build-state` layer records “partly built” and identifies `goto`, `search` and `layer` as not built. |

M1's build-state item is `d51451db2e174c78a6dabb16efa40dcc`.
These observations locate intended functionality and reported build state. Current source supplies the implementation check.

## R5 source corrections

**F1:** `goto` delivers layer names, skill frontmatter and record counts once per context (`TOPOGEE-SPEC.md:291`, R-5.30).
Later arrivals deliver only adjusted information in that context.
`goto` counts CEL records, not fields; deriving `status` does not reduce the record count (Astra T341).
These are specified behaviors; the four runtime checks below remain untested.

**F2:** section 11 lists the context resolver under “Not in this document yet” (`TOPOGEE-SPEC.md:556`).
The resolver contract is not specified there; `TOPOGEE.md:30` describes prefix composition.
M1 separately reports the live map's “not built” state.
Neither observation substitutes for the other (Astra T320; all-seat R5 F2 agreement).

Earlier R5 references follow the supplied continuation after T394, not the saved transcript through T296.
The owner supplied T402 and T404 directly; Sol's T405 entered the discussion.
This edit did not independently replay the earlier R5 turns.

## Four runtime checks

Use distinct parent and child records when the required paths become available.
The fixtures below are acceptance conditions, not performed tests.

| Check | Path | Required observation | Runtime result | Evidence and reason |
|---|---|---|---|---|
| 1 | `goto` | The child exposes inherited layer names. A negated layer name disappears below its prefix. | **untested** | R-6.3 and R-6.4: `TOPOGEE-SPEC.md:393`, `:395`. The dispatcher has no `goto` branch: `mcp-server/src/commands.ts:136`. M1 and M3 report it unbuilt. |
| 2 | `goto` | The child summary excludes records from other addresses' layers. | **untested** | R-5.30: `TOPOGEE-SPEC.md:291`, with “Not built” at `:293`. The existing addressed read builds a subtree: `mcp-server/src/commands.ts:125`. It cannot substitute for `goto`. |
| 3 | Resolver | Selected parent planning records compose with child context. Bindings and enforced limits stay local. Visibility masking preserves enforcement. | **untested** | Prefix composition: `TOPOGEE.md:30`. Device scope: P4, L-10 and L-10a. No resolver composition or device enforcement path was found in the reviewed implementation scope. M1 reports the resolver unbuilt. |
| 4 | Resolver delivery; ticket delivery separately when claimed | The intended System receives selected device context through the resolver. Any claimed ticket delivery has its own evidence. | **untested** | P4 selects resolver delivery. R-5.31 specifies ticket context at `TOPOGEE-SPEC.md:333`, marked “Not built” at `:335`. No device delivery or ticket selection path was found in the reviewed implementation scope. |

No fixture request exercised any of these runtime paths.
No runtime pass or failure is claimed for an unavailable path.

## R5 proposed link checks

All checks below are Proposed (`judgment`) and **untested**. Each check establishes only its stated claim if performed successfully.
They supplement the four L-60 checks; they do not verify resolver or ticket delivery.
L-33 derives `status` at runtime; the CEL retains only `world` and `instance_id`.

| Check | Setup and stimulus | Required observation | Basis |
|---|---|---|---|
| R5-1: matching restart | Start with matching durable world and CEL records; restart and rebind. | Before rebind, derive `stale`; after rebind, derive `bound`. Observe zero committed map writes and zero announcements emitted. | T314; Astra T320; Opus T329; T356; G1/L-33 decision trigger. |
| R5-2: obsolete loss event | Restart, rebind, then deliver a loss event bearing the earlier boot token. | Drop the event; retain `bound`; create no map write. | Sol T331; Fable T339. |
| R5-3: lost acknowledgement | Persist a recovered CEL pair, lose the acknowledgement, and retry the original `instance_id`. | At retry application, return success for the identical pair, with zero refusals and zero additional commits or emitted announcements. | Sol T336; T387; Astra T404; Sol T405. |
| R5-4: delayed action | Accept an action, delay delivery, restart the world, then deliver the action with its earlier token. | The world rejects the obsolete token when applying the action; the action has no effect. | Sol T344. |
| R5-5: object-loss delivery | Despawn an object or produce an index miss; deliver the world event to the link runtime. | The runtime derives `unbound`. Measure from the world event to the runtime result. | Sol T317; Opus T319; Fable T324. |
| R5-6: world-first crash | Persist the world object; crash before CEL persistence; recover using the stored identity. | Persist the missing pair with the original `instance_id`; create no replacement object or identity. | L-7; Astra T276, T327; Opus T329. |
| R5-7: queued retry | Hold the project queue. Submit the recovered pair. Retry before acknowledgement. Release the queue. | Across both submissions, observe one commit and one emitted announcement. Record duplicate commits separately from lost announcements. | Fable T362; T364; T368; T380. |
| R5-8: retry after reconciliation | Delay a cause 1 retry. Reconcile pair A to B. Deliver the retry carrying A. | Refuse the retry with no commit. Retain B. The world reports the mismatch and derives `unbound`. | Astra T381; T384; T387; T391; T404. |
| R5-9: delayed reconciliation | Reconcile A to B. Deliver a delayed cause 2 submission that expects A. | Refuse the delayed submission with no commit. Retain B. | Sol T394; Opus T402; Astra T404. |

R5-3 and R5-7 to R5-9 depend on proposed preconditions checked at application.
The owner must decide those preconditions before the update contract at `mcp-tools.proposed.json:578` adopts them (T384, T394, T402).
The identical-update commit question remains open; these expected outcomes are proposals, not verified behavior.
R5-7 records actual commit and announcement counts independently; an announcement count alone cannot prove the commit count.

Count restart, recovery, repair and retry separately (Sol T313; Astra T327; T369, T371).
R5-1's no-write claim requires matching durable records; it does not apply to a missing or reconciled pair.
Identity mismatch and address conflict require explicit reconciliation before replacement (T321).
Reporting both mismatched records is runtime output, not a map write (T318).

For R5-5, the link runtime is the observer of delivery; only the world observes object presence (L-7).
Disconnection alone must not produce `unbound`; report an unreachable link without adding an enum value (T319, T324).
After disconnection, retained `bound` authorizes nothing until revalidation against the current token (Astra T334).
Whether the runtime needs a separate link-down signal remains open for P5 (T319, T328).

No loss-delivery budget is proposed; the owner or P5 sets it after the observer and endpoints are named (Sol T317).
Stale-ID test 2 does not depend on L-6's map-to-world budget; only identity reconciliation still crosses R-4.7 (T310).
The proposed checks establish no latency, compatibility, recovery or write-count result until performed.

## R5 observers and counting

This observer set remains Proposed (`judgment`); no observer was built or exercised here.

| Observer | Required counts | Basis |
|---|---|---|
| Map server | Submissions received; success and refusal outcomes; R-4.7 acknowledgements; commit events; R-4.10 announcements emitted | T368, T372, T375, T380; T404, T405. |
| Accepted effect log, if any | R-4.13 entries, only if the owner accepts that proposed commit mechanism | T370; R-4.13 at `TOPOGEE-SPEC.md:239`, `:241`. |
| World | Submissions sent; responses and acknowledgements received; announcements received | T368, T372; T405. |

Count commits at the queue's commit transition, before acknowledgement delivery (Sol T380).
R-4.7 does not expose that observer. The proposed build measure emits one event per committed write, acknowledged or not (Opus T383).
Without that observer, record the commit count as unknown. Neither acknowledgements nor announcements substitute for commit events.
An acknowledgement after commit does not establish that every commit produces an acknowledgement (T380).
R-4.7 appears at `TOPOGEE-SPEC.md:223`; its Decided status appears at `:225` (Opus T402).
The status attributes the acknowledgement detail to an earlier proposal; the retry expectation retains that Proposed basis.

Count announcements emitted at the map server, separately from announcements received at the world (R-4.10; T356, T368).
Receipt counts can lose events. A missing receipt cannot establish zero commits or excuse a duplicate commit.
For the matching restart, both committed writes and emitted announcements must equal zero (T356, T380).

### Classification and correlation

- Assign restart, recovery, repair and retry from the submission's cause, independently of its label (T369, T371).
- A retry follows an unacknowledged earlier submission. A matching restart with no earlier submission has no retry write.
- In that restart window, count every write as a restart write; the expected count is zero.
- Log `world`, address, the identity pair, `instance_id` and a distinct attempt label (T375, T388, T390).
- Link each retry to its earlier unacknowledged attempt (T390). Keep correlation in test logs, outside the CEL.

L-7 makes `instance_id` unique within a world only. A test must retain `world` when correlating identities.
These log requirements do not add persistent link fields.

### Proposed L-6 outcomes

| CEL state when cause 1 applies | Submissions received | Success outcomes | Refusals | Commits |
|---|---|---|---|---|
| Identical pair already present | 1 | 1 | 0 | 0 |
| Different pair already present | 1 | 0 | 1 | 0 |

The counting distinction follows Astra T404 and Sol T405. It resolves T387 against T391's earlier pair-present refusal wording.
Count server outcomes separately from world receipts. Losing a response affects receipt counts only.
The identical-pair case stays outside the L-6 refusal budget.
Reply encoding and acknowledgement counts remain unspecified (Astra T427; Opus T428).
Fable explicitly confirms the identical-pair outcome and both guards, and withdraws the separate-type proposal, in kept turn T446.
For a different pair, the world reports the mismatch and derives `unbound`; it does not adopt the returned pair (T391).
For cause 2, compare the named expected pair when applying reconciliation. A different current pair produces refusal without commit (T394, T404).
These rules remain Proposed and untested; panel agreement supplies no owner acceptance.

## Implementation observations

1. `mcp-tools.proposed.json:10` declares branches for `add`, `update`, `delete`, `orphaned` and addressed reads.
2. `mcp-server/src/commands.ts:136` routes those operations. It routes other accepted keys to addressed reads.
3. `mcp-server/src/commands.ts:125` reads the address and its descendants. That behavior is separate from R-5.30.
4. `mcp-server/src/server.ts:14` advertises the contract tool and passes calls to `apply` at `:20`.
5. `mcp-server/test/metaform.test.ts:114` checks subtree reads. It supplies no L-60 runtime evidence.

The inspected source matches the limited command surface described by the current implementation.
It does not implement the complete L-60 contract.

### Dedicated layer command

After Opus T440, source reads confirmed no dedicated `layer` operation in the proposed input contract or dispatcher.
R-5.1 lists `layer` at `TOPOGEE-SPEC.md:251`; L-21 selects it for world and device CELs.
The current branches remain `add`, `update`, `delete`, `orphaned` and addressed reads (`mcp-tools.proposed.json:10`; `mcp-server/src/commands.ts:136`).
Existing add and update branches accept native layer arrays. That capability is separate from a dedicated `layer` command.
The proposed application guards must name their command before implementation.
The `update` description at `mcp-tools.proposed.json:578` remains an edit target only.
This is a contract and implementation observation, not a performed runtime check. No schema or source was adjusted.

## Verification environment

The available `node --version` returned `v22.18.0`.
`mcp-server/package.json:8` requires Node 24 or newer.
Neither the repository root nor `mcp-server/` has a `node_modules` directory.
The existing Node suite was not attempted in this environment.
An environment repair would not supply the missing runtime paths.

No product code, schemas, reference files or installed dependencies were adjusted.
This report records evidence from reads, not runtime acceptance.

## Decisions Made

- Record checks 1 to 4 as untested, with the missing path identified.
- Keep L-10 agreed and unverified under the accepted R3 gate.
- Preserve the distinction between the live map and the rebuilt implementation.
- Carry the verification gap in C-2 of `contradictions.md`.
- Preserve the absent resolver contract separately from M1's reported build state (R5 F2).
- Record R5 link checks as untested; retain G1/L-33 as Proposed.
- Record queued retries, reconciliation races and their proposed application checks as separate acceptance conditions.
- Separate server outcomes, commits, acknowledgements, emitted announcements and world receipts before interpreting counts.

## Open Questions Handed Forward

| Item | Best-fit recommendation | Basis |
|---|---|---|
| L-10 verification | Keep its current status until all four runtime checks pass. | Sol T227, Astra T229; P4 and L-60. |
| Required runtime paths | Add fixtures to the rebuilt paths when those paths exist. Record passed, failed or untested outcomes separately. | `judgment`; the four acceptance conditions above. |
| Ticket delivery | Check it separately when claimed. Do not infer ticket behavior from `goto` or resolver results. | L-60; R-5.31 at `TOPOGEE-SPEC.md:333`. |
| Link persistence | Retain persistent `world` and `instance_id`; derive `status` at runtime as Proposed. | G1/L-33; R5-1 to R5-9. |
| Update contract | The owner decides absence and expected-pair preconditions before adoption. | `mcp-tools.proposed.json:578`; T384, T394, T402, T404. |
| Link command | Reconcile L-21's specified `layer` operation with the proposed `update` target before implementation. | R-5.1 at `TOPOGEE-SPEC.md:251`; `mcp-tools.proposed.json:10`; `mcp-server/src/commands.ts:136`; T440. |
| Identical-update commit | Measure queued retries after the owner decides the proposed contract. | R5-3 and R5-7; T336, T362, T364. |
| Commit observer | Build a commit-transition observer before reporting a verified commit count. Until then, record the count as unknown. | T380, T383. |
| Link-down signal and budget | P5 should decide the signal and loss-delivery budget before performance acceptance. | T317, T319, T328; R5-5. |
