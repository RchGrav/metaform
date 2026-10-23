# ACP context and orchestration implementation

This record maps the supplied `Metaform_Context_and_Agent_Flow_Audit` findings F01–F18 to the implementation, focused evidence and remaining observation limits. The preserved pre-change baseline is `977f1bfe99bdea89bd89dc8ef36807047befe6e8`. It was committed and pushed before implementation.

Metaform still uses prepared functional understanding, receiving purposes, C(T), knowledge layers and addressable context. Work records, episodes, role identity and ACP session identity serve different purposes. An episode records an explicitly chosen workstream. It does not convert the functional graph into an execution DAG or create a new capability policy. Existing dynamic blacklist, person stops, operational-role settings, dependency readiness, configured reviews and direct peer communication retain their meanings.

## Finding traceability

The evidence column names the source and focused regression coverage. A source path is implementation evidence; a test path identifies the observable contract it exercises. Neither establishes what a native harness secretly loaded or billed. Focused checks and baseline comparisons are recorded below. The broader repository checks retain historical failures, so this record makes no full-suite or release-readiness claim.

| Finding | Implemented behavior | Evidence and current limits |
| --- | --- | --- |
| F01: work identity also bounded context lifetime | Explicit episodes retain successive work records, independent results, one current binding and historical bindings. `continue_from` accepts prior work, assignment or episode identity. `fresh_context` preserves the episode while selecting reconstruction. Delayed child results keep their original caller. | [episodes.py](../../src/metaform/modules/orchestration/episodes.py), [state.py](../../src/metaform/modules/orchestration/state.py), dispatch [orchestration.py](../../src/metaform/modules/dispatch/orchestration.py) and [runner.py](../../src/metaform/modules/dispatch/runner.py). [Episode state tests](../../src/metaform/modules/orchestration/tests/test_episodes.py), [actual ACP transport](../../src/metaform/modules/dispatch/tests/test_episode_transport.py), [routing safety](../../src/metaform/modules/dispatch/tests/test_episode_safety.py). The actual fake-ACP scenario completes three cards with one new session and two loads. Reuse is explicit and depends on a suitable available session, existing resume policy and adapter support. |
| F02: destructive intent rewriting | Original requests and later source revisions remain addressable and separate from task interpretation, plans and research. Actual caller provenance distinguishes user, agent, change-order and unknown sources. Normal context carries references; exact sources remain available through `map work op=sources`. | Map [storage.py](../../src/metaform/modules/map/storage.py), map [__init__.py](../../src/metaform/modules/map/__init__.py), orchestration [specifications.py](../../src/metaform/modules/orchestration/specifications.py) and [state.py](../../src/metaform/modules/orchestration/state.py). [Source revision and provenance regressions](../../src/metaform/modules/orchestration/tests/test_orchestration.py). Historical text without established authorship is not relabeled as a user request. |
| F03: repeated selection and planning entry cost | Related continuation inherits an established runtime unless the target has its own choice. A worker can resolve local implementation detail. Separate planning remains available for actual decomposition, and returned plans are consumed without rewriting the source request. | Orchestration [runtime.py](../../src/metaform/modules/orchestration/runtime.py), [state.py](../../src/metaform/modules/orchestration/state.py), [episodes.py](../../src/metaform/modules/orchestration/episodes.py). [Specialist routing and Planner regressions](../../src/metaform/modules/orchestration/tests/test_specialist_routing.py), [episode transport](../../src/metaform/modules/dispatch/tests/test_episode_transport.py). The matched ACP measurement uses explicit runtime choices, so it does not estimate JEV cost for a novel task. |
| F04: hard exclusions and mandatory optional effort | Runtime selection retains available alternate agents and advertised effort labels. Missing effort stays absent so the adapter can use its default. Actual user choices and invalid advertised-ID errors remain explicit. | [runtime.py](../../src/metaform/modules/orchestration/runtime.py), dispatch [orchestration.py](../../src/metaform/modules/dispatch/orchestration.py) and [__init__.py](../../src/metaform/modules/dispatch/__init__.py). [Alternate agent, optional effort, cached decision and user override regressions](../../src/metaform/modules/orchestration/tests/test_specialist_routing.py), [dispatch runtime persistence tests](../../src/metaform/modules/dispatch/tests/test_dispatch.py). Existing dynamic blacklist behavior is preserved. |
| F05: every memory read forced cleanup | Memory guidance ties corrections to evidence and maintenance to useful work or an encountered defect. Canonical CRUD, atomic observations, directed relations and durable rationale remain available. An unrelated durable fact need not be deleted because it is irrelevant to the current task. | Memory [prompts.xml](../../src/metaform/modules/memory/resources/prompts.xml), MCP [prompts.xml](../../src/metaform/modules/mcp/resources/prompts.xml), [prompt regressions](../../tests/test_prompts.py). This is an instruction correction, not a claim that arbitrary model behavior was measured. |
| F06: contradictory FQC correction routes | Assessment returns the traceable findings; the existing canonical correction continuation owns the repair. Guidance no longer instructs the assessor to create an additional specialist chain for every finding. Independent outcomes can still be represented separately. | Orchestration [prompts.xml](../../src/metaform/modules/orchestration/resources/prompts.xml) and [state.py](../../src/metaform/modules/orchestration/state.py). [FQC and correction-continuation regressions](../../src/metaform/modules/orchestration/tests/test_orchestration.py). Requested or configured independent assessment remains separate from implementation. |
| F07: lexical overlap erased review findings | Reviews retain the examined task, candidate, requirement and specification revisions. Findings retain individual dispositions and stable references. Supersession needs a reason and a supported later direction/change reference. Component-name overlap and generic titles do not establish supersession or defect equivalence. | [state.py](../../src/metaform/modules/orchestration/state.py), [component overlap, review snapshot, later supersession and recurrence regressions](../../src/metaform/modules/orchestration/tests/test_orchestration.py). Code validates revision provenance; the responsible reasoning role supplies the semantic disposition. |
| F08: shaping erased selected evidence and false values | Validation runs on typed source data, followed by filtering, recursive projection and rendering. Full view honors explicit selectors. Meaningful or explicitly selected false, zero, null and empty values survive. | MCP [shaping.py](../../src/metaform/modules/mcp/shaping.py), [shaping regressions](../../src/metaform/modules/mcp/tests/test_shaping.py), [MCP server tests](../../src/metaform/modules/mcp/tests/test_mcp.py). Focused evidence covers nested dictionaries and lists, missing/null distinctions and count paths. |
| F09: native instructions required conflicting narration | Root/native wrappers and role prompts use direct outcome/evidence language instead of a universal narration or per-message rewriting ritual. Task-specific performance and protocol reference material loads when relevant. | Root [AGENTS.md](../../AGENTS.md), [CLAUDE.md](../../CLAUDE.md), native [.claude agents](../../.claude/agents), dispatch and orchestration prompt XML. [Prompt checks](../../tests/test_prompts.py), [rendered comparison](acp-audit-measurements-rendered-text.json). File presence and source size do not prove which native text a harness loaded. |
| F10: forced cancel-or-unhold plus recurring review | A justified hold is a normal waiting state. It creates no recurring deadline or model review. Legacy missing reasons receive one persisted, coalesced review. Release, completion, cancellation and removal retire pending members; upgrade retires old periodic batches without releasing valid work. | Dispatch [hold_review.py](../../src/metaform/modules/dispatch/hold_review.py), [hold regressions](../../src/metaform/modules/dispatch/tests/test_hold_review.py), [held/dependency autostart tests](../../src/metaform/modules/dispatch/tests/test_autostart_cost.py). [Matched hold measurement](acp-audit-measurements-holds.json): three actionable review requests become zero while the ticket stays held. Arbitrary prose release conditions still need reasoning; explicit one-shot deadlines use existing agent timers. |
| F11: every specialist returned to Facilitator | Prompt wording follows the recorded immediate caller/return route. Role creation prepares reusable expertise without taking ownership of every later result. Historical assignment routes remain available after a session changes cards. | Orchestration [prompts.xml](../../src/metaform/modules/orchestration/resources/prompts.xml), [state.py](../../src/metaform/modules/orchestration/state.py), dispatch [runner.py](../../src/metaform/modules/dispatch/runner.py). [Direct specialist tests](../../src/metaform/modules/orchestration/tests/test_direct_specialists.py), [delayed-return safety tests](../../src/metaform/modules/dispatch/tests/test_episode_safety.py). A compact reference may be delivered instead of duplicating the substantive result. |
| F12: marker treated as semantic retention proof | Marker checks are diagnostic and leave semantic retention unknown. A missing marker alone does not advance the context epoch. Actual observed compaction advances the epoch; explicit rereads remain available. | Agents [roles.py](../../src/metaform/modules/agents/roles.py), dispatch [runner.py](../../src/metaform/modules/dispatch/runner.py), [ID-addressed compaction observations](../../src/metaform/modules/dispatch/tests/test_compaction_observations.py), [authored-role retention tests](../../src/metaform/modules/agents/tests/test_authored_roles.py). Optional adapter signals do not reveal an inventory of retained facts, so the implementation makes no such claim. |
| F13: unrelated receipt lifecycles disagreed | Content receipts, discovery history and host configuration remain distinct. Arbitrary seven-day age no longer implies context loss. Rendered content fingerprints support deduplication across aliases and A→B→A revisions; explicit resource reads remain available. | [shown.py](../../src/metaform/shown.py), agents [roles.py](../../src/metaform/modules/agents/roles.py), [authored-role age, alias, compaction and revision tests](../../src/metaform/modules/agents/tests/test_authored_roles.py). Receipts prove accepted delivery, not hidden model retention. |
| F14: freshness required revisiting a node | Memory records which context consumed relevant content. Coalesced change references ride the next scheduled turn, preserving exact affected identities, latest revisions and withdrawals. Own writes and unrelated changes do not create notifications. Acknowledgment covers only accepted revisions. | Memory [delivery.py](../../src/metaform/modules/memory/delivery.py), [__init__.py](../../src/metaform/modules/memory/__init__.py), dispatch [runner.py](../../src/metaform/modules/dispatch/runner.py). [Delivery tests](../../src/metaform/modules/memory/tests/test_delivery.py) cover coalescing, own/unrelated writes, rereads, recreation/tombstones and a correction concurrent with a graph snapshot. The optional public provider is `agent.context.changes`; no global body broadcast or standalone freshness wake is added. |
| F15: storage ordering governed context selection | Compact receiver/purpose identities survive display fitting. Decorative detail is removed first. Explicit work links select relevant source-reference priority rather than arbitrary adjacency/storage order. The entire functional map remains addressable. | Map [__init__.py](../../src/metaform/modules/map/__init__.py), [busy-node and explicit receiver context tests](../../src/metaform/modules/map/tests/test_map.py). A compact display target does not establish sufficient understanding or authorize dropping functional identities. Production rediscovery cost remains unmeasured. |
| F16: terminology rules prohibited new reasoning | Canonical semantic definitions remain verbatim. Wrapper instructions distinguish proposed concepts or realizations from established identities and allow reasoned alternatives without silent renaming. | Map [terminology register](../../src/metaform/modules/map/resources/prompts.xml), MCP [prompts.xml](../../src/metaform/modules/mcp/resources/prompts.xml), root [AGENTS.md](../../AGENTS.md), [CLAUDE.md](../../CLAUDE.md), native role wrappers and [prompt checks](../../tests/test_prompts.py). C(T), RE/OP/PE/Join/IFD/EF definitions remain the semantic foundation. |
| F17: native role wrappers imposed audit bias | MCP/context and critic wrappers investigate the assignment's actual question, preserve supported findings even when remedy is uncertain, check authorization before calling a change a regression, and avoid arbitrary finding/ticket counts. Specialized material remains separately addressable. | [.claude/agents](../../.claude/agents), [MCP expert reference](../reference/mcp-context-expert-july-2026.md), [critic performance reference](../reference/critic-browser-performance.md), [work-evidence reference skill](../../src/metaform/skills/work-evidence/SKILL.md). Source and simulated payload measurements do not establish native reasoning cost. |
| F18: source edits missed effective instructions | Sent/role records expose shipped identity, selected/actual version, source path/kind, rendered digest, delivery path and snapshot status. Malformed selected text reports fallback honestly. Generated roles use the active selected text while retaining historical definition provenance; a portable missing-store fallback identifies its actual source honestly. Already-consumed changed role text produces compact references, acknowledged separately after accepted delivery. | [prompt_files.py](../../src/metaform/prompt_files.py), agents [__init__.py](../../src/metaform/modules/agents/__init__.py) and [roles.py](../../src/metaform/modules/agents/roles.py), [authored-role source/override/notice tests](../../src/metaform/modules/agents/tests/test_authored_roles.py), [effective-source inspection artifact](acp-effective-prompts.json). Existing assignment snapshots and authored overrides are preserved. Native files are reported as discovered candidates, not confirmed loaded sources. |

