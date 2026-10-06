"""The MCP server, MCP-002: the official SDK's low-level Server over stdio.

Tools are computed on every request from the live module declarations and the
folder's command surface, MCP-003 and MCP-004, plus the chassis tools that
always run, `set`, `feedback`, `list_reports`, `read_report` and
`instructions`, CLI-022 and BASE-045. Opening a tool lists its commands with
their summaries; a command's arguments come when it is asked for with `help`,
CLI-037. The instructions are composed again for each request that carries
them, and a change to the tools or slash commands is announced where the
protocol allows, MCP-007 and MCP-004. Each call gets its own Context, BASE-028,
with its arguments checked as the command line checks them, MCP-005: a
coroutine verb is awaited in the server's loop, so the host's cancellation
reaches it; a plain function runs in a worker thread. The result is one text block of `say` lines, when there are
any, and one block holding the result, BASE-036.
"""
from __future__ import annotations

import dataclasses
import functools
import inspect
import json
import re
import subprocess
import sys
from collections.abc import Callable
from datetime import date
from importlib import resources
from pathlib import Path
from typing import Any, cast

import anyio

from metaform import events, home, prompt_files, settings
from metaform.data import NewerStore, Store, StoreError, prompts
from metaform.module import (
    Context,
    Module,
    Noun,
    Stop,
    Verb,
    aliases,
    call,
    chassis_version,
    command_summary,
    context,
    feedback,
    instructions,
    list_reports,
    module_instructions,
    on_surface,
    on_this_system,
    project_for,
    read_report,
    refresh_modules,
    request_scope,
    result_json,
    setting_value,
    surface,
    tool_arguments,
)

PROJECT = {'type': 'string', 'description': "A registered project id; overrides the folder's project for this call."}
LAYERS = {'type': 'array', 'items': {'type': 'string'},
          'description': 'The layers, by name or tag, toggled on for this call only.'}
NOUN_TYPES: dict[str, dict[str, Any]] = {'str': {'type': 'string'}, 'int': {'type': 'integer'},
                                         'bool': {'type': 'boolean'}}
PER_CALL = ('project', 'layers', 'confirm')
TEXT = {'type': 'string'}


def _text(description: str) -> dict[str, Any]:
    return {**TEXT, 'description': description}

Outcome = tuple[bool, list[str]]


def _here(verb: Verb) -> bool:
    return 'mcp' in verb.surfaces and on_this_system(verb)


def _described(schema: dict[str, Any], help: str) -> dict[str, Any]:
    """A property with its help as the description, so an agent reads over MCP what `metaform help` says, MCP-003."""
    return {**schema, 'description': help} if help and 'description' not in schema else schema


def setting_schema(setting: settings.Setting, folder: Path) -> dict[str, Any]:
    """A setting's JSON type over MCP, CLI-027, with its help."""
    return _described(_setting_type(setting, folder), setting.help)


def _setting_type(setting: settings.Setting, folder: Path) -> dict[str, Any]:
    if setting.kind == 'bool':
        return {'type': 'boolean'}
    if setting.kind == 'int':
        return {'type': 'integer'}
    if setting.kind == 'list':
        return {'type': 'array', 'items': {'type': 'string'}}
    if setting.kind == 'select':
        try:
            choices = setting.options(folder)
        except Exception:  # noqa: BLE001  a module's failing choices function gives a plain string, not a dead list
            choices = []
        return {'type': 'string', 'enum': choices} if choices else {'type': 'string'}
    return {'type': 'string'}


def verb_schema(verb: Verb, folder: Path) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []
    for noun in verb.nouns:
        kind = dict(noun.schema) if noun.schema is not None else ({} if noun.kind == 'json' else
                                                                  dict(NOUN_TYPES[noun.kind]))
        properties[noun.name] = _described({'type': 'array', 'items': kind} if noun.many else kind, noun.help)
        if noun.required:
            required.append(noun.name)
    for key in verb.switches:
        setting = settings.SCHEMA.get(key)
        if setting is not None:
            properties[key] = setting_schema(setting, folder)
    if verb.caution:
        properties['confirm'] = {'type': 'boolean', 'description': 'Run it. Without it the tool only explains.'}
    properties['project'] = PROJECT
    properties.setdefault('layers', LAYERS)
    return {'type': 'object', 'properties': properties, 'required': required, 'additionalProperties': False}


def tools(folder: Path) -> dict[str, tuple[Module, Verb]]:
    return {f'{module.id}_{verb.name}': (module, verb) for module in surface(folder) for verb in module.verbs
            if _here(verb)}


