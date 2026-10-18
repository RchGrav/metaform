---
name: metaform-3d-depth-cues-from-viewer
description: Use when editing the 3D map haze, fog or depth fade.
category: development
---

# Measure 3D depth cues from the viewer's eye, never from the visible nodes

The haze of depth (VIEW-038), the names' fade by depth and any depth-based scale belong to the viewpoint. Measure each from the camera: the distance from the eye, scaled by the camera's look distance (camera to controls.target), so a thing's haze is the same whatever else is on screen.

- Do not normalise a cue to the nearest and deepest on-screen element. Why: when a few nodes sit close together in depth, as when the camera nears a large figure, the span collapses and everything behind them is drawn in the ground colour, so the view goes near-black.
- Keep one scene fog in the theme's ground colour. Why: the materials and the page's shaders already take it through three.js. Allocate nothing per frame (CLAUDE.md section 4, rule 1).
- Move the names' fade to the same measure as the nodes and edges, so names and parts still fade together.
- Check in a browser on the 3D map: with the camera still, a node's fog factor does not change when other nodes enter or leave view; moving the camera toward a node lowers its haze; with the camera close to a large figure, the nodes behind are not all drawn in the ground colour. No console errors.
- Record the change in VIEW-038 (specifications/09-viewer.md) with the date and ticket, after the code is built.
