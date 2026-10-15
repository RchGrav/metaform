"""Task orientation and optional history at elements and joins."""
import pytest

from metaform import home
from metaform.data import Node
from tests.storekit import small_map

pytestmark = pytest.mark.kind('fixture')


@pytest.mark.req('MAP-049')
@pytest.mark.req('MAP-051')
@pytest.mark.parametrize('kind', ['element', 'join'])
def test_node_reads_show_taken_age_and_past_work_without_spending_context_on_its_log(store, monkeypatch, kind):
    _, outer, _ = small_map(store)
    target = Node('element', 'code.timer.kitchen') if kind == 'element' else Node('join', outer.id)
    monkeypatch.setattr(home, 'now', lambda: '2026-10-01T00:00:00Z')
    old = store.add_work(target, 'broken', task='wire the tone')
    store.take_work(old.id, steps=1, by='first agent')
    store.step_work(old.id, 'Wired the driver.')
    monkeypatch.setattr(home, 'now', lambda: '2026-10-02T00:00:00Z')
    store.finish_work(old.id, 'wired')
    active = store.add_work(target, None, task='a softer tone')
    store.take_work(active.id, by='second agent')
    monkeypatch.setattr(home, 'now', lambda: '2026-10-03T00:00:00Z')

    at = store.ticket(active.id).to_dict()['at']
    assert [one['id'] for one in at['work']] == [active.id]
    assert (at['work'][0]['taken_by'], at['work'][0]['age_seconds']) == ('second agent', 86400)
    assert at['past_work'] == [{'work_id': old.id, 'done': '2026-10-02T00:00:00Z', 'age_seconds': 86400}]
    assert 'Wired the driver.' not in str(at)
    past = store.ticket(at['past_work'][0]['work_id']).to_dict()
    assert (past['resolution'], past['age_seconds'], past['said'][0]['said']) == ('wired', 86400, 'Wired the driver.')
    assert [one.id for one in store.work(target, open=True).results] == [active.id]
    if kind == 'element':
        assert store.where(target.id, full=True).to_dict()['past_work'] == at['past_work']


@pytest.mark.req('MAP-049')
def test_requeue_preserves_the_log_and_a_later_take_starts_a_new_age(store, monkeypatch):
    small_map(store)
    target = Node('element', 'code.timer.kitchen')
    monkeypatch.setattr(home, 'now', lambda: '2026-10-01T00:00:00Z')
    ticket = store.add_work(target, 'unbuilt', task='build the timer')
    store.take_work(ticket.id, steps=2, by='stopped agent')
    store.step_work(ticket.id, 'Traced the circuit.')
    returned = store.move_work(ticket.id, 'todo')
    assert returned.to_dict()['age_seconds'] is None
    assert returned.taken_by is None and returned.said[0].said == 'Traced the circuit.'
    monkeypatch.setattr(home, 'now', lambda: '2026-10-03T00:00:00Z')
    assigned = store.take_work(ticket.id, by='next agent')
    assert (assigned.to_dict()['age_seconds'], assigned.taken_by) == (0, 'next agent')


@pytest.mark.req('MAP-051')
def test_past_work_lists_recent_completions_first_even_when_the_ticket_was_created_earlier(store, monkeypatch):
    small_map(store)
    target = Node('element', 'code.timer.kitchen')
    old = store.add_work(target, 'broken')
    new = store.add_work(target, None, task='a second fix')  # a record with neither is refused, MAP-046
    monkeypatch.setattr(home, 'now', lambda: '2026-10-01T00:00:00Z')
    store.finish_work(new.id, 'done first')
    monkeypatch.setattr(home, 'now', lambda: '2026-10-02T00:00:00Z')
    store.finish_work(old.id, 'done later')
    assert [one['work_id'] for one in store.where(target.id).to_dict()['past_work']] == [old.id, new.id]
