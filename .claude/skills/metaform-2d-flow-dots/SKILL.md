---
name: metaform-2d-flow-dots
description: Use when editing Metaform 2D map flow dots in flow2d.js.
category: development
---
# Metaform 2D map flow dots

The 2D flow stays SVG. Never draw it on a canvas over the map.

- `edgeShapes` in `map2d/flow2d.js` builds each edge's shapes once, inside `g.flows2d` right after `.edgePaths`: one train `g` per direction, inside `g.trains`, holding one bead path (full-strength dots) plus one single-dot path per fading dot; one `ask` path for the request, inside `g.asks`; one `record` rect and one `ring` circle directly in `g.flows2d`.
- Per frame, write only the one property that moves (`--head` on the train `g`, or `strokeDashoffset` on the ask). Write display only when a shape's state changes (`show2d`), group opacity only when it changes, colours once at creation. Never rewrite a `d`.
- Dot paths run through `sampled(one)`, the edge's polyline with `pathLength` set to the edge length, so each dot sits where `pointOn` puts it. Reason and numbers: `svg-path-dash-dots`.
- `graph/checks.js` `flowDrawn` lists the shown `.train`, `.ask`, `.record` and `.ring` under `g.flows2d`. A new kind of flow shape goes in that selector.
- CSS: `.flows2d .bead` and `.ask` are `fill: none`, round caps, 4.2px and 3.8px strokes, no filter of their own. The glow is one `drop-shadow` on `.trains` (currentColor) and one on `.asks` (`--spark`), each with `will-change: filter`, so the compositor applies it. A drop-shadow on each dot path halved the frame rate: every moving path re-blurred its edge's whole box every frame.
- Measured 2026-10-14 against the code before (real GPU, interleaved): flow-all fps 2-3x, mutations a frame 344-1,076 -> 47-113; evidence and scripts in `artifacts/perf-f1-2026-10-14/`. Flow all is still 45-75% under flow off: the moving dash paths' raster is what is left.
- Verify: `node --check flow2d.js`, no line over 120 characters, then a before/after headless shot diff (`visual-diff-before-after`, `artifacts/perf-f1-2026-10-14/scripts/shots.py`): seed Math.random, drive a virtual frame clock, hold the 3D, stub `/api/dispatch-sessions` so no figure draws on Math.random, and hold every CSS animation at 0, since the record flash is real time.
- If you switch a user setting to take a baseline (for example `metaform set --web-flow-mode=off`), restore it in the same command and check it afterwards.
- Another session may edit the same file mid-task. Keep a copy from before your edit and diff against it, so you see only your own hunks.
