"""`metaform start`: one command in a person's own project folder, and their project as a living map, CLI-041.

It chains what exists, each with the default that asks nothing: the folder is registered under its own name, the
modules the chain needs are turned on, Claude Code is connected to this project, the intake agent is started with
what the files already say, the web GUI is started and the browser opened on the project. It asks only what the
files cannot say, at most two short questions, and only a person at a terminal. Run again, it changes nothing that
is already so and opens the page again.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tomllib
import webbrowser
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from . import context, home, loader, prompt_files, settings
from .data import Recording, Store
from .errors import Stop, StoreError
from .module import call
from .wording import counted

Say = Callable[[str], None]

NEEDED = ('map', 'intake', 'mcp', 'web', 'dispatch')  # the modules the chain runs; dispatch ships off
AGENT_TOOLS = ('claude', 'codex', 'gemini')  # AI tools that are also dispatch agents, in the order one is chosen
SKIPPED = {'node_modules', '__pycache__', 'venv', 'env', 'dist', 'build', 'target', 'vendor', 'site-packages'}
MOST_FILES = 20000  # a folder read stops here, so a home folder or a monorepo is read in seconds
LANGUAGES = {
    '.py': 'Python', '.js': 'JavaScript', '.mjs': 'JavaScript', '.cjs': 'JavaScript', '.jsx': 'JavaScript',
    '.ts': 'TypeScript', '.tsx': 'TypeScript', '.go': 'Go', '.rs': 'Rust', '.java': 'Java', '.kt': 'Kotlin',
    '.swift': 'Swift', '.c': 'C', '.h': 'C', '.cc': 'C++', '.cpp': 'C++', '.hpp': 'C++', '.cs': 'C#', '.rb': 'Ruby',
    '.php': 'PHP', '.scala': 'Scala', '.dart': 'Dart', '.lua': 'Lua', '.r': 'R', '.jl': 'Julia', '.ex': 'Elixir',
    '.exs': 'Elixir', '.erl': 'Erlang', '.hs': 'Haskell', '.clj': 'Clojure', '.sh': 'Shell', '.ps1': 'PowerShell',
    '.sql': 'SQL', '.vue': 'Vue', '.svelte': 'Svelte', '.html': 'HTML', '.css': 'CSS', '.scss': 'CSS', '.zig': 'Zig',
    '.m': 'Objective-C', '.gd': 'GDScript', '.ipynb': 'Jupyter',
}
MANIFESTS = ('pyproject.toml', 'package.json', 'Cargo.toml', 'go.mod', 'pom.xml', 'build.gradle', 'build.gradle.kts',
             'Gemfile', 'composer.json', 'mix.exs', 'pubspec.yaml', 'CMakeLists.txt', 'Makefile', 'setup.py',
             'requirements.txt', 'deno.json', 'Package.swift')
READMES = ('README.md', 'README.rst', 'README.txt', 'README', 'readme.md', 'Readme.md')


@dataclass
class Read:
    """What a folder's files say before any agent reads them."""
    name: str = ''
    description: str = ''
    described_by: str = ''
    languages: list[tuple[str, int]] = field(default_factory=list[tuple[str, int]])
    code_files: int = 0
    files: int = 0
    structure: list[tuple[str, int]] = field(default_factory=list[tuple[str, int]])
    manifests: list[str] = field(default_factory=list[str])
    answers: list[tuple[str, str]] = field(default_factory=list[tuple[str, str]])

    @property
    def greenfield(self) -> bool:
        return self.code_files == 0


def start(args: list[str], folder: Path, say: Say) -> None:
    if args:
        raise Stop('start takes no words: run it in your project folder.', 'metaform start')
    folder = folder.resolve()
    enable(say)  # first, so a Metaform that cannot run the chain registers nothing
    project = register(folder, say)
    connect(folder, say)
    store = Store(project)
    mapped = store.has_intake() or bool(store.intake_bases())  # mapped in a metaform not active now, MCP-009
    recording = bool(store.intake_recording().results) or agent_at_work(folder, project)
    left = None if recording else next(iter(store.intake_building().results), None)  # no agent records it any more
    found = read_folder(folder) if not (mapped or recording or left) else None
    if found is not None:
        say(f'Read: {summary(found)}')
        ask(found, project, say)
    address = web(folder, project)
    opened = open_browser(address)
    say(f'Map: {address}' + ('' if opened else '  (open it in your browser)'))
    intake(folder, project, found, mapped, recording, say, left)


