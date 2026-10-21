"""Dispatch's transport for recorded orchestration transitions.

Every managed adapter, including a resumed caller, enters the existing admission gate. Waiting parents end their
adapter before the runner releases its lease; the next transition is drained after that release. A durable message
is accepted by a recipient's normal-turn queue, and its thread records the later ACP handoff separately.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from metaform import events, home, prompt_files
from metaform.module import Context, Stop, provided

SUSPENDED = 'orchestration suspended'
UPDATES = 'conversation-orchestration-updates'


def service(ctx: Context) -> Any:
    found = provided(ctx.folder, 'orchestration')
    return found[0][1] if found else None


def assignment(ctx: Context, work_id: str | None = None, session_id: str | None = None) -> dict[str, Any] | None:
    owner = service(ctx)
    return owner.assignment(ctx, work_id=work_id, session_id=session_id) if owner is not None else None


def drain(ctx: Context, work_ids: list[str] | None = None) -> list[dict[str, Any]]:
    with home.registry_scope(fresh=True):
        owner = service(ctx)
        return events.announced(ctx.folder, ctx.surface, owner.drain, ctx, work_ids)[0] if owner is not None else []


def render(ctx: Context, name: str, bindings: dict[str, str]) -> dict[str, str] | None:
    """Owner-supplied fill values also used when an authored role resolves dispatch's selected PM prompt."""
    if name != 'prompt.dispatch:system':
        return None
    from . import mascot_line
    return {'project': str(ctx.project or ''), 'mascot': mascot_line(ctx.folder), **bindings}


def _lock(ctx: Context, ident: str) -> Path:
    digest = hashlib.sha256(f'{ctx.project}:{ident}'.encode()).hexdigest()
    folder = home.home() / 'run' / 'dispatch' / 'orchestration'
    home.mkdir_private(folder)
    return folder / f'{digest}.lock'


def _row(ctx: Context, held: dict[str, Any], *, verify: bool = True) -> dict[str, Any] | None:
    from . import sessions
    rows = sessions(ctx.require_store(), str(held['work_id']), verify=verify)
    return next((row for row in reversed(rows) if row['session_id'] == held.get('owner_session_id')), None)


def identity(ctx: Context) -> tuple[dict[str, Any], dict[str, Any]]:
    """An agent's actual registered sender identity; role prose and tool arguments cannot supply it."""
    from .peering import caller, side
    record, row = caller(ctx.require_store())
    return row, side(ctx, record, row)


def owned_gc(ctx: Context, team: str | None = None) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    owner = service(ctx)
    row, sender = identity(ctx)
    held = owner.assignment(ctx, session_id=str(row['session_id'])) if owner is not None else None
    if not held or held['gc_assignment_id'] != held['assignment_id'] or (team and held['team_id'] != team):
        raise Stop('Only the recorded delivery owner can direct its own workers.', 'metaform orchestration team')
    return owner, held, sender


