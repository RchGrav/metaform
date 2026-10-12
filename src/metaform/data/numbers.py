"""The numbers of the items written at an address: one counter per address, kept in the project's own database.

Every item a module writes at an address, a memory, a question or message, a work record, takes the next number of
that address's counter. The counter counts up from 1 and never goes back, so a number is never reused: deleting an
item leaves a gap, and an item moved to another address takes the next number there. It is kept in the project's
own database, `project.sqlite3`, which a clear of the project's metaforms keeps, so a new intake never starts the
counters again. A number is shown in lowercase hex after `#`, `code.manager.route#1f`; upper case is read as well.

The table is given to a database made before it on the first number taken, as the aliases table is, so the project
database's layout version does not change and older code reads it as before.

Each take is also logged with the agent session that took it, `taken`, so a node's brief can say what the last session
added there as a range, MCP-037: the session is the one `shown.session` names, METAFORM_SESSION or the serving MCP
process, and None for a person's command line or the page. The log is given to a database the same way, on the first
number taken after it existed; numbers taken before it name no session, so no range is said for them.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from .. import home

# An item's reference: an address, `#`, and its number in hex, either case. The address holds no `#` and no space.
REFERENCE = re.compile(r'^(?P<address>[^#\s]+)#(?P<number>[0-9A-Fa-f]{1,15})$')


def shown(number: int) -> str:
    """A number as it is shown, `#1f`."""
    return f'#{number:x}'


def reference(address: str, number: int) -> str:
    """An item's reference, `<address>#<n>`, the number in lowercase hex."""
    return f'{address}{shown(number)}'


def parse(text: str) -> tuple[str, int] | None:
    """The address and number of a reference `<address>#<n>`, upper-case hex accepted; None when it is not one, or
    names number 0, which no item holds."""
    found = REFERENCE.match(text.strip())
    if found is None:
        return None
    number = int(found.group('number'), 16)
    return (found.group('address'), number) if number else None


def folder_of(path: Path) -> Path | None:
    """The project folder a store file lives in: the nearest folder above it holding the project database."""
    for folder in path.parents:
        if (folder / home.PROJECT_DB).is_file():
            return folder
    return None


def take(folder: Path, address: str, count: int = 1) -> int:
    """Take the next `count` numbers of the address's counter in the project folder's database; returns the first.
    Its own transaction: an item whose write fails after this leaves a gap, never a reused number."""
    with home.project_db(folder, write=True) as db:
        return take_in(db, address, count)


TAKEN = ("""CREATE TABLE IF NOT EXISTS taken(
  address TEXT NOT NULL,
  first   INTEGER NOT NULL,
  last    INTEGER NOT NULL,
  session TEXT,
  at      TEXT NOT NULL
)""", 'CREATE INDEX IF NOT EXISTS taken_address ON taken(address)')


def take_in(db: sqlite3.Connection, address: str, count: int = 1) -> int:
    """`take` inside a write transaction already open on the project database, for a write that takes its number and
    stores its item as one."""
    from .. import shown
    db.execute(home.NUMBERS)
    db.execute('INSERT INTO numbers(address, last) VALUES (?, ?) '
               'ON CONFLICT(address) DO UPDATE SET last = last + excluded.last', (address, count))
    last = int(db.execute('SELECT last FROM numbers WHERE address=?', (address,)).fetchone()[0])
    for statement in TAKEN:  # each alone: executescript would commit the transaction this take is part of
        db.execute(statement)
    db.execute('INSERT INTO taken(address, first, last, session, at) VALUES (?, ?, ?, ?, ?)',
               (address, last - count + 1, last, shown.session(), home.now()))
    return last - count + 1


def _has(db: sqlite3.Connection, table: str) -> bool:
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def last_session(folder: Path, address: str, *, besides: str | None = None) -> tuple[str, int, int, int] | None:
    """What the last agent session to take numbers at the address took there, other than `besides`, the caller's own
    session, which is never news to it: `(session, first, last, count)`, the lowest and highest number it took and how
    many, None when no session is known to have taken one. A serving process names its session with the client it
    serves after it, `process:<id>:<client>`, so the process's own takes are its own whatever the client."""
    with home.project_db(folder) as db:
        if not _has(db, 'taken'):
            return None
        rows = db.execute('SELECT first, last, session FROM taken WHERE address=? AND session IS NOT NULL '
                          'ORDER BY rowid DESC', (address,)).fetchall()

    def own(session: str) -> bool:
        return besides is not None and (besides == session or besides.startswith(session + ':'))
    chosen = next((str(row[2]) for row in rows if not own(str(row[2]))), None)
    if chosen is None:
        return None
    held = [(int(row[0]), int(row[1])) for row in rows if row[2] == chosen]
    return chosen, min(first for first, _ in held), max(last for _, last in held), sum(b - a + 1 for a, b in held)


def latest(folder: Path, address: str) -> int:
    """The last number taken at the address, 0 when none has been."""
    with home.project_db(folder) as db:
        held = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='numbers'").fetchone()
        row = db.execute('SELECT last FROM numbers WHERE address=?', (address,)).fetchone() if held else None
    return int(row[0]) if row else 0


def project_folder(project_id: str) -> Path:
    """The folder of a registered project, whose database holds its counters."""
    from ..errors import StoreError
    folder = home.project_folder(project_id)
    if folder is None:
        raise StoreError(f'Project {project_id} is no longer registered.', 'metaform list projects')
    return folder
