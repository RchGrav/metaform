"""Stage 1, step 2: modules, proven through the template module."""
import json
import textwrap


def module_row(run, identifier):
    for line in run('list', 'modules').stdout.splitlines():
        parts = line.split(None, 3)
        if parts and parts[0] == identifier:
            return parts
    return None


def user_module(home, name, body):
    folder = home / 'modules' / name
    folder.mkdir(parents=True)
    (folder / '__init__.py').write_text(textwrap.dedent(body))
    return folder


def test_template_module_is_listed_and_enabled_out_of_the_box(run):
    assert module_row(run, 'template')[:3] == ['template', 'on', 'system']


def test_sync_verb_with_noun_and_adverb(run):
    assert run('template', 'greet', 'world').stdout.strip() == 'hello, world'
    assert run('template', 'greet', 'world', '--loud').stdout.strip() == 'HELLO, WORLD!'


def test_async_verb_runs(run):
    assert 'waited 0 s' in run('template', 'wait', '0').stdout


def test_module_setting_declared_in_code_drives_set_and_behavior(run):
    run('set', '--greeting', 'hi')
    assert run('template', 'greet', 'you').stdout.strip() == 'hi, you'
    assert '--greeting' in run('help', 'switches').stdout
    run('unset', '--greeting')
    assert run('template', 'greet', 'you').stdout.strip() == 'hello, you'


def test_event_reaches_every_subscriber_and_one_failure_does_not_stop_the_rest(run, home):
    user_module(home, 'broken_listener', '''
        from metaform.module import Module, Subscription
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        def fail(payload, ctx):
            raise RuntimeError('listener failed')
        MODULE = Module(id='broken_listener', purpose='Fails.', summary='Fails.',
                        subscriptions=(Subscription('template.greeted', fail),))
    ''')
    user_module(home, 'listener', '''
        import json
        from metaform.module import Module, Subscription, Verb
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        def heard(payload, ctx):
            path = ctx.data / 'heard.json'
            got = json.loads(path.read_text()) if path.exists() else []
            path.write_text(json.dumps(got + [payload]))
        def show(ctx):
            path = ctx.data / 'heard.json'
            ctx.say(path.read_text() if path.exists() else '[]')
        MODULE = Module(id='listener', purpose='Listens.', summary='Listens.',
                        verbs=(Verb('show', show, 'Show what it heard.'),),
                        subscriptions=(Subscription('template.greeted', heard),))
    ''')
    run('template', 'greet', 'ada')
    run('template', 'greet', 'bob')
    assert json.loads(run('listener', 'show').stdout) == [{'name': 'ada'}, {'name': 'bob'}]
    assert run('template', 'history').stdout.split() == ['ada', 'bob']


def test_data_driven_select_setting(run):
    result = run('set', '--favorite', 'zed', ok=False)
    assert result.returncode != 0 and 'none yet' in result.stderr
    run('template', 'greet', 'zed')
    rejected = run('set', '--favorite', 'amy', ok=False)
    assert rejected.returncode == 2 and 'Choices: zed.' in rejected.stderr
    run('set', '--favorite', 'zed')
    assert '  favorite: zed  (set)' in run('config', '--show').stdout.splitlines()


def test_module_help_two_forms(run):
    page = run('help', 'template').stdout
    syntax = run('template', '--help').stdout
    assert page != syntax
    assert 'greet' in page and 'Details' in page
    assert 'Usage' in syntax and 'Details' not in syntax
    verb_page = run('help', 'template', 'greet').stdout
    verb_syntax = run('template', 'greet', '--help').stdout
    assert '--loud' in verb_page and '--loud' in verb_syntax and verb_page != verb_syntax


def test_command_index_includes_module_verbs(run):
    rows = [line.split()[:2] for line in run('help', 'commands').stdout.splitlines() if line.startswith('  ')]
    assert ['template', 'greet'] in rows and ['template', 'wait'] in rows


def test_module_and_verb_syntax_with_short_flag(run):
    assert run('template', '-h').stdout == run('template', '--help').stdout
    assert run('template', 'greet', '-h').stdout == run('template', 'greet', '--help').stdout
    assert run('template', 'greet', '-h').stdout.startswith('Usage: metaform template greet <name> [--loud]')


def test_disable_keeps_settings_and_enable_restores_the_module(run):
    run('set', '--greeting', 'hey')
    run('disable', 'module', 'template')
    assert module_row(run, 'template')[1] == 'off'
    result = run('template', 'greet', 'x', ok=False)
    assert result.stderr.splitlines() == ['Error: Module template is off.', 'Next: metaform enable module template']
    assert 'template' not in run('help', 'commands').stdout
    run('enable', 'module', 'template')
    assert run('template', 'greet', 'x').stdout.strip() == 'hey, x'


def test_user_place_module_loads(run, home):
    folder = home / 'modules' / 'hello'
    folder.mkdir(parents=True)
    (folder / '__init__.py').write_text(textwrap.dedent('''
        from metaform.module import Module, Verb

        SUPPORTED_OS = ('linux', 'macos', 'windows')

        def ping(ctx):
            ctx.say('pong')

        MODULE = Module(id='hello', purpose='Says pong.', summary='Answer ping.',
                        verbs=(Verb('ping', ping, 'Answer with pong.'),))
    '''))
    assert run('hello', 'ping').stdout.strip() == 'pong'
    assert module_row(run, 'hello')[:3] == ['hello', 'on', 'user']


def test_module_without_supported_os_is_refused_with_reason(run, home):
    folder = home / 'modules' / 'bad'
    folder.mkdir(parents=True)
    (folder / '__init__.py').write_text('raise SystemExit("must not run")\n')
    row = module_row(run, 'bad')
    assert row[1] == 'error' and 'SUPPORTED_OS is required' in row[3]


