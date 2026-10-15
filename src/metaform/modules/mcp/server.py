"""The MCP server, MCP-002: the official SDK's low-level Server, over stdio or Streamable HTTP.

Every command is its own tool, MCP-003 and CLI-037: each surfaced module verb is
`<module>_<verb>`, and the chassis's own commands are `metaform_<command>`, `set`,
`feedback`, `list_reports`, `read_report`, `instructions`, `register` and `skills` always,
CLI-022 and BASE-045, and the history, prompt and clear commands while the chassis
is on the folder's surface, MCP-004. A tool is described once, where it is listed:
its description is the verb's summary, its input schema is built from the verb's
declaration as its command line is, and its annotations follow the effect the verb
declares, BASE-006. The list is computed on every request from the live
declarations and the folder's command surface, sorted, and a change to it is
announced where the protocol allows, MCP-004. Each call gets its own Context,
BASE-028, with its arguments checked as the command line checks them, MCP-005: a
coroutine verb is awaited in the server's loop, so the host's cancellation reaches
it; a plain function runs in a worker thread. The result is one text block of
`say` lines, when there are any, and one block holding the result, BASE-036, with
an object result also given as structured content.
"""
from __future__ import annotations

import dataclasses
import functools
import hashlib
import inspect
import json
import re
import subprocess
import sys
from collections import OrderedDict
from collections.abc import AsyncGenerator, Callable
from importlib import resources
from pathlib import Path
from typing import Any, Literal, cast

import anyio

from metaform import events, home, prompt_files, settings
from metaform.data import (
    NewerStore,
    Store,
    StoreError,
    plain,
    prompts,
    query_read,
    query_reads,
    reference,
)
from metaform.module import (
    Context,
    Effect,
    Module,
    Noun,
    Stop,
    Verb,
    call,
    chassis_version,
    command_summary,
    context,
    feedback,
    instructions,
    item_read,
    item_text,
    item_view,
    items_page,
    list_reports,
    module_instructions,
    node_brief,
    node_view,
    on_surface,
    on_this_system,
    project_for,
    provisioning_notice,
    read_report,
    refresh_modules,
    request_scope,
    result_json,
    serve_session,
    served_session,
    setting_value,
    startup_instructions,
    surface,
    tool_arguments,
)
from metaform.settings import refuse_held_control

from . import consent

# On each tool that uses them, MCP-025 and CLI-033: `project` on a verb that needs a project, `layers` on a verb that
# reads the map's layers; said in as few words as hold the meaning, since each is paid once per tool listed.
PROJECT = {'type': 'string', 'description': "Another registered project's id."}
LAYERS = {'type': 'array', 'items': {'type': 'string'}, 'description': 'Layers, by name or tag, on for this call.'}
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
        try:
            choices = setting.options(folder) if setting.choices is not None else []
        except Exception:  # noqa: BLE001  a module's failing choices function gives plain strings
            choices = []
        return {'type': 'array', 'items': {'type': 'string', 'enum': choices} if choices else {'type': 'string'}}
    if setting.kind == 'select':
        try:
            choices = setting.options(folder)
        except Exception:  # noqa: BLE001  a module's failing choices function gives a plain string, not a dead list
            choices = []
        return {'type': 'string', 'enum': choices} if choices else {'type': 'string'}
    return {'type': 'string'}


def verb_schema(verb: Verb, folder: Path) -> dict[str, Any]:
    """A verb's input schema: its nouns and the switches it reads, `confirm` for a caution verb, `project` when it
    needs a project, and `layers` when it reads the map's layers."""
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
        if setting is not None and not setting.person_only:  # an agent is not offered what only the person sets
            properties[key] = setting_schema(setting, folder)
    if verb.caution:
        properties['confirm'] = {'type': 'boolean', 'description': 'Run it. Without it the tool only explains.'}
    if verb.needs_project:
        properties['project'] = PROJECT
    if verb.reads_layers:
        properties.setdefault('layers', LAYERS)
    return {'type': 'object', 'properties': properties, 'required': required, 'additionalProperties': False}


def tools(folder: Path) -> dict[str, tuple[Module, Verb]]:
    """Every module verb on the folder's surface over MCP, by tool name, listed or not: a call is routed by these."""
    return {f'{module.id}_{verb.name}': (module, verb) for module in surface(folder) for verb in module.verbs
            if _here(verb)}


def set_schema(folder: Path) -> dict[str, Any]:
    """metaform_set's input schema: `glue` and `confirm`, with each setting given by its key as a further argument.
    The settings are listed by the call that gives none, `settable`, not here, where every agent paid for over a
    hundred of them before its first call; each one given is checked as `metaform set` checks it."""
    properties = {'glue': {'type': 'boolean', 'description': 'Keep these settings through unset all.'},
                  'confirm': {'type': 'boolean', 'description': 'The person confirmed a choice that lets an agent act '
                                                                'without asking; without it such a choice is refused.'}}
    return {'type': 'object', 'properties': properties, 'additionalProperties': True}


def settable(folder: Path) -> list[dict[str, Any]]:
    """The settings an agent may change here, for metaform_set called with none: each the chassis's or a module's on
    the folder's surface that serves tools here, never person-only or per-call, with its help, its JSON type, its
    choices and its value."""
    owners = {'chassis', *(module.id for module, _ in tools(folder).values())}
    listed: list[dict[str, Any]] = []
    for key, setting in settings.SCHEMA.items():
        if setting.person_only or setting.per_call or setting.owner not in owners:
            continue
        kind = _setting_type(setting, folder)
        choices = kind.get('enum') or cast(dict[str, Any], kind.get('items') or {}).get('enum')
        listed.append({'name': key, 'help': setting.help, 'type': kind['type'],
                       **({'choices': choices} if choices else {}), 'value': settings.value(key, folder)})
    return listed


CHASSIS: dict[str, tuple[str, dict[str, Any]]] = {
    'feedback': (('Save feedback on the Metaform process: a problem, bad semantics, or a trouble report when you '
                  'cannot continue. Attach your report and the shape you could not submit when you have them. Always '
                  'available.'),
                 {'type': 'object', 'required': ['text'], 'additionalProperties': False,
                  'properties': {
                      'text': _text('Feedback on the Metaform process: a problem with the process, bad semantics, a '
                                    'tool that did not match its schema, or a trouble report when you cannot continue.'),
                      'layer': _text('The layer the feedback is about, by name or id, when it is about one.'),
                      'report': _text('Your report on the project you examined, when you have one.'),
                      'shape': _text('The result you could not submit, as it stands, so a person can review and fix '
                                     'it.'),
                      'project': PROJECT}}),
    'list_reports': ('List the report, feedback and shape files saved for this project. Always available.',
                     {'type': 'object', 'additionalProperties': False,
                      'properties': {'kind': {'type': 'string', 'enum': ['report', 'feedback', 'shape'],
                                              'description': 'Only files of this kind.'},
                                     'layer': _text('Only files of this layer, by name or id.'),
                                     'limit': {'type': 'integer', 'description': 'How many results, 0 for all.'},
                                     'after': _text('The cursor the previous page returned.'),
                                     'project': PROJECT}}),
    'read_report': ('Read one saved report, feedback or shape file exactly. Always available.',
                    {'type': 'object', 'required': ['name'], 'additionalProperties': False,
                     'properties': {'name': _text('The file name, as list_reports gives it.'), 'project': PROJECT}}),
    'instructions': (('Read how to use Metaform here: the guide to this folder\'s modules and state, or one module\'s '
                      'instructions. As metaform instructions prints it; with module, that module\'s full '
                      'instructions. Always available.'),
                     {'type': 'object', 'additionalProperties': False,
                      'properties': {'module': _text('A module on this folder\'s surface, by id, or metaform for '
                                                     'Metaform\'s glossary, as metaform://metaform.'),
                                     'project': PROJECT}}),
    'register': (('Register this folder as a Metaform project, so its map can be recorded and read. As metaform add '
                  'project does; a folder already in a project is left as it is. Returns the project and the '
                  'instructions for it now. Always available.'),
                 {'type': 'object', 'additionalProperties': False,
                  'properties': {'id': _text('The project id: lowercase letters, digits, - and _. Without it, the '
                                             "folder's name.")}}),
    'skills': (('List discoverable skills, load a skill with fresh libs, or read one of its files. '
                'A name or logic.skill.<name> address loads internal skills too. Always available.'),
               {'type': 'object', 'additionalProperties': False, 'properties': {
                   'op': {'type': 'string', 'enum': ['list', 'load', 'read'],
                          'description': 'list by default, load the procedure and libs, or read one file.'},
                   'name': _text('The skill name or logic.skill.<name> address, required for load and read.'),
                   'path': _text('The relative skill file path, required for read.'),
                   'all': {'type': 'boolean', 'description': 'Include internal skills in an administrative list.'},
                   'project': PROJECT}}),
}
ORIGIN = _text('The origin, by its short id; without it, the project\'s selected origin, the one established last.')
CONFIRM = {'type': 'boolean', 'description': 'Run it. Without it the tool only explains.'}
SURFACED: dict[str, tuple[str, dict[str, Any]]] = {
    'add_origin': (("Establish an origin from the project's current state: the baseline that variants of work are "
                    'stored against. As metaform add origin does.'),
                   {'type': 'object', 'additionalProperties': False, 'properties': {'project': PROJECT}}),
    'list_origins': (("List the project's origins, the baselines variants are stored against, as metaform list "
                      'origins lists them.'),
                     {'type': 'object', 'additionalProperties': False, 'properties': {'project': PROJECT}}),
    'add_variant': (("Collect a folder, such as a worker's worktree, as a variant of an origin: the work's changes "
                     'against it. As metaform add variant does.'),
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
    'list_variants': ("List an origin's variants, as metaform list variants lists them.",
                      {'type': 'object', 'additionalProperties': False,
                       'properties': {'origin': ORIGIN, 'project': PROJECT}}),
    'prompts': ('List the stored prompts, each with its newest version number, as metaform prompts lists them.',
                {'type': 'object', 'additionalProperties': False, 'properties': {}}),
    'prompt': ("Read a stored prompt's text and version, the newest unless a number is given.",
               {'type': 'object', 'required': ['name'], 'additionalProperties': False,
                'properties': {'name': _text('The prompt, by name.'),
                               'number': {'type': 'integer', 'description': 'The version number; without it, the '
                                                                            'newest.'}}}),
    'save_prompt': (('Save a named prompt as a new version, creating it or adding an edit; earlier versions stay '
                     'unchanged.'),
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
    'clear_project': (("Clear the project's map, as metaform clear project does: remove its bases and reports. A "
                       'backup is made first, and metaform restore project brings it back; its registration, folder, '
                       'settings, origins and variants stay. Without confirm it only says what it would remove.'),
                      {'type': 'object', 'additionalProperties': False,
                       'properties': {'confirm': CONFIRM, 'project': PROJECT}}),
    'extract': (('Write variants out to folders as files you can read or run, with Python alone, as metaform '
                 'extract does.'),
                {'type': 'object', 'required': ['variants', 'folder'], 'additionalProperties': False,
                 'properties': {
                     'variants': {'type': 'array', 'items': {'type': 'string'},
                                  'description': 'Variant ids, or ["all"] for every variant of the origin.'},
                     'folder': _text('An empty folder; each of several variants goes into a subfolder named by '
                                     'its id.'),
                     'origin': ORIGIN, 'project': PROJECT}}),
}
# What each of the chassis's own tools does, declared as a module verb declares its effect, BASE-006, for the tool's
# annotations, MCP-003. add_variant can remove the worktree it collects.
CHASSIS_EFFECTS: dict[str, Effect] = {
    'set': 'write', 'feedback': 'write', 'list_reports': 'read', 'read_report': 'read', 'instructions': 'read',
    'register': 'write', 'skills': 'read', 'add_origin': 'write', 'list_origins': 'read', 'add_variant': 'remove',
    'list_variants': 'read', 'prompts': 'read', 'prompt': 'read', 'save_prompt': 'write', 'clear_project': 'remove',
    'extract': 'write'}
# The chassis's own tools of SURFACED that act on a project's records, so they are listed once the folder has one.
ON_PROJECT = ('add_origin', 'list_origins', 'add_variant', 'list_variants', 'clear_project', 'extract')
# The chassis tools whose result is text, not data, so it has no structured form.
CHASSIS_TEXT = ('instructions', 'read_report')
JSON_TYPES: dict[str, type] = {'string': str, 'integer': int, 'boolean': bool, 'array': list}


# A command line's next step, read over MCP as the tool call or resource it stands for, MCP-038. Modules write
# next steps for the command line; the server translates the forms that name a module's command or its help, so an
# agent holding tools is never sent to a shell it may not have. A chassis command line stays as written.
HELP_AGENTS = re.compile(r'\bmetaform help agents(?: (?P<module>[a-z0-9_-]+))?')
HELP_VERB = re.compile(r'\bmetaform help (?P<module>[a-z0-9_-]+)(?: (?P<verb>[a-z0-9_-]+))?')
VERB = re.compile(r'\bmetaform (?P<module>[a-z0-9_-]+) (?P<verb>[a-z0-9_-]+)(?P<help> --help)?')
ADD_PROJECT = re.compile(r'\bmetaform add project <id> <path>')  # registering this folder is a tool over MCP


def schema_step(tool: str) -> str:
    """The next step for a call that did not give what a tool takes: the tool again, as its input schema says."""
    return f'call {tool} with the arguments its input schema lists'


def mcp_next(text: str, folder: Path) -> str:
    """A next step as an MCP action where it names a module's command or help, which an agent cannot run."""
    verbs = {module.id: {verb.name for verb in module.verbs} for module in surface(folder)}

    def agents(match: re.Match[str]) -> str:
        module = match.group('module')
        return f'read resource metaform://instructions/{module}' if module else 'read resource metaform://instructions'

    def help_verb(match: re.Match[str]) -> str:
        module, verb = match.group('module'), match.group('verb')
        if module == 'commands':
            return 'list the tools' + (f' {verb}' if verb else '')
        if module == 'switches':
            return f'call {OWN}_set with no arguments for the settings it takes'
        if module not in verbs:
            return match.group(0)
        if verb in verbs[module]:
            return schema_step(f'{module}_{verb}')
        return f'read resource metaform://instructions/{module}' + (f' {verb}' if verb else '')

    def verb(match: re.Match[str]) -> str:
        module, name = match.group('module'), match.group('verb')
        if name not in verbs.get(module, ()):
            return match.group(0)
        if match.group('help'):
            return schema_step(f'{module}_{name}')
        return f'call {module}_{name}'

    text = ADD_PROJECT.sub(f'call {OWN}_register', text)
    return VERB.sub(verb, HELP_VERB.sub(help_verb, HELP_AGENTS.sub(agents, text)))


def _error(stop: Stop, folder: Path) -> Outcome:
    return True, [f'Error: {stop}\nNext: {mcp_next(str(stop.next_step), folder)}']


def _checked(name: str, arguments: dict[str, Any], schema: dict[str, Any],
             notices: list[str]) -> dict[str, Any]:
    """A chassis tool's arguments, the required ones given, each read by its declared JSON type as a module's
    nouns are, MCP-005: a text argument sent another type is kept as its JSON text and said in `notices`; a
    whole number, true or false, or a list sent another type cannot be read as its kind and stops the call."""
    properties: dict[str, Any] = schema['properties']
    for key in schema.get('required', []):
        if key not in arguments:
            raise Stop(f'{name} needs {key}.', schema_step(f'{OWN}_{name}'))
    checked: dict[str, Any] = {}
    for key, value in arguments.items():
        expected = properties.get(key)
        if expected is None:
            raise Stop(f'{name} has no argument {key}.', schema_step(f'{OWN}_{name}'))
        wanted = JSON_TYPES[expected['type']]
        if wanted is str and not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False)
            notices.append(f'Notice: {key}: {key} is text; what was sent was kept as its JSON text.')
        elif not isinstance(value, wanted) or (isinstance(value, bool) and wanted is not bool):
            kind = {str: 'text', int: 'a whole number', bool: 'true or false', list: 'a list'}[wanted]
            raise Stop(f'{key} is {kind}, not {value!r}.', schema_step(f'{OWN}_{name}'))
        checked[key] = value
    return checked


def run_set(folder: Path, arguments: dict[str, Any], consented: bool = False) -> Outcome:
    """The `set` tool stores settings for the server's folder, as `metaform set` would, PROJ-005 and CLI-033.
    `consented`: the person gave the person-only values among them in their AI tool, so they are not refused."""
    glue = arguments.pop('glue', False)
    confirm = arguments.pop('confirm', False) is True or consented  # a person's own answer to the form confirms it
    changes: list[dict[str, Any]] = []
    notices: list[dict[str, str]] = []
    try:
        if not isinstance(glue, bool):
            raise Stop('glue is true or false.', schema_step(f'{OWN}_set'))
        if not arguments:  # none given: the settings it takes, as the list is not in its schema
            return False, [result_json({'settings': settable(folder)})]
        if not consented:
            refuse_held_control(arguments, folder)
        read: list[tuple[str, str]] = []
        typed = {key: setting_value(key, value, folder, read) for key, value in arguments.items()}
        notices += [{'where': key, 'message': message} for key, message in read]
        for key, value in typed.items():
            try:
                settings.checked(key, value, folder, typed=True)
            except settings.SettingError as error:
                raise Stop(str(error), error.next_step or 'metaform help switches') from None
            if not confirm and (risked := settings.risk(key, value, folder)):
                raise Stop(f'{key} {value} is stored only when the person confirms it: {risked}',
                           'ask the person, then call set again with confirm true')
        for key, value in typed.items():
            try:
                old, new, noted = settings.put(key, value, folder, glue=glue)
            except settings.SettingError as error:
                raise Stop(str(error), error.next_step or 'metaform help switches') from None
            changes.append({'key': key, 'old': old, 'new': new})
            notices += [{'where': key, 'message': message} for message in noted]
    except Stop as stop:
        return _error(stop, folder)
    result: dict[str, Any] = {'updated': changes, 'glued': glue}
    if notices:
        result['notices'] = notices
    return False, [result_json(result)]


def run_chassis(folder: Path, name: str, arguments: dict[str, Any]) -> Outcome:
    """The always-available chassis tools: an agent can report, read instructions and load skills on any surface."""
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
                           f'call {OWN}_instructions with no module')
        elif name == 'instructions':
            result = instructions(folder, project, surface='mcp')
        elif name == 'register':
            result = result_json(register(folder, given.get('id')))
        elif name == 'skills':
            result = result_json(run_skills(given))
        else:
            result = read_report(folder, given['name'], project=project)
    except Stop as stop:
        return _error(stop, folder)
    return False, (['\n'.join(notices)] if notices else []) + [result]


