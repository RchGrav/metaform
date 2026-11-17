"""The MCP server: the tool `project`, and on a folder's server the memory layer's nine tools.

The tool's arguments are one command of the project engine (`metaform.project.commands`), and its result is that
command's answer: `{"map": "<project>"}` reads the base map, `{"<project>.<root>.<steps>": {}}` reads one element,
`{"add": {...}}` writes. The project's name leads every path, so the server keeps nothing between calls: no session,
no current project, nothing told once and remembered. It lists no resources and no prompts, and it sends no
instructions at connect; what an agent needs to use the tool is the tool's description, and `{"help": {}}`.

A server for one folder also serves its project's memory layer, as the MCP reference memory server serves its graph:
the nine tools with the reference's names, inputs and results (`create_entities` ... `open_nodes`), and the resource
`memory://knowledge-graph`, with an update sent to a client that subscribed after each call that changes the graph.
They take no project, as the reference's take none, so they act on the project the folder belongs to; the server for
no folder has no project and serves neither.

Every call goes to the home's single-writer service, which holds the databases. This server holds none, so any
number of these may run.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, cast

import anyio

from metaform import project as commands
from metaform.project import COMMANDS

TOOL = 'project'
DESCRIPTION = (
    "Reads and writes a project's map. The arguments are one command: a single key and its value.\n"
    '{"map": {}} names the projects. {"map": "<project>"} returns a project\'s base map: its element addresses, '
    'wants and overlays.\n'
    '{"<project>.<root>.<steps>": {}} reads one element. The project\'s name leads every path.\n'
    '{"add": {...}}, {"update": {...}} and {"delete": {...}} write; {"orphaned": "<project>"} lists elements nothing '
    'wants.\n'
    'An element holds lists of records in overlays, each defined beneath <project>.overlay; {"help": "overlay"} '
    'shows how.\n'
    '{"help": {}} lists the commands, and {"help": "<command>"} gives a command\'s fields and examples.\n'
    'A refused command comes back with status, code, message and remediation.')
# Said by `project` on a folder's server, beside which the memory tools are listed.
MEMORY_NOTE = (
    "\nThe memory tools (create_entities, add_observations, create_relations and the rest) keep this folder's project's "
    "memory layer. Any address of its map is an entity there too, such as <project>.code.masher.widget: add "
    'observations to it and relate entities to it. A memory tied to an object the map no longer holds is hidden.')
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


def listed(memory: bool = False) -> Any:
    """The tool as it is listed. It writes and can delete, an add grows a list so a repeat is not the same call, and
    it reaches nothing outside this machine. With `memory`, beside the memory tools, it says how they take the map."""
    from mcp import types
    return types.Tool(name=TOOL, description=DESCRIPTION + (MEMORY_NOTE if memory else ''), input_schema=SCHEMA,
                      annotations=types.ToolAnnotations(read_only_hint=False, destructive_hint=True,
                                                        idempotent_hint=False, open_world_hint=False))


def memory_listed() -> list[Any]:
    """The memory layer's nine tools, listed exactly as the reference lists them."""
    from mcp import types
    return [types.Tool(name=str(tool['name']), title=str(tool['title']), description=str(tool['description']),
                       input_schema=cast(dict[str, Any], tool['inputSchema']),
                       output_schema=cast(dict[str, Any], tool['outputSchema']),
                       annotations=_hints(cast(dict[str, bool], tool['annotations'])))
            for tool in commands.memory_tools()]


def _hints(given: dict[str, bool]) -> Any:
    from mcp import types
    return types.ToolAnnotations(read_only_hint=given['readOnlyHint'], destructive_hint=given['destructiveHint'],
                                 idempotent_hint=given['idempotentHint'], open_world_hint=given['openWorldHint'])


def folder_project(folder: Path) -> str | None:
    """The name in the project store of the project this folder belongs to, or None for a folder of no project."""
    from metaform import home
    found = home.folder_project(folder)
    return commands.stored_name(found) if found else None


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


