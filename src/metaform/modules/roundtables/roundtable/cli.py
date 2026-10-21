"""The command line: `roundtable serve` runs the MCP server, over stdio, or Streamable HTTP on the loopback with
--http, the web page beside it; `roundtable web` runs the web page alone; `roundtable run <N>` is a table's runner,
started detached by the server; `roundtable import <file>` takes in a table Metaform recorded; `roundtable settings`
prints the settings in force."""
from __future__ import annotations

import argparse
import json


def main() -> None:
    parser = argparse.ArgumentParser(prog='roundtable', description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    serving = commands.add_parser('serve', help='Run the MCP server.')
    serving.add_argument('--http', action='store_true', help='Streamable HTTP on the loopback, in place of stdio.')
    serving.add_argument('--host', help='127.0.0.1 by default.')
    serving.add_argument('--port', type=int, help='7435 by default.')
    showing = commands.add_parser('web', help='Run the web page alone.')
    showing.add_argument('--host', help='127.0.0.1 by default.')
    showing.add_argument('--port', type=int, help='7436 by default.')
    taking = commands.add_parser('import', help='Take in a table Metaform recorded, from its combined JSON.')
    taking.add_argument('file')
    running = commands.add_parser('run', help='Run a table; started detached by the server.')
    running.add_argument('discussion', type=int)
    commands.add_parser('settings', help='Print the settings in force.')
    given = parser.parse_args()
    if given.command == 'serve':
        from .server import serve
        serve(given.http, given.host, given.port)
    elif given.command == 'web':
        from .server import serve_web
        serve_web(given.host, given.port)
    elif given.command == 'import':
        from pathlib import Path

        from .importing import load
        print(json.dumps({'discussion': load(Path(given.file).expanduser().resolve())}))
    elif given.command == 'run':
        from .runner import run
        print(json.dumps(run(given.discussion)))
    else:
        from .config import shown
        print(json.dumps(shown(), indent=2))
