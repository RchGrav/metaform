"""Dispatch signals in existing transcript storage, without upgrading beneath active runners."""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, cast

from metaform.data import Store
from metaform.module import Context


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
        kept = tx.get('lines', {'session_id': session_id, 'name': key})
        if kept is not None:
            tx.update('lines', {'session_id': session_id, 'name': key}, {'text': text})
            return key, int(kept['seq'])
    later = tx.rows('lines', {'session_id': session_id}, by=('session_id', 'seq'), after=json.dumps([known, '']),
                    limit=0).results
    seq = max((int(row['seq']) for row in later), default=known) + 1
    name = key or f'line:{seq}'
    while not key and tx.get('lines', {'session_id': session_id, 'name': name}) is not None:
        seq += 1
        name = f'line:{seq}'
    tx.insert('lines', {'session_id': session_id, 'name': name, 'work_id': work_id, 'kind': kind, 'text': text,
                        'seq': seq})
    return name, seq


def record(store: Store, signal: str, *, work_id: str = '', session_id: str = '', key: str = '',
           active: bool = True, **details: Any) -> dict[str, Any] | None:
    """Keep one signal per source/key; repeated evidence does not raise duplicate events."""
    own = own_store(store)
    source = session_id or f'work:{work_id}'
    name = f'signal:{signal}:{key}'
    with own.tables() as tx:
        previous = tx.rows('lines', {'session_id': source, 'name': name}, limit=1).results
        if previous and json.loads(previous[0]['text'])['active'] == active:
            return None
        if not previous and not active:
            return None
        value = {'signal': signal, 'module': 'dispatch', 'project': store.project_id,
                 'work_id': work_id, 'session_id': session_id or None, 'active': active,
                 'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), **details}
        text = json.dumps(value, ensure_ascii=False)
        if previous:
            tx.update('lines', {'session_id': source, 'name': name}, {'text': text})
        else:
            rows = tx.rows('lines', {'session_id': source}, limit=0).results
            seq = max((row['seq'] for row in rows), default=0) + 1
            tx.insert('lines', {'session_id': source, 'name': name, 'work_id': work_id,
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
                               'dispatch_tables': ['dispatch.lines'], 'signal': value})


def rows(store: Store, work_id: str | None = None, active: bool = True) -> list[dict[str, Any]]:
    own = own_store(store)
    with own.tables(write=False) as tx:
        rows = tx.rows('lines', {'work_id': work_id}, by=('work_id', 'seq'), limit=0).results if work_id else tx.rows(
            'lines', limit=0).results
    found = [json.loads(row['text']) for row in rows if row['kind'] == 'signal']
    return sorted((row for row in found if row['active'] == active),
                  key=lambda row: (row['at'], row['session_id'] or '', row['signal']))


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
    """Persist existing producers' raw events once; stored events already carry active state."""
    if 'active' in payload:
        return
    details = {key: value for key, value in payload.items()
               if key not in ('signal', 'module', 'project', 'work_id', 'session_id')}
    key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    value = record(ctx.require_store(), payload['signal'], work_id=payload.get('work_id', ''),
                   session_id=payload.get('session_id') or f"producer:{payload.get('module', '')}",
                   key=key, producer=payload.get('module'), **details)
    if value is not None:
        ctx.publish('map.changed', {'project': value['project'], 'tables': 'dispatch',
                                   'dispatch_tables': ['dispatch.lines'], 'signal': value})


def clear_permissions(ctx: Context, session_id: str) -> None:
    for value in rows(ctx.require_store()):
        if value['session_id'] == session_id and value['signal'] in ('permission-waiting', 'question-waiting'):
            # keyed by its request; a request with no question at a node, an intake agent's, has no message id
            request = value.get('request') or value['message_id']
            publish(ctx, value['signal'], work_id=value['work_id'], session_id=session_id, key=request,
                    active=False, message_id=value.get('message_id'), request=request, reason='the session ended')
