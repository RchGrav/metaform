# Carry-forward ledger

**State:** a panel ratification records panel agreement only; it is not owner acceptance (Astra T348; Opus T354). A row leaves Proposed only when the owner decides in `DECISIONS.md` or `docs/`. L-60 and L-61 record P1–P2 conclusions. A row is never dropped. A panel closes it with a decision or hands it forward.

**R2 update (Fable, 2026-11-04):** P3 and P4 ratified or amended L-1 to L-10a and L-28 below. The reports `panel-03-bevy-ruling.md` and `panel-04-link-cel.md` hold the reasoning. A claim without a citation carries `judgment`.

**R3 update (Fable, 2026-11-04):** L-20 to L-22 ratified, L-22a stays Proposed, and new rows L-29 to L-32 record the C-5 ruling, the link write path, the common interface and C-8. The L-7 note records dual persistence. The L-60 checks are untested at HEAD `24a72b3` (`l60-verification.md`). `panel-07-storage-interface.md` (Opus) holds the reasoning once written; rows cite turns until then.

**R5 update (Fable, 2026-11-04):** R5 answered the owner-requested review (`topics/05.md`). F1 to F4, G2 and G3 are accepted and applied to L-3, L-7, L-9, L-10, L-20, L-22, L-29 to L-31 and criterion 8. G1 is Proposed as L-33 (new section after P7). T404, T405 and T427 settled the counting rule. The cause 2 guard (Sol T394) stays Proposed, supported by Opus T402 and Astra T404, T427. No R5 claim is tested. `panel-10-synthesis.md` (Opus) holds the synthesis.

**Recovery note (Opus):** concurrent edits lost this file and `carry-forward-ledger.md`. Opus rebuilt it from both versions. Rows L-10a and L-22a were Fable's merge; the text below is Opus's reconstruction. Fable must confirm or correct both rows. **Fable confirmed both in R2:** L-10a matches `panel-04-link-cel.md`; L-22a stands as written.

## P3: Bevy ruling

| ID | Row | Basis | Agreement |
|---|---|---|---|
| L-1 | Link, not host. The map and the MCP server stay beside Bevy. Addresses link to Bevy entities. Two grounds: (1) an owner decision excludes hosting; (2) the angle A criteria favour the link. The D-9 ground in Alternative C is stale, because `DECISIONS.md:124` now fixes Rust and Bevy. The rejection stands on "a process, not the chassis" and R-2.11. | Ground 1: `DECISIONS.md:124`; R-4.4 (Decided); R-2.11 (`TOPOGEE-SPEC.md:77`); design `:884–890`. Ground 2: T105, T106, T119; `judgment`. T10, T25, T27 | Ratified in R2 by all four seats |
| L-2 | **Amended.** Only the world link crosses the map/world boundary: submit, subscribe, read of committed state. The chassis controller boundary of R-2.11 is a different boundary and stays open. | `TOPOGEE-SPEC.md:77–79`; design `:588–594`; `DECISIONS.md:124`; map `code.framework.plugin`; T55, T115 (Astra), T117 (Sol) | All four |
| L-3 | The map never stores runtime component state. The world server never stores wants. **R5 scope (F4):** the row covers the world server only. Which data moves to the chassis is decided under R-2.11 (`:79`) when the chassis is specified. | T03; scoped by Sol T144 and Astra T145; R-2.11 `:79`; review F4 | Ratified in R2 by all four seats; scoped in R5 by all four |
| L-4 | Review triggers only: (1) a Rust map server, which adjusts R-4.6; (2) link cost over the L-6 budget; (3) same-tick map reads. Trigger 3 stays dormant until a named module needs same-tick reads. The world reads link status through the link runtime, not the map. An owner reversal is not a trigger (see L-4a). | T35, T37, T39; T111, T181 | All four |
| L-4a | Under the P1 authority order, an owner ruling on Alternative C overrides P3 directly. It needs no review cycle. | P1 authority order; `DECISIONS.md:124`; T111 (Opus), T113 (Fable) | All four |
| L-5 | A reversal must meet all four conditions: (1) the map stands alone with no chassis (R-2.11); (2) isolation and recovery tests pass; (3) the reversal has a measured gain over the link; (4) the owner approves. The linked/hosted build comparison is condition 2 evidence, not a P3 gate. The L-6 method measures the sync hop, which is the possible hosting gain under condition 3. The chassis panel owns the isolation verification and the version-pair tests. | T39, T104 (Opus); Fable merge; T119 (Astra); T189 (Sol), T190 (Astra) | All four |

## P4: Link CEL

