"""Real ticket and board persistence for cooperative worksheet execution over worktrees."""
from __future__ import annotations

import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from metaform.module import Stop

pytestmark = pytest.mark.kind('fixture')

NODE = 'code.timer.kitchen'
NODES = ['code.Exact_Name', 'Unknown.Unexpanded.Node']
FULL = {'Efficient': 5, 'Alert & Aware': 5, 'Thorough': 5, 'Coordination': 5}


@pytest.fixture
def working(project_folder, tmp_path, monkeypatch):
    from metaform import events
    from metaform.data import Store
    from metaform.module import context
    from metaform.modules.tasks import protocol
    from metaform.modules.tasks.board import Board

    monkeypatch.setenv('TMPDIR', str(tmp_path / 'temporary'))
    monkeypatch.delenv('METAFORM_TASK', raising=False)
    published = []
    monkeypatch.setattr(events, 'publish', lambda topic, payload, source: published.append((topic, payload)) or [])
    store = Store('proj')
    with store.atomic():
        layer = store.layer('test-map', 'intake', 'Test map.', kind='intake', mutable=False,
                            hideable=False, provenance={'module': 'intake'}, ready=True)
        store.add_element(layer.name, NODE, name_length=2, role='DE')
    board = Board('proj')
    for ident in ('alice', 'bob', 'carol'):
        board.register(ident, ident.title(), f'work-{ident}')

    def call(verb, *, identity=None, **nouns):
        ctx = context('tasks', project_folder, nouns=nouns, identity=identity or {})
        return getattr(protocol, verb)(ctx)

    return SimpleNamespace(call=call, board=board, store=store, published=published, protocol=protocol,
                           folder=project_folder)


def registered(working, *, holder='alice', partner='bob', summary='Fix the kitchen timer', items=None, worktree=None):
    ticket = working.call('ticket', node=NODE, summary=summary, text='Repair and verify the timer behavior.',
                          **({'worktree': worktree} if worktree else {}))['ticket']
    round_ = working.call('worksheet', worktree=worktree or ticket, holder=holder, partner=partner,
                          items=items if items is not None else ['Inspect the timer', 'Verify the correction'],
                          nodes=list(NODES))
    return ticket, round_


def checked(working, worktree, round_):
    for item in round_['items']:
        working.call('check', worktree=worktree, item=item['id'])


def ratings(working, worktree):
    first = working.call('rate', worktree=worktree, reviewer='alice', target='bob', scores={**FULL, 'Coordination': 4})
    second = working.call('rate', worktree=worktree, reviewer='bob', target='alice', scores=FULL, bonus=True)
    return first, second


def repository(folder):
    """The project folder made a git repository with one commit, as the person's checkout."""
    def git(*words):
        return subprocess.run(['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', *words],
                              cwd=folder, check=True, capture_output=True, text=True)
    git('init', '-q')
    (folder / 'README').write_text('one\n', encoding='utf-8')
    git('add', 'README')
    git('commit', '-q', '-m', 'start')
    return git


def test_a_ticket_without_a_worktree_is_one_of_its_own_and_checks_project_into_it_without_inflation(working):
    ticket, round_ = registered(working)
    record = working.store.ticket(ticket).work
    assert working.store.numbers_of('work', [ticket])[ticket][1] == 'Fix the kitchen timer'
    assert record.task == 'Repair and verify the timer behavior.'
    assert (record.steps, record.steps_done) == (2, 0)
    assert round_['tickets'] == [ticket]
    item = round_['items'][0]['id']
    working.call('check', worktree=ticket, item=item)
    working.call('check', worktree=ticket, item=item)
    record = working.store.ticket(ticket).work
    assert (record.steps, record.steps_done) == (2, 1)
    assert record.said == ()  # Checking a worksheet must not fabricate a completed-step narrative.
    working.call('check', worktree=ticket, item=item, done=False)
    assert working.store.ticket(ticket).work.steps_done == 0
    edited = working.call('worksheet', worktree=ticket, holder='alice', partner='bob',
                          items=['Inspect the timer', 'Verify the correction'], nodes=list(NODES))
    assert [item['id'] for item in edited['items']] == [item['id'] for item in round_['items']]
    assert working.call('worksheet', worktree=ticket)['nodes'] == NODES


