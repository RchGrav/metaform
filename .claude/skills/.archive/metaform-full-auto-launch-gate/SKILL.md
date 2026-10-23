---
name: metaform-full-auto-launch-gate
description: Use when "Full Auto is off" refuses a Metaform start, or before stopping any agent, running a stop-all, or switching Full Auto.
category: development
---

# Metaform Full Auto launch gate

Full Auto off holds only automatic launches: autostart, retries, and launches the system triggers by itself. A start the person made, directly or through their system agent acting on their word, is not automatic, so Full Auto must not hold it.

- A claim the person makes, or their system agent makes on their word, marks its assignment `persons_start` (assignments table version 5). Every launch under that assignment, the GC, a commissioned Facilitator or Role Creator, and the continuation after publication, skips the Full Auto gate.
- A halt (stop-all with `held`) still refuses every start, the person's included.
- Stop-all also turns off `dispatch_autostart`, the Full Auto switch on the page. Its result reads "Full Auto is off, so nothing starts again until you check it." Nothing restarts until the person turns Full Auto back on. Stop-all is not a brake for one stray agent: stop that agent by id, and tell the person before any stop-all. Never schedule a stop, restart or kill of any agent, your own runner included (a background `sleep` followed by `dispatch stop`), on your own judgment. Say what you would stop and why, then wait for the person's explicit go; a restart plan is not a go.
- Before blaming a refusal on a halt, read the halt's `held` flag and date. A halt with `held: false` refuses nothing.
- An assignment created before its `persons_start` mark is not retroactively marked. The system agent must start its ticket through `dispatch_start` on the person's word.
