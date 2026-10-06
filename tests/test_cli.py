"""The command line: grammar, help, errors, settings and context, CLI, through the real CLI."""
from __future__ import annotations

import json
import os
import re
import signal
import sqlite3
import subprocess
import sys
import time

import pytest

from metaform import __version__


def own(project_id):
    """A project's folder in the home, PROJ-026."""
    from metaform import home as metaform_home
    return metaform_home.project_folder(project_id)

pytestmark = pytest.mark.kind('fixture')

OS = "SUPPORTED_OS = ('linux', 'macos', 'windows')"


def lines(result):
    return result.stdout.splitlines()


def shown(run, cwd=None):
    return {row['key']: row for row in json.loads(run('config', '--show', '--json', cwd=cwd).stdout)}


@pytest.fixture
def toggles(user_module):
    """A module with a boolean switch `tmux` and a verb that reports it."""
    user_module('toggles', f'''
        from metaform import settings
        from metaform.module import Module, Verb
        {OS}
        settings.boolean('tmux', False, help='Run inside tmux.')
        settings.boolean('fast', False, help='Go fast.')
        settings.number('panes', 4, min=1, max=9, help='How many panes.')
        def show(ctx):
            return f"tmux={{ctx.setting('tmux')}}"
        MODULE = Module(id='toggles', summary='Toggles.', purpose='Toggles. Details: metaform help toggles.',
                        verbs=(Verb('show', show, 'Show tmux.', switches=('tmux',)),))
    ''')


@pytest.fixture
def project(run, tmp_path):
    folder = tmp_path / 'proj'
    (folder / 'src').mkdir(parents=True)
    run('add', 'project', 'proj', str(folder))
    return folder


def noted(run, project, text):
    """Write a note on the map by hand, which makes the project's first metaform when it has none. Memory did this
    before it became a graph of its own that never touches the map, LAYER-013."""
    run('map', 'knowledge', 'op=create', 'layer=notes', 'variable=Notes.', 'mutable=true', 'hideable=true',
        'module=test', cwd=project)
    run('map', 'knowledge', 'op=add-item', 'layer=notes', 'node=type:code.timer', f'value={json.dumps(text)}',
        cwd=project)


# Grammar ----------------------------------------------------------------------

@pytest.mark.req('CLI-001')
def test_an_undeclared_switch_is_refused_with_the_verbs_syntax_as_next(run, toggles):
    assert run('toggles', 'show', '--tmux').stdout == 'tmux=True'
    refused = run('toggles', 'show', '--colour', ok=False)
    assert refused.returncode == 2
    assert refused.stderr.splitlines()[-1] == 'Next: metaform toggles show --help'


@pytest.mark.req('CLI-002')
def test_all_is_an_argument_and_never_a_switch(run, toggles):
    refused = run('unset', '--all', ok=False)
    assert refused.returncode == 2
    assert refused.stderr.splitlines() == ['Error: --all is not a switch. all is an argument.', 'Next: metaform unset all']
    run('set', '--tmux', '--panes', '6')
    run('unset', 'all')
    assert {key: row['state'] for key, row in shown(run).items() if key in ('tmux', 'panes')} == \
        {'tmux': 'default', 'panes': 'default'}


@pytest.mark.req('CLI-003')
def test_a_word_after_the_double_dash_is_never_a_switch(run, toggles):
    refused = run('set', '--', '--tmux', ok=False)
    assert refused.returncode == 2 and "'--tmux'" in refused.stderr
    assert shown(run)['tmux']['state'] == 'default'


@pytest.mark.req('CLI-004')
def test_a_short_switch_is_one_letter_and_aliases_its_long_form(run, toggles):
    assert run('set', '--tmux', '-q').stdout == ''
    assert run('set', '--fast', '--quiet').stdout == ''
    refused = run('set', '--fast', '-quiet', ok=False)
    assert refused.returncode == 2 and '--quiet' in refused.stderr.splitlines()[-1]


@pytest.mark.req('CLI-015')
def test_booleans_have_two_forms_and_never_toggle(run, toggles):
    run('set', '--tmux')
    run('set', '--panes', '6')
    assert shown(run)['tmux']['value'] is True
    run('set', '--tmux')
    assert shown(run)['tmux']['value'] is True
    run('set', '--no-tmux')
    assert shown(run)['tmux']['value'] is False
    assert run('toggles', 'show', '--tmux').stdout == 'tmux=True'
    assert shown(run)['tmux']['value'] is False
    refused = run('set', '--tmux=true', ok=False)
    assert refused.returncode == 2


@pytest.mark.req('CLI-016')
@pytest.mark.req('CLI-013')
def test_a_glued_value_inverts_with_the_opposite_form_and_stays_glued(run, toggles):
    run('set', '--tmux', '--glue')
    run('set', '--no-tmux')
    assert (shown(run)['tmux']['value'], shown(run)['tmux']['state']) == (False, 'glued')
    run('unset', 'all')
    assert shown(run)['tmux']['value'] is False
    assert 'Skipped (glued): tmux' in lines(run('unset', '--tmux'))
    run('unset', '--tmux', '--unglue')
    assert shown(run)['tmux']['state'] == 'default'


@pytest.mark.req('CLI-017')
def test_unset_all_unglue_returns_every_setting_to_default(run, toggles, project):
    run('set', '--tmux', '--glue', cwd=project)
    run('set', '--panes', '7', cwd=project)
    run('set', '--project', 'proj', '--glue', cwd=project)
    out = lines(run('unset', 'all', '--unglue', cwd=project))
    assert out[0] == 'Reset three settings: project, tmux, panes'
    assert any(line.startswith('Unglued: ') for line in out)
    assert {row['state'] for row in shown(run, cwd=project).values()} == {'default'}


@pytest.mark.req('CLI-014')
def test_a_folder_setting_applies_below_until_a_deeper_folder_sets_its_own(run, toggles, tmp_path):
    parent, child = tmp_path / 'p', tmp_path / 'p' / 'c'
    child.mkdir(parents=True)
    run('set', '--panes', '3', cwd=parent)
    assert shown(run, cwd=child)['panes']['value'] == 3
    run('set', '--panes', '5', cwd=child)
    assert shown(run, cwd=child)['panes']['value'] == 5
    assert shown(run, cwd=parent)['panes']['value'] == 3


@pytest.mark.req('CLI-011')
@pytest.mark.req('CLI-027')
def test_values_of_each_kind_read_back_as_written(run, toggles, project):
    run('set', '--panes', '6', '--tmux', '--modules', 'chassis,toggles', cwd=project)
    got = shown(run, cwd=project)
    assert (got['panes']['value'], got['tmux']['value'], got['modules']['value']) == (6, True, ['chassis', 'toggles'])
    assert run('toggles', 'show', '--no-tmux', cwd=project).stdout == 'tmux=False'
    assert shown(run, cwd=project)['tmux']['value'] is True
    refused = run('set', '--panes', '12', cwd=project, ok=False)
    assert refused.returncode == 2 and refused.stderr.splitlines()[-1] == 'Next: metaform help --panes'