| ID | Row | Basis |
|---|---|---|
| L-6 | **Provisional target:** 100 ms p95, same host, one address. **Endpoints:** map commit to confirmed application in the world; R-4.10 announces at commit. **Method:** tag each write with its commit revision; the world echoes the tag; one monotonic clock for both endpoints. **Report:** p95, p99, timeouts, missed updates, delivered and expected counts, reconnection recovery, hardware, world load. **Measure apart:** queue delay, binding availability, device response (own limit). **Completeness gate:** every tagged revision gets a confirmation or an explicit failure; a timeout is a failure even after later recovery; steady state passes only with zero missed applications. **Counting:** an L-9 refusal is an explicit failure, not a missed application (T161); refusals count apart from confirmed applications, and expected refusals belong to the stale-ID tests (T172). Exceeding the budget reopens review (L-4 trigger 2). The same method measures the P3 sync hop. **R5 counting (G1, `judgment`):** expected counts list four write categories apart: restart, recovery, repair and retry. The submission's cause sets its category, not its label. A write is a retry only when it follows an unacknowledged earlier submission; a matching restart has none, so its restart count must be zero (T369, T371). Outcomes per retry checked at application: identical pair, one success, zero refusals, zero extra commits; different pair, one refusal, zero commits. Only a different pair is a refusal; the identical-pair success stays outside the refusal budget (Astra T404, T427; Sol T405). Server outcomes count apart from world receipts; a lost response affects receipt counts only (T405). Whether that success is a separate response type under R-4.7 `:223` is Proposed (`judgment`, Fable; Opus withdrew it in T428). | T39; R-4.10; T126, T130, T133, T135, T153, T154, T160, T161, T172; R5: T369, T371, T404, T405, T427, T428. Provisional, `judgment`; all four seats |
| L-7 | Chain: project + address → world + persistent `instance_id` → runtime `Entity`. **Fields (amended in R5, L-33):** `world` (server identity), `instance_id` (persists across restart, unique within one `world`). `status` (`bound`, `stale` or `unbound`) is derived by the link runtime and never stored. **Never held:** the Bevy `Entity` id, component data, wants, the boot token, `status`. At bind time the link resolves address → `instance_id` → `Entity` and refuses stale IDs. The world server rebuilds the index at load. **R3 note (dual persistence, `judgment`):** `instance_id` persists in both the world store and the link CEL. Order: world-first. The world mints `instance_id` (L-7), saves `(address, instance_id)` with the object, then submits `world` and `instance_id`; only the map server persists them under the address (R-4.4 `:217`). At start the world submits only a pair the CEL lacks: a first spawn, or a crash between the two writes (L-33 cause 1). T318 dropped the earlier "resubmit each record as `unbound`". A retry resubmits the same pair and mints no object or identity. Address authority does not prove restored object identity: on a mismatch or a missing object the link stays `unbound`, both records are reported, and reconciliation precedes a fresh binding. L-8 rules out address-only adoption. **Label ruling:** the P4 enum stands (panel-07, Status labels). Astra T295 withdrew the T285 evidence-only reading of `stale`. `stale` = the restored object matches, but the binding predates the current boot token (test 1). `unbound` = no restored object carries the `instance_id`, or the identity exists but its address conflicts with the CEL address (Astra T295, Opus T296). R5 ruled on G1: `status` leaves the CEL and is derived at runtime (L-33, Proposed). | T26, T28, T29; T116 (Fable); Bevy `Entity` generation counter (T28). Ratified: Opus T128, Sol T144, Astra T145, Fable T152. R3 note: Astra T258, T262, T276, T285; Opus T268, T282; Sol T261, T270, T274, T283; Fable T275, T284; Astra T295; Opus T296; R5: T308, T318, L-33; all four seats |
| L-8 | One address has 0..n instances. Each instance has one address. Stale-ID test 3 covers it. | T29. Ratified: Opus T128, Sol T144, Astra T145, Fable T152 |
| L-9 | A command naming an unknown or stale ID is refused, never redirected. **Restart detection:** the world issues a new boot token at every process start; a new token invalidates all earlier bindings; the token lives in the link runtime, outside the CEL. Every restart forces a fresh binding, even when `world`, `instance_id` and `Entity` all match. **R5 (L-33):** the fresh binding is a runtime act; a matching restart creates no map write. The runtime derives `stale` for a matching restored object and `unbound` only for L-33's three conditions (T314, T318). | T26; R5: T314, T318; T162, T170 (Fable), T189 (Sol), T190 (Astra); `judgment`. Ratified: Opus T128, Sol T144, Astra T145, Fable T152 |
| L-10 | **Amended.** The device CEL rides the resolver path. Records inherit and are masked per System. Device bindings and enforced limits stay local (L-10a). `goto` stays a read. It delivers the attached layer names, the skill frontmatter and the memory counts once per context (R-5.30 `:291`; review F1, accepted in R5). Resolver and ticket delivery remain L-60 matters. **Status:** agreed by all four seats; unverified until Sol's R3 L-60 checks pass. Specification and map checks establish source conformance only; while a runtime path is missing, L-10 stays unverified (Sol T227). **R3 result:** all four runtime checks are untested at `24a72b3`; `mcp-server/src/` has no resolver, `goto`, ticket, inherit or negate path (`l60-verification.md`, Sol T244, Fable T242). L-10 stays agreed and unverified. | P2; T80, T82; `TOPOGEE.md:30`; map `code.resolver.context`; R-6.4; T189 (Sol) |
| L-10a | Device bindings and enforced limits resolve only at the bound address, not a parent prefix. Inheritance creates no binding, because only bindings carry `instance_id`. A parent may negate layer visibility for a subtree with `-`. A visibility mask never disables enforcement (L-17). The row does not extend to all device records (Sol, Astra). | R-6.4; T79; T151 (Opus), T152 (Fable). Ratified for bound-address enforcement: Opus T128, Sol T144, Astra T145 |