class Transport:
    """The orchestration module uses this provider instead of importing dispatch internals."""

    def runtime_catalog(self, ctx: Context, work_id: str) -> dict[str, Any]:
        """Installed, eligible adapters and their advertised model descriptions and thinking levels; a model's short
        name, such as sol, is a choice too and means its family's newest release when the session starts.

        Reading a catalog starts no process and sends no prompt. Missing options remain empty so the assignment
        owner can request an options-only prime before choosing.
        """
        from . import agent_choices, catalog_rows, found_command, option_key, short_names
        eligible = cast(list[str], self.runtime_settings(ctx, work_id).get('eligible') or [])
        rows = catalog_rows(ctx.require_store())
        result: dict[str, Any] = {}
        for agent in agent_choices():
            if eligible and agent not in eligible or found_command(ctx, agent) is None:
                continue
            models: dict[str, str] = {}
            efforts: list[str] = []
            for option in cast(list[dict[str, Any]], (rows.get(agent) or {}).get('settings') or []):
                key = option_key(option)
                for choice in cast(list[dict[str, Any]], option.get('options') or []):
                    value = choice.get('value')
                    if not isinstance(value, str) or not value.strip():
                        continue
                    if key == 'model':
                        models[value] = ': '.join(str(part) for part in
                                                 (choice.get('name'), choice.get('description')) if part) or value
                    elif key == 'thought_level':
                        efforts.append(value)
                if key == 'model':  # a short name first, such as sol, which means its family's newest release now
                    models = {**{short: f'newest {short}, now {value}: {models.get(value, value)}'
                                 for short, value in short_names(option).items() if short != value}, **models}
            result[agent] = {'models': models, 'efforts': efforts}
        return result

    def runtime_settings(self, ctx: Context, work_id: str) -> dict[str, Any]:
        """The saved ticket choice, carrying pre-existing manual tune values until it is saved in the map."""
        from . import runtime_settings
        return runtime_settings(ctx, work_id)

    def keep_runtime(self, ctx: Context, work_id: str, choice: dict[str, Any]) -> dict[str, Any]:
        """Keep an assignment's validated choice while preserving the person's existing ticket overrides."""
        from . import keep_runtime
        catalog = self.runtime_catalog(ctx, work_id)
        with ctx.require_store().atomic():
            return keep_runtime(ctx, work_id, choice, catalog)

    def edit_runtime(self, ctx: Context, work_id: str, given: dict[str, Any]) -> dict[str, Any]:
        """Card edits share dispatch tune's validation and authority."""
        from . import edit_runtime
        return edit_runtime(ctx, work_id, given)

    def guard_claim(self, ctx: Context, work_id: str) -> None:
        from . import person_asks, starts_held
        caution = starts_held(replace(ctx, nouns={'id': work_id}))
        if caution and not (ctx.consented or person_asks(ctx)):
            raise Stop(caution, f'metaform dispatch start {work_id}')

    def launch(self, ctx: Context, held: dict[str, Any], transition_id: str) -> dict[str, Any]:
        from . import (
            admit,
            agent_named,
            given_back_reservation,
            glyph_of,
            keep_launch,
            launches,
            persons_start,
            resume_spawn,
            session_state,
            sessions,
            start_runner,
            startable,
            ticket,
        )
        store = ctx.require_store()
        work = str(held['work_id'])
        # a delivery the person started, or their system agent on their word, is no automatic start: Full Auto off
        # does not hold its launches; a halt still refuses them as it does every start
        auto = not persons_start(ctx, recorded=bool(held.get('persons_start')))
        if held.get('stop'):
            return {'state': 'stopped'}
        if store.ticket(work).work.done:
            return {'state': 'completed', 'work_id': work}
        # A delivery whose specialist role is still being made waits for its publication, which owns the start: a
        # runner started here only read that state and ended at once, SUSPENDED, and the launch left pending started
        # another on every pass of the agent starter (783 runner starts on one ticket, 2026-10-20).
        owner = service(ctx)
        status = owner.routing_status(ctx, work) if owner is not None else None
        if status and status.get('state') == 'creating':
            return {'state': 'queued', 'problem': str(status.get('reason') or 'its specialist role is being made')}
        if owner is not None and hasattr(owner, 'prepare_runtime') and not owner.prepare_runtime(ctx, held):
            return {'state': 'queued', 'problem': 'The Facilitator is choosing the ticket runtime.'}
        # A launch counts the runners it started in its delivery, `attempts`. Past dispatch_retries starts with no
        # session made, the delivery is handed to the person with a signal and started no more: the system stops its
        # own loop and says why, rather than start a runner on every pass (2026-10-20).
        previous = cast(dict[str, Any], cast(dict[str, Any], held.get('continuation') or {}).get('delivery') or {})
        attempts = int(previous.get('attempts') or 0)
        if attempts > int(ctx.setting('dispatch_retries')) and not previous.get('session_id'):
            from .signals import publish
            reason = (f'{attempts} runners were started on this delivery and none made a session'
                      + (f' (the last said: {previous["problem"]})' if previous.get('problem') else ''))
            publish(ctx, 'handed-over', work_id=work, key=f'launch:{transition_id}',
                    reason=f'{reason}. It waits for you.', next=f'metaform dispatch start {work}')
            return {'state': 'failed', 'problem': reason, 'attempts': attempts}
        created = held.get('continuation', {}).get('created')
        if isinstance(created, str):
            asked = int(datetime.fromisoformat(created).timestamp() * 1_000_000_000)
        elif isinstance(created, (int, float)):
            asked = int(float(created) * 1_000_000_000)
        else:
            asked = time.time_ns()
        with home.file_lock(_lock(ctx, str(held['assignment_id']))):
            running = next((one for one in launches() if one.get('project') == ctx.project and
                            one.get('work_id') == work), None)
            row = _row(ctx, held)
            if running is not None:
                if row and row['state'] == 'running':
                    return {'state': 'running', 'session_id': row['session_id'], 'runner': row.get('runner')}
                return {'state': 'queued', 'reservation': running.get('lease'), 'pid': running['pid'],
                        'attempts': attempts}
            runtime = self.runtime_settings(ctx, work)
            agent = agent_named(str(runtime.get('agent') or (row or {}).get('agent') or ctx.setting('dispatch_agent')))
            if row is not None and row.get('agent') != agent:
                row = None  # a changed ticket agent starts its own adapter instead of resuming another agent's session
            launch_ctx = replace(ctx, nouns={'id': work, 'agent': agent})
            words = [f'assignment={held["assignment_id"]}']
            checked_sessions = sessions(store, work if glyph_of(launch_ctx, ticket(store, work)) is None else None)
            if row is not None:
                kept = session_state(store, str(row['session_id'])) or {}
                capabilities = cast(dict[str, Any], kept.get('capabilities') or {})
                if capabilities.get('resume') or capabilities.get('load'):
                    # A worker resumed in place goes on only with the ticket its session's own. A review finding
                    # reopens a done ticket into To do, untaken, so the session takes it back before its runner
                    # starts; a ticket another holder took since goes on through a new session below.
                    by = f'{agent} {row["session_id"]}'
                    with store.atomic():
                        record = ticket(store, work)
                        if record.done:
                            return {'state': 'completed', 'work_id': work}
                        took = not record.taken
                        if took:
                            startable(launch_ctx, store, record, agent, checked_sessions=checked_sessions)
                            store.take_work(work, by=by)
                    if took or record.taken_by == by:
                        try:
                            made = resume_spawn(store, work, agent,
                                                [*words, f'resume={row["session_id"]}', 'retry=true'],
                                                'orchestration', ctx=launch_ctx, asked=asked, auto=auto)
                        except (Stop, OSError):
                            if took:
                                given_back_reservation(store, work, by)
                            raise
                        return {'state': 'queued', 'reservation': transition_id, 'attempts': attempts + 1, **made}
            # Unknown context retention creates a new registered context with the retained work and current brief.
            # The same gate checks before the take, and again under its machine-wide lock during the process spawn.
            admit(launch_ctx, store, work, 'worker', asked=asked, agent=agent, auto=auto)
            reservation = f'dispatch starting {transition_id}'
            with store.atomic():
                record = ticket(store, work)
                if record.done:
                    return {'state': 'completed', 'work_id': work}
                previous = record.taken_by
                if record.taken:
                    store.move_work(work, 'todo', kept=True)
                    record = ticket(store, work)
                startable(launch_ctx, store, record, agent, checked_sessions=checked_sessions)
                store.take_work(work, by=reservation)
            keep_launch(store, work, {'prompts': None, 'mode': None})
            try:
                made = start_runner(launch_ctx, store, work, agent, [*words, f'reservation={reservation}'],
                                    'orchestration', reservation=reservation, asked=asked, auto=auto)
            except (Stop, OSError):
                # Capacity can change between the optimistic check and the locked gate. Ownership survives it.
                with store.atomic():
                    current = ticket(store, work)
                    if previous and not current.taken and not current.done:
                        store.take_work(work, by=previous)
                raise
            return {'state': 'queued', 'reservation': transition_id, 'attempts': attempts + 1, **made}

    def suspend(self, ctx: Context, held: dict[str, Any], reason: str) -> dict[str, Any]:
        from . import tell
        row = _row(ctx, held)
        if row is None or row['state'] != 'running':
            return {'state': 'suspended'}
        told = tell(row, 'suspend', assignment=held['assignment_id'], reason=reason)
        # Accepted means shutdown is queued. The gate keeps counting the process until its adapter has ended.
        return {'state': 'queued', 'accepted': bool(told.get('accepted')), **told}

    def send(self, ctx: Context, held: dict[str, Any], envelope: dict[str, Any]) -> dict[str, Any]:
        from . import held_ticket, sessions, tell
        from .peering import side
        row = _row(ctx, held)
        if row is None or row['state'] != 'running':
            return {'state': 'queued', 'reason': 'The recipient will read this after its recorded continuation.'}
        sender = dict(envelope.get('from') or {})
        if not sender and envelope.get('sender_assignment_id'):
            owner = service(ctx)
            source = owner.assignment(ctx, assignment_id=envelope['sender_assignment_id']) if owner else None
            if source:
                rows = sessions(ctx.require_store(), source['work_id'], verify=False)
                actual = next((one for one in reversed(rows)
                               if one['session_id'] == envelope.get('sender_session_id')), None)
                if actual:
                    sender = side(ctx, held_ticket(ctx.require_store(), source['work_id']), actual)
        sender.setdefault('agent', 'orchestration')
        sender.setdefault('session_id', '')
        body = envelope.get('text') or envelope.get('body') or envelope.get('summary')
        if body is None:
            raise ValueError('An agent message requires a message body.')
        # Keep message identity and routing, never assignment snapshots, context or reports.
        line = {**{key: envelope[key] for key in MESSAGE_FIELDS if key in envelope},
                'id': envelope.get('id') or envelope.get('message_id'), 'from': sender,
                'text': str(body), 'at': envelope.get('at') or home.now(),
                'kind': envelope.get('kind') or 'continuation',
                'to': [{'work_id': row['work_id'], 'session_id': row['session_id'], 'agent': row['agent'],
                        'assignment_id': held['assignment_id'], 'state': 'queued'}]}
        told = tell(row, 'note', line=line, deliver=True)
        return {'state': 'queued', 'accepted': bool(told.get('noted')), 'session_id': row['session_id'], **told}

    def notify_user(self, ctx: Context, message: dict[str, Any] | str, change_id: str) -> dict[str, Any]:
        """Publish an actual message in the existing Chat surface, whether or not a PM adapter is connected.

        This is a notification conversation, identified as such in its state, with no model, process or capacity
        reservation. Its rendered message and stable identity make replay harmless and the notification reviewable.
        """
        return events.announced(ctx.folder, ctx.surface, self._notify_user, ctx, message, change_id)[0]

    def _notify_user(self, ctx: Context, message: dict[str, Any] | str, change_id: str) -> dict[str, Any]:
        from . import origin
        from .signals import add_line, own_store
        body = message if isinstance(message, str) else str(message.get('text') or message.get('body') or
                                                          message.get('summary') or '')
        if isinstance(message, dict) and (message.get('update') or message.get('kind')) in (
                'result', 'role_publication', 'functional_assessment', 'functional_correction') and message.get('state') in ('returned', 'delivered', 'completed'):
            body = inbox_status(message)
        if not body:
            raise ValueError('A user notification requires an actual message body.')
        message_id = str(message.get('message_id') or change_id) if isinstance(message, dict) else change_id
        seq = time.time_ns() // 1_000_000
        with own_store(ctx.require_store()).tables() as tx:
            session = tx.get('agent_sessions', {'session_id': UPDATES})
            if session is None:
                tx.insert('agent_sessions', {'session_id': UPDATES, 'work_id': UPDATES, 'agent': 'metaform',
                    'state': 'ended', 'started': home.now(), 'seq': seq, 'origin': origin(), 'how': 'notifications'})
                tx.insert('session_lines', {'session_id': UPDATES, 'name': 'state', 'work_id': UPDATES,
                    'kind': 'state', 'text': json.dumps({'role': 'notification', 'about': 'Project updates',
                    'title': 'Project updates', 'notification': True, 'capabilities': {}, 'commands': []}), 'seq': seq})
            name = f'notification:{message_id}'
            if tx.get('session_lines', {'session_id': UPDATES, 'name': name}) is None:
                seq = max(seq, int(session['seq']) + 1) if session is not None else seq
                tx.insert('session_lines', {'session_id': UPDATES, 'name': name, 'work_id': UPDATES,
                    'kind': 'agent_message_chunk', 'text': body, 'seq': seq + 1})
                tx.update('agent_sessions', {'session_id': UPDATES}, {'seq': seq + 1})
                state: dict[str, Any] = {'role': 'notification', 'about': 'Project updates', 'title': 'Project updates',
                         'notification': True, 'capabilities': {}, 'commands': [], 'latest_message_id': message_id,
                         'latest_message_text': body, 'updated_at': home.now()}
                tx.update('session_lines', {'session_id': UPDATES, 'name': 'state'},
                          {'text': json.dumps(state, ensure_ascii=False), 'seq': seq + 2})
                if isinstance(message, dict):  # what the system agent's inbox names it by, `update_entries`
                    add_line(tx, UPDATES, UPDATES, f'about:{message_id}', 'about', json.dumps(
                        {key: message.get(key) for key in ('work_id', 'kind', 'state', 'table', 'record')},
                        ensure_ascii=False), seq + 2)
                tx.concern(work_id=UPDATES, session_id=UPDATES, kind='session')
        # Updates retain message ids and ticket status. Completion reports remain on their tickets.
        # A failed relay can retry the same id.
        from . import sessions, system_sessions
        running = [row for row in sessions(ctx.require_store()) if row['state'] == 'running']
        route: dict[str, Any] = (message.get('return_to') or {}) if isinstance(message, dict) else {}
        preferred = route.get('session_id')
        pms = [row for row in running if row['session_id'] == preferred] if preferred else system_sessions(
            ctx.require_store(), running)
        delivered_pm: list[dict[str, Any]] = []
        for pm in pms:  # `update` keeps the update's own kind, which the system agent's inbox names it by
            envelope = {**({key: message[key] for key in MESSAGE_FIELDS if key in message}
                           if isinstance(message, dict) else {}), 'id': message_id, 'text': body,
                        'kind': 'project_update', 'update': message.get('kind') if isinstance(message, dict) else None}
            delivered_pm.append(self.send(ctx, {'work_id': pm['work_id'], 'owner_session_id': pm['session_id'],
                                                'assignment_id': None}, envelope))
        return {'state': 'delivered', 'session_id': UPDATES, 'message_id': message_id, 'text': body, 'pm': delivered_pm}


