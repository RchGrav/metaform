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
import os
import shlex
import signal
import sys
import threading
import zipfile
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext, suppress
from importlib import resources
from pathlib import Path
from typing import Any, cast

from . import (
    __version__,
    aliases,
    caller,
    changes,
    context,
    docs,
    grammar,
    harness,
    home,
    instructions,
    loader,
    prompt_files,
    query,
    reports,
    results,
    settings,
)
from .data import Store, export_document, history, import_document, prompts
from .docs import Command, Switch
from .errors import Stop, StoreError
from .module import Verb, call, caution_of, decided, on_this_system, persons_word, persons_word_acted
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


def setting_row(key: str, value: Any, state: str, source: str | None = None) -> str:
    """One setting as `config --show` and the settings screen print it: `*` glued, `(set)`, `(glued)` or
    `(inherited from <folder>)`, CLI-026 and CLI-014."""
    mark = '*' if state == 'glued' else ' '
    note = '' if state == 'default' else f'  (inherited from {source})' if state == 'inherited' and source \
        else f'  ({state})'
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
        out('  Watch it first: metaform demo')
        out('  Map this folder: metaform start')
        out('  Register one: metaform add project <id> <path>')
        return
    where = settings.state('project', folder)
    line = f'Project: {record.project_id} ({record.path})'
    if where != 'default':
        scope = settings.scope_of(settings.SCHEMA['project'], folder)
        line += ', selected here' if scope == home.path_key(folder) else f', inherited from {_folder_of(scope)}'
    out(line)
    out(f'Target: {record.target_type} {record.target_value}')
    forms = home.bases(record.project_id)
    active = home.active_base(record.project_id)
    if active is None:
        out('Base: none yet')
    else:
        out(f'Base: {active.name}' + (f', {count(len(forms))} in project' if len(forms) > 1 else ''))
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
    return settings.folder_of(scope)


def status_lines(folder: Path, project: str | None) -> list[str]:
    """Each surfaced module's status hook, in module id order; the chassis names no module, BASE-035."""
    from .module import Status
    lines: list[str] = []
    for module in instructions.surfaced(folder):
        if module.status is None:
            continue
        try:
            got = call(module.status, context.build(module.id, folder, project=project, resolve=False))
        except Exception as error:  # noqa: BLE001 - Isolate arbitrary module status failures to one reported line.
            lines.append(f'{module.id}: status failed: {type(error).__name__}: {error}')
            continue
        if isinstance(got, Status):
            lines.extend(got.lines)
            if got.notice:
                lines.append('  ' + got.notice)
    return lines


