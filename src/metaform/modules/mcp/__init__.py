"""mcp: serves Metaform's tools to AI tools over MCP, MCP-001.

`metaform mcp serve` starts the server over stdio, and `metaform mcp serve
--http` over Streamable HTTP on 127.0.0.1, MCP-002, with A2A beside it on the
same port, `a2a.py`, while `mcp_a2a` is on. It is declared for the CLI
only, so it is never itself a tool. Every tool comes from a module verb on the
folder's command surface, `<module>_<verb>`, or is one of the chassis's own
commands, `metaform_<command>`, MCP-003; the server gets no private access to
the chassis. `mcp a2a_send`, `a2a_exchanges` and `a2a_cancel` are its own tools: an agent here sends an A2A peer
the person names work about an Address and follows it there, `a2a_out.py`, MCP-040 to MCP-043.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from metaform import settings
from metaform.data import Tables
from metaform.module import Context, Module, Noun, Provides, Subscription, Verb, project_for

from . import a2a_records, task_records

# The module's tables: A2A's, versions 1 and 2 (a2a_records.py), the tasks extension's tool calls, version 3, A2A
# outbound's peers and exchanges, version 4, MCP-043, an exchange's open question, version 5, MCP-041, and the claim on
# sending its answer, version 6; each only adds a table or a column that may be empty, so every earlier version still
# reads the rest.
TABLES = Tables(version=6,tables=(*a2a_records.TABLES.tables, task_records.TABLE), compatible_from=1)

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ('mcp>=2.2,<3', 'a2a-sdk[http-server]>=1.2.2,<2')
SHIPS_DISABLED = False
REMOTE_AGENT = False  # a hosted agent reaches Metaform through the CLI, and mcp's compiled dependencies do not travel

settings.boolean('mcp_http', False, switches=('--http', '--no-http'), label='Serve over HTTP', per_call=True,
                 help='Serve this run over Streamable HTTP on 127.0.0.1 instead of stdio.',
                 details='Given on the command line, metaform mcp serve --http, for the one run, and never stored: '
                         'stored, every metaform mcp serve in its scope would serve HTTP, the servers AI tools and '
                         'dispatch start over stdio included. mcp_transport is what tells metaform install to register '
                         'the HTTP server.')
settings.number('mcp_port', 7434, min=1, max=65535, scope='global', switches=('--mcp-port', '--port'),
                label='MCP HTTP port', help='The port the HTTP MCP server listens on at 127.0.0.1.',
                details='Read by metaform mcp serve --http, and by metaform install when mcp_transport is http, '
                        'which registers http://127.0.0.1:<port>/mcp.')
# A server reached beyond this machine, the Metaform Node, oauth.py: any bind but loopback, or a public URL, starts
# only with the Node's authorization server.
settings.text('mcp_bind', '127.0.0.1', scope='global', label='MCP HTTP bind address',
              help='The address metaform mcp serve --http listens on; anything but loopback needs mcp_public_url and '
                   'the Node\'s authorization server.',
              details='Loopback serves this machine only, as before. Any other address is refused unless the server is '
                      'a Metaform Node with its authorization server running, so nothing is served anonymously.')
settings.text('mcp_public_url', '', scope='global', label='MCP public URL',
              help='The https origin the server is reached at from outside, such as https://metaform.example.com; '
                   'empty serves this machine only.',
              details='Set, every request to <it>/mcp needs a token the Node\'s authorization server issued for '
                      'exactly that resource, and A2A one for <it>/a2a; the Agent Card names these URLs. Written by '
                      'metaform node init into the Node\'s compose file.')
settings.choice('mcp_transport', ['stdio', 'http'], 'stdio', scope='global', label='AI tool transport',
                help='How metaform install registers the server: stdio, each AI tool starting its own, or http, the '
                     'one server you start with metaform mcp serve --http.',
                details='stdio is the default: a host starts metaform mcp serve in the folder it opens, so each '
                        'folder is served as itself. http registers http://127.0.0.1:<mcp_port>/mcp, which serves '
                        'the folder metaform mcp serve --http was started in, for every AI tool that connects.')
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
settings.choice('mcp_search_fetch', ['remote', 'always', 'never'], 'remote', label='search and fetch tools',
                help='Offer the two tools ChatGPT calls by name, search and fetch: remote offers them over HTTP and the '
                     'cloud tunnel, always everywhere, never nowhere.',
                details='ChatGPT\'s connectors and deep research call tools named exactly search and fetch. Both only '
                        'read: search finds layer items, memories and terms and returns metaform:// ids, fetch reads '
                        'one. Over stdio a local agent has the real tools (map_search, memory_search_nodes), so remote '
                        'leaves the two generic ones out there.')
settings.choice('mcp_recovery', ['relay', 'manual'], 'relay', label='Schema upgrade recovery',
                help='On a newer store or changed code on disk, relay this connection to the code on disk, or '
                     'require a manual restart.',
                details='Relay preserves the host connection and retries calls refused before dispatch, and serves a '
                        'tool call made after the package code on disk changed from that code. Manual returns the '
                        'schema error and serves the code it started with. Unchanged package code never starts a '
                        'replacement.')
# A2A, P004 and P005: other agents send work to Metaform as tickets.
settings.boolean('mcp_a2a', True, scope='global', label='Serve A2A',
                 help='Serve A2A beside MCP on metaform mcp serve --http, so other agents can send this home tickets.',
                 details='The public Agent Card is at http://127.0.0.1:<mcp_port>/.well-known/agent-card.json and names '
                         'no project. Every other A2A request needs the bearer token in <home>/run/a2a-token, made on '
                         'the first start and separate from every other token. A message becomes a ticket at the '
                         'Address its contextId names, in To do for an agent to select. Off, '
                         'the HTTP server serves MCP alone.',
                 category='integrations', heading='A2A')
settings.items('mcp_a2a_webhooks', (), scope='global', label='A2A push webhooks',
               help='The webhook URLs A2A push notifications may be sent to, each a URL prefix such as '
                    'https://agent.example/hooks/; none turns push notifications off.',
               details='A2A clients ask to be told of a task\'s changes at a URL of theirs. Metaform calls only a URL '
                       'with the scheme, host and port of one of these and a path under its path, so a client cannot '
                       'make it call anywhere else on your network, the A2A specification\'s guard against '
                       'server-side request forgery. The Agent Card offers push notifications only while the list '
                       'holds one.',
               category='integrations', heading='A2A')
settings.number('mcp_a2a_wait', 30, min=0, max=3600, scope='global', label='A2A send wait',
                help='How many seconds an A2A send that asks to wait is held for its ticket to finish, before it '
                     'answers with the task as it stands.',
                details='A2A asks a send without returnImmediately to wait until the task ends or needs input. A '
                        'ticket can take hours, so the wait ends here and the caller follows the task with GetTask, '
                        'SubscribeToTask or a push notification; the Agent Card says so. 0 answers at once. A ticket '
                        'named no Address is answered at once and asked for one.',
                category='integrations', heading='A2A')



def changed(payload: dict[str, Any], ctx: Context) -> None:
    """A change made in this process, BASE-032: the A2A server here, when one runs, reads the tasks it follows in that
    project again; changes from other processes reach it through `events.listen`, BASE-053. An answer given to a
    question an A2A peer asked goes back from the server's follower, which that wake reads it on, or from a listing,
    MCP-041; never from here, so a change to the map never waits on a peer. A trace view's next read reads the store
    when the change concerns its ticket."""
    served = sys.modules.get(f'{__name__}.a2a')
    if served is not None:
        served.heard(payload)
    shown = sys.modules.get(f'{__name__}.views')  # the trace views' held reads, views.Traces
    if shown is not None:
        shown.heard(payload)


def serve(ctx: Context) -> None:
    from .server import serve as run_server
    run_server(Path(ctx.folder), http=bool(ctx.setting('mcp_http')), port=int(ctx.setting('mcp_port')),
               bind=str(ctx.setting('mcp_bind') or '127.0.0.1'), public_url=str(ctx.setting('mcp_public_url') or ''))


def a2a_send(ctx: Context) -> Any:
    from .a2a_out import send
    return send(ctx)


def a2a_exchanges(ctx: Context) -> Any:
    from .a2a_out import exchanges
    return exchanges(ctx)


def a2a_cancel(ctx: Context) -> Any:
    from .a2a_out import cancel
    return cancel(ctx)


def carry_peers(ctx: Context | None = None) -> list[str]:
    """The mcp module's start: a stored mcp_a2a_peers list carried into the peer records once per home."""
    from .a2a_peers import carry
    return carry(ctx)


