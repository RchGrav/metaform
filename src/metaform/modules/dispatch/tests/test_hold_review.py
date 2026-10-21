"""Held work receives persisted, coalesced review reminders through existing dispatch signals."""
from __future__ import annotations

import importlib

import pytest

from metaform.data import Node, Store
from metaform.module import context
from metaform.modules.dispatch import hold_review
from metaform.modules.dispatch.tests.test_dispatch import dispatch  # noqa: F401

pytestmark = pytest.mark.kind('fixture')


@pytest.fixture
def review(dispatch, monkeypatch):  # noqa: F811
    case = dispatch
    current = importlib.import_module('metaform.modules.dispatch.hold_review')
    monkeypatch.setitem(globals(), 'hold_review', current)
    ctx = context('dispatch', case.folder, project='proj')
    monkeypatch.setattr(ctx, 'setting', lambda name: name == 'dispatch_autostart')
    clock = [1000.0]
    monkeypatch.setattr(hold_review.time, 'time', lambda: clock[0])
    published = []
    monkeypatch.setattr(hold_review, 'announce', lambda ctx, value: published.append(value))
    return case, ctx, clock, published


def held(review, task='Waiting repair', reason='Wait for replacement hardware.'):
    case, _, _, _ = review
    return case.store.add_work(case.node, None, task=task, held=True, hold_reason=reason)


def schedules(review):
    case, _, _, _ = review
    with Store(case.store.project_id, module='dispatch').tables(write=False) as tx:
        return tx.rows('hold_reviews', limit=0).results


def event(review, ids, **overrides):
    case, _, _, _ = review
    return {'project': case.store.project_id, 'base_id': case.store.bound_base().id,
            'tables': ['work', 'map.ticket_settings'], 'kinds': ['ticket'], 'work_ids': ids, **overrides}


def consume(review):
    case, _, _, published = review
    from metaform.modules.dispatch.signals import taken
    assert taken(case.store, published[-1])


def test_deadlines_persist_restart_and_repeat_fifteen_minutes_after_delivery(review, monkeypatch):
    _, ctx, clock, published = review
    ticket = held(review)
    assert hold_review.reconcile(ctx) == 1900.0
    assert schedules(review)[0]['work_id'] == ticket.id
    assert published == []
    clock[0] = 1899.0
    assert hold_review.reconcile(ctx) == 1900.0
    assert published == []
    clock[0] = 1900.0
    assert hold_review.reconcile(ctx) == 2800.0
    assert len(published) == 1 and published[0]['actionable'] is True
    assert 'replacement hardware' in published[0]['said']
    consume(review)
    importlib.reload(hold_review)
    monkeypatch.setattr(hold_review, 'announce', lambda ctx, value: published.append(value))
    assert hold_review.reconcile(ctx) == 2800.0
    clock[0] = 2800.0
    assert hold_review.reconcile(ctx) == 3700.0
    assert len(published) == 2
    assert published[0]['signal_key'] != published[1]['signal_key']


def test_reminders_coalesce_due_tickets_pending_delivery_and_repeated_passes(review):
    _, ctx, clock, published = review
    first, second = held(review), held(review, task='Second waiting repair')
    hold_review.reconcile(ctx)
    clock[0] = 1900.0
    assert hold_review.reconcile(ctx) == 2800.0
    assert len(published) == 1
    assert {ticket['work_id'] for ticket in published[0]['tickets']} == {first.id, second.id}
    assert hold_review.reconcile(ctx) == 2800.0
    assert len(published) == 1
    clock[0] = 2800.0
    assert hold_review.reconcile(ctx) == 3700.0
    assert len(published) == 1
    consume(review)
    clock[0] = 3700.0
    assert hold_review.reconcile(ctx) == 4600.0
    assert len(published) == 2


@pytest.mark.parametrize('action', ['unhold', 'done', 'cancel', 'remove'])
def test_release_completion_cancellation_and_removal_cancel_deadlines(review, action):
    case, ctx, clock, published = review
    ticket = held(review)
    hold_review.reconcile(ctx)
    if action == 'unhold':
        case.store.unhold_all_work()
    elif action == 'done':
        case.store.finish_work(ticket.id, 'Completed repair.')
    elif action == 'cancel':
        case.store.finish_work(ticket.id, 'Cancelled by person.', outcome='cancelled')
    else:
        case.store.remove_work(ticket.id)
    hold_review.changed(event(review, [ticket.id]), ctx)
    assert schedules(review) == ()
    clock[0] = 1900.0
    assert hold_review.reconcile(ctx) is None
    assert published == []


def test_off_autostart_reads_nothing_and_emits_no_review(review, monkeypatch):
    _, ctx, _, published = review
    held(review)
    monkeypatch.setattr(ctx, 'setting', lambda name: False)
    monkeypatch.setattr(ctx, 'require_store', lambda: pytest.fail('paused reminders read storage'))
    assert hold_review.reconcile(ctx) is None
    assert published == []


