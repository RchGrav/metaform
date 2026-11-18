"""A project's bases in the project store: the maps it keeps of itself, one of them active (MAP-045, STORE-041).

Each base is a whole project database. The active one is the project's own, `<home>/maps/<project>.lbug`, which every
command and the page read; the others are set aside, unopened, as `<home>/maps/bases/<project>/<base>.lbug`. Their
names, when each was made and last made active, and which is active are kept in `<home>/maps/bases/<project>/bases.json`.
A project with no such record has one base, `main`. A switch moves files, so it runs in the service, with the project's
database closed (`Owner.released`), and one base operation runs at a time.

What goes with a base and what goes with the project is the old store's (STORE-041, STORE-020): the map and every
overlay's records stay with the base they were written in, as the old store's layers and tickets did; the memory layer
is the project's, kept in the memory module's project-level tables there, so it moves into whichever base is made
active.
"""
from __future__ import annotations

import copy as copy_module
import json
import os
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from metaform import home as metaform_home
from metaform.project import store
from metaform.project.overlays import definitions
from metaform.project.owner import Owner
from metaform.project.store import Store

FIRST = 'main'  # the base a project held in the store has before any other is made, as the old store names its first
_SERIAL = threading.Lock()  # one base operation at a time in the service: each reads and writes the record and files

Memory = tuple[list[tuple[str, str | None, list[str]]], list[tuple[str, str, str]]]


class Refused(Exception):
    """A base operation that cannot be done, with what to do instead."""

    def __init__(self, code: str, message: str, remediation: str) -> None:
        super().__init__(message)
        self.code, self.message, self.remediation = code, message, remediation


def folder(home: Path, project: str) -> Path:
    return home / 'maps' / 'bases' / project


def _now() -> str:
    return datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def _record(home: Path, project: str) -> dict[str, Any]:
    path = folder(home, project) / 'bases.json'
    if not path.exists():
        return {'active': FIRST, 'bases': [{'name': FIRST, 'created': None, 'activated': None, 'elements': None,
                                            'held': None}]}
    return cast(dict[str, Any], json.loads(path.read_text(encoding='utf-8')))


def _save(home: Path, project: str, record: dict[str, Any]) -> None:
    """The record written whole, by a replace, so a reader never sees half of it."""
    where = folder(home, project)
    where.mkdir(parents=True, exist_ok=True)
    partial = where / 'bases.json.partial'
    partial.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding='utf-8')
    os.replace(partial, where / 'bases.json')


def _files(path: Path) -> list[Path]:
    """A database and the files the engine keeps beside it, as `store.remove` finds them."""
    return [path, *sorted(path.parent.glob(path.name + '.*'))] if path.exists() else []


