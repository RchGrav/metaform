"""The MCP server, MCP-002: the official SDK's low-level Server over stdio.

Tools are computed on every request from the live module declarations and the
folder's command surface, MCP-003 and MCP-004, plus the chassis tools that
always run, `set`, `feedback`, `list_reports` and `read_report`, CLI-022 and
BASE-045. Each call gets its own Context, BASE-028, with its arguments checked
as the command line checks them, MCP-005: a coroutine verb is awaited in the
server's loop, so the host's cancellation reaches it; a plain function runs in
a worker thread. The result is one text block of `say` lines, when there are
any, and one block holding the result, BASE-036.
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any, cast

import anyio

from metaform import changes, home, settings
from metaform.context import project_for
from metaform.data import Store, StoreError, prompts
from metaform.instructions import on_surface
from metaform.module import (Context, Module, Stop, Verb, call, context, feedback, instructions, list_reports,
                             on_this_system, read_report, result_json, setting_value, surface, tool_arguments)

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
    'feedback': ('Save feedback on the Metaform process, with a report and the shape you could not submit when you '
                 'have them. Always available.',
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
}
ORIGIN = _text('The origin, by its short id; without it, the project\'s selected origin, the one established last.')
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
    'clear_project': (("Remove a project's metaforms and reports, as metaform clear project does, PROJ-025. Its "
                       'registration, folder, settings, origins and variants stay. Caution: without confirm it only '
                       'says what it would remove.'),
                      {'type': 'object', 'additionalProperties': False,
                       'properties': {'confirm': {'type': 'boolean',
                                                  'description': 'Run it. Without it the tool only explains.'},
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
    """`feedback`, `list_reports` and `read_report`: always on the surface, so an agent can always report."""
    notices: list[str] = []
    try:
        given = _checked(name, arguments, CHASSIS[name][1], notices)
        project = given.pop('project', None)
        if name == 'feedback':
            result = result_json(feedback(folder, given.pop('text'), project=project, **given))
        elif name == 'list_reports':
            result = result_json(list_reports(folder, project=project, **given))
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
    if name == 'clear_project':
        project = project_for(folder, given.pop('project', None)) or _no_project()
        if home.project(project) is None:
            raise Stop(f'No project {project} is registered.', 'metaform list projects')
        if not given.get('confirm', False):
            raise Stop(home.to_clear(project).caution, 'If you are sure: call clear_project with confirm true')
        cleared = home.clear_project(project)
        result = cleared.to_dict()
        if cleared.not_removed:  # still on disk, and what to do, as a notice and never an error, BASE-044
            result['notices'] = [{'where': 'not_removed', 'message': f'{cleared.left} '
                                  f'{cleared.remedy("call clear_project with confirm true again")}'}]
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
             lines: list[str]) -> Context:
    project = arguments.get('project')
    layers = arguments.get('layers')
    confirmed = arguments.get('confirm', False)
    if project is not None and not isinstance(project, str):
        raise Stop('project is a registered project id, as text.', 'metaform list projects')
    if layers is not None and (not isinstance(layers, list)
                               or not all(isinstance(item, str) for item in cast(list[Any], layers))):
        raise Stop('layers is a list of layer names or tags.', 'metaform map layers')
    if not isinstance(confirmed, bool):
        raise Stop('confirm is true or false.', f'If you are sure: call {name} with confirm true')
    if verb.caution and not confirmed:
        raise Stop(verb.caution, f'If you are sure: call {name} with confirm true')
    nouns, switches, notices = tool_arguments(module.id, verb, arguments, ignore=PER_CALL, folder=folder)
    lines.extend(f'Notice: {key}: {message}' for key, message in notices)
    if layers is not None:
        switches['layers'] = [str(item) for item in cast(list[Any], layers)]
    return context(module.id, folder, project=project, nouns=nouns, switches=switches, sink=lines.append,
                   surface='mcp')


async def run_tool(folder: Path, name: str, arguments: dict[str, Any]) -> Outcome:
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
        ctx = await anyio.to_thread.run_sync(_prepare, folder, module, verb, name, dict(arguments), lines)
        if inspect.iscoroutinefunction(verb.run):
            result = await verb.run(ctx)
        else:
            result = await anyio.to_thread.run_sync(call, verb.run, ctx)
    except Stop as stop:
        return _error(stop)
    except Exception as error:  # noqa: BLE001  any failure of a module's verb goes back to the host, MCP-006
        return True, [f'Error: {type(error).__name__}: {error}\nNext: metaform list modules']
    blocks = ['\n'.join(lines)] if lines else []
    if result is not None:
        blocks.append(result if isinstance(result, str) else result_json(result))
    return False, blocks


def serve(folder: Path) -> None:
    from mcp import types
    from mcp.server import Server
    from mcp.server.stdio import stdio_server

    from metaform import __version__

    def build() -> list[Any]:
        found = [types.Tool(name=name, description=verb.summary + (f' Caution: {verb.caution}' if verb.caution
                                                                    else ''),
                            input_schema=verb_schema(verb, folder))
                 for name, (_, verb) in tools(folder).items()]
        found.append(types.Tool(name='set', description="Save settings for the server's folder, as metaform set "
                                                        'does.', input_schema=set_schema(folder)))
        found += [types.Tool(name=name, description=description, input_schema=schema)
                  for name, (description, schema) in CHASSIS.items()]
        if on_surface('chassis', folder):
            found += [types.Tool(name=name, description=description, input_schema=schema)
                      for name, (description, schema) in SURFACED.items()]
        return found

    async def list_tools(ctx: Any, params: Any) -> Any:
        return types.ListToolsResult(tools=await anyio.to_thread.run_sync(build))

    async def call_tool(ctx: Any, params: Any) -> Any:
        try:
            error, blocks = await run_tool(folder, params.name, params.arguments or {})
        finally:  # what the tool changed, fired on the event bus from a worker thread, VIEW-018
            await anyio.to_thread.run_sync(changes.announce, folder, 'mcp')
        return types.CallToolResult(content=[types.TextContent(type='text', text=block) for block in blocks],
                                    is_error=error)

    server = Server('metaform', version=__version__, instructions=instructions(folder), on_list_tools=list_tools,
                    on_call_tool=call_tool)

    async def main() -> None:
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())
    anyio.run(main)
