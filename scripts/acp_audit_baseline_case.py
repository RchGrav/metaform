"""Legacy half of the paired ACP episode measurement.

Copy this file into the baseline repository tests folder, then run pytest there
with METAFORM_EPISODE_TRACE pointing at the desired fake-adapter JSONL trace.
The revised half is dispatch/tests/test_episode_transport.py.
"""
import os

import pytest

from metaform.data import Node
from metaform.module import context
from metaform.modules.dispatch.tests.test_dispatch import Dispatch, eventually, runtime_offers
from metaform.modules.orchestration.state import SERVICE

pytestmark = pytest.mark.kind('simulation')


def test_three_related_cards_reuse_acp_context_and_current_tool_identity(run, home, project_folder, tmp_path, monkeypatch):
    live = Dispatch(run, home, project_folder, tmp_path, orchestration=True)
    run('set', '--no-dispatch-autostart', '--dispatch-resume-chats', '--no-dispatch-stay-connected',
        '--dispatch-record-on-finish', 'off', cwd=project_folder)
    runtime_offers(live, 'claude', models=('small',), efforts=('high',))
    rich_path = tmp_path / 'engine.py'
    rich_path.write_text('one\n')
    for name, value in live.env('done', FAKE_ACP_LOAD='1', FAKE_ACP_RICH='1',
                                FAKE_ACP_RICH_PATH=str(rich_path)).items():
        if name.startswith('FAKE_'):
            monkeypatch.setenv(name, value)
    work_ids = []
    try:
        for index in range(3):
            work_id = live.id if index == 0 else live.store.add_work(
                Node('element', 'code.engine'), None, task=f'Write related evidence {index}.').id
            work_ids.append(work_id)
            run('map', 'work', 'op=edit', f'id={work_id}', 'agent=claude', 'model=small', 'effort=high',
                cwd=project_folder)
            ctx = context('orchestration', project_folder, project='proj', nouns={
                'work': work_id, 'role': 'implementer'})
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
        assert len(live.received('session/new')) == 3
        assert len(live.received('session/load')) == 0
        assert [entry['work'] for entry in live.entries() if 'done' in entry] == work_ids
        # Keep a standalone recipient trace for the matched baseline/revised measurement command.
        trace = os.environ.get('METAFORM_EPISODE_TRACE')
        if trace:
            from pathlib import Path
            Path(trace).write_text(live.log.read_text(), encoding='utf-8')
    finally:
        run('dispatch', 'stop-all', cwd=project_folder, ok=False)
        live.close()
