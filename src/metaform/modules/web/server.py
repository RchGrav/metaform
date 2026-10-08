"""The web GUI's server process, VIEW-002: the standard library's threading HTTP server, detached from any terminal.

`metaform web` starts it with `python -m metaform.modules.web.server`. Every
request must name the server's own address and port in its Host header, so a
page that rebinds a domain to this machine reads nothing. On a bind address
other than loopback, every request also needs the home's token: in the page
URL as `?t=`, then in a cookie the page load sets, or in the
`X-Metaform-Token` header. The server writes its record to `run/web.json`
once it listens, then says so on the pipe `metaform web` gave it as standard
output, and its loop waits in `select` with no timeout, waking only for a
connection; the stop signal ends the process, QUAL-015. It hears each
`map.changed` published in another process through the base's listener, and
each of its own writes' changes from `events.announce`, and pushes both to
every open page, BASE-053 and VIEW-018.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import queue
import re
import secrets
import signal
import socket
import socketserver
import subprocess
import sys
import threading
import time
import traceback
from collections.abc import Callable
from datetime import UTC, datetime
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, urlsplit

from metaform import events, home, settings
from metaform import module as chassis
from metaform.data import (
    COLUMNS,
    SCHEMA_VERSION,
    TICKETS,
    NewerStore,
    Node,
    Outcome,
    Page,
    Store,
    StoreError,
    WorkRecord,
    plain,
    prompts,
    query_read,
    query_reads,
)
from metaform.finish_xml import xml as map_xml
from metaform.module import Stop
from metaform.outline import markdown as map_markdown

from . import WAIT, WILDCARDS, host_port, loopback, reach, ready_line, run_file, spawn, token

HERE = Path(__file__).parent
STATIC = {'page': HERE / 'page', 'vendor': HERE / 'vendor'}
COOKIE = 'metaform_token'
RESERVED = ('project', 'metaform', 'layers')  # what picks the store and its layers; never a read's own argument
TYPES = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
         '.mjs': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
         '.json': 'application/json', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.md': 'text/plain; charset=utf-8',
         '.txt': 'text/plain; charset=utf-8'}  # fixed, since Windows's registry can give .js a type browsers refuse
PAGE_POLICY = "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'"
IMPORT_MAP = re.compile(rb'<script type="importmap">(.*?)</script>', re.DOTALL)
DISPATCH_CHANGES = frozenset({'work', 'messages', 'map.glyphs', 'map.ticket_settings', 'map.eligible',
                              'map.question_work', 'dispatch.sessions', 'dispatch.questions', 'dispatch.settings'})


def dispatch_change(payload: dict[str, Any]) -> bool:
    """Only selection inputs trigger autostart. Older events without table detail may have changed any input."""
    tables = payload.get('tables')
    if tables == 'dispatch':
        tables = payload.get('dispatch_tables')
    if not isinstance(tables, list) or not tables:
        return True
    if any(not isinstance(table, str) for table in cast(list[Any], tables)):
        return True
    return bool(DISPATCH_CHANGES.intersection(cast(list[str], tables)))


COALESCE = 0.3  # seconds a page's stream holds dispatch-only events to merge them, VIEW-018


def dispatch_only(event: dict[str, Any]) -> bool:
    """An event naming only dispatch tables and no signal: an agent's thread or session changed, never the map."""
    payload = event.get('payload') or {}
    tables = payload.get('tables')
    return event.get('topic') == 'map.changed' and 'signal' not in payload and (
        tables == 'dispatch' or (isinstance(tables, list) and bool(tables)
                                 and all(isinstance(t, str) and t.startswith('dispatch.') for t in tables)))


def coalesce(held: dict[str, Any], event: dict[str, Any]) -> dict[str, Any] | None:
    """`event` merged into `held`, both dispatch-only, or None when they are for another project or metaform, or one
    names `dispatch` and the other a list. The merged event names the union of what each named; one that named no
    detail may have changed any dispatch table, so the merge then names none."""
    a, b = held['payload'], event['payload']
    if any(a.get(key) != b.get(key) for key in ('project', 'base_id')) or type(a['tables']) is not type(b['tables']):
        return None
    payload = dict(a)
    if isinstance(a['tables'], list):
        payload['tables'] = sorted(set(a['tables']) | set(b['tables']))
    elif isinstance(a.get('dispatch_tables'), list) and isinstance(b.get('dispatch_tables'), list):
        payload['dispatch_tables'] = sorted(set(a['dispatch_tables']) | set(b['dispatch_tables']))
    else:
        payload.pop('dispatch_tables', None)
    return {**held, 'payload': payload}


def policy(body: bytes, kind: str) -> str:
    """The Content Security Policy a file is sent with, VIEW-003. A page's import map is an inline script, which a
    browser runs only when the policy names its SHA-256; it is read from the page itself, so the two always agree, and
    no other inline script is allowed."""
    found = IMPORT_MAP.search(body) if kind.startswith('text/html') else None
    if found is None:
        return PAGE_POLICY
    digest = base64.b64encode(hashlib.sha256(found.group(1)).digest()).decode('ascii')
    return f"{PAGE_POLICY}; script-src 'self' 'sha256-{digest}'"


code_print = chassis.code_print


