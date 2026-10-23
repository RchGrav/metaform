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


def reasonless(review, task='Legacy waiting repair'):
    case, _, _, _ = review
    ticket = held(review, task=task)
    with Store(case.store.project_id, base=case.store.bound_base().id, module='map').tables() as tx:
        tx.update('ticket_settings', {'work_id': ticket.id}, {'hold_reason': ''})
    return ticket


def test_justified_hold_has_no_timer_or_repeated_review_after_restart(review, monkeypatch):
    _, ctx, clock, published = review
    held(review)
    assert hold_review.reconcile(ctx) is None
    for moment in (1900.0, 2800.0, 3700.0):
        clock[0] = moment
        assert hold_review.reconcile(ctx) is None
    importlib.reload(hold_review)
    monkeypatch.setattr(hold_review, 'announce', lambda ctx, value: published.append(value))
    assert hold_review.reconcile(ctx) is None
    assert published == []


def test_missing_legacy_reasons_coalesce_once_and_survive_restart(review, monkeypatch):
    _, ctx, clock, published = review
    first, second = reasonless(review), reasonless(review, task='Another legacy wait')
    assert hold_review.reconcile(ctx) is None
    assert len(published) == 1
    assert {ticket['work_id'] for ticket in published[0]['tickets']} == {first.id, second.id}
    consume(review)
    clock[0] = 1900.0
    importlib.reload(hold_review)
    monkeypatch.setattr(hold_review, 'announce', lambda ctx, value: published.append(value))
    assert hold_review.reconcile(ctx) is None
    assert len(published) == 1


@pytest.mark.parametrize('action', ['unhold', 'done', 'cancel', 'remove'])
def test_release_completion_cancellation_and_removal_retire_review(review, action):
    from metaform.modules.dispatch import signals
    case, ctx, _, published = review
    ticket = reasonless(review)
    hold_review.reconcile(ctx)
    assert len(published) == 1
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
    assert not [value for value in signals.rows(case.store) if value['signal_key'].startswith('hold-review:')]
    assert hold_review.reconcile(ctx) is None
    assert len(published) == 1


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
def test_unrelated_event_burst_reads_nothing(review, monkeypatch, overrides):
    _, ctx, _, _ = review
    payload = event(review, ['unrelated'], **overrides)
    monkeypatch.setattr(ctx, 'require_store', lambda: pytest.fail('unrelated event read storage'))
    for _ in range(100):
        hold_review.changed(payload, ctx)


def test_related_events_read_only_named_tickets_and_notes_do_not_wake_model(review, monkeypatch):
    case, ctx, _, published = review
    first = held(review)
    held(review, task='Other held repair')
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
    hold_review.changed(event(review, [first.id]), ctx)
    assert captured == [{'ids': [first.id], 'limit': 0}]
    case.store.set_work_hold(first.id, hold=True, hold_reason='Wait for owner decision.')
    hold_review.changed(event(review, [first.id]), ctx)
    assert published == []


def test_seed_covers_all_bases_excludes_conversations_stages_and_closed_work(review):
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
    assert hold_review.reconcile(ctx) is None
    assert {row['work_id'] for row in schedules(review)} == {first.id, second.id}


def test_seed_does_not_repeat_project_scans_after_restart(review, monkeypatch):
    _, ctx, _, _ = review
    held(review)
    assert hold_review.reconcile(ctx) is None
    monkeypatch.setattr(Store, 'bases', lambda *args, **kwargs: pytest.fail('seed rescanned bases'))
    assert hold_review.reconcile(ctx) is None


def test_recording_missing_reason_retires_pending_batch_without_new_review(review):
    from metaform.modules.dispatch import signals
    case, ctx, _, published = review
    ticket = reasonless(review)
    hold_review.reconcile(ctx)
    assert len(published) == 1
    case.store.set_work_hold(ticket.id, hold=True, hold_reason='Wait for an actual delivery.')
    hold_review.changed(event(review, [ticket.id]), ctx)
    assert not [value for value in signals.rows(case.store) if value['signal_key'].startswith('hold-review:')]
    assert hold_review.reconcile(ctx) is None
    assert len(published) == 1


