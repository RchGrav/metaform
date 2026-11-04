"""The configured budget reaches both the engine and the person's live controls."""
from importlib import import_module
from types import SimpleNamespace

import pytest

from metaform import settings
from metaform.module import Stop, context

pytestmark = pytest.mark.kind('fixture')


@pytest.fixture
def budget_project(run, project_folder, monkeypatch):
    run('enable', 'dispatch', cwd=project_folder)
    module = import_module('metaform.modules.roundtables')
    monkeypatch.setattr(module, 'started', lambda *_: {'state': 'running'})
    monkeypatch.setattr(module, 'model_of', lambda _ctx, _agent, model: model)
    return project_folder, module


def test_open_captures_project_budget_and_explicit_disable(budget_project):
    folder, module = budget_project
    settings.put('roundtables_token_budget', 12000, folder)
    for supplied, expected in (({}, 12000), ({'token_budget': 0}, 0), ({'token_budget': 2000}, 2000)):
        ctx = context('roundtables', folder, nouns={
            'topic': 'Create the shared documents.', 'seats': ['claude/opus'], 'judging': False,
            'chain': 1, **supplied})
        ctx.nouns['table'] = module.open_table(ctx)['table']
        assert module.table_row(ctx)['followed']['token_budget'] == expected
        assert module.status(ctx)['token_budget'] == expected
        assert module.table_row(ctx)['followed']['token_basis'] == 'uncached'
    assert settings.value('roundtables_token_budget', folder) == 12000


def test_phase_progress_is_current_even_with_no_new_follower_events(budget_project):
    from metaform.modules.roundtables.roundtable import budget, store

    folder, module = budget_project
    ctx = context('roundtables', folder, nouns={
        'topic': 'A question.', 'seats': ['claude/opus'], 'judging': False, 'token_budget': 500000})
    table_id = module.open_table(ctx)['table']
    ctx.nouns.update(table=table_id, after=9999)
    seats = [{'kind': 'acp', 'id': 'acp:claude/opus', 'agent': 'claude', 'model': 'opus'}]
    number = store.opened({'subject': table_id, 'opening': 'A question.', 'folder': str(folder),
                           'chair_key': None, 'chair_token': 'fixture', 'reporter': seats[0]['id'],
                           'rounds': 0, 'spend': 0}, seats,
                          [{'name': 'first', 'title': 'First topic', 'text': 'Explore.'}],
                          judging=False, token_budget=500000, token_basis='all')
    with ctx.require_store().tables() as tx:
        tx.update('tables', {'table_id': table_id}, {'discussion': number, 'state': 'held'})
    answer = module.table_events(ctx)
    assert answer['events'] == [] and answer['latest'] == 9999
    assert answer['phase_budget']['participants'][0]['tokens'] == 0
    budget.record_reply(store.discussion(number), store.seats(number)[0],
                        {'prompt_tokens': 12, 'cached_tokens': 462034, 'cache_write_tokens': 14223,
                         'completion_tokens': 3208}, 'first-current-reply')
    assert module.table_events(ctx)['phase_budget']['participants'][0]['tokens'] == 479477
    store.phase(number, 'collaboration', 'Write the shared documents.')
    current = module.table_events(ctx)['phase_budget']
    assert current['phase'] == 'collaboration' and current['topic'] == 1
    assert current['participants'][0]['tokens'] == 0


def test_phase_progress_rejects_a_stale_discussion_from_another_table(budget_project):
    from metaform.modules.roundtables.roundtable import store

    folder, module = budget_project
    ctx = context('roundtables', folder)
    seats = [{'kind': 'acp', 'id': 'acp:claude/opus', 'agent': 'claude', 'model': 'opus'}]
    number = store.opened({'subject': 'another-table', 'opening': 'Another question.', 'folder': str(folder),
                           'chair_key': None, 'chair_token': 'fixture', 'reporter': seats[0]['id'],
                           'rounds': 0, 'spend': 0}, seats, judging=False)
    assert module.phase_progress(ctx, {'table_id': 'requested-table', 'discussion': number}) is None


