"""Dispatch signals: a signal is a line of the project's `signals`, whatever map is shown, saying the metaform it was
raised on, and a thread's own lines are in the project's `session_lines`, which no clear removes, PROJ-026. A signal
of a metaform the project no longer holds, cleared or removed, is not read; a restore that brings it back brings its
signals back with it."""
from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Sequence
from typing import Any, cast

from metaform.data import Store, StoreError
from metaform.module import Context

TABLE = 'signals'  # the project's table of signals, since dispatch's version 18
# the kind of change each of dispatch's tables carries on `map.changed`, `concerning`
KINDS = {'dispatch.lines': 'line', 'dispatch.signals': 'signal', 'dispatch.permissions': 'permission',
         'dispatch.sessions': 'session',
         'dispatch.spending': 'spend', 'dispatch.settings': 'session', 'dispatch.merges': 'merge',
         'dispatch.session_lines': 'line', 'dispatch.agent_sessions': 'session'}
# The tables a session's thread is in: its own lines, the project's since version 16, and the signals beside the map.
THREAD_TABLES = frozenset({'dispatch.session_lines', 'dispatch.lines'})


def concerning(work_id: str | None, session_id: str | None, dispatch_tables: Sequence[str] | None = None,
               signal: bool = False) -> dict[str, list[str]]:
    """What a dispatch write concerns, carried on its `map.changed` as the chassis carries a map write's, BASE-053:
    `work_ids` and `session_ids` the ticket and session it was for, and `kinds` when every table it names has one, so
    a runner of another session reads nothing for it. A ticket or session not given is left unknown."""
    about: dict[str, list[str]] = {}
    if work_id:
        about['work_ids'] = [work_id]
    if session_id:
        about['session_ids'] = [session_id]
    kinds: set[str | None] = {KINDS.get(table) for table in dispatch_tables or ()}
    if signal:
        kinds.add('signal')
    if (dispatch_tables or signal) and None not in kinds:
        about['kinds'] = sorted(kind for kind in kinds if kind is not None)
    return about


def own_store(store: Store) -> Store:
    """The dispatch module's own store for this project: the one given when it is already that."""
    if store.module == 'dispatch':
        return store
    bound = store.bound_base()
    return Store(store.project_id, base=bound.id if bound else None, module='dispatch')


def add_line(tx: Any, session_id: str, work_id: str, key: str | None, kind: str, text: str,
             known: int = 0) -> tuple[str, int]:
    """A line of a session's thread, written inside the caller's write transaction and numbered from the table, so
    every writer on the session, a runner, a second runner resuming it, a served session, takes the next number and
    none fails on a name another took, code.dispatcher.agent#12. A keyed line already kept is changed in place; any
    other takes the seq after the session's last, read from the rows past `known`, the last seq the writer saw.
    Returns its name and seq."""
    if key:
        kept = tx.get('session_lines', {'session_id': session_id, 'name': key})
        if kept is not None:
            tx.update('session_lines', {'session_id': session_id, 'name': key}, {'text': text})
            return key, int(kept['seq'])
    later = tx.rows('session_lines', {'session_id': session_id}, by=('session_id', 'seq'),
                    after=json.dumps([known, '']), limit=0).results
    seq = max((int(row['seq']) for row in later), default=known) + 1
    name = key or f'line:{seq}'
    while not key and tx.get('session_lines', {'session_id': session_id, 'name': name}) is not None:
        seq += 1
        name = f'line:{seq}'
    tx.insert('session_lines', {'session_id': session_id, 'name': name, 'work_id': work_id, 'kind': kind,
                                'text': text, 'seq': seq})
    return name, seq


# A peer note's delivery to one receiver, `dispatch note`, in the order it only ever moves forward: queued in the
# receiver's runner, delivered when the turn carrying it is sent, read when that turn ends, replied when the receiver
# answers it. A note no runner took is failed, which only a queued state becomes.
PEER_STATES = ('queued', 'delivered', 'read', 'replied')


def mark_peer(tx: Any, session_id: str, note_id: str, work_id: str, state: str,
              recipient_session: str | None = None) -> bool:
    """Set one receiver's delivery state on the copy of a peer note a thread keeps, `peer:<id>`, read and written in
    the caller's transaction so a sender's copy that several receivers mark keeps every mark; a state never goes back.
    False when that thread keeps no such note or the state is not newer."""
    row = tx.get('session_lines', {'session_id': session_id, 'name': f'peer:{note_id}'})
    if row is None:
        return False
    try:
        found: Any = json.loads(str(row['text']))
    except ValueError:
        return False
    if not isinstance(found, dict):
        return False
    value = cast(dict[str, Any], found)
    states = cast(dict[str, str], value.setdefault('states', {}))
    per_session = cast(dict[str, str], value.setdefault('session_states', {}))
    before = per_session.get(recipient_session) if recipient_session else states.get(work_id)
    rank = {name: place for place, name in enumerate(PEER_STATES)}
    if state == 'failed' and before not in (None, 'queued'):
        return False
    if state != 'failed' and before in rank and rank.get(state, -1) <= rank[before]:
        return False
    states[work_id] = state
    if recipient_session:
        per_session[recipient_session] = state
    tx.update('session_lines', {'session_id': session_id, 'name': f'peer:{note_id}'},
              {'text': json.dumps(value, ensure_ascii=False)})
    return True


