"""The MCP server, MCP-002: the official SDK's low-level Server over stdio.

Tools are computed on every request from the live module declarations and the
folder's command surface, MCP-003 and MCP-004. Each call gets its own Context,
BASE-028: a coroutine verb is awaited in the server's loop, so the host's
cancellation reaches it; a plain function runs in a worker thread. The result
is one text block of `say` lines, when there are any, and one block holding
the result, BASE-036.
"""
from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import anyio

from metaform import settings
from metaform.module import Module, Stop, Verb, call, context, instructions, result_json, surface

PROJECT = {'type': 'string', 'description': "A registered project id; overrides the folder's project for this call."}
LAYERS = {'type': 'array', 'items': {'type': 'string'},
          'description': 'The layers, by name or tag, toggled on for this call only.'}
NOUN_TYPES = {'str': {'type': 'string'}, 'int': {'type': 'integer'}, 'bool': {'type': 'boolean'}}


def _here(verb: Verb) -> bool:
    import platform
    system = platform.system().lower()
    system = 'macos' if system == 'darwin' else system
    return 'mcp' in verb.surfaces and (verb.supported_os is None or system in verb.supported_os)


def setting_schema(setting: Any, folder: Path) -> dict[str, Any]:
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
        except Exception:  # A module's choices that fail give a plain string.
            choices = []
        return {'type': 'string', 'enum': choices} if choices else {'type': 'string'}
    return {'type': 'string'}


def verb_schema(verb: Verb, folder: Path) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required = []
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


def _error(stop: Stop) -> tuple[bool, list[str]]:
    return True, [f'Error: {stop}\nNext: {stop.next_step}']


def run_set(folder: Path, arguments: dict[str, Any]) -> tuple[bool, list[str]]:
    """The `set` tool stores settings for the server's folder, as `metaform set` would, PROJ-005 and CLI-033."""
    glue = bool(arguments.pop('glue', False))
    changes = []
    try:
        for key, value in arguments.items():
            setting = settings.SCHEMA.get(key)
            if setting is None:
                raise Stop(f'{key} is not a setting.', 'metaform help switches')
            try:
                old, new = settings.put(key, value, folder, glue=glue)
            except settings.SettingError as error:
                raise Stop(str(error), error.next_step or f'metaform help {setting.switch}') from None
            changes.append({'key': key, 'old': old, 'new': new})
    except Stop as stop:
        return _error(stop)
    return False, [result_json({'updated': changes, 'glued': glue})]


def _prepare(folder: Path, module: Module, verb: Verb, name: str, arguments: dict[str, Any],
             lines: list[str]) -> Any:
    arguments = dict(arguments)
    project = arguments.pop('project', None)
    layers = arguments.pop('layers', None)
    confirmed = bool(arguments.pop('confirm', False))
    if verb.caution and not confirmed:
        raise Stop(verb.caution, f'If you are sure: call {name} with confirm true')
    nouns = {noun.name: arguments[noun.name] for noun in verb.nouns if noun.name in arguments}
    switches = {key: arguments[key] for key in verb.switches if key in arguments}
    if layers is not None:
        switches['layers'] = list(layers)
    return context(module.id, folder, project=project, nouns=nouns, switches=switches, sink=lines.append,
                   surface='mcp')


async def run_tool(folder: Path, name: str, arguments: dict[str, Any]) -> tuple[bool, list[str]]:
    if name == 'set':
        return await anyio.to_thread.run_sync(run_set, folder, dict(arguments))
    known = await anyio.to_thread.run_sync(tools, folder)
    if name not in known:
        return True, [f'Error: No tool {name} on this surface.\nNext: metaform help commands']
    module, verb = known[name]
    lines: list[str] = []
    try:
        ctx = await anyio.to_thread.run_sync(_prepare, folder, module, verb, name, arguments, lines)
        if inspect.iscoroutinefunction(verb.run):
            result = await verb.run(ctx)
        else:
            result = await anyio.to_thread.run_sync(call, verb.run, ctx)
    except Stop as stop:
        return _error(stop)
    except Exception as error:  # Unexpected: the error and one next step, MCP-006.
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

    async def list_tools(ctx: Any, params: Any) -> Any:
        def build() -> list[Any]:
            found = [types.Tool(name=name, description=verb.summary + (f' Caution: {verb.caution}' if verb.caution
                                                                        else ''),
                                input_schema=verb_schema(verb, folder))
                     for name, (_, verb) in tools(folder).items()]
            found.append(types.Tool(name='set', description="Save settings for the server's folder, as metaform set "
                                                            'does.', input_schema=set_schema(folder)))
            return found
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
