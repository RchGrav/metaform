"""Full Auto admits generated assessments when their owner's board has free capacity."""
import importlib
import json
import os
import threading

import pytest

from metaform.data import Store
from metaform.module import context, provided
from metaform.modules.dispatch.tests.test_dispatch import dispatch  # noqa: F401 -- fixture

pytestmark = [pytest.mark.kind('simulation'), pytest.mark.req('VIEW-042'), pytest.mark.req('BASE-052')]


@pytest.mark.parametrize('legacy', [False, True], ids=['new-assessment', 'legacy-assessment'])
@pytest.mark.parametrize('hold_kind', ['hold', 'backlog'])
def test_capacity_event_automatically_admits_assessment_on_owner_board(
        dispatch, run, monkeypatch, legacy, hold_kind):  # noqa: F811
    run('enable', 'orchestration')
    run('map', 'boards', 'op=add', 'name=repairs', cwd=dispatch.folder)
    run('set', '--board=repairs', '--dispatch-autostart', '--dispatch-agents=1', '--dispatch-machine-agents=1',
        '--no-dispatch-stay-connected', cwd=dispatch.folder)
    run('map', 'work', 'op=edit', f'id={dispatch.id}', 'board=repairs', cwd=dispatch.folder)
    SERVICE = provided(dispatch.folder, 'orchestration')[0][1]
    transport = provided(dispatch.folder, 'orchestration.transport')[0][1]
    implementation = importlib.import_module(type(transport).__module__.rsplit('.', 1)[0])
    from metaform.modules.web import server as web

    # Runtime choice is already established. Keep actual board, stop, capacity and ownership admission checks.
    monkeypatch.setattr(SERVICE, 'prepare_runtime', lambda *args, **kwargs: True)
    ctx = context('dispatch', dispatch.folder, project='proj')
    owner = SERVICE.ensure(ctx, dispatch.id, role='verifier', session_id='owner-session')
    unrelated = dispatch.store.add_work(dispatch.node, None, task='Work set aside on the first board').id
    child = SERVICE.assessment(ctx, owner, {}, 'assessment')
    held = SERVICE.assessment(ctx, owner, {}, 'held-assessment')
    if hold_kind == 'hold':
        dispatch.store.set_work_hold(held['work_id'], hold=True, hold_reason='Wait for the person')
    else:
        dispatch.store.move_work(held['work_id'], 'backlog', hold_reason='Wait for the person')
    if legacy:
        # Missing settings prove no canonical placement. Historical NULL rows may record explicit first-board edits.
        with Store('proj', module='map').tables() as tx:
            tx.delete('ticket_settings', {'work_id': child['work_id']})
            tx.update('ticket_settings', {'work_id': held['work_id']}, {'board': None})
        assert implementation.set_aside(ctx, child['work_id']) is not None
    else:
        assert implementation.set_aside(ctx, child['work_id']) is None
    with Store('proj', module='map').tables(write=False) as tx:
        held_settings = dict(tx.get('ticket_settings', {'work_id': held['work_id']}))

    running = [{'pid': os.getpid(), 'project': 'proj', 'work_id': dispatch.id, 'kind': 'worker'}]
    launches = []
    started = threading.Event()
    passed = threading.Event()
    failures = []
    results = []
    monkeypatch.setattr(implementation, 'launches', lambda: list(running))

    def start(launch_ctx, store, work_id, agent, words, name, **kwargs):
        assert kwargs['auto'] is True
        assert work_id == child['work_id']
        assert implementation.set_aside(launch_ctx, work_id) is None
        assert store.ticket(work_id).work.taken_by == kwargs['reservation']
        launches.append(work_id)
        running.append({'pid': os.getpid(), 'project': 'proj', 'work_id': work_id, 'kind': 'worker'})
        started.set()
        return {'pid': os.getpid()}

    monkeypatch.setattr(implementation, 'start_runner', start)
    # Keep the real change handler, coalescing worker, autostart, transport and admission gate.
    # Bypass command discovery reloads while preserving actual automatic dispatch.
    monkeypatch.setattr(web.chassis, 'refresh_modules', lambda: None)
    with web.Server('127.0.0.1', 0, 'fixture') as server:
        monkeypatch.setattr(server, 'watch_backgrounds', lambda *args, **kwargs: None)
        monkeypatch.setattr(server, 'watch_runners', lambda *args, **kwargs: None)

        def observe(*args, **kwargs):
            try:
                result = implementation.autostart(context('dispatch', dispatch.folder, project='proj', surface='web'))
                results.append(result)
                return result
            except Exception as error:  # Surface failures from the dispatch worker.
                failures.append(error)
                raise
            finally:
                passed.set()

        monkeypatch.setattr(web, 'module_verb', observe)
        payload = {'project': 'proj', 'base_id': None, 'tables': ['dispatch.agent_sessions'],
                   'work_ids': [dispatch.id], 'session_ids': ['owner-session']}
        try:
            server.changed(payload)
            assert passed.wait(10), 'capacity event did not reach automatic dispatch'
            assert failures == []
            assert launches == [], 'occupied worker capacity must block the assessment'
            assert implementation.set_aside(ctx, child['work_id']) is None, 'pending launch repairs legacy placement'
            passed.clear()
            running.clear()  # The owner has suspended and released its worker slot.
            server.changed(payload)
            assert passed.wait(10)
            assert started.is_set(), json.dumps(results, indent=2)
            assert failures == []
            assert launches == [child['work_id']]
            with Store('proj', module='map').tables(write=False) as tx:
                assert tx.get('ticket_settings', {'work_id': held['work_id']}) == held_settings
                assert bool(held_settings['hold']) == (hold_kind == 'hold')
            if legacy:
                assert held_settings['board'] is None
                assert implementation.set_aside(ctx, held['work_id']) is not None
            assert dispatch.store.ticket(held['work_id']).work.held == (hold_kind == 'backlog')
            assert dispatch.store.ticket(held['work_id']).work.taken is None
            assert implementation.set_aside(ctx, unrelated) is not None
            assert dispatch.store.ticket(unrelated).work.taken is None
            assert dispatch.store.ticket(dispatch.id).work.done is None
        finally:
            for _, timer in server.retry_timers.values():
                timer.cancel()
            server.close_backgrounds()
            server.vouch.close()