# Registration and modules ------------------------------------------------------------------

def register(folder: Path, say: Say) -> str:
    """The folder's project, registered under the folder's own name when it has none; a name another folder holds
    takes the next free number, so nothing is asked."""
    held = home.folder_project(folder)
    if held is not None:
        say(f'Project: {held}, already registered.')
        return held
    named = home.project_id_for(folder)
    chosen, number = named, 2
    while home.project(chosen) is not None:
        suffix = f'-{number}'
        chosen, number = named[:64 - len(suffix)] + suffix, number + 1
    try:
        home.add_project(chosen, folder)
    except StoreError as error:
        raise Stop(str(error), error.next_step) from None
    say(f'Project: {chosen}, registered for {folder}.')
    return chosen


def enable(say: Say) -> None:
    """Turn on the modules the chain runs that are off: dispatch ships off, and a person may have turned another off."""
    known = {item.id: item for item in loader.discover()}
    turned = [name for name in NEEDED if name in known and not known[name].enabled]
    for name in turned:
        loader.set_enabled(name, True)
    missing = [name for name in NEEDED if name not in known]
    if turned:
        say(f'Modules: turned on {", ".join(turned)}.')
    if missing:
        raise Stop(f'This Metaform has no {", ".join(missing)} module, which start needs.', 'metaform list modules')


def run_verb(identifier: str, verb_name: str, folder: Path, project: str, nouns: dict[str, Any] | None = None) -> Any:
    """One module verb, run as the CLI runs it, with its own Context."""
    found = loader.get(identifier)
    if found is None or found.module is None:
        raise Stop(f'Module {identifier} did not load: {found.problem if found else "not found"}.',
                   'metaform list modules')
    verb = next(verb for verb in found.module.verbs if verb.name == verb_name)
    return call(verb.run, context.build(identifier, folder, project=project, nouns=nouns or {}, sink=_line))


def _line(text: str) -> None:
    sys.stdout.write(text + '\n')


# The AI tool ---------------------------------------------------------------------------------

def found_tools() -> list[str]:
    """The AI tools found on this machine, by the catalogue `metaform install` detects them with."""
    from . import install
    return [name for name, tool in install.tools().items() if tool.verified and tool.detect()]


def server_entry(folder: Path) -> dict[str, Any] | None:
    """The stdio entry of Metaform's MCP server, in Claude Code's documented `.mcp.json` form: `metaform` itself when
    it is on PATH, the wheel through uvx when Metaform runs from one, else this Python."""
    from . import install
    command = install.server(folder)
    if command is None:
        return None
    if shutil.which('metaform'):
        words = command
    elif os.environ.get('METAFORM_WHEEL') and shutil.which('uvx'):
        words = install.entry(Path(os.environ['METAFORM_WHEEL']), command)
    else:
        words = [sys.executable, '-m', *command]
    return mcp_entry(words)


def mcp_entry(words: list[str]) -> dict[str, Any]:
    """The `.mcp.json` entry that runs these words as Metaform's MCP server, as start writes it and a build's README
    shows it, so both connect Claude Code the one same way."""
    return {'type': 'stdio', 'command': words[0], 'args': words[1:], 'env': {}}


