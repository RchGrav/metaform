# source_placement

Uses tree-sitter plus the existing functional map, and derives function placement into the map at a 90% confidence level. A function placed below 90% is not placed: it goes to the Place remaining code ticket, where a reasoning agent places it from the source. The module also serves the procedure that connects each receiving element's purpose to implementation evidence and records the inference that editing agents would otherwise repeat.

Until 2026-10-14 the module was called `refactor`; Rich renamed it because it does not refactor, it places code at the map. What a home stored under the old name moves once, as the module starts (see Lifecycle and cleanup).

## Purpose

Symbol and call lookup says what the code is; it does not say which functionality the code serves, what a proposed boundary must preserve, or why one extraction depends on another. This module serves the procedure that works that out, BASE-063, and the agent following it records the result once, in the `source_placement` knowledge layer, at the element that owns it. Later agents read that knowledge instead of reconstructing it. BASE-065 adds the pass that places the confidently classified code upfront and leaves the rest as ordinary work.

## Template version

The template changelog version this module started from: 0.3.0, with the Unreleased changes.

## Declaration

`SUPPORTED_OS` is Linux, macOS and Windows: the procedure is text and the parser's wheels are built for all three. `DEPENDENCIES` is `tree-sitter>=0.25,<0.26` and `tree-sitter-javascript>=0.25,<0.26`: this module owns the Tree-sitter runtime and the JavaScript grammar, and offers its parser to other modules rather than letting them declare it, BASE-065. `SHIPS_DISABLED` is False: the module ships enabled, and reading its procedure costs nothing until an agent follows it. `REMOTE_AGENT` is False: the intake prepares a project's knowledge before work is assigned, so it runs where the project is.

The code is in parts, each under 500 lines: `parser.py` the Tree-sitter source parser offered as `code.functions`, `jev.py` the bulk category request, `pipeline.py` the placement run, its batches and its saved progress, and `remainder.py` the work record left for a reasoning agent.

### Toolbar items and panes

None. The module's surfaces are the command line and MCP; what it records is read through the map's own panes, at `<address>@source_placement`.

## Common base used

`metaform.module` for the declaration, `Context`, `Stop`, `Provides` and `Subscription`, for `child_environment` when the extension is started as its own process, and for `provided` to find the code graph capability. `metaform.prompt_files` reads the authored procedure out of `resources/prompts.xml` and binds the caller's task text as data, `prompt_files.required` where a missing prompt is a defect, MCP-031. `metaform.data` for `Store` and `Node`: the module writes through the public layer, item and work operations only, and declares no tables of its own. `metaform.jev` for the Jev configuration and transport: `jev.py` builds the bulk category selection and sends it with `jev.post`, so the person-only `jev` setting, `jev_endpoint`, `jev_model` and `jev_decisions` (as the decision point `source_placement.associate`) govern it as they govern every other Jev caller. `metaform.settings` reads `jev` itself, so a refusal names the setting.

### Provides

`Provides('code.functions', ...)`, the source parser: the suffixes it reads and the function it parses with. The map module finds it with `provided(folder, 'code.functions')` and so declares no parser dependency of its own; disabling source_placement withdraws the capability and map's inventory falls back to the configured code graph MCP, and never withdraws map, intake or dispatch, BASE-065.

## Prompts

In `resources/prompts.xml`: `instructions`, the module's line in the instructions agents read; `intake`, the authored procedure itself, written as Axiom rather than this store's usual XML because it is the procedure the owner refined; `input`, which binds the caller's optional task text as a JSON data block after the procedure; `jev`, the optional bulk association pass added only when the caller asks for it; `remainder`, the session text for the work left below the threshold; and `commands`, which offers the procedure as the client prompt `source_placement-intake`. The module declares no rules.

## Verbs

- `intake` — `metaform source_placement intake`, tool `source_placement_intake`, effect `read`. Serves the procedure as written, with `text` bound after it as data, and `association=jev confidence=<n>` (default 90) adding the optional pass. It opens no layer and records nothing.
- `extend` — tool `source_placement_extend`, effect `write`, `open_world`, `task=True`. Runs the placement pass over an existing intake base, `run=` resuming a saved run. A function is placed only at `confidence` (default 90) or above; the rest go to the Place remaining code ticket.
- `status` — tool `source_placement_status`, effect `read`. The saved counts, cost, coverage gaps and progress of a run.
- `pending` — tool `source_placement_pending`, effect `read`. The unresolved placements with their source and category suggestions, paged by `offset` and `limit`.
- `resolve` — tool `source_placement_resolve`, effect `write`. Records one source-supported placement with its reason.
- `associate` — tool `source_placement_associate`, effect `write`, `open_world`. Asks Jev which provider category each named code item belongs to, in bulk. It writes no map records; the agent records what it accepts. It is not read-only because it sends project code to a third party and spends the person's credit, so no host may run it as a read, H17.

`extend` is marked `task=True` because a placement run over a whole base can take long; every other verb answers at once.

## Settings

The module declares none. Its thresholds are nouns of the call, `confidence` defaulting to 90 percent (`CONFIDENCE`), so a run carries the bar it was asked for. Nothing is sent unless the person has turned on `jev`; a key in the environment is not consent. The request then reads the key `jev_endpoint` names, `OPENROUTER_API_KEY` or `TYPESAFE_API_KEY`, from the environment when it is sent, and never stores it.

## Events

