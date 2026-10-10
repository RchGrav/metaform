"""Process feedback, intake reports and saved shapes: files in the home, one row each, listed and read, BASE-045."""
from __future__ import annotations

import json
import re

import pytest

from metaform.data import Store


def own(project_id):
    """A project's folder in the home, PROJ-026."""
    from metaform import home as metaform_home
    return metaform_home.project_folder(project_id)

pytestmark = pytest.mark.kind('fixture')

OS = "SUPPORTED_OS = ('linux', 'macos', 'windows')"


@pytest.fixture
def project(run, tmp_path):
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    return folder


def listed(run, cwd, *args):
    return json.loads(run('list', 'reports', *args, '--json', cwd=cwd).stdout)['results']


@pytest.mark.req('BASE-045')
@pytest.mark.req('STORE-043')
@pytest.mark.req('STORE-001')
def test_feedback_with_a_shape_and_no_layer_writes_two_files_with_one_run_id(run, project, home):
    shape = project.parent / 'shape.txt'
    shape.write_text('<result id="x"><elements/></result>\n', encoding='utf-8')
    result = json.loads(run('feedback', 'The tool schema named flag twice.', f'shape={shape}', '--json',
                            cwd=project).stdout)
    names = sorted(result['files'])
    run_id = names[0].rsplit('-', 1)[0]
    assert re.fullmatch(r'\d{8}T\d{6}Z-[0-9a-f]{6}', run_id)
    assert names == [f'{run_id}-feedback.md', f'{run_id}-shape.txt']
    folder = own('proj') / 'reports'
    assert (folder / f'{run_id}-feedback.md').read_text(encoding='utf-8') == 'The tool schema named flag twice.'
    assert (folder / f'{run_id}-shape.txt').read_text(encoding='utf-8') == '<result id="x"><elements/></result>\n'
    rows = listed(run, project)
    assert sorted((row['name'], row['kind'], row['layer']) for row in rows) == [
        (f'{run_id}-feedback.md', 'feedback', None), (f'{run_id}-shape.txt', 'shape', None)]
    assert sorted(path.name for path in project.iterdir()) == []


@pytest.mark.req('BASE-045')
@pytest.mark.req('BASE-044')
def test_a_shape_file_that_is_not_utf8_is_saved_with_a_notice_and_never_as_its_name(run, project, home):
    shape = project.parent / 'shape.txt'
    shape.write_bytes(b'<result id="caf\xe9"/>\n')
    result = json.loads(run('feedback', 'Encoding.', f'shape={shape}', '--json', cwd=project).stdout)
    saved = next(name for name in result['files'] if name.endswith('-shape.txt'))
    assert (own('proj') / 'reports' / saved).read_text(encoding='utf-8') == '<result id="caf�"/>\n'
    assert [notice['where'] for notice in result['notices']] == ['shape']


@pytest.mark.req('BASE-045')
def test_a_second_write_for_one_run_appends_a_section_and_read_returns_the_text_exactly(run, project, home):
    store = Store('proj')
    store.layer('notes', 'test', 'Notes.', mutable=True, hideable=True, provenance={'module': 'test'})
    first = json.loads(run('feedback', 'First.', 'layer=notes', '--json', cwd=project).stdout)
    run('feedback', 'Second.', 'layer=notes', cwd=project)
    name = first['files'][0]
    text = run('read', 'report', name, cwd=project).stdout
    assert text.startswith('First.') and text.rstrip().endswith('Second.')
    assert re.search(r'^## \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$', text, re.MULTILINE)
    assert [ref.value for ref in store.provenance('notes').refs] == [name]


@pytest.mark.req('BASE-045')
def test_feedback_outside_any_project_goes_to_the_homes_reports_folder(run, home, tmp_path):
    outside = tmp_path / 'desk'
    outside.mkdir()
    result = json.loads(run('feedback', 'Nothing here to map.', '--json', cwd=outside).stdout)
    name = result['files'][0]
    assert (home / 'reports' / name).read_text(encoding='utf-8') == 'Nothing here to map.'
    assert [row['name'] for row in listed(run, outside)] == [name]
    assert run('read', 'report', name, cwd=outside).stdout == 'Nothing here to map.'


@pytest.mark.req('BASE-045')
@pytest.mark.req('CLI-031')
def test_an_unknown_report_names_the_listing_and_a_path_is_never_read(run, project, tmp_path):
    secret = tmp_path / 'secret.txt'
    secret.write_text('do not serve', encoding='utf-8')
    for name in ('nosuch-report.md', str(secret), '../secret.txt'):
        refused = run('read', 'report', name, cwd=project, ok=False)
        assert refused.returncode == 2
        assert refused.stderr.splitlines() == [f'Error: No report {name}.', 'Next: metaform list reports']


