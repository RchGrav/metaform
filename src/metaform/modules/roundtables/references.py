"""Bounded, project-confined reads of accepted messages, files and literal search references."""
from __future__ import annotations

import os
import re
import shlex
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote

from metaform.module import Context, Stop

MAX_BYTES = 1024 * 1024
MAX_FILES = 10000
SEARCH_SECONDS = 2.0
CONTEXT_LINES = 80
MAX_PATHS = 8
MESSAGE = re.compile(r'R\d+-\d+')
LOCATION = re.compile(r'^(.*?)(?::(\d+)|#L(\d+))(?:-L?\d+|:\d+)?$')
SHORT_FLAGS = frozenset('niFlrRH')
LONG_FLAGS = frozenset({'--line-number', '--ignore-case', '--fixed-strings', '--files-with-matches',
                        '--recursive', '--with-filename', '--no-messages'})


def _refused(message: str) -> Stop:
    return Stop(message, 'choose an accepted message id, project file, or a literal rg/grep reference')


def _result(path: str, text: str, cut: bool = False, line: int | None = None) -> dict[str, Any]:
    encoded = text.encode('utf-8')
    if len(encoded) > MAX_BYTES:
        text, cut = encoded[:MAX_BYTES].decode('utf-8', 'ignore'), True
    return {'path': path, 'text': text, 'cut': cut, **({'line': line} if line is not None else {})}


def _path(root: Path, given: str) -> Path:
    try:
        found = (root / given).resolve()
    except (OSError, RuntimeError, ValueError) as error:
        raise _refused('That project path could not be resolved.') from error
    if not found.is_relative_to(root):
        raise _refused('References must stay inside this project folder.')
    return found


def _text(path: Path) -> tuple[str | None, bool]:
    with path.open('rb') as held:
        data = held.read(MAX_BYTES + 1)
    if b'\0' in data:
        return None, len(data) > MAX_BYTES
    raw = data[:MAX_BYTES]
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError as error:
        if len(data) <= MAX_BYTES or error.start < len(raw) - 3:
            return None, len(data) > MAX_BYTES
        text = raw[:error.start].decode('utf-8')
    return text, len(data) > MAX_BYTES


def _file(root: Path, reference: str) -> dict[str, Any]:
    match = LOCATION.fullmatch(reference)
    given, line = (match[1], int(match[2] or match[3])) if match else (reference, None)
    if line is not None and line < 1:
        raise _refused('A file line number starts at 1.')
    found = _path(root, given)
    if not found.is_file():
        raise _refused('No such project file.')
    try:
        text, cut = _text(found)
    except OSError as error:
        raise _refused('That project file could not be read.') from error
    if text is None:
        raise _refused('That file is not readable UTF-8 text.')
    relative = found.relative_to(root).as_posix()
    if line is not None:
        lines = text.splitlines()
        if line > len(lines):
            if not cut:
                raise _refused(f'Line {line} is outside that project file.')
            return _result(relative, f'The read limit was reached before line {line}.', True, line)
        start, end = max(0, line - 1 - CONTEXT_LINES), min(len(lines), line + CONTEXT_LINES)
        text = f'{relative}:{line}\n\n' + '\n'.join(f'{at + 1}: {lines[at]}' for at in range(start, end))
    return _result(relative, text, cut, line)


def _compound(command: str) -> bool:
    quote, escaped = '', False
    for at, char in enumerate(command):
        if escaped:
            escaped = False
        elif char == '\\' and quote != "'":
            escaped = True
        elif quote:
            if char == quote:
                quote = ''
        elif char in "\"'":
            quote = char
        elif char in ';|&<>`\n\r' or command[at:at + 2] == '$(':
            return True
    return False


def _command(root: Path, command: str) -> tuple[str, list[Path], bool, bool]:
    if _compound(command):
        raise _refused('Compound commands are not supported in references.')
    try:
        words = shlex.split(command)
    except ValueError as error:
        raise _refused('The search reference has unmatched quotes.') from error
    operands: list[str] = []
    flags: set[str] = set()
    options = True
    for word in words[1:]:
        if options and word == '--':
            options = False
        elif options and word.startswith('--'):
            if word not in LONG_FLAGS:
                raise _refused(f'That search flag is not supported: {word}.')
            flags.add(word)
        elif options and word.startswith('-') and word != '-':
            if not word[1:] or not set(word[1:]).issubset(SHORT_FLAGS):
                raise _refused(f'That search flag is not supported: {word}.')
            flags.update(f'-{char}' for char in word[1:])
        else:
            operands.append(word)
    if not operands or not operands[0] or len(operands[0]) > 4096:
        raise _refused('A search reference needs one nonempty literal pattern of at most 4096 characters.')
    if len(operands) > MAX_PATHS + 1:
        raise _refused(f'A search reference names at most {MAX_PATHS} project paths.')
    paths = [_path(root, value) for value in operands[1:]] or [root]
    if any(not path.is_file() and not path.is_dir() for path in paths):
        raise _refused('No such project search path.')
    return operands[0], paths, bool(flags & {'-i', '--ignore-case'}), bool(flags & {'-l', '--files-with-matches'})


