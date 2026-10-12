"""`metaform install`: checks, registration, backups, the skill and the proof, MCP-010 to MCP-021 and MCP-023."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fakes import calls, recorder, server

from metaform import __version__

pytestmark = pytest.mark.kind('simulation')

ROOT = Path(__file__).parents[1]
SKILL = (ROOT / 'src' / 'metaform' / 'skill' / 'SKILL.md')
CURSOR_BEFORE = {'mcpServers': {'other': {'command': 'other-server', 'args': []}}}
VERSION_PARTS = tuple(int(part) for part in __version__.split('.'))
NEWER_UPDATE = '.'.join(str(part) for part in (*VERSION_PARTS[:3], VERSION_PARTS[3] + 10))
NEWER_DATE = f'{VERSION_PARTS[0] + 1}.1.1.1'
OLDER_VERSION = f'{VERSION_PARTS[0] - 1}.1.1.1'


@pytest.fixture
def machine(tmp_path):
    """A user home and a PATH holding only fake tools: uv, uvx serving a fake server, claude and codex."""
    user = tmp_path / 'user'
    user.mkdir()
    bin_folder = tmp_path / 'bin'
    recorder(bin_folder, 'uv')
    server(bin_folder, 'uvx')
    recorder(bin_folder, 'claude')
    recorder(bin_folder, 'codex')
    (user / '.cursor').mkdir()
    (user / '.cursor' / 'mcp.json').write_text(json.dumps(CURSOR_BEFORE, indent=2), encoding='utf-8')
    wheel = tmp_path / 'metaform-0.2.0-py3-none-any.whl'
    wheel.write_bytes(b'not really a wheel')
    env = {'HOME': str(user), 'USERPROFILE': str(user), 'PATH': str(bin_folder), 'METAFORM_WHEEL': str(wheel)}
    return {'user': user, 'bin': bin_folder, 'wheel': wheel, 'env': env, 'folder': tmp_path}


def tree(folder: Path) -> dict[str, bytes]:
    return {str(path.relative_to(folder)): path.read_bytes() for path in sorted(folder.rglob('*')) if path.is_file()}


def entry(wheel):
    return ['uvx', '--from', str(wheel), 'metaform', 'mcp', 'serve']


@pytest.mark.req('BASE-001')
@pytest.mark.req('MCP-010')
@pytest.mark.parametrize('disabled', ['mcp', 'all'])
def test_without_a_server_install_skills_without_touching_mcp(run, machine, home, disabled):
    modules = ['mcp'] if disabled == 'mcp' else [
        line.split()[0] for line in run('list', 'modules').stdout.splitlines() if line.strip()]
    for module in modules:
        run('disable', module)
    env = {**machine['env'], 'METAFORM_WHEEL': ''}
    for binary in ('uv', 'uvx'):
        path = machine['bin'] / binary
        path.with_suffix('.cmd').unlink(missing_ok=True)
        path.unlink(missing_ok=True)
    config = machine['user'] / '.cursor' / 'mcp.json'
    original = config.read_bytes()
    out = run('install', 'claude', 'cursor', cwd=machine['folder'], env=env).stdout
    assert 'no enabled module declares an MCP server' in out
    assert config.read_bytes() == original and calls(machine['bin'], 'claude') == []
    assert not (machine['bin'] / 'uvx.requests').exists()
    assert (machine['user'] / '.claude/skills/metaform/SKILL.md').read_bytes() == SKILL.read_bytes()
    assert (machine['user'] / '.cursor/skills/metaform/SKILL.md').read_bytes() == SKILL.read_bytes()
    assert (home / 'skills/metaform/SKILL.md').read_bytes() == SKILL.read_bytes()
    page = run('help', 'provision').stdout
    assert 'no enabled module declares an MCP server' in page and 'metaform mcp serve' not in page
    run('uninstall', 'all', cwd=machine['folder'], env=env)
    assert config.read_bytes() == original and calls(machine['bin'], 'claude') == []
    assert not (home / 'skills/metaform/SKILL.md').exists()


@pytest.mark.req('BASE-001')
@pytest.mark.req('MCP-010')
def test_install_works_with_the_module_folder_physically_absent(machine, home, monkeypatch, tmp_path):
    from metaform import install, loader
    empty = tmp_path / 'absent-modules'
    monkeypatch.setattr(loader, 'SYSTEM', empty)
    monkeypatch.chdir(machine['folder'])
    for key, value in machine['env'].items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv('METAFORM_WHEEL', '')
    output = []
    install.install(['claude'], output.append)
    assert any('no enabled module declares an MCP server' in line for line in output)
    assert calls(machine['bin'], 'claude') == []
    assert (home / 'skills/metaform/SKILL.md').read_bytes() == SKILL.read_bytes()


@pytest.mark.req('BASE-035')
@pytest.mark.req('MCP-010')
def test_install_and_provision_use_the_declaring_modules_server(run, machine, user_module):
    user_module('bridge', '''
        from metaform.module import Module, Verb
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        MODULE = Module(id='bridge', summary='A server.', purpose='A server.', mcp_server='listen',
                        verbs=(Verb('listen', lambda ctx: None, 'Serve.', surfaces=('cli',), transport=True),))
    ''')
    run('disable', 'mcp')
    out = run('install', 'claude', cwd=machine['folder'], env=machine['env']).stdout
    command = ['uvx', '--from', str(machine['wheel']), 'metaform', 'bridge', 'listen']
    assert calls(machine['bin'], 'claude')[-1][-len(command):] == command
    assert 'claude: server starts, 2 tools' in out
    page = run('help', 'provision').stdout
    assert 'metaform bridge listen' in page and 'metaform mcp serve' not in page
    run('enable', 'mcp')
    refused = run('install', 'claude', cwd=machine['folder'], env=machine['env'], ok=False)
    assert refused.returncode == 2 and '--install-server' in refused.stderr
    run('set', '--install-server', 'bridge')
    run('install', 'claude', cwd=machine['folder'], env=machine['env'])
    assert calls(machine['bin'], 'claude')[-1][-len(command):] == command
    run('disable', 'bridge')
    refused = run('install', 'claude', cwd=machine['folder'], env=machine['env'], ok=False)
    assert refused.returncode == 2 and '--install-server' in refused.stderr


@pytest.mark.req('BASE-035')
@pytest.mark.parametrize('declaration', [
    "mcp_server='missing', verbs=()",
    "mcp_server='listen', verbs=(Verb('listen', lambda ctx: None, 'Serve.'),)",
    "mcp_server='listen', verbs=(Verb('listen', lambda ctx: None, 'Serve.', transport=True, surfaces=('mcp',)),)",
    ("mcp_server='listen', verbs=(Verb('listen', lambda ctx: None, 'Serve.', transport=True, "
     "nouns=(Noun('required', 'Required.'),)),)"),
])
def test_invalid_server_declarations_are_reported_and_never_registered(run, machine, user_module, declaration):
    user_module('badserver', f'''
        from metaform.module import Module, Verb, Noun
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        MODULE = Module(id='badserver', summary='Bad server.', purpose='Bad server.', {declaration})
    ''')
    row = next(line for line in run('list', 'modules').stdout.splitlines() if line.startswith('badserver '))
    assert 'error' in row and 'mcp_server' in row
    run('disable', 'mcp')
    run('install', 'claude', cwd=machine['folder'], env={**machine['env'], 'METAFORM_WHEEL': ''})
    assert calls(machine['bin'], 'claude') == []


@pytest.mark.req('MCP-019')
@pytest.mark.req('MCP-020')
def test_skill_only_rerun_preserves_an_existing_registration_and_its_ownership(run, machine):
    run('install', 'claude', 'cursor', cwd=machine['folder'], env=machine['env'])
    config = machine['user'] / '.cursor' / 'mcp.json'
    original = config.read_bytes()
    previous_calls = calls(machine['bin'], 'claude')
    run('disable', 'mcp')
    run('install', 'claude', 'cursor', cwd=machine['folder'], env={**machine['env'], 'METAFORM_WHEEL': ''})
    assert config.read_bytes() == original and calls(machine['bin'], 'claude') == previous_calls
    run('uninstall', 'all', cwd=machine['folder'], env={**machine['env'], 'METAFORM_WHEEL': ''})
    assert json.loads(config.read_text()) == CURSOR_BEFORE
    assert calls(machine['bin'], 'claude')[-1][:2] == ['mcp', 'remove']


@pytest.mark.req('MCP-013')
def test_a_missing_uv_stops_before_anything_changes(run, machine):
    (machine['bin'] / ('uv.cmd' if (machine['bin'] / 'uv.cmd').exists() else 'uv')).unlink()
    before = tree(machine['user'])
    result = run('install', 'claude', cwd=machine['folder'], env=machine['env'], ok=False)
    assert result.returncode != 0
    lines = result.stdout.splitlines() + result.stderr.splitlines()
    nexts = [line for line in lines if line.startswith('Next: ')]
    assert len(nexts) == 1 and 'install' in nexts[0] and 'uv' in nexts[0]
    assert tree(machine['user']) == before and calls(machine['bin'], 'claude') == []


@pytest.mark.req('MCP-010')
def test_with_no_wheel_to_register_install_names_the_build(run, machine, home):
    env = dict(machine['env'])
    env.pop('METAFORM_WHEEL')
    before = tree(machine['user'])
    result = run('install', 'claude', cwd=machine['folder'], env={**env, 'METAFORM_WHEEL': ''}, ok=False)
    assert result.returncode != 0 and result.stderr.splitlines()[-1] == 'Next: metaform build'
    assert tree(machine['user']) == before


@pytest.mark.req('MCP-014')
@pytest.mark.req('CLI-025')
def test_without_a_terminal_or_names_nothing_changes_and_both_forms_are_named(run, machine):
    before = tree(machine['user'])
    result = run('install', cwd=machine['folder'], env=machine['env'], ok=False, input='')
    assert result.returncode == 2
    assert result.stderr.splitlines()[-1] == 'Next: metaform install <tool>... or metaform install all'
    assert tree(machine['user']) == before


@pytest.mark.req('MCP-014')
@pytest.mark.req('MCP-016')
@pytest.mark.req('MCP-021')
def test_install_claude_touches_only_claude_and_shared_skills(run, machine, home):
    before = tree(machine['user'])
    out = run('install', 'claude', cwd=machine['folder'], env=machine['env']).stdout
    assert calls(machine['bin'], 'claude')[-1] == ['mcp', 'add', '--transport', 'stdio', '--scope', 'user',
                                                   'metaform', '--', *entry(machine['wheel'])]
    assert calls(machine['bin'], 'codex') == []
    changed = {name for name, data in tree(machine['user']).items() if before.get(name) != data}
    assert changed == {str(Path('.claude/skills/metaform/SKILL.md')), str(Path('.agents/skills/metaform/SKILL.md')),
                       str(Path('.claude/skills/metaform-node/SKILL.md')),
                       str(Path('.claude/CLAUDE.md')), str(Path('.claude/settings.json'))}
    for copy in (machine['user'] / '.claude' / 'skills' / 'metaform' / 'SKILL.md',
                 home / 'skills' / 'metaform' / 'SKILL.md'):
        assert copy.read_bytes() == SKILL.read_bytes()
    assert out.splitlines()[-1].startswith('Next: ')
    assert 'claude: server starts, 2 tools' in out


@pytest.mark.req('MCP-014')
@pytest.mark.req('MCP-015')
@pytest.mark.req('MCP-016')
def test_install_all_merges_cursor_and_backs_up_every_changed_file(run, machine, home):
    original = (machine['user'] / '.cursor' / 'mcp.json').read_bytes()
    out = run('install', 'all', cwd=machine['folder'], env=machine['env']).stdout
    assert calls(machine['bin'], 'claude') and calls(machine['bin'], 'codex')[-1] == [
        'mcp', 'add', 'metaform', '--', *entry(machine['wheel'])]
    merged = json.loads((machine['user'] / '.cursor' / 'mcp.json').read_text())
    assert merged['mcpServers']['other'] == CURSOR_BEFORE['mcpServers']['other']
    assert merged['mcpServers']['metaform'] == {'command': 'uvx', 'args': entry(machine['wheel'])[1:]}
    backups = list((home / 'backups' / 'install').rglob('mcp.json'))
    assert len(backups) == 1 and backups[0].read_bytes() == original
    assert backups[0].parts[-2:] == ('.cursor', 'mcp.json')
    for tool in ('claude', 'codex', 'cursor'):
        assert f'{tool}: server starts, 2 tools' in out
    assert (machine['user'] / '.cursor' / 'skills' / 'metaform' / 'SKILL.md').is_file()


@pytest.mark.req('MCP-019')
def test_running_install_twice_leaves_one_entry(run, machine):
    run('install', 'claude', 'cursor', cwd=machine['folder'], env=machine['env'])
    run('install', 'claude', 'cursor', cwd=machine['folder'], env=machine['env'])
    assert json.loads((machine['bin'] / 'claude.servers').read_text()) == ['metaform']
    merged = json.loads((machine['user'] / '.cursor' / 'mcp.json').read_text())
    assert list(merged['mcpServers']) == ['other', 'metaform']


@pytest.mark.req('MCP-019')
def test_install_replaces_an_entry_it_has_no_record_of_and_continues(run, machine, home):
    """The chassis database holding the install record was set aside, and the next install stopped
    at claude's own entry, "MCP server metaform already exists". Install replaces the one entry and goes on."""
    run('install', 'claude', cwd=machine['folder'], env=machine['env'])
    for name in ('metaform.sqlite3', 'metaform.sqlite3-wal', 'metaform.sqlite3-shm'):
        (home / name).unlink(missing_ok=True)
    newer = machine['folder'] / 'metaform-0.3.0-py3-none-any.whl'
    newer.write_bytes(b'not really a wheel either')
    result = run('install', 'claude', cwd=machine['folder'], env={**machine['env'], 'METAFORM_WHEEL': str(newer)})
    assert 'claude: server starts' in result.stdout
    assert json.loads((machine['bin'] / 'claude.servers').read_text()) == ['metaform']
    assert calls(machine['bin'], 'claude')[-1] == ['mcp', 'add', '--transport', 'stdio', '--scope', 'user',
                                                  'metaform', '--', *entry(newer)]


