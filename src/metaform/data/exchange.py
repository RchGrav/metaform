"""Export and import: a project carried whole, by unique id, STORE-027 and STORE-046.

The document is JSON. A base travels as its op log: every op with its kind, its id, its layer and its data, in
the order it was written, so what comes back is what was, versions, provenance and all. Import adds only what the
target does not hold: a base whose id exists is not created again, a layer whose id exists is skipped whole, and
an object whose id exists is not added again. Each base's store is imported in one transaction, STORE-006.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import home
from ..errors import StoreError
from ..sqlite import COMPATIBLE_FROM, SCHEMA_VERSION, readable
from . import log, tables
from .ids import as_list, as_object, new_id
from .projection import OBJECT_KINDS, Op, Projection
from .session import open_store

FORMAT = 2
OP_KEYS = ('seq', 'session_id', 'at', 'op', 'kind', 'id', 'layer_id', 'data')
OPS = ('add', 'change', 'remove')
KINDS = (*OBJECT_KINDS, 'layer', 'selection', 'type')
PROJECT_KEYS = ('project_id', 'path', 'target_type', 'target_value')
HEAD_KEYS = ('id', 'name', 'created')
REFERENCES = ('receiver', 'target_id', 'link_id', 'element_id')  # the fields of an op's data that name another object


# ------------------------------------------------------------------------------------------------- export

def export_document(project_ids: Sequence[str] | None = None, *, metaform: str | None = None,
                    layers: Sequence[str] = ()) -> dict[str, Any]:
    """The exchange document for the named projects, or every project when none or `all` is named; `metaform`
    names one base of each."""
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
        bases = [item for item in home.bases(record.project_id) if metaform is None or item.name == metaform]
        if metaform is not None and not bases:
            raise StoreError(f'No base {metaform} in {record.project_id}.', 'metaform list bases')
        active = home.active_base(record.project_id)
        entry: dict[str, Any] = {
            'project': record.to_dict(),
            'bases': [_export_base(record.project_id, item, layers) for item in bases],
            'active_base': active.id if active else None,
        }
        modules = _export_project_modules(record.project_id)
        if modules:  # a module's project-level tables, STORE-045
            entry['modules'] = modules
        exported.append(entry)
    return {'metaform_export': FORMAT, 'schema_version': SCHEMA_VERSION, 'compatible_from': COMPATIBLE_FROM,
            'projects': exported}


def _export_base(project_id: str, base: home.Base, layer_names: Sequence[str]) -> dict[str, Any]:
    document: dict[str, Any] = {'base': {'id': base.id, 'name': base.name, 'created': base.created}}
    with open_store(home.store_path(project_id, base.id), write=False) as db:
        db.execute('BEGIN')
        ops = log.read_ops(db, 0)
        modules = tables.export_modules(db)
        unowned = tables.export_unowned(db)
        prior = db.execute("SELECT value FROM meta WHERE key='prior_schema_version'").fetchone()
        if prior is not None:
            document['prior_schema_version'] = str(prior[0])
        db.execute('COMMIT')
    if layer_names:
        named: dict[str, str] = {}  # layer id to its name now: a rename is a change of name, layering.rename
        for op in ops:
            if op['kind'] == 'layer' and op['op'] in ('add', 'change') and 'name' in op['data']:
                named[op['id']] = op['data']['name']
        known = {name: ident for ident, name in named.items()}
        missing = [name for name in layer_names if name not in known]
        if missing:
            raise StoreError(f'No layer {missing[0]}.', 'metaform map layers')
        chosen = {known[name] for name in layer_names}
        ops = [op for op in ops if op['kind'] == 'type' or op['layer_id'] in chosen
               or (op['kind'] in OBJECT_KINDS and op['layer_id'] == '' )]
        for op in ops:
            if op['kind'] == 'layer':
                op['data'] = {**op['data'], 'sources': [source for source in op['data'].get('sources', ())
                                                        if source in chosen]}
    document['ops'] = ops
    document['requires'] = _requires(ops)
    extensions = [entry for entry in modules if any(value.get('schema') is not None for value in entry['tables'])]
    modules = [entry for entry in modules if entry not in extensions]
    if unowned:
        document['unowned_tables'] = unowned
    if extensions:
        layer_ids = {op['id'] for op in ops if op['kind'] == 'layer'}
        items = {op['id'] for op in ops if op['kind'] == 'item'}
        for entry in extensions:
            for value in entry['tables']:
                table = tables.Table.from_dict(value)
                rows = entry['rows'][table.name]
                names = {column.name for column in table.columns}
                if 'layer_id' in names:
                    rows = [row for row in rows if row['layer_id'] is None or row['layer_id'] in layer_ids]
                elif 'item_id' in names:
                    rows = [row for row in rows if row['item_id'] in items]
                entry['rows'][table.name] = rows
        document['extensions'] = extensions
    if modules:  # the modules' tables beside the map, STORE-045
        document['modules'] = modules
    return document


def _export_project_modules(project_id: str) -> list[dict[str, Any]]:
    """The modules' project-level tables, each module's store read in one transaction, STORE-045."""
    exported: list[dict[str, Any]] = []
    for path in tables.project_stores(project_id):
        with tables.project_transaction(path, write=False) as db:
            exported += tables.export_modules(db)
    return exported


def _requires(ops: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Ids the exported ops point at that no exported op adds."""
    added = {op['id'] for op in ops if op['kind'] in OBJECT_KINDS and op['op'] == 'add'}
    wanted: list[tuple[str, str]] = []
    for op in ops:
        if op['kind'] not in OBJECT_KINDS:
            continue
        data = op['data']
        if op['op'] != 'add' and op['kind'] != 'property':
            wanted.append((op['kind'], op['id']))
        if op['kind'] == 'join':
            wanted.append(('element', str(data.get('receiver'))))
            wanted += [('element', str(held)) for held in data.get('held', ())]
        if op['kind'] == 'item':
            wanted.append((str(data.get('target_kind')), str(data.get('target_id'))))
            if data.get('link_kind'):
                wanted.append((str(data['link_kind']), str(data['link_id'])))
        if op['kind'] == 'property':
            wanted.append(('element', str(data.get('element_id'))))
    found: list[dict[str, str]] = []
    for kind, ident in wanted:
        entry = {'kind': kind, 'id': ident}
        if ident not in added and ident != 'None' and entry not in found:
            found.append(entry)
    return found



