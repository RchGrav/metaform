"""The MCP server with one tool, `project`.

The tool's arguments are one command of the project engine (`metaform.project.commands`), and its result is that
command's answer: `{"map": "<project>"}` reads the base map, `{"<project>.<root>.<steps>": {}}` reads one element,
`{"add": {...}}` writes. The project's name leads every path, so the server keeps nothing between calls: no session,
no current project, nothing told once and remembered. It lists no resources and no prompts, and it sends no
instructions at connect; what an agent needs to use the tool is the tool's description, and `{"help": {}}`.

Every call goes to the home's single-writer service, which holds the databases. This server holds none, so any
number of these may run.
"""
from __future__ import annotations

import json
from typing import Any

import anyio

from metaform.project import commands
from metaform.project.forms import COMMANDS

TOOL = 'project'
DESCRIPTION = (
    "Reads and writes a project's map. The arguments are one command: a single key and its value.\n"
    '{"map": {}} names the projects. {"map": "<project>"} returns a project\'s base map: its element addresses, '
    'wants and overlays.\n'
    '{"<project>.<root>.<steps>": {}} reads one element. The project\'s name leads every path.\n'
    '{"add": {...}}, {"update": {...}} and {"delete": {...}} write; {"orphaned": "<project>"} lists elements nothing '
    'wants.\n'
    '{"help": {}} lists the commands, and {"help": "<command>"} gives a command\'s fields and examples.\n'
    'A refused command comes back with status, code, message and remediation.')
_BODY: dict[str, Any] = {'type': 'object', 'description': 'One path and what is written there.'}
SCHEMA: dict[str, Any] = {
    'type': 'object',
    'description': f"One command: exactly one key, which is one of {', '.join(COMMANDS)}, or a path to read.",
    # Each value's type is stated, so a client sends an object as an object and not as its text.
    'properties': {
        'map': {'anyOf': [{'type': 'string'}, {'type': 'object'}],
                'description': "A project's name, or {} for the names of the projects."},
        'orphaned': {'type': 'string', 'description': "A project's name."},
        'help': {'anyOf': [{'type': 'string'}, {'type': 'object'}],
                 'description': "A command's name, or {} for the names help takes."},
        'add': _BODY, 'update': _BODY, 'delete': _BODY,
    },
    'additionalProperties': {'type': 'object', 'description': 'A path to read: {} or the overlays to include.'},
    'minProperties': 1,
    'maxProperties': 1,
}


def command(arguments: dict[str, Any]) -> dict[str, Any]:
    """The command a client sent. A client that was given no type for a value sends an object as its text; such a
    value is read back as the object. No command takes a text that starts with a brace, so nothing else is changed."""
    out: dict[str, Any] = {}
    for key, value in arguments.items():
        if isinstance(value, str) and value.lstrip().startswith(('{', '[')):
            try:
                value = json.loads(value)
            except ValueError:
                pass
        out[key] = value
    return out


def build() -> Any:
    """The server: one tool, whichever transport carries it."""
    from mcp import types
    from mcp.server import Server

    from metaform.module import chassis_version

    listed = types.ListToolsResult(tools=[types.Tool(name=TOOL, description=DESCRIPTION, input_schema=SCHEMA)])

    async def list_tools(ctx: Any, params: Any) -> Any:
        return listed

    async def call_tool(ctx: Any, params: Any) -> Any:
        if params.name != TOOL:
            answer: dict[str, object] = {'status': 'error', 'code': 'NOT_FOUND', 'remediation': None,
                                         'message': f"'{params.name}' is not a tool of this server; its one tool is "
                                                    f"'{TOOL}'"}
        else:
            given = command(params.arguments or {})
            answer = await anyio.to_thread.run_sync(commands.run, given, None, 'mcp')
        return types.CallToolResult(content=[types.TextContent(type='text', text=json.dumps(answer))],
                                    is_error=answer.get('status') == 'error')

    return Server('metaform', version=chassis_version(), on_list_tools=list_tools, on_call_tool=call_tool)


def http_app() -> Any:
    """The Streamable HTTP app, stateless: each request is answered on its own, as JSON, with no session kept. The
    SDK checks each request's Host and Origin against this machine, so a web page cannot reach it."""
    return build().streamable_http_app(host='127.0.0.1', stateless_http=True, json_response=True)


def serve(port: int) -> None:
    import sys

    import uvicorn

    from .server import serving

    print(f'Metaform project tool at http://127.0.0.1:{port}/mcp', file=sys.stderr, flush=True)
    serving(uvicorn.Config(http_app(), host='127.0.0.1', port=port, log_level='warning')).run()
