"""`metaform install`: set up AI tools to use Metaform, MCP-010 to MCP-021.

Checks come first and change nothing. Each chosen tool is registered through
its own command where it has one, or by merging one entry into its user-level
JSON config, always with the uvx entry of MCP-010; every file that changes is
backed up first. The metaform skill is copied to the shared folders and each
chosen tool's folder. Discoverable universal skills and their current libraries
are copied to harnesses with native discovery, with the exact deployed files recorded.
Claude Code also gets the metaform-node skill while map is enabled and on the folder's surface.
Then the exact registered command is started and proved,
and the run ends with one next step.
"""
from __future__ import annotations

import hashlib
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

from . import __version__, _build_info, agent_setup, harness, home, instructions, loader, settings
from .errors import Stop
from .module import Context, on_this_system
from .probe import probe, probe_http

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
    add_url: Callable[[str], list[str]] | None = None  # the registration of a Streamable HTTP server, MCP-002
    merge: bool = False
    verified: bool = True
    key: str = 'mcpServers'  # where the tool's JSON config holds its servers
    # An editor that mounts Metaform as its ACP agent, BASE-062: its entry for the `dispatch serve` command, merged
    # under `key` in place of an MCP server.
    agent: Callable[[list[str]], dict[str, Any]] | None = None
    # A config the tool writes as JSON with comments and trailing commas, as Zed's settings.json: changed in place, so
    # its comments and layout stay, BASE-062.
    jsonc: bool = False


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


def _zed_config() -> Path | None:
    """Zed's user settings: ~/.config/zed/settings.json on macOS and Linux, under XDG_CONFIG_HOME when it is set
    (zed.dev/docs/ai/external-agents), and %APPDATA%\\Zed\\settings.json on Windows, as Zed's own config_dir and
    settings_file give it (crates/paths/src/paths.rs)."""
    if system() == 'windows':
        appdata = os.environ.get('APPDATA')
        return Path(appdata) / 'Zed' / 'settings.json' if appdata else None
    base = os.environ.get('XDG_CONFIG_HOME') if system() == 'linux' else None
    return (Path(base) if base else user_home() / '.config') / 'zed' / 'settings.json'


def _zed_present() -> bool:
    config = _zed_config()
    return config is not None and config.parent.is_dir()


def _jetbrains_present() -> bool:
    """A JetBrains IDE here: the folder of its ACP file, ~/.jetbrains (jetbrains.com/help/ai-assistant/acp.html), which
    the IDE makes only once an agent is added by hand, or the folder every JetBrains IDE keeps its configuration in:
    %APPDATA%\\JetBrains on Windows, ~/Library/Application Support/JetBrains on macOS, ~/.config/JetBrains on Linux.
    Setting it up makes ~/.jetbrains/acp.json when there is none."""
    if (user_home() / '.jetbrains').is_dir():
        return True
    if system() == 'windows':
        appdata = os.environ.get('APPDATA')
        return bool(appdata) and (Path(str(appdata)) / 'JetBrains').is_dir()
    if system() == 'macos':
        return (user_home() / 'Library' / 'Application Support' / 'JetBrains').is_dir()
    base = os.environ.get('XDG_CONFIG_HOME')
    return ((Path(base) if base else user_home() / '.config') / 'JetBrains').is_dir()


def _zed_agent(command: list[str]) -> dict[str, Any]:
    """A custom agent server in Zed's agent_servers, as Zed's external agents page gives it."""
    return {'type': 'custom', 'command': command[0], 'args': command[1:], 'env': {}}


def _jetbrains_agent(command: list[str]) -> dict[str, Any]:
    """An agent server in a JetBrains IDE's acp.json agent_servers, as its ACP page gives it."""
    return {'command': command[0], 'args': command[1:], 'env': {}}


def tools() -> dict[str, Tool]:
    return {tool.name: tool for tool in (
        Tool('claude', 'Claude Code', _on_path('claude'), 'claude on PATH', lambda: user_home() / '.claude.json',
             lambda: user_home() / '.claude' / 'skills',
             add=lambda entry: ['claude', 'mcp', 'add', '--transport', 'stdio', '--scope', 'user', 'metaform', '--',
                                *entry],
             remove=['claude', 'mcp', 'remove', '--scope', 'user', 'metaform'],
             add_url=lambda url: ['claude', 'mcp', 'add', '--transport', 'http', '--scope', 'user', 'metaform', url]),
        Tool('codex', 'Codex', _on_path('codex'), 'codex on PATH', _codex_config,
             lambda: _codex_config().parent / 'skills',
             add=lambda entry: ['codex', 'mcp', 'add', 'metaform', '--', *entry],
             remove=['codex', 'mcp', 'remove', 'metaform'],
             add_url=lambda url: ['codex', 'mcp', 'add', 'metaform', '--url', url]),
        Tool('gemini', 'Gemini CLI', _on_path('gemini'), 'gemini on PATH', lambda: user_home() / '.gemini' /
             'settings.json', lambda: user_home() / '.gemini' / 'skills',
             add=lambda entry: ['gemini', 'mcp', 'add', '--scope', 'user', 'metaform', *entry],
             remove=['gemini', 'mcp', 'remove', '--scope', 'user', 'metaform'],
             add_url=lambda url: ['gemini', 'mcp', 'add', '--scope', 'user', '--transport', 'http', 'metaform', url]),
        Tool('cursor', 'Cursor', _folder('.cursor'), 'the folder ~/.cursor', lambda: user_home() / '.cursor' /
             'mcp.json', lambda: user_home() / '.cursor' / 'skills', merge=True),
        Tool('vscode', 'VS Code', _on_path('code'), 'code on PATH', _vscode_config, lambda: None, key='servers',
             add=lambda entry: ['code', '--add-mcp', json.dumps({'name': 'metaform', 'command': entry[0],
                                                                  'args': entry[1:]})],
             add_url=lambda url: ['code', '--add-mcp', json.dumps({'name': 'metaform', 'type': 'http', 'url': url})]),
        Tool('copilot', 'Copilot CLI', _on_path('copilot'), 'copilot on PATH', lambda: None,
             lambda: user_home() / '.copilot' / 'skills', verified=False),
        Tool('factory', 'Factory', _on_path('droid'), 'droid on PATH', lambda: None, lambda: None, verified=False),
        Tool('antigravity', 'Antigravity', _folder('.gemini', 'config'), 'the folder ~/.gemini/config', lambda: None,
             lambda: user_home() / '.gemini' / 'config' / 'skills', verified=False),
        Tool('claude-desktop', 'Claude Desktop', lambda: _desktop_config().parent.is_dir(), 'its config folder',
             _desktop_config, lambda: None, merge=True, verified=False),
        Tool('zed', 'Zed', _zed_present, 'its config folder', _zed_config, lambda: None, merge=True,
             key='agent_servers', agent=_zed_agent, jsonc=True),
        Tool('jetbrains', 'JetBrains IDEs', _jetbrains_present, 'its config folder',
             lambda: user_home() / '.jetbrains' / 'acp.json', lambda: None, merge=True, key='agent_servers',
             agent=_jetbrains_agent),
    )}


