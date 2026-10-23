---
name: metaform-catalog-tool-calls
description: Use when calling dispatch_* tools through metaform_catalog.
category: development
---

# Calling Metaform orchestration tools through the catalog

Orchestration tools are not direct MCP tools: reach them through the metaform_catalog tool. Search first, then call; do not guess a tool name.

- Find the exact name with metaform_catalog, its search field set to a few words, plus its module field when known. The search matches approximate names and returns each tool's signature and its metaform module tools resource.
- Call it with metaform_catalog, the tool field set to the tool's name and the arguments object holding its parameters.
- A note from dispatch_note reaches the receiving agent after the turn in flight and is kept on every ticket it touches. Keep its summary to one line, and say in the text whether the receiver must act.
- dispatch_link answers linked true on a new link and already linked on a repeat; a repeat is harmless.
