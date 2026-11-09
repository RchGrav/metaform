# Evidence and contradiction register

Editor: Sol. Shared draft for Opus, Astra, Sol and Fable.

Status: pending review by the seats. These findings do not establish owner acceptance.

Source baseline: `24a72b37cf76574f1c9b140aad6e10fec0983daf`, read on 2026-11-04.
No runtime tests were performed for this register.

## Relies on

- P1: preserve source authority and distinguish specified contracts from implemented contracts.
- P2: distinguish layer visibility, `goto`, resolver composition and ticket context.
- The supplied continuation: preserve earlier disagreements through P10.

## Challenges

- Field names alone do not establish an implementation defect. R-3.4 explicitly permits the earlier names during the transition.
- R-6.5 excludes inheritance of the project's layer list. It does not establish that external addresses receive no context.
- A `goto` check cannot establish resolver behavior. These operations have different documented outputs.

## C-1: Specified fields and implemented fields

**Earlier claim:** Fable described the implemented field names as contradicting the specification.

**Evidence:** [R-3.4](../../../TOPOGEE-SPEC.md#3-the-map) says, “The store and the form still use the earlier names until the code changes.”
The passage is at `TOPOGEE-SPEC.md:111`.

`mcp-server/src/commands.ts:39` requires `goal`, `function` and `intent`.
`metaform.schema.json:253` permits `send`, `receive` and `send_receive`.
R-3.6 specifies `inbound`, `outbound` and `two-way`, with status “Not built.”

**Draft resolution:** classify this difference as a documented transition.
The [P1 crosswalk](panel-01-sources-authority.md) distinguishes the two contracts.
Reports must identify which contract an example uses.
The intake concepts retain their authored meanings.
Schemas remain protected by `AGENTS.md`.

**Next decision:** the implementation plan must identify the authorized transition before adopting the specified names.
P1 records the distinction. P10 checks consistency across the final documents.

## C-2: Visibility and context delivery

**Earlier claims:** Sol raised a possible resolver conflict. Opus called the resolver wording older (T79) and now accepts Fable's reading of separate operations (T80).

| Operation | Direct evidence | Supported scope |
|---|---|---|
| Layer list | `TOPOGEE-SPEC.md:391`: “controls which layer names are visible” | R-6.3 inherits that list. |
| External addresses | R-6.5: “They do not inherit the project's list.” | Excludes list inheritance for `upstream` and `downstream`. |
| `goto` | `TOPOGEE-SPEC.md:291`: “record counts, not records” | Describes discovery at the addressed element. |
| Resolver | `TOPOGEE.md:30`: “parent prefix layers” | Describes composition of context from prefixes. |
| Ticket context | `TOPOGEE-SPEC.md:333`: “A ticket selects an agent's context.” | Selects context for the task. |

**R5 correction F1:** `goto` delivers names, skill frontmatter and record counts once per context.
Later arrivals deliver only adjusted information in that context (R-5.30 at `TOPOGEE-SPEC.md:291`).
It counts CEL records, not fields; removing `status` does not reduce the record count (Astra T341).

**P2 resolution:** the passages describe distinct operations. No cited passage expressly removes resolver composition.
The ticket path's relation to resolver composition remains unspecified.

**R5 correction F2:** section 11 lists the context resolver under “Not in this document yet” (`TOPOGEE-SPEC.md:556`).
The resolver contract is not specified there; `TOPOGEE.md:30` still describes prefix composition.
Separately, M1 in the [L-60 report](l60-verification.md#live-map-observations) records the live map's “not built” report.
An absent specification and a reported build state are separate observations (Astra T320; R5 F2 agreement).

**R2 resolution:** P4 selects the resolver for device CEL delivery, under L-10 and L-10a.
Parent planning records compose through the resolver and are masked per System.
Device bindings and enforced limits resolve only at the bound address.
Inheritance creates no binding. A visibility mask never disables enforcement.
This panel recommendation selects the P4 delivery path; it does not specify its contract or establish runtime behavior.
The owner decision on the resolver and its relation to `goto` and tickets remains open under section 11.

**Basis:** `TOPOGEE.md:30`; R-6.4 at `TOPOGEE-SPEC.md:395`; T151, T152 and T189; [P4 report](panel-04-link-cel.md).
The binding and enforcement split is a panel recommendation (`judgment`), not a claim that R-6.4 defines device enforcement.

**Proposed L-60 checks:** use distinct records at a parent and child address.

1. Check inherited layer names through `goto`.
2. Check that `goto` excludes records from other addresses.
3. Check resolver composition, System masking, and local bindings and enforced limits.
4. Check device CEL delivery through the resolver; check ticket delivery separately when claimed.

These are separate acceptance conditions. None has been tested here.
R-5.30 and R-5.31 both carry “Not built” status.

**Recommendation:** retain the agreed split and perform the four runtime checks when their implementation paths exist (`judgment`; Sol owns L-60).
L-10 stays agreed and unverified until those checks pass.
Specification and map checks establish source conformance only.
If a required runtime path is unavailable, record the missing path and keep L-10 unverified.
Reserve “not built” for the cited source or reported build state.
This distinction follows L-60 and P4's separation of agreement from runtime verification.

**R3 verification result:** checks 1 to 4 are untested at HEAD `24a72b3`.
The reviewed Node implementation lacks the required `goto`, resolver composition and device delivery paths.
R-5.30 and R-5.31 remain marked “Not built” at `TOPOGEE-SPEC.md:293` and `:335`.
The live map also records the context resolver as not built.
The [L-60 report](l60-verification.md) records each path, source evidence and missing runtime evidence.
L-10 stays agreed and unverified. This result records a verification gap, not an observed runtime failure.

## C-3: Local inhibition and queues

**Earlier claim:** T55 proposed bypassing every queue.
**Earlier agreement:** T54 separated local inhibition from durable audit recording.

`DECISIONS.md:12` records fair write queues for stores.
The design at `docs/designs/metaform-server-design.md:579` defines writes through effects of final values.
That design labels the data-controller boundary as an agent choice.
Neither source defines device scheduling or a physical response limit.

**Draft resolution:** local inhibition must not wait for storage commits or storage fairness queues.
This requirement does not prove bounded device scheduling.
Opus's two-lane design remains Proposed.
The one-control-tick target remains Proposed.

**Next decision:** P8 must specify device scheduling and saturation tests.
The tests must measure inhibition latency separately from physical motion ending.
P6 must define the relation between inhibition and lease revocation.

## C-4: Shared embodiment contract

**Earlier claim:** physical and virtual embodiments differ only in the device CEL.
**Challenge:** Astra identified the missing compatibility evidence.

`docs/world-ideas.md:18` distinguishes the embodiment from the agent and ties only the embodiment to the game loop.
`docs/world-ideas.md:19` says the owner's control scheme is not recorded.
Neither passage proves identical physical and virtual contracts.

**Draft resolution:** treat common message compatibility as a proposed test.
A passing message test does not establish physical clearance or braking behavior.

**Next decision:** P5 defines the contract and separate physical evidence.
P7 evaluates the common interface against those results.

## C-5: World storage and fixed map requirements

**Earlier question:** does Ladybug replace the map's JSON store or proposed SQLite log?

R-4.1 specifies JSON by default and permits other stores where they fit better.
Section 9 proposes “The JSON store, the SQLite log”.
`docs/world-ideas.md:128` reports Rust blob tests through 16 MB.
Line 129 reports Node binary failures at every tested size.
Line 119 limits the evidence to small databases under Linux on WSL.

**Fixed input:** the owner already decided JSON map storage in `DECISIONS.md:12` and R-4.1.
C-5 does not reopen that decision. The implementation moves from Ladybug to JSON.
The remaining C-5 question concerns world storage; the other stores provide its boundary conditions.

The [original owner brief](review-evidence.md#original-owner-topic-brief) names Rust, LadybugDB and Bevy for the world server.
That scope does not establish a per-world database layout, an interface contract or performed tests.

**R3 panel recommendation:** separate the map store, effect log, ACP conversation log and world store.
The seats ratify L-20, L-21 and L-22. Fair queues on every store are already Decided (`DECISIONS.md:12`).
L-22a stays Proposed because the owner has not accepted that agent suggestion.
These are panel rulings, not evidence of implementation or owner acceptance.

| Data | Storage and writer | Basis |
|---|---|---|
| Map, layers, settings and project registry | Decided: JSON under `~/.metaform`; only the map server writes. | `DECISIONS.md:12`; R-4.1 and R-4.4 at `TOPOGEE-SPEC.md:188`, `:217`. |
| Link CEL | Proposed: a JSON layer file at its address, holding `world` and `instance_id`; only the map server persists it. | R-4.3 at `TOPOGEE-SPEC.md:211`; R5 G1/L-33, T307, T329. |
| Effect log as commit point | Proposed: append and sync the effect before updating files. | R-4.13 at `TOPOGEE-SPEC.md:239`, with Proposed status at `:241`; T360. |
| Medium for the effect log | SQLite is `judgment` under Decided permission to use SQLite where tabular data fits. The owner can accept the role without accepting this medium. | `DECISIONS.md:12`; R-4.1; section 9 at `TOPOGEE-SPEC.md:513`; T359, T360. |
| ACP conversation log | Storage remains open. Recommend SQLite because the records are tabular (`judgment`). | `TOPOGEE-SPEC.md:566`; Opus T251; Astra T243 distinguishes this log from the effect log. |
| World objects | Proposed: Ladybug per world, owned by the world server. A fair write queue is Decided. | Per-world layout is `judgment` under L-20. `DECISIONS.md:12` establishes fair queues, not that layout. |

Sharing the effect log's queue with map persistence remains Proposed under L-29 (`judgment`; R3 panel ruling).
World submissions enter a separate fair-queue lane in the R-4.7 project queue (`judgment`; Opus T251, Sol T256).
The exact lane policy remains open.
L-21 selects the specified `layer` command for world and device CELs. Device commands and telemetry stay on the world server.
After T440, source reads confirmed no dedicated `layer` operation in `mcp-tools.proposed.json` or `mcp-server/src/commands.ts:136`.
R-5.1 lists that command at `TOPOGEE-SPEC.md:251`; its contract and implementation remain separate gaps.
The earlier `update` citation names a proposed edit target. Reconcile that target with L-21 before implementation.
Revision echoes acknowledge application and create no map write (`judgment`; Sol T261).
This rule prevents commit announcements and echoes from producing an endless commit cycle.

### Identity persistence and recovery

The world persists `(address, instance_id)` with its object before submitting the link CEL (`judgment`).
The map server then persists the submission; the identity therefore survives in both stores.
Retries resubmit the same pair without creating another object or identity.
Basis: Astra T258 and T276; Sol T270 and T283; Opus T282; Fable T275 and T284.
L-8 still permits 0..n instances at one address.

Separate queues do not provide an atomic commit across the two stores (Astra T262).
After restart, recovery requires a fresh binding under L-9.
Matching durable records require no map write (R5 G1; Astra T320).
If the CEL lacks the pair, recovery submits the original `instance_id` (Astra T276, T327; Opus T329).
An identity mismatch requires explicit reconciliation before replacement (T321).
The proposed crash tests must cover the interval between persistence steps.

On an identity mismatch, the link stays `unbound`, both records are reported, and reconciliation precedes binding.
Opus T282 and Fable T284 withdraw automatic CEL precedence and accept Sol T274; Astra T285 agrees.
Recovery matches `(world, instance_id)` and checks the address; address-only adoption is ambiguous under L-8 (Astra T285).
Restart, crash, retry and echo checks remain test designs. No seat performed them.

### Resolved R3 status wording

P4 explicitly lists `bound`, `stale` and `unbound` at `panel-04-link-cel.md:21`.
Its restart test retains `stale` until fresh binding at `:58`; despawn produces `unbound` at `:61`.
Opus T282, Sol T283 and Astra T285 instead propose using `stale` only as diagnostic evidence.
Fable T284 retains the P4 distinction: restored object with an old binding is `stale`; missing or mismatched object is `unbound`.

Sol withdraws the diagnostic-only proposal after this source review.
Astra withdraws that reading in T295. The [P7 report](panel-07-storage-interface.md#status-labels) retains P4's three statuses.
Sol accepts that correction, including `unbound` for an existing identity whose address conflicts with the CEL address (`judgment`).
All seats still require fresh binding. No wording permits an obsolete binding to accept commands.

### R5 G1: Proposed runtime status

All four seats support L-33 as Proposed (`judgment`; T307–T348, supplied continuation).
The link runtime derives `status` from the CEL `instance_id`, object presence and the boot token.
Nothing stores `status`; the CEL retains `world` and `instance_id`.

| Runtime status | Meaning |
|---|---|
| `bound` | A binding exists under the current boot token. |
| `stale` | The object carries the CEL `instance_id`, but no binding exists under the current token. |
| `unbound` | No object, an identity mismatch, or an address conflict. |

At start, a matching restored object gives `stale` until rebind; the runtime does not reset every record to `unbound` (T314).
The world lane has two write causes: the CEL lacks the pair, or an identity mismatch was explicitly reconciled (T329).
Both first spawn and world-first recovery submit the original identity; recovery never creates a replacement identity automatically (T276, T327).
Reporting both mismatched records is runtime output, not a map write (T318).
Echoes create no map writes; only `instance_id` submissions remain in the revised P7 echo clause (T308).
The earlier P4 case for persisted `bound` becomes moot (Fable T312).

**Safeguard:** loss events carry `world`, `instance_id` and the boot token; the runtime drops events with an obsolete token (Sol T331).
Events and tokens stay on the world side under L-31 (Fable T339).
After disconnection, retained `bound` is diagnostic only until revalidation against the current token (Astra T334).
The world also validates the boot token when applying an action (Sol T344).
Disconnection reports an unreachable link; it does not establish object loss or add a status (Opus T319; Fable T324).
Whether the runtime needs a separate link-down signal remains open for P5 (T319, T328).

### Application checks and outcome counts

The following rules remain Proposed (`judgment`), with owner acceptance pending for the update contract at `mcp-tools.proposed.json:578`.
The map server checks each precondition when applying the submission; a read before submission cannot close the queue interval (T362, T381, T384).

| Write cause and current CEL pair | Proposed outcome | Basis |
|---|---|---|
| Cause 1: the pair is absent | Persist the submitted original pair. | T329; T384. |
| Cause 1: the identical pair is present | Return success without a commit or refusal. | T387; Astra T404; Sol T405. |
| Cause 1: a different pair is present | Refuse without a commit. The world reports the mismatch and derives `unbound`; it does not adopt the returned pair. | T391; T404. |
| Cause 2: the expected pair remains current | Apply the explicitly reconciled replacement. | Sol T394; Opus T402; Astra T404. |
| Cause 2: the expected pair is no longer current | Refuse without replacing the current pair or committing. | Sol T394; supported as Proposed in T402 and T404. |

Reconciliation names the pair it replaces. This guard prevents a delayed reconciliation from overwriting a newer reconciliation (T394).
Each checked submission increments submissions received. Only a refused submission increments refusals (Astra T404).
Count server outcomes separately from world receipts; a lost response affects receipt counts only (Sol T405).
An identical-pair success stays outside the L-6 refusal budget. These are expected outcomes, not performed results.

R-4.7's queue requirement is Decided at `TOPOGEE-SPEC.md:223`, with its status and source at `:225` (Opus T402).
The acknowledgement-after-commit detail comes from the earlier proposal. Preserve that provenance beside the proposed retry expectations.
R-4.7 supplies no commit-transition observer; the proposed build measure emits one event for every committed write (Opus T383).

**Decision trigger:** a restart with matching durable records produces zero committed map writes and zero announcements emitted by the map server.
The trigger follows T320, T329 and T356; receiver silence cannot establish it (T368, T380).
Count restart, recovery, repair and retry separately, using the submission's cause rather than its label (T369, T371).
A retry follows an unacknowledged earlier submission. With no earlier submission, every write in the matching-restart window counts as a restart write.
Count commits at the commit transition. Without that observer, record the commit count as unknown; announcements cannot substitute (Sol T380).
The [L-60 observer set](l60-verification.md#r5-observers-and-counting) separates submissions, acknowledgements, commits, optional effect-log entries and announcements.
Test logs join `world`, address, the identity pair, `instance_id` and a distinct attempt label (T375, T388, T390).
`instance_id` is unique within one world only (L-7). Correlation records stay in test logs, never in the CEL.

The [R5 checks](l60-verification.md#r5-proposed-link-checks) remain unperformed; panel support establishes no measured benefit.
Stale-ID test 2 no longer depends on the L-6 map-to-world budget; only identity reconciliation crosses R-4.7 (T310).

### Documented storage transitions

`mcp-server/src/store.ts:1` currently stores the map in Ladybug.
R-4.1 explicitly records this lag at `TOPOGEE-SPEC.md:195`; R-4.6 proposes removing Ladybug at `:243`.
`store.ts:28` also keeps layers in one column; R-4.3 specifies separate files at `TOPOGEE-SPEC.md:211`.
These are storage transitions, recorded separately from the ownership conflict in C-8.
No store implementation or layer files were adjusted during this session.

**Measurement boundary:** the cited blob tests do not establish large-world suitability.
Recommend measuring burst fairness, queue delay and revision application latency separately from device response (`judgment`).
P10 should retain the proposed map build order while carrying the unperformed recovery checks (`judgment`).

## C-6: Stale D-9 ground in Alternative C

**Earlier claim:** Alternative C cites an undecided chassis language as a reason against hosting.
The passage is at `docs/designs/metaform-server-design.md:887` and `:888`.

**Evidence:** `DECISIONS.md:124` records the owner's Rust and Bevy decision on 3 November 2026.
The same passage preserves the standalone Node MCP server and leaves module connections open.

**Resolution:** the language ground is stale. This correction does not reverse the hosting rejection.
Alternative C retains its separate-process ground at design `:889` through `:891`.
[P3](panel-03-bevy-ruling.md) records the link ruling under the P1 authority order.

**Recommendation:** retain the P3 link ruling and exclude the stale language ground from its rationale.
This recommendation follows `DECISIONS.md:124` and the surviving Alternative C ground.

## C-7: Bevy requirement and chassis pin

**Earlier claim:** the map's module lifecycle establishes a need for `bevy_app` and the proposed `MinimalPlugins` stack.
Astra T207 challenges that inference. Opus accepted the correction in the supplied continuation.

**Evidence:** `metaform-canonical.json:96` describes module discovery, loading and unloading.
The Chassis element starts at `metaform-canonical.json:268`.
Neither cited passage names Bevy plugins or `bevy_app`.
`DECISIONS.md:124` requires Bevy; it leaves module connections open.

**Resolution:** the map does not establish that bare `bevy_ecs` is insufficient.
The `MinimalPlugins` choice remains `judgment`.
Opus and Fable recommend one workspace `bevy` version, with render features added for the world.
Astra and Sol keep L-28 Proposed pending stack sufficiency and build measurements.
The [P3 report](panel-03-bevy-ruling.md) now records this distinction.

**Measurement scope:** `docs/world-ideas.md:123` reports a 20-second clean build for `bevy_ecs` alone.
That measurement does not establish build time for the other proposed stacks.
Opus T118 reports dependency counts using a different method; those counts do not measure build time.

**Recommendation:** evaluate the proposed shared Bevy version against the chassis requirements before adopting L-28 (`judgment`).
The chassis panel should compare stack sufficiency and clean and incremental build times with one method (`judgment`).
The owner confirms the resulting stack recommendation.

## C-8: Map store ownership in the source header

**Earlier claim:** `mcp-server/src/store.ts:7` and `:8` say the chassis will take ownership of the database.
The header dates from 2 November 2026; the owner settled map-server ownership on 3 November (`DECISIONS.md:12`).

**Evidence:** R-4.4 makes the map server the only writer under the home at `TOPOGEE-SPEC.md:217`.
Its status explicitly replaces chassis ownership at `:221`.
R-2.11 selects integrated data control at start-up (`TOPOGEE-SPEC.md:77`).
`DECISIONS.md:124` retains that integration rule; it does not expressly transfer the map files.

**R3 resolution:** this is a scope conflict, not a timing conflict.
The later ownership decision supersedes the header. Map persistence stays with the map server.
The chassis supplies deep-integration data; the map server persists map data under R-4.4.
Basis: Fable T253, T257 and T260; Opus T259; Astra T262; Sol T270.

This reading preserves P3's process boundary and R-2.11's start-up selection.
The integration parts remain deferred until chassis specification (`TOPOGEE-SPEC.md:79`).

**Recommendation:** adjust the header to retain map-server ownership during the map-store implementation (`judgment`).
This session records the correction without adjusting product source.
Keep the Ladybug and layer-layout transitions under C-5, apart from this ownership correction.

## R5 review response

The [independent review](review-session-20261104-24c67015.md) is advisory, not an owner decision.
R5 accepts F1–F4, G2 and G3; all four seats support G1 as Proposed.
The supplied continuation after T394 records the earlier positions and turn references below.
The owner supplied T402 and T404 directly; Sol's T405 entered the discussion.

| Finding | R5 result | Assigned record |
|---|---|---|
| F1 | Accepted: `goto` delivers names and counts once per context (R-5.30). | C-2; Opus owns P4, Fable owns the ledger. |
| F2 | Accepted with both readings: absent resolver contract and map-reported build state (T320). | C-2 and L-60 report. |
| F3 | Accepted: JSON is Decided; C-5 concerns world storage; per-world layout remains `judgment`. | C-5; Opus owns P7, Fable owns L-20/L-29. |
| F4 | Accepted: the `wants` exclusion applies to the world server; chassis data remains open under R-2.11. | Opus owns P3; Fable owns L-3; C-8 preserves the ownership boundary. |
| G1 | Proposed: runtime-derived `status`, with the P4 enum and two write causes (T307, T314, T321, T329). | C-5 and L-60 report; Opus owns P4/P7, Fable owns L-33. |
| G2 | Accepted: use “world link” (L-2; `TOPOGEE-SPEC.md:558`). | Opus owns P7 and topic 03. |
| G3 | Accepted: criterion 8 measures the build (`docs/countermeasures.md:94`). | Fable owns the ledger; Opus owns P10. |

The [review evidence](review-evidence.md) now supplies saved turns through T296 and the original owner brief.
That snapshot addresses the missing-turn observation for its stated range. It excludes later turns.
Earlier R5 references follow the supplied continuation; this edit did not independently replay those turns.
The later supplied turns resolve the identical-pair counting distinction and support the expected-pair guard as Proposed (T402, T404, T405).
Single ownership of each file remains the session rule. Each writer re-reads the file before editing.
P5, P6, P8 and P9 remain hand-offs under the [R5 draft](topics/05.md), not completed reports.

### P10 check after T422

Sol read `panel-10-synthesis.md` after the chair supplied T417 to T422.
P10 contains all eight requested outputs and distinguishes owner decisions, panel agreement, proposals and verified evidence.
The table records findings against the earlier draft. They are source checks, not new panel rulings.
After T428, Sol re-read P10 and confirmed all three corrections.

| Finding | Evidence | Required correction |
|---|---|---|
| The world scope is already recorded | `review-evidence.md:30` names Rust, LadybugDB and Bevy. P10 at `:56` and roadmap row 8 still require the owner to record it. | Preserve that recorded scope. Keep interface and device details Proposed until accepted; do not repeat the scope question. |
| Announcements cannot establish the commit count | P10's R5-7 row at `:171` infers commits from announcement counts. T380 and P10 criterion 9 require an independent commit observer. | Count commits and emitted announcements independently. Without a commit observer, record the commit count as unknown. |
| A success outcome does not specify response encoding | T404 and T405 distinguish success from refusal. P10 at `:30`, `:155` and `:167` adds a necessary third reply kind and zero acknowledgements. | Preserve success with zero additional commits and refusals. Record reply encoding and acknowledgement counts as unspecified, rather than consequences of T404/T405. |

R-4.7's acknowledgement detail comes from the earlier proposal (`TOPOGEE-SPEC.md:223`, `:225`).
That provenance does not establish a required new reply type (`judgment`).
The owner brief explains the write guards with examples and now names `mcp-tools.proposed.json:578` explicitly.
R5-7 to R5-9 and the observer rules are already saved in [L-60](l60-verification.md#r5-proposed-link-checks).
C-2's closing status now preserves the open owner contract decision and unverified L-10.

**Confirmed after T428:** P10 preserves the recorded world scope, counts commits separately from announcements, and leaves reply encoding unspecified.
Sol supports the corrected synthesis. This confirmation concerns the document, not owner acceptance or runtime verification.

**Final reconciliation after T446:** Sol re-read the saved ledger and index and confirmed the remaining corrections.
The ledger counts commits independently of announcements and qualifies verification as a document check.
Both files preserve the recorded world scope and distinguish owner acceptance from panel agreement.
The index lists P10 and Astra's R5 crosswalk; it no longer lists a missing next-topic file.
Fable withdrew the separate-response proposal and explicitly supported the identical-pair outcome and both guards in kept turn T446.
Reply encoding remains unspecified. All three behaviors remain Proposed and untested; no owner acceptance is implied.
Sol confirms the corrected ledger and index. No Sol document-consistency finding remains open.

## Located source

`docs/world-ideas.md:87` states, “Metaform is not a system for making games.”
The same line says making games is one capability.
This locates the quotation previously reported without a file reference.
The document remains a brainstorm under its line 3 status.

## Decisions Made

- Sol accepts one ledger for later proposals.
- Sol accepts P7 for common interface and storage, and P8 for safeguards.
- Sol supports Opus as synthesis lead and maintains this register.
- This register records source checks separately from proposed runtime checks.
- C-2 records the panel's proposed delivery path. The owner contract decision and L-10 verification remain open.
- C-6 removes a stale ground without reversing P3. C-7 preserves the L-28 evidence gap.
- C-5 records fixed map requirements, proposed world storage, world-first recovery and the corrected R3 status wording.
- R5 preserves F2's separate observations and records G1/L-33 as Proposed, with untested checks.
- R5 records application preconditions, separate server outcomes and receipts, and the proposed commit observer.
- Sol confirms P10's three corrections after T428 and supports the corrected synthesis.
- Sol confirms the corrected ledger and index after T446; Fable's kept turn supplies support for both application guards.
- C-8 records the superseded ownership header separately from documented storage transitions.
- Sol accepts chassis ownership of isolation checks and separate supported map/world version tests (`judgment`; P3).
- Sol supports C-5 in R3 beside L-60 (`judgment`; Fable's proposal).
- Sol supports one R4 device panel for hardware limits, control scheme, motion observations and device scheduling (`judgment`; Fable's proposal).

## Open Questions Handed Forward

- Seats: review these classifications before marking the shared materials Agreed.
- Runtime implementation: perform all four L-60 checks before marking L-10 verified (`judgment`; P4 agreement).
- Owner: decide the proposed absence and expected-pair preconditions before adopting the contract at `mcp-tools.proposed.json:578`.
- Build measurement: provide the commit-transition observer before claiming zero committed writes (`judgment`; T380, T383).
- Link command: reconcile L-21's specified `layer` operation with the proposed `update` target; record the missing contract and dispatcher paths.
- Chassis panel: verify isolation and supported version pairs separately, and measure the recommended L-28 stack (`judgment`; P3).
- P5 and P7: test the proposed physical and virtual contract.
- P6 and P8: specify inhibition, lease fencing and bounded scheduling.
- Agents module: select ACP conversation log storage. Recommend SQLite for its tabular records (`judgment`; Opus T251).
- Chassis panel: name the deep-integration data without transferring map persistence (`judgment`; C-8).
- P9 and P10: retain storage transitions, specify world-lane fairness and schedule the unperformed recovery checks (`judgment`; C-5).
- P10: retain each unresolved claim until an explicit ruling names it.
