"""The web GUI's server process, VIEW-002: the standard library's threading HTTP server, detached from any terminal.

`metaform web` starts it with `python -m metaform.modules.web.server`. Every
request must name the server's own address and port in its Host header, so a
page that rebinds a domain to this machine reads nothing. On a bind address
other than loopback, every request also needs the home's token: in the page
URL as `?t=`, then in a cookie the page load sets, or in the
`X-Metaform-Token` header. The server writes its record to `run/web.json`
once it listens, then says so on the pipe `metaform web` gave it as standard
output, and its loop waits in `select` with no timeout, waking only for a
connection; the stop signal ends the process, QUAL-015.
"""
from __future__ import annotations

import argparse
import hmac
import json
import ipaddress
import os
import queue
import socket
import socketserver
import sys
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, urlsplit

from metaform import changes, home, query, results, settings
from metaform.context import toggled_for
from metaform.data import Outcome, Store, prompts
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
        self.listeners: set[queue.SimpleQueue[dict[str, Any]]] = set()
        self.listening = threading.Lock()
        super().__init__((bind, port), Handler)
        self.port = int(self.server_address[1])
        names = {'127.0.0.1', 'localhost', '::1'} if loopback(bind) else {bind, socket.gethostname()}
        self.hosts = {host_port(name, self.port).lower() for name in names}

    def server_bind(self) -> None:
        """Bind without `HTTPServer`'s own reverse lookup of the address, which can stall for many seconds on macOS
        before the server answers; the server never uses the name it looks up."""
        if os.name == 'nt':
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)  # type: ignore[attr-defined]
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.bind, int(self.server_address[1])

    def own_host(self, host: str | None) -> bool:
        """The Host header names this server. On a wildcard bind every name of the machine is its own, so only the
        port is checked there, and the token guards every request."""
        if not host:
            return False
        host = host.strip().lower()
        if self.bind in WILDCARDS:
            return host.rsplit(':', 1)[-1] == str(self.port) and ':' in host
        return host in self.hosts

    def push(self, event: dict[str, Any]) -> int:
        """Hand one event to every open page's stream, VIEW-018."""
        with self.listening:
            for waiting in self.listeners:
                waiting.put(event)
            return len(self.listeners)

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
        if method == 'POST' and url.path == '/api/notify':
            return self.notify()
        if method == 'POST':
            return self.write(url.path)
        if url.path == '/api/events':
            return self.events()
        if url.path == '/api/server':
            return self.send(200, {'pid': os.getpid(), 'home': str(home.home())})
        if url.path == '/api/projects':
            return self.send(200, {'projects': [{'id': found.project_id, 'path': found.path}
                                                for found in home.projects()]})
        if url.path == '/api/clear-preview':
            return self.clear_preview(query.get('project', [''])[-1])
        if url.path.startswith('/api/'):
            return self.read(url.path[5:], {key: values[-1] for key, values in query.items() if key != 't'})
        if url.path == '/':
            return self.file(STATIC['page'], 'index.html', set_cookie='t' in query)
        top, _, rest = url.path.lstrip('/').partition('/')
        if top in STATIC and rest:
            return self.file(STATIC[top], rest)
        return self.send(404, {'error': f'Nothing at {url.path}.'})

    def read(self, name: str, given: dict[str, str]) -> None:
        """One store read of STORE-025 by its query name, for one project, with the page's layers or the folder's;
        or a read of the home's prompt store, which belongs to no project, STORE-044."""
        if name in PROMPT_READS:
            try:
                return self.send(200, plain(PROMPT_READS[name](given)))
            except StoreError as error:
                return self.send(404, {'error': str(error), 'next': error.next_step})
        if name not in query.READS:
            return self.send(404, {'error': f'No read {name}.'})
        try:
            store = opened(given)
            found = query.call(store, name, {key: value for key, value in given.items() if key not in RESERVED})
        except (Stop, StoreError) as error:
            return self.send(404 if isinstance(error, StoreError) else 400,
                             {'error': str(error), 'next': getattr(error, 'next_step', None)})
        if found is None:
            return self.send(404, {'error': f'Nothing for {name} here, in these layers.'})
        self.reply(200, results.as_json(found).encode('utf-8'), 'application/json', {'Cache-Control': 'no-store'})

    def notify(self) -> None:
        """A module's event, handed over by the web module's subscriber in the publishing process, VIEW-018. Only
        a process on this machine holding the server's nonce, which is in its run file, can hand one over."""
        data = self.rfile.read(int(self.headers.get('Content-Length') or 0))
        if not local(self.client_address[0]) or not hmac.compare_digest(self.headers.get('X-Metaform-Nonce') or '',
                                                                        self.gui.nonce):
            return self.send(403, {'error': "Events are taken only from this machine, with the server's nonce."})
        try:
            event: Any = json.loads(data or b'null')
        except ValueError:
            return self.send(400, {'error': 'The event is not JSON.'})
        if not isinstance(event, dict):
            return self.send(400, {'error': 'An event is a JSON object with its topic and payload.'})
        self.send(200, {'pages': self.gui.push(cast(dict[str, Any], event))})

    def events(self) -> None:
        """One open page's stream of what modules publish, held open. Its thread sleeps until an event comes and
        writes it; nothing polls, QUAL-015. A page that has gone is dropped at the next event."""
        waiting: queue.SimpleQueue[dict[str, Any]] = queue.SimpleQueue()
        with self.gui.listening:
            self.gui.listeners.add(waiting)
        self.close_connection = True
        try:
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Connection', 'close')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(b': open\n\n')
            self.wfile.flush()
            while True:
                self.wfile.write(b'data: ' + json.dumps(waiting.get()).encode('utf-8') + b'\n\n')
                self.wfile.flush()
        except OSError:
            pass
        finally:
            with self.gui.listening:
                self.gui.listeners.discard(waiting)

    def write(self, path: str) -> None:
        """One of the four writes of VIEW-011, from the GUI's own page only: the same Origin, and a JSON body."""
        origin = self.headers.get('Origin')
        if origin is None or origin.lower() != f'http://{self.headers.get("Host", "")}'.lower():
            return self.send(403, {'error': "A write is taken only from the web GUI's own page."})
        if (self.headers.get('Content-Type') or '').split(';')[0].strip().lower() != 'application/json':
            return self.send(415, {'error': 'A write takes a JSON body.'})
        writes = {'/api/apply-layers': self.apply_layers, '/api/remove-correction': self.remove_correction,
                  '/api/save-prompt': self.save_prompt, '/api/clear-project': self.clear_project}
        if path not in writes:
            return self.send(404, {'error': f'No such write: {path}.'})
        try:
            body: Any = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)) or b'null')
        except ValueError:
            return self.send(400, {'error': 'The body is not JSON.'})
        try:
            writes[path](cast(dict[str, Any], body) if isinstance(body, dict) else {})
        finally:  # the page's own write reaches every open page, VIEW-018
            for project, metaforms in sorted(changes.take().items()):
                for metaform in sorted(metaforms):
                    self.gui.push({'topic': 'map.changed', 'payload': {'project': project,
                                                                       'metaform_id': metaform or None}})

    def remove_correction(self, given: dict[str, Any]) -> None:
        """Peel the top correction layer and discard it, in one write, only while it is still the top, VIEW-014."""
        layer = str(given.get('layer', ''))
        try:
            store = opened({'project': str(given.get('project', '')), 'metaform': str(given.get('metaform') or '')})
            with store.atomic():
                peeled = store.peel(layer)
                if isinstance(peeled, Outcome):
                    return self.send(200, {'layer': layer, 'removed': False, 'notices': plain(peeled.notices)})
                done = store.discard(layer)
        except (Stop, StoreError) as error:
            return self.send(400, {'error': str(error), 'next': getattr(error, 'next_step', None)})
        self.send(200, {'layer': layer, 'removed': True, 'notices': plain(done.notices)})

    def save_prompt(self, given: dict[str, Any]) -> None:
        """Save an edited prompt as its next version, edited from `parent`; no version ever changes, VIEW-013."""
        name, text, parent = given.get('name'), given.get('text'), given.get('parent')
        if not isinstance(name, str) or not isinstance(text, str) or not isinstance(parent, int) \
                or isinstance(parent, bool):
            return self.send(400, {'error': 'Saving a prompt takes its name, the text, and the version number it '
                                            'was edited from.'})
        try:
            saved = prompts.add_prompt_version(name, text, parent)
        except StoreError as error:
            return self.send(400, {'error': str(error), 'next': error.next_step})
        self.send(200, plain(saved))

    def apply_layers(self, given: dict[str, Any]) -> None:
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

    def clear_preview(self, project: str) -> None:
        """What clearing the project removes and keeps, in the command's own caution; it changes nothing, VIEW-019."""
        if home.project(project) is None:
            return self.send(404, {'error': f'No project {project} is registered.', 'next': 'metaform list projects'})
        found = home.to_clear(project)
        self.send(200, {**found.to_dict(), 'caution': found.caution})

    def clear_project(self, given: dict[str, Any]) -> None:
        """Clear the project through the chassis's `clear_project`, as `metaform clear project --confirm` does, and
        only with `confirm` true, as the command only with `--confirm`, PROJ-025 and VIEW-019."""
        project = str(given.get('project', ''))
        if home.project(project) is None:
            return self.send(404, {'error': f'No project {project} is registered.', 'next': 'metaform list projects'})
        if given.get('confirm') is not True:
            return self.send(400, {'error': home.to_clear(project).caution,
                                   'next': 'If you are sure: send confirm true'})
        cleared = home.clear_project(project)
        answer = {**cleared.to_dict(), 'said': cleared.said}
        if cleared.not_removed:  # still on disk, and what to do, as a notice and never an error, BASE-044
            answer['notices'] = [{'where': 'not_removed',
                                  'message': f'{cleared.left} {cleared.remedy("use Clear project again")}'}]
        self.send(200, answer)

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


