# Changelog

Each change to the dispatch module, newest first.

## Unreleased

- One agent per glyph, VIEW-040: a runner started on a ticket with an agent glyph works the glyph's tickets one after another in board order, a session for each, the next taken when the one before is done; `start` and `run` refuse a ticket whose glyph's agent is at work and name the ticket it works. The glyph is read through the base's `work_reads`. The fake agent names each process's session by the sessions made before it, and its `done` mode closes the ticket its prompt names.
- The runner hears `map.changed` from other processes through the base's listener, `ctx.listen`, BASE-053. dispatch's `map.changed` subscriber, `relayed`, `RUNNER` and the control port's `changed` request are gone; the port takes `message` and `stop`.
- A question a dispatched agent asks itself with `map ask` is told to it when the person answers it, as the `answered` prompt, BASE-052. The runner knows the question by its id in the output of one of the agent's own tool calls, made no earlier than that call began.
- A ticket's sessions show on its work record, BASE-035: dispatch's `work_read` adds `{"sessions": [...]}` under `dispatch` in `metaform map work id=<id>`, each session from dispatch's own table without what only reaches a running session.
- dispatch reads its prompts with `metaform.prompt_files`, now part of the public base, BASE-004 and MCP-031, and no longer carries its own copy of the reader.
- dispatch is made from the template at its changelog's Unreleased contract, BASE-019 and BASE-052: `start`, `run`, `message`, `stop` and `handoff`, the `dispatch_claude`, `dispatch_codex` and `dispatch_gemini` settings, the `dispatch` layer, and a `map.changed` subscriber.
