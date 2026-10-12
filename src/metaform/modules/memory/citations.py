"""The evidence a memory cites, checked on every read, so a memory whose evidence changed is flagged stale and never
trusted silently.

A memory may cite where its knowledge comes from, as `path:line`, `path:start-end`, `path:symbol` or `path` alone,
relative to the project's folder. The write refuses a citation that names no file there, a line past its end, or a
symbol the file does not hold, so a citation is true when it is made. What it saw is kept: the cited lines' text
hashed, or for a whole file its bytes hashed, and for a symbol nothing more than its name; with each, the file's size
and modification time. A read checks each citation cheaply: a file whose size and time are as kept holds, unread;
any other is read once per read and checked again, and a citation whose file is gone, whose lines no longer read as
they did, or whose symbol is no longer in the file is stale, with the reason, and where the cited text now stands when
it moved.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from metaform import home
from metaform.module import Context, Stop

Row = dict[str, Any]
LINES = re.compile(r'^(?P<start>\d+)(?:-(?P<end>\d+))?$')
SYMBOL = re.compile(r'^[A-Za-z_][\w.]*$')


def root_of(ctx: Context) -> Path:
    """The folder a citation's path is read from: the project's registered source path, else the call's folder."""
    project = ctx.store.project_id if ctx.store is not None else ctx.project
    found = home.project(str(project)) if project else None
    return Path(found.path) if found is not None and found.path else ctx.folder


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]


def _lines(text: str, start: int, end: int) -> str:
    """The cited lines, each stripped, so a change of indentation alone keeps the evidence."""
    return '\n'.join(line.strip() for line in text.splitlines()[start - 1:end])


def _split(cite: str, root: Path) -> tuple[str, str]:
    """A citation's path and what follows it: the whole citation when it names a file, else the text before its last
    colon (a doubled colon, `path::symbol`, read the same)."""
    if (root / cite).is_file():
        return cite, ''
    path, _, rest = cite.rpartition(':')
    return path.rstrip(':'), rest


def stamp(cite: str, root: Path) -> Row:
    """What a citation is kept as when a memory is written: its path, its lines or symbol, what they read as, and the
    file's size and time. Stop when it names nothing the project holds, with the forms it takes."""
    cite = ' '.join(cite.split())
    path, rest = _split(cite, root)
    forms = 'cite path:line, path:start-end, path:symbol or a path, relative to the project folder'
    target = (root / path) if path else None
    if target is None or not target.is_file():
        raise Stop(f'The citation {cite!r} names no file in the project at {root}.', forms)
    stat = target.stat()
    row: Row = {'cite': cite, 'path': path, 'start': None, 'end': None, 'symbol': None, 'size': stat.st_size,
                'mtime': stat.st_mtime_ns}
    if not rest:
        row['digest'] = hashlib.sha256(target.read_bytes()).hexdigest()[:16]
        return row
    text = target.read_text(encoding='utf-8', errors='replace')
    lines = LINES.match(rest)
    if lines:
        start = int(lines.group('start'))
        end = int(lines.group('end') or start)
        if not 1 <= start <= end <= len(text.splitlines()):
            raise Stop(f'{path} has {len(text.splitlines())} lines; the citation {cite!r} is past them.', forms)
        row.update(start=start, end=end, digest=_digest(_lines(text, start, end)))
        return row
    if not SYMBOL.match(rest) or not re.search(rf'\b{re.escape(rest.split(".")[-1])}\b', text):
        raise Stop(f'{path} holds no symbol {rest!r}, so the citation {cite!r} cannot be checked.', forms)
    row.update(symbol=rest, digest=None)
    return row


@dataclass
class Checker:
    """Checks citations against the project's files for one read: each file is stat'ed, and read only when its size or
    time changed, once."""
    root: Path
    texts: dict[str, str | None] = field(default_factory=dict[str, str | None])

    def _text(self, path: str) -> str | None:
        if path not in self.texts:
            target = self.root / path
            self.texts[path] = target.read_text(encoding='utf-8', errors='replace') if target.is_file() else None
        return self.texts[path]

    def stale(self, row: Row) -> str | None:
        """Why a kept citation no longer holds, or None when it does."""
        target = self.root / str(row['path'])
        try:
            stat = target.stat()
        except OSError:
            return f'{row["path"]} is gone'
        if stat.st_size == row.get('size') and stat.st_mtime_ns == row.get('mtime'):
            return None  # unchanged since it was cited
        if row.get('symbol'):
            text = self._text(str(row['path'])) or ''
            name = str(row['symbol']).split('.')[-1]
            return None if re.search(rf'\b{re.escape(name)}\b', text) else f'{row["symbol"]} is no longer in it'
        if row.get('start') is None:
            held = hashlib.sha256(target.read_bytes()).hexdigest()[:16]
            return None if held == row.get('digest') else 'the file changed'
        text = self._text(str(row['path'])) or ''
        start, end = int(row['start']), int(row['end'])
        if _digest(_lines(text, start, end)) == row.get('digest'):
            return None
        span = end - start + 1
        count = len(text.splitlines())
        moved = next((at for at in range(1, count - span + 2) if _digest(_lines(text, at, at + span - 1))
                      == row.get('digest')), None)
        where = f'lines {start}-{end}' if end > start else f'line {start}'
        return f'{where} changed' + (f'; the cited text is now at line {moved}' if moved else '')