# Projects, bases and modules ---------------------------------------------------------

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
    if args[:1] == ['base'] and len(args) in (2, 3):
        project_id = _project_arg(folder, args[2] if len(args) == 3 else None)
        if caller.unconsented():  # switching the map is the person's decision, CLI-011
            raise caller.persons_decision(home.switch_caution(project_id), shlex.join(['metaform', 'add', *args]),
                                          'the base picker')
        previous = home.active_base(project_id)
        created = home.add_base(project_id, args[1])
        kept = previous.name if previous else 'main'
        out(f'Added base {created.name} to {project_id}; it is now active. The previous base {kept} is kept. '
            f'To switch back: metaform activate base {kept}')
        if created.name != args[1]:
            out(f'Notice: name: {project_id} already has a base named {args[1]}; this one was named '
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
    raise Stop('add needs: project <id> <path>, base <name>, origin, or variant <folder>.',
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
            # a prompt written wrong in its file never turns the module off; it is named here until corrected
            for said in prompt_files.problems(item.path) if item.module is not None else []:
                out(f'{"":<{width}}  {"":<5}  {"":<6}  prompt: {said}')
        return
    if args[:1] == ['bases'] and len(args) in (1, 2):
        project_id = _project_arg(folder, args[1] if len(args) == 2 else None)
        for form in home.bases(project_id):
            out(f'{form.name}  {form.created}' + ('  (active)' if form.active else ''))
        return
    if args[:1] == ['backups'] and len(args) in (1, 2):
        project_id = _project_arg(folder, args[1] if len(args) == 2 else None)
        for kept in home.backups(project_id):
            out(f'{kept.name}  {kept.held}')
        for wiped in home.wipe_backups(project_id):
            out(f'{wiped["stamp"]}  wipe  {wiped["board"] or "First board"}  {wiped["tickets"]} tickets')
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
        raise Stop('list needs a noun: projects, modules, bases, reports, backups, origins or variants.',
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


def _text_or_file(value: str, noun: str, notices: list[tuple[str, str]]) -> str:
    """A report or shape given on the command line: `-` reads standard input, a file's path reads the file. A file
    that cannot be read as given is still saved, never refused, with a notice saying what was kept, BASE-044."""
    if value == '-':
        return sys.stdin.read()
    path = Path(value)
    try:
        named = path.is_file()
    except (OSError, ValueError):  # text no file name can hold, such as a long report with line breaks
        return value
    if not named:
        return value
    try:
        data = path.read_bytes()
    except OSError as error:
        said = f'{path} could not be read ({error.strerror or error}); its name was saved as the {noun}.'
        notices.append((noun, said))
        return value
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        notices.append((noun, f'{path} is not UTF-8 text; it was saved with each byte that is not shown as U+FFFD.'))
        return data.decode('utf-8', errors='replace')


def feedback(args: list[str], folder: Path) -> None:
    """`feedback <text> [layer=] [report=] [shape=]`: saved whatever the settings and never refused, BASE-045."""
    as_json = '--json' in args
    positional, named = _nouns([arg for arg in args if arg != '--json'], ('layer', 'report', 'shape'), 'feedback')
    if len(positional) != 1:
        raise Stop('feedback takes one text; put it in quotes.', 'metaform help feedback')
    given = {key: values[0] for key, values in named.items()}
    notices: list[tuple[str, str]] = []
    report = _text_or_file(given['report'], 'report', notices) if 'report' in given else None
    shape = _text_or_file(given['shape'], 'shape', notices) if 'shape' in given else None
    result = results.noted(reports.feedback(folder, positional[0], layer=given.get('layer'), report=report,
                                            shape=shape), notices)
    sys.stdout.write(results.as_json(result) + '\n' if as_json else results.as_text(result))


def report_(args: list[str], folder: Path) -> None:
    """`report [<text>] [files=true|false]`: one zip of what is needed to see a problem, written here, BASE-045."""
    positional, named = _nouns(args, ('files',), 'report')
    if len(positional) > 1:
        raise Stop('report takes one line; put it in quotes.', 'metaform help report')
    files: bool | None = None
    if 'files' in named:
        if named['files'][-1] not in ('true', 'false'):
            raise Stop('files= takes true or false.', 'metaform help report')
        files = named['files'][-1] == 'true'
    description = positional[0].strip() if positional else ''
    if not description:
        if not sys.stdin.isatty():
            raise Stop('report needs one line saying what went wrong.', 'metaform report "what went wrong"')
        description = input('What went wrong, in one line: ').strip()
        if not description:
            raise Stop('report needs one line saying what went wrong.', 'metaform report "what went wrong"')
        if files is None:
            files = input("Include the project's own files? [y/N] ").strip().lower() in ('y', 'yes')
    from . import problem_report
    path, held = problem_report.write(folder, description, files=bool(files))
    out(f'Wrote {path}, holding:')
    for line in held:
        out(f'  {line}')
    out(f'Nothing was sent. {problem_report.SEND_TO}')


def activate(args: list[str], folder: Path) -> None:
    if args[:1] != ['base'] or len(args) not in (2, 3):
        raise Stop('activate needs: base <name>.', 'metaform list bases')
    project_id = _project_arg(folder, args[2] if len(args) == 3 else None)
    known = {form.name for form in home.bases(project_id)}
    if args[1] not in known:
        raise Stop(f'No base {args[1]} in {project_id}.', 'metaform list bases')
    if caller.unconsented():  # switching the map is the person's decision, CLI-011
        raise caller.persons_decision(home.switch_caution(project_id, args[1]),
                                      shlex.join(['metaform', 'activate', *args]),
                                      'the base picker')
    left = home.active_base(project_id)
    made = home.activate_base(project_id, args[1])
    out(f'Active base for {project_id}: {args[1]}')
    said = home.staying(project_id, left, made)
    if said:
        out(said)



def clear(args: list[str], folder: Path) -> None:
    """`clear project [<project>] --confirm`: the bases and reports go, everything else stays, PROJ-025."""
    confirm = '--confirm' in args
    words = [arg for arg in args if arg != '--confirm']
    if words[:1] != ['project'] or len(words) not in (1, 2):
        raise Stop('clear needs: project [<project>].', 'metaform clear project')
    project_id = _project_arg(folder, words[1] if len(words) == 2 else None)
    if home.project(project_id) is None:
        raise Stop(f'No project {project_id} is registered.', 'metaform list projects')
    found = home.to_clear(project_id)
    if caller.unconsented():  # clearing the map is the person's decision: an agent's --confirm never runs it, CLI-011
        raise caller.persons_decision(found.caution, shlex.join(['metaform', 'clear', 'project', project_id,
                                                                 '--confirm']),
                                      'Clear project')
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


def remove(args: list[str], folder: Path) -> None:
    """`remove project [<project>] --confirm`: an empty project leaves the list, its folder untouched, PROJ-031."""
    confirm = '--confirm' in args
    words = [arg for arg in args if arg != '--confirm']
    if words[:1] != ['project'] or len(words) not in (1, 2):
        raise Stop('remove needs: project [<project>].', 'metaform remove project')
    project_id = _project_arg(folder, words[1] if len(words) == 2 else None)
    if home.project(project_id) is None:
        raise Stop(f'No project {project_id} is registered.', 'metaform list projects')
    held = home.not_empty(project_id)
    if held:
        raise Stop(held, f'metaform clear project {project_id} --confirm')
    if not confirm:
        raise Stop(home.removal_caution(project_id), f'If you are sure: metaform remove project {project_id} --confirm')
    home.remove_project(project_id)
    out(f'Removed {project_id}. Its folder and files were not touched.')


def restore(args: list[str], folder: Path) -> None:
    """`restore project [<project>] [<backup>]`: a backup is brought back, the newest when none is named, PROJ-030. A
    `--confirm` the person pastes with it is taken as said: the restore backs up what it replaces first."""
    confirm = '--confirm' in args
    args = [arg for arg in args if arg != '--confirm']
    if args[:1] != ['project'] or len(args) > 3:
        raise Stop('restore needs: project [<project>] [<backup>].', 'metaform restore project')
    project_id = _project_arg(folder, args[1] if len(args) >= 2 else None)
    if home.project(project_id) is None:
        raise Stop(f'No project {project_id} is registered.', 'metaform list projects')
    if caller.unconsented():  # a restore replaces the map the person and every agent sees, CLI-011
        raise caller.persons_decision(home.restore_caution(project_id, args[2] if len(args) == 3 else None),
                                      shlex.join(['metaform', 'restore', *args]), 'Restore')
    # A restore clears first, and a clear stops the agents at work: with any at work it asks first and names them,
    # as clear project does (UX review round 2, 2026-10-17, project-scope F2).
    if not confirm and home.at_work(project_id):
        raise Stop(home.restore_caution(project_id, args[2] if len(args) == 3 else None),
                   f'If you are sure: {shlex.join(["metaform", "restore", *args, "--confirm"])}')
    restored = home.restore_project(project_id, args[2] if len(args) == 3 else None)
    out(restored.said)
    if restored.held_before:
        out(f'What it held was backed up as {restored.held_before}. To bring that back: {restored.back}')


def _toggle(args: list[str], on: bool, folder: Path) -> None:
    verb = 'enable' if on else 'disable'
    if len(args) != 1:
        raise Stop(f'{verb} needs one module id.', f'metaform {verb} <module>')
    identifier = args[0]
    if identifier not in {item.id for item in loader.discover()}:
        raise Stop(f'No module {identifier}.', 'metaform list modules')
    loader.set_enabled(identifier, on)
    out(f"Module {identifier}: {'on' if on else 'off'}")
    from . import install
    install.node_skill_follows(identifier, folder, out)  # Claude Code's metaform-node skill exists only with map on


def enable(args: list[str], folder: Path) -> None:
    _toggle(args, True, folder)


def disable(args: list[str], folder: Path) -> None:
    _toggle(args, False, folder)


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


def _held_or_word(keys: list[str], folder: Path, command: str) -> dict[str, Any] | None:
    """For a call without the person's consent that names person-only settings: the person's word it runs on, when
    every one of them is a setting their own system agent changes on their word (`Setting.on_persons_word`, Autostart
    agents) and the call is made in a turn their own message started, as over MCP; otherwise refused as the person's
    decision, saying what would allow it. None when it names no person-only setting."""
    word = persons_word(folder, f'Setting {", ".join(keys)}') if settings.on_persons_word(keys) else None
    if word is None:
        settings.refuse_held_control(keys, folder, command)
    return word


def _acted_on_word(folder: Path, word: dict[str, Any], said: str) -> None:
    """What a settings call did on the person's word: written in their system agent's chat with the message that
    authorized it, and said in the output."""
    persons_word_acted(folder, word, said)
    out(f'On the person\'s word, "{word.get("text")}": {said}.')


def _set_command(pairs: list[tuple[settings.Setting, Any]]) -> str:
    """The `metaform set` line the person pastes for the person-only settings among `pairs`, quoted for a shell."""
    words = ['metaform', 'set']
    for setting, raw in pairs:
        if setting.person_only:
            words += [setting.switch if raw is True else setting.negative or setting.switch] \
                if setting.kind == 'bool' else [setting.switch, str(raw)]
    return shlex.join(words)


def set_(args: list[str], folder: Path) -> None:
    named = any(arg.startswith('folder=') for arg in args)
    args, folder = _split_folder(args, folder)
    glue = quiet = ended = confirm = False
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
        elif arg == '--confirm':
            confirm = True  # a risky choice is stored only when it is confirmed; it is never a setting, CLI-018
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
    if not pairs and confirm:
        raise Stop('--confirm is not a setting.', 'metaform help --confirm')
    if not pairs:
        raise Stop('set needs at least one setting switch.', 'metaform set --help')
    word: dict[str, Any] | None = None
    if caller.unconsented():
        # Check the whole call before validation, confirmation or writes: --confirm cannot grant control. Autostart
        # agents, asked by the person in their system agent's chat, is set in the turn their message started.
        word = _held_or_word([setting.key for setting, _ in pairs], folder, _set_command(pairs))
    for setting, raw in pairs:
        try:
            settings.checked(setting.key, raw, folder)
        except settings.SettingError as error:
            raise Stop(str(error), error.next_step or ('metaform list projects' if setting.key == 'project'
                                                       else f'metaform help {setting.switch}')) from None
        if not confirm and (risked := settings.risk(setting.key, raw, folder)):
            raise Stop(f'{setting.switch} {raw} is stored only when you confirm it: {risked}',
                       f'metaform set {setting.switch} {raw} --confirm')
    before_groups = settings.value('modules', folder)
    updates: list[tuple[str, Any, Any]] = []
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
            updates.append((setting.key, old, new))
        if glue:
            glued.append(setting.key)
        notices += [(setting.key, message) for message in noted]
    for key, message in notices:
        out(f'Notice: {key}: {message}')
    if word is not None:  # what it did on the person's word, in their system agent's chat
        said = 'set ' + ', '.join(f'{key} to {show(key, new)}' for key, _, new in updates) if updates else \
            'left the settings as they were'
        _acted_on_word(folder, word, said)
    if quiet:
        return
    where = f' for {folder}' if named else ''
    if not updates:
        out(f'Success: no updates{where}')
    else:
        out(f'Success: updated {counted(len(updates), "key", "keys")}{where}')
        for key, old, new in updates:
            out(f'  {key}: {show(key, old)} → {show(key, new)}')
    if glued:
        out('  glued: ' + ', '.join(glued))
    after_groups = settings.value('modules', folder)
    if any(key == 'modules' for key, _, _ in updates) and after_groups and \
            (not before_groups or set(after_groups) < set(before_groups)):
        out(f'Commands shown here: {", ".join(after_groups)}.')
        out('All other commands and help, including yours, are now hidden and will not run.')
        out('To restore them: metaform unset --modules')


def completions(line: str, folder: Path) -> list[str]:
    """What can follow the typed line, for the shell's tab, as bash's `complete -C` asks: a command first, then
    after set or unset a setting's switch, and after a switch with choices one of its choices, as `--switch value` or
    `--switch=value`; bash completes the word after `=` by itself."""
    words = line.split()
    typed = '' if not words or line.endswith((' ', '\t')) else words.pop()
    if len(words) <= 1:
        found = [*VERBS, *(item.id for item in loader.discover())]
    elif words[1] in ('set', 'unset'):
        switch, equals, typed = typed.partition('=') if typed.startswith('--') and '=' in typed else ('', '', typed)
        named = settings.by_switch(switch or words[-1]) if (equals or words[-1].startswith('--')) else None
        if named is not None and named[0].kind != 'bool' and (equals or not typed.startswith('-')):
            found = named[0].options(folder) if named[0].choices is not None else []
        else:
            found = sorted({item for setting in settings.SCHEMA.values() for item in setting.switches
                            if item.startswith('--') and (words[1] == 'set' or not item.startswith('--no-'))
                            and not (words[1] == 'set' and setting.per_call)}  # given on its verb, never set
                           | ({'--glue', '--quiet', '--confirm'} if words[1] == 'set' else {'--unglue', '--quiet'}))
    else:
        found = []
    return [item for item in dict.fromkeys(found) if item.startswith(typed)]


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
    held = shlex.join(['metaform', 'unset',
                       *(settings.SCHEMA[key].switch for key in keys if settings.SCHEMA[key].person_only)])
    word = _held_or_word(keys, folder, held) if caller.unconsented() else None
    for key in keys:  # every one is checked before any is reset
        try:
            settings.check_reset(key, folder)
        except settings.SettingError as error:
            raise Stop(str(error), error.next_step or 'metaform config --show') from None
    results_by_key = {key: settings.reset(key, folder, unglue=unglue) for key in keys}
    if word is not None:  # what it did on the person's word, in their system agent's chat
        done = [key for key, (result, _) in results_by_key.items() if result == 'reset']
        _acted_on_word(folder, word, f'reset {", ".join(done)} to the default' if done
                       else 'left the settings as they were')
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


def alias(args: list[str], folder: Path) -> None:
    """`alias <name> <module> <module>... [folder=<path>]`: one name at the top menu for several modules, CLI-039."""
    named = any(arg.startswith('folder=') for arg in args)
    args, folder = _split_folder(args, folder)
    name, *modules = args or ['']
    modules = aliases.define(folder, name, modules, set(VERBS))
    where = f'in {folder}, ' if named else ''
    out(f'Success: {where}{name} stands for {", ".join(modules)}')


def config(args: list[str], folder: Path) -> None:
    args, folder = _split_folder(args, folder)
    show_it = '--show' in args
    as_json = '--json' in args
    unknown = [arg for arg in args if arg not in ('--show', '--json')]
    if unknown:
        raise Stop(f'config does not take {unknown[0]}.', 'metaform config --help')
    if not show_it:
        from . import tui
        if tui.available():
            tui.run(folder)
            return
    rows = settings.describe(folder)
    if as_json:
        out(json.dumps(rows, default=str, ensure_ascii=False))
        return
    for row in rows:
        out(setting_row(row['key'], row['value'], row['state'], row.get('from')))
    out('')
    out('* glued: kept by unset all until unglued.')


# Help -------------------------------------------------------------------------------------

def help_(args: list[str], folder: Path) -> None:
    if not args:
        out(docs.overview())
    elif args == ['intro']:
        out(docs.intro(str(home.home())))
    elif args == ['commands']:
        out(docs.commands_index(lambda group: shown(group, folder),
                                {name: [module.id for module in held] for name, held in aliases.shown(folder).items()}))
    elif args == ['switches']:
        out(docs.switches_index())
    elif args == ['agents']:
        out(instructions.compose(folder))
    elif len(args) == 2 and args[0] == 'agents':
        out(_module_instructions(args[1], folder))
    elif len(args) == 1 and args[0].startswith('-'):
        if not docs.known_switch(args[0]):
            raise Stop(f'No command, module or switch {args[0]}.', 'metaform help commands')
        out(docs.switch_page(args[0], folder))
    elif len(args) == 1 and args[0] in docs.COMMANDS:
        extra_details = ''
        if args[0] == 'provision':
            from . import install
            extra_details = install.provision_mcp(folder)
        out(docs.page(args[0], extra_details=extra_details))
    elif len(args) == 1 and loader.get(args[0]) is None and args[0] in aliases.defined(folder):
        run_alias(args[0], [], folder)
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


def instructions_(args: list[str], folder: Path) -> None:
    """The instructions agents read, composed now for the folder, MCP-007; always available, like help agents."""
    if len(args) > 1:
        raise Stop(f'instructions takes one module, not {" ".join(args)}.', 'metaform instructions')
    out(_module_instructions(args[0], folder) if args else instructions.compose(folder))


def _module_instructions(identifier: str, folder: Path) -> str:
    """One module's full instructions, MCP-029."""
    found = instructions.module_text(folder, identifier)
    if found is None:
        raise Stop(f'No module {identifier} with instructions on this folder\'s surface.', 'metaform help agents')
    return found


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
    positional, named = _nouns(args, ('file', 'base', 'metaform', 'layer'))  # metaform= is the base's old name
    if len(positional) > 1:
        raise Stop('export takes one project, or all.', 'metaform export --help')
    projects = positional or [_project_arg(folder, None)]
    if projects != ['all'] and home.project(projects[0]) is None:
        raise Stop(f'No project {projects[0]} is registered.', 'metaform list projects')
    document = export_document(projects, metaform=(named.get('base') or named.get('metaform') or [None])[0],
                               layers=named.get('layer', []))
    text = json.dumps(document, ensure_ascii=False, indent=1)
    if 'file' in named:
        target = _named_folder(folder, named['file'][0])
        if home.is_home_path(target):
            home.mkdir_private(target.parent)
            home.write_private(target, text + '\n')
        else:
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
    if zipfile.is_zipfile(source):  # a project archive or a returned one, BASE-060
        _import_archive(source, args[1] if len(args) == 2 else None)
        return
    try:
        document = json.loads(source.read_text(encoding='utf-8'))
    except ValueError:
        raise Stop(f'{source} is not JSON.', 'metaform export > <file>') from None
    _imported(import_document(document, args[1] if len(args) == 2 else None))


def _imported(report: dict[str, Any]) -> None:
    for key, number in report.items():
        if key != 'notices':
            out(f'{key.replace("_", " ")}: {count(number)}')
    for notice in report['notices']:
        out(f"Notice: {notice['where']}: {notice['message']}")


def _import_archive(source: Path, project: str | None) -> None:
    """Import an archive and say what came in, and for returned work which layers and where its file changes wait for
    review: nothing is applied to the project's folder, BASE-060."""
    from . import archive
    found = archive.import_archive(source, project)
    if found.kind == 'project':
        out(f'Imported the project archive of {found.project}.')
        _imported(found.report)
        if found.files:
            out(f"Files: the archive holds the project's {counted(found.files, 'file', 'files')} in "
                f'{archive.ORIGIN}; nothing was unpacked.')
        return
    out(f'Imported work returned on the project {found.project}'
        + (f', working layer {found.layer}.' if found.layer else '.'))
    _imported(found.report)
    record = home.project(found.project)
    if found.changed or found.added or found.removed:
        out(f'Changes: {counted(len(found.changed), "file", "files")} changed, {count(len(found.added))} new, '
            f'{count(len(found.removed))} removed, written for review to {found.review}; nothing was applied to '
            f'{record.path if record is not None else "the project"}. Review {archive.vary.DIFF}, '
            f'{archive.vary.FILES} and {archive.vary.REMOVED} there, then apply what you want.')
    else:
        out('Changes: none to the files.')
    if found.note and found.review is not None:
        out(f'Note: {found.review / archive.NOTE}')


def query_(args: list[str], folder: Path) -> None:
    as_json = '--json' in args
    words = [arg for arg in args if arg != '--json']
    if not words:
        out(query.listing())
        return
    project_id = _project_arg(folder, None)
    store = Store(project_id, toggled=settings.toggled_layers(folder))
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


def start_(args: list[str], folder: Path) -> None:
    from . import start
    start.start(args, folder, out)


def demo_(args: list[str], folder: Path) -> None:
    from . import demo  # `main` has already moved this process into the demo's own home, CLI-042
    demo.run(args, folder, out)


def prompts_(args: list[str], folder: Path) -> None:
    if args == ['review']:  # every prompt agents read, browsed and edited in the terminal, STORE-044
        from . import prompt_review
        prompt_review.run()
        return
    if args:
        raise Stop('prompts takes no words but review.', 'metaform prompts')
    for item in prompts.prompts():
        out(f'{item.name}  {item.format}  version {item.newest}')


def prompt_(args: list[str], folder: Path) -> None:
    if args[:1] == ['register'] and len(args) >= 2:  # a prompt kept anywhere joins the review, MCP-031
        from . import prompt_review
        positional, named = _nouns(args[1:], ('source', 'element', 'purpose', 'used'), 'prompt register')
        if len(positional) != 1 or not named.get('source') or any(len(v) != 1 for v in named.values()):
            raise Stop('prompt register takes owner:name and source=<file>, with optional element=, purpose= and used=.',
                       'metaform help prompt')
        item = prompt_review.register(positional[0], named['source'][0], element=named.get('element', [''])[0],
                                      purpose=named.get('purpose', [''])[0], used=named.get('used', [''])[0])
        out(f'Registered {item["key"]} from {item["source"]}' + (f' element <{item["element"]}>' if item['element'] else ''))
        return
    if args[:1] == ['save'] and len(args) >= 3:
        name, text, *options = args[1:]
        json_output = '--json' in options
        options = [option for option in options if option != '--json']
        extra, named = _nouns(options, ('format', 'parent'), 'prompt')
        if extra or any(len(values) != 1 for values in named.values()):
            raise Stop('prompt save takes a name, text and optional format= and parent=.', 'metaform help prompt')
        parent = named.get('parent', [None])[0]
        if parent is not None and (not parent.isdecimal() or int(parent) < 1):
            raise Stop('parent= takes a positive version number.', 'metaform help prompt')
        try:  # through the one gate every surface saves through: plain text in, sent as written
            saved, said = prompt_files.save_edit(name, sys.stdin.read() if text == '-' else text,
                                                 format=named.get('format', ['text'])[0],
                                                 parent=int(parent) if parent is not None else None)
        except ValueError as error:
            raise Stop(f'{error}.', f'metaform prompt {name}') from None
        shown = results.noted(saved, [(name, one) for one in said])
        out(results.as_json(shown) if json_output else results.as_text(shown))
        return
    if len(args) not in (1, 2) or (len(args) == 2 and not args[1].isdecimal()):
        raise Stop('prompt takes a prompt name and an optional version number.', 'metaform prompts')
    sys.stdout.write(prompt_files.readable(prompts.prompt_version(args[0], int(args[1]) if len(args) == 2 else None)))


def extract(args: list[str], folder: Path) -> None:
    positional, named = _nouns(args, ('origin',), 'extract')
    if len(positional) < 2:
        raise Stop('extract takes variant ids, or all, and then a folder.', 'metaform extract <variant id> <folder>')
    store = Store(_project_arg(folder, None))
    for written in store.extract(positional[:-1], _named_folder(folder, positional[-1]),
                                 (named.get('origin') or [None])[0]):
        out(f'Extracted into {written}')


def provision(args: list[str], folder: Path) -> None:
    """Record that the agent is done provisioning the harness Metaform runs under, MCP-028 and D96."""
    if len(args) == 1 and args[0] in ('claude', 'codex', 'gemini'):
        from . import install
        install.provision(args[0], out)
        return
    if args != ['done']:
        raise Stop('provision takes done.', 'metaform provision done')
    binary = harness.running()
    if binary is None or harness.key(binary) is None:
        raise Stop('Metaform cannot tell which harness it runs under, so there is none to record.',
                   'metaform help provision')
    harness.done(binary)
    out(f'Provisioning is done for the harness at {harness.key(binary)}; Metaform will not ask here again.')


def uninstall_(args: list[str], folder: Path) -> None:
    from . import install
    install.uninstall(args, out)


def build_(args: list[str], folder: Path) -> None:
    """One of the four builds, BASE-060; with no words, the wheel of the modules on at home, BASE-041. It asks
    nothing: what is built is what the words say."""
    from . import build
    positional, named = _nouns(args, ('kind', 'project', 'modules', 'shape', 'files', 'prompt'), 'build')
    if positional:
        raise Stop(f'build takes only name=value words, not {positional[0]}.', 'metaform help build')
    if any(len(values) != 1 for values in named.values()):
        raise Stop('build takes each of its words once.', 'metaform help build')
    given = {key: values[0] for key, values in named.items()}
    if given.get('files', 'true') not in ('true', 'false'):
        raise Stop('files= takes true or false.', 'metaform help build')
    task = None
    if 'prompt' in given:
        task = sys.stdin.read() if given['prompt'] == '-' else _read_task(_named_folder(folder, given['prompt']))
    built = build.make(build.Request(
        kind=given.get('kind', 'installer'), project=given.get('project'),
        modules=tuple(name for name in given['modules'].split(',') if name) if 'modules' in given else None,
        shape=given.get('shape'), files=given.get('files', 'true') == 'true', task=task), folder)
    for note in built.notes:
        out(note)
    if built.kind == 'archive':
        out(f'Archive: {built.path}')
        return
    out(f'Modules: {", ".join(built.modules) or "none"}')
    out(f'Wheel: {built.path}')
    if built.prompt is not None:
        out(f'Prompt: {built.path.parent / "prompt.md"}')
    if built.bundle is not None:
        out(f'Zip: {built.bundle}')


def _read_task(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError) as error:
        raise Stop(f'The prompt file {path} could not be read: {error}.', 'metaform build prompt=<a UTF-8 text file>') \
            from None


def return_(args: list[str], folder: Path) -> None:
    """`python <project wheel> return`: the remote agent's work as one archive to offer as a download, BASE-060."""
    from . import archive
    positional, named = _nouns(args, ('note', 'file'), 'return')
    if positional or any(len(values) != 1 for values in named.values()):
        raise Stop('return takes note=<text> and file=<path>, each at most once.', 'metaform help return')
    file = _named_folder(folder, named['file'][0]) if 'file' in named else None
    returned = archive.write_return(folder, named.get('note', [''])[0], file)
    out(f'Archive: {returned.path}')
    out(f'Layers: {", ".join(returned.layers)}')
    if not returned.files:
        out('Changes: this wheel carried no project files, so the archive holds no file changes.')
    else:
        out(f'Changes: {counted(len(returned.changed), "file", "files")} changed, {count(len(returned.added))} new, '
            f'{count(len(returned.removed))} removed.')
    if returned.left:
        out(f'Notice: layers: {counted(returned.left, "write", "writes")} went to layers the person\'s home already '
            'holds, such as refinements of the base; they stay here and are not in the archive. Write what should '
            'return to the working layer.')
    out(prompt_files.chassis('remote_returned', archive=str(returned.path)))


VERBS: dict[str, Callable[[list[str], Path], None]] = {
    'help': help_, 'add': add, 'list': list_, 'set': set_, 'unset': unset, 'config': config, 'enable': enable,
    'disable': disable, 'activate': activate, 'import': import_, 'export': export, 'query': query_,
    'start': start_, 'install': install_, 'uninstall': uninstall_, 'build': build_, 'return': return_, 'feedback': feedback, 'read': read,
    'report': report_, 'extract': extract, 'prompts': prompts_, 'prompt': prompt_, 'clear': clear, 'restore': restore, 'remove': remove,
    'instructions': instructions_, 'provision': provision, 'alias': alias, 'demo': demo_}


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

    # Only the main thread can take Ctrl+C; a call made on another thread, as a test or a host may make, runs
    # without the handler rather than failing with its loop and task left open.
    handling = threading.current_thread() is threading.main_thread()
    previous = signal.signal(signal.SIGINT, on_interrupt) if handling else None
    try:
        return loop.run_until_complete(task)
    finally:
        if handling:
            signal.signal(signal.SIGINT, previous)
        try:
            spawned = {item for item in loader.tasks_of(ctx.module) if item.get_loop() is loop}
            loader.finish_tasks(spawned)
            loop.run_until_complete(loop.shutdown_asyncgens())
        finally:
            loop.close()


def run_alias(name: str, rest: list[str], folder: Path) -> None:
    """`metaform <alias>`: the commands of each module it stands for that this folder shows, CLI-039."""
    if rest not in ([], ['-h'], ['--help']):
        raise Stop(f'{name} is an alias; run its commands by their module, as it lists them.', f'metaform {name}')
    held = aliases.shown(folder).get(name)
    if not held:
        raise Stop(f"{name} stands for {', '.join(aliases.defined(folder)[name])}, and none of them is on this "
                   "folder's command surface.", 'metaform unset --modules')
    out('\n'.join(docs.module_syntax(module) for module in held))


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
    given = [key for key in parsed.switches if key in verb.switches]
    # read only when the call needs to know: whether the person's consent is with it, from their terminal or the page
    acting = caller.unconsented() if given or verb.person_says else None
    word = _held_or_word(given, folder, shlex.join(['metaform', identifier, *rest])) if acting else None
    messages = sys.stderr if parsed.json else sys.stdout
    project = parsed.switches.pop('project', None)

    def sink(text: str) -> None:
        messages.write(text + '\n')
    ctx = context.build(identifier, folder, project=project, nouns=parsed.nouns, switches=parsed.switches, sink=sink)
    if verb.caution and (not parsed.confirm or verb.person_says and acting):
        # quoted for a shell, so a JSON argument such as ["k3"] pastes as it was given (person-consent F4)
        confirm = shlex.join(['metaform', identifier, verb.name, *(arg for arg in rest[1:] if arg != '--confirm'),
                              '--confirm'])
        if verb.person_says and acting:  # the person's decision: an agent's --confirm never runs it, CLI-011
            raise caller.persons_decision(caution_of(verb, ctx), confirm, verb.page)
        raise Stop(caution_of(verb, ctx), f'If you are sure: {confirm}')
    # a call that is the person's decision by what it asks, such as releasing a held ticket: it runs on their consent
    # alone, from their terminal or the page, and needs no --confirm there (UX review round 2, held-and-signals)
    deciding = decided(verb, ctx)
    if deciding and caller.unconsented():
        raise caller.persons_decision(deciding, shlex.join(['metaform', identifier, *rest]), verb.page)
    if inspect.iscoroutinefunction(verb.run):
        result = _run_async(verb.run, ctx, f'{identifier} {verb.name}')
    else:
        result = call(verb.run, ctx)
    if word is not None:  # run on the person's word with a switch only they set otherwise, as over MCP
        _acted_on_word(folder, word, f'ran {identifier} {verb.name} with ' + ', '.join(
            f'{key} {show(key, parsed.switches[key])}' for key in given if key in parsed.switches))
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
                      'metaform help agents', 'metaform help agents <module>', 'metaform help <command|module|switch>',
                      'metaform help <module> <verb>'),
                     details='Each command also takes --help, which shows only its syntax.', see_also=('intro',)))
