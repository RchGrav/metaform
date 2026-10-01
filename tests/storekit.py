"""Test helpers for the storage records: build layers the way writers do, and diff stored tables.

The diff reads the SQLite file directly. It lets a test state which rows an
operation must write and that nothing else changed, which STORE-024 asks for.
The full-text index's shadow tables are left out: they are the index of
`items`, not rows of their own.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

PROVENANCE = {'module': 'test', 'workflow': 'fixture', 'prompt': 'Write the fixture.', 'model': 'none',
              'role': 'fixture writer', 'blinded': False}


def store_file(home: Path, store) -> Path:
    active = store.active_metaform()
    assert active is not None, 'the project has no metaform yet'
    from metaform import home as metaform_home
    return metaform_home.store_path(store.project().project_id, active.metaform_id)


def dump(path: Path) -> dict[str, frozenset]:
    if not path.exists():
        return {}
    db = sqlite3.connect(path)
    try:
        names = [row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "AND name NOT LIKE 'item_text%'")]
        return {name: frozenset(db.execute(f'SELECT * FROM "{name}"').fetchall()) for name in names}
    finally:
        db.close()


def diff(before: dict[str, frozenset], after: dict[str, frozenset]) -> dict[str, tuple[int, int]]:
    """Per table that changed: (rows added, rows removed). A changed row counts once each way."""
    changed = {}
    for name in set(before) | set(after):
        old, new = before.get(name, frozenset()), after.get(name, frozenset())
        if old != new:
            changed[name] = (len(new - old), len(old - new))
    return changed


def intake(store, name='intake-1', ready=True):
    return store.layer(name, 'intake', 'The functional map of the artifact.', kind='intake', mutable=False,
                       hideable=False, provenance=PROVENANCE, ready=ready)


def _named(given, names):
    return [f'{name}={json.dumps(value) if isinstance(value, (list, dict)) else value}'
            for name, value in given.items() if name in names]


def record_intake(run, folder, elements, env=None, finish=()):
    """Record an intake through the command line one object per call, as an intake agent does, then finish it."""
    def call(*args):
        return json.loads(run('intake', *args, '--json', cwd=folder, env=env).stdout)
    run('intake', 'start', cwd=folder, env=env)  # start hands over the Canonical Intake, not JSON, BASE-039
    for element in elements:
        call('element', element['namespace_address'],
             *_named(element, ('role', 'name', 'name_length', 'refs')))
    for element in elements:
        for join in element.get('joins', []):
            made = call('join', element['namespace_address'], join['provider'],
                        *_named(join, ('type', 'name', 'purpose', 'function', 'ef', 'relation', 'verb',
                                       'observation', 'non_goal', 'refs')))
            for subtype in join.get('subtypes', []):
                inner = subtype.get('element', {})
                call('subtype', made['join_id'], inner['namespace_address'],
                     *_named(subtype, ('function', 'ef', 'relation', 'verb', 'observation')),
                     *_named(inner, ('role', 'name', 'name_length', 'refs')))
    return call('finish', *finish)


def knowledge(store, name, *, hideable=True, tags=(), sources=()):
    return store.layer(name, 'test', f'What {name} says at each node.', mutable=True, hideable=hideable,
                       provenance=PROVENANCE, tags=tags, sources=sources)


def correction(store, name):
    return store.layer(name, 'test', 'Corrections to the metaform.', kind='correction', mutable=False,
                       hideable=False, provenance=PROVENANCE)


def memory(store):
    return store.layer('memory', 'memory', 'What agents have noted at this node.', kind='memory', mutable=True,
                       hideable=True, ready=True)


def small_map(store):
    """An intake with a CQU receiving from a DE, and the DE receiving from an SE through a join with one subtype.

    Each element is its address, name_length and role; the project's name for each functionality is on its join."""
    with store.atomic():
        layer = intake(store)
        store.add_element(layer.name, 'stakeholder.cook.home', name_length=2, role='CQU')
        store.add_element(layer.name, 'code.timer.kitchen', name_length=2, role='DE')
        store.add_element(layer.name, 'code.alarm.audible', name_length=2, role='SE')
        outer = store.add_join(layer.name, 'stakeholder.cook.home', 'code.timer.kitchen', name='kitchen timer',
                               purpose='Know when each dish is done.', function='Counts down and rings.',
                               relation='The timer tells the cook.', observation='One countdown per dish.',
                               refs=[('path', 'src')])
        inner = store.add_join(layer.name, 'code.timer.kitchen', 'code.alarm.audible', name='audible alarm',
                               purpose='Get attention when a countdown ends.', function='Plays a tone.',
                               relation='The alarm rings for the timer.', observation='A piezo speaker.')
        store.add_subtype(layer.name, outer.join_id, 'code.loop.tick', function='Advances each countdown.',
                          relation='The tick loop drives the timer.', observation='One tick per second.',
                          name='tick loop', name_length=2, role='SE', refs=[('path', 'src/tick.c')])
    return layer, outer, inner


def values(view, layer=None):
    """The item values of a node read, per layer name, or for one layer."""
    grouped = {group.layer: [item.value for item in group.items] for group in view.layers}
    return grouped if layer is None else grouped.get(layer, [])


ALLOWED_SCANS = {'layers', 'projects', 'hidden_layers', 'layer_sources', 'layer_tags', 'correction_stack'}
PLANNED = ('SELECT', 'WITH', 'INSERT', 'UPDATE', 'DELETE')


def plans(home, store, statements):
    from metaform.data.prompts import PROMPT_SCHEMA
    base = home / 'metaform.sqlite3'
    issued = list(statements)
    # The home's prompt store may not exist yet; its reads are planned against its schema, STORE-044.
    prompt_store = home / 'prompts.sqlite3'
    if not prompt_store.exists():
        prompt_store = ':memory:prompts'
    from metaform import home as metaform_home
    own = metaform_home.project_folder(store.project().project_id)
    paths = (store_file(home, store), base, prompt_store, *((own / 'project.sqlite3',) if own is not None else ()))
    found = []
    for statement in issued:
        if not statement.lstrip().upper().startswith(PLANNED):
            continue
        if "'main'.'item_text_" in statement:  # FTS5 reading its own shadow tables, not a query of the store
            continue
        for path in paths:
            if path == ':memory:prompts':
                db = sqlite3.connect(':memory:')
                db.executescript(PROMPT_SCHEMA)
            else:
                db = sqlite3.connect(path)
            try:
                found.append((statement, [row[3] for row in db.execute('EXPLAIN QUERY PLAN ' + statement)]))
                break
            except sqlite3.OperationalError:
                continue
            finally:
                db.close()
        else:
            raise AssertionError(f'Could not plan {statement}')
    return found


def scans(plan_lines):
    bad = []
    for line in plan_lines:
        if not line.startswith('SCAN '):
            continue
        table = line.split()[1]
        if table in ALLOWED_SCANS or line == 'SCAN CONSTANT ROW':
            continue
        if table == 'item_text' and 'VIRTUAL TABLE INDEX' in line:
            continue
        bad.append(line)
    return bad


