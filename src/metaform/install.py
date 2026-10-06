"""`metaform install`: set up AI tools to use Metaform, MCP-010 to MCP-021.

Checks come first and change nothing. Each chosen tool is registered through
its own command where it has one, or by merging one entry into its user-level
JSON config, always with the uvx entry of MCP-010; every file that changes is
backed up first. The one skill is copied to the shared folders and each
chosen tool's folder. Then the exact registered command is started and proved,
and the run ends with one next step.
"""
from __future__ import annotations

import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any, cast

from . import __version__, _build_info, agent_setup, harness, home, loader, settings
from .errors import Stop
from .module import on_this_system
from .probe import probe

UV_INSTALL = {'windows': 'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'}
UV_INSTALL_POSIX = 'curl -LsSf https://astral.sh/uv/install.sh | sh'
BOTH_FORMS = 'metaform install <tool>... or metaform install all'
BOTH_UNINSTALL = 'metaform uninstall <tool>... or metaform uninstall all'


class Failed(Exception):
    """Setup ran, and a proof failed: exit 1 with the report printed, MCP-017."""

    def __init__(self, message: str, next_step: str) -> None:
        super().__init__(message)
        self.next_step = next_step


def user_home() -> Path:
    return Path.home()


def system() -> str:
    name = platform.system().lower()
    return 'macos' if name == 'darwin' else name


@dataclass(frozen=True)
class Tool:
    """How one AI tool is found and registered, MCP-016. Unverified tools are listed and never set up, E2."""
    name: str
    label: str
    detect: Callable[[], bool]
    detected_by: str
    config: Callable[[], Path | None]
    skills: Callable[[], Path | None]
    add: Callable[[list[str]], list[str]] | None = None
    remove: list[str] = field(default_factory=list[str])
    merge: bool = False
    verified: bool = True
    key: str = 'mcpServers'  # where the tool's JSON config holds its servers


def _on_path(command: str) -> Callable[[], bool]:
    return lambda: shutil.which(command) is not None


def _folder(*parts: str) -> Callable[[], bool]:
    return lambda: user_home().joinpath(*parts).is_dir()


def _codex_config() -> Path:
    base = os.environ.get('CODEX_HOME')
    return (Path(base) if base else user_home() / '.codex') / 'config.toml'


def _vscode_config() -> Path:
    if system() == 'windows':
        return Path(os.environ.get('APPDATA', str(user_home()))) / 'Code' / 'User' / 'mcp.json'
    if system() == 'macos':
        return user_home() / 'Library' / 'Application Support' / 'Code' / 'User' / 'mcp.json'
    return user_home() / '.config' / 'Code' / 'User' / 'mcp.json'


def _desktop_config() -> Path:
    if system() == 'windows':
        return Path(os.environ.get('APPDATA', str(user_home()))) / 'Claude' / 'claude_desktop_config.json'
    return user_home() / 'Library' / 'Application Support' / 'Claude' / 'claude_desktop_config.json'


