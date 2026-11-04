"""Ticket completion saves feature commits. Explicit publication preserves shared edits.

Legacy review rows remain under manual control. Real local git repositories, no model.
"""
import asyncio
import importlib
import json
import subprocess
import time

import pytest

from metaform.modules.dispatch.tests.test_dispatch import dispatch as dispatch  # noqa: PLC0414 fixture re-export

pytestmark = [pytest.mark.req('VIEW-044'), pytest.mark.kind('simulation')]


def git(folder, *words):
    return subprocess.run(['git', *words], cwd=folder, capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def repo(dispatch, run, tmp_path):
    """The project folder as a git repository on its dev branch, with worktrees on and a test command that passes."""
    folder = dispatch.folder
    git(folder, 'init', '-q', '-b', 'dev')
    git(folder, 'config', 'user.email', 'test@example.com')
    git(folder, 'config', 'user.name', 'Test')
    (folder / 'README.md').write_text('base\n', encoding='utf-8')
    git(folder, 'add', '-A')
    git(folder, 'commit', '-q', '-m', 'base')
    remote = tmp_path / 'origin.git'
    git(folder, 'init', '--bare', '-q', str(remote))
    git(folder, 'remote', 'add', 'origin', str(remote))
    git(folder, 'push', '-qu', 'origin', 'dev')
    run('set', '--dispatch-worktrees', '--dispatch-test-command=true', cwd=folder)
    return folder


def worked(dispatch, repo):
    """Complete a ticket in its worktree through the real delivery path."""
    from metaform.module import context
    from metaform.modules.dispatch.merge import finished
    folder, record = ticket_work(dispatch, repo)
    return [finished(context('dispatch', repo, project='proj'), dispatch.store, record, folder)]


def ticket_work(dispatch, repo):
    from metaform.modules.dispatch.merge import worktree_for
    folder = worktree_for(repo, dispatch.id)
    (folder / 'feature.txt').write_text('ticket feature\n', encoding='utf-8')
    record = dispatch.store.finish_work(dispatch.id, 'Feature completed.', 'Deliver accepted behavior.')
    return folder, record


def waiting_merge(dispatch, repo):
    """A persisted ready row from before automatic delivery, for manual review and recovery."""
    from metaform.data import Store
    from metaform.modules.dispatch.merge import READY, branch_of, checkpoint, ticket_message
    folder, record = ticket_work(dispatch, repo)
    assert checkpoint(folder, dispatch.id, ticket_message(dispatch.store, record), completed=True)
    row = {'work_id': dispatch.id, 'branch': branch_of(dispatch.id), 'worktree': str(folder),
           'state': READY, 'reason': '', 'ready': time.time(), 'deadline': time.time(), 'seq': time.time_ns()}
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('merges', row)
    return row


def test_a_done_ticket_saves_one_verified_commit_without_publishing_or_successor(dispatch, repo, run):
    head = git(repo, 'rev-parse', 'HEAD')
    [delivered] = worked(dispatch, repo)
    assert delivered['state'] == 'committed' and not delivered['reason'], delivered
    assert delivered['branch'].startswith('metaform/')
    assert (repo / delivered['worktree']).is_dir()
    tree = repo / delivered['worktree']
    assert (tree / 'feature.txt').read_text(encoding='utf-8') == 'ticket feature\n'
    assert not (repo / 'feature.txt').exists()
    assert git(repo, 'branch', '--show-current') == 'dev'
    assert git(repo, 'rev-parse', 'HEAD') == git(repo, 'rev-parse', 'origin/dev') == head
    assert git(tree, 'rev-list', '--count', 'HEAD') == '2'
    assert git(tree, 'log', '--format=%B').count(f'Metaform-Ticket: {dispatch.id}') == 1
    assert delivered['head'] == git(tree, 'rev-parse', 'HEAD')
    assert delivered['evidence']['verification']['passed'] is True
    assert delivered['evidence']['artifacts'] == ['feature.txt']
    assert dispatch.ticket().done
    assert not dispatch.store.work(open=True, limit=0).results, 'delivery creates no successor ticket'
    assert json.loads(run('dispatch', 'merges', '--json', cwd=repo).stdout)['merges'] == []


def test_saved_feature_branch_survives_automatic_abandoned_cleanup(dispatch, repo):
    from metaform.modules.dispatch.merge import abandoned

    [saved] = worked(dispatch, repo)
    assert abandoned(dispatch.store, repo, 0) == []
    assert git(repo, 'rev-parse', saved['branch']) == saved['head']
    assert (repo / saved['worktree']).is_dir()


def test_saved_candidate_does_not_integrate_or_publish_without_explicit_request(dispatch, repo, monkeypatch):
    from metaform.modules.dispatch import activation
    merge = importlib.import_module('metaform.modules.dispatch.merge')
    before = git(repo, 'rev-parse', 'HEAD')

    def publish_forbidden(*args, **kwargs):
        pytest.fail('Local ticket completion must not publish or activate.')

    monkeypatch.setattr(merge, 'push_ticket', publish_forbidden)
    monkeypatch.setattr(activation, 'delivered', publish_forbidden)
    [saved] = worked(dispatch, repo)
    assert saved['state'] == 'committed'
    assert dispatch.ticket().done
    assert git(repo, 'rev-parse', 'origin/dev') == before
    assert git(repo, 'rev-parse', 'HEAD') == before
    assert not (repo / 'feature.txt').exists()
    assert git(repo, 'show', f"{merge.branch_of(dispatch.id)}:feature.txt") == 'ticket feature'
    assert not dispatch.store.work(open=True, limit=0).results


def test_explicit_merge_integrates_locally_without_pushing_by_default(dispatch, repo, run, monkeypatch):
    from metaform.modules.dispatch import activation
    merge = importlib.import_module('metaform.modules.dispatch.merge')
    [saved] = worked(dispatch, repo)
    before = git(repo, 'rev-parse', 'HEAD')

    def publish_forbidden(*args, **kwargs):
        pytest.fail('An explicit local merge must not publish or activate.')

    monkeypatch.setattr(merge, 'push_ticket', publish_forbidden)
    monkeypatch.setattr(activation, 'delivered', publish_forbidden)
    result = json.loads(run('dispatch', 'merge', dispatch.id, '--json', cwd=repo).stdout)
    assert result['merged'] and not result['pushed'] and not result['why'], result
    assert git(repo, 'rev-parse', 'HEAD') != before
    assert git(repo, 'rev-parse', 'origin/dev') == before
    assert (repo / 'feature.txt').read_text() == 'ticket feature\n'
    assert git(repo, 'rev-parse', saved['branch']) == saved['head']


def _killed_at(monkeypatch, step):
    """merge.git, raising as if the process were killed right after the git command `step` ran."""
    merge = importlib.import_module('metaform.modules.dispatch.merge')
    real = merge.git

    def git_then_die(folder, *words, **kwargs):
        done = real(folder, *words, **kwargs)
        if words and words[0] == step:
            raise SystemExit('killed')
        return done
    monkeypatch.setattr(merge, 'git', git_then_die)
    return real


@pytest.mark.req('BASE-052')
@pytest.mark.parametrize('step', ['merge-recursive', 'commit', 'checkout', 'update-ref'])
def test_a_merge_killed_part_way_leaves_the_agents_branch_as_it_was_and_the_next_check_merges_it_once(
        dispatch, repo, run, monkeypatch, step):
    """A crash at each durable git step preserves ticket history and resumes delivery exactly once."""
    from metaform.module import context
    merge = importlib.import_module('metaform.modules.dispatch.merge')
    waiting = waiting_merge(dispatch, repo)
    tip = git(repo, 'rev-parse', waiting['branch'])
    from pathlib import Path
    folder = Path(waiting['worktree'])
    (folder / 'peer-draft.txt').write_text('peer draft\n')
    ctx = context('dispatch', repo, project='proj')
    merge = importlib.import_module('metaform.modules.dispatch.merge')
    real = _killed_at(monkeypatch, step)
    with pytest.raises(SystemExit):
        result = merge.merge_due(ctx, dispatch.store, dispatch.id, publish=True)
        pytest.fail(f'Merge never reached {step}: {result}')
    monkeypatch.setattr(merge, 'git', real)
    assert git(repo, 'rev-parse', waiting['branch']) == tip, 'the agent\'s branch never moves'
    [row] = json.loads(run('dispatch', 'merges', '--json', cwd=repo).stdout)['merges']
    assert row['state'] == 'merging', 'the merge under way is journaled'
    dead = subprocess.Popen(['true'])
    dead.wait()
    merge.Queued(repo).path.write_text(str(dead.pid), encoding='utf-8')  # the lock a killed merge leaves
    merged = merge.merge_due(ctx, dispatch.store, dispatch.id, publish=True)
    assert merged['merged'] is True and 'conflict' not in merged['why'], merged
    assert merged['pushed'] and not merged['why'], merged
    assert (repo / 'feature.txt').read_text(encoding='utf-8') == 'ticket feature\n'
    assert git(repo, 'log', '--format=%B').count(f'Metaform-Ticket: {dispatch.id}') == 1
    assert git(repo, 'rev-list', '--count', 'HEAD') == '2'
    assert git(repo, 'rev-parse', 'origin/dev') == git(repo, 'rev-parse', 'HEAD')
    assert git(repo, 'rev-parse', waiting['branch']) == tip
    assert (folder / 'peer-draft.txt').read_text() == 'peer draft\n'
    assert not (repo / 'peer-draft.txt').exists()
    assert not git(repo, 'branch', '--list', 'metaform-merging/*')
    assert git(repo, 'status', '--porcelain') == ''
    assert not dispatch.store.work(open=True, limit=0).results




def test_review_takes_the_merge_over_for_good(dispatch, repo, run):
    waiting_merge(dispatch, repo)
    assert json.loads(run('dispatch', 'review', dispatch.id, '--json', cwd=repo).stdout)['state'] == 'review'
    merged = json.loads(run('dispatch', 'merge', dispatch.id, 'publish=true', '--json', cwd=repo).stdout)
    assert merged['merged'] is False and not (repo / 'feature.txt').exists(), 'a reviewed merge never merges by itself'
    again = run('dispatch', 'review', dispatch.id, cwd=repo, ok=False)
    assert again.returncode != 0, 'the countdown never restarts'


def test_with_no_test_command_ticket_still_saves_without_publishing(dispatch, repo, run):
    head = git(repo, 'rev-parse', 'HEAD')
    run('set', '--dispatch-test-command=', cwd=repo)
    [delivered] = worked(dispatch, repo)
    assert delivered['state'] == 'committed' and not delivered['reason'], delivered
    assert delivered['evidence']['verification']['passed'] is True
    assert delivered['evidence']['verification']['command'] == ''
    assert (repo / delivered['worktree'] / 'feature.txt').read_text() == 'ticket feature\n'
    assert git(repo, 'rev-parse', 'origin/dev') == git(repo, 'rev-parse', 'HEAD') == head


def test_work_that_clashes_preserves_branches_and_sends_one_inbox_line(dispatch, repo, run, monkeypatch):
    from metaform.module import context
    waiting = waiting_merge(dispatch, repo)
    tip = git(repo, 'rev-parse', waiting['branch'])
    (repo / 'feature.txt').write_text('changed on dev meanwhile\n', encoding='utf-8')
    git(repo, 'add', '-A')
    git(repo, 'commit', '-q', '-m', 'ongoing work')
    head = git(repo, 'rev-parse', 'HEAD')
    ctx = context('dispatch', repo, project='proj')
    merge = importlib.import_module('metaform.modules.dispatch.merge')
    from metaform.modules.dispatch.orchestration import TRANSPORT
    notices = []
    monkeypatch.setattr(TRANSPORT, 'notify_user', lambda *args: notices.append(args))
    merged = merge.merge_due(ctx, dispatch.store, dispatch.id, publish=True)
    assert merged['merged'] is False and 'conflict' in merged['why'].lower(), merged
    assert (repo / 'feature.txt').read_text(encoding='utf-8') == 'changed on dev meanwhile\n'
    assert git(repo, 'status', '--porcelain') == '', 'a refused merge leaves the dev branch untouched'
    assert git(repo, 'rev-parse', 'HEAD') == head
    assert git(repo, 'rev-parse', waiting['branch']) == tip
    assert not merge.merge_due(ctx, dispatch.store, dispatch.id, publish=True)['merged']
    assert len(notices) == 1, [args[1]['text'] for args in notices]
    payload = notices[0][1]
    handle = dispatch.store.numbers_of('work', [dispatch.id])[dispatch.id][0]
    assert handle in payload['text'] and 'feature.txt' in payload['text']
    assert payload['work_id'] == dispatch.id and payload['state'] == 'blocked'


def test_the_agent_asked_to_help_works_in_the_merges_worktree_with_the_prep_prompt(dispatch, repo, run, monkeypatch,
                                                                                  dispatch_runners):
    from metaform.modules.dispatch.tests.test_dispatch import eventually
    waiting = waiting_merge(dispatch, repo)
    run('dispatch', 'review', dispatch.id, cwd=repo)
    run('map', 'work', 'op=edit', f'id={dispatch.id}', 'agent=claude', cwd=repo)
    for name, value in dispatch.env('hold').items():
        monkeypatch.setenv(name, value)
    started = json.loads(run('dispatch', 'prep', dispatch.id, '--json', cwd=repo).stdout)
    dispatch_runners.append((started, repo, dispatch.log))
    said = eventually(lambda: dispatch.received('session/new') or None)
    assert said[0]['params']['cwd'] == waiting['worktree'], 'the helping agent works in the merge\'s worktree'
    [text] = eventually(lambda: [message['params']['prompt'][0]['text'] for message in dispatch.received('session/prompt')
                                 if 'Do not merge into' in message['params']['prompt'][0]['text']] or None)
    assert waiting['branch'] in text and 'Do not merge into dev' in text
    assert not dispatch.ticket().taken_by, 'the completed ticket is not taken again'


@pytest.mark.req('BASE-052')
def test_a_worktree_excludes_shared_uncommitted_work_and_merges_only_ticket_changes(dispatch, repo, run):
    """Ticket branches start from committed HEAD. Shared staging, edits, deletions and drafts stay in place."""
    (repo / 'removed.txt').write_text('tracked peer file\n', encoding='utf-8')
    git(repo, 'add', 'removed.txt')
    git(repo, 'commit', '-q', '-m', 'peer file')
    head = git(repo, 'rev-parse', 'HEAD')
    (repo / 'README.md').write_text('staged peer change\n', encoding='utf-8')
    git(repo, 'add', 'README.md')
    (repo / 'README.md').write_text('base\nuncommitted line\n', encoding='utf-8')
    (repo / 'removed.txt').unlink()
    (repo / 'draft.txt').write_text('an untracked draft\n', encoding='utf-8')
    before = [git(repo, *args) for args in [('diff',), ('diff', '--cached'), ('status', '--porcelain')]]
    [waiting] = worked(dispatch, repo)
    tree = repo / waiting['worktree']
    assert (tree / 'README.md').read_text(encoding='utf-8') == 'base\n'
    assert (tree / 'removed.txt').read_text(encoding='utf-8') == 'tracked peer file\n'
    assert not (tree / 'draft.txt').exists()
    assert waiting['state'] == 'committed' and not waiting['reason'], waiting
    assert git(repo, 'rev-parse', 'HEAD') == head
    assert not (repo / 'feature.txt').exists()
    assert [git(repo, *args) for args in [('diff',), ('diff', '--cached'), ('status', '--porcelain')]] == before
    assert git(repo, 'rev-parse', f"refs/metaform/snapshot/{waiting['branch']}") == head
    assert 'Snapshot of uncommitted work' not in git(tree, 'log', '--format=%s', f'{head}..HEAD')
    assert f'Metaform-Ticket: {dispatch.id}' in git(tree, 'log', '-1', '--format=%B')
    tip = git(tree, 'rev-parse', 'HEAD')
    (tree / 'later-draft.txt').write_text('another agent owns this draft\n')
    merged = json.loads(run('dispatch', 'merge', dispatch.id, 'publish=true', '--json', cwd=repo).stdout)
    assert merged['merged'] and merged['pushed'], merged
    assert git(repo, 'rev-parse', 'origin/dev') == git(repo, 'rev-parse', 'HEAD') != head
    assert git(repo, 'log', '-1', '--format=%B').count('Metaform-Ticket') == 1
    assert git(repo, 'show', '--stat', '--format=', 'HEAD').split('|')[0].strip() == 'feature.txt', \
        'the merged commit holds the agent\'s work alone'
    assert git(tree, 'rev-parse', 'HEAD') == tip
    assert (tree / 'later-draft.txt').read_text() == 'another agent owns this draft\n'
    assert [git(repo, *args) for args in [('diff',), ('diff', '--cached'), ('status', '--porcelain')]] == before
    assert tree.exists() and git(repo, 'branch', '--list', waiting['branch'])


def test_legacy_dirty_snapshot_is_excluded_when_its_ticket_branch_merges(dispatch, repo):
    from metaform.module import context
    merge = importlib.import_module('metaform.modules.dispatch.merge')

    folder = merge.worktree_for(repo, dispatch.id)
    (folder / 'README.md').write_text('unrelated shared edit\n', encoding='utf-8')
    (folder / 'draft.txt').write_text('unrelated shared draft\n', encoding='utf-8')
    git(folder, 'add', '-A')
    git(folder, 'commit', '-qm', f'Snapshot of uncommitted work for ticket {dispatch.id}')
    git(repo, 'update-ref', f'{merge.SNAPSHOTS}/{merge.branch_of(dispatch.id)}', git(folder, 'rev-parse', 'HEAD'))
    (folder / 'feature.txt').write_text('ticket change\n', encoding='utf-8')
    record = dispatch.store.finish_work(dispatch.id, 'Feature completed.', 'Deliver only ticket changes.')
    ctx = context('dispatch', repo, project='proj')
    assert merge.finished(ctx, dispatch.store, record, folder)['state'] == 'committed'
    assert merge.merge_due(ctx, dispatch.store, dispatch.id, publish=True)['merged']
    assert (repo / 'README.md').read_text(encoding='utf-8') == 'base\n'
    assert not (repo / 'draft.txt').exists()
    assert (repo / 'feature.txt').read_text(encoding='utf-8') == 'ticket change\n'
    assert git(repo, 'diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD') == 'feature.txt'
    assert 'Snapshot of uncommitted work' not in git(repo, 'log', '--format=%s')


def test_a_ticket_branch_that_merged_the_dev_branch_lands_from_their_merge_base(dispatch, repo):
    """A branch that merged dev after its recorded start lands from their merge-base, not from that start: dev's own
    changes since then are not read as conflicts the branch has already resolved, and only the ticket's delta lands."""
    from metaform.module import context
    merge = importlib.import_module('metaform.modules.dispatch.merge')
    folder = merge.worktree_for(repo, dispatch.id)
    (repo / 'README.md').write_text('base\ndev line\n', encoding='utf-8')
    git(repo, 'commit', '-qam', 'dev moves on')
    (folder / 'README.md').write_text('base\nbranch line\n', encoding='utf-8')
    git(folder, 'commit', '-qam', 'branch edits the same place')
    clashed = subprocess.run(['git', 'merge', '--no-edit', 'dev'], cwd=folder, capture_output=True, text=True,
                             check=False)
    assert clashed.returncode != 0, 'the branch meets dev\'s change and resolves it itself'
    (folder / 'README.md').write_text('base\ndev line\nbranch line\n', encoding='utf-8')
    git(folder, 'add', 'README.md')
    git(folder, 'commit', '-qm', 'merge dev, resolved')
    (folder / 'feature.txt').write_text('ticket feature\n', encoding='utf-8')
    record = dispatch.store.finish_work(dispatch.id, 'Feature completed.', 'Deliver only ticket changes.')
    ctx = context('dispatch', repo, project='proj')
    merge.finished(ctx, dispatch.store, record, folder)
    landed = merge.merge_due(ctx, dispatch.store, dispatch.id, publish=True)
    assert landed['merged'] and 'conflict' not in landed['why'], landed
    assert (repo / 'README.md').read_text(encoding='utf-8') == 'base\ndev line\nbranch line\n'
    assert (repo / 'feature.txt').read_text(encoding='utf-8') == 'ticket feature\n'
    assert git(repo, 'diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD') == 'README.md\nfeature.txt'


@pytest.mark.parametrize('outcome', ['cancelled', 'failed'])
def test_uncompleted_worktree_keeps_edits_without_committing_until_abandoned(dispatch, repo, outcome):
    """Cancelled and failed tickets retain unfinished edits until expiry without creating commits."""
    from metaform.data import Store
    from metaform.modules.dispatch.merge import abandoned, branch_of, worktree_for
    store = Store('proj')
    folder = worktree_for(repo, dispatch.id)
    head = git(folder, 'rev-parse', 'HEAD')
    (folder / 'half.txt').write_text('half done\n', encoding='utf-8')
    store.finish_work(dispatch.id, 'Work stopped.', 'No accepted result.', outcome=outcome)
    from metaform.module import context
    from metaform.modules.dispatch.merge import finished
    assert finished(context('dispatch', repo, project='proj'), store, store.ticket(dispatch.id).work, folder) is None
    branch = branch_of(dispatch.id)
    assert git(repo, 'rev-parse', branch) == head
    assert (folder / 'half.txt').read_text() == 'half done\n'
    assert abandoned(store, repo, 30) == [], 'kept while younger than the setting'
    assert abandoned(store, repo, 0) == [branch]
    assert not git(repo, 'branch', '--list', branch)
    assert not folder.exists()


def test_the_shared_checkout_is_never_committed_or_removed_by_a_tickets_completion(dispatch, repo):
    """2026-10-15: a resumed session handed the project's own checkout to the completion step, which committed every
    agent's uncommitted work under one ticket; only a worktree, whose .git is a file, is committed or removed."""
    from metaform.modules.dispatch.merge import checkpoint, finished
    head = git(repo, 'rev-parse', 'HEAD')
    (repo / 'README.md').write_text('someone else\'s work\n', encoding='utf-8')
    assert checkpoint(repo, 'w1', 'work: not mine') is None
    assert finished(None, dispatch.store, None, repo) is None  # type: ignore[arg-type]
    assert git(repo, 'rev-parse', 'HEAD') == head and repo.is_dir()
    assert git(repo, 'status', '--porcelain') == 'M README.md'


@pytest.mark.parametrize('board', ['', 'release'])
def test_shared_completion_preserves_peer_edits_and_carries_ticket_record(dispatch, repo, monkeypatch, board):
    from metaform.data import Store
    from metaform.modules.dispatch.merge import capture_state
    from metaform.modules.dispatch.tests.test_completion_commit import session_for

    dispatch.store.edit_work(dispatch.id, {'title': 'Owned feature'})
    with Store('proj', module='map').tables() as tx:
        if board:
            tx.insert('boards', {'name': board, 'created': '2026-10-21T00:00:00Z'})
        tx.insert('ticket_settings', {'work_id': dispatch.id, 'board': board or None})
    (repo / 'peer.txt').write_text('peer staged\n')
    git(repo, 'add', 'peer.txt')
    (repo / 'peer.txt').write_text('peer unstaged\n')
    made = session_for(dispatch)
    made.acp['ticket_git'] = {'baseline': capture_state(repo), 'files': {}, 'result': None}
    made.sources = {'README.md': [{'kind': 'element', 'id': 'owned', 'address': 'code.owned'}]}
    changes = []

    async def note(*args):
        pass

    async def publish(topic, payload):
        changes.append((topic, payload))

    monkeypatch.setattr(made, 'note', note)
    monkeypatch.setattr(made.ctx, 'publish_async', publish)

    async def scenario():
        await made.write_text_file('test', str(repo / 'README.md'), 'owned feature\n')
        dispatch.store.finish_work(dispatch.id, 'Feature delivered.', 'Keep history independently readable.')
        await made.commit_done()
        await made.commit_done()

    asyncio.run(scenario())
    handle = dispatch.store.numbers_of('work', [dispatch.id])[dispatch.id][0]
    message = git(repo, 'log', '-1', '--format=%B')
    assert message.splitlines()[0] == 'Owned feature'
    assert 'Feature delivered.\n\nWhy: Keep history independently readable.' in message
    assert 'Metaform-Target: element:code.engine' in message
    assert message.splitlines()[-5:] == [f'Metaform-Ticket: {dispatch.id}', f'Metaform-Number: {handle}',
                                        'Metaform-Node: code.engine', f'Metaform-Board: {board}'.rstrip(),
                                        f'Metaform-Agent: claude {made.name}']
    assert git(repo, 'show', '--format=', '--name-only', 'HEAD') == 'README.md'
    assert git(repo, 'show', ':peer.txt') == 'peer staged'
    assert (repo / 'peer.txt').read_text() == 'peer unstaged\n'
    assert git(repo, 'rev-list', '--count', 'HEAD') == '2'
    commits = [payload for topic, payload in changes if topic == 'map.changed' and payload.get('kinds') == ['commit']]
    assert len(commits) == 1 and commits[0]['work_ids'] == [dispatch.id]


def test_empty_shared_completion_commits_once_without_claiming_peer_staging(dispatch, repo):
    from metaform.modules.dispatch.tests.test_completion_commit import session_for

    head = git(repo, 'rev-parse', 'HEAD')
    (repo / 'README.md').write_text('peer staged\n')
    git(repo, 'add', 'README.md')
    made = session_for(dispatch)
    made.acp['ticket_git'] = {'baseline': None, 'files': {}, 'result': None}
    dispatch.store.finish_work(dispatch.id, 'No files required.', 'Existing behavior already meets requirements.')

    async def scenario():
        await made.commit_done()
        await made.commit_done()

    asyncio.run(scenario())
    assert git(repo, 'rev-parse', 'HEAD') != head
    assert git(repo, 'rev-parse', 'HEAD^{tree}') == git(repo, 'rev-parse', f'{head}^{{tree}}')
    assert git(repo, 'rev-list', '--count', 'HEAD') == '2'
    assert git(repo, 'show', ':README.md') == 'peer staged'
    assert f'Metaform-Ticket: {dispatch.id}' in git(repo, 'log', '-1', '--format=%B')


@pytest.mark.parametrize('outcome', ['cancelled', 'failed'])
def test_uncompleted_shared_ticket_makes_no_commit(dispatch, repo, outcome):
    from metaform.modules.dispatch.merge import capture_state
    from metaform.modules.dispatch.tests.test_completion_commit import session_for

    head = git(repo, 'rev-parse', 'HEAD')
    made = session_for(dispatch)
    made.acp['ticket_git'] = {'baseline': capture_state(repo), 'files': {}, 'result': None}
    dispatch.store.finish_work(dispatch.id, 'Work stopped.', 'No accepted result.', outcome=outcome)
    asyncio.run(made.commit_done())
    assert git(repo, 'rev-parse', 'HEAD') == head
    assert made.acp['ticket_git']['result'] is None


def test_empty_worktree_completion_saves_empty_ticket_commit_without_publishing(dispatch, repo):
    from metaform.module import context
    from metaform.modules.dispatch.merge import finished, worktree_for

    head = git(repo, 'rev-parse', 'HEAD')
    folder = worktree_for(repo, dispatch.id)
    record = dispatch.store.finish_work(dispatch.id, 'No changes required.', 'Existing behavior suffices.')
    ctx = context('dispatch', repo, project='proj')
    result = finished(ctx, dispatch.store, record, folder)
    assert result['state'] == 'committed'
    assert result['evidence']['artifacts'] == []
    assert git(repo, 'rev-parse', 'HEAD') == head
    assert git(folder, 'rev-list', '--count', 'HEAD') == '2'
    assert git(folder, 'rev-parse', 'HEAD^{tree}') == git(repo, 'rev-parse', f'{head}^{{tree}}')
    message = git(folder, 'log', '-1', '--format=%B')
    assert 'No changes required.\n\nWhy: Existing behavior suffices.' in message
    assert message.count('Metaform-') == 6


def test_missing_completion_commit_files_one_numbered_broken_ticket(dispatch, repo, monkeypatch):
    from metaform.data import Node, Store
    from metaform.modules.dispatch.merge import file_fingerprint
    from metaform.modules.dispatch.orchestration import TRANSPORT
    from metaform.modules.dispatch.tests.test_completion_commit import session_for

    dispatch.store.add_element('parts', 'code.dispatcher.agent')
    with Store('proj', module='map').tables() as tx:
        tx.insert('boards', {'name': 'release', 'created': '2026-10-21T00:00:00Z'})
        tx.insert('ticket_settings', {'work_id': dispatch.id, 'board': 'release'})
    made = session_for(dispatch)
    (repo / 'README.md').write_text('owned edit\n')
    made.sources = {'README.md': [{'kind': 'element', 'id': 'owned', 'address': 'code.owned'}]}
    made.acp['ticket_git'] = {'baseline': None,
                              'files': {'README.md': file_fingerprint(repo, 'README.md')}, 'result': None}
    monkeypatch.setattr(TRANSPORT, 'notify_user', lambda *args: None)
    dispatch.store.finish_work(dispatch.id, 'Owned edit completed.', 'Deliver requested change.')

    async def scenario():
        await made.commit_done()
        await made.commit_done()

    asyncio.run(scenario())
    [fault] = dispatch.store.work(node=Node('element', 'code.dispatcher.agent'), open=True, limit=0).results
    handle = dispatch.store.numbers_of('work', [dispatch.id])[dispatch.id][0]
    numbered = dispatch.store.numbers_of('work', [fault.id])[fault.id]
    assert fault.condition == fault.kind == 'broken'
    assert numbered[1] == f'Missing commit for {handle}'
    with Store('proj', module='map').tables(write=False) as tx:
        assert tx.get('ticket_settings', {'work_id': fault.id})['board'] == 'release'
    assert git(repo, 'rev-list', '--count', 'HEAD') == '1'


def test_proof_landing_commit_retains_resolution_reason(dispatch, repo):
    from metaform.modules.dispatch.tests.test_completion_commit import session_for

    made = session_for(dispatch)
    made.acp['ticket_git'] = {'baseline': {}, 'files': {}, 'result': None}
    dispatch.store.prove_work(dispatch.id)
    record = dispatch.store.finish_work(dispatch.id, 'Fix landed.', 'Keep the required behavior.')
    assert record.done
    asyncio.run(made.commit_done())
    assert 'Fix landed.\n\nWhy: Keep the required behavior.' in git(repo, 'log', '-1', '--format=%B')


def test_failed_checks_save_completed_work_and_retry_saves_later_edits_once(dispatch, repo, run, monkeypatch):
    from metaform.module import context
    from metaform.modules.dispatch.merge import finished, worktree_for

    folder = worktree_for(repo, dispatch.id)
    (folder / 'feature.txt').write_text('ticket feature\n')
    run('set', '--dispatch-test-command=false', cwd=repo)
    monkeypatch.setenv('METAFORM_TASK_NAME', 'project_agent')
    shared_head = git(repo, 'rev-parse', 'HEAD')
    record = dispatch.store.finish_work(dispatch.id, 'Feature completed.', 'Deliver accepted behavior.')
    assert record.done
    ctx = context('dispatch', repo, project='proj')
    failed = finished(ctx, dispatch.store, record, folder)
    assert failed['state'] == 'failed' and failed['reason']
    assert failed['evidence']['verification']['passed'] is False
    assert failed['evidence']['artifacts'] == ['feature.txt']
    assert git(folder, 'show', 'HEAD:feature.txt') == 'ticket feature'
    assert git(folder, 'rev-list', '--count', 'HEAD') == '2'
    assert dispatch.store.complete_delivery(dispatch.id).done
    head = git(folder, 'rev-parse', 'HEAD')
    assert failed['head'] == head
    assert finished(ctx, dispatch.store, record, folder)['state'] == 'failed'
    assert git(folder, 'rev-parse', 'HEAD') == head
    (folder / 'README.md').write_text('later edit\n')
    monkeypatch.delenv('METAFORM_TASK_NAME')
    run('set', '--dispatch-test-command=true', cwd=repo)
    monkeypatch.setenv('METAFORM_TASK_NAME', 'project_agent')
    saved = finished(ctx, dispatch.store, record, folder)
    assert saved['state'] == 'committed'
    assert saved['evidence']['verification']['passed'] is True
    assert dispatch.store.complete_delivery(dispatch.id).done
    assert git(folder, 'show', 'HEAD:README.md') == 'later edit'
    assert git(folder, 'status', '--porcelain') == ''
    assert (repo / 'README.md').read_text() == 'base\n'
    assert git(folder, 'rev-list', '--count', 'HEAD') == '3'
    assert finished(ctx, dispatch.store, record, folder)['head'] == saved['head']
    assert git(folder, 'rev-list', '--count', 'HEAD') == '3'
    assert git(repo, 'rev-parse', 'origin/dev') == git(repo, 'rev-parse', 'HEAD') == shared_head


@pytest.mark.parametrize('during_checks', [False, True])
def test_ready_merge_rechecks_cancellation_before_committing(dispatch, repo, monkeypatch, during_checks):
    from metaform.module import context
    merge = importlib.import_module('metaform.modules.dispatch.merge')

    waiting_merge(dispatch, repo)
    ctx = context('dispatch', repo, project='proj')
    merge = importlib.import_module('metaform.modules.dispatch.merge')
    head = git(repo, 'rev-parse', 'HEAD')

    def cancel():
        dispatch.store.move_work(dispatch.id, 'todo')
        dispatch.store.finish_work(dispatch.id, 'Cancelled.', 'No longer required.', outcome='cancelled')

    if during_checks:
        def tests_pass(*args):
            cancel()
            return True, ''
        monkeypatch.setattr(merge, 'tests_pass', tests_pass)
    else:
        cancel()
    assert not merge.merge_due(ctx, dispatch.store, dispatch.id, publish=True)['merged']
    assert git(repo, 'rev-parse', 'HEAD') == head


def test_worktree_commit_exception_files_missing_commit_fault(dispatch, repo, monkeypatch):
    from metaform.data import Node
    from metaform.module import context
    merge = importlib.import_module('metaform.modules.dispatch.merge')

    dispatch.store.add_element('parts', 'code.dispatcher.agent')
    folder = merge.worktree_for(repo, dispatch.id)
    record = dispatch.store.finish_work(dispatch.id, 'Feature completed.', 'Deliver accepted behavior.')

    def unavailable(*args, **kwargs):
        raise OSError('Git unavailable')

    monkeypatch.setattr(merge, 'checkpoint', unavailable)
    assert merge.finished(context('dispatch', repo, project='proj'), dispatch.store, record, folder) is None
    [fault] = dispatch.store.work(node=Node('element', 'code.dispatcher.agent'), open=True, limit=0).results
    assert fault.kind == 'broken' and 'Git unavailable' in fault.task


def test_existing_checkpoint_trailer_does_not_replace_completed_ticket_record(dispatch, repo):
    from metaform.modules.dispatch.tests.test_completion_commit import session_for

    git(repo, 'commit', '--allow-empty', '-qm', 'Manual checkpoint', '-m', f'Metaform-Ticket: {dispatch.id}')
    made = session_for(dispatch)
    made.acp['ticket_git'] = {'baseline': {}, 'files': {}, 'result': None}
    dispatch.store.finish_work(dispatch.id, 'Ticket completed.', 'Preserve the final record.')
    asyncio.run(made.commit_done())
    assert git(repo, 'rev-list', '--count', 'HEAD') == '3'
    message = git(repo, 'log', '-1', '--format=%B')
    assert 'Ticket completed.\n\nWhy: Preserve the final record.' in message
    assert message.count('Metaform-') == 6


def test_already_landed_merge_recovers_after_ticket_cancellation(dispatch, repo, monkeypatch):
    from metaform.module import context
    merge = importlib.import_module('metaform.modules.dispatch.merge')

    waiting = waiting_merge(dispatch, repo)
    ctx = context('dispatch', repo, project='proj')
    merge = importlib.import_module('metaform.modules.dispatch.merge')
    real = _killed_at(monkeypatch, 'update-ref')
    with pytest.raises(SystemExit):
        result = merge.merge_due(ctx, dispatch.store, dispatch.id, publish=True)
        pytest.fail(f'Merge never reached the crash point: {result}')
    monkeypatch.setattr(merge, 'git', real)
    head = git(repo, 'rev-parse', 'HEAD')
    dispatch.store.move_work(dispatch.id, 'todo')
    dispatch.store.finish_work(dispatch.id, 'Cancelled.', 'No longer required.', outcome='cancelled')
    assert merge.merge_due(ctx, dispatch.store, dispatch.id, publish=True)['merged']
    assert git(repo, 'rev-parse', 'HEAD') == head
    assert (repo / waiting['worktree']).exists()
