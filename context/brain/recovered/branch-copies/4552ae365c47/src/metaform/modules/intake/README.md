# intake

Serves the intake instructions by name and records the intake one object at a time as the agent reasons it.

## Purpose

The intake is agent work. A subagent reads the instructions with `intake prompt`, starts the intake, and records each element and each purpose record in its own call as soon as it is reasoned. Once everything is recorded it reads the map back, whole or one receiver at a time, proofs and corrects it, then finishes it. The map is: an element is its `namespace_address`, `name_length`, `name` and `role`; a purpose record is its type, `purpose`, `ef` and `ifd`, held by its receiver, holding the elements that serve it. The agent names what it reasoned and never what the store keeps: an element by its `namespace_address` and a purpose record by its `receiver` and an element it holds. No id reaches the agent. After the finish, `remove` changes nothing and says the metaform changes by refining. Until the finish the intake layer is building: no context read sees it, and the web GUI draws it live. The module also reports whether the project has an intake, or one being recorded. It ships enabled.

## Template version

Started from template 0.2.0.

## Declaration

`SUPPORTED_OS = ('linux', 'macos', 'windows')`, `DEPENDENCIES = ()`, `SHIPS_DISABLED = False`. `MODULE` declares `prompt`, `start`, `element`, `purpose`, `show`, `remove`, `finish`, `status` and `discard`, and a status hook.

## Common base used

`metaform.module` for the declaration, `Context`, `Status` and `save_report`; `metaform.settings` for `--intake-file`; `metaform.data` for the store writes and the reads `intake_recording` and `layer_graph`.

## Prompts

`resources/prompts.xml` holds `instructions`, `intake is active.`, listed in the instructions agents read under "modules available.", MCP-031.

## Verbs

- `prompt`: the stored intake text with its prompt slot filled with `text`. Tool `intake_prompt`.
- `start`: opens the building intake layer, with the model and role the agent gives, or resumes the one being recorded. When the active metaform already has an intake, `start` opens a verification pass on it: a changed field is refined, a new element or purpose record is added to the map's own layer, every version kept, and `finish` closes the pass without opening or activating a base. `start name=<x>` instead records a separate intake in a new metaform `<x>`, finished beside the active map, which stays active: `metaform map activate <x> --confirm` makes it the active one (UX review round 1, 2026-10-17). On a project with a map that is the person's decision (`person_decides`): an agent's `start name=` is refused with the caution and the refine route, unless the person chose the map at the agent's launch. An element or purpose record sent to a finished map with no start opens a verification pass on it, never a new intake (refinement first, 2026-10-17). A pass grows the base through the store's `grow_element` and `grow_join`, the same writes `map refine` uses, each version with reason `intake verification pass` and its author. Tool `intake_start`.
- `element <namespace_address>`: records one element, with optional `name_length`, `name` and `role`. Recording an address again records it again: the fields given replace the ones it had. `refs` given here go in the sources layer, one item at the element, replacing what it held, while `intake_sources` is on. Tool `intake_element`.
- `purpose <receiver> <elements>`: records one purpose record: the receiver's purpose served by the elements it holds, a JSON list of addresses, with optional `purpose`, `ef` and `ifd`. A purpose record of the receiver that already holds one of the elements is that purpose record: the fields given replace its own, and the elements it does not hold are added to it. An annealed part is an ordinary element held by a purpose record one level deeper: the parent element receives that purpose record. Elements and purpose records repeat in the same form at every depth. Tool `intake_purpose`.
- `show`: the intake being recorded as `elements`, `purposes` and `undescribed`: whole, every element by `namespace_address`, every purpose record by `receiver` with the `elements` it holds, and the addresses named in a purpose record and never described; with `receiver=<namespace_address>`, only that receiver's purpose records and the elements they name. Tool `intake_show`.
- `remove`: removes one recorded thing while the intake is building, named by its addresses: `namespace_address` for an element, `receiver` and `provider` for the purpose record of that receiver holding that element, and all three to take the element at `namespace_address` out of that purpose record. After the finish it writes nothing and names `metaform map refine`, which changes the metaform in the same layer and keeps every version, LAYER-025. Tool `intake_remove`.
- `finish`: marks the layer ready, saves `report=` and `feedback=` as the intake layer's report and feedback files, reading a value that names a file from the file and `-` from standard input on the command line, while a tool is handed the text and opens no path, and returns the layer, the project, the metaform, the counts of `elements` and `purposes`, the count of open work records on them as `work`, and the notices, which name any address named in a purpose record and never described. Tool `intake_finish`, declared `open_world`: its `intake.finished` event starts the refactor module's follow-on, which sends code to Jev when the person has turned `jev` on, H17.
- `status`: whether the project has an intake, with the latest intake layer, and the intake being recorded or left unfinished. Tool `intake_status`. The status hook adds `Intake: complete`, `Intake: being recorded` while an agent records one, `Intake: left unfinished` for one no agent records any more, or `Intake: none yet` and the notice to delegate the intake. An intake is being recorded only while the process of the agent recording it lives: a host's MCP server over stdio, or a dispatched agent's, holds it from its first record until it ends, BASE-039; commands alone never do. While an intake agent dispatch started lives, its runner holding `intake.agent`, the intake its records go into is being recorded whatever surface it records through; `start`, `element`, `purpose`, `finish` and `discard` from any other caller are refused with `metaform dispatch stop <its work id>`, the status hook says `Intake: an agent Metaform started is at work on it now` and sends no onboarding or aborted-intake line, and its own `start` follows the map the person chose at its launch, `map=new` with its name or `map=extend` (UX review round 1, 2026-10-17).
- `discard`: drops the intake left unfinished, its layer and the parts it recorded, and a base opened for it alone, a copy kept under `backups/remove-base`. It is refused while an agent records the intake now. The person's choice, beside resuming and finishing it: on the command line only, with `--confirm`, never a tool; the web page's notice for an intake left unfinished offers it. It is `person_says`: a command an agent runs is refused whatever it confirms, and its caution names the layer and how many elements go (UX review round 1).

