"""The web GUI's server process, VIEW-002: the standard library's threading HTTP server, detached from any terminal.

`metaform web` starts it with `python -m metaform.modules.web.server`. Every
request must name the server's own address and port in its Host header, so a
page that rebinds a domain to this machine reads nothing. On a bind address
other than loopback, every request also needs the home's token: in the page
URL as `?t=`, then in a cookie the page load sets, or in the
`X-Metaform-Token` header. The server writes its record to `run/web.json`
once it listens.
"""
from __future__ import annotations

import argparse
import hmac
import json
import os
import socket
import sys
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, urlsplit

from metaform import home, query, results, settings
from metaform.context import toggled_for
from metaform.data import Store
from metaform.data.paging import LIMIT
from metaform.data.records import plain
from metaform.errors import Stop, StoreError

from . import WILDCARDS, host_port, loopback, run_file, token

HERE = Path(__file__).parent
STATIC = {'page': HERE / 'page', 'vendor': HERE / 'vendor'}
COOKIE = 'metaform_token'
RESERVED = ('project', 'metaform', 'layers')  # what picks the store and its layers; never a read's own argument
TYPES = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
         '.json': 'application/json', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.md': 'text/plain; charset=utf-8',
         '.txt': 'text/plain; charset=utf-8'}  # fixed, since Windows's registry can give .js a type browsers refuse
PAGE_POLICY = "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'"


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = os.name != 'nt'  # on Windows it would let a second server share the port

    def __init__(self, bind: str, port: int, nonce: str) -> None:
        self.address_family = socket.AF_INET6 if ':' in bind else socket.AF_INET
        self.bind, self.nonce = bind, nonce
        self.token = None if loopback(bind) else token()
        super().__init__((bind, port), Handler)
        self.port = int(self.server_address[1])
        names = {'127.0.0.1', 'localhost', '::1'} if loopback(bind) else {bind, socket.gethostname(), socket.getfqdn()}
        self.hosts = {host_port(name, self.port).lower() for name in names}

    def server_bind(self) -> None:
        if os.name == 'nt':
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)  # type: ignore[attr-defined]
        super().server_bind()

    def own_host(self, host: str | None) -> bool:
        """The Host header names this server. On a wildcard bind every name of the machine is its own, so only the
        port is checked there, and the token guards every request."""
        if not host:
            return False
        host = host.strip().lower()
        if self.bind in WILDCARDS:
            return host.rsplit(':', 1)[-1] == str(self.port) and ':' in host
        return host in self.hosts

    def record(self) -> None:
        path = run_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        written = path.with_suffix('.tmp')
        written.write_text(json.dumps({'pid': os.getpid(), 'bind': self.bind, 'port': self.port,
                                       'home': str(home.home()), 'nonce': self.nonce,
                                       'started': datetime.now(timezone.utc).isoformat(timespec='seconds')}),
                           encoding='utf-8')
        os.replace(written, path)


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    @property
    def gui(self) -> Server:
        return cast(Server, self.server)

    def log_message(self, format: str, *args: Any) -> None:
        """Requests are not logged; the log holds only what went wrong."""

    def do_GET(self) -> None:
        self.answer('GET')

    def do_POST(self) -> None:
        self.answer('POST')

    def answer(self, method: str) -> None:
        if not self.gui.own_host(self.headers.get('Host')):
            return self.send(403, {'error': "This request is not for the web GUI's own address."})
        url = urlsplit(self.path)
        query = parse_qs(url.query, keep_blank_values=True)
        given = self.given_token(query)
        if self.gui.token is not None and not (given and hmac.compare_digest(given, self.gui.token)):
            return self.send(403, {'error': 'This request needs the token that metaform web prints.'})
        if method == 'POST':
            return self.write(url.path)
        if url.path == '/api/server':
            return self.send(200, {'pid': os.getpid(), 'home': str(home.home())})
        if url.path == '/api/projects':
            return self.send(200, {'projects': [{'id': found.project_id, 'path': found.path}
                                                for found in home.projects()]})
        if url.path.startswith('/api/'):
            return self.read(url.path[5:], {key: values[-1] for key, values in query.items() if key != 't'})
        if url.path == '/':
            return self.file(STATIC['page'], 'index.html', set_cookie='t' in query)
        top, _, rest = url.path.lstrip('/').partition('/')
        if top in STATIC and rest:
            return self.file(STATIC[top], rest)
        return self.send(404, {'error': f'Nothing at {url.path}.'})

    def read(self, name: str, given: dict[str, str]) -> None:
        """One store read of STORE-025 by its query name, for one project, with the page's layers or the folder's."""
        if name != 'graph' and name not in query.READS:
            return self.send(404, {'error': f'No read {name}.'})
        try:
            store = opened(given)
            arguments = {key: value for key, value in given.items() if key not in RESERVED}
            found = graph(store, arguments) if name == 'graph' else query.call(store, name, arguments)
        except (Stop, StoreError) as error:
            return self.send(404 if isinstance(error, StoreError) else 400,
                             {'error': str(error), 'next': getattr(error, 'next_step', None)})
        if found is None:
            return self.send(404, {'error': f'Nothing for {name} here, in these layers.'})
        self.reply(200, results.as_json(found).encode('utf-8'), 'application/json', {'Cache-Control': 'no-store'})

    def write(self, path: str) -> None:
        """One of the three writes of VIEW-011, from the GUI's own page only: the same Origin, and a JSON body."""
        origin = self.headers.get('Origin')
        if origin is None or origin.lower() != f'http://{self.headers.get("Host", "")}'.lower():
            return self.send(403, {'error': "A write is taken only from the web GUI's own page."})
        if (self.headers.get('Content-Type') or '').split(';')[0].strip().lower() != 'application/json':
            return self.send(415, {'error': 'A write takes a JSON body.'})
        if path != '/api/apply-layers':
            return self.send(404, {'error': f'No such write: {path}.'})
        try:
            body: Any = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)) or b'null')
        except ValueError:
            return self.send(400, {'error': 'The body is not JSON.'})
        given = cast(dict[str, Any], body) if isinstance(body, dict) else {}
        project = home.project(str(given.get('project', '')))
        layers = given.get('layers')
        if project is None or not isinstance(layers, list):
            return self.send(400, {'error': 'Apply takes a registered project and a list of layers.'})
        folder = Path(project.path)
        try:
            settings.checked('layers', layers, folder, typed=True)
            assigned = settings.put('layers', layers, folder)
        except settings.SettingError as error:
            return self.send(400, {'error': str(error), 'next': error.next_step})
        self.send(200, {'project': project.project_id, 'folder': str(folder), 'layers': assigned.new,
                        'notices': [{'where': 'layers', 'message': notice} for notice in assigned.notices]})

    def given_token(self, query: dict[str, list[str]]) -> str | None:
        if query.get('t'):
            return query['t'][0]
        if self.headers.get('X-Metaform-Token'):
            return str(self.headers['X-Metaform-Token'])
        cookie = SimpleCookie(self.headers.get('Cookie') or '')
        return cookie[COOKIE].value if COOKIE in cookie else None

    def file(self, base: Path, relative: str, *, set_cookie: bool = False) -> None:
        resolved = (base / relative).resolve()
        if not resolved.is_relative_to(base.resolve()) or not resolved.is_file():
            return self.send(404, {'error': 'Nothing here.'})
        body = resolved.read_bytes()
        kind = TYPES.get(resolved.suffix.lower(), 'application/octet-stream')
        headers = {'Content-Security-Policy': PAGE_POLICY}
        if set_cookie and self.gui.token is not None:
            headers['Set-Cookie'] = f'{COOKIE}={self.gui.token}; Path=/; HttpOnly; SameSite=Strict'
        self.reply(200, body, kind, headers)

    def send(self, status: int, data: Any) -> None:
        self.reply(status, json.dumps(data).encode('utf-8'), 'application/json', {'Cache-Control': 'no-store'})

    def reply(self, status: int, body: bytes, kind: str, headers: dict[str, str]) -> None:
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)


