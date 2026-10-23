"""Long questions remain readable without displacing roundtable participants and controls."""
import pytest

from metaform.modules.web.tests.test_web import browser, mapped, opened, started, web  # noqa: F401

pytestmark = [pytest.mark.kind('simulation'), pytest.mark.browser]


def test_long_question_scrolls_inside_header(run, web, mapped, browser):  # noqa: F811
    run('set', '--web-bubble-seconds=60')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    topic = 'Inspect project code before answering. Preserve every requirement.\n' * 200
    page.route('**/api/roundtable?*', lambda route: route.fulfill(json={'seats': [], 'events': [
        {'kind': 'turn', 'seat': 'First', 'text': 'Inspect the code before changing the design.'}],
        'latest': 1, 'status': {
        'table': 'large', 'topic': topic, 'state': 'running', 'seats': ['codex/one'], 'seated': ['First']}}))
    page.evaluate("async () => (await import('/page/app/roundtable/stage.js')).openRoundtable(true)")
    question = page.get_by_role('textbox', name='Your question to the table', exact=True)
    question.fill(topic)
    size = question.bounding_box()
    assert size and size['height'] == pytest.approx(200, abs=1)
    assert question.evaluate('el => getComputedStyle(el).resize') == 'vertical'
    page.mouse.move(size['x'] + size['width'] - 3, size['y'] + size['height'] - 3)
    page.mouse.down()
    page.mouse.move(size['x'] + size['width'] - 3, size['y'] + size['height'] + 57, steps=5)
    page.mouse.up()
    assert question.bounding_box()['height'] >= size['height'] + 40
    assert question.input_value() == topic
    page.evaluate('''async () => {
        const stage = await import('/page/app/roundtable/stage.js');
        stage.TABLE.id = 'large'; stage.TABLE.kind = 'roundtables:large';
        await stage.openRoundtable();
    }''')
    page.get_by_role('button', name='Hold', exact=True).wait_for()
    for width in (1280, 375):
        page.set_viewport_size({'width': width, 'height': 800})
        bounds = page.evaluate('''async () => {
            const {bubbles3d} = await import('/page/app/figures/bubble3d.js');
            for (let n = 0; n < 30; n++) { await new Promise(requestAnimationFrame); bubbles3d(); }
            const root = document.querySelector('.roundtable').getBoundingClientRect();
            const question = document.querySelector('.rt-question');
            const box = question.getBoundingClientRect();
            const hold = document.querySelector('.rt-hold').getBoundingClientRect();
            const bubble = [...document.querySelectorAll('#bubbles .wbubble')]
                .find(el => el.style.display !== 'none' && el.dataset.name === 'First');
            const body = bubble.querySelector('[id^="wbubble-body-"]').getBoundingClientRect();
            const band = document.querySelector('.rt-band').getBoundingClientRect();
            return {questionHeight: box.height, lineHeight: parseFloat(getComputedStyle(question).lineHeight),
                scrolls: question.scrollHeight > question.clientHeight,
                bandHeight: band.height, scale: Number(bubble.style.transform.match(/scale\\(([^)]+)\\)/)[1]),
                bubbleInside: body.left >= band.left && body.right <= band.right
                    && body.top >= band.top && body.bottom <= band.bottom,
                controlsInside: hold.top >= root.top && hold.bottom <= root.bottom};
        }''')
        assert bounds['questionHeight'] <= 3 * bounds['lineHeight'] + 1, bounds
        assert bounds['scrolls'] and bounds['bandHeight'] > 0 and bounds['controlsInside'], bounds
        assert bounds['bubbleInside'], bounds
        if width == 1280:
            assert bounds['scale'] == pytest.approx(1.25), bounds
        assert page.locator('.rt-question').text_content() == topic
    page.screenshot(path='/tmp/roundtable-long-prompt-fixed.png')
    page.evaluate("localStorage.setItem('metaform.bubbleSize', '0')")
    page.reload()
    page.wait_for_function('() => window.metaform.loaded()')
    assert page.evaluate('''async () => {
        const {stepBubbleSize} = await import('/page/app/figures/bubble3d.js');
        return stepBubbleSize();
    }''') == 1  # Explicit smallest setting survives reload.
    assert not problems
    page.close()
