---
name: intake-built-state-analysis
description: "Intake design: MISS is now not_built, BKN is too coarse a judgement, and built-state analysis is a required core part of intake"
metadata:
  node_type: memory
  type: project
  originSessionId: 64f72fa6-1e3a-44a5-9ed3-c89e8167ad8a
  modified: 2026-10-31T00:42:18.187Z
---

Founder ruling, 2026-10-30: the MISS state is now `not_built`, and BKN is too coarse a judgement. Built-state analysis is a required core part of intake. Everything else relies on it to know what exists and what does not, even in a project with no build history or commits.

**Why:** Intake is already a heavy operation. Judging defects was too much for intake agents, and they marked things broken when they had not understood the approach. Existence is what later work depends on, so the founder wants caution about what else intake is asked to reason against.

**How to apply:** This is the target design for intake. The spec, schema and tests still use `un_built` and reject `not_built`, so they disagree with this ruling until the founder directs that change.
