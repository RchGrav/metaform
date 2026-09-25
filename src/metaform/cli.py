"""The metaform command: verbs, the nouns they act on, and switches that change how they run."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import asyncio

from . import __version__, context, docs, grammar, home, loader, results, settings
from .docs import Command, Switch
from .module import Context, call


from .module import Stop


def out(text: str = '') -> None:
    sys.stdout.write(text if text.endswith('\n') else text + '\n')


def _fmt(value) -> str:
    if isinstance(value, bool):
        return 'on' if value else 'off'
    if value is None:
        return 'none'
    if isinstance(value, list):
        return ','.join(value) if value else 'all'
    return str(value)


# Commands ---------------------------------------------------------------

def status(args, folder):
    if args:
        raise Stop(f'Unknown command: {args[0]}.', 'metaform help commands')
    project = settings.value('project', folder)
    registered = {record.project_id: record.path for record in home.projects()}
    out(f'Metaform {__version__}')
    out(f'Home: {home.home()}')
    out(f'Folder: {folder}')
    if project is None:
        out('Project: none')
        out('  Register one: metaform add project <id> <path>')
    else:
        where = registered.get(project)
        chosen = settings.state('project', folder) != 'default'
        out(f'Project: {project} ({where})' + (' [selected here]' if chosen else ''))
    out(f'Projects: {len(registered)} registered')
    found = loader.discover()
    loaded = [item.id for item in found if item.module is not None]
    broken = [item.id for item in found if item.enabled and item.problem]
    line = f'Modules: {len(loaded)} on'
    if broken:
        line += f", {len(broken)} not loaded (metaform list modules)"
    out(line)
    groups = settings.value('commands', folder)
    if groups:
        out('Commands: ' + ', '.join(groups))
    for line in status_lines(folder, project):
        out(line)


def status_lines(folder: Path, project: str | None) -> list[str]:
    """Each surfaced module's status hook, in module id order; the chassis names no module, BASE-035."""
    from .module import Status
    lines: list[str] = []
    for module in sorted(loader.enabled(), key=lambda item: item.id):
        if module.status is None or not shown(module.id, folder):
            continue
        try:
            ctx = context.build(module.id, folder, project=project, resolve=False)
            got = call(module.status, ctx)
        except Exception as error:  # A failing hook is one line and nothing else.
            lines.append(f'{module.id}: status failed: {type(error).__name__}: {error}')
            continue
        if isinstance(got, Status):
            lines.extend(got.lines)
            if got.notice:
                lines.append('  ' + got.notice)
    return lines


