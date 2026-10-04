# Metaform Plugin Package Structure

This document defines the recommended internal structure for a substantial Metaform plugin.

It is an **organization and implementation template** for module authors. It does not replace the chassis plugin contract. A module may still be a single `.py` file when that is sufficient. When a feature grows into a larger module, use this shape so commands, operations, settings, events, data access, lifecycle behavior, and packaged resources remain understandable and independently maintainable.

The architectural boundary is:

- The **chassis owns shared infrastructure**: module discovery/lifecycle coordination, execution context, settings persistence, event dispatch, storage, provenance, assignments/work identity, runtime scheduling, and contextual CLI composition.
- The **plugin owns feature behavior**: its operations, domain objects, DAOs, commands, event handlers, settings declarations, help, and resources.
- Module-internal files organize one plugin. They do not create parallel configuration, runtime, database, event, or command frameworks.

---

## 1. Recommended package shape

```text
my_plugin/
├── __init__.py          # Public package entry; exposes PLUGIN
├── plugin.py            # Plugin composition and module-owned lifecycle hooks
├── operations.py        # Feature behavior exposed through public operations
├── commands.py          # Complete Click command objects adapting operations
├── events.py            # Event handlers and event contribution declarations
├── settings.py          # Module-owned setting declarations/defaults/help
├── dao.py               # Module-owned DAOs over the chassis data service
├── models.py            # Module-private DTOs/value objects/domain models
├── help.py              # Optional larger module guide/help text
├── resources/           # Optional packaged templates/assets/data
│   └── ...
└── tests/
    ├── test_operations.py
    ├── test_commands.py
    ├── test_events.py
    ├── test_dao.py
    └── test_lifecycle.py
```

A module can add more domain-specific files when the feature genuinely needs them. Do not split files merely to reproduce this tree.

A small plugin can collapse the same responsibilities into one `.py` file. The public contract is the same either way.

---

## 2. `__init__.py` — one public module entry

`__init__.py` should stay small.

Its job is to expose the plugin's public contribution object:

```python
from .plugin import PLUGIN

__all__ = ["PLUGIN"]
```

The chassis discovers and activates the module through this public object.

Do not make import itself start workers, open databases, launch subprocesses, start listeners, or execute feature work. Importing Python executes module code; resource acquisition belongs to lifecycle hooks.

---

## 3. `plugin.py` — composition root

`plugin.py` assembles the module's contributions into the public Metaform plugin object.

It should answer:

- What is this module?
- What operations does it expose?
- What commands does it contribute?
- What settings does it declare?
- What events does it subscribe to?
- What lifecycle work does it own?
- What help does it expose?
- Which operations or commands are currently available?

Conceptual shape:

```python
from metaform import Plugin

from .commands import COMMANDS
from .events import SUBSCRIPTIONS
from .help import MODULE_HELP
from .operations import OPERATIONS
from .settings import SETTINGS

async def startup(context):
    ...

async def shutdown(context):
    ...

PLUGIN = Plugin(
    name="my_plugin",
    description="...",
    operations=OPERATIONS,
    commands=COMMANDS,
    settings=SETTINGS,
    subscriptions=SUBSCRIPTIONS,
    startup=startup,
    shutdown=shutdown,
    help=MODULE_HELP,
)
```

Use the actual public API types and signatures supplied by the chassis. The example above illustrates responsibility placement, not a replacement API.

Keep composition here. Put feature logic in the files that own it.

---

## 4. `operations.py` — the feature's executable behavior

Operations are the primary callable feature surface.

A command, web action, MCP adapter, workflow step, or event handler should reach shared feature behavior through operations rather than each interface implementing its own version.

Typical shape:

```python
def inspect_item(item_id: str):
    ...

async def refresh_item(item_id: str):
    ...

OPERATIONS = {
    "inspect": inspect_item,
    "refresh": refresh_item,
}
```

Operations may be synchronous, asynchronous, or both according to what they actually do.

### Rules

- Keep business/domain behavior here rather than in Click callbacks.
- Accept the chassis-supplied execution/work context where the public operation contract provides it.
- Preserve project, module, assignment/nonce, operation, and producer context passed by the chassis.
- Return domain/results through the public operation contract.
- Do not create a private event loop.
- Do not create a second global runtime.
- Do not bypass chassis provenance for produced Metaform records.
- Do not make an operation's CLI presentation its only callable implementation.

