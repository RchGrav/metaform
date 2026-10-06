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

Start with `roots`: the map's entry, the CQU and the DE with the joins they receive, and every root element; `where` with an empty address returns the same. Handed an address, start with `where`: one read of the address returns the element with its address read through name_length and its role, `provides`, what relies on it, every join that holds it with the receiver, the receiver's purpose, the join's ef, ifd, the elements it holds and its layer, `receives`, what it relies on, every join it receives with the elements it holds and the join's purpose, ef, ifd and layer, `work`, its open work records with condition, note and task, and `layers`, what the layers in context hold at it, as `node` gives them, the sources layer's refs among them. Ids and empty fields are left out so the read stays small; `full=true` keeps them. Reads: `roots`, `where`, `element`, `joins`, `identity`, `children`, `layers`, `layer`, `node`, `context`, `links`, `citing`, `history`, `stack`, `metaforms`, `search`, which finds the items, memories and knowledge values, whose value holds every word of the text, and `work`, the work records, the condition of an element or a join kept apart from the map, MAP-046. Writes: `work` with `op=add`, `op=edit` and `op=done`, `knowledge` with `op=` and `layer=` on every call, `tag`, `untag`, `select`, `mask`, `clear`, `hide`, `unhide`, `reexamined`, `add-metaform`, `activate`, `answer`, and `approve` on the CLI only. `critic` starts a blind-spot critic run, fast mode by default, critic mode with `--critic`: it creates the run's blind-spot layer, provenance role `critic` with `blinded` true, or false with `--critic`, and returns the critic prompt, `blind_spot_challenge`, then `critic_fast` or `critic_critic` with the layer and the whole metaform as `markdown` prints it, LAYER-014. `challenges <layer>` returns the answer prompt, `answer_challenges`, with each challenge of that layer, its state, the node it is attached to and its text, LAYER-015. Each verb returns its operation's result; every join shows the layer it comes from, and every element and join its `open_work`, the conditions of its open work records. A write that does not fit is stored as given and its result carries `notices`. A field that is missing is stored empty and named in a notice; a `knowledge` or `work` call stops only when it is missing a field its record cannot be stored without, such as a join's receiver or a work record's node, the table in BASE-038. `knowledge op=add-element` takes an element's `address`, `name_length`, `name` and `role`, Rich's shape, 2026-10-04. `op=add-join` takes the join's `receiver`, `elements`, the elements that serve its purpose, `purpose`, `ef`, `ifd` and `type`; refs live in the sources layer, never in the metaform. `knowledge op=edit` and `map refine` move a join with `receiver` and change the elements it holds with `elements`; the join keeps its id, MAP-003. They change a join's `purpose`, `ef`, `ifd` and `type` too. An element cannot be moved: an `address` given to them for an element is not applied and is named in a notice, MAP-015. `work` names its node as `refine` does: a join by `receiver` and `provider`, an element it holds, an element by `address` or `node`; `links` take the same as objects. `ask` and `tell` take `node` first, an element's address; `provider` beside it names the join that element holds as receiver, the one holding that provider. A work record is missing, broken, flawed, enhancement or exclude. missing means the thing does not exist at all, or is not built yet. A thing that exists but is wrong is not missing: it is broken (not working, not connected, orphaned), flawed (works but is not right) or an enhancement (works, could be better); exclude is outside the scope, or conflicts with a superseding specification. A work record has a note and a task, held and reviewed flags, and its resolution once done; it is attached to one object, has no layer, and never changes the map. Tools are `map_<verb>`.

Move a ticket to another node with `work op=edit id=<work id> node=<address>`, or name its destination join by `receiver` and `provider`. Its id, ownership, progress, completion and reference links are kept; `links=` edits those references explicitly. Move an existing question or message with `messages op=move id=<message id> node=<address>`, with `provider` and `address` as in `ask` and `tell`; its suggestions, answer and closed state are kept. These operations carry records to a better-addressed functionality without changing element identity, MAP-015. Without `op`, `messages` still lists them.

`collapse <name> [project=<id>]` writes the current functional map into a new metaform with one finished `intake` layer and makes it active, LAYER-026. Each current element and join appears once with its original identity, giving subsequent refinements a fresh base. The old metaform keeps its history and attachments whole; `activate <old-name>` switches back. A taken name gets the next free suffix, such as `-2`, with a notice. An intake still building must be finished first. Knowledge, memory, sources and tickets currently stay with the old metaform, and the result says so; knowledge/memory and ticket carryover await D111's remaining answers.

`promote receiver=<address> provider=<address> address=<element-address> [name=<name>] [name_length=<n>] [role=<role>] [reason=<why>]` gives a join an ordinary element, MAP-054. The join keeps its receiver, held elements, identity, history, memories and work, and records the associated element's address in `element`. That element receives and provides ordinary joins. An existing element keeps its authored fields. Repeating the same promotion adds no join version; trying a different address for an associated join returns a notice and writes nothing. Element creation and association share one transaction so a failed promotion leaves no partial changes.

`work id=<work id>` hands an agent its task with knowledge and enabled modules' node memories at its attachment and reference links. Review the knowledge layers first, read the other agents' memories there, and record your own memories at the nodes you work on. A node's compact read shows each taken ticket's ownership and `age_seconds`, measured since it was taken. Completed tickets leave open work and appear under `past_work`, newest first, as references with their completion time and age; `work id=<past work id>` reads the resolution and step log when wanted. The GUI's board and work history show relative age since take or completion.

Put a stopped agent's ticket back with `work op=move id=<work id> column=todo`; its ownership is cleared and its progress log is kept. Assignment already uses `work op=edit id=<work id> glyph=<name>`, or `work op=distribute agents=<n>` for several agents; the dispatch module starts the assigned tickets. A later take starts a new taken age.

Set a ticket's Eligible agents with `work op=add ... eligible='["claude"]'` or `work op=edit id=<work id> eligible='["claude", "codex"]'`. An empty list restores Any agent, which is the default for existing and new tickets. The map module keeps the list in `"map.eligible"`, keyed by `work_id`, and shows it under `map` on ticket reads. Dispatch and direct `op=take` claims honor it. A direct MCP claim uses the initialized client name, while a CLI claim uses the first word of `by`. Unidentified agents cannot claim restricted tickets. Moving a card to Doing remains a person's action.

## Settings

`--raw`, default off: read every stored layer, building, hidden and masked ones included.

## Events

None.

## Sync and async

Every verb is a plain function.

## Layers

It writes whatever layer a `knowledge` call names; it creates no layer of its own.

## Lifecycle and cleanup

No `start` or `stop`, and no tasks.

## Modules relied on

None.

## Systems supported

Linux, macOS and Windows.

## Resources owned

`storage.py` declares the module's tables through public `Tables(version=3)`: `work`, `work_links`, `work_steps`, `messages`, `challenge_states`, `plans`, `reports` and `"map.glyphs"`. The seven existing feature tables retain their names and data in the metaform's store; their definitions and operations belong to this module. Public `Data` and `Operation` declarations run its reads, writes and record contributions through the DAO's transaction. The chassis supplies the transaction and table services, with no feature SQL, BASE-046. Persisted table declarations preserve exports and layer cleanup when the module is disabled.

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
