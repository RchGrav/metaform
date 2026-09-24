"""Stage 1, step 1: projects, settings with glue, status and help, through the real CLI."""
import json

import pytest


def lines(result):
    return result.stdout.splitlines()


def test_status_runs_with_zero_config(run, home):
    out = run().stdout
    assert out.splitlines()[0].startswith('Metaform ')
    assert f'Home: {home}' in out.splitlines()


def test_add_and_list_projects(run, tmp_path):
    work = tmp_path / 'work'
    work.mkdir()
    run('add', 'project', 'demo', str(work))
    rows = [line.split() for line in lines(run('list', 'projects'))]
    assert ['demo', str(work)] in rows


def test_folder_project_is_the_default_and_the_deepest_wins(run, tmp_path):
    outer, inner = tmp_path / 'outer', tmp_path / 'outer' / 'inner'
    (inner / 'deep').mkdir(parents=True)
    run('add', 'project', 'outer', str(outer))
    run('add', 'project', 'inner', str(inner))
    assert 'Project: inner' in run(cwd=inner / 'deep').stdout
    assert 'Project: outer' in run(cwd=outer).stdout
    assert 'Project: none' in run(cwd=tmp_path).stdout


def test_set_project_belongs_to_its_folder_and_its_subfolders(run, tmp_path):
    a, b, c = tmp_path / 'a', tmp_path / 'b', tmp_path / 'c'
    (a / 'sub').mkdir(parents=True); b.mkdir(); c.mkdir()
    run('add', 'project', 'alpha', str(a))
    run('add', 'project', 'beta', str(b))
    run('add', 'project', 'gamma', str(c))
    run('set', '--project', 'beta', cwd=a)
    assert 'Project: beta' in run(cwd=a).stdout
    assert 'Project: beta' in run(cwd=a / 'sub').stdout
    other = run(cwd=c).stdout
    assert 'Project: gamma' in other and '[selected here]' not in other
    run('unset', '--project', cwd=a)
    assert 'Project: alpha' in run(cwd=a).stdout


def test_set_rejects_an_unknown_project(run):
    result = run('set', '--project', 'ghost', ok=False)
    assert result.returncode == 2
    assert result.stderr.splitlines() == ["Error: --project has no choice 'ghost'. Choices: none yet.",
                                          'Next: metaform list projects']


def test_glue_cycle_matches_mvm_line_for_line(run, tmp_path):
    a, b = tmp_path / 'a', tmp_path / 'b'
    a.mkdir(); b.mkdir()
    run('add', 'project', 'alpha', str(a))
    run('add', 'project', 'beta', str(b))
    assert lines(run('set', '--project', 'beta', '--glue', cwd=a)) == [
        'Success: updated 1 key', '  project: alpha → beta', '  glued: project']
    assert lines(run('set', '--greeting', 'hi', cwd=a)) == [
        'Success: updated 1 key', '  greeting: hello → hi']
    assert lines(run('unset', 'all', cwd=a)) == [
        'Reset 1 setting(s): greeting', 'Skipped (glued): project']
    assert 'Project: beta' in run(cwd=a).stdout
    assert lines(run('unset', 'all', '--unglue', cwd=a)) == [
        'Reset 1 setting(s): project', 'Unglued: project']
    shown = {row['key']: row for row in json.loads(run('config', '--show', '--json', cwd=a).stdout)}
    assert shown['project']['state'] == 'default' and shown['project']['value'] == 'alpha'


def test_setting_the_same_value_again_is_no_change(run, tmp_path):
    work = tmp_path / 'work'
    work.mkdir()
    run('add', 'project', 'demo', str(work))
    run('set', '--greeting', 'hi', cwd=work)
    assert lines(run('set', '--greeting', 'hi', cwd=work)) == ['Success: no changes']


def test_unset_all_is_a_noun_and_dash_all_is_not_a_setting(run):
    result = run('unset', '--all', ok=False)
    assert result.stderr.splitlines() == ['Error: --all is not a setting. A switch names one setting.',
                                          'Next: metaform unset all']


def test_config_show_reports_default_set_and_glued(run, tmp_path):
    work = tmp_path / 'work'
    work.mkdir()
    run('add', 'project', 'demo', str(work))
    state = lambda: {row['key']: row['state'] for row in json.loads(run('config', '--show', '--json', cwd=work).stdout)}
    assert state()['greeting'] == 'default'
    run('set', '--greeting', 'hi', cwd=work)
    assert state()['greeting'] == 'set'
    run('set', '--greeting', 'hi', '--glue', cwd=work)
    assert state()['greeting'] == 'glued'


def test_help_overview_is_brief_and_ends_with_tips(run):
    out = lines(run('help'))
    assert len(out) <= 25
    assert out[-5:] == ['Tips:', '  - start here: metaform help intro',
                        "  - run 'metaform help commands' for an index of all commands",
                        "  - run 'metaform help switches' for all switches",
                        "  - run 'metaform config --show' to inspect your saved defaults."]


@pytest.mark.parametrize('command', ['help', 'add', 'list', 'set', 'unset', 'config', 'enable', 'disable'])
def test_every_chassis_command_has_a_man_page_and_a_separate_syntax(run, command):
    page = run('help', command).stdout
    syntax = run(command, '--help').stdout
    assert run(command, '-h').stdout == syntax
    assert page.startswith(f'{command} — ')
    assert syntax.startswith('Usage: ')
    assert page != syntax


def test_indexes_list_each_command_and_switch_as_a_row(run):
    rows = {line.split()[0] for line in lines(run('help', 'commands')) if line.startswith('  ')}
    assert {'add', 'list', 'set', 'unset', 'config', 'help', 'enable', 'disable'} <= rows
    switches = {line.split()[0] for line in lines(run('help', 'switches')) if line.startswith('  ')}
    assert {'--project', '--commands', '--greeting', '--glue', '--unglue'} <= switches
    assert '--all' not in switches


def test_switch_page_is_its_own(run):
    page = run('help', '--glue').stdout
    assert page.startswith('--glue — ')
    assert 'Used by: set' in page
    assert page not in (run('help', 'switches').stdout, run('help', '--unglue').stdout)


def test_every_error_names_exactly_one_next_command(run):
    for args in (['frobnicate'], ['add'], ['list', 'things'], ['set', '--nope', 'x'],
                 ['unset', 'banana'], ['help', 'nothing'], ['enable', 'module', 'ghost'],
                 ['template', 'shout']):
        result = run(*args, ok=False)
        err = result.stderr.splitlines()
        assert result.returncode == 2, args
        assert len(err) == 2 and err[0].startswith('Error: ') and err[1].startswith('Next: metaform '), (args, err)
