# intake

Serves the editable `intake` task instructions and records the intake one object at a time as the agent reasons it.

## Purpose

The intake is an assigned task. `tasks read name=intake` reads its instructions and `tasks assign name=intake text="..."` starts an agent with the selected instructions and assignment input. `intake prompt` reads the same instruction body. The agent records elements and purpose records, reads the map back, corrects it, and finishes it according to the supplied task. The map is: an element is its `namespace_address`, `name_length`, `name` and `role`, with optional native `block` and `within` metadata; a purpose record is its type, `purpose`, `ef` and `ifd`, held by its receiver, holding the elements that serve it. The agent names what it reasoned and never what the store keeps: an element by its `namespace_address` and a purpose record by its `receiver` and an element it holds. No id reaches the agent. After the finish, `remove` changes nothing and says the metaform changes by refining. Until the finish the intake layer is building: no context read sees it, and the web GUI draws it live. The module also reports whether the project has an intake, or one being recorded. It ships enabled.

## Template version

Started from template 0.2.0.

## Declaration

`SUPPORTED_OS = ('linux', 'macos', 'windows')`, `DEPENDENCIES = ()`, `SHIPS_DISABLED = False`. `MODULE` declares `prompt`, `start`, `element`, `purpose`, `show`, `remove`, `finish`, `status` and `discard`, and a status hook.

## Common base used

`metaform.module` for the declaration, `Context`, `Status` and `save_report`; `metaform.settings` for `--intake-file`; `metaform.data` for the store writes and the reads `intake_recording` and `layer_graph`.

### Provides

`intake.task_component(ctx, **bindings)` returns the selected intake prompt's exact text and source metadata.
Assigned tasks use this provider alongside intake's existing `intake.first_run` and `agent.tool.instructions` services.

## Prompts

`resources/prompts.xml` holds `instructions`, `intake is active.`, listed in the instructions agents read under "modules available.", MCP-031.

## Verbs

- `prompt`: the selected task instruction text, with the declared `{project}` binding applied. Nonempty `text` is appended literally under a separate `## Intake request` heading, preserving the instruction body's trailing newlines. XML tags, headings and method phases are not interpreted, and `{prompt}` remains literal. Optional `mode=fresh|refine|resume` adds the shared mode request from `resources/prompts.xml`. A dispatched intake retains its launch mode when it rereads the prompt. Fresh records into its separate destination despite an existing map. Refine updates the current map. Resume continues the unfinished destination. The task body remains editable. Tool `intake_prompt`.
- `start`: opens the building intake layer, with the model and role the agent gives, or resumes the one being recorded. When the active metaform already has an intake, `start` opens a verification pass on it: a changed field is refined, a new element or purpose record is added to the map's own layer, every version kept, and `finish` closes the pass without opening or activating a base. `start name=<x>` instead records a separate intake in a new metaform `<x>`, finished beside the active map, which stays active: `metaform map activate <x> --confirm` makes it the active one (UX review round 1, 2026-10-17). On a project with a map that is the person's decision (`person_decides`): an agent's `start name=` is refused with the caution and the refine route, unless the person chose the map at the agent's launch. An element or purpose record sent to a finished map with no start opens a verification pass on it, never a new intake (refinement first, 2026-10-17). A pass grows the base through the store's `grow_element` and `grow_join`, the same writes `map refine` uses, each version with reason `intake verification pass` and its author. Tool `intake_start`.
- `element <namespace_address>`: records one element, with optional `name_length`, `name`, `role`, `block` and `within`. `block` records its numbered ICE block identifier and `within` records its containing element's namespace address. Recording an address again records it again: the fields given replace the ones it had. For `block` and `within`, omission preserves the value and explicit JSON `null` clears it. `refs` given here go in the sources layer, one item at the element, replacing what it held, while `intake_sources` is on. Tool `intake_element`.
- `purpose <receiver> <elements>`: records one purpose record: the receiver's purpose served by the elements it holds, a JSON list of addresses, with optional `purpose`, `ef` and `ifd`. A purpose record of the receiver that already holds one of the elements is that purpose record: the fields given replace its own, and the elements it does not hold are added to it. An annealed part is an ordinary element held by a purpose record one level deeper: the parent element receives that purpose record. Elements and purpose records repeat in the same form at every depth. Tool `intake_purpose`.
- `show`: the intake being recorded as `elements`, `purposes` and `undescribed`: whole, every element by `namespace_address`, every purpose record by `receiver` with the `elements` it holds, and the addresses named in a purpose record and never described; with `receiver=<namespace_address>`, only that receiver's purpose records and the elements they name. Element entries include `block` and `within` when set, and omit them when unset. Tool `intake_show`.
- `remove`: removes one recorded thing while the intake is building, named by its addresses: `namespace_address` for an element, `receiver` and `provider` for the purpose record of that receiver holding that element, and all three to take the element at `namespace_address` out of that purpose record. After the finish it writes nothing and names `metaform map refine`, which changes the metaform in the same layer and keeps every version, LAYER-025. Tool `intake_remove`.
- `finish`: marks the layer ready, saves `report=` and `feedback=` as the intake layer's report and feedback files, reading a value that names a file from the file and `-` from standard input on the command line, while a tool is handed the text and opens no path, and returns the layer, the project, the metaform, the counts of `elements` and `purposes`, the count of open work records on them as `work`, and the notices, which name any address named in a purpose record and never described. Tool `intake_finish`, declared `open_world`: its `intake.finished` event starts the refactor module's follow-on, which sends code to Jev when the person has turned `jev` on, H17.
- `status`: whether the project has an intake, with the latest intake layer, and the intake being recorded or left unfinished. Tool `intake_status`. The status hook adds `Intake: complete`, `Intake: being recorded` while an agent records one, `Intake: left unfinished` for one no agent records any more, or `Intake: none yet` and the notice to delegate the intake. An intake is being recorded only while the process of the agent recording it lives: a host's MCP server over stdio, or a dispatched agent's, holds it from its first record until it ends, BASE-039; commands alone never do. While an intake agent dispatch started lives, its runner holding `intake.agent`, the intake its records go into is being recorded whatever surface it records through; `start`, `element`, `purpose`, `finish` and `discard` from any other caller are refused with `metaform dispatch stop <its work id>`, the status hook says `Intake: an agent Metaform started is at work on it now` and sends no onboarding or aborted-intake line, and its own `start` follows the map the person chose at its launch, `map=new` with its name or `map=extend` (UX review round 1, 2026-10-17).
- `discard`: drops the intake left unfinished, its layer and the parts it recorded, and a base opened for it alone, a copy kept under `backups/remove-base`. It is refused while an agent records the intake now. The person's choice, beside resuming and finishing it: on the command line only, with `--confirm`, never a tool; the web page's notice for an intake left unfinished offers it. Its caution names the layer and how many elements go.

