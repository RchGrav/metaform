"""Export and import: a project carried whole, by unique id, STORE-027.

The document is JSON. Every row carries its identity id and layer id, never the
store's `row` integers. Import adds only what the target does not hold: a
metaform whose id exists is not created again, a layer whose id exists is
skipped whole, and a thing whose identity id exists is not added again. Each
metaform's store is imported in one transaction, STORE-006.
"""
from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Iterable, Sequence
from contextlib import ExitStack
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from .. import home
from ..errors import StoreError
from ..sqlite import SCHEMA_VERSION
from . import versions
from .ids import as_list, as_object, prefixes
from .schema import STORE_SCHEMA
from .session import open_store

FORMAT = 1
THINGS = ('elements', 'joins', 'items', 'properties')  # a subtype join is a row of joins, STORE-011
KIND_OF_TABLE = {'elements': 'element', 'joins': 'join', 'items': 'item', 'properties': 'property'}
ID_OF_TABLE = {table: versions.KINDS[kind].id_column for table, kind in KIND_OF_TABLE.items()}


def _rows(db: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in db.execute(sql, tuple(params)).fetchall()]


def _without_row(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: value for key, value in row.items() if key != 'row'} for row in rows]


def export_document(project_ids: Sequence[str] | None = None, *, metaform: str | None = None,
                    layers: Sequence[str] = ()) -> dict[str, Any]:
    """The exchange document for the named projects, or every project when none or `all` is named."""
    if not project_ids or list(project_ids) == ['all']:
        chosen = list(home.projects())
    else:
        chosen: list[home.Project] = []
        for project_id in project_ids:
            record = home.project(project_id)
            if record is None:
                raise StoreError(f'No project {project_id} is registered.', 'metaform list projects')
            chosen.append(record)
    exported: list[dict[str, Any]] = []
    for record in chosen:
        metaforms = [item for item in home.metaforms(record.project_id) if metaform is None or item.name == metaform]
        if metaform is not None and not metaforms:
            raise StoreError(f'No metaform {metaform} in {record.project_id}.', 'metaform list metaforms')
        active = home.active_metaform(record.project_id)
        exported.append({
            'project': record.to_dict(),
            'metaforms': [_export_metaform(record.project_id, item, layers) for item in metaforms],
            'active_metaform': active.metaform_id if active else None,
        })
    return {'metaform_export': FORMAT, 'schema_version': SCHEMA_VERSION, 'projects': exported}


def _export_metaform(project_id: str, metaform: home.Metaform, layer_names: Sequence[str]) -> dict[str, Any]:
    document: dict[str, Any] = {'metaform': {'metaform_id': metaform.metaform_id, 'name': metaform.name,
                                             'created': metaform.created}}
    for name in ('types', 'layers', 'layer_fields', 'layer_tags', 'layer_sources', 'provenance', 'selections',
                 'hidden', *THINGS, 'refs', 'challenge_states', 'plans', 'work', 'requires'):
        document[name] = []
    with open_store(home.store_path(project_id, metaform.metaform_id), write=False) as db:
        db.execute('BEGIN')
        _fill(db, document, layer_names)
        db.execute('COMMIT')
    return document


