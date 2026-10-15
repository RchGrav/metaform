"""Peer notes, code.dispatcher.agent#32, BASE-052: information between the agents working open tickets, never steering.

An agent reaches the others by their work, not by their sessions: one ticket, by work id or `<address>#<n>`; whoever
works at a part of the map or inside it, `at=<Address>`, a trunk Address reaching a whole area; whoever touched a file
or a folder, `file=<path>`, from the paths its tool calls named; or the tickets whose titles hold some words,
`topic=<words>`. `peers` shows who is where, with the files each touched and what each said last, and with `at=` or
`file=` answers who else is in that part or file before an edit, with a note ready to send them.

A note is a `peer` line, `peer:<id>`, in the sender's thread and in each receiver's, the same JSON on every copy, so
both tickets keep every exchange and no table changes. Each receiver's runner takes it as a turn after any in flight,
never steered into one, and marks its delivery on its copy and on the sender's, `signals.mark_peer`: queued, delivered,
read, replied. With `wait=<seconds>` the note is a question and the call waits for the replies threaded to it,
`reply=<id>`, and says plainly who did not answer; a reply that reaches a waiting sender is returned by the call rather
than given to it again as a turn. A note never starts, stops, interrupts or redirects anyone, so the authority check
`may_steer` does not apply to it, and two caps an hour keep two agents from answering each other without end.
"""
from __future__ import annotations

import asyncio
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any, cast

from metaform.data import Store, StoreError, WorkRecord, parse_reference
from metaform.module import Context, Stop, work_reads

from . import intake_id, session_status, sessions, summoned, tell, ticket
from .signals import mark_peer, own_store

NOTE_MOST = 1000  # characters in one note
NOTES_HOURLY = 10  # notes one ticket's agent sends in an hour, however many agents each reaches
PAIR_HOURLY = 6  # notes between one pair of tickets in an hour, both ways together
NOTE_REACH = 8  # agents one note reaches at most; a wider Address is narrowed instead
WAIT_MOST = 120  # seconds a question waits for its replies
HOUR = 3600
RECENT_FILES = 12  # the files presence shows for each agent, the latest first
RECENT_LINES = 10  # the file lines presence shows for each of them
SAID_MOST = 240  # characters of what an agent said last that presence shows
TARGETS = ('to', 'at', 'file', 'topic', 'reply')


def stamp(at: float | None = None) -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(at))


def told(row: dict[str, Any], op: str, **given: Any) -> dict[str, Any]:
    """A request to a session's runner; one that does not answer is said in the answer, never raised, so a note to
    several agents still reaches the others."""
    try:
        return tell(row, op, **given)
    except OSError as error:
        return {'error': str(error) or type(error).__name__}


def caller(store: Store) -> tuple[WorkRecord, dict[str, Any]]:
    """The calling agent's ticket and running session, found by the work and runner its session was started with."""
    work, runner = os.environ.get('METAFORM_WORK'), os.environ.get('METAFORM_SESSION')
    if not work or not runner or intake_id(work):
        raise Stop('A note is sent by the agent working a ticket, from its own session, to agents working other open '
                   'tickets.', 'metaform help dispatch note')
    mine = next((one for one in sessions(store, work, verify=False)
                 if one.get('runner') == runner and one.get('state') == 'running'), None)
    if mine is None or session_status(own_store(store), mine, done=False)['state'] != 'running':
        raise Stop('Your session is not running here, so it sends no note.', f'metaform dispatch sessions id={work}')
    return ticket(store, work), mine


def numbered(ctx: Context, record: WorkRecord) -> tuple[str, str]:
    """A ticket's number, `<address>#<n>`, and title as the map module shows them under `map`, BASE-035; its work id
    and no title when the map keeps none."""
    kept = work_reads(ctx.folder, record, project=ctx.project).get('map')
    held = cast(dict[str, Any], kept) if isinstance(kept, dict) else {}
    return str(held.get('item') or record.id), str(held.get('title') or '')