def connect(folder: Path, say: Say) -> None:
    """Connect the person's AI tool to this project: Claude Code through the project's `.mcp.json`, written as
    `claude mcp add --scope project` writes it; any other tool is named with the command that sets it up."""
    from . import install
    tools = found_tools()
    if 'claude' in tools:
        if 'claude' in install._installed():  # pyright: ignore[reportPrivateUsage] - install's own record
            say('Claude Code: already connected in every folder by metaform install; nothing written.')
            return
        entry = server_entry(folder)
        if entry is None:
            say('Claude Code: not connected; no enabled module declares an MCP server.')
            return
        path = folder / '.mcp.json'
        if path.is_file() and _current(path) == entry:
            say(f'Claude Code: already connected through {path}.')
            return
        backups = home.home() / 'backups' / 'start' / datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')
        try:
            install._merge(path, entry, install._backup(path, backups))  # pyright: ignore[reportPrivateUsage]
        except Stop as stop:
            say(f'Claude Code: not connected. {stop} Next: {stop.next_step}')
            return
        say(f'Claude Code: wrote the metaform MCP server into {path}; Claude Code asks once to use it.')
        return
    if tools:
        say(f'AI tool: {tools[0]} found; connect it with metaform install {tools[0]}.')
        return
    say('AI tool: none found to connect, such as Claude Code, Codex or Gemini CLI.')
    say('  Install Claude Code, then run metaform start here again: it connects it to this project and starts the '
        'intake. The map works in the browser meanwhile.')


def _current(path: Path) -> Any:
    try:
        data: Any = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return None
    servers: Any = cast(dict[str, Any], data).get('mcpServers') if isinstance(data, dict) else None
    return cast(dict[str, Any], servers).get('metaform') if isinstance(servers, dict) else None


# What the files say ---------------------------------------------------------------------------

def read_folder(folder: Path) -> Read:
    """The project's name, what it is, its languages and its structure, from its files alone."""
    found = Read(name=folder.name)
    languages: Counter[str] = Counter()
    tops: Counter[str] = Counter()
    for path in _files(folder):
        found.files += 1
        language = LANGUAGES.get(path.suffix.lower())
        if language:
            languages[language] += 1
            found.code_files += 1
        relative = path.relative_to(folder).parts
        if len(relative) > 1:
            tops[relative[0] + '/'] += 1
    found.languages = languages.most_common(4)
    found.structure = tops.most_common(8)
    found.manifests = [name for name in MANIFESTS if (folder / name).is_file()]
    manifest, named, described = _manifest(folder)
    found.name = named or found.name
    for source, description in ((manifest, described), _readme(folder)):
        if description and not found.description:
            found.description, found.described_by = description, source
    return found


def _files(folder: Path) -> list[Path]:
    seen: list[Path] = []
    for root, folders, files in os.walk(folder):
        folders[:] = sorted(name for name in folders if not name.startswith('.') and name not in SKIPPED
                            and not name.endswith('.egg-info'))
        for name in sorted(files):
            if not name.startswith('.'):
                seen.append(Path(root) / name)
                if len(seen) >= MOST_FILES:
                    return seen
    return seen


def _manifest(folder: Path) -> tuple[str, str, str]:
    """The first manifest found of pyproject.toml, Cargo.toml and package.json, with the name and description it
    gives; empty text for what it leaves out."""
    tables: list[tuple[str, Any]] = []
    for name, section in (('pyproject.toml', 'project'), ('Cargo.toml', 'package')):
        try:
            tables.append((name, tomllib.loads((folder / name).read_text(encoding='utf-8')).get(section)))
        except (OSError, ValueError, UnicodeDecodeError):
            continue
    try:
        tables.append(('package.json', json.loads((folder / 'package.json').read_text(encoding='utf-8'))))
    except (OSError, ValueError, UnicodeDecodeError):
        pass
    for name, table in tables:
        if isinstance(table, dict):
            given = cast(dict[str, Any], table)
            named, described = given.get('name'), given.get('description')
            return (name, named.strip() if isinstance(named, str) else '',
                    described.strip() if isinstance(described, str) else '')
    return '', '', ''


