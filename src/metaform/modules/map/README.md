# map

Reads and writes a project's functional map and its layers, on the CLI and as MCP tools.

## Purpose

The map module exposes the data access object's reads and writes as verbs, so agents read the map and build knowledge layers through tools, and people through `metaform map`. It ships enabled.

## Template version

Started from template 0.2.0.

## Declaration

`SUPPORTED_OS = ('linux', 'macos', 'windows')`, `DEPENDENCIES = ()`, `SHIPS_DISABLED = False`. `MODULE` declares the verbs of BASE-038.

## Common base used

`metaform.module` for the declaration and `Context`, `metaform.settings` for `--raw`, `metaform.data` for every read and write.

## Prompts

`resources/prompts.xml` holds `instructions`, `map is active.`, listed in the instructions agents read under "modules available.", MCP-031.

## Verbs

`markdown` writes the map, or with `address=` the part around one address, as a short Markdown document: each element's name, address, role and paths, from the sources layer, and each join's receiver, the elements it holds, its ef and its purpose, MAP-052, and `file=` writes the document to a file. It is a command only and never a tool.

`mermaid` writes the map, or with `address=` that element and the elements one join away, as a Mermaid flowchart, P063: the elements and joins the web GUI's 2D map draws, each element a node named by what the project calls it, else its short name, over its address, and an edge for each element each join holds, pointing the way the join's information goes, its ifd: from the receiver to the element served when it sends or nothing is recorded, from the element to the receiver when it receives, `<-->` when both, as the 2D map's arrowheads point. The CQUs and the DE carry the classes `cqu` and `de`. Its YAML frontmatter gives the title and the 2D map's layout, ELK by network simplex. `direction=TB`, the default, or `LR`; `leave_out=` roots not drawn, comma-separated; `labels=purpose` or `labels=ef` puts each join's on its edges; `file=` writes it to a file such as `map.mmd`, which GitHub, VS Code and Obsidian draw. Mermaid with its default limits refuses a diagram over 50,000 characters or 500 edges, and those limits cannot be raised from the diagram, so such a diagram says so in a comment at its top, and with `file=` in a notice. The web GUI's Export menu saves and copies the same flowchart, written by the same writer, `metaform.outline.mermaid`, with the page's layers, the direction its 2D map runs and the roots it leaves out.