TRANSPORT = Transport()


# Authenticated routing and delivery metadata remain available through dispatch_notes.
MESSAGE_FIELDS = ('work_id', 'assignment_id', 'sender_assignment_id', 'sender_session_id', 'team_id',
                  'change_id', 'transition_id', 'return_to', 'state', 'update', 'ask', 'reply_to',
                  'decision', 'board', 'epoch', 'table', 'record')


CARRIED = ('delivered', 'read', 'replied')


def inbox_what(update: str, state: str, ask: bool, note_id: str, board: str) -> str:
    """What an inbox entry is, in a word or two, for the inbox line: a board item's kind, a question with the note id
    that answers it, a project update's kind (a result by its state), or a note."""
    if board:
        return f'board {board.partition(":")[0]}'
    if ask:
        return f'question, note {note_id}'
    if update == 'result':
        return {'returned': 'done', 'completed': 'done'}.get(state, state or 'result')
    if update:
        return update.removeprefix('functional_').replace('_', ' ')
    return 'note'


def inbox_status(held: dict[str, Any]) -> str:
    """The model-facing notification contains an identifier and status, never authored text or evidence.

    Addresses and reply routes remain in the stored note; the inbox supplies its exact read handle alongside this
    short label, so tickets with the same local number are still inspectable without guessing an address.
    """
    sender = cast(dict[str, Any], held.get('from') or {})
    if (held.get('update') or held.get('kind')) == 'roundtable_result':
        return f'Roundtable {held.get("table")}: {held.get("record")}'
    item = str(sender.get('item') or held.get('work_id') or sender.get('work_id') or '')
    if not held.get('ask') and (held.get('update') or held.get('kind')) in (
            'result', 'role_publication', 'functional_assessment', 'functional_correction') and held.get('state') in (
                'returned', 'delivered', 'completed'):
        if '#' not in item:
            body = str(held.get('text') or held.get('body') or '')
            if body.endswith(' complete') and '#' in body and '\n' not in body:
                return body
        return f'{item} complete'
    number = item.rpartition('#')[2] if '#' in item else item
    label = f'Ticket {number}' if number else str(sender.get('agent') or 'Project')
    what = inbox_what(str(held.get('update') or held.get('kind') or ''), str(held.get('state') or ''),
                      bool(held.get('ask')), str(held.get('id') or ''), str(held.get('board') or ''))
    return f'{label} — {what}'


