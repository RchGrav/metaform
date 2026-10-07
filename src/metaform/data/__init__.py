"""The data access object every module imports, STORE-023: `from metaform.data import Store, Node, StoreError`.

A module declares its own tables with `Tables`, `Table`, `Column` and `Index`, and reads and writes them in the
`TableTx` that `Store.tables()` gives it, STORE-045.
"""
from collections.abc import Mapping
from typing import Any

from ..errors import NewerStore, StoreError
from ..sqlite import SCHEMA_VERSION
from . import history, prompts
from .exchange import export_document, import_document
from .ids import as_object, new_id
from .names import reading, roots, short_name
from .operations import Data, Operation
from .paging import LIMIT, paged, sliced
from .projection import Projection
from .records import (
    COLUMNS,
    CONDITIONS,
    HELD_ROLES,
    MESSAGES,
    PLACE_KINDS,
    ROLES,
    TAKEN,
    TICKETS,
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
    Step,
    Ticket,
    Version,
    Where,
    WorkLink,
    WorkRecord,
    plain,
)
from .session import Tx as DataTx
from .session import sqlite3 as _sqlite3
from .store import Store
from .tables import Column, Index, Table, Tables, TableTx

DataRow = _sqlite3.Row
DataConnection = _sqlite3.Connection


def now() -> str:
    """The DAO's UTC timestamp, shared by native and module-owned records."""
    from .. import home
    return home.now()


def query_reads() -> tuple[str, ...]:
    """The chassis's named DAO reads, STORE-028."""
    from .. import query
    return tuple(query.READS)


def query_read(store: Store, name: str, arguments: Mapping[str, str]) -> Any:
    """Run a named DAO read with the chassis's conversion of text arguments, STORE-028."""
    from .. import query
    return query.call(store, name, arguments)

__all__ = [
    'COLUMNS',
    'CONDITIONS',
    'HELD_ROLES',
    'LIMIT',
    'MESSAGES',
    'PLACE_KINDS',
    'ROLES',
    'SCHEMA_VERSION',
    'TAKEN',
    'TICKETS',
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
    'export_document',
    'history',
    'import_document',
    'new_id',
    'now',
    'paged',
    'plain',
    'prompts',
    'query_read',
    'query_reads',
    'reading',
    'roots',
    'short_name',
    'sliced',
]