Start with `roots`: the map's entry, the CQU and the DE with the joins they receive, and every root element; `where` with an empty address returns the same. Handed an address, start with `where`: one read of the address returns the element with its address read through name_length and its role, its `sources`, the sources layer's refs, `provides`, what relies on it, each join it provides for by its receiver with the receiver's purpose and its refs, `receives`, what it relies on, each join it receives by its providers with its purpose and refs, and, the first time an agent session reads it, `around`: a small tree of how much is held at it and at its direct neighbours, memories, open work, messages, layer items, earlier runs and properties, with the call that reads each, MCP-039. Later in the session only a count that changed is said, under `changed`. `contents=true` returns what is held there in full: the joins with ef, ifd, elements and layer, `work`, its open work records with condition, note and task, `layers`, what the layers in context hold at it, as `node` gives them, messages, properties and each module's node read. Ids and empty fields are left out, all but the element's id, which `history` takes, and each ticket's and open message's id; `full=true` keeps them all, with the contents. Under the node the tree names what is new there: `Latest: <address>#<n>  <title>`, the last number taken at it with its item's title, and `the last session added #a–#b`, the numbers the last agent session other than the reader's own took there, from the project's number log, which records the session that took each number. The CLI, the node's `metaform://<address>` resource, the ticket read, dispatch's hand-off and the page's Brief all show it, since all are this read. The tree's words are the `around_*` prompts. An address that is no element in context stops with `No element <address> in context here.` and `Next: metaform map children <address>`. Reads: `roots`, `where`, `element`, `joins`, `identity`, `children`, `layers`, `layer`, `node`, `context`, `links`, `citing`, `history`, `stack`, `metaforms`, `search`, which finds the items, memories and knowledge values, whose value holds every word of the text, and `work`, the work records, the condition of an element or a join kept apart from the map, MAP-046. Writes: `work` with `op=add`, `op=edit` and `op=done`, `knowledge` with `op=` and `layer=` on every call, `tag`, `untag`, `select`, `mask`, `clear`, `hide`, `unhide`, `reexamined`, `add-metaform`, `activate`, `answer`, and `approve` on the CLI only. `critic` starts a blind-spot critic run, fast mode by default, critic mode with `--critic`: it creates the run's blind-spot layer, provenance role `critic` with `blinded` true, or false with `--critic`, and returns the critic prompt, `blind_spot_challenge`, then `critic_fast` or `critic_critic` with the layer and the whole metaform as `markdown` prints it, LAYER-014. `challenges <layer>` returns the answer prompt, `answer_challenges`, with each challenge of that layer, its state, the node it is attached to and its text, LAYER-015. Each verb returns its operation's result; every join shows the layer it comes from, and every element and join its `open_work`, the conditions of its open work records. A write that does not fit is stored as given and its result carries `notices`. A field that is missing is stored empty and named in a notice; a `knowledge` or `work` call stops only when it is missing a field its record cannot be stored without, such as a join's receiver or a work record's node, the table in BASE-038. `knowledge op=add-element` takes an element's `address`, `name_length`, `name` and `role`. `op=add-join` takes the join's `receiver`, `elements`, the elements that serve its purpose, `purpose`, `ef`, `ifd` and `type`; refs live in the sources layer, never in the metaform. `knowledge op=edit` and `map refine` move a join with `receiver` and change the elements it holds with `elements`; the join keeps its id, MAP-003. They change a join's `purpose`, `ef`, `ifd` and `type` too. An element cannot be moved: an `address` given to them for an element is not applied and is named in a notice, MAP-015. `work` names its node as `refine` does: a join by `receiver` and `provider`, an element it holds, an element by `address` or `node`; `links` take the same as objects. `ask` and `tell` take `node` first, an element's address; `provider` beside it names the join that element holds as receiver, the one holding that provider. A work record is missing, broken, flawed, enhancement or exclude. missing means the thing does not exist at all, or is not built yet. A thing that exists but is wrong is not missing: it is broken (not working, not connected, orphaned), flawed (works but is not right) or an enhancement (works, could be better); exclude is outside the scope, or conflicts with a superseding specification. A work record has a note and a task, held and reviewed flags, and its resolution once done; it is attached to one object, has no layer, and never changes the map. Tools are `map_<verb>`.

Move a ticket to another node with `work op=edit id=<work id> node=<address>`, or name its destination join by `receiver` and `provider`. Its id, ownership, progress, completion and reference links are kept; `links=` edits those references explicitly. Move an existing question or message with `messages op=move id=<message id> node=<address>`, with `provider` and `address` as in `ask` and `tell`; its suggestions, answer and closed state are kept. These operations carry records to a better-addressed functionality without changing element identity, MAP-015. Without `op`, `messages` still lists them.

`add-base`, `activate` and `collapse` each change which base is the project's active map, so each carries a caution: the active map changes for every agent and the page of that project, and the previous base is kept, `map activate <its name>` switching back. Over MCP the call runs only with `confirm` true, or the person's consent to the form, as `remove-base` does.

`collapse <name> [project=<id>]` writes the current functional map into a new metaform with one finished `intake` layer and makes it active, LAYER-026. Each current element and join appears once with its original identity, giving subsequent refinements a fresh base. The old metaform keeps its history and attachments whole; `activate <old-name>` switches back. A taken name gets the next free suffix, such as `-2`, with a notice. An intake still building must be finished first. Knowledge, memory, sources and tickets currently stay with the old metaform, and the result says so; knowledge/memory and ticket carryover await D111's remaining answers.

`promote receiver=<address> provider=<address> address=<element-address> [name=<name>] [name_length=<n>] [role=<role>] [reason=<why>]` gives a join an ordinary element, MAP-054. The join keeps its receiver, held elements, identity, history, memories and work, and records the associated element's address in `element`. That element receives and provides ordinary joins. An existing element keeps its authored fields. Repeating the same promotion adds no join version; trying a different address for an associated join returns a notice and writes nothing. Element creation and association share one transaction so a failed promotion leaves no partial changes.

