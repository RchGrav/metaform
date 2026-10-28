"""The roundtable stage on the page: its setup, its results and the pipeline's decisions."""
from __future__ import annotations

import pytest

from metaform.modules.web.tests.test_web import browser, mapped, opened, started, web  # noqa: F401

pytestmark = pytest.mark.kind('fixture')


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
