# GC-led orchestration implementation and evidence

## Candidate and scope

The runtime and prompt candidate tested is **`8c9bf81eaa6876b5dc34766574ebb1eece2a5851`**, tree **`0491a3ce9f3d0814c835de60f6070211ccf9dd57`**, on local branch `implement/gc-led-orchestration`. Its parent is the authoritative current checkout, **`10e2984ea36231b474b197e30661712ff45e3765`**. The later verification commit contains evidence and test expectation/coverage changes; it does not change the runtime or prompt implementation.

The supplied design reviewed `eea0d1678bb9e8a4369d46380a65613379871176`. Six subsequent commits were reconciled before implementation. The last-minute removal of the link-before-write gate, asking mode, command sandbox, confined terminal and read-only ignore controls remains operative. Those mechanisms were not restored. Existing work claims, user controls and configured dynamic blacklist remain in effect. See [source-reconciliation.json](source-reconciliation.json) and [candidate.json](candidate.json).

This is runtime implementation evidence. The packet's `VALIDATION.md` established artifact parsing and source fidelity; those checks did not establish live orchestration. Here, scripted adapters run as real ACP subprocesses under Metaform's runner, and a worker uses the runner-supplied stdio MCP server in another process. Assertions inspect actual recipient turns, process suspension/load/cancellation, work ownership, generated versions, notification bodies and capacity. No production model's autonomous judgment is claimed.

## What changed

### Ownership, roles and delivery

The new shipped `orchestration` module declares public providers, verbs, resources, tables and event subscriptions through the existing loader. It records root ticket and GC ownership, parent and immediate caller, team, authored role, functional locations, requested result, candidate/validation evidence, operative specification, current mode, actual session/runner binding, retained check-in, pending direction, stop history and continuation delivery.

The Liaison/Triage/PM retains the existing `dispatch:system` identity and represents user intent, priorities and delivery status. The GC owns the ticket, its swarm, internal criticism, validation and integration. The `functionality` role is the independent Functional Quality Critic; its reviewed-work relationship is separate from the reviewed GC's swarm membership. A delivered GC root remains closed while subsequent findings create recorded corrective GC continuations.

The module registers 17 native authored responsibilities, including `role_creator`. The physical packet contains 16 entries; the operative request also requires the GC-owned Role Creator. Authored responsibility is separate from the existing operational execution role. Native, custom-module, generated and installed BMAD role definitions share the provider/resolver path.

An existing specialist can be called directly by a worker. A missing-role request preserves the requested contribution, original caller and context, then reaches the recorded GC. Only that GC commissions the Role Creator; only the commissioned creator publishes the registered definition and prompt-store duty. Publication resumes the original specialist call. Generated duties need no shipped XML element and retain source, version and selected override history. Calls and results use durable identities; result keys are scoped to the returning assignment so a reused specialist cannot suppress another call's return.

### Capacity, messaging and recovery

Managed GC, specialist, Role Creator, FQC, corrective and resumed launches use dispatch's existing admission machinery. A waiting parent's actual adapter ends before its capacity lease is released. Its child then starts, and the returning result resumes the immediate caller through the same admission path. Native ACP forks initiated through Metaform acquire capacity before creation and before later active turns.

Discovery lists registered agents, including conversations, independent assessments and queued/suspended assignments. Message envelopes retain the actual sender session/runner and assignment/team relationship. Ordinary notes and agent messages enter the normal-turn queue. They do not invoke steering or cancellation. Thread IDs and per-session delivery states survive reuse and reconnect, including editor sessions sharing one held work record.

A GC broadcasts to its own swarm, including descendants, and may interrupt its own members. Other teams and ordinary peers gain no such authority. The four fixed peer-note controls (`NOTE_MOST`, `NOTES_HOURLY`, `PAIR_HOURLY`, `NOTE_REACH`) and their peer enforcement/help assumptions were removed. The unrelated voice-log truncation constant with the same `NOTE_MOST` name was preserved.

Interruption records the new direction before cancellation. Retained work, check-ins and pending direction enter resumed recipient context. User stop stores a tombstone, cancels pending continuations and reaches descendants and independent assessments while preserving completed delivery history. Explicitly admitted user resume clears only the selected assignment's stop.

### Functional assessment and specification changes

C(T) preserves the functional core; it is not a snapshot of context. FQC receives the candidate, functional grounding and the GC's validation evidence. Implementation findings return corrective work to responsible GCs and remain visible to the PM. The original root does not wait indefinitely for an assessor to close it.

Adaptive changes preserve before/after source, exact revision, observed limitation, C(T) rationale and affected work. Publication updates the operative file or workflow source, sends recorded GC change orders, and publishes an actual user/PM message through the existing Chat surface. Notification does not create an approval wait. Strict mode records a recommendation while retaining the operative source. Actual newer user instructions retain their effect; a supplied noun or session omission cannot impersonate the user.

Frozen workflow runs get recorded successors through the existing workflow history and verbs. Variables, completed branches, active child return routes and genuine user-input pauses survive. Recovery follows existing successor links and reconciles newer source revisions without reopening completed execution. Post-delivery FQC requests for missing roles receive a separate corrective GC to own the commission, preserving the original assessment's specialist return.

