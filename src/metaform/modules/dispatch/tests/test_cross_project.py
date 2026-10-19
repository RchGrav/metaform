"""Two live project sessions exchange threaded notes and survive project/base selection."""
import json
import sys

import pytest

from metaform import home as registry
from metaform.data import Node, Store
from metaform.modules.dispatch.tests.test_dispatch import NODE, Dispatch, eventually

pytestmark = pytest.mark.kind('simulation')


def test_live_project_routing_and_reply_keep_original_sessions(run, home, project_folder, tmp_path):
    first = Dispatch(run, home, project_folder, tmp_path)
    other_folder = tmp_path / 'other'
    other_folder.mkdir()
    run('add', 'project', 'other', str(other_folder))
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


def test_the_same_words_sent_twice_by_note_reach_a_session_once(run, home, project_folder, tmp_path):
    """Two notes from one sender with the same words and different ids, the first still waiting for its turn, are
    one: the second is marked delivered, never given again; another sender's same words, and a reply, still arrive.
    Once a turn has carried the first, the same words come again, and so does the person's decision relayed again
    from a new message of theirs."""
    import asyncio

    from metaform.module import context
    from metaform.modules.dispatch.runner import Session

    live = Dispatch(run, home, project_folder, tmp_path)
    resumed = Session(context('dispatch', project_folder, project='proj'), Store('proj', module='dispatch'),
                      live.ticket(), 'claude', ['unused'])
    resumed.session_id, resumed.turns = 'receiver', 1  # a turn in flight: the notes wait as prompts

    def line(note_id, sender, text, reply_to=None, kind='peer', decision=None):
        return {'id': note_id, 'kind': kind, 'from': {'session_id': sender}, 'text': text, 'reply_to': reply_to,
                'to': [{'work_id': live.id, 'session_id': 'receiver'}], 'session_states': {'receiver': 'queued'},
                **({'decision': {'id': decision}} if decision else {})}

    def carried():  # the turn in flight ends and the next takes the prompt waiting first, as `prompted` does
        for queue in (resumed.pending, resumed.prompt_versions, resumed.prompt_contexts, resumed.voiced,
                      resumed.peered, resumed.worded, resumed.typed):
            if queue:
                queue.popleft()
        resumed.priority_count = max(0, resumed.priority_count - 1)

    async def delivered():
        answers = [await resumed.peer_note({'line': one, 'deliver': True}) for one in (
            line('first', 'system', 'Remove the camera clearance.'),
            line('again', 'system', 'Remove  the camera clearance. '),
            line('other', 'peer', 'Remove the camera clearance.'),
            line('yes-1', 'peer', 'yes', reply_to='q1'), line('yes-2', 'peer', 'yes', reply_to='q2'))]
        waiting = [note_id for marks in resumed.peered for note_id, _ in marks]
        carried()
        answers.append(await resumed.peer_note({'line': line('later', 'system', 'Remove the camera clearance.'),
                                                'deliver': True}))
        for note_id, decision in (('d1', 'msg-1'), ('d2', 'msg-2')):
            answers.append(await resumed.peer_note({'line': line(note_id, 'system', 'Stop building the camera.',
                                                                 kind='user_direction', decision=decision),
                                                    'deliver': True}))
            carried()
        await asyncio.sleep(0.1)  # the delivered mark the second note takes
        return answers, waiting
    answers, waiting = asyncio.run(delivered())
    assert [bool(one.get('same_text')) for one in answers] == [False, True, False, False, False, False, False, False]
    assert waiting == ['first', 'other', 'yes-1', 'yes-2']  # the notes that waited joined one turn
    assert [note_id for marks in resumed.peered for note_id, _ in marks] == ['later']


