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
    run('map', 'work', 'op=edit', f'id={held}', 'hold=true', 'hold_reason=Wait for release', cwd=dispatch.folder)
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
def test_autostart_without_page_starts_the_next_ticket_when_a_runner_finishes(dispatch, run,  # noqa: F811
                                                                            dispatch_runners):
    """One automatic admission starts both real workers through completion-driven refill, D-11."""
    import sys
    import threading

    from metaform import events
    from metaform.data import Store
    from metaform.modules import dispatch as module
    from metaform.modules.dispatch.tests.test_ticket_commit import git

    git(dispatch.folder, 'init', '-q', '-b', 'main')
    git(dispatch.folder, 'config', 'user.name', 'Test')
    git(dispatch.folder, 'config', 'user.email', 'test@example.com')
    (dispatch.folder / 'check_feature.py').write_text(
        "from pathlib import Path\nassert Path('feature.txt').read_text() == 'changed by the fake agent\\n'\n")
    git(dispatch.folder, 'add', 'check_feature.py')
    git(dispatch.folder, 'commit', '-qm', 'Verification fixture')
    baseline = git(dispatch.folder, 'rev-parse', 'HEAD')
    command = f'"{sys.executable}" check_feature.py'
    run('set', '--dispatch-autostart', '--dispatch-agents=1', '--dispatch-worktrees',
        f'--dispatch-test-command={command}', cwd=dispatch.folder)
    second = dispatch.store.add_work(dispatch.node, 'unbuilt', task='Second ticket').id
    wanted = {dispatch.id, second}
    finished = threading.Event()
    observed, errors = {}, []
    registered = set()

    def remember(row):
        if row.get('pid') and row['pid'] not in registered:
            registered.add(row['pid'])
            dispatch_runners.append((row, dispatch.folder, dispatch.log))

    def observe(payload):
        if payload.get('project') != dispatch.store.project_id:
            return
        if payload.get('work_ids') and wanted.isdisjoint(payload['work_ids']):
            return
        try:
            for item in dispatch.items('session'):
                row = item.extra
                if row['work_id'] in wanted:
                    observed[row['work_id']] = row
                    remember(row)
            if wanted <= observed.keys() and all(
                    observed[work_id]['state'] == 'ended' and dispatch.store.ticket(work_id).work.done
                    for work_id in wanted):
                finished.set()
        except Exception as error:  # noqa: BLE001 - Deliver listener failures to the test thread.
            errors.append(str(error))
            finished.set()

    listener = events.listen('web', observe)
    try:
        result = json.loads(run('dispatch', 'autostart', '--json', cwd=dispatch.folder,
                                env=dispatch.env('done', FAKE_ACP_EDIT='feature.txt')).stdout)
        for started in result['started']:
            remember(started)
        assert [one['work_id'] for one in result['started']] == [dispatch.id], result
        assert finished.wait(30), {
            'sessions': observed,
            'completion': [entry for entry in dispatch.entries() if 'done' in entry]}
        assert errors == []
        assert wanted <= observed.keys()
        assert all(dispatch.store.ticket(work_id).work.done for work_id in wanted)
        assert observed[dispatch.id]['ended'] <= observed[second]['started']
        with Store(dispatch.store.project_id, module='dispatch').tables(write=False) as tx:
            saved = [tx.get('merges', {'work_id': work_id}) for work_id in wanted]
        for candidate in saved:
            assert candidate['state'] == 'merged' and not candidate['reason'], candidate
            assert candidate['evidence']['verification']['passed'] is True
            assert candidate['evidence']['verification']['command'] == command
            if candidate['work_id'] == dispatch.id:
                assert candidate['evidence']['artifacts'] == ['feature.txt']
            else:
                assert set(candidate['evidence']['artifacts']) <= {'feature.txt'}
            assert f'Metaform-Ticket: {candidate["work_id"]}' in git(
                dispatch.folder, 'show', '-s', '--format=%B', candidate['head'])
            assert git(dispatch.folder, 'merge-base', '--is-ancestor', baseline, candidate['head']) == ''
            integration = git(dispatch.folder, 'log', '--format=%H', '--fixed-strings', '--grep',
                              f'Metaform-Ticket: {candidate["work_id"]}').splitlines()
            assert integration, 'The saved ticket has no local integration commit.'
            assert git(dispatch.folder, 'show', f'{candidate["head"]}:feature.txt') == \
                'changed by the fake agent'
        assert git(dispatch.folder, 'rev-parse', 'HEAD') != baseline
        assert git(dispatch.folder, 'merge-base', '--is-ancestor', baseline, 'HEAD') == ''
        assert git(dispatch.folder, 'show', 'HEAD:feature.txt') == 'changed by the fake agent'
        assert git(dispatch.folder, 'remote') == ''
    finally:
        listener.close()
        # A failure can precede the session event. Include every detached runner before fixture teardown.
        for row in module.launches():
            if row.get('project') == dispatch.store.project_id and row.get('work_id') in wanted:
                remember(row)


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
    held = dispatch.store.add_work(dispatch.node, 'unbuilt', task='Planned, held', held=True,
                                   hold_reason='Wait for release').id
    kept = dispatch.store.add_work(dispatch.node, 'unbuilt', task='Held from agents').id
    run('map', 'work', 'op=edit', f'id={kept}', 'hold=true', 'hold_reason=Wait for release', cwd=dispatch.folder)
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
@pytest.mark.parametrize('identity', [
    {'METAFORM_ROLE': 'system'}, {'METAFORM_ROLE': 'sentinel'}, {'METAFORM_ROLE': 'intake'},
    {'METAFORM_ROLE': 'talk'}, {'METAFORM_ROLE': '', 'METAFORM_SESSION': 's-1'},
    {'METAFORM_ROLE': ''},
])
@pytest.mark.parametrize('reviewed', [False, True])
def test_agent_creation_never_adds_implicit_hold(dispatch, run, identity, reviewed):  # noqa: F811
    """Source identity, review state and a saved obsolete policy cannot hold new work."""
    from metaform import home
    home.save(home.path_key(dispatch.folder), 'map', 'hold_agent_tickets', [True], folder=dispatch.folder)
    ready = json.loads(run('map', 'work', 'op=add', f'node=element:{dispatch.node.id}',
                          'task=Fix it', 'title=Fix it', f'reviewed={str(reviewed).lower()}',
                          '--json', cwd=dispatch.folder, env=identity).stdout)
    assert ready['held'] is False, ready
    assert not ready.get('map', {}).get('hold'), ready
    assert ready['column'] == 'todo', ready


