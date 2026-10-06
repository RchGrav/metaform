# Standalone hello-world chassis template

Usage guidance is embedded in this module's Python `Plugin.help` contribution,
alongside its settings and commands. Contextual CLI help displays that guidance;
derived modules provide their own text with `replace(TEMPLATE, help=...)`.

`showcase` works by itself and demonstrates all public chassis services:

```python
from metaform import settings, event, cli, data, work, modules
```

It registers settings and conditional Click commands, creates namespace objects
and receiver-owned joins with retained revisions, inspects producers, starts async jobs, issues nonce assignments,
and sends local events to its declared async receiver and dynamically registered
sync observer. It demonstrates
sync activation and async teardown. Neither event-demo module is needed.

The separate [event requester](../event_requester/README.md) and
[harness responder](../../../modules/harness_runner/README.md) show how to derive two cooperating
modules from this template using the same chassis event bus.

## Package structure

| File | Responsibility |
| --- | --- |
| `__init__.py` | Expose `PLUGIN` as the package's public entry. |
| `plugin.py` | Compose contributions and activation/teardown hooks. |
| `settings.py` | Declare defaults/help and read visibility switches through chassis settings. |
| `dao.py` | Read/write owned joins and follow exact references through the shared chassis data API. |
| `events.py` | Declare subscriptions and handle received events and dynamic watches. |
| `commands.py` | Adapt Click arguments to the registered operations. |
| `operations.py` | Implement synchronous operations and asynchronous background work. |
| `help.py` | Provide the module guide displayed by contextual help. |

The layout follows the [Metaform module structure guide](../../../specifications/module-structure-refined.md).
The chassis persists configuration and objects, tracks producing operations,
dispatches synchronous callbacks in worker threads, and owns background jobs and
registered contributions. Copy the whole package to `modules/` to keep its imports
and resources together. Single-file modules use the same `Plugin` contract.

## Run the standalone template

From the repository root, set up a temporary data root and source workfolder.

```bash
export METAFORM_HOME="$(mktemp -d)"
METAFORM_DEMO_REPO="$PWD"
METAFORM_DEMO_WORK="$(mktemp -d)"
mf() { "$METAFORM_DEMO_REPO/.venv/bin/python" -m metaform --project demo "$@"; }
mf modules load "$METAFORM_DEMO_REPO/examples/modules/showcase"
mf projects add demo "$METAFORM_DEMO_WORK"
cd "$METAFORM_DEMO_WORK"
mf --help
mf enter showcase
mf --help
mf showcase
```

`enter` writes `.metaform-context`. Following CLI processes recover the module,
project and global root from this hidden file. `exit` removes it and restores the
base command menu. Each command is a new client of the same persistent runtime.

## Settings, commands, objects and local events

```bash
mf sample-write --text 'Hello, chassis'
mf sample-write --text 'A retained revision'
mf sample-read --revision 1
mf namespace get data.showcase.note
mf namespace get data.showcase.observation
mf namespace get data.showcase.receipt
mf events
mf settings
mf settings set showcase write_enabled false
mf --help
mf sample-write --text 'This command is now unavailable'
mf settings reset showcase write_enabled
mf sample-watch --off
mf sample-write --text 'The dynamic observer is off; the declared receiver stays active'
mf sample-watch --on
mf sample-write --text 'The live observer receives this event'
mf events
```

`write_enabled` controls discovery and direct/generic invocation of note,
annotation, prompt and authoring commands and operations. `async_enabled` controls
the asynchronous command and operations.
Settings are registered in the module's Python definition. `mf settings` opens
the BIOS-style setup screen in a terminal; `mf --json settings` prints the same
registered values for scripts. Edits in the screen are staged until S saves them.
F2 reads the module's embedded help.

Set an owned baseline with `mf set showcase label 'My baseline' --glue`.
`mf unset showcase --all` restores other settings to their declared defaults while
preserving that label. `mf unset showcase label --unglue` releases it and restores
the module default. Unloading hides these settings but retains their saved values
and glue state for reactivation.
Note and annotation writes return and publish a `JoinRef` with project, namespace address,
persistent join ID and exact revision. `sample-write` revises the `note` join on
`data.showcase.note`. Both event handlers write `example.receipt` joins containing
the publication ID and those exact references, with their own producing operations.
The `sample-read` result contains `reference`, `join` and `productions`; each
production includes its own reference and the chassis-retained operation evidence.

