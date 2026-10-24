"""template: the empty start of every module, BASE-019.

Copy this folder, rename it, set MODULE.id to the folder's name, write the
module's purpose, and enable it with `metaform enable <id>`. Every field
hello declares is here, empty. CHANGELOG.md records each change to the
module contract, so a copy can follow it.

A verb declares what it does with `effect=`: `read` changes nothing, `write`,
the default, adds or changes and keeps what was there, `remove` deletes or
replaces what cannot be had back; and `open_world=True` when it reaches past
the home and the map, to agents or the network. The MCP server gives them
to hosts as the tool's annotations, MCP-003. hello's verbs show each.

A module that keeps data of its own declares its tables with `metaform.data`'s
`Tables`, `Table`, `Column` and `Index` and sets `tables=` below; a verb reads
and writes them in `with ctx.require_store().tables() as tx:`, STORE-045.
`place='metaform'` keeps a table beside the map, gone with the metaform;
`place='project'` keeps it in the project, kept by a clear. hello's `visit`,
`note` and `notes` show it.

Read selected children with `tx.rows_in(table, column, values, where=..., by=...)`.
The column and equal `where` columns must begin a declared index. It returns
a tuple in index order, reads repeated values once, batches SQLite bindings,
and issues no SQL for an empty selection. Use it to read only records the
current view needs.


A module owns composite DAO operations with `data=Data(operations={...})`,
importing `Data`, `DataTx` and `Operation` from `metaform.data`. Its handler
receives the current transaction, and `Operation(handler, write=True)` joins
`Store.atomic()`. `tx.tables()` reaches its metaform tables in that same
transaction. Hello's `count_visit` operation backs `visit`. `Data.decorate`
adds to native records; `Data.item_write` contributes to item writes.
For reads needed while the module is disabled, declare a literal
`DATA_SOURCE = 'storage.py'`. That standalone file exports `DATA` and `TABLES`
and marks those reads `Operation(handler, retained=True)`; it imports only
public APIs and its own helpers, without importing this runtime initializer.
`Table.from_sql(name, schema, on_remove=...)` adopts an existing SQL table
with its rows, constraints and indexes. Recorded removal rules survive an
absent owner. `tx.cleanup(kind, identity)` applies those rules atomically when
a module removes its own record. Map's storage shows ticket cleanup and upgrades.

A module adds to the read of a node, `map where` and `map node`, with
`node_read=`: a function of the context and the node read, which returns plain
data, shown under the module's id, or None for nothing, BASE-035. hello's
`node_read` shows it. A module keeps its own fields on a work record in a table
of its own keyed by the work id, STORE-045, and shows them in `map work id=<id>`
with `work_read=`: a function of the context and the work record, which returns
plain data under the module's id, or None for nothing. hello's `work_read`
shows it. A module says how much it holds at a node, never what, with
`node_count=`: a function of the context and a tuple of element addresses,
which returns a `Count` of `metaform.module`, the word for one and for several,
at each address how many, how many the last session there wrote and how many
this session wrote, and the line from its `counts` prompt saying how to read
them, MCP-039. An agent orienting on a node is told them once per session, the
node's and its direct neighbours'. memory's `node_count` shows it.

A module numbers each item it writes at an address with `store.number(address)`,
one counter per address that never reuses a number, keeps the number with the
item, and refuses a write without its short title, or its why when it records
knowledge or a decision, with `metaform.module.titled`, MCP-037. It reads one
item back with `item_read=`: a function of the context, an address and a
number, which returns plain data, `kind`, `title`, `why`, `body` and `links`,
or None, served at `metaform://<address>#<n>`. memory's `item_read` shows it.
It lists them with `items_at=`: a function of the context, an address, a number
or None and a limit, which returns those numbered below the number, newest
first, at most the limit, each `number`, `kind`, `title` and `why`, in one read.
`item_kinds=` names the kinds it numbers, so a list of other kinds skips it.
`metaform.module.node_items` merges every module's into one list for the brief
of a node; a module without it is read number by number. memory's shows it.

Every prompt an agent reads is in `resources/prompts.xml`, an element named
for the prompt, never in Python, MCP-031. A module reads one with
`prompt_files.text(resources.files(__name__), name)`, or `prompt_files.required`
when a missing prompt is a defect. `instructions` is listed in the
instructions agents read; a copy writes its own name in place of `template`.
Its `rules` hold the module's rules, `<rule why="the reason">One sentence.</rule>`
each; the MCP server requires receipt of applicable rules through instruction
reads before executing a command, and a rule without a why stops the module loading.

Module.id and Module.summary publish the capability at metaform://modules.
Its MCP verbs appear automatically at metaform://<id>/tools, named
<id>_<verb>, with their argument schemas generated from Noun declarations.
There is no category registry or Verb.category. A new module needs no
MCP-server edit. Descriptions also feed fuzzy command search.

MCP requires each tool's current instructions before execution. Ordinary
verb guides are generated from declarations and served at
metaform://tools/<tool>/instructions[/<op>], also available through
metaform_instructions tool=<tool> op=<op>. An unread guide returns
instructions_required with executed=false and its read URI. Catalog and
instruction retrieval remain available. Keep tool usage in declarations and
named prompts instead of repeating it in role duties or startup catalogs.

Additional tool-owned instructions use
Provides('agent.tool.instructions', tool_instructions), whose callable is
(ctx: Context, tool: str, op: str | None) -> Sequence[dict[str, Any]]. Return
exact named/versioned components for applicable tools and operations, or an
empty sequence. prompt_files.resolve preserves selected/actual versions,
bindings, source and rendered fingerprints. A component can name an explicit
source with read={'uri': ...}. The canonical guide combines these components
with ordinary verb guidance. The template registers no placeholder provider.

Instruction readers queue exact components with ctx.queue_context(components,
epoch), using the epoch from prepare_agent_context. Complete bodies surviving
response shaping receive receipts; preparing or listing establishes none.
Changed effective content must be delivered before the next operation.
Unchanged content is reused. Receipts establish delivery, not comprehension.

A verb that can take long declares `task=True`: an AI tool that declares the
MCP tasks extension is answered with a task it polls, BASE-030. hello's `wait`
shows it. A cancel stops an `async` verb at its next `await`; a verb run in a
thread finishes, and its task completes with its result. A verb returning
`{'run': <run id>}`, a workflow run record the server itself advances to its
end, declares `task='run'`: the run is the task until it ends. A task only for
work the server advances by itself: a verb whose result the calling agent must
act on, such as workflow's `assign`, declares neither.

A module adds tools to the web GUI's toolbar with `toolbar=`, `ToolbarItem`s,
and panes to its workspace with `panes=`, `Pane`s, both of `metaform.module`.
A tool runs one of the module's verbs with fixed arguments, shows a pane,
runs a command of the page, or opens a link; a pane shows a read verb's
result, a view the page draws, or a `.md`, `.txt` or `.html` file under
`resources/`. Each has an id, a title, a one-line description saying why a
person uses it, its tooltip, and an icon, a name from `ICONS` or an SVG
under `resources/`. They are defaults: the person arranges the toolbar and
the panes and saves workspaces on the page. The tool and the pane below show
`resources/pane.md`; a copy writes its own.

A module offers something to other modules, without either importing the other, with `provides=`: `Provides(kind,
value)` of `metaform.module`, found by kind with `metaform.module.provided(folder, kind)`, every enabled module's in
module id order. A disabled module provides nothing. The voice module finds speech engines this way, each a
`VoiceEngine(name, summary, sends=, transcribe=, speak=, ready=, formats=)` provided as `voice.engine`; the
elevenlabs module provides one. The voice module provides `voice`, its own speak and transcribe for a server-side
caller such as a phone bridge.

A module can supply observational context updates with
`Provides('agent.context.changes', provider)`. The provider implements
`pending(ctx, session) -> list[dict]` and `delivered(ctx, session, notices)`.
`session` is the runner's context/receipt identity. Return compact JSON-ready
references only for relevant revisions already consumed by that context, keeping
stable component and withdrawal identities. Preparing notices acknowledges
nothing. Dispatch appends them to an already-scheduled turn and calls `delivered`
only after transport acceptance. Acknowledge the exact revisions received, so a
newer concurrent change stays pending. This capability does not wake a model,
broadcast bodies or replace the existing event bus. A module records changes from
its mutating operations and filters unrelated and own writes before reads.
Any module-owned wording belongs in its resources/prompts.xml.
"""
from __future__ import annotations

from metaform.module import Module, Pane, ToolbarItem

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = True
REMOTE_AGENT = False  # the empty start of a module; a copy declares its own

# Domain expertise uses definition.uri under metaform://specialist/; specialist=False uses metaform://role/.
# Tasks stay in assignments; prompt-store source names and full instruction bodies stay with their owner.

MODULE = Module(
    id='template',
    summary='The empty start of a module.',
    purpose='Replace this with two to four sentences: what the module is for, when an agent uses it, and '
            'where its details are. Details: metaform help template.',
    details='',
    verbs=(),
    subscriptions=(),
    start=None,
    stop=None,
    status=None,
    tables=None,
    data=None,
    node_read=None,
    node_count=None,
    work_read=None,
    item_read=None,
    items_at=None,
    item_kinds=(),
    toolbar=(
        ToolbarItem('about', 'About template', 'Read what this module is for before turning it on.', icon='file',
                    pane='about', placement='extra'),
    ),
    panes=(
        Pane('about', 'About template', 'Read what this module is for before turning it on.', icon='file',
             resource='resources/pane.md', area='right'),
    ),
)