def tools() -> dict[str, Tool]:
    return {tool.name: tool for tool in (
        Tool('claude', 'Claude Code', _on_path('claude'), 'claude on PATH', lambda: user_home() / '.claude.json',
             lambda: user_home() / '.claude' / 'skills',
             add=lambda entry: ['claude', 'mcp', 'add', '--transport', 'stdio', '--scope', 'user', 'metaform', '--',
                                *entry],
             remove=['claude', 'mcp', 'remove', '--scope', 'user', 'metaform']),
        Tool('codex', 'Codex', _on_path('codex'), 'codex on PATH', _codex_config,
             lambda: user_home() / '.codex' / 'skills',
             add=lambda entry: ['codex', 'mcp', 'add', 'metaform', '--', *entry],
             remove=['codex', 'mcp', 'remove', 'metaform']),
        Tool('gemini', 'Gemini CLI', _on_path('gemini'), 'gemini on PATH', lambda: user_home() / '.gemini' /
             'settings.json', lambda: user_home() / '.gemini' / 'skills',
             add=lambda entry: ['gemini', 'mcp', 'add', '--scope', 'user', 'metaform', *entry],
             remove=['gemini', 'mcp', 'remove', '--scope', 'user', 'metaform']),
        Tool('cursor', 'Cursor', _folder('.cursor'), 'the folder ~/.cursor', lambda: user_home() / '.cursor' /
             'mcp.json', lambda: user_home() / '.cursor' / 'skills', merge=True),
        Tool('vscode', 'VS Code', _on_path('code'), 'code on PATH', _vscode_config, lambda: None, key='servers',
             add=lambda entry: ['code', '--add-mcp', json.dumps({'name': 'metaform', 'command': entry[0],
                                                                  'args': entry[1:]})]),
        Tool('copilot', 'Copilot CLI', _on_path('copilot'), 'copilot on PATH', lambda: None,
             lambda: user_home() / '.copilot' / 'skills', verified=False),
        Tool('factory', 'Factory', _on_path('droid'), 'droid on PATH', lambda: None, lambda: None, verified=False),
        Tool('antigravity', 'Antigravity', _folder('.gemini', 'config'), 'the folder ~/.gemini/config', lambda: None,
             lambda: user_home() / '.gemini' / 'config' / 'skills', verified=False),
        Tool('claude-desktop', 'Claude Desktop', lambda: _desktop_config().parent.is_dir(), 'its config folder',
             _desktop_config, lambda: None, merge=True, verified=False),
    )}


def source() -> Path:
    """The wheel to register: the running wheel, else the last build, MCP-010."""
    running = os.environ.get('METAFORM_WHEEL')
    if running:
        return Path(running)
    last = home.meta('last_build')
    if last:
        return Path(last)
    raise Stop('There is no wheel to register yet.', 'metaform build')


def server(folder: Path) -> list[str] | None:
    """The enabled provider's declared stdio command, independent of the folder's tool surface."""
    providers = {module.id: module.mcp_server for module in loader.enabled()
                 if module.mcp_server is not None and any(
                     verb.name == module.mcp_server and on_this_system(verb) for verb in module.verbs)}
    selected = settings.value('install_server', folder)
    if selected:
        if selected not in providers:
            raise Stop(f'{selected} is not an enabled MCP server provider.', 'metaform unset --install-server')
    elif len(providers) > 1:
        raise Stop('Several enabled modules declare an MCP server: ' + ', '.join(sorted(providers)) + '.',
                   'metaform set --install-server ' + min(providers))
    elif providers:
        selected = next(iter(providers))
    else:
        return None
    return ['metaform', selected, providers[selected]]


def entry(wheel: Path, command: list[str]) -> list[str]:
    return ['uvx', '--from', str(wheel), *command]


def provision_mcp(folder: Path) -> str:
    command = server(folder)
    if command is None:
        return 'MCP registration: skipped; no enabled module declares an MCP server. '
    return ('MCP registration: add a stdio MCP server named metaform whose command is ' +
            ' '.join(command) + ', wherever the tool keeps its MCP servers. ')


def skill_text() -> bytes:
    return (resources.files('metaform') / 'skill' / 'SKILL.md').read_bytes()


def _python_ok() -> bool:
    minimum = tuple(int(part) for part in _build_info.REQUIRES_PYTHON.lstrip('>=').split('.'))
    return sys.version_info[:len(minimum)] >= minimum


def _backup(path: Path, folder: Path) -> Path | None:
    if not path.is_file():
        return None
    try:
        relative = path.resolve().relative_to(user_home().resolve())
    except ValueError:
        relative = Path(*path.resolve().parts[1:])
    target = folder / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    return target


def _agent_changes(names: list[str], *, remove: bool = False) -> dict[str, list[agent_setup.Change]]:
    return {name: agent_setup.prepare(name, user_home(), _codex_config().parent, remove=remove)
            for name in dict.fromkeys(names)}