| Setting | Default | Effect |
| --- | --- | --- |
| `label` | `Showcase` | Label retained on new note revisions. |
| `write_enabled` | `true` | Exposes note, annotation, prompt and authoring commands/operations. |
| `async_enabled` | `true` | Exposes delayed work and its queue command. |
| `watch_enabled` | `true` | Restores the dynamic observer on activation. |
| `lifecycle` | `new` | Updated to `started` / `stopped` by lifecycle hooks. |

These declarations live in Python. Activation registers them into chassis
configuration; the module does not write a second configuration file. Settings
remain in chassis storage while the module is absent.

### Namespace objects and typed joins

```bash
mf sample-join --text 'An annotation of the current note'
mf namespace get document.showcase.note
mf sample-join --text 'A revised annotation' --join-id RETURNED_JOIN_ID
```

`dao.annotate` writes an `example.note` join through
`data.namespace_store().put_join`. The returned `JoinRef` contains project,
namespace address, persistent join id, and exact revision. The join stores the
source note's `JoinRef`; event receivers retain the new annotation's `JoinRef`.
Earlier versions still resolve after editing. The chassis writes the separate
provenance join linking the annotation to its producing operation and inputs.
The DAO supplies feature content while the chassis chooses storage and owns
identity, revisions and provenance.

In an operation, use `data.namespace_store().resolve(reference)` or its async
`aresolve` counterpart. Both retain the consumed revision as an operation input.
Saved records from an earlier version remain readable through the chassis' existing
record/history surface; this module's new writes use the owned joins described here.

## Authored answer with exact context

```bash
mf sample-prompt --text 'Explain the recorded observation.'
mf sample-author --answer 'My authored answer' --source-revision 1 --prompt-revision 1
mf sample-read --address document.showcase.answer --join-id RETURNED_JOIN_ID
mf sample-prompt --text 'An edited instruction'
mf sample-write --text 'An edited source'
mf sample-read --address document.showcase.answer --join-id RETURNED_JOIN_ID
```

This is a deterministic authoring demonstration. You supply the answer; the
operation does not invoke a model. Its `example.authored` join records
`origin: authoring-demonstration`, the exact prompt join revision, its rendered
text, the `source` binding, the exact consumed source/prompt references, an empty
selected-layer list, and the answer unchanged. The fixed rendering is the supplied
instruction, a `Recorded note:` label, and the source note's text. No layer is read
or selected by this example.

`prompt(text)` writes the `instruction` join on `document.showcase.prompt`.
`author(answer, source=None, prompt=None)` accepts exact `JoinRef` inputs; omitted
references select the latest sample note and instruction. `source_revision` and
`prompt_revision` select earlier versions for the CLI walkthrough. The operation
resolves those exact inputs through the data service before writing its output.
Every invocation gets its own producing occurrence. The output's provenance join
links to that occurrence, its actual inputs, result, and parent operation. Follow
the stored `source` or `prompt` reference with `inspect(reference=...)` to inspect
its own producing operation. Editing either input leaves the earlier answer's
rendered context and consumed revisions intact.

Feature rendering belongs to `operations.py`; the DAO supplies the authored
join content through shared storage. The chassis owns the production occurrence,
exact read tracking and provenance joins. A module making an actual model call
must retain that call's real prompt, context and answer through the same contract.

## Async work, status and cancellation

```bash
mf sample-async --text 'Finished in the background' --seconds 2
mf status
mf jobs
mf jobs show JOB_ID
mf sample-async --text 'A cancellable job' --seconds 30
mf jobs cancel JOB_ID
mf jobs show JOB_ID
```

The command returns a job id immediately. Status and other commands remain usable
while the runtime owns the work. Successful results and cancelled outcomes remain
inspectable after the original CLI process exits.

## Nonce menu and headed submission

```bash
mf sample-assignment --prompt 'Describe what you observed in this demo.'
mf exit
mf begin NONCE_FROM_ASSIGNMENT
mf --help
mf status
```

The assignment menu replaces the base commands. `begin` creates `.agentid/nonce`;
help and status deliver the exact instructions, header and knowledge addresses.
The instruction is retained as an authored prompt join. The available sample
note is supplied as an exact `JoinRef`, so subsequent note edits do not change
which revision was offered. That available reference is not recorded as content
consumed by the assignee until it is actually read through the shared data service.
Copy the delivered header unchanged into `answer.json`:

