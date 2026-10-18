"""Project notifications are real Chat messages and retain their latest body across the session view's cache."""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context

import pytest

from metaform.data import Node
from metaform.module import context, provided, refresh_modules
from metaform.modules.web.tests.test_web import browser, mapped, opened, started, web  # noqa: F401

pytestmark = pytest.mark.kind('fixture')


def notify(folder, identifier, body):
    def publish():
        refresh_modules()
        transport = provided(folder, 'orchestration.transport')[0][1]
        return transport.notify_user(context('dispatch', folder), {'body': body}, identifier)

    # The real background drain calls this synchronous transport in a worker thread. Playwright's main thread
    # already has an event loop, where the chassis intentionally refuses synchronous event publication.
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(copy_context().run, publish).result()


def test_notification_body_and_cache_refresh_are_exposed_by_the_real_session_read(run, mapped):  # noqa: F811
    run('enable', 'dispatch', cwd=mapped)
    first = notify(mapped, 'change-1', 'Adaptive revision 2 preserves checkout completion with a simpler interaction.')

    def read():
        return json.loads(run('dispatch', 'sessions', 'thread=false', '--json', cwd=mapped).stdout)

    visible = read()
    state = visible['states'][first['session_id']]
    assert state['notification'] is True
    assert state['latest_message_id'] == 'change-1'
    assert 'checkout completion' in state['latest_message_text']
    notify(mapped, 'change-2', 'The GC received the change order and the explanation is visible in Project updates.')
    latest = read()['states'][first['session_id']]
    assert latest['latest_message_id'] == 'change-2'
    assert 'GC received' in latest['latest_message_text']
    # Replaying the same continuation neither duplicates its message nor invents a new latest update.
    notify(mapped, 'change-2', 'The GC received the change order and the explanation is visible in Project updates.')
    thread = json.loads(run('dispatch', 'sessions', f'id={first["session_id"]}', '--json', cwd=mapped).stdout)
    assert len([one for one in thread['lines'] if one['kind'] == 'agent_message_chunk']) == 2


def managed_assignment(folder):
    refresh_modules()
    ctx = context('orchestration', folder, session='gc-ui')
    work = ctx.require_store().add_work(Node('element', 'code.timer.kitchen'), None,
                                        title='Keep the timer usable', task='Preserve timer interaction.')
    owner = provided(folder, 'orchestration')[0][1]
    gc = owner.claim(context('orchestration', folder, session='gc-ui', nouns={'work': work.id}))
    return owner, gc


def record_view_session(folder, assignment, session):
    with context('dispatch', folder).require_store().tables() as tx:
        tx.insert('agent_sessions', {'session_id': session, 'work_id': assignment['work_id'], 'agent': 'claude',
                                     'state': 'ended', 'how': 'retained fixture context',
                                     'started': '2026-10-18T00:00:00Z', 'seq': 1})
        tx.insert('session_lines', {'session_id': session, 'work_id': assignment['work_id'], 'name': 'state',
                                    'kind': 'state', 'text': json.dumps({'role': 'worker'}), 'seq': 1})


@pytest.mark.parametrize('thread', [True, False])
def test_scoped_assignment_view_reads_only_its_relationships_and_preserves_independent_assessment(
        run, mapped, monkeypatch, thread):  # noqa: F811
    from metaform.modules.dispatch import read_sessions

    run('enable', 'dispatch', cwd=mapped)
    run('enable', 'orchestration', cwd=mapped)
    owner, gc = managed_assignment(mapped)
    assessment = owner.assessment(context('orchestration', mapped, session='gc-ui'), gc,
        {'summary': 'GC validated countdown; review selection usability.', 'evidence': ['candidate-7 countdown check']},
        'view-assessment')
    owner.bind(context('orchestration', mapped), assessment['assignment_id'], 'fqc-ui')
    record_view_session(mapped, assessment, 'fqc-ui')

    def unrelated_scan(*_args, **_kwargs):
        pytest.fail('A scoped session view scanned all assignments.')

    monkeypatch.setattr(owner, 'assignments', unrelated_scan)
    shown = read_sessions(context('dispatch', mapped, nouns={'id': assessment['work_id'], 'thread': thread}))
    state = shown['states']['fqc-ui']
    assert state['authored_role_uri'] == 'metaform://role/functionality'
    assert state['reviewed_work_id'] == gc['work_id'] and state['reviewed_session_id'] == 'gc-ui'
    assert state['parent_assignment_id'] is None and state['team_id'] != gc['team_id']
    assert state['reviewed_gc_id'] == state['owner_gc_id'] == gc['assignment_id']
    assert ('continuations' in state['orchestration']) is thread


def test_native_role_menu_uses_registered_definitions_and_the_independent_assessment_launch_route(run, mapped):  # noqa: F811
    from metaform.modules.web.server import call_role, role_choices

    run('enable', 'dispatch', cwd=mapped)
    run('enable', 'orchestration', cwd=mapped)
    owner, gc = managed_assignment(mapped)
    menu = role_choices({'project': 'proj'})
    native = {one['role']: one for one in menu['roles'] if one['provider'] == 'orchestration'}
    assert len(native) == 17
    assert native['functionality']['launch'] == 'assessment'
    assert native['role_creator']['launch'] == 'commission' and native['gc']['launch'] == 'claim'
    child = call_role({'project': 'proj', 'assignment': gc['assignment_id'], 'role': 'verifier',
                      'task': 'Verify the selected candidate.', 'result': 'Return observations.'})
    assert child['parent_assignment_id'] == gc['assignment_id'] and child['team_id'] == gc['team_id']
    assessment = call_role({'project': 'proj', 'assignment': gc['assignment_id'], 'role': 'functionality',
                           'task': 'Independently assess the timer interactions.'})
    assert assessment['parent_assignment_id'] is None and assessment['team_id'] != gc['team_id']
    assert assessment['reviewed_assignment_id'] == gc['assignment_id']
    assert owner.pending(context('orchestration', mapped))  # both use the actual queued continuation path


