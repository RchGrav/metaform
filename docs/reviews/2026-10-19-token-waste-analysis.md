# API cost and token waste audit — 2026-10-19

Historical audit baseline: `5f76ec7`. Implementation commit: `17983a5`, based on `55edb8c` on `main`, preserving the newer output rules and user prompt-edit permissions. The accompanying changes address message delivery and context handling; the remaining remediation is specified below.

## Finding

**The evidence does not support advertising this implementation as token efficient.** Unnecessary coordination increases the API price an end user pays to complete a task. Metaform has been multiplying small pieces of work into large repeated model inputs through long-lived conversations, message envelopes, duplicated action/assignment context, and correction/review chains. Shortening the final answer alone cannot solve this: accumulated conversation is processed again during subsequent model calls, including calls within one tool-using turn.

**This is an end-user API cost analysis.** The packet records **$1,758.75 USD of API-equivalent Claude usage**, including **$707.80 in one UTC day**. One issue's assignment family consumed **$235.20**; system-agent sessions consumed **$350.47**. Those costs include useful work. They identify expensive concentration points, not permission to label the entire bill waste.

### Total waste attributable from retained delivery evidence

| Attribution | Measured total | What the evidence establishes |
| --- | ---: | --- |
| Removable automatic action manifest | **3,432,919 characters / 146 delivery receipts** | A second catalog of actions/arguments was delivered through ACP although the tools expose their schemas through discovery. Remove the automatic catalog. |
| Removable peer wrapper | **53,674 characters / 30 delivery receipts** | Exact retained rendered prompt minus its exact authored message. Routing envelopes and boilerplate went to the model alongside the message. |
| **Confirmed removable delivered payload, these two sources combined** | **3,486,593 characters** | Distinct components, counted once per retained recipient/epoch receipt. This is a measured subset of waste, not the system's complete historical total. |
| Exact repeated tool-result candidates | **18 extra copies / 7,473 characters / 9 Claude sessions** | Identical tool, arguments and completed text, excluding conversations with a retained compaction notice. Not added to the confirmed total because UI records do not prove complete provider delivery or complete compaction history. |
| **Historical API dollars attributable to all waste** | **Not recoverable from the existing accounting** | Missing per-invocation component attribution prevents separating wasted context rereads and unnecessary calls from useful work. This is a serious observability defect, not zero waste. |

The confirmed payload subtotal uses actual `acp_prompt` receipts, not a replay estimate. These tables retain the latest named component in each context epoch; overwritten deliveries and most subsequent cache rereads are absent from that subtotal. **3,486,593 characters is therefore not a ceiling on the waste.** The peer replay figure later in this report overlaps the wrapper mechanism and must not be added to this total.

An exact historical token or dollar waste total cannot be manufactured by multiplying all cache reads by a price or declaring all coordination unnecessary. The concrete deliverable here is a reproducible measured subtotal, explicit cost calculations, and instructions to close the accounting gap so a complete waste bill becomes possible.

### API cost of the measured waste

Provider-specific tokenization and per-call price records are unavailable for these payload receipts. The following are **pricing scenarios**, not current vendor price quotations or reconstructed invoice lines. They use a declared rate card of **$5/M uncached input, $6.25/M cache writes, $0.50/M cache reads, and $25/M output**. Substitute the end user's actual model, cache duration, region, service tier and contract prices. A live pricing-document fetch was denied during this audit, so these rates are deliberately not presented as verified current prices.

| Conversion sensitivity for the 3,486,593 measured characters | Estimated unnecessary tokens on first delivery | One cache write | Write + 100 subsequent cache reads | Write + 1,000 subsequent cache reads |
| --- | ---: | ---: | ---: | ---: |
| 5 characters/token | 697,319 | $4.36 | $39.22 | $353.02 |
| 4 characters/token | 871,648 | $5.45 | $49.03 | $441.27 |
| 3 characters/token | 1,162,198 | $7.26 | $65.37 | $588.36 |