@pytest.mark.req('MAP-060')
@pytest.mark.parametrize('role', ['sentinel', 'talk', 'intake', 'system'])
def test_reason_based_unholding_needs_no_person_approval_but_explicit_start_does(dispatch, run, role):  # noqa: F811
    """Ordinary release stays available under ask-first without granting explicit start authority."""
    folder = dispatch.folder
    run('set', '--agents-ask-first', cwd=folder)
    identity = {'METAFORM_ROLE': role, 'METAFORM_SESSION': 'review-session'}
    for mode in ('held', 'backlog', 'hold'):
        record = dispatch.store.add_work(dispatch.node, 'unbuilt', task=f'Proposal {mode}', title=f'Proposal {mode}',
                                         held=mode != 'hold', hold_reason='Wait for prerequisite review')
        if mode == 'hold':
            run('map', 'work', 'op=edit', f'id={record.id}', 'hold=true',
                'hold_reason=Wait for prerequisite review', cwd=folder)
        refused = run('dispatch', 'start', record.id, 'claude', cwd=folder, env=identity, ok=False)
        said = refused.stdout + refused.stderr
        assert refused.returncode != 0 and "the person's decision" in said, said
        assert dispatch.store.ticket(record.id).work.taken is None
        call = ('op=move', 'column=todo') if mode == 'backlog' else ('op=edit', f'{mode}=false')
        released = json.loads(run('map', 'work', *call, f'id={record.id}', '--json',
                                  cwd=folder, env=identity).stdout)
        assert not released['held']
        assert not released.get('map', {}).get('hold')
        assert dispatch.store.ticket(record.id).work.taken is None


@pytest.mark.req('BASE-052')
def test_a_glyphs_next_ticket_is_never_one_waiting_on_an_open_ticket(dispatch, run):  # noqa: F811
    from metaform.module import context
    from metaform.modules import dispatch as module

    held = dispatch.store.add_work(dispatch.node, 'unbuilt', task='Held', held=True,
                                   hold_reason='Wait for release').id
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