@pytest.mark.parametrize('invalid', [-1, True, 1.5, '1000', 9007199254740992])
def test_invalid_budget_is_rejected_before_start(budget_project, invalid):
    folder, module = budget_project
    ctx = context('roundtables', folder, nouns={
        'topic': 'A question.', 'seats': ['claude/opus'], 'judging': False, 'token_budget': invalid})
    with pytest.raises(Stop, match='non-negative whole number'):
        module.open_table(ctx)


def test_live_edit_updates_saved_budget_and_wakes_the_engine(budget_project, monkeypatch):
    folder, module = budget_project
    ctx = context('roundtables', folder, nouns={
        'topic': 'A question.', 'seats': ['claude/opus'], 'judging': False, 'token_budget': 1000})
    ctx.nouns['table'] = module.open_table(ctx)['table']
    with ctx.require_store().tables() as tx:
        tx.update('tables', {'table_id': ctx.nouns['table']},
                  {'state': 'running', 'discussion': 27, 'chair': 'fixture'})
    called = []

    def engine_call(*args, **kwargs):
        called.append((args, kwargs))
        return {'state': 'running', 'token_budget': kwargs['token_budget']}

    monkeypatch.setattr(module.engine, 'call', engine_call)
    ctx.nouns['token_budget'] = 5000
    assert module.set_token_budget(ctx)['token_budget'] == 5000
    assert called[0][0][1] == 'budget'
    assert called[0][1]['discussion'] == 27
    assert module.table_row(ctx)['followed']['token_budget'] == 5000
    # A follower imported before this feature still writes its old cursor snapshot.
    saved = module.table_row(ctx)['followed']
    with ctx.require_store().tables() as tx:
        tx.update('tables', {'table_id': ctx.nouns['table']}, {'followed': {**saved, 'token_budget': 1000}})
    assert module.status(ctx)['token_budget'] == 5000


def test_selected_basis_is_forwarded_without_resuming_a_held_table(budget_project, monkeypatch):
    folder, module = budget_project
    ctx = context('roundtables', folder, nouns={
        'topic': 'A question.', 'seats': ['claude/opus'], 'judging': False})
    ctx.nouns['table'] = module.open_table(ctx)['table']
    with ctx.require_store().tables() as tx:
        tx.update('tables', {'table_id': ctx.nouns['table']},
                  {'state': 'held', 'reason': 'held by its chair.', 'discussion': 27, 'chair': 'fixture'})
    seen = []
    monkeypatch.setattr(module.engine, 'call', lambda *args, **kwargs:
                        seen.append((args, kwargs)) or {'state': 'held', 'token_budget': 500000,
                                                     'token_basis': 'uncached'})
    ctx.nouns.update(token_budget=500000, token_basis='uncached')
    answer = module.set_token_budget(ctx)
    assert answer['state'] == 'held' and answer['token_basis'] == 'uncached'
    assert seen[0][0][1] == 'budget' and seen[0][1]['token_basis'] == 'uncached'
    assert module.table_row(ctx)['state'] == 'held'


@pytest.mark.parametrize('action', ['open', 'budget'])
def test_web_passes_zero_to_explicitly_disable_a_budget(monkeypatch, action):
    from metaform.modules.web import server

    seen, sent = [], []
    monkeypatch.setattr(server, 'module_verb', lambda _given, _module, verb, nouns:
                        seen.append((verb, nouns)) or {'table': 'fixture'})
    handler = SimpleNamespace(send=lambda status, body: sent.append((status, body)))
    given = {'table': 'fixture', 'topic': 'A question.', 'action': action, 'token_budget': 0}
    method = server.Handler.roundtable_open if action == 'open' else server.Handler.roundtable_control
    method(handler, given)
    assert sent == [(200, {'table': 'fixture'})]
    assert seen[0][1]['token_budget'] == 0


@pytest.mark.parametrize('invalid', [-1, True, 1.2, '1000', 9007199254740992])
def test_web_live_budget_rejects_invalid_values_without_calling_engine(monkeypatch, invalid):
    from metaform.modules.web import server

    called, sent = [], []
    monkeypatch.setattr(server, 'module_verb', lambda *args: called.append(args))
    handler = SimpleNamespace(send=lambda status, body: sent.append((status, body)))
    server.Handler.roundtable_control(handler, {'table': 'fixture', 'action': 'budget', 'token_budget': invalid})
    assert sent[0][0] == 400
    assert called == []


