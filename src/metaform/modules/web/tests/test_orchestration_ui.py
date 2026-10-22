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


def test_the_agents_key_names_an_ended_session_without_its_assignment_record(run, mapped):  # noqa: F811
    """The agents key names an ended session by its responsibility and delivery, without its assignment's record and
    directions, which made the read megabytes; a second read, from the states it keeps, says the same."""
    from metaform.modules.dispatch import ENDED_ASSIGNMENT, read_sessions

    run('enable', 'dispatch', cwd=mapped)
    run('enable', 'orchestration', cwd=mapped)
    owner, gc = managed_assignment(mapped)
    assessment = owner.assessment(context('orchestration', mapped, session='gc-ui'), gc,
        {'summary': 'GC validated countdown; review selection usability.', 'evidence': ['candidate-7 countdown check']},
        'view-assessment')
    owner.bind(context('orchestration', mapped), assessment['assignment_id'], 'fqc-ui')
    record_view_session(mapped, assessment, 'fqc-ui')
    listed = read_sessions(context('dispatch', mapped, nouns={'thread': False}))['states']['fqc-ui']
    assert set(listed['orchestration']) == set(ENDED_ASSIGNMENT) and listed['pending_direction'] == []
    assert listed['orchestration']['reviewed_assignment_id'] == gc['assignment_id']
    assert listed['authored_role_uri'] == 'metaform://role/functionality'
    assert read_sessions(context('dispatch', mapped, nouns={'thread': False}))['states']['fqc-ui'] == listed


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
    for agent in ('claude', 'codex', 'antigravity'):
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


def test_roundtable_creation_automation_is_explicit_and_resets_for_each_table(
        run, web, mapped, browser):  # noqa: F811 -- shared browser fixtures
    started(run)
    page, problems, _ = opened(browser, web)
    created = []

    def open_table(route):
        created.append(route.request.post_data_json)
        route.fulfill(json={'table': f'created-{len(created)}'})

    def read_table(route):
        if 'table=' not in route.request.url:
            route.fulfill(json={'seats': []})
        else:
            route.fulfill(json={'events': [], 'latest': 0, 'status': {
                'state': 'ended', 'topic': 'Prepare tickets', 'seats': []}})

    page.route('**/api/roundtable-open', open_table)
    page.route('**/api/roundtable?*', read_table)
    page.evaluate("""async () => {
        const {openRoundtable} = await import('/page/app/roundtable/stage.js');
        await openRoundtable(true);
    }""")
    automate = page.get_by_role('checkbox', name='Automate Ticket Creation', exact=True)
    assert not automate.is_checked()
    assert 'inactive board' in page.locator('#rt-automate-description').inner_text()
    for selected in (False, True):
        if selected:
            automate.check()
        page.get_by_role('textbox', name='Your question to the table', exact=True).fill('Prepare tickets')
        page.click('.rt-start')
        page.wait_for_selector('#roundtable[data-state="ended"]')
        assert created[-1]['automate_ticket_creation'] is selected
        page.click('.rt-new')
        page.wait_for_selector('.rt-setup:not([hidden])')
        assert not automate.is_checked()
    assert len(created) == 2
    assert not problems


