---
name: commit-every-test
description: Feature commits are automatic, test then commit and push before the founder tests; the rule is in AGENTS.md
metadata:
  node_type: memory
  type: feedback
  originSessionId: b09b07b3-bc99-40d2-8e74-5d0c4363eefb
  modified: 2026-11-02T21:35:02.322Z
---

After a test where the code seems to operate, make a feature commit and push it automatically, so the exact prompt and code that ran can always be seen.

**Why:** On 2026-11-02 nearly all the work was uncommitted, and neither the founder nor the agent could say cleanly what had changed or what had been tested.

**How to apply:** Follow the Feature commits section of `AGENTS.md`, which the founder placed there on 2026-11-02. Commit only the files that belong to the test. See [[owner-files-reference]].
