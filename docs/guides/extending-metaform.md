# Extending Metaform

[Documentation](../README.md) · [Module-system walkthrough](../examples/project-walkthrough.md) · [Implementation map](../inference-metaform/IMPLEMENTATION_MAP.md#extensions)

Metaform's community extension mechanism is implemented. A module contributes a capability through one declaration; the chassis supplies discovery, context, settings, invocation, storage access, events, lifecycle, help, and tool exposure. A new module can develop or use inferred understanding without recreating those facilities.

The project's own map records this as the module author's receiving purpose: add a capability once, in its own folder, with the required surfaces and lifecycle, without changing the chassis. This guide follows that purpose into the actual code.

## See the contract working first

In a registered project:

```sh
metaform enable hello
metaform hello greet world
metaform hello greet world --loud
metaform hello history
metaform hello wait 0
metaform
```

The first greeting prints `hello, world`; the second prints `HELLO, WORLD!`. Each publishes `hello.greeted`. The example's subscriber records the greeted name in the project's store, so `history` returns the names and the status hook can show the count.

The implementation is [hello/__init__.py](../../src/metaform/modules/hello/__init__.py). It demonstrates a synchronous verb, an asynchronous verb, declared settings, a data-backed select setting, an event subscriber, module-owned data, a status hook, a Windows-specific verb, and a destructive operation with the contract's existing confirmation behavior. `hello forget --confirm` deletes the example's greeting history; it is not needed to follow this guide.

The demonstration layer is `hello.greetings`, with holder element `code.module.hello`. In contrast, the earlier map of this repository, the September 26 export in [docs/examples](../examples/project-metaform.json), holds helloworld's contribution to the module author's purpose at `code.module.example`, in a subtype join. Those are different records for different purposes.

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
    purpose='Reads the selected knowledge at an element or a join. '
            'Use it when examining what is already known at a functional address. '
            'Details: metaform help nodeview.',
    verbs=(
        Verb(
            'show', show, 'Read a node and its participating layer items.',
            nouns=(Noun('node', 'An element: or join: reference.'),),
        ),
    ),
)
```

This example deliberately reuses the existing node read. It demonstrates how a new capability obtains the common context and store, not a replacement for the map module.

Enable and call it against the kitchen timer's map from [Getting started](getting-started.md#record-a-small-map-by-hand), with a join id that `metaform map joins code.timer.kitchen as=provider` prints:

```sh
metaform enable nodeview
metaform help nodeview
metaform nodeview show element:code.timer.kitchen
metaform nodeview show join:<join_id>
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
| `Module.node_read` | What the module adds to `map where` and `map node` of a node, under its id. |

Required nouns are positional on the CLI; optional nouns use `name=value`. Nouns can be text, integer, boolean, or JSON. Only the last noun may accept multiple values. Verb names use lowercase letters, digits, hyphens and underscores.

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
settings.text('greeting', 'hello', help='The word hello greets with.')
settings.boolean('loud', False, help='Shout the greeting.')
settings.choice('favorite', choices=_favorite_choices,
                help="A name hello has greeted.")
```

`_favorite_choices(ctx)` reads names from the selected project's store. The chassis supplies its context when it needs the available options. The helper families are `text`, `number`, `boolean`, `items`, and `choice`.

Declared settings appear in help, `set`, `unset`, `config --show`, and the settings screen. A setting named with underscores is exposed through a hyphenated long switch. Boolean settings have positive and negative forms. A setting listed in a verb's switches can be overridden for one call:

```sh
metaform hello greet world --loud
metaform set --greeting welcome
metaform hello greet world
metaform unset --greeting
```

Names belong to their declaring module and share the schema; choose an appropriate distinct setting key rather than assuming every module has a private unqualified namespace. Folder settings inherit into descendants; global settings apply across folders. Module disablement withdraws active registration without deleting stored values.

The setting named `confirm` is not a persistent setting. It is the contract's one-call switch for an operation declaring a caution. Do not copy it into unrelated operations merely because the demo has a destructive verb.

## Use the graph and knowledge facilities directly

The `Store` façade exposes the existing data operations to a module: functional records, node reads, scoped context, layer construction, items, properties, references, work records, refinements, challenges, plans, and history. A module does not need to call another module's CLI to access those facilities.

Hello's subscriber demonstrates a persistent contribution:

```python
with store.atomic():
    store.layer(
        'hello.greetings', 'hello', 'Who hello has greeted.',
        mutable=True, hideable=True,
        provenance={'module': 'hello', 'workflow': 'greet', 'role': 'module'},
    )
    store.add_element('hello.greetings', 'code.module.hello')
    store.add_item(
        'hello.greetings', Node('element', 'code.module.hello'),
        payload['name'],
    )