### Blocking work

A synchronous operation is not automatically blocking. Lightweight synchronous work may remain synchronous.

If an operation performs blocking I/O or expensive work, declare/use the execution form supported by the chassis so it can be scheduled appropriately. Async work runs through the chassis runtime. CPU-heavy or independently isolated work can use the execution adapters provided for that need.

The plugin should not silently invent its own thread/process scheduler when the chassis execution service already owns that boundary.

---

## 5. `commands.py` — complete CLI presentation

Commands are the module's Click-facing adapters.

The module owns complete command definitions:

- command/group names;
- arguments;
- options;
- types;
- defaults;
- nested groups;
- command help;
- examples where useful.

Example organization:

```python
import click

@click.group("my-plugin")
def my_plugin_group():
    """Operate the My Plugin feature."""

@my_plugin_group.command("inspect")
@click.argument("item_id")
def inspect_cmd(item_id):
    # Delegate through the shared operation path.
    ...
```

The chassis composes these contributed commands into the contextual CLI.

### Rules

- Commands delegate to the same registered operations used by other interfaces.
- Do not put the feature's only implementation inside a Click callback.
- Command availability predicates belong to the module and must agree with direct operation availability when they represent the same feature.
- Help and direct invocation must observe the same current module/context state.
- Fully specified commands must be usable non-interactively.
- Do not duplicate chassis administration commands inside feature modules.

---

## 6. `settings.py` — declarations owned by the module

The module defines its own settings, including:

- key;
- type;
- default;
- readable label;
- help/explanation;
- examples when useful;
- any constraints intrinsic to that setting.

Conceptual example:

```python
from metaform import Setting

SETTINGS = (
    Setting(
        key="interval",
        default=60,
        value_type=int,
        help="Seconds between refresh operations.",
    ),
)
```

The exact class/signature comes from the public chassis API.

The chassis owns:

- persistence;
- effective-value resolution;
- glue/pinning behavior;
- set/unset/reset behavior;
- settings UI/CLI presentation;
- preservation while a module is absent;
- module identity used to separate settings.

Do not create a second `config["plugins"][name]` configuration system inside the module.

A module may have a `config.py` helper if it performs domain-specific interpretation of its resolved settings, but that helper consumes the chassis settings service rather than replacing it.

---

## 7. `dao.py` — module-owned Data Access Objects

Complex modules often need a domain-specific data API. This is the correct place for DAOs.

A DAO translates between the module's domain operations and the chassis data service.

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Item:
    id: str
    name: str

class ItemDAO:
    def __init__(self, data_service):
        self._data = data_service

    def get(self, item_id: str) -> Item | None:
        record = self._data.get(...)
        ...

    def save(self, item: Item):
        return self._data.put(...)
```

The DAO owns **domain-specific data-access logic**.

The chassis data/persistence layer owns:

- the authoritative database;
- physical database location;
- connections;
- transactions;
- concurrency/locking policy;
- project ownership;
- revisions;
- durable identities;
- producer/provenance relationships;
- payload durability;
- migration of shared storage.

Therefore a normal plugin DAO should not receive or retain a raw SQLite connection merely to implement its feature.

The relationship is:

```text
Feature operation
    ↓
Module DAO
    ↓
metaform.data
    ↓
Chassis persistence/provenance services
    ↓
Authoritative storage
```

If a feature intentionally manages an external or feature-specific datastore, that is a distinct feature responsibility and should not be confused with direct access to Metaform's authoritative database.

---

## 8. `models.py` — module-local domain types

Use module-local dataclasses, enums, typed dictionaries, or other value objects to make the feature's internal contracts explicit.

These are useful for:

- DAO return values;
- operation inputs/results;
- parsed resource structures;
- event-specific domain payloads;
- module-private state.

Do not create alternate representations of chassis-owned identities merely for convenience. Preserve chassis record references, namespace addresses, assignment identities, revisions, and producer identities where those are the actual objects being referenced.

---

## 9. `events.py` — subscriptions and publications

Event handlers should be kept separate from feature operations when a plugin participates meaningfully in the event bus.

Example organizational shape:

```python
async def on_item_requested(event, context):
    ...

