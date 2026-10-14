"""A harness seat, BASE-066: Claude Code, Codex or another agent dispatch runs over ACP, on the person's own login to
it and never an API key, written `acp:<agent>/<model>`.

Each harness seat is one dispatch session for the life of its table, so it keeps its own conversation as every seat
does. The sessions hang on one held ticket per table, `Roundtable <N>` at the table's Address: held, so autostart never
starts it, and closed when the table ends. It is the smallest anchor dispatch's sessions take, since every dispatch
session belongs to a work record, and one per table keeps the board to one card however many harnesses sit. dispatch
starts a seat's session with `seat=`: no turn of its own, its model the one the seat names, a mode that only reads,
Claude Code's built-in tools cut to the ones that read and no MCP server but Metaform's, every write and terminal
refused, its permission requests answered at once and never put to the person, no API key in its environment, and no
agent slot taken. Each seat's session is its own: its row keeps the session's whole id, since two sessions of one agent
started at once share their first characters, and the model the agent reports the session runs, `reported`, so the
table's record says which model each seat really was.

On its turn a seat is sent, through dispatch's `message`, exactly the seat view the runner renders for every seat:
the opening and every turn before its own the first time, and after that only the turns since its last reply. Its
reply is the last text the agent wrote in that turn, read from the session's thread. A turn that takes longer than
roundtable_agent_wait is interrupted and passes with no submission; the session stays for the seat's next turn. A
session that ends takes the seat away from the table, and its turns are skipped.

dispatch is reached only through its verbs, never by import, and map's `work` makes and closes the held ticket.
"""
from __future__ import annotations

import re
import time
from collections.abc import Callable, Sequence
from typing import Any, cast

from metaform.data import Store
from metaform.module import Context, Stop

from . import store
from .chair import verb_call
from .render import LIMIT, said

POLL = 1.0  # seconds between looks at a seat's session while its turn runs
TASK = 'Roundtable {number}'  # the held ticket a table's harness seats hang on


def name(number: int, position: int) -> str:
    """The seat as its dispatch session's state names it, so the table finds its own session among the ticket's."""
    return f'roundtable:{number}:{position}'


# ----------------------------------------------------------------------------------------------- opening the table

def offered_models(ctx: Context, agent: str) -> list[dict[str, Any]]:
    """The models the agent offered at its last session in this project, as dispatch options lists them; none when
    it has not run here yet."""
    found: Any = verb_call(ctx, 'dispatch', 'options', {'agent': agent})
    read = cast(dict[str, Any], found) if isinstance(found, dict) else {}
    rows = cast(list[dict[str, Any]], read.get('agents') or [])
    for row in rows:
        for setting in cast(list[dict[str, Any]], row.get('settings') or []):
            if setting.get('key') == 'model':
                return cast(list[dict[str, Any]], setting.get('choices') or [])
    return []


def plain(text: str) -> str:
    return re.sub(r'[^a-z0-9]', '', text.lower())


def matches(given: str, value: str, label: str, way: int) -> bool:
    """Whether a model the agent offers, its value and its name, is the one given, in the `way`th sense: the value
    itself, its name, either with only letters and digits compared, or a full id ending with the name."""
    if way == 0:
        return value == given
    if way == 1:
        return label.casefold() == given.casefold()
    if way == 2:
        return plain(value) == plain(given) or plain(label) == plain(given)
    return bool(plain(label)) and plain(given).endswith(plain(label))


def resolve(given: str, choices: Sequence[dict[str, Any]]) -> str | None:
    """The model value an agent offers for a seat's model: the value itself, its name, or a full id that ends with the
    name, so claude-opus-5-5 is Claude Code's opus, named Opus 5.5; None when none or two match."""
    for way in range(4):
        found = [str(one['value']) for one in choices
                 if matches(given, str(one['value']), str(one.get('name') or ''), way)]
        if len(found) == 1:
            return found[0]
        if len(found) > 1:
            return None
    return None