def addresses(record: WorkRecord) -> list[str]:
    """The Addresses a ticket is at: its element's, or its join's receiver and provider."""
    return [one for one in (record.address, record.receiver_address, record.provider_address) if one]


def side(ctx: Context, record: WorkRecord, row: dict[str, Any]) -> dict[str, Any]:
    """One end of a note: the ticket, its agent and session, and the node its figure stands at."""
    item, title = numbered(ctx, record)
    return {'work_id': record.id, 'item': item, 'title': title, 'agent': str(row['agent']),
            'session_id': str(row['session_id']), 'address': (addresses(record) or [''])[0],
            'node': {'kind': record.node_kind, 'id': record.node_id}}


def _prefixed(tx: Any, session_id: str, prefix: str) -> list[dict[str, Any]]:
    """A thread's lines whose names begin with `prefix`, read through the key from there, a page at a time."""
    found: list[dict[str, Any]] = []
    after: str | None = json.dumps([prefix])
    while after is not None:
        page = tx.rows('lines', {'session_id': session_id}, after=after, limit=100)
        rows = [dict(row) for row in page.results if str(row['name']).startswith(prefix)]
        found += rows
        after = page.next if len(rows) == len(page.results) else None
    return found


def _parsed(text: Any) -> dict[str, Any] | None:
    try:
        value: Any = json.loads(str(text))
    except ValueError:
        return None
    return cast(dict[str, Any], value) if isinstance(value, dict) else None


def touched(tx: Any, session_id: str) -> list[dict[str, Any]]:
    """The files a session's tool calls named, the latest first, each once: `edit` when a call changed it, else the
    call's kind; with the file lines its calls named (`lines`, from ACP's locations, which an adapter gives for the
    place it reads or edits) and how many lines its edits added and removed (`changed`), so another agent can tell
    work in the same lines from work in the same file. The files it read or wrote through the runner, kept in its
    state, are among them."""
    named: list[tuple[int, str, str, int | None, int]] = []
    for row in _prefixed(tx, session_id, 'detail:'):
        detail = _parsed(row['text'])
        if detail is None:
            continue
        seq = int(row['seq'])
        for diff in cast(list[dict[str, Any]], detail.get('diffs') or []):
            changed = int(diff.get('added') or 0) + int(diff.get('removed') or 0)
            named.append((seq, str(diff.get('path') or ''), 'edit', None, changed))
        for place in cast(list[dict[str, Any]], detail.get('locations') or []):
            line = place.get('line')
            named.append((seq, str(place.get('path') or ''), 'edit' if detail.get('diffs') else
                          str(detail.get('kind') or 'read'), int(line) if isinstance(line, int) else None, 0))
    state = tx.get('lines', {'session_id': session_id, 'name': 'state'})
    held = _parsed(state['text']) if state is not None else None
    for place, one in enumerate(cast(list[dict[str, Any]], (held or {}).get('files') or [])):
        named.append((-place, str(one.get('path') or ''), str(one.get('action') or 'read'), None, 0))
    files: dict[str, dict[str, Any]] = {}
    for _, path, action, line, changed in sorted(named, key=lambda one: -one[0]):
        if not path:
            continue
        entry = files.setdefault(path, {'path': path, 'action': action, 'lines': [], 'changed': 0})
        if action == 'edit':
            entry['action'] = 'edit'
        if line is not None and line not in entry['lines'] and len(entry['lines']) < RECENT_LINES:
            entry['lines'].append(line)
        entry['changed'] += changed
    return [{key: value for key, value in entry.items() if value or key in ('path', 'action')}
            for entry in files.values()]


def said(tx: Any, session_id: str) -> str:
    """The end of the last message a session's agent wrote, at most SAID_MOST characters."""
    last = max((row for row in _prefixed(tx, session_id, 'flow:') if row['kind'] == 'agent_message_chunk'),
               key=lambda row: int(row['seq']), default=None)
    text = ' '.join(str(last['text']).split()) if last is not None else ''
    return text if len(text) <= SAID_MOST else '…' + text[-SAID_MOST:]


