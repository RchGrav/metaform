---
id: SPEC-metaform-rebuild
status: review-proposal
companions:
  - OWNER-AMENDMENTS.md
  - SPEC-AMENDMENTS.md
  - COMMAND-CONTEXT-INTAKE.md
  - BACKEND-COMPATIBILITY.md
  - CHASSIS-CLI-CLEANUP.md
  - RUNTIME-AND-EVENTS.md
  - SEPTEMBER-LADYBUG-RECOVERY.md
  - REUSE-MATRIX.md
  - EVIDENCE.md
sources: []
---

# Proposed amended Metaform rebuild capability kernel

Review-derived proposal. Existing owner decisions govern; reviewer mechanisms remain proposals in the companions. This preserves the archive's CAP-1 through CAP-16 identities and unchanged capability outcomes while carrying amendments A-F. Read the preserved ECS/archive source identified in EVIDENCE.md for the detailed adopted baseline. This is not a complete implementation contract or an implementation-readiness declaration.

## Why

Metaform develops reusable functional understanding before work and makes that understanding available to subsequent agents. Agents should spend inference on the work that needs their judgment, while receiving meaningful project orientation, retained knowledge and purposeful coordination. The rebuild provides this through a deliberately engineered agent interface and persistent infrastructure. It addresses repeated reconstruction of understanding and purposeless context flooding that previously incurred substantial inference cost.

## Capabilities

- **CAP-1: Functional understanding**
  - **intent:** Agents can establish and refine a functional map of an existing or intended AUE and reuse its receiving-purpose relationships.
  - **success:** One element can participate as receiver and provider without duplicate identity; OP/EF remain receiver-owned; refinements retain earlier referenced forms. See AC-01.

- **CAP-2: Semantic intake and change**
  - **intent:** Agents can express, inspect and revise functional understanding through semantic objects and consolidated changes.
  - **success:** An agent records meaningful elements and their receiving relationships without constructing Cypher, storage keys or a sequence of database operations; recursive reasoning and revision remain possible. See AC-02.

- **CAP-3: Functional navigation and retrieval**
  - **intent:** Agents can navigate to a functional Address or inspect it without moving, and retrieve the appropriate functional or knowledge view.
  - **success:** All three specified presentations are demonstrated, with direct relationships retained and neighbors' attached knowledge excluded from the local knowledge-rich presentation. See AC-03.

- **CAP-4: Knowledge layers**
  - **intent:** Participants can attach and select contextual knowledge at elements and Joins while preserving its application scope.
  - **success:** Ancestor knowledge applies correctly; a leaf-local selection does not restore a hidden layer on a sibling branch; explicitly empty and unspecified selection differ. See AC-04.

- **CAP-5: Native tools and skills**
  - **intent:** Agents can discover and use the native tools and skills relevant to the selected place.
  - **success:** Equivalent place/view/revision inputs expose the same available catalog across participants; native input schemas and skill bytes/digests survive projection; discovery alone does not count as skill loading. See AC-05.

- **CAP-6: Context continuity**
  - **intent:** Agents can acquire relevant context progressively and retain loaded skills through movement, compaction and deliberate handoff.
  - **success:** Unchanged bodies are omitted within an epoch; changed versions remain identifiable; movement preserves loaded skill versions; handoff and observed compaction use explicit delivery/retention records. See AC-06.

- **CAP-7: Addressed communication**
  - **intent:** Agents can communicate directly and leave discoverable messages for agents or namespace nodes.
  - **success:** A message retains origin, target, reply/causation and consumption traceability; node/agent records remain inspectable; a mailbox notice is distinguishable from durable semantic memory. See AC-07.

- **CAP-8: Event-driven orchestration**
  - **intent:** The system and participating agents can select useful teams and deliver purposeful assignments and continuations to eligible workers.
  - **success:** An eligible dormant worker receives an assignment and relevant context; direct peer exchanges and reasoned events work; routine ticket/status logging produces no automatic stream of model-context updates. See AC-08.

- **CAP-9: Coupled work composition**
  - **intent:** Work can be composed around receiving outcomes and indivisibly coupled contracts.
  - **success:** Explicit overlapping ICE memberships compose into one shared work unit; software contributions retain one worktree reference for the coupled change, without automatically merging branches. See AC-09.

- **CAP-10: Persistent agent lifecycle**
  - **intent:** Agents can continue across contexts, remain dormant for reuse and remain historically addressable after runtime retirement.
  - **success:** Logical identity/history persist through handoff, an independently proceeding fork has a new identity, and selection retirement preserves reference access; reuse decisions expose measured cache/harness evidence. See AC-10.

- **CAP-11: Peer reputation**
  - **intent:** Agents can assess practical work and use peers' aggregate histories when selecting collaborators.
  - **success:** Agent-visible results reveal neither an agent's own score nor identifiable reviewers/specific reviews; a single low result does not erase an established history. See AC-11.