### P4 stale-ID tests (`judgment`; Opus T127, strengthened T162)

1. **Restart:** `instance_id` persists. The runtime derives `stale` until rebind, then `bound` (L-33; nothing is stored). The test reuses the `Entity` value on purpose. The link refuses any write on a binding made before the restart.
2. **Despawn:** the runtime derives `unbound` once the despawn or index-miss event reaches it. The L-6 budget no longer applies (T310). No budget value is proposed; the owner or P5 sets one after the observer and endpoints are named (Sol T317). A spawn that reuses the index with a new generation must not rebind.
3. **Multiple instances:** the link refuses a second bind of a duplicate `instance_id` in one world. The same `instance_id` in two worlds resolves by `world`.
4. **Prefix isolation:** parent device context cannot replace a local binding or an enforced limit. A negated layer hides the name; enforcement persists (T151, T152).

Test 3 covers L-8. L-9 refusal covers tests 1 and 2. Refusals in these tests are expected and count apart from L-6 applications (T172).

**R3 additions to test 1 (test designs; none performed; no restart test exists at `24a72b3`):**

| Addition | Source | Agreement |
|---|---|---|
| A persisted `bound` counts as stale until a rebind with a fresh boot token | Sol T256; panel-04 `:58` | all four |
| Restart each server alone, then both together | Astra T258 | all four (Sol T270) |
| Crash between the two persistence steps: an incomplete pair never reports `bound`; recovery keeps identity and requires a fresh binding | Astra T262 | all four (Sol T270) |
| Applying revision N with unchanged link state produces one echo and no new revision | Sol T261 | all four |
| An identity mismatch or missing object keeps the link `unbound`, reports both records, and reconciles before binding | Sol T274 | Opus T282, Sol T283, Fable T284, Astra T285 |
| A retry resubmits the same `(address, instance_id)` pair and creates no new object or identity | Astra T276 | Opus T282, Sol T283, Fable T284, Astra T285 |

## P5–P6: Devices and leases

| ID | Row | Basis |
|---|---|---|
| L-11 | `function` stays a one-line fragment. Schemas, clocks and limits go in the device CEL. | R-3.17; T36, T41, T50 |
| L-12 | Each sensor message carries `source: physical\|sim`, frame, clock domain, `age_us`, validity, error bounds, sensing limits. | T21–T23 |
| L-13 | A missing return is not clear space. A shared schema proves message compatibility only. Physical clearance needs separate evidence. | T07, T22, T23 |
| L-14 | Observation age, command expiry and device response limits are separate quantities. Command expiry does not prove that motion has ended. | T31 |
| L-15 | Each device accepts one controller lease at a time. | T05; unopposed, not ratified |
| L-16 | Each command carries lease generation, sequence number and deadline. Revocation invalidates the generation. The device rejects old generations, repeats and expired commands. | T53 |
| L-17 | Authority order: device, then world server, then agent context. The device enforces limits from its local copy. The agent's copy is for planning only. | T51 |
| L-17a | "Lease" means device command rights. "Control" keeps its R-2.11 meaning. | T19 |

## P7: Common interface and storage

Rows L-20 to L-22a and L-29 to L-32 were ruled in R3 turns. `panel-07-storage-interface.md` (Opus) records the reasoning. L-18 and L-19 go to the R4 device panel.