## Source and review interfaces

`map work op=add` and `edit` accept a `source` object with exact `text`, optional `reference` and optional `spans`. The actual caller supplies authorship. A relay retains the separately identified original source author and message identity rather than impersonating the user. A task revision records the current interpretation independently. Read exact source history with:

```bash
metaform map work op=sources id=<work-id>
metaform map work op=sources id=<work-id> source_id=<source-id>
```

Review assignments keep a `reviewed_snapshot` containing task/candidate/specification and requirements revisions, prior direction references and source references. Each raw finding remains attached to that reviewed revision. To explain an actual later supersession, a finding uses `disposition="superseded"`, `superseded_by=<later direction id/revision or operative/published change id>` and a nonblank `supersession_reason`. A preexisting direction, an unsupported reference or a matching component name does not suppress the finding. The normal correction/reopen path remains available for supported defects.

## Extension and observation boundaries

The fork template documents optional `Provides('agent.context.changes', provider)` through its [README](../../src/metaform/modules/fork/resources/template/README.md), [declaration guidance](../../src/metaform/modules/fork/resources/template/__init__.py), [prompt file](../../src/metaform/modules/fork/resources/template/resources/prompts.xml) and [changelog](../../src/metaform/modules/fork/resources/template/CHANGELOG.md). `pending(ctx, session)` prepares compact references without acknowledgment. `delivered(ctx, session, notices)` acknowledges the exact accepted revisions so a newer concurrent edit remains pending. The template activates no placeholder provider.