def set_schema(folder: Path) -> dict[str, Any]:
    properties = {key: setting_schema(setting, folder) for key, setting in settings.SCHEMA.items()}
    properties['glue'] = {'type': 'boolean', 'description': 'Keep these settings through unset all.'}
    return {'type': 'object', 'properties': properties, 'additionalProperties': False}


CHASSIS: dict[str, tuple[str, dict[str, Any]]] = {
    'feedback': (('Save feedback on the Metaform process, with a report and the shape you could not submit when you '
                 'have them. Always available.'),
                 {'type': 'object', 'required': ['text'], 'additionalProperties': False,
                  'properties': {
                      'text': _text('Feedback on the Metaform process: a problem with the process, bad semantics, a '
                                    'tool that did not match its schema, or a trouble report when you cannot continue.'),
                      'layer': _text('The layer the feedback is about, by name or id, when it is about one.'),
                      'report': _text('Your report on the project you examined, when you have one.'),
                      'shape': _text('The result you could not submit, as it stands, so a person can review and fix '
                                     'it.'),
                      'project': PROJECT}}),
    'list_reports': ('List the report, feedback and shape files of this project. Always available.',
                     {'type': 'object', 'additionalProperties': False,
                      'properties': {'kind': {'type': 'string', 'enum': ['report', 'feedback', 'shape'],
                                              'description': 'Only files of this kind.'},
                                     'layer': _text('Only files of this layer, by name or id.'),
                                     'limit': {'type': 'integer', 'description': 'How many results, 0 for all.'},
                                     'after': _text('The cursor the previous page returned.'),
                                     'project': PROJECT}}),
    'read_report': ('Read one report, feedback or shape file exactly. Always available.',
                    {'type': 'object', 'required': ['name'], 'additionalProperties': False,
                     'properties': {'name': _text('The file name, as list_reports gives it.'), 'project': PROJECT}}),
    'instructions': (('The instructions agents read, composed now for this folder, as metaform help agents prints '
                      'them; with module, that module\'s full instructions. Always available.'),
                     {'type': 'object', 'additionalProperties': False,
                      'properties': {'module': _text('A module on this folder\'s surface, by id.'),
                                     'project': PROJECT}}),
}
ORIGIN = _text('The origin, by its short id; without it, the project\'s selected origin, the one established last.')
# The clear_project prompts, MCP-031; clear_project checks its confirmation against the statement.
PROMPTS = resources.files('metaform.modules.mcp')
CLEAR_STATEMENT = prompt_files.required(PROMPTS, 'clear_statement')
SURFACED: dict[str, tuple[str, dict[str, Any]]] = {
    'add_origin': ("Establish an origin from the project's current state, as metaform add origin does, PROJ-014.",
                   {'type': 'object', 'additionalProperties': False, 'properties': {'project': PROJECT}}),
    'list_origins': ("The project's origins, as metaform list origins lists them.",
                     {'type': 'object', 'additionalProperties': False, 'properties': {'project': PROJECT}}),
    'add_variant': ('Collect a folder as a variant of an origin, as metaform add variant does, PROJ-017.',
                    {'type': 'object', 'required': ['folder'], 'additionalProperties': False,
                     'properties': {
                         'folder': _text('The folder to collect, such as a worker\'s worktree.'),
                         'origin': ORIGIN,
                         'remove': {'type': 'boolean', 'description': 'Remove the git worktree once its variant '
                                                                      'holds it.'},
                         'module': _text('The module that produced the work.'),
                         'workflow': _text('The workflow that produced the work.'),
                         'prompt': _text('The prompt the work was done from.'),
                         'model': _text('The model that did the work.'),
                         'role': _text('The role of the agent that did the work.'),
                         'blinded': {'type': 'boolean', 'description': 'Whether the agent saw only the map.'},
                         'project': PROJECT}}),
    'list_variants': ("An origin's variants, as metaform list variants lists them.",
                      {'type': 'object', 'additionalProperties': False,
                       'properties': {'origin': ORIGIN, 'project': PROJECT}}),
    'prompts': ('The stored prompts, each with its newest version number, as metaform prompts lists them.',
                {'type': 'object', 'additionalProperties': False, 'properties': {}}),
    'prompt': ("A stored prompt's text and version, the newest unless a number is given, STORE-044.",
               {'type': 'object', 'required': ['name'], 'additionalProperties': False,
                'properties': {'name': _text('The prompt, by name.'),
                               'number': {'type': 'integer', 'description': 'The version number; without it, the '
                                                                            'newest.'}}}),
    'save_prompt': (('Save a named prompt, creating its first version or adding an edit without changing earlier '
                     'versions, STORE-044.'),
                    {'type': 'object', 'required': ['name', 'text'], 'additionalProperties': False,
                     'properties': {
                         'name': _text('The prompt, by name; a new name creates a prompt.'),
                         'text': _text('The prompt text to save exactly as given.'),
                         'format': {'type': 'string', 'enum': list(prompts.FORMATS),
                                    'description': 'The format for a new prompt; defaults to text. An existing '
                                                   'prompt keeps its format.'},
                         'parent': {'type': 'integer', 'minimum': 1,
                                    'description': 'The existing version this edit came from; without it, the '
                                                   'newest. Omit this when creating a prompt.'}}}),
    'clear_project': (prompt_files.required(PROMPTS, 'clear_project'),
                      {'type': 'object', 'additionalProperties': False,
                       'properties': {'confirm': {'type': 'boolean',
                                                  'description': prompt_files.required(PROMPTS, 'clear_confirm')},
                                      'confirmation': _text(prompt_files.required(PROMPTS, 'clear_confirmation',
                                                                                  statement=CLEAR_STATEMENT)),
                                      'model': _text('Your full model designation.'),
                                      'date': _text('Date of confirmation, YYYY-MM-DD.'),
                                      'project': PROJECT}}),
    'extract': ('Write variants out to folders with Python alone, as metaform extract does, PROJ-018.',
                {'type': 'object', 'required': ['variants', 'folder'], 'additionalProperties': False,
                 'properties': {
                     'variants': {'type': 'array', 'items': {'type': 'string'},
                                  'description': 'Variant ids, or ["all"] for every variant of the origin.'},
                     'folder': _text('An empty folder; each of several variants goes into a subfolder named by '
                                     'its id.'),
                     'origin': ORIGIN, 'project': PROJECT}}),
}
JSON_TYPES: dict[str, type] = {'string': str, 'integer': int, 'boolean': bool, 'array': list}


