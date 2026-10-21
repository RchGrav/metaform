"""Worktrees and the review-or-merge flow, VIEW-044.

With `dispatch_worktrees` on, each ticket's agent works in a git worktree of its own, on a branch made from the active
dev branch. When its ticket is done, the worktree's changes are committed there, the project's test command is run in
it and git checks that the branch merges into the active dev branch with no conflict. When both pass, the merge waits
`dispatch_review_minutes` for a person's review; the web GUI shows Review. With no review by then, both checks run
again and the branch is merged into the active dev branch, and a ticket says the feature was merged without review and
needs testing before the next release. A person who clicks Review takes the merge over: the countdown is cancelled
and never restarts.

How its words are read here, recorded in VIEW-044 as interpretations: the merge check is git finding no conflicts;
"the tests clear" is the project's test command, `dispatch_test_command`, passing in the worktree, and with none set no
merge is ever offered; the active dev branch is the branch checked out in the project folder.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from metaform.data import Node, Store, WorkRecord

READY, REVIEW, MERGED, FAILED = 'ready', 'review', 'merged', 'failed'
PUSH_PENDING = 'push pending'
MERGING = 'merging'  # journaled: a merge under way, or left part way by one that died, `merge_due`
FOLDER = '.worktrees'  # inside the project folder, so an agent there reaches the project; kept out of git status
TRAILER = 'Metaform-Ticket'  # the git trailer every commit made for a ticket carries, P009
SNAPSHOTS = 'refs/metaform/snapshot'  # where the snapshot a ticket's worktree began from is kept, by its branch name
QUEUE = 'metaform-merge.lock'  # in the project's git folder: one merge at a time, P018
QUEUE_LIMIT = 600.0  # seconds a lock left by a merge that died is honoured before it is taken over


def git(folder: str | Path, *words: str, limit: float = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(['git', *words], cwd=folder, capture_output=True, text=True, encoding='utf-8',
                          timeout=limit, check=False, stdin=subprocess.DEVNULL)


def capture_state(folder: str | Path) -> dict[str, str]:
    """Dirty paths at session start. Their content belongs to an earlier writer."""
    found = git(folder, 'status', '--porcelain=v1', '-z', '--untracked-files=all', '--no-renames')
    if found.returncode:
        return {'': 'not a git checkout'}
    return {entry[3:]: file_fingerprint(folder, entry[3:])
            for entry in found.stdout.split('\0') if entry}


def file_fingerprint(folder: str | Path, name: str) -> str:
    """Content and mode prove that a successful edit has not since changed."""
    path = Path(folder) / name
    try:
        mode = path.lstat().st_mode
        content = os.readlink(path).encode('utf-8') if path.is_symlink() else path.read_bytes()
    except FileNotFoundError:
        return 'deleted'
    return hashlib.sha256(str(mode).encode('ascii') + b'\0' + content).hexdigest()


def ticket_title(store: Store, record: WorkRecord) -> str:
    address = record.address or record.receiver_address or record.provider_address or 'work'
    numbered = store.numbers_of('work', [record.id]).get(record.id)
    handle = numbered[0] if numbered else f'{address}#{record.id[:8]}'
    title = numbered[1] if numbered and numbered[1] else record.task or record.note or record.condition or 'Work'
    return f'{handle} {title}'.splitlines()[0]


def ticket_message(store: Store, record: WorkRecord, agent: str = '', name: str = '') -> str:
    """The completed ticket's lasting record, shared by direct commits and worktree squashes."""
    from . import agent_label
    address = record.address or record.receiver_address or record.provider_address or 'work'
    numbered = store.numbers_of('work', [record.id]).get(record.id)
    handle, title, why = numbered or (f'{address}#{record.id[:8]}', None, None)
    subject = (title or record.task or record.note or record.condition or 'Work').splitlines()[0]
    base = store.bound_base()
    with Store(store.project_id, base=base.id if base else None, module='map').tables(write=False) as tx:
        settings = tx.get('ticket_settings', {'work_id': record.id})
    board = str(settings['board'] or '') if settings else ''
    agent = agent or (record.taken_by or '').split(' ', 1)[0]
    author = ' '.join(part for part in (agent, name or (agent_label(agent) if agent else '')) if part)
    return '\n\n'.join((subject, record.resolution or '', f'Why: {why or ""}'.rstrip(), '\n'.join((
        f'{TRAILER}: {record.id}', f'Metaform-Number: {handle}', f'Metaform-Node: {address}',
        f'Metaform-Board: {board}'.rstrip(), f'Metaform-Agent: {author}'.rstrip()))))


