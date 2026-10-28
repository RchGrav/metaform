"""The git worktree the tickets of one composer grouping share: made when a pair claims it, merged into the checked-out
branch and removed when its round closes with Full Auto on."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, cast

from metaform.module import Context, Stop

FOLDER = '.worktrees'  # inside the project folder, so an agent there reaches the project; kept out of git status
NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]*')
TABLE = 'tickets'


def named(name: str) -> str:
    """A worktree name as given, one safe path segment and branch name."""
    if not NAME.fullmatch(name) or name in ('.', '..') or name.endswith('.lock') or '..' in name:
        raise Stop(f'A worktree name is letters, digits, dots, dashes and underscores, not {name!r}.',
                   'metaform tasks ticket worktree=<name>')
    return name


def assign(ctx: Context, work_id: str, name: str | None, agents: list[str]) -> None:
    """Record a ticket's worktree and the agents named on it; a ticket in no worktree is an assignment of its own,
    named by its id."""
    from .runtime import own
    with own(ctx).tables() as tx:
        if tx.get(TABLE, {'work_id': work_id}) is None:
            tx.insert(TABLE, {'work_id': work_id, 'worktree': name, 'agents': agents})
        else:
            tx.update(TABLE, {'work_id': work_id}, {'worktree': name, 'agents': agents})


def of(ctx: Context, work_ids: list[str]) -> dict[str, str]:
    """Each ticket's worktree, its own id when the composer put it in none."""
    from .runtime import own
    wanted = set(work_ids)
    with own(ctx).tables(write=False) as tx:
        found = {str(row['work_id']): str(row['worktree']) for row in tx.rows(TABLE, limit=0).results
                 if row['work_id'] in wanted and row['worktree']}
    return {work_id: found.get(work_id, work_id) for work_id in work_ids}


def agents_of(ctx: Context, work_ids: list[str]) -> dict[str, list[str]]:
    """The agent names on each ticket, in the order they were given; none when the ticket names nobody."""
    from .runtime import own
    wanted = set(work_ids)
    with own(ctx).tables(write=False) as tx:
        found = {str(row['work_id']): [str(one) for one in cast(list[Any], row['agents'] or [])]
                 for row in tx.rows(TABLE, limit=0).results if row['work_id'] in wanted}
    return {work_id: found.get(work_id, []) for work_id in work_ids}


def tickets(ctx: Context, name: str) -> list[str]:
    """The tickets the composer put in a worktree."""
    from .runtime import own
    with own(ctx).tables(write=False) as tx:
        return [str(row['work_id']) for row in tx.rows(TABLE, {'worktree': name}, limit=0).results]


def assigned(ctx: Context, name: str) -> bool:
    """Whether the composer put tickets in the worktree `name`: only then does a claim make the git worktree and Full
    Auto merge it. A ticket claimed by its own id is worked in the project folder."""
    return bool(tickets(ctx, name))


# ---------------------------------------------------------------------------------------------------- git

