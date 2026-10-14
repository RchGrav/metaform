"""The table as a place, BASE-066: where each seat sits, which way it faces, and what it sees from its own eyes.

The seats sit in speaking order round a round table, the first nearest the person's view and the rest clockwise as
the person sees it from above, with a plant in the middle. Each figure stays at its chair; it only turns about its
own vertical axis. A facing is a bearing in degrees, clockwise from the far side of the table as the person sees it,
so turning by a positive number of degrees turns a figure to its right. A seat that has not turned faces the middle
of the table.

This module is the one source of the scene's numbers: the state it builds carries every seat's place and facing to
the scene module in `resources/scene/`, which draws it, and the same numbers give the list of what a seat sees, so a
model that cannot see pictures acts on what the picture shows.
"""
from __future__ import annotations

import math
import time
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from . import store
from .names import harness_of
from .render import said

FIGURE_GAP = 2.1  # the distance between neighbours round the table, in figure sizes of 1.6
SEAT_Y = 1.35  # the height of a figure's middle above the floor
TABLE_Y = 0.8  # the height of the table's top
PLANT_TOP = 1.0  # the height of the plant's leaves: below the seats' eyes, so they see each other across it
EYE_FOV = 60.0  # the eye camera's vertical field of view, degrees
EYE_ASPECT = 4 / 3  # the eye picture's width over its height
EYE_SIZE = (640, 480)  # the eye picture, in pixels
BUBBLE = 5.0  # seconds a seat's kept answer shows in a bubble over its head
AHEAD = 10.0  # degrees either side of straight ahead that count as in front


def half_view() -> float:
    """Half the eye camera's horizontal field of view, in degrees."""
    return math.degrees(math.atan(math.tan(math.radians(EYE_FOV / 2)) * EYE_ASPECT))


def wrap(degrees: float) -> float:
    """An angle as -180 to 180, positive to the right."""
    found = (degrees + 180.0) % 360.0 - 180.0
    return 180.0 if found == -180.0 else found


def bearing(degrees: float) -> float:
    """An angle as a bearing, 0 up to but never 360."""
    found = round(degrees % 360.0, 6)
    return 0.0 if found >= 360.0 else found


def ring(count: int) -> float:
    """The radius the seats sit at."""
    return max(3.6, count * FIGURE_GAP / (2 * math.pi))  # a few seats still sit at a full table


def table_radius(count: int) -> float:
    return ring(count) - 0.6  # the table comes out to the seats, so it fills the scene rather than sitting small


def place(position: int, count: int) -> tuple[float, float, float]:
    """A seat's place: its x and z on the floor and its bearing from the middle of the table."""
    around = (180.0 + position * 360.0 / max(count, 1)) % 360.0
    radius = ring(count)
    return radius * math.sin(math.radians(around)), -radius * math.cos(math.radians(around)), around


def home(position: int, count: int) -> float:
    """The facing of a seat that has not turned: toward the middle of the table."""
    return bearing(place(position, count)[2] + 180.0)


def facing(seat: Mapping[str, Any], count: int) -> float:
    given = seat.get('facing')
    return bearing(float(given)) if given is not None else home(int(seat['position']), count)


def bearing_to(at: tuple[float, float], to: tuple[float, float]) -> float:
    """The bearing from one point on the floor to another."""
    return bearing(math.degrees(math.atan2(to[0] - at[0], -(to[1] - at[1]))))


def things(seats: Sequence[Mapping[str, Any]]) -> list[tuple[str, tuple[float, float]]]:
    """Every seat by its name with its place on the floor, and the plant."""
    count = len(seats)
    found = [(str(seat['name']), place(int(seat['position']), count)[:2]) for seat in seats]
    return [*found, (said('scene_plant'), (0.0, 0.0))]


def side(relative: float) -> str:
    """Where something is from a seat, in words."""
    turned = abs(relative)
    if turned <= AHEAD:
        return said('side_ahead')
    if turned >= 150:
        return said('side_behind')
    right = relative > 0
    if turned <= half_view():
        return said('side_ahead_right') if right else said('side_ahead_left')
    return said('side_right') if right else said('side_left')


