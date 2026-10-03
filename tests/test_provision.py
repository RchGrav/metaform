"""First-run provisioning under an unfamiliar harness, MCP-028 and D96: a notice on stderr, metaform help provision,
metaform provision done, and metaform install recording the harnesses it sets up."""
from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest
from fakes import executable, recorder, server

pytestmark = [pytest.mark.req('MCP-028')]

# Outside the system's temporary folder, where every tmp_path is; nothing is created here.
ROOT = Path(os.path.abspath(os.sep))
HARNESS = ROOT / 'opt' / 'harness' / 'versions' / '2.0.1'
OTHER = ROOT / 'opt' / 'other' / 'bin' / 'other'
NOTICE = ("This is Metaform's first run here. Read metaform help provision for each feature, MCP registration, "
          'skill and hooks, then run metaform provision done.')


@pytest.fixture
def under(monkeypatch, home):
    """Run Metaform in this process as if under the harness whose binary is given."""
    from metaform import harness

    def at(binary: Path | None) -> None:
        monkeypatch.setattr(harness, 'running', lambda: binary)
    return at


def command(capsys, *args: str) -> tuple[int, str, str]:
    from metaform import cli
    code = cli.main(list(args))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


@pytest.mark.kind('fixture')
@pytest.mark.parametrize('args', [('help',), ('--version',), ('help', 'commands'), ('list', 'projects'),
                                  ('no-such-module',)])
def test_any_command_under_an_unrecorded_harness_gives_the_notice_once_on_stderr(under, capsys, args):
    under(HARNESS)
    _, out, err = command(capsys, *args)
    assert err.count(NOTICE) == 1
    assert NOTICE not in out


@pytest.mark.kind('fixture')
def test_the_notice_changes_nothing_the_command_prints_or_returns(under, capsys):
    under(None)
    quiet = command(capsys, 'help', 'commands')
    under(HARNESS)
    code, out, err = command(capsys, 'help', 'commands')
    assert (code, out) == quiet[:2]
    assert err.replace(f'Notice: {NOTICE}\n', '') == quiet[2]


@pytest.mark.kind('fixture')
@pytest.mark.req('CLI-009')
@pytest.mark.parametrize('args', [('help',), ('--version',), ('provision', 'done')])
def test_a_notice_record_read_error_uses_the_cli_error_handler(under, capsys, home, args):
    from metaform import home as metaform_home
    with metaform_home.base(write=True) as db:
        db.execute("UPDATE meta SET value='999' WHERE key='schema_version'")
    under(HARNESS)
    code, out, err = command(capsys, *args)
    assert code == 2 and not out
    error, next_step = err.splitlines()
    assert error.startswith('Error: ') and 'schema version 999' in error
    assert str(home / 'metaform.sqlite3') in error
    assert next_step == 'Next: install the Metaform release that wrote it'


@pytest.mark.kind('fixture')
def test_a_recorded_harness_sees_no_notice(under, capsys):
    from metaform import harness
    harness.done(HARNESS.with_name('1.9.0'))
    under(HARNESS)
    assert NOTICE not in command(capsys, 'help')[2]
    under(OTHER)
    assert NOTICE in command(capsys, 'help')[2]


@pytest.mark.kind('fixture')
def test_no_notice_when_no_harness_is_found_or_it_runs_from_the_temporary_folder(under, capsys):
    under(None)
    assert NOTICE not in command(capsys, 'help')[2]
    under(Path(tempfile.gettempdir()) / 'agent' / 'bin' / 'agent')
    assert NOTICE not in command(capsys, 'help')[2]


@pytest.mark.kind('fixture')
def test_provision_done_records_the_running_harness_and_the_notice_stops(under, capsys, home):
    from metaform import harness
    under(HARNESS)
    code, out, _ = command(capsys, 'provision', 'done')
    assert code == 0 and out.strip()
    assert harness.known(HARNESS)
    assert NOTICE not in command(capsys, 'help')[2]
    under(OTHER)
    assert NOTICE in command(capsys, 'help')[2]


@pytest.mark.kind('fixture')
def test_provision_done_twice_does_no_harm(under, capsys):
    from metaform import harness
    under(HARNESS)
    assert command(capsys, 'provision', 'done')[0] == 0
    assert command(capsys, 'provision', 'done')[0] == 0
    assert harness.known(HARNESS)


@pytest.mark.kind('fixture')
@pytest.mark.parametrize('binary', [None, Path(tempfile.gettempdir()) / 'agent' / 'agent'])
def test_provision_done_with_no_harness_to_record_says_so_and_records_nothing(under, capsys, home, binary):
    under(binary)
    code, _, err = command(capsys, 'provision', 'done')
    assert code == 2
    lines = err.splitlines()
    assert [line for line in lines if line.startswith('Error: ')] and lines[-1].startswith('Next: ')
    database = home / 'metaform.sqlite3'
    if database.exists():
        with sqlite3.connect(database) as db:
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            assert 'harnesses' not in tables or not db.execute('SELECT 1 FROM harnesses').fetchone()


@pytest.mark.kind('fixture')
def test_provision_takes_only_done(under, capsys, home):
    from metaform import harness
    under(HARNESS)
    for args in (('provision',), ('provision', 'now'), ('provision', 'done', 'extra')):
        code, _, err = command(capsys, *args)
        assert code == 2 and err.splitlines()[-1].startswith('Next: ')
    assert not harness.known(HARNESS)


