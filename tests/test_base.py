"""The common base and the module contract: declarations, discovery, lifecycle and events, BASE."""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.kind('fixture')

MODULES = Path(__file__).parents[1] / 'src' / 'metaform' / 'modules'
PUBLIC = {'metaform.module', 'metaform.settings', 'metaform.data', 'metaform.events', 'metaform.nonce',
          'metaform.prompt_files', 'metaform.axiom', 'metaform.home', 'metaform.outline', 'metaform.finish_xml'}
OS = "SUPPORTED_OS = ('linux', 'macos', 'windows')"


def module_ids(run):
    return {line.split()[0]: line.split()[1] for line in run('list', 'modules').stdout.splitlines() if line.strip()}


@pytest.mark.req('BASE-001')
def test_the_chassis_works_with_every_module_off(run, tmp_path):
    for identifier, state in module_ids(run).items():
        if state == 'on':
            run('disable', identifier)
    assert set(module_ids(run).values()) <= {'off'}
    folder = tmp_path / 'work'
    folder.mkdir()
    for args in ((), ('help',), ('config', '--show'), ('add', 'project', 'work', str(folder)),
                 ('set', '--project', 'work'), ('unset', '--project')):
        assert run(*args, cwd=folder).returncode == 0


@pytest.mark.req('BASE-001')
@pytest.mark.req('MCP-001')
def test_the_chassis_imports_with_every_module_package_unimportable(tmp_path):
    script = ("import importlib.abc, sys\n"
              "class Block(importlib.abc.MetaPathFinder):\n"
              "    def find_spec(self, name, path=None, target=None):\n"
              "        if name.startswith(('metaform.modules', 'metaform_module_', 'mcp')):\n"
              "            raise ImportError(name)\n"
              "sys.meta_path.insert(0, Block())\n"
              "import metaform, metaform.cli, metaform.data\n"
              "print('imported')\n")
    result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, encoding='utf-8',
                            env={**os.environ, 'METAFORM_HOME': str(tmp_path / 'h')}, check=False)
    assert result.stdout.strip() == 'imported', result.stderr


@pytest.mark.req('BASE-004')
@pytest.mark.req('STORE-023')
def test_every_shipped_module_imports_only_the_public_base():
    for folder in sorted(MODULES.iterdir()):
        for source in folder.rglob('*.py'):
            if 'tests' in source.parts:
                continue
            tree = ast.parse(source.read_text(encoding='utf-8'))
            package = '.'.join(('metaform', 'modules', *source.relative_to(MODULES).parts[:-1]))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.level:
                    target = importlib.util.resolve_name('.' * node.level + (node.module or ''), package)
                    if target == 'metaform':
                        assert all(f'metaform.{alias.name}' in PUBLIC for alias in node.names), source
                    elif not target.startswith(f'metaform.modules.{folder.name}'):
                        assert target in PUBLIC, (source, target)
                if isinstance(node, ast.ImportFrom) and node.module == 'metaform':
                    for alias in node.names:
                        assert f'metaform.{alias.name}' in PUBLIC, (source, alias.name)
                elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith('metaform'):
                    assert node.module in PUBLIC, (source, node.module)
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not alias.name.startswith('metaform') or alias.name in PUBLIC, (source, alias.name)
                        assert alias.name != 'sqlite3', source
                if isinstance(node, ast.ImportFrom) and node.module == 'sqlite3':
                    raise AssertionError(f'{source} imports sqlite3')
    for source in MODULES.rglob('*.py'):
        for node in ast.walk(ast.parse(source.read_text(encoding='utf-8'))):
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else \
                [node.module or ''] if isinstance(node, ast.ImportFrom) else []
            assert 'sqlite3' not in names, source


@pytest.mark.req('BASE-004')
@pytest.mark.parametrize('public', sorted(PUBLIC))
def test_importing_the_public_base_creates_no_files(tmp_path, public):
    home = tmp_path / 'missing-home'
    result = subprocess.run([sys.executable, '-c', f'import {public}'],
                            env={**os.environ, 'METAFORM_HOME': str(home)}, capture_output=True, text=True, encoding='utf-8', check=False)
    assert result.returncode == 0, result.stderr
    assert not home.exists()


