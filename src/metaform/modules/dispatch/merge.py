"""Save ticket commits. Full Auto integrates locally. Publication requires an explicit request.

Only the delta from the recorded ticket start is merged. Legacy startup snapshots and
shared uncommitted files never enter the feature commit. Merge journals recover interrupted
delivery without rewriting either branch. Explicit legacy reviews remain under human control.
"""
from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from metaform.data import Node, Store, WorkRecord

READY, REVIEW, MERGED, FAILED = 'ready', 'review', 'merged', 'failed'
COMMITTED = 'committed'
PUSH_PENDING = 'push pending'
MERGING = 'merging'  # journaled: a merge under way, or left part way by one that died, `merge_due`
FOLDER = '.worktrees'  # inside the project folder, so an agent there reaches the project; kept out of git status
TRAILER = 'Metaform-Ticket'  # the git trailer every commit made for a ticket carries, P009
SNAPSHOTS = 'refs/metaform/snapshot'  # ticket starting commits, including snapshots made by older versions
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
    target = f'{record.node_kind}:{address if record.node_kind == "element" else record.node_id}'
    snapshot = f'Ticket state:\n{store.work_snapshot(record.id)}'
    return '\n\n'.join((subject, record.resolution or '', f'Why: {why or ""}'.rstrip(), snapshot, '\n'.join((
        f'Metaform-Target: {target}',
        f'{TRAILER}: {record.id}', f'Metaform-Number: {handle}', f'Metaform-Node: {address}',
        f'Metaform-Board: {board}'.rstrip(), f'Metaform-Agent: {author}'.rstrip()))))


def repository(folder: str | Path) -> bool:
    """Whether the folder is inside a git repository: only there can a completed ticket have a commit to miss."""
    return git(folder, 'rev-parse', '--is-inside-work-tree', limit=20).returncode == 0


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
        if git(folder, 'log', '-1', '--format=%B', commit).stdout.strip() == message.strip() \
                and (not files or ((baseline is None or git(folder, 'diff', '--quiet', commit, '--', *files).returncode == 0)
                     and not git(folder, 'ls-files', '--others', '--exclude-standard', '-z', '--', *files).stdout)):
            result['committed'] = commit
            with Queued(folder) as held:
                if not held:
                    result['why'] = 'Another git operation is under way.'
                    return result
                result['why'] = _reconcile_index(folder, commit, files)
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
            return result
        finally:
            Path(index).unlink(missing_ok=True)


def branch_of(work_id: str) -> str:
    return f'metaform/{work_id[:12]}'


def dev_branch(project: str | Path) -> str | None:
    """The active dev branch: the branch checked out in the project folder; none outside git or detached."""
    found = git(project, 'symbolic-ref', '--quiet', '--short', 'HEAD')
    return found.stdout.strip() or None if found.returncode == 0 else None


def _branch_worktree(project: Path, branch: str) -> Path | None:
    """The registered location of a branch, independent of the first card that used its directory."""
    listed = git(project, 'worktree', 'list', '--porcelain')
    for block in listed.stdout.split('\n\n') if not listed.returncode else ():
        lines = block.splitlines()
        if f'branch refs/heads/{branch}' in lines:
            return next((Path(line[9:]) for line in lines if line.startswith('worktree ')), None)
    return None


def episode_workspace(project: str | Path, work_id: str, folder: str | Path,
                      previous_work_id: str) -> dict[str, str] | None:
    """Prepare a clean retained cwd for a new card without changing ACP's saved session cwd.

    Each card keeps a frozen branch and its own start snapshot. Integrated source work starts from current dev;
    otherwise its exact candidate remains the new card's baseline and is returned as an explicit source reference.
    A dirty, foreign or occupied workspace is left intact for the normal fresh-context path.
    """
    project, folder = Path(project).resolve(), Path(folder).resolve()
    if folder == project or not (folder / '.git').is_file() or not folder.is_relative_to(project / FOLDER):
        return None
    common = git(folder, 'rev-parse', '--path-format=absolute', '--git-common-dir')
    root_common = git(project, 'rev-parse', '--path-format=absolute', '--git-common-dir')
    if common.returncode or root_common.returncode or common.stdout.strip() != root_common.stdout.strip():
        return None
    source_branch, branch = branch_of(previous_work_id), branch_of(work_id)
    if dev_branch(folder) not in (source_branch, branch):
        return None
    dirty = git(folder, 'status', '--porcelain', '--untracked-files=all')
    if dirty.returncode or dirty.stdout.strip():
        return None
    source = git(project, 'rev-parse', '--verify', '--quiet', source_branch)
    current = git(project, 'rev-parse', '--verify', '--quiet', 'HEAD')
    if source.returncode or current.returncode:
        return None
    source_head, current_head = source.stdout.strip(), current.stdout.strip()
    used = _branch_worktree(project, branch)
    if used is not None and used.resolve() != folder:
        return None
    known = git(project, 'rev-parse', '--verify', '--quiet', branch).returncode == 0
    if known:
        start = snapshot_of(project, branch)
        if not start:
            return None
    else:
        integrated = git(project, 'merge-base', '--is-ancestor', source_head, current_head).returncode == 0
        start = current_head if integrated else source_head
        saved = git(project, 'update-ref', f'{SNAPSHOTS}/{branch}', start)
        if saved.returncode:
            return None
    changed = git(folder, 'switch', '--no-overwrite-ignore',
                  *([branch] if known else ['-c', branch, start]))
    if changed.returncode:
        return None
    return {'cwd': str(folder), 'branch': branch, 'baseline': start,
            'source_candidate': source_head, 'source_branch': source_branch}