def working(ctx: Context, store: Store) -> list[dict[str, Any]]:
    """Every agent at work now on an open ticket it has taken: its ticket, Address, activity, the files it touched
    and what it said last; a ticket done, not taken, an intake and the conversations the person summoned are left
    out. Each entry carries its ticket and session under `_record` and `_row` for the caller."""
    running: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for row in sessions(store, verify=False):
        work_id = str(row['work_id'])
        if row.get('state') != 'running' or intake_id(work_id) or summoned(row):
            continue
        status = session_status(own_store(store), row, done=False)
        if status['state'] == 'running':
            running[work_id] = (row, status)
    found: list[dict[str, Any]] = []
    try:
        with own_store(store).tables(write=False) as tx:
            for work_id, (row, status) in running.items():
                try:
                    record = store.ticket(work_id).work
                except StoreError:
                    continue
                if record.done or not record.taken_by:
                    continue
                found.append({**side(ctx, record, row), 'activity': status.get('activity') or 'working',
                              'files': touched(tx, str(row['session_id'])), 'said': said(tx, str(row['session_id'])),
                              '_record': record, '_row': row})
    except StoreError:
        pass
    return found


def shown(entry: dict[str, Any], files: int = RECENT_FILES) -> dict[str, Any]:
    """An entry of `working` as an agent reads it: no private fields, its latest files only."""
    return {**{key: value for key, value in entry.items() if not key.startswith('_') and key != 'node'},
            'files': entry['files'][:files]}


def project_path(store: Store, given: str) -> str:
    """A path as the threads keep it: from the project folder, with forward slashes and no trailing slash."""
    path = Path(given.strip()).expanduser()
    root = Path(store.project().path).resolve()
    if path.is_absolute():
        try:
            path = path.resolve().relative_to(root)
        except ValueError:
            pass
    text = path.as_posix()
    while text.startswith('./'):
        text = text[2:]
    return text.rstrip('/')


def at_part(entry: dict[str, Any], address: str) -> bool:
    return any(one == address or one.startswith(address + '.') for one in addresses(entry['_record']))


def in_file(entry: dict[str, Any], path: str) -> bool:
    return any(one['path'] == path or one['path'].startswith(path + '/') for one in entry['files'])


def on_topic(entry: dict[str, Any], words: list[str]) -> bool:
    title = str(entry['title']).lower()
    return bool(words) and all(word in title for word in words)


