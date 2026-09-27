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


def heard(log):
    """What the watcher heard since it was last asked, once."""
    found = [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()] if log.exists() else []
    log.unlink(missing_ok=True)
    return found


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
    run('memory', 'read-graph', cwd=folder)
    assert heard(log) == []  # reading changes nothing, so nothing is announced
    run('memory', 'add-observations', 'element:code.timer', 'Counts down.', cwd=folder)
    active = metaform_home.active_metaform('proj')
    assert {'project': 'proj', 'metaform_id': active.metaform_id} in heard(log)  # no module asked for it
    run('memory', 'add-observations', 'element:code.timer', 'Rings at zero.', cwd=folder)
    assert heard(log) == [{'project': 'proj', 'metaform_id': active.metaform_id}]  # once for one command
    run('add', 'metaform', 'fresh', cwd=folder)
    assert heard(log) == [{'project': 'proj', 'metaform_id': None}]  # the project's metaforms changed
    run('activate', 'metaform', 'main', cwd=folder)
    assert heard(log) == [{'project': 'proj', 'metaform_id': None}]
    run('map', 'roots', cwd=folder)
    assert heard(log) == []


@pytest.mark.req('PROJ-025')
@pytest.mark.req('VIEW-018')
def test_clearing_a_project_is_announced_once_as_a_change_to_its_metaforms(run, watched):
    folder, log = watched
    run('memory', 'add-observations', 'element:code.timer', 'Counts down.', cwd=folder)
    heard(log)
    refused = run('clear', 'project', cwd=folder, ok=False)
    assert refused.returncode == 2 and heard(log) == []  # the caution alone changes nothing
    run('clear', 'project', '--confirm', cwd=folder)
    assert heard(log) == [{'project': 'proj', 'metaform_id': None}]
    assert metaform_home.metaforms('proj') == ()