def worktree_for(project: str | Path, work_id: str) -> Path | None:
    """The ticket's own worktree, branched from committed HEAD without copying shared uncommitted files.
    The starting commit is kept under SNAPSHOTS so merges also support older branches based on dirty snapshots.
    None when the project folder is not a git repository on a branch."""
    project = Path(project)
    dev = dev_branch(project)
    if dev is None:
        return None
    branch = branch_of(work_id)
    registered = _branch_worktree(project, branch)
    if registered is not None:
        return registered if registered.is_dir() else None
    folder = project / FOLDER / work_id[:12]
    if folder.exists():
        # An episode may still own the first card's stable ACP cwd on a later card's branch.
        suffix = 1
        while (folder := project / FOLDER / f'{work_id[:12]}-{suffix}').exists():
            suffix += 1
    excluded = project / '.git' / 'info' / 'exclude'
    if excluded.parent.is_dir() and f'/{FOLDER}/' not in (excluded.read_text(encoding='utf-8') if excluded.exists() else ''):
        with excluded.open('a', encoding='utf-8') as written:
            written.write(f'\n/{FOLDER}/\n')
    known = git(project, 'rev-parse', '--verify', '--quiet', branch).returncode == 0
    start = None if known else git(project, 'rev-parse', '--verify', '--quiet', 'HEAD').stdout.strip() or dev
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


def landing_base(project: str | Path, dev: str, branch: str) -> str:
    """The base a ticket branch lands from: its recorded start, which keeps a legacy dirty snapshot out of the delta,
    P009, unless the branch has merged the dev branch since, when their merge-base is later than that start and
    holds no snapshot, so a three-way merge from it finds only the ticket's own changes; with no recorded start, the
    merge-base. A start kept as the base after the branch merged dev found dev's own changes on both sides and
    reported conflicts the branch had already resolved (2026-10-21)."""
    base = git(project, 'merge-base', dev, branch).stdout.strip()
    began = snapshot_of(project, branch)
    if not began:
        return base
    if base and began != base and git(project, 'merge-base', '--is-ancestor', began, base).returncode == 0:
        return base
    return began

def snapshot_of(project: str | Path, branch: str) -> str | None:
    """The recorded starting commit, or legacy dirty snapshot; None for branches without a recorded start."""
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


def verification(ctx: Any, folder: Path, record: WorkRecord) -> dict[str, Any]:
    """Keep the configured check, or the worker's submitted verification report, with its candidate."""
    command = str(ctx.setting('dispatch_test_command') or '').strip()
    passed, output = tests_pass(folder, command) if command else (bool(record.resolution), '')
    return {'passed': passed, 'command': command, 'output': output,
            'source': 'command' if command else 'worker', 'report': record.resolution or ''}


def verify_commit(ctx: Any, folder: Path, record: WorkRecord, commit: str) -> dict[str, Any]:
    """Run configured checks on the saved tree, excluding mutable checkout and peer changes."""
    if not str(ctx.setting('dispatch_test_command') or '').strip():
        return verification(ctx, folder, record)
    with tempfile.TemporaryDirectory(prefix='metaform-verify-') as temporary:
        candidate = Path(temporary) / 'candidate'
        added = git(folder, 'worktree', 'add', '--detach', str(candidate), commit)
        if added.returncode:
            return {'passed': False, 'command': str(ctx.setting('dispatch_test_command')),
                    'output': added.stderr.strip(), 'source': 'command', 'report': record.resolution or ''}
        try:
            return verification(ctx, candidate, record)
        finally:
            git(folder, 'worktree', 'remove', '--force', str(candidate))


