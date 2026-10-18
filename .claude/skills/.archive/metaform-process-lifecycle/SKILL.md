---
name: metaform-process-lifecycle
description: Use when a server runs old code or a check leaks processes.
category: development
---

# Processes: stale code after a fix, and what checks spawn

A running process keeps the code it started with, and a process a check spawns must not outlive that check.

## Stale processes after a fix
- A `metaform mcp serve`, dispatch runner or web server loads its code once. Before relying on a fix or telling a peer it is live, compare each process's start time with the changed file's mtime. Commands: `references/process-start-times.md`.
- A removed element is not gone while records still name its id (the work table's `target_id`, `work_links`, memory nodes). Before calling a removal complete, list those rows and the ops that touched the id after the removal.
- When something removed reappears, find its writer: each `ops` row carries the `session_id` that wrote it, so match it to a process start time. If the stores and a fresh process both lack it but the person still sees it, ask which surface shows it (2D map, another project, an open tab) before more tracing.
- Each agent runs its own `metaform mcp serve`, so a fix does not reach other agents' links until their sessions restart. Tell the person which servers still run old code. After a fix, make writes through the CLI (`uv run metaform ...`), which starts a fresh process, and read the element back.
- Do not restart a process other agents are working through without the person's go. Until it restarts, tell the agents on it not to make the call the fix changes.
- A runner outlives a store layout bump only if it hands over (code.dispatcher.agent#48, 2026-10-15). Runners started earlier keep the old behaviour until they restart.

## Checks and probes that spawn processes
The full pitfall list is in `references/spawned-checks-pitfalls.md`. These are the rules whose breach did real damage:
- Start every spawned process under a try/finally that terminates, waits briefly, then kills. Stop it by the pid recorded at start or by its process group (`start_new_session=True`, then `os.killpg`). Never `pkill -f` with the pattern in the script's own command line: it matches the shell and exits 144.
- A sweep that ends servers by name or port also ends other sessions' live servers. Before any sweep, check `/proc/PID/environ` for the owning home, and end only pids from your own run.
- Use a fresh empty scratch home, set the dispatch agent explicitly, and pop the inherited `METAFORM_WORK`, `METAFORM_SESSION`, `METAFORM_ROLE` and `METAFORM_NODE` first. Start a scratch web server with a PATH that holds no agent command, and never on a copy of `~/.metaform`.
- Before reporting, scan `/proc/*/environ` for the scratch home's `METAFORM_HOME=` path (errors to /dev/null) and stop any hit.
- Print the verdict only: `grep -E "^(ok|FAIL|all|[0-9]+ failed)|Traceback"`.

## Throwaway probes leave no test files
- Pytest collects any `test_*.py`, so an untracked probe file reruns the browser suite on every run and pollutes shared logs. Put probes outside the `tests/` folders, or make them copies that delete themselves on exit.
- Run a probe with `-n 0` and a `-k` filter for the one case under test.
- Delete the probe and any log it wrote when the ticket ends, and confirm with `ls` on the test folder before reporting done.
