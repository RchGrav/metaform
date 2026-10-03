# intake

Serves the Canonical Intake instructions by name and records the intake one object at a time as the agent reasons it.

## Purpose

The intake is agent work. A subagent reads the instructions with `intake prompt`, starts the intake, and records each element, requirement and part in its own call as soon as it is reasoned, and anneals one requirement at a time with `intake absorb`. Once everything is recorded it reads the map back, whole or one receiver at a time, proofs and corrects it, then finishes it. The agent names what it reasoned and never what the store keeps: an element by its `namespace_address`, as in the Canonical Intake, a requirement by its `receiver` and `provider`, and a part by its `namespace_address` inside that requirement. After the finish, `edit`, `remove` and `absorb` change nothing and say the metaform changes by refining. The code writes them as elements, joins and subtype joins, and no id reaches the agent; Rich, 2026-10-02: "joins are a database concept". Until the finish the intake layer is building: no context read sees it, and the web GUI draws it live. The module also reports whether the project has an intake, or one being recorded. It ships enabled.

## Template version

Started from template 0.2.0.

## Declaration

`SUPPORTED_OS = ('linux', 'macos', 'windows')`, `DEPENDENCIES = ()`, `SHIPS_DISABLED = False`. `MODULE` declares `prompt`, `start`, `element`, `join`, `subtype`, `absorb`, `show`, `edit`, `remove`, `finish` and `status`, and a status hook.

## Common base used

`metaform.module` for the declaration, `Context`, `Status` and `save_report`; `metaform.settings` for `--intake-file`; `metaform.data` for the store writes and the reads `intake_recording` and `layer_graph`.

## Prompts

`resources/prompts.xml` holds `instructions`, `intake is active.`, listed in the instructions agents read under "modules available.", MCP-031.

## Verbs

- `prompt`: the stored intake text with the project's target filled, then the recording lines: always how to record with the intake tools and the rule to stop and submit a trouble report with `feedback` instead of retrying; the report request when `--report` is on; the feedback request when `--debug` is on. Takes `--report` and `--debug` for one call. Tool `intake_prompt`.
- `start`: opens the building intake layer, with the model, role, blinded flag and result id the agent gives, or resumes the one being recorded. When the active metaform already has an intake, the new one is recorded in a new metaform `intake-<UTC timestamp>`, which becomes active at the finish. Tool `intake_start`.
- `element <namespace_address>`: records one element, with optional `role`, `name_length`, `refs` and `extra`, and returns its `element_id`. An element is its address, name_length and role; its name is its address read through name_length. A `name` sent here is kept in the element's `extra` with a notice, since the project's name for a functionality goes on the join. Recording an address again describes it again: the fields given replace the ones it had. Tool `intake_element`.
- `add_requirement <receiver> <provider>`: adds one requirement, the receiver's purpose served by the provider's encounter function, with optional `name`, the project's own name for the functionality, `purpose`, `ef`, `ifd`, `verb`, `non_goal`, `refs` and `extra`. The code writes it as a join of type require held by the receiver. Returns the two addresses. Tool `intake_add_requirement`.
- `subtype <parent_receiver> <parent_provider> <namespace_address>`: records one part inside the requirement of `parent_receiver` served by `parent_provider`, holding the element at `namespace_address`, which it records, or describes again with the `role` and `name_length` given, as `element` does: the part stays one element record, MAP-030. Optional `purpose`, `ef`, `ifd`, `verb`, `non_goal`, `name`, `refs`, the part's own, and `extra`. The code writes it as a subtype join. Tool `intake_subtype`.
- `absorb <receiver> <provider> <parent_receiver> <parent_provider>`: anneals: makes the requirement of `receiver` served by `provider` a part inside the parent requirement, with every field, its purpose among them, and any other requirement that still names the element is listed in a notice and left as it is. An element held only as a part is no root and no node of the outer map. Tool `intake_absorb`.
- `show`: the intake being recorded: whole, every element by `namespace_address`, every requirement by `receiver` and `provider` with the parts it holds under `subtypes`, and the addresses named in a requirement and never described; with `receiver=<namespace_address>`, only that receiver's requirements, what they hold and the elements they name. Tool `intake_show`.
- `edit` and `remove`: change or remove one recorded thing while the intake is building, named by its addresses: `namespace_address` for an element, `receiver` and `provider` for a requirement, and all three for a part. Two requirements of one receiver on the same provider cannot be told apart by their addresses: the notice lists both purposes and neither is changed. `to_receiver` and `to_provider` move a requirement, which stays the same requirement. An element cannot be moved: `to_address` given for an element is not applied, and the notice says to record the element at the new address and move its requirements; on a part it gives the part another element to hold, and `role` and `name_length` describe the element it holds. After the finish they write nothing and name `metaform map refine`, which changes the metaform in the same layer and keeps every version, LAYER-025. Tools `intake_edit` and `intake_remove`.
- `finish`: marks the layer ready, saves `report=` and `feedback=` as the intake layer's report and feedback files, reading a value that names a file from the file and `-` from standard input on the command line, while a tool is handed the text and opens no path, and returns the layer, the project, the metaform, the counts of elements, requirements, parts as `subtypes`, and refs, the count of open work records on them as `work`, and the notices, which name any address named in a requirement and never described. Tool `intake_finish`.
- `status`: whether the project has an intake, with the latest intake layer, and the intake being recorded. Tool `intake_status`. The status hook adds `Intake: complete` and `Start with: metaform map roots`, `Intake: being recorded` while one is, or `Intake: none yet` and the notice to delegate the intake.