HANDED = 'METAFORM_INSTALL_WHEEL'  # the wheel a run from it handed the setup over with, `hand_over`
UPKEEP = 'METAFORM_INSTALL_UPKEEP'  # a newer stage hands its follow-up to the installed dependency environment


def source() -> Path:
    """The wheel to register: the running wheel, or the one a run from it handed the setup over with, else the last
    build, MCP-010."""
    running = os.environ.get('METAFORM_WHEEL') or os.environ.get(HANDED)
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


SERVE = ['metaform', 'dispatch', 'serve']  # what an editor starts as its ACP agent, BASE-062


def editor_entry(chosen: list[Tool], everything: bool, say: Callable[[str], None]) -> tuple[list[str], Path] | None:
    """The command editors start Metaform with, `uvx --from <wheel> metaform dispatch serve`, and its wheel, when an
    editor is chosen; it needs uv and the dispatch module, which serves it, BASE-062. With `all`, editors are left out
    while dispatch is off, and said so; named, they stop with the next step."""
    editors = [tool.name for tool in chosen if tool.agent is not None]
    if not editors:
        return None
    if not any(module.id == 'dispatch' for module in loader.enabled()):
        if everything:
            say(f'  {", ".join(editors)}: left out; editors start Metaform through dispatch, which is off. Next: '
                'metaform enable dispatch')
            return None
        raise Stop('Editors start Metaform through dispatch, which is off.', 'metaform enable dispatch')
    if shutil.which('uv') is None or shutil.which('uvx') is None:
        raise Stop('uv or uvx is not installed; editors start Metaform with uvx.',
                   UV_INSTALL.get(system(), UV_INSTALL_POSIX))
    wheel = source()
    command = entry(wheel, SERVE)
    say(f'Editor agent: {" ".join(command)}')
    return command, wheel


def behind(folder: Path) -> str:
    """The agent an editor reaches through `dispatch serve` with the settings as they are, and whether its start
    command is found here, so the person sees what the registration starts, BASE-062."""
    try:
        chosen = str(settings.value('dispatch_serve_agent', folder) or 'default')
        if chosen == 'default':
            chosen = str(settings.value('dispatch_agent', folder))
        if chosen == 'none':
            return 'Metaform alone, starting no model (dispatch_serve_agent is none)'
        start = str(settings.value(f'dispatch_{chosen}', folder))
    except (KeyError, Stop):
        return 'unknown; the dispatch settings are not readable here'
    try:
        words = shlex.split(start, posix=os.name != 'nt')
    except ValueError:
        words = []
    found = bool(words) and (shutil.which(words[0].strip('"')) is not None or Path(words[0].strip('"')).is_file())
    return (f'{chosen} ({start}), ' + ('found' if found else 'not found here, so Metaform serves alone until it is') +
            '; metaform set --dispatch-serve-agent none starts no model')