# ---------------------------------------------------------------------------------------- documents of format 1

TABLE_KINDS = {'elements': 'element', 'joins': 'join', 'properties': 'property', 'items': 'item'}
ID_COLUMNS = {'elements': 'element_id', 'joins': 'join_id', 'properties': 'property_id', 'items': 'item_id'}


def from_format_1(document: dict[str, Any]) -> dict[str, Any]:
    """A document written before the log, format 1 at layout 19 or 20, as a format 2 document: each metaform's rows
    are loaded into a layout 20 database in memory and read into ops the way an upgrade reads a store, so the bundled
    map of Metaform and every earlier export still import, BASE-048 and STORE-027."""
    from .schema import LAYOUT_20
    from .upgrade import ops_of
    whole = as_object(document)
    if whole is None or whole.get('metaform_export') != 1:
        raise StoreError('This is not a Metaform export document.', 'metaform export > <file>')
    if str(whole.get('schema_version')) not in ('19', '20'):
        raise StoreError(f'The document has schema version {whole.get("schema_version")}; this Metaform reads '
                         'format 1 documents at version 19 or 20.', 'install the Metaform release that wrote it')
    projects: list[dict[str, Any]] = []
    for entry in as_list(whole.get('projects')) or []:
        bases: list[dict[str, Any]] = []
        for metaform in entry.get('metaforms', []):
            head = metaform['metaform']
            db = sqlite3.connect(':memory:')
            db.executescript(LAYOUT_20)
            rows_by_key: dict[tuple[str, str, str, int], int] = {}
            for layer in metaform.get('layers', []):
                db.execute('INSERT INTO layers(layer_id, metaform_id, name, module, variable, mutable, hideable, '
                           'result_id, kind, created, ready) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                           (layer['layer_id'], layer.get('metaform_id') or head.get('metaform_id') or head.get('id'),
                            layer['name'], layer['module'], layer['variable'], layer['mutable'], layer['hideable'],
                            layer.get('result_id'), layer['kind'], layer['created'], layer.get('ready')))
            for table, columns in (('provenance', ('layer_id', 'module', 'workflow', 'prompt', 'model', 'role', 'blinded')),
                                   ('layer_fields', ('layer_id', 'position', 'name')),
                                   ('layer_tags', ('layer_id', 'tag')),
                                   ('layer_sources', ('layer_id', 'source_layer_id')),
                                   ('selections', ('address', 'layer_id', 'kind')),
                                   ('reexamine', ('layer_id', 'changed_in', 'thing_id'))):
                for row in metaform.get(table, []):
                    db.execute(f'INSERT OR IGNORE INTO {table}({", ".join(columns)}) VALUES ({", ".join("?" for _ in columns)})',
                               tuple(row.get(column) for column in columns))
            for layer_id in metaform.get('hidden', []):
                db.execute('INSERT OR IGNORE INTO hidden_layers(layer_id) VALUES (?)', (layer_id,))
            for row in metaform.get('types', []):
                db.execute('INSERT OR IGNORE INTO types(address, parent) VALUES (?, ?)', (row['address'], row.get('parent')))
            for table, kind in TABLE_KINDS.items():
                ident = ID_COLUMNS[table]
                seen: dict[tuple[str, str], int] = {}
                for row in metaform.get(table, []):
                    columns = [key for key in row if key != 'row']
                    if kind != 'property':
                        db.execute('INSERT OR IGNORE INTO identities(id, kind) VALUES (?, ?)', (row[ident], kind))
                        if kind == 'element':
                            db.execute('INSERT OR IGNORE INTO element_ids(element_id) VALUES (?)', (row[ident],))
                        elif kind == 'join':
                            db.execute('INSERT OR IGNORE INTO join_ids(join_id) VALUES (?)', (row[ident],))
                        else:
                            db.execute('INSERT OR IGNORE INTO item_ids(item_id, layer_id) VALUES (?, ?)',
                                       (row[ident], row['layer_id']))
                    cursor = db.execute(f'INSERT INTO {table}({", ".join(columns)}) VALUES ({", ".join("?" for _ in columns)})',
                                        tuple(row[column] for column in columns))
                    version = seen.get((row[ident], row['layer_id']), 0)
                    seen[(row[ident], row['layer_id'])] = version + 1
                    rows_by_key[(kind, row[ident], row['layer_id'], version)] = int(cursor.lastrowid or 0)
                    if kind == 'element':
                        db.execute('INSERT OR REPLACE INTO address_elements(address, element_id) VALUES (?, ?)',
                                   (row['address'], row[ident]))
            for held in metaform.get('join_elements', []):
                row_number = rows_by_key.get(('join', held['join_id'], held['join_layer_id'], held['join_version']))
                if row_number is not None:
                    db.execute('INSERT OR IGNORE INTO join_elements(join_row, position, element_id) VALUES (?, ?, ?)',
                               (row_number, held['position'], held['element_id']))
            for ref in metaform.get('refs', []):
                row_number = rows_by_key.get((ref['owner'], ref['owner_id'], ref['owner_layer_id'], ref['owner_version']))
                if row_number is not None:
                    db.execute('INSERT INTO refs(owner, owner_row, position, key, value) VALUES (?, ?, ?, ?, ?)',
                               (ref['owner'], row_number, ref['position'], ref['key'], ref['value']))
            db.row_factory = sqlite3.Row
            ops = [{'seq': number, 'session_id': 'format-1', 'at': head.get('created') or home.now(), 'op': op,
                    'kind': kind, 'id': ident, 'layer_id': layer_id, 'data': data}
                   for number, (op, kind, ident, layer_id, data) in enumerate(ops_of(db), 1)]
            db.close()
            base: dict[str, Any] = {'base': {'id': head.get('metaform_id') or head.get('id'), 'name': head['name'],
                                             'created': head['created']},
                                    'ops': ops, 'requires': _requires(ops)}
            for key in ('modules', 'extensions', 'unowned_tables'):
                if key in metaform:
                    base[key] = metaform[key]
            bases.append(base)
        projects.append({'project': entry['project'], 'bases': bases,
                         'active_base': entry.get('active_base', entry.get('active_metaform')),
                         **({'modules': entry['modules']} if entry.get('modules') else {})})
    return {'metaform_export': FORMAT, 'schema_version': SCHEMA_VERSION, 'compatible_from': COMPATIBLE_FROM,
            'projects': projects}