def chosen(ctx: Context, store: Store, record: WorkRecord) -> tuple[str, str, list[dict[str, Any]],
                                                                    dict[str, Any] | None]:
    """Whom a note goes to: the target named, its kind, the agents at work there other than the caller, and the
    note it answers when it is a reply."""
    given = {name: str(ctx.nouns[name]).strip() for name in TARGETS if str(ctx.nouns.get(name) or '').strip()}
    if len(given) != 1:
        raise Stop('A note names whom it goes to, one of: to=<work id or address#n>, at=<Address>, file=<path>, '
                   'topic=<words> or reply=<note id>.', 'metaform dispatch peers')
    (kind, named), = given.items()
    everyone = [entry for entry in working(ctx, store) if entry['work_id'] != record.id]
    answered: dict[str, Any] | None = None
    if kind == 'reply':
        answered = next((one for one in peer_lines(store, record.id) if one.get('id') == named), None)
        if answered is None or cast(dict[str, Any], answered.get('from') or {}).get('work_id') == record.id:
            raise Stop(f'No note {named} came to your ticket, so there is none to answer.', 'metaform dispatch notes')
        target = str(cast(dict[str, Any], answered['from']).get('work_id'))
        found = [entry for entry in everyone if entry['work_id'] == target]
        if not found:
            raise Stop(f'The agent that sent note {named} is no longer at work on an open ticket, so the reply would '
                       'reach no one.', 'metaform dispatch peers')
        return named, kind, found, answered
    if kind == 'to':
        target = named
        reference = parse_reference(named)
        if reference is not None:
            item = store.item_at(*reference)
            if item is None or item.get('kind') != 'work':
                raise Stop(f'No ticket is numbered {named}.', 'metaform dispatch peers')
            target = str(item['id'])
        if target == record.id:
            raise Stop('That is your own ticket; a note goes to the agent on another.', 'metaform dispatch peers')
        found = [entry for entry in everyone if entry['work_id'] == target]
        if not found:
            ticket(store, target)  # an unknown ticket is said as such
            raise Stop(f'No agent is at work on {named} now: it is done, not taken, or its agent is not running, so '
                       'the note would reach no one.', 'metaform dispatch peers')
        return named, kind, found, None
    if kind == 'at':
        found = [entry for entry in everyone if at_part(entry, named)]
    elif kind == 'file':
        path = project_path(store, named)
        found = [entry for entry in everyone if in_file(entry, path)]
    else:
        found = [entry for entry in everyone if on_topic(entry, named.lower().split())]
    if not found:
        raise Stop(f'No other agent is at work with {kind}={named} now, so the note would reach no one.',
                   'metaform dispatch peers')
    if len(found) > NOTE_REACH:
        raise Stop(f'{len(found)} agents are at work with {kind}={named}; a note reaches at most {NOTE_REACH}. Name a '
                   'narrower part, a file or one ticket.', f'metaform dispatch peers {kind}={named}')
    return named, kind, found, None


def peer_lines(store: Store, work_id: str) -> list[dict[str, Any]]:
    """The peer notes kept in a ticket's threads, each once, those it sent and those it was sent, each with the
    thread that keeps it as `_session`."""
    found: dict[str, dict[str, Any]] = {}
    try:
        with own_store(store).tables(write=False) as tx:
            for session in sessions(store, work_id, verify=False):
                for row in _prefixed(tx, str(session['session_id']), 'peer:'):
                    value = _parsed(row['text'])
                    if value is not None:
                        found[str(value.get('id'))] = {**value, '_session': str(session['session_id'])}
    except StoreError:
        pass
    return sorted(found.values(), key=lambda one: float(one.get('epoch') or 0))


def ends(one: dict[str, Any]) -> tuple[str, set[str]]:
    """The work ids a note is from and to."""
    to: Any = one.get('to') or []
    receivers = [cast(dict[str, Any], to)] if isinstance(to, dict) else cast(list[dict[str, Any]], to)
    return str(cast(dict[str, Any], one.get('from') or {}).get('work_id') or ''), \
        {str(end.get('work_id') or '') for end in receivers}


def room(store: Store, work: str, found: list[dict[str, Any]], now: float) -> tuple[list[dict[str, Any]],
                                                                                     list[dict[str, Any]]]:
    """The receivers a note may go to under the caps, and those a pair's cap holds back with when it frees; a
    sender past its own cap is refused, saying when the next can go. The sender's threads keep every note it sent
    and every note sent to it, so both counts read there."""
    recent = [one for one in peer_lines(store, work) if float(one.get('epoch') or 0) > now - HOUR]
    sent = sorted(float(one['epoch']) for one in recent if ends(one)[0] == work)
    if len(sent) >= NOTES_HOURLY:
        frees = stamp(sent[len(sent) - NOTES_HOURLY] + HOUR)
        raise Stop(f'No note sent: you have sent {len(sent)} notes in the last hour, and the most is {NOTES_HOURLY}, '
                   f'so agents never answer each other in a loop. The next can go at {frees}. Until then, put it in '
                   'your own ticket\'s note for the person.', 'metaform map work op=edit id=<your work id> note="..."')
    allowed: list[dict[str, Any]] = []
    held: list[dict[str, Any]] = []
    for entry in found:
        other = entry['work_id']
        pair = sorted(float(one['epoch']) for one in recent
                      if (ends(one)[0] == work and other in ends(one)[1])
                      or (ends(one)[0] == other and work in ends(one)[1]))
        if len(pair) >= PAIR_HOURLY:
            held.append({'work_id': other, 'item': entry['item'], 'notes': len(pair),
                         'frees': stamp(pair[len(pair) - PAIR_HOURLY] + HOUR)})
        else:
            allowed.append(entry)
    if not allowed:
        one = held[0]
        raise Stop(f'No note sent: you and {one["item"]} have sent each other {one["notes"]} notes in the last hour, '
                   f'and the most is {PAIR_HOURLY}, so agents never answer each other in a loop. The next can go at '
                   f'{one["frees"]}. Until then, put it in your own ticket\'s note for the person.',
                   'metaform map work op=edit id=<your work id> note="..."')
    return allowed, held


