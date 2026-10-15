---
name: acp-client-integration
description: Use when gating ACP file writes or compaction shows up.
category: development
---

# ACP client: gate agent file writes at the runner, and receive compaction events

An ACP agent sends a feature only when the client advertises it, and a file write reaches Metaform only along the path the adapter actually uses. Confirm both per adapter before trusting them.

## File-write gate
- Writes arrive as `fs/write_text_file` or `session/request_permission` of kind `edit`, `delete` or `move`. The per-adapter table is in [references/adapter-write-paths.md](references/adapter-write-paths.md).
- Check the lock before `allowed()`, so approve-all and every permission mode still refuse a locked write.
- Refuse with the agent's `reject_once` option, never `reject_always`, which makes Claude persist a deny rule. With no such option, cancel.
- A permission answer carries no text: steer the reason into the running turn, or send it as the next turn.
- Claude Code edit tools write to disk themselves. Send `_meta.claudeCode.options.settings.permissions.ask` for Edit, Write, MultiEdit and NotebookEdit on `session/new`, `session/load` and `session/resume`. That settings object replaces the adapter's own `CLAUDE_MODEL_CONFIG` settings.
- Codex asks only in read-only mode. Forcing read-only overrides the person's chosen mode, so ask the person first.
- Shell writes name no file in any adapter; say so in the report.
- Reads are never gated. Cache the refs the gate reads, drop the cache on non-dispatch `map.changed`, and show that a burst of reads costs one read.
- Only a live check with a real agent in bypass-permissions mode proves the Claude path; a fake agent proves the runner side only. Report which one ran.

## Compaction events
- Dispatch sends `clientCapabilities.session.compaction: {}` in `initialize`. Without it, the Claude wrapper falls back to a synthetic tool call titled "Compact conversation", and dispatch must treat that call as the compaction signal.
- `compaction_update` runs `in_progress`, then one of `completed`, `failed` or `cancelled`. The summary arrives from the `PostCompact` hook. A compaction still open at turn end closes as `cancelled`.
- `dispatch_claude` launches `claude-agent-acp` unpinned, so it gets the current release. `dispatch_codex` pins `codex-acp@2.2.2`, which has not been checked for compaction support.
- Verify the wrapper's `src/context-compaction.ts` at the pinned commit. Search `~/.npm/_npx` only; a `find /` search ran past the 60 s limit.
- Planned, not built: on `completed`, clear the session's "already sent" record so the next turn re-pushes what applies at the agent's current element. The ACP Python library predates `compaction_update` and needs an upgrade first.
