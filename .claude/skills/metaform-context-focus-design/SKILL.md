---
name: metaform-context-focus-design
description: Use when designing how agents get context, tools or skills.
category: development
---

# Give each agent only what its task needs now

Every token an agent holds is a counted cost and a loss of focus. Deliver what the task at this place needs now; fetch everything else narrowly, when asked for.

- Keep the selectable items in an agent's range (tools, skills, and anything else it must choose from) at 30 or fewer at any point. Count them together. Test the count at every node so it cannot grow back quietly.
- Discovery is progressive: a short list first, then the detail of the one item the agent opens. Never load a whole collection (the whole map, every tool schema, every skill body) to find one thing.
- Do not rely on a brief to carry context. A fresh subagent receives only the prompt its parent writes. Design so no process needs a subagent to do its work. Facts and sources: `references/subagent-handoff.md`.
- Token cost is a hard limit, not a rank against focus. A prompt or tool description that does the same job with fewer tokens replaces the old one.
- Restate the owner's priorities in his words. Do not reorder or rank them yourself.
- Judge every delivery change by one question: does this exact task need this text now?
