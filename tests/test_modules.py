"""Stage 1, step 2: modules, proven through the template module."""
import json
import textwrap


def test_template_module_is_listed_and_enabled_out_of_the_box(run):
    out = run('list', 'modules').stdout
    assert 'template' in out and 'on' in out


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


def test_event_published_by_one_verb_reaches_the_subscriber(run):
    run('template', 'greet', 'ada')
    run('template', 'greet', 'bob')
    assert run('template', 'history').stdout.split() == ['ada', 'bob']


def test_data_driven_select_setting(run):
    result = run('set', '--favorite', 'zed', ok=False)
    assert result.returncode != 0 and 'none yet' in result.stderr
    run('template', 'greet', 'zed')
    run('set', '--favorite', 'zed')
    assert 'favorite: zed' in run('config', '--show').stdout.replace('  ', ' ')


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
    assert 'template greet' in run('help', 'commands').stdout


def test_disable_and_enable_module(run):
    run('disable', 'module', 'template')
    result = run('template', 'greet', 'x', ok=False)
    assert result.returncode != 0 and 'metaform enable module template' in result.stderr
    assert 'template greet' not in run('help', 'commands').stdout
    run('enable', 'module', 'template')
    assert run('template', 'greet', 'x').stdout.strip() == 'hello, x'


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
    assert 'hello' in run('list', 'modules').stdout


def test_module_without_supported_os_is_refused_with_reason(run, home):
    folder = home / 'modules' / 'bad'
    folder.mkdir(parents=True)
    (folder / '__init__.py').write_text('raise SystemExit("must not run")\n')
    out = run('list', 'modules').stdout
    assert 'bad' in out and 'SUPPORTED_OS' in out


def test_commands_setting_narrows_the_surface_and_says_so(run):
    out = run('set', '--commands', 'chassis').stdout
    assert 'hidden' in out.lower()
    result = run('template', 'greet', 'x', ok=False)
    assert result.returncode != 0
    assert 'template greet' not in run('help', 'commands').stdout
    run('unset', '--commands')
    assert run('template', 'greet', 'x').stdout.strip() == 'hello, x'


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
    assert 'entry' in run('list', 'modules').stdout


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
    out = run('list', 'modules').stdout
    assert 'clash' in out and 'already belongs to template' in out
    assert run('template', 'greet', 'x').stdout.strip() == 'hello, x'


def test_module_that_crashes_on_import_is_reported_and_others_still_run(run, home):
    folder = home / 'modules' / 'crash'
    folder.mkdir(parents=True)
    (folder / '__init__.py').write_text("SUPPORTED_OS = ('linux', 'macos', 'windows')\nraise RuntimeError('boom')\n")
    out = run('list', 'modules').stdout
    assert 'crash' in out and 'boom' in out
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


def test_status_shows_modules_and_a_narrowed_surface(run):
    assert 'Modules: 1 on' in run().stdout
    run('set', '--commands', 'template')
    assert 'Commands: template' in run().stdout