def wait_seconds(ctx: Context) -> float:
    given = ctx.nouns.get('wait')
    if given in (None, '', 0, '0', False):
        return 0.0
    try:
        seconds = float(str(given))
    except ValueError:
        seconds = -1.0
    if not 1 <= seconds <= WAIT_MOST:
        raise Stop(f'A question waits from 1 to {WAIT_MOST} seconds for its replies.',
                   'metaform dispatch note to=<ticket> wait=60 -- "<question>"')
    return seconds


def send(ctx: Context, store: Store, text: str, wait: float) -> dict[str, Any]:
    """Send one note, keeping it first in the sender's thread so each receiver's delivery marks land on it, then
    giving it to each receiver's runner; a receiver whose runner does not take it is marked failed."""
    record, mine = caller(store)
    named, kind, found, answered = chosen(ctx, store, record)
    now = time.time()
    allowed, held = room(store, record.id, found, now)
    note_id = secrets.token_hex(8)
    line: dict[str, Any] = {
        'id': note_id, 'at': stamp(now), 'epoch': now, 'text': text, 'ask': wait > 0,
        'reply_to': answered.get('id') if answered else None, 'target': {kind: named},
        'from': side(ctx, record, mine),
        'to': [{key: value for key, value in entry.items() if not key.startswith('_')
                and key not in ('files', 'said', 'activity')} for entry in allowed],
        'states': {entry['work_id']: 'queued' for entry in allowed}}
    kept = told(mine, 'note', line=line, awaiting=wait)
    if not kept.get('noted'):
        raise Stop(f'Your own session did not keep the note: {kept.get("error") or "no answer"}. Nothing was sent.',
                   f'metaform dispatch sessions id={record.id}')
    taken: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for entry in allowed:
        answer = told(entry['_row'], 'note', line=line, deliver=True)
        (taken if answer.get('noted') else failed).append({'item': entry['item'], 'agent': entry['agent'],
                                                           'work_id': entry['work_id'],
                                                           **({'error': str(answer.get('error') or 'no answer')}
                                                              if not answer.get('noted') else
                                                              {'turn': 'after the turn in flight' if answer.get('busy')
                                                               else 'now'})})
    with own_store(store).tables() as tx:
        for one in failed:
            mark_peer(tx, str(mine['session_id']), note_id, one['work_id'], 'failed')
        if answered is not None:  # the note it answers is replied, on the receiver's copy and on its sender's
            sender = cast(dict[str, Any], answered.get('from') or {})
            for session_id in {str(answered['_session']), str(sender.get('session_id') or '')} - {''}:
                mark_peer(tx, session_id, str(answered['id']), record.id, 'replied')
    ctx.publish('map.changed', {'project': store.project_id, 'tables': 'dispatch', 'dispatch_tables': ['dispatch.lines']})
    if not taken:
        raise Stop('No agent took the note: ' + '; '.join(f'{one["item"]}: {one["error"]}' for one in failed) + '.',
                   'metaform dispatch peers')
    reached = ', '.join(f'{one["agent"]} on {one["item"]} {one["turn"]}' for one in taken)
    words = f'Your {"question" if wait else "note"} {note_id} reaches {reached}; it is kept on every ticket it touches.'
    if held:
        words += ' Held back by the cap between two tickets: ' + ', '.join(
            f'{one["item"]} until {one["frees"]}' for one in held) + '.'
    if failed:
        words += ' Not taken: ' + ', '.join(f'{one["item"]} ({one["error"]})' for one in failed) + '.'
    return {'sent': True, 'note': note_id, 'to': taken, 'held': held, 'failed': failed, 'said': words,
            '_mine': mine, '_work': record.id}