def prove_agent(command: list[str]) -> str | None:
    """Start the editors' command alone, `agent=none`, so no model starts, and send ACP's `initialize`; None when it
    answers with a protocol version, else why not, MCP-017 and BASE-062."""
    resolved = [shutil.which(command[0]) or command[0], *command[1:], 'agent=none']
    asked = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                        'params': {'protocolVersion': 1, 'clientCapabilities': {},
                                   'clientInfo': {'name': 'metaform-install', 'version': '1'}}}) + '\n'
    try:
        done = subprocess.run(resolved, input=asked, capture_output=True, text=True, encoding='utf-8',
                              timeout=TOOL_TIMEOUT, cwd=user_home(), check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return f'it did not start: {error}'
    for line in done.stdout.splitlines():
        try:
            found: Any = json.loads(line)
        except ValueError:
            continue
        answer = cast(dict[str, Any], found) if isinstance(found, dict) else {}
        if answer.get('id') == 1:
            result = answer.get('result')
            if isinstance(result, dict) and 'protocolVersion' in result:
                return None
            return f'initialize was answered with {json.dumps(answer)[:200]}'
    return done.stderr.strip()[-300:] or f'no answer to initialize, exit code {done.returncode}'


def http_url(folder: Path, command: list[str] | None) -> str | None:
    """The address AI tools are registered with when the mcp module's `mcp_transport` setting is http, or None for
    stdio, the default, MCP-010 and MCP-002. Only the mcp module's server has the setting; another provider is
    registered over stdio."""
    if command is None or command[1:2] != ['mcp'] or 'mcp_transport' not in settings.SCHEMA:
        return None
    if settings.value('mcp_transport', folder) != 'http':
        return None
    return f'http://127.0.0.1:{settings.value("mcp_port", folder)}/mcp'


def provision_mcp(folder: Path) -> str:
    """The MCP line of `metaform help provision`. A help page always shows: a provider choice that cannot be made
    is said on it, with its next step, instead of failing the page."""
    try:
        command = server(folder)
    except Stop as undecided:
        return f'MCP registration: none chosen yet. {undecided} Next: {undecided.next_step}. '
    if command is None:
        return 'MCP registration: skipped; no enabled module declares an MCP server. '
    url = http_url(folder, command)
    if url is not None:
        return (f'MCP registration: add an HTTP MCP server named metaform at {url}, wherever the tool keeps its MCP '
                'servers, and start it with metaform mcp serve --http. ')
    return ('MCP registration: add a stdio MCP server named metaform whose command is ' +
            ' '.join(command) + ', wherever the tool keeps its MCP servers. ')


def skill_text() -> bytes:
    return (resources.files('metaform') / 'skill' / 'SKILL.md').read_bytes()


NODE_SKILL = 'metaform-node'  # the person-invoked node read, `/metaform-node <address>`, Claude Code only


def node_skill_path() -> Path:
    """Where Claude Code loads a personal skill. Claude Code alone gets the node skill: it fills `$ARGUMENTS` and keeps
    a skill person-invoked with `disable-model-invocation`. Codex and Gemini CLI read the shared ~/.agents/skills, do
    neither, and would list it to their model as one more description, so it is never written there."""
    return user_home() / '.claude' / 'skills' / NODE_SKILL / 'SKILL.md'


def node_skill_wanted(folder: Path) -> bool:
    """The node skill runs `metaform map where`, so it exists only while map is enabled and on the folder's command
    surface; a skill whose command answers that map is off is never left behind."""
    return any(module.id == 'map' for module in loader.enabled()) and instructions.on_surface('map', folder)


def _node_plan(folder: Path, *, remove: bool = False) -> tuple[Path, bytes | None] | None:
    """What Claude Code's node skill needs: the path with the text to write, the path with None to remove it, or None
    when it is already as it should be."""
    path = node_skill_path()
    if not remove and node_skill_wanted(folder):
        text = (resources.files('metaform') / 'skill' / NODE_SKILL / 'SKILL.md').read_bytes()
        return None if path.is_file() and path.read_bytes() == text else (path, text)
    return (path, None) if path.is_file() else None


def _say_node(plan: tuple[Path, bytes | None] | None, say: Callable[[str], None], *, remove: bool = False) -> None:
    if plan is not None and plan[1] is not None:
        say(f'  skill: {plan[0]}')
    elif plan is not None:
        say(f'  skill: remove {plan[0]}' + ('' if remove else "; map is off or not on this folder's surface"))


def _apply_node(plan: tuple[Path, bytes | None] | None, backups: Path) -> None:
    if plan is None:
        return
    path, text = plan
    if text is None:
        _remove_file(path, backups)
        return
    _backup(path, backups)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text)


