# Chassis product and complete demonstration

> **Superseded plan/specification — retained evidence.**
> [REQUIREMENTS.md](REQUIREMENTS.md) is the complete governing contract.
> Its [section 20](REQUIREMENTS.md#20-remediation-instructions) authorizes
> active outside-in remediation, tracked in the [live matrix](REMEDIATION-MATRIX.md).
> The earlier tasks, authority statements, technology choices, open questions and
> completion claims below add no requirements and impose no continuing pause.
> They remain useful as historical implementation and verification evidence.

The chassis is a standalone engineering product. Its specification and public
objects govern its implementation; legacy feature code is historical reference.
The existing first-slice services are the starting foundation to complete.

## Acceptance journey

1. Start from a polished base CLI with status, project, runtime and loaded-module
   information; navigate module menus and inspect point-of-use help.
   Module guides, command help and setting help come from Python declarations.
2. Load three external modules through the same public module contract: one
   standalone all-services template and two modules built from that template.
3. Enter a module; a hidden working-folder binding persists its menu across CLI
   invocations. Exit removes only that binding and restores the base surface.
4. Enter an assigned nonce; its module surface replaces the base surface, shows
   exact instructions/header, accepts a headed answer, and preserves completion
   before marker cleanup. `exit` detaches navigation; complete/abort settle work.
5. Change module settings to enable/disable commands; help, direct dispatch and
   generic operation dispatch observe the same module-declared availability.
   Configure those values in a staged terminal setup menu or entirely through
   scripted CLI commands. Preserve glued baselines across ordinary resets.
6. Demonstrate synchronous records, revisions and provenance, asynchronous work,
   concurrent status access, job cancellation, and retained results.
7. Demonstrate request and completion events between `event_requester` and
   `harness_runner`. The request handler queues work and returns without waiting
   for the harness response. The requester receives the response in a later event.
   Expose event identities and delivery outcomes for inspection.
8. Launch a configurable agent harness without blocking the CLI. Retain PID,
   project, nonce, actual prompt, stdout/stderr, exit outcome and response.
   Support both Codex and Claude presets and include a deterministic local harness
   that needs no credentials.
9. Unload/reload modules cleanly, preserving stored objects and settings,
   while the chassis and unrelated module remain usable.
10. Repeat the journey through installed/module/executable-wheel entrypoints.

## Implementation contracts

The four established imports remain `settings`, `event`, `cli`, `data`. Public
`work` and `modules` services provide assignment/job access and module catalog inspection.
`objects` supplies typed value objects and transport serialization.
SQLite remains one global project-owned store. Service façades resolve the active
runtime/context without opening independent stores at import time.

Plugin gains `description`, `command_visibility: dict[str, Callable[[], bool]]`
and `operation_visibility: dict[str, Callable[[], bool]]`. Predicates execute with
module-bound settings/context and affect discovery and invocation consistently.
A command and its operation use the same predicate when they express one feature.
These are module-authored availability rules, not inference-output conditions.

A chassis-owned background runtime survives CLI client exit. Local authenticated
RPC routes calls to one instance per global root. Clients import command definitions
for Click presentation but never run lifecycle hooks. Runtime start/status/stop
remain chassis operations independent of web. Shutdown cancels owned asynchronous
jobs, settles workers, unloads modules, and releases endpoint ownership.

Host signatures: `await Runtime.spawn(module, operation, arguments, context) -> Job`,
`await Runtime.cancel(job_id) -> Job`, `Runtime.jobs(context=None)`, `Runtime.job(id)`.
Runtime invoke remains awaitable. Jobs persist queued/running/completed/failed/
cancelled/interrupted outcomes, result/error, producer and work identity. Restart
marks abandoned nonterminal local jobs interrupted; it does not silently retry.

Public work service: `submit_job(operation, **arguments)`, `await asubmit_job(...)`,
`jobs()`, `job(id)`, `cancel(id)`, `assign(prompt, **metadata)`, `assignment(nonce=None)`,
`submit(header, answer, nonce=None)`, `complete(nonce=None)`, `track_process(pid, role,
nonce=None)`; async counterparts for blocking service access. Context defines module
and project. Assignment methods wrap the shared chassis assignment service.

Data service returns typed Record objects (with backward-compatible mapping reads),
RecordRef and Producer objects; CLI/transport serializers retain their meaning.
Store internals remain an explicit SQLite mapping, not the module-facing contract.

## Module installation and help

Install a module by placing its `.py` file or Python package directory directly
under `<root>/plugins`. CLI connections and setup-screen refresh discover entries.
The module exports `PLUGIN`, including its settings and help; installation does
not require a separate manifest.

The plain-text file `<root>/plugins/disabled` is authoritative for disabled
modules. Each non-comment entry identifies an immediate installed filename
(including `.py`) or package-folder name. Explicitly loaded modules outside this
folder use their resolved absolute paths. CLI and setup controls resolve module
IDs to these entries and update the same file, preserving comments and blank
lines. If the file is absent, present modules are enabled. Disabled entries are
skipped before importing their code.

`modules enable ID` and `modules disable ID` control this state. Disabling or
removing a module withdraws its commands, settings, subscriptions and help while
retaining its catalog entry, saved values and glue. Restoring the files makes the
module available again unless it remains listed in `disabled`.

`Plugin.help` embeds the module's guide; Click commands and `Setting.help` retain
their own help in that same module. `help [MODULE|COMMAND]`, contextual `--help`
and setup-screen F2 present the appropriate live declaration. The chassis does
not maintain a second help catalog.

## Settings ownership and terminal setup

Each module's Python `Plugin.settings` tuple owns its defaults, types, help and
menu entries. The chassis builds one BIOS-style keyboard setup surface from these
live declarations. Unloaded modules have no settings surface; their saved values
and pins survive for reuse when enabled again.

`settings` opens the setup screen on a terminal and prints values for nonterminal
or `--json` use. `config [MODULE]` opens the same screen with optional module scope;
`config --show` lists values, and `tui` opens the setup screen. The menu groups
modules, displays settings and help, and stages edits until save. Navigation,
boolean/module toggles, numeric adjustment, search, individual/group reset, glue,
preview, save, save-and-exit and save/discard/continue on exit are supported.

Top-level `set MODULE KEY VALUE [--glue]` and
`unset MODULE [KEY|--all] [--unglue]` have equivalents under `settings`.
`settings reset MODULE KEY [--unglue]` remains available. Declared defaults apply
out of the box. Gluing saves the chosen value as the user's baseline; reset skips
it until explicitly unglued. Updating a glued value preserves the pin by default.
Unloading and reloading preserves both saved values and glue state.

Public service signatures include `settings.set(key, value, *, glue=None)`,
`pin(key, pinned=True)`, `reset(key, *, unglue=False)`, and the `unset` alias, with
asynchronous counterparts. `describe()` reports the default, effective value,
source and pinned state. The terminal and scripted interfaces use these services.

## Three demonstration modules

`showcase` is the standalone hello-world template for the imported chassis
services: `settings`, `event`, `cli`, `data`, `work`, and `modules`. It demonstrates
settings, conditional commands, records/provenance, assignments, background jobs,
synchronous and asynchronous callbacks, lifecycle hooks, and local subscriptions.
It runs without either event example loaded.

`event_requester` and `harness_runner` are built from that template, with the
relationship visible in their source and package dependencies. The requester
publishes a stored request reference and subscribes to completed responses. The
runner subscribes to requests, queues an assigned harness job, and publishes the
stored response reference when the harness finishes. Both directions use the
same chassis event API. The requesting command returns while the job runs.

The harness runner also offers direct execution and Codex/Claude presets. Its
bundled fixture is explicitly a deterministic protocol demonstration; actual agent
execution uses the configured harness command, without invented response gates.
The existing optional web plugin is a separate feature demonstrating global web
lifecycle and settings, not a fourth module in this three-module template set.

## Documentation and boundaries

The [public API guide](../docs/plugin-api.md) describes the implemented services
and links each module's walkthrough. This chassis work does not itself migrate
legacy intake, workflows, graph layers, or MCP adapters. Those features consume
the same public services in subsequent work.
