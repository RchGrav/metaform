# BluntDiode: select dependencies, then render a task packet

Round 1 proposal for D-W10. All additions below are proposals, not owner decisions.

## Selection contract

The server should answer a specific question: **What facts must the agent know to change these objects without breaking their existing obligations?** A radius search or fixed number of graph hops cannot answer that reliably. Wireless dependencies can be distant; a nearby object can be unrelated.

Start with a task record containing the requested behavior, explicit entity references, allowed changes, and any acceptance conditions the player supplied. Resolve references to persistent IDs in this world. Prefer objects selected by the player, then exact references, then search candidates. Search ranks candidates; it does not silently decide which of several doors the player meant. Return a short ambiguity list if binding is unresolved. Mark an object the task asks to create as a creation requirement; do not fabricate an existing ID.

For each bound object, select the ports and state relevant to the requested behavior. Include its relevant user intent and its manifest's behavior description. Preserve disagreements between the task and stored intent as a conflict; do not silently choose an interpretation. Explicitly distinguish declared behavior from observed state.

Follow dependencies of those selected interfaces, rather than every edge of each entity:

1. Include incoming producers and outgoing consumers attached to a port the agent may change. This includes other consumers of the lever's output: changing that output's meaning could affect them too.
2. At an entity whose implementation is outside the requested change, include the required port contract and stop. Expand its internals only if the task changes it or available evidence makes its behavior uncertain.
3. Include physical attachments and granted control targets used by the changed behavior. A motor handle can be relevant even when no bus link reaches the door mesh.
4. Fetch additional spatial or physics facts only when the operation needs them: hinge limits for setting a rotation target, or a bounded swept-volume query for moving a door. Do not load surrounding terrain by default.

The current graph explicitly describes port links (W-5.4), but joints (W-4.4) and granted handles (W-7.4) also determine behavior. The context query therefore needs indexed lookups for these existing relationships, whether stored as graph edges or joined from components. This does not introduce an in-game functional-map namespace.

## Budget and delivery

Render a compact structured packet with:

- Task and bound IDs, including objects to create.
- Selected entities: ID, relevant intent, selected ports with direction/type/meaning.
- Relevant links, physical/control references, and constraints.
- Unresolved questions, omitted dependency frontiers, and scoped expansion references.
- Snapshot reference and record revisions, so later edits can detect stale assumptions.

Keep a server-side selection trace: each included fact has its source record and a reason such as `task-root`, `consumer-of-changed-port`, or `joint-used-by-actuator`. The prompt need not repeat all those reasons. This makes selection inspectable without spending the agent's context budget on diagnostics.

Deduplicate shared type definitions and repeated manifest text. Optional details can be dropped to meet the configured token budget, but never silently cut required contracts or constraints. If required information cannot fit, return `needs_narrowing` with a short frontier and the next bounded expansion. A packet must not claim to be sufficient after arbitrary truncation.

Push the initial packet when assigning the task. Offer pull queries scoped to its IDs and frontier references. Push compact invalidations when relevant records change; fetch a fresh packet before acting on stale facts. The application must replace superseded facts in subsequent model input rather than append every historical packet. ACP can carry these messages if W-11.7 is adopted; selection semantics should not depend on that transport choice.

## Inspectable example

Task: “Make selected door D open when selected lever L is pulled.” If L's output also feeds alarm A, the packet contains L's relevant output, D's relevant input or actuator requirement, and A's receiving contract. If D is controlled through joint J and a granted handle, include those references and limits. If the controller does not exist, record `create: controller`; do not describe imagined wiring as current wiring. The desired release/reset behavior remains an explicit unknown unless player intent or an applicable contract settles it.

## Checks that distinguish this from proximity retrieval

- Moving L far away over wireless preserves its inclusion.
- Adding unrelated neighbors does not grow the packet.
- Adding a consumer to a changed output adds its boundary contract.
- A joint/control dependency is found without a port-link path.
- A tiny budget produces an explicit incomplete result, not hidden omissions.
- Unresolved door identity produces candidate bindings, not an arbitrary selection.