@pytest.mark.req('BASE-004')
@pytest.mark.req('MCP-031')
def test_a_module_reads_its_own_prompts_through_the_public_base():
    from importlib import resources

    from metaform import prompt_files
    assert 'metaform.prompt_files' in PUBLIC
    folder = resources.files('metaform.modules.template')
    assert prompt_files.text(folder, 'instructions') == 'template is active.'
    assert prompt_files.required(folder, 'instructions') == 'template is active.'
    assert prompt_files.text(folder, 'no_such_prompt') is None
    with pytest.raises(LookupError):
        prompt_files.required(folder, 'no_such_prompt')


@pytest.mark.req('BASE-035')
def test_stop_needs_its_next_step():
    from metaform.module import Stop
    with pytest.raises(TypeError):
        Stop('Something went wrong.')  # type: ignore[call-arg]


@pytest.mark.req('BASE-035')
@pytest.mark.req('BASE-006')
@pytest.mark.req('BASE-043')
def test_a_declared_verb_gets_its_nouns_and_appears_in_help(run, user_module):
    user_module('scratch', f'''
        import json
        from metaform.module import Module, Noun, Verb
        {OS}
        def show(ctx):
            return {{'nouns': ctx.nouns}}
        MODULE = Module(id='scratch', summary='A scratch module.', purpose='Shows nouns. Details: metaform help scratch.',
                        verbs=(Verb('show', show, 'Show the nouns it received.',
                                    nouns=(Noun('first', 'The first word.'),
                                           Noun('count', 'A number.', kind='int', required=False),
                                           Noun('rest', 'Everything else.', required=False, many=True))),
                               Verb('local', show, 'Only on the command line.', surfaces=('cli',))))
    ''')
    got = json.loads(run('scratch', 'show', 'a', 'count=3', 'b', 'c', '--json').stdout)
    assert got == {'nouns': {'first': 'a', 'count': 3, 'rest': ['b', 'c']}}
    assert json.loads(run('scratch', 'show', 'a', '--json').stdout) == {'nouns': {'first': 'a'}}
    assert 'scratch show' in run('help', 'commands').stdout
    page = run('help', 'scratch').stdout
    assert 'show' in page and 'local' in page
    assert run('scratch', 'show', '--help').stdout.splitlines()[0] == \
        'Usage: metaform scratch show <first> [count=<int>] [rest...]'
    refused = run('scratch', 'show', ok=False)
    assert refused.returncode == 2 and refused.stderr.splitlines()[-1] == 'Next: metaform scratch show --help'
    early = run('scratch', 'show', 'count=3', 'a', ok=False)
    assert early.returncode == 2 and early.stderr.splitlines()[-1] == 'Next: metaform scratch show --help'
    wrong = run('scratch', 'show', 'a', 'count=three', ok=False)
    assert wrong.returncode == 2 and 'count' in wrong.stderr


@pytest.mark.req('BASE-043')
@pytest.mark.req('CLI-003')
def test_words_after_the_double_dash_are_plain_nouns(run, user_module):
    user_module('echoer', f'''
        from metaform.module import Module, Noun, Verb
        {OS}
        def echo(ctx):
            return ' '.join(ctx.nouns['words'])
        MODULE = Module(id='echoer', summary='Echo words.', purpose='Echoes. Details: metaform help echoer.',
                        verbs=(Verb('echo', echo, 'Echo the words.', nouns=(Noun('words', 'Words.', many=True),)),))
    ''')
    assert run('echoer', 'echo', '--', '-40', 'dBm', 'x=1').stdout == '-40 dBm x=1'
    refused = run('echoer', 'echo', '-40', ok=False)
    assert refused.returncode == 2


@pytest.mark.req('BASE-036')
def test_a_string_result_is_printed_byte_for_byte(run, user_module):
    user_module('texter', f'''
        from metaform.module import Module, Verb
        {OS}
        def text(ctx):
            return 'line one\\n  line two'
        MODULE = Module(id='texter', summary='Text.', purpose='Returns text. Details: metaform help texter.',
                        verbs=(Verb('text', text, 'Return text.'),))
    ''')
    assert run('texter', 'text').stdout == 'line one\n  line two'
    assert run('texter', 'text', '--json').stdout == 'line one\n  line two'