CLEAR = prompt_files.required(PROMPTS, 'clear', statement=CLEAR_STATEMENT)
CLEAR_AGAIN = CLEAR


def _error(stop: Stop) -> Outcome:
    return True, [f'Error: {stop}\nNext: {stop.next_step}']


def _checked(name: str, arguments: dict[str, Any], schema: dict[str, Any],
             notices: list[str]) -> dict[str, Any]:
    """A chassis tool's arguments, the required ones given, each read by its declared JSON type as a module's
    nouns are, MCP-005: a text argument sent another type is kept as its JSON text and said in `notices`; a
    whole number, true or false, or a list sent another type cannot be read as its kind and stops the call."""
    properties: dict[str, Any] = schema['properties']
    for key in schema.get('required', []):
        if key not in arguments:
            raise Stop(f'{name} needs {key}.', 'metaform help commands')
    checked: dict[str, Any] = {}
    for key, value in arguments.items():
        expected = properties.get(key)
        if expected is None:
            raise Stop(f'{name} has no argument {key}.', 'metaform help commands')
        wanted = JSON_TYPES[expected['type']]
        if wanted is str and not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False)
            notices.append(f'Notice: {key}: {key} is text; what was sent was kept as its JSON text.')
        elif not isinstance(value, wanted) or (isinstance(value, bool) and wanted is not bool):
            kind = {str: 'text', int: 'a whole number', bool: 'true or false', list: 'a list'}[wanted]
            raise Stop(f'{key} is {kind}, not {value!r}.', 'metaform help commands')
        checked[key] = value
    return checked


def run_set(folder: Path, arguments: dict[str, Any]) -> Outcome:
    """The `set` tool stores settings for the server's folder, as `metaform set` would, PROJ-005 and CLI-033."""
    glue = arguments.pop('glue', False)
    changes: list[dict[str, Any]] = []
    notices: list[dict[str, str]] = []
    try:
        if not isinstance(glue, bool):
            raise Stop('glue is true or false.', 'metaform help --glue')
        read: list[tuple[str, str]] = []
        typed = {key: setting_value(key, value, folder, read) for key, value in arguments.items()}
        notices += [{'where': key, 'message': message} for key, message in read]
        for key, value in typed.items():
            try:
                settings.checked(key, value, folder, typed=True)
            except settings.SettingError as error:
                raise Stop(str(error), error.next_step or 'metaform help switches') from None
        for key, value in typed.items():
            try:
                old, new, noted = settings.put(key, value, folder, glue=glue)
            except settings.SettingError as error:
                raise Stop(str(error), error.next_step or 'metaform help switches') from None
            changes.append({'key': key, 'old': old, 'new': new})
            notices += [{'where': key, 'message': message} for message in noted]
    except Stop as stop:
        return _error(stop)
    result: dict[str, Any] = {'updated': changes, 'glued': glue}
    if notices:
        result['notices'] = notices
    return False, [result_json(result)]


