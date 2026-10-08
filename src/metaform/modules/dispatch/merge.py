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

import subprocess
import time
from pathlib import Path
from typing import Any

from metaform.data import Node, Store, WorkRecord

READY, REVIEW, MERGED, FAILED = 'ready', 'review', 'merged', 'failed'
FOLDER = '.worktrees'  # inside the project folder, so an agent there reaches the project; kept out of git status


def git(folder: str | Path, *words: str, limit: float = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(['git', *words], cwd=folder, capture_output=True, text=True, encoding='utf-8',
                          timeout=limit, check=False, stdin=subprocess.DEVNULL)


def branch_of(work_id: str) -> str:
    return f'metaform/{work_id[:12]}'


def dev_branch(project: str | Path) -> str | None:
    """The active dev branch: the branch checked out in the project folder; none outside git or detached."""
    found = git(project, 'symbolic-ref', '--quiet', '--short', 'HEAD')
    return found.stdout.strip() or None if found.returncode == 0 else None


def worktree_for(project: str | Path, work_id: str) -> Path | None:
    """The ticket's own worktree, made on first use on a branch from the active dev branch; none when the project
    folder is not a git repository on a branch."""
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
    made = git(project, 'worktree', 'add', *([str(folder), branch] if known else ['-b', branch, str(folder), dev]))
    return folder if made.returncode == 0 else None


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
    """Whether the branch merges into the active dev branch with no conflict, without touching either."""
    dev = dev_branch(project)
    if dev is None:
        return False, 'the project folder is not on a branch'
    found = git(project, 'merge-tree', '--write-tree', dev, branch)
    if found.returncode in (0, 1) and 'unknown rev' not in found.stderr:  # git 2.38 and later: 1 means conflicts
        return found.returncode == 0, '' if found.returncode == 0 else (found.stdout + found.stderr).strip()[-400:]
    # An earlier git: the trivial three-way merge-tree prints conflict markers where the two sides clash.
    base = git(project, 'merge-base', dev, branch).stdout.strip()
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
    """A done ticket's worktree: its changes committed, the tests and the merge check run, and when both pass the merge
    waits for review. Returns the merge row, or None when there is nothing to merge."""
    project = Path(store.project().path)
    git(folder, 'add', '-A')
    git(folder, 'commit', '-q', '-m', f'{record.condition or "work"}: {(record.task or record.note or "")[:60]}',
        '-m', f'Work {record.id}: {record.resolution or ""}')
    branch = branch_of(record.id)
    dev = dev_branch(project)
    if dev is None or git(project, 'rev-list', '--count', f'{dev}..{branch}').stdout.strip() in ('', '0'):
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


def due(store: Store) -> list[dict[str, Any]]:
    """The merges waiting for review, the soonest first."""
    own = Store(store.project_id, module='dispatch')
    with own.tables(write=False) as tx:
        rows = [dict(row) for row in tx.rows('merges', {'state': READY}, limit=0).results]
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


def merge_due(ctx: Any, store: Store, work_id: str) -> dict[str, Any]:
    """At the deadline, with no review: run both checks again, merge into the active dev branch, and write the ticket
    that says the feature needs testing before the next release. Anything that no longer passes is not merged."""
    own = Store(store.project_id, module='dispatch')
    with own.tables(write=False) as tx:
        row = tx.get('merges', {'work_id': work_id})
    if row is None or row['state'] != READY:
        return {'work_id': work_id, 'merged': False, 'why': 'not waiting'}
    row = dict(row)
    project = Path(store.project().path)
    passed, said = tests_pass(row['worktree'], str(ctx.setting('dispatch_test_command')))
    merges, why = clean_merge(project, row['branch']) if passed else (False, said)
    outcome: dict[str, Any] = {'state': FAILED, 'reason': why}
    if passed and merges:
        done = git(project, 'merge', '--no-ff', '--no-edit', row['branch'])
        if done.returncode == 0:
            outcome = {'state': MERGED, 'reason': ''}
            record = store.ticket(work_id).work
            store.add_work(Node.of(record.node_kind, record.node_id), None,
                           note=f'Merged into {dev_branch(project)} without review, from {row["branch"]}, after its '
                                f'tests passed: work {work_id}.',
                           task=f'Newly committed feature, needs testing before the next release: '
                                f'{record.task or record.note or work_id}')
        else:
            git(project, 'merge', '--abort')
            outcome['reason'] = (done.stdout + done.stderr).strip()[-400:]
    with own.tables() as tx:
        tx.update('merges', {'work_id': work_id}, outcome)
    return {'work_id': work_id, 'merged': outcome['state'] == MERGED, 'why': outcome['reason']}
