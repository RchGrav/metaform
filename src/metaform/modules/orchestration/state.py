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
from typing import Any, cast

from metaform import home
from metaform.data import Column, Index, Node, Store, Table, Tables, TableTx, WorkRecord, functional_context
from metaform.module import (
    Context,
    Stop,
    agent_caller,
    call,
    context,
    held_role,
    on_persons_word,
    persons_word,
    persons_word_acted,
    provided,
    surface,
)

from . import routing

HELP = 'metaform help orchestration'
ENDED = frozenset(('returned', 'delivered', 'failed', 'stopped', 'transferred'))
ACTIVE = ('queued', 'running', 'waiting', 'blocked', 'suspended', 'interrupted')
FACILITATORS = ('metaform://role/facilitator', 'metaform://role/role_creator')


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


def signature(title: str) -> str:
    """A finding's normalised signature: its summary's words, lower case, without punctuation or spacing."""
    return fingerprint(' '.join(''.join(one if one.isalnum() else ' ' for one in title.lower()).split()))[:16]


def names(said: Any, subjects: Sequence[str], called: Sequence[str] = ()) -> bool:
    """Whether the person's words name one of these parts: its address, a part within it, a dotted address of a
    whole that holds it, or the short name a part is called by, as whole words. A plain word never stands for a
    whole, so 'code' alone names no code part."""
    text = ' '.join(str(said or '').lower().split())
    if any(re.search(rf'(?<!\w){re.escape(one)}(?!\w)', text) for one in called if one):
        return True
    for named in re.findall(r'\w+(?:\.\w+)*', text):
        if any(named == one or named.startswith(f'{one}.') or ('.' in named and one.startswith(f'{named}.'))
               for one in subjects if one):
            return True
    return False


def own(ctx: Context) -> Store:
    store = ctx.require_store()
    if store.module == 'orchestration':
        return store
    base = store.bound_base()
    return Store(store.project_id, module='orchestration',
                 base=None if base is None else base.id, toggled=store.toggled)


# Version 2 adds an assignment's `role_snapshot` and `attempt`; version 3 its `findings_filed`, the tickets its
# assessment's findings landed on; version 5 its `persons_start`, a delivery the person started. Each column may be
# empty or has a default, so version 1's code still reads and writes the tables, STORE-029.
TABLES = Tables(version=5, compatible_from=1, tables=(
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
        Column('specification', 'json'), Column('mode', required=True), Column('state', required=True),
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
    if held is None:
        raise Stop('No recorded assignment for this call.', 'metaform orchestration claim <work>')
    if session and (caller is None or caller['assignment_id'] != held['assignment_id']):
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
        'owner_session_id': session, 'authored_role_uri': f'metaform://role/{role}', 'execution_role': 'worker',
        'functional_locations': [dict(one) for one in locations], 'task': task, 'requested_result': result,
        'candidate': candidate, 'specification': specification, 'mode': mode,
        'state': 'running' if session else 'queued', 'return_to': return_to,
        'pending_direction': list((parent or review or {}).get('pending_direction') or []),
        'result': None, 'evidence': [], 'last_check_in': None, 'stop': None, 'stop_history': [],
        'persons_start': persons or bool((parent or review or {}).get('persons_start')),
        'created': now(), 'updated': now()})
    touch(tx, made, 'assignment')
    if session:
        tx.insert('sessions', {'session_id': session, 'assignment_id': ident, 'runner': None, 'created': now()})
    return made


def role_options(request: Mapping[str, Any]) -> dict[str, Any]:
    supplied = cast(dict[str, Any], request.get('context') or {})
    return cast(dict[str, Any], supplied.get('context') or {})


def resolve(ctx: Context, role: str) -> dict[str, Any]:
    name = role.removeprefix('metaform://role/')
    return service(ctx, 'agent.role').resolve(ctx, name)


def resolved_role(ctx: Context, role: str) -> str:
    name = role.removeprefix('metaform://role/')
    found = resolve(ctx, name)
    if found.get('problems'):
        raise Stop(f'Role {name} cannot be resolved: {found["problems"]}', f'metaform agents resolve {name}')
    return name


def current_mode(tx: TableTx, assignment: Mapping[str, Any]) -> str:
    root = row_for(tx, assignment_id=assignment.get('gc_assignment_id'))
    return str((root or assignment)['mode'])