```

The example's history read directly addresses its layer. General knowledge intended for ordinary selected context also follows the layer's building/finished lifecycle; `store.finish(name)` makes that contribution ready. Use node-local items for local values and `add_property` for branch-scoped knowledge. The layer variable describes what its values answer; provenance and `sources` connect a producer's output to its actual origin and inputs.

A module that records functional structure writes the same records the intake does. An element is its address, `name_length` and role: `store.add_element(layer, address, name_length=2, role='SE')`. The project's name for a functionality goes on the join: `store.add_join(layer, receiver, provider, name=..., purpose=..., function=..., ef='Function', relation=..., verb=...)`. A subtype join sits inside a parent join and holds an ordinary element: `store.add_subtype(layer, join_id, address, ...)`. `store.where(address)` reads one address with what relies on it and what it relies on. An element never moves; `store.edit` and `store.correct` move a join with `receiver`, `provider` or `parent`. Nothing is refused for its content: what does not fit is stored as given and the result carries `notices`.

`Store.edit` and `Store.refine` change a join's `ef` and `verb`; the `map knowledge` interface's `op=edit` and `op=refine` read `ef` and do not read `verb`. [C01](../inference-metaform/IMPLEMENTATION_MAP.md#c01) identifies the source correspondence.

The condition of an object is not knowledge and not a field of the object: it is a work record, apart from the map, MAP-046. A module records an intended part that is not built as `missing`, a malfunction as `broken`, and material outside intake scope or code conflicting with a superseding specification as `exclude`. It writes `store.add_work(Node('element', address), condition, note='what and where', task='what it needs')`, using the condition that describes the finding. An exclusion note links the affected material and the scope reason or superseding specification for review. The module changes the record with `store.edit_work` and resolves it with `store.finish_work(id, resolution)`; `store.work(node=..., condition=..., open=True)` lists records, and every element and join read, a subtype join's included, carries `open_work`. The web GUI draws a node ghostly while a `missing` record is open and flashes it red while a `broken` one is. Hello's `todo` and `done` verbs show it.

The memory module is one consumer of node-addressed storage. Other modules can contribute their own layers without converting every finding into mutable memory. Conversely, memory's lack of revision history does not imply that refinements or prompt versions lack their own histories.

Store API: [store.py](../../src/metaform/data/store.py). Reader semantics: [Working with Metaform](working-with-metaform.md#keep-a-body-of-knowledge-as-a-layer).

## Keep data of the module's own in tables it declares

A module that needs data of its own, which is not knowledge about a node, declares its tables and reaches them through the same data access object, STORE-045. The chassis creates them, versions them with the module's version, upgrades them, and carries them through backup, export, import and clear. The module imports no `sqlite3` and writes no SQL.

```python
from metaform.data import Column, Index, Table, Tables

TABLES = Tables(version=1, tables=(
    Table('visits', place='metaform', key=('name',),
          columns=(Column('name', required=True), Column('times', 'int', required=True, default=0))),
    Table('notes', place='project', key=('note_id',),
          columns=(Column('note_id', required=True), Column('text', required=True), Column('at', required=True)),
          indexes=(Index(('at',)),)),
))

MODULE = Module(id='hello', ..., tables=TABLES)
```

`place='metaform'` keeps a table in the metaform's store, beside the map: use it when the feature does not work without that metaform. A clear of the project removes it with the metaform, and the clear's backup holds it. `place='project'` keeps a table in `projects/<project>/modules/<module>.sqlite3`, which a clear of the project's metaforms leaves in place; memory that must outlive a new intake belongs there. A column's kind is `text`, `int`, `real`, `bool` or `json`. Every table has a key.

A verb reads and writes inside one transaction:

```python
with ctx.require_store().tables() as tx:
    held = tx.get('visits', {'name': name})
    if held is None:
        tx.insert('visits', {'name': name, 'times': 1})
    else:
        tx.update('visits', {'name': name}, {'times': held['times'] + 1})

