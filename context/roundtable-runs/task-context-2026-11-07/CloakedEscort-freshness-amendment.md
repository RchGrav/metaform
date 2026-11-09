# D-W10 v3 freshness amendment — CloakedEscort

Round 5 proposal. The consolidated draft's A7 now includes the goal-slice/change-boundary distinction. This amendment specifies what must invalidate that boundary and corrects D2's claim that content hashes alone establish runtime freshness.

## Definitions

- **Definition revision:** version of a manifest, intent record, link, or other structural dependency.
- **Membership revision:** version of the result of a dependency query, such as all consumers of one port.
- **Observation step:** simulation step at which runtime state or a test result was sampled.
- **Packet hash:** identity of serialized context already delivered. It establishes byte identity, not that the world has remained unchanged since delivery.

These serve different purposes. A single opaque context token may refer to all of them server-side; that does not make their invalidation conditions interchangeable.

## Counterexample A: unseen new consumer

Premise from W-5.4: an outbound port can have multiple inbound consumers. Premise from A7 of the consolidated draft: editing a producer requires checking affected consumer contracts.

| Time | World | Agent knowledge |
|---|---|---|
| r10 | L.state feeds C, which drives door D | Consumer query returns only C; packet hash h10 |
| r11 | Another builder adds L.state → A.armed | Old manifests and L→C link can remain unchanged |
| r12 | Agent proposes changing L.state from maintained state to a pulse | Its door check can pass while the unseen alarm changes behavior |

Because none of the old selected records must change, comparing their revisions or rehashing only their old content cannot detect the added consumer. The consumer-set query must be invalidated or rerun. A retained slice's subscription therefore watches **incident edge additions and removals**, including edges to endpoints not yet selected. The final validation and application must share a transaction or equivalent guarded operation so an edge cannot be added between checking and writing.

Proposed D sentence:

> Validate selected-record revisions and the membership of dependency queries used to compute the change boundary. An added or removed producer, consumer, grant, or applicable scope invalidates the affected boundary even when no previously selected record changed. Refresh that boundary before applying the proposed edits.

## Counterexample B: runtime state without graph edits

Premises from W-4.4 and W-8.3: physics bodies/joints evolve on simulation steps. W-3.5 separately describes persisted entities, ports, links, manifests, and intent records. No supplied requirement says every physics step rewrites those definitions or changes the task-packet hash.

At step 100, a sampled check says the doorway is clear. At step 101, a moving body enters the doorway; manifests, port links, and intent remain the same. The graph packet can still have hash h100. Thus `hash unchanged` cannot establish `doorway still clear`. If runtime deltas are coalesced until the next agent turn, even a watched change may not yet have reached the agent.

Proposed D2 replacement:

> Runtime observations and acceptance evidence carry their evaluation step and relevant entity references. They describe that step. A later action that requires a condition to hold checks it on the authoritative server at action execution, or executes through an equivalent guarded operation. Structural context hashes do not prove runtime freshness. Definition deltas, runtime observations, and historical test evidence retain distinct meanings.

A successful historical test need not be invalidated merely because another step passes: `door opened in response to pull during steps 100–110` remains evidence of that run. It is not a statement about the current door position.

## Two required checks

1. Add an off-slice consumer after context delivery, without modifying old manifests or links. A producer behavior edit must refresh its change boundary and expose the new consumer's relevant contract before application.
2. Advance physics across a required runtime condition without any structural edit. An action guarded by that condition must use its current server value, even when the packet hash is unchanged.