`element` and `purpose` take `condition` and `note`. A `missing` or `trouble` condition writes an open work record at what was recorded, apart from the functional map, MAP-046, and the map shows it. One defect seen at two parts is recorded once: the second finding gives `same_as`, the address of the element where it is open, and joins that ticket, its note added and its part linked, so one ticket carries it; `show` marks the linked part with `kept_in`, and recording that part again takes the link off. A ticket an agent has taken is not changed: a note it lacks becomes the part's own finding, the two tickets linking each other. `ok` writes no work record: it is the part's one item of the `checked` layer, which `show` reads back as `ok`, and a later `missing` or `trouble` there removes it. A `note` given without a condition, or with `ok`, is the part's one item of the `critic` layer, beside the map: the base holds RE, PE, OP and EF only, and the store refuses a note written into it.

Nothing is refused for its content. What does not fit is stored as given and named in a notice by its field: a missing field is stored empty, an element a purpose record names that the intake has not recorded gets one in the intake layer, and an address out of form is stored as given. On the CLI `elements` and `refs` are JSON text; a value that is not a JSON list is read as a list holding that one value.

## Settings

`--intake-file`, default empty, meaning the intake in `resources/`. `--intake-sources`, default on: whether the intake writes the refs it is given into the sources layer.

## Events

None.

## Sync and async

Every verb is a plain function.

## Layers

Each intake makes one layer named `intake`, LAYER-025, kind intake, immutable, not hideable, building until `finish`, with provenance module `intake`, workflow `canonical-intake`, no prompt text, and the model and role the agent gives. A `start` that resumes a layer being built fills in what the layer lacks of these; what it holds is kept, and a different value given for it is named in a notice. The refs the intake is given go in a knowledge layer named `sources`, mutable and hideable, one item per element.

## Lifecycle and cleanup

No `start` or `stop` hooks, and no tasks. An intake left building by an agent that stopped is resumed by the next `intake start`.

## Modules relied on

None.

## Systems supported

Linux, macOS and Windows.

## Resources owned

`resources/Intake_2.1.md`, Intake 2.1, the served intake and its only copy.

## Installed and direct wheel

The same in both; the intake text travels inside the module.

## Demonstration

```
metaform intake prompt
metaform intake start model=opus role="intake agent"
metaform intake element downstream.cqu.cook.home role=CQU name_length=2
metaform intake element code.timer.kitchen role=DE name_length=2 name="dish clock" refs='[{"key": "path", "value": "timer.c"}]'
metaform intake purpose downstream.cqu.cook.home '["code.timer.kitchen"]' purpose="Know when each dish is done." ef="tells the cook when a dish is done" ifd=receives
metaform intake element code.loop.tick role=SE name_length=2 name="ticker"
metaform intake purpose code.timer.kitchen '["code.loop.tick"]' purpose="Advance the countdown." ef="fires once a second" ifd=sends
metaform intake show receiver=downstream.cqu.cook.home
metaform intake finish report="The alarm pin is unconnected."
metaform intake status
```
