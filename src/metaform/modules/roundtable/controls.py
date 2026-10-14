"""A seat's controls at its table, BASE-066: turn in place, look straight ahead, look at another seat.

Every seat has them. A harness seat calls them as tools of Metaform's MCP server in its own dispatch session,
`roundtable_rotate`, `roundtable_look` and `roundtable_look-at`; an agent seat calls the same verbs naming its table
and seat; a model seat through OpenRouter calls them as tools in its turn's tool loop, `toolloop`. A figure never
leaves its chair: a turn only changes its facing, and `look-at` turns it toward the seat named, visibly in the scene.
A look returns the picture from the seat's own eyes, drawn by the table's runner, with what is in view as a list, so
a model that cannot see pictures acts on the same thing.

A control acts only for the caller's own seat. A harness seat is known by its session: the dispatch session whose
runner id is the caller's METAFORM_SESSION, running on the caller's METAFORM_WORK, which must be its table's held
ticket, and whose state names it `roundtable:<table>:<position>`. An agent seat names its table and seat, and the agent
session that answers for that seat is the only one let through, MCP-042. Every other caller is refused. Like every
role check in Metaform this guards against an agent's mistakes, not an agent set on getting round it.

The controls are declared `read`: they write nothing in the project or the map, only the seat's own facing at its
table, and a seat's session serves only the tools that read.
"""
from __future__ import annotations

import base64
import os
import re
import secrets
from collections.abc import Callable
from typing import Any, cast

from metaform import home
from metaform.data import Store
from metaform.module import Context, Status, Stop

from . import harness, scene, stage, store
from .render import said

Picture = Callable[[int], str]  # a seat's eye view, base64 PNG; stage.Unseen when none is drawn


# ----------------------------------------------------------------------------------------------- the controls

def seat_name(held: Store, number: int, position: int) -> str:
    return str(store.seats(held, number)[position]['name'])


def rotate(held: Store, number: int, position: int, degrees: float | None = None,
           to: float | None = None) -> dict[str, Any]:
    """Turn the seat in place: by `degrees`, positive to its right, or `to` a facing in degrees from its home facing
    toward the middle of the table. Its new facing, and who is in front of it now."""
    seats = store.seats(held, number)
    count = len(seats)
    if to is not None:
        facing = scene.home(position, count) + float(to)
    else:
        facing = scene.facing(seats[position], count) + float(degrees or 0)
    seats[position]['facing'] = scene.bearing(facing)
    store.seat_change(held, number, position, facing=scene.bearing(facing))
    seen = scene.view(seats, position)
    return {'seat': seats[position]['name'], 'facing': seen['facing'], 'in_front': seen['in_front']}


def look(held: Store, number: int, position: int, picture: Picture) -> dict[str, Any]:
    """What the seat sees straight ahead: the picture from its own eyes as `png`, and the list of what is in view."""
    seats = store.seats(held, number)
    seen = scene.view(seats, position)
    found: dict[str, Any] = {'seat': seats[position]['name'], 'facing': seen['facing'], 'in_front': seen['in_front'],
                             'in_view': seen['in_view']}
    try:
        found['png'] = picture(position)
    except stage.Unseen as error:
        found['no_picture'] = str(error)
    return found


def look_at(held: Store, number: int, position: int, name: str, picture: Picture) -> dict[str, Any]:
    """Turn the seat toward the seat named, or the plant, and look."""
    seats = store.seats(held, number)
    found = scene.find(seats, name)
    own = seats[position]['name']
    if found is None:
        others = ', '.join(str(seat['name']) for seat in seats if seat['name'] != own)
        raise Stop(f'No one at this table is named {name}: the seats are {others}, and there is the plant.',
                   'look at one of them by name')
    if found[0] == own:
        raise Stop(f'{own} is your own name; look at another seat.', 'look at another seat by name')
    x, z, _ = scene.place(position, len(seats))
    facing = scene.bearing_to((x, z), found[1])
    store.seat_change(held, number, position, facing=facing)
    return look(held, number, position, picture)


# ----------------------------------------------------------------------------------------------- whose seat

def harness_seat(ctx: Context) -> tuple[int, int] | None:
    """The table and position of the harness seat this call comes from, by its dispatch session; None when the call
    is not a seat's."""
    if os.environ.get('METAFORM_ROLE') != 'seat':
        return None
    runner, work = os.environ.get('METAFORM_SESSION'), os.environ.get('METAFORM_WORK')
    if not runner or not work:
        return None
    try:
        read = harness.sessions(ctx, work)
    except Stop:
        return None
    rows = cast(list[dict[str, Any]], read.get('sessions') or [])
    row = next((one for one in rows if one.get('runner') == runner and one.get('state') == 'running'), None)
    if row is None:
        return None
    states = cast(dict[str, dict[str, Any]], read.get('states') or {})
    named = re.fullmatch(r'roundtable:(\d+):(\d+)', str(states.get(str(row['session_id']), {}).get('seat') or ''))
    if named is None:
        return None
    number, position = int(named.group(1)), int(named.group(2))
    found = store.discussion(ctx.require_store(), number)
    return (number, position) if found.get('seat_work') == work else None