@pytest.mark.req('BASE-009')
def test_an_async_verb_runs_like_a_sync_one(run, user_module):
    user_module('waiter', f'''
        import asyncio
        from metaform.module import Module, Verb
        {OS}
        async def wait(ctx):
            await asyncio.sleep(0)
            return 'waited'
        MODULE = Module(id='waiter', summary='Waits.', purpose='Waits. Details: metaform help waiter.',
                        verbs=(Verb('wait', wait, 'Wait.'),))
    ''')
    assert run('waiter', 'wait').stdout == 'waited'


@pytest.mark.req('BASE-010')
@pytest.mark.req('BASE-032')
def test_one_failing_subscriber_never_hides_the_others(run, user_module, tmp_path):
    user_module('publisher', f'''
        from metaform.module import Module, Verb
        {OS}
        def shout(ctx):
            return ctx.publish('publisher.shouted', {{'word': 'hi'}})
        MODULE = Module(id='publisher', summary='Publishes.', purpose='Publishes. Details: metaform help publisher.',
                        verbs=(Verb('shout', shout, 'Publish an event.'),))
    ''')
    user_module('broken_listener', f'''
        from metaform.module import Module, Subscription
        {OS}
        def fail(payload, ctx):
            raise RuntimeError('listener failed')
        MODULE = Module(id='broken_listener', summary='Fails.', purpose='Fails. Details: metaform help broken_listener.',
                        subscriptions=(Subscription('publisher.shouted', fail),))
    ''')
    user_module('listener', f'''
        from metaform.module import Module, Subscription
        {OS}
        from metaform.data import Node
        def heard(payload, ctx):
            store = ctx.require_store()
            with store.atomic():
                store.layer('heard', 'listener', 'What the listener heard.', mutable=True, hideable=True,
                            provenance={{'module': 'listener'}})
                store.add_element('heard', 'code.listener')
                store.add_item('heard', Node('element', 'code.listener'), payload['word'])
            return {{'word': payload['word'], 'project': ctx.project}}
        MODULE = Module(id='listener', summary='Listens.', purpose='Listens. Details: metaform help listener.',
                        subscriptions=(Subscription('publisher.shouted', heard),))
    ''')
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    deliveries = json.loads(run('publisher', 'shout', '--json', cwd=folder).stdout)
    by_module = {delivery['module']: delivery for delivery in deliveries}
    assert by_module['broken_listener']['status'] == 'failed'
    assert 'listener failed' in by_module['broken_listener']['error']
    assert by_module['listener'] == {'module': 'listener', 'status': 'completed',
                                     'result': {'word': 'hi', 'project': 'proj'}}
    from metaform.data import Store
    assert [item.value for item in Store('proj').layer_items('heard').results] == ['hi']


@pytest.mark.req('BASE-013')
@pytest.mark.req('CLI-018')
def test_a_caution_verb_acts_only_with_confirm(run, user_module, tmp_path):
    marker = tmp_path / 'deleted'
    user_module('careful', f'''
        from pathlib import Path
        from metaform.module import Module, Verb
        {OS}
        def forget(ctx):
            Path({str(marker)!r}).write_text('gone')
            return 'forgotten'
        MODULE = Module(id='careful', summary='Careful.', purpose='Careful. Details: metaform help careful.',
                        verbs=(Verb('forget', forget, 'Forget everything.', caution='This deletes everything.'),))
    ''')
    refused = run('careful', 'forget', ok=False)
    assert refused.returncode == 2
    assert refused.stderr.splitlines() == ['Error: This deletes everything.',
                                           'Next: If you are sure: metaform careful forget --confirm']
    assert not marker.exists()
    run('careful', 'forget', '--confirm')
    assert marker.exists()


@pytest.mark.req('BASE-014')
@pytest.mark.req('BASE-037')
def test_a_module_named_like_a_chassis_verb_is_refused(module_row, user_module):
    user_module('export', f'''
        {OS}
        raise SystemExit('must not run')
    ''')
    row = module_row('export')
    assert row[1] == 'error' and 'chassis' in row[3]


