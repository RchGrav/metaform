"""How each person's page looks right now: kept for the person, never as configuration.

Settings cleanup, 2026-10-15 (ticket 0d9e3882): fourteen keys the page wrote as global settings on a key press or a
View-menu click, the signs, the lens, the flow, the depth, the 2D map's direction, what the pointer shows, node zoom,
the agents window, the physics, and the toolbar, panes and workspaces, are view state. They are kept here, per account
behind a Node's gate and the owner's otherwise, as hints.py keeps hints; they leave `set`, `config --show`, the
settings screens and the agents' set list. An account reads the owner's view under its own, so a member opens the page
as the owner left it until they change it. The web module's start carries the values stored in the old settings
over once per home, `carry`, then removes those rows, so nobody's view changes; a read never writes.

`GET /api/view` answers `{view: {key: value}}`; `POST /api/view` with `{key, value}` keeps one, checked, and answers the
same. Any account keeps its own, so the route is a read for its class.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from metaform import home, settings

if TYPE_CHECKING:
    from .server import Handler

VIEW = '/api/view'
OWNER = ''  # the home's owner, and every page without a Node's gate


def _choice(*names: str) -> Callable[[Any], bool]:
    return lambda value: value in names


def _depth(value: Any) -> bool:
    """A number of levels, as many as the map has, or all."""
    return value == 'all' or isinstance(value, str) and value.isdigit() and 0 < int(value) < 1000


def _boolean(value: Any) -> bool:
    return isinstance(value, bool)


def _text(value: Any) -> bool:
    return isinstance(value, str)


# Each key, its default and what it takes. The toolbar, the layout and the workspaces are the JSON text workspace.py
# checks against its shapes; web_workspace is the name of the one in use.
KEYS: dict[str, tuple[Any, Callable[[Any], bool]]] = {
    'web_signs': ('facing', _choice('outward', 'facing')),
    'web_lens': ('natural', _choice('natural', 'wide', 'fisheye')),
    'web_flow_mode': ('selected', _choice('off', 'hover', 'selected', 'all', 'live')),
    'web_map_depth': ('all', _depth),
    'web_flow_edges': (True, _boolean),
    'web_map_direction': ('auto', _choice('auto', 'across', 'down')),
    'web_hover_info': ('name+summary', _choice('name+summary', 'name', 'summary', 'off')),
    'web_node_zoom': (True, _boolean),
    'web_agents_window': ('auto', _choice('auto', 'open', 'hidden')),
    'web_physics': ('organic', _choice('organic', 'flat')),
    'web_toolbar': ('', _text),
    'web_layout': ('', _text),
    'web_workspaces': ('', _text),
    'web_workspace': ('Default', _text),
}


class ViewError(ValueError):
    """A key that is not view state, or a value it does not take."""


def account(handler: Handler) -> str:
    """Whose view this is: the signed-in account behind a Node's gate, else the home's owner."""
    from .server import ACCOUNT_HEADER
    return (handler.headers.get(ACCOUNT_HEADER) or OWNER) if handler.gui.gate is not None else OWNER


def _file() -> Path:
    return home.home() / 'web' / 'view.json'


def _lock() -> Path:
    home.mkdir_private(_file().parent)
    return _file().parent / 'view.lock'


def _read() -> dict[str, dict[str, Any]]:
    try:
        kept: Any = json.loads(_file().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    if not isinstance(kept, dict):
        return {}
    return {str(who): {str(key): value for key, value in cast(dict[Any, Any], mine).items() if key in KEYS}
            for who, mine in cast(dict[Any, Any], kept).items() if isinstance(mine, dict)}


def _write(kept: dict[str, dict[str, Any]]) -> None:
    home.write_private(_file(), json.dumps(kept, indent=1, sort_keys=True))


def carry(ctx: Any = None) -> list[str]:
    """Once per home, as the web module starts: each value stored in the old global settings goes into the owner's
    view, over nothing the owner already keeps, and its row is removed; a value the key no longer takes is left out, so
    the page opens at that key's default. Marked `carried:web-view-state` in the home's meta."""
    del ctx
    return settings.carry_once('web-view-state', _carry)


def _carry() -> list[str]:
    said: list[str] = []
    found: dict[str, Any] = {}
    for key, (_, takes) in KEYS.items():
        stored = home.stored('global', 'web', key)
        if stored is None and not home.glued('global', 'web', key):
            continue
        if stored and takes(stored[0]):
            found[key] = stored[0]
            said.append(f'{key} = {stored[0]!r}')
        home.clear('global', 'web', key)
        home.set_glue('global', 'web', key, False)
    if found:
        with home.file_lock(_lock()):
            kept = _read()
            kept[OWNER] = {**found, **kept.get(OWNER, {})}
            _write(kept)
    return said


def values(who: str = OWNER) -> dict[str, Any]:
    """An account's view: each key's default, under the owner's, under its own."""
    kept = _read()
    return {**{key: default for key, (default, _) in KEYS.items()}, **kept.get(OWNER, {}), **kept.get(who, {})}


def value(key: str, who: str = OWNER) -> Any:
    return values(who)[key]


def keep(who: str, key: str, given: Any) -> dict[str, Any]:
    """Keep one key of an account's view, or return it to the default with None; raises ViewError for a key that is
    not view state or a value it does not take."""
    if key not in KEYS:
        raise ViewError(f'{key} is not part of the page\'s view.')
    if given is not None and not KEYS[key][1](given):
        raise ViewError(f'{key} does not take {given!r}.')
    with home.file_lock(_lock()):
        kept = _read()
        mine = kept.setdefault(who, {})
        if given is None:
            mine.pop(key, None)
        else:
            mine[key] = given
        _write(kept)
    return values(who)


def answer(handler: Handler, method: str) -> None:
    """Answer one request to /api/view. The server has checked its Host, token and class."""
    who = account(handler)
    if method != 'POST':
        return handler.send(200, {'view': values(who)})
    if not handler.same_origin():
        return handler.send(403, {'error': "A write is taken only from the web GUI's own page."})
    if (handler.headers.get('Content-Type') or '').split(';')[0].strip().lower() != 'application/json':
        return handler.send(415, {'error': 'A write takes a JSON body.'})
    try:
        body: Any = handler.json_body()
    except ValueError:
        return handler.send(400, {'error': 'The body is not JSON.'})
    given = cast(dict[str, Any], body) if isinstance(body, dict) else {}
    try:
        kept = keep(who, str(given.get('key') or ''), given.get('value'))
    except ViewError as error:
        return handler.send(400, {'error': str(error), 'next': f'GET {VIEW} lists the view and its values'})
    handler.send(200, {'view': kept})