def _readme(folder: Path) -> tuple[str, str]:
    """The README's first paragraph of prose: no heading, badge, image or markup, links kept as their words."""
    for name in READMES:
        try:
            text = (folder / name).read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        paragraph: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                if paragraph:
                    break
                continue
            if stripped.startswith(('#', '![', '[![', '<', '=', '-' * 3, '```', '|', '>')) or set(stripped) <= set('=-'):
                if paragraph:
                    break
                continue
            paragraph.append(stripped)
        said = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', ' '.join(paragraph)).replace('**', '').replace('`', '')
        if said:
            return name, said[:400]
    return '', ''


def summary(found: Read) -> str:
    """One line of what was read."""
    if found.greenfield:
        return f'no code yet ({counted(found.files, "file", "files")}), so the map records intent only.'
    languages = ' and '.join(name for name, _ in found.languages[:2])
    said = f'; {found.described_by} says what it is' if found.description else ''
    return f'{languages}, {counted(found.code_files, "code file", "code files")}{said}.'


def answers_path(project: str) -> Path:
    """Where the person's answers to start's questions are kept for the project until an intake uses them."""
    return home.home() / 'start' / f'{project}.json'


def kept_answers(project: str) -> list[tuple[str, str]]:
    try:
        given: Any = json.loads(answers_path(project).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    pairs = [cast(list[Any], pair) for pair in cast(list[Any], given) if isinstance(pair, list)] \
        if isinstance(given, list) else []
    return [(str(pair[0]), str(pair[1])) for pair in pairs if len(pair) == 2]


def ask(found: Read, project: str, say: Say) -> None:
    """What the files cannot say, at most two short questions, asked only of a person at a terminal: what the
    project is for when nothing says it, and, for a folder with no code, who it is for. An empty answer skips. An
    answer is kept for the project, so a start whose intake did not run never asks it again."""
    found.answers = kept_answers(project)
    if found.answers:
        say('Your answers: kept from the last metaform start here.')
    if not _interactive():
        return
    questions: list[tuple[str, str]] = []
    if not found.description:
        questions.append(('What it is for, in the person\'s words', 'What will this project be, in a sentence? '
                          if found.greenfield else 'What is this project for, in a sentence? '))
    if found.greenfield:
        questions.append(('Who it is for, in the person\'s words', 'Who is it for? '))
    answered = {label for label, _ in found.answers}
    for label, question in [one for one in questions[:2] if one[0] not in answered]:
        try:
            answer = input(question).strip()
        except EOFError:
            break
        if answer:
            found.answers.append((label, answer))
            home.mkdir_private(answers_path(project).parent)
            home.write_private(answers_path(project), json.dumps(found.answers, ensure_ascii=False))


def _interactive() -> bool:
    return sys.stdin.isatty() and os.environ.get('METAFORM_ROLE') in (None, '', 'none')


def brief(folder: Path, project: str, found: Read) -> str:
    """The intake agent's prompt: the target, and what the files said, from the chassis prompts."""
    lines = [f'- Name: {found.name}']
    if found.description:
        lines.append(f'- What it is, from {found.described_by}: {found.description}')
    lines += [f'- {label}: {answer}' for label, answer in found.answers]
    if found.languages:
        lines.append('- Languages: ' + ', '.join(f'{name} ({_files_of(number)})' for name, number in found.languages))
    if found.structure:
        lines.append('- Structure: ' + ', '.join(f'{name} ({_files_of(number)})' for name, number in found.structure))
    if found.manifests:
        lines.append('- Manifests: ' + ', '.join(found.manifests))
    name = 'start_intent' if found.greenfield else 'start_intake'
    return prompt_files.chassis(name, project=project, path=str(folder), found='\n'.join(lines))


def _files_of(number: int) -> str:
    return counted(number, 'file', 'files')


# The page and the intake -------------------------------------------------------------------------

def web(folder: Path, project: str) -> str:
    """The web GUI's address on this project, starting the GUI when it is not running."""
    started = cast(dict[str, Any], run_verb('web', 'start', folder, project))
    address = str(started['address'])
    return address.split('#', 1)[0] + '#p=' + project


def intake_agent(folder: Path) -> str | None:
    """The agent the intake starts with: the person's chosen default when they chose one, else the AI tool found
    here, else dispatch's own default."""
    if settings.state('dispatch_agent', folder) != 'default':
        return None
    return next((name for name in found_tools() if name in AGENT_TOOLS), None)


def agent_at_work(folder: Path, project: str) -> bool:
    """Whether an intake agent dispatch started is running in the project; it reads before it records, so the
    project can hold no intake layer yet while one works."""
    try:
        listed = cast(dict[str, Any], run_verb('dispatch', 'sessions', folder, project, {'thread': False}))
    except Stop:
        return False
    return any(str(row.get('work_id', '')).startswith('intake-') and row.get('state') == 'running'
               for row in cast(list[dict[str, Any]], listed.get('sessions') or []))


def intake(folder: Path, project: str, found: Read | None, mapped: bool, recording: bool, say: Say,
           left: Recording | None = None) -> None:
    """Start the intake agent with what the files said, unless the project is mapped, an intake is being recorded,
    or one was left unfinished, which is the person's to resume, finish or discard. With no AI tool here and no agent
    chosen, none is started, so nothing is fetched for one. It says the agent is mapping only once the agent has made
    its session; an agent that does not start is said with why and its next step. The page is open already."""
    if mapped:
        say('Intake: the map is recorded; opening it.')
        return
    if recording:
        say('Intake: being recorded; the page follows it.')
        return
    if left is not None:
        say(f'Intake: left unfinished in layer {left.layer.name} of base {left.base}, with {left.parts} parts, and no '
            'agent is recording it. The page offers Resume, Finish and Discard; or: '
            'metaform dispatch intake resume=true')
        return
    assert found is not None
    agent = intake_agent(folder)
    kept = '; your answers are kept for it' if found.answers else ''
    if agent is None and settings.state('dispatch_agent', folder) == 'default':
        say(f'Intake: not started; no AI tool here can run it{kept}.')
        say('  Install Claude Code, then run metaform start here again; the page shows the project meanwhile.')
        return
    nouns: dict[str, Any] = {'text': brief(folder, project, found), 'wait': True, **({'agent': agent} if agent else {})}
    say(f'Intake: starting {agent or settings.value("dispatch_agent", folder)}; a first start may take a minute.')
    try:
        started = cast(dict[str, Any], run_verb('dispatch', 'intake', folder, project, nouns))
    except Stop as stop:
        if 'already at work' in str(stop) or 'is starting' in str(stop):
            say('Intake: an agent is already mapping the project; the page follows it.')
            return
        say(f'Intake: not started{kept}. {stop} Next: {stop.next_step}')
        return
    if started.get('state') == 'running':
        say(f'Intake: {started["agent"]} is mapping the project; the page shows each part as it is recorded.')
        return
    reason = str(started.get('reason') or 'its runner ended').removeprefix('it did not start: ')
    login = f'metaform dispatch login {started["agent"]}'
    step = login if 'login' in reason else f'read {started.get("log")}, then run metaform start here again'
    say(f'Intake: {started["agent"]} did not start{kept}: {reason}')
    say(f'  Next: {step}')


def open_browser(address: str) -> bool:
    """Open the page once, in a browser window of the person's desktop. Nothing opens without a desktop, in an
    agent's run, under WSL, or where the only browser found would take over this terminal."""
    if os.environ.get('METAFORM_ROLE') not in (None, '', 'none'):
        return False
    if wsl():
        return False  # a WSLg window, not the person's Windows browser; interop may be off, so print the address
    if sys.platform not in ('win32', 'darwin') and not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        return False
    try:
        browser = webbrowser.get()
    except webbrowser.Error:
        return False
    if isinstance(browser, webbrowser.GenericBrowser) and not isinstance(browser, webbrowser.BackgroundBrowser):
        return False  # a terminal browser, such as lynx, would hold this terminal
    try:
        return bool(browser.open(address))
    except OSError:
        return False


def wsl() -> bool:
    """Running inside WSL, where a Linux browser would open in a WSL window instead of the person's Windows browser,
    and Windows programs may not run at all (interop off)."""
    if sys.platform != 'linux':
        return False
    if os.environ.get('WSL_DISTRO_NAME') or os.environ.get('WSL_INTEROP'):
        return True
    try:
        return 'microsoft' in Path('/proc/sys/kernel/osrelease').read_text().lower()
    except OSError:
        return False