def test_budget_events_show_readable_warnings_once():
    import json

    from metaform.modules.roundtables.follow import Follower

    notice = {'phase': 'panel', 'percent': 50, 'text': 'Panel has reached 50% of its token budget.'}
    page = SimpleNamespace(get=lambda _path: {'events': [
        {'number': 7, 'kind': 'budget', 'text': json.dumps(notice)}]})
    emitted = []
    follower = SimpleNamespace(followed={}, emit=lambda *args, **kwargs: emitted.append((args, kwargs)))
    Follower.operational(follower, page, 1)
    Follower.operational(follower, page, 1)
    assert len(emitted) == 1
    assert emitted[0] == (('operational', 'person'), {'what': 'budget', 'text': notice['text'], 'budget': notice})


def test_detached_follower_preserves_a_new_live_budget_when_saving_older_cursors(budget_project):
    folder, module = budget_project
    ctx = context('roundtables', folder, nouns={
        'topic': 'A question.', 'seats': ['claude/opus'], 'judging': False, 'token_budget': 1000})
    table_id = module.open_table(ctx)['table']
    follower = module.follow.Follower(ctx, table_id)
    assert follower.followed['token_budget'] == 1000
    for value, event in ((5000, True), (0, False)):
        with ctx.require_store().tables() as tx:
            saved = dict(tx.get('tables', {'table_id': table_id}))
            tx.update('tables', {'table_id': table_id},
                      {'token_budget': value, 'followed': {**saved['followed'], 'token_budget': value}})
        follower.followed['turns'] = value + 7
        if event:
            follower.emit('operational', 'person', text='A completed turn.')
        else:
            follower.change(followed=follower.followed)
        ctx.nouns['table'] = table_id
        saved = module.table_row(ctx)['followed']
        assert saved['token_budget'] == follower.followed['token_budget'] == value
        assert saved['turns'] == value + 7


def test_upgrade_keeps_version_six_follower_writes_compatible_and_budget_independent(run, tmp_path):
    from dataclasses import replace

    from metaform.data import Store
    from metaform.data.tables import TableTx, ensure, project_store, project_transaction
    from metaform.modules.roundtables import TABLES

    folder = tmp_path / 'legacy-budget'
    folder.mkdir()
    run('add', 'project', 'legacy-budget', str(folder))
    legacy = replace(TABLES, version=6, tables=tuple(
        replace(table, columns=tuple(column for column in table.columns if column.name != 'token_budget'))
        for table in TABLES.tables))
    file = project_store('legacy-budget', 'roundtables')
    file.parent.mkdir(parents=True, exist_ok=True)
    with project_transaction(file, write=True) as db:
        ensure(db, file, 'roundtables', legacy, 'project')
        tx = TableTx('roundtables', legacy, write=True, opener=lambda _: (db, file, True), bound='project')
        tx.insert('tables', {'table_id': 'existing', 'topic': 'Keep the evidence.', 'opening': 'Original instructions.',
                            'seats': ['acp:claude/opus'], 'spend': 0, 'state': 'held',
                            'created': '2026-11-04T00:00:00Z', 'followed': {'turns': 3}})
    with Store('legacy-budget', module='roundtables').tables() as tx:
        tx.update('tables', {'table_id': 'existing'},
                  {'token_budget': 5000, 'followed': {'turns': 3, 'token_budget': 5000}})
    with project_transaction(file, write=True) as db:
        ensure(db, file, 'roundtables', legacy, 'project')
        tx = TableTx('roundtables', legacy, write=True, opener=lambda _: (db, file, True), bound='project')
        tx.update('tables', {'table_id': 'existing'}, {'followed': {'turns': 4}})
    with Store('legacy-budget', module='roundtables').tables(write=False) as tx:
        saved = tx.get('tables', {'table_id': 'existing'})
    assert saved['token_budget'] == 5000 and saved['followed'] == {'turns': 4}
    assert saved['opening'] == 'Original instructions.' and saved['state'] == 'held'