| ID | Row | Basis | Agreement |
|---|---|---|---|
| L-18 | The embodiment is a receiver whose wants name sensor and actuator providers. | world-ideas, Agents; T34, T36, T41 | Proposed; R4 device panel |
| L-19 | Test, not claim: a microDuck and a Bevy body share one map record and differ only in the device CEL. Astra disputes it. | T34, T41, T50; C-4 | Proposed; R4 device panel |
| L-20 | **Ratified.** The map moves to JSON; it is built on Ladybug today (R-4.1 status `:195`, a transition). Ladybug databases are per world, and the world server owns them (`judgment`; review F3 finds no owner source, and world-ideas `:125` tests 200 databases in one process). The Node MCP server owns no world blobs. Verb corrected after review F3; R5 confirms. | `DECISIONS.md:12`; R-4.1 (`:188`); R-4.6 (`:243`); world-ideas Tested; T12, T13 | All four in R3 |
| L-21 | **Ratified.** World and device CELs use the existing `layer` command (R-5.1, `:251`). Device commands and telemetry stay on the world server. No tool is added. | `CLAUDE.md`; T43; tool boundary scoped after T88 | All four in R3 |
| L-22 | **Ratified, extended.** Every store has one writer, concurrent reads, ack after commit and a fair write queue, not only the world store. | `DECISIONS.md:12`; R-4.7 text `:223`, status `:225` (the queue is owner text; ack-after-commit is earlier-proposal detail, T402, Fable verified); T43 | All four in R3 |
| L-22a | Busstone links read as wants, so one intake grammar covers code, machines and robots. Agent suggestion; the owner has not accepted it. | world-ideas agent note; T09; P1 source rule. Fable confirmed | Stays Proposed; owner |
| L-29 | **C-5 ruling, labels split in R5 (F3; Fable verified T359, T366).** JSON files under `~/.metaform`, written only by the map server: Decided (`DECISIONS.md:12`; R-4.1 `:188`, `:195`). Fair write queues on every store, including the world store's queue: Decided (`DECISIONS.md:12`). Permission to use SQLite where tabular data fits: Decided (R-4.1 `:188`). (a) An effect log as the commit point: Proposed, Alternative G, an agent recommendation (R-4.13 `:239`, `:241`). (b) SQLite as the medium of that log: `judgment` of fit under the Decided permission; the fit claim is an append-only tabular log. §9 `:513` is the only passage that joins (a) and (b) (T360). The owner can accept (a) and reject (b). C-5 covers world storage only. Ladybug runs per world under the world server (L-20, `judgment`). The link CEL persists as a JSON layer file at its address (R-4.3 `:211`). Map persistence and the effect log share the R-4.7 project queue; the world's own store uses a separate queue. World submissions enter the R-4.7 queue as their own fair-queue lane, so a burst cannot starve agent writes. The ACP conversation log (`:566`) is a separate log and is not ruled; SQLite is the best fit, because the log is tabular. Separate queues do not make persistence atomic across map and world; world-first plus resubmission at start is the recovery path (L-7 note), untested. | Opus T239, T251; Astra T243, T262; Sol T256; Fable; `DECISIONS.md:12`; R5: T354, T359, T360, T366 | All four in R3; labels split in R5; ACP log and lane details handed forward |
| L-30 | **Link write path.** The world submits `world` and `instance_id`; only the map server persists them under the address. `status` is derived, never submitted (R5, L-33, T308). Map store ownership stays with the map server under R-4.4. R-2.11 reads narrowly: the chassis supplies the deep-integration data, and the map server persists it. | R-4.4 `:217`, `:221`; R-2.11 `:77`; Astra T243; Opus T250, T259; Sol T256, T261; Fable T253, T257 | All four in R3 |
| L-31 | **World link** (renamed in R5, G2; "common interface" risked reusing the unsettled owner term at SPEC `:558`). Map to world: commit announcements (R-4.10 `:227`), each tagged with its revision. World to map: revision echoes, and submissions through the R-4.7 lane. Echo rule (`judgment`): an echo acknowledges application and creates no map write; the world submits a pair only under L-33's two write causes, so announcements and replies cannot form an endless commit cycle. Never crosses: device commands and telemetry (L-21); `Entity` ids and boot tokens (L-7, L-9). The map owns the address. | Opus T240; Sol T261; L-6 method; R5: G2, T308 | All four in R3; renamed in R5 |
| L-32 | **C-8, header conflict.** `store.ts:7-8` (2026-11-02, `71c2268`) says the chassis takes over database ownership later. `DECISIONS.md:12` and R-4.4 `:217`, `:221` (2026-11-03, `1f9c262`) make the map server the only writer under the home. A scope conflict, not a timing conflict; date order resolves it; the header should be adjusted outside this session. The parts list the chassis supplies is deferred to the chassis panel (R-2.11 `:77`, `:79`). **Transitions, recorded apart:** R-4.1 "Built on Ladybug, not yet on JSON" (`:195`), R-4.6 "Ladybug leaves it" (`:243`), and `store.ts:28` keeping every layer in one `layers` column against R-4.3. | Fable T253, T257, T260; Opus T259; Astra T262; Sol T256, T270 | All four in R3; Sol records C-8 |

## R5: G1 ruling (L-33) and review response

R5 Part 1 closed with all four seats in agreement (T307 to T394). F1 to F4, G2 and G3 are accepted and applied above. G1 is Proposed as L-33. T404, T405 and T427 settled the counting rule. The cause 2 guard stays Proposed. Nothing in this section is tested. Each statement carries `judgment` unless it cites a passage.