def test_fully_checked_worksheet_appends_once_and_retains_participant_notes(working):
    ticket, round_ = registered(working)
    working.store.edit_work(ticket, {'note': 'Existing evidence from a participant.'})
    checked(working, ticket, round_)
    record = working.store.ticket(ticket).work
    assert (record.steps, record.steps_done) == (2, 2)
    assert not record.done  # Worksheet progress and the ratings at the close are separate observations.
    marker = f'Completed worksheet ({ticket})'
    assert record.note.count(marker) == 1
    assert '[x] Inspect the timer' in record.note and '[x] Verify the correction' in record.note
    working.store.edit_work(ticket, {'note': record.note + '\n\nLater participant evidence.'})
    working.call('check', worktree=ticket, item=round_['items'][-1]['id'])
    note = working.store.ticket(ticket).work.note
    assert note.count(marker) == 1
    assert note.startswith('Existing evidence from a participant.')
    assert note.endswith('Later participant evidence.')


def test_every_participants_pick_closes_the_worktree_and_one_does_not(working):
    ticket, round_ = registered(working)
    checked(working, ticket, round_)
    first = working.call('rate', worktree=ticket, reviewer='alice', target='bob', scores=FULL)
    assert first['completed'] is False and not working.store.ticket(ticket).work.done
    second = working.call('rate', worktree=ticket, reviewer='bob', alone=True)
    assert second['completed'] is True and second['points'] is None and second['target'] is None
    assert working.store.ticket(ticket).work.done
    assert working.board.round(ticket)['completed'] is True
    repeated = working.call('rate', worktree=ticket, reviewer='bob', alone=True)
    assert repeated['completed'] is True
    assert len(working.board.ratings(ticket)) == 2
    assert working.store.ticket(ticket).work.note.count(f'Completed worksheet ({ticket})') == 1
    assert working.call('view')['worktrees'] == []


def test_a_rating_names_stars_in_every_category_unless_alone(working):
    ticket, _ = registered(working)
    with pytest.raises(Stop, match='each category'):
        working.call('rate', worktree=ticket, reviewer='alice', target='bob')
    with pytest.raises(Stop, match='missing Coordination'):
        working.call('rate', worktree=ticket, reviewer='alice', target='bob',
                     scores={'Efficient': 5, 'Alert & Aware': 5, 'Thorough': 5})
    assert working.board.ratings(ticket) == [] and working.board.worker('bob')['score'] is None


def test_native_actor_attribution_overrides_claimed_reviewer(working):
    ticket, _ = registered(working)
    result = working.call('rate', worktree=ticket, reviewer='claimed-other', target='alice',
                          scores={**FULL, 'Thorough': 3}, identity={'METAFORM_TASK': 'bob'})
    assert result['reviewer'] == 'bob' and result['points'] == 88
    assert working.board.ratings(ticket) == [
        {'worktree': ticket, 'reviewer': 'bob', 'target': 'alice', 'alone': False, 'stars': {**FULL, 'Thorough': 3},
         'bonus': False, 'points': 88, 'change': 88, 'context': '', 'applied': 88}]
    assert working.board.worker('alice')['score'] == 88


def test_peer_board_hides_own_row_and_score_and_preserves_exact_node_strings(working):
    ticket, round_ = registered(working)
    assert working.call('view')['worktrees'] == [
        {'worktree': ticket, 'tickets': [{'ticket': ticket, 'title': 'Fix the kitchen timer', 'taken': True, 'held': False}], 'agents': [],
         'phrase': 'Fix the kitchen timer', 'holder': 'alice', 'partner': 'bob', 'checked': 0, 'total': 2}]
    checked(working, ticket, round_)
    ratings(working, ticket)
    own_view = working.call('view', identity={'METAFORM_TASK': 'alice'})['agents']
    assert {row['agent_id'] for row in own_view} == {'bob', 'carol'}
    bob = next(row for row in own_view if row['agent_id'] == 'bob')
    assert bob['score'] == 92
    assert bob['past'] == [{'worktree': ticket, 'phrase': 'Fix the kitchen timer', 'tickets': [ticket],
                            'nodes': NODES, 'points': 92}]
    assert all(row['score'] != 105 for row in own_view)
    human_view = working.call('view')['agents']
    alice = next(row for row in human_view if row['agent_id'] == 'alice')
    assert alice['score'] == 105 and alice['past'][0]['nodes'] == NODES