class Orchestration:
    """Public provider used by dispatch, MCP context delivery and module UI reads."""

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

    def routing_status(self, ctx: Context, work_id: str) -> dict[str, Any] | None:
        with own(ctx).tables(write=False) as tx:
            assignment = row_for(tx, work_id=work_id)
            if assignment:
                requests = tx.rows('role_requests', {'caller_assignment_id': assignment['assignment_id']}, limit=0).results
                if any(one['state'] == 'commissioned' and role_options(one).get('assign_in_place') for one in requests):
                    return {'state': 'creating', 'role': None}
                return {'state': assignment['state'], 'role': assignment['authored_role_uri']}
            row = tx.get('routing', {'work_id': work_id})
            return {key: row.get(key) for key in ('state', 'role', 'reason')} if row else None

    def ticket_edited(self, ctx: Context, work_id: str, revision: str) -> None:
        """Keep the operative task current and deliver a reference to its changed requirements once."""
        store = own(ctx)
        record = store.ticket(work_id).work
        with store.tables() as tx:
            assignment = row_for(tx, work_id=work_id)
            if assignment and assignment['state'] not in ENDED:
                body = f'Ticket {work_id}: the user edited its requirements. Read the current ticket before continuing.'
                direction = {'kind': 'user_direction', 'body': body, 'at': now(), 'revision': revision}
                assignment = update(tx, assignment, task=record.task or '',
                    requested_result=record.task if assignment['requested_result'] == assignment['task']
                    else assignment['requested_result'],
                    pending_direction=[*(assignment.get('pending_direction') or []), direction])
                transition(tx, assignment, 'send', {'text': body, 'kind': 'user_direction', 'revision': revision},
                           f'ticket-edit:{revision}')

    def assignment(self, ctx: Context, work_id: str | None = None, session_id: str | None = None,
                   assignment_id: str | None = None) -> dict[str, Any] | None:
        with own(ctx).tables(write=False) as tx:
            return row_for(tx, assignment_id=assignment_id, work_id=work_id,
                           session_id=session_id or (ctx.session if not (assignment_id or work_id) else None))

    def members(self, ctx: Context, team_id: str) -> list[dict[str, Any]]:
        with own(ctx).tables(write=False) as tx:
            return list(tx.rows('assignments', {'team_id': team_id}, limit=0).results)

    def assignments(self, ctx: Context) -> list[dict[str, Any]]:
        """Enumerate registered assignments, including work awaiting its first session."""
        with own(ctx).tables(write=False) as tx:
            return list(tx.rows('assignments', limit=0).results)

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
             runner: str | None = None) -> dict[str, Any]:
        with own(ctx).tables(write=False) as tx:
            requests = tx.rows('role_requests', {'caller_assignment_id': assignment_id}, limit=0).results
            if any(one['state'] == 'commissioned' and role_options(one).get('assign_in_place') for one in requests):
                raise Stop('The ticket is waiting for its specialist role to be published.', HELP)
        before = self.assignment(ctx, assignment_id=assignment_id)
        snapshot = (before or {}).get('role_snapshot')
        if before and not snapshot:
            snapshot = resolve(ctx, before['authored_role_uri'])
            if snapshot.get('missing') or snapshot.get('problems'):
                raise Stop(f'Cannot start {before["authored_role_uri"]}: {snapshot.get("problems")}', HELP)
        with own(ctx).tables() as tx:
            held = row_for(tx, assignment_id=assignment_id)
            if held is None:
                raise Stop(f'No assignment {assignment_id}.', HELP)
            if held.get('stop'):
                raise Stop('The assignment was stopped before this launch.', HELP)
            bound = tx.get('sessions', {'session_id': session_id})
            if bound and bound['assignment_id'] != assignment_id:
                raise Stop('The session is already bound to another assignment.', HELP)
            if bound:
                tx.update('sessions', {'session_id': session_id}, {'runner': runner or bound['runner']})
            else:
                tx.insert('sessions', {'session_id': session_id, 'assignment_id': assignment_id,
                                      'runner': runner, 'created': now()})
            bound_assignment = update(tx, held, owner_session_id=session_id, state='running',
                                      role_snapshot=held.get('role_snapshot') or snapshot)
            for event in tx.rows('transitions', {'assignment_id': assignment_id}, limit=0).results:
                if event['kind'] == 'launch' and event['state'] == 'pending':
                    tx.update('transitions', {'transition_id': event['transition_id']}, {
                        'state': 'delivered', 'delivery': {'state': 'running', 'session_id': session_id,
                                                         'runner': runner}, 'updated': now()})
            return bound_assignment

    def ensure(self, ctx: Context, work_id: str, role: str | None = None, session_id: str | None = None,
               runner: str | None = None, queue: bool = False) -> dict[str, Any]:
        """Bind a dispatch-admitted root start, including the existing Start-button path.

        Dispatch already established the reservation and controls before this
        service call. It reuses that take rather than claiming the work twice.
        """
        store = own(ctx)
        if role is None and self.assignment(ctx, work_id=work_id) is None:
            role = routing.route(ctx, work_id).get('role')
            if role is None:
                raise Stop(f'Ticket {work_id} needs specialist selection by triage.',
                           'metaform agents specialists; metaform orchestration claim work=<id> role=<expertise>')
        with store.atomic(), store.tables() as tx:
            assignment = row_for(tx, work_id=work_id)
            if assignment and assignment['state'] in ENDED and not assignment.get('stop') and not store.ticket(work_id).work.done:
                assignment = update(tx, assignment, state='queued', attempt=int(assignment.get('attempt') or 1) + 1,
                    result=None, evidence=[], candidate=None, last_check_in={'previous_result': assignment['result'],
                        'previous_evidence': assignment['evidence'], 'previous_candidate': assignment['candidate']})
            if assignment is None:
                assert role is not None
                role = role.removeprefix('metaform://role/')
                record = store.ticket(work_id).work
                if not record.taken and not record.done:
                    store.take_work(work_id, by=session_id or runner or f'Specialist {work_id}')
                at = record.address or record.receiver_address
                _, places = location(store, {'kind': record.node_kind, 'id': record.node_id, 'address': at})
                assignment = new_assignment(tx, record, role, ident=identity('gc', work_id),
                    task=record.task or '', result=record.task or '', locations=places,
                    mode=str(ctx.setting('orchestration_mode')), return_to={'kind': 'pm'})
                if queue:
                    transition(tx, assignment, 'launch', {}, 'initial')
        if session_id:
            return self.bind(ctx, assignment['assignment_id'], session_id, runner)
        return assignment

    def context(self, ctx: Context, work_id: str | None = None,
                session_id: str | None = None) -> dict[str, Any] | None:
        with own(ctx).tables(write=False) as tx:
            held = row_for(tx, work_id=work_id, session_id=session_id or ctx.session)
            if held is None:
                return None
            result = dict(held)
            result['mode'] = current_mode(tx, held)
            result.update(related(tx, held))
            returns = tx.rows('transitions', {'assignment_id': held['assignment_id']}, limit=0).results
            result['continuations'] = [one for one in returns if one['state'] == 'pending']
            children = tx.rows('assignments', {'parent_assignment_id': held['assignment_id']}, limit=0).results
            result['returned_children'] = [{key: child[key] for key in (
                'assignment_id', 'work_id', 'authored_role_uri', 'state', 'candidate', 'result', 'evidence')}
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
            made = tx.update('transitions', {'transition_id': transition_id}, {
                'state': 'delivered' if accepted else 'failed' if state == 'failed' else 'pending',
                'delivery': dict(delivery), 'updated': now()})
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
            raise Stop(f'Ticket {work_id} needs specialist expertise selected or created by triage.',
                       'metaform agents specialists; metaform orchestration claim work=<id> role=<expertise>')
        role = str(chosen).removeprefix('metaform://role/')
        # A sessionless delivery owner holds the ticket until the creator names real expertise.
        # It is never launched as a generic worker; publication replaces its role before launch.
        resolution = {'missing': True} if create else resolve(ctx, role)
        if create and session:
            raise Stop('Publish the specialist before binding a worker session.', HELP)
        if resolution.get('problems') and not resolution.get('missing'):
            raise Stop(f'Cannot assign {role}: {resolution["problems"]}', HELP)
        for _, transport in provided(ctx.folder, 'orchestration.transport'):
            guard = getattr(transport, 'guard_claim', None)
            if guard is not None:
                guard(ctx, work_id)
        # the person's own claim, or their system agent's on their word, launches at once whatever Full Auto says
        persons = ctx.consented or (ctx.surface != 'mcp' and agent_caller() is None) or persons_word(
            ctx.folder, f'Starting an agent on ticket {work_id}', ctx.project, [work_id]) is not None
        with store.atomic(), store.tables() as tx:
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
            if not record.taken:
                store.take_work(work_id, by=session or f'Specialist {work_id}')
            at = record.address or record.receiver_address
            _, places = location(store, {'kind': record.node_kind, 'id': record.node_id, 'address': at})
            assignment = new_assignment(tx, record, role, ident=identity('gc', work_id),
                task=record.task or '', result=str(ctx.nouns.get('result') or record.task or ''),
                locations=places, mode=mode, specification=ctx.nouns.get('specification'),
                candidate=ctx.nouns.get('candidate'), session=session,
                return_to={'session_id': ctx.nouns.get('pm_session'), 'kind': 'pm'}, persons=bool(persons))
            if not resolution.get('missing'):
                assignment = update(tx, assignment, role_snapshot=resolution)
                if not session:
                    transition(tx, assignment, 'launch', {}, 'initial')
            else:
                request_ctx = replace(ctx, nouns={**ctx.nouns, 'task': assignment['task'],
                                                 'context': {'assign_in_place': True, 'choose_name': create}})
                request = self.request_role(request_ctx, assignment, '' if create else role)
                return {**(self.assignment(ctx, work_id=work_id) or assignment), 'role_request': request}
        return assignment

    def delegate(self, ctx: Context, *, waiting: bool = False, handoff: bool = False) -> dict[str, Any]:
        parent = requested(ctx, ctx.nouns.get('assignment'))
        name = str(ctx.nouns['role']).removeprefix('metaform://role/')
        if name == 'functionality':
            raise Stop('The FQC assesses independently of a GC swarm and returns findings to the responsible GC.',
                       'metaform orchestration assess summary="The candidate and functional concern."')
        if name in ('facilitator', 'role_creator'):
            raise Stop('The Facilitator needs the delivery GC\'s recorded specialist-role commission.',
                       'metaform orchestration commission <request>')
        blocked = held_role(ctx)
        if blocked:
            raise Stop(f'The configured roles_without_authority excludes {blocked} from creating work.',
                       'metaform config --show')
        if ctx.nouns.get('key'):
            with own(ctx).tables(write=False) as tx:
                prior_request = tx.get('role_requests', {'request_id': identity(
                    parent['assignment_id'], 'role_request', str(ctx.nouns['key']))})
                if prior_request:
                    return row_for(tx, assignment_id=prior_request.get('child_assignment_id')) or prior_request
        resolution = resolve(ctx, name)
        if resolution.get('missing'):
            return self.request_role(ctx, parent, name, handoff=handoff)
        if resolution.get('problems'):
            raise Stop(f'Role {name} cannot be resolved: {resolution["problems"]}', f'metaform agents resolve {name}')
        store = own(ctx)
        node, places = location(store, ctx.nouns.get('at'), parent)
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
            child = new_assignment(tx, work, name, ident=ident, parent=current, task=task,
                result=result, locations=places, mode=current_mode(tx, current),
                specification=current['specification'], candidate=ctx.nouns.get('candidate') or current['candidate'],
                return_to={'assignment_id': current['assignment_id'], 'continuation_id': ident})
            transfers = handoff and current['gc_assignment_id'] != current['assignment_id'] and \
                not current['reviewed_assignment_id']
            if transfers:
                child = self._handoff(tx, current, child)
            elif waiting or handoff or bool(ctx.nouns.get('wait')):
                update(tx, current, state='waiting')
                transition(tx, current, 'suspend', {'reason': 'Waiting for delegated result.',
                                                   'child_assignment_id': ident}, ident)
            transition(tx, child, 'launch', {'parent_assignment_id': current['assignment_id']}, 'initial')
        return child

    def request_role(self, ctx: Context, parent: Mapping[str, Any], name: str,
                     handoff: bool = False) -> dict[str, Any]:
        gc_id = parent.get('gc_assignment_id')
        if not gc_id:
            raise Stop('A missing specialty needs its delivery GC to commission the role.', HELP)
        request_key = str(ctx.nouns.get('key') or fingerprint(json.dumps(
            {'call': ctx.nouns, 'handoff': handoff}, sort_keys=True, default=str)))
        request_id = identity(parent['assignment_id'], 'role_request', request_key)
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
            gc = row_for(tx, assignment_id=gc_id)
            if gc is None or gc.get('stop'):
                raise Stop('The delivery GC is unavailable or stopped.', HELP)
            parent = row_for(tx, assignment_id=parent['assignment_id']) or dict(parent)
            if parent.get('stop'):
                raise Stop('The requesting assignment was stopped before its role request.', HELP)
            responsible_gc = gc['assignment_id']
            made = tx.insert('role_requests', {'request_id': request_id,
                'caller_assignment_id': parent['assignment_id'], 'gc_assignment_id': gc_id, 'role': name,
                'purpose': str(ctx.nouns.get('purpose') or ctx.nouns.get('result') or ctx.nouns['task']),
                'task': task, 'requested_result': str(ctx.nouns.get('result') or ctx.nouns['task']),
                'context': {'contribution': ctx.nouns.get('contribution'), 'context': ctx.nouns.get('context'),
                            'candidate': parent.get('candidate'), 'specification': parent.get('specification'),
                            'responsible_gc_assignment_id': responsible_gc,
                            'handoff': handoff},
                'functional_locations': places, 'creator_assignment_id': None,
                'child_assignment_id': None, 'state': 'requested', 'source': None, 'created': now()})
            update(tx, parent, state='waiting')
            transition(tx, parent, 'suspend', {'reason': 'Waiting for a requested specialist role.'}, request_id)
            # Concurrent tickets needing the same specialty share one authoring helper. Each
            # request retains its own caller, task and continuation; publication releases all.
            shared = tx.rows('role_requests', {'role': name, 'state': 'commissioned'}, limit=0).results if name else ()
            for pending in shared:
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
        # Ticket text is included once; ids carry the continuation, not copies of every field.
        record = store.ticket(str(owner['work_id'])).work
        graph = functional_context(store, record)
        task = json.dumps({'request': {'request_id': request['request_id'], 'role': request['role'] or None,
                                      'task': request['task'], 'functional_locations': request['functional_locations']},
                           'note': record.note,
                           'function': {key: value for key, value in graph.items() if key != 'markdown'}},
                          ensure_ascii=False)
        node, places = location(store, None, owner)
        work = store.add_work(node, None, task=task, title=f'Create specialist role {request["role"] or "for this ticket"}')
        creator = new_assignment(tx, work, 'facilitator', parent=owner, task=task,
            result='Publish reusable expertise and return its registered name and URL.', locations=places,
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
        column = str(ctx.nouns.get('column') or 'todo')
        if column not in ('todo', 'backlog'):
            raise Stop('A specialist handoff places pending work in todo or backlog.', HELP)
        source = {'request_id': request_id, 'gc_assignment_id': request['gc_assignment_id'],
                  'creator_assignment_id': creator['assignment_id'],
                  'creator_session_id': creator['owner_session_id'],
                  'creator_caller_id': ctx.session or os.environ.get('METAFORM_SESSION')}
        role = str(ctx.nouns.get('role') or request['role']).removeprefix('metaform://role/')
        if not role:
            raise Stop('Name the reusable expertise being published.', 'metaform orchestration publish_role role=<name>')
        lock = home.home() / 'run' / 'role-publication' / f'{fingerprint(f"{ctx.project}:{role}")}.lock'
        home.mkdir_private(lock.parent)
        with home.file_lock(lock):
            registered = resolve(ctx, role)
            choose_name = role_options(request).get('choose_name')
            if request['state'] == 'published':
                published = request['source']  # Retried delivery cannot revise an already published duty.
                receipt = cast(dict[str, Any], request['context'].get('publication') or {})
            elif not registered.get('missing'):
                if registered.get('problems') or not registered.get('specialist'):
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
                    child = new_assignment(tx, work, published['name'], parent=caller,
                        task=request['task'], result=request['requested_result'], locations=places,
                        mode=current_mode(tx, caller), specification=caller['specification'],
                        candidate=caller['candidate'], return_to={'assignment_id': caller['assignment_id'],
                                                                'role_request_id': request['request_id']})
                    if request['context'].get('handoff') and caller['gc_assignment_id'] != caller['assignment_id'] and \
                            not caller['reviewed_assignment_id']:
                        child = self._handoff(tx, caller, child)
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
                    store.move_work(child['work_id'], column, kept=True)
                    if column != 'backlog':
                        transition(tx, child, 'launch', {'role_request_id': request['request_id']}, 'initial')
                published_assignments.append(child)
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

    def assessment(self, ctx: Context, gc: Mapping[str, Any], report: Mapping[str, Any],
                   key: str) -> dict[str, Any]:
        resolved_role(ctx, 'functionality')
        store = own(ctx)
        ident = identity(gc['assignment_id'], 'assessment', key)
        with store.atomic(), store.tables() as tx:
            existing = row_for(tx, assignment_id=ident)
            if existing:
                return existing
            current_gc = row_for(tx, assignment_id=gc['assignment_id']) or gc
            if current_gc.get('stop'):
                raise Stop('The delivery ticket was stopped before its assessment.', HELP)
            node, places = location(store, None, gc)
            task = json.dumps({'reviewed_work': gc['work_id'], 'report': dict(report),
                               'candidate': report.get('candidate') or gc['candidate'],
                               'evidence': report.get('evidence') or gc['evidence']}, ensure_ascii=False)
            work = store.add_work(node, None, task=task, title=f'Functional assessment of {gc["work_id"]}')
            made = new_assignment(tx, work, 'functionality', ident=ident, review=gc,
                task=task, result='Assess actual functionality, constraints and interactions against C(T).',
                locations=places, mode=current_mode(tx, gc), specification=gc['specification'],
                candidate=report.get('candidate') or gc['candidate'],
                return_to={'assignment_id': gc['assignment_id'], 'kind': 'assessment'})
            transition(tx, made, 'launch', {'reviewed_assignment_id': gc['assignment_id']}, 'initial')
            for event in tx.rows('transitions', {'assignment_id': gc['assignment_id']}, limit=0).results:
                if event['kind'] == 'assessment' and event['payload'].get('key') == key:
                    tx.update('transitions', {'transition_id': event['transition_id']}, {
                        'state': 'delivered', 'delivery': {'state': 'completed', 'assessment_id': ident},
                        'updated': now()})
            return made

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
            if state in ('waiting', 'blocked'):
                transition(tx, held, 'suspend', {'reason': report['summary'] or state}, key)
            if gc and gc['assignment_id'] != held['assignment_id']:
                transition(tx, gc, 'send', {'kind': state, 'body': str(report['summary'] or state),
                    'report': report, 'sender_assignment_id': held['assignment_id'],
                    'sender_session_id': held['owner_session_id']}, key)
            if state == 'blocked' and gc:
                transition(tx, gc, 'assessment', {'report': report, 'key': key}, key)
        if state == 'blocked' and gc:
            assessment = self.assessment(ctx, gc, report, key)
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
            record = store.ticket(work_id).work
            if not record.done:
                store.finish_work(work_id, str(result), 'Assigned outcome returned.',
                                  outcome='failed' if state == 'failed' else 'completed')
            returned = update(tx, held, state=state, result=result, evidence=evidence or held['evidence'],
                              candidate=candidate or held['candidate'])
            reviewed_gc = row_for(tx, assignment_id=held.get('reviewed_assignment_id'))
            superseded = reviewed_gc is not None and self._decided(tx, store, reviewed_gc, held)
            filed = [self._finding(tx, store, reviewed_gc, held, finding, str(number), returned['evidence'])
                     for number, finding in enumerate(findings or [])] if reviewed_gc and not superseded else []
            if filed:
                returned = update(tx, returned, findings_filed=list(dict.fromkeys(
                    landed for landed, _ in filed if landed)))
            corrections = list({one['assignment_id']: one for _, one in filed if one}.values())
            body = str(result) if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
            packet = {'kind': 'role_publication' if held['authored_role_uri'] in FACILITATORS else 'result', 'state': state, 'result': result, 'body': body,
                      'evidence': returned['evidence'],
                      'verification': 'evidence supplied' if returned['evidence'] else 'not established',
                      'candidate': returned['candidate'], 'findings': findings, 'superseded': superseded,
                      'corrective_assignments': [{name: correction[name] for name in
                          ('assignment_id', 'work_id', 'team_id', 'state', 'parent_assignment_id')}
                          for correction in corrections],
                      'sender_assignment_id': held['assignment_id'],
                      'sender_session_id': held['owner_session_id'], 'work_id': work_id,
                      'return_to': held['return_to']}
            # The author's summary is the notification. Candidate and evidence remain in the durable assignment
            # and packet, available through inspect, rather than appended again to every message.
            user_packet = packet
            route: dict[str, Any] = held['return_to'] or {}
            parent = row_for(tx, assignment_id=route.get('assignment_id'))
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
            if parent:
                transition(tx, parent, 'send', packet, result_key)
                if held['authored_role_uri'] not in FACILITATORS:
                    self.wake(tx, parent, result_key)
            elif route.get('kind') == 'pm':
                transition(tx, returned, 'user_message', user_packet, result_key)
            touch(tx, returned, 'return')
            if reviewed_gc:
                transition(tx, returned, 'user_message', {**user_packet, 'kind': 'functional_assessment',
                    'reviewed_assignment_id': reviewed_gc['assignment_id']}, result_key)
            owns_delivery = held['gc_assignment_id'] == held['assignment_id'] and not held['reviewed_assignment_id']
            if owns_delivery and held['parent_assignment_id']:
                transition(tx, returned, 'user_message', {**user_packet, 'kind': 'functional_correction',
                    'responsible_gc_assignment_id': held['parent_assignment_id']}, result_key)
            reviews = tx.rows('assignments', {'reviewed_assignment_id': held['assignment_id']}, limit=0).results
            if owns_delivery and state != 'failed' and len(reviews) < int(ctx.setting('orchestration_reviews')):
                transition(tx, returned, 'assessment', {'report': packet, 'key': result_key}, result_key)
            return returned

    @staticmethod
    def _decided(tx: TableTx, store: Store, gc: Mapping[str, Any], review: Mapping[str, Any]) -> bool:
        """The person's decision superseded what a review examined: since the review began, a direction of theirs
        that names the reviewed part, by address or short name, reached the reviewed GC, its root or the review, or
        a specification change of theirs whose instruction names that part was routed to that work. Their word about
        another part is no decision about this one, and the findings are filed. Only the change orders the work
        received are read."""
        since = str(review['created'])
        locations = cast(list[Mapping[str, Any]], gc.get('functional_locations') or [])
        subjects = [str(one.get('address') or one.get('id') or '').lower() for one in locations]
        elements = [store.element(str(one.get('address') or one.get('id') or ''))
                    for one in locations if one.get('kind') != 'join']
        called = [one.short_name.lower() for one in elements if one is not None]
        top = row_for(tx, work_id=gc['root_work_id']) if gc['root_work_id'] != gc['work_id'] else None
        for one in cast(list[Mapping[str, Any]], [*(gc.get('pending_direction') or []),
                                                  *((top or {}).get('pending_direction') or []),
                                                  *(review.get('pending_direction') or [])]):
            if one.get('kind') == 'user_direction':
                if str(one.get('at') or '') >= since and names(one.get('text') or one.get('body'), subjects, called):
                    return True
            elif one.get('kind') == 'change_order' and one.get('source') == 'user':
                record = tx.get('changes', {'change_id': one.get('change_id')})
                instruction = cast(Mapping[str, Any], (record or {}).get('user_instruction') or {})
                if record and str(record['created']) >= since and names(instruction.get('text'), subjects, called):
                    return True
        return False

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
        mark = f'Finding {signature(title)}'
        source = f'review {assessment["work_id"]}'
        observed = prose([evidence, fields.get('evidence')])
        said = f'{mark}, from {source}.' + (f' Evidence: {observed}' if observed else '')
        node, _ = location(store, None, gc)
        for record in store.work(node=node, open=True, limit=0).results:
            first = (record.task or '').strip().split('\n')[0]
            if mark not in (record.note or '') and signature(first) != signature(title):
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
        direction = {'kind': 'review_finding', 'body': task, 'evidence': fields.get('evidence'),
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
                    assessment = self.assessment(ctx, assignment, payload['report'], str(payload['key']))
                    delivered = {'state': 'completed', 'assessment_id': assessment['assignment_id']}
                    for addition in self.pending(ctx, [assessment['work_id']]):
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
