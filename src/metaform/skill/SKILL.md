---
name: metaform
description: Use when the Metaform MCP server is connected, when working in a project registered with Metaform, or when the user mentions Metaform or a functional map. Metaform holds the project's functional map and agent instructions.
---

Metaform keeps a project's functional map: what each part is for, who receives what it does, and how.

Metaform has two interfaces: its MCP server and the `metaform` command line, which mirrors many of the server's functions. When the MCP server is available, it is your primary interface: work through its tools, whose instructions are already in your context. Each command is its own tool, named `<module>_<command>`, such as `map_where`, with its arguments in the tool's input schema; Metaform's own commands are `metaform_<command>`, and `metaform_instructions` with a module gives that module's full instructions. A tool error ends with one Next line: follow it.

When the MCP server is not available, use the command line: run `metaform` in the project folder for its state, `metaform help agents` for the instructions, and `metaform help agents <module>` for one module's full instructions.
