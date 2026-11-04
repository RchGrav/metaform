"""The temporary board survives reopening, keeps peer views separate and moves scores by the ratings."""
import pytest

from metaform.modules.tasks.board import Board

pytestmark = pytest.mark.kind('fixture')

FULL = {'Efficient': 5, 'Alert & Aware': 5, 'Thorough': 5, 'Coordination': 5}


@pytest.fixture
def board(tmp_path, monkeypatch):
    monkeypatch.setenv('TMPDIR', str(tmp_path))
    return Board('test-project')


def test_reopen_registration_keeps_names_slots_nodes_score_and_real_context(board):
    board.register('a', 'Exact Canonical Name', 'work-a')
    board.patch('a', {'current': 'one', 'next': 'two', 'nodes': ['code.Unknown_Name'],
                      'context': {'used': 50, 'size': 200}, 'state': 'idle'})
    reopened = Board('test-project')
    reopened.register('a', 'Exact Canonical Name', 'work-a', 'native')
    worker = reopened.worker('a')
    assert worker['name'] == 'Exact Canonical Name'
    assert (worker['current'], worker['next']) == ('one', 'two')
    assert worker['nodes'] == ['code.Unknown_Name']
    assert worker['context'] == {'used': 50, 'size': 200}
    assert worker['session_id'] == 'native'
    assert worker['score'] is None
    assert reopened.view()[0]['context'] == 25
    assert reopened.path.name == 'board.sqlite' and reopened.path.exists()


@pytest.mark.parametrize('project', ['../escape', '/absolute', '.', '..', 'nested/path', 'bad\\path'])
def test_project_is_one_path_segment(board, project):
    with pytest.raises(ValueError):
        Board(project)


def test_worksheet_edits_preserve_ids_checks_and_per_agent_counts(board):
    board.register('a', 'A', 'work-a')
    board.register('b', 'B', 'work-b')
    round_ = board.set_round('t', 'Phrase exactly.', 'a', [
        'Shared', {'id': 'owned', 'text': 'For A', 'agent': 'a', 'nodes': ['Unchanged.Node']},
        {'id': 'other', 'text': 'For B', 'agent': 'b', 'done': True}], ['Unchanged.Node'], tickets=['t'])
    shared = round_['items'][0]['id']
    board.check('t', shared)
    board.check('t', shared)
    edited = board.set_round('t', 'Edited phrase', 'a', [
        'Shared', {'id': 'owned', 'text': 'For A edited'}, {'id': 'other', 'text': 'For B'}], ['Unchanged.Node'])
    assert edited['items'][0] == {'id': shared, 'text': 'Shared', 'done': True}
    assert edited['items'][1]['nodes'] == ['Unchanged.Node']
    assert edited['items'][2]['done'] is True
    assert edited['tickets'] == ['t'], 'an edit that names no tickets keeps them'
    board.pair('t', 'b')
    views = {row['agent_id']: row for row in board.view()}
    assert views['a']['complete'] == 50 and views['b']['complete'] == 100
    assert views['a']['current']['checked'] == 1 and views['a']['current']['total'] == 2
    assert sum(bool(item['done']) for item in board.round('t')['items']) == 2
    assert views['a']['current']['phrase'] == 'Edited phrase'
    board.check('t', shared, False)
    assert board.view()[0]['complete'] == 0


def test_progress_of_one_ticket_counts_its_own_items_and_the_shared(board):
    round_ = board.set_round('w', 'W', 'a', [
        {'text': 'One', 'ticket': 't1', 'done': True}, {'text': 'Two', 'ticket': 't2'}, 'Shared'], [], tickets=['t1', 't2'])
    assert Board.progress(round_, ticket='t1') == {'checked': 1, 'total': 2}
    assert Board.progress(round_, ticket='t2') == {'checked': 0, 'total': 2}
    assert Board.progress(round_) == {'checked': 1, 'total': 3}


def test_pair_overwrites_next_without_arbitration_and_completion_promotes(board):
    board.register('a', 'A', 'wa')
    board.register('b', 'B', 'wb')
    board.set_round('busy', 'Existing work', 'b', [], [])
    board.patch('b', {'next': 'replaceable'})
    board.set_round('pair', 'Pair work', 'a', [], ['literal'])
    board.pair('pair', 'b')
    assert board.worker('b')['next'] == 'pair'
    assert [worker['agent_id'] for worker in board.waiters('b')] == ['a']
    assert board.complete_round('busy')['affected'] == ['b']
    assert board.worker('b')['current'] == 'pair' and board.worker('b')['next'] == ''
    assert set(board.complete_round('pair')['affected']) == {'a', 'b'}
    assert all(not worker['current'] for worker in board.workers())


