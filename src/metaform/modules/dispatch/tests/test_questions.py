"""VIEW-042 keeps work moving after questions, with explicit chat and automatic starts."""
import asyncio
import json

import pytest

from metaform.modules.dispatch.tests.test_dispatch import dispatch as dispatch  # noqa: PLC0414 fixture re-export
from metaform.modules.dispatch.tests.test_dispatch import eventually, glyphed

pytestmark = [pytest.mark.kind('simulation'), pytest.mark.req('VIEW-042')]


def test_a_blocked_question_ends_the_session_preserves_progress_and_answer_only_unpauses(dispatch, run):
    dispatch.store.plan_work(dispatch.work_id, 3)
    dispatch.store.step_work(dispatch.work_id, 'Read the dependencies.')
    dispatch.start('question', FAKE_ACP_ASK_AT='code.engine')
    [question] = eventually(dispatch.questions)
    assert dispatch.process.wait(15) == 0, dispatch.process.stderr.read().decode()
    record = dispatch.ticket()
    assert record.taken is None and record.held and record.steps == 3 and record.steps_done == 1
    assert dispatch.session().extra['state'] == 'ended'
    run('map', 'reply', question.message_id, 'answer=Keep it', cwd=dispatch.folder)
    from metaform.module import context
    from metaform.modules.dispatch import autostart
    autostart(context('dispatch', dispatch.folder, project='proj'))
    assert not dispatch.ticket().held and not dispatch.ticket().taken
    assert len(dispatch.items('session')) == 1
    assert dispatch.questions(False)[0].answer == 'Keep it'


def test_automatic_dispatch_uses_board_order_free_glyphs_and_five_undistributed_slots(dispatch, run, monkeypatch):
    from metaform.module import context
    from metaform.modules import dispatch as module
    ids = glyphed(dispatch, run, *[(str(n), None, False) for n in range(6)])
    dispatch.store.move_work(ids[-1], 'todo', 0)
    run('set', '--dispatch-autostart', cwd=dispatch.folder)
    launched = []
    monkeypatch.setattr(module, 'start', lambda ctx: launched.append(ctx.nouns['id']) or {'work_id': ctx.nouns['id']})
    ctx = context('dispatch', dispatch.folder, project='proj')
    module.autostart(ctx)
    assert launched == [ids[-1], dispatch.work_id, *ids[:3]]
    for work_id in [dispatch.work_id, *ids]:
        run('map', 'work', 'op=edit', f'id={work_id}', 'glyph=kite', cwd=dispatch.folder)
    run('map', 'work', 'op=edit', f'id={ids[1]}', 'glyph=moth', cwd=dispatch.folder)
    launched.clear()
    module.autostart(ctx)
    assert launched == [ids[-1], ids[1]], 'one runner per distributed glyph'


def test_automatic_dispatch_counts_starting_reservations_before_sessions_register(dispatch, run, monkeypatch):
    from metaform.module import context
    from metaform.modules import dispatch as module
    ids = glyphed(dispatch, run, *[(str(n), None, False) for n in range(5)])
    run('set', '--dispatch-autostart', '--dispatch-agents', '2', cwd=dispatch.folder)
    launched = []
    def reserve(ctx):
        work_id = ctx.nouns['id']
        dispatch.store.take_work(work_id, by='dispatch starting fake')
        launched.append(work_id)
        return {'work_id': work_id}
    monkeypatch.setattr(module, 'start', reserve)
    ctx = context('dispatch', dispatch.folder, project='proj')
    module.autostart(ctx)
    module.autostart(ctx)
    assert launched == [dispatch.work_id, ids[0]], 'unregistered runners still occupy the two slots'
    for work_id in [dispatch.work_id, *ids]:
        run('map', 'work', 'op=edit', f'id={work_id}', 'glyph=kite', cwd=dispatch.folder)
    run('map', 'work', 'op=edit', f'id={ids[-1]}', 'glyph=moth', cwd=dispatch.folder)
    module.autostart(ctx)
    assert launched == [dispatch.work_id, ids[0]], 'the two reservations also occupy distributed capacity'


