---
name: claude-code-sandbox-settings
description: Use when editing Claude sandbox allowWrite or denyWrite.
category: development
---

# Claude Code sandbox settings

Build a Claude Code sandbox as a deny list plus a bounded allow list, and prove it live against the Claude Code build the adapter bundles, not the `claude` on PATH.

- A `denyWrite` folder wins over any `allowWrite` path inside it, so an exception cannot be carved out of a denied folder. Deny path by path: each unlinked file, each folder with no allowed file under it, each file that must stay read-only.
- Never send `allowWrite: ['/']`. On Claude Code 2.1.293 (bundled by claude-agent-acp 0.89.1) every command then fails with `bwrap: Can't mkdir /etc/claude-code: Permission denied`. The `claude` 2.1.301 on PATH accepted it, so a probe against PATH proves nothing. Allow the home and temp folders instead.
- The SDK passes settings as one argument, and Linux caps one argument at 128 KiB. Keep the deny list under 96 KiB; past that, deny whole folders, largest first.
- A denied path that is a file cannot be written, removed or moved (EBUSY); a denied path that does not exist cannot be created.
- Prove each rule with one write to a denied file, one to an allowed file, and one trivial command, run through `claude -p` in bypassPermissions in a scratch copy. A unit test of the list does not show what Claude Code enforces.
- While a command runs, the sandbox shows empty mount points in the project root, so `git status` lists them as untracked. They are gone when the command ends; do not treat them as project changes.
- The list and settings are built by `denied_writes` and `held_settings` in `src/metaform/modules/dispatch/runner.py`. Change them there, then re-run the live probe.
