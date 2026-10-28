"""The MCP server, MCP-002: the official SDK's low-level Server, over stdio or Streamable HTTP.

Every command is its own tool, MCP-003 and CLI-037: each surfaced module verb is
`<module>_<verb>`, and the chassis's own commands are `metaform_<command>`, `set`,
`feedback`, `list_reports`, `read_report`, `instructions` and `register` always,
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

import base64
import dataclasses
import functools
import hashlib
import inspect
import json
import os
import re
import subprocess
import sys
import time
import traceback
import uuid
from collections import OrderedDict
from collections.abc import AsyncGenerator, Callable
from importlib import resources
from pathlib import Path
from typing import Any, Literal, cast

import anyio

from metaform import events, home, prompt_files, settings
from metaform.data import (
    BASE_VARIABLE,
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
    COMPACTED_KEY,
    Context,
    Effect,
    Module,
    Noun,
    Stop,
    Verb,
    call,
    caution_of,
    chassis_version,
    collecting_agent_context,
    command_summary,
    context,
    feedback,
    forget_shown,
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
    prepare_agent_context,
    project_for,
    provided,
    provisioning_notice,
    read_report,
    record_agent_context,
    record_shown,
    refresh_modules,
    request_scope,
    result_json,
    serve_session,
    served_session,
    setting_value,
    shown_before,
    startup_notices,
    surface,
    tool_arguments,
)
from metaform.module import (
    noted as with_notices,
)

from . import catalog, shaping, skill_extension

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
        if setting is not None:
            properties[key] = setting_schema(setting, folder)
    if verb.caution:
        properties['confirm'] = CONFIRM
    if verb.needs_project:
        properties['project'] = PROJECT
    if verb.reads_layers:
        properties.setdefault('layers', LAYERS)
    if looks_up(verb):  # how much of the result to give, said once with the first trimmed list
        for key, schema in shaping.SCHEMAS.items():
            properties.setdefault(key, schema)
    return {'type': 'object', 'properties': properties, 'required': required, 'additionalProperties': False}


def looks_up(verb: Verb) -> bool:
    """Whether a verb's tool reads records, so it takes the per-call `view`, `fields`, `must_contain` and
    `status_equals` of `shaping`: a verb that only reads, or one with an `op` whose default reads, such as map_work."""
    return verb.effect == 'read' or any(noun.name == 'op' for noun in verb.nouns)


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
    the folder's surface that serves tools here, never per-call, with its help, its JSON type, its choices and its
    value."""
    owners = {'chassis', *(module.id for module, _ in tools(folder).values())}
    listed: list[dict[str, Any]] = []
    for key, setting in settings.SCHEMA.items():
        if setting.per_call or setting.owner not in owners:
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
                                     'tool': _text('A tool, by name: its whole guide, as its first use gives it.'),
                                     'op': _text('With tool: the guide for this op of it alone.'),
                                     'project': PROJECT}}),
    'register': (('Register this folder as a Metaform project, so its map can be recorded and read. As metaform add '
                  'project does; a folder already in a project is left as it is. Returns the project and the '
                  'instructions for it now. Always available.'),
                 {'type': 'object', 'additionalProperties': False,
                  'properties': {'id': _text('The project id: lowercase letters, digits, - and _. Without it, the '
                                             "folder's name.")}}),
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
    'add_variant': (("Collect a folder, such as an agent's worktree, as a variant of an origin: the work's changes "
                     'against it. As metaform add variant does.'),
                    {'type': 'object', 'required': ['folder'], 'additionalProperties': False,
                     'properties': {
                         'folder': _text('The folder to collect, such as an agent\'s worktree.'),
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
                         'text': _text('The prompt as plain text, as the agent reads it: & and < are written as '
                                       'they are; a fill place of a prompt a module ships is written <name/>.'),
                         'format': {'type': 'string', 'enum': list(prompts.FORMATS),
                                    'description': 'The format for a new prompt; defaults to text. An existing '
                                                   'prompt keeps its format.'},
                         'parent': {'type': 'integer', 'minimum': 1,
                                    'description': 'The existing version this edit came from; without it, the '
                                                   'newest. Omit this when creating a prompt.'}}}),
    'clear_project': (("Clear the project's map, as metaform clear project does: remove its bases and reports. A "
                       'backup is made first, and metaform restore project (metaform_restore_project) brings it back; its '
                       'registration, folder, '
                       'settings, origins, variants, memories and conversations with agents stay. It runs with '
                       'confirm true; without it, it says what it would remove.'),
                      {'type': 'object', 'additionalProperties': False,
                       'properties': {'project': PROJECT, 'confirm': CONFIRM}}),
    'restore_project': (("Bring back a backup of the project's map, as metaform restore project does: the newest a "
                         'clear made, or the one named. What the project holds now is backed up first, so nothing is '
                         'lost. It runs with confirm true; without it, it says what it would bring back and replace.'),
                        {'type': 'object', 'additionalProperties': False,
                         'properties': {'project': PROJECT, 'confirm': CONFIRM,
                                        'backup': _text('The backup, by the name a clear or a restore gave it; the '
                                                        'newest a clear made when omitted.')}}),
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
    'restore_project': 'remove', 'extract': 'write'}
# The chassis's own tools that are the person's decision, run only on their answer to the form, CLI-011 and MCP-006.
# The chassis's own tools of SURFACED that act on a project's records, so they are listed once the folder has one.
ON_PROJECT = ('add_origin', 'list_origins', 'add_variant', 'list_variants', 'clear_project', 'restore_project',
              'extract')
# The chassis tools whose result is text, not data, so it has no structured form.
CHASSIS_TEXT = ('instructions', 'read_report')
JSON_TYPES: dict[str, type] = {'string': str, 'integer': int, 'boolean': bool, 'array': list, 'object': dict}


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
    step = mcp_next(str(stop.next_step), folder)
    return True, [f'Error: {stop}\nNext: {step}']


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


def run_set(folder: Path, arguments: dict[str, Any]) -> Outcome:
    """The `set` tool stores settings for the server's folder, as `metaform set` would, PROJ-005 and CLI-033.
    """
    glue = arguments.pop('glue', False)
    confirm = arguments.pop('confirm', False)
    changes: list[dict[str, Any]] = []
    notices: list[dict[str, str]] = []
    try:
        if not isinstance(glue, bool):
            raise Stop('glue is true or false.', schema_step(f'{OWN}_set'))
        if not isinstance(confirm, bool):
            raise Stop('confirm is true or false.', schema_step(f'{OWN}_set'))
        if not arguments:  # none given: the settings it takes, as the list is not in its schema
            return False, [result_json({'settings': settable(folder)})]
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


def run_chassis(folder: Path, name: str, arguments: dict[str, Any], session: str | None = None) -> Outcome:
    """The always-available chassis tools: an agent can report, read instructions and load skills on any surface."""
    notices: list[str] = []
    try:
        given = _checked(name, arguments, CHASSIS[name][1], notices)
        project = given.pop('project', None)
        if name == 'instructions' and given.get('tool'):
            return False, [tool_guide(folder, str(given['tool']), given.get('op'), session)]
        if name == 'feedback':
            text = str(given.pop('text'))
            saved = feedback(folder, text, project=project, **given)
            result = result_json(saved)
            _fault(folder, project, {'source': 'feedback', 'message': text.strip().split('\n')[0][:300],
                                     'detail': text, 'reproduce': f'Read the feedback saved as '
                                     f'{", ".join(str(one) for one in cast(list[Any], saved.get("files") or []))}, with '
                                     f'{OWN}_read_report.', 'work_id': os.environ.get('METAFORM_WORK')})
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
        else:
            result = read_report(folder, given['name'], project=project)
    except Stop as stop:
        return _error(stop, folder)
    return False, (['\n'.join(notices)] if notices else []) + [result]


CODE_LOADED = time.time()  # when this server's code was loaded: each fault it raises says so, `loaded`, for autoticket


def _fault(folder: Path, project: Any, payload: dict[str, Any]) -> list[str] | None:
    """Publish `fault.raised`, for autoticket to file as a ticket to fix: a module's verb that failed, or feedback;
    `work_id` names the ticket of the agent whose call it was. Returns the tickets it was filed or counted on, empty
    while it waits to be filed, or None when no subscriber took it: no project, or autoticket off."""
    try:
        source = context('mcp', folder, project=str(project) if project else None, surface='mcp')
        if source.project is None:
            return None
        payload = {**payload, 'loaded': CODE_LOADED}
        taken = [cast(dict[str, Any], one['result']) for one in events.publish('fault.raised', payload, source)
                 if one.get('status') == 'completed' and isinstance(one.get('result'), dict)
                 and cast(dict[str, Any], one['result']).get('taken')]
    except Exception as error:  # noqa: BLE001  the caller's answer stands whether or not the fault is filed
        sys.stderr.write(f'The fault could not be published: {error}\n')
        return None
    return [str(ticket) for result in taken for ticket in cast(list[Any], result.get('tickets') or [])] \
        if taken else None


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


# Metaform's own budget for the connect message, MCP-029: Claude Code keeps 4,096 characters of a server's
# instructions since v2.1.296 (2,048 before), and Metaform keeps to half that, since every agent reads all of it.
HOST_KEEPS = 2048


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


def connect_instructions(folder: Path) -> str:
    """The connect message, MCP-007 and MCP-029, for every agent and on every wire: `opening`, the directive line and
    the links to the instruction blocks that apply to the agent this server serves, now. Each block is a resource read
    whole, so the message stays far within what any host keeps and no block is cut."""
    return opening(served_agent(folder))


def task_text(folder: Path, client: str | None = None, session: str | None = None, keyed: bool = True) -> str:
    """The task block, metaform://task/<name>: what the session is for, then the catalog's line, the compaction or
    handle line this connection needs, the project's name to the person's own session and the folder's notices. It is
    linked to the person's own session, `connect_use`, and to the intake task, `task_intake`; every other task's text
    is its first turn, so no block repeats it, `task_link`."""
    own = not catalog.dispatched()
    project = project_for(folder)
    lines: list[str] = []
    if said := prompt_files.module('mcp', 'connect_use' if own else f'task_{catalog.task()}'):
        lines.append(said)
    if said := prompt_files.module('mcp', 'connect_catalog'):
        lines.append(said)
    if not keyed:
        said = prompt_files.module('mcp', 'connect_unkeyed', handle=HANDLE)
    elif session is None or session.startswith('process:'):  # no runner hears this session's compaction
        said = prompt_files.module('mcp', 'connect_compaction')
    else:
        said = ''
    if said:
        lines.append(said)
    if own and project is not None and (said := prompt_files.module('mcp', 'connect_here', project=project)):
        lines.append(said)
    first_run = first_run_text(folder) if own else None
    lines += [one for one in startup_notices(folder, project) if one != first_run]
    return '\n\n'.join(lines)


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