# ----------------------------------------------------------------------------------------------- validation

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


def _op(value: Any, path: str, problems: list[str]) -> None:
    """One op of the document: its fields, each of the right form, and data that is an object."""
    fields = as_object(value)
    if fields is None:
        problems.append(f'{path}: not an object')
        return
    problems += [f'{path}.{key}: not a field here' for key in fields if key not in OP_KEYS]
    problems += [f'{path}.{key}: missing' for key in OP_KEYS if key not in fields]
    if 'seq' in fields and (isinstance(fields['seq'], bool) or not isinstance(fields['seq'], int)):
        problems.append(f'{path}.seq: not a whole number')
    for key in ('session_id', 'at', 'id', 'layer_id'):
        if key in fields and not isinstance(fields[key], str):
            problems.append(f'{path}.{key}: not text')
    if 'op' in fields and fields['op'] not in OPS:
        problems.append(f'{path}.op: not add, change or remove')
    if 'kind' in fields and fields['kind'] not in KINDS:
        problems.append(f'{path}.kind: not a kind of op')
    if 'data' in fields and as_object(fields['data']) is None:
        problems.append(f'{path}.data: not an object')


def _layout(value: str | None) -> int | None:
    """A layout version as a number, or None: ASCII digits only, so a document's `²` is refused, never raised."""
    return int(value) if value is not None and value.isascii() and value.isdigit() else None