def _saved(store: Store, record: WorkRecord, folder: Path, branch: str, commit: str | None,
           checked: dict[str, Any], since: str = '', *, repository_present: bool = True) -> dict[str, Any]:
    """Retain delivery evidence separately from ticket closure."""
    own = Store(store.project_id, module='dispatch')
    artifacts: list[str] = []
    if commit:
        changed = git(folder, 'diff', '--name-only', '-z', since, commit) if since else git(
            folder, 'diff-tree', '--no-commit-id', '--name-only', '--root', '-r', '-z', commit)
        artifacts = [path for path in changed.stdout.split('\0') if path]
    reason = '' if checked['passed'] else str(checked['output'] or 'Ticket verification failed.')
    row = {'work_id': record.id, 'branch': branch, 'worktree': str(folder),
           'state': COMMITTED if checked['passed'] else FAILED, 'reason': reason, 'head': commit,
           'evidence': {'repository': repository_present, 'verification': checked, 'artifacts': artifacts},
           'ready': time.time(), 'deadline': time.time(), 'seq': time.time_ns()}
    with own.tables() as tx:
        if tx.update('merges', {'work_id': record.id}, row) is None:
            tx.insert('merges', row)
        tx.concern(work_id=record.id, kind='ticket')
    if checked['passed']:
        store.complete_delivery(record.id)
    return row


def finished(ctx: Any, store: Store, record: WorkRecord, folder: Path) -> dict[str, Any] | None:
    """Save a feature commit, recording checks and integrating locally under Full Auto."""
    from . import work_over
    project = Path(store.project().path)
    folder = Path(folder)
    if not (folder / '.git').is_file() or folder.resolve() == project.resolve():
        return None
    if record.outcome in ('cancelled', 'failed') or not work_over(store, record):
        return None
    branch = dev_branch(folder)
    if branch is None:
        return None
    own = Store(store.project_id, module='dispatch')
    with own.tables(write=False) as tx:
        previous = tx.get('merges', {'work_id': record.id})
    with Store(store.project_id, module='map').tables(write=False) as tx:
        settings = tx.get('ticket_settings', {'work_id': record.id})
    landed = str(settings['landed'] or '') if settings else ''
    fresh = previous is not None and (not landed or float(previous['ready']) >= datetime.fromisoformat(landed).timestamp())
    if fresh and previous is not None and previous['state'] in (COMMITTED, MERGED) and previous['evidence'] \
            and not previous['reason'] and git(folder, 'rev-parse', 'HEAD').stdout.strip() == previous['head'] \
            and not git(folder, 'status', '--porcelain').stdout.strip():
        store.complete_delivery(record.id)
        return dict(previous)
    checked = verification(ctx, folder, record)
    try:
        committed = checkpoint(folder, record.id, ticket_message(store, record), completed=True)
    except (OSError, subprocess.SubprocessError) as error:
        commit_fault(store, record, str(error))
        return None
    if committed is None:
        commit_fault(store, record, 'Git could not commit the completed worktree ticket.')
        return None
    since = snapshot_of(project, branch) or ''
    return _saved(store, record, folder, branch, committed, checked, since)


def in_force(store: Store, work_id: str) -> bool:
    """Whether delivery is recorded and the fault's source has loaded the changed code."""
    own = Store(store.project_id, module='dispatch')
    with own.tables(write=False) as tx:
        row = tx.get('merges', {'work_id': work_id})
    if row is not None:
        evidence = row['evidence']
        if isinstance(evidence, dict) and cast(dict[str, Any], evidence).get('repository') is False:
            return row['state'] == COMMITTED and not row['reason']
        if row['state'] != MERGED or row['reason']:
            return False
        from .activation import in_force as active
        return active(store, work_id)
    return not (Path(store.project().path) / FOLDER / work_id[:12] / '.git').exists()


def due(store: Store) -> list[dict[str, Any]]:
    """The merges waiting for review, the soonest first, with any a merge left part way, `merging`, whose deadline is
    past, so the next check finishes it."""
    own = Store(store.project_id, module='dispatch')
    with own.tables(write=False) as tx:
        rows = [dict(row) for state in (READY, MERGING)
                for row in tx.rows('merges', {'state': state}, limit=0).results]
    return sorted(rows, key=lambda row: row['deadline'])