def agent_seat(ctx: Context) -> tuple[int, int] | None:
    """The table and position of the agent seat the call names, when the caller answers for it."""
    if ctx.nouns.get('discussion') in (None, '') or not ctx.nouns.get('seat'):
        return None
    number = int(ctx.nouns['discussion'])
    named = str(ctx.nouns['seat']).strip()
    seat = next((one for one in store.seats(ctx.require_store(), number)
                 if one['id'] == named and one['kind'] == 'agent'), None)
    if seat is None:
        return None
    if seat['session'] and ctx.session != seat['session']:  # MCP-042: one agent answers for a seat
        return None
    return number, int(seat['position'])


def caller(ctx: Context, what: str) -> tuple[Store, int, int]:
    """The store, table and position of the caller's own seat; every other caller refused, naming `what` it tried."""
    found = harness_seat(ctx) or agent_seat(ctx)
    if found is None:
        raise Stop(f'Only a seat at a roundtable can {what}, and only for itself: this call comes from no seat.',
                   'metaform roundtable list')
    number, position = found
    given = ctx.nouns.get('discussion')
    if given not in (None, '') and int(given) != number:
        raise Stop(f'This seat sits at roundtable {number}, not {given}.', f'metaform roundtable status {number}')
    held = store.own(ctx.require_store())
    table = store.discussion(held, number)
    if table['state'] == 'ended':
        raise Stop(f'Roundtable {number} has ended.', f'metaform roundtable status {number}')
    if store.seats(held, number)[position]['gone']:
        raise Stop(f'This seat has left roundtable {number}.', f'metaform roundtable status {number}')
    return held, number, position


def connect(ctx: Context) -> Status:
    """What a harness seat's own server tells it as it connects: which seat it is, at which table, who sits there and
    what its controls are, so its time to explore finds them. Nothing for any other caller. The seat is named by
    METAFORM_SEAT, which dispatch gives a seat's server, on its table's held ticket."""
    named = re.fullmatch(r'roundtable:(\d+):(\d+)', os.environ.get('METAFORM_SEAT') or '')
    if named is None or os.environ.get('METAFORM_ROLE') != 'seat' or ctx.store is None:
        return Status()
    number, position = int(named.group(1)), int(named.group(2))
    try:
        found = store.discussion(ctx.store, number)
        seats = store.seats(ctx.store, number)
    except Stop:
        return Status()
    if found.get('seat_work') != os.environ.get('METAFORM_WORK') or position >= len(seats):
        return Status()
    others = ', '.join(str(seat['name']) for seat in seats if int(seat['position']) != position)
    return Status(instruction=said('seat_connect', discussion=number, seat=seats[position]['name'], others=others))


def remote_picture(held: Store, number: int) -> Picture:
    """A seat's eye view drawn by its table's runner, reached over the loopback."""
    return lambda position: stage.fetch_look(store.discussion(held, number).get('scene'), position)


def pictured(ctx: Context, found: dict[str, Any]) -> dict[str, Any]:
    """The picture as the tool's image over MCP, so it reaches the seat as image content; elsewhere saved under the
    home and its path given."""
    picture = str(found.pop('png', '') or '')
    if picture and ctx.surface == 'mcp':
        found['image'] = {'data': picture, 'mimeType': 'image/png'}
    elif picture:
        saved = home.home() / 'run' / 'looks' / f'roundtable-{secrets.token_hex(4)}.png'
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_bytes(base64.b64decode(picture))
        found['file'] = str(saved)
    return found


# ----------------------------------------------------------------------------------------------- the verbs

def rotate_verb(ctx: Context) -> dict[str, Any]:
    """Turn your figure in place, by degrees (positive to your right), or to a facing from your home facing."""
    held, number, position = caller(ctx, 'turn')
    degrees, to = ctx.nouns.get('degrees'), ctx.nouns.get('to')
    if degrees in (None, '') and to in (None, ''):
        raise Stop('Say how far to turn: degrees=<degrees>, positive to your right, or to=<degrees> from facing the '
                   'table.', 'metaform roundtable rotate degrees=90')
    return rotate(held, number, position, None if degrees in (None, '') else float(degrees),
                  None if to in (None, '') else float(to))


def look_verb(ctx: Context) -> dict[str, Any]:
    """See straight ahead from your own eyes."""
    held, number, position = caller(ctx, 'look')
    return pictured(ctx, look(held, number, position, remote_picture(held, number)))


def look_at_verb(ctx: Context) -> dict[str, Any]:
    """Turn to face a seat by its name, and look."""
    held, number, position = caller(ctx, 'look at a seat')
    return pictured(ctx, look_at(held, number, position, str(ctx.nouns.get('name') or ''),
                                 remote_picture(held, number)))
