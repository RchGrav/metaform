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
