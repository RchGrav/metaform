"""Explicit ticket delivery in a real browser, isolated Git repositories and test homes."""
import importlib
from datetime import UTC, datetime

import pytest

from metaform.data import Node, Store
from metaform.module import context
from metaform.modules.dispatch.tests.test_merge import git
from metaform.modules.web.tests.test_hold_controls import board_page
from metaform.modules.web.tests.test_ticket_detail import browser, mapped, threaded, web  # noqa: F401

pytestmark = [pytest.mark.kind('simulation'), pytest.mark.browser, pytest.mark.req('VIEW-044')]
merge = importlib.import_module('metaform.modules.dispatch.merge')


@pytest.fixture
def repository(run, mapped):  # noqa: F811
    git(mapped, 'init', '-q', '-b', 'dev')
    git(mapped, 'config', 'user.email', 'test@example.com')
    git(mapped, 'config', 'user.name', 'Test')
    (mapped / 'README.md').write_text('base\n', encoding='utf-8')
    git(mapped, 'add', 'README.md')
    git(mapped, 'commit', '-qm', 'Base')
    run('enable', 'dispatch')
    run('set', '--dispatch-worktrees', '--dispatch-test-command=true', cwd=mapped)
    return mapped


def candidate(repository, *, done=False, path='feature.txt', text='Ticket feature.\n'):
    store = Store('proj')
    work = store.add_work(Node('element', 'code.timer.kitchen'), None,
                          task='Deliver ticket changes.', title='Saved implementation')
    tree = merge.worktree_for(repository, work.id)
    assert tree is not None
    (tree / path).write_text(text, encoding='utf-8')
    record = store.finish_work(work.id, 'Implementation verified.', 'Focused checks passed.')
    saved = merge.finished(context('dispatch', repository, project='proj'), store, record, tree)
    assert saved is not None and saved['state'] == merge.COMMITTED, saved
    if not done:
        # A submitted, open legacy ticket retains its resolution and saved delivery evidence.
        store.move_work(work.id, 'doing')
        with Store('proj', module='map').tables() as tx:
            fields = {'landed': datetime.now(UTC).isoformat()}
            if tx.update('ticket_settings', {'work_id': work.id}, fields) is None:
                tx.insert('ticket_settings', {'work_id': work.id, **fields})
    return work, tree, saved


def card_of(page, work):
    return page.locator(f'#board .card[data-id="{work.id}"]')


def merge_response(response):
    return '/api/ticket-merge' in response.url and response.request.method == 'POST'


def test_merge_requires_saved_verified_implementation_not_branch_or_idle_worker(
        run, web, repository, browser):  # noqa: F811
    store = Store('proj')
    untouched = store.add_work(Node('element', 'code.timer.kitchen'), None, task='Still unimplemented.')
    branch_only = store.add_work(Node('element', 'code.timer.kitchen'), None, task='A branch alone.')
    assert merge.worktree_for(repository, branch_only.id) is not None
    verified, _, _ = candidate(repository)
    unverified, _, _ = candidate(repository)
    with Store('proj', module='dispatch').tables() as tx:
        tx.update('merges', {'work_id': unverified.id}, {'evidence': None})
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('sessions', {'session_id': 'idle-without-implementation', 'work_id': untouched.id,
                               'agent': 'codex', 'state': 'completed', 'started': '2026-10-21T00:00:00Z',
                               'seq': 1})
    page = board_page(browser, web)
    try:
        assert card_of(page, verified).get_by_role('button', name='Merge', exact=True).count() == 1
        for work in (untouched, branch_only, unverified):
            assert card_of(page, work).locator('.ticket-merge').count() == 0
            card_of(page, work).locator('.lead').click()
            page.locator('#ticketDetail input[name=title]').wait_for()
            assert page.locator('#ticketDetail .ticket-merge').count() == 0
            page.locator('#ticketDetail .close').click()
    finally:
        page.close()


@pytest.mark.parametrize('already_done', [False, True])
def test_explicit_merge_integrates_locally_preserves_shared_edits_cleans_and_finishes(
        run, web, repository, browser, already_done, monkeypatch):  # noqa: F811
    with monkeypatch.context() as clock:
        if already_done:
            from metaform import home
            clock.setattr(home, 'now', lambda: '2020-01-01T00:00:00Z')
        work, tree, _ = candidate(repository, done=already_done)
    previous_done = Store('proj').ticket(work.id).work.done
    (repository / 'README.md').write_text('Shared staged edit.\n', encoding='utf-8')
    git(repository, 'add', 'README.md')
    (repository / 'draft.txt').write_text('Shared untracked draft.\n', encoding='utf-8')
    staged = git(repository, 'diff', '--cached')
    page = board_page(browser, web)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        card_of(page, work).locator('.lead').click()
        page.locator('#ticketDetail input[name=title]').fill('Unsaved title')
        page.locator('#ticketDetail textarea[name=task]').fill('Unsaved task text.')
        with page.expect_response(merge_response) as response:
            page.locator('#ticketDetail').get_by_role('button', name='Merge', exact=True).click()
        assert response.value.status == 200, response.value.text()
        assert response.value.json()['merged'] and response.value.json()['done']
        page.wait_for_function('() => !document.querySelector("#ticketDetail .ticket-merge")')
        assert page.locator('#ticketDetail input[name=title]').input_value() == 'Unsaved title'
        assert page.locator('#ticketDetail textarea[name=task]').input_value() == 'Unsaved task text.'
        assert page.locator('#ticketDetail .board-column').inner_text() == '· done'
        assert (repository / 'feature.txt').read_text(encoding='utf-8') == 'Ticket feature.\n'
        assert f'Metaform-Ticket: {work.id}' in git(repository, 'log', '-1', '--format=%B')
        assert not tree.exists()
        assert git(repository, 'diff', '--cached') == staged
        assert (repository / 'draft.txt').read_text(encoding='utf-8') == 'Shared untracked draft.\n'
        current = Store('proj').ticket(work.id).work
        assert current.done and current.resolution == 'Implementation verified.'
        if already_done:
            assert current.done == previous_done
        page.locator('#ticketDetail button[type=submit]').click()
        page.wait_for_function('() => document.querySelector("#ticketDetail .ticket-main [role=status]")'
                               '.textContent === "Saved."')
        assert Store('proj').ticket(work.id).work.task == 'Unsaved task text.'
        assert not errors, errors
    finally:
        page.close()