def log(text: str) -> None:
    """One line of `run/web.log`, the server's standard error, stamped with its UTC time, so the log alone says when
    the server started, stopped or failed, and why."""
    print(f'{datetime.now(UTC).isoformat(timespec="seconds")} {text}', file=sys.stderr, flush=True)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = os.name != 'nt'  # on Windows it would let a second server share the port

    def __init__(self, bind: str, port: int, nonce: str) -> None:
        self.address_family = socket.AF_INET6 if ':' in bind else socket.AF_INET
        self.bind, self.nonce = bind, nonce
        self.token = None if loopback(bind) else token()
        self.listeners: set[queue.SimpleQueue[dict[str, Any]]] = set()
        # The project each open page shows, so the page that opens a project runs its agent starter at once.
        self.watching: dict[queue.SimpleQueue[dict[str, Any]], str] = {}
        self.listening = threading.Lock()
        self.dispatch_lock = threading.Lock()
        self.dispatch_pending: set[str] = set()
        self.dispatch_busy = False
        self.dispatch_errors: dict[str, str] = {}  # each project's last automatic-dispatch error, logged once
        self.merge_timers: dict[tuple[str, str], threading.Timer] = {}  # VIEW-044: one per merge waiting for review
        self.code = code_print()
        self.handing = threading.Lock()
        self.stopping, self.handed = threading.Event(), threading.Event()
        self.replacing = self.successor = False
        self.redirecting: list[threading.Thread] = []
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

    def handle_error(self, request: Any, client_address: Any) -> None:
        """A page that went away while it was answered is no fault of the server and is not logged; anything else is,
        with its time and traceback."""
        if isinstance(sys.exc_info()[1], (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
            return
        log(f'Error answering {client_address}:\n{traceback.format_exc().rstrip()}')

    def own_host(self, host: str | None) -> bool:
        """The Host header names this server. On a wildcard bind every name of the machine is its own, so only the
        port is checked there, and the token guards every request."""
        if not host:
            return False
        host = host.strip().lower()
        if self.bind in WILDCARDS:
            return host.rsplit(':', 1)[-1] == str(self.port) and ':' in host
        return host in self.hosts

    def changed(self, payload: dict[str, Any]) -> int:
        """Push one `map.changed` to every open page, VIEW-018 and BASE-053; a change to a project no longer registered,
        such as the removal of one, is not pushed, since a page has nothing of it to read."""
        if home.project(str(payload.get('project', ''))) is None:
            return 0
        if dispatch_change(payload):
            self.schedule_dispatch(str(payload['project']))
        return self.push({'topic': 'map.changed', 'payload': payload})

    def open_projects(self) -> set[str]:
        with self.listening:
            return set(self.watching.values())

    def schedule_dispatch(self, project: str) -> None:
        """Queue a dispatch check on a change, without blocking page reads or starting concurrent batches."""
        with self.dispatch_lock:
            self.dispatch_pending.add(project)
            if self.dispatch_busy:
                return
            self.dispatch_busy = True
        threading.Thread(target=self.dispatch_waiting, daemon=True).start()

    def schedule_merges(self, project: str) -> None:
        """Set one timer for each merge waiting for review, at its deadline, VIEW-044; nothing polls, QUAL-015."""
        ok, data = run_dispatch(project, 'merges', [])
        for row in cast(list[dict[str, Any]], data.get('merges') or []) if ok else []:
            key = (project, str(row['work_id']))
            if key in self.merge_timers:
                continue
            timer = threading.Timer(max(0.0, float(row['deadline']) - time.time()), self.merge_due, key)
            timer.daemon = True
            self.merge_timers[key] = timer
            timer.start()

    def merge_due(self, project: str, work_id: str) -> None:
        """A merge's review time is up with no review: dispatch checks it again and merges it, VIEW-044."""
        self.merge_timers.pop((project, work_id), None)
        run_dispatch(project, 'merge', [work_id])
        found = home.project(project)
        if found is not None:
            for payload in events.announce(Path(found.path), 'web'):
                self.changed(dict(payload))

    def cancel_merge(self, project: str, work_id: str) -> None:
        timer = self.merge_timers.pop((project, work_id), None)
        if timer is not None:
            timer.cancel()

    def dispatch_waiting(self) -> None:
        """Check changed projects in one worker; new changes are coalesced while a batch starts."""
        while True:
            with self.dispatch_lock:
                if not self.dispatch_pending:
                    self.dispatch_busy = False
                    return
                project_id = self.dispatch_pending.pop()
            with chassis.request_scope(fresh=True):
                chassis.refresh_modules()
                project = home.project(project_id)
                if project is None:
                    continue
                self.schedule_merges(project_id)
                try:
                    module_verb({'project': project_id}, 'dispatch', 'autostart', {})
                except StoreError as error:
                    if self.dispatch_errors.get(project_id) != str(error):  # once until it changes, not on every change
                        self.dispatch_errors[project_id] = str(error)
                        log(f'Automatic dispatch for {project_id}: {error}')
                    continue
                except Stop:  # dispatch is disabled for this project
                    continue
                self.dispatch_errors.pop(project_id, None)
                for payload in events.announce(Path(project.path), 'web'):
                    self.changed(dict(payload))

    def push(self, event: dict[str, Any]) -> int:
        """Hand one event to every open page's stream, VIEW-018."""
        with self.listening:
            for waiting in self.listeners:
                waiting.put(event)
            return len(self.listeners)

    def run(self) -> None:
        """Serve until `shutdown` or a hand-over ends the loop. Each turn waits for one connection with no timeout and
        then runs `service_actions`, as the standard library's loop does, QUAL-015. A hand-over closes the listener
        first, so the replacement can take the port, and lets the requests waiting on it answer before this returns."""
        with self:
            while not self.stopping.is_set():
                self.handle_request()
                self.service_actions()
        if not self.replacing:
            return
        try:
            process = spawn(self.bind, self.port, secrets.token_hex(8))
            self.successor = bool(ready_line(process))
            log(f'Handed over to process {process.pid}' if self.successor else
                f'Hand-over failed: process {process.pid} did not say it listens')
            if process.stdout is not None:
                process.stdout.close()
        finally:
            self.handed.set()
            with self.handing:
                waiting = list(self.redirecting)
            for thread in waiting:
                thread.join(WAIT)

    def shutdown(self) -> None:
        """End `run`'s loop, woken by a connection of its own, since nothing else wakes it."""
        self.stopping.set()
        socket.create_connection((reach(self.bind), self.port), timeout=WAIT).close()

    def hand_over(self) -> bool:
        """Whether a replacement from the code on disk now answers on this port, for a store newer than this server's
        code, STORE-029. Only when that code changed since this server started: with it unchanged the store is from a
        newer release, which a replacement could not read either, so the error stands and nothing loops. The first
        request starts the hand-over; every request meanwhile waits for it and is answered by the same outcome."""
        with self.handing:
            if not self.replacing:
                if self.stopping.is_set() or code_print() == self.code:
                    return False
                self.replacing = True
                self.shutdown()
            self.redirecting.append(threading.current_thread())
        self.handed.wait()
        return self.successor

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
        try:
            with chassis.request_scope(fresh=True):
                chassis.refresh_modules()
                self.route(method)
        except NewerStore as error:  # the base database, read before any handler's own error answer
            self.refuse(error, 404)

    def route(self, method: str) -> None:
        if not self.gui.own_host(self.headers.get('Host')):
            return self.send(403, {'error': "This request is not for the web GUI's own address."})
        url = urlsplit(self.path)
        query = parse_qs(url.query, keep_blank_values=True)
        given = self.given_token(query)
        if self.gui.token is not None and not (given and hmac.compare_digest(given, self.gui.token)):
            return self.send(403, {'error': 'This request needs the token that metaform web prints.'})
        if method == 'POST':
            return self.write(url.path)
        if url.path == '/api/events':
            return self.events(query.get('project', [''])[-1])
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
        if url.path == '/api/ignore':
            return self.read_ignore(query.get('project', [''])[-1])
        if url.path == '/api/dispatch-sessions':
            return self.dispatch_sessions({key: values[-1] for key, values in query.items() if key != 't'})
        if url.path == '/api/dispatch-prompts':
            return self.dispatch_prompts(query.get('project', [''])[-1])
        if url.path == '/api/dispatch-autostart':
            return self.dispatch_autostart({'project': query.get('project', [''])[-1]})
        if url.path == '/api/lookup':
            return self.lookup(query.get('project', [''])[-1], query.get('ref', [''])[-1])
        if url.path == '/api/merges':
            return self.list_merges({key: values[-1] for key, values in query.items() if key != 't'})
        if url.path == '/api/markdown':
            return self.markdown({key: values[-1] for key, values in query.items() if key != 't'})
        if url.path == '/api/xml':
            return self.xml({key: values[-1] for key, values in query.items() if key != 't'})
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
                return self.refuse(error, 404)
        if name == 'workflows':
            try:
                # List the active folder's callable logic, the same context an ACP worker starts in.
                found = module_verb({'project': given.get('project', '')}, 'workflow', 'list', {})
            except StoreError as error:
                return self.refuse(error, 404)
            except Stop:
                return self.send(200, {'enabled': False, 'workflows': []})
            return self.send(200, {'enabled': True, 'workflows': plain(found)})
        if name not in query_reads():
            return self.send(404, {'error': f'No read {name}.'})
        try:
            store = opened(given)
            found = query_read(store, name, {key: value for key, value in given.items() if key not in RESERVED})
        except (Stop, StoreError) as error:
            return self.refuse(error, 404 if isinstance(error, StoreError) else 400)
        if found is None:
            return self.send(404, {'error': f'Nothing for {name} here, in these layers.'})
        if name == 'node':
            found = with_modules(given, found)
        if name == 'work':
            found = with_glyphs(given, found)
        self.reply(200, chassis.result_json(found).encode('utf-8'), 'application/json', {'Cache-Control': 'no-store'})

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
            return self.refuse(error, 404 if isinstance(error, StoreError) else 400)
        self.reply(200, chassis.result_json(found).encode('utf-8'), 'application/json', {'Cache-Control': 'no-store'})

    def markdown(self, given: dict[str, str]) -> None:
        """The map as the common base's Markdown document, MAP-052, for the page's export,
        VIEW-024, with the page's layers or the folder's."""
        try:
            text = map_markdown(opened(given), given.get('address') or None)
        except (Stop, StoreError) as error:
            return self.refuse(error, 404 if isinstance(error, StoreError) else 400)
        self.reply(200, text.encode('utf-8'), 'text/markdown; charset=utf-8', {'Cache-Control': 'no-store'})

    def xml(self, given: dict[str, str]) -> None:
        """The map as the common base's XML document, MAP-059, for the page's export menu,
        VIEW-024, with the page's layers or the folder's."""
        try:
            text = map_xml(opened(given), given.get('address') or None)
        except (Stop, StoreError) as error:
            return self.refuse(error, 404 if isinstance(error, StoreError) else 400)
        self.reply(200, text.encode('utf-8'), 'application/xml; charset=utf-8', {'Cache-Control': 'no-store'})

    def events(self, project: str = '') -> None:
        """One open page's stream of what modules publish, held open, and the project the page shows. Its thread sleeps until an event comes and writes it;
        nothing polls, QUAL-015. Events naming only dispatch tables are held up to `COALESCE` seconds and merged into
        one, so a burst of agent lines wakes the page once; any other event writes what is held and then itself at
        once. A page that has gone is dropped at the next event."""
        waiting: queue.SimpleQueue[dict[str, Any]] = queue.SimpleQueue()
        with self.gui.listening:
            self.gui.listeners.add(waiting)
            if project:
                self.gui.watching[waiting] = project
        if project:
            self.gui.schedule_dispatch(project)  # the page opened the project: its agent starter runs now
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
            def send(event: dict[str, Any]) -> None:
                self.wfile.write(b'data: ' + json.dumps(event).encode('utf-8') + b'\n\n')
                self.wfile.flush()

            held: dict[str, Any] | None = None
            due = 0.0
            while True:
                try:  # asleep until an event comes or, while one is held, until it is due: one bounded wait
                    event = waiting.get() if held is None else waiting.get(timeout=max(0.0, due - time.monotonic()))
                except queue.Empty:
                    send(cast(dict[str, Any], held))
                    held = None
                    continue
                if dispatch_only(event):
                    merged = coalesce(held, event) if held is not None else None
                    if merged is not None:
                        held = merged
                        continue
                    if held is not None:
                        send(held)
                    held, due = event, time.monotonic() + COALESCE
                    continue
                if held is not None:
                    send(held)
                    held = None
                send(event)
        except OSError:
            pass
        finally:
            with self.gui.listening:
                self.gui.listeners.discard(waiting)
                self.gui.watching.pop(waiting, None)

    def write(self, path: str) -> None:
        """One of the eighteen writes of VIEW-011, from the GUI's own page only: the same Origin, and a JSON body."""
        origin = self.headers.get('Origin')
        if origin is None or origin.lower() != f'http://{self.headers.get("Host", "")}'.lower():
            return self.send(403, {'error': "A write is taken only from the web GUI's own page."})
        if (self.headers.get('Content-Type') or '').split(';')[0].strip().lower() != 'application/json':
            return self.send(415, {'error': 'A write takes a JSON body.'})
        writes = {'/api/apply-layers': self.apply_layers,
                  '/api/save-prompt': self.save_prompt, '/api/clear-project': self.clear_project, '/api/remove-project': self.remove_project,
                  '/api/answer': self.answer_question, '/api/reopen': self.reopen_question, '/api/read': self.read_note, '/api/task': self.give_work,
                  '/api/element': self.add_part, '/api/restore': self.restore,
                  '/api/note': self.add_note, '/api/move': self.move_ticket, '/api/distribute': self.distribute_tickets,
                  '/api/ticket': self.set_ticket, '/api/eligible': self.set_eligible, '/api/merge-review': self.review_merge,
                  '/api/merge-assist': self.assist_merge, '/api/dispatch-reset': self.reset_agents,
                  '/api/system-chat': self.system_chat, '/api/attach': self.attach, '/api/talk': self.talk,
                  '/api/activate-base': self.activate_base,
                  '/api/remove-base': self.remove_base, '/api/ignore': self.write_ignore,
                  '/api/memory': self.write_memory,
                  '/api/dispatch-start': self.dispatch_start, '/api/dispatch-message': self.dispatch_message,
                  '/api/dispatch-stop': self.dispatch_stop, '/api/dispatch-prompts': self.set_dispatch_prompts,
                  '/api/dispatch-autostart': self.set_dispatch_autostart}
        if path not in writes:
            return self.send(404, {'error': f'No such write: {path}.'})
        try:
            body: Any = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)) or b'null')
        except ValueError:
            return self.send(400, {'error': 'The body is not JSON.'})
        given = cast(dict[str, Any], body) if isinstance(body, dict) else {}
        try:
            writes[path](given)
        finally:  # announced as a command's write is: map.changed on the module event bus, VIEW-018 and BASE-010,
            # and pushed to every open page from what was announced; a change made in another process reaches this
            # server through the base's listener instead, BASE-053. A module enabled or disabled since this server
            # started is loaded or dropped first.
            chassis.refresh_modules()
            project = home.project(str(given.get('project', '')))
            for payload in events.announce(Path(project.path) if project is not None else home.home(), 'web'):
                self.gui.changed(dict(payload))

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
            return self.refuse(error, 400)
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
            return self.refuse(error, 400)
        self.send(200, {'project': project.project_id, 'folder': str(folder), 'layers': assigned.new,
                        'notices': [{'where': 'layers', 'message': notice} for notice in assigned.notices]})

    def activate_base(self, given: dict[str, Any]) -> None:
        """Make a base the project's active one, as `metaform activate base <name>` does, STORE-041."""
        project = home.project(str(given.get('project', '')))
        name = given.get('name')
        if project is None or not isinstance(name, str) or not name:
            return self.send(400, {'error': 'Activate takes a registered project and a base name.'})
        try:
            made = home.activate_base(project.project_id, name)
        except StoreError as error:
            return self.refuse(error, 404)
        self.send(200, plain(made))

    def remove_base(self, given: dict[str, Any]) -> None:
        """Take one base out of the project, as `metaform map remove-base <name> --confirm` does, only with `confirm`
        true; a copy of its store is kept, and the active base is refused, STORE-041."""
        project = home.project(str(given.get('project', '')))
        name = given.get('name')
        if project is None or not isinstance(name, str) or not name:
            return self.send(400, {'error': 'Remove takes a registered project and a base name.'})
        if given.get('confirm') is not True:
            return self.send(400, {'error': f'Removing {name} removes its store; a copy is kept under '
                                            'backups/remove-base. The active base is refused.',
                                   'next': 'If you are sure: send confirm true'})
        try:
            made = home.remove_base(project.project_id, name)
        except StoreError as error:
            return self.refuse(error, 400)
        self.send(200, plain(made))

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
            store = opened({'project': str(given.get('project', '')), 'base': str(given.get('base') or '')})
            with store.atomic():
                asked = [found for found in store.messages(None, 'question', True, limit=0).results
                         if found.id == record]
                if not asked:
                    return self.send(400, {'error': 'This is not an open question.'})
                done = store.reply(record, answer.strip())
        except (Stop, StoreError) as error:
            return self.refuse(error, 400)
        self.send(200, plain(done))

    def reopen_question(self, given: dict[str, Any]) -> None:
        """Reopen a question the person answered by mistake, so it waits again with its suggestions, MAP-050 and
        VIEW-021. Only an answered question is reopened from the page."""
        record = str(given.get('id', ''))
        try:
            store = opened({'project': str(given.get('project', '')), 'base': str(given.get('base') or '')})
            with store.atomic():
                answered = [found for found in store.messages(None, 'question', False, limit=0).results
                            if found.id == record]
                if not answered:
                    return self.send(400, {'error': 'This is not an answered question.'})
                done = store.reopen(record)
        except (Stop, StoreError) as error:
            return self.refuse(error, 400)
        self.send(200, plain(done))

    def read_note(self, given: dict[str, Any]) -> None:
        """Mark a note read, which ends its record, VIEW-030. Only an unread note is read from the page."""
        record = str(given.get('id', ''))
        try:
            store = opened({'project': str(given.get('project', '')), 'base': str(given.get('base') or '')})
            with store.atomic():
                unread = [found for found in store.messages(None, 'message', True, limit=0).results
                          if found.id == record]
                if not unread:
                    return self.send(400, {'error': 'This is not an unread message.'})
                done = store.reply(record)
        except (Stop, StoreError) as error:
            return self.refuse(error, 400)
        self.send(200, plain(done))

    def give_work(self, given: dict[str, Any]) -> None:
        """Put a task a person wrote on the node it is assigned to, the first given, as one ticket that links the other
        nodes for reference, VIEW-032, VIEW-035 and MAP-048."""
        text, nodes, condition = given.get('task'), given.get('nodes'), given.get('condition')
        if not isinstance(text, str) or not text.strip():
            return self.send(400, {'error': 'A task says what is to be done.'})
        if not isinstance(nodes, list) or not nodes or not all(isinstance(node, str) for node in cast(list[Any], nodes)):
            return self.send(400, {'error': 'A task is given at one node or more.'})
        if condition and condition not in TICKETS:  # none: a task on a part that exists, MAP-046
            return self.send(400, {'error': 'The part is missing, broken, flawed, could be better, or none of these.'})
        try:
            store = opened({'project': str(given.get('project', '')), 'base': str(given.get('base') or '')})
            with store.atomic():
                targets = [Node.parse(node) for node in cast(list[str], nodes)]
                written = [store.add_work(targets[0], condition, task=text.strip(), held=bool(given.get('held')),
                                          links=targets[1:])]
            kept = {key: given[key] for key in ('agent', 'hold', 'eligible') if given.get(key) is not None}
            if kept:  # the ticket's preferred agent and the person's hold, kept by the map module
                module_verb(given, 'map', 'work', {'op': 'edit', 'id': written[0].id, **kept}, chosen=True)
        except (Stop, StoreError) as error:
            return self.refuse(error, 400)
        self.send(200, {'results': plain(written)})

    def set_eligible(self, given: dict[str, Any]) -> None:
        """The person's choice of agents eligible for a ticket, owned by map, MAP-058."""
        work_id, agents = given.get('work_id'), given.get('agents')
        if not isinstance(work_id, str) or not work_id:
            return self.send(400, {'error': 'An eligibility change names the ticket.'})
        if not isinstance(agents, list) or not all(isinstance(agent, str) for agent in cast(list[Any], agents)):
            return self.send(400, {'error': 'Eligible agents is a list of agent names, or an empty list for Any agent.'})
        try:
            edited = plain(module_verb(given, 'map', 'work', {'op': 'edit', 'id': work_id, 'eligible': agents}, chosen=True))
        except (Stop, StoreError) as error:
            return self.refuse(error, 400)
        self.send(200, {'results': [edited]})

    def set_ticket(self, given: dict[str, Any]) -> None:
        """Change a ticket's preferred agent, the person's hold or its glyph, at any time. When the agent changes while
        another agent works the ticket, that agent is stopped and the chosen one started on it."""
        work_id = given.get('work_id')
        if not isinstance(work_id, str) or not work_id:
            return self.send(400, {'error': 'A ticket change names the ticket.'})
        changes = {key: given[key] for key in ('agent', 'hold', 'glyph') if key in given}
        if not changes:
            return self.send(400, {'error': 'A ticket change gives an agent, a hold or a glyph.'})
        try:
            edited = plain(module_verb(given, 'map', 'work', {'op': 'edit', 'id': work_id, **changes}, chosen=True))
        except (Stop, StoreError) as error:
            return self.refuse(error, 400)
        agent = changes.get('agent')
        if agent:
            running, data = self.dispatch_call(given, 'sessions', [f'id={work_id}', 'thread=false'])
            rows: list[dict[str, Any]] = cast(list[dict[str, Any]], data.get('sessions') or []) if running else []
            live = [row for row in rows if row.get('state') == 'running']
            if live and live[-1].get('agent') != agent:
                # The stopped runner releases the ticket and announces it; the agent starter, run on every change,
                # then starts the agent the ticket now prefers. Nothing here waits for it, QUAL-015.
                self.dispatch_call(given, 'stop', [work_id])
        self.send(200, {'results': [edited]})

    def dispatch_call(self, given: dict[str, Any], verb: str, nouns: list[str]) -> tuple[bool, dict[str, Any]]:
        """One dispatch verb run as the command line runs it, for a write that goes on after it."""
        return run_dispatch(str(given.get('project', '')), verb, nouns)

    def list_merges(self, given: dict[str, str]) -> None:
        """The merges waiting for review, VIEW-044, for the page's Review notice."""
        ok, data = run_dispatch(str(given.get('project', '')), 'merges', [])
        self.send(200, data if ok else {'merges': []})

    def review_merge(self, given: dict[str, Any]) -> None:
        """The person clicked Review: the merge is theirs and its countdown is cancelled for good, VIEW-044."""
        work_id, project = given.get('work_id'), str(given.get('project', ''))
        if not isinstance(work_id, str) or not work_id:
            return self.send(400, {'error': 'Review names the ticket whose merge waits.'})
        ok, data = run_dispatch(project, 'review', [work_id])
        self.gui.cancel_merge(project, work_id)
        if not ok:
            return self.send(400, {'error': f'No merge of work {work_id} is waiting for review.'})
        self.send(200, data)

    def reset_agents(self, given: dict[str, Any]) -> None:
        """Reset agents from the Administration menu: `metaform dispatch reset` in the project's folder."""
        self.dispatched(given, 'reset', [])

    def assist_merge(self, given: dict[str, Any]) -> None:
        """Yes to agent assistance: an agent starts in the merge's worktree to prepare its code for review, VIEW-044."""
        work_id = given.get('work_id')
        if not isinstance(work_id, str) or not work_id:
            return self.send(400, {'error': 'Assistance names the ticket whose merge is under review.'})
        self.dispatched(given, 'prep', [work_id])

    def system_chat(self, given: dict[str, Any]) -> None:
        """Call in the chat dock: the person's system agent starts, or the running one is reused."""
        self.dispatched(given, 'system', [])

    def lookup(self, project_id: str, ref: str) -> None:
        """What a reference in text the person reads stands for, VIEW-042: a spec record, a ticket or a message by its
        id or a prefix, or a file in the project folder. Nothing found is an answer too, with its plain reason, so a
        page asking about every reference it draws logs no failed request."""
        project = home.project(project_id)
        if project is None:
            return self.send(200, {'kind': None, 'reason': f'No project {project_id} is registered.'})
        try:
            found = referenced(project, ref)
        except (Stop, StoreError) as error:
            return self.send(200, {'kind': None, 'reason': str(error)})
        self.send(200, found or {'kind': None, 'reason': f'{ref} names nothing in this project.'})

    def talk(self, given: dict[str, Any]) -> None:
        """Chat on anything the page shows: a ticket, open or done, a node, a question or an agent's session."""
        nouns = [f'{key}={given[key]}' for key in ('id', 'node', 'question', 'session', 'agent')
                 if isinstance(given.get(key), str) and given[key]]
        if not nouns:
            return self.send(400, {'error': 'Chat names what it is about.'})
        self.dispatched(given, 'talk', nouns)

    def attach(self, given: dict[str, Any]) -> None:
        """A file attached in the chat dock, kept in the project's own folder under the Metaform home, never in the
        person's source tree; the answer is its full path, which the message then gives the agent."""
        folder = home.project_folder(str(given.get('project', '')))
        name, data = given.get('name'), given.get('data')
        if folder is None:
            return self.send(404, {'error': f'No project {given.get("project", "")} is registered.'})
        if not isinstance(name, str) or not isinstance(data, str):
            return self.send(400, {'error': 'An attachment has a name and its contents.'})
        try:
            raw = base64.b64decode(data, validate=True)
        except ValueError:
            return self.send(400, {'error': 'The attachment did not arrive whole.'})
        if len(raw) > ATTACH_LIMIT:
            return self.send(413, {'error': f'An attachment is at most {ATTACH_LIMIT // 1024 // 1024} MB.'})
        safe = re.sub(r'[^A-Za-z0-9._-]', '_', os.path.basename(name)).lstrip('.') or 'file'
        target = folder / 'attachments' / f'{datetime.now(UTC):%Y%m%d-%H%M%S}-{secrets.token_hex(2)}-{safe}'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        self.send(200, {'path': str(target)})

    def move_ticket(self, given: dict[str, Any]) -> None:
        """Put a ticket in a column of the board and at a place in it, VIEW-037 and STORE-042."""
        work_id, column, position = given.get('work_id'), given.get('column'), given.get('position')
        if not isinstance(work_id, str) or column not in COLUMNS:
            return self.send(400, {'error': 'A move names a ticket and a column: backlog, todo, doing or done.'})
        if position is not None and (not isinstance(position, int) or isinstance(position, bool)):
            return self.send(400, {'error': 'A place in a column is a whole number.'})
        try:
            store = opened({'project': str(given.get('project', '')), 'base': str(given.get('base') or '')})
            moved = store.move_work(work_id, column, position, given.get('by'))
        except (Stop, StoreError) as error:
            return self.refuse(error, 400)
        self.send(200, {'results': plain([moved])})

    def distribute_tickets(self, given: dict[str, Any]) -> None:
        """Give the tickets not done and not taken the glyphs of N agents, in turn, VIEW-040, with the map module's
        `map work op=distribute`, which keeps them in its own table, STORE-045, and refuses an N it has no glyphs
        for."""
        agents = given.get('agents')
        if not isinstance(agents, int) or isinstance(agents, bool):
            return self.send(400, {'error': 'Work is distributed over a whole number of agents.'})
        try:
            given_out = module_verb(given, 'map', 'work', {'op': 'distribute', 'agents': agents}, chosen=True)
        except (Stop, StoreError) as error:
            return self.refuse(error, 400)
        self.reply(200, chassis.result_json(given_out).encode('utf-8'), 'application/json', {'Cache-Control': 'no-store'})

    def add_part(self, given: dict[str, Any]) -> None:
        """Add an element a person describes and join it to a node, in the layer of what people add by hand, and
        make its validation ticket when asked to, VIEW-033. The page starts that ticket through ACP dispatch. The
        element is on the map at once, as a part not built, with the validation as its open task."""
        address, anchor = given.get('address'), given.get('node')
        if not isinstance(address, str) or not address.strip():
            return self.send(400, {'error': 'An element has an address.'})
        if not isinstance(anchor, str) or given.get('receives') not in ('node', 'new'):
            return self.send(400, {'error': 'An element is joined to a node, and one of the two holds the purpose.'})
        try:
            store = opened({'project': str(given.get('project', '')), 'base': str(given.get('base') or '')})
            with store.atomic():
                store.layer(ADDITIONS, 'web', 'What people added to the map by hand.', mutable=True, hideable=True,
                            provenance=ADDED, ready=True)
                made = store.add_element(ADDITIONS, address.strip(), name_length=given.get('name_length') or None,
                                         role=given.get('role') or None, name=given.get('name') or None)
                if isinstance(made, Outcome):
                    return self.send(400, {'error': 'The element was not written.', 'notices': plain(made.notices)})
                held = Node.parse(anchor).id
                receiver, provider = (held, made.id) if given['receives'] == 'node' else (made.id, held)
                joined = store.add_join(ADDITIONS, receiver, provider, purpose=given.get('purpose') or None,
                                        ef=given.get('ef') or None)
                work = store.add_work(Node('element', made.id), 'missing', note='Added by hand in the web GUI.')
                if given.get('validate') is True:
                    work = store.edit_work(work.id, {'task': validation(made.address)})
        except (Stop, StoreError) as error:
            return self.refuse(error, 400)
        self.send(200, {'element': plain(made), 'join': plain(joined), 'work': plain(work)})

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
            return self.refuse(error, 400)
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
            return self.refuse(error, 400)
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

    def dispatch_autostart(self, given: dict[str, Any]) -> None:
        """Read automatic dispatch settings in the registered project's folder, VIEW-042."""
        project = home.project(str(given.get('project', '')))
        if project is None:
            return self.send(404, {'error': f'No project {given.get("project", "")} is registered.',
                                   'next': 'metaform list projects'})
        folder = Path(project.path)
        chassis.refresh_modules()
        if not any(module.id == 'dispatch' for module in chassis.surface(folder)):
            return self.send(200, {'value': False, 'available': False})
        self.send(200, {name: settings.value(key, folder) for name, key in
                        (('value', 'dispatch_autostart'), ('agent', 'dispatch_agent'), ('agents', 'dispatch_agents'))})

    def set_dispatch_autostart(self, given: dict[str, Any]) -> None:
        """Save automatic dispatch settings and start waiting work when enabled, VIEW-042."""
        project = home.project(str(given.get('project', '')))
        if project is None:
            return self.send(404, {'error': f'No project {given.get("project", "")} is registered.',
                                   'next': 'metaform list projects'})
        folder = Path(project.path)
        chassis.refresh_modules()
        if not any(module.id == 'dispatch' for module in chassis.surface(folder)):
            return self.send(400, {'error': 'The dispatch module is not enabled.', 'next': 'metaform enable dispatch'})
        values = {key: given[name] for name, key in
                  (('value', 'dispatch_autostart'), ('agent', 'dispatch_agent'), ('agents', 'dispatch_agents'))
                  if name in given}
        if 'value' in given and not isinstance(given['value'], bool):
            return self.send(400, {'error': 'Autostart is checked or unchecked.'})
        if 'agents' in given and (not isinstance(given['agents'], int) or isinstance(given['agents'], bool)):
            return self.send(400, {'error': 'The number of agents is a whole number.'})
        try:
            for key, value in values.items():
                settings.checked(key, value, folder, typed=True)
            for key, value in values.items():
                settings.put(key, value, folder)
        except (settings.SettingError, Stop) as error:
            return self.refuse(error, 400)
        self.gui.schedule_dispatch(project.project_id)
        self.dispatch_autostart(given)

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

    def dispatch_sessions(self, given: dict[str, str]) -> None:
        """The agent sessions and their threads, from the dispatch module's own tables, VIEW-039 and VIEW-036. With
        dispatch not enabled there are none."""
        try:
            nouns: dict[str, Any] = {'id': given['id']} if given.get('id') else {}
            if given.get('thread') == 'false':
                nouns['thread'] = False
            found = module_verb(given, 'dispatch', 'sessions', nouns)
        except Stop:
            return self.send(200, {'sessions': [], 'lines': []})
        except StoreError as error:  # the project is gone or its store cannot be read: said, as every other read says it
            return self.refuse(error, 404)
        self.reply(200, chassis.result_json(found).encode('utf-8'), 'application/json', {'Cache-Control': 'no-store'})

    def dispatch_prompts(self, project_id: str) -> None:
        """How agents' permission prompts are answered, as the settings hold it, with its choices, VIEW-039: read from
        `metaform config` in the project's folder, so dispatch enabled after this server started is found."""
        project = home.project(project_id)
        if project is None:
            return self.send(404, {'error': f'No project {project_id} is registered.', 'next': 'metaform list projects'})
        done = subprocess.run([sys.executable, '-m', 'metaform', 'config', '--json'], cwd=project.path,
                              capture_output=True, text=True, encoding='utf-8', stdin=subprocess.DEVNULL,
                              timeout=DISPATCH_LIMIT, check=False)
        try:
            found = next((entry for entry in json.loads(done.stdout) if entry.get('key') == 'dispatch_prompts'), None)
        except ValueError:
            found = None
        if found is None:
            return self.send(400, {'error': 'Agent prompts are a setting of the dispatch module, which is not enabled.',
                                   'next': 'metaform enable dispatch'})
        self.send(200, {'value': found['value'], 'choices': found.get('choices', [])})

    def set_dispatch_prompts(self, given: dict[str, Any]) -> None:
        """Set how agents' permission prompts are answered, as `metaform set --dispatch-prompts` sets it, so the choice
        is kept in the settings and every agent reads it at its next prompt, VIEW-039 and BASE-052."""
        project, value = home.project(str(given.get('project', ''))), given.get('value')
        if project is None:
            return self.send(404, {'error': f'No project {given.get("project", "")} is registered.',
                                   'next': 'metaform list projects'})
        if not isinstance(value, str) or not value:
            return self.send(400, {'error': 'Agent prompts are set to one of their choices.'})
        done = subprocess.run([sys.executable, '-m', 'metaform', 'set', f'--dispatch-prompts={value}'], cwd=project.path,
                              capture_output=True, text=True, encoding='utf-8', stdin=subprocess.DEVNULL,
                              timeout=DISPATCH_LIMIT, check=False)
        if done.returncode == 0:
            return self.send(200, {'value': value})
        said = (done.stderr + done.stdout).strip().splitlines()
        self.send(400, {'error': next((line[len('Error: '):] for line in said if line.startswith('Error: ')), ' '.join(said)),
                        'next': next((line[len('Next: '):] for line in said if line.startswith('Next: ')), None)})

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
                                  stdin=subprocess.DEVNULL, timeout=DISPATCH_LIMIT, check=False)
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

    def read_ignore(self, project: str) -> None:
        """The intake's ignore list, `.metaform/ignore.txt` in the project, as the person edits it."""
        found = home.project(project)
        if found is None:
            return self.send(404, {'error': f'No project {project} is registered.', 'next': 'metaform list projects'})
        path = Path(found.path) / home.IGNORE_FILE
        try:
            text = path.read_text(encoding='utf-8')
        except OSError:
            text = ''
        self.send(200, {'file': home.IGNORE_FILE, 'text': text, 'patterns': home.ignore_patterns(found.path)})

    def write_ignore(self, given: dict[str, Any]) -> None:
        """Save the ignore list as typed; the intake reads it on its next prompt."""
        found = home.project(str(given.get('project', '')))
        if found is None:
            return self.send(404, {'error': f'No project {given.get("project", "")} is registered.',
                                   'next': 'metaform list projects'})
        text = given.get('text')
        if not isinstance(text, str):
            return self.send(400, {'error': 'The ignore list is text, one pattern per line.'})
        path = Path(found.path) / home.IGNORE_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text if text.endswith('\n') or not text else text + '\n', encoding='utf-8')
        self.send(200, {'file': home.IGNORE_FILE, 'patterns': home.ignore_patterns(found.path)})

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

    def refuse(self, error: Exception, status: int) -> None:
        """Answer with the error and its next step; or, for a store newer than this server's code once the code on
        disk has changed, with a 307 to the same address, where the replacement started from that code answers."""
        if isinstance(error, NewerStore) and self.gui.hand_over():
            self.close_connection = True  # the browser asks again on a new connection, so it reaches the replacement
            return self.reply(307, b'', 'text/plain', {'Location': self.path, 'Connection': 'close',
                                                       'Cache-Control': 'no-store'})
        self.send(status, {'error': str(error), 'next': getattr(error, 'next_step', None)})

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
ATTACH_LIMIT = 25 * 1024 * 1024  # the largest file the chat dock takes
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


