"""What the board needs from the person's system agent, which owns it (the "Own the board" paragraph of the <system>
prompt): a ticket filed that can never start, a ticket that repeats an open one, a ticket whose runner died, and a
ticket an agent finished, whose work may clear fault lights. Each is kept as one signal, `BOARD`, raised once while
Full Auto is on, and the system agent takes every one waiting into its inbox, `Session.board`: a note in its thread
saying it whole, named by ticket and kind in the one inbox line its next turn carries (2026-10-19: one board turn listed
30 tickets in full); while none runs, one is started for them as dispatch_stay_connected's starter starts it, and its
opening turn carries the line. Nothing here runs on a timer: each comes from the change that made it.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from typing import Any, cast

from metaform.data import Store, StoreError
from metaform.module import Context

from .signals import announce
from .signals import record as keep

BOARD = 'board-needs'


def raised(ctx: Context, key: str, said: str, *, work_id: str = '', session_id: str = '', start: bool = True,
           urgent: bool = False, **details: Any) -> bool:
    """Keep one thing the board needs, `said` in a line, once for its `key`, while Full Auto is on, and tell the
    system agent; with `start`, a system agent is started for it when none runs. Whether it was raised now."""
    automatic = ctx.setting('dispatch_autostart')
    if not automatic and not urgent:
        return False
    store = ctx.require_store()
    value = keep(store, BOARD, work_id=work_id, session_id=session_id, key=key, once=True, signal_key=key,
                   said=said, urgent=urgent, **details)
    if value is None:
        return False
    announce(ctx, value)
    if start and automatic:
        from . import stay_connected
        try:
            stay_connected(ctx, store)
        except Exception as error:  # noqa: BLE001  the item waits for the next system agent either way
            import sys
            sys.stderr.write(f'Could not start the system agent for the board: {error}\n')
    return True


def fault_filed(payload: dict[str, Any], ctx: Context) -> None:
    """A canonical startup repair needs the existing system session, even with automatic workers off.

    Other filed faults enter the routine inbox. Group and recurrence identify one notification across processes.
    """
    if not payload.get('work_id') or 'group_id' not in payload:
        return
    work = str(payload['work_id'])
    store = ctx.require_store()
    numbered = store.numbers_of('work', [work]).get(work)
    ref = numbered[0] if numbered else work
    urgent = payload.get('source') == 'start'
    kind = 'start-fault' if urgent else 'fault'
    from . import prompt
    said = prompt('startup_fault', item=ref) if urgent else f'{ref}: fault filed'
    raised(ctx, f'{kind}:{payload["group_id"]}:{payload["occurrence"]}', said,
           work_id=work, urgent=urgent, start=urgent)


def waiting(store: Store) -> bool:
    """Whether anything the board needs waits for the system agent, read through the signals' index alone."""
    from .signals import rows
    return any(value.get('signal') == BOARD for value in rows(store))


def _episode(store: Store, board: str | None, fingerprint: str | None) -> str:
    """Persist stall episodes beside other dispatch bookkeeping, outside any agent transcript.

    Clearing the fingerprint records real execution. A later identical stall gets a new delivery key.
    Keeping the key before raising its signal makes a crash between the writes safely retryable.
    """
    from .signals import own_store
    bound = store.bound_base()
    where = {'session_id': f'board:{bound.id if bound else ""}:{board or ""}', 'name': 'stalled-state'}
    own = own_store(store)
    with own.tables(write=False) as tx:
        previous = tx.get('session_lines', where)
    state = json.loads(str(previous['text'])) if previous else {'fingerprint': None, 'episode': ''}
    if state['fingerprint'] == fingerprint:
        return str(state['episode'])
    with own.tables() as tx:
        previous = tx.get('session_lines', where)
        state = json.loads(str(previous['text'])) if previous else {'fingerprint': None, 'episode': ''}
        if state['fingerprint'] == fingerprint:
            return str(state['episode'])
        state = {'fingerprint': fingerprint, 'episode': secrets.token_hex(8) if fingerprint else ''}
        text = json.dumps(state)
        tx.concern(session_id=where['session_id'], kind='board-state')
        if previous:
            tx.update('session_lines', where, {'text': text})
        else:
            tx.insert('session_lines', {**where, 'work_id': '', 'kind': 'board-state', 'text': text, 'seq': 1})
    return str(state['episode'])


def worker_started(ctx: Context, work_id: str) -> None:
    """The mutating runner rearms attention before its turn, even if that turn ends before reconciliation."""
    if not ctx.setting('dispatch_autostart'):
        return
    from . import active_board, capacity_kind, set_aside, ticket_settings
    if capacity_kind(ctx, work_id, 'worker') == 'worker' and set_aside(ctx, work_id, ticket_settings(ctx)) is None:
        _episode(ctx.require_store(), active_board(ctx), None)