@pytest.mark.req('BASE-045')
@pytest.mark.req('CLI-022')
def test_feedback_and_reports_run_whatever_the_surface(run, project, user_module):
    user_module('solo', f'''
        from metaform.module import Module, Verb
        {OS}
        MODULE = Module(id='solo', summary='x', purpose='Solo. Details: metaform help solo.',
                        verbs=(Verb('hi', lambda ctx: 'hi', 'Say hi.'),))
    ''')
    run('set', '--modules', 'solo', cwd=project)
    assert run('list', 'projects', cwd=project, ok=False).returncode == 2
    name = json.loads(run('feedback', 'Narrowed and still reporting.', '--json', cwd=project).stdout)['files'][0]
    assert [row['name'] for row in listed(run, project)] == [name]
    assert run('read', 'report', name, cwd=project).stdout == 'Narrowed and still reporting.'
    index = run('help', 'commands', cwd=project).stdout
    assert re.search(r'^  feedback ', index, re.MULTILINE) and re.search(r'^  read ', index, re.MULTILINE)


@pytest.mark.req('BASE-045')
@pytest.mark.req('BASE-046')
def test_public_report_files_remain_usable_with_map_disabled(run, project):
    first = json.loads(run('feedback', 'Before disabling map.', '--json', cwd=project).stdout)
    run('disable', 'map', cwd=project)
    second = json.loads(run('feedback', 'Map is disabled.', 'report=Still report.',
                            '--json', cwd=project).stdout)
    names = first['files'] + second['files']
    assert {row['name'] for row in listed(run, project)} == set(names)
    assert [row['name'] for row in listed(run, project, 'kind=report')] == [second['files'][1]]
    for name, content in zip(names, ('Before disabling map.', 'Map is disabled.', 'Still report.'), strict=True):
        assert run('read', 'report', name, cwd=project).stdout == content
    missing = run('read', 'report', 'unknown-report.md', cwd=project, ok=False)
    assert missing.returncode == 2
    assert missing.stderr.splitlines() == ['Error: No report unknown-report.md.', 'Next: metaform list reports']


@pytest.mark.req('BASE-045')
def test_writes_to_one_file_at_the_same_time_all_survive(home):
    # Eight writers released at once; on Windows, where an append is not one step, sections were lost without a lock.
    import threading

    from metaform import reports
    texts = [f'Report {number}.' for number in range(8)]
    start = threading.Barrier(len(texts))

    def write(text):
        start.wait()
        reports.write(None, 'run-1', 'feedback', text)
    threads = [threading.Thread(target=write, args=(text,)) for text in texts]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    content = (reports.folder(None) / 'run-1-feedback.md').read_text(encoding='utf-8')
    assert [text for text in texts if text not in content] == []


@pytest.mark.req('STORE-043')
def test_a_reports_recorded_size_never_falls_below_one_already_recorded(home, tmp_path):
    # Writers appending at once each record the size they saw; the last to record may have seen the file earlier.
    from metaform import home as metaform_home
    (tmp_path / 'proj').mkdir()
    metaform_home.add_project('proj', tmp_path / 'proj')
    store = Store('proj')
    store.save_report('run-1-feedback.md', 'run-1', 'feedback', 717)
    store.save_report('run-1-feedback.md', 'run-1', 'feedback', 207)
    assert store.report('run-1-feedback.md').size == 717



@pytest.mark.req('BASE-045')
def test_writes_from_separate_processes_to_one_file_all_survive(home, tmp_path):
    # Separate processes share no lock but the file's own, so this is what keeps them apart.
    import os
    import subprocess
    import sys

    from metaform import reports
    go = tmp_path / 'go'
    code = ('import pathlib, sys, time\n'
            'from metaform import reports\n'
            'go = pathlib.Path(sys.argv[1])\n'
            'while not go.exists():\n'
            '    time.sleep(0.01)\n'
            "reports.write(None, 'run-2', 'feedback', sys.argv[2])\n")
    texts = [f'Process report {number}.' for number in range(6)]
    writers = [subprocess.Popen([sys.executable, '-c', code, str(go), text],
                                env={**os.environ, 'METAFORM_HOME': str(home)}) for text in texts]
    go.write_text('now', encoding='utf-8')
    assert [writer.wait(timeout=60) for writer in writers] == [0] * len(texts)
    content = (reports.folder(None) / 'run-2-feedback.md').read_text(encoding='utf-8')
    assert [text for text in texts if text not in content] == []
    assert content.count('\n## ') == len(texts) - 1