@pytest.mark.req('CLI-018')
def test_confirm_is_never_a_setting(run):
    refused = run('set', '--confirm', ok=False)
    assert refused.returncode == 2
    assert refused.stderr.splitlines() == ['Error: --confirm is not a setting.', 'Next: metaform help --confirm']


@pytest.mark.req('CLI-023')
def test_a_default_is_never_written_and_unknown_stored_keys_survive(run, toggles, home):
    run('config', '--show')
    run('set', '--panes', '5')
    db = sqlite3.connect(home / 'metaform.sqlite3')
    db.execute("INSERT INTO settings(scope, owner, key, position, value) VALUES ('global', 'gone', 'old', 0, '1')")
    db.commit()
    assert db.execute("SELECT key FROM settings WHERE owner='toggles'").fetchall() == [('panes',)]
    db.close()
    run('unset', 'all', '--unglue')
    db = sqlite3.connect(home / 'metaform.sqlite3')
    assert db.execute("SELECT COUNT(*) FROM settings WHERE owner='gone'").fetchone() == (1,)


@pytest.mark.req('CLI-024')
def test_a_modules_glued_setting_survives_its_absence(run, toggles):
    run('set', '--panes', '8', '--glue')
    run('disable', 'toggles')
    refused = run('set', '--panes', '2', ok=False)
    assert refused.returncode == 2 and refused.stderr.splitlines()[-1] == 'Next: metaform help switches'
    assert '--panes' not in run('help', 'switches').stdout
    run('enable', 'toggles')
    assert (shown(run)['panes']['value'], shown(run)['panes']['state']) == (8, 'glued')


@pytest.mark.req('STORE-004')
@pytest.mark.req('STORE-002')
def test_a_list_setting_is_stored_one_row_per_member(run, home, user_module):
    for name in 'abc':
        user_module(name, f'''
            from metaform.module import Module
            {OS}
            MODULE = Module(id='{name}', summary='{name}', purpose='{name}. Details: metaform help {name}.')
        ''')
    run('set', '--modules', 'a,b,c')
    db = sqlite3.connect(home / 'metaform.sqlite3')
    assert db.execute("SELECT position, value FROM settings WHERE key='modules' ORDER BY position").fetchall() == \
        [(0, '"a"'), (1, '"b"'), (2, '"c"')]


@pytest.mark.req('PROJ-002')
def test_reads_never_write_a_folder_row(run, home, tmp_path, project):
    for _ in range(3):
        run(cwd=tmp_path)
        run('config', '--show', cwd=tmp_path)
    chassis = home / 'metaform.sqlite3'
    if chassis.exists():
        db = sqlite3.connect(chassis)
        assert db.execute('SELECT COUNT(*) FROM folders').fetchone() == (0,)


# Context ----------------------------------------------------------------------

@pytest.mark.req('CLI-021')
@pytest.mark.req('PROJ-003')
def test_a_folder_inside_a_project_works_on_it_by_default(run, tmp_path, project):
    other = tmp_path / 'other'
    other.mkdir()
    run('add', 'project', 'other', str(other))
    assert 'Project: proj (' in run(cwd=project / 'src').stdout
    run('set', '--project', 'other', cwd=project)
    assert 'Project: other (' in run(cwd=project / 'src').stdout
    run('unset', '--project', cwd=project)
    assert 'Project: proj (' in run(cwd=project / 'src').stdout


@pytest.mark.req('PROJ-003')
def test_a_selection_above_a_project_does_not_reach_inside_it(run, tmp_path, project):
    other = tmp_path / 'other'
    other.mkdir()
    run('add', 'project', 'other', str(other))
    run('set', '--project', 'other', cwd=tmp_path)
    assert 'Project: other (' in run(cwd=tmp_path).stdout
    assert 'Project: proj (' in run(cwd=project / 'src').stdout


@pytest.mark.req('CLI-022')
@pytest.mark.req('CLI-008')
def test_narrowing_the_surface_hides_and_blocks_and_names_the_way_back(run, toggles):
    out = lines(run('set', '--modules', 'toggles'))
    assert out == ['Success: updated one key', '  modules: all → toggles', 'Commands shown here: toggles.',
                   'All other commands and help, including yours, are now hidden and will not run.',
                   'To restore them: metaform unset --modules']
    refused = run('list', 'projects', ok=False)
    assert refused.returncode == 2 and refused.stderr.splitlines()[-1] == 'Next: metaform unset --modules'
    rows = {line.split()[0] for line in lines(run('help', 'commands')) if line.startswith('  ')}
    assert 'list' not in rows and {'help', 'set', 'unset', 'config'} <= rows and 'toggles' in rows
    run('unset', '--modules')
    run('list', 'projects')


@pytest.mark.req('PROJ-007')
@pytest.mark.req('CLI-022')
def test_a_worker_folder_is_narrowed_from_the_orchestrators_folder(run, toggles, tmp_path):
    worker, orchestrator = tmp_path / 'worker', tmp_path / 'orchestrator'
    worker.mkdir()
    orchestrator.mkdir()
    out = lines(run('set', '--modules', 'toggles', f'folder={worker}', cwd=orchestrator))
    assert out[1] == '  modules: all → toggles'
    assert run('list', 'projects', cwd=worker, ok=False).returncode == 2
    run('list', 'projects', cwd=orchestrator)
    assert shown(run, cwd=worker)['modules']['value'] == ['toggles']


def entered(run, *modules, cwd=None):
    """What entering each module prints, in order: the listing an alias of those modules gives, CLI-039."""
    return '\n'.join(run(module, '--help', cwd=cwd).stdout for module in modules)


@pytest.mark.req('CLI-039')
def test_an_alias_is_one_name_at_the_top_that_lists_the_commands_of_its_modules(run):
    """Rich, 2026-10-03, question 16: its own chassis command, metaform alias <name> <module> <module>..."""
    assert lines(run('alias', 'mapping', 'map', 'memory')) == ['Success: mapping stands for map, memory']
    assert run('mapping').stdout == run('help', 'mapping').stdout == entered(run, 'map', 'memory')
    assert run('mapping', '--help').stdout == run('mapping', '-h').stdout == entered(run, 'map', 'memory')
    index = lines(run('help', 'commands'))
    found = [number for number, line in enumerate(index) if 'mapping' in line]
    assert len(found) == 1 and index[found[0] - 1] == 'Aliases'      # one line, none of its commands
    assert re.fullmatch(r'\s+mapping\s+map, memory', index[found[0]])
    refused = run('mapping', 'where', ok=False)
    assert refused.returncode == 2 and refused.stderr.splitlines()[-1] == 'Next: metaform mapping'
    run('alias', 'mapping', 'map', 'intake')                        # defining a name again replaces it
    assert run('mapping').stdout == entered(run, 'map', 'intake')
    assert any(re.fullmatch(r'\s+mapping\s+map, intake', line) for line in lines(run('help', 'commands')))
    assert lines(run('alias', 'both', 'map', 'memory', 'map')) == ['Success: both stands for map, memory']
    assert run('both').stdout == entered(run, 'map', 'memory')      # a module named twice counts once


