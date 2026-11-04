"""Relay ACP permission requests unchanged to the person and wait for their answer.

The engine and the page run in separate processes. The existing Metaform change
relay wakes the request after the page stores an answer. No permission decision
is inferred from the agent, tool name, path, or session phase.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Callable
from typing import Any, cast

from metaform import events
from metaform.data import DataConnection

from . import store

SCHEMA = """CREATE TABLE IF NOT EXISTS permission_requests(
  discussion INTEGER NOT NULL, request TEXT NOT NULL, payload TEXT NOT NULL,
  state TEXT NOT NULL, chosen TEXT,
  PRIMARY KEY (discussion, request))"""


def topic(number: int) -> str:
    return f'roundtables:permissions:{number}'


def _event(db: DataConnection, number: int, payload: dict[str, Any]) -> None:
    """Store the request's state and its visible event in the same transaction."""
    latest = int(db.execute('SELECT COALESCE(MAX(number), 0) FROM events WHERE discussion=?',
                            (number,)).fetchone()[0])
    store.insert(db, 'events', {'discussion': number, 'number': latest + 1, 'kind': 'permission',
                               'text': json.dumps(payload, ensure_ascii=False), 'seat': payload['seat'],
                               'created': store.stamp()})


def _row(db: DataConnection, number: int, request_id: str) -> dict[str, Any]:
    found = db.execute('SELECT payload, state, chosen FROM permission_requests WHERE discussion=? AND request=?',
                       (number, request_id)).fetchone()
    if found is None:
        raise ValueError(f'No permission request {request_id} waits on roundtable {number}.')
    return {**cast(dict[str, Any], json.loads(found['payload'])),
            'state': str(found['state']), 'chosen': found['chosen']}


def get(number: int, request_id: str) -> dict[str, Any]:
    with store.connect() as db:
        db.execute(SCHEMA)
        return _row(db, number, request_id)


def _opened(number: int, position: int, request_id: str, given: dict[str, Any]) -> dict[str, Any]:
    seats = store.seats(number)
    seat = next((one for one in seats if int(one['position']) == position), None)
    payload = {**given, 'request': request_id, 'position': position,
               'seat': str(seat['id']) if seat else 'minutes' if position == -4 else 'agent',
               'name': str(seat['name']) if seat else 'Minutes' if position == -4 else 'Agent',
               'state': 'waiting', 'chosen': None}
    with store.connect() as db:
        db.execute(SCHEMA)
        if db.execute('SELECT 1 FROM discussions WHERE number=?', (number,)).fetchone() is None:
            raise store.Missing(f'No roundtable discussion {number}.')
        db.execute('INSERT INTO permission_requests(discussion,request,payload,state,chosen) VALUES (?,?,?,?,NULL)',
                   (number, request_id, json.dumps(payload, ensure_ascii=False), 'waiting'))
        _event(db, number, payload)
    return payload


def answer(number: int, request_id: str, option: str) -> dict[str, Any]:
    """Store one of the options supplied by ACP. Repeating the same answer is safe."""
    with store.connect() as db:
        db.execute(SCHEMA)
        payload = _row(db, number, request_id)
        if payload['state'] == 'answered' and payload['chosen'] == option:
            return payload
        if payload['state'] != 'waiting':
            raise ValueError(f'Permission request {request_id} is {payload["state"]}.')
        options = cast(list[dict[str, Any]], payload.get('options') or [])
        if option not in [one.get('optionId') for one in options]:
            raise ValueError('Choose one of the permission options supplied by the agent.')
        db.execute('UPDATE permission_requests SET state=?, chosen=? WHERE discussion=? AND request=?',
                   ('answered', option, number, request_id))
        payload = {**payload, 'state': 'answered', 'chosen': option}
        _event(db, number, payload)
    return payload


def _cancel(number: int, request_id: str) -> None:
    with store.connect() as db:
        db.execute(SCHEMA)
        if db.execute('SELECT 1 FROM permission_requests WHERE discussion=? AND request=?',
                      (number, request_id)).fetchone() is None:
            return
        payload = _row(db, number, request_id)
        if payload['state'] != 'waiting':
            return
        db.execute('UPDATE permission_requests SET state=? WHERE discussion=? AND request=?',
                   ('cancelled', number, request_id))
        _event(db, number, {**payload, 'state': 'cancelled'})


def cancel_all(number: int) -> None:
    """Withdraw requests left waiting when a runner closes its seats."""
    with store.connect() as db:
        db.execute(SCHEMA)
        waiting = db.execute('SELECT request FROM permission_requests WHERE discussion=? AND state=?',
                             (number, 'waiting')).fetchall()
        for row in waiting:
            payload = _row(db, number, str(row['request']))
            db.execute('UPDATE permission_requests SET state=? WHERE discussion=? AND request=?',
                       ('cancelled', number, row['request']))
            _event(db, number, {**payload, 'state': 'cancelled'})


async def request(number: int, position: int, payload: dict[str, Any],
                  notify: Callable[[dict[str, Any]], None] | None = None) -> str | None:
    """Wait for the person's ACP option. Unrelated changes cause no database reads."""
    request_id = uuid.uuid4().hex
    loop = asyncio.get_running_loop()
    waiting: asyncio.Future[str | None] = loop.create_future()

    def receive() -> None:
        if waiting.done():
            return
        try:
            found = get(number, request_id)
        except (ValueError, store.Missing):
            return
        if found['state'] != 'waiting':
            waiting.set_result(str(found['chosen']) if found['state'] == 'answered' else None)

    def changed(given: dict[str, Any]) -> None:
        if topic(number) in given.get('kinds', []):
            loop.call_soon_threadsafe(receive)

    listener = events.listen('roundtables', changed)
    opened = False
    try:
        found = _opened(number, position, request_id, payload)
        opened = True
        if notify is not None:
            await asyncio.to_thread(notify, found)
        receive()  # An answer can arrive before the request reaches this await.
        return await waiting
    finally:
        try:
            if opened:
                _cancel(number, request_id)
                if notify is not None:
                    await asyncio.to_thread(notify, get(number, request_id))
        finally:
            listener.close()