docs.command(Command('instructions', 'Show the instructions agents read, composed now for this folder.',
                     ('metaform instructions', 'metaform instructions <module>'),
                     details="The same text as metaform help agents and the MCP server's instructions, but for its "
                             "first line, which says whether a server or the command line serves it. It runs "
                             "whatever the folder's command surface. With a module, that module's full "
                             "instructions, as metaform help agents <module> shows them; --connect-instructions "
                             "chooses whether the instructions list each module in one line or in full.",
                     see_also=('help',)))
docs.command(Command('add', 'Register a project, or start a new base for one.',
                     ('metaform add project <id> <path> [<target type> <target value>]',
                      'metaform add base <name> [<project>]', 'metaform add origin [<project>]',
                      ('metaform add variant <folder> [origin=<id>] [remove=true] [workflow=<text>] [prompt=<text>] '
                       '[model=<text>] [role=<text>] [module=<text>] [blinded=true|false]')),
                     description='Metaform keeps its data in the home, never in the project folder.',
                     details='The target type is path, url, artifact, inline or inferred; with none given it is the '
                             'folder itself.',
                     examples=(('metaform add project notes ~/notes', 'Register the folder ~/notes as the project notes.'),),
                     see_also=('list', 'activate')))
docs.command(Command('list', "List registered projects, modules, a project's bases, or its reports.",
                     ('metaform list projects', 'metaform list modules', 'metaform list bases [<project>]',
                      'metaform list reports [<project>] [kind=<kind>] [layer=<layer>] [--json]',
                      'metaform list backups [<project>]',
                      'metaform list origins [<project>]', 'metaform list variants [origin=<id>]'),
                     details='list modules shows each module, whether it is on, where it was found, and why it did '
                             'not load when it did not.', see_also=('add', 'enable', 'disable')))
