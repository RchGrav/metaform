---
name: metaform-triage-specialists
description: Use when triage picks a role or specialist for a ticket.
category: development
---

# Triage reasons against specialists

Triage chooses only from `metaform://specialists`, the list of published domain specialists. Each entry names the functional area it covers.

- If a specialist covers the ticket's area, assign that specialist.
- If none covers it, request one. The Role Creator writes it and adds it to the list.
- System roles (triage, gc, functionality, planner, implementer, verifier, reviewer, integrator, release, dogfood and the rest) are workflow stages. The workflow assigns them. They are not expertise and never count as a specialist match.

Do not pick a generic system role to avoid requesting a specialist. A generic `implementer` always looks like a fit, so no specialist would ever be requested.

- Known fault (observed 2026-10-20): with Jev off and no specialist registered, routing starts a Facilitator for every ticket before any work begins. That produced one "board specialist" inbox item per ticket (253 in one run) and one extra agent per ticket. Check the cause in `orchestration/routing.py` before relying on the specialist path.