def inbox_wakes(update: str, state: str, ask: bool) -> bool:
    """Whether an inbox entry needs the person, so it may start the system agent's turn: an agent's question waiting
    on an answer, a recommendation the person decides, or a failed result the person must act on."""
    return ask or update == 'specification_recommendation' or state == 'failed'


def user_updates(ctx: Context) -> list[str]:
    """The project updates the person's system agent, one role across its conversations, has not carried, by id: a
    conversation, new or resumed, takes those written while none ran. One is carried once any system conversation's
    inbox line named it, shown by its `carried:<id>` mark here, or by its note delivered in a system thread."""
    from . import system_sessions
    from .signals import own_store
    store = ctx.require_store()
    systems = system_sessions(store)
    with own_store(store).tables(write=False) as tx:
        rows = tx.rows('session_lines', {'session_id': UPDATES}, by=('session_id', 'seq'), limit=0).results
        carried = {str(row['name']).partition(':')[2] for row in rows if str(row['name']).startswith('carried:')}
        updates = [str(row['name']).partition(':')[2] for row in rows if str(row['name']).startswith('notification:')]
        for ident in set(updates) - carried:
            for system in systems:
                line = tx.get('session_lines', {'session_id': system['session_id'], 'name': f'peer:{ident}'})
                held: Any = json.loads(str(line['text'])) if line is not None else {}
                states = [*cast(dict[str, Any], held.get('session_states') or {}).values(),
                          *cast(dict[str, Any], held.get('states') or {}).values()]
                if any(state in CARRIED for state in states):
                    carried.add(ident)
                    break
    return [ident for ident in updates if ident not in carried]