def local(address: str) -> bool:
    """Whether a client address is this machine's loopback, an IPv4 one seen through an IPv6 socket included."""
    try:
        found = ipaddress.ip_address(address.split('%', 1)[0])
    except ValueError:
        return False
    mapped = getattr(found, 'ipv4_mapped', None)
    return (mapped or found).is_loopback


def _versions(given: dict[str, str]) -> dict[str, Any]:
    """Every version of a prompt, newest first, each with the layers it made."""
    return {'versions': [{**cast(dict[str, Any], plain(version)),
                          'layers': plain(prompts.layers_by_prompt_version(version.version_id))}
                         for version in prompts.prompt_versions(given.get('name', ''))]}


PROMPT_READS: dict[str, Callable[[dict[str, str]], Any]] = {
    'prompts': lambda given: {'prompts': prompts.prompts()},
    'prompt': lambda given: prompts.prompt_version(given.get('name', ''), int(given['number'])
                                                   if given.get('number', '').isdigit() else None),
    'prompt-versions': _versions,
}


def opened(given: dict[str, str]) -> Store:
    """The project's store, with the layers the page chose, or else the `--layers` of the project's own folder, which
    stands for the folder the web GUI shows, question 5."""
    project = home.project(given.get('project', ''))
    if project is None:
        raise StoreError(f'No project {given.get("project", "")} is registered.', 'metaform list projects')
    chosen = given.get('layers')
    toggled = [name for name in chosen.split(',') if name] if chosen is not None else toggled_for(Path(project.path))
    return Store(project.project_id, toggled=toggled, metaform=given.get('metaform') or None)


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
    ready(server)
    with server:
        # Wakes only for a connection, QUAL-015; the stop signal ends the process, so nothing checks for shutdown.
        # The stubs type poll_interval as float; the standard library hands it to select, where None is no timeout.
        server.serve_forever(poll_interval=None)  # type: ignore[arg-type]
    return 0


def ready(server: Server) -> None:
    """Tell `metaform web` the server listens: one line on the pipe it inherited as standard output, which is then
    pointed at the log so nothing else is ever written to the pipe, VIEW-002."""
    sys.stdout.write(json.dumps({'pid': os.getpid(), 'port': server.port}) + '\n')
    sys.stdout.flush()
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())


if __name__ == '__main__':
    sys.exit(main())
