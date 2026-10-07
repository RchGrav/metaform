"""VIEW-042 keeps work moving after questions, with explicit chat and automatic starts."""
import asyncio
import json
from pathlib import Path

import pytest

from metaform.modules.dispatch.tests.test_dispatch import dispatch as dispatch  # noqa: PLC0414 fixture re-export
from metaform.modules.dispatch.tests.test_dispatch import eventually, glyphed

pytestmark = [pytest.mark.kind('simulation'), pytest.mark.req('VIEW-042')]


TRIAL_PROMPTS = Path(__file__).with_name('trial_prompts.xml')  # test-only prompts Rich has not written yet

def test_an_unfinished_ticket_with_a_question_returns_to_todo_and_keeps_progress(dispatch, run):
    dispatch.store.plan_work(dispatch.id, 3)
    dispatch.store.step_work(dispatch.id, 'Read the dependencies.')
    dispatch.start('question', FAKE_ACP_ASK_AT='code.engine')
    [question] = eventually(dispatch.questions)
    assert dispatch.process.wait(15) == 0, dispatch.process.stderr.read().decode()
    record = dispatch.ticket()
    assert record.taken is None and not record.held and record.steps == 3 and record.steps_done == 1
    assert dispatch.session().extra['state'] == 'ended'
    run('map', 'reply', question.id, 'answer=Keep it', cwd=dispatch.folder)
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
    assert launched == [ids[-1], dispatch.id, *ids[:3]]
    for work_id in [dispatch.id, *ids]:
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
    assert launched == [dispatch.id, ids[0]], 'unregistered runners still occupy the two slots'
    for work_id in [dispatch.id, *ids]:
        run('map', 'work', 'op=edit', f'id={work_id}', 'glyph=kite', cwd=dispatch.folder)
    run('map', 'work', 'op=edit', f'id={ids[-1]}', 'glyph=moth', cwd=dispatch.folder)
    module.autostart(ctx)
    assert launched == [dispatch.id, ids[0]], 'the two reservations also occupy distributed capacity'


def test_submitting_a_question_keeps_the_turn_working_and_its_answer_reaches_the_asker(dispatch, run, tmp_path):
    gate = tmp_path / 'question-turn'
    dispatch.start('question', FAKE_ACP_ASK_AT='code.engine', FAKE_ACP_QUESTION_GATE=str(gate))
    [question] = eventually(dispatch.questions)
    eventually(lambda: [one for one in dispatch.items('note') if one.extra['update'] == 'tool_call' and
                       'Ask a question' in one.value])
    assert dispatch.process.poll() is None and dispatch.ticket().taken
    run('map', 'reply', question.id, 'answer=Keep it', cwd=dispatch.folder)
    answered = eventually(lambda: [one for one in dispatch.items('note') if one.extra['update'] == 'answered'])
    assert 'Keep it' in answered[0].value
    assert dispatch.process.poll() is None, 'an answer queues while useful work continues'
    gate.touch()
    sent = eventually(lambda: dispatch.received('session/prompt')[1:])[0]
    assert question.id in sent['params']['prompt'][0]['text']
    assert 'Keep it' in sent['params']['prompt'][0]['text']
    assert dispatch.process.wait(15) == 0


def test_open_questions_do_not_skip_board_order_in_next_ticket_or_autostart(dispatch, run, monkeypatch):
    from metaform.module import context
    from metaform.modules import dispatch as module
    run('map', 'work', 'op=edit', f'id={dispatch.id}', 'glyph=kite', cwd=dispatch.folder)
    [later] = glyphed(dispatch, run, ('Later', 'kite', False))
    dispatch.store.ask(dispatch.node, 'Which format?', suggestions=['Text'], work=dispatch.id)
    ctx = context('dispatch', dispatch.folder, project='proj')
    assert module.next_ticket(ctx, dispatch.store, 'kite').id == dispatch.id
    assert module.next_ticket(ctx, dispatch.store, 'kite', exclude=(dispatch.id,)).id == later
    run('set', '--dispatch-autostart', cwd=dispatch.folder)
    started = []
    monkeypatch.setattr(module, 'start', lambda ctx: started.append(ctx.nouns['id']) or {'work_id': ctx.nouns['id']})
    module.autostart(ctx)
    assert started == [dispatch.id], 'a question does not move the first ticket behind later work'