@pytest.mark.req('MCP-014')
def test_a_tool_that_is_not_detected_is_refused(run, machine):
    result = run('install', 'gemini', cwd=machine['folder'], env=machine['env'], ok=False)
    assert result.returncode == 2 and result.stderr.splitlines()[-1].startswith('Next: metaform install')


@pytest.mark.req('MCP-017')
def test_a_registration_that_cannot_start_fails_its_proof(run, machine):
    (machine['bin'] / ('uvx.py')).write_text('import sys\nsys.exit(3)\n', encoding='utf-8')
    result = run('install', 'claude', cwd=machine['folder'], env=machine['env'], ok=False)
    assert result.returncode == 1
    assert 'claude: failed' in result.stdout


@pytest.mark.req('MCP-017')
def test_the_probe_passes_a_server_that_answers(tmp_path):
    """MCP 2026-07-28: the proof sends server/discover and tools/list, each with the per-request _meta, and no
    initialize handshake; the fake server answers only that."""
    from metaform.probe import probe
    launcher = server(tmp_path / 'bin', 'fake-server')
    passed = probe([str(launcher)], cwd=tmp_path)
    assert passed.ok and passed.tools == 2 and passed.instructions == 'Fake instructions.'
    sent = [json.loads(line) for line in (tmp_path / 'bin' / 'fake-server.requests').read_text().splitlines()]
    assert [message['method'] for message in sent] == ['server/discover', 'tools/list']
    for message in sent:
        meta = message['params']['_meta']
        assert meta['io.modelcontextprotocol/protocolVersion'] == '2026-07-28'
        assert meta['io.modelcontextprotocol/clientCapabilities'] == {}
        assert meta['io.modelcontextprotocol/clientInfo']['name'] == 'metaform-install'
    failed = probe([str(tmp_path / 'missing-server')], cwd=tmp_path)
    assert not failed.ok and failed.reason