Subscribes to `intake.finished`: when a code intake's layer is ready and its base is active, and the person has turned `jev` on, the module starts the placement extension in a detached process. With `jev` off it starts nothing and sends nothing. The completed intake stands whether or not that extension runs — `jev` off, a missing key, an unavailable code graph MCP or a failed Jev request leaves it alone, BASE-065. It publishes no topic of its own; its writes go through the ordinary map operations, so the chassis fires `map.changed` for them.

## Sync and async

Every verb and the `intake.finished` subscriber are ordinary functions. The long pass does not hold a verb open: `extend` starts it and the run is followed through `status` and `pending`.

## Layers

The `source_placement` knowledge layer, mutable and hideable, created when absent and resumed when present, with its provenance. Placements are recorded at the provider element acting as RE, never at a purpose record: the implementation belongs to that element whatever purposes it serves for others. Code links keep exact file-qualified symbols and their reasons in the code layer. The module declares no tables; its run state is files under `projects/<folder_name(source)>-NNN/source_placement/` in the Metaform home, never written to the project folder by a new run, and the work left below the threshold is an ordinary work record, STORE-042.

## Lifecycle and cleanup

New placement runs and launch receipts live at `home.project_folder(project_id) / 'source_placement'`, the registered project's folder inside the Metaform home (`projects/<folder_name(source)>-NNN/source_placement/`), created with mode `0700`. An unregistered project cannot create a run folder. Every saved run must name one of the project's current bases, including runs read from the legacy project-folder location.

Cleanup happens in `clear_project`: clearing all bases also removes that registered folder's `source_placement/` tree, including launch receipts, because none of those runs can resume without its base. These files are not backed up or restored. Removing an empty project unregisters it and its bases while retaining its folder under the existing project lifecycle. Reusing its ID for another source folder does not expose those old runs. Existing run folders are never migrated, copied or moved to the registered location.

`start` is `migrate_names`, which runs once per home: what was stored under the old id `refactor` is kept under `source_placement`. It moves the module's enabled state, the members of the `modules`, `layers` and `jev_decisions` settings and of aliases that name it (`refactor.associate` becomes `source_placement.associate`), and the `refactor` layer of every base, renamed in place with its items and provenance. The marker `migrated-source-placement` in the home lists what moved; anything it could not read is said and tried again at the next start. At every start, with no marker, it renames what earlier versions wrote into a project folder's `.metaform/refactor/` in place to `.metaform/source_placement/`; nothing leaves the project folder, because every home that registers the project shares it, and the rename gives the same result whichever home runs it. A name already under `source_placement` is left and said. A renamed run not yet in review or complete has a saved threshold below 90% raised to 90%, so a resumed run never places a function under 90%. A run is read from `projects/<folder_name(source)>-NNN/source_placement/` in the home first and, when not there, from the project folder's `.metaform/source_placement/`, where it resumes. Remainder tickets made before the rename keep their notes and task text as written. No `stop`. The one process the module spawns is the detached placement run started from `intake.finished`; it is bound to the intake base it began on, and its inputs, completed batches and decisions stay under `projects/<folder_name(source)>-NNN/source_placement/` in the home so a retry reuses finished work instead of paying for it again. Unload leaves the `source_placement` layer, the code links, the work records and those files; nothing is removed with the module.

## Modules relied on

`map`, for the layer, item, work and code-link operations and for `map_cypher`, reached through its verbs. The configured code graph MCP supplies code evidence. Both are reached through the public interfaces; this module imports neither, and map reaches this module's parser only through `provided`.

## Systems supported

The three of `SUPPORTED_OS`. No verb narrows them. `associate`, and `extend` while it classifies, need the network; everything else works offline.

## Resources owned

The Tree-sitter runtime and JavaScript grammar, loaded when the parser is first asked and held for the process. The detached placement run and its files under `projects/<folder_name(source)>-NNN/source_placement/` in the home, released when the run ends; its saved records stay for the next run to resume. An HTTPS connection to the endpoint `jev_endpoint` names for the length of one Jev request.

## Installed and direct wheel

The same in both: the procedure, the prompts and the parser's grammar travel in the package, so a directly run wheel serves the procedure and parses source without anything fetched. With `jev` off, or without the key `jev_endpoint` names, the optional pass reports itself skipped, which is not a completed classification, and the ordinary intake is unaffected.

## Demonstration

```bash
metaform source_placement intake
metaform source_placement intake text="Extract the selection callbacks." association=jev confidence=90
metaform source_placement extend base=<base-id> paths='["src/app.js"]'
metaform source_placement status <run-id> base=<base-id>
metaform source_placement pending <run-id> base=<base-id> offset=0 limit=25
metaform source_placement resolve <run-id> <item-id> <provider-namespace> "<source evidence>" base=<base-id>
```

Read what a placement run recorded with `metaform map where address=<address>@source_placement`.

## Verification

`tests/test_source_placement.py` drives the real CLI and a fresh MCP server: module activation, the served procedure, the caller's text surviving as separate data, the annotations (`intake` read-only, `associate` neither read-only nor idempotent), and an existing map and populated source_placement layer left unchanged across repeated reads, and the one-time move of a home's `refactor` data to the new names. `tests/test_parser.py` the parser and the capability it offers, `tests/test_jev.py` the category request and its batching, `tests/test_pipeline.py` the run, its saved progress and its 90% threshold, `tests/test_remainder.py` the work left below it, and `tests/test_follow_on.py` the start from `intake.finished` and what happens when a service is absent.