def test_answer_does_not_move_a_ticket_the_person_put_in_backlog(dispatch, run):
    from metaform.module import context
    from metaform.modules.dispatch import autostart
    question = dispatch.store.ask(dispatch.node, 'Which format?', suggestions=['Text'], work=dispatch.id)
    dispatch.store.move_work(dispatch.id, 'backlog', 7)
    position = dispatch.ticket().position
    run('map', 'reply', question.id, 'answer=Text', cwd=dispatch.folder)
    autostart(context('dispatch', dispatch.folder, project='proj'))
    assert dispatch.ticket().held and dispatch.ticket().position == position


def test_an_answer_reaches_the_current_ticket_holder_even_when_another_agent_asked(dispatch, run, tmp_path):
    question = dispatch.store.ask(dispatch.node, 'Which format?', suggestions=['Text'], work=dispatch.id,
                                 by='previous agent')
    gates = tmp_path / 'holder-turns'
    gates.mkdir()
    dispatch.start('replace', FAKE_ACP_TURN_GATES=str(gates))
    eventually(lambda: dispatch.received('session/prompt'))
    run('map', 'reply', question.id, 'answer=Text', cwd=dispatch.folder)
    answered = eventually(lambda: [one for one in dispatch.items('note') if one.extra['update'] == 'answered'])
    assert question.id in answered[0].value and 'Text' in answered[0].value
    (gates / '1').touch()
    sent = eventually(lambda: dispatch.received('session/prompt')[1:])[0]
    assert question.id in sent['params']['prompt'][0]['text']
    assert 'Text' in sent['params']['prompt'][0]['text']
    (gates / '2').touch()
    assert dispatch.process.wait(15) == 0


def test_questions_added_and_reopened_during_work_reach_the_current_holder(dispatch, run, tmp_path):
    gates = tmp_path / 'holder-turns'
    gates.mkdir()
    dispatch.start('replace', FAKE_ACP_TURN_GATES=str(gates))
    eventually(lambda: dispatch.received('session/prompt'))
    question = json.loads(run('map', 'ask', 'node=code.engine', 'question=Which format?',
                              'suggestions=["Text","XML"]', 'by=previous agent', 'specs=00-index.md',
                              'not_option=One format is read.',
                              'rich_said=None; the decision and its reason are described in the question.',
                              f'work={dispatch.id}', '--json', cwd=dispatch.folder).stdout)
    message_id = question['id']
    run('map', 'reply', message_id, 'answer=Text', cwd=dispatch.folder)
    eventually(lambda: [one for one in dispatch.items('note') if one.extra['update'] == 'answered'])
    (gates / '1').touch()
    sent = eventually(lambda: dispatch.received('session/prompt')[1:])[0]
    assert message_id in sent['params']['prompt'][0]['text'] and 'Text' in sent['params']['prompt'][0]['text']
    run('map', 'reopen', message_id, cwd=dispatch.folder)
    run('map', 'reply', message_id, 'answer=XML', cwd=dispatch.folder)
    eventually(lambda: [one for one in dispatch.items('note') if one.extra['update'] == 'answered' and
                       'XML' in one.value])
    (gates / '2').touch()
    sent = eventually(lambda: dispatch.received('session/prompt')[2:])[0]
    assert message_id in sent['params']['prompt'][0]['text'] and 'XML' in sent['params']['prompt'][0]['text']
    (gates / '3').touch()
    assert dispatch.process.wait(15) == 0


