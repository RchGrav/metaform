"""Completion commits use successful writes, linked deliverables and retained ownership evidence."""
import asyncio
import json
import sys

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


async def edited(made, path, text):
    """An agent's edit as its tool call reports it once completed: the file written, and the write kept for
    completion, as the runner does for each path a completed edit names."""
    path.write_text(text)
    await made.changed_files([str(path)])


def initialize(folder):
    for args in [('init', '-q', '-b', 'dev'), ('config', 'user.name', 'Test'),
                 ('config', 'user.email', 'test@example.com')]:
        assert git(folder, *args).returncode == 0
    (folder / 'owned.py').write_text('before\n')
    (folder / 'peer.py').write_text('before\n')
    assert git(folder, 'add', '-A').returncode == 0
    assert git(folder, 'commit', '-qm', 'base').returncode == 0


@pytest.mark.parametrize('check_passes', [False, True])
def test_nonrepository_completion_records_verification_without_inventing_commit(dispatch, run, monkeypatch, check_passes):
    check = f'"{sys.executable}" -c "raise SystemExit({0 if check_passes else 1})"'
    run('set', f'--dispatch-test-command={check}', cwd=dispatch.folder)
    made = session_for(dispatch)
    made.acp['ticket_git'] = {'baseline': {'': 'not a git checkout'}, 'files': {}, 'result': None}

    async def note(*args):
        pass

    monkeypatch.setattr(made, 'note', note)
    monkeypatch.setenv('METAFORM_TASK_NAME', 'project_agent')
    dispatch.store.finish_work(dispatch.id, 'Verified nonrepository result.')
    asyncio.run(made.commit_done())
    assert dispatch.ticket().done
    assert made.acp['ticket_git']['result']['committed'] is None
    assert made.acp['ticket_git']['result']['not_required'] is True
    with Store('proj', module='dispatch').tables(write=False) as tx:
        receipt = tx.get('merges', {'work_id': dispatch.id})
    assert receipt['head'] is None
    assert receipt['evidence']['repository'] is False
    assert receipt['evidence']['verification']['passed'] is check_passes
    if not check_passes:
        monkeypatch.delenv('METAFORM_TASK_NAME')
        run('set', f'--dispatch-test-command="{sys.executable}" -c "raise SystemExit(0)"', cwd=dispatch.folder)
        monkeypatch.setenv('METAFORM_TASK_NAME', 'project_agent')
        asyncio.run(made.commit_done())
        assert dispatch.ticket().done


def test_repository_cannot_bypass_feature_commit_with_nonrepository_delivery(dispatch):
    from metaform.modules.dispatch.merge import deliver_nonrepository

    initialize(dispatch.folder)
    result = deliver_nonrepository(context('dispatch', dispatch.folder, project='proj'), dispatch.store, dispatch.id)
    assert 'repository' in result['reason']
    with Store('proj', module='dispatch').tables(write=False) as tx:
        assert tx.get('merges', {'work_id': dispatch.id}) is None


def test_shared_verification_cannot_certify_dirty_content_as_saved_commit(dispatch, run, monkeypatch):
    from metaform.modules.dispatch.merge import complete_ticket, deliver_shared, file_fingerprint, ticket_message

    initialize(dispatch.folder)
    run('set', '--dispatch-test-command=grep -q fixed owned.py', cwd=dispatch.folder)
    monkeypatch.setenv('METAFORM_TASK_NAME', 'project_agent')
    record = dispatch.store.finish_work(dispatch.id, 'Fix verified.')
    (dispatch.folder / 'owned.py').write_text('broken\n')
    saved = complete_ticket(dispatch.folder, dispatch.id, ticket_message(dispatch.store, record),
                            {'owned.py': file_fingerprint(dispatch.folder, 'owned.py')}, {})
    (dispatch.folder / 'owned.py').write_text('fixed\n')
    result = deliver_shared(context('dispatch', dispatch.folder, project='proj'), dispatch.store, dispatch.id,
                            saved['committed'])
    assert result['state'] == 'failed'
    assert result['evidence']['verification']['passed'] is False
    assert dispatch.ticket().done
    assert git(dispatch.folder, 'show', 'HEAD:owned.py').stdout == 'broken\n'
    assert (dispatch.folder / 'owned.py').read_text() == 'fixed\n'


