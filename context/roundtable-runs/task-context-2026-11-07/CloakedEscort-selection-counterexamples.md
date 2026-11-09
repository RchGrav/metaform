# Corrections to the converging path-selection proposal

Round 3 — CloakedEscort. Complements `CloakedEscort-task-context-proposal.md`.

## 1. An off-path consumer can be necessary context

Fixture:

```text
L.state:bool ──> C.request:bool ──> D (door actuator)
          └───> A.armed:bool       (alarm)
```

Task anchors are L and D. Task: make D open when L is pulled.

If the agent only adds an independent consumer to L's unchanged output, the full alarm implementation is irrelevant. If it changes L's output behavior from maintained state to a pulse to suit C, it changes the alarm too. Both edits can satisfy the door's acceptance check. An anchor-to-accept path cannot distinguish them, and excludes A in both cases.

Correction: selection has two parts:

- **Goal slice:** anchor-to-goal paths and required non-port dependencies.
- **Change boundary:** all incident connections of interfaces to be changed, including other writers, consumers, and relevant actuator/control relationships. Return their contracts without recursively expanding their implementations.

Initially, use the task's allowed change set conservatively. After the agent proposes a concrete change set, recompute its boundary before applying it. If a whole code module is replaced and has no reliable per-port dependency declaration, treat all its exposed behavior as potentially changed.

Expected context for an L.state behavior change includes A.armed's contract and an obligation to preserve it. Expected context for merely adding an independent L.state consumer need not include A's internals. Thus we preserve brevity without assuming every off-path entity is irrelevant.

## 2. WIT compatibility is local to a link

Fixture:

```text
L.pulled:event ──> C.pull:event
                  C.open:bool ──> D.open:bool
```

C converts events to a maintained boolean state. Each link is type-correct, as W-5.4 requires. L and D have different port types but are behaviorally connected.

Correction: check each stored link against its own endpoint types. Do not prune C because its output type differs from the anchor's signal. Traversing C requires a declared input/output dependency or, without one, a conservative approximation that all its outputs may depend on its inputs. W-5.3 does not currently provide a machine-readable dependency relation within a code block; free-text `function` fields are not that relation.

## 3. A dependency snapshot includes query results, not just records

At revision 10 the agent reads all consumers of L.state: only C. At revision 11 another builder adds `L.state -> A.armed`. L's manifest, C's manifest, and the original link can remain unchanged.

Checking only retained-record revisions, or watching only links whose two endpoints are already retained, misses this change. The agent may overwrite L under a false assumption about its consumer set.

Correction: version or revalidate the relevant adjacency queries and other membership predicates. For example, `consumers(L.state, adjacency_revision=10)` must become stale when a consumer is added or removed. A concrete implementation can use per-port adjacency counters, or a transactional rerun of the dependency queries before commit. If selection hit a query limit, report an unresolved boundary rather than an empty result.

Acceptance case: add an off-slice consumer after context delivery but before applying a producer behavior change. Applying the change must trigger boundary refresh and expose the consumer contract, even if no previously retained record changed.

## Recommended consolidated wording

Select anchors and the behavioral paths needed for the task; supplement them with the contracts of existing behavior potentially affected by the proposed changes. Traverse typed links and explicit physical/control dependencies, checking compatibility per link rather than imposing one signal type across a path. Deliver a bounded packet with unknown boundaries and retrieval references. Revalidate both selected records and dependency-query membership before applying changes.

Numerical budgets remain proposed tuning defaults. A fixed projection is not intrinsically bounded: arbitrary user intent, anchor counts, port counts, or WIT type definitions can exceed it. Overflow must be explicit; paging or a proposed task split must preserve cross-page dependencies.