def git(folder: str | Path, *words: str, limit: float = 120) -> subprocess.CompletedProcess[str]:
    """One git command; a timeout or a missing git is a failed result with the reason, never an exception."""
    try:
        return subprocess.run(['git', *words], cwd=folder, capture_output=True, text=True, encoding='utf-8',
                              timeout=limit, check=False, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as error:
        return subprocess.CompletedProcess(['git', *words], 1, '', str(error))


def repository(folder: Path) -> bool:
    return git(folder, 'rev-parse', '--is-inside-work-tree').stdout.strip() == 'true'


def branch_of(name: str) -> str:
    return f'metaform/{name}'


def folder_of(project: Path, name: str) -> Path:
    return project / FOLDER / name


def create(project: Path, name: str) -> dict[str, Any]:
    """The worktree a claim makes, `.worktrees/<name>` on branch metaform/<name> from the checked-out HEAD; one already
    there is kept. A branch left from an earlier round is reused, never discarded, and the notice says when it has
    commits that are not in HEAD. A folder outside git has none: its pair works in the project folder."""
    if not repository(project):
        return {'worktree': name, 'folder': None, 'branch': None,
                'notice': 'The project folder is not a git repository; the pair works in it directly.'}
    if git(project, 'rev-parse', '--verify', '--quiet', 'HEAD').returncode:
        return {'worktree': name, 'folder': None, 'branch': None,
                'notice': 'The repository has no commit yet, so no worktree can branch from it; the pair works in the '
                          'project folder.'}
    folder, branch = folder_of(project, name), branch_of(name)
    _excluded(project)
    if folder.is_dir():
        return {'worktree': name, 'folder': str(folder), 'branch': branch}
    folder.parent.mkdir(parents=True, exist_ok=True)
    known = git(project, 'rev-parse', '--verify', '--quiet', f'refs/heads/{branch}').returncode == 0
    made = git(project, 'worktree', 'add', *([str(folder), branch] if known else ['-b', branch, str(folder)]))
    if made.returncode:
        raise Stop(f'git could not add the worktree {name}: {(made.stderr or made.stdout).strip()}',
                   'metaform tasks board')
    result: dict[str, Any] = {'worktree': name, 'folder': str(folder), 'branch': branch}
    if known and git(project, 'merge-base', '--is-ancestor', branch, 'HEAD').returncode:
        result['notice'] = (f'Branch {branch} has commits from an earlier round that are not in HEAD; this claim '
                            'reuses it, so the new work goes on top of them.')
    return result


def _excluded(project: Path) -> None:
    """`.worktrees/` kept out of the project's git status, through .git/info/exclude, so it is never committed."""
    found = git(project, 'rev-parse', '--git-path', 'info/exclude').stdout.strip()
    if not found:
        return
    excluded = project / found  # absolute when git says so, else relative to the project folder
    excluded.parent.mkdir(parents=True, exist_ok=True)
    held = excluded.read_text(encoding='utf-8') if excluded.exists() else ''
    if f'/{FOLDER}/' not in held:
        with excluded.open('a', encoding='utf-8') as written:
            written.write(('' if held.endswith('\n') or not held else '\n') + f'/{FOLDER}/\n')


def land(project: Path, name: str, message: str) -> dict[str, Any]:
    """Full Auto's close of a worktree: what it holds committed, its branch merged into the branch checked out in the
    project folder, and the worktree and branch removed. A merge git refuses is undone and the worktree left as it
    was, with git's words in the result; the tickets are closed either way."""
    folder, branch = folder_of(project, name), branch_of(name)
    if not repository(project) or not folder.is_dir():
        return {'merged': False, 'why': f'No worktree {name} to merge.'}
    if git(folder, 'status', '--porcelain').stdout.strip():
        git(folder, 'add', '-A')
        committed = git(folder, *_author(folder), 'commit', '-q', '-m', message)
        if committed.returncode:
            return {'merged': False, 'why': (committed.stderr or committed.stdout).strip()}
    into = git(project, 'symbolic-ref', '--quiet', '--short', 'HEAD').stdout.strip()
    if not into:
        return {'merged': False, 'why': 'The project folder has no branch checked out.'}
    if git(project, 'rev-parse', '--verify', '--quiet', 'MERGE_HEAD').returncode == 0:
        return {'merged': False, 'into': into, 'why': 'A merge is in progress in the project folder.'}
    merged = git(project, 'merge', '--no-edit', branch)
    if merged.returncode:
        git(project, 'merge', '--abort')
        return {'merged': False, 'into': into, 'why': (merged.stderr or merged.stdout).strip()}
    git(project, 'worktree', 'remove', '--force', str(folder))
    git(project, 'branch', '-D', branch)
    git(project, 'worktree', 'prune')
    return {'merged': True, 'into': into, 'commit': git(project, 'rev-parse', 'HEAD').stdout.strip()}


def _author(folder: Path) -> list[str]:
    """A commit identity for a repository that has none configured."""
    if git(folder, 'config', 'user.email').stdout.strip():
        return []
    return ['-c', 'user.name=Metaform', '-c', 'user.email=metaform@localhost']
