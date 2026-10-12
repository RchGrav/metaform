"""mcp: serves Metaform's tools to AI tools over MCP, MCP-001.

`metaform mcp serve` starts the server over stdio, and `metaform mcp serve
--http` over Streamable HTTP on 127.0.0.1, MCP-002, with A2A beside it on the
same port, `a2a.py`, while `mcp_a2a` is on. It is declared for the CLI
only, so it is never itself a tool. Every tool comes from a module verb on the
folder's command surface, `<module>_<verb>`, or is one of the chassis's own
commands, `metaform_<command>`, MCP-003; the server gets no private access to
the chassis.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from metaform import settings
from metaform.data import Tables
from metaform.module import Context, Module, Subscription, Verb

from . import a2a_records, task_records

# The module's tables: A2A's, versions 1 and 2 (a2a_records.py), and the tasks extension's tool calls, version 3,
# which only adds a table, so every earlier version still reads the rest.
TABLES = Tables(version=3, tables=(*a2a_records.TABLES.tables, task_records.TABLE), compatible_from=1)

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ('mcp>=2.2,<3', 'a2a-sdk[http-server]>=1.2.2,<2')
SHIPS_DISABLED = False
REMOTE_AGENT = False  # a hosted agent reaches Metaform through the CLI, and mcp's compiled dependencies do not travel

settings.boolean('mcp_http', False, switches=('--http', '--no-http'), label='Serve over HTTP',
                 help='Serve this run over Streamable HTTP on 127.0.0.1 instead of stdio.',
                 details='Given on the command line, metaform mcp serve --http, for the one run. Stored, every metaform '
                         'mcp serve in its scope serves HTTP, the servers AI tools and dispatch start over stdio '
                         'included, so it is meant for the command line; mcp_transport is what tells metaform install '
                         'to register the HTTP server.')
settings.number('mcp_port', 7434, min=1, max=65535, scope='global', switches=('--mcp-port', '--port'),
                label='MCP HTTP port', help='The port the HTTP MCP server listens on at 127.0.0.1.',
                details='Read by metaform mcp serve --http, and by metaform install when mcp_transport is http, '
                        'which registers http://127.0.0.1:<port>/mcp.')
# A server reached beyond this machine, the Metaform Node, oauth.py: who may reach it is the person's to decide, so
# these are person_only; any bind but loopback, or a public URL, starts only with the Node's authorization server.
settings.text('mcp_bind', '127.0.0.1', scope='global', person_only=True, label='MCP HTTP bind address',
              help='The address metaform mcp serve --http listens on; anything but loopback needs mcp_public_url and '
                   'the Node\'s authorization server.',
              details='Loopback serves this machine only, as before. Any other address is refused unless the server is '
                      'a Metaform Node with its authorization server running, so nothing is served anonymously.')
settings.text('mcp_public_url', '', scope='global', person_only=True, label='MCP public URL',
              help='The https origin the server is reached at from outside, such as https://metaform.example.com; '
                   'empty serves this machine only.',
              details='Set, every request to <it>/mcp needs a token the Node\'s authorization server issued for '
                      'exactly that resource, and A2A one for <it>/a2a; the Agent Card names these URLs. Written by '
                      'metaform node init into the Node\'s compose file.')
settings.text('mcp_introspection', 'http://127.0.0.1:7435/oauth/introspect', scope='global', person_only=True,
              label='Token introspection endpoint',
              help='Where an exposed server checks tokens (RFC 7662), the Node\'s authorization server on loopback.')
settings.choice('mcp_transport', ['stdio', 'http'], 'stdio', scope='global', label='AI tool transport',
                help='How metaform install registers the server: stdio, each AI tool starting its own, or http, the '
                     'one server you start with metaform mcp serve --http.',
                details='stdio is the default: a host starts metaform mcp serve in the folder it opens, so each '
                        'folder is served as itself. http registers http://127.0.0.1:<mcp_port>/mcp, which serves '
                        'the folder metaform mcp serve --http was started in, for every AI tool that connects.')
settings.choice('mcp_consent', ['ask', 'confirm'], 'ask', person_only=True, label='Consent over MCP',
                help='How a call that needs your say is confirmed: ask shows you a form in your AI tool where it can '
                     'show one; confirm takes the agent\'s confirm=true.',
                details='Covers a tool with a caution, such as metaform_clear_project, and an agent asking to change a '
                        'setting only you set. With ask, an AI tool that shows forms (MCP elicitation) asks you '
                        'directly and the agent cannot answer for you; a tool that cannot, and every dispatched agent, '
                        'falls back to confirm=true for a caution and a refusal for your settings. With confirm, the '
                        'agent passes confirm=true after asking you itself, as before.')
settings.boolean('mcp_apps', True, label='Map views in AI tools',
                 help='Offer the map, node, agent trace and glossary views to AI tools that show MCP Apps, such as '
                      'Claude Desktop.',
                 details='map_where and map_roots then open the map focused on their address, map_item and map_node '
                         'the node with its numbered items, dispatch_sessions and dispatch_start the ticket\'s agent '
                         'trace, followed while it works, and metaform_instructions and map_glossary the glossary, inside the '
                         'conversation. Selecting a node there tells the agent which Address you are looking at, and '
                         'an Address the agent names in a call turns the open views to it. AI tools without MCP Apps, '
                         'such as Claude Code, get the text as before.')
settings.choice('mcp_apps_offer', ['declared', 'always'], 'declared', label='Offer views to',
                help='declared offers the views only to AI tools that say they show MCP Apps; always offers them to '
                     'every AI tool.',
                details='MCP Apps asks an AI tool to declare the io.modelcontextprotocol/ui extension, and a server to '
                        'check for it. Some tools show the views without declaring it, such as the specification\'s own '
                        'test host, basic-host. With always, each view-opening tool carries its view and the views\' '
                        'own tool metaform_view is listed to every AI tool; one that does not show MCP Apps may list '
                        'metaform_view to its agent, which only reads.')
settings.boolean('mcp_tasks', True, label='Tasks for long tools',
                 help='Answer a long tool, such as workflow_assign or hello_wait, with a task an AI tool polls, when '
                      'it declares the MCP tasks extension.',
                 details='hello_wait is answered at once and runs on in the server; workflow_assign is answered with '
                         'the run it hands to a fresh agent, which the task follows until that agent closes it, and a '
                         'run paused on you asks its question in your AI tool. tasks/get gives the result and '
                         'tasks/cancel stops the work. A task is kept in the project for a day. AI tools that do not '
                         'declare the extension get the result as before.')
settings.choice('mcp_recovery', ['relay', 'manual'], 'relay', label='Schema upgrade recovery',
                help='On a newer store, relay this connection to changed code on disk, or require a manual restart.',
                details='Relay preserves the host connection and retries calls refused before dispatch. '
                        'Manual returns the schema error. Unchanged package code never starts a replacement.')
# A2A, P004 and P005: other agents send work to Metaform as tickets. Who may reach it and where it may call out to are
# the person's to decide, CLI-011, so both are person_only; how long a send waits only paces the caller, so it is not.
settings.boolean('mcp_a2a', True, scope='global', person_only=True, label='Serve A2A',
                 help='Serve A2A beside MCP on metaform mcp serve --http, so other agents can send this home tickets.',
                 details='The public Agent Card is at http://127.0.0.1:<mcp_port>/.well-known/agent-card.json and names '
                         'no project. Every other A2A request needs the bearer token in <home>/run/a2a-token, made on '
                         'the first start and separate from every other token. A message becomes a ticket at the '
                         'Address its contextId names, in To do; it starts only when dispatch_autostart is on. Off, '
                         'the HTTP server serves MCP alone.')
settings.items('mcp_a2a_webhooks', (), scope='global', person_only=True, label='A2A push webhooks',
               help='The webhook URLs A2A push notifications may be sent to, each a URL prefix such as '
                    'https://agent.example/hooks/; none turns push notifications off.',
               details='A2A clients ask to be told of a task\'s changes at a URL of theirs. Metaform calls only a URL '
                       'with the scheme, host and port of one of these and a path under its path, so a client cannot '
                       'make it call anywhere else on your network, the A2A specification\'s guard against '
                       'server-side request forgery. The Agent Card offers push notifications only while the list '
                       'holds one.')
settings.number('mcp_a2a_wait', 30, min=0, max=3600, scope='global', label='A2A send wait',
                help='How many seconds an A2A send that asks to wait is held for its ticket to finish, before it '
                     'answers with the task as it stands.',
                details='A2A asks a send without returnImmediately to wait until the task ends or needs input. A '
                        'ticket can take hours, so the wait ends here and the caller follows the task with GetTask, '
                        'SubscribeToTask or a push notification; the Agent Card says so. 0 answers at once. A ticket '
                        'nothing will start, with dispatch_autostart off, is answered at once, as is a message that '
                        'named no Address, which is asked for one.')


def changed(payload: dict[str, Any], ctx: Context) -> None:
    """A change made in this process, BASE-032: the A2A server here, when one runs, reads the tasks it follows in that
    project again; changes from other processes reach it through `events.listen`, BASE-053."""
    served = sys.modules.get(f'{__name__}.a2a')
    if served is not None:
        served.heard(payload)


def serve(ctx: Context) -> None:
    from .server import serve as run_server
    run_server(Path(ctx.folder), http=bool(ctx.setting('mcp_http')), port=int(ctx.setting('mcp_port')),
               bind=str(ctx.setting('mcp_bind') or '127.0.0.1'), public_url=str(ctx.setting('mcp_public_url') or ''),
               introspection=str(ctx.setting('mcp_introspection') or ''))


MODULE = Module(
    id='mcp',
    summary="Serve Metaform's tools to AI tools over MCP.",
    purpose="Serves Metaform's tools to AI tools over MCP. Every tool is also a metaform command on the CLI. "
            'Details: metaform help mcp.',
    details='A host starts it with uvx --from <source> metaform mcp serve. It serves the folder it starts in, '
            "whatever that folder's command surface; the surface narrows the tools it serves. With --http it serves "
            'Streamable HTTP at http://127.0.0.1:<mcp_port>/mcp until stopped.',
    verbs=(Verb('serve', serve, 'Serve the MCP server over stdio, or with --http over Streamable HTTP.',
                switches=('mcp_http', 'mcp_port', 'mcp_bind', 'mcp_public_url', 'mcp_introspection'),
                surfaces=('cli',), transport=True),),
    mcp_server='serve',
    tables=TABLES,
    subscriptions=(Subscription('map.changed', changed),),
)