These character/token ratios are sensitivity assumptions, **not tokenizer measurements or statistical bounds**. The read counts are scenarios, not observed counts for every component. Each scenario assumes all of this subtotal remains in its recipients' contexts for that many later calls. Output, missed-cache premiums, unnecessary whole calls, reviewer multiplication, and unrelated payload waste are excluded. The first-write column alone would materially understate the cost of keeping unnecessary context alive.

For exact token counts and observed rereads, calculate:

`payload waste USD = unnecessary uncached tokens × input rate / 1e6 + unnecessary cache-write tokens × write rate / 1e6 + unnecessary cached tokens across later requests × read rate / 1e6 + unnecessary generated tokens × output rate / 1e6`

For a completely unnecessary call, count its entire reported marginal cost once. Do not also add that call's component costs into the total. Attribute any history it leaves behind on **later** calls separately. This avoids double counting and makes the amount recoverable by each remediation explicit.

### Why unnecessary turns are a pricing failure

The packet retains a system conversation at **874,954 context tokens**. At the scenario's $0.50/M cache-read rate, rereading that much cached context costs approximately **$0.4375 per model request before output**. A status note can be only a few words and still initiate an expensive request. One ACP turn can contain several such requests.

| Avoidable model requests at that retained context size | Cached input cost alone |
| --- | ---: |
| 100 | $43.75 |
| 1,000 | $437.48 |
| 10,000 | $4,374.77 |

This is a scale illustration, not a claim that the packet contains those exact avoidable-request counts. At a $5/M uncached rate the same context costs approximately **$4.37 per request**. The engineering objective must be to eliminate unnecessary requests and unnecessary retained context; cheaper caching alone does not fix the economics. End-user pricing should be evaluated in **dollars per verified completed task**, including coordination and review, rather than price per worker or ticket.

## Evidence and measurement limits

The imported project packet was analyzed through Metaform's public Store API on a separate copy. It contains 354 dispatch sessions, 61,718 conversation records, and 5,637 spending rows across October 12–19 UTC. Spending rows were deduplicated by `(session_id, seq)` across project and legacy stores; the legacy tables added zero rows. A spending row may hold only cost or only tokens, so row counts are **not** turn counts.

All 146 historical orchestration assignments remain user-stopped. No real agent, self-healing runner, or paid model was started for this audit. Verification uses fixture adapters. The packet predates several fixes in the current source; historical findings and remaining defects are separated below.

The source packet has no complete per-provider billing export or complete final ACP prompt trace. It also does not include the user's current live process state or current global settings. Prompt receipts retain the latest component for each recipient/epoch/name; their sizes are retained evidence, **not** a complete cumulative delivery ledger. Stored tool details and envelopes are not automatically evidence that every byte reached a model.

### Recorded Claude usage

| Component | Recorded amount |
| --- | ---: |
| Uncached input | 39,732 tokens |
| Cache creation | 61,085,248 tokens |
| Cache reads | 4,138,747,859 tokens |
| Output | 12,728,466 tokens |
| Raw sum of those components | 4,212,601,305 tokens |
| Metaform's weighted “tokens” counter | 487,729,367 |
| Reported API-equivalent cost | $1,758.75 USD |
| Claude sessions with spending records | 302 |

Cache reads account for about 98.2% of that raw sum. They include repeated reads of the same context, not 4.14 billion distinct words of useful work. Caching lowers the provider's accounting cost of rereads; it does not make a large, repeatedly invoked conversation free. Recorded consumption is **not all waste**: necessary reasoning, code reads, tool use, and verification also consume it.

| UTC day | Claude cache reads | Claude output | Reported API-equivalent USD |
| --- | ---: | ---: | ---: |
| October 12 | 894,802 | 7,293 | 2.15 |
| October 13 | 82,029,362 | 336,855 | 37.48 |
| October 14 | 449,151,449 | 2,503,778 | 247.52 |
| October 15 | 1,764,366,945 | 5,904,213 | 707.80 |
| October 16 | 448,288,438 | 1,136,587 | 188.58 |
| October 17 | 3,053,385 | 13,024 | 3.53 |
| October 18 | 1,174,890,377 | 2,267,931 | 480.15 |
| October 19, partial packet | 216,073,101 | 558,785 | 91.55 |