def commit_fault(store: Store, record: WorkRecord, why: str) -> None:
    """A missing completion commit is one numbered broken ticket, which lights its board node."""
    node = Node('element', 'code.dispatcher.agent')
    numbered = store.numbers_of('work', [record.id]).get(record.id)
    handle = numbered[0] if numbered else record.id
    note = f'Completed ticket {handle} ({record.id}) has no commit.'
    with store.atomic():
        if any(other.note == note for other in store.work(node=node, open=True, limit=0).results):
            return
        fault = store.add_work(node, 'broken', kind='broken', title=f'Missing commit for {handle}', note=note,
                               task=f'{why}\nRecover the completed ticket commit without including peer edits. '
                                    f'Verify git log --fixed-strings --grep="{TRAILER}: {record.id}".')
        base = store.bound_base()
        own = Store(store.project_id, base=base.id if base else None, module='map')
        with own.tables() as tx:
            settings = tx.get('ticket_settings', {'work_id': record.id})
            if settings and settings['board']:
                tx.insert('ticket_settings', {'work_id': fault.id, 'board': settings['board']})


def _deliverable(path: str) -> bool:
    """Exclude runtime output, temporary files and diagnostic captures from ticket commits."""
    parts = Path(path).parts
    return bool(parts) and not any(part in ('.git', '.worktrees', '__pycache__', '.pytest_cache',
                                            'node_modules', '.venv', 'tmp', 'temp', 'diagnostics')
                                   for part in parts) and not path.endswith(('.log', '.tmp', '.pyc', '.bak', '~'))


def push_ticket(folder: str | Path) -> dict[str, Any]:
    try:
        return _push_ticket(folder)
    except (OSError, subprocess.SubprocessError) as exc:
        return {'pushed': False, 'conflict': False, 'why': f'Git push failed: {exc}'}


def _push_ticket(folder: str | Path) -> dict[str, Any]:
    """Push configured upstream. A rejected push fetches and merges, never rewrites history."""
    result: dict[str, Any] = {'pushed': False, 'conflict': False, 'why': ''}
    upstream = git(folder, 'rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{upstream}')
    if upstream.returncode:
        return result
    branch = dev_branch(folder)
    if branch is None:
        return result
    remote = git(folder, 'config', '--get', f'branch.{branch}.remote').stdout.strip()
    destination = git(folder, 'config', '--get', f'branch.{branch}.merge').stdout.strip()
    if not remote or not destination:
        return result
    pushed = git(folder, 'push', remote, f'HEAD:{destination}')
    if pushed.returncode == 0:
        result['pushed'] = True
        return result
    fetched = git(folder, 'fetch', remote)
    if fetched.returncode:
        result['why'] = (fetched.stdout + fetched.stderr).strip()[-400:]
        return result
    merged = git(folder, '-c', 'merge.autostash=false', 'merge', '--no-edit', '@{upstream}')
    if merged.returncode:
        result['conflict'] = _conflicting(folder, merged.stdout + merged.stderr)
        result['why'] = (merged.stdout + merged.stderr).strip()[-400:]
        if result['conflict']:
            git(folder, 'merge', '--abort')
        return result
    pushed = git(folder, 'push', remote, f'HEAD:{destination}')
    result['pushed'] = pushed.returncode == 0
    result['why'] = '' if result['pushed'] else (pushed.stdout + pushed.stderr).strip()[-400:]
    return result


def _reconcile_index(folder: Path, commit: str, files: dict[str, str]) -> str:
    """Refresh only ticket entries still at their pre-commit version, preserving later peer staging."""
    changed = git(folder, 'diff-tree', '--no-commit-id', '--name-only', '--no-renames', '-r', '-z', commit)
    if changed.returncode:
        return changed.stderr.strip()[-400:]
    owned: set[str] = set()
    for name in files:
        candidate = Path(name)
        try:
            relative = (candidate if candidate.is_absolute() else folder / candidate).relative_to(folder).as_posix()
        except ValueError:
            continue
        if '..' not in Path(relative).parts:
            owned.add(relative)
    refresh: list[str] = []
    for name in changed.stdout.split('\0'):
        if name not in owned:
            continue
        unchanged = git(folder, 'diff', '--cached', '--quiet', f'{commit}^', '--', name)
        if unchanged.returncode == 0:
            refresh.append(name)
        elif unchanged.returncode != 1:
            return unchanged.stderr.strip()[-400:]
    if not refresh:
        return ''
    reset = git(folder, 'reset', '-q', 'HEAD', '--', *refresh)
    return '' if reset.returncode == 0 else (reset.stdout + reset.stderr).strip()[-400:]


