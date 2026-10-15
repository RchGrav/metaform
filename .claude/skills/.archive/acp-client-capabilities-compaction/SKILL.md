---
name: acp-client-capabilities-compaction
description: Use when ACP compaction or "Compact conversation" appears.
category: development
---

# ACP client capabilities and compaction

An ACP agent only sends a feature the client advertises. To receive structured compaction events, dispatch must send `clientCapabilities.session.compaction: {}` in `initialize`. Without it, the Claude wrapper falls back to a synthetic tool call titled "Compact conversation", and dispatch must treat that call as the compaction signal.

- **Lifecycle:** `compaction_update` runs `in_progress` then one of `completed`, `failed`, `cancelled`. The summary arrives from the `PostCompact` hook. A compaction still open at turn end is closed as `cancelled`.
- **Which adapter runs:** `dispatch_claude` launches `npx -y @agentclientprotocol/claude-agent-acp` unpinned, so it gets the current release. `dispatch_codex` pins `@agentclientprotocol/codex-acp@2.2.2`, which has not been checked for compaction support.
- **Verify before relying on it:** read the wrapper's `src/context-compaction.ts` at the pinned commit. To find the installed copy, search `~/.npm/_npx` only; a `find /` search ran past the 60 s limit.
- **Planned, not built:** on `completed`, clear the session's "already sent" record so the next turn re-pushes what applies at the agent's current element. The ACP Python library predates `compaction_update` and needs an upgrade before dispatch can parse it.