def test_project_update_opens_its_actual_chat_without_start_resume_or_send_controls(
        run, web, mapped, browser):  # noqa: F811
    run('enable', 'dispatch', cwd=mapped)
    body = 'Adaptive revision 2 preserves checkout completion with a simpler interaction.'
    notify(mapped, 'change-1', body)
    started(run)
    page, problems, _ = opened(browser, web, plain=True)
    # an update raises no banner the person has to close: it is in the chat, 2026-10-18
    page.evaluate('''async () => {
        const {D, agentAt} = await import('/page/app/agents/dispatch.js');
        const {notificationState} = await import('/page/app/session/orchestration.js');
        for (let n = 0; n < 100 && !D.sessions.some(one => notificationState(D.states?.[one.session_id])); n++)
            await new Promise(done => setTimeout(done, 100));
        const session = D.sessions.find(one => notificationState(D.states?.[one.session_id]));
        agentAt(session.work_id, session.session_id);
    }''')
    assert page.locator('#banners [data-key="project-updates"]').count() == 0
    page.wait_for_selector('#helpdesk .log .bubble')
    assert body in page.locator('#helpdesk .log').inner_text()
    assert page.locator('#helpdesk .compose').is_hidden()
    assert page.locator('#helpdesk .calls').is_hidden()
    assert page.locator('#helpdesk .threadbar .again').is_hidden()
    assert page.locator('#helpdesk .threadbar .stop').is_hidden()
    assert page.locator('#helpdesk .sessionbar').is_hidden()
    assert page.locator('#helpdesk .who .title').inner_text() == 'Project updates'
    notify(mapped, 'change-2', 'The GC received the new direction; the ticket continues without an approval wait.')
    page.wait_for_function('() => document.querySelector("#helpdesk .log").innerText.includes("without an approval wait")')
    assert page.locator('#banners [data-key="project-updates"]').count() == 0
    assert problems == []


def test_role_picker_keeps_native_and_installed_bmad_sources_and_calls_the_actual_adapter(
        run, web, mapped, browser, tmp_path):  # noqa: F811
    from metaform.modules.dispatch.tests.test_dispatch import FAKE, eventually
    from metaform.modules.orchestration.tests.test_bmad import installed_manifest

    run('enable', 'dispatch', cwd=mapped)
    run('enable', 'orchestration', cwd=mapped)
    run('set', '--dispatch-agents', '1', '--dispatch-machine-agents', '1', cwd=mapped)
    source = installed_manifest(mapped)
    authored = source.read_text()
    log = tmp_path / 'role-picker-acp.jsonl'
    adapter = tmp_path / 'role_picker_adapter.py'
    adapter.write_text('import os, runpy\n'
        f'os.environ["FAKE_ACP_LOG"] = {str(log)!r}\n'
        'os.environ["FAKE_ACP_MODE"] = "ask"\n'
        f'runpy.run_path({str(FAKE)!r}, run_name="__main__")\n', encoding='utf-8')
    for agent in ('claude', 'codex', 'gemini'):
        run('set', f'--dispatch-{agent}', f'"{sys.executable}" "{adapter}"', cwd=mapped)
    _, gc = managed_assignment(mapped)
    record_view_session(mapped, gc, 'gc-ui')
    started(run)
    page, problems, _ = opened(browser, web, plain=True)
    try:
        page.evaluate('''async ({work}) => {
            const {openHelpdesk} = await import('/page/app/dock/threads.js');
            openHelpdesk(work, 'the fixture GC', '', 'gc-ui', 'agent');
        }''', {'work': gc['work_id']})
        page.locator('#helpdesk .assignmentbox > details > summary').click()
        page.get_by_role('button', name='Choose specialist').click()
        picker = page.get_by_label('Specialist responsibility')
        picker.wait_for(state='visible')
        assert picker.locator('optgroup[label="Native"] option').count() == 17
        assert picker.locator('optgroup[label="BMAD"] option').count() == 1
        picker.select_option('verifier')
        assert 'observed behavior' in page.locator('#helpdesk .rolecall .hint').first.inner_text()
        picker.select_option('bmad.bmm.dev')
        page.get_by_text('Installed BMAD menu', exact=True).click()
        assert 'cmd="CR"' in page.locator('#helpdesk .rolecall pre').inner_text()
        assert str(source) in page.locator('#helpdesk .rolecall .source').inner_text()
        page.get_by_label('Requested specialist contribution').fill('CR: review the fixture candidate and return evidence.')
        page.get_by_role('button', name='Start contribution').click()

        def received():
            if not log.exists():
                return None
            raw = log.read_bytes()
            entries = [json.loads(line) for line in raw[:raw.rfind(b'\n') + 1].decode('utf-8').splitlines()]
            turns = [one['message']['params'] for one in entries
                     if one.get('message', {}).get('method') == 'session/prompt']
            return '\n'.join(part.get('text', '') for turn in turns for part in turn.get('prompt', [])) or None

        delivered = eventually(received, limit=30)
        assert authored in delivered
        assert 'CR: review the fixture candidate and return evidence.' in delivered
        assert 'metaform://role/bmad.bmm.dev' in delivered
        assert source.read_text() == authored
        capacity = json.loads(run('dispatch', 'agents', '--json', cwd=mapped).stdout)['slots']
        assert capacity['limit'] == capacity['used'] == capacity['machine_limit'] == capacity['machine_used'] == 1
        assert problems == []
    finally:
        run('dispatch', 'stop-all', cwd=mapped, ok=False)
