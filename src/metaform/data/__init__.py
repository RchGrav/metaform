"""The data access object every module imports, STORE-023: `from metaform.data import Store, Node, StoreError`.

A module declares its own tables with `Tables`, `Table`, `Column` and `Index`, and reads and writes them in the
`TableTx` that `Store.tables()` gives it, STORE-045.
"""
import sqlite3 as _sqlite3
from collections.abc import Mapping
from typing import Any

from ..errors import NewerStore, StoreError
from ..sqlite import SCHEMA_VERSION
from . import history, prompts
from .exchange import export_document, import_document
from .functional import functional_context
from .ids import as_object, new_id
from .names import reading, roots, short_name
from .numbers import parse as parse_reference
from .numbers import reference
from .numbers import shown as shown_number
from .operations import Data, Operation
from .paging import LIMIT, paged, row_cursor, sliced
from .projection import Projection
from .records import (
    COLUMNS,
    CONDITIONS,
    FAULTS,
    HELD_ROLES,
    KINDS,
    MESSAGES,
    PLACE_KINDS,
    ROLES,
    STAGES,
    Answer,
    ChallengeState,
    Citation,
    ContextView,
    Element,
    GraphElement,
    GraphPage,
    Held,
    Item,
    Join,
    Layer,
    LayerGroup,
    LayerKind,
    Message,
    Node,
    NodeKind,
    NodeView,
    Notice,
    Op,
    Outcome,
    Page,
    PastWork,
    Plan,
    Property,
    Provenance,
    Record,
    Recording,
    Ref,
    Report,
    RootElement,
    RootEntry,
    Roots,
    Selection,
    SourceRef,
    Step,
    Ticket,
    Version,
    Where,
    WorkLink,
    WorkRecord,
    is_work,
    plain,
    shown_open,
)
from .refs import RESERVED as RESERVED_REF_NAMES
from .session import BASE_VARIABLE, on_base
from .session import Tx as DataTx
from .store import Store
from .tables import (
    Column,
    Index,
    Table,
    Tables,
    TableTx,
    delete_work_rows,
    export_work_rows,
    insert_work_rows,
    project_work_rows,
    restore_project_work_rows,
)
from .versions import NOTES_LAYER, NOTES_MODULE, NOTES_VARIABLE

DataRow = _sqlite3.Row
DataConnection = _sqlite3.Connection


def now() -> str:
    """The DAO's UTC timestamp, shared by native and module-owned records."""
    from .. import home
    return home.now()


def author(surface: str | None = None) -> str | None:
    """Who a change to the base is made by, LAYER-025: the ticket and the session a runner names, else the surface the
    call came through, such as cli or mcp."""
    import os
    work, session = os.environ.get('METAFORM_WORK'), os.environ.get('METAFORM_SESSION')
    named = ' '.join(part for part in (f'work {work}' if work else '', f'session {session}' if session else '') if part)
    return named or surface


def query_reads() -> tuple[str, ...]:
    """The chassis's named DAO reads, STORE-028."""
    from .. import query
    return tuple(query.READS)


def query_read(store: Store, name: str, arguments: Mapping[str, str]) -> Any:
    """Run a named DAO read with the chassis's conversion of text arguments, STORE-028."""
    from .. import query
    return query.call(store, name, arguments)


def private_database(path: Any) -> DataConnection:
    """A SQLite file a module keeps for itself outside every project, such as the Metaform Node's accounts and tokens
    in the home: autocommit with the chassis's busy timeout, write-ahead logging, usable from any thread (the module
    serializes its writes), and readable by its owner alone. Its tables are the module's; nothing in it is part of a
    map or travels with a project, STORE-023."""
    from pathlib import Path

    from .. import home
    from ..sqlite import BUSY_SECONDS, private
    file = Path(path)
    if home.is_home_path(file):
        home.mkdir_private(file.parent)
    else:
        file.parent.mkdir(parents=True, exist_ok=True)
    private(file)  # before write-ahead logging is on, so its log and shared memory are the owner's alone too
    db = _sqlite3.connect(str(file), isolation_level=None, timeout=BUSY_SECONDS, check_same_thread=False)
    db.execute(f'PRAGMA busy_timeout={BUSY_SECONDS * 1000}')
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA foreign_keys=ON')
    try:
        file.chmod(0o600)
    except OSError:
        pass
    return db

__all__ = [
    'BASE_VARIABLE',
    'COLUMNS',
    'CONDITIONS',
    'FAULTS',
    'HELD_ROLES',
    'KINDS',
    'LIMIT',
    'MESSAGES',
    'NOTES_LAYER',
    'NOTES_MODULE',
    'NOTES_VARIABLE',
    'PLACE_KINDS',
    'RESERVED_REF_NAMES',
    'ROLES',
    'SCHEMA_VERSION',
    'STAGES',
    'Answer',
    'ChallengeState',
    'Citation',
    'Column',
    'ContextView',
    'Data',
    'DataConnection',
    'DataRow',
    'DataTx',
    'Element',
    'GraphElement',
    'GraphPage',
    'Held',
    'Index',
    'Item',
    'Join',
    'Layer',
    'LayerGroup',
    'LayerKind',
    'Message',
    'NewerStore',
    'Node',
    'NodeKind',
    'NodeView',
    'Notice',
    'Op',
    'Operation',
    'Outcome',
    'Page',
    'PastWork',
    'Plan',
    'Projection',
    'Property',
    'Provenance',
    'Record',
    'Recording',
    'Ref',
    'Report',
    'RootElement',
    'RootEntry',
    'Roots',
    'Selection',
    'SourceRef',
    'Step',
    'Store',
    'StoreError',
    'Table',
    'TableTx',
    'Tables',
    'Ticket',
    'Version',
    'Where',
    'WorkLink',
    'WorkRecord',
    'as_object',
    'author',
    'delete_work_rows',
    'export_document',
    'export_work_rows',
    'functional_context',
    'history',
    'import_document',
    'insert_work_rows',
    'is_work',
    'new_id',
    'now',
    'on_base',
    'paged',
    'parse_reference',
    'plain',
    'private_database',
    'project_work_rows',
    'prompts',
    'query_read',
    'query_reads',
    'reading',
    'reference',
    'restore_project_work_rows',
    'roots',
    'row_cursor',
    'short_name',
    'shown_number',
    'shown_open',
    'sliced',
]