def complete_ticket(folder: str | Path, work_id: str, message: str, files: dict[str, str],
                    baseline: dict[str, str] | None) -> dict[str, Any]:
    """Commit only owned paths through a private index, preserving other staged and unstaged work.

    Ownership must be supplied by the runner. Dirty startup paths cannot be attributed safely,
    even if the session subsequently edits them. Missing startup evidence blocks shared commits.
    """
    result: dict[str, Any] = {'committed': None, 'pushed': False, 'conflict': False, 'why': ''}
    folder = Path(folder).resolve()
    trailer = f'{TRAILER}: {work_id}'
    previous = git(folder, 'log', '--format=%H', '--fixed-strings', '--grep', trailer)
    for commit in previous.stdout.splitlines():
        if git(folder, 'log', '-1', '--format=%B', commit).stdout.strip() == message.strip():
            result['committed'] = commit
            with Queued(folder) as held:
                if not held:
                    result['why'] = 'Another git operation is under way.'
                    return result
                result['why'] = _reconcile_index(folder, commit, files)
                if not result['why']:
                    result.update(push_ticket(folder))
            return result
    if baseline is not None and '' in baseline:
        result['why'] = 'The project folder is not a git checkout.'
        return result
    if files and baseline is None:
        result['why'] = 'Missing startup git state. Ticket files cannot be attributed safely.'
        return result
    paths: list[str] = []
    expected: dict[str, str] = {}
    dirty = capture_state(folder)
    for name, fingerprint in files.items():
        candidate = Path(name)
        if not candidate.is_absolute():
            candidate = folder / candidate
        try:
            relative = candidate.relative_to(folder).as_posix()
        except ValueError:
            continue
        if '..' in Path(relative).parts or not _deliverable(relative) or relative not in dirty:
            continue
        if file_fingerprint(folder, relative) != fingerprint:
            result['why'] = f'File changed after the session edit: {relative}'
            return result
        if baseline is not None and relative in baseline:
            result['why'] = f'Pre-existing changes prevent safe attribution: {relative}'
            return result
        if relative not in paths:
            paths.append(relative)
            expected[relative] = fingerprint
    with Queued(folder) as held:
        if not held:
            result['why'] = 'Another git operation is under way.'
            return result
        handle, index = tempfile.mkstemp(prefix='metaform-ticket-index-')
        os.close(handle)
        env = {**os.environ, 'GIT_INDEX_FILE': index}
        try:
            def staged(*words: str) -> subprocess.CompletedProcess[str]:
                return subprocess.run(['git', *words], cwd=folder, capture_output=True, text=True,
                                      encoding='utf-8', timeout=120, check=False,
                                      stdin=subprocess.DEVNULL, env=env)
            head = git(folder, 'rev-parse', 'HEAD').stdout.strip()
            for words in [('read-tree', head), *([('add', '-A', '--', *paths)] if paths else []),
                          ('diff', '--cached', '--check')]:
                done = staged(*words)
                if done.returncode:
                    result['why'] = (done.stdout + done.stderr).strip()[-400:]
                    return result
            for name, fingerprint in expected.items():
                if file_fingerprint(folder, name) != fingerprint:
                    result['why'] = f'File changed while preparing ticket commit: {name}'
                    return result
            tree = staged('write-tree')
            if tree.returncode:
                result['why'] = tree.stderr.strip()[-400:]
                return result
            made = git(folder, 'commit-tree', tree.stdout.strip(), '-p', head, '-m', message)
            if made.returncode:
                result['why'] = made.stderr.strip()[-400:]
                return result
            committed = made.stdout.strip()
            advanced = git(folder, 'update-ref', 'HEAD', committed, head)
            if advanced.returncode:
                result['why'] = 'Branch changed while preparing ticket commit.'
                return result
            result['committed'] = committed
            result['why'] = _reconcile_index(folder, committed, expected)
            if result['why']:
                return result
            result.update(push_ticket(folder))
            return result
        finally:
            Path(index).unlink(missing_ok=True)


def branch_of(work_id: str) -> str:
    return f'metaform/{work_id[:12]}'


def dev_branch(project: str | Path) -> str | None:
    """The active dev branch: the branch checked out in the project folder; none outside git or detached."""
    found = git(project, 'symbolic-ref', '--quiet', '--short', 'HEAD')
    return found.stdout.strip() or None if found.returncode == 0 else None