def _package(site, name, body):
    import textwrap
    package = site / name
    package.mkdir(parents=True)
    (package / '__init__.py').write_text(textwrap.dedent(body))
    info = site / f'{name}-1.0.dist-info'
    info.mkdir()
    (info / 'METADATA').write_text(f'Metadata-Version: 2.1\nName: {name}\nVersion: 1.0\n')
    (info / 'entry_points.txt').write_text(f'[metaform.modules]\n{name} = {name}\n')


@pytest.mark.req('BASE-014')
@pytest.mark.req('BASE-037')
def test_a_second_module_with_one_id_is_refused_naming_the_first(home, tmp_path, user_module):
    user_module('shelf', f'''
        from metaform.module import Module
        {OS}
        MODULE = Module(id='shelf', summary='User shelf.', purpose='A shelf. Details: metaform help shelf.')
    ''')
    site = tmp_path / 'site'
    _package(site, 'shelf', f'''
        {OS}
        raise SystemExit('must not run')
    ''')
    env = {**os.environ, 'METAFORM_HOME': str(home), 'PYTHONPATH': str(site)}
    lines = subprocess.run([sys.executable, '-m', 'metaform', 'list', 'modules'], env=env, cwd=tmp_path,
                           capture_output=True, text=True, encoding='utf-8', check=False).stdout.splitlines()
    shelves = [line.split(None, 3) for line in lines if line.startswith('shelf')]
    assert [row[1:3] for row in shelves] == [['on', 'user'], ['error', 'entry']]
    assert 'user' in shelves[1][3]


@pytest.mark.req('BASE-014')
def test_an_entry_point_module_loads(home, tmp_path):
    site = tmp_path / 'site'
    _package(site, 'books', f'''
        from metaform.module import Module, Verb
        {OS}
        def count(ctx):
            return '3 books'
        MODULE = Module(id='books', summary='Count books.', purpose='Counts. Details: metaform help books.',
                        verbs=(Verb('count', count, 'Count the books.'),))
    ''')
    env = {**os.environ, 'METAFORM_HOME': str(home), 'PYTHONPATH': str(site)}
    out = subprocess.run([sys.executable, '-m', 'metaform', 'books', 'count'], env=env, cwd=tmp_path,
                         capture_output=True, text=True, encoding='utf-8', check=False).stdout
    assert out == '3 books'


def _project_module(source, name, body, **files):
    """Write a module into a project's place, `<source>/.metaform/modules/<name>/`, D93, with any other files."""
    import textwrap
    folder = source / '.metaform' / 'modules' / name
    folder.mkdir(parents=True)
    (folder / '__init__.py').write_text(textwrap.dedent(body))
    for file, text in files.items():
        (folder / f'{file}.py').write_text(textwrap.dedent(text))
    return folder


NOTES = f'''
    from metaform.module import Module, Verb
    {OS}
    def count(ctx):
        return 'proj notes'
    MODULE = Module(id='notes', summary='Proj notes.', purpose='Notes. Details: metaform help notes.',
                    verbs=(Verb('count', count, 'Count the notes.'),))
'''


@pytest.mark.req('BASE-014')
@pytest.mark.req('BASE-037')
@pytest.mark.req('PROJ-003')
def test_a_project_module_loads_only_for_the_active_selected_project(run, module_row, tmp_path):
    proj, other, outside = tmp_path / 'proj', tmp_path / 'other', tmp_path / 'outside'
    for folder in (proj / 'src', other, outside):
        folder.mkdir(parents=True)
    run('add', 'project', 'proj', str(proj))
    run('add', 'project', 'other', str(other))
    _project_module(proj, 'notes', NOTES)
    assert module_row('notes', cwd=proj / 'src')[1:3] == ['on', 'project']
    assert run('notes', 'count', cwd=proj / 'src').stdout == 'proj notes'
    assert module_row('notes', cwd=other) is None
    assert module_row('notes', cwd=outside) is None
    assert 'Unknown command: notes.' in run('notes', 'count', cwd=other, ok=False).stderr
    run('set', '--project', 'proj', cwd=other)
    assert run('notes', 'count', cwd=other).stdout == 'proj notes'
    run('set', '--project', 'other', cwd=proj)
    assert module_row('notes', cwd=proj) is None


