"""Storing one intake submission, never blocked, BASE-039 and BASE-044.

A submission is read once and stored whole in one atomic write as a new
intake layer. What does not fit the pattern is stored as given and named in
a notice with its path in the submission: a missing field is stored empty,
an unknown field is kept in the row's `extra`, a subtype's purpose and a
subtype provider that differs from its element are kept in the subtype's
`extra`, and the data access object notes what it stores as given, such as an
address out of form or a provider that names no element. Only a call whose
`elements` cannot be read at all stores nothing, and returns one notice.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, cast

from metaform.data import Join, Notice, Store

from .schema import ELEMENT, JOIN, ROLES, SUBTYPE, SUBTYPE_ELEMENT, fields

UNREADABLE = ('Nothing was stored. Do not retry: save your result as it stands with the feedback tool, putting it '
              'in the shape field with your report, so it can be reviewed and fixed.')
JOIN_TEXT = ('purpose', 'function', 'relation', 'observation')
SUBTYPE_TEXT = ('function', 'relation', 'observation')


def unreadable(why: str) -> dict[str, str]:
    """The one notice for a call whose elements cannot be read at all."""
    return {'where': 'elements', 'message': f'{why} {UNREADABLE}'}


@dataclass
class Counts:
    elements: int = 0
    joins: int = 0
    subtypes: int = 0
    refs: int = 0


@dataclass
class Writer:
    """Writes one submission into one intake layer and collects its notices with their paths."""
    store: Store
    layer: str
    notices: list[dict[str, str]] = field(default_factory=list[dict[str, str]])
    counts: Counts = field(default_factory=Counts)
    seen: set[str] = field(default_factory=set[str])

    def note(self, where: str, message: str) -> None:
        self.notices.append({'where': where, 'message': message})

    def noted(self, path: str, found: tuple[Notice, ...], names: Mapping[str, str]) -> None:
        """The data access object's notices, placed at their path in the submission."""
        for notice in found:
            self.note(names.get(notice.where, f'{path}.{notice.where}'), notice.message)

    def _object(self, value: Any, path: str, what: str) -> dict[str, Any] | None:
        if isinstance(value, dict):
            return {str(key): member for key, member in cast(dict[Any, Any], value).items()}
        self.note(path, f'This {what} is not an object; it was skipped.')
        return None

    def _list(self, value: Any, path: str, what: str) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return list(cast(list[Any], value))
        self.note(path, f'{what} is not an array; it was skipped.')
        return []

    def _unknown(self, given: dict[str, Any], known: tuple[str, ...], path: str, what: str) -> dict[str, Any]:
        extra = {key: value for key, value in given.items() if key not in known}
        if extra:
            self.note(path, f'{", ".join(sorted(extra))} {"is" if len(extra) == 1 else "are"} not a field of '
                            f'{what}; kept in its extra.')
        return extra

    def _text(self, given: dict[str, Any], name: str, path: str) -> Any:
        if name not in given:
            self.note(path, f'{name} is missing; stored empty.')
            return None
        return given[name]

    def _refs(self, value: Any, path: str) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        for index, ref in enumerate(self._list(value, f'{path}.refs', 'refs')):
            given = cast(dict[str, Any], ref) if isinstance(ref, dict) else {}
            key, text = given.get('key'), given.get('value')
            if isinstance(key, str) and isinstance(text, str):
                pairs.append((key, text))
            else:
                self.note(f'{path}.refs[{index}]', 'A ref is an object with a key and a value, both text; this one '
                                                   'was skipped.')
        return pairs

    def _address(self, value: Any, path: str) -> str:
        if value is None:
            self.note(path, 'namespace_address is missing; stored empty.')
            return ''
        if isinstance(value, str):
            return value
        self.note(f'{path}.namespace_address', 'namespace_address is not text; stored as its JSON text.')
        return json.dumps(value, ensure_ascii=False)

    def element(self, index: int, raw: Any) -> str | None:
        """Store one element; returns its address, or None when it could not be read as an element."""
        path = f'elements[{index}]'
        given = self._object(raw, path, 'element')
        if given is None:
            return None
        extra = self._unknown(given, fields(ELEMENT), path, 'an element')
        address = self._address(given.get('namespace_address'), path)
        role = given.get('role')
        if role is None:
            self.note(path, 'role is missing; the element was stored without a role.')
        elif role not in ROLES:
            self.note(f'{path}.role', f'{role!r} is not AUE, VE, DE, SE or NE; stored as given.')
        refs = self._refs(given.get('refs'), path)
        made = self.store.add_element(self.layer, address, name=given.get('name'),
                                      name_length=given.get('name_length'), role=role, refs=refs,
                                      extra=extra or None, flag=given.get('flag'), flag_note=given.get('flag_note'))
        self.noted(path, made.notices, {'address': f'{path}.namespace_address'})
        if address not in self.seen:
            self.seen.add(address)
            self.counts.elements += 1
        self.counts.refs += len(refs)
        return address

    def joins(self, index: int, raw: dict[str, Any], receiver: str) -> None:
        """Store the joins one element holds as their receiver."""
        path = f'elements[{index}]'
        for number, entry in enumerate(self._list(raw.get('joins'), f'{path}.joins', 'joins')):
            self.join(receiver, f'{path}.joins[{number}]', entry)

    def join(self, receiver: str, path: str, raw: Any) -> None:
        given = self._object(raw, path, 'join')
        if given is None:
            return
        extra = self._unknown(given, fields(JOIN), path, 'a join')
        texts = {name: self._text(given, name, path) for name in JOIN_TEXT}
        provider = given.get('provider')
        if provider is None:
            self.note(path, 'provider is missing; stored empty.')
            provider = ''
        refs = self._refs(given.get('refs'), path)
        made = self.store.add_join(self.layer, receiver, provider, **texts, non_goal=given.get('non_goal'),
                                   type=given.get('type', 'purpose'), refs=refs, extra=extra or None,
                                   flag=given.get('flag'), flag_note=given.get('flag_note'))
        self.noted(path, made.notices, {'provider': path, 'receiver': path})
        if not isinstance(made, Join):
            return
        self.counts.joins += 1
        self.counts.refs += len(refs)
        for number, entry in enumerate(self._list(given.get('subtypes'), f'{path}.subtypes', 'subtypes')):
            self.subtype(made.join_id, f'{path}.subtypes[{number}]', entry)

    def subtype(self, join_id: str, path: str, raw: Any) -> None:
        given = self._object(raw, path, 'subtype join')
        if given is None:
            return
        extra = self._unknown(given, (*fields(SUBTYPE), 'purpose'), path, 'a subtype join')
        if 'purpose' in given:
            extra['purpose'] = given['purpose']
            self.note(path, 'A subtype join has no purpose; its parent join carries it. The purpose was kept in the '
                            "subtype's extra.")
        inner = given.get('element')
        element: dict[str, Any] = {}
        if inner is None:
            self.note(path, 'element is missing; the subtype was stored at its provider.')
        elif isinstance(inner, dict):
            element = {str(key): member for key, member in cast(dict[Any, Any], inner).items()}
            extra.update(self._unknown(element, fields(SUBTYPE_ELEMENT), f'{path}.element', "a subtype's element"))
        else:
            self.note(f'{path}.element', 'element is not an object; the subtype was stored at its provider.')
        provider = given.get('provider')
        address_given = element.get('namespace_address', provider)
        address = self._address(address_given, f'{path}.element')
        if provider is not None and provider != address:
            extra['provider'] = provider
            self.note(path, f'provider {provider} differs from its element {address}; the subtype was stored at the '
                            "element's address with the provider kept in its extra.")
        texts = {name: self._text(given, name, path) for name in SUBTYPE_TEXT}
        refs = self._refs(element.get('refs'), f'{path}.element')
        made = self.store.add_subtype(self.layer, join_id, address, **texts, name=element.get('name'),
                                      name_length=element.get('name_length'), role=element.get('role'), refs=refs,
                                      extra=extra or None, flag=given.get('flag', element.get('flag')),
                                      flag_note=given.get('flag_note', element.get('flag_note')))
        self.noted(path, made.notices, {'address': f'{path}.element.namespace_address', 'role': f'{path}.element.role',
                                        'name_length': f'{path}.element.name_length', 'purpose': path})
        self.counts.subtypes += 1
        self.counts.refs += len(refs)