def test_module_for_another_os_is_refused_with_its_reason(run, home):
    user_module(home, 'elsewhere', '''
        SUPPORTED_OS = ('plan9',)
        raise SystemExit('must not run')
    ''')
    row = module_row(run, 'elsewhere')
    assert row[1] == 'error' and 'plan9' in row[3]


def test_duplicate_id_and_reserved_name_are_refused(run, home):
    user_module(home, 'template', '''
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        raise SystemExit('must not run')
    ''')
    user_module(home, 'list', '''
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        raise SystemExit('must not run')
    ''')
    rows = [line for line in run('list', 'modules').stdout.splitlines()]
    assert any(line.startswith('template') and 'Another module already has the id' in line for line in rows)
    assert any(line.startswith('list') and 'belongs to a chassis command' in line for line in rows)
    assert run('template', 'greet', 'x').stdout.strip() == 'hello, x'


def test_commands_setting_narrows_the_surface_and_names_the_way_back(run):
    out = run('set', '--commands', 'template').stdout.splitlines()
    assert out[-3:] == ['Commands shown here: template.',
                        'All other commands and help, including yours, are now hidden and will not run.',
                        'To restore them: metaform unset --commands']
    assert run('template', 'greet', 'x').stdout.strip() == 'hello, x'
    refused = run('list', 'projects', ok=False)
    assert refused.stderr.splitlines()[-1] == 'Next: metaform unset --commands'
    rows = {line.split()[0] for line in run('help', 'commands').stdout.splitlines() if line.startswith('  ')}
    assert 'list' not in rows and 'add' not in rows and {'help', 'set', 'unset', 'config'} <= rows
    run('config', '--show')
    run('unset', '--commands')
    run('list', 'projects')


def test_commands_setting_can_hide_a_module(run):
    run('set', '--commands', 'chassis')
    refused = run('template', 'greet', 'x', ok=False)
    assert refused.stderr.splitlines()[-1] == 'Next: metaform unset --commands'


def _package(site, name, body):
    pkg = site / name
    pkg.mkdir(parents=True)
    (pkg / '__init__.py').write_text(textwrap.dedent(body))
    info = site / f'{name}-1.0.dist-info'
    info.mkdir()
    (info / 'METADATA').write_text(f'Metadata-Version: 2.1\nName: {name}\nVersion: 1.0\n')
    (info / 'entry_points.txt').write_text(f'[metaform.modules]\n{name} = {name}\n')


def test_installed_package_module_loads_through_its_entry_point(home, tmp_path):
    import os, subprocess, sys
    site = tmp_path / 'site'
    _package(site, 'shelf', '''
        from metaform.module import Module, Verb
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        def count(ctx):
            ctx.say('3 books')
        MODULE = Module(id='shelf', purpose='Counts books.', summary='Count books.',
                        verbs=(Verb('count', count, 'Count the books.'),))
    ''')
    env = {**os.environ, 'METAFORM_HOME': str(home), 'PYTHONPATH': str(site)}
    run = lambda *a: subprocess.run([sys.executable, '-m', 'metaform', *a], env=env, cwd=tmp_path,
                                    capture_output=True, text=True)
    assert run('shelf', 'count').stdout.strip() == '3 books'
    row = next(line.split(None, 3) for line in run('list', 'modules').stdout.splitlines() if line.startswith('shelf'))
    assert row[:3] == ['shelf', 'on', 'entry']


def test_module_setting_that_clashes_is_refused_and_reported(run, home):
    folder = home / 'modules' / 'clash'
    folder.mkdir(parents=True)
    (folder / '__init__.py').write_text(textwrap.dedent('''
        from metaform import settings
        from metaform.module import Module
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        settings.text('greeting', 'yo')
        MODULE = Module(id='clash', purpose='Clashes.', summary='Clash.')
    '''))
    row = module_row(run, 'clash')
    assert row[1] == 'error' and 'already belongs to template' in row[3]
    assert run('template', 'greet', 'x').stdout.strip() == 'hello, x'


def test_module_that_crashes_on_import_is_reported_and_others_still_run(run, home):
    folder = home / 'modules' / 'crash'
    folder.mkdir(parents=True)
    (folder / '__init__.py').write_text("SUPPORTED_OS = ('linux', 'macos', 'windows')\nraise RuntimeError('boom')\n")
    row = module_row(run, 'crash')
    assert row[1] == 'error' and 'boom' in row[3]
    result = run('crash', 'x', ok=False)
    assert 'did not load' in result.stderr and 'metaform list modules' in result.stderr
    assert run('template', 'greet', 'x').stdout.strip() == 'hello, x'


def test_caution_verb_explains_first_and_runs_with_confirm(run):
    run('template', 'greet', 'ada')
    result = run('template', 'forget', ok=False)
    assert result.returncode != 0
    assert 'This deletes the greeting history.' in result.stderr
    assert 'metaform template forget --confirm' in result.stderr
    assert run('template', 'history').stdout.strip() == 'ada'
    run('template', 'forget', '--confirm')
    assert 'No greetings yet' in run('template', 'history').stdout


def test_confirm_is_not_a_switch_of_an_ordinary_verb(run):
    result = run('template', 'greet', 'x', '--confirm', ok=False)
    assert result.stderr.splitlines() == ['Error: template greet has no switch --confirm.',
                                          'Next: metaform template greet --help']


def test_status_shows_modules_and_a_narrowed_surface(run):
    on = sum(1 for line in run('list', 'modules').stdout.splitlines() if line.split()[1] == 'on')
    assert f'Modules: {on} on' in run().stdout.splitlines()
    run('set', '--commands', 'template')
    assert 'Commands: template' in run().stdout
