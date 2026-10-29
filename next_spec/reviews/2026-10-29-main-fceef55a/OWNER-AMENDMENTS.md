# Governing owner amendments

Source: the owner's review assignment in this session, 2026-10-29. These amendments govern the archived specification where they update it. The text below is preserved for review traceability. It does not authorize rebuild implementation.

## A. Reuse and redesign

- There is no blanket prohibition on reusing existing project code.
- The existing chassis specification and Python module template are explicitly permitted reuse sources.
- Formally evaluate other existing code for usability before recommending reuse.
- The command surface, context delivery and intake process are the principal areas requiring re-engineering.
- Clean up the chassis CLI.
- Engineer a proper agent-facing semantic MCP interface. Do not simply expose database operations or mirror the old CLI command inventory into MCP.
- Preserve the functional meaning and canonical terminology. The existing intake implementation and procedural choreography are not frozen merely because the underlying semantics are important.

## B. Backend

- LadybugDB is an informed, selected choice. Do not reopen the database selection.
- The rebuild has a different data backend and data model. This is not merely a driver or import replacement.
- Every reuse recommendation must account for direct and transitive storage dependencies.
- Do not silently retain SQLite for settings, conversations, sessions, receipts or other runtime data as an assumed exception.
- The owner recalls LadybugDB already being wired into the project in September. Locate and assess that work rather than assuming all LadybugDB integration must be created from nothing.

## C. Agent interface and context

- Namespace hierarchy, functional relationships and the agent’s reasoning process are related but distinct.
- Agents should express and revise meaningful functional objects, receiving purposes, provider contributions and references through an engineered interface.
- Support compact, coherent submissions and revision without requiring database-command choreography.
- Preserve three retrieval presentations:
  1. Local functional view: selected element and its providers/receivers.
  2. Global functional map without ancillary knowledge layers.
  3. Local knowledge-rich view: the selected element’s attached knowledge and direct functional relationships, without dumping neighbors’ knowledge.
- Preserve once-per-context-epoch delivery, source/version identity and changed information as deltas.
- Discovery, resource delivery, skill loading and retained context are distinct.
- Do not equate a receipt with comprehension or with retention that the harness cannot observe.

## D. Events and harness compatibility

- The MCP event mechanism is a draft.
- The owner identifies Codex as the current supporting harness.
- Use the supported draft MCP event mechanism where available.
- For harnesses without support, deliver a local chassis event—for example, a message.
- This is the general event-delivery design, not a sensor-specific exception.
- Select transport by actual capability/version. Other harnesses should be able to adopt MCP events without rewriting event-producing code.
- Preserve event meaning and origin across transports.
- Purposeful messages, assignments, peer communication and reasoned event-driven orchestration are allowed.
- Do not implement continual live logging of every ticket update, progress line or completion into agent harness context. That previous behavior caused purposeless context flooding and substantial inference cost.
- This is not a blanket prohibition on informational content, messages or events.
- Do not introduce an inferred hierarchy, event allowlist or mandatory approval/reviewer pipeline. Preserve the explicit dynamic blacklist model.

## E. Python and Node

- An asynchronous Python–Node.js channel is required.
- ACP may live in Python or Node. Its placement remains explicitly open for discussion.
- Do not infer ACP ownership from the location of the chassis or from a preferred SDK.
- Compare actual ownership of sessions, streaming, cancellation, lifecycle, state and failure recovery.
- The existing module named “node” may mean a hosted Metaform Node/broker. Do not mistake that name for evidence of an existing Node.js runtime or Python–Node.js channel.

## F. Sensor control scheme

This is a data/control surface, not a requirement to implement autonomous NPC behavior.

- Physical profile: camera view with a depth-grid overlay, up to 3500 mm, with the stated 60-degree FOV.
- Virtual profile: 360-degree sensing around the agent, described as eight spherical wedges with top-to-bottom distribution.
- Surround events expose the triggering 45-degree zone and an up/down angle.
- Agents can query the virtual data at any time.
- Agent-written code can trigger events based on sensor data and use them to initiate actions.
- Virtual space can also use the conventional 3500 mm/60-degree profile and read its sensor-value array.
- Virtual sensing exposes the full unsigned 16-bit millimeter range: up to 65535 mm, approximately 215 ft. Do not inherit the physical range limit or signed-16-bit truncation.
- A rear event followed by a head turn and image/depth read is an example consumer.
- Forward-looking sensing for stealth-game NPCs is another example.
- Those examples do not impose a compulsory reaction, gameplay policy or autonomous detection system on MCP.
- Do not silently treat the old forward positive-z/axial-depth profile as the geometry of virtual surround sensing.