@pytest.mark.kind('fixture')
def test_help_provision_says_what_to_do_for_each_feature_and_how_to_finish(under, capsys):
    under(None)
    code, page, _ = command(capsys, 'help', 'provision')
    assert code == 0
    lowered = page.lower()
    for feature in ('mcp registration', 'skill', 'hooks'):
        assert feature in lowered, feature
    assert 'stdio MCP server named metaform' in page and 'metaform mcp serve' in page
    assert "global skills folder as metaform/SKILL.md" in page
    assert 'a real copy and never a link' in page and 'never into a project folder' in page
    skill = Path(__file__).parents[1] / 'src' / 'metaform' / 'skill' / 'SKILL.md'
    named = [word.strip('.,') for word in page.split() if word.strip('.,').endswith('SKILL.md')]
    assert named and all(Path(word).read_bytes() == skill.read_bytes() for word in named if Path(word).is_absolute())
    assert any(Path(word).is_absolute() for word in named)
    assert 'metaform provision done' in page


@pytest.mark.kind('simulation')
@pytest.mark.req('BASE-042')
def test_direct_wheel_provision_help_names_an_extractable_skill(tmp_path, home):
    from metaform import build
    package = Path(__file__).parents[1] / 'src' / 'metaform'
    wheel = tmp_path / 'metaform proof.whl'
    with zipfile.ZipFile(wheel, 'w') as archive:
        archive.writestr('__main__.py', build.BOOTSTRAP)
        for path in package.rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:
                archive.write(path, 'metaform/' + path.relative_to(package).as_posix())
    result = subprocess.run([sys.executable, str(wheel), 'help', 'provision'], cwd=tmp_path,
                            env={**os.environ, 'METAFORM_HOME': str(home)}, capture_output=True,
                            text=True, encoding='utf-8', check=True)
    source = re.search(r'Skill: extract (\S+) from (.+?) into the tool', result.stdout)
    assert source is not None, result.stdout
    with zipfile.ZipFile(source[2]) as archive:
        assert archive.read(source[1]) == (package / 'skill' / 'SKILL.md').read_bytes()
    assert 'global skills folder as metaform/SKILL.md' in result.stdout
    assert 'a real copy and never a link' in result.stdout
    assert 'never into a project folder' in result.stdout


@pytest.mark.kind('fixture')
def test_the_notice_and_its_commands_run_whatever_the_folder_surface(under, capsys, tmp_path, monkeypatch):
    from metaform import harness
    under(HARNESS)
    assert command(capsys, 'set', '--modules', 'map', f'folder={tmp_path}')[0] == 0
    monkeypatch.chdir(tmp_path)
    code, _, err = command(capsys, 'list', 'projects')
    assert code == 2 and err.count(NOTICE) == 1
    assert command(capsys, 'help', 'provision')[0] == 0
    assert command(capsys, 'provision', 'done')[0] == 0
    assert harness.known(HARNESS)


# metaform install records the harnesses it sets up, so those never see the notice -------------------------------

@pytest.fixture
def machine(tmp_path, monkeypatch):
    """A user home and a PATH of fake tools, with the temporary folder moved off tmp_path so the tools' folder
    counts as a harness, here and in the installer's process."""
    temporary = tmp_path / 'temporary'
    temporary.mkdir()
    monkeypatch.setattr(tempfile, 'tempdir', str(temporary))
    user = tmp_path / 'user'
    user.mkdir()
    tools, claude = tmp_path / 'tools', tmp_path / 'claude'
    recorder(tools, 'uv')
    server(tools, 'uvx')
    recorder(claude, 'claude')
    (user / '.cursor').mkdir()
    (user / '.cursor' / 'mcp.json').write_text(json.dumps({'mcpServers': {}}), encoding='utf-8')
    wheel = tmp_path / 'metaform-0.2.0-py3-none-any.whl'
    wheel.write_bytes(b'not really a wheel')
    env = {'HOME': str(user), 'USERPROFILE': str(user), 'PATH': os.pathsep.join((str(tools), str(claude))),
           'METAFORM_WHEEL': str(wheel), 'TMPDIR': str(temporary), 'TEMP': str(temporary), 'TMP': str(temporary)}
    return {'tools': tools, 'claude': claude, 'env': env, 'folder': tmp_path}


def recorded(home: Path) -> list[str]:
    if not (home / 'metaform.sqlite3').exists():  # recording a harness makes the home
        return []
    with sqlite3.connect(home / 'metaform.sqlite3') as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='harnesses'").fetchone():
            return []
        return [str(row[0]) for row in db.execute('SELECT path_key FROM harnesses')]


@pytest.mark.kind('simulation')
def test_install_records_the_harness_of_each_tool_it_registers(run, machine, home):
    from metaform import harness
    run('install', 'claude', cwd=machine['folder'], env=machine['env'])
    folder = machine['claude']
    claude = folder / ('claude.cmd' if (folder / 'claude.cmd').exists() else 'claude')
    assert harness.known(claude)
    assert recorded(home) == [harness.key(claude)]


@pytest.mark.kind('simulation')
def test_install_records_no_harness_for_a_tool_whose_registration_failed(run, machine, home):
    executable(machine['claude'], 'claude', 'import sys; sys.exit(1)')
    assert run('install', 'claude', cwd=machine['folder'], env=machine['env'], ok=False).returncode != 0
    assert recorded(home) == []