def test_failed_shared_check_retry_saves_and_verifies_current_fix(dispatch, run, monkeypatch):
    initialize(dispatch.folder)
    run('set', '--dispatch-test-command=grep -q fixed owned.py', cwd=dispatch.folder)
    made = session_for(dispatch)
    made.acp['ticket_git'] = {'baseline': {}, 'files': {}, 'result': None}
    made.sources = {'owned.py': [{'kind': 'element', 'id': 'owned', 'address': 'code.owned'}]}

    async def note(*args):
        pass

    monkeypatch.setattr(made, 'note', note)
    monkeypatch.setenv('METAFORM_TASK_NAME', 'project_agent')

    async def scenario():
        await edited(made, dispatch.folder / 'owned.py', 'broken\n')
        dispatch.store.finish_work(dispatch.id, 'Fix verified.')
        await made.commit_done()
        assert made.acp['ticket_git']['result']['why']
        assert dispatch.ticket().done
        old = made.acp['ticket_git']['result']['committed']
        await edited(made, dispatch.folder / 'owned.py', 'fixed\n')
        await made.commit_done()
        assert not made.acp['ticket_git']['result']['why']
        assert made.acp['ticket_git']['result']['committed'] != old

    asyncio.run(scenario())
    assert dispatch.ticket().done
    assert git(dispatch.folder, 'show', 'HEAD:owned.py').stdout == 'fixed\n'
    with Store('proj', module='dispatch').tables(write=False) as tx:
        receipt = tx.get('merges', {'work_id': dispatch.id})
    assert receipt['head'] == git(dispatch.folder, 'rev-parse', 'HEAD').stdout.strip()
    assert receipt['evidence']['verification']['passed'] is True
    monkeypatch.delenv('METAFORM_TASK_NAME')
    retained = json.loads(run('map', 'work', f'id={dispatch.id}', '--json', cwd=dispatch.folder).stdout)
    assert retained['dispatch']['completion']['head'] == receipt['head']
    assert retained['dispatch']['completion']['branch'] == 'dev'
    assert retained['dispatch']['completion']['evidence']['artifacts'] == ['owned.py']


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
        await edited(made, dispatch.folder / 'owned.py', 'own edit\n')
        await edited(made, dispatch.folder / 'capture.txt', 'diagnostic\n')
        dispatch.store.finish_work(dispatch.id, 'Owned edit completed.', 'Preserve peer edits.')
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
        dispatch.store.finish_work(dispatch.id, 'Owned edit completed.', 'Preserve peer edits.')
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


def test_shell_edit_commits_without_acp_diff_after_an_open_ticket_attempt(dispatch, monkeypatch):
    from types import SimpleNamespace

    initialize(dispatch.folder)
    made = session_for(dispatch)
    made.acp['ticket_git'] = {'baseline': capture_state(dispatch.folder), 'files': {}, 'result': None}
    made.sources = {'owned.py': [{'kind': 'element', 'id': 'owned', 'address': 'code.owned'}]}

    async def note(*args):
        pass

    monkeypatch.setattr(made, 'note', note)

    async def update(status):
        data = {'sessionUpdate': 'tool_call' if status == 'in_progress' else 'tool_call_update',
                'toolCallId': 'shell', 'kind': 'execute', 'status': status, 'title': 'exec_command'}
        await made.session_update('test', SimpleNamespace(model_dump=lambda **kwargs: data))

    async def scenario():
        await made.commit_done()  # An open ticket must not commit before its edit.
        assert made.acp['ticket_git']['result'] is None
        await update('in_progress')
        (dispatch.folder / 'owned.py').write_text('shell edit\n')
        await update('completed')
        dispatch.store.finish_work(dispatch.id, 'Shell edit completed.', 'Record tool ownership.')
        await made.commit_done()

    asyncio.run(scenario())
    assert made.acp['ticket_git']['result']['committed']
    assert git(dispatch.folder, 'show', '--format=', '--name-only', 'HEAD').stdout.strip() == 'owned.py'
    assert git(dispatch.folder, 'show', 'HEAD:owned.py').stdout == 'shell edit\n'