def test_composer_worktree_groups_tickets_and_the_claim_takes_them_all(working):
    one = working.call('ticket', node=NODE, summary='Timer face', text='Draw the face.', worktree='timer')
    two = working.call('ticket', node=NODE, summary='Timer bell', text='Ring the bell.', worktree='timer')
    assert one['worktree'] == two['worktree'] == 'timer'
    free, = working.call('view')['worktrees']
    assert (free['worktree'], free['holder'], free['total']) == ('timer', None, 0)
    assert sorted((t['ticket'], t['title'], t['taken']) for t in free['tickets']) == sorted(
        [(one['ticket'], 'Timer face', False), (two['ticket'], 'Timer bell', False)])
    round_ = working.call('worksheet', worktree='timer', holder='alice', items=[
        {'text': 'Face', 'ticket': one['ticket']}, {'text': 'Bell', 'ticket': two['ticket']}, 'Shared check'], nodes=[])
    assert sorted(round_['tickets']) == sorted([one['ticket'], two['ticket']])
    assert round_['folder'] is None and 'not a git repository' in round_['notice']
    face, bell = working.store.ticket(one['ticket']).work, working.store.ticket(two['ticket']).work
    assert face.taken_by == 'alice' and bell.taken_by == 'alice'
    assert (face.steps, bell.steps) == (2, 2), 'each ticket counts its own items and the shared'
    checked(working, 'timer', round_)
    assert working.call('rate', worktree='timer', reviewer='alice', alone=True)['completed'] is True
    face, bell = working.store.ticket(one['ticket']).work, working.store.ticket(two['ticket']).work
    assert face.done and bell.done
    assert '[x] Face' in face.note and '[x] Shared check' in face.note and '[x] Bell' not in face.note
    assert '[x] Bell' in bell.note and '[x] Shared check' in bell.note and '[x] Face' not in bell.note
    with pytest.raises(Stop, match='No open ticket'):
        working.call('worksheet', worktree='timer', holder='alice', items=['Again'])


def test_an_empty_worksheet_is_refused_and_claims_nothing(working):
    ticket = working.call('ticket', node=NODE, summary='Timer', text='Fix it.')['ticket']
    with pytest.raises(Stop, match='at least one item'):
        working.call('worksheet', worktree=ticket, holder='alice', items=[])
    assert working.board.round(ticket) is None and not working.store.ticket(ticket).work.taken


def test_a_ticket_in_another_worktree_is_not_claimable_under_its_own_id(working):
    one = working.call('ticket', node=NODE, summary='Face', text='Draw it.', worktree='timer')['ticket']
    with pytest.raises(Stop, match='No open ticket'):
        working.call('worksheet', worktree=one, holder='alice', items=['x'])
    assert working.call('worksheet', worktree='timer')['tickets'] == [one]


def test_a_ticket_written_into_a_claimed_worktree_joins_the_round_and_is_taken(working):
    one = working.call('ticket', node=NODE, summary='Face', text='Draw it.', worktree='timer')['ticket']
    round_ = working.call('worksheet', worktree='timer', holder='alice', items=['Shared'], nodes=[])
    two = working.call('ticket', node=NODE, summary='Bell', text='Ring it.', worktree='timer')['ticket']
    assert working.board.round('timer')['tickets'] == [one, two]
    bell = working.store.ticket(two).work
    assert bell.taken_by == 'alice' and bell.steps == 1
    checked(working, 'timer', round_)
    assert working.call('rate', worktree='timer', reviewer='alice', alone=True)['completed'] is True
    assert working.store.ticket(two).work.done and working.call('view')['worktrees'] == []


def test_a_participant_gone_offline_is_recorded_alone_so_the_worktree_can_close(working):
    from metaform.module import context
    ticket, round_ = registered(working)
    checked(working, ticket, round_)
    working.call('rate', worktree=ticket, reviewer='alice', target='bob', scores=FULL)
    assert not working.store.ticket(ticket).work.done
    working.protocol.reconcile(context('tasks', working.folder),
                               {'name': 'project_agent', 'task_id': 'bob', 'work_id': 'work-bob', 'payload': {}},
                               {'state': 'cancelled'})
    assert working.store.ticket(ticket).work.done and working.board.worker('bob') is None
    assert [(r['reviewer'], r['alone']) for r in working.board.ratings(ticket)] == [('alice', False), ('bob', True)]