def _readable(whole: dict[str, Any]) -> None:
    """Refuse a document only when this Metaform cannot read it, STORE-029: one at this layout, at a later layout whose
    `compatible_from` is at or below this one, or at an earlier layout from this one's `compatible_from` on, which
    differs from this one only by what this one added, is read as it is. A document without `compatible_from` takes
    it as its own `schema_version`."""
    found, needed = str(whole.get('schema_version')), whole.get('compatible_from')
    needed = None if needed is None or isinstance(needed, bool) else str(needed)
    if 'compatible_from' in whole and needed is None:
        raise StoreError('The document\'s compatible_from is not a layout version.', 'metaform export > <file>')
    if readable(found, needed, SCHEMA_VERSION):
        return
    at, oldest = _layout(found), _layout(needed)
    if at is not None and int(COMPATIBLE_FROM) <= at < int(SCHEMA_VERSION) and (needed is None or oldest is not None
                                                                               and oldest <= at):
        return
    if oldest is not None and oldest > int(SCHEMA_VERSION):
        raise StoreError(f'The document has schema version {found}, which a Metaform reads from version {needed}; '
                         f'this Metaform supports version {SCHEMA_VERSION}.',
                         'install the Metaform release that wrote it')
    raise StoreError(f'The document has schema version {found}; this Metaform supports version {SCHEMA_VERSION}.',
                     'install the Metaform release that wrote it')