def _fill(db: sqlite3.Connection, document: dict[str, Any], layer_names: Sequence[str]) -> None:
    all_layers = _rows(db, 'SELECT * FROM layers ORDER BY rowid')
    if layer_names:
        by_name = {layer['name']: layer['layer_id'] for layer in all_layers}
        missing = [name for name in layer_names if name not in by_name]
        if missing:
            raise StoreError(f'No layer {missing[0]}.', 'metaform map layers')
        chosen = {by_name[name] for name in layer_names}
    else:
        chosen = {layer['layer_id'] for layer in all_layers}
    document['layers'] = [layer for layer in all_layers if layer['layer_id'] in chosen]
    for table in ('layer_fields', 'layer_tags', 'provenance', 'selections'):
        document[table] = [row for row in _rows(db, f'SELECT * FROM {table} ORDER BY rowid')
                           if row['layer_id'] in chosen]
    document['layer_sources'] = [row for row in _rows(db, 'SELECT * FROM layer_sources ORDER BY rowid')
                                 if row['layer_id'] in chosen and row['source_layer_id'] in chosen]
    document['hidden'] = [row[0] for row in db.execute('SELECT layer_id FROM hidden_layers ORDER BY rowid')
                          if row[0] in chosen]
    # A ref names its owner by the thing, its layer and which of the thing's versions in that layer it is, since the
    # metaform keeps every version of a thing in its own layer, LAYER-025.
    owner_ids: dict[tuple[str, int], tuple[str, str, int]] = {}
    for table in THINGS:
        rows: list[dict[str, Any]] = []
        for layer_id in [layer['layer_id'] for layer in document['layers']]:
            rows += _rows(db, f'SELECT * FROM {table} WHERE layer_id=?', (layer_id,))
        rows.sort(key=lambda row: row['row'])
        seen: dict[tuple[str, str], int] = {}
        for row in rows:
            version = seen.get((row[ID_OF_TABLE[table]], row['layer_id']), 0)
            seen[(row[ID_OF_TABLE[table]], row['layer_id'])] = version + 1
            owner_ids[(KIND_OF_TABLE[table], row['row'])] = (row[ID_OF_TABLE[table]], row['layer_id'], version)
        document[table] = _without_row(rows)
    refs: list[tuple[int, dict[str, Any]]] = []
    for (owner, owner_row), (owner_id, owner_layer, version) in sorted(owner_ids.items(),
                                                                      key=lambda pair: pair[0][1]):
        for ref in _rows(db, 'SELECT ref_id, position, key, value FROM refs WHERE owner=? AND owner_row=? '
                             'ORDER BY position', (owner, owner_row)):
            refs.append((ref['ref_id'], {'owner': owner, 'owner_id': owner_id, 'owner_layer_id': owner_layer,
                                         'owner_version': version, 'position': ref['position'], 'key': ref['key'],
                                         'value': ref['value']}))
    refs.sort(key=lambda pair: pair[0])
    document['refs'] = [ref for _, ref in refs]
    item_ids = {row['item_id'] for row in document['items']}
    document['challenge_states'] = [row for row in _rows(db, 'SELECT * FROM challenge_states ORDER BY rowid')
                                    if row['item_id'] in item_ids]
    document['plans'] = [row for row in _rows(db, 'SELECT * FROM plans ORDER BY rowid') if row['layer_id'] in chosen]
    document['work'] = _without_row(_rows(db, 'SELECT * FROM work ORDER BY row'))
    addresses = {row['address'] for table in ('elements', 'selections') for row in document[table]}
    needed = {prefix for address in addresses for prefix in prefixes(address)}
    document['types'] = [row for row in _rows(db, 'SELECT address, parent FROM types ORDER BY rowid')
                         if not layer_names or row['address'] in needed]
    document['requires'] = _requires(document)


def _requires(document: dict[str, Any]) -> list[dict[str, str]]:
    """Identity ids the exported rows point at that no exported row adds."""
    added = {row[ID_OF_TABLE[table]] for table in THINGS for row in document[table] if row['op'] == 'add'}
    wanted: list[tuple[str, str]] = []
    for table in THINGS:
        kind = KIND_OF_TABLE[table]
        for row in document[table]:
            if row['op'] != 'add' and kind != 'property':
                wanted.append((kind, row[ID_OF_TABLE[table]]))
            if table == 'joins':
                wanted += [('element', end) for end in (row['receiver'], row['provider']) if end is not None]
                if row['parent'] is not None:
                    wanted.append(('join', row['parent']))
            if table == 'items':
                wanted.append((row['target_kind'], row['target_id']))
                if row['link_kind']:
                    wanted.append((row['link_kind'], row['link_id']))
            if table == 'properties':
                wanted.append(('element', row['element_id']))
    found: list[dict[str, str]] = []
    for kind, ident in wanted:
        entry = {'kind': kind, 'id': ident}
        if ident not in added and entry not in found:
            found.append(entry)
    return found


ROW_TABLES = ('types', 'layers', 'layer_fields', 'layer_tags', 'layer_sources', 'provenance', 'selections',
              *THINGS, 'challenge_states', 'plans', 'work')
PROJECT_KEYS = ('project_id', 'path', 'target_type', 'target_value')
HEAD_KEYS = ('metaform_id', 'name', 'created')
REF_KEYS = ('owner', 'owner_id', 'owner_layer_id', 'owner_version', 'position', 'key', 'value')


@cache
def columns(table: str) -> tuple[str, ...]:
    """The columns a document row of this table carries: the store's own, without `row`, STORE-027."""
    db = sqlite3.connect(':memory:')
    try:
        db.executescript(STORE_SCHEMA)
        found = tuple(str(row[1]) for row in db.execute(f'PRAGMA table_info({table})') if row[1] != 'row')
    finally:
        db.close()
    return found