def test_a_gc_check_in_result_reaches_the_system_agents_session_once(run, home, project_folder, tmp_path,
                                                                      monkeypatch):
    """code.router.assignment#f: a GC's returned check-in is one entry in the person's system agent's inbox, though
    its first relay fails, two drains run at once, a drain runs again, another process replays the notification, the
    session is handed to a runner on newer code, the resumed runner replays its notes and its project updates, and a
    new conversation of the system agent starts; an update written while none ran is given to the next one alone,
    named by its ticket and kind (code.dispatcher.agent#72)."""
    import asyncio
    import importlib
    import os
    from concurrent.futures import ThreadPoolExecutor
    from contextvars import copy_context

    from metaform.module import context, provided, refresh_modules

    live = Dispatch(run, home, project_folder, tmp_path, orchestration=True)
    run('set', '--orchestration-reviews', '0', cwd=project_folder)  # no assessment launches a runner here
    gc_work = live.store.add_work(live.node, None, task='Count only open tickets toward the held cap.').id
    refresh_modules()
    transport = provided(project_folder, 'orchestration.transport')[0][1]
    owner = provided(project_folder, 'orchestration')[0][1]
    module = sys.modules[type(transport).__module__.rpartition('.')[0]]  # dispatch, as the loader runs it
    monkeypatch.setattr(module, 'runner_of', lambda pid: live.id)  # this process stands for the system's runner

    def conversation(session_id, state='running'):  # one conversation of the person's system agent
        with Store('proj', module='dispatch').tables() as tx:
            if tx.get('agent_sessions', {'session_id': session_id}) is not None:
                tx.update('agent_sessions', {'session_id': session_id}, {'state': state})
                return
            tx.insert('agent_sessions', {'session_id': session_id, 'work_id': live.id, 'agent': 'claude',
                                         'state': state, 'pid': os.getpid(), 'runner': f'r-{session_id}',
                                         'started': '2026-10-19T00:00:00Z', 'seq': 1, 'origin': module.origin()})
            tx.insert('session_lines', {'session_id': session_id, 'name': 'state', 'work_id': live.id, 'kind': 'state',
                                        'text': json.dumps({'about': 'system', 'role': 'system'}), 'seq': 1})
    conversation('system')
    told: list[dict] = []
    failing = [True]

    def tell(row, op, **given):
        if op != 'note':
            return {}
        if failing.pop() if failing else False:
            raise OSError('The runner did not answer in time.')
        told.append(given['line'])
        return {'noted': True}
    monkeypatch.setattr(module, 'tell', tell)

    def ctx(**nouns):
        return context('orchestration', project_folder, project='proj', session='gc', nouns=nouns)
    owner.claim(ctx(work=gc_work, session='gc', pm_session='system'))
    owner.check_in(ctx(state='returned', summary='The held cap counts only open, not-held tickets.'))

    def drain():
        return copy_context().run(owner.drain, ctx())
    drain()
    assert told == [] and not failing, 'the first relay failed'
    with ThreadPoolExecutor(max_workers=2) as pool:  # two drains at once, as two processes' do
        list(pool.map(lambda _: drain(), range(2)))
    drain()
    assert told, 'a relay that failed is sent again'
    # another process that read the transition as pending before it was marked delivered relays it again
    transport.notify_user(context('dispatch', project_folder, project='proj'), {**told[0], 'message_id': told[0]['id']},
                          told[0]['id'])
    line = told[0]
    assert {one['id'] for one in told} == {line['id']} and 'held cap' in line['text']
    Session = importlib.import_module(f'{module.__name__}.runner').Session

    def session(session_id='system'):
        made = Session(context('dispatch', project_folder, project='proj', nouns={'system': True}),
                       Store('proj', module='dispatch'), live.ticket(), 'claude', ['unused'])
        made.session_id, made.turns = session_id, 1  # a turn in flight: notes wait as prompts
        return made
    first = session()

    async def received():  # every relay the runner is told of
        for one in told:
            await first.peer_note({'line': one, 'deliver': True})
    asyncio.run(received())
    assert [one[0] for one in first.inbox] == [line['id']] and not first.pending, 'one inbox entry, no turn'
    assert 'held cap' not in first.inbox[0][2], 'the inbox names it by ticket and kind, never its words'

    # handed to a runner on newer code; the new runner replays its notes and updates into one inbox entry
    path = module.handed_path('system')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'carried': []}), encoding='utf-8')
    taken = session()

    async def resumed():
        await taken.taken_over()
        await taken.replay_peers()
        await taken.updates_due()
    asyncio.run(resumed())
    assert [one[0] for one in taken.inbox] == [line['id']] and not taken.pending
    asyncio.run(taken.peer_marked([(line['id'], '')], 'delivered'))  # the turn carrying its inbox line went out

    # the conversation ends; an update arrives while no system agent runs, and the next conversation starts
    conversation('system', 'ended')
    transport.notify_user(context('dispatch', project_folder, project='proj'),
                          {'body': 'The web log now rotates daily.', 'kind': 'result', 'state': 'returned',
                           'work_id': gc_work}, 'offline-1')
    conversation('system-2')
    second = session('system-2')
    asyncio.run(second.updates_due())
    gc_item = live.store.numbers_of('work', [gc_work])[gc_work][0]
    assert second.inbox == [('offline-1', '', f'{gc_item} returned', True)], second.inbox

    async def accepted():  # the turn carrying its inbox line went out
        second.inflight_updates = ['offline-1']
        second.context_delivered()
        await asyncio.sleep(0.5)
    asyncio.run(accepted())
    conversation('system-2', 'ended')
    conversation('system-3')
    third = session('system-3')
    asyncio.run(third.updates_due())
    assert third.inbox == [], 'no update reaches a third conversation again'


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