def _preview_agent_changes(changes: dict[str, list[agent_setup.Change]], backups: Path,
                           say: Callable[[str], None]) -> None:
    for name, edits in changes.items():
        for edit in edits:
            say(f'  {name}: {edit.path}, backed up under {backups}: {edit.description}')


def _apply_agent_changes(changes: list[agent_setup.Change], backups: Path) -> None:
    for change in changes:
        _backup(change.path, backups)
        change.write()


def provision(tool: str, say: Callable[[str], None]) -> None:
    """Use the approved harness additions independently of MCP registration, MCP-028 and MCP-036."""
    if tool not in agent_setup.TOOLS:
        raise Stop(f'{tool} has no global instruction setup.', 'metaform help provision')
    changes = _agent_changes([tool])
    backups = home.home() / 'backups' / 'provision' / datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')
    say('Changes:')
    _preview_agent_changes(changes, backups, say)
    _apply_agent_changes(changes[tool], backups)
    say(f'Backups: {backups}' if backups.exists() else 'Backups: none needed')
    say('Next: finish the other supported features in metaform help provision, then metaform provision done')


def _merge(path: Path, command: list[str], backup: Path | None) -> None:
    """Add Metaform's server to a tool's JSON config. A config that is not a JSON object is left as it is and
    refused, naming it and its backup; the merged file replaces the old one whole, so a crash never leaves half."""
    data: Any = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except ValueError:
            data = None
    servers = cast(dict[str, Any], data).get('mcpServers', {}) if isinstance(data, dict) else None
    if not isinstance(servers, dict):
        kept = f' A copy is at {backup}.' if backup else ''
        raise Stop(f'{path} is not a JSON object with an mcpServers object, so Metaform did not change it.{kept}',
                   f'add "metaform": {json.dumps({"command": command[0], "args": command[1:]})} to mcpServers in '
                   f'{path}')
    data = cast(dict[str, Any], data)
    data['mcpServers'] = {**cast(dict[str, Any], servers), 'metaform': {'command': command[0], 'args': command[1:]}}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{path.name}.metaform-{os.getpid()}')
    temporary.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, path)


TOOL_TIMEOUT = 120  # seconds for one command of a tool, such as claude mcp add, M6


def _run(tool: str, command: list[str], *, next_step: str | None = None) -> subprocess.CompletedProcess[str]:
    resolved = shutil.which(command[0]) or command[0]
    try:
        return subprocess.run([resolved, *command[1:]], capture_output=True, text=True, timeout=TOOL_TIMEOUT,
                              check=False)
    except subprocess.TimeoutExpired:
        raise Failed(f'{tool}: {" ".join(command[:3])} did not finish in {TOOL_TIMEOUT} seconds.',
                     next_step or f'metaform install {tool}') from None


def _said(result: subprocess.CompletedProcess[str]) -> str:
    return result.stderr.strip() or result.stdout.strip() or f'exit code {result.returncode}'


def _recorded() -> set[str]:
    with home.base() as db:
        return {str(row[0]) for row in db.execute("SELECT tool FROM installs WHERE source != ''")}


def _installed() -> dict[str, str | None]:
    """Each tool Metaform set up, with the skill file it wrote there."""
    with home.base() as db:
        return {str(row[0]): row[1] for row in db.execute('SELECT tool, skill_path FROM installs')}


def _record(tool: str, wheel: Path | None, skill: Path | None) -> None:
    with home.base(write=True) as db:
        db.execute('INSERT INTO installs(tool, source, skill_path, installed) VALUES (?, ?, ?, ?) '
                   "ON CONFLICT(tool) DO UPDATE SET source=CASE WHEN excluded.source='' THEN installs.source "
                   'ELSE excluded.source END, skill_path=excluded.skill_path, installed=excluded.installed',
                   (tool, str(wheel) if wheel is not None else '', str(skill) if skill else None, home.now()))