@pytest.mark.req('MCP-021')
def test_enabling_a_module_changes_no_skill_file(run, machine, home):
    run('install', 'claude', cwd=machine['folder'], env=machine['env'])
    before = tree(machine['user'])
    run('enable', 'hello', cwd=machine['folder'], env=machine['env'])
    assert tree(machine['user']) == before
    assert not any(path.name == 'SKILL.md' for path in machine['folder'].glob('*'))


@pytest.mark.req('MCP-015')
@pytest.mark.req('MCP-019')
def test_a_tool_that_fails_after_another_registered_leaves_that_one_recorded_for_the_rerun(run, machine):
    codex = machine['bin'] / 'codex.py'
    working = codex.read_text(encoding='utf-8')
    codex.write_text('import sys\nprint("codex cannot add", file=sys.stderr)\nsys.exit(1)\n', encoding='utf-8')
    failed = run('install', 'claude', 'codex', cwd=machine['folder'], env=machine['env'], ok=False)
    assert failed.returncode != 0 and 'codex' in failed.stderr
    codex.write_text(working, encoding='utf-8')
    run('install', 'claude', 'codex', cwd=machine['folder'], env=machine['env'])
    assert [call[:2] for call in calls(machine['bin'], 'claude')] == [['mcp', 'add'], ['mcp', 'remove'],
                                                                      ['mcp', 'add']]
    assert json.loads((machine['bin'] / 'claude.servers').read_text()) == ['metaform']


@pytest.mark.req('MCP-015')
def test_a_config_that_is_not_a_json_object_is_refused_naming_it_and_its_backup(run, machine, home):
    config = machine['user'] / '.cursor' / 'mcp.json'
    config.write_text('// my servers\n{"mcpServers": {}}\n', encoding='utf-8')
    before = config.read_bytes()
    refused = run('install', 'cursor', cwd=machine['folder'], env=machine['env'], ok=False)
    assert refused.returncode != 0 and str(config) in refused.stderr
    backups = list((home / 'backups' / 'install').rglob('mcp.json'))
    assert len(backups) == 1 and str(backups[0]) in refused.stderr
    assert config.read_bytes() == before


@pytest.mark.req('MCP-015')
def test_a_tool_command_that_hangs_stops_at_its_timeout(machine, home, monkeypatch):
    from fakes import executable

    from metaform import install
    executable(machine['bin'], 'claude', 'import time\ntime.sleep(30)\n')
    for key, value in machine['env'].items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(install, 'TOOL_TIMEOUT', 1)
    said: list[str] = []
    with pytest.raises(install.Failed) as stopped:
        install.install(['claude'], said.append)
    assert 'claude' in str(stopped.value) and 'did not finish' in str(stopped.value)


def skills(folder: Path) -> list[str]:
    return sorted(str(path.relative_to(folder)) for path in folder.rglob('SKILL.md') if 'metaform' in path.parts)


@pytest.mark.req('MCP-020')
def test_uninstall_removes_what_install_added_and_leaves_every_other_entry(run, machine, home):
    before = tree(machine['user'])
    run('install', 'claude', 'codex', 'cursor', cwd=machine['folder'], env=machine['env'])
    installed = (machine['user'] / '.cursor' / 'mcp.json').read_bytes()
    out = run('uninstall', 'all', cwd=machine['folder'], env=machine['env']).stdout
    assert calls(machine['bin'], 'claude')[-1] == ['mcp', 'remove', '--scope', 'user', 'metaform']
    assert calls(machine['bin'], 'codex')[-1] == ['mcp', 'remove', 'metaform']
    for tool in ('claude', 'codex'):
        assert json.loads((machine['bin'] / f'{tool}.servers').read_text()) == []
    assert json.loads((machine['user'] / '.cursor' / 'mcp.json').read_text()) == CURSOR_BEFORE
    assert skills(machine['user']) == [] and skills(home / 'skills') == []
    after = tree(machine['user'])
    # Instructions remain as files, with the installed block removed. Empty hook settings hold no additions.
    assert after.pop(str(Path('.claude/CLAUDE.md'))) == b''
    assert after.pop(str(Path('.codex/AGENTS.md'))) == b''
    assert json.loads(after.pop(str(Path('.claude/settings.json')))) == {}
    assert {name: data for name, data in after.items() if not name.endswith('mcp.json')} == \
        {name: data for name, data in before.items() if not name.endswith('mcp.json')}
    backups = list((home / 'backups' / 'uninstall').rglob('mcp.json'))
    assert len(backups) == 1 and backups[0].read_bytes() == installed
    assert (home / 'metaform.sqlite3').is_file() and str(home) in out
    again = run('uninstall', 'all', cwd=machine['folder'], env=machine['env'], ok=False)
    assert again.returncode != 0 and 'Next: metaform install' in again.stderr


@pytest.mark.req('MCP-020')
def test_uninstalling_one_tool_keeps_the_others_and_a_users_own_later_entries(run, machine, home):
    run('install', 'claude', 'cursor', cwd=machine['folder'], env=machine['env'])
    config = machine['user'] / '.cursor' / 'mcp.json'
    edited = json.loads(config.read_text())
    edited['mcpServers']['mine'] = {'command': 'mine', 'args': ['--fast']}
    config.write_text(json.dumps(edited), encoding='utf-8')
    run('uninstall', 'cursor', cwd=machine['folder'], env=machine['env'])
    assert json.loads(config.read_text())['mcpServers'] == {**CURSOR_BEFORE['mcpServers'],
                                                            'mine': {'command': 'mine', 'args': ['--fast']}}
    assert json.loads((machine['bin'] / 'claude.servers').read_text()) == ['metaform']
    assert skills(machine['user']) == [str(Path('.agents/skills/metaform/SKILL.md')),
                                       str(Path('.claude/skills/metaform/SKILL.md'))]
    assert (home / 'skills' / 'metaform' / 'SKILL.md').is_file()
    refused = run('uninstall', 'cursor', cwd=machine['folder'], env=machine['env'], ok=False)
    assert refused.returncode == 2 and 'cursor' in refused.stderr


@pytest.mark.req('MCP-020')
@pytest.mark.req('MCP-014')
def test_uninstall_without_a_terminal_or_names_changes_nothing(run, machine, home):
    run('install', 'claude', cwd=machine['folder'], env=machine['env'])
    before = tree(machine['user'])
    result = run('uninstall', cwd=machine['folder'], env=machine['env'], ok=False, input='')
    assert result.returncode == 2
    assert result.stderr.splitlines()[-1] == 'Next: metaform uninstall <tool>... or metaform uninstall all'
    assert tree(machine['user']) == before and calls(machine['bin'], 'claude')[-1][:2] == ['mcp', 'add']


@pytest.mark.req('BASE-047')
@pytest.mark.parametrize('version', [NEWER_UPDATE, NEWER_DATE])
def test_a_wheel_refuses_a_newer_installed_version_before_setup(run, machine, home, version):
    from fakes import executable

    executable(machine['bin'], 'metaform', f'import sys\nassert sys.argv[1:] == ["--version"]\nprint("metaform {version}")')
    from metaform import home as metaform_home
    metaform_home.set_meta('installed_version', OLDER_VERSION)
    metaform_home.set_meta('last_run_version', OLDER_VERSION)
    before = tree(machine['user'])
    refused = run('install', 'claude', cwd=machine['folder'], env=machine['env'], ok=False)
    assert refused.returncode == 2 and version in refused.stderr and 'force=true' in refused.stderr
    assert calls(machine['bin'], 'uv') == calls(machine['bin'], 'claude') == []
    assert tree(machine['user']) == before
    assert metaform_home.meta('installed_version') == metaform_home.meta('last_run_version') == OLDER_VERSION