def test_notes_that_arrive_while_one_waits_for_its_turn_join_that_turn(run, home, project_folder, tmp_path):
    """A burst of notes behind a turn in flight is one turn, not one each, so the last is not hours behind the first;
    the person's message still goes ahead of them, and a relayed decision never joins a note's turn."""
    import asyncio

    from metaform.module import context
    from metaform.modules.dispatch.runner import Session

    live = Dispatch(run, home, project_folder, tmp_path)
    held = Session(context('dispatch', project_folder, project='proj'), Store('proj', module='dispatch'),
                   live.ticket(), 'claude', ['unused'])
    held.session_id, held.turns = 'receiver', 1  # a turn in flight: what comes waits

    def line(note_id, sender, text, kind='peer'):
        return {'id': note_id, 'kind': kind, 'from': {'session_id': sender}, 'text': text,
                'to': [{'work_id': live.id, 'session_id': 'receiver'}], 'session_states': {'receiver': 'queued'}}

    async def burst():
        for number in range(5):
            await held.peer_note({'line': line(f'n{number}', f's{number}', f'Finding {number}.'), 'deliver': True})
        held.turn('The person asks something.', first=True, typed=True)
        await held.peer_note({'line': line('d1', 'system', 'The person decided.', 'user_direction'), 'deliver': True})
    asyncio.run(burst())
    assert len(held.pending) == 3, list(held.pending)
    assert held.pending[0] == 'The person asks something.' and 'The person decided.' in held.pending[1]
    assert all(f'Finding {number}.' in held.pending[2] for number in range(5))
    assert [note_id for note_id, _ in held.peered[2]] == [f'n{number}' for number in range(5)]


