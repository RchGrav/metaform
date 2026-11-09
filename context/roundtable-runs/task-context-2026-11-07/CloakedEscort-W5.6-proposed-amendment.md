# Proposed W-5.6 replacement

**Status:** Proposed for owner review. This is a concise outcome of the roundtable, not an owner decision or an implementation report. It leaves W-1.1's separation from the functional map intact.

**W-5.6 Task context selection and delivery.**

1. A task records the requested behavior, existing entity IDs or task-local placeholders for new objects, acceptance checks, and the allowed change scope. Resolve ambiguous references before edits depend on them. A placeholder does not imply that a template or a world entity already exists.
2. Select the entities and interfaces needed to explain the requested behavior. Follow port links and applicable physical/control dependencies: joints, actuator handles, sensor targets, and physics scopes. Obtain those dependencies from authoritative components or indexes; their graph representation must be implemented where it is not already present. Check WIT compatibility at each link, allowing controllers to convert between different input and output types.
3. Return relevant port semantics, intent, constraints, and connections. Stop at an unchanged component's usable interface contract; retrieve its implementation only when the task requires it. Missing semantics remain explicit unknowns. Requested behavior describes the desired result; an existing manifest describes an existing contract and must not be silently rewritten merely because the two differ.
4. Before applying proposed edits, compute their change boundary from current dependencies. Include the relevant contracts of other producers, consumers, or controlled objects whose behavior the edits may affect. A module replacement conservatively changes all exposed ports unless independent evidence supports a narrower footprint. Matching declarations or an agent's `preserved` claim do not establish behavioral conformance.
5. Push a compact initial packet at task assignment. Supply bounded detail through pull operations. Initial packets and pulls use explicit configurable size budgets; required information exceeding a budget is paged, narrowed, or split while preserving cross-page dependencies. A partial boundary is marked incomplete and is never reported as completed validation.
6. The packet includes task/target references, relevant contracts and connections, allowed edits, revision references, and explicit unresolved boundaries with retrieval references where available. Distinguish verified absence from uninspected, capped, or inaccessible dependencies. Apply the world's read permissions to retrieved content; an action handle does not by itself define every read permission.
7. Coalesce relevant definition and connection changes for delivery. Before guarded application, revalidate both selected-record versions and dependency-query membership, including newly added connections to objects previously outside the packet. Validation and application must prevent intervening changes from invalidating that check.
8. Runtime observations and acceptance evidence carry their evaluation step. Actions requiring a present condition check that condition at server execution. Structural hashes identify context definitions; they do not establish that physics state is unchanged or prove that an implementation satisfies a behavioral contract.

**Delivery proposal:** use ACP push/pull as suggested in W-11.7; choose concrete protocol operations during implementation. No exact token count, maximum pull count, temporal enum, renderer, or perception mechanism is required to adopt this selection rule.

## Acceptance fixtures

- A controller drives a door through an actuator handle and joint: context exposes that mechanism despite the absence of a direct lever-to-door port link.
- A controller converts events to boolean state: per-link checking retains the converter.
- A producer is replaced while an off-path alarm consumes its output: the alarm's contract appears in the change boundary even when the agent declares behavior preserved.
- A consumer is added after context delivery: dependency membership invalidates the old boundary before application.
- Consumer contracts exceed one response budget: the response is capped and incomplete, with continuation; validation does not silently succeed.
- A body enters a doorway without structural edits: the action's runtime guard uses current server state despite an unchanged context hash.
- Unrelated nearby content and distance changes to an existing wireless dependency do not respectively inflate or remove required context.

**Known limit:** this decides what information must be available and when it becomes stale. Program correctness still requires appropriate testing, runtime enforcement, or other verification; neither context delivery nor acknowledgements prove it.
