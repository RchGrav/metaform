"""Peer delivery metadata and project notifications retained after organizational execution was retired."""
from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from typing import Any, cast

from metaform import events, home, prompt_files
from metaform.data import Store, StoreError
from metaform.module import Context

UPDATES = 'conversation-orchestration-updates'
PLAN_UPDATE = 'plan_report'  # the kind of project update that says a plan's last ticket is done, code.dispatcher.agent#10


class Transport:
    """Persist user notifications without executing organizational assignments."""

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
        # Project updates are UI records. They never enter any agent's context or resume queue.
        return {'state': 'delivered', 'session_id': UPDATES, 'message_id': message_id, 'text': body, 'pm': []}

    def plan_done(self, ctx: Context, store: Store, work_id: str, records: list[Any]) -> dict[str, Any] | None:
        """One project update for a plan whose last ticket is done, `PLAN_UPDATE`: one line with the plan's tickets
        by outcome, from its first ticket to the one just done, named by the plan's tickets so the same plan is said
        once; None when it was said already. The UI shows it without waking an agent,
        since completion alone requires no model turn (code.dispatcher.agent#10, item 4)."""
        from .signals import own_store
        members = sorted(str(record.id) for record in records)
        ident = f'plan:{hashlib.sha256(" ".join(members).encode()).hexdigest()[:16]}'
        with own_store(ctx.require_store()).tables(write=False) as tx:
            if tx.get('session_lines', {'session_id': UPDATES, 'name': f'notification:{ident}'}) is not None:
                return None
        counts = Counter(str(record.outcome or 'completed') for record in records)
        numbered = store.numbers_of('work', members)
        first = min(records, key=lambda record: str(record.created))
        last = next((record for record in records if str(record.id) == work_id), first)

        def named(record: Any) -> str:
            ref, title = numbered.get(str(record.id), (str(record.id)[:8], None, None))[:2]
            return f'{ref} "{title}"' if title else ref

        ended = ', '.join(f'{count} {outcome}' for outcome, count in sorted(counts.items()))
        text = f'Plan done: {len(records)} tickets, {ended}, from {named(first)} to {named(last)}.'
        return self.notify_user(ctx, {'message_id': ident, 'kind': PLAN_UPDATE, 'state': 'completed',
                                      'work_id': work_id, 'text': text}, ident)


TRANSPORT = Transport()


# Authenticated routing and delivery metadata remain available through dispatch_notes.
MESSAGE_FIELDS = ('work_id', 'assignment_id', 'sender_assignment_id', 'sender_session_id', 'team_id',
                  'change_id', 'transition_id', 'return_to', 'state', 'update', 'ask', 'reply_to',
                  'decision', 'board', 'epoch', 'table', 'record', 'withdrawn', 'resolved', 'superseded', 'cancelled')


def actionable(ctx: Context, envelope: dict[str, Any], *, session_id: str | None = None,
               recipient: dict[str, Any] | None = None) -> bool:
    """Wake for authored peer messages and directions, without organizational ownership checks.

    Peer producers authenticate their caller before recording the envelope. Project status and completion metadata
    remain readable records and do not independently request another model turn.
    """
    if any(envelope.get(key) for key in ('withdrawn', 'resolved', 'superseded', 'cancelled')) or \
            envelope.get('state') in ('withdrawn', 'resolved', 'superseded', 'cancelled', 'stopped'):
        return False
    kind = str(envelope.get('kind') or '')
    if kind == 'user_direction':
        return True
    sender = cast(dict[str, Any], envelope.get('from') or {})
    return kind in ('peer', 'message', 'note', 'question', 'invitation', 'direction') and bool(sender.get('session_id'))


def delivery_metadata(held: dict[str, Any]) -> dict[str, Any]:
    """Small replay marker beside a peer line, using the existing session/kind index. No message body."""
    return {key: held[key] for key in (*MESSAGE_FIELDS, 'id', 'kind', 'from', 'to', 'actionable', 'tickets') if key in held}


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
    """Explicit questions request a reply. Status updates alone require no agent turn."""
    return ask


def user_updates(ctx: Context) -> list[str]:
    """Project history is read explicitly. Startup must not scan notification bodies or replay old notices."""
    return []


def update_entries(ctx: Context, idents: list[str], *, passive: set[str] | None = None) -> list[tuple[str, str, bool]]:
    """Retained notification IDs from older runners confer no permission to consume model context."""
    return []


def carried_updates(ctx: Context, idents: list[str]) -> None:
    """Mark project updates a system conversation's accepted turn carried, so no other conversation is given them."""
    from .signals import add_line, own_store
    with own_store(ctx.require_store()).tables() as tx:
        for ident in idents:
            if tx.get('session_lines', {'session_id': UPDATES, 'name': f'notification:{ident}'}) is not None:
                add_line(tx, UPDATES, UPDATES, f'carried:{ident}', 'carried',
                         json.dumps({'runner': ctx.session, 'at': home.now()}))


def plan_changed(payload: dict[str, Any], ctx: Context) -> None:
    """map.changed: a ticket done, the change's kind `done`. When it was the last open ticket of its plan, the tickets
    tied to it by `after_work` in either direction, the plan is done, and `Transport.plan_done` says so once to the
    person's system agent (code.dispatcher.agent#10, item 4). Decided from the event first, so every other change
    reads nothing; then one read of the map's `after` table, which keeps every plan's ties, and one of the plan's
    tickets. A ticket tied to none is no plan and says nothing."""
    kinds: Any = payload.get('kinds')
    named: Any = payload.get('work_ids')
    if not isinstance(kinds, list) or 'done' not in kinds or not isinstance(named, list) or not named:
        return
    if payload.get('project') != ctx.project:
        return
    held = ctx.require_store()
    store = Store(held.project_id, base=payload['base_id']) if payload.get('base_id') else held
    try:
        with Store(store.project_id, module='map').tables(write=False) as tx:
            rows = tx.rows('after', limit=0).results
    except StoreError:
        return
    tied: dict[str, set[str]] = {}
    for row in rows:
        raw: Any = row['works']
        for before in ([str(one) for one in cast(list[Any], raw)] if isinstance(raw, list) else []):
            tied.setdefault(str(row['work_id']), set()).add(before)
            tied.setdefault(before, set()).add(str(row['work_id']))
    said: set[str] = set()
    for work_id in [str(one) for one in cast(list[Any], named)]:
        plan = plan_members(tied, work_id)
        if len(plan) < 2 or plan & said:
            continue
        said |= plan
        try:
            records = store.work(ids=sorted(plan), limit=0).results
        except StoreError:
            return
        if records and all(record.done is not None for record in records):
            TRANSPORT.plan_done(ctx, store, work_id, list(records))


def plan_members(tied: dict[str, set[str]], work_id: str) -> set[str]:
    """The tickets of one plan: `work_id` and every ticket reached from it through `after_work` ties in either
    direction, done or not, so a plan is the same set from its first ticket to its last."""
    found, reach = {work_id}, [work_id]
    while reach:
        for other in tied.get(reach.pop(), ()):
            if other not in found:
                found.add(other)
                reach.append(other)
    return found


def snapshots(sent: list[prompt_files.Sent]) -> list[dict[str, Any]]:
    return [{'name': one.name, 'text': getattr(one, 'rendered_text', ''), 'actual_version_id': one.version_id,
             'selected_version_id': one.selected_version_id, 'rendered_fingerprint': one.rendered_fingerprint,
             'number': one.number, 'origin': one.origin, 'bindings': one.bindings, 'problems': list(one.problems),
             'source': dict(one.source), 'delivery_path': 'acp_prompt'}
            for one in sent]