def test_two_projects_system_agents_exchange_a_note_and_reply_each_side_in_each_persons_chat(run, home, project_folder,
                                                                                            tmp_path):
    """A's system agent notes B's with to=system target_project=: it waits in B's agent's inbox, and B's next turn
    names it in one line, never its words (code.dispatcher.agent#72); B's reply reaches A the same way; and the person's chat in
    each project, `dispatch sessions`, shows the note and the reply, each with its sender's project named. A system
    agent with no session running is never refused: a reply to it, or a note to it, waits in its last conversation and
    is given to its next session, a new conversation included."""
    first = Dispatch(run, home, project_folder, tmp_path)
    other_folder = tmp_path / 'other'
    other_folder.mkdir()
    run('add', 'project', 'other', str(other_folder))
    second = Dispatch.__new__(Dispatch)
    second.run, second.home, second.folder = run, home, other_folder
    second.log, second.process = tmp_path / 'other.jsonl', None
    second.store = Store('other')
    second.store.layer('parts', 'test', 'Functional parts.', mutable=True, hideable=True, ready=True)
    second.store.add_element('parts', NODE)
    second.node = Node('element', NODE)
    second.id = second.store.add_work(second.node, None, task='Hold the other project contribution.').id

    def live(project, but=()):
        with Store(project, module='dispatch').tables(write=False) as tx:
            return next((row for row in tx.rows('agent_sessions', limit=0).results
                         if row['state'] == 'running' and row['session_id'] not in but), None)

    def command(runner, row, *words):
        return json.loads(run('dispatch', 'note', '--json', *words, cwd=runner.folder, env={
            'METAFORM_ROLE': 'system', 'METAFORM_WORK': runner.id, 'METAFORM_SESSION': row['runner']}).stdout)

    def chat(runner):
        lines = json.loads(run('dispatch', 'sessions', f'id={runner.id}', '--json', cwd=runner.folder).stdout)['lines']
        return {line['data']['id']: line['data'] for line in lines if line['kind'] == 'peer'}

    def given(runner, words):
        return [one for one in runner.received('session/prompt') if words in json.dumps(one)]
    try:
        first.start('plain', 'system=true')  # a first turn that ends, so a note is given as the next turn
        second.start('plain', 'system=true')
        eventually(lambda: first.received('session/prompt') and second.received('session/prompt'))
        a, b = eventually(lambda: live('proj')), eventually(lambda: live('other'))
        sent = command(first, a, 'target_project=other', 'to=system', '--', 'Intake fails on an empty folder.')
        assert sent['to'][0]['project'] == 'other' and sent['to'][0]['session_id'] == b['session_id'], sent
        # the note waits in B's inbox: no turn of its own, and B's next turn names it in one line, never its words
        run('dispatch', 'message', second.id, '--', 'Anything new?', cwd=second.folder)
        turn = json.dumps(eventually(lambda: given(second, 'new in your inbox')))
        assert 'Intake fails on an empty folder.' not in turn and 'Anything new?' in turn, turn
        reply = command(second, b, f'reply={sent["note"]}', '--', 'Filed here as a ticket.')
        assert reply['to'][0]['project'] == 'proj' and reply['to'][0]['session_id'] == a['session_id'], reply
        run('dispatch', 'message', first.id, '--', 'Anything new?', cwd=first.folder)
        turn = json.dumps(eventually(lambda: given(first, 'new in your inbox')))
        assert 'Filed here as a ticket.' not in turn, turn
        for runner in (first, second):  # both sides in the person's chat of each project, the sender named
            shown = eventually(lambda runner=runner: (found := chat(runner)).keys() >= {sent['note'], reply['note']}
                               and found)
            assert shown[sent['note']]['from']['project'] == 'proj' and shown[sent['note']]['text'] == \
                'Intake fails on an empty folder.'
            assert shown[reply['note']]['from']['project'] == 'other' and \
                shown[reply['note']]['reply_to'] == sent['note']
        # A's session ends: B's next reply is not refused but waits for A's next session, a new conversation here,
        # whose opening turn names it in its inbox line
        first.close()
        again = command(second, b, f'reply={sent["note"]}', '--', 'It is fixed now.')
        assert again['to'][0]['project'] == 'proj' and again['to'][0]['turn'] == 'when its next session starts'
        before = len(first.received('session/prompt'))
        first.start('plain', 'system=true')
        c = eventually(lambda: live('proj', but=(a['session_id'],)))
        opening = json.dumps(eventually(lambda: first.received('session/prompt')[before:]))
        assert 'new in your inbox' in opening and 'It is fixed now.' not in opening, opening
        # and the other way: no system session runs in B's project, so the note waits for its next one
        second.close()
        later = command(first, c, 'target_project=other', 'to=system', '--', 'Its help text is stale too.')
        assert later['to'][0]['turn'] == 'when its next session starts', later
        before = len(second.received('session/prompt'))
        second.start('plain', 'system=true')
        opening = json.dumps(eventually(lambda: second.received('session/prompt')[before:]))
        assert 'new in your inbox' in opening and 'Its help text is stale too.' not in opening, opening
    finally:
        first.close()
        second.close()
