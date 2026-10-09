"""The Metaform home and its base database: placement, projects, schema version and metaforms."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from metaform import home as metaform_home
from metaform.data import Node, Store, StoreError


def own(project_id):
    """A project's folder in the home, PROJ-026."""
    from metaform import home as metaform_home
    return metaform_home.project_folder(project_id)

pytestmark = pytest.mark.kind('fixture')


def listing(folder: Path) -> dict[str, bytes]:
    return {str(path.relative_to(folder)): (path.read_bytes() if path.is_file() else b'')
            for path in sorted(folder.rglob('*'))}


@pytest.mark.req('STORE-001')
def test_nothing_is_written_into_the_project_folder(home, tmp_path, run, monkeypatch):
    folder = tmp_path / 'work'
    folder.mkdir()
    (folder / '.hidden').write_text('x')
    before = listing(folder)
    run('add', 'project', 'work', str(folder), cwd=folder)
    run('set', '--project', 'work', cwd=folder)
    monkeypatch.chdir(folder)
    store = Store('work')
    layer = store.layer('notes', 'test', 'Notes.', mutable=True, hideable=True,
                        provenance={'module': 'test'})
    store.add_element(layer.name, 'code.engine')
    memory = store.layer('memory', 'memory', 'What agents have noted at this node.', kind='memory',
                         mutable=True, hideable=True, ready=True)
    store.add_item(memory.name, Node('element', 'code.engine'), 'An observation.')
    assert listing(folder) == before


@pytest.mark.req('STORE-001')
def test_every_file_created_is_under_the_home(home, tmp_path, run, monkeypatch):
    user_home = tmp_path / 'user'
    user_home.mkdir()
    monkeypatch.setenv('HOME', str(user_home))
    monkeypatch.setenv('USERPROFILE', str(user_home))
    folder = tmp_path / 'work'
    folder.mkdir()
    def outside():
        return {path for path in tmp_path.rglob('*') if path != home and home not in path.parents}
    before = outside()
    run('add', 'project', 'work', str(folder), cwd=folder, env={'HOME': str(user_home), 'USERPROFILE': str(user_home)})
    store = Store('work')
    store.add_element(store.layer('notes', 'test', 'Notes.', mutable=True, hideable=True,
                                  provenance={'module': 'test'}).name, 'code.engine')
    assert outside() == before
    assert not any(user_home.iterdir())
    assert (own('work') / 'project.sqlite3').is_file()


@pytest.mark.req('STORE-002')
@pytest.mark.req('BASE-047')
def test_read_only_commands_create_only_first_run_version_records(home, run, tmp_path):
    from metaform import __version__
    run(cwd=tmp_path)
    run('list', 'projects', cwd=tmp_path)
    run('config', '--show', cwd=tmp_path)
    assert not (home / 'projects').exists()
    with metaform_home.chassis() as db:
        assert dict(db.execute('SELECT key, value FROM meta')) == {
            'schema_version': metaform_home.CHASSIS_SCHEMA_VERSION,
            'last_run_version': __version__,
        }
        assert db.execute('SELECT COUNT(*) FROM settings').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM folders').fetchone()[0] == 0


@pytest.mark.req('STORE-002')
def test_project_found_by_folder_follows_the_systems_case_rule(home, tmp_path):
    folder = tmp_path / 'Work' / 'Proj'
    (folder / 'src').mkdir(parents=True)
    metaform_home.add_project('proj', folder)
    other_case = tmp_path / 'work' / 'proj' / 'src'
    if os.name == 'nt':
        assert metaform_home.folder_project(other_case) == 'proj'
    else:
        assert metaform_home.folder_project(other_case) is None
    assert metaform_home.folder_project(folder / 'src') == 'proj'


@pytest.mark.req('STORE-029')
def test_a_base_database_of_an_unknown_schema_version_is_refused_and_not_written(home, tmp_path):
    folder = tmp_path / 'p'
    folder.mkdir()
    metaform_home.add_project('p', folder)
    metaform_home.set_module_state('hello', True)
    for path, act in ((own('p') / 'project.sqlite3', lambda: metaform_home.add_project('q', folder.parent)),
                      (home / 'metaform.sqlite3', lambda: metaform_home.set_module_state('hello', False))):
        db = sqlite3.connect(path)
        db.execute("UPDATE meta SET value='999' WHERE key='schema_version'")
        db.commit()
        db.close()
        before = path.read_bytes()
        with pytest.raises(StoreError) as refused:
            act()
        assert '999' in str(refused.value)
        assert path.read_bytes() == before


@pytest.mark.req('STORE-029')
def test_a_home_written_before_the_stores_layout_changed_still_opens(home, tmp_path):
    """The metaform store's layout changed and the whole home was refused, the registry of projects
    and settings included, whose own layout had not changed. Each kind of database keeps its own version."""
    from metaform import settings
    from metaform.data import history, prompts
    folder = tmp_path / 'p'
    folder.mkdir()
    metaform_home.add_project('p', folder)
    history.add_origin('p')
    prompts.prompts()
    settings.assign('debug', True, folder)
    db = sqlite3.connect(own('p') / 'project.sqlite3')
    assert db.execute("SELECT count(*) FROM settings WHERE key='debug'").fetchone()[0] == 1
    db.close()
    for path in (own('p') / 'project.sqlite3', own('p') / 'history.sqlite3'):
        db = sqlite3.connect(path)
        db.execute("UPDATE meta SET value='1' WHERE key='schema_version'")
        db.commit()
        db.close()
    assert metaform_home.project('p') is not None
    assert len(history.origins('p')) == 1
    assert settings.value('debug', folder) is True
    metaform_home.add_project('q', tmp_path)
    assert {record.project_id for record in metaform_home.projects()} == {'p', 'q'}


