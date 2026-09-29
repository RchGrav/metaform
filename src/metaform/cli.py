"""The metaform command: verbs, the nouns they act on, and switches that change how they run, CLI-001.

The first word is a chassis verb or a module id. Chassis verbs are here, and
print exactly what CLI-031 states. Module verbs are parsed by the shared
grammar and run with their own Context, BASE-028. Every error is one Error
line and one Next line, CLI-009; exit codes are those of BASE-031.
"""
from __future__ import annotations

import asyncio
import codecs
import inspect
import io
import json
import signal
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from . import (
    __version__,
    changes,
    context,
    docs,
    grammar,
    home,
    instructions,
    loader,
    nonce,
    query,
    reports,
    results,
    settings,
)
from .data import Store, export_document, history, import_document, prompts, pull_wheel
from .docs import Command, Switch
from .errors import Stop
from .module import Verb, call, on_this_system
from .wording import count, counted

EMPTY_IS_ALL = settings.EMPTY_IS_ALL


def out(text: str = '') -> None:
    sys.stdout.write(text if text.endswith('\n') else text + '\n')


def show(key: str, value: Any) -> str:
    """How a value is written in output, CLI-031."""
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, list):
        if not value:
            return 'all' if key in EMPTY_IS_ALL else '(none)'
        return ','.join(str(item) for item in cast(list[Any], value))
    if value is None or value == '':
        return '(none)'
    return str(value)


def setting_row(key: str, value: Any, state: str) -> str:
    """One setting as `config --show` and the settings screen print it: `*` glued, `(set)` or `(glued)`, CLI-026."""
    mark = '*' if state == 'glued' else ' '
    note = '' if state == 'default' else f'  ({state})'
    return f'{mark} {key}: {show(key, value)}{note}'


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
        scope = settings.scope_of(settings.SCHEMA['project'], folder)
        line += ', selected here' if scope == home.path_key(folder) else f', inherited from {_folder_of(scope)}'
    out(line)
    out(f'Target: {record.target_type} {record.target_value}')
    forms = home.metaforms(record.project_id)
    active = home.active_metaform(record.project_id)
    if active is None:
        out('Metaform: none yet')
    else:
        out(f'Metaform: {active.name}' + (f', {count(len(forms))} in project' if len(forms) > 1 else ''))
    out(f'Projects: {count(len(home.projects()))} registered')
    found = loader.discover()
    loaded = [item for item in found if item.module is not None]
    broken = [item for item in found if item.enabled and item.problem]
    out(f'Modules: {count(len(loaded))} on' + (f', {count(len(broken))} not loaded (metaform list modules)' if broken else ''))
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
        if created.name != args[1]:
            out(f'Notice: name: {project_id} already has a metaform named {args[1]}; this one was named '
                f'{created.name}.')
        return
    if args[:1] == ['origin'] and len(args) in (1, 2):
        store = Store(_project_arg(folder, args[1] if len(args) == 2 else None))
        known = {item.mform_sha_id for item in store.origins()}
        made = store.add_origin()
        if made.mform_sha_id in known:
            out(f'Origin {made.mform_id} already holds this content; nothing was added.')
            return
        where = f'at commit {made.commit_id}' if made.commit_id else f'copied from {made.source_path}'
        out(f'Added origin {made.mform_id}, {made.kind} {where}.')
        first = store.variants(made.mform_id)
        if first:
            out(f'Uncommitted work was collected as variant {first[0].variant_id}.')
        return
    if args[:1] == ['variant']:
        positional, named = _nouns(args[1:], ('origin', 'remove', *history.PROVENANCE), 'add')
        if len(positional) != 1:
            raise Stop('add variant takes one folder.', 'metaform add variant <folder>')
        given = {key: values[-1] for key, values in named.items()}
        provenance: dict[str, object] = {key: given[key] for key in history.PROVENANCE if key in given}
        if 'blinded' in provenance:
            provenance['blinded'] = _truth(str(provenance['blinded']), 'blinded')
        store = Store(_project_arg(folder, None))
        made = store.add_variant(_named_folder(folder, positional[0]), given.get('origin'),
                                 remove=_truth(given.get('remove', 'false'), 'remove'), provenance=provenance)
        out(f'Collected variant {made.variant_id} of origin {made.mform_id}: '
            f'{counted(len(made.files), "file", "files")} changed.')
        return
    raise Stop('add needs: project <id> <path>, metaform <name>, origin, or variant <folder>.',
               'metaform add project <id> <path>')


