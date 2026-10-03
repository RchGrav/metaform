"""Fake executables for installer tests: each records its arguments, and a fake uvx serves a tiny MCP server.

A fake is a Python script run by this interpreter, with a `.cmd` launcher on
Windows, so the installer finds it on PATH on every system, MCP-023.
"""
from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path

RECORDER = '''
import json, sys, pathlib
log = pathlib.Path(__file__).with_suffix('.log')
with log.open('a', encoding='utf-8') as out:
    out.write(json.dumps(sys.argv[1:]) + '\\n')
state = pathlib.Path(__file__).with_suffix('.servers')
names = json.loads(state.read_text()) if state.exists() else []
args = sys.argv[1:]
if args[:2] == ['mcp', 'add']:
    name = next(arg for arg in args[2:] if not arg.startswith('-') and arg not in ('stdio', 'user'))
    if name in names:
        print(f'{name} already exists', file=sys.stderr); sys.exit(1)
    names.append(name)
elif args[:2] == ['mcp', 'remove']:
    name = [arg for arg in args[2:] if not arg.startswith('-') and arg != 'user'][0]
    if name in names:
        names.remove(name)
state.write_text(json.dumps(names))
'''

SERVER = '''
import json, sys, pathlib
# MCP 2026-07-28 only: no initialize handshake, and every request carries the per-request _meta. Each line read is kept.
log = pathlib.Path(__file__).with_suffix('.requests')
KEYS = ('io.modelcontextprotocol/protocolVersion', 'io.modelcontextprotocol/clientCapabilities')
for line in sys.stdin:
    with log.open('a', encoding='utf-8') as out:
        out.write(line)
    message = json.loads(line)
    if 'id' not in message:
        continue
    meta = (message.get('params') or {}).get('_meta') or {}
    if message['method'] not in ('server/discover', 'tools/list', 'ping'):
        reply = {'error': {'code': -32601, 'message': 'Method not found'}}
    elif any(key not in meta for key in KEYS) or meta[KEYS[0]] != '2026-07-28':
        reply = {'error': {'code': -32602, 'message': 'Invalid request parameters'}}
    elif message['method'] == 'server/discover':
        reply = {'result': {'resultType': 'complete', 'supportedVersions': ['2026-07-28'],
                            'capabilities': {'tools': {}}, 'serverInfo': {'name': 'fake', 'version': '0'},
                            'instructions': 'Fake instructions.'}}
    elif message['method'] == 'tools/list':
        reply = {'result': {'resultType': 'complete', 'tools': [{'name': 'one', 'inputSchema': {'type': 'object'}},
                                                               {'name': 'two', 'inputSchema': {'type': 'object'}}]}}
    else:
        reply = {'result': {'resultType': 'complete'}}
    print(json.dumps({'jsonrpc': '2.0', 'id': message['id'], **reply}), flush=True)
'''


def executable(folder: Path, name: str, body: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    script = folder / f'{name}.py'
    script.write_text(textwrap.dedent(body), encoding='utf-8')
    if os.name == 'nt':
        launcher = folder / f'{name}.cmd'
        launcher.write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding='utf-8')
    else:
        launcher = folder / name
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding='utf-8')
        launcher.chmod(0o755)
    return launcher


def recorder(folder: Path, name: str) -> Path:
    return executable(folder, name, RECORDER)


def server(folder: Path, name: str = 'uvx') -> Path:
    return executable(folder, name, SERVER)


def calls(folder: Path, name: str) -> list[list[str]]:
    import json
    log = folder / f'{name}.log'
    return [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()] if log.exists() else []
