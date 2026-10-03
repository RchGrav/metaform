"""The harnesses Metaform knows, MCP-028.

A harness is known by the parent folder of its binary, since its path may carry its version and some harnesses run
from an install folder of their own; a binary under the system's temporary folder is ignored. Once the agent says
it is done provisioning a harness, the home records it, and it is never asked again. Under a harness not
recorded, every command gives the notice on stderr, D96.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from . import home

# A home made before this table existed is given it on the first harness recorded, as with the nonces, BASE-050.
HARNESSES = """CREATE TABLE IF NOT EXISTS harnesses(
  path_key TEXT PRIMARY KEY,
  binary   TEXT NOT NULL,
  done     TEXT NOT NULL
);
"""

NOTICE = ("This is Metaform's first run here. Read metaform help provision for each feature, MCP registration, "
          'skill and hooks, then run metaform provision done.')


def running() -> Path | None:
    """The binary of the harness Metaform runs under. How it is found waits on Rich's answer to the D96
    follow-up at code.installer; until then none is found, so no notice is given."""
    return None


def notice() -> str | None:
    """The first-run notice, when the running harness is one the home has not recorded."""
    binary = running()
    if binary is None or key(binary) is None or known(binary):
        return None
    return NOTICE


def key(binary: Path | str) -> str | None:
    """The harness a binary belongs to: the parent folder of the binary a link points to, or None under the
    temporary folder."""
    folder = Path(home.path_key(Path(binary).expanduser().resolve().parent))
    temporary = Path(home.path_key(tempfile.gettempdir()))
    if folder == temporary or temporary in folder.parents:
        return None
    return str(folder)


def known(binary: Path | str) -> bool:
    """Whether the agent has said it is done provisioning this binary's harness."""
    found = key(binary)
    if found is None or not home.base_path().exists():
        return False
    with home.base() as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='harnesses'").fetchone():
            return False
        return db.execute('SELECT 1 FROM harnesses WHERE path_key=?', (found,)).fetchone() is not None


def done(binary: Path | str) -> None:
    """Record that provisioning this binary's harness is done. An ignored binary records nothing."""
    found = key(binary)
    if found is None:
        return
    with home.base(write=True) as db:
        db.execute(HARNESSES)
        db.execute('INSERT INTO harnesses(path_key, binary, done) VALUES (?, ?, ?) '
                   'ON CONFLICT(path_key) DO UPDATE SET binary=excluded.binary, done=excluded.done',
                   (found, str(binary), home.now()))