def build(folder: Path | None = None) -> Any:
    """The server: one tool, whichever transport carries it. With `folder`, the server an AI tool or a runner starts
    for one agent working there: it also sends that agent its opening at connect, one line and the links to its
    rules and its task, and serves those links (`opening`). Without, it sends and serves nothing but the tool."""
    from mcp import types
    from mcp.server import Server

    from metaform.module import chassis_version

    tools = types.ListToolsResult(tools=[listed(folder is not None), *(memory_listed() if folder is not None else [])])
    memory_names = {tool.name for tool in tools.tools} - {TOOL}
    caller = os.environ.get('METAFORM_SESSION') or 'mcp'
    subscribed: set[str] = set()  # the resources a 2025-era client subscribed to with resources/subscribe

    from mcp.server.subscriptions import InMemorySubscriptionBus, ListenHandler
    from mcp.shared.subscriptions import ResourceUpdated
    bus = InMemorySubscriptionBus()  # a 2026-07-28 client's subscriptions/listen streams

    async def list_tools(ctx: Any, params: Any) -> Any:
        return tools

    async def remember(ctx: Any, params: Any) -> Any:
        """Call a memory tool on the folder's project, and tell a subscribed client the graph changed."""
        project = folder_project(folder) if folder is not None else None
        if project is None:
            return types.CallToolResult(content=[types.TextContent(type='text', text=(
                f'{folder} belongs to no project of Metaform, so it has no memory layer'))], is_error=True)
        given = cast(dict[str, Any], params.arguments or {})
        answer = await anyio.to_thread.run_sync(commands.memory, project, params.name, given, None, caller)
        if answer.get('status') != 'ok':
            return types.CallToolResult(content=[types.TextContent(type='text', text=str(answer.get('message')))],
                                        is_error=True)
        texts, structured = commands.memory_answer(params.name, given, answer['result'])
        if params.name in commands.memory_tools_changing():
            await bus.publish(ResourceUpdated(uri=commands.MEMORY_URI))
            if commands.MEMORY_URI in subscribed:
                try:
                    await ctx.session.send_resource_updated(commands.MEMORY_URI)
                except Exception:  # noqa: BLE001, S110  the result never waits on, or fails by, the notification
                    pass
        return types.CallToolResult(content=[types.TextContent(type='text', text=text) for text in texts],
                                    structured_content=structured)

    async def call_tool(ctx: Any, params: Any) -> Any:
        if params.name in memory_names:
            return await remember(ctx, params)
        if params.name != TOOL:
            answer: dict[str, object] = {'status': 'error', 'code': 'NOT_FOUND', 'remediation': None,
                                         'message': f"'{params.name}' is not a tool of this server; its one tool is "
                                                    f"'{TOOL}'"}
        else:
            given = command(params.arguments or {})
            answer = await anyio.to_thread.run_sync(commands.run, given, None, os.environ.get('METAFORM_SESSION') or 'mcp')
        return types.CallToolResult(content=[types.TextContent(type='text', text=json.dumps(answer))],
                                    is_error=answer.get('status') == 'error')

    if folder is None:
        return Server('metaform', version=chassis_version(), on_list_tools=list_tools, on_call_tool=call_tool)

    from mcp.shared.exceptions import MCPError

    from . import opening

    graph = types.Resource(uri=commands.MEMORY_URI, name='knowledge-graph', title='Knowledge Graph',
                           description='The full knowledge graph with all entities and relations',
                           mime_type='application/json')

    async def list_resources(ctx: Any, params: Any) -> Any:
        found = await anyio.to_thread.run_sync(opening.listed, folder)
        return types.ListResourcesResult(resources=[
            *(types.Resource(uri=uri, name=name, description=description, mime_type='text/plain')
              for uri, name, description in found), graph])

    async def read_resource(ctx: Any, params: Any) -> Any:
        uri = str(params.uri)
        if uri == commands.MEMORY_URI:
            project = folder_project(folder)
            whole: dict[str, Any] = {}
            answer = (await anyio.to_thread.run_sync(commands.memory, project, 'read_graph', whole, None, caller)
                      if project is not None else {'status': 'error', 'message': f'{folder} belongs to no project'})
            if answer.get('status') != 'ok':
                raise MCPError(-32002, str(answer.get('message')))
            return types.ReadResourceResult(contents=[types.TextResourceContents(
                uri=uri, text=json.dumps(answer['result'], indent=2, ensure_ascii=False),
                mime_type='application/json')])
        said = await anyio.to_thread.run_sync(opening.block_text, folder, uri)
        if said is None:
            raise MCPError(-32002, f'No resource {uri} here.\nNext: list the resources')
        return types.ReadResourceResult(contents=[types.TextResourceContents(uri=uri, text=said,
                                                                             mime_type='text/plain')])

    # A host may ask for prompts and resource templates whatever a server offers: it is answered that there are none.
    async def no_templates(ctx: Any, params: Any) -> Any:
        return types.ListResourceTemplatesResult(resource_templates=[])

    async def no_prompts(ctx: Any, params: Any) -> Any:
        return types.ListPromptsResult(prompts=[])

    async def subscribe(ctx: Any, params: Any) -> Any:
        subscribed.add(str(params.uri))
        return types.EmptyResult()

    async def unsubscribe(ctx: Any, params: Any) -> Any:
        subscribed.discard(str(params.uri))
        return types.EmptyResult()

    return Server('metaform', version=chassis_version(), instructions=opening.connect_instructions(folder),
                  on_list_tools=list_tools, on_call_tool=call_tool, on_list_resources=list_resources,
                  on_read_resource=read_resource, on_list_resource_templates=no_templates,
                  on_list_prompts=no_prompts, on_subscribe_resource=subscribe, on_unsubscribe_resource=unsubscribe,
                  on_subscriptions_listen=ListenHandler(bus))