def _scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float)) and not isinstance(value, bool)


def _record(value: Any, path: str, keys: Sequence[str], problems: list[str]) -> None:
    """One object of the document: exactly these keys, each holding text, a number or null."""
    fields = as_object(value)
    if fields is None:
        problems.append(f'{path}: not an object')
        return
    problems += [f'{path}.{key}: not a field here' for key in fields if key not in keys]
    problems += [f'{path}.{key}: missing' for key in keys if key not in fields]
    problems += [f'{path}.{key}: not text, a number or null' for key in keys if key in fields
                 and not _scalar(fields[key])]


def _strings(value: Any, path: str, problems: list[str]) -> None:
    members = as_list(value)
    if members is None or not all(isinstance(item, str) for item in members):
        problems.append(f'{path}: not a list of ids')


def _validate(document: Any) -> None:
    """Check the whole document before anything is written; every problem is named with its path, H8."""
    whole = as_object(document)
    if whole is None or whole.get('metaform_export') != FORMAT:
        raise StoreError('This is not a Metaform export document.', 'metaform export > <file>')
    if str(whole.get('schema_version')) != SCHEMA_VERSION:
        raise StoreError(f'The document has schema version {whole.get("schema_version")}; this Metaform '
                         f'supports version {SCHEMA_VERSION}.', 'install the Metaform release that wrote it')
    problems: list[str] = []
    entries = as_list(whole.get('projects'))
    if entries is None:
        problems.append('projects: not a list')
        entries = []
    for number, given in enumerate(entries):
        path = f'projects[{number}]'
        entry = as_object(given)
        if entry is None:
            problems.append(f'{path}: not an object')
            continue
        _record(entry.get('project'), f'{path}.project', PROJECT_KEYS, problems)
        if not _scalar(entry.get('active_metaform')):
            problems.append(f'{path}.active_metaform: not an id or null')
        metaforms = as_list(entry.get('metaforms'))
        if metaforms is None:
            problems.append(f'{path}.metaforms: not a list')
            continue
        for index, held in enumerate(metaforms):
            where = f'{path}.metaforms[{index}]'
            metaform = as_object(held)
            if metaform is None:
                problems.append(f'{where}: not an object')
                continue
            _record(metaform.get('metaform'), f'{where}.metaform', HEAD_KEYS, problems)
            for table in ROW_TABLES:
                rows = as_list(metaform.get(table, []))
                if rows is None:
                    problems.append(f'{where}.{table}: not a list')
                    continue
                for place, row in enumerate(rows):
                    _record(row, f'{where}.{table}[{place}]', columns(table), problems)
            refs = as_list(metaform.get('refs', []))
            if refs is None:
                problems.append(f'{where}.refs: not a list')
            for place, ref in enumerate(refs or []):
                _record(ref, f'{where}.refs[{place}]', REF_KEYS, problems)
            _strings(metaform.get('hidden', []), f'{where}.hidden', problems)
            requires = as_list(metaform.get('requires', []))
            if requires is None:
                problems.append(f'{where}.requires: not a list')
            for place, need in enumerate(requires or []):
                wanted = as_object(need)
                keys = ('kind', 'address') if wanted is not None and wanted.get('kind') == 'type' else ('kind', 'id')
                _record(need, f'{where}.requires[{place}]', keys, problems)
    if problems:
        raise StoreError('The document does not fit an export document:\n' +
                         '\n'.join(f'  {problem}' for problem in problems),
                         'metaform export > <file>, from the home that holds the project')


@dataclass
class Planned:
    """One metaform of the document, with the project it goes to and whether that project is registered here."""
    project_id: str
    record: home.Project
    registered: bool
    metaform: dict[str, Any]
    activate: bool
    never_active: bool = False


def _pulled(metaform: dict[str, Any], project_id: str, label: str, taken: set[str]) -> dict[str, Any]:
    """A wheel's metaform as it arrives in the main home: an id made from the wheel and its own, so pulling the same
    folder again finds it, and its name followed by `-from-<wheel>`, numbered when taken, BASE-025."""
    head = metaform['metaform']
    derived = hashlib.sha256(f'{label}/{head["metaform_id"]}'.encode()).hexdigest()[:32]
    folder = home.project_folder(project_id)
    wanted = f'{head["name"]}-from-{label}'
    if folder is None:
        name, number = wanted, 1
        while name in taken:
            number += 1
            name = f'{wanted}-{number}'
    else:
        with home.project_db(folder) as db:
            name = home.free_name(db, project_id, wanted, taken)
    taken.add(name)
    return {**metaform, 'metaform': {**head, 'metaform_id': derived, 'name': name}}