@pytest.mark.req('CLI-039')
def test_an_alias_stands_for_two_or_more_real_modules_under_a_free_name(run):
    count = ['Error: alias needs a name and two or more modules.', 'Next: metaform help alias']
    naming = ['Error: An alias is named with a lowercase letter, then letters, digits, - or _.',
              'Next: metaform help alias']
    for args, err in ((('solo', 'map'), count), (('twice', 'map', 'map'), count), ((), count),
                      (('mapping', 'map', 'ghost'), ['Error: No module ghost.', 'Next: metaform list modules']),
                      (('list', 'map', 'memory'), ['Error: list is already a command.', 'Next: metaform help commands']),
                      (('map', 'map', 'memory'), ['Error: map is already a command.', 'Next: metaform help commands']),
                      (('chassis', 'map', 'memory'),
                       ['Error: chassis is already a command.', 'Next: metaform help commands']),
                      (('metaform', 'map', 'memory'),                 # the chassis's own tool over MCP, CLI-037
                       ['Error: metaform is already a command.', 'Next: metaform help commands']),
                      (('1234567', 'map', 'memory'), naming), (('Mapping', 'map', 'memory'), naming)):
        refused = run('alias', *args, ok=False)
        assert refused.returncode == 2 and refused.stderr.splitlines() == err, args
    assert run('mapping', ok=False).stderr.splitlines()[0] == 'Error: Unknown command: mapping.'
    assert run('solo', ok=False).returncode == 2
    assert 'Aliases' not in lines(run('help', 'commands'))           # nothing refused was stored


@pytest.mark.req('CLI-039')
def test_a_module_of_an_aliases_name_comes_before_the_alias(run, user_module):
    run('alias', 'mapping', 'map', 'memory')
    user_module('mapping', f'''
        from metaform.module import Module, Verb
        {OS}
        MODULE = Module(id='mapping', summary='Mapping.', purpose='Mapping. Details: metaform help mapping.',
                        verbs=(Verb('show', lambda ctx: 'shown', 'Show.'),))
    ''')
    assert run('mapping', 'show').stdout == 'shown'
    assert run('help', 'mapping').stdout.startswith('mapping: Mapping.')
    assert 'Aliases' not in lines(run('help', 'commands'))


@pytest.mark.req('CLI-039')
@pytest.mark.req('CLI-038')
def test_an_alias_is_defined_for_a_worker_folder_and_holds_below_it(run, tmp_path):
    worker, orchestrator = tmp_path / 'worker', tmp_path / 'orchestrator'
    (worker / 'deep').mkdir(parents=True)
    orchestrator.mkdir()
    out = lines(run('alias', 'mapping', 'map', 'memory', f'folder={worker}', cwd=orchestrator))
    assert out == [f'Success: in {worker.resolve()}, mapping stands for map, memory']
    assert run('mapping', cwd=orchestrator, ok=False).returncode == 2
    assert run('mapping', cwd=worker / 'deep').stdout == entered(run, 'map', 'memory')
    run('alias', 'mapping', 'map', 'intake', cwd=worker / 'deep')   # the nearest folder's definition wins
    assert run('mapping', cwd=worker / 'deep').stdout == entered(run, 'map', 'intake')
    assert run('mapping', cwd=worker).stdout == entered(run, 'map', 'memory')


@pytest.mark.req('CLI-039')
def test_an_alias_is_stored_with_its_folder_in_the_database_that_holds_the_folder(run, home, project):
    """Rich, 2026-10-03: stored per folder in the folder table."""
    folder = (project / 'src').resolve()
    run('alias', 'mapping', 'map', 'memory', cwd=folder)
    key = os.path.normcase(str(folder))
    with sqlite3.connect(own('proj') / 'project.sqlite3') as db:
        assert db.execute('SELECT path FROM folders WHERE path_key=?', (key,)).fetchone() == (str(folder),)
        assert db.execute('SELECT name, module FROM aliases WHERE path_key=? ORDER BY position',
                          (key,)).fetchall() == [('mapping', 'map'), ('mapping', 'memory')]
    with sqlite3.connect(home / 'metaform.sqlite3') as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert 'aliases' not in tables or not db.execute('SELECT 1 FROM aliases').fetchall()


@pytest.mark.req('CLI-039')
@pytest.mark.req('CLI-022')
def test_an_alias_shows_only_what_the_folders_command_surface_shows(run):
    run('alias', 'mapping', 'map', 'memory')
    run('set', '--modules', 'chassis,map')
    assert run('mapping').stdout == entered(run, 'map')
    run('set', '--modules', 'chassis,intake')
    refused = run('mapping', ok=False)
    assert refused.returncode == 2 and refused.stderr.splitlines()[-1] == 'Next: metaform unset --modules'
    assert not any('mapping' in line for line in lines(run('help', 'commands')))
    run('unset', '--modules')
    run('disable', 'memory')                                         # off is not loaded: only map is listed
    assert run('mapping').stdout == entered(run, 'map')


@pytest.mark.req('CLI-030')
def test_the_context_settings_accept_only_real_names(run, toggles):
    ids = sorted(line.split()[0] for line in lines(run('list', 'modules')))
    refused = run('set', '--modules', 'mapp', ok=False)
    assert refused.stderr.splitlines() == [f"Error: --modules has no group 'mapp'. Groups: {', '.join(['chassis', *ids])}.",
                                           'Next: metaform list modules']
    assert shown(run)['modules']['state'] == 'default'
    run('set', '--modules', 'chassis,toggles')
    refused = run('set', '--project', 'ghost', ok=False)
    assert refused.returncode == 2 and refused.stderr.splitlines()[-1] == 'Next: metaform list projects'


# Status, help and errors --------------------------------------------------------

@pytest.mark.req('CLI-005')
@pytest.mark.req('CLI-028')
def test_status_in_a_folder_with_no_project(run, home, tmp_path):
    out = lines(run(cwd=tmp_path))
    assert out == [f'Metaform {__version__}', f'Home: {home}', f'Folder: {tmp_path}', 'Project: none',
                   '  Register one: metaform add project <id> <path>']


@pytest.mark.req('CLI-028')
@pytest.mark.req('MAP-041')
def test_status_in_a_registered_project_has_the_fixed_lines(run, home, project):
    run('set', '--project', 'proj', cwd=project)
    out = lines(run(cwd=project / 'src'))
    assert out[:5] == [f'Metaform {__version__}', f'Home: {home}', f'Folder: {project / "src"}',
                       f'Project: proj ({project}), inherited from {project}', f'Target: path {project}']
    assert out[5].startswith('Metaform: ')
    assert out[6] == 'Projects: one registered'
    assert out[7].startswith('Modules: ') and out[-1] == 'Instructions: metaform help agents'
    assert f'Project: proj ({project}), selected here' in lines(run(cwd=project))


@pytest.mark.req('CLI-028')
@pytest.mark.req('BASE-035')
def test_a_modules_status_hook_lines_and_notice_are_printed(run, user_module, project):
    user_module('hooked', f'''
        from metaform.module import Module, Status
        {OS}
        def status(ctx):
            return Status(lines=('Hooked: ready',), notice='Do the next thing.')
        MODULE = Module(id='hooked', summary='x', purpose='Hooked. Details: metaform help hooked.', status=status)
    ''')
    out = lines(run(cwd=project))
    at = out.index('Hooked: ready')
    assert out[at + 1] == '  Do the next thing.' and out[-1] == 'Instructions: metaform help agents'