The most recent two UTC dates in the packet total $571.70 in reported API-equivalent usage. These are recorded API-equivalent costs for the observed workload.

### Where the amplification is visible

- Eight Claude system-agent sessions, including older records identified by `about=system`, account for **902,419,808 cache-read tokens** and **$350.47** of reported API-equivalent cost. One retained system conversation occupied **874,954 context tokens**. Keeping routine work reports out of this context is a high-priority pricing correction.
- The camera-selection/orbit issue rooted at `5decae95491d4e928076d200000dad5a` has **46 distinct work IDs in its recorded assignment family**, **573,654,429 cache-read tokens**, and **$235.20** reported API-equivalent cost. Review/correction multiplicity needs an explicit economic test against verified improvement to the candidate.
- **139 unique project-update envelopes** occupy **1,217,599 characters**, containing **224,225 characters of message text**. Routing, result, candidate, evidence, and related data dominate the stored envelopes. This storage ratio alone is not the delivered-token ratio.
- Re-rendering the packet's **293 unique peer envelopes** through the pre-change `peer_note` formatter produces **959,145 characters**; their actual message bodies total **324,373 characters**. Message-only delivery removes **634,772 characters, or 66.18%**, from that formatter replay. This is an exact character comparison, not a Claude tokenizer estimate or a measured reduction in API charges. The current system inbox already avoids sending ordinary project-update bodies automatically, so the replay is not a claim that all 293 would be delivered on current main.
- Retained `orchestration:actions` receipts contain **3,432,919 characters across 146 receipts**, up to **27,018** for one component. Retained assignment snapshots contain **1,875,763 characters across 144 receipts**, up to **59,343** for one component. These are latest retained snapshots, not lifetime totals.
- One memory entity, “Map keys, follow (A) and agent view (V),” occupies **1,287,404 characters across 116 retained receipts**. Another, “Agent size held by default (key 6),” occupies **711,002 across 110**. Required project knowledge needs appropriate scope and stable atomic updates; broad, large entities make each fresh context expensive.
- The old roundtable flow left **371 message records totaling 1,289,104 characters across five participant sessions**. The current `roundtables` module uses a different external engine, so this is historical evidence of fan-out, not proof that the replacement repeats it.
- Of retained Claude state records, **308 select `opus`**. This is the final recorded selection, not reliable model attribution for every earlier turn. Small coordination work was not visibly separated into a cheaper model class in those final settings; model choice should remain the user's decision.

## Changes made with this audit

