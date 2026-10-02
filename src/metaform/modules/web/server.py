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
import base64
import hashlib
import hmac
import ipaddress
import json
import os
import queue
import re
import shlex
import socket
import socketserver
import subprocess
import sys
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, urlsplit

from metaform import changes, home, outline, query, results, settings
from metaform import module as chassis
from metaform.context import toggled_for
from metaform.data import Node, Outcome, Store, prompts
from metaform.data.records import COLUMNS, TICKETS, plain
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
IMPORT_MAP = re.compile(rb'<script type="importmap">(.*?)</script>', re.DOTALL)


def policy(body: bytes, kind: str) -> str:
    """The Content Security Policy a file is sent with, VIEW-003. A page's import map is an inline script, which a
    browser runs only when the policy names its SHA-256; it is read from the page itself, so the two always agree, and
    no other inline script is allowed."""
    found = IMPORT_MAP.search(body) if kind.startswith('text/html') else None
    if found is None:
        return PAGE_POLICY
    digest = base64.b64encode(hashlib.sha256(found.group(1)).digest()).decode('ascii')
    return f"{PAGE_POLICY}; script-src 'self' 'sha256-{digest}'"


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
                                       'started': datetime.now(UTC).isoformat(timespec='seconds')}),
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
        if url.path == '/api/remove-preview':
            return self.remove_preview(query.get('project', [''])[-1])
        if url.path == '/api/backups':
            return self.backups(query.get('project', [''])[-1])
        if url.path == '/api/markdown':
            return self.markdown({key: values[-1] for key, values in query.items() if key != 't'})
        if url.path.startswith('/api/memory-'):
            return self.memory_read(url.path[len('/api/memory-'):],
                                    {key: values[-1] for key, values in query.items() if key != 't'})
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
        if name == 'node':
            found = with_modules(given, found)
        self.reply(200, results.as_json(found).encode('utf-8'), 'application/json', {'Cache-Control': 'no-store'})

    def memory_read(self, name: str, given: dict[str, str]) -> None:
        """A read of the memory module for the page, VIEW-031 and VIEW-034: `graph`, the whole graph with each join
        saying whether its memory shows at its node in the page's layers; `orphaned`, the memory joins the map no longer
        holds, for the orphaned menu; and `note`, a node's one note."""
        if name not in MEMORY_READS:
            return self.send(404, {'error': f'No read memory-{name}.'})
        arguments = {'node': given['node']} if name == 'note' and given.get('node') else {}
        try:
            found = module_verb(given, 'memory', name, arguments)
        except (Stop, StoreError) as error:
            return self.send(404 if isinstance(error, StoreError) else 400,
                             {'error': str(error), 'next': getattr(error, 'next_step', None)})
        self.reply(200, results.as_json(found).encode('utf-8'), 'application/json', {'Cache-Control': 'no-store'})

    def markdown(self, given: dict[str, str]) -> None:
        """The map as the Markdown document the command writes, MAP-052, for the page's export, VIEW-024, with the
        page's layers or the folder's."""
        try:
            text = outline.markdown(opened(given), given.get('address') or None)
        except (Stop, StoreError) as error:
            return self.send(404 if isinstance(error, StoreError) else 400,
                             {'error': str(error), 'next': getattr(error, 'next_step', None)})
        self.reply(200, text.encode('utf-8'), 'text/markdown; charset=utf-8', {'Cache-Control': 'no-store'})

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
        """One of the fifteen writes of VIEW-011, from the GUI's own page only: the same Origin, and a JSON body."""
        origin = self.headers.get('Origin')
        if origin is None or origin.lower() != f'http://{self.headers.get("Host", "")}'.lower():
            return self.send(403, {'error': "A write is taken only from the web GUI's own page."})
        if (self.headers.get('Content-Type') or '').split(';')[0].strip().lower() != 'application/json':
            return self.send(415, {'error': 'A write takes a JSON body.'})
        writes = {'/api/apply-layers': self.apply_layers,
                  '/api/save-prompt': self.save_prompt, '/api/clear-project': self.clear_project, '/api/remove-project': self.remove_project,
                  '/api/answer': self.answer_question, '/api/read': self.read_note, '/api/task': self.give_work,
                  '/api/element': self.add_part, '/api/restore': self.restore,
                  '/api/note': self.add_note, '/api/move': self.move_ticket,
                  '/api/memory': self.write_memory,
                  '/api/dispatch-start': self.dispatch_start, '/api/dispatch-message': self.dispatch_message,
                  '/api/dispatch-stop': self.dispatch_stop}
        if path not in writes:
            return self.send(404, {'error': f'No such write: {path}.'})
        try:
            body: Any = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)) or b'null')
        except ValueError:
            return self.send(400, {'error': 'The body is not JSON.'})
        given = cast(dict[str, Any], body) if isinstance(body, dict) else {}
        try:
            writes[path](given)
        finally:  # announced as a command's write is: map.changed on the module event bus, VIEW-018 and BASE-010.
            # The web module's own subscriber hands it back to this server, which pushes it to every open page.
            project = home.project(str(given.get('project', '')))
            changes.announce(Path(project.path) if project is not None else home.home(), 'web')

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

    def remove_preview(self, project: str) -> None:
        """What removing the project does, in the command's own words, or why it cannot be removed yet: it holds what
        a clear removes and backs up. It changes nothing, PROJ-031 and VIEW-019."""
        if home.project(project) is None:
            return self.send(404, {'error': f'No project {project} is registered.', 'next': 'metaform list projects'})
        held = home.not_empty(project)
        self.send(200, {'project': project, 'held': held} if held else
                  {'project': project, 'caution': home.removal_caution(project)})

    def remove_project(self, given: dict[str, Any]) -> None:
        """Take an empty project off the list through the chassis's `remove_project`, as `metaform remove project
        --confirm` does, and only with `confirm` true, PROJ-031 and VIEW-019."""
        project = str(given.get('project', ''))
        if home.project(project) is None:
            return self.send(404, {'error': f'No project {project} is registered.', 'next': 'metaform list projects'})
        held = home.not_empty(project)
        if held:
            return self.send(400, {'error': held, 'next': 'Use Clear project first.'})
        if given.get('confirm') is not True:
            return self.send(400, {'error': home.removal_caution(project), 'next': 'If you are sure: send confirm true'})
        home.remove_project(project)
        self.send(200, {'project': project, 'said': f'Removed {project}. Its folder and files were not touched.'})

    def answer_question(self, given: dict[str, Any]) -> None:
        """Write the user's answer beside the question, which closes it, MAP-050 and VIEW-021. Only a question is
        answered from the page; any other work record is left as it is."""
        record, answer = str(given.get('id', '')), given.get('answer')
        if not isinstance(answer, str) or not answer.strip():
            return self.send(400, {'error': 'An answer says something.'})
        try:
            store = opened({'project': str(given.get('project', '')), 'metaform': str(given.get('metaform') or '')})
            with store.atomic():
                asked = [found for found in store.messages(None, 'question', True, limit=0).results
                         if found.message_id == record]
                if not asked:
                    return self.send(400, {'error': 'This is not an open question.'})
                done = store.reply(record, answer.strip())
        except (Stop, StoreError) as error:
            return self.send(400, {'error': str(error), 'next': getattr(error, 'next_step', None)})
        self.send(200, plain(done))

    def read_note(self, given: dict[str, Any]) -> None:
        """Mark a note read, which ends its record, VIEW-030. Only an unread note is read from the page."""
        record = str(given.get('id', ''))
        try:
            store = opened({'project': str(given.get('project', '')), 'metaform': str(given.get('metaform') or '')})
            with store.atomic():
                unread = [found for found in store.messages(None, 'message', True, limit=0).results
                          if found.message_id == record]
                if not unread:
                    return self.send(400, {'error': 'This is not an unread message.'})
                done = store.reply(record)
        except (Stop, StoreError) as error:
            return self.send(400, {'error': str(error), 'next': getattr(error, 'next_step', None)})
        self.send(200, plain(done))

    def give_work(self, given: dict[str, Any]) -> None:
        """Put a task a person wrote on the node it is assigned to, the first given, as one ticket that links the other
        nodes for reference, VIEW-032, VIEW-035 and MAP-048."""
        text, nodes, condition = given.get('task'), given.get('nodes'), given.get('condition', 'missing')
        if not isinstance(text, str) or not text.strip():
            return self.send(400, {'error': 'A task says what is to be done.'})
        if not isinstance(nodes, list) or not nodes or not all(isinstance(node, str) for node in cast(list[Any], nodes)):
            return self.send(400, {'error': 'A task is given at one node or more.'})
        if condition not in TICKETS:
            return self.send(400, {'error': 'Work is missing, broken, flawed or an enhancement.'})
        try:
            store = opened({'project': str(given.get('project', '')), 'metaform': str(given.get('metaform') or '')})
            with store.atomic():
                targets = [Node.parse(node) for node in cast(list[str], nodes)]
                written = [store.add_work(targets[0], condition, task=text.strip(), held=bool(given.get('held')),
                                          links=targets[1:])]
        except (Stop, StoreError) as error:
            return self.send(400, {'error': str(error), 'next': getattr(error, 'next_step', None)})
        self.send(200, {'results': plain(written)})

    def move_ticket(self, given: dict[str, Any]) -> None:
        """Put a ticket in a column of the board and at a place in it, VIEW-037 and STORE-042."""
        work_id, column, position = given.get('work_id'), given.get('column'), given.get('position')
        if not isinstance(work_id, str) or column not in COLUMNS:
            return self.send(400, {'error': 'A move names a ticket and a column: backlog, todo, doing or done.'})
        if position is not None and (not isinstance(position, int) or isinstance(position, bool)):
            return self.send(400, {'error': 'A place in a column is a whole number.'})
        try:
            store = opened({'project': str(given.get('project', '')), 'metaform': str(given.get('metaform') or '')})
            moved = store.move_work(work_id, column, position, given.get('by'))
        except (Stop, StoreError) as error:
            return self.send(400, {'error': str(error), 'next': getattr(error, 'next_step', None)})
        self.send(200, {'results': plain([moved])})

    def add_part(self, given: dict[str, Any]) -> None:
        """Add an element a person describes and join it to a node, in the layer of what people add by hand, and
        start an agent to validate it when asked to, VIEW-033. The element is on the map at once, as a part not
        built, with the validation as its open task."""
        address, anchor = given.get('address'), given.get('node')
        if not isinstance(address, str) or not address.strip():
            return self.send(400, {'error': 'An element has an address.'})
        if not isinstance(anchor, str) or given.get('receives') not in ('node', 'new'):
            return self.send(400, {'error': 'An element is joined to a node, and one of the two holds the purpose.'})
        project = home.project(str(given.get('project', '')))
        notices: list[dict[str, str]] = []
        try:
            store = opened({'project': str(given.get('project', '')), 'metaform': str(given.get('metaform') or '')})
            with store.atomic():
                store.layer(ADDITIONS, 'web', 'What people added to the map by hand.', mutable=True, hideable=True,
                            provenance=ADDED, ready=True)
                made = store.add_element(ADDITIONS, address.strip(), name_length=given.get('name_length') or None,
                                         role=given.get('role') or None, name=given.get('name') or None)
                if isinstance(made, Outcome):
                    return self.send(400, {'error': 'The element was not written.', 'notices': plain(made.notices)})
                held = Node.parse(anchor).id
                receiver, provider = (held, made.element_id) if given['receives'] == 'node' else (made.element_id, held)
                joined = store.add_join(ADDITIONS, receiver, provider, purpose=given.get('purpose') or None,
                                        ef=given.get('ef') or None)
                work = store.add_work(Node('element', made.element_id), 'missing', note='Added by hand in the web GUI.')
                if given.get('validate') is True:
                    work = store.edit_work(work.work_id, {'task': validation(made.address)})
        except (Stop, StoreError) as error:
            return self.send(400, {'error': str(error), 'next': getattr(error, 'next_step', None)})
        if given.get('validate') is True and project is not None and work.task:
            told = started_agent(Path(project.path), work.task)
            if told:
                notices.append({'where': 'agent', 'message': told})
        self.send(200, {'element': plain(made), 'join': plain(joined), 'work': plain(work), 'notices': notices})

    def backups(self, project: str) -> None:
        """The project's backups, the newest first, PROJ-030."""
        if home.project(project) is None:
            return self.send(404, {'error': f'No project {project} is registered.', 'next': 'metaform list projects'})
        self.send(200, {'results': [kept.to_dict() for kept in home.backups(project)]})

    def restore(self, given: dict[str, Any]) -> None:
        """Bring a backup back through the chassis's `restore_project`, as `metaform restore project` does."""
        project, backup = str(given.get('project', '')), given.get('backup')
        if home.project(project) is None:
            return self.send(404, {'error': f'No project {project} is registered.', 'next': 'metaform list projects'})
        try:
            restored = home.restore_project(project, backup if isinstance(backup, str) and backup else None)
        except (Stop, StoreError) as error:
            return self.send(400, {'error': str(error), 'next': getattr(error, 'next_step', None)})
        self.send(200, restored.to_dict())

    def add_note(self, given: dict[str, Any]) -> None:
        """Write the node's one note in place of what it held, as the user's, through `memory note`, VIEW-034; empty
        text clears it, and one over 2048 characters is refused with its length."""
        node, text = given.get('node'), given.get('text')
        if not isinstance(text, str):
            return self.send(400, {'error': 'A note is text; empty text clears it.'})
        if not isinstance(node, str) or not node:
            return self.send(400, {'error': 'A note is written at a node.'})
        try:
            written = module_verb(given, 'memory', 'note', {'node': node, 'text': text, 'by': 'user'})
        except (Stop, StoreError) as error:
            return self.send(400, {'error': str(error), 'next': getattr(error, 'next_step', None)})
        self.send(200, written)

    def write_memory(self, given: dict[str, Any]) -> None:
        """Change the memory graph as a person manages it, VIEW-031: `steps`, each a memory command that writes and
        its arguments, run in order through the memory module as the command line and the tools run them, stopping at
        the first that fails. An edit is two steps, the new written before the old is deleted, so a failure loses
        nothing."""
        steps = given.get('steps')
        if not isinstance(steps, list) or not steps or not all(memory_step(step) for step in cast(list[Any], steps)):
            return self.send(400, {'error': 'A memory change is a list of steps, each a command of '
                                            f'{", ".join(MEMORY_WRITES)} with its arguments.'})
        done: list[Any] = []
        for step in cast(list[dict[str, Any]], steps):
            try:
                done.append(module_verb(given, 'memory', step['command'], dict(step.get('arguments') or {})))
            except (Stop, StoreError) as error:
                return self.send(400, {'error': str(error), 'next': getattr(error, 'next_step', None),
                                       'done': done})
        self.send(200, {'done': done})

    def dispatch_start(self, given: dict[str, Any]) -> None:
        """Start an agent on a ticket with the dispatch module's start, VIEW-039 and BASE-052."""
        work_id, agent = given.get('work_id'), given.get('agent')
        if not isinstance(work_id, str) or not work_id or not isinstance(agent, str) or not agent:
            return self.send(400, {'error': 'An agent is started on a ticket: its work id and the agent.'})
        self.dispatched(given, 'start', [work_id, agent])

    def dispatch_message(self, given: dict[str, Any]) -> None:
        """Send a person's message to the agent working a ticket with the dispatch module's message, VIEW-039."""
        work_id, text = given.get('work_id'), given.get('text')
        if not isinstance(work_id, str) or not work_id:
            return self.send(400, {'error': 'A message goes to the agent working a ticket: its work id.'})
        if not isinstance(text, str) or not text.strip():
            return self.send(400, {'error': 'A message says something.'})
        self.dispatched(given, 'message', [work_id], text.strip())

    def dispatch_stop(self, given: dict[str, Any]) -> None:
        """Stop the agent working a ticket with the dispatch module's stop, VIEW-039."""
        work_id = given.get('work_id')
        if not isinstance(work_id, str) or not work_id:
            return self.send(400, {'error': 'An agent is stopped by the work id of its ticket.'})
        self.dispatched(given, 'stop', [work_id])

    def dispatched(self, given: dict[str, Any], verb: str, nouns: list[str], text: str | None = None) -> None:
        """Run one dispatch verb as `metaform dispatch` runs it in the project's folder, and answer with its result,
        or with its error and next step. It runs as the command line, so dispatch enabled after this server started
        is found, and the person's environment reaches the agent unchanged, BASE-052. A message's text comes after
        `--`, so no text a person writes is read as a switch."""
        project = home.project(str(given.get('project', '')))
        if project is None:
            return self.send(404, {'error': f'No project {given.get("project", "")} is registered.',
                                   'next': 'metaform list projects'})
        command = [sys.executable, '-m', 'metaform', 'dispatch', verb, *nouns, '--json', '--project',
                   project.project_id, *(['--', text] if text is not None else [])]
        try:
            done = subprocess.run(command, cwd=project.path, capture_output=True, text=True, encoding='utf-8',
                                  stdin=subprocess.DEVNULL, timeout=DISPATCH_LIMIT)
        except (OSError, subprocess.TimeoutExpired) as error:
            return self.send(500, {'error': f'metaform dispatch {verb} did not finish: {error}'})
        if done.returncode == 0:
            try:
                return self.send(200, json.loads(done.stdout))
            except ValueError:
                return self.send(200, {'said': done.stdout.strip()})
        said = (done.stderr + done.stdout).strip().splitlines()
        error = next((line[len('Error: '):] for line in said if line.startswith('Error: ')), ' '.join(said))
        found = next((line[len('Next: '):] for line in said if line.startswith('Next: ')), None)
        self.send(400, {'error': error, 'next': found})

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
        # The browser asks again before it uses its copy, so an updated page is the page a person sees.
        headers = {'Content-Security-Policy': policy(body, kind), 'Cache-Control': 'no-cache'}
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