def run_skills(given: dict[str, Any]) -> dict[str, Any]:
    """The universal BASE-059 skill surface, independent of the workflow module's enabled state."""
    from metaform import skills
    op = given.get('op', 'list')
    if op == 'list':
        return {'skills': skills.listing(discoverable=not given.get('all', False))}
    if op not in ('load', 'read'):
        raise Stop(f'No skills operation {op}.', f'call {OWN}_skills with op=list, load or read')
    name = given.get('name')
    if not name:
        raise Stop(f'skills {op} needs name.', schema_step(f'{OWN}_skills'))
    if op == 'load':
        return skills.load(name)
    path = given.get('path')
    if not path:
        raise Stop('skills read needs path.', schema_step(f'{OWN}_skills'))
    return {'name': name, 'path': path, 'text': skills.read(name, path)}


def client_name(ctx: Any) -> str | None:
    """Use the connecting request's identity, including modern per-request metadata, before session identity."""
    params = getattr(ctx, 'params', None)
    if isinstance(params, dict):
        given = cast(dict[str, Any], params)
        meta = given.get('_meta')
        info: Any = given.get('clientInfo') or (cast(dict[str, Any], meta).get('io.modelcontextprotocol/clientInfo')
                                                if isinstance(meta, dict) else None)
        if isinstance(info, dict):
            name = cast(dict[str, Any], info).get('name')
            if isinstance(name, str):
                return name
    initialized = ctx.session.client_params
    return initialized.client_info.name if initialized is not None else None


HOST_KEEPS = 2048  # the characters of the connect message Claude Code keeps, MCP-029


def fallback_skills(folder: Path, client: str | None = None) -> list[dict[str, Any]]:
    """The discoverable skills a connecting harness is told of, BASE-059: none with skill_index off, or auto where a
    completed native deployment already provides them."""
    from metaform import install, skills
    mode = settings.value('skill_index', folder)
    if mode == 'off' or (mode == 'auto' and client and install.skills_deployed(client)):
        return []
    return skills.listing(discoverable=True)


def skills_said(folder: Path, client: str | None = None) -> str:
    """metaform_skills' description, closed by the names of `fallback_skills`: tool descriptions are listed by every
    host and no host cuts them, so the names reach the agent when the connect message has no room for the index."""
    said = CHASSIS['skills'][0]
    names = ', '.join(one['name'] for one in fallback_skills(folder, client))
    named = prompt_files.module('mcp', 'skills_discoverable', skills=names) if names else None
    return f'{said} {named}' if named else said


def skill_index(folder: Path, client: str | None = None, room: int | None = None) -> str:
    """Fallback discovery only where a completed native deployment does not provide it, BASE-059. Within `room`
    characters: each skill with its description, else the names alone, for metaform_skills op=list to describe, else
    nothing here, since what passes the host's cut never arrives; metaform_skills' description names them still."""
    entries = fallback_skills(folder, client)
    if not entries:
        return ''
    lines = '\n'.join(f'{one["name"]}: {one["description"]}' for one in entries)
    for listed in (lines, ', '.join(one['name'] for one in entries)):
        index = prompt_files.module('mcp', 'skill_index', skills=listed) or ''
        if room is None or len(index) <= room:
            return index
    return ''


TOLD: set[str] = set()  # the agent sessions this server has given the provisioning notice, or found no need to


def provisioning(session: str | None) -> str | None:
    """The first-run provisioning notice, MCP-028, for the agent session of a stdio server, whose AI tool is the one
    that started it, while the home has not recorded that tool and the session has not been told; None with no
    session, which is how an HTTP connect, whose client did not start the server, is asked."""
    if session is None or session in TOLD:
        return None
    said = provisioning_notice()
    if said is None:
        TOLD.add(session)
        return None
    return f'Notice: {said}'


def connect_instructions(folder: Path, client: str | None = None, session: str | None = None) -> str:
    """The usual startup instructions, then the provisioning notice for `session` when it is due and fits within the
    characters the host keeps, else it comes with the session's first tool result, then the connecting harness's
    fallback skill discovery, together within those characters."""
    started = startup_instructions(folder)
    notice = provisioning(session)
    if notice is not None and session is not None and len(started) + 1 + len(notice) <= HOST_KEEPS:
        started = f'{started}\n{notice}'
        TOLD.add(session)
    return '\n'.join(one for one in (started, skill_index(folder, client, HOST_KEEPS - len(started) - 1)) if one)


def register(folder: Path, given: str | None = None) -> dict[str, Any]:
    """Register the server's folder as a project, the first step of onboarding, MCP-009, through the same path as
    metaform add project. A folder already in a project answers with it and changes nothing. The answer carries the
    instructions composed now, since the ones sent at connect are not sent again."""
    held = home.folder_project(folder)
    if held is not None:
        said = f'This folder is already in project {held}; nothing was changed.'
    else:
        chosen = given or home.project_id_for(folder)
        try:
            said = home.add_project(chosen, folder)
        except StoreError as error:
            raise Stop(str(error), f'call {OWN}_register with another id') from None
        held = chosen
    return {'project': held, 'said': said, 'instructions': instructions(folder, surface='mcp')}


def run_history(folder: Path, name: str, arguments: dict[str, Any], consented: bool = False) -> Outcome:
    """The history, prompt and clear commands as tools, on the surface while the chassis is, PROJ-024, STORE-044,
    PROJ-025 and MCP-004. `consented`: the person said yes to the call's caution in their AI tool."""
    notices: list[str] = []
    try:
        error, blocks = _history(folder, name, _checked(name, arguments, SURFACED[name][1], notices), consented)
    except (Stop, StoreError) as stop:
        return _error(stop, folder)
    return error, (['\n'.join(notices)] if notices else []) + blocks


def _history(folder: Path, name: str, given: dict[str, Any], consented: bool = False) -> Outcome:
    """The history, prompt and clear tools once their arguments are read."""
    if name == 'prompts':
        return False, [result_json(list(prompts.prompts()))]
    if name == 'prompt':
        return False, [result_json(prompts.prompt_version(given['name'], given.get('number')))]
    if name == 'save_prompt':
        return False, [result_json(prompts.save_prompt(**given))]
    if name == 'clear_project':
        project = project_for(folder, given.pop('project', None)) or _no_project()
        again = f'call {OWN}_clear_project with confirm true'
        if not (given.get('confirm', False) or consented):  # the person's yes, as confirm or through the form
            raise Stop(home.to_clear(project).caution, f'If you are sure: {again}')
        cleared = home.clear_project(project)
        result = cleared.to_dict()
        if cleared.not_removed:  # still on disk, and what to do, as a notice and never an error, BASE-044
            result['notices'] = [{'where': 'not_removed', 'message': f'{cleared.left} '
                                  f'{cleared.remedy(again + " again")}'}]
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
    raise Stop('No project for this folder.', f'call {OWN}_register')


def _prepare(folder: Path, module: Module, verb: Verb, name: str, arguments: dict[str, Any],
             lines: list[str], client: str | None = None, consented: bool = False,
             session: str | None = None, identity: dict[str, str] | None = None) -> Context:
    project = arguments.get('project')
    layers = arguments.get('layers')
    confirmed = arguments.get('confirm', False)
    if project is not None and not isinstance(project, str):
        raise Stop('project is a registered project id, as text.', "omit project for the folder's own project")
    if layers is not None and (not isinstance(layers, list)
                               or not all(isinstance(item, str) for item in cast(list[Any], layers))):
        raise Stop('layers is a list of layer names or tags.', 'call map_layers for their names')
    if not isinstance(confirmed, bool):
        raise Stop('confirm is true or false.', f'If you are sure: call {name} with confirm true')
    if project is not None and not verb.needs_project:  # the argument is on the tools that use it, as listed
        raise Stop(f'{name} takes no project: it works without one.', schema_step(name))
    if layers is not None and not verb.reads_layers:
        raise Stop(f"{name} takes no layers: it does not read the map's layers.", schema_step(name))
    if verb.caution and not (confirmed or consented):
        raise Stop(verb.caution, f'If you are sure: call {name} with confirm true')
    if not consented:
        refuse_held_control((key for key in arguments if key in verb.switches), folder)
    nouns, switches, notices = tool_arguments(module.id, verb, arguments, ignore=PER_CALL, folder=folder)
    lines.extend(f'Notice: {key}: {message}' for key, message in notices)
    if layers is not None:
        switches['layers'] = [str(item) for item in cast(list[Any], layers)]
    return context(module.id, folder, project=project, nouns=nouns, switches=switches, sink=lines.append,
                   surface='mcp', client=client, session=session, identity=identity)


