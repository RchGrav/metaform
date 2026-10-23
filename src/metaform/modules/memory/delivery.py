"""Functional memory delivery, using the agents module's shared context-epoch receipts.

The graph remains the source of memory bodies. These tables keep functional encounters, entry revisions and
withdrawn identities only. Changes to consumed functional entries coalesce into references for the next natural
turn. No change wakes an agent or broadcasts bodies. Counts never acknowledge a body.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, cast

from metaform import events
from metaform.data import Column, Index, Store, Table, TableTx
from metaform.module import (
    Context,
    agent_context_collecting,
    agent_context_epoch,
    prepare_agent_context,
    record_agent_context,
)

from .citations import settled

Row = dict[str, Any]
Key = tuple[str, str]

TABLES = (
    Table('encounters', place='project', key=('session', 'epoch', 'receiver', 'provider'),
          columns=(Column('session', required=True), Column('epoch', 'int', required=True),
                   Column('receiver', required=True), Column('provider', required=True, default=''),
                   Column('layers', 'json')),
          indexes=(Index(('receiver', 'provider')),)),
    Table('pending_changes', place='project', key=('session', 'epoch', 'receiver', 'provider'),
          columns=(Column('session', required=True), Column('epoch', 'int', required=True),
                   Column('receiver', required=True), Column('provider', required=True, default=''),
                   Column('revision', required=True), Column('components', 'json', required=True),
                   Column('withdrawals', 'json', required=True))),
    Table('entry_revisions', place='project', key=('receiver', 'provider'),
          columns=(Column('receiver', required=True), Column('provider', required=True, default=''),
                   Column('revision', required=True))),
    Table('withdrawals', place='project', key=('receiver', 'provider', 'component'),
          columns=(Column('receiver', required=True), Column('provider', required=True, default=''),
                   Column('component', required=True), Column('requires', required=True),
                   Column('kind', required=True), Column('value', 'json', required=True)),
          indexes=(Index(('component',)),)),
)


def encoded(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def fingerprint(value: Any) -> str:
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def entity_name(name: str) -> str:
    return f'memory:entity:{name}'


def relation_name(value: Row) -> str:
    return f'memory:relation:{fingerprint(value)}'


def component(kind: str, value: Any, *, name: str | None = None, requires: str | None = None) -> Row:
    """One exact canonical body, independently receipted from the other entities and relations in a response. Its
    receipted text leaves out where a moved cited text now stands, which `value` still shows the reader, `settled`."""
    if name is None:
        name = entity_name(str(value['name'])) if kind == 'entities' else relation_name(value)
    identity = value
    if kind == 'entities' and value.get('stale'):
        identity = {**value, 'stale': [settled(one) for one in value['stale']]}
    text = encoded({kind: identity})
    digest = hashlib.sha256(text.encode()).hexdigest()
    return {'name': name, 'text': text, 'rendered_fingerprint': digest, 'actual_version_id': digest,
            'origin': 'memory', 'kind': kind, 'value': value, 'delivered_value': value, 'requires': requires}


def components(whole: Row) -> list[Row]:
    return [component(kind, value) for kind in ('entities', 'relations') for value in whole.get(kind, [])]


def encounter(ctx: Context, key: Key, *, epoch: int | None = None) -> None:
    """Remember the functional entry point encountered by this actual session, without recording a body read."""
    if ctx.session is None or ctx.store is None:
        return
    if epoch is None:
        epoch = agent_context_epoch(ctx.folder, ctx.session, project=ctx.project)
    identity = {'session': ctx.session, 'epoch': epoch, 'receiver': key[0], 'provider': key[1]}
    layers = ctx.switches.get('layers')
    with ctx.store.tables() as tx:
        row = tx.get('encounters', identity)
        if row is None:
            tx.insert('encounters', {**identity, 'layers': layers})
        elif row.get('layers') != layers:
            tx.update('encounters', identity, {'layers': layers})
        tx.concern(session_id=ctx.session, kind='memory.encounter')


def changed(tx: TableTx, keys: set[Key], withdrawals: list[Row] | None = None, writer: str | None = None,
            affected: list[str] | None = None) -> None:
    """Publish enough identity for relay recipients to filter before reading. Called inside the graph mutation. The
    session that wrote, `writer`, is not among them: what it wrote is its own, `authored`."""
    for receiver, provider in sorted(keys):
        identity = {'receiver': receiver, 'provider': provider}
        revision = uuid.uuid4().hex
        if tx.get('entry_revisions', identity) is None:
            tx.insert('entry_revisions', {**identity, 'revision': revision})
        else:
            tx.update('entry_revisions', identity, {'revision': revision})
        for one in withdrawals or ():
            entry = {**identity, 'component': one['name']}
            values = {'kind': one['kind'], 'value': one['value'], 'requires': one['requires'] or one['name']}
            if tx.get('withdrawals', entry) is None:
                tx.insert('withdrawals', {**entry, **values})
            else:
                tx.update('withdrawals', entry, values)
        tx.concern(kind='memory.changed')
        tx.concern(kind=f'memory:{receiver}')
        if provider:
            tx.concern(kind=f'memory:{provider}')
        # Queue references only for encountered entries. Actual body receipts are checked at delivery time:
        # orienting/counting an entry alone must not subscribe a session to memory corrections.
        names = {entity_name(name) for name in affected or ()}
        names.update(str(one['requires'] or one['name']) for one in withdrawals or ())
        removed = [{'name': str(one['name']), 'kind': one['kind'], 'value': one['value'],
                    'observed_revision': revision}
                   for one in withdrawals or ()]
        for row in tx.rows('encounters', identity, limit=0).results:
            if row['session'] == writer:
                continue
            key = {'session': row['session'], 'epoch': row['epoch'], **identity}
            pending = tx.get('pending_changes', key)
            prior_removed = {one['name']: one for one in pending['withdrawals']} if pending else {}
            prior_removed.update({one['name']: one for one in removed})
            values = {'revision': revision, 'components': sorted(names | set(pending['components'] if pending else [])),
                      'withdrawals': list(prior_removed.values())}
            if pending is None:
                tx.insert('pending_changes', {**key, **values})
            else:
                tx.update('pending_changes', key, values)
            tx.concern(session_id=row['session'])


def remade(tx: TableTx, names: list[str]) -> None:
    """A memory that exists is not withdrawn under its own identity: kept, a withdrawal at a node the memory made again
    does not reach is read there while its new body is read at another, and the two take turns as the one receipt of
    that identity, unread forever. Where the memory is joined its new body supersedes the withdrawal, which is dropped;
    where it is not, the withdrawal becomes an index withdrawal, as unjoin writes, with an identity of its own for this
    making, so the agent that held the memory there is told once it no longer applies. A withdrawal of one of their
    relations is dropped: a relation reaches a node only through its ends' joins. Reads only these memories' rows."""
    from . import Key as MemoryKey
    for name in dict.fromkeys(names):
        entity = tx.get('entities', {'name': name})
        if entity is None:
            continue
        joined = {(row['receiver'], row['provider']) for row in tx.rows('joins', {'entity': name}, limit=0).results}
        for row in tx.rows('withdrawals', {'component': entity_name(name)}, limit=0).results:
            identity = {'receiver': row['receiver'], 'provider': row['provider']}
            tx.delete('withdrawals', {**identity, 'component': row['component']})
            if (row['receiver'], row['provider']) in joined:
                continue
            index = {**identity, 'component': f'memory:index:{row["receiver"]}|{row["provider"]}:{name}@{entity["seq"]}'}
            if tx.get('withdrawals', index) is None:
                tx.insert('withdrawals', {**index, 'requires': entity_name(name), 'kind': 'withdrawn',
                                          'value': {'name': name, **MemoryKey(**identity).said()}})
        for end in ('source', 'target'):
            for row in tx.rows('relations', {end: name}, limit=0).results:
                tx.delete('withdrawals', {'component': relation_name(
                    {'from': row['source'], 'to': row['target'], 'relationType': row['relation_type']})})


def authored(ctx: Context, after: list[Row], before: list[Row] | None = None) -> None:
    """The bodies the calling session just wrote are received by it, so its own write never comes back to it as an
    unread notice, one more turn to tell it what it sent (2026-10-19, code.dispatcher.agent#5b). A body it changed,
    `after`, counts only when it held the one it changed, `before`, at that version: another agent's change it has not
    read stays unread."""
    if ctx.session is None or not after:
        return
    known: set[str] = set()
    if before:
        due = {str(one['name']) for one in prepare_agent_context(ctx.folder, ctx.session, before,
                                                                 project=ctx.project)['components']}
        known = {str(one['name']) for one in before} - due
    changed_names = {str(one['name']) for one in before or ()}
    # a receipt changes no map and no one listens for it, so it is announced by no event: noted, it would strip the
    # write's own concerns, the sessions and kinds every other recipient filters on
    events.quietly(record_agent_context, ctx.folder, ctx.session, [one for one in after if one['name'] not in
                   changed_names or one['name'] in known], project=ctx.project, channel='authored')


def revision(project: str, address: str, provider: str = '') -> str:
    """The one functional entry's content-change revision, independent of its item counter or memory count."""
    with Store(project, module='memory').tables(write=False) as tx:
        row = tx.get('entry_revisions', {'receiver': address, 'provider': provider})
    return str(row['revision']) if row else ''


def withdrawals(ctx: Context, key: Key | None) -> list[Row]:
    if ctx.store is None or key is None or ctx.session is None:
        return []
    with ctx.store.tables(write=False) as tx:
        rows = tx.rows('withdrawals', {'receiver': key[0], 'provider': key[1]}, limit=0).results
    return [component(row['kind'], row['value'], name=row['component'], requires=row['requires']) for row in rows]


def prepare(ctx: Context, whole: Row, key: Key | None = None, *, interested: bool = True,
            entry_revision: Row | None = None) -> Row:
    """Select current unread bodies and withdrawals against the shared ledger; this does not acknowledge any."""
    current = components(whole)
    live = {one['name'] for one in current}
    removed = [one for one in withdrawals(ctx, key) if one['name'] not in live]
    # Only a revision captured in the same transaction as the body can establish an exact reread. Reading the
    # revision later could tag an old snapshot with a concurrent correction's revision and hide that correction.
    if entry_revision is not None:
        for one in current:
            one['entry_revision'] = entry_revision
    # An index withdrawal has its own identity, but is only meaningful to an agent that received its entity.
    required = {str(one['requires']) for one in removed if one.get('requires')} - live
    probes = [{'name': name, 'text': '', 'rendered_fingerprint': ''} for name in required
              if name not in {one['name'] for one in removed}]
    prepared = prepare_agent_context(ctx.folder, ctx.session, [*current, *removed, *probes], project=ctx.project)
    previous = cast(dict[str, Row], prepared.get('previous') or {})
    due = [one for one in cast(list[Row], prepared['components']) if one.get('kind') and
           (not one.get('requires') or one['requires'] in previous)]
    if interested and key is not None:
        encounter(ctx, key, epoch=int(prepared['epoch']))
    result: Row = {'entities': [], 'relations': []}
    for one in due:
        if one.get('reference'):
            result.setdefault('restored', []).append(one['reference'])
        else:
            result.setdefault(one['kind'], []).append(one['value'])
    return {**prepared, 'components': due, 'whole': result, 'current': current}


def queue(ctx: Context, prepared: Row, *, all_current: bool = False) -> None:
    """Keep exact snapshots until MCP response shaping succeeds; CLI returns deliver their complete bodies."""
    if ctx.session is None:
        return
    selected = cast(list[Row], prepared['current' if all_current else 'components'])
    epoch = int(prepared['epoch'])
    if ctx.surface == 'mcp' or agent_context_collecting():
        ctx.queue_context(selected, epoch)
    else:
        record_agent_context(ctx.folder, ctx.session, selected, project=ctx.project, epoch=epoch, channel='cli')


def counts(prepared: Row) -> tuple[set[str], set[str], set[str]]:
    """Current, unread and updated memory identities, including relation changes and previous-body withdrawals."""
    current = {str(one['value']['name']) for one in prepared['current'] if one['kind'] == 'entities'}
    previous = cast(dict[str, Row], prepared.get('previous') or {})
    unread: set[str] = set()
    updated: set[str] = set()
    for one in prepared['components']:
        kind, value = one['kind'], one['value']
        if kind == 'entities':
            names = {str(value['name'])}
        elif kind == 'deleted_entities':
            names = {str(value)}
        elif kind == 'withdrawn':
            names = {str(value['name'])}
        else:
            names = {str(value['from']), str(value['to'])} & current
        unread.update(names)
        updated.update(name for name in names if entity_name(name) in previous or one['name'] in previous)
    return current, unread, updated


class ContextChanges:
    """Observational change references, consumed by transport only on an already scheduled turn."""

    def pending(self, ctx: Context, session: str | None) -> list[Row]:
        from metaform.module import context
        if not session:
            return []
        from . import visible_at
        ctx = context('memory', ctx.folder, project=ctx.project, session=session, switches=ctx.switches)
        epoch = agent_context_epoch(ctx.folder, session, project=ctx.project)
        with ctx.require_store().tables(write=False) as tx:
            rows = tx.rows('pending_changes', {'session': session, 'epoch': epoch}, limit=0).results
            for row in rows:
                row['withdrawals'] = [{**one, 'superseded': tx.get('withdrawals', {
                    'receiver': row['receiver'], 'provider': row['provider'], 'component': one['name']}) is None}
                    for one in row['withdrawals']]
        notices: list[Row] = []
        for row in rows:
            if not visible_at(ctx.require_store(), str(row['receiver'])):
                continue
            probes = [{'name': name, 'text': ''} for name in row['components']]
            previous = prepare_agent_context(ctx.folder, session, probes, project=ctx.project)['previous']
            receiver, provider = str(row['receiver']), str(row['provider'])
            expected = {'receiver': receiver, 'provider': provider, 'revision': row['revision']}
            previous = {name: held for name, held in previous.items()
                        if held.get('component', {}).get('entry_revision') != expected}
            if not previous:
                continue
            read = f'metaform memory read_graph node=element:{receiver}' + (f' provider={provider}' if provider else '')
            notices.append({'receiver': receiver, 'provider': provider, 'revision': row['revision'],
                            'epoch': epoch, 'previous': {name: held['fingerprint'] for name, held in previous.items()},
                            'withdrawals': row['withdrawals'], 'read': read})
        return notices

    def delivered(self, ctx: Context, session: str | None, notices: list[Row]) -> None:
        """Acknowledge only matching revisions after acceptance. A concurrent edit remains pending."""
        from metaform.module import context
        if not session or not notices:
            return
        ctx = context('memory', ctx.folder, project=ctx.project, session=session)
        with ctx.require_store().tables() as tx:
            for notice in notices:
                key = {'session': session, 'epoch': notice['epoch'],
                       'receiver': notice['receiver'], 'provider': notice['provider']}
                row = tx.get('pending_changes', key)
                if row and row['revision'] == notice['revision']:
                    tx.delete('pending_changes', key)


CHANGES = ContextChanges()
