"""A module declares its own tables and reaches them through the data access object, STORE-045.

The chassis creates them, versions them with the module's own version, upgrades them, and carries them through
backup, export, import and clear by their kind: a metaform-level table goes with its metaform, a project-level one
outlives a clear. The module reads and writes them inside a transaction the data access object gives it.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest

from metaform import home as metaform_home
from metaform import loader
from metaform.data import Store, StoreError, export_document, import_document
from metaform.sqlite import SCHEMA_VERSION

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('STORE-045')]

LEDGER_V1 = '''
    from metaform.data import Column, Index, Table, Tables
    from metaform.module import Module
    SUPPORTED_OS = ('linux', 'macos', 'windows')
    TABLES = Tables(version=1, tables=(
        Table('entries', place='metaform', key=('entry_id',),
              columns=(Column('entry_id', required=True), Column('who', required=True), Column('amount', 'int'),
                       Column('paid', 'bool', default=False), Column('detail', 'json')),
              indexes=(Index(('who',)),)),
        Table('notes', place='project', key=('note_id',),
              columns=(Column('note_id', required=True), Column('text', required=True), Column('at', required=True)),
              indexes=(Index(('at',)),)),
    ))
    MODULE = Module(id='ledger', summary='Ledger.', purpose='Keeps a ledger. Details: metaform help ledger.',
                    tables=TABLES)
'''

LEDGER_V2 = '''
    from metaform.data import Column, Index, Table, Tables
    from metaform.module import Module
    SUPPORTED_OS = ('linux', 'macos', 'windows')
    SEEN = []
    def upgrade(tx, found):
        SEEN.append(found)
        if tx.place != 'metaform':  # it runs once in each store that holds the module's tables
            return
        for row in tx.rows('entries', limit=0).results:
            tx.update('entries', {'entry_id': row['entry_id']}, {'currency': 'EUR'})
    TABLES = Tables(version=2, upgrade=upgrade, tables=(
        Table('entries', place='metaform', key=('entry_id',),
              columns=(Column('entry_id', required=True), Column('who', required=True), Column('amount', 'int'),
                       Column('paid', 'bool', default=False), Column('detail', 'json'), Column('currency')),
              indexes=(Index(('who',)), Index(('currency', 'who')))),
        Table('notes', place='project', key=('note_id',),
              columns=(Column('note_id', required=True), Column('text', required=True), Column('at', required=True)),
              indexes=(Index(('at',)),)),
    ))
    MODULE = Module(id='ledger', summary='Ledger.', purpose='Keeps a ledger. Details: metaform help ledger.',
                    tables=TABLES)
'''


@pytest.fixture
def ledger(home, project_folder, user_module):
    """The module ledger, loaded in this process, and a store working for it in project proj."""
    user_module('ledger', LEDGER_V1)
    loader.reset()
    yield Store('proj', module='ledger')
    loader.reset()


def store_file(project='proj'):
    active = metaform_home.active_base(project)
    assert active is not None
    return metaform_home.store_path(project, active.id)


def project_store(project='proj', module='ledger'):
    folder = metaform_home.project_folder(project)
    assert folder is not None
    return folder / 'modules' / f'{module}.sqlite3'


def raw(path, sql, params=()):
    db = sqlite3.connect(path)
    try:
        return db.execute(sql, params).fetchall()
    finally:
        db.close()


def fill(ledger):
    with ledger.tables() as tx:
        tx.insert('entries', {'entry_id': 'e1', 'who': 'ada', 'amount': 5, 'detail': {'for': 'tea'}})
        tx.insert('entries', {'entry_id': 'e2', 'who': 'bob', 'amount': 7, 'paid': True})
        tx.insert('entries', {'entry_id': 'e3', 'who': 'ada', 'amount': 2})
    with ledger.tables() as tx:
        tx.insert('notes', {'note_id': 'n1', 'text': 'first', 'at': '2026-10-02T08:00:00Z'})
        tx.insert('notes', {'note_id': 'n2', 'text': 'second', 'at': '2026-10-02T09:00:00Z'})


def test_a_module_writes_and_reads_its_tables_of_both_kinds_without_changing_the_chassis_layout(ledger):
    fill(ledger)
    with ledger.tables(write=False) as tx:
        assert tx.get('entries', {'entry_id': 'e1'}) == {'entry_id': 'e1', 'who': 'ada', 'amount': 5, 'paid': False,
                                                         'detail': {'for': 'tea'}}
        assert [row['entry_id'] for row in tx.rows('entries', {'who': 'ada'}).results] == ['e1', 'e3']
        assert tx.get('entries', {'entry_id': 'e2'})['paid'] is True
    with ledger.tables(write=False) as tx:
        assert [row['text'] for row in tx.rows('notes', limit=0).results] == ['first', 'second']
    with ledger.tables() as tx:
        changed = tx.update('entries', {'entry_id': 'e3'}, {'amount': 3, 'paid': True})
        assert changed is not None and changed['amount'] == 3
        assert tx.delete('entries', {'who': 'bob'}) == 1
    with ledger.tables(write=False) as tx:
        assert [(row['entry_id'], row['amount']) for row in tx.rows('entries', limit=0).results] == [('e1', 5),
                                                                                                    ('e3', 3)]
    path = store_file()
    assert raw(path, "SELECT value FROM meta WHERE key='schema_version'") == [(SCHEMA_VERSION,)]
    recorded = json.loads(raw(path, "SELECT value FROM meta WHERE key='module:ledger'")[0][0])
    assert recorded['version'] == 1 and [table['name'] for table in recorded['tables']] == ['entries']
    assert raw(path, 'SELECT entry_id FROM "ledger.entries" ORDER BY entry_id') == [('e1',), ('e3',)]
    assert 'ledger.notes' not in {row[0] for row in raw(path, "SELECT name FROM sqlite_master WHERE type='table'")}
    assert raw(project_store(), 'SELECT note_id FROM "ledger.notes" ORDER BY note_id') == [('n1',), ('n2',)]


def test_reads_page_through_the_index_they_are_answered_by(ledger):
    with ledger.tables() as tx:
        for number in range(5):
            tx.insert('entries', {'entry_id': f'e{number}', 'who': 'ada', 'amount': number})
    with ledger.tables(write=False) as tx:
        first = tx.rows('entries', {'who': 'ada'}, limit=2)
        second = tx.rows('entries', {'who': 'ada'}, limit=2, after=first.next)
        third = tx.rows('entries', {'who': 'ada'}, limit=2, after=second.next)
    assert [row['entry_id'] for page in (first, second, third) for row in page.results] == \
        ['e0', 'e1', 'e2', 'e3', 'e4']
    assert third.next is None


def test_rows_read_in_the_order_of_the_index_named_by_its_leading_columns(ledger, traced):
    with ledger.tables() as tx:
        tx.insert('notes', {'note_id': 'a', 'text': 'later', 'at': '2026-10-02T09:00:00Z'})
        tx.insert('notes', {'note_id': 'b', 'text': 'sooner', 'at': '2026-10-02T08:00:00Z'})
        tx.insert('notes', {'note_id': 'c', 'text': 'latest', 'at': '2026-10-02T10:00:00Z'})
    del traced[:]
    with ledger.tables(write=False) as tx:
        first = tx.rows('notes', by=('at',), limit=2)
        second = tx.rows('notes', by=('at',), limit=2, after=first.next)
        with pytest.raises(StoreError):
            tx.rows('notes', by=('text',))
    assert [row['text'] for row in first.results + second.results] == ['sooner', 'later', 'latest']
    planned = [sql for sql in traced if '"ledger.notes"' in sql and not sql.startswith('PRAGMA')]  # reads of rows
    assert len(planned) >= 2
    db = sqlite3.connect(project_store())
    try:
        for sql in planned:
            assert any('INDEX "ledger.notes:at"' in row[3] or 'INDEX ledger.notes:at' in row[3]
                       for row in db.execute('EXPLAIN QUERY PLAN ' + sql)), sql
    finally:
        db.close()


def test_every_read_and_delete_is_planned_on_an_index_and_a_where_no_index_starts_with_is_refused(ledger, traced):
    fill(ledger)
    del traced[:]
    with ledger.tables() as tx:
        tx.get('entries', {'entry_id': 'e1'})
        tx.rows('entries', {'who': 'ada'}, limit=1)
        page = tx.rows('entries', limit=1)
        tx.rows('entries', limit=1, after=page.next)
        tx.update('entries', {'entry_id': 'e1'}, {'amount': 1})
        tx.delete('entries', {'who': 'bob'})
        with pytest.raises(StoreError) as refused:
            tx.rows('entries', {'amount': 5})
    assert 'who' in str(refused.value)
    statements = [sql for sql in traced if '"ledger.entries"' in sql and not sql.lstrip().startswith(
        ('CREATE', 'INSERT'))]
    assert len(statements) >= 6
    db = sqlite3.connect(store_file())
    try:
        for sql in statements:
            for line in (row[3] for row in db.execute('EXPLAIN QUERY PLAN ' + sql)):
                assert line.startswith(('SEARCH ', 'SCAN ')), (sql, line)
                assert line.startswith('SEARCH ') or ' USING ' in line and 'INDEX' in line, (sql, line)
    finally:
        db.close()


def test_one_transaction_reaches_one_store_and_a_write_that_raises_leaves_nothing(ledger):
    with pytest.raises(StoreError), ledger.tables() as tx:
        tx.insert('entries', {'entry_id': 'e1', 'who': 'ada'})
        tx.insert('notes', {'note_id': 'n1', 'text': 'x', 'at': 'now'})
    with pytest.raises(RuntimeError), ledger.tables() as tx:
        tx.insert('entries', {'entry_id': 'e2', 'who': 'ada'})
        raise RuntimeError('the module failed')
    with ledger.tables(write=False) as tx:
        assert tx.rows('entries', limit=0).results == ()
    with ledger.tables(write=False) as tx:
        assert tx.rows('notes', limit=0).results == ()


def test_a_metaform_level_table_joins_the_maps_transaction_inside_atomic(ledger):
    with pytest.raises(RuntimeError), ledger.atomic():
        ledger.layer('ledger.marks', 'ledger', 'Marks.', mutable=True, hideable=True,
                     provenance={'module': 'ledger'})
        with ledger.tables() as tx:
            tx.insert('entries', {'entry_id': 'e1', 'who': 'ada'})
        raise RuntimeError('undo both')
    assert not [layer for layer in ledger.layers(limit=0).results if layer.name == 'ledger.marks']
    with ledger.tables(write=False) as tx:
        assert tx.get('entries', {'entry_id': 'e1'}) is None


def test_raising_the_version_upgrades_the_tables_keeping_every_row_and_a_copy_first(ledger, home, user_module):
    fill(ledger)
    user_module('ledger', LEDGER_V2)
    loader.reset()
    upgraded = Store('proj', module='ledger')
    with upgraded.tables(write=False) as tx:
        assert [(row['entry_id'], row['currency']) for row in tx.rows('entries', {'currency': 'EUR'}).results] == \
            [('e1', 'EUR'), ('e3', 'EUR'), ('e2', 'EUR')]  # in the order of the new index: currency, who, key
        assert tx.get('entries', {'entry_id': 'e1'})['detail'] == {'for': 'tea'}
    with upgraded.tables(write=False) as tx:
        assert [row['text'] for row in tx.rows('notes', limit=0).results] == ['first', 'second']
    found = next(item for item in loader.discover() if item.id == 'ledger')
    import sys
    assert sys.modules[found.import_name].SEEN == [1, 1]  # once in each store that holds its tables
    assert json.loads(raw(store_file(), "SELECT value FROM meta WHERE key='module:ledger'")[0][0])['version'] == 2
    assert raw(store_file(), "SELECT value FROM meta WHERE key='schema_version'") == [(SCHEMA_VERSION,)]
    indexes = {row[0] for row in raw(store_file(), "SELECT name FROM sqlite_master WHERE type='index' "
                                                   "AND tbl_name='ledger.entries' AND sql IS NOT NULL")}
    assert indexes == {'ledger.entries:who', 'ledger.entries:currency+who'}
    copies = list((home / 'backups').glob('module-ledger-2/*/*/*.sqlite3'))
    assert len(copies) == 2
    kept = next(path for path in copies if path.name.endswith('.metaform.sqlite3'))
    assert json.loads(raw(kept, "SELECT value FROM meta WHERE key='module:ledger'")[0][0])['version'] == 1


def test_a_store_at_a_later_version_is_refused_and_left_unchanged(ledger, user_module):
    fill(ledger)
    user_module('ledger', LEDGER_V2)
    loader.reset()
    with Store('proj', module='ledger').tables(write=False) as tx:
        tx.rows('entries', limit=0)
    with Store('proj', module='ledger').tables(write=False) as tx:
        tx.rows('notes', limit=0)
    user_module('ledger', LEDGER_V1)
    loader.reset()
    before = raw(store_file(), 'SELECT * FROM "ledger.entries" ORDER BY entry_id')
    recorded = raw(store_file(), "SELECT value FROM meta WHERE key='module:ledger'")
    with pytest.raises(StoreError) as refused, Store('proj', module='ledger').tables() as tx:
        tx.insert('entries', {'entry_id': 'e9', 'who': 'eve'})
    assert str(refused.value) == ('The store holds the tables of ledger at version 2, which ledger reads from '
                                  'version 2; this ledger declares version 1.')
    assert raw(store_file(), 'SELECT * FROM "ledger.entries" ORDER BY entry_id') == before
    assert raw(store_file(), "SELECT value FROM meta WHERE key='module:ledger'") == recorded
    with pytest.raises(StoreError), Store('proj', module='ledger').tables() as tx:
        tx.insert('notes', {'note_id': 'n9', 'text': 'x', 'at': 'now'})
    assert raw(project_store(), 'SELECT note_id FROM "ledger.notes" ORDER BY note_id') == [('n1',), ('n2',)]



@pytest.mark.req('STORE-029')
def test_tables_at_a_later_version_compatible_with_this_one_are_read_and_written_as_held(ledger, user_module):
    fill(ledger)
    user_module('ledger', LEDGER_V2.replace('Tables(version=2,', 'Tables(version=2, compatible_from=1,'))
    loader.reset()
    with Store('proj', module='ledger').tables(write=False) as tx:
        tx.rows('entries', limit=0)
    user_module('ledger', LEDGER_V1)
    loader.reset()
    recorded = raw(store_file(), "SELECT value FROM meta WHERE key='module:ledger'")
    assert json.loads(recorded[0][0])['version'] == 2 and json.loads(recorded[0][0])['compatible_from'] == 1
    with Store('proj', module='ledger').tables() as tx:
        tx.insert('entries', {'entry_id': 'e9', 'who': 'eve'})
        assert tx.get('entries', {'entry_id': 'e1'})['amount'] == 5
    assert raw(store_file(), "SELECT value FROM meta WHERE key='module:ledger'") == recorded
    assert raw(store_file(), 'SELECT entry_id, currency FROM "ledger.entries" ORDER BY entry_id') == [
        ('e1', 'EUR'), ('e2', 'EUR'), ('e3', 'EUR'), ('e9', None)]

def test_export_import_export_carries_the_module_rows_and_importing_again_adds_none(ledger, monkeypatch, tmp_path):
    fill(ledger)
    first = export_document(['proj'])
    assert [entry['module'] for entry in first['projects'][0]['bases'][0]['modules']] == ['ledger']
    assert [entry['module'] for entry in first['projects'][0]['modules']] == ['ledger']
    monkeypatch.setenv('METAFORM_HOME', str(tmp_path / 'other-home'))
    report = import_document(json.loads(json.dumps(first)))
    assert report['things_added'] == 5
    assert export_document(['proj']) == first
    again = import_document(json.loads(json.dumps(first)))
    assert again['things_added'] == 0 and again['things_skipped'] == 5
    assert export_document(['proj']) == first


def test_a_document_with_no_module_tables_has_no_modules_list(store):
    from metaform.data import Node
    store.add_work(Node('element', 'code.anything'), 'unbuilt', task='x')
    document = export_document(['proj'])
    assert 'modules' not in document['projects'][0]
    assert 'modules' not in document['projects'][0]['bases'][0]


def test_importing_a_module_held_at_another_version_adds_nothing_of_it_and_says_so(ledger, user_module):
    fill(ledger)
    document = export_document(['proj'])
    user_module('ledger', LEDGER_V2)
    loader.reset()
    with Store('proj', module='ledger').tables(write=False) as tx:
        tx.rows('entries', limit=0)
    document['projects'][0]['bases'][0]['modules'][0]['rows']['entries'].append(
        {'entry_id': 'e9', 'who': 'eve', 'amount': None, 'paid': 0, 'detail': None})
    report = import_document(document)
    assert any('ledger' in notice['message'] and '1' in notice['message'] and '2' in notice['message']
               for notice in report['notices'])
    with Store('proj', module='ledger').tables(write=False) as tx:
        assert tx.get('entries', {'entry_id': 'e9'}) is None


def test_clear_removes_the_metaform_level_rows_keeps_the_project_level_ones_and_restore_brings_them_back(ledger):
    fill(ledger)
    cleared = metaform_home.clear_project('proj')
    assert cleared.backup is not None
    with ledger.tables(write=False) as tx:
        assert tx.rows('entries', limit=0).results == ()
    with ledger.tables(write=False) as tx:
        assert [row['note_id'] for row in tx.rows('notes', limit=0).results] == ['n1', 'n2']
    kept = metaform_home.home() / 'backups' / 'clear' / 'proj' / cleared.backup
    assert (kept / 'modules' / 'ledger.sqlite3').is_file()
    with ledger.tables() as tx:
        tx.insert('notes', {'note_id': 'n3', 'text': 'after the clear', 'at': '2026-10-02T10:00:00Z'})
    metaform_home.restore_project('proj', cleared.backup)
    restored = Store('proj', module='ledger')
    with restored.tables(write=False) as tx:
        assert [row['entry_id'] for row in tx.rows('entries', limit=0).results] == ['e1', 'e2', 'e3']
    with restored.tables(write=False) as tx:
        assert [row['note_id'] for row in tx.rows('notes', limit=0).results] == ['n1', 'n2', 'n3']


def test_the_chassis_upgrade_of_its_layout_keeps_a_module_table(ledger):
    fill(ledger)
    path = store_file()
    db = sqlite3.connect(path)
    db.execute("UPDATE meta SET value='9' WHERE key='schema_version'")
    db.commit()
    db.close()
    with Store('proj', module='ledger').tables(write=False) as tx:
        assert [row['entry_id'] for row in tx.rows('entries', limit=0).results] == ['e1', 'e2', 'e3']
    assert raw(path, "SELECT value FROM meta WHERE key='schema_version'") == [(SCHEMA_VERSION,)]


def test_a_store_for_no_module_is_told_to_use_the_modules_own_store(store):
    with pytest.raises(StoreError) as refused, store.tables() as tx:
        tx.rows('entries')
    assert str(refused.value) == "This store works for no module, so it reaches no module's tables."


def test_a_module_that_declares_no_tables_is_told_how_to_declare_them(home, project_folder, user_module):
    user_module('plain', """
        from metaform.module import Module
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        MODULE = Module(id='plain', summary='Plain.', purpose='Plain. Details: metaform help plain.')
    """)
    loader.reset()
    try:
        with pytest.raises(StoreError) as refused, Store('proj', module='plain').tables() as tx:
            tx.rows('entries')
        assert str(refused.value) == 'plain declares no tables.'
        assert 'Tables(' in refused.value.next_step
    finally:
        loader.reset()


def test_a_where_that_gives_the_whole_key_reads_that_one_row(ledger):
    fill(ledger)
    with ledger.tables(write=False) as tx:
        page = tx.rows('entries', {'entry_id': 'e2'}, limit=1)
        assert [row['who'] for row in page.results] == ['bob'] and page.next is None
        assert tx.rows('entries', {'entry_id': 'e9'}).results == ()


def test_a_delete_names_the_rows_it_deletes(ledger):
    fill(ledger)
    with pytest.raises(StoreError), ledger.tables() as tx:
        tx.delete('entries', {})
    with ledger.tables(write=False) as tx:
        assert len(tx.rows('entries', limit=0).results) == 3


LEDGER_CHANGED_AT_V1 = LEDGER_V1.replace("Column('detail', 'json')),", "Column('detail', 'json'), Column('extra')),")
LEDGER_V3_WITHOUT_ENTRIES = """
    from metaform.data import Column, Index, Table, Tables
    from metaform.module import Module
    SUPPORTED_OS = ('linux', 'macos', 'windows')
    TABLES = Tables(version=3, tables=(
        Table('payments', place='metaform', key=('payment_id',), columns=(Column('payment_id', required=True),)),
        Table('notes', place='project', key=('note_id',),
              columns=(Column('note_id', required=True), Column('text', required=True), Column('at', required=True)),
              indexes=(Index(('at',)),)),
    ))
    MODULE = Module(id='ledger', summary='Ledger.', purpose='Keeps a ledger. Details: metaform help ledger.',
                    tables=TABLES)
