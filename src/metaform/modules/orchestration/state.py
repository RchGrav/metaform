"""Durable GC assignments and their continuations over existing work records.

Work and its continuation share the work store's transaction. Dispatch owns every
process, capacity reservation and message delivery; this module records who owes
the result and what operation remains to be delivered after a restart.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import replace
from importlib import resources
from typing import Any, cast

from metaform import home, prompt_files
from metaform.data import Column, Index, Node, Store, Table, Tables, TableTx, WorkRecord
from metaform.module import (
    Context,
    Stop,
    agent_caller,
    agent_role_name,
    call,
    context,
    held_role,
    on_persons_word,
    persons_word,
    persons_word_acted,
    provided,
    surface,
)

from . import episodes, routing

HELP = 'metaform help orchestration'
ENDED = frozenset(('returned', 'delivered', 'failed', 'stopped', 'transferred'))
ACTIVE = ('queued', 'running', 'waiting', 'blocked', 'suspended', 'interrupted')
FACILITATORS = ('metaform://role/facilitator', 'metaform://role/role_creator')
TITLE = 80  # characters of a ticket's title a commission's line gives, cut as the brief cuts a title


def now() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def identity(*parts: str) -> str:
    return uuid.uuid5(uuid.NAMESPACE_URL, 'metaform:orchestration:' + ':'.join(parts)).hex


def prose(value: Any) -> str:
    """Structured finding parts written out as text: lists and objects become clauses, never their JSON."""
    if value is None:
        return ''
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Mapping):
        fields = cast(Mapping[str, Any], value)
        return '; '.join(f'{name}: {said}' for name, one in fields.items() if (said := prose(one)))
    if isinstance(value, (list, tuple)):
        return '; '.join(said for one in cast(Sequence[Any], value) if (said := prose(one)))
    return str(value)


HEADLINES = ('summary', 'finding', 'task', 'failure', 'detail', 'title')
TITLES = ('title', 'summary', 'finding', 'failure', 'detail', 'task')
STEPS = ('remediation', 'fix', 'steps')
DETAILS = ('where', 'file', 'line', 'why', 'detail', 'failure', 'severity', 'evidence')


def finding_text(fields: Mapping[str, Any]) -> tuple[str, str]:
    """A finding's ticket title, its summary in one line, and its task: the summary, details, remediation steps and
    verify check written out as prose."""
    head = next((name for name in HEADLINES if prose(fields.get(name))), None)
    named = next((name for name in TITLES if prose(fields.get(name))), None)
    title = ' '.join(prose(fields.get(named)).split()) if named else 'Functional finding'
    parts = [prose(fields.get(head))] if head else []
    for name in DETAILS:
        if name != head and prose(fields.get(name)):
            parts.append(f'{name.capitalize()}: {prose(fields.get(name))}')
    steps = next((fields.get(name) for name in STEPS if prose(fields.get(name))), None)
    if isinstance(steps, (list, tuple)):
        listed = [said for one in cast(Sequence[Any], steps) if (said := prose(one))]
        parts.append('Remediation:\n' + '\n'.join(f'{number}. {one}' for number, one in enumerate(listed, 1)))
    elif steps is not None:
        parts.append(f'Remediation: {prose(steps)}')
    if prose(fields.get('verify')):
        parts.append(f'Verify: {prose(fields.get("verify"))}')
    return title, '\n\n'.join(parts) or title


def own(ctx: Context) -> Store:
    store = ctx.require_store()
    if store.module == 'orchestration':
        return store
    base = store.bound_base()
    return Store(store.project_id, module='orchestration',
                 base=None if base is None else base.id, toggled=store.toggled)


def migrate_specialist_references(ctx: Context, *, work_ids: Sequence[str] | None = None,
                                  request_id: str | None = None) -> dict[str, int]:
    """Persist the namespace change in operational identity fields, never prompt or historical event bodies.

    Public registry metadata is read before the write transaction. Pinned specialist classifications also survive
    a temporarily unavailable provider. Supplying work IDs limits lazy migration to encountered assignments.
    """
    store = own(ctx)
    with store.tables(write=False) as tx:
        assignments = ([row for work in work_ids for row in tx.rows('assignments', {'work_id': work}, limit=1).results]
                       if work_ids is not None else [] if request_id else list(tx.rows('assignments', limit=0).results))
        routes = ([row for work in work_ids if (row := tx.get('routing', {'work_id': work})) is not None]
                  if work_ids is not None else [] if request_id else list(tx.rows('routing', limit=0).results))
        requests = ([row] if (row := tx.get('role_requests', {'request_id': request_id})) else []) if request_id else (
            [] if work_ids is not None else list(tx.rows('role_requests', limit=0).results))
        pending = ([] if request_id else [row for work in work_ids for row in
                    tx.rows('transitions', {'work_id': work, 'state': 'pending'}, limit=0).results]
                   if work_ids is not None else list(tx.rows('transitions', {'state': 'pending'}, limit=0).results))
    candidates = [str(row['authored_role_uri']) for row in assignments]
    candidates.extend(str(row.get('role') or '') for row in routes)
    snapshots = [cast(dict[str, Any], value) for value in [
        *(row.get('role_snapshot') for row in assignments), *(row.get('source') for row in requests),
        *(row['payload'].get('role_snapshot') for row in pending if row['kind'] == 'launch')]
        if isinstance(value, dict)]
    candidates.extend(str(snapshot.get('uri') or '') for snapshot in snapshots)
    candidates.extend(str(row['payload'].get('authored_role_uri') or '') for row in pending if row['kind'] == 'launch')
    counts = {'assignments': 0, 'routing': 0, 'role_requests': 0, 'pending_launches': 0}
    if not any(one.startswith('metaform://role/') for one in candidates):
        return counts
    mapping: dict[str, str] = {}
    procedural: set[str] = set()
    for snapshot in snapshots:
        if snapshot.get('specialist') is True:
            name = str(snapshot.get('name') or agent_role_name(str(snapshot.get('uri') or '')))
            if name:
                mapping[f'metaform://role/{name}'] = f'metaform://specialist/{name}'
        elif snapshot.get('specialist') is False:
            procedural.add(str(snapshot.get('uri')))
    if any(one.startswith('metaform://role/') and one not in mapping and one not in procedural for one in candidates):
        registries = provided(ctx.folder, 'agent.role')
        if len(registries) == 1:
            mapping.update({f'metaform://role/{agent_role_name(str(one["uri"]))}': str(one['uri'])
                            for one in registries[0][1].specialists(ctx)})
    if not any(one in mapping for one in candidates):
        return counts

    def snapshot_uri(value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        snapshot = cast(dict[str, Any], value)
        return {**snapshot, 'uri': mapping[snapshot['uri']]} if snapshot.get('uri') in mapping else snapshot

    with store.atomic(), store.tables() as tx:
        for before in assignments:
            row = tx.get('assignments', {'assignment_id': before['assignment_id']})
            if row is None:
                continue
            changes: dict[str, Any] = {}
            if row['authored_role_uri'] in mapping:
                changes['authored_role_uri'] = mapping[row['authored_role_uri']]
            snapshot = snapshot_uri(row.get('role_snapshot'))
            if snapshot != row.get('role_snapshot'):
                changes['role_snapshot'] = snapshot
            if changes:
                tx.update('assignments', {'assignment_id': row['assignment_id']}, changes)
                counts['assignments'] += 1
        for before in routes:
            row = tx.get('routing', {'work_id': before['work_id']})
            if row and row.get('role') in mapping:
                tx.update('routing', {'work_id': row['work_id']}, {'role': mapping[row['role']]})
                counts['routing'] += 1
        for before in requests:
            row = tx.get('role_requests', {'request_id': before['request_id']})
            if row and snapshot_uri(row.get('source')) != row.get('source'):
                tx.update('role_requests', {'request_id': row['request_id']}, {'source': snapshot_uri(row['source'])})
                counts['role_requests'] += 1
        for before in pending:
            row = tx.get('transitions', {'transition_id': before['transition_id']})
            if row and row['state'] == 'pending' and row['kind'] == 'launch':
                payload = row['payload']
                updated_payload = {**payload}
                if payload.get('authored_role_uri') in mapping:
                    updated_payload['authored_role_uri'] = mapping[payload['authored_role_uri']]
                if snapshot_uri(payload.get('role_snapshot')) != payload.get('role_snapshot'):
                    updated_payload['role_snapshot'] = snapshot_uri(payload['role_snapshot'])
                if updated_payload != payload:
                    tx.update('transitions', {'transition_id': row['transition_id']}, {'payload': updated_payload})
                    counts['pending_launches'] += 1
    return counts


def _migrated_assignment(ctx: Context, row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    snapshot = cast(dict[str, Any], row.get('role_snapshot') or {})
    legacy = str(row['authored_role_uri']).startswith('metaform://role/') and snapshot.get('specialist') is not False
    if legacy or (snapshot.get('specialist') is True and str(snapshot.get('uri')).startswith('metaform://role/')):
        changed = migrate_specialist_references(ctx, work_ids=[str(row['work_id'])])
        if changed['assignments']:
            with own(ctx).tables(write=False) as tx:
                return tx.get('assignments', {'assignment_id': row['assignment_id']})
    return row


# Version 2 adds an assignment's `role_snapshot` and `attempt`; version 3 its `findings_filed`, the tickets its
# assessment's findings landed on; version 5 its `persons_start`, a delivery the person started; version 6 adds
# execution episodes, separate plans and retained reviewed sources/findings. Additions are nullable or separate
# tables, so version 1's code still reads and writes its tables, STORE-029.
TABLES = Tables(version=6, compatible_from=1, tables=(
    *episodes.TABLES,
    routing.TABLE,
    Table('assignments', key=('assignment_id',), columns=(
        Column('assignment_id', required=True), Column('work_id', required=True),
        Column('root_work_id', required=True), Column('team_id', required=True),
        Column('gc_assignment_id'), Column('parent_assignment_id'), Column('reviewed_assignment_id'),
        Column('successor_assignment_id'),
        Column('owner_session_id'), Column('authored_role_uri', required=True), Column('role_snapshot', 'json'),
        Column('attempt', 'int', default=1),
        Column('execution_role', required=True, default='worker'), Column('functional_locations', 'json'),
        Column('task', required=True), Column('requested_result', required=True), Column('candidate', 'json'),
        Column('specification', 'json'), Column('plan', 'json'), Column('reviewed_snapshot', 'json'),
        Column('findings', 'json'), Column('mode', required=True), Column('state', required=True),
        Column('return_to', 'json'), Column('pending_direction', 'json'), Column('result', 'json'),
        Column('evidence', 'json'), Column('last_check_in', 'json'), Column('stop', 'json'), Column('stop_history', 'json'),
        Column('findings_filed', 'json'), Column('persons_start', 'bool', default=False),
        Column('created', required=True), Column('updated', required=True)), indexes=(
            Index(('work_id',), unique=True), Index(('owner_session_id',)), Index(('team_id',)),
            Index(('parent_assignment_id',)), Index(('reviewed_assignment_id',)), Index(('state',)))),
    Table('sessions', key=('session_id',), columns=(
        Column('session_id', required=True), Column('assignment_id', required=True), Column('runner'),
        Column('created', required=True)), indexes=(Index(('assignment_id',)), Index(('runner',)))),
    Table('transitions', key=('transition_id',), columns=(
        Column('transition_id', required=True), Column('assignment_id', required=True),
        Column('work_id', required=True), Column('kind', required=True), Column('state', required=True),
        Column('payload', 'json', required=True), Column('delivery', 'json'),
        Column('created', required=True), Column('updated', required=True)),
        indexes=(Index(('state',)), Index(('work_id', 'state')), Index(('assignment_id',)))),
    Table('role_requests', key=('request_id',), columns=(
        Column('request_id', required=True), Column('caller_assignment_id', required=True),
        Column('gc_assignment_id', required=True), Column('role', required=True), Column('purpose', required=True),
        Column('task', required=True), Column('requested_result', required=True), Column('context', 'json'),
        Column('functional_locations', 'json'), Column('creator_assignment_id'), Column('child_assignment_id'),
        Column('state', required=True), Column('source', 'json'), Column('created', required=True)),
        indexes=(Index(('gc_assignment_id',)), Index(('caller_assignment_id',)),
                 Index(('role', 'state')), Index(('creator_assignment_id', 'state')))),
    Table('changes', key=('change_id',), columns=(
        Column('change_id', required=True), Column('assessment_assignment_id', required=True),
        Column('specification', 'json', required=True), Column('previous_revision', required=True),
        Column('current_revision'), Column('before_content', required=True), Column('content', required=True),
        Column('reason', required=True), Column('observed_limitation', required=True),
        Column('affected_work_ids', 'json', required=True), Column('mode_at_publication', required=True),
        Column('source', required=True), Column('user_instruction', 'json'), Column('state', required=True),
        Column('user_message_state', required=True),
        Column('created', required=True), Column('updated', required=True)),
        indexes=(Index(('state',)), Index(('assessment_assignment_id',)),)),
))


def service(ctx: Context, kind: str) -> Any:
    providers = provided(ctx.folder, kind)
    if len(providers) != 1:
        owners = ', '.join(owner for owner, _ in providers) or 'none'
        raise Stop(f'{kind} needs one active provider; found {owners}.', 'metaform status')
    return providers[0][1]


def verb(ctx: Context, module_id: str, operation_name: str, **nouns: Any) -> Any:
    module = next((one for one in surface(ctx.folder) if one.id == module_id), None)
    operation = next((one for one in module.verbs if one.name == operation_name), None) if module else None
    if operation is None:
        raise Stop(f'{module_id} {operation_name} is not available on this project surface.', 'metaform status')
    target = context(module_id, ctx.folder, project=ctx.project, nouns=nouns, surface=ctx.surface,
                     client=ctx.client, session=ctx.session, identity=ctx.identity)
    return call(operation.run, target)


def row_for(tx: TableTx, *, assignment_id: str | None = None, work_id: str | None = None,
            session_id: str | None = None) -> dict[str, Any] | None:
    if assignment_id:
        return tx.get('assignments', {'assignment_id': assignment_id})
    if work_id:
        rows = tx.rows('assignments', {'work_id': work_id}, limit=1).results
        return rows[0] if rows else None
    if session_id:
        binding = tx.get('sessions', {'session_id': session_id})
        if binding:
            return tx.get('assignments', {'assignment_id': binding['assignment_id']})
        bindings = tx.rows('sessions', {'runner': session_id}, limit=1).results
        if bindings:
            return tx.get('assignments', {'assignment_id': bindings[0]['assignment_id']})
        rows = tx.rows('assignments', {'owner_session_id': session_id}, limit=1).results
        return rows[0] if rows else None
    return None


def touch(tx: TableTx, assignment: Mapping[str, Any], kind: str) -> None:
    tx.concern(work_id=str(assignment['work_id']), session_id=assignment.get('owner_session_id'),
               kind=f'orchestration.{kind}')


def update(tx: TableTx, assignment: Mapping[str, Any], **fields: Any) -> dict[str, Any]:
    row = tx.update('assignments', {'assignment_id': assignment['assignment_id']}, {**fields, 'updated': now()})
    assert row is not None
    touch(tx, row, 'assignment')
    return row


def message_text(kind: str, payload: Mapping[str, Any]) -> str | None:
    """The text a send or user message delivers, as dispatch's transport reads it; None for structured envelopes."""
    if kind not in ('send', 'user_message'):
        return None
    text = payload.get('text') or payload.get('body') or payload.get('summary')
    return text if isinstance(text, str) and text.strip() else None