| ID | Row | Basis | Agreement |
|---|---|---|---|
| L-33 | **Derived status (G1).** The link CEL holds only `world` and `instance_id`. Nothing stores `status`. The link runtime derives it from the CEL `instance_id`, object presence and the boot token. `bound`: a binding exists under the current boot token. `stale`: the object carries the CEL `instance_id`, but no binding exists under this token. `unbound`: no object, an identity mismatch, or an address conflict. **Start rule (T314):** the runtime does not reset everything to `unbound`, because that would erase `stale`. It sets `stale` where the CEL pair matches a restored object and `unbound` only for the three conditions. **Two write causes on the world lane (T329):** (1) the CEL lacks the pair, at a first spawn or in recovery after a world-first crash; the world submits the original `instance_id` (T276, T327). (2) A mismatch was explicitly reconciled; R3 forbids automatic replacement (T321). An echo creates no map write (T308). A matching restart writes nothing (T329); "a restart writes nothing" holds only when both durable records already agree (T327). `goto` counts CEL records, not fields (T341). L-7 crash recovery holds. | T307, T308, T314, T318, T321, T327, T329, T341; review G1; R-4.4 `:217` | Proposed by all four seats; untested; amends panel-07 L61–62 and L-7, L-9, L-30, L-31 above |

### L-33 additions (T348 to T430; all `judgment`)

- **"No map write" (Fable T356, Astra T368):** R-4.10 `:227` announces each commit as it happens. The checks compare counts kept at the map server, with commit events and announcements counted apart (Sol T426). A missing announcement at the receiver does not prove that nothing committed, so a lost announcement must not let a duplicate commit pass.
- **Observer set (T368, T372, T375, T380, T383, T404, T405):**

| Side | Counts |
|---|---|
| Map server | Submissions received; identical-pair successes; refusals; R-4.7 acknowledgements; commit events at the queue's commit transition; R-4.13 effect-log entries, only if the owner accepts R-4.13; R-4.10 announcements emitted |
| World | Submissions sent; acknowledgements received; identical-pair successes received; refusals received; announcements received (a lossy count) |

  - An acknowledgement after commit does not prove that every commit emits one. Commits are counted at the commit transition. Without that observer the commit count is recorded as unknown, and announcements do not substitute for it (Sol T380). R-4.7 exposes no such observer; criterion 9 lists one as a build measure (Opus T383).
- **Precondition at application (Opus T384, T387; Fable T386, T391; Astra T404; Sol T405):** the map server checks the write cause when it applies a submission, as the world checks the boot token. Cause 1 carries the precondition "pair absent". Same pair: success, nothing more committed (T404, T405). Different pair: an L-9-style refusal, nothing committed; the world does not adopt the returned pair, derives `unbound` (identity mismatch) and reports it. Reason: a read before submission cannot cover the reconciliation interval (Astra T381). Opus withdrew the T364 "correct either way".
- **Reply encoding (unspecified):** R-4.7 `:223` acknowledges a write after it commits. T404 and T405 specify counts only; they do not require a separate reply type (Sol T426, T442). Fable withdrew the separate-type proposal after T436 to T439. The reply to an identical retry reports success, so the world sends no further retry (`judgment`). The encoding goes to the owner with the `:578` decision. T336 expects one success without another commit, zero extra commits and zero announcements; the initial write is counted separately (Opus T430).
- **Cause 2 guard (Sol T394, Proposed; supported by Opus T402 and Astra T404, T427):** a reconciliation names the pair it replaces. The map server applies it only while that pair is current.
- **Contract effect:** both preconditions adjust the update semantics at `mcp-tools.proposed.json:578` ("Update supplied fields on one receiving element") and add no tool. They need an owner decision.
- **Log join key (T375, T388, T390):** `world`, address, pair, `instance_id` and a label for each attempt. L-7 makes `instance_id` unique only within one world. Correlation lives in test logs, never in the CEL.
- **R-4.7 citation (Fable verified at `24a72b3`):** text at `TOPOGEE-SPEC.md:223`; status Decided and source at `:225`. The owner's words cover the queue. "Acknowledged only after it commits" is earlier-proposal detail (Opus T402).
- **Superseded:** Opus T357 (read the CEL pair before a retry) fell to the residual race in Fable T362 (the first submission may still be queued) and to the reconciliation interval in Astra T381. The precondition at application (T384) replaced it.

### Boot-token safeguard (P10 output 4; `judgment`, untested)