# The headers Paperclip's tool gateway forwards with each call, its connection's forwardContextHeaders, ticket T3 of
# artifacts/swarm-2026-10-11/PAPERCLIP-INTEGRATION.md: the agent, the issue and the run the call is made in.
PAPERCLIP_HEADERS = (('agent', 'x-paperclip-agent-id'), ('issue', 'x-paperclip-issue-id'), ('run', 'x-paperclip-run-id'))


def gateway_identity(headers: Any) -> dict[str, str]:
    """The IDs supplied by Paperclip for this request, copied without changing the server's environment."""
    if headers is None:
        return {}
    return {f'{name}_id': value for name, header in PAPERCLIP_HEADERS
            if (value := str(headers.get(header) or '').strip())}


def gateway_session(headers: Any) -> str | None:
    """The agent session of a call through Paperclip's gateway, from the headers it forwards, MCP-042: credited to
    that agent, and kept apart per run, so what one run was shown is never taken as shown to another, MCP-039. None
    for a call that carries none of them, which keeps the session this server gives."""
    from urllib.parse import quote
    identity = gateway_identity(headers)
    # A run may work on several issues. Counts already delivered to that run stay delivered as the issue changes.
    keys = ('agent', 'run') if 'run_id' in identity else ('agent', 'issue')
    named = ','.join(f'{name}={quote(identity[name + "_id"], safe="")}'
                     for name in keys if name + '_id' in identity)
    return f'paperclip:{named}' if named else None


OWN = 'metaform'  # the prefix of the chassis's own tools, metaform_<command>, as a module's are <module>_<verb>
# How long a client may keep a list before asking again, the cache hints of MCP 2026-07-28. The lists change only when
# a person enables, disables or narrows modules, and a change is announced, MCP-004; a minute bounds what a client that
# does not listen keeps. Private, since what is listed is this folder's.
CACHE_TTL_MS = 60_000
# The connections whose last shown lists are kept, MCP-004: the SDK says nothing when an HTTP session ends, so the record
# is bounded, the least recently heard from dropped first; such a connection takes the lists it asks for next unannounced.
CONNECTIONS = 256
STDIO = 'stdio'  # the one connection a stdio server has, its process serving one host


def _fixed(schema: dict[str, Any]) -> Callable[[], dict[str, Any]]:
    return lambda: schema


@dataclasses.dataclass(frozen=True)
class Listed:
    """One tool as the server lists it, MCP-003: its name, its description, what builds its input schema from the
    declaration, and what it declares it does, for its annotations."""
    name: str
    description: str
    schema: Callable[[], dict[str, Any]]
    effect: Effect
    open_world: bool = False
    task: bool | Literal['run'] = False  # the verb can take long, so a client declaring tasks gets a task; 'run': its run
    guide: Callable[[], str] = lambda: ''  # what comes with its first use in a session, MCP-039: what the list cut
    module: str = 'metaform'  # the module that serves it, whose rules come with the first use of any of its tools

    def annotations(self) -> dict[str, bool]:
        """The four hints, each set from the declared effect. None is left out, since an absent hint falls back on
        the protocol's defaults, which take a tool to be a destructive write that reaches the open world."""
        return {'read_only_hint': self.effect == 'read', 'destructive_hint': self.effect == 'remove',
                'idempotent_hint': self.effect == 'read', 'open_world_hint': self.open_world}


SENTENCE = re.compile(r'(?<=\.)\s')  # where a description's first sentence ends


def glossary(folder: Path) -> str:
    """metaform://metaform: the system glossary, the mcp module's glossary prompt exactly as written and nothing more,
    how to operate in Metaform; the same for every folder, and for a project named metaform too. The tools and the
    modules' rules are metaform://tools, the project's own terms metaform://<project>, each read once on its own. The
    text is `metaform instructions metaform`'s, MCP-003, made in one place."""
    return module_instructions(folder, 'metaform') or ''


def tool_index(folder: Path) -> list[tuple[str, str]]:
    """Every tool on the folder's surface by name with the first sentence of its description, its caution left out:
    the glossary view's list."""
    return [(name, SENTENCE.split(one.description.split(' Caution:')[0], maxsplit=1)[0])
            for name, one in listing(folder).items()]


CLAUSE = re.compile(r'(?<=[\w>)])[:;]\s')  # where a first sentence's head ends and its details begin
AS_DOES = re.compile(r',? as metaform [\w -]+? (?:does|gives|lists|prints)(?: them| it)?(?=[,.:;]|$)')
AS_DOES_ALONE = re.compile(r'\s*\bAs metaform [\w -]+? (?:does|gives|lists|prints)(?: them| it)?\.')  # a sentence of it
BARE_VERB = re.compile(r'(?<![\w_-])(?P<module>[a-z0-9_]+) (?P<verb>[a-z0-9-]+)(?= <)')  # `map activate <its name>`
LINE = 64  # the characters a tool's line is cut back toward, at a comma
LINE_LEAST = 32  # and the fewest it is cut to


def short_line(description: str) -> str:
    """One tool's line in metaform://tools: the head of its description's first sentence, what it does, before the
    details a colon or semicolon opens, with the command it matches left out; the details come with the tool."""
    first = SENTENCE.split(description.split(' Caution:')[0], maxsplit=1)[0]
    head = CLAUSE.split(AS_DOES.sub('', first), maxsplit=1)[0].strip().rstrip('.')
    while len(head) > LINE and ', ' in head:  # a long head keeps its leading phrases, each whole
        shorter = head.rsplit(', ', 1)[0]
        if len(shorter) < LINE_LEAST:  # cut no further than still says what the tool does
            break
        head = shorter
    return head


def tools_text(folder: Path) -> str:
    """metaform://tools: every tool on the folder's surface in one line, grouped under the prefix of the module that
    serves it (`map_`, then `  where: ...` for map_where), for a host that lists tools by name only; then the rules of
    the modules on the surface, MCP-031. Read once, when the agent needs it; nothing here is pushed."""
    named = tools(folder)
    groups: dict[str, list[str]] = {}
    for name, one in listing(folder).items():
        module = named[name][0].id if name in named else OWN
        groups.setdefault(module, []).append(f'  {name.removeprefix(module + "_")}: {short_line(one.description)}')
    heading = prompt_files.module('mcp', 'tool_index')
    index = '\n'.join(f'{module}_\n' + '\n'.join(lines) for module, lines in groups.items())
    parts = [part for part in ((heading + '\n' if heading else '') + index, rules(folder)) if part]
    return '\n\n'.join(parts) + '\n'


def rules(folder: Path) -> str:
    """The rules block that closes metaform://tools: mcp's `rules_heading`, then each rule of each module on the
    folder's surface, in module id order, as `[module] <rule> Why: <why>`; empty when no module there holds a rule, so
    an agent is handed each rule once, with its reason and the module it comes from."""
    heading = prompt_files.module('mcp', 'rules_heading')
    lines = [f'[{module.id}] {said} Why: {why}' for module in surface(folder)
             for said, why in prompt_files.module_rules(module.id)]
    return heading + '\n' + '\n'.join(lines) if heading and lines else ''


def listing(folder: Path, client: str | None = None) -> dict[str, Listed]:
    """Every tool the server lists, by name in order, CLI-037 and MCP-003: each surfaced module verb as
    `<module>_<verb>`, described by its summary and its caution, and the chassis's own commands as
    `metaform_<command>`, the history, prompt and clear commands only while the chassis is on the folder's surface,
    MCP-004. Each command is described once, here, with its arguments' schema built from its declaration, so an agent
    plans a call from the list alone and the list is the same on every connection to the folder, but for the skill
    names metaform_skills' description gives the `client` harness, BASE-059. Until the folder has a project, only
    what runs without one is listed: the verbs that declare `needs_project` false and the chassis's own tools but
    those of SURFACED that act on a project's records; registering lists the rest, announced as a change, MCP-004."""
    registered = project_for(folder) is not None
    states: dict[Callable[[Path], bool], bool] = {}

    def can(verb: Verb) -> bool:
        """Whether the verb is listed in the folder's state now, MCP-004: each state read once per listing."""
        if not (registered or not verb.needs_project):
            return False
        if verb.listed is None:
            return True
        if verb.listed not in states:
            try:
                states[verb.listed] = bool(verb.listed(folder))
            except Exception:  # noqa: BLE001  a state that cannot be read lists the verb, which says why if it cannot act
                states[verb.listed] = True
        return states[verb.listed]
    found: dict[str, Listed] = {}
    for name, (module, verb) in tools(folder).items():
        if not can(verb):
            continue
        said, more = headed(verb.summary + (f' Caution: {verb.caution}' if verb.caution else ''))
        built = functools.partial(verb_schema, verb, folder)
        found[name] = Listed(name, tool_named(said, folder), functools.partial(briefed, built), verb.effect,
                             verb.open_world, verb.task, functools.partial(verb_guide, verb, more, built, folder),
                             module.id)
    own: dict[str, tuple[str, Callable[[], dict[str, Any]]]] = {
        'set': (('Save settings for this folder, each given as name=value. Called with none, it lists the settings '
                 'an agent may change, each with its help, choices and current value.'),
                functools.partial(set_schema, folder)),
        **{name: (said, _fixed(schema)) for name, (said, schema) in CHASSIS.items()
           if name != 'register' or not registered},  # registering is the first step, listed until it is taken
        'skills': (skills_said(folder, client), _fixed(CHASSIS['skills'][1]))}
    if on_surface('chassis', folder):
        own.update({name: (said, _fixed(schema)) for name, (said, schema) in SURFACED.items()
                    if registered or name not in ON_PROJECT})
    for name, (said, build) in own.items():
        head, more = headed(said)
        found[f'{OWN}_{name}'] = Listed(f'{OWN}_{name}', tool_named(head, folder), functools.partial(briefed, build),
                                        CHASSIS_EFFECTS[name], guide=functools.partial(own_guide, more, build, folder))
    return dict(sorted(found.items()))


DESCRIPTION_MOST = 160  # the characters a tool's description is listed whole within; a longer one keeps its first sentence
HELP_MOST = 80  # the bytes an argument's help is listed within; the whole help comes with the tool's first use
SCOPE = 30  # the characters within which a help's head before its first colon is a scope, such as `list and add`
SENTENCE_MOST = 200  # the characters a listed first sentence keeps; a longer one is listed to its first colon or semicolon


def headed(description: str) -> tuple[str, str]:
    """A tool's description as it is listed, and the rest, which comes with its first use in a session, MCP-039: a
    description over DESCRIPTION_MOST characters is listed as its first sentence, what the tool does and when to use
    it, and its caution, which is never cut; the rest is moved word for word."""
    said, _, caution = description.partition(' Caution: ')
    first, *rest = SENTENCE.split(said, maxsplit=1)
    head, more = (said, '') if len(description) <= DESCRIPTION_MOST else (first, rest[0] if rest else '')
    if len(head) > SENTENCE_MOST and len(parts := CLAUSE.split(head, maxsplit=1)) > 1:
        head, more = parts[0], ' '.join(part for part in (parts[1], more) if part)
    head = AS_DOES.sub('', head.rstrip('.')).rstrip(',') + '.'  # an agent with tools has no command line to compare
    return head + (f' Caution: {caution}' if caution else ''), more


def short_help(help: str) -> str:
    """An argument's help as its schema lists it: whole within HELP_MOST bytes, else the head of its first sentence,
    before the details a colon or semicolon opens, cut back at a comma; the whole help comes with the tool's first
    use. Its words are the help's own."""
    if len(help.encode('utf-8')) <= HELP_MOST:
        return help
    first = SENTENCE.split(help, maxsplit=1)[0]
    cut = CLAUSE.search(first)
    head = first if cut is None else first[:cut.start()]
    if cut is not None and cut.group().startswith(':') and cut.start() < SCOPE:  # `list and add: an element`: the
        head = f'{head}: {CLAUSE.split(first[cut.end():], maxsplit=1)[0]}'  # scope, then what it is
    head = head.strip().rstrip('.,;:')
    room = HELP_MOST - len('…'.encode())
    while len(head.encode('utf-8')) > room and ', ' in head:
        head = head.rsplit(', ', 1)[0]
    while len(head.encode('utf-8')) > room and ' ' in head:  # one long clause keeps its first words
        head = head.rsplit(' ', 1)[0]
    return head + ('.' if head == help.rstrip('.') else '…')


