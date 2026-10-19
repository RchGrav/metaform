# Specialist routing and ticket inspection

Automatic ticket routing no longer defaults to `implementer`. A reusable expertise definition is separate from an operational responsibility and from the task assigned to it. The shipped framework duties declare `specialist=False`; extension and generated expertise appears in `agents_specialists` as names, purposes and `metaform://role/<name>` URLs, without loading every duty.

New tickets enter a durable routing queue. The existing event-driven starter handles one routing decision per pass, then gives other work an opportunity to run. It continues while pending routing remains, including when automatic worker execution is off. Newly filed tickets now trigger that starter: its event filter previously omitted `filed`. Stage-only records do not enter specialist selection.

When JEV is enabled for `orchestration.specialist`, selection uses ticket text, the immediate functional graph and specialist descriptions. It can choose “none”; a confident no-match now commissions the Facilitator directly. Uncertain, failed and unavailable decisions go to the ticket writer/orchestrator to select existing expertise or hand off with `orchestration_claim create=true`. On OpenRouter, an available credit observation is required before this selection. A per-ticket lock and the existing JEV answer cache prevent concurrent or repeated selection from paying again for the same decision. Unresolved tickets do not request a separate harness/model decision.

Triage is instructed to inspect the specialist inventory, name existing expertise or commission missing expertise through `orchestration_claim`. The Facilitator is instructed to write reusable domain knowledge and methods. Ticket IDs, one-off objectives, paths and return destinations remain in assignments. Worker startup binds the selected role URL before creating its model session. Existing explicit assignments retain their responsibilities; this change does not silently rewrite running agents or delete framework roles used by internal operations.

`orchestration_credits` reads the cached OpenRouter account balance and its observation time. `refresh=true` requests a current observation and requeues unresolved selections when credit is available. Lookups occur on demand, are cached for 60 seconds across processes, and subtract observed JEV request costs locally. No API key is stored. Unknown credit is distinct from exhausted credit. Other applications can spend the account balance between observations; this is an observed balance, not a provider reservation or a billing guarantee.

Board cards now open an editable inspector, with an accessible Inspect button. The inspector shows the assigned expertise or pending selection, canonical functional names, every immediate requirement and dependent through actual joins, and a Markdown graph. The same functional context is available explicitly through `orchestration_functionality work=<id>`; it is not broadcast to other agents.

Ticket title, task, note and kind can be edited. A revision check refuses stale overwrites. Reads and saves retain the project and base where the inspector opened. An edit updates the active assignment and sends its worker a short change notice; the worker reads the updated ticket when needed. The full edited ticket is not copied into the notice.

The inspector reads only the memory graph attached to its node and incident relations. Each observation is drawn as a distinct node; relationships keep their type and direction, including named endpoints outside the local attachment. The memory layer is enabled for this inspection, while node masks still apply. The existing one-fact-per-observation validation now applies to web writes too. This checks sentence form; it does not retroactively rewrite legacy prose or prove the semantic atomicity of arbitrary text.

## Operation and compatibility

- Restart running Metaform web and MCP processes to load the changes.
- Use `metaform://modules`, then `metaform://<module>/tools`, for module-owned discovery. `metaform_catalog search=<words>` provides typo-tolerant command search. The old category argument and global `metaform://tools` index are removed; extension authors remove `Verb(category=...)`.
- Specialist routing uses the existing JEV opt-in and decision settings. An empty `jev_decisions` includes all decisions; an explicit list must include `orchestration.specialist`.
- With no long-running starter, filed selections remain durable until dispatch next runs. `orchestration_route work=<id> refresh=true` explicitly retries a selection; triage can always explicitly name expertise through `orchestration_claim`.
- The new routing table is additive and uses orchestration schema version 4, compatible with the previous table layouts.

## Verification

No paid model calls were used. Provider replies and ACP agents in tests are deterministic fixtures.

The final module/routing/API integration selection passed 19 tests, including the official-SDK MCP view and an actual Chromium inspector session. The inspector test opened a board card, edited and saved it after changing the page’s selected project, and rendered both the functional and memory graphs. API tests verified stale-write refusal, assignment updates and atomic memory writes. A later routing/harness selection passed 12 tests, including bounded batches, stage exclusion, credit fallback and unrelated-event filtering.

A further 14 runtime and lifecycle tests passed, including a missing specialist being created, its role URL read over MCP, delivery of the original ticket, cross-project messaging and stop/resume behavior. The orchestration state regression selection passed its 38 existing scenarios. JEV’s existing cache and decision tests passed. Ruff and strict type checks passed for the changed production paths. The 60-second idle check recorded 0.01 runner CPU seconds and zero adapter CPU seconds; unrelated event bursts caused no reads or scheduled work. Earlier baseline and module-discovery idle measurements recorded 0.03 runner CPU seconds. These measurements establish low idle overhead, not a workload throughput claim.

See [module discovery measurements](2026-10-19-module-discovery.md) for serialized startup payload reductions and two independently reproduced baseline signal-test failures. See the [API token-waste analysis](2026-10-19-token-waste-analysis.md) for historical cost evidence. These changes do not turn byte counts into billed-token claims or establish that every remaining source of token waste has been eliminated.

## Facilitator follow-up

The registry-first workflow and its validation are documented in [the Facilitator report](2026-10-19-facilitator-handoff.md). It replaces the earlier behavior that sent every no-match result to triage.