def run_chassis(folder: Path, name: str, arguments: dict[str, Any]) -> Outcome:
    """`feedback`, `list_reports`, `read_report` and `instructions`: always on the surface, so an agent can always
    report and read what it is to do."""
    notices: list[str] = []
    try:
        given = _checked(name, arguments, CHASSIS[name][1], notices)
        project = given.pop('project', None)
        if name == 'feedback':
            result = result_json(feedback(folder, given.pop('text'), project=project, **given))
        elif name == 'list_reports':
            result = result_json(list_reports(folder, project=project, **given))
        elif name == 'instructions' and given.get('module'):
            result = module_instructions(folder, given['module'], project)
            if result is None:
                raise Stop(f'No module {given["module"]} with instructions on this folder\'s surface.',
                           'call metaform with command instructions and no module')
        elif name == 'instructions':
            result = instructions(folder, project)
        else:
            result = read_report(folder, given['name'], project=project)
    except Stop as stop:
        return _error(stop)
    return False, (['\n'.join(notices)] if notices else []) + [result]


def run_history(folder: Path, name: str, arguments: dict[str, Any]) -> Outcome:
    """The history, prompt and clear commands as tools, on the surface while the chassis is, PROJ-024, STORE-044,
    PROJ-025 and MCP-004."""
    notices: list[str] = []
    try:
        error, blocks = _history(folder, name, _checked(name, arguments, SURFACED[name][1], notices))
    except (Stop, StoreError) as stop:
        return _error(stop)
    return error, (['\n'.join(notices)] if notices else []) + blocks


def _history(folder: Path, name: str, given: dict[str, Any]) -> Outcome:
    """The history, prompt and clear tools once their arguments are read."""
    if name == 'prompts':
        return False, [result_json(list(prompts.prompts()))]
    if name == 'prompt':
        return False, [result_json(prompts.prompt_version(given['name'], given.get('number')))]
    if name == 'save_prompt':
        return False, [result_json(prompts.save_prompt(**given))]
    if name == 'clear_project':
        project = project_for(folder, given.pop('project', None)) or _no_project()
        caution = home.to_clear(project).caution
        confirmation_date = given.get('date', '')
        try:
            valid_date = date.fromisoformat(confirmation_date).isoformat() == confirmation_date
        except ValueError:
            valid_date = False
        if (not given.get('confirm', False) or given.get('confirmation') != CLEAR_STATEMENT
                or not given.get('model', '').strip() or not valid_date):
            raise Stop(caution, CLEAR)
        cleared = home.clear_project(project)
        result = cleared.to_dict()
        if cleared.not_removed:  # still on disk, and what to do, as a notice and never an error, BASE-044
            result['notices'] = [{'where': 'not_removed', 'message': f'{cleared.left} '
                                  f'{cleared.remedy(CLEAR_AGAIN)}'}]
        return False, [result_json(result)]
    store = Store(project_for(folder, given.pop('project', None)) or _no_project())
    if name == 'add_origin':
        known = {item.mform_sha_id for item in store.origins()}
        made = store.add_origin()
        first = store.variants(made.mform_id)
        return False, [result_json({'origin': made, 'added': made.mform_sha_id not in known,
                                    'first_variant': first[0].variant_id if first else None})]
    if name == 'list_origins':
        return False, [result_json(list(store.origins()))]
    if name == 'add_variant':
        folder_given = _within(folder, given.pop('folder'))
        origin_given = given.pop('origin', None)
        remove = bool(given.pop('remove', False))
        return False, [result_json(store.add_variant(folder_given, origin_given, remove=remove,
                                                     provenance=given))]
    if name == 'list_variants':
        return False, [result_json(list(store.variants(given.get('origin'))))]
    written = store.extract([str(item) for item in given['variants']], _within(folder, given['folder']),
                            given.get('origin'))
    return False, [result_json([str(path) for path in written])]


def _within(folder: Path, given: Any) -> Path:
    """A folder argument, taken from the server's folder when it is relative."""
    return (folder / str(given)).resolve()


def _no_project() -> str:
    raise Stop('No project for this folder.', 'metaform add project <id> <path>')