def briefed(build: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """A tool's input schema as it is listed: each argument's help in brief, MCP-039."""
    schema = build()
    properties = cast(dict[str, dict[str, Any]], schema.get('properties') or {})
    return {**schema, 'properties': {key: {**one, 'description': short_help(str(one['description']))}
                                     if isinstance(one.get('description'), str) else one
                                     for key, one in properties.items()}}


def _arguments_said(schema: dict[str, Any]) -> list[str]:
    """Each argument whose help the list cut, with its whole help."""
    properties = cast(dict[str, dict[str, Any]], schema.get('properties') or {})
    return [f'{key}: {one["description"]}' for key, one in properties.items()
            if isinstance(one.get('description'), str) and short_help(str(one['description'])) != one['description']]


def verb_guide(verb: Verb, more: str, build: Callable[[], dict[str, Any]], folder: Path) -> str:
    """What a module verb's tool gives with its first use, MCP-039: the rest of its description, each argument whose
    help the list cut with its whole help, the verb's details and its examples, each a call; all from its declaration."""
    examples = [f'{mcp_next(command, folder)}: {said}' for command, said in verb.examples]
    parts = [more, '\n'.join(_arguments_said(build())), mcp_next(verb.details, folder), '\n'.join(examples)]
    return '\n\n'.join(part.strip() for part in parts if part.strip())


def own_guide(more: str, build: Callable[[], dict[str, Any]], folder: Path) -> str:
    """What a chassis tool gives with its first use: the rest of its description and its arguments' whole help."""
    parts = [mcp_next(more, folder), '\n'.join(_arguments_said(build()))]
    return '\n\n'.join(part.strip() for part in parts if part.strip())


def tool_named(text: str, folder: Path) -> str:
    """A listed description with each module command it names as a command line written as its tool's name, since an
    agent holding tools may have no shell, MCP-038."""
    verbs = {module.id: {verb.name for verb in module.verbs} for module in surface(folder)}

    def named(match: re.Match[str]) -> str:
        module, verb = match.group('module'), match.group('verb')
        return f'{module}_{verb}' if verb in verbs.get(module, ()) else match.group(0)
    text = AS_DOES_ALONE.sub('', ADD_PROJECT.sub(f'{OWN}_register', text))
    return BARE_VERB.sub(named, VERB.sub(named, text))


def guidance(folder: Path, listed: Listed, ctx: Context) -> str:
    """What a tool's result carries the first time in the session it is called, and again only once what it says has
    changed, MCP-039, as the counts at a node are given: the rules of its module the first time any of the module's
    tools is called, from the module's prompts.xml, and the tool's own guide, from its declaration. Each heading is the
    mcp module's `module_guide` and `tool_guide` prompt; an empty one leaves that part out. First, once, the
    provisioning notice a stdio connect had no room for, MCP-028."""
    parts: list[str] = []
    session = ctx.session if served_session() is not None else None
    if session is not None and (notice := provisioning(session)) is not None:
        parts.append(notice)
        TOLD.add(session)
    rules = [f'{said} Why: {why}' for said, why in prompt_files.module_rules(listed.module)] \
        if listed.module != OWN else []
    heading = prompt_files.module('mcp', 'module_guide', module=listed.module) if rules else None
    if heading:
        text = heading + '\n' + '\n'.join(rules)
        if ctx.seen(f'guide:module:{listed.module}', _digest(text)) != _digest(text):
            parts.append(text)
    said = listed.guide()
    heading = prompt_files.module('mcp', 'tool_guide', tool=listed.name) if said else None
    if heading:
        text = heading + '\n' + said
        if ctx.seen(f'guide:tool:{listed.name}', _digest(text)) != _digest(text):
            parts.append(text)
    return '\n\n'.join(parts)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]


def needs(folder: Path, name: str, arguments: dict[str, Any]) -> consent.Ask | None:
    """The form a call needs the person to answer before it runs, CLI-011: the caution it carries, and the person-only
    settings it asks to change; None when it needs neither, or names no tool here, so the call answers as it does."""
    own = name[len(OWN) + 1:] if name.startswith(OWN + '_') else ''
    if own == 'set':
        return consent.form(name, None, consent.held({key: value for key, value in arguments.items()
                                                      if key != 'glue'}, folder), folder)
    if own == 'clear_project':
        named = arguments.get('project')
        try:
            project = project_for(folder, named if isinstance(named, str) else None) \
                if on_surface('chassis', folder) else None
        except (Stop, StoreError):
            return None  # the call says what is wrong with the project it names
        return None if project is None else consent.form(name, home.to_clear(project).caution, {}, folder)
    found = None if own else tools(folder).get(name)
    if found is None:
        return None
    verb = found[1]
    return consent.form(name, verb.caution or None, consent.held(
        {key: value for key, value in arguments.items() if key in verb.switches}, folder), folder)


async def run_tool(folder: Path, name: str, arguments: dict[str, Any], *, client: str | None = None) -> Outcome:
    """A call to one listed tool by its name: whether it failed, and its text blocks."""
    error, blocks, _ = await answer(folder, name, arguments, client=client)
    return error, blocks


async def answer(folder: Path, name: str, arguments: dict[str, Any], *, client: str | None = None,
                 consented: bool = False, session: str | None = None,
                 identity: dict[str, str] | None = None) -> tuple[bool, list[str], dict[str, Any] | None]:
    """A call to one listed tool, as `run_tool`, with the result's structured form when it is an object, BASE-036:
    the same data as the text block holding it, for a host that reads tool output as data. `consented`: the person
    said yes to the call in their AI tool, so its caution and its person-only settings need no more from the agent."""
    own = name[len(OWN) + 1:] if name.startswith(OWN + '_') else ''
    if own == 'set':
        error, blocks = await anyio.to_thread.run_sync(run_set, folder, dict(arguments), consented)
        return error, blocks, _structured(error, blocks)
    if own in CHASSIS:
        error, blocks = await anyio.to_thread.run_sync(run_chassis, folder, own, dict(arguments))
        return error, blocks, None if own in CHASSIS_TEXT else _structured(error, blocks)
    if own in SURFACED and await anyio.to_thread.run_sync(on_surface, 'chassis', folder):
        error, blocks = await anyio.to_thread.run_sync(run_history, folder, own, dict(arguments), consented)
        return error, blocks, _structured(error, blocks)
    known = await anyio.to_thread.run_sync(tools, folder)
    if name not in known:
        return True, [f'Error: No tool {name} on this surface.\nNext: list the tools'], None
    module, verb = known[name]
    lines: list[str] = []
    try:
        ctx = await anyio.to_thread.run_sync(_prepare, folder, module, verb, name, dict(arguments), lines, client,
                                             consented, session, identity)
        if inspect.iscoroutinefunction(verb.run):
            result = await verb.run(ctx)
        else:
            result = await _threaded(verb.run, ctx)
    except Stop as stop:
        error, blocks = _error(stop, folder)
        return error, blocks, None
    except Exception as error:  # noqa: BLE001  any failure of a module's verb goes back to the host, MCP-006
        return True, [(f'Error: {type(error).__name__}: {error}\nNext: call {OWN}_feedback and say what you '
                       'called')], None
    if lines and isinstance(result, str):  # one block, so no host's way of joining blocks runs the lines into the text
        return False, ['\n'.join(lines) + '\n' + result], None
    blocks = ['\n'.join(lines)] if lines else []
    if result is not None:
        blocks.append(result if isinstance(result, str) else result_json(result))
    data = None if result is None or isinstance(result, str) else plain(result)
    return False, blocks, cast(dict[str, Any], data) if isinstance(data, dict) else None


async def _threaded(run: Any, ctx: Any) -> Any:
    """A verb run in a thread, shielded: a thread cannot be stopped, so a cancel waits for it either way, and its
    result is kept for the caller rather than dropped after its effect landed; the cancel takes effect after."""
    with anyio.CancelScope(shield=True):
        return await anyio.to_thread.run_sync(call, run, ctx)


def _structured(error: bool, blocks: list[str]) -> dict[str, Any] | None:
    """A chassis tool's result block as data, when it is a JSON object, as the tool wrote it with `result_json`."""
    if error or not blocks:
        return None
    try:
        data = json.loads(blocks[-1])
    except ValueError:
        return None
    return cast(dict[str, Any], data) if isinstance(data, dict) else None


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


# Resources, MCP-037: the texts an agent reads at discovery, before any tool runs. The chassis serves the instructions,
# each module's instructions, the stored prompts and the reports; a module serves what it declares, each read through
# one of its verbs with no arguments. A command's arguments are in its tool's input schema, MCP-003. Every address of
# the map resolves too: `metaform://<address>` is that node's brief, and `metaform://<address>/items/<n>` the one
# item numbered n there, so any agent, and the person, reads any node at any time. The item's number is in the path,
# not in a fragment, which RFC 3986 leaves to the client and a client may strip before resources/read; the fragment
# form `metaform://<address>#<n>`, as items are named, is still read.
INSTRUCTIONS_URI = 'metaform://instructions'
# The system glossary, the mcp module's glossary prompt, which the connect instructions tell every agent to read first.
# It replaced metaform://glossary, with no alias kept (Phase 1c, item 8).
GLOSSARY_URI = 'metaform://metaform'
TOOLS_URI = 'metaform://tools'  # each tool in one line and the modules' rules, for a host that defers tool descriptions
TEMPLATES: tuple[tuple[str, str, str], ...] = (
    ('metaform://instructions/{module}', "A module's instructions",
     "One module's full instructions, as metaform_instructions gives them with module. module is a module's id."),
    ('metaform://prompts/{name}', 'A stored prompt', "A stored prompt's newest text and version, by name."),
    ('metaform://reports/{name}', 'A report file', ('One report, feedback or shape file exactly, by the name '
                                                    'list_reports gives.')),
)
TEMPLATE_PATTERNS = {uri: re.compile('^' + re.sub(r'\{(\w+)\}', r'(?P<\1>[^/]+)', uri) + '$')
                     for uri, _, _ in TEMPLATES}
# The address templates, listed after the fixed ones: an address holds no `/`, so it never reads as a templated URI,
# and a fixed resource, the project's glossary or a module's resource is served first, so `metaform://metaform`,
# `metaform://<project>` and `metaform://instructions` are never read as addresses.
BRIEF_TEMPLATE = 'metaform://{address}'
ITEM_TEMPLATE = 'metaform://{address}/items/{n}'
ITEM_ALIAS = 'metaform://{address}#{n}'  # the fragment form, read and completed, not listed
ADDRESS_TEMPLATES: tuple[tuple[str, str, str, str], ...] = (
    (BRIEF_TEMPLATE, "A node's brief", ("One node of the map by its address, such as metaform://code.manager.route: "
                                        "the element, what relies on it and what it relies on, with how much is held "
                                        "at it and around it and the call that reads each."), 'application/json'),
    (ITEM_TEMPLATE, 'One item at a node', ("The one memory, ticket, question or message numbered n at an address, n "
                                           "in hex as it is shown, such as metaform://code.manager.route/items/1f: its "
                                           "title, why, body and links."), 'text/plain'),
)
ADDRESS = re.compile(r'^metaform://(?P<address>[^/#?\s]+)'
                     r'(?:/items/(?P<path>[0-9A-Fa-f]{1,15})|#(?P<number>[0-9A-Fa-f]{1,15}))?$')


class Missing(Exception):
    """A resource whose address or item does not exist: refused with the protocol's code for a missing resource,
    -32602, and a next step."""

    def __init__(self, message: str, next_step: str) -> None:
        super().__init__(message)
        self.next_step = next_step


def brief(folder: Path, address: str, client: str | None = None) -> str:
    """`metaform://<address>`: the node's brief as the chassis gives it, the map module's own `where` read, given whole
    every time; the web GUI shows the same brief."""
    try:
        text = node_brief(folder, address, client=client)
    except Stop as stop:
        raise Missing(f'No node {address} here: {stop}', f'call map_where with the address\'s parent, or read '
                                                          f'{GLOSSARY_URI} for what an address is') from None
    if text is None:
        raise Missing(f'No map is served here, so {address} does not resolve.', 'list the resources')
    return text


def item(folder: Path, address: str, number: int) -> str:
    """`metaform://<address>#<n>`: the one item numbered n at the address, from the module that wrote it."""
    found = item_read(folder, address, number)
    if found is None:
        raise Missing(f'No item {reference(address, number)} here.',
                      f'read metaform://{address}, whose counts name what is held there, or call map_item '
                      f'with {address} for its latest number')
    return item_text(found)


def project_uri(folder: Path) -> str | None:
    """`metaform://<project>`, the folder's project's own glossary, or None when the folder is no registered project.
    A project named metaform has its terms at metaform://metaform's side, never in its place: that URI always serves
    Metaform's own glossary."""
    project = project_for(folder)
    return None if project is None or f'metaform://{project}' == GLOSSARY_URI else f'metaform://{project}'


def project_glossary_text(folder: Path, client: str | None = None) -> str:
    """`metaform://<project>`: the project's own glossary as the map module generates it, the register standard then
    the project's terms in the form of Metaform's own glossary, called through `metaform.module.project_glossary`;
    while the map module is off here, the register standard the map module ships, exactly as written, and mcp's
    `project_glossary_absent` note saying why there are no terms."""
    from metaform import module as chassis
    generate = getattr(chassis, 'project_glossary', None)  # the map module's generator, Phase 1c item 8
    try:
        text = generate(folder, client=client) if generate is not None else None
    except Stop:
        text = None
    if text:
        return text if text.endswith('\n') else text + '\n'
    standard = prompt_files.module('map', 'register_standard') or ''
    note = prompt_files.module('mcp', 'project_glossary_absent') or ''
    return '\n\n'.join(part for part in (standard, note) if part) + '\n'


def resource_list(folder: Path) -> list[dict[str, Any]]:
    """The fixed resources: Metaform's glossary, the project's own, the tools in one line each, the instructions, then
    each surfaced module's declared resources."""
    own = project_uri(folder)
    listed = [{'uri': GLOSSARY_URI, 'name': 'Metaform glossary',
               'description': 'Read first: the terms every agent works by in Metaform, the mcp module\'s glossary '
                              'prompt as written.',
               'mime_type': 'text/plain'},
              *([{'uri': own, 'name': 'Project glossary',
                  'description': "This project's own terms after the peer register standard, generated from its map.",
                  'mime_type': 'text/plain'}] if own else []),
              {'uri': TOOLS_URI, 'name': 'Tools',
               'description': "Each Metaform tool in one line, by module, then the rules the modules ask you to keep.",
               'mime_type': 'text/plain'},
              {'uri': INSTRUCTIONS_URI, 'name': 'Agent instructions',
               'description': "The guide to this folder's modules and state, as metaform instructions prints it.",
               'mime_type': 'text/plain'}]
    for module in surface(folder):
        listed += [{'uri': held.uri, 'name': held.name, 'description': held.description, 'mime_type': held.mime_type}
                   for held in module.resources if not held.fields]
    return listed


