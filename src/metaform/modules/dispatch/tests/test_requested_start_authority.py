"""User-request provenance survives permissive policy and deferred runtime selection."""
import sys
from dataclasses import replace

import pytest

from metaform.module import context
from metaform.modules.dispatch.tests.test_dispatch import Dispatch


@pytest.mark.req('BASE-052')
@pytest.mark.kind('simulation')
@pytest.mark.parametrize('existing', [False, True])
@pytest.mark.parametrize('authority', ['message', 'covered', 'autonomous', 'stopped'])
def test_requested_start_retains_authority_through_runtime_and_continuation(
        run, home, project_folder, tmp_path, monkeypatch, existing, authority):
    from metaform import jev
    from metaform.module import provided
    from metaform.modules.agents.roles import SERVICE as roles
    from metaform.modules.dispatch.orchestration import service
    from metaform.modules.orchestration.state import own

    made = Dispatch(run, home, project_folder, tmp_path, orchestration=True)
    run('set', '--no-dispatch-autostart', '--no-agents-ask-first', cwd=project_folder)
    ctx = context('dispatch', project_folder, project='proj', surface='mcp',
                  nouns={'id': made.id, 'agent': 'claude'})
    SERVICE = service(ctx)
    Transport = type(provided(ctx.folder, 'orchestration.transport')[0][1])
    word_provider = provided(ctx.folder, 'person.word')[0][1]
    package = sys.modules[word_provider.__module__]
    roles.publish(ctx, 'notes_engineering', 'Write requested project notes.', 'Write and verify project notes.')
    monkeypatch.setattr(jev, 'config', lambda *args: None)
    monkeypatch.setattr(Transport, 'runtime_catalog', lambda *args: {
        'claude': {'models': {'full': 'Full capability model.'}, 'efforts': ['medium', 'high']}})
    monkeypatch.setattr(package, 'mcp_server', lambda *args: None)
    launched = []
    monkeypatch.setattr(package, 'start_runner',
                        lambda ctx, store, work, *args, **kwargs: launched.append(work) or {'pid': 1})
    monkeypatch.setattr(package, 'launches', list)
    # Real assignment and runtime commission, including the already-stalled child from #148.
    if existing:
        SERVICE.ensure(ctx, made.id, role='notes_engineering')
    else:
        # Route selects existing expertise, without commissioning runtime before dispatch_start.
        monkeypatch.setattr(SERVICE, 'route', lambda *args: {'role': 'notes_engineering'})
    unrelated = made.store.add_work(made.node, None, task='Unrelated notes.').id
    outsider = SERVICE.ensure(ctx, unrelated, role='facilitator')
    monkeypatch.setenv('METAFORM_ROLE', 'system')
    monkeypatch.setenv('METAFORM_SESSION', 'system-runner')
    monkeypatch.setenv('METAFORM_WORK', 'system-work')
    # Only the runner reply is simulated. Canonical provider discovery, word lookup,
    # start classification, persistence, propagation and admission remain real.
    monkeypatch.setitem(word_provider.__globals__, 'own_session', lambda *args: {'runner': 'system-runner'})
    word = {'id': 'user-message', 'text': 'Write the project notes.', 'at': '2026-10-21T12:00:00Z'}
    if authority == 'covered':
        word['covered'] = True
    reply = {'word': word} if authority in ('message', 'covered') else {'stopped': authority == 'stopped'}
    monkeypatch.setitem(word_provider.__globals__, 'tell', lambda *args, **kwargs: reply)
    try:
        result = package.start(ctx)
        assert result['state'] == 'queued'
        parent = SERVICE.assignment(ctx, work_id=made.id)
        with own(ctx).tables(write=False) as tx:
            request, = tx.rows('role_requests', {'caller_assignment_id': parent['assignment_id']}, limit=0).results
        child = SERVICE.assignment(ctx, assignment_id=request['creator_assignment_id'])
        authorized = authority in ('message', 'covered')
        assert parent['persons_start'] is authorized
        assert child['persons_start'] is authorized
        assert not SERVICE.assignment(ctx, work_id=unrelated)['persons_start']
        with pytest.raises(package.Refused, match='Full Auto is off'):
            Transport().launch(ctx, outsider, 'unrelated')
        if not authorized:
            with pytest.raises(package.Refused, match='Full Auto is off'):
                Transport().launch(ctx, child, 'runtime')
            assert launched == []
            return
        assert Transport().launch(ctx, child, 'runtime')['pid'] == 1
        assert launched == [child['work_id']]
        # Later runtime publication resumes the original assignment without another user message.
        monkeypatch.setitem(word_provider.__globals__, 'tell', lambda *args, **kwargs: {})
        creator_ctx = replace(ctx, surface='cli', nouns={'assignment': child['assignment_id']})
        for key in ('METAFORM_ROLE', 'METAFORM_SESSION', 'METAFORM_WORK'):
            monkeypatch.delenv(key)
        choice = {'agent': 'claude', 'model': 'full', 'effort': 'medium', 'confidence': 1.0,
                  'task_type': 'coding', 'reason': 'The requested file change is specified.'}
        assert SERVICE.runtime(creator_ctx, made.id, choice)['state'] == 'selected'
        SERVICE.publish_role(replace(creator_ctx, nouns={**creator_ctx.nouns,
            'request': request['request_id'], 'role': 'notes_engineering'}))
        parent = SERVICE.assignment(ctx, work_id=made.id)
        assert parent['persons_start'] and parent['state'] == 'queued'
        assert Transport().launch(ctx, parent, 'continuation')['pid'] == 1
        assert launched == [child['work_id'], made.id]
        # A recorded stop still blocks subsequent delivery, even with retained authority.
        SERVICE.stopped(ctx, work_id=made.id, by='user')
        stopped = SERVICE.assignment(ctx, work_id=made.id)
        assert Transport().launch(ctx, stopped, 'stopped')['state'] == 'stopped'
        assert launched == [child['work_id'], made.id]
        assert ctx.setting('dispatch_autostart') is False
    finally:
        made.close()
