"""The A2A peers the person names, MCP-040: the only agents Metaform sends work to, records of the person's own.

Each peer is a short name, its Agent Card's URL and the environment variable that holds the bearer token it takes,
read when a message is sent and never stored. They are kept for the whole home in `<home>/mcp/a2a-peers.json`, as the
global setting they were, and changed only by the person: `mcp a2a_peer_add` and `mcp a2a_peer_remove` run on the
command line and never from an agent's session; `mcp a2a_peers` lists them. Settings cleanup 2026-10-15 (ticket
0d9e3882) made them records: as one list setting, setting a peer replaced every other. The mcp module's start carries
a stored `mcp_a2a_peers` list over once per home, `carry`, and removes its rows; a read never writes.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

from metaform import home, settings
from metaform.module import Context, Stop

NAME = re.compile(r'^[a-z0-9][a-z0-9_-]*$')
VARIABLE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
ADD = 'metaform mcp a2a_peer_add <name> <card URL> [token=<token variable>]'


@dataclass(frozen=True)
class Peer:
    """A peer the person names: its short name, its Agent Card's URL and the variable that holds its token."""
    name: str
    url: str
    token_env: str | None

    @property
    def token(self) -> str | None:
        return os.environ.get(self.token_env) or None if self.token_env else None


def made(name: str, url: str, variable: str | None) -> Peer:
    """A peer checked as the person gives it; refused, with the form, when a part cannot be read."""
    name, url, variable = name.strip(), url.strip(), (variable or '').strip()
    if not NAME.fullmatch(name) or not url.startswith(('http://', 'https://')) or ' ' in url \
            or (variable and not VARIABLE.fullmatch(variable)):
        raise Stop(f'A peer is a name of lowercase letters, digits, _ and -, an http or https card URL and, if it '
                   f'takes a token, the environment variable that holds it; not {name} {url} {variable}.'.rstrip(),
                   ADD)
    return Peer(name, url, variable or None)


def _file() -> Path:
    return home.home() / 'mcp' / 'a2a-peers.json'


def _lock() -> Path:
    home.mkdir_private(_file().parent)
    return _file().parent / 'a2a-peers.lock'


def _read() -> list[Peer]:
    try:
        kept: Any = json.loads(_file().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    rows = [cast(dict[str, Any], one) for one in cast(list[Any], kept if isinstance(kept, list) else [])
            if isinstance(one, dict)]
    return [Peer(str(one.get('name')), str(one.get('url')), one.get('token_env') or None) for one in rows]


def _write(found: list[Peer]) -> None:
    home.write_private(_file(), json.dumps([asdict(one) for one in sorted(found, key=lambda one: one.name)], indent=1))


def carry(ctx: Any = None) -> list[str]:
    """Once per home, as the mcp module starts: each entry of a stored mcp_a2a_peers list, `<name>=<card URL> <token
    variable>`, becomes a peer, over none of that name already kept; one that cannot be read is left out and said. The
    list's rows are removed. Marked `carried:mcp-a2a-peers` in the home's meta."""
    del ctx
    return settings.carry_once('mcp-a2a-peers', _carry)


def _carry() -> list[str]:
    said: list[str] = []
    found: dict[str, Peer] = {}
    for entry in home.stored('global', 'mcp', 'mcp_a2a_peers') or []:
        name, _, rest = str(entry).partition('=')
        url, _, variable = rest.strip().partition(' ')
        try:
            found[name.strip()] = made(name, url, variable)
            said.append(f'peer {name.strip()}')
        except Stop:
            said.append(f'{entry!r} cannot be read as a peer and was left out')
    if found:
        with home.file_lock(_lock()):
            kept = {one.name: one for one in _read()}
            _write([*found.values(), *(one for name, one in kept.items() if name not in found)])
    home.clear('global', 'mcp', 'mcp_a2a_peers')
    home.set_glue('global', 'mcp', 'mcp_a2a_peers', False)
    return said


def listed() -> list[Peer]:
    """Every peer, by name."""
    return _read()


def peers(folder: Path | None = None) -> dict[str, Peer]:
    del folder  # the peers are the home's, whatever folder asks
    return {one.name: one for one in listed()}


def peer(folder: Path, name: str) -> Peer:
    """A peer on the person's list, or a refusal that lists them: Metaform sends to no other, MCP-040."""
    known = peers(folder)
    if name not in known:
        named = ', '.join(sorted(known)) or 'none yet'
        raise Stop(f'{name} is not one of the A2A peers the person names ({named}).',
                   f'ask the person to add it: {ADD}')
    return known[name]


def _shown(one: Peer) -> dict[str, Any]:
    return {'name': one.name, 'url': one.url, 'token_env': one.token_env,
            'token_set': None if one.token_env is None else one.token is not None}


def add(ctx: Context) -> dict[str, Any]:
    """Add a peer, or replace the one of that name; the others are left as they are."""
    given = made(str(ctx.nouns['name']), str(ctx.nouns['url']), str(ctx.nouns.get('token') or ''))
    with home.file_lock(_lock()):
        kept = [one for one in _read() if one.name != given.name]
        _write([*kept, given])
    said = _shown(given)
    if given.token_env and given.token is None:
        said['notice'] = f'{given.token_env} is not set here; a send to {given.name} needs it where it runs.'
    return said


def remove(ctx: Context) -> dict[str, Any]:
    """Remove a peer by name; Metaform then sends it nothing."""
    name = str(ctx.nouns['name'])
    with home.file_lock(_lock()):
        kept = _read()
        if name not in {one.name for one in kept}:
            raise Stop(f'No A2A peer {name}.', 'metaform mcp a2a_peers')
        _write([one for one in kept if one.name != name])
    return {'removed': name}


def show(ctx: Context) -> dict[str, Any]:
    """The peers, each with whether its token variable is set where this runs."""
    del ctx
    return {'peers': [_shown(one) for one in listed()]}
