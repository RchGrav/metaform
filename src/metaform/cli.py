"""The metaform command: verbs, the nouns they act on, and switches that change how they run."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import __version__, docs, home, settings
from .docs import Command, Switch


class Stop(Exception):
    """A user error. It says what happened and the one command to run next."""

    def __init__(self, message: str, next_step: str | None = None):
        super().__init__(message)
        self.next_step = next_step


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
    registered = home.projects()
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


def add(args, folder):
    if len(args) != 3 or args[0] != 'project':
        raise Stop('add needs: project <id> <path>.', 'metaform add project <id> <path>')
    _, identifier, path = args
    target = (folder / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    if not target.is_dir():
        raise Stop(f'No folder at {target}.', f'metaform add project {identifier} <existing folder>')
    home.add_project(identifier, target)
    out(f'Added project {identifier}: {target}')


def list_(args, folder):
    if args != ['projects']:
        raise Stop('list needs a noun: projects.', 'metaform list projects')
    registered = home.projects()
    if not registered:
        out('No projects yet. Register one: metaform add project <id> <path>')
        return
    width = max(len(identifier) for identifier in registered)
    for identifier, path in registered.items():
        out(f'{identifier:<{width}}  {path}')


def _setting_for(switch: str) -> settings.Setting:
    match = next((item for item in settings.SCHEMA.values() if item.switch == switch), None)
    if match is None:
        raise Stop(f'{switch} is not a setting.', 'metaform help switches')
    return match


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
            name, _, inline = arg.partition('=')
            setting = _setting_for(name)
            if inline:
                raw = inline
            elif setting.kind == 'bool' and (index + 1 == len(args) or args[index + 1].startswith('--')):
                raw = 'on'
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
            raise Stop(str(error), nxt) from None
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
            keys.append(_setting_for(arg).key)
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
    width = max(len(row['key']) for row in rows)
    for row in rows:
        mark = '*' if row['state'] == 'glued' else ' '
        out(f"{mark} {row['key']:<{width}}  {_fmt(row['value'])}  ({row['state']})")
    out('')
    out('* glued: kept by unset all until unglued.')


def help_(args, folder):
    if not args:
        out(docs.overview())
    elif args == ['intro']:
        out(docs.INTRO)
    elif args == ['commands']:
        out(docs.commands_index())
    elif args == ['switches']:
        out(docs.switches_index())
    elif len(args) == 1 and args[0].startswith('--'):
        if not docs.known_switch(args[0]):
            raise Stop(f'No switch {args[0]}.', 'metaform help switches')
        out(docs.switch_page(args[0]))
    elif len(args) == 1 and args[0] in docs.COMMANDS:
        out(docs.page(args[0]))
    else:
        raise Stop(f'No help topic {" ".join(args)}.', 'metaform help commands')


VERBS = {'help': help_, 'add': add, 'list': list_, 'set': set_, 'unset': unset, 'config': config}


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
docs.command(Command('list', 'List registered things.', ('metaform list projects',),
                     see_also=('add',)))
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
        if not args:
            status(args, folder)
            return 0
        verb, rest = args[0], args[1:]
        if verb in ('-h', '--help'):
            out(docs.overview())
            return 0
        if verb not in VERBS:
            raise Stop(f'Unknown command: {verb}.', 'metaform help commands')
        if '-h' in rest or '--help' in rest:
            out(docs.syntax(verb))
            return 0
        VERBS[verb](rest, folder)
        return 0
    except Stop as stop:
        sys.stderr.write(f'Error: {stop}\n')
        if stop.next_step:
            sys.stderr.write(f'Next: {stop.next_step}\n')
        return 2