`work id=<work id>` hands an agent its task with knowledge and enabled modules' node memories at its attachment and reference links. Review the knowledge layers first, read the other agents' memories there, and record your own memories at the nodes you work on. A node's compact read shows each taken ticket's ownership and `age_seconds`, measured since it was taken. Completed tickets leave open work and appear under `past_work`, newest first, as references with their completion time and age; `work id=<past work id>` reads the resolution and step log when wanted. The GUI's board and work history show relative age since take or completion.

Put a stopped agent's ticket back with `work op=move id=<work id> column=todo`; its ownership is cleared and its progress log is kept. Assignment already uses `work op=edit id=<work id> glyph=<name>`, or `work op=distribute agents=<n>` for several agents; the dispatch module starts the assigned tickets. A later take starts a new taken age.

Who writes a ticket goes by the role the dispatch runner gives an agent, MAP-050. The person on the page always may, and so may the agents that serve them and a session the person runs outside dispatch. The roles named in the person-only setting `roles_without_authority`, `worker` and `prep` by default, are refused `work op=add` and `knowledge op=add-item` with a `task`, and their `condition` and `kind` on `work op=edit` are ignored with a notice, on the CLI and over MCP. The person sets it to `none` to lift this. `reply` stays refused over MCP for a permission request whatever the role, since answering one is the person's act.

Set a ticket's Eligible agents with `work op=add ... eligible='["claude"]'` or `work op=edit id=<work id> eligible='["claude", "codex"]'`. An empty list restores Any agent, which is the default for existing and new tickets. The map module keeps the list in `"map.eligible"`, keyed by `work_id`, and shows it under `map` on ticket reads. Dispatch and direct `op=take` claims honor it. A direct MCP claim uses the initialized client name, while a CLI claim uses the first word of `by`. Unidentified agents cannot claim restricted tickets. Moving a card to Doing remains a person's action.

## The code layer

The functional map is the base. The project's code is a layer on it, the code layer: a CEL you take off with `knowledge op=discard layer=code` and put back with `code-import`, like any other layer. Functional Addresses in the base and code symbols in the layer meet in the middle, at links.

A link is held at its node, the RE, and names the symbol, which is the PE. What a link means depends on where it is held:

- At an element, the symbol serves that element's own purpose.
- At a join, the symbol realizes the join's EF. It is the code of the provider named with it (`provider=` on `code-link`), or of every provider of the join when none is named, and it serves the receiver.

So every read credits a join's links to those providers. At the receiver, they show apart, as the code serving it.

A symbol is known by its file and its qualified name, so two files that name one module, `tools/gen.py` and `tools/gen/__init__.py`, are both held.

Metaform does not index code itself. It reads an established tool's index, read-only, through that tool's own interface (`code_index.py`):

- `scip`: a SCIP index file (`index.scip`), from any SCIP indexer: scip-python, scip-typescript, rust-analyzer, scip-java and the rest.
  - It is read as `scip.Index` from sourcegraph/scip's `scip.proto`, by field number, with no generated code.
  - A symbol is named by its descriptors joined with dots, for example `kitchen.timer.Timer.tick`. The SCIP symbol string is kept beside it, so a package version bump changes nothing.
  - A reference to a function or method inside a definition's `enclosing_range` is a CALLS edge; any other reference there is USAGE. An occurrence with the Import role is IMPORTS. A `Relationship` with `is_implementation` is INHERITS or IMPLEMENTS from a type, and OVERRIDE from a method.
- `mcp`: a code-graph MCP server, reached as an MCP client with the official SDK, over stdio (a command) or Streamable HTTP (a URL).
  - codebase-memory-mcp is read through `list_projects` and `query_graph`: its declaration labels, and its CALLS, USAGE, INHERITS, IMPLEMENTS, OVERRIDE, TESTS and IMPORTS edges, each with the file its target is in.
  - The project is found by its folder. The project prefix, which names the folder the project was indexed from, is taken off every qualified name.
  - If the server reindexes while it is being read, the read starts again.
