"""Explicit ticket integration and conservative cleanup of its saved worktree."""
from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from metaform.data import Store, WorkRecord
from metaform.module import Context


def _object(value: Any) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def cleanup_pending(row: dict[str, Any]) -> bool:
    return _object(_object(row.get('evidence')).get('cleanup')).get('state') == 'pending'


def eligible(store: Store, record: WorkRecord, row: dict[str, Any]) -> bool:
    from . import work_over
    evidence = _object(row.get('evidence'))
    return bool(row.get('head') and evidence.get('repository') is True
                and _object(evidence.get('verification')).get('passed') is True
                and record.outcome not in ('cancelled', 'failed') and record.resolution and work_over(store, record))


def unavailable(ctx: Context, store: Store, work_id: str, *, check_launches: bool = False) -> str:
    from . import holding, launches, sessions
    from .orchestration import assignment
    found = sessions(store, work_id, verify=False)
    if any(one.get('state') == 'running' for one in found):
        return 'An agent still owns this ticket. End its session before merging or cleaning its worktree.'
    if check_launches and (any(one.get('project') == store.project_id and one.get('work_id') == work_id
                              for one in launches()) or holding(store, work_id, found) is not None):
        return 'An admitted agent is starting or resuming this ticket.'
    record = store.ticket(work_id).work
    if str(record.taken_by or '').startswith('dispatch starting '):
        return 'An agent is starting on this ticket.'
    held = assignment(ctx, work_id=work_id)
    if held and held.get('stop') or found and str(found[-1].get('how') or '').startswith('stopped by '):
        return 'This ticket was explicitly stopped. Resume it before merging or cleaning its worktree.'
    return ''


def read(ctx: Context, records: Sequence[WorkRecord]) -> dict[str, dict[str, Any]]:
    """Read only saved candidates for the requested tickets. No Git work on board refreshes."""
    from .merge import MERGED
    store = ctx.require_store()
    with Store(store.project_id, module='dispatch').tables(write=False) as tx:
        rows = {record.id: tx.get('merges', {'work_id': record.id}) for record in records}
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        row = rows[record.id]
        if row is None or not eligible(store, record, dict(row)):
            continue
        cleanup = _object(_object(row.get('evidence')).get('cleanup')) or None
        merged = row['state'] == MERGED
        action = 'cleanup' if merged and cleanup and cleanup['state'] != 'complete' else None if merged else 'merge'
        reason = unavailable(ctx, store, record.id)
        result[record.id] = {'head': row['head'], 'action': action, 'busy': bool(reason),
                             'reason': reason or row['reason'] or '', 'merged': merged, 'cleanup': cleanup}
    return result


def pending(ctx: Context) -> list[WorkRecord]:
    """Keep older saved, unmerged Done tickets visible beyond a board's archive cutoff."""
    from .merge import MERGED
    store = ctx.require_store()
    with Store(store.project_id, module='dispatch').tables(write=False) as tx:
        rows = {str(row['work_id']): dict(row) for row in tx.rows('merges', limit=0).results
                if row['state'] != MERGED or cleanup_pending(dict(row))}
    if not rows:
        return []
    return [record for record in store.work(ids=list(rows), open=False, limit=0).results
            if eligible(store, record, rows[record.id])]


def validate(ctx: Context, store: Store, row: dict[str, Any], expected_head: str) -> str:
    from .merge import MERGED, branch_of, git
    record = store.ticket(str(row['work_id'])).work
    with Store(store.project_id, module='dispatch').tables(write=False) as tx:
        current = tx.get('merges', {'work_id': record.id})
    if current is None or any(current[key] != row.get(key) for key in ('head', 'seq', 'branch', 'worktree')):
        return 'The saved candidate changed. Reload this ticket before merging.'
    if row.get('head') != expected_head:
        return 'The saved candidate changed. Reload this ticket before merging.'
    if not eligible(store, record, row):
        return 'This ticket has no verified, saved implementation awaiting integration.'
    reason = unavailable(ctx, store, record.id, check_launches=True)
    if reason:
        return reason
    project = Path(store.project().path).resolve()
    if row['state'] == MERGED:
        integrated = _object(_object(row.get('evidence')).get('integration')).get('commit')
        if integrated and git(project, 'merge-base', '--is-ancestor', str(integrated), 'HEAD').returncode:
            return 'The integrated commit is absent from the current checkout branch. Worktree cleanup is preserved.'
        return ''
    body = git(project, 'log', '-1', '--format=%B', expected_head)
    if body.returncode or f'Metaform-Ticket: {record.id}' not in body.stdout.splitlines():
        return 'The saved commit does not identify this ticket.'
    if Path(row['worktree']).resolve() != project:
        if row['branch'] != branch_of(record.id):
            return 'The saved branch does not belong to this ticket.'
        if git(project, 'rev-parse', '--verify', row['branch']).stdout.strip() != expected_head:
            return 'The ticket branch changed after saving. Save and verify its current candidate first.'
    return ''