def add(args, folder):
    if len(args) != 3 or args[0] != 'project':
        raise Stop('add needs: project <id> <path>.', 'metaform add project <id> <path>')
    _, identifier, path = args
    target = (folder / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    out(home.add_project(identifier, target))


def list_(args, folder):
    if args == ['modules']:
        found = loader.discover()
        width = max((len(item.id) for item in found), default=6)
        for item in found:
            state = 'on' if item.enabled and not item.problem else ('off' if not item.enabled else 'error')
            line = f'{item.id:<{width}}  {state:<5}  {item.place:<6}  '
            line += item.problem if item.problem else (item.module.summary if item.module else '')
            out(line.rstrip())
        return
    if args != ['projects']:
        raise Stop('list needs a noun: projects or modules.', 'metaform list projects')
    registered = {record.project_id: record.path for record in home.projects()}
    if not registered:
        out('No projects yet. Register one: metaform add project <id> <path>')
        return
    width = max(len(identifier) for identifier in registered)
    for identifier, path in registered.items():
        out(f'{identifier:<{width}}  {path}')


def _toggle(args, on):
    verb = 'enable' if on else 'disable'
    if len(args) != 1:
        raise Stop(f'{verb} needs one module id.', f'metaform {verb} <module>')
    identifier = args[0]
    known = {item.id for item in loader.discover()}
    if identifier not in known:
        raise Stop(f'No module {identifier}.', 'metaform list modules')
    loader.set_enabled(identifier, on)
    out(f"Module {identifier}: {'on' if on else 'off'}")


def enable(args, folder):
    _toggle(args, True)


def disable(args, folder):
    _toggle(args, False)


def _setting_for(switch: str) -> tuple[settings.Setting, bool]:
    found = settings.by_switch(switch)
    if found is None:
        raise Stop(f'{switch} is not a setting.', 'metaform help switches')
    return found


def set_(args, folder):
    glue = quiet = False
    pairs = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == '--glue':
            glue = True
        elif arg in ('-q', '--quiet'):
            quiet = True
        elif arg.startswith('--'):
            name, equals, inline = arg.partition('=')
            if name == '--confirm':
                raise Stop('--confirm is not a setting.', 'metaform help --confirm')
            setting, negative = _setting_for(name)
            if setting.kind == 'bool':
                if equals:
                    raise Stop(f'{name} takes no value.', f'metaform help {setting.switch}')
                raw = not negative
            elif equals:
                raw = inline
            else:
                if index + 1 == len(args):
                    raise Stop(f'{name} needs a value.', f'metaform set {name} <value>')
                index += 1
                raw = args[index]
            pairs.append((setting, raw))
        else:
            raise Stop(f'set takes switches, not {arg!r}.', 'metaform set --help')
        index += 1
    changes, glued = [], []
    for setting, raw in pairs:
        try:
            old, new = settings.assign(setting.key, raw, folder, glue=glue)
        except settings.SettingError as error:
            nxt = 'metaform list projects' if setting.key == 'project' else f'metaform help {setting.switch}'
            raise Stop(str(error), error.next_step or nxt) from None
        if old != new:
            changes.append((setting.key, old, new))
        if glue:
            glued.append(setting.key)
    if quiet:
        return
    if not changes:
        out('Success: no changes')
    else:
        out(f'Success: updated {len(changes)} key' + ('s' if len(changes) != 1 else ''))
        for key, old, new in changes:
            out(f'  {key}: {_fmt(old)} → {_fmt(new)}')
    if glued:
        out('  glued: ' + ', '.join(glued))
    if any(key == 'commands' for key, _, _ in changes) and settings.value('commands', folder):
        shown = ', '.join(settings.value('commands', folder))
        out(f'Commands shown here: {shown}.')
        out('All other commands and help, including yours, are now hidden and will not run.')
        out('To restore them: metaform unset --commands')


def unset(args, folder):
    unglue = quiet = everything = False
    keys = []
    for arg in args:
        if arg == 'all':
            everything = True
        elif arg == '--unglue':
            unglue = True
        elif arg in ('-q', '--quiet'):
            quiet = True
        elif arg == '--all':
            raise Stop('--all is not a setting. A switch names one setting.', 'metaform unset all')
        elif arg.startswith('--'):
            keys.append(_setting_for(arg)[0].key)
        else:
            raise Stop(f'unset takes switches or all, not {arg!r}.', 'metaform unset --help')
    if everything:
        keys = list(settings.SCHEMA)
    results = {key: settings.reset(key, folder, unglue=unglue) for key in keys}
    if quiet:
        return
    reset = sorted(key for key, (result, _) in results.items() if result == 'reset')
    skipped = sorted(key for key, (result, _) in results.items() if result == 'skipped')
    unglued = sorted(key for key, (_, was) in results.items() if was)
    if reset:
        out(f'Reset {len(reset)} setting(s): ' + ', '.join(reset))
    else:
        out('No settings required reset')
    if skipped:
        out('Skipped (glued): ' + ', '.join(skipped))
    if unglued:
        out('Unglued: ' + ', '.join(unglued))


def config(args, folder):
    show = '--show' in args
    as_json = '--json' in args
    unknown = [arg for arg in args if arg not in ('--show', '--json')]
    if unknown:
        raise Stop(f'config does not take {unknown[0]}.', 'metaform config --help')
    rows = settings.describe(folder)
    if not show:
        from . import tui
        if tui.available():
            return tui.run(folder)
    if as_json:
        out(json.dumps(rows, indent=2, default=str))
        return
    for row in rows:
        mark = '*' if row['state'] == 'glued' else ' '
        note = '' if row['state'] == 'default' else f"  ({row['state']})"
        out(f"{mark} {row['key']}: {_fmt(row['value'])}{note}")
    out('')
    out('* glued: kept by unset all until unglued.')


def help_(args, folder):
    if not args:
        out(docs.overview())
    elif args == ['intro']:
        out(docs.INTRO)
    elif args == ['commands']:
        out(docs.commands_index(lambda group: shown(group, folder)))
    elif args == ['switches']:
        out(docs.switches_index())
    elif len(args) == 1 and args[0].startswith('--'):
        if not docs.known_switch(args[0]):
            raise Stop(f'No switch {args[0]}.', 'metaform help switches')
        out(docs.switch_page(args[0]))
    elif len(args) == 1 and args[0] in docs.COMMANDS:
        out(docs.page(args[0]))
    elif args and _module(args[0], folder, quiet=True):
        found = _module(args[0], folder)
        if len(args) == 1:
            out(docs.module_page(found.module))
        elif len(args) == 2 and (verb := _verb(found, args[1])):
            out(docs.verb_page(found.module, verb))
        else:
            raise Stop(f'No verb {args[1]} in {args[0]}.', f'metaform help {args[0]}')
    else:
        raise Stop(f'No help topic {" ".join(args)}.', 'metaform help commands')


def mcp(args, folder):
    if args:
        raise Stop('mcp takes no words.', 'metaform mcp')
    from . import mcp_server
    mcp_server.serve(folder)


VERBS = {'help': help_, 'add': add, 'list': list_, 'set': set_, 'unset': unset, 'config': config,
         'enable': enable, 'disable': disable, 'mcp': mcp}
ALWAYS = {'help', 'set', 'unset', 'config', 'mcp'}


def shown(group: str, folder: Path) -> bool:
    """Whether a command group is on this folder's surface. Empty means every group."""
    groups = settings.value('commands', folder)
    return not groups or group in groups


def _module(identifier, folder, quiet=False):
    found = loader.get(identifier)
    if found is None:
        if quiet:
            return None
        raise Stop(f'Unknown command: {identifier}.', 'metaform help commands')
    if not found.enabled:
        if quiet:
            return None
        raise Stop(f'Module {identifier} is off.', f'metaform enable {identifier}')
    if found.problem or found.module is None:
        if quiet:
            return None
        raise Stop(f'Module {identifier} did not load: {found.problem}', 'metaform list modules')
    if not shown(identifier, folder):
        if quiet:
            return None
        raise Stop(f'{identifier} is not on this folder\'s command surface.', 'metaform unset --commands')
    return found


def _verb(found, name):
    return next((verb for verb in found.module.verbs if verb.name == name), None)


def verb_on_this_system(module_id: str, verb) -> bool:
    from .module_metadata import current_os
    return verb.supported_os is None or current_os() in verb.supported_os


def run_module(identifier, rest, folder):
    found = _module(identifier, folder)
    if not rest or rest[0] in ('-h', '--help'):
        out(docs.module_syntax(found.module))
        return
    verb = _verb(found, rest[0])
    if verb is None or 'cli' not in verb.surfaces:
        raise Stop(f'{identifier} has no verb {rest[0]}.', f'metaform help {identifier}')
    if not verb_on_this_system(identifier, verb):
        raise Stop(f'{identifier} {verb.name} runs on {", ".join(verb.supported_os)}.', f'metaform help {identifier}')
    parsed = grammar.parse(identifier, verb, rest[1:])
    if parsed.help:
        out(docs.verb_syntax(found.module, verb))
        return
    if verb.caution and not parsed.confirm:
        confirm = ' '.join(['metaform', identifier, verb.name, *rest[1:], '--confirm'])
        raise Stop(verb.caution, f'If you are sure: {confirm}')
    messages = sys.stderr if parsed.json else sys.stdout
    ctx = context.build(identifier, folder, nouns=parsed.nouns, switches=parsed.switches,
                        sink=lambda text: messages.write(text + '\n'))
    result = call(verb.run, ctx)
    if result is None:
        return
    if isinstance(result, str):
        sys.stdout.write(result)
    elif parsed.json:
        sys.stdout.write(results.as_json(result) + '\n')
    else:
        sys.stdout.write(results.as_text(result))


# Help records -------------------------------------------------------------

docs.command(Command('help', 'Show an overview, an index, or the page for one command or switch.',
                     ('metaform help', 'metaform help intro', 'metaform help commands',
                      'metaform help switches', 'metaform help <command|switch>'),
                     details='Each command also takes --help, which shows only its syntax.',
                     see_also=('intro',)))
docs.command(Command('add', 'Register a project.', ('metaform add project <id> <path>',),
                     description='Registers a folder as a project. Metaform keeps its data in the home, '
                                 'not in the folder.',
                     details='Running metaform inside the folder, or any folder below it, works on this project.',
                     examples=(('metaform add project mgm ~/mgm-main', 'Register the MGM repository as mgm.'),),
                     see_also=('list', 'set')))
docs.command(Command('list', 'List registered projects or modules.',
                     ('metaform list projects', 'metaform list modules'),
                     details='list modules shows each module, whether it is on, where it was found, '
                             'and why it did not load when it did not.',
                     see_also=('add', 'enable', 'disable')))
docs.command(Command('mcp', "Serve this folder's module verbs as MCP tools, over stdio.",
                     ('metaform mcp',),
                     description='A harness launches this. Each module verb on the folder\'s command surface becomes '
                                 'a tool named <module>_<verb>, and the instructions carry each module\'s purpose.',
                     details='Add it to Claude Code with: claude mcp add metaform -- metaform mcp. '
                             'It serves the project of the folder it starts in.',
                     see_also=('set', 'help')))
docs.command(Command('enable', 'Turn a module on.', ('metaform enable module <id>',), see_also=('disable', 'list')))
docs.command(Command('disable', 'Turn a module off. Its settings keep their saved values.',
                     ('metaform disable module <id>',), see_also=('enable', 'list')))
docs.command(Command('set', 'Save settings. Each setting is a switch.',
                     ('metaform set --<setting> <value> [--glue] [--quiet]',),
                     switches=(('--glue', 'Keep these settings through unset all.'),
                               ('--quiet', 'Apply without printing.')),
                     description='Saves one or more settings. Folder settings apply to the folder you run it in.',
                     details='Out of the box every setting is at its default, and the defaults work. '
                             'A glued setting keeps its value when you run unset all.',
                     examples=(('metaform set --project mgm', 'Work on mgm from this folder.'),
                               ('metaform set --project mgm --glue', 'Same, and keep it through unset all.')),
                     see_also=('unset', 'config')))
docs.command(Command('unset', 'Return settings to their defaults.',
                     ('metaform unset --<setting> [--unglue] [--quiet]', 'metaform unset all [--unglue]'),
                     switches=(('--unglue', 'Also reset glued settings, and unglue them.'),
                               ('--quiet', 'Apply without printing.')),
                     details='unset all resets every setting except glued ones. Add --unglue to reset those too.',
                     examples=(('metaform unset --project', "Return this folder to its own project."),
                               ('metaform unset all --unglue', 'Reset everything, glued settings included.')),
                     see_also=('set', 'config')))
docs.command(Command('config', 'Open the settings screen, or print the settings.',
                     ('metaform config', 'metaform config --show [--json]'),
                     switches=(('--show', 'Print the settings instead of opening the screen.'),
                               ('--json', 'With --show, print JSON.')),
                     details='Each setting shows its value and its state: default, set, or glued.',
                     see_also=('set', 'unset')))
docs.switch(Switch('--glue', 'Keep the settings you set through unset all.',
                   'A glued setting is skipped by unset all until you unset it with --unglue.', ('set',)))
docs.switch(Switch('--unglue', 'Reset glued settings too, and unglue them.', used_by=('unset',)))
docs.switch(Switch('--quiet', 'Apply the change without printing.', used_by=('set', 'unset')))
docs.switch(Switch('--show', 'Print the settings instead of opening the settings screen.', used_by=('config',)))
docs.switch(Switch('--json', 'Print machine-readable JSON.', used_by=('config',)))


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    folder = Path.cwd()
    try:
        loader.discover()
        if not args:
            status(args, folder)
            return 0
        verb, rest = args[0], args[1:]
        if verb in ('-h', '--help'):
            out(docs.overview())
            return 0
        if verb not in VERBS:
            run_module(verb, rest, folder)
            return 0
        if verb not in ALWAYS and not shown('chassis', folder):
            raise Stop(f'{verb} is not on this folder\'s command surface.', 'metaform unset --commands')
        if '-h' in rest or '--help' in rest:
            out(docs.syntax(verb))
            return 0
        VERBS[verb](rest, folder)
        return 0
    except Stop as stop:
        sys.stderr.write(f'Error: {stop}\n')
        sys.stderr.write(f'Next: {stop.next_step}\n')
        return 2
    except asyncio.CancelledError:
        sys.stderr.write('Cancelled.\n')
        return 3
    except KeyboardInterrupt:
        sys.stderr.write('Interrupted.\n')
        return 130
    except Exception as error:  # Unexpected: one Error and one Next line, exit 1, BASE-031 and CLI-009.
        sys.stderr.write(f'Error: {type(error).__name__}: {error}\n')
        sys.stderr.write(f'Next: {"metaform list modules" if args and args[0] not in VERBS else "metaform help"}\n')
        return 1