def agent_actions(ctx: Context, capabilities: dict[str, Any] | None = None) -> dict[str, Any]:
    from .server import action_bindings
    return action_bindings(ctx, capabilities)


def list_peers(ctx: Context) -> Any:
    from .a2a_peers import show
    return show(ctx)


def add_peer(ctx: Context) -> Any:
    from .a2a_peers import add
    return add(ctx)


def remove_peer(ctx: Context) -> Any:
    from .a2a_peers import remove
    return remove(ctx)


class HttpService:
    """What this module offers another module that serves its MCP app behind a front door of its own, such as cloud's
    tunnel: the app, the check of a broker's assertions, the exposure it is served under and the scope ladder. Found
    with `provided(folder, 'mcp.http')`, so no module imports this one's internals."""

    @staticmethod
    def http_app(folder: Path, **given: Any) -> Any:
        from .server import http_app
        return http_app(folder, **given)

    @staticmethod
    def asserted(*given: Any, **named: Any) -> Any:
        from .oauth import Asserted
        return Asserted(*given, **named)

    @staticmethod
    def exposure(**given: Any) -> Any:
        from .oauth import Exposure
        return Exposure(**given)

    @staticmethod
    def scopes_up_to(capability: str) -> tuple[str, ...]:
        from .oauth import scopes_up_to
        return tuple(scopes_up_to(capability))