def cleanup(ctx: Context, store: Store, row: dict[str, Any]) -> dict[str, str]:
    """Called under dispatch admission and Git merge locks. Never force worktree removal."""
    from .merge import FOLDER, branch_of, git
    project = Path(store.project().path).resolve()
    folder = Path(row['worktree'])
    expected = project / FOLDER / str(row['work_id'])[:12]
    if folder.resolve() == project:
        return {'state': 'complete', 'reason': 'The shared checkout is retained.'}
    reason = unavailable(ctx, store, str(row['work_id']), check_launches=True)
    if reason:
        return {'state': 'pending', 'reason': reason}
    if folder.absolute() != expected or folder.resolve() != expected or row['branch'] != branch_of(str(row['work_id'])):
        return {'state': 'pending', 'reason': f'Worktree ownership cannot be proved: {folder}.'}
    with Store(store.project_id, module='dispatch').tables(write=False) as tx:
        others = tx.rows('merges', limit=0).results
    if any(other['work_id'] != row['work_id'] and (other['worktree'] == str(folder)
               or other['branch'] == row['branch']) for other in others):
        return {'state': 'pending', 'reason': 'Another ticket also references this worktree or branch.'}
    if not folder.exists():
        return {'state': 'complete', 'reason': 'The ticket worktree is already absent.'}
    listed = git(project, 'worktree', 'list', '--porcelain')
    block = next((part for part in listed.stdout.split('\n\n') if f'worktree {folder}' in part.splitlines()), '')
    if listed.returncode or f'branch refs/heads/{row["branch"]}' not in block.splitlines():
        return {'state': 'pending', 'reason': f'The registered worktree does not match this ticket: {folder}.'}
    if git(folder, 'rev-parse', 'HEAD').stdout.strip() != row['head']:
        return {'state': 'pending', 'reason': 'The worktree contains commits beyond the integrated candidate.'}
    # Ignored files are recovery material too. Git --force would discard them.
    dirty = git(folder, 'status', '--porcelain', '--untracked-files=all', '--ignored')
    if dirty.returncode or dirty.stdout.strip():
        return {'state': 'pending', 'reason': f'Uncommitted, untracked or ignored files remain in {folder}.'}
    removed = git(project, 'worktree', 'remove', str(folder))
    if removed.returncode:
        return {'state': 'pending', 'reason': (removed.stderr or removed.stdout).strip() or f'Cannot remove {folder}.'}
    return {'state': 'complete', 'reason': ''}


def complete(ctx: Context, store: Store, row: dict[str, Any]) -> dict[str, Any]:
    """Keep integration separate from recoverable cleanup. Cleanup retries never merge again."""
    try:
        result = cleanup(ctx, store, row)
    except (OSError, subprocess.SubprocessError) as error:
        result = {'state': 'pending', 'reason': f'Worktree cleanup failed: {error}'}
    own = Store(store.project_id, module='dispatch')
    with own.tables() as tx:
        tx.update('merges', {'work_id': row['work_id']},
                  {'evidence': {**(row.get('evidence') or {}), 'cleanup': result}, 'reason': result['reason']
                   if result['state'] != 'complete' else ''})
        tx.concern(work_id=str(row['work_id']), kind='ticket')
    record = store.ticket(str(row['work_id'])).work
    if result['state'] == 'complete' and not record.done:
        record = store.finish_work(record.id, record.resolution)
    return {'work_id': row['work_id'], 'merged': True, 'pushed': False, 'done': bool(record.done),
            'cleanup': result, 'why': result['reason'] if result['state'] != 'complete' else ''}
