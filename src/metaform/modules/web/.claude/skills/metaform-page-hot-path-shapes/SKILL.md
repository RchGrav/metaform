---
name: metaform-page-hot-path-shapes
description: Use when editing per-frame or per-event Metaform page JS.
category: development
---

# Metaform page hot paths: no allocation, stable shapes, index loops

Code that runs per animation frame, per stream event or per graph node allocates nothing and keeps one object shape. Check the diff for these before calling it done.

- Scratch vectors are module-level constants (`const THERE = new THREE.Vector3()`), reused by every call. No `new`, `[]`, `{}` or `Object.assign` inside a frame or event function.
- A list of waiters is a dense array walked by index, removed by swap-pop. Never iterate a `Set` or `filter` a list in a frame. Shared lists (`AFTER` in `graph3d.js`, `WARM.waiting` in `linking3d`) change only through their add and remove helpers.
- In per-event code, replace `find` and `some` with index loops; test kinds by loop, not `includes` on a freshly built array.
- Build a result object once, when a wait ends, never per frame.
- Declare every field in the literal, unset ones as `null`, and assign in the same order. Set fields directly; no `delete`.
- Pass positional arguments on hot calls instead of an options object; keep module tables (such as `PANE_TABLES`) as constants.
- Measure before and after (allocation count or the burst test); moving an allocation is not a fix.