def memory_step(step: Any) -> bool:
    """One step of a memory change: a memory command that writes, with its arguments as an object."""
    if not isinstance(step, dict):
        return False
    found = cast(dict[str, Any], step)
    return found.get('command') in MEMORY_WRITES and isinstance(found.get('arguments', {}), dict)


def chosen_layers(given: dict[str, Any], folder: Path) -> list[str]:
    """The layers the page chose, or else the folder's `--layers`."""
    chosen = given.get('layers')
    return [name for name in str(chosen).split(',') if name] if chosen is not None else settings.toggled_layers(folder)


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


def with_glyphs(given: dict[str, str], found: Any) -> Any:
    """A work read's records, each with what the map module keeps on it under `map`, its glyph, its preferred agent,
    eligible agents and whether the person holds it, as `map work` shows it, VIEW-040, MAP-058 and BASE-035. Its tables, STORE-045,
    are read once each: running `map work` over every ticket again only to add these cost more than the work read
    itself, and the page reads work on every ticket change. With map not on the surface the records are returned as they
    are.
    A field a record holds already is never replaced."""
    if not isinstance(found, Page):
        return found
    page = cast(Page[WorkRecord], found)
    project = home.project(given.get('project', ''))
    if project is None:
        return page
    chassis.refresh_modules()  # map enabled or disabled since this server started, as module_verb follows it
    if not any(one.id == 'map' for one in chassis.surface(Path(project.path))):
        return page
    try:
        store = Store(project.project_id, base=given.get('base') or None, module='map')
        with store.tables(write=False) as tx:
            held: dict[str, dict[str, Any]] = {
                str(row['work_id']): {'glyph': row['glyph']} for row in tx.rows('glyphs', limit=0).results}
            for row in tx.rows('ticket_settings', limit=0).results:
                held.setdefault(str(row['work_id']), {}).update(agent=row['agent'], hold=bool(row['hold']))
            for row in tx.rows('eligible', limit=0).results:
                held.setdefault(str(row['work_id']), {})['eligible'] = row['agents']
    except (Stop, StoreError):
        return page
    if not held:
        return page
    shown: list[dict[str, Any]] = []
    for record in page.results:
        data = record.to_dict()
        if record.id in held:
            data.setdefault('map', held[record.id])
        shown.append(data)
    return {**page.to_dict(), 'results': shown}


