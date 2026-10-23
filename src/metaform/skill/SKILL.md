---
name: metaform
description: Use when the Metaform MCP server is connected, when working in a project registered with Metaform, or when the user mentions Metaform or a functional map. Metaform holds the project's functional map and agent instructions.
---

Metaform keeps a project's functional map: what each part is for, who receives what it does, and how.

When its MCP server is available, use it as your primary interface. Follow the tool names actually advertised by your host. A command such as `map_where` may be exposed directly, possibly with a host prefix, or reached through the advertised catalog gateway with `tool="map_where"` and `arguments={...}`. Use a known command directly through that route. Use a focused catalog search or module listing when you need to discover a command or its argument schema.

Tool instructions are delivered before execution when they are due. If a call returns `instructions_required` with `executed=false`, read its instruction URI or follow its exact `read_tool` command and arguments through the advertised route, then repeat the operation. Carry any returned `session_handle` through the read and subsequent calls. Reading a guide records delivery, not comprehension or compliance: apply its instructions to the requested work. Changed effective instructions require another read; unchanged delivered content is reused.

Read the applicable project instructions, functional map, source request and relevant knowledge for your assignment. A tool guide explains tool use; it does not replace that functional understanding. Module instructions are available through `metaform_instructions module=<id>` or `metaform://instructions/<id>`. Follow the concrete next step returned with an error.

Reusable methods can run in the current informed context: `orchestration_methods` lists their families and `orchestration_apply` loads a selected method with per-context delivery receipts. The `facilitator` skill is the entry point for finding, reusing and creating specialist expertise. Loading a method or publishing expertise keeps the current assignment; claim, delegate, call and handoff assign execution separately. Use continued episodes for related work and separate agents for useful parallelism, requested independence or genuine isolation.

When the MCP server is not available, use the command line: run `metaform` in the project folder for its state, `metaform help agents` for the instructions, and `metaform help agents <module>` for one module's full instructions.
