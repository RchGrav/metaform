"""template: the empty start of every module, BASE-019.

Copy this folder, rename it, set MODULE.id to the folder's name, write the
module's purpose, and enable it with `metaform enable <id>`. Every field
hello declares is here, empty. CHANGELOG.md records each change to the
module contract, so a copy can follow it.

A verb receives `ctx.identity`, a fresh dictionary of IDs supplied by the transport for this call. Paperclip's
HTTP gateway supplies `agent_id`, `issue_id` and `run_id`; absent headers leave it empty. `context(..., identity=...)`
copies the dictionary. These IDs do not change the process environment or grant authority. `ctx.session` keeps
what was shown apart per agent and run, including when MCP executes the verb as a background task.

A verb declares what it does with `effect=`: `read` changes nothing, `write`,
the default, adds or changes and keeps what was there, `remove` deletes or
replaces what cannot be had back; and `open_world=True` when it reaches past
the home and the map, to agents or the network. The MCP server gives them
to hosts as the tool's annotations, MCP-003. hello's verbs show each.

A verb that works in a folder with no project, such as one that reads a packaged
skill, declares `needs_project=False`: over MCP it is listed before the folder is
registered and takes no `project` argument. Every other verb is listed once the
folder has a project. A verb whose result follows the map's layers turned on, such
as a read of the map, declares `reads_layers=True`, so its tool takes the per-call
`layers` argument; no other tool has it.

A module that keeps data of its own declares its tables with `metaform.data`'s
`Tables`, `Table`, `Column` and `Index` and sets `tables=` below; a verb reads
and writes them in `with ctx.require_store().tables() as tx:`, STORE-045.
`place='metaform'` keeps a table beside the map, gone with the metaform;
`place='project'` keeps it in the project, kept by a clear. hello's `visit`,
`note` and `notes` show it.


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
absent owner. Map's storage shows legacy table adoption and upgrades.

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
when a missing prompt is a defect. A prompt sent to an agent is read with
`prompt_files.served(resources.files(__name__), name, **fills)`: the home's
prompt store keeps it as `<module>:<name>`, a version for each shipped text,
and an edit saved there, `agents override`, is sent in its place, STORE-044.
`instructions` is listed in the
instructions agents read; a copy writes its own name in place of `template`.
Its `rules` hold the module's rules, `<rule why="the reason">One sentence.</rule>`
each; the MCP server delivers the module's rules with the first use of its
commands, and a rule without a why stops the module loading.

Module.id and Module.summary publish the capability at metaform://modules.
Its MCP verbs appear automatically at metaform://<id>/tools, named
<id>_<verb>, with their argument schemas generated from Noun declarations.
There is no category registry or Verb.category. A new module needs no
MCP-server edit. Descriptions also feed fuzzy command search.

A verb that can take long declares `task=True`: an AI tool that declares the
MCP tasks extension is answered with a task it polls, BASE-030. hello's `wait`
shows it. A cancel stops an `async` verb at its next `await`; a verb run in a
thread finishes, and its task completes with its result. A verb returning
`{'run': <run id>}`, a workflow run record the server itself advances to its
end, declares `task='run'`: the run is the task until it ends. A task only for
work the server advances by itself: a verb whose result the calling agent must
act on, such as workflow's `assign`, declares neither.

A module serves read-only texts over MCP with `resources=`, `Resource`s of
`metaform.module`, each read through one of its verbs, MCP-037. A URI with
`{field}` parts is a template, read by calling the verb with the fields as
its nouns.

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
caller such as a phone bridge. A project service can provide `project.background`: a factory taking Context and returning
an owned object with close(), or None when disabled. The web supervisor starts one per registered project,
independently of browser subscriptions, and closes it on shutdown or policy refresh. The service uses ctx.listen
and the existing event bus, filters before reading, and releases every listener, watcher and lease in close().
"""
from __future__ import annotations

from metaform.module import AgentRoleDefinition, Module, Pane, Provides, ToolbarItem

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = True
REMOTE_AGENT = False  # the empty start of a module; a copy declares its own

# Add authored responsibilities as ordered prompt-store components. These names do not replace METAFORM_ROLE.
ROLE_DEFINITIONS: tuple[AgentRoleDefinition, ...] = ()

MODULE = Module(
    id='template',
    summary='The empty start of a module.',
    purpose='Replace this with two to four sentences: what the module is for, when an agent uses it, and '
            'where its details are. Details: metaform help template.',
    details='',
    verbs=(),
    subscriptions=(),  # Release upkeep can subscribe to install.completed; fork shows the handler and manual retry.
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
    settings_category=None,  # where its settings sit on the settings screens when one names none; None: advanced
    toolbar=(
        ToolbarItem('about', 'About template', 'Read what this module is for before turning it on.', icon='file',
                    pane='about', placement='extra'),
    ),
    panes=(
        Pane('about', 'About template', 'Read what this module is for before turning it on.', icon='file',
             resource='resources/pane.md', area='right'),
    ),
    provides=(Provides('agent.roles', ROLE_DEFINITIONS),),
)