def test_chat_reuses_the_asking_session_even_while_it_keeps_working(dispatch, run):
    dispatch.start('question', FAKE_ACP_ASK_AT='code.engine', FAKE_ACP_QUESTION_HOLD='1')
    [question] = eventually(dispatch.questions)
    eventually(lambda: dispatch.logged('asked'))
    result = json.loads(run('dispatch', 'chat', question.message_id, '--json', cwd=dispatch.folder).stdout)
    assert result['state'] == 'running' and result['session_id'] == 'fake-session-1'
    assert result['work_id'] == dispatch.work_id and len(dispatch.items('session')) == 1
    dispatch.stop()


def test_chat_after_blocked_exit_starts_new_glyph_and_answer_reaches_that_session(dispatch, run, monkeypatch,
                                                                                dispatch_runners):
    dispatch.start('question', FAKE_ACP_ASK_AT='code.engine')
    [question] = eventually(dispatch.questions)
    assert dispatch.process.wait(15) == 0
    run('map', 'work', 'op=edit', f'id={dispatch.work_id}', 'glyph=kite', cwd=dispatch.folder)
    for name, value in dispatch.env('hold').items():
        monkeypatch.setenv(name, value)
    result = json.loads(run('dispatch', 'chat', question.message_id, '--json', cwd=dispatch.folder).stdout)
    dispatch_runners.append((result, dispatch.folder, dispatch.log))
    text = eventually(lambda: dispatch.received('session/prompt')[1:])[0]['params']['prompt'][0]['text']
    assert question.message_id in text and 'Is the store kept?' in text
    record = json.loads(run('map', 'work', f'id={dispatch.work_id}', '--json', cwd=dispatch.folder).stdout)
    assert record['map']['glyph'] and record['map']['glyph'] != 'kite'
    run('map', 'reply', question.message_id, 'answer=Keep it', cwd=dispatch.folder)
    answered = eventually(lambda: dispatch.received('session/prompt')[2:])[0]
    assert answered['params']['sessionId'] == 'fake-session-2'
    assert 'Keep it' in answered['params']['prompt'][0]['text']
    dispatch.stop()


def test_start_reserves_ticket_before_runner_launch_and_restores_claim_on_launch_failure(dispatch, run, monkeypatch):
    from metaform.module import Stop, context
    from metaform.modules import dispatch as module
    ctx = context('dispatch', dispatch.folder, project='proj', nouns={'id': dispatch.work_id, 'agent': 'claude'})
    run('map', 'work', 'op=edit', f'id={dispatch.work_id}', 'glyph=kite', cwd=dispatch.folder)
    [other] = glyphed(dispatch, run, ('Other ticket', 'kite', False))
    def launch(*args, **kwargs):
        assert dispatch.ticket().taken
        with pytest.raises(Stop, match='taken'):
            module.start(ctx)
        with pytest.raises(Stop, match='kite'):
            module.start(context('dispatch', dispatch.folder, project='proj', nouns={'id': other, 'agent': 'claude'}))
        raise OSError('launch failed')
    monkeypatch.setattr(module.subprocess, 'Popen', launch)
    with pytest.raises(OSError, match='launch failed'):
        module.start(ctx)
    assert not dispatch.ticket().taken


def test_direct_run_and_glyph_transition_reserve_before_starting_the_adapter(dispatch, run, monkeypatch):
    from metaform.module import Stop, context
    from metaform.modules import dispatch as module
    from metaform.modules.dispatch import runner
    run('map', 'work', 'op=edit', f'id={dispatch.work_id}', 'glyph=kite', cwd=dispatch.folder)
    [other] = glyphed(dispatch, run, ('Next ticket', 'kite', False))
    began = []
    async def session_run(session):
        work_id = session.work_id
        assert dispatch.store.ticket(work_id).work.taken_by.startswith('dispatch starting ')
        competing = other if work_id == dispatch.work_id else work_id
        with pytest.raises(Stop, match='kite|taken'):
            module.start(context('dispatch', dispatch.folder, project='proj',
                                 nouns={'id': competing, 'agent': 'claude'}))
        began.append(work_id)
        dispatch.store.finish_work(work_id, 'Finished')
        return {'work_id': work_id}
    monkeypatch.setattr(runner.Session, 'run', session_run)
    ctx = context('dispatch', dispatch.folder, project='proj', nouns={'id': dispatch.work_id, 'agent': 'claude'})
    result = asyncio.run(runner.dispatch(ctx))
    assert result['worked'] == began == [dispatch.work_id, other]
