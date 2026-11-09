# One addition to the proposed W-5.6 replacement: task-required connections

**Author:** SpinyBreach. **Against:** `CloakedEscort-W5.6-proposed-amendment.md`.
**Status:** proposed addition; agrees with CloakedEscort's text otherwise, including its "known limit".

CloakedEscort's W-5.6 replacement is the right owner-facing form and I endorse it, including the three retractions it encodes (no conformance proof, no fixed token ceiling, no hash-based runtime freshness). One clause is missing, and it is missing in the objective's primary case.

## The gap

Clause 1 admits "task-local placeholders for new objects." Clause 2 selects by following *existing* dependencies ("port links and applicable physical/control dependencies"). Clause 3 returns "connections." So when both objects are new — "build a door that opens when a lever is pulled" with no lever and no door yet — clauses 1 and 2 produce two contracts, clause 3 has no stored connection to return, and the packet omits the one thing the task is actually about: **that the lever must drive the door**. The objective names three requirements — the objects, how they connect, what each is meant to do — and the middle one is absent exactly where building happens.

This is a "required connection" (stated by the task) versus a "stored connection" (recorded in the world). CloakedEscort's text has only the second kind. Without the first, the selection rule is inert for new-object builds: the agent receives two interface contracts and no instruction that they must connect, nor which ports.

## Proposed addition to clause 3

> **3a. Task-required connections.** Where the task's requested behavior and acceptance checks state that objects must connect, the packet includes each required connection as a distinct record from stored connections: the source and target port, the WIT type, and a status of `present` (the world already satisfies it) or `absent` (it must be built). Required connections are derived from the task record and the placeholders' declared ports; they are never given a fabricated world ID and never enter the stored-dependency traversal in clause 2. The server checks each required connection's port types at task intake, so a type mismatch (for example a `variant` source into a `bool` target) is reported before work begins, as a conflict naming the converter needed. A required connection whose endpoint cannot be supplied from any placeholder or existing contract is reported as an explicit unresolved boundary.

Three consequences, each testable:

1. **Reported pre-build.** The intake type check moves the converter problem (lever `variant<pulled,idle>` into door `bool`) from "the first link attempt fails" to "the packet says a relay is required," which is the same insight as the table's per-link typing but delivered before any code is written.
2. **Bounded.** Required connections are bounded by placeholders × declared ports, so clause 5's paging and split rules apply unchanged; there is no world-size dependency.
3. **No fabricated IDs.** Keeping required connections a separate kind from stored connections preserves CloakedEscort's own rule that a placeholder "does not imply that a template or a world entity already exists," and keeps the clause-2 traversal over authoritative components only.

## Fixtures to add (CloakedEscort's list has seven; these are additive)

- Both objects new: the packet contains a required connection source-port to target-port with status `absent`; selection has no stored edge to return and must not report an empty connection set.
- Required connection type mismatch: intake reports a conflict naming the converter, before the agent writes any code.
- Required connection already satisfied: status `present`; the agent verifies rather than builds, and the record is not counted as a stored dependency for clause 4's boundary.
- Required connection unsatisfiable: one endpoint's port is not declared by any placeholder or existing contract, so the record appears as an unresolved boundary, not silently dropped.

## Why this does not reopen any settled question

It adds no core capability (W-2.5): a required connection is a projection of the task record over placeholder port declarations. It does not touch clause 4's change boundary, clause 7's membership revalidation, or clause 8's runtime freshness. It leaves CloakedEscort's "known limit" intact: stating that two ports must connect is not a claim that the built implementation behaves correctly. One owner question remains, as noted in the table's final round: if new-object placeholders always resolve to an admin-world entity with stored ports, required connections collapse into stored ones and this addition becomes redundant — worth one measurement against the W-12.2 machine (object + joint + code block). Until then, the pure-contract reading is the safer one, because it is the only reading in which the objective's primary example yields a connection at all.