"""


@pytest.mark.req('STORE-029')
def test_a_column_added_at_the_same_version_is_added_in_place_keeping_every_row(ledger, user_module):
    """Ticket 03f869a0: compatibility follows the real schema. A declaration that only adds a column that may be
    empty opens the store with no refusal, whatever the version says, adds the column in place and records it."""
    fill(ledger)
    user_module('ledger', LEDGER_CHANGED_AT_V1)
    loader.reset()
    with Store('proj', module='ledger').tables(write=False) as tx:
        assert [(row['entry_id'], row['extra']) for row in tx.rows('entries', limit=0).results] == [
            ('e1', None), ('e2', None), ('e3', None)]
    assert raw(store_file(), 'SELECT entry_id, amount FROM "ledger.entries" ORDER BY entry_id') == [
        ('e1', 5), ('e2', 7), ('e3', 2)]
    recorded = json.loads(raw(store_file(), "SELECT value FROM meta WHERE key='module:ledger'")[0][0])
    assert recorded['version'] == 1 and ['extra', 'text', False, None] in recorded['tables'][0]['columns']
    assert not (metaform_home.home() / 'backups').exists() or not list(
        (metaform_home.home() / 'backups').glob('module-ledger-*'))  # an addition rewrites nothing, so no copy


@pytest.mark.req('STORE-029')
def test_a_declaration_reordered_with_the_same_schema_opens_with_no_change(ledger, user_module):
    fill(ledger)
    before = raw(store_file(), "SELECT sql FROM sqlite_master WHERE name LIKE 'ledger.%' ORDER BY name")
    user_module('ledger', LEDGER_V1.replace(  # a comment too, so the file's size changes and its bytecode is not reused
        "columns=(Column('entry_id', required=True), Column('who', required=True), Column('amount', 'int'),",
        "columns=(Column('who', required=True), Column('entry_id', required=True), Column('amount', 'int'),") + '    # reordered\n')
    loader.reset()
    with Store('proj', module='ledger').tables() as tx:
        assert tx.get('entries', {'entry_id': 'e1'})['who'] == 'ada'
    assert raw(store_file(), "SELECT sql FROM sqlite_master WHERE name LIKE 'ledger.%' ORDER BY name") == before


LEDGER_KEY_RETYPED_AT_V1 = LEDGER_V1.replace("Column('entry_id', required=True)", "Column('entry_id', 'int', required=True)")


@pytest.mark.req('STORE-029')
def test_a_real_conflict_is_refused_for_that_module_alone_and_changes_nothing(ledger, user_module, store):
    fill(ledger)
    user_module('ledger', LEDGER_KEY_RETYPED_AT_V1)
    loader.reset()
    recorded = raw(store_file(), "SELECT value FROM meta WHERE key='module:ledger'")
    with pytest.raises(StoreError) as refused, Store('proj', module='ledger').tables(write=False) as tx:
        tx.rows('entries', limit=0)
    assert str(refused.value) == ('The tables of ledger this store holds conflict with what this ledger needs: '
                                  'entries.entry_id is held as TEXT and ledger declares it INTEGER. Nothing of ledger '
                                  'was changed, and the rest of Metaform works as before.')
    assert refused.value.next_step == "raise the version of ledger's Tables to 2, so its upgrade rebuilds entries " \
                                      'keeping every row'
    assert raw(store_file(), "SELECT value FROM meta WHERE key='module:ledger'") == recorded
    from metaform.data import Node
    store.add_work(Node('element', 'code.anything'), 'unbuilt', task='the map still writes')
    assert [work.task for work in store.work(Node('element', 'code.anything')).results] == ['the map still writes']


MARKS_V1 = '''
    from metaform.data import Table, Tables
    from metaform.module import Module
    SUPPORTED_OS = ('linux', 'macos', 'windows')
    MODULE = Module(id='marks', summary='Marks.', purpose='Keeps marks. Details: metaform help marks.',
                    tables=Tables(version=1, tables=(Table.from_sql('marks', """
        CREATE TABLE IF NOT EXISTS marks(mark_id TEXT PRIMARY KEY, n INTEGER);"""),)))
'''


@pytest.mark.req('STORE-029')
def test_a_conflict_in_a_table_every_store_opening_prepares_leaves_the_map_working(home, project_folder, store,
                                                                                    user_module):
    """A table declared by its SQL is prepared whenever any store opens; its conflict must stop only its module."""
    from metaform.data import Node
    user_module('marks', MARKS_V1)
    loader.reset()
    with Store('proj', module='marks').tables() as tx:
        tx.insert('marks', {'mark_id': 'm1', 'n': 1})
    user_module('marks', MARKS_V1.replace('mark_id TEXT PRIMARY KEY', 'mark_id INTEGER PRIMARY KEY'))
    loader.reset()
    try:
        store.add_work(Node('element', 'code.anything'), 'unbuilt', task='the map opens')
        assert [work.task for work in store.work(Node('element', 'code.anything')).results] == ['the map opens']
        with pytest.raises(StoreError) as refused, Store('proj', module='marks').tables(write=False) as tx:
            tx.rows('marks', limit=0)
        assert 'marks.mark_id is held as TEXT and marks declares it INTEGER' in str(refused.value)
        assert raw(store_file(), 'SELECT mark_id, n FROM marks') == [('m1', 1)]
    finally:
        loader.reset()


MARKS_RULES = '''
    from metaform.data import Table, Tables
    from metaform.module import Module
    SUPPORTED_OS = ('linux', 'macos', 'windows')
    MODULE = Module(id='marks', summary='Marks.', purpose='Keeps marks. Details: metaform help marks.',
                    tables=Tables(version=VERSION, tables=(Table.from_sql('marks', """SCHEMA"""),)))
'''
MARKS_SCHEMA = ("CREATE TABLE IF NOT EXISTS marks(mark_id TEXT PRIMARY KEY, state TEXT CHECK(state IN ('A','B')), "
                'parent TEXT REFERENCES marks(mark_id), done TEXT); '
                'CREATE UNIQUE INDEX IF NOT EXISTS marks_one ON marks(parent) WHERE done IS NULL;')


def marks(schema=MARKS_SCHEMA, version=1):
    return MARKS_RULES.replace('VERSION', str(version)).replace('SCHEMA', schema)


@pytest.mark.req('STORE-029')
@pytest.mark.parametrize('held, declared, said', [
    ("('A','B')", "('A','B','C')", ("marks's CHECK constraints are held as state in ('A', 'B') and marks declares "
                                    "state in ('A', 'B', 'C')")),
    ('REFERENCES marks(mark_id)', 'REFERENCES marks(mark_id) ON DELETE CASCADE',
     ("marks's foreign keys are held as parent references marks(mark_id) on update NO ACTION on delete NO ACTION and "
      'marks declares parent references marks(mark_id) on update NO ACTION on delete CASCADE')),
    ('done TEXT);', 'done TEXT UNIQUE);', 'marks lacks'),  # the store lacks a unique rule: added in place, below
    ('WHERE done IS NULL', 'WHERE done IS NOT NULL', ('marks holds a unique index on parent where done is null that '
                                                      'marks does not declare')),
], ids=['check', 'foreign-key', 'unique-added', 'partial-condition'])
def test_a_rule_a_write_meets_changed_at_the_same_version_is_refused_for_that_module_alone(
        home, project_folder, store, user_module, held, declared, said):
    """Ticket 13b34894: a CHECK, a foreign key or a unique index's condition is part of what the code needs of its
    table. A store that holds another is refused at open for that module alone, as before 03f869a0, never opened and
    then failed at its first write; the map still writes. A unique rule the store only lacks is added in place."""
    from metaform.data import Node
    user_module('marks', marks())
    loader.reset()
    try:
        with Store('proj', module='marks').tables() as tx:
            tx.insert('marks', {'mark_id': 'm1', 'state': 'A'})
        user_module('marks', marks(MARKS_SCHEMA.replace(held, declared)))
        loader.reset()
        before = raw(store_file(), "SELECT name, sql FROM sqlite_master WHERE tbl_name='marks' ORDER BY name")
        store.add_work(Node('element', 'code.anything'), 'unbuilt', task='the map writes')
        if said == 'marks lacks':
            with Store('proj', module='marks').tables() as tx:
                tx.insert('marks', {'mark_id': 'm2', 'state': 'B', 'done': 'x'})
                with pytest.raises(StoreError, match='UNIQUE constraint failed'):
                    tx.insert('marks', {'mark_id': 'm3', 'state': 'B', 'done': 'x'})
            return
        with pytest.raises(StoreError) as refused, Store('proj', module='marks').tables(write=False) as tx:
            tx.rows('marks', limit=0)
        assert said in str(refused.value)
        assert raw(store_file(), "SELECT name, sql FROM sqlite_master WHERE tbl_name='marks' ORDER BY name") == before
        assert raw(store_file(), 'SELECT mark_id, state FROM marks') == [('m1', 'A')]
        assert [work.task for work in store.work(Node('element', 'code.anything')).results] == ['the map writes']
    finally:
        loader.reset()


@pytest.mark.req('STORE-029')
def test_a_check_widened_with_the_version_raised_rebuilds_the_table_keeping_every_row(home, project_folder,
                                                                                       user_module):
    """Ticket 13b34894: raising the version for a CHECK change rebuilds the table, as it did before 03f869a0, so the
    record and the table agree and the new value is accepted."""
    user_module('marks', marks())
    loader.reset()
    try:
        with Store('proj', module='marks').tables() as tx:
            tx.insert('marks', {'mark_id': 'm1', 'state': 'A'})
            tx.insert('marks', {'mark_id': 'm2', 'state': 'B', 'parent': 'm1'})
        user_module('marks', marks(MARKS_SCHEMA.replace("('A','B')", "('A','B','C')"), version=2))
        loader.reset()
        with Store('proj', module='marks').tables() as tx:
            tx.insert('marks', {'mark_id': 'm3', 'state': 'C'})
        assert raw(store_file(), 'SELECT mark_id, state, parent FROM marks ORDER BY mark_id') == [
            ('m1', 'A', None), ('m2', 'B', 'm1'), ('m3', 'C', None)]
        assert "'C'" in raw(store_file(), "SELECT sql FROM sqlite_master WHERE name='marks'")[0][0]
        assert raw(store_file(), "SELECT name FROM sqlite_master WHERE name='marks_one'") == [('marks_one',)]
        assert json.loads(raw(store_file(), "SELECT value FROM meta WHERE key='module:marks'")[0][0])['version'] == 2
        assert list((metaform_home.home() / 'backups').glob('module-marks-2'))
    finally:
        loader.reset()


@pytest.mark.req('STORE-029')
def test_the_same_rules_written_differently_open_the_store_as_it_is(home, project_folder, user_module):
    """Ticket 13b34894: the rules are compared as SQLite applies them, so a declaration re-cased, re-quoted,
    re-spaced or commented opens the store with its tables untouched and no copy kept."""
    user_module('marks', marks())
    loader.reset()
    try:
        with Store('proj', module='marks').tables() as tx:
            tx.insert('marks', {'mark_id': 'm1', 'state': 'A'})
        before = raw(store_file(), "SELECT name, sql FROM sqlite_master WHERE tbl_name='marks' ORDER BY name")
        user_module('marks', marks(
            'create table if not exists "marks"( "mark_id" text primary key, /* the same rules */ '
            'state TEXT check ( "state"  in ( \'A\' , \'B\' ) ), parent text references [marks] ( mark_id ), '
            'done TEXT ) ; create unique index if not exists marks_one on marks ( parent ) where "done" is NULL ;'))
        loader.reset()
        with Store('proj', module='marks').tables() as tx:
            assert tx.get('marks', {'mark_id': 'm1'})['state'] == 'A'
        assert raw(store_file(), "SELECT name, sql FROM sqlite_master WHERE tbl_name='marks' ORDER BY name") == before
        assert not list((metaform_home.home() / 'backups').glob('module-marks-*'))
    finally:
        loader.reset()


@pytest.mark.req('STORE-029')
def test_two_declarations_at_one_version_and_a_later_one_each_open_a_store_and_add_what_it_lacks(ledger,
                                                                                                user_module):
    """Two fixers each called their change version 1 of ledger; the store's record names one, its real tables hold
    the other's column. A third declaration at version 2 holds both and a new table. Each opens the store; none
    loses a row or the column the record never named."""
    fill(ledger)
    path = store_file()
    db = sqlite3.connect(path)
    db.execute('ALTER TABLE "ledger.entries" ADD COLUMN "theirs" TEXT')
    db.execute('UPDATE "ledger.entries" SET theirs=\'kept\'')
    db.commit()
    db.close()
    ours = LEDGER_V1.replace("Column('detail', 'json')),", "Column('detail', 'json'), Column('ours')),")
    user_module('ledger', ours)
    loader.reset()
    with Store('proj', module='ledger').tables() as tx:
        tx.update('entries', {'entry_id': 'e1'}, {'ours': 'mine'})
    later = ours.replace('version=1', 'version=2').replace("Column('ours')),", "Column('ours'), Column('theirs')),") \
        .replace("    ))\n    MODULE", "        Table('payments', place='metaform', key=('payment_id',), "
                                      "columns=(Column('payment_id', required=True),)),\n    ))\n    MODULE")
    user_module('ledger', later)
    loader.reset()
    with Store('proj', module='ledger').tables() as tx:
        tx.insert('payments', {'payment_id': 'p1'})
        assert [(row['entry_id'], row['ours'], row['theirs']) for row in tx.rows('entries', limit=0).results] == [
            ('e1', 'mine', 'kept'), ('e2', None, 'kept'), ('e3', None, 'kept')]
    assert json.loads(raw(path, "SELECT value FROM meta WHERE key='module:ledger'")[0][0])['version'] == 2


def test_a_table_the_new_version_no_longer_declares_is_dropped_after_its_copy_is_kept(ledger, user_module):
    fill(ledger)
    user_module('ledger', LEDGER_V3_WITHOUT_ENTRIES)
    loader.reset()
    with Store('proj', module='ledger').tables() as tx:
        tx.insert('payments', {'payment_id': 'p1'})
    tables = {row[0] for row in raw(store_file(), "SELECT name FROM sqlite_master WHERE type='table'")}
    assert 'ledger.entries' not in tables and 'ledger.payments' in tables


LEDGER_V2_CENTS = '''
    from metaform.data import Column, Index, Table, Tables
    from metaform.module import Module
    SUPPORTED_OS = ('linux', 'macos', 'windows')
    FOUND = []
    PAGED = []
    def upgrade(tx, found):
        if tx.place != 'metaform':
            return
        rows = tx.found_rows('entries', limit=0).results
        FOUND.extend(rows)
        first = tx.found_rows('entries', limit=2)
        PAGED.extend(first.results + tx.found_rows('entries', limit=2, after=first.next).results)
        for row in rows:
            tx.update('entries', {'entry_id': row['entry_id']}, {'cents': row['amount'] * 100})
    TABLES = Tables(version=2, upgrade=upgrade, tables=(
        Table('entries', place='metaform', key=('entry_id',),
              columns=(Column('entry_id', required=True), Column('who', required=True),
                       Column('paid', 'bool', default=False), Column('detail', 'json'), Column('cents', 'int')),
              indexes=(Index(('who',)),)),
        Table('notes', place='project', key=('note_id',),
              columns=(Column('note_id', required=True), Column('text', required=True), Column('at', required=True)),
              indexes=(Index(('at',)),)),
    ))
    MODULE = Module(id='ledger', summary='Ledger.', purpose='Keeps a ledger. Details: metaform help ledger.',
                    tables=TABLES)
'''


def test_an_upgrade_reads_a_column_its_new_version_drops_and_carries_it_into_a_new_one(ledger, user_module):
    """Ticket 823465c9: the module's upgrade reads the rows as the version found held them, a dropped column
    included, and carries what it held into a new column before the column goes."""
    fill(ledger)
    user_module('ledger', LEDGER_V2_CENTS)
    loader.reset()
    with Store('proj', module='ledger').tables(write=False) as tx:
        assert [(row['entry_id'], row['cents']) for row in tx.rows('entries', limit=0).results] == \
            [('e1', 500), ('e2', 700), ('e3', 200)]
        with pytest.raises(StoreError):  # only an upgrade reads the rows as the version found held them
            tx.found_rows('entries')
    found = next(item for item in loader.discover() if item.id == 'ledger')
    import sys
    assert sys.modules[found.import_name].FOUND == [
        {'entry_id': 'e1', 'who': 'ada', 'amount': 5, 'paid': False, 'detail': {'for': 'tea'}},
        {'entry_id': 'e2', 'who': 'bob', 'amount': 7, 'paid': True, 'detail': None},
        {'entry_id': 'e3', 'who': 'ada', 'amount': 2, 'paid': False, 'detail': None}]  # in the found key's order
    assert sys.modules[found.import_name].PAGED == sys.modules[found.import_name].FOUND  # a page at a time, STORE-025
    assert [row[1] for row in raw(store_file(), 'PRAGMA table_info("ledger.entries")')] == \
        ['entry_id', 'who', 'paid', 'detail', 'cents']
    tables = {row[0] for row in raw(store_file(), "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {name for name in tables if name.startswith('ledger.')} == {'ledger.entries'}


def test_an_upgrade_that_cannot_keep_the_rows_is_refused_and_changes_nothing(ledger, user_module):
    fill(ledger)
    user_module('ledger', LEDGER_V1.replace('version=1', 'version=2').replace(
        "Column('detail', 'json')),", "Column('detail', 'json'), Column('owner', required=True)),"))
    loader.reset()
    with pytest.raises(StoreError), Store('proj', module='ledger').tables() as tx:
        tx.rows('entries', limit=0)
    assert json.loads(raw(store_file(), "SELECT value FROM meta WHERE key='module:ledger'")[0][0])['version'] == 1
    assert raw(store_file(), 'SELECT entry_id FROM "ledger.entries" ORDER BY entry_id') == [('e1',), ('e2',), ('e3',)]


def test_the_declaration_refuses_names_that_are_not_plain_and_a_key_it_does_not_hold():
    from metaform.data import Column, Index, Table, Tables
    with pytest.raises(ValueError):
        Table('Bad-name', columns=(Column('a'),), key=('a',))
    with pytest.raises(ValueError):
        Table('t', columns=(Column('a'),), key=('b',))
    with pytest.raises(ValueError):
        Table('t', columns=(Column('a'),), key=('a',), indexes=(Index(('c',)),))
    with pytest.raises(ValueError):
        Table('t', columns=(Column('a', 'decimal'),), key=('a',))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Tables(version=0, tables=())


# ------------------------------------------------------------------------------------------------ the schema guard

SNAPSHOT = Path(__file__).with_name('module_tables.snapshot.json')


def declared_schemas():
    """Every shipped module's tables as SQLite would hold them, by module: the version, compatible_from and, for each
    table, its place, key, columns (by name: kind, SQL type, NOT NULL, default), indexes (unique, each column with
    its order and collation, partial condition) and every rule a write meets: CHECK clauses, foreign keys,
    collations, ON CONFLICT resolutions and generated columns. A declaration reordered, reworded or moved into a
    constant reads the same; a change to what the database holds does not."""
    from metaform.data import tables as module_tables
    for found in loader.discover():
        loader.set_enabled(found.id, True)
    schemas = {}
    for found in loader.discover():
        assert not found.problem and found.module is not None, (found.id, found.problem)
        declared = found.module.tables
        if declared is None and found.declared is not None and found.declared.data_source:
            declared = getattr(loader.data_source(found.id), 'TABLES', None)
        if declared is None:
            schemas[found.id] = None
            continue
        held = {}
        for table in declared.tables:
            db = sqlite3.connect(':memory:')
            try:
                module_tables._create(db, found.id, table)
                name = module_tables.physical(found.id, table)
                columns = {str(row[1]): [table.column(str(row[1])).kind, str(row[2]).upper(), bool(row[3]), row[4]]
                           for row in db.execute(f'PRAGMA table_info("{name}")')}
                shape = module_tables._shape(db, name)
            finally:
                db.close()
            assert shape is not None
            held[table.name] = {
                'place': table.place, 'key': list(table.key), 'columns': dict(sorted(columns.items())),
                'indexes': sorted([unique, [list(column) for column in held_columns], where]
                                  for unique, held_columns, where in shape.indexes),
                'checks': list(shape.checks), 'foreign_keys': [json.loads(json.dumps(key)) for key in shape.foreign_keys],
                'collations': {column: collation for column, collation in sorted(shape.collations.items())
                               if collation != 'BINARY'},
                'on_conflict': [list(resolution) for resolution in shape.resolutions],
                'generated': sorted(shape.generated)}
        schemas[found.id] = {'version': declared.version, 'compatible_from': declared.oldest,
                             'tables': dict(sorted(held.items()))}
    return dict(sorted(schemas.items()))


def schema_changes(before, after):
    """What changed between two snapshots, one line per module, saying whether its version was raised."""
    lines = []
    for module in sorted(set(before) | set(after)):
        old, new = before.get(module), after.get(module)
        if old == new:
            continue
        if old is None or new is None:
            lines.append(f'{module}: {"declares tables now" if old is None else "no longer declares tables"}')
            continue
        said = []
        for table in sorted(set(old['tables']) | set(new['tables'])):
            was, now = old['tables'].get(table), new['tables'].get(table)
            if was is None or now is None:
                said.append(f'table {table} {"added" if was is None else "removed"}')
                continue
            for column in sorted(set(was['columns']) | set(now['columns'])):
                a, b = was['columns'].get(column), now['columns'].get(column)
                if a != b:
                    said.append(f'{table}.{column} ' + ('added' if a is None else 'removed' if b is None else
                                                        f'changed from {a} to {b}'))
            for field in ('place', 'key', 'indexes', 'checks', 'foreign_keys', 'collations', 'on_conflict',
                          'generated'):
                if was.get(field) != now.get(field):
                    said.append(f'{table} {field} changed from {was[field]} to {now[field]}')
        bumped = (f'version raised from {old["version"]} to {new["version"]}' if new['version'] > old['version'] else
                  f'version NOT raised, still {new["version"]}')
        if old['compatible_from'] != new['compatible_from']:
            said.append(f'compatible_from changed from {old["compatible_from"]} to {new["compatible_from"]}')
        lines.append(f'{module}: {"; ".join(said) or "the declaration changed"}; {bumped}')
    return lines


@pytest.mark.req('STORE-029')
def test_no_module_changes_its_tables_without_the_snapshot_saying_so(home):
    """The guard against unneeded schema changes, ticket 03f869a0: every shipped module's tables are compared with
    the committed snapshot. A change the ticket's own task requires raises the module's version once and updates the
    snapshot in the same commit, METAFORM_TABLES_SNAPSHOT=write; any other change fails here, naming the module."""
    try:
        now = declared_schemas()
    finally:
        loader.reset()
    if os.environ.get('METAFORM_TABLES_SNAPSHOT') == 'write':
        SNAPSHOT.write_text(json.dumps(now, indent=1) + '\n', encoding='utf-8')
    committed = json.loads(SNAPSHOT.read_text(encoding='utf-8'))
    changes = schema_changes(committed, now)
    assert not changes, (
        'Module tables differ from tests/module_tables.snapshot.json:\n  ' + '\n  '.join(changes) + '\nNo module '
        'changes its tables, columns or keys unless its ticket\'s task requires it (AGENTS.md). If it does: raise the '
        'version once, say why in the Tables comment and the ticket, and update the snapshot in the same commit with '
        'METAFORM_TABLES_SNAPSHOT=write uv run pytest -n 0 tests/test_module_tables.py -k snapshot')