1. **Peer delivery sends the authored message text.** JSON routing envelopes, candidate/evidence fields, boilerplate, and supplied context components are no longer appended. Stored identities, delivery receipts, and reply routes remain available to the tools.
2. **Established conversations skip automatic guidance reconstruction.** A note, timer or continuation does not trigger another full assignment/actions/memory payload. A new conversation receives its initial task context once. Resume and compaction recover through scoped resource/tool reads. Human direction retains priority and the existing steering path.
3. **Check-ins carry their summary.** Older persisted check-ins can obtain their summary from `report`; transport no longer falls back to dumping the entire envelope as JSON.
4. **Default user-facing notifications are ticket + basic status.** For example: `Ticket 654 — done`. Inbox summaries omit title, narrative, candidate and evidence. An explicit `dispatch_notes note=<id>` read retrieves the authored message; assignment inspection retrieves structured evidence. Candidate and verification evidence are no longer automatically appended to the author's message body.
5. **All dispatch roles receive concise communication guidance once per context epoch.** Routine summaries should use one to three short sentences, identify outcome/essential verification/blockers, and keep detail in work records. The person's request for detail takes precedence. No summarizer model or truncation pass was added.
6. **The shipped implementer prompt drops ceremonial verbosity.** Its body falls from **2,725 characters / 361 words** to **730 characters / 102 words**. It retains planning, codebase awareness, concurrency, safety, verification, and durable evidence requirements without requiring a four-section answer and multiple narrated alternatives for routine work.
7. **Startup no longer appends a second action catalog or a full assignment snapshot.** The agent reads its pinned Metaform role URL; the tools supply their own schemas. Assignment/history details are retrieved for the action that needs them. This removes the automatic `orchestration:actions` component measured above.
8. **Context receipts now retain content hashes across names and versions.** Unchanged bodies are suppressed within a context epoch, including aliases and version reversions. A reversion sends a small reference indicating which retained version is active, rather than silently leaving the agent on the intervening version. Legacy receipts seed the ledger when updated. Receipt inspection returns metadata rather than another body dump.
9. **A startup/resume retention check shares the first necessary turn.** The agent acknowledges a new checkpoint with a key given once in its retained context. Resuming does not reveal the old key again. Missing or incorrect proof makes context eligible once; stale replies cannot invalidate it twice. Nothing schedules a recovery turn or pushes a context dump. The next relevant read recovers what it needs. This demonstrates retention of the checkpoint instruction/key, not mathematical proof that every token of opaque provider context survives. There is no additional ACP turn, but the acknowledgement tool call can add a provider-internal request; account for that required coordination cost rather than calling the check free.
10. **An agent's own memory-detachment write is acknowledged locally.** `memory.unjoin` now records what the author already knows and excludes it from change recipients. Other agents still receive the applicable withdrawal on a contextual read.

These changes affect new code execution. They cannot remove context already held by a live provider conversation. Existing pinned role snapshots and user prompt overrides are durable choices; this patch does not silently rewrite them. A deployed runner must load the changed code, and new or explicitly refreshed contexts are needed to realize the full benefit. No running user session was stopped or reset here. Concise prompt instructions guide model behavior; they are not a guarantee that every generated answer will obey a word limit.

## Remediation status and remaining findings