def review(store: Store, work_id: str) -> bool:
    """The person takes an existing pending integration under explicit review."""
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


def advance(project: Path, commit: str, before: str, *, ctx: Any = None, work_id: str = '',
            require_applied: bool = False) -> tuple[bool, str]:
    """Advance the checked-out branch from `before` to `commit` while keeping every local edit in the project
    checkout, staged or not: helpers and the person work there, and on another project it is the person's own working
    copy, so a landing never refuses for it (the person's rule, 2026-10-21). A path the landing changes is taken as
    landed when the checkout has it clean; a locally modified path takes the landed hunks by a three-way merge into
    its working copy and, when staged, into its index entry; a path whose local edits clash with the landed hunks is
    left exactly as it was and named: in the report, and, given `ctx`, as one board-needs line for the system agent,
    so the person merges it by hand while the ticket stays closed. The compare-and-swap on the ref refuses a
    concurrent advance. Recoverable failures restore each changed path and index entry to its pre-call state.
    """
    if git(project, 'rev-parse', 'HEAD').stdout.strip() != before:
        return False, 'the project branch changed during delivery; retry the merge'
    listed = git(project, 'diff', '--name-status', '--no-renames', '-z', before, commit)
    if listed.returncode:
        return False, (listed.stdout + listed.stderr).strip()[-1200:]
    parts = listed.stdout.split('\0')
    changes = [(parts[at], parts[at + 1]) for at in range(0, len(parts) - 1, 2)]
    changed: list[tuple[str, list[str], bytes | None, int]] = []
    kept: list[str] = []  # paths left as they were: their local edits clash with the landed hunks
    try:
        for status, path in changes:
            file = project / path
            mode = file.lstat().st_mode if file.exists() or file.is_symlink() else 0
            entries = [item for item in git(project, 'ls-files', '-s', '-z', '--', path).stdout.split('\0') if item]
            entry = entries[0].partition('\t')[0].split() if len(entries) == 1 else ['unmerged'] if entries else []
            shown = git(project, 'ls-tree', commit, '--', path).stdout.split()
            if any((project / parent).is_symlink() for parent in Path(path).parents if parent != Path('.')) \
                    or mode and not stat.S_ISREG(mode) \
                    or entry and (len(entry) != 3 or entry[2] != '0') \
                    or shown and shown[0] not in ('100644', '100755'):
                kept.append(path)
                continue
            content = file.read_bytes() if mode else None
            local = git(project, 'status', '--porcelain', '-z', '--untracked-files=all', '--', path).stdout
            if content is not None and not entry:
                local = local or 'untracked local file'
            changed.append((path, entry, content, mode))
            if not local:
                took = git(project, 'rm', '-q', '--', path) if status == 'D' else git(project, 'checkout', commit, '--', path)
                if took.returncode:
                    _restore_landing(project, changed)
                    return False, (took.stdout + took.stderr).strip()[-1200:]
            elif not _landed(project, status, path, before, commit):
                changed.pop()
                kept.append(path)
    except (OSError, subprocess.SubprocessError) as error:
        _restore_landing(project, changed)
        return False, str(error)
    if kept and require_applied:
        _restore_landing(project, changed)
        return False, 'Local edits conflict with ticket changes: ' + ', '.join(kept)
    branch = dev_branch(project)
    moved = git(project, 'update-ref', f'refs/heads/{branch}', commit, before)
    if moved.returncode:
        _restore_landing(project, changed)
        return False, (moved.stdout + moved.stderr).strip()[-1200:]
    if not kept:
        return True, ''
    report = 'kept as they were, their local edits clash with the landed hunks: ' + ', '.join(kept)
    if ctx is None:
        print(f'Landing {commit[:12]}: {report}', file=sys.stderr)
    else:
        _reported(ctx, work_id, commit, kept)
    return True, report


def _restore_landing(project: Path, changed: list[tuple[str, list[str], bytes | None, int]]) -> None:
    """Restore only paths and index entries changed by this attempted integration."""
    for path, entry, content, mode in reversed(changed):
        file = project / path
        if content is None:
            file.unlink(missing_ok=True)
        else:
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(content)
            file.chmod(stat.S_IMODE(mode))
        if entry:
            git(project, 'update-index', '--add', '--cacheinfo', f'{entry[0]},{entry[1]},{path}')
        else:
            git(project, 'update-index', '--force-remove', '--', path)


