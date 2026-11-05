"""Persistent participant aliases, with provider and model identifiers kept in their private profile mapping."""
from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, TypedDict, cast

from metaform.data import DataConnection
from metaform.module import Stop, provided


class Assigned(TypedDict):
    identity: str | None
    name: str
    profile_key: str


def source(seat: Mapping[str, Any]) -> str:
    """The existing private profile key, retained so earlier aggregate scores are not lost or split."""
    return f'{seat.get("agent") or seat.get("kind")}/{seat.get("model") or seat.get("id")}'


def _generator(folder: Path) -> Callable[[str], object]:
    found = provided(folder, 'agent.name')
    if not found:
        raise Stop('Roundtable participants need the shared agent naming service.', 'metaform enable dispatch')
    if len(found) != 1 or not callable(found[0][1]):
        raise Stop('Roundtables need one agent.name provider.', 'enable one shared agent naming service')
    return cast(Callable[[str], object], found[0][1])


def _fresh(make: Callable[[str], object], taken: set[str]) -> tuple[str, str]:
    # The existing generator has a finite word space. Retry collisions without exposing a model-derived label.
    for _ in range(64):
        identity = uuid.uuid4().hex
        name = make(identity)
        if not isinstance(name, str) or not name.strip():
            raise Stop('The agent naming service returned no name.', 'check the agent.name provider')
        name = name.strip()
        if name.casefold() not in taken:
            return identity, name
    raise Stop('The agent naming service could not supply an unused name.', 'check the agent.name provider')


def assign(db: DataConnection, folder: Path | str, seats: Sequence[Mapping[str, Any]]) -> list[Assigned]:
    """Reuse each source's occurrence alias in the caller's transaction; the first keeps its legacy score key.

    Every new table uses dispatch's public generator, regardless of project registration. Existing aliases always
    win, including when their source is opened elsewhere later.
    """
    folder = Path(folder)
    taken = {str(row['name']).casefold() for row in db.execute('SELECT name FROM profile_aliases')}
    occurrences: dict[str, int] = {}
    make: Callable[[str], object] | None = None
    found: list[Assigned] = []
    for seat in seats:
        key = source(seat)
        occurrence = occurrences.get(key, 0)
        occurrences[key] = occurrence + 1
        held = db.execute('SELECT identity,name,profile_key FROM profile_aliases WHERE source=? AND occurrence=?',
                          (key, occurrence)).fetchone()
        if held is not None:
            found.append({'identity': str(held['identity']), 'name': str(held['name']),
                          'profile_key': str(held['profile_key'])})
            continue
        make = make or _generator(folder)
        identity, name = _fresh(make, taken)
        profile_key = key if occurrence == 0 else f'identity:{identity}'
        db.execute('INSERT INTO profile_aliases(source,occurrence,identity,name,profile_key) VALUES (?,?,?,?,?)',
                   (key, occurrence, identity, name, profile_key))
        taken.add(name.casefold())
        found.append({'identity': identity, 'name': name, 'profile_key': profile_key})
    return found


def write_roster(folder: Path | str, names: Sequence[str]) -> Path:
    """Create a names-only shared roster once; retries never replace an existing file's contents."""
    if not names or any(not name.strip() or '\n' in name or '\r' in name for name in names):
        raise Stop('A participant roster needs nonempty single-line names.', 'supply the generated participant names')
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / 'participants.md'
    text = '# Participants\n\n' + ''.join(f'- {name}\n' for name in names)
    expected = text.encode('utf-8')
    try:
        with path.open('xb') as written:
            written.write(expected)
    except FileExistsError:
        try:
            existing = path.read_bytes()
        except OSError as error:
            raise Stop(f'The existing participant roster could not be verified: {path}.',
                       'preserve the existing file and choose a new session folder') from error
        if existing != expected:
            raise Stop(f'The participant roster already has different content: {path}.',
                       'preserve the existing file and choose a new session folder')
    return path