@pytest.mark.req('CLI-006')
def test_help_is_the_brief_overview_with_its_tips(run):
    assert run('help').stdout == (
        f'Metaform {__version__}: gives agents a project\'s purpose before they work on it.\n\n'
        'Common commands\n'
        '  metaform                          Show status: home, folder, project.\n'
        '  metaform add project <id> <path>  Register a project.\n'
        '  metaform config                   Open the settings screen.\n'
        '  metaform set --<setting> <value>  Save a setting.\n\n'
        'Tips:\n'
        '  - start here: metaform help intro\n'
        "  - run 'metaform help commands' for an index of all commands\n"
        "  - run 'metaform help switches' for all switches\n"
        "  - run 'metaform config --show' to inspect your saved defaults.\n")


@pytest.mark.req('CLI-006')
def test_help_intro_names_the_home(run, home):
    out = run('help', 'intro').stdout
    assert out.startswith('Metaform keeps a map of what each part of a project is for: which element receives\n')
    assert f'All data lives in the Metaform home, {home}. Nothing is written into your projects.' in out
    assert '  metaform install                   Set up your AI tools to use Metaform.' in out


@pytest.mark.req('CLI-007')
@pytest.mark.req('CLI-029')
@pytest.mark.parametrize('command', ['help', 'add', 'list', 'set', 'unset', 'config', 'enable', 'disable',
                                     'activate', 'export', 'import', 'query', 'alias'])
def test_every_chassis_command_has_a_page_and_a_separate_syntax(run, command):
    page = run('help', command).stdout
    syntax = run(command, '--help').stdout
    assert run(command, '-h').stdout == syntax
    assert page.startswith(f'{command}: ')
    assert syntax.startswith('Usage: ') and syntax.rstrip().splitlines()[-1].split() == ['-h,', '--help', 'Show', 'this', 'syntax.']
    assert page != syntax


@pytest.mark.req('CLI-029')
def test_a_verb_page_has_its_sections_in_order(run, user_module):
    user_module('paged', f'''
        from metaform.module import Module, Noun, Verb
        {OS}
        MODULE = Module(id='paged', summary='Paged.', purpose='Paged. Details: metaform help paged.',
                        verbs=(Verb('go', lambda ctx: None, 'Go somewhere.', nouns=(Noun('where', 'Where to go.'),),
                                    caution='This goes.', details='It goes far.',
                                    examples=(('metaform paged go home', 'Goes home.'),)),))
    ''')
    page = run('help', 'paged', 'go').stdout
    order = [page.index(heading) for heading in ('paged go: Go somewhere.', 'Usage', 'Switches', 'Caution',
                                                 'Details', 'Examples', 'See also:')]
    assert order == sorted(order)
    assert 'Examples' not in run('paged', 'go', '--help').stdout


@pytest.mark.req('CLI-008')
@pytest.mark.req('CLI-032')
@pytest.mark.req('BASE-029')
def test_the_indexes_group_commands_by_owner(run, toggles):
    out = run('help', 'commands').stdout
    assert out.startswith('Commands\n')
    assert 'toggles: Toggles.\n  toggles show' in out
    assert not any(line.startswith('show') for line in out.splitlines())
    switches = {line.split()[0] for line in lines(run('help', 'switches')) if line.startswith('  ')}
    assert {'--tmux', '--panes', '--project', '--modules', '--layers', '--glue', '--json'} <= switches
    assert all(row['owner'] for row in shown(run).values())
    assert shown(run)['tmux']['owner'] == 'toggles'


@pytest.mark.req('CLI-037')
def test_a_modules_command_is_never_written_with_a_colon(run, toggles):
    """Rich, 2026-10-01: `<server>:<prompt>` is how a person runs an MCP prompt in Claude Code, and only there. The
    command line reads `toggles:show` as no command of its own, the same as any unknown name."""
    assert run('toggles', 'show', '--tmux').stdout == 'tmux=True'
    for args in (('toggles:show', '--tmux'), ('help', 'toggles:show')):
        refused = run(*args, ok=False)
        assert refused.returncode != 0 and 'tmux=True' not in refused.stdout
        assert 'toggles:show' in refused.stderr
    assert run('help', 'toggles', 'show').stdout != run('help', 'toggles:show', ok=False).stdout


@pytest.mark.req('CLI-009')
def test_every_error_names_exactly_one_next_command(run):
    for args in (['frobnicate'], ['add'], ['list', 'things'], ['set', '--nope', 'x'], ['unset', 'banana'],
                 ['help', 'nothing'], ['enable', 'ghost'], ['activate', 'metaform', 'ghost'],
                 ['query', 'nothing'], ['export', 'ghost']):
        result = run(*args, ok=False)
        err = result.stderr.splitlines()
        assert result.returncode == 2, args
        assert len(err) == 2 and err[0].startswith('Error: ') and err[1].startswith('Next: '), (args, err)
    assert run('list', 'foo', ok=False).stderr.splitlines() == [
        'Error: list needs a noun: projects, modules, metaforms, reports, backups, origins or variants.',
        'Next: metaform list projects']


@pytest.mark.req('CLI-010')
def test_a_setting_declared_by_a_module_reaches_every_surface(run, toggles):
    row = shown(run)['panes']
    assert (row['default'], row['help'], row['kind'], row['switch']) == (4, 'How many panes.', 'int', '--panes')
    assert '--panes' in run('help', 'switches').stdout
    run('set', '--panes', '5')


@pytest.mark.req('CLI-025')
def test_json_goes_to_standard_output_alone(run, toggles, user_module):
    user_module('noisy', f'''
        import sys
        from metaform.module import Module, Verb
        {OS}
        def speak(ctx):
            ctx.say('A message for a person.')
            print('A stray warning.', file=sys.stderr)
            return {{'answer': 42}}
        MODULE = Module(id='noisy', summary='x', purpose='Noisy. Details: metaform help noisy.',
                        verbs=(Verb('speak', speak, 'Speak.'),))
    ''')
    result = run('noisy', 'speak', '--json')
    assert json.loads(result.stdout) == {'answer': 42}
    assert 'A message for a person.' in result.stderr
    json.loads(run('config', '--show', '--json').stdout)


@pytest.mark.req('CLI-031')
def test_config_show_prints_each_setting_with_its_state(run, toggles):
    run('set', '--panes', '5')
    run('set', '--tmux', '--glue')
    out = lines(run('config', '--show'))
    assert '  panes: 5  (set)' in out and '* tmux: true  (glued)' in out and '  modules: all' in out
    assert out[-2:] == ['', '* glued: kept by unset all until unglued.']


@pytest.mark.req('CLI-020')
def test_every_chassis_verb_runs_in_an_empty_home(run, tmp_path):
    folder = tmp_path / 'w'
    folder.mkdir()
    for args in ((), ('help',), ('help', 'intro'), ('help', 'commands'), ('help', 'switches'), ('help', 'agents'),
                 ('list', 'projects'), ('list', 'modules'), ('config', '--show'), ('query',),
                 ('add', 'project', 'w', str(folder)), ('list', 'metaforms', 'w'), ('export', 'w')):
        assert run(*args, cwd=folder).returncode == 0, args