def check(ctx: Context, chosen: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[str]]:
    """The seats with each harness seat's agent checked against dispatch's agents and its model resolved to the value
    its agent offers, each seat named once; and a notice for an agent that has not run in this project yet, whose
    model dispatch checks when the seat's session starts."""
    if not any(seat['kind'] == 'acp' for seat in chosen):
        return chosen, []
    listed: Any = verb_call(ctx, 'dispatch', 'agents', {})
    agents = {str(row['agent']): row for row in cast(list[dict[str, Any]], listed.get('agents') or [])}
    notices: list[str] = []
    seats: list[dict[str, str]] = []
    for seat in chosen:
        if seat['kind'] == 'acp':
            agent, model = seat['agent'], seat['model']
            row = agents.get(agent)
            if row is None:
                raise Stop(f'{seat["id"]}: {agent} is not an agent dispatch starts: {", ".join(agents)}.',
                           'metaform dispatch agents')
            if not row.get('available'):
                raise Stop(f'{seat["id"]}: the start command of {agent} is not found on this system.',
                           str(row.get('next') or 'metaform dispatch agents'))
            choices = offered_models(ctx, agent)
            if choices:
                value = resolve(model, choices)
                if value is None:
                    offered = ', '.join(f'{one["value"]} ({one.get("name")})' for one in choices)
                    raise Stop(f'{seat["id"]}: {row.get("label") or agent} offers no one model matching {model}; '
                               f'it offers {offered}.', f'metaform dispatch options agent={agent}')
                seat = {**seat, 'id': f'acp:{agent}/{value}', 'model': value}
            else:
                notices.append(f'{agent} has not run in this project yet, so the model {model} is checked when its '
                               f'seat\'s session starts: metaform dispatch options agent={agent} prime=true lists '
                               'what it offers.')
        if all(seat['id'] != held['id'] for held in seats):
            seats.append(seat)
    return seats, notices


# ----------------------------------------------------------------------------------------------- the table's ticket

def anchor(ctx: Context, held: Store, found: dict[str, Any]) -> str:
    """The held ticket the table's harness seats hang on, made the first time at the table's Address."""
    task = TASK.format(number=found['number'])
    if found.get('seat_work'):
        record = next((one for one in held.work(open=True, limit=0).results if one.id == found['seat_work']), None)
        if record is not None:  # one a map clear took away, or closed, is made again
            return record.id
    verb_call(ctx, 'map', 'work', {'op': 'add', 'node': found['address'], 'task': task, 'title': task,
                                   'note': 'Held for the harness seats of a roundtable; no agent works this ticket.',
                                   'held': True, 'hold': True})
    record = next((one for one in held.work(open=True, limit=0).results if one.task == task), None)
    if record is None:
        raise Stop(f'The held ticket of roundtable {found["number"]} was not made.', 'metaform map work')
    store.change(held, int(found['number']), seat_work=record.id)
    return record.id


def close(ctx: Context, held: Store, found: dict[str, Any]) -> None:
    """The table's held ticket closed, which also ends a seat session made after the table ended."""
    if not found.get('seat_work'):
        return
    try:
        if not held.ticket(str(found['seat_work'])).work.done:
            verb_call(ctx, 'map', 'work', {'op': 'done', 'id': found['seat_work'],
                                           'resolution': f'Roundtable {found["number"]} ended.',
                                           'why': 'The table ended, and its harness seats with it.'})
    except Exception as error:  # noqa: BLE001  the table ends whether or not its ticket closes
        raise Stop(f'The held ticket of roundtable {found["number"]} was not closed: {error}',
                   f'metaform map work op=done id={found["seat_work"]}') from None


# ----------------------------------------------------------------------------------------------- the sessions

def sessions(ctx: Context, work: str, since: int | None = None) -> dict[str, Any]:
    """The sessions on the table's ticket with their states, and with `since`, their thread lines after it."""
    nouns: dict[str, Any] = {'id': work, 'thread': since is not None, **({'since': since} if since is not None else {})}
    found: Any = verb_call(ctx, 'dispatch', 'sessions', nouns)
    return cast(dict[str, Any], found) if isinstance(found, dict) else {}