def _truth(text: str, noun: str) -> bool:
    if text not in ('true', 'false'):
        raise Stop(f'{noun}= takes true or false.', 'metaform help add')
    return text == 'true'


def list_(args: list[str], folder: Path) -> None:
    if args[:1] == ['reports']:
        list_reports(args[1:], folder)
        return
    if args == ['modules']:
        found = loader.discover()
        width = max((len(item.id) for item in found), default=6)
        for item in found:
            state = 'error' if item.problem else ('on' if item.enabled else 'off')
            summary = item.module.summary if item.module else (item.declared.summary if item.declared else None)
            text = item.problem or summary or ''
            out(f'{item.id:<{width}}  {state:<5}  {item.place:<6}  {text}'.rstrip())
        return
    if args[:1] == ['metaforms'] and len(args) in (1, 2):
        project_id = _project_arg(folder, args[1] if len(args) == 2 else None)
        for form in home.metaforms(project_id):
            out(f'{form.name}  {form.created}' + ('  (active)' if form.active else ''))
        return
    if args[:1] == ['backups'] and len(args) in (1, 2):
        for kept in home.backups(_project_arg(folder, args[1] if len(args) == 2 else None)):
            out(f'{kept.name}  {kept.held}')
        return
    if args[:1] == ['origins'] and len(args) in (1, 2):
        for item in Store(_project_arg(folder, args[1] if len(args) == 2 else None)).origins():
            out(f'{item.mform_id}  {item.kind}  {item.commit_id or item.source_path}  {item.established}  '
                f'{item.variants} variants')
        return
    if args[:1] == ['variants']:
        positional, named = _nouns(args[1:], ('origin',), 'list')
        if positional:
            raise Stop('list variants takes only origin=.', 'metaform list variants')
        for made in Store(_project_arg(folder, None)).variants((named.get('origin') or [None])[0]):
            out(f'{made.variant_id}  {made.collected}  {made.source_path}  {made.workflow or "-"}')
        return
    if args != ['projects']:
        raise Stop('list needs a noun: projects, modules, metaforms, reports, backups, origins or variants.',
                   'metaform list projects')
    registered = home.projects()
    if not registered:
        out('No projects yet. Register one: metaform add project <id> <path>')
        return
    width = max(len(record.project_id) for record in registered)
    for record in registered:
        out(f'{record.project_id:<{width}}  {record.path}  {record.target_type} {record.target_value}')


def list_reports(args: list[str], folder: Path) -> None:
    """`list reports [<project>] [kind=] [layer=]`: one line per file, BASE-045."""
    as_json = '--json' in args
    positional, named = _nouns([arg for arg in args if arg != '--json'], ('kind', 'layer'), 'list')
    if len(positional) > 1:
        raise Stop('list reports takes one project.', 'metaform list reports')
    page = reports.list_reports(folder, project=positional[0] if positional else None,
                                kind=(named.get('kind') or [None])[0], layer=(named.get('layer') or [None])[0])
    if as_json:
        out(results.as_json(page))
        return
    if not page.results:
        out('No reports yet.')
        return
    width = max(len(row.name) for row in page.results)
    for row in page.results:
        out(f'{row.name:<{width}}  {row.kind:<8}  {row.layer or "-"}  {row.size}  {row.created}')


def read(args: list[str], folder: Path) -> None:
    """`read report <file name> [<project>]`: the file's text exactly, BASE-045."""
    if args[:1] != ['report'] or len(args) not in (2, 3):
        raise Stop('read needs: report <file name>.', 'metaform list reports')
    sys.stdout.write(reports.read_report(folder, args[1], project=args[2] if len(args) == 3 else None))


