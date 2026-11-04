"""Setup choices remain the standard agent permissions throughout a roundtable session."""
from __future__ import annotations

from importlib import import_module
from types import SimpleNamespace

import pytest

from metaform import events, settings
from metaform.data import Store
from metaform.module import Stop, context

pytestmark = pytest.mark.kind('fixture')


@pytest.fixture
def permissions_project(run, project_folder, monkeypatch):
    run('enable', 'dispatch', cwd=project_folder)
    return project_folder


@pytest.fixture
def roundtables(permissions_project, monkeypatch):
    roundtables = import_module('metaform.modules.roundtables')
    monkeypatch.setattr(roundtables, 'started', lambda *_: {'state': 'running'})
    monkeypatch.setattr(roundtables, 'model_of', lambda _ctx, _agent, model: model)
    return roundtables


def test_setup_captures_project_defaults_and_overrides_without_changing_them(permissions_project, roundtables):
    folder = permissions_project
    settings.put('dispatch_prompts', 'approve-reads', folder)
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('catalog', {'agent': 'claude', 'version': 'fixture', 'name': 'Claude',
                              'seen': '2026-11-04T00:00:00Z', 'seq': 1,
                              'settings': [{'id': 'mode', 'category': 'mode', 'type': 'select',
                                            'options': [{'value': 'default'}, {'value': 'plan'}]}]})
    settings.put('dispatch_claude_mode', 'plan', folder)
    ctx = context('roundtables', folder)
    captured = roundtables.permission_settings(ctx, {'claude': {'prompts': 'approve-all'}}, {'claude', 'codex'})
    assert captured == {'claude': {'prompts': 'approve-all', 'mode': 'plan'},
                        'codex': {'prompts': 'approve-reads', 'mode': ''}}
    assert settings.value('dispatch_prompts', folder) == 'approve-reads'
    assert settings.value('dispatch_claude_mode', folder) == 'plan'
    settings.put('dispatch_prompts', 'ask_all', folder)
    assert captured['codex']['prompts'] == 'approve-reads'


@pytest.mark.parametrize('choices', [[], {'other': {}}, {'claude': []}, {'claude': {'tools': 'all'}},
                                    {'claude': {'mode': True}}, {'claude': {'prompts': 'invented'}}])
def test_invalid_setup_permissions_are_rejected_before_starting(permissions_project, roundtables, choices):
    with pytest.raises(Stop):
        roundtables.permission_settings(context('roundtables', permissions_project), choices, {'claude'})


def test_open_retains_captured_choices_for_follower_and_all_session_phases(permissions_project, roundtables):
    ctx = context('roundtables', permissions_project, nouns={
        'topic': 'Build the shared documents.', 'seats': ['claude/opus'], 'chain': 1, 'judging': False,
        'permissions': {'claude': {'prompts': 'approve-reads'}}})
    answer = roundtables.open_table(ctx)
    ctx.nouns['table'] = answer['table']
    row = roundtables.table_row(ctx)
    assert row['followed']['permissions']['claude'] == {'prompts': 'approve-reads', 'mode': ''}
    assert row['followed']['judging'] is False
    assert row['followed']['session']['total'] == 1
    assert roundtables.status(ctx)['materials'] == row['followed']['session']['folder']
    folder = row['followed']['session']['folder']
    assert folder in row['opening'] and folder in row['followed']['session']['between']
    assert 'minutes will have been kept' not in row['opening'] + row['followed']['session']['between']
    assert 'create these documents together' in row['opening']


def test_engine_snapshot_keeps_the_same_permissions_between_phases(tmp_path, monkeypatch):
    from metaform.modules.roundtables.roundtable import store

    monkeypatch.setenv('ROUNDTABLE_HOME', str(tmp_path / 'engine'))
    selected = {'claude': {'prompts': 'approve-reads', 'mode': 'plan'}}
    number = store.opened({'subject': 'permissions', 'opening': 'Author documents together.',
                           'folder': str(tmp_path), 'chair_key': None, 'chair_token': 'fixture',
                           'reporter': 'acp:claude/opus', 'rounds': 0, 'spend': 0},
                          [{'kind': 'acp', 'id': 'acp:claude/opus', 'agent': 'claude', 'model': 'opus'}],
                          judging=False, permissions=selected)
    for phase in ('discussion', 'collaboration', 'scoring', 'farewell'):
        store.phase(number, phase, 'Continue the session.')
        assert store.discussion(number)['snapshot']['permissions'] == selected