@pytest.mark.req('BASE-014')
@pytest.mark.req('BASE-037')
@pytest.mark.cli_process
def test_a_project_module_never_displaces_a_same_name_module_of_an_earlier_place(home, tmp_path, user_module, run):
    proj = tmp_path / 'proj'
    proj.mkdir()
    run('add', 'project', 'proj', str(proj))
    user_module('shelf', f'''
        from metaform.module import Module
        {OS}
        MODULE = Module(id='shelf', summary='User shelf.', purpose='A shelf. Details: metaform help shelf.')
    ''')
    user_module('crate', '''
        SUPPORTED_OS = ('plan9',)
        raise SystemExit('must not run')
    ''')
    site = tmp_path / 'site'
    _package(site, 'books', f'''
        from metaform.module import Module
        {OS}
        MODULE = Module(id='books', summary='Entry books.', purpose='Books. Details: metaform help books.')
    ''')
    for name in ('shelf', 'books', 'crate'):
        _project_module(proj, name, f'''
            {OS}
            raise SystemExit('must not run')
        ''')
    lines = run('list', 'modules', cwd=proj, env={'PYTHONPATH': str(site)}).stdout.splitlines()
    rows = {(row[0], row[2]): row for row in (line.split(None, 3) for line in lines)
            if row[0] in ('shelf', 'books', 'crate')}
    assert sorted(rows) == [('books', 'entry'), ('books', 'project'), ('crate', 'project'), ('crate', 'user'),
                            ('shelf', 'project'), ('shelf', 'user')]
    assert rows['shelf', 'user'][1] == 'on' and rows['books', 'entry'][1] == 'on'
    assert rows['crate', 'user'][1] == 'error' and 'plan9' in rows['crate', 'user'][3]
    for name, place in (('shelf', 'user'), ('books', 'entry'), ('crate', 'user')):
        assert rows[name, 'project'][1] == 'error' and f'{place} place' in rows[name, 'project'][3]


def _snapshot(folder):
    return {path.relative_to(folder).as_posix(): path.read_bytes() if path.is_file() else None
            for path in sorted(folder.rglob('*'))}


@pytest.mark.req('BASE-014')
@pytest.mark.req('STORE-001')
def test_loading_and_running_a_project_module_leaves_the_project_folder_unchanged(home, tmp_path, user_module):
    proj = tmp_path / 'proj'
    proj.mkdir()
    from metaform import home as metaform_home
    metaform_home.add_project('proj', proj)
    body = f'''
        from metaform.module import Module, Verb
        from . import parts
        {OS}
        def count(ctx):
            from .deeper import later
            return parts.WORD + later.WORD
        MODULE = Module(id='{{name}}', summary='Notes.', purpose='Notes. Details: metaform help {{name}}.',
                        verbs=(Verb('count', count, 'Count the notes.'),))
    '''
    _project_module(proj, 'notes', body.replace('{name}', 'notes'), parts="WORD = 'proj '")
    (proj / '.metaform' / 'modules' / 'notes' / 'deeper').mkdir()
    (proj / '.metaform' / 'modules' / 'notes' / 'deeper' / '__init__.py').write_text('')
    (proj / '.metaform' / 'modules' / 'notes' / 'deeper' / 'later.py').write_text("WORD = 'notes'\n")
    control = user_module('control', body.replace('{name}', 'control').replace('from .deeper import later',
                                                                              'from . import parts as later'))
    (control / 'parts.py').write_text("WORD = 'control'\n")
    before = _snapshot(proj)
    env = {key: value for key, value in os.environ.items() if key not in ('PYTHONDONTWRITEBYTECODE', 'PYTHONPYCACHEPREFIX')}
    env['METAFORM_HOME'] = str(home)
    for args in (('list', 'modules'), ('notes', 'count'), ('control', 'count')):
        result = subprocess.run([sys.executable, '-m', 'metaform', *args], env=env, cwd=proj,
                                capture_output=True, text=True, encoding='utf-8', check=False)
        assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == 'controlcontrol'
    assert subprocess.run([sys.executable, '-m', 'metaform', 'notes', 'count'], env=env, cwd=proj,
                          capture_output=True, text=True, encoding='utf-8', check=False).stdout == 'proj notes'
    assert (control / '__pycache__').is_dir(), 'the control shows this Python writes bytecode beside a module'
    assert _snapshot(proj) == before


