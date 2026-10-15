---
name: metaform-ticket-dispatch
description: Use when dispatching, ordering, writing, releasing or cancelling Metaform tickets for agents, or when two agents share a store layout version.
category: development
---

# Dispatch Metaform tickets: name the agent, hold in order, tell parallel agents about each other

- Every ticket names `agent=claude`. Create a held ticket with `uv run metaform map work op=add node=<Address> kind=enhancement agent=claude hold=true title="..." task="..."`, and put its place in the chain in `note=` (for example "Held: runs after <address>#<n>").
- Resolve the work id from the item address with `uv run metaform map work node=<Address> hold=true limit=0` before starting it.
- Start with `uv run metaform dispatch start <work id> claude`. Follow it with `uv run metaform dispatch wait stopped id=<work id>`, run in the background because it blocks.
- Tickets that touch independent files may run side by side. Before two run together that share a map file or the store layout version, send each the other's scope with `uv run metaform dispatch note to=<work id> "<what, where, who goes first>"` and check for the "said:" line. A note stays on every ticket it touches. A note reaches the agent after the turn it has in flight, so expect a reply, not an instant change. When two tickets both change the store layout version, the note says which one bumps it first and which files each edits; keep the map module importable at every step, since a broken map module takes down every agent's map tools and the web page.
- Sequence the rest by the held chain; release each held ticket when the one before it lands. Release with `uv run metaform map work op=edit id=<work id> hold=false`, then `uv run metaform dispatch start <work id> claude`.
- Cancel a ticket the person has dropped with `uv run metaform map work op=done id=<work id> resolution="Cancelled: <what replaced it>" why="<who decided, date>"`. A worker refuses a cancel, so the system agent closes it.
- A ticket that places a property layer or a knowledge link states the moving-link rule in its own note: a link settles at the longest common prefix of its addresses and never moves toward the leaves. The agent running it reads only the ticket, and a later agent may link a different leaf of the same property.
- A worker cannot cancel a ticket: `dispatch cancel` refuses a worker, and `map work op=done` records the outcome completed, never cancelled. Name the cancel command and its reason for the person in the final resolution.
- A `dispatch note` to a work id whose agent has finished fails with "No agent is at work ... the note would reach no one." That note reached nobody. Check who is live with dispatch peers before relying on a note, and put what it said into the resolution.
- A `dispatch_note` reply to an agent whose session has ended is refused: "The agent that sent note <id> is no longer at work on an open ticket, so the reply would reach no one." Run dispatch peers first; if the sender is gone, put the answer on the ticket instead.
- When a spec lands while tickets are already running, cite its record ids on every ticket it governs (`map work op=edit` with the note extended), then `uv run metaform dispatch message <work id> "..."` each running agent, naming the records and the open questions it must not build past. Do not assume a running agent reads the spec on its own.
- A note is at most 1000 characters; a longer one is refused outright. Put the point in the note and the rest in a file or on the ticket.
- `map work op=done` does not read `said=`; it is ignored. Put the closing account in `resolution=` and the reason in `why=`, or it is lost.
