"""Dispatch signals in existing transcript storage, without upgrading beneath active runners."""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from metaform.data import Store
from metaform.module import Context


def record(store: Store, signal: str, *, work_id: str = '', session_id: str = '', key: str = '',
           active: bool = True, **details: Any) -> dict[str, Any] | None:
    """Keep one signal per source/key; repeated evidence does not raise duplicate events."""
    own = store if store.module == 'dispatch' else Store(store.project_id, module='dispatch')
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
        ctx.publish('signal.raised' if value['active'] else 'signal.cleared', value)
        ctx.publish('map.changed', {'project': value['project'], 'tables': 'dispatch',
                                   'dispatch_tables': ['dispatch.lines'], 'signal': value})


def rows(store: Store, work_id: str | None = None, active: bool = True) -> list[dict[str, Any]]:
    own = store if store.module == 'dispatch' else Store(store.project_id, module='dispatch')
    with own.tables(write=False) as tx:
        rows = tx.rows('lines', {'work_id': work_id}, by=('work_id', 'seq'), limit=0).results if work_id else tx.rows(
            'lines', limit=0).results
    found = [json.loads(row['text']) for row in rows if row['kind'] == 'signal']
    return sorted((row for row in found if row['active'] == active),
                  key=lambda row: (row['at'], row['session_id'] or '', row['signal']))


def read(ctx: Context) -> dict[str, Any]:
    """An observational read, available on CLI, MCP and web through the module verb."""
    return {'signals': rows(ctx.require_store(), ctx.nouns.get('id'), ctx.nouns.get('active', True))}


def requeued(payload: dict[str, Any], ctx: Context) -> None:
    publish(ctx, 'requeue', work_id=payload['work_id'], key=str(payload.get('revision', '')),
            previous=payload['previous'])


def rework_limit(payload: dict[str, Any], ctx: Context) -> None:
    """The rework counter owns its limit; dispatch records its announced result."""
    publish(ctx, 'rework-limit', work_id=payload['work_id'], key=str(payload.get('attempts', '')),
            attempts=payload.get('attempts'), limit=payload.get('limit'))


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
        if value['session_id'] == session_id and value['signal'] == 'permission-waiting':
            publish(ctx, 'permission-waiting', work_id=value['work_id'], session_id=session_id,
                    key=value['message_id'], active=False, message_id=value['message_id'], reason='the session ended')