@pytest.mark.req('BASE-047')
@pytest.mark.parametrize('installed', [False, True, 'same'])
@pytest.mark.parametrize('force', [False, True])
def test_a_permitted_wheel_installs_before_setup_and_authorizes_the_next_run(run, machine, installed, force):
    from fakes import executable

    from metaform import home as metaform_home
    previous = NEWER_DATE if force else OLDER_VERSION
    if installed:
        executable_version = __version__ if installed == 'same' else previous
        executable(machine['bin'], 'metaform', f'import sys\nassert sys.argv[1:] == ["--version"]\nprint("metaform {executable_version}")')
    metaform_home.set_meta('last_run_version', previous)
    metaform_home.set_meta('installed_version', previous)
    read_approval = ('import os, sqlite3\n'
                     'db = sqlite3.connect(os.path.join(os.environ["METAFORM_HOME"], "metaform.sqlite3"))\n'
                     'approval = db.execute("SELECT value FROM meta WHERE key=\'installed_version\'").fetchone()[0]\n'
                     'db.close()\n')
    uv_script = machine['bin'] / 'uv.py'
    uv_script.write_text(uv_script.read_text(encoding='utf-8') +
                         '\n' + read_approval + f'assert approval == {previous!r}\n',
                         encoding='utf-8')
    claude_script = machine['bin'] / 'claude.py'
    claude_script.write_text(read_approval + f'assert approval == {__version__!r}\n' +
                             claude_script.read_text(encoding='utf-8'), encoding='utf-8')
    result = run('install', 'claude', f'force={str(force).lower()}', cwd=machine['folder'], env=machine['env'])
    assert calls(machine['bin'], 'uv') == [['tool', 'install', '--force', str(machine['wheel'])]]
    assert result.stdout.index('Installed:') < result.stdout.index('Changes:')
    assert metaform_home.meta('installed_version') == __version__
    run('list', 'projects', env={**machine['env'], 'METAFORM_WHEEL': ''})
    assert metaform_home.meta('last_run_version') == __version__


@pytest.mark.req('BASE-047')
def test_a_failed_wheel_install_records_no_success_and_never_sets_up_tools(run, machine):
    from fakes import executable

    from metaform import home as metaform_home
    executable(machine['bin'], 'uv', 'import sys\nprint("cannot install", file=sys.stderr)\nsys.exit(1)')
    before = tree(machine['user'])
    failed = run('install', 'claude', cwd=machine['folder'], env=machine['env'], ok=False)
    assert failed.returncode == 1 and 'cannot install' in failed.stderr
    assert metaform_home.meta('installed_version') is None
    assert calls(machine['bin'], 'claude') == [] and tree(machine['user']) == before


@pytest.mark.req('BASE-047')
@pytest.mark.parametrize('record', ['installed_version', 'last_run_version'])
def test_the_stage_checks_home_history_even_after_a_raw_install(run, machine, record):
    from fakes import executable

    from metaform import home as metaform_home
    executable(machine['bin'], 'metaform', f'print("metaform {OLDER_VERSION}")')
    metaform_home.set_meta(record, NEWER_DATE)
    refused = run('install', 'claude', cwd=machine['folder'], env=machine['env'], ok=False)
    assert refused.returncode == 2 and NEWER_DATE in refused.stderr
    assert calls(machine['bin'], 'uv') == calls(machine['bin'], 'claude') == []
    assert metaform_home.meta(record) == NEWER_DATE
    other = 'installed_version' if record == 'last_run_version' else 'last_run_version'
    assert metaform_home.meta(other) is None


@pytest.mark.req('BASE-047')
def test_an_installed_copy_only_sets_up_tools_and_force_recovers_a_raw_downgrade(run, machine):
    from metaform import home as metaform_home
    metaform_home.set_meta('last_build', str(machine['wheel']))
    metaform_home.set_meta('last_run_version', NEWER_DATE)
    run('install', 'claude', 'force=true', cwd=machine['folder'],
        env={**machine['env'], 'METAFORM_WHEEL': ''})
    assert calls(machine['bin'], 'uv') == []
    assert calls(machine['bin'], 'claude')[0][:2] == ['mcp', 'add']
    assert metaform_home.meta('installed_version') == metaform_home.meta('last_run_version') == __version__
    run('list', 'projects', env={**machine['env'], 'METAFORM_WHEEL': ''})


@pytest.mark.req('BASE-047')
@pytest.mark.parametrize('force', ['false', 'yes'])
def test_force_must_be_true_to_allow_a_downgrade(run, machine, force):
    from metaform import home as metaform_home
    metaform_home.set_meta('last_run_version', NEWER_DATE)
    refused = run('install', 'claude', f'force={force}', cwd=machine['folder'], env=machine['env'], ok=False)
    assert refused.returncode == 2
    assert calls(machine['bin'], 'uv') == calls(machine['bin'], 'claude') == []


@pytest.mark.req('BASE-047')
def test_first_run_checks_a_raw_downgrade_without_changing_its_version_records(run, home, tmp_path):
    from metaform import home as metaform_home
    metaform_home.set_meta('installed_version', OLDER_VERSION)
    metaform_home.set_meta('last_run_version', NEWER_DATE)
    folder = tmp_path / 'refused-project'
    folder.mkdir()
    refused = run('add', 'project', 'refused', str(folder), env={'METAFORM_WHEEL': ''}, ok=False)
    assert refused.returncode == 2 and __version__ in refused.stderr and NEWER_DATE in refused.stderr
    assert refused.stderr.splitlines()[-1] == 'Next: metaform install force=true'
    assert metaform_home.meta('installed_version') == OLDER_VERSION
    assert metaform_home.meta('last_run_version') == NEWER_DATE
    assert not metaform_home.projects()
    assert not (home / 'projects').exists()
    assert run('--version', env={'METAFORM_WHEEL': ''}).stdout.strip() == f'metaform {__version__}'
    assert metaform_home.meta('last_run_version') == NEWER_DATE


@pytest.mark.req('BASE-047')
def test_a_raw_upgrade_records_its_version_and_a_direct_wheel_does_not(run, machine):
    from metaform import home as metaform_home
    metaform_home.set_meta('installed_version', OLDER_VERSION)
    metaform_home.set_meta('last_run_version', OLDER_VERSION)
    run('list', 'projects', env={'METAFORM_WHEEL': ''})
    assert metaform_home.meta('last_run_version') == __version__
    assert metaform_home.meta('installed_version') is None
    metaform_home.set_meta('last_run_version', NEWER_DATE)
    run('list', 'projects', cwd=machine['folder'], env=machine['env'])
    assert metaform_home.meta('last_run_version') == NEWER_DATE
    assert metaform_home.meta('installed_version') is None


@pytest.mark.req('BASE-047')
def test_version_probe_works_without_reading_an_incompatible_home(home, monkeypatch, capsys):
    from metaform import cli, harness
    from metaform import home as metaform_home

    with metaform_home.chassis(write=True) as db:
        db.execute("UPDATE meta SET value='999' WHERE key IN ('schema_version', 'compatible_from')")
    before = (home / 'metaform.sqlite3').read_bytes()
    monkeypatch.setattr(harness, 'running', lambda: Path('/opt/base047-harness/codex'))
    assert cli.main(['--version']) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == f'metaform {__version__}' and captured.err == ''
    assert (home / 'metaform.sqlite3').read_bytes() == before


@pytest.mark.req('BASE-047')
@pytest.mark.parametrize(('current', 'previous'), [
    ('2026.10.1.1', '2026.9.30.9'), ('2026.9.30.10', '2026.9.30.9'),
    ('2026.9.30.9', '2026.10.1.1'), ('2026.9.30.9', '2026.9.30.10'),
])
def test_numeric_version_boundaries_control_wheel_installation(machine, home, monkeypatch, current, previous):
    from fakes import executable

    from metaform import home as metaform_home
    from metaform import install
    from metaform.errors import Stop

    for key, value in machine['env'].items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(install, '__version__', current)
    executable(machine['bin'], 'metaform', f'print("metaform {previous}")')
    newer = tuple(map(int, current.split('.'))) > tuple(map(int, previous.split('.')))
    if newer:
        install.stage(machine['wheel'], 'uv', False, lambda text: None, 'retry')
        assert calls(machine['bin'], 'uv') == [['tool', 'install', '--force', str(machine['wheel'])]]
        assert metaform_home.meta('installed_version') == current
    else:
        with pytest.raises(Stop, match='downgrade'):
            install.stage(machine['wheel'], 'uv', False, lambda text: None, 'retry')
        assert calls(machine['bin'], 'uv') == []
        assert metaform_home.meta('installed_version') is None