def run_history(folder: Path, name: str, arguments: dict[str, Any]) -> Outcome:
    """The history, prompt and clear commands as tools, on the surface while the chassis is, PROJ-024, STORE-044,
    PROJ-025 and MCP-004."""
    notices: list[str] = []
    confirmed = arguments.pop('confirm', False) is True
    try:
        error, blocks = _history(folder, name, _checked(name, arguments, SURFACED[name][1], notices), confirmed)
    except (Stop, StoreError) as stop:
        return _error(stop, folder)
    return error, (['\n'.join(notices)] if notices else []) + blocks


def _history(folder: Path, name: str, given: dict[str, Any], confirmed: bool = False) -> Outcome:
    """The history, prompt and clear tools once their arguments are read; `confirmed`, the call's confirm=true, which
    a restore or a clear asks for with its caution."""
    if name == 'prompts':
        return False, [result_json(list(prompts.prompts()))]
    if name == 'prompt':
        found = prompts.prompt_version(given['name'], given.get('number'))
        # as the person and the agent read and edit it: the characters sent, fill places written <name />
        return False, [result_json(dataclasses.replace(found, text=prompt_files.readable(found)))]
    if name == 'save_prompt':
        try:  # the one gate every surface saves through: plain text in, sent as written
            saved, said = prompt_files.save_edit(str(given['name']), str(given['text']),
                                                 format=str(given.get('format', 'text')), parent=given.get('parent'))
        except ValueError as error:
            raise Stop(f'{error}.', f"metaform prompt {given['name']}") from None
        return False, [result_json(with_notices(saved, [(str(given["name"]), one) for one in said]))]
    if name == 'restore_project':
        project = project_for(folder, given.pop('project', None)) or _no_project()
        backup = cast(str | None, given.get('backup'))
        if not confirmed:
            raise Stop(home.restore_caution(project, backup), f'If you are sure: call {OWN}_{name} with confirm true')
        restored = home.restore_project(project, backup)
        return False, [result_json({'project': project, 'said': restored.said, 'backup': restored.backup.name,
                                    'held_before': restored.held_before, 'back': restored.back,
                                    **({'stopped': list(restored.stopped)} if restored.stopped else {})})]
    if name == 'clear_project':
        project = project_for(folder, given.pop('project', None)) or _no_project()
        again = f'ask the person to clear {project} again'
        if not confirmed:
            raise Stop(home.to_clear(project).caution, f'If you are sure: call {OWN}_{name} with confirm true')
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
             lines: list[str], client: str | None = None,
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
    nouns, switches, notices = tool_arguments(module.id, verb, arguments, ignore=PER_CALL, folder=folder)
    if layers is not None:
        switches['layers'] = [str(item) for item in cast(list[Any], layers)]
    made = context(module.id, folder, project=project, nouns=nouns, switches=switches, sink=lines.append,
                   surface='mcp', client=client, session=session, identity=identity)
    if verb.caution and not confirmed:
        raise Stop(caution_of(verb, made), f'If you are sure: call {name} with confirm true')
    lines.extend(f'Notice: {key}: {message}' for key, message in notices)
    return made


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
    # Long calls run here; assigned agent sessions keep their own task records.
    task: bool | Literal['session'] = False
    # what comes with its first use in a session, MCP-039: what the list cut; given the call's op, that op's part alone
    guide: Callable[[str | None], str] = lambda op: ''
    module: str = 'metaform'  # the module that serves it, whose rules come with the first use of any of its tools
    verb: Verb | None = None  # the module verb it runs, None for the chassis's own tools

    def annotations(self) -> dict[str, bool]:
        """The four hints, each set from the declared effect. None is left out, since an absent hint falls back on
        the protocol's defaults, which take a tool to be a destructive write that reaches the open world. A tool that
        is the person's decision, such as one that switches the map every agent sees, is destructive too."""
        return {'read_only_hint': self.effect == 'read', 'destructive_hint': self.effect == 'remove',
                'idempotent_hint': self.effect == 'read', 'open_world_hint': self.open_world}


SENTENCE = re.compile(r'(?<=\.)\s')  # where a description's first sentence ends


def glossary(folder: Path) -> str:
    """metaform://metaform: the system glossary, the mcp module's glossary prompt exactly as written and nothing more,
    how to operate in Metaform; the same for every folder, and for a project named metaform too. The tools and the
    modules are discovered at metaform://modules, with commands at metaform://<module>/tools. The
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
    """One tool's line in its module's tools resource: the head of its description's first sentence, what it does, before the
    details a colon or semicolon opens, with the command it matches left out; the details come with the tool."""
    first = SENTENCE.split(description.split(' Caution:')[0], maxsplit=1)[0]
    head = CLAUSE.split(AS_DOES.sub('', first), maxsplit=1)[0].strip().rstrip('.')
    while len(head) > LINE and ', ' in head:  # a long head keeps its leading phrases, each whole
        shorter = head.rsplit(', ', 1)[0]
        if len(shorter) < LINE_LEAST:  # cut no further than still says what the tool does
            break
        head = shorter
    return head


def module_descriptions(folder: Path) -> dict[str, str]:
    """Active modules publish their own capability description, including modules with no MCP verbs."""
    return {'metaform': prompt_files.module('mcp', 'chassis_description') or '',
            **{module.id: module.summary for module in surface(folder)}}


def modules_text(folder: Path) -> str:
    """A directory of capabilities and their tool resources, without command names or schemas."""
    head = prompt_files.module('mcp', 'module_index') or ''
    return '\n'.join([head, *(f'- {name}: {purpose} — metaform://{name}/tools'
                             for name, purpose in sorted(module_descriptions(folder).items()))])


def module_tools_text(folder: Path, module: str) -> str:
    """Only one module's commands, generated from that module's current declarations."""
    descriptions = module_descriptions(folder)
    if module not in descriptions:
        raise Missing(f'No active module {module}.', 'read metaform://modules')
    available = given_tools(folder)
    names = catalog.grouped(available, tools(folder)).get(module, [])
    lines = [f'{module}: {descriptions[module]}',
             prompt_files.module('mcp', 'module_tools', module=module) or '',
             *(catalog_line(available[name]) for name in names)]
    return '\n'.join(line for line in lines if line)


def listing(folder: Path, client: str | None = None) -> dict[str, Listed]:
    """Every tool the server lists, by name in order, CLI-037 and MCP-003: each surfaced module verb as
    `<module>_<verb>`, described by its summary and its caution, and the chassis's own commands as
    `metaform_<command>`, the history, prompt and clear commands only while the chassis is on the folder's surface,
    MCP-004. Each command is described once, here, with its arguments' schema built from its declaration, so an agent
    plans a call from the list alone and the list is the same on every connection to the folder. Until the folder has a project, only
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
                             module.id, verb)
    own: dict[str, tuple[str, Callable[[], dict[str, Any]]]] = {
        'set': (('Save settings for this folder, each given as name=value. Called with none, it lists the settings '
                 'an agent may change, each with its help, choices and current value.'),
                functools.partial(set_schema, folder)),
        **{name: (said, _fixed(schema)) for name, (said, schema) in CHASSIS.items()
           if name != 'register' or not registered}}  # registering is listed until it is taken
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


OP_SCOPE = re.compile(r'^(?P<head>[^:.]{1,40}):\s')  # an argument's help that opens with the ops it is for


def ops_of(verb: Verb) -> tuple[str, ...]:
    """The ops a verb's `op` noun takes, from its schema's enum; none for a verb without one."""
    noun = next((one for one in verb.nouns if one.name == 'op'), None)
    schema: dict[str, Any] = dict(noun.schema or {}) if noun is not None else {}
    return tuple(str(one) for one in cast(list[Any], schema.get('enum') or ()))


def for_op(help: str, op: str | None, ops: tuple[str, ...]) -> bool:
    """Whether an argument's help is for `op`: help that opens with the ops it is for, `take and plan: ...`, names it;
    help that opens with no op is for every op, and with `op` None only such help is."""
    found = OP_SCOPE.match(help)
    named: set[str] = set(re.findall(r'[a-z-]+', found.group('head'))) & set(ops) if found else set()
    return not named or op in named


def verb_guide(verb: Verb, more: str, build: Callable[[], dict[str, Any]], folder: Path,
               op: str | None = None) -> str:
    """What a module verb's tool gives with its first use, MCP-039: the rest of its description, each argument whose
    help the list cut with its whole help, the verb's details and its examples, each a call; all from its declaration.
    For a verb with an `op`, only the part for the call's op, its default the first when none is given: the arguments
    whose help is for it, by the ops it opens with, and the examples that call it, so a worker taking a ticket is not
    handed how to distribute glyphs. A record read by id with no op, `read`, is given the id's help alone, since the
    agent has only to read. The verb's details, which say what its records are, come with the first op that writes
    one, never with a read or a list; its `person_details` with them only to an agent that acts for the person,
    catalog.for_person, since they are said to the person. A line given once is not given again, `Given`."""
    ops = ops_of(verb)
    said = _arguments_said(build())
    if ops and op == 'read':
        return '\n'.join(line for line in said if line.startswith('id: '))
    examples = [(command, said) for command, said in verb.examples]
    told = ' '.join(part for part in (verb.details, verb.person_details) if part) if catalog.for_person() else \
        verb.details
    details = mcp_next(told, folder)
    if ops and (op is None or op == ops[0]):  # the verb's details come with its first op that writes
        details = ''
    if ops:
        chosen = op if op in ops else ops[0] if op is None else None
        said = [line for line in said if line.startswith('op: ') or for_op(line.split(': ', 1)[-1], chosen, ops)]
        examples = [(command, text) for command, text in examples
                    if ((chosen is not None and f'op={chosen}' in command)
                        or (chosen in (None, ops[0]) and 'op=' not in command))]
    shown = [f'{mcp_next(command, folder)}: {text}' for command, text in examples]
    parts = [more, '\n'.join(said), details, '\n'.join(shown)]
    return '\n\n'.join(part.strip() for part in parts if part.strip())


def own_guide(more: str, build: Callable[[], dict[str, Any]], folder: Path, op: str | None = None) -> str:
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


def guidance(folder: Path, listed: Listed, ctx: Context, op: str | None = None) -> str:
    """Return provisioning and compaction notices alongside the result.

    Usage instructions and module rules are delivered before execution through
    the MCP-044 prerequisite. These notices retain their existing timing.
    """
    parts: list[str] = []
    session = ctx.session if served_session() is not None else None
    if session is not None and not catalog.dispatched() and (notice := provisioning(session)) is not None:
        parts.append(notice)  # the person's AI tool's setup: never a dispatched agent's business
        TOLD.add(session)
    if ctx.session is None:  # nothing records what this connection was given, so no guide is repeated on every call
        unkeyed = prompt_files.module('mcp', 'guide_unkeyed', tool=listed.name) if listed.guide(op) else None
        return '\n\n'.join([*parts, *([unkeyed] if unkeyed else [])])
    pending = shown_before(ctx.session, COMPACTED_KEY)
    if isinstance(pending, str) and pending:  # the runner's line, given once, by whichever comes first
        parts.insert(0, pending)
        record_shown(ctx.session, COMPACTED_KEY, '')
    return '\n\n'.join(parts)


