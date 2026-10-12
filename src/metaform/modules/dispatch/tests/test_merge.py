"""VIEW-044: a done ticket's worktree waits for review, then merges into the active dev branch and is logged; a review
takes it over for good; with no test command nothing is offered. A real git repository and the fake agent, no model."""
import json
import subprocess

import pytest

from metaform.modules.dispatch.tests.test_dispatch import dispatch as dispatch  # noqa: PLC0414 fixture re-export

pytestmark = [pytest.mark.req('VIEW-044'), pytest.mark.kind('simulation')]


def git(folder, *words):
    return subprocess.run(['git', *words], cwd=folder, capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def repo(dispatch, run):
    """The project folder as a git repository on its dev branch, with worktrees on and a test command that passes."""
    folder = dispatch.folder
    git(folder, 'init', '-q', '-b', 'dev')
    git(folder, 'config', 'user.email', 'test@example.com')
    git(folder, 'config', 'user.name', 'Test')
    (folder / 'README.md').write_text('base\n', encoding='utf-8')
    git(folder, 'add', '-A')
    git(folder, 'commit', '-q', '-m', 'base')
    run('set', '--dispatch-worktrees', '--dispatch-test-command=true', cwd=folder)
    return folder


def worked(dispatch, repo):
    """The fake agent closes its ticket after changing a file in the folder it works in."""
    dispatch.start('done', FAKE_ACP_EDIT='feature.txt')
    assert dispatch.process.wait(30) == 0, dispatch.process.stderr.read().decode()
    found = json.loads(dispatch.run('dispatch', 'merges', '--json', cwd=repo).stdout)['merges']
    return found


def test_a_done_ticket_in_its_own_worktree_waits_for_review_then_merges_and_is_logged(dispatch, repo, run):
    [waiting] = worked(dispatch, repo)
    assert waiting['state'] == 'ready' and waiting['branch'].startswith('metaform/')
    assert '.worktrees' in waiting['worktree'] and (repo / '.worktrees').is_dir()
    assert not (repo / 'feature.txt').exists(), 'the agent worked in its worktree, not the project folder'
    merged = json.loads(run('dispatch', 'merge', dispatch.id, '--json', cwd=repo).stdout)
    assert merged['merged'] is True, merged
    assert (repo / 'feature.txt').read_text(encoding='utf-8') == 'changed by the fake agent\n'
    assert git(repo, 'branch', '--show-current') == 'dev'
    logged = [record for record in dispatch.store.work(open=True, limit=0).results
              if 'needs testing before the next release' in (record.task or '')]
    assert len(logged) == 1 and logged[0].condition == ''
    assert json.loads(run('dispatch', 'merges', '--json', cwd=repo).stdout)['merges'] == []


def test_review_takes_the_merge_over_for_good(dispatch, repo, run):
    worked(dispatch, repo)
    assert json.loads(run('dispatch', 'review', dispatch.id, '--json', cwd=repo).stdout)['state'] == 'review'
    merged = json.loads(run('dispatch', 'merge', dispatch.id, '--json', cwd=repo).stdout)
    assert merged['merged'] is False and not (repo / 'feature.txt').exists(), 'a reviewed merge never merges by itself'
    again = run('dispatch', 'review', dispatch.id, cwd=repo, ok=False)
    assert again.returncode != 0, 'the countdown never restarts'


def test_with_no_test_command_no_merge_is_offered(dispatch, repo, run):
    run('set', '--dispatch-test-command=', cwd=repo)
    assert worked(dispatch, repo) == []


def test_work_that_clashes_with_the_dev_branch_is_never_merged(dispatch, repo, run):
    worked(dispatch, repo)
    (repo / 'feature.txt').write_text('changed on dev meanwhile\n', encoding='utf-8')
    git(repo, 'add', '-A')
    git(repo, 'commit', '-q', '-m', 'ongoing work')
    merged = json.loads(run('dispatch', 'merge', dispatch.id, '--json', cwd=repo).stdout)
    assert merged['merged'] is False and 'conflict' in merged['why'].lower(), merged
    assert (repo / 'feature.txt').read_text(encoding='utf-8') == 'changed on dev meanwhile\n'
    assert git(repo, 'status', '--porcelain') == '', 'a refused merge leaves the dev branch untouched'


def test_the_agent_asked_to_help_works_in_the_merges_worktree_with_the_prep_prompt(dispatch, repo, run, monkeypatch,
                                                                                  dispatch_runners):
    from metaform.modules.dispatch.tests.test_dispatch import eventually
    [waiting] = worked(dispatch, repo)
    run('dispatch', 'review', dispatch.id, cwd=repo)
    run('map', 'work', 'op=edit', f'id={dispatch.id}', 'agent=claude', cwd=repo)
    for name, value in dispatch.env('hold').items():
        monkeypatch.setenv(name, value)
    started = json.loads(run('dispatch', 'prep', dispatch.id, '--json', cwd=repo).stdout)
    dispatch_runners.append((started, repo, dispatch.log))
    said = eventually(lambda: [message for message in dispatch.received('session/new')[1:]] or None)
    assert said[0]['params']['cwd'] == waiting['worktree'], 'the helping agent works in the merge\'s worktree'
    [text] = eventually(lambda: [message['params']['prompt'][0]['text'] for message in dispatch.received('session/prompt')
                                 if 'Do not merge into' in message['params']['prompt'][0]['text']] or None)
    assert waiting['branch'] in text and 'Do not merge into dev' in text
    assert dispatch.ticket().done, 'the done ticket is not taken again'


@pytest.mark.req('BASE-052')
def test_a_worktree_begins_from_uncommitted_work_and_merges_only_the_agents_work_squashed(dispatch, repo, run):
    """P009, P018: the worktree branches from a snapshot of the folder with its uncommitted change; the agent's work
    is committed with the ticket's trailer; a folder with uncommitted changes holds the merge; once committed, the
    agent's work alone lands as one commit fast-forwarded onto dev, and its worktree, branch and snapshot are gone."""
    (repo / 'README.md').write_text('base\nuncommitted line\n', encoding='utf-8')
    (repo / 'draft.txt').write_text('an untracked draft\n', encoding='utf-8')
    [waiting] = worked(dispatch, repo)
    tree = repo / waiting['worktree']
    assert (tree / 'draft.txt').read_text(encoding='utf-8') == 'an untracked draft\n', 'uncommitted work came along'
    assert f'Metaform-Ticket: {dispatch.id}' in git(tree, 'log', '-1', '--format=%B')
    held = json.loads(run('dispatch', 'merge', dispatch.id, '--json', cwd=repo).stdout)
    assert held['merged'] is False and 'uncommitted' in held['why']
    git(repo, 'add', '-A')
    git(repo, 'commit', '-q', '-m', 'the person commits their own work')
    merged = json.loads(run('dispatch', 'merge', dispatch.id, '--json', cwd=repo).stdout)
    assert merged['merged'] is True, merged
    assert git(repo, 'log', '-1', '--format=%B').count('Metaform-Ticket') == 1
    assert git(repo, 'show', '--stat', '--format=', 'HEAD').split('|')[0].strip() == 'feature.txt', \
        'the merged commit holds the agent\'s work alone'
    assert not tree.exists() and not git(repo, 'branch', '--list', waiting['branch'])
    assert not git(repo, 'for-each-ref', 'refs/metaform/')


def test_a_cancelled_tickets_work_is_kept_on_its_branch_until_abandoned(dispatch, repo, run):
    """P192, P017: a ticket closed without completing is not offered; its work is committed on its branch and its
    worktree removed; past dispatch_abandoned_branch_days the branch goes too, at recovery."""
    from metaform.data import Store
    from metaform.modules.dispatch.merge import abandoned, branch_of, worktree_for
    store = Store('proj')
    folder = worktree_for(repo, dispatch.id)
    (folder / 'half.txt').write_text('half done\n', encoding='utf-8')
    store.finish_work(dispatch.id, 'Cancelled: no longer needed', 'cancelled by the person', outcome='cancelled')
    from metaform.module import context
    from metaform.modules.dispatch.merge import finished
    assert finished(context('dispatch', repo, project='proj'), store, store.ticket(dispatch.id).work, folder) is None
    branch = branch_of(dispatch.id)
    assert not folder.exists() and 'half.txt' in git(repo, 'show', '--stat', '--format=', branch)
    assert abandoned(store, repo, 30) == [], 'kept while younger than the setting'
    assert abandoned(store, repo, 0) == [branch]
    assert not git(repo, 'branch', '--list', branch)