def update_entries(ctx: Context, idents: list[str], *, passive: set[str] | None = None) -> list[tuple[str, str, bool]]:
    """Each project update as the system agent's inbox names it, by id: its ticket and kind, from the `about:<id>`
    line its notification keeps, never its words, and whether it needs the person."""
    from .signals import own_store
    if not idents:
        return []
    store = ctx.require_store()
    about: dict[str, dict[str, Any]] = {}
    with own_store(store).tables(write=False) as tx:
        for ident in idents:
            line = tx.get('session_lines', {'session_id': UPDATES, 'name': f'about:{ident}'})
            with contextlib.suppress(ValueError, TypeError):
                about[ident] = json.loads(str(line['text'])) if line is not None else {}
    from . import helper_id, helper_item
    works = sorted({str(one.get('work_id')) for one in about.values() if one.get('work_id')
                    and not helper_id(one.get('work_id'))})
    named: dict[str, Any] = store.numbers_of('work', works) if works else {}
    entries: list[tuple[str, str, bool]] = []
    for ident in idents:
        held = about.get(ident) or {}
        work, update, state = str(held.get('work_id') or ''), str(held.get('kind') or 'update'), str(held.get('state') or '')
        item = str(named[work][0]) if work in named else helper_item(work) if helper_id(work) else work
        if update == 'roundtable_result' and passive is not None:
            passive.add(ident)
        entries.append((ident, inbox_status({**held, 'id': ident, 'from': {'item': item}}),
                        inbox_wakes(update, state, False)))
    return entries


