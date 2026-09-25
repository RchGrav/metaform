"""Export and import: a project carried whole, by unique id, STORE-027.

The document is JSON. Every row carries its identity id and layer id, never the
store's `row` integers. Import adds only what the target does not hold: a
metaform whose id exists is not created again, a layer whose id exists is
skipped whole, and a thing whose identity id exists is not added again. Each
metaform's store is imported in one transaction, STORE-006.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Sequence
from functools import cache
from typing import Any

from .. import home
from ..errors import StoreError
from . import corrections
from .ids import prefixes
from .schema import STORE_SCHEMA
from .session import _open

FORMAT = 1
SCHEMA = '1'
THINGS = ('elements', 'joins', 'subtypes', 'items', 'properties')
KIND_OF_TABLE = {'elements': 'element', 'joins': 'join', 'subtypes': 'subtype', 'items': 'item',
                 'properties': 'property'}
ID_OF_TABLE = {table: corrections.KINDS[kind].id_column for table, kind in KIND_OF_TABLE.items()}


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
        chosen = []
        for project_id in project_ids:
            record = home.project(project_id)
            if record is None:
                raise StoreError(f'No project {project_id} is registered.', 'metaform list projects')
            chosen.append(record)
    exported = []
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
    return {'metaform_export': FORMAT, 'schema_version': SCHEMA, 'projects': exported}


def _export_metaform(project_id: str, metaform: home.Metaform, layer_names: Sequence[str]) -> dict[str, Any]:
    document: dict[str, Any] = {'metaform': {'metaform_id': metaform.metaform_id, 'name': metaform.name,
                                             'created': metaform.created}}
    for name in ('types', 'layers', 'layer_fields', 'layer_tags', 'layer_sources', 'provenance', 'selections',
                 'hidden', *THINGS, 'refs', 'challenge_states', 'plans', 'element_roles', 'findings',
                 'correction_stack', 'requires'):
        document[name] = []
    path = home.store_path(project_id, metaform.metaform_id)
    if not path.exists():
        return document
    db = _open(path, create=False)
    try:
        db.execute('BEGIN')
        _fill(db, document, layer_names)
        db.execute('COMMIT')
    finally:
        db.close()
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
    owner_ids: dict[tuple[str, int], tuple[str, str]] = {}
    for table in THINGS:
        rows: list[dict[str, Any]] = []
        for layer_id in [layer['layer_id'] for layer in document['layers']]:
            rows += _rows(db, f'SELECT * FROM {table} WHERE layer_id=?', (layer_id,))
        rows.sort(key=lambda row: row['row'])
        if table == 'subtypes':
            for row in rows:
                row['join_id'] = db.execute('SELECT join_id FROM subtype_ids WHERE subtype_id=?',
                                            (row['subtype_id'],)).fetchone()[0]
        for row in rows:
            owner_ids[(KIND_OF_TABLE[table], row['row'])] = (row[ID_OF_TABLE[table]], row['layer_id'])
        document[table] = _without_row(rows)
    refs = []
    for (owner, owner_row), (owner_id, owner_layer) in sorted(owner_ids.items(), key=lambda pair: pair[0][1]):
        for ref in _rows(db, 'SELECT ref_id, position, key, value FROM refs WHERE owner=? AND owner_row=? '
                             'ORDER BY position', (owner, owner_row)):
            refs.append((ref['ref_id'], {'owner': owner, 'owner_id': owner_id, 'owner_layer_id': owner_layer,
                                         'position': ref['position'], 'key': ref['key'], 'value': ref['value']}))
    refs.sort(key=lambda pair: pair[0])
    document['refs'] = [ref for _, ref in refs]
    item_ids = {row['item_id'] for row in document['items']}
    document['challenge_states'] = [row for row in _rows(db, 'SELECT * FROM challenge_states ORDER BY rowid')
                                    if row['item_id'] in item_ids]
    document['plans'] = [row for row in _rows(db, 'SELECT * FROM plans ORDER BY rowid') if row['layer_id'] in chosen]
    document['element_roles'] = [row for row in _rows(db, 'SELECT * FROM element_roles ORDER BY rowid')
                                 if row['layer_id'] in chosen]
    document['findings'] = _without_row([row for row in _rows(db, 'SELECT * FROM findings ORDER BY row')
                                         if row['layer_id'] in chosen])
    document['correction_stack'] = [row[0] for row in db.execute('SELECT layer_id FROM correction_stack '
                                                                 'ORDER BY position') if row[0] in chosen]
    addresses = {row['address'] for table in ('elements', 'subtypes', 'selections') for row in document[table]}
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
                wanted += [('element', row['receiver']), ('element', row['provider'])]
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
              *THINGS, 'challenge_states', 'plans', 'element_roles', 'findings')
PROJECT_KEYS = ('project_id', 'path', 'target_type', 'target_value')
HEAD_KEYS = ('metaform_id', 'name', 'created')
REF_KEYS = ('owner', 'owner_id', 'owner_layer_id', 'position', 'key', 'value')


@cache
def columns(table: str) -> tuple[str, ...]:
    """The columns a document row of this table carries: the store's own, without `row`, STORE-027."""
    db = sqlite3.connect(':memory:')
    try:
        db.executescript(STORE_SCHEMA)
        found = tuple(str(row[1]) for row in db.execute(f'PRAGMA table_info({table})') if row[1] != 'row')
    finally:
        db.close()
    return (*found, 'join_id') if table == 'subtypes' else found


