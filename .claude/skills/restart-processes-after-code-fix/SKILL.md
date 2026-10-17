---
name: restart-processes-after-code-fix
description: Use when a server or runner started before a code fix.
category: development
---

# A running process keeps the code it started with

A `metaform mcp serve`, dispatch runner or web server loads its code once. After a fix lands, anything it does still runs the old code, including a link or write an agent makes through it.

- Before relying on a fix, or telling a peer it is live, compare each process's start time with the changed file's mtime. A process started earlier runs old code. The commands are in [references/process-start-times.md](references/process-start-times.md).
- A removed element is not gone while records still name its id. Before calling a removal complete, list the rows that point at its id (the work table's `target_id`, `work_links`, memory nodes) and the ops that touched it after the removal; a record left behind can keep an element on the page or make the agent that holds it re-create it.
- When something you removed reappears, find its writer before tracing the render. Each row of the store's `ops` table carries the `session_id` that wrote it, so a write after the fix names the session to check; match that session to a process start time. If the stores and a fresh process both lack the element but the person still sees it, ask which surface shows it (2D map, another project, an open tab) before more tracing.
- Tell the person which processes are old and what restart clears them. Do not restart a process other agents are working through without the person's go.
- Until the old processes restart, tell the agents on them not to make the call the fix changes, and say why.
- A check that matters is one the new code runs in a fresh process, not one through a server that predates the fix.
- A runner outlives a store layout bump only if it hands over. Since code.dispatcher.agent#48 (2026-10-15) a runner that meets a newer store, while the code on disk has changed, ends its agent and a successor resumes the same session; runners started before that change keep the old behaviour until they restart. To prove a hand-over, copy `src` to a scratch home, raise the layout with that copy, send one message to a fake-agent runner, and check the old pid exits, the same session id continues, and the message reaches the agent.
- Every agent runs its own `metaform mcp serve`, so each one stays stale until its agent's session restarts. A fix does not reach other agents' links when it lands; tell the person which agents' servers still run the old code before they link or write anything. A stale link can leave an empty element behind (a link at a new address creates it) that the base refuses to remove, so list the elements a stale link created and report them for cleanup.
- A write through a stale MCP server runs the old code too. A `dispatch link` sent through an old server moved a ref to a shared ancestor prefix that the fix had already stopped doing, and the store had to be repaired. After a fix, make writes through the CLI (`uv run metaform ...`), which starts a fresh process, and read the element back to confirm where it landed.
