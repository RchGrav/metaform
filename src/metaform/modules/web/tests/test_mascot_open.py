"""Mascot board commands use the page controls without closing an open board."""
import pytest

from metaform.modules.web.tests.test_web import browser, mapped, opened, started, web  # noqa: F401

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.browser, pytest.mark.req('VIEW-005')]


def test_mascot_opens_board_without_global_selector(run, web, mapped, browser):  # noqa: F811
    started(run)
    page, problems, _ = opened(browser, web, plain=True)
    try:
        result = page.evaluate("""async () => {
            const {mascotEvent} = await import('/page/app/figures/attention.js');
            const {S} = await import('/page/app/core/reads.js');
            const board = document.querySelector('#board');
            board.hidden = true;
            let clicks = 0;
            document.querySelector('#boardBtn').addEventListener('click', () => clicks++);
            const command = {project: S.project, act: 'open', what: 'board'};
            mascotEvent(command);
            const opened = !board.hidden;
            mascotEvent(command);
            return {opened, stillOpen: !board.hidden, clicks, globalSelector: typeof window.$};
        }""")
        assert result == {'opened': True, 'stillOpen': True, 'clicks': 1, 'globalSelector': 'undefined'}
        assert not problems
    finally:
        page.close()
