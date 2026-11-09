# Round 2 prioritized findings

Reviewers: PricklyHaven (PH), SupremeChange (SC). IDs below are canonical; parenthetical SC/PH numbers identify the original notes. Paths are relative to `/home/rich/roundtable`. Order: security, hangs, broken primary features, state/accounting errors, lesser fidelity defects. PH approved F01–F18 and their ordering at R2-3/R2-4. F19 was added in the final cross-read and is SC-only; it has not been checked by PH. Other individual agreement and verification limits are explicit below. Review finalized when the table entered its end-rating round.

Authority: owner quotations and decisions in TRACEABILITY L/M/N, then README, then ACP design. Builder status claims are not proof. Implementation files remain unchanged.

## F01 — P1 — Configured chair credential reaches participants

**Finder:** SC (SC9). **Agrees:** PH + SC, confirmed R1-12. **Evidence:** source trace, no live exploit.

**Location:** `crates/roundtable-web/src/app.rs:102`; `crates/roundtable/src/config.rs:27`; `crates/roundtable/src/engine.rs:802-806`.

**Failure:** With the supported ROUNDTABLE_TOKEN override, harnesses inherit the chair token because only two provider keys are scrubbed. A participant can read its environment, authenticate to chair APIs and control other tables or launch commands. The default token generated only in memory is unaffected by this path.

**Fix:** Remove chair credentials from inherited and explicit harness environments and model-executed subprocesses. Add a fake-harness environment test. This repairs an existing boundary without deciding the owner's broader security-hardening question.

## F02 — P1 — Dangling symlinks bypass both filesystem guards

**Finders:** SC + PH (SC8/PH12). **Agrees:** PH + SC. **Evidence:** adapter write and actual Rust policy reproduced.

**Location:** `adapters/openrouter-acp/src/tools.ts:68-77,332-334`; `crates/acp-host/src/permission.rs:66-86`.

**Failure:** root/link points to a missing outside file. realpath/canonicalize returns ENOENT; both guards resolve only the parent and reconstruct an apparently in-root leaf. ScopePolicy allows it; write_file follows the link and creates the outside file. No race is needed. Independent harness sandboxes may still block a write; this finding does not claim to bypass those.

**Fix:** Distinguish nonexistent ordinary leaves from dangling symlinks using lstat/readlink and safely resolve targets. For race-resistant operations use directory-descriptor-relative beneath/no-escape facilities. Fix both sites; test dangling and existing-target links. Proofs: `dangling-symlink.mjs`, `scope-dangling.rs` here.

## F03 — P1 — Busy seat failure strands the end-rating round

**Finder:** PH (PH1). **Agrees:** PH + SC. **Evidence:** independently traced, not runtime-reproduced.

**Location:** `crates/roundtable/src/engine.rs:609-610,625-638,655-667`; `crates/roundtable/src/turn.rs:303-315`.

**Failure:** End includes a Working/Reviewing/Floor/Proposing seat in pending raters. Its prompt then fails or its process exits. Only successful completion schedules the deferred rating, and only Rating failures remove the obligation. The pending entry survives indefinitely while step refuses normal progress; a second End is needed.

**Fix:** Resolve rating obligations on every terminal path: ask a surviving idle seat, or remove a gone seat and check completion. Test working-seat prompt failure and crash after End.

## F04 — P1 — Cancellation misses descendants after shell exit

**Finder:** SC (SC2). **Agrees:** PH + SC on code review (PH R2-4); PH did not reproduce it. **Evidence:** SC locally reproduced against existing adapter build.

**Location:** `adapters/openrouter-acp/src/tools.ts:197-200`.

**Failure:** A command such as `sleep 30.123456789 & exit 0` leaves a descendant holding output pipes after the shell exits. Abort refuses to signal the process group because the leader has an exitCode. The command remains pending until its descendant exits; a long-lived child can stall indefinitely. Its detached group is outside the adapter's own process group.

**Fix:** Track process-group lifetime independently of leader exit; signal the command group on abort until its pipes/processes are done, treating ESRCH as already stopped. Add exited-leader cancellation and disconnect tests. `cancel-descendant.mjs` prints cancelled=true, settled=false, then cleans up its distinctive test group.

## F05 — P1 — Listed OpenRouter adapter fails creation-time resolution

**Finder:** SC (SC1). **Agrees:** PH + SC, confirmed R1-6. **Evidence:** source trace, no live registry/provider call.

**Location:** `crates/roundtable-web/src/app.rs:185-189`; `crates/roundtable-web/src/tables.rs:68-70`.