def test_shell_snapshot_excludes_known_concurrent_peer_write(dispatch):
    import time

    initialize(dispatch.folder)
    made = session_for(dispatch)
    made.session_id = 'ours'
    made.acp['ticket_git'] = {'baseline': {}, 'files': {}, 'result': None}
    made.sources = {'owned.py': [{'kind': 'element', 'id': 'owned', 'address': 'code.owned'}]}
    call = {'kind': 'execute', 'status': 'in_progress'}

    async def scenario():
        await made.track_tool_files('shell', call)
        (dispatch.folder / 'owned.py').write_text('own edit\n')
        (dispatch.folder / 'peer.py').write_text('peer edit\n')
        peer = {'cwd': made.folder, 'ticket_git': {'tool_windows': {}, 'written_at': {'peer.py': time.time_ns()}}}
        with made.store.tables() as tx:
            tx.insert('agent_sessions', {'session_id': 'peer', 'work_id': 'peer-work', 'agent': 'codex',
                                         'state': 'running', 'started': '2026-10-20T00:00:00Z', 'seq': 1})
            tx.insert('session_lines', {'session_id': 'peer', 'work_id': 'peer-work', 'name': 'state',
                                       'kind': 'state', 'text': json.dumps(peer), 'seq': 1})
        call['status'] = 'completed'
        await made.track_tool_files('shell', call)
        dispatch.store.finish_work(dispatch.id, 'Shell edit completed.', 'Preserve peer edits.')
        await made.commit_done()

    asyncio.run(scenario())
    assert set(made.acp['ticket_git']['files']) == {'owned.py'}
    assert made.acp['ticket_git']['result']['committed']
    assert git(dispatch.folder, 'show', '--format=', '--name-only', 'HEAD').stdout.strip() == 'owned.py'
    assert git(dispatch.folder, 'show', 'HEAD:peer.py').stdout == 'before\n'
    assert (dispatch.folder / 'peer.py').read_text() == 'peer edit\n'


def test_overlapping_shell_windows_refuse_ambiguous_ownership(dispatch):
    initialize(dispatch.folder)
    made = session_for(dispatch)
    made.session_id = 'ours'
    made.acp['ticket_git'] = {'baseline': {}, 'files': {}, 'result': None}
    call = {'kind': 'execute', 'status': 'in_progress'}

    async def scenario():
        await made.track_tool_files('shell', call)
        (dispatch.folder / 'owned.py').write_text('unknown writer\n')
        peer = {'cwd': made.folder, 'ticket_git': {'tool_windows': {
            'peer-shell': {'started': made.acp['ticket_git']['tool_windows']['shell']['started'], 'ended': None}}}}
        with made.store.tables() as tx:
            tx.insert('agent_sessions', {'session_id': 'peer', 'work_id': 'peer-work', 'agent': 'codex',
                                         'state': 'running', 'started': '2026-10-20T00:00:00Z', 'seq': 1})
            tx.insert('session_lines', {'session_id': 'peer', 'work_id': 'peer-work', 'name': 'state',
                                       'kind': 'state', 'text': json.dumps(peer), 'seq': 1})
        call['status'] = 'completed'
        await made.track_tool_files('shell', call)

    asyncio.run(scenario())
    assert made.acp['ticket_git']['files'] == {}
    assert 'Overlapping' in made.acp['ticket_git']['attribution_error']


def test_idle_peer_with_window_journal_allows_shell_attribution(dispatch):
    initialize(dispatch.folder)
    made = session_for(dispatch)
    made.session_id = 'ours'
    made.acp['ticket_git'] = {'baseline': {}, 'files': {}, 'tool_windows': {}, 'result': None}
    peer = {'cwd': made.folder, 'ticket_git': {'files': {}, 'written_at': {}, 'tool_windows': {}}}
    with made.store.tables() as tx:
        tx.insert('agent_sessions', {'session_id': 'idle-peer', 'work_id': 'peer-work', 'agent': 'codex',
                                     'state': 'running', 'started': '2026-10-20T00:00:00Z', 'seq': 1})
        tx.insert('session_lines', {'session_id': 'idle-peer', 'work_id': 'peer-work', 'name': 'state',
                                   'kind': 'state', 'text': json.dumps(peer), 'seq': 1})
    call = {'kind': 'execute', 'status': 'in_progress'}

    async def scenario():
        await made.track_tool_files('shell', call)
        (dispatch.folder / 'owned.py').write_text('own edit\n')
        call['status'] = 'completed'
        await made.track_tool_files('shell', call)

    asyncio.run(scenario())
    assert set(made.acp['ticket_git']['files']) == {'owned.py'}
    assert not made.acp['ticket_git'].get('attribution_error')