def snapshot(project: str | Path, work_id: str) -> str | None:
    """The project folder as it is now, committed on top of HEAD without touching the folder, its index or any
    branch, P009: tracked changes and untracked files that are not ignored, through a temporary index, write-tree and
    commit-tree. HEAD itself when nothing is uncommitted; None outside git."""
    head = git(project, 'rev-parse', '--verify', '--quiet', 'HEAD').stdout.strip()
    if not head:
        return None
    handle, index = tempfile.mkstemp(prefix='metaform-index-')
    os.close(handle)
    env = {**os.environ, 'GIT_INDEX_FILE': index}
    try:
        def staged(*words: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(['git', *words], cwd=project, capture_output=True, text=True, encoding='utf-8',
                                  timeout=120, check=False, stdin=subprocess.DEVNULL, env=env)
        if staged('read-tree', head).returncode != 0 or staged('add', '-A').returncode != 0:
            return head
        tree = staged('write-tree').stdout.strip()
    finally:
        with_index = Path(index)
        if with_index.exists():
            with_index.unlink()
    if not tree or tree == git(project, 'rev-parse', f'{head}^{{tree}}').stdout.strip():
        return head
    made = git(project, 'commit-tree', tree, '-p', head, '-m', f'Snapshot of uncommitted work for ticket {work_id}',
               '-m', f'{TRAILER}: {work_id}').stdout.strip()
    return made or head


def worktree_for(project: str | Path, work_id: str) -> Path | None:
    """The ticket's own worktree, made on first use on a branch from a snapshot of the project folder as it is, its
    uncommitted work with it, P009; the snapshot is kept under SNAPSHOTS, so a merge carries the agent's work alone.
    None when the project folder is not a git repository on a branch."""
    project = Path(project)
    dev = dev_branch(project)
    if dev is None:
        return None
    folder = project / FOLDER / work_id[:12]
    if (folder / '.git').exists():
        return folder
    excluded = project / '.git' / 'info' / 'exclude'
    if excluded.parent.is_dir() and f'/{FOLDER}/' not in (excluded.read_text(encoding='utf-8') if excluded.exists() else ''):
        with excluded.open('a', encoding='utf-8') as written:
            written.write(f'\n/{FOLDER}/\n')
    branch = branch_of(work_id)
    known = git(project, 'rev-parse', '--verify', '--quiet', branch).returncode == 0
    start = None if known else snapshot(project, work_id) or dev
    made = git(project, 'worktree', 'add', *([str(folder), branch] if known else ['-b', branch, str(folder), start or dev]))
    if made.returncode != 0:
        return None
    if start:
        git(project, 'update-ref', f'{SNAPSHOTS}/{branch}', start)
    return folder


def checkpoint(folder: str | Path, work_id: str, said: str, *, completed: bool = False) -> str | None:
    """Everything the agent has changed in its worktree committed, with the ticket's trailer, P009: the runner's own
    commit at each step and at the session's end, so nothing is lost on a crash. The commit, or None when nothing
    changed or the folder is not a worktree of the project's. A worktree's .git is a file; the project's own
    checkout, whose .git is a folder, is never committed here: 2026-10-15, a resumed session handed the shared checkout
    here and every agent's uncommitted work was committed under one ticket."""
    if not (Path(folder) / '.git').is_file():
        return None
    if completed and git(folder, 'log', '-1', '--format=%B').stdout.strip() == said.strip() \
            and not git(folder, 'status', '--porcelain').stdout.strip():
        return git(folder, 'rev-parse', 'HEAD').stdout.strip()
    if git(folder, 'add', '-A').returncode:
        return None
    if not completed and git(folder, 'diff', '--cached', '--quiet').returncode == 0:
        return None
    message = said if completed else f'{said[:200] or f"Checkpoint of ticket {work_id}"}\n\n{TRAILER}: {work_id}'
    done = git(folder, 'commit', '--allow-empty', '--cleanup=verbatim', '-q', '-m', message)
    return git(folder, 'rev-parse', 'HEAD').stdout.strip() if done.returncode == 0 else None


def snapshot_of(project: str | Path, branch: str) -> str | None:
    """The snapshot a branch's worktree began from, as worktree_for kept it; None for a branch made before."""
    found = git(project, 'rev-parse', '--verify', '--quiet', f'{SNAPSHOTS}/{branch}').stdout.strip()
    return found or None


def removed(project: str | Path, folder: str | Path, branch: str | None = None) -> None:
    """A ticket's worktree removed once its work is committed, P192; with a branch, that branch and its snapshot ref
    too, for work merged or abandoned."""
    git(project, 'worktree', 'remove', '--force', str(folder))
    if branch:
        git(project, 'branch', '-D', branch)
        git(project, 'update-ref', '-d', f'{SNAPSHOTS}/{branch}')
    git(project, 'worktree', 'prune')


def worktree_of(store: Store, work_id: str) -> Path:
    """The worktree of a merge under review, where its helping agent works."""
    own = Store(store.project_id, module='dispatch')
    with own.tables(write=False) as tx:
        row = tx.get('merges', {'work_id': work_id})
    if row is None:
        from metaform.module import Stop
        raise Stop(f'No merge of work {work_id} is known.', 'metaform dispatch merges')
    return Path(row['worktree'])


def clean_merge(project: str | Path, branch: str) -> tuple[bool, str]:
    """Whether the branch's own work merges into the active dev branch with no conflict, without touching either: the
    work since the snapshot its worktree began from, P009, or since the two branches parted."""
    dev = dev_branch(project)
    if dev is None:
        return False, 'the project folder is not on a branch'
    began = snapshot_of(project, branch)
    found = git(project, 'merge-tree', '--write-tree', *(['--merge-base', began] if began else []), dev, branch)
    if found.returncode in (0, 1) and 'unknown' not in found.stderr and 'usage' not in found.stderr:
        # git 2.38 and later: 1 means conflicts
        return found.returncode == 0, '' if found.returncode == 0 else (found.stdout + found.stderr).strip()[-400:]
    # An earlier git: the trivial three-way merge-tree prints conflict markers where the two sides clash.
    base = began or git(project, 'merge-base', dev, branch).stdout.strip()
    if not base:
        return False, f'{branch} and {dev} share no history'
    shown = git(project, 'merge-tree', base, dev, branch).stdout
    clashing = [line for line in shown.splitlines() if line.startswith('+<<<<<<<')]
    return not clashing, '' if not clashing else f'{len(clashing)} conflicting part(s) between {branch} and {dev}'


def tests_pass(folder: str | Path, command: str) -> tuple[bool, str]:
    """Whether the project's test command passes in this folder; with none set, the tests cannot clear."""
    if not command.strip():
        return False, 'no test command is set: metaform set --dispatch-test-command "<command>"'
    try:
        done = subprocess.run(command, cwd=folder, shell=True, capture_output=True, text=True, encoding='utf-8',
                              timeout=3600, check=False, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return False, 'the tests took more than an hour'
    return done.returncode == 0, (done.stdout + done.stderr).strip()[-400:]


def finished(ctx: Any, store: Store, record: WorkRecord, folder: Path) -> dict[str, Any] | None:
    """A done ticket's worktree: its changes committed with the ticket's trailer, then, for a ticket completed, the
    tests and the merge check run, and when both pass the merge waits for review. A ticket cancelled or failed is not
    offered: uncommitted work stays in its worktree without another commit, P192, until
    dispatch_abandoned_branch_days have passed, P017. Returns the merge row, or None when there is nothing to merge."""
    project = Path(store.project().path)
    if not (Path(folder) / '.git').is_file() or Path(folder).resolve() == project.resolve():
        return None  # not a worktree: the shared checkout is neither committed nor removed, as checkpoint
    branch = branch_of(record.id)
    if (record.outcome or 'completed') != 'completed':
        if not git(folder, 'status', '--porcelain').stdout.strip():
            removed(project, folder)
        return None
    try:
        committed = checkpoint(folder, record.id, ticket_message(store, record), completed=True)
    except (OSError, subprocess.SubprocessError) as error:
        commit_fault(store, record, str(error))
        return None
    if committed is None:
        commit_fault(store, record, 'Git could not commit the completed worktree ticket.')
        return None
    dev = dev_branch(project)
    since = snapshot_of(project, branch) or dev
    if dev is None or git(project, 'rev-list', '--count', f'{since}..{branch}').stdout.strip() in ('', '0'):
        return None
    passed, said = tests_pass(folder, str(ctx.setting('dispatch_test_command')))
    merges, why = clean_merge(project, branch) if passed else (False, said)
    row = {'work_id': record.id, 'branch': branch, 'worktree': str(folder),
           'state': READY if passed and merges else FAILED, 'reason': '' if passed and merges else why,
           'ready': time.time(), 'deadline': time.time() + 60 * int(ctx.setting('dispatch_review_minutes')),
           'seq': time.time_ns()}
    own = Store(store.project_id, module='dispatch')
    with own.tables() as tx:
        if tx.update('merges', {'work_id': record.id}, row) is None:
            tx.insert('merges', row)
    return row


def in_force(store: Store, work_id: str) -> bool:
    """Whether a ticket's work is in the project folder: it has no worktree of its own, which its merge removes, and no
    merge of it waits."""
    if (Path(store.project().path) / FOLDER / work_id[:12] / '.git').exists():
        return False
    own = Store(store.project_id, module='dispatch')
    with own.tables(write=False) as tx:
        row = tx.get('merges', {'work_id': work_id})
    return row is None or row['state'] == MERGED


def due(store: Store) -> list[dict[str, Any]]:
    """The merges waiting for review, the soonest first, with any a merge left part way, `merging`, whose deadline is
    past, so the next check finishes it."""
    own = Store(store.project_id, module='dispatch')
    with own.tables(write=False) as tx:
        rows = [dict(row) for state in (READY, MERGING, MERGED)
                for row in tx.rows('merges', {'state': state}, limit=0).results
                if state != MERGED or row['reason'] == PUSH_PENDING]
    return sorted(rows, key=lambda row: row['deadline'])


def review(store: Store, work_id: str) -> bool:
    """The person takes the merge over: the countdown is cancelled for good."""
    own = Store(store.project_id, module='dispatch')
    with own.tables() as tx:
        row = tx.get('merges', {'work_id': work_id})
        if row is None or row['state'] != READY:
            return False
        tx.update('merges', {'work_id': work_id}, {'state': REVIEW})
        return True


class Queued:
    """One merge at a time in a project, P018: a lock file in the project's git folder naming the process that holds
    it, taken over at once when that process is gone, and otherwise once it is older than QUEUE_LIMIT, as a lock left
    by a merge from code before it named its process. A merge killed part way so leaves no ten-minute block on every
    other merge (UX review round 1, interrupt F7)."""

    def __init__(self, project: Path) -> None:
        found = git(project, 'rev-parse', '--git-common-dir').stdout.strip()
        self.path = (project / found if found else project / '.git') / QUEUE
        self.held = False

    def _left(self) -> bool:
        """Whether the lock there was left by a merge that is no longer running."""
        try:
            said = self.path.read_text(encoding='utf-8').strip()
            if said.isdigit():
                return not _alive(int(said))
            return time.time() - self.path.stat().st_mtime >= QUEUE_LIMIT
        except OSError:
            return False

    def __enter__(self) -> bool:
        for _ in range(2):
            try:
                handle = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                try:
                    os.write(handle, str(os.getpid()).encode('ascii'))
                finally:
                    os.close(handle)
                self.held = True
                return True
            except FileExistsError:
                if not self._left():
                    return False
                try:
                    self.path.unlink()
                except OSError:
                    return False
            except OSError:
                return False
        return False

    def __exit__(self, *_: object) -> None:
        if self.held:
            try:
                self.path.unlink()
            except OSError:
                pass


def _alive(pid: int) -> bool:
    if pid == os.getpid():
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:  # it exists, as another user's, or the platform cannot say: taken as alive
        return True
    return True


def merging_branch(work_id: str) -> str:
    """The branch a merge is made on, beside the agent's own, which a merge never moves."""
    return f'metaform-merging/{work_id[:12]}'


def merging_folder(project: Path, work_id: str) -> Path:
    return project / FOLDER / f'merging-{work_id[:12]}'


def _dropped(project: Path, work_id: str) -> None:
    """A merge's own worktree and branch removed, whatever state it was left in: a rebase stopped part way included."""
    folder = merging_folder(project, work_id)
    if folder.exists():
        git(project, 'worktree', 'remove', '--force', str(folder))
    git(project, 'worktree', 'prune')
    if git(project, 'rev-parse', '--verify', '--quiet', merging_branch(work_id)).returncode == 0:
        git(project, 'branch', '-D', merging_branch(work_id))


def _conflicting(folder: str | Path, said: str) -> bool:
    """Whether a rebase that failed stopped on a genuine conflict, rather than on git refusing for another reason."""
    unmerged = git(folder, 'diff', '--name-only', '--diff-filter=U').stdout.strip()
    return bool(unmerged) or 'CONFLICT' in said


RELEASE = 'Newly committed feature, needs testing before the next release: '  # the release log ticket's task, VIEW-044


def _logged(ctx: Any, store: Store, work_id: str, dev: str, branch: str) -> None:
    """The release log of a merge made without review, VIEW-044: a ticket held in Backlog, so no agent starts it by
    itself and a merged ticket never writes and starts its own successor (UX review round 1, runaway F5). Written once,
    though a merge resumed after a crash comes here again; a merge of a release log's own ticket writes none."""
    record = store.ticket(work_id).work
    if (record.task or '').startswith(RELEASE):
        return
    note = f'Merged into {dev} without review, from {branch}, after its tests passed: work {work_id}.'
    if any(other.note == note for other in store.work(open=None, limit=0).results):
        return
    store.add_work(Node.of(record.node_kind, record.node_id), None, note=note, held=True,
                   task=f'{RELEASE}{record.task or record.note or work_id}')


def merge_due(ctx: Any, store: Store, work_id: str) -> dict[str, Any]:
    """At the deadline, with no review, one merge at a time, P018 and P011: the branch's own work, since the snapshot it
    began from, rebased onto the active dev branch in a worktree of the merge's own, on a branch of its own, the tests
    run there again, squashed into one commit with the ticket's trailer, and the dev branch fast-forwarded to it, which
    only a folder with no uncommitted change to a tracked file takes; then the worktrees, the branches and the snapshot
    are removed, P192, and the held ticket that says the feature needs testing before the next release is written.
    Anything that no longer passes is not merged; a folder with uncommitted changes, or another merge under way, leaves
    it waiting.

    The agent's branch and worktree are never moved, and the merge is journaled: its row reads `merging` from before
    the first git step to the last. A merge killed part way is found so on the next call, under the queue's lock, so it
    is not still running: when the dev branch already holds its commit it is finished, and otherwise its own worktree
    and branch are dropped and it is made again from the agent's branch as it was. Only a genuine conflict is said
    with `conflict:` (UX review round 1, interrupt F7: a merge killed after its soft reset left the agent's work only
    staged, and the next attempt reported a conflict that did not exist)."""
    from . import work_over
    own = Store(store.project_id, module='dispatch')
    with own.tables(write=False) as tx:
        row = tx.get('merges', {'work_id': work_id})
    if row is not None and row['state'] == MERGED:
        return _delivered(ctx, store, own, Path(store.project().path), work_id)
    if row is None or row['state'] not in (READY, MERGING):
        return {'work_id': work_id, 'merged': False, 'why': 'not waiting'}
    row = dict(row)
    project = Path(store.project().path)
    folder, branch = str(row['worktree']), str(row['branch'])
    with Queued(project) as first:
        if not first:
            return {'work_id': work_id, 'merged': False, 'why': 'another merge is under way; this one waits'}
        dev = dev_branch(project)
        if dev is None:
            return {'work_id': work_id, 'merged': False, 'why': 'the project folder is not on a branch'}
        temp, here = merging_branch(work_id), merging_folder(project, work_id)
        if row['state'] == MERGING:  # left part way by a merge that died: finish it, or begin it again
            # the dev branch holds its squashed commit when the merge's own branch is a commit of this ticket's, by its
            # trailer, that dev has: only the fast-forward puts one there
            made = git(project, 'rev-parse', '--verify', '--quiet', temp).stdout.strip()
            ours = bool(made) and f'{TRAILER}: {work_id}' in git(project, 'log', '-1', '--format=%B', made).stdout
            if ours and git(project, 'merge-base', '--is-ancestor', made, dev).returncode == 0:
                return _merged(ctx, store, own, project, work_id, dev, folder, branch)
            _dropped(project, work_id)
            with own.tables() as tx:
                tx.update('merges', {'work_id': work_id}, {'state': READY, 'reason': ''})
        record = store.ticket(work_id).work
        if record.outcome in ('cancelled', 'failed') or not work_over(store, record):
            with own.tables() as tx:
                tx.update('merges', {'work_id': work_id}, {'state': FAILED, 'reason': 'ticket is not completed'})
            return {'work_id': work_id, 'merged': False, 'why': 'ticket is not completed'}
        if git(project, 'status', '--porcelain', '--untracked-files=no').stdout.strip():
            return {'work_id': work_id, 'merged': False,
                    'why': 'the project folder has uncommitted changes; the merge waits until they are committed'}
        passed, why = clean_merge(project, branch)
        outcome: dict[str, Any] = {'state': FAILED, 'reason': why}
        began = ''
        if passed:
            with own.tables() as tx:  # the journal: from here to the end the merge reads `merging`
                tx.update('merges', {'work_id': work_id}, {'state': MERGING, 'reason': ''})
            _dropped(project, work_id)
            began = snapshot_of(project, branch) or git(project, 'merge-base', dev, branch).stdout.strip()
            made = git(project, 'worktree', 'add', '-b', temp, str(here), branch)
            if made.returncode != 0:
                outcome['reason'] = 'git: ' + (made.stdout + made.stderr).strip()[-400:]
                passed = False
        if passed:
            moved = git(here, 'rebase', '--onto', dev, began)
            if moved.returncode != 0:
                said = (moved.stdout + moved.stderr).strip()
                outcome['reason'] = ('conflict: ' if _conflicting(here, said) else 'git: ') + said[-400:]
                git(here, 'rebase', '--abort')
                passed = False
        if passed:
            passed, said = tests_pass(here, str(ctx.setting('dispatch_test_command')))
            outcome['reason'] = said
        if passed:
            record = store.ticket(work_id).work
            if record.outcome in ('cancelled', 'failed') or not work_over(store, record):
                passed = False
                outcome['reason'] = 'ticket is not completed'
        if passed:
            git(here, 'reset', '--soft', dev)
            squashed = git(here, 'commit', '--allow-empty', '--cleanup=verbatim', '-q', '-m',
                           ticket_message(store, record))
            done = git(project, 'merge', '--ff-only', temp) if squashed.returncode == 0 else squashed
            if done.returncode == 0:
                return _merged(ctx, store, own, project, work_id, dev, folder, branch)
            outcome['reason'] = 'git: ' + (done.stdout + done.stderr).strip()[-400:]
        _dropped(project, work_id)
    with own.tables() as tx:
        tx.update('merges', {'work_id': work_id}, outcome)
    return {'work_id': work_id, 'merged': False, 'why': outcome['reason']}


def _merged(ctx: Any, store: Store, own: Store, project: Path, work_id: str, dev: str, folder: str,
            branch: str) -> dict[str, Any]:
    """The end of a merge whose commit the dev branch holds: its release log written, its worktrees, branches and
    snapshot removed, and its row merged, each step safe to run again."""
    _logged(ctx, store, work_id, dev, branch)
    _dropped(project, work_id)
    removed(project, folder, branch)
    with own.tables() as tx:
        tx.update('merges', {'work_id': work_id}, {'state': MERGED, 'reason': PUSH_PENDING})
    return _delivered(ctx, store, own, project, work_id)


def _delivered(ctx: Any, store: Store, own: Store, project: Path, work_id: str) -> dict[str, Any]:
    """A committed merge's pending push survives crashes. Explicit retries never repeat its squash."""
    pushed = push_ticket(project)
    if pushed['why']:
        from .orchestration import TRANSPORT
        try:
            record = store.ticket(work_id).work
            TRANSPORT.notify_user(ctx, {'text': f'{ticket_title(store, record)}: {pushed["why"]}',
                                        'work_id': work_id, 'kind': 'ticket-commit', 'state': 'blocked'},
                                  f'ticket-commit:{work_id}')
        except Exception as exc:  # noqa: BLE001  notification failure cannot undo a completed merge
            print(f'Ticket push notification failed: {exc}', file=sys.stderr)
    with own.tables() as tx:
        tx.update('merges', {'work_id': work_id}, {'reason': pushed['why']})
    return {'work_id': work_id, 'merged': True, **pushed}


def abandoned(store: Store, project: str | Path, days: int) -> list[str]:
    """The branches of tickets closed and not merged, older than `days`, removed with their worktrees and snapshots,
    P017, without committing cancelled or failed work; git's record of worktrees gone is pruned, P192."""
    project = Path(project)
    if dev_branch(project) is None:
        return []
    git(project, 'worktree', 'prune')
    listed = git(project, 'for-each-ref', '--format=%(refname:short) %(committerdate:unix)', 'refs/heads/metaform/')
    own = Store(store.project_id, module='dispatch')
    with own.tables(write=False) as tx:
        waiting = {str(row['branch']) for row in tx.rows('merges', limit=0).results if row['state'] in (READY, REVIEW, MERGING)}
    closed = {branch_of(record.id): record for record in store.work(open=False, limit=0).results}
    gone: list[str] = []
    for line in listed.stdout.splitlines():
        branch, _, when = line.partition(' ')
        if branch in waiting or branch not in closed or time.time() - float(when or 0) < days * 86400:
            continue
        folder = project / FOLDER / branch.split('/', 1)[1]
        removed(project, folder, branch)
        gone.append(branch)
    return gone