@pytest.mark.parametrize('overrides', [
    {'kinds': ['note']}, {'tables': ['dispatch.session_lines']}, {'work_ids': []},
    {'project': 'another-project'}, {'base_id': None}, {'kinds': ['signal']},
    {'tables': ['map.hold_history']},
])
def test_unrelated_events_read_nothing(review, monkeypatch, overrides):
    _, ctx, _, _ = review
    payload = event(review, ['unrelated'], **overrides)
    monkeypatch.setattr(ctx, 'require_store', lambda: pytest.fail('unrelated event read storage'))
    hold_review.changed(payload, ctx)


def test_related_events_read_only_named_tickets_and_preserve_deadline_for_note_changes(review, monkeypatch):
    case, ctx, clock, _ = review
    first, other = held(review), held(review, task='Other held repair')
    hold_review.reconcile(ctx)
    captured = []
    original = Store.__getattr__
    def tracked(store, name):
        call = original(store, name)
        if name != 'work':
            return call
        def read(*args, **kwargs):
            captured.append(kwargs)
            return call(*args, **kwargs)
        return read
    monkeypatch.setattr(Store, '__getattr__', tracked)
    clock[0] = 1100.0
    hold_review.changed(event(review, [first.id]), ctx)
    assert captured == [{'ids': [first.id], 'limit': 0}]
    assert {row['deadline'] for row in schedules(review)} == {1900.0}
    case.store.set_work_hold(first.id, hold=True, hold_reason='Wait for owner decision.')
    hold_review.changed(event(review, [first.id]), ctx)
    deadlines = {row['work_id']: row['deadline'] for row in schedules(review)}
    assert deadlines == {first.id: 1900.0, other.id: 1900.0}


def test_seed_covers_all_bases_and_excludes_conversations_stages_and_closed_work(review):
    from metaform import home
    case, ctx, _, _ = review
    first = held(review)
    case.store.add_work(case.node, None, task='Conversation with the system agent', held=True)
    case.store.add_work(case.node, 'unbuilt', held=True, hold_reason='Legacy stage hold.')
    closed = held(review, task='Completed work')
    case.store.finish_work(closed.id, 'Done.')
    base = home.add_base(case.store.project_id, 'another')
    other = Store(case.store.project_id, base=base.id)
    other.layer('parts', 'test', 'Parts.', mutable=True, hideable=True)
    other.add_element('parts', 'code.other')
    second = other.add_work(Node('element', 'code.other'), None, task='Other base repair.', held=True,
                            hold_reason='Wait for delivery.')
    assert hold_review.reconcile(ctx) == 1900.0
    assert {row['work_id'] for row in schedules(review)} == {first.id, second.id}


def test_seed_does_not_repeat_project_scans_after_restart(review, monkeypatch):
    _, ctx, _, _ = review
    held(review)
    assert hold_review.reconcile(ctx) == 1900.0
    monkeypatch.setattr(Store, 'bases', lambda *args, **kwargs: pytest.fail('seed rescanned bases'))
    assert hold_review.reconcile(ctx) == 1900.0


def test_release_after_queued_review_retires_signal_and_cancels_deadline(review):
    from metaform.modules.dispatch import signals
    case, ctx, clock, published = review
    ticket = held(review)
    hold_review.reconcile(ctx)
    clock[0] = 1900.0
    hold_review.reconcile(ctx)
    assert len(published) == 1
    case.store.unhold_all_work()
    hold_review.changed(event(review, [ticket.id]), ctx)
    assert schedules(review) == ()
    assert not [value for value in signals.rows(case.store) if value['signal_key'].startswith('hold-review:')]
    assert hold_review.reconcile(ctx) is None


def test_newly_due_holds_merge_into_existing_pending_review(review):
    from metaform.modules.dispatch import signals
    case, ctx, clock, published = review
    first = held(review)
    hold_review.reconcile(ctx)
    clock[0] = 1100.0
    second = held(review, task='Later waiting repair')
    hold_review.changed(event(review, [second.id]), ctx)
    clock[0] = 1900.0
    assert hold_review.reconcile(ctx) == 2000.0
    key = published[0]['signal_key']
    clock[0] = 2000.0
    assert hold_review.reconcile(ctx) == 2800.0
    queued = [value for value in signals.rows(case.store) if value['signal_key'].startswith('hold-review:')]
    assert len(queued) == 1 and queued[0]['signal_key'] == key
    assert {ticket['work_id'] for ticket in queued[0]['tickets']} == {first.id, second.id}
    assert 'replacement hardware' in queued[0]['said']


