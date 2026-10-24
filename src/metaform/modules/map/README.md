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

`boards op=wipe name=<board>` clears every ticket on that board after keeping an automatic backup and stopping its
running sessions through dispatch. Empty `name=` clears the first board. Named boards are removed. The map stays.
`boards op=restore name=<board> backup=<stamp>` inserts original tickets with their numbers, steps, links and
settings. Existing ticket ids are skipped. Later work stays. `metaform list backups` lists wipe stamps beside clear
backups. Wipe backups are kept permanently. Wipe and restore are person_only, refused over MCP. The page's Boards
select offers Wipe this board and Restore for each backup.

`markdown` writes the map, or with `address=` the part around one address, as a short Markdown document: each element's name, address, role and paths, from the sources layer, and each join's receiver, the elements it holds, its ef and its purpose, MAP-052, and `file=` writes the document to a file. It is a command only and never a tool.

`mermaid` writes the map, or with `address=` that element and the elements one join away, as a Mermaid flowchart, P063: the elements and joins the web GUI's 2D map draws, each element a node named by what the project calls it, else its short name, over its address, and an edge for each element each join holds, pointing the way the join's information goes, its ifd: from the receiver to the element served when it sends or nothing is recorded, from the element to the receiver when it receives, `<-->` when both, as the 2D map's arrowheads point. The CQUs and the DE carry the classes `cqu` and `de`. Its YAML frontmatter gives the title and the 2D map's layout, ELK by network simplex. `direction=TB`, the default, or `LR`; `leave_out=` roots not drawn, comma-separated; `labels=purpose` or `labels=ef` puts each join's on its edges; `file=` writes it to a file such as `map.mmd`, which GitHub, VS Code and Obsidian draw. Mermaid with its default limits refuses a diagram over 50,000 characters or 500 edges, and those limits cannot be raised from the diagram, so such a diagram says so in a comment at its top, and with `file=` in a notice. The web GUI's Export menu saves and copies the same flowchart, written by the same writer, `metaform.outline.mermaid`, with the page's layers, the direction its 2D map runs and the roots it leaves out.