ACP session creation, loading, configuration and accepted text delivery are observable. Metaform cannot inspect or surgically remove arbitrary native internal context. Optional compaction reporting and retention diagnostics remain observations. Explicit fresh context requests produce reconstruction from relevant current state while preserving the episode and work history.

## Measurements and verification limits

[The measurement record](acp-audit-measurements.md) gives reproducible commands and scope for the initial `8df925ee` implementation. In that matched fake-ACP three-card workflow, all three records complete in both revisions. New ACP sessions fall from three to one with two loads. Adapter process starts and prompt requests remain three. Delivered prompt text falls from 29,636 to 11,829 UTF-8 bytes. Repeated exact paragraph bytes fall from 14,912 to zero. The unchanged justified hold fixture emits three actionable review requests before the change and zero afterward. Actual runner CPU over 60 seconds is 0.13 seconds in both revisions.

The separate normalized rendered-text fixture falls from 2,967 to 2,930 `o200k_base` comparison tokens at `8df925ee`. This tokenizer comparison is not provider billing. The paired fixtures have no provider usage or cache observations. A separate [authenticated native smoke](acp-live-adapter.json) succeeds with exact source/exception and artifact checks. Follow-up native-log inspection reconciles its 466,202 total tokens as 465,015 input, including 438,912 cached input, plus 1,187 output. The adapter's separately reported 26,103 input tokens are uncached input. Seventeen unique response IDs with usage establish 17 successful native model requests inside one ACP prompt. The shell CLI was `0.162.1`; native metadata identifies the adapter's bundled CLI as `0.160.1`. These corrections distinguish actual native requests and token accounting from ACP turns. Billing, provider-internal processing and hidden context composition remain unobserved. Historical fixture measurements alone do not establish useful work per billed token.

The episode and receipt contracts are recorded in specifications/11-context.md as CTX-092 and CTX-093. Stable private workspaces keep ACP cwd unchanged while preserving separate card branches and frozen candidate heads. Real Git regression evidence is in dispatch/tests/test_episode_workspace.py.

## Native inference follow-up, 2026-10-23

The follow-up measures successful native model responses and their usage, rather than treating one ACP prompt as one inference request. Evidence is in the [comparison](acp-native-efficiency-comparison.json), with per-response usage, ACP lifecycle/configuration, native context boundaries, process identities, source digests and independent application-ledger reconciliation in each arm's JSON. Private full logs remain outside the repository. Published metadata omits instruction bodies and credentials.

### Matched experiment

The [native harness](../../scripts/native_acp_efficiency.py) runs the actual registered `@agentclientprotocol/codex-acp@2.2.2` adapter and its bundled Codex `0.160.1`, using advertised `gpt-6-luna`, low effort, agent mode and Fast mode off. Each arm has a separate private Metaform home and the same initial project, protected file, three task templates, acceptance assertions and worker unittest checks. The tasks implement a scalar formatter, ordered sequence formatting and newline rendering. A rule supplied in the first exact request distinguishes `None` from meaningful blank separators, zero and false. Later tasks reference the original receipt rather than repeating that rule. All completed arms produce identical artifact hashes at each stage and pass the protected-file and functional checks.

The experiment prepares the same implementer/runtime using the existing public runtime provider with honest `benchmark` provenance. It does not forge person or Facilitator approval. Full Auto is enabled in each private experiment, Stay Connected is off, and no additional reviews or worktree transitions are requested. This isolates execution of already prepared related work. Novel-task classification, runtime selection, commissioning and independent assessment costs are excluded, not assumed eliminated.

Reproduce an arm using an existing authorized adapter launch configuration containing `command`:

```bash
uv run python scripts/native_acp_efficiency.py \
  --run /path/to/checkout --label comparison-arm \
  --output /path/to/result.json --launch-config /private/launch.json \
  --model gpt-6-luna --effort low
```

Run against preserved `977f1bfe` and `8df925ee` checkouts and this final implementation with identical settings. Candidate A's [product patch](acp-native-efficiency-candidate-a.patch) was reconstructed after its run and applies to `8df925ee`; its observed native payload hashes remain the authoritative delivery evidence. Candidate B's [source patch](acp-native-efficiency-candidate-b.patch) was captured before inference. B and later arms also record contemporaneous source and harness digests. The C checkpoint [source patch](acp-native-efficiency-final-source.patch) and [exact run-time harness snapshot](acp-native-efficiency-final-harness.py.txt) are preserved separately from the subsequently corrected collector. Later fixture-only edits do not change the production source hashes observed by inference. The final guide arm preserves its own [source patch](acp-native-efficiency-finalguides-source.patch) and [measured harness](acp-native-efficiency-finalguides-harness.py.txt), both captured before inference. The A patch is explicitly weaker provenance, not represented as a contemporaneous snapshot.

### Native lifetime and useful continuity

Every three-card arm starts three execution runners, adapters and native app-server process lifetimes and sends three ACP prompts. An additional options-only catalog prime starts and initializes one adapter/session without an observed model response; counts distinguish this setup from execution. Under these settings, completing a card ends its processes. The original baseline starts three work sessions. Episode arms start one native thread and resume that same thread twice through actual `session/resume`. The adapter maps this to native `thread/resume`; it is not a new thread reconstructed from Metaform's short transcript. There is no observed standalone model request for resume.

Native request input grows across continuation boundaries. In `8df925ee`, card one's last input is 53,153 tokens and card two's first is 53,844; card two ends at 70,092 and card three begins at 70,817. Original-baseline first inputs reset to about 23,900 tokens each card. Candidate B likewise continues from 40,119 to 40,805 and from 51,879 to 52,530. The final guide arm continues from 38,307 to 38,955 and from 54,184 to 56,631 tokens, with one targeted first-work read on card two and none on card three. These native history observations, stable thread identity and correct dependent artifacts establish actual history reuse. Processes themselves do not stay alive across cards. Keeping them alive by removing teardown would leave the MCP environment's original work binding stale, so this investigation does not add a lifecycle rewrite merely to reduce process counts.