@pytest.mark.parametrize('answer_text', ['Use both topic results.', ''])
def test_roundtable_result_shows_all_topics_before_paced_turns_and_survives_reopening(
        run, web, mapped, browser, answer_text):  # noqa: F811 -- shared browser fixtures
    """An ended table keeps its complete result even while earlier turns wait for their speaking time."""
    started(run)
    page, problems, _ = opened(browser, web)
    result = {
        'state': 'ended', 'topic': 'Keep every topic', 'seats': ['codex/sol'], 'seated': ['Sol'],
        'answer': answer_text, 'saved': 'docs/roundtables/7-keep-every-topic',
        'topics': [
            {'number': 1, 'title': 'Storage', 'synthesis': {'ideas': [
                {'id': 'I1', 'name': 'Keep files', 'summary': 'Save every turn.'},
                {'id': 'I2', 'name': 'Keep rows', 'summary': 'Store searchable records.'}]},
             'borda': {'order': ['I2', 'I1'], 'points': {'I1': 2, 'I2': 4}},
             'host_summary': {'name': 'Host', 'text': 'Use searchable rows.'}},
            {'number': 2, 'title': 'Delivery', 'synthesis': {'ideas': [
                {'id': 'I1', 'name': 'Show results', 'summary': 'Keep results visible.'}]},
             'borda': {'order': ['I1'], 'points': {'I1': 0}},
             'host_summary': {'name': 'Host', 'text': 'Show results immediately.'}},
        ],
    }
    final_answer = answer_text or 'The table ended without a final answer.'
    requests = []
    ended = False

    def answer(route):
        requests.append(route.request.url)
        if 'table=' not in route.request.url:
            route.fulfill(json={'seats': []})
            return
        after = int(route.request.url.split('after=')[1].split('&')[0])
        events = []
        if ended and not after:
            events = [{'kind': 'turn', 'seat': 'Sol', 'text': f'Earlier turn {number}'} for number in range(3)]
            events += [{'kind': 'summary', 'name': 'Host', 'text': 'Earlier topic answer.'},
                       {'kind': 'end', **result}]
        status = result if ended else {**result, 'state': 'running'}
        route.fulfill(json={'events': events, 'latest': 5 if ended else 0, 'status': status})

    page.route('**/api/roundtable?*', answer)
    page.evaluate("""async () => {
        const stage = await import('/page/app/roundtable/stage.js');
        Object.assign(stage.TABLE, {id: 'result-table', kind: 'roundtables:result-table'});
        await stage.openRoundtable();
    }""")
    page.wait_for_selector('#roundtable[data-state="running"]')
    assert page.locator('.rt-chair, .rt-say, .rt-hold, .rt-continue, .rt-advance, .rt-end').count() == 0
    before = len(requests)
    page.evaluate("""async () => {
        const {tableChange} = await import('/page/app/roundtable/stage.js');
        for (let n = 0; n < 20; n++) tableChange({kinds: ['roundtables', 'roundtables:another-table']});
    }""")
    assert len(requests) == before
    ended = True
    page.evaluate("""async () => {
        const {tableChange} = await import('/page/app/roundtable/stage.js');
        tableChange({kinds: ['roundtables', 'roundtables:result-table']});
    }""")
    page.wait_for_selector('#roundtable[data-state="ended"] .rt-results:not([hidden])')
    assert page.locator('.rt-topic-result').count() == 2
    assert page.locator('.rt-topic-result[data-topic="1"] .rt-borda tbody').inner_text() == (
        '1\tKeep rows\t4\n2\tKeep files\t2')
    assert page.locator('.rt-topic-result[data-topic="2"] .rt-borda tbody').inner_text() == '1\tShow results\t0'
    assert 'Save every turn.' in page.locator('.rt-topic-result[data-topic="1"]').inner_text()
    assert 'Use searchable rows.' in page.locator('.rt-topic-result[data-topic="1"]').inner_text()
    assert page.locator('.rt-answertext').inner_text() == final_answer
    # The end result arrives before the earlier turns finish their deliberate pacing.
    assert page.locator('.rt-transcript .rt-turn').count() < 3
    links = page.locator('.rt-records a').evaluate_all('(links) => links.map(link => link.getAttribute("href"))')
    assert len(links) == 2
    assert all('project=proj&table=result-table&file=' in link for link in links)
    assert any('file=export.json' in link for link in links)
    assert any('file=mechanical-report.md' in link for link in links)
    page.click('.rt-leave')  # flushes the paced summaries, which must preserve the final answer
    assert page.locator('.rt-answertext').inner_text() == final_answer
    page.evaluate("""async () => {
        const {openRoundtable} = await import('/page/app/roundtable/stage.js');
        await openRoundtable();
    }""")
    page.wait_for_selector('#roundtable:not([hidden])')
    page.wait_for_function('() => document.querySelector(".rt-state").textContent === "Ended"')
    assert page.locator('.rt-topic-result').count() == 2
    assert page.locator('.rt-records a').count() == 2
    assert page.locator('.rt-answertext').inner_text() == final_answer
    assert 'system agent is writing' not in page.locator('.rt-transcript').inner_text()
    page.click('.rt-new')
    page.wait_for_selector('.rt-setup:not([hidden])')
    assert page.locator('.rt-topic-result').count() == 0
    assert not problems


@pytest.mark.parametrize(('stage_name', 'decision'), [
    ('research', 'yes'), ('research', 'no'), ('plan_review', 'comment'),
    ('plan_review', 'revise'), ('plan_review', 'approve'), ('execution_outline', 'approve')])