def _text_or_file(value: str) -> str:
    """A report or shape given on the command line: `-` reads standard input, a file's path reads the file."""
    if value == '-':
        return sys.stdin.read()
    path = Path(value)
    try:
        if path.is_file():
            return path.read_bytes().decode('utf-8')
    except (OSError, ValueError):
        return value
    return value


def feedback(args: list[str], folder: Path) -> None:
    """`feedback <text> [layer=] [report=] [shape=]`: saved whatever the settings and never refused, BASE-045."""
    as_json = '--json' in args
    positional, named = _nouns([arg for arg in args if arg != '--json'], ('layer', 'report', 'shape'), 'feedback')
    if len(positional) != 1:
        raise Stop('feedback takes one text; put it in quotes.', 'metaform help feedback')
    given = {key: values[0] for key, values in named.items()}
    report = _text_or_file(given['report']) if 'report' in given else None
    shape = _text_or_file(given['shape']) if 'shape' in given else None
    result = reports.feedback(folder, positional[0], layer=given.get('layer'), report=report, shape=shape)
    sys.stdout.write(results.as_json(result) + '\n' if as_json else results.as_text(result))


def activate(args: list[str], folder: Path) -> None:
    if args[:1] != ['metaform'] or len(args) not in (2, 3):
        raise Stop('activate needs: metaform <name>.', 'metaform list metaforms')
    project_id = _project_arg(folder, args[2] if len(args) == 3 else None)
    known = {form.name for form in home.metaforms(project_id)}
    if args[1] not in known:
        raise Stop(f'No metaform {args[1]} in {project_id}.', 'metaform list metaforms')
    home.activate_metaform(project_id, args[1])
    out(f'Active metaform for {project_id}: {args[1]}')



def clear(args: list[str], folder: Path) -> None:
    """`clear project [<project>] --confirm`: the metaforms and reports go, everything else stays, PROJ-025."""
    confirm = '--confirm' in args
    words = [arg for arg in args if arg != '--confirm']
    if words[:1] != ['project'] or len(words) not in (1, 2):
        raise Stop('clear needs: project [<project>].', 'metaform clear project')
    project_id = _project_arg(folder, words[1] if len(words) == 2 else None)
    if home.project(project_id) is None:
        raise Stop(f'No project {project_id} is registered.', 'metaform list projects')
    found = home.to_clear(project_id)
    if not confirm:
        raise Stop(found.caution, f'If you are sure: metaform clear project {project_id} --confirm')
    cleared = home.clear_project(project_id)
    out(cleared.said)
    if cleared.backup:
        out(f'Backed up as {cleared.backup}.')
        out(f'To bring it back: {cleared.restore}')
    if cleared.not_removed:
        out('Not removed, still on disk:')
        for path, reason in cleared.not_removed:
            out(f'  {path}: {reason}')
        out(f'Next: {cleared.remedy(f"run metaform clear project {project_id} --confirm again")}')