def _validate(document: Any) -> None:
    """Check the whole document before anything is written; every problem is named with its path, H8."""
    whole = as_object(document)
    if whole is None or whole.get('metaform_export') != FORMAT:
        raise StoreError('This is not a Metaform export document.', 'metaform export > <file>')
    _readable(whole)
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
        project_id = (as_object(entry.get('project')) or {}).get('project_id')
        if isinstance(project_id, str) and not home.PROJECT_ID.fullmatch(project_id):
            # The id names the project's folder entries, archives and downloads; one from a document is held to the
            # rule metaform add project holds a typed one to, so no document reaches outside a folder with it.
            problems.append(f'{path}.project.project_id: not a project id')
        if 'modules' in entry:
            tables.check(entry['modules'], f'{path}.modules', problems)
        if not _scalar(entry.get('active_base')):
            problems.append(f'{path}.active_base: not an id or null')
        bases = as_list(entry.get('bases'))
        if bases is None:
            problems.append(f'{path}.bases: not a list')
            continue
        for index, held in enumerate(bases):
            where = f'{path}.bases[{index}]'
            base = as_object(held)
            if base is None:
                problems.append(f'{where}: not an object')
                continue
            _record(base.get('base'), f'{where}.base', HEAD_KEYS, problems)
            name = (as_object(base.get('base')) or {}).get('name')
            if isinstance(name, (str, int, float)) and not home.NAME.fullmatch(str(name)):
                problems.append(f'{where}.base.name: not a base name')  # it names the store's file, STORE-003
            if 'prior_schema_version' in base and base['prior_schema_version'] not in (
                    '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20'):
                problems.append(f'{where}.prior_schema_version: not a historical layout version')
            if 'unowned_tables' in base:
                tables.check_unowned(base['unowned_tables'], f'{where}.unowned_tables', problems)
            for key in ('modules', 'extensions'):
                if key in base:
                    tables.check(base[key], f'{where}.{key}', problems)
            ops = as_list(base.get('ops', []))
            if ops is None:
                problems.append(f'{where}.ops: not a list')
            for place, op in enumerate(ops or []):
                _op(op, f'{where}.ops[{place}]', problems)
            requires = as_list(base.get('requires', []))
            if requires is None:
                problems.append(f'{where}.requires: not a list')
            for place, need in enumerate(requires or []):
                _record(need, f'{where}.requires[{place}]', ('kind', 'id'), problems)
    if problems:
        raise StoreError('The document does not fit an export document:\n' +
                         '\n'.join(f'  {problem}' for problem in problems),
                         'metaform export > <file>, from the home that holds the project')


# ------------------------------------------------------------------------------------------------ collapse

def _replayed(ops: list[dict[str, Any]]) -> Projection:
    made = Projection()
    for number, op in enumerate(ops, 1):
        made.apply(Op(number, str(op['session_id']), str(op['op']), str(op['kind']), str(op['id']),
                      str(op['layer_id']), dict(op['data'])))
    return made


def collapsed(document: dict[str, Any], name: str, *, workflow: str, role: str, base_id: str | None = None,
              created: str | None = None) -> dict[str, Any]:
    """A new base `name` holding each current element and join of the base layer once, with its held elements,
    LAYER-026: one layer of ops, each an add, every id carried over."""
    _validate(document)
    projects = document['projects']
    if len(projects) != 1 or len(projects[0]['bases']) != 1:
        raise StoreError('Collapse takes exactly one project and base.', 'metaform export metaform=<name>')
    project = projects[0]
    source = project['bases'][0]
    replayed = _replayed(source['ops'])
    intake = [layer for layer in replayed.layers.values() if layer.kind == 'base']
    if len(intake) != 1:
        raise StoreError('Collapse needs the base to have one base layer.', 'metaform map layers')
    if intake[0].ready is None:  # collapsing would mark a building intake finished
        raise StoreError('The intake is still building; finish it before collapsing.', 'metaform intake finish')
    source_layer = intake[0].id
    base_id, layer_id, created = base_id or new_id(), new_id(), created or home.now()
    stamp = created
    ops: list[dict[str, Any]] = []

    def emit(op: str, kind: str, ident: str, data: dict[str, Any]) -> None:
        ops.append({'seq': len(ops) + 1, 'session_id': 'collapse', 'at': stamp, 'op': op, 'kind': kind, 'id': ident,
                    'layer_id': layer_id if kind != 'type' else '', 'data': data})

    layer = intake[0].to_data()
    emit('add', 'layer', layer_id, {**layer, 'base_id': base_id, 'name': 'base', 'result_id': None,
                                     'created': created, 'ready': created, 'hidden': False, 'sources': [],
                                     'reexamine': [], 'tags': [], 'provenance': {
                                         'module': 'chassis', 'workflow': workflow, 'prompt': None, 'model': None,
                                         'role': role, 'blinded': None}})
    for kind in ('element', 'join'):
        for ident, version in replayed.currents(kind):
            if version.layer_id != source_layer:
                continue
            emit('add', kind, ident, {'mode': 'add', 'reason': None, 'evidence': None, **version.fields})
    result: dict[str, Any] = {'base': {'id': base_id, 'name': name, 'created': created}, 'ops': ops,
                              'requires': _requires(ops)}
    released = {**{key: document[key] for key in ('metaform_export', 'schema_version', 'compatible_from')
                   if key in document},
                'projects': [{'project': project['project'].copy(), 'bases': [result], 'active_base': base_id}]}
    _validate(released)
    return released


