"""The independent observer explains a live panel without rewriting its event sequence or documents."""
import asyncio
import importlib
import json
import queue
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

pytestmark = pytest.mark.kind('simulation')


@pytest.fixture
def panel(run, tmp_path, monkeypatch):
    folder = tmp_path / 'project'
    folder.mkdir()
    run('add', 'project', 'summary-project', str(folder))
    run('enable', 'dispatch', cwd=folder)
    from metaform.module import context
    from metaform.modules.roundtables.roundtable import store as engine_store

    module = importlib.import_module('metaform.modules.roundtables.live_summary')
    ctx = context('roundtables', folder)
    monkeypatch.setenv('ROUNDTABLE_HOME', str(tmp_path / 'engine'))
    chosen = [{'kind': 'acp', 'id': 'acp:claude/opus', 'agent': 'claude', 'model': 'opus'}]
    role = {**chosen[0], 'name': 'Opus'}
    number = engine_store.opened({'subject': 'Evidence', 'opening': 'Explain the options.', 'folder': str(folder),
                                  'chair_key': None, 'chair_token': 'fixture', 'reporter': chosen[0]['id'],
                                  'host': role, 'synthesizer': role, 'rounds': 1, 'spend': 0}, chosen, judging=False)
    store = ctx.require_store()
    shared = folder / 'shared'
    shared.mkdir()
    with store.tables() as tx:
        tx.insert('tables', {'table_id': 'panel', 'topic': 'What should we build?', 'opening': 'Discuss evidence.',
                             'seats': ['acp:claude/opus'], 'spend': 0, 'state': 'running', 'discussion': number,
                             'created': module.now(), 'followed': {'session': {'folder': str(shared)},
                                 'permissions': {'claude': {'prompts': 'ask_all', 'mode': ''}}}})
    writes = queue.Queue()
    original = module.Background.write

    def written(self, table_id, **changes):
        result = original(self, table_id, **changes)
        writes.put(changes)
        return result

    monkeypatch.setattr(module.Background, 'write', written)
    services = []

    def started():
        service = module.start(ctx)
        assert service is not None
        services.append(service)
        return service

    yield SimpleNamespace(module=module, ctx=ctx, store=store, folder=folder, shared=shared, number=number,
                          writes=writes, start=started)
    for service in services:
        service.close()


def record(panel, seq, *, topic=1, kind='turn', text='Use the existing event bus.', outcome='kept', stage=None):
    payload = {'topic': topic, 'seat': 'Opus', 'text': text, 'outcome': outcome}
    if stage is not None:
        payload = {'topic': topic, 'stage': stage}
    with panel.store.tables() as tx:
        tx.insert('events', {'table_id': 'panel', 'seq': seq, 'kind': kind, 'audience': 'table',
                             'payload': payload, 'at': panel.module.now()})


def changed(panel, service):
    service.heard({'project': panel.ctx.project, 'tables': ['roundtables.events'], 'kinds': ['roundtables:panel']})


def state(panel, wanted):
    while True:  # block on actual writes, never poll the store
        change = panel.writes.get(timeout=5)
        if change.get('state') == wanted:
            return panel.module.snapshot(panel.ctx, 'panel')


@pytest.fixture
def model(panel, monkeypatch):
    calls = queue.Queue()
    closed = queue.Queue()

    class Session:
        def __init__(self, *args, **kwargs):
            self.args, self.kwargs = args, kwargs
            self.cancelled = threading.Event()
            self.late = False

        async def start(self):
            return None

        async def prompt(self, asked, timeout):
            self.asked = asked
            self.loop = asyncio.get_running_loop()
            self.reply = self.loop.create_future()
            self.kwargs['on_sent']()
            calls.put(self)
            try:
                return await self.reply
            except asyncio.CancelledError:
                self.cancelled.set()
                if self.late:
                    return 'A late reply must not resurrect an aborted panel.', {}
                raise

        def answer(self, text='A clear explanation.', usage=None):
            value = (text, usage or {'prompt_tokens': 10, 'completion_tokens': 5, 'model': 'haiku'})
            self.loop.call_soon_threadsafe(self.reply.set_result, value)

        def fail(self):
            self.loop.call_soon_threadsafe(self.reply.set_exception, RuntimeError('Native agent unavailable'))

        async def close(self):
            closed.put(self)

    monkeypatch.setattr(panel.module, 'Session', Session)
    return SimpleNamespace(calls=calls, closed=closed)