def stalled(ctx: Context) -> None:
    """Reconcile after the existing starter pass, never on routine thread or progress events.

    An unfinished active board with no executing ticket worker needs diagnosis, including when holds or
    prerequisites explain the wait. This requests attention only; existing orchestration owns every recovery.
    The evidence fingerprint survives delivery and restart, so unchanged stalls never start another turn.
    """
    if not ctx.setting('dispatch_autostart'):
        return
    from . import (
        SYSTEM_TASK,
        active_board,
        capacity_kind,
        launches,
        sessions,
        set_aside,
        summoned,
        ticket_settings,
        verified,
        waiting_on,
    )
    store = ctx.require_store()
    board = active_board(ctx)
    kept = ticket_settings(ctx)
    opened = store.work(open=True, limit=0).results
    unfinished = [record for record in opened if record.task != SYSTEM_TASK
                  and set_aside(ctx, record.id, kept) is None]
    if not unfinished:
        _episode(store, board, None)
        return
    ids = {record.id for record in unfinished}
    # Pending assignments are not sessions. Filter chats/helpers and other boards before any runner probes.
    rows = [row for row in sessions(store, verify=False) if row['work_id'] in ids and not summoned(row)
            and capacity_kind(ctx, str(row['work_id']), 'worker') == 'worker']
    checked = verified(store, rows, opened)
    if any(row['state'] == 'running' and row.get('activity') == 'working' for row in checked):
        _episode(store, board, None)
        return
    made = {row.get('pid') for row in rows}
    if any(entry.get('project') == store.project_id and entry.get('work_id') in ids and entry.get('pid') not in made
           and entry.get('kind') == 'worker' for entry in launches()):
        _episode(store, board, None)
        return  # a runner actually launching is different from an assignment waiting for launch
    latest = {str(row['work_id']): row for row in checked}
    evidence: list[dict[str, Any]] = []
    for record in sorted(unfinished, key=lambda one: one.id):
        row = latest.get(record.id, {})
        evidence.append({'work_id': record.id, 'held': bool(record.held), 'hold': bool(kept.get(record.id, {}).get('hold')),
                         'prerequisites': waiting_on(kept.get(record.id), {one.id for one in opened}),
                         'taken_by': record.taken_by,
                         'session': {key: row.get(key) for key in ('session_id', 'state', 'activity', 'how')}})
    bound = store.bound_base()
    fingerprint = hashlib.sha256(json.dumps([bound.id if bound else None, board, evidence],
                                            sort_keys=True).encode()).hexdigest()
    from . import prompt
    episode = _episode(store, board, fingerprint)
    raised(ctx, f'stalled:{fingerprint}:{episode}', prompt('stalled_board', board=board or 'first',
                                               count=str(len(unfinished))),
           actionable=True, board=board, tickets=evidence)


def _plain(title: str | None) -> str:
    """A title as compared for repeats: its words alone, lower case."""
    return ' '.join(re.findall(r'[a-z0-9]+', (title or '').lower()))


def changed(payload: dict[str, Any], ctx: Context) -> None:
    """map.changed: a ticket filed, the change's kind `filed`, that can never start, having no task and no trouble,
    broken or missing marker its agent could start from, or whose title repeats an open ticket's. Decided from the
    event first, so every other change reads nothing; then only the tickets it names are read, and the open tickets'
    titles only for a filing. The page's and the intake's own records are theirs by design (a stage drawn on a node),
    and the system agent's own filings are its own writes, so none of those raises anything."""
    kinds: Any = payload.get('kinds')
    named: Any = payload.get('work_ids')
    if not isinstance(kinds, list) or 'filed' not in kinds or not isinstance(named, list) or not named:
        return
    if ctx.surface == 'web' or os.environ.get('METAFORM_ROLE') in ('intake', 'system'):
        return
    if not ctx.setting('dispatch_autostart'):
        return
    from . import MARKERS, SYSTEM_TASK
    held = ctx.require_store()
    store = Store(held.project_id, base=payload['base_id']) if payload.get('base_id') else held
    try:
        filed = [record for record in store.work(ids=[str(one) for one in cast(list[Any], named)], limit=0).results
                 if record.done is None and record.task != SYSTEM_TASK]
        if not filed:
            return
        others = [record.id for record in store.work(open=True, limit=0).results]
        numbered = store.numbers_of('work', others)
    except StoreError:
        return
    titles: dict[str, str] = {}  # each open ticket's title as compared, to the first such ticket not filed now
    for one in others:
        if one in numbered and one not in named and _plain(numbered[one][1]):
            titles.setdefault(_plain(numbered[one][1]), one)
    for record in filed:
        ref, title = numbered.get(record.id, (record.id, None, None))[:2]
        if not (record.task or '').strip() and record.condition not in MARKERS:
            raised(ctx, f'taskless:{record.id}', f'{ref} "{title or ""}" was filed with no task, so no agent can '
                                                 'start it.', work_id=record.id)
        repeated = titles.get(_plain(title)) if _plain(title) else None
        if repeated is not None:
            raised(ctx, f'duplicate:{record.id}', f'{ref} "{title or ""}" repeats the open ticket '
                                                  f'{numbered[repeated][0]}, filed with the same title.',
                   work_id=record.id)


def died(ctx: Context, work_id: str, session_id: str, what: str) -> None:
    """A ticket whose runner died, after `what` came of it: back in To do, or resumed in place by the supervisor.
    Raised inside the agent starter's pass, which starts the system agent for it itself. The system agent's own
    runner, and a conversation on no ticket, are no ticket of the board's."""
    from . import SYSTEM_TASK
    store = ctx.require_store()
    try:
        found = store.work(ids=[work_id], limit=1).results
        numbered = store.numbers_of('work', [work_id]).get(work_id)
    except StoreError:
        return
    if not found or found[0].task == SYSTEM_TASK:
        return
    ref = numbered[0] if numbered else work_id
    raised(ctx, f'died:{session_id}', f'{ref}: its agent\'s runner died; {what}.', work_id=work_id,
           session_id=session_id, start=False)


def finished(ctx: Context, work_id: str) -> None:
    """An agent finished its ticket while Full Auto is on: its work may clear fault lights, which the system agent
    checks."""
    try:
        numbered = ctx.require_store().numbers_of('work', [work_id]).get(work_id)
    except StoreError:
        numbered = None
    ref, title = (numbered[0], numbered[1] or '') if numbered else (work_id, '')
    raised(ctx, f'finished:{work_id}', f'{ref} "{title}" was finished by its agent: check the fault lights its work '
                                       'may clear.', work_id=work_id)