DISPATCH_LIMIT = 120.0  # the one wait for a dispatch verb; its own waits for an agent are at most 30 s each
MEMORY_READS = ('graph', 'orphaned', 'note')  # the memory module's reads the page makes, VIEW-031 and VIEW-034
MEMORY_WRITES = ('create_entities', 'create_relations', 'add_observations', 'delete_entities', 'delete_observations',
                 'delete_relations', 'unjoin')  # the memory commands a person manages the graph with, VIEW-031
ADDITIONS = 'additions'  # the knowledge layer that holds what people add to the map by hand, VIEW-033
ADDED = {'module': 'web', 'workflow': 'add element', 'prompt': 'Written by a person in the web GUI.', 'model': 'none',
         'role': 'user', 'blinded': False}
# The prompt is the user's own, word for word, and the element it speaks of. How the agent answers is what the map
# tool tells it.
VALIDATE = ('Orient yourself only enough to validate the coherence of this element, approve addition or if element '
            'needs additional coherence submit questions w/ recommendations.')


def validation(address: str) -> str:
    return f'{VALIDATE} The element is {address}.'


def started_agent(folder: Path, task: str) -> str | None:
    """Start the agent the `agent_command` setting names, in the project's folder, with the task as its last
    argument, and do not wait for it. Returns what to tell the person when it could not be started."""
    command = str(settings.value('agent_command', folder) or '').strip()
    waits = 'The task waits on the element for an agent to take it.'
    if not command:
        return f'No agent command is set. {waits}'
    parts = shlex.split(command, posix=os.name != 'nt')
    apart: dict[str, Any] = ({'creationflags': getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)} if os.name == 'nt'
                             else {'start_new_session': True})
    try:
        subprocess.Popen([*parts, task], cwd=folder, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, **apart)
    except OSError as error:
        return f'{parts[0]} could not be started: {error.strerror or error}. {waits}'
    return None