@pytest.mark.req('BASE-014')
@pytest.mark.req('BASE-037')
@pytest.mark.req('PROJ-003')
def test_a_long_lived_process_follows_the_folders_project_selection(home, tmp_path, monkeypatch):
    from metaform import home as metaform_home
    from metaform import loader, settings
    proj, other = tmp_path / 'proj', tmp_path / 'other'
    for folder in (proj, other):
        folder.mkdir()
        metaform_home.add_project(folder.name, folder)
    _project_module(proj, 'notes', NOTES)
    before = _snapshot(proj)
    monkeypatch.setattr(sys, 'dont_write_bytecode', False)
    monkeypatch.chdir(other)
    loader.reset()
    try:
        assert loader.get('notes') is None
        for _ in range(2):
            settings.put('project', 'proj', other)
            loader.follow_enabled()
            assert loader.get('notes') is not None and loader.get('notes').module is not None
            settings.put('project', 'other', other)
            loader.follow_enabled()
            assert loader.get('notes') is None
    finally:
        loader.reset()
    assert _snapshot(proj) == before


LEFTOVER ="from metaform import settings\nsettings.text('{name}_leftover', 'x')"
REFUSALS = {
    'missing_os': ("raise SystemExit('must not run')", 'SUPPORTED_OS is required'),
    'wrong_id': ((f"{OS}\n{{leftover}}\nfrom metaform.module import Module\n"
                 "MODULE = Module(id='other', summary='x', purpose='x')"), 'must match'),
    'twin_verbs': ((f"{OS}\n{{leftover}}\nfrom metaform.module import Module, Verb\n"
                   "MODULE = Module(id='twin_verbs', summary='x', purpose='x', verbs=(Verb('a', print, 'a'), "
                   "Verb('a', print, 'a')))"), 'share one name'),
    'bad_verb': ((f"{OS}\n{{leftover}}\nfrom metaform.module import Module, Verb\n"
                 "MODULE = Module(id='bad_verb', summary='x', purpose='x', verbs=(Verb('a' * 70, print, 'a'),))"),
                 'tool name'),
    'crashes': (f"{OS}\n{{leftover}}\nraise RuntimeError('boom')", 'RuntimeError: boom'),
    'no_purpose': ((f"{OS}\n{{leftover}}\nfrom metaform.module import Module\n"
                   "MODULE = Module(id='no_purpose', summary='x', purpose='')"), 'purpose'),
    'odd_os': ("SUPPORTED_OS = ('plan9',)\nraise SystemExit('must not run')", 'plan9'),
}


@pytest.mark.req('BASE-037')
@pytest.mark.req('BASE-015')
@pytest.mark.req('MCP-008')
@pytest.mark.parametrize('name', sorted(REFUSALS))
def test_a_module_that_cannot_load_is_listed_with_its_reason_and_adds_nothing(run, module_row, home, name):
    body, reason = REFUSALS[name]
    folder = home / 'modules' / name
    folder.mkdir(parents=True)
    (folder / '__init__.py').write_text(body.replace('{leftover}', LEFTOVER.format(name=name)) + '\n')
    row = module_row(name)
    assert row[1] == 'error' and reason in row[3] and 'Next:' not in row[3], row
    assert f'{name}_leftover' not in run('help', 'switches').stdout.replace('-', '_')
    assert f'{name} ' not in run('help', 'commands').stdout


@pytest.mark.req('BASE-015')
def test_a_non_literal_declaration_is_an_error_naming_it(module_row, user_module):
    user_module('computed', '''
        SUPPORTED_OS = tuple(['linux', 'macos', 'windows'])
        raise SystemExit('must not run')
    ''')
    row = module_row('computed')
    assert row[1] == 'error' and 'SUPPORTED_OS' in row[3]