def restore(args: list[str], folder: Path) -> None:
    """`restore project [<project>] [<backup>]`: a backup is brought back, the newest when none is named, PROJ-030."""
    if args[:1] != ['project'] or len(args) > 3:
        raise Stop('restore needs: project [<project>] [<backup>].', 'metaform restore project')
    project_id = _project_arg(folder, args[1] if len(args) >= 2 else None)
    if home.project(project_id) is None:
        raise Stop(f'No project {project_id} is registered.', 'metaform list projects')
    restored = home.restore_project(project_id, args[2] if len(args) == 3 else None)
    out(restored.said)
    if restored.held_before:
        out(f'What it held was backed up as {restored.held_before}.')


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
    rest: list[str] = []
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
    named = any(arg.startswith('folder=') for arg in args)
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
    for setting, raw in pairs:
        try:
            settings.checked(setting.key, raw, folder)
        except settings.SettingError as error:
            raise Stop(str(error), error.next_step or ('metaform list projects' if setting.key == 'project'
                                                       else f'metaform help {setting.switch}')) from None
    before_groups = settings.value('modules', folder)
    changes: list[tuple[str, Any, Any]] = []
    glued: list[str] = []
    notices: list[tuple[str, str]] = []
    for setting, raw in pairs:
        before = settings.state(setting.key, folder)
        try:
            old, new, noted = settings.assign(setting.key, raw, folder, glue=glue)
        except settings.SettingError as error:
            raise Stop(str(error), error.next_step or ('metaform list projects' if setting.key == 'project'
                                                       else f'metaform help {setting.switch}')) from None
        if old != new or settings.state(setting.key, folder) != before:
            changes.append((setting.key, old, new))
        if glue:
            glued.append(setting.key)
        notices += [(setting.key, message) for message in noted]
    for key, message in notices:
        out(f'Notice: {key}: {message}')
    if quiet:
        return
    where = f' for {folder}' if named else ''
    if not changes:
        out(f'Success: no changes{where}')
    else:
        out(f'Success: updated {counted(len(changes), "key", "keys")}{where}')
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
                if settings.scope_of(setting, folder) == settings.own_scope_of(setting, folder)]
    results_by_key = {key: settings.reset(key, folder, unglue=unglue) for key in keys}
    if quiet:
        return
    reset = [key for key, (result, _) in results_by_key.items() if result == 'reset']
    skipped = [key for key, (result, _) in results_by_key.items() if result == 'skipped']
    unglued = [key for key, (_, was) in results_by_key.items() if was]
    out(f'Reset {counted(len(reset), "setting", "settings")}: ' + ', '.join(reset) if reset
        else 'No settings required reset')
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
        out(setting_row(row['key'], row['value'], row['state']))
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
            if not _here(verb):
                raise _elsewhere(args[0], verb)
            out(docs.verb_page(found.module, verb))
        else:
            raise Stop(f'No verb {args[1]} in {args[0]}.', f'metaform help {args[0]}')
    else:
        raise Stop(f'No command, module or switch {" ".join(args)}.', 'metaform help commands')


# Data -------------------------------------------------------------------------------------

def _nouns(args: list[str], allowed: tuple[str, ...], verb: str = 'export') -> tuple[list[str], dict[str, list[str]]]:
    positional: list[str] = []
    named: dict[str, list[str]] = {}
    for arg in args:
        key, equals, value = arg.partition('=')
        if equals and key in allowed:
            named.setdefault(key, []).append(value)
        elif equals and key.isidentifier() and not arg.startswith('-'):
            raise Stop(f'{key}= is not a noun here; the named nouns are {", ".join(allowed)}.', f'metaform help {verb}')
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
    if args[0].startswith('wheel='):
        if len(args) != 1:
            raise Stop('import wheel= takes nothing more.', 'metaform import wheel=<name>-<version>')
        report = pull_wheel(args[0].partition('=')[2])
    else:
        source = _named_folder(folder, args[0])
        if not source.is_file():
            raise Stop(f'No file at {source}.', 'metaform export > <file>')
        try:
            document = json.loads(source.read_text(encoding='utf-8'))
        except ValueError:
            raise Stop(f'{source} is not JSON.', 'metaform export > <file>') from None
        report = import_document(document, args[1] if len(args) == 2 else None)
    for key, number in report.items():
        if key != 'notices':
            out(f'{key.replace("_", " ")}: {count(number)}')
    for notice in report['notices']:
        out(f"Notice: {notice['where']}: {notice['message']}")


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


def install_(args: list[str], folder: Path) -> None:
    from . import install
    install.install(args, out)


def prompts_(args: list[str], folder: Path) -> None:
    if args:
        raise Stop('prompts takes no words.', 'metaform prompts')
    for item in prompts.prompts():
        out(f'{item.name}  {item.format}  version {item.newest}')


def prompt_(args: list[str], folder: Path) -> None:
    if len(args) not in (1, 2) or (len(args) == 2 and not args[1].isdigit()):
        raise Stop('prompt takes a prompt name and an optional version number.', 'metaform prompts')
    sys.stdout.write(prompts.prompt_version(args[0], int(args[1]) if len(args) == 2 else None).text)


