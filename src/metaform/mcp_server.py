"""metaform mcp: the MCP server a harness launches.

Every module verb on this folder's command surface is a tool named
<module>_<verb>, built from the same declaration as the CLI command. The
instructions are a short base text plus each module's purpose.
"""
from __future__ import annotations

import re
from pathlib import Path

import anyio

from . import __version__, loader, settings
from .module import Context, Stop, call

BASE = ('Metaform keeps this project\'s functional map: what each part is for, who receives what it does, '
        'and how. Read the map before you change code, so you work from the purpose of the part. '
        'Each tool below comes from a module; the sections that follow say what each module is for. '
        'Tools named <module>_<verb> take the words the CLI takes after the verb as "nouns", and each '
        'switch as a named argument. A tool error ends with the one next step to take.')

NAME = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')


def _surface(folder: Path):
    groups = settings.value('commands', folder)
    return [module for module in loader.enabled() if not groups or module.id in groups]


def instructions(folder: Path) -> str:
    sections = [BASE]
    for module in _surface(folder):
        sections.append(f'## {module.id}\n{module.purpose}')
    return '\n\n'.join(sections)


def tools(folder: Path) -> dict:
    """Tool name -> (module, verb, input schema, description). Replaced by the mcp module, MCP-001."""
    from .module_metadata import current_os
    result = {}
    for module in _surface(folder):
        for verb in module.verbs:
            if 'mcp' not in verb.surfaces or (verb.supported_os and current_os() not in verb.supported_os):
                continue
            name = f'{module.id}_{verb.name}'
            properties: dict = {}
            required = []
            for noun in verb.nouns:
                kind = {'str': {'type': 'string'}, 'int': {'type': 'integer'}, 'bool': {'type': 'boolean'},
                        'json': noun.schema or {}}[noun.kind]
                properties[noun.name] = {'type': 'array', 'items': kind} if noun.many else dict(kind)
                if noun.required:
                    required.append(noun.name)
            for key in verb.switches:
                setting = settings.SCHEMA.get(key)
                if setting is not None:
                    properties[key] = {'type': {'bool': 'boolean', 'int': 'integer'}.get(setting.kind, 'string')}
            if verb.caution:
                properties['confirm'] = {'type': 'boolean'}
            schema = {'type': 'object', 'properties': properties, 'required': required, 'additionalProperties': False}
            description = verb.summary + (f' Caution: {verb.caution}' if verb.caution else '')
            result[name] = (module, verb, schema, description)
    return result


def run_tool(folder: Path, name: str, arguments: dict) -> tuple[bool, str]:
    """Run one tool. Returns (is_error, text)."""
    from . import context, results
    known = tools(folder)
    if name not in known:
        return True, f'Error: No tool {name} on this surface.\nNext: metaform help commands'
    module, verb, _, _ = known[name]
    arguments = dict(arguments or {})
    confirmed = bool(arguments.pop('confirm', False))
    nouns = {noun.name: arguments[noun.name] for noun in verb.nouns if noun.name in arguments}
    switches = {key: arguments[key] for key in verb.switches if key in arguments}
    lines: list[str] = []
    try:
        if verb.caution and not confirmed:
            raise Stop(verb.caution, f'If you are sure: call {name} with confirm true')
        ctx = context.build(module.id, folder, nouns=nouns, switches=switches, sink=lines.append, surface='mcp')
        result = call(verb.run, ctx)
        text = '\n'.join(lines)
        if result is not None:
            text += ('\n' if text else '') + (result if isinstance(result, str) else results.as_json(result))
        return False, text
    except Stop as stop:
        return True, f'Error: {stop}\nNext: {stop.next_step}'


def serve(folder: Path) -> None:
    from mcp import types
    from mcp.server import Server
    from mcp.server.stdio import stdio_server

    async def list_tools(context, params):
        return types.ListToolsResult(tools=[
            types.Tool(name=name, description=description, input_schema=schema)
            for name, (_, _, schema, description) in tools(folder).items()])

    async def call_tool(context, params):
        error, text = await anyio.to_thread.run_sync(run_tool, folder, params.name, params.arguments or {})
        return types.CallToolResult(content=[types.TextContent(type='text', text=text)], is_error=error)

    server = Server('metaform', version=__version__, instructions=instructions(folder),
                    on_list_tools=list_tools, on_call_tool=call_tool)

    async def main():
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())
    anyio.run(main)
