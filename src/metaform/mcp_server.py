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
    """Tool name -> (module, verb, input schema, description)."""
    result = {}
    for module in _surface(folder):
        for verb in module.verbs:
            name = f'{module.id}_{verb.name}'
            if not NAME.fullmatch(name) or '__' in name:
                continue
            properties = {'nouns': {'type': 'array', 'items': {'type': 'string'},
                                    'description': verb.nouns or 'No words are needed.'}}
            for adverb in verb.adverbs:
                key = adverb.name.lstrip('-').replace('-', '_')
                properties[key] = ({'type': 'string', 'description': adverb.help} if adverb.takes_value
                                   else {'type': 'boolean', 'description': adverb.help})
            if verb.caution:
                properties['confirm'] = {'type': 'boolean',
                                         'description': 'Run it. Without this the tool only explains what it would do.'}
            schema = {'type': 'object', 'properties': properties, 'additionalProperties': False}
            description = verb.summary + (f' Caution: {verb.caution}' if verb.caution else '')
            result[name] = (module, verb, schema, description)
    return result


def run_tool(folder: Path, name: str, arguments: dict) -> tuple[bool, str]:
    """Run one tool. Returns (is_error, text)."""
    known = tools(folder)
    if name not in known:
        return True, f'Error: No tool {name} on this surface.\nNext: metaform help commands'
    module, verb, _, _ = known[name]
    arguments = dict(arguments or {})
    nouns = [str(item) for item in arguments.pop('nouns', []) or []]
    confirmed = bool(arguments.pop('confirm', False))
    adverbs = {}
    for adverb in verb.adverbs:
        key = adverb.name.lstrip('-').replace('-', '_')
        if key in arguments and arguments[key] not in (None, False):
            adverbs[adverb.name] = arguments[key]
    lines: list[str] = []
    try:
        if verb.caution and not confirmed:
            raise Stop(verb.caution, f'If you are sure: call {name} with confirm true')
        call(verb.run, Context(module=module.id, folder=folder, nouns=nouns, adverbs=adverbs, sink=lines.append))
        return False, '\n'.join(lines)
    except Stop as stop:
        text = f'Error: {stop}' + (f'\nNext: {stop.next_step}' if stop.next_step else '')
        return True, text


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
