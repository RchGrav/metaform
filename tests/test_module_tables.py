"""A module declares its own tables and reaches them through the data access object, STORE-045.

The chassis creates them, versions them with the module's own version, upgrades them, and carries them through
backup, export, import and clear by their kind: a metaform-level table goes with its metaform, a project-level one
outlives a clear. The module reads and writes them inside a transaction the data access object gives it.
"""
from __future__ import annotations

import json
import sqlite3

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
    planned = [sql for sql in traced if '"ledger.notes"' in sql]
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


def test_tables_changed_at_the_same_version_are_refused_with_the_next_step_to_raise_it(ledger, user_module):
    fill(ledger)
    user_module('ledger', LEDGER_CHANGED_AT_V1)
    loader.reset()
    with pytest.raises(StoreError) as refused, Store('proj', module='ledger').tables(write=False) as tx:
        tx.rows('entries', limit=0)
    assert refused.value.next_step == "raise the version of ledger's Tables to 2"


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
