---
name: metaform-agent-attention-signals
description: Use when the page says an agent seems stuck or spinning.
category: development
---

# Attention alerts mean no progress was reported, not that the agent is frozen

The page's "seems stuck" comes from `noticeAttention()` in `web/page/app/figures/attention.js`. It fires only for an active dispatch signal named in `RESTLESS` (`web/page/app/figures/walk.js`: spinning-calls, spinning-time, repeated-failure, drift) on a running session. not-smooth and incomplete prompt do not raise it.

- `spinning-calls` means many tool calls with no `map work op=step`. `spinning-time` means N minutes with no step. The agent clears both by reporting a step; stopping it is not needed.
- Before telling the person an agent is stuck, check it with the MCP tool `dispatch_sessions` (pass the work id, `thread=false`) and read its `activity`. The CLI `metaform dispatch sessions --json` printed text before its JSON and failed to parse.
- Report what the signal is, what clears it, and whether the agent is still working. Do not stop a running agent on the alert alone.
- An `incomplete prompt` signal can stay active after the check that raised it is removed. Nothing clears it automatically; it can be cleared by hand.