def _landed(project: Path, status: str, path: str, before: str, commit: str) -> bool:
    """A locally modified path takes the landed change, its index entry and its working copy alike: True when it
    did. False, with the path untouched, when the two sides clash: a landed deletion, a landed addition unlike the
    local file, a local deletion, or hunks that overlap."""
    file = project / path
    if status == 'D' or file.is_symlink() or not file.is_file():
        return False
    shown = git(project, 'ls-tree', commit, '--', path).stdout.split()
    if len(shown) < 3:
        return False
    mode, landed_blob = shown[0], shown[2]
    if mode not in ('100644', '100755'):
        return False
    theirs = _blob(project, landed_blob)
    if theirs is None:
        return False
    work = file.read_bytes()
    entries = [item for item in git(project, 'ls-files', '-s', '-z', '--', path).stdout.split('\0') if item]
    entry = entries[0].partition('\t')[0].split() if len(entries) == 1 else ['unmerged'] if entries else []
    if entry and (len(entry) != 3 or entry[2] != '0'
                  or entry[0] not in ('100644', '100755')):
        return False
    index = _blob(project, entry[1]) if entry else None
    if status == 'A':
        return work == theirs and index in (None, theirs) and git(project, 'update-index', '--add', '--cacheinfo',
                                      f'{mode},{landed_blob},{path}').returncode == 0
    original = git(project, 'ls-tree', before, '--', path).stdout.split()
    base = _blob(project, f'{before}:{path}')
    if base is None or index is None or not original or original[0] not in ('100644', '100755'):
        return False
    staged = index != base
    in_index = _three_way(base, index, theirs) if staged else theirs
    in_work = in_index if work == index else _three_way(base, work, theirs)
    if in_index is None or in_work is None:
        return False
    blob = _stored(project, in_index) if staged else landed_blob
    index_mode = entry[0] if entry[0] != original[0] else mode
    if blob is None or git(project, 'update-index', '--add', '--cacheinfo', f'{index_mode},{blob},{path}').returncode:
        return False
    permissions = file.stat().st_mode
    file.write_bytes(in_work)
    if bool(permissions & stat.S_IXUSR) == (original[0] == '100755') and mode != original[0]:
        file.chmod(permissions | 0o111 if mode == '100755' else permissions & ~0o111)
    return True


def _blob(project: Path, spec: str) -> bytes | None:
    """The bytes of a blob, by object id or `<commit>:<path>`; None when there is none."""
    found = subprocess.run(['git', 'cat-file', 'blob', spec], cwd=project, capture_output=True, check=False,
                           stdin=subprocess.DEVNULL)
    return found.stdout if found.returncode == 0 else None


def _stored(project: Path, content: bytes) -> str | None:
    """`content` written to the object store, its id; None when git refused it."""
    found = subprocess.run(['git', 'hash-object', '-w', '--stdin'], cwd=project, input=content, capture_output=True,
                           check=False)
    return found.stdout.decode('ascii').strip() if found.returncode == 0 else None


def _three_way(base: bytes, ours: bytes, theirs: bytes) -> bytes | None:
    """`ours` given the change from `base` to `theirs`, a three-way merge; None when the two sides clash."""
    with tempfile.TemporaryDirectory() as temp:
        names: list[str] = []
        for name, content in (('local', ours), ('base', base), ('landed', theirs)):
            (Path(temp) / name).write_bytes(content)
            names.append(str(Path(temp) / name))
        found = subprocess.run(['git', 'merge-file', '-p', '-L', 'local', '-L', 'base', '-L', 'landed', *names],
                               capture_output=True, check=False, stdin=subprocess.DEVNULL)
    return found.stdout if found.returncode == 0 else None


def _reported(ctx: Any, work_id: str, commit: str, kept: list[str]) -> None:
    """Record a factual landing notification without starting or directing another agent."""
    from .orchestration import TRANSPORT
    try:
        store = ctx.require_store()
        record = store.ticket(work_id).work if work_id else None
        name = ticket_title(store, record) if record is not None else f'landing {commit[:12]}'
        TRANSPORT.notify_user(ctx, {'work_id': work_id, 'text': f'{name} landed in the project branch, but local edits in '
               f'{", ".join(kept)} clash with its hunks; the files were kept as they were, so merge the landed hunks '
               'by hand (git diff HEAD -- <file> shows both sides).'}, f'landing:{work_id or commit[:12]}')
    except Exception as error:  # noqa: BLE001  the landing stands whatever its report meets
        print(f'Landing report failed: {error}', file=sys.stderr)