def _plan(document: dict[str, Any], project: str | None, notices: list[dict[str, str]],
          pulled: str | None = None) -> tuple[list[Planned], int]:
    """Where each metaform goes, decided before anything is written, and how many are skipped.

    A metaform another project owns here is not created again, STORE-027: nothing of it is written, and a notice
    names the project that owns it, BASE-044.
    """
    planned: list[Planned] = []
    skipped = 0
    names: dict[str, set[str]] = {}
    for entry in document.get('projects', []):
        record = home.Project(**entry['project'])
        if project is not None:
            target = home.project(project)
            if target is None:
                raise StoreError(f'No project {project} is registered.', 'metaform list projects')
            project_id, registered = target.project_id, True
        else:
            project_id = record.project_id
            registered = home.project(project_id) is not None
            if not registered:
                holder = home.project_at(record.path)
                if holder is not None:
                    raise StoreError(f'{record.path} is already registered as project {holder}.',
                                     f'metaform import <file> {holder}')
        for metaform in entry.get('metaforms', []):
            if pulled is not None:
                metaform = _pulled(metaform, project_id, pulled, names.setdefault(project_id, set()))
            metaform_id = metaform['metaform']['metaform_id']
            owner = home.metaform_owner(metaform_id)
            if owner is not None and owner != project_id:
                skipped += 1
                notices.append({'where': f'metaforms.{metaform_id}', 'message': (
                    f'Metaform {metaform_id} belongs to project {owner} here; nothing of it was written. To add '
                    f'what it holds to that project: metaform import <file> {owner}')})
                continue
            planned.append(Planned(project_id, record, registered, metaform,
                                   pulled is None and not registered and entry.get('active_metaform') == metaform_id,
                                   never_active=pulled is not None))
    return planned, skipped


def import_document(document: dict[str, Any], project: str | None = None, *,
                    pulled: str | None = None) -> dict[str, Any]:
    """Add what the target does not hold, by unique id, as one unit, STORE-027 and STORE-006.

    The document is checked whole and every metaform's place decided before anything is written. A project the
    home does not hold is registered first, in a folder of its own, PROJ-026. Each store's rows are written in an
    open transaction; each project's metaform rows are then written and committed, and only then each store. When
    anything fails, every store transaction rolls back, every store file this import created is removed, and a
    project it registered is taken off the list again. Returns what was added and skipped, and a notice for each identity the document needs
    that this home does not hold, BASE-044.
    """
    _validate(document)
    notices: list[dict[str, str]] = []
    planned, skipped = _plan(document, project, notices, pulled)
    report: dict[str, Any] = {'metaforms_added': 0, 'metaforms_skipped': skipped, 'layers_added': 0,
                              'layers_skipped': 0, 'things_added': 0, 'things_skipped': 0, 'notices': notices}
    opened: list[sqlite3.Connection] = []
    created: list[Path] = []
    registered: list[str] = []
    with ExitStack() as stores:
        try:
            for item in planned:
                if not item.registered and item.project_id not in registered and home.project(item.project_id) is None:
                    home.register(item.record)
                    registered.append(item.project_id)
            for item in planned:
                head = item.metaform['metaform']
                known = home.metaform_by_id(item.project_id, head['metaform_id'])
                path = (home.store_path(item.project_id, head['metaform_id']) if known is not None
                        else home.store_file(item.project_id, head['name']))
                if not path.exists():
                    created.append(path)
                db = stores.enter_context(open_store(path, write=True))
                opened.append(db)
                db.execute('BEGIN IMMEDIATE')
                _import_rows(db, item.metaform['metaform']['metaform_id'], item.metaform, report)
            for item in planned:
                head = item.metaform['metaform']
                folder = home.project_folder(item.project_id)
                assert folder is not None
                with home.project_db(folder, write=True) as own:
                    added = home.import_metaform_in(own, item.project_id, head['metaform_id'], head['name'],
                                                    head['created'], activate=item.activate,
                                                    never_active=item.never_active)
                report['metaforms_added' if added else 'metaforms_skipped'] += 1
            for db in opened:
                db.execute('COMMIT')
        except BaseException as error:
            for db in opened:
                if db.in_transaction:
                    db.execute('ROLLBACK')
            stores.close()
            for path in created:
                home.remove_store(path)
            for project_id in registered:
                home.remove_project(project_id)
            if isinstance(error, sqlite3.IntegrityError):
                raise StoreError(f'The document does not fit the store: {error}.', 'metaform export > <file>') from None
            raise
    return report


