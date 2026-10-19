# Agent context cost: wording for Rich to approve

Ticket code.server.tool#11 (2f55c234), 2026-10-15, built from artifacts/critic/2026-10-15-round7/agent-surface.md.
Everything below is new wording the build needed. Nothing here is approved yet; each line can be changed or emptied.

## New prompts in `src/metaform/modules/mcp/resources/prompts.xml`

- `<module_guide>The <module/> module's rules, given once in this session, each with its reason:</module_guide>`
  The heading of the module rules a tool's result carries the first time a session calls any of that module's tools.
  Empty leaves the rules out of results (they stay in metaform://tools).
- `<tool_guide>How to use <tool/>, given once in this session:</tool_guide>`
  The heading of what the list cut from a tool: the rest of its description, each shortened argument's whole help,
  the verb's details and examples. Empty switches the guidance off.

## Tool descriptions written in code (`src/metaform/modules/mcp/server.py`)

- `metaform_set`: "Save settings for this folder, each given as name=value. Called with none, it lists the settings an
  agent may change, each with its help, choices and current value." (the critic's wording, R1)
- `project` argument help: "Another registered project's id." (R2; it was "A registered project id, in place of the
  folder's, for this call.")

## Text moved, not reworded

- Descriptions over 160 characters are listed as their first sentence and their caution; the rest moves word for word
  into the tool's guide. A first sentence over 200 characters is listed to its first colon or semicolon.
- Argument help over 80 bytes is listed as the head of its first sentence (a scope before a colon, such as
  "list, add and edit:", keeps the clause after it), cut back at a comma or a word, ending in "…"; the whole help is in
  the guide.
- "As metaform … does" cross-references are dropped from listed descriptions, and a command line a description names
  (`metaform map activate`, `map activate <its name>`) is written as its tool's name.

## Left for Rich (wording or policy, not built)

- R8: the connect message is 1,816 characters in a mapped project; the report's target is 1,000. Its first-run steps
  are lettered b, c, d once step a (register) is dropped; the module line says "web start" where the tool is
  `web_start`; the `metaform://tools` line could be left out for a client that defers tools. All are his text.
- R8.3: the report says Claude Code 2.1.296 and later keep 4,096 characters of server instructions; the ticket and
  CLAUDE.md say 2,048. Unchanged until he decides.
- R1 step 4: making `connect_instructions`, `skill_index`, `glossary_register`, `glossary_bytes`,
  `node_summary_bytes`, `modules`, `mcp_*` and `report` person-only.
- Finding 9: the glossary's "Metaform MCP ready." first statement against the first-run block's question.
- R6.1-3: splitting `map_work` into `map_work` and a `map_board` listed only to the system agent. Not built: the
  orchestrator session sets `agent=claude` on tickets and arranges the board through `map_work`, and is not a session
  `dispatch_system` starts, so the split would take those controls from it.
- R10: a 28-tool core list.