def _search(root: Path, command: str) -> dict[str, Any]:
    pattern, paths, ignore_case, files_only = _command(root, command)
    wanted = pattern.casefold() if ignore_case else pattern
    deadline, examined, length = time.monotonic() + SEARCH_SECONDS, 0, 0
    matches: list[str] = []
    seen: set[Path] = set()
    cut = False

    def files() -> Iterator[Path]:
        for path in paths:
            if path.is_file():
                yield path
                continue
            for base, directories, leaves in os.walk(path, followlinks=False):
                directories[:] = [name for name in directories
                                   if name != '.git' and not (Path(base) / name).is_symlink()]
                if time.monotonic() >= deadline:
                    return
                for name in leaves:
                    yield Path(base) / name

    for path in files():
        if examined >= MAX_FILES or time.monotonic() >= deadline:
            cut = True
            break
        examined += 1
        try:
            found = _path(root, str(path))
            if found in seen or not found.is_file() or '.git' in found.relative_to(root).parts:
                continue
            seen.add(found)
            text, shortened = _text(found)
        except (OSError, Stop):
            continue
        cut = cut or shortened
        if text is None:
            continue
        relative = found.relative_to(root).as_posix()
        for line, content in enumerate(text.splitlines(), 1):
            if time.monotonic() >= deadline:
                cut = True
                break
            if wanted not in (content.casefold() if ignore_case else content):
                continue
            entry = f'{relative}:{line}' if files_only else f'{relative}:{line}:{content}'
            added = len(entry.encode('utf-8')) + 1
            if length + added > MAX_BYTES:
                matches.append(entry.encode('utf-8')[:MAX_BYTES - length].decode('utf-8', 'ignore'))
                length = MAX_BYTES
                cut = True
                break
            matches.append(entry)
            length += added
            if files_only:
                break
        if length >= MAX_BYTES or time.monotonic() >= deadline:
            cut = True
            break
    cut = cut or time.monotonic() >= deadline
    text = '\n'.join(matches) if matches else f'No matches for {pattern!r}.'
    return _result('Search results', text, cut)


def _message(ctx: Context, table: str, reference: str) -> dict[str, Any]:
    with ctx.require_store().tables(write=False) as tx:
        for row in tx.rows('events', {'table_id': table}, limit=0).results:
            if row['kind'] not in ('turn', 'comment'):
                continue
            payload = cast(dict[str, Any], row['payload'])
            if payload.get('message_id') != reference or payload.get('accepted') is False:
                continue
            outcome = payload.get('outcome')
            if outcome in ('vetoed', 'none', 'pass', 'unjudged', 'handoff', 'carry', 'over512'):
                continue
            if not (outcome in ('kept', 'comment') or payload.get('accepted') is True or row['kind'] == 'comment'):
                continue
            name = str(payload.get('seat') or 'Participant')
            return _result(reference, f'# {reference} · {name}\n\n{payload.get("text") or ""}')
    raise _refused(f'No accepted message {reference} was recorded for this table.')


def read(ctx: Context) -> dict[str, Any]:
    from . import table_row

    table = table_row(ctx)
    root = Path(ctx.require_store().project().path).resolve()
    reference = str(ctx.nouns.get('reference') or '').strip()
    if not reference or len(reference) > 8192:
        raise _refused('A reference is nonempty and at most 8192 characters.')
    if reference.startswith('`') and reference.endswith('`'):
        reference = reference.strip('`').strip()
    if MESSAGE.fullmatch(reference):
        return _message(ctx, str(table['table_id']), reference)
    try:
        words = shlex.split(reference)
    except ValueError:
        words = []
    if len(words) == 1 and words[0].startswith(('rg ', 'grep ')):
        reference = words[0]
    if reference.startswith(('rg ', 'grep ')):
        return _search(root, reference)
    if len(words) == 1:
        reference = words[0]
    return _file(root, unquote(reference))