def _missing(db: sqlite3.Connection, need: dict[str, str]) -> bool:
    if need.get('kind') == 'type':
        return db.execute('SELECT 1 FROM types WHERE address=?', (need['address'],)).fetchone() is None
    return (db.execute('SELECT 1 FROM identities WHERE id=?', (need['id'],)).fetchone() is None and
            db.execute('SELECT 1 FROM properties WHERE property_id=? LIMIT 1', (need['id'],)).fetchone() is None)


def _import_rows(db: sqlite3.Connection, metaform_id: str, metaform: dict[str, Any], report: dict[str, Any]) -> None:
    fresh_ids = {row[ID_OF_TABLE[table]] for table in THINGS for row in metaform.get(table, []) if row['op'] == 'add'}
    for place, need in enumerate(metaform.get('requires', [])):
        if not _missing(db, need) or need.get('id') in fresh_ids:
            continue
        name = need.get('id') or need.get('address')
        if need.get('kind') == 'element':
            db.execute('INSERT OR IGNORE INTO element_ids(element_id) VALUES (?)', (need['id'],))
            db.execute("INSERT OR IGNORE INTO identities(id, kind) VALUES (?, 'element')", (need['id'],))
        elif need.get('kind') == 'join':
            db.execute('INSERT OR IGNORE INTO join_ids(join_id) VALUES (?)', (need['id'],))
            db.execute("INSERT OR IGNORE INTO identities(id, kind) VALUES (?, 'join')", (need['id'],))
        elif need.get('kind') == 'type':
            db.execute('INSERT OR IGNORE INTO types(address, parent) VALUES (?, NULL)', (need['address'],))
        report['notices'].append({'where': f'requires[{place}]', 'message': (
            f'{need.get("kind")} {name} is not in this store; what points at it was stored orphaned. To attach it, '
            'import the project\'s map first: metaform import <an export of the project>')})
    new_layers: list[str] = []
    for layer in metaform.get('layers', []):
        if db.execute('SELECT 1 FROM layers WHERE layer_id=?', (layer['layer_id'],)).fetchone():
            report['layers_skipped'] += 1
            continue
        new_layers.append(layer['layer_id'])
        _insert(db, 'layers', {**layer, 'metaform_id': metaform_id})
        report['layers_added'] += 1
    fresh = set(new_layers)
    if not fresh:
        return
    for row in metaform.get('types', []):
        db.execute('INSERT OR IGNORE INTO types(address, parent) VALUES (?, ?)', (row['address'], row['parent']))
    for table in ('layer_fields', 'layer_tags', 'provenance'):
        for row in metaform.get(table, []):
            if row['layer_id'] in fresh:
                _insert(db, table, row)
    for row in metaform.get('layer_sources', []):
        if row['layer_id'] in fresh and db.execute('SELECT 1 FROM layers WHERE layer_id=?',
                                                   (row['source_layer_id'],)).fetchone():
            _insert(db, 'layer_sources', row)
    rows_of: dict[tuple[str, str, str, int], int] = {}
    versions_of: dict[tuple[str, str, str], int] = {}
    touched: dict[str, list[str]] = {kind: [] for kind in versions.ORDER}
    new_ids: set[tuple[str, str]] = set()
    for table in THINGS:  # every identity first, so a subtype join written before its parent finds it, STORE-011
        kind = KIND_OF_TABLE[table]
        for row in metaform.get(table, []):
            if row['layer_id'] in fresh and _identity(db, kind, row):
                new_ids.add((kind, str(row[ID_OF_TABLE[table]])))
    counted: set[tuple[str, str]] = set()
    for table in THINGS:
        kind = KIND_OF_TABLE[table]
        column = ID_OF_TABLE[table]
        for row in metaform.get(table, []):
            if row['layer_id'] not in fresh:
                continue
            key = (kind, str(row[column]))
            if key in new_ids and key not in counted:
                report['things_added'] += 1
                counted.add(key)
            else:
                report['things_skipped'] += 1
            cursor = _insert(db, table, row)
            if kind == 'element' and row['op'] != 'remove':
                versions.hold_address(db, row['address'], row[column])
            version = versions_of.get((kind, row[column], row['layer_id']), 0)
            versions_of[(kind, row[column], row['layer_id'])] = version + 1
            rows_of[(kind, row[column], row['layer_id'], version)] = int(cursor.lastrowid or 0)
            if row[column] not in touched[kind]:
                touched[kind].append(row[column])
    for ref in metaform.get('refs', []):
        if ref['owner_layer_id'] not in fresh:
            continue
        owner_row = rows_of.get((ref['owner'], ref['owner_id'], ref['owner_layer_id'], int(ref['owner_version'])))
        if owner_row is None:
            raise StoreError(f'A ref names {ref["owner"]} {ref["owner_id"]}, which the document does not hold.',
                             'metaform export > <file>')
        db.execute('INSERT INTO refs(owner, owner_row, position, key, value) VALUES (?, ?, ?, ?, ?)',
                   (ref['owner'], owner_row, ref['position'], ref['key'], ref['value']))
    for row in metaform.get('selections', []):
        if row['layer_id'] in fresh:
            db.execute('INSERT OR IGNORE INTO types(address, parent) VALUES (?, NULL)', (prefixes(row['address'])[0],))
            _insert(db, 'selections', row, ignore=True)
    for layer_id in metaform.get('hidden', []):
        if layer_id in fresh:
            db.execute('INSERT OR IGNORE INTO hidden_layers(layer_id) VALUES (?)', (layer_id,))
    for row in metaform.get('challenge_states', []):
        _insert(db, 'challenge_states', row, ignore=True)
    for row in metaform.get('plans', []):
        if row['layer_id'] in fresh:
            _insert(db, 'plans', row, ignore=True)
    for row in metaform.get('work', []):  # a work record has no layer; it follows its object, STORE-042
        _insert(db, 'work', row, ignore=True)
    for kind in versions.ORDER:
        versions.recompute(db, kind, touched[kind])


