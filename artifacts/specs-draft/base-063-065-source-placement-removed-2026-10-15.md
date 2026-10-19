# Draft amendments: the source_placement module and the map's code layer removed

Drafted 2026-10-15 by the worker on ticket code.analyzer.refactoring#1a (9798b73d7422440c9d224f77a7b58e98). The ticket
asked for the spec records to be amended directly; the spec-amendment rule has a worker draft the wording here and the
owner land it. Each bullet goes at the end of its record in `specifications/04-chassis-modules.md`, after the record's
last amendment.

What the code now does: the `source_placement` module (BASE-063's `refactor` module, renamed) is deleted with its
verbs `intake`, `associate`, `extend`, `status`, `pending` and `resolve`, its `intake.finished` subscriber, its
`code.functions` capability and its tree-sitter dependencies. The map module's code layer is deleted with it: the verbs
`code-import`, `code-search`, `code-trace`, `code-context`, `code-gaps`, `code-changes` and `code-link`, `code_index.py`
(the client of codebase-memory-mcp's `list_projects` and `query_graph`), `code_preparation.py` (the `code.inventory`
capability), the Code pane, the brief's code line, and the tables `code_files`, `code_symbols`, `code_edges` and
`code_links` (map Tables version 16). `intake.finished` is still published; no shipped module subscribes to it.

## BASE-063

The sentences the code now contradicts: "An optional `refactor` module serves an Axiom intake procedure..." and
"Reuse the existing layer, item and code-link operations."

- Amendment, 2026-10-15, ticket code.analyzer.refactoring#1a (9798b73d), the owner's decision: the refactor module, last named `source_placement`, is deleted with its intake procedure and tools, and so are the map's code-link operations and code layer it reused. The refactor function was overzealous and the code-graph server it relied on is not native to Metaform's design. A file is placed on the map by its ref in the sources layer, which an agent must add before it writes the file (code.dispatcher.agent#3d). The record is kept as history; nothing serves it.

## BASE-064

The sentence the code now contradicts: "Refactor preparation offers an optional Jev pass..."

- Amendment, 2026-10-15, ticket code.analyzer.refactoring#1a (9798b73d): the bulk classification pass is deleted with the refactor module (BASE-063 as amended); no `associate` verb remains. Jev's other decision points, `metaform.jev`, are unchanged.

## BASE-065

The sentences the code now contradicts: "Completing a code intake automatically follows it with provider
classification...", "The refactor module ships enabled." and "The refactor module owns the Tree-sitter runtime ... Map
consumes that capability"; the 2026-10-14 amendment's "so the extension runs for the base as it does after a first
intake" no longer holds, since no extension runs.

- Amendment, 2026-10-15, ticket code.analyzer.refactoring#1a (9798b73d), the owner's decision: the extension is deleted. A finished code intake, and a verification pass that adds `code.*` elements (amendment of 2026-10-14, ticket 59573056), still publishes `intake.finished`, but no shipped module subscribes, so nothing follows it and `intake finish` no longer declares open world. Its result no longer names `map code-import` in `next`. Evidence of no use: no call to the code-graph tools and no `map code-*` call across 400 Claude Code sessions, and 44% of placements fell to the folder fallback. Placement is now the file ref on the map (code.dispatcher.agent#3d). The run folders already written under the home's `projects/<id>/source_placement/` are left in place; nothing reads them.

## Not in a requirement record

The map's code layer (`code-*` verbs, P165 and P167) has no record of its own in `specifications/0*.md`; it is described
in `specifications/CHANGE-ORDER-2026-10-08.md` section 5.1 and in the map README, which now says the code layer's tables
were dropped at map version 16. The `<scope>@<layer>` read of P165 stays for every other layer.