@pytest.mark.req('BASE-017')
@pytest.mark.req('STORE-002')
def test_a_module_that_ships_disabled_is_off_until_enabled(run, home, module_row, user_module):
    user_module('quiet', f'''
        from metaform.module import Module
        {OS}
        SHIPS_DISABLED = True
        MODULE = Module(id='quiet', summary='Quiet.', purpose='Quiet. Details: metaform help quiet.')
    ''')
    assert module_row('quiet')[1] == 'off'
    assert run('enable', 'quiet').stdout.strip() == 'Module quiet: on'
    assert module_row('quiet')[1] == 'on'
    import sqlite3
    db = sqlite3.connect(home / 'metaform.sqlite3')
    db.execute("DELETE FROM module_state WHERE module_id='quiet'")
    db.commit()
    db.close()
    assert module_row('quiet')[1] == 'off'
    run('enable', 'quiet')
    run('disable', 'quiet')
    assert module_row('quiet')[1] == 'off'


@pytest.mark.req('BASE-017')
@pytest.mark.req('BASE-019')
def test_the_example_modules_ship_disabled(module_row):
    assert module_row('hello')[1] == 'off'
    assert module_row('template')[1] == 'off'


@pytest.mark.req('BASE-016')
def test_a_verb_off_its_systems_is_hidden_and_explains_itself(home, user_module, monkeypatch, capsys):
    import platform

    from metaform import cli, harness, loader
    user_module('narrow', '''
        from metaform.module import Module, Verb
        SUPPORTED_OS = ('linux', 'macos', 'windows', 'plan9')
        def here(ctx):
            return 'here'
        def elsewhere(ctx):
            return 'elsewhere'
        MODULE = Module(id='narrow', summary='Narrow.', purpose='Narrow. Details: metaform help narrow.',
                        verbs=(Verb('here', here, 'Runs everywhere.'),
                               Verb('elsewhere', elsewhere, 'Runs on one system.', supported_os=('plan9',))))
    ''')
    loader.reset()
    assert cli.main(['help', 'commands']) == 0
    listed = capsys.readouterr().out
    assert 'narrow here' in listed and 'narrow elsewhere' not in listed
    assert cli.main(['narrow', 'elsewhere']) == 2
    err = capsys.readouterr().err.removeprefix(f'Notice: {harness.NOTICE}\n').splitlines()
    assert err == ['Error: narrow elsewhere runs on plan9.', 'Next: metaform help narrow']
    assert cli.main(['help', 'narrow', 'elsewhere']) == 2
    assert capsys.readouterr().err.removeprefix(f'Notice: {harness.NOTICE}\n').splitlines() == err
    assert cli.main(['help', 'narrow']) == 0
    page = capsys.readouterr().out
    assert 'Not on this system' in page and page.index('Not on this system') < page.index('elsewhere')
    assert cli.main(['narrow', 'here']) == 0
    assert capsys.readouterr().out == 'here'
    monkeypatch.setattr(platform, 'system', lambda: 'Plan9')
    loader.reset()
    assert cli.main(['narrow', 'elsewhere']) == 0
    assert capsys.readouterr().out == 'elsewhere'
    loader.reset()


@pytest.mark.req('BASE-018')
@pytest.mark.req('QUAL-010')
def test_load_unload_and_reload_leave_one_registration_each(home, user_module):
    from metaform import events, loader, settings
    user_module('counted', '''
        from metaform import settings
        from metaform.module import Module, Subscription, Verb
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        settings.text('counted_word', 'x', help='A word.')
        STARTS = []
        def start(ctx):
            STARTS.append(ctx.module)
        def hear(payload, ctx):
            return 'heard'
        MODULE = Module(id='counted', summary='Counted.', purpose='Counted. Details: metaform help counted.',
                        verbs=(Verb('noop', lambda ctx: None, 'Nothing.'),),
                        subscriptions=(Subscription('counted.ping', hear),), start=start)
    ''')
    for _ in range(3):
        loader.reset()
        loaded = [item for item in loader.discover() if item.id == 'counted' and item.module is not None]
        assert len(loaded) == 1
        assert [key for key, item in settings.SCHEMA.items() if item.owner == 'counted'] == ['counted_word']
        from metaform.module import Context
        deliveries = events.publish('counted.ping', {}, Context(module='test', folder=home))
        assert [delivery['module'] for delivery in deliveries] == ['counted']
    loader.reset()
    assert not [key for key, item in settings.SCHEMA.items() if item.owner == 'counted']