def module_templates(folder: Path) -> list[tuple[str, str, str, str]]:
    """Each surfaced module's resource templates, a URI with `{field}` parts each read through the module's verb
    with the fields as its nouns, MCP-037: as (template, name, description, media type)."""
    return [(held.uri, held.name, held.description, held.mime_type)
            for module in surface(folder) for held in module.resources if held.fields]


async def read_resource_text(folder: Path, uri: str, *, client: str | None = None) -> tuple[str, str] | None:
    """A resource's text and media type, or None when this folder serves no such resource. metaform://metaform is
    read first, so it is Metaform's own glossary whatever the folder's project or modules are called."""
    if uri == GLOSSARY_URI:
        return await anyio.to_thread.run_sync(glossary, folder), 'text/plain'
    for module in await anyio.to_thread.run_sync(surface, folder):
        for held in module.resources:
            fields = held.matched(uri)
            if held.uri == uri or fields is not None:
                kinds = {noun.name: noun.kind for verb in module.verbs if verb.name == held.verb for noun in verb.nouns}
                given = {name: int(value) if kinds.get(name) == 'int' and value.isdigit() else value
                         for name, value in (fields or {}).items()}  # a number in the path is a number noun
                error, blocks = await run_tool(folder, f'{module.id}_{held.verb}', given, client=client)
                if error and fields is not None:  # a template's URI naming what is not there, MCP-037
                    message, _, step = blocks[0].removeprefix('Error: ').partition('\nNext: ')
                    raise Missing(message, step or 'list the resources and their templates')
                if error:
                    raise Stop(blocks[0], 'read resource ' + INSTRUCTIONS_URI)
                return '\n'.join(blocks), held.mime_type
    if uri == TOOLS_URI:
        return await anyio.to_thread.run_sync(tools_text, folder), 'text/plain'
    if uri == INSTRUCTIONS_URI:
        return await anyio.to_thread.run_sync(functools.partial(instructions, folder, surface='mcp')), 'text/plain'
    if uri == await anyio.to_thread.run_sync(project_uri, folder):
        return await anyio.to_thread.run_sync(project_glossary_text, folder, client), 'text/plain'
    matched = next(((name, held.groupdict()) for name, pattern in TEMPLATE_PATTERNS.items()
                    if (held := pattern.match(uri))), None)
    if matched is None:
        addressed = ADDRESS.match(uri)
        if addressed is None:
            return None
        given = addressed.group('path') or addressed.group('number')
        if given is None:
            text = await anyio.to_thread.run_sync(brief, folder, addressed.group('address'), client)
            return text, 'application/json' if text.startswith('{') else 'text/plain'
        number = int(given, 16)
        return await anyio.to_thread.run_sync(item, folder, addressed.group('address'), number), 'text/plain'
    template, fields = matched
    if template.startswith('metaform://instructions/'):
        text = await anyio.to_thread.run_sync(module_instructions, folder, fields['module'])
        return (text, 'text/plain') if text is not None else None
    if template.startswith('metaform://prompts/'):
        return result_json(await anyio.to_thread.run_sync(prompts.prompt_version, fields['name'], None)), 'application/json'
    return await anyio.to_thread.run_sync(read_report, folder, fields['name']), 'text/plain'


def run_verb(folder: Path, module_id: str, verb_name: str, nouns: dict[str, Any]) -> Any:
    """One module verb run for the person through the server, whatever its surfaces: the answer a person gave in a
    form their AI tool showed, or a read a view makes. Stops when the module is not on the folder's surface."""
    found = next((module for module in surface(folder) if module.id == module_id), None)
    verb = None if found is None else next((one for one in found.verbs if one.name == verb_name), None)
    if verb is None:
        raise Stop(f'No {module_id} {verb_name} on this folder\'s surface.', f'metaform enable {module_id}')
    return call(verb.run, context(module_id, folder, nouns=nouns, surface='mcp'))


VIEW_LIMIT = 200  # the most items a view lists at a node, newest first
VIEW_SCHEMA: dict[str, Any] = {
    'type': 'object', 'required': ['read'], 'additionalProperties': False,
    'properties': {'read': _text('What the view reads: brief, items or item at an address, trace for a ticket\'s '
                                 'sessions, glossary, focus for the Address the agent last named, or one of the '
                                 'map\'s named reads, as the web GUI reads it.'),
                   'params': {'type': 'object', 'additionalProperties': {'type': ['string', 'number', 'boolean']},
                              'description': 'The read\'s arguments, as the web GUI passes them.'}}}


def view_read(folder: Path, name: str, params: dict[str, Any]) -> Any:
    """What the map and node views read through metaform_view, MCP-037: a node's brief, the items numbered at it, one
    item, the memory graph, or one of the map's named reads with the web GUI's arguments. Only the folder's own
    project is read; a view asks nothing else of the server."""
    project = project_for(folder) or _no_project()
    given = {str(key): str(value).lower() if isinstance(value, bool) else str(value)
             for key, value in params.items() if value is not None}
    if given.get('project', project) != project:
        raise Stop(f'This view shows {project} only.', f'open the web GUI for {given["project"]}')
    if name == 'projects':
        return {'projects': [{'id': project}], 'opened': project}
    if name == 'brief':  # what the web GUI's /api/brief gives, so the map view draws the same brief
        kinds = tuple(kind for kind in given.get('kind', '').split(',') if kind)
        return node_view(folder, given.get('address', ''), cursor=given.get('cursor'), kinds=kinds, project=project)
    if name == 'items':
        return items_at(folder, project, given.get('address', ''), given.get('cursor'))
    if name == 'item':  # what the web GUI's /api/item gives
        return item_view(folder, given.get('item', ''), project=project)
    if name.startswith('memory-'):
        nouns = {'node': given['node']} if name == 'memory-note' and given.get('node') else {}
        return run_verb(folder, 'memory', name[len('memory-'):], nouns)
    if name == 'glossary':
        return glossary_view(folder)
    if name == 'trace':
        return trace_view(folder, given.get('id', ''), given.get('digest', ''))
    if name not in query_reads():
        raise Stop(f'The view does not read {name}.', 'open the web GUI for the rest of the page')
    record = home.project(project)
    chosen = given.get('layers')
    toggled = [one for one in chosen.split(',') if one] if chosen is not None else \
        settings.toggled_layers(Path(record.path)) if record is not None else []
    store = Store(project, toggled=toggled, base=given.get('base') or None)
    return query_read(store, name, {key: value for key, value in given.items() if key not in VIEW_RESERVED})


VIEW_RESERVED = ('project', 'metaform', 'layers')  # what picks the store and its layers, as the web GUI reads them
TERM = re.compile(r'^\s*\{(?P<term>[^{}]+)\}\s*:=\s*(?P<definition>.+?)\s*$')
SECTION = re.compile(r'^\s*//\s*-*\s*(?P<title>.+?)\s*-*\s*$')


def glossary_view(folder: Path) -> dict[str, Any]:
    """What the glossary view draws, MCP-037: the mcp module's glossary prompt as written, `text`, with each term
    defined in it (`{TERM} := "definition"`, quoted) taken out with the section it stands in, its definition exactly as
    written inside its quotes; then the tools on the folder's surface and the rules of its modules, as metaform://tools
    gives them. Nothing is reworded: a term the view shows is the prompt's own line."""
    written = prompt_files.module('mcp', 'glossary') or ''
    terms: list[dict[str, str]] = []
    section = ''
    for line in written.splitlines():
        heading = SECTION.match(line)
        if heading:
            section = heading.group('title')
            continue
        found = TERM.match(line)
        if found is None:
            continue
        said = found.group('definition')
        if len(said) > 1 and said[0] == said[-1] == '"':  # a defined term; `{Mode} := SYSTEM_PRELOAD` sets a state
            terms.append({'term': found.group('term'), 'definition': said[1:-1], 'section': section})
    tools = [{'name': name, 'summary': said} for name, said in tool_index(folder)]
    ruled = [{'module': module.id, 'rule': said, 'why': why} for module in surface(folder)
             for said, why in prompt_files.module_rules(module.id)]
    return {'text': written, 'terms': terms, 'tools': tools, 'rules': ruled, 'uri': GLOSSARY_URI}


def trace_view(folder: Path, work_id: str, seen: str = '') -> dict[str, Any]:
    """What the trace view draws, MCP-037: the ticket, as map_work reads it, and its agent sessions with their threads,
    as dispatch_sessions reads them; with no ticket, every session without its thread, to pick one from. `digest`
    names what was read, so a view that already holds it is answered with `unchanged` alone: the view reads again
    every few seconds while it is on screen, and a line the agent is still writing changes in place."""
    nouns: dict[str, Any] = {'id': work_id} if work_id else {'thread': False}
    found = plain(run_verb(folder, 'dispatch', 'sessions', nouns))
    ticket: Any = None
    if work_id:
        try:
            ticket = plain(run_verb(folder, 'map', 'work', {'id': work_id}))
        except (Stop, StoreError):
            ticket = None
    digest = hashlib.sha256(json.dumps([found, ticket], sort_keys=True, default=str).encode()).hexdigest()[:20]
    if seen and seen == digest:
        return {'digest': digest, 'unchanged': True}
    return {'digest': digest, 'id': work_id or None, 'ticket': ticket, **cast(dict[str, Any], found)}


def items_at(folder: Path, project: str, address: str, cursor: str | None = None) -> dict[str, Any]:
    """The items numbered at an address, newest first, a page of `VIEW_LIMIT`, each with its reference, number, title,
    kind, why and module, MCP-037: `items_page`, the list the web GUI's brief reads too, paged as MCP pages a list,
    `cursor` the `nextCursor` the page before gave."""
    if not address:
        raise Stop('items needs an address.', 'read items with params.address')
    listed = items_page(folder, address, cursor=cursor, limit=VIEW_LIMIT, project=project)
    try:
        reading = plain(query_read(Store(project), 'element', {'ref': address})).get('reading')
    except (Stop, StoreError, AttributeError):
        reading = None
    return {'address': address, 'reading': reading, 'latest': Store(project).latest_number(address),
            **listed}


COMPLETE_LIMIT = 100  # the most values one completion carries, as the protocol allows
ADDRESS_ARGUMENTS = ('address', 'node', 'item')  # a prompt argument named so takes an Address or <address>#<n>


def completions(folder: Path, kind: str, ref: str, argument: str, value: str,
                known: dict[str, str] | None = None) -> list[str]:
    """What completes an argument, MCP-037: an Address one segment at a time, from the map's own children read; a
    number at an address, or `<address>#<n>`, from the items numbered there; a module for the instructions template;
    a stored prompt's name. `kind` is `resource` for a resource template, `prompt` for a slash command. Empty when the
    argument takes nothing known here."""
    known = known or {}
    if kind == 'resource' and ref in (BRIEF_TEMPLATE, ITEM_TEMPLATE, ITEM_ALIAS) and argument == 'address':
        return _addresses(folder, value, items=False)
    if kind == 'resource' and ref in (ITEM_TEMPLATE, ITEM_ALIAS) and argument == 'n':
        return [number for number in _numbers(folder, known.get('address', ''), value)]
    if kind == 'resource' and ref == 'metaform://instructions/{module}' and argument == 'module':
        return sorted(module.id for module in surface(folder) if module.id.startswith(value))
    if kind == 'resource' and ref == 'metaform://prompts/{name}' and argument == 'name':
        return sorted(one.name for one in prompts.prompts() if one.name.startswith(value))
    if kind == 'prompt' and argument in ADDRESS_ARGUMENTS:
        return _addresses(folder, value, items=True)
    return []


def _addresses(folder: Path, value: str, *, items: bool) -> list[str]:
    """Addresses that complete `value`: the children of its parent that start with it, and, when it names a node,
    that node's children; with `items`, a value holding `#` completes the numbers at its address."""
    project = project_for(folder)
    if project is None:
        return []
    if items and '#' in value:
        address, _, prefix = value.partition('#')
        return [f'{address}#{number}' for number in _numbers(folder, address, prefix)]
    store = Store(project)

    def children(of: str) -> list[str]:
        try:
            return [str(one) for one in plain(query_read(store, 'children', {'address': of})).get('results', [])]
        except (Stop, StoreError):
            return []
    parent = value.rsplit('.', 1)[0] if '.' in value else ''
    found = [one for one in children(parent) if one.startswith(value)]
    if value and value in found:
        found += children(value)
    return sorted(dict.fromkeys(found))


def _numbers(folder: Path, address: str, prefix: str) -> list[str]:
    """The numbers taken at an address, newest first, in hex as they are shown, that start with `prefix`: from the
    address's counter alone, no item read, since a completion is a hint; a number whose item was deleted is said so
    when it is read."""
    project = project_for(folder)
    if project is None or not address:
        return []
    try:
        top = Store(project).latest_number(address)
    except StoreError:
        return []
    asked = prefix.lower()
    if asked.strip('0123456789abcdef'):
        return []
    found: list[str] = []
    for number in range(top, 0, -1):
        shown = f'{number:x}'
        if shown.startswith(asked):
            found.append(shown)
            if len(found) == COMPLETE_LIMIT:
                break
    return found


# ChatGPT's connectors and deep research call two tools by exactly these names, so they break the <module>_<verb> rule,
# MCP-003: the mcp module serves them itself, read-only, over HTTP and the cloud tunnel by default (mcp_search_fetch).
SEARCH_FETCH: dict[str, tuple[str, dict[str, Any]]] = {
    'search': (('Search this Metaform: the map\'s layer items, the memories and the project\'s terms. Returns ids '
                'to read with fetch.'),
               {'type': 'object', 'properties': {'query': {'type': 'string', 'description': 'The words to find.'}},
                'required': ['query'], 'additionalProperties': False}),
    'fetch': ('Read one result of search by its id: a node\'s brief, an item, or a glossary.',
              {'type': 'object', 'properties': {'id': {'type': 'string', 'description': 'An id search returned, a '
                                                                                      'metaform:// URI.'}},
               'required': ['id'], 'additionalProperties': False}),
}
SEARCH_LIMIT = 20