@pytest.mark.parametrize('name', ['../escape', 'a/b', '.lock.lock', 'ends.lock', 'a b'])
def test_a_worktree_name_is_one_safe_path_segment(working, name):
    with pytest.raises(Stop, match='worktree name'):
        working.call('ticket', node=NODE, summary='Bad', text='Bad name.', worktree=name)


def test_a_claim_makes_the_git_worktree_and_full_auto_merges_and_removes_it_at_the_close(working, run):
    repo = working.folder
    git = repository(repo)
    run('set', '--tasks-full-auto', cwd=repo)
    ticket, round_ = registered(working, worktree='timer')
    folder = repo / '.worktrees' / 'timer'
    assert (round_['folder'], round_['branch']) == (str(folder), 'metaform/timer') and folder.is_dir()
    assert '/.worktrees/' in (repo / '.git' / 'info' / 'exclude').read_text(encoding='utf-8')
    assert git('status', '--porcelain').stdout == '', 'the worktree folder is kept out of git status'
    (folder / 'timer.py').write_text('print(1)\n', encoding='utf-8')
    checked(working, 'timer', round_)
    ratings(working, 'timer')
    assert working.store.ticket(ticket).work.done
    assert (repo / 'timer.py').read_text(encoding='utf-8') == 'print(1)\n' and not folder.exists()
    assert git('branch', '--list', 'metaform/timer').stdout.strip() == ''
    assert 'Worktree timer' in git('log', '-1', '--format=%B').stdout


def test_a_merge_git_refuses_is_undone_and_said_on_the_tickets_and_the_worktree_stays(working, run):
    repo = working.folder
    git = repository(repo)
    run('set', '--tasks-full-auto', cwd=repo)
    ticket, round_ = registered(working, worktree='timer')
    (repo / '.worktrees' / 'timer' / 'README').write_text('theirs\n', encoding='utf-8')
    (repo / 'README').write_text('ours\n', encoding='utf-8')
    git('commit', '-q', '-am', 'ours')
    checked(working, 'timer', round_)
    ratings(working, 'timer')
    record = working.store.ticket(ticket).work
    assert record.done, 'closure is never gated on the merge'
    assert 'Not merged:' in record.note and (repo / '.worktrees' / 'timer').is_dir()
    assert (repo / 'README').read_text(encoding='utf-8') == 'ours\n'
    assert git('status', '--porcelain').stdout == ''


def test_without_full_auto_the_worktree_and_branch_stay_for_the_person(working):
    repo = working.folder
    git = repository(repo)
    ticket, round_ = registered(working, worktree='timer')
    checked(working, 'timer', round_)
    ratings(working, 'timer')
    assert working.store.ticket(ticket).work.done
    assert (repo / '.worktrees' / 'timer').is_dir()
    assert git('branch', '--list', 'metaform/timer').stdout.strip().lstrip('+ ') == 'metaform/timer'


def test_a_claim_reusing_a_leftover_branch_keeps_its_work_and_says_it_is_unmerged(working):
    repo = working.folder
    git = repository(repo)
    folder = repo / '.worktrees' / 'timer'
    _, round_ = registered(working, worktree='timer')
    assert 'notice' not in round_
    (folder / 'timer.py').write_text('print(1)\n', encoding='utf-8')
    git('-C', str(folder), 'add', 'timer.py')
    git('-C', str(folder), 'commit', '-q', '-m', 'old work')
    checked(working, 'timer', round_)
    ratings(working, 'timer')
    git('worktree', 'remove', '--force', str(folder))  # the person removed the folder and left the branch
    _, again = registered(working, worktree='timer')
    assert again['branch'] == 'metaform/timer' and (folder / 'timer.py').exists(), 'the old work is never discarded'
    assert 'metaform/timer' in again['notice'] and 'not in HEAD' in again['notice']
    checked(working, 'timer', again)
    ratings(working, 'timer')
    git('worktree', 'remove', '--force', str(folder))
    git('merge', '-q', 'metaform/timer')  # the person merged the branch and left it
    _, merged = registered(working, worktree='timer')
    assert merged['branch'] == 'metaform/timer' and 'notice' not in merged


