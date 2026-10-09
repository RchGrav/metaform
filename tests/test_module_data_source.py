"""Retained declarations load without activating a module and survive wheel resources."""

import sys
import zipfile
from pathlib import Path

import pytest

from metaform import loader, module_metadata

pytestmark = [pytest.mark.req("BASE-046"), pytest.mark.req("BASE-018"), pytest.mark.kind("fixture")]

ENTRY = """SUPPORTED_OS = ('linux', 'macos', 'windows')
SHIPS_DISABLED = True
DATA_SOURCE = 'storage.py'
from pathlib import Path
from metaform.module import Module
Path(__file__).with_name('runtime-imported').touch()
MODULE = Module(id='retained', summary='Retained data.', purpose='Hold data.',
                start=lambda ctx: Path(__file__).with_name('runtime-started').touch())
"""
SOURCE = """from .helper import VALUE
from metaform.data import Data, Tables
DATA = Data()
TABLES = Tables(version=1, tables=())
def later():
    from .later import VALUE
    return VALUE
"""


@pytest.mark.parametrize("wheel", [False, True], ids=["folder", "wheel"])
def test_disabled_data_source_has_its_own_lifecycle(home, tmp_path, monkeypatch, wheel):
    files = {"__init__.py": ENTRY + "DEPENDENCIES = ('metaform-absent-runtime-dependency',)\n",
             "storage.py": SOURCE, "helper.py": "VALUE = 42\n", "later.py": "VALUE = 43\n"}
    archive = None
    if wheel:
        path = tmp_path / "modules.whl"
        with zipfile.ZipFile(path, "w") as target:
            for name, body in files.items():
                target.writestr("modules/retained/" + name, body)
        archive = zipfile.ZipFile(path)
        folder = zipfile.Path(archive, "modules/retained/")
        original = loader.importlib.resources.as_file

        def files_only(resource):
            # Python 3.11's as_file supports files; directory extraction arrived in 3.12.
            assert resource.is_file()
            return original(resource)

        monkeypatch.setattr(loader.importlib.resources, "as_file", files_only)
    else:
        folder = tmp_path / "modules" / "retained"
        folder.mkdir(parents=True)
        for name, body in files.items():
            (folder / name).write_text(body)
    monkeypatch.setattr(loader, "_candidates", lambda project: [
        loader.Found("retained", "system", folder, "metaform_module_system_retained")])
    try:
        assert module_metadata.read(folder).data_source == "storage.py"
        loaded = loader.data_source("retained")
        assert loaded is not None
        assert loaded.VALUE == 42
        assert loader.data_source("retained") is loaded
        extracted = Path(sys.modules[loaded.__package__].__path__[0])
        assert loaded.later() == 43
        assert loader.get("retained").module is None
        assert not (extracted / "runtime-imported").exists()
        assert not (extracted / "runtime-started").exists()
        loader.reset()
        assert loaded.__name__ not in sys.modules
        assert loaded.__package__ not in sys.modules
        assert extracted.exists() is not wheel
    finally:
        loader.reset()
        if archive is not None:
            archive.close()


def test_external_enablement_replaces_the_standalone_package(home, user_module):
    from metaform import home as metadata

    folder = user_module("retained", ENTRY)
    (folder / "storage.py").write_text(SOURCE)
    (folder / "helper.py").write_text("VALUE = 42\n")
    (folder / "later.py").write_text("VALUE = 43\n")
    loaded = loader.data_source("retained")
    assert loaded is not None
    assert loader.get("retained").module is None
    metadata.set_module_state("retained", True)
    assert loader.get("retained").module is not None
    assert (folder / "runtime-imported").is_file()
    assert (folder / "runtime-started").is_file()
    assert loaded.__name__ not in sys.modules


@pytest.mark.parametrize("source", [None, "raise ValueError('broken declaration')\n"], ids=["missing", "broken"])
def test_broken_unrelated_source_does_not_block_retained_reads(home, user_module, store, source, monkeypatch):
    from storekit import small_map

    from metaform.data import Node

    small_map(store)
    work = store.add_work(Node("element", "code.timer.kitchen"), "unbuilt", task="Recover its timer.")
    loader.set_enabled("map", False)
    folder = user_module("aaa_broken", ENTRY.replace("id='retained'", "id='aaa_broken'"))
    if source is not None:
        (folder / "storage.py").write_text(source)
    loader.reset()
    candidates = loader._candidates
    monkeypatch.setattr(loader, "_candidates", lambda project: sorted(
        candidates(project), key=lambda item: item.id != "aaa_broken"))
    assert store.ticket(work.id).work == work
    assert not hasattr(store, "add_work")
    found = loader.get("aaa_broken")
    assert found is not None and found.module is None
    assert "FileNotFoundError" in found.problem if source is None else "ValueError" in found.problem
    assert found.import_name not in sys.modules
    assert found.import_name + ".data_source" not in sys.modules