def own(read: dict[str, Any], named: str) -> dict[str, Any] | None:
    """The latest session whose state names this seat."""
    states = cast(dict[str, dict[str, Any]], read.get('states') or {})
    rows = [row for row in cast(list[dict[str, Any]], read.get('sessions') or [])
            if states.get(str(row['session_id']), {}).get('seat') == named]
    return rows[-1] if rows else None


def reported(read: dict[str, Any], session: str) -> str | None:
    """The model the agent reports the session runs: the current value of its model setting, as the session's state
    keeps it; None when it names none."""
    state = cast(dict[str, dict[str, Any]], read.get('states') or {}).get(session) or {}
    for setting in cast(list[dict[str, Any]], state.get('settings') or []):
        if setting.get('id') == 'model' or setting.get('category') == 'model':
            return str(setting['current']) if setting.get('current') else None
    return None


def start(ctx: Context, held: Store, found: dict[str, Any]) -> None:
    """Every harness seat's session started at once, so each is ready by its first turn; a seat whose session runs
    already, or that has left the table, is left as it is."""
    seated = [seat for seat in store.seats(held, int(found['number'])) if seat['kind'] == 'acp' and not seat['gone']]
    if not seated:
        return
    work = anchor(ctx, held, found)
    read = sessions(ctx, work)
    for seat in seated:
        named = name(int(found['number']), int(seat['position']))
        row = own(read, named)
        if row is not None and row['state'] == 'running':
            continue
        if seat['session']:  # its conversation ended while no runner watched: it has left the table
            store.seat_change(held, int(found['number']), int(seat['position']),
                              gone=said('seat_gone', how=(row or {}).get('how') or 'its session ended'))
            continue
        verb_call(ctx, 'dispatch', 'seat', {'id': work, 'agent': seat['agent'], 'seat': named,
                                            'model': seat['model'] or ''})


def stop(ctx: Context, held: Store, found: dict[str, Any]) -> None:
    """The table has ended: its ticket closed first, so a seat's end raises no signal on it and a seat still starting
    ends as its session is made, then every seat's session stopped through dispatch's own stop. dispatch reads a
    session on a closed ticket as ended, so each is stopped by its id, and stop itself asks its runner. A ticket that
    does not close leaves the sessions to be stopped all the same, and is said after."""
    if not found.get('seat_work'):
        return
    unclosed: Stop | None = None
    try:
        close(ctx, held, found)
    except Stop as error:
        unclosed = error
    read = sessions(ctx, str(found['seat_work']))
    for seat in store.seats(held, int(found['number'])):
        if seat['kind'] != 'acp':
            continue
        row = own(read, name(int(found['number']), int(seat['position'])))
        for session in {one for one in (seat['session'], (row or {}).get('session_id')) if one}:
            try:
                verb_call(ctx, 'dispatch', 'stop', {'id': found['seat_work'], 'session': session})
            except Stop:  # it ended already
                pass
    if unclosed is not None:
        raise unclosed


Ending = Callable[[], bool]


class Gone(Exception):
    """The seat's session ended; the message says how."""


class Silent(Exception):
    """The seat's turn passed with no reply; the message says why."""


def session_of(ctx: Context, held: Store, found: dict[str, Any], seat: dict[str, Any], deadline: float,
               ending: Ending) -> dict[str, Any] | None:
    """The seat's running session, waited for until the deadline; None when the table ends first. Gone when it ended
    or did not start in time."""
    work = anchor(ctx, held, found)
    named = name(int(found['number']), int(seat['position']))
    while True:
        read = sessions(ctx, work)
        row = own(read, named)
        if row is not None and row['state'] == 'running':
            model = reported(read, str(row['session_id']))
            changes = {**({'session': row['session_id']} if seat['session'] != row['session_id'] else {}),
                       **({'reported': model} if model and model != seat.get('reported') else {})}
            if changes:
                store.seat_change(held, int(found['number']), int(seat['position']), **changes)
            return row
        if row is not None:
            raise Gone(said('seat_gone', how=row.get('how') or 'its session ended'))
        if ending():
            return None
        if time.time() > deadline:
            raise Gone(said('seat_gone', how='its session did not start in time'))
        time.sleep(POLL)


