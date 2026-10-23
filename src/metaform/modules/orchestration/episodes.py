"""Coherent work identity independent of a card, runner or ACP conversation.

The responsible agent selects continuity through ``continue_from``. This is an
organizational choice, never a new readiness condition. Each card keeps its own
assignment, result and return route. Session bindings retain history separately
from the one current binding used for tool attribution.
"""
from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

from metaform.data import Column, Index, Table, TableTx
from metaform.module import Stop

TABLES = (
    Table('episodes', key=('episode_id',), columns=(
        Column('episode_id', required=True), Column('created', required=True),
        Column('updated', required=True), Column('session_id'), Column('assignment_id'))),
    Table('episode_work', key=('assignment_id',), columns=(
        Column('assignment_id', required=True), Column('work_id', required=True),
        Column('episode_id', required=True), Column('created', required=True),
        Column('fresh_context', 'bool', default=False)),
        indexes=(Index(('episode_id',)), Index(('work_id',), unique=True))),
    Table('binding_history', key=('session_id', 'assignment_id'), columns=(
        Column('session_id', required=True), Column('assignment_id', required=True),
        Column('episode_id', required=True), Column('runner'),
        Column('created', required=True), Column('updated', required=True)),
        indexes=(Index(('assignment_id',)), Index(('runner',)), Index(('episode_id',)))),
)


def attach(tx: TableTx, assignment: Mapping[str, Any], at: str, *,
           continue_from: str | None = None, fresh: bool = False) -> dict[str, Any]:
    """Retain a declared workstream without guessing coherence from title overlap."""
    ident = str(assignment['assignment_id'])
    member = tx.get('episode_work', {'assignment_id': ident})
    source = None
    if continue_from:
        source = tx.get('episodes', {'episode_id': continue_from})
        if source is None:
            previous = tx.get('episode_work', {'assignment_id': continue_from})
            if previous is None:
                found = tx.rows('assignments', {'work_id': continue_from}, limit=1).results
                if found:
                    prior = found[0]
                    previous = tx.get('episode_work', {'assignment_id': prior['assignment_id']})
                    if previous is None:
                        attach(tx, prior, at)
                        previous = tx.get('episode_work', {'assignment_id': prior['assignment_id']})
            source = tx.get('episodes', {'episode_id': previous['episode_id']}) if previous else None
        if source is None:
            raise Stop(f'No recorded episode or assignment {continue_from}.', 'metaform orchestration inspect')
        if member and member['episode_id'] != source['episode_id'] and assignment.get('owner_session_id'):
            raise Stop('A bound assignment retains its episode history.', 'metaform orchestration episode')
    episode_id = str(source['episode_id']) if source else str(member['episode_id']) if member else uuid.uuid4().hex
    episode = tx.get('episodes', {'episode_id': episode_id})
    if episode is None:
        episode = tx.insert('episodes', {'episode_id': episode_id, 'created': at, 'updated': at,
                                        'session_id': None, 'assignment_id': None})
    if member is None:
        tx.insert('episode_work', {'assignment_id': ident, 'work_id': assignment['work_id'],
                                  'episode_id': episode_id, 'created': at, 'fresh_context': fresh})
    elif member['episode_id'] != episode_id or fresh:
        tx.update('episode_work', {'assignment_id': ident}, {'episode_id': episode_id, 'fresh_context': fresh})
    return episode


def context(tx: TableTx, assignment: Mapping[str, Any]) -> dict[str, Any] | None:
    member = tx.get('episode_work', {'assignment_id': assignment['assignment_id']})
    if member is None:
        return None
    episode = tx.get('episodes', {'episode_id': member['episode_id']})
    if episode is None:
        return None
    current = tx.get('assignments', {'assignment_id': episode['assignment_id']}) if episode['assignment_id'] else None
    members = tx.rows('episode_work', {'episode_id': episode['episode_id']}, limit=0).results
    return {**episode, 'fresh_context': bool(member['fresh_context']), 'previous_assignment': current,
            'work': [{'assignment_id': one['assignment_id'], 'work_id': one['work_id']} for one in members]}


def bound(tx: TableTx, assignment: Mapping[str, Any], session: str, runner: str | None, at: str) -> None:
    episode = attach(tx, assignment, at)
    key = {'session_id': session, 'assignment_id': assignment['assignment_id']}
    prior = tx.get('binding_history', key)
    if prior is None:
        tx.insert('binding_history', {**key, 'episode_id': episode['episode_id'],
                                     'runner': runner, 'created': at, 'updated': at})
    else:
        tx.update('binding_history', key, {'runner': runner, 'updated': at})
    tx.update('episodes', {'episode_id': episode['episode_id']}, {
        'session_id': session, 'assignment_id': assignment['assignment_id'], 'updated': at})
    tx.update('episode_work', {'assignment_id': assignment['assignment_id']}, {'fresh_context': False})