# ------------------------------------------------------------------------------------------------- import

@dataclass
class Planned:
    """One base of the document, with the project it goes to and whether that project is registered here."""
    project_id: str
    record: home.Project
    registered: bool
    base: dict[str, Any]
    activate: bool


def _plan(document: dict[str, Any], project: str | None,
          notices: list[dict[str, str]]) -> tuple[list[Planned], int]:
    """Where each base goes, decided before anything is written, and how many are skipped.

    A base another project owns here is not created again, STORE-027: nothing of it is written, and a notice
    names the project that owns it, BASE-044.
    """
    planned: list[Planned] = []
    skipped = 0
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
            if not registered and not record.path:
                # A document that carries no folder, as the release's own map, BASE-048, goes into a project
                # the person names, never one registered nowhere.
                raise StoreError(f'The document carries project {project_id} without a folder.',
                                 'metaform import <file> <project>')
            if not registered:
                holder = home.project_at(record.path)
                if holder is not None:
                    raise StoreError(f'{record.path} is already registered as project {holder}.',
                                     f'metaform import <file> {holder}')
        for base in entry.get('bases', []):
            base_id = base['base']['id']
            owner = home.base_owner(base_id)
            if owner is not None and owner != project_id:
                skipped += 1
                notices.append({'where': f'bases.{base_id}', 'message': (
                    f'Base {base_id} belongs to project {owner} here; nothing of it was written. To add '
                    f'what it holds to that project: metaform import <file> {owner}')})
                continue
            planned.append(Planned(project_id, record, registered, base,
                                   not registered and entry.get('active_base') == base_id))
    return planned, skipped


def import_document(document: dict[str, Any], project: str | None = None) -> dict[str, Any]:
    """Add what the target does not hold, by unique id, as one unit, STORE-027 and STORE-006.

    A document of format 1, written before the log, is read as one of format 2 first.

    The document is checked whole and every base's place decided before anything is written. A project the
    home does not hold is registered first, in a folder of its own, PROJ-026. Each store's ops are appended in an
    open transaction; each project's base rows are then written and committed, and only then each store. When
    anything fails, every store transaction rolls back, every store file this import created is removed, and a
    project it registered is taken off the list again. Returns what was added and skipped, and a notice for each
    identity the document needs that this home does not hold, BASE-044.
    """
    if project is not None and not home.PROJECT_ID.fullmatch(project):
        raise StoreError(f'{project!r} is not a project id: use lowercase letters, digits, - and _.',
                         'metaform list projects')
    if as_object(document) is not None and document.get('metaform_export') == 1:
        document = from_format_1(document)
    _validate(document)
    notices: list[dict[str, str]] = []
    planned, skipped = _plan(document, project, notices)
    report: dict[str, Any] = {'bases_added': 0, 'bases_skipped': skipped, 'layers_added': 0,
                              'layers_skipped': 0, 'things_added': 0, 'things_skipped': 0, 'notices': notices}
    opened: list[sqlite3.Connection] = []
    created: list[Path] = []
    registered: list[str] = []
    touched: list[Path] = []
    with ExitStack() as stores:
        try:
            for item in planned:
                if not item.registered and item.project_id not in registered and home.project(item.project_id) is None:
                    home.register(item.record)
                    registered.append(item.project_id)
            for item in planned:
                head = item.base['base']
                known = home.base_by_id(item.project_id, head['id'])
                path = (home.store_path(item.project_id, head['id']) if known is not None
                        else home.store_file(item.project_id, head['name']))
                if not path.exists():
                    created.append(path)
                db = stores.enter_context(open_store(path, write=True))
                opened.append(db)
                touched.append(path)
                db.execute('BEGIN IMMEDIATE')
                _import_ops(db, path, item.base, report)
            for entry in document.get('projects', []):  # the modules' project-level tables, STORE-045
                if not entry.get('modules'):
                    continue
                project_id = project if project is not None else entry['project']['project_id']
                if home.project(project_id) is None:
                    home.register(home.Project(**entry['project']))
                    registered.append(project_id)
                for held in entry['modules']:
                    path = tables.project_store(project_id, held['module'])
                    if not path.exists():
                        created.append(path)
                    db = stores.enter_context(tables.open_project_store(path, write=True))
                    opened.append(db)
                    db.execute('BEGIN IMMEDIATE')
                    tables.import_modules(db, [held], report, f'projects.{project_id}.modules')
            for item in planned:
                head = item.base['base']
                folder = home.project_folder(item.project_id)
                assert folder is not None
                with home.project_db(folder, write=True) as own:
                    added = home.import_base_in(own, item.project_id, head['id'], head['name'],
                                                head['created'], activate=item.activate)
                report['bases_added' if added else 'bases_skipped'] += 1
            for db in opened:
                db.execute('COMMIT')
        except BaseException as error:
            for db in opened:
                if db.in_transaction:
                    db.execute('ROLLBACK')
            for path in touched:
                log.forget(path)  # the projection took ops the log never did
            stores.close()
            for path in created:
                home.remove_store(path)
            for project_id in registered:
                home.forget_project(project_id)
            if isinstance(error, sqlite3.IntegrityError):
                raise StoreError(f'The document does not fit the store: {error}.', 'metaform export > <file>') from None
            raise
    return report


