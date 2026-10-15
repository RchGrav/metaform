---
name: metaform-2d-flow-dots
description: Use when editing Metaform 2D map flow dots in flow2d.js.
category: development
---
# Metaform 2D map flow dots

The 2D flow stays SVG. Never draw it on a canvas over the map.

- `edgeShapes` in `map2d/flow2d.js` builds each edge's shapes once, inside `g.flows2d` right after `.edgePaths`: one train `g` per direction, inside `g.trains`, holding one bead path (full-strength dots) plus one single-dot path per fading dot; one `ask` path for the request, inside `g.asks`; one `record` rect and one `ring` circle inside `g.marks`. It samples the edge (`sampled`) there, at build: sampling later, inside a frame after its first write, forces a full layout per `getPointAtLength` (690 a frame once).
- A dot path holds only its dots: each dot `M x,y h0`, a zero-length round-capped subpath at `pointOn`'s point; `dots2d` writes `d` only when it changes. Display only when a shape's state changes (`show2d`), group opacity only when it changes (`FLOW2D.group`), colours once at creation. State lives in classes (`Shape2d`, `Train2d`, `Edge2d`, samples as `Float32Array`s in the `SAMPLED` WeakMap), never as properties added to DOM elements or Mermaid's edges; the frame allocates nothing but the text it writes (scratch `POINT`, index loops, `flowAt`'s shared `AT`). Never a dashed copy of the whole edge: it made the GPU re-raster every moving edge's whole length each frame.
- Each composited flow layer (`.trains`, `.asks`, `.marks`) keeps one size: `extent2d` prepends a rect that draws nothing, the box of all the flow's edges plus 20. A layer sized by its moving dots resized every frame and made the browser re-cut the map after it into new layers each frame (365-466 layer ids in 2 s against 116).
- `graph/checks.js` `flowDrawn` lists the shown `.train`, `.ask`, `.record` and `.ring` under `g.flows2d`. A new kind of flow shape goes in that selector.
- CSS: `.flows2d .bead` and `.ask` are `fill: none`, round caps, 4.2px and 3.8px strokes, no filter of their own. The glow is one `drop-shadow` on `.trains` (currentColor) and one on `.asks` (`--spark`), each with `will-change: filter`, so the compositor applies it; `.marks` has `will-change: filter` and no filter. A drop-shadow on each dot path halved the frame rate; no layer at all costs 1.6-5x; `will-change: transform` costs 1.5x.
- Measured 2026-10-15 (graphical#80, `artifacts/perf/2026-10-15-graphical-80/`): flow all 2D 10-12.5 -> 14-19.5 fps, 3D 7.4-10.6 -> 15.4-21; still 0.5-0.8 of flow off. The GPU process (WSL D3D12) is ~95% busy with flow off and each moving layer re-rasters ~3 wide tiles a frame at ~1.6 ms: that raster is what is left.
- Verify: `node --check flow2d.js`, no line over 120 characters, then the look. `artifacts/perf-f1-2026-10-14/scripts/shots.py` is not deterministic on fresh scratch homes (flow cycles start from unseeded Math.random at load and persist); compare in one page instead, `artifacts/perf/2026-10-15-graphical-80/scripts/lookab.py`: hold the virtual clock, shoot, redraw each dot the other way at the same distance along its edge, shoot again.
- `web_flow_mode` is a per-person view setting, not a `metaform set` switch: set it in the page with `saveView('web_flow_mode', ...)` from `/page/app/views/settings.js`, on a scratch home only.
- Another session may edit the same file mid-task. Keep a copy from before your edit and diff against it, so you see only your own hunks.
