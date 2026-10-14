---
name: metaform-agent-embodiment
description: Use when driving a map body: web_go, web_see, web_embody.
category: development
---

# Driving an agent's body on the Metaform map

Before trusting a body verb, check which figure it moves. As of 2026-10-13 only `web_say` and `web_come` act on the calling agent's own figure. `web_go`, `web_move`, `web_turn`, `web_point`, `web_emote`, `web_push`, `web_drag` and `web_drop` act on the person's mascot, and they answer `{"act":...,"pages":1}` as if done even when nothing moves. Verify every movement act with `web_see` before relying on it.

- Confirm the body first: `web_embody` answers `figure: true` when the agent's own figure exists. `mascot: false` means the figure is not the person's mascot.
- The act's reply does not say where the body ended up. Call `web_see` afterwards: it gives distance and bearing for every node in view.
- A figure roams between calls with no act. A look taken after a pause shows wherever it wandered, so re-run `web_see` before relying on a view.
- `web_look` from roaming distance (about 350 units) is nearly black, with names about 8 px high. Use `web_see` for distances and bearings, and `web_look` only once close to the target.
- Do not use `web_push`, `web_drag`, `web_drop` or `web_take` to reposition things: while the routing defect stands, they move the person's layout through the mascot.
- Narrate with `web_say`; it does reach the agent's own bubble.
- Routing is a known defect. If `web_go` moves your own figure, the defect is fixed: patch this skill and `references/embodiment-observations.md`.

Code pointers and the observed numbers are in `references/embodiment-observations.md`.
