"""The board's Archive: the project folder's git history, read by the page a page at a time, VIEW-037.

Once a ticket is done and shed, its commit is the record of the work: every completed ticket becomes one, carrying the
ticket's trailers, `Metaform-Ticket`, `Metaform-Number` (<address>#<n>), `Metaform-Node`, `Metaform-Board` and
`Metaform-Agent`. A commit made by hand carries none and is listed too, marked so, so the history is whole.

`GET /api/commits` lists the commits newest first, `PAGE` at a time, never the whole history in one answer: its
`next` cursor is the tip the first page was read from and how many commits git gave past it, so commits made while the
person pages do not shift the pages. It filters by board, by node and its leaves, by time, and by words in the
message. `GET /api/commit` gives one commit: its message, its files with their diffs, as an agent's tool call shows
its edits, and the parts of the map each file belongs to, placed through the sources layer's refs as a tool call's
files are, MAP-021. A new commit Metaform makes is said on `map.changed` with the kind `commit`, or `merge` for a
merge into the dev branch, and the page reads its first page again; nothing polls.
"""
from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Generator
from contextlib import closing
from pathlib import Path
from typing import TYPE_CHECKING, Any

from metaform.data import StoreError, placed, sources_index
from metaform.module import Stop

if TYPE_CHECKING:
    from .server import Handler

PAGE = 50  # commits on one page of the Archive
MOST = 200  # the most a page may ask for
PATCH_KEPT = 60_000  # the most characters of one file's diff sent, as the runner keeps of a tool call's
PATCH_READ = 4_000_000  # the most bytes of one commit's diff read; past it, its files are listed without their diffs
FIELD, RECORD = '\x1f', '\x1e'
LISTED = f'%H{FIELD}%cI{FIELD}%an{FIELD}%s{FIELD}%(trailers:only,unfold){RECORD}'
TRAILERS = {'metaform-ticket': 'ticket', 'metaform-number': 'number', 'metaform-node': 'node',
            'metaform-board': 'board', 'metaform-agent': 'agent'}
SHA = re.compile(r'[0-9a-f]{7,64}')
DAY = re.compile(r'\d{4}-\d{2}-\d{2}')
ESCAPE = re.compile(r'\\([abtnvfr"\\]|[0-7]{3})')  # git's C quoting of a name in a diff's header
ESCAPES = {'a': '\a', 'b': '\b', 't': '\t', 'n': '\n', 'v': '\v', 'f': '\f', 'r': '\r', '"': '"', '\\': '\\'}


def answer(handler: Handler, path: str, given: dict[str, str]) -> None:
    """Answer one read of the Archive. The server has checked its Host, token and class."""
    from .server import opened, project_folder
    try:
        _, folder = project_folder(given)
        if path == '/api/commit':
            return handler.send(200, commit(folder, given.get('sha', ''), sources_index(opened(given), str(folder))))
        return handler.send(200, listing(folder, given))
    except (Stop, StoreError) as error:
        return handler.refuse(error, 404 if isinstance(error, StoreError) else 400)


