"""The fields of the intake tools, one object per call: the metaform's shape, BASE-039 and D115.

Each schema says what the field expects; the tools never refuse a value for its
content, BASE-044. What does not fit is stored as given and named in a notice.
"""
from __future__ import annotations

from typing import Any

from metaform.data import ROLES as ROLE_NAMES

Schema = dict[str, Any]

ROLE: Schema = {'type': 'string', 'enum': list(ROLE_NAMES)}
NAME_LENGTH: Schema = {'type': 'integer', 'minimum': 1}
REF: Schema = {'type': 'object', 'required': ['key', 'value'],
               'properties': {'key': {'type': 'string'}, 'value': {'type': 'string'}}}
REFS: Schema = {'type': 'array', 'items': REF}
ELEMENTS: Schema = {'type': 'array', 'items': {'type': 'string'}}
IFD: Schema = {'type': 'string', 'enum': ['sends', 'receives', 'both']}  # Information Flow Direction; the store also reads send and receive