### Prompt, memory and UI integration

Native common/duty/event components and selected prompt updates are merged by existing identity. Targeted migrations operate on the actually selected version, append an updated child version once, and retain user-authored register and unrelated text. Ambiguous or missing anchors preserve the selected override and expose diagnostics. Newer explicit user edits stay authoritative. Legacy skill component aliases and whole-file selected skill procedures resolve through their existing identities.

Preparation and inspection do not acknowledge delivery. Persistent receipts identify the agent, context epoch, actual rendered body/fingerprint, actual version, selected version and channel. ACP acknowledges after the outgoing handoff; MCP acknowledges after final result shaping. Shared components suppress unchanged material within an active epoch. Compaction advances the epoch. Failed selected overrides record the actual fallback separately. Current action bindings come from actual module verbs, schemas, adapter capabilities and configured controls.

Canonical graph CRUD maintains entity/observation/relation identity through functional entry points. Memory-body receipts identify exact delivered revisions. Counts and notices do not acknowledge bodies. Corrections/deletions, shared identities at multiple entry points, concurrent reads and new epochs retain the correct unread state. Relevant changes reach active recipients through the existing relay without replaying unchanged content.

The existing UI exposes role, assignment, GC/team/root/caller relationships, independent reviews, pending direction and continuation state. Native, generated and installed BMAD roles are selectable through public managed operations. Actual project-update messages appear in the live banner and Chat, with no model-launch or composer controls on that notification conversation. A second committed notification updates an already open page through the existing event system.

## Verification results

| Gate | Observed result | Evidence |
| --- | --- | --- |
| Integrated actual runner/ACP/MCP scenarios | All 9 scenarios have passing evidence: 8 in the initial run and strict mode on its corrected readiness rerun | [initial run](integrated-runtime-initial.xml), [strict rerun](integrated-strict-rerun.xml), [scenario summary](runtime-summary.md), [recipient and capacity evidence](runtime-summary.json) |
| Two concurrent GC teams: actual notes, replies, scoped broadcast and interruption | 1 passed at configured capacity 3 | [cross-team.xml](cross-team.xml), [recipient evidence](cross-team-recipients.json), [explanation](cross-team.md) |
| Orchestration, workflow and BMAD contracts | 27 passed | [orchestration-contracts.xml](orchestration-contracts.xml), [contracts.md](contracts.md), [contract-snapshots.json](contract-snapshots.json) |
| Cancellation, recovery, autostart and event lifecycle | 35 passed | [dispatch-lifecycle.xml](dispatch-lifecycle.xml) |
| Capacity, shared-session identity, unrelated event reads and idle CPU | 4 passed | [dispatch-capacity-events.xml](dispatch-capacity-events.xml) |
| Actual peer/editor normal-turn delivery | 4 passed on the same frozen implementation | [dispatch-peer-identity.xml](dispatch-peer-identity.xml) |
| Roles, prompt migration, skill deployment and selected MCP checks | 124 passed; one stale resource-inventory expectation corrected and its case then passed | [roles-prompts.xml](roles-prompts.xml), [resource-inventory.xml](resource-inventory.xml), [roles-prompts-verification.md](roles-prompts-verification.md) |
| Actual Chromium notification and native/BMAD launch scenarios | 2 passed | [browser.xml](browser.xml) |
| Canonical memory, revision receipts, functional Around and MCP Watch | 63 passed | [memory-focused.xml](memory-focused.xml) |
| All changed Python implementation files, strict Pyright | 0 errors, 0 warnings | [pyright-changed.txt](pyright-changed.txt), [checked files](pyright-changed-files.json) |
| Whole-repository Ruff | All checks passed | [ruff.txt](ruff.txt) |

The original resource-inventory failure is retained in its JUnit report. Its correction adds only the newly implemented fixed BMAD resource and role/assignment resource templates to the expected sets; all body, description, CLI-equivalence and unknown-resource checks remain.

The initial integrated run passed eight scenarios and failed strict-mode fixture readiness when it attempted the final PM launch after an ended session row but before the actual process lease released. The configured capacity-one gate correctly refused that launch. A three-line test correction waits for public `dispatch agents` to report `machine_used == 0`; the strict-only rerun then passed its actual PM delivery and reconnect assertions in 66.21 seconds. Both reports remain available. This changed no runtime or prompt source and does not claim that the initial nine-test invocation was entirely green.

[runtime-traces.tar.gz](runtime-traces.tar.gz) retains 30 lossless ACP/MCP, event and runtime-record files (5,959,080 uncompressed bytes). Each member's SHA-256, assignment relationships, actual PM recipients, generated-role receipts, capacity samples and functional memory reads are indexed in [runtime-summary.json](runtime-summary.json). The cross-team recipient evidence and browser ACP transcript are retained separately in [cross-team-recipients.json](cross-team-recipients.json) and [browser-acp.jsonl.gz](browser-acp.jsonl.gz).

### Capacity and event cost

