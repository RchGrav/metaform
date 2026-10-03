"""The data access object every module imports, STORE-023: `from metaform.data import Store, Node, StoreError`.

A module declares its own tables with `Tables`, `Table`, `Column` and `Index`, and reads and writes them in the
`TableTx` that `Store.tables()` gives it, STORE-045.
"""
from ..errors import StoreError
from . import history, prompts
from .exchange import export_document, import_document
from .ids import as_object, new_id
from .names import reading, roots, short_name
from .operations import Data, Operation
from .paging import LIMIT, paged, sliced
from .records import (
                      COLUMNS,
                      CONDITIONS,
                      MESSAGES,
                      PLACE_KINDS,
                      ROLES,
                      SUBTYPE_ROLES,
                      TAKEN,
                      TICKETS,
                      Answer,
                      ChallengeState,
                      Citation,
                      ContextView,
                      Element,
                      GraphElement,
                      GraphJoin,
                      GraphPage,
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
                      Recording,
                      Ref,
                      Report,
                      RootElement,
                      RootEntry,
                      Roots,
                      Selection,
                      Step,
                      Subtype,
                      Ticket,
                      Version,
                      Where,
                      WorkLink,
                      WorkRecord,
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

__all__ = [
    'COLUMNS',
    'CONDITIONS',
    'LIMIT',
    'MESSAGES',
    'PLACE_KINDS',
    'ROLES',
    'SUBTYPE_ROLES',
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
    'GraphJoin',
    'GraphPage',
    'Index',
    'Item',
    'Join',
    'Layer',
    'LayerGroup',
    'LayerKind',
    'Message',
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
    'Property',
    'Provenance',
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
    'Subtype',
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
    'prompts',
    'reading',
    'roots',
    'short_name',
    'sliced',
]