| Priority | Finding and current source | Required remedy and acceptance check |
| --- | --- | --- |
| P0 | **Context grows without an economic explanation.** Historical system context reached 875k tokens. `dispatch/runner.py:prompted`, `spend`, and `trace` do not persist a local causal ledger linking each final prompt's components to its eventual usage. | Record prompt cause, recipient, model, exact input component byte counts/fingerprints, and reported usage. Report cost by human request, peer message, correction, retry, memory follow-up, and roundtable. Every invocation must have one attribution record, including interrupted calls. Do not record another copy of sensitive prompt text merely to count it. |
| Fixed here; verify deployment | **Duplicate action schemas in automatic guidance.** `current_guidance` previously constructed a large `orchestration:actions` JSON manifest although connected MCP tools already describe their arguments. | Removed that automatic component. Keep discovery authoritative. Verify production adapters can call, return, inspect and stop using their discovered tools; record zero bytes for `orchestration:actions` in new ACP deliveries. |
| Fixed automatic path; P0 for explicit reads | **Whole assignment snapshots as a changing component.** `current_guidance` previously included task, specification, candidate, last check-in, returned children, corrections, and assessments in one fingerprint. | Removed automatic snapshots. Next, add field-selective `orchestration inspect` responses: stable task/spec, changed state, selected child result and evidence by handle. Repeated explicit inspections must not resend unchanged bodies. A state-only change must not resend task/specification/history. |
| P0 | **Configured budget behavior is incomplete.** `budget_check` says no further automatic turns after a reached budget; the checks explicitly suppress memory follow-ups, but `turn`/`prompted`, timers, and peer continuations have no corresponding general admission check. | Enforce the user's selected policy consistently for automatic turns while preserving human messages, Stop, overrides, and availability of triage. Test a budget reached with several queued causes. Do not change unlimited/signal defaults or add approval gates as a substitute for reducing waste. |
| Fixed here | **Redundant role delivery path.** `current_guidance` injected pinned role components and then asked the worker to read that URL. The resource already shared receipts, so a duplicate full body was not established; the extra path/roundtrip was redundant. | Role URL is now the single authored-duty delivery path. Preserve pinned versions. Verify first read delivers duty once, subsequent reads suppress it, and a post-compaction explicit read restores only that resource. |
| P0 | **Deduplication is not yet universal.** The shared ledger covers component-aware delivery paths. Direct tool results, unrestricted assignment inspection, host-supplied context and opaque adapter internals can still repeat data outside it. | Route automatic instruction/context-producing responses through the same recipient/epoch/content ledger. Preserve explicit human messages and real state-change references. Instrument actual output boundaries, not merely queued envelopes. Reject an efficiency claim until duplicate-content accounting covers every paid path. |
| P1 | **Completion can create a bookkeeping turn.** `dispatch_record_on_finish` defaults to `when-missing`; `record_prompt` checks whether this runner wrote memory. A valid task that learned nothing new can therefore receive another model turn. | Establish necessary knowledge during the work, then complete deterministically when there is nothing new to retain. Distinguish “no new knowledge” from “required knowledge missing.” A simple successful task with no durable learning must not need a second inference merely to satisfy a write predicate. |
| P1 | **Review loops and child fan-out have consumed substantial usage.** The 46-work family is the clearest historical example. Current direct-specialist, canonical-correction, and review-count changes already address part of this. | Verify against replayed findings: the same unresolved fault updates one canonical ticket, reviews run against a changed candidate or new evidence, and completed/unchanged candidates do not create another coordinator tree. Measure useful fixes per model turn, not ticket throughput. Honor the 146 existing user stops. |
| P1 | **Memory payloads are large and refinement can cause churn.** `memory/delivery.py` now has receipt/self-write protections, but large entities and broad scope remain in the packet. | Apply CEL and functional scope toward relevant descendants; send changed observations rather than unrelated entities. Verify that a control-specific worker sees its applicable imperatives, not global unrelated map knowledge, and that its own unchanged writes create no fresh delivery. Preserve meaningful inherited instructions. |
| P1 | **Fork usage is missing from the dispatch turn meter.** `fork_turn` calls `conn.prompt` and reads only `stop_reason`; it does not pass returned usage through `spend`/`trace`. | Attribute fork usage once to the child and its parent work, with no double counting of provider aggregate updates. Test success, exception, cancellation, and resume. |
| P1 | **Failed prompts have no final usage row.** `prompted` records `spend` after a successful return; its exception branch traces an error but does not persist an unmetered spending row. `provision` is an estimate derived from context size, not actual provider call usage. | Persist attempted-call and unknown-usage evidence on failures/cancellations, reconcile later provider readings, and label estimates. Never interpret missing measurements as zero cost. |
| P1 | **Roundtable ACP subscriptions sit outside the advertised dollar cap.** The new module explicitly limits OpenRouter spend; its comments state subscription ACP seats are unpriced. It does use dispatch's worker admission gate. | Include external engine seat invocations in the same usage/cause view and expose the cap's actual coverage. Test the external engine's per-turn context and termination behavior separately; this packet does not contain that runtime. Do not advertise a comprehensive dollar cap while adapter calls outside it remain unpriced. |
| P2 | **Static instructions and output formatting repeat.** `AGENTS.md` is 9,584 characters and `CLAUDE.md` 18,940; both include the semantic glossary. Actual host loading determines whether both enter a given Claude context. | Measure the final host prompt, then deduplicate only proven overlapping delivery while retaining the immutable semantic definitions and actual project rules. Avoid speculative percentage claims based on file sizes alone. |
| P2 | **Broad sends and tiny acknowledgements can amplify long histories.** Historical roundtable fan-out is measurable; `dispatch_broadcast`, peer replies, workflow wakes, timers, and recovery can each initiate work. | Make recipients explicit and task-relevant. Avoid automatic acknowledgements and status-only follow-ups; coalesce useful bursts. Test that one meaningful update creates at most one necessary recipient turn, and that human messages retain priority. |