def test_chat_after_unfinished_exit_starts_new_glyph_and_answer_reaches_that_session(dispatch, run, monkeypatch,
                                                                                dispatch_runners, tmp_path):
    dispatch.start('question', FAKE_ACP_ASK_AT='code.engine')
    [question] = eventually(dispatch.questions)
    assert dispatch.process.wait(15) == 0
    run('map', 'work', 'op=edit', f'id={dispatch.id}', 'glyph=kite', cwd=dispatch.folder)
    gates = tmp_path / 'turns'
    gates.mkdir()
    for name, value in dispatch.env('replace', FAKE_ACP_TURN_GATES=str(gates)).items():
        monkeypatch.setenv(name, value)
    result = json.loads(run('dispatch', 'chat', question.id, '--json', cwd=dispatch.folder).stdout)
    dispatch_runners.append((result, dispatch.folder, dispatch.log))
    text = eventually(lambda: dispatch.received('session/prompt')[1:])[0]['params']['prompt'][0]['text']
    assert question.id in text and 'Is the store kept?' in text
    record = json.loads(run('map', 'work', f'id={dispatch.id}', '--json', cwd=dispatch.folder).stdout)
    assert record['map']['glyph'] and record['map']['glyph'] != 'kite'
    run('map', 'reply', question.id, 'answer=Keep it', cwd=dispatch.folder)
    eventually(lambda: [one for one in dispatch.items('note') if one.extra['update'] == 'answered'])
    run('dispatch', 'message', dispatch.id, 'Check the store', cwd=dispatch.folder)
    assert len(dispatch.received('session/prompt')) == 2, 'the answer waits for the chat turn to end'
    (gates / '1').touch()
    answered = eventually(lambda: dispatch.received('session/prompt')[2:])[0]
    assert answered['params']['sessionId'] == 'fake-session-2'
    assert 'Keep it' in answered['params']['prompt'][0]['text']
    (gates / '2').touch()
    following = eventually(lambda: dispatch.received('session/prompt')[3:])[0]
    assert following['params']['prompt'] == [{'type': 'text', 'text': 'Check the store'}]
    assert not dispatch.logged('replaced')
    dispatch.stop()


def test_chat_on_a_question_naming_no_ticket_opens_one_at_its_node_and_a_second_chat_reaches_it(
        dispatch, run, monkeypatch, dispatch_runners):
    dispatch.store.add_work(dispatch.node, 'flawed', task='Another ticket')
    question = dispatch.store.ask(dispatch.node, 'Which format?', suggestions=['Text'])
    for name, value in dispatch.env('hold').items():
        monkeypatch.setenv(name, value)
    result = json.loads(run('dispatch', 'chat', question.id, '--json', cwd=dispatch.folder).stdout)
    dispatch_runners.append((result, dispatch.folder, dispatch.log))
    tickets = dispatch.store.work(dispatch.node, open=True, limit=0).results
    [opened] = [record for record in tickets if record.id == result['work_id']]
    assert len(tickets) == 3 and opened.task == 'Which format?'
    eventually(lambda: [row for row in dispatch.items('session')
                        if row.extra['work_id'] == opened.id and row.extra['state'] == 'running'])
    again = json.loads(run('dispatch', 'chat', question.id, '--json', cwd=dispatch.folder).stdout)
    assert again['work_id'] == opened.id
    assert len(dispatch.store.work(dispatch.node, open=True, limit=0).results) == 3


def test_chat_on_a_done_tickets_question_starts_an_agent_to_talk_it_through(dispatch, run, monkeypatch,
                                                                            dispatch_runners):
    """A done ticket's question is still worth talking about: Chat starts an agent told the question and that the
    work is done; its session counts as running, and the ticket stays done."""
    dispatch.start('question', FAKE_ACP_ASK_AT='code.engine')
    [question] = eventually(dispatch.questions)
    assert dispatch.process.wait(15) == 0
    dispatch.store.finish_work(dispatch.id, 'Finished')
    monkeypatch.setenv('METAFORM_PROMPTS', str(TRIAL_PROMPTS))
    for name, value in dispatch.env('hold').items():
        monkeypatch.setenv(name, value)
    result = json.loads(run('dispatch', 'chat', question.id, '--json', cwd=dispatch.folder).stdout)
    dispatch_runners.append((result, dispatch.folder, dispatch.log))
    assert result['work_id'] == dispatch.id
    text = eventually(lambda: dispatch.received('session/prompt')[1:])[0]['params']['prompt'][0]['text']
    assert question.id in text and 'Is the store kept?' in text and 'Test talk prompt.' in text
    eventually(lambda: [row for row in json.loads(run('dispatch', 'sessions', f'id={dispatch.id}', '--json',
                                                      cwd=dispatch.folder).stdout)['sessions']
                        if row['state'] == 'running'])
    assert dispatch.ticket().done
    dispatch.stop()