def test_roundtable_pipeline_loads_full_current_output_before_person_decides(
        run, web, mapped, browser, stage_name, decision):  # noqa: F811 -- shared browser fixtures
    """Every stage asks beside its full output. Plan review offers distinct comment, revision and approval paths."""
    from urllib.parse import parse_qs, urlparse

    started(run)
    page, problems, _ = opened(browser, web)
    filename = {'research': 'research.md', 'plan_review': 'plan.md',
                'execution_outline': 'execution-outline.md'}[stage_name]
    pipeline = {'stage': stage_name, 'state': 'running', 'file': f'docs/roundtables/7-results/{filename}',
                'ticket': 'stage-ticket', 'revision': 1, 'error': 'Stage write will retry.',
                'question': 'Proceed with this output?'}
    sequence = 0
    reviews, decisions, pending = [], [], []
    text = '# Full stage output\nKeep every result. <script>window.pipelineRan = true</script>'

    def answer(route):
        query = parse_qs(urlparse(route.request.url).query)
        if query.get('pipeline') == ['1']:
            reviews.append((pipeline['revision'], pipeline['digest']))
            pending.append(route)
            return
        after = int(query.get('after', ['0'])[0])
        events = [{'kind': 'pipeline', 'pipeline': pipeline}] if after < sequence else []
        body = {'events': events, 'latest': sequence}
        if query.get('whole') == ['1']:
            body['status'] = {'state': 'ended', 'topic': 'Stage review', 'seats': ['codex/sol'],
                              'seated': ['Sol'], 'answer': 'Keep all results.', 'pipeline': pipeline}
        route.fulfill(json=body)

    def decide(route):
        nonlocal pipeline
        body = route.request.post_data_json
        decisions.append(body)
        pipeline = {**pipeline, 'state': {'no': 'stopped', 'comment': 'awaiting'}.get(body['action'], 'running')}
        route.fulfill(json={'table': 'pipeline-table', 'pipeline': pipeline})

    page.route('**/api/roundtable?*', answer)
    page.route('**/api/roundtable-decision', decide)
    page.evaluate("""async () => {
        const stage = await import('/page/app/roundtable/stage.js');
        Object.assign(stage.TABLE, {id: 'pipeline-table', kind: 'roundtables:pipeline-table'});
        await stage.openRoundtable();
    }""")
    page.wait_for_selector('.rt-pipeline:not([hidden])')
    assert page.locator('.rt-pipeline-state').inner_text().endswith(': Running')
    assert page.locator('.rt-pipeline-error').inner_text() == pipeline['error']
    assert page.locator('.rt-approve').is_hidden()
    assert page.locator('.rt-no').is_hidden()
    assert not reviews and not decisions

    def announce():
        page.evaluate("""async () => {
            const {tableChange} = await import('/page/app/roundtable/stage.js');
            tableChange({kinds: ['roundtables', 'roundtables:pipeline-table']});
        }""")

    pipeline = {**pipeline, 'state': 'awaiting', 'digest': 'a' * 64, 'error': ''}
    sequence += 1
    with page.expect_request('**/api/roundtable?*pipeline=1'):
        announce()
    page.wait_for_function('() => document.querySelector(".rt-review").disabled')
    assert page.locator('.rt-no').is_disabled()
    assert page.locator('.rt-pipeline-error').is_hidden()
    assert not decisions
    pending.pop(0).fulfill(json={'table': 'pipeline-table', 'pipeline': pipeline, 'output_text': text})
    page.wait_for_function('() => !document.querySelector(".rt-no").disabled')
    assert page.locator('.rt-pipeline-text').inner_text() == text
    assert page.locator('.rt-pipeline-question').inner_text() == pipeline['question']
    assert page.locator('.rt-pipeline-link').get_attribute('href').endswith(f'file={filename}')
    assert page.evaluate('() => window.pipelineRan') is None
    assert reviews == [(1, 'a' * 64)] and not decisions
    assert page.locator('.rt-yes').is_hidden() == (stage_name != 'research')
    assert page.locator('.rt-approve').is_hidden() == (stage_name == 'research')
    assert page.locator('.rt-revise').is_hidden() == (stage_name != 'plan_review')
    # Even unchanged bytes in a new revision require fresh review before any decision.
    pipeline = {**pipeline, 'revision': 2}
    sequence += 1
    with page.expect_request('**/api/roundtable?*pipeline=1'):
        announce()
    page.wait_for_function('() => document.querySelector(".rt-no").disabled')
    assert page.locator('.rt-pipeline-text').is_hidden()
    pending.pop(0).fulfill(json={'table': 'pipeline-table', 'pipeline': pipeline, 'output_text': text})
    page.wait_for_function('() => !document.querySelector(".rt-no").disabled')
    assert reviews == [(1, 'a' * 64), (2, 'a' * 64)]
    assert not decisions
    if stage_name == 'plan_review':
        page.fill('.rt-comment', 'Retain every result.')
    page.click('.rt-send-comment' if decision == 'comment' else f'.rt-{decision}')
    page.wait_for_function('() => !document.querySelector(".rt-review").disabled')
    assert len(decisions) == 1
    assert {key: decisions[0][key] for key in ('table', 'action', 'digest', 'revision', 'comment')} == {
        'table': 'pipeline-table', 'action': decision, 'digest': 'a' * 64, 'revision': 2,
        'comment': 'Retain every result.' if stage_name == 'plan_review' else ''}
    assert decisions[0]['project'] == 'proj'
    assert page.locator('.rt-pipeline-text').inner_text() == text
    if decision == 'comment':
        assert page.locator('.rt-revise').is_visible()
        assert page.locator('.rt-approve').is_enabled()
    else:
        assert page.locator('.rt-approve').is_hidden()
        assert page.locator('.rt-no').is_hidden()
    assert not problems
