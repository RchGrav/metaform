"""template: the empty start of every module, BASE-019.

Copy this folder, rename it, set MODULE.id to the folder's name, write the
module's purpose, and enable it with `metaform enable <id>`. Every field
hello declares is here, empty. CHANGELOG.md records each change to the
module contract, so a copy can follow it.

A module imports `metaform.nonce` to hand work to an agent by nonce, BASE-050.
`request(module, function, value=None)` issues a nonce, `read(nonce)` returns
its record, `update` changes the value or the function its next run is sent,
and `close` ends it and keeps its record, so its number is never issued
again. `reached()` is the nonce the running command came through, or None
when it did not come through one, and `current()` is that nonce, stopping
the command when there is none. `metaform <nonce>` runs the module's
function for it. hello's `noncedemo` shows it.

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
shows it.

Every prompt an agent reads is in `resources/prompts.xml`, an element named
for the prompt, never in Python, MCP-031. A module reads one with
`prompt_files.text(resources.files(__name__), name)`, or `prompt_files.required`
when a missing prompt is a defect. `instructions` is listed in the
instructions agents read; a copy writes its own name in place of `template`.
"""
from __future__ import annotations

from metaform.module import Module

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = True

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
    work_read=None,
)