| Rule | Source |
|---|---|
| A loss event carries `world`, `instance_id` and the boot token. The runtime drops an event whose token is not current. | Sol T331; Fable T339 |
| A `bound` value kept through a disconnection is diagnostic only. It authorizes nothing until the runtime revalidates it. | Astra T334 |
| The world validates the boot token when it applies an action. | Sol T344 |
| A disconnection is not a loss. The runtime keeps the last derived value and reports the link as unreachable: a condition, not a status, and no new enum value. | Opus T319; Fable T324 |
| A silent world must not produce `unbound`, because `unbound` triggers reconciliation. | Sol T317; Opus T319 |
| Write causes are checked when the map server applies them: cause 1 precondition, cause 2 expected pair. | T384, T387, T394 |

### L-33 proposed checks (none performed; each establishes only its own claim)

| Check | Source |
|---|---|
| A restart with matching durable records creates no committed write and no R-4.10 announcement. This is the G1 decision trigger. | T313, T320, T329, T356 |
| Count restart, recovery, repair and retry writes separately. | T313, T327, T369 |
| Object loss is detected and delivered to the link runtime. Endpoints: a world despawn or index-miss event, and the derived `unbound`. | T317, T319, T324 |
| Restart, rebind, then deliver the earlier loss event. The binding stays `bound`; no map write occurs. | T331 |
| Persist the recovered pair, lose the acknowledgement, and retry. The retry succeeds without another commit; the initial write is counted separately. | T336, T404, T405, T430 |
| T336 variant: hold the queue, retry, release the queue, then count commit events and announcements apart. One commit event means the identical update commits nothing beyond the initial write; two mean it commits again. Announcement counts never substitute for commit counts (Sol T426; R5-7). | T362, T364, T426 |
| T336 variant: delay the retry, reconcile the pair, then deliver the retry. The reconciled pair remains. | T381 |
| Reconcile A to B, then deliver a delayed reconciliation that expects A. B remains. | T394 |
| Delay an accepted action, restart the world, then deliver the action. The world rejects the obsolete token. | T344 |
| A crash-recovery check beside the restart and repair measures. | T327 |

Four earlier L-60 checks remain untested at `24a72b3`. L-10 is unverified. Sol's link and section checks cover document structure only.

## P8: Safeguards

| ID | Row | Basis |
|---|---|---|
| L-23 | Local inhibition waits on no storage commit or storage fairness queue. Astra accepts this scope. T55's "A stop is observed, not written" remains disputed. Device scheduling remains open. | T55, T62, T73; C-3; Astra correction after T88 |
| L-24 | Safety and audit are separate. The audit record queues separately. The ACP log records lease grants and revocations. | T05, T54 |
| L-25 | Bounded device scheduling (diagram below). | T70 (Opus) |
| L-26 | Is a safety stop a write under "fair queuing on writes"? Does lease history enter the map? | `DECISIONS.md`; T55. Open; owner |

### L-25 bounded device scheduling

```
            ┌───────────── device ──────────────┐
inhibit ──▶ │ inhibit lane: 1 slot, newest wins  │──┐ preempts
            │ never durable                      │  │
command ──▶ │ command lane: FIFO, depth N        │──┴─▶ actuator, once per control tick
            │ full → refuse; never drop silently │
            └────────────────────────────────────┘
on inhibit: clear the command lane; advance the lease generation (L-16)
limit: an inhibit takes effect within 1 control tick
test: inhibit latency with a full command lane (criterion 6)
```

## P9: Roadmap

| ID | Row | Basis |
|---|---|---|
| L-27 | Keep §9 steps 1–5. Start world work only after step 3 (map server). | `TOPOGEE-SPEC.md` §9; T06, T09 |
| L-28 | **Recommendation (Opus, Fable; `judgment`):** one workspace `bevy` version. The chassis uses `default-features = false` with `MinimalPlugins` (the 78-crate class). The world adds render features on the same version. Reason (`judgment`, corrected after Astra T207): map `code.framework.plugin` (`metaform-canonical.json:96`, `:268`) names the Chassis with a module lifecycle (discover, load, unload) but names neither Bevy plugins nor `bevy_app`. `DECISIONS.md:124` requires Bevy and leaves module connections open. Fable infers that `bevy_app`'s plugin model fits that lifecycle and that bare `bevy_ecs` might not satisfy "uses Bevy". The map does not establish this. The owner confirms. **Astra and Sol keep it Proposed** until stack sufficiency (world-ideas `:104`) and build time are shown. **Counts (Opus T118, `cargo tree -e normal,build`, cargo 1.88, Linux):** `bevy_ecs` 0.20.1 = 70 crates; `bevy --no-default-features` = 78; full `bevy` = 403. World-ideas `:123` uses another method: 67 and 394 crates, with a 20-second clean build for `bevy_ecs` alone. No build time exists for the 78-crate or 403-crate class. Compare counts only within one method. The link CEL stays the only shared type (T06). | T06; `DECISIONS.md:124`; T118, T126, T134; world-ideas `:104`, `:123`. Status: Recommended by Opus and Fable; Proposed for Astra and Sol; owner confirms |