class Given:
    """The guide lines a session was given, by digest, so a line given with one tool is not given again with another,
    as the memory tools' shared argument help was, MCP-039: read once, kept once, for one guidance."""
    KEY = 'guide:lines'

    def __init__(self, session: str | None) -> None:
        self.session = session
        self.held: set[str] = set(cast(list[str], shown_before(session, self.KEY) or []))
        self.before = len(self.held)

    def new(self, lines: list[str]) -> list[str]:
        """The lines not given yet, blank lines kept between them, each recorded as given."""
        found: list[str] = []
        for line in lines:
            if not line.strip():
                if found and found[-1]:
                    found.append('')
                continue
            digest = _digest(line)
            if digest in self.held:
                continue
            self.held.add(digest)
            found.append(line)
        return found if any(found) else []

    def keep(self) -> None:
        if len(self.held) != self.before:
            record_shown(self.session, self.KEY, sorted(self.held))


GUIDE_URI = re.compile(r'^metaform://tools/(?P<tool>[\w-]+)/instructions(?:/(?P<op>[\w-]+))?'
                       r'(?:\?session_handle=(?P<handle>[0-9a-f]{12}))?$')
GUIDE_EXEMPT = {'metaform_instructions', catalog.CATALOG}


def usage_pointer(listed: Listed) -> str:
    if listed.name in GUIDE_EXEMPT:
        return ''
    scopes = ops_of(listed.verb) if listed.verb else ()
    if prompt_files.module_rules(listed.module) or listed.guide(None) or any(listed.guide(op) for op in scopes):
        return f' Before use, read {instruction_uri(listed.name)}.'
    return ''


def usage_description(listed: Listed) -> str:
    return listed.description + usage_pointer(listed)


def instruction_uri(name: str, op: str | None = None, handle: str | None = None) -> str:
    return f'metaform://tools/{name}/instructions' + (f'/{op}' if op else '') + (
        f'?{HANDLE}={handle}' if handle else '')


def instruction_op(listed: Listed, arguments: dict[str, Any]) -> str | None:
    op = arguments.get('op')
    if isinstance(op, str):
        return op
    if listed.verb is not None and (ops := ops_of(listed.verb)):
        return 'read' if 'id' in arguments else ops[0]
    return None


def usage_components(folder: Path, listed: Listed, op: str | None, session: str | None) -> list[dict[str, Any]]:
    """Exact tool-owned usage, independently of who is allowed to execute the operation."""
    if listed.name in GUIDE_EXEMPT:
        return []
    result: list[dict[str, Any]] = []
    rules = prompt_files.module_rules(listed.module)
    if rules:
        text = '\n'.join(f'{said} Why: {why}' for said, why in rules)
        version = 'module-rules:' + hashlib.sha256(text.encode()).hexdigest()
        one = prompt_files.component(f'mcp:module_usage:{listed.module}', text, version_id=version)
        one['source'] = {'kind': 'module_rules', 'name': prompt_files.address(listed.module, 'rules')}
        result.append(one)
    body = listed.guide(op).strip()
    if body:
        heading = prompt_files.resolve('prompt.mcp:tool_guide', tool=listed.name)
        text = str(heading['text']) + '\n' + body
        version = 'tool-guide:' + hashlib.sha256(text.encode()).hexdigest()
        one = prompt_files.component(f'mcp:tool_usage:{listed.name}:{op or "default"}', text, version_id=version)
        one['source'] = {'kind': 'tool_declaration', 'tool': listed.name, 'op': op,
                         'heading': heading}
        result.append(one)
    ctx = context('mcp', folder, surface='mcp', session=session)
    for _, provider in provided(folder, 'agent.tool.instructions'):
        result.extend(provider(ctx, listed.name, op))
    if result:
        schema = json.dumps({'inputSchema': listed.schema()}, ensure_ascii=False, separators=(',', ':'),
                            sort_keys=True)
        version = 'tool-schema:' + hashlib.sha256(schema.encode()).hexdigest()
        one = prompt_files.component(f'mcp:tool_schema:{listed.name}', schema, version_id=version)
        one['source'] = {'kind': 'tool_schema', 'tool': listed.name}
        result.append(one)
    return result


def prepare_usage(folder: Path, session: str | None, components: list[dict[str, Any]]) -> dict[str, Any]:
    # Before registration there is no project ledger. Keep exact session-scoped fingerprints in the existing
    # home receipt store, whose compaction path already drops non-catalog entries, rather than a process unlock.
    if project_for(folder) is not None and provided(folder, 'agent.context'):
        return prepare_agent_context(folder, session, components)
    due = [{**one, 'usage_home_receipt': True} for one in components if session is None or
           shown_before(session, f'usage:0:{one["name"]}') != one['rendered_fingerprint']]
    return {'epoch': 0, 'components': due, 'text': '\n\n'.join(str(one['text']) for one in due)}


def instruction_required(folder: Path, name: str, arguments: dict[str, Any], session: str | None) -> dict[str, Any] | None:
    listed = listing(folder).get(name)
    if listed is None or name in GUIDE_EXEMPT:
        return None  # unknown tools retain their ordinary error, and discovery never requires itself
    op = instruction_op(listed, arguments)
    components = usage_components(folder, listed, op, session)
    if not components:
        return None
    prepared = prepare_usage(folder, session, components)
    if not prepared['components']:
        return None
    handle = (uuid.uuid4().hex[:12] if session is None or session.startswith('process:') else
              session.removeprefix('handle:') if session.startswith('handle:') else None)
    uri = instruction_uri(name, op, handle)
    read_arguments: dict[str, Any] = {'tool': name}
    if op is not None:
        read_arguments['op'] = op
    if handle:
        read_arguments[HANDLE] = handle
    return {'error': 'instructions_required', 'executed': False, 'tool': name, 'op': op,
            'read': uri, 'read_tool': {'tool': 'metaform_instructions', 'arguments': read_arguments},
            **({HANDLE: handle} if handle else {}),
            'instructions': [{'name': one['name'], 'fingerprint': one['rendered_fingerprint'],
                              'version': one.get('actual_version_id'),
                              **({'read': one['read']} if one.get('read') else {})}
                             for one in prepared['components']],
            'next': 'Read the instruction URI, then repeat the operation' +
                    (f' with {HANDLE}={handle}.' if handle else '.')}


def tool_guide(folder: Path, name: str, op: str | None, session: str | None) -> str:
    """Explicit usage retrieval, shared by its resource URI and metaform_instructions alias."""
    listed = listing(folder).get(name)
    if listed is None:
        raise Stop(f'No tool {name} on this surface.', f'call {catalog.CATALOG} with search')
    handle = uuid.uuid4().hex[:12] if session is None else None
    session = f'handle:{handle}' if handle else session
    scopes: tuple[str | None, ...] = (op,)
    if op is None and listed.verb is not None and (ops := ops_of(listed.verb)):
        scopes = (*ops, 'read')
    components: list[dict[str, Any]] = []
    for scope in scopes:
        components.extend(usage_components(folder, listed, scope, session))
    unique = {str(one['name']): one for one in components}
    prepared = prepare_usage(folder, session, list(unique.values()))
    due = cast(list[dict[str, Any]], prepared['components'])
    if components and not due:
        return prompt_files.module('mcp', 'already_read', uri=instruction_uri(name, op),
                                   again='use the current context') or ''
    ctx = context('mcp', folder, surface='mcp', session=session)
    ctx.queue_context(due, int(prepared['epoch']))
    schema = json.dumps({'inputSchema': listed.schema()}, ensure_ascii=False, separators=(',', ':'))
    prefix = [f'{HANDLE}: {handle}\nUse this handle on subsequent tool calls.'] if handle else []
    return '\n\n'.join([*prefix, *(str(one['text']) for one in due), *([] if components else [schema])])


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]


def catalog_schema(folder: Path, unkeyed: bool = False) -> dict[str, Any]:
    """metaform_catalog's input schema: the module to open, the words to search, the tool
    to run with its arguments, and the flag that says the agent's context was compacted. `unkeyed`: for a listing that
    names no session, whose module's help says what opening it does there."""
    def said(name: str) -> str:
        return prompt_files.module('mcp', name) or ''
    opening = said('catalog_module')
    return {'type': 'object', 'additionalProperties': False, 'properties': {
        'module': {'type': 'string', 'description': opening},
        'search': {'type': 'string', 'description': said('catalog_search')},
        'tool': {'type': 'string', 'description': said('catalog_run')},
        'arguments': {'type': 'object', 'description': said('catalog_arguments')},
        'compacted': {'type': 'boolean', 'description': said('catalog_compacted')}}}


def openable(folder: Path) -> tuple[str, ...]:
    """Module ids available on this surface, without a separate registry of modules."""
    return tuple(sorted(module_descriptions(folder)))


def given_tools(folder: Path) -> dict[str, Listed]:
    """Every tool on the folder's enabled module surface, in listing order, MCP-003."""
    return listing(folder)


def action_bindings(ctx: Context, capabilities: dict[str, Any] | None = None) -> dict[str, Any]:
    """Bindings generated from implemented, surfaced tool declarations and the caller's actual adapter evidence, with
    the name of the task the calling agent runs, None for a session no task names."""
    active = listing(ctx.folder, ctx.client)
    return {'task': catalog.task(), 'adapter': dict(capabilities or {}),
            'tools': {name: {'description': usage_description(one), 'arguments': one.schema(),
                             'effect': one.effect}
                      for name, one in active.items()}}


def open_module(folder: Path, session: str | None) -> str | None:
    """The module a session has open: the one it opened last; None for none."""
    held = shown_before(session, catalog.OPEN_KEY)
    chosen = held if isinstance(held, str) else None
    return chosen if chosen in openable(folder) else None


# A session handle, MCP-039: what a call on the July 2026 wire over HTTP, which has no session header, names its
# session by, given by metaform_catalog and passed back as this argument, or in the request's _meta under HANDLE_META by
# a client that can; the session is then `handle:<it>`.
HANDLE = 'session_handle'
HANDLE_META = 'io.metaform/session'
HANDLED = re.compile(r'[0-9a-f]{12}')  # a handle as metaform_catalog makes it; anything else names no session
# The keys of a session's record of how its AI tool lists: the module opened whose listing the AI tool has not asked
# for yet, and that it asked for one after a change was announced, so it re-lists and needs no tool lines. Both start
# with catalog:, so a compaction keeps them, shown.KEPT_THROUGH_COMPACTION.
PENDING_KEY = 'catalog:pending'
RELISTS_KEY = 'catalog:relists'
PURPOSES_KEY = 'announce:purposes'