def _identity(db: sqlite3.Connection, kind: str, row: dict[str, Any]) -> bool:
    """Write the identity rows of an imported thing. Returns whether its identity was new."""
    if kind == 'property':
        return db.execute('SELECT 1 FROM properties WHERE property_id=? LIMIT 1', (row['property_id'],)).fetchone() \
            is None
    ident = row[versions.KINDS[kind].id_column]
    if db.execute('SELECT 1 FROM identities WHERE id=?', (ident,)).fetchone():
        return False
    db.execute('INSERT INTO identities(id, kind) VALUES (?, ?)', (ident, kind))
    if kind == 'element':
        db.execute('INSERT INTO element_ids(element_id) VALUES (?)', (ident,))
    elif kind == 'join':
        db.execute('INSERT INTO join_ids(join_id) VALUES (?)', (ident,))
    else:
        db.execute('INSERT INTO item_ids(item_id, layer_id) VALUES (?, ?)', (ident, row['layer_id']))
    return True


def _insert(db: sqlite3.Connection, table: str, row: dict[str, Any], *, ignore: bool = False) -> sqlite3.Cursor:
    """Insert one checked document row; the SQL names only the table's own columns, never a document's keys."""
    names = list(columns(table))
    marks = ', '.join('?' for _ in names)
    verb = 'INSERT OR IGNORE' if ignore else 'INSERT'
    return db.execute(f'{verb} INTO {table}({", ".join(names)}) VALUES ({marks})', tuple(row[key] for key in names))


def pull_wheel(label: str) -> dict[str, Any]:
    """Pull a directly run wheel's data into this home: each of its metaforms arrives as its own, never active and
    never merged into one that is here; pulling again adds nothing; the wheel's folder is left in place, BASE-025."""
    wheels = home.home() / 'wheels'
    folder = wheels / label
    if not (folder / 'projects').is_dir() and not (folder / 'metaform.sqlite3').is_file():
        found = sorted(path.name for path in wheels.iterdir() if path.is_dir()) if wheels.is_dir() else []
        raise StoreError(f'No data of a wheel {label} at {folder}.',
                         f'metaform import wheel={found[0]}' if found else 'metaform list projects')
    with home.at(folder):
        document = export_document()
    return import_document(document, pulled=label)