## Ratified in P1 and P2 (session 1)

| ID | Row | Basis |
|---|---|---|
| L-60 | Resolver scope: layer list names inherit (R-6.3); `goto` returns nothing from other addresses' layers (R-5.30); the resolver composites parent prefix layers (`TOPOGEE.md` §2). Each runtime check requires its relevant path. A `goto` check does not establish resolver or ticket delivery. Gate (Sol T227): specification and map checks establish source conformance only; a missing runtime path keeps L-10 unverified. **R3 result:** the four checks (resolver, ticket, `goto`) are untested at `24a72b3`; `commands.ts:136` has no `goto`; the live map marks `code.resolver.context` as not built; R-6.1 to R-6.8 are scheduled after D-7 and D-13 (SPEC `:518`). Node 22 is installed, Node 24 is required, dependencies are not installed. | T79, T80, T82; P2; C-2; `l60-verification.md` (Sol T244) |
| L-61 | C-1 is a documented transition. R-3.4 status: "The store and the form still use the earlier names until the code changes." | `TOPOGEE-SPEC.md` R-3.4, R-3.6; `commands.ts:39`; T71, T81; P1 |

## Draft success criteria (P10)

1. A non-world project performs full intake and reads with the world server absent.
2. World overload or failure does not block reads of committed map state (T48).
3. Map reads and committed writes have separate latency budgets. Tests measure tail latency and fairness under world load (T48).
4. One contract test passes against a Bevy raycast ToF sensor and a real VL53L-class sensor. It proves message compatibility only (T07, T23).
5. The microDuck ends motion within an agreed travel distance after revocation or expiry. Values unknown: the repo holds no microDuck data (T31, T32).
6. Revocation is tested under queue saturation, then delayed commands. Inhibition is tested with storage saturated and the world disconnected. Inhibit time and physical response are recorded apart (T53, T54, L-25).
7. A stale link after restart or despawn resolves to the intended object or returns unavailable. It never reaches a replacement (T26, T29).
8. **Restated in R5 (G3).** The build is measured: orientation tokens of the built system against a raw-source baseline, including intake, refresh and repeat costs, first task apart from later tasks. Use equivalent tasks and models. Record completion and errors. Report whether cumulative cost falls below the baseline, and after how many tasks. No gain is claimed without it. A poor result implicates the build first and does not refute the method (`docs/countermeasures.md:94`; T07, T47).
9. **Proposed in R5 (T383, `judgment`).** The map server emits one commit event for each committed write, acknowledged or not. Without this observer the commit count is unknown (T380), and the L-33 checks cannot close.
10. **Proposed in R5 (P10; R5-1).** A matching restart creates zero restart writes and zero R-4.10 announcements. This is the G1 decision trigger (T329, T356).

## Review challenges (owner-requested review, snapshot 15:28 on 2026-11-04)

`review-session-20261104-24c67015.md` is a reading by a reviewer, not an owner decision. `review-evidence.md` holds the turn record through T296, which answers the review's traceability observation. R5 Part 1 ruled on each item (`topics/05.md`; T307 to T394, closed with all four seats). Fable verified each citation below at HEAD `24a72b3`. "Verified" in this table means the cited passage was checked in the file: a document check, not a runtime check. **World scope:** the original owner brief records the world server as Rust, LadybugDB and Bevy (`review-evidence.md:29`). That scope is owner text; only the interface and device details stay Proposed (Opus T428).

| Item | Challenge | Rows | Citation check (Fable) | Status |
|---|---|---|---|---|
| F1 | `goto` delivers layer names, skill frontmatter and record counts once per context; "does not deliver" is too wide | L-10, L-60, P4 | R-5.30 `:291` says `goto` "returns what is directly linked there" and names "the frontmatter `goto` delivers". Verified document check | Accepted in R5; L-10 amended |
| F2 | The resolver is "not specified", not only "not built" | L-10, L-60, C-2 | SPEC `:556` lists the context resolver under "Not in this document yet". Verified document check | Accepted as amended in R5 (T320): keep both readings, "not specified" (SPEC `:556`) and "not built" (L-60 M1); C-2 and `l60-verification.md` (Sol) |
| F3 | The map store is Decided; C-5 covers world storage only; L-20 "stays" reads "moves to"; "per world" needs a source | L-20, L-29, C-5 | `DECISIONS.md:12`; world-ideas `:125` (200 databases, one process). Verified document check. Verb corrected in L-20 above | Accepted in R5; L-29 labels split; C-5 limited to world storage; "per world" is `judgment` |
| F4 | "Bevy never stores wants" decides chassis data control in advance | L-3 | R-2.11 `:79`: "Which parts move to the chassis is decided when the chassis is specified." Verified document check | Accepted in R5; L-3 scoped |
| G1 | `status` in the CEL makes every restart or despawn a map write; L-6 measures the other direction | L-7, L-29, L-31, test 2 | L-29 world lane and the echo rule limit writes to new link state; no method measures world-to-map. Verified document check | Proposed as L-33 by all four seats; panel-07 L61–62 amended by Opus |
| G2 | "Common interface" might reuse an owner term; use "world link" (L-2) | L-31, topic 03 | SPEC `:558` lists "the common navigation interface" as unsettled. Verified document check | Accepted in R5; L-31 renamed |
| G3 | Success criterion 8 targets the method, not the build | Draft criterion 8 | `docs/countermeasures.md:94`: "A poor result implicates the build first." Verified document check | Accepted in R5; criterion 8 restated |
| Item 6 | World and device rows L-6 to L-26 stay Proposed and outside `TOPOGEE-SPEC.md` | L-6 to L-26 | The world-server scope is already recorded in the owner brief: Rust, LadybugDB and Bevy (`review-evidence.md:29`). Only the interface and device details stay Proposed (Opus T428). Document check | Accepted by all four seats in R5 |

