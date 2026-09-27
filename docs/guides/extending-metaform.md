# Extending Metaform

[Documentation](../README.md) · [Module-system walkthrough](../examples/project-walkthrough.md) · [Implementation map](../inference-metaform/IMPLEMENTATION_MAP.md#extensions)

Metaform's community extension mechanism is implemented. A module contributes a capability through one declaration; the chassis supplies discovery, context, settings, invocation, storage access, events, lifecycle, help, and tool exposure. A new module can develop or use inferred understanding without recreating those facilities.

The project's own map records this as the module author's receiving purpose: add a capability once, in its own folder, with the required surfaces and lifecycle, without changing the chassis. This guide follows that purpose into the actual code.

## See the contract working first

In a registered project:

```sh
metaform enable helloworld
metaform helloworld greet world
metaform helloworld greet world --loud
metaform helloworld history
metaform helloworld wait 0
metaform
```

The first greeting prints `hello, world`; the second prints `HELLO, WORLD!`. Each publishes `helloworld.greeted`. The example's subscriber records the greeted name in the project's store, so `history` returns the names and the status hook can show the count.

The implementation is [helloworld/__init__.py](../../src/metaform/modules/helloworld/__init__.py). It demonstrates a synchronous verb, an asynchronous verb, declared settings, a data-backed select setting, an event subscriber, module-owned data, a status hook, a Windows-specific verb, and a destructive operation with the contract's existing confirmation behavior. `helloworld forget --confirm` deletes the example's greeting history; it is not needed to follow this guide.

The demonstration layer is `helloworld.greetings`, with holder element `code.module.helloworld`. In contrast, the original intake represents helloworld's contribution to the module-author purpose as the subtype `code.module.example`. Those are different records for different purposes.

## Start a module from the template

The [template](../../src/metaform/modules/template/__init__.py) contains an empty declaration. From the repository root, copy it into the user-module directory. The following shell commands use the normal home unless `METAFORM_HOME` is set:

```sh
mkdir -p "${METAFORM_HOME:-$HOME/.metaform}/modules"
cp -R src/metaform/modules/template "${METAFORM_HOME:-$HOME/.metaform}/modules/nodeview"
```

On other shells, make the equivalent folder copy into `<Metaform home>/modules/nodeview`. Replace the copy's `__init__.py` with this small read-only example:

```python
from __future__ import annotations

from metaform.data import Node
from metaform.module import Context, Module, Noun, Verb

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = True


def show(ctx: Context) -> object:
    """Read the prepared knowledge at the selected map node."""
    return ctx.require_store().node(Node.parse(ctx.nouns['node']))


MODULE = Module(
    id='nodeview',
    summary='Inspect knowledge at a map node.',
    purpose='Reads the selected knowledge at an element, join, or subtype. '
            'Use it when examining what is already known at a functional address. '
            'Details: metaform help nodeview.',
    verbs=(
        Verb(
            'show', show, 'Read a node and its participating layer items.',
            nouns=(Noun('node', 'An element:, join:, or subtype: reference.'),),
        ),
    ),
)
```

This example deliberately reuses the existing node read. It demonstrates how a new capability obtains the common context and store, not a replacement for the map module.

Enable and call it against the supplied project map:

```sh
metaform enable nodeview
metaform help nodeview
metaform nodeview show element:code.system.plugin
metaform nodeview show join:d14bd3498b614dfbaf0754c99b28dba3
```

Its MCP tool is `nodeview_show`, taking `node` and the usual context arguments such as `project`. A wheel-backed host uses the module contents in its wheel: rebuild and register the updated build to carry this module into that environment. A separately running server needs to discover the new module in its own environment; editing your source checkout does not rewrite an already built wheel.

## What a module declares

A module is a Python package folder containing `__init__.py`. The folder's identifier and `MODULE.id` match. The loader reads literal `SUPPORTED_OS`, optional `DEPENDENCIES`, and optional `SHIPS_DISABLED` metadata before importing module code. There is no required separate manifest file.

The declaration uses [Module, Verb, Noun, Subscription, and Status](../../src/metaform/module.py):

| Declaration | What the chassis takes from it |
|---|---|
| `Module.id`, `summary`, `purpose`, `details` | Identity, listings, help, and agent-facing purpose. Purpose must be nonempty. |
| `Module.verbs` | Callable operations exposed on their declared surfaces. |
| `Verb.name`, `run`, `summary` | Command/tool name, function, and explanation. |
| `Verb.nouns` | Required/optional inputs, types, multiplicity, and optional JSON schema. |
| `Verb.switches` | Declared settings that the operation reads as one-call overrides. |
| `Verb.surfaces`, `supported_os` | The interfaces and systems on which that operation is exposed. |
| `Verb.caution` | The existing one-call confirmation behavior for that operation. |
| `Module.subscriptions` | Event topics and handlers. |
| `Module.start`, `stop`, `status` | Lifecycle and status contributions. |
| `Module.default` | The verb invoked by the bare module command. |

Required nouns are positional on the CLI; optional nouns use `name=value`. Nouns can be text, integer, boolean, or JSON. Only the last noun may accept multiple values. Verb names use lowercase letters, digits, and hyphens.

The ordinary surfaces are `cli` and `mcp`; declarations may choose one. For example, the current `map approve` operation is CLI-only. The MCP transport's `serve` verb is a CLI transport entry rather than a tool an agent calls. This is why “declared once” does not mean every operation must be exposed identically everywhere.

## Receive the invocation's context

Each verb receives a `Context`. It carries the module ID, current folder, resolved project, selected store, nouns, switches, output sink, and surface. A project's settings do not have to be encoded into a global module singleton.

Use `ctx.require_store()` when the capability needs a project. It returns this call's store; when no project resolves, the existing context API reports the next registration/selection step. Use `ctx.setting(key)` to resolve a one-call switch before the stored/default setting.

Return the structured result an agent needs. Use `ctx.say(text)` for a person-facing message. The MCP surface represents messages and the returned result distinctly; a verb should not replace its structured result with an incidental progress sentence.

Start and stop hooks receive module/folder context, not an already resolved project store. Their lifetime is the module lifetime, not the duration of one selected project's task. Status hooks receive context for the status being requested and can contribute `Status(lines=(...), notice=...)`. A notice can orient an arriving agent; for example, intake supplies the notice to delegate an intake when the project has none.

Source: [context.py](../../src/metaform/context.py), [module.py](../../src/metaform/module.py), and [instructions.py](../../src/metaform/instructions.py).

## Declare settings rather than building a second settings system

The example module declares:

```python
settings.text('greeting', 'hello', help='The word helloworld greets with.')
settings.boolean('loud', False, help='Shout the greeting.')
settings.choice('favorite', choices=_favorite_choices,
                help="A name helloworld has greeted.")
```

`_favorite_choices(ctx)` reads names from the selected project's store. The chassis supplies its context when it needs the available options. The helper families are `text`, `number`, `boolean`, `items`, and `choice`.

Declared settings appear in help, `set`, `unset`, `config --show`, and the settings screen. A setting named with underscores is exposed through a hyphenated long switch. Boolean settings have positive and negative forms. A setting listed in a verb's switches can be overridden for one call:

```sh
metaform helloworld greet world --loud
metaform set --greeting welcome
metaform helloworld greet world
metaform unset --greeting
```

Names belong to their declaring module and share the schema; choose an appropriate distinct setting key rather than assuming every module has a private unqualified namespace. Folder settings inherit into descendants; global settings apply across folders. Module disablement withdraws active registration without deleting stored values.

The setting named `confirm` is not a persistent setting. It is the contract's one-call switch for an operation declaring a caution. Do not copy it into unrelated operations merely because the demo has a destructive verb.

## Use the graph and knowledge facilities directly

The `Store` façade exposes the existing data operations to a module: functional records, node reads, scoped context, layer construction, items, properties, references, corrections, challenges, plans, and history. A module does not need to call another module's CLI to access those facilities.

Helloworld's subscriber demonstrates a persistent contribution:

```python
with store.atomic():
    store.layer(
        'helloworld.greetings', 'helloworld', 'Who helloworld has greeted.',
        mutable=True, hideable=True,
        provenance={'module': 'helloworld', 'workflow': 'greet', 'role': 'module'},
    )
    store.add_element('helloworld.greetings', 'code.module.helloworld')
    store.add_item(
        'helloworld.greetings', Node('element', 'code.module.helloworld'),
        payload['name'],
    )
```

The example's history read directly addresses its layer. General knowledge intended for ordinary selected context also follows the layer's building/finished lifecycle; `store.finish(name)` makes that contribution ready. Use node-local items for local values and `add_property` for branch-scoped knowledge. The layer variable describes what its values answer; provenance and `sources` connect a producer's output to its actual origin and inputs.

Python `Store.add_join` and `Store.add_subtype` support the dedicated `ef` field. The current `map knowledge` CLI/MCP interface omits it. A module using the Python API receives the existing capability rather than inheriting that interface omission. [C01](../inference-metaform/IMPLEMENTATION_MAP.md#c01) identifies the source correspondence.

The memory module is one consumer of node-addressed storage. Other modules can contribute their own layers without converting every finding into mutable memory. Conversely, memory's lack of revision history does not imply that corrections or prompt versions lack their own histories.

Store API: [store.py](../../src/metaform/data/store.py). Reader semantics: [Working with Metaform](working-with-metaform.md#keep-a-body-of-knowledge-as-a-layer).

## Events and asynchronous work have distinct behavior

Modules communicate through event topics and payloads. Declare a `Subscription(topic, handler)` and publish with the context:

```python
# From a synchronous verb:
outcomes = ctx.publish('module.topic', {'value': 'example'})

# From an asynchronous verb:
outcomes = await ctx.publish_async('module.topic', {'value': 'example'})
```

Each subscriber receives a copied payload and its own context built for the publisher's folder and project. The subscriber does not inherit the publisher's noun or switch dictionaries. Outcomes are attributed to the receiving module as completed, failed, or cancelled. A handler exception is recorded without hiding the remaining deliveries.

**Delivery is sequential in the supplied implementation.** Synchronous publication waits for each handler. Async publication awaits each handler in turn; synchronous handlers run through a worker thread, and asynchronous handlers are awaited on the loop. This preserves event-loop availability, but it does not make the publisher independent of subscriber completion or turn the bus into concurrent fan-out.

**A write to the map is announced.** A module that writes to a project's map publishes `map.changed` after the write, and the web GUI's open pages redraw from it at once. The web module subscribes to the topic and hands each event to its running server, which pushes it to every open page over a server-sent events stream; with no server running, nothing happens. Nothing in Metaform polls for a change; a timer, a sleep in a loop or a repeated read waiting for something is a defect unless it is shown there is no other way.

```python
ctx.publish('map.changed', {'project': store.project_id, 'metaform_id': layer.metaform_id,
                            'layer': layer.name, 'kind': layer.kind, 'building': layer.ready is None})
```

helloworld's greeting does this: with the page open, each greeting appears in the 3D view as it is recorded.

Separate owned asynchronous work uses `ctx.spawn(coroutine)` inside an active event loop. The loader tracks the task as belonging to the module and cancels it during unload/reset/shutdown. That facility is distinct from publication. A one-shot asynchronous CLI verb owns a transient loop; its spawned work is cleaned up when the invocation ends, not converted into an independent daemon.

An async verb exposed through MCP runs on the server loop; a synchronous verb runs in a worker thread. Cancellation reaches the supported async execution path. The source contains lifecycle tests for cleanup and cancellation; this guide does not substitute a different scheduler.

Source: [events.py](../../src/metaform/events.py), [loader.py](../../src/metaform/loader.py), [MCP server](../../src/metaform/modules/mcp/server.py), [the web module's subscriber](../../src/metaform/modules/web/__init__.py), [helloworld](../../src/metaform/modules/helloworld/__init__.py), and [lifecycle tests](../../tests/test_lifecycle.py).

## Discovery, enablement, and lifecycle

The loader searches the system module directory, `<Metaform home>/modules`, and the `metaform.modules` entry-point group. Earlier discoveries retain a duplicate ID; a later conflicting candidate is reported rather than loaded a second time. Chassis command names are reserved.

`metaform list modules` identifies origin and load state. Unsupported platforms, absent declared dependencies, disabled modules, and import failures are distinguishable conditions. Enablement determines whether a module loads; the folder's `modules` selection determines whether a loaded module appears on that folder's command surface.

During loading, declared settings are associated with their owner and the start hook runs. Unload withdraws the module's active contributions, handles its owned tasks, calls stop, and removes its active settings registration. Stored data and setting values remain. The source exposes lifecycle/reset APIs; it does not ship a generic `metaform reload` command.

MCP tool lists are formed from the currently loaded declarations on each tools/list request. Agent instructions are assembled through the server/instruction lifecycle. Do not confuse a dynamic tool-list computation with automatic replacement of the code or instructions inside every running host.

## Packaging and distribution

An independently installed Python package can declare an entry point:

```toml
[project.entry-points."metaform.modules"]
nodeview = "nodeview"
```

Here the installed package `nodeview` contains the module declaration and metadata. Its ID follows the same rules as a discovered folder. The loader's entry-point support and the source tests establish this packaging route.

For a Metaform-built distribution:

```sh
metaform list modules
metaform build
```

The builder copies the chassis and **enabled, successfully loaded modules** into a wheel as system modules. It omits module test folders. It resolves declared dependencies with `uv`, vendors pure-Python dependencies, and leaves compiled dependencies as package requirements, reporting that distinction. It records the latest wheel under the Metaform home for the installer to register.

A direct self-running wheel and a wheel installed/launched through an environment have different dependency and home behavior. See [Getting started](getting-started.md#running-an-existing-build-instead). The direct-wheel home can later be imported into the normal home with the provided wheel-import operation.

## Building the next inference producer

The shared architecture already provides meaningful nodes, layer storage and selection, prompt records, settings, events, execution context, and CLI/MCP exposure. A module that performs lexicalization, derives Encounter-specific knowledge, or conducts blindspot exchanges can use those facilities. That does not mean those producers are already shipped, and their absence does not erase the implemented facilities they can use.

A module's contribution should remain intelligible through its receiving purpose: what new understanding or operation it supplies, who uses it, and how it becomes useful in subsequent work. The [technical reference](../inference-metaform/REFERENCE.md#extensibility) explains that relationship to advance inference amortization. The separate [Ideas](../inference-metaform/IDEAS.md) document contains proposals rather than extra requirements on module authors.