def test_bootstrap_explains_current_panel_in_one_call_without_changing_follower_history(panel, model):
    for seq in range(1, 101):
        record(panel, seq, text=f'Old panel evidence {seq}.')
    record(panel, 101, topic=2, kind='stage', stage='discussion')
    for seq in range(102, 122):
        record(panel, seq, topic=2, text=f'Current evidence {seq}.')
    record(panel, 122, topic=2, text='PASS', outcome='pass')
    record(panel, 123, topic=2, kind='veto', text='A disputed proposal.')
    document = panel.shared / 'joint-proposal.md'
    document.write_text('The agents own these materials.', encoding='utf-8')
    service = panel.start()
    call = model.calls.get(timeout=5)
    assert 'Current evidence 102.' in call.asked and 'Current evidence 121.' in call.asked
    assert 'Old panel evidence' not in call.asked and 'Opus: PASS' not in call.asked
    assert 'vetoed proposal' in call.asked and 'A disputed proposal.' in call.asked
    assert call.kwargs['permission_settings'] == {'prompts': 'ask_all', 'mode': ''}
    assert call.kwargs['command'] and 'fake_agent.py' in call.kwargs['command']
    call.answer('The current panel compares two choices and their evidence.')
    result = state(panel, 'ready')
    assert result['through_seq'] == 123 and result['text'].startswith('The current panel')
    assert result['updated'] and result['error'] is None
    with panel.store.tables(write=False) as tx:
        assert len(tx.rows('events', {'table_id': 'panel'}, limit=0).results) == 123
        assert tx.get('live_summaries', {'table_id': 'panel'})['usage']['prompt_tokens'] == 10
    assert document.read_text(encoding='utf-8') == 'The agents own these materials.'
    assert model.calls.empty()
    service.close()


def test_new_turns_coalesce_while_haiku_works_and_unrelated_changes_do_no_reads(panel, model, monkeypatch):
    record(panel, 1, text='The first proposal.')
    service = panel.start()
    first = model.calls.get(timeout=5)
    for seq in range(2, 12):
        record(panel, seq, text=f'Follow-up evidence {seq}.')
        changed(panel, service)
    first.answer('Initial interpretation.')
    second = model.calls.get(timeout=5)
    assert 'Initial interpretation.' in second.asked
    assert 'Follow-up evidence 2.' in second.asked and 'Follow-up evidence 11.' in second.asked
    second.answer('The updated interpretation.')
    state(panel, 'ready')
    result = state(panel, 'ready')
    assert result['through_seq'] == 11
    read = Mock(wraps=service.store.tables)
    monkeypatch.setattr(service.store, 'tables', read)
    for _ in range(20):
        service.heard({'project': panel.ctx.project, 'tables': ['roundtables.live_summaries'],
                       'kinds': ['roundtables:panel']})
        service.heard({'project': panel.ctx.project, 'tables': ['work'], 'kinds': ['note']})
        service.heard({'project': 'another', 'kinds': ['roundtables:panel']})
    read.assert_not_called()
    assert model.calls.empty()


def test_error_keeps_last_summary_and_only_new_evidence_retries(panel, model):
    with panel.store.tables() as tx:
        tx.insert('live_summaries', {'table_id': 'panel', 'text': 'Earlier useful account.', 'through_seq': 1,
                                     'state': 'ready', 'usage': {'prompt_tokens': 7}})
    record(panel, 1, text='Earlier evidence.')
    record(panel, 2, text='The new proposal.')
    service = panel.start()
    first = model.calls.get(timeout=5)
    first.fail()
    result = state(panel, 'error')
    assert result['text'] == 'Earlier useful account.' and result['through_seq'] == 2
    assert 'Native agent unavailable' in result['error']
    changed(panel, service)
    record(panel, 3, text='Additional evidence for the proposal.')
    changed(panel, service)
    second = model.calls.get(timeout=5)
    assert 'The new proposal.' not in second.asked and 'Additional evidence' in second.asked
    second.answer('The recovered explanation.')
    result = state(panel, 'ready')
    assert result['through_seq'] == 3 and result['error'] is None
    with panel.store.tables(write=False) as tx:
        assert tx.get('live_summaries', {'table_id': 'panel'})['usage']['prompt_tokens'] == 17
    assert model.calls.empty()


def test_close_cancels_native_work_and_preserves_prior_text(panel, model):
    record(panel, 1)
    service = panel.start()
    call = model.calls.get(timeout=5)
    service.close()
    assert call.cancelled.is_set() and model.closed.get(timeout=1) is call
    assert not service.thread.is_alive()
    assert panel.module.snapshot(panel.ctx, 'panel')['state'] == 'paused'