def http_app(folder: Path | None = None, *, bind: str = '127.0.0.1', exposed: Any = None, verifier: Any = None) -> Any:
    """The Streamable HTTP app, stateless: each request is answered on its own, as JSON, with no session kept. For a
    local server the SDK checks each request's Host and Origin against this machine, so a web page cannot reach it.
    For one reached from outside (`exposed`), as the cloud module's tunnel and the node service serve it, every
    request's bearer is checked against its resource, with `verifier` (introspection at the Node's authorization
    server by default, the broker's signed assertions through the tunnel), and a call to the tool needs the scope to
    write."""
    server = build(folder)
    if exposed is None:
        return server.streamable_http_app(host='127.0.0.1', stateless_http=True, json_response=True)
    from . import oauth
    app = server.streamable_http_app(host=bind, stateless_http=True, json_response=True,
                                     transport_security=oauth.transport_security(exposed),
                                     auth=oauth.auth_settings(exposed),
                                     token_verifier=verifier or oauth.Introspection(exposed, exposed.mcp))
    oauth.protect(app, exposed, lambda name: oauth.required_scope(name, 'write', False),
                  getattr(verifier, 'allowed', None))
    return app


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


def serve(port: int) -> None:
    """Serve the tool alone on this machine, `metaform mcp project`."""
    import sys

    import uvicorn

    print(f'Metaform project tool at http://127.0.0.1:{port}/mcp', file=sys.stderr, flush=True)
    serving(uvicorn.Config(http_app(), host='127.0.0.1', port=port, log_level='warning')).run()


def serve_http(folder: Path, *, port: int, bind: str, public_url: str, introspection: str | None = None) -> None:
    """Serve `folder` over Streamable HTTP, `metaform mcp serve --http`: one server any number of clients connect
    to, with the opening of the person's own session. Beyond this machine only with the Node's authorization server
    checking every caller. A2A is served on the same port while `mcp_a2a` is on."""
    import sys

    import uvicorn

    from metaform import settings

    from . import oauth
    exposed = oauth.exposure(public_url, bind, introspection or oauth.DEFAULT_INTROSPECTION)
    app = http_app(folder, bind=bind, exposed=exposed)
    where = exposed.mcp if exposed is not None else f'http://127.0.0.1:{port}/mcp'
    print(f'Metaform MCP server for {folder} at {where}', file=sys.stderr, flush=True)
    if settings.value('mcp_a2a', folder):
        from .a2a import attach
        from .a2a_out import attach as follow_exchanges
        print(attach(app, folder, port, exposed), file=sys.stderr, flush=True)
        follow_exchanges(app, folder)  # what agents here sent to peers, followed to its end
    serving(uvicorn.Config(app, host=bind, port=port, log_level='warning')).run()


def serve_stdio(folder: Path) -> None:
    """Serve one agent working in `folder` over stdio, the connection its AI tool or its runner holds: the tool, and
    the agent's opening. The server ends when the host closes its input."""
    from mcp.server.stdio import stdio_server

    server = build(folder)

    async def main() -> None:
        async with stdio_server() as (read, write):
            try:
                await server.run(read, write, server.create_initialization_options())
            finally:
                await write.aclose()
    anyio.run(main)