## Specific implementation instructions for the remaining remediation

### 1. Make the complete waste bill calculable — P0

Change `dispatch/runner.py` at `prompted`, `fork_turn`, `spend`, `cost_spent` and `trace`, plus the external roundtable bridge. Use the public Store API for a versioned, append-only invocation ledger. Persist an invocation before sending it, then reconcile its completion. No polling or second model should be involved.

For every invocation, retain: invocation/request ID; parent invocation; project, work, assignment and recipient IDs; context epoch; adapter/model and price-card version; trigger (`human`, `peer`, `timer`, `review`, `recovery`, `memory bookkeeping`, `roundtable`); queued/sent/completed/cancelled/error timestamps; input/output/cache-write/cache-read counts; currency and reported incremental cost; and whether usage is measured, estimated or unknown. For each delivered context component, retain its fingerprint, purpose, byte count, token count when measurable, necessity classification and originating invocation. Store references rather than additional copies of prompt bodies.

Instrument the **actual provider request boundary** where the adapter exposes it. An ACP prompt can contain many internal model requests; labeling one ACP turn as one API call would leave the largest amplification invisible. When the adapter cannot expose that detail, label coverage as ACP-only and the unallocated cost explicitly. Do not invent request counts from spending-row counts. Capture model changes per invocation instead of using a session's final selected model for its history.

Reconcile cumulative adapter cost updates by stable provider session/request identity and deltas; deduplicate replayed updates after resume. Attribute a fork once to its child, roll it up to its parent for reporting, and never sum both as separate spending. An exception/cancellation must retain an attempted invocation and `usage_unknown` until actual usage arrives. Token prices must distinguish cached reads, cache creation durations, output, applicable context-size premiums, batch/service-tier discounts and contract rates. Do not add reasoning tokens twice when they are already included in output.

**Acceptance:** successful, interrupted, failed, resumed and forked fixture calls each produce exactly one invocation record; cumulative-update replay adds zero duplicate charge; report totals reconcile to the provider export where available. Every unallocated dollar appears in a named bucket. Produce a per-task view showing productive work, required coordination, confirmed waste, estimated waste and unknown attribution. The last three must not silently disappear into a general “tokens used” total.

### 2. Finish context deduplication across every output path — P0

Use `agents/roles.py` as the shared receipt owner through the public `prepare_agent_context` / `record_agent_context` APIs. Apply it to context-producing tool responses as well as `mcp/server.py` resource responses. In `orchestration/state.py` inspection, add field selection and stable handles for task/specification, current state, a selected child's result and evidence. In `memory/delivery.py`, deliver changed observations and restoration/withdrawal references at the applicable functional entry. Audit full graph reads, role-resolution tools and host-injected instructions separately; they must not bypass accounting merely because the MCP resource path deduplicates correctly.

Hash the actual rendered content, with receipts scoped to recipient and context epoch. Preparing a response must not consume its receipt. Commit only after the supported transport/output boundary succeeds. Retain historical hashes so renaming a component or reverting to an earlier version cannot resend its body. Send a short activation reference when a previously delivered version becomes current again. Failed sends remain eligible; a stale pre-compaction completion cannot acknowledge the new epoch. Missing startup proof changes eligibility once and never schedules a replay. Close the concurrent prepare/commit race with recipient-scoped serialized delivery or a durable pending-delivery protocol: two responses prepared before either is committed can otherwise both contain the same component. The current ledger alone does not establish an exactly-once guarantee for those concurrent requests or for opaque host delivery.

**Acceptance:** the same instruction returned inline, through a role URL and through a tool appears once in retained context, including simultaneous requests; aliases do not bypass it; A → B → A changes the active version with a reference only; a failed send is retryable; compaction or failed proof allows one relevant reread; unrelated knowledge remains absent. User-authored messages and overrides always remain deliverable. Add an adapter-level duplicate-byte counter so the claim is measured at delivery, not inferred from stored envelopes.

