---
name: agent-embodiment-design
description: Use when designing agent embodiment or physics test views.
category: development
---

# Agent embodiment design

Design for any simulated body, not for the current map. An agent acts in turns, so every interface must let it know its own state between turns.

- Every act returns its outcome, not an acknowledgement: where the body ended, what was asked against what happened, and what it touched.
- Sense from the body: distance to surfaces (not only centres), distances in body units, and only what is perceivable by range and occlusion, nearest first and capped, with the rest as a count.
- Time advances only when the agent asks: pause between turns, or step a stated number of seconds and then report. Each look says what changed since the last turn.
- Prefer goal-shaped acts with a stopping rule ("go to X, stop 2 units short") over raw distances.
- Tests are seeded, recordable and replayable. Measurements come back as data an agent can assert on; images are for people and rough checks.

No embodiment or physics records exist in `specifications/` yet. Agree the record with the person before building, following AGENTS.md.
