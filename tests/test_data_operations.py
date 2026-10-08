"""Module data callbacks and operations use the owner's tables through the DAO."""

from types import SimpleNamespace

import pytest

from metaform.data import Column, Data, Element, Node, Operation, Store, Table, Tables
from metaform.module import Module

pytestmark = [pytest.mark.req("STORE-045"), pytest.mark.req("BASE-046"), pytest.mark.kind("fixture")]


@pytest.fixture
def declare(monkeypatch):
    from metaform import loader

    declared = []
    original = loader.get
    monkeypatch.setattr(loader, "enabled", lambda: declared)
    monkeypatch.setattr(
        loader, "get", lambda name: SimpleNamespace(module=declared[0]) if name == "demo" else original(name)
    )

    def install(data, *, version=1, extra=()):
        tables = Tables(
            version,
            (
                Table(
                    "counts",
                    key=("name",),
                    columns=(Column("name", required=True), Column("times", "int", required=True), *extra),
                ),
            ),
        )
        module = Module(id="demo", summary="Fixture.", purpose="Fixture.", data=data, tables=tables)
        declared[:] = [module]
        return module

    return install


@pytest.mark.parametrize("callback", ["decorate", "cleanup", "item_write"])
def test_data_callbacks_use_their_owners_tables(store, declare, callback):
    observed = []

    def hook(tx, *args):
        if callback == "decorate" and not isinstance(args[0], Element):
            return args[0]
        if callback == "cleanup" and args[0] != "layer":
            return None
        row = tx.tables().get("counts", {"name": "owned"})
        observed.append(row["times"])
        return args[0] if callback == "decorate" else None

    declare(Data(**{callback: hook}))
    with Store("proj", module="demo").tables() as tx:
        tx.insert("counts", {"name": "owned", "times": 7})
    layer = store.layer("knowledge", "demo", "Facts.", mutable=True, hideable=True)
    element = store.add_element(layer.name, "code.root", name_length=1, role="DE")
    if callback == "decorate":
        observed.clear()
        assert store.element(element.id, raw=True).id == element.id
    elif callback == "cleanup":
        store.discard(layer.name)
    else:
        store.add_item(layer.name, Node("element", element.id), "An answer.")
    assert observed == [7]


def test_read_data_operation_upgrades_existing_tables_without_hiding_rows(store, declare, home):
    def read_count(tx):
        return tx.tables().get("counts", {"name": "owned"})

    data = Data(operations={"read_count": Operation(read_count)})
    declare(data)
    with Store("proj", module="demo").tables() as tx:
        tx.insert("counts", {"name": "owned", "times": 7})
    declare(data, version=2, extra=(Column("label"),))
    assert store.read_count() == {"name": "owned", "times": 7, "label": None}
    assert list((home / "backups" / "module-demo-2").rglob("*.sqlite3"))


def test_read_data_operation_keeps_absent_regular_tables_absent(store, declare):
    def read_count(tx):
        return tx.tables().get("counts", {"name": "owned"})

    declare(Data(operations={"read_count": Operation(read_count)}))
    assert store.read_count() is None
    assert store.active_base() is None


def test_dao_follows_enablement_changed_by_another_process(store):
    from metaform import home

    assert store.layers().results == ()
    home.set_module_state("hello", True)
    assert store.count_visit("Rich") == "Rich: 1 visit\n"
    home.set_module_state("hello", False)
    assert not hasattr(store, "count_visit")


def test_module_table_access_follows_external_enablement(store):
    from metaform import home

    assert store.layers().results == ()
    home.set_module_state("hello", True)
    with Store("proj", module="hello").tables() as tx:
        tx.insert("visits", {"name": "Rich", "times": 1})


def test_direct_module_import_registers_settings_again_after_dao_unload(store, tmp_path):
    from metaform import loader, settings
    from metaform.modules import web as before

    assert before.MODULE.id == "web"
    store.layers()
    loader.reset()
    from metaform.modules import web

    assert web.MODULE.id == "web"
    assert settings.value("web_port", tmp_path) == 7433


def test_cold_disabled_map_keeps_work_readable_without_activating_its_runtime(store):
    from storekit import small_map

    from metaform import loader

    small_map(store)
    created = store.add_work(Node("element", "code.timer.kitchen"), "unbuilt", task="Recover the timer.")
    store.take_work(created.id, steps=2, by="codex")
    expected = store.step_work(created.id, "Located its boundary.")
    loader.set_enabled("map", False)
    loader.reset()

    assert loader.get("map").module is None
    assert store.ticket(created.id).work == expected
    assert store.work(limit=0).results == (expected,)
    assert not hasattr(store, "add_work")
    assert loader.get("map").module is None
    assert store.element("code.timer.kitchen").open_work == ()


def test_retained_reads_on_a_new_project_do_not_create_a_metaform(store):
    from metaform import loader

    loader.set_enabled("map", False)
    loader.reset()
    assert store.work(limit=0).results == ()
    assert store.messages(limit=0).results == ()
    assert store.active_base() is None
    assert loader.get("map").module is None
