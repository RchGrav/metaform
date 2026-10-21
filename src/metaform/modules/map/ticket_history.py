"""Completed tickets retained by Git on the registered project's active dev branch."""
from __future__ import annotations

import subprocess
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path
from typing import Any, ParamSpec, TypeVar

from metaform import home
from metaform.data import StoreError, parse_reference, reference

P = ParamSpec('P')
R = TypeVar('R')


@dataclass(frozen=True)
class History:
    folder: Path
    tickets: dict[str, dict[str, str]]
    numbers: dict[str, dict[str, str]]
    fault: str | None = None


_READS: ContextVar[dict[str, History] | None] = ContextVar('map_git_history', default=None)


def per_call(run: Callable[P, R]) -> Callable[P, R]:
    """Share one Git snapshot within a command, including its linked node reads."""
    @wraps(run)
    def call(*args: P.args, **kwargs: P.kwargs) -> R:
        if _READS.get() is not None:
            return run(*args, **kwargs)
        token = _READS.set({})
        try:
            return run(*args, **kwargs)
        finally:
            _READS.reset(token)
    return call


def _git(folder: Path, *words: str) -> str:
    try:
        result = subprocess.run(['git', *words], cwd=folder, capture_output=True, text=True,
                                encoding='utf-8', errors='replace', timeout=30, check=False,
                                stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as error:
        raise StoreError(f'Git history could not be read: {error}', 'check the project Git checkout') from error
    if result.returncode:
        raise StoreError(result.stderr.strip() or 'Git history could not be read.', 'check the project Git checkout')
    return result.stdout


def read(project: str) -> History:
    cache = _READS.get()
    if cache is not None and project in cache:
        return cache[project]
    registered = home.project(project)
    folder = Path(registered.path) if registered is not None else Path()
    tickets: dict[str, dict[str, str]] = {}
    numbers: dict[str, dict[str, str]] = {}
    fault = None
    try:
        if registered is None:
            raise StoreError('The project has no registered folder.', 'metaform list projects')
        _git(folder, 'symbolic-ref', '--quiet', 'HEAD')
        format = '%H%x00%cI%x00' + '%x00'.join(f'%(trailers:key=Metaform-{key},valueonly)'
                                              for key in ('Ticket', 'Number', 'Node', 'Board', 'Target')) + '%x00%B'
        fields = _git(folder, 'log', 'HEAD', '-z', f'--format={format}',
                      '--fixed-strings', '--grep=Metaform-Ticket:').split('\0')
        for offset in range(0, len(fields) - 7, 8):
            commit, done, work_id, item, node, board, target, body = (
                one.strip() for one in fields[offset:offset + 8])
            parsed = parse_reference(item) if item else None
            if not work_id or parsed is None or node != parsed[0]:
                continue
            item = reference(*parsed)
            done = datetime.fromisoformat(done).astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
            record = {'hash': commit, 'done': done, 'work_id': work_id, 'item': item, 'node': node, 'board': board,
                      'target': target or f'element:{node}', 'body': body}
            tickets.setdefault(work_id, record)
            numbers.setdefault(item, record)
    except StoreError as error:
        fault = str(error)
    found = History(folder, tickets, numbers, fault)
    if cache is not None:
        cache[project] = found
    return found


def resolve(project: str, given: str) -> dict[str, Any] | None:
    history = read(project)
    parsed = parse_reference(given)
    record = history.numbers.get(reference(*parsed)) if parsed else history.tickets.get(given)
    if record is None:
        return None
    details = _git(history.folder, 'show', '--format=%s%x00%B', '--name-only', '--no-renames', '-z',
                   record['hash']).split('\0')
    subject, body = details[:2]
    files = details[2:]
    if files:
        files[0] = files[0].removeprefix('\n')
    return {**record, 'subject': subject, 'body': body, 'state': 'committed',
            'files': [name for name in files if name]}
