"""The README a build's zip carries for a tester who has never seen Metaform, BASE-060.

It is made at build time from the code, so it never drifts from what the wheel does: the version and the Python
requirement from `_build_info`, which copies `pyproject.toml`; the modules the wheel carries, with their summaries; the
chassis commands from their help records in `docs`; the MCP server command from the carried module that declares one,
in the `.mcp.json` entry `metaform start` writes; the Node.js the agents need from dispatch's `NODE`; uv's install
lines from the installer; the web GUI's port from its setting. `metaform demo` and `metaform start` are named only when
the wheel carries every module they run. A command the README relies on that is no longer declared stops the build,
so a renamed command can never leave a README naming the old one.
"""
from __future__ import annotations

import ast
import importlib
import json
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from . import __version__, _build_info, docs, settings
from .errors import Stop

if TYPE_CHECKING:
    from . import loader

# Rich's own words, kept exactly as he wrote them; they open every README a build writes.
WELCOME = ("Thanks for helping test our code. We ask that you do not distribute this software yet. If you would like "
           "to have access to our repository, send us your GitHub name, and you can file tickets with us. Please do "
           "not distribute this code to others. We appreciate all your help. Here's how to set up our code. It's "
           "really easy.")
DISCORD = 'Message us on Discord: `rchgrav` (Discord username).'


def _cli() -> Any:
    """The CLI module, where the chassis commands' help records and the version line are declared."""
    return importlib.import_module(f'{__package__}.cli')


def _command(name: str) -> docs.Command:
    """A chassis command's help record; the README is not written around a command that is gone."""
    _cli()
    record = docs.COMMANDS.get(name)
    if record is None:
        raise Stop(f'The README names metaform {name}, which is no longer a command.', 'update metaform/build_readme.py')
    return record


def _usage(name: str, starts: str) -> str:
    """The usage line of a chassis command that starts with these words."""
    for line in _command(name).usage:
        if line.startswith(starts):
            return line
    raise Stop(f'metaform {name} has no usage starting {starts}.', 'update metaform/build_readme.py')


def _summary(item: loader.Found) -> str:
    if item.module is not None:
        return item.module.summary or ''
    return (item.declared.summary if item.declared is not None else None) or ''


def mcp_server(carried: Sequence[loader.Found]) -> list[str] | None:
    """The command that starts the MCP server of a carried module that declares one, as `metaform install` starts it:
    read from the loaded module, or from its `mcp_server=` literal when it is off at home."""
    for item in sorted(carried, key=lambda found: found.id):
        verb = item.module.mcp_server if item.module is not None else None
        if verb is None:
            try:
                tree = ast.parse((item.path / '__init__.py').read_text(encoding='utf-8'))
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            verb = next((node.value.value for node in ast.walk(tree)
                         if isinstance(node, ast.keyword) and node.arg == 'mcp_server'
                         and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)), None)
        if verb is not None:
            return ['metaform', item.id, verb]
    return None


def _literal(carried: Sequence[loader.Found], identifier: str, name: str) -> str | None:
    """A text constant a carried module assigns at its top level, read from its `__init__.py`, so a module off at home
    is read without being loaded."""
    item = next((found for found in carried if found.id == identifier), None)
    if item is None:
        return None
    try:
        tree = ast.parse((item.path / '__init__.py').read_text(encoding='utf-8'))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None
    return next((node.value.value for node in tree.body
                 if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name
                                                         for target in node.targets)
                 and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)), None)


def _web_port() -> tuple[str, int]:
    """The web GUI's port switch and default, from its setting when the web module has declared it."""
    setting = settings.SCHEMA.get('web_port')
    if setting is None:
        return '--web-port', 7433
    return setting.switches[0] if setting.switches else '--web-port', int(setting.default)