def extract(args: list[str], folder: Path) -> None:
    positional, named = _nouns(args, ('origin',), 'extract')
    if len(positional) < 2:
        raise Stop('extract takes variant ids, or all, and then a folder.', 'metaform extract <variant id> <folder>')
    store = Store(_project_arg(folder, None))
    for written in store.extract(positional[:-1], _named_folder(folder, positional[-1]),
                                 (named.get('origin') or [None])[0]):
        out(f'Extracted into {written}')


def uninstall_(args: list[str], folder: Path) -> None:
    from . import install
    install.uninstall(args, out)


def build_(args: list[str], folder: Path) -> None:
    if args:
        raise Stop('build takes no words.', 'metaform build')
    from . import build
    wheel, notes = build.build()
    for note in notes:
        out(note)
    out(f'Wheel: {wheel}')


VERBS: dict[str, Callable[[list[str], Path], None]] = {
    'help': help_, 'add': add, 'list': list_, 'set': set_, 'unset': unset, 'config': config, 'enable': enable,
    'disable': disable, 'activate': activate, 'import': import_, 'export': export, 'query': query_,
    'install': install_, 'uninstall': uninstall_, 'build': build_, 'feedback': feedback, 'read': read,
    'extract': extract, 'prompts': prompts_, 'prompt': prompt_, 'clear': clear, 'restore': restore}


def always(verb: str, rest: list[str]) -> bool:
    """Whether a chassis command runs whatever the surface: restoring it, and reporting, CLI-022 and BASE-045."""
    return verb in docs.ALWAYS or (verb == 'list' and rest[:1] == ['reports'])


# Module verbs ------------------------------------------------------------------------------

def _module(identifier: str, folder: Path, quiet: bool = False, surface: bool = True) -> Any:
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
    if surface and not shown(identifier, folder):
        if quiet:
            return None
        raise off_surface(identifier)
    return found


def off_surface(identifier: str) -> Stop:
    return Stop(f"{identifier} is not on this folder's command surface.", 'metaform unset --modules')


def _verb(found: loader.Found, name: str) -> Verb | None:
    if found.module is None:
        return None
    return next((verb for verb in found.module.verbs if verb.name == name and 'cli' in verb.surfaces), None)


def _here(verb: Verb) -> bool:
    return on_this_system(verb)


def _elsewhere(identifier: str, verb: Verb) -> Stop:
    """A verb outside this system: where it runs, printed by running it and by its help page, BASE-016."""
    return Stop(f'{identifier} {verb.name} runs on {", ".join(verb.supported_os or ())}.', f'metaform help {identifier}')


def _run_async(function: Callable[..., Any], ctx: Any, label: str) -> Any:
    """Run an async verb: the first Ctrl+C asks it to cancel, a second interrupts at once, BASE-031.

    Before its loop closes, the tasks the verb's module spawned on it are cancelled and waited for, and the loop's
    async generators are shut down, so shutdown finds nothing left running, BASE-018.
    """
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
        try:
            spawned = {item for item in loader.tasks_of(ctx.module) if item.get_loop() is loop}
            loader.finish_tasks(spawned)
            loop.run_until_complete(loop.shutdown_asyncgens())
        finally:
            loop.close()


def run_nonce(held: nonce.Nonce, rest: list[str], folder: Path) -> None:
    """`metaform <nonce>`: the module's function for the nonce, its commands with help, or one of them, BASE-050."""
    said = f'metaform {held.nonce}'
    if not held.open:
        raise Stop(f'Nonce {held.nonce} is closed; its task is complete.', 'Ask the main agent for the nonce of '
                                                                           'your next task')
    found = loader.get(held.module)
    if found is None or found.module is None:
        raise Stop(f'Nonce {held.nonce} belongs to module {held.module}, which is not loaded.',
                   'metaform list modules')
    if rest[:1] in (['help'], ['-h'], ['--help']):
        out('\n'.join(f'{said} {verb.name}  {verb.summary}' for verb in found.module.verbs))
        return
    if rest and _verb(found, rest[0]) is None:
        raise Stop(f'{held.module} has no command {rest[0]}.', f'{said} help')
    token = nonce.entered(held)
    try:
        run_module(held.module, rest or [held.function], folder)
    finally:
        nonce.left(token)