def test_waiting_peer_receives_durable_wake_when_partner_finishes_prior_round(working, monkeypatch):
    from metaform import events
    from metaform.module import context
    from metaform.modules.tasks import runtime

    adapter = SimpleNamespace(start=lambda ctx, row: {'session_id': 'fixture-session'}, wake=Mock())
    monkeypatch.setattr(runtime, 'transport', lambda ctx: adapter)
    ctx = context('tasks', working.folder, nouns={'text': 'Fixture worksheet participation.'})
    waiter = runtime.SERVICE.assign(ctx, 'project_agent', None)['task_id']

    def deliver(topic, payload, source):
        working.published.append((topic, payload))
        if topic == 'map.changed' and payload.get('wake'):
            working.protocol.event(source, payload)
        return []

    monkeypatch.setattr(events, 'publish', deliver)
    prior, prior_round = registered(working, holder='bob', partner='carol', summary='Prior work')
    waiting, _ = registered(working, holder=waiter, partner=None, summary='Waiting paired work')
    working.call('pair', worktree=prior, partner='carol')
    working.call('pair', worktree=waiting, partner='bob')
    assert working.board.worker(waiter)['waiting_for'] == 'bob'
    assert working.board.worker('bob')['next'] == waiting
    checked(working, prior, prior_round)
    working.call('rate', worktree=prior, reviewer='bob', target='carol', scores=FULL)
    adapter.wake.assert_not_called()
    working.call('rate', worktree=prior, reviewer='carol', target='bob', scores=FULL)
    assert working.board.worker(waiter)['waiting_for'] is None
    assert working.board.worker('bob')['current'] == waiting
    adapter.wake.assert_called_once()
    _, assignment, message_key, message_text = adapter.wake.call_args.args
    assert assignment['task_id'] == waiter
    assert prior in message_key and prior in message_text


def test_a_ticket_naming_its_pair_tells_each_one_online_and_the_board_lists_the_names(working):
    made = working.call('ticket', node=NODE, summary='Timer face', text='Draw the face.', agents=['Alice', 'Dave'])
    assert (made['agents'], made['told']) == (['Alice', 'Dave'], ['alice'])  # Dave is not online
    assert working.call('view')['worktrees'][0]['agents'] == ['Alice', 'Dave']
    assert working.board.pending('alice')[0]['text'].startswith(f"Ticket {made['ticket']} (Timer face) names you with Dave")
    with pytest.raises(Stop):
        working.call('ticket', node=NODE, summary='Bad', text='Bad names.', agents=['Alice', 3])


def test_a_message_to_an_ended_agent_calls_its_context_back(working, monkeypatch):
    from metaform.module import context
    from metaform.modules.tasks import runtime
    adapter = SimpleNamespace(start=lambda ctx, row: {'session_id': 's'},
                              inspect=lambda ctx, row: {'state': 'completed', 'result': runtime.tool_result('Done.')},
                              wake=Mock(), resume=Mock(return_value={'state': 'starting', 'session_id': 's'}))
    monkeypatch.setattr(runtime, 'transport', lambda ctx: adapter)
    ctx = context('tasks', working.folder, nouns={'text': 'Paired work.'})
    agent = runtime.SERVICE.assign(ctx, 'project_agent', None)['task_id']
    working.board.patch(agent, {'session_id': 's'})
    working.board.set_round('round', 'Round', agent, [], [])
    working.board.rate('round', 'bob', agent, {**FULL, 'Efficient': 0})
    assert runtime.SERVICE.get(ctx, agent)['status'] == 'completed'
    assert working.board.worker(agent) is None, 'an agent gone offline leaves the board'
    told = working.call('message', agent_id=agent, text='What happened?')
    adapter.resume.assert_called_once()
    assert adapter.resume.call_args.args[1]['task_id'] == agent
    assert told['called_back'] == {'state': 'starting', 'session_id': 's'}
    assert working.board.pending(agent)[0]['text'].endswith('What happened?'), 'the message waits for the session'
    adapter.inspect = lambda ctx, row: {'state': 'working', 'idle': True, 'session_id': 's', 'name': 'Agent'}
    assert runtime.SERVICE.get(ctx, agent)['status'] == 'working', 'its session running again: the task is back'
    assert runtime.SERVICE.assignment(ctx, agent)['result'] is None
    assert working.board.worker(agent)['score'] == 90, 'the same context resumed brings its score back'
    adapter.wake.assert_called_once()
    assert adapter.wake.call_args.args[3].endswith('What happened?')