def _choose(names: list[str], everything: bool, detected: dict[str, Tool], say: Callable[[str], None]) -> list[Tool]:
    offered = {name: tool for name, tool in detected.items() if tool.verified}
    if everything:
        return list(offered.values())
    if names:
        chosen: list[Tool] = []
        for name in dict.fromkeys(names):
            if name not in offered:
                reason = 'is not verified yet' if name in detected else 'is not detected here'
                raise Stop(f'{name} {reason}.', BOTH_FORMS)
            chosen.append(offered[name])
        return chosen
    if not sys.stdin.isatty():
        raise Stop('Name the tools to set up; without a terminal nothing is asked.', BOTH_FORMS)
    chosen: list[Tool] = []
    for tool in offered.values():
        answer = input(f'Set up {tool.label} ({tool.name})? [Y/n] ').strip().lower()
        if answer in ('', 'y', 'yes'):
            chosen.append(tool)
    return chosen


def _named(verb: str, words: list[str], both: str) -> tuple[list[str], bool]:
    """The tools named, and whether `all` was."""
    names: list[str] = []
    everything = ended = False
    for word in words:
        if not ended and word == '--':
            ended = True
        elif not ended and word == 'all':
            everything = True
        elif not ended and word.startswith('-'):
            raise Stop(f'{verb} takes tool names, not {word}.', both)
        else:
            names.append(word)
    return names, everything


def install_options(words: list[str]) -> tuple[list[str], bool, bool]:
    """Separate the downgrade consent noun from AI tool names, BASE-047 and BASE-043."""
    tools: list[str] = []
    force = ended = False
    for word in words:
        if not ended and word.startswith('force='):
            value = word.partition('=')[2]
            if value not in ('true', 'false'):
                raise Stop('force= takes true or false.', 'metaform install --help')
            force = value == 'true'
        else:
            tools.append(word)
            if word == '--':
                ended = True
    names, everything = _named('install', tools, BOTH_FORMS)
    return names, everything, force


def _version(version: str) -> tuple[int, ...]:
    """Compare numeric version components, including multi-digit CalVer months and update counts."""
    if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)*', version):
        raise Stop(f'Metaform cannot compare version {version!r}.', 'metaform install --help')
    return tuple(int(part) for part in version.split('.'))


def _check_downgrade(previous: str | None, force: bool, next_step: str) -> None:
    if previous and _version(__version__) < _version(previous) and not force:
        raise Stop(f'Metaform {__version__} would downgrade Metaform {previous}; force=true is required.', next_step)


