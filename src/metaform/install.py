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
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

from . import __version__, _build_info, home
from .errors import Stop
from .probe import probe

UV_INSTALL = {'windows': 'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'}
UV_INSTALL_POSIX = 'curl -LsSf https://astral.sh/uv/install.sh | sh'
BOTH_FORMS = 'metaform install <tool>... or metaform install all'


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
    remove: list[str] = field(default_factory=list)
    merge: bool = False
    verified: bool = True


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
        Tool('vscode', 'VS Code', _on_path('code'), 'code on PATH', _vscode_config, lambda: None,
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


def entry(wheel: Path) -> list[str]:
    return ['uvx', '--from', str(wheel), 'metaform', 'mcp', 'serve']


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


def _merge(path: Path, command: list[str]) -> None:
    data = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    servers = data.setdefault('mcpServers', {})
    servers['metaform'] = {'command': command[0], 'args': command[1:]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    resolved = shutil.which(command[0]) or command[0]
    return subprocess.run([resolved, *command[1:]], capture_output=True, text=True)


def _recorded() -> set[str]:
    with home.base() as db:
        return {row[0] for row in db.execute('SELECT tool FROM installs')}


def _record(tool: str, wheel: Path, skill: Path | None) -> None:
    with home.base(write=True) as db:
        db.execute('INSERT INTO installs(tool, source, skill_path, installed) VALUES (?, ?, ?, ?) '
                   'ON CONFLICT(tool) DO UPDATE SET source=excluded.source, skill_path=excluded.skill_path, '
                   'installed=excluded.installed', (tool, str(wheel), str(skill) if skill else None, home.now()))


def _choose(names: list[str], everything: bool, detected: dict[str, Tool], say: Callable[[str], None]) -> list[Tool]:
    offered = {name: tool for name, tool in detected.items() if tool.verified}
    if everything:
        return list(offered.values())
    if names:
        chosen = []
        for name in names:
            if name not in offered:
                reason = 'is not verified yet' if name in detected else 'is not detected here'
                raise Stop(f'{name} {reason}.', BOTH_FORMS)
            chosen.append(offered[name])
        return chosen
    if not sys.stdin.isatty():
        raise Stop('Name the tools to set up; without a terminal nothing is asked.', BOTH_FORMS)
    chosen = []
    for tool in offered.values():
        answer = input(f'Set up {tool.label} ({tool.name})? [Y/n] ').strip().lower()
        if answer in ('', 'y', 'yes'):
            chosen.append(tool)
    return chosen


def install(words: list[str], say: Callable[[str], None]) -> None:
    names, everything, ended = [], False, False
    for word in words:
        if not ended and word == '--':
            ended = True
        elif not ended and word == 'all':
            everything = True
        elif not ended and word.startswith('-'):
            raise Stop(f'install takes tool names, not {word}.', BOTH_FORMS)
        else:
            names.append(word)
    asking = not names and not everything
    say(f'System: {system()}')
    say(f'Python: {platform.python_version()} (needs {_build_info.REQUIRES_PYTHON})')
    if not _python_ok():
        raise Stop(f'Python {platform.python_version()} is older than Metaform needs.',
                   f'install Python {_build_info.REQUIRES_PYTHON.lstrip(">=")} or newer')
    uv, uvx = shutil.which('uv'), shutil.which('uvx')
    say(f'uv: {uv or "missing"}')
    if uv is None or uvx is None:
        raise Stop('uv is not installed; Metaform starts its server with uvx.',
                   UV_INSTALL.get(system(), UV_INSTALL_POSIX))
    wheel = source()
    say(f'Source: {wheel}')
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
    command = entry(wheel)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backups = home.home() / 'backups' / 'install' / stamp
    skill = skill_text()
    shared = [home.home() / 'skills' / 'metaform' / 'SKILL.md', user_home() / '.agents' / 'skills' / 'metaform' /
              'SKILL.md']
    say('Changes:')
    for tool in chosen:
        config = tool.config()
        how = f'merge mcpServers.metaform into {config}' if tool.merge else ' '.join(tool.add(command))  # type: ignore[misc]
        say(f'  {tool.name}: {how}; changes {config}, backed up under {backups}')
    skill_files = list(shared) + [folder / 'metaform' / 'SKILL.md' for tool in chosen if (folder := tool.skills())]
    for path in skill_files:
        say(f'  skill: {path}')
    if asking and input('Apply these changes? [y/N] ').strip().lower() not in ('y', 'yes'):
        raise Stop('Nothing was changed.', BOTH_FORMS)
    recorded = _recorded()
    for tool in chosen:
        config = tool.config()
        if config is not None:
            _backup(config, backups)
        if tool.merge and config is not None:
            _merge(config, command)
            continue
        if tool.name in recorded and tool.remove:
            _run(tool.remove)
        assert tool.add is not None
        result = _run(tool.add(command))
        if result.returncode != 0:
            raise Failed(f'{tool.name} registration failed: {result.stderr.strip() or result.stdout.strip()}',
                         f'metaform install {tool.name}')
    for path in skill_files:
        _backup(path, backups)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(skill)
    for tool in chosen:
        folder = tool.skills()
        _record(tool.name, wheel, folder / 'metaform' / 'SKILL.md' if folder else None)
    say('Proof:')
    failed = []
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