def _prepare(folder: Path, module: Module, verb: Verb, name: str, arguments: dict[str, Any],
             lines: list[str], client: str | None = None) -> Context:
    project = arguments.get('project')
    layers = arguments.get('layers')
    confirmed = arguments.get('confirm', False)
    if project is not None and not isinstance(project, str):
        raise Stop('project is a registered project id, as text.', 'metaform list projects')
    if layers is not None and (not isinstance(layers, list)
                               or not all(isinstance(item, str) for item in cast(list[Any], layers))):
        raise Stop('layers is a list of layer names or tags.', 'metaform map layers')
    if not isinstance(confirmed, bool):
        raise Stop('confirm is true or false.', f'If you are sure: call {name} and confirm true in its arguments')
    if verb.caution and not confirmed:
        raise Stop(verb.caution, f'If you are sure: call {name} and confirm true in its arguments')
    nouns, switches, notices = tool_arguments(module.id, verb, arguments, ignore=PER_CALL, folder=folder)
    lines.extend(f'Notice: {key}: {message}' for key, message in notices)
    if layers is not None:
        switches['layers'] = [str(item) for item in cast(list[Any], layers)]
    return context(module.id, folder, project=project, nouns=nouns, switches=switches, sink=lines.append,
                   surface='mcp', client=client)


OWN = 'metaform'  # the tool that holds the chassis's own commands
COMMAND = 'The command to run. Leave it out for the commands and their summaries.'
ARGUMENTS = "The command's arguments, by name, as help gives them."
HELP = "A command's name, sent without command, for what it takes."
Commands = dict[str, tuple[str, Callable[[], dict[str, Any]]]]


def _fixed(schema: dict[str, Any]) -> Callable[[], dict[str, Any]]:
    return lambda: schema


def entries(folder: Path) -> dict[str, tuple[str, Commands]]:
    """The tools the server lists, CLI-037: one for each module on the surface, named for the module, and one for
    the chassis's own commands. Each holds its commands, with the summary of each and what builds its arguments'
    schema; a command is `<module> <command>` on the command line, and over MCP the tool's name and its `command`.
    Opening a tool shows the summaries; a command's arguments are built and read with `help`."""
    found: dict[str, tuple[str, Commands]] = {}
    for module in surface(folder):
        commands: Commands = {verb.name: (verb.summary + (f' Caution: {verb.caution}' if verb.caution else ''),
                                          functools.partial(verb_schema, verb, folder))
                              for verb in module.verbs if _here(verb)}
        if commands:
            found[module.id] = (module.summary, commands)
    for name, held in aliases(folder).items():
        # An alias is one more tool, CLI-039; its commands are written as the command line writes them.
        ids = [module.id for module in held if module.id in found]
        if ids and name not in found and name != OWN:
            found[name] = (f'An alias for {", ".join(ids)}: their commands under one name.',
                           {f'{module} {command}': listed for module in ids
                            for command, listed in found[module][1].items()})
    own: Commands = {'set': ("Save settings for the server's folder, as metaform set does.",
                             functools.partial(set_schema, folder)),
                     **{name: (said, _fixed(schema)) for name, (said, schema) in CHASSIS.items()}}
    if on_surface('chassis', folder):
        own.update({name: (said, _fixed(schema)) for name, (said, schema) in SURFACED.items()})
    found[OWN] = ("Metaform's own commands: settings, feedback and reports, and the project's history and prompts.",
                  own)
    return found


def entry_schema(commands: Commands) -> dict[str, Any]:
    return {'type': 'object', 'additionalProperties': False,
            'properties': {'command': {'type': 'string', 'enum': list(commands), 'description': COMMAND},
                           'arguments': {'type': 'object', 'description': ARGUMENTS},
                           'help': {'type': 'string', 'description': HELP}}}


def entry_description(summary: str, commands: Commands) -> str:
    return f'{summary} Commands: {", ".join(commands)}. Call it with help and a command for what it takes.'


def inner(tool: str, command: str) -> str:
    """The name a command runs under: the chassis's own by its name, a module's as `<module>_<command>`. An alias's
    command is written `<module> <command>`, and runs as that module's, CLI-039."""
    if tool == OWN:
        return command
    return command.replace(' ', '_', 1) if ' ' in command else f'{tool}_{command}'


def said(tool: str, command: str) -> str:
    """How an agent is told to call a command."""
    return f'{tool} with command {command}'