def replies(store: Store, work: str, note_id: str, receivers: set[str]) -> list[dict[str, Any]]:
    return [one for one in peer_lines(store, work) if one.get('reply_to') == note_id and ends(one)[0] in receivers]


async def note(ctx: Context) -> dict[str, Any]:
    """`dispatch note`: send a note, and with wait=<seconds> wait for the replies threaded to it, said plainly when
    none comes. It waits on map changes from the receivers' runners, BASE-053, never on a timer, QUAL-015."""
    store = ctx.require_store()
    given: Any = ctx.nouns.get('text') or []
    text = (' '.join(str(word) for word in cast(list[Any], given)) if isinstance(given, (list, tuple))
            else str(given)).strip()
    if not text:
        raise Stop('A note says what the other agent should know.',
                   'metaform dispatch note to=<work id or address#n> -- "<note>"')
    if len(text) > NOTE_MOST:
        raise Stop(f'A note is at most {NOTE_MOST} characters, and this one is {len(text)}. Say the point and where '
                   'the rest is, such as a file or your ticket.', 'metaform dispatch note to=<ticket> -- "<note>"')
    wait = wait_seconds(ctx)
    sent = await asyncio.to_thread(send, ctx, store, text, wait)
    mine, work = cast(dict[str, Any], sent.pop('_mine')), str(sent.pop('_work'))
    if not wait:
        return sent
    receivers = {str(one['work_id']) for one in sent['to']}
    loop = asyncio.get_running_loop()
    heard = asyncio.Event()

    def changed(payload: dict[str, Any]) -> None:
        if payload.get('project') == store.project_id:
            loop.call_soon_threadsafe(heard.set)
    deadline = loop.time() + wait
    got: list[dict[str, Any]] = []
    with ctx.listen(changed):
        while True:
            heard.clear()  # before the read, so a reply written during it wakes the wait again
            got = await asyncio.to_thread(replies, store, work, sent['note'], receivers)
            if {ends(one)[0] for one in got} >= receivers:
                break
            try:
                await asyncio.wait_for(heard.wait(), max(deadline - loop.time(), 0))
            except TimeoutError:
                got = await asyncio.to_thread(replies, store, work, sent['note'], receivers)
                break
    # replies the runner held for this wait and the call did not return go to the agent as turns after all
    await asyncio.to_thread(told, mine, 'unawait', id=sent['note'], taken=[str(one['id']) for one in got])

    def read() -> None:
        with own_store(store).tables() as tx:
            for one in got:
                sender = cast(dict[str, Any], one.get('from') or {})
                for session_id in {str(one['_session']), str(sender.get('session_id') or '')} - {''}:
                    mark_peer(tx, session_id, str(one['id']), work, 'read')
    await asyncio.to_thread(read)
    answered = {ends(one)[0] for one in got}
    silent = [one for one in sent['to'] if one['work_id'] not in answered]
    words = sent['said']
    if got:
        words += ' Replies: ' + ' '.join(
            f'{cast(dict[str, Any], one["from"]).get("agent")} on {cast(dict[str, Any], one["from"]).get("item")}: '
            f'{one.get("text")}' for one in got)
    if silent:
        words += (f' No reply came from {", ".join(one["item"] for one in silent)} within {wait:g} seconds; a later '
                  'reply reaches you as a turn of its own.')
    return {**sent, 'replies': [{'note': one['id'], 'from': {key: cast(dict[str, Any], one['from']).get(key)
                                                              for key in ('work_id', 'item', 'title', 'agent')},
                                 'text': one.get('text'), 'at': one.get('at')} for one in got],
            'unanswered': silent, 'said': words}


