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
- To prove a command touches nothing outside its own home, build the wheel, install it in a fresh venv, and run it under `unshare -rn` (network blocked, loopback only) with `strace -f -e trace=file,network`. Then summarise the log: the processes seen, every real-home path outside the command's own folder, and every `connect()` address. A `mkdir` of the real home that returns `EEXIST` is not a write.
- Snapshot the real home read-only before and after the run (settings, folders, module state, project stores) and diff the two. Record "no difference" only when the diff is empty.
- Strip the display and any harness variables from the command's environment (`env -u DISPLAY -u WAYLAND_DISPLAY`) and set `BROWSER=true` so nothing opens on the person's screen. Feed stdin from a silent pipe and check the exit code after Ctrl+C.
- Compare before and after by building HEAD in a worktree: `git worktree add --detach /tmp/<dir> HEAD`, run the same probe once with `PYTHONPATH=<worktree>/src` and once with the working tree's `src`, then `git worktree remove --force` it. Create the scratch home folder (`mkdir -p`) before pointing `METAFORM_HOME` at it; a home path that does not exist yet fails the probe and looks like a product bug.
- Read the README the build actually shipped, not the generator's output: `unzip -p <zip> '*/README.md' > README-as-shipped.md` in the artifacts folder, then count the expected strings in that file and follow it.
- Exercise a failing agent by pointing its runner setting at a binary that exits at once (`dispatch_claude=/bin/false`). Check that the failure says why, with the next step, and that the session row ends with that reason, rather than reporting the agent as started.