def git(folder: Path, *words: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(['git', '-c', 'core.quotePath=false', *words], cwd=folder, capture_output=True, text=True,
                          encoding='utf-8', errors='replace', timeout=60, check=False, stdin=subprocess.DEVNULL)


def tip(folder: Path) -> str | None:
    """The commit the folder's history starts from; a folder that is not a repository, or has no commit, raises Stop."""
    try:
        if git(folder, 'rev-parse', '--show-toplevel').returncode:
            raise Stop("The project's folder is not a git repository, so it has no commits to list.", 'git init')
    except FileNotFoundError as error:
        raise Stop('git is not installed, so the commits cannot be read.', 'install git') from error
    head = git(folder, 'rev-parse', '--verify', '--quiet', 'HEAD^{commit}')
    return head.stdout.strip() or None


def trailers(text: str) -> dict[str, str]:
    """A commit's Metaform trailers by their short names, as git parsed its trailer block."""
    found: dict[str, str] = {}
    for line in text.splitlines():
        key, colon, value = line.partition(':')
        name = TRAILERS.get(key.strip().lower())
        if colon and name and name not in found:
            found[name] = value.strip()
    return found


def row(record: str) -> dict[str, Any]:
    sha, when, author, subject, block = (record.lstrip('\n').split(FIELD) + [''] * 5)[:5]
    held = trailers(block)
    return {'sha': sha, 'when': when, 'author': author, 'subject': subject, 'ticket': held.get('ticket'),
            'number': held.get('number'), 'node': held.get('node'), 'board': held.get('board'),
            'agent': held.get('agent'), 'hand': 'ticket' not in held and 'number' not in held}


def records(folder: Path, words: list[str]) -> Generator[str, None, None]:
    """The records git log writes, one at a time, read as they come: the reader stops git once it has its page."""
    process = subprocess.Popen(['git', '-c', 'core.quotePath=false', *words], cwd=folder, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    assert process.stdout is not None
    held = b''
    try:
        while chunk := os.read(process.stdout.fileno(), 65536):
            held += chunk
            *whole, held = held.split(RECORD.encode())
            for one in whole:
                yield one.decode('utf-8', errors='replace')
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()


def listing(folder: Path, given: dict[str, str]) -> dict[str, Any]:
    """One page of commits, newest first: `after`, the cursor a page gave as `next`; `board`, a board's name, '' the
    first board's, absent for every commit; `node`, an Address, its commits and its leaves'; `since` and `until`, days
    as YYYY-MM-DD, both included; `words`, each in the message. Git narrows by the words and the trailers' text, then
    each trailer is checked exactly. `next` is null on the last page."""
    try:
        limit = max(1, min(MOST, int(given.get('limit') or PAGE)))
    except ValueError as error:
        raise Stop('limit is a whole number of commits.', f'GET /api/commits?limit={PAGE}') from error
    start, _, skipped = str(given.get('after') or '').partition('.')
    if start and not (SHA.fullmatch(start) and skipped.isdigit()):
        raise Stop('after is the cursor a page of commits gave as next.', 'GET /api/commits?after=<next>')
    start = start or tip(folder) or ''
    if not start:
        return {'commits': [], 'next': None}
    board, node = given.get('board'), str(given.get('node') or '').strip()
    words = ['log', f'--format={LISTED}', '--no-color', f'--skip={int(skipped or 0)}', '--fixed-strings',
             '--regexp-ignore-case', '--all-match']
    for side, edge in (('since', '00:00:00'), ('until', '23:59:59')):
        day = str(given.get(side) or '')
        if day and not DAY.fullmatch(day):
            raise Stop(f'{side} is a day, YYYY-MM-DD.', f'GET /api/commits?{side}=2026-10-21')
        if day:
            words.append(f'--{side}={day}T{edge}')
    if board is not None:
        words.append(f'--grep=Metaform-Board: {board}'.rstrip())
    if node:
        words.append(f'--grep=Metaform-Node: {node}')
    words += [f'--grep={word}' for word in str(given.get('words') or '').split()]
    words += [start, '--']
    commits: list[dict[str, Any]] = []
    read = last = int(skipped or 0)
    with closing(records(folder, words)) as given_back:  # closed as the page fills, which stops git
        for record in given_back:
            read += 1
            one = row(record)
            if board is not None and (one['board'] is None or one['board'] != board):
                continue
            if node and not (one['node'] == node or str(one['node'] or '').startswith(node + '.')):
                continue
            if len(commits) == limit:  # one more than the page: there is a next page, from the last one listed
                return {'commits': commits, 'next': f'{start}.{last}'}
            commits.append(one)
            last = read
    return {'commits': commits, 'next': None}


def unquoted(path: str) -> str:
    """A path as git writes it in a diff's header, its C quotes taken off: core.quotePath off leaves only a name with
    a quote, a backslash or a control character quoted."""
    if len(path) < 2 or not (path.startswith('"') and path.endswith('"')):
        return path
    return ESCAPE.sub(lambda found: ESCAPES.get(found[1]) or chr(int(found[1], 8)), path[1:-1])


def file_of(chunk: list[str]) -> dict[str, Any]:
    """One file's part of a commit's patch: its path, how it changed, the lines added and removed, and its hunks."""
    head = next((at for at, line in enumerate(chunk) if line.startswith('@@')), len(chunk))
    path = old = ''
    for line in chunk[:head]:
        if line.startswith('rename to '):
            path = unquoted(line[10:])
        elif line.startswith('rename from '):
            old = unquoted(line[12:])
        elif line.startswith('+++ ') and line[4:] != '/dev/null' and not path:
            path = unquoted(line[4:]).removeprefix('b/')
        elif line.startswith('--- ') and line[4:] != '/dev/null' and not old:
            old = unquoted(line[4:]).removeprefix('a/')
    if not path and not old:  # a binary file or a mode alone: the names on its first line, both the same
        named = chunk[0].removeprefix('diff --git ')
        half = (len(named) - 5) // 2
        if named == f'a/{named[2:2 + half]} b/{named[2:2 + half]}':
            path = named[2:2 + half]
    body = chunk[head:]
    patch = ''.join(line + '\n' for line in body)
    return {'path': path or old, 'was': old if path and old and old != path else None,
            'created': any(line.startswith('new file mode') for line in chunk[:head]),
            'deleted': any(line.startswith('deleted file mode') for line in chunk[:head]),
            'binary': any(line.startswith('Binary files') for line in chunk[:head]),
            'added': sum(1 for line in body if line.startswith('+')),
            'removed': sum(1 for line in body if line.startswith('-')),
            'patch': patch[:PATCH_KEPT], 'truncated': len(patch) > PATCH_KEPT}


def commit(folder: Path, given: str, index: dict[str, list[dict[str, str]]]) -> dict[str, Any]:
    """One commit: its message whole, its files each with its diff against its first parent, and the parts of the map
    each file belongs to, and all of them, as a tool call's are found, MAP-021."""
    tip(folder)
    if not SHA.fullmatch(given):
        raise Stop('sha names a commit by its hash.', 'GET /api/commit?sha=<sha>')
    sha = git(folder, 'rev-parse', '--verify', '--quiet', f'{given}^{{commit}}').stdout.strip()
    if not sha:
        raise StoreError(f'No commit {given} in this project.', 'the board\'s Archive lists them')
    shown = git(folder, 'show', '-s', f'--format=%H{FIELD}%cI{FIELD}%an{FIELD}%s{FIELD}%(trailers:only,unfold)'
                f'{FIELD}%P{FIELD}%B', sha).stdout
    *head, parents, message = shown.split(FIELD, 6)
    found = row(FIELD.join(head))
    against = [parents.split()[0], sha] if parents.split() else ['--root', sha]
    words = ['diff-tree', '-r', '-M', '-p', '--no-color', '--no-ext-diff', '--no-commit-id', *against]
    process = subprocess.Popen(['git', '-c', 'core.quotePath=false', *words], cwd=folder, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    assert process.stdout is not None
    try:
        read = process.stdout.read(PATCH_READ + 1)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()
    cut = len(read) > PATCH_READ
    lines = read[:PATCH_READ].decode('utf-8', errors='replace').split('\n')
    starts = [at for at, line in enumerate(lines) if line.startswith('diff --git ')]
    files = [file_of(lines[begin:end]) for begin, end in zip(starts, [*starts[1:], len(lines)], strict=True)]
    if cut:  # the last file read is cut short, and the files past it are listed without their diffs
        if files:
            files[-1]['truncated'] = True
        named = {one['path'] for one in files}
        listed = git(folder, 'diff-tree', '-r', '-M', '--name-only', '--no-commit-id', *against).stdout.splitlines()
        files += [{'path': path, 'was': None, 'created': False, 'deleted': False, 'binary': False, 'added': None,
                   'removed': None, 'patch': '', 'truncated': True} for path in listed if path not in named]
    nodes: list[dict[str, str]] = []
    for one in files:
        one['nodes'], one['exact'] = placed(index, one['path'])
        nodes.extend(place for place in one['nodes'] if place not in nodes)
    return {**found, 'message': message.rstrip('\n'), 'parents': parents.split(), 'files': files, 'nodes': nodes}