def run_module(identifier: str, rest: list[str], folder: Path) -> None:
    found = _module(identifier, folder, surface=False)
    module = found.module
    if module is None:
        raise Stop(f'Module {identifier} did not load: {found.problem}', 'metaform list modules')
    if module.default is not None and (not rest or rest[0].startswith('-') and rest[0] not in ('-h', '--help')):
        rest = [module.default, *rest]  # with no verb named, the module runs its default verb, BASE-035
    verb = _verb(found, rest[0]) if rest else None
    if not (verb is not None and verb.transport) and not shown(identifier, folder):
        raise off_surface(identifier)
    if not rest or rest[0] in ('-h', '--help'):
        out(docs.module_syntax(module))
        return
    if verb is None:
        raise Stop(f'{identifier} has no verb {rest[0]}.', f'metaform help {identifier}')
    if not _here(verb):
        raise _elsewhere(identifier, verb)
    parsed = grammar.parse(identifier, verb, rest[1:])
    if parsed.help:
        out(docs.verb_syntax(module, verb))
        return
    if verb.caution and not parsed.confirm:
        confirm = ' '.join(['metaform', identifier, verb.name, *rest[1:], '--confirm'])
        raise Stop(verb.caution, f'If you are sure: {confirm}')
    messages = sys.stderr if parsed.json else sys.stdout
    project = parsed.switches.pop('project', None)

    def sink(text: str) -> None:
        messages.write(text + '\n')
    ctx = context.build(identifier, folder, project=project, nouns=parsed.nouns, switches=parsed.switches, sink=sink)
    if inspect.iscoroutinefunction(verb.run):
        result = _run_async(verb.run, ctx, f'{identifier} {verb.name}')
    else:
        result = call(verb.run, ctx)
    data = results.noted(result, parsed.notices) if parsed.notices else result
    if parsed.notices and not isinstance(data, dict):
        for where, message in parsed.notices:
            messages.write(f'Notice: {where}: {message}\n')
    if result is None:
        return
    if isinstance(result, str):
        sys.stdout.write(result)
    elif parsed.json:
        sys.stdout.write(results.as_json(data) + '\n')
    else:
        sys.stdout.write(results.as_text(data))


# Help records --------------------------------------------------------------------------

docs.command(Command('help', 'Show an overview, an index, or the page for one command, module or switch.',
                     ('metaform help', 'metaform help intro', 'metaform help commands', 'metaform help switches',
                      'metaform help agents', 'metaform help <command|module|switch>', 'metaform help <module> <verb>'),
                     details='Each command also takes --help, which shows only its syntax.', see_also=('intro',)))
docs.command(Command('add', 'Register a project, or start a new metaform for one.',
                     ('metaform add project <id> <path> [<target type> <target value>]',
                      'metaform add metaform <name> [<project>]', 'metaform add origin [<project>]',
                      'metaform add variant <folder> [origin=<id>] [remove=true] [workflow=<text>] [prompt=<text>] '
                      '[model=<text>] [role=<text>] [module=<text>] [blinded=true|false]'),
                     description='Metaform keeps its data in the home, never in the project folder.',
                     details='The target type is path, url, artifact, inline or inferred; with none given it is the '
                             'folder itself.',
                     examples=(('metaform add project notes ~/notes', 'Register the folder ~/notes as the project notes.'),),
                     see_also=('list', 'activate')))