with ctx.require_store().tables(write=False) as tx:
    page = tx.rows('notes', by=('at',), limit=50)
```

The transaction is on the store of the first table it touches. A table of the other place needs a transaction of its own; inside `store.atomic()` a metaform-level table joins the map's transaction. `get` and `update` take the whole key. `rows` and `delete` take equal values for the leading columns of the key or of a declared index, and `rows` reads in that index's order and pages on it with `after`; `by` names the index to read through. A read that no index answers is refused with the indexes declared, so every read goes straight to its answer, STORE-005. Declare the index the read needs.

To change the tables, change the declaration and raise `version`. On the next transaction the chassis keeps a copy of the store under `backups/module-<id>-<version>/`, adds new tables, columns and indexes, keeps every row in the columns both versions share, runs `Tables(upgrade=...)` as `upgrade(tx, found)` once in each store that holds the tables, with `tx.place` naming it, and drops a table no longer declared. Tables changed at the same version are refused, and so is a store written by a later version. Hello's `visit`, `note` and `notes` show the capability.

## Add to the read of a node

An agent orients at a part with `map where <address>` and `map node <node>`. A module that keeps something about a node adds it to those reads with `node_read`, so the agent sees it without knowing the module's commands, BASE-035:

```python
def node_read(ctx: Context, node: Node) -> dict[str, int] | None:
    if ctx.store is None or node != Node('element', HOLDER):
        return None
    return {'greeted': len(_names(ctx.store))}

MODULE = Module(id='hello', ..., node_read=node_read)
```

The hook gets a context of its own module, with the call's project and toggled layers, and the node read: `Node('element', <address>)` from `where`, the node given to `node`. What it returns appears under the module's id, `hello: {greeted: 2}`; None adds nothing, and with nothing added the read is as it was. A field the read holds already is never replaced. A hook that raises adds `{"failed": "<ExceptionType>: <message>"}` under its id and the read goes on. The memory module adds a node's note and its memories this way, under `memory`, and leaves the memories out where the layer named memory does not reach. Hello's `node_read` shows the capability.

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

**Every change to the map is announced for you.** After any command that changes a project's map, on the command line or over MCP, the chassis fires `map.changed` on the event bus with the project and the metaform's id, no id meaning the project's metaforms changed. A module does nothing to announce its writes. Any module can subscribe:

```python
def changed(payload, ctx):
    ...  # payload: {'project': 'proj', 'metaform_id': '...'}

MODULE = Module(..., subscriptions=(Subscription('map.changed', changed),))
```

The web module subscribes and hands each event to its running server, which pushes it to every open page over a server-sent events stream, so the page redraws at once; with no server running, nothing happens. Work a module does outside a command, in a task it spawned, is announced only when the module publishes `map.changed` itself. The web GUI's server fires it the same way after each of the page's own writes that changed the map, so a subscriber hears a clear made on the page as it hears one from the command line. hello's greeting shows it: with the page open, each greeting appears in the 3D view as it is recorded, and hello has no code for it. Nothing in Metaform polls for a change; a timer, a sleep in a loop or a repeated read waiting for something is a defect unless it is shown there is no other way.

Separate owned asynchronous work uses `ctx.spawn(coroutine)` inside an active event loop. The loader tracks the task as belonging to the module and cancels it during unload/reset/shutdown. That facility is distinct from publication. A one-shot asynchronous CLI verb owns a transient loop; its spawned work is cleaned up when the invocation ends, not converted into an independent daemon.

An async verb exposed through MCP runs on the server loop; a synchronous verb runs in a worker thread. Cancellation reaches the supported async execution path. The source contains lifecycle tests for cleanup and cancellation; this guide does not substitute a different scheduler.

Source: [events.py](../../src/metaform/events.py), [loader.py](../../src/metaform/loader.py), [MCP server](../../src/metaform/modules/mcp/server.py), [the web module's subscriber](../../src/metaform/modules/web/__init__.py), [hello](../../src/metaform/modules/hello/__init__.py), and [lifecycle tests](../../tests/test_lifecycle.py).

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