def node_skill_follows(identifier: str, folder: Path, say: Callable[[str], None]) -> None:
    """After map is enabled or disabled, Claude Code's node skill follows it, where Metaform set Claude Code up by
    install or provision; a tool Metaform never set up gets no skill."""
    if identifier != 'map':
        return
    path = node_skill_path()
    if not (path.is_file() or 'claude' in _installed() or
            agent_setup.owned('claude', user_home(), _codex_config().parent)):
        return
    plan = _node_plan(folder)
    if plan is None:
        return
    _apply_node(plan, home.home() / 'backups' / 'skills' / datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ'))
    say(f'Skill: {"wrote" if plan[1] is not None else "removed"} {path}')


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
    if home.is_home_path(target):
        home.mkdir_private(target.parent)
        home.write_private(target, path.read_bytes())
        found = path.stat()
        if os.name == 'nt':
            shutil.copystat(path, target)
        else:
            target.chmod(found.st_mode & 0o700)
            os.utime(target, ns=(found.st_atime_ns, found.st_mtime_ns))
    else:
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
    node = _node_plan(Path.cwd()) if tool == 'claude' else None
    say('Changes:')
    _preview_agent_changes(changes, backups, say)
    _say_node(node, say)
    _apply_agent_changes(changes[tool], backups)
    _apply_node(node, backups)
    say(f'Backups: {backups}' if backups.exists() else 'Backups: none needed')
    say('Next: finish the other supported features in metaform help provision, then metaform provision done')


def _merge(path: Path, server: dict[str, Any], backup: Path | None, key: str = 'mcpServers',
           jsonc: bool = False) -> None:
    """Add Metaform's server to a tool's JSON config. A config that is not a JSON object is left as it is and
    refused, naming it and its backup; the merged file replaces the old one whole, so a crash never leaves half. A
    config written as JSON with comments has only Metaform's entry written into its text, keeping the rest."""
    kept = f' A copy is at {backup}.' if backup else ''
    next_step = f'add "metaform": {json.dumps(server)} to {key} in {path}'
    if jsonc and path.is_file():
        text = _read_text(path)
        changed = _jsonc_put(text, key, 'metaform', server) if text is not None else None
        if changed is None:
            raise Stop(f'{path} is not a JSON object, even read with comments and trailing commas, or its {key} is '
                       f'not an object, so Metaform did not change it.{kept}', next_step)
        _write_text(path, changed)
        return
    data: Any = {}
    if path.is_file():
        data = _read_json(path)
    servers = cast(dict[str, Any], data).get(key, {}) if isinstance(data, dict) else None
    if not isinstance(servers, dict):
        why = 'is not valid JSON' if data is None else f'is not a JSON object with a {key} object'
        raise Stop(f'{path} {why}, so Metaform did not change it.{kept}', next_step)
    data = cast(dict[str, Any], data)
    data[key] = {**cast(dict[str, Any], servers), 'metaform': server}
    _write_json(path, data)


def _adding(tool: Tool, command: list[str], url: str | None) -> list[str]:
    """The command that registers Metaform's server with a tool: its HTTP form when the server is registered by
    address, MCP-002, otherwise its stdio form. A tool that does not merge a config has both; the catalogue
    guarantees it."""
    if url is not None:
        assert tool.add_url is not None
        return tool.add_url(url)
    assert tool.add is not None
    return tool.add(command)


def _read_json(path: Path) -> Any:
    """A tool's JSON config, or None when it is not JSON. Bytes are read so a UTF-8 file with a byte order mark,
    as some Windows editors write, reads as the JSON it holds."""
    try:
        return json.loads(path.read_bytes())
    except ValueError:
        return None


def _write_json(path: Path, data: Any) -> None:
    _write_text(path, json.dumps(data, indent=2) + '\n')


def _write_text(path: Path, text: str) -> None:
    """Write a tool's config beside the old one and move it into place, so a crash never leaves half a file; the
    temporary file never outlives a failed move, such as onto a file another program holds open on Windows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{path.name}.metaform-{os.getpid()}')
    try:
        temporary.write_text(text, encoding='utf-8')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_text(path: Path) -> str | None:
    try:
        return path.read_bytes().decode('utf-8-sig')
    except (OSError, UnicodeDecodeError):
        return None


# JSON with comments, as Zed writes its settings.json: `//` and `/* */` comments and trailing commas. It is read with
# a small parser that keeps where each member of an object is, so one member is written or removed in the text and
# every comment and the layout around it stay as the person left them.

@dataclass
class _Member:
    name: str
    start: int  # where its key begins
    value_start: int
    value_end: int
    inner: _Object | None  # its value, when that is an object


@dataclass
class _Object:
    opened: int  # the index of `{`
    closed: int  # the index of `}`
    members: list[_Member]


_LITERAL = re.compile(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?|true|false|null')


def _skip(text: str, at: int) -> int:
    """The index after any whitespace and comments from `at`."""
    while at < len(text):
        if text[at] in ' \t\r\n':
            at += 1
        elif text.startswith('//', at):
            ended = text.find('\n', at)
            at = len(text) if ended < 0 else ended + 1
        elif text.startswith('/*', at):
            ended = text.find('*/', at + 2)
            if ended < 0:
                raise ValueError('an unclosed comment')
            at = ended + 2
        else:
            break
    return at


def _string_end(text: str, at: int) -> int:
    if text[at] != '"':
        raise ValueError(f'a string expected at {at}')
    at += 1
    while text[at] != '"':
        at += 2 if text[at] == '\\' else 1
    return at + 1


def _value(text: str, at: int) -> tuple[int, _Object | None]:
    """Where the value at `at` ends, and its members when it is an object."""
    if text[at] == '{':
        opened, members = at, list[_Member]()
        at = _skip(text, at + 1)
        while text[at] != '}':
            start, key_end = at, _string_end(text, at)
            name = json.loads(text[start:key_end])
            at = _skip(text, key_end)
            if text[at] != ':':
                raise ValueError(f'a colon expected at {at}')
            value_start = _skip(text, at + 1)
            value_end, inner = _value(text, value_start)
            members.append(_Member(str(name), start, value_start, value_end, inner))
            at = _skip(text, value_end)
            if text[at] == ',':
                at = _skip(text, at + 1)
            elif text[at] != '}':
                raise ValueError(f'a comma expected at {at}')
        return at + 1, _Object(opened, at, members)
    if text[at] == '[':
        at = _skip(text, at + 1)
        while text[at] != ']':
            at = _skip(text, _value(text, at)[0])
            if text[at] == ',':
                at = _skip(text, at + 1)
            elif text[at] != ']':
                raise ValueError(f'a comma expected at {at}')
        return at + 1, None
    if text[at] == '"':
        return _string_end(text, at), None
    found = _LITERAL.match(text, at)
    if found is None:
        raise ValueError(f'a value expected at {at}')
    return found.end(), None


def _jsonc(text: str) -> _Object | None:
    """The top-level object of a JSON-with-comments text, or None when it is not one."""
    try:
        at = _skip(text, 0)
        end, found = _value(text, at)
        return found if found is not None and _skip(text, end) == len(text) else None
    except (ValueError, IndexError):
        return None


def _indent(text: str, at: int) -> str:
    line = text.rfind('\n', 0, at) + 1
    return text[line:line + len(text[line:at]) - len(text[line:at].lstrip(' \t'))]


def _dumped(value: Any, indent: str) -> str:
    return json.dumps(value, indent=2).replace('\n', '\n' + indent)


def _blank(text: str, at: int) -> int:
    """The index after any spaces and tabs from `at`."""
    while at < len(text) and text[at] in ' \t':
        at += 1
    return at


def _tail(text: str, member: _Member) -> tuple[int | None, int | None]:
    """After a member's value: where its comma is, if it has one, and where its line ends when nothing but that comma
    and a comment follow the value on its line, else None."""
    at = _blank(text, member.value_end)
    comma = at if at < len(text) and text[at] == ',' else None
    at = _blank(text, at + 1) if comma is not None else at
    if text.startswith('//', at):
        ended = text.find('\n', at)
        at = len(text) if ended < 0 else ended - (1 if text[ended - 1] == '\r' else 0)
    elif text.startswith('/*', at) and '\n' not in text[at:text.find('*/', at + 2)]:
        at = _blank(text, text.find('*/', at + 2) + 2)
    return comma, (at if at == len(text) or text[at] in '\r\n' else None)


def _inserted(text: str, into: _Object, name: str, value: Any) -> str:
    """`name: value` added as the last member of an object, on a line of its own after the last member's line, so a
    comment on that line stays with it; with a trailing comma when the last member has one, as the file writes."""
    if into.members:
        last = into.members[-1]
        indent = _indent(text, last.start)
        member = f'{indent}{json.dumps(name)}: {_dumped(value, indent)}'
        comma, line_end = _tail(text, last)
        if line_end is None:  # more on the value's line: right after the value, as compact JSON writes it
            return text[:last.value_end] + f',\n{member}' + text[last.value_end:]
        newline = '\r\n' if text.startswith('\r\n', line_end) else '\n'
        if comma is None:
            return text[:last.value_end] + ',' + text[last.value_end:line_end] + newline + member + text[line_end:]
        return text[:line_end] + newline + member + ',' + text[line_end:]
    outer = _indent(text, into.opened)
    indent = outer + '  '
    member = f'\n{indent}{json.dumps(name)}: {_dumped(value, indent)}'
    if not text[into.opened + 1:into.closed].strip():
        return text[:into.opened + 1] + member + f'\n{outer}' + text[into.closed:]
    return text[:into.opened + 1] + member + ',' + text[into.opened + 1:]


def _jsonc_put(text: str, key: str, name: str, value: Any) -> str | None:
    """The text with `key.name` set to `value`, or None when the text is not an object or its `key` is no object."""
    top = _jsonc(text)
    if top is None:
        return None
    outer = next((member for member in top.members if member.name == key), None)
    if outer is None:
        return _inserted(text, top, key, {name: value})
    if outer.inner is None:
        return None
    found = next((member for member in outer.inner.members if member.name == name), None)
    if found is None:
        return _inserted(text, outer.inner, name, value)
    return text[:found.value_start] + _dumped(value, _indent(text, found.start)) + text[found.value_end:]


def _removed(text: str, members: list[_Member], at: int) -> str:
    """The text without member `at`: its whole lines when it has lines of its own, and the comma before it when it
    was the last member and had none, so what `_inserted` added comes out as it went in."""
    found = members[at]
    line = text.rfind('\n', 0, found.start) + 1
    comma, line_end = _tail(text, found)
    if text[line:found.start].strip() == '' and line_end is not None:
        start = line
        end = line_end + (2 if text.startswith('\r\n', line_end) else 1 if line_end < len(text) else 0)
    elif at > 0:  # on a line with others: from the end of the member before it, its comma going with it
        return text[:members[at - 1].value_end] + text[found.value_end:]
    else:
        start, end = found.start, _skip(text, comma + 1) if comma is not None else found.value_end
    kept = text[:start] + text[end:]
    if comma is None and at > 0 and at == len(members) - 1:  # the last one, after a comma it no longer follows
        before, _ = _tail(text, members[at - 1])
        if before is not None:
            kept = kept[:before] + kept[before + 1:]
    return kept


def _jsonc_drop(text: str, key: str, name: str) -> str | None:
    """The text without `key.name`, and without `key` too when nothing else was in it; the same text when it has no
    `key.name`; None when it is not an object with `key` one."""
    top = _jsonc(text)
    outer = next((member for member in top.members if member.name == key), None) if top is not None else None
    if top is None or outer is None or outer.inner is None:
        return None
    members = outer.inner.members
    at = next((index for index, member in enumerate(members) if member.name == name), None)
    if at is None:
        return text
    if len(members) == 1:  # the object held only Metaform's member, as when Metaform made it: it goes too
        return _removed(text, top.members, top.members.index(outer))
    return _removed(text, members, at)


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
    with home.chassis() as db:
        return {str(row[0]) for row in db.execute("SELECT tool FROM installs WHERE source != ''")}


def _installed() -> dict[str, str | None]:
    """Each tool Metaform set up, with the skill file it wrote there."""
    with home.chassis() as db:
        return {str(row[0]): row[1] for row in db.execute('SELECT tool, skill_path FROM installs')}


def _record(tool: str, wheel: Path | None, skill: Path | None) -> None:
    with home.chassis(write=True) as db:
        db.execute('INSERT INTO installs(tool, source, skill_path, installed) VALUES (?, ?, ?, ?) '
                   "ON CONFLICT(tool) DO UPDATE SET source=CASE WHEN excluded.source='' THEN installs.source "
                   'ELSE excluded.source END, skill_path=excluded.skill_path, installed=excluded.installed',
                   (tool, str(wheel) if wheel is not None else '', str(skill) if skill else None, home.now()))


_NATIVE_SKILLS = frozenset(('claude', 'codex', 'gemini', 'cursor'))
_SKILL_CLIENTS = {
    'claude': 'claude', 'claude code': 'claude', 'claude-code': 'claude',
    'codex': 'codex', 'codex-mcp-client': 'codex',
    'gemini': 'gemini', 'gemini cli': 'gemini', 'gemini-cli': 'gemini',
    'cursor': 'cursor',
}


@dataclass(frozen=True)
class _SkillDeployment:
    root: Path
    files: dict[Path, bytes]
    versions: dict[str, str]


def _skill_plan(tool: Tool) -> _SkillDeployment | None:
    """Only verified harnesses known to inject native discovery receive universal skills, BASE-059."""
    if not tool.verified or tool.name not in _NATIVE_SKILLS or (root := tool.skills()) is None:
        return None
    from . import skills
    files: dict[Path, bytes] = {}
    versions: dict[str, str] = {}
    for skill in skills.catalog():
        if not skill.discover:
            continue
        versions[skill.address] = skill.version
        for relative, content in skills.deployment_files(skill).items():
            path = root / skill.name / relative
            if not path.is_relative_to(root) or '..' in path.relative_to(root).parts:
                raise ValueError(f'Skill deployment path escapes its folder: {relative}')
            files[path] = content
    return _SkillDeployment(root, files, versions)


def _deployment_record(tool: str) -> dict[str, Any]:
    raw = home.meta(f'skill_deployment.{tool}')
    try:
        record: object = json.loads(raw) if raw else {}
    except (ValueError, TypeError):
        return {}
    return cast(dict[str, Any], record) if isinstance(record, dict) else {}


def _skill_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _remove_deployed(tool: str, backups: Path, keep: set[Path] | None = None) -> None:
    """Remove recorded bytes only: user additions and edits retain their ownership."""
    record = _deployment_record(tool)
    root, files = record.get('root'), record.get('files')
    if not isinstance(root, str) or not isinstance(files, dict):
        return
    root_path = Path(root)
    for name, digest in cast(dict[str, object], files).items():
        path = Path(name)
        if (not path.is_relative_to(root_path) or '..' in path.relative_to(root_path).parts
                or (keep is not None and path in keep) or not path.is_file() or path.is_symlink()
                or _skill_hash(path.read_bytes()) != digest):
            continue
        _backup(path, backups)
        path.unlink()
        parent = path.parent
        while parent != root_path and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent


def _deploy_skills(tool: Tool, plan: _SkillDeployment, backups: Path) -> None:
    previous = _deployment_record(tool.name)
    # Keep ownership of old files for a retry, but never claim a partial update supplies discovery.
    home.set_meta(f'skill_deployment.{tool.name}', json.dumps({**previous, 'complete': False}))
    _remove_deployed(tool.name, backups, set(plan.files))
    old_files = previous.get('files')
    owned = dict(cast(dict[str, str], old_files)) if previous.get('root') == str(plan.root) and \
        isinstance(old_files, dict) else {}
    for path, content in plan.files.items():
        _backup(path, backups)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        owned[str(path)] = _skill_hash(content)
        home.set_meta(f'skill_deployment.{tool.name}', json.dumps({
            'complete': False, 'root': str(plan.root), 'files': owned,
        }))
    home.set_meta(f'skill_deployment.{tool.name}', json.dumps({
        'complete': True, 'package_version': __version__, 'root': str(plan.root), 'skills': plan.versions,
        'files': {str(path): _skill_hash(content) for path, content in plan.files.items()},
    }))


def skills_deployed(client_name: str) -> bool:
    """Whether this MCP client has the current discoverable skills and libraries on disk, BASE-059."""
    name = _SKILL_CLIENTS.get(client_name.strip().casefold())
    tool = tools().get(name) if name else None
    if tool is None:
        return False
    record = _deployment_record(tool.name)
    if record.get('complete') is not True or record.get('package_version') != __version__:
        return False
    plan = _skill_plan(tool)
    if plan is None or not plan.files or record.get('root') != str(plan.root) or record.get('skills') != plan.versions:
        return False
    expected = {str(path): _skill_hash(content) for path, content in plan.files.items()}
    if record.get('files') != expected:
        return False
    try:
        return all(path.is_file() and _skill_hash(path.read_bytes()) == expected[str(path)] for path in plan.files)
    except OSError:
        return False


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
    with home.chassis() as db:
        versions = dict(db.execute("SELECT key, value FROM meta WHERE key IN ('installed_version', 'last_run_version')"))
    if not force and versions.get('last_run_version') == __version__:
        return
    with home.chassis(write=True) as db:
        versions = dict(db.execute("SELECT key, value FROM meta WHERE key IN ('installed_version', 'last_run_version')"))
        if versions.get('installed_version') != __version__:
            _check_downgrade(versions.get('last_run_version'), force, 'metaform install force=true')
            # Approval belongs to this installation, not to a later raw upgrade that replaces it.
            db.execute("DELETE FROM meta WHERE key='installed_version'")
        for key in (('installed_version', 'last_run_version') if force else ('last_run_version',)):
            if versions.get(key) != __version__:
                db.execute('INSERT INTO meta(key, value) VALUES (?, ?) '
                           'ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, __version__))


def stage(wheel: Path, uv: str, force: bool, say: Callable[[str], None], retry: str) -> bool:
    """Install the running wheel before setting up AI tools; record only a successful install, BASE-047."""
    next_step = f'python "{wheel}" install force=true'
    # Keep preflight, executable replacement and approval together. Concurrent installs and
    # first runs use the same chassis write lock, so an older preflight cannot outlive a newer install.
    with home.chassis(write=True) as db:
        previous = None
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
        known = [version for version in [previous, *versions.values()] if version]
        newer = not known or _version(__version__) > max(_version(version) for version in known)
        for version in versions.values():
            _check_downgrade(version, force, next_step)
        result = _run('uv', [uv, 'tool', 'install', '--force', str(wheel)], next_step=retry)
        if result.returncode != 0:
            raise Failed(f'Metaform installation failed: {_said(result)}', retry)
        db.execute("INSERT INTO meta(key, value) VALUES ('installed_version', ?) "
                   'ON CONFLICT(key) DO UPDATE SET value=excluded.value', (__version__,))
    say(f'Installed: Metaform {__version__} from {wheel}')
    if newer and not loader.withdrawn():
        notify_install(wheel, say)
    return newer


def notify_install(wheel: Path, say: Callable[[str], None]) -> None:
    """Deliver after the approval commits, with installed dependencies available for upkeep agents."""
    source_context = Context(module='install', folder=Path.cwd(), sink=say)
    for delivery in source_context.publish('install.completed', {'version': __version__, 'wheel': str(wheel)}):
        if delivery['status'] != 'completed':
            say(f'Install follow-up ({delivery["module"]}): '
                f'{delivery.get("error", delivery["status"])}')


def hand_over(uv: str, wheel: Path, words: list[str], *, newer: bool = False) -> None:
    """Set the tools up with the Metaform the wheel has just installed. Run straight from the wheel, the modules whose
    compiled dependencies it cannot carry are left out, mcp among them, BASE-042, so this process would register no
    server; the installed copy has them all, and registers the same wheel."""
    found = _run('uv', [uv, 'tool', 'dir', '--bin'])
    installed = shutil.which('metaform', path=found.stdout.strip()) if found.returncode == 0 else None
    retry = 'metaform install ' + ' '.join(words) if words else BOTH_FORMS
    if installed is None:
        raise Failed('Metaform is installed, but its command was not found to set the tools up.', retry)
    environment = {key: value for key, value in os.environ.items() if key not in ('METAFORM_WHEEL', UPKEEP)}
    if newer:
        environment[UPKEEP] = __version__
    sys.stdout.flush()  # what this process said comes before what the installed copy says
    done = subprocess.run([installed, 'install', *words], env={**environment, HANDED: str(wheel)}, check=False)
    if done.returncode != 0:
        raise Failed('The installed Metaform did not finish setting the tools up.', retry)


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
        newer = stage(wheel, uv, force, say, retry)
        if loader.withdrawn():
            return hand_over(uv, wheel, [word for word in words if not word.startswith('force=')], newer=newer)
    elif os.environ.pop(UPKEEP, None) == __version__ and os.environ.get(HANDED):
        notify_install(source(), say)
    say(f'System: {system()}')
    say(f'Python: {platform.python_version()} (needs {_build_info.REQUIRES_PYTHON})')
    if not _python_ok():
        raise Stop(f'Python {platform.python_version()} is older than Metaform needs.',
                   f'install Python {_build_info.REQUIRES_PYTHON.lstrip(">=")} or newer')
    server_command = server(Path.cwd())
    url = http_url(Path.cwd(), server_command)
    wheel = None
    command = None
    if url is not None:
        say(f'Server: {url}, started with metaform mcp serve --http')
        command = server_command
    elif server_command is not None:
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
    editors = editor_entry(chosen, everything, say)
    if editors is None:
        chosen = [tool for tool in chosen if tool.agent is None]
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
        if tool.agent is not None and editors is not None:
            say(f'  {tool.name}: merge {tool.key}.metaform, the ACP agent, into {tool.config()}; backed up under '
                f'{backups}')
            continue
        if command is None:
            continue
        config = tool.config()
        # A tool that does not merge a config always has an add command; the catalogue guarantees it.
        how = f'merge mcpServers.metaform into {config}' if tool.merge else ' '.join(_adding(tool, command, url))
        say(f'  {tool.name}: {how}; changes {config}, backed up under {backups}')
    _preview_agent_changes(agent_changes, backups, say)
    skill_files = list(shared) + [folder / 'metaform' / 'SKILL.md' for tool in chosen if (folder := tool.skills())]
    for path in skill_files:
        say(f'  skill: {path}')
    deployments = {tool.name: plan for tool in chosen if (plan := _skill_plan(tool)) is not None}
    for name, plan in deployments.items():
        for path in plan.files:
            say(f'  skill: {path}; backed up under {backups}')
        if isinstance(previous_files := _deployment_record(name).get('files'), dict):
            for path in cast(dict[str, object], previous_files):
                if Path(path) not in plan.files:
                    say(f'  skill: remove {path} if unchanged; backed up under {backups}')
    node = _node_plan(Path.cwd()) if any(tool.name == 'claude' for tool in chosen) else None
    _say_node(node, say)
    if asking and input('Apply these changes? [y/N] ').strip().lower() not in ('y', 'yes'):
        raise Stop('Nothing was changed.', BOTH_FORMS)
    recorded = _recorded()
    unmerged: dict[str, Stop] = {}  # the tools whose config Metaform could not change, with why
    for tool in chosen:
        config = tool.config()
        backup = _backup(config, backups) if (command is not None or tool.agent is not None) and config is not None \
            else None
        folder = tool.skills()
        # Gemini's registration command also edits settings.json. Install the previewed hooks first,
        # so its own config merge retains them and no prepared edit overwrites the new MCP entry.
        if tool.name == 'gemini':
            _apply_agent_changes(agent_changes[tool.name], backups)
        if tool.agent is not None and editors is not None and config is not None:
            try:
                _merge(config, tool.agent(editors[0]), backup, tool.key, tool.jsonc)
            except Stop as stop:  # this editor is left out; the other tools are still set up and proven
                unmerged[tool.name] = stop
                continue
        elif command is None:
            pass  # Skills and instruction pointers remain useful through the CLI.
        elif tool.merge and config is not None:
            registered = {'url': url} if url else {'command': command[0], 'args': command[1:]}
            try:
                _merge(config, registered, backup, tool.key)
            except Stop as stop:  # this tool is left out; the others are still set up and proven, BASE-062
                unmerged[tool.name] = stop
                continue
        else:
            removed = ''
            if tool.name in recorded and tool.remove:
                result = _run(tool.name, tool.remove)
                if result.returncode != 0:
                    removed = f' Removing the earlier entry also failed: {_said(result)}'
            result = _run(tool.name, _adding(tool, command, url))
            # An entry the record does not know of, left by an earlier home, is replaced as the one entry, MCP-019.
            if (result.returncode != 0 and tool.remove and tool.name not in recorded
                    and _run(tool.name, tool.remove).returncode == 0):
                result = _run(tool.name, _adding(tool, command, url))
            if result.returncode != 0:
                raise Failed(f'{tool.name} registration failed: {_said(result)}{removed}',
                             f'metaform install {tool.name}')
        # Recorded as soon as it is registered, so a later failure never hides it from the next run, MCP-019.
        _record(tool.name, editors[1] if tool.agent is not None and editors is not None else wheel,
                folder / 'metaform' / 'SKILL.md' if folder else None)
        if tool.name != 'gemini':
            _apply_agent_changes(agent_changes[tool.name], backups)
        # The harness of the binary that registered it never sees the first-run notice, D96; a merged config
        # names no binary, so it records none.
        if not tool.merge and tool.add is not None and (binary := shutil.which(tool.add(command or ['metaform'])[0])):
            harness.done(binary)
    for path in skill_files:
        _backup(path, backups)
        if home.is_home_path(path):
            home.mkdir_private(path.parent)
            home.write_private(path, skill)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(skill)
    for tool in chosen:
        if tool.name not in unmerged and (plan := deployments.get(tool.name)) is not None:
            _deploy_skills(tool, plan, backups)
    _apply_node(node, backups)
    failed: list[str] = []
    servers = [tool for tool in chosen if tool.agent is None]
    reached = [tool for tool in servers if tool.name not in unmerged]
    if editors is not None:
        say('Proof:')
        why = prove_agent(editors[0])
        for tool in chosen:
            if tool.agent is not None and tool.name in unmerged:
                failed.append(tool.name)
                say(f'  {tool.name}: not registered: {unmerged[tool.name]} Next: {unmerged[tool.name].next_step}')
            elif tool.agent is not None and why:
                failed.append(tool.name)
                say(f'  {tool.name}: failed: {why}')
            elif tool.agent is not None:
                say(f'  {tool.name}: the ACP agent answers initialize')
        say(f'  behind it: {behind(Path.cwd())}')
    if command is not None and servers:
        say('Proof:')
        # the same command or address for every tool: one start, one answer
        proof = (probe_http(url) if url else probe(command, cwd=user_home())) if reached else None
        for tool in servers:
            if proof is None or tool.name in unmerged:
                stop = unmerged[tool.name]
                say(f'  {tool.name}: not registered: {stop} Next: {stop.next_step}')
            elif proof.ok:
                say(f'  {tool.name}: server starts, {proof.tools} tools')
            else:
                failed.append(tool.name)
                say(f'  {tool.name}: failed: {proof.reason}')
    say(f'Backups: {backups}' if backups.exists() else 'Backups: none needed')
    if unmerged:
        first = next(iter(unmerged.values()))
        raise Failed(f'{", ".join(unmerged)} could not be registered; every other tool was set up. {first.message}',
                     first.next_step)
    if failed:
        if url:
            raise Failed(f'Nothing answered at {url} for {", ".join(failed)}; the registration is kept.',
                         'metaform mcp serve --http')
        raise Failed(f'The server did not start for {", ".join(failed)}.', f'metaform install {failed[0]}')
    say('Next: open your AI tool in a project folder, or run metaform')


def _unmerge(path: Path, key: str, jsonc: bool = False) -> bool:
    """Take Metaform's entry out of a tool's JSON config and leave every other entry as it is, MCP-020; in the text of
    a config written with comments, so they stay."""
    if not path.is_file():
        return False
    if jsonc:
        text = _read_text(path)
        changed = _jsonc_drop(text, key, 'metaform') if text is not None else None
        if changed is None:
            raise Stop(f'{path} is not a JSON object with a {key} object, even read with comments, so Metaform did '
                       'not change it.', f'remove "metaform" from {key} in {path}')
        if changed == text:
            return False
        _write_text(path, changed)
        return True
    data = _read_json(path)
    servers = cast(dict[str, Any], data).get(key) if isinstance(data, dict) else None
    if not isinstance(servers, dict):
        raise Stop(f'{path} is not a JSON object with a {key} object, so Metaform did not change it.',
                   f'remove "metaform" from {key} in {path}')
    if 'metaform' not in servers:
        return False
    data = cast(dict[str, Any], data)
    data[key] = {name: value for name, value in cast(dict[str, Any], servers).items() if name != 'metaform'}
    _write_json(path, data)
    return True


def _remove_file(path: Path, backups: Path) -> bool:
    """Back up and remove one skill file, and its `metaform` or `metaform-node` folder when that is left empty."""
    if not path.is_file():
        return False
    _backup(path, backups)
    path.unlink()
    if path.parent.name in ('metaform', NODE_SKILL) and not any(path.parent.iterdir()):
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
    for tool in chosen:
        record = _deployment_record(tool.name)
        if isinstance(files := record.get('files'), dict):
            for path in cast(dict[str, object], files):
                say(f'  skill: remove {path} if unchanged; backed up under {backups}')
    node = _node_plan(Path.cwd(), remove=True) if any(tool.name == 'claude' for tool in chosen) else None
    _say_node(node, say, remove=True)
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
            _unmerge(config, tool.key, tool.jsonc)
        if tool.name != 'gemini':
            _apply_agent_changes(agent_changes[tool.name], backups)
        skill = installed.get(tool.name)
        if skill:
            _remove_file(Path(skill), backups)
        _remove_deployed(tool.name, backups)
        with home.chassis(write=True) as db:
            db.execute('DELETE FROM installs WHERE tool=?', (tool.name,))
            db.execute('DELETE FROM meta WHERE key=?', (f'skill_deployment.{tool.name}',))
        say(f'Removed: {tool.name}')
    for path in shared:
        _remove_file(path, backups)
    _apply_node(node, backups)
    say(f'Backups: {backups}' if backups.exists() else 'Backups: none needed')
    say(f"Data: Metaform's projects and maps stay in {home.home()}.")