def test_ratings_move_scores_by_category_stars_and_bonus_within_the_limits_and_hide_viewer(board):
    board.register('a', 'Canonical A', 'wa')
    board.register('b', 'Canonical B', 'wb')
    board.set_round('first', 'First', 'a', [], ['code.Exact'], tickets=['t1'])
    board.pair('first', 'b')
    rating = board.rate('first', 'b', 'a', {**FULL, 'Coordination': 4})
    assert (rating['points'], rating['change']) == (92, 92)
    assert board.worker('a')['score'] == 92
    board.rate('first', 'b', 'a', FULL, bonus=True)  # the pick made again replaces the first
    assert len(board.ratings('first')) == 1 and board.worker('a')['score'] == 105
    board.rate('first', 'a', None, {}, alone=True)
    assert board.worker('b')['score'] is None
    board.complete_round('first')
    board.set_round('second', 'Second', 'a', [], [], tickets=['t2'])
    board.pair('second', 'b')
    board.rate('second', 'b', 'a', {**FULL, 'Thorough': 0})
    assert board.worker('a')['score'] == 175, 'each rating adds its points, worth what they are'
    board.complete_round('second')
    peer, = board.view('b')
    assert peer['agent_id'] == 'a' and peer['name'] == 'Canonical A' and peer['score'] == 175
    assert [past['points'] for past in peer['past']] == [105, 70]
    own_peer, = board.view('a')
    assert own_peer['agent_id'] == 'b' and own_peer['score'] is None and own_peer['past'][0]['points'] is None
    assert own_peer['context'] is None


@pytest.mark.parametrize('stars', [{**FULL, 'Coordination': 6}, {**FULL, 'Coordination': -1},
                                   {**FULL, 'Coordination': float('nan')}, {**FULL, 'Coordination': True},
                                   {**FULL, 'Coordination': '1'}, {**FULL, 'Unknown': 5}, {'Efficient': 5}])
def test_rating_rejects_stars_outside_the_categories_or_five(board, stars):
    board.register('a', 'A', 'wa')
    board.set_round('t', 'T', 'a', [], [])
    with pytest.raises(ValueError):
        board.rate('t', 'b', 'a', stars)
    assert board.worker('a')['score'] is None


def test_outbox_is_durable_deduplicated_and_clear_keeps_database_reopenable(board):
    board.register('a', 'A', 'wa')
    board.enqueue('a', 'wake:one', 'First message')
    board.enqueue('a', 'wake:one', 'Duplicate must not replace the first')
    board.enqueue('a', 'wake:two', 'Second message')
    reopened = Board('test-project')
    assert reopened.pending('a') == [{'key': 'wake:one', 'text': 'First message'},
                                      {'key': 'wake:two', 'text': 'Second message'}]
    reopened.delivered('wake:one')
    assert board.pending('a') == [{'key': 'wake:two', 'text': 'Second message'}]
    reopened.clear()
    assert Board('test-project').workers() == [] and board.pending('a') == []
    assert board.path.exists()


def test_partner_nodes_are_exact_and_completed_history_survives_new_work(board):
    board.register('a', 'A', 'wa')
    board.register('b', 'B', 'wb')
    board.set_round('first', 'First', 'a', [
        {'id': 'a-item', 'text': 'A work', 'agent': 'a', 'nodes': ['Exact.A']},
        {'id': 'b-item', 'text': 'B work', 'agent': 'b', 'nodes': ['Exact.B']}], ['Whole.Round'])
    board.pair('first', 'b')
    view = {row['agent_id']: row for row in board.view()}
    assert view['a']['current']['nodes'] == ['Exact.A']
    assert view['b']['current']['nodes'] == ['Exact.B']
    board.patch('a', {'nodes': ['Actual.A_name']})
    assert board.view('b')[0]['current']['nodes'] == ['Actual.A_name']
    board.set_round('second', 'Second', 'a', [
        {'text': 'Next A', 'agent': 'a', 'nodes': ['Next.A']},
        {'text': 'Next B', 'agent': 'b', 'nodes': []}], ['Next.Whole'])
    board.pair('second', 'b')
    view = {row['agent_id']: row for row in board.view()}
    assert view['a']['next']['nodes'] == ['Next.A']
    assert view['b']['next']['nodes'] == []
    board.complete_round('first')
    board.patch('a', {'nodes': ['New.Current.A']})
    board.patch('b', {'nodes': []})
    board.complete_round('first')
    reopened = Board('test-project')
    view = {row['agent_id']: row for row in reopened.view()}
    assert view['a']['past'][0]['nodes'] == ['Actual.A_name']
    assert view['b']['past'][0]['nodes'] == ['Exact.B']
    assert view['a']['current']['nodes'] == ['New.Current.A']
    assert view['b']['current']['nodes'] == []