# Chassis verbs ------------------------------------------------------------------

@pytest.mark.req('CLI-031')
@pytest.mark.req('STORE-031')
def test_add_and_list_projects(run, tmp_path):
    folder = tmp_path / 'pics'
    folder.mkdir()
    assert lines(run('add', 'project', 'photos', str(folder), 'artifact', 'kitchen_photos')) == \
        [f'Added project photos: {folder} (target artifact kitchen_photos)']
    assert lines(run('add', 'project', 'photos', str(folder), 'artifact', 'kitchen_photos')) == \
        ['Project photos is already registered.']
    assert lines(run('list', 'projects')) == [f'photos  {folder}  artifact kitchen_photos']
    refused = run('add', 'project', 'Photos', str(folder), ok=False)
    assert refused.returncode == 2


@pytest.mark.req('CLI-031')
@pytest.mark.req('STORE-041')
@pytest.mark.req('MAP-045')
def test_metaforms_are_added_listed_and_activated(run, project):
    assert lines(run('add', 'metaform', 'fresh', cwd=project)) == [
        ('Added metaform fresh to proj; it is now active. The previous metaform main is kept. To switch back: '
        'metaform activate metaform main')]
    listed = lines(run('list', 'metaforms', cwd=project))
    assert [line.split()[0] for line in listed] == ['main', 'fresh'] and listed[1].endswith('(active)')
    assert lines(run('activate', 'metaform', 'main', cwd=project)) == ['Active metaform for proj: main']
    assert run(cwd=project).stdout.count('Metaform: main, two in project') == 1


@pytest.mark.req('PROJ-025')
@pytest.mark.req('CLI-018')
def test_clear_project_removes_the_metaforms_and_reports_and_keeps_registration_settings_and_history(
        run, project, home, tmp_path):
    (project / 'notes.txt').write_text('first\n', encoding='utf-8')
    noted(run, project, 'Counts down.')
    run('add', 'metaform', 'fresh', cwd=project)
    run('feedback', 'The subtype fields did not match.', cwd=project)
    run('add', 'origin', cwd=project)
    work = tmp_path / 'work'
    work.mkdir()
    (work / 'notes.txt').write_text('second\n', encoding='utf-8')
    run('add', 'variant', str(work), cwd=project)
    elsewhere = tmp_path / 'elsewhere'
    run('set', '--project', 'proj', cwd=elsewhere)
    before = {'metaforms': sorted(path.name for path in own('proj').glob('*.metaform.sqlite3')),
              'reports': sorted(path.name for path in (own('proj') / 'reports').iterdir()),
              'origins': run('list', 'origins', cwd=project).stdout,
              'variants': run('list', 'variants', cwd=project).stdout,
              'files': sorted(path.name for path in project.iterdir())}
    assert len(before['metaforms']) == 2 and len(before['reports']) == 1

    refused = run('clear', 'project', cwd=elsewhere, ok=False)
    assert refused.returncode == 2
    assert refused.stderr.splitlines() == [
        ('Error: Clearing proj removes two metaforms, main and fresh, with their stores, and one report file. '
         'Its registration, folder, settings, origins and variants stay.'),
        'Next: If you are sure: metaform clear project proj --confirm']
    assert [line.split()[0] for line in lines(run('list', 'metaforms', cwd=project))] == ['main', 'fresh']
    assert sorted(path.name for path in (own('proj') / 'reports').iterdir()) == before['reports']

    said = lines(run('clear', 'project', 'proj', '--confirm', cwd=elsewhere))
    assert said[0] == ('Cleared proj: two metaforms, main and fresh, and one report file. Its registration, folder, '
                       'settings, origins and variants stay.')
    assert len(said) == 3 and said[1].startswith('Backed up as ') and said[2] == \
        'To bring it back: metaform restore project proj'  # PROJ-030
    assert run('list', 'metaforms', cwd=project).stdout == ''
    assert not list(own('proj').glob('*.metaform.sqlite3'))
    assert not (own('proj') / 'reports').exists()
    assert run(cwd=project).stdout.count('Metaform: none yet') == 1
    assert run('list', 'origins', cwd=project).stdout == before['origins']
    assert run('list', 'variants', cwd=project).stdout == before['variants']
    assert [line.split()[0] for line in lines(run('list', 'projects'))] == ['proj']
    assert shown(run, cwd=elsewhere)['project']['value'] == 'proj'
    assert sorted(path.name for path in project.iterdir()) == before['files']
    assert (project / 'notes.txt').read_text(encoding='utf-8') == 'first\n'

    noted(run, project, 'Counts down again.')
    listed = lines(run('list', 'metaforms', cwd=project))
    assert [line.split()[0] for line in listed] == ['main'] and listed[0].endswith('(active)')
    assert 'clear' in {line.split()[0] for line in lines(run('help', 'commands')) if line.startswith('  ')}


@pytest.mark.req('PROJ-031')
def test_remove_project_takes_an_empty_project_off_the_list_and_deletes_nothing(run, project, home, tmp_path):
    (project / 'notes.txt').write_text('first\n', encoding='utf-8')
    noted(run, project, 'Counts down.')
    run('feedback', 'The subtype fields did not match.', cwd=project)
    elsewhere = tmp_path / 'elsewhere'
    run('set', '--project', 'proj', cwd=elsewhere)
    files = sorted(path.name for path in project.rglob('*'))

    held = run('remove', 'project', 'proj', '--confirm', cwd=elsewhere, ok=False)
    assert held.returncode == 2 and held.stderr.splitlines() == [
        ('Error: proj holds one metaform, main, and one report file. Only an empty project is removed; clearing it '
         'backs it up first.'),
        'Next: metaform clear project proj --confirm']
    assert [line.split()[0] for line in lines(run('list', 'projects'))] == ['proj']
    assert [line.split()[0] for line in lines(run('list', 'metaforms', cwd=project))] == ['main']

    run('clear', 'project', 'proj', '--confirm', cwd=elsewhere)
    backups = run('list', 'backups', 'proj').stdout
    refused = run('remove', 'project', 'proj', cwd=elsewhere, ok=False)
    assert refused.returncode == 2 and refused.stderr.splitlines() == [
        ('Error: Removing proj takes it off the list of projects and forgets the folder settings that select it. Its '
         "folder, history and backups stay in the home, and its source's folder and files are not touched."),
        'Next: If you are sure: metaform remove project proj --confirm']
    assert [line.split()[0] for line in lines(run('list', 'projects'))] == ['proj']

    assert lines(run('remove', 'project', 'proj', '--confirm', cwd=elsewhere)) == [
        'Removed proj. Its folder and files were not touched.']
    assert 'proj' not in [line.split()[0] for line in lines(run('list', 'projects'))]
    from metaform import home as metaform_home
    assert any((home / 'projects').glob(metaform_home.folder_name(project) + '-*'))  # its folder stays, PROJ-026
    assert (home / 'backups' / 'clear' / 'proj').is_dir()
    assert sorted(path.name for path in project.rglob('*')) == files
    assert 'Project: none' in run(cwd=elsewhere).stdout
    run('add', 'project', 'proj', str(project))
    assert run('list', 'backups', 'proj').stdout == backups
    run('restore', 'project', 'proj', cwd=project)
    assert [line.split()[0] for line in lines(run('list', 'metaforms', cwd=project))] == ['main']