def on_settings_changed(event, context):
    ...

SUBSCRIPTIONS = (
    ...,
)
```

The chassis owns event dispatch and execution boundaries.

The module owns:

- which events it subscribes to;
- handler behavior;
- which events it publishes as part of its feature;
- any domain-specific interpretation of those events.

Events should retain the chassis-provided attribution/context, including the publishing module, project, assignment when applicable, producer/operation identity, and affected record references.

Store durable data through chassis services and publish references when that is the appropriate event contract rather than treating transient event payloads as the authoritative database.

Event handlers do not own workflow progression merely because they receive notifications.

---

## 10. Lifecycle ownership

A module may acquire resources during activation/startup, including:

- event subscriptions;
- background tasks;
- temporary resources;
- subprocesses or harnesses;
- file handles;
- feature-specific listeners;
- caches;
- external client sessions.

Anything the plugin intentionally acquires must have an identifiable owner and a corresponding release path.

### Activation

Activation should be conceptually transactional:

```text
construct module
→ receive chassis services/context
→ register contributions
→ acquire module-owned resources
→ run startup
→ active
```

If activation fails partway through, contributions/resources already acquired by that activation must be unwound.

A failed module must not remove chassis administration or unrelated modules.

### Deactivation

Deactivation should:

1. stop accepting new module-owned work where applicable;
2. withdraw its executable contributions/subscriptions;
3. settle or request cancellation of module-owned work according to its execution contract;
4. release module-owned resources;
5. run final teardown;
6. leave persisted settings/data/provenance intact unless an explicit feature operation says otherwise.

`task.cancel()` is a cancellation request, not proof that work has stopped. Track owned work until its actual terminal state where the chassis contract requires that distinction.

Deactivation is not the same operation as replacing Python code in a live process. Removing references from `sys.modules` does not prove that existing objects/resources disappeared.

---

## 11. Error boundaries

Failures must remain attributable to the module and operation that caused them.

Plugin operations, lifecycle hooks, event handlers, and owned background work should execute through the chassis failure boundary so an exception does not take down unrelated functionality.

A handler failure should produce an observable failure for that handler/operation.

Do **not** automatically add the module to the persistent disabled policy merely because one callback raised. Disabling a module is a separate module-management action.

The plugin can perform its own feature-specific cleanup after a failure when appropriate, while the chassis retains the authoritative operation/job outcome and diagnostics.

---

## 12. Sync/async behavior

Metaform modules can participate synchronously, asynchronously, or both.

Organize module code so the execution nature is obvious:

```python
def inspect(...):
    ...

async def refresh(...):
    ...