@pytest.mark.req('BASE-047')
def test_raw_upgrade_retires_an_old_stage_approval_before_a_raw_downgrade(home, monkeypatch):
    from metaform import home as metaform_home
    from metaform import install
    from metaform.errors import Stop

    monkeypatch.delenv('METAFORM_WHEEL', raising=False)
    metaform_home.set_meta('installed_version', OLDER_VERSION)
    metaform_home.set_meta('last_run_version', OLDER_VERSION)
    monkeypatch.setattr(install, '__version__', NEWER_DATE)
    install.backstage()
    assert metaform_home.meta('installed_version') is None
    assert metaform_home.meta('last_run_version') == NEWER_DATE
    monkeypatch.setattr(install, '__version__', OLDER_VERSION)
    with pytest.raises(Stop, match='downgrade'):
        install.backstage()
    assert metaform_home.meta('installed_version') is None
    assert metaform_home.meta('last_run_version') == NEWER_DATE


@pytest.mark.req('BASE-047', 'STORE-002')
def test_direct_wheel_and_version_probe_do_not_create_a_version_database(home, run, machine):
    run('--version', env={'METAFORM_WHEEL': ''})
    assert not (home / 'metaform.sqlite3').exists()
    run('list', 'projects', cwd=machine['folder'], env=machine['env'])
    assert not (home / 'metaform.sqlite3').exists()


@pytest.mark.req('BASE-047')
def test_concurrent_wheel_installs_cannot_replace_a_newer_install_with_an_older_one(machine, home):
    from fakes import executable

    from metaform import home as metaform_home

    state = machine['bin'] / 'installed-version'
    state.write_text(OLDER_VERSION, encoding='utf-8')
    started, release = machine['bin'] / 'old-started', machine['bin'] / 'release-old'
    ready = machine['bin'] / 'new-ready'
    executable(machine['bin'], 'metaform', f'from pathlib import Path\nprint("metaform " + Path({str(state)!r}).read_text())')
    executable(machine['bin'], 'uv', f'''
        import os, time
        from pathlib import Path
        version = os.environ['BASE047_TEST_VERSION']
        if version == {__version__!r}:
            Path({str(started)!r}).touch()
            deadline = time.monotonic() + 15
            while not Path({str(release)!r}).exists():
                if time.monotonic() > deadline:
                    raise RuntimeError('test did not release old installation')
                time.sleep(0.01)
        Path({str(state)!r}).write_text(version, encoding='utf-8')
    ''')
    script = ('import os\nfrom pathlib import Path\nfrom metaform import install\n'
              'install.__version__ = os.environ["BASE047_TEST_VERSION"]\n'
              f'if install.__version__ == {NEWER_DATE!r}: Path({str(ready)!r}).touch()\n'
              f'install.stage(Path({str(machine["wheel"])!r}), "uv", False, print, "retry")\n')
    processes = []
    try:
        for version, marker in ((__version__, started), (NEWER_DATE, ready)):
            process = subprocess.Popen([sys.executable, '-c', script], cwd=machine['folder'],
                                       env={**os.environ, **machine['env'], 'METAFORM_HOME': str(home),
                                            'BASE047_TEST_VERSION': version},
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
            processes.append(process)
            deadline = time.monotonic() + 10
            while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.01)
            assert marker.exists(), process.communicate(timeout=5)
        # Without serialization the newer install completes while the older uv is paused.
        try:
            processes[1].communicate(timeout=1)
        except subprocess.TimeoutExpired:
            pass
        release.touch()
        for process in processes:
            out, err = process.communicate(timeout=15)
            assert process.returncode == 0, out + err
        assert state.read_text(encoding='utf-8') == NEWER_DATE
        assert metaform_home.meta('installed_version') == NEWER_DATE
    finally:
        release.touch()
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)


@pytest.mark.req('BASE-047')
@pytest.mark.parametrize('command', ['uv', 'metaform'])
def test_stage_timeouts_name_a_valid_retry_and_keep_downgrade_consent(machine, home, monkeypatch, command):
    import shlex

    from fakes import executable

    from metaform import install
    binary = executable(machine['bin'], command, 'import time\ntime.sleep(30)')
    for key, value in machine['env'].items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(install, 'TOOL_TIMEOUT', 0.2)
    with pytest.raises(install.Failed) as stopped:
        install.install(['claude', 'force=true'], lambda text: None)
    assert 'did not finish' in str(stopped.value)
    if command == 'metaform':
        assert stopped.value.next_step == f'"{binary}" --version'
    else:
        assert shlex.split(stopped.value.next_step) == ['python', str(machine['wheel']), 'install',
                                                       'claude', 'force=true']
    assert calls(machine['bin'], 'claude') == []


@pytest.mark.req('BASE-047', 'MCP-013')
def test_wheel_installation_precedes_ai_setup_prerequisites(run, machine):
    from metaform import home as metaform_home
    (machine['bin'] / ('uvx.cmd' if (machine['bin'] / 'uvx.cmd').exists() else 'uvx')).unlink()
    result = run('install', 'claude', cwd=machine['folder'], env=machine['env'], ok=False)
    assert result.returncode == 2 and 'uvx' in result.stderr
    assert calls(machine['bin'], 'uv') == [['tool', 'install', '--force', str(machine['wheel'])]]
    assert metaform_home.meta('installed_version') == __version__
    assert calls(machine['bin'], 'claude') == []


@pytest.mark.req('MCP-036', 'MCP-015')
@pytest.mark.parametrize('tool,filename', [('claude', 'CLAUDE.md'), ('codex', 'AGENTS.md'), ('gemini', 'GEMINI.md')])
def test_global_pointer_preserves_authored_bytes_and_has_a_backup(run, machine, home, tool, filename):
    recorder(machine['bin'], 'gemini')
    path = machine['user'] / f'.{tool}' / filename
    path.parent.mkdir(parents=True)
    original = b'# My rules\r\nKeep my work private.'
    path.write_bytes(original)
    out = run('install', tool, cwd=machine['folder'], env=machine['env']).stdout
    pointer = ('This system orchestrates work using Metaform. You must use its active features. '
               'Read them with `metaform help agents`, or the metaform_instructions tool.')
    assert path.read_bytes().startswith(original)
    assert pointer in path.read_text()
    assert str(path) in out and pointer in out
    backups = list((home / 'backups' / 'install').rglob(filename))
    assert len(backups) == 1 and backups[0].read_bytes() == original
    once = path.read_bytes()
    run('install', tool, cwd=machine['folder'], env=machine['env'])
    assert path.read_bytes() == once
    run('uninstall', tool, cwd=machine['folder'], env=machine['env'])
    assert path.read_bytes() == original


