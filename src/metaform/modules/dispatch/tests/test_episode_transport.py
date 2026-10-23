"""Actual ACP process replacement reuses one context for three explicitly related work records."""
import json
import os

import pytest

from metaform.data import Node, Store
from metaform.module import context
from metaform.modules.dispatch.tests.test_dispatch import Dispatch, eventually, runtime_offers
from metaform.modules.orchestration.state import SERVICE

pytestmark = pytest.mark.kind('simulation')


@pytest.mark.parametrize('worktrees', [False, True])
def test_three_related_cards_reuse_acp_context_and_current_tool_identity(
        run, home, project_folder, tmp_path, monkeypatch, worktrees):
    live = Dispatch(run, home, project_folder, tmp_path, orchestration=True)
    if worktrees:
        from metaform.modules.dispatch.merge import git
        for args in [('init', '-b', 'main'), ('config', 'user.name', 'Episode fixture'),
                     ('config', 'user.email', 'episode@example.invalid')]:
            assert git(project_folder, *args).returncode == 0
        (project_folder / 'seed.txt').write_text('Existing prepared project.\n')
        assert git(project_folder, 'add', 'seed.txt').returncode == 0
        assert git(project_folder, 'commit', '-m', 'Prepared baseline').returncode == 0
    run('set', '--no-dispatch-autostart', '--dispatch-resume-chats', '--no-dispatch-stay-connected',
        '--dispatch-record-on-finish', 'off', '--dispatch-worktrees' if worktrees else '--no-dispatch-worktrees',
        cwd=project_folder)
    runtime_offers(live, 'claude', models=('small',), efforts=('high',))
    source = tmp_path / 'engine.py'
    source.write_text('one\n')
    for name, value in live.env('done', FAKE_ACP_LOAD='1', FAKE_ACP_RICH='1',
                                FAKE_ACP_RICH_PATH=str(source)).items():
        if name.startswith('FAKE_'):
            monkeypatch.setenv(name, value)
    prior = None
    work_ids = []
    try:
        for index in range(3):
            work_id = live.id if index == 0 else live.store.add_work(
                Node('element', 'code.engine'), None, task=f'Write related evidence {index}.').id
            work_ids.append(work_id)
            if index == 0:
                run('map', 'work', 'op=edit', f'id={work_id}', 'agent=claude', 'model=small', 'effort=high',
                    cwd=project_folder)
            ctx = context('orchestration', project_folder, project='proj', nouns={
                'work': work_id, 'role': 'implementer', **({'continue_from': prior} if prior else {})})
            SERVICE.claim(ctx)
            result = SERVICE.drain(ctx, [work_id])
            assert result, SERVICE.pending(ctx, [work_id])

            def completed(work_id=work_id):
                errors = live.logged('done')
                assert not any(value != 0 for value in errors), live.entries()[-5:]
                from metaform.modules.dispatch import sessions
                rows = sessions(live.store, verify=False)
                return live.store.ticket(work_id).work.done and any(
                    row['work_id'] == work_id and row['state'] == 'ended' for row in rows)

            eventually(completed)
            assert SERVICE.assignment(ctx, work_id=work_id)['state'] == 'delivered'
            prior = work_id
        assert len([message for message in live.received('session/new')
                    if message['params'].get('mcpServers')]) == 1
        assert len(live.received('session/load')) == 2
        turns = live.received('session/prompt')
        assert len({turn['params']['sessionId'] for turn in turns}) == 1
        with Store('proj', module='orchestration').tables(write=False) as tx:
            history = tx.rows('binding_history', limit=0).results
        assert {one['assignment_id'] for one in history} == {
            SERVICE.assignment(ctx, work_id=work)['assignment_id'] for work in work_ids}
        assert [entry['work'] for entry in live.entries() if 'done' in entry] == work_ids
        for turn, work_id in zip(turns[1:], work_ids[1:], strict=True):
            text = '\n'.join(block.get('text', '') for block in turn['params']['prompt'])
            assert f'"work_id": "{work_id}"' in text
            assert '"previous_work_id"' in text
        # Keep a standalone recipient trace for the matched baseline/revised measurement command.
        trace = os.environ.get('METAFORM_EPISODE_TRACE')
        if trace and not worktrees:
            from pathlib import Path
            Path(trace).write_text(live.log.read_text(), encoding='utf-8')
    finally:
        run('dispatch', 'stop-all', cwd=project_folder, ok=False)
        live.close()


def test_changed_consumed_prompt_reaches_next_real_turn_as_reference_once(
        run, home, project_folder, tmp_path, monkeypatch):
    from metaform import prompt_files
    from metaform.modules.agents.roles import SERVICE as roles
    from metaform.modules.dispatch.tests.test_orchestration_transport import busy, sent

    live = Dispatch(run, home, project_folder, tmp_path, orchestration=True)
    try:
        worker = busy(live)
        worker.runner, worker.authored_role, worker.spoken = 'prompt-consumer', 'metaform://role/implementer', True
        agent_ctx = context('agents', project_folder, project='proj')
        before = roles.resolve(agent_ctx, 'implementer')
        roles.record(agent_ctx, worker.runner, before['components'], channel='mcp_resource')
        original = next(one for one in before['components'] if one['name'] == 'prompt.orchestration:implementer')
        replacement = str(original['text']) + '\nKeep the exact source exception.'
        prompt_files.save_edit('prompt.orchestration:implementer', replacement, format='text')
        worker.turn('Continue with the next local step.')
        [first] = sent(monkeypatch, worker)
        [notice] = json.loads(first.partition('\n\n')[2])['prompt_changes']
        assert notice['name'] == 'prompt.orchestration:implementer'
        assert notice['read'] == {'tool': 'agents_resolve', 'arguments': {'name': 'implementer'}}
        assert 'Keep the exact source exception.' not in first, 'A revision notice is not an unsolicited body replay.'
        worker.turns = 1
        worker.turn('Continue once more.')
        [second] = sent(monkeypatch, worker)
        assert 'prompt_changes' not in second
    finally:
        live.close()