def record(store: Store, signal: str, *, work_id: str = '', session_id: str = '', key: str = '',
           active: bool = True, once: bool = False, **details: Any) -> dict[str, Any] | None:
    """Keep one signal per source/key; repeated evidence does not raise duplicate events. `once` raises a key only
    the first time, so one a reader has taken and cleared is never raised again by a later report of the same thing."""
    own = own_store(store)
    source = session_id or f'work:{work_id}'
    name = f'signal:{signal}:{key}'
    bound = own.bound_base()
    if not active and bound is None:  # no metaform holds a signal to clear, and none is made for it
        return None
    with own.tables() as tx:
        previous = tx.rows(TABLE, {'session_id': source, 'name': name}, limit=1).results
        if previous and (once and active or json.loads(previous[0]['text'])['active'] == active):
            return None
        if not previous and not active:
            return None
        value = {'signal': signal, 'module': 'dispatch', 'project': store.project_id,
                 'work_id': work_id, 'session_id': session_id or None, 'active': active,
                 'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                 'base': bound.id if bound is not None else None, **details}
        text = json.dumps(value, ensure_ascii=False)
        tx.concern(work_id=work_id or None, session_id=session_id or None, kind='signal')
        if previous:
            tx.update(TABLE, {'session_id': source, 'name': name}, {'text': text})
        else:
            rows = tx.rows(TABLE, {'session_id': source}, limit=0).results
            seq = max((row['seq'] for row in rows), default=0) + 1
            tx.insert(TABLE, {'session_id': source, 'name': name, 'work_id': work_id,
                              'kind': 'signal', 'text': text, 'seq': seq})
    return value


def publish(ctx: Context, signal: str, **details: Any) -> None:
    value = record(ctx.require_store(), signal, **details)
    if value is not None:
        announce(ctx, value)


def announce(ctx: Context, value: dict[str, Any]) -> None:
    """Publish a signal already committed by its producer, outside that producer's transaction."""
    ctx.publish('signal.raised' if value['active'] else 'signal.cleared', value)
    bound = ctx.require_store().bound_base()
    ctx.publish('map.changed', {'project': value['project'], 'base_id': bound.id if bound else None, 'tables': 'dispatch',
                               'dispatch_tables': ['dispatch.lines'], 'signal': value,
                               **concerning(value.get('work_id'), value.get('session_id'), ['dispatch.lines'], True)})


def rows(store: Store, work_id: str | None = None, active: bool = True) -> list[dict[str, Any]]:
    """The signals of one ticket or of every ticket, read through the (kind, work_id) index alone, with what runners
    on older code raised beside a map carried in first, which costs nothing while their stores are unchanged."""
    from . import carry_conversations
    try:
        carry_conversations(own_store(store))
    except StoreError:  # a metaform that cannot be read now keeps what it holds of them until one can carry it
        pass
    with own_store(store).tables(write=False) as tx:
        return read_rows(tx, work_id, active)


def read_rows(tx: Any, work_id: str | None = None, active: bool = True, *,
              session_ids: Sequence[str] | None = None, work_ids: Sequence[str] = ()) -> list[dict[str, Any]]:
    """`rows`, read in the caller's transaction on dispatch's tables."""
    if session_ids is not None:
        rows = tx.rows_in(TABLE, 'session_id', [*session_ids, *(f'work:{ref}' for ref in work_ids)])
    else:
        rows = tx.rows(TABLE, {'kind': 'signal', **({'work_id': work_id} if work_id else {})}, by=('kind',),
                       limit=0).results
    found = [json.loads(row['text']) for row in rows]
    held = _held_bases(found)
    return sorted((row for row in found if row['active'] == active and (not row.get('base') or row['base'] in held)),
                  key=lambda row: (row['at'], row['session_id'] or '', row['signal']))


def _held_bases(found: Sequence[dict[str, Any]]) -> set[str]:
    """The ids of the metaforms the projects of these signals hold now, read once per project named."""
    from metaform import home
    held: set[str] = set()
    for project in {str(row.get('project') or '') for row in found if row.get('base')}:
        held.update(base.id for base in home.bases(project))
    return held


def read(ctx: Context) -> dict[str, Any]:
    """An observational read, available on CLI, MCP and web through the module verb; the waiting ones triaged by
    Jev when it is on, `triaged`."""
    active = ctx.nouns.get('active', True)
    found = rows(ctx.require_store(), ctx.nouns.get('id'), active)
    return {'signals': triaged(ctx, found) if active else found}


ASKED = ('permission-waiting', 'question-waiting')  # put to the person by the agent: always the person's, MAP-050
TRIAGE_LIMIT = 3.0  # seconds a read waits on Jev's triage before it answers in its own order


def triaged(ctx: Context, found: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The waiting signals, each marked `for` the person or an agent and the person's first, as Jev's triage
    decides when jev is on and its triage decision is chosen, H23. Triage orders and marks; it never hides one. A
    permission or a question the agent asked is the person's whatever Jev says. With Jev off, unsure or unreachable
    within TRIAGE_LIMIT, the signals are as they were, in their own order and unmarked."""
    if not found:
        return found
    from metaform import jev
    try:
        if jev.config(ctx.folder, 'triage') is None:
            return found
        said = {f's{n}': json.dumps({key: value for key, value in one.items()
                                     if key not in ('module', 'project', 'active', 'at')}, ensure_ascii=False)
                for n, one in enumerate(found)}
        asked = [f's{n}' for n, one in enumerate(found) if one.get('signal') in ASKED]
        with jev.within(TRIAGE_LIMIT):
            decision = jev.triage(ctx.folder, said, questions=asked)
    except Exception:  # noqa: BLE001  a decision that fails leaves the list as it is
        return found
    if decision is None:
        return found
    sorted_to = cast(dict[str, str], decision.answer)
    marked = [{**one, 'for': sorted_to.get(f's{n}', 'person')} for n, one in enumerate(found)]
    return sorted(marked, key=lambda one: one['for'] != 'person')


def requeued(payload: dict[str, Any], ctx: Context) -> None:
    from .progress import requeued as account_requeue
    account_requeue(payload, ctx)
    publish(ctx, 'requeue', work_id=payload['work_id'], key=str(payload.get('revision', '')),
            previous=payload['previous'])


def rework_limit(payload: dict[str, Any], ctx: Context) -> None:
    """The rework counter owns its limit; dispatch records its announced result."""
    if 'active' in payload:  # the counter committed its signal with its count; the event announces that result
        return
    publish(ctx, 'rework-limit', work_id=payload['work_id'], key=str(payload.get('epoch') or payload.get('attempts', '')),
            attempts=payload.get('attempts'), limit=payload.get('limit'),
            **({'epoch': payload['epoch']} if payload.get('epoch') else {}))


def collect(payload: dict[str, Any], ctx: Context) -> None:
    """Persist existing producers' raw events once; stored events already carry active state. A producer that names
    its signal's `key` keeps it as `signal_key`, so a reader can clear it, and clears it itself with `clear` true."""
    if 'active' in payload:
        return
    named = str(payload.get('key') or '')
    details = {key: value for key, value in payload.items()
               if key not in ('signal', 'module', 'project', 'work_id', 'session_id', 'key', 'clear')}
    key = named or hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    value = record(ctx.require_store(), payload['signal'], work_id=payload.get('work_id', ''),
                   session_id=payload.get('session_id') or f"producer:{payload.get('module', '')}",
                   key=key, active=not (named and payload.get('clear')), producer=payload.get('module'),
                   **({'signal_key': named} if named else {}), **details)
    if value is not None:
        ctx.publish('map.changed', {'project': value['project'], 'tables': 'dispatch',
                                   'dispatch_tables': ['dispatch.lines'], 'signal': value,
                                   **concerning(value.get('work_id'), value.get('session_id'), ['dispatch.lines'],
                                                True)})


# A feature the person set up is not working, raised by the module that serves it with what the person set up,
# `set_up`, the feature in words, `feature`, how to look at it, `look`, and its findings, `report`: the person's system
# agent takes it as a turn and brings it up with them, `Runner.troubles`. Any module may raise it.
SETUP_NOT_WORKING = 'setup-not-working'


def taken(store: Store, value: dict[str, Any]) -> bool:
    """Clear a producer's keyed signal once a reader has taken it; False when another reader took it first."""
    return record(store, str(value['signal']), work_id=str(value.get('work_id') or ''),
                  session_id=str(value.get('session_id') or ''), key=str(value.get('signal_key') or ''),
                  active=False, **{name: one for name, one in value.items()
                                   if name not in ('signal', 'module', 'project', 'work_id', 'session_id', 'active',
                                                   'at')}) is not None


def clear_permissions(ctx: Context, session_id: str) -> None:
    for value in rows(ctx.require_store()):
        if value['session_id'] == session_id and value['signal'] in ('permission-waiting', 'question-waiting'):
            # keyed by its request; a request with no question at a node, an intake agent's, has no message id
            request = value.get('request') or value['message_id']
            publish(ctx, value['signal'], work_id=value['work_id'], session_id=session_id, key=request,
                    active=False, message_id=value.get('message_id'), request=request, reason='the session ended')