def carried_updates(ctx: Context, idents: list[str]) -> None:
    """Mark project updates a system conversation's accepted turn carried, so no other conversation is given them."""
    from .signals import add_line, own_store
    with own_store(ctx.require_store()).tables() as tx:
        for ident in idents:
            if tx.get('session_lines', {'session_id': UPDATES, 'name': f'notification:{ident}'}) is not None:
                add_line(tx, UPDATES, UPDATES, f'carried:{ident}', 'carried',
                         json.dumps({'runner': ctx.session, 'at': home.now()}))


def broadcast(ctx: Context, text: str, team: str | None = None) -> dict[str, Any]:
    from . import BROADCASTS
    from .signals import own_store
    owner, gc, sender = owned_gc(ctx, team)
    ident = hashlib.sha256(f'{gc["assignment_id"]}:{time.time_ns()}'.encode()).hexdigest()[:16]
    recipients: list[dict[str, Any]] = []
    for member in owner.members(ctx, gc['team_id']):
        if (member['assignment_id'] == gc['assignment_id'] or member.get('stop')
                or member['state'] in ('returned', 'delivered', 'failed', 'stopped', 'transferred')):
            continue
        event = owner.queue_message(ctx, member['assignment_id'],
            {'id': ident, 'kind': 'gc_broadcast', 'from': sender, 'text': text, 'team_id': gc['team_id']},
            key=ident)
        recipients.append({'work_id': member['work_id'], 'assignment_id': member['assignment_id'],
                           'session_id': member.get('owner_session_id'), 'transition_id': event['transition_id'],
                           'state': 'queued', 'steered': False})
    line = {'id': ident, 'text': text, 'from': sender, 'at': home.now(), 'team_id': gc['team_id'],
            'recipients': recipients}
    with own_store(ctx.require_store()).tables() as tx:
        tx.insert('session_lines', {'session_id': BROADCASTS, 'work_id': BROADCASTS, 'name': f'broadcast:{ident}',
            'kind': 'broadcast', 'text': json.dumps(line, ensure_ascii=False), 'seq': time.time_ns() // 1_000_000})
    drain(ctx, [str(one['work_id']) for one in recipients])
    return {'sent': ident, 'team_id': gc['team_id'], 'recipients': recipients, 'steered': False}


def transitions_changed(payload: dict[str, Any]) -> bool:
    """Recognize transition writes even when an aggregate includes a write with no named concerns.

    The event bus deliberately omits all concerns when any write in a command leaves them unspecified. A public
    delegation can create work and transition rows in that same command. The owning table still proves that a
    drain is relevant; unrelated table events must cause no orchestration reads.
    """
    tables: Any = payload.get('tables') or []
    tables = [tables] if isinstance(tables, str) else tables
    kinds: list[Any] = payload.get('kinds') or []
    return (not kinds and 'orchestration.transitions' in tables) or any(str(kind) in (
            'orchestration.launch', 'orchestration.return', 'orchestration.direction', 'orchestration.change',
            'orchestration.stop', 'orchestration.suspend', 'orchestration.send', 'orchestration.user_message',
            'orchestration.publish', 'orchestration.assessment') for kind in kinds)


def changed(payload: dict[str, Any], ctx: Context) -> None:
    """Only orchestration transitions trigger a drain; per-assignment locks and runner leases deduplicate starts."""
    if payload.get('project') != ctx.project or not transitions_changed(payload):
        return
    drain(ctx, payload.get('work_ids'))


def resume_context(ctx: Context, work: str, session: str | None) -> dict[str, Any]:
    owner = service(ctx)
    return owner.context(ctx, work_id=work, session_id=session) or {} if owner is not None else {}


def snapshots(sent: list[prompt_files.Sent]) -> list[dict[str, Any]]:
    return [{'name': one.name, 'text': getattr(one, 'rendered_text', ''), 'actual_version_id': one.version_id,
             'selected_version_id': one.selected_version_id, 'rendered_fingerprint': one.rendered_fingerprint,
             'number': one.number, 'origin': one.origin, 'bindings': one.bindings, 'problems': list(one.problems)}
            for one in sent]
