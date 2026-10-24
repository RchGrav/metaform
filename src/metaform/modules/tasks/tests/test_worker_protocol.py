"""Real ticket and worker-board persistence for cooperative worksheet execution."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

pytestmark = pytest.mark.kind('fixture')

NODE = 'code.timer.kitchen'
NODES = ['code.Exact_Name', 'Unknown.Unexpanded.Node']


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


def registered(working, *, holder='alice', partner='bob', summary='Fix the kitchen timer', items=None):
    ticket = working.call('ticket', node=NODE, summary=summary, text='Repair and verify the timer behavior.')['ticket']
    round_ = working.call('worksheet', ticket=ticket, holder=holder, partner=partner,
                          items=items if items is not None else ['Inspect the timer', 'Verify the correction'],
                          nodes=list(NODES))
    return ticket, round_


def checked(working, ticket, round_):
    for item in round_['items']:
        working.call('check', ticket=ticket, item=item['id'])


def ratings(working, ticket):
    first = working.call('rate', ticket=ticket, reviewer='alice', target='bob', scores={'fixture care': 75})
    second = working.call('rate', ticket=ticket, reviewer='bob', target='alice', scores={'fixture clarity': 85})
    return first, second


def test_registered_summary_and_item_checks_project_into_real_ticket_without_inflation(working):
    ticket, round_ = registered(working)
    record = working.store.ticket(ticket).work
    assert working.store.numbers_of('work', [ticket])[ticket][1] == 'Fix the kitchen timer'
    assert record.task == 'Repair and verify the timer behavior.'
    assert (record.steps, record.steps_done) == (2, 0)
    item = round_['items'][0]['id']
    working.call('check', ticket=ticket, item=item)
    working.call('check', ticket=ticket, item=item)
    record = working.store.ticket(ticket).work
    assert (record.steps, record.steps_done) == (2, 1)
    assert record.said == ()  # Checking a worksheet must not fabricate a completed-step narrative.
    working.call('check', ticket=ticket, item=item, done=False)
    assert working.store.ticket(ticket).work.steps_done == 0
    edited = working.call('worksheet', ticket=ticket, holder='alice', partner='bob',
                          items=['Inspect the timer', 'Verify the correction'], nodes=list(NODES))
    assert [item['id'] for item in edited['items']] == [item['id'] for item in round_['items']]
    assert working.call('worksheet', ticket=ticket)['nodes'] == NODES


def test_fully_checked_worksheet_appends_once_and_retains_participant_notes(working):
    ticket, round_ = registered(working)
    working.store.edit_work(ticket, {'note': 'Existing evidence from a participant.'})
    checked(working, ticket, round_)
    record = working.store.ticket(ticket).work
    assert (record.steps, record.steps_done) == (2, 2)
    assert not record.done  # Worksheet progress and peer review are separate observations.
    marker = f'Completed worksheet ({ticket})'
    assert record.note.count(marker) == 1
    assert '[x] Inspect the timer' in record.note and '[x] Verify the correction' in record.note
    working.store.edit_work(ticket, {'note': record.note + '\n\nLater participant evidence.'})
    working.call('check', ticket=ticket, item=round_['items'][-1]['id'])
    note = working.store.ticket(ticket).work.note
    assert note.count(marker) == 1
    assert note.startswith('Existing evidence from a participant.')
    assert note.endswith('Later participant evidence.')


def test_both_counterpart_ratings_close_ticket_and_single_rating_does_not(working, monkeypatch):
    ticket, round_ = registered(working)
    checked(working, ticket, round_)
    # No current-work, ownership or role identity is required to contribute a counterpart rating.
    monkeypatch.setenv('METAFORM_ROLE', 'arbitrary-legacy-role')
    first = working.call('rate', ticket=ticket, reviewer='alice', target='bob', scores={'fixture care': 75})
    assert first['completed'] is False and not working.store.ticket(ticket).work.done
    second = working.call('rate', ticket=ticket, reviewer='bob', target='alice', scores={'fixture clarity': 85})
    assert second['completed'] is True
    assert working.store.ticket(ticket).work.done
    assert working.board.round(ticket)['completed'] is True
    repeated = working.call('rate', ticket=ticket, reviewer='bob', target='alice', scores={'fixture clarity': 85})
    assert repeated['completed'] is True
    assert len(working.board.ratings(ticket)) == 2
    assert working.store.ticket(ticket).work.note.count(f'Completed worksheet ({ticket})') == 1


def test_native_actor_attribution_overrides_claimed_reviewer(working):
    ticket, _ = registered(working)
    result = working.call('rate', ticket=ticket, reviewer='claimed-other', target='alice',
                          scores={'fixture observation': 60}, identity={'METAFORM_TASK': 'bob'})
    assert result['reviewer'] == 'bob'
    assert working.board.ratings(ticket) == [
        {'ticket': ticket, 'reviewer': 'bob', 'target': 'alice',
         'scores': {'fixture observation': 60}, 'total': 60}]


def test_peer_board_hides_own_row_and_preserves_exact_node_strings(working):
    ticket, round_ = registered(working)
    checked(working, ticket, round_)
    ratings(working, ticket)
    own_view = working.call('view', identity={'METAFORM_TASK': 'alice'})['agents']
    assert {row['agent_id'] for row in own_view} == {'bob', 'carol'}
    bob = next(row for row in own_view if row['agent_id'] == 'bob')
    assert bob['rating'] == 75
    assert bob['past'] == [{'ticket': ticket, 'phrase': 'Fix the kitchen timer', 'nodes': NODES, 'rating': 75}]
    assert all(row['rating'] != 85 for row in own_view)
    human_view = working.call('view')['agents']
    alice = next(row for row in human_view if row['agent_id'] == 'alice')
    assert alice['rating'] == 85 and alice['past'][0]['nodes'] == NODES


def test_waiting_peer_receives_durable_wake_when_partner_finishes_prior_round(working, monkeypatch):
    from metaform import events
    from metaform.module import context
    from metaform.modules.tasks import runtime

    adapter = SimpleNamespace(start=lambda ctx, row: {'session_id': 'fixture-session'}, wake=Mock())
    monkeypatch.setattr(runtime, 'transport', lambda ctx: adapter)
    ctx = context('tasks', working.folder, nouns={'text': 'Fixture worksheet participation.'})
    waiter = runtime.SERVICE.assign(ctx, 'worker', None)['task_id']

    def deliver(topic, payload, source):
        working.published.append((topic, payload))
        if topic == 'map.changed' and payload.get('wake'):
            working.protocol.event(source, payload)
        return []

    monkeypatch.setattr(events, 'publish', deliver)
    prior, prior_round = registered(working, holder='bob', partner='carol', summary='Prior work')
    waiting, _ = registered(working, holder=waiter, partner=None, summary='Waiting paired work')
    working.call('pair', ticket=prior, partner='carol')
    working.call('pair', ticket=waiting, partner='bob')
    assert working.board.worker(waiter)['waiting_for'] == 'bob'
    assert working.board.worker('bob')['next'] == waiting
    checked(working, prior, prior_round)
    working.call('rate', ticket=prior, reviewer='bob', target='carol', scores={'fixture contribution': 70})
    adapter.wake.assert_not_called()
    working.call('rate', ticket=prior, reviewer='carol', target='bob', scores={'fixture contribution': 80})
    assert working.board.worker(waiter)['waiting_for'] is None
    assert working.board.worker('bob')['current'] == waiting
    adapter.wake.assert_called_once()
    _, assignment, message_key, message_text = adapter.wake.call_args.args
    assert assignment['task_id'] == waiter
    assert prior in message_key and prior in message_text
    assert working.board.pending(waiter) == []  # Only successful native delivery removes the durable outbox row.
    working.call('rate', ticket=prior, reviewer='carol', target='bob', scores={'fixture contribution': 80})
    assert adapter.wake.call_count == 1
    assert any(topic == 'map.changed' and payload.get('wake') and waiter in payload.get('agent_ids', [])
               for topic, payload in working.published)