def exchange_open(folder: Path) -> bool:
    """Whether an exchange this project sent is still open, so the verb that cancels one is listed over MCP, MCP-004."""
    project = project_for(folder)
    return project is not None and bool(a2a_records.exchanges(project, open_only=True))


def agent_opening(folder: Path, task: str | None) -> str:
    """The directive and links that open a dispatched agent's session and its first turn after a compaction, for an
    agent on the task named `task` or on none, `server.opening`, offered as `agent.opening` so a runner reaches it
    through the chassis; imported here only when asked."""
    from .server import dispatched_agent, opening
    return opening(dispatched_agent(folder, task))


MODULE = Module(
    id='mcp',
    summary="Serve Metaform's tools to AI tools over MCP.",
    purpose="Serves Metaform's tools to AI tools over MCP. Every tool is also a metaform command on the CLI. "
            'Details: metaform help mcp.',
    details='A host starts it with uvx --from <source> metaform mcp serve. It serves the folder it starts in, '
            "whatever that folder's command surface; the surface narrows the tools it serves. With --http it serves "
            'Streamable HTTP at http://127.0.0.1:<mcp_port>/mcp until stopped.',
    verbs=(Verb('serve', serve, 'Serve the MCP server over stdio, or with --http over Streamable HTTP.',
                switches=('mcp_http', 'mcp_port', 'mcp_bind', 'mcp_public_url'),
                surfaces=('cli',), transport=True),
           Verb('a2a_send', a2a_send, 'Send an A2A peer the person names a message about an Address; what its task '
                                      'does comes back to that Address.',
                nouns=(Noun('peer', 'The peer, by its name in mcp a2a_peers.'),
                       Noun('address', 'The Address the work concerns: the contextId the peer receives, and where '
                                       'its answers, artifacts and questions land here.'),
                       Noun('text', 'The work, in words the peer reads with none of your context.'),
                       Noun('title', 'A short title for the work, given to the peer.', required=False),
                       Noun('work', 'The ticket this belongs to, by its work id; an agent\'s own by default.',
                            required=False)),
                details='The message carries the Address as its contextId under the Address extension and the '
                        'sending agent instance in its metadata, MCP-042. The exchange is kept in the project before '
                        'the message leaves, so a reply after a restart lands at its Address. metaform mcp serve '
                        '--http follows every open exchange; mcp a2a_exchanges reads one again.',
                examples=((('metaform mcp a2a_send other code.alarm.audible "Make the alarm louder: the cook '
                            'misses it over the fan."'), 'Hand the alarm work to the peer named other.'),),
                open_world=True),
           Verb('a2a_exchanges', a2a_exchanges, 'List the A2A exchanges sent from this project, newest first, '
                                                'each open one read again from its peer.',
                nouns=(Noun('id', 'One exchange, by its id.', required=False),
                       Noun('address', 'Only those about this Address.', required=False)),
                open_world=True),
           Verb('a2a_cancel', a2a_cancel, "Cancel an A2A exchange's task at its peer.",
                nouns=(Noun('id', 'The exchange, by its id.'),), open_world=True, listed=exchange_open),
           # A2A outbound's peers, MCP-040: records of the home that only the person adds and removes, so a2a_send
           # reaches no other agent. Settings cleanup 2026-10-15 made them records; they were the list mcp_a2a_peers.
           Verb('a2a_peers', list_peers, 'List the A2A peers the person names, the only agents work is sent to.',
                effect='read', needs_project=False),
           Verb('a2a_peer_add', add_peer, 'Add an A2A peer work may be sent to, or replace the one of that name.',
                nouns=(Noun('name', 'Its short name: lowercase letters, digits, _ and -.'),
                       Noun('url', "Its Agent Card's URL, such as http://127.0.0.1:7440/.well-known/agent-card.json."),
                       Noun('token', 'The environment variable that holds the bearer token it takes; read when a '
                                     'message is sent, never stored.', required=False)),
                details='The person\'s own: run on the command line, never from an agent\'s session. The other peers '
                        'stay as they are.',
                examples=((('metaform mcp a2a_peer_add other http://127.0.0.1:7440/.well-known/agent-card.json '
                            'token=OTHER_A2A_TOKEN'), 'Lets agents here send work to another Metaform.'),),
                surfaces=('cli',), effect='write', needs_project=False),
           Verb('a2a_peer_remove', remove_peer, 'Remove an A2A peer; no work is sent to it after.',
                nouns=(Noun('name', 'The peer, by its name.'),),
                details='The person\'s own: run on the command line, never from an agent\'s session.',
                surfaces=('cli',), effect='remove', needs_project=False)),
    mcp_server='serve',
    tables=TABLES,
    start=carry_peers,
    subscriptions=(Subscription('map.changed', changed),),
    provides=(Provides('mcp.http', HttpService()), Provides('agent.opening', agent_opening),
              Provides('agent.actions', agent_actions)),
)
