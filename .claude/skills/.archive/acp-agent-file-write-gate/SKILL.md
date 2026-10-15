---
name: acp-agent-file-write-gate
description: Use when gating ACP agent file writes or Claude Code Edit.
category: development
---

# Gate ACP agent file writes at the runner, before automatic approval

A file write reaches Metaform only along the path the adapter actually uses: `fs/write_text_file`, or `session/request_permission` of kind `edit`, `delete` or `move`. Confirm that path per adapter before trusting a gate. Per-adapter detail: `references/adapter-write-paths.md`.

- Check the lock before `allowed()`, so approve-all and every permission mode still refuse a locked write.
- Refuse with the agent's `reject_once` option, never `reject_always` (Claude would persist a deny rule); with no such option, cancel.
- A permission answer carries no text: send the reason steered into the running turn, or as the next turn.
- Claude Code edit tools write to disk themselves. Force them to ask by sending `_meta.claudeCode.options.settings.permissions.ask` for Edit, Write, MultiEdit and NotebookEdit on `session/new`, `session/load` and `session/resume`. This settings object replaces the adapter's own `CLAUDE_MODEL_CONFIG` settings.
- Codex asks before file changes only in read-only mode. Forcing read-only overrides the person's chosen mode, so ask the person before doing it.
- Shell writes name no file in any adapter; no per-file gate reaches them. Say so in the report.
- Reads are never gated. Cache the refs the gate reads and drop the cache on non-dispatch `map.changed`; a test should show a burst of reads costs one read.
- A live check with a real agent in bypassPermissions is the only proof for Claude; a fake agent proves the runner side only. Report which one ran.
