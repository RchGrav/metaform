"""Full Auto reads selection inputs once and preserves ticket selection rules."""
import json
import re
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
    run('map', 'work', 'op=edit', f'id={second}', 'eligible=["antigravity"]', cwd=dispatch.folder)
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
    monkeypatch.setattr(module, 'run_reserved', lambda ctx, reservation, *_, **__: start(ctx))
    monkeypatch.setattr(recovery, 'recover', lambda ctx: {'released': []})
    result = module.autostart(context('dispatch', dispatch.folder, project='proj'))
    assert result['started'] == [{'id': first, 'agent': 'claude'}, {'id': second, 'agent': 'antigravity'}]
    # one read decides there is something to start, and one inside the write transaction counts and reserves
    assert calls['work'] == 2, 'selection must not reread work to obtain map settings'


@pytest.mark.req('QUAL-015')
def test_a_pass_with_nothing_to_start_reads_once_and_takes_no_write_lock(dispatch, run, monkeypatch):  # noqa: F811
    """UX review round 1, runaway F3: with every slot in use, a pass of the agent starter is one read of the open
    tickets; it reconciles no ticket's progress, and opens no write transaction on the work store."""
    from metaform.data import Store
    from metaform.module import context
    from metaform.modules import dispatch as module
    from metaform.modules.dispatch import progress, recovery

    run('set', '--dispatch-autostart', '--dispatch-agents=1', cwd=dispatch.folder)
    for number in range(20):
        dispatch.store.add_work(dispatch.node, 'unbuilt', task=f'Ticket {number}')
    monkeypatch.setattr(recovery, 'recover', lambda ctx: {'released': []})
    monkeypatch.setattr(module, 'run_reserved', lambda ctx, reservation, *_, **__: dict(ctx.nouns))
    dispatch.store.take_work(dispatch.id, by='claude 0123456789abcdef')  # the one slot is in use
    # held as the admission gate counts it, by a live runner in the ledger (integration wave 2: the gate counts the
    # runners that run, not the tickets taken)
    import os
    holder = module.ledger() / f'{os.getpid()}.json'
    holder.parent.mkdir(parents=True, exist_ok=True)
    holder.write_text(json.dumps({'pid': os.getpid(), 'born': recovery.identity(os.getpid()) or '',
                                  'project': dispatch.store.project_id, 'work_id': dispatch.id, 'kind': 'worker'}))
    calls = Counter()
    atomic, work = Store.atomic, Store.__getattr__

    def counted(self, name):
        method = work(self, name)
        if name != 'work':
            return method
        def read(*args, **kwargs):
            calls['work'] += 1
            return method(*args, **kwargs)
        return read

    def locked(self):
        calls['atomic'] += 1
        return atomic(self)

    monkeypatch.setattr(Store, '__getattr__', counted)
    monkeypatch.setattr(Store, 'atomic', locked)
    monkeypatch.setattr(progress, 'refresh', lambda *args: calls.update(['refresh']))
    result = module.start_work(context('dispatch', dispatch.folder, project='proj'), dispatch.store, {})
    assert result['started'] == []
    assert (calls['work'], calls['atomic'], calls['refresh']) == (1, 0, 0), calls


