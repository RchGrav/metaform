"""mcp: serves Metaform's tools to AI tools over MCP, MCP-001.

`metaform mcp serve` starts the server over stdio. It is declared for the CLI
only, so it is never itself a tool. Every tool comes from a module verb on the
folder's command surface, MCP-003; the server gets no private access to the
chassis.
"""
from __future__ import annotations

from pathlib import Path

from metaform import settings
from metaform.module import Context, Module, Verb

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ('mcp>=2.2,<3',)
SHIPS_DISABLED = False
REMOTE_AGENT = False  # a hosted agent reaches Metaform through the CLI, and mcp's compiled dependencies do not travel

settings.choice('mcp_schemas', ['on_demand', 'inline'], 'on_demand', label='Tool schemas',
                help='List the commands only and serve an argument schema when asked, or serve every schema inside '
                     'its tool.',
                details='On demand keeps what every agent is handed at connect to the menu, about 2,000 tokens; an '
                        'argument schema is read with help or at metaform://tools/<tool>/<command> when a command is '
                        'used. Inline puts every schema in the tool list, about 28,000 tokens for every agent '
                        'whatever its role.')
settings.choice('mcp_recovery', ['relay', 'manual'], 'relay', label='Schema upgrade recovery',
                help='On a newer store, relay this connection to changed code on disk, or require a manual restart.',
                details='Relay preserves the host connection and retries calls refused before dispatch. '
                        'Manual returns the schema error. Unchanged package code never starts a replacement.')


def serve(ctx: Context) -> None:
    from .server import serve as run_server
    run_server(Path(ctx.folder))


MODULE = Module(
    id='mcp',
    summary="Serve Metaform's tools to AI tools over MCP.",
    purpose="Serves Metaform's tools to AI tools over MCP. Every tool is also a metaform command on the CLI. "
            'Details: metaform help mcp.',
    details='A host starts it with uvx --from <source> metaform mcp serve. It serves the folder it starts in, '
            "whatever that folder's command surface; the surface narrows the tools it serves.",
    verbs=(Verb('serve', serve, 'Serve the MCP server over stdio.', surfaces=('cli',), transport=True),),
    mcp_server='serve',
)