docs.command(Command('activate', "Make one of a project's bases the active one.",
                     ('metaform activate base <name> [<project>]',), see_also=('add', 'list')))
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
                             'keeps its value when you run unset all. A setting with choices takes one of them, and '
                             'a value that is not one is refused with the list. Tab completes the switches and each '
                             'setting\'s choices once your shell asks metaform for them: in bash, complete -C '
                             'metaform metaform; in zsh, autoload bashcompinit; bashcompinit; complete -C metaform '
                             'metaform.',
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
docs.command(Command('alias', 'Give two or more modules one name at the top menu.',
                     ('metaform alias <name> <module> <module>... [folder=<path>]',),
                     description='An alias is one name beside the module names. Entering it, metaform <name>, lists '
                                 'the commands of every module it stands for, each written <module> <command>.',
                     details='It holds in the folder it is defined for and every folder below it. Defining a name '
                             'again replaces what it stood for there. folder= defines it for another folder, such as '
                             "a worker's, before the worker starts.",
                     examples=(('metaform alias mapping map memory', 'One name for the map and memory commands.'),),
                     see_also=('help',)))
docs.command(Command('export', "Write a project's data to one JSON document.",
                     ('metaform export [<project>|all] [file=<file>] [base=<name>] [layer=<name>]...',),
                     details='With no file the document goes to standard output. Everything carries its unique id.',
                     see_also=('import',)))
