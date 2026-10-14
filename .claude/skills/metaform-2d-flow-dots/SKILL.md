---
name: metaform-2d-flow-dots
description: Use when editing Metaform 2D map flow dots in flow2d.js.
category: development
---
# Metaform 2D map flow dots

The 2D flow stays SVG. Never draw it on a canvas over the map.

- `edgeShapes` in `map2d/flow2d.js` builds each edge's shapes once, inside `g.flows2d` right after `.edgePaths`: one train `g` per direction holding one bead path (full-strength dots) plus one single-dot path per fading dot; one `ask` path for the request; one `record` rect and one `ring` circle.
- Per frame, write only the one property that moves (`--head` on the train `g`, or `strokeDashoffset` on the ask). Write display only when a shape's state changes (`show2d`), group opacity only when it changes, colours once at creation. Never rewrite a `d`.
- Dot paths run through `sampled(one)`, the edge's polyline with `pathLength` set to the edge length, so each dot sits where `pointOn` puts it. Reason and numbers: `svg-path-dash-dots`.
- `graph/checks.js` `flowDrawn` lists the shown direct children of `g.flows2d`. Adding or removing a direct child means updating that list.
- CSS: `.flows2d .bead` and `.ask` are `fill: none`, round caps, 4.2px and 3.8px strokes; keep the glow drop-shadow.
- Verify: `node --check flow2d.js`, no line over 120 characters, then a before/after headless shot diff (`visual-diff-before-after`). Mask the "Tests and CI" box: its flash is a real-time CSS animation, not part of the flow.
- If you switch a user setting to take a baseline (for example `metaform set --web-flow-mode=off`), restore it in the same command and check it afterwards.
- Another session may edit the same file mid-task. Keep a copy from before your edit and diff against it, so you see only your own hunks.
