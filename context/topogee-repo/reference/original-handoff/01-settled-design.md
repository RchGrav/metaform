# Settled design from the voice conversation

## Governing intent

Metaform develops reusable functional understanding independently of work execution, so agents do not repeatedly reconstruct the project. The emerging new specification supersedes legacy implementations, prompts and historical plans. Existing source is evidence of possible mechanisms and omissions, not normative authority. Do not silently import existing behavior. The system uses a dynamic explicit blacklist model; do not convert intent into a whitelist or add unrequested gates.

## Functional namespace and context

The backend graph/database representation and the reasoning-facing agent intake representation are separate. Agent intake should resemble completing semantic fields, not writing database queries. Ingest functional elements, purposes, provider/receiver joins and related descriptions through a compact semantic interface. Prefer collecting/refining information and applying it in consolidated blocks instead of requiring ~20 iterative commands; recursive reasoning and revision remain available. A compact functional graph is independently retrievable.

Three retrieval presentations were identified: (1) local functional view of one namespace element, its providers and receivers; (2) global functional map without ancillary knowledge layers; (3) local knowledge-rich view focused on the selected element, showing only that element's attached knowledge and direct functional relationships, without dumping neighbors' knowledge. One recovery/retrieval tool may offer these modes. One apply/change command is preferred for semantic updates. Full-map retrieval need not be automatic at startup.

## Context delivery and mailboxes

Context delivery is once per agent context epoch (bounded by deliberate compaction/self-handoff). Changed information should be delivered as a delta, rather than repeating the entire local namespace. Agents may choose when to retrieve a pending local notice. There is an agent inbox and an inbox on each namespace node for the next visiting agent. Pending messages cease to be pending when acknowledged/delivered; read-message records are retained locally at both the node and consuming agent for traceability. Distinguish a one-off mailbox notice from durable semantic memory.

A key delivery restriction was emphatic: do not inject informational messages, logs, progress or task-completion notifications into agent conversation context. Ordinary agent-to-agent direct communication and chassis-driven lifecycle messages (selection for work, handoff, etc.) are distinct. Do not inherit the old implementation's incidental informational-notification path. Existing local agent messaging is preferred; A2A is not a required local replacement and may be considered later for remote collaboration. MCP events are the forward direction, with local agent messaging as compatible fallback where needed; protocol capabilities must be validated against real harnesses.

## Agent lifecycle and orchestration

There is no fixed two-agent minimum. Users can express preferences for team size and composition; in Full Auto the facilitator can reason about whether one worker, a pair, or a differentiated team is useful. Examples: high-end specification reasoning, coding implementer, inexpensive trailing completion checker; a two-agent collaboration can perform reciprocal real-time review. Peers should be candid, attentive and appropriately critical; undercommunication and excess messaging affect performance assessment.

Workers remain dormant and available for reuse after completing assignments, retaining live skill/context while useful, rather than automatically terminating. Reuse avoids repeated orientation. Cached context value and consumption determine whether to keep an idle session eligible; once cache economics no longer justify reuse, it can be retired from selection. Cache duration depends on model/harness and must be measured, not fixed universally at five minutes.

Agents self-handoff around 50% context utilization with graduated warning and later enforcement around the previously discussed ~65% threshold; this is an existing intended behavior to verify in code, not a request to replace with an unrelated policy. Each agent retains a unique deterministic identity, persistent conversation and commit history across contexts; code edits themselves need not be reproduced in the conversation ledger. Historical identities remain addressable for questions after runtime retirement.

## Peer reputation

Agents score each other's practical work, quality, critical review and communication conduct. Peer ratings are not attributed to identifiable reviewers in agent-visible output. An agent can see other agents' aggregate reputation for selection purposes but never its own score; reviewer identities and specific reviews are not disclosed to peers. Scores are aggregated across history so that one low result does not arbitrarily erase an established record. Separate optional retirement reason: an agent that is the lowest rated across two consecutive assessment cycles becomes ineligible for fresh work and goes dormant for reference, with identity/history preserved. This two-cycle mechanism was discussed as a proposed rule; check its unresolved details before final implementation.

## Operation and quality

Agents should be able to identify upstream/downstream functional responsibilities, the purpose/function/relation of joins, and the state of work from a bounded contextual view. Correct functional behavior takes priority over busy-work documentation. No automatic background progress/completion broadcasts into worker contexts. Implement sufficient observable tests to show behavior, cost and delivery semantics without inventing additional controls.
