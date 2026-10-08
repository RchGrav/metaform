"""Feature storage is declared by modules; the chassis carries only generic services."""

import sqlite3

import pytest

pytestmark = [pytest.mark.req("BASE-046"), pytest.mark.kind("fixture")]


def test_chassis_schema_contains_no_feature_tables():
    from metaform.data.schema import STORE_SCHEMA

    db = sqlite3.connect(":memory:")
    try:
        db.executescript(STORE_SCHEMA)
        names = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert not names & {"work", "work_links", "work_steps", "messages", "challenge_states", "plans", "reports"}
    finally:
        db.close()


def test_map_declares_its_storage_and_operations(home):
    from metaform import loader

    module = loader.get("map").module
    assert {"work", "work_links", "work_steps", "messages", "challenge_states", "plans", "reports"} <= {
        table.name for table in module.tables.tables
    }
    assert {"add_work", "answer", "save_report", "ticket"} <= set(module.data.operations)


def test_disabled_features_leave_chassis_data_usable(store, monkeypatch):
    from metaform import loader

    monkeypatch.setattr(loader, "enabled", list)
    layer = store.layer("base", "test", "", kind="intake", mutable=False, hideable=False, ready=True)
    element = store.add_element(layer.name, "code.root", name_length=1, role="DE")
    assert store.where(element.address).element.id == element.id
    assert not hasattr(store, "add_work")


def test_module_operation_rolls_back_with_native_writes(store):
    from storekit import small_map

    from metaform import loader
    from metaform.data import Store

    loader.set_enabled("hello", True)
    layer, _, _ = small_map(store)
    assert store.count_visit("Rich") == "Rich: 1 visit\n"
    with pytest.raises(RuntimeError, match="undo together"), store.atomic():
        store.add_element(layer.name, "code.rollback")
        assert store.count_visit("Rich") == "Rich: 2 visits\n"
        raise RuntimeError("undo together")
    assert store.element("code.rollback") is None
    with Store("proj", module="hello").tables(write=False) as tx:
        assert tx.get("visits", {"name": "Rich"})["times"] == 1


@pytest.mark.parametrize("roundtrip", [False, True])
def test_discard_cleans_owned_layer_references_with_owner_disabled(store, monkeypatch, tmp_path, roundtrip):
    from storekit import knowledge, small_map, store_file

    from metaform import home, loader
    from metaform.data import Node, Store, export_document, import_document

    small_map(store)
    layer = knowledge(store, "owned")
    element = store.add_element(layer.name, "code.watchdog")
    item = store.add_item(layer.name, Node("element", element.id), "Recover a hung loop.")
    store.answer(item.id, "A")
    store.add_plan(layer.name, element.id, None)
    store.save_report("run-report.md", "run", "report", 10, layer.name)
    store.finish(layer.name)
    monkeypatch.setattr(loader, "enabled", list)
    if roundtrip:
        document = export_document(["proj"])
        monkeypatch.setenv("METAFORM_HOME", str(tmp_path / "imported-home"))
        import_document(document)
        assert export_document(["proj"]) == document
        store = Store("proj")

    store.discard(layer.name)
    with sqlite3.connect(store_file(home.home(), store)) as db:
        assert db.execute("SELECT COUNT(*) FROM challenge_states").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM plans").fetchone()[0] == 0
        assert db.execute("SELECT layer_id FROM reports WHERE report_id=?", ("run-report.md",)).fetchone()[0] is None
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_unadopted_feature_tables_survive_export_with_all_modules_disabled(store, monkeypatch, tmp_path):
    from storekit import small_map, store_file

    from metaform import home, loader
    from metaform.data import Node, Store, export_document, import_document

    small_map(store)
    ticket = store.add_work(Node("element", "code.timer.kitchen"), "unbuilt", task="Recover this task.")
    store.take_work(ticket.id, by="codex")
    store.step_work(ticket.id, "Observed the failure.")
    with sqlite3.connect(store_file(home.home(), store)) as db:
        db.execute("DELETE FROM meta WHERE key='module:map'")
        db.execute('DROP TABLE "map.glyphs"')
    enabled = loader.enabled
    monkeypatch.setattr(loader, "enabled", list)
    document = export_document(["proj"])
    monkeypatch.setenv("METAFORM_HOME", str(tmp_path / "unowned-import"))
    import_document(document)
    path = store_file(home.home(), Store("proj"))
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT task FROM work WHERE work_id=?", (ticket.id,)).fetchone() == (
            "Recover this task.",
        )
        assert db.execute("SELECT said FROM work_steps WHERE work_id=?", (ticket.id,)).fetchone() == (
            "Observed the failure.",
        )
        assert db.execute("SELECT 1 FROM meta WHERE key='module:map'").fetchone() is None
    assert export_document(["proj"]) == document
    monkeypatch.setattr(loader, "enabled", enabled)
    recovered = Store("proj").ticket(ticket.id).work
    assert recovered.task == "Recover this task." and recovered.said[0].said == "Observed the failure."


