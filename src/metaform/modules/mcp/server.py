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
from pathlib import Path
from typing import Any

import anyio

from metaform import settings
from metaform.module import (Context, Module, Stop, Verb, call, context, feedback, instructions, list_reports,
                             on_this_system, read_report, result_json, setting_value, surface, tool_arguments)

PROJECT = {'type': 'string', 'description': "A registered project id; overrides the folder's project for this call."}
LAYERS = {'type': 'array', 'items': {'type': 'string'},
          'description': 'The layers, by name or tag, toggled on for this call only.'}
NOUN_TYPES: dict[str, dict[str, Any]] = {'str': {'type': 'string'}, 'int': {'type': 'integer'},
                                         'bool': {'type': 'boolean'}}
PER_CALL = ('project', 'layers', 'confirm')
TEXT = {'type': 'string'}

Outcome = tuple[bool, list[str]]


def _here(verb: Verb) -> bool:
    return 'mcp' in verb.surfaces and on_this_system(verb)


def setting_schema(setting: settings.Setting, folder: Path) -> dict[str, Any]:
    """A setting's JSON type over MCP, CLI-027."""
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
        properties[noun.name] = {'type': 'array', 'items': kind} if noun.many else kind
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
                  'properties': {'text': TEXT, 'layer': TEXT, 'report': TEXT, 'shape': TEXT, 'project': PROJECT}}),
    'list_reports': ('List the report, feedback and shape files of this project. Always available.',
                     {'type': 'object', 'additionalProperties': False,
                      'properties': {'kind': {'type': 'string', 'enum': ['report', 'feedback', 'shape']},
                                     'layer': TEXT, 'limit': {'type': 'integer'}, 'after': TEXT,
                                     'project': PROJECT}}),
    'read_report': ('Read one report, feedback or shape file exactly. Always available.',
                    {'type': 'object', 'required': ['name'], 'additionalProperties': False,
                     'properties': {'name': TEXT, 'project': PROJECT}}),
}
JSON_TYPES: dict[str, type] = {'string': str, 'integer': int}


def _error(stop: Stop) -> Outcome:
    return True, [f'Error: {stop}\nNext: {stop.next_step}']


def _checked(name: str, arguments: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """A chassis tool's arguments: each one of its declared JSON type, the required ones given."""
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
        if not isinstance(value, wanted) or isinstance(value, bool):
            raise Stop(f'{key} is {"text" if wanted is str else "a whole number"}, not {value!r}.',
                       'metaform help commands')
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
        typed = {key: setting_value(key, value, folder) for key, value in arguments.items()}
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
    try:
        given = _checked(name, arguments, CHASSIS[name][1])
        project = given.pop('project', None)
        if name == 'feedback':
            return False, [result_json(feedback(folder, given.pop('text'), project=project, **given))]
        if name == 'list_reports':
            return False, [result_json(list_reports(folder, project=project, **given))]
        return False, [read_report(folder, given['name'], project=project)]
    except Stop as stop:
        return _error(stop)


def _prepare(folder: Path, module: Module, verb: Verb, name: str, arguments: dict[str, Any],
             lines: list[str]) -> Context:
    project = arguments.get('project')
    layers = arguments.get('layers')
    confirmed = arguments.get('confirm', False)
    if project is not None and not isinstance(project, str):
        raise Stop('project is a registered project id, as text.', 'metaform list projects')
    if layers is not None and (not isinstance(layers, list) or not all(isinstance(item, str) for item in layers)):
        raise Stop('layers is a list of layer names or tags.', 'metaform map layers')
    if not isinstance(confirmed, bool):
        raise Stop('confirm is true or false.', f'If you are sure: call {name} with confirm true')
    if verb.caution and not confirmed:
        raise Stop(verb.caution, f'If you are sure: call {name} with confirm true')
    nouns, switches, notices = tool_arguments(module.id, verb, arguments, ignore=PER_CALL, folder=folder)
    lines.extend(f'Notice: {key}: {message}' for key, message in notices)
    if layers is not None:
        switches['layers'] = list(layers)
    return context(module.id, folder, project=project, nouns=nouns, switches=switches, sink=lines.append,
                   surface='mcp')


async def run_tool(folder: Path, name: str, arguments: dict[str, Any]) -> Outcome:
    if name == 'set':
        return await anyio.to_thread.run_sync(run_set, folder, dict(arguments))
    if name in CHASSIS:
        return await anyio.to_thread.run_sync(run_chassis, folder, name, dict(arguments))
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
        return found

    async def list_tools(ctx: Any, params: Any) -> Any:
        return types.ListToolsResult(tools=await anyio.to_thread.run_sync(build))

    async def call_tool(ctx: Any, params: Any) -> Any:
        error, blocks = await run_tool(folder, params.name, params.arguments or {})
        return types.CallToolResult(content=[types.TextContent(type='text', text=block) for block in blocks],
                                    is_error=error)

    server = Server('metaform', version=__version__, instructions=instructions(folder), on_list_tools=list_tools,
                    on_call_tool=call_tool)

    async def main() -> None:
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())
    anyio.run(main)
