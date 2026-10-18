---
name: metaform-frame-step-no-allocation
description: Use when a per-frame JS follow or spring step allocates.
category: development
---

# Per-frame steps write scalars in place

A step that runs every animation frame must not return an array or destructure one (CLAUDE.md section 4, rule 1). Inline the step per axis, reading each old value into a `const` before writing, and write the result back with `Vector3.setComponent` / `getComponent`. Leave the shared helper (`spring` in `map2d/camera.js`) unchanged for its other callers.

Before reporting it done:
- Check the inline step against the original helper on random inputs (10,000 samples, both outputs). The worst difference must be 0.
- Keep the reduced-motion branch identical to the helper's early return.
- Grep the function for array literals `[` and destructuring that remain.
- Run the filtered tests for that feature, for example `uv run pytest -n 0 FILE -k NAME`.