def memory_step(step: Any) -> bool:
    """One step of a memory change: a memory command that writes, with its arguments as an object."""
    if not isinstance(step, dict):
        return False
    found = cast(dict[str, Any], step)
    return found.get('command') in MEMORY_WRITES and isinstance(found.get('arguments', {}), dict)


def chosen_layers(given: dict[str, Any], folder: Path) -> list[str]:
    """The layers the page chose, or else the folder's `--layers`."""
    chosen = given.get('layers')
    return [name for name in str(chosen).split(',') if name] if chosen is not None else toggled_for(folder)


def with_modules(given: dict[str, str], found: Any) -> Any:
    """A node's read with what the modules on the project folder's surface add to it, each under its own id, as the
    map module's `map node` reads it, BASE-035; a field the read holds already is never replaced."""
    project = home.project(given.get('project', ''))
    if project is None:
        return found
    folder = Path(project.path)
    added = chassis.node_reads(folder, Node.parse(given.get('target', '')), project=project.project_id,
                               layers=chosen_layers(given, folder) or None)
    if not added:
        return found
    data = cast(dict[str, Any], found.to_dict())
    for module, value in added.items():
        data.setdefault(module, value)
    return data


def module_verb(given: dict[str, Any], module_id: str, name: str, arguments: dict[str, Any]) -> Any:
    """Run one command of a module on the project folder's surface, as a tool call runs it: its arguments checked as
    the command line checks them, a context for the project with the page's layers, on the surface `web`. A module
    that is not on the surface is named with its next step."""
    project = home.project(str(given.get('project', '')))
    if project is None:
        raise StoreError(f'No project {given.get("project", "")} is registered.', 'metaform list projects')
    folder = Path(project.path)
    found = next((one for one in chassis.surface(folder) if one.id == module_id), None)
    verb = next((one for one in found.verbs if one.name == name), None) if found is not None else None
    if verb is None:
        raise Stop(f'{module_id} {name} is not on this project\'s surface.', f'metaform enable {module_id}')
    nouns, switches, _ = chassis.tool_arguments(module_id, verb, arguments, folder=folder)
    switches['layers'] = chosen_layers(given, folder)
    ctx = chassis.context(module_id, folder, project=project.project_id, nouns=nouns, switches=switches,
                          sink=lambda text: None, surface='web')
    return chassis.call(verb.run, ctx)


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
        print(f'{datetime.now(UTC).isoformat(timespec="seconds")} cannot listen at '
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
