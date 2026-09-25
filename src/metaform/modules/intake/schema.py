"""The input schema of `intake_submit` and the checks that refuse only what cannot be stored, BASE-039.

The field names and nesting are the Canonical Intake's response schema. The
checks never judge content: they refuse input that does not match the
schema, an address not in the form of MAP-010, a join provider that names no
element, and a subtype whose provider is not its own element's address. Every
problem is listed with its path, so one resubmission can fix them all.
"""
from __future__ import annotations

import re
from typing import Any

ADDRESS = re.compile(r'^[a-z0-9_]+(\.[a-z0-9_]+)*$')
ROLES = ['AUE', 'VE', 'DE', 'SE', 'NE']
SUBTYPE_ROLES = ['DE', 'SE', 'NE']

REF = {'type': 'object', 'additionalProperties': False, 'required': ['key', 'value'],
       'properties': {'key': {'type': 'string'}, 'value': {'type': 'string'}}}
REFS = {'type': 'array', 'items': REF}
SUBTYPE_ELEMENT = {'type': 'object', 'additionalProperties': False, 'required': ['namespace_address', 'role'],
                   'properties': {'namespace_address': {'type': 'string'}, 'name_length': {'type': 'integer', 'minimum': 1},
                                  'role': {'type': 'string', 'enum': SUBTYPE_ROLES}, 'name': {'type': 'string'},
                                  'refs': REFS}}
SUBTYPE = {'type': 'object', 'additionalProperties': False,
           'required': ['provider', 'function', 'relation', 'observation', 'element'],
           'properties': {'provider': {'type': 'string'}, 'function': {'type': 'string'},
                          'relation': {'type': 'string'}, 'observation': {'type': 'string'},
                          'element': SUBTYPE_ELEMENT}}
JOIN = {'type': 'object', 'additionalProperties': False,
        'required': ['provider', 'purpose', 'function', 'relation', 'observation'],
        'properties': {'type': {'type': 'string', 'enum': ['purpose']}, 'provider': {'type': 'string'},
                       'purpose': {'type': 'string'}, 'function': {'type': 'string'}, 'relation': {'type': 'string'},
                       'observation': {'type': 'string'}, 'non_goal': {'type': 'string'}, 'refs': REFS,
                       'subtypes': {'type': 'array', 'items': SUBTYPE}}}
ELEMENT = {'type': 'object', 'additionalProperties': False, 'required': ['namespace_address', 'role'],
           'properties': {'namespace_address': {'type': 'string'}, 'name_length': {'type': 'integer', 'minimum': 1},
                          'role': {'type': 'string', 'enum': ROLES}, 'name': {'type': 'string'}, 'refs': REFS,
                          'joins': {'type': 'array', 'items': JOIN}}}
ELEMENTS = {'type': 'array', 'items': ELEMENT}
SUBMISSION = {'$schema': 'https://json-schema.org/draft/2020-12/schema', 'type': 'object',
              'additionalProperties': False, 'required': ['elements'],
              'properties': {'id': {'type': 'string'}, 'elements': ELEMENTS}}

TYPES = {'object': dict, 'array': list, 'string': str, 'integer': int}


def conform(value: Any, schema: dict[str, Any], path: str, problems: list[str]) -> None:
    """Every place the value departs from the schema, each with its path."""
    expected = schema.get('type')
    if expected is not None:
        python = TYPES[expected]
        if not isinstance(value, python) or (expected == 'integer' and isinstance(value, bool)):
            problems.append(f'{path}: must be {"an" if expected[0] in "aeiou" else "a"} {expected}')
            return
    if 'enum' in schema and value not in schema['enum']:
        problems.append(f'{path}: must be one of {", ".join(schema["enum"])}')
    if 'minimum' in schema and value < schema['minimum']:
        problems.append(f'{path}: must be at least {schema["minimum"]}')
    if expected == 'object':
        for name in schema.get('required', []):
            if name not in value:
                problems.append(f'{path}: {name} is required')
        known = schema.get('properties', {})
        for name, member in value.items():
            if name not in known:
                if schema.get('additionalProperties') is False:
                    problems.append(f'{path}.{name}: is not a field here')
                continue
            conform(member, known[name], f'{path}.{name}', problems)
    if expected == 'array':
        for index, member in enumerate(value):
            conform(member, schema['items'], f'{path}[{index}]', problems)


def check(elements: Any, known_addresses: set[str]) -> list[str]:
    """Every problem of a submission; an empty list means it can be stored."""
    problems: list[str] = []
    conform(elements, ELEMENTS, 'elements', problems)
    if not isinstance(elements, list):
        return problems
    rows = [element for element in elements if isinstance(element, dict)]
    submitted = {element.get('namespace_address') for element in rows}
    for index, element in enumerate(elements):
        if not isinstance(element, dict):
            continue
        path = f'elements[{index}]'
        address = element.get('namespace_address')
        if isinstance(address, str) and not ADDRESS.fullmatch(address):
            problems.append(f'{path}.namespace_address: {address!r} is not an address (dotted lowercase segments)')
        for position, join in enumerate(element.get('joins') or []):
            if not isinstance(join, dict):
                continue
            where = f'{path}.joins[{position}]'
            provider = join.get('provider')
            if isinstance(provider, str):
                if provider not in submitted and provider not in known_addresses:
                    problems.append(f'{where}.provider: {provider} names no element in the submission or the project')
                if provider == address:
                    problems.append(f'{where}.provider: a join runs to a different element than its receiver')
            for number, subtype in enumerate(join.get('subtypes') or []):
                if not isinstance(subtype, dict) or not isinstance(subtype.get('element'), dict):
                    continue
                spot = f'{where}.subtypes[{number}]'
                inner = subtype['element'].get('namespace_address')
                if not isinstance(inner, str):
                    continue
                if subtype.get('provider') != inner:
                    problems.append(f'{spot}.provider: {subtype.get("provider")} differs from its element {inner}')
                if not ADDRESS.fullmatch(inner):
                    problems.append(f'{spot}.element.namespace_address: {inner!r} is not an address')
                if inner in submitted:
                    problems.append(f'{spot}.element.namespace_address: {inner} is also a root element')
    return problems
