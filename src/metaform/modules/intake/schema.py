"""The fields of the intake tools, one object per call: the Canonical Intake's response schema, BASE-039.

Each schema says what the field expects; the tools never refuse a value for its
content, BASE-044. What does not fit is stored as given and named in a notice.
"""
from __future__ import annotations

from typing import Any

from metaform.data import EF_WORDS
from metaform.data import FLAGS as FLAG_NAMES
from metaform.data import ROLES as ROLE_NAMES
from metaform.data import SUBTYPE_ROLES as SUBTYPE_ROLE_NAMES

Schema = dict[str, Any]

FLAG: Schema = {'type': 'string', 'enum': list(FLAG_NAMES),
                'description': 'missing, broken or cruft; leave it out for a working object, MAP-046.'}
EF: Schema = {'type': 'string', 'enum': list(EF_WORDS),
              'description': 'Function if it is the encounter of a functionality, Encounter if it is the functionality '
                             'of the encounter.'}
ROLE: Schema = {'type': 'string', 'enum': list(ROLE_NAMES)}
SUBTYPE_ROLE: Schema = {'type': 'string', 'enum': list(SUBTYPE_ROLE_NAMES)}
NAME_LENGTH: Schema = {'type': 'integer', 'minimum': 1}
REF: Schema = {'type': 'object', 'required': ['key', 'value'],
               'properties': {'key': {'type': 'string'}, 'value': {'type': 'string'}}}
REFS: Schema = {'type': 'array', 'items': REF}
EXTRA: Schema = {'type': 'object'}