def listed_names(folder: Path, session: str | None) -> tuple[str, ...]:
    """Only discovery at startup; after selecting a module, only that module's tools.

    Stateless clients invoke the catalog directly. They never receive the entire tool inventory.
    """
    if session is None:
        return (catalog.CATALOG,)
    opened = open_module(folder, session)
    if opened is None:
        return (catalog.CATALOG,)
    groups = catalog.grouped(given_tools(folder), tools(folder))
    return (catalog.CATALOG, *groups.get(opened, []))


def relisted(session: str | None, opened: str | None) -> None:
    """A session's AI tool asked for the tools with `opened` open: when that is the module opened last and not yet
    listed, the AI tool re-lists on a change, so the next module it opens is answered in one line."""
    if session is not None and opened is not None and shown_before(session, PENDING_KEY) == opened:
        record_shown(session, PENDING_KEY, '')
        record_shown(session, RELISTS_KEY, True)


def run_catalog(folder: Path, given: dict[str, Any], session: str | None, follows: bool = True) -> Outcome:
    """Discover modules, select one, search its declared capabilities, or report compaction."""
    if given.get('compacted') is True:
        return False, [compaction_state(folder, session, follows)]
    module, search = given.get('module'), given.get('search')
    if module is not None and module not in openable(folder):
        raise Stop(f'No active module {module}.', 'read metaform://modules')
    if module is not None and not search:
        text = module_tools_text(folder, str(module))
        if follows:
            record_shown(session, catalog.OPEN_KEY, module)
            record_shown(session, PENDING_KEY, module)
        return False, [discovery_delivery(folder, session, f'metaform://{module}/tools', text)]
    if isinstance(search, str) and search.strip():
        available = {name: one for name, one in given_tools(folder).items()
                     if module is None or one.module == module}
        homes = {name: one.module for name, one in available.items()}
        found = catalog.ranked(search, {name: one.description for name, one in available.items()}, homes,
                               module_descriptions(folder))[:8]
        if not found:
            return False, [prompt_files.module('mcp', 'catalog_none') or 'No tool fits.']
        return False, ['\n'.join(f'{catalog_line(available[name])} [metaform://{homes[name]}/tools]'
                                 for name in found)]
    return False, [discovery_delivery(folder, session, MODULES_URI, modules_text(folder))]


def discovery_delivery(folder: Path, session: str | None, uri: str, text: str) -> str:
    """Resources and catalog calls share content receipts; opening a retained module still changes selection."""
    one = prompt_files.component('mcp:discovery_' + uri.removeprefix('metaform://').replace('/', '_'), text)
    prepared = prepare_agent_context(folder, session, [one])
    due = cast(list[dict[str, Any]], prepared['components'])
    if not due:
        return prompt_files.module('mcp', 'already_read', uri=uri, again='use the current context') or ''
    record_agent_context(folder, session, due, epoch=int(prepared['epoch']), channel='mcp_discovery')
    return str(prepared['text'])


def catalog_line(one: Listed) -> str:
    """One tool as the catalog says it: its name, the arguments it takes but the per-call ones, and what it does."""
    schema = one.schema()
    properties = {key: value for key, value in cast(dict[str, Any], schema.get('properties') or {}).items()
                  if key not in (*shaping.ARGUMENTS, *PER_CALL) or (one.verb is not None and key in
                                                                    {noun.name for noun in one.verb.nouns})}
    said = short_line(one.description) + usage_pointer(one)
    return f'{one.name}({catalog.signature({**schema, "properties": properties})}): {said}'


def compaction_state(folder: Path, session: str | None, follows: bool = True) -> str:
    """What a session is told once its agent's context was compacted: first the directive and the links to its
    instruction blocks, `opening`, since compaction removed what it read; then that the record
    of what it was given is forgotten, so each piece comes again at its next use, and, when its listing follows it, the
    module it has open, which its AI tool still lists."""
    gone = forget_shown(session)
    try:  # CTX-045's topic, as the runner publishes it on ACP's signal, for a module that keeps more per session
        context('mcp', folder, surface='mcp', session=session).publish(
            'session.compacted', {'session': session, 'forgotten': gone, 'by': 'agent'})
    except (Stop, StoreError):
        pass
    opened = open_module(folder, session) if follows else None
    held = prompt_files.module('mcp', 'compaction_open', module=opened) if opened else ''
    said = prompt_files.module('mcp', 'compaction_state', n=str(gone), open=f' {held}' if held else '') or ''
    return '\n\n'.join(part for part in (opening(served_agent(folder)), said) if part)


async def run_tool(folder: Path, name: str, arguments: dict[str, Any], *, client: str | None = None,
                   session: str | None = None, instruction_read: bool = False) -> Outcome:
    """A call to one listed tool by its name: whether it failed, and its text blocks."""
    error, blocks, _ = await answer(folder, name, arguments, client=client, session=session,
                                    instruction_read=instruction_read)
    return error, blocks


def _contains_delivery(value: Any, wanted: Any) -> bool:
    if value == wanted:
        return True
    if isinstance(value, dict):
        return any(_contains_delivery(one, wanted) for one in cast(dict[str, Any], value).values())
    if isinstance(value, list):
        return any(_contains_delivery(one, wanted) for one in cast(list[Any], value))
    return isinstance(value, str) and isinstance(wanted, str) and bool(wanted) and wanted in value


def _commit_response(receipts: list[dict[str, Any]], blocks: list[str], data: Any, channel: str) -> None:
    """A complete body survived rendering and shaping; acknowledge its captured revision, never a fresh read."""
    candidates = [data, *blocks]
    for block in blocks:
        try:
            candidates.append(json.loads(block))
        except ValueError:
            pass
    for receipt in receipts:
        one = cast(dict[str, Any], receipt['component'])
        wanted = one.get('delivered_value', one.get('text'))
        if wanted is None or not any(_contains_delivery(value, wanted) for value in candidates):
            continue
        record_agent_context(receipt['folder'], receipt['session'], [one], project=receipt['project'],
                             epoch=int(receipt['epoch']), channel=channel)
        fallback = not (receipt['project'] and provided(receipt['folder'], 'agent.context'))
        if (one.get('usage_home_receipt') or fallback) and receipt['session'] is not None:
            record_shown(receipt['session'], f'usage:{receipt["epoch"]}:{one["name"]}',
                         one['rendered_fingerprint'])


async def answer(folder: Path, name: str, arguments: dict[str, Any], *, client: str | None = None,
                 session: str | None = None,
                 identity: dict[str, str] | None = None,
                 shape: shaping.Shape | None = None, instruction_read: bool = False
                 ) -> tuple[bool, list[str], dict[str, Any] | None]:
    with collecting_agent_context(session) as receipts:
        outcome = await _answer(folder, name, arguments, client=client, session=session,
                                identity=identity, shape=shape, instruction_read=instruction_read)
    if not outcome[0] and receipts:
        await anyio.to_thread.run_sync(_commit_response, receipts, outcome[1], outcome[2], 'mcp_tool')
    return outcome


async def _answer(folder: Path, name: str, arguments: dict[str, Any], *, client: str | None = None,
                 session: str | None = None,
                 identity: dict[str, str] | None = None,
                 shape: shaping.Shape | None = None, instruction_read: bool = False
                 ) -> tuple[bool, list[str], dict[str, Any] | None]:
    """A call to one listed tool, as `run_tool`, with the result's structured form when it is an object, BASE-036:
    the same data as the text block holding it, for a host that reads tool output as data.
    `shape`: an agent's call over the protocol, whose module tool's result is given as it asks, `shaping.shaped`;
    without it, as the result is, for what reads it as data, a resource or search."""
    if not instruction_read:
        try:
            required = await anyio.to_thread.run_sync(instruction_required, folder, name, arguments, session)
        except Stop as stop:
            error, blocks = _error(stop, folder)
            return error, blocks, None
        if required is not None:
            return True, [result_json(required)], required
    own = name[len(OWN) + 1:] if name.startswith(OWN + '_') else ''
    if own == 'set':
        error, blocks = await anyio.to_thread.run_sync(run_set, folder, dict(arguments))
        return error, blocks, _structured(error, blocks)
    if own in CHASSIS:
        error, blocks = await anyio.to_thread.run_sync(run_chassis, folder, own, dict(arguments), session)
        return error, blocks, None if own in CHASSIS_TEXT else _structured(error, blocks)
    if own in SURFACED and await anyio.to_thread.run_sync(on_surface, 'chassis', folder):
        error, blocks = await anyio.to_thread.run_sync(run_history, folder, own, dict(arguments))
        return error, blocks, _structured(error, blocks)
    known = await anyio.to_thread.run_sync(tools, folder)
    if name not in known:
        return True, [f'Error: No tool {name} on this surface.\nNext: list the tools'], None
    module, verb = known[name]
    lines: list[str] = []
    try:
        ctx = await anyio.to_thread.run_sync(_prepare, folder, module, verb, name, dict(arguments), lines, client,
                                             session, identity)
        if inspect.iscoroutinefunction(verb.run):
            result = await verb.run(ctx)
        else:
            result = await _threaded(verb.run, ctx)
    except Stop as stop:
        error, blocks = _error(stop, folder)
        return error, blocks, None
    except Exception as error:  # noqa: BLE001  any failure of a module's verb goes back to the host, MCP-006
        payload = {'source': 'mcp', 'message': f'{type(error).__name__}: {error}', 'detail': traceback.format_exc(),
                   'reproduce': f'call {name} with {json.dumps(arguments, default=str)[:1000]}',
                   'work_id': os.environ.get('METAFORM_WORK')}
        filed = await anyio.to_thread.run_sync(_fault, folder, arguments.get('project'), payload)
        if filed is None:
            step = f'call {OWN}_feedback and say what you called'
        else:  # the fault carries the message, the traceback and the call, so feedback on it would file it again
            step = (f'this failure is {"filed for a fix as ticket " + ", ".join(filed) if filed else "recorded for a fix"}'
                    f'; call {OWN}_feedback only for what this error does not say')
        return True, [f'Error: {type(error).__name__}: {error}\nNext: {step}'], None
    if catalog.task() == 'user_agent':  # the person's own agent, the one that follows the active map, `map_moved`
        moved: str | None = None
        with anyio.CancelScope(shield=True):  # its verb's effect landed: a cancel now never loses the result
            moved = await anyio.to_thread.run_sync(map_moved, ctx.project)
        if moved:
            lines.append(f'Notice: map: {moved}')
    if lines and isinstance(result, str):  # one block, so no host's way of joining blocks runs the lines into the text
        return False, ['\n'.join(lines) + '\n' + result], None
    blocks = ['\n'.join(lines)] if lines else []
    if shape is not None and result is not None and not isinstance(result, str):
        more = prompt_files.module('mcp', 'list_cut') or '<n/> more.'
        try:
            text, data = shaping.shaped(result, shape, more, record=looks_up(verb))
        except shaping.Unheld as wrong:  # an answer of none would be read as true
            return True, [*blocks, f'Error: {wrong}\nNext: call {name} without it, or with view=full'], None
        return False, [*blocks, text], data
    if result is not None:
        blocks.append(result if isinstance(result, str) else result_json(result))
    data = None if result is None or isinstance(result, str) else plain(result)
    return False, blocks, cast(dict[str, Any], data) if isinstance(data, dict) else None