def transition(tx: TableTx, assignment: Mapping[str, Any], kind: str, payload: Mapping[str, Any],
               key: str) -> dict[str, Any]:
    ident = identity(str(assignment['assignment_id']), kind, key)
    prior = tx.get('transitions', {'transition_id': ident})
    if prior:
        return prior
    text = message_text(kind, payload)
    sender = str(payload.get('sender_assignment_id') or '')
    if text is not None and (kind == 'user_message' or sender):
        # The same result from the same assignment reaches its recipient once, whatever key, path or process queued it
        # again, told apart by its kind; a user message is told apart by the assignment returning it, so two works'
        # alike results both reach the person. A dispatch note, reply or broadcast carries no sender assignment and is
        # keyed by its own id alone, so the same words said again, by anyone, arrive again.
        route = cast(Mapping[str, Any], payload.get('return_to') or {})
        recipient = (str(assignment['assignment_id']), sender, str(payload.get('kind') or '')) \
            if kind == 'send' else ('user', str(route.get('session_id') or ''), str(assignment['assignment_id']))
        ident = identity(*recipient, kind, 'text', fingerprint(text))
        prior = tx.get('transitions', {'transition_id': ident})
        if prior:
            return prior
    row = tx.insert('transitions', {'transition_id': ident, 'assignment_id': assignment['assignment_id'],
                    'work_id': assignment['work_id'], 'kind': kind, 'state': 'pending',
                    'payload': dict(payload), 'delivery': None, 'created': now(), 'updated': now()})
    touch(tx, assignment, kind)
    return row


def requested(ctx: Context, assignment_id: str | None = None) -> dict[str, Any]:
    store = own(ctx)
    session = ctx.session or os.environ.get('METAFORM_SESSION')
    with store.tables(write=False) as tx:
        held = row_for(tx, assignment_id=assignment_id, session_id=session)
        caller = row_for(tx, session_id=session)
        bound = tx.get('sessions', {'session_id': held['owner_session_id']}) if held else None
    held = _migrated_assignment(ctx, held)
    if held is None:
        raise Stop('No recorded assignment for this call.', 'metaform orchestration claim <work>')
    if session and (caller is None or caller['assignment_id'] != held['assignment_id']):
        raise Stop('This assignment belongs to another agent.', 'metaform orchestration team')
    if session and session not in (held['owner_session_id'], (bound or {}).get('runner')):
        raise Stop('This assignment belongs to another agent.', 'metaform orchestration team')
    if held.get('stop'):
        raise Stop('This assignment is stopped.', f'metaform orchestration inspect {held["assignment_id"]}')
    return held


def descendants(tx: TableTx, root: Mapping[str, Any], *, assessments: bool = False) -> list[dict[str, Any]]:
    """Follow recorded responsibilities across correction teams without sweeping unrelated work."""
    found: dict[str, dict[str, Any]] = {}
    remaining = [dict(root)]
    while remaining:
        one = remaining.pop()
        ident = one['assignment_id']
        if ident in found:
            continue
        found[ident] = one
        remaining.extend(tx.rows('assignments', {'parent_assignment_id': ident}, limit=0).results)
        if assessments:
            remaining.extend(tx.rows('assignments', {'reviewed_assignment_id': ident}, limit=0).results)
    return list(found.values())