- `tree-sitter`: the py-tree-sitter bindings with the installed grammar packages (`tree_sitter_python` and the like).
  - Each grammar's tags query is read: the `@definition.*`, `@reference.call` and `@name` convention that GitHub's code navigation and Aider's repository map use.
  - A call is resolved only where its scope shows what it reaches, never by a name alone. A bare call reaches the file's own declarations or a name the file imports. A call on `self`, `cls` or `this` reaches the enclosing class and the bases it names. A call on an imported module or class reaches that module's or class's declaration. A call on any other receiver, such as a list's `append`, is left out.
  - For Python, imports and base classes are read from the grammar's nodes, giving IMPORTS and INHERITS. Other languages resolve calls within the file and on `self` or `this`.
  - When a file changes, the files that called into it are read again, and so are the files whose calls named something a changed file now declares.

### Importing

`code-import [from=scip|mcp|tree-sitter] [index=<file>] [full=true]` reads only the files whose stamp at the provider changed since the layer last read them.

- The provider is chosen by opening it and listing its files. With `auto`, a provider that does not answer is passed over with a notice. Once one answers, everything is read from it: an error while reading stops the import with that provider's own words and the step that fixes it.
- It never reads a file under `.metaform/ignore.txt` (BASE-058) or a file matched by the `code_ignore` setting.
- A file whose bytes changed while its stamp did not is one the provider has not indexed again. The import keeps what the index says, counts the file as `stale` and names the call that refreshes the index. The brief and `code-context` count stale files.
- The index is kept in the tables `code_files`, `code_symbols` and `code_edges`, under the layer, and goes with it. Edges to code the index does not hold, such as a library's, are left out.
- A decided or proposed link whose symbol is gone is carried only where the symbol's identity is shown to survive: to a symbol this import brought, with the same name below its module (`Timer.tick`, `Alpha.__init__`) and the same kind, in the same file, as when the provider changed and names modules otherwise, or in the file `git diff -M` reports the old file renamed to since the commit it was read at. A link is never carried to a symbol the layer held before, or to another file by its name alone. Each carry is listed under `carried`, with the node, `from`, `to`, `file` and, across a rename, `renamed_from`.
- Any other such link is orphaned: counted as `orphaned`, listed by `code-gaps` and `code-context` with its id, and counted in the brief, until `code-link op=move` or `op=remove` settles it.

The import then ties each file the sources layer cites at a node to the symbols that file declares, at that node.

- A cited line range, `path:12-40` or `path#L12-L40`, narrows the link to the symbols that overlap it.
- A cited folder links nothing. Which code in a folder serves which purpose is for an agent to say, and the result counts such cites as `folders`.
- A link this pass made is taken off when its citation no longer gives it. The pass never touches a link an agent decided.

### Linking as work proceeds

`code-link` is how agents tie code to the map as they work. Every link is a row of `code_links`. Each call that decides is one decision, however many symbols it names: one item of the code layer at its node, with one number at the address, a title and a why, readable as `map item <address>#<n>`. The answer gives the item, the count and the first symbols.

- `op=add node=<address> symbol=<qn or name> why="<how it serves the purpose>"`: links the symbol. Give `file=<path>` instead of `symbol=` for every symbol a file declares, or beside it to name the file of a symbol two files declare. Give `provider=` beside `node` to name the join the element receives; the code is that provider's.
- `op=remove`: unlinks, with a why, by node and symbol or by `id=`. The decision is kept, so the sources pass does not link it again. `id=` works whatever the symbol's state, so an orphaned link can be taken off.
- `op=move id=<id> symbol=<qn> why=`: points a decided or proposed link at the symbol that serves now, keeping its number; the why is added to the decision's.
- `op=propose`: writes a proposal that waits on the link without changing it. It may be a new link, a link the sources pass made to keep, or, with `unlink=true`, a link to take off. `file=` proposes a whole file in one call.
- `op=accept node=<address> [provider=]` decides every proposal waiting there as one decision; `id=<id>` decides one. `op=reject` leaves the links as they were.
- With no op, the proposals waiting are listed.

The workflow skill `code_links` spends the inference up front, before the work. It walks the Addresses no code serves, the code no Address claims, the links the sources pass made that no one has reviewed, file by file, and the orphaned links. It reads both sides and proposes links, keeps, removals and moves, each with its why, for the person or another agent to accept. It writes proposals only.

### Reads

The reads ask the questions that codebase-memory's `search_graph`, `trace_path` and `detect_changes` and GitNexus's `context` and `impact` ask, and answer them in the map's terms.