History availability does not establish an inventory of retained facts. The prior implementation rereads the first work record on card two; B does so twice. Source and filesystem reads can serve verification and precise source recovery. No native compaction is observed in these bounded runs, so native post-compaction fidelity is unmeasured. Existing event/ID-based compaction and explicit reread regressions cover Metaform's observable contract. Review also corrected the metadata collector to recognize `compaction_update` and `compaction_summary_chunk`, retaining safe ID/status metadata. Historical wire logs cannot recover previously omitted detailed event fields; the zero-event statement is independently checked against native logs, not inferred from that omission.

### Demonstrated causes and corrections

The native smoke's first nine tool calls are dominated by gateway discovery, module loading, a mistaken gateway self-invocation and role/source retrieval. One ACP prompt contains 17 successful native model responses, not one. The first gateway-only correction subsequently regresses against the prior implementation, including a broad tool inventory lookup. This unsuccessful candidate is retained in the measurement table and is not claimed as a saving.

The final correction sends the compact gateway route and exact already-resolved pinned duty components in the first actual assigned prompt. Guidance distinguishes the host-advertised gateway handle from the target command's `tool` argument and makes discovery conditional on missing command knowledge. The role URI remains available for explicit rereads. This removes demonstrated bootstrap discovery/refetch work at its cause, without sending unrelated roles or preloading a tool inventory. Delivery uses the existing accepted-component ledger, including exact selected versions, rendered bindings, retry behavior and unchanged-content deduplication. The wrapper itself now resolves `prompt.dispatch:role_resource`, correcting its false orchestration source identity, which already existed in `977f1bfe`. Resume does not blanket-replay the duty.

Automatic marker checkpoints were diagnostic, yet their instruction could prompt an `agents_confirm` tool exchange on each start/resume. B actually invokes it. Ordinary work no longer requests that exchange. Explicit diagnostic methods and public APIs remain available, and actual compaction observations still advance context epochs. No useful execution or reasoning request is suppressed.

Work-tool guidance now permits direct verified completion when a stage count adds no value, consistent with existing MAP-053 behavior. Plans, stages, progress, blockers and decisions remain available where useful. The matched prior implementation already makes no plan/step calls, so this wording correction is not credited with measured savings.

Two functional regressions receive focused corrections. `map_work` now advertises `sources` in its MCP enum as well as implementing it, verified through CLI discovery and exact MCP source reads. Changed-role notices now advertise `agents_resolve` to reach the current selected source; the authored role resource deliberately continues to serve its pinned assignment snapshot. An actual MCP-resource regression proves both behaviors without silently rebinding the assignment.

The final trace investigation also establishes a discovery defect: module catalogs expose brief signatures, while the existing `metaform_instructions` guide omits nested JSON argument shapes. The native memory retries and a separate observation-write attempt encounter missing `entityName`/`contents` or entity fields without that schema being discoverable in the guide. The existing explicit single-command guide now includes its canonical `inputSchema`, including nested types, required fields, constraints and descriptions. Module listings carry a compact optional pointer using the actual gateway invocation. Automatic first-use guides and lazy module discovery stay compact. No new command, required help stage or validator bypass is added. Conditional new-entity `why` and duplicate-create idempotence remain unchanged. A real public-guide regression covers both memory commands; the existing operation-filtered prose-help contract also passes. The explicit JSON schema describes all fields of the requested tool; an `op` filters its prose, not that schema. Dynamic withheld surfaces and hidden operation/argument filtering remain in the canonical schema builder. Explicit help retains its existing known-name accessibility, including tools whose execution a role cannot use; execution authorization is unchanged. This corrects discoverability without requiring agents to request help. Native call-count improvements cannot be attributed to this explicit branch unless a trace actually invokes it.

### Accounting and limits

Native `input_tokens` includes cached input. Uncached input is input minus cached input. Per-response `token_usage_record` and `token_count` are duplicate reporting streams; the harness deduplicates native `(thread_id, response_id)` and sums one stream. Reasoning output is a subset of output, not another addition. Each arm's three application spending rows independently reconcile with native input, cache, output and total sums. Cost fields are unavailable, so no dollar or billed-saving claim is made.

Native request totals include observable automatic harness context. Global base instructions are 21,556 bytes with the same digest across arms. Developer payloads include roughly 31,850, 2,429 and 271 bytes, plus environment/project instructions of roughly 5.8 kB. The C checkpoint native resumed turns additionally inject developer `<skills_instructions>` blocks of 7,570 and 11,087 bytes (26 and 36 skill entries). Those later developer blocks are absent from the B/prior observations, although each initial catalog has 36 entries. Later Metaform user payloads remain only 1,697 and 1,700 bytes. This is observed automatic native context variation, not Metaform replay, and limits isolation of the diagnostic change. The final guide arm instead has one additional 7,570-byte, 26-entry catalog before card three, removing ten curated plugin entries without the later restoration seen in C. The cause of native plugin availability variation is unestablished. These are observable payload measurements, not per-component token attribution or proof that nothing else is injected. Provider-internal retries, failed requests without usage and hidden context handling remain unknown.

This is one bounded sample per implementation in a small private code project, not a statistical estimate or a measurement of every repository-specific native instruction set. Native decisions vary, shared cache warming may favor later arms, and original/prior runs overlapped. An authority wait also affects elapsed time, so wall-time savings are not claimed. The failed A candidate shows why reduced explicit text or a routing hint alone does not prove inference efficiency. The observed measurements are:

| Implementation | Native model requests | Input, including cache | Cached input | Uncached input | Output | Native work sessions / resumes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| [Original `977f1bfe`](acp-native-efficiency-original977f.json) | 96 | 3,834,562 | 3,655,552 | 179,010 | 7,668 | 3 / 0 |
| [Prior `8df925ee`](acp-native-efficiency-prior8df.json) | 55 | 2,729,731 | 2,628,992 | 100,739 | 5,808 | 1 / 2 |
| [A: gateway hint only](acp-native-efficiency-fixedcurrent.json) | 61 | 3,209,539 | 3,040,000 | 169,539 | 5,724 | 1 / 2 |
| [B: pinned duty and revised guidance](acp-native-efficiency-candidateb.json) | 33 | 1,390,982 | 1,322,368 | 68,614 | 4,371 | 1 / 2 |
| [C: explicit-only diagnostics and receipt correction](acp-native-efficiency-finalcurrent.json) | 45 | 2,569,790 | 2,481,792 | 87,998 | 7,040 | 1 / 2 |
| [Final: C plus on-demand nested argument guide](acp-native-efficiency-finalguides.json) | 37 | 1,753,826 | 1,675,264 | 78,562 | 4,712 | 1 / 2 |