def test_run_history_lasts_until_the_last_agent_leaves(board):
    board.register('a', 'A', 'wa')
    board.register('b', 'B', 'wb')
    board.set_round('open', 'Open', 'a', [], ['Exact.Node'])
    board.remove('a')
    assert board.round('open') is not None
    board.remove('b')
    assert board.rounds() == [] and board.ratings('open') == []
    assert Board('test-project').workers() == []


def test_a_claim_of_a_closed_worktree_name_starts_clean_and_keeps_the_old_round_in_history(board):
    board.register('a', 'A', 'wa')
    board.register('b', 'B', 'wb')
    board.set_round('timer', 'First', 'a', ['x'], [], tickets=['t1'])
    board.pair('timer', 'b')
    board.rate('timer', 'b', 'a', {**FULL, 'Coordination': 4})
    board.complete_round('timer')
    again = board.set_round('timer', 'Second', 'a', ['y'], [], tickets=['t2'])
    assert again['completed'] is False and again['tickets'] == ['t2'] and board.ratings('timer') == []
    assert [item['text'] for item in again['items']] == ['y']
    peer, = board.view('b')
    assert [past['worktree'] for past in peer['past']] == ['timer#1'] and peer['past'][0]['points'] == 92
    assert board.worker('a')['score'] == 92 and peer['current']['worktree'] == 'timer'


def test_a_replaced_rating_reverses_only_what_the_limits_let_it_apply(board):
    board.register('a', 'A', 'wa')
    board.set_round('t', 'T', 'a', [], [])
    board.rate('t', 'b', 'a', FULL, bonus=True)
    assert board.worker('a')['score'] == 105
    second = board.rate('t', 'c', 'a', FULL, bonus=True)
    assert (second['change'], second['applied']) == (105, 105) and board.worker('a')['score'] == 210
    board.rate('t', 'c', 'a', {**FULL, 'Efficient': 0})
    assert board.worker('a')['score'] == 195


def test_a_ticket_joins_an_open_round_only(board):
    board.set_round('t', 'T', 'a', ['x'], [], tickets=['t1'])
    assert board.add_ticket('t', 't2')['tickets'] == ['t1', 't2']
    assert board.add_ticket('t', 't2')['tickets'] == ['t1', 't2']
    board.complete_round('t')
    assert board.add_ticket('t', 't3') is None and board.add_ticket('other', 't3') is None


def test_a_score_belongs_to_the_context_and_comes_back_with_its_session(board):
    board.register('a', 'A', 'wa', 'first-context')
    board.register('b', 'B', 'wb')
    board.set_round('t', 'T', 'a', [], [])
    board.rate('t', 'b', 'a', {**FULL, 'Coordination': 4})
    assert board.worker('a')['score'] == 92
    board.remove('a')  # the agent shut down: its score clears with it
    board.register('a', 'A', 'wa')
    assert board.worker('a')['score'] is None, 'a worker with no session id yet is unscored'
    board.patch('a', {'session_id': 'first-context'})  # the same context resumed: its score comes back with it
    assert board.worker('a')['score'] == 92
    board.remove('a')
    board.register('a', 'A', 'wa', 'second-context')
    assert board.worker('a')['score'] is None, 'a fresh context is unscored'
    board.rate('t', 'b', 'a', FULL, bonus=True)  # the pick made again moves the new context, not the old one
    assert board.worker('a')['score'] == 105
    board.remove('a')
    board.remove('b')  # the last agent leaves: the run's rounds go, the contexts' scores stay
    assert board.rounds() == []
    assert Board('test-project').register('a', 'A', 'wa', 'first-context')['score'] == 92
    assert board.register('c', 'C', 'wc', 'second-context')['score'] == 105


def test_a_handoff_moves_the_place_and_the_newcomer_starts_fresh(board):
    board.register('a', 'A', 'wa', 'ctx-a')
    board.register('b', 'B', 'wb', 'ctx-b')
    board.register('c', 'C', 'wc')
    board.set_round('one', 'One', 'a', [], ['Node.A'], tickets=['t1'])
    board.pair('one', 'b')
    board.set_round('two', 'Two', 'a', [], [], tickets=['t2'])
    board.patch('b', {'waiting_for': 'a'})
    board.rate('one', 'b', 'a', {**FULL, 'Thorough': 3})
    moved = board.handoff('a', 'c')
    assert moved == {'leaving': 'a', 'arriving': 'c', 'worktrees': ['one', 'two'], 'current': 'one', 'next': 'two'}
    assert (board.round('one')['holder'], board.round('one')['partner']) == ('c', 'b')
    assert board.round('two')['holder'] == 'c'
    assert (board.worker('c')['current'], board.worker('c')['next'], board.worker('c')['score']) == ('one', 'two', None)
    assert (board.worker('a')['current'], board.worker('a')['next'], board.worker('a')['score']) == ('', '', 88)
    assert board.worker('b')['waiting_for'] == 'c'
    with pytest.raises(KeyError):
        board.handoff('c', 'nobody')
