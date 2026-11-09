---
name: intake-context-architecture
description: "System design: two sides (functional space and procedure), intake context as concepts + TASTE + procedure + patches, knowledge layers, progressive discovery and the address demo"
metadata:
  node_type: memory
  type: project
  originSessionId: 64f72fa6-1e3a-44a5-9ed3-c89e8167ad8a
  modified: 2026-10-31T00:42:30.645Z
---

Design as the founder explained it on 2026-10-30.

**Two sides.** The system has a unified functional space that stores the data, and a procedure, which is intake. Internally it stores and proceeds in metaform terms. Agents get an MCP interface in terms they understand, with TASTE. The reason is the last build: all agents received the metaform context, and in place of a proper MCP interface they got direct backend access and treated it as a way to maintain the database.

**Intake context.** Lowest-context intake is metaform concepts + TASTE concepts + procedure + patches. A patch is a single clarification added after a failure is observed. The present intake is large because each time a token changed and it stopped working as tested, a rule was added to reinforce it. Those rules are load-bearing. Which of them ride with the procedure is the founder's decision. Keeping rule context at all is open, because partial understanding can be dangerous.

**Procedure.** It is recursive. It isolates similar things into categories and finds the party that needs them. Universal intake can have focused task and skill combinations by job and target.

**Metaform and layers.** The metaform is pure functional understanding, with no programming language and no non-functional properties. Its strict rules, such as fps being valid and platformer being illegal, apply only to intake and to expanding the base functional map. Everything else goes into knowledge layers: understanding needed in that part of the project and irrelevant elsewhere. Formboard is an analogy for the metaform without layers, and it is not a spec term.

**Progressive discovery.** An agent in functional space benefits from its position and relations, as a game character benefits from distances and vectors more than from vision. It needs to know what it provides to callers, what it calls, what skill applies and what rules apply here. This matters more as a project grows, because the agent's job is local and the rest of the project is noise to it.

**Address demo.** A one-line best-practices prompt was run on each prefix of `code.engine.game.fps`. The addresses are nearly identical, and the outputs overlap very little. The demo shows what a knowledge layer is and how one prompt can be magnified across a project's functional topology. The trunk orients, and the leaf drives the inference. Practices inherit from parent to child, so a practice that stays true without its leaf belongs higher. The lists are demo output, not project rules.