docs.command(Command('import', 'Add what a JSON document or a project archive holds and this home does not.',
                     ('metaform import <file> [<project>]',),
                     description='The file is an export document, or a .zip archive that metaform build or a '
                                 "project wheel's return wrote.",
                     details='Importing something that already exists does nothing. A returned archive adds the '
                             "remote agent's working layer as a new layer of a project this home holds, and writes its "
                             'file changes, as diffs and whole files, and its note into a new folder beside the '
                             "archive for you to review; the project's own folder is never changed.",
                     see_also=('export', 'build', 'return')))
docs.command(Command('query', "Ask one of the design's questions of the folder's project.",
                     ('metaform query', 'metaform query <read> [<argument>...] [name=value]... [--json]'),
                     details="metaform query alone lists the reads.", see_also=('export',)))
docs.command(Command('install', 'Set up your AI tools to use Metaform.',
                     ('metaform install [force=<true|false>]', 'metaform install <tool>... [force=<true|false>]',
                      'metaform install all [force=<true|false>]'),
                     description='Checks the system first, previews every change with its backup, registers the '
                                 'declared server when one is enabled, writes the skill and supported global instruction pointers '
                                 'and reminders, and proves each tool can start the server.',
                     details='With no tool named it asks; naming tools, or all, sets up without asking. '
                             'Run from a wheel, install first installs that wheel through uv tool install, '
                             'then sets up AI tools. An installed copy only sets up tools. '
                             'force=true allows a downgrade; the default is false. '
                             'With no enabled MCP server provider, setup writes skills and supported instruction '
                             'pointers and reminders and skips registration and proof. '
                             'Use metaform set --install-server <module> to choose among several providers. '
                             'Claude Code also gets the metaform-node skill, ~/.claude/skills/metaform-node/SKILL.md, '
                             'while the map module is enabled and on the folder\'s surface: a person types '
                             '/metaform-node <address> and Claude runs metaform map where for that Address, so the '
                             'node brief arrives without the MCP server. Claude never invokes it on its own. Enabling '
                             'or disabling map adds or removes it; no other tool gets it, since only Claude Code '
                             'passes it the typed Address and keeps it person-invoked.',
                     see_also=('build',)))
