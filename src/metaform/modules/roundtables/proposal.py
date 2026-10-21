"""Prepare a fresh Planner proposal, then record the person's decision on its exact saved revision."""
from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from metaform import events, prompt_files
from metaform.data import Node
from metaform.module import Context, Stop, agent_caller, provided

from . import follow

FILE = 'proposal.md'


def state(ctx: Context, table: str) -> dict[str, Any] | None:
    with ctx.require_store().tables(write=False) as tx:
        row = tx.get('proposals', {'table_id': table})
    if row is None:
        return None
    return {'state': row['state'], 'file': row['file'], 'ticket': row.get('work_id'),
            'digest': row.get('digest'), 'error': row.get('error')}


def announce(ctx: Context, table: str) -> dict[str, Any]:
    """A proposal change uses the table's existing stream, after its discussion has ended."""
    result = state(ctx, table)
    store = ctx.require_store()
    with store.tables() as tx:
        seq = max((int(row['seq']) for row in tx.rows('events', {'table_id': table}, limit=0).results), default=0) + 1
        tx.concern(kind=follow.CHANGE_KIND)
        tx.concern(kind=f'{follow.CHANGE_KIND}:{table}')
        tx.insert('events', {'table_id': table, 'seq': seq, 'kind': 'proposal', 'audience': 'person',
                             'payload': {'proposal': result}, 'at': follow.now()})
    ctx.publish(follow.TOPIC, {'table': table, 'seq': seq, 'kind': 'proposal', 'audience': 'person',
                             'proposal': result})
    return {'table': table, 'proposal': result}


def plan(ctx: Context, table: str) -> dict[str, Any]:
    """Reserve one planning ticket durably, then assign the existing Planner through normal dispatch admission."""
    store = ctx.require_store()
    with store.tables(write=False) as tx:
        row = tx.get('tables', {'table_id': table})
    if row is None or row['state'] != 'ended':
        raise Stop('A proposal needs a finished table.', 'metaform roundtables status ' + table)
    followed = cast(dict[str, Any], row.get('followed') or {})
    if followed.get('opener') == 'agent':
        return {'table': table, 'said': 'The result belongs to the calling agent.'}
    saved = str(followed.get('saved') or '')
    if not saved:
        raise Stop('Save the table record before planning.', 'metaform roundtables follow ' + table)
    file = f'{saved}/{FILE}'
    with store.tables() as tx:
        if tx.get('proposals', {'table_id': table}) is None:
            tx.insert('proposals', {'table_id': table, 'state': 'planning', 'file': file, 'created': follow.now()})
    # Stable transport identity makes retries harmless, including a crash after notification delivery.
    for _, transport in provided(ctx.folder, 'orchestration.transport'):
        ident = f'roundtable-result-{table}'
        record = f'{saved}/{follow.RECORD}'
        transport.notify_user(ctx, {'message_id': ident, 'kind': 'roundtable_result',
                                   'table': table, 'record': record,
                                   'text': f'Roundtable {table}: {record}'}, ident)
        break
    services = [value for _, value in provided(ctx.folder, 'orchestration')]
    if not services:
        raise Stop('Orchestration is off, so Planner cannot be assigned.', 'metaform enable orchestration')
    address = str(row.get('address') or '') or follow.top_element(store)
    if not address:
        raise Stop('The proposal needs a functional map location.', 'metaform help intake')
    root = Path(store.project().path).resolve()
    task = prompt_files.required(follow.PACKAGE, 'proposal_task', table=table,
                                 record=str(root / saved / follow.RECORD), proposal=file)
    with store.atomic(), store.tables() as tx:
        kept = tx.get('proposals', {'table_id': table})
        if kept is None or not kept.get('work_id'):
            work = store.add_work(Node('element', address), None, kind='enhancement',
                                  title=f'Proposal from roundtable {table}', task=task,
                                  note='Planning only. Execution requires the person\'s decision on the saved proposal.')
            tx.update('proposals', {'table_id': table}, {'work_id': work.id})
            work_id = work.id
        else:
            work_id = str(kept['work_id'])
    service = services[0]
    called = replace(ctx, nouns={'work': work_id, 'role': 'planner', 'automatic': True,
                                 'result': f'Prepare {file} for the person. Create no execution work.'})
    if service.assignment(called, work_id=work_id) is None:
        try:
            service.claim(called)
        except Stop:
            if service.assignment(called, work_id=work_id) is None:
                raise
    with store.tables() as tx:
        tx.concern(kind=follow.CHANGE_KIND)
        tx.concern(kind=f'{follow.CHANGE_KIND}:{table}')
        tx.update('proposals', {'table_id': table}, {'error': None})
    return announce(ctx, table)