def backstage(force: bool = False) -> None:
    """Protect a home from an installed copy that skipped the wheel's install stage, BASE-047."""
    if os.environ.get('METAFORM_WHEEL'):
        return
    with home.base() as db:
        versions = dict(db.execute("SELECT key, value FROM meta WHERE key IN ('installed_version', 'last_run_version')"))
    if not force and versions.get('last_run_version') == __version__:
        return
    with home.base(write=True) as db:
        versions = dict(db.execute("SELECT key, value FROM meta WHERE key IN ('installed_version', 'last_run_version')"))
        if versions.get('installed_version') != __version__:
            _check_downgrade(versions.get('last_run_version'), force, 'metaform install force=true')
            # Approval belongs to this installation, not to a later raw upgrade that replaces it.
            db.execute("DELETE FROM meta WHERE key='installed_version'")
        for key in (('installed_version', 'last_run_version') if force else ('last_run_version',)):
            if versions.get(key) != __version__:
                db.execute('INSERT INTO meta(key, value) VALUES (?, ?) '
                           'ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, __version__))


def stage(wheel: Path, uv: str, force: bool, say: Callable[[str], None], retry: str) -> None:
    """Install the running wheel before setting up AI tools; record only a successful install, BASE-047."""
    next_step = f'python "{wheel}" install force=true'
    # Keep preflight, executable replacement and approval together. Concurrent installs and
    # first runs use the same chassis write lock, so an older preflight cannot outlive a newer install.
    with home.base(write=True) as db:
        installed = shutil.which('metaform')
        if installed:
            probe_next = f'"{installed}" --version'
            result = _run('metaform', [installed, '--version'], next_step=probe_next)
            if result.returncode != 0:
                raise Failed(f'The installed Metaform version could not be read: {_said(result)}',
                             probe_next)
            previous = result.stdout.strip().removeprefix('metaform ')
            _check_downgrade(previous, force, next_step)
        versions = dict(db.execute("SELECT key, value FROM meta WHERE key IN ('installed_version', 'last_run_version')"))
        for version in versions.values():
            _check_downgrade(version, force, next_step)
        result = _run('uv', [uv, 'tool', 'install', '--force', str(wheel)], next_step=retry)
        if result.returncode != 0:
            raise Failed(f'Metaform installation failed: {_said(result)}', retry)
        db.execute("INSERT INTO meta(key, value) VALUES ('installed_version', ?) "
                   'ON CONFLICT(key) DO UPDATE SET value=excluded.value', (__version__,))
    say(f'Installed: Metaform {__version__} from {wheel}')


def install(words: list[str], say: Callable[[str], None]) -> None:
    names, everything, force = install_options(words)
    asking = not names and not everything
    if os.environ.get('METAFORM_WHEEL'):
        uv = shutil.which('uv')
        if uv is None:
            raise Stop('uv is not installed; Metaform installs its wheel with uv.',
                       UV_INSTALL.get(system(), UV_INSTALL_POSIX))
        wheel = source()
        retry_words = ['python', str(wheel), 'install', *(['all'] if everything else names)]
        if force:
            retry_words.append('force=true')
        retry = subprocess.list2cmdline(retry_words) if os.name == 'nt' else shlex.join(retry_words)
        stage(wheel, uv, force, say, retry)
    say(f'System: {system()}')
    say(f'Python: {platform.python_version()} (needs {_build_info.REQUIRES_PYTHON})')
    if not _python_ok():
        raise Stop(f'Python {platform.python_version()} is older than Metaform needs.',
                   f'install Python {_build_info.REQUIRES_PYTHON.lstrip(">=")} or newer')
    server_command = server(Path.cwd())
    wheel = None
    command = None
    if server_command is not None:
        uv, uvx = shutil.which('uv'), shutil.which('uvx')
        say(f'uv: {uv or "missing"}')
        if uv is None or uvx is None:
            raise Stop('uv or uvx is not installed; Metaform starts its server with uvx.',
                       UV_INSTALL.get(system(), UV_INSTALL_POSIX))
        wheel = source()
        say(f'Source: {wheel}')
        command = entry(wheel, server_command)
    else:
        say('MCP registration and proof: skipped; no enabled module declares an MCP server.')
    catalogue = tools()
    detected = {name: tool for name, tool in catalogue.items() if tool.detect()}
    say('Tools:')
    for tool in catalogue.values():
        if tool.name in detected:
            say(f'  {tool.name}  {tool.label}, found by {tool.detected_by}' +
                ('' if tool.verified else '  (unverified; not offered)'))
    if not any(tool.verified for tool in detected.values()):
        say('  none that can be set up')
    chosen = _choose(names, everything, detected, say)
    if not chosen:
        raise Stop('No tool was chosen.', BOTH_FORMS)
    agent_changes = _agent_changes([tool.name for tool in chosen])
    stamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')
    backups = home.home() / 'backups' / 'install' / stamp
    skill = skill_text()
    shared = [home.home() / 'skills' / 'metaform' / 'SKILL.md', user_home() / '.agents' / 'skills' / 'metaform' /
              'SKILL.md']
    say('Changes:')
    for tool in chosen:
        if command is None:
            continue
        config = tool.config()
        # A tool that does not merge a config always has an add command; the catalogue guarantees it.
        how = f'merge mcpServers.metaform into {config}' if tool.merge else ' '.join(tool.add(command))  # type: ignore[misc]
        say(f'  {tool.name}: {how}; changes {config}, backed up under {backups}')
    _preview_agent_changes(agent_changes, backups, say)
    skill_files = list(shared) + [folder / 'metaform' / 'SKILL.md' for tool in chosen if (folder := tool.skills())]
    for path in skill_files:
        say(f'  skill: {path}')
    if asking and input('Apply these changes? [y/N] ').strip().lower() not in ('y', 'yes'):
        raise Stop('Nothing was changed.', BOTH_FORMS)
    recorded = _recorded()
    for tool in chosen:
        config = tool.config()
        backup = _backup(config, backups) if command is not None and config is not None else None
        folder = tool.skills()
        # Gemini's registration command also edits settings.json. Install the previewed hooks first,
        # so its own config merge retains them and no prepared edit overwrites the new MCP entry.
        if tool.name == 'gemini':
            _apply_agent_changes(agent_changes[tool.name], backups)
        if command is None:
            pass  # Skills and instruction pointers remain useful through the CLI.
        elif tool.merge and config is not None:
            _merge(config, command, backup)
        else:
            removed = ''
            if tool.name in recorded and tool.remove:
                result = _run(tool.name, tool.remove)
                if result.returncode != 0:
                    removed = f' Removing the earlier entry also failed: {_said(result)}'
            assert tool.add is not None
            result = _run(tool.name, tool.add(command))
            # An entry the record does not know of, left by an earlier home, is replaced as the one entry, MCP-019.
            if (result.returncode != 0 and tool.remove and tool.name not in recorded
                    and _run(tool.name, tool.remove).returncode == 0):
                result = _run(tool.name, tool.add(command))
            if result.returncode != 0:
                raise Failed(f'{tool.name} registration failed: {_said(result)}{removed}',
                             f'metaform install {tool.name}')
        # Recorded as soon as it is registered, so a later failure never hides it from the next run, MCP-019.
        _record(tool.name, wheel, folder / 'metaform' / 'SKILL.md' if folder else None)
        if tool.name != 'gemini':
            _apply_agent_changes(agent_changes[tool.name], backups)
        # The harness of the binary that registered it never sees the first-run notice, D96; a merged config
        # names no binary, so it records none.
        if not tool.merge and tool.add is not None and (binary := shutil.which(tool.add(command or ['metaform'])[0])):
            harness.done(binary)
    for path in skill_files:
        _backup(path, backups)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(skill)
    failed: list[str] = []
    if command is not None:
        say('Proof:')
        for tool in chosen:
            proof = probe(command, cwd=user_home())
            if proof.ok:
                say(f'  {tool.name}: server starts, {proof.tools} tools')
            else:
                failed.append(tool.name)
                say(f'  {tool.name}: failed: {proof.reason}')
    say(f'Backups: {backups}' if backups.exists() else 'Backups: none needed')
    if failed:
        raise Failed(f'The server did not start for {", ".join(failed)}.', f'metaform install {failed[0]}')
    say('Next: open your AI tool in a project folder, or run metaform')


def _unmerge(path: Path, key: str) -> bool:
    """Take Metaform's entry out of a tool's JSON config and leave every other entry as it is, MCP-020."""
    if not path.is_file():
        return False
    try:
        data: Any = json.loads(path.read_text(encoding='utf-8'))
    except ValueError:
        data = None
    servers = cast(dict[str, Any], data).get(key) if isinstance(data, dict) else None
    if not isinstance(servers, dict):
        raise Stop(f'{path} is not a JSON object with a {key} object, so Metaform did not change it.',
                   f'remove "metaform" from {key} in {path}')
    if 'metaform' not in servers:
        return False
    data = cast(dict[str, Any], data)
    data[key] = {name: value for name, value in cast(dict[str, Any], servers).items() if name != 'metaform'}
    temporary = path.with_name(f'.{path.name}.metaform-{os.getpid()}')
    temporary.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, path)
    return True