**R4 not held:** the chair counted 4 of 5 topics at T297 with no R4 turns recorded. `topics/04.md` (P5 and P6) goes forward unchanged. P8 and P9 go forward with their open questions (`topics/05.md`).

## Open questions

| Question | Owner or trigger |
|---|---|
| Lane depth N and control tick length | P5 or P8; hardware measurement |
| microDuck stop limits | First measured stop test. Fable proposes one R4 device panel, angle B, which asks the owner for the limits (`judgment`; not yet accepted by other seats) |
| Which observations justify motion? Opus: physical, younger than command TTL. Sol: a separate age limit. | P5. Fable proposes the same R4 device panel (`judgment`; not yet accepted) |
| Map store: §9 "JSON store, SQLite log" against Ladybug in world-ideas | **Ruled in R3** (L-29). The link CEL is a JSON layer file at its address. Owner confirms |
| ACP conversation log store (SPEC `:566`) | Open. Best fit: SQLite, because the log is tabular (Opus T251; R-4.1). P9 or owner |
| Which parts of the integrated data the chassis supplies (R-2.11 `:77`, `:79`) | Chassis panel |
| How layers move from one `layers` column (`store.ts:28`) to separate files (R-4.3) | Transition; map server build (§9 step 2) |
| World fair-queue lane details on R-4.7 | P8 or the map server build; `judgment` |
| `stale`: a `status` value or a report description | **Resolved in R3:** the P4 enum stands (panel-07; Astra T295; Opus T296). Review G1 reopened the location of `status`; R5 moved it to the link runtime (L-33, Proposed) |
| Cross-store persistence is not atomic; world-first plus resubmission at start is the untested recovery path | First restart test (P4 test 1 additions; L-33 proposed checks) |
| Device response limit, measured apart from L-6 | R4 device panel, with the owner's microDuck limits (panel-04; `judgment`) |
| L-6 target | Keep 100 ms p95 until a measured run exists. Adjust only from measurement (panel-04; `judgment`) |
| Ladybug limits for large worlds | First world above tested sizes |
| Owner's control scheme is unrecorded (world-ideas, Agents) | Owner. Fable proposes the same R4 device panel (`judgment`; not yet accepted) |
| C-3 stop-as-write (L-23, L-25) | Fable proposes the device scheduling panel (`judgment`; not yet accepted) |
| Chassis pin and headless stack sufficiency | L-28 recommendation; owner confirms; chassis panel measures build time |
| Owner decision on `mcp-tools.proposed.json:578`: does an identical update commit and does R-4.10 announce it; the cause 1 precondition "pair absent"; the cause 2 expected pair | Owner. Trigger: the T336 result (T357, T364, T384, T394). A write-count question, not a correctness question |
| Commit-transition observer: no R-4.7 observer exposes the commit transition | Map server build (§9 step 3); criterion 9 (T383). Until it exists the commit count is unknown (T380) |
| Link-down signal: a disconnection is a condition, not a status | P5 (T319, T328) |
| Test 2 and other lane budgets | Owner or P5, after the observer and endpoints are named (T310, T317) |
| Chassis scope of L-3 and of the rows that rest on R-2.11 | Open (Astra); chassis panel |
| Device limits and leases (P5, P6); device rows stay Proposed under review item 6 | Deferred with `topics/04.md` |
| P8 and P9 matters | Not reviewed; carried as open items in `panel-10-synthesis.md` |
| Status reconciliation between `ledger.md` and `contradictions.md` | Pending (Astra); the final folder check |
| Reply encoding for an identical-pair success under R-4.7 `:223` | Owner, with the `mcp-tools.proposed.json:578` decision; unspecified (Sol T442) |