async def enter(folder: Path, tool: str, given: dict[str, Any], *, client: str | None = None) -> Outcome:
    """A call to one of the listed tools. With no command it enters the tool: it returns the tool's commands with
    the summary of each. With help and no command it returns what that one command takes, CLI-037. With a command it
    runs it with its arguments."""
    known = await anyio.to_thread.run_sync(entries, folder)
    if tool not in known:
        return True, [f'Error: No tool {tool} on this surface.\nNext: metaform help commands']
    summary, commands = known[tool]
    asked = given.get('help')
    if asked is not None and 'command' not in given:
        if not isinstance(asked, str) or asked not in commands:
            return True, [f'Error: {tool} has no command {asked}.\nNext: call {tool} with no command for its commands']
        described, schema = commands[asked]
        built = await anyio.to_thread.run_sync(schema)
        return False, [result_json({'tool': tool, 'command': asked, 'summary': described, 'arguments': built})]
    unread = sorted(key for key in given if key not in ('command', 'arguments', 'help'))
    if unread and isinstance(given.get('command'), str) and isinstance(given.get('arguments') or {}, dict):
        # The command's arguments sent beside the command are its arguments; what is inside arguments wins.
        given = {'command': given['command'],
                 'arguments': {**{key: given[key] for key in unread}, **(given.get('arguments') or {})}}
    elif unread:
        return True, [(f'Error: {tool} takes command and arguments, not {", ".join(unread)}.\n'
                      f'Next: call {tool} with command and the command\'s own arguments inside arguments')]
    command, arguments = given.get('command'), given.get('arguments')
    if command is None:
        # Entering a module's tool gives its full instructions, which the compact connect-time text leaves out, MCP-029.
        own = None if tool == OWN else await anyio.to_thread.run_sync(module_instructions, folder, tool)
        return False, [result_json({'tool': tool, 'summary': summary,
                                    **({'instructions': own} if own else {}),
                                    'commands': [{'command': name, 'summary': described}
                                                 for name, (described, _) in commands.items()],
                                    'next': f"call {tool} with help and a command's name for what it takes"})]
    if not isinstance(command, str) or command not in commands:
        return True, [f'Error: {tool} has no command {command}.\nNext: call {tool} with no command for its commands']
    if arguments is not None and not isinstance(arguments, dict):
        return True, [(f'Error: arguments is an object of the command\'s arguments by name.\n'
                      f'Next: call {tool} with help {command} for what it takes')]
    return await run_tool(folder, inner(tool, command), cast(dict[str, Any], arguments or {}), said(tool, command),
                          client=client)


async def run_tool(folder: Path, name: str, arguments: dict[str, Any], called: str | None = None,
                   *, client: str | None = None) -> Outcome:
    if name == 'set':
        return await anyio.to_thread.run_sync(run_set, folder, dict(arguments))
    if name in CHASSIS:
        return await anyio.to_thread.run_sync(run_chassis, folder, name, dict(arguments))
    if name in SURFACED and await anyio.to_thread.run_sync(on_surface, 'chassis', folder):
        return await anyio.to_thread.run_sync(run_history, folder, name, dict(arguments))
    known = await anyio.to_thread.run_sync(tools, folder)
    if name not in known:
        return True, [f'Error: No tool {name} on this surface.\nNext: metaform help commands']
    module, verb = known[name]
    lines: list[str] = []
    try:
        ctx = await anyio.to_thread.run_sync(_prepare, folder, module, verb, called or name, dict(arguments), lines,
                                            client)
        if inspect.iscoroutinefunction(verb.run):
            result = await verb.run(ctx)
        else:
            result = await anyio.to_thread.run_sync(call, verb.run, ctx)
    except Stop as stop:
        return _error(stop)
    except Exception as error:  # noqa: BLE001  any failure of a module's verb goes back to the host, MCP-006
        return True, [f'Error: {type(error).__name__}: {error}\nNext: metaform list modules']
    if lines and isinstance(result, str):  # one block, so no host's way of joining blocks runs the lines into the text
        return False, ['\n'.join(lines) + '\n' + result]
    blocks = ['\n'.join(lines)] if lines else []
    if result is not None:
        blocks.append(result if isinstance(result, str) else result_json(result))
    return False, blocks


@dataclasses.dataclass(frozen=True)
class Slash:
    """One slash command, MCP-032: the command line it runs, the arguments a person gives it, and its own text."""
    name: str
    summary: str
    argv: tuple[str, ...]
    fixed: tuple[tuple[str, str], ...]
    nouns: tuple[Noun, ...]
    before: str
    after: str
    marked: bool
    runs: bool
    positional: bool = False
    parameters: tuple[Noun, ...] = ()


# A chassis command line's argument, `<name>` or `[<name>]` when optional, as its usage writes it, D105.
PLACE = re.compile(r'(\[?)<(\w+)>\]?')