def related(tx: TableTx, assignment: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Delivery relationships are visible without representing an assessor or corrective GC as a swarm member."""
    reviews = tx.rows('assignments', {'reviewed_assignment_id': assignment['assignment_id']}, limit=0).results
    children = tx.rows('assignments', {'parent_assignment_id': assignment['assignment_id']}, limit=0).results
    return {'independent_assessments': list(reviews), 'related_corrections': [one for one in children if
            one['authored_role_uri'] == 'metaform://role/gc' and one['gc_assignment_id'] == one['assignment_id']]}


def location(store: Store, at: Any, parent: Mapping[str, Any] | None = None) -> tuple[Node, list[dict[str, Any]]]:
    if at is None and parent is not None:
        found = list(parent['functional_locations'] or [])
        at = found[0] if found else None
    if isinstance(at, str):
        node = Node('element', at)
    elif isinstance(at, Mapping):
        fields = dict(cast(Mapping[str, Any], at))
        if fields.get('kind') == 'join':
            node = Node('join', str(fields.get('id') or fields.get('address') or ''))
        else:
            node = Node('element', str(fields.get('address') or fields.get('id') or ''))
    else:
        raise Stop('An assignment needs an existing functional element or join.', 'metaform map roots')
    actual = store.node(node)
    if actual is None:
        raise Stop(f'No functional {node.kind} {node.id}.', 'metaform map roots')
    address = node.id
    if node.kind == 'element':
        element = store.element(node.id)
        address = element.address if element is not None else node.id
    return node, [{'kind': node.kind, 'id': node.id, 'address': address}]


def new_assignment(tx: TableTx, work: WorkRecord, role: str, *, ident: str | None = None,
                   parent: Mapping[str, Any] | None = None, review: Mapping[str, Any] | None = None,
                   task: str, result: str, locations: Sequence[Mapping[str, Any]],
                   mode: str = 'adaptive', specification: Any = None, candidate: Any = None,
                   session: str | None = None, return_to: Any = None, persons: bool = False) -> dict[str, Any]:
    """`persons`: the person started this delivery, themselves or through their system agent on their word, so its
    launches, and those of every assignment under it, are no automatic starts: Full Auto off does not hold them."""
    ident = ident or uuid.uuid4().hex
    root = work.id if parent is None else parent['root_work_id']
    team = ident if parent is None else parent['team_id']
    gc = ident if parent is None else parent.get('gc_assignment_id')
    if review is not None:
        gc = review['gc_assignment_id'] or review['assignment_id']
    made = tx.insert('assignments', {'assignment_id': ident, 'work_id': work.id, 'root_work_id': root,
        'team_id': team, 'gc_assignment_id': gc, 'parent_assignment_id': None if parent is None else
        parent['assignment_id'], 'reviewed_assignment_id': None if review is None else review['assignment_id'],
        'successor_assignment_id': None,
        'owner_session_id': session, 'authored_role_uri': role if role.startswith('metaform://') else f'metaform://role/{role}',
        'execution_role': 'worker',
        'functional_locations': [dict(one) for one in locations], 'task': task, 'requested_result': result,
        'candidate': candidate, 'specification': specification, 'plan': None,
        'reviewed_snapshot': None if review is None else {
            'assignment_id': review['assignment_id'], 'work_id': review['work_id'],
            'task_revision': fingerprint(str(review['task'])), 'task': review['task'],
            'specification': review.get('specification'), 'candidate': candidate or review.get('candidate')},
        'findings': [], 'mode': mode,
        'state': 'running' if session else 'queued', 'return_to': return_to,
        'pending_direction': list((parent or review or {}).get('pending_direction') or []),
        'result': None, 'evidence': [], 'last_check_in': None, 'stop': None, 'stop_history': [],
        'persons_start': persons or bool((parent or review or {}).get('persons_start')),
        'created': now(), 'updated': now()})
    touch(tx, made, 'assignment')
    if session:
        tx.insert('sessions', {'session_id': session, 'assignment_id': ident, 'runner': None, 'created': now()})
    return made


def review_snapshot(ctx: Context, reviewed: Mapping[str, Any], candidate: Any = None) -> dict[str, Any]:
    """Retain the actual requirements read for an assessment, including externally edited specifications."""
    from .specifications import read, specification
    snapshot: dict[str, Any] = {'assignment_id': reviewed['assignment_id'], 'work_id': reviewed['work_id'],
        'task': reviewed['task'], 'task_revision': fingerprint(str(reviewed['task'])),
        'candidate': candidate if candidate is not None else reviewed.get('candidate'),
        'sources': list(own(ctx).work_sources(str(reviewed['root_work_id']), contents=False)),
        'direction_references': [str(one.get('id') or one.get('revision') or one.get('change_id'))
                                 for one in cast(list[dict[str, Any]], reviewed.get('pending_direction') or [])
                                 if one.get('id') or one.get('revision') or one.get('change_id')]}
    try:
        spec = specification(ctx, reviewed.get('specification'), str(reviewed['work_id']))
        content, revision = read(ctx, spec)
        snapshot.update(specification={**spec, 'revision': revision}, requirements_revision=revision,
                        requirements=content)
    except (Stop, OSError, UnicodeError) as error:
        # An unavailable reference remains visible evidence. It cannot silently block an assessment.
        snapshot.update(specification=reviewed.get('specification'), requirements_error=str(error))
    return snapshot


def reviewed_revision(assessment: Mapping[str, Any]) -> dict[str, Any]:
    """Reference the retained reviewed source without copying it into every finding and direction."""
    snapshot = cast(Mapping[str, Any], assessment.get('reviewed_snapshot') or {})
    return {'assessment_assignment_id': assessment['assignment_id'],
            'task_revision': snapshot.get('task_revision'),
            'requirements_revision': snapshot.get('requirements_revision'),
            'read': f'metaform orchestration inspect assignment={assessment["assignment_id"]}'}


def role_options(request: Mapping[str, Any]) -> dict[str, Any]:
    supplied = cast(dict[str, Any], request.get('context') or {})
    return cast(dict[str, Any], supplied.get('context') or {})


def resolve(ctx: Context, role: str) -> dict[str, Any]:
    found = service(ctx, 'agent.role').resolve(ctx, role)
    if role.startswith('metaform://') and found.get('specialist') is not None and found.get('uri') != role:
        raise Stop(f'{agent_role_name(role)} is available at {found["uri"]}.', 'metaform agents specialists')
    return found


def resolved_role(ctx: Context, role: str) -> str:
    name = agent_role_name(role)
    found = resolve(ctx, role)
    if found.get('problems'):
        raise Stop(f'Role {name} cannot be resolved: {found["problems"]}', f'metaform agents resolve {name}')
    return name


def current_mode(tx: TableTx, assignment: Mapping[str, Any]) -> str:
    root = row_for(tx, assignment_id=assignment.get('gc_assignment_id'))
    return str((root or assignment)['mode'])


class Orchestration:
    """Public provider used by dispatch, MCP context delivery and module UI reads."""

    def runtime(self, ctx: Context, work_id: str,
                fallback: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Choose once at assignment. Missing Jev decisions belong to the Facilitator's full model."""
        from .runtime import TASKS, choose, strengths_of
        transports = [one for _, one in provided(ctx.folder, 'orchestration.transport')
                      if hasattr(one, 'runtime_catalog')]
        if not transports:
            return {'state': 'unmanaged'}
        transport = transports[0]
        record = own(ctx).ticket(work_id).work
        kept = transport.runtime_settings(ctx, work_id)
        decision = cast(dict[str, Any], kept.get('decision') or {})
        overrides = cast(dict[str, Any], decision.get('overrides') or {})
        if not overrides and decision.get('decider') == 'person':
            overrides = {key: kept[key] for key in ('agent', 'model', 'effort') if kept.get(key)}
        if not decision and kept.get('agent'):
            overrides = {'agent': kept['agent']}
        current = fingerprint(record.task or '')
        if fallback is not None:
            caller = requested(ctx, ctx.nouns.get('assignment'))
            with own(ctx).tables(write=False) as tx:
                commissions = tx.rows('role_requests', {
                    'creator_assignment_id': caller['assignment_id'], 'state': 'commissioned'}, limit=0).results
                allowed = any((row_for(tx, assignment_id=one['caller_assignment_id']) or {}).get('work_id') == work_id
                              for one in commissions)
            if caller['authored_role_uri'] not in FACILITATORS or not allowed:
                raise Stop('Only the commissioned Facilitator records a full-model runtime choice.', HELP)
        recorded_task = decision.get('task_fingerprint')
        if all(kept.get(key) for key in ('agent', 'model')) and (
                recorded_task == current or (recorded_task is None and not decision.get('task_type'))):
            catalog = transport.runtime_catalog(ctx, work_id)
            offered = cast(dict[str, Any], catalog.get(kept['agent']) or {})
            if offered and not offered.get('models') and decision.get('decider') == 'person':
                # Manual settings made before this harness advertised its controls remain unchecked.
                # Startup reads the actual controls and reports configuration errors in their own terms.
                return {'state': 'selected', 'choice': kept}
            if (kept['model'] in offered.get('models', {})
                    and (kept.get('effort') in offered.get('efforts', [])
                         or (not offered.get('efforts') and kept.get('effort') is None))):
                return {'state': 'selected', 'choice': kept}
        catalog = transport.runtime_catalog(ctx, work_id)
        # Explicit choices remain authoritative. A plan is separate evidence, not a replacement request.
        with own(ctx).tables(write=False) as tx:
            assigned = row_for(tx, work_id=work_id)
        plan = (assigned or {}).get('plan')
        fields = {**record.to_dict(), 'plan': plan} if plan else record
        chosen = choose(ctx, fields, catalog, fallback=fallback, overrides=overrides)
        if chosen is None:
            from .runtime import TASKS, rejection_reason, strengths_of
            needed = {'state': 'needs_choice', 'work_id': work_id, 'catalog': catalog,
                      'strengths': strengths_of(ctx, catalog), 'task_types': dict(TASKS)}
            if fallback is not None:
                needed['reason'] = rejection_reason(fallback, catalog, overrides)
            return needed
        chosen['task_fingerprint'] = current
        saved = transport.keep_runtime(ctx, work_id, chosen)
        return {'state': 'selected', 'choice': saved}

    def prepare_runtime(self, ctx: Context, assignment: Mapping[str, Any], *, restart: bool = False) -> bool:
        """Commission existing fallback work before launching an unconfigured specialist."""
        store = own(ctx)
        with store.tables(write=False) as tx:
            assignment = row_for(tx, assignment_id=assignment['assignment_id']) or assignment
        record = store.ticket(str(assignment['work_id'])).work
        if assignment.get('stop') or record.done:
            return False
        if assignment['authored_role_uri'] in FACILITATORS:
            return True
        with own(ctx).tables(write=False) as tx:
            pending = tx.rows('role_requests', {'caller_assignment_id': assignment['assignment_id']}, limit=0).results
            pending = [one for one in pending
                       if one['state'] == 'commissioned' and role_options(one).get('assign_in_place')]
            creators = [row_for(tx, assignment_id=one['creator_assignment_id']) for one in pending]
        if pending:
            if not restart and any(one is None for one in creators) and not record.held:
                # Missing ownership cannot publish a choice. Recreate only absent helpers, never stopped ones.
                with store.atomic(), store.tables() as tx:
                    current = row_for(tx, assignment_id=assignment['assignment_id'])
                    gc = row_for(tx, assignment_id=assignment.get('gc_assignment_id'))
                    work = store.ticket(str(assignment['work_id'])).work
                    if (current and not current.get('stop') and current['state'] not in ENDED
                            and gc and not gc.get('stop') and not work.done and not work.held):
                        for request in pending:
                            latest = tx.get('role_requests', {'request_id': request['request_id']})
                            if (latest and latest['state'] == 'commissioned'
                                    and row_for(tx, assignment_id=latest['creator_assignment_id']) is None):
                                self._commission(tx, store, current, latest)
                return False
            if restart and not assignment.get('stop') and all(
                    one is None or one.get('stop') or one['state'] in ENDED for one in creators):
                # An explicit root restart authorizes replacement work. Old stopped descendants remain stopped.
                with own(ctx).atomic(), own(ctx).tables() as tx:
                    for request in pending:
                        tx.update('role_requests', {'request_id': request['request_id']}, {'state': 'superseded'})
                    request = pending[0]
                    self.request_role(replace(ctx, nouns={
                        'task': request['task'], 'key': 'restart:' + request['request_id'],
                        'context': role_options(request)}), assignment, request['role'])
            return False  # Its existing Facilitator owns both expertise and runtime before publication.
        if not assignment.get('role_snapshot'):
            placeholder = (assignment['authored_role_uri'] == 'metaform://role/gc'
                           and not assignment.get('parent_assignment_id')
                           and not assignment.get('reviewed_assignment_id'))
            resolution = {'missing': True} if placeholder else resolve(ctx, assignment['authored_role_uri'])
            if resolution.get('missing'):
                # Restore lost expertise requests without replacing a surviving creator or its publication ID.
                with store.atomic(), store.tables() as tx:
                    current = row_for(tx, assignment_id=assignment['assignment_id'])
                    work = store.ticket(str(assignment['work_id'])).work
                    if (not current or current.get('stop') or current['state'] in ENDED
                            or work.done or work.held):
                        return False
                    if (current.get('role_snapshot')
                            or current['authored_role_uri'] != assignment['authored_role_uri']):
                        return False
                    requests = tx.rows('role_requests', {
                        'caller_assignment_id': current['assignment_id']}, limit=0).results
                    if any(one['state'] == 'commissioned' and role_options(one).get('assign_in_place')
                           for one in requests):
                        return False
                    children = tx.rows('assignments', {
                        'parent_assignment_id': current['assignment_id']}, limit=0).results
                    orphaned = [one for one in children if one['authored_role_uri'] in FACILITATORS
                                and cast(dict[str, Any], one.get('return_to') or {}).get('role_request_id')
                                and not tx.get('role_requests', {
                                    'request_id': one['return_to']['role_request_id']})]
                    creator = max(orphaned, key=lambda one: (
                        not one.get('stop') and one['state'] not in ENDED, one['created'], one['assignment_id']),
                        default=None)
                    if creator and (creator.get('stop') or creator['state'] in ENDED):
                        return False
                    self.request_role(replace(ctx, nouns={
                        'task': work.task or '', 'key': 'expertise:' + uuid.uuid4().hex,
                        'context': {'assign_in_place': True, 'choose_name': placeholder}}), current,
                        '' if placeholder else agent_role_name(str(current['authored_role_uri'])),
                        creator=creator)
                return False
            if resolution.get('problems'):
                raise Stop(f'Cannot assign {assignment["authored_role_uri"]}: {resolution["problems"]}', HELP)
        work_id = str(assignment['work_id'])
        selected = self.runtime(ctx, work_id)
        if selected['state'] == 'unmanaged':
            return True
        if selected['state'] != 'selected':
            request_ctx = replace(ctx, nouns={
                'task': record.task or '', 'key': 'runtime:' + fingerprint(record.task or ''),
                'context': {'assign_in_place': True, 'runtime_only': True}})
            self.request_role(request_ctx, assignment,
                              agent_role_name(str(assignment['authored_role_uri'])))
            return False
        choice = selected['choice']
        decision = choice.get('decision') or choice
        plan = cast(dict[str, Any], assignment.get('plan') or {})
        revision = fingerprint(record.task or '')
        if (decision.get('task_type') != 'needs_plan'
                or assignment['authored_role_uri'] == 'metaform://role/planner'
                or plan.get('revision') == revision or plan.get('continued_for') == revision):
            return True
        # A distinct planning contribution returns evidence once for this request revision.
        task = prompt_files.served(resources.files('metaform.modules.orchestration'), 'runtime_plan',
                                   work=work_id)
        inherited = ({**{key: choice.get(key) for key in ('agent', 'model', 'effort')},
                      **decision, 'task_type': 'planning'}
                     if decision.get('decider') in ('jev', 'facilitator') and not decision.get('overrides') else None)
        self._delegate(replace(ctx, nouns={
            'assignment': assignment['assignment_id'], 'role': 'planner', 'task': task,
            'result': 'Return the implementation approach, dependencies and evidence needed to establish the result.',
            'key': 'runtime-plan:' + revision, 'wait': True,
            '_runtime_plan': {'revision': revision}, '_runtime_choice': inherited}), assignment,
            waiting=True, internal=True)
        return False

    def route(self, ctx: Context, work_id: str, *, refresh: bool = False) -> dict[str, Any]:
        return routing.route(ctx, work_id, refresh=refresh)

    def route_pending(self, ctx: Context) -> list[dict[str, Any]]:
        return routing.pending(ctx)

    def queue_routing(self, ctx: Context, work_ids: list[str]) -> None:
        routing.queue(ctx, work_ids)

    def routing_waiting(self, ctx: Context) -> bool:
        return routing.waiting(ctx)

    def selected_specialist(self, ctx: Context, work_id: str) -> str | None:
        return routing.selected(ctx, work_id)

    def creator_running(self, ctx: Context, work_id: str) -> bool:
        """Whether the creator a ticket's routing waits on, state creating, is at work: a commissioned request of the
        ticket's assignment names a creator assignment that is running. One commissioned and never launched, as Full
        Auto off leaves it, or one that ended, is not."""
        with own(ctx).tables(write=False) as tx:
            caller = row_for(tx, work_id=work_id)
            if caller is None:
                return False
            for request in tx.rows('role_requests', {'caller_assignment_id': caller['assignment_id']}, limit=0).results:
                if request['state'] != 'commissioned' or not request.get('creator_assignment_id'):
                    continue
                creator = row_for(tx, assignment_id=str(request['creator_assignment_id']))
                if creator is not None and creator['state'] == 'running':
                    return True
        return False

    def select_registered(self, ctx: Context, work_id: str, role_uri: str, reason: str) -> bool:
        """Jev's pick of registered expertise for a ticket whose routing waited on a creator that does not run: each
        waiting in-place request is published from the registry, as the Facilitator's publication does it, the creator
        it waited on is stopped and its ticket cancelled, and the original ticket continues on its own assignment with
        its launch. False when no request waits or the role is not a registered specialist. 2026-10-20: a ticket sat for
        hours at 'Facilitator is selecting expertise' with no Facilitator running and Jev able to choose."""
        store = own(ctx)
        registered = resolve(ctx, role_uri)
        if registered.get('missing') or registered.get('problems') or not registered.get('specialist'):
            return False
        released = False
        with store.atomic(), store.tables() as tx:
            caller = row_for(tx, work_id=work_id)
            if caller is None:
                return False
            for request in tx.rows('role_requests', {'caller_assignment_id': caller['assignment_id']}, limit=0).results:
                if request['state'] != 'commissioned' or not role_options(request).get('assign_in_place'):
                    continue
                if role_options(request).get('runtime_only'):
                    continue  # Choosing expertise cannot replace the missing full-model runtime decision.
                creator_id = request.get('creator_assignment_id')
                creator = row_for(tx, assignment_id=str(creator_id)) if creator_id else None
                if creator is not None and creator['state'] == 'running':
                    continue  # the Facilitator is at work: its publication continues this ticket
                caller = update(tx, caller, authored_role_uri=registered['uri'], role_snapshot=registered,
                                state='queued')
                receipt = {'source': 'existing', 'match_reason': reason, 'by': 'jev'}
                tx.update('role_requests', {'request_id': request['request_id']}, {
                    'state': 'published', 'role': registered['name'], 'child_assignment_id': caller['assignment_id'],
                    'source': registered, 'context': {**request['context'], 'publication': receipt}})
                if creator is not None and creator['state'] not in ENDED:
                    stop = {'by': 'routing', 'direction': None, 'at': now(), 'every': False}
                    update(tx, creator, state='stopped', stop=stop,
                           stop_history=[*(creator.get('stop_history') or []), stop])
                    for event in tx.rows('transitions', {'assignment_id': creator['assignment_id']}, limit=0).results:
                        if event['state'] == 'pending':
                            tx.update('transitions', {'transition_id': event['transition_id']},
                                      {'state': 'cancelled', 'updated': now()})
                    if not store.ticket(str(creator['work_id'])).work.done:
                        store.finish_work(str(creator['work_id']), 'Not needed: registered expertise was selected for '
                                          'the ticket it was commissioned for.', outcome='cancelled')
                if tx.get('routing', {'work_id': work_id}):
                    tx.update('routing', {'work_id': work_id}, {'state': 'selected', 'role': registered['uri'],
                                                                 'reason': reason, 'updated': now()})
                tx.concern(work_id=work_id, kind='orchestration.routing')
                if not caller.get('stop'):
                    transition(tx, caller, 'launch', {'role_request_id': request['request_id']}, 'initial')
                released = True
        return released

    def routing_status(self, ctx: Context, work_id: str) -> dict[str, Any] | None:
        with own(ctx).tables(write=False) as tx:
            assignment = row_for(tx, work_id=work_id)
            if assignment:
                requests = tx.rows('role_requests', {'caller_assignment_id': assignment['assignment_id']}, limit=0).results
                waiting = [one for one in requests
                           if one['state'] == 'commissioned' and role_options(one).get('assign_in_place')]
                if waiting:
                    reason = ('Facilitator is choosing agent, model and thinking level.'
                              if all(role_options(one).get('runtime_only') for one in waiting)
                              else 'Facilitator is selecting expertise.')
                    return {'state': 'creating', 'role': None, 'reason': reason}
                return {'state': assignment['state'], 'role': assignment['authored_role_uri']}
            row = tx.get('routing', {'work_id': work_id})
            return {key: row.get(key) for key in ('state', 'role', 'reason')} if row else None

    def ticket_edited(self, ctx: Context, work_id: str, revision: str, *, source: str = 'unknown',
                      source_reference: str | None = None) -> None:
        """Keep the operative task current and deliver a reference to its changed requirements once."""
        store = own(ctx)
        record = store.ticket(work_id).work
        sources = store.work_sources(work_id, contents=False)
        source_reference = source_reference or (sources[-1]['source_id'] if sources else None)
        with store.tables() as tx:
            assignment = row_for(tx, work_id=work_id)
            if assignment and assignment['state'] not in ENDED:
                author = {'user': 'the user', 'agent': 'an agent', 'change_order': 'an adaptive change order'}.get(
                    source, 'a recorded edit')
                body = f'Ticket {work_id}: {author} revised its execution description. Read the current ticket and source references before continuing.'
                kind = 'user_direction' if source == 'user' else 'ticket_revision'
                direction = {'kind': kind, 'body': body, 'at': now(), 'revision': revision,
                             'source': source, 'source_reference': source_reference}
                assignment = update(tx, assignment, task=record.task or '',
                    requested_result=record.task if assignment['requested_result'] == assignment['task']
                    else assignment['requested_result'],
                    pending_direction=[*(assignment.get('pending_direction') or []), direction])
                transition(tx, assignment, 'send', {'text': body, 'kind': kind, 'revision': revision,
                                                       'source': source, 'source_reference': source_reference},
                           f'ticket-edit:{revision}')

    def assignment(self, ctx: Context, work_id: str | None = None, session_id: str | None = None,
                   assignment_id: str | None = None) -> dict[str, Any] | None:
        with own(ctx).tables(write=False) as tx:
            row = row_for(tx, assignment_id=assignment_id, work_id=work_id,
                          session_id=session_id or (ctx.session if not (assignment_id or work_id) else None))
        return _migrated_assignment(ctx, row)

    def members(self, ctx: Context, team_id: str) -> list[dict[str, Any]]:
        with own(ctx).tables(write=False) as tx:
            rows = list(tx.rows('assignments', {'team_id': team_id}, limit=0).results)
        return [cast(dict[str, Any], _migrated_assignment(ctx, row)) for row in rows]

    def assignments(self, ctx: Context) -> list[dict[str, Any]]:
        """Enumerate registered assignments, including work awaiting its first session."""
        with own(ctx).tables(write=False) as tx:
            rows = list(tx.rows('assignments', limit=0).results)
        return [cast(dict[str, Any], _migrated_assignment(ctx, row)) for row in rows]

    def related(self, ctx: Context, assignment_id: str) -> dict[str, list[dict[str, Any]]]:
        with own(ctx).tables(write=False) as tx:
            held = row_for(tx, assignment_id=assignment_id)
            return related(tx, held) if held is not None else {'independent_assessments': [], 'related_corrections': []}

    def same_team(self, ctx: Context, work_a: str, work_b: str) -> bool:
        with own(ctx).tables(write=False) as tx:
            first, second = row_for(tx, work_id=work_a), row_for(tx, work_id=work_b)
            if not first or not second:
                return False
            if first['team_id'] == second['team_id']:
                return True
            gc_id = first.get('gc_assignment_id')
            if not gc_id or gc_id != second.get('gc_assignment_id'):
                return False
            # An assessment and the specialists it calls can examine the reviewed references. Their own
            # team-root review link authorizes coordinated access, never GC swarm control over that team.
            roots = [row_for(tx, assignment_id=one['team_id']) for one in (first, second)]
            return any(root and root.get('reviewed_assignment_id') == gc_id for root in roots)

    def owns(self, ctx: Context, sender_session: str, recipient_session: str) -> bool:
        with own(ctx).tables(write=False) as tx:
            sender = row_for(tx, session_id=sender_session)
            recipient = row_for(tx, session_id=recipient_session)
        return bool(sender and recipient and sender['gc_assignment_id'] == sender['assignment_id'] and
                    recipient['gc_assignment_id'] == sender['assignment_id'] and
                    sender['team_id'] == recipient['team_id'] and
                    recipient['assignment_id'] != sender['assignment_id'])

    def bind(self, ctx: Context, assignment_id: str, session_id: str,
             runner: str | None = None, persons: bool = False) -> dict[str, Any]:
        """Bind a session to its assignment. A delivery whose specialist role is still being made waits for the
        publication, which starts it; the person's own start, `persons`, runs now as a worker with no role, and the
        role is theirs at the next session once published (2026-10-20: their Start failed to bind and ended)."""
        with own(ctx).tables(write=False) as tx:
            requests = tx.rows('role_requests', {'caller_assignment_id': assignment_id}, limit=0).results
            if not persons and any(one['state'] == 'commissioned' and role_options(one).get('assign_in_place')
                                   for one in requests):
                raise Stop('The ticket is waiting for its specialist role to be published.', HELP)
        before = self.assignment(ctx, assignment_id=assignment_id)
        snapshot = (before or {}).get('role_snapshot')
        if before and not snapshot:
            snapshot = resolve(ctx, before['authored_role_uri'])
            if snapshot.get('missing') or snapshot.get('problems'):
                if not persons:
                    raise Stop(f'Cannot start {before["authored_role_uri"]}: {snapshot.get("problems")}', HELP)
                snapshot = None  # the person's worker runs with no role until one is published
        with own(ctx).tables() as tx:
            held = row_for(tx, assignment_id=assignment_id)
            if held is None:
                raise Stop(f'No assignment {assignment_id}.', HELP)
            if held.get('stop'):
                raise Stop('The assignment was stopped before this launch.', HELP)
            bound = tx.get('sessions', {'session_id': session_id})
            if bound and bound['assignment_id'] != assignment_id:
                previous = row_for(tx, assignment_id=bound['assignment_id'])
                target_episode = episodes.attach(tx, held, now())
                previous_episode = episodes.attach(tx, previous, now()) if previous else None
                if not previous or previous.get('stop') or previous['state'] == 'running' or not previous_episode \
                        or previous_episode['episode_id'] != target_episode['episode_id']:
                    raise Stop('The session is already bound to another active workstream.', HELP)
                if previous['authored_role_uri'] != held['authored_role_uri']:
                    raise Stop('Different responsibilities use separate ACP contexts.', HELP)
                episodes.bound(tx, previous, session_id, bound.get('runner'), now())
                tx.update('sessions', {'session_id': session_id}, {'assignment_id': assignment_id})
            if bound:
                tx.update('sessions', {'session_id': session_id}, {'runner': runner or bound['runner']})
            else:
                tx.insert('sessions', {'session_id': session_id, 'assignment_id': assignment_id,
                                      'runner': runner, 'created': now()})
            bound_assignment = update(tx, held, owner_session_id=session_id, state='running',
                                      role_snapshot=held.get('role_snapshot') or snapshot)
            episodes.bound(tx, bound_assignment, session_id, runner, now())
            for event in tx.rows('transitions', {'assignment_id': assignment_id}, limit=0).results:
                if event['kind'] == 'launch' and event['state'] == 'pending':
                    tx.update('transitions', {'transition_id': event['transition_id']}, {
                        'state': 'delivered', 'delivery': {'state': 'running', 'session_id': session_id,
                                                         'runner': runner}, 'updated': now()})
            return bound_assignment

    def episode(self, ctx: Context, work_id: str, *, continue_from: str | None = None,
                fresh: bool = False) -> dict[str, Any]:
        """Select related continuity explicitly, retaining every assignment and return route."""
        with own(ctx).tables() as tx:
            held = row_for(tx, work_id=work_id)
            if held is None:
                raise Stop(f'No assignment for {work_id}.', HELP)
            episodes.attach(tx, held, now(), continue_from=continue_from, fresh=fresh)
            result = episodes.context(tx, held)
        assert result is not None
        return result

    def episode_context(self, ctx: Context, assignment: Mapping[str, Any]) -> dict[str, Any] | None:
        with own(ctx).tables(write=False) as tx:
            return episodes.context(tx, assignment)

    def session_bound(self, ctx: Context, session_id: str, work_id: str) -> bool:
        """Whether this exact ACP conversation previously worked on the named card."""
        with own(ctx).tables(write=False) as tx:
            assignment = row_for(tx, work_id=work_id)
            return bool(assignment and tx.get('binding_history', {
                'session_id': session_id, 'assignment_id': assignment['assignment_id']}))

    def inherit_runtime(self, ctx: Context, assignment: Mapping[str, Any]) -> None:
        """An explicit coherent continuation can reuse an advertised, unchanged runtime choice."""
        stream = self.episode_context(ctx, assignment)
        previous = (stream or {}).get('previous_assignment')
        if not previous or previous['assignment_id'] == assignment['assignment_id'] or previous.get('stop') \
                or previous['authored_role_uri'] != assignment['authored_role_uri']:
            return
        plan = cast(dict[str, Any], previous.get('plan') or {})
        previous_revision = fingerprint(str(previous['task']))
        for _, transport in provided(ctx.folder, 'orchestration.transport'):
            if not all(hasattr(transport, name) for name in ('runtime_settings', 'keep_runtime')):
                continue
            current = transport.runtime_settings(ctx, str(assignment['work_id']))
            if current.get('decision') or current.get('agent') or current.get('model'):
                return
            choice = transport.runtime_settings(ctx, str(previous['work_id']))
            if not choice.get('agent') or not choice.get('model'):
                return
            decision = dict(choice.get('decision') or {})
            saved = {**choice, **decision, 'decider': 'continuation',
                     'source_decider': decision.get('decider'), 'source_work_id': previous['work_id'],
                     'confidence': decision.get('confidence', 1.0),
                     'reason': 'Retained runtime for the explicitly related execution episode.',
                     'task_fingerprint': fingerprint(str(assignment['task']))}
            try:
                inherited = transport.keep_runtime(ctx, str(assignment['work_id']), saved)
            except (Stop, ValueError):
                return  # Changed advertised options are resolved through the normal selection path.
            if (plan and not assignment.get('plan')
                    and cast(dict[str, Any], inherited.get('decision') or {}).get('decider') == 'continuation'
                    and (plan.get('revision') == previous_revision or plan.get('continued_for') == previous_revision)):
                # Retain a consumed plan only when the runtime decision itself continues.
                # An explicit new planning choice keeps its own dependency and source revision.
                with own(ctx).tables() as tx:
                    current_assignment = row_for(tx, assignment_id=assignment['assignment_id'])
                    if current_assignment and not current_assignment.get('plan'):
                        update(tx, current_assignment, plan={**plan,
                            'source_work_id': plan.get('source_work_id') or previous['work_id'],
                            'continued_from': previous['work_id'],
                            'continued_for': fingerprint(str(assignment['task']))})
            return

    def ensure(self, ctx: Context, work_id: str, role: str | None = None, session_id: str | None = None,
               runner: str | None = None, queue: bool = False, persons: bool = False) -> dict[str, Any]:
        """Bind a dispatch-admitted root start, including the existing Start-button path.

        Dispatch already established the reservation and controls before this
        service call. It reuses that take rather than claiming the work twice.
        """
        store = own(ctx)
        existing = self.assignment(ctx, work_id=work_id)
        if role is None and existing is None:
            role = routing.route(ctx, work_id).get('role')
            if role is None and self.assignment(ctx, work_id=work_id) is None:
                raise Stop(f'Ticket {work_id} is not available for specialist assignment.',
                           f'metaform orchestration route work={work_id}')
        if role is not None and existing is None:
            resolution = resolve(ctx, role)
            if not resolution.get('missing'):
                role = str(resolution['uri'])
        with store.atomic(), store.tables() as tx:
            assignment = row_for(tx, work_id=work_id)
            if assignment and assignment['state'] in ENDED and not assignment.get('stop') and not store.ticket(work_id).work.done:
                assignment = update(tx, assignment, state='queued', attempt=int(assignment.get('attempt') or 1) + 1,
                    result=None, evidence=[], candidate=None, last_check_in={'previous_result': assignment['result'],
                        'previous_evidence': assignment['evidence'], 'previous_candidate': assignment['candidate']})
            if assignment is None:
                assert role is not None
                record = store.ticket(work_id).work
                # Assignment alone leaves work in To do. A bound runner may take it when dispatch has not.
                if (session_id or runner) and not record.taken and not record.done:
                    store.take_work(work_id, by=session_id or runner)
                at = record.address or record.receiver_address
                _, places = location(store, {'kind': record.node_kind, 'id': record.node_id, 'address': at})
                assignment = new_assignment(tx, record, role, ident=identity('gc', work_id),
                    task=record.task or '', result=record.task or '', locations=places,
                    mode=str(ctx.setting('orchestration_mode')), persons=persons)
                if queue:
                    transition(tx, assignment, 'launch', {}, 'initial')
            if persons and not assignment.get('stop'):
                descendants = [assignment]
                for current in descendants:
                    if current.get('stop'):
                        continue
                    updated = update(tx, current, persons_start=True)
                    if current['assignment_id'] == assignment['assignment_id']:
                        assignment = updated
                    descendants.extend(tx.rows('assignments', {
                        'parent_assignment_id': current['assignment_id']}, limit=0).results)
        if session_id:
            return self.bind(ctx, assignment['assignment_id'], session_id, runner, persons=persons)
        self.prepare_runtime(ctx, assignment, restart=persons)
        return self.assignment(ctx, assignment_id=assignment['assignment_id']) or assignment

    def context(self, ctx: Context, work_id: str | None = None,
                session_id: str | None = None) -> dict[str, Any] | None:
        held = self.assignment(ctx, work_id=work_id, session_id=session_id)
        if held is None:
            return None
        with own(ctx).tables(write=False) as tx:
            result = dict(held)
            result['sources'] = list(own(ctx).work_sources(str(held['root_work_id']), contents=False))
            result['mode'] = current_mode(tx, held)
            result.update(related(tx, held))
            returns = tx.rows('transitions', {'assignment_id': held['assignment_id']}, limit=0).results
            result['continuations'] = [one for one in returns if one['state'] == 'pending']
            children = tx.rows('assignments', {'parent_assignment_id': held['assignment_id']}, limit=0).results
            result['returned_children'] = [{key: child[key] for key in (
                'assignment_id', 'work_id', 'authored_role_uri', 'state')}
                for child in children if child['state'] in ENDED and child['result'] is not None]
            return result

    def pending(self, ctx: Context, work_ids: Sequence[str] | None = None) -> list[dict[str, Any]]:
        with own(ctx).tables(write=False) as tx:
            if work_ids is None:
                return list(tx.rows('transitions', {'state': 'pending'}, limit=0).results)
            return [one for work in dict.fromkeys(work_ids)
                    for one in tx.rows('transitions', {'work_id': work, 'state': 'pending'}, limit=0).results]

    def queue_message(self, ctx: Context, recipient_assignment_id: str, envelope: Mapping[str, Any],
                      key: str | None = None) -> dict[str, Any]:
        """Persist an authenticated dispatch envelope for an active or suspended recipient."""
        with own(ctx).tables() as tx:
            recipient = row_for(tx, assignment_id=recipient_assignment_id)
            if recipient is None:
                raise Stop('The message recipient assignment is unavailable.', HELP)
            return transition(tx, recipient, 'send', envelope,
                              key or str(envelope.get('message_id') or uuid.uuid4().hex))

    def delivered(self, ctx: Context, transition_id: str, delivery: Mapping[str, Any]) -> dict[str, Any] | None:
        with own(ctx).tables() as tx:
            held = tx.get('transitions', {'transition_id': transition_id})
            if not held:
                return None
            state = str(delivery.get('state', 'queued'))
            accepted = state in ('running', 'delivered', 'suspended', 'stopped', 'returned', 'completed') or bool(
                delivery.get('accepted'))
            next_state = 'delivered' if accepted else 'failed' if state == 'failed' else 'pending'
            if next_state == 'pending' and held['state'] == 'pending' and held.get('delivery') == dict(delivery):
                return held  # still waiting as it was: no write, so no change for every process of the home to hear
            made = tx.update('transitions', {'transition_id': transition_id}, {
                'state': next_state, 'delivery': dict(delivery), 'updated': now()})
            assignment = row_for(tx, assignment_id=held['assignment_id'])
            if assignment:
                touch(tx, assignment, 'delivery')
                if held['kind'] == 'suspend' and accepted and assignment['state'] not in ENDED:
                    update(tx, assignment, state='suspended')
            if held['kind'] == 'user_message' and accepted:
                change_id = held['payload'].get('change_id')
                if change_id:
                    tx.update('changes', {'change_id': change_id}, {'user_message_state': state, 'updated': now()})
            return made

    def _direction(self, ctx: Context, session_id: str, direction: Mapping[str, Any] | str,
                   state: str | None = None) -> dict[str, Any]:
        with own(ctx).tables() as tx:
            held = row_for(tx, session_id=session_id)
            if held is None:
                raise Stop('The directed session has no recorded assignment.', HELP)
            envelope = {'body': direction} if isinstance(direction, str) else dict(direction)
            directions = list(held['pending_direction'] or [])
            key = envelope.get('message_id') or envelope.get('id') or envelope.get('transition_id')
            if key is None or not any((one.get('message_id') or one.get('id') or one.get('transition_id')) == key
                                      for one in directions):
                directions.append(envelope)
            return update(tx, held, pending_direction=directions, state=state or held['state'])

    def directed(self, ctx: Context, session_id: str, envelope: Mapping[str, Any] | str) -> dict[str, Any]:
        """Retain authenticated newer direction for recovery without changing the recipient's lifecycle."""
        return self._direction(ctx, session_id, envelope)

    def interrupted(self, ctx: Context, session_id: str, direction: Mapping[str, Any] | str) -> dict[str, Any]:
        return self._direction(ctx, session_id, direction, 'interrupted')

    def reopen(self, ctx: Context, work_id: str, queue: bool = False) -> dict[str, Any] | None:
        """Dispatch calls this after admitting an explicit user Start/Resume; descendants stay stopped."""
        store = own(ctx)
        with store.tables() as tx:
            held = row_for(tx, work_id=work_id)
            if held is None or not held.get('stop'):
                return held
            if store.ticket(work_id).work.done:
                raise Stop('The ticket is already complete; corrective work needs its own ticket.', HELP)
            made = update(tx, held, stop=None, state='queued')
            if queue:
                transition(tx, made, 'launch', {'resume': True, 'user_restart': True}, uuid.uuid4().hex)
            return made

    def stopped(self, ctx: Context, session_id: str | None = None, work_id: str | None = None,
                by: str | None = None, direction: str | None = None, every: bool = False) -> list[str]:
        """Stop the assignment and those it is responsible for. `every`: the person's Stop all, a pause of the whole
        machine that their Full Auto turned on again lifts (dispatch `resume_paused`); without it the stop is of this
        work alone and lasts until it is restarted."""
        with own(ctx).tables() as tx:
            root = row_for(tx, session_id=session_id, work_id=work_id)
            if root is None:
                return []
            # Independent assessments remain outside swarm control, but a user's ticket stop also cancels
            # its recorded unfinished assessment continuations so they cannot restart stopped delivery.
            rows = descendants(tx, root, assessments=by == 'user')
            stopping_ids = {row['assignment_id'] for row in rows}
            changed: list[str] = []
            for row in rows:
                if every and row.get('stop'):
                    continue  # Stop all must not make an existing individual stop resumable by Full Auto.
                if row['assignment_id'] != root['assignment_id'] and row['authored_role_uri'] in FACILITATORS:
                    waiters = tx.rows('role_requests', {'creator_assignment_id': row['assignment_id'],
                                                       'state': 'commissioned'}, limit=0).results
                    remaining = [row_for(tx, assignment_id=one['caller_assignment_id']) for one in waiters
                                 if one['caller_assignment_id'] not in stopping_ids]
                    survivor = next((one for one in remaining if one and not one.get('stop')), None)
                    if survivor:
                        update(tx, row, parent_assignment_id=survivor['assignment_id'],
                               return_to={'assignment_id': survivor['assignment_id']})
                        continue
                stop = {'by': by, 'direction': direction, 'at': now(), 'every': every}
                update(tx, row, state=row['state'] if row['state'] in ENDED else 'stopped',
                       stop=stop, stop_history=[*(row.get('stop_history') or []), stop])
                touch(tx, row, 'stop')
                changed.append(row['work_id'])
                for event in tx.rows('transitions', {'assignment_id': row['assignment_id']}, limit=0).results:
                    if event['state'] == 'pending':
                        tx.update('transitions', {'transition_id': event['transition_id']},
                                  {'state': 'cancelled', 'updated': now()})
            return changed

    def claim(self, ctx: Context) -> dict[str, Any]:
        store = own(ctx)
        work_id = str(ctx.nouns['work'])
        # Claim assigns a specialist. The requesting triage/audit session is not the worker
        # that will execute it; dispatch binds that session only after actual admission.
        session = ctx.nouns.get('session')
        if session and (ctx.surface == 'mcp' or agent_caller() is not None) and session != ctx.session:
            raise Stop('An agent can bind only its own session. Omit session to dispatch the assigned specialist.', HELP)
        mode = str(ctx.nouns.get('mode') or ctx.setting('orchestration_mode'))
        if mode not in ('adaptive', 'strict'):
            raise Stop('Mode is adaptive or strict.', HELP)
        create = bool(ctx.nouns.get('create')) and not ctx.nouns.get('role')
        chosen = ctx.nouns.get('role') or ('gc' if create else None)
        if not chosen:
            routed = routing.route(ctx, work_id)
            if routed['state'] == 'creating':
                pending = self.assignment(ctx, work_id=work_id)
                if pending:
                    return pending
            chosen = routed.get('role')
        if not chosen:
            raise Stop(f'Ticket {work_id} is not available for specialist assignment.',
                       f'metaform orchestration route work={work_id}')
        role = agent_role_name(str(chosen))
        # A sessionless delivery owner records responsibility until the creator names real expertise.
        # It is never launched as a generic worker; publication replaces its role before launch.
        resolution = {'missing': True} if create else resolve(ctx, str(chosen))
        if create and session:
            raise Stop('Publish the specialist before binding a worker session.', HELP)
        if resolution.get('problems') and not resolution.get('missing'):
            raise Stop(f'Cannot assign {role}: {resolution["problems"]}', HELP)
        for _, transport in provided(ctx.folder, 'orchestration.transport'):
            guard = getattr(transport, 'guard_claim', None)
            if guard is not None:
                guard(ctx, work_id)
        # the person's own claim, or their system agent's on their word, launches at once whatever Full Auto says
        persons = not ctx.nouns.get('automatic') and (
            ctx.consented or (ctx.surface != 'mcp' and agent_caller() is None) or persons_word(
                ctx.folder, f'Starting an agent on ticket {work_id}', ctx.project, [work_id]) is not None)
        with store.atomic(), store.tables() as tx:
            # Outline approval covers this board's existing tickets. A Facilitator
            # claims those roots rather than creating replacement child tickets.
            caller_session = ctx.session or os.environ.get('METAFORM_SESSION')
            caller = row_for(tx, session_id=caller_session) if caller_session else None
            raw_specification = (caller or {}).get('specification')
            specification = cast(dict[str, Any], raw_specification) if isinstance(raw_specification, dict) else {}
            if not persons and not ctx.nouns.get('automatic') and caller and caller['persons_start'] \
                    and caller['authored_role_uri'] == 'metaform://role/facilitator' \
                    and caller['owner_session_id'] == caller_session \
                    and caller['state'] in ACTIVE and not caller.get('stop') \
                    and specification.get('approved_board'):
                with Store(store.project_id, module='map').tables(write=False) as mapped:
                    placed = mapped.get('ticket_settings', {'work_id': work_id})
                persons = placed is not None and placed.get('board') == specification['approved_board']
            prior = row_for(tx, work_id=work_id)
            if prior:
                if create:
                    requests = tx.rows('role_requests', {'caller_assignment_id': prior['assignment_id']}, limit=0).results
                    for request in requests:
                        if role_options(request).get('assign_in_place'):
                            return {**prior, 'role_request': request}
                if session and prior['owner_session_id'] == session:
                    return prior
                raise Stop(f'Ticket {work_id} is owned by GC {prior["assignment_id"]}.', HELP)
            record = store.ticket(work_id).work
            if record.taken and record.taken_by != session:
                raise Stop(f'Ticket {work_id} is already taken by {record.taken_by}.', HELP)
            # Only a specialist already executing in its own session takes work here.
            if session and not record.taken:
                store.take_work(work_id, by=session)
            at = record.address or record.receiver_address
            _, places = location(store, {'kind': record.node_kind, 'id': record.node_id, 'address': at})
            assignment = new_assignment(tx, record, str(resolution.get('uri') or role), ident=identity('gc', work_id),
                task=record.task or '', result=str(ctx.nouns.get('result') or record.task or ''),
                locations=places, mode=mode, specification=ctx.nouns.get('specification'),
                candidate=ctx.nouns.get('candidate'), session=session,
                return_to={'session_id': str(ctx.nouns['pm_session']), 'kind': 'pm'}
                if ctx.nouns.get('pm_session') else None, persons=bool(persons))
            episodes.attach(tx, assignment, now(), continue_from=ctx.nouns.get('continue_from'),
                            fresh=bool(ctx.nouns.get('fresh_context')))
            if not resolution.get('missing'):
                assignment = update(tx, assignment, role_snapshot=resolution)
                if not session:
                    transition(tx, assignment, 'launch', {}, 'initial')
            else:
                request_ctx = replace(ctx, nouns={**ctx.nouns, 'task': assignment['task'],
                                                 'context': {'assign_in_place': True, 'choose_name': create}})
                request = self.request_role(request_ctx, assignment, '' if create else role)
                return {**(self.assignment(ctx, work_id=work_id) or assignment), 'role_request': request}
        self.episode(ctx, work_id, continue_from=ctx.nouns.get('continue_from'),
                     fresh=bool(ctx.nouns.get('fresh_context')))
        self.inherit_runtime(ctx, assignment)
        self.prepare_runtime(ctx, assignment)
        return self.assignment(ctx, assignment_id=assignment['assignment_id']) or assignment

    def delegate(self, ctx: Context, *, waiting: bool = False, handoff: bool = False) -> dict[str, Any]:
        parent = requested(ctx, ctx.nouns.get('assignment'))
        return self._delegate(ctx, parent, waiting=waiting, handoff=handoff)

    def _delegate(self, ctx: Context, parent: Mapping[str, Any], *, waiting: bool = False,
                  handoff: bool = False, internal: bool = False) -> dict[str, Any]:
        name = agent_role_name(str(ctx.nouns['role']))
        if name == 'functionality':
            raise Stop('The FQC assesses independently of a GC swarm and returns findings to the responsible GC.',
                       'metaform orchestration assess summary="The candidate and functional concern."')
        if name in ('facilitator', 'role_creator'):
            raise Stop('The Facilitator needs the delivery GC\'s recorded specialist-role commission.',
                       'metaform orchestration commission <request>')
        blocked = None if internal else held_role(ctx)
        if blocked:
            raise Stop(f'The configured roles_without_authority excludes {blocked} from creating work.',
                       'metaform config --show')
        if ctx.nouns.get('key'):
            with own(ctx).tables(write=False) as tx:
                prior_request = tx.get('role_requests', {'request_id': identity(
                    parent['assignment_id'], 'role_request', str(ctx.nouns['key']))})
                if prior_request:
                    return row_for(tx, assignment_id=prior_request.get('child_assignment_id')) or prior_request
        resolution = resolve(ctx, str(ctx.nouns['role']))
        if resolution.get('missing'):
            return self.request_role(ctx, parent, name, handoff=handoff)
        if resolution.get('problems'):
            raise Stop(f'Role {name} cannot be resolved: {resolution["problems"]}', f'metaform agents resolve {name}')
        store = own(ctx)
        reviewed = None
        if name == 'harsh_critic':
            if parent['state'] in ENDED:
                raise Stop('Harsh Critic needs an active review caller.',
                           'Request review from the active workflow assignment, not an ended role commission.')
            target = cast(dict[str, Any], ctx.nouns.get('context') or {}).get('reviewed_work')
            if target:
                reviewed = self.assignment(ctx, work_id=str(target))
                if reviewed is None:
                    raise Stop(f'No assignment for reviewed ticket {target}.', HELP)
            elif parent['authored_role_uri'] in FACILITATORS:
                raise Stop('Facilitator reviews need the delivered ticket identity.',
                           'Delegate harsh_critic with context={"reviewed_work":"DELIVERED_TICKET_ID"}.')
            else:
                reviewed = parent
        node, places = location(store, ctx.nouns.get('at'), reviewed or parent)
        task = str(ctx.nouns['task'])
        if ctx.nouns.get('context'):
            task += '\n\nSupplied caller context:\n' + json.dumps(ctx.nouns['context'], ensure_ascii=False)
        result = str(ctx.nouns.get('result') or task)
        key = str(ctx.nouns.get('key') or uuid.uuid4().hex)
        ident = identity(parent['assignment_id'], 'child', key)
        with store.atomic(), store.tables() as tx:
            prior = row_for(tx, assignment_id=ident)
            if prior:
                return prior
            current = row_for(tx, assignment_id=parent['assignment_id']) or parent
            if current.get('stop'):
                raise Stop('The parent was stopped before delegation.', HELP)
            work = store.add_work(node, None, task=task, title=ctx.nouns.get('title') or result.split('\n')[0])
            child = new_assignment(tx, work, str(resolution['uri']), ident=ident, parent=current, task=task,
                review=reviewed,
                result=result, locations=places, mode=current_mode(tx, current),
                specification=(reviewed or current)['specification'],
                candidate=ctx.nouns.get('candidate') or (reviewed or current)['candidate'],
                return_to={'assignment_id': current['assignment_id'], 'continuation_id': ident,
                           **({'runtime_plan': ctx.nouns['_runtime_plan']} if ctx.nouns.get('_runtime_plan') else {})})
            if reviewed is not None:
                child = update(tx, child, reviewed_snapshot=review_snapshot(ctx, reviewed, child.get('candidate')))
            transfers = handoff and current['gc_assignment_id'] != current['assignment_id'] and \
                not current['reviewed_assignment_id']
            if transfers:
                child = self._handoff(tx, current, child)
            elif waiting or handoff or bool(ctx.nouns.get('wait')):
                update(tx, current, state='waiting')
                transition(tx, current, 'suspend', {'reason': 'Waiting for delegated result.',
                                                   'child_assignment_id': ident}, ident)
            transition(tx, child, 'launch', {'parent_assignment_id': current['assignment_id']}, 'initial')
        self.episode(ctx, str(child['work_id']), continue_from=ctx.nouns.get('continue_from'),
                     fresh=bool(ctx.nouns.get('fresh_context')))
        self.inherit_runtime(ctx, child)
        supplied_runtime = ctx.nouns.get('_runtime_choice')
        if supplied_runtime:
            for _, transport in provided(ctx.folder, 'orchestration.transport'):
                if hasattr(transport, 'keep_runtime'):
                    transport.keep_runtime(ctx, child['work_id'], {
                        **supplied_runtime, 'task_fingerprint': fingerprint(child['task'])})
        self.prepare_runtime(ctx, child)
        return self.assignment(ctx, assignment_id=child['assignment_id']) or child

    def request_role(self, ctx: Context, parent: Mapping[str, Any], name: str,
                     handoff: bool = False, *, creator: Mapping[str, Any] | None = None) -> dict[str, Any]:
        name = agent_role_name(name)
        gc_id = parent.get('gc_assignment_id')
        if not gc_id:
            raise Stop('A missing specialty needs its delivery GC to commission the role.', HELP)
        request_key = str(ctx.nouns.get('key') or fingerprint(json.dumps(
            {'call': ctx.nouns, 'handoff': handoff}, sort_keys=True, default=str)))
        request_id = str(creator['return_to']['role_request_id']) if creator else identity(
            parent['assignment_id'], 'role_request', request_key)
        store = own(ctx)
        _, places = location(store, ctx.nouns.get('at'), parent)
        task = str(ctx.nouns['task'])
        supplied_context = {key: value for key, value in cast(dict[str, Any], ctx.nouns.get('context') or {}).items()
                            if key not in ('assign_in_place', 'choose_name')}
        if supplied_context:
            task += '\n\nSupplied caller context:\n' + json.dumps(supplied_context, ensure_ascii=False)
        with store.atomic(), store.tables() as tx:
            previous = tx.get('role_requests', {'request_id': request_id})
            if previous:
                return previous
            if creator is None:
                surviving = [one for one in tx.rows('assignments', {
                    'parent_assignment_id': parent['assignment_id']}, limit=0).results
                    if one['authored_role_uri'] in FACILITATORS
                    and cast(dict[str, Any], one.get('return_to') or {}).get('role_request_id') == request_id]
                creator = max(surviving, key=lambda one: (
                    not one.get('stop') and one['state'] not in ENDED, one['created'], one['assignment_id']),
                    default=None)
            gc = row_for(tx, assignment_id=gc_id)
            if gc is None or gc.get('stop'):
                raise Stop('The delivery GC is unavailable or stopped.', HELP)
            parent = row_for(tx, assignment_id=parent['assignment_id']) or dict(parent)
            if parent.get('stop'):
                raise Stop('The requesting assignment was stopped before its role request.', HELP)
            if store.ticket(str(parent['work_id'])).work.done:
                raise Stop('The requesting ticket was closed before its role request.', HELP)
            responsible_gc = gc['assignment_id']
            made = tx.insert('role_requests', {'request_id': request_id,
                'caller_assignment_id': parent['assignment_id'], 'gc_assignment_id': gc_id, 'role': name,
                'purpose': str(ctx.nouns.get('purpose') or ctx.nouns.get('result') or ctx.nouns['task']),
                'task': task, 'requested_result': str(ctx.nouns.get('result') or ctx.nouns['task']),
                'context': {'contribution': ctx.nouns.get('contribution'), 'context': ctx.nouns.get('context'),
                            'continuity': {key: ctx.nouns[key] for key in ('continue_from', 'fresh_context')
                                           if key in ctx.nouns},
                            'candidate': parent.get('candidate'), 'specification': parent.get('specification'),
                            'responsible_gc_assignment_id': responsible_gc,
                            'handoff': handoff},
                'functional_locations': places, 'creator_assignment_id': None,
                'child_assignment_id': None, 'state': 'requested', 'source': None, 'created': now()})
            update(tx, parent, state='waiting')
            transition(tx, parent, 'suspend', {'reason': 'Waiting for a requested specialist role.'}, request_id)
            if creator:
                tx.update('role_requests', {'request_id': request_id}, {
                    'state': 'commissioned', 'creator_assignment_id': creator['assignment_id']})
                return {**made, 'state': 'commissioned', 'creator_assignment_id': creator['assignment_id']}
            # Concurrent tickets needing the same specialty share one authoring helper. Each
            # request retains its own caller, task and continuation; publication releases all.
            runtime_only = cast(dict[str, Any], ctx.nouns.get('context') or {}).get('runtime_only')
            shared = tx.rows('role_requests', {'role': name, 'state': 'commissioned'}, limit=0).results \
                if name and not runtime_only else ()
            for pending in shared:
                if role_options(pending).get('runtime_only'):
                    continue
                creator = row_for(tx, assignment_id=pending['creator_assignment_id'])
                if creator and creator['state'] not in ENDED and not creator.get('stop'):
                    tx.update('role_requests', {'request_id': request_id}, {
                        'state': 'commissioned', 'creator_assignment_id': creator['assignment_id']})
                    return {**made, 'state': 'commissioned', 'creator_assignment_id': creator['assignment_id']}
            creator = self._commission(tx, store, parent, made)
            return {**made, 'state': 'commissioned', 'creator_assignment_id': creator['assignment_id']}

    @staticmethod
    def _commission(tx: TableTx, store: Store, owner: Mapping[str, Any],
                    request: Mapping[str, Any]) -> dict[str, Any]:
        # The commission is one line, the form every delivery between agents takes (the person's rule, 2026-10-21),
        # naming the ticket by its number and carrying nothing of its content: the Facilitator reads the ticket itself
        # for its text, note and functional context. A copy grew with the ticket (one note of 1.9 MB, copied whole,
        # made the commission the heaviest ticket on the board, 2026-10-20) and was read by every surface that listed
        # the commission, while the ticket is one read away.
        work_id = str(owner['work_id'])
        numbered = store.numbers_of('work', [work_id]).get(work_id)
        item, title = (numbered[0], ' '.join(str(numbered[1] or '').split())) if numbered else (work_id, '')
        task = prompt_files.served(
            resources.files('metaform.modules.orchestration'), 'commission',
            agent=f'{agent_role_name(str(owner["authored_role_uri"]))} {item}',
            task=(title if len(title) <= TITLE else title[:TITLE - 1].rstrip() + '…') or 'no ticket', ticket=item,
            role=f', role {request["role"]}' if request['role'] else '',
            runtime=', runtime only' if role_options(request).get('runtime_only') else '',
            request=str(request['request_id']))
        node, places = location(store, None, owner)
        runtime_only = bool(role_options(request).get('runtime_only'))
        work = store.add_work(node, None, task=task,
                              title='Choose ticket runtime' if runtime_only
                              else f'Create specialist role {request["role"] or "for this ticket"}')
        creator = new_assignment(tx, work, 'facilitator', parent=owner, task=task,
            result=('Choose ticket runtime and continue its assigned expertise.' if runtime_only
                    else 'Publish reusable expertise and return its registered name and URL.'), locations=places,
            mode=current_mode(tx, owner), specification=owner['specification'],
            return_to={'assignment_id': owner['assignment_id'], 'role_request_id': request['request_id']})
        tx.update('role_requests', {'request_id': request['request_id']},
                  {'creator_assignment_id': creator['assignment_id'], 'state': 'commissioned'})
        transition(tx, creator, 'launch', {'role_request_id': request['request_id']}, 'initial')
        return creator

    def commission(self, ctx: Context) -> dict[str, Any]:
        gc = requested(ctx, ctx.nouns.get('assignment'))
        blocked = held_role(ctx)
        if blocked:
            raise Stop(f'The configured roles_without_authority excludes {blocked} from creating work.',
                       'metaform config --show')
        store = own(ctx)
        request_id = str(ctx.nouns['request'])
        resolved_role(ctx, 'facilitator')
        with store.atomic(), store.tables() as tx:
            request = tx.get('role_requests', {'request_id': request_id})
            if request is None:
                raise Stop(f'No role request {request_id}.', HELP)
            if gc['assignment_id'] != request['gc_assignment_id']:
                raise Stop('Only this request\'s delivery GC commissions its role creation.', HELP)
            if request['creator_assignment_id']:
                return row_for(tx, assignment_id=request['creator_assignment_id']) or request
            return self._commission(tx, store, gc, request)

    def publish_role(self, ctx: Context) -> dict[str, Any]:
        creator = requested(ctx, ctx.nouns.get('assignment'))
        store = own(ctx)
        request_id = str(ctx.nouns['request'])
        with store.tables(write=False) as tx:
            request = tx.get('role_requests', {'request_id': request_id})
        if request is None or request['creator_assignment_id'] != creator['assignment_id']:
            raise Stop('This role publication does not match this GC commission.', HELP)
        if request.get('child_assignment_id'):
            self.assignment(ctx, assignment_id=request['child_assignment_id'])
        if isinstance(request.get('source'), dict) and str(request['source'].get('uri')).startswith('metaform://role/'):
            migrate_specialist_references(ctx, request_id=request_id)
            with store.tables(write=False) as tx:
                request = tx.get('role_requests', {'request_id': request_id}) or request
        column = str(ctx.nouns.get('column') or 'todo')
        if column not in ('todo', 'backlog'):
            raise Stop('A specialist handoff places pending work in todo or backlog.', HELP)
        source = {'request_id': request_id, 'gc_assignment_id': request['gc_assignment_id'],
                  'creator_assignment_id': creator['assignment_id'],
                  'creator_session_id': creator['owner_session_id'],
                  'creator_caller_id': ctx.session or os.environ.get('METAFORM_SESSION')}
        role = agent_role_name(str(ctx.nouns.get('role') or request['role']))
        if not role:
            raise Stop('Name the reusable expertise being published.', 'metaform orchestration publish_role role=<name>')
        runtime_only = bool(role_options(request).get('runtime_only'))
        if runtime_only and role != request['role']:
            raise Stop('Runtime selection preserves assigned expertise.', HELP)
        lock = home.home() / 'run' / 'role-publication' / f'{fingerprint(f"{ctx.project}:{role}")}.lock'
        home.mkdir_private(lock.parent)
        with home.file_lock(lock):
            registered = resolve(ctx, str(ctx.nouns.get('role') or request['role']))
            choose_name = role_options(request).get('choose_name')
            if request['state'] == 'published':
                published = request['source']  # Retried delivery cannot revise an already published duty.
                receipt = cast(dict[str, Any], request['context'].get('publication') or {})
            elif not registered.get('missing'):
                if registered.get('problems') or (not registered.get('specialist') and not runtime_only):
                    raise Stop('Select registered specialist expertise, not a system responsibility.',
                               'metaform agents specialists')
                published = registered  # Another creator may have published it while this one worked.
                receipt = {'source': 'existing', 'match_reason': str(ctx.nouns.get('match_reason') or '')}
            else:
                duty = str(ctx.nouns.get('duty') or '').strip()
                purpose = str(ctx.nouns.get('purpose') or ('' if choose_name else request['purpose'])).strip()
                if not duty or not purpose:
                    raise Stop('New expertise needs its reusable purpose and system prompt.', HELP)
                published = service(ctx, 'agent.role').publish(ctx, role, purpose, duty, source=source)
                receipt = {'source': 'created', 'match_reason': str(ctx.nouns.get('match_reason') or '')}
        published_assignments: list[dict[str, Any]] = []
        # Resolve every shared in-place ticket independently before publication can queue any worker.
        with store.tables(write=False) as tx:
            pending = tx.rows('role_requests', {'creator_assignment_id': creator['assignment_id']}, limit=0).results
            targets = [row_for(tx, assignment_id=one['caller_assignment_id']) for one in pending
                       if not one.get('child_assignment_id') and role_options(one).get('assign_in_place')]
        for target in targets:
            if target and not target.get('stop'):
                selected = self.runtime(ctx, str(target['work_id']))
                if selected['state'] == 'needs_choice':
                    raise Stop(f'Choose runtime for ticket {target["work_id"]} before publishing.',
                               f'metaform orchestration runtime work={target["work_id"]}')
        with store.atomic(), store.tables() as tx:
            waiting = tx.rows('role_requests', {'creator_assignment_id': creator['assignment_id']}, limit=0).results
            for request in waiting:
                if request['child_assignment_id']:
                    existing = row_for(tx, assignment_id=request['child_assignment_id'])
                    if existing:
                        published_assignments.append(existing)
                    continue
                caller = row_for(tx, assignment_id=request['caller_assignment_id'])
                if caller is None:
                    raise Stop('The requesting worker assignment is unavailable.', HELP)
                supplied = cast(dict[str, Any], request.get('context') or {})
                in_place = cast(dict[str, Any], supplied.get('context') or {}).get('assign_in_place')
                if in_place:
                    child = update(tx, caller, authored_role_uri=published['uri'], role_snapshot=published,
                                   state='queued')
                else:
                    node, places = location(store, request['functional_locations'][0], caller)
                    work = store.add_work(node, None, task=request['task'], title=request['requested_result'].split('\n')[0])
                    child = new_assignment(tx, work, published['uri'], parent=caller,
                        task=request['task'], result=request['requested_result'], locations=places,
                        mode=current_mode(tx, caller), specification=caller['specification'],
                        candidate=caller['candidate'], return_to={'assignment_id': caller['assignment_id'],
                                                                'role_request_id': request['request_id']})
                    if request['context'].get('handoff') and caller['gc_assignment_id'] != caller['assignment_id'] and \
                            not caller['reviewed_assignment_id']:
                        child = self._handoff(tx, caller, child)
                continuity = cast(dict[str, Any], supplied.get('continuity') or {})
                episodes.attach(tx, child, now(), continue_from=continuity.get('continue_from'),
                                fresh=bool(continuity.get('fresh_context')))
                tx.update('role_requests', {'request_id': request['request_id']},
                          {'state': 'published', 'role': published['name'],
                           'child_assignment_id': child['assignment_id'], 'source': published,
                           'context': {**request['context'], 'publication': receipt}})
                if in_place and tx.get('routing', {'work_id': caller['work_id']}):
                    tx.update('routing', {'work_id': caller['work_id']}, {
                        'state': 'selected', 'role': published['uri'],
                        'reason': 'Reusable specialist published; original ticket continues.', 'updated': now()})
                if caller.get('stop'):
                    update(tx, child, state='stopped', stop=caller['stop'])
                else:
                    current_work = store.ticket(str(child['work_id'])).work
                    if not (in_place and (current_work.held or current_work.done)):
                        store.move_work(child['work_id'], column, kept=True,
                            hold_reason=('Specialist publication explicitly deferred this contribution to Backlog.'
                                         if column == 'backlog' else None))
                        if column != 'backlog':
                            transition(tx, child, 'launch', {'role_request_id': request['request_id']},
                                       request['request_id'])
                published_assignments.append(child)
        for assigned in published_assignments:
            current_work = store.ticket(str(assigned['work_id'])).work
            if not assigned.get('stop') and not current_work.held and not current_work.done:
                self.inherit_runtime(ctx, assigned)
                self.prepare_runtime(ctx, assigned)
        reference = {key: published.get(key) for key in ('name', 'uri', 'version_id')}
        self.returned(ctx, creator['work_id'], {'published_role': reference, 'request_id': request_id},
                      evidence=[reference], key=identity(request_id, 'published'))
        with store.tables(write=False) as tx:
            original = tx.get('role_requests', {'request_id': request_id})
            child = row_for(tx, assignment_id=original['child_assignment_id']) if original else None
        record = store.ticket(str(child['work_id'])).work if child else None
        actual_column = ('done' if record.done else 'doing' if record.taken else 'backlog' if record.held else 'todo') \
            if record else None
        return {'role': published, 'assignment': child, 'assignments': published_assignments, **receipt,
                'board_placement': {'status': 'done' if record else 'failed', 'column': actual_column,
                                    'work_id': child['work_id'] if child else None}}

    @staticmethod
    def wake(tx: TableTx, owner: Mapping[str, Any], key: str) -> None:
        if owner.get('stop') or owner['state'] in ('running', 'queued') or owner['state'] in ENDED:
            return
        update(tx, owner, state='queued')
        transition(tx, owner, 'launch', {'resume': True, 'return_transition': key}, key)

    @staticmethod
    def blocked_assessment_allowed(tx: TableTx, store: Store, gc: Mapping[str, Any],
                                   source: Mapping[str, Any]) -> bool:
        if gc.get('stop') or gc['state'] in ENDED or store.ticket(str(gc['work_id'])).work.done:
            return False
        # Helpers return their blocker to their caller. Assessments already inspect this delivery, including
        # specialists and role commissions they call; their blockers must not start another review of it.
        seen: set[str] = set()
        current: Mapping[str, Any] | None = source
        while current is not None:
            ident = str(current['assignment_id'])
            if ident in seen or current.get('stop') or current.get('reviewed_assignment_id') or \
                    current['authored_role_uri'] in FACILITATORS:
                return False
            seen.add(ident)
            current = row_for(tx, assignment_id=current.get('parent_assignment_id'))
        return not store.ticket(str(source['work_id'])).work.done

    def assessment(self, ctx: Context, gc: Mapping[str, Any], report: Mapping[str, Any],
                   key: str, *, blocked_by: str | None = None, automatic: bool = False) -> dict[str, Any]:
        if automatic and not int(ctx.setting('orchestration_reviews')):
            return {'state': 'completed', 'queued': False, 'reason': 'Automatic assessments are disabled.'}
        resolved_role(ctx, 'functionality')
        store = own(ctx)
        ident = identity(gc['assignment_id'], 'assessment', key)
        with store.atomic(), store.tables() as tx:
            existing = row_for(tx, assignment_id=ident)
            if existing:
                self.assessment_board(ctx, tx, existing)
                return existing
            current_gc = row_for(tx, assignment_id=gc['assignment_id']) or gc
            if automatic and len(tx.rows('assignments', {
                    'reviewed_assignment_id': gc['assignment_id']}, limit=0).results) >= int(
                        ctx.setting('orchestration_reviews')):
                return {'state': 'completed', 'queued': False, 'reason': 'Automatic assessment limit reached.'}
            record = store.ticket(str(current_gc['work_id'])).work
            source = row_for(tx, assignment_id=blocked_by) if blocked_by else None
            is_blocker = blocked_by is not None or 'work_so_far' in report
            if is_blocker and blocked_by is None:
                # Older blocker transitions recorded the report and key only. Their matching suspension and
                # sender retain the source; delivery reviews have an empty report and need no blocker guard.
                candidates = [current_gc]
                for event in tx.rows('transitions', {'assignment_id': gc['assignment_id']}, limit=0).results:
                    payload = event['payload']
                    if event['kind'] == 'send' and payload.get('kind') == 'blocked' and payload.get('report') == report:
                        sender = row_for(tx, assignment_id=payload.get('sender_assignment_id'))
                        if sender:
                            candidates.append(sender)
                source = next((one for one in candidates if tx.get('transitions', {
                    'transition_id': identity(one['assignment_id'], 'suspend', key)})), None)
            if record.outcome == 'cancelled' or (is_blocker and (source is None or not
                    self.blocked_assessment_allowed(tx, store, current_gc, source))):
                return {'state': 'completed', 'queued': False, 'reason': 'Assessment no longer applies.'}
            if current_gc.get('stop'):
                raise Stop('The delivery ticket was stopped before its assessment.', HELP)
            node, places = location(store, None, gc)
            task = (f'Assess ticket {gc["work_id"]} against the retained reviewed_snapshot of this assessment, '
                    f'available through orchestration_inspect assignment={ident}. Read the current delivery report '
                    f'through orchestration_inspect assignment={gc["assignment_id"]} and reconcile subsequent '
                    'changes per finding against the retained reviewed revision.')
            work = store.add_work(node, None, task=task, title=f'Functional assessment of {gc["work_id"]}')
            store.inherit_work_board(work.id, str(current_gc['work_id']))
            made = new_assignment(tx, work, 'functionality', ident=ident, review=current_gc,
                task=task, result='Assess actual functionality, constraints and interactions against C(T).',
                locations=places, mode=current_mode(tx, gc), specification=current_gc['specification'],
                candidate=report.get('candidate') or current_gc['candidate'],
                return_to={'assignment_id': gc['assignment_id'], 'kind': 'assessment'})
            made = update(tx, made, evidence=report.get('evidence') or current_gc['evidence'],
                          reviewed_snapshot=review_snapshot(ctx, current_gc, made.get('candidate')),
                          last_check_in=dict(report))
            transition(tx, made, 'launch', {'reviewed_assignment_id': gc['assignment_id'],
                                           'automatic_assessment': automatic}, 'initial')
            for event in tx.rows('transitions', {'assignment_id': gc['assignment_id']}, limit=0).results:
                if event['kind'] == 'assessment' and event['payload'].get('key') == key:
                    tx.update('transitions', {'transition_id': event['transition_id']}, {
                        'state': 'delivered', 'delivery': {'state': 'completed', 'assessment_id': ident},
                        'updated': now()})
            return made

    def assessment_launch_allowed(self, ctx: Context, assignment: Mapping[str, Any]) -> bool:
        """Recheck current policy for queued automatic reviews, including pre-marker launches."""
        reviewed = assignment.get('reviewed_assignment_id')
        if not reviewed or int(ctx.setting('orchestration_reviews')):
            return True
        with own(ctx).tables(write=False) as tx:
            launches = tx.rows('transitions', {'assignment_id': assignment['assignment_id']}, limit=0).results
            for event in launches:
                if event['kind'] != 'launch':
                    continue
                automatic = event['payload'].get('automatic_assessment')
                if automatic is not None:
                    return not automatic
            # Older assignments retain their automatic origin on the delivery's assessment transition.
            return not any(identity(str(reviewed), 'assessment', str(event['payload'].get('key'))) ==
                           assignment['assignment_id'] for event in tx.rows('transitions', {
                               'assignment_id': reviewed}, limit=0).results if event['kind'] == 'assessment')

    @staticmethod
    def assessment_board(ctx: Context, tx: TableTx, assignment: Mapping[str, Any]) -> None:
        """Recover only generated assessments with an established owner, without releasing person stops."""
        reviewed = assignment.get('reviewed_assignment_id')
        if not reviewed or assignment.get('stop') or assignment['state'] in ENDED:
            return
        owner = row_for(tx, assignment_id=str(reviewed))
        if owner is not None and not owner.get('stop'):
            own(ctx).inherit_work_board(str(assignment['work_id']), str(owner['work_id']))

    def check_in(self, ctx: Context) -> dict[str, Any]:
        assignment = requested(ctx, ctx.nouns.get('assignment'))
        state = str(ctx.nouns['state'])
        if state in ('returned', 'delivered', 'failed'):
            return self.returned(ctx, assignment['work_id'], ctx.nouns.get('summary') or '',
                                 evidence=ctx.nouns.get('evidence'), state=state,
                                 candidate=ctx.nouns.get('candidate'), findings=ctx.nouns.get('findings'),
                                 key=ctx.nouns.get('key'))
        if state not in ('running', 'waiting', 'blocked'):
            raise Stop('Check-in state is running, waiting, blocked, returned, delivered or failed.', HELP)
        key = identity(assignment['assignment_id'], 'check_in', str(ctx.nouns.get('key') or uuid.uuid4().hex))
        report = {name: ctx.nouns.get(name) for name in ('summary', 'candidate', 'evidence', 'work_so_far')}
        store = own(ctx)
        with store.tables() as tx:
            held = update(tx, assignment, state=state, evidence=ctx.nouns.get('evidence') or assignment['evidence'],
                          candidate=ctx.nouns.get('candidate') or assignment['candidate'], last_check_in=report)
            gc = row_for(tx, assignment_id=assignment.get('gc_assignment_id'))
            assess_blocker = state == 'blocked' and bool(int(ctx.setting('orchestration_reviews'))) and \
                gc is not None and \
                self.blocked_assessment_allowed(tx, store, gc, held)
            if state in ('waiting', 'blocked'):
                transition(tx, held, 'suspend', {'reason': report['summary'] or state}, key)
            if gc and gc['assignment_id'] != held['assignment_id']:
                transition(tx, gc, 'send', {'kind': state, 'body': str(report['summary'] or state),
                    'report': report, 'sender_assignment_id': held['assignment_id'],
                    'sender_session_id': held['owner_session_id']}, key)
            if assess_blocker and gc:
                transition(tx, gc, 'assessment', {'report': report, 'key': key,
                           'blocked_by': held['assignment_id']}, key)
        if assess_blocker and gc:
            assessment = self.assessment(ctx, gc, report, key, blocked_by=held['assignment_id'], automatic=True)
            return {'assignment': held, 'assessment': assessment}
        return held

    def returned(self, ctx: Context, work_id: str, result: Any, evidence: Any = None, state: str = 'returned',
                 candidate: Any = None, findings: Any = None, key: str | None = None) -> dict[str, Any]:
        store = own(ctx)
        with store.atomic(), store.tables() as tx:
            held = row_for(tx, work_id=work_id)
            if held is None:
                return {'work_id': work_id, 'unmanaged': True}
            if held['state'] in ENDED:
                return held
            if held.get('stop'):
                return held
            critic = held['authored_role_uri'] == 'metaform://role/harsh_critic'
            verdict_data: Any = result
            verdict = str(cast(Mapping[str, Any], verdict_data).get('verdict')
                          if isinstance(verdict_data, Mapping) else verdict_data).strip()
            rejected = critic and re.match(r'REJECT\b', verdict, re.IGNORECASE) is not None
            if rejected and not findings:
                raise Stop('Harsh Critic rejection needs concrete findings.',
                           'Return REJECT with findings containing defects, evidence, fixes and verification.')
            if rejected and not held.get('reviewed_assignment_id'):
                raise Stop('Harsh Critic rejection needs a recorded review target.',
                           'Delegate harsh_critic from an active caller with context.reviewed_work.')
            record = store.ticket(work_id).work
            if not record.done:
                store.finish_work(work_id, str(result), 'Assigned outcome returned.',
                                  outcome='failed' if state == 'failed' else 'completed')
            returned = update(tx, held, state=state, result=result, evidence=evidence or held['evidence'],
                              candidate=candidate or held['candidate'])
            reviewed_gc = row_for(tx, assignment_id=held.get('reviewed_assignment_id'))
            filed: list[tuple[str | None, dict[str, Any] | None]] = []
            retained: list[dict[str, Any]] = []
            for number, finding in enumerate(findings or []):
                fields: dict[str, Any] = dict(cast(Mapping[str, Any], finding)) if isinstance(finding, Mapping) else {
                    'summary': str(finding)}
                finding_id = str(fields.get('id') or fields.get('finding_id') or number)
                superseded = reviewed_gc is not None and self._decided(tx, store, reviewed_gc, held, fields)
                landed = None
                if reviewed_gc and not superseded:
                    if rejected:
                        landed, assigned = self._critic_finding(ctx, tx, store, reviewed_gc, held, fields,
                                                               returned['evidence'])
                        filed.append((landed, assigned))
                    elif not critic:
                        landed, assigned = self._finding(tx, store, reviewed_gc, held, fields, finding_id,
                                                        returned['evidence'])
                        filed.append((landed, assigned))
                retained.append({'finding_id': finding_id, 'finding': fields,
                    'reviewed_revision': reviewed_revision(held),
                    'disposition': 'superseded' if superseded else 'correction' if landed else 'retained',
                    'work_id': landed, 'evidence': returned['evidence']})
            if retained:
                returned = update(tx, returned, findings=retained, findings_filed=list(dict.fromkeys(
                    landed for landed, _ in filed if landed)))
            numbered = store.numbers_of('work', [work_id]).get(work_id)
            item = numbered[0] if numbered else work_id
            packet = {'kind': 'role_publication' if held['authored_role_uri'] in FACILITATORS else 'result',
                      'state': state, 'body': f'{item} complete',
                      'sender_assignment_id': held['assignment_id'],
                      'sender_session_id': held['owner_session_id'], 'work_id': work_id,
                      'return_to': held['return_to']}
            route: dict[str, Any] = held['return_to'] or {}
            parent = row_for(tx, assignment_id=route.get('assignment_id'), session_id=route.get('session_id'))
            plan_request = route.get('runtime_plan')
            if parent and plan_request:
                # Keep the source task immutable. A planning contribution is consumed by this exact revision.
                parent = update(tx, parent, plan={'revision': plan_request['revision'], 'state': state, 'result': result,
                    'evidence': returned['evidence'], 'assignment_id': held['assignment_id']})
            followed: set[str] = set()
            while parent and parent.get('successor_assignment_id') and parent['assignment_id'] not in followed:
                followed.add(parent['assignment_id'])
                parent = row_for(tx, assignment_id=parent['successor_assignment_id'])
            for predecessor_id in cast(list[str], route.get('transferred_assignments') or []):
                predecessor = row_for(tx, assignment_id=predecessor_id)
                if predecessor is None or predecessor.get('stop'):
                    continue
                if not store.ticket(predecessor['work_id']).work.done:
                    store.finish_work(predecessor['work_id'], str(result),
                                      f'Responsibility completed by successor {held["assignment_id"]}.',
                                      outcome='failed' if state == 'failed' else 'completed')
                update(tx, predecessor, result=result, evidence=returned['evidence'], candidate=returned['candidate'])
            result_key = identity(held['assignment_id'], 'result', str(held.get('attempt') or 1), key or 'completion')
            if parent and not parent.get('stop') and parent['state'] not in ENDED and \
                    not store.ticket(parent['work_id']).work.done:
                transition(tx, parent, 'send', packet, result_key)
                if held['authored_role_uri'] not in FACILITATORS:
                    self.wake(tx, parent, result_key)
            touch(tx, returned, 'return')
            owns_delivery = held['gc_assignment_id'] == held['assignment_id'] and not held['reviewed_assignment_id']
            reviews = tx.rows('assignments', {'reviewed_assignment_id': held['assignment_id']}, limit=0).results
            if owns_delivery and state != 'failed' and len(reviews) < int(ctx.setting('orchestration_reviews')):
                transition(tx, returned, 'assessment', {'report': {}, 'key': result_key}, result_key)
            return returned

    @staticmethod
    def _decided(tx: TableTx, store: Store, gc: Mapping[str, Any], review: Mapping[str, Any],
                 finding: Mapping[str, Any]) -> bool:
        """Only a reasoned per-finding disposition tied to an actual later revision supersedes a finding."""
        if finding.get('disposition') != 'superseded' or not prose(finding.get('supersession_reason')):
            return False
        reference = finding.get('superseded_by')
        snapshot = cast(Mapping[str, Any], review.get('reviewed_snapshot') or {})
        if not reference or str(reference) in snapshot.get('direction_references', []):
            return False
        top = row_for(tx, work_id=gc['root_work_id']) if gc['root_work_id'] != gc['work_id'] else None
        directions = cast(list[dict[str, Any]], [*(gc.get('pending_direction') or []),
                      *((top or {}).get('pending_direction') or []), *(review.get('pending_direction') or [])])
        for direction in directions:
            if (direction.get('kind') == 'user_direction'
                    and str(direction.get('at') or '') >= str(review['created'])
                    and reference in (direction.get('id'), direction.get('revision'))):
                return True
            if direction.get('kind') == 'change_order' and reference == direction.get('change_id'):
                change = tx.get('changes', {'change_id': reference})
                if change and change['state'] in ('operative', 'published') and str(change['created']) >= str(review['created']):
                    return True
        return False

    @staticmethod
    def _critic_finding(ctx: Context, tx: TableTx, store: Store, reviewed: Mapping[str, Any], review: Mapping[str, Any],
                        finding: Any, evidence: Any) -> tuple[str, dict[str, Any]]:
        """Keep Harsh Critic corrections separate from the existing FQC canonical-ticket repair path."""
        fields: dict[str, Any] = dict(cast(Mapping[str, Any], finding)) if isinstance(finding, Mapping) else {
            'summary': str(finding)}
        title, task = finding_text(fields)
        # Preserve fields beyond the standard finding renderer, including requirement, impact and expected behavior.
        task += '\n\nFinding details:\n' + json.dumps(fields, ensure_ascii=False, indent=2)
        task += f'\n\nReviewed work: {reviewed["work_id"]}\nReview: {review["work_id"]}'
        node, _ = location(store, None, reviewed)
        work = store.add_work(node, None, task=task, title=title, kind='flawed',
                              note=f'Review evidence: {prose(evidence)}')
        store.inherit_work_board(work.id, str(reviewed['work_id']))
        # This dependency is generated by the review contract, using the board's existing completion gate.
        verb(replace(ctx, surface='internal'), 'map', 'work', op='edit', id=work.id,
             after_work=[str(reviewed['work_id'])])
        persons = bool(reviewed.get('persons_start')) and not reviewed.get('stop') and not review.get('stop')
        assigned = SERVICE.claim(replace(ctx, consented=bool(persons),
                                 nouns={'work': work.id, 'create': True, 'automatic': not persons}))
        assigned = update(tx, assigned, return_to=review['return_to'])
        return work.id, assigned

    @staticmethod
    def _finding(tx: TableTx, store: Store, gc: Mapping[str, Any], assessment: Mapping[str, Any],
                 finding: Any, key: str, evidence: Any) -> tuple[str | None, dict[str, Any] | None]:
        """A finding becomes corrective work only when no open ticket at its node covers it; a ticket that does
        takes the new evidence in its note, and no second ticket or GC is made. Gives the ticket the finding landed
        on, None when it landed nowhere, with that ticket's assignment."""
        ident = identity(assessment['assignment_id'], 'correction', key)
        existing = row_for(tx, assignment_id=ident)
        if existing:
            return existing['work_id'], existing
        fields: dict[str, Any] = dict(cast(Mapping[str, Any], finding)) if isinstance(finding, Mapping) else {
            'task': str(finding)}
        title, task = finding_text(fields)
        explicit_id = fields.get('finding_id')
        substantive = {name: value for name, value in fields.items() if name not in ('title', 'id')}
        issue = (identity(str(gc['assignment_id']), 'finding', str(explicit_id)) if explicit_id else
                 fingerprint(json.dumps(substantive, sort_keys=True, ensure_ascii=False)) if substantive else
                 identity(assessment['assignment_id'], 'finding', key))
        mark = f'Finding {issue}'
        source = f'review {assessment["work_id"]}'
        observed = prose([evidence, fields.get('evidence')])
        said = f'{mark}, from {source}.' + (f' Evidence: {observed}' if observed else '')
        node, _ = location(store, None, gc)
        for record in store.work(node=node, open=True, limit=0).results:
            # A complete plain-text task can cover a plain-text finding. Rich findings need their stable identity:
            # a renderer can omit additional requirement or evidence fields and cannot prove equivalence.
            plain_finding = len(substantive) == 1 and next(iter(substantive), '') in ('summary', 'task', 'finding')
            same_description = (plain_finding and ' '.join((record.task or '').lower().split()) ==
                                ' '.join(task.lower().split()))
            if mark not in (record.note or '') and not same_description:
                continue
            if source not in (record.note or ''):
                store.edit_work(record.id, {'note': f'{record.note}\n\n{said}' if record.note else said})
            return record.id, row_for(tx, work_id=record.id)
        return Orchestration._correction(tx, store, gc, assessment, fields, key, title=title, task=task, note=said)

    @staticmethod
    def _correction(tx: TableTx, store: Store, gc: Mapping[str, Any], assessment: Mapping[str, Any],
                    finding: Any, key: str, *, title: str | None = None, task: str | None = None,
                    note: str | None = None) -> tuple[str | None, dict[str, Any]]:
        fields: dict[str, Any] = dict(cast(Mapping[str, Any], finding)) if isinstance(finding, Mapping) else {'task': str(finding)}
        if title is None or task is None:
            title, task = finding_text(fields)
        current = row_for(tx, assignment_id=gc['assignment_id']) or dict(gc)
        record = store.ticket(current['work_id']).work
        if current.get('stop') or record.outcome == 'cancelled':
            return None, current
        mark = f'Review {assessment["work_id"]} finding {key}'
        if mark not in (record.note or ''):
            history = f'{mark}: {task}\n{note or ""}'
            store.edit_work(record.id, {'note': '\n\n'.join(filter(None, [record.note, history]))})
        if record.done:
            store.move_work(record.id, 'todo', kept=True)
        direction = {'kind': 'review_finding', 'finding_id': key, 'finding': fields,
                     'reviewed_revision': reviewed_revision(assessment), 'body': task, 'evidence': fields.get('evidence'),
                     'reviewed_assignment_id': assessment['assignment_id'], 'at': now()}
        directions = list(current.get('pending_direction') or [])
        new_attempt = not any(one.get('reviewed_assignment_id') == assessment['assignment_id'] for one in directions)
        if direction not in directions:
            directions.append(direction)
        made = update(tx, current, state='queued', pending_direction=directions,
                      attempt=int(current.get('attempt') or 1) + int(new_attempt),
                      evidence=[] if new_attempt else current['evidence'],
                      last_check_in={'previous_result': current['result'], 'previous_evidence': current['evidence'],
                                     'previous_candidate': current['candidate']} if new_attempt else current['last_check_in'])
        transition(tx, made, 'launch', {'resume': True, 'kind': 'functional_correction', 'finding': fields},
                   identity(assessment['assignment_id'], 'correction'))
        return record.id, made

    def handoff(self, ctx: Context) -> dict[str, Any]:
        return self.delegate(ctx, waiting=True, handoff=True)

    @staticmethod
    def _handoff(tx: TableTx, current: Mapping[str, Any], child: Mapping[str, Any]) -> dict[str, Any]:
        route = dict(current['return_to'] or {})
        route['transferred_assignments'] = [*(route.get('transferred_assignments') or []), current['assignment_id']]
        retained = {'kind': 'handoff_context', 'sender_assignment_id': current['assignment_id'],
                    'sender_session_id': current['owner_session_id'], 'work_id': current['work_id'],
                    'last_check_in': current['last_check_in'], 'evidence': current['evidence'],
                    'candidate': current['candidate'], 'body': 'Retained work from the recorded predecessor.'}
        successor = update(tx, child, return_to=route, pending_direction=[*(child['pending_direction'] or []), retained])
        update(tx, current, state='transferred', successor_assignment_id=child['assignment_id'])
        transition(tx, current, 'suspend', {'reason': 'Responsibility transferred to a successor.',
            'successor_assignment_id': child['assignment_id']}, child['assignment_id'])
        return successor

    def mode(self, ctx: Context) -> dict[str, Any]:
        assignment = self.assignment(ctx, assignment_id=str(ctx.nouns['assignment']))
        if assignment is None:
            raise Stop('No assignment for this mode change.', HELP)
        chosen = str(ctx.nouns['mode'])
        if chosen not in ('adaptive', 'strict'):
            raise Stop('Mode is adaptive or strict.', HELP)
        what = f'Selecting {chosen} specification behavior for ticket {assignment["root_work_id"]}'
        word = on_persons_word(ctx, what, [assignment['root_work_id']])
        with own(ctx).tables() as tx:
            gc = row_for(tx, assignment_id=assignment.get('gc_assignment_id')) or assignment
            for member in descendants(tx, gc, assessments=True):
                update(tx, member, mode=chosen)
            result = row_for(tx, assignment_id=assignment['assignment_id']) or assignment
        if word is not None:
            persons_word_acted(ctx.folder, word, what, project=ctx.project, tickets=[assignment['root_work_id']])
        return result

    def drain(self, ctx: Context, work_ids: Sequence[str] | None = None) -> list[dict[str, Any]]:
        """Run only recorded transitions; called by a change event or recovery, never a timer."""
        transports = provided(ctx.folder, 'orchestration.transport')
        if not transports:
            return []
        transport = transports[0][1]
        events = self.pending(ctx, work_ids)
        # Release waiting owners before admitting children; launches precede their queued result bodies.
        order = {'suspend': 0, 'assessment': 1, 'launch': 2, 'send': 3, 'user_message': 4}
        events.sort(key=lambda event: (order.get(event['kind'], 4), event['created'], event['transition_id']))
        results: list[dict[str, Any]] = []
        seen = {event['transition_id'] for event in events}
        for event in events:
            assignment = self.assignment(ctx, assignment_id=event['assignment_id'])
            if assignment is None or assignment.get('stop'):
                continue
            kind, payload = event['kind'], event['payload']
            try:
                if kind == 'launch':
                    if not self.assessment_launch_allowed(ctx, assignment):
                        delivered = {'state': 'queued', 'reason': 'Automatic assessments are disabled.'}
                        self.delivered(ctx, event['transition_id'], delivered)
                        results.append({'transition_id': event['transition_id'], **delivered})
                        continue
                    if assignment.get('reviewed_assignment_id'):
                        with own(ctx).atomic(), own(ctx).tables() as tx:
                            current = row_for(tx, assignment_id=assignment['assignment_id'])
                            if current is not None:
                                self.assessment_board(ctx, tx, current)
                    delivered = transport.launch(ctx, {**assignment, 'continuation': event}, event['transition_id'])
                    if delivered.get('session_id') and delivered.get('state') == 'running':
                        self.bind(ctx, assignment['assignment_id'], delivered['session_id'], delivered.get('runner'))
                elif kind == 'suspend':
                    delivered = transport.suspend(ctx, assignment, str(payload.get('reason') or 'Waiting for return.'))
                elif kind == 'send':
                    delivered = transport.send(ctx, assignment, {**payload, 'transition_id': event['transition_id'],
                                                                'message_id': event['transition_id']})
                elif kind == 'user_message':
                    delivered = transport.notify_user(ctx, {**payload, 'message_id': event['transition_id']},
                                                      payload.get('change_id') or event['transition_id'])
                elif kind == 'publish':
                    from .specifications import finish_publication
                    delivered = finish_publication(ctx, self, str(payload['change_id']))
                elif kind == 'assessment':
                    assessment = self.assessment(ctx, assignment, payload['report'], str(payload['key']),
                                                 blocked_by=payload.get('blocked_by'), automatic=True)
                    delivered = {'state': 'completed', 'assessment_id': assessment.get('assignment_id')}
                    for addition in self.pending(ctx, [assessment['work_id']]) if assessment.get('assignment_id') else ():
                        if addition['transition_id'] not in seen:
                            events.append(addition)
                            seen.add(addition['transition_id'])
                else:
                    continue
            except (Stop, OSError, ValueError) as error:
                delivered = {'state': 'queued', 'problem': str(error)}
            self.delivered(ctx, event['transition_id'], delivered)
            results.append({'transition_id': event['transition_id'], **delivered})
        return results


SERVICE = Orchestration()


LINKED = ('assignment_id', 'work_id', 'authored_role_uri', 'state', 'result', 'findings_filed')


def work_read(ctx: Context, record: WorkRecord) -> Any:
    """A ticket's assignment, with the assessments that reviewed it, each by its assignment, ticket, state, result and
    the tickets its findings landed on: a ticket whose work ran shows that work, its reviews and where they led."""
    with own(ctx).tables(write=False) as tx:
        held = row_for(tx, work_id=record.id)
        if held is None:
            return tx.get('routing', {'work_id': record.id})
        reviews = tx.rows('assignments', {'reviewed_assignment_id': held['assignment_id']}, limit=0).results
    return {**held, 'independent_assessments': [{key: one.get(key) for key in LINKED} for one in reviews]}


def work_changed(payload: dict[str, Any], ctx: Context) -> None:
    """Only completed work rows need result routing; unrelated bursts cause no store reads."""
    if payload.get('project') != ctx.project:
        return
    if 'work' not in payload.get('tables', ()):
        return
    if payload.get('base_id'):
        ctx = replace(ctx, store=Store(str(ctx.project), module='orchestration', base=str(payload['base_id'])))
    if {'filed', 'ticket', 'note'} & set(payload.get('kinds', ())) and payload.get('work_ids'):
        routing.queue(ctx, [str(one) for one in payload['work_ids']], invalidate='filed' not in payload['kinds'])
    if 'orchestration.return' in payload.get('kinds', ()):
        return
    store = own(ctx)
    if 'work_ids' in payload:
        assignments = [SERVICE.assignment(ctx, work_id=work_id) for work_id in payload['work_ids']]
    else:
        # A public command can combine a concerned work write with an unannotated module write. The
        # aggregate then deliberately omits its concerns. Only this work-table fallback visits the
        # indexed active assignments; completed history and unrelated table events remain untouched.
        with store.tables(write=False) as tx:
            assignments = [one for state in ACTIVE for one in
                           tx.rows('assignments', {'state': state}, limit=0).results]
    for assignment in assignments:
        if assignment is None or assignment['state'] in ENDED:
            continue
        work_id = assignment['work_id']
        record = store.ticket(work_id).work
        if record.done:
            SERVICE.returned(ctx, work_id, record.resolution or '', state='delivered' if
                             assignment['gc_assignment_id'] == assignment['assignment_id'] else 'returned')


def fingerprint(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()