**Failure:** The harness-list API adds repository-local openrouter-acp; table creation resolves the submitted ID through autoselect alone, whose built-ins omit it. Normal GUI selection returns unknown harness, or resolves an unrelated remote entry if the registry publishes that ID.

**Fix:** Share one resolver and exact local launch specification between listing and creation; test that a listed local ID resolves using a mocked registry. Also construct command plus argument vector: formatting an unquoted adapter path into a command line breaks paths containing spaces (PH cross-read).

## F19 — P1 — Opt-in provider key is removed again at process launch

**Finder:** SC (SC14, final cross-read). **Agrees:** SC only; PH did not review this final addition. **Evidence:** source trace plus isolated reproduction of the command environment precedence, not a live provider run.

**Location:** `crates/roundtable/src/engine.rs:803-810`; `crates/acp-host/src/process.rs:65,70-71`.

**Failure:** The chair supplies an OpenRouter key and explicitly enables share_openrouter_key. start_seat first puts OPENROUTER_API_KEY in env_remove, then inserts the authorized key into env. Process spawn applies envs first and env_remove afterward, removing the key again. The OpenRouter adapter then fails session creation with authRequired; other environment-based OpenRouter harnesses also cannot use the supplied credential. This remains after F05 is fixed and affects custom-command launch too.

**Fix:** Reconcile removal and explicit authorized sharing: when inserting the shared key, remove that key from the removal list, while preserving all other secret removals. Add a fake-harness launch test for sharing on/off and an existing inherited key. `env-order.rs` reproduces the relevant standard-command precedence with a synthetic variable only, printing false for whether an explicitly set key survives subsequent env_remove.

## F06 — P1 — Stale proposals enter scoring or later polls

**Finder:** PH (PH2). **Agrees:** PH + SC; PH accepted the correction below. **Evidence:** independently traced, not runtime-reproduced.

**Location:** `crates/roundtable/src/engine.rs:576-581`; `crates/roundtable/src/turn.rs:208-217,237-245,272-276`.

**Failure:** A proposing seat starts a tool, leaves waiting, but remains Proposing. Its response can append after JEV's pair set is frozen, getting default-zero missing scores, or contaminate a later poll. A zero-score tie can include the unjudged proposal. Appending does not itself reindex existing pairs; that stronger original claim is withdrawn.

**Fix:** Bind activity to a poll ID, require current waiting membership, reject additions after scoring begins, and select from the exact immutable vector judged. Test arrival during scoring and during a later poll.

## F07 — P2 — Topics can change after judging is disabled

**Finder:** SC (SC13). **Agrees:** SC traced the code; PH endorsed the conclusion in R2-4 but explicitly has not traced the late-score path or reproduced it. **Evidence:** SC source trace only.

**Location:** `crates/roundtable/src/engine.rs:433-445,737-743`; `crates/roundtable/src/turn.rs:256-278`.

**Failure:** Disable judging or clear the key during a poll. Settings change flags but leave topic work intact; a late score still changes the topic. A queued explicit advance is also applied without rechecking eligibility. Owner M forbids progression/polling with judging off.

**Fix:** Invalidate or suspend outstanding topic work when eligibility changes, and recheck eligibility at commit. Test settings changes during collection, scoring and queued advance.

## F08 — P2 — Corrupt identity history is silently replaced

**Finder:** SC (SC4). **Agrees:** PH + SC, PH confirmed R2-1. **Evidence:** source trace.

**Location:** `crates/roundtable-web/src/app.rs:412-418`.

**Failure:** Any read/parse error creates a fresh zero-point profile which overwrites accumulated history at the next rating. Direct truncating writes can themselves leave malformed profiles after interruption.

**Fix:** Initialize only on NotFound; visibly record other read/parse/schema failures. Write atomically through a sibling temporary file and rename; serialize writers sharing the directory. Test malformed existing profiles and write failure.

## F09 — P2 — Monitor events disappear from records and fail browser routing

**Finder:** SC (SC11), independently confirmed PH R1-13. **Agrees:** PH + SC. **Evidence:** source trace plus actual HTML helper reproduction.

**Location:** `crates/agent-monitor/src/lib.rs:70-76,112,142`; `crates/roundtable/src/record.rs:26`; `crates/roundtable-web/assets/index.html:175-177,197-235`.

**Failure:** Monitor harness is an object {pid,id}. Recorder/scoped-stream routing expect a string; browser routing calls includes on the object and throws. UI also has no observation/monitor-failure cases. Initial full attach failure gets an engine notice, but TLS failure and later probe failures do not, defeating required independent visibility.