def test_session_verification_reuses_the_unfiltered_open_work_snapshot(dispatch, monkeypatch):  # noqa: F811
    from metaform.data import Store
    from metaform.modules import dispatch as module

    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('agent_sessions', {'session_id': 'live', 'work_id': dispatch.id, 'agent': 'codex',
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
    monkeypatch.setattr(module, 'run_reserved', lambda ctx, reservation, *_, **__: launched.append(ctx.nouns['id']) or {})
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
    """Full Auto unchecked: a runner that finishes leaves the waiting ticket waiting."""
    from metaform.modules.dispatch.tests.test_dispatch import LIMIT

    second = dispatch.store.add_work(dispatch.node, 'unbuilt', task='Second ticket').id
    dispatch.start('done')
    assert dispatch.process.wait(LIMIT) == 0, dispatch.process.stderr.read().decode()
    assert dispatch.store.ticket(second).work.taken is None


def _passes(dispatch, monkeypatch):  # noqa: F811
    """One pass of the agent starter, as autostart runs it, with the launch stubbed: the tickets it reserved."""
    from metaform.module import context
    from metaform.modules import dispatch as module
    from metaform.modules.dispatch import recovery

    monkeypatch.setattr(recovery, 'recover', lambda ctx: {'released': []})
    monkeypatch.setattr(module, 'run_reserved', lambda ctx, reservation, *_, **__: dict(ctx.nouns))
    return lambda: [one['id'] for one in module.autostart(context('dispatch', dispatch.folder, project='proj'))['started']]


@pytest.mark.req('VIEW-045')
def test_a_held_ticket_waits_in_backlog_for_the_person_and_autostart_never_starts_it(dispatch, run,  # noqa: F811
                                                                                    monkeypatch):
    """UX review round 1, orchestrator F5: held=true put a ticket in Backlog, and autostart started it after To do."""
    run('set', '--dispatch-autostart', '--dispatch-agents=5', cwd=dispatch.folder)
    held = dispatch.store.add_work(dispatch.node, 'unbuilt', task='Planned, held', held=True).id
    kept = dispatch.store.add_work(dispatch.node, 'unbuilt', task='Held from agents').id
    run('map', 'work', 'op=edit', f'id={kept}', 'hold=true', cwd=dispatch.folder)
    started = _passes(dispatch, monkeypatch)
    assert started() == [dispatch.id], 'only the To do ticket starts'
    assert dispatch.store.ticket(held).work.taken is None and dispatch.store.ticket(held).work.column == 'backlog'
    run('map', 'work', 'op=move', f'id={held}', 'column=todo', cwd=dispatch.folder)  # the person releases it
    assert started() == [held]


@pytest.mark.req('VIEW-042')
def test_a_ticket_after_another_starts_only_once_that_one_is_done(dispatch, run, monkeypatch):  # noqa: F811
    """UX review round 1, orchestrator F6: a plan's order holds; with five slots, B waits on A."""
    run('set', '--dispatch-autostart', '--dispatch-agents=5', cwd=dispatch.folder)
    second = dispatch.store.add_work(dispatch.node, 'unbuilt', task='After the first').id
    said = run('map', 'work', 'op=edit', f'id={second}', f'after_work=["{dispatch.id}"]', '--json',
               cwd=dispatch.folder).stdout
    assert json.loads(said)['map']['after_work'] == [dispatch.id]
    started = _passes(dispatch, monkeypatch)
    assert started() == [dispatch.id]
    assert dispatch.store.ticket(second).work.taken is None
    refused = run('dispatch', 'start', second, 'claude', cwd=dispatch.folder, ok=False)
    said = refused.stderr + refused.stdout
    # both tickets named by their handle and title, never by 32-hex ids (round 2, held-and-signals F6)
    assert refused.returncode != 0 and '"After the first" waits on code.engine#1 "Write notes.txt"' in said, said
    assert not re.search('[0-9a-f]{32}', said), said
    dispatch.store.finish_work(dispatch.id, 'Done.', 'It is done.')
    assert started() == [second], 'the next pass starts what the done ticket freed'


@pytest.mark.req('VIEW-045')
def test_a_ticket_an_agent_writes_is_held_so_no_work_starts_its_own_successor(dispatch, run):  # noqa: F811
    """UX review round 1, runaway F5: with hold_agent_tickets on, a ticket written by an agent of Metaform waits in
    Backlog for the person; off, the default since 2026-10-18, it goes on the board ready, so a project heals itself."""
    ready = json.loads(run('map', 'work', 'op=add', f'node=element:{dispatch.node.id}', 'task=Fix it', 'title=Fix it',
                           '--json', cwd=dispatch.folder, env={'METAFORM_ROLE': 'system'}).stdout)
    assert ready['held'] is False, ready
    run('set', '--hold-agent-tickets', cwd=dispatch.folder)
    said = json.loads(run('map', 'work', 'op=add', f'node=element:{dispatch.node.id}', 'task=Follow up',
                          'title=Follow up', '--json', cwd=dispatch.folder, env={'METAFORM_ROLE': 'system'}).stdout)
    assert said['held'] is True, said
    assert 'waits in Backlog' in json.dumps(said)
    mine = json.loads(run('map', 'work', 'op=add', f'node=element:{dispatch.node.id}', 'task=Mine', 'title=Mine',
                          '--json', cwd=dispatch.folder, env={'METAFORM_ROLE': ''}).stdout)
    assert mine['held'] is False, "the person's own ticket goes to To do"


@pytest.mark.req('VIEW-045')
def test_a_held_ticket_is_released_only_by_the_person_whatever_path_an_agent_takes(dispatch, run):  # noqa: F811
    """UX review round 2, held-and-signals F3 and F4: a sentinel moved its own held proposal to To do and autostart
    started it, an intake agent started one with dispatch start, a system agent edited held=false, and an agent with
    METAFORM_ROLE cleared wrote an unheld ticket. Releasing is the person's decision: their terminal, or the page."""
    run('set', '--agents-ask-first', cwd=dispatch.folder)  # these check asking, off by default since 2026-10-18
    folder = dispatch.folder
    run('set', '--hold-agent-tickets', cwd=folder)  # the person asks to approve what agents write
    # every identity name the runner sets says an agent writes, not the role alone
    cleared = json.loads(run('map', 'work', 'op=add', f'node=element:{dispatch.node.id}', 'task=Proposal',
                             'title=Proposal', '--json', cwd=folder,
                             env={'METAFORM_ROLE': '', 'METAFORM_SESSION': 's-1'}).stdout)
    assert cleared['held'] is True, cleared
    held = cleared['id']
    run('map', 'work', 'op=edit', f'id={dispatch.id}', 'hold=true', cwd=folder)  # the person holds this one
    calls = (('map', 'work', 'op=move', f'id={held}', 'column=todo'),
             ('map', 'work', 'op=move', f'id={held}', 'column=doing'),
             ('map', 'work', 'op=edit', f'id={held}', 'held=false'),
             ('map', 'work', 'op=take', f'id={held}'),
             ('dispatch', 'start', held, 'claude'),
             ('map', 'work', 'op=edit', f'id={dispatch.id}', 'hold=false'),
             ('dispatch', 'start', dispatch.id, 'claude'))
    for role in ('sentinel', 'talk', 'intake', 'system'):
        for call in calls:
            refused = run(*call, cwd=folder, env={'METAFORM_ROLE': role}, ok=False)
            said = refused.stdout + refused.stderr
            assert refused.returncode != 0 and "the person's decision" in said, (role, call, said)
            assert '"Proposal"' in said or '"Write notes.txt"' in said, said  # named as the person reads it
    record = dispatch.store.ticket(held).work
    assert record.held and record.taken is None and dispatch.store.ticket(dispatch.id).work.taken is None
    # the person releases it at their own terminal, with no --confirm; their hold's letting go is theirs too
    moved = json.loads(run('map', 'work', 'op=move', f'id={held}', 'column=todo', '--json', cwd=folder).stdout)
    assert moved['held'] is False
    let_go = json.loads(run('map', 'work', 'op=edit', f'id={dispatch.id}', 'hold=false', '--json', cwd=folder).stdout)
    assert let_go['map']['hold'] is False
    # what an agent may still do with a held ticket: read it, note it, and put it back in Backlog
    again = run('map', 'work', 'op=edit', f'id={held}', 'held=true', 'note=Seen', cwd=folder,
                env={'METAFORM_ROLE': 'system'})
    assert again.returncode == 0 and dispatch.store.ticket(held).work.held


@pytest.mark.req('BASE-052')
def test_a_glyphs_next_ticket_is_never_one_waiting_on_an_open_ticket(dispatch, run):  # noqa: F811
    from metaform.module import context
    from metaform.modules import dispatch as module

    held = dispatch.store.add_work(dispatch.node, 'unbuilt', task='Held', held=True).id
    waiting = dispatch.store.add_work(dispatch.node, 'unbuilt', task='Waiting').id
    ready = dispatch.store.add_work(dispatch.node, 'unbuilt', task='Ready').id
    for one in (held, waiting, ready):
        run('map', 'work', 'op=edit', f'id={one}', 'glyph=kite', cwd=dispatch.folder)
    run('map', 'work', 'op=edit', f'id={waiting}', f'after_work=["{dispatch.id}"]', cwd=dispatch.folder)
    ctx = context('dispatch', dispatch.folder, project='proj')
    found = module.next_ticket(ctx, dispatch.store, 'kite', agent='claude', exclude=(dispatch.id,))
    assert found is not None and found.id == ready


def test_under_full_auto_only_the_active_board_starts(dispatch, run, monkeypatch):  # noqa: F811
    """2026-10-21: boards set work aside. Full Auto on, two boards, one active: a pass of the agent starter starts the
    active board's ticket and leaves the other board's waiting, untaken; activating the other board turns it round."""
    run('set', '--dispatch-autostart', '--dispatch-agents=5', cwd=dispatch.folder)
    run('map', 'boards', 'op=add', 'name=next', cwd=dispatch.folder)
    on_next = dispatch.store.add_work(dispatch.node, 'unbuilt', task='On the active board').id
    run('map', 'work', 'op=edit', f'id={on_next}', 'board=next', cwd=dispatch.folder)
    run('set', '--board', 'next', cwd=dispatch.folder)
    started = _passes(dispatch, monkeypatch)
    assert started() == [on_next], 'only the active board starts under Full Auto'
    assert dispatch.store.ticket(dispatch.id).work.taken is None, 'the first board is set aside'
    run('set', '--board=', cwd=dispatch.folder)  # the first board active again
    assert started() == [dispatch.id], 'the board activated starts; the one set aside waits'