def slashes(folder: Path) -> dict[str, Slash]:
    """The slash commands of the owners on this folder's command surface, the chassis's always, MCP-032 and
    MCP-033; a name a second owner declares again is left out."""
    found: dict[str, Slash] = {}
    owners: list[tuple[Any, Module | None]] = [(prompt_files.commands(resources.files('metaform')), None)]
    owners += [(prompt_files.module_commands(module.id), module) for module in surface(folder)]
    for declared, module in owners:
        for name, attrs, before, after, marked in declared:
            if name in found:
                continue
            given = attrs.get('verb')
            fixed = tuple((key, value) for key, value in attrs.items() if key not in ('verb', 'summary'))
            if module is None:
                words = tuple((given or '').split())
                places = [held for word in words if (held := PLACE.fullmatch(word))]
                nouns = tuple(Noun(held[2], '', required=not held[1]) for held in places)
                argv = tuple(word for word in words if not PLACE.fullmatch(word))
                summary = attrs.get('summary') or (command_summary(words[0]) if words else None) or ''
                found[name] = Slash(name, summary, argv, fixed, nouns, before, after, marked, given is not None,
                                    positional=True)
                continue
            verb = next((one for one in module.verbs if one.name == given), None) if given else None
            if given and verb is None:
                continue
            summary = attrs.get('summary') or (verb.summary if verb is not None else '')
            nouns = tuple(noun for noun in verb.nouns if noun.name not in dict(fixed)) if verb is not None else ()
            argv = (module.id, verb.name) if verb is not None else ()
            found[name] = Slash(name, summary, argv, fixed, nouns, before, after, marked, verb is not None,
                                parameters=verb.nouns if verb is not None else ())
    return found


def slash_text(folder: Path, slash: Slash, given: dict[str, str]) -> str:
    """The person's message a slash command puts into the conversation: its text, with the command line's output
    where it holds `<result/>`, or that output alone, exactly as `metaform` prints it in the folder, MCP-032."""
    if not slash.runs:
        return (slash.before + slash.after).strip()
    words = [*slash.argv]
    parameters = slash.parameters or slash.nouns
    bound = {**given, **dict(slash.fixed)}
    for noun in parameters:
        value = bound.get(noun.name)
        if value is None or value == '':
            if slash.positional:  # a later chassis argument would take this one's place
                break
            continue
        words.append(value if noun.required or slash.positional else f'{noun.name}={value}')
    names = {noun.name for noun in parameters}
    words += [f'{key}={value}' for key, value in slash.fixed if key not in names]
    done = subprocess.run([sys.executable, '-m', 'metaform', *words], check=False, cwd=folder, capture_output=True, text=True,
                          encoding='utf-8', stdin=subprocess.DEVNULL)
    printed = done.stdout.strip() if done.returncode == 0 else (done.stdout + done.stderr).strip()
    if not slash.marked:
        return ((slash.before + printed) if slash.before.strip() else printed).strip()
    return (slash.before + printed + slash.after).strip()