`element` records namespace address, canonical name, name length, role, optional native block and containment metadata, and refs. `purpose` records receiver, providing elements, purpose, ef, ifd and refs. These commands record functional understanding and references. Intake does not create critic notes, assessment markers or repair tickets. The retired `note`, `condition` and `same_as` arguments are absent from the recording schema. Reports and process feedback remain available through `finish`.

`block` and `within` accept JSON strings or null. On the CLI, write `'block="BLOCK_001"'` or `'within="code.timer.kitchen"'` to preserve the JSON string quotes, and `block=null` or `within=null` to clear a value. The same fields and omission/null semantics apply to `map refine`. They remain on native element reads, `map where` and XML output without creating a knowledge layer.

Nothing is refused for its content. What does not fit is stored as given and named in a notice by its field: a missing field is stored empty, an element a purpose record names that the intake has not recorded gets one in the intake layer, and an address out of form is stored as given. On the CLI `elements` and `refs` are JSON text; a value that is not a JSON list is read as a list holding that one value.

## Settings

`--intake-file`, default empty, meaning `resources/intake.xml`. Any UTF-8 instruction file is accepted. The extension and contents do not select a parser or impose a required form. `--intake-sources`, default on: whether the intake writes the refs it is given into the sources layer.

## Events

`intake.completed` announces every successfully finished intake with its project, base and layer. Roundtable
follow-through uses it to present the new project's map before planning. Verification passes do not emit it.
`intake.finished` retains its existing code-enrichment meaning and only announces finished code maps or newly
added code elements.

## Sync and async

Every verb is a plain function.

## Layers

Each intake makes one layer named `intake`, LAYER-025, kind intake, immutable, not hideable, building until `finish`, with provenance module `intake`, workflow `canonical-intake`, no prompt text, and the model and role the agent gives. A `start` that resumes a layer being built fills in what the layer lacks of these; what it holds is kept, and a different value given for it is named in a notice. The refs the intake is given go in a knowledge layer named `sources`, mutable and hideable, one item per element.

## Lifecycle and cleanup

The tasks module owns assigned execution. This module has no `start` or `stop` hooks. An intake left building by an agent that stopped is resumed by the next `intake start`.

## Modules relied on

None.

## Systems supported

Linux, macOS and Windows.

## Resources owned

- `resources/intake.xml`: the one source file for the named `intake` task, read as opaque text. Task reads, task assignment and `intake prompt` share its selected editable prompt version. No XML form or prescribed headings are required.
- `resources/metaform.xml`: the schema served by `intake schema` and `metaform://intake/schema`.
- `resources/prompts.xml`: module instructions, tool field descriptions and the shared intake mode section.

Map construction guidance is its own editable prompt and directs the agent to read the `intake` task. It does not extract or parse sections of the intake instructions. Editing intake markup leaves map guidance usable. The former `intake.axiom` and `metaform.axiom` resources are removed from active intake resources.

## Installed and direct wheel

The same in both; the intake text travels inside the module.

## Demonstration

```
metaform intake prompt
metaform tasks assign name=intake text="Map the kitchen timer."
metaform intake start model=opus role="intake agent"
metaform intake element downstream.cqu.cook.home role=CQU name_length=2
metaform intake element code.timer.kitchen role=DE name_length=2 name="dish clock" 'block="BLOCK_001"' refs='[{"key": "path", "value": "timer.c"}]'
metaform intake purpose downstream.cqu.cook.home '["code.timer.kitchen"]' purpose="Know when each dish is done." ef="tells the cook when a dish is done" ifd=receives
metaform intake element code.loop.tick role=SE name_length=2 name="ticker" 'block="BLOCK_001"' 'within="code.timer.kitchen"'
metaform intake purpose code.timer.kitchen '["code.loop.tick"]' purpose="Advance the countdown." ef="fires once a second" ifd=sends
metaform intake show receiver=downstream.cqu.cook.home
metaform intake finish report="The alarm pin is unconnected."
metaform intake status
```
