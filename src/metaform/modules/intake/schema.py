"""The input schema of `intake_submit`: the metaform's general data pattern, BASE-039.

The field names and nesting are the Canonical Intake's response schema. The
schema says what the pattern expects; the tool never refuses a submission for
its content, BASE-044. What does not fit is stored as given and named in a
notice by `submission.py`.
"""
from __future__ import annotations

from typing import Any

ROLES = ['AUE', 'VE', 'DE', 'SE', 'NE']
SUBTYPE_ROLES = ['DE', 'SE', 'NE']
FLAGS = ['missing', 'broken', 'cruft']

Schema = dict[str, Any]

FLAG: Schema = {'type': 'string', 'enum': FLAGS,
                'description': 'missing, broken or cruft; leave it out for a working object, MAP-046.'}
FLAG_NOTE: Schema = {'type': 'string', 'description': 'A short note on the finding.'}
REF: Schema = {'type': 'object', 'required': ['key', 'value'],
               'properties': {'key': {'type': 'string'}, 'value': {'type': 'string'}}}
REFS: Schema = {'type': 'array', 'items': REF}
SUBTYPE_ELEMENT: Schema = {'type': 'object', 'required': ['namespace_address', 'role'],
                           'properties': {'namespace_address': {'type': 'string'},
                                          'name_length': {'type': 'integer', 'minimum': 1},
                                          'role': {'type': 'string', 'enum': SUBTYPE_ROLES}, 'name': {'type': 'string'},
                                          'refs': REFS}}
SUBTYPE: Schema = {'type': 'object', 'required': ['provider', 'function', 'relation', 'observation', 'element'],
                   'properties': {'provider': {'type': 'string'}, 'function': {'type': 'string'},
                                  'relation': {'type': 'string'}, 'observation': {'type': 'string'},
                                  'flag': FLAG, 'flag_note': FLAG_NOTE, 'element': SUBTYPE_ELEMENT}}
JOIN: Schema = {'type': 'object', 'required': ['provider', 'purpose', 'function', 'relation', 'observation'],
                'properties': {'type': {'type': 'string', 'enum': ['purpose']}, 'provider': {'type': 'string'},
                               'purpose': {'type': 'string'}, 'function': {'type': 'string'},
                               'relation': {'type': 'string'}, 'observation': {'type': 'string'},
                               'non_goal': {'type': 'string'}, 'flag': FLAG, 'flag_note': FLAG_NOTE, 'refs': REFS,
                               'subtypes': {'type': 'array', 'items': SUBTYPE}}}
ELEMENT: Schema = {'type': 'object', 'required': ['namespace_address', 'role'],
                   'properties': {'namespace_address': {'type': 'string'}, 'flag': FLAG, 'flag_note': FLAG_NOTE,
                                  'name_length': {'type': 'integer', 'minimum': 1},
                                  'role': {'type': 'string', 'enum': ROLES}, 'name': {'type': 'string'},
                                  'refs': REFS, 'joins': {'type': 'array', 'items': JOIN}}}
ELEMENTS: Schema = {'type': 'array', 'items': ELEMENT}


def fields(schema: Schema) -> tuple[str, ...]:
    """The field names an object of this schema knows."""
    properties: dict[str, Any] = schema['properties']
    return tuple(properties)
