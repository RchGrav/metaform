# metaform knowledge kit

Reference libs and task skills for the metaform MCP server. A lib is loaded once per agent; a skill names
the libs it needs and loads only what the agent is missing; a skill can be called by an agent, run by a
person as `/metaform:<skill>`, or handed to a fresh agent as a task by nonce.

Start with `MCP-IMPLEMENTATION.md`. Contents:

- `libs/` four shared texts: `lib_axiom` (grammar), `lib_metaform` (the system), `lib_workflow` (the rules), `lib_quality` (lint, honesty, plain writing)
- `skills/` five playbooks, each with its procedure, checks and task examples: `scan`, `write_workflow`, `import_workflow`, `workflow_efficiency`, `prompt_efficiency`
- `sources/` the two original task prompts the write and import skills were folded from
- `module/knowledge/` the metaform module: declaration, `resources/prompts.xml`, tests
- `server.py` the same tools as a standalone MCP server, for hosts without metaform

Who loads what:

| | lib_axiom | lib_metaform | lib_workflow | lib_quality |
|---|---|---|---|---|
| scan | | | | |
| write_workflow | x | x | x | |
| import_workflow | x | x | x | |
| workflow_efficiency | x | x | x | x |
| prompt_efficiency | x | | | x |

An agent that already holds `lib_axiom` and `lib_metaform` and is handed `import_workflow` loads one more
thing, `lib_workflow`, then the skill itself, and nothing twice.