def test_a_handoff_starts_a_fresh_agent_in_the_callers_place_and_ends_the_caller(working, monkeypatch):
    from metaform.module import context
    from metaform.modules.tasks import runtime
    started = []

    def start(ctx, row):
        started.append(row)
        return {'session_id': f's{len(started)}', 'agent': row['agent']}

    adapter = SimpleNamespace(start=start, wake=Mock(), finish=Mock())
    monkeypatch.setattr(runtime, 'transport', lambda ctx: adapter)
    ctx = context('tasks', working.folder, nouns={'text': 'Paired work.', 'agent': 'codex'})
    leaving = runtime.SERVICE.assign(ctx, 'project_agent', None)['task_id']
    ticket, _ = registered(working, holder=leaving, partner='bob')
    working.board.rate(ticket, 'bob', leaving, {**FULL, 'Thorough': 3})
    result = working.protocol.handoff(context('tasks', working.folder, nouns={'text': 'Handoff: done X, next Y.'},
                                              identity={'METAFORM_TASK': leaving}))
    arriving = result['arriving']
    assert arriving != leaving and result['worktrees'] == [ticket] and result['current'] == ticket
    newcomer = started[-1]
    assert (newcomer['name'], newcomer['agent'], newcomer['cwd']) == ('project_agent', 'codex', str(working.folder))
    assert newcomer['payload']['input'] == 'Handoff: done X, next Y.'
    assert (working.board.round(ticket)['holder'], working.board.round(ticket)['partner']) == (arriving, 'bob')
    assert (working.board.worker(arriving)['current'], working.board.worker(arriving)['score']) == (ticket, None)
    assert (working.board.worker(leaving)['current'], working.board.worker(leaving)['score']) == ('', 88)
    adapter.finish.assert_called_once()
    assert adapter.finish.call_args.args[1]['task_id'] == leaving
    assert runtime.SERVICE.assignment(ctx, leaving)['message'] == f'Handed off to {arriving}.'


def test_a_claim_of_an_assignment_another_agent_holds_is_refused_and_names_the_holder(working):
    ticket, round_ = registered(working)  # alice holds it, bob is the partner
    with pytest.raises(Stop) as refused:
        working.call('worksheet', worktree=ticket, holder='carol', items=['Mine now'])
    assert 'held by alice' in str(refused.value)
    again = [{'id': item['id'], 'text': item['text']} for item in round_['items']]
    with pytest.raises(Stop):  # the partner pairs and checks; only the holder registers the worksheet again
        working.call('worksheet', worktree=ticket, holder='bob', items=again)
    assert working.call('worksheet', worktree=ticket, holder='alice', items=again)['holder'] == 'alice'
    assert working.call('view')['worktrees'][0]['holder'] == 'alice'


def test_messages_ride_on_the_next_tool_result_of_a_working_agent_and_wake_an_idle_one(working, monkeypatch):
    from metaform.module import context
    from metaform.modules.tasks import runtime
    wakes = []
    adapter = SimpleNamespace(start=lambda ctx, row: {'session_id': 's'},
                              wake=lambda ctx, row, key, text: wakes.append(text))
    monkeypatch.setattr(runtime, 'transport', lambda ctx: adapter)
    ctx = context('tasks', working.folder, nouns={'text': 'Paired work.'})
    agent = runtime.SERVICE.assign(ctx, 'project_agent', None)['task_id']
    assignment = runtime.SERVICE.assignment(ctx, agent)
    working.board.patch(agent, {'state': 'working'})
    working.call('message', agent_id=agent, text='Plan?', identity={'METAFORM_TASK': 'alice'})
    working.protocol.flush(ctx, assignment)
    assert wakes == []  # a working agent is not interrupted; its next tool call carries the message
    own = context('tasks', working.folder, nouns={}, identity={'METAFORM_TASK': agent})
    shown = working.protocol.with_inbox(working.protocol.view)(own)
    assert shown['messages'] == ['From alice: Plan?'] and working.board.pending(agent) == []
    assert 'messages' not in working.protocol.with_inbox(working.protocol.view)(own)  # delivered once
    working.board.patch(agent, {'state': 'idle'})
    working.call('message', agent_id=agent, text='Done?', identity={'METAFORM_TASK': 'alice'})
    working.protocol.flush(ctx, assignment)
    assert wakes == ['From alice: Done?'] and working.board.pending(agent) == []