def test_concurrent_due_passes_queue_one_review_and_advance_once(review):
    from concurrent.futures import ThreadPoolExecutor

    from metaform.modules.dispatch import signals
    case, ctx, clock, published = review
    held(review)
    hold_review.reconcile(ctx)
    clock[0] = 1900.0
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda _: hold_review.reconcile(ctx), range(2)))
    assert results == [2800.0, 2800.0]
    assert len(published) == 1
    assert len([value for value in signals.rows(case.store)
                if value['signal_key'].startswith('hold-review:')]) == 1


def test_dispatch_composition_and_autostart_share_retry_deadline(review, monkeypatch):
    _, ctx, _, _ = review
    module = importlib.import_module('metaform.modules.dispatch')
    recovery = importlib.import_module('metaform.modules.dispatch.recovery')
    orchestration = importlib.import_module('metaform.modules.dispatch.orchestration')
    assert {'hold_reviews', 'hold_review_state'} <= {table.name for table in module.TABLES.tables}
    assert any(subscription.topic == 'map.changed' and subscription.handler is module.hold_review_changed
               for subscription in module.MODULE.subscriptions)
    held(review)
    monkeypatch.setattr(module, 'halted', lambda *args: None)
    monkeypatch.setattr(recovery, 'recover', lambda ctx: {})
    monkeypatch.setattr(recovery, 'settle', lambda ctx: None)
    monkeypatch.setattr(orchestration, 'service', lambda ctx: None)
    monkeypatch.setattr(orchestration, 'drain', lambda ctx: [])
    monkeypatch.setattr(module, 'start_raised', lambda *args: None)
    monkeypatch.setattr(module, 'stay_connected', lambda *args: {})
    monkeypatch.setattr(module, 'start_work', lambda *args: {'started': []})
    assert module.autostart(ctx)['retry_due'] == 1900.0
    monkeypatch.setattr(module, 'halted', lambda *args: {'by': 'person'})
    monkeypatch.setattr(module, 'review_holds', lambda *args: pytest.fail('explicit halt started hold review'))
    assert module.autostart(ctx) == {'started': [], 'halted': 'person'}


def test_removed_base_cancels_persisted_deadline_without_reading_another_base(review):
    from metaform import home
    case, ctx, clock, published = review
    base = home.add_base(case.store.project_id, 'removed')
    other = Store(case.store.project_id, base=base.id)
    other.layer('parts', 'test', 'Parts.', mutable=True, hideable=True)
    other.add_element('parts', 'code.other')
    ticket = other.add_work(Node('element', 'code.other'), None, task='Other base repair.', held=True,
                            hold_reason='Wait for delivery.')
    assert hold_review.reconcile(ctx) == 1900.0
    assert schedules(review)[0]['work_id'] == ticket.id
    home.activate_base(case.store.project_id, 'main')
    home.remove_base(case.store.project_id, 'removed')
    clock[0] = 1900.0
    assert hold_review.reconcile(ctx) is None
    assert schedules(review) == ()
    assert published == []


def test_reason_change_at_deadline_does_not_postpone_review(review):
    case, ctx, clock, published = review
    ticket = held(review)
    assert hold_review.reconcile(ctx) == 1900.0
    clock[0] = 1899.0
    case.store.set_work_hold(ticket.id, hold=True, hold_reason='Wait for owner decision.')
    hold_review.changed(event(review, [ticket.id]), ctx)
    assert schedules(review)[0]['deadline'] == 1900.0
    clock[0] = 1900.0
    assert hold_review.reconcile(ctx) == 2800.0
    assert 'Wait for owner decision.' in published[0]['said']
    assert 'replacement hardware' not in published[0]['said']


def test_consumption_between_claim_and_merge_does_not_postpone_undelivered_hold(review, monkeypatch):
    from metaform.modules.dispatch import signals
    case, ctx, clock, published = review
    first = held(review)
    hold_review.reconcile(ctx)
    clock[0] = 1100.0
    second = held(review, task='Later waiting repair')
    hold_review.changed(event(review, [second.id]), ctx)
    clock[0] = 1900.0
    assert hold_review.reconcile(ctx) == 2000.0
    original = hold_review.record_signal
    consumed = []
    def consume_before_merge(*args, **kwargs):
        if not consumed:
            consume(review)
            consumed.append(True)
        return original(*args, **kwargs)
    monkeypatch.setattr(hold_review, 'record_signal', consume_before_merge)
    clock[0] = 2000.0
    assert hold_review.reconcile(ctx) == 2000.0
    deadlines = {row['work_id']: row['deadline'] for row in schedules(review)}
    assert deadlines == {first.id: 2800.0, second.id: 2000.0}
    assert len(published) == 1
    assert hold_review.reconcile(ctx) == 2800.0
    assert len(published) == 2
    queued = [value for value in signals.rows(case.store) if value['signal_key'].startswith('hold-review:')]
    assert {ticket['work_id'] for ticket in queued[0]['tickets']} == {second.id}
