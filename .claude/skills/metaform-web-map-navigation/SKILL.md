---
name: metaform-web-map-navigation
description: Use when moving or looking on the Metaform web map.
category: development
---

# Navigating the Metaform 3D map

Before any `web_move` or `web_turn`, read `web_embody`'s answer. `figure: true` means you have your own body. `figure: false` means every move drives the person's mascot: stop and report that instead of moving.

- Treat `address=` moves as approximate. They can land short or overshoot. Confirm with one `web_look`, then correct with a small step.
- Let a turn finish before judging facing. A look straight after `web_turn` can report the old facing.
- Forward steps travel further than their number suggests (forward 200 went about 250 units) and head toward wherever you face, not toward a target. Labels are readable at roughly 50 to 250 units.
- `web_look` lists 60 to 90 entries, including `visible: false` ones up to about 960 units away. Read the nearest readable ones; do not paste the whole list into a reply.
- Labels are mirrored when seen from behind. Check orientation before reading text.
- A defect you hit is a ticket (`metaform map work op=add`), not a silent workaround.