def _scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float)) and not isinstance(value, bool)


def _record(value: Any, path: str, keys: Sequence[str], problems: list[str]) -> None:
    """One object of the document: exactly these keys, each holding text, a number or null."""
    if not isinstance(value, dict):
        problems.append(f'{path}: not an object')
        return
    problems += [f'{path}.{key}: not a field here' for key in value if key not in keys]
    problems += [f'{path}.{key}: missing' for key in keys if key not in value]
    problems += [f'{path}.{key}: not text, a number or null' for key in keys if key in value
                 and not _scalar(value[key])]


def _strings(value: Any, path: str, problems: list[str]) -> None:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        problems.append(f'{path}: not a list of ids')


def _validate(document: Any) -> None:
    """Check the whole document before anything is written; every problem is named with its path, H8."""
    if not isinstance(document, dict) or document.get('metaform_export') != FORMAT:
        raise StoreError('This is not a Metaform export document.', 'metaform export > <file>')
    if str(document.get('schema_version')) != SCHEMA:
        raise StoreError(f'The document has schema version {document.get("schema_version")}; this Metaform '
                         f'supports version {SCHEMA}.', 'install the Metaform release that wrote it')
    problems: list[str] = []
    entries = document.get('projects')
    if not isinstance(entries, list):
        problems.append('projects: not a list')
        entries = []
    for number, entry in enumerate(entries):
        path = f'projects[{number}]'
        if not isinstance(entry, dict):
            problems.append(f'{path}: not an object')
            continue
        _record(entry.get('project'), f'{path}.project', PROJECT_KEYS, problems)
        if not _scalar(entry.get('active_metaform')):
            problems.append(f'{path}.active_metaform: not an id or null')
        metaforms = entry.get('metaforms')
        if not isinstance(metaforms, list):
            problems.append(f'{path}.metaforms: not a list')
            continue
        for index, metaform in enumerate(metaforms):
            where = f'{path}.metaforms[{index}]'
            if not isinstance(metaform, dict):
                problems.append(f'{where}: not an object')
                continue
            _record(metaform.get('metaform'), f'{where}.metaform', HEAD_KEYS, problems)
            for table in ROW_TABLES:
                rows = metaform.get(table, [])
                if not isinstance(rows, list):
                    problems.append(f'{where}.{table}: not a list')
                    continue
                for place, row in enumerate(rows):
                    _record(row, f'{where}.{table}[{place}]', columns(table), problems)
            for place, ref in enumerate(metaform.get('refs', [])):
                _record(ref, f'{where}.refs[{place}]', REF_KEYS, problems)
            for key in ('hidden', 'correction_stack'):
                _strings(metaform.get(key, []), f'{where}.{key}', problems)
            for place, need in enumerate(metaform.get('requires', [])):
                keys = ('kind', 'address') if isinstance(need, dict) and need.get('kind') == 'type' else ('kind', 'id')
                _record(need, f'{where}.requires[{place}]', keys, problems)
    if problems:
        raise StoreError('The document does not fit an export document:\n' +
                         '\n'.join(f'  {problem}' for problem in problems),
                         'metaform export > <file>, from the home that holds the project')


def import_document(document: dict[str, Any], project: str | None = None) -> dict[str, int]:
    """Add what the target does not hold, by unique id, STORE-027. Returns what was added and skipped."""
    _validate(document)
    report = {'metaforms_added': 0, 'metaforms_skipped': 0, 'layers_added': 0, 'layers_skipped': 0,
              'things_added': 0, 'things_skipped': 0}
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
                home.register(record)
        for metaform in entry.get('metaforms', []):
            head = metaform['metaform']
            known = any(item.metaform_id == head['metaform_id'] for item in home.metaforms(project_id))
            _import_store(project_id, head['metaform_id'], metaform, report)
            if known:
                report['metaforms_skipped'] += 1
            elif home.import_metaform(project_id, head['metaform_id'], head['name'], head['created'],
                                      activate=not registered and entry.get('active_metaform') == head['metaform_id']):
                report['metaforms_added'] += 1
            else:
                report['metaforms_skipped'] += 1
    return report