### 3. Eliminate model calls with no useful work — P0/P1

In `dispatch/orchestration.py`, `peering.py` and `runner.py`, keep routine results in the durable inbox. A burst of 100 completions should create **zero** standalone user-facing-agent turns. The next actual user turn can carry one coalesced line of ticket/status references. Read one selected note when its content is needed. Reserve automatic wakes for actionable blockers/questions under the user's configured policy; suppress acknowledgement-only ping-pong.

In `runner.py:record_prompt`, `ticket_done` and the stopped/failure follow-up paths, replace “this runner did not write memory” as a reason for another model call. Complete deterministically when there is no new durable knowledge. If a task requires a durable record, make that requirement part of the task's existing completion action and validate the resulting record. No separate “write something” turn should be needed for an otherwise finished task.

In `board.finished` / `stay_connected`, pass the affected fault identity and candidate revision. An unrelated ticket completion must not start a new system-agent session to inspect every fault. Let deterministic watchers clear proven conditions and update canonical tickets. In orchestration's review/correction transitions, key review eligibility by fault identity, candidate revision and evidence revision; repeated unchanged findings update the same work instead of creating another coordinator/reviewer tree.

**Acceptance:** no-action completion, unchanged candidate review, duplicate log error and status-only reply each add zero paid calls. Replaying the camera/orbit family must show the exact candidate/evidence change that justified every review and child assignment. Report cost per independently verified fix, plus avoided invocations. Honor the existing user-stopped assignments.

### 4. Enforce the user's economic controls consistently — P1

Centralize automatic-turn admission for queued peers, timers, workflow continuations, recovery and maintenance. Apply the user's selected budget action consistently at execution time, including work queued before the budget was reached. Preserve unlimited/signal modes, human messages, Stop, explicit overrides and an available user-facing agent. Do not impose per-ticket confirmation as a waste remedy. Keep worker-capacity limits separate from triage and temporary automation capacity.

Attribute external roundtable seats and forked work to the same project/task cost view. Expose which engines a dollar cap actually covers. Offer model selection per responsibility without silently changing the user's choices. Keep project switching and tabs from destroying retained agent contexts; forced restarts would repay initial context costs and lose the basis for deduplication.

**Acceptance:** set a budget, queue each automatic trigger, cross the budget, and verify each follows the selected action while human input/Stop still work. Verify project switches keep existing session IDs and receipts. A dollar cap cannot be advertised as comprehensive while adapter calls outside it remain unmetered.

### Evidence required before claiming token efficiency

Run a fixed workload before and after remediation: a small code fix, a review requiring one actual correction, a brownfield intake, a multi-worker dependency and a project switch/resume. Preserve the same model/rate card, task, candidate quality requirements and verification. Record cold-cache and retained-context cases separately. Compare against an appropriate direct-agent baseline completing the same work, including its verification costs.

Publish total API dollars per accepted task, redundant delivered tokens, avoidable invocations, required coordination dollars, latency and accounting coverage. Report distributions across repeated runs; a single cheap run is insufficient. Duplicate unchanged automatic instructions within an epoch, body dumps on routine notifications, unmetered forks, and billed calls with no explainable cause are release failures for an efficiency claim. Do not claim a percentage saving from prompt character reduction alone.

### Meter interpretation

`dispatch.billable` computes approximately:

`uncached input + output + cache creation + ceil(cache reads / 10)`

This is a heuristic weighted counter. It does not apply model-specific output prices or cache-creation premiums and must not be presented as an API price. Thought tokens are reported separately and must not be added again to output. Recorded cost rows require provider reconciliation before being described as invoice charges. Cross-project and external-adapter costs also need coverage in an end-user total.

### Existing protections that should remain

