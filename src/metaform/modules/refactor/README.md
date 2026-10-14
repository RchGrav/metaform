# refactor

Prepares reusable refactoring context on an existing functional map. It connects each receiving element's purpose to implementation evidence and records the inference that editing agents would otherwise repeat.

## Purpose

Symbol and call lookup says what the code is; it does not say which functionality the code serves, what a proposed boundary must preserve, or why one extraction depends on another. This module serves the procedure that works that out, BASE-063, and the agent following it records the result once, in the `refactor` knowledge layer, at the element that owns it. Later agents read that knowledge instead of reconstructing it. BASE-065 adds the pass that places the confidently classified code upfront and leaves the rest as ordinary work.

## Template version

The template changelog version this module started from: 0.3.0, with the Unreleased changes.

## Declaration

`SUPPORTED_OS` is Linux, macOS and Windows: the procedure is text and the parser's wheels are built for all three. `DEPENDENCIES` is `tree-sitter>=0.25,<0.26` and `tree-sitter-javascript>=0.25,<0.26`: this module owns the Tree-sitter runtime and the JavaScript grammar, and offers its parser to other modules rather than letting them declare it, BASE-065. `SHIPS_DISABLED` is False: the module ships enabled, and reading its procedure costs nothing until an agent follows it. `REMOTE_AGENT` is False: the intake prepares a project's knowledge before work is assigned, so it runs where the project is.

The code is in parts, each under 500 lines: `parser.py` the Tree-sitter source parser offered as `code.functions`, `jev.py` the bulk category request, `pipeline.py` the placement run, its batches and its saved progress, and `remainder.py` the work record left for a reasoning agent.

### Toolbar items and panes

None. The module's surfaces are the command line and MCP; what it records is read through the map's own panes, at `<address>@refactor`.

## Common base used

`metaform.module` for the declaration, `Context`, `Stop`, `Provides` and `Subscription`, for `child_environment` when the extension is started as its own process, and for `provided` to find the code graph capability. `metaform.prompt_files` reads the authored procedure out of `resources/prompts.xml` and binds the caller's task text as data, `prompt_files.required` where a missing prompt is a defect, MCP-031. `metaform.data` for `Store` and `Node`: the module writes through the public layer, item and work operations only, and declares no tables of its own. It does not use `metaform.jev`; its Jev request is a bulk category selection of its own in `jev.py`, over OpenRouter.

### Provides

`Provides('code.functions', ...)`, the source parser: the suffixes it reads and the function it parses with. The map module finds it with `provided(folder, 'code.functions')` and so declares no parser dependency of its own; disabling refactor withdraws the capability and map's inventory falls back to the configured code graph MCP, and never withdraws map, intake or dispatch, BASE-065.

## Prompts

In `resources/prompts.xml`: `instructions`, the module's line in the instructions agents read; `intake`, the authored procedure itself, written as Axiom rather than this store's usual XML because it is the procedure the owner refined; `input`, which binds the caller's optional task text as a JSON data block after the procedure; `jev`, the optional bulk association pass added only when the caller asks for it; `remainder`, the session text for the work left below the threshold; and `commands`, which offers the procedure as the client prompt `refactor-intake`. The module declares no rules.

## Verbs

- `intake` — `metaform refactor intake`, tool `refactor_intake`, effect `read`. Serves the procedure as written, with `text` bound after it as data, and `association=jev confidence=<n>` adding the optional pass. It opens no layer and records nothing.
- `extend` — tool `refactor_extend`, effect `write`, `open_world`, `task=True`. Runs the placement pass over an existing intake base, `run=` resuming a saved run.
- `status` — tool `refactor_status`, effect `read`. The saved counts, cost, coverage gaps and progress of a run.
- `pending` — tool `refactor_pending`, effect `read`. The unresolved placements with their source and category suggestions, paged by `offset` and `limit`.
- `resolve` — tool `refactor_resolve`, effect `write`. Records one source-supported placement with its reason.
- `associate` — tool `refactor_associate`, effect `read`, `open_world`. Asks Jev which provider category each named code item belongs to, in bulk. It writes no map records; the agent records what it accepts.