def _import_store(project_id: str, metaform_id: str, metaform: dict[str, Any], report: dict[str, int]) -> None:
    path = home.store_path(project_id, metaform_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = _open(path, create=True)
    try:
        db.execute('BEGIN IMMEDIATE')
        try:
            _import_rows(db, metaform_id, metaform, report)
        except BaseException:
            db.execute('ROLLBACK')
            raise
        db.execute('COMMIT')
    except sqlite3.IntegrityError as error:
        raise StoreError(f'The document does not fit the store: {error}.', 'metaform export > <file>') from None
    finally:
        db.close()


def _import_rows(db: sqlite3.Connection, metaform_id: str, metaform: dict[str, Any], report: dict[str, int]) -> None:
    for need in metaform.get('requires', []):
        if need.get('kind') == 'type':
            present = db.execute('SELECT 1 FROM types WHERE address=?', (need['address'],)).fetchone()
        else:
            present = db.execute('SELECT 1 FROM identities WHERE id=?', (need['id'],)).fetchone() or \
                db.execute('SELECT 1 FROM properties WHERE property_id=? LIMIT 1', (need['id'],)).fetchone()
        if not present:
            raise StoreError(f'The document needs {need.get("kind")} {need.get("id") or need.get("address")}, which '
                             'this store does not hold.', 'metaform import <the project map export>')
    new_layers = []
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
    rows_of: dict[tuple[str, str, str], int] = {}
    touched: dict[str, list[str]] = {kind: [] for kind in corrections.ORDER}
    for table in THINGS:
        kind = KIND_OF_TABLE[table]
        column = ID_OF_TABLE[table]
        for row in metaform.get(table, []):
            if row['layer_id'] not in fresh:
                continue
            if _identity(db, kind, row):
                report['things_added'] += 1
            else:
                report['things_skipped'] += 1
            cursor = _insert(db, table, row)
            rows_of[(kind, row[column], row['layer_id'])] = int(cursor.lastrowid or 0)
            if row[column] not in touched[kind]:
                touched[kind].append(row[column])
    for ref in metaform.get('refs', []):
        if ref['owner_layer_id'] not in fresh:
            continue
        owner_row = rows_of.get((ref['owner'], ref['owner_id'], ref['owner_layer_id']))
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
    for table in ('element_roles', 'findings'):
        for row in metaform.get(table, []):
            if row['layer_id'] in fresh:
                _insert(db, table, row, ignore=True)
    for layer_id in metaform.get('correction_stack', []):
        if layer_id in fresh:
            db.execute('INSERT INTO correction_stack(position, layer_id) VALUES (?, ?)',
                       (corrections.top_position(db) + 1, layer_id))
    kinds = corrections.layer_kinds(db)
    positions = corrections.stack_positions(db)
    for kind in corrections.ORDER:
        corrections.recompute(db, kind, touched[kind], kinds, positions)


def _identity(db: sqlite3.Connection, kind: str, row: dict[str, Any]) -> bool:
    """Write the identity rows of an imported thing. Returns whether its identity was new."""
    if kind == 'property':
        return db.execute('SELECT 1 FROM properties WHERE property_id=? LIMIT 1', (row['property_id'],)).fetchone() \
            is None
    ident = row[corrections.KINDS[kind].id_column]
    if db.execute('SELECT 1 FROM identities WHERE id=?', (ident,)).fetchone():
        return False
    db.execute('INSERT INTO identities(id, kind) VALUES (?, ?)', (ident, kind))
    if kind == 'element':
        db.execute('INSERT INTO element_ids(element_id) VALUES (?)', (ident,))
    elif kind == 'join':
        db.execute('INSERT INTO join_ids(join_id, receiver) VALUES (?, ?)', (ident, row['receiver']))
    elif kind == 'subtype':
        db.execute('INSERT INTO subtype_ids(subtype_id, join_id) VALUES (?, ?)', (ident, row['join_id']))
    else:
        db.execute('INSERT INTO item_ids(item_id, layer_id) VALUES (?, ?)', (ident, row['layer_id']))
    return True


def _insert(db: sqlite3.Connection, table: str, row: dict[str, Any], *, ignore: bool = False) -> sqlite3.Cursor:
    """Insert one checked document row; the SQL names only the table's own columns, never a document's keys."""
    names = [column for column in columns(table) if not (table == 'subtypes' and column == 'join_id')]
    marks = ', '.join('?' for _ in names)
    verb = 'INSERT OR IGNORE' if ignore else 'INSERT'
    return db.execute(f'{verb} INTO {table}({", ".join(names)}) VALUES ({marks})', tuple(row[key] for key in names))