_provision_skill = resources.files('metaform') / 'skill' / 'SKILL.md'
_provision_skill_source = (f'extract {_provision_skill.at} from {_provision_skill.root.filename}'
                           if isinstance(_provision_skill, zipfile.Path) else f'copy {_provision_skill}')
docs.command(Command('provision', 'Give an AI tool the installer does not know what it supports of Metaform.',
                     ('metaform provision <claude|codex|gemini>', 'metaform provision done'),
                     description='The first metaform run under a tool Metaform has not recorded says so. Set up '
                                 'each feature below that the tool supports, skip any it cannot or you do not want, '
                                 'then run metaform provision done; runs under that tool then say nothing of it.',
                     details=f'Skill: {_provision_skill_source} into the tool\'s '
                             'global skills folder as metaform/SKILL.md, a real copy and never a link, and never '
                             'into a project folder. '
                             'Global instructions: run metaform provision claude, codex or gemini to preview '
                             'and back up additions to ~/.claude/CLAUDE.md, ~/.codex/AGENTS.md '
                             '(under CODEX_HOME when set), or ~/.gemini/GEMINI.md. '
                             'Provision claude also writes the metaform-node skill into '
                             '~/.claude/skills/metaform-node/SKILL.md while map is enabled and on this folder\'s '
                             'surface, and removes it when map is not; other harnesses do not get it. '
                             'Hooks: provision claude also merges a passive PreToolUse reminder for Agent, Task, '
                             'Workflow and AskUserQuestion into ~/.claude/settings.json. It changes no permissions '
                             'or tool arguments. Codex receives no hook. Gemini receives an AfterTool reminder '
                             'for invoke_agent, delegate_to_agent and ask_user, after the action returns because '
                             'BeforeTool cannot deliver passive context. Run metaform set --gemini-reminder off to use only '
                             'global instructions, then rerun provision gemini or install gemini. '
                             f'Other harnesses: append this pointer: {prompt_files.chassis("global_instructions")} '
                             'Place it in the harness global instructions file, showing the '
                             'addition and backing up the file first. Set up only hooks that can pass a '
                             'reminder to the agent without blocking or changing the tool call. '
                             'A tool registered through a command by metaform install is recorded and never sees '
                             'the notice. For a tool installed through a config file, finish here with '
                             'metaform provision done.',
                     see_also=('install',)))