def _remove_file(path: Path, backups: Path) -> bool:
    """Back up and remove one skill file, and its `metaform` folder when that is left empty."""
    if not path.is_file():
        return False
    _backup(path, backups)
    path.unlink()
    if path.parent.name == 'metaform' and not any(path.parent.iterdir()):
        path.parent.rmdir()
    return True


def uninstall(words: list[str], say: Callable[[str], None]) -> None:
    """Remove what setup added: each tool's registration and skill, and the shared skill copies once no tool is
    left. A config keeps every other entry, the user's later ones included. The data in the home stays, MCP-020."""
    names, everything = _named('uninstall', words, BOTH_UNINSTALL)
    installed = _installed()
    registered = _recorded()
    available = set(installed) | {name for name in agent_setup.TOOLS
                                 if agent_setup.owned(name, user_home(), _codex_config().parent)}
    if not available:
        raise Stop('Metaform is not set up in any tool.', 'metaform install')
    catalogue = tools()
    chosen: list[Tool]
    if everything:
        chosen = [tool for name, tool in catalogue.items() if name in available]
    elif names:
        chosen = []
        for name in dict.fromkeys(names):
            if name not in available or name not in catalogue:
                raise Stop(f'{name} was not set up by Metaform.', BOTH_UNINSTALL)
            chosen.append(catalogue[name])
    else:
        if not sys.stdin.isatty():
            raise Stop('Name the tools to remove Metaform from; without a terminal nothing is asked.', BOTH_UNINSTALL)
        chosen = [catalogue[name] for name in sorted(available) if name in catalogue and
                  input(f'Remove Metaform from {catalogue[name].label} ({name})? [Y/n] ').strip().lower()
                  in ('', 'y', 'yes')]
    if not chosen:
        raise Stop('No tool was chosen.', BOTH_UNINSTALL)
    agent_changes = _agent_changes([tool.name for tool in chosen], remove=True)
    stamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')
    backups = home.home() / 'backups' / 'uninstall' / stamp
    left = set(installed) - {tool.name for tool in chosen}
    shared = [] if left or not installed else [home.home() / 'skills' / 'metaform' / 'SKILL.md',
                              user_home() / '.agents' / 'skills' / 'metaform' / 'SKILL.md']
    say('Changes:')
    for tool in chosen:
        if tool.name not in registered:
            continue
        config = tool.config()
        how = ' '.join(tool.remove) if tool.remove else f'remove {tool.key}.metaform from {config}'
        say(f'  {tool.name}: {how}; changes {config}, backed up under {backups}')
    _preview_agent_changes(agent_changes, backups, say)
    skill_files = [Path(path) for tool in chosen if (path := installed.get(tool.name))] + shared
    for path in skill_files:
        say(f'  skill: remove {path}')
    if not names and not everything and input('Apply these changes? [y/N] ').strip().lower() not in ('y', 'yes'):
        raise Stop('Nothing was changed.', BOTH_UNINSTALL)
    for tool in chosen:
        config = tool.config()
        if tool.name in registered and config is not None:
            _backup(config, backups)
        if tool.name == 'gemini':
            _apply_agent_changes(agent_changes[tool.name], backups)
        if tool.name in registered and tool.remove:
            result = _run(tool.name, tool.remove)
            if result.returncode != 0:
                raise Failed(f'{tool.name}: removing the registration failed: {_said(result)}',
                             f'metaform uninstall {tool.name}')
        elif tool.name in registered and config is not None:
            _unmerge(config, tool.key)
        if tool.name != 'gemini':
            _apply_agent_changes(agent_changes[tool.name], backups)
        skill = installed.get(tool.name)
        if skill:
            _remove_file(Path(skill), backups)
        with home.base(write=True) as db:
            db.execute('DELETE FROM installs WHERE tool=?', (tool.name,))
        say(f'Removed: {tool.name}')
    for path in shared:
        _remove_file(path, backups)
    say(f'Backups: {backups}' if backups.exists() else 'Backups: none needed')
    say(f"Data: Metaform's projects and maps stay in {home.home()}.")