@pytest.mark.req('PROJ-031')
def test_remove_project_of_an_unregistered_id_changes_nothing(run, project):
    stopped = run('remove', 'project', 'ghost', ok=False)
    assert stopped.returncode == 2 and stopped.stderr.splitlines()[-1] == 'Next: metaform list projects'
    assert [line.split()[0] for line in lines(run('list', 'projects'))] == ['proj']


@pytest.mark.req('PROJ-025')
def test_clear_project_names_a_file_it_could_not_remove_with_the_reason_and_what_to_do(run, project, home,
                                                                                       unremovable):
    noted(run, project, 'Counts down.')
    run('feedback', 'The subtype fields did not match.', cwd=project)
    reports = own('proj') / 'reports'
    (stuck,) = reports.iterdir()
    with unremovable(stuck):
        cleared = run('clear', 'project', '--confirm', cwd=project)
        assert stuck.is_file()
    said = lines(cleared)
    assert said[0] == ('Cleared proj: one metaform, main, and one report file. Its registration, folder, settings, '
                       'origins and variants stay.')
    assert said[1].startswith('Backed up as ') and said[2] == 'To bring it back: metaform restore project proj'
    assert said[3] == 'Not removed, still on disk:'
    assert said[4].startswith(f'  {stuck}: ') and len(said[4]) > len(f'  {stuck}: ')
    assert said[5:] == [('Next: Close any program that has it open, such as a running web GUI, or fix its '
                         'permissions, then run metaform clear project proj --confirm again.')]
    assert run('list', 'metaforms', cwd=project).stdout == ''
    assert not list(own('proj').glob('*.metaform.sqlite3'))

    again = lines(run('clear', 'project', '--confirm', cwd=project))
    assert again[0] == ('Cleared proj: no metaforms and one report file. Its registration, folder, settings, origins '
                        'and variants stay.') and again[1].startswith('Backed up as ') and len(again) == 3
    assert not reports.exists()
    assert run('clear', 'project', cwd=project, ok=False).stderr.splitlines()[0] == (
        'Error: Clearing proj removes no metaforms and no report files. Its registration, folder, settings, origins '
        'and variants stay.')


@pytest.mark.req('STORE-027')
@pytest.mark.req('BASE-002')
def test_export_then_import_into_an_empty_home_reproduces_the_project(run, project, tmp_path, home):
    run('enable', 'hello')
    run('hello', 'greet', 'ada', cwd=project)
    document = tmp_path / 'backup.json'
    run('export', 'proj', f'file={document}', cwd=project)
    first = json.loads(document.read_text())
    other = tmp_path / 'other-home'
    env = {'METAFORM_HOME': str(other)}
    report = run('import', str(document), cwd=tmp_path, env=env).stdout
    assert 'layers added: one' in report
    again = run('export', 'proj', cwd=tmp_path, env=env).stdout
    assert json.loads(again) == first
    skipped = run('import', str(document), cwd=tmp_path, env=env).stdout
    assert 'layers skipped: one' in skipped


@pytest.mark.req('STORE-028')
def test_query_answers_through_the_reads_and_lists_them(run, project):
    listed = run('query').stdout
    assert 'element' in listed and 'layer-items' in listed and 'search' in listed
    run('enable', 'hello')
    run('hello', 'greet', 'ada', cwd=project)
    layers = json.loads(run('query', 'layers', '--json', cwd=project).stdout)
    assert [layer['name'] for layer in layers['results']] == ['hello.greetings']
    items = json.loads(run('query', 'layer-items', 'hello.greetings', '--json', cwd=project).stdout)
    assert [item['value'] for item in items['results']] == ['ada']
    node = json.loads(run('query', 'node', 'element:code.module.hello', 'raw=true', '--json', cwd=project).stdout)
    assert node['layers'][0]['layer'] == 'hello.greetings'
    run('map', 'knowledge', 'op=finish', 'layer=hello.greetings', cwd=project)

    def layers_at(*command):
        result = run(*command, 'element:code.module.hello', '--json', cwd=project, ok=False)
        view = json.loads(result.stdout) if result.returncode == 0 and result.stdout.strip() else None
        return {group['layer'] for group in view['layers']} if view else set()
    assert 'hello.greetings' in layers_at('query', 'node') & layers_at('map', 'node')
    run('map', 'mask', 'code.module', 'hello.greetings', cwd=project)
    assert 'hello.greetings' not in layers_at('query', 'node') | layers_at('map', 'node')


@pytest.mark.req('CLI-033')
@pytest.mark.req('LAYER-019')
def test_the_layers_setting_is_the_starting_selection(run, project):
    from metaform.data import Node, Store
    store = Store('proj')
    with store.atomic():
        base = store.layer('intake-1', 'intake', 'The map.', kind='intake', mutable=False, hideable=False,
                           provenance={'module': 'intake'}, ready=True)
        store.add_element(base.name, 'code.timer', role='DE')
    for name, tag in (('a', 'practices'), ('b', None)):
        store.layer(name, 'test', f'{name} notes.', mutable=True, hideable=True, provenance={'module': 'test'},
                    tags=(tag,) if tag else ())
        store.add_item(name, Node('element', 'code.timer'), f'from {name}')
        store.finish(name)

    def read(*extra, cwd=project):
        view = json.loads(run('query', 'node', 'element:code.timer', '--json', *extra, cwd=cwd).stdout)
        return {group['layer'] for group in view['layers'] if group['items']} & {'a', 'b'}
    assert read() == {'a', 'b'}
    run('set', '--layers', 'practices', cwd=project)
    assert read(cwd=project / 'src') == {'a'}
    run('unset', '--layers', cwd=project)
    assert read() == {'a', 'b'}
    run('set', '--layers', 'practices', '--glue', cwd=project)
    run('unset', 'all', cwd=project)
    assert shown(run, cwd=project)['layers']['value'] == ['practices']
    run('unset', 'all', '--unglue', cwd=project)
    assert shown(run, cwd=project)['layers']['value'] == []
    kept = run('set', '--layers', 'nothing-here', cwd=project)
    assert re.search(r'^Notice: layers: .*nothing-here.*metaform map layers', kept.stdout, re.MULTILINE)
    assert shown(run, cwd=project)['layers']['value'] == ['nothing-here']
    assert read() == set()