def test_a_board_name_stands_for_its_agent_id_wherever_an_id_is_taken(working):
    ticket = working.call('ticket', node=NODE, summary='Face', text='Draw it.')['ticket']
    round_ = working.call('worksheet', worktree=ticket, holder='alice', partner='Bob',
                          items=[{'text': 'Theirs', 'agent': 'Bob'}, 'Shared'])
    assert round_['partner'] == 'bob' and round_['items'][0]['agent'] == 'bob'
    assert working.call('pair', worktree=ticket, partner='Carol')['partner'] == 'carol'
    rated = working.call('rate', worktree=ticket, reviewer='alice', target='Carol', scores=FULL)
    assert rated['target'] == 'carol'


@pytest.fixture
def stored(working, home):
    """`proj` held in the project store, its kitchen timer an element there, so its tickets are the tickets overlay's
    records (kickoff 2026-11-17, t-legacy-keep). Its single-writer service is stopped when the test ends."""
    from metaform.project import owner, service
    from metaform.project import run as command
    assert command({'add': {f'proj.{NODE}': {'technical_name': 'kitchen timer', 'name': 'kitchen timer',
                                             'role': 'Defining Element'}}}) == {'status': 'ok'}
    yield working
    service.stop(home)
    owner.close_all()


def overlay_tickets():
    from metaform.project import overlay_records
    return {one['id']: one for one in overlay_records('proj', 'tickets') or []}


def test_a_pairs_worksheet_on_a_project_in_the_project_store_runs_on_its_tickets_overlay(stored):
    """The ticket is a record at the element the board reads, taken by the holder, its steps following the items, the
    completed worksheet in its note, and done with the resolution at the close; the old store gets no ticket."""
    ticket, round_ = registered(stored)
    one = overlay_tickets()[ticket]
    assert one['element'] == f'proj.{NODE}' and one['title'] == 'Fix the kitchen timer'
    assert one['task'] == 'Repair and verify the timer behavior.'
    assert one['taken_by'] == 'alice' and (one['steps'], one['steps_done']) == (2, 0)
    assert [worktree['worktree'] for worktree in stored.call('view')['worktrees']] == [ticket]
    checked(stored, ticket, round_)
    one = overlay_tickets()[ticket]
    assert one['steps_done'] == 2 and 'done' not in one
    assert one['note'].count(f'Completed worksheet ({ticket})') == 1 and '[x] Inspect the timer' in one['note']
    ratings(stored, ticket)
    one = overlay_tickets()[ticket]
    assert one['outcome'] == 'completed' and one['done']
    assert one['note'].endswith('Resolution: Completed the registered worksheet. Why: Every participant rated at the '
                                f'close of worktree {ticket}.')
    assert stored.call('view')['worktrees'] == []
    assert not stored.store.work(limit=0).results


def test_a_ticket_on_a_join_is_refused_by_name_on_a_project_in_the_project_store(stored):
    with pytest.raises(Stop, match='a join has no tickets there yet'):
        stored.call('ticket', node='join:code.timer.kitchen->code.timer.bell', summary='Ring', text='Ring the bell.')
    assert overlay_tickets() == {}


def test_a_project_given_tickets_before_steps_existed_gains_them_on_open_and_keeps_its_records(stored, home):
    """give_standing_overlays brings an existing project's tickets definition up to the standing one with its new
    optional fields only (F03): the records stay as they were."""
    from metaform.project import owner, service
    from metaform.project import run as command
    for name in ('steps', 'steps_done'):
        assert command({'delete': {f'proj.overlay.tickets.{name}': {}}}) == {'status': 'ok'}
    assert 'steps' not in command({'proj.overlay.tickets': {}})['proj.overlay.tickets']
    ticket = stored.call('ticket', node=NODE, summary='Fix it', text='Fix the timer.')['ticket']
    before = overlay_tickets()[ticket]
    service.stop(home)
    owner.close_all()
    definition = command({'proj.overlay.tickets': {}})['proj.overlay.tickets']
    assert definition['steps']['optional'] is True and definition['steps_done']['type'] == 'number'
    assert overlay_tickets()[ticket] == before
