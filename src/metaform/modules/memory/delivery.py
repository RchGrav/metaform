"""Functional memory delivery, using the agents module's shared context-epoch receipts.

The graph remains the source of memory bodies. These tables keep functional encounters, entry revisions and
withdrawn identities only; a notice never copies a graph into a per-agent inbox or acknowledges its contents.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

from metaform.data import Column, Index, Store, Table, TableTx
from metaform.module import (
    Context,
    agent_context_collecting,
    agent_context_epoch,
    context,
    prepare_agent_context,
    record_agent_context,
)

Row = dict[str, Any]
Key = tuple[str, str]

TABLES = (
    Table('encounters', place='project', key=('session', 'epoch', 'receiver', 'provider'),
          columns=(Column('session', required=True), Column('epoch', 'int', required=True),
                   Column('receiver', required=True), Column('provider', required=True, default=''),
                   Column('layers', 'json')),
          indexes=(Index(('receiver', 'provider')),)),
    Table('entry_revisions', place='project', key=('receiver', 'provider'),
          columns=(Column('receiver', required=True), Column('provider', required=True, default=''),
                   Column('revision', required=True))),
    Table('withdrawals', place='project', key=('receiver', 'provider', 'component'),
          columns=(Column('receiver', required=True), Column('provider', required=True, default=''),
                   Column('component', required=True), Column('requires', required=True),
                   Column('kind', required=True), Column('value', 'json', required=True))),
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
    """One exact canonical body, independently receipted from the other entities and relations in a response."""
    if name is None:
        name = entity_name(str(value['name'])) if kind == 'entities' else relation_name(value)
    text = encoded({kind: value})
    digest = hashlib.sha256(text.encode()).hexdigest()
    return {'name': name, 'text': text, 'rendered_fingerprint': digest, 'actual_version_id': digest,
            'origin': 'memory', 'kind': kind, 'value': value, 'delivered_value': value, 'requires': requires}


def components(whole: Row) -> list[Row]:
    return [component(kind, value) for kind in ('entities', 'relations') for value in whole.get(kind, [])]


@contextmanager
def authoring(ctx: Context) -> Generator[list[tuple[Row | None, Row]]]:
    """A successful write teaches its author the supplied change, without acknowledging unseen prior content.

    Each pair is the body before and after the mutation. A new body is wholly supplied by the author; an edit is
    known only if its previous body was already received. Receipts follow commit, in the context epoch that wrote.
    """
    changes: list[tuple[Row | None, Row]] = []
    session = ctx.session if ctx.surface != 'web' else None
    epoch = agent_context_epoch(ctx.folder, session, project=ctx.project) if session else 0
    yield changes
    if not session or not changes:
        return
    prepared = prepare_agent_context(ctx.folder, session, [before for before, _ in changes if before],
                                     project=ctx.project)
    if prepared['epoch'] != epoch:
        return
    previous = cast(dict[str, Row], prepared.get('previous') or {})
    known: dict[str, Row] = {}
    for before, after in changes:
        if before is None or previous.get(before['name'], {}).get('fingerprint') == before['rendered_fingerprint']:
            known[after['name']] = after
            previous[after['name']] = {'fingerprint': after['rendered_fingerprint']}
    if known:
        record_agent_context(ctx.folder, session, list(known.values()), project=ctx.project, epoch=epoch,
                             channel='authored')


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


def changed(tx: TableTx, keys: set[Key], withdrawals: list[Row] | None = None) -> None:
    """Publish enough identity for relay recipients to filter before reading. Called inside the graph mutation."""
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
        for row in tx.rows('encounters', identity, limit=0).results:
            tx.concern(session_id=row['session'])


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


def prepare(ctx: Context, whole: Row, key: Key | None = None, *, interested: bool = True) -> Row:
    """Select current unread bodies and withdrawals against the shared ledger; this does not acknowledge any."""
    current = components(whole)
    live = {one['name'] for one in current}
    removed = [one for one in withdrawals(ctx, key) if one['name'] not in live]
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


def notices(ctx: Context, payload: Row | None = None) -> Row:
    """Unread notices for functional entries this agent already encountered, suitable for its next normal turn.

    Returned components acknowledge only the notices. The referenced read_unread operation acknowledges graph
    contents independently after those contents are returned. A resumed session can request this without a payload.
    """
    if ctx.session is None or ctx.project is None:
        return {'epoch': 0, 'components': [], 'text': '', 'entries': []}
    if payload is not None:
        kinds: list[Any] = payload.get('kinds') or []
        if payload.get('project') not in (None, ctx.project) or 'memory.changed' not in kinds:
            return {'epoch': 0, 'components': [], 'text': '', 'entries': []}
        recipients = payload.get('session_ids')
        if isinstance(recipients, list) and ctx.session not in recipients:
            return {'epoch': 0, 'components': [], 'text': '', 'entries': []}
    from . import Key as MemoryKey
    from . import _prompt, _reaches, _view  # pyright: ignore[reportPrivateUsage]

    epoch = agent_context_epoch(ctx.folder, ctx.session, project=ctx.project)
    store = Store(ctx.project, module='memory')
    with store.tables(write=False) as tx:
        entries = list(tx.rows('encounters', {'session': ctx.session, 'epoch': epoch}, limit=0).results)
    selected: list[Row] = []
    details: list[Row] = []
    addresses = {str(kind)[7:] for kind in (payload or {}).get('kinds', []) if str(kind).startswith('memory:')}
    for entry in entries:
        receiver, provider = str(entry['receiver']), str(entry['provider'])
        if addresses and receiver not in addresses and provider not in addresses:
            continue
        reading = context('memory', Path(ctx.folder), project=ctx.project)
        reading.session = ctx.session
        reading.switches = {'layers': entry['layers']} if entry['layers'] else {}
        reading.store = Store(ctx.project, module='memory', toggled=entry['layers'] or None)
        if not _reaches(reading.store, receiver):
            continue
        with reading.store.tables(write=False) as tx:
            whole = _view(tx, MemoryKey(receiver, provider)).whole()
        pending = prepare(reading, whole, (receiver, provider), interested=False)
        total, unread, updated = counts(pending)
        if not unread:
            continue
        call = (f'metaform memory read_unread receiver={receiver} provider={provider}' if provider else
                f'metaform memory read_unread node=element:{receiver}')
        text = ctx.calls(_prompt('counts', total=str(len(total)), unread=str(len(unread)),
                                 updated=str(len(updated)), read_unread=call))
        # Distinct corrections with unchanged totals still produce a new notice.
        digest = fingerprint([(one['name'], one['rendered_fingerprint']) for one in pending['components']])
        selected.append({'name': f'memory:notice:{receiver}|{provider}:{digest}', 'text': text,
                         'rendered_fingerprint': digest, 'actual_version_id': digest,
                         'origin': 'memory', 'delivered_value': text})
        details.append({'receiver': receiver, 'provider': provider, 'total': len(total), 'unread': len(unread),
                        'updated': len(updated), 'read_unread': call})
    result = prepare_agent_context(ctx.folder, ctx.session, selected, project=ctx.project)
    return {**result, 'entries': details}
