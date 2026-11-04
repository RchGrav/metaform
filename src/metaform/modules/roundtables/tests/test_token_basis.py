"""Explicit accounting changes rebase one phase from raw evidence, preserving the conversation and billing."""
import json
import time
from unittest.mock import Mock

import pytest

from metaform.modules.roundtables.roundtable import budget, server, store

pytestmark = pytest.mark.kind('simulation')

USE = {'prompt_tokens': 12, 'cached_tokens': 462034, 'cache_write_tokens': 14223, 'completion_tokens': 3208,
       'reasoning_tokens': 1000, 'cost': .23}


@pytest.fixture
def tables(home, tmp_path, monkeypatch):
    monkeypatch.setenv('ROUNDTABLE_HOME', str(tmp_path / 'engine'))
    spawn = Mock()
    monkeypatch.setattr(server.runner, 'spawn', spawn)
    monkeypatch.setattr(server.events, 'publish', Mock())

    def make(**options):
        seats = [{'kind': 'acp', 'id': 'acp:claude/opus', 'agent': 'claude', 'model': 'opus'}]
        role = {**seats[0], 'name': 'Opus'}
        return store.opened({'subject': 'Token basis', 'opening': 'Preserve the conversation.',
                             'folder': str(tmp_path), 'chair_token': 'fixture', 'reporter': seats[0]['id'],
                             'host': role, 'synthesizer': role, 'rounds': 0, 'spend': 1}, seats,
                            [{'name': str(at), 'title': f'Topic {at+1}', 'text': 'Discuss evidence.'}
                             for at in range(4)], judging=False, token_budget=500000, **options)

    return make, spawn


def test_selected_transport_metrics_exclude_cache_reads_without_double_counting_reasoning():
    openrouter = {'prompt_tokens': 476269, 'cached_tokens': 462034, 'completion_tokens': 3208,
                  'reasoning_tokens': 1000}
    for kind, use in (('acp', USE), ('openrouter', openrouter)):
        assert budget.tokens(use, kind, 'uncached') == (17443, True)
        assert budget.tokens(use, kind, 'all') == (479477, True)
        assert budget.tokens(use, kind, 'output') == (3208, True)
    assert budget.tokens({'prompt_tokens': 5, 'cached_tokens': 10, 'completion_tokens': 2},
                         'openrouter', 'uncached') == (2, True)
    assert budget.tokens({'used': 70000, 'reasoning_tokens': 10}, 'acp', 'uncached') == (0, False)


def test_new_tables_default_to_selected_metric_but_missing_legacy_setting_keeps_all(tables):
    make, _ = tables
    number = make()
    assert budget.basis(store.discussion(number)) == 'uncached'
    found = store.discussion(number)
    snapshot = dict(found['snapshot'])
    snapshot.pop('token_basis')
    store.change(number, snapshot=snapshot)
    assert budget.progress(store.discussion(number))['basis'] == 'all'
    server.budget(number, 400000, chair='fixture')
    assert budget.basis(store.discussion(number)) == 'all'
    assert 'token_basis' not in store.discussion(number)['snapshot']


def test_held_legacy_current_phase_recounts_t298_and_preserves_history_billing_and_state(tables, tmp_path):
    make, spawn = tables
    number = make(token_basis='all')
    snapshot = dict(store.discussion(number)['snapshot'])
    snapshot.pop('token_basis')
    store.change(number, topic=2, snapshot=snapshot)
    store.phase(number, 'collaboration', 'Previous collaboration.')
    row = store.seats(number)[0]
    budget.record_reply(store.discussion(number), row, {'prompt_tokens': 715295}, 'previous-phase')
    store.change(number, topic=3)
    store.phase(number, 'collaboration', 'New collaboration.')
    found = store.discussion(number)
    record = store.record(number, {'topic': 3, 'round': 1, 'position': 0, 'kind': 'collab', 'seat': row['id'],
                                   'name': row['name'], 'text': 'Actual T298 reply.', **USE})
    # Old installations have an eight-column receipt and a linked raw submission, with no raw-receipt table row.
    with store.connect() as db:
        db.execute('INSERT INTO phase_replies VALUES (?,?,?,?,?,?,?,?)',
                   (number, 'legacy-t298', 3, 'collaboration', 0, 479477, 1, record['number']))
        db.execute('INSERT INTO phase_usage(discussion,topic,phase,position,tokens,reported) VALUES (?,?,?,?,?,?)',
                   (number, 3, 'collaboration', 0, 479477, 1))
    budget.evaluate(found)
    store.spend(number, .23)
    messages = [{'role': 'user', 'content': 'Saved native context, once.'}]
    pending = {'topic': 3, 'notice': 100, 'closing': True}
    store.seat_change(number, 0, messages=messages, session='unchanged-native-session',
                      extra={'collaboration_request': pending})
    store.change(number, state='held', reason='held by its chair.')
    document = tmp_path / 'shared.md'
    document.write_text('Shared document remains intact.', encoding='utf-8')
    raw_before = store.submission(number, record['number'])
    events_before = store.events(number)
    with store.connect() as db:
        history = [tuple(one) for one in db.execute('SELECT * FROM phase_usage WHERE discussion=? AND topic=2',
                                                    (number,))]
    answer = server.budget(number, 500000, chair='fixture', token_basis='uncached')
    assert answer['state'] == 'held' and answer['reason'] == 'held by its chair.'
    assert answer['token_budget'] == 500000 and answer['token_basis'] == 'uncached'
    assert answer['phase_budget']['participants'][0]['tokens'] == 17443
    assert not answer['phase_budget']['closing'] and not answer['phase_budget']['forced']
    assert answer['phase_budget']['notices'] == []
    assert store.submission(number, record['number']) == raw_before
    assert store.discussion(number)['spent'] == .23
    kept = store.seats(number)[0]
    assert kept['messages'] == messages and kept['session'] == 'unchanged-native-session'
    assert kept['extra']['collaboration_request'] == {'topic': 3, 'notice': 0, 'closing': False}
    assert document.read_text(encoding='utf-8') == 'Shared document remains intact.'
    assert store.events(number)[:len(events_before)] == events_before
    assert json.loads(store.events(number)[-1]['text'])['action'] == 'reconfigured'
    with store.connect() as db:
        assert [tuple(one) for one in db.execute('SELECT * FROM phase_usage WHERE discussion=? AND topic=2',
                                                 (number,))] == history
        assert db.execute('SELECT tokens FROM phase_replies WHERE discussion=? AND reply=?',
                           (number, 'legacy-t298')).fetchone()[0] == 17443
    spawn.assert_not_called()