def _blocked(ctx: Any, store: Store, own: Store, work_id: str, why: str) -> dict[str, Any]:
    """One inbox line identifies the ticket and conflicting files. No branch is forced."""
    from .orchestration import TRANSPORT
    with own.tables() as tx:
        previous = tx.get('merges', {'work_id': work_id})
        changed = previous is not None and previous['reason'] != why
        tx.update('merges', {'work_id': work_id}, {'state': FAILED, 'reason': why})
        tx.concern(work_id=work_id, kind='ticket')
    if changed:
        try:
            title = ticket_title(store, store.ticket(work_id).work)
            TRANSPORT.notify_user(ctx, {'text': f'{title} blocked: {" ".join(why.split())}',
                                       'work_id': work_id, 'kind': 'ticket-commit', 'state': 'blocked'},
                                  f'ticket-merge:{work_id}')
        except Exception as exc:  # noqa: BLE001  the durable reason survives notification failure
            print(f'Ticket merge notification failed: {exc}', file=sys.stderr)
    return {'work_id': work_id, 'merged': False, 'why': why}


def merge_due(ctx: Any, store: Store, work_id: str, *, publish: bool = False,
              expected_head: str | None = None) -> dict[str, Any]:
    """Merge only ticket changes into one new commit. Never replay or rewrite ticket history."""
    project = Path(store.project().path)
    with Queued(project) as first:
        if not first:
            return {'work_id': work_id, 'merged': False, 'why': 'another merge is under way; retry delivery'}
        return _merge_due(ctx, store, work_id, publish=publish, expected_head=expected_head)


def _merge_due(ctx: Any, store: Store, work_id: str, *, publish: bool,
               expected_head: str | None) -> dict[str, Any]:
    """Read candidate state after acquiring the project lock, including repeated requests."""
    from . import work_over
    from .ticket_merge import validate
    own = Store(store.project_id, module='dispatch')
    with own.tables(write=False) as tx:
        found = tx.get('merges', {'work_id': work_id})
    if expected_head is not None:
        if found is None:
            return {'work_id': work_id, 'merged': False, 'why': 'No saved candidate exists for this ticket.'}
        why = validate(ctx, store, dict(found), expected_head)
        if why:
            return {'work_id': work_id, 'merged': found['state'] == MERGED, 'why': why}
    if found is None:
        project = Path(store.project().path)
        committed = git(project, 'log', '-1', '--format=%H', '--fixed-strings', '--grep',
                        f'{TRAILER}: {work_id}').stdout.strip()
        if committed:
            return deliver_shared(ctx, store, work_id)
    if found is not None and found['state'] == MERGED:
        if expected_head is not None:
            return _ticket_landed(ctx, store, own, dict(found), expected_head)
        return _delivered(ctx, store, own, Path(store.project().path), work_id, publish=publish)
    if found is None or found['state'] not in (COMMITTED, READY, MERGING, FAILED, *([REVIEW] if expected_head else [])):
        return {'work_id': work_id, 'merged': False, 'why': 'not waiting'}
    row = dict(found)
    project = Path(store.project().path)
    folder, branch = str(row['worktree']), str(row['branch'])
    if expected_head is not None and Path(folder).resolve() == project.resolve():
        if git(project, 'merge-base', '--is-ancestor', expected_head, 'HEAD').returncode:
            return _blocked(ctx, store, own, work_id, 'The saved commit is absent from the shared checkout branch.')
        return _ticket_landed(ctx, store, own, row, expected_head, made=expected_head)
    dev = dev_branch(project)
    if dev is None:
        return _blocked(ctx, store, own, work_id, 'the project folder is not on a branch')
    temp, here = merging_branch(work_id), merging_folder(project, work_id)
    before = git(project, 'rev-parse', dev).stdout.strip()
    if row['state'] == MERGING:
        made = git(project, 'rev-parse', '--verify', '--quiet', temp).stdout.strip()
        ours = bool(made) and f'{TRAILER}: {work_id}' in git(project, 'log', '-1', '--format=%B', made).stdout
        if ours and git(project, 'merge-base', '--is-ancestor', made, dev).returncode == 0:
            if expected_head is not None:
                return _ticket_landed(ctx, store, own, row, expected_head, made=made)
            return _merged(ctx, store, own, project, work_id, dev, folder, branch, publish=publish)
        if ours and git(project, 'rev-parse', f'{made}^').stdout.strip() == before:
            if expected_head is not None:
                return _ticket_landed(ctx, store, own, row, expected_head, made=made, before=before)
            passed, why = advance(project, made, before, ctx=ctx, work_id=work_id)
            if passed:
                return _merged(ctx, store, own, project, work_id, dev, folder, branch, publish=publish)
            return _blocked(ctx, store, own, work_id, why)
        _dropped(project, work_id)
    record = store.ticket(work_id).work
    if record.outcome in ('cancelled', 'failed') or not work_over(store, record):
        return _blocked(ctx, store, own, work_id, 'ticket is not completed')
    began = landing_base(project, dev, branch)
    if not began:
        return _blocked(ctx, store, own, work_id, 'ticket branch has no recorded starting commit')
    with own.tables() as tx:
        tx.update('merges', {'work_id': work_id}, {'state': MERGING})
    _dropped(project, work_id)
    made = git(project, 'worktree', 'add', '-b', temp, str(here), before)
    if made.returncode:
        return _blocked(ctx, store, own, work_id, (made.stdout + made.stderr).strip()[-1200:])
    # Explicit base excludes legacy startup snapshots. merge-recursive is also
    # available on Git versions before merge-tree gained --write-tree.
    merged = git(here, 'merge-recursive', began, '--', before, branch)
    if merged.returncode:
        why = 'conflict: ' + (merged.stdout + merged.stderr).strip()[-3000:]
        _dropped(project, work_id)
        return _blocked(ctx, store, own, work_id, why)
    command = str(ctx.setting('dispatch_test_command') or '')
    passed, why = tests_pass(here, command) if command.strip() else (True, '')
    record = store.ticket(work_id).work
    if passed and (record.outcome in ('cancelled', 'failed') or not work_over(store, record)):
        passed, why = False, 'ticket is not completed'
    if passed:
        if expected_head is not None:
            why = validate(ctx, store, row, expected_head)
            if why:
                _dropped(project, work_id)
                return {'work_id': work_id, 'merged': False, 'why': why}
        squashed = git(here, 'commit', '--allow-empty', '--cleanup=verbatim', '-q', '-m',
                       ticket_message(store, record))
        if squashed.returncode:
            passed, why = False, (squashed.stdout + squashed.stderr).strip()[-1200:]
        else:
            if expected_head is not None:
                return _ticket_landed(ctx, store, own, row, expected_head,
                                      made=git(here, 'rev-parse', 'HEAD').stdout.strip(), before=before)
            passed, why = advance(project, git(here, 'rev-parse', 'HEAD').stdout.strip(), before,
                                  ctx=ctx, work_id=work_id)
    if passed:
        return _merged(ctx, store, own, project, work_id, dev, folder, branch, publish=publish)
    _dropped(project, work_id)
    return _blocked(ctx, store, own, work_id, why)


