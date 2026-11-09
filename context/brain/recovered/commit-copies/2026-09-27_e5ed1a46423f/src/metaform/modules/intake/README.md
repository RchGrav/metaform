# intake

Serves the Canonical Intake instructions by name and records the intake one object at a time as the agent reasons it.

## Purpose

The intake is agent work. A subagent reads the instructions with `intake prompt`, starts the intake, and records each element, join and subtype join in its own call as soon as it is reasoned. Once everything is recorded it reads the whole map back, proofs and corrects it, then finishes it. Until the finish the intake layer is building: no context read sees it, and the web GUI draws it live. The module also reports whether the project has an intake, or one being recorded. It ships enabled.

## Template version

Started from template 0.2.0.

## Declaration

`SUPPORTED_OS = ('linux', 'macos', 'windows')`, `DEPENDENCIES = ()`, `SHIPS_DISABLED = False`. `MODULE` declares `prompt`, `start`, `element`, `join`, `subtype`, `show`, `edit`, `remove`, `finish` and `status`, and a status hook.

## Common base used

`metaform.module` for the declaration, `Context`, `Status` and `save_report`; `metaform.settings` for `--intake-file`; `metaform.data` for the store writes and the reads `intake_recording` and `layer_graph`.

## Verbs

- `prompt`: the stored intake text with the project's target filled, then the recording lines: always how to record with the intake tools and the rule to stop and submit a trouble report with `feedback` instead of retrying; the report request when `--report` is on; the feedback request when `--debug` is on. Takes `--report` and `--debug` for one call. Tool `intake_prompt`.
- `start`: opens the building intake layer, with the model, role, blinded flag and result id the agent gives, or resumes the one being recorded. When the active metaform already has an intake, the new one is recorded in a new metaform `intake-<UTC timestamp>`, which becomes active at the finish. Tool `intake_start`.
- `element <address>`: records one element, with optional `role`, `name_length`, `refs` and `extra`. An element is its address, name_length and role; its name is its address read through name_length. A `name` sent here is kept in the element's `extra` with a notice, since the project's name for a functionality goes on the join. Recording an address again describes it again: the fields given replace the ones it had. Tool `intake_element`.
- `join <receiver> <provider>`: records one join, with optional `name`, the project's own name for the functionality, `purpose`, `function`, `ef`, `relation`, `verb`, `observation`, `non_goal`, `type`, `refs` and `extra`. Returns the join id. Tool `intake_join`.
- `subtype <join> <address>`: records one subtype join inside its parent join, with optional `function`, `ef`, `relation`, `verb`, `observation`, `role`, `name`, the subtype join's name, `name_length`, `refs`, `purpose`, kept in its `extra`, and `extra`. Tool `intake_subtype`.
- `show`: the intake being recorded, whole, with every id, and the addresses recorded only as the end of a join and never described. Tool `intake_show`.
- `edit <id>` and `remove <id>`: change or remove one recorded element, by address or id, join or subtype join while the intake is building. After the finish they write nothing and name the correction layer. Tools `intake_edit` and `intake_remove`.
- `finish`: marks the layer ready, saves `report=` and `feedback=` as the intake layer's report and feedback files, and returns the layer, the project, the metaform, the counts of elements, joins, subtypes and refs, the count of open work records on them as `work`, and the notices. Tool `intake_finish`.

The tools carry no condition field. What is in the specs and not built, broken, or cruft is a work record, apart from the map, written with `map_work` at any time, the intake agent's as it maps, MAP-046.
- `status`: whether the project has an intake, with the latest intake layer, and the intake being recorded. Tool `intake_status`. The status hook adds `Intake: complete` and `Start with: metaform map roots`, `Intake: being recorded` while one is, or `Intake: none yet` and the notice to delegate the intake.

Nothing is refused for its content. What does not fit is stored as given and named in a notice by its field: a missing field is stored empty, a subtype's purpose goes to its `extra`, a join end that names no element gets one in the intake layer, an `ef` other than `Function` or `Encounter` goes to `extra`, and an address out of form is stored as given. On the CLI `refs` and `extra` are JSON text.

## Settings

`--intake-file`, default empty, meaning the Canonical Intake in `resources/`. The prompt also reads the chassis settings `--report`, default on, and `--debug`, default off, CLI-034.

## Events

None.

## Sync and async

Every verb is a plain function.

## Layers

Each intake makes one layer `intake-<UTC timestamp>-<6 hex>`, kind intake, immutable, not hideable, building until `finish`, with provenance module `intake`, workflow `canonical-intake`, no prompt text, and the model, role and blinded flag the agent gives.

## Lifecycle and cleanup

No `start` or `stop` hooks, and no tasks. An intake left building by an agent that stopped is resumed by the next `intake start`.

## Modules relied on

None.

## Systems supported

Linux, macOS and Windows.

## Resources owned

`resources/Canonical_Intake.xml`, a byte copy of `specifications/Canonical_Intake.xml`; a repository test fails when they differ.

## Installed and direct wheel

The same in both; the intake text travels inside the module.

## Demonstration

```
metaform intake prompt
metaform intake start model=opus role="intake agent" id=my-result
metaform intake element stakeholder.cook.home role=VE name="Home cook"
metaform intake join stakeholder.cook.home code.timer.kitchen purpose="Know when each dish is done." function="Counts down and rings." ef=Function relation="The kitchen timer tells the cook." verb=tells observation="One countdown per dish."
metaform intake show
metaform intake finish report="The alarm pin is unconnected."
metaform intake status
```