```json
{"header": {"assignment": "DELIVERED_ID", "nonce": "DELIVERED_NONCE", "step": "1"}, "answer": "My observation"}
```

```bash
mf submit --input answer.json
mf complete
mf --help
```

Completion is stored before the marker is removed and the base menu returns.
`exit` detaches navigation without settling work; `abort` settles it as aborted.
`--nonce NONCE` selects assigned work without creating a marker.

## Unload and restore

```bash
mf modules unload showcase
mf namespace get data.showcase.note
mf modules load "$METAFORM_DEMO_REPO/examples/modules/showcase"
mf enter showcase
mf settings
mf exit
mf runtime stop
```

Unload withdraws commands, subscriptions and live work. Objects, settings and
provenance remain in the global database. Reload restores module contributions.

## Feature map

| Capability | Concrete demonstration |
| --- | --- |
| Public namespace objects and exact reference serialization | `sample-write`, `sample-read`, `showcase` |
| Global storage, project ownership, revisions, provenance | Repeat writes, read revision 1, inspect producer |
| Universal objects, typed joins and reference exchange | `sample-join`, revise its id, inspect `document.showcase.note` and event refs |
| Authored prompt, exact object bindings, rendered text and answer | `sample-prompt`, `sample-author`, inspect earlier input revisions |
| Settings declaration/get/set/reset/description | Label, lifecycle, command switches, chassis settings menu |
| Conditional command and operation availability | Toggle `write_enabled` and `async_enabled` |
| Sync and async execution/context propagation | Sync writes, async delayed job, async event publication |
| Sync and async lifecycle | `start`, `stop`; inspect lifecycle setting and producer history |
| Declared/dynamic event registration, delivery, history and removal | `sample-watch --on/--off`, writes, receipt joins, `events` |
| Assignment prompt/header/nonce and completion | `sample-assignment`, `begin`, `submit`, `complete` |
| Module navigation and hidden binding | `enter showcase`, later invocations, `exit` |
| Background jobs/status/cancellation | `sample-async`, `jobs`, `jobs show`, `jobs cancel` |
| Module catalog and active context | `showcase` calls `modules.describe/catalog` and `cli.context` |
| Persistent runtime and removable features | Separate CLI processes, unload/reload, `runtime stop` |
| Installed/module/wheel entrypoints | Replace `python -m metaform` with `metaform` or `python /path/to/metaform.whl` |
| Cross-module events and real agent processes | Separate requester/responder examples derived from this template |

The sync and `a`-prefixed APIs expose the same capabilities. Examples use both
execution paths in useful work instead of duplicating every getter call.

## Public operations and runtime boundaries

| Operation | Return value |
| --- | --- |
| `features` | Context, settings, module catalog, namespace references, jobs and events. |
| `write`, `annotate`, `prompt`, `author` | Exact produced `JoinRef`. |
| `inspect` | Exact join and its retained producing occurrences. |
| `delayed` | Produced `JoinRef` after the configured delay; async. |
| `queue` | Chassis-owned job immediately; its terminal result is a `JoinRef`. |
| `assignment` | Chassis `Assignment`, including nonce, exact instructions and header. |
| `watch` | Current `watch_enabled` state. |

The package depends on `metaform-chassis` and Click, as declared in
`pyproject.toml`. It requires no other Metaform module, model credentials or
external service. It uses portable Python APIs and declares support for Linux,
macOS and Windows; the tests reported for this change ran on Linux. All module
resources are Python code in this directory. User-authored prompts and answers
are retained through chassis storage, so operation does not depend on a source
checkout or writing beside a wheel.

The chassis schedules async jobs and both kinds of event callback. Unload drains
owned work and removes subscriptions; `stop` releases the dynamic watch and
records lifecycle state. No subprocess, private event loop or independent
database is opened by this module. Project, module, nonce and producing operation
come from the execution context supplied by the chassis.

## Build and derive

```bash
python -m build --wheel --no-isolation examples/modules/showcase
```

The resulting `metaform-showcase` package exports `showcase.PLUGIN`. Each derived
module owns a small local `template.py` copied from this lifecycle scaffold and
uses `dataclasses.replace` to supply its own id, commands, operations, settings,
subscriptions, and visibility maps. All module execution remains bound to its own
chassis context. The derived modules can be copied or installed independently.
