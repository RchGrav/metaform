"""The fields of the intake tools, one object per call: the Canonical Intake's response schema, BASE-039.

Each schema says what the field expects; the tools never refuse a value for its
content, BASE-044. What does not fit is stored as given and named in a notice.
"""
from __future__ import annotations

from typing import Any

from metaform.data import PERSPECTIVES
from metaform.data import ROLES as ROLE_NAMES
from metaform.data import SUBTYPE_ROLES as SUBTYPE_ROLE_NAMES

Schema = dict[str, Any]

EF: Schema = {'type': 'string', 'enum': list(PERSPECTIVES)}
ROLE: Schema = {'type': 'string', 'enum': list(ROLE_NAMES)}
SUBTYPE_ROLE: Schema = {'type': 'string', 'enum': list(SUBTYPE_ROLE_NAMES)}
NAME_LENGTH: Schema = {'type': 'integer', 'minimum': 1}
REF: Schema = {'type': 'object', 'required': ['key', 'value'],
               'properties': {'key': {'type': 'string'}, 'value': {'type': 'string'}}}
REFS: Schema = {'type': 'array', 'items': REF}
EXTRA: Schema = {'type': 'object'}
