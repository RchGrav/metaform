"""Stage 1, step 1: projects, settings with glue, status and help, through the real CLI."""
import json


def test_status_runs_with_zero_config(run, home):
    out = run().stdout
    assert 'Metaform' in out
    assert str(home) in out


def test_add_and_list_projects(run, tmp_path):
    work = tmp_path / 'work'
    work.mkdir()
    run('add', 'project', 'demo', str(work))
    listed = run('list', 'projects').stdout
    assert 'demo' in listed and str(work) in listed


def test_folder_project_is_the_default(run, tmp_path):
    work = tmp_path / 'work'
    (work / 'sub').mkdir(parents=True)
    run('add', 'project', 'demo', str(work))
    assert 'Project: demo' in run(cwd=work / 'sub').stdout
    assert 'Project: none' in run(cwd=tmp_path).stdout


def test_set_project_selects_another_and_unset_returns_home(run, tmp_path):
    a, b = tmp_path / 'a', tmp_path / 'b'
    a.mkdir(); b.mkdir()
    run('add', 'project', 'alpha', str(a))
    run('add', 'project', 'beta', str(b))
    run('set', '--project', 'beta', cwd=a)
    assert 'Project: beta' in run(cwd=a).stdout
    # The selection belongs to the folder it was made in.
    assert 'Project: beta' in run(cwd=b).stdout
    assert 'Project: alpha' not in run(cwd=b).stdout
    run('unset', '--project', cwd=a)
    assert 'Project: alpha' in run(cwd=a).stdout


def test_set_rejects_an_unknown_project(run, tmp_path):
    result = run('set', '--project', 'ghost', ok=False)
    assert result.returncode != 0
    assert 'ghost' in result.stderr
    assert 'metaform list projects' in result.stderr


def test_glue_cycle_matches_mvm(run, tmp_path):
    a, b = tmp_path / 'a', tmp_path / 'b'
    a.mkdir(); b.mkdir()
    run('add', 'project', 'alpha', str(a))
    run('add', 'project', 'beta', str(b))
    out = run('set', '--project', 'beta', '--glue', cwd=a).stdout
    assert 'Success: updated 1 key' in out
    assert 'project: alpha → beta' in out
    assert 'glued: project' in out
    out = run('unset', 'all', cwd=a).stdout
    assert 'No settings required reset' in out
    assert 'Skipped (glued): project' in out
    assert 'Project: beta' in run(cwd=a).stdout
    out = run('unset', 'all', '--unglue', cwd=a).stdout
    assert 'Reset 1 setting(s): project' in out
    assert 'Unglued: project' in out
    assert 'Project: alpha' in run(cwd=a).stdout


def test_set_with_no_change_says_so(run):
    assert 'Success: no changes' in run('set').stdout


def test_unset_all_is_a_noun_and_dash_all_is_not_a_setting(run):
    result = run('unset', '--all', ok=False)
    assert result.returncode != 0
    assert 'metaform unset all' in result.stderr


def test_config_show_prints_every_setting_with_state(run, tmp_path):
    work = tmp_path / 'work'
    work.mkdir()
    run('add', 'project', 'demo', str(work))
    shown = json.loads(run('config', '--show', '--json', cwd=work).stdout)
    by_key = {item['key']: item for item in shown}
    assert by_key['project']['value'] == 'demo'
    assert by_key['project']['state'] == 'default'
    run('set', '--project', 'demo', '--glue', cwd=work)
    shown = json.loads(run('config', '--show', '--json', cwd=work).stdout)
    assert {item['key']: item for item in shown}['project']['state'] == 'glued'


def test_help_overview_is_brief_and_ends_with_tips(run):
    out = run('help').stdout
    assert len(out.splitlines()) <= 25
    for tip in ('metaform help intro', 'metaform help commands', 'metaform help switches',
                'metaform config --show'):
        assert tip in out


def test_man_page_and_syntax_are_different_outputs(run):
    page = run('help', 'set').stdout
    syntax = run('set', '--help').stdout
    assert page != syntax
    assert 'Usage' in syntax and 'Usage' in page
    assert 'Details' in page and 'Details' not in syntax
    assert run('set', '-h').stdout == syntax


def test_indexes_list_commands_and_switches(run):
    commands = run('help', 'commands').stdout
    for verb in ('add', 'list', 'set', 'unset', 'config', 'help'):
        assert verb in commands
    switches = run('help', 'switches').stdout
    for switch in ('--project', '--glue', '--unglue'):
        assert switch in switches
    assert '--all' not in switches


def test_switch_has_its_own_page(run):
    assert 'glue' in run('help', '--glue').stdout.lower()


def test_unknown_command_names_the_next_step(run):
    result = run('frobnicate', ok=False)
    assert result.returncode != 0
    assert 'metaform help commands' in result.stderr