@pytest.mark.req('MCP-036', 'MCP-028', 'MCP-020')
def test_provision_installs_an_executable_passive_claude_hook_and_preserves_other_hooks(run, machine, home):
    from metaform import prompt_files
    settings = machine['user'] / '.claude' / 'settings.json'
    settings.parent.mkdir(parents=True)
    other = {'matcher': 'Bash', 'hooks': [{'type': 'command', 'command': 'my-check'}]}
    original = {'permissions': {'deny': ['Bash(rm *)']}, 'hooks': {'PreToolUse': [other]}}
    settings.write_text(json.dumps(original))
    before = settings.read_bytes()
    out = run('provision', 'claude', cwd=machine['folder'], env=machine['env']).stdout
    assert str(settings) in out
    configured = json.loads(settings.read_text())
    assert configured['permissions'] == original['permissions']
    assert configured['hooks']['PreToolUse'][0] == other
    added = configured['hooks']['PreToolUse'][1]
    import re
    assert all(re.fullmatch(added['matcher'], tool) for tool in ('Agent', 'Task', 'AskUserQuestion'))
    assert not re.fullmatch(added['matcher'], 'Bash')
    handler = added['hooks'][0]
    result = subprocess.run([handler['command'], *handler['args']], cwd=machine['folder'],
                            input='{}', text=True, capture_output=True, check=False)
    assert result.returncode == 0 and not result.stderr
    assert json.loads(result.stdout) == {'hookSpecificOutput': {
        'hookEventName': 'PreToolUse', 'additionalContext': prompt_files.chassis('work_reminder')}}
    # Once per host session, which the host names on standard input; a call naming none gets it each time, MCP-039.
    named = json.dumps({'session_id': f'test-{os.getpid()}-{time.time_ns()}'})
    told = [subprocess.run([handler['command'], *handler['args']], cwd=machine['folder'], input=named, text=True,
                           capture_output=True, check=False).stdout for _ in range(2)]
    assert json.loads(told[0]) == json.loads(result.stdout) and told[1] == ''
    assert calls(machine['bin'], 'claude') == []
    assert not (home / 'metaform.sqlite3').exists() or not recorded_installs(home)
    backups = list((home / 'backups' / 'provision').rglob('settings.json'))
    assert len(backups) == 1 and backups[0].read_bytes() == before
    run('provision', 'claude', cwd=machine['folder'], env=machine['env'])
    assert json.loads(settings.read_text()) == configured
    run('uninstall', 'claude', cwd=machine['folder'], env=machine['env'])
    assert json.loads(settings.read_text()) == original
    assert calls(machine['bin'], 'claude') == []


def recorded_installs(home):
    import sqlite3
    with sqlite3.connect(home / 'metaform.sqlite3') as db:
        return list(db.execute('SELECT tool FROM installs'))


@pytest.mark.req('MCP-036', 'MCP-015')
@pytest.mark.parametrize('content', ['{broken', '[]', '{"hooks": []}', '{"hooks": {"PreToolUse": {}}}'])
def test_invalid_hook_settings_are_unchanged_and_no_global_pointer_is_written(run, machine, content):
    settings = machine['user'] / '.claude' / 'settings.json'
    settings.parent.mkdir(parents=True)
    settings.write_text(content)
    result = run('install', 'claude', cwd=machine['folder'], env=machine['env'], ok=False)
    assert result.returncode == 2 and str(settings) in result.stderr
    assert settings.read_text() == content
    assert not (settings.parent / 'CLAUDE.md').exists()
    assert calls(machine['bin'], 'claude') == []


@pytest.mark.req('MCP-036')
def test_codex_pointer_uses_codex_home(run, machine):
    alternate = machine['user'] / 'my-codex'
    run('provision', 'codex', cwd=machine['folder'], env={**machine['env'], 'CODEX_HOME': str(alternate)})
    assert 'This system orchestrates work using Metaform.' in (alternate / 'AGENTS.md').read_text()
    assert not (machine['user'] / '.codex').exists()


@pytest.mark.req('MCP-036')
def test_codex_skill_uses_codex_home(run, machine):
    alternate = machine['folder'] / 'ch'
    run('install', 'codex', cwd=machine['folder'], env={**machine['env'], 'CODEX_HOME': str(alternate)})
    assert (alternate / 'skills' / 'metaform' / 'SKILL.md').read_bytes() == SKILL.read_bytes()
    assert not (machine['user'] / '.codex' / 'skills').exists()


@pytest.mark.req('MCP-036', 'MCP-015', 'MCP-020')
@pytest.mark.parametrize('action', ['provision', 'uninstall'])
def test_pointer_revision_preserves_existing_rules_and_remains_owned(home, machine, monkeypatch, action):
    from metaform import install, prompt_files

    monkeypatch.setattr(install, 'user_home', lambda: machine['user'])
    folder = machine['user'] / 'configured-codex'
    monkeypatch.setenv('CODEX_HOME', str(folder))
    folder.mkdir()
    path = folder / 'AGENTS.md'
    original = b'# Existing rules\r\nKeep these bytes.'
    path.write_bytes(original)
    install.provision('codex', lambda line: None)
    installed = path.read_bytes()
    chassis = prompt_files.chassis
    revised = chassis('global_instructions') + ' Revised test guidance.'
    monkeypatch.setattr(prompt_files, 'chassis', lambda name, **fills:
                        revised if name == 'global_instructions' else chassis(name, **fills))

    if action == 'provision':
        install.provision('codex', lambda line: None)
        assert path.read_bytes().startswith(original)
        assert path.read_text().count(revised) == 1
        assert any(backup.read_bytes() == installed for backup in (home / 'backups').rglob('AGENTS.md'))
    install.uninstall(['codex'], lambda line: None)
    assert path.read_bytes() == original


@pytest.mark.req('MCP-036', 'MCP-015', 'MCP-020')
def test_user_edits_inside_owned_pointer_survive_setup_and_uninstall(home, machine, monkeypatch):
    from metaform import install
    from metaform.errors import Stop

    monkeypatch.setattr(install, 'user_home', lambda: machine['user'])
    folder = machine['user'] / 'configured-codex'
    monkeypatch.setenv('CODEX_HOME', str(folder))
    install.provision('codex', lambda line: None)
    path = folder / 'AGENTS.md'
    edited = path.read_bytes().replace(b'You must use its active features.', b'My own instruction.')
    path.write_bytes(edited)
    for action in (lambda: install.provision('codex', lambda line: None),
                   lambda: install.uninstall(['codex'], lambda line: None)):
        with pytest.raises(Stop, match='edited Metaform instruction block'):
            action()
        assert path.read_bytes() == edited


@pytest.mark.req('MCP-036', 'QUAL-002')
def test_a_pointer_whose_line_endings_an_editor_changed_stays_owned(home, machine, monkeypatch):
    from metaform import install

    monkeypatch.setattr(install, 'user_home', lambda: machine['user'])
    folder = machine['user'] / 'configured-codex'
    monkeypatch.setenv('CODEX_HOME', str(folder))
    folder.mkdir()
    path = folder / 'AGENTS.md'
    original = b'# Existing rules\r\nKeep these bytes.'
    path.write_bytes(original)
    install.provision('codex', lambda line: None)
    path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
    install.uninstall(['codex'], lambda line: None)
    assert path.read_bytes() == original


@pytest.mark.req('MCP-015', 'MCP-036')
def test_provision_preview_runs_before_either_global_file_changes(home, machine, monkeypatch):
    from metaform import install
    monkeypatch.setattr(install, 'user_home', lambda: machine['user'])
    monkeypatch.setattr(install.harness, 'done', lambda binary: pytest.fail('Provisioning marked the harness done'))
    instructions = machine['user'] / '.claude' / 'CLAUDE.md'
    settings = instructions.with_name('settings.json')
    instructions.parent.mkdir()
    instructions.write_bytes(b'Existing instructions')
    settings.write_bytes(b'{"model": "chosen"}')
    before = {path: path.read_bytes() for path in (instructions, settings)}
    previews = []

    def say(line):
        if any(str(path) in line for path in before):
            assert all(path.read_bytes() == content for path, content in before.items())
            previews.append(line)

    install.provision('claude', say)
    assert len(previews) == 2
    assert all(path.read_bytes() != content for path, content in before.items())