def test_new_missing_reason_joins_existing_pending_batch(review):
    from metaform.modules.dispatch import signals
    case, ctx, _, published = review
    first = reasonless(review)
    hold_review.reconcile(ctx)
    second = reasonless(review, task='Later legacy wait')
    hold_review.changed(event(review, [second.id]), ctx)
    hold_review.reconcile(ctx)
    queued = [value for value in signals.rows(case.store) if value['signal_key'].startswith('hold-review:')]
    assert len(queued) == 1
    assert {ticket['work_id'] for ticket in queued[0]['tickets']} == {first.id, second.id}
    assert len(published) == 2  # new evidence updates one pending batch


def test_concurrent_passes_queue_one_legacy_review(review):
    from concurrent.futures import ThreadPoolExecutor
    _, ctx, _, published = review
    reasonless(review)
    hold_review.ensure(ctx)
    with ThreadPoolExecutor(max_workers=2) as workers:
        assert list(workers.map(lambda _: hold_review.reconcile(ctx), range(2))) == [None, None]
    assert len(published) == 1


def test_crash_after_claim_retries_same_batch_once(review, monkeypatch):
    _, ctx, _, published = review
    reasonless(review)
    original = hold_review.record_signal
    monkeypatch.setattr(hold_review, 'record_signal', lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('crash')))
    with pytest.raises(RuntimeError, match='crash'):
        hold_review.reconcile(ctx)
    key = schedules(review)[0]['signal_key']
    monkeypatch.setattr(hold_review, 'record_signal', original)
    hold_review.reconcile(ctx)
    assert len(published) == 1 and published[0]['signal_key'] == key
    hold_review.reconcile(ctx)
    assert len(published) == 1


def test_dispatch_autostart_keeps_explicit_stop_authority_and_no_hold_timer(review, monkeypatch):
    _, ctx, _, _ = review
    module = importlib.import_module('metaform.modules.dispatch')
    recovery = importlib.import_module('metaform.modules.dispatch.recovery')
    orchestration = importlib.import_module('metaform.modules.dispatch.orchestration')
    held(review)
    monkeypatch.setattr(module, 'halted', lambda *args: None)
    monkeypatch.setattr(recovery, 'recover', lambda ctx: {})
    monkeypatch.setattr(recovery, 'settle', lambda ctx: None)
    monkeypatch.setattr(orchestration, 'service', lambda ctx: None)
    monkeypatch.setattr(orchestration, 'drain', lambda ctx: [])
    monkeypatch.setattr(module, 'start_raised', lambda *args: None)
    monkeypatch.setattr(module, 'stay_connected', lambda *args: {})
    monkeypatch.setattr(module, 'start_work', lambda *args: {'started': []})
    assert module.autostart(ctx).get('retry_due') is None
    monkeypatch.setattr(module, 'halted', lambda *args: {'by': 'person'})
    monkeypatch.setattr(module, 'review_holds', lambda *args: pytest.fail('explicit halt started hold review'))
    assert module.autostart(ctx) == {'started': [], 'halted': 'person'}


def test_upgrade_retires_old_periodic_review_without_releasing_valid_work(review):
    from metaform.modules.dispatch import signals
    case, ctx, _, _ = review
    ticket = held(review)
    base_id = case.store.bound_base().id
    with Store(case.store.project_id, module='dispatch').tables() as tx:
        tx.insert('hold_review_state', {'name': 'seeded', 'initialized': 1, 'signal_key': 'hold-review:old'})
        tx.insert('hold_reviews', {'base_id': base_id, 'work_id': ticket.id, 'deadline': 1900.0,
                                  'reason': 'Wait for replacement hardware.', 'board': '',
                                  'signal_key': 'hold-review:old'})
    signals.record(case.store, hold_review.BOARD, key='hold-review:old', signal_key='hold-review:old',
                   actionable=True, tickets=[{'work_id': ticket.id}])
    assert hold_review.reconcile(ctx) is None
    assert not [value for value in signals.rows(case.store) if value['signal_key'] == 'hold-review:old']
    assert case.store.ticket(ticket.id).work.held
