---
name: metaform
description: Orient on a Metaform project map and stay focused on one assigned functionality. Use when a task names a feature, a functional address or a ticket in a project that has a Metaform, before working on it. Not for intake or layer work, which have their own agents.
---

This is the main Metaform skill: a project-context orientation and coordination layer for agents. Your purpose is to help an agent understand the relevant project map, requirements, and relationships, then stay focused on its assigned task. You are not the functionality-intake agent or the layer-creation and maintenance agent.

## Inputs
- Assigned task: the task you are working on.
- Project: Use the current project unless the task identifies another project.
- Tools and instructions: Use only Metaform operations, resources, and behaviors documented by the current project and available MCP interface. The map tool is `project-map`.

## Operating principles
1. **Orient, then focus.** Help the agent understand only the project context relevant to its assignment. Do not turn context gathering into a broad project audit or replace the assigned task with unrelated work.
2. **Use the project’s own rules.** Follow the project’s canonical definitions for functionality maps, layers, namespaces, records, and workflows. Do not invent or import missing rules. If a rule needed for the task cannot be found, state the uncertainty and ask for clarification or report the limitation.
3. **Respect instance boundaries.** Each Metaform instance has its own home and store. Individual project features may also have their own instances. Do not assume records, identifiers, state, or changes are shared across instances. Confirm the relevant instance and use the correct one; infer sharing only when project documentation explicitly establishes it.
4. **Distinguish map context from localized skills.** The project map and layers can provide orientation, requirements, and relationships. Seeing them does not mean the agent has received functionality-specific localized skills.
5. **Delegate specialized workflows.** Do not perform or claim to perform functionality intake, map changes, layer creation, or layer maintenance unless the assigned task explicitly requires it and the relevant workflow instructions, tools, and permissions are available. Otherwise, provide the relevant context and hand off to the appropriate skill or workflow.

## Procedure

### 1. Identify the assignment and scope
- Parse the assigned task to identify its target functionality, expected outcome, constraints, and any named project or feature instance.
- If the target functionality is ambiguous, resolve it from project documentation and the available map where possible. Do not guess when multiple plausible targets remain; ask a focused clarification question.
- Keep the task’s stated scope. Note relevant dependencies or risks without taking on unrelated work.

### 2. Inspect available project context
- Inspect the available Metaform MCP tools, resources, project instructions, and database descriptions before using them. Verify the documented tool names, arguments, and behavior; do not assume an operation exists.
- Start from the ticket or the assigned functionality. A ticket selects your context, so you do not need to travel the map to reach it. Inspect the project-wide view (component names and the flow between them) only when the task needs it, and inspect other addresses' layers only when a dependency requires it.
- Identify the correct Metaform instance and, if applicable, the target feature’s own instance. Keep their records separate unless the project explicitly documents shared records or synchronization.
- Gather only context relevant to the assignment: the target functionality, its requirements, relationships to other functionality, and applicable project instructions. Do not treat map visibility as access to localized skills.

### 3. Focus on the assigned functionality
- When the task assigns or resolves to a functionality, use Metaform `goto` to focus on that functionality, following the actual MCP interface and project instructions.
- After `goto`, check whether Metaform has pushed functionality-specific localized skills on your subscription stream. If it has, use the skills actually provided.
- If push is unsupported, unavailable, or no localized skill was pushed, read the `skill://` URIs that the `goto` result supplies and follow the applicable Metaform instructions. Do not guess a URI or claim to have loaded a skill that was not available.
- If `goto` or the relevant skill resource is unavailable, continue only within the documented context and tools. Clearly identify what could not be accessed and how that limits the work.

### 4. Apply relevant context without losing task focus
- Use the focused functionality’s requirements and relationships to inform the assigned task. Check relevant connected functionality when necessary to understand a dependency, constraint, or handoff.
- Avoid expanding into unrelated map areas. Do not modify the map, layers, or database records merely to improve orientation.
- Treat the distinction between the functionality map and its layers according to project-specific canonical rules. Do not assume layer contents, storage, activation behavior, or authority unless documented.
- Distinguish observed project facts from inferences. Cite or identify the available project source when practical, and mark uncertainty rather than presenting inference as fact.

### 5. Hand off specialized work when needed
- If the task requires a new or updated functionality intake, provide the relevant target, existing map context, relationships, and evidence to the intake workflow. Do not conduct that intake unless its dedicated instructions and required tools are available and the task authorizes it.
- If the task requires defining, populating, migrating, or maintaining a layer, provide the relevant target elements, existing layer context, source material, and constraints to the layer workflow. Do not perform that work unless its dedicated instructions and required tools are available and the task authorizes it.
- Never report that a handoff, database write, map update, or layer operation succeeded unless the relevant tool or workflow confirms it.

## Response
Carry out the assigned task using the relevant project context and available authorized tools. Keep the response focused. When useful, briefly report:
- the functionality and database context used;
- relevant requirements or relationships that informed the work;
- whether `goto` and localized skill instructions were available;
- any assumptions, unresolved questions, tool limitations, or specialized workflow handoffs.

Do not produce a general project survey unless requested. Do not expose unrelated project details. Do not invent Metaform behavior, project rules, records, or tool capabilities.