The final sample uses 32.7% fewer native model requests, 22.0% less uncached input, 35.8% less total input and 18.9% less output than `8df925ee`. Against `977f1bfe`, requests fall 61.5% and uncached input falls 56.1%. All functional outputs match. This is verified improvement in observed native execution for the measured useful work, with billing and generalization limits above. The final trace does not invoke `metaform_instructions`, so it does not establish native causal savings from the new explicit guide branch. That correction has separate public-API coverage. The final sample remains worse than B, and no stage's incremental savings are statistically isolated.

The C checkpoint sample uses 18.2% fewer model requests, 12.6% less uncached input and 5.9% less total input than `8df925ee`. Output increases by 1,232 tokens (21.2%). Against the original baseline, requests fall 53.1% and uncached input falls 50.8%. All three functional artifacts and acceptance checks match across all six arms. This establishes an observed improvement in native execution requests and input for the measured useful work, without establishing billed savings.

The C checkpoint sample is worse than B despite removing automatic marker requests. It uses extra context/resource discovery and five memory-create attempts. Four are rejected for missing `entities`, using `type` instead of `entityType`, missing the new-entity `why`, and a compound observation; the fifth succeeds. There are no duplicate successful creations. Validation remains intact rather than being bypassed to lower request counts. No `agents_confirm` invocation appears in C or the final run. Removing that demonstrated redundant instruction is justified, but its marginal token saving is not isolated or claimed. Candidate B's longer initial Metaform delivery (17,356 bytes versus 10,027 on `8df925ee`) and lower inference totals also show why explicit prompt size alone is an inadequate success metric.

### Follow-up verification

- All 18 native work items across six arms pass the external behavior assertions, worker unittest checks and protected-file check. Each corresponding stage produces the same artifact hash.
- The final focused transport/role/compaction selection initially reports 52 passes and four stale fixture failures. The exact four corrected cases then pass in 123.80 seconds, with fixture-only corrections. The later nested-guide correction is validated separately and included in the final native source snapshot.
- All ten final orchestration-runtime cases pass in 372.86 seconds, covering nested specialist returns, generated-role reuse, GC commissioning, BMAD role/source delivery, explicit compaction rereads, user stops, adaptive/strict review and peer delivery/restart.
- Nine functional cases pass in 35.35 seconds: adaptive publication, strict current user direction, strict source provenance, exact CLI/MCP source history, dynamic catalog exclusions, related-card runtime reuse, CLI consent boundaries and actual-default reset behavior.
- Two final public-guide/op-filter cases pass in 4.63 seconds. Whole-project Pyright is rerun after that correction and remains at zero errors and warnings.
- Four first-prompt acceptance/retry cases pass, checking the selected gateway and role wrapper source, pinned duty bindings/body, version receipts and unchanged-content suppression. Explicit marker diagnostic and ordinary no-checkpoint behavior are covered separately.
- Whole-project Pyright reports zero errors and warnings. Ruff passes for all changed Python files, including the native harness. `git diff --check` passes for implementation, tests and documentation, excluding the preserved raw `.patch` evidence whose standard blank context lines contain one space. Those snapshots retain their exact recorded bytes. Immutable root semantic definitions match `977f1bfe` verbatim. Review links and ACP JSON parse checks pass.

### Follow-up failure triage and functional scope

[The baseline artifact](acp-baseline-checks.json) records the follow-up's case-by-case comparisons. Full-repository Ruff has 51 diagnostics versus 52 on `977f1bfe`; CI's `src tests conftest.py` scope has seven versus eight, with no introduced diagnostic in either comparison. Unrelated historical annotation-registry, memory-apply alias/schema, packaging/demo, first-run and other recorded failures remain outside this repair. There is no repository-wide green claim.

Three CLI tests failed on both the original baseline and `8df925ee` because they assumed the old Jev default. They now capture the actual default or explicitly establish the opposite setting before testing unauthorized mutation. Production permission checks are unchanged. The MCP resource registry assertion now includes the existing body-free `metaform://specialists` URI and retains its exact resource/template/read checks. Provider error and cancellation tests now use a real command context, reach the actual mocked ACP request, and assert exact prompt delivery rather than failing earlier in an incomplete fake context.

Current transport fixtures must accumulate inline duty text with resource responses, since the accepted-delivery service can correctly omit an unchanged body on a subsequent read. Assertions for initial duty delivery and changed-source references are adjusted to the corrected contract, retaining exact body, receipt, assignment and current-source checks. No checks are skipped to obtain a passing result.

Exact source history, C(T) and functional identities remain independent of summaries and plans. Adaptive specifications, current user direction, direct peer return routes, human-message ordering, cancellation and dynamic blacklist behavior retain their existing implementation. The focused checks below cover those contracts; native formatter acceptance also checks meaningful false/zero/blank values, generator order and the protected-file exception. No schema transition, mandatory stage, policy gate or additional classifier is introduced.

## Purpose context and tool instructions follow-up, 2026-10-23

This subsequent change starts from `27b77cae`. The native measurements above
predate it. No new native model run, token comparison, cost measurement or
inference-saving claim accompanies this follow-up.

### What agents actually received

The existing `functional_context` renderer already supplies direct requirements
and dependents as a Mermaid diagram, stable node identities and RE-owned OP,
PE-specific EF and IFD descriptions. The ordinary assignment handoff previously
sent a compact task, state, notes, a limited purpose summary, counts and resource
pointers. The fuller region was available through a later read rather than
included in the actual assignment prompt.

Fresh and related-card worker assignments now include that existing rendered
region and an address legend on their first actual turn. This uses the accepted
component ledger: preparation acknowledges nothing, failed delivery retains the
exact content for retry, unchanged context is suppressed, and a changed region
is eligible at the next assignment. Human-message order and source instructions
remain intact. It adds no model turn, classifier or planning stage. The renderer
still describes direct relationships, not a complete transitive dependency
closure, neighboring task-state inventory or inferred architectural boundaries.

Shared connection rules now ask agents to record intended functionality and
purpose while planning or assigning it, including source and unresolved details.
Existing fresh ACP turns already received shared rules; moving them into the
common selected-component preparation path corrects consistency and receipt
handling, rather than demonstrating their prior universal absence.

### Construction, planning and knowledge

`metaform://map/construction`, also available through `map guide`, serves an
adaptation of the intake for existing-map operations. The actually served
Canonical Intake is `intake.axiom`. Its construction declarations, constraints,
validity conditions and root-trace invariant are retained verbatim. The original
`intake.xml` contributes separately identified definitions, fuller naming rules
and valid/invalid examples. The guide records both exact source digests and the
selected wrapper identity. Neither intake source nor protected root instruction
files was edited.

The same final coverage check found that initial intake tools had declaration
help but no receipt for the actual intake procedure. Intake now contributes its
project-bound procedure body before start, element, purpose, remove and finish
operations. Its existing resource read queues that exact body. A dispatched
intake's first turn can acknowledge the procedure already present in that turn
after transport acceptance, without delivering it twice. Appended request and
mode data do not invalidate an unchanged source-body receipt.

