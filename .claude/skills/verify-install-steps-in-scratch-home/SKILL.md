---
name: verify-install-steps-in-scratch-home
description: Use when testing install steps or a tester README.
category: development
---
# Verify install steps in a scratch home

Follow the written guide literally, step by step, as a new user would, in an environment that cannot touch the real install: a scratch HOME, a clean environment, and a copy of any tool the guide relies on. Record the exit code of every step.

- Run the steps under `env -i HOME=<scratch> PATH=<copied tools>:/usr/bin:/bin TERM=dumb bash <script>`. Copy `uv` and `uvx` out of the real `~/.local/bin` first, because that folder also holds the real tool under test.
- Give the build and the app their own scratch data home. Never point them at the real home, and use a free scratch port for any "other port" branch of the guide.
- After each step print `[exit $?]`, then grep for non-zero exits. Name every expected failure in the script, such as "command not found" before the guide's own remedy runs, so an unexpected one stands out.
- Finish with the guide's own uninstall, then confirm nothing is left: the command is gone and the home folder is removed.
- A harness notice can still appear in the scratch shell, because detection walks process ancestry. Report it as seen; do not call the step clean.
- Keep the exact guide copy and the transcript as evidence, in an ignored artifacts folder or the ticket.
- When an install or start step writes an AI tool's config file (Claude Code's project `.mcp.json`), read it back with `claude mcp get <name>` run in that folder. It reads the file with no model call and reports the scope, type, command, args and pending approval. Then start the written command once from the scratch install's interpreter (`metaform.probe.probe([...], cwd=...)`) and record the tool count it reports.
- List what was not exercised, such as a live AI-tool connection or a command that opens a browser. Never claim it passed.