- **CAP-12: Consistent persistent state**
  - **intent:** Participants can read consistent map/context versions and contribute changes without silently losing incompatible concurrent work.
  - **success:** A projection identifies its snapshot and resolved live revisions; concurrent incompatible edits expose both versions and a finding; materialized ancestry and incidence publish consistently with base changes. See AC-12.

- **CAP-13: Recoverable event delivery**
  - **intent:** Hosts can recover meaningful events across disconnects and distinguish known delivery from uncertain model or command outcomes.
  - **success:** Crossing and clearing remain separately replayable; duplicate event identities are recognized; a crash after ACP submission records an unknown outcome rather than asserting exactly-once execution. See AC-13.

- **CAP-14: Spatial observations and local response**
  - **intent:** Virtual and physical providers can supply a common observation contract while acting locally at their own execution rates.
  - **success:** Physical camera/depth-grid sensing supports 3500 mm at the stated 60-degree FOV. Virtual surround sensing supports 360 degrees as eight spherical wedges with top-to-bottom distribution, 45-degree triggering-zone and up/down-angle events, on-demand reads and unsigned 16-bit millimeters through 65535. Virtual conventional 3500 mm/60-degree arrays remain available. Profiles preserve geometry, quality, source and calibration identity without imposing autonomous reactions. See amended AC-14 in SPEC-AMENDMENTS.md.

- **CAP-15: Revision-bound documentation**
  - **intent:** Participants can regenerate specifications, explanations and user journeys from a named source revision.
  - **success:** An OP/Objective Purpose change updates affected explanations; a file rename alone does not fabricate a functional change; failed generation leaves the prior complete output available. See AC-15.

- **CAP-16: Observable operation**
  - **intent:** Users can examine behavior, delivery and inference cost through attributable evidence.
  - **success:** Acceptance demonstrations report source revisions, delivered bytes, model calls and boundary timings separately, and keep diagnostic observation outside automatic model-context logging. See AC-16.

## Constraints

- Preserve the functional semantics, exact C(T) formula, receiver ownership and distinct OP/EF/Objective Purpose meanings in the adopted ECS material.
- Use the selected LadybugDB/Cypher realization behind a semantic MCP interface; callers must not perform database choreography to express domain intent.
- Preserve source identity, revision and payload meaning across projection, delivery, replay and recomposition.
- Use reasoned event-driven orchestration and direct messaging while keeping continual live logging out of agent harness contexts.
- Preserve independent participant identities, positions and delivery histories; contextual presentation does not create a permission hierarchy.
- Use the explicit dynamic blacklist model where restrictions are configured; add no inferred whitelist or mandatory approval/reviewer pipeline.
- Preserve once-per-epoch delivery and explicit deltas without equating a receipt with model comprehension or unobservable retention.
- Report actual harness compatibility and separate local execution, transport and model timings.
- Preserve the permitted chassis specification and Python module template through evidence-based adaptation. Existing intake choreography and CLI-to-MCP mirroring are not frozen by canonical semantics.
- Metaform-owned retained runtime state, including settings, prompt versions, sessions, conversations and receipts, uses the selected LadybugDB arrangement. Externally owned native-resource references do not authorize internal SQLite exceptions.
- Use supported draft MCP events by actual capability/version/mode with general chassis-local event/message fallback preserving meaning and origin. Codex support is owner-identified; deployed profiles still require evidence.
- Provide an asynchronous Python-Node.js channel. ACP placement in Python or Node remains an explicit ownership decision.
- Separate virtual surround from conventional forward/physical geometry and range. Agent-written sensor/event consumers choose reactions.

## Non-goals

- Rebuild implementation or migration of legacy code during this specification operation.
- Automatic adoption of the old tool surface, prompts, status broadcasts, hierarchy or storage behavior.
- Requiring ECS for the functional graph or physical sensor adapter; Bevy remains an optional execution realization.
- A mandatory two-agent team, universal cache expiry, mandatory local A2A replacement or invented retirement defaults.
- Universal sensor equivalence, automatic arbitrary code recomposition, or unmeasured latency/capacity/inference-savings guarantees.
- Defining a multiplayer game, screen-sharing application or a complete team-management product through incidental examples.

## Success signal

A participant can establish functional understanding through semantic MCP interactions, inspect the right local context, receive a purposeful assignment, perform work and leave reusable findings for a later agent. The implementation demonstrates these interactions against the acceptance contracts while showing that routine background ticket/status activity adds no automatic logging stream to model context.

## Assumptions

- The handoff represents the prior discussion except where the owner corrects it; the owner has chosen to proceed from it and identify omissions as encountered.

## Open Questions

- The handoff records specific reputation arithmetic/assessment-cycle and proposed two-cycle-retirement details for later owner resolution. They remain localized in `completion-work.md`; they do not reopen the recorded reputation or lifecycle behavior.

- ACP placement and complete session/stream/cancellation/state/failure ownership across the asynchronous Python-Node channel.
- Final semantic change/readback/error/retry schemas, target persistence publication and actual harness event/skill/retention bindings.
- Surround angle/frame/sample conventions and physical calibration evidence, with topology/ranges and optional-consumer behavior already settled.