@pytest.mark.req('BASE-018')
def test_a_failed_start_unloads_the_module(module_row, user_module, run):
    user_module('badstart', '''
        from metaform import settings
        from metaform.module import Module
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        settings.text('badstart_word', 'x')
        def start(ctx):
            raise RuntimeError('cannot start')
        MODULE = Module(id='badstart', summary='x', purpose='Fails to start. Details: metaform help badstart.',
                        start=start)
    ''')
    row = module_row('badstart')
    assert row[1] == 'error' and 'cannot start' in row[3]
    assert '--badstart-word' not in run('help', 'switches').stdout


@pytest.mark.req('BASE-018')
@pytest.mark.req('QUAL-010')
def test_unloading_cancels_the_modules_tasks_and_calls_stop(home, user_module):
    import asyncio

    from metaform import loader
    from metaform.module import Context
    user_module('spawner', '''
        import asyncio
        from metaform.module import Module, Verb
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        STOPPED = []
        TASKS = []
        async def work(ctx):
            TASKS.append(ctx.spawn(asyncio.sleep(3600)))
            return 'spawned'
        def stop(ctx):
            STOPPED.append(True)
        MODULE = Module(id='spawner', summary='x', purpose='Spawns. Details: metaform help spawner.',
                        verbs=(Verb('work', work, 'Spawn a task.'),), stop=stop)
    ''')
    loader.reset()
    found = next(item for item in loader.discover() if item.id == 'spawner')
    namespace = sys.modules[found.import_name]

    async def scenario():
        verb = found.module.verbs[0]
        await verb.run(Context(module='spawner', folder=home))
        task = namespace.TASKS[0]
        await loader.unload_async('spawner')
        return task
    task = asyncio.run(scenario())
    assert task.cancelled()
    assert namespace.STOPPED == [True]


@pytest.mark.req('BASE-034')
@pytest.mark.req('BASE-019')
def test_every_shipped_module_has_a_readme_with_the_template_headings():
    headings = [line for line in (MODULES / 'template' / 'README.md').read_text(encoding='utf-8').splitlines()
                if line.startswith('## ')]
    assert len(headings) >= 15
    missing = {}
    for folder in sorted(path for path in MODULES.iterdir() if (path / '__init__.py').is_file()):
        readme = folder / 'README.md'
        found = readme.read_text(encoding='utf-8').splitlines() if readme.is_file() else []
        absent = [heading for heading in headings if heading not in found]
        if absent:
            missing[folder.name] = absent
    assert missing == {}


@pytest.mark.req('BASE-019')
def test_both_example_modules_have_the_same_files():
    for name in ('hello', 'template'):
        folder = MODULES / name
        assert {'__init__.py', 'README.md', 'CHANGELOG.md', 'tests'} <= {path.name for path in folder.iterdir()}


@pytest.mark.req('BASE-009')
@pytest.mark.req('BASE-010')
def test_an_async_publish_never_blocks_its_loop_and_a_sync_one_there_is_refused(home, user_module):
    import asyncio

    from metaform import loader
    from metaform.module import Context, call
    user_module('slowear', '''
        import asyncio, time
        from metaform.module import Module, Subscription
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        async def hear_async(payload, ctx):
            await asyncio.sleep(0.3)
            return 'async heard'
        def hear_sync(payload, ctx):
            time.sleep(0.3)
            return 'sync heard'
        MODULE = Module(id='slowear', summary='Listens slowly.', purpose='Listens. Details: metaform help slowear.',
                        subscriptions=(Subscription('slowear.ping', hear_async), Subscription('slowear.ping', hear_sync)))
    ''')
    loader.reset()
    loader.discover()
    ticks = []

    async def main():
        async def ticker():
            while True:
                ticks.append(1)
                await asyncio.sleep(0.02)
        running = asyncio.get_running_loop().create_task(ticker())
        source = Context(module='test', folder=home)
        deliveries = await source.publish_async('slowear.ping', {})
        with pytest.raises(RuntimeError, match='publish_async'):
            source.publish('slowear.ping', {})

        async def later():
            return 'x'
        with pytest.raises(RuntimeError):
            call(later)
        running.cancel()
        return deliveries
    deliveries = asyncio.run(main())
    assert sorted(delivery['result'] for delivery in deliveries) == ['async heard', 'sync heard']
    assert len(ticks) >= 15