def notes(ctx: Context) -> dict[str, Any]:
    """`dispatch notes`: the caller's notes, sent and received, the latest first, each with its delivery to each
    receiver; with note=<id>, that note and the replies threaded to it."""
    store = ctx.require_store()
    record, _ = caller(store)
    held = peer_lines(store, record.id)
    wanted = str(ctx.nouns.get('note') or '')
    if wanted:
        held = [one for one in held if one.get('id') == wanted or one.get('reply_to') == wanted]
        if not held:
            raise Stop(f'Your ticket keeps no note {wanted}.', 'metaform dispatch notes')
    limit = ctx.nouns.get('limit')
    count = int(limit) if isinstance(limit, int) and limit > 0 else 20
    listed = [{'note': one.get('id'), 'at': one.get('at'),
               'way': 'sent' if ends(one)[0] == record.id else 'received',
               'from': {key: cast(dict[str, Any], one.get('from') or {}).get(key) for key in ('item', 'agent')},
               'to': [{key: end.get(key) for key in ('item', 'agent', 'work_id')}
                      for end in cast(list[dict[str, Any]], one.get('to') or [])],
               'text': one.get('text'), 'ask': bool(one.get('ask')), 'reply_to': one.get('reply_to'),
               'states': one.get('states') or {}} for one in reversed(held)]
    return {'notes': listed[:count], 'more': max(len(listed) - count, 0)}


def peers(ctx: Context) -> dict[str, Any]:
    """`dispatch peers`: who is at work where, each agent with its ticket, Address, activity, the files it touched and
    what it said last. With at=<Address>, file=<path> or topic=<words>, only those working there, for the question
    "who else is in this part or file?" before an edit, with the note ready to send them."""
    store = ctx.require_store()
    mine = os.environ.get('METAFORM_WORK')
    everyone = working(ctx, store)
    given = {name: str(ctx.nouns[name]).strip() for name in ('at', 'file', 'topic')
             if str(ctx.nouns.get(name) or '').strip()}
    if len(given) > 1:
        raise Stop('peers narrows by one of at=<Address>, file=<path> or topic=<words>.', 'metaform help dispatch peers')
    found = everyone
    if given:
        (kind, named), = given.items()
        if kind == 'at':
            found = [entry for entry in everyone if at_part(entry, named)]
        elif kind == 'file':
            named = project_path(store, named)
            found = [entry for entry in everyone if in_file(entry, named)]
        else:
            found = [entry for entry in everyone if on_topic(entry, named.lower().split())]
        others = [entry for entry in found if entry['work_id'] != mine]
        result: dict[str, Any] = {'peers': [{**shown(entry), **({'yours': True} if entry['work_id'] == mine else {})}
                                            for entry in found]}
        if others:
            call = 'dispatch_note' if ctx.surface == 'mcp' else 'metaform dispatch note'
            result['ready'] = f'{call} {kind}={named} wait=60 -- "I am about to change {named}; is there anything I ' \
                              'should know first?"'
            result['said'] = (f'{len(others)} other agents are at work with {kind}={named}: '
                              + ', '.join(f'{entry["agent"]} on {entry["item"]}' for entry in others)
                              + '. Ask them before you change it; `ready` is the note.')
        else:
            result['said'] = f'No other agent is at work with {kind}={named} now.'
        return result
    return {'peers': [{**shown(entry), **({'yours': True} if entry['work_id'] == mine else {})} for entry in found],
            'said': f'{len(found)} agents are at work on open tickets; send one a note with dispatch note to=, at=, '
                    'file= or topic=.'}