def test_abort_cancels_observer_and_late_reply_cannot_recreate_saved_summary(panel, model):
    record(panel, 1)
    service = panel.start()
    call = model.calls.get(timeout=5)
    call.late = True
    with panel.store.tables() as tx:
        tx.delete('tables', {'table_id': 'panel'})
        tx.delete('live_summaries', {'table_id': 'panel'})
    changed(panel, service)
    assert model.closed.get(timeout=5) is call
    assert call.cancelled.is_set()
    with panel.store.tables(write=False) as tx:
        assert tx.get('tables', {'table_id': 'panel'}) is None
        assert tx.get('live_summaries', {'table_id': 'panel'}) is None


def test_direct_engine_abort_cancels_when_wrapper_row_still_exists_and_rejects_late_ready_write(panel, model):
    record(panel, 1)
    service = panel.start()
    call = model.calls.get(timeout=5)
    call.late = True
    with panel.store.tables() as tx:
        tx.update('tables', {'table_id': 'panel'}, {'state': 'ended', 'reason': 'aborted by its chair'})
    changed(panel, service)
    assert model.closed.get(timeout=5) is call
    assert call.cancelled.is_set()
    result = panel.module.snapshot(panel.ctx, 'panel')
    assert result['state'] == 'paused' and result['text'] == ''
    with panel.store.tables(write=False) as tx:
        assert tx.get('live_summaries', {'table_id': 'panel'})['text'] is None


def test_web_successor_waits_for_existing_observer_then_resumes_without_duplicate_model_calls(panel, model):
    record(panel, 1)
    first = panel.start()
    call = model.calls.get(timeout=5)
    second = panel.start()
    assert model.calls.empty()
    first.close()
    assert call.cancelled.is_set()
    record(panel, 2, text='New evidence after the successor took ownership.')
    changed(panel, second)
    resumed = model.calls.get(timeout=5)
    assert 'New evidence after the successor' in resumed.asked
    assert 'Opus: Use the existing event bus.' not in resumed.asked
    resumed.answer('The successor explains the saved evidence.')
    assert state(panel, 'ready')['through_seq'] == 2
    assert model.calls.empty()
    second.close()


def test_restart_after_failed_sent_batch_never_replays_its_source_turns(panel, model):
    record(panel, 1, text='The already delivered proposal.')
    first = panel.start()
    call = model.calls.get(timeout=5)
    call.fail()
    failed = state(panel, 'error')
    assert failed['through_seq'] == 1
    first.close()
    second = panel.start()
    record(panel, 2, text='Only the later evidence may be sent.')
    changed(panel, second)
    resumed = model.calls.get(timeout=5)
    assert 'The already delivered proposal.' not in resumed.asked
    assert 'Only the later evidence may be sent.' in resumed.asked
    resumed.answer()
    assert state(panel, 'ready')['through_seq'] == 2


@pytest.mark.parametrize('protocol', [1, 2])
def test_native_permission_reaches_summary_panel_and_person_answer_wakes_same_web_process(panel, monkeypatch, protocol):
    from metaform import settings

    fake = Path(__file__).with_name('fake_agent.py')
    wire = panel.folder / 'wire.jsonl'
    settings.put('dispatch_claude', f'"{sys.executable}" "{fake}"', panel.folder)
    monkeypatch.delenv('ROUNDTABLE_AGENT_CLAUDE', raising=False)
    monkeypatch.setenv('FAKE_ACP_LOG', str(wire))
    monkeypatch.setenv('FAKE_ACP_PERMISSION', '1')
    monkeypatch.setenv('FAKE_ACP_PROTOCOL', str(protocol))
    monkeypatch.delenv('FAKE_ACP_MCP', raising=False)
    record(panel, 1)
    panel.start()
    while True:
        written = panel.writes.get(timeout=5)
        if written.get('permissions') and written['permissions'][0]['state'] == 'waiting':
            request = written['permissions'][0]
            break
    assert request['name'] == 'Live summary'
    assert [one['optionId'] for one in request['options']] == ['allow', 'reject']
    assert panel.module.snapshot(panel.ctx, 'panel')['state'] == 'working'
    assert panel.module.answer(panel.ctx, 'panel', 'a-seat-request', 'allow') is None
    result = panel.module.answer(panel.ctx, 'panel', request['request'], 'allow')
    assert result['state'] == 'answered' and result['chosen'] == 'allow'
    summary = state(panel, 'ready')
    assert summary['text'].startswith('haiku on turn 1:')
    rows = [json.loads(line) for line in wire.read_text().splitlines()]
    assert any(one.get('message', {}).get('result', {}).get('outcome') == {
        'outcome': 'selected', 'optionId': 'allow'} for one in rows)
    assert all(one['state'] != 'waiting' for one in summary['permissions'])