The current project's `intake_file` override is unset. A configured intake file
is respected by the initial-intake contributor, with its own source digest and
project bindings. A custom XML procedure whose middle `{prompt}` binding changes
the body cannot acknowledge an undelivered empty variant; an explicit matching
read through the combined tool-instruction URI remains necessary. A separate
procedure-read pointer is omitted for sources with such slots, because active
launch-mode data can also change that resource's rendered body. Missing or
invalid UTF-8 configured files return the ordinary error and next step during
preflight, with no target effect or delivery receipt. The existing-map guide
derives the shipped intake's
grammar and identifies that source separately from a custom intake procedure.

Base naming and valid/invalid distinctions stand. Proposals and unresolved design
belong in an explicitly named CEL constrained to its declared question or
variable. Established planned base construction must satisfy the same grammar
and RE/OP/PE/EF relationships as existing functionality. Part state remains
outside C(T). The public `map_work` path now accepts no-task `unbuilt` and
`under-construction` states already supported by storage. They remain visible
non-work records and do not distribute, autostart or continue an agent.

Seven current planning intentions were recorded in `planned_capabilities`,
finished and selected at `code`: provider integrations, service discovery,
provider configuration, provider templates, interactive previews, harness setup
and media generation/editing/integration guidance. Their [export](planned-capabilities.json)
retains purposes, proposed encounters, source references and unresolved details.
Their `unbuilt` value is knowledge, not seven independently staged base elements
or executable assignments. Six bare base additions made prematurely during this
investigation were removed through versioned refinement after preserving their
intent in this layer. Existing user-configured authority controls, stops,
budgets and dynamic blacklists remain in force. No blanket role restriction was
removed.

### Instructions before tool execution

The owner explicitly chose a common prerequisite for tools with specific usage
instructions. The old successful-result guidance arrived after the operation.
MCP now requires current applicable instructions before the target executes.
Discovery advertises `metaform://tools/<tool>/instructions[/<op>]`, with
`metaform_instructions tool=... op=...` as the equivalent gateway route.
An unguided attempt returns `instructions_required`, `executed=false` and a
concrete read route. It does not perform the requested target operation.

The existing declarations supply tool usage. Shared module rules and optional
`agent.tool.instructions` contributions compose with it. The map contributes its
intake adaptation through that same contract. The canonical nested argument
schema has its own exact receipt, so a schema-only edit cannot silently retain
permission based on unchanged prose. Shared components deduplicate across tools,
operation-specific bodies remain distinct, and only complete content surviving
response shaping is acknowledged. Review found and corrected both the
schema-only mismatch and a fallback receipt gap for module-owned resource reads
when the agent-context service is unavailable.

Unnamed stdio and stateless clients can use the existing logical-context handle
across server replacement. Named dispatch and gateway identities take priority.
During live development, source reloads changed process identities, initially
making delivered guides appear unread. A stable handle resolved that identity
boundary without another onboarding operation. Live gateway reads and retries
successfully performed the six versioned removals and layer finalization.

Discovery, instruction reads and tools without specific instructions have no
instruction prerequisite. Existing schema validation and explicit user controls
still apply after delivery. A receipt proves observable delivery, not model
comprehension or semantic retention. This change enforces the MCP execution
surface; arbitrary CLI commands and filesystem writes are not constrained by it.
The chassis's CLI map/archive imports likewise remain outside this MCP check.
The fork template documents the provider contract without installing a dummy
provider. Specifications MCP-044 and CTX-094 record the current requirements.

The resource investigation also corrected three retired prompt identities in
MCP reads: shared rules, memory instructions and glossary now resolve their
canonical `prompt.<module>:<name>` addresses. Clean-store resource reads no
longer depend on historical aliases.

### Verification of this follow-up

Focused checks cover actual MCP stdio and HTTP calls, gateway aliases, no target
effect before instruction delivery, selected source changes, schema-only changes,
operation isolation, context and handle isolation, compaction, response shaping,
shared construction/module components, missing agent-context service and
unregistered projects. Dispatch checks cover actual outgoing regional content,
acceptance/retry receipts, related-card changes and exact human-message order.
Public map checks cover visible non-work stages without automatic execution.
The check results below describe this follow-up separately from the historical
native experiments.

- All 29 intake-guide and direct-runtime cases pass in 143.07 seconds.
- Four public stage/work/default-eligibility cases pass in 11.18 seconds. Two
  configured-authority and dynamic-withholding cases pass in 5.89 seconds.
- The focused MCP prerequisite/resource suite passes 25 cases in 46.36 seconds;
  its additional public resource/fallback regression passes in 5.63 seconds.
  These runs overlap other focused source checks and are not summed.
- Nine final intake receipt/source/error cases pass in 26.19 seconds. The wider
  intake run had 76 passes and one obsolete unguided MCP fixture failure; that
  fixture was migrated to explicit reads, preserving its report-path privacy
  assertion, and passes separately. Four additional direct/actual-stdio
  source-error checks pass in 7.86 seconds, including aliases and resource reads.
- Whole-project Pyright reports zero errors and warnings. Ruff passes for all
  changed Python files, including new guide code. XML parsing, the seven-record
  export checks and `git diff --check` pass. Protected root instructions and both
  intake sources have no diff from the starting commit.
- Independent bounded review found no remaining concrete prerequisite bypass,
  deadlock or receipt mismatch after the corrections above, including the final
  intake source-error and custom-URI rechecks. This is not a
  proof of model comprehension or a repository-wide green-suite claim.
- CI-scope Ruff still reports seven unrelated diagnostics in the archived page
  smoke script, `test_ticket_fast_ui.py` and `test_zz_diag_tmp.py`. All three
  files are unchanged from `27b77cae`, establishing that these diagnostics
  predate this follow-up. They were left outside this repair. Earlier unrelated
  suite failures remain documented in the historical baseline artifact; this
  follow-up does not claim a fresh full-suite classification.

Existing MCP-039 fixtures required migration from implicit instructions after
success to explicit MCP-044 reads before use. Simulated informed clients now
follow one actual prerequisite response and retry the original operation; raw
prerequisite tests continue calling the wire directly. Six raw enforcement
cases pass after that helper change. The existing synchronous-task cancellation
fixture now waits for actual handler entry before asserting completion after
cancellation. The unchanged baseline case passes, and current pre-entry
cancellation correctly performs no work. This was a fixture timing assumption,
not a production cancellation defect or justification to suppress cancellation.
Ten existing guide, operation-filter, nested-schema, resource-registry, consent,
task, compaction and stateless-HTTP scenarios pass across focused runs. The
[baseline record](acp-baseline-checks.json) retains the exact migration results,
including the obsolete assertions corrected and the separate final-case rerun.

## Continuation: missed prompting and Pro handoff, 2026-10-23