- Where those tools share an argument, the same name and default are used: `query`, `name_pattern`, `qn_pattern`, `file_pattern`, `label`, `direction` (both for a trace, inbound for changes), `depth` (3 for a trace, 2 for changes), `edge_types`, `include_tests` (false), `since`, and `base` for detect_changes's `base_branch`.
- Paging follows Metaform's page: `limit`, the cursor under `next`, passed back as `after`, rather than search_graph's `offset`.
- Each symbol row carries search_graph's `name`, `qn`, `label`, `file` and `lines`. It adds `address`, the Addresses whose own code the symbol is, and `serves`, the receivers it serves through a join.

The reads:

- `code-context address=<address>`:
  - the Address's own symbols, linked at the element and at the joins it provides for, each with its id and, when decided, its item. A join link shows `at: {receiver, provider}`, which `code-link` takes as `node=` and `provider=`.
  - their files, with stale ones marked
  - the calls in and out, with the Address at the other end
  - `serving`: the code serving the Address, linked at the joins it receives, grouped by provider
  - proposals waiting, and orphaned links with their id and the move and remove calls
  - With `symbol=` or `file=` instead, it gives the Addresses of that symbol or file, linked and citing.
- `code-search [query=] [name_pattern=] [qn_pattern=] [file_pattern=] [label=]`: symbols, paged.
- `code-trace from=<address or symbol> [to=] [direction=both|outbound|inbound] [depth=3] [edge_types=["CALLS"]] [include_tests=true]`:
  - With `to`, it gives the shortest path and the Addresses it passes through.
  - Without `to`, it gives every Address reached within `depth` hops, each at the first hop that reaches it. Calls that stay inside one Address are counted as `within`, and reached code no Address claims as `unclaimed`.
  - `edge_types` takes CALLS, USAGE, INHERITS, IMPLEMENTS, OVERRIDE and TESTS; a type the layer holds none of is said in a notice naming the provider.
  - Test code is left out unless `include_tests=true`, as trace_path does.
- `code-changes [since=HEAD | base=<branch>] [depth=2] [direction=inbound|outbound|both] [include_tests=true]`: the Addresses a change touches.
  - It reads git's changed lines since the ref, or since the merge base with `base`, named as `merge_base`, and the innermost symbols those lines fall in.
  - It gives the Addresses those symbols are the code of (`changed`), the receivers they serve (`served`), and within `depth` the Addresses of their callers (`caller`) and of the types and methods that inherit or override them (`inherits`).
  - `tests` lists the tests that reach a changed symbol, by TESTS edges or calls from test code.
  - The layer's lines are compared with the lines after the change for a file read since the change, and with the lines before it otherwise. Files the layer has not read are listed as `unread`.
  - It uses `git diff` rather than detect_changes, so it works with every provider: detect_changes seeds every symbol of a changed file, not just the changed lines.
- `code-gaps [side=code|purpose|both] [include_tests=true] [after=]`:
  - code without a purpose: the symbols no link or proposal claims, by file, with test code counted as `tests` unless `include_tests=true`
  - purpose without code: the ghosts, the Addresses under the `code` root, or whose sources cite a path, that are no symbol's own Address
  - `unreviewed`: the links the sources pass made that have no why yet, by Address and file
  - `orphaned` links, each with its id and the calls that settle it
  - the cursor under `next`, and the calls that act on the gaps under `then`

### A layer at a scope: `<scope>@<layer>`

What one layer holds at one place has an address of its own, P165: `<scope>@<layer>`, read backward with `@` as "for". `code.timer.kitchen@code` is the code for the kitchen timer. The scope is an Address, or a join written `<receiver>:<provider>`, as every read names a join: `code.timer.kitchen:code.alarm.audible@code` is the code realizing the timer's join with the alarm. `base@<layer>` is the whole project. A layer named with its scope, as `knowledge` asks a new layer to be named, `code.cpp@best_practices`, resolves by that full name first.