def _import_ops(db: sqlite3.Connection, path: Path, base: dict[str, Any], report: dict[str, Any]) -> None:
    """Append the document's ops the store does not hold: a layer whose id exists is skipped whole, an object whose
    id exists is skipped whole, the rest is appended in the document's order under one session."""
    held = log.projection(path, db)
    with held.lock:
        if 'prior_schema_version' in base:  # the layout the base was written at before it was upgraded, carried
            db.execute("INSERT OR IGNORE INTO meta(key,value) VALUES ('prior_schema_version',?)",
                       (base['prior_schema_version'],))
        known_layers = set(held.layers) | {op['id'] for op in base['ops'] if op['kind'] == 'layer' and op['op'] == 'remove'}
        known_layers &= set(held.layers)
        skipped_layers: set[str] = set()
        added_layers: set[str] = set()
        skipped_things: set[str] = set()
        added_things: set[str] = set()
        pending: list[Op] = []
        at = home.now()
        for op in base['ops']:
            kind, ident = str(op['kind']), str(op['id'])
            if kind == 'layer':
                if ident in known_layers or ident in skipped_layers:
                    skipped_layers.add(ident)
                    continue
                added_layers.add(ident)
            elif kind in OBJECT_KINDS:
                if ident in skipped_things or (ident in held.kinds and ident not in added_things):
                    skipped_things.add(ident)
                    continue
                if op['layer_id'] in skipped_layers:
                    skipped_things.add(ident)
                    continue
                added_things.add(ident)
            elif kind == 'selection':
                key = (op['data'].get('address'), op['data'].get('layer_id'), op['data'].get('kind'))
                if op['layer_id'] in skipped_layers or (op['op'] == 'add' and key in held.selections):
                    continue
            elif kind == 'type':
                if op['data'].get('address') in held.types:
                    continue
            made = Op(held.seq + 1, str(op['session_id']), str(op['op']), kind, ident, str(op['layer_id']),
                      dict(op['data']), str(op['at']))
            held.apply(made)
            pending.append(made)
        log.append(db, pending, at)
        report['layers_added'] += len(added_layers)
        report['layers_skipped'] += len(skipped_layers)
        report['things_added'] += len(added_things)
        report['things_skipped'] += len(skipped_things)
        for need in base.get('requires', []):
            if need['id'] not in held.kinds:
                report['notices'].append({'where': f'requires.{need["id"]}', 'message': (
                    f'The document points at {need["kind"]} {need["id"]}, which this home does not hold; what points '
                    f'at it is orphaned until it arrives: metaform import <file> with the layer that adds it')})
        _import_extensions(db, base, report, base['base']['id'])


def _import_extensions(db: sqlite3.Connection, document: dict[str, Any], report: dict[str, Any],
                       base_id: str) -> None:
    """Import declared extensions after the identities and layers their rows can reference."""
    tables.import_unowned(db, document.get('unowned_tables', []))
    entries = document.get('modules', []) + document.get('extensions', [])
    tables.import_modules(db, entries, report, f'bases.{base_id}.modules')