def readme(kind: str, wheel: str, carried: Sequence[loader.Found], project: str | None = None,
           prompt: bool = False) -> str:
    """The README.md of an installer, full or project build's zip."""
    from . import build, install, start
    needs = _build_info.REQUIRES_PYTHON.removeprefix('>=')
    folder = f'{wheel.removesuffix("-py3-none-any.whl")}-{kind}'
    ids = {item.id for item in carried}
    onboarding = build.carries_onboarding(ids)  # demo and start run only with every module they need carried
    node = _literal(carried, 'dispatch', 'NODE')
    server = mcp_server(carried)
    uv_posix, uv_windows = install.UV_INSTALL_POSIX, install.UV_INSTALL['windows']
    register = _usage('add', 'metaform add project')
    example, _ = _command('add').examples[0]
    feedback = _usage('feedback', 'metaform feedback')
    port_switch, port = _web_port()
    lines: list[str] = []
    add = lines.append

    def block(*commands: str, language: str = '') -> None:
        add(f'```{language}')
        lines.extend(commands)
        add('```')
        add('')

    add(f'# Metaform {__version__}: a guide for testers')
    add('')
    add(WELCOME)
    add('')
    add(DISCORD)
    add('')
    add('## What Metaform is')
    add('')
    add("Metaform keeps a functional map of a software project: its parts, what each one is for, and which parts serve "
        'which. Your AI coding tool reads that map through Metaform\'s MCP server before it changes anything, so it '
        'starts from the project\'s purpose instead of guessing. You can watch the map, and the agents working on it, '
        'in a web page on your own machine.')
    add('')
    add('## What this zip holds')
    add('')
    add(f'- `{wheel}`: Metaform {__version__}, the {kind} build. It carries these modules:')
    for item in sorted(carried, key=lambda found: found.id):
        summary = _summary(item)
        add(f'  - `{item.id}`' + (f': {summary}' if summary else ''))
    if not carried:
        add('  - none; the chassis alone')
    if project is not None:
        add(f'  It also carries the project `{project}`, for an agent working on a remote system. See "The remote '
            'agent round trip" below.')
    if prompt:
        add('- `prompt.md`: the prompt to give that remote agent with the wheel.')
    add('- `README.md`: this guide.')
    add('')
    add('## What you need first')
    add('')
    add(f'- Python {needs} or newer. You need not install it yourself: uv fetches a suitable Python when it installs '
        'Metaform, even where the system Python is older.')
    add('- uv, the Python package manager from Astral. Install it with one line:')
    add(f'  - Linux and macOS: `{uv_posix}`')
    add(f'  - Windows, in PowerShell: `{uv_windows}`')
    add('  Then open a new terminal so `uv` is on your PATH.')
    if node is not None:
        add(f'- Node.js {node} or newer, with npm: the agents Metaform starts, the intake that `metaform start` runs '
            'among them, run their AI tool\'s adapter with `npx`. The demo\'s agents are scripted and need no Node.js.')
    add('- An AI coding tool that speaks MCP, such as Claude Code (`claude`). The steps below give the exact setup '
        'for Claude Code.')
    add('')
    add('The commands below are the same on Linux, macOS and Windows unless a step says otherwise. On Windows, type '
        'them in PowerShell.')
    add('')
    add('## Set it up')
    add('')
    add('### 1. Unzip')
    add('')
    add('Linux and macOS:')
    add('')
    block(f'unzip {folder}.zip', f'cd {folder}', language='sh')
    add('Windows, in PowerShell:')
    add('')
    block(f'Expand-Archive {folder}.zip -DestinationPath .', f'cd {folder}', language='powershell')
    add('### 2. Install')
    add('')
    block(f'uv tool install ./{wheel}')
    add('If your shell then says `metaform` is not found, open a new terminal, or run `uv tool update-shell` and '
        'then open a new terminal.')
    add('')
    add(f'If you already have Python {needs} or newer and prefer pip, this works too: make a virtual environment, '
        f'activate it, and run `pip install ./{wheel}`. Running the wheel directly with an older Python stops with '
        f'"Metaform needs Python {needs} or newer".')
    add('')
    add('### 3. Check the install')
    add('')
    block('metaform --version')
    add(f'It prints `{_cli().VERSION}`. Then:')
    add('')
    block('metaform list modules')
    add('lists the modules this build carries, each `on` or `off`.')
    add('')
    provision = _usage('provision', 'metaform provision <').split('<')[0] + 'claude'
    if server is not None:
        add('When an AI tool Metaform has not set up yet connects to its MCP server, the agent there is told once that '
            'this is Metaform\'s first run and how to provision it. It is safe to leave for now. '
            f'`{provision}` gives Claude Code Metaform\'s skill and reminders, showing each change and backing up '
            f'each file first; `{_usage("provision", "metaform provision done")}` then stops the notice. '
            '`metaform help provision` says what each part does.')
        add('')
    step = 4
    if onboarding:
        add(f'### {step}. See it working')
        add('')
        block(_command('demo').usage[0])
        add(_command('demo').summary + ' Run it first: it needs no project of your own.')
        add('')
        step += 1
        add(f'Run in your own project folder, `metaform start` does what the next steps do in one go. '
            f'{_command("start").summary} The steps below do the same by hand, so you can check each one.')
        add('')
    add(f'### {step}. Register a project folder')
    add('')
    add('Pick a small project of your own, a folder of code or documents. Metaform keeps its map in its home folder. '
        'In the project it writes only `.mcp.json`, when it connects Claude Code there, and a report zip, when you '
        'make one there. In a terminal, go to the project folder and register it with a short id '
        f'of your choosing. The command is `{register}`; for example `{example}` registers the folder `~/notes` as '
        'the project `notes`. From inside the folder:')
    add('')
    block('metaform add project myproject .', 'metaform list projects')
    add('`metaform list projects` shows `myproject` with its folder.')
    add('')
    step += 1
    add(f'### {step}. Connect Claude Code to Metaform\'s MCP server')
    add('')
    if server is None:
        add('This build carries no module that serves MCP, so there is nothing to connect. Your AI tool can still '
            'run `metaform` commands in a terminal; `metaform help` lists them.')
        add('')
    else:
        add('Claude Code connects to Metaform through `.mcp.json` in the project folder'
            + (', which `metaform start` writes for you when it finds `claude`. By hand, save' if onboarding
               else '. Save') + ' this as `.mcp.json` there:')
        add('')
        block(json.dumps({'mcpServers': {'metaform': start.mcp_entry(server)}}, indent=2), language='json')
        add('Start `claude` in the project folder: it asks you once to approve the `metaform` server. Then type '
            '`/mcp`: `metaform` is listed as connected. Another MCP tool takes the same server command: '
            f'`{" ".join(server)}`, run in the project folder.')
        add('')
    step += 1
    if 'intake' in ids:
        add(f'### {step}. Run an intake')
        add('')
        add('An intake is the first pass that maps the project: the agent reads it and records each part and what it '
            'is for. In Claude Code, in the project folder, ask:')
        add('')
        add('> Use Metaform to run an intake of this project.')
        add('')
        add('The agent reads the intake procedure, starts the intake, records the elements and the purposes they '
            'serve, and finishes it. You can start one from the terminal too; the agent then carries it on:')
        add('')
        block('metaform intake start', 'metaform intake status')
        add('`metaform intake status` says whether the project has an intake and whether one is being recorded.')
        add('')
        step += 1
    if 'web' in ids:
        add(f'### {step}. Open the web GUI')
        add('')
        block('metaform web start')
        add(f'It prints the address, `http://127.0.0.1:{port}` unless you chose another port. Open it in your '
            'browser. You see your registered projects; choose yours to see its map, the parts the intake recorded '
            'and the joins between the parts that receive and the parts that provide. While an agent works, the page '
            'follows it live.')
        add('')
        add(f'If port {port} is taken on your machine, choose another before starting it, for example '
            f'`metaform set {port_switch} 7500`. Stop the web GUI with `metaform web stop`.')
        add('')
    add('## What to try')
    add('')
    checks: list[tuple[str, str]] = []
    if onboarding:
        checks.append(('`metaform demo`', 'It runs with no questions and shows Metaform at work.'))
    checks.append(('`metaform list projects` after registering', 'Your project is listed with its folder.'))
    if server is not None:
        checks.append(('`/mcp` in Claude Code', '`metaform` is connected and its tools are listed.'))
    if 'intake' in ids:
        checks.append(('Ask the agent for an intake', ('It records elements and purposes and finishes; '
                                                       '`metaform intake status` then says the project has an intake.')))
    if 'web' in ids:
        checks.append(('`metaform web start` and open the address',
                       "The project's map is drawn and changes as the agent works."))
    if 'map' in ids and server is not None:
        checks.append(('Ask the agent what Metaform knows about one part of the project',
                       'It reads that part from the map by its address and answers from it.'))
    for number, (action, expect) in enumerate(checks, 1):
        add(f'{number}. {action}. {expect}')
    add('')
    add('## Report what you found')
    add('')
    add('Tell us what you tried, what you expected and what happened, with the output of the command. Include your '
        'system, Linux, macOS or Windows, and what `metaform --version` prints.')
    add('')
    if 'report' in docs.COMMANDS:
        report = _command('report')
        add(f'- `{_usage("report", "metaform report <")}` {report.description[0].lower()}{report.description[1:]} '
            'It sends nothing; you send the file.')
    add(f'- Save it in Metaform: `{feedback}`. `metaform list reports` lists what you saved.')
    add('- Logs: Metaform keeps everything in its home folder, `~/.metaform` on Linux and macOS and '
        '`%USERPROFILE%\\.metaform` on Windows, or the folder `METAFORM_HOME` names. The web GUI writes its log to '
        '`run/web.log` there.')
    add('- Send it to us on Discord, `rchgrav`, with the log attached, or file a ticket on our repository once you '
        'have access.')
    add('')
    if project is not None:
        add('## The remote agent round trip')
        add('')
        add(f'This wheel carries the project `{project}` for an agent on a hosted system that can take an upload, a '
            'chat message and a download, with no install and no MCP.')
        add('')
        add(f'1. Upload `{wheel}` to the agent' + (' and give it the text of `prompt.md` as its message.'
                                                   if prompt else '.'))
        add(f'2. The agent runs `python {wheel}` with nothing after it. The first run unpacks the project into a '
            'Metaform home and registers it at the current folder, opens a working layer for the agent\'s changes to '
            'the map, and prints the prompt, the instructions and where the map starts. A second run prints the same '
            'and imports nothing.')
        add(f'3. When the work is done, the agent runs `{_usage("return", "python")}`'.replace('<project wheel>', wheel)
            + '. It writes one return archive, `<project>-return-<time>.zip`, holding the working layer, the changes '
              'to the project\'s files and the note, and the agent offers it as a download.')
        add(f'4. Download that archive and send it back to us. We add it with `{_usage("import", "metaform import")}`, '
            'which adds the agent\'s work as a new layer and never overwrites the map.')
        add('')
    add('## Uninstall')
    add('')
    add('Remove each piece in this order.')
    add('')
    if 'web' in ids:
        block('metaform web stop')
    if server is not None:
        add('Delete `.mcp.json` from the project folder, or only its `metaform` entry when it holds other servers.')
        add('')
    add('Remove Metaform itself:')
    add('')
    block('uv tool uninstall metaform')
    add('Delete the home folder. It holds every map and setting Metaform made, so this cannot be undone.')
    add('')
    add('Linux and macOS:')
    add('')
    block('rm -rf ~/.metaform', language='sh')
    add('Windows, in PowerShell:')
    add('')
    block('Remove-Item -Recurse -Force "$HOME\\.metaform"', language='powershell')
    add('In your project folder Metaform wrote only `.mcp.json` and any report zip you made there.')
    return '\n'.join(lines).rstrip() + '\n'