def test_talk_on_a_done_ticket_and_on_a_node_starts_a_conversation_and_takes_nothing(dispatch, run, monkeypatch,
                                                                                  dispatch_runners):
    """Talk works on anything: a done ticket's agent is told the ticket and that it is done, the ticket stays done and
    untaken; a second Talk while one is open is refused, naming it; a node's Talk, after the first is closed, is told
    the node's address and how to read it."""
    dispatch.store.finish_work(dispatch.id, 'Finished')
    for name, value in dispatch.env('hold').items():
        monkeypatch.setenv(name, value)
    unwritten = run('dispatch', 'talk', f'id={dispatch.id}', cwd=dispatch.folder, ok=False)
    assert 'This needs its prompt written:' in unwritten.stderr and 'prompts.xml talk' in unwritten.stderr
    monkeypatch.setenv('METAFORM_PROMPTS', str(TRIAL_PROMPTS))
    result = json.loads(run('dispatch', 'talk', f'id={dispatch.id}', '--json', cwd=dispatch.folder).stdout)
    dispatch_runners.append((result, dispatch.folder, dispatch.log))
    text = eventually(lambda: dispatch.received('session/prompt'))[0]['params']['prompt'][0]['text']
    assert f'ticket {dispatch.id}, done' in text and 'Test talk prompt.' in text
    assert dispatch.ticket().done and not dispatch.ticket().taken
    refused = run('dispatch', 'talk', 'node=code.engine', cwd=dispatch.folder, ok=False)
    assert refused.returncode != 0 and dispatch.id in refused.stderr + refused.stdout
    dispatch.stop()
    eventually(lambda: not [row for row in json.loads(run('dispatch', 'sessions', 'thread=false', '--json',
                                                          cwd=dispatch.folder).stdout)['sessions']
                            if row['state'] == 'running'])
    node = json.loads(run('dispatch', 'talk', 'node=code.engine', '--json', cwd=dispatch.folder).stdout)
    dispatch_runners.append((node, dispatch.folder, dispatch.log))
    told = eventually(lambda: [one for one in dispatch.received('session/prompt') if 'node code.engine' in
                               one['params']['prompt'][0]['text']])[0]['params']['prompt'][0]['text']
    assert '`metaform map where code.engine`' in told


def test_start_reserves_ticket_before_runner_launch_and_restores_claim_on_launch_failure(dispatch, run, monkeypatch):
    from metaform.module import Stop, context
    from metaform.modules import dispatch as module
    ctx = context('dispatch', dispatch.folder, project='proj', nouns={'id': dispatch.id, 'agent': 'claude'})
    run('map', 'work', 'op=edit', f'id={dispatch.id}', 'glyph=kite', cwd=dispatch.folder)
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
    run('map', 'work', 'op=edit', f'id={dispatch.id}', 'glyph=kite', cwd=dispatch.folder)
    [other] = glyphed(dispatch, run, ('Next ticket', 'kite', False))
    began = []
    async def session_run(session):
        work_id = session.work_id
        assert dispatch.store.ticket(work_id).work.taken_by.startswith('dispatch starting ')
        competing = other if work_id == dispatch.id else work_id
        with pytest.raises(Stop, match='kite|taken'):
            module.start(context('dispatch', dispatch.folder, project='proj',
                                 nouns={'id': competing, 'agent': 'claude'}))
        began.append(work_id)
        dispatch.store.finish_work(work_id, 'Finished')
        return {'work_id': work_id}
    monkeypatch.setattr(runner.Session, 'run', session_run)
    ctx = context('dispatch', dispatch.folder, project='proj', nouns={'id': dispatch.id, 'agent': 'claude'})
    result = asyncio.run(runner.dispatch(ctx))
    assert result['worked'] == began == [dispatch.id, other]