@pytest.mark.req('CLI-033')
@pytest.mark.req('CLI-011')
@pytest.mark.req('CLI-021')
@pytest.mark.req('BASE-028')
def test_project_and_layers_pass_on_one_call_to_any_module_verb(run, project, tmp_path):
    from metaform.data import Node, Store
    other = tmp_path / 'other'
    other.mkdir()
    run('add', 'project', 'other', str(other))
    for project_id in ('proj', 'other'):
        store = Store(project_id)
        with store.atomic():
            base = store.layer('intake-1', 'intake', 'The map.', kind='intake', mutable=False, hideable=False,
                               provenance={'module': 'intake'}, ready=True)
            store.add_element(base.name, f'code.{project_id}', role='DE')
    store = Store('proj')
    for name in ('a', 'b'):
        store.layer(name, 'test', f'{name} notes.', mutable=True, hideable=True, provenance={'module': 'test'})
        store.add_item(name, Node('element', 'code.proj'), f'from {name}')
        store.finish(name)

    def read(*extra):
        view = json.loads(run('map', 'node', 'element:code.proj', '--json', *extra, cwd=project).stdout)
        return {group['layer'] for group in view['layers'] if group['items']} & {'a', 'b'}
    assert read() == {'a', 'b'}
    assert read('--layers', 'a') == {'a'}
    assert read() == {'a', 'b'} and shown(run, cwd=project)['layers']['value'] == []
    there = json.loads(run('map', 'where', 'code.other', '--project', 'other', '--json', cwd=project).stdout)
    assert there['element']['address'] == 'code.other'
    assert shown(run, cwd=project)['project']['value'] == 'proj'


@pytest.mark.req('CLI-029')
def test_a_module_page_leaves_out_an_empty_section_and_keeps_its_rows_narrow(run, user_module):
    user_module('quiet', f'''
        from metaform.module import Module
        {OS}
        MODULE = Module(id='quiet', summary='Declares nothing.', purpose='Declares nothing. Details: metaform help quiet.')
    ''')
    page = run('help', 'quiet').stdout.splitlines()
    assert page[0] == 'quiet: Declares nothing.' and 'Verbs' not in page
    rows = run('help', 'map').stdout.splitlines()
    roots = next(line for line in rows if line.strip().startswith('roots'))
    assert roots.index("The map's entry") <= 2 + 40 + 2
    knowledge = next(index for index, line in enumerate(rows) if line.strip().startswith('knowledge '))
    assert len(rows[knowledge].strip()) > 40 and rows[knowledge + 1].strip().startswith('Create, build')
    assert rows[knowledge + 1].index('Create, build') == roots.index("The map's entry")


@pytest.mark.req('CLI-029')
def test_a_row_of_up_to_40_characters_stays_on_its_line_and_a_longer_one_wraps(run, user_module):
    user_module('rows', f'''
        from metaform.module import Module, Noun, Verb
        {OS}
        MODULE = Module(id='rows', summary='Rows.', purpose='Rows. Details: metaform help rows.', verbs=(
            Verb('fit', lambda ctx: None, 'Forty wide.', nouns=(Noun('{'a' * 34}', 'A noun.'),)),
            Verb('far', lambda ctx: None, 'Forty-one wide.', nouns=(Noun('{'b' * 35}', 'A noun.'),)),
            Verb('few', lambda ctx: None, 'Short.')))
    ''')
    rows = run('help', 'rows').stdout.splitlines()
    fit = next(line for line in rows if line.strip().startswith('fit '))
    far = next(index for index, line in enumerate(rows) if line.strip().startswith('far '))
    assert len(fit.strip().split('  ')[0]) == 40 and fit.index('Forty wide.') == 2 + 40 + 2
    assert len(rows[far].strip()) == 41 and 'Forty-one' not in rows[far]
    assert rows[far + 1].index('Forty-one wide.') == 2 + 40 + 2


@pytest.mark.req('BASE-037')
def test_an_off_module_lists_with_the_summary_it_shows_when_on(run):
    def text(module_id):
        line = next(line for line in lines(run('list', 'modules')) if line.split()[0] == module_id)
        parts = line.split(None, 3)
        return parts[3] if len(parts) == 4 else ''
    off = text('hello')
    run('enable', 'hello')
    assert off and off == text('hello')


@pytest.mark.req('CLI-015')
@pytest.mark.req('CLI-017')
def test_set_and_unset_report_what_is_stored_whatever_the_value(run, toggles):
    assert lines(run('set', '--no-tmux'))[0] == 'Success: updated one key'
    assert shown(run)['tmux']['state'] == 'set'
    assert lines(run('unset', 'all'))[0] == 'Reset one setting: tmux'
    assert shown(run)['tmux']['state'] == 'default'
    run('set', '--no-tmux', '--glue')
    unglued = lines(run('unset', '--tmux', '--unglue'))
    assert 'Reset one setting: tmux' in unglued and 'Unglued: tmux' in unglued


@pytest.mark.req('QUAL-002')
@pytest.mark.req('CLI-022')
def test_output_is_utf8_whatever_the_encoding_the_system_gives_a_pipe(run, toggles):
    # A pipe on Windows defaults to cp1252, which has no arrow; PYTHONIOENCODING gives any system the same pipe.
    result = run('set', '--tmux', env={'PYTHONIOENCODING': 'cp1252'})
    assert '  tmux: false → true' in result.stdout.splitlines()


@pytest.mark.req('CLI-022')
@pytest.mark.req('CLI-027')
def test_set_with_one_value_that_does_not_fit_stores_none_of_them(run, toggles):
    refused = run('set', '--tmux', '--panes', '99', ok=False)
    assert refused.returncode == 2 and 'panes' in refused.stderr
    assert shown(run)['tmux']['state'] == 'default'


@pytest.mark.req('CLI-022')
@pytest.mark.req('PROJ-007')
def test_set_for_another_folder_names_that_folder(run, tmp_path):
    job = tmp_path / 'job1'
    job.mkdir()
    assert lines(run('set', '--modules', 'chassis', f'folder={job}'))[0] == f'Success: updated one key for {job}'


@pytest.mark.req('BASE-031')
@pytest.mark.skipif(os.name == 'nt', reason='SIGINT is delivered differently on Windows')
def test_interrupting_an_async_verb_reports_cancelled_then_interrupted(home, user_module, tmp_path):
    user_module('sleeper', f'''
        import asyncio
        from metaform.module import Module, Verb
        {OS}
        async def sleep(ctx):
            print('started', flush=True)
            await asyncio.sleep(60)
            return 'woke'
        MODULE = Module(id='sleeper', summary='x', purpose='Sleeps. Details: metaform help sleeper.',
                        verbs=(Verb('sleep', sleep, 'Sleep.'),))
    ''')
    process = subprocess.Popen([sys.executable, '-m', 'metaform', 'sleeper', 'sleep'], cwd=tmp_path,
                               env={**os.environ, 'METAFORM_HOME': str(home)}, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, encoding='utf-8')
    try:
        assert process.stdout.readline().strip() == 'started'
        time.sleep(0.2)
        process.send_signal(signal.SIGINT)
        out, err = process.communicate(timeout=30)
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)
    assert process.returncode == 3
    assert 'Cancelling sleeper sleep...' in err and 'woke' not in out
    assert err.splitlines()[-1] == 'Cancelled.'