- `where address=<scope>@<layer>` gives the scope's element as the map has it, name and role, and what the layer holds there. For the code layer that is the code-context read, each call with the Address at its other end, so the code is walked in both directions, symbol to owning Address and Address to symbols. For any other layer it is the layer's items there, read in context, each with its id, value, refs and link.
- `code-context address=` takes the same form.
- The MCP resource `metaform://<scope>@<layer>` and the web GUI's brief serve the same read, since both are `where`.
- A hidden layer resolves to nothing, with the call that shows it again; the map is unchanged.
- The web GUI's workspace gets the `Code` pane, `map.code`, which runs `code-context` on the selected node through `/api/workspace/pane`.

### Where agents meet it

An element's brief gains one line, `code`, from the `brief_code` prompt. The line gives:

- its own symbols and files
- the calls in and out
- the code serving it, if any
- the stale files, if any
- the orphaned links, if any
- the call that reads them

The line is counted from the code tables by node and by file, never symbol by symbol, and it stays within `node_summary_bytes`.

- `brief_code_none` names the call that links code, but only at nodes the code should serve: those under the `code` root, or citing a file the code layer holds.
- `map node` and `where contents=true` carry the same line, so the code layer's links are counted there, not listed.
- The map's entry, `map roots` (or `map where` with no address), names `code-import` in `code_start` until the layer exists. The intake's `finish` names it in `next` when the map has a code trunk.

## The project's glossary

`glossary` reads the project's own terms, the block an agent is pointed at as `metaform://<project>`. It is generated from the project alone:

- Every element of the map in context with a name, the canonical or informal name the intake recorded, is a term. Its definition is its Address with its EF, how it serves what relies on it, and its OP, the purpose it bears as receiver. These are read from the map at each read, never copied, so `refine` of a name, a removed element or another base is in step at once.
- `term` adds, edits and removes terms, on the command line and over MCP as `map_term`. The page reads them in the Glossary pane; a page form that writes one needs the workspace's tool action to take typed nouns, which it does not yet. `op=add` needs `definition`, `why` and `source`, the file and line or who uses it (the page's person may leave the source out); `node=<address>` puts it at the node where it was found, where it takes the next number, `<address>#<n>`, read with `map item` like any item and named under the node in its brief, `Terms here`. `op=edit` on an element's term keeps the person's or agent's definition over the EF and OP; `op=remove` takes an added term out, its number never reused, or hides an element's term until it is added or edited again. Each change needs a why.
- The block has the form of Metaform's own glossary block: the peer register standard first, exactly as the person wrote it (`register_standard`), then `@STATE_INIT`, one `{Term} := "definition"` line per term and `@CONSTRAINT`. The form is the canonical prompt `glossary`, which ships with Metaform and is not edited at runtime.
- The most-used terms go in first: use is how many joins name the element and how often the term's words appear in the map's purposes, EFs and other definitions. What does not fit `glossary_bytes` is counted under the terms with the call that lists it, `glossary format=list after=<n>`.
- `format=list` gives every term with its kind, element, added or edited, its Addresses, why, source, who wrote it and its uses, paged; `term=<words>` gives one.
- `metaform.module.project_glossary(folder)` gives the block as an agent reads it, for the MCP server's `metaform://<project>` resource. The web GUI's workspace gets the `Glossary` pane, `map.glossary`, the list read.
- Terms are kept in the map module's `terms` table, version 15, in the project's own database, so a new intake keeps them.

## Settings

`--raw`, default off: read every stored layer, building, hidden and masked ones included.

`--node-summary-bytes`, default 2048, at least 512: the most bytes the compact read of the node an agent works on may take, in `where`, the ticket read `work id=` and so dispatch's hand-off. What does not fit goes in this order: the code paths, the joins it receives' first and the node's own last, then the joins it receives, then the joins it provides for after the first, and then the tree draws fewer neighbours a side, down to one. Code paths that fit again in the room a join left come back. Each kind left out is said under `more` as a count with the call that reads it, in the `summary_*` prompts. `contents=true` and `full=true` are never cut.

`--code-provider`, default `auto`: where `code-import` reads the code, `scip`, `mcp` or `tree-sitter`; `auto` takes the first the project has, in that order. `from=` on the call names one for that call.

`--code-server`, default `codebase-memory-mcp`, person only: the code-graph MCP server `code-import` reads, a command started over stdio or an http(s) URL. Person only because it names a program Metaform starts.

