"""The evidence a memory cites, checked on every read, so a memory whose evidence changed is flagged stale and never
trusted silently.

A memory may cite where its knowledge comes from, as `path:line`, `path:start-end`, `path:symbol` or `path` alone,
relative to the project's folder. The write refuses a citation that names no file there, a line past its end, or a
symbol the file does not hold, so a citation is true when it is made. What it saw is kept: the cited lines' text
hashed, or for a whole file its bytes hashed, and for a symbol nothing more than its name; with each, the file's size
and modification time. A citation whose file is gone, whose lines no longer read as they did, or whose symbol is no
longer in the file is stale, with the reason, and where the cited text now stands when it moved.

Whether a citation holds is worked out once each time its file changes and stored with it, beside the file's size and
time it was worked out against: by the citation watcher, `watch.py`, when the system says the file changed, so a read
looks the result up and reads no file. While no watcher runs for the project, a read stats each cited file and uses
the stored result of one that is as it was when that result was worked out, and works out the rest itself, each file
read and split once per read.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from metaform import home
from metaform.data import TableTx
from metaform.module import Context, Stop

Row = dict[str, Any]
LINES = re.compile(r'^(?P<start>\d+)(?:-(?P<end>\d+))?$')
SYMBOL = re.compile(r'^[A-Za-z_][\w.]*$')


def root_of(ctx: Context) -> Path:
    """The folder a citation's path is read from: the project's registered source path, else the call's folder. The
    registry remembers where it found the project, so finding it again opens no other project's database."""
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
    """Checks citations against the project's files for one read, or one pass of the watcher: each file is stat'ed,
    and read and split only when its size or time changed, once. The project's folder is looked up on the first
    citation checked, so a read of memories that cite nothing costs nothing more."""
    ctx: Context
    texts: dict[str, str | None] = field(default_factory=dict[str, str | None])
    lines: dict[str, list[str]] = field(default_factory=dict[str, list[str]])
    windows: dict[tuple[str, int], dict[str, int]] = field(default_factory=dict[tuple[str, int], dict[str, int]])
    _root: Path | None = None
    _watched: bool | None = None

    @property
    def root(self) -> Path:
        if self._root is None:
            self._root = root_of(self.ctx)
        return self._root

    @property
    def watched(self) -> bool:
        """Whether the project's citation watcher runs, so every stored result is current; asked once per read, of
        the lock the watcher holds."""
        if self._watched is None:
            from .watch import watching
            project = self.ctx.store.project_id if self.ctx.store is not None else self.ctx.project
            self._watched = bool(project) and watching(str(project))
        return self._watched

    def stamp_of(self, path: str) -> tuple[int | None, int | None]:
        """The file's size and time now; both None when it is gone."""
        try:
            stat = (self.root / path).stat()
        except OSError:
            return None, None
        return stat.st_size, stat.st_mtime_ns

    def held(self, row: Row) -> str | None:
        """Why a kept citation no longer holds, or None when it does, as a read gives it: the stored result while the
        watcher runs, with no file read; else the stored result when the file is as it was when that was worked out,
        and otherwise worked out now."""
        if self.watched or self.stamp_of(str(row['path'])) == checked(row):
            return row.get('stale') or None
        return self.stale(row)

    def _text(self, path: str) -> str | None:
        if path not in self.texts:
            target = self.root / path
            self.texts[path] = target.read_text(encoding='utf-8', errors='replace') if target.is_file() else None
        return self.texts[path]

    def _lines(self, path: str) -> list[str]:
        """The file's lines, each stripped as `_lines` strips them, split once per read."""
        if path not in self.lines:
            self.lines[path] = [line.strip() for line in (self._text(path) or '').splitlines()]
        return self.lines[path]

    def _moved(self, path: str, span: int, digest: object) -> int | None:
        """The first line where `span` lines read as the digest, from the digest of every window of that size, taken
        once per file and size in a read, so many moved citations in one file cost one pass, not one per position."""
        key = (path, span)
        if key not in self.windows:
            lines = self._lines(path)
            found: dict[str, int] = {}
            for at in range(1, len(lines) - span + 2):
                found.setdefault(_digest('\n'.join(lines[at - 1:at - 1 + span])), at)
            self.windows[key] = found
        return self.windows[key].get(str(digest))

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
        path = str(row['path'])
        start, end = int(row['start']), int(row['end'])
        if _digest('\n'.join(self._lines(path)[start - 1:end])) == row.get('digest'):
            return None
        moved = self._moved(path, end - start + 1, row.get('digest'))
        where = f'lines {start}-{end}' if end > start else f'line {start}'
        return f'{where} changed' + (f'; the cited text is now at line {moved}' if moved else '')


def checked(row: Row) -> tuple[int | None, int | None]:
    """The file's size and time the citation's stored result was worked out against: those it was cited at, until
    the watcher works it out again."""
    if row.get('checked_mtime') is None and row.get('stale') is None:
        return row.get('size'), row.get('mtime')
    return row.get('checked_size'), row.get('checked_mtime')


def rework(tx: TableTx, checker: Checker, paths: set[str] | None = None) -> int:
    """Work out again whether each citation of these files holds, every cited file's with None, and store it with the
    file's size and time, for each citation whose file is no longer as it was when its result was worked out. The
    watcher's pass after a change; how many citations' results changed."""
    changed = 0
    for row in tx.rows('citations', limit=0).results:
        path = str(row['path'])
        if paths is not None and path not in paths:
            continue
        size, mtime = checker.stamp_of(path)
        if (size, mtime) == checked(row):
            continue
        why = checker.stale(row)
        tx.update('citations', {'entity': row['entity'], 'cite': row['cite']},
                  {'stale': why, 'checked_size': size, 'checked_mtime': mtime})
        changed += why != (row.get('stale') or None)
    return changed
