"""The metaform command: verbs, the nouns they act on, and switches that change how they run, CLI-001.

The first word is a chassis verb or a module id. Chassis verbs are here, and
print exactly what CLI-031 states. Module verbs are parsed by the shared
grammar and run with their own Context, BASE-028. Every error is one Error
line and one Next line, CLI-009; exit codes are those of BASE-031.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import signal
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import __version__, context, docs, grammar, home, instructions, loader, query, results, settings
from .data import Store, export_document, import_document
from .docs import Command, Switch
from .errors import Stop
from .module import call

EMPTY_IS_ALL = ('modules', 'layers')


def out(text: str = '') -> None:
    sys.stdout.write(text if text.endswith('\n') else text + '\n')


def show(key: str, value: Any) -> str:
    """How a value is written in output, CLI-031."""
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, list):
        if not value:
            return 'all' if key in EMPTY_IS_ALL else '(none)'
        return ','.join(str(item) for item in value)
    if value is None or value == '':
        return '(none)'
    return str(value)


def shown(group: str, folder: Path) -> bool:
    return instructions.on_surface(group, folder)


# Status ---------------------------------------------------------------------------

def status(args: list[str], folder: Path) -> None:
    if args:
        raise Stop(f'Unknown command: {args[0]}.', 'metaform help commands')
    out(f'Metaform {__version__}')
    out(f'Home: {home.home()}')
    out(f'Folder: {folder}')
    project_id = context.project_for(folder)
    record = home.project(project_id) if project_id else None
    if record is None:
        out('Project: none')
        out('  Register one: metaform add project <id> <path>')
        return
    where = settings.state('project', folder)
    line = f'Project: {record.project_id} ({record.path})'
    if where != 'default':
        scope = settings._scope(settings.SCHEMA['project'], folder)
        line += ', selected here' if scope == home.path_key(folder) else f', inherited from {_folder_of(scope)}'
    out(line)
    out(f'Target: {record.target_type} {record.target_value}')
    forms = home.metaforms(record.project_id)
    active = home.active_metaform(record.project_id)
    if active is None:
        out('Metaform: none yet')
    else:
        out(f'Metaform: {active.name}' + (f', {len(forms)} in project' if len(forms) > 1 else ''))
    out(f'Projects: {len(home.projects())} registered')
    found = loader.discover()
    loaded = [item for item in found if item.module is not None]
    broken = [item for item in found if item.enabled and item.problem]
    out(f'Modules: {len(loaded)} on' + (f', {len(broken)} not loaded (metaform list modules)' if broken else ''))
    groups = settings.value('modules', folder)
    if groups:
        out(f'Modules: {", ".join(groups)} (narrowed; restore: metaform unset --modules)')
    for line in status_lines(folder, record.project_id):
        out(line)
    out('Instructions: metaform help agents')


def _folder_of(scope: str) -> str:
    with home.base() as db:
        row = db.execute('SELECT path FROM folders WHERE path_key=?', (scope,)).fetchone()
    return str(row[0]) if row else scope


def status_lines(folder: Path, project: str | None) -> list[str]:
    """Each surfaced module's status hook, in module id order; the chassis names no module, BASE-035."""
    from .module import Status
    lines: list[str] = []
    for module in instructions.surfaced(folder):
        if module.status is None:
            continue
        try:
            got = call(module.status, context.build(module.id, folder, project=project, resolve=False))
        except Exception as error:  # A failing hook is one line and nothing else.
            lines.append(f'{module.id}: status failed: {type(error).__name__}: {error}')
            continue
        if isinstance(got, Status):
            lines.extend(got.lines)
            if got.notice:
                lines.append('  ' + got.notice)
    return lines


# Projects, metaforms and modules ---------------------------------------------------------