docs.command(Command('extract', 'Write variants of an origin out to folders, with Python alone.',
                     ('metaform extract <variant id>... <folder> [origin=<id>]', ('metaform extract all <folder> '
                      '[origin=<id>]')),
                     description="Starts from the origin's files, applies each variant's changes, and checks every "
                                 'file against its recorded hash. Needs no git and no access to the repository.',
                     details='One named variant goes into the folder itself; several, or all, each go into a '
                             'subfolder named by the variant id. A folder that is not empty is refused.',
                     see_also=('add', 'list')))
docs.command(Command('prompts', 'List the stored prompts, each with its newest version; review browses every prompt agents read.',
                     ('metaform prompts', 'metaform prompts review'),
                     details='A prompt is edited as a new version with prompt save or in the web GUI; no version ever changes, so each '
                             'layer shows the exact text it was made from. review lists every prompt in the chassis and the modules '
                             'with its purpose and where the code uses it; Enter shows one whole, e opens it in an editor, and a '
                             'changed text is saved as a new version and as a packet under artifacts/prompt-edits for an agent to '
                             'apply to the source.', see_also=('prompt',)))
docs.command(Command('prompt', "Show a stored prompt's text, its newest version or a numbered one.",
                     ('metaform prompt <name> [<version>]',
                      'metaform prompt save <name> <text|-> [format=<text|markdown|xml>] [parent=<version>]',
                      'metaform prompt register <owner:name> source=<file> [element=<name>] [purpose=<text>] [used=<where>]'),
                     details='save creates version 1 or appends an edit, with the newest version as parent unless '
                             'parent= names one. Use - to read text from standard input. Text is kept verbatim. '
                             'format= applies only to a new prompt, default text. Identical text returns its '
                             'parent with a notice. Older versions and provenance links stay unchanged. '
                             'Over MCP use metaform_save_prompt with name, text, optional format and parent. register '
                             'adds a prompt kept in any file to the review, metaform prompts review, by its owner and '
                             'name; element= names the XML element inside the file when it holds several.',
                     see_also=('prompts',)))
docs.command(Command('start', 'Map the project in this folder: one command, and its map opens in your browser.',
                     ('metaform start',),
                     description='Run it in your own project folder. It registers the folder as a project named '
                                 'after it, turns on the modules it needs, connects Claude Code to this project, '
                                 'starts the intake agent with what the files already say, starts the web GUI and '
                                 'opens your browser on the project, where the map grows as each part is recorded.',
                     details='It asks only what the files cannot say, at most two short questions, and only at a '
                             'terminal: what the project is for when no README or manifest says it, and who it is for '
                             'when the folder holds no code yet, in which case the map records intent only. Claude '
                             'Code gets the metaform MCP server in the project\'s .mcp.json, as claude mcp add --scope '
                             'project writes it, unless metaform install already connected it everywhere; any other '
                             'AI tool is named with metaform install <tool>. The intake agent is the AI tool found, '
                             'unless you chose another with metaform set --dispatch-agent. Running it again changes '
                             'nothing already done and opens the page again.',
                     examples=(('cd ~/my-project && metaform start', 'Map my-project and open its map.'),),
                     see_also=('install', 'web', 'intake')))
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
                     examples=((('metaform feedback "The join fields did not match the intake text." '
                                 'layer=intake-20260925T041500Z-3fa2c1'), "Feedback on an intake run."),),
                     see_also=('list', 'read')))
docs.command(Command('report', 'Report a problem: one file holding what is needed to see it, to send to rchgrav on '
                     'Discord.',
                     ('metaform report', 'metaform report <text> [files=true|false]'),
                     description='Writes metaform-report-<time>.zip in this folder: your one line saying what went '
                                 'wrong, the Metaform version and modules, the system and Python, the last lines of '
                                 "the home's logs and the dispatch runner logs, the errors found in them, and the "
                                 'settings in force here. Every key, token, password and phone number is masked, '
                                 'keeping its last two characters.',
                     details="Without a line it asks for one, and asks whether to include the project's own files; "
                             'with one it includes them only with files=true. It never sends anything: send the '
                             'file to rchgrav on Discord. The page\'s View menu has the same, Report a problem, which '
                             'adds the browser and its console errors.',
                     examples=(('metaform report "The map stopped drawing after I opened Agents."',
                                'Write the report here.'),),
                     see_also=('feedback',)))
docs.command(Command('read', 'Read one report, feedback or shape file exactly.',
                     ('metaform read report <file name> [<project>]',), see_also=('list', 'feedback')))
docs.command(Command('clear', "Remove a project's bases and reports; its registration, settings and history stay.",
                     ('metaform clear project [<project>] --confirm',),
                     description='Clears what Metaform inferred about the project so an intake can be taken again '
                                 'from nothing. Every base goes with its store, and every report, feedback and '
                                 'shape file. The registration, the folder and every file in it, the folder settings, '
                                 'the origins and variants, and the conversations with agents stay.',
                     details='It backs the project up before it removes anything, says the backup\'s name, and '
                             'metaform restore project brings it back. '
                             'Without --confirm it says exactly what it would remove and removes nothing. After a '
                             'clear the project has no base until the next intake, or any other write, creates '
                             'main again. A file it cannot remove, such as a store a running web GUI holds open on '
                             'Windows, stays on disk and is named with the reason and what to do.',
                     examples=(('metaform clear project', 'Say what clearing this folder\'s project would remove.'),
                               ('metaform clear project notes --confirm', 'Clear the project notes.')),
                     see_also=('list', 'add', 'restore')))
docs.command(Command('restore', 'Bring back what a clear removed, from the backup the clear made.',
                     ('metaform restore project [<project>] [<backup>]',),
                     description='Puts the project back as it was when the backup was made: its bases with their '
                                 'stores, the one that was active, and its report files.',
                     details='With no backup named it brings back the newest. A project that holds bases or '
                             'reports is cleared first, which backs up what it holds, so nothing is lost. '
                             'metaform list backups lists them, the newest first.',
                     examples=(('metaform restore project', "Bring back this folder's project from its newest backup."),
                               ('metaform list backups', 'List the backups of this folder\'s project.')),
                     see_also=('clear', 'list')))