async def search(folder: Path, query: str, client: str | None = None) -> dict[str, Any]:
    """ChatGPT's `search`: `{"results": [{"id", "title", "url"}]}`, at most SEARCH_LIMIT. Each id is the metaform://
    URI fetch reads: a layer item's hit is the node it is held at, a memory's the node it is attached to (knowledge
    attaches to the receiving element), a term's the project's glossary."""
    words = [word for word in query.lower().split() if word]
    if not words:
        return {'results': []}
    hits: list[dict[str, str]] = []

    def add(uri: str, title: str) -> None:
        if len(hits) < SEARCH_LIMIT and all(one['id'] != uri for one in hits):
            hits.append({'id': uri, 'title': title[:200], 'url': uri})
    known = await anyio.to_thread.run_sync(tools, folder)
    if 'map_search' in known:
        error, _, data = await answer(folder, 'map_search', {'text': query}, client=client)
        for found in cast(list[Any], (data or {}).get('results') or []) if not error else []:
            target: Any = cast(dict[str, Any], found).get('target') if isinstance(found, dict) else None
            if isinstance(target, dict) and cast(dict[str, Any], target).get('kind') in ('element', 'type'):
                address = str(cast(dict[str, Any], target).get('id') or '')
                value = cast(dict[str, Any], found).get('value')
                add(f'metaform://{address}', f'{address}: {value if isinstance(value, str) else json.dumps(value)}')
    if 'memory_search_nodes' in known:
        error, _, data = await answer(folder, 'memory_search_nodes', {'query': query}, client=client)
        names = [str(cast(dict[str, Any], one).get('name')) for one in
                 cast(list[Any], (data or {}).get('entities') or []) if isinstance(one, dict)] if not error else []
        if names and 'memory_joins' in known:
            error, _, joined = await answer(folder, 'memory_joins', {}, client=client)
            where: dict[str, str] = {}
            for join in cast(list[Any], (joined or {}).get('joins') or []) if not error else []:
                if isinstance(join, dict):
                    held = cast(dict[str, Any], join)
                    where.setdefault(str(held.get('entity')), str(held.get('receiver') or held.get('address') or ''))
            for name in names:
                if where.get(name):
                    add(f'metaform://{where[name]}', f'{where[name]}: memory {name}')
    own = await anyio.to_thread.run_sync(project_uri, folder)
    texts = [(own, await anyio.to_thread.run_sync(project_glossary_text, folder, client))] if own else []
    texts.append((GLOSSARY_URI, await anyio.to_thread.run_sync(glossary, folder)))
    for uri, text in texts:
        line = next((line.strip() for line in text.splitlines() if all(word in line.lower() for word in words)), None)
        if line:
            add(uri, line)
    return {'results': hits}


async def fetch(folder: Path, given: str, client: str | None = None) -> dict[str, Any]:
    """ChatGPT's `fetch`: `{"id", "title", "text", "url", "metadata"}`, the text read as resources/read reads it."""
    try:
        found = await read_resource_text(folder, given, client=client)
    except (Missing, Stop, StoreError) as error:
        return {'id': given, 'error': str(error)}
    if found is None:
        return {'id': given, 'error': f'No resource {given} here; use an id search returned.'}
    text, mime = found
    addressed = ADDRESS.match(given)
    title = addressed.group('address') if addressed else given.removeprefix('metaform://')
    return {'id': given, 'title': title, 'text': text, 'url': given, 'metadata': {'mimeType': mime}}