def test_reset_releases_tickets_dead_agents_hold_and_closes_their_sessions(dispatch, run):
    """After crashes a ticket can stay taken, by a start that died or a runner that is gone, and hold a slot for good;
    reset puts it back on the board and records the session as ended, deleting nothing."""
    from metaform.data import Store
    dispatch.store.take_work(dispatch.id, by='dispatch starting deadbeef')
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('sessions', {'session_id': 'gone', 'work_id': dispatch.id, 'agent': 'claude', 'state': 'running',
                               'pid': 999999, 'port': 1, 'token': 'x', 'started': '2026-10-05T00:00:00Z', 'seq': 1})
    done = json.loads(run('dispatch', 'reset', '--json', cwd=dispatch.folder).stdout)
    assert done['released'] == [dispatch.id] and done['sessions_ended'] == [dispatch.id]
    assert dispatch.ticket().taken is None and not dispatch.ticket().done
    with Store('proj', module='dispatch').tables(write=False) as tx:
        assert tx.get('sessions', {'session_id': 'gone'})['state'] == 'ended'


def test_a_glyph_moves_past_unfinished_work_without_retrying_it_in_the_same_run(dispatch, run, monkeypatch):
    from metaform.module import context
    from metaform.modules.dispatch import release, runner
    run('map', 'work', 'op=edit', f'id={dispatch.id}', 'glyph=kite', cwd=dispatch.folder)
    [later] = glyphed(dispatch, run, ('Later', 'kite', False))
    dispatch.store.ask(dispatch.node, 'Which format?', suggestions=['Text'], work=dispatch.id)
    began = []
    async def session_run(session):
        began.append(session.work_id)
        if len(began) > 2:
            pytest.fail('the runner selected the unfinished ticket again')
        record = session.store.ticket(session.work_id).work
        session.store.move_work(session.work_id, 'todo', record.position)
        session.store.take_work(session.work_id, by=session.by)
        if session.work_id == later:
            dispatch.store.finish_work(later, 'Finished')
            how = 'the ticket is done'
        else:
            how = 'cannot continue without an answer'
        await asyncio.to_thread(release, session.store, session.work_id, session.by, True, None, how)
        return {'work_id': session.work_id, 'ended': how}
    monkeypatch.setattr(runner.Session, 'run', session_run)
    result = asyncio.run(runner.dispatch(context('dispatch', dispatch.folder, project='proj',
                                                nouns={'id': dispatch.id, 'agent': 'claude'})))
    assert result['worked'] == began == [dispatch.id, later]
    assert not dispatch.ticket().taken and not dispatch.ticket().held


def test_a_real_glyph_runner_moves_past_a_questioned_ticket(dispatch, run):
    run('map', 'work', 'op=edit', f'id={dispatch.id}', 'glyph=kite', cwd=dispatch.folder)
    [later] = glyphed(dispatch, run, ('Later', 'kite', False))
    dispatch.start('question', FAKE_ACP_ASK_AT='code.engine')
    assert dispatch.process.wait(20) == 0, dispatch.process.stderr.read().decode()
    sent = dispatch.received('session/prompt')
    assert len(sent) == 2
    assert later in sent[1]['params']['prompt'][0]['text']
    assert not dispatch.store.ticket(later).work.taken


def test_the_agent_limit_counts_every_ticket_in_motion_even_one_whose_runner_does_not_answer(dispatch, run, monkeypatch):
    """Found 2026-10-05: eight agents ran against a limit of five, because a runner that did not answer its status check
    was not counted. A ticket an agent holds is an agent at work, whatever its runner answers."""
    from metaform.module import context
    from metaform.modules import dispatch as module
    ids = glyphed(dispatch, run, *[(str(n), None, False) for n in range(4)])
    run('set', '--dispatch-autostart', '--dispatch-agents', '3', cwd=dispatch.folder)
    for work_id in ids[:2]:
        dispatch.store.take_work(work_id, by='codex a-session-that-does-not-answer')
    launched = []
    monkeypatch.setattr(module, 'start', lambda ctx: launched.append(ctx.nouns['id']) or {'work_id': ctx.nouns['id']})
    module.autostart(context('dispatch', dispatch.folder, project='proj'))
    assert len(launched) == 1, 'two tickets in motion leave one of three slots'