The 60-second baseline measurement used the exact original source at `10e2984...`: runner **0.00 CPU seconds**, adapter **0.00 CPU seconds**. The final committed candidate, with native orchestration enabled and a real held adapter turn, used runner **0.01 CPU seconds** over **60.000132 seconds** (approximately **0.0167% of one core**) and adapter **0.00 CPU seconds**. These are single-run observations at the host's timer resolution, not a general performance benchmark. No project queries ran during the measured interval. Raw measurements: [baseline](idle-baseline.json), [candidate](idle-candidate.json).

The event regression sends 350 unrelated events and asserts zero store reads, scheduled tasks or orchestration drains. It separately checks aggregated relevant transition events and ignores delivery acknowledgements. There is no polling scheduler for mail, ownership, handoffs or progress.

The integrated scenarios record configured project and machine capacity at recipient launches. Capacity-one cases include suspended callers, role creation, independent assessment, corrective GC work and resumed sessions. The communications scenario uses configured capacity three. The native-fork gate refuses before ACP creation at limit one, admits creation after increasing the configured limit, and refuses a later fork turn after the limit is reduced again.

### Selected prompt evidence

[selected-prompt-versions.json](selected-prompt-versions.json), reproduced by [record_selected_prompts.py](record_selected_prompts.py), records **28 selected-identity migrations** and **17 native role resource deliveries**. It contains exact selected-before/actual-after/parent IDs, rendered bodies, preserved register, source hashes and MCP receipt records. These are actual isolated prompt-store selections. No live user's prompt store or memory graph was inspected or modified.

## Reproduction

Use the repository's normal development environment. Exact package versions and adapter scope are in [environment.json](environment.json). Run fixture projects outside the source Git checkout: the existing project-history fixture detects ancestor Git repositories, so an untracked basetemp nested in the checkout fails before a scenario starts.

```sh
.venv/bin/pytest -n2 --dist load \
  src/metaform/modules/dispatch/tests/test_orchestration_runtime.py \
  --basetemp=/tmp/metaform-gc-runtime \
  --junitxml=evidence/gc-orchestration/integrated-runtime.xml

.venv/bin/pytest -n0 src/metaform/modules/orchestration/tests \
  --junitxml=evidence/gc-orchestration/orchestration-contracts.xml

.venv/bin/pytest -n0 -q \
  src/metaform/modules/dispatch/tests/test_liveness.py \
  src/metaform/modules/dispatch/tests/test_autostart_cost.py \
  src/metaform/modules/dispatch/tests/test_line_events.py \
  -k 'mid_turn or stop_ or interrupt or after_a_crash or automatic_recovery or dead_runner or completed_ticket or schema_change or autostart or recovery_keeps_ownership or burst'

METAFORM_CANDIDATE_LABEL=8c9bf81eaa6876b5dc34766574ebb1eece2a5851 \
METAFORM_IDLE_EVIDENCE="$PWD/evidence/gc-orchestration/idle-candidate.json" \
.venv/bin/pytest -n0 -q -s \
  src/metaform/modules/dispatch/tests/test_orchestration_transport.py
```

Exact retained runtime and focused memory commands are in [runtime-summary.json](runtime-summary.json). The additional concurrent-team command is in [cross-team.md](cross-team.md). Prompt/skill/MCP and actual browser commands are in [roles-prompts-verification.md](roles-prompts-verification.md). Tests use isolated homes. In this execution environment, actual threaded/ACP tests required execution outside the sandbox because a minimal independent AnyIO thread primitive hangs inside it; no application behavior was patched to mask that environment condition.

## Practical limits

- No production model executable was available in this session. Scripted fake ACP adapters establish the actual lifecycle, tools, recipient context, work transitions, files and messages. Autonomous GC/FQC judgment with Claude, Codex, Gemini or an installed production BMAD workflow remains a live-model smoke-test task.
- A generic ACP adapter can expose opaque internal children only after it has started them. Metaform enforces admission for its managed launches and integrated native fork operations. It cannot pre-admit an adapter's hidden internal execution. Externally owned editor processes retain their existing capacity semantics.
- ACP load/resume preserves the existing context when supported. Otherwise the runtime launches a fresh context with retained assignment/check-in/direction and current prompts; it cannot recover an adapter's undisclosed internal state.
- The optional BMAD bridge covers project-local manifest and installed skill entry points. Global/plugin-only installations need an appropriate provider. Availability of referenced external scripts and human-input steps remains an installation/adapter capability.
- Memory schema version 9 deliberately rejects older incompatible writers so they cannot bypass revision receipts. Running processes should use the updated module before accessing an upgraded store. This implementation does not perform the separately described destructive reset of a live project's old graph.
- Full-repository Pyright still reports the same **15 existing PyAV type errors in `modules/voice/engine.py`** on the unmodified base and candidate environment; the baseline output is retained in [pyright-baseline.txt](pyright-baseline.txt). Every changed Python implementation file passes strict Pyright. Existing unrelated prompt-text/grouped-comment checks and the root-user chmod assumption are identified in the prompt verification report; they were not silently rewritten.

The runtime and prompt implementation remained frozen during final verification. Evidence reports identify actual transitions separately from stored-record and renderer checks so each conclusion can be assessed at its observed boundary.
