"""Module data callbacks and operations use the owner's tables through the DAO."""
from types import SimpleNamespace

import pytest

from metaform.data import Column, Data, Element, Node, Operation, Store, Table, Tables
from metaform.module import Module

pytestmark = [pytest.mark.req('STORE-045'), pytest.mark.req('BASE-046'), pytest.mark.kind('fixture')]


@pytest.fixture
def declare(monkeypatch):
    from metaform import loader

    declared = []
    original = loader.get
    monkeypatch.setattr(loader, 'enabled', lambda: declared)
    monkeypatch.setattr(loader, 'get', lambda name: SimpleNamespace(module=declared[0]) if name == 'demo'
                        else original(name))

    def install(data, *, version=1, extra=()):
        tables = Tables(version, (Table('counts', key=('name',), columns=(
            Column('name', required=True), Column('times', 'int', required=True), *extra)),))
        module = Module(id='demo', summary='Fixture.', purpose='Fixture.', data=data, tables=tables)
        declared[:] = [module]
        return module
    return install


@pytest.mark.parametrize('callback', ['decorate', 'cleanup', 'item_write'])
def test_data_callbacks_use_their_owners_tables(store, declare, callback):
    observed = []

    def hook(tx, *args):
        if callback == 'decorate' and not isinstance(args[0], Element):
            return args[0]
        if callback == 'cleanup' and args[0] != 'layer':
            return None
        row = tx.tables().get('counts', {'name': 'owned'})
        observed.append(row['times'])
        return args[0] if callback == 'decorate' else None

    declare(Data(**{callback: hook}))
    with Store('proj', module='demo').tables() as tx:
        tx.insert('counts', {'name': 'owned', 'times': 7})
    layer = store.layer('knowledge', 'demo', 'Facts.', mutable=True, hideable=True)
    element = store.add_element(layer.name, 'code.root', name_length=1, role='DE')
    if callback == 'decorate':
        observed.clear()
        assert store.element(element.element_id, raw=True).element_id == element.element_id
    elif callback == 'cleanup':
        store.discard(layer.name)
    else:
        store.add_item(layer.name, Node('element', element.element_id), 'An answer.')
    assert observed == [7]


def test_read_data_operation_upgrades_existing_tables_without_hiding_rows(store, declare, home):
    def read_count(tx):
        return tx.tables().get('counts', {'name': 'owned'})

    data = Data(operations={'read_count': Operation(read_count)})
    declare(data)
    with Store('proj', module='demo').tables() as tx:
        tx.insert('counts', {'name': 'owned', 'times': 7})
    declare(data, version=2, extra=(Column('label'),))
    assert store.read_count() == {'name': 'owned', 'times': 7, 'label': None}
    assert list((home / 'backups' / 'module-demo-2').rglob('*.sqlite3'))


def test_read_data_operation_keeps_absent_regular_tables_absent(store, declare):
    def read_count(tx):
        return tx.tables().get('counts', {'name': 'owned'})

    declare(Data(operations={'read_count': Operation(read_count)}))
    assert store.read_count() is None
    assert store.active_metaform() is None
