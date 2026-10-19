"""Two live project sessions exchange threaded notes and survive project/base selection."""
import json
import sys

import pytest

from metaform import home as registry
from metaform.data import Node, Store
from metaform.modules.dispatch.tests.test_dispatch import FAKE, NODE, Dispatch, eventually

pytestmark = pytest.mark.kind('simulation')


def test_live_project_routing_and_reply_keep_original_sessions(run, home, project_folder, tmp_path):
    first = Dispatch(run, home, project_folder, tmp_path)
    other_folder = tmp_path / 'other'
    other_folder.mkdir()
    run('add', 'project', 'other', str(other_folder))
    run('set', '--dispatch-claude', f'"{sys.executable}" "{FAKE}"', cwd=other_folder)
    second = Dispatch.__new__(Dispatch)
    second.run, second.home, second.folder = run, home, other_folder
    second.log, second.process = tmp_path / 'other.jsonl', None
    second.store = Store('other')
    second.store.layer('parts', 'test', 'Functional parts.', mutable=True, hideable=True, ready=True)
    second.store.add_element('parts', NODE)
    second.node = Node('element', NODE)
    second.id = second.store.add_work(second.node, None, task='Hold the other project contribution.').id
    def session(project):
        with Store(project, module='dispatch').tables(write=False) as tx:
            return next((row for row in tx.rows('agent_sessions', limit=0).results if row['state'] == 'running'), None)
    def command(runner, row, *words):
        return json.loads(run('dispatch', 'note', '--json', *words, cwd=runner.folder, env={
            'METAFORM_ROLE': 'worker', 'METAFORM_WORK': runner.id, 'METAFORM_SESSION': row['runner']}).stdout)
    try:
        first.start('hold', 'system=true')
        second.start('hold')
        eventually(lambda: first.received('session/prompt') and second.received('session/prompt'))
        a, b = session('proj'), session('other')
        original_base = b['base']
        registry.add_base('other', 'another-map', activate=True)
        sent = command(first, a, 'target_project=other', f'to={b["session_id"]}', '--', 'Keep the alarm interface.')
        assert sent['sent'] and sent['to'][0]['project'] == 'other'
        reply = command(second, b, f'reply={sent["note"]}', '--', 'The interface is retained.')
        assert reply['sent'] and reply['to'][0]['project'] == 'proj'
        # Selection changes no running process or session identity.
        assert first.process.poll() is None and second.process.poll() is None
        assert session('proj')['session_id'] == a['session_id']
        assert session('other')['session_id'] == b['session_id']
        from metaform.modules.dispatch.peering import peer_lines
        notes = peer_lines(first.store, first.id)
        returned = next(one for one in notes if one.get('reply_to') == sent['note'])
        assert returned['from']['project'] == 'other'
        assert returned['from']['base'] == original_base
        assert returned['from']['session_id'] == b['session_id']
        shown = json.loads(run('dispatch', 'notes', '--json', cwd=first.folder, env={
            'METAFORM_ROLE': 'worker', 'METAFORM_WORK': first.id, 'METAFORM_SESSION': a['runner']}).stdout)
        received = next(one for one in shown['notes'] if one['note'] == reply['note'])
        assert received['way'] == 'received' and received['from']['project'] == 'other'

        # Replies consumed by a waiting tool carry the same read receipt back to the other project.
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=1) as pool:
            waiting = pool.submit(command, first, a, 'target_project=other', f'to={b["session_id"]}',
                                  'wait=10', '--', 'Can the alarm retain this interface?')
            question = eventually(lambda: next((one for one in peer_lines(second.store, second.id)
                                                if one.get('ask')), None))
            response = command(second, b, f'reply={question["id"]}', '--', 'Yes, it is retained.')
            result = waiting.result(timeout=15)
        assert result['replies'][0]['note'] == response['note'] and not result['unanswered']
        receipt = next(one for one in peer_lines(second.store, second.id) if one['id'] == response['note'])
        assert receipt['session_states'][a['session_id']] == 'read'
    finally:
        first.close()
        second.close()


def test_reconnected_runner_does_not_repeat_an_acknowledged_peer_note(run, home, project_folder, tmp_path):
    import asyncio

    from metaform.module import context
    from metaform.modules.dispatch.runner import Session
    from metaform.modules.dispatch.signals import add_line

    live = Dispatch(run, home, project_folder, tmp_path)
    note = {'id': 'durable-note', 'from': {'project': 'other', 'session_id': 'sender'},
            'text': 'Keep the interface.', 'session_states': {'receiver': 'delivered'}}
    store = Store('proj', module='dispatch')
    with store.tables() as tx:
        add_line(tx, 'receiver', live.id, 'peer:durable-note', 'peer', json.dumps(note))
    resumed = Session(context('dispatch', project_folder, project='proj'), store, live.ticket(), 'claude', ['unused'])
    resumed.session_id = 'receiver'
    answer = asyncio.run(resumed.peer_note({'line': note, 'deliver': True}))
    assert answer['reused'] and not resumed.pending


@pytest.mark.kind('fixture')
def test_reply_returned_while_its_thread_is_written_is_not_also_queued(run, home, project_folder, tmp_path):
    import asyncio
    import time

    from metaform.module import context
    from metaform.modules.dispatch.runner import Session

    live = Dispatch(run, home, project_folder, tmp_path)
    held = Session(context('dispatch', project_folder, project='proj'), Store('proj', module='dispatch'),
                   live.ticket(), 'claude', ['unused'])
    held.session_id = 'receiver'
    held.awaiting['question'] = {'until': time.monotonic() + 10, 'held': []}
    async def note(*args):
        # The waiting tool can observe the committed reply before its publishing callback returns.
        held.unawait({'id': 'question', 'taken': ['reply']})
    held.note = note
    reply = {'id': 'reply', 'reply_to': 'question', 'from': {'session_id': 'sender'}, 'text': 'Yes.'}
    answer = asyncio.run(held.peer_note({'line': reply, 'deliver': True}))
    assert answer['reused'] and not held.pending and not held.awaiting