**Fix:** Normalize/extract harness.id consistently, record/route events to the table, and display observations, attachment state and later failures. Test synthetic monitor events through recorder, scoped SSE and UI. `monitor-routing.mjs` reproduces the helper's TypeError without privileges.

## F10 — P2 — Web layer retains prohibited timers

**Finder:** SC (SC3). **Agrees:** PH + SC; PH confirmed the F08–F14 group by code read in R2-4. **Evidence:** source trace, no runtime reproduction.

**Location:** `crates/roundtable-web/assets/index.html:233`; `crates/roundtable-web/src/app.rs:342`.

**Failure:** Completion schedules a history refresh after an invented 500ms; SSE enables periodic keepalives. Owner M says no timers. The delay cannot guarantee recorder completion on slow I/O and can still show stale history.

**Fix:** Remove timer-based keepalives and update history from table events, or signal recorder completion if disk confirmation is needed. Do not substitute another delay. The open process-shutdown sequence is separate.

## F11 — P2 — Feedback silently loses persistence and advertised identity credit

**Finder:** SC (SC5). **Agrees:** PH + SC, PH confirmed R2-1. **Evidence:** source trace.

**Location:** `crates/roundtable/src/mcp.rs:23,90-91`; `crates/roundtable-web/src/app.rs:75-85`.

**Failure:** Feedback says it builds identity and replies Recorded, but only appends to accolades.jsonl; only end-rating events update identity profiles. Feedback-log open/write failures are ignored, so success can mean no durable record at all.

**Fix:** Surface persistence errors and describe only actions actually completed. If feedback remains an identity tool, resolve genesis identities and use identity persistence before claiming recording. Whether feedback itself stays is owner-open.

## F12 — P2 — Common prompt advertises tools unavailable to the seat

**Finders:** SC + PH (SC7/PH8, narrowed). **Agrees:** PH + SC on prompt defect. **Evidence:** source trace.

**Location:** `crates/roundtable/src/prompts.rs:31`; `crates/roundtable/src/engine.rs:819-827`; `adapters/openrouter-acp/src/adapter.ts:178,190-194`.

**Failure:** A non-HTTP-MCP harness, including OpenRouter, gets instructions to use advance/feedback and may be elected head despite lacking both tools. The chair-side warning does not correct its prompt.

**Fix:** Generate per-seat instructions from actual tool availability. Adapter MCP support using an existing client library could remove the limitation; universal MCP support is not established as mandatory merely by the common prompt's assumption.

## F13 — P2 — Review requests omit their enforced allowance

**Finders:** SC + PH (SC10/PH4, narrowed). **Agrees:** PH + SC. **Evidence:** source trace.

**Location:** `crates/roundtable/src/turn.rs:44`; `crates/roundtable/src/prompts.rs:68`; `crates/roundtable/src/engine.rs:601-602`.

**Failure:** REVIEW replaces the allowance line and invites a message, but its response is truncated/spent as a contribution. A changed or first-ever numerical bank is absent from the request. Publishing a review response is not itself established as forbidden.

**Fix:** Keep the review instruction before the owner's final current-allowance line. Test a review request with a nondefault bank.

## F14 — P2 — Missing peer ratings and empty proposals pass silently

**Finders:** PH + SC (PH6/SC12). **Agrees:** PH + SC on missing-rating/empty-proposal reporting. **Evidence:** source trace.

**Location:** `crates/roundtable/src/turn.rs:213-218,333-356`.

**Failure:** Rating {} records nothing and emits no error, then marks the rater done; partial peer sets also silently omit required peers. Empty proposals lack the per-agent failure used for empty discussion replies. The table can end without the owner's required peer ratings.

**Fix:** Explicitly report missing peer ratings and empty proposals. This is completeness/error reporting, not rating-value validation struck by L#12. Test {}, partial peer sets and empty proposals; no unlimited retry loop is proposed.

## F15 — P2 — Immediate after-work acceptance omits productivity accounting

**Finder:** PH (PH3); SC traced the missing update. **Agrees:** PH + SC on accounting; toggle consequence not runtime-reproduced. **Evidence:** source trace.

**Location:** `crates/roundtable/src/turn.rs:78,91-97,129-134`.

**Failure:** An after-work contribution accepted with judging off/no key is logged, but resolve_reply discards its Accepted outcome. Only asynchronous on_judged records after-work productivity. Counters omit acceptance; enabling judging before another round closes can expose a stale nonproductive streak. Keeping topics disabled hides the progression symptom.

