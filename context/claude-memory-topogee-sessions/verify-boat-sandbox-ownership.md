---
name: verify-boat-sandbox-ownership
description: "Never stop, prompt into or delete a Boat sandbox unless this session created it, proven by the id returned from the create call"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 64f72fa6-1e3a-44a5-9ed3-c89e8167ad8a
  modified: 2026-10-30T16:07:41.072Z
---

Only act on Boat sandboxes whose id came back from a create or fork call in this session. The founder uses the same account concurrently, so `boat list` can show their sandboxes, and createdBy does not distinguish them from the assistant's.

**Why:** On 2026-10-30 the assistant's `boat new` failed on the 2-sandbox limit and it did not notice. It assumed two sandboxes from `boat list` were its own, ran prompts in one, stopped it, and permanently deleted both. They were the founder's. The ttl and machine type already disagreed with what the assistant had requested.

**How to apply:** Check the create call's result before going on, stop if it fails, and compare a sandbox's attributes to the request before touching it. Create with `--name` so ownership is explicit. Never bypass delete confirmation with `--yes` on an id not proven to be this session's.
