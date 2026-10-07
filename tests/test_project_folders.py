"""PROJ-026: each project is its own folder in the home, named by its source's path, and no database lists them."""
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
from pathlib import Path

import pytest

pytestmark = pytest.mark.kind('fixture')


def folder_for(home: Path, source: Path, number: int = 1) -> Path:
    """Where PROJ-026 says a source's project folder is."""
    name = re.sub(r'[^A-Za-z0-9]', '-', os.path.normcase(str(source.resolve())))
    return home / 'projects' / f'{name}-{number:03d}'


@pytest.fixture
def source(tmp_path):
    folder = tmp_path / 'kitchen timer'
    folder.mkdir()
    return folder


@pytest.mark.req('PROJ-026')
def test_registering_makes_one_folder_named_by_the_source_path(run, home, source):
    run('add', 'project', 'timer', str(source))
    folder = folder_for(home, source)
    assert [path.name for path in (home / 'projects').iterdir()] == [folder.name]
    assert (folder / 'source.txt').read_text(encoding='utf-8').strip() == str(source.resolve())
    assert (folder / 'project.sqlite3').is_file()
    provenance = json.loads((folder / '.metaform' / 'provenance.json').read_text(encoding='utf-8'))
    assert provenance['source'] == str(source.resolve()) and provenance['registered']


@pytest.mark.req('PROJ-026')
@pytest.mark.req('STORE-002')
def test_no_database_in_the_home_lists_a_project_or_holds_its_settings(run, home, source):
    run('add', 'project', 'timer', str(source))
    inside = source / 'src'
    inside.mkdir()
    run('set', '--layers', 'notes', cwd=inside)
    run('set', '--debug', cwd=home.parent)  # a folder outside every project keeps its settings in the chassis
    with sqlite3.connect(home / 'metaform.sqlite3') as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        dump = '\n'.join(db.iterdump())
    assert not tables & {'projects', 'metaforms', 'active_metaforms'}
    assert 'timer' not in dump and str(source.resolve()) not in dump


@pytest.mark.req('PROJ-026')
@pytest.mark.req('PROJ-003')
def test_a_working_folder_finds_its_project_from_the_file_system_alone(run, home, source):
    run('add', 'project', 'timer', str(source))
    for name in ('metaform.sqlite3', 'metaform.sqlite3-wal', 'metaform.sqlite3-shm'):
        (home / name).unlink(missing_ok=True)
    deep = source / 'a' / 'b'
    deep.mkdir(parents=True)
    assert 'Project: timer' in run(cwd=deep).stdout
    assert 'timer' in run('list', 'projects', cwd=deep).stdout


@pytest.mark.req('PROJ-026')
@pytest.mark.req('STORE-003')
def test_each_metaform_is_a_store_named_by_the_metaform_in_the_project_folder(run, home, source):
    run('add', 'project', 'timer', str(source))
    folder = folder_for(home, source)
    run('intake', 'element', 'code.timer', 'role=DE', cwd=source)
    assert (folder / 'main.metaform.sqlite3').is_file()
    run('add', 'base', 'fresh', cwd=source)
    run('map', 'knowledge', 'op=create', 'layer=notes', 'variable=Notes.', cwd=source)
    assert (folder / 'fresh.metaform.sqlite3').is_file()
    assert not (folder / 'metaforms').exists()


@pytest.mark.req('PROJ-026')
def test_a_project_folder_copied_into_an_empty_home_reads_back_whole(run, home, source, tmp_path):
    run('add', 'project', 'timer', str(source))
    inside = source / 'src'
    inside.mkdir()
    run('intake', 'element', 'code.timer', 'role=DE', 'name_length=1', cwd=source)
    run('intake', 'finish', cwd=source)
    run('set', '--layers', 'notes', cwd=inside)
    other = tmp_path / 'other home'
    shutil.copytree(folder_for(home, source), folder_for(other, source))
    elsewhere = {'METAFORM_HOME': str(other)}
    assert 'code.timer' in run('map', 'where', 'code.timer', cwd=source, env=elsewhere).stdout
    shown = json.loads(run('config', '--show', '--json', cwd=inside, env=elsewhere).stdout)
    assert next(row for row in shown if row['key'] == 'layers')['value'] == ['notes']


@pytest.mark.req('PROJ-026')
def test_two_sources_whose_paths_read_the_same_get_folders_of_their_own(run, home, tmp_path):
    joined, nested = tmp_path / 'x-y', tmp_path / 'x' / 'y'
    joined.mkdir()
    nested.mkdir(parents=True)
    run('add', 'project', 'one', str(joined))
    run('add', 'project', 'two', str(nested))
    assert folder_for(home, joined).is_dir() and folder_for(home, nested, 2).is_dir()
    assert 'Project: one' in run(cwd=joined).stdout
    assert 'Project: two' in run(cwd=nested).stdout


@pytest.mark.req('PROJ-026')
@pytest.mark.req('PROJ-023')
@pytest.mark.req('PROJ-025')
def test_origins_and_variants_are_kept_in_the_project_folder_and_nowhere_shared(run, home, source, tmp_path):
    (source / 'timer.txt').write_text('ten minutes\n', encoding='utf-8')
    run('add', 'project', 'timer', str(source))
    run('add', 'origin', cwd=source)
    work = tmp_path / 'work'
    shutil.copytree(source, work)
    (work / 'timer.txt').write_text('five minutes\n', encoding='utf-8')
    run('add', 'variant', str(work), cwd=source)
    assert not (home / 'origins').exists()
    [unit] = (folder_for(home, source) / 'origins').iterdir()
    assert (unit / 'origin' / 'timer.txt').read_text(encoding='utf-8') == 'ten minutes\n'
    assert [path.name for path in (unit / 'variants').iterdir()] == ['v000001']
    before = {str(path.relative_to(unit)): path.read_bytes() for path in unit.rglob('*') if path.is_file()}
    run('clear', 'project', 'timer', '--confirm', cwd=tmp_path)
    assert {str(path.relative_to(unit)): path.read_bytes() for path in unit.rglob('*') if path.is_file()} == before