docs.command(Command('remove', 'Take an empty project off the list of projects; its folder and files are not touched.',
                     ('metaform remove project [<project>] --confirm',),
                     description='Removes the project\'s registration, so it is no longer listed, and the folder '
                                 'settings that select it. Only an empty project is removed: clear it first, which '
                                 'backs it up.',
                     details='Without --confirm it says what it would do and does nothing. Nothing in the home is '
                             'deleted: the backups its clears made and its history stay, and registering the same id '
                             'again brings them back into reach, so metaform restore project can restore a backup.',
                     examples=(('metaform clear project old --confirm', 'Empty the project old, backing it up.'),
                               ('metaform remove project old --confirm', 'Then take it off the list.')),
                     see_also=('clear', 'restore', 'list')))
docs.command(Command('build', 'Build a Metaform wheel, a project archive, or a wheel carrying a project.',
                     ('metaform build',
                      ('metaform build [kind=archive|project|installer|full] [project=<id>] '
                       '[modules=<a,b>|shape=remote|map|home|everything] [files=true|false] [prompt=<file|->]')),
                     description='installer, the default, is the wheel of the modules on at home, or of the modules '
                                 'named; full carries every module found; project is the wheel with the project '
                                 'archive and the prompt for a remote agent inside it; archive is the project archive '
                                 'alone, a .zip of the project\'s data and, with files=true, its files.',
                     details='A shape is where the modules start: remote, the modules a remote agent has use for; '
                             'map, map alone; home, those on at home; everything, every module found. A project build '
                             'starts from remote. project= defaults to the folder\'s project. prompt= is a file '
                             'holding your task for the remote agent, or - for standard input; with none the agent '
                             'learns the project and waits. files= includes the project\'s files, true by default. '
                             'Building never turns a module on or off at home. A wheel carries its pure-Python '
                             'dependencies and runs directly with python <wheel>; everything is written under the '
                             "home's builds folder, a project wheel's prompt beside it as prompt.md. installer, full "
                             'and project also write metaform-<version>-<kind>.zip there, the file to send a tester: '
                             'the wheel, the prompt of a project build, and a README.md made from this version\'s '
                             'commands and modules that takes them from install to their first intake.',
                     examples=(('metaform build kind=project project=notes shape=remote',
                                'A wheel carrying notes, for a remote agent.'),
                               ('metaform build kind=archive files=false', "The folder's project's data alone.")),
                     see_also=('install', 'return', 'import')))
docs.command(Command('return', "Write a project wheel's work back as one archive to download.",
                     ('python <project wheel> return [note=<text>] [file=<path>]',),
                     description='Run from a project wheel, it writes one archive of the working layer and every '
                                 'other layer made since the project was carried, the changes to the project\'s files '
                                 'against the files the wheel carried, as diffs and new files, and the note.',
                     details='The archive goes to file=, or into the project\'s folder named <project>-return-<time>'
                             '.zip. The person adds it to their Metaform with metaform import <file>.',
                     see_also=('build', 'import')))
docs.command(Command('demo', 'Watch Metaform at work: a sample project\'s map with agents on it, in your browser.',
                     ('metaform demo', 'metaform demo --reset'),
                     description='Asks nothing and needs no AI tool, API key or account. It opens the finished map of '
                                 'Pocket Ledger, a tiny expense app with a planted bug, starts the web GUI on a free '
                                 'port, opens your browser on it and prints the address. Three scripted demo agents '
                                 'work tickets on the map, say what they find, and one finds the bug; your mascot '
                                 'greets you. It keeps going until Ctrl+C.',
                     details='It runs in a home of its own, demo inside the Metaform home, so your projects and '
                             'settings are never read or changed. Its agents call no model and no network service and '
                             'spend nothing. Run again, it reuses that home; --reset removes it first and starts '
                             'fresh. The card on the page names the next step: metaform start in your own project, '
                             'which maps it and connects Claude Code there.',
                     examples=(('metaform demo', 'Open the demo map with its agents at work.'),
                               ('metaform demo --reset', 'Start the demo fresh.')),
                     see_also=('start', 'install', 'web')))
docs.switch(Switch('--reset', 'Remove the demo\'s home and start it fresh.', used_by=('demo',)))
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


VERSION = f'metaform {__version__}'  # what metaform --version prints; the build README quotes it


def main(argv: list[str] | None = None) -> int:
    _utf8_streams()
    caller.claim()  # the web server's vouch, kept for this command alone and never passed to what it starts
    args = list(sys.argv[1:] if argv is None else argv)
    folder = Path.cwd()
    if argv is None and 'COMP_LINE' in os.environ and 'COMP_POINT' in os.environ:  # the shell's tab, complete -C
        with suppress(Exception):  # a tab that finds nothing offers nothing
            loader.follow_enabled()
            loader.discover()  # the modules' settings are switches too
            line = os.environ['COMP_LINE'][:int(os.environ['COMP_POINT'])]
            out('\n'.join(completions(line, folder)))
        return 0
    if args[:1] == ['--version']:
        return _command(args, folder)
    own_home: AbstractContextManager[Any] = nullcontext()
    if args[:1] == ['demo'] and not {'-h', '--help'} & set(args[1:]):
        from . import demo  # the demo's own home, before anything reads one, so the person's is never touched, CLI-042
        own_home = demo.own_home()
    with own_home, loader.request_scope():
        code = 1
        try:
            code = _command(args, folder)
            return code
        finally:
            try:
                changes.announce(folder, 'cli')  # what the command changed, fired on the event bus, VIEW-018
            except StoreError as error:  # a home that cannot be read: the command has said so; a done one is told
                if code == 0:
                    print(f'Notice: what this command changed was not announced: {error}', file=sys.stderr)


def _command(args: list[str], folder: Path) -> int:
    try:
        if args[:1] == ['--version']:
            out(VERSION)
            return 0
        if failed := home.make_private():  # the home is its owner's alone, made or tightened before anything reads it
            sys.stderr.write(f'Notice: {counted(len(failed), "path", "paths")} in the home could not be closed to '
                             f'other users, such as {failed[0]}; make this user their owner and run metaform again.\n')
        loader.follow_enabled()  # it reads the home, so a home it cannot read is reported as every error is, CLI-009
        from . import install
        force = (install.install_options(args[1:])[2]
                 if args[:1] == ['install'] and not any(word in ('-h', '--help') for word in args[1:])
                 else False)
        install.backstage(force)
        loader.discover()
        if not args:
            from . import archive
            if archive.carried() is not None:  # a project wheel run with nothing after it, BASE-060
                archive.first_run(folder, out)
                return 0
            status(args, folder)
            return 0
        verb, *rest = args
        if verb in ('-h', '--help'):
            out(docs.overview())
            return 0
        if verb not in VERBS:
            if loader.get(verb) is None and verb in aliases.defined(folder):
                run_alias(verb, rest, folder)
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
    except Exception as error:  # noqa: BLE001 - Report any unexpected verb failure with exit 1, BASE-031 and CLI-009.
        from .install import Failed
        sys.stdout.flush()
        if isinstance(error, Failed):
            sys.stderr.write(f'Error: {error}\nNext: {error.next_step}\n')
            return 1
        sys.stderr.write(f'Error: {type(error).__name__}: {error}\n')
        sys.stderr.write(f'Next: {"metaform list modules" if args and args[0] not in VERBS else "metaform help"}\n')
        return 1