SPEC_CODE = re.compile(r'^(?:[A-Z]{2,6}-\d{3}|D\d{2,4})$')  # a record's code in specifications/*.md: VIEW-042, D120
HEX_REF = re.compile(r'^[0-9a-f]{8,32}$')  # a ticket's or a message's id, whole or its first characters
FILE_LINES = 80  # how much of a file a reference shows


def spec_record(folder: Path, code: str) -> dict[str, Any] | None:
    """A record of the project's specifications by its code: its `### CODE` section, or the paragraph that opens with
    `**CODE.`, whole, with the file it is in. Rich's folder, rich/, is never read for this."""
    for path in sorted((folder / 'specifications').glob('*.md')):
        lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
        for at, line in enumerate(lines):
            heading = re.match(rf'^(#{{2,4}})\s+{re.escape(code)}\b', line)
            if heading or line.startswith(f'**{code}.'):
                end = at + 1
                while end < len(lines) and not (lines[end].startswith('#') if heading else not lines[end].strip()):
                    end += 1
                bold = None if heading else re.match(r'^\*\*(.+?)\*\*\s*(.*)$', line)
                title = line.lstrip('# ') if heading else bold.group(1) if bold else line
                body = ([bold.group(2)] if bold else []) + lines[at + 1:end]
                return {'kind': 'spec', 'title': title, 'text': '\n'.join(body).strip(),
                        'file': str(path.relative_to(folder))}
    return None