```

Avoid:

- `asyncio.run()` inside code already called by the chassis runtime;
- hidden long blocking calls inside async handlers;
- untracked `asyncio.create_task()` calls;
- module-private global event loops;
- claiming a cancelled worker has stopped before it actually has.

Long-lived work should have an owner visible to lifecycle management.

---

## 13. Context and provenance

Every operation that acts on Metaform state runs in a meaningful context.

Depending on the operation, that can include:

- project;
- module;
- operation;
- assignment/nonce;
- workflow/run/step;
- producing operation;
- selected knowledge/layer context.

Do not reconstruct these identities from:

- current working directory alone;
- PID alone;
- thread identity;
- event-loop identity;
- mutable module globals.

Use the context supplied by the chassis.

When a module produces a Metaform record/result, create it through the chassis data/provenance path so its producer and actual inputs remain inspectable.

A DAO must not strip this context from writes.

---

## 14. `help.py` — module guidance

For a small module, help can live directly beside the declaration it explains.

For a larger module, `help.py` can hold a longer module guide referenced by `PLUGIN.help`.

Useful module help covers:

- purpose;
- main operations;
- settings;
- examples;
- expected context;
- resource/dependency requirements;
- lifecycle behavior that users need to know.

Command-specific help belongs on the Click command. Setting-specific help belongs on the setting declaration.

Do not maintain a separate hidden help catalog that can drift from the live module declarations.

---

## 15. `resources/` — packaged module assets

A package plugin can include its own assets:

```text
resources/
├── templates/
├── schemas/
├── prompts/
└── fixtures/
```

Access them using package-aware resource APIs rather than assuming the current working directory is the plugin directory.

Resources must behave correctly when Metaform is:

- installed normally;
- run with `python -m metaform`;
- executed from the delivered/uploaded wheel in a supported environment.

Do not assume internet access or a source checkout is present.

---

## 16. Dependencies

A plugin is trusted in-process Python under the current Metaform model.

That means its imports share the host interpreter and dependency graph.

A plugin does not need to be standard-library-only, but its required dependencies must be compatible with the supported Metaform distribution and available in the delivered environment.

Do not let a plugin dynamically `pip install` packages into the running Metaform interpreter as part of ordinary activation.

If a feature genuinely requires an incompatible dependency environment or process isolation, implement that boundary deliberately through an external-process/adapter design rather than mutating the host interpreter's dependency state.

Module/package loading must preserve:

- stable package identity;
- relative imports;
- submodules;
- packaged assets;
- independent internal module names.

---

## 17. Optional internal files

A plugin may add files such as:

```text
adapters.py
service.py
parser.py
schema.py
state.py
client.py
render.py
```

when the feature requires them.

These names have no chassis-level meaning. They are ordinary internal organization.

A `manifest.py` or `metadata.py` is also acceptable when a complex feature wants an internal metadata object, but it is not a required external plugin manifest and does not replace the public `PLUGIN` declaration.

---

## 18. Recommended test shape

A substantial plugin should test the boundaries it actually participates in.

```text
tests/
├── test_plugin.py        # PLUGIN composition and declarations
├── test_operations.py    # feature behavior
├── test_commands.py      # CLI → operation adaptation
├── test_events.py        # subscriptions/publications
├── test_dao.py           # domain access through data service
├── test_settings.py      # declarations/effective behavior
├── test_lifecycle.py     # startup, partial failure, unload/reload
└── test_distribution.py  # packaged resources / wheel behavior when relevant
```

High-value behavioral checks include:

- load the module without chassis edits;
- verify declared settings/help appear dynamically;
- invoke the same feature through its operation and CLI adapter;
- interleave sync and async work without losing project/assignment context;
- unload and verify commands/subscriptions/resources disappear;
- reload and verify saved settings/data remain;
- inject failure during activation and verify partial contributions are released;
- cancel/stop owned asynchronous work and inspect its actual terminal state;
- verify DAO writes preserve project/provenance context;
- verify resources work outside the source checkout;
- exercise the module from the actual delivered wheel when the feature is part of portable execution.

Tests should prove observable behavior, not simply mirror implementation internals.

---

## 19. Complete responsibility map

| Concern | Plugin owns | Chassis owns |
| --- | --- | --- |
| Feature behavior | Domain operations | Invocation/runtime boundary |
| CLI | Complete contributed Click commands | Contextual root/composition/dispatch |
| Settings | Definitions/defaults/help | Persistence, glue, UI/CLI, resolution |
| Data access | Domain-specific DAOs | Database, transactions, ownership, revisions |
| Events | Subscriptions, handlers, publications | Bus, execution, attribution, lifecycle |
| Async work | Feature coroutine/worker behavior | Scheduling, job state, cancellation tracking |
| Lifecycle | Feature startup/teardown behavior | Activation/deactivation coordination |
| Provenance | Correct feature inputs/results | Producer/binding/revision persistence |
| Help | Module/command/setting guidance | Discovery and presentation |
| Resources | Feature-owned assets | Distribution/runtime support |
| Dependencies | Feature requirements | Supported distribution environment |
| Failure handling | Feature cleanup where needed | Isolation, attribution, diagnostics |

---

## 20. Design rule

A well-shaped Metaform plugin should be understandable as a small application without becoming a second chassis.

Its internal files should make feature ownership obvious:

```text
PLUGIN
  ├── settings declarations
  ├── operations
  │    └── DAOs → metaform.data
  ├── commands → operations
  ├── event handlers → operations/data
  ├── lifecycle-owned resources
  ├── domain models
  ├── help
  └── packaged resources
```

All of those parts participate through the shared Metaform contract.

The module remains removable. Its executable contributions disappear when unloaded; its saved settings, records, and provenance remain under chassis ownership for inspection and for the module's later return.
