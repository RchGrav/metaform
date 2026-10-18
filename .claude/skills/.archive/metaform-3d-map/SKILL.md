---
name: metaform-3d-map
description: Use when editing the 3D map orbit, haze, fog or probes.
category: development
---

# Metaform 3D map: probes, orbit pivot and depth cues

Measure the 3D map from the viewer's own eye and camera, keep the orbit on the selected node, and set up each probe so it really opens the view it measures.

## Probes that press V or E
- Before the page loads, a probe sets `localStorage` key `metaform.swapped` to the empty string. Without it the 3D map can start in the small area, where `agentView()` refuses V and `EYE.saved` stays null, so the probe measures a view that never opened.
- After pressing V or E, read `EYE.saved` first. If it is null, the setup is wrong, not the eye code; fix the setup before measuring timings.
- Run each headless browser under `env -u DISPLAY -u WAYLAND_DISPLAY` with `--headless=new`, in a scratch home, following `metaform-process-lifecycle`.
- Set CPU throttling through CDP only for timing parts, and report frame rates with the throttle level.
- Load the modules onto `window` first, then wait on a synchronous predicate. An async predicate in `wait_for_function` returns at once.
- For a before/after probe, run the same script on a scratch copy of the HEAD files and on the change, and report both numbers. Never `git stash` in the shared tree.

## Orbit pivot stays on the selected node
While a node is selected, the orbit target is that node's centre, so a drag turns the map about the node the person is looking at. Mechanics, the follow clearance and the browser test recipe are in `references/orbit-pivot-clearance.md`.
- The pivot ends on flyTo, a changed or cleared selection, a memory network, an agent's eyes, or a followed agent. While `FOLLOW.work` is set, `followIn3d` is the only mover.
- A click on a 3D figure is a selection, not a follow. On the selection flight and while the pivot holds, the camera keeps at least `CLEAR` (3.3) times `FIGURE_RADIUS` (0.8) times `mesh.scale.x` from the focused figure.
- In Work mode, when agents are working on the node, and in Free mode, a selection does not move the camera; leave the pivot alone there.
- Label size, flight easing and auto zoom are outside this rule; do not change them to fit it.
- VIEW-005 does not describe the pivot yet. Amend it through the spec-amendment route, not in passing.

## Depth cues come from the viewer
- The haze (VIEW-038), the names' fade by depth and any depth-based scale are measured from the camera: distance from the eye, scaled by the look distance (camera to controls.target).
- Do not normalise a cue to the nearest and deepest on-screen element. When nodes sit close in depth the span collapses and everything behind is drawn in the ground colour, so the view goes near-black.
- Keep one scene fog in the theme's ground colour, and allocate nothing per frame.
- Names fade on the same measure as nodes and edges, so names and parts fade together.
- Check in a browser: with the camera still, a node's fog factor does not change when others enter or leave view; moving toward a node lowers its haze; close to a large figure the nodes behind are not all drawn in the ground colour; no console errors. Then record the change in VIEW-038 with its date and ticket.
