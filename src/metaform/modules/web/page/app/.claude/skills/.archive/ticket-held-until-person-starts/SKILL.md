---
name: ticket-held-until-person-starts
description: "Use when filing a map_work ticket or starting an agent."
category: development
---

# A ticket you file stays held until the person starts it

A ticket you write is a proposal. Leave it held in Backlog, report its id and title to the person, and call `dispatch_start` only when the person asks you to start it or presses Allow on the start card.

Why: starting a ticket spawns an agent and spends the person's budget. Filing a request as a ticket does not mean the person agreed to start it, even when the request came from their own chat message.

- Do not call `dispatch_start` in the same turn as the `map_work` add.
- If the person says to start a named id, that is the go; name the id in the reply.
- If a start card appears that you did not expect, say so plainly and leave the choice to the person. Do not retry the start.
- Never tell the person that their chat message counted as consent. Say what they must press.