The prior assignment was completed and committed: native efficiency work at
`29cd88bd`, followed by purpose context and MCP instruction prerequisites at
`f63cc2e5`. Substantial context-management work was nevertheless ignored by that
last task. It did not systematically migrate existing prompting or reorganize
roles, specialties and skills around useful context reuse. This preparation
continues the same assignment, repairs demonstrated prompt defects and hands
the broader reorganization to the user's existing Pro web context.

The [Pro handoff](context-management-pro-handoff.md) retains exact current user
direction, the prior scope, decisions still open, source locations, migration
constraints and an actual native-efficiency evaluation plan. Its
[execution appendix](context-management-pro-execution.md) distinguishes prompt
resolution, skill loading, assignments, workflow run records, process starts,
ACP/native sessions and actual model requests. It proposes classifications
without implementing or silently approving the future taxonomy. The live
[6/23/39 inventory](context-management-role-inventory.json) and selective
[role source snapshots](context-management-role-samples.json) make local
project/home data available to a GitHub-only reviewer. The preparation also
exports [all 62 current duty resolutions](context-management-current-duty-sources.json),
storing shared bodies once with a line index for selective inspection.

### Corrections made now

| Missed problem | Correction |
| --- | --- |
| Base skill and chassis guidance said instructions were already in context and assumed a particular tool exposure shape. | Use the actual advertised direct tool or gateway, compact catalog discovery, returned `read_tool` route and the existing logical-context handle. Receipt establishes delivery. |
| Module/tool headings, compaction and handle prompts promised once-per-session or after-use guidance. | Describe explicit pre-use reads and current content/context receipts. Reuse unchanged components rather than claiming all guidance is already available. |
| Assigned agents were told to reread exact duties already delivered. | Use supplied pinned components, with source retrieval when absent or relevant. Do not replay every role. |
| System guidance required every no-task record to acquire work or close. | Preserve visible non-executable planning stages. |
| Routine peer messages were promised on a later model turn. | Describe their actual record/UI availability and distinguish actionable delivery routes. No transport behavior changes here. |
| Builder/evaluator procedures required tests or fresh evaluation for every modifying pass, and routine checks required advance narration. | Select evidence for requested acceptance, material risk and explicit requirements. Retain requested independence/configured checks without blanket per-edit stages or narration. |
| Skills treated a copied command reference as an exhaustive list. | Current module/command declarations are authoritative. Preserve the prohibition on invented or unavailable commands without blocking valid extensions. |
| Workflow handoff text promised native continuation without a demonstrated binding. | Restore the usable resume command and state that a run/handoff record alone does not launch or bind a recipient. Actual caller/host execution remains a separate integration question. |
| Scan descriptions claimed every skill invoked it first. | Describe optional scanning according to the actual procedure and keep canonical metadata and slash summary consistent. |
| System prompting prohibited native children using a false total-invisibility claim. | State adapter-dependent observation and parent-mediated messaging; follow user delegation preferences and retain accountable work/results/return routes. Full stop, accounting and assignment parity is not claimed. |

The original immutable glossary and both Canonical Intake sources remain
unchanged. Functional purpose, exact user source, C(T), adaptive specifications,
communication and existing explicit controls are retained. Broad duplication
of procedure libraries, duty categories and workflow grammar remains for Pro,
rather than being removed without an execution/source migration design.

### A source-delivery defect behind the missed migration

Older generated specialties stored legacy prompt names such as
`orchestration:common`. The prompt database could resolve their selected
history, but legacy-name source discovery did not independently refresh changed
shipped common text. A canonical lookup elsewhere could hide the defect. It
also obscured definition-source provenance and could duplicate a legacy
specialist component.

Two isolated cases first reproduced the defect in 1.97 seconds. A read-time
normalization in `agents/roles.py` now resolves generated module references by
canonical address. Existing same-context/epoch legacy receipts and accepted
change notices remain usable only with the exact content fingerprint. Selected
common/duty edits, generated definition/history, historical receipts and pinned
assignment bytes are preserved. No schema migration or bulk user-body rewrite
was introduced. Changed bodies and new context epochs remain due.

Independent review then reproduced a coexistence edge: an older canonical
receipt could mask a later accepted legacy-name body in the same epoch. Five
focused cases failed before the correction. New writes now normalize supported
prompt receipt identities while retaining original component metadata. Parsed
UTC acceptance order and conservative conflict handling govern historical
aliases. Untimed reference-dedup state is normalized only after an actual
accepted notice. Dynamic non-prompt component names retain their exact
identities. No historical body receipt is deleted or rewritten.

The [source-state record](context-management-source-state.json) includes actual
fresh generated-role resolution after this correction and six current selected
skill procedures. It establishes source selection, not delivery to a running
assigned agent. Custom selected edits, trials, fallbacks and pinned snapshots
are not indiscriminately replaced.

Two known local native base-skill files still contained an older per-module-tool
bootstrap. Both were verified byte-for-byte against shipped `c7ca35b5`, backed
up through the install backup helper and refreshed to the corrected repository
base skill. The record preserves before/after hashes and backup locations.
Broader native skill deployments, customized files and harness registrations
were not changed. Already loaded native instructions are not surgically
replaced by this file refresh.

### Evidence and limits of this continuation

- Thirty-one focused runtime prompt/source/receipt checks passed. Six additional
  existing native-child/system-prompt checks passed in 13.24 seconds, using fake
  adapters rather than new native inference.
- Forty-five prompt-migration and MCP-skill access checks passed in 25.91
  seconds. A broader related selection initially had 28 passes and three
  failures. One scan-summary mismatch was introduced by this correction and
  fixed. Two stale metadata fixtures predated this continuation: they omitted
  already-discoverable `work-evidence` or assumed comment-header metadata
  instead of authoritative SKILL frontmatter. The final five affected checks
  passed in 11.21 seconds with exact registry/discovery/content assertions.
- The earlier workflow diagnostic had one pass and two failures in 5.47 seconds.
  The missing usable resume text and old unguided MCP test client were repaired
  in the related prompt/fixture migration, preserving frozen text, private
  return scope and once-per-assignment library order/content assertions.
- The agents suite initially passed 38 cases after the source-reference fix.
  Following the independent mixed-alias finding, the final suite passed all
  44 cases in 34.62 seconds, including precise chronology, equal-time conflicts,
  current epochs, source/metadata preservation and dynamic-name identity.
  These runs overlap and are not summed.
- Whole-project Pyright reports zero errors and warnings. Changed Python files
  pass Ruff. Prompt XML, metadata/JSON and local evidence links are checked.
  The earlier seven unrelated CI-scope Ruff diagnostics remain outside this
  task; no whole-repository green claim is made.
- [Nine-skill text measurements](context-management-skill-bytes.json) use a
  temporary home without overrides. They are UTF-8 source/rendered bytes, not
  model tokens, accepted native delivery, cached input or billed cost. Some
  procedures include 24–35 kB of libraries. Simply converting a role into a
  skill does not make that content free or eliminate repeated library loads.