def referenced(project: Any, ref: str) -> dict[str, Any] | None:
    """What one reference stands for in a project, or None."""
    folder = Path(project.path)
    if SPEC_CODE.match(ref):
        return spec_record(folder, ref)
    if HEX_REF.match(ref):
        store = Store(project.project_id)
        tickets = [record for record in store.work(limit=0).results if record.id.startswith(ref)]
        if len(tickets) == 1:
            record = tickets[0]
            return {'kind': 'ticket', 'id': record.id, 'title': record.task or record.note or record.id,
                    'task': record.task, 'note': record.note, 'condition': record.condition, 'column': record.column,
                    'done': record.done, 'resolution': record.resolution, 'address': record.address}
        said = [message for kind in ('question', 'message')
                for message in store.messages(None, kind, None, limit=0).results if message.id.startswith(ref)]
        if len(said) == 1:
            message = said[0]
            return {'kind': 'message', 'id': message.id, 'type': message.kind, 'title': message.text or '',
                    'text': message.text, 'choices': list(message.suggestions), 'answer': message.answer,
                    'closed': message.closed, 'address': message.address}
        return None
    if '/' not in ref or ref.startswith('rich/'):
        return None
    root = folder.resolve()
    path = (root / ref).resolve()
    if not path.is_relative_to(root) or path.is_relative_to(root / 'rich') or not path.is_file():
        return None
    with path.open('rb') as handle:
        head = handle.read(256 * 1024)
    if b'\0' in head:
        return {'kind': 'file', 'title': ref, 'text': 'This file is not text.', 'lines': 0}
    shown = head.decode('utf-8', errors='replace').splitlines()[:FILE_LINES]
    return {'kind': 'file', 'title': ref, 'text': '\n'.join(shown), 'lines': len(shown)}


