"""Autostart reads selection inputs once and preserves ticket selection rules."""
from collections import Counter

import pytest

from metaform.modules.dispatch.tests.test_dispatch import dispatch  # noqa: F401 -- fixture

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('VIEW-042')]


def test_autostart_reads_work_once_and_uses_bulk_settings(dispatch, run, monkeypatch):  # noqa: F811
    from metaform.data import Store
    from metaform.module import context
    from metaform.modules import dispatch as module
    from metaform.modules.dispatch import recovery

    run('set', '--dispatch-autostart', '--dispatch-agents=2', cwd=dispatch.folder)
    first = dispatch.id
    second = dispatch.store.add_work(dispatch.node, 'unbuilt', task='Second ticket').id
    held = dispatch.store.add_work(dispatch.node, 'unbuilt', task='Held ticket').id
    run('map', 'work', 'op=edit', f'id={held}', 'hold=true', cwd=dispatch.folder)
    run('map', 'work', 'op=edit', f'id={first}', 'eligible=["claude"]', 'glyph=kite', cwd=dispatch.folder)
    run('map', 'work', 'op=edit', f'id={second}', 'eligible=["gemini"]', cwd=dispatch.folder)
    calls = Counter()
    get = Store.__getattr__

    def counted(self, name):
        method = get(self, name)
        if name != 'work':
            return method
        def work(*args, **kwargs):
            calls['work'] += 1
            return method(*args, **kwargs)
        return work

    def start(ctx):
        calls['starts'] += 1
        return dict(ctx.nouns)

    monkeypatch.setattr(Store, '__getattr__', counted)
    monkeypatch.setattr(module, 'run_reserved', lambda ctx, reservation: start(ctx))
    monkeypatch.setattr(recovery, 'recover', lambda ctx: {'released': []})
    result = module.autostart(context('dispatch', dispatch.folder, project='proj'))
    assert result['started'] == [{'id': first, 'agent': 'claude'}, {'id': second, 'agent': 'gemini'}]
    assert calls['work'] == 1, 'selection must not reread work to obtain map settings'


def test_session_verification_reuses_the_unfiltered_open_work_snapshot(dispatch, monkeypatch):  # noqa: F811
    from metaform.data import Store
    from metaform.modules import dispatch as module

    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('sessions', {'session_id': 'live', 'work_id': dispatch.id, 'agent': 'codex',
                               'state': 'running', 'started': '2026-10-05', 'pid': 1, 'port': 1, 'token': 'test',
                               'seq': 1})
    opened = dispatch.store.work(open=True, limit=0).results
    seen = []
    monkeypatch.setattr(module, 'session_status', lambda store, row, *, done: seen.append(done) or row)
    monkeypatch.setattr(dispatch.store, 'work', lambda *args, **kwargs: pytest.fail('work was read again'))
    assert module.sessions(dispatch.store, open_work=opened)[0]['session_id'] == 'live'
    assert seen == [False]


@pytest.mark.req('BASE-052')
def test_autostart_without_page_starts_the_next_ticket_when_a_runner_finishes(dispatch, run):  # noqa: F811
    """No page is open: the runner whose ticket is done starts the waiting ticket itself, D-11."""
    from metaform.modules.dispatch.tests.test_dispatch import LIMIT, eventually, gone

    run('set', '--dispatch-autostart', '--dispatch-agents=1', cwd=dispatch.folder)
    second = dispatch.store.add_work(dispatch.node, 'unbuilt', task='Second ticket').id
    dispatch.start('done')
    assert dispatch.process.wait(LIMIT) == 0, dispatch.process.stderr.read().decode()
    row = eventually(lambda: next((item.extra for item in dispatch.items('session')
                                   if item.extra['work_id'] == second and item.extra['state'] == 'ended'), None))
    assert dispatch.store.ticket(second).work.done
    assert gone([row['pid']], LIMIT), 'the second runner ends once its ticket is done'


@pytest.mark.req('BASE-052')
def test_autostart_without_page_twice_at_once_fills_one_slot_once(dispatch, monkeypatch):  # noqa: F811
    """Two checks at once, a runner's and the page's, with one free slot: one ticket starts, since counting and
    reserving are one transaction. Each check waits at the count for the other; the lock lets only one in."""
    import threading

    from metaform.module import context
    from metaform.modules import dispatch as module

    dispatch.run('set', '--dispatch-autostart', '--dispatch-agents=1', cwd=dispatch.folder)
    second = dispatch.store.add_work(dispatch.node, 'unbuilt', task='Second ticket').id
    both = threading.Barrier(2)
    counted = module.sessions

    def sessions(*args, **kwargs):
        try:
            both.wait(1.0)  # both counts at once, as without the lock; with it the first waits alone
        except threading.BrokenBarrierError:
            pass
        return counted(*args, **kwargs)

    launched = []
    monkeypatch.setattr(module, 'sessions', sessions)
    monkeypatch.setattr(module, 'run_reserved', lambda ctx, reservation: launched.append(ctx.nouns['id']) or {})
    failed = []

    def check():
        try:
            module.autostart(context('dispatch', dispatch.folder, project='proj'))
        except Exception as error:  # noqa: BLE001  a check that fails is a failed test, not a thread's warning
            failed.append(error)

    checks = [threading.Thread(target=check) for _ in range(2)]
    for check in checks:
        check.start()
    for check in checks:
        check.join(30)
    assert not failed and len(launched) == 1, failed
    assert sum(1 for work_id in (dispatch.id, second) if dispatch.store.ticket(work_id).work.taken) == 1


@pytest.mark.req('BASE-052')
def test_autostart_without_page_off_starts_nothing_when_a_runner_finishes(dispatch, run):  # noqa: F811
    """Autostart agents unchecked: a runner that finishes leaves the waiting ticket waiting."""
    from metaform.modules.dispatch.tests.test_dispatch import LIMIT

    second = dispatch.store.add_work(dispatch.node, 'unbuilt', task='Second ticket').id
    dispatch.start('done')
    assert dispatch.process.wait(LIMIT) == 0, dispatch.process.stderr.read().decode()
    assert dispatch.store.ticket(second).work.taken is None
