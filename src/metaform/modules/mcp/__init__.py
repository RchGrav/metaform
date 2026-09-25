"""mcp: serves Metaform's tools to AI tools over MCP, MCP-001.

`metaform mcp serve` starts the server over stdio. It is declared for the CLI
only, so it is never itself a tool. Every tool comes from a module verb on the
folder's command surface, MCP-003; the server gets no private access to the
chassis.
"""
from __future__ import annotations

from pathlib import Path

from metaform.module import Context, Module, Verb

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ('mcp>=2.2',)
SHIPS_DISABLED = False


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
)
