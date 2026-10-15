# Adapter write paths (verified 2026-10-15 from installed adapter code, not live runs)

| Adapter | Writes files itself? | Asks via session/request_permission | Gate reaches it |
|---|---|---|---|
| claude-agent-acp 0.89.1 | yes: Edit, Write, MultiEdit, NotebookEdit | only through canUseTool; bypassPermissions, acceptEdits and user allow rules skip it; explicit ask rules reach canUseTool in every mode | yes, once the ask rules are sent in _meta.claudeCode.options.settings |
| codex-acp 2.2.2 (over codex app-server) | yes | only in read-only mode (item/fileChange/requestApproval); workspace-write, agent and agent-full-access write with no request | no, unless the runner forces read-only, which overrides the person's mode |
| gemini-cli | no: writes through the client's fs/write_text_file when offered | n/a | yes |

Shell writes (Claude Bash, Codex command execution) name no file in any adapter.

The adapter's own comment in acp-agent.js canUseTool is the source for the ask-rule behaviour; re-check it when the adapter version changes.
