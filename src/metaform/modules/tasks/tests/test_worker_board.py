"""The temporary worker board survives reopening and keeps peer views separate."""
import pytest

from metaform.modules.tasks.board import Board

pytestmark = pytest.mark.kind('fixture')


@pytest.fixture
def board(tmp_path, monkeypatch):
    monkeypatch.setenv('TMPDIR', str(tmp_path))
    return Board('test-project')


def test_reopen_registration_keeps_names_slots_nodes_and_real_context(board):
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
    assert reopened.view()[0]['context'] == 25
    assert reopened.path.name == 'sessions.sqlite' and reopened.path.exists()


@pytest.mark.parametrize('project', ['../escape', '/absolute', '.', '..', 'nested/path', 'bad\\path'])
def test_project_is_one_path_segment(board, project):
    with pytest.raises(ValueError):
        Board(project)


def test_worksheet_edits_preserve_ids_checks_and_per_agent_counts(board):
    board.register('a', 'A', 'work-a')
    board.register('b', 'B', 'work-b')
    round_ = board.set_round('t', 'Phrase exactly.', 'a', [
        'Shared', {'id': 'owned', 'text': 'For A', 'agent': 'a', 'nodes': ['Unchanged.Node']},
        {'id': 'other', 'text': 'For B', 'agent': 'b', 'done': True}], ['Unchanged.Node'])
    shared = round_['items'][0]['id']
    board.check('t', shared)
    board.check('t', shared)
    edited = board.set_round('t', 'Edited phrase', 'a', [
        'Shared', {'id': 'owned', 'text': 'For A edited'}, {'id': 'other', 'text': 'For B'}], ['Unchanged.Node'])
    assert edited['items'][0] == {'id': shared, 'text': 'Shared', 'done': True}
    assert edited['items'][1]['nodes'] == ['Unchanged.Node']
    assert edited['items'][2]['done'] is True
    board.pair('t', 'b')
    views = {row['agent_id']: row for row in board.view()}
    assert views['a']['complete'] == 50 and views['b']['complete'] == 100
    assert views['a']['current']['checked'] == 1 and views['a']['current']['total'] == 2
    assert sum(bool(item['done']) for item in board.round('t')['items']) == 2
    assert views['a']['current']['phrase'] == 'Edited phrase'
    board.check('t', shared, False)
    assert board.view()[0]['complete'] == 0


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


def test_ratings_use_supplied_categories_completed_round_average_and_hide_viewer(board):
    board.register('a', 'Canonical A', 'wa')
    board.register('b', 'Canonical B', 'wb')
    board.set_round('first', 'First', 'a', [], ['code.Exact'])
    board.pair('first', 'b')
    rating = board.rate('first', 'b', 'a', {'accuracy': 40, 'care': 20})
    assert rating['total'] == 60 and rating['scores'] == {'accuracy': 40, 'care': 20}
    assert 'rating' not in rating and 'average' not in rating
    board.rate('first', 'b', 'a', {'accuracy': 50, 'care': 30})
    assert len(board.ratings('first')) == 1
    assert board.view('b')[0]['rating'] is None
    board.complete_round('first')
    board.set_round('second', 'Second', 'a', [], [])
    board.pair('second', 'b')
    board.rate('second', 'b', 'a', {'chosen category': 40})
    board.complete_round('second')
    peer, = board.view('b')
    assert peer['agent_id'] == 'a' and peer['name'] == 'Canonical A'
    assert peer['rating'] == 60
    assert [past['rating'] for past in peer['past']] == [80, 40]
    own_peer, = board.view('a')
    assert own_peer['agent_id'] == 'b' and own_peer['rating'] is None
    assert own_peer['context'] is None


@pytest.mark.parametrize('scores', [{'x': -1}, {'x': 101}, {'x': float('nan')}, {'x': float('inf')}, {'x': True}, {'x': '1'}])
def test_rating_rejects_invalid_numeric_points(board, scores):
    board.set_round('t', 'T', 'a', [], [])
    with pytest.raises(ValueError):
        board.rate('t', 'b', 'a', scores)


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


def test_run_history_lasts_until_the_last_worker_leaves(board):
    board.register('a', 'A', 'wa')
    board.register('b', 'B', 'wb')
    board.set_round('open', 'Open', 'a', [], ['Exact.Node'])
    board.remove('a')
    assert board.round('open') is not None
    board.remove('b')
    assert board.rounds() == [] and board.ratings('open') == []
    assert Board('test-project').workers() == []