def build(folder: Path, *, http: bool = False) -> tuple[Any, Any, Any]:
    """The MCP server for the folder, MCP-002, with the relay that keeps a stdio connection over a schema upgrade and
    the listen handler a stdio session closes: one server whichever transport carries it. `http`: it is reached over
    HTTP, directly or through the cloud broker's tunnel, which is where ChatGPT's `search` and `fetch` are offered
    (mcp_search_fetch).

    Beside the core it serves the extensions a client declares, each only to a client that declares it: MCP Apps, the
    map and node views; the tasks extension, for verbs that can take long; and elicitation, by multi round-trip
    requests on the July 2026 wire, for what only the person says yes to. Completion fills Address arguments and
    `#n` references, and a client listening for a node's brief hears when items are added there."""
    from contextlib import asynccontextmanager

    from mcp import types
    from mcp.server import Server
    from mcp.server.caching import CacheHint
    from mcp.server.lowlevel import NotificationOptions
    from mcp.server.models import InitializationOptions
    from mcp.server.request_state import RequestStateBoundary, RequestStateSecurity
    from mcp.server.session import ServerSession
    from mcp.server.streamable_http import MCP_SESSION_ID_HEADER
    from mcp.server.subscriptions import (
        InMemorySubscriptionBus,
        ListenHandler,
        PromptsListChanged,
        ResourcesListChanged,
        ResourceUpdated,
        ToolsListChanged,
    )
    from mcp.shared.exceptions import MCPError
    from mcp_types.version import MODERN_PROTOCOL_VERSIONS

    from . import tasks as tasked
    from . import views
    from .transport import RETRY, Relay

    relay = Relay(folder, not http and settings.value('mcp_recovery', folder) == 'relay')
    apps_on = bool(settings.value('mcp_apps', folder))
    apps_always = settings.value('mcp_apps_offer', folder) == 'always'
    offered = settings.value('mcp_search_fetch', folder)
    searching = offered == 'always' or (offered == 'remote' and http)
    tokens = consent.Tokens()  # the forms asked and not yet answered, each answer taken once
    running = tasked.Running()  # the tool calls this process runs as tasks
    held: dict[str, Any] = {}  # the task group tasks run in, while the server runs

    def capabilities(ctx: Any) -> Any:
        return ctx.session.client_capabilities

    def apps(ctx: Any) -> bool:
        """Whether this request's client renders MCP Apps, and the person lets the views be offered: to a client that
        declares the extension, or, with mcp_apps_offer always, to every client, for a host that renders them without
        saying so, as the specification's reference host does."""
        return apps_on and (apps_always or views.supported(capabilities(ctx)))

    # The Address the agent last named in a call, per viewer: an open view reads it (`focus`) and turns to it, so
    # what the agent discusses is what the person sees. `seq` grows with each call, so a view turns once per call. On
    # a Metaform Node the viewer is the signed-in account its authorization server named, so two people using the
    # same AI tool never turn each other's views; elsewhere it is the client's name, oauth.viewer.
    focus: dict[str, dict[str, Any]] = {}

    def viewer(ctx: Any) -> str:
        from .oauth import viewer as signed_in
        return signed_in(ctx) or client_of(ctx) or ''

    def discussed(ctx: Any, name: str, arguments: dict[str, Any]) -> None:
        said = views.discussed(arguments)
        if said is None or not apps(ctx):
            return
        held = focus.get(viewer(ctx), {})
        focus[viewer(ctx)] = {'address': said, 'tool': name, 'seq': int(held.get('seq', 0)) + 1}

    def client_of(ctx: Any) -> str | None:
        return client_name(ctx)

    def tool(one: Listed, shown: bool) -> Any:
        hints = one.annotations()
        view = views.SHOWN_BY.get(one.name) if shown else None
        made = types.Tool(name=one.name, description=one.description, input_schema=one.schema(),
                          annotations=types.ToolAnnotations(
                              read_only_hint=hints['read_only_hint'], destructive_hint=hints['destructive_hint'],
                              idempotent_hint=hints['idempotent_hint'], open_world_hint=hints['open_world_hint']))
        if view:
            made.meta = {'ui': {'resourceUri': view}}
        return made

    # The views' own tool, listed only to a client that renders the views and hidden from its model, MCP Apps'
    # visibility ["app"]: a view calls it through its host for what it draws.
    view_tool = types.Tool(
        name=views.TOOL, description='Read what the map and node views draw. Called by the views, not the model.',
        input_schema=VIEW_SCHEMA,
        annotations=types.ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True,
                                          open_world_hint=False))
    view_tool.meta = {'ui': {'visibility': ['app']}}

    # ChatGPT's two, by the names it calls: read-only, over the map, memory and the terms (mcp_search_fetch).
    searched_tools = [types.Tool(name=name, description=description, input_schema=schema,
                                 annotations=types.ToolAnnotations(read_only_hint=True, destructive_hint=False,
                                                                   idempotent_hint=True, open_world_hint=False))
                      for name, (description, schema) in SEARCH_FETCH.items()]

    def build(shown: bool, client: str | None = None) -> list[Any]:
        listed = [tool(one, shown) for one in listing(folder, client).values()]
        if searching:
            listed = sorted([*listed, *searched_tools], key=lambda one: one.name)
        return sorted([*listed, view_tool], key=lambda one: one.name) if shown else listed

    def build_prompts() -> list[Any]:
        return [types.Prompt(name=slash.name, description=slash.summary or None, arguments=[
                    types.PromptArgument(name=noun.name, description=noun.help or None, required=noun.required)
                    for noun in slash.nouns]) for slash in slashes(folder).values()]

    # What was last shown, so a change made since, by any process, is announced, MCP-004, once to each client: on the
    # subscriptions/listen streams of a 2026-07-28 client, which is the only way that revision allows, by the bus and
    # what it last told; and on the connection of each client that connected with initialize, by what that connection
    # was last shown. The SDK makes a session for every request, so a connection is known by its transport: the one a
    # stdio process serves, or an HTTP client's Mcp-Session-Id. The SDK drops whichever does not apply.
    # Both lists follow from the modules on the folder's surface and whether the chassis is on it, CLI-022.
    bus = InMemorySubscriptionBus()
    bus_shown: dict[str, Any] = {'tools': None, 'prompts': None, 'resources': None}
    connections: OrderedDict[str, dict[str, Any]] = OrderedDict()
    notices: dict[str, tuple[Any, Callable[[ServerSession], Any]]] = {
        'tools': (ToolsListChanged, ServerSession.send_tool_list_changed),
        'prompts': (PromptsListChanged, ServerSession.send_prompt_list_changed),
        'resources': (ResourcesListChanged, ServerSession.send_resource_list_changed)}

    def current() -> dict[str, Any]:
        """What each list follows: the tools are the names listed, which change with the modules on the surface."""
        both = tuple(module.id for module in surface(folder)), on_surface('chassis', folder)
        return {'tools': tuple(listing(folder)), 'prompts': both, 'resources': both[0]}

    def conn_key(ctx: Any) -> str | None:
        """The caller's connection; None on the July wire, which has none to announce on, and for an HTTP request
        that names no session."""
        if ctx.protocol_version in MODERN_PROTOCOL_VERSIONS:
            return None
        if ctx.request is None:
            return STDIO
        return ctx.request.headers.get(MCP_SESSION_ID_HEADER)

    def connection(ctx: Any) -> dict[str, Any] | None:
        """What the caller's connection was last shown, kept for the CONNECTIONS heard from last."""
        key = conn_key(ctx)
        if key is None:
            return None
        own = connections.pop(key, None) or {'tools': None, 'prompts': None, 'resources': None}
        connections[key] = own
        while len(connections) > CONNECTIONS:
            connections.popitem(last=False)
        return own

    async def to_bus(kind: str, now: Any) -> None:
        """Publish a change from what the bus last told, for the listen streams; the first value is taken unsaid."""
        if bus_shown[kind] is not None and bus_shown[kind] != now:
            await bus.publish(notices[kind][0]())
        bus_shown[kind] = now

    async def announce(ctx: Any) -> None:
        now = await anyio.to_thread.run_sync(current)
        own = connection(ctx)
        for kind in ('tools', 'prompts', 'resources'):
            await to_bus(kind, now[kind])
            if own is not None:
                if own[kind] is not None and own[kind] != now[kind]:
                    await notices[kind][1](ctx.session)
                own[kind] = now[kind]
        await watch.check()

    async def listed_now(ctx: Any, kind: str) -> None:
        """A list was just given: the listen streams hear a change first, and the caller's own connection has seen
        it, while every other connection's record waits for that connection's next request."""
        now = (await anyio.to_thread.run_sync(current))[kind]
        await to_bus(kind, now)
        own = connection(ctx)
        if own is not None:
            own[kind] = now

    async def list_tools(ctx: Any, params: Any) -> Any:
        tools = await anyio.to_thread.run_sync(build, apps(ctx), client_of(ctx))
        await listed_now(ctx, 'tools')
        return types.ListToolsResult(tools=tools)

    def declined(name: str) -> Any:
        said = prompt_files.module('mcp', 'consent_declined') or 'The person declined.'
        return types.CallToolResult(content=[types.TextContent(
            type='text', text=f'Error: {said}\nNext: call {name} again if the person changes their mind')],
            is_error=True)

    async def consented(ctx: Any, params: Any, name: str,
                        arguments: dict[str, Any]) -> tuple[dict[str, Any] | None, Any]:
        """The arguments the person let the call run with, the person-only values they chose among them; or the
        result the call answers with now: the form to fill on the July wire, or the refusal when they declined.
        `(arguments, None)` unchanged when the call needs no form or none can be shown."""
        if not await anyio.to_thread.run_sync(consent.can_ask, capabilities(ctx), folder):
            return arguments, None
        ask = await anyio.to_thread.run_sync(needs, folder, name, arguments)
        if ask is None:
            return arguments, None
        if ctx.protocol_version in MODERN_PROTOCOL_VERSIONS:  # multi round-trip: ask, then read the retry's answer
            raw = cast(dict[str, Any], dict(ctx.params or {}))
            responses: Any = raw.get('inputResponses') or {}
            answer_given: Any = cast(dict[str, Any], responses).get(consent.FORM) if isinstance(responses, dict) else None
            if not isinstance(answer_given, dict) or not tokens.spend(params.request_state):
                return None, types.InputRequiredResult(input_requests={consent.FORM: types.ElicitRequest(
                    params=types.ElicitRequestFormParams(message=ask.message, requested_schema=ask.schema))},
                    request_state=tokens.mint())
            answered = cast(dict[str, Any], answer_given)
            action, content = str(answered.get('action')), answered.get('content')
        else:  # the 2025 handshake: the form is a request of the server's while the call waits
            try:
                got = await ctx.session.elicit_form(ask.message, ask.schema, related_request_id=ctx.request_id)
            except Exception:  # noqa: BLE001  a client that cannot show it keeps the plain rule
                return arguments, None
            action, content = got.action, got.content
        values = ask.accepted(action, cast(dict[str, Any] | None, content))
        if values is None:
            return None, declined(name)
        return {**arguments, **values}, True

    def outcome(error: bool, blocks: list[str], structured: dict[str, Any] | None) -> Any:
        # A result that carries a picture, `image` with its base64 `data` and `mimeType`, as web look does: the picture
        # is the tool's image content, and the text and the structured result name it rather than repeat it.
        picture: Any = (structured or {}).get('image')
        images: list[Any] = []
        shown = cast(dict[str, Any], picture) if isinstance(picture, dict) else {}
        if isinstance(shown.get('data'), str):
            data, kind = str(shown['data']), str(shown.get('mimeType') or 'image/png')
            images = [types.ImageContent(type='image', data=data, mime_type=kind)]
            blocks = [block.replace(data, '(the picture, attached)') for block in blocks]
            structured = {**cast(dict[str, Any], structured), 'image': {'mimeType': kind, 'attached': True}}
        return types.CallToolResult(content=[*(types.TextContent(type='text', text=block) for block in blocks), *images],
                                    structured_content=structured, is_error=error)

    async def call_tool(ctx: Any, params: Any) -> Any:
        name, arguments = params.name, dict(params.arguments or {})
        client = client_of(ctx)
        if name == views.TOOL and apps(ctx):
            return await view_call(arguments, viewer(ctx))
        if searching and name in SEARCH_FETCH:
            found = await (search(folder, str(arguments.get('query') or ''), client) if name == 'search' else
                           fetch(folder, str(arguments.get('id') or ''), client))
            return types.CallToolResult(content=[types.TextContent(type='text', text=json.dumps(found))],
                                        structured_content=found, is_error='error' in found)
        given, answered = await consented(ctx, params, name, arguments)
        if given is None:
            return answered
        approved = answered is True
        listed = (await anyio.to_thread.run_sync(listing, folder)).get(name)
        tasked_as = listed.task if listed is not None and tasked.declared(capabilities(ctx)) else False
        headers = ctx.request.headers if ctx.request is not None else None
        identity, session = gateway_identity(headers), gateway_session(headers)
        if tasked_as is True and 'group' in held:
            project = await anyio.to_thread.run_sync(tasked.owning, folder)
            if project is not None:  # a folder that is no project's keeps no task, so its call is answered as ever
                return await start_task(project, name, given, client, approved, session, identity)
        try:
            error, blocks, structured = await answer(folder, name, given, client=client, consented=approved,
                                                     session=session, identity=identity)
        finally:  # what the tool changed, fired on the event bus from a worker thread, VIEW-018; a module enabled or
            # disabled since this server started is loaded or dropped first, BASE-037
            await anyio.to_thread.run_sync(events.announce, folder, 'mcp')
        if listed is not None:  # what the list cut, before the result of its first use in the session, wrong calls too
            guide = await anyio.to_thread.run_sync(guided, listed, client, session)
            blocks = [guide, *blocks] if guide else blocks
        await announce(ctx)
        if not error:
            discussed(ctx, name, given)
        if tasked_as == 'run' and not error and isinstance((structured or {}).get('run'), str):
            seeded = await anyio.to_thread.run_sync(run_task, str(cast(dict[str, Any], structured)['run']))
            if seeded is not None:
                return seeded
        return outcome(error, blocks, structured)

    def guided(listed: Listed, client: str | None, session: str | None) -> str:
        """The guidance the call's result carries, `guidance`, in the agent session the call is made in."""
        try:
            ctx = context('mcp', folder, surface='mcp', client=client, session=session)
        except (Stop, StoreError):
            return ''
        return guidance(folder, listed, ctx)

    def run_task(run_id: str) -> dict[str, Any] | None:
        """The task a verb declared `task='run'` answers with: the workflow run it just made, by its run id."""
        found = tasked.store(folder)
        return None if found is None else tasked.seed_run(found, run_id)

    async def start_task(project: str, name: str, given: dict[str, Any], client: str | None, approved: bool,
                         session: str | None, identity: dict[str, str]) -> Any:
        """A tool call answered with a task: the task is written first, so tasks/get finds it at once, then the call
        runs in this process and the task keeps its result."""
        said = prompt_files.module('mcp', 'task_working', tool=name) or f'{name} is running.'
        made = await anyio.to_thread.run_sync(tasked.create, running, project, name, said)

        async def work() -> dict[str, Any]:
            try:
                error, blocks, structured = await answer(folder, name, given, client=client, consented=approved,
                                                         session=session, identity=identity)
            finally:  # shielded, so a cancel after the verb finished leaves its result to the task
                with anyio.CancelScope(shield=True):
                    await anyio.to_thread.run_sync(events.announce, folder, 'mcp')
            return outcome(error, blocks, structured).model_dump(by_alias=True, mode='json', exclude_none=True)
        running.scopes[made['taskId']] = anyio.CancelScope()  # made here, in the loop, so a cancel finds it at once
        held['group'].start_soon(tasked.run, running, project, made['taskId'], work)
        return made

    async def view_call(arguments: dict[str, Any], seen_by: str) -> Any:
        read = arguments.get('read')
        given: Any = arguments.get('params') or {}
        if not isinstance(read, str) or not isinstance(given, dict):
            return outcome(True, [f'Error: read is text and params an object.\nNext: {schema_step(views.TOOL)}'],
                           None)
        said = prompt_files.module('mcp', 'view_read', read=read) or f'Read {read} for the view.'
        if read == 'focus':  # the Address the agent last named, kept in this process; nothing is read for it
            return outcome(False, [said], {'address': None, 'tool': None, 'seq': 0, **focus.get(seen_by, {})})
        try:
            found = await anyio.to_thread.run_sync(view_read, folder, read, cast(dict[str, Any], given))
        except (Stop, StoreError) as stop:
            return outcome(*_error(stop, folder), None)
        data = plain(found)
        if not isinstance(data, dict):
            return outcome(False, [result_json(data)], None)
        # Under MCP Apps a result's structured content is the view's data and never the model's, so the data goes
        # once, there, and the text is one line for a host that logs the call.
        return outcome(False, [said], cast(dict[str, Any], data))

    async def list_prompts(ctx: Any, params: Any) -> Any:
        found = await anyio.to_thread.run_sync(build_prompts)
        await listed_now(ctx, 'prompts')
        return types.ListPromptsResult(prompts=found)

    async def get_prompt(ctx: Any, params: Any) -> Any:
        found = await anyio.to_thread.run_sync(slashes, folder)
        slash = found.get(params.name)
        if slash is None:
            raise MCPError(-32602, f'No slash command {params.name} on this surface.\nNext: list the prompts')
        said = await anyio.to_thread.run_sync(slash_text, folder, slash, dict(params.arguments or {}))
        await anyio.to_thread.run_sync(events.announce, folder, 'mcp')
        await announce(ctx)
        return types.GetPromptResult(description=slash.summary or None, messages=[
            types.PromptMessage(role='user', content=types.TextContent(type='text', text=said))])

    async def list_resources(ctx: Any, params: Any) -> Any:
        listed = await anyio.to_thread.run_sync(resource_list, folder)
        await listed_now(ctx, 'resources')
        found = [types.Resource(uri=one['uri'], name=one['name'], description=one['description'],
                                mime_type=one['mime_type']) for one in listed]
        if apps(ctx):  # the views, each with its _meta.ui, so a host can review what they ask before one is shown
            for uri, (name, description) in views.NAMES.items():
                view = types.Resource(uri=uri, name=name, description=description, mime_type=views.MIME)
                view.meta = views.meta(uri)
                found.append(view)
        return types.ListResourcesResult(resources=found)

    async def list_resource_templates(ctx: Any, params: Any) -> Any:
        addressed = [types.ResourceTemplate(uri_template=uri, name=name, description=description, mime_type=mime)
                     for uri, name, description, mime in ADDRESS_TEMPLATES]
        if apps(ctx):  # where a node or an item is shown: the node view, the one map_item and map_node open
            for template in addressed:
                template.meta = {'ui': {'resourceUri': views.NODE}}
        modules = [types.ResourceTemplate(uri_template=uri, name=name, description=description, mime_type=mime)
                   for uri, name, description, mime in await anyio.to_thread.run_sync(module_templates, folder)]
        return types.ListResourceTemplatesResult(resource_templates=[
            *(types.ResourceTemplate(uri_template=uri, name=name, description=description, mime_type='text/plain')
              for uri, name, description in TEMPLATES), *modules, *addressed])

    def web_address(project: str | None) -> str:
        """The web GUI's address on this machine, open at the folder's project, for a view's link to the full page;
        empty when the web module is not installed here."""
        try:
            port = settings.value('web_port', folder)
        except LookupError:
            return ''
        return f'http://127.0.0.1:{port}/' + (f'#p={project}' if project else '')

    def view_config(uri: str) -> dict[str, Any]:
        """What a view is told when it is served: its project, its tool, the line it tells the agent about a
        selection, the version it names itself with in the handshake, whether it follows the host's look (the node
        view does; the map keeps the page's own theme), and for the map view not built here, the line saying so."""
        map_built = uri == views.MAP and views.built()
        kind = uri.rsplit('/', 1)[-1]
        project = project_for(folder)
        config: dict[str, Any] = {
            'view': kind if uri != views.MAP or map_built else 'node', 'tool': views.TOOL, 'project': project,
            'version': chassis_version(), 'themed': not map_built, 'modes': views.MODES[uri],
            'selected': prompt_files.module('mcp', 'view_selected', address='{address}') or '',
            # the view's own tools, which a host that calls them lists to its agent while the view is open
            'show': prompt_files.module('mcp', 'view_show') or '',
            'state': prompt_files.module('mcp', 'view_state') or '',
            'shown': prompt_files.module('mcp', 'view_shown', address='{address}') or '',
            'absent': prompt_files.module('mcp', 'view_absent', address='{address}') or '',
            'web': web_address(project)}
        if uri == views.MAP and not map_built:
            config['notice'] = prompt_files.module('mcp', 'view_unbuilt') or ''
        return config

    async def read_resource(ctx: Any, params: Any) -> Any:
        uri = str(params.uri)
        if apps_on and uri in views.NAMES:  # a view, read by a client that renders MCP Apps
            config = await anyio.to_thread.run_sync(view_config, uri)
            text = await anyio.to_thread.run_sync(views.html, uri, config)
            page = types.TextResourceContents(uri=uri, text=text, mime_type=views.MIME)
            page.meta = views.meta(uri)
            # A view changes only with the installation and the folder's project, so a host keeps it for the list
            # hint's time, not more, so a rebuilt map view reaches the next call.
            return types.ReadResourceResult(contents=[page], ttl_ms=CACHE_TTL_MS, cache_scope='private')
        # A resource that does not exist: -32602 on the July 2026 wire, which moved it there, -32002 before it.
        missing_code = -32602 if ctx.protocol_version in MODERN_PROTOCOL_VERSIONS else -32002
        try:
            found = await read_resource_text(folder, uri, client=client_of(ctx))
        except Missing as missing:
            raise MCPError(missing_code, f'Error: {missing}\nNext: {missing.next_step}') from None
        except (Stop, StoreError) as stop:
            raise MCPError(-32603, f'Error: {stop}\nNext: {mcp_next(str(stop.next_step), folder)}') from None
        if found is None:
            raise MCPError(missing_code,
                           f'No resource {uri} on this surface.\nNext: list the resources and their templates')
        text, mime = found
        await watch.seen(uri)
        return types.ReadResourceResult(contents=[types.TextResourceContents(uri=uri, text=text, mime_type=mime)])

    async def complete(ctx: Any, params: Any) -> Any:
        ref = params.ref
        kind = 'resource' if getattr(ref, 'type', '') == 'ref/resource' else 'prompt'
        named = str(getattr(ref, 'uri', None) or getattr(ref, 'name', ''))
        known = dict(params.context.arguments or {}) if params.context is not None else {}
        found = await anyio.to_thread.run_sync(completions, folder, kind, named, params.argument.name,
                                               params.argument.value or '', known)
        return types.CompleteResult(completion=types.Completion(
            values=found[:COMPLETE_LIMIT], total=len(found), has_more=len(found) > COMPLETE_LIMIT))

    watch = Watch(folder, bus, ResourceUpdated)
    subscriptions = ListenHandler(bus)

    async def listen(ctx: Any, params: Any) -> Any:
        """A subscriptions/listen stream, MCP-004: the SDK serves it; the nodes whose briefs it names are watched for
        items added there while it is open."""
        uris = [str(uri) for uri in params.notifications.resource_subscriptions or ()]
        await watch.open(uris)
        try:
            return await subscriptions(ctx, params)
        finally:
            await watch.close(uris)

    async def subscribe(ctx: Any, params: Any) -> Any:
        await watch.open([str(params.uri)], ctx.session)
        return types.EmptyResult()

    async def unsubscribe(ctx: Any, params: Any) -> Any:
        await watch.close([str(params.uri)], ctx.session)
        return types.EmptyResult()

    @asynccontextmanager
    async def lifespan(_: Any) -> AsyncGenerator[dict[str, Any]]:
        """The task group the tasks run in, open while the server runs; a stop cancels what is still running, and
        each such task is marked failed, so none waits for ever."""
        async with anyio.create_task_group() as group:
            held['group'] = group
            group.start_soon(tasked.beat, running, folder)
            try:
                yield {}
            finally:
                held.pop('group', None)
                group.cancel_scope.cancel()
                watch.stop()

    hint = CacheHint(ttl_ms=CACHE_TTL_MS, scope='private')
    server = Server('metaform', version=chassis_version(), lifespan=lifespan, on_list_tools=list_tools,
                    on_call_tool=call_tool,
                    cache_hints={'tools/list': hint, 'prompts/list': hint, 'resources/list': hint,
                                 'resources/templates/list': hint},
                    on_list_prompts=list_prompts, on_get_prompt=get_prompt,
                    on_list_resources=list_resources, on_list_resource_templates=list_resource_templates,
                    on_read_resource=read_resource, on_subscriptions_listen=listen, on_completion=complete,
                    on_subscribe_resource=subscribe, on_unsubscribe_resource=unsubscribe)
    made_options = server.create_initialization_options

    def initialization_options(notification_options: NotificationOptions | None = None,
                               experimental_capabilities: dict[str, dict[str, Any]] | None = None,
                               extensions: dict[str, dict[str, Any]] | None = None) -> InitializationOptions:
        """What initialize declares, on every transport: the lists change and the change is announced, MCP-004. The
        Streamable HTTP session manager asks with no options, which would declare none."""
        return made_options(notification_options or NotificationOptions(
            prompts_changed=True, tools_changed=True, resources_changed=True), experimental_capabilities, extensions)
    server.create_initialization_options = initialization_options
    if apps_on:
        server.extensions[views.EXTENSION] = {}
    # Tasks for long tools are always offered: an AI tool that does not declare the extension gets the result as
    # before, so turning them off only took them from those that do. Settings cleanup 2026-10-15 removed mcp_tasks.
    server.extensions[tasked.EXTENSION] = {}
    add_tasks(server, folder, running, types, MCPError)

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
        project = cast(dict[str, Any], arguments).get('project')
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
            raise MCPError(-32603, f'Error: {error}\nNext: {mcp_next(str(error.next_step), folder)}')
        return types.CallToolResult(content=[types.TextContent(type='text', text=_error(error, folder)[1][0])],
                                    is_error=True).model_dump(by_alias=True, exclude_none=True)

    async def live(ctx: Any, call_next: Any) -> Any:
        """The instructions, composed for the folder as this request is answered, MCP-007: `initialize` for a client
        that connects with it, and `server/discover` on the 2026-07-28 wire, each time it is asked."""
        with request_scope(fresh=True):
            try:
                await anyio.to_thread.run_sync(prepare, ctx)
            except NewerStore as error:
                retry = relay.refusal(error)
                if retry.code == RETRY:
                    raise retry
                # With recovery disabled or unchanged code, the command keeps its usual behavior, including
                # commands that do not need this project's store. The preflight must not add a new gate.
            try:
                result = await call_next(ctx)
            except NewerStore as error:
                return refused(ctx, error)
            if ctx.method in ('initialize', 'server/discover') and isinstance(result, dict):
                # Over stdio the AI tool that connects is the one that started this process; over HTTP it is not.
                client = client_of(ctx)
                composed = await anyio.to_thread.run_sync(connect_instructions, folder, client,
                                                          None if http else served_session(client))
                result = {**cast(dict[str, Any], result), 'instructions': composed}
            return result
    server.middleware.append(live)
    # The state a form's answer comes back with is sealed by the SDK and bound to the call and its arguments, MRTR's
    # integrity requirement; this server's own tokens make each answer count once.
    server.middleware.append(RequestStateBoundary(RequestStateSecurity.ephemeral(ttl=consent.EXPIRES_S),
                                                  default_audience='metaform'))

    return server, relay, subscriptions