@pytest.mark.req('MCP-036', 'MCP-028', 'MCP-020')
def test_gemini_passive_reminder_preserves_settings_and_can_be_turned_off(run, machine, home):
    import re

    from metaform import prompt_files
    settings = machine['user'] / '.gemini' / 'settings.json'
    settings.parent.mkdir()
    other = {'matcher': 'read_file', 'hooks': [{'type': 'command', 'command': 'my-check'}]}
    original = {'mcpServers': {'other': {'command': 'other'}}, 'hooks': {'AfterTool': [other]}}
    settings.write_text(json.dumps(original))
    before = settings.read_bytes()
    out = run('provision', 'gemini', cwd=machine['folder'], env=machine['env']).stdout
    assert 'AfterTool' in out and 'after' in out
    configured = json.loads(settings.read_text())
    assert configured['mcpServers'] == original['mcpServers']
    assert configured['hooks']['AfterTool'][0] == other
    added = configured['hooks']['AfterTool'][1]
    assert all(re.fullmatch(added['matcher'], tool) for tool in ('invoke_agent', 'delegate_to_agent', 'ask_user'))
    assert not re.fullmatch(added['matcher'], 'read_file')
    handler = added['hooks'][0]
    shell = ['powershell', '-NoProfile', '-NonInteractive', '-Command'] if os.name == 'nt' else ['bash', '-c']
    result = subprocess.run([*shell, handler['command']], cwd=machine['folder'],
                            input='{}', text=True, capture_output=True, check=False)
    assert result.returncode == 0 and not result.stderr
    assert json.loads(result.stdout) == {'hookSpecificOutput': {
        'hookEventName': 'AfterTool', 'additionalContext': prompt_files.chassis('work_reminder')}}
    backups = list((home / 'backups' / 'provision').rglob('settings.json'))
    assert len(backups) == 1 and backups[0].read_bytes() == before
    run('provision', 'gemini', cwd=machine['folder'], env=machine['env'])
    assert json.loads(settings.read_text()) == configured
    run('set', '--gemini-reminder', 'off', cwd=machine['folder'], env=machine['env'])
    run('provision', 'gemini', cwd=machine['folder'], env=machine['env'])
    assert json.loads(settings.read_text()) == original
    assert (settings.parent / 'GEMINI.md').exists()
    run('uninstall', 'gemini', cwd=machine['folder'], env=machine['env'])
    assert json.loads(settings.read_text()) == original


@pytest.mark.req('MCP-036', 'MCP-015')
def test_gemini_registration_preserves_the_previewed_hook_edits(run, machine):
    from fakes import RECORDER, executable
    body = RECORDER + '''
config = pathlib.Path.home() / '.gemini' / 'settings.json'
config.parent.mkdir(exist_ok=True)
data = json.loads(config.read_text()) if config.exists() else {}
servers = data.setdefault('mcpServers', {})
if args[:2] == ['mcp', 'add']:
    servers['metaform'] = {'command': 'registered-by-gemini'}
elif args[:2] == ['mcp', 'remove']:
    servers.pop('metaform', None)
config.write_text(json.dumps(data))
'''
    executable(machine['bin'], 'gemini', body)
    settings = machine['user'] / '.gemini' / 'settings.json'
    settings.parent.mkdir()
    other = {'matcher': 'read_file', 'hooks': [{'type': 'command', 'command': 'my-check'}]}
    original = {'mcpServers': {'other': {'command': 'other'}}, 'hooks': {'AfterTool': [other]}}
    settings.write_text(json.dumps(original))
    for _ in range(2):
        run('install', 'gemini', cwd=machine['folder'], env=machine['env'])
        data = json.loads((machine['user'] / '.gemini' / 'settings.json').read_text())
        assert data['mcpServers']['metaform'] == {'command': 'registered-by-gemini'}
        assert data['mcpServers']['other'] == original['mcpServers']['other']
        assert len(data['hooks']['AfterTool']) == 2
    run('uninstall', 'gemini', cwd=machine['folder'], env=machine['env'])
    assert json.loads(settings.read_text()) == original


@pytest.mark.req('MCP-036', 'MCP-015')
@pytest.mark.parametrize('content', ['{broken', '{"hooks": {"AfterTool": {}}}'])
def test_invalid_gemini_hooks_leave_global_instructions_unchanged(run, machine, content):
    settings = machine['user'] / '.gemini' / 'settings.json'
    settings.parent.mkdir()
    settings.write_text(content)
    result = run('provision', 'gemini', cwd=machine['folder'], env=machine['env'], ok=False)
    assert result.returncode == 2 and str(settings) in result.stderr
    assert settings.read_text() == content
    assert not (settings.parent / 'GEMINI.md').exists()


ACP_AGENT = '''
import json, sys, pathlib
# An ACP agent that answers initialize, as metaform dispatch serve does; each start's arguments are kept.
with pathlib.Path(__file__).with_suffix('.log').open('a', encoding='utf-8') as out:
    out.write(json.dumps(sys.argv[1:]) + '\\n')
for line in sys.stdin:
    message = json.loads(line)
    if message.get('method') == 'initialize':
        print(json.dumps({'jsonrpc': '2.0', 'id': message['id'], 'result': {'protocolVersion': 1,
                          'agentCapabilities': {}, 'authMethods': []}}), flush=True)
'''


@pytest.mark.req('BASE-062')
@pytest.mark.req('MCP-020')
def test_install_registers_metaform_as_the_acp_agent_of_editors_and_uninstall_removes_only_it(run, machine):
    from fakes import executable
    executable(machine['bin'], 'uvx', ACP_AGENT)
    user = machine['user']
    env = {**machine['env'], 'XDG_CONFIG_HOME': str(user / '.config'), 'APPDATA': str(user / 'AppData' / 'Roaming')}
    zed = (user / 'AppData' / 'Roaming' / 'Zed' if os.name == 'nt' else user / '.config' / 'zed') / 'settings.json'
    jetbrains = user / '.jetbrains' / 'acp.json'
    jetbrains.parent.mkdir()
    jetbrains.write_text(json.dumps({'default_mcp_settings': {'use_custom_mcp': True},
                                     'agent_servers': {'Other': {'command': 'other'}}}), encoding='utf-8')
    editors = ['jetbrains', 'zed']
    zed.parent.mkdir(parents=True)
    zed.write_text(ZED_SETTINGS, encoding='utf-8')  # as Zed writes it first: comments and trailing commas
    refused = run('install', *editors, cwd=machine['folder'], env=env, ok=False)
    assert refused.returncode == 2 and 'metaform enable dispatch' in refused.stderr, 'dispatch serves editors'
    run('enable', 'dispatch')
    out = run('install', *editors, cwd=machine['folder'], env=env).stdout
    command = ['uvx', '--from', str(machine['wheel']), 'metaform', 'dispatch', 'serve']
    registered = json.loads(jetbrains.read_text())
    assert registered['agent_servers']['metaform'] == {'command': 'uvx', 'args': command[1:], 'env': {}}
    assert registered['agent_servers']['Other'] == {'command': 'other'} and registered['default_mcp_settings']
    merged = zed.read_text(encoding='utf-8')
    assert merged.startswith(ZED_SETTINGS.split('{')[0]) and '"mode": "system",' in merged, 'its comments stay'
    assert jsonc(merged) == {**jsonc(ZED_SETTINGS), 'agent_servers': {
        'metaform': {'type': 'custom', 'command': 'uvx', 'args': command[1:], 'env': {}}}}
    assert all(f'{name}: the ACP agent answers initialize' in out for name in editors)
    assert 'behind it: ' in out, 'the agent an editor reaches is named'
    assert calls(machine['bin'], 'uvx')[-1] == [*command[1:], 'agent=none'], 'the proof starts no model'
    run('uninstall', *editors, cwd=machine['folder'], env=env)
    assert 'metaform' not in json.loads(jetbrains.read_text())['agent_servers']
    left = zed.read_text(encoding='utf-8')
    assert left == ZED_SETTINGS, 'Zed settings come back as they were, the agent_servers Metaform made gone with it'


# Zed's settings.json as Zed first writes it, assets/settings/initial_user_settings.json
ZED_SETTINGS = """// Zed settings
//
// For information on how to configure Zed, see the Zed
// documentation: https://zed.dev/docs/configuring-zed
//
// To see all of Zed's default settings without changing your
// custom settings, run `zed: open default settings` from the
// command palette (cmd-shift-p / ctrl-shift-p)
{
  "ui_font_size": 16,
  "buffer_font_size": 15,
  "theme": {
    "mode": "system",
    "light": "One Light",
    "dark": "One Dark",
  },
}
"""


def jsonc(text):
    """JSON with whole-line comments and trailing commas, as these tests write it, read as JSON."""
    import re
    kept = '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('//'))
    return json.loads(re.sub(r',(\s*[}\]])', r'\1', kept))