def _move(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    for found in _files(source):
        found.rename(target.with_name(target.name + found.name[len(source.name):]))


def _aside(home: Path, project: str, name: str) -> Path:
    return folder(home, project) / f'{name}.lbug'


def _counts(opened: Store) -> tuple[int, dict[str, int]]:
    """What a base holds: its elements with fields of their own, and the records of each overlay. Read inside a
    reading transaction the caller holds."""
    elements = sum(1 for _, fields in opened.all_elements() if any(value is not None for value in fields.values()))
    held = {key: opened.held(key)[0] for key in opened.overlay_keys()}
    return elements, {key: count for key, count in held.items() if count}


def _put_memory(opened: Store, memory: Memory) -> None:
    """The project's memory layer put in place of what the base holds of it."""
    entities, relations = memory
    with opened.transaction():
        present = [name for name, _, _ in opened.memory_entities()]
        if present:
            opened.delete_memory_entities(present)
        for name, kind, observations in entities:
            opened.put_memory_entity(name, kind, observations)
        for start, end, relation_type in relations:
            opened.add_memory_relation(start, end, relation_type)


def _copy_map(source: Store, target: Store) -> None:
    """The base map, as it is now, written into a new database: the root's fields, every element, every want, and the
    definition of each overlay with its table, but none of its records (`collapse`)."""
    with source.reading():
        root, elements, wants = source.root(), source.all_elements(), source.all_wants()
        parts, keys = source.parts(), set(source.overlay_keys())
    with target.transaction():
        target.put_root(root)
        for address, fields in elements:
            target.put_element(address, fields)
        for holder, want in wants:
            target.add_want(holder, str(want['element']), want)
        for address, fields in parts.items():
            target.put_part(address, fields)
        made = set(target.overlay_keys())
        for key, definition in definitions(parts).items():
            if key in keys and key not in made:
                target.create_overlay(key, {name: spec.column for name, spec in definition.fields.items()
                                            if name != 'ref'})


def _named(record: dict[str, Any], name: str) -> dict[str, Any] | None:
    return next((base for base in cast(list[dict[str, Any]], record['bases']) if base['name'] == name), None)


def _free(record: dict[str, Any], name: str) -> str:
    """The name asked for, or with `-2` or the next free number added when the project has a base of that name."""
    chosen, number = name, 1
    while _named(record, chosen) is not None:
        number += 1
        chosen = f'{name}-{number}'
    return chosen


def _checked_name(name: str, verb: str) -> None:
    if not metaform_home.NAME.fullmatch(name) or metaform_home.ID.fullmatch(name):
        raise Refused('BASE_NAME', f'{name!r} is not a base name: use letters, digits, ., _ and -.',
                      f'metaform map {verb} <name>')


def _switch(home: Path, project: str, owned: Owner, record: dict[str, Any], source: Path | None,
            incoming: Callable[[Path, Memory], None], settle: Callable[[], None]) -> dict[str, Any]:
    """Set the active base aside and put another in its place, with the project's memory carried into it: the base
    set aside at `source`, or, with none, a new database `incoming` makes; `incoming` is given the path and the memory.
    Done with the project's database closed; anything that fails puts every file back where it was, and `settle`, which
    writes the record of the bases, runs last inside that guard, so a record that cannot be written also puts every
    file back and the files and the record never disagree. Answers what the base set aside holds."""
    left = cast(dict[str, Any], _named(record, record['active']))
    with owned.released(project) as path:
        with Store(path) as opened, opened.reading():
            memory: Memory = (opened.memory_entities(), opened.memory_relations())
            elements, held = _counts(opened)
        kept = _aside(home, project, left['name'])
        _move(path, kept)
        try:
            if source is not None:
                _move(source, path)
            incoming(path, memory)
            left.update(elements=elements, held=held)  # on the record before settle writes it
            settle()
        except BaseException:
            if source is not None:
                _move(path, source)
            else:
                store.remove(path)
            _move(kept, path)
            raise
    return {'name': left['name'], 'elements': elements, 'held': held}


def _announce(owned: Owner, project: str) -> None:
    """A switch replaces the whole map the page and every agent read: told as a change of the map, as a commit is."""
    if owned.committed is not None:
        owned.committed(project, {'map'})


def _listed(owned: Owner, project: str, record: dict[str, Any]) -> list[dict[str, Any]]:
    """Each base as the list shows it. The active one is counted now; one set aside is never opened, since nothing
    changes it there, and shows what it held when it was set aside."""
    found: list[dict[str, Any]] = []
    for base in cast(list[dict[str, Any]], record['bases']):
        active = base['name'] == record['active']
        elements = owned.read(project, lambda opened: _counts(opened)[0]) if active else base.get('elements')
        found.append({'name': base['name'], 'created': base.get('created'), 'active': active,
                      'activated': base.get('activated'), 'mapped': bool(elements)})
    return found


def perform(asked: dict[str, Any], owned: Owner) -> dict[str, object]:
    """Answer one base operation in the service: `op` is list, add, activate, collapse or remove, with `name` for all
    but list. A refusal answers as the tool's refusals do."""
    project, op, name = str(asked.get('project') or ''), str(asked.get('op') or 'list'), str(asked.get('name') or '')
    home = owned.home
    try:
        if not store.location(home, project).exists():
            raise Refused('PROJECT_NOT_FOUND', f'the project store holds no map of {project}.',
                          'metaform map bases --project <a project held in the store>')
        with _SERIAL:
            record = _record(home, project)
            if op == 'list':
                return {'status': 'ok', 'active': record['active'], 'bases': _listed(owned, project, record)}
            if op not in ('add', 'collapse', 'activate', 'remove'):
                raise Refused('BASE_OPERATION', f'{op} is not a base operation: list, add, activate, collapse or '
                              'remove.', 'metaform help map bases')
            answer = _changed(home, project, owned, record, op, name)  # writes the record itself, inside its guard
        if answer.get('left') is not None:  # a switch happened: a removal, or activating the active base, changes no map
            _announce(owned, project)
        return {'status': 'ok', **answer}
    except Refused as refusal:
        return {'status': 'error', 'code': refusal.code, 'message': refusal.message,
                'remediation': refusal.remediation}


def _changed(home: Path, project: str, owned: Owner, record: dict[str, Any], op: str,
             name: str) -> dict[str, Any]:
    """Do one changing base operation on the record and the files; the caller saves the record."""
    if op in ('add', 'collapse'):
        _checked_name(name, 'add-base' if op == 'add' else 'collapse')
        chosen = _free(record, name)

        def made(path: Path, memory: Memory) -> None:
            with Store(path, create=project) as fresh:
                if op == 'collapse':
                    with Store(_aside(home, project, cast(str, record['active']))) as old:
                        _copy_map(old, fresh)
                _put_memory(fresh, memory)
        def settle() -> None:
            stamp = _now()
            _saved(home, project, record, lambda new: (new['bases'].append(
                {'name': chosen, 'created': stamp, 'activated': stamp, 'elements': None, 'held': None}),
                new.update(active=chosen)))
        left = _switch(home, project, owned, record, None, made, settle)
        return {'base': chosen, 'asked': name, 'left': left}
    found = _named(record, name)
    if found is None:
        raise Refused('BASE_NOT_FOUND', f'{project} has no base {name}.', 'metaform map bases')
    if op == 'activate':
        if name == record['active']:
            return {'base': name, 'asked': name, 'left': None}

        def kept(path: Path, memory: Memory) -> None:
            with Store(path) as opened:
                _put_memory(opened, memory)
        def settle() -> None:
            def change(new: dict[str, Any]) -> None:
                cast(dict[str, Any], _named(new, name)).update(activated=_now(), elements=None, held=None)
                new['active'] = name
            _saved(home, project, record, change)
        left = _switch(home, project, owned, record, _aside(home, project, name), kept, settle)
        return {'base': name, 'asked': name, 'left': left}
    if name == record['active']:  # remove
        raise Refused('BASE_ACTIVE', f'{name} is the active base of {project}; it is not removed while it is active.',
                      f'metaform map activate <another base of {project}> --confirm')
    stamp = _now().replace(':', '').replace('-', '')
    copy = home / 'backups' / 'remove-base' / project / stamp / f'{name}.lbug'
    moved = bool(_files(_aside(home, project, name)))
    if moved:
        _move(_aside(home, project, name), copy)
    try:  # a record that cannot be written puts the base back where it was
        _saved(home, project, record, lambda new: new.update(
            bases=[base for base in cast(list[dict[str, Any]], new['bases']) if base['name'] != name]))
    except BaseException:
        if moved:
            _move(copy, _aside(home, project, name))
        raise
    return {'base': name, 'kept': str(copy), 'held': found.get('held') or {}, 'elements': found.get('elements')}


def _saved(home: Path, project: str, record: dict[str, Any], change: Callable[[dict[str, Any]], object]) -> None:
    """Write the record of the bases as `change` leaves it, and only once it is written take that state in memory too,
    so a failed write leaves both the file and `record` as they were."""
    new = copy_module.deepcopy(record)
    change(new)
    _save(home, project, new)
    record.clear()
    record.update(new)