def run_dispatch(project_id: str, verb: str, nouns: list[str]) -> tuple[bool, dict[str, Any]]:
    """One dispatch verb run as the command line runs it, in the project's folder: whether it succeeded, and its
    result."""
    project = home.project(project_id)
    if project is None:
        return False, {}
    command = [sys.executable, '-m', 'metaform', 'dispatch', verb, *nouns, '--json', '--project', project.project_id]
    try:
        done = subprocess.run(command, cwd=project.path, capture_output=True, text=True, encoding='utf-8',
                              stdin=subprocess.DEVNULL, timeout=DISPATCH_LIMIT, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False, {}
    try:
        return done.returncode == 0, json.loads(done.stdout) if done.returncode == 0 else {}
    except ValueError:
        return done.returncode == 0, {}


def module_verb(given: dict[str, Any], module_id: str, name: str, arguments: dict[str, Any], *,
                chosen: bool = False) -> Any:
    """Run one command of a module on the project folder's surface, as a tool call runs it: its arguments checked as
    the command line checks them, a context for the project with the page's layers, on the surface `web`; with
    chosen, on the metaform the page chose, as `opened` reads it. A module that is not on the surface is named with
    its next step. A module enabled or disabled since this server started is loaded or dropped first, so a read follows
    the surface as the command line left it, VIEW-040."""
    project = home.project(str(given.get('project', '')))
    if project is None:
        raise StoreError(f'No project {given.get("project", "")} is registered.', 'metaform list projects')
    folder = Path(project.path)
    chassis.refresh_modules()
    found = next((one for one in chassis.surface(folder) if one.id == module_id), None)
    verb = next((one for one in found.verbs if one.name == name), None) if found is not None else None
    if verb is None:
        raise Stop(f'{module_id} {name} is not on this project\'s surface.', f'metaform enable {module_id}')
    nouns, switches, _ = chassis.tool_arguments(module_id, verb, arguments, folder=folder)
    switches['layers'] = chosen_layers(given, folder)
    ctx = chassis.context(module_id, folder, project=project.project_id, nouns=nouns, switches=switches,
                          sink=lambda text: None, surface='web')
    if chosen and given.get('base'):
        ctx.store = Store(project.project_id, toggled=switches['layers'], base=str(given['base']),
                          module=module_id)
    return chassis.call(verb.run, ctx)


def opened(given: dict[str, str]) -> Store:
    """The project's store, with the layers the page chose, or else the `--layers` of the project's own folder, which
    stands for the folder the web GUI shows, question 5."""
    project = home.project(given.get('project', ''))
    if project is None:
        raise StoreError(f'No project {given.get("project", "")} is registered.', 'metaform list projects')
    chosen = given.get('layers')
    toggled = [name for name in chosen.split(',') if name] if chosen is not None else settings.toggled_layers(Path(project.path))
    return Store(project.project_id, toggled=toggled, base=given.get('base') or None)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='metaform-web')
    parser.add_argument('--bind', required=True)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--nonce', required=True)
    given = parser.parse_args(argv)
    if threading.current_thread() is threading.main_thread():  # only the main thread may set it; tests run main in one
        signal.signal(signal.SIGTERM, stopped)
    try:
        return serve(given)
    except Exception:  # noqa: BLE001  whatever ends the server is written to the log with its time
        log(f'Process {os.getpid()} stopped by an unhandled error:\n{traceback.format_exc().rstrip()}')
        return 1


