"""Word-bubble expiry follows the person's formula without holding the next speaker."""
import pytest

from metaform.modules.web.tests.test_web import browser, mapped, opened, started, web  # noqa: F401

pytestmark = [pytest.mark.kind('simulation'), pytest.mark.browser]


def test_wait_formula_and_independent_roundtable_expiry(run, web, mapped, browser):  # noqa: F811
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    cases = {'': 2050, 'bcdf': 2050, 'AI': 2050, 'ai ai': 2050, 'make': 2050, 'make!': 2150,
             'eau': 2050, 'queue': 2150, 'cie': 2050, 'eo': 2050, '0': 2050, '123456789': 2450,
             '.,;:!?': 2300}
    computed = page.evaluate('''async texts => {
        const {bubbleSeconds} = await import('/page/app/figures/bubble.js');
        return {auto: texts.map(text => 1000 * bubbleSeconds(text, 'auto')),
            fixed: bubbleSeconds('queue', '10')};
    }''', list(cases))
    assert computed['auto'] == pytest.approx(list(cases.values()))
    assert computed['fixed'] == 10

    page.route('**/api/roundtable?*', lambda route: route.fulfill(json={
        'events': [
            {'kind': 'turn', 'seat': 'First',
             'text': 'We should examine queue timing carefully before changing model execution.'},
            {'kind': 'veto', 'seat': 'Second', 'text': 'queue'}],
        'latest': 2, 'status': {'table': 'timing', 'topic': 'Bubble timing', 'state': 'running',
                               'seats': ['codex/one', 'claude/two'], 'seated': ['First', 'Second']}}))
    page.evaluate('''async () => {
        const stage = await import('/page/app/roundtable/stage.js');
        const {takeBubbleSeconds} = await import('/page/app/workspace/workspace.js');
        takeBubbleSeconds('auto');
        stage.TABLE.id = 'timing'; stage.TABLE.kind = 'roundtables:timing';
        window.__timingStage = stage;
        await stage.openRoundtable();
    }''')
    page.wait_for_function('() => window.__timingStage.stageView().speakers[1]?.text === "queue"')
    expiry = page.evaluate('''async () => {
        const {SEATS} = await import('/page/app/figures/bubble3d.js');
        const {bubbleSeconds} = await import('/page/app/figures/bubble.js');
        const [first, second] = window.__timingStage.stageView().speakers;
        const firstUntil = first.lineAt + 1000 * bubbleSeconds(first.text, 'auto');
        const secondUntil = second.lineAt + 1000 * bubbleSeconds(second.text, 'auto');
        SEATS.frame(second.lineAt + 1);
        const together = [first.want, second.want];
        SEATS.frame(firstUntil - 1);
        const before = first.want;
        SEATS.frame(firstUntil + 1);
        const after = first.want;
        SEATS.frame(secondUntil + 1);
        return {together, before, after, secondAfter: second.want,
            nextBeforeExpiry: second.lineAt < firstUntil};
    }''')
    assert expiry == {'together': [1, 1], 'before': 1, 'after': 0, 'secondAfter': 0, 'nextBeforeExpiry': True}
    assert not problems
    page.close()
