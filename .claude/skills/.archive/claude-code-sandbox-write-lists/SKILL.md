---
name: claude-code-sandbox-write-lists
description: Use when building a sandbox allowWrite or denyWrite list.
category: development
---

# Claude Code sandbox write lists

Build a dispatched session's write sandbox as deny entries plus a short allow list of roots. Never put `/` in allowWrite.

- A denyWrite folder beats every allowWrite path inside it. A linked file, `.venv` or `.git` under a denied project stayed read-only in the live proof. So the deny list names the unlinked files, ignore-listed paths and folders with no linked file, path by path, and keeps tool folders (`.git`, `.venv`, caches, `node_modules`) out of it.
- allowWrite holds only the home folder, the temp folders, `/tmp` and `/var/tmp`. `allowWrite ['/']` makes Claude Code 2.1.293, the build claude-agent-acp 0.89.1 bundles, fail every command with `bwrap: Can't mkdir /etc/claude-code`.
- A denied existing file cannot be written, removed or moved (EBUSY). A denied path that does not exist cannot be created, so a new file under an unknown name in an allowed folder stays writable. State that gap in the report; the sandbox cannot close it.
- The SDK passes settings as one argument, which Linux caps at 128 KiB. Past about 96 KiB of deny entries, deny whole folders instead, largest first.
- Prove a list in a live session before relying on it: [references/sandbox-probe.md](references/sandbox-probe.md).