`element`, `add_requirement` and `subtype` take `condition` and `note`. Given, they write an open work record at what was recorded, apart from the functional map, MAP-046, and the map shows it. Their definitions in `resources/prompts.xml` are the Canonical Intake's step 2 words.

Nothing is refused for its content. What does not fit is stored as given and named in a notice by its field: a missing field is stored empty, a join end that names no element gets one in the intake layer, an `ef` other than `Function` or `Encounter` goes to `extra`, a ref whose key or value is not text is kept in the record's `extra` under `refs`, and an address out of form is stored as given. On the CLI `refs` and `extra` are JSON text; a `refs` value that is not a JSON array is read as a list holding that one ref.

## Settings

`--intake-file`, default empty, meaning the Canonical Intake in `resources/`. The prompt also reads the chassis settings `--report`, default on, and `--debug`, default off, CLI-034.

## Events

None.

## Sync and async

Every verb is a plain function.

## Layers

Each intake makes one layer named `intake`, LAYER-025, kind intake, immutable, not hideable, building until `finish`, with provenance module `intake`, workflow `canonical-intake`, no prompt text, and the model, role and blinded flag the agent gives. A `start` that resumes a layer being built fills in what the layer lacks of these and of its result id; what it holds is kept, and a different value given for it is named in a notice.

## Lifecycle and cleanup

No `start` or `stop` hooks, and no tasks. An intake left building by an agent that stopped is resumed by the next `intake start`.

## Modules relied on

None.

## Systems supported

Linux, macOS and Windows.

## Resources owned

`resources/Intake_2.1.md`, a byte copy of `specifications/Intake_2.1.md`, Intake 2.1, the served intake; a repository test fails when they differ.

## Installed and direct wheel

The same in both; the intake text travels inside the module.

## Demonstration

```
metaform intake prompt
metaform intake start model=opus role="intake agent" id=my-result
metaform intake element stakeholder.cook.home role=CQU name_length=2
metaform intake element code.timer.kitchen role=DE name_length=2
metaform intake add_requirement stakeholder.cook.home code.timer.kitchen name="dish clock" purpose="Know when each dish is done." ef="tells the cook when a dish is done" ifd=receives verb=tells
metaform intake subtype stakeholder.cook.home code.timer.kitchen code.loop.tick role=SE name_length=2 name="ticker" ef="advances every running countdown" ifd=receives verb=advances
metaform intake absorb code.timer.kitchen code.alarm.audible stakeholder.cook.home code.timer.kitchen
metaform intake show receiver=stakeholder.cook.home
metaform intake finish report="The alarm pin is unconnected."
metaform intake status
```
