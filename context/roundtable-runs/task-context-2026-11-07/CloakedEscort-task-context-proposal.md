# Task context selection proposal — CloakedEscort

Round 1 proposal for D-W10. All mechanisms below are proposed; they do not change the status of existing world requirements.

## Selection rule

Select a task's **behavioral dependencies**, rather than every entity within a distance or a fixed number of graph hops. Geography helps resolve a player's reference, but is not the boundary of context: a wireless controller can be distant and a nearby unrelated machine can be irrelevant.

1. Resolve the task to persistent entity IDs, requested behavior, allowed changes, and explicit constraints. Use the player's selected objects first. Search descriptions and location only to produce candidates. If multiple candidates remain plausible, return the candidates for disambiguation rather than selecting silently. A requested new object gets a task-local placeholder, never a fabricated world ID.
2. Read the selected entities' intent and interface declarations. Select the ports involved in the requested behavior and all existing links incident to those ports, including other producers or consumers. Include all ports of an entity being reprogrammed unless it declares a trustworthy narrower dependency contract: otherwise its unrelated behavior can accidentally be removed.
3. Follow dependencies needed to explain or change that behavior. Bus links alone are insufficient: W-4.4 joints, W-7.4 actuator handles, sensor targets, and applicable W-7.3 physics volumes can also affect the result. Represent these as typed, queryable relationships or explicit query results with provenance. This extends the retrieval model, not the functional map.
4. Stop at an entity's declared interface when its internals will remain unchanged. Include its relevant input/output contract and constraints; leave implementation behind a retrieval reference. Expand inside it only for a task that modifies or diagnoses its implementation, or when no adequate contract exists.
5. Include needed constraints and failure information, then project away meshes, module bytes, unrelated state, and repeated descriptions. Attach an inclusion reason to each selected record in the server's inspection trace; the agent normally receives only the compact projection.

The resolver must distinguish a known absent connection from a connection it has not inspected. It may not turn an unexplored boundary into “no dependencies.”

## Bounded delivery

The initial packet contains:

- Task, target IDs, allowed changes, and unresolved requirements.
- Relevant entity intent, port names/directions/types/semantics, links and non-bus dependencies.
- Available action handles and constraints; visibility does not itself grant permission to edit.
- Source revisions for definitions and a tick for any runtime observations.
- A boundary manifest: what remains outside the packet, why, and how to retrieve it.

Use an initial configurable serialized-size/token budget. Preserve exact IDs, port names, types, link endpoints, constraints, and unknown markers. Shorten redundant prose first. If mandatory context exceeds the budget, return an explicitly incomplete task summary plus bounded pages or subtask scopes. Never present a silently truncated packet as sufficient to act.

World-to-agent transport is independent of selection. Push this packet when assigning the task; expose bounded pull requests for an entity's details, a dependency boundary, or a relevant implementation. These are proposed semantic operations, not a commitment to a particular ACP method or MCP tool. All use the same permission filtering and revision references.

During work, send coalesced changes to relevant definitions and links, plus task-relevant failures. Do not push every simulation tick. Before applying changes, validate revisions for the read dependencies and reselect affected context if they changed. Runtime observations carry a tick and require fresh checks when an action depends on present state.

## Door example (illustrative records, not existing world content)

Task: make selected door D open when selected lever L is pulled.

- Include L's relevant output and its meaning, not merely `bool`: does it emit an edge on pull, or a maintained state? Type compatibility alone cannot answer this.
- Include D's intended opening behavior and the actuator/controller interface. If D is only a mesh attached to joint J controlled by block C, include J, C, and C's grant to drive J; a graph walk restricted to port links misses the actual mechanism.
- Include existing writers to the chosen controller input and consumers of a changed output. A second lever or alarm sharing the signal is a dependency even if the user did not name it.
- Keep an unchanged controller's internal code outside the packet when its contract suffices. Include it if the task requires reprogramming that controller.
- Record missing behavior explicitly: for example, `lever release behavior: unspecified`. Do not invent “close on release” from the phrase “opens when pulled.”
- Exclude an unconnected lamp beside the door, the lever's decorative mesh, and distant unrelated wireless channels.

## Inspectable acceptance cases

1. Adding an unrelated neighboring machine does not enlarge this task's packet.
2. Moving a linked wireless controller far away does not remove it.
3. Replacing a direct port connection with a controller/handle/joint path still exposes the actuator dependency.
4. Adding another consumer to a changed output exposes its contract or an explicit unresolved boundary.
5. Budget overflow remains visible and blocks claims that the task context is complete.
6. A definition or link revision change invalidates affected proposed edits; an unrelated entity change does not require full reselection.

These cases test relevance and omissions directly, rather than rewarding small packets that happen to hide necessary facts.
