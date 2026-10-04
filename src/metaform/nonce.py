"""The nonce service, BASE-050: a module requests a nonce, and an agent reaches its work by running metaform <nonce>.

A nonce is seven digits, the first never zero. Its record holds the module that requested it, the function in that
module to call, which is one of the module's verbs, and the value the chassis passes to it. The module updates the
nonce as the work moves and closes it when the task is complete. A closed nonce's record is kept, so its number is
never issued again.
"""
from __future__ import annotations

import json
import re
import secrets
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from . import home
from .errors import Stop

_CURRENT: ContextVar[Nonce | None] = ContextVar('metaform_nonce', default=None)
FORM = re.compile(r'[1-9][0-9]{6}')  # the form of a nonce: seven digits, the first never zero


@dataclass(frozen=True)
class Nonce:
    nonce: str
    module: str
    function: str
    value: Any
    open: bool
    created: str
    closed: str | None


def _record(row: tuple[Any, ...]) -> Nonce:
    return Nonce(str(row[0]), str(row[1]), str(row[2]), json.loads(row[3]), row[5] is None, str(row[4]),
                 None if row[5] is None else str(row[5]))


def _taken(word: str) -> bool:
    """A nonce is the first word of a command, so it is never the name of a command or of a module."""
    from . import loader
    from .cli import VERBS
    return word in VERBS or any(found.id == word for found in loader.discover())


def _draw() -> str:
    return str(1_000_000 + secrets.randbelow(9_000_000))


def request(module: str, function: str, value: Any = None) -> str:
    """A new nonce for the module: what `metaform <nonce>` runs is the module's function, sent the value. A number
    already in the table, open or closed, is never issued again."""
    while True:
        word = _draw()
        if _taken(word):
            continue
        with home.base(write=True) as db:
            db.execute(home.NONCES)
            if db.execute('SELECT 1 FROM nonces WHERE nonce=?', (word,)).fetchone():
                continue
            db.execute('INSERT INTO nonces(nonce, module_id, function, value, created) VALUES(?, ?, ?, ?, ?)',
                       (word, module, function, json.dumps(value), home.now()))
        return word


def read(nonce: str) -> Nonce | None:
    if not home.base_path().exists():
        return None
    with home.base() as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='nonces'").fetchone():
            return None
        row = db.execute('SELECT nonce, module_id, function, value, created, closed FROM nonces WHERE nonce=?',
                         (nonce,)).fetchone()
    return None if row is None else _record(row)


def _held(nonce: str) -> Nonce:
    found = read(nonce)
    if found is None:
        raise Stop(f'No nonce {nonce} was issued.', 'metaform help')
    return found


def update(nonce: str, *, value: Any = None, function: str | None = None) -> Nonce:
    """Change what the next run of the nonce is sent, the function it calls, or both."""
    held = _held(nonce)
    with home.base(write=True) as db:
        db.execute('UPDATE nonces SET value=?, function=? WHERE nonce=?',
                   (json.dumps(held.value if value is None else value), function or held.function, nonce))
    found = _held(nonce)
    if (now := _CURRENT.get()) is not None and now.nonce == nonce:
        _CURRENT.set(found)
    return found


def mutate(nonce: str, change: Callable[[Any], Any]) -> Nonce:
    """Read and change a nonce value in one transaction, retaining concurrent updates."""
    with home.base(write=True) as db:
        row = db.execute('SELECT nonce, module_id, function, value, created, closed FROM nonces WHERE nonce=?',
                         (nonce,)).fetchone()
        if row is None:
            raise Stop(f'No nonce {nonce} was issued.', 'metaform help')
        held = _record(row)
        value = change(held.value)
        db.execute('UPDATE nonces SET value=? WHERE nonce=?', (json.dumps(value), nonce))
        found = Nonce(held.nonce, held.module, held.function, value, held.open, held.created, held.closed)
    if (now := _CURRENT.get()) is not None and now.nonce == nonce:
        _CURRENT.set(found)
    return found


def close(nonce: str) -> Nonce:
    """The task is complete: the nonce gives no menu and runs no command from now on. Its record is kept."""
    held = _held(nonce)
    if held.open:
        with home.base(write=True) as db:
            db.execute('UPDATE nonces SET closed=? WHERE nonce=?', (home.now(), nonce))
    found = _held(nonce)
    if (now := _CURRENT.get()) is not None and now.nonce == nonce:
        _CURRENT.set(found)
    return found


def reached() -> Nonce | None:
    """The nonce the running command came through, or None when it did not come through one. A verb can in this way
    be both a module's entry and the function its nonce calls."""
    return _CURRENT.get()


def current() -> Nonce:
    """The nonce the running command was reached through."""
    held = reached()
    if held is None:
        raise Stop('This command was not run through a nonce.', 'metaform help')
    return held


def entered(held: Nonce) -> Any:
    return _CURRENT.set(held)


def left(token: Any) -> None:
    _CURRENT.reset(token)