docs.command(Command('list', "List registered projects, modules, a project's metaforms, or its reports.",
                     ('metaform list projects', 'metaform list modules', 'metaform list metaforms [<project>]',
                      'metaform list reports [<project>] [kind=<kind>] [layer=<layer>] [--json]',
                      'metaform list backups [<project>]',
                      'metaform list origins [<project>]', 'metaform list variants [origin=<id>]'),
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
                     examples=(('metaform set --project notes', 'Work on notes from this folder.'),
                               ('metaform set --project notes --glue', 'Same, and keep it through unset all.')),
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
docs.command(Command('import', "Add what a JSON document or a directly run wheel's data holds and this home "
                               'does not.',
                     ('metaform import <file> [<project>]', 'metaform import wheel=<name>-<version>'),
                     details='Importing something that already exists does nothing. wheel= pulls in the data a '
                             'wheel kept while it ran directly: each of its metaforms arrives as its own, named '
                             '<name>-from-<name>-<version>, and is never made active.', see_also=('export',)))
docs.command(Command('query', "Ask one of the design's questions of the folder's project.",
                     ('metaform query', 'metaform query <read> [<argument>...] [name=value]... [--json]'),
                     details="metaform query alone lists the reads.", see_also=('export',)))
docs.command(Command('install', 'Set up your AI tools to use Metaform.',
                     ('metaform install', 'metaform install <tool>...', 'metaform install all'),
                     description='Checks the system first, previews every change with its backup, registers the '
                                 'server with each tool, writes the skill, and proves each tool can start the server.',
                     details='With no tool named it asks; naming tools, or all, sets up without asking.',
                     see_also=('build',)))
docs.command(Command('extract', 'Write variants of an origin out to folders, with Python alone.',
                     ('metaform extract <variant id>... <folder> [origin=<id>]', 'metaform extract all <folder> '
                      '[origin=<id>]'),
                     description="Starts from the origin's files, applies each variant's changes, and checks every "
                                 'file against its recorded hash. Needs no git and no access to the repository.',
                     details='One named variant goes into the folder itself; several, or all, each go into a '
                             'subfolder named by the variant id. A folder that is not empty is refused.',
                     see_also=('add', 'list')))
docs.command(Command('prompts', 'List the stored prompts, each with its newest version.', ('metaform prompts',),
                     details='A prompt is edited as a new version, in the web GUI; no version ever changes, so each '
                             'layer shows the exact text it was made from.', see_also=('prompt',)))
docs.command(Command('prompt', "Show a stored prompt's text, its newest version or a numbered one.",
                     ('metaform prompt <name> [<version>]',), see_also=('prompts',)))
docs.command(Command('uninstall', 'Remove Metaform from your AI tools.',
                     ('metaform uninstall', 'metaform uninstall <tool>...', 'metaform uninstall all'),
                     description="Previews every change with its backup, then removes Metaform's registration and "
                                 'skill from each tool. Every other entry in a tool\'s config stays as it is.',
                     details='With no tool named it asks; naming tools, or all, removes without asking. The '
                             'projects and maps in the home stay.',
                     see_also=('install',)))
docs.command(Command('feedback', 'Save feedback on the Metaform process, and a report or a shape with it.',
                     ('metaform feedback <text> [layer=<layer>] [report=<text|file|->] [shape=<text|file|->]',),
                     description='Feedback is about Metaform itself: problems with the process, bad semantics, a tool '
                                 'that did not match its schema. It is saved in the home, never in the project, and '
                                 'nothing given is refused.',
                     details='An agent that cannot continue stops and saves a trouble report here, with the result '
                             'it has in shape=, instead of retrying. A value that names a file reads the file; - reads '
                             'standard input.',
                     examples=(('metaform feedback "The subtype fields did not match the intake text." '
                                'layer=intake-20260925T041500Z-3fa2c1', "Feedback on an intake run."),),
                     see_also=('list', 'read')))
docs.command(Command('read', 'Read one report, feedback or shape file exactly.',
                     ('metaform read report <file name> [<project>]',), see_also=('list', 'feedback')))
docs.command(Command('clear', "Remove a project's metaforms and reports; its registration, settings and history stay.",
                     ('metaform clear project [<project>] --confirm',),
                     description='Clears what Metaform inferred about the project so an intake can be taken again '
                                 'from nothing. Every metaform goes with its store, and every report, feedback and '
                                 'shape file. The registration, the folder and every file in it, the folder settings, '
                                 'and the origins and variants stay.',
                     details='It backs the project up before it removes anything, says the backup\'s name, and '
                             'metaform restore project brings it back. '
                             'Without --confirm it says exactly what it would remove and removes nothing. After a '
                             'clear the project has no metaform until the next intake, or any other write, creates '
                             'main again. A file it cannot remove, such as a store a running web GUI holds open on '
                             'Windows, stays on disk and is named with the reason and what to do.',
                     examples=(('metaform clear project', 'Say what clearing this folder\'s project would remove.'),
                               ('metaform clear project notes --confirm', 'Clear the project notes.')),
                     see_also=('list', 'add', 'restore')))
docs.command(Command('restore', 'Bring back what a clear removed, from the backup the clear made.',
                     ('metaform restore project [<project>] [<backup>]',),
                     description='Puts the project back as it was when the backup was made: its metaforms with their '
                                 'stores, the one that was active, and its report files.',
                     details='With no backup named it brings back the newest. A project that holds metaforms or '
                             'reports is cleared first, which backs up what it holds, so nothing is lost. '
                             'metaform list backups lists them, the newest first.',
                     examples=(('metaform restore project', "Bring back this folder's project from its newest backup."),
                               ('metaform list backups', 'List the backups of this folder\'s project.')),
                     see_also=('clear', 'list')))
docs.command(Command('build', 'Build one wheel of the chassis and the enabled modules.', ('metaform build',),
                     details='The wheel carries its pure-Python dependencies and runs directly with python <wheel>.',
                     see_also=('install',)))
docs.switch(Switch('--glue', 'Keep the settings you set through unset all.',
                   'A glued setting is skipped by unset all until you unset it with --unglue.', ('set',)))
docs.switch(Switch('--unglue', 'Reset glued settings too, and unglue them.', used_by=('unset',)))
docs.switch(Switch('--quiet', 'Apply the change without printing.', used_by=('set', 'unset')))
docs.switch(Switch('--show', 'Print the settings instead of opening the settings screen.', used_by=('config',)))
docs.switch(Switch('--json', 'Print machine-readable JSON.', used_by=('config', 'query', 'every module verb')))
docs.switch(Switch('--confirm', 'Run a caution verb. It is never a setting.', used_by=('caution verbs', 'clear')))


def _utf8_streams() -> None:
    """Read and write UTF-8 on every system, QUAL-002: a pipe on Windows defaults to cp1252, which cannot write
    the arrow of `set` or the intake's text. A Windows console, and every other system, is UTF-8 already."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper) and codecs.lookup(stream.encoding).name != 'utf-8':
            stream.reconfigure(encoding='utf-8')


def main(argv: list[str] | None = None) -> int:
    _utf8_streams()
    args = list(sys.argv[1:] if argv is None else argv)
    folder = Path.cwd()
    if args[:1] == ['--version']:
        out(f'metaform {__version__}')
        return 0
    try:
        return _command(args, folder)
    finally:
        changes.announce(folder, 'cli')  # what the command changed, fired on the event bus, VIEW-018


def _command(args: list[str], folder: Path) -> int:
    try:
        loader.discover()
        if not args:
            status(args, folder)
            return 0
        verb, rest = args[0], args[1:]
        if verb in ('-h', '--help'):
            out(docs.overview())
            return 0
        if verb == '--version':
            out(f'metaform {__version__}')
            return 0
        if verb not in VERBS:
            held = nonce.read(verb) if loader.get(verb) is None else None
            if held is not None:
                run_nonce(held, rest, folder)
                return 0
            run_module(verb, rest, folder)
            return 0
        if not always(verb, rest) and not shown('chassis', folder):
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
    except Exception as error:  # A failure: one Error line and one Next line, exit 1, BASE-031 and CLI-009.
        from .install import Failed
        sys.stdout.flush()
        if isinstance(error, Failed):
            sys.stderr.write(f'Error: {error}\nNext: {error.next_step}\n')
            return 1
        sys.stderr.write(f'Error: {type(error).__name__}: {error}\n')
        sys.stderr.write(f'Next: {"metaform list modules" if args and args[0] not in VERBS else "metaform help"}\n')
        return 1