def opened(given: dict[str, str]) -> Store:
    """The project's store, with the layers the page chose, or else the `--layers` of the project's own folder, which
    stands for the folder the web GUI shows, question 5."""
    project = home.project(given.get('project', ''))
    if project is None:
        raise StoreError(f'No project {given.get("project", "")} is registered.', 'metaform list projects')
    chosen = given.get('layers')
    toggled = [name for name in chosen.split(',') if name] if chosen is not None else toggled_for(Path(project.path))
    return Store(project.project_id, toggled=toggled, metaform=given.get('metaform') or None)


def following(store: Store, address: str) -> str | None:
    """The next address after this one in the namespace tree, depth first, through `children`."""
    first = store.children(address, limit=1).results
    if first:
        return first[0]
    while address:
        parent = address.rpartition('.')[0]
        sibling = store.children(parent, after=address, limit=1).results
        if sibling:
            return sibling[0]
        address = parent
    return None


def graph(store: Store, given: dict[str, str]) -> dict[str, Any]:
    """A page of the whole map for the 3D view: each element at its address in namespace order, with its nearest
    parent element, and each join it receives with its subtypes, VIEW-005 and VIEW-010. Only reads of STORE-025."""
    raw = given.get('raw') == 'true'
    limit = int(given.get('limit') or LIMIT)
    elements: list[dict[str, Any]] = []
    joins: list[dict[str, Any]] = []
    known: dict[str, bool] = {}

    def element_at(address: str) -> Any:
        found = store.where(address, raw=raw)
        known[address] = found is not None and found.element is not None
        return found.element if found is not None else None

    def parent_of(address: str) -> str | None:
        prefix = address.rpartition('.')[0]
        while prefix:
            if known.get(prefix) if prefix in known else element_at(prefix) is not None:
                return prefix
            prefix = prefix.rpartition('.')[0]
        return None

    address = following(store, given.get('after') or '')
    while address is not None and (limit == 0 or len(elements) < limit):
        element = element_at(address)
        if element is not None:
            elements.append({'element': plain(element), 'parent': parent_of(address)})
            for join in store.joins(element.element_id, raw=raw, limit=0).results:
                held = store.subtypes(join.join_id, raw=raw, limit=0).results
                joins.append({**cast(dict[str, Any], plain(join)),
                              'subtypes': [plain(subtype) for subtype in held]})
        last, address = address, following(store, address)
        if address is not None and limit and len(elements) >= limit:
            return {'elements': elements, 'joins': joins, 'next': last}
    return {'elements': elements, 'joins': joins, 'next': None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='metaform-web')
    parser.add_argument('--bind', required=True)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--nonce', required=True)
    given = parser.parse_args(argv)
    try:
        server = Server(given.bind, given.port, given.nonce)
    except OSError as error:
        print(f'{datetime.now(timezone.utc).isoformat(timespec="seconds")} cannot listen at '
              f'{host_port(given.bind, given.port)}: {error}', file=sys.stderr, flush=True)
        return 1
    server.record()
    with server:
        server.serve_forever()
    return 0


if __name__ == '__main__':
    sys.exit(main())
