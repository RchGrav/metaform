"""Accepted prompt delivery history remains available after role retirement."""
from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.kind('fixture')


def read(run, *args, folder):
    return json.loads(run('agents', *args, '--json', cwd=folder).stdout)


def test_sent_reads_the_role_and_the_versions_each_turn_of_a_session_carried(run, project_folder):
    from metaform import home
    from metaform.data import Store
    from metaform.module import context
    home.ensure_base('proj')
    turn = {'project': 'proj', 'work_id': 'w1', 'session_id': 's1', 'runner': 'r1', 'role': 'worker',
            'agent': 'claude', 'at': '2026-10-15T18:00:00Z',
            'prompts': [{'name': 'prompt.dispatch:work', 'number': 1, 'origin': 'shipped', 'version_id': 'v1'},
                        {'name': 'prompt.dispatch:work_record', 'number': 1, 'origin': 'shipped', 'version_id': 'v2'}]}
    later = {**turn, 'at': '2026-10-15T18:05:00Z',
             'prompts': [{'name': 'prompt.dispatch:work', 'number': 2, 'origin': 'edited', 'version_id': 'v3'}]}
    told = context('dispatch', project_folder, project='proj')
    told.publish('prompt.sent', turn)
    told.publish('prompt.sent', later)
    found = read(run, 'sent', 'session=s1', folder=project_folder)
    assert (found['role'], found['agent'], found['work_id']) == ('worker', 'claude', 'w1')
    assert found['prompts'] == [{'name': 'prompt.dispatch:work', 'versions': [1, 2]},
                                {'name': 'prompt.dispatch:work_record', 'versions': [1]}]
    assert [one['at'] for one in found['turns']] == ['2026-10-15T18:00:00Z', '2026-10-15T18:05:00Z']
    assert read(run, 'sent', 'session=r1', folder=project_folder)['session_id'] == 's1'
    assert [layer.module for layer in Store('proj').layers(limit=0).results if layer.name == 'agents'] == ['agents']
    unknown = run('agents', 'sent', 'session=nobody', cwd=project_folder, ok=False)
    assert unknown.returncode != 0 and 'No prompts are recorded for session nobody' in unknown.stderr