def view(seats: Sequence[Mapping[str, Any]], position: int) -> dict[str, Any]:
    """What a seat sees: its facing, in degrees from its home facing, positive to its right, and in words who is in
    front of it; then everything in its view, nearest the middle of the view first, each with its bearing from
    straight ahead, positive to the right, and its distance."""
    count = len(seats)
    seat = seats[position]
    x, z, _ = place(position, count)
    heading = facing(seat, count)
    seen: list[dict[str, Any]] = []
    around: list[dict[str, Any]] = []
    for name, at in things(seats):
        if name == seat['name']:
            continue
        relative = wrap(bearing_to((x, z), at) - heading)
        entry = {'name': name, 'bearing': round(relative), 'distance': round(math.dist((x, z), at), 1),
                 'where': side(relative)}
        around.append(entry)
        if abs(relative) <= half_view():
            seen.append(entry)
    seen.sort(key=lambda one: (abs(float(one['bearing'])), float(one['distance'])))
    around.sort(key=lambda one: float(one['bearing']) % 360)
    front = [one for one in seen if abs(float(one['bearing'])) <= AHEAD]
    if front:
        words = said('facing_front', names=', '.join(str(one['name']) for one in front))
    elif seen:
        words = said('facing_near', seat=seen[0]['name'], where=seen[0]['where'])
    else:
        words = said('facing_away')
    return {'facing': round(wrap(heading - home(position, count))), 'in_front': words, 'in_view': seen,
            'around': around}


def find(seats: Sequence[Mapping[str, Any]], name: str) -> tuple[str, tuple[float, float]] | None:
    """A seat, or the plant, by its name, any case."""
    wanted = ' '.join(name.split()).casefold()
    return next(((named, at) for named, at in things(seats) if named.casefold() == wanted), None)


def age(stamp: str | None) -> float:
    if not stamp:
        return math.inf
    try:
        return time.time() - datetime.fromisoformat(stamp).timestamp()
    except ValueError:
        return math.inf


def state(held: Any, number: int) -> dict[str, Any]:
    """The table as the scene draws it: its phase, every seat's place, facing, name and ring, its hand when raised,
    and its kept answer in a bubble while it is new."""
    found = store.discussion(held, number)
    seats = store.seats(held, number)
    count = len(seats)
    latest: dict[int, dict[str, Any]] = {}
    for row in store.submissions(held, number):
        if row['position'] is not None and row['kind'] == 'seat':
            latest[int(row['position'])] = row
    turn = int(found['position']) if found['state'] in ('running', 'held') else None
    exploring = not found.get('explored') and float(found.get('explore_until') or 0) > time.time()
    drawn: list[dict[str, Any]] = []
    for seat in seats:
        position = int(seat['position'])
        x, z, _ = place(position, count)
        said_last = latest.get(position)
        bubble = (str(said_last['text']) if said_last is not None and said_last['accepted']
                  and age(str(said_last['created'])) < BUBBLE else None)
        drawn.append({'position': position, 'name': seat['name'], 'id': seat['id'], 'kind': seat['kind'],
                      'harness': harness_of(seat), 'x': round(x, 4), 'z': round(z, 4),
                      # a raised hand, drawn by the scene module's hand; nothing raises one yet
                      'facing': round(facing(seat, count), 2), 'hand': bool(seat.get('hand')),
                      'gone': bool(seat.get('gone')), 'speaking': position == turn and not exploring,
                      'bubble': bubble})
    return {'discussion': number, 'address': found['address'], 'subject': found['subject'], 'state': found['state'],
            'phase': 'explore' if exploring else found['state'], 'round': found['round'],
            'explore_left': max(0, round(float(found.get('explore_until') or 0) - time.time())) if exploring else 0,
            'table': {'radius': round(table_radius(count), 4), 'top': TABLE_Y, 'ring': round(ring(count), 4),
                      'seat_y': SEAT_Y, 'plant_top': PLANT_TOP},
            'eye': {'fov': EYE_FOV, 'width': EYE_SIZE[0], 'height': EYE_SIZE[1]},
            'bubble_seconds': BUBBLE, 'seats': drawn}
