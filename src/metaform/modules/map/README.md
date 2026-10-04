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

`markdown` writes the map, or with `address=` the part around one address, as a short Markdown document: each element's name, address, role and paths, and each join's receiver, provider, ef, purpose and non_goal, MAP-052, and `file=` writes the document to a file. It is a command only and never a tool.

Start with `roots`: the map's entry, the CQU and the DE with the joins they receive, and every root element; `where` with an empty address returns the same. Handed an address, start with `where`: one read of the address returns the element with its address read through name_length and its role, `provides`, what relies on it, every join it provides with the receiver, the receiver's purpose, the join's function, ef, verb, name and layer, `receives`, what it relies on, every join it receives with the provider and the join's purpose, function, ef, verb, name and layer, the subtype joins inside each of those joins, `held`, the subtype join holding it and the join that subtype join sits in, `work`, its open work records with condition, note and task, and `layers`, what the layers in context hold at it, as `node` gives them. Ids and empty fields are left out so the read stays small; `full=true` keeps them. Reads: `roots`, `where`, `element`, `joins`, `identity`, `subtypes`, `children`, `layers`, `layer`, `node`, `context`, `links`, `citing`, `history`, `stack`, `metaforms`, `search`, which finds the items, memories and knowledge values, whose value holds every word of the text, and `work`, the work records, the condition of an element or a join kept apart from the map, MAP-046. `subtypes` returns the subtype joins inside a join, each with the element it holds; `where` at the address of an element held only by subtype joins returns it with the subtype join and the join holding it, MAP-031. Writes: `work` with `op=add`, `op=edit` and `op=done`, `knowledge` with `op=` and `layer=` on every call, `tag`, `untag`, `select`, `mask`, `clear`, `hide`, `unhide`, `reexamined`, `add-metaform`, `activate`, `answer`, and `approve` on the CLI only. `critic` starts a blind-spot critic run: it creates the run's blind-spot layer, provenance role `critic` with `blinded` true, or false with `sighted=true`, and returns the critic prompt, `critic_blind` or `critic_sighted`, with the whole metaform as `markdown` prints it, LAYER-014. `challenges <layer>` returns the answer prompt, `answer_challenges`, with each challenge of that layer, its state, the node it is attached to and its text, LAYER-015. Each verb returns its operation's result; every join shows the layer it comes from, and every element and join, a subtype join included, its `open_work`, the conditions of its open work records. A write that does not fit is stored as given and its result carries `notices`. A field that is missing is stored empty and named in a notice; a `knowledge` or `work` call stops only when it is missing a field its record cannot be stored without, such as a join's receiver or a work record's node, the table in BASE-038. `knowledge op=add-element` takes an element's `address`, `name_length`, `role`, `refs` and `extra`; a `name` sent there is kept in the element's `extra` with a notice, since the project's name for a functionality goes on the join. `op=add-join` and `op=add-subtype` take `name`, `purpose`, `ef` and `verb` beside the join's other fields; a subtype join keeps its own Operative Purpose in `purpose`. `knowledge op=edit` and `map refine` move a join with `receiver` or `provider`, and with `parent` make it a subtype join inside that join, its purpose kept in its own `purpose` field; the join keeps its id, MAP-003 and MAP-030. They do not read `ef` or `verb`: a value given for either is named in a notice and ignored. An element cannot be moved: an `address` given to them for an element is not applied and is named in a notice, MAP-015. `work` names its node as `refine` does: a purpose by `receiver` and `provider`, a part inside it by `address` with them, an element by `address` or `node`; `links` take the same as objects. `ask` and `tell` take `node` first, an element's address; `provider` beside it names the purpose that element holds as receiver, and `address` with them a part inside it. A work record is missing, broken or exclude, with a note and a task, held and reviewed flags, and its resolution once done; it is attached to one object, has no layer, and never changes the map. Tools are `map_<verb>`.

Move a ticket to another node with `work op=edit id=<work id> node=<address>`, or name its destination purpose by `receiver` and `provider`, with `address` for a part inside it. Its id, ownership, progress, completion and reference links are kept; `links=` edits those references explicitly. Move an existing question or message with `messages op=move id=<message id> node=<address>`, with `provider` and `address` as in `ask` and `tell`; its suggestions, answer and closed state are kept. These operations carry records to a better-addressed functionality without changing element identity, MAP-015. Without `op`, `messages` still lists them.

`work id=<work id>` hands an agent its task with knowledge and enabled modules' node memories at its attachment and reference links. Review the knowledge layers first, read the other agents' memories there, and record your own memories at the nodes you work on. A node's compact read shows each taken ticket's ownership and `age_seconds`, measured since it was taken. Completed tickets leave open work and appear under `past_work`, newest first, as references with their completion time and age; `work id=<past work id>` reads the resolution and step log when wanted. The GUI's board and work history show relative age since take or completion.

Put a stopped agent's ticket back with `work op=move id=<work id> column=todo`; its ownership is cleared and its progress log is kept. Assignment already uses `work op=edit id=<work id> glyph=<name>`, or `work op=distribute agents=<n>` for several agents; the dispatch module starts the assigned tickets. A later take starts a new taken age.

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
