# MCP-003: draft amendments, memory beside the open category and metaform://tools by category

Ticket acedf98a (code.interface.graphical#112), 2026-10-18. Drafted by the worker; it lands in
`specifications/06-mcp-install.md` under MCP-003, after its 2026-10-15 amendment, only once the owner approves this
exact wording. The ticket asked for the amendments; per the amendment procedure the worker drafts and does not edit
`specifications/`.

What the code contradicts today: nothing in MCP-003 or any other record describes `metaform_catalog`'s categories at
all, so neither bullet supersedes an earlier sentence. The 2026-10-15 amendment ("a tool is listed small and explained
at use") still holds; these add to it. The code is uncommitted in the shared tree at the time of drafting
(`src/metaform/modules/mcp/catalog.py`, `server.py`, `resources/prompts.xml`).

## Bullet 1

- Amendment, 2026-10-18, ticket code.interface.graphical#112 (acedf98a): the memory tools are always listed. A session
  is listed `metaform_catalog`, the tools of the category it has open (or the tools its role starts with while none is
  open), and beside either the tools of each category in `catalog.BESIDE`, which holds `memory` alone; a tool already
  listed through the open category is not listed twice, and a listing that names no session is every tool the role is
  given, as before. `metaform_catalog` called with nothing marks such a category `(always listed)` and the open one
  `(open)`. The category was renamed from `remember` to `memory` in the same change, with its prompt element
  `category_memory`. Why: the memory instructions ask every agent to read the memories where it works and keep them
  current as it works, removing what is outdated; with the memory tools a category away, agents left memories unread
  and stale, and a person working with them asked why the memory tools were not available. Build: `BESIDE` in
  `src/metaform/modules/mcp/catalog.py`; `listed_names` and `run_catalog` in `src/metaform/modules/mcp/server.py`.
  Acceptance: `test_a_worker_is_listed_its_category_alone_and_opens_another_in_its_place` in
  `src/metaform/modules/mcp/tests/test_mcp.py`: a worker with ticket open is listed `map_work` and
  `memory_read_graph`, and the catalog shows `ticket (open)` and `memory (always listed)`.

## Bullet 2

- Amendment, 2026-10-18, ticket code.interface.graphical#112 (acedf98a): `metaform://tools` lists by category, within
  a strict limit. It gives every tool the agent's role is given, one line per category, `<category> — <what the
  category is for>: <tool>, <tool>, …`, where what the category is for is the head of the category's purpose, up to
  its first colon (and before its first ", and "), in the catalog's category order, a category in `catalog.BESIDE`
  marked `(always listed)`, a tool in two categories under each; then the modules' rules, MCP-031. The heading is the
  mcp module's `tool_index` prompt. The whole is at most `TOOLS_MOST` characters, 4,500. The rules block is worked
  out first and never cut: past the limit, only category lines are cut, to the last whole line that fits beside the
  `tool_index_more` pointer, the rules block and the blank line between them; the pointer, which sends the agent to
  `metaform_catalog search`, follows the last whole category line, and the rules block follows it, whole. Should the
  rules alone ever pass `TOOLS_MOST`, they are still given whole, past the limit. Why the rules outrank the tool
  lines: a cut tool line can still be found with `metaform_catalog search`, while the rules, such as the `[memory]`
  rule to record each memory at the RE, reach an agent only here, and the Join rule is how memory reaches the next
  agent at the right address. Every connect message links it as an instruction block, and nothing in it is
  pushed. Before, it listed every tool on the folder's surface under the prefix of the module serving it, each with
  the head of its description, with no limit. Why: an agent knows every tool it can reach and which category opens
  it, from one bounded read, without the descriptions it gets when it loads a tool. Measured on this project on
  2026-10-18: 4,258 characters for the person's session and 4,229 for a worker, both whole. Build: `tools_text` and
  `TOOLS_MOST` in `src/metaform/modules/mcp/server.py`, the `tools` entry of `BLOCKS` in the same file;
  `tool_index` and `tool_index_more` in `src/metaform/modules/mcp/resources/prompts.xml`, whose wording the system
  agent drafted on 2026-10-18 and the owner has yet to approve. Acceptance:
  `test_metaform_serves_its_glossary_alone_the_projects_own_and_the_tools_in_a_line_each` in the same test file: the
  orient line carries its purpose and `map_where`, `memory (always listed)` comes before the rules heading, and the
  text is within `TOOLS_MOST`; with `TOOLS_MOST` patched 1,000 below the text's length, the cut text is within it,
  ends with the whole rules block holding the `[memory]` rule, and has the `tool_index_more` line before the rules
  heading (ticket code.interface.graphical#11f, 64d8f2e3).

## Notes for the owner

- The 4,500 limit is recorded in the code's comment as the person's decision of 2026-10-18; the worker could not see
  those words in its session, so the bullet states the value and not its source.
- Both acceptance tests passed on 2026-10-18 (`uv run pytest -n 0 -rs … -k "tools_in_a_line_each or
  listed_its_category_alone"`: 2 passed, none skipped). No switch gates either behaviour.
- On this project the text fits whole, so the pointer line has not been seen in practice; the acceptance test
  covers the cut by lowering `TOOLS_MOST`. With `TOOLS_MOST` at 3,000 on 2026-10-18 the person's text was 2,457
  characters with the `[memory]` rule whole (#11f). Before #11f the rules block was what the cut dropped first.