@pytest.mark.req('BASE-035')
def test_a_module_named_alone_runs_its_default_verb_and_help_still_shows_its_syntax(run, user_module):
    user_module('dflt', f'''
        from metaform.module import Module, Verb
        {OS}
        MODULE = Module(id='dflt', summary='Default.', purpose='Default. Details: metaform help dflt.', default='go',
                        verbs=(Verb('go', lambda ctx: 'went', 'Go.'), Verb('stop', lambda ctx: 'stopped', 'Stop.')))
    ''')
    user_module('plain', f'''
        from metaform.module import Module, Verb
        {OS}
        MODULE = Module(id='plain', summary='Plain.', purpose='Plain. Details: metaform help plain.',
                        verbs=(Verb('go', lambda ctx: 'went', 'Go.'),))
    ''')
    assert run('dflt').stdout == 'went' and run('dflt', '--json').stdout == 'went'
    assert run('dflt', 'go').stdout == 'went' and run('dflt', 'stop').stdout == 'stopped'
    assert run('dflt', '--help').stdout.startswith('Usage: metaform dflt')
    assert run('plain').stdout.startswith('Usage: metaform plain')
    user_module('wrong', f'''
        from metaform.module import Module, Verb
        {OS}
        MODULE = Module(id='wrong', summary='Wrong.', purpose='Wrong. Details: metaform help wrong.', default='nope',
                        verbs=(Verb('go', lambda ctx: 'went', 'Go.'),))
    ''')
    row = next(line for line in lines(run('list', 'modules')) if line.split()[0] == 'wrong')
    assert row.split()[1] == 'error' and 'nope' in row


@pytest.mark.req('BASE-029')
def test_chassis_settings_stay_the_chassiss_when_a_module_is_what_first_imports_them(home):
    probe = ('import metaform.modules.web\n'
             'from metaform import settings\n'
             "print(settings.SCHEMA['layers'].owner, settings.SCHEMA['web_port'].owner)\n")
    result = subprocess.run([sys.executable, '-c', probe], capture_output=True, text=True, encoding='utf-8',
                            env={**os.environ, 'METAFORM_HOME': str(home)}, check=False)
    assert result.stdout.split() == ['chassis', 'web'], result.stderr


@pytest.mark.req('CLI-031')
@pytest.mark.req('CLI-022')
def test_all_is_what_an_empty_list_setting_is_shown_as_and_setting_it_clears_the_setting(run, toggles):
    """An unset `modules` or `layers` is shown as all. Set to the word all, it is the same: every module, every
    finished layer. Stored as the word, it named nothing and turned everything off."""
    run('set', '--modules', 'toggles')
    out = lines(run('set', '--modules', 'all'))
    assert out[:2] == ['Success: updated one key', '  modules: toggles → all']
    run('list', 'projects')                                           # nothing is narrowed
    shown = lines(run('config', '--show'))
    assert '  modules: all' in shown and not any('modules: all  (set)' in line for line in shown)



@pytest.mark.req('PROJ-030')
def test_a_clear_backs_the_project_up_first_and_restore_brings_it_back_as_it_was(run, project, home, tmp_path):
    """Rich, 2026-09-29: the clear backs it up and allows restoration easily, telling the user. What a clear removes
    cannot be made again by an intake: answers, tasks and knowledge are added to a map by hand."""
    import re
    noted(run, project, 'Counts down.')
    run('add', 'metaform', 'fresh', cwd=project)
    run('map', 'activate', 'main', cwd=project)
    run('feedback', 'The subtype fields did not match.', cwd=project)
    before = {'metaforms': lines(run('list', 'metaforms', cwd=project)),
              'memory': run('map', 'layer', 'notes', '--json', cwd=project).stdout,
              'reports': sorted(path.name for path in (own('proj') / 'reports').iterdir()),
              'stores': sorted(path.name for path in own('proj').glob('*.metaform.sqlite3'))}
    assert before['stores'] and lines(run('list', 'backups', cwd=project)) == []
    said = lines(run('clear', 'project', '--confirm', cwd=project))
    name = re.fullmatch(r'Backed up as (\d{8}T\d{6}Z(?:-\d+)?)\.', said[1]).group(1)
    kept = home / 'backups' / 'clear' / 'proj' / name
    assert sorted(path.name for path in kept.iterdir()) == ['reports', 'rows.json', 'stores']
    assert sorted(path.name for path in (kept / 'reports').iterdir()) == before['reports']
    assert sorted(path.name for path in (kept / 'stores').glob('*.metaform.sqlite3')) == before['stores']
    listed = lines(run('list', 'backups', cwd=project))
    assert len(listed) == 1 and listed[0].split()[0] == name and 'two metaforms' in listed[0]
    assert run('list', 'metaforms', cwd=project).stdout == ''

    assert lines(run('restore', 'project', cwd=project)) == [
        f'Restored proj from {name}: two metaforms, main and fresh, and one report file.']
    assert lines(run('list', 'metaforms', cwd=project)) == before['metaforms']
    assert run('map', 'layer', 'notes', '--json', cwd=project).stdout == before['memory']
    assert sorted(path.name for path in (own('proj') / 'reports').iterdir()) == before['reports']

    # restoring over a project that holds data backs that up first, so a restore loses nothing either
    noted(run, project, 'Added after the restore.')
    later = run('map', 'layer', 'notes', '--json', cwd=project).stdout
    assert later != before['memory']
    again = lines(run('restore', 'project', 'proj', name, cwd=project))
    assert again[0] == f'Restored proj from {name}: two metaforms, main and fresh, and one report file.'
    assert again[1].startswith('What it held was backed up as ') and run('map', 'layer', 'notes', '--json',
                                                                          cwd=project).stdout == before['memory']
    names = [line.split()[0] for line in lines(run('list', 'backups', cwd=project))]
    assert len(names) == 2 and names[1] == name and names == sorted(names, reverse=True)
    run('restore', 'project', 'proj', names[0], cwd=project)
    assert run('map', 'layer', 'notes', '--json', cwd=project).stdout == later

    missing = run('restore', 'project', 'proj', 'nothing', cwd=project, ok=False)
    assert missing.returncode == 2 and missing.stderr.splitlines() == [
        'Error: No backup nothing of proj.', 'Next: metaform list backups proj']


@pytest.mark.req('PROJ-030')
def test_a_clear_stops_when_the_backup_cannot_be_made_and_a_project_with_nothing_makes_none(run, project, home):
    noted(run, project, 'Counts down.')
    (home / 'backups').mkdir(exist_ok=True)
    (home / 'backups' / 'clear').write_text('in the way\n', encoding='utf-8')  # a file where the folder would be
    refused = run('clear', 'project', '--confirm', cwd=project, ok=False)
    assert refused.returncode == 2 and refused.stderr.startswith('Error: proj was not cleared, since it could not be '
                                                                  'backed up first: ')
    assert [line.split()[0] for line in lines(run('list', 'metaforms', cwd=project))] == ['main']
    (home / 'backups' / 'clear').unlink()
    assert len(lines(run('clear', 'project', '--confirm', cwd=project))) == 3
    assert lines(run('clear', 'project', '--confirm', cwd=project)) == [  # nothing to remove: no backup is made
        'Cleared proj: no metaforms and no report files. Its registration, folder, settings, origins and variants stay.']
    assert len(lines(run('list', 'backups', cwd=project))) == 1