@pytest.mark.req('BASE-062')
def test_install_finds_a_jetbrains_ide_by_its_config_folder_and_an_unreadable_config_spares_the_other_tools(
        run, machine):
    from fakes import executable
    executable(machine['bin'], 'uvx', ACP_AGENT)
    user = machine['user']
    env = {**machine['env'], 'XDG_CONFIG_HOME': str(user / '.config'), 'APPDATA': str(user / 'AppData' / 'Roaming')}
    ide = {'nt': user / 'AppData' / 'Roaming'}.get(os.name) or (
        user / 'Library' / 'Application Support' if sys.platform == 'darwin' else user / '.config')
    (ide / 'JetBrains').mkdir(parents=True)  # an IDE that has never had an ACP agent: no ~/.jetbrains yet
    zed = (user / 'AppData' / 'Roaming' / 'Zed' if os.name == 'nt' else user / '.config' / 'zed') / 'settings.json'
    zed.parent.mkdir(parents=True, exist_ok=True)
    zed.write_text('{"theme": ', encoding='utf-8')
    run('enable', 'dispatch')
    done = run('install', 'zed', 'jetbrains', cwd=machine['folder'], env=env, ok=False)
    assert done.returncode == 1 and 'zed: not registered' in done.stdout
    assert 'jetbrains: the ACP agent answers initialize' in done.stdout, 'the other editor is still set up and proven'
    made = json.loads((user / '.jetbrains' / 'acp.json').read_text(encoding='utf-8'))
    assert made == {'agent_servers': {'metaform': {'command': 'uvx', 'args': [
        '--from', str(machine['wheel']), 'metaform', 'dispatch', 'serve'], 'env': {}}}}
    assert zed.read_text(encoding='utf-8') == '{"theme": ', 'left as it was'


@pytest.mark.req('BASE-062')
def test_an_unreadable_mcp_config_spares_the_editors_and_zeds_comments_come_back_as_they_were(run, machine):
    from fakes import executable

    from metaform.install import _jsonc_drop, _jsonc_put
    executable(machine['bin'], 'uvx', ACP_AGENT)
    user = machine['user']
    env = {**machine['env'], 'XDG_CONFIG_HOME': str(user / '.config'), 'APPDATA': str(user / 'AppData' / 'Roaming')}
    (user / '.cursor').mkdir(exist_ok=True)
    (user / '.cursor' / 'mcp.json').write_text('{"mcpServers": ', encoding='utf-8')
    zed = (user / 'AppData' / 'Roaming' / 'Zed' if os.name == 'nt' else user / '.config' / 'zed') / 'settings.json'
    zed.parent.mkdir(parents=True, exist_ok=True)
    zed.write_text('{\n  "theme": "One" // my theme\n}\n', encoding='utf-8')
    run('enable', 'dispatch')
    done = run('install', 'cursor', 'zed', cwd=machine['folder'], env=env, ok=False)
    assert done.returncode == 1 and 'cursor: not registered' in done.stdout and 'cursor' in done.stderr
    assert 'zed: the ACP agent answers initialize' in done.stdout, 'the editor after it is still set up and proven'
    written = zed.read_text(encoding='utf-8')
    assert '"theme": "One", // my theme\n' in written and '"metaform"' in written, 'the comment stays on its line'
    # put, then drop, gives back the text as it was, comments and trailing commas included
    for text in ('{\n  "theme": "One" // my theme\n}\n',
                 '{\n  "agent_servers": {\n    "claude": {"command": "x"}, // keep me\n  },\n}\n'):
        put = _jsonc_put(text, 'agent_servers', 'metaform', {'command': 'metaform'})
        assert put is not None and _jsonc_drop(put, 'agent_servers', 'metaform') == text


NODE_SKILL = ROOT / 'src' / 'metaform' / 'skill' / 'metaform-node' / 'SKILL.md'


def node_copies(user: Path) -> list[str]:
    return sorted(str(path.relative_to(user)) for path in user.rglob('SKILL.md') if 'metaform-node' in path.parts)


def test_the_node_skill_goes_to_claude_code_alone_and_leaves_with_its_uninstall(run, machine, home):
    run('install', 'claude', 'codex', 'cursor', cwd=machine['folder'], env=machine['env'])
    assert node_copies(machine['user']) == [str(Path('.claude/skills/metaform-node/SKILL.md'))]
    assert not (home / 'skills' / 'metaform-node').exists()
    copy = machine['user'] / '.claude' / 'skills' / 'metaform-node' / 'SKILL.md'
    assert copy.read_bytes() == NODE_SKILL.read_bytes()
    run('uninstall', 'codex', 'cursor', cwd=machine['folder'], env=machine['env'])
    assert copy.is_file()
    out = run('uninstall', 'claude', cwd=machine['folder'], env=machine['env']).stdout
    assert f'skill: remove {copy}' in out and node_copies(machine['user']) == []
    assert not copy.parent.exists() and list((home / 'backups' / 'uninstall').rglob('metaform-node/SKILL.md'))


def test_the_node_skill_exists_only_while_map_is_on(run, machine):
    copy = machine['user'] / '.claude' / 'skills' / 'metaform-node' / 'SKILL.md'
    run('enable', 'map', cwd=machine['folder'], env=machine['env'])
    assert not copy.exists()  # Claude Code was never set up, so nothing is written for it
    run('disable', 'map', cwd=machine['folder'], env=machine['env'])
    out = run('install', 'claude', cwd=machine['folder'], env=machine['env']).stdout
    assert not copy.exists() and 'metaform-node' not in out
    assert 'Skill: wrote' in run('enable', 'map', cwd=machine['folder'], env=machine['env']).stdout
    assert copy.read_bytes() == NODE_SKILL.read_bytes()
    assert 'Skill: removed' in run('disable', 'map', cwd=machine['folder'], env=machine['env']).stdout
    assert not copy.parent.exists()
    run('enable', 'map', cwd=machine['folder'], env=machine['env'])
    run('set', '--modules', 'chassis', cwd=machine['folder'], env=machine['env'])
    out = run('install', 'claude', cwd=machine['folder'], env=machine['env']).stdout
    assert f'skill: remove {copy}' in out and not copy.exists()  # map is off this folder's surface


def test_provision_claude_writes_or_removes_the_node_skill_with_map(run, machine):
    copy = machine['user'] / '.claude' / 'skills' / 'metaform-node' / 'SKILL.md'
    run('provision', 'claude', cwd=machine['folder'], env=machine['env'])
    assert copy.read_bytes() == NODE_SKILL.read_bytes()
    run('disable', 'map', cwd=machine['folder'], env=machine['env'])
    assert not copy.exists()
    run('enable', 'map', cwd=machine['folder'], env=machine['env'])
    assert copy.is_file()  # provision set Claude Code up, so map's return brings the skill back
    run('provision', 'codex', cwd=machine['folder'], env=machine['env'])
    assert node_copies(machine['user']) == [str(Path('.claude/skills/metaform-node/SKILL.md'))]


@pytest.mark.req('BASE-042')
def test_a_wheel_that_leaves_modules_out_hands_the_setup_to_the_metaform_it_installed(run, machine, monkeypatch):
    """Run straight from a wheel, modules whose compiled dependencies it cannot carry are left out, mcp among them, so
    it would register no server; once installed, the installed Metaform sets the tools up with the same wheel."""
    from fakes import executable

    from metaform import loader
    installed = machine['folder'] / 'tools-bin'
    executable(machine['bin'], 'uv', f'import sys\nprint({str(installed)!r}) if sys.argv[1:3] == ["tool", "dir"] else None\n')
    executable(installed, 'metaform', 'import json, os, sys\n'
               'print("metaform 0.0.1") if sys.argv[1:] == ["--version"] else open(os.path.join(os.path.dirname('
               '__file__), "handed.json"), "w").write(json.dumps([sys.argv[1:], os.environ.get("METAFORM_WHEEL"), '
               'os.environ.get("METAFORM_INSTALL_WHEEL")]))\n')
    monkeypatch.setattr(loader, 'withdrawn', lambda: frozenset({'mcp'}))
    run('install', 'claude', 'force=true', cwd=machine['folder'], env=machine['env'])
    assert json.loads((installed / 'handed.json').read_text(encoding='utf-8')) == [
        ['install', 'claude'], None, str(machine['wheel'])]
    assert calls(machine['bin'], 'claude') == []  # the wheel's own run registered nothing