Start with `roots`: the map's entry, the CQU and the DE with the joins they receive, and every root element; `where` with an empty address returns the same. Handed an address, start with `where`: one read of the address returns the element with its address read through name_length and its role, its `sources`, the sources layer's refs, `provides`, what relies on it, each join it provides for by its receiver with the receiver's purpose and its refs, `receives`, what it relies on, each join it receives by its providers with its purpose and refs, and, the first time an agent session reads it, `around`: a small tree of how much is held at it and at its direct neighbours, memories, open work, messages, layer items, earlier runs and properties, with the call that reads each, MCP-039. Later in the session only a count that changed is said, under `changed`. `contents=true` returns what is held there in full: the joins with ef, ifd, elements and layer, `work`, its open work records with condition, note and task, `layers`, what the layers in context hold at it, as `node` gives them, messages, properties and each module's node read. Ids and empty fields are left out, all but the element's id, which `history` takes, and each ticket's and open message's id; `full=true` keeps them all, with the contents. Under the node the tree names what is new there: `Latest: <address>#<n>  <title>`, the last number taken at it with its item's title, and `the last session added #a–#b`, the numbers the last agent session other than the reader's own took there, from the project's number log, which records the session that took each number. The CLI, the node's `metaform://<address>` resource, the ticket read, dispatch's hand-off and the page's Brief all show it, since all are this read. The tree's words are the `around_*` prompts. An address that is no element in context stops with `No element <address> in context here.` and `Next: metaform map children <address>`. Reads: `roots`, `where`, `element`, `joins`, `identity`, `children`, `layers`, `layer`, `node`, `context`, `links`, `citing`, `history`, `stack`, `metaforms`, `search`, which finds the items, memories and knowledge values, whose value holds every word of the text, and `work`, the work records, the condition of an element or a join kept apart from the map, MAP-046. Writes: `work` with `op=add`, `op=edit` and `op=done`, `knowledge` with `op=` and `layer=` on every call, `tag`, `untag`, `select`, `mask`, `clear`, `hide`, `unhide`, `reexamined`, `add-metaform`, `activate`, `answer`, and `approve` on the CLI only. `critic` starts a blind-spot critic run, fast mode by default, critic mode with `--critic`: it creates the run's blind-spot layer, provenance role `critic` with `blinded` true, or false with `--critic`, and returns the critic prompt, `blind_spot_challenge`, then `critic_fast` or `critic_critic` with the layer and the whole metaform as `markdown` prints it, LAYER-014. `challenges <layer>` returns the answer prompt, `answer_challenges`, with each challenge of that layer, its state, the node it is attached to and its text, LAYER-015. Each verb returns its operation's result; every join shows the layer it comes from, and every element and join its `open_work`, the conditions of its open work records. A write that does not fit is stored as given and its result carries `notices`. A field that is missing is stored empty and named in a notice; a `knowledge` or `work` call stops only when it is missing a field its record cannot be stored without, such as a join's receiver or a work record's node, the table in BASE-038. `knowledge op=add-element` takes an element's `address`, `name_length`, `name` and `role`. `op=add-join` takes the join's `receiver`, `elements`, the elements that serve its purpose, `purpose`, `ef`, `ifd` and `type`; refs live in the sources layer, never in the metaform. `knowledge op=edit` and `map refine` move a join with `receiver` and change the elements it holds with `elements`; the join keeps its id, MAP-003. They change a join's `purpose`, `ef`, `ifd` and `type` too. An `address` given to them for an element is not applied and is named in a notice, MAP-015: an element is renamed by `map refine address=<old> to_address=<new>`, which makes the element at the new address (or merges into the one there), moves every purpose record, knowledge item and property at the old one, each a new version, moves its tickets, questions and ticket links, and publishes `map.moved`, on which the memory module moves its memories, then removes the old element; refs of the sources layer stay where they were linked and are named with the `dispatch link` call for the new place. `map refine` also grows the base after the intake, under the intake's rules, by the store's `grow_element` and `grow_join`, which the intake's verification pass uses too: an address the base lacks given with `name`, `name_length` or `role` is added as an element, and `receiver` with `elements` no join of it holds, with `purpose`, `ef` and `ifd`, is added as a purpose record; `adopt=true` takes an element or join a knowledge layer holds into the base keeping its id. Every version refine writes records `reason`, `evidence` and `by` (`work <id> session <id>` from the runner's identity, else the surface), shown by `history`. A fault ticket marked with the store's `prove_work` requires delivery evidence. Done records its resolution. Missing delivery keeps it open, answers with `work_delivery` and names the missing steps. Successful delivery closes it immediately, including through `complete_delivery` or a board move to Done. `ticket_settings` retains `proof` as the delivery requirement and `landed` as the submitted result's time. Moving it to To do or Backlog clears its submitted result and resolution. Cancelled or failed work ends without delivery. `work op=done` answers with a notice for each part of the ticket's work not on the map in use (its node, and every element its session linked a file at), with the refine call that puts it there (refinement first, 2026-10-17). `work` names its node as `refine` does: a join by `receiver` and `provider`, an element it holds, an element by `address` or `node`; `links` take the same as objects. `ask` and `tell` take `node` first, an element's address; `provider` beside it names the join that element holds as receiver, the one holding that provider. A work record is missing, broken, flawed, enhancement or exclude. missing means the thing does not exist at all, or is not built yet. A thing that exists but is wrong is not missing: it is broken (not working, not connected, orphaned), flawed (works but is not right) or an enhancement (works, could be better); exclude is outside the scope, or conflicts with a superseding specification. A work record has a note and a task, held and reviewed flags, and its resolution once done; it is attached to one object, has no layer, and never changes the map. Tools are `map_<verb>`.

Move a ticket to another node with `work op=edit id=<work id> node=<address>`, or name its destination join by `receiver` and `provider`. Its id, ownership, progress, completion and reference links are kept; `links=` edits those references explicitly. Move an existing question or message with `messages op=move id=<message id> node=<address>`, with `provider` and `address` as in `ask` and `tell`; its suggestions, answer and closed state are kept. These operations carry records to a better-addressed functionality without changing element identity, MAP-015. Without `op`, `messages` still lists them.

`add-base`, `activate` and `collapse` each change which base is the project's active map, so each carries a caution: the active map changes for every agent and the page of that project, and the previous base is kept, `map activate <its name>` switching back. Each is the person's decision (`person_says`, CLI-011, UX review round 1): it runs on the person's own `--confirm` on their command line, the page, or their yes to the form their AI tool shows them, never on an agent's `confirm`, and an agent is told the command the person runs. Its caution names what the active base holds that leaves view: open tickets, knowledge layers and agents at work (the conversations with agents are the project's and stay); `remove-base`'s names what the removed base holds and that no command brings it back. The map counts its tickets and layers for those cautions and for a clear's with `Provides('base.holds', base_holds)`. The result of a switch names the agents at work on the base left, which stay on it with their tickets, and the open tickets that stay with it (UX review round 1, 2026-10-17).

`collapse <name> [project=<id>]` writes the current functional map into a new metaform with one finished `intake` layer and makes it active, LAYER-026. Each current element and join appears once with its original identity, giving subsequent refinements a fresh base. The old metaform keeps its history and attachments whole; `activate <old-name>` switches back. A taken name gets the next free suffix, such as `-2`, with a notice. An intake still building must be finished first. Knowledge, memory, sources and tickets currently stay with the old metaform, and the result says so; knowledge/memory and ticket carryover await D111's remaining answers.

`promote receiver=<address> provider=<address> address=<element-address> [name=<name>] [name_length=<n>] [role=<role>] [reason=<why>]` gives a join an ordinary element, MAP-054. The join keeps its receiver, held elements, identity, history, memories and work, and records the associated element's address in `element`. That element receives and provides ordinary joins. An existing element keeps its authored fields. Repeating the same promotion adds no join version; trying a different address for an associated join returns a notice and writes nothing. Element creation and association share one transaction so a failed promotion leaves no partial changes.

`work id=<work id>` hands an agent its task with knowledge and enabled modules' node memories at its attachment and reference links. Review the knowledge layers first, read the other agents' memories there, and record your own memories at the nodes you work on. A node's compact read shows each taken ticket's ownership and `age_seconds`, measured since it was taken. Completed tickets leave open work and appear under `past_work`, newest first, as references with their completion time and age; `work id=<past work id>` reads the resolution and step log when wanted. The GUI's board and work history show relative age since take or completion.

`boards op=line [name=<board>]` archives tickets completed before the cutoff. A ticket leaves the store only when its
completion commit is on the branch checked out in the registered project folder and retains its exact citation.
Tickets without that proof stay in the store, listed under `kept` with a fault. Removed tickets lose their steps,
reference links, settings and base progress lines. Project conversations stay. `work id=<address>#<n>` and `item`
resolve a removed ticket through its `Metaform-Number` trailer, returning the commit hash, subject, body and files.
Project counters keep citation numbers from being reused. Node past-work references and brief counts combine live
records with Git history, without counting both copies of a ticket. Each command shares one Git history read and
the next command reads Git again. A prior or empty cutoff changes visibility without restoring removed records.
Completion commits include a canonical `Ticket state` JSON snapshot of the map-owned ticket rows and citation
metadata. Shedding requires an exact match, so later notes, tasks, steps, links or settings keep a record until a
new completion commit preserves them. Older commits remain readable by citation, but records without this snapshot
stay in the store. The completion writer reads the snapshot through `store.work_snapshot(work_id)`.
Join tickets require `Metaform-Target` attachment proof. A commit must preserve the current resolution and must
not predate the current completion, so reopening does not allow an older resolution to replace the newer record.

Put a stopped agent's ticket back with `work op=move id=<work id> column=todo`; its ownership is cleared and its progress log is kept. Assignment already uses `work op=edit id=<work id> glyph=<name>`, or `work op=distribute agents=<n>` for several agents; the dispatch module starts the assigned tickets. A later take starts a new taken age.

Ticket writes, task-bearing knowledge writes and condition/kind edits have no role-based authority filter. Graph/schema invariants and explicit ticket eligibility still apply. Actual native permission responses retain their transport handling.

`work op=add` accepts a no-task `unbuilt` or `under-construction` stage, using the DAO's `shown_open` contract. Such a record is visible on its node, has `is_work=false`, and is excluded from executable work and autostart. A task makes executable work; a trouble, broken or missing marker can start from its note. Empty built/ok records and notes without work or a visible stage remain invalid. New records announce kind `filed` on `map.changed`.

Before constructing or extending the base or a knowledge layer, read `metaform://map/construction`, also served by `metaform map guide`. The operation-specific guide composes exact constraints from the served `intake.axiom` with separately identified definitions, namespace rules and valid/invalid examples from the original `intake.xml`. Its selected wrapper and source fingerprints identify the complete delivered guide. Base additions must meet the functional construction grammar; provisional concepts and details remain in a named CEL bounded by its declared variable. Conditions and executable work stay outside the frozen functional core. Response-boundary receipts identify the exact guide body delivered; they do not establish semantic understanding.

Set a ticket's Eligible agents with `work op=add ... eligible='["claude"]'` or `work op=edit id=<work id> eligible='["claude", "codex"]'`. An empty list restores Any agent, which is the default for existing and new tickets. The map module keeps the list in `"map.eligible"`, keyed by `work_id`, and shows it under `map` on ticket reads. Dispatch and direct `op=take` claims honor it. A direct MCP claim uses the initialized client name, while a CLI claim uses the first word of `by`. Unidentified agents cannot claim restricted tickets. Moving a card to Doing remains a person's action.

A ticket can wait on others: `work op=edit id=<work id> after_work='["<work id>", ...]'` (each an id or an `<address>#<n>`), and `after_work='[]'` waits on none. The map module keeps the list in `"map.after"`, keyed by `work_id`, and shows it under `map` on ticket reads; dispatch starts no such ticket by itself, and `dispatch start` refuses it, while any of them is open. A held ticket (`held=true`, the Backlog) waits for release: autostart and Start all never start it. Holds require an explicit user or deliberate agent action with a fresh `hold_reason` recorded on the ticket. Creation never adds a hold because of source, role, feedback, filing or review state. Autostart controls automatic starts. Reason-based unholding needs no person approval, including with `agents_ask_first` on. Explicit start and stop authority remain unchanged. A ticket's change says its kind on `map.changed`: `note` for its note, title or links alone, `step` for its plan and steps, `ticket` for the rest. A ticket done also says `done` beside `ticket`, heard by dispatch's plan report (code.dispatcher.agent#10).

## A layer at a scope: `<scope>@<layer>`

What one layer holds at one place has an address of its own, P165: `<scope>@<layer>`, read backward with `@` as "for". `code.timer.kitchen@best_practices` is the best practices for the kitchen timer. The scope is an Address, or a join written `<receiver>:<provider>`, as every read names a join: `code.timer.kitchen:code.alarm.audible@best_practices` is what the layer holds at the timer's join with the alarm. `base@<layer>` is the whole project. A layer named with its scope, as `knowledge` asks a new layer to be named, `code.cpp@best_practices`, resolves by that full name first.

- `where address=<scope>@<layer>` gives the scope's element as the map has it, name and role, and the layer's items there, read in context, each with its id, value, refs and link.
- The MCP resource `metaform://<scope>@<layer>` and the web GUI's brief serve the same read, since both are `where`.
- A hidden layer resolves to nothing, with the call that shows it again; the map is unchanged.

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

`--node-summary-bytes`, default 2048, at least 512: the display target for the compact node read in `where`, the ticket read `work id=` and dispatch's handoff. Fitting removes decorative count detail before source paths, with `more` notices linking to omitted source references. Receiver identities, operative purposes and relationships remain regardless of storage order; the essential packet can exceed the display target when needed to preserve them. `contents=true` and `full=true` retain their complete reads.

`--glossary-bytes`, default 5120, at least 1024: the most bytes the project's glossary is given in, register standard included; the most-used terms go in and the rest are counted with the call that lists them.

`--glossary-register`, default `peer`: `peer` sends the peer register standard ahead of the terms, as written, and sets `{Register} := PEER_UNSLOP`; `none` sends the terms alone.

## Events

None.

## Sync and async

Every verb is a plain function.

## Layers

It writes whatever layer a `knowledge` call names.

## Lifecycle and cleanup

No `start` or `stop`, and no tasks.

## Modules relied on

None.

## Systems supported

Linux, macOS and Windows.

## Resources owned

`storage.py` declares the module's tables through public `Tables(version=3)`: `work`, `work_links`, `work_steps`, `messages`, `challenge_states`, `plans`, `reports` and `"map.glyphs"`. The seven existing feature tables retain their names and data in the metaform's store; their definitions and operations belong to this module. Public `Data` and `Operation` declarations run its reads, writes and record contributions through the DAO's transaction. The chassis supplies the transaction and table services, with no feature SQL, BASE-046. Persisted table declarations preserve exports and layer cleanup when the module is disabled.

Version 16 dropped the code layer's tables, `code_files`, `code_symbols`, `code_edges` and `code_links`, with `code-import` and the other code-* verbs (ticket code.analyzer.refactoring#1a, 2026-10-15); a file is placed on the map by its ref in the sources layer, `dispatch link`. Code-layer items already in a store stay as plain items of that layer.

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

Explicit holds require a fresh nonblank `hold_reason` on `hold=true`, `held=true` and moves into Backlog.
The hold author answers: "Please explain why this ticket is on hold. State whether it is unsafe to unhold, and why."
General notes and previous reasons never substitute for a new explanation. `work id=<id>` reads retained
`hold_history`; release preserves it. `work op=unhold_all` releases open executable work across project boards
and bases, leaves prerequisites intact, excludes reserved conversations and closed work, and returns changed count.
Board previews recorded explanations before confirmation and rejects a stale preview. Ordinary reason-based
unholding needs no approval, including with `agents_ask_first` on. Autostart controls automatic starts.


Work request provenance lives in `work_sources`, separate from the current task. Add or edit with
`source={"text":"exact original words","reference":"message or source reference","spans":[]}` when available.
The task records the execution interpretation. Caller identity records the edit author; a relayed user message
keeps its separate source identity. Each task revision retains the earlier words. A legacy ticket's first edit
retains a pre-edit snapshot without inventing its original author or request. Ticket reads return source ids and
read commands. `map work op=sources id=<work> [source_id=<source>]` retrieves exact text, interpretation and
provenance in publication order. Source records never add a hold or require approval.