def test_raw_receipts_recount_pending_replies_once_and_neutralize_old_closing_metadata(tables):
    make, _ = tables
    number = make(token_basis='all')
    found, row = store.discussion(number), store.seats(number)[0]
    budget.record_reply(found, row, USE, 'completed-unrecorded')
    pending = {'topic': 0, 'round': 1, 'original': 'Completed physical reply.', 'use': dict(USE),
               'usage_id': 'completed-unrecorded', 'notice': 100, 'closing': True}
    store.seat_change(number, 0, extra={'panel_reply': pending})
    store.change(number, state='held')
    server.budget(number, 500000, chair='fixture', token_basis='uncached')
    kept = store.seats(number)[0]['extra']['panel_reply']
    assert kept['usage_id'] == pending['usage_id'] and kept['original'] == pending['original']
    assert kept['use'] == USE and kept['notice'] == 0 and kept['closing'] is False
    assert budget.progress(store.discussion(number))['participants'][0]['tokens'] == 17443
    # A recovered duplicate receipt adds no tokens; a new reply uses the CURRENT basis despite an old snapshot.
    budget.record_reply(found, row, USE, 'completed-unrecorded')
    budget.record_reply(found, row, USE, 'new-physical-reply')
    assert budget.progress(store.discussion(number))['participants'][0]['tokens'] == 34886


def test_missing_original_usage_refuses_metric_change_atomically(tables):
    make, _ = tables
    number = make(token_basis='all')
    with store.connect() as db:
        db.execute('INSERT INTO phase_replies VALUES (?,?,?,?,?,?,?,?)',
                   (number, 'unrecoverable-old-reply', 0, 'panel', 0, 479477, 1, None))
        db.execute('INSERT INTO phase_usage(discussion,topic,phase,position,tokens,reported) VALUES (?,?,?,?,?,?)',
                   (number, 0, 'panel', 0, 479477, 1))
    store.change(number, state='held')
    before = store.discussion(number)
    with pytest.raises(server.ToolError, match='original usage.*missing'):
        server.budget(number, 300000, chair='fixture', token_basis='uncached')
    assert store.discussion(number) == before
    assert budget.progress(before)['participants'][0]['tokens'] == 479477
    assert store.events(number) == []


@pytest.mark.parametrize('state', ['running', 'held'])
def test_actual_basis_change_waits_for_a_runner_to_stop(tables, state):
    make, _ = tables
    number = make(token_basis='all')
    store.change(number, state=state, runner='old-active-runner', budget_runner='old-active-runner', beat=time.time())
    before = store.discussion(number)
    with pytest.raises(server.ToolError, match='wait until its runner stops before changing token accounting'):
        server.budget(number, 500000, chair='fixture', token_basis='uncached')
    assert store.discussion(number) == before


def test_concurrent_continue_claim_between_outer_check_and_configure_cannot_change_basis(tables, monkeypatch):
    make, spawn = tables
    number = make(token_basis='all')
    budget.record_reply(store.discussion(number), store.seats(number)[0], USE, 'preserved-receipt')
    store.change(number, state='held')
    before = store.discussion(number)
    notices = store.events(number)
    configured = budget.configure

    def continue_then_configure(found, maximum, token_basis=None):
        assert not server.runner.alive(found), 'The outer check read the stopped runner.'
        store.change(number, state='running')
        assert store.claim(number, 'concurrent-continue', server.runner.STALE)
        return configured(found, maximum, token_basis)

    monkeypatch.setattr(budget, 'configure', continue_then_configure)
    try:
        with pytest.raises(server.ToolError, match='wait until its runner stops before changing token accounting'):
            server.budget(number, 300000, chair='fixture', token_basis='uncached')
        after = store.discussion(number)
        assert after['snapshot'] == before['snapshot']
        assert after['state'] == 'running' and after['runner'] == 'concurrent-continue'
        assert budget.progress(after)['participants'][0]['tokens'] == 479477
        assert store.events(number) == notices
        spawn.assert_not_called()
    finally:
        store.release(number, 'concurrent-continue')