`--code-server-env`, default `CBM_*`, person only: the environment variables a code-graph server started over stdio is given, beside HOME, PATH and the MCP SDK's other safe defaults; a name ending in `*` passes every variable it starts. codebase-memory-mcp reads its cache folder from `CBM_CACHE_DIR`, and refuses to start against a different cache than its running daemon's, so the variable has to reach it.

`--glossary-bytes`, default 5120, at least 1024: the most bytes the project's glossary is given in, register standard included; the most-used terms go in and the rest are counted with the call that lists them.

`--glossary-register`, default `peer`: `peer` sends the peer register standard ahead of the terms, as written, and sets `{Register} := PEER_UNSLOP`; `none` sends the terms alone.

`--code-server-project`, default empty: the project's name on that server; empty finds it by the project's folder.

`--code-index`, default `index.scip`: the SCIP index file, relative to the project.

`--code-layer`, default `code`: the layer the code symbols and their links are kept in.

`--code-kinds`, default Function, Method, Class, Interface, Struct, Enum, Trait and Type: the kinds of declaration kept, as the code graph labels them.

`--code-ignore`, default `*.md`, `*.markdown`, `*.rst`, `*.txt`, `*.xml`, `*.html`, `*.htm`, `*.json`, `*.toml`, `*.yaml`, `*.yml`, `*.ini`, `*.cfg`, `*.css`, `*.svg`, `*.csv` and `*.lock`: files `code-import` never reads, as gitignore patterns. These are documents and data a code graph also parses; their elements and keys are not code.

## Events

None.

## Sync and async

Every verb is a plain function.

## Layers

It writes whatever layer a `knowledge` call names. `code-import` creates the code layer, the setting `code_layer`, owned by map, mutable and hideable, and writes the code decisions into it as items; the links themselves are rows of `code_links` under it.

## Lifecycle and cleanup

No `start` or `stop`, and no tasks.

## Modules relied on

None.

## Systems supported

Linux, macOS and Windows.

## Resources owned

`storage.py` declares the module's tables through public `Tables(version=3)`: `work`, `work_links`, `work_steps`, `messages`, `challenge_states`, `plans`, `reports` and `"map.glyphs"`. The seven existing feature tables retain their names and data in the metaform's store; their definitions and operations belong to this module. Public `Data` and `Operation` declarations run its reads, writes and record contributions through the DAO's transaction. The chassis supplies the transaction and table services, with no feature SQL, BASE-046. Persisted table declarations preserve exports and layer cleanup when the module is disabled.

`code_files`, `code_symbols`, `code_edges` and `code_links` hold the code layer's index and links. They are keyed by the layer's id and removed with the layer; a symbol is keyed by its file and qualified name, and a file row keeps the commit it was read at and the names its calls did not find. A link that is a decision is also removed with its item. These tables are version 14, read and written by version 9 and later. A store whose code tables are version 11 to 13 reads every file again at its next import. `numbered` holds a code decision's number, title and why under kind `code`, beside those of work records and messages.

`DATA_SOURCE = 'storage.py'` keeps the declared `Operation(..., retained=True)` reads available for existing work, messages and report records while map is disabled. Loading that source does not activate map's commands, settings or glyph contribution; writes follow map's enabled state.

`"map.glyphs"`, key `work_id`, holds the agent glyph each ticket is assigned to, STORE-045 and VIEW-040. `work op=distribute agents=<n>` and `work op=edit glyph=<name>` write it; every `work` result shows a record's glyph as `{"map": {"glyph": "<name>"}}`, and `MODULE.work_read` shows it in `work id=<id>`, BASE-035. The work table holds no glyph. Native map reads and writes use the public data access object.

## Installed and direct wheel

The same in both.

## Demonstration

```
metaform map knowledge op=create layer=notes variable="Notes at each node." mutable=true hideable=true module=me
metaform map knowledge op=add-item layer=notes node=element:code.engine value='"Profile first."'
metaform map knowledge op=finish layer=notes
metaform map node element:code.engine
```

`exclude` records material outside the intake scope or code conflicting with a superseding specification. Its note links the affected material and the specification or scope reason for review. Unrelated folders are excluded from functional capture; proposed gitignore changes are recorded for review. Marking a record preserves files and does not change gitignore. Unneeded migration code is marked for review. A store at an earlier layout is updated by Metaform when it opens it.