@pytest.mark.parametrize('active_shell', [False, True])
def test_ticketless_peer_journal_distinguishes_idle_from_shell_overlap(dispatch, active_shell):
    initialize(dispatch.folder)
    made = session_for(dispatch)
    made.session_id = 'ours'
    made.acp['ticket_git'] = {'baseline': {}, 'files': {}, 'result': None}
    peer = session_for(dispatch)
    peer.session_id = 'system-peer'
    assert peer.acp['ticket_git'] is None
    assert peer.acp['tool_windows'] == {}
    with made.store.tables() as tx:
        tx.insert('agent_sessions', {'session_id': peer.session_id, 'work_id': peer.work_id, 'agent': 'codex',
                                     'state': 'running', 'started': '2026-10-20T00:00:00Z', 'seq': 1})
    call = {'kind': 'execute', 'status': 'in_progress'}
    peer_call = {'kind': 'execute', 'status': 'in_progress'}

    async def scenario():
        await peer.save_state()
        await made.track_tool_files('shell', call)
        if active_shell:
            await peer.track_tool_files('system-shell', peer_call)
        (dispatch.folder / 'owned.py').write_text('shell edit\n')
        call['status'] = 'completed'
        await made.track_tool_files('shell', call)
        if active_shell:
            peer_call['status'] = 'completed'
            await peer.track_tool_files('system-shell', peer_call)

    asyncio.run(scenario())
    if active_shell:
        assert made.acp['ticket_git']['files'] == {}
        assert 'Overlapping' in made.acp['ticket_git']['attribution_error']
        assert peer.acp['tool_windows']['system-shell']['ended'] is not None
    else:
        assert set(made.acp['ticket_git']['files']) == {'owned.py'}
        assert not made.acp['ticket_git'].get('attribution_error')


def test_native_child_shell_commits_while_parent_delegation_is_open(dispatch, monkeypatch):
    from types import SimpleNamespace

    initialize(dispatch.folder)
    made = session_for(dispatch)
    made.session_id = 'ours'
    made.acp['ticket_git'] = {'baseline': {}, 'files': {}, 'result': None}
    made.sources = {'owned.py': [{'kind': 'element', 'id': 'owned', 'address': 'code.owned'}]}
    made.children['child'] = {'flow': None, 'tools': {}}
    parent_call = {'kind': 'other', 'status': 'in_progress', 'title': 'Delegate task'}

    async def note(*args):
        pass

    monkeypatch.setattr(made, 'note', note)
    monkeypatch.setattr(made, 'child_note', note)

    async def child_update(status):
        data = {'sessionUpdate': 'tool_call' if status == 'in_progress' else 'tool_call_update',
                'toolCallId': 'shell', 'kind': 'execute', 'status': status, 'title': 'exec_command'}
        await made.session_update('child', SimpleNamespace(model_dump=lambda **kwargs: data))

    async def scenario():
        await made.track_tool_files('delegate', parent_call)
        await child_update('in_progress')
        (dispatch.folder / 'owned.py').write_text('child shell edit\n')
        await child_update('completed')
        parent_call['status'] = 'completed'
        await made.track_tool_files('delegate', parent_call)
        dispatch.store.finish_work(dispatch.id, 'Child edit completed.', 'Retain child ownership.')
        await made.commit_done()

    asyncio.run(scenario())
    assert made.acp['ticket_git']['result']['committed']
    assert git(dispatch.folder, 'show', '--format=', '--name-only', 'HEAD').stdout.strip() == 'owned.py'
    assert git(dispatch.folder, 'show', 'HEAD:owned.py').stdout == 'child shell edit\n'