def test_historical_fold_keeps_persisted_module_layer_references_without_owner(home, tmp_path, monkeypatch):
    import json

    from test_store_upgrade import CORRECTION, INTAKE, layout_7_store

    from metaform import loader
    from metaform.data import Table
    from metaform.data.session import open_store

    path = tmp_path / "fold.metaform.sqlite3"
    layout_7_store(path)
    schema = "CREATE TABLE retained(id TEXT PRIMARY KEY, layer_id TEXT REFERENCES layers(layer_id));"
    table = Table.from_sql("retained", schema, on_remove=(("layer", "layer_id", "null"),))
    with sqlite3.connect(path) as db:
        db.execute(schema)
        db.execute("INSERT INTO retained(id, layer_id) VALUES (?, ?)", ("one", CORRECTION))
        db.execute(
            "INSERT INTO meta(key, value) VALUES (?, ?)",
            ("module:owner", json.dumps({"version": 1, "tables": [table.to_dict()]})),
        )
    monkeypatch.setattr(loader, "enabled", list)
    with open_store(path, write=False) as db:
        assert db.execute("SELECT layer_id FROM retained WHERE id=?", ("one",)).fetchone()[0] == INTAKE
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize("references", [False, True])
@pytest.mark.parametrize("transport", [False, True])
def test_native_old_store_upgrade_then_late_map_adoption_preserves_features(
    store, monkeypatch, tmp_path, references, transport
):
    from storekit import store_file
    from test_store_upgrade import CORRECTION, INTAKE, layout_7_store

    from metaform import home, loader
    from metaform.data import Store, export_document, import_document
    from metaform.data.session import open_store

    head = home.ensure_base(store.project_id)
    path = store_file(home.home(), store)
    layout_7_store(path)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE layers SET metaform_id=?", (head.id,))
        db.execute(
            "INSERT INTO work(work_id,target_kind,target_id,condition,task,created,steps,steps_done) "
            "VALUES ('W-old','element','E1','in-progress','Recover historical work.','2026-10-01',2,1)"
        )
        db.execute("INSERT INTO work_steps(work_id,number,said,at) VALUES ('W-old',1,'Kept progress.','2026-10-01')")
        if references:
            db.execute("INSERT INTO plans(element_id,layer_id,source) VALUES ('E1',?,'direct')", (CORRECTION,))
            db.execute(
                "INSERT INTO reports(report_id,run_id,layer_id,kind,created,size) "
                "VALUES ('old-report.md','old',?,'report','2026-10-01',1)",
                (CORRECTION,),
            )
    enabled = loader.enabled
    monkeypatch.setattr(loader, "enabled", list)
    with open_store(path, write=False) as db:
        assert db.execute("SELECT condition FROM work WHERE work_id='W-old'").fetchone()[0] == "in-progress"
        if references:
            assert db.execute("SELECT layer_id FROM plans").fetchone()[0] == INTAKE
            assert db.execute("SELECT layer_id FROM reports").fetchone()[0] == INTAKE
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    if transport:
        document = export_document(["proj"])
        monkeypatch.setenv("METAFORM_HOME", str(tmp_path / "late-import"))
        import_document(document)
        store = Store("proj")
        assert export_document(["proj"]) == document
    monkeypatch.setattr(loader, "enabled", enabled)
    ticket = store.ticket("W-old").work
    assert ticket.condition == "unbuilt" and ticket.taken == "2026-10-01"
    assert ticket.task == "Recover historical work." and ticket.said[0].said == "Kept progress."
    store.step_work(ticket.id, "Resumed successfully.")
    assert store.ticket(ticket.id).work.steps_done == 2