def serve(given: argparse.Namespace) -> int:
    try:
        server = Server(given.bind, given.port, given.nonce)
    except OSError as error:
        log(f'cannot listen at {host_port(given.bind, given.port)}: {error}')
        return 1
    server.record()
    # Each map.changed published in another process, a command, the MCP server or a runner, reaches every open page.
    listener = events.listen('web', server.changed)
    ready(server)
    log(f'Process {os.getpid()} started on port {server.port}, code {server.code[:12]}, schema version {SCHEMA_VERSION}')
    for project in home.projects():
        server.schedule_dispatch(project.project_id)
    with listener:
        server.run()  # the stop signal ends the process; a hand-over to newer code ends `run`
    log(f'Process {os.getpid()} stopped')
    return 0


def stopped(number: int, frame: Any) -> None:
    """The stop signal, `metaform web stop`'s: write it to the log and end the process at once, as the signal's own
    default would. On Windows the signal ends the process before any handler runs, so no line is written there."""
    log(f'Process {os.getpid()} stopped by {signal.Signals(number).name}')
    os._exit(0)


def ready(server: Server) -> None:
    """Tell `metaform web` the server listens: one line on the pipe it inherited as standard output, which is then
    pointed at the log so nothing else is ever written to the pipe, VIEW-002."""
    sys.stdout.write(json.dumps({'pid': os.getpid(), 'port': server.port}) + '\n')
    sys.stdout.flush()
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())


if __name__ == '__main__':
    sys.exit(main())