def serve(folder: Path) -> None:
    from mcp import types
    from mcp.server import Server
    from mcp.server.lowlevel import NotificationOptions
    from mcp.server.stdio import stdio_server
    from mcp.server.subscriptions import InMemorySubscriptionBus, ListenHandler, PromptsListChanged, ToolsListChanged
    from mcp.shared.exceptions import MCPError

    from .transport import Relay

    relay = Relay(folder, settings.value('mcp_recovery', folder) == 'relay')

    def build() -> list[Any]:
        return [types.Tool(name=name, description=entry_description(summary, commands),
                           input_schema=entry_schema(commands))
                for name, (summary, commands) in entries(folder).items()]

    def build_prompts() -> list[Any]:
        return [types.Prompt(name=slash.name, description=slash.summary or None, arguments=[
                    types.PromptArgument(name=noun.name, description=noun.help or None, required=noun.required)
                    for noun in slash.nouns]) for slash in slashes(folder).values()]

    # What this session was last shown, so a change made since, by any process, is announced, MCP-004: on the
    # connection to a client that connected with initialize, and on the subscriptions/listen streams of a
    # 2026-07-28 client, which is the only way that revision allows. The SDK drops whichever does not apply.
    # Both lists follow from the modules on the folder's surface and whether the chassis is on it, CLI-022.
    bus = InMemorySubscriptionBus()
    shown: dict[str, Any] = {'tools': None, 'prompts': None}

    def current() -> dict[str, Any]:
        """What each list follows: the tools also follow the folder's aliases, CLI-039."""
        both = tuple(module.id for module in surface(folder)), on_surface('chassis', folder)
        named = tuple((name, tuple(module.id for module in held)) for name, held in aliases(folder).items())
        return {'tools': (*both, named), 'prompts': both}

    async def announce(ctx: Any) -> None:
        now = await anyio.to_thread.run_sync(current)
        for kind in ('tools', 'prompts'):
            if shown[kind] is None:
                shown[kind] = now[kind]
            elif shown[kind] != now[kind]:
                shown[kind] = now[kind]
                if kind == 'tools':
                    await bus.publish(ToolsListChanged())
                    await ctx.session.send_tool_list_changed()
                else:
                    await bus.publish(PromptsListChanged())
                    await ctx.session.send_prompt_list_changed()

    async def list_tools(ctx: Any, params: Any) -> Any:
        tools = await anyio.to_thread.run_sync(build)
        shown['tools'] = (await anyio.to_thread.run_sync(current))['tools']
        return types.ListToolsResult(tools=tools)

    async def call_tool(ctx: Any, params: Any) -> Any:
        try:
            initialized = ctx.session.client_params
            client = initialized.client_info.name if initialized is not None else None
            error, blocks = await enter(folder, params.name, params.arguments or {}, client=client)
        finally:  # what the tool changed, fired on the event bus from a worker thread, VIEW-018; a module enabled or
            # disabled since this server started is loaded or dropped first, BASE-037
            await anyio.to_thread.run_sync(events.announce, folder, 'mcp')
        await announce(ctx)
        return types.CallToolResult(content=[types.TextContent(type='text', text=block) for block in blocks],
                                    is_error=error)

    async def list_prompts(ctx: Any, params: Any) -> Any:
        found = await anyio.to_thread.run_sync(build_prompts)
        shown['prompts'] = await anyio.to_thread.run_sync(current)
        return types.ListPromptsResult(prompts=found)

    async def get_prompt(ctx: Any, params: Any) -> Any:
        from mcp.shared.exceptions import MCPError
        found = await anyio.to_thread.run_sync(slashes, folder)
        slash = found.get(params.name)
        if slash is None:
            raise MCPError(-32602, f'No slash command {params.name} on this surface.\nNext: metaform help commands')
        said = await anyio.to_thread.run_sync(slash_text, folder, slash, dict(params.arguments or {}))
        await anyio.to_thread.run_sync(events.announce, folder, 'mcp')
        await announce(ctx)
        return types.GetPromptResult(description=slash.summary or None, messages=[
            types.PromptMessage(role='user', content=types.TextContent(type='text', text=said))])

    subscriptions = ListenHandler(bus)
    server = Server('metaform', version=chassis_version(), on_list_tools=list_tools, on_call_tool=call_tool,
                    on_list_prompts=list_prompts, on_get_prompt=get_prompt,
                    on_subscriptions_listen=subscriptions)

    def prepare(ctx: Any) -> None:
        """Prove schema compatibility before dispatch: construction alone does not open a Store.

        A later failure might follow a committed write or an external side effect and must never be retried.
        """
        refresh_modules()
        if ctx.method != 'tools/call':
            return
        parameters: dict[str, Any] = ctx.params or {}
        arguments: Any = parameters.get('arguments') or {}
        if not isinstance(arguments, dict):
            return  # the regular argument path supplies its error
        given: Any = cast(dict[str, Any], arguments).get('arguments') or {}
        if not isinstance(given, dict):
            return
        project = cast(dict[str, Any], given).get('project', cast(dict[str, Any], arguments).get('project'))
        if project is not None and not isinstance(project, str):
            return
        try:
            checked = context('mcp', folder, project=project, surface='mcp')
            if checked.store is not None:
                checked.store.layers(limit=1)
        except NewerStore:
            raise
        except Stop:
            pass  # ordinary argument/project errors belong to the requested command

    def refused(ctx: Any, error: NewerStore) -> dict[str, Any]:
        if ctx.method != 'tools/call':
            raise MCPError(-32603, f'Error: {error}\nNext: {error.next_step}')
        return types.CallToolResult(content=[types.TextContent(type='text', text=_error(error)[1][0])],
                                    is_error=True).model_dump(by_alias=True, exclude_none=True)

    async def live(ctx: Any, call_next: Any) -> Any:
        """The instructions, composed for the folder as this request is answered, MCP-007: `initialize` for a client
        that connects with it, and `server/discover` on the 2026-07-28 wire, each time it is asked."""
        with request_scope(fresh=True):
            try:
                await anyio.to_thread.run_sync(prepare, ctx)
            except NewerStore as error:
                retry = relay.refusal(error)
                if retry.code == -32098:
                    raise retry
                # With recovery disabled or unchanged code, the command keeps its usual behavior, including
                # commands that do not need this project's store. The preflight must not add a new gate.
            try:
                result = await call_next(ctx)
            except NewerStore as error:
                return refused(ctx, error)
            if ctx.method in ('initialize', 'server/discover') and isinstance(result, dict):
                composed = await anyio.to_thread.run_sync(instructions, folder)
                result = {**cast(dict[str, Any], result), 'instructions': composed}
            return result
    server.middleware.append(live)

    async def main() -> None:
        async with stdio_server() as (read, write):
            async def run(local_read: Any, local_write: Any) -> None:
                await server.run(local_read, local_write, server.create_initialization_options(
                    NotificationOptions(prompts_changed=True, tools_changed=True)))
            await relay.run(run, read, write, subscriptions.close)
    anyio.run(main)