def _ticket_landed(ctx: Any, store: Store, own: Store, row: dict[str, Any], expected_head: str, *,
                   made: str = '', before: str = '') -> dict[str, Any]:
    """Exclude new worker admission while integrating and removing its directory, never during long checks."""
    from metaform import home

    from . import admit_lock
    from .ticket_merge import complete, validate
    work_id = str(row['work_id'])
    project = Path(store.project().path)
    gate = admit_lock()
    home.mkdir_private(gate.parent)
    with home.file_lock(gate):
        why = validate(ctx, store, row, expected_head)
        if why:
            return {'work_id': work_id, 'merged': row['state'] == MERGED, 'why': why}
        if before:
            passed, why = advance(project, made, before, ctx=ctx, work_id=work_id, require_applied=True)
            if not passed:
                _dropped(project, work_id)
                return _blocked(ctx, store, own, work_id, why)
        if row['state'] != MERGED:
            # Save integration before cleanup. A crash or unsafe directory leaves a cleanup-only retry.
            row = {**row, 'state': MERGED, 'reason': '',
                   'evidence': {**(row.get('evidence') or {}), 'integration': {'commit': made},
                                'cleanup': {'state': 'pending', 'reason': 'Worktree cleanup is pending.'}}}
            with own.tables() as tx:
                tx.update('merges', {'work_id': work_id}, row)
                tx.concern(work_id=work_id, kind='ticket')
        _dropped(project, work_id)
        return complete(ctx, store, row)