def _named_folder(folder: Path, path: str) -> Path:
    return (folder / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()


def _project_arg(folder: Path, given: str | None) -> str:
    project_id = context.project_for(folder, given)
    if project_id is None:
        raise Stop('No project for this folder.', 'metaform add project <id> <path>')
    return project_id


def add(args: list[str], folder: Path) -> None:
    if args[:1] == ['project'] and len(args) in (3, 5):
        _, identifier, path, *target = args
        out(home.add_project(identifier, _named_folder(folder, path), *target))
        return
    if args[:1] == ['metaform'] and len(args) in (2, 3):
        project_id = _project_arg(folder, args[2] if len(args) == 3 else None)
        previous = home.active_metaform(project_id)
        created = home.add_metaform(project_id, args[1])
        kept = previous.name if previous else 'main'
        out(f'Added metaform {created.name} to {project_id}; it is now active. The previous metaform {kept} is kept. '
            f'To switch back: metaform activate metaform {kept}')
        return
    raise Stop('add needs: project <id> <path>, or metaform <name>.', 'metaform add project <id> <path>')


def list_(args: list[str], folder: Path) -> None:
    if args == ['modules']:
        found = loader.discover()
        width = max((len(item.id) for item in found), default=6)
        for item in found:
            state = 'error' if item.problem else ('on' if item.enabled else 'off')
            text = item.problem if item.problem else (item.module.summary if item.module else '')
            out(f'{item.id:<{width}}  {state:<5}  {item.place:<6}  {text}'.rstrip())
        return
    if args[:1] == ['metaforms'] and len(args) in (1, 2):
        project_id = _project_arg(folder, args[1] if len(args) == 2 else None)
        for form in home.metaforms(project_id):
            out(f'{form.name}  {form.created}' + ('  (active)' if form.active else ''))
        return
    if args != ['projects']:
        raise Stop('list needs a noun: projects or modules.', 'metaform list projects')
    registered = home.projects()
    if not registered:
        out('No projects yet. Register one: metaform add project <id> <path>')
        return
    width = max(len(record.project_id) for record in registered)
    for record in registered:
        out(f'{record.project_id:<{width}}  {record.path}  {record.target_type} {record.target_value}')


def activate(args: list[str], folder: Path) -> None:
    if args[:1] != ['metaform'] or len(args) not in (2, 3):
        raise Stop('activate needs: metaform <name>.', 'metaform list metaforms')
    project_id = _project_arg(folder, args[2] if len(args) == 3 else None)
    known = {form.name for form in home.metaforms(project_id)}
    if args[1] not in known:
        raise Stop(f'No metaform {args[1]} in {project_id}.', 'metaform list metaforms')
    home.activate_metaform(project_id, args[1])
    out(f'Active metaform for {project_id}: {args[1]}')


def _toggle(args: list[str], on: bool) -> None:
    verb = 'enable' if on else 'disable'
    if len(args) != 1:
        raise Stop(f'{verb} needs one module id.', f'metaform {verb} <module>')
    identifier = args[0]
    if identifier not in {item.id for item in loader.discover()}:
        raise Stop(f'No module {identifier}.', 'metaform list modules')
    loader.set_enabled(identifier, on)
    out(f"Module {identifier}: {'on' if on else 'off'}")


def enable(args: list[str], folder: Path) -> None:
    _toggle(args, True)


def disable(args: list[str], folder: Path) -> None:
    _toggle(args, False)


# Settings -----------------------------------------------------------------------------

def _split_folder(args: list[str], folder: Path) -> tuple[list[str], Path]:
    """The `folder=<path>` noun stores settings for another folder, PROJ-007."""
    rest = []
    for arg in args:
        if arg.startswith('folder='):
            folder = _named_folder(folder, arg.split('=', 1)[1])
        else:
            rest.append(arg)
    return rest, folder


def _setting_for(switch: str, verb: str) -> tuple[settings.Setting, bool]:
    if switch == '--confirm':
        raise Stop('--confirm is not a setting.', 'metaform help --confirm')
    if switch == '--all':
        raise Stop('--all is not a switch. all is an argument.', f'metaform {verb} all')
    if switch.startswith('-') and not switch.startswith('--') and len(switch) > 2:
        raise Stop(f'{switch} is not a switch: a short switch is one letter.', f'metaform help -{switch}')
    found = settings.by_switch(switch)
    if found is None:
        raise Stop(f'{switch} is not a setting.', 'metaform help switches')
    return found


def set_(args: list[str], folder: Path) -> None:
    args, folder = _split_folder(args, folder)
    glue = quiet = ended = False
    pairs: list[tuple[settings.Setting, Any]] = []
    index = 0
    while index < len(args):
        arg = args[index]
        index += 1
        if ended or not arg.startswith('-'):
            raise Stop(f"set takes switches, not '{arg}'.", 'metaform set --help')
        if arg == '--':
            ended = True
        elif arg == '--glue':
            glue = True
        elif arg in ('-q', '--quiet'):
            quiet = True
        else:
            name, equals, inline = arg.partition('=')
            setting, negative = _setting_for(name, 'set')
            if setting.kind == 'bool':
                if equals:
                    raise Stop(f'{name} takes no value: use {setting.switch} or {setting.negative}.',
                               f'metaform help {setting.switch}')
                pairs.append((setting, not negative))
                continue
            if not equals:
                if index >= len(args):
                    raise Stop(f'{name} needs a value.', f'metaform help {setting.switch}')
                inline = args[index]
                index += 1
            pairs.append((setting, inline))
    if not pairs:
        raise Stop('set needs at least one setting switch.', 'metaform set --help')
    before_groups = settings.value('modules', folder)
    changes, glued = [], []
    for setting, raw in pairs:
        try:
            old, new = settings.assign(setting.key, raw, folder, glue=glue)
        except settings.SettingError as error:
            raise Stop(str(error), error.next_step or ('metaform list projects' if setting.key == 'project'
                                                       else f'metaform help {setting.switch}')) from None
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
            out(f'  {key}: {show(key, old)} → {show(key, new)}')
    if glued:
        out('  glued: ' + ', '.join(glued))
    after_groups = settings.value('modules', folder)
    if any(key == 'modules' for key, _, _ in changes) and after_groups and \
            (not before_groups or set(after_groups) < set(before_groups)):
        out(f'Commands shown here: {", ".join(after_groups)}.')
        out('All other commands and help, including yours, are now hidden and will not run.')
        out('To restore them: metaform unset --modules')


def unset(args: list[str], folder: Path) -> None:
    args, folder = _split_folder(args, folder)
    unglue = quiet = everything = ended = False
    keys: list[str] = []
    for arg in args:
        if not ended and arg == 'all':
            everything = True
        elif not ended and arg == '--':
            ended = True
        elif not ended and arg == '--unglue':
            unglue = True
        elif not ended and arg in ('-q', '--quiet'):
            quiet = True
        elif not ended and arg.startswith('-'):
            keys.append(_setting_for(arg, 'unset')[0].key)
        else:
            raise Stop(f"unset takes switches or all, not '{arg}'.", 'metaform unset --help')
    if everything:
        # Only the settings stored at this folder, D36, of the modules loaded now, D53.
        keys = [key for key, setting in settings.SCHEMA.items()
                if settings._scope(setting, folder) == settings._own_scope(setting, folder)]
    results_by_key = {key: settings.reset(key, folder, unglue=unglue) for key in keys}
    if quiet:
        return
    reset = [key for key, (result, _) in results_by_key.items() if result == 'reset']
    skipped = [key for key, (result, _) in results_by_key.items() if result == 'skipped']
    unglued = [key for key, (_, was) in results_by_key.items() if was]
    out(f'Reset {len(reset)} setting(s): ' + ', '.join(reset) if reset else 'No settings required reset')
    if skipped:
        out('Skipped (glued): ' + ', '.join(skipped))
    if unglued:
        out('Unglued: ' + ', '.join(unglued))


def config(args: list[str], folder: Path) -> None:
    args, folder = _split_folder(args, folder)
    show_it = '--show' in args
    as_json = '--json' in args
    unknown = [arg for arg in args if arg not in ('--show', '--json')]
    if unknown:
        raise Stop(f'config does not take {unknown[0]}.', 'metaform config --help')
    rows = settings.describe(folder)
    if not show_it:
        from . import tui
        if tui.available():
            tui.run(folder)
            return
    if as_json:
        out(json.dumps(rows, default=str, ensure_ascii=False))
        return
    for row in rows:
        mark = '*' if row['state'] == 'glued' else ' '
        note = '' if row['state'] == 'default' else f"  ({row['state']})"
        out(f"{mark} {row['key']}: {show(row['key'], row['value'])}{note}")
    out('')
    out('* glued: kept by unset all until unglued.')


# Help -------------------------------------------------------------------------------------

def help_(args: list[str], folder: Path) -> None:
    if not args:
        out(docs.overview())
    elif args == ['intro']:
        out(docs.intro(str(home.home())))
    elif args == ['commands']:
        out(docs.commands_index(lambda group: shown(group, folder)))
    elif args == ['switches']:
        out(docs.switches_index())
    elif args == ['agents']:
        out(instructions.compose(folder))
    elif len(args) == 1 and args[0].startswith('-'):
        if not docs.known_switch(args[0]):
            raise Stop(f'No command, module or switch {args[0]}.', 'metaform help commands')
        out(docs.switch_page(args[0], folder))
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
        raise Stop(f'No command, module or switch {" ".join(args)}.', 'metaform help commands')


# Data -------------------------------------------------------------------------------------

def _nouns(args: list[str], allowed: tuple[str, ...]) -> tuple[list[str], dict[str, list[str]]]:
    positional, named = [], {}
    for arg in args:
        key, equals, value = arg.partition('=')
        if equals and key in allowed:
            named.setdefault(key, []).append(value)
        elif equals and '=' in arg and not arg.startswith('-'):
            raise Stop(f'{key}= is not a noun here; the named nouns are {", ".join(allowed)}.', 'metaform help export')
        else:
            positional.append(arg)
    return positional, named


def export(args: list[str], folder: Path) -> None:
    positional, named = _nouns(args, ('file', 'metaform', 'layer'))
    if len(positional) > 1:
        raise Stop('export takes one project, or all.', 'metaform export --help')
    projects = positional or [_project_arg(folder, None)]
    if projects != ['all'] and home.project(projects[0]) is None:
        raise Stop(f'No project {projects[0]} is registered.', 'metaform list projects')
    document = export_document(projects, metaform=(named.get('metaform') or [None])[0],
                               layers=named.get('layer', []))
    text = json.dumps(document, ensure_ascii=False, indent=1)
    if 'file' in named:
        target = _named_folder(folder, named['file'][0])
        target.write_text(text + '\n', encoding='utf-8')
        out(f'Exported to {target}')
    else:
        out(text)


def import_(args: list[str], folder: Path) -> None:
    if len(args) not in (1, 2):
        raise Stop('import takes a file, and then an optional project.', 'metaform import --help')
    source = _named_folder(folder, args[0])
    if not source.is_file():
        raise Stop(f'No file at {source}.', 'metaform export > <file>')
    try:
        document = json.loads(source.read_text(encoding='utf-8'))
    except ValueError:
        raise Stop(f'{source} is not JSON.', 'metaform export > <file>') from None
    report = import_document(document, args[1] if len(args) == 2 else None)
    for key, count in report.items():
        out(f'{key.replace("_", " ")}: {count}')


def query_(args: list[str], folder: Path) -> None:
    as_json = '--json' in args
    words = [arg for arg in args if arg != '--json']
    if not words:
        out(query.listing())
        return
    project_id = _project_arg(folder, None)
    store = Store(project_id, toggled=context.toggled_for(folder))
    result = query.run(store, words[0], words[1:])
    if as_json:
        out(results.as_json(result))
    elif isinstance(result, str):
        out(result)
    else:
        sys.stdout.write(results.as_text(result))


VERBS: dict[str, Callable[[list[str], Path], None]] = {
    'help': help_, 'add': add, 'list': list_, 'set': set_, 'unset': unset, 'config': config, 'enable': enable,
    'disable': disable, 'activate': activate, 'import': import_, 'export': export, 'query': query_}
ALWAYS = {'help', 'set', 'unset', 'config'}


# Module verbs ------------------------------------------------------------------------------

def _module(identifier: str, folder: Path, quiet: bool = False) -> Any:
    found = loader.get(identifier)
    if found is None:
        if quiet:
            return None
        raise Stop(f'Unknown command: {identifier}.', 'metaform help commands')
    if found.problem or (found.enabled and found.module is None):
        if quiet:
            return None
        raise Stop(f'Module {identifier} did not load: {found.problem}', 'metaform list modules')
    if not found.enabled:
        if quiet:
            return None
        raise Stop(f'Module {identifier} is off.', f'metaform enable {identifier}')
    if not shown(identifier, folder):
        if quiet:
            return None
        raise Stop(f"{identifier} is not on this folder's command surface.", 'metaform unset --modules')
    return found


def _verb(found: Any, name: str) -> Any:
    return next((verb for verb in found.module.verbs if verb.name == name and 'cli' in verb.surfaces), None)


def _here(verb: Any) -> bool:
    from .module_metadata import current_os
    return verb.supported_os is None or current_os() in verb.supported_os


def _run_async(function: Callable[..., Any], ctx: Any, label: str) -> Any:
    """Run an async verb: the first Ctrl+C asks it to cancel, a second interrupts at once, BASE-031."""
    loop = asyncio.new_event_loop()
    task = loop.create_task(function(ctx))
    presses = 0

    def on_interrupt(signum: int, frame: Any) -> None:
        nonlocal presses
        presses += 1
        if presses > 1:
            raise KeyboardInterrupt
        sys.stderr.write(f'Cancelling {label}...\n')
        sys.stderr.flush()
        loop.call_soon_threadsafe(task.cancel)

    previous = signal.signal(signal.SIGINT, on_interrupt)
    try:
        return loop.run_until_complete(task)
    finally:
        signal.signal(signal.SIGINT, previous)
        loop.close()


def run_module(identifier: str, rest: list[str], folder: Path) -> None:
    found = _module(identifier, folder)
    if not rest or rest[0] in ('-h', '--help'):
        out(docs.module_syntax(found.module))
        return
    verb = _verb(found, rest[0])
    if verb is None:
        raise Stop(f'{identifier} has no verb {rest[0]}.', f'metaform help {identifier}')
    if not _here(verb):
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
    if inspect.iscoroutinefunction(verb.run):
        result = _run_async(verb.run, ctx, f'{identifier} {verb.name}')
    else:
        result = call(verb.run, ctx)
    if result is None:
        return
    if isinstance(result, str):
        sys.stdout.write(result)
    elif parsed.json:
        sys.stdout.write(results.as_json(result) + '\n')
    else:
        sys.stdout.write(results.as_text(result))


# Help records --------------------------------------------------------------------------

docs.command(Command('help', 'Show an overview, an index, or the page for one command, module or switch.',
                     ('metaform help', 'metaform help intro', 'metaform help commands', 'metaform help switches',
                      'metaform help agents', 'metaform help <command|module|switch>', 'metaform help <module> <verb>'),
                     details='Each command also takes --help, which shows only its syntax.', see_also=('intro',)))
docs.command(Command('add', 'Register a project, or start a new metaform for one.',
                     ('metaform add project <id> <path> [<target type> <target value>]',
                      'metaform add metaform <name> [<project>]'),
                     description='Metaform keeps its data in the home, never in the project folder.',
                     details='The target type is path, url, artifact, inline or inferred; with none given it is the '
                             'folder itself.',
                     examples=(('metaform add project mgm ~/mgm-main', 'Register the MGM repository as mgm.'),),
                     see_also=('list', 'activate')))
docs.command(Command('list', 'List registered projects, modules, or a project\'s metaforms.',
                     ('metaform list projects', 'metaform list modules', 'metaform list metaforms [<project>]'),
                     details='list modules shows each module, whether it is on, where it was found, and why it did '
                             'not load when it did not.', see_also=('add', 'enable', 'disable')))
docs.command(Command('activate', "Make one of a project's metaforms the active one.",
                     ('metaform activate metaform <name> [<project>]',), see_also=('add', 'list')))
docs.command(Command('enable', 'Turn a module on.', ('metaform enable <module>',), see_also=('disable', 'list')))
docs.command(Command('disable', 'Turn a module off. Its settings keep their saved values.',
                     ('metaform disable <module>',), see_also=('enable', 'list')))
docs.command(Command('set', 'Save settings. Each setting is a switch.',
                     ('metaform set --<setting> [<value>] [--glue] [-q] [folder=<path>]',),
                     switches=(('--glue', 'Keep these settings through unset all.'),
                               ('-q, --quiet', 'Apply without printing.')),
                     description='Saves one or more settings. Folder settings apply to the folder you run it in and '
                                 'every folder below it.',
                     details='Out of the box every setting is at its default, and the defaults work. A glued setting '
                             'keeps its value when you run unset all.',
                     examples=(('metaform set --project mgm', 'Work on mgm from this folder.'),
                               ('metaform set --project mgm --glue', 'Same, and keep it through unset all.')),
                     see_also=('unset', 'config')))
docs.command(Command('unset', 'Return settings to their defaults.',
                     ('metaform unset --<setting> [--unglue] [-q] [folder=<path>]', 'metaform unset all [--unglue]'),
                     switches=(('--unglue', 'Also reset glued settings, and unglue them.'),
                               ('-q, --quiet', 'Apply without printing.')),
                     details='unset all resets every setting stored at this folder except glued ones. Add --unglue to '
                             'reset those too.',
                     examples=(('metaform unset --project', "Return this folder to its own project."),
                               ('metaform unset all --unglue', 'Reset everything, glued settings included.')),
                     see_also=('set', 'config')))
docs.command(Command('config', 'Open the settings screen, or print the settings.',
                     ('metaform config', 'metaform config --show [--json] [folder=<path>]'),
                     switches=(('--show', 'Print the settings instead of opening the screen.'),
                               ('--json', 'With --show, print JSON.')),
                     details='Each setting shows its value and its state: default, set, or glued.',
                     see_also=('set', 'unset')))
docs.command(Command('export', "Write a project's data to one JSON document.",
                     ('metaform export [<project>|all] [file=<file>] [metaform=<name>] [layer=<name>]...',),
                     details='With no file the document goes to standard output. Everything carries its unique id.',
                     see_also=('import',)))
docs.command(Command('import', 'Add what a JSON document holds and this home does not.',
                     ('metaform import <file> [<project>]',),
                     details='Importing something that already exists does nothing.', see_also=('export',)))
docs.command(Command('query', "Ask one of the design's questions of the folder's project.",
                     ('metaform query', 'metaform query <read> [<argument>...] [name=value]... [--json]'),
                     details="metaform query alone lists the reads.", see_also=('export',)))
docs.switch(Switch('--glue', 'Keep the settings you set through unset all.',
                   'A glued setting is skipped by unset all until you unset it with --unglue.', ('set',)))
docs.switch(Switch('--unglue', 'Reset glued settings too, and unglue them.', used_by=('unset',)))
docs.switch(Switch('--quiet', 'Apply the change without printing.', used_by=('set', 'unset')))
docs.switch(Switch('--show', 'Print the settings instead of opening the settings screen.', used_by=('config',)))
docs.switch(Switch('--json', 'Print machine-readable JSON.', used_by=('config', 'query', 'every module verb')))
docs.switch(Switch('--confirm', 'Run a caution verb. It is never a setting.', used_by=('caution verbs',)))


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
            raise Stop(f"{verb} is not on this folder's command surface.", 'metaform unset --modules')
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
    except Exception as error:  # Unexpected: one Error line and one Next line, exit 1, BASE-031 and CLI-009.
        sys.stderr.write(f'Error: {type(error).__name__}: {error}\n')
        sys.stderr.write(f'Next: {"metaform list modules" if args and args[0] not in VERBS else "metaform help"}\n')
        return 1