`extend` is marked `task=True` because a placement run over a whole base can take long; every other verb answers at once.

## Settings

The module declares none. Its thresholds are nouns of the call, `confidence` defaulting to 83 percent, so a run carries the bar it was asked for. The Jev request reads `OPENROUTER_API_KEY` from the environment when it is sent, and never stores it.

## Events

Subscribes to `intake.finished`: when a code intake's layer is ready and its base is active, the module starts the placement extension in a detached process. The completed intake stands whether or not that extension runs — a missing key, an unavailable code graph MCP or a failed Jev request leaves it alone, BASE-065. It publishes no topic of its own; its writes go through the ordinary map operations, so the chassis fires `map.changed` for them.

## Sync and async

Every verb and the `intake.finished` subscriber are ordinary functions. The long pass does not hold a verb open: `extend` starts it and the run is followed through `status` and `pending`.

## Layers

The `refactor` knowledge layer, mutable and hideable, created when absent and resumed when present, with its provenance. Placements are recorded at the provider element acting as RE, never at a purpose record: the implementation belongs to that element whatever purposes it serves for others. Code links keep exact file-qualified symbols and their reasons in the code layer. The module declares no tables; its run state is files under `.metaform/refactor/`, and the work left below the threshold is an ordinary work record, STORE-042.

## Lifecycle and cleanup

No `start` or `stop`. The one process the module spawns is the detached placement run started from `intake.finished`; it is bound to the intake base it began on, and its inputs, completed batches and decisions stay under `.metaform/refactor/` so a retry reuses finished work instead of paying for it again. Unload leaves the `refactor` layer, the code links, the work records and those files; nothing is removed with the module.

## Modules relied on

`map`, for the layer, item, work and code-link operations and for `map_cypher`, reached through its verbs. The configured code graph MCP supplies code evidence. Both are reached through the public interfaces; this module imports neither, and map reaches this module's parser only through `provided`.

## Systems supported

The three of `SUPPORTED_OS`. No verb narrows them. `associate`, and `extend` while it classifies, need the network; everything else works offline.

## Resources owned

The Tree-sitter runtime and JavaScript grammar, loaded when the parser is first asked and held for the process. The detached placement run and its files under `.metaform/refactor/`, released when the run ends; its saved records stay for the next run to resume. An HTTPS connection to OpenRouter for the length of one Jev request.

## Installed and direct wheel

The same in both: the procedure, the prompts and the parser's grammar travel in the package, so a directly run wheel serves the procedure and parses source without anything fetched. Without `OPENROUTER_API_KEY` the optional pass reports itself unavailable, which is not a completed classification, and the ordinary intake is unaffected.

## Demonstration

```bash
metaform refactor intake
metaform refactor intake text="Extract the selection callbacks." association=jev confidence=83
metaform refactor extend base=<base-id> paths='["src/app.js"]'
metaform refactor status <run-id> base=<base-id>
metaform refactor pending <run-id> base=<base-id> offset=0 limit=25
metaform refactor resolve <run-id> <item-id> <provider-namespace> "<source evidence>" base=<base-id>
```

Read what a placement run recorded with `metaform map where address=<address>@refactor`.

## Verification

`tests/test_refactor.py` drives the real CLI and a fresh MCP server: module activation, the served procedure, the caller's text surviving as separate data, the read-only annotations, and an existing map and populated refactor layer left unchanged across repeated reads. `tests/test_parser.py` the parser and the capability it offers, `tests/test_jev.py` the category request and its batching, `tests/test_pipeline.py` the run, its saved progress and its threshold, `tests/test_remainder.py` the work left below it, and `tests/test_follow_on.py` the start from `intake.finished` and what happens when a service is absent.