def test_standard_policy_preserves_unknown_acp_options_and_only_auto_approves_selected_kinds():
    from metaform.modules import dispatch

    options = [{'optionId': 'future', 'name': 'Future option', 'kind': 'future_kind'},
               {'optionId': 'allow', 'name': 'Yes', 'kind': 'allow_once'},
               {'optionId': 'reject', 'name': 'No', 'kind': 'reject_once'}]
    assert dispatch.permission_choice(options, 'approve-reads', 'read') == 'allow'
    assert dispatch.permission_choice(options, 'approve-reads', 'search') == 'allow'
    assert dispatch.permission_choice(options, 'approve-reads', 'execute') is None
    assert dispatch.permission_choice(options, 'ask_all', 'read') is None
    assert dispatch.permission_choice(options, 'approve-all', 'execute') == 'allow'
    assert options[0]['kind'] == 'future_kind'


def test_chair_control_wakes_an_all_busy_panel_through_the_existing_relay(permissions_project, roundtables, monkeypatch):
    ctx = context('roundtables', permissions_project, nouns={
        'topic': 'A question.', 'seats': ['claude/opus'], 'judging': False})
    table_id = roundtables.open_table(ctx)['table']
    ctx.nouns['table'] = table_id
    with ctx.require_store().tables() as tx:
        tx.update('tables', {'table_id': table_id}, {'state': 'running', 'discussion': 27, 'chair': 'fixture'})
    monkeypatch.setattr(roundtables.engine, 'call', lambda *_, **__: {'state': 'running'})
    announced, payloads = events.announced, []

    def capture(*args, **kwargs):
        result, published = announced(*args, **kwargs)
        payloads.extend(published)
        return result, published

    monkeypatch.setattr(events, 'announced', capture)
    roundtables.chaired(ctx, 'advance')
    assert any('roundtables:control:27' in (payload.get('kinds') or []) for payload in payloads)


def test_web_start_passes_setup_permissions_to_the_roundtable_module(monkeypatch):
    from metaform.modules.web import server

    seen = []
    monkeypatch.setattr(server, 'module_verb', lambda _given, _module, _verb, nouns:
                        seen.append(nouns) or {'table': 'fixture'})
    sent = []
    handler = SimpleNamespace(send=lambda status, body: sent.append((status, body)))
    selected = {'claude': {'prompts': 'approve-reads', 'mode': 'plan'}}
    server.Handler.roundtable_open(handler, {'topic': 'A question.', 'chain': 1, 'permissions': selected})
    assert sent == [(200, {'table': 'fixture'})]
    assert seen[0]['permissions'] == selected and seen[0]['chain'] == 1


def test_end_restores_a_missing_follower_to_save_the_result(permissions_project, roundtables, monkeypatch):
    ctx = context('roundtables', permissions_project, nouns={
        'topic': 'A question.', 'seats': ['claude/opus'], 'judging': False})
    table_id = roundtables.open_table(ctx)['table']
    ctx.nouns['table'] = table_id
    with ctx.require_store().tables() as tx:
        tx.update('tables', {'table_id': table_id}, {'state': 'held', 'discussion': 27, 'chair': 'fixture'})
    monkeypatch.setattr(roundtables.engine, 'call', lambda *_, **__: {'state': 'ending'})
    monkeypatch.setattr(roundtables.follow, 'alive', lambda *_: False)
    followed = []
    monkeypatch.setattr(roundtables, 'started', lambda _ctx, table: followed.append(table) or {'state': 'ending'})
    assert roundtables.end(ctx)['state'] == 'ending'
    assert followed == [table_id]