def tool_scope(folder: Path, name: str) -> str | None:
    """The scope a tool call needs, oauth.required_scope; a tool not listed is asked of as a write, or a dispatch by
    name, and search and fetch, which only read, as reads."""
    from . import oauth
    if name in SEARCH_FETCH:
        return oauth.READ
    one = listing(folder).get(name)
    return oauth.required_scope(name, one.effect if one else 'write', one.open_world if one else False)


def http_app(folder: Path, *, bind: str = '127.0.0.1', exposed: Any = None, verifier: Any = None) -> Any:
    """The Streamable HTTP app `metaform mcp serve --http` serves, and the cloud module's tunnel runs in-process: for
    a local server the SDK's Host and Origin checks for loopback; for one reached from outside (`exposed`) the bearer
    check of every request against its resource, with `verifier` (introspection at the Node's authorization server by
    default, the broker's signed assertions through the tunnel) and the scope gate before every tool call."""
    from . import oauth
    server = build(folder, http=True)[0]
    if exposed is None:
        return server.streamable_http_app(host='127.0.0.1')  # the SDK turns Host and Origin checks on for loopback
    app = server.streamable_http_app(host=bind, transport_security=oauth.transport_security(exposed),
                                     auth=oauth.auth_settings(exposed),
                                     token_verifier=verifier or oauth.Introspection(exposed, exposed.mcp))
    oauth.protect(app, exposed, functools.partial(tool_scope, folder), getattr(verifier, 'allowed', None))
    return app


def serve(folder: Path, *, http: bool = False, port: int = 0, bind: str | None = None, public_url: str | None = None,
          introspection: str | None = None) -> None:
    """Serve the folder over stdio, the host's own connection, or with `http` over Streamable HTTP on 127.0.0.1 at
    `port`, one server any number of clients connect to, MCP-002. Both run the one server `build` makes; the transport
    is the only difference. Over HTTP the SDK checks every request's Host and Origin against 127.0.0.1 and localhost,
    so a web page cannot reach the server through DNS rebinding, and there is no relay: an HTTP client reconnects."""
    if http:
        import uvicorn

        from . import oauth
        bind = bind or str(settings.value('mcp_bind', folder) or '127.0.0.1')
        # Beyond this machine only with the Node's authorization server checking every caller, oauth.py.
        exposed = oauth.exposure(
            public_url if public_url is not None else str(settings.value('mcp_public_url', folder) or ''), bind,
            introspection or oauth.DEFAULT_INTROSPECTION)
        app = http_app(folder, bind=bind, exposed=exposed)
        where = exposed.mcp if exposed is not None else f'http://127.0.0.1:{port}/mcp'
        print(f'Metaform MCP server for {folder} at {where}', file=sys.stderr, flush=True)
        if settings.value('mcp_a2a', folder):  # A2A on the same port, P004 and P005
            from .a2a import attach
            from .a2a_out import attach as follow_exchanges
            print(attach(app, folder, port, exposed), file=sys.stderr, flush=True)
            follow_exchanges(app, folder)  # what agents here sent to peers, followed to its end, MCP-043
        uvicorn.Server(uvicorn.Config(app, host=bind, port=port, log_level='warning')).run()
        return
    from mcp.server.lowlevel import NotificationOptions
    from mcp.server.stdio import stdio_server

    server, relay, subscriptions = build(folder)
    serve_session()  # one host conversation per process over stdio, so what it was told is told once, MCP-039

    async def main() -> None:
        async with stdio_server() as (read, write):
            async def run(local_read: Any, local_write: Any) -> None:
                await server.run(local_read, local_write, server.create_initialization_options(
                    NotificationOptions(prompts_changed=True, tools_changed=True, resources_changed=True)))
            try:
                await relay.run(run, read, write, subscriptions.close)
            finally:
                # The host closed its input, so the session is over: closing the output lets the stdio writer end and
                # the process exit, as MCP's stdio transport expects, instead of waiting to be killed.
                await write.aclose()
    anyio.run(main)


class Watch:
    """The nodes clients are listening on, MCP-004: each brief URI, `metaform://<address>`, named in an open
    subscriptions/listen stream or a resources/subscribe, with the last number taken at its address when it was
    watched or read. After every call this server answers, and on every `map.changed` another process of the home
    publishes, each watched node is checked; one with a higher number now is announced with
    `notifications/resources/updated` for its URI, a notice the client reads the brief again for, never the items
    themselves."""

    def __init__(self, folder: Path, bus: Any, updated: Any) -> None:
        self.folder, self.bus, self.updated = folder, bus, updated
        self.latest: dict[str, int] = {}
        self.listeners: dict[str, int] = {}  # how many open streams name each URI
        self.sessions: dict[str, list[Any]] = {}  # the 2025-handshake sessions subscribed to each URI
        self.listener: Any = None
        self.token: Any = None

    def _number(self, uri: str) -> int | None:
        found = ADDRESS.match(uri)
        if found is None or found.group('number') is not None:
            return None
        project = project_for(self.folder)
        return None if project is None else Store(project).latest_number(found.group('address'))

    async def open(self, uris: list[str], session: Any = None) -> None:
        for uri in uris:
            number = await anyio.to_thread.run_sync(self._number, uri)
            if number is None:
                continue
            self.latest.setdefault(uri, number)
            if session is None:
                self.listeners[uri] = self.listeners.get(uri, 0) + 1
            elif session not in self.sessions.setdefault(uri, []):
                self.sessions[uri].append(session)
        if self.latest and self.listener is None:
            self.token = anyio.lowlevel.current_token()
            self.listener = events.listen('mcp', self._heard)

    async def close(self, uris: list[str], session: Any = None) -> None:
        for uri in uris:
            if session is None and uri in self.listeners:
                self.listeners[uri] -= 1
                if self.listeners[uri] <= 0:
                    del self.listeners[uri]
            elif session is not None and session in self.sessions.get(uri, []):
                self.sessions[uri].remove(session)
                if not self.sessions[uri]:
                    del self.sessions[uri]
            if uri not in self.listeners and uri not in self.sessions:
                self.latest.pop(uri, None)

    async def seen(self, uri: str) -> None:
        """A brief read anew: what it showed is what the client has, so only items added after it are news."""
        if uri in self.latest:
            number = await anyio.to_thread.run_sync(self._number, uri)
            if number is not None:
                self.latest[uri] = number

    async def check(self) -> None:
        for uri, last in list(self.latest.items()):
            number = await anyio.to_thread.run_sync(self._number, uri)
            if number is None or number <= last or uri not in self.latest:
                continue
            self.latest[uri] = number
            if uri in self.listeners:
                await self.bus.publish(self.updated(uri=uri))
            for session in list(self.sessions.get(uri, ())):
                try:
                    await session.send_resource_updated(uri)
                except Exception:  # noqa: BLE001  a session gone since it subscribed hears nothing more
                    self.sessions[uri].remove(session)

    def _heard(self, payload: dict[str, Any]) -> None:
        """A `map.changed` from another process, heard on the listener's thread: the check runs in the server's loop."""
        try:
            anyio.from_thread.run(self.check, token=self.token)
        except Exception:  # noqa: BLE001, S110  a server that stopped has nothing left to tell
            pass

    def stop(self) -> None:
        if self.listener is not None:
            self.listener.close()
            self.listener = None


def add_tasks(server: Any, folder: Path, running: Any, types: Any, error_type: Any) -> None:
    """`tasks/get`, `tasks/update` and `tasks/cancel` of the tasks extension, BASE-030, on the tool calls kept as
    tasks and the workflow run records; each refused to a client that does not declare the extension, -32021, and for
    an unknown task, -32602."""
    from pydantic import Field

    from . import tasks as tasked

    class TaskParams(types.RequestParams):
        task_id: str

    class UpdateParams(TaskParams):
        input_responses: dict[str, Any] = Field(default_factory=dict[str, Any])

    def required(ctx: Any) -> tuple[str | None, Any]:
        """The project whose store keeps the tool-call tasks and the workflow runs' store, each None where there is
        none; refused to a client without the extension."""
        if not tasked.declared(ctx.session.client_capabilities):
            raise error_type(-32021, 'Missing required client capability',
                             {'requiredCapabilities': {'extensions': {tasked.EXTENSION: {}}}})
        return tasked.owning(folder), tasked.store(folder)

    def missing() -> Any:
        return error_type(-32602, 'Failed to retrieve task: Task not found')

    async def verb(module_id: str, verb_name: str, nouns: dict[str, Any]) -> Any:
        try:
            return await anyio.to_thread.run_sync(run_verb, folder, module_id, verb_name, nouns)
        finally:
            await anyio.to_thread.run_sync(events.announce, folder, 'mcp')

    async def get(ctx: Any, params: Any) -> Any:
        project, found = await anyio.to_thread.run_sync(required, ctx)
        detail = await anyio.to_thread.run_sync(tasked.detailed, project, found, params.task_id)
        if detail is None:
            raise missing()
        return {**detail, 'resultType': 'complete'}

    async def update(ctx: Any, params: Any) -> Any:
        project, found = await anyio.to_thread.run_sync(required, ctx)
        if not await tasked.update(project, found, params.task_id, dict(params.input_responses), verb):
            raise missing()
        return {'resultType': 'complete'}

    async def cancel(ctx: Any, params: Any) -> Any:
        project, found = await anyio.to_thread.run_sync(required, ctx)
        if not await tasked.cancel(running, project, found, params.task_id, verb):
            raise missing()
        return {'resultType': 'complete'}

    server.add_request_handler('tasks/get', TaskParams, get)
    server.add_request_handler('tasks/update', UpdateParams, update)
    server.add_request_handler('tasks/cancel', TaskParams, cancel)
