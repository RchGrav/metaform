---
name: metaform-operations
description: Use when restarting the Metaform web GUI or MCP server.
category: development
---

# Metaform operations: restarts

- Web GUI: from the project folder run `uv run metaform web restart`. An open page reconnects through its live stream and offers a reload.
- MCP server: there is no restart verb. Each agent session starts its own `metaform mcp serve` and keeps it for the session's life.
- `/mcp reconnect` works only in a Claude Code terminal. It is not available in a session the Metaform runner started over ACP.
- To give a runner-started agent the new code, stop that agent on the page and start it again. Say so in one line; do not claim a restart you did not run.
