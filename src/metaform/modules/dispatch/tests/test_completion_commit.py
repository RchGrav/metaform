"""Completion commits use successful writes, linked deliverables and retained ownership evidence."""
import asyncio
import json

import pytest

from metaform.data import Store
from metaform.module import context
from metaform.modules.dispatch import runner
from metaform.modules.dispatch.merge import capture_state, git
from metaform.modules.dispatch.tests.test_dispatch import dispatch as dispatch  # noqa: PLC0414 fixture re-export

pytestmark = [pytest.mark.req('BASE-052'), pytest.mark.kind('simulation')]


def session_for(dispatch):
    return runner.Session(context('dispatch', dispatch.folder, project='proj'),
                          Store('proj', module='dispatch'), dispatch.ticket(), 'claude', ['true'])


def initialize(folder):
    for args in [('init', '-q', '-b', 'dev'), ('config', 'user.name', 'Test'),
                 ('config', 'user.email', 'test@example.com')]:
        assert git(folder, *args).returncode == 0
    (folder / 'owned.py').write_text('before\n')
    (folder / 'peer.py').write_text('before\n')
    assert git(folder, 'add', '-A').returncode == 0
    assert git(folder, 'commit', '-qm', 'base').returncode == 0


def test_completion_commits_linked_writes_once_and_preserves_peer_edits(dispatch, monkeypatch):
    initialize(dispatch.folder)
    (dispatch.folder / 'peer.py').write_text('peer edit\n')
    made = session_for(dispatch)
    made.acp['ticket_git'] = {'baseline': capture_state(dispatch.folder), 'files': {}, 'result': None}
    made.sources = {'owned.py': [{'kind': 'element', 'id': 'owned', 'address': 'code.owned'}]}
    notes = []

    async def note(key, kind, text):
        notes.append((key, kind, text))

    monkeypatch.setattr(made, 'note', note)

    async def scenario():
        await made.write_text_file('test', str(dispatch.folder / 'owned.py'), 'own edit\n')
        await made.write_text_file('test', str(dispatch.folder / 'capture.txt'), 'diagnostic\n')
        await made.commit_done()
        await made.commit_done()

    asyncio.run(scenario())
    assert git(dispatch.folder, 'rev-list', '--count', 'HEAD').stdout.strip() == '2'
    assert git(dispatch.folder, 'show', '--format=', '--name-only', 'HEAD').stdout.strip() == 'owned.py'
    assert git(dispatch.folder, 'show', 'HEAD:peer.py').stdout == 'before\n'
    assert (dispatch.folder / 'peer.py').read_text() == 'peer edit\n'
    assert (dispatch.folder / 'capture.txt').exists()
    assert len([entry for entry in notes if entry[0] == 'ticket-commit']) == 1
    assert json.loads(next(entry[2] for entry in notes if entry[0] == 'ticket-commit'))['committed']


def test_write_evidence_is_unbounded_and_survives_thread_resume(dispatch, monkeypatch):
    made = session_for(dispatch)
    made.acp['ticket_git'] = {'baseline': {}, 'files': {}, 'result': None}

    async def note(*args):
        pass

    monkeypatch.setattr(made, 'note', note)
    paths = []
    for i in range(runner.TOUCHED_KEPT + 5):
        path = dispatch.folder / f'file{i}.py'
        path.write_text(str(i))
        paths.append(str(path))
    asyncio.run(made.changed_files(paths))
    assert len(made.acp['ticket_git']['files']) == len(paths)
    made.session_id = 'retained-session'
    with made.store.tables() as tx:
        tx.insert('session_lines', {'session_id': made.session_id, 'work_id': made.work_id,
                                   'name': 'state', 'kind': 'state', 'text': json.dumps(made.acp), 'seq': 1})
    resumed = session_for(dispatch)
    resumed.session_id = made.session_id
    resumed.continue_thread()
    assert resumed.acp['ticket_git'] == made.acp['ticket_git']


