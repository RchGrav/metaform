# Assigned tasks

`user_agent` is the first named task. Its canonical instruction file is `resources/user_agent.txt`.
Only the literal `{project}` placeholder is bound. The authored text is otherwise unchanged.

- `list` discovers task definitions and skill metadata without loading bodies.
- `read name=user_agent` loads the task instructions for direct self-execution.
- `assign name=user_agent` starts an interactive dedicated agent.
- `assign text="..." skills='["skill-name"]'` assigns explicit work with selected skills.
- `get id=...`, `update id=... responses=...`, and `cancel id=...` control its durable execution.
- `configure id=...` lists native agent settings. Add `setting=mode value=plan` when the adapter advertises that mode.

A target `folder` selects the working directory. A registered target project owns its assignment and instructions.
No ticket, organizational role, commission, creator ownership or review workflow is required.
The default dispatch system entry point opens this User Agent task. Named tasks beyond it are defined separately,
under user direction. No other old roles are automatically converted into skills or tasks.

MCP execution follows the Tasks extension, stable schema 2026-07-28:
https://modelcontextprotocol.io/extensions/tasks/overview
https://github.com/modelcontextprotocol/ext-tasks/blob/main/specification/2026-07-28/tasks.md

The task is stored before launching ACP and before returning a flat CreateTaskResult. Clients must negotiate
`io.modelcontextprotocol/tasks` for asynchronous launch. Standard `tasks/get`, `tasks/update`, and `tasks/cancel`
are served through MCP. Polling is client-driven. Native session events update durable status without a server polling loop.
Input requests keep unique keys. Responses are durably queued and duplicates are ignored. Cancellation is cooperative.
Native/tool failures complete with `isError`; JSON-RPC failures use failed. Terminal records never change.

Explicit ACP permissions are forwarded as native input requests. The extension's capability negotiation and
transport authentication do not impose organizational authority on agents.
