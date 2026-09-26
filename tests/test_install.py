"""`metaform install`: checks, registration, backups, the skill and the proof, MCP-010 to MCP-021 and MCP-023."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from fakes import calls, recorder, server

pytestmark = pytest.mark.kind('simulation')

ROOT = Path(__file__).parents[1]
SKILL = (ROOT / 'src' / 'metaform' / 'skill' / 'SKILL.md')
CURSOR_BEFORE = {'mcpServers': {'other': {'command': 'other-server', 'args': []}}}


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
def test_install_claude_touches_only_claude_and_the_skill(run, machine, home):
    before = tree(machine['user'])
    out = run('install', 'claude', cwd=machine['folder'], env=machine['env']).stdout
    assert calls(machine['bin'], 'claude')[-1] == ['mcp', 'add', '--transport', 'stdio', '--scope', 'user',
                                                   'metaform', '--', *entry(machine['wheel'])]
    assert calls(machine['bin'], 'codex') == []
    changed = {name for name, data in tree(machine['user']).items() if before.get(name) != data}
    assert changed == {str(Path('.claude/skills/metaform/SKILL.md')), str(Path('.agents/skills/metaform/SKILL.md'))}
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
    from metaform.probe import probe
    launcher = server(tmp_path / 'bin', 'fake-server')
    passed = probe([str(launcher)], cwd=tmp_path)
    assert passed.ok and passed.tools == 2
    failed = probe([str(tmp_path / 'missing-server')], cwd=tmp_path)
    assert not failed.ok and failed.reason


@pytest.mark.req('MCP-021')
def test_enabling_a_module_changes_no_skill_file(run, machine, home):
    run('install', 'claude', cwd=machine['folder'], env=machine['env'])
    before = tree(machine['user'])
    run('enable', 'helloworld', cwd=machine['folder'], env=machine['env'])
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