def test_ended_peer_writes_remain_ownership_conflicts_beyond_display_limit(dispatch):
    made = session_for(dispatch)
    made.session_id = 'ours'
    made.acp['ticket_git'] = {'started': 100, 'baseline': {}, 'files': {}, 'written_at': {}, 'result': None}
    peer_files = {f'file{i}.py': 'hash' for i in range(runner.TOUCHED_KEPT + 5)}
    peer = {'cwd': made.folder, 'ticket_git': {'files': peer_files,
                                              'written_at': {path: 200 for path in peer_files}}}
    with made.store.tables() as tx:
        tx.insert('agent_sessions', {'session_id': 'peer', 'work_id': 'peer-work', 'agent': 'codex',
                                     'state': 'ended', 'started': '2026-10-20T00:00:00Z', 'seq': 1})
        tx.insert('session_lines', {'session_id': 'peer', 'work_id': 'peer-work', 'name': 'state',
                                   'kind': 'state', 'text': json.dumps(peer), 'seq': 1})
    assert made.commit_overlaps(set(peer_files)) == set(peer_files)
    made.acp['ticket_git']['started'] = 300
    assert made.commit_overlaps(set(peer_files)) == set()


def test_completed_acp_diff_records_ownership_and_rejects_later_peer_write(dispatch, monkeypatch):
    from types import SimpleNamespace

    from metaform.modules.dispatch.orchestration import TRANSPORT

    initialize(dispatch.folder)
    made = session_for(dispatch)
    made.acp['ticket_git'] = {'started': 100, 'baseline': {}, 'files': {}, 'written_at': {}, 'result': None}
    made.sources = {'owned.py': [{'kind': 'element', 'id': 'owned', 'address': 'code.owned'}]}
    notifications = []

    async def note(*args):
        pass

    monkeypatch.setattr(made, 'note', note)
    monkeypatch.setattr(TRANSPORT, 'notify_user', lambda *args: notifications.append(args))
    (dispatch.folder / 'owned.py').write_text('own edit\n')
    update = {'sessionUpdate': 'tool_call_update', 'toolCallId': 'edit-1', 'kind': 'edit', 'status': 'completed',
              'content': [{'type': 'diff', 'path': str(dispatch.folder / 'owned.py'),
                           'oldText': 'before\n', 'newText': 'own edit\n'}]}

    async def scenario():
        await made.session_update('test', SimpleNamespace(model_dump=lambda **kwargs: update))
        assert set(made.acp['ticket_git']['files']) == {'owned.py'}
        (dispatch.folder / 'owned.py').write_text('peer replacement\n')
        await made.commit_done()

    asyncio.run(scenario())
    assert 'changed after' in made.acp['ticket_git']['result']['why']
    assert len(notifications) == 1
    assert git(dispatch.folder, 'rev-list', '--count', 'HEAD').stdout.strip() == '1'


def test_legacy_peer_present_at_start_stays_a_conflict_after_ending(dispatch):
    made = session_for(dispatch)
    made.session_id = 'ours'
    with made.store.tables() as tx:
        tx.insert('agent_sessions', {'session_id': 'legacy', 'work_id': 'peer-work', 'agent': 'codex',
                                     'state': 'running', 'started': '2026-10-20T00:00:00Z', 'seq': 1})
        tx.insert('session_lines', {'session_id': 'legacy', 'work_id': 'peer-work', 'name': 'state',
                                   'kind': 'state', 'text': json.dumps({'cwd': made.folder,
                                   'files': [{'path': 'owned.py', 'action': 'edit'}]}), 'seq': 2})
    made.acp['ticket_git'] = {'started': 1_000_000_000, 'peers': made.commit_peers(),
                              'baseline': {}, 'files': {}, 'result': None}
    with made.store.tables() as tx:
        tx.update('agent_sessions', {'session_id': 'legacy'}, {'state': 'ended'})
    assert made.commit_overlaps({'owned.py'}) == {'owned.py'}
