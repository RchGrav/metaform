"""The chassis fires map.changed on the event bus after any command that changed the map, VIEW-018 and QUAL-015."""
from __future__ import annotations

import json

import pytest

from metaform import home as metaform_home

pytestmark = pytest.mark.kind('fixture')

WATCHER = '''
    import json
    from pathlib import Path
    from metaform.module import Module, Subscription
    SUPPORTED_OS = ('linux', 'macos', 'windows')
    LOG = Path(LOGPATH)
    def saw(payload, ctx):
        with LOG.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(payload) + '\\n')
    MODULE = Module(id='watcher', summary='x', purpose='Watches the map. Details: metaform help watcher.',
                    subscriptions=(Subscription('map.changed', saw),))
'''


def noted(run, folder, text):
    """Write a note on the map by hand, which makes the project's first metaform when it has none. Memory did this
    before it became a graph of its own that never touches the map, LAYER-013."""
    run('map', 'knowledge', 'op=create', 'layer=notes', 'variable=Notes.', 'mutable=true', 'hideable=true',
        'module=test', cwd=folder)
    run('map', 'knowledge', 'op=add-item', 'layer=notes', 'node=type:code.timer', f'value={json.dumps(text)}',
        cwd=folder)


def heard(log):
    """What the watcher heard since it was last asked, once: each event's project and base. What was written, the
    `tables` beside them, is the page's to read, VIEW-018, not what these tests count."""
    found = [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()] if log.exists() else []
    log.unlink(missing_ok=True)
    return [{key: value for key, value in event.items() if key in ('project', 'base_id')} for event in found]


@pytest.fixture
def watched(run, home, tmp_path, user_module):
    """A project, and a module of the user's own that records every map.changed it hears."""
    log = tmp_path / 'heard.jsonl'
    user_module('watcher', WATCHER.replace('LOGPATH', repr(str(log))))
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    heard(log)
    return folder, log


@pytest.mark.req('VIEW-018')
@pytest.mark.req('BASE-010')
@pytest.mark.req('QUAL-015')
def test_any_module_hears_map_changed_for_each_command_that_changed_the_map_and_never_for_a_read(run, watched):
    folder, log = watched
    run('map', 'layers', cwd=folder)
    run('map', 'roots', cwd=folder)
    assert heard(log) == []  # reading changes nothing, so nothing is announced
    noted(run, folder, 'Counts down.')
    active = metaform_home.active_base('proj')
    assert {'project': 'proj', 'base_id': active.id} in heard(log)  # no module asked for it
    run('map', 'knowledge', 'op=add-item', 'layer=notes', 'node=type:code.timer', 'value="Rings at zero."', cwd=folder)
    assert heard(log) == [{'project': 'proj', 'base_id': active.id}]  # once for one command
    run('add', 'base', 'fresh', cwd=folder)
    assert heard(log) == [{'project': 'proj', 'base_id': None}]  # the project's metaforms changed
    run('activate', 'base', 'main', cwd=folder)
    assert heard(log) == [{'project': 'proj', 'base_id': None}]
    run('map', 'roots', cwd=folder)
    assert heard(log) == []


@pytest.mark.req('PROJ-025')
@pytest.mark.req('VIEW-018')
def test_clearing_a_project_is_announced_once_as_a_change_to_its_metaforms(run, watched):
    folder, log = watched
    noted(run, folder, 'Counts down.')
    heard(log)
    refused = run('clear', 'project', cwd=folder, ok=False)
    assert refused.returncode == 2 and heard(log) == []  # the caution alone changes nothing
    run('clear', 'project', '--confirm', cwd=folder)
    assert heard(log) == [{'project': 'proj', 'base_id': None}]
    assert metaform_home.bases('proj') == ()


@pytest.mark.req('VIEW-018')
@pytest.mark.req('STORE-045')
@pytest.mark.req('STORE-020')
def test_a_write_to_a_modules_project_level_tables_is_announced_as_a_change_to_the_active_map(run, watched):
    """Found 2026-10-02: memory keeps its graph in project-level tables, and a write there fired no map.changed, so an
    open page never heard of a memory added or deleted. The chassis notes a project-level table's write as it notes a
    metaform store's, once per command, and a read notes nothing."""
    folder, log = watched
    noted(run, folder, 'Counts down.')
    active = metaform_home.active_base('proj')
    run('memory', 'create_entities', '[{"name":"tone","entityType":"behavior","observations":["Rings."],"why":"It rings."}]',
        cwd=folder)
    heard(log)
    run('memory', 'add_observations', '[{"entityName":"tone","contents":["Too quiet."]}]', cwd=folder)
    assert heard(log) == [{'project': 'proj', 'base_id': active.id}]
    run('memory', 'read_graph', cwd=folder)
    run('memory', 'graph', cwd=folder)
    assert heard(log) == []
    run('memory', 'add_observations', '[{"entityName":"tone","contents":["Too quiet."]}]', cwd=folder)
    assert heard(log) == []  # an observation the entity holds is skipped, and a write that changed nothing is silent
    run('memory', 'delete_entities', '["tone"]', cwd=folder)
    assert heard(log) == [{'project': 'proj', 'base_id': active.id}]