def path(ctx: Context, proposal: dict[str, Any]) -> Path:
    root = Path(ctx.require_store().project().path).resolve()
    found = (root / str(proposal['file'])).resolve()
    if not found.is_relative_to(root) or found.name != FILE or not found.is_file():
        raise Stop('The saved proposal is missing.', 'metaform roundtables status ' + str(ctx.nouns['table']))
    return found


def read(ctx: Context) -> dict[str, Any]:
    table = str(ctx.nouns['table'])
    proposal = state(ctx, table)
    if proposal is None:
        raise Stop('This table has no Planner proposal.', 'metaform roundtables plan ' + table)
    if proposal['state'] == 'planning':
        return {'table': table, 'proposal': proposal}
    body = path(ctx, proposal).read_bytes()
    if hashlib.sha256(body).hexdigest() != proposal['digest']:
        raise Stop('The proposal changed. Planner must submit the new revision.', 'metaform roundtables submit ' + table)
    return {'table': table, 'proposal': proposal, 'proposal_text': body.decode('utf-8')}


def submit(ctx: Context) -> dict[str, Any]:
    table = str(ctx.nouns['table'])
    proposal = state(ctx, table)
    if proposal is None:
        raise Stop('This table has no planning assignment.', 'metaform roundtables plan ' + table)
    root = Path(ctx.require_store().project().path).resolve()
    source_root = ctx.folder.resolve()
    source = (source_root / str(proposal['file'])).resolve()
    target = (root / str(proposal['file'])).resolve()
    if source_root != root:
        if not source.is_relative_to(source_root) or not target.is_relative_to(root) or not source.is_file() \
                or source.name != FILE or target.name != FILE:
            raise Stop('Save the proposal in this assignment\'s project folder.', 'metaform roundtables status ' + table)
        target.write_bytes(source.read_bytes())
    body = path(ctx, proposal).read_bytes()
    if not body.strip():
        raise Stop('The proposal is empty.', 'metaform roundtables status ' + table)
    digest = hashlib.sha256(body).hexdigest()
    with ctx.require_store().tables() as tx:
        kept = tx.get('proposals', {'table_id': table})
        assert kept is not None
        tx.update('proposals', {'table_id': table}, {'digest': digest, 'error': None,
                  'state': kept['state'] if kept.get('digest') == digest else 'ready'})
    return announce(ctx, table)


def decide(ctx: Context) -> dict[str, Any]:
    """Approval records consent. It starts no execution work and never guesses tickets from Markdown."""
    if not ctx.consented and (ctx.surface == 'mcp' or (ctx.surface == 'cli' and agent_caller() is not None)):
        raise Stop('The person must decide this proposal from the page or their own terminal.',
                   'metaform roundtables proposal ' + str(ctx.nouns['table']))
    table, action = str(ctx.nouns['table']), str(ctx.nouns['action'])
    if action not in ('approve', 'reject'):
        raise Stop('Choose approve or reject.', 'metaform roundtables decide ' + table)
    result = read(ctx)
    proposal = result['proposal']
    if proposal['state'] == 'planning' or ctx.nouns.get('digest') != proposal['digest']:
        raise Stop('Review the current proposal before deciding.', 'metaform roundtables proposal ' + table)
    with ctx.require_store().tables() as tx:
        kept = tx.get('proposals', {'table_id': table})
        if kept is None or kept.get('digest') != proposal['digest']:
            raise Stop('The proposal changed during review.', 'metaform roundtables proposal ' + table)
        tx.update('proposals', {'table_id': table}, {'state': 'approved' if action == 'approve' else 'rejected'})
    return announce(ctx, table)


def prepare(ctx: Context, table: str) -> dict[str, Any]:
    try:
        return events.announced(ctx.folder, ctx.surface, plan, ctx, table)[0]
    except (Stop, OSError, ValueError) as error:
        # A Planner failure must not retract the finished discussion or stop its seats from being released.
        with ctx.require_store().tables() as tx:
            if tx.get('proposals', {'table_id': table}) is not None:
                tx.concern(kind=follow.CHANGE_KIND)
                tx.concern(kind=f'{follow.CHANGE_KIND}:{table}')
                tx.update('proposals', {'table_id': table}, {'error': follow.named(error)})
        if state(ctx, table) is not None:
            events.announced(ctx.folder, ctx.surface, announce, ctx, table)
        return {'table': table, 'error': follow.named(error)}