# The active metaform each project's map tools last read here, for the person's own agent, which follows it, `map_moved`.
_READ_ON: dict[str, str] = {}


def map_moved(project: str | None) -> str | None:
    """For the person's own agent, the one that follows the active metaform, what its next call is told when the map
    it reads changed since its last call: which map it reads now and that the other is kept. Said once per change, in
    the result of the call that first reads it; nothing for any other agent, which stays on its own metaform, nor for
    a first call (decision of 2026-10-17, pending Rich's confirmation; the wording is his to give)."""
    if not project or catalog.task() != 'user_agent' or os.environ.get(BASE_VARIABLE):
        return None
    try:
        now = home.active_base(project)
    except (OSError, StoreError, Stop):
        return None
    if now is None:
        return None
    before = _READ_ON.get(project)
    _READ_ON[project] = now.id
    if before is None or before == now.id:
        return None
    left = home.base_by_id(project, before)
    kept = f'; {left.name} is kept as it was' if left is not None else ''
    return f'The person made {now.name} the active map: your map tools read {now.name} from here{kept}.'


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
MODULES_URI = 'metaform://modules'
MODULE_TOOLS = re.compile(r'^metaform://(?P<module>[a-zA-Z0-9_.-]+)/tools$')
# What a session reads once its agent's context was compacted, as metaform_catalog compacted=true answers: the record of
# what it was given is forgotten, so each piece comes again at its next use, CTX-045. Read, it forgets.
COMPACTION_URI = 'metaform://runtime/compaction-state'
TEMPLATES: tuple[tuple[str, str, str], ...] = (
    ('metaform://tools/{tool}/instructions', 'Tool usage instructions',
     'Read specific tool usage before execution; the exact delivered revision unlocks this context only.'),
    ('metaform://tools/{tool}/instructions/{op}', 'Operation usage instructions',
     'Read the applicable operation usage before execution, without running the tool.'),
    ('metaform://{module}/tools', 'Module commands',
     'The commands of one active module, using its declared name. Discover modules at metaform://modules.'),
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


# The instruction blocks, MCP-007: every agent's connect message is mcp's `connect_directive` and one link per line
# to each block below that applies to the agent now, in this order, generated here and never typed into a prompt. Each
# block is a resource served whole and exactly as its prompt holds it, so the message stays a few lines and each block
# arrives uncut. The same directive and links open the agent's first turn after every compaction, `opening`, since
# compaction removes what the agent read. A new block is one entry here: its link, when it applies, and its text.
RULES_URI = 'metaform://rules'
MEMORY_URI = 'metaform://memory'
FIRSTRUN_URI = 'metaform://firstrun'
TASK_URI = 'metaform://task/'
PERSON = 'person'  # the name in metaform://task/<name> for the person's own sessions, which no runner started


@dataclasses.dataclass(frozen=True)
class Agent:
    """Who an instruction block's link is decided for: the folder its server serves, the name of the task it runs,
    None for a session no task names, whether the session is the person's own, which no runner started, and the ids
    of the modules on its surface."""
    folder: Path
    task: str | None
    own: bool
    modules: tuple[str, ...]


def served_agent(folder: Path) -> Agent:
    """The agent this server serves, as its runner's environment names it, `catalog.task` and `catalog.dispatched`."""
    return Agent(folder, catalog.task(), not catalog.dispatched(), tuple(module.id for module in surface(folder)))


def dispatched_agent(folder: Path, task: str | None) -> Agent:
    """An agent a runner started, on the task named `task` or on none, for the runner asking what opens its session."""
    return Agent(folder, task, False, tuple(module.id for module in surface(folder)))


@dataclasses.dataclass(frozen=True)
class Reading:
    """A read of an instruction block: the folder, the connecting AI tool, the session the compaction line is for
    (None, or a process's own, where no runner follows it), and whether the connection names a session at all."""
    folder: Path
    client: str | None
    session: str | None
    keyed: bool


@dataclasses.dataclass(frozen=True)
class Block:
    """One instruction block: `link`, its URI when it applies to the agent now, else None; `read`, its text for a read
    of the URI, else None when the URI is not this block's."""
    name: str
    link: Callable[[Agent], str | None]
    read: Callable[[Reading, str], str | None]


def first_run_text(folder: Path) -> str | None:
    """Intake's first-run text while the project has no intake and none is being recorded, `intake.first_run`; None
    otherwise or with the intake module off."""
    for module_id, given in provided(folder, 'intake.first_run'):
        try:
            said = given(context(module_id, folder, surface='mcp'))
        except (Stop, StoreError):
            said = None
        if said:
            return said
    return None


def memory_text(folder: Path) -> str | None:
    """The memory module's instructions prompt, through the prompt store as `memory.prompt` serves it, filled with the
    folder's project; no element is assigned at connect, so its unassigned bullet stands. Before a project {project}
    stays as written. None with the memory module off."""
    project = project_for(folder)
    for _, given in provided(folder, 'memory.prompt'):
        return given(project if project is not None else '{project}')
    return None


def task_link(task: str | None, own: bool) -> str | None:
    """The task block's link: metaform://task/person for the person's own session and metaform://task/intake for the
    intake task, whose text points it to the intake commands; None for every other agent a runner started, whose
    first turn is its instructions, so no block repeats them."""
    return TASK_URI + PERSON if own else TASK_URI + 'intake' if task == 'intake' else None


def _task_read(reading: Reading, uri: str) -> str | None:
    if uri == task_link(catalog.task(), not catalog.dispatched()):
        return task_text(reading.folder, reading.client, reading.session, reading.keyed)
    return None


def _project_read(reading: Reading, uri: str) -> str | None:
    return project_glossary_text(reading.folder, reading.client) if uri == project_uri(reading.folder) else None


BLOCKS: tuple[Block, ...] = (
    Block('rules', lambda _: RULES_URI,
          lambda _, uri: prompt_files.module('mcp', 'connect_rules') or '' if uri == RULES_URI else None),
    Block('metaform', lambda _: GLOSSARY_URI, lambda reading, uri: glossary(reading.folder) if uri == GLOSSARY_URI
          else None),
    Block('memory', lambda agent: MEMORY_URI if 'memory' in agent.modules else None,
          lambda reading, uri: memory_text(reading.folder) if uri == MEMORY_URI else None),
    # every tool the agent can reach, by module, so none is unknown to it and none is pushed into its context
    Block('modules', lambda _: MODULES_URI,
          lambda reading, uri: modules_text(reading.folder) if uri == MODULES_URI else None),
    Block('firstrun', lambda agent: FIRSTRUN_URI if agent.own and first_run_text(agent.folder) else None,
          lambda reading, uri: first_run_text(reading.folder) if uri == FIRSTRUN_URI else None),
    Block('task', lambda agent: task_link(agent.task, agent.own), _task_read),
    Block('project', lambda agent: project_uri(agent.folder), _project_read),
)


def links(agent: Agent) -> list[str]:
    """The links of the instruction blocks that apply to `agent` now, in BLOCKS' order."""
    return [uri for block in BLOCKS if (uri := block.link(agent))]


def opening(agent: Agent) -> str:
    """What opens an agent's session and its first turn after each compaction: mcp's `connect_directive`, then one
    line per link, `links`."""
    directive = prompt_files.module('mcp', 'connect_directive') or ''
    return '\n'.join(line for line in (directive, *links(agent)) if line)


def block_text(folder: Path, uri: str, client: str | None = None, session: str | None = None,
               keyed: bool = True) -> str | None:
    """The text of the instruction block at `uri`, exactly as its prompt holds it; None when no block is there."""
    reading = Reading(folder, client, session, keyed)
    for block in BLOCKS:
        said = block.read(reading, uri)
        if said is not None:
            return said
    return None


def resource_list(folder: Path) -> list[dict[str, Any]]:
    """The fixed resources: Metaform's glossary, the project's own, the tools in one line each, the instructions, then
    each surfaced module's declared resources."""
    own = project_uri(folder)
    applies = links(served_agent(folder))
    blocks = {RULES_URI: ('Rules', 'Read first: the rules every agent works by.'),
              MEMORY_URI: ('Memory', 'How to keep memory in this project.'),
              FIRSTRUN_URI: ('First run', 'What to do first: this project has no intake yet.'),
              **{uri: ('Task', ('What your task is, how to reach the module commands, and what else you need before '
                                'your first call.'))
                 for uri in applies if uri.startswith(TASK_URI)}}
    listed = [*({'uri': uri, 'name': name, 'description': description, 'mime_type': 'text/plain'}
                for uri, (name, description) in blocks.items() if uri in applies),
              {'uri': GLOSSARY_URI, 'name': 'Metaform glossary',
               'description': 'Read first: the terms every agent works by in Metaform, the mcp module\'s glossary '
                              'prompt as written.',
               'mime_type': 'text/plain'},
              *([{'uri': own, 'name': 'Project glossary',
                  'description': "This project's own terms after the peer register standard, generated from its map.",
                  'mime_type': 'text/plain'}] if own else []),
              {'uri': MODULES_URI, 'name': 'Modules',
               'description': "Each active module's name, description, and its commands resource.",
               'mime_type': 'text/plain'},
              {'uri': COMPACTION_URI, 'name': 'After a compaction',
               'description': 'Read once your context was compacted: what Metaform gave you once comes again at its '
                              'next use.',
               'mime_type': 'text/plain'},
              {'uri': INSTRUCTIONS_URI, 'name': 'Agent instructions',
               'description': "The guide to this folder's modules and state, as metaform instructions prints it.",
               'mime_type': 'text/plain'}]
    for module in surface(folder):
        listed += [{'uri': held.uri, 'name': held.name, 'description': held.description, 'mime_type': held.mime_type}
                   for held in module.resources if not held.fields]
    return [*listed, *skill_extension.resources(folder)]


def glossary_repeat(folder: Path, session: str | None, uri: str) -> str | None:
    """The line a second read of a glossary in one session answers with while it is unchanged, `already_read`: the
    first is still in the agent's context, so the text is not given twice; None for the first read, a changed one, or
    a session that keeps no record. `uri` is metaform://metaform or the project's own."""
    if session is None:
        return None
    text = glossary(folder) if uri == GLOSSARY_URI else project_glossary_text(folder)
    digest = _digest(text)
    if record_shown(session, f'doc:{uri}', digest) != digest:
        return None
    again = (f'call {OWN}_instructions with module=metaform' if uri == GLOSSARY_URI else
             'call map_glossary with view=full')
    return prompt_files.module('mcp', 'already_read', uri=uri, again=again)


def module_templates(folder: Path) -> list[tuple[str, str, str, str]]:
    """Each surfaced module's resource templates, a URI with `{field}` parts each read through the module's verb
    with the fields as its nouns, MCP-037: as (template, name, description, media type)."""
    return [(held.uri, held.name, held.description, held.mime_type)
            for module in surface(folder) for held in module.resources if held.fields]


async def read_resource_text(folder: Path, uri: str, *, client: str | None = None, session: str | None = None,
                             keyed: bool = True) -> tuple[str, str] | None:
    with collecting_agent_context(session) as receipts:
        found = await _read_resource_text(folder, uri, client=client, session=session, keyed=keyed)
    if found is None:
        return None
    text, mime = found
    if uri == MODULES_URI or MODULE_TOOLS.fullmatch(uri):
        text = await anyio.to_thread.run_sync(discovery_delivery, folder, session, uri, text)
    components: list[dict[str, Any]] = []
    if uri == MEMORY_URI:
        one = await anyio.to_thread.run_sync(prompt_files.resolve, 'prompt.memory:instructions')
        one.update(text=text, bindings={'project': str(project_for(folder) or '{project}')})
        components = [one]
    elif uri == RULES_URI:
        components = [await anyio.to_thread.run_sync(prompt_files.resolve, 'prompt.mcp:connect_rules')]
    elif uri == GLOSSARY_URI:
        one = await anyio.to_thread.run_sync(prompt_files.resolve, 'prompt.mcp:glossary')
        one['text'] = text
        components = [one]
    elif uri == project_uri(folder):
        components = [prompt_files.component('map:project_glossary', text)]
    elif uri == task_link(catalog.task(), not catalog.dispatched()):
        components = [prompt_files.component('mcp:task_' + uri.removeprefix(TASK_URI), text)]
    if components:
        prepared = await anyio.to_thread.run_sync(prepare_agent_context, folder, session, components)
        due = cast(list[dict[str, Any]], prepared['components'])
        if due:
            text = str(prepared['text'])
            await anyio.to_thread.run_sync(functools.partial(record_agent_context, folder, session, due,
                                                            epoch=int(prepared['epoch']), channel='mcp_resource'))
        else:
            text = prompt_files.module('mcp', 'already_read', uri=uri, again='use the current context') or ''
    if receipts:
        await anyio.to_thread.run_sync(_commit_response, receipts, [text], None, 'mcp_resource')
    return text, mime


async def _read_resource_text(folder: Path, uri: str, *, client: str | None = None, session: str | None = None,
                              keyed: bool = True) -> tuple[str, str] | None:
    """A resource's text and media type, or None when this folder serves no such resource. The instruction blocks are
    read first, so metaform://metaform is Metaform's own glossary whatever the folder's project or modules are called.
    `session` and `keyed` say what metaform://task/<name> tells this connection, as `task_text` says."""
    if guide := GUIDE_URI.fullmatch(uri):
        handle = guide.group('handle')
        named = (f'handle:{handle}' if handle and (session is None or session.startswith('process:'))
                 else session)
        if named is None:
            handle = uuid.uuid4().hex[:12]
            named = f'handle:{handle}'
        text = await anyio.to_thread.run_sync(tool_guide, folder, guide.group('tool'), guide.group('op'), named)
        if handle:
            text = f'{HANDLE}: {handle}\nUse this handle on subsequent tool calls.\n\n' + text
        return text, 'text/plain'
    said = await anyio.to_thread.run_sync(functools.partial(block_text, folder, uri, client, session, keyed))
    if said is not None:
        return said, 'text/plain'
    if matched_module := MODULE_TOOLS.fullmatch(uri):
        module = matched_module.group('module')
        text = await anyio.to_thread.run_sync(module_tools_text, folder, module)
        if keyed and session is not None:
            record_shown(session, catalog.OPEN_KEY, module)
            record_shown(session, PENDING_KEY, module)
        return text, 'text/plain'
    for module in await anyio.to_thread.run_sync(surface, folder):
        for held in module.resources:
            fields = held.matched(uri)
            if held.uri == uri or fields is not None:
                kinds = {noun.name: noun.kind for verb in module.verbs if verb.name == held.verb for noun in verb.nouns}
                given = {name: int(value) if kinds.get(name) == 'int' and value.isdigit() else value
                         for name, value in (fields or {}).items()}  # a number in the path is a number noun
                error, blocks = await run_tool(folder, f'{module.id}_{held.verb}', given, client=client,
                                               session=session, instruction_read=next(
                                                   verb.effect == 'read' for verb in module.verbs
                                                   if verb.name == held.verb))
                if error and fields is not None:  # a template's URI naming what is not there, MCP-037
                    message, _, step = blocks[0].removeprefix('Error: ').partition('\nNext: ')
                    raise Missing(message, step or 'list the resources and their templates')
                if error:
                    raise Stop(blocks[0], 'read resource ' + INSTRUCTIONS_URI)
                return '\n'.join(blocks), held.mime_type
    if uri == INSTRUCTIONS_URI:
        return await anyio.to_thread.run_sync(functools.partial(instructions, folder, surface='mcp')), 'text/plain'
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
    written inside its quotes; then a human-readable reference of tools and module rules. Nothing is reworded: a term the view shows is the prompt's own line."""
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
    names what was read, so a view that already holds it is answered with `unchanged` alone: the view reads again on
    each change to the ticket while it is on screen, views.Traces, and a line the agent is still writing changes in
    place."""
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
    if kind == 'resource' and ref in ('metaform://instructions/{module}', 'metaform://{module}/tools') and argument == 'module':
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
    map and node views, and the tasks extension, for verbs that can take long. Completion fills Address arguments and
    `#n` references, and a client listening for a node's brief hears when items are added there."""
    from contextlib import asynccontextmanager

    from mcp import types
    from mcp.server import Server
    from mcp.server.caching import CacheHint
    from mcp.server.lowlevel import NotificationOptions
    from mcp.server.models import InitializationOptions
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
    traces = views.Traces()  # what the trace views follow, so a read of an unchanged ticket reads nothing

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

    def handled(schema: dict[str, Any], on: bool) -> dict[str, Any]:
        """A tool's input schema with `session_handle`, for a connection whose calls name no session otherwise."""
        if not on:
            return schema
        said = prompt_files.module('mcp', 'handle_argument') or ''
        return {**schema, 'properties': {**cast(dict[str, Any], schema.get('properties') or {}),
                                         HANDLE: {'type': 'string', 'description': said}}}

    def tool(one: Listed, shown: bool, unkeyed: bool = False) -> Any:
        hints = one.annotations()
        view = views.SHOWN_BY.get(one.name) if shown else None
        made = types.Tool(name=one.name, description=usage_description(one), input_schema=handled(one.schema(), unkeyed),
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

    def catalog_tool(unkeyed: bool = False) -> Any:
        """metaform_catalog as it is listed: the tool every agent is listed, to find the others by purpose."""
        said = prompt_files.module('mcp', 'catalog_tool_unkeyed' if unkeyed else 'catalog_tool') or ''
        return types.Tool(name=catalog.CATALOG, description=said,
                          input_schema=handled(catalog_schema(folder, unkeyed), unkeyed),
                          annotations=types.ToolAnnotations(read_only_hint=False, destructive_hint=False,
                                                            idempotent_hint=False, open_world_hint=False))

    def build(shown: bool, client: str | None = None, session: str | None = None) -> list[Any]:
        """The tools listed to a session, MCP-003: `listed_names`, each as `tool` makes it; over HTTP to a listing
        that names no session, each takes the session handle its calls name their session by."""
        everything = listing(folder, client)
        names = listed_names(folder, session)
        unkeyed = (http and session is None) or (not http and not os.environ.get('METAFORM_SESSION'))
        listed = [tool(everything[name], shown, unkeyed) for name in names if name in everything]
        if catalog.CATALOG in names:
            listed = sorted([*listed, catalog_tool(unkeyed)], key=lambda one: one.name)
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

    def current(session: str | None = None) -> dict[str, Any]:
        """What each list follows: the tools are the names listed to the session, which change with the modules on
        the surface and the module it has open."""
        both = tuple(module.id for module in surface(folder)), on_surface('chassis', folder)
        return {'tools': listed_names(folder, session), 'prompts': both, 'resources': both[0]}

    def session_of(ctx: Any, handle: Any = None) -> str | None:
        """The agent session a request is made in, MCP-039: the one Paperclip's gateway names; over stdio this
        process's, the host that started it; over HTTP the client's Mcp-Session-Id, one connection's conversation,
        so what it was told is told once there too; else the session handle metaform_catalog gave, passed as the call's
        `handle` or in the request's _meta; None for an HTTP request that names none."""
        headers = ctx.request.headers if ctx.request is not None else None
        named = gateway_session(headers)
        if named is not None:
            return named
        if not http and os.environ.get('METAFORM_SESSION'):
            return served_session(client_of(ctx))
        given = headers.get(MCP_SESSION_ID_HEADER) if http and headers is not None else None
        if given:
            return f'http:{given}'
        meta: Any = cast(dict[str, Any], dict(ctx.params or {})).get('_meta') if ctx.params else None
        held = handle or (cast(dict[str, Any], meta).get(HANDLE_META) if isinstance(meta, dict) else None)
        if isinstance(held, str) and HANDLED.fullmatch(held):
            return f'handle:{held}'
        return served_session(client_of(ctx)) if not http else None

    def follows(ctx: Any) -> bool:
        """Whether the tools listed to the caller follow its session, so a module it opens changes them: a request
        that names its session by itself, which an argument the model passes cannot do for tools/list."""
        return session_of(ctx) is not None

    def bus_session(ctx: Any) -> str | None:
        """Whose listing the listen streams follow: over stdio the one session; over HTTP no session's, since every
        client's stream hears it."""
        return None if http else session_of(ctx)

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

    async def announce(ctx: Any, fired: list[dict[str, Any]] | None = None) -> None:
        """After a call: the lists' changes to the listen streams and the caller's connection, then the watched nodes
        the call's changes, `fired`, can concern."""
        now = await anyio.to_thread.run_sync(current, session_of(ctx))
        heard = now if not http else await anyio.to_thread.run_sync(current, None)
        own = connection(ctx)
        for kind in ('tools', 'prompts', 'resources'):
            await to_bus(kind, heard[kind])
            if own is not None:
                if own[kind] is not None and own[kind] != now[kind]:
                    await notices[kind][1](ctx.session)
                own[kind] = now[kind]
        if any(map(watch.concerns, fired or ())):
            await watch.check()

    async def listed_now(ctx: Any, kind: str) -> None:
        """A list was just given: the listen streams hear a change first, and the caller's own connection has seen
        it, while every other connection's record waits for that connection's next request."""
        now = (await anyio.to_thread.run_sync(current, session_of(ctx)))[kind]
        await to_bus(kind, now if not http else (await anyio.to_thread.run_sync(current, bus_session(ctx)))[kind])
        own = connection(ctx)
        if own is not None:
            own[kind] = now

    async def list_tools(ctx: Any, params: Any) -> Any:
        session = session_of(ctx)
        tools = await anyio.to_thread.run_sync(build, apps(ctx), client_of(ctx), session)
        if session is not None:
            await anyio.to_thread.run_sync(relisted, session, await anyio.to_thread.run_sync(open_module, folder,
                                                                                               session))
        await listed_now(ctx, 'tools')
        return types.ListToolsResult(tools=tools)

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
        handle = arguments.pop(HANDLE, None)
        session = session_of(ctx, handle)
        if name == catalog.CATALOG:  # the catalog itself, or a tool it runs for an AI tool that keeps its first list
            run = arguments.get('tool')
            if run is None:
                error, blocks = await anyio.to_thread.run_sync(catalog_call, arguments, session, follows(ctx))
                await announce(ctx, [])
                return outcome(error, blocks, None)
            inner = arguments.get('arguments', {})
            if not isinstance(run, str) or run == catalog.CATALOG or not isinstance(inner, dict):
                return outcome(True, [(f'Error: tool is the name of another tool, and arguments an object.\n'
                                       f'Next: {schema_step(catalog.CATALOG)}')], None)
            name, arguments = run, dict(cast(dict[str, Any], inner))
            if HANDLE in arguments:
                session = session_of(ctx, arguments.pop(HANDLE))
        listed = (await anyio.to_thread.run_sync(listing, folder)).get(name)
        if listed is not None and listed.task == 'session' and not tasked.declared(capabilities(ctx)):
            raise MCPError(-32021, 'Missing required client capability',
                           {'requiredCapabilities': {'extensions': {tasked.EXTENSION: {}}}})
        shape: shaping.Shape | None = None
        if listed is not None and listed.verb is not None:  # a module tool's result, as the agent asks for it
            shape, wrong = shaping.taken(arguments, {noun.name for noun in listed.verb.nouns})
            if wrong is not None:
                return outcome(True, [f'Error: {wrong}\nNext: {schema_step(name)}'], None)
        if name == 'map_glossary' and shape is not None and shape.view == 'triage' and \
                not set(arguments) - {'layers', 'project'} and (own := await anyio.to_thread.run_sync(project_uri,
                                                                                                      folder)):
            repeat = await anyio.to_thread.run_sync(glossary_repeat, folder, session, own)
            if repeat:  # the project's glossary, read already in this session, as map_glossary or its resource
                return outcome(False, [repeat], None)
        try:
            required = await anyio.to_thread.run_sync(instruction_required, folder, name, arguments, session)
        except Stop as stop:
            error, blocks = _error(stop, folder)
            return outcome(error, blocks, None)
        if required is not None:
            return outcome(True, [result_json(required)], required)
        given = arguments
        tasked_as = listed.task if listed is not None and tasked.declared(capabilities(ctx)) else False
        headers = ctx.request.headers if ctx.request is not None else None
        identity = gateway_identity(headers)
        if tasked_as is True and 'group' in held:
            project = await anyio.to_thread.run_sync(tasked.owning, folder)
            if project is not None:  # a folder that is no project's keeps no task, so its call is answered as ever
                return await start_task(project, name, given, client, session, identity)
        fired: list[dict[str, Any]] = []
        try:
            error, blocks, structured = await answer(folder, name, given, client=client,
                                                     session=session, identity=identity, shape=shape)
        finally:  # what the tool changed, fired on the event bus from a worker thread, VIEW-018; a module enabled or
            # disabled since this server started is loaded or dropped first, BASE-037
            fired = await anyio.to_thread.run_sync(events.announce, folder, 'mcp')
        if listed is not None and not error:  # errors carry only the error and its next step
            op = given.get('op') if isinstance(given.get('op'), str) else None
            if op is None and listed.verb is not None and ops_of(listed.verb) and 'id' in given:
                op = 'read'  # a record named by id with no op is read, which no op's own help is for
            guide = await anyio.to_thread.run_sync(guided, listed, client, session, op)
            blocks = [guide, *blocks] if guide else blocks
        if not error and shape is not None and shape.view == 'triage' and shape.given and listed is not None and \
                listed.verb is not None and looks_up(listed.verb) and session is not None and \
                await anyio.to_thread.run_sync(record_shown, session, 'announce:triage', 1) is None:
            note = prompt_files.module('mcp', 'triage_note')
            blocks = [*blocks, note] if note else blocks
        await announce(ctx, fired)
        if not error:
            discussed(ctx, name, given)
        if tasked_as == 'session' and not error:
            launched = structured or {}
            task_id, project = launched.get('task_id'), launched.get('project_id')
            if not isinstance(task_id, str) or not isinstance(project, str):
                raise MCPError(-32603, 'Task launch did not return task_id and project_id')
            seeded = await anyio.to_thread.run_sync(tasked.seed_session, folder, project, task_id)
            if seeded is None:
                raise MCPError(-32603, 'Failed to retrieve the launched task')
            return seeded
        return outcome(error, blocks, structured)

    def guided(listed: Listed, client: str | None, session: str | None, op: str | None = None) -> str:
        """The guidance the call's result carries, `guidance`, in the agent session the call is made in."""
        try:
            ctx = context('mcp', folder, surface='mcp', client=client, session=session)
        except (Stop, StoreError):
            return ''
        return guidance(folder, listed, ctx, op)

    def catalog_call(arguments: dict[str, Any], session: str | None, listing_follows: bool) -> Outcome:
        """metaform_catalog's own answer, `run_catalog`, its arguments checked as a chassis tool's are. A call that
        names no session, over HTTP on the July wire, is given a session handle first, `catalog_handle`, so each guide
        can be given it once from its next call."""
        notices: list[str] = []
        told: list[str] = []
        if session is None and http:
            handle = uuid.uuid4().hex[:12]
            session = f'handle:{handle}'
            told = [line for line in (prompt_files.module('mcp', 'catalog_handle', handle=handle, argument=HANDLE),
                                      prompt_files.module('mcp', 'connect_compaction')) if line]
        try:
            given = _checked('catalog', arguments, catalog_schema(folder), notices)
            error, blocks = run_catalog(folder, given, session, listing_follows)
        except Stop as stop:
            return _error(stop, folder)
        before = (['\n'.join(notices)] if notices else []) + (['\n'.join(told)] if told else [])
        # after a compaction the rules and the glossary's order come first in the turn, compaction_state
        return error, blocks + before if given.get('compacted') is True else before + blocks

    async def start_task(project: str, name: str, given: dict[str, Any], client: str | None,
                         session: str | None, identity: dict[str, str]) -> Any:
        """A tool call answered with a task: the task is written first, so tasks/get finds it at once, then the call
        runs in this process and the task keeps its result."""
        said = prompt_files.module('mcp', 'task_working', tool=name) or f'{name} is running.'
        made = await anyio.to_thread.run_sync(tasked.create, running, project, name, said)

        async def work() -> dict[str, Any]:
            try:
                error, blocks, structured = await answer(folder, name, given, client=client,
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
        params = cast(dict[str, Any], given)
        if read == 'focus':  # the Address the agent last named, kept in this process; nothing is read for it
            return outcome(False, [said], {'address': None, 'tool': None, 'seq': 0, **focus.get(seen_by, {})})
        mark = None
        if read == 'trace':  # read again only when a change to the ticket came after the view's mark
            project = await anyio.to_thread.run_sync(tasked.owning, folder)
            given_mark = str(params.pop('mark', '') or '')
            if project is not None:
                mark = traces.track(project, str(params.get('id') or ''))
                if given_mark == mark and params.get('digest'):
                    return outcome(False, [said], {'digest': params.get('digest'), 'unchanged': True, 'mark': mark})
        try:
            found = await anyio.to_thread.run_sync(view_read, folder, read, params)
        except (Stop, StoreError) as stop:
            return outcome(*_error(stop, folder), None)
        data = plain(found)
        if mark is not None and isinstance(data, dict):
            data = {**cast(dict[str, Any], data), 'mark': mark}
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
        await announce(ctx, await anyio.to_thread.run_sync(events.announce, folder, 'mcp'))
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
        if uri.startswith('skill://'):
            supplied = await anyio.to_thread.run_sync(skill_extension.read, folder, uri)
            if supplied is not None:
                raw, mime = supplied
                document: Any
                if mime.startswith('text/') or mime in ('application/json', 'application/xml'):
                    try:
                        document = types.TextResourceContents(uri=uri, text=raw.decode('utf-8'), mime_type=mime)
                    except UnicodeDecodeError:
                        document = types.BlobResourceContents(uri=uri, blob=base64.b64encode(raw).decode('ascii'),
                                                              mime_type=mime)
                else:
                    document = types.BlobResourceContents(uri=uri, blob=base64.b64encode(raw).decode('ascii'),
                                                          mime_type=mime)
                return types.ReadResourceResult(contents=[document], ttl_ms=0, cache_scope='private')
        if apps_on and uri in views.NAMES:  # a view, read by a client that renders MCP Apps
            config = await anyio.to_thread.run_sync(view_config, uri)
            text = await anyio.to_thread.run_sync(views.html, uri, config)
            page = types.TextResourceContents(uri=uri, text=text, mime_type=views.MIME)
            page.meta = views.meta(uri)
            # A view changes only with the installation and the folder's project, so a host keeps it for the list
            # hint's time, not more, so a rebuilt map view reaches the next call.
            return types.ReadResourceResult(contents=[page], ttl_ms=CACHE_TTL_MS, cache_scope='private')
        if uri == COMPACTION_URI:
            said = await anyio.to_thread.run_sync(compaction_state, folder, session_of(ctx), follows(ctx))
            return types.ReadResourceResult(contents=[types.TextResourceContents(uri=uri, text=said,
                                                                                 mime_type='text/plain')])
        # A resource that does not exist: -32602 on the July 2026 wire, which moved it there, -32002 before it.
        missing_code = -32602 if ctx.protocol_version in MODERN_PROTOCOL_VERSIONS else -32002
        try:
            client = client_of(ctx)
            found = await read_resource_text(folder, uri, client=client, session=session_of(ctx),
                                             keyed=not http or session_of(ctx) is not None)
        except Missing as missing:
            raise MCPError(missing_code, f'Error: {missing}\nNext: {missing.next_step}') from None
        except (Stop, StoreError) as stop:
            raise MCPError(-32603, f'Error: {stop}\nNext: {mcp_next(str(stop.next_step), folder)}') from None
        if found is None:
            raise MCPError(missing_code,
                           f'No resource {uri} on this surface.\nNext: list the resources and their templates')
        text, mime = found
        if MODULE_TOOLS.fullmatch(uri):
            await announce(ctx, [])
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
            watch.group = group
            try:
                yield {}
            finally:
                held.pop('group', None)
                watch.group = None
                group.cancel_scope.cancel()
                watch.stop()
                traces.stop()

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
    skill_extension.register(server, folder)

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
                # The same few lines on every wire: what each block says to this connection is in the block.
                composed = await anyio.to_thread.run_sync(connect_instructions, folder)
                result = {**cast(dict[str, Any], result), 'instructions': composed}
            return result
    server.middleware.append(live)

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
        serving(uvicorn.Config(app, host=bind, port=port, log_level='warning')).run()
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
    watched or read. After a call this server answers, and on a `map.changed` another process of the home publishes,
    the watched nodes are checked when the change can concern them, `concerns`: one with a higher number now is
    announced with `notifications/resources/updated` for its URI, a notice the client reads the brief again for, never
    the items themselves. Changes heard while a check runs make one more check after it, `checks`."""

    def __init__(self, folder: Path, bus: Any, updated: Any) -> None:
        self.folder, self.bus, self.updated = folder, bus, updated
        self.latest: dict[str, int] = {}
        self.memory_latest: dict[str, str] = {}
        self.listeners: dict[str, int] = {}  # how many open streams name each URI
        self.sessions: dict[str, list[Any]] = {}  # the 2025-handshake sessions subscribed to each URI
        self.listener: Any = None
        self.token: Any = None
        self.project: str | None = None  # the folder's project, read once a node is watched
        self.group: Any = None  # the server's task group, which a check heard from another process runs in
        self.checking = False
        self.again = False  # a change heard while a check ran: one more check after it
        self.pending_uris: set[str] = set()

    def _number(self, uri: str) -> int | None:
        found = ADDRESS.match(uri)
        if found is None or found.group('number') is not None:
            return None
        project = project_for(self.folder)
        return None if project is None else Store(project).latest_number(found.group('address'))

    def _memory_revision(self, uri: str) -> str:
        found = ADDRESS.match(uri)
        if found is None or found.group('number') is not None:
            return ''
        project = self.project or project_for(self.folder)
        if project is None:
            return ''
        return '|'.join(str(read(project, found.group('address')))
                        for _, read in provided(self.folder, 'memory.revision'))

    async def open(self, uris: list[str], session: Any = None) -> None:
        for uri in uris:
            number = await anyio.to_thread.run_sync(self._number, uri)
            if number is None:
                continue
            self.latest.setdefault(uri, number)
            self.memory_latest.setdefault(uri, await anyio.to_thread.run_sync(self._memory_revision, uri))
            if session is None:
                self.listeners[uri] = self.listeners.get(uri, 0) + 1
            elif session not in self.sessions.setdefault(uri, []):
                self.sessions[uri].append(session)
        if self.latest and self.listener is None:
            self.project = await anyio.to_thread.run_sync(project_for, self.folder)
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
                self.memory_latest.pop(uri, None)
                self.pending_uris.discard(uri)

    async def seen(self, uri: str) -> None:
        """A brief read anew: what it showed is what the client has, so only items added after it are news."""
        if uri in self.latest:
            number = await anyio.to_thread.run_sync(self._number, uri)
            if number is not None:
                self.latest[uri] = number

    def concerns(self, payload: dict[str, Any]) -> bool:
        """Whether a change can have numbered an item at a watched node, decided from the change alone: a node is
        watched, the change is the folder's project's, and it wrote a table that can hold an item. A module's own
        payload, such as dispatch's (`tables` its module's name), and a change only to dispatch's tables or the mcp
        module's own, the agents' threads, signals and sessions, the tool tasks and the A2A records, numbers
        nothing. A change that names no tables may have changed anything."""
        if not self.latest or payload.get('project') not in (None, '', self.project):
            return False
        tables: Any = payload.get('tables')
        if isinstance(tables, str):
            return False
        if isinstance(tables, list) and tables:
            if all(str(table) in ('memory.encounters',) or str(table) == 'dispatch' or str(table).startswith(QUIET)
                   for table in cast(list[Any], tables)):
                return False
            if all(str(table).startswith('memory.') for table in cast(list[Any], tables)):
                addresses = {str(kind)[7:] for kind in payload.get('kinds', [])
                             if str(kind).startswith('memory:')}
                if addresses:
                    return any((match := ADDRESS.match(uri)) is not None and match.group('address') in addresses
                               for uri in self.latest)
        return True

    async def check(self, uris: set[str] | None = None) -> None:
        for uri in list(self.latest if uris is None else uris):
            if uri not in self.latest:
                continue
            last = self.latest[uri]
            number = await anyio.to_thread.run_sync(self._number, uri)
            memory_revision = await anyio.to_thread.run_sync(self._memory_revision, uri)
            if number is None or uri not in self.latest or \
                    (number <= last and memory_revision == self.memory_latest.get(uri, '')):
                continue
            self.latest[uri] = number
            self.memory_latest[uri] = memory_revision
            if uri in self.listeners:
                await self.bus.publish(self.updated(uri=uri))
            for session in list(self.sessions.get(uri, ())):
                try:
                    await session.send_resource_updated(uri)
                except Exception:  # noqa: BLE001  a session gone since it subscribed hears nothing more
                    self.sessions[uri].remove(session)

    async def checks(self) -> None:
        """Check, and once more for whatever was heard meanwhile, so a burst of changes costs at most two checks."""
        self.checking = True
        try:
            self.again = True
            while self.again:
                self.again = False
                wanted = self.pending_uris
                self.pending_uris = set()
                await self.check(wanted or None)
        finally:
            self.checking = False

    def _wanted(self, uris: set[str] | None = None) -> None:
        """In the server's loop: a check, or one more after the one running."""
        self.pending_uris.update(self.latest if uris is None else uris)
        if self.checking:
            self.again = True
        elif self.group is not None:
            self.group.start_soon(self.checks)

    def _heard(self, payload: dict[str, Any]) -> None:
        """A `map.changed` from another process, heard on the listener's thread: one that can concern a watched node
        asks the server's loop for a check, without waiting for it."""
        if not self.concerns(payload):
            return
        addresses = {str(kind)[7:] for kind in payload.get('kinds', []) if str(kind).startswith('memory:')}
        tables = cast(list[Any], payload.get('tables') or [])
        restricted = bool(addresses) and all(str(table).startswith('memory.') for table in tables)
        wanted = {uri for uri in self.latest if not restricted or
                  ((match := ADDRESS.match(uri)) is not None and match.group('address') in addresses)}
        try:
            anyio.from_thread.run_sync(self._wanted, wanted, token=self.token)
        except Exception:  # noqa: BLE001, S110  a server that stopped has nothing left to tell
            pass

    def stop(self) -> None:
        if self.listener is not None:
            self.listener.close()
            self.listener = None


# What numbers nothing at a node: dispatch's own tables, the agents' threads, signals and sessions, and the mcp
# module's own, its tool tasks and A2A records, Watch.concerns.
QUIET = ('dispatch.', 'mcp.')


def serving(config: Any) -> Any:
    """uvicorn's server waiting on its exit rather than looking for it ten times a second, QUAL-015: uvicorn's own main
    loop wakes every 0.1 s to read `should_exit`; this one sleeps until the flag is set, by uvicorn's signal handler or
    anything else, as the node module's server does."""
    import asyncio
    import contextlib

    import uvicorn

    class Serving(uvicorn.Server):
        def __init__(self, config: uvicorn.Config) -> None:
            self.loop: asyncio.AbstractEventLoop | None = None
            self.exiting = asyncio.Event()
            self.exit = False
            super().__init__(config)

        @property
        def should_exit(self) -> bool:  # pyright: ignore[reportIncompatibleVariableOverride]
            return self.exit

        @should_exit.setter
        def should_exit(self, value: bool) -> None:
            self.exit = value
            if value and self.loop is not None:
                with contextlib.suppress(RuntimeError):  # its loop has closed: it is not serving
                    self.loop.call_soon_threadsafe(self.exiting.set)

        async def startup(self, sockets: list[Any] | None = None) -> None:
            self.loop = asyncio.get_running_loop()
            await super().startup(sockets=sockets)

        async def main_loop(self) -> None:
            await self.on_tick(0)  # the default headers, as uvicorn's own first tick sets them
            if not self.should_exit:
                await self.exiting.wait()
    return Serving(config)


def add_tasks(server: Any, folder: Path, running: Any, types: Any, error_type: Any) -> None:
    """`tasks/get`, `tasks/update` and `tasks/cancel` of the tasks extension, BASE-030, on the tool calls kept as
    tasks and assigned agent sessions; each refused to a client that does not declare the extension, -32021, and for
    an unknown task, -32602."""
    from pydantic import Field

    from . import tasks as tasked

    class TaskParams(types.RequestParams):
        task_id: str

    class UpdateParams(TaskParams):
        input_responses: dict[str, Any] = Field(default_factory=dict[str, Any])

    def required(ctx: Any) -> str | None:
        """The project whose store keeps the tool-call tasks, None where there is none; refused to a client without
        the extension."""
        if not tasked.declared(ctx.session.client_capabilities):
            raise error_type(-32021, 'Missing required client capability',
                             {'requiredCapabilities': {'extensions': {tasked.EXTENSION: {}}}})
        return tasked.owning(folder)

    def missing() -> Any:
        return error_type(-32602, 'Failed to retrieve task: Task not found')

    async def get(ctx: Any, params: Any) -> Any:
        project = await anyio.to_thread.run_sync(required, ctx)
        detail = await anyio.to_thread.run_sync(tasked.detailed, project, params.task_id, folder)
        if detail is None:
            raise missing()
        return {**detail, 'resultType': 'complete'}

    async def update(ctx: Any, params: Any) -> Any:
        project = await anyio.to_thread.run_sync(required, ctx)
        if not await tasked.update(project, params.task_id, dict(params.input_responses), folder):
            raise missing()
        return {'resultType': 'complete'}

    async def cancel(ctx: Any, params: Any) -> Any:
        project = await anyio.to_thread.run_sync(required, ctx)
        try:
            if not await tasked.cancel(running, project, params.task_id, folder):
                raise missing()
        finally:  # the cancel's change, so the process running the task hears it, BASE-053
            await anyio.to_thread.run_sync(events.announce, folder, 'mcp')
        return {'resultType': 'complete'}

    server.add_request_handler('tasks/get', TaskParams, get)
    server.add_request_handler('tasks/update', UpdateParams, update)
    server.add_request_handler('tasks/cancel', TaskParams, cancel)
