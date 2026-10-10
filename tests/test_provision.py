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
# --version is the installer's probe and reads no home, so it gives no notice, BASE-047
@pytest.mark.parametrize('args', [('help',), ('help', 'commands'), ('list', 'projects'), ('no-such-module',)])
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
@pytest.mark.parametrize('args', [('help',), ('provision', 'done')])  # --version reads no home, BASE-047
def test_a_notice_record_read_error_uses_the_cli_error_handler(under, capsys, home, args):
    from metaform import home as metaform_home
    with metaform_home.chassis(write=True) as db:
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
@pytest.mark.parametrize('ready', [True, False])
def test_never_says_first_run_when_an_intake_exists(under, capsys, store, tmp_path, monkeypatch, ready):
    from storekit import intake
    under(HARNESS)
    assert NOTICE in command(capsys, 'help')[2]
    intake(store, ready=ready)
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)  # an intake in any project of the home, not only the folder's own
    err = command(capsys, 'help')[2]
    assert 'first run' not in err.lower()
    assert err.count('Read metaform help provision for each feature') == 1


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
def test_provision_through_timeout_records_only_the_actual_harness(monkeypatch, capsys, home):
    from metaform import harness
    wrapper = ROOT / 'usr' / 'bin' / 'timeout'
    processes = {20: (21, wrapper), 21: (0, HARNESS)}
    monkeypatch.setattr(os, 'getppid', lambda: 20)
    monkeypatch.setattr(harness, '_process', lambda pid: processes.get(pid))

    code, _, err = command(capsys, 'provision', 'done')
    assert code == 0 and NOTICE in err
    assert harness.known(HARNESS)
    assert recorded(home) == [harness.key(HARNESS)]
    assert NOTICE not in command(capsys, 'help')[2]

    processes[21] = (0, OTHER)
    assert NOTICE in command(capsys, 'help')[2]
    assert not harness.known(OTHER)


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
        archive.writestr('__main__.py', build.bootstrap())
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


def earlier_installs(home: Path, *, recorded: bool) -> list[str]:
    """A schema-2 home, including an optional harness recorded before the upgrade."""
    from metaform import harness
    from metaform import home as metaform_home
    home.mkdir()
    with sqlite3.connect(home / 'metaform.sqlite3') as db:
        db.executescript(metaform_home.CHASSIS_SCHEMA)
        db.execute("INSERT INTO meta VALUES ('schema_version', '2')")
        db.execute("INSERT INTO meta VALUES ('last_run_version', '2026.9.30.2')")
        db.execute("INSERT INTO module_state VALUES ('hello', 1)")
        db.execute("INSERT INTO settings VALUES ('global', '', 'debug', 0, 'true')")
        db.executemany('INSERT INTO installs VALUES (?, ?, ?, ?)',
                       [(tool, 'original.whl', 'original/SKILL.md', '2026-10-02T12:00:00Z')
                        for tool in ('claude', 'codex', 'gemini', 'vscode', 'cursor', 'retired')])
        if recorded:
            db.execute(harness.HARNESSES)
            db.execute('INSERT INTO harnesses VALUES (?, ?, ?)',
                       (harness.key(OTHER), str(OTHER.with_name('earlier')), '2026-10-03T12:00:00Z'))
        return list(db.iterdump())


@pytest.mark.kind('fixture')
@pytest.mark.req('STORE-029')
@pytest.mark.parametrize('recorded_before', [False, True])
@pytest.mark.parametrize('write', [False, True])
def test_earlier_installs_are_known_after_the_home_upgrade(home, monkeypatch, recorded_before, write):
    from metaform import harness, install
    from metaform import home as metaform_home
    earlier_installs(home, recorded=recorded_before)
    temporary = Path(tempfile.gettempdir()) / 'gemini' / 'gemini'
    binaries = {'claude': str(HARNESS), 'codex': str(OTHER), 'gemini': str(temporary), 'code': None}
    looked_up = []

    def which(command):
        looked_up.append(command)
        return binaries[command]

    monkeypatch.setattr(install.shutil, 'which', which)
    with metaform_home.chassis(write=write) as db:
        assert db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone() == ('3',)
        assert db.execute("SELECT value FROM meta WHERE key='last_run_version'").fetchone() == ('2026.9.30.2',)
        assert db.execute('SELECT * FROM module_state').fetchall() == [('hello', 1)]
        assert db.execute('SELECT * FROM settings').fetchall() == [('global', '', 'debug', 0, 'true')]
        assert db.execute('SELECT COUNT(*) FROM installs').fetchone() == (6,)
        rows = {key: (binary, done) for key, binary, done in db.execute('SELECT * FROM harnesses')}
    assert sorted(looked_up) == ['claude', 'code', 'codex', 'gemini']
    assert rows == {
        harness.key(HARNESS): (str(HARNESS), '2026-10-02T12:00:00Z'),
        harness.key(OTHER): ((str(OTHER.with_name('earlier')), '2026-10-03T12:00:00Z')
                             if recorded_before else (str(OTHER), '2026-10-02T12:00:00Z')),
    }
    monkeypatch.setattr(harness, 'running', lambda: HARNESS)
    assert harness.known(HARNESS) and harness.notice() is None
    assert harness.known(OTHER)
    assert not harness.known(temporary)
    assert not harness.known(ROOT / 'opt' / 'unrecorded' / 'agent')

    def no_more_lookups(command):
        pytest.fail(f'upgrade repeated the binary lookup for {command}')

    monkeypatch.setattr(install.shutil, 'which', no_more_lookups)
    with metaform_home.chassis() as db:
        assert db.execute('SELECT COUNT(*) FROM harnesses').fetchone() == (2,)
    assert harness.notice() is None


@pytest.mark.kind('fixture')
@pytest.mark.req('STORE-029')
def test_failed_home_upgrade_preserves_schema_and_records_for_retry(home, monkeypatch):
    from metaform import harness, install
    from metaform import home as metaform_home
    before = earlier_installs(home, recorded=False)
    monkeypatch.setattr(install.shutil, 'which', lambda command: str(HARNESS if command == 'claude' else OTHER))
    real_key = harness.key

    def fail_after_first(binary):
        if binary == str(OTHER):
            raise OSError('binary lookup failed')
        return real_key(binary)

    monkeypatch.setattr(harness, 'key', fail_after_first)
    with pytest.raises(OSError, match='binary lookup failed'), metaform_home.chassis():
        pass
    with sqlite3.connect(home / 'metaform.sqlite3') as db:
        assert list(db.iterdump()) == before
    monkeypatch.setattr(harness, 'key', real_key)
    assert harness.known(HARNESS)
    with metaform_home.chassis() as db:
        assert db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone() == ('3',)


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


@pytest.mark.kind('simulation')
def test_config_only_install_leaves_the_harness_for_first_use_to_record(run, machine, home):
    run('install', 'cursor', cwd=machine['folder'], env=machine['env'])
    config = Path(machine['env']['HOME']) / '.cursor' / 'mcp.json'
    assert 'metaform' in json.loads(config.read_text(encoding='utf-8'))['mcpServers']
    assert recorded(home) == []