Current main already coalesces queued peer notes, suppresses duplicate deliveries, prioritizes human direction, and gives the system agent a compact inbox instead of automatically injecting ordinary result bodies. Memory changes no longer push autonomous notice turns. New work defaults to direct specialists instead of creating a coordinator by default. These are material fixes; the historical packet does not demonstrate that they have failed in the currently deployed application.

`board.finished` currently raises a signal for every completed ticket to check possible cleared faults. An already connected system agent keeps ordinary board items in its inbox without a dedicated wake. **If no system agent is running, however, `stay_connected` can start one for a waiting board signal even with “Keep triage connected” off.** Thus an unrelated completion can cause a fresh model startup. Connect a completion to affected fault IDs and let deterministic proof/watch logic clear what it can. Preserve the user's choice to keep triage available; measure this startup separately from actual fault investigation.

Automatic paths inspected: initial/handover/recovery prompts, peer and user-direction delivery, inbox and board events, workflow resume, timers, post-finish/stop/failure memory prompts, forks, helper completion, orchestration returns/reviews, and the external roundtable bridge. This is coverage of the application's visible orchestration paths, not a claim to observe internal provider reasoning or hidden calls made by an external adapter.

## Verification and reproduction

The committed [aggregate evidence](../../evidence/token-waste/2026-10-19-summary.json) contains recorded usage, cost concentrations and the waste ledger. The [reproduction instructions](../../evidence/token-waste/README.md) and `reproduce.py` recover the measured waste subtotal through the public Store API without a model call; the reproduced JSON matched the saved ledger exactly. No private message bodies are committed.

Additional local audit artifacts are under `/workspace/.onboarding/token-audit/`: `analyze.py`, `details.py`, `packet-usage.json`, `packet-details.json`, `waste-ledger.json`, and CPU/test logs. `details.py` replays the **baseline** formatter; run it against the baseline checkout, not the modified module where that formatter is removed. The original imported packet was preserved separately.

Deterministic meter probes in `meter-probes.json` confirm that a session with an already reached budget still queues an automatic peer turn, and that a simulated fork prompt returning usage invokes no spend recorder. Neither probe calls a paid model.

The combined focused suite passed **90 tests, with one explicit idle-measurement test skipped in that run**. It covers exact message bytes at the ACP boundary, concise inbox output with detailed explicit reads, no context reconstruction for established conversations, role-resource delivery, retention checks, version restoration references, preserved structured evidence, memory withdrawals, peer-team authority, and actual ACP compaction followed by contextual recovery. Three older memory tests were updated to exercise contextual reads instead of calling notice APIs already removed on the audit baseline; the no-extra-turn requirement remains asserted.

The idle test was then run explicitly and passed: over 60 seconds, the runner used **0.03 CPU seconds (0.05% of one core)** and the fixture adapter used **0.00**. The pre-change baseline used 0.01 CPU seconds for its runner and 0.00 for its adapter. These are single observations, not a statistical performance claim. The irrelevant-event burst test verifies zero reads and zero scheduled work. Ruff and the targeted strict type check passed. No paid model was called.

Additional fixture adapter checks exercised generated specialist creation/reuse, installed BMAD role-resource delivery, compaction recovery, cross-project replies, retained session identities, offline notifications and replay suppression. Cross-project tests now inspect a selected note for routing details instead of expecting the compact inbox list to contain the full envelope.

An earlier broader runtime run exposed two failures also reproduced on untouched `5f76ec7`: a test expecting exactly four created sessions sees an additional automatically started triage session, and a test waiting for every session to end times out because triage remains available. The unconditional completion-to-board startup described above explains these baseline failures and remains a remediation item. A complete repository-wide green run is not claimed.

The acceptance target for the next phase is **necessary context once, meaningful updates to their actual recipients, and every model invocation explainable by a user request or a concrete state change**. The confirmed payload subtotal is measurable waste. The complete historical dollar total remains unaccounted for, and the pricing scenarios must not be substituted for that missing measurement. A token-efficiency claim requires the per-task API cost evidence and zero-duplicate acceptance checks specified above.
