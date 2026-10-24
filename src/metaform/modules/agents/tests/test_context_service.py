"""Context delivery and v5 role-factory retirement preserve durable evidence."""
from __future__ import annotations

import json
import sqlite3

import pytest

from metaform import home as metaform_home
from metaform import prompt_files
from metaform.data import Column, Store, Table, Tables
from metaform.data import tables as table_storage
from metaform.module import (
    advance_agent_context,
    agent_context_epoch,
    context,
    prepare_agent_context,
    provided,
    record_agent_context,
)
from metaform.modules import agents

pytestmark = pytest.mark.kind('fixture')


def test_chassis_context_provider_acknowledges_only_recorded_delivery(project_folder):
    providers = provided(project_folder, 'agent.context')
    assert len(providers) == 1
    assert providers[0][0] == 'agents'
    assert type(providers[0][1]).__name__ == 'ContextService'
    assert provided(project_folder, 'agent.role') == []
    component = prompt_files.component('task:example', 'Exact assigned instructions.', version_id='v1')
    first = prepare_agent_context(project_folder, 'recipient', [component])
    assert first['epoch'] == 0
    assert len(first['components']) == 1
    assert prepare_agent_context(project_folder, 'recipient', [component]) == first
    accepted = record_agent_context(project_folder, 'recipient', first['components'],
                                    epoch=first['epoch'], channel='tool_result')
    assert accepted == {'recorded': 1, 'epoch': 0}
    retained = prepare_agent_context(project_folder, 'recipient', [component])
    assert retained['components'] == []
    assert retained['previous']['task:example']['channel'] == 'tool_result'
    assert len(prepare_agent_context(project_folder, 'another-recipient', [component])['components']) == 1
    assert agent_context_epoch(project_folder, 'recipient') == 0
    assert advance_agent_context(project_folder, 'recipient', reason='compaction') == 1
    stale = record_agent_context(project_folder, 'recipient', first['components'], epoch=0)
    assert stale == {'recorded': 0, 'epoch': 0, 'current_epoch': 1, 'stale': True}
    assert len(prepare_agent_context(project_folder, 'recipient', [component])['components']) == 1


def test_changed_components_use_current_sources_without_resolving_a_role(project_folder):
    service = provided(project_folder, 'agent.context')[0][1]
    ctx = context('agents', project_folder)
    first = prompt_files.component('task:example', 'Initial instructions.', version_id='v1')
    second = prompt_files.component('task:example', 'Changed instructions.', version_id='v2')
    assert service.changes(ctx, 'recipient', [second]) == []
    service.record(ctx, 'recipient', [first])
    notices = service.changes(ctx, 'recipient', [second])
    assert len(notices) == 1
    assert notices[0]['actual_version_id'] == 'v2'
    assert notices[0]['previous'] == first['rendered_fingerprint']
    assert service.changes(ctx, 'recipient', [second]) == notices
    service.delivered_changes(ctx, 'recipient', notices)
    assert service.changes(ctx, 'recipient', [second]) == []
    assert len(service.prepare(ctx, 'recipient', [second])['components']) == 1


def test_v5_upgrade_preserves_evidence_and_backs_up_retired_live_tables(home, project_folder, monkeypatch):
    definitions = Table('definitions', place='project', key=('name',), columns=(
        Column('name', required=True), Column('purpose', required=True), Column('prompts', 'json', required=True),
        Column('source', 'json', required=True), Column('version_id', required=True), Column('at', required=True)))
    sources = Table('role_sources', place='project', key=('name', 'provider'), columns=(
        Column('name', required=True), Column('provider', required=True), Column('purpose', required=True),
        Column('prompts', 'json', required=True)))
    old = Tables(version=5, compatible_from=1, tables=(*agents.TABLES.tables, definitions, sources))
    original_declared = table_storage.declared
    with monkeypatch.context() as patch:
        patch.setattr(table_storage, 'declared', lambda module, **kwargs:
                      old if module == 'agents' else original_declared(module, **kwargs))
        store = Store('proj', module='agents')
        component = prompt_files.component('prompt.test:instruction', 'Historic delivered text.', version_id='v-old')
        history = {'name': 'historic_role', 'seq': 1, 'purpose': 'Historical definition.',
                   'prompts': ['prompt.test:instruction'], 'source': {'duty': 'Historic authored duty.'},
                   'version_id': 'v-old', 'at': '2026-10-20T10:00:00Z'}
        rows = {
            'definition_history': history,
            'definitions': {key: value for key, value in history.items() if key != 'seq'},
            'role_sources': {'name': 'historic_role', 'provider': 'agents', 'purpose': history['purpose'],
                             'prompts': history['prompts']},
            'contexts': {'session_id': 'historic-session', 'epoch': 2, 'reason': 'compaction', 'at': history['at']},
            'receipts': {'session_id': 'historic-session', 'epoch': 2, 'name': component['name'],
                         'fingerprint': component['rendered_fingerprint'], 'actual_version_id': 'v-old',
                         'selected_version_id': 'v-old', 'component': component, 'channel': 'turn', 'at': history['at']},
            'sent': {'session_id': 'historic-session', 'seq': 1, 'work_id': 'historic-work', 'runner': 'historic-runner',
                     'role': 'historic_role', 'agent': 'codex', 'at': history['at'], 'prompts': [component]},
            'delivered_text': {'session_id': 'historic-session', 'epoch': 2,
                               'fingerprint': component['rendered_fingerprint'], 'at': history['at']},
            'change_notices': {'session_id': 'historic-session', 'epoch': 2, 'name': component['name'],
                               'fingerprint': component['rendered_fingerprint']},
            'context_checks': {'session_id': 'historic-session', 'epoch': 2, 'checkpoint': 'historic-check',
                               'marker': 'historic-marker', 'pending': False, 'confirmed': True},
        }
        with store.tables() as tx:
            for table, row in rows.items():
                tx.insert(table, row)
    path = metaform_home.project_folder('proj') / 'modules' / 'agents.sqlite3'

    def snapshot(database):
        with sqlite3.connect(database) as db:
            names = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            record = json.loads(db.execute("SELECT value FROM meta WHERE key='module:agents'").fetchone()[0])
            data = {table: db.execute(f'SELECT * FROM "agents.{table}"').fetchall()
                    for table in rows if f'agents.{table}' in names}
        return names, record, data

    _, before_record, before = snapshot(path)
    assert before_record['version'] == 5
    with Store('proj', module='agents').tables(write=False) as tx:
        for table in set(rows) - {'definitions', 'role_sources'}:
            assert dict(tx.rows(table, limit=0).results[0]) == rows[table]
    names, upgraded, after = snapshot(path)
    assert upgraded['version'] == upgraded['compatible_from'] == 6
    assert 'agents.definitions' not in names
    assert 'agents.role_sources' not in names
    assert after == {table: row for table, row in before.items() if table not in {'definitions', 'role_sources'}}
    backups = list((home / 'backups').glob('module-agents-6/*/*/agents.sqlite3'))
    assert len(backups) == 1
    _, backup_record, backup_data = snapshot(backups[0])
    assert backup_record == before_record
    assert backup_data == before
    assert prepare_agent_context(project_folder, 'historic-session', [component])['components'] == []
