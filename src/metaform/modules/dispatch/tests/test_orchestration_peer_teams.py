"""Actual ACP delivery between two independent GC teams, using the classic fake adapter."""
from __future__ import annotations

import json
import os

import pytest

from metaform.data import Node, Store
from metaform.modules.dispatch.tests.test_dispatch import Dispatch, eventually

pytestmark = pytest.mark.kind('simulation')


def test_two_gc_teams_exchange_threaded_notes_but_keep_broadcast_and_interrupt_ownership(
        run, home, project_folder, tmp_path):
    a = Dispatch(run, home, project_folder, tmp_path, orchestration=True)
    b = Dispatch.__new__(Dispatch)
    b.run, b.home, b.folder, b.store, b.process = run, home, project_folder, a.store, None
    b.log, b.node = a.log, Node('element', 'code.ledger')
    a.store.add_element('parts', 'code.ledger')
    b.id = a.store.add_work(b.node, 'unbuilt', task='Review the independent ledger.').id
    from metaform.module import context
    from metaform.modules.agents.roles import SERVICE as roles
    from metaform.modules.orchestration.state import SERVICE
    ctx = context('orchestration', project_folder, project='proj')
    roles.publish(ctx, 'runtime_engineering', 'Concurrent runtimes and event delivery.',
                  'Establish event delivery and runtime ownership through reproducible observations.')
    for work in (a.id, b.id):
        SERVICE.ensure(ctx, work, role='runtime_engineering')
        a.store.move_work(work, 'todo', kept=True)
    gates_a, gates_b = tmp_path / 'a-turns', tmp_path / 'b-turns'
    gates_a.mkdir()
    gates_b.mkdir()
    run('set', '--dispatch-agents', '3', '--dispatch-machine-agents', '3', cwd=project_folder)
    run('set', '--dispatch-record-on-finish', 'off', '--dispatch-autostart', cwd=project_folder)
    proof = {'candidate': os.environ.get('METAFORM_CANDIDATE_LABEL', '8c9bf81eaa6876b5dc34766574ebb1eece2a5851'),
             'configured_capacity': 3}

    def command(*words, env=None, ok=True):
        return run(*words, '--json', cwd=project_folder, env=env, ok=ok)

    def rows(module, table):
        with Store('proj', module=module).tables(write=False) as tx:
            return [dict(one) for one in tx.rows(table, limit=0).results]

    def session(work):
        def live():
            for runner in (a, b):
                if runner.id == work and runner.process is not None and runner.process.poll() is not None:
                    output, error = runner.process.communicate()
                    raise AssertionError(f'Runner ended before its live session: {output!r} {error!r}')
            return next((one for one in rows('dispatch', 'agent_sessions')
                         if one['work_id'] == work and one['state'] == 'running'), None)
        return eventually(live)

    def prompts(sid):
        return [' '.join(block.get('text', '') for block in one['params']['prompt'])
                for one in a.received('session/prompt') if one['params']['sessionId'] == sid]

    def interrupted(sid):
        return [one for one in a.received('session/cancel') if one['params']['sessionId'] == sid]

    try:
        a.start('replace', FAKE_ACP_TURN_GATES=str(gates_a))
        sa = session(a.id)
        eventually(lambda: prompts(sa['session_id']))
        b.start('replace', FAKE_ACP_TURN_GATES=str(gates_b))
        sb = session(b.id)
        eventually(lambda: prompts(sb['session_id']))
        ea = {**a.env('replace', FAKE_ACP_TURN_GATES=str(gates_a)), 'METAFORM_WORK': a.id,
              'METAFORM_SESSION': sa['runner'], 'METAFORM_ROLE': 'worker'}
        eb = {**b.env('replace', FAKE_ACP_TURN_GATES=str(gates_b)), 'METAFORM_WORK': b.id,
              'METAFORM_SESSION': sb['runner'], 'METAFORM_ROLE': 'worker'}
        child = json.loads(command('orchestration', 'delegate', 'role=implementer',
            'task=Retain the engine contribution while its GC coordinates.', 'wait=false',
            'key=cross-team-child', env=ea).stdout)
        sc = session(child['work_id'])
        eventually(lambda: prompts(sc['session_id']))
        assignments = rows('orchestration', 'assignments')
        ga = next(one for one in assignments if one['work_id'] == a.id)
        gb = next(one for one in assignments if one['work_id'] == b.id)
        assert ga['team_id'] != gb['team_id']
        assert ga['authored_role_uri'] == gb['authored_role_uri'] == 'metaform://role/runtime_engineering'
        assert child['team_id'] == ga['team_id']
        discovery = json.loads(command('dispatch', 'peers', env=ea).stdout)['peers']
        assert {one['work_id'] for one in discovery} == {a.id, b.id, child['work_id']}
        proof['capacity'] = json.loads(command('dispatch', 'agents').stdout)['slots']
        assert proof['capacity']['used'] == proof['capacity']['machine_used'] == 3
        note = json.loads(command('dispatch', 'note', f'to={sb["session_id"]}',
            'text=CROSS_TEAM_NOTE: ledger interaction from the engine GC.', env=ea).stdout)
        assert not any('CROSS_TEAM_NOTE:' in text for text in prompts(sb['session_id']))
        assert not a.received('session/cancel') and not a.received('_session/steering')
        (gates_b / '1').touch()
        eventually(lambda: any('CROSS_TEAM_NOTE:' in text for text in prompts(sb['session_id'])))
        reply = json.loads(command('dispatch', 'note', f'reply={note["note"]}',
            'text=CROSS_TEAM_REPLY: ledger result returns to the engine GC.', env=eb).stdout)
        broadcast = json.loads(command('dispatch', 'broadcast',
            'text=OWN_SWARM_ONLY: preserve the engine contribution.', env=ea).stdout)
        assert {one['work_id'] for one in broadcast['recipients']} == {child['work_id']}
        assert broadcast['team_id'] == ga['team_id'] and broadcast['steered'] is False
        denied = command('dispatch', 'interrupt', b.id, 'direction=FORBIDDEN_OTHER_TEAM_DIRECTION',
                         env=ea, ok=False)
        assert denied.returncode != 0 and 'Only the recorded GC' in denied.stdout + denied.stderr
        assert not a.received('session/cancel') and not a.received('_session/steering')
        (gates_a / '1').touch()
        eventually(lambda: any('CROSS_TEAM_REPLY:' in text for text in prompts(sa['session_id'])))
        eventually(lambda: any('OWN_SWARM_ONLY:' in text for text in prompts(sc['session_id'])))
        assert not any('OWN_SWARM_ONLY:' in text or 'FORBIDDEN_OTHER_TEAM_DIRECTION' in text
                       for text in prompts(sb['session_id']))
        own_interrupt = json.loads(command('dispatch', 'interrupt', child['work_id'],
            'direction=OWN_CHILD_NEW_DIRECTION: keep retained work and revise the interaction.', env=ea).stdout)
        eventually(lambda: interrupted(sc['session_id']))
        eventually(lambda: any('OWN_CHILD_NEW_DIRECTION:' in text for text in prompts(sc['session_id'])))
        assert not interrupted(sb['session_id']) and not interrupted(sa['session_id'])
        assert not a.received('_session/steering')
        assert b.process.poll() is None and session(b.id)['session_id'] == sb['session_id']
        peer_rows = [json.loads(one['text']) for one in rows('dispatch', 'session_lines') if one['kind'] == 'peer']
        sent_rows = [one for one in peer_rows if one['id'] == note['note']]
        reply_rows = [one for one in peer_rows if one.get('reply_to') == note['note']]
        assert sent_rows and reply_rows
        assert all(one['from']['assignment_id'] == ga['assignment_id'] for one in sent_rows)
        assert all(one['from']['assignment_id'] == gb['assignment_id'] for one in reply_rows)
        proof.update(assignments=rows('orchestration', 'assignments'), discovery=discovery,
                     note=note, reply=reply, broadcast=broadcast, peer_rows=peer_rows,
                     other_team_interrupt_denied={'code': denied.returncode,
                                                  'message': denied.stdout + denied.stderr},
                     owned_child_interrupt=own_interrupt, sessions={'gc_a': sa, 'gc_b': sb, 'child_a': sc},
                     recipient_prompts={sid: prompts(sid) for sid in
                                        (sa['session_id'], sb['session_id'], sc['session_id'])},
                     cancellation=a.received('session/cancel'), steering=a.received('_session/steering'))
        (tmp_path / 'cross-team-evidence.json').write_text(json.dumps(proof, indent=2), encoding='utf-8')
    finally:
        run('dispatch', 'stop-all', cwd=project_folder, ok=False)
        a.close()
        b.close()