**Fix:** Record after-work acceptance exactly once in both immediate and asynchronous paths. Test an otherwise nonproductive round with immediate worker acceptance, then a settings toggle; avoid all-pass rounds when isolating this because their separate progression condition still applies.

## F16 — P2 — Chair allowance display ignores configured base

**Finder:** SC (SC6). **Agrees:** PH + SC, explicitly confirmed R2-4. **Evidence:** source trace.

**Location:** `crates/roundtable-web/assets/index.html:194,214`; opened event already supplies base at `crates/roundtable/src/engine.rs:367`.

**Failure:** Set base 1024: new seat and accepted-message resets show 512 until another event updates them, misleading the chair while the engine enforces another limit.

**Fix:** Store and use the supplied per-table base at initialization and acceptance reset. Test custom-base acceptance and veto.

## F17 — P3 — Struck private-proposal label remains

**Finder:** SC. **Agrees:** PH + SC, explicitly confirmed R2-4. **Evidence:** literal source versus L#6.

**Location:** `crates/roundtable/src/prompts.rs:23`.

**Failure:** Participants are told to privately propose topics despite the owner's explicit strike, misdescribing visibility.

**Fix:** Remove privately; retain the approved proposal bound.

## F18 — P3 — Failed seats remain described as joining

**Finder:** PH (PH7). **Agrees:** PH + SC. **Evidence:** source trace.

**Location:** `crates/roundtable/src/turn.rs:28`; `crates/roundtable/src/engine.rs:709-713`.

**Failure:** A startup failure alongside successful seats leaves its missing name displayed as (joining) in first participant prompts. Agents coordinate around a nonexistent future member.

**Fix:** List live seats or describe failures accurately without exposing peer model identities.

## Owner-open decisions and acknowledged limitations

These are separate from confirmed defects:

- **Shutdown (PH11):** `crates/acp-host/src/harness.rs:594-639` waits on all close replies before process stop. An unresponsive close can outlive End; N explicitly leaves this waiting policy open. Cancel-before-close helps cooperative agents but cannot guarantee exit. The ACP 1s/2s shutdown sequence also awaits confirmation; do not invent another timeout.
- **Advance deferral:** L#13/N leave its policy open. F07 concerns eligibility changes regardless of whether deferral remains.
- **Allowance credit wording:** M/N leave the proposed credit wording and R §3 rewording open. No cap is authorized; PH9's cap suggestion is withdrawn.
- **Security hardening:** L#17/N leave retaining the package open. F01/F02 repair advertised/implemented boundaries without deciding whether to retain the package.
- **Other N-open matters:** rating carry-forward, whether feedback stays, context handoff, TASTE, three-or-more topic ties and adapter MCP support. Existing builder choices do not settle owner decisions.

## Last cross-read: overstatements and verification limits

- PH2's claim that appending necessarily reindexes existing pairs is corrected in F06, accepted by PH.
- PH4's claim that review replies must not become contributions is unsupported; only the missing limit survives as F13.
- PH5's exact PASS case/punctuation complaint remains a disputed minor parsing-policy point: L#1 permits parsing without specifying its precise tolerance. It is not a confirmed defect here.
- PH10's ended-by-chair reason accurately identifies the initiating End request; no material defect established.
- PH13's process-descendant limitation is not established: `capture.rs:43-58` explicitly seeds the pid family and configures descendant tracking. TLS capture is limited to the leader by design (`lib.rs:33-38`). Keep this as a stated visibility limit, not a new confirmed process-monitoring defect. Probe internals were not audited.
- PH12 is now reproduced against ScopePolicy. It does not prove bypass of independent harness OS sandboxes. SC7's broader demand for universal MCP support is narrowed to the concrete prompt defect in F12.
- Local proofs cover F02, F04 and F09's browser helper. Other entries are source-path findings, not successful live exploit/test claims. PH has not rerun SC's cancellation proof. No paid calls or broad workspace tests were run.
- Important missing regression cases: failure/crash during end ratings; proposals during scoring/later polls; settings changes mid-poll; chair-token inheritance; corrupt profiles; feedback storage errors; monitor routing/rendering; review/custom-base prompts; incomplete ratings. A JEV request that legitimately never answers is not a timer defect. Task-panic reporting merits testing, but no reachable JEV panic was established.
- All artifacts and proof outputs stay under `review/round2/`. Original reviewer files preserve historical numbering; this file gives the triaged conclusions.