def exchange(ctx: Context, held: Store, found: dict[str, Any], seat: dict[str, Any], row: dict[str, Any],
             text: str, deadline: float, ending: Ending) -> str | None:
    """One prompt of the seat's session and the last text the agent wrote in that turn; None when the table ends
    first, its turn then interrupted. Silent when the turn runs past the deadline or says nothing, Gone when the
    session ends."""
    work, session = str(found['seat_work']), str(row['session_id'])
    lines = cast(list[dict[str, Any]], sessions(ctx, work, int(seat['cursor'] or 0)).get('lines') or [])
    base = max([int(one['seq']) for one in lines if one['session_id'] == session] + [int(seat['cursor'] or 0)])
    try:
        verb_call(ctx, 'dispatch', 'message', {'id': work, 'session': session, 'text': [text]})
    except Stop as error:
        raise Gone(said('seat_gone', how=str(error))) from None
    while True:
        read = sessions(ctx, work)
        now = own(read, name(int(found['number']), int(seat['position'])))
        if now is None or now['state'] != 'running':
            raise Gone(said('seat_gone', how=(now or {}).get('how') or 'its session ended'))
        if now.get('activity') == 'idle':
            break
        if ending() or time.time() > deadline:
            try:
                verb_call(ctx, 'dispatch', 'interrupt', {'id': work, 'session': session})
            except Stop:
                pass
            if ending():
                return None
            raise Silent(said('no_reply_time', seconds=int(ctx.setting('roundtable_agent_wait'))))
        time.sleep(POLL)
    lines = [one for one in cast(list[dict[str, Any]], sessions(ctx, work, base).get('lines') or [])
             if one['session_id'] == session]
    model = reported(read, session)  # the model the turn ran on, as the agent reports it
    store.seat_change(held, int(found['number']), int(seat['position']),
                      cursor=max([int(one['seq']) for one in lines] + [base]), **({'reported': model} if model else {}))
    said_last = [str(one['text']).strip() for one in lines if one['kind'] == 'agent_message_chunk'
                 and str(one['text']).strip()]
    if not said_last:
        raise Silent(said('no_reply_harness', error='it wrote no text'))
    return said_last[-1]


def speak(ctx: Context, held: Store, found: dict[str, Any], seat: dict[str, Any], view: str, latest: int,
          ending: Ending) -> tuple[str | None, bool, str] | None:
    """A harness seat's turn in its own session: the seat view, told once when it runs over the limit and given one
    retry. None when the table ends first. A seat whose session ended leaves the table."""
    seconds = int(ctx.setting('roundtable_agent_wait'))
    number, position = int(found['number']), int(seat['position'])
    messages: list[dict[str, str]] = [*seat['messages'], {'role': 'user', 'content': view}]
    try:
        row = session_of(ctx, held, found, seat, time.time() + seconds, ending)
        if row is None:
            return None
        found = store.discussion(held, number)  # with its ticket
        reply = exchange(ctx, held, found, seat, row, view, time.time() + seconds, ending)
        if reply is None:
            return None
        messages.append({'role': 'assistant', 'content': reply})
        over = len(reply) > LIMIT
        if over:
            retry = said('over_limit', length=len(reply), limit=LIMIT)
            messages.append({'role': 'user', 'content': retry})
            seat = store.seats(held, number)[position]
            try:
                again = exchange(ctx, held, found, seat, row, retry, time.time() + seconds, ending)
            except Silent:  # no second reply: the first stands, over the limit
                again = reply
            if again is None:
                return None
            if again is not reply:
                messages.append({'role': 'assistant', 'content': again})
            reply, over = again, len(again) > LIMIT
    except Gone as error:
        store.seat_change(held, number, position, gone=str(error), messages=messages, seen=latest)
        return None, False, str(error)
    except Silent as error:  # the session was given the view, so its next turn carries only what follows
        store.seat_change(held, number, position, messages=messages, seen=latest)
        return None, False, str(error)
    store.seat_change(held, number, position, messages=messages, seen=latest)
    return reply, over, ''