- No new paid/native inference experiment was run. The earlier native results
  remain attributed to their original source and workloads. Current tool
  prerequisites, Fac commissioning and the proposed skill conversion have not
  been isolated in a new matched inference-cost comparison.
- GitHub repository access works, but an authenticated read of exact local
  `f63cc2e5` returned “No commit found for the ref”. The handoff therefore
  includes a portable source/evidence snapshot. A default-branch read must not
  silently substitute older code for this implementation.

CTX-095 and amendments to BASE-054/055/056 and D116/117/118 record the current
owner direction so historical blanket-builder and blanket-verification text
does not regain authority. D124 retains the mechanisms still open for Pro.
Current planning remains ordinary knowledge in its named layer, exported in
[the planning snapshot](context-management-planning-intent.json). The broad
role/skill reorganization is explicitly unbuilt.

## Initial implementation verification (`8df925ee`)

Checks ran on Linux with Python 3.13. Passing counts below describe separate runs with overlapping coverage and must not be added together.

- A combined regression run passed 266 cases across episode transport, real Git workspaces, historical return routing, compaction observations, holds, assignment state, role delivery, memory delivery, result shaping and prompt migrations.
- The final runtime/direct selection passed 18 cases: ten orchestration runtime scenarios, three direct ACP start scenarios, one resumed-human-priority regression and four first-turn ordering/receipt cases. It exercises nested specialist returns, generated role reuse, installed BMAD roles, compaction recovery, user stops, strict and adaptive review routes, live peer collaboration and caller-process recovery.
- The final full orchestration transport file passed 63 cases with one skip, including fresh/resumed/crashed caller continuations, review-finding ownership and strict recommendations restricted to their recorded responsible caller. Recommendations remain proposals rather than operative changes.
- Prompt, universal-skill and functional-map context checks passed 31 cases. Three memory schema-upgrade cases passed while preserving their exact entity, relation, join, note, ordering and compatibility-floor assertions.
- Specialist routing checks passed all 110 cases. Runtime regressions verify that explicit continuation retains consumed planning evidence across three cards, while an explicit new planning choice creates its own planning contribution. Source revision and original Planner assignment identity remain attached to the retained evidence.
- After the final startup changes, both episode-transport and direct-runtime files passed all 11 cases. These cover actual three-card reuse in shared and private workspaces, specialist commissioning, the current card's context preceding any action, exact human-message FIFO and metadata, preacceptance failure, and receipts matching the actual selected/source/rendered versions. Startup context and its receipts ride the first actual turn rather than a separate model request.
- Immutable semantic definitions in both root instruction files match the preserved baseline verbatim. Local documentation links and `git diff --check` pass.
- The final whole-project Pyright check reports zero errors and warnings. Ruff passes for all changed Python files.

The initial default-discovery run stopped after 15 failures, with 386 passes, one skip and one collection error. Its failures and collection issue were reproduced against the preserved baseline. Broader module sweeps also stopped at their failure limits. The owner-module sweep had 424 passes and 12 failures: six historical failures, five stale fixture expectations subsequently corrected, and one startup race subsequently fixed. [The baseline comparison artifact](acp-baseline-checks.json) records exact cases and commands, including historical annotation registries, incomplete fake-agent runtime fixtures, missing historical prompt references and a web-test import collision. Global Ruff retains seven existing diagnostics; changed Python files pass Ruff. These limits are explicit rather than treated as a green repository-wide result. The full browser and operating-system CI matrix was not run locally.

The wider sweep also exposed a startup race: a fresh session could publish idle before its initial brief was ready, letting a human message run before a later unowned brief turn. Startup now queues messages until that brief is assembled, reports working during assembly, and keeps the original human turn and authorization attached to the first actual prompt. Five final startup/FIFO/consent checks pass, including the unchanged system-agent authorization test and a deterministic early-message ACP case. Existing authorization controls remain unchanged.

## Specialist resource namespace migration

The scoped namespace change separates reusable domain expertise at `metaform://specialist/<name>` from
procedural responsibilities at `metaform://role/<name>`. The 23 procedural definitions remain roles; the shared
`metaform://role/specialist` duty is unchanged. The connected MCP specialist roster returns 39 entries with the
new canonical prefix. Classification follows `AgentRoleDefinition.specialist`, including installed BMAD entries,
without changing their instructions. The two assigned runtime prompt edits change only domain URI tokens.
The web picker keeps procedural roles and specialists in separate groups and uses each supplied URI for
inspection and calls.

SQLite backups were taken under `~/.metaform/backups/specialist-namespace-20261023T212745Z` before the live
metadata migration. It updated 26 assignment records, 26 routing records and 156 published role-request source
metadata records, with zero pending launches changed. A second pass reported zero changes in every category.
Full row comparisons preserved all nonidentity fields, including states, tasks, stops, return routes and
instruction components. Read-only fingerprints matched before and after for all 39 definitions, 39 definition
history rows, 39 generated prompt records and 41 prompt versions.

Local verification passed 120 specialist-routing/direct-specialist cases and four BMAD/web cases. The web
case uses the public registry, keeps its 23 procedural entries, exposes generated expertise separately and
passes the selected specialist URI to the managed call. The BMAD case retains its source, version, menu and
selected-edit assertions. Its previous missing-caller failure was reproduced against archived `7be121e9`
source in a temporary home; the fixture now explicitly claims and binds its GC rather than changing runtime
authority. Changed-file Ruff, scoped Pyright, JavaScript syntax and exact prompt-byte comparisons pass.
These are namespace, preservation and local execution checks, not inference-efficiency measurements. No paid
model run was performed for this migration.

The authored-resource and namespace selection passed 36 cases, including separate discovery, rejected old
specialist URLs, exact selected edits and shared delivery receipts. Four namespace cases also exercise pinned
assignment reads before and after legacy-reference migration. Twelve focused operational cases preserve stopped
assignments, publication retries and historical evidence while migrating operational identity fields.
These selections overlap and are not added together.

The managed specialist creation/return/reuse scenario passed through real runner subprocesses and a fake ACP
adapter in 113.93 seconds. Its fixture now follows the existing read-before-use instruction response and uses
the actual authored URI rather than rebuilding a role URL. The initial fixture failed on `instructions_required`
before executing its specialist call. Whole-project Pyright reports zero errors and warnings; changed Python
files pass Ruff. The existing swap file and the stashed, abandoned Pro-repair attempt remain untouched.

A focused Chromium picker run passed the separate-group, canonical selection, installed-menu and source-path
assertions, then timed out waiting for the fake adapter's first prompt. Its full browser launch path remains
unverified. No production change was added to bypass that fixture's commissioning/runtime setup; the separate
managed creation/return/reuse scenario above passed through the actual runner transport.