def test_conflict_stays_visible_without_closing_or_removing_saved_candidate(
        run, web, repository, browser):  # noqa: F811
    work, tree, saved = candidate(repository, path='README.md', text='Ticket replacement.\n')
    (repository / 'README.md').write_text('Conflicting main replacement.\n', encoding='utf-8')
    git(repository, 'commit', '-qam', 'Conflicting main edit')
    page = board_page(browser, web)
    try:
        with page.expect_response(merge_response) as response:
            card_of(page, work).get_by_role('button', name='Merge', exact=True).click()
        assert response.value.status in (200, 409), response.value.text()
        assert not response.value.json()['merged']
        card_of(page, work).locator('.integration-reason').filter(has_text='conflict').wait_for()
        assert not Store('proj').ticket(work.id).work.done
        assert tree.is_dir()
        assert git(tree, 'rev-parse', 'HEAD') == saved['head']
        assert (repository / 'README.md').read_text(encoding='utf-8') == 'Conflicting main replacement.\n'
    finally:
        page.close()


def test_dirty_ticket_worktree_offers_cleanup_recovery_without_remerging(
        run, web, repository, browser):  # noqa: F811
    work, tree, _ = candidate(repository)
    draft = tree / 'unsaved.txt'
    draft.write_text('Preserve this draft.\n', encoding='utf-8')
    page = board_page(browser, web)
    try:
        with page.expect_response(merge_response) as response:
            card_of(page, work).get_by_role('button', name='Merge', exact=True).click()
        assert response.value.status == 200, response.value.text()
        assert response.value.json()['merged']
        card_of(page, work).get_by_role('button', name='Clean worktree', exact=True).wait_for()
        assert draft.read_text(encoding='utf-8') == 'Preserve this draft.\n'
        assert card_of(page, work).locator('.integration-reason').inner_text()
        integrated_head = git(repository, 'rev-parse', 'HEAD')
        draft.unlink()
        with page.expect_response(merge_response) as response:
            card_of(page, work).get_by_role('button', name='Clean worktree', exact=True).click()
        assert response.value.status == 200, response.value.text()
        assert response.value.json()['done']
        page.wait_for_function('id => !document.querySelector(`.card[data-id="${id}"] .ticket-cleanup`)', arg=work.id)
        assert not tree.exists()
        assert git(repository, 'rev-parse', 'HEAD') == integrated_head
        assert Store('proj').ticket(work.id).work.done
    finally:
        page.close()


def test_request_disables_card_and_inspector_across_redraws_and_pins_project(
        run, web, repository, browser):  # noqa: F811
    work, _, saved = candidate(repository)
    page = board_page(browser, web)
    requests = []
    page.route('**/api/ticket-merge', lambda route: requests.append(route))
    try:
        card_of(page, work).locator('.lead').click()
        page.locator('#ticketDetail .ticket-merge').wait_for()
        page.evaluate("async () => { (await import('/page/app/core/reads.js')).S.project = 'another-project'; }")
        page.locator('#ticketDetail .ticket-merge').click()
        assert len(requests) == 1
        body = requests[0].request.post_data_json
        assert body['project'] == 'proj' and body['work_id'] == work.id and body['head'] == saved['head']
        assert 'base' in body
        assert page.locator('#ticketDetail .ticket-merge').is_disabled()
        assert card_of(page, work).locator('.ticket-merge').is_disabled()
        previous_card = card_of(page, work).element_handle()
        page.evaluate("async id => { const s = await import('/page/app/core/reads.js'); s.S.project = 'proj'; "
                      "const refs = await import('/page/app/board/refs.js'); "
                      "refs.B.tickets.find(ticket => ticket.id === id).note = 'Redrawn while merging.'; "
                      "(await import('/page/app/board/board.js')).drawBoard(); "
                      "document.querySelectorAll('.ticket-merge').forEach(button => button.click()); }", work.id)
        assert previous_card is not None and previous_card.evaluate('card => !card.isConnected')
        assert card_of(page, work).locator('.ticket-merge').is_disabled()
        assert len(requests) == 1
        requests[0].fulfill(status=409, json={'why': 'Candidate changed. Reload this ticket.'})
        page.locator('#ticketDetail [role=alert]').filter(has_text='Candidate changed.').wait_for()
        assert page.locator('#ticketDetail .ticket-merge').is_enabled()
        assert not Store('proj').ticket(work.id).work.done
    finally:
        page.close()