def _merged(ctx: Any, store: Store, own: Store, project: Path, work_id: str, dev: str, folder: str,
            branch: str, *, publish: bool = False) -> dict[str, Any]:
    """Journal the landed commit, retaining the ticket branch and all its worktree files."""
    _dropped(project, work_id)
    record = store.ticket(work_id).work
    candidate = git(project, 'rev-parse', branch).stdout.strip()
    _saved(store, record, Path(folder), branch, candidate, verify_commit(ctx, project, record, candidate),
           snapshot_of(project, branch) or '')
    # Keep ticket branches and worktrees. Another session may still own uncommitted files there.
    with own.tables() as tx:
        tx.update('merges', {'work_id': work_id}, {'state': MERGED, 'reason': PUSH_PENDING if publish else ''})
    return _delivered(ctx, store, own, project, work_id, publish=publish)


def _delivered(ctx: Any, store: Store, own: Store, project: Path, work_id: str, *,
               publish: bool = False) -> dict[str, Any]:
    """A committed merge's pending push survives crashes. Explicit retries never repeat its squash."""
    if not publish:
        return {'work_id': work_id, 'merged': True, 'pushed': False, 'conflict': False, 'why': ''}
    pushed = push_ticket(project)
    activation: dict[str, Any] = {}
    why = pushed['why'] or ('' if pushed['pushed'] else 'push pending: configure the branch upstream')
    if pushed['pushed']:
        from .activation import delivered
        activation = delivered(ctx, store, own, project, work_id)
        if not activation['active']:
            why = activation['why'] or 'runtime activation pending'
    if why:
        from .orchestration import TRANSPORT
        try:
            record = store.ticket(work_id).work
            TRANSPORT.notify_user(ctx, {'text': f'{ticket_title(store, record)} blocked: {why}',
                                        'work_id': work_id, 'kind': 'ticket-commit', 'state': 'blocked'},
                                  f'ticket-commit:{work_id}')
        except Exception as exc:  # noqa: BLE001  notification failure cannot undo a completed merge
            print(f'Ticket push notification failed: {exc}', file=sys.stderr)
    with own.tables() as tx:
        tx.update('merges', {'work_id': work_id}, {'reason': why})
        tx.concern(work_id=work_id, kind='ticket')
    return {'work_id': work_id, 'merged': True, **pushed, 'why': why, **activation}


def deliver_shared(ctx: Any, store: Store, work_id: str, commit: str = '') -> dict[str, Any]:
    """Record a shared-checkout feature commit and verification without publishing it."""
    project = Path(store.project().path)
    record = store.ticket(work_id).work
    commit = commit or git(project, 'log', '-1', '--format=%H', '--fixed-strings', '--grep',
                           f'{TRAILER}: {work_id}').stdout.strip()
    if not commit or f'{TRAILER}: {work_id}' not in git(project, 'log', '-1', '--format=%B', commit).stdout:
        return {'work_id': work_id, 'why': "Save this ticket's feature commit before completion."}
    return _saved(store, record, project, dev_branch(project) or '', commit,
                  verify_commit(ctx, project, record, commit))


def deliver_nonrepository(ctx: Any, store: Store, work_id: str) -> dict[str, Any]:
    """Verify work without a repository, retaining that fact instead of inventing a commit."""
    project = Path(store.project().path)
    if repository(project):
        return {'reason': 'This project has a repository. Save its verified feature commit.'}
    record = store.ticket(work_id).work
    return _saved(store, record, project, '', None, verification(ctx, project, record), repository_present=False)


def abandoned(store: Store, project: str | Path, days: int) -> list[str]:
    """The branches of tickets closed and not merged, older than `days`, removed with their worktrees and snapshots,
    P017, without committing cancelled or failed work; git's record of worktrees gone is pruned, P192."""
    from .ticket_merge import cleanup_pending
    project = Path(project)
    if dev_branch(project) is None:
        return []
    git(project, 'worktree', 'prune')
    listed = git(project, 'for-each-ref', '--format=%(refname:short) %(committerdate:unix)', 'refs/heads/metaform/')
    own = Store(store.project_id, module='dispatch')
    with own.tables(write=False) as tx:
        waiting = {str(row['branch']) for row in tx.rows('merges', limit=0).results
                   if row['state'] in (COMMITTED, READY, REVIEW, MERGING, FAILED)
                   or cleanup_pending(dict(row))}
    closed = {branch_of(record.id): record for record in store.work(open=False, limit=0).results}
    gone: list[str] = []
    for line in listed.stdout.splitlines():
        branch, _, when = line.partition(' ')
        if branch in waiting or branch not in closed or time.time() - float(when or 0) < days * 86400:
            continue
        folder = project / FOLDER / branch.split('/', 1)[1]
        if folder.exists() and dev_branch(folder) != branch:
            continue  # a retained episode now works on a later card here
        removed(project, folder, branch)
        gone.append(branch)
    return gone