@pytest.mark.req('STORE-029')
def test_a_store_of_an_unknown_schema_version_is_refused_and_not_written(home, store):
    layer = store.layer('notes', 'test', 'Notes.', mutable=True, hideable=True,
                        provenance={'module': 'test'})
    store.add_element(layer.name, 'code.engine')
    path = metaform_home.store_path('proj', store.active_base().id)
    db = sqlite3.connect(path)
    db.execute("UPDATE meta SET value='999' WHERE key='schema_version'")
    db.commit()
    db.close()
    before = path.read_bytes()
    with pytest.raises(StoreError) as refused:
        store.add_element(layer.name, 'code.other')
    assert '999' in str(refused.value) and refused.value.next_step
    with pytest.raises(StoreError):
        store.element('code.engine')
    assert path.read_bytes() == before


@pytest.mark.req('STORE-031')
def test_project_ids_are_lowercase_and_registration_is_idempotent(home, tmp_path):
    folder = tmp_path / 'p'
    folder.mkdir()
    with pytest.raises(StoreError):
        metaform_home.add_project('Notes', folder)
    first = metaform_home.add_project('notes', folder)
    second = metaform_home.add_project('notes', folder)
    assert 'already registered' not in first
    assert second == 'Project notes is already registered.'
    assert [record.project_id for record in metaform_home.projects()] == ['notes']


@pytest.mark.req('STORE-031')
def test_a_second_id_on_a_registered_path_is_refused_and_names_the_first(home, tmp_path):
    folder = tmp_path / 'p'
    folder.mkdir()
    metaform_home.add_project('notes', folder)
    with pytest.raises(StoreError) as refused:
        metaform_home.add_project('other', folder)
    assert 'notes' in str(refused.value) and refused.value.next_step == 'metaform list projects'
    elsewhere = tmp_path / 'q'
    elsewhere.mkdir()
    with pytest.raises(StoreError) as moved:
        metaform_home.add_project('notes', elsewhere)
    assert moved.value.next_step == 'metaform list projects'
    with pytest.raises(StoreError):
        metaform_home.add_project('ghost', tmp_path / 'missing')


@pytest.mark.req('STORE-031')
@pytest.mark.req('MAP-041')
def test_the_project_record_holds_its_target(home, tmp_path):
    folder = tmp_path / 'pics'
    folder.mkdir()
    metaform_home.add_project('photos', folder, 'artifact', 'kitchen_photos')
    record = Store('photos').project()
    assert (record.project_id, record.target_type, record.target_value) == ('photos', 'artifact', 'kitchen_photos')
    plain = tmp_path / 'plain'
    plain.mkdir()
    metaform_home.add_project('plain', plain)
    record = Store('plain').project()
    assert (record.target_type, record.target_value) == ('path', str(plain.resolve()))


@pytest.mark.req('STORE-023')
def test_a_store_for_an_unregistered_project_is_refused(home):
    with pytest.raises(StoreError) as refused:
        Store('ghost')
    assert refused.value.next_step == 'metaform list projects'


@pytest.mark.req('STORE-003')
def test_reading_a_metaform_that_was_never_written_leaves_no_store(home, store):
    assert store.element('code.engine') is None
    assert store.layers().results == ()
    assert store.has_intake() is False
    assert not list(home.rglob('*.metaform.sqlite3'))


@pytest.mark.req('STORE-041')
@pytest.mark.req('MAP-045')
def test_a_new_metaform_starts_empty_and_the_old_one_is_kept_whole(home, store):
    with store.atomic():
        layer = store.layer('intake-1', 'intake', 'The map.', kind='intake', mutable=False, hideable=False, provenance={'module': 'intake'}, ready=True)
        element = store.add_element(layer.name, 'code.engine', name_length=1, role='DE')
    main = store.active_base()
    assert main.name == 'main'
    main_file = metaform_home.store_path('proj', main.id)
    before = main_file.read_bytes()
    before_read = store.element(element.id).to_dict()
    fresh = store.add_base('fresh')
    assert store.active_base().id == fresh.id
    assert store.element(element.id) is None
    assert store.has_intake() is False
    assert main_file.read_bytes() == before
    store.activate_base('main')
    assert store.element(element.id).to_dict() == before_read
    assert store.has_intake() is True
    assert [item.name for item in store.bases().results] == ['main', 'fresh']


@pytest.mark.req('STORE-041')
@pytest.mark.req('BASE-044')
def test_a_metaform_name_taken_in_the_project_is_numbered_with_a_notice(home, store):
    store.add_base('fresh')
    second = store.add_base('fresh')
    third = store.add_base('fresh')
    assert (second.name, third.name) == ('fresh-2', 'fresh-3')
    assert second.notices and 'fresh' in second.notices[0].message
    assert [item.name for item in store.bases().results] == ['main', 'fresh', 'fresh-2', 'fresh-3']


@pytest.mark.req('STORE-041')
def test_every_layer_names_the_metaform_that_holds_it(store):
    layer = store.layer('notes', 'test', 'Notes.', mutable=True, hideable=True,
                        provenance={'module': 'test'})
    assert layer.base_id == store.active_base().id
