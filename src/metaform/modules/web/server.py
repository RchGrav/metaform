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
import contextvars
import gzip
import hashlib
import hmac
import json
import os
import posixpath
import queue
import re
import secrets
import shlex
import signal
import socket
import socketserver
import subprocess
import sys
import threading
import time
import traceback
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, quote, urlsplit

from metaform import events, home, prompt_files, settings
from metaform import module as chassis
from metaform.data import (
    BASE_VARIABLE,
    COLUMNS,
    CONDITIONS,
    SCHEMA_VERSION,
    NewerStore,
    Node,
    Outcome,
    Page,
    Store,
    StoreError,
    WorkRecord,
    functional_context,
    on_base,
    parse_reference,
    plain,
    prompts,
    query_read,
    query_reads,
    reference,
)
from metaform.finish_xml import xml as map_xml
from metaform.module import Stop
from metaform.outline import markdown as map_markdown
from metaform.outline import mermaid as map_mermaid
from metaform.outline import mermaid_limits

from . import (
    GATE_SECRET,
    RESTARTED,
    SERVING,
    SUPERVISOR,
    WAIT,
    WILDCARDS,
    host_port,
    loopback,
    opened_project,
    reach,
    ready_line,
    restart_said,
    run_file,
    shown_file,
    shown_project,
    spawn,
    token,
    write_run,
)

HERE = Path(__file__).parent
STATIC = {'page': (HERE / 'page').resolve(), 'vendor': (HERE / 'vendor').resolve()}
COOKIE = 'metaform_token'
# The cookie each page this server serves gets its own key in, named with the server's port: a write that is the
# person's alone is taken only with a key this server gave a page, CLI-011 (UX review, person-consent F1).
PAGE_COOKIE = 'metaform_page'
PAGE_KEYS = 64  # the newest page keys kept: the pages open now and the reloads before them
RESERVED = ('project', 'metaform', 'layers')  # what picks the store and its layers; never a read's own argument
TYPES = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
         '.mjs': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
         '.json': 'application/json', '.svg': 'image/svg+xml', '.jpg': 'image/jpeg', '.woff2': 'font/woff2', '.md': 'text/plain; charset=utf-8',
         '.txt': 'text/plain; charset=utf-8'}  # fixed, since Windows's registry can give .js a type browsers refuse
PAGE_POLICY = "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'"
# Scripts come only from the server; WebAssembly may be compiled, for the voice module's in-browser Whisper, whose
# runtime is WebAssembly. 'wasm-unsafe-eval' allows compiling WebAssembly and nothing else: no eval of script text.
SCRIPTS = "script-src 'self' 'wasm-unsafe-eval'"
IMPORT_MAP = re.compile(rb'<script type="importmap">(.*?)</script>', re.DOTALL)
# The libraries are named at /vendor/v-<version>/, the version a digest of the vendor files' stamps, so a browser keeps
# each one without asking again until an upgrade changes a file, and with it every address. The page's own files name
# /vendor/ on disk; the server writes the version into each as it sends it.
VERSIONED = re.compile(r'v-[0-9a-f]{16}')
VENDOR_NAMED = re.compile(rb'''(?<=["'(])/vendor/''')
REWRITTEN = ('.html', '.js', '.mjs', '.css')  # the page's files that name the libraries
LASTING = 'public, max-age=31536000, immutable'
# A static import or re-export, `import x from '…'`, `import '…'`, `export {x} from '…'`; never `import(…)`, which runs
# only when the code reaches it.
STATIC_IMPORT = re.compile(rb'''(?<![\w$.])(?:import|export)\s*(?:[\w$*{}\s,]*?\bfrom\s*)?(["'])([^"'\n]+)\1''')
MODULE_SCRIPT = re.compile(rb'<script type="module" src="([^"]+)"></script>')
PACKED_LEAST = 1024  # bytes; a smaller file gains less from gzip than its header costs


@dataclass
class Served:
    """A static file as it is sent: the stamp it was read at, the vendor version written into it, its ETag, a hash of
    the bytes sent, and its gzip form once a browser has asked for it."""
    stamp: tuple[int, int, str]
    tag: str
    packed: bytes | None = None


# Each static file as it is sent, VIEW-003, kept for as long as the file's size and modification time, and the vendor
# version written into it, are unchanged, so a page load re-sends nothing unchanged and an edited file is sent again
# at once.
_SERVED: dict[str, Served] = {}
_VENDOR: list[str] = []  # the vendor version, worked out again on each load of the page
# The page's modulepreload links, with what they were worked out from: the import map and module scripts, and the
# stamp of every module file read.
_PRELOADS: list[tuple[tuple[str, tuple[str, ...]], tuple[tuple[str, tuple[int, int]], ...], bytes]] = []
DISPATCH_CHANGES = frozenset({'work', 'messages', 'orchestration.routing', 'map.glyphs', 'map.ticket_settings', 'map.eligible', 'map.after',
                              'map.question_work', 'dispatch.sessions', 'dispatch.agent_sessions',
                              'dispatch.questions', 'dispatch.settings', 'dispatch.claims', 'dispatch.claim_work',
                              'dispatch.raised'})


# What a change concerns, map.changed's `kinds`, when every write said it, changes.concerns: the kinds that can start
# work, a ticket made ready, released or freed, a message or question answered; and the inputs no kind names, read from
# the tables. A session that ended says no kinds (dispatch's release), so the tables decide; `session` alone is a
# runner's own state, working or idle, which starts nothing. A ticket's words, `note`, and its plan and steps, `step`,
# start nothing either, so an agent editing its note or reporting a step costs the starter no pass (UX review round 1,
# runaway F3): only `ticket` does, a ticket written, released, freed, done or given a task.
STARTS = frozenset({'ticket', 'filed', 'orchestration.routing', 'message', 'question'})
UNKINDED = frozenset({'map.glyphs', 'map.ticket_settings', 'map.eligible', 'map.after', 'dispatch.settings',
                      'dispatch.claims',
                      'dispatch.claim_work', 'dispatch.raised'})


def named_tables(payload: dict[str, Any]) -> list[str] | None:
    """The tables a change names, the dispatch tables in its detail among them; None when it names none, or names
    `dispatch` with no detail, so it may have changed any."""
    tables: Any = payload.get('tables')
    if tables == 'dispatch':
        tables = payload.get('dispatch_tables')
    if not isinstance(tables, list) or not tables or any(not isinstance(one, str) for one in cast(list[Any], tables)):
        return None
    return cast(list[str], tables)


def given_kinds(payload: dict[str, Any]) -> list[str] | None:
    kinds: Any = payload.get('kinds')
    if not isinstance(kinds, list) or any(not isinstance(one, str) for one in cast(list[Any], kinds)):
        return None
    return cast(list[str], kinds)


def runner_change(payload: dict[str, Any]) -> bool:
    """Whether a change may have started a runner, whose lease the watch on deaths then waits on: a session or a
    ticket changed, or a change that says nothing of what it concerns. A note, a step or an agent's thread lines start
    none, so a burst of them lists nothing."""
    kinds = given_kinds(payload)
    return kinds is None or 'session' in kinds or 'ticket' in kinds


def dispatch_change(payload: dict[str, Any]) -> bool:
    """Only selection inputs trigger autostart: a change whose `kinds` say it concerns none that can start work
    does not, and else the tables it names decide. Older events without table detail may have changed any input."""
    kinds = given_kinds(payload)
    if kinds is not None and not STARTS.intersection(kinds):
        return bool(UNKINDED.intersection(named_tables(payload) or ()))
    tables = named_tables(payload)
    return tables is None or bool(DISPATCH_CHANGES.intersection(tables))


# Behind a Metaform Node's gate, the page server trusts who is calling only from requests carrying the per-deploy
# secret Caddy adds (GATE_SECRET), and serves each route only to an account whose classes, which the gate sends,
# include the route's class.
GATE_HEADER, CLASSES_HEADER, ACCOUNT_HEADER = 'X-Metaform-Gate', 'X-Metaform-Classes', 'X-Metaform-Account'
# Every page write by class. Reads are `read`, but for the build panel and the developer panes, which are admin. write
# changes the map, its tickets and memories; dispatch starts or steers agents, and needs the Node's dispatch
# capability; admin is the owner's: settings, the page's toolbar, layout and workspaces (view.py keeps them per account),
# modules, prompts, bases, backups, removing or clearing a project, builds, and any tool call through the MCP Apps host,
# which can run any verb. A toolbar tool's run passes the route as a read and is classed by its verb, verb_class, in
# workspace.run. A write not listed is admin, so a new one is refused to members until it is classed here.
WRITE_ROUTES = frozenset({
    '/api/apply-layers', '/api/answer', '/api/reopen', '/api/read', '/api/task', '/api/state', '/api/element',
    '/api/note', '/api/unhold-all', '/api/move', '/api/distribute', '/api/ticket', '/api/remove-ticket',
    '/api/eligible', '/api/memory',
    '/api/ignore',
    '/api/attach', '/api/mascot', '/api/mascot-result', '/api/voice/transcribe', '/api/voice/clip', '/api/voice/speak',
    '/api/voice/note', '/api/page-faults'})
DISPATCH_ROUTES = frozenset({
    '/api/raise', '/api/talk', '/api/system-chat', '/api/merge-review', '/api/merge-assist', '/api/ticket-merge', '/api/dispatch-start',
    '/api/orchestration-call',
    '/api/dispatch-message', '/api/dispatch-broadcast', '/api/dispatch-fork', '/api/dispatch-stop',
    '/api/dispatch-stop-all', '/api/dispatch-new', '/api/dispatch-interrupt',
    '/api/dispatch-cancel', '/api/dispatch-intake', '/api/dispatch-resume', '/api/dispatch-permit',
    '/api/dispatch-configure', '/api/dispatch-session-prompts', '/api/workflow-answer', '/api/workflow-cancel',
    '/api/roundtable-open', '/api/roundtable-decision'})
ADMIN_ROUTES = frozenset({
    '/api/save-prompt', '/api/clear-project', '/api/remove-project', '/api/restore', '/api/add-project',
    '/api/activate-base',
    '/api/remove-base', '/api/intake-finish', '/api/intake-discard','/api/dispatch-prompts', '/api/dispatch-autostart', '/api/dispatch-agents',
    '/api/dispatch-reset', '/api/settings', '/api/settings/reset', '/api/settings/choices', '/api/modules',
    '/api/mcp-call', '/api/board-line', '/api/board-add', '/api/board-remove', '/api/board-wipe', '/api/board-restore',
    '/api/voice/download', '/api/build', '/api/workspace/arrangement', '/api/workspace/reset', '/api/report',
    '/api/workspace/save', '/api/workspace/select', '/api/workspace/delete'})
ADMIN_PREFIXES = ('/api/build/', '/api/debug/', '/api/phone-check', '/api/speech-voices')
TOOL_RUN = '/api/workspace/run'
HINTS = '/api/hints'  # the first-time tips a person has seen: any account keeps its own, hints.py
VIEW = '/api/view'  # how a person's page looks right now: any account keeps its own, view.py
SHOWN = '/api/shown'  # the project the person's page shows, VIEW-002


def route_class(method: str, path: str) -> str:
    """The class of one page route: read, write, dispatch or admin. A path that is both read and written, such as
    /api/settings, is read by GET and classed by its write for POST."""
    if path == '/api/build' or path.startswith(ADMIN_PREFIXES):
        return 'admin'
    if method != 'POST' or path in (TOOL_RUN, HINTS, VIEW, SHOWN):  # a tool's run is classed again by its verb, verb_class
        return 'read'
    if path in WRITE_ROUTES:
        return 'write'
    if path in DISPATCH_ROUTES:
        return 'dispatch'
    return 'admin'  # ADMIN_ROUTES, and any write not yet classed


def verb_class(module_id: str, verb: chassis.Verb, arguments: dict[str, Any]) -> str:
    """The class a toolbar tool's verb needs, as an MCP tool call is scoped by its effect (mcp.oauth.required_scope):
    admin for a verb with a caution or given a setting only the person sets; dispatch for the dispatch module's verbs
    and any that changes something past the map; read for a read; write otherwise."""
    if verb.caution or any((setting := settings.SCHEMA.get(key)) is not None and setting.person_only
                           for key in arguments if key in verb.switches):
        return 'admin'
    if module_id == 'dispatch' or (verb.open_world and verb.effect != 'read'):
        return 'dispatch'
    return 'read' if verb.effect == 'read' else 'write'


COALESCE = 0.3  # seconds a page's stream holds dispatch-only events to merge them, VIEW-018
GONE: dict[str, Any] = {'topic': 'gone'}  # put on a page's stream by its socket closing, `events`
# The acts of the person's mascot a page takes, VIEW-005; those that ask the page something, and the body's acts, which
# answer once the body is done, at most six seconds on the page, wait this long for it
MASCOT_ACTS = {'say', 'go', 'turn', 'point', 'emote', 'look', 'see', 'select', 'camera', 'tab', 'open', 'swap',
               'flow', 'physics', 'viewing', 'embody', 'move', 'push', 'drag', 'drop', 'take', 'release', 'come',
               'capture'}
MASCOT_ASKS = {'look', 'see', 'viewing', 'embody', 'come', 'capture', 'go', 'turn', 'point', 'emote', 'move', 'push',
               'drag', 'drop', 'take', 'release', 'open'}
MASCOT_WAIT = 10.0


def dispatch_only(event: dict[str, Any]) -> bool:
    """An event naming only dispatch tables and no signal: an agent's thread or session changed, never the map."""
    payload: dict[str, Any] = cast(dict[str, Any], event.get('payload') or {})
    tables: Any = payload.get('tables')
    named: list[Any] = cast(list[Any], tables) if isinstance(tables, list) else []
    return event.get('topic') == 'map.changed' and 'signal' not in payload and (
        tables == 'dispatch' or (bool(named) and all(isinstance(t, str) and t.startswith('dispatch.') for t in named)))


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
    # what each said it concerns, map.changed's fields, BASE-053: the union, or unknown when either left one out, so a
    # page reads for every ticket and kind the merged events named, never only the first's
    for key in ('work_ids', 'session_ids', 'kinds'):
        first, second = a.get(key), b.get(key)
        if isinstance(first, list) and isinstance(second, list):
            payload[key] = sorted({*cast(list[str], first), *cast(list[str], second)})
        else:
            payload.pop(key, None)
    return {**held, 'payload': payload}


def policy(body: bytes, kind: str) -> str:
    """The Content Security Policy a file is sent with, VIEW-003. A page's import map is an inline script, which a
    browser runs only when the policy names its SHA-256; it is read from the page itself, so the two always agree, and
    no other inline script is allowed."""
    found = IMPORT_MAP.search(body) if kind.startswith('text/html') else None
    if found is None:
        return f'{PAGE_POLICY}; {SCRIPTS}'
    digest = base64.b64encode(hashlib.sha256(found.group(1)).digest()).decode('ascii')
    return f"{PAGE_POLICY}; {SCRIPTS} 'sha256-{digest}'"


code_print = chassis.code_print


def log(text: str) -> None:
    """One line of `run/web.log`, the server's standard error, stamped with its UTC time, so the log alone says when
    the server started, stopped or failed, and why."""
    print(f'{datetime.now(UTC).isoformat(timespec="seconds")} {text}', file=sys.stderr, flush=True)


# A hung server says why, and the watchdog restarts it, VIEW-002. Each request, and each page read's work, is kept in
# the server's busy table with what it waits on and since when; /api/health, answered before any module refresh or
# store, names the slowest. A page read runs in a worker thread and is answered within READ_LIMIT whatever its work
# does, since a browser opens only a few connections to one server and a read that never answers soon stops every
# other. Its work still running at STUCK, its own deadline, is wedged: /api/health then answers 503, and under the
# watchdog the server says so on its pipe and ends, so the watchdog starts it again; nothing asks it on a clock.
HEALTH = '/api/health'
NOTICED: dict[str, str] = {}  # each module's notice last written to the log, so a notice is logged once, not per read
READ_LIMIT = 15.0  # seconds a page read may run before it is answered 503 with what it waits on
SLOW = 3.0  # a read running this long is what /api/health says the server is slow on, logged once
STUCK = 20.0  # a read's work running this long has /api/health answer 503, and ends a server under the watchdog
STUCK_EXIT = 75  # the exit code of a server that ended itself for a stuck read
BACKLOG = 128  # connections the listener holds before it refuses one; the standard library's 5 fills at a page load
STREAMS = ('/api/events', '/api/voice/', '/api/build')  # GET routes that write their answer as it comes, never bounded


@dataclass(eq=False)
class Busy:
    """One request, or one page read's work, in the busy table: its route, what it waits on now, and since when."""
    route: str
    what: str
    since: float
    read: bool = False

    def shown(self, now: float) -> dict[str, Any]:
        seconds = round(now - self.since)
        return {'route': self.route, 'what': self.what, 'seconds': seconds, 'read': self.read,
                'said': f'waiting {seconds} s on {self.what}'}


_busy: ContextVar[Busy | None] = ContextVar('metaform_web_busy', default=None)
# A read's worker: the answer it gives, which the request thread writes, `Handler.bounded`
_held: ContextVar[list[tuple[int, bytes, str, dict[str, str]]] | None] = ContextVar('metaform_web_held', default=None)


def doing(what: str) -> None:
    """Say what the request or read on this thread waits on now, as /api/health and the log name it."""
    entry = _busy.get()
    if entry is not None:
        entry.what = what


def waits_on(path: str) -> str:
    """What a request waits on, named from its route until its handler says more: `/api/dispatch-sessions` is
    `dispatch sessions`."""
    return path.removeprefix('/api/').strip('/').replace('-', ' ').replace('/', ' ') or path


SAID_KEPT = 512  # the refusals and faults remembered as already logged
CODE_LOADED = time.time()  # when this server's code was loaded: each fault it raises says so, `loaded`, for autoticket
PAGE_FAULTS = 20  # the page's errors taken from one request; the page sends the errors of a second in one


class Server(ThreadingHTTPServer):
    daemon_threads = True  # one thread per request, no pool to fill: a slow request holds only its own
    allow_reuse_address = os.name != 'nt'  # on Windows it would let a second server share the port
    request_queue_size = BACKLOG

    def __init__(self, bind: str, port: int, nonce: str, origin: str = '', gate: str | None = None) -> None:
        self.address_family = socket.AF_INET6 if ':' in bind else socket.AF_INET
        self.bind, self.nonce = bind, nonce
        # Behind a Node's gate: the public origin the browser's Host and Origin name, and the secret Caddy adds.
        self.origin, self.gate = origin.rstrip('/').lower(), gate or None
        self.token = None if loopback(bind) else token()
        self.listeners: set[queue.SimpleQueue[dict[str, Any]]] = set()
        # The project each open page shows, so the page that opens a project runs its agent starter at once.
        self.watching: dict[queue.SimpleQueue[dict[str, Any]], str] = {}
        self.listening = threading.Lock()
        self.dispatch_lock = threading.Lock()
        self.dispatch_pending: set[tuple[str, str | None]] = set()  # each project, with the page's base or None
        self.capacity_waiters: set[tuple[str, str | None]] = set()
        self.dispatch_last = ''
        self.dispatch_busy = False
        self.dispatch_errors: dict[str, str] = {}  # each project's last automatic-dispatch error, logged once
        self.said: dict[str, None] = {}  # the refusals and faults already logged, oldest first, `first_time`
        self.said_lock = threading.Lock()
        self.busy: set[Busy] = set()  # each request and page read's work running now, `tracked`
        self.busy_lock = threading.Lock()
        self.started = datetime.now(UTC).isoformat(timespec='seconds')
        # Under the watchdog: its process, and the restart that started this server with its cause, taken out of the
        # environment so no agent this server starts inherits them.
        self.supervisor = os.environ.pop(SUPERVISOR, '') or None
        self.restarted = restart_said(os.environ.pop(RESTARTED, ''))
        self.told: int | None = None  # the pipe to the watchdog, kept past the ready line, `ready`
        self.retry_timers: dict[str, tuple[float, threading.Timer]] = {}  # P012: each project's next retry, when due
        # The watch on every runner of the home, dispatch's `dispatch.deaths`: a runner's death, however it comes, is a
        # change announced at once, never one a page finds on its next read (UX review round 2, intake-single-flight F1)
        self.deaths: Any = None
        self.backgrounds: dict[str, list[Any]] = {}
        self.background_lock = threading.RLock()
        # the mascot's questions to the open pages waiting for their answer, by id: what it sees, VIEW-005
        self.mascot_waiting: dict[str, dict[str, Any]] = {}
        self.code = code_print()
        # The secret the commands this server runs for the person carry, so they act as the person, CLI-011.
        self.vouch = chassis.page_vouch()
        # The keys this server put in its pages' cookies, newest last, held in memory alone: never in a file, the
        # environment or a page's script, where an agent's process would read it (UX review, person-consent F1).
        self.page_keys: dict[str, None] = {}
        self.keys_lock = threading.Lock()
        self.handing = threading.Lock()
        self.stopping, self.handed = threading.Event(), threading.Event()
        self.replacing = self.successor = False
        self.redirecting: list[threading.Thread] = []
        super().__init__((bind, port), Handler)
        self.port = int(self.server_address[1])
        names = {'127.0.0.1', 'localhost', '::1'} if loopback(bind) else {bind, socket.gethostname()}
        self.hosts = {host_port(name, self.port).lower() for name in names}

    def page_key(self) -> str:
        """A new key for one page this server serves, kept among the newest PAGE_KEYS."""
        key = secrets.token_urlsafe(32)
        with self.keys_lock:
            self.page_keys[key] = None
            while len(self.page_keys) > PAGE_KEYS:
                del self.page_keys[next(iter(self.page_keys))]
        return key

    def page_key_held(self, key: str | None) -> bool:
        """Whether `key` is one this server gave a page it served."""
        if not key:
            return False
        with self.keys_lock:
            return key in self.page_keys

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

    def first_time(self, said: str) -> bool:
        """Whether the log has not yet had this line: each refusal and fault is logged once, not on every read that
        meets it. The most recent `SAID_KEPT` are remembered."""
        with self.said_lock:
            if said in self.said:
                return False
            self.said[said] = None
            while len(self.said) > SAID_KEPT:
                del self.said[next(iter(self.said))]
            return True

    @contextmanager
    def tracked(self, entry: Busy) -> Generator[Busy, None, None]:
        """Keep `entry` in the busy table while the request or read's work it stands for runs on this thread."""
        with self.busy_lock:
            self.busy.add(entry)
        held = _busy.set(entry)
        try:
            yield entry
        finally:
            _busy.reset(held)
            with self.busy_lock:
                self.busy.discard(entry)

    def health(self) -> tuple[int, dict[str, Any]]:
        """What /api/health answers, from the busy table alone: how many requests run, the slowest of them with what
        it waits on, whether a page read is slow (SLOW) or wedged (STUCK, answered 503 for the watchdog), whether a
        watchdog keeps this server, and the restart that started it. A slow read and a wedged one are logged once."""
        now = time.monotonic()
        with self.busy_lock:
            running = sorted(self.busy, key=lambda one: one.since)
        reads = [one for one in running if one.read]
        for one in reads:
            if now - one.since >= SLOW and self.first_time(f'slow {one.route} {one.since}'):
                log(f'Slow: {one.route} has run {now - one.since:.0f} s, waiting on {one.what}')
        stuck = bool(reads) and now - reads[0].since >= STUCK
        if stuck and self.first_time(f'stuck {reads[0].route} {reads[0].since}'):
            log(f'Stuck: {reads[0].route} has run {now - reads[0].since:.0f} s, waiting on {reads[0].what}')
        slow = reads[0].shown(now) if reads and now - reads[0].since >= SLOW else None
        return 503 if stuck else 200, {
            'ok': not stuck, 'pid': os.getpid(), 'started': self.started, 'running': len(running),
            'slowest': running[0].shown(now) if running else None, 'slow': slow, 'stuck': stuck, 'stuck_after': STUCK,
            'supervised': self.supervisor is not None, 'restarted': self.restarted}

    def overran(self, entry: Busy, done: threading.Event) -> None:
        """A page read past READ_LIMIT: one wait on its work's end, with its deadline, STUCK after it began, as the
        limit. Its work still running then is wedged and logged; under the watchdog the server says why on its pipe
        and ends, so the watchdog starts it again, VIEW-002."""
        if done.wait(max(0.0, entry.since + STUCK - time.monotonic())):
            return
        said = entry.shown(time.monotonic())['said']
        if self.first_time(f'stuck {entry.route} {entry.since}'):
            log(f'Stuck: {entry.route} has run {time.monotonic() - entry.since:.0f} s, waiting on {entry.what}'
                + ('; ending, so the watchdog starts the server again' if self.told is not None else ''))
        if self.told is None:
            return
        try:
            os.write(self.told, json.dumps({'stuck': f'{entry.route} was stuck, {said}'}).encode() + b'\n')
        except OSError:
            pass
        os._exit(STUCK_EXIT)

    def own_host(self, host: str | None) -> bool:
        """The Host header names this server. On a wildcard bind every name of the machine is its own, so only the
        port is checked there, and the token guards every request. Behind a Node's gate it is the public origin's."""
        if not host:
            return False
        host = host.strip().lower()
        if self.origin:
            return host == urlsplit(self.origin).netloc
        if self.bind in WILDCARDS:
            return host.rsplit(':', 1)[-1] == str(self.port) and ':' in host
        return host in self.hosts

    def changed(self, payload: dict[str, Any], own: bool = False) -> int:
        """Push one `map.changed` to every open page, VIEW-018 and BASE-053; a change to a project no longer registered,
        such as the removal of one, is not pushed, since a page has nothing of it to read. `own`, the agent starter's
        own writes, schedules no dispatch check: a process never reacts to its own writes."""
        if home.project(str(payload.get('project', ''))) is None:
            self.watch_backgrounds(str(payload.get('project', '')), refresh=True)
            return 0
        self.background_heard(payload)
        deaths = getattr(self, 'deaths', None)  # a server made without __init__, as a test's, has none
        if deaths is not None and runner_change(payload):  # the leases listed, read only when one is new
            deaths.arm()
        if payload.get('flow'):  # where an agent's tool calls reached, drawn on the map as they happen, VIEW-005
            payload = dict(payload)
            self.push({'topic': 'map.flow', 'payload': {'project': payload['project'], 'flows': payload.pop('flow')}})
        if not own and {'autoticket.settings', 'chassis.settings'} & set(named_tables(payload) or []):
            self.watch_backgrounds(str(payload['project']), refresh=True)
        if not own and dispatch_change(payload):
            if runner_change(payload) and getattr(self, 'capacity_waiters', None):
                with self.dispatch_lock:
                    self.dispatch_pending.update(getattr(self, 'capacity_waiters', ()))
            self.schedule_dispatch(str(payload['project']))
        return self.push({'topic': 'map.changed', 'payload': payload})

    def pages_changed(self, project_id: str) -> None:
        """Say in this home's other processes how many pages show a project, as a page's stream opens or closes:
        `map.changed` naming the table `web.pages` and the kind `pages`, BASE-053, for a process that waits for a page,
        such as the demo's agent. Off the request's thread, since it reaches every listener."""
        found = home.project(project_id)
        if found is None:
            return
        with self.listening:
            pages = sum(1 for shown in self.watching.values() if shown == project_id)
        source = chassis.context('web', Path(found.path), project=project_id, surface='web')
        payload = {'project': project_id, 'base_id': None, 'tables': ['web.pages'], 'work_ids': [], 'session_ids': [],
                   'kinds': ['pages'], 'pages': pages}
        threading.Thread(target=events.publish, args=('map.changed', payload, source), daemon=True).start()

    def watch_backgrounds(self, project: str, *, refresh: bool = False) -> None:
        """One module-owned service per registered project, independent of page subscriptions."""
        if not hasattr(self, 'backgrounds'):
            return
        with self.background_lock:
            if project in self.backgrounds and not refresh:
                return
            previous = self.backgrounds.pop(project, [])
            for running in previous:
                running.close()
            found = home.project(project)
            if found is None or self.stopping.is_set():
                return
            folder = Path(found.path)
            self.backgrounds[project] = []
            for owner, start in chassis.provided(folder, 'project.background'):
                service = start(chassis.context(owner, folder, project=project, surface='web'))
                if service is not None:
                    self.backgrounds[project].append(service)

    def background_heard(self, payload: dict[str, Any]) -> None:
        """Each `map.changed` of a project, this server's own writes and those heard from other processes alike, handed
        to its background services that hear changes, `heard(payload)`: the server holds them, so they hear through any
        reload of their module, and each decides from the event alone whether it concerns it."""
        if not hasattr(self, 'backgrounds'):
            return
        with self.background_lock:
            running = list(self.backgrounds.get(str(payload.get('project', '')), ()))
        for service in running:
            heard = getattr(service, 'heard', None)
            if heard is not None:
                try:
                    heard(payload)
                except Exception as error:  # noqa: BLE001  one service's failure never stops a page's update
                    sys.stderr.write(f'A background service failed on a change: {error}\n')

    def close_backgrounds(self) -> None:
        with self.background_lock:
            for running in self.backgrounds.values():
                for service in running:
                    service.close()
            self.backgrounds.clear()

    def watch_runners(self, folder: Path) -> None:
        """Start the watch on the home's runners, once, from the first folder whose modules provide it."""
        if getattr(self, 'deaths', None) is not None:
            return
        for _, watch in chassis.provided(folder, 'dispatch.deaths'):
            with self.dispatch_lock:
                if getattr(self, 'deaths', None) is None:
                    self.deaths = watch(self.runner_died)
            return

    def runner_died(self, about: dict[str, Any]) -> None:
        """A runner of the home ended without saying so, killed or crashed: dispatch has ended what it left; the change
        goes to every open page and every other process of the home, and the agent starter looks again, since a slot
        is free and a ticket may be back in To do. In the watch's own thread."""
        project = home.project(str(about.get('project', '')))
        if project is None:
            return
        with chassis.request_scope(fresh=True):
            for payload in events.announce(Path(project.path), 'web'):  # the signals and rows the cleanup wrote
                self.changed(dict(payload), own=True)
        payload = {'project': project.project_id, 'base_id': None, 'tables': 'dispatch',
                   'dispatch_tables': ['dispatch.agent_sessions'], 'work_ids': list(about.get('work_ids') or []),
                   'session_ids': [], 'kinds': list(about.get('kinds') or ['session'])}
        self.changed(payload)
        source = chassis.context('web', Path(project.path), project=project.project_id, surface='web')
        events.publish('map.changed', payload, source)

    def open_projects(self) -> set[str]:
        with self.listening:
            return set(self.watching.values())

    def schedule_dispatch(self, project: str, base: str | None = None) -> None:
        """Queue a dispatch check on a change, without blocking page reads or starting concurrent batches; on the active
        base, or on `base`, a base the page shows that is not the active one."""
        with self.dispatch_lock:
            self.dispatch_pending.add((project, base))
            if self.dispatch_busy:
                return
            self.dispatch_busy = True
        threading.Thread(target=self.dispatch_waiting, daemon=True).start()

    def schedule_retry(self, project: str, due: Any) -> None:
        """The supervisor's next retry, P012, when one waits: one timer per project, at the earliest time due, runs the
        agent starter again, so a session whose runner is gone, as after a restart, is still resumed; nothing polls,
        QUAL-015. A runner that saw its own session stop comes back for it as well; a second pass finds it done."""
        if not isinstance(due, (int, float)):
            with self.dispatch_lock:
                held = self.retry_timers.pop(project, None)
                if held is not None:
                    held[1].cancel()
            return
        with self.dispatch_lock:
            held = self.retry_timers.get(project)
            if held is not None and held[1].is_alive() and held[0] <= due:
                return
            if held is not None:
                held[1].cancel()
            timer = threading.Timer(max(0.0, float(due) - time.time()) + 0.5, self.schedule_dispatch, (project,))
            timer.daemon = True
            self.retry_timers[project] = (float(due), timer)
            timer.start()

    def dispatch_waiting(self) -> None:
        """Start eligible work for changed projects in one worker; coalesce changes while a batch starts."""
        while True:
            with self.dispatch_lock:
                if self.dispatch_pending:
                    def order(one: tuple[str, str | None]) -> tuple[str, str]:
                        return one[0], one[1] or ''
                    ordered = sorted(self.dispatch_pending, key=order)
                    last = getattr(self, 'dispatch_last', '')
                    project_id, base = next((one for one in ordered if one[0] > last), ordered[0])
                    self.dispatch_pending.discard((project_id, base))
                    self.dispatch_last = project_id
                else:
                    self.dispatch_busy = False
                    return
            with chassis.request_scope(fresh=True):
                chassis.refresh_modules()
                project = home.project(project_id)
                if project is None:
                    continue
                try:
                    self.watch_backgrounds(project_id)
                    self.watch_runners(Path(project.path))
                    started = module_verb({'project': project_id, 'base': base or ''}, 'dispatch', 'autostart', {'batch': 1},
                                          chosen=bool(base))
                    if isinstance(started, dict):
                        result = cast(dict[str, Any], started)
                        with self.dispatch_lock:
                            if hasattr(self, 'capacity_waiters'):
                                if result.get('capacity_waiting'):
                                    self.capacity_waiters.add((project_id, base))
                                else:
                                    self.capacity_waiters.discard((project_id, base))
                            if result.get('more'):
                                self.dispatch_pending.add((project_id, base))
                    self.schedule_retry(project_id, cast(dict[str, Any], started).get('retry_due')
                                        if isinstance(started, dict) else None)
                except StoreError as error:
                    if self.dispatch_errors.get(project_id) != str(error):  # once until it changes, not on every change
                        self.dispatch_errors[project_id] = str(error)
                        log(f'Automatic dispatch for {project_id}: {error}')
                    continue
                except Stop:  # dispatch is disabled for this project
                    continue
                self.dispatch_errors.pop(project_id, None)
                for payload in events.announce(Path(project.path), 'web'):
                    self.changed(dict(payload), own=True)

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
            process = spawn(self.bind, self.port, secrets.token_hex(8), self.origin, self.gate,
                            supervisor=self.supervisor)
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
        home.mkdir_private(path.parent)
        written = path.with_suffix('.tmp')
        write_run(written, json.dumps({'pid': os.getpid(), 'bind': self.bind, 'port': self.port,
                                       'home': str(home.home()), 'nonce': self.nonce,
                                       'started': datetime.now(UTC).isoformat(timespec='seconds')}))
        os.replace(written, path)


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    # TCP_NODELAY: an answer's headers and body are two writes, and with Nagle's algorithm a small body waits for the
    # browser to acknowledge the headers, which it delays by 40 ms; a page load is hundreds of small files.
    disable_nagle_algorithm = True

    @property
    def gui(self) -> Server:
        return cast(Server, self.server)

    def log_message(self, format: str, *args: Any) -> None:
        """Requests are not logged; the log holds only what went wrong."""

    def do_GET(self) -> None:
        self.answer('GET')

    def do_POST(self) -> None:
        self.body_read = False
        self.project_given: str | None = None  # the project a write's body names, for a fault answering it
        try:
            self.answer('POST')
        finally:
            # a POST answered without its body read, a refusal among them, leaves the body on the connection, where it
            # would be taken for the start of the next request: such a connection is closed instead
            if not self.body_read and int(self.headers.get('Content-Length') or 0) > 0:
                self.close_connection = True

    def answer(self, method: str) -> None:
        self.begun = False  # one connection carries many requests; each starts unanswered
        if method == 'GET' and self.static():
            return
        path = urlsplit(self.path).path
        if path == HEALTH:
            return self.health()
        if method == 'GET':  # a stream is open for as long as the page listens, so it is no work to wait on
            return self.answered(method) if path.startswith(STREAMS) else self.bounded(path)
        with self.gui.tracked(Busy(f'{method} {path}', waits_on(path), time.monotonic())):
            self.answered(method)

    def health(self) -> None:
        """/api/health, VIEW-002: answered from the busy table alone, with no module refresh, setting or store, so it
        answers on its own thread while every other request waits on something."""
        if self.refused(parse_qs(urlsplit(self.path).query, keep_blank_values=True)) or \
                not self.permitted('GET', HEALTH):
            return
        status, found = self.gui.health()
        self.send(status, found)

    def bounded(self, path: str) -> None:
        """A GET read answered from a worker thread, so no read holds the page's connection past READ_LIMIT, whatever
        it waits on: a dispatch call, a store's upgrade or another process's lock. Past it the page is answered 503
        with what the read waits on, and the work is left to finish, named by /api/health until it does."""
        entry = Busy(f'GET {path}', waits_on(path), time.monotonic(), read=True)
        held: list[tuple[int, bytes, str, dict[str, str]]] = []
        done = threading.Event()

        def work() -> None:
            _held.set(held)
            try:
                with self.gui.tracked(entry):
                    self.answered('GET')
            except Exception:  # noqa: BLE001  answered has said all it can; what is left goes to the log
                log(f'Error answering GET {path}:\n{traceback.format_exc().rstrip()}')
            finally:
                done.set()

        threading.Thread(target=contextvars.copy_context().run, args=(work,), daemon=True,
                         name=f'read {path}').start()
        if not done.wait(READ_LIMIT):
            self.close_connection = True  # the worker still holds this handler; the page asks again on a new one
            threading.Thread(target=self.gui.overran, args=(entry, done), daemon=True, name=f'deadline {path}').start()
            restarts = (' The watchdog restarts a server whose read is stuck for '
                        f'{STUCK:.0f} s.') if self.gui.supervisor else ''
            return self.send(503, {
                'error': f'The server did not answer {path} within {READ_LIMIT:.0f} s: it is waiting on {entry.what}.',
                'next': f'Ask again shortly.{restarts} run/web.log in the Metaform home names what it waited on.'})
        if not held:
            return self.send(500, {'error': f'The server gave no answer to {path}.',
                                   'next': 'run/web.log in the Metaform home says why'})
        for status, body, kind, headers in held:
            self.reply(status, body, kind, headers)

    def answered(self, method: str) -> None:
        """Route one request with the modules enabled now, and answer whatever its handler did not answer itself."""
        try:
            with chassis.request_scope(fresh=True):
                chassis.refresh_modules()
                self.route(method)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            raise  # the page went away; there is no one to answer
        except Exception as error:
            # Whatever a handler did not answer itself, the base database read before any handler among it, is still
            # answered as {error, next}: a page never gets a dropped connection, an empty reply or HTML.
            if self.begun:  # the answer had begun, as a stream does, so nothing more can be said on it
                raise
            if isinstance(error, Stop):
                return self.refuse(error, 400 if type(error) is Stop else 404)
            self.fault(error)

    def fault(self, error: Exception) -> None:
        """An error no handler expected: logged once with its traceback, answered as a 500 the page can show, then
        published as a fault each time, for autoticket to file as a ticket to fix."""
        url = urlsplit(self.path)
        said = f'{type(error).__name__}: {error}'
        trace = traceback.format_exc().rstrip()
        if self.gui.first_time(f'fault {self.command} {url.path} {said}'):
            log(f'Fault answering {self.command} {url.path}:\n{trace}')
        self.send(500, {'error': f'The server failed answering {url.path}: {said}',
                        'next': 'metaform report "what you were doing"; the traceback is in run/web.log in the '
                                'Metaform home'})
        named = parse_qs(url.query).get('project', [None])[-1] if self.command == 'GET' else \
            getattr(self, 'project_given', None)
        self.fault_raised(named, {'source': 'web', 'message': said, 'detail': trace, 'loaded': CODE_LOADED,
                                  'reproduce': f'{self.command} {url.path} on the web server, as the page asks it.'})

    def fault_raised(self, named: Any, payload: dict[str, Any]) -> None:
        """Publish `fault.raised` for the project a request named; nothing when it named none this home holds."""
        project = home.project(str(named or ''))
        if project is None:
            return
        try:
            source = chassis.context('web', Path(project.path), project=project.project_id, surface='web')
            events.publish('fault.raised', payload, source)
        except Exception:  # noqa: BLE001  a fault that cannot be published is in the log, which is enough
            log(f'The fault could not be published:\n{traceback.format_exc().rstrip()}')

    def send_response(self, code: int, message: str | None = None) -> None:
        self.begun = True
        super().send_response(code, message)

    def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
        """The standard library's own refusals, a malformed request or a method the server has no answer for, as
        {error, next} JSON like every other answer, never its HTML page."""
        self.close_connection = True
        said = message or self.responses.get(code, ('Error',))[0]
        self.reply(code, json.dumps({'error': said, 'next': None}).encode('utf-8'), 'application/json',
                   {'Connection': 'close', 'Cache-Control': 'no-store'})

    def static(self) -> bool:
        """Answer a file of the page or a bundled library, and say whether this request was one. A file reads no
        module, setting or project, so it is answered without the request's module refresh; a page load asks for
        hundreds of them, and the refresh on each would make a reload take seconds."""
        url = urlsplit(self.path)
        top, _, rest = url.path.lstrip('/').partition('/')
        if url.path != '/' and not (top in STATIC and rest):
            return False
        query = parse_qs(url.query, keep_blank_values=True)
        if self.refused(query):
            return True
        version, _, inside = rest.partition('/')
        if url.path == '/':
            self.file(STATIC['page'], 'index.html', set_cookie='t' in query)
        elif top == 'vendor' and VERSIONED.fullmatch(version):
            # an address from a page of an earlier version is answered with the file as it is now, asked again each time
            self.file(STATIC['vendor'], inside, lasting=version == vendor_version(again=False))
        else:
            self.file(STATIC[top], rest)
        return True

    def refused(self, query: dict[str, list[str]]) -> bool:
        """Refuse a request for another address or without the token, and say whether it was refused."""
        if not self.gui.own_host(self.headers.get('Host')):
            self.send(403, {'error': "This request is not for the web GUI's own address."})
            return True
        given = self.given_token(query)
        if self.gui.token is not None and not (given and hmac.compare_digest(given, self.gui.token)):
            self.send(403, {'error': 'This request needs the token that metaform web prints.'})
            return True
        gated = self.headers.get(GATE_HEADER) or ''
        if self.gui.gate is not None and not hmac.compare_digest(gated.encode(), self.gui.gate.encode()):
            self.send(403, {'error': "This request did not come through the Node's sign-in."})
            return True
        return False

    def permitted(self, method: str, path: str) -> bool:
        """Behind a Node's gate, whether the signed-in account may use this route, by its class and the classes the
        gate sent for the account; refused with 403 when not. Without a gate the page is the person's own."""
        return self.holds(route_class(method, path), path)

    def holds(self, needed: str, path: str) -> bool:
        """Behind a Node's gate, whether the account's classes include `needed`; refused with 403 when not."""
        if self.gui.gate is None:
            return True
        allowed = (self.headers.get(CLASSES_HEADER) or '').split()
        if needed in allowed:
            return True
        account = self.headers.get(ACCOUNT_HEADER) or 'this account'
        self.send(403, {'error': f'{path} needs {needed}, which {account} may not use here.',
                        'next': 'only the owner changes settings, modules and prompts; writes need a Node at write '
                                'capability, dispatch a Node at dispatch capability'})
        return False

    def same_origin(self) -> bool:
        """A write comes from the GUI's own page: its Origin is the server's own, the public origin behind a Node's
        gate, else http://<Host>."""
        origin = self.headers.get('Origin')
        expected = self.gui.origin or f'http://{self.headers.get("Host", "")}'
        return origin is not None and origin.lower() == expected.lower()

    def route(self, method: str) -> None:
        url = urlsplit(self.path)
        query = parse_qs(url.query, keep_blank_values=True)
        if self.refused(query) or not self.permitted(method, url.path):
            return
        if url.path == '/api/build' or url.path.startswith('/api/build/'):  # the build panel, BASE-060
            from . import builds
            return builds.answer(self, method, url.path)
        if url.path == '/api/workspace' or url.path.startswith('/api/workspace/'):  # the toolbar and the panes
            from . import workspace
            return workspace.answer(self, method, url.path, query)
        if url.path.startswith('/api/voice/'):  # speech to text through the voice module's commands
            from . import voice
            return voice.answer(self, method, url.path, query)
        if url.path.startswith('/api/debug/'):  # the developer panes, only while the developer level is on
            from . import debug
            return debug.answer(self, url.path, {key: values[-1] for key, values in query.items() if key != 't'})
        if url.path == HINTS:  # the first-time tips each person has seen
            from . import hints
            return hints.answer(self, method)
        if url.path == VIEW:  # how each person's page looks right now
            from . import view
            return view.answer(self, method)
        if url.path in ('/api/mcp-apps', '/api/mcp-app', '/api/mcp-call'):  # the chat as an MCP Apps host
            from . import apps
            return apps.answer(self, method, url.path, query)
        if method == 'POST':
            return self.write(url.path)
        if url.path == '/api/events':
            return self.events(query.get('project', [''])[-1])
        if url.path in ('/api/commits', '/api/commit'):  # the board's Archive: the project folder's git history
            from . import commits
            return commits.answer(self, url.path, {key: values[-1] for key, values in query.items() if key != 't'})
        if url.path == '/api/server':
            return self.send(200, {'pid': os.getpid(), 'home': str(home.home())})
        if url.path == '/api/demo':  # the demo's card, in the home `metaform demo` runs, CLI-042
            return self.send(200, demo_card())
        if url.path == '/api/projects':  # `opened`: the project of the folder `metaform web` ran in; `recent`: the
            # project the person's page showed last, VIEW-002
            return self.send(200, {'projects': [{'id': found.project_id, 'path': found.path}
                                                for found in home.projects()], 'opened': opened_project(),
                                   'recent': shown_project()})
        if url.path == '/api/clear-preview':
            return self.clear_preview(query.get('project', [''])[-1])
        if url.path == '/api/remove-preview':
            return self.remove_preview(query.get('project', [''])[-1])
        if url.path == '/api/base-preview':
            return self.base_preview(query.get('project', [''])[-1], query.get('name', [''])[-1])
        if url.path == '/api/backups':
            return self.backups(query.get('project', [''])[-1])
        if url.path == '/api/ignore':
            return self.read_ignore(query.get('project', [''])[-1])
        if url.path == '/api/dispatch-sessions':
            return self.dispatch_sessions({key: values[-1] for key, values in query.items() if key != 't'})
        if url.path == '/api/dispatch-options':
            return self.dispatch_options({key: values[-1] for key, values in query.items() if key != 't'})
        if url.path == '/api/dispatch-spend':
            return self.dispatch_spend({key: values[-1] for key, values in query.items() if key != 't'})
        if url.path == '/api/dispatch-broadcasts':
            return self.dispatch_broadcasts({key: values[-1] for key, values in query.items() if key != 't'})
        if url.path == '/api/workflow-runs':
            return self.workflow_runs({key: values[-1] for key, values in query.items() if key != 't'})
        if url.path == '/api/roundtable':  # the roundtable stage's table, its events after a cursor
            return self.roundtable({key: values[-1] for key, values in query.items() if key != 't'})
        if url.path == '/api/dispatch-claims':
            return self.dispatch_claims({key: values[-1] for key, values in query.items() if key != 't'})
        if url.path == '/api/dispatch-prompts':
            return self.dispatch_prompts(query.get('project', [''])[-1])
        if url.path == '/api/settings':
            return self.read_settings(query.get('project', [''])[-1], keys=query.get('keys', [''])[-1],
                                      prefix=query.get('prefix', [''])[-1])
        if url.path == '/api/notices':  # what modules say needs the person, for the error surface's banners
            return self.module_notices(query.get('project', [''])[-1])
        if url.path in ('/api/phone-check', '/api/speech-voices'):  # asked for by a button, never on a page's read
            return self.settings_check(url.path, query.get('project', [''])[-1])
        if url.path == '/api/dispatch-autostart':
            return self.dispatch_autostart({'project': query.get('project', [''])[-1]})
        if url.path == '/api/dispatch-agents':
            return self.dispatch_agents({'project': query.get('project', [''])[-1]})
        if url.path in ('/api/agent-roles', '/api/agent-role'):
            return self.authored_roles({key: values[-1] for key, values in query.items() if key != 't'},
                                       one=url.path == '/api/agent-role')
        if url.path == '/api/lookup':
            return self.lookup(query.get('project', [''])[-1], list(dict.fromkeys(query.get('refs', [''])[-1].split())))
        if url.path == '/api/merges':
            return self.list_merges({key: values[-1] for key, values in query.items() if key != 't'})
        if url.path == '/api/boards':
            return self.list_boards({key: values[-1] for key, values in query.items() if key != 't'})
        if url.path == '/api/markdown':
            return self.markdown({key: values[-1] for key, values in query.items() if key != 't'})
        if url.path == '/api/xml':
            return self.xml({key: values[-1] for key, values in query.items() if key != 't'})
        if url.path == '/api/mermaid':
            return self.mermaid({key: values[-1] for key, values in query.items() if key != 't'})
        if url.path == '/api/attachment':
            return self.attachment({key: values[-1] for key, values in query.items() if key != 't'})
        if url.path == '/api/brief':
            return self.brief({key: values[-1] for key, values in query.items() if key != 't'})
        if url.path == '/api/item':
            return self.item({key: values[-1] for key, values in query.items() if key != 't'})
        if url.path == '/api/agent-view':
            return self.agent_view({key: values[-1] for key, values in query.items() if key != 't'})
        if url.path == '/api/held-work':
            return self.held_work({key: values[-1] for key, values in query.items() if key != 't'})
        if url.path == '/api/ticket-detail':
            return self.ticket_detail({key: values[-1] for key, values in query.items() if key != 't'})
        if url.path.startswith('/api/memory-'):
            return self.memory_read(url.path[len('/api/memory-'):],
                                    {key: values[-1] for key, values in query.items() if key != 't'})
        if url.path.startswith('/api/'):
            return self.read(url.path[5:], {key: values[-1] for key, values in query.items() if key != 't'})
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
        doing(f'the {name} read of {given.get("project", "")}')
        arguments = {key: value for key, value in given.items() if key not in RESERVED and key not in ('board', 'on')}
        board = given.get('board') if name == 'work' else None
        cutoff = ''
        try:
            if board is not None:  # the board reads what it shows, never every ticket
                cutoff = board_cutoff(given)
                arguments.update(done_since=cutoff)
            store = opened(given)
            found = query_read(store, name, arguments)
        except (Stop, StoreError) as error:
            return self.refuse(error, 404 if isinstance(error, StoreError) else 400)
        if found is None:
            return self.send(404, {'error': f'Nothing for {name} here, in these layers.'})
        if name == 'node':
            found = with_modules(given, found)
        if name == 'work':
            if board == 'shown' and cutoff and not given.get('ids') and isinstance(found, Page):
                ctx = chassis.context('web', Path(store.project().path), project=store.project_id, surface='web')
                ctx.store = store
                page = cast(Page[WorkRecord], found)
                known = {record.id for record in page.results}
                older = [record for _, read in chassis.provided(ctx.folder, 'dispatch.integration.pending')
                         for record in read(ctx) if record.id not in known]
                found = page._replace(results=(*page.results, *older))
            found = with_glyphs(given, found)
            if board is not None and isinstance(found, Page):
                found = {**cast(Page[WorkRecord], found).to_dict(), 'cutoff': cutoff}
            if board is not None and isinstance(found, dict):  # one named board's tickets, '' the first board's
                on = str(given.get('on') or '')
                listed = cast(list[dict[str, Any]], cast(dict[str, Any], found).get('results') or [])
                found = {**cast(dict[str, Any], found), 'cutoff': cutoff, 'board': on,
                         'results': [one for one in listed
                                     if str(cast(dict[str, Any], one.get('map') or {}).get('board') or '') == on]}
            if str(given.get('full') or '').lower() not in ('1', 'true'):
                found = brief_work(found)
        self.reply(200, chassis.result_json(found).encode('utf-8'), 'application/json', {'Cache-Control': 'no-store'})

    def memory_read(self, name: str, given: dict[str, str]) -> None:
        """A read of the memory module for the page, VIEW-031 and VIEW-034: `graph`, the whole graph with each join
        saying whether its memory shows at its node in the page's layers; `orphaned`, the memory joins the map no longer
        holds, for the orphaned menu; `note`, a node's one note; and `open_nodes`, one named memory's body."""
        if name not in MEMORY_READS:
            return self.send(404, {'error': f'No read memory-{name}.'})
        arguments = {'node': given['node']} if name == 'note' and given.get('node') else {}
        try:
            if name == 'open_nodes':
                arguments = {'names': [given.get('name', '')], 'node': given.get('node', '')}
                _, folder = project_folder(given)
                visible = chosen_layers(given, folder)
                given = {**given, 'layers': ','.join([*visible, 'memory'])} if visible else given
            found = module_verb(given, 'memory', name, arguments, chosen=name == 'open_nodes')
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

    def mermaid(self, given: dict[str, str]) -> None:
        """The map as a Mermaid flowchart, P063, for the page's export menu, with the page's layers or the folder's,
        drawn the way the page's 2D map runs and without the roots the page leaves out: the writer `map mermaid`
        uses. A diagram past what Mermaid renders by default is sent with that notice in `X-Metaform-Notice` too, for
        the page to say."""
        leave_out = tuple(root for root in given.get('leave_out', '').split(',') if root)
        try:
            text = map_mermaid(opened(given), given.get('address') or None, direction=given.get('direction') or 'TB',
                               leave_out=leave_out, labels=given.get('labels') or 'none')
        except (Stop, StoreError) as error:
            return self.refuse(error, 404 if isinstance(error, StoreError) else 400)
        notice = mermaid_limits(text)
        self.reply(200, text.encode('utf-8'), 'text/plain; charset=utf-8',
                   {'Cache-Control': 'no-store', **({'X-Metaform-Notice': notice} if notice else {})})

    def brief(self, given: dict[str, str]) -> None:
        """A node's brief as an agent reads it at `metaform://<address>`, MCP-037, so the person sees what the agent
        sees: `chassis.node_view`, the answer the MCP map view's `brief` read gives too, its items a page of `ITEMS` of
        the `kind`s named, newest first, the next page asked for with the `cursor` the last gave as `nextCursor`. The
        agent's read is the folder's, its layers and its active base, whatever the page shows."""
        try:
            project, folder = project_folder(given)
            kinds = tuple(kind for kind in given.get('kind', '').split(',') if kind)
            found = chassis.node_view(folder, given.get('address', ''), cursor=given.get('cursor'), kinds=kinds,
                                      limit=ITEMS, project=project)
        except (Stop, StoreError) as error:
            return self.refuse(error, 404 if isinstance(error, StoreError) else 400)
        self.reply(200, chassis.result_json(found).encode('utf-8'), 'application/json', {'Cache-Control': 'no-store'})

    def item(self, given: dict[str, str]) -> None:
        """One item as an agent reads it at `metaform://<address>#<n>`, MCP-037: `chassis.item_view`, the answer the MCP
        views' `item` read gives too, its text exactly and its fields, the links among them each `<relation> <arrow>
        <address>#<n>  <title>` for another memory, for the page to walk."""
        try:
            project, folder = project_folder(given)
            found = chassis.item_view(folder, given.get('item', ''), project=project)
        except (Stop, StoreError) as error:
            return self.refuse(error, 404)
        self.reply(200, chassis.result_json(found).encode('utf-8'), 'application/json', {'Cache-Control': 'no-store'})

    def agent_view(self, given: dict[str, str]) -> None:
        """What an agent connecting here receives, read from the folder's own MCP server over MCP, as the MCP Inspector
        reads a server: the server/discover result, its capabilities and the instructions sent at connect; every tool,
        resource, resource template and prompt the lists give, each entry as received with its size, the tools largest
        first; metaform://metaform, and metaform://modules measured apart; and with an address, that node's brief
        as the agent reads it. What it costs is `agent_cost`, said as Claude Code sends it to the model. The
        instructions are counted in characters too, since Claude Code keeps only the first
        `HOST_LIMIT` of a server's instructions and of each tool's description."""
        try:
            _, folder = project_folder(given)
            address = given.get('address', '').strip()
            uris = ('metaform://metaform', 'metaform://modules', *((f'metaform://{address}',) if address else ()))
            read = chassis.mcp_reads(folder, uris)
        except (Stop, StoreError) as error:
            return self.refuse(error, 404 if isinstance(error, StoreError) else 400)
        found = cast(dict[str, Any], read['discover'])
        connect = str(found.get('instructions') or '')
        texts = cast(dict[str, str], read['texts'])
        glossary = texts.get('metaform://metaform', '')
        index = texts.get('metaform://modules', '')  # each tool in one line, read apart from the glossary
        cost = agent_cost(read)
        self.send(200, {'connect': sized(connect), 'glossary': {**sized(glossary), 'index': sized(index)},
                        'brief': sized(texts[f'metaform://{address}']) if address else None,
                        'tools': cost['tools'], 'tool_bytes': sum(int(one['bytes']) for one in cost['tools']),
                        'resources': weighed(cast(list[Any], read['resources'])),
                        'templates': weighed(cast(list[Any], read['templates'])),
                        'prompts': weighed(cast(list[Any], read['prompts'])),
                        'capabilities': found.get('capabilities') or {},
                        'server': cast(dict[str, Any], found.get('_meta') or {}).get(
                            'io.modelcontextprotocol/serverInfo'),
                        'paid': cost['paid'],
                        'host_limit': HOST_LIMIT, 'budget': settings.value('node_summary_bytes', folder),
                        'protocol': found.get('supportedVersions') or []})

    def events(self, project: str = '') -> None:
        """One open page's stream of what modules publish, held open, and the project the page shows. Its thread sleeps until an event comes and writes it;
        nothing polls, QUAL-015. Events naming only dispatch tables are held up to `COALESCE` seconds and merged into
        one, so a burst of agent lines wakes the page once; any other event writes what is held and then itself at
        once. A page that has gone is dropped as its socket closes."""
        waiting: queue.SimpleQueue[dict[str, Any]] = queue.SimpleQueue()
        with self.gui.listening:
            self.gui.listeners.add(waiting)
            if project:
                self.gui.watching[waiting] = project
        if project:
            self.gui.schedule_dispatch(project)  # the page opened the project: its agent starter runs now
            self.gui.pages_changed(project)
        self.close_connection = True
        # A page whose key this process never gave, an open page reconnecting after a restart, gets a key of its own
        # with its stream, in the same HttpOnly cookie the page's load sets, so its later writes are the person's
        # again without a reload; an agent's process gets none, as with the page, CLI-011.
        keyed = None if self.gui.page_key_held(self.page_key_given()) else self.page_cookie()
        try:
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Connection', 'close')
            self.send_header('X-Content-Type-Options', 'nosniff')
            if keyed is not None:
                self.send_header('Set-Cookie', keyed)
            self.end_headers()
            self.wfile.write(b': open\n\n')
            # first, the code this server runs, so a page opened on older code knows it once the server it reconnects
            # to was updated, VIEW-002, and never runs stale code unknowing
            self.wfile.write(b'data: ' + json.dumps({'topic': 'hello', 'payload': {'code': self.gui.code[:12]}})
                             .encode('utf-8') + b'\n\n')
            self.wfile.flush()
            def send(event: dict[str, Any]) -> None:
                self.wfile.write(b'data: ' + json.dumps(event).encode('utf-8') + b'\n\n')
                self.wfile.flush()

            def gone() -> None:
                """The page sends nothing after its request: its socket readable again is the page closing it."""
                try:
                    while self.connection.recv(1024):
                        pass
                except OSError:
                    pass
                waiting.put(GONE)

            threading.Thread(target=gone, daemon=True, name='stream closing').start()
            held: dict[str, Any] | None = None
            due = 0.0
            while True:
                try:  # asleep until an event comes or, while one is held, until it is due: one bounded wait
                    event = waiting.get() if held is None else waiting.get(timeout=max(0.0, due - time.monotonic()))
                except queue.Empty:
                    send(cast(dict[str, Any], held))
                    held = None
                    continue
                if event is GONE:
                    break
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
                shown = self.gui.watching.pop(waiting, None)
            if shown:
                self.gui.pages_changed(shown)

    def write(self, path: str) -> None:
        """One of the writes of VIEW-011, from the GUI's own page only: the same Origin, and a JSON body. Whether a
        write is the person's is decided once, for every route: the page's key is held and no agent's process sent it.
        Every write that is the person's carries this server's vouch, so the commands it runs act as the person and a
        message carries their word, CLI-011, whatever the route; no route loses it by being left off a list. A write
        that is the person's alone, PERSONS_WRITES, is refused when it is not the person's; any other is taken as
        before, carrying no vouch."""
        if not self.same_origin():
            return self.send(403, {'error': "A write is taken only from the web GUI's own page."})
        keyed = self.gui.page_key_held(self.page_key_given())
        sent_by = chassis.page_caller(self.client_address[:2], self.connection.getsockname()[:2],
                                      home.home()) if keyed else None
        if path in PERSONS_WRITES:
            if not keyed:
                return self.send(403, {'error': f"{path} is the person's to do on the page itself, and this request "
                                                'carries no key this server gave a page it served.',
                                       'next': 'ask the person in chat; they do it on the page'})
            if sent_by is not None:
                return self.send(403, {'error': f"{path} is the person's to do on the page, and this request came "
                                                f'from an agent: {sent_by}.',
                                       'next': 'ask the person in chat; they do it on the page'})
        if not keyed or sent_by is not None:
            return self.writing(path)
        VOUCHED.server = self.gui
        try:
            return self.writing(path)
        finally:
            VOUCHED.server = None

    def writing(self, path: str) -> None:
        """The write itself, once it is known to come from the page, and from the person where it must."""
        if (self.headers.get('Content-Type') or '').split(';')[0].strip().lower() != 'application/json':
            return self.send(415, {'error': 'A write takes a JSON body.'})
        writes = {'/api/apply-layers': self.apply_layers,
                  '/api/save-prompt': self.save_prompt, '/api/clear-project': self.clear_project, '/api/remove-project': self.remove_project,
                  '/api/answer': self.answer_question, '/api/reopen': self.reopen_question, '/api/read': self.read_note, '/api/task': self.give_work, '/api/state': self.set_state,
                  '/api/element': self.add_part, '/api/restore': self.restore, '/api/add-project': self.add_project, '/api/report': self.problem_report,
                  '/api/page-faults': self.page_faults, SHOWN: self.shown,
                  '/api/note': self.add_note, '/api/unhold-all': self.unhold_all, '/api/move': self.move_ticket, '/api/distribute': self.distribute_tickets,
                  '/api/ticket': self.set_ticket, '/api/remove-ticket': self.remove_ticket, '/api/eligible': self.set_eligible, '/api/merge-review': self.review_merge,
                  '/api/ticket-merge': self.merge_ticket,
                  '/api/merge-assist': self.assist_merge, '/api/dispatch-reset': self.reset_agents,
                  '/api/system-chat': self.system_chat, '/api/attach': self.attach, '/api/talk': self.talk, '/api/raise': self.raise_issue,
                  '/api/activate-base': self.activate_base,
                  '/api/remove-base': self.remove_base, '/api/ignore': self.write_ignore,
                  '/api/memory': self.write_memory,
                  '/api/mascot': self.mascot_request, '/api/mascot-result': self.mascot_result,
                  '/api/dispatch-start': self.dispatch_start, '/api/dispatch-message': self.dispatch_message,
                  '/api/orchestration-call': self.orchestration_call,
                  '/api/dispatch-fork': self.dispatch_fork, '/api/dispatch-broadcast': self.dispatch_broadcast,
                  '/api/dispatch-stop': self.dispatch_stop, '/api/dispatch-stop-all': self.dispatch_stop_all,
                  '/api/dispatch-interrupt': self.dispatch_interrupt,
                  '/api/dispatch-new': self.dispatch_new,
                  '/api/dispatch-cancel': self.dispatch_cancel,
                  '/api/dispatch-prompts': self.set_dispatch_prompts,
                  '/api/dispatch-autostart': self.set_dispatch_autostart, '/api/board-line': self.board_line,
                  '/api/board-add': self.add_board, '/api/board-remove': self.remove_board,
                  '/api/board-wipe': self.wipe_board, '/api/board-restore': self.restore_board,
                  '/api/dispatch-agents': self.set_dispatch_agent, '/api/dispatch-intake': self.dispatch_intake,
                  '/api/intake-finish': self.intake_finish, '/api/intake-discard': self.intake_discard,
                  '/api/dispatch-resume': self.dispatch_resume, '/api/dispatch-permit': self.dispatch_permit,
                  '/api/dispatch-configure': self.dispatch_configure,
                  '/api/dispatch-session-prompts': self.dispatch_session_prompts,
                  '/api/workflow-answer': self.workflow_answer, '/api/workflow-cancel': self.workflow_cancel,
                  '/api/roundtable-open': self.roundtable_open,
                  '/api/roundtable-decision': self.roundtable_decision,
                  '/api/settings': self.set_setting, '/api/settings/reset': self.reset_setting,
                  '/api/settings/choices': self.read_choices, '/api/modules': self.set_module}
        if path not in writes:
            return self.send(404, {'error': f'No such write: {path}.'})
        try:
            body: Any = self.json_body()
        except ValueError:
            return self.send(400, {'error': 'The body is not JSON.'})
        given = cast(dict[str, Any], body) if isinstance(body, dict) else {}
        self.project_given = str(given.get('project') or '') or None
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

    def mascot_request(self, given: dict[str, Any]) -> None:
        """An act of the person's mascot, from the web module's verbs, VIEW-005: handed to every open page of the
        project as a `mascot` event with an id of its own. An act that asks something, what the mascot sees or a
        picture from its eyes, or what the person is looking at, or that opens a box on the page, waits up to
        MASCOT_WAIT seconds for the first page's answer that is not a refusal, `mascot_result`, or for every page to
        refuse; a page that cannot do it does not speak for one that can. The rest answer at once. With no page open on
        the project it is refused plainly."""
        project, act = str(given.get('project') or ''), str(given.get('act') or '')
        if act not in MASCOT_ACTS:
            return self.send(400, {'error': f'{act or "Nothing"} is not an act of the mascot.'})
        with self.gui.listening:
            pages = [waiting for waiting, shown in self.gui.watching.items() if shown == project]
        if not pages:
            return self.send(409, {'error': f'No page shows {project or "the project"}, so the mascot is on no map.',
                                   'next': 'open the page, at the address metaform web prints, on this project'})
        ident = secrets.token_hex(8)
        # a line asked to be said aloud waits to hear whether it was
        asks = act in MASCOT_ASKS or act == 'say' and bool(given.get('speak'))
        if asks:
            self.gui.mascot_waiting[ident] = {'event': threading.Event(), 'result': None, 'pages': len(pages),
                                              'refusals': []}
        for waiting in pages:
            waiting.put({'topic': 'mascot', 'payload': {**given, 'id': ident}})
        if not asks:
            return self.send(200, {'act': act, 'pages': len(pages)})
        held = self.gui.mascot_waiting[ident]
        answered = held['event'].wait(MASCOT_WAIT)
        self.gui.mascot_waiting.pop(ident, None)
        # a page that refused said why in its own words, which beat silence once no page did it
        result = held['result'] if held['result'] is not None else next(iter(held['refusals']), None)
        if not answered and result is None:
            return self.send(504, {'error': f'The page did not answer within {MASCOT_WAIT:g} seconds.',
                                   'next': 'bring the page to the front, then ask again'})
        return self.send(200, result)

    def mascot_result(self, given: dict[str, Any]) -> None:
        """A page's answer to one of the mascot's questions, by its id: the first answer that is not a refusal is the
        one kept; a refusal is kept only once every page asked has refused."""
        held = self.gui.mascot_waiting.get(str(given.get('id') or ''))
        if held is not None and not held['event'].is_set():
            result = given.get('result')
            answer = cast(dict[str, Any], result) if isinstance(result, dict) else {'answer': result}
            if 'error' in answer:
                held['refusals'].append(answer)
                if len(held['refusals']) >= held['pages']:
                    held['event'].set()
            else:
                held['result'] = answer
                held['event'].set()
        self.send(200, {'kept': held is not None})

    def save_prompt(self, given: dict[str, Any]) -> None:
        """Save an edited prompt as its next version, edited from `parent`, 0 for a prompt the store does not hold yet,
        whose shipped text it was edited from; no version ever changes, VIEW-013. The text is plain, as the agent
        reads it, and goes through the gate every surface saves through, so what is saved is what is sent; a text
        that cannot be is refused with why, and nothing is saved."""
        name, text, parent = given.get('name'), given.get('text'), given.get('parent')
        if not isinstance(name, str) or not isinstance(text, str) or not isinstance(parent, int) \
                or isinstance(parent, bool) or parent < 0:
            return self.send(400, {'error': 'Saving a prompt takes its name, the text, and the version number it '
                                            'was edited from.'})
        try:
            saved, said = prompt_files.save_edit(name, text, parent=parent or None)
        except StoreError as error:
            return self.refuse(error, 400)
        except ValueError as error:
            return self.send(400, {'error': f'{error}.'})
        self.send(200, {**cast(dict[str, Any], plain(saved)), 'plain': prompt_files.readable(saved),
                        'said': said + [notice.message for notice in saved.notices]})

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
        """Make a base the project's active one, as `metaform activate base <name>` does, STORE-041, only with
        `confirm` true: without it the answer is the caution, naming what leaves view, UX review round 1."""
        project = home.project(str(given.get('project', '')))
        name = given.get('name')
        if project is None or not isinstance(name, str) or not name:
            return self.send(400, {'error': 'Activate takes a registered project and a base name.'})
        if given.get('confirm') is not True:
            return self.send(400, {'error': home.switch_caution(project.project_id),
                                   'next': 'If you are sure: send confirm true'})
        try:
            left = home.active_base(project.project_id)
            made = home.activate_base(project.project_id, name)
        except StoreError as error:
            return self.refuse(error, 404)
        said = home.staying(project.project_id, left, made)  # the agents at work on the base left stay on it
        # and as data, for the page to say in its own words, never the command line's
        self.send(200, {**plain(made), **({'agents': said} if said else {}),
                        **home.staying_agents(project.project_id, left, made)})

    def remove_base(self, given: dict[str, Any]) -> None:
        """Take one base out of the project, as `metaform map remove-base <name> --confirm` does, only with `confirm`
        true; a copy of its store is kept, and the active base is refused, STORE-041."""
        project = home.project(str(given.get('project', '')))
        name = given.get('name')
        if project is None or not isinstance(name, str) or not name:
            return self.send(400, {'error': 'Remove takes a registered project and a base name.'})
        if given.get('confirm') is not True:
            return self.send(400, {'error': home.remove_caution(project.project_id, name),
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

    def base_preview(self, project: str, name: str) -> None:
        """What activating or removing the base `name` would take, in the commands' own cautions, said before the
        person decides; it changes nothing, STORE-041 and UX review round 1."""
        if home.project(project) is None:
            return self.send(404, {'error': f'No project {project} is registered.', 'next': 'metaform list projects'})
        self.send(200, {'project': project, 'name': name, 'activate': home.switch_caution(project),
                        'remove': home.remove_caution(project, name)})

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

    def set_state(self, given: dict[str, Any]) -> None:
        """The person sets a part's state on its node, MAP-046, a stage or the fault, held on the
        node's open record that carries a state, or on a new record with no task; built, or none, clears it, since
        built marks nothing."""
        node, condition = given.get('node'), given.get('condition') or ''
        if not isinstance(node, str) or not node:
            return self.send(400, {'error': 'A state is set on one node.'})
        if condition and condition not in CONDITIONS:
            return self.send(400, {'error': 'The part is unbuilt, under construction, built or broken.'})
        try:
            store = opened({'project': str(given.get('project', '')), 'base': str(given.get('base') or '')})
            with store.atomic():
                written = _stage(store, Node.parse(node), condition)
        except (Stop, StoreError) as error:
            return self.refuse(error, 400)
        kept = '' if condition == 'built' else condition
        self.send(200, {'node': node, 'condition': kept, **({'work_id': written.id} if written else {})})

    def give_work(self, given: dict[str, Any]) -> None:
        """Put a task a person wrote on the node it is assigned to, the first given, as one ticket that links the other
        nodes for reference, VIEW-032, VIEW-035 and MAP-048."""
        text, nodes, condition = given.get('task'), given.get('nodes'), given.get('condition') or ''
        # The ticket carries its kind; the part's stage, when given, goes on the part's state record, as the state
        # control sets it, never on the ticket, MAP-046 as amended 2026-10-08.
        if not isinstance(text, str) or not text.strip():
            return self.send(400, {'error': 'A task says what is to be done.'})
        if not isinstance(nodes, list) or not nodes or not all(isinstance(node, str) for node in cast(list[Any], nodes)):
            return self.send(400, {'error': 'A task is given at one node or more.'})
        if condition and condition not in CONDITIONS:  # none: a task on a part that exists, MAP-046
            return self.send(400, {'error': 'The part is unbuilt, under construction, built or broken, or its state is not given.'})
        try:
            store = opened({'project': str(given.get('project', '')), 'base': str(given.get('base') or '')})
            if given.get('hold'):
                from metaform.modules.map.storage import validate_hold_reason
                validate_hold_reason(given.get('hold_reason'))
            with store.atomic():
                targets = [Node.parse(node) for node in cast(list[str], nodes)]
                written = [store.add_work(targets[0], None, task=text.strip(), held=bool(given.get('held')),
                                          links=targets[1:], kind=given.get('kind'),
                                          hold_reason=given.get('hold_reason'))]
                if condition:
                    _stage(store, targets[0], condition)
            kept = {key: given[key] for key in ('agent', 'hold', 'eligible', 'hold_reason') if given.get(key) is not None}
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

    def ticket_detail(self, given: dict[str, str]) -> None:
        try:
            store = opened(given)
            work = store.ticket(given.get('work_id', '')).work
            fields = ticket_fields(store, work)
            graph = functional_context(store, work)
            ctx = chassis.context('web', Path(store.project().path), project=store.project_id, surface='web')
            ctx.store = store
            routing = next((owner.routing_status(ctx, work.id) for _, owner in
                            chassis.provided(ctx.folder, 'orchestration')), None)
            numbered = store.numbers_of('work', [work.id]).get(work.id)
            self.send(200, {'ticket': {**plain(work), **fields, 'column': work.column,
                                       **integration_for(store, [work]).get(work.id, {}),
                                       **ticket_hold(store, work.id)}, 'revision': ticket_revision(fields),
                            'board': board_of(store.project_id, work.id, given.get('base')),
                            'item': numbered[0] if numbered else None,  # <address>#<n>, the dialog's title bar
                            'functionality': graph, 'routing': routing,
                            'hold_history': list(store.work_hold_history(work.id))})
        except (Stop, StoreError) as error:
            self.refuse(error, 404)

    def set_ticket(self, given: dict[str, Any]) -> None:
        """Change a ticket's agent, model, thinking level, Fast, hold, glyph or board. When the agent changes while another
        agent works the ticket, that agent is stopped and the chosen one started on it."""
        work_id = given.get('work_id')
        if not isinstance(work_id, str) or not work_id:
            return self.send(400, {'error': 'A ticket change names the ticket.'})
        fields = {key: given[key] for key in TICKET_FIELDS if key in given}
        if fields:
            if any(not isinstance(value, str) for value in fields.values()):
                return self.send(400, {'error': 'Ticket text and kind must be strings.'})
            if not isinstance(given.get('revision'), str):
                return self.send(400, {'error': 'Open the ticket before editing its text.'})
            try:
                store = opened(given)
                with store.atomic():
                    before = ticket_fields(store, store.ticket(work_id).work)
                    if given['revision'] != ticket_revision(before):
                        return self.send(409, {'error': 'This ticket changed since you opened it. Reload before saving.'})
                    edited = store.edit_work(work_id, {**fields, **{key: given[key] for key in
                        ('held', 'hold_reason') if key in given}})
                    if 'hold' in given:
                        store.set_work_hold(work_id, hold=bool(given['hold']),
                                            hold_reason=given.get('hold_reason'))
                    after = ticket_fields(store, edited)
                    revision = ticket_revision(after)
                    if before != after:
                        ctx = chassis.context('web', Path(store.project().path), project=store.project_id,
                                              surface='web')
                        ctx.store = store
                        for _, owner in chassis.provided(ctx.folder, 'orchestration'):
                            owner.ticket_edited(ctx, work_id, revision)
            except (Stop, StoreError) as error:
                return self.refuse(error, 400)
            return self.send(200, {'results': [{**plain(edited), **after}], 'revision': revision})
        changes = {key: given[key] for key in
                   ('agent', 'model', 'effort', 'fast', 'hold', 'held', 'hold_reason', 'glyph', 'board') if key in given}
        if not changes:
            return self.send(400, {'error': 'A ticket change gives an agent, model, thinking level, Fast, hold, glyph or board.'})
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

    def remove_ticket(self, given: dict[str, Any]) -> None:
        """Delete a ticket for good, `map work op=remove`, the person's own act (2026-10-20: a ticket could be cancelled
        into the Archive but never deleted). An agent working it is stopped first, as one is when the ticket's agent
        changes, so nothing goes on with a ticket that is gone."""
        work_id = given.get('work_id')
        if not isinstance(work_id, str) or not work_id:
            return self.send(400, {'error': 'A ticket is deleted by its work id.'})
        try:
            found: Any = plain(module_verb(given, 'dispatch', 'sessions', {'id': work_id, 'thread': False}, chosen=True))
            rows = cast(list[dict[str, Any]], cast(dict[str, Any], found).get('sessions') or []) \
                if isinstance(found, dict) else []
            if any(row.get('state') == 'running' for row in rows):
                module_verb(given, 'dispatch', 'stop', {'id': work_id}, chosen=True)
        except (Stop, StoreError):
            pass  # dispatch not on the surface, or nothing running on it: the ticket is removed as it stands
        try:
            removed = plain(module_verb(given, 'map', 'work', {'op': 'remove', 'id': work_id}, chosen=True))
        except (Stop, StoreError) as error:
            return self.refuse(error, 400)
        self.send(200, {'results': [removed]})

    def dispatch_call(self, given: dict[str, Any], verb: str, nouns: list[str]) -> tuple[bool, dict[str, Any]]:
        """One dispatch verb run as the command line runs it, for a write that goes on after it."""
        return run_dispatch(str(given.get('project', '')), verb, nouns, chosen_base(given))

    def list_merges(self, given: dict[str, str]) -> None:
        """The merges waiting for review, VIEW-044, for the page's Review notice."""
        self.send(200, merges_waiting(given))

    def list_boards(self, given: dict[str, str]) -> None:
        """The project's named boards with their open tickets, `map boards`, for the board's picker."""
        try:
            found = cast(dict[str, Any], plain(module_verb(given, 'map', 'boards', {},
                                                         chosen=bool(chosen_base(given)))))
            boards = cast(list[dict[str, Any]], found.get('boards') or [])
            for board in boards:
                board['cutoff'] = board_cutoff({**given, 'on': str(board['name'])}, boards=boards)
            self.send(200, found)
        except (Stop, StoreError) as error:
            self.refuse(error, 400)

    def add_board(self, given: dict[str, Any]) -> None:
        """Make a named board, `map boards op=add`, the person's need of 2026-10-20: work for a new effort moves to that
        effort's board instead of piling up on the one board."""
        name = given.get('name')
        if not isinstance(name, str) or not name.strip():
            return self.send(400, {'error': 'A board has a name.'})
        try:
            made = module_verb(given, 'map', 'boards', {'op': 'add', 'name': name.strip()}, chosen=bool(chosen_base(given)))
        except (Stop, StoreError) as error:
            return self.refuse(error, 400)
        self.send(200, plain(made))

    def wipe_board(self, given: dict[str, Any]) -> None:
        """Back up and wipe one board through its canonical map verb, from the person's page only."""
        name = given.get('name')
        if not isinstance(name, str):
            return self.send(400, {'error': 'Name the board to wipe, or use an empty name for the first board.'})
        try:
            made = module_verb(given, 'map', 'boards', {'op': 'wipe', 'name': name.strip()},
                               chosen=bool(chosen_base(given)))
        except (Stop, StoreError) as error:
            return self.refuse(error, 400)
        self.send(200, plain(made))

    def restore_board(self, given: dict[str, Any]) -> None:
        """Insert one wipe backup through its canonical map verb, from the person's page only."""
        name, backup = given.get('name'), given.get('backup')
        if not isinstance(name, str) or not isinstance(backup, str) or not backup.strip():
            return self.send(400, {'error': 'Restore names the board and its backup stamp.'})
        try:
            made = module_verb(given, 'map', 'boards', {'op': 'restore', 'name': name.strip(), 'backup': backup.strip()},
                               chosen=bool(chosen_base(given)))
        except (Stop, StoreError) as error:
            return self.refuse(error, 400)
        self.send(200, plain(made))

    def remove_board(self, given: dict[str, Any]) -> None:
        """Take a named board off the project, `map boards op=remove`, from the board's Remove beside its Activate,
        as the base's on the main page: refused while tickets are on it, as the verb says."""
        name = given.get('name')
        if not isinstance(name, str) or not name.strip():
            return self.send(400, {'error': 'Name the board to remove.'})
        try:
            made = module_verb(given, 'map', 'boards', {'op': 'remove', 'name': name.strip()},
                               chosen=bool(chosen_base(given)))
        except (Stop, StoreError) as error:
            return self.refuse(error, 400)
        self.send(200, plain(made))

    def merge_ticket(self, given: dict[str, Any]) -> None:
        """The ticket's Merge click authorizes local integration, safe cleanup and completion only."""
        work_id, head = given.get('work_id'), given.get('head')
        if not isinstance(work_id, str) or not work_id or not isinstance(head, str) or not re.fullmatch(r'[0-9a-f]{40,64}', head):
            return self.send(400, {'error': 'Merge names the ticket and its saved commit.'})
        try:
            data = module_verb(given, 'dispatch', 'merge', {'id': work_id, 'head': head}, chosen=True)
        except (Stop, StoreError) as error:
            return self.refuse(error, 400)
        # A recoverable merge conflict is ordinary ticket state, retained by dispatch and shown on the card.
        self.send(200, data)

    def review_merge(self, given: dict[str, Any]) -> None:
        """The person clicked Review: retain their ownership of the explicit merge, VIEW-044."""
        work_id, project = given.get('work_id'), str(given.get('project', ''))
        if not isinstance(work_id, str) or not work_id:
            return self.send(400, {'error': 'Review names the ticket whose merge waits.'})
        ok, data = run_dispatch(project, 'review', [work_id], chosen_base(given))
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
        """Call in the chat dock: the person's system agent starts, with the agent chosen or the default one, or the
        running one is reused; `fresh`, /new on My agent with none running, resumes no earlier conversation."""
        agent, fresh = given.get('agent'), given.get('fresh')
        if agent is not None and (not isinstance(agent, str) or not agent):
            return self.send(400, {'error': 'The agent is claude, codex or antigravity.'})
        if fresh is not None and not isinstance(fresh, bool):
            return self.send(400, {'error': 'fresh is true or false.'})
        self.dispatched(given, 'system', [*([f'agent={agent}'] if agent else []), *(['fresh=true'] if fresh else [])])

    def lookup(self, project_id: str, refs: list[str]) -> None:
        """What each reference in text the person reads stands for, VIEW-042, in one answer for every reference a page
        drew: a spec record, a ticket or a message by its id or a prefix, or a file in the project folder. Nothing
        found is an answer too, with its plain reason, so a page asking about every reference it draws logs no failed
        request."""
        project = home.project(project_id)
        if project is None:
            return self.send(200, {'found': {ref: {'kind': None, 'reason': f'No project {project_id} is registered.'}
                                             for ref in refs}})
        try:
            found = referenced(project, refs)
        except (Stop, StoreError) as error:
            return self.send(200, {'found': {ref: {'kind': None, 'reason': str(error)} for ref in refs}})
        self.send(200, {'found': {ref: one or {'kind': None, 'reason': f'{ref} names nothing in this project.'}
                                  for ref, one in found.items()}})

    def raise_issue(self, given: dict[str, Any]) -> None:
        """The person raises an issue on a node: the dispatch module's raise starts the sentinel."""
        node, text = given.get('node'), given.get('text')
        if not isinstance(node, str) or not node:
            return self.send(400, {'error': 'An issue is raised on one node.'})
        if not isinstance(text, str) or not text.strip():
            return self.send(400, {'error': 'Say what is wrong, in your words.'})
        agent = given.get('agent')
        if agent is not None and (not isinstance(agent, str) or not agent):
            return self.send(400, {'error': 'The agent is claude, codex or antigravity.'})
        self.dispatched(given, 'raise', [node, *([f'agent={agent}'] if agent else [])], text.strip())

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
        home.mkdir_private(target.parent)
        home.write_private(target, raw)
        self.send(200, {'path': str(target)})

    def attachment(self, given: dict[str, str]) -> None:
        """A file an agent attached to its chat, `dispatch attach`, downloaded by its project, session and id: read
        only from where the attach kept it under the project's folder in the Metaform home, never from a path the page
        gives. `check=1` says whether it is still kept, for the chat's card, without its bytes."""
        folder = home.project_folder(given.get('project', ''))
        session, ident = given.get('session', ''), given.get('id', '')
        if folder is None:
            return self.send(404, {'error': f'No project {given.get("project", "")} is registered.'})
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', session) or not re.fullmatch(r'[0-9a-f]{16}', ident):
            return self.send(400, {'error': 'An attachment is named by its session and its id.'})
        kept = folder / 'published' / session / ident
        try:
            meta = json.loads((kept / 'meta.json').read_text(encoding='utf-8'))
            name = str(meta['name'])
            body = None if given.get('check') else (kept / name).read_bytes()
            present = (kept / name).is_file()
        except (OSError, ValueError, KeyError, TypeError):
            meta, name, body, present = None, '', None, False
        if not meta or not present or '/' in name or '\\' in name or name.startswith('.'):
            return self.send(404, {'error': 'That file is no longer kept here.'})
        if given.get('check'):
            return self.send(200, {'kept': True, 'size': (kept / name).stat().st_size, 'sha256': meta.get('sha256')})
        plain_name = ''.join(char if char.isascii() and (char.isalnum() or char in '._-') else '_' for char in name)
        self.reply(200, cast(bytes, body), str(meta.get('type') or 'application/octet-stream'), {
            'Content-Disposition': f'attachment; filename="{plain_name}"; filename*=UTF-8\'\'{quote(name, safe="")}',
            'Content-Security-Policy': 'sandbox', 'Cache-Control': 'no-store'})

    def move_ticket(self, given: dict[str, Any]) -> None:
        """Put a ticket in a column of the board and at a place in it, VIEW-037 and STORE-042."""
        work_id, column, position = given.get('work_id'), given.get('column'), given.get('position')
        if not isinstance(work_id, str) or column not in COLUMNS:
            return self.send(400, {'error': 'A move names a ticket and a column: backlog, todo, doing or done.'})
        if position is not None and (not isinstance(position, int) or isinstance(position, bool)):
            return self.send(400, {'error': 'A place in a column is a whole number.'})
        try:
            store = opened({'project': str(given.get('project', '')), 'base': str(given.get('base') or '')})
            moved = store.move_work(work_id, column, position, given.get('by'),
                                    hold_reason=given.get('hold_reason'))
        except (Stop, StoreError) as error:
            return self.refuse(error, 400)
        self.send(200, {'results': plain([moved])})

    def held_work(self, given: dict[str, Any]) -> None:
        """Preview held work and its recorded reasons before the person's bulk release."""
        from metaform.modules.map.holds import held_work_project
        try:
            held = held_work_project(opened(given))
        except (Stop, StoreError) as error:
            return self.refuse(error, 400)
        self.send(200, {'results': held, 'revision': held_work_revision(held)})

    def unhold_all(self, given: dict[str, Any]) -> None:
        """Release open work holds through the shared map operation."""
        if not isinstance(given.get('revision'), str) or not isinstance(given.get('hold_preview'), list):
            return self.send(400, {'error': 'Review held work before releasing it.'})
        try:
            if 'revision' in given:
                from metaform.modules.map.holds import held_work_project
                if given['revision'] != held_work_revision(held_work_project(opened(given))):
                    return self.send(409, {'error': 'Held work changed. Review its reasons again before releasing.'})
            made = module_verb(given, 'map', 'work', {'op': 'unhold_all',
                               **({'hold_preview': given['hold_preview']} if 'hold_preview' in given else {})},
                               chosen=True)
        except (Stop, StoreError) as error:
            return self.refuse(error, 400)
        self.send(200, plain(made))

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
                work = store.add_work(Node('element', made.id), 'unbuilt', note='Added by hand in the web GUI.')
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
        named = backup if isinstance(backup, str) and backup else None
        # a restore clears first, and a clear stops the agents at work: with any at work it is asked first, naming
        # them, as a clear is (UX review round 2, 2026-10-17, project-scope F2)
        if given.get('confirm') is not True and home.at_work(project):
            return self.send(409, {'error': 'Agents are at work on this project.',
                                   'caution': home.restore_caution(project, named),
                                   'next': 'If you are sure: send confirm true'})
        try:
            restored = home.restore_project(project, named)
        except (Stop, StoreError) as error:
            return self.refuse(error, 400)
        self.send(200, restored.to_dict())

    def add_project(self, given: dict[str, Any]) -> None:
        """Map a folder… on the page: the folder registered as `metaform start` registers it, named by the folder,
        `home.register_folder`, answered with the project and whether it was registered now; its registration is
        announced like every write, so every open page lists it (UX review round 2, 2026-10-17, PROPOSED-VIEW-D)."""
        path = given.get('path')
        if not isinstance(path, str) or not path.strip():
            return self.send(400, {'error': 'Map a folder takes the path of a folder.'})
        try:
            project, created = home.register_folder(path.strip())
        except (Stop, StoreError) as error:
            return self.refuse(error, 400)
        found = home.project(project)
        self.send(200, {'project': project, 'created': created, 'path': found.path if found else path.strip()})

    def shown(self, given: dict[str, Any]) -> None:
        """The project the page now shows, kept as the one the person used last when the page is the person's own,
        VIEW-002; a page an agent drives is answered and kept nowhere, so it never chooses the person's project."""
        project = str(given.get('project') or '')
        if home.project(project) is None:
            return self.send(404, {'error': f'No project {project} is registered.', 'next': 'metaform list projects'})
        if VOUCHED.server is None:
            return self.send(200, {'project': project, 'kept': False})
        home.mkdir_private(shown_file().parent)
        write_run(shown_file(), project)
        self.send(200, {'project': project, 'kept': True})

    def page_faults(self, given: dict[str, Any]) -> None:
        """The page's errors, core/errors.js: what failed on the page and the reads that failed, those of one second in
        one request, each with how many times it came. They are published together as one fault event, for autoticket
        to file each as a ticket to fix in one pass, once the page has its answer."""
        faults, named, loaded = given.get('faults'), given.get('project'), given.get('loaded')
        if not isinstance(faults, list) or not named:
            return self.send(400, {'error': "The page's faults are a list, with the project they happened on."})
        taken = [cast(dict[str, Any], one) for one in cast(list[Any], faults)[:PAGE_FAULTS] if isinstance(one, dict)]
        self.send(200, {'taken': len(taken)})
        raised: list[dict[str, Any]] = []
        for one in taken:
            message, count = str(one.get('message') or '')[:2000], one.get('count')
            if not message:
                continue
            framed = re.search(r'/page/[^\s:()]+\.js', str(one.get('stack') or ''))  # its innermost part of the page
            where = re.sub(r':\d+(?::\d+)?$', '', str(one.get('where') or '') or (framed[0] if framed else ''))
            where = where.lstrip('/')
            read = str(one.get('read') or '')
            raised.append({
                'source': 'page', 'message': f'{read} could not be read: {message}' if read else message,
                'detail': str(one.get('stack') or '')[:8000], 'file': where,
                'count': count if isinstance(count, int) and count > 0 else 1,
                **({'loaded': float(loaded)} if isinstance(loaded, (int, float)) else {}),  # when the page loaded
                'reproduce': (f'Open the web page on project {named}: it reads /api/{read}.' if read else
                              f'Open the web page on project {named}' + (f'; the error came from {one["where"]}.'
                                                                         if one.get('where') else '.'))})
        if raised:
            self.fault_raised(named, {'faults': raised})

    def problem_report(self, given: dict[str, Any]) -> None:
        """A tester's problem report, as `metaform report` makes it, with the page's browser and console errors,
        BASE-045: built for the project's folder and handed back for the page to save; nothing is written or sent."""
        description, console = given.get('description'), given.get('console')
        if not isinstance(description, str) or not description.strip():
            return self.send(400, {'error': 'Say in one line what went wrong.'})
        project = home.project(str(given.get('project', '')))
        folder = Path(project.path) if project is not None else home.home()
        lines = [str(line)[:4000] for line in cast(list[Any], console)[-200:]] if isinstance(console, list) else []
        try:
            name, data, held = chassis.problem_report(folder, description, files=given.get('files') is True,
                                                      browser=str(given.get('browser') or '')[:500], console=lines)
        except (Stop, StoreError, OSError) as error:
            return self.refuse(error, 500)
        self.send(200, {'name': name, 'held': held, 'send_to': 'Send this file to rchgrav on Discord.',
                        'data': base64.b64encode(data).decode('ascii')})

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
        # the launch's own permissions, when the person chose them; dispatch start checks them
        own = [f'{key}={given[key]}' for key in ('prompts', 'mode', 'batch')
               if isinstance(given.get(key), str) and given[key]]
        self.dispatched(given, 'start', [work_id, agent, *own])

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
        # with the most Agents at once may be, the setting's own maximum, so the page checks what the server checks
        self.send(200, {**{name: settings.value(key, folder) for name, key in
                           (('value', 'dispatch_autostart'), ('agent', 'dispatch_agent'), ('agents', 'dispatch_agents'),
                            ('machine', 'dispatch_machine_agents'))},
                        'most': settings.SCHEMA['dispatch_agents'].max})

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
        self.gui.schedule_dispatch(project.project_id, chosen_base(given))
        self.dispatch_autostart(given)

    def board_line(self, given: dict[str, Any]) -> None:
        """Archive through the map's shared operation, including Git proof and kept faults."""
        project = home.project(str(given.get('project', '')))
        if project is None:
            return self.send(404, {'error': f'No project {given.get("project", "")} is registered.',
                                   'next': 'metaform list projects'})
        line = given.get('line', home.now())
        if not isinstance(line, str):
            return self.send(400, {'error': 'The archive cutoff is a time as text.'})
        board = str(given.get('board') or '')
        try:
            done = cast(dict[str, Any], module_verb(given, 'map', 'boards', {
                'op': 'line', 'name': board, **({'line': line} if 'line' in given else {})},
                chosen=bool(chosen_base(given))))
        except (Stop, StoreError) as error:
            return self.refuse(error, 400)
        self.send(200, {**done, 'was': str(done.get('was') or '')})

    def dispatch_agents(self, given: dict[str, Any]) -> None:
        """The agents the page offers to start, VIEW-039: each one's name, whether its start command is found on this
        machine and which is the default, with how many more agents may be summoned now; with dispatch not enabled,
        none, and the step that enables it."""
        try:
            found = module_verb(given, 'dispatch', 'agents', {})
        except StoreError as error:  # the project is gone or its store cannot be read; a StoreError is a Stop too
            return self.refuse(error, 404)
        except Stop:
            return self.send(200, {'enabled': False, 'agents': [], 'default': None, 'next': 'metaform enable dispatch'})
        self.reply(200, chassis.result_json({**cast(dict[str, Any], found), 'enabled': True}).encode('utf-8'),
                   'application/json', {'Cache-Control': 'no-store'})

    def authored_roles(self, given: dict[str, Any], *, one: bool = False) -> None:
        """Responsibilities from the enabled public providers, with installed BMAD provenance beside native roles."""
        try:
            found = module_verb(given, 'agents', 'resolve', {'name': given.get('name')}) if one else role_choices(given)
        except StoreError as error:
            return self.refuse(error, 404)
        except Stop as error:
            return self.refuse(error, 400)
        self.reply(200, chassis.result_json(found).encode('utf-8'), 'application/json', {'Cache-Control': 'no-store'})

    def orchestration_call(self, given: dict[str, Any]) -> None:
        """The person requests a contribution from the selected assignment; the normal continuation owns launch."""
        if not all(isinstance(given.get(key), str) and given[key].strip() for key in ('assignment', 'role', 'task')):
            return self.send(400, {'error': 'A specialist call names its assignment, role and requested contribution.'})
        try:
            result = call_role(given)
        except (Stop, ValueError) as error:
            return self.refuse(error, 400)
        self.reply(200, chassis.result_json(result).encode('utf-8'), 'application/json', {})

    def set_dispatch_agent(self, given: dict[str, Any]) -> None:
        """Make one agent the default, the one started when none is chosen, as `metaform set --dispatch-agent` sets
        it, and answer with the agents as they are now."""
        project, value = home.project(str(given.get('project', ''))), given.get('default')
        if project is None:
            return self.send(404, {'error': f'No project {given.get("project", "")} is registered.',
                                   'next': 'metaform list projects'})
        folder = Path(project.path)
        chassis.refresh_modules()
        if not any(module.id == 'dispatch' for module in chassis.surface(folder)):
            return self.send(400, {'error': 'The dispatch module is not enabled.', 'next': 'metaform enable dispatch'})
        if not isinstance(value, str) or not value:
            return self.send(400, {'error': 'The default agent is claude, codex or antigravity.'})
        try:
            settings.checked('dispatch_agent', value, folder, typed=True)
            settings.put('dispatch_agent', value, folder)
        except (settings.SettingError, Stop) as error:
            return self.refuse(error, 400)
        self.dispatch_agents({'project': project.project_id})

    def dispatch_intake(self, given: dict[str, Any]) -> None:
        """Start an agent on the project's intake with the dispatch module's intake, VIEW-045 and BASE-039: the agent
        chosen or the default one, what the person asked for after `--`, and resume to take up an intake left being
        recorded. The page follows the intake as it is recorded."""
        agent, text, resume = given.get('agent'), given.get('text'), given.get('resume')
        chosen, name = given.get('map'), given.get('name')
        if agent is not None and (not isinstance(agent, str) or not agent):
            return self.send(400, {'error': 'The agent is claude, codex or antigravity.'})
        if text is not None and not isinstance(text, str):
            return self.send(400, {'error': 'What the intake is for is text.'})
        if resume is not None and not isinstance(resume, bool):
            return self.send(400, {'error': 'resume is true or false.'})
        # the map the person chose the intake makes, VIEW-045 as amended 2026-10-17: the map in use checked and
        # extended, or a new one beside it with its name; dispatch checks the name
        if chosen is not None and chosen not in ('extend', 'new'):
            return self.send(400, {'error': 'map is extend or new.'})
        if name is not None and (not isinstance(name, str) or chosen != 'new'):
            return self.send(400, {'error': 'A name is text, for a new map.'})
        nouns = [*([f'agent={agent}'] if agent else []), *(['resume=true'] if resume else []),
                 *([f'map={chosen}'] if chosen else []), *([f'name={name.strip()}'] if name and name.strip() else [])]
        self.dispatched(given, 'intake', nouns, text.strip() if text and text.strip() else None)

    def intake_finish(self, given: dict[str, Any]) -> None:
        """Finish the intake left unfinished with what it recorded, as `metaform intake finish` does, BASE-039. One an
        agent records now is its agent's to finish: the page's Finish never takes it from under it."""
        project = home.project(str(given.get('project', '')))
        if project is not None:
            try:
                held = Store(project.project_id).intake_recording().results
            except StoreError:
                held = ()
            if held:
                return self.send(400, {'error': f'An agent is recording the intake in layer {held[0].layer.name} of '
                                                f'base {held[0].base} now; it finishes the intake itself.',
                                       'next': 'metaform intake status'})
        self.dispatched(given, 'finish', [], module_id='intake')

    def intake_discard(self, given: dict[str, Any]) -> None:
        """Drop the intake left unfinished, as `metaform intake discard --confirm` does, only with `confirm` true,
        BASE-039."""
        if given.get('confirm') is not True:
            return self.send(400, {'error': 'Discarding the unfinished intake removes every part it recorded; it is '
                                            'not undone.', 'next': 'If you are sure: send confirm true'})
        self.dispatched(given, 'discard', ['--confirm'], module_id='intake')

    def dispatch_resume(self, given: dict[str, Any]) -> None:
        """Resume an ended agent session in place with the dispatch module's resume, where its agent can."""
        work_id, session = given.get('work_id'), given.get('session')
        if not isinstance(work_id, str) or not work_id:
            return self.send(400, {'error': 'A session is resumed by the work id of its ticket.'})
        if session is not None and (not isinstance(session, str) or not session):
            return self.send(400, {'error': 'The session id must be a nonempty string.'})
        self.dispatched(given, 'resume', [work_id, *([f'session={session}'] if session else [])])

    def dispatch_permit(self, given: dict[str, Any]) -> None:
        """Answer an agent's waiting permission request with the option the person chose, with the dispatch module's
        permit; the option goes after `--`."""
        work_id, request, option = given.get('work_id'), given.get('request'), given.get('option')
        if not isinstance(work_id, str) or not work_id or not isinstance(request, str) or not request:
            return self.send(400, {'error': 'A permission is answered by the work id and the request it waits on.'})
        if not isinstance(option, str) or not option.strip():
            return self.send(400, {'error': 'A permission is answered with one of its options.'})
        self.dispatched(given, 'permit', [work_id, request], option.strip())

    def dispatch_configure(self, given: dict[str, Any]) -> None:
        """Set one of a running session's settings, its mode, its model or another option, with the dispatch
        module's configure; the value goes after `--`, and a switch takes true or false."""
        work_id, setting, value = given.get('work_id'), given.get('setting'), given.get('value')
        if not isinstance(work_id, str) or not work_id or not isinstance(setting, str) or not setting:
            return self.send(400, {'error': 'A setting is set by the work id and the setting\'s id.'})
        if isinstance(value, bool):
            value = 'true' if value else 'false'
        if not isinstance(value, str) or not value.strip():
            return self.send(400, {'error': 'A setting is set to one of its choices, or on or off.'})
        self.dispatched(given, 'configure', [work_id, setting], value.strip())

    def dispatch_session_prompts(self, given: dict[str, Any]) -> None:
        """Choose how one running session's permission requests are answered from now on, with the dispatch module's
        prompts: ask_all, approve-reads or approve-all, which the page sends with confirm once the person confirmed it."""
        work_id, prompts, session = given.get('work_id'), given.get('prompts'), given.get('session')
        if not isinstance(work_id, str) or not work_id or not isinstance(prompts, str) or not prompts:
            return self.send(400, {'error': "A session's permission prompts are chosen by its work id and the choice."})
        if session is not None and (not isinstance(session, str) or not session):
            return self.send(400, {'error': 'The session id must be a nonempty string.'})
        self.dispatched(given, 'prompts', [work_id, prompts, *([f'session={session}'] if session else []),
                                           *(['confirm=true'] if given.get('confirm') is True else [])])

    def dispatch_message(self, given: dict[str, Any]) -> None:
        """Send a person's message to the agent working a ticket with the dispatch module's message, VIEW-039; to the
        chat session it names, when it names one, as several editor sessions share one ticket, BASE-062. A message to a
        child of the session, named by `fork`, goes with the dispatch module's child-message path, as text."""
        work_id, text, session, forked = given.get('work_id'), given.get('text'), given.get('session'), given.get('fork')
        if not isinstance(work_id, str) or not work_id:
            return self.send(400, {'error': 'A message goes to the agent working a ticket: its work id.'})
        if not isinstance(text, str) or not text.strip():
            return self.send(400, {'error': 'A message says something.'})
        if session is not None and (not isinstance(session, str) or not session):
            return self.send(400, {'error': 'The chat session id must be a nonempty string.'})
        if forked is not None:
            if not isinstance(forked, str) or not forked:
                return self.send(400, {'error': 'The fork\'s session id must be a nonempty string.'})
            if given.get('audio') is not None:
                return self.send(400, {'error': 'A message to a fork is sent as text; a fork takes no recording.'})
            return self.dispatched(given, 'fork', [work_id, *([f'session={session}'] if session else []),
                                                   f'fork={forked}'], text.strip())
        # a spoken message's recording, kept by /api/voice/clip, for an agent that takes audio
        from .voice import clip_path
        clip = clip_path(given['audio']) if isinstance(given.get('audio'), str) else None
        frame = kept_frame(given['image']) if isinstance(given.get('image'), str) else None
        if given.get('image') is not None and frame is None:
            return self.send(400, {'error': 'A frame is a JPEG or PNG picture, as base64, of at most 16 MB.'})
        self.dispatched(given, 'message', [work_id, *([f'session={session}'] if session else []),
                                           *([f'audio={clip}'] if clip else []),
                                           *([f'image={frame}'] if frame else [])], text.strip())

    def dispatch_broadcast(self, given: dict[str, Any]) -> None:
        """Send the person's one message to every agent running on the project with the dispatch module's broadcast,
        in one request that tells the sessions at once, so one slow agent holds neither the others nor the page; the
        person's system agent too only when `system` is true. The steering rules are `message`'s; the page is the
        person's. It answers with each session told, delivered or failed and why."""
        text, system = given.get('text'), given.get('system')
        if not isinstance(text, str) or not text.strip():
            return self.send(400, {'error': 'A broadcast says something.'})
        if system is not None and not isinstance(system, bool):
            return self.send(400, {'error': 'system is true or false: whether your chat agent is told too.'})
        self.dispatched(given, 'broadcast', ['system=true'] if system else [], text.strip())

    def dispatch_broadcasts(self, given: dict[str, str]) -> None:
        """The broadcasts kept on the project, newest first, as `metaform dispatch broadcasts` lists them. With
        dispatch not enabled there are none."""
        nouns: dict[str, Any] = {'limit': int(given['limit'])} if given.get('limit', '').isdigit() else {}
        try:
            found = module_verb(given, 'dispatch', 'broadcasts', nouns, chosen=True)
        except StoreError as error:
            return self.refuse(error, 404)
        except Stop as error:
            if 'not on this project' in str(error):
                return self.send(200, {'broadcasts': []})
            return self.refuse(error, 400)
        self.reply(200, chassis.result_json(found).encode('utf-8'), 'application/json', {'Cache-Control': 'no-store'})

    def dispatch_fork(self, given: dict[str, Any]) -> None:
        """Fork a running session into a side conversation with the dispatch module's fork, P030; the text, when there
        is some, is the fork's first turn, and with none the fork is made and waits."""
        work_id, text, session = given.get('work_id'), given.get('text'), given.get('session')
        if not isinstance(work_id, str) or not work_id:
            return self.send(400, {'error': 'A session is forked by the work id of its ticket.'})
        if session is not None and (not isinstance(session, str) or not session):
            return self.send(400, {'error': 'The chat session id must be a nonempty string.'})
        if text is not None and not isinstance(text, str):
            return self.send(400, {'error': 'A fork\'s first turn is text.'})
        self.dispatched(given, 'fork', [work_id, *([f'session={session}'] if session else [])],
                        text.strip() if text and text.strip() else None)

    def dispatch_interrupt(self, given: dict[str, Any]) -> None:
        """Interrupt the chat's current turn through dispatch without ending its session."""
        work_id, session = given.get('work_id'), given.get('session')
        if not isinstance(work_id, str) or not work_id:
            return self.send(400, {'error': 'An agent is interrupted by the work id of its ticket.'})
        if session is not None and (not isinstance(session, str) or not session):
            return self.send(400, {'error': 'The chat session id must be a nonempty string.'})
        self.dispatched(given, 'interrupt', [work_id, *([f'session={session}'] if session else [])])

    def dispatch_stop(self, given: dict[str, Any]) -> None:
        """Stop the agent working a ticket with the dispatch module's stop, VIEW-039."""
        work_id, session = given.get('work_id'), given.get('session')
        if not isinstance(work_id, str) or not work_id:
            return self.send(400, {'error': 'An agent is stopped by the work id of its ticket.'})
        if session is not None and (not isinstance(session, str) or not session):
            return self.send(400, {'error': 'The chat session id must be a nonempty string.'})
        self.dispatched(given, 'stop', [work_id, *([f'session={session}'] if session else [])])

    def dispatch_stop_all(self, given: dict[str, Any]) -> None:
        """Stop all agents in the Agents menu: `metaform dispatch stop-all`, every agent of the project, or with `home`
        true of every project, and Autostart agents turned off first, UX review round 1, 2026-10-17."""
        every = given.get('home')
        if every is not None and not isinstance(every, bool):
            return self.send(400, {'error': 'home is true or false.'})
        self.dispatched(given, 'stop-all', ['home=true'] if every else [])

    def dispatch_new(self, given: dict[str, Any]) -> None:
        """/new and /clear in the chat dock: the conversation of the agent on a ticket ends and a new one starts in the
        same role, nothing resumed, with the dispatch module's new."""
        work_id, session = given.get('work_id'), given.get('session')
        if not isinstance(work_id, str) or not work_id:
            return self.send(400, {'error': 'A new conversation names the work id of its ticket.'})
        if session is not None and (not isinstance(session, str) or not session):
            return self.send(400, {'error': 'The chat session id must be a nonempty string.'})
        self.dispatched(given, 'new', [work_id, *([f'session={session}'] if session else [])])

    def dispatch_cancel(self, given: dict[str, Any]) -> None:
        """Cancel a ticket with the dispatch module's cancel: its agent is stopped as the person's own stop, so
        nothing retries it, and the ticket is closed with the outcome cancelled and the reason, which goes after
        `--`. Moving a card to Done is completing it; this is the other end."""
        work_id, reason = given.get('work_id'), given.get('reason')
        if not isinstance(work_id, str) or not work_id:
            return self.send(400, {'error': 'A ticket is cancelled by its work id.'})
        if reason is not None and not isinstance(reason, str):
            return self.send(400, {'error': 'A reason is text.'})
        self.dispatched(given, 'cancel', [work_id], reason.strip() if reason and reason.strip() else None)

    def dispatch_options(self, given: dict[str, str]) -> None:
        """What an agent offered at its last session in this project, its model, effort, mode and the rest, with the
        value dispatch_<agent>_<option> gives each, as `metaform dispatch options` lists them, so the chat offers them
        before the agent is called; it never primes an agent. With dispatch not enabled, none."""
        try:
            found = module_verb(given, 'dispatch', 'options', {'agent': given['agent']} if given.get('agent') else {})
        except StoreError as error:
            return self.refuse(error, 404)
        except Stop as error:
            if 'not on this project' in str(error):
                return self.send(200, {'agents': []})
            return self.refuse(error, 400)
        self.reply(200, chassis.result_json(found).encode('utf-8'), 'application/json', {'Cache-Control': 'no-store'})

    def dispatch_spend(self, given: dict[str, str]) -> None:
        """What agents spent today, and on one ticket when `id` names it, as `metaform dispatch spend` reads it, so the
        page shows the same numbers the budgets are checked against. With dispatch not enabled, nothing is spent."""
        try:
            found = module_verb(given, 'dispatch', 'spend', {'id': given['id']} if given.get('id') else {})
        except StoreError as error:
            return self.refuse(error, 404)
        except Stop as error:
            if 'not on this project' in str(error):
                return self.send(200, {'enabled': False})
            return self.refuse(error, 400)
        self.reply(200, chassis.result_json(found).encode('utf-8'), 'application/json', {'Cache-Control': 'no-store'})

    def workflow_runs(self, given: dict[str, str]) -> None:
        """The project's workflow runs for the page's Runs pane, as `metaform workflow runs` lists them: the open ones,
        or those in one state, each with what stopped a paused one. With workflow not enabled there are none."""
        nouns: dict[str, Any] = {'limit': 0}
        if given.get('state'):
            nouns['state'] = given['state']
        try:
            found = module_verb(given, 'workflow', 'runs', nouns)
        except StoreError as error:
            return self.refuse(error, 404)
        except Stop as error:
            if 'not on this project' in str(error):
                return self.send(200, {'enabled': False, 'runs': []})
            return self.refuse(error, 400)
        self.reply(200, chassis.result_json({'enabled': True, **cast(dict[str, Any], found)}).encode('utf-8'),
                   'application/json', {'Cache-Control': 'no-store'})

    def roundtable(self, given: dict[str, str]) -> None:
        """The roundtable stage's read, through the roundtables module: with a table, its events after the `after` the
        page holds, and with `whole` its status too, for a stage that starts watching it; without one, the seats a
        table opens with when the person names none, roundtables_seats."""
        try:
            if not given.get('table'):
                project, folder = project_folder(given)
                doing(f'the roundtable seats of {project}')
                chassis.refresh_modules()  # roundtables declares the setting once it is loaded
                if 'roundtables_seats' not in settings.SCHEMA:
                    raise Stop('Roundtables are off in this home.', 'metaform enable roundtables')
                return self.send(200, {'seats': settings.value('roundtables_seats', folder)})
            table = {'table': given['table']}
            if given.get('pipeline'):
                return self.send(200, module_verb(given, 'roundtables', 'review', table))
            if given.get('file'):
                name = given['file']
                if name not in ('export.json', 'mechanical-report.md', 'research.md', 'architecture.md',
                                'intake.md', 'plan.md', 'decomposition.md', 'execution-outline.md', 'facilitation.md'):
                    return self.send(400, {'error': 'Choose a saved roundtable record or stage output.'})
                status = cast(dict[str, Any], module_verb(given, 'roundtables', 'status', table))
                saved = str(status.get('saved') or '')
                if not saved:
                    return self.send(404, {'error': 'The table has no saved record yet.'})
                _, folder = project_folder(given)
                return self.file(folder.resolve(), f'{saved}/{name}')
            found = cast(dict[str, Any], module_verb(given, 'roundtables', 'events',
                                                     {**table, 'after': int(given.get('after') or 0)}))
            if given.get('whole'):
                found['status'] = module_verb(given, 'roundtables', 'status', table)
        except StoreError as error:
            return self.refuse(error, 404)
        except (Stop, ValueError) as error:
            return self.refuse(error, 400)
        self.reply(200, chassis.result_json(found).encode('utf-8'), 'application/json', {'Cache-Control': 'no-store'})

    def roundtable_decision(self, given: dict[str, Any]) -> None:
        try:
            found = module_verb(given, 'roundtables', 'decide',
                                {key: given.get(key) for key in ('table', 'action', 'digest', 'revision', 'comment')})
        except StoreError as error:
            return self.refuse(error, 404)
        except (Stop, ValueError, OSError) as error:
            return self.refuse(error, 400)
        self.send(200, found)

    def roundtable_open(self, given: dict[str, Any]) -> None:
        """A table opened on the person's question, `roundtables open`, focused on the part at `address` when the
        person had one selected: with the seats the person chose, or none for roundtables_seats. It answers once the
        table's follower has opened it."""
        address, topic, seats = given.get('address'), given.get('topic'), given.get('seats')
        automate_ticket_creation = given.get('automate_ticket_creation', False)
        reply_limit = given.get('reply_limit', 512)
        if type(reply_limit) is not int or reply_limit < 1:
            return self.send(400, {'error': 'Maximum reply length is a positive whole number of characters.'})
        if address is not None and not isinstance(address, str):
            return self.send(400, {'error': 'The Address a table is about is text, or left out.'})
        if not isinstance(topic, str) or not topic.strip():
            return self.send(400, {'error': 'A table opens on a question.'})
        if not isinstance(automate_ticket_creation, bool):
            return self.send(400, {'error': 'Automate Ticket Creation is true or false.'})
        if seats is not None and (not isinstance(seats, list) or not all(isinstance(one, str) for one in
                                                                          cast(list[Any], seats))):
            return self.send(400, {'error': 'The seats are a list of seat names, such as claude/opus.'})
        nouns: dict[str, Any] = {'topic': topic.strip(),
                               **({'reply_limit': reply_limit} if 'reply_limit' in given else {}),
                               'automate_ticket_creation': automate_ticket_creation,
                               **({'address': address.strip()} if address and address.strip()
                                                            else {}), **({'seats': seats} if seats else {})}
        try:
            found = module_verb(given, 'roundtables', 'open', nouns)
        except StoreError as error:
            return self.refuse(error, 404)
        except Stop as error:
            return self.refuse(error, 400)
        self.send(200, plain(found))

    def workflow_answer(self, given: dict[str, Any]) -> None:
        """The person's answer to a run paused on them, as `metaform workflow answer` takes it on the command line, the
        person's own surface; the answer after `--`, so nothing typed is read as a switch. The page then tells the
        agent that paused it, with the web module's `resume_run` prompt, when the person asks it to."""
        run, said = given.get('run'), given.get('answer')
        if not isinstance(run, str) or not run:
            return self.send(400, {'error': 'A run is answered by its run id.'})
        if not isinstance(said, str) or not said.strip():
            return self.send(400, {'error': 'An answer says something.'})
        status, found = cli_result(given, 'workflow', 'answer', [f'run={run}'], said.strip())
        ticket = found.get('ticket')
        if status == 200 and given.get('resume') is True and isinstance(ticket, str) and ticket \
                and not ticket.startswith('not noted'):
            told = prompt_files.module('web', 'resume_run', run=run) or ''
            sent, reply = cli_result(given, 'dispatch', 'message', [ticket], told)
            found['resumed'] = sent == 200
            if sent != 200:
                found['resume_error'] = reply.get('error')
        self.send(status, found)

    def workflow_cancel(self, given: dict[str, Any]) -> None:
        """Cancel a run and every run below it, as `metaform workflow cancel` does, with the person's reason."""
        run, reason = given.get('run'), given.get('reason')
        if not isinstance(run, str) or not run:
            return self.send(400, {'error': 'A run is cancelled by its run id.'})
        if reason is not None and not isinstance(reason, str):
            return self.send(400, {'error': 'A reason is text.'})
        nouns = [f'run={run}', *([f'reason={reason.strip()}'] if reason and reason.strip() else [])]
        self.dispatched(given, 'cancel', nouns, module_id='workflow')

    def dispatch_sessions(self, given: dict[str, str]) -> None:
        """The agent sessions and their threads, from the dispatch module's own tables, VIEW-039 and VIEW-036. With
        dispatch not enabled there are none."""
        try:
            nouns: dict[str, Any] = {'id': given['id']} if given.get('id') else {}
            for key in ('session', 'after'):
                if given.get(key):
                    nouns[key] = given[key]
            for key in ('thread', 'history', 'latest'):
                if key in given:
                    if given[key] not in ('true', 'false'):
                        return self.send(400, {'error': f'{key} must be true or false.'})
                    nouns[key] = given[key] == 'true'
            for key in ('since', 'limit'):
                if key in given:
                    nouns[key] = int(given[key])
            for key in ('ids', 'session_ids'):
                if key in given:
                    value: Any = json.loads(given[key])
                    if not isinstance(value, list) or not all(isinstance(ref, str) for ref in cast(list[Any], value)):
                        return self.send(400, {'error': f'{key} must be a list of ids.'})
                    nouns[key] = value
            found = module_verb(given, 'dispatch', 'sessions', nouns, chosen=True)
        except (ValueError, TypeError):
            return self.send(400, {'error': 'Invalid session read arguments.'})
        except StoreError as error:  # the project is gone or its store cannot be read; a StoreError is a Stop too
            return self.refuse(error, 404)
        except Stop as error:
            if error.next_step == 'metaform dispatch sessions history=true':
                return self.refuse(error, 400)
            return self.send(200, {'sessions': [], 'lines': [], 'states': {}})
        if given.get('thread') == 'false' and isinstance(found, dict):
            said(given, cast(list[dict[str, Any]], cast(dict[str, Any], found).get('sessions') or []))
        self.reply(200, chassis.result_json(found).encode('utf-8'), 'application/json', {'Cache-Control': 'no-store'})

    def dispatch_claims(self, given: dict[str, str]) -> None:
        """The work claims and the sentinels' proposals, from the dispatch module's own tables, LAYER-029 and VIEW-045.
        With dispatch not enabled there are none."""
        try:
            found = module_verb(given, 'dispatch', 'claims', {}, chosen=True)
        except StoreError as error:  # the project is gone or its store cannot be read; a StoreError is a Stop too
            return self.refuse(error, 404)
        except Stop:
            return self.send(200, {'claims': [], 'proposals': {}})
        self.reply(200, chassis.result_json(found).encode('utf-8'), 'application/json', {'Cache-Control': 'no-store'})

    def dispatch_prompts(self, project_id: str) -> None:
        """How agents' permission prompts are answered, as the settings hold it, with its choices, VIEW-039: read from
        `metaform config` in the project's folder, so dispatch enabled after this server started is found."""
        project = home.project(project_id)
        if project is None:
            return self.send(404, {'error': f'No project {project_id} is registered.', 'next': 'metaform list projects'})
        doing('metaform config')
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
        self.send(200, {'value': found['value'], 'choices': found.get('choices', []), 'risky': found.get('risky', [])})

    def set_dispatch_prompts(self, given: dict[str, Any]) -> None:
        """Set how agents' permission prompts are answered, as `metaform set --dispatch-prompts` sets it, so the choice
        is kept in the settings and every agent reads it at its next prompt, VIEW-039 and BASE-052."""
        project, value = home.project(str(given.get('project', ''))), given.get('value')
        if project is None:
            return self.send(404, {'error': f'No project {given.get("project", "")} is registered.',
                                   'next': 'metaform list projects'})
        if not isinstance(value, str) or not value:
            return self.send(400, {'error': 'Agent prompts are set to one of their choices.'})
        confirmed = ['--confirm'] if given.get('confirm') is True else []  # approve-all is stored only when confirmed
        done = subprocess.run([sys.executable, '-m', 'metaform', 'set', *confirmed, f'--dispatch-prompts={value}'],
                              cwd=project.path,
                              capture_output=True, text=True, encoding='utf-8', stdin=subprocess.DEVNULL,
                              timeout=DISPATCH_LIMIT, check=False, env=vouched(None))
        if done.returncode == 0:
            return self.send(200, {'value': value})
        said = (done.stderr + done.stdout).strip().splitlines()
        self.send(400, {'error': next((line[len('Error: '):] for line in said if line.startswith('Error: ')), ' '.join(said)),
                        'next': next((line[len('Next: '):] for line in said if line.startswith('Next: ')), None)})

    def read_settings(self, project_id: str, keys: str = '', prefix: str = '') -> None:
        """The settings screen's read: every setting of the project's folder and every module with whether it is on,
        as `configured` reads them. With `keys`, a comma-separated list, or `prefix`, the settings named alone and no
        modules: a part of the page that follows two settings read all 203 and the modules, 168 KB, at every load and
        every settings change (2026-10-20)."""
        project = home.project(project_id)
        if project is None:
            return self.send(404, {'error': f'No project {project_id} is registered.', 'next': 'metaform list projects'})
        try:
            found = configured(Path(project.path), listing=not (keys or prefix))
        except Stop as error:
            return self.refuse(error, 400)
        if keys or prefix:
            named = {one.strip() for one in keys.split(',') if one.strip()}
            found['settings'] = [row for row in found['settings']
                                 if str(row.get('key')) in named or (prefix and str(row.get('key')).startswith(prefix))]
        self.send(200, found)

    def settings_check(self, path: str, project_id: str) -> None:
        """What the settings screen asks for only when the person presses its button, since it may take a while: the
        phone's state as `metaform twilio status` gives it, or the ElevenLabs voices `metaform elevenlabs voices`
        lists, which asks ElevenLabs."""
        module_id, name = ('twilio', 'status') if path == '/api/phone-check' else ('elevenlabs', 'voices')
        try:
            self.send(200, plain(module_verb({'project': project_id}, module_id, name, {})))
        except (Stop, StoreError) as error:
            self.refuse(error, 400)

    def module_notices(self, project_id: str) -> None:
        """What each module on the project's surface says needs the person: its status hook's notice, BASE-035, such
        as twilio's when its number sends calls where nothing answers. The page says each in a banner, core/errors.js.
        A notice is the owner's, so behind a Node's gate another account is answered none. Each is written to the log
        the first time it is said, and a hook that fails is logged once and says nothing on the page."""
        project = home.project(project_id)
        if project is None or (self.gui.gate is not None
                               and 'admin' not in (self.headers.get(CLASSES_HEADER) or '').split()):
            return self.send(200, {'notices': []})
        folder = Path(project.path)
        doing('module notices')
        chassis.refresh_modules()
        found: list[dict[str, str]] = []
        for module in chassis.surface(folder):
            if module.status is None:
                continue
            try:
                got = chassis.call(module.status, chassis.context(module.id, folder, project=project.project_id,
                                                                  sink=lambda text: None, surface='web'))
            except Exception as error:  # noqa: BLE001  one module's failing hook never hides the others' notices
                said = f'Notice from {module.id} could not be read: {type(error).__name__}: {error}'
            else:
                if not isinstance(got, chassis.Status) or not got.notice:
                    NOTICED.pop(module.id, None)
                    continue
                found.append({'module': module.id, 'notice': got.notice})
                said = f'Notice from {module.id}: {got.notice}'
            if NOTICED.get(module.id) != said:
                NOTICED[module.id] = said
                log(said)
        self.send(200, {'notices': found})

    def set_setting(self, given: dict[str, Any]) -> None:
        """Save one setting as `metaform set` saves it, run in the project's folder: the same switch, the same checks,
        and its refusal with the next step; with `glue` true, glued as `--glue` glues it. A boolean is true or false,
        a list is a list of its items, never its text, any other value its text; an empty list of a setting
        shown as all when empty is sent as the word all, which clears it. Answers with every setting as it is now and
        the notices `set` gave for what it kept."""
        project, key, value = home.project(str(given.get('project', ''))), given.get('key'), given.get('value')
        if project is None:
            return self.send(404, {'error': f'No project {given.get("project", "")} is registered.',
                                   'next': 'metaform list projects'})
        folder = Path(project.path)
        try:
            found = switch_of(folder, key)
        except Stop as error:
            return self.refuse(error, 400)
        if found is None:
            return self.send(404, {'error': f'No setting {key} here.', 'next': 'metaform config --show'})
        switch, negative, kind = found
        if kind == 'list' and isinstance(value, str):
            return self.send(400, {'error': f'{switch} is a list: send its items as an array.', 'key': key})
        if kind == 'list' and isinstance(value, list):
            return self.save_list(folder, str(key), cast(list[Any], value), glue=given.get('glue') is True)
        if kind == 'bool':
            if not isinstance(value, bool):
                return self.send(400, {'error': f'{switch} is on or off: true or false.', 'key': key})
            argument = switch if value else negative
        elif isinstance(value, (str, int)) and not isinstance(value, bool):
            argument = f'{switch}={value}'
        else:
            return self.send(400, {'error': f'{switch} takes its value as text.', 'key': key})
        try:
            done = metaform_cli(folder, 'set', *(['--glue'] if given.get('glue') is True else []),
                                *(['--confirm'] if given.get('confirm') is True else []), argument)
        except Stop as error:
            return self.refuse(error, 500)
        if done.returncode != 0:
            return self.send(400, {**refusal(done), 'key': key})
        said = f'Notice: {key}: '  # what set kept and says of this setting, apart from notices of the run itself
        notices = [line[len(said):] for line in done.stdout.splitlines() if line.startswith(said)]
        if key == 'dispatch_stay_connected':  # turned on, the system agent connects now, not at the next change
            self.gui.schedule_dispatch(project.project_id)
        try:
            self.send(200, {**configured(folder), 'key': key, 'notices': notices})
        except Stop as error:
            self.refuse(error, 400)

    def save_list(self, folder: Path, key: str, value: list[Any], *, glue: bool) -> None:
        """Save a list setting as the list it is, member by member, so an item may hold a comma: joined into the
        command line's comma text it was split again at every comma, CLI-027. Checked and stored as `metaform set`
        checks and stores it; an empty list of a setting shown as all when empty clears it. A setting this server does
        not declare, such as one of another project's own modules, is saved by a process in the project's folder,
        which loads that folder's modules."""
        if not all(isinstance(item, str) for item in value):
            return self.send(400, {'error': f'{key} is a list of names.', 'key': key})
        chassis.refresh_modules()  # a module turned off since this server started has no setting to save
        members = [item.strip() for item in cast(list[str], value) if item.strip()]
        try:
            status, said = (stored_list(folder, key, members, glue=glue) if key in settings.SCHEMA
                            else stored_list_there(folder, key, members, glue=glue))
        except Stop as error:
            return self.refuse(error, 500)
        if status != 200:
            return self.send(status, {**said, 'key': key})
        try:
            self.send(200, {**configured(folder), 'key': key, 'notices': said['notices']})
        except Stop as error:
            self.refuse(error, 400)

    def reset_setting(self, given: dict[str, Any]) -> None:
        """Return one setting to its default as `metaform unset` does, run in the project's folder; a glued setting is
        kept unless `unglue` is true, which unglues and resets it as `--unglue` does. Answers with every setting as it
        is now."""
        project, key = home.project(str(given.get('project', ''))), given.get('key')
        if project is None:
            return self.send(404, {'error': f'No project {given.get("project", "")} is registered.',
                                   'next': 'metaform list projects'})
        folder = Path(project.path)
        try:
            found = switch_of(folder, key)
            if found is None:
                return self.send(404, {'error': f'No setting {key} here.', 'next': 'metaform config --show'})
            done = metaform_cli(folder, 'unset', *(['--unglue'] if given.get('unglue') is True else []), found[0])
        except Stop as error:
            return self.refuse(error, 400)
        if done.returncode != 0:
            return self.send(400, {**refusal(done), 'key': key})
        if any(line.startswith('Skipped (glued)') for line in done.stdout.splitlines()):
            return self.send(400, {'error': f'{key} is glued, and a reset keeps a glued setting.', 'key': key,
                                   'next': f'metaform unset --unglue {found[0]}', 'glued': True})
        try:
            self.send(200, {**configured(folder), 'key': key})
        except Stop as error:
            self.refuse(error, 400)

    def read_choices(self, given: dict[str, Any]) -> None:
        """Read a select's choices from their source as its declaration's `choices_from` command reads them, such as
        an agent's models, which `dispatch options prime=true` reads by starting it once with no prompt; run in the
        project's folder, as the command line runs it. Only the declared command runs, never one the page sends.
        Answers with every setting as it is now, the choices read among them."""
        project, key = home.project(str(given.get('project', ''))), given.get('key')
        if project is None:
            return self.send(404, {'error': f'No project {given.get("project", "")} is registered.',
                                   'next': 'metaform list projects'})
        chassis.surface(Path(project.path))  # this server's declarations for the folder, as configured reads them
        setting = settings.SCHEMA.get(key) if isinstance(key, str) else None
        if setting is None or not setting.choices_from:
            return self.send(404, {'error': f'{key} has no command that reads its choices.',
                                   'next': 'metaform config --show', 'key': key})
        folder = Path(project.path)
        try:
            done = metaform_cli(folder, *shlex.split(setting.choices_from)[1:])
        except Stop as error:
            return self.refuse(error, 500)
        if done.returncode != 0:
            return self.send(400, {**refusal(done), 'key': key})
        try:
            self.send(200, {**configured(folder), 'key': key})
        except Stop as error:
            self.refuse(error, 400)

    def set_module(self, given: dict[str, Any]) -> None:
        """Turn a module on or off as `metaform enable` and `disable` do, run in the project's folder. It answers with
        the module and its state; the settings it brings or takes away are read again by the next read, in which this
        server has followed the change."""
        project, module_id, enabled = home.project(str(given.get('project', ''))), given.get('module'), given.get('enabled')
        if project is None:
            return self.send(404, {'error': f'No project {given.get("project", "")} is registered.',
                                   'next': 'metaform list projects'})
        if not isinstance(module_id, str) or not MODULE_ID.match(module_id) or not isinstance(enabled, bool):
            return self.send(400, {'error': 'A module is turned on or off: its id, and enabled true or false.'})
        try:
            done = metaform_cli(Path(project.path), 'enable' if enabled else 'disable', module_id)
        except Stop as error:
            return self.refuse(error, 500)
        if done.returncode != 0:
            return self.send(400, {**refusal(done), 'module': module_id})
        self.send(200, {'module': module_id, 'enabled': enabled})

    def dispatched(self, given: dict[str, Any], verb: str, nouns: list[str], text: str | None = None,
                   module_id: str = 'dispatch') -> None:
        """Run one dispatch verb as `metaform dispatch` runs it in the project's folder, and answer with its result,
        or with its error and next step. It runs as the command line, so dispatch enabled after this server started
        is found, and the person's environment reaches the agent unchanged, BASE-052. A message's text comes after
        `--`, so no text a person writes is read as a switch. `module_id` runs another module's verb the same way."""
        if module_id == 'dispatch' and verb in IN_PROCESS:
            try:
                self.send(200, in_process_result(given, verb, nouns, text))
            except (Stop, StoreError) as error:
                self.refuse(error, 400)
        else:
            self.send(*cli_result(given, module_id, verb, nouns, text))
        deaths = getattr(self.gui, 'deaths', None)
        if module_id == 'dispatch' and deaths is not None:  # a runner it started is watched at once
            deaths.arm()

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
        text = text if text.endswith('\n') or not text else text + '\n'
        if home.is_home_path(path):
            home.mkdir_private(path.parent)
            home.write_private(path, text)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
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

    def json_body(self) -> Any:
        """A write's JSON body, read to its stated length; raises ValueError when the length or the JSON is not
        valid, so a negative length never reads until the client closes the connection."""
        length = int(self.headers.get('Content-Length') or 0)
        if length < 0:
            raise ValueError(length)
        self.body_read = True
        return json.loads(self.rfile.read(length) or b'null')

    def page_key_given(self) -> str | None:
        """The page key this request's cookie carries, the one this server set when it served the page."""
        cookie = SimpleCookie(self.headers.get('Cookie') or '')
        named = f'{PAGE_COOKIE}_{self.gui.port}'
        return cookie[named].value if named in cookie else None

    def page_cookie(self) -> str | None:
        """The cookie that gives the page being served its own key, CLI-011; None when the process asking for the
        page is known as an agent's, which gets the page without one, so its writes of the person's are refused."""
        if chassis.page_caller(self.client_address[:2], self.connection.getsockname()[:2], home.home()) is not None:
            return None
        return f'{PAGE_COOKIE}_{self.gui.port}={self.gui.page_key()}; Path=/; HttpOnly; SameSite=Strict'

    def given_token(self, query: dict[str, list[str]]) -> str | None:
        if query.get('t'):
            return query['t'][0]
        if self.headers.get('X-Metaform-Token'):
            return str(self.headers['X-Metaform-Token'])
        cookie = SimpleCookie(self.headers.get('Cookie') or '')
        return cookie[COOKIE].value if COOKIE in cookie else None

    def file(self, base: Path, relative: str, *, set_cookie: bool = False, lasting: bool = False) -> None:
        """A file of the page or a bundled library, VIEW-003, gzipped when the browser takes gzip. A library at the
        current vendor version, `lasting`, is kept by the browser without asking again: its address changes when the
        file does. Every other file is asked for again before the browser uses its copy, so an updated page is the
        page a person sees; its ETag lets the answer be a 304 with no body when the copy is current. The page itself
        names every module it imports to the browser at once, `page_index`, so they load side by side."""
        resolved = (base / relative).resolve()  # base is one of STATIC's folders, resolved once
        if not resolved.is_relative_to(base) or not resolved.is_file():
            return self.send(404, {'error': 'Nothing here.'})
        kind = TYPES.get(resolved.suffix.lower(), 'application/octet-stream')
        held = resolved.stat()
        page = base == STATIC['page']
        body = None
        if page and resolved == base / 'index.html':
            body = page_index(resolved)  # its preloads and vendor version are worked out again on each load
            served = Served((held.st_mtime_ns, held.st_size, ''), quoted_digest(body))
        else:
            version = vendor_version(again=False) if page and resolved.suffix.lower() in REWRITTEN else ''
            stamp = (held.st_mtime_ns, held.st_size, version)
            served = _SERVED.get(str(resolved))
            if served is None or served.stamp != stamp:
                body = sent_bytes(resolved, version)
                served = _SERVED[str(resolved)] = Served(stamp, quoted_digest(body))
        packing = packable(kind) and held.st_size >= PACKED_LEAST and \
            accepts_gzip(self.headers.get('Accept-Encoding'))
        tag = served.tag[:-1] + '-gzip"' if packing else served.tag  # each encoding is its own representation
        current = current_copy(self.headers.get('If-None-Match'), tag)
        sending = not current and not (packing and served.packed is not None)
        if body is None and (sending or kind.startswith('text/html')):  # the page's policy is read from its body
            body = sent_bytes(resolved, served.stamp[2])
        headers = {'Content-Security-Policy': policy(body or b'', kind),
                   'Cache-Control': LASTING if lasting else 'no-cache', 'ETag': tag}
        if packable(kind):
            headers['Vary'] = 'Accept-Encoding'
        cookies = [f'{COOKIE}={self.gui.token}; Path=/; HttpOnly; SameSite=Strict'] \
            if set_cookie and self.gui.token is not None else []
        if page and resolved == base / 'index.html':  # each page served gets a key of its own, CLI-011
            keyed = self.page_cookie()
            cookies += [keyed] if keyed is not None else []
        if cookies:
            headers['Set-Cookie'] = '\n'.join(cookies)  # each sent as its own header, `sent_headers`
        if current:
            return self.unchanged(headers)
        if not packing:
            assert body is not None
            return self.reply(200, body, kind, headers)
        if served.packed is None:
            assert body is not None
            served.packed = gzip.compress(body, compresslevel=6, mtime=0)
        self.reply(200, served.packed, kind, {**headers, 'Content-Encoding': 'gzip'})

    def unchanged(self, headers: dict[str, str]) -> None:
        """A 304: the browser's copy is current. It carries the headers the file is sent with and no body."""
        self.send_response(304)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.sent_headers(headers)
        self.end_headers()

    def sent_headers(self, headers: dict[str, str]) -> None:
        """Send each header; a value of several lines is several headers of that name, as two cookies are."""
        for key, value in headers.items():
            for line in value.split('\n'):
                self.send_header(key, line)

    def refuse(self, error: Exception, status: int) -> None:
        """Answer with the error and its next step; or, for a store newer than this server's code once the code on
        disk has changed, with a 307 to the same address, where the replacement started from that code answers."""
        if isinstance(error, NewerStore) and self.gui.hand_over():
            self.close_connection = True  # the browser asks again on a new connection, so it reaches the replacement
            return self.reply(307, b'', 'text/plain', {'Location': self.path, 'Connection': 'close',
                                                       'Cache-Control': 'no-store'})
        step = getattr(error, 'next_step', None)
        path = urlsplit(self.path).path  # never the query, which can carry the token
        if self.gui.first_time(f'refused {self.command} {path} {error} {step}'):
            log(f'Refused {self.command} {path} ({status}): {error}' + (f' Next: {step}' if step else ''))
        self.send(status, {'error': str(error), 'next': step})

    def send(self, status: int, data: Any) -> None:
        self.reply(status, json.dumps(data).encode('utf-8'), 'application/json', {'Cache-Control': 'no-store'})

    def reply(self, status: int, body: bytes, kind: str, headers: dict[str, str]) -> None:
        held = _held.get()
        if held is not None:  # a read's worker: the request thread writes its answer, `bounded`
            held.append((status, body, kind, headers))
            return
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.sent_headers(headers)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)


FRAME_MOST = 16 << 20  # bytes of one frame the person sends an agent
FRAME_HOURS = 1  # a frame not sent within the hour is the person's screen left lying about, so it is removed


def kept_frame(data: str) -> Path | None:
    """A frame of the person's shared screen, base64 JPEG or PNG from the page, kept under the home's run/captures for
    the one message it goes with, which removes it once read; None for anything that is not such a picture."""
    try:
        body = base64.b64decode(data, validate=True)
    except ValueError:
        return None
    suffix = '.jpg' if body.startswith(b'\xff\xd8\xff') else '.png' if body.startswith(b'\x89PNG\r\n\x1a\n') else None
    if suffix is None or len(body) > FRAME_MOST:
        return None
    place = home.home() / 'run' / 'captures'
    home.mkdir_private(place)
    for old in place.iterdir():
        if time.time() - old.stat().st_mtime > FRAME_HOURS * 3600:
            old.unlink(missing_ok=True)
    kept = place / f'{secrets.token_hex(16)}{suffix}'
    home.write_private(kept, body)
    return kept


def current_copy(given: str | None, tag: str) -> bool:
    """Whether an `If-None-Match` header names the file's ETag, compared weakly as RFC 9110 has a GET compare it."""
    if not given:
        return False
    return any(part.strip() in ('*', tag, 'W/' + tag) for part in given.split(','))


def accepts_gzip(given: str | None) -> bool:
    """Whether an `Accept-Encoding` header takes gzip, RFC 9110: named, or `*`, with no `q=0`."""
    for part in (given or '').split(','):
        name, _, weight = part.partition(';')
        if name.strip().lower() not in ('gzip', 'x-gzip', '*'):
            continue
        weight = weight.strip().lower()
        try:
            return not weight.startswith('q=') or float(weight[2:]) > 0
        except ValueError:
            return False
    return False


def packable(kind: str) -> bool:
    """Whether a file of this type is worth gzipping: text, JSON and SVG are; fonts and pictures come compressed."""
    return kind.startswith(('text/', 'application/json', 'image/svg+xml'))


def quoted_digest(body: bytes) -> str:
    return '"' + hashlib.sha256(body).hexdigest()[:32] + '"'


def vendor_version(*, again: bool = True) -> str:
    """The vendor files' version: a digest of each one's path, size and modification time. Worked out again on each
    load of the page, `again`; a file's own request takes the version that load named."""
    if _VENDOR and not again:
        return _VENDOR[0]
    root = STATIC['vendor']
    digest = hashlib.sha256()
    for path in sorted(root.rglob('*')):
        if path.is_file():
            held = path.stat()
            digest.update(f'{path.relative_to(root).as_posix()}\0{held.st_size}\0{held.st_mtime_ns}\n'.encode())
    _VENDOR[:] = ['v-' + digest.hexdigest()[:16]]
    return _VENDOR[0]


def sent_bytes(path: Path, version: str) -> bytes:
    """A static file's bytes as they are sent: a page file with the vendor version in each library's address."""
    body = path.read_bytes()
    return VENDOR_NAMED.sub(b'/vendor/' + version.encode('ascii') + b'/', body) if version else body


def page_index(path: Path) -> bytes:
    """The page, index.html, as it is sent: a modulepreload link after its import map for every module it loads, and
    the current vendor version in each library's address."""
    page = path.read_bytes()
    found = IMPORT_MAP.search(page)
    if found is not None:  # a preload is only resolved through the import map when it comes after it
        page = page[:found.end()] + preloads(page) + page[found.end():]
    return VENDOR_NAMED.sub(b'/vendor/' + vendor_version().encode('ascii') + b'/', page)


def stamp(path: Path) -> tuple[int, int]:
    try:
        held = path.stat()
    except OSError:
        return (-1, -1)
    return (held.st_mtime_ns, held.st_size)


def static_path(url: str) -> Path | None:
    """The file a static address names, or None for an address outside the page's and the libraries' folders."""
    top, _, rest = url.lstrip('/').partition('/')
    if not url.startswith('/') or top not in STATIC or not rest:
        return None
    base = STATIC[top].resolve()
    path = (base / rest).resolve()
    return path if path.is_relative_to(base) else None


def resolved_import(specifier: str, at: str, imports: dict[str, str]) -> str | None:
    """The address a browser loads for a static import in the module at `at`, by URL resolution and the page's import
    map, or None for one the browser would refuse."""
    if specifier.startswith(('./', '../')):
        return posixpath.normpath(posixpath.join(posixpath.dirname(at), specifier))
    if specifier.startswith('/') and not specifier.startswith('//'):
        return posixpath.normpath(specifier)
    if specifier in imports:
        return imports[specifier]
    prefixes = [key for key in imports if key.endswith('/') and specifier.startswith(key)]
    if not prefixes:
        return None
    longest = max(prefixes, key=len)
    return imports[longest] + specifier[len(longest):]


def preloads(page: bytes) -> bytes:
    """A `<link rel="modulepreload">` for every module the page's module scripts reach by static import, in the order
    they are found. Each part of the page imports the part before it, so without them the browser finds the modules
    one round trip at a time, a level deep each; with them it asks for all of them at once. Worked out again only when
    the import map, the module scripts or a module file read has changed."""
    found = IMPORT_MAP.search(page)
    imports = cast(dict[str, str], json.loads(found.group(1)).get('imports', {})) if found else {}
    entries = tuple(entry.decode('utf-8') for entry in MODULE_SCRIPT.findall(page))
    key = (json.dumps(imports, sort_keys=True), entries)
    if _PRELOADS:
        known, stamps, links = _PRELOADS[0]
        if known == key and all(stamp(Path(name)) == held for name, held in stamps):
            return links
    order: list[str] = []
    read: list[tuple[str, tuple[int, int]]] = []
    waiting, seen = list(entries), set(entries)
    while waiting:
        url = waiting.pop(0)
        path = static_path(url)
        if path is None or path.suffix.lower() not in ('.js', '.mjs'):
            continue
        read.append((str(path), stamp(path)))  # a module missing now is read again once it is there
        if not path.is_file():
            continue
        order.append(url)
        for _, specifier in STATIC_IMPORT.findall(path.read_bytes()):
            target = resolved_import(specifier.decode('utf-8', 'replace'), url, imports)
            if target is not None and target not in seen:
                seen.add(target)
                waiting.append(target)
    links = b''.join(b'\n<link rel="modulepreload" href="' + url.encode('utf-8') + b'">' for url in order)
    _PRELOADS[:] = [(key, tuple(read), links)]
    return links


def _versions(given: dict[str, str]) -> dict[str, Any]:
    """Every version of a prompt, newest first, each with the layers it made and `plain`, its text as the person reads
    and edits it. A prompt a module ships that the store does not hold yet is its shipped text as version 0, so any
    prompt an agent is sent can be opened and edited before it was first sent, VIEW-013. `problem` says why its
    element does not read from its file, when it does not."""
    name = given.get('name', '')
    owner, colon, element = name.partition(':')
    problem = prompt_files.problem_of(owner, element) if colon and '.' not in element else None
    written = 'plain' if prompt_files.written_plain(name) else 'stored'  # how the editor shows and saves it
    try:
        versions = prompts.prompt_versions(name)
    except StoreError:
        shipped = prompt_files.shipped(owner, element) if colon and owner != 'skill' else None
        if shipped is None:
            raise
        return {'versions': [{'number': 0, 'name': name, 'format': 'xml' if '.' not in element else 'text',
                              'origin': 'shipped', 'created': 'not sent yet', 'text': shipped,
                              'plain': prompt_files.plain(shipped) if written == 'plain' else shipped,
                              'layers': []}], 'problem': problem, 'written': written}
    return {'versions': [{**cast(dict[str, Any], plain(version)), 'plain': prompt_files.readable(version),
                          'layers': plain(prompts.layers_by_prompt_version(version.version_id))}
                         for version in versions], 'problem': problem, 'written': written}


def _catalog(given: dict[str, str]) -> dict[str, Any]:
    """Every prompt the page can open, VIEW-013: those the agents of each role are sent, by role, as the agents
    module names them for the project the page shows, whether or not they were ever sent; then every other prompt the
    store holds. With the agents module off, or no project, only the stored ones."""
    roles: list[dict[str, Any]] = []
    if given.get('project'):
        try:
            found = cast(dict[str, Any], module_verb({'project': given['project']}, 'agents', 'roles', {}))
            roles = [{'role': one['role'], 'purpose': one['purpose'], 'prompts': one['prompts'],
                      'behind': one.get('behind', []), 'broken': one.get('broken', [])}
                     for one in cast(list[dict[str, Any]], found.get('roles') or [])]
        except (Stop, StoreError):
            roles = []
    named = {name for one in roles for name in one['prompts']}
    stored = [one for one in prompts.prompts() if one.name not in named]
    return {'roles': roles, 'stored': [{'name': one.name, 'newest': one.newest} for one in stored]}


PROMPT_READS: dict[str, Callable[[dict[str, str]], Any]] = {
    'prompts': lambda given: {'prompts': prompts.prompts()},
    'prompt': lambda given: prompts.prompt_version(given.get('name', ''), int(given['number'])
                                                   if given.get('number', '').isdigit() else None),
    'prompt-versions': _versions,
    'prompt-catalog': _catalog,
}


def demo_card() -> dict[str, Any]:
    """What the page's demo card says, written by `metaform demo` into the home it runs in, CLI-042; in any other home
    there is none, `{'demo': None}`."""
    try:
        found: Any = json.loads((home.home() / 'demo.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'demo': None}
    return {'demo': cast(dict[str, Any], found) if isinstance(found, dict) else None}


DISPATCH_LIMIT = 120.0  # the one wait for a dispatch verb; its own waits for an agent are at most 30 s each

# The newest line each running agent said in its thread, kept per session as (its seq, its text), so each read of the
# sessions takes only the lines begun since, and the line still being written, and never the whole thread again.
SAID: dict[str, tuple[int, str]] = {}


def said(given: dict[str, str], sessions: list[dict[str, Any]]) -> None:
    """Give each running session the newest line its agent said, `said`, for the speech bubble over its figure on the
    map. A line still streaming keeps its seq and grows in place, so the read starts at the newest line seen."""
    for session in sessions:  # an ended session's line is never asked for again
        if session.get('state') != 'running':
            SAID.pop(str(session.get('session_id')), None)
    running = [session for session in sessions if session.get('state') == 'running' and session.get('session_id')]
    project = home.project(given.get('project', ''))
    if not running or project is None:
        return
    try:
        store = Store(project.project_id, base=given.get('base') or None, module='dispatch')
        with store.tables(write=False) as tx:
            for session in running:
                key = str(session['session_id'])
                seq, text = SAID.get(key, (0, ''))
                for row in tx.rows('session_lines', {'session_id': key}, by=('session_id', 'seq'), limit=0,
                                   after=json.dumps([seq - 1, ''])).results:
                    if row['kind'] == 'agent_message_chunk' and int(row['seq']) >= seq and str(row['text']).strip():
                        seq, text = int(row['seq']), str(row['text'])
                SAID[key] = (seq, text)
                session['said'] = {'seq': seq, 'text': text} if text else None
    except (Stop, StoreError):
        return
ATTACH_LIMIT = 25 * 1024 * 1024  # the largest file the chat dock takes
ITEMS = 40  # the items of a node's brief listed at a time, newest first; the page asks for the next ones below
# The characters Claude Code keeps of a server's instructions and of each tool's description by default, MCP-029: its
# MCP documentation, https://code.claude.com/docs/en/mcp, under tool search for server authors.
HOST_LIMIT = 2048
# The name metaform install registers the MCP server under, so Claude Code names its tools mcp__metaform__<tool>, the
# names it lists to the model with tool search on: https://code.claude.com/docs/en/mcp, Scale with MCP tool search.
HOST_SERVER = 'metaform'
# Tokens are estimated from bytes: about four bytes of English text and JSON to a token. An estimate, said as one.
BYTES_PER_TOKEN = 4
TICKET_FIELDS = ('title', 'task', 'note', 'kind')


def ticket_fields(store: Store, work: WorkRecord) -> dict[str, str]:
    numbered = store.numbers_of('work', [work.id]).get(work.id)
    return {'title': str(numbered[1] or '') if numbered else '', 'task': work.task or '',
            'note': work.note or '', 'kind': work.kind or ''}


def held_work_revision(rows: list[dict[str, Any]]) -> str:
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def ticket_hold(store: Store, work_id: str) -> dict[str, Any]:
    bound = store.bound_base()
    with Store(store.project_id, base=bound.id if bound else None,
               module='map').tables(write=False) as tx:
        row = tx.get('ticket_settings', {'work_id': work_id})
    return {'hold': bool(row['hold']), 'hold_reason': row.get('hold_reason')} if row else {}


def ticket_revision(fields: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


MEMORY_READS = ('graph', 'orphaned', 'note', 'open_nodes')  # the memory module's reads the page makes
MEMORY_WRITES = ('create_entities', 'create_relations', 'add_observations', 'delete_entities', 'delete_observations',
                 'delete_relations', 'unjoin', 'lock', 'unlock')  # the person's memory commands, VIEW-031, CTX-023
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


def board_cutoff(given: dict[str, str], *, boards: list[dict[str, Any]] | None = None) -> str:
    """The time the board's done tickets start at: board_done_days ago, or the board's archive cutoff when that is
    later. A ticket done before it leaves the board, its commit read in the Archive; times compare as text, as
    `home.now` writes them."""
    project = home.project(given.get('project', ''))
    if project is None:
        raise Stop(f'No project {given.get("project", "")} is registered.', 'metaform list projects')
    folder = Path(project.path)
    days = int(settings.value('board_done_days', folder))
    since = datetime.fromtimestamp(time.time() - days * 86400, UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
    on = str(given.get('on') or '')
    if on:  # a named board keeps its own archive line, `map boards op=line`
        if boards is None:
            try:
                listed = cast(dict[str, Any], module_verb(given, 'map', 'boards', {}, chosen=bool(chosen_base(given))))
            except (Stop, StoreError):
                listed = {}
            boards = cast(list[dict[str, Any]], listed.get('boards') or [])
        line = next((str(one.get('line') or '') for one in boards
                     if one.get('name') == on), '')
        return max(since, line)
    return max(since, str(settings.value('board_line', folder) or ''))


BRIEF = 600  # characters of a ticket's task, note and resolution a page list read carries
BRIEF_FIELDS = ('task', 'note', 'resolution')


def brief_work(found: Any) -> Any:
    """A page work read's records with their task, note and resolution cut to BRIEF characters, marked `brief`: the
    card, the list and the figure show their first words, and the detail dialog reads the whole ticket by id,
    `ticket_detail`; `full=true` reads them whole. One ticket's task of 2 MB and the notes of 94 made the board's read
    4.5 MB, parsed on the page at every render (2026-10-20)."""
    data: Any = found.to_dict() if isinstance(found, Page) else found
    if not isinstance(data, dict):
        return cast(Any, found)
    results = cast(dict[str, Any], data).get('results')
    if not isinstance(results, list):
        return cast(dict[str, Any], data)
    cut: list[Any] = []
    for one in cast(list[Any], results):
        if isinstance(one, dict):
            record = cast(dict[str, Any], one)
            long = [name for name in BRIEF_FIELDS if isinstance(record.get(name), str) and len(record[name]) > BRIEF]
            if long:
                record = {**record, **{name: str(record[name])[:BRIEF] + '…' for name in long}, 'brief': True}
            cut.append(record)
        else:
            cut.append(one)
    return {**cast(dict[str, Any], data), 'results': cut}


def integration_for(store: Store, records: Sequence[WorkRecord]) -> dict[str, dict[str, Any]]:
    ctx = chassis.context('web', Path(store.project().path), project=store.project_id, surface='web')
    ctx.store = store
    result: dict[str, dict[str, Any]] = {}
    for _, read in chassis.provided(ctx.folder, 'dispatch.integration'):
        result.update({key: {'integration': value} for key, value in read(ctx, records).items()})
    return result


def with_glyphs(given: dict[str, str], found: Any) -> Any:
    """A work read's records, each with what the map module keeps on it under `map`, its glyph, runtime choice,
    eligible agents, the tickets it waits on and whether the person holds it, as `map work` shows it, VIEW-040, VIEW-042,
    MAP-058 and BASE-035. Its tables, STORE-045,
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
        named = [one for one in given.get('ids', '').split(',') if one]
        with store.tables(write=False) as tx:
            def rows(table: str, key: str, where: dict[str, str]) -> list[Any]:
                # the tickets a change named read their own rows by key, never every ticket's, VIEW-018
                if not named:
                    return list(tx.rows(table, where or None, limit=0).results)
                return [row for one in named for row in tx.rows(table, {**where, key: one}, limit=0).results]
            held: dict[str, dict[str, Any]] = {
                str(row['work_id']): {'glyph': row['glyph']} for row in rows('glyphs', 'work_id', {})}
            for row in rows('ticket_settings', 'work_id', {}):
                held.setdefault(str(row['work_id']), {}).update(agent=row['agent'], hold=bool(row['hold']),
                    board=row.get('board') or '',
                    **{field: row[field] for field in ('model', 'effort', 'fast', 'decision', 'hold_reason') if row.get(field) is not None})
            for row in rows('eligible', 'work_id', {}):
                held.setdefault(str(row['work_id']), {})['eligible'] = row['agents']
            # the tickets it waits on, `after_work`, so the card says Waiting on and Start all leaves it out, as every
            # agent starter does (UX review round 2, held-and-signals F2: the page never received it)
            try:
                for row in rows('after', 'work_id', {}):
                    held.setdefault(str(row['work_id']), {})['after_work'] = row['works']
            except StoreError:
                pass  # a map store below version 17 keeps no order between tickets
            # its item at its address, `<address>#<n>`, and its title, MCP-037, as the full-size dock's agent list says
            for row in rows('numbered', 'item_id', {'kind': 'work'}):
                held.setdefault(str(row['item_id']), {}).update(
                    item=reference(row['address'], row['number']), title=row['title'])
    except (Stop, StoreError):
        return page
    paths: dict[tuple[str, str], list[str]] = {}
    for ref in store.refs():
        if ref.key == 'path' and ref.value.replace('\\', '/').startswith('src/metaform/modules/web/page/'):
            paths.setdefault((ref.node.kind, ref.node.id), []).append(ref.value)
    for record in page.results:
        own_paths = paths.get((record.node_kind, record.node_id))
        if own_paths:
            held.setdefault(record.id, {})['paths'] = own_paths
    integration = integration_for(store, page.results)
    if not held and not integration:
        return page
    shown: list[dict[str, Any]] = []
    for record in page.results:
        data = record.to_dict()
        data.update(integration.get(record.id, {}))
        if record.id in held:
            data.setdefault('map', held[record.id])
        shown.append(data)
    return {**page.to_dict(), 'results': shown}


SPEC_CODE = re.compile(r'^(?:[A-Z]{2,6}-\d{3}|D\d{2,4})$')  # a record's code in specifications/*.md: VIEW-042, D120
HEX_REF = re.compile(r'^[0-9a-f]{8,32}$')  # a ticket's or a message's id, whole or its first characters
ITEM_REF = re.compile(r'^[\w.-]+#[0-9a-fA-F]{1,15}$')  # an item's reference, `<address>#<n>`, as the system agent names tickets
FILE_LINES = 80  # how much of a file a reference shows


def spec_record(folder: Path, code: str, specs: list[tuple[Path, list[str]]]) -> dict[str, Any] | None:
    """A record of the project's specifications by its code: its `### CODE` section, or the paragraph that opens with
    `**CODE.`, whole, with the file it is in; `specs` is each specification file's lines, read once for a batch. The
    rich/ folder is never read for this."""
    for path, lines in specs:
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


REFERENCE_WORDS = 300  # characters of a referenced ticket's or message's text a lookup carries


def short(value: Any) -> Any:
    """A text cut to REFERENCE_WORDS for a lookup's answer; anything else as it is."""
    return value[:REFERENCE_WORDS] + '…' if isinstance(value, str) and len(value) > REFERENCE_WORDS else value


def referenced(project: Any, refs: list[str]) -> dict[str, dict[str, Any] | None]:
    """What each reference stands for in a project, or None, in one pass: the specifications are read once for every
    code, and the tickets and the messages once for every id. A page draws hundreds of references at once, and one
    read of every ticket for each of them held the server long enough that a restart's readiness check gave up
    (2026-10-19)."""
    folder = Path(project.path)
    found: dict[str, dict[str, Any] | None] = {}
    codes = [ref for ref in refs if SPEC_CODE.match(ref)]
    if codes:
        specs = [(path, path.read_text(encoding='utf-8', errors='replace').splitlines())
                 for path in sorted((folder / 'specifications').glob('*.md'))]
        found.update((code, spec_record(folder, code, specs)) for code in codes)
    items = [ref for ref in refs if ITEM_REF.match(ref)]
    if items:
        found.update((ref, item_reference(project.project_id, ref)) for ref in items)
    ids = [ref for ref in refs if HEX_REF.match(ref)]
    if ids:
        store = Store(project.project_id)
        work = store.work(limit=0).results
        said: list[Any] | None = None  # the messages, read only for an id no ticket has
        for ref in ids:
            tickets = [record for record in work if record.id.startswith(ref)]
            if len(tickets) == 1:
                record = tickets[0]
                # the popover shows a reference's first words; the ticket opens whole from it (178 KB a batch of
                # whole records, 2026-10-20)
                found[ref] = {'kind': 'ticket', 'id': record.id,
                              'title': short(record.task or record.note or record.id),
                              'task': short(record.task), 'note': short(record.note), 'condition': record.condition,
                              'column': record.column, 'done': record.done, 'resolution': short(record.resolution),
                              'address': record.address}
                continue
            if said is None:
                said = [message for kind in ('question', 'message')
                        for message in store.messages(None, kind, None, limit=0).results]
            messages = [message for message in said if message.id.startswith(ref)]
            message = messages[0] if len(messages) == 1 else None
            found[ref] = None if message is None else {
                'kind': 'message', 'id': message.id, 'type': message.kind, 'title': short(message.text or ''),
                'text': short(message.text), 'choices': list(message.suggestions), 'answer': short(message.answer),
                'closed': message.closed, 'address': message.address}
    for ref in refs:
        if ref not in found:
            found[ref] = file_reference(folder, ref)
    return found


def board_of(project_id: str, work_id: str, base: str | None = None) -> str:
    """The named board a ticket is on, '' for the first board."""
    try:
        with Store(project_id, base=base or None, module='map').tables(write=False) as tx:
            row = tx.get('ticket_settings', {'work_id': work_id})
    except StoreError:
        return ''
    return str(row.get('board') or '') if row else ''


def item_reference(project_id: str, ref: str) -> dict[str, Any] | None:
    """The ticket numbered at `<address>#<n>`, as a lookup answers a ticket, with its board; None when that number
    holds no ticket, so the page leaves it plain text."""
    parsed = parse_reference(ref)
    if parsed is None:
        return None
    store = Store(project_id)
    try:
        held = store.item_at(*parsed)
        record = store.ticket(str(held['id'])).work if held and held.get('kind') == 'work' else None
    except (Stop, StoreError):
        return None
    if record is None:
        return None
    return {'kind': 'ticket', 'id': record.id, 'item': ref, 'title': short(record.task or record.note or record.id),
            'task': short(record.task), 'note': short(record.note), 'condition': record.condition,
            'column': record.column, 'done': record.done, 'resolution': short(record.resolution),
            'address': record.address, 'board': board_of(project_id, record.id)}


def file_reference(folder: Path, ref: str) -> dict[str, Any] | None:
    """A file of the project named by its path, its first lines shown; never one in the rich/ folder."""
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


def cli_result(given: dict[str, Any], module_id: str, verb: str, nouns: list[str],
               text: str | None = None) -> tuple[int, dict[str, Any]]:
    """One module verb run as `metaform <module> <verb>` runs it in the project's folder, the person's own surface:
    the status to answer with and its result, or its error and next step. A text goes after `--`."""
    project = home.project(str(given.get('project', '')))
    if project is None:
        return 404, {'error': f'No project {given.get("project", "")} is registered.', 'next': 'metaform list projects'}
    doing(f'metaform {module_id} {verb}')
    command = [sys.executable, '-m', 'metaform', module_id, verb, *nouns, '--json', '--project',
               project.project_id, *(['--', text] if text is not None else [])]
    # dispatch acts on the base the page shows; an intake follows the active base, whichever its finish makes active
    base = chosen_base(given) if module_id == 'dispatch' and verb != 'intake' else None
    try:
        done = subprocess.run(command, cwd=project.path, capture_output=True, text=True, encoding='utf-8',
                              stdin=subprocess.DEVNULL, timeout=DISPATCH_LIMIT, check=False, env=based(base))
    except (OSError, subprocess.TimeoutExpired) as error:
        return 500, {'error': f'metaform {module_id} {verb} did not finish: {error}'}
    if done.returncode == 0:
        try:
            found: Any = json.loads(done.stdout)
        except ValueError:
            return 200, {'said': done.stdout.strip()}
        return 200, cast(dict[str, Any], found) if isinstance(found, dict) else {'result': found}
    return 400, refusal(done)


# The dispatch verbs run in this server rather than as a command-line process: a process costs seconds of startup, and
# from the page a cancel took 6 s a step (the person, 2026-10-20). A verb that starts an agent keeps the command line, so
# the person's environment reaches the agent unchanged, BASE-052; stop, message and the rest keep it for now, since the
# command line's caller is not read as the person and their in-process answers differ (a stop with nothing running
# cancels the ticket's assignments in process, and is refused with the start to make from the command line).
IN_PROCESS = frozenset({'cancel'})


def in_process_result(given: dict[str, Any], verb: str, nouns: list[str], text: str | None = None) -> dict[str, Any]:
    """`cli_result` for a dispatch verb in IN_PROCESS, run in this process, `module_verb`: the command-line words, each
    positional one a required noun in order, each `name=value` its noun, and the text after `--` the noun that takes
    many words, give the arguments; the result is the JSON the command line prints. Stop and StoreError are the
    caller's to answer, as `refuse` does."""
    project = home.project(str(given.get('project', '')))
    if project is None:
        raise StoreError(f'No project {given.get("project", "")} is registered.', 'metaform list projects')
    chassis.refresh_modules()
    module = next((one for one in chassis.surface(Path(project.path)) if one.id == 'dispatch'), None)
    declared = next((one for one in module.verbs if one.name == verb), None) if module is not None else None
    if declared is None:
        raise Stop(f'dispatch {verb} is not on this project\'s surface.', 'metaform enable dispatch')
    named = {noun.name: noun for noun in declared.nouns}
    arguments: dict[str, Any] = {}
    positional: list[str] = []
    for word in nouns:
        key, equals, value = word.partition('=')
        if equals and key in named:
            arguments[key] = (value.lower() in ('true', '1', 'yes')) if named[key].kind == 'bool' else value
        else:
            positional.append(word)
    required = [noun.name for noun in declared.nouns if noun.required and not noun.many]
    arguments.update(dict(zip(required, positional)))
    if text is not None:
        many = next((noun.name for noun in declared.nouns if noun.many), None)
        if many is not None:
            arguments[many] = text
    found = module_verb(given, 'dispatch', verb, arguments, chosen=True)
    result: Any = json.loads(chassis.result_json(found))
    return cast(dict[str, Any], result) if isinstance(result, dict) else {'result': result}


def run_dispatch(project_id: str, verb: str, nouns: list[str], base: str | None = None) -> tuple[bool, dict[str, Any]]:
    """One dispatch verb run as the command line runs it, in the project's folder, on `base` when one is given:
    whether it succeeded, and its result."""
    project = home.project(project_id)
    if project is None:
        return False, {}
    doing(f'metaform dispatch {verb}')
    command = [sys.executable, '-m', 'metaform', 'dispatch', verb, *nouns, '--json', '--project', project.project_id]
    try:
        done = subprocess.run(command, cwd=project.path, capture_output=True, text=True, encoding='utf-8',
                              stdin=subprocess.DEVNULL, timeout=DISPATCH_LIMIT, check=False, env=based(base))
    except (OSError, subprocess.TimeoutExpired):
        return False, {}
    try:
        return done.returncode == 0, json.loads(done.stdout) if done.returncode == 0 else {}
    except ValueError:
        return done.returncode == 0, {}


def chosen_base(given: dict[str, Any]) -> str | None:
    """The base the page shows when it is not the project's active one, None otherwise. Dispatch runs on it, and the
    runner and agent it starts stay on it, since their ticket is there; on the active base nothing is bound here, and
    dispatch pins the runner to the base active as it starts, so it stays there whichever is made active later."""
    base, project = str(given.get('base') or ''), home.project(str(given.get('project', '')))
    if not base or project is None:
        return None
    active = home.active_base(project.project_id)
    return None if active is not None and active.id == base else base


def based(base: str | None) -> dict[str, str] | None:
    """The environment of a command run on `base`, METAFORM_BASE set to it; None, this process's own, with none. A
    command run for a write that is the person's carries this server's vouch too, `vouched`."""
    return vouched({**os.environ, BASE_VARIABLE: base} if base else None)


# The writes only the person makes: clearing, switching or removing the map, discarding an intake, the page's memory
# edits, locking and unlocking among them, the settings and modules, among them the person-only ones, and what
# dispatch keeps the person's own (an agent's permissions at its start, a ticket's model and effort, cancelling a
# ticket, `persons_own`). One sent by an agent's process is refused, CLI-011.
PERSONS_WRITES = frozenset({
    '/api/dispatch-permit', '/api/save-prompt',  # an answer to an agent's request or card; what agents are sent
    '/api/clear-project', '/api/remove-project', '/api/activate-base', '/api/remove-base', '/api/restore',
    '/api/board-wipe', '/api/board-restore',
    '/api/add-project', '/api/intake-discard', '/api/memory', '/api/settings', '/api/settings/reset', '/api/dispatch-prompts',
    '/api/dispatch-autostart', '/api/dispatch-agents', '/api/modules', '/api/dispatch-session-prompts',
    '/api/dispatch-start', '/api/dispatch-configure', '/api/dispatch-cancel', '/api/orchestration-call',
    # the board's own moves, a ticket's hold and glyph, and Distribute: a move out of Backlog or a hold let go
    # releases a ticket held for the person, which an agent posting as the page did (round 2, held-and-signals F4)
    '/api/move', '/api/ticket', '/api/distribute', '/api/unhold-all'})


class _Vouched(threading.local):
    """The server whose person's write this thread is serving, so the commands it runs carry its vouch."""
    server: Any = None


VOUCHED = _Vouched()


def vouched(env: dict[str, str] | None) -> dict[str, str] | None:
    """`env`, None for this process's own, with this server's vouch while the thread serves a write that is the
    person's: the command it runs then acts as the person, since its parent is this server, CLI-011."""
    server = VOUCHED.server
    if server is None:
        return env
    return {**(env if env is not None else os.environ), **server.vouch.environment()}


MODULE_ID = re.compile(r'^[A-Za-z0-9_][A-Za-z0-9_-]*$')  # a module's id as `enable` and `disable` take it
def metaform_cli(folder: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """One chassis command run as the command line runs it, in `folder`, so what it reads is that folder's: its
    settings, and the modules enabled now, a module enabled since this server started and the project's own among
    them. Raises Stop when it cannot be run or does not finish."""
    doing(f'metaform {args[0]}')
    try:
        return subprocess.run([sys.executable, '-m', 'metaform', *args], cwd=folder, capture_output=True, text=True,
                              encoding='utf-8', stdin=subprocess.DEVNULL, timeout=DISPATCH_LIMIT, check=False,
                              env=vouched(None))
    except (OSError, subprocess.TimeoutExpired) as error:
        raise Stop(f'metaform {args[0]} did not finish: {error}', f'metaform {args[0]}, in {folder}') from None


STORED = 'stored-list: '  # the line a process in a project's folder answers `stored_list_there` with


def stored_list(folder: Path, key: str, members: list[str], *, glue: bool) -> tuple[int, dict[str, Any]]:
    """Check and store a list setting this process declares, member by member, as `metaform set` checks and stores
    it: the status the page gets, with the refusal and its next step, or the notices set gave for what it kept."""
    if key not in settings.SCHEMA:
        return 404, {'error': f'No setting {key} here.', 'next': 'metaform config --show'}
    try:
        settings.checked(key, members, folder, typed=True)
        assigned = settings.put(key, members, folder, glue=glue)
    except (settings.SettingError, Stop) as error:
        return 400, {'error': str(error), 'next': getattr(error, 'next_step', None)}
    return 200, {'notices': list(assigned.notices)}


def stored_list_there(folder: Path, key: str, members: list[str], *, glue: bool) -> tuple[int, dict[str, Any]]:
    """`stored_list` run by a process in `folder`, which loads the modules enabled there, the project's own among
    them, as `metaform set` would, so a list this server does not declare is still stored member by member. Raises
    Stop when it cannot be run or does not answer."""
    program = 'from metaform.modules.web.server import store_list_here; store_list_here()'
    try:
        done = subprocess.run([sys.executable, '-c', program], cwd=folder, env=vouched(None),
                              input=json.dumps({'key': key, 'members': members, 'glue': glue}), capture_output=True, text=True, encoding='utf-8', timeout=DISPATCH_LIMIT, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise Stop(f'saving {key} did not finish: {error}', f'metaform config --show, in {folder}') from None
    answer = next((line[len(STORED):] for line in reversed(done.stdout.splitlines()) if line.startswith(STORED)), None)
    if done.returncode != 0 or answer is None:
        raise Stop(f'saving {key} did not finish: {(done.stderr or done.stdout).strip()}',
                   f'metaform config --show, in {folder}')
    status, said = json.loads(answer)
    return int(status), cast(dict[str, Any], said)


def store_list_here() -> None:
    """The process `stored_list_there` starts: it loads the modules enabled in its folder, then stores the list it
    reads on stdin and prints its answer on a line of its own."""
    given = json.loads(sys.stdin.read())
    folder = Path.cwd()
    with chassis.request_scope():
        chassis.surface(folder)  # loads the modules enabled here, the project's own among them, and their settings
        answer = stored_list(folder, str(given['key']), [str(item) for item in given['members']],
                             glue=given['glue'] is True)
    sys.stdout.write(f'\n{STORED}{json.dumps(answer)}\n')


def refusal(done: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    """A command's refusal as the page shows it: its error and its next step."""
    said = (done.stderr + done.stdout).strip().splitlines()
    return {'error': next((line[len('Error: '):] for line in said if line.startswith('Error: ')), ' '.join(said)),
            'next': next((line[len('Next: '):] for line in said if line.startswith('Next: ')), None)}


def refused(done: subprocess.CompletedProcess[str]) -> Stop:
    """A command's refusal as a Stop, with its next step or else the command that shows the settings."""
    said = refusal(done)
    return Stop(said['error'], said['next'] or 'metaform config --show')


def configured(folder: Path, *, listing: bool = True) -> dict[str, Any]:
    """Every setting of a folder as `metaform config --show --json` describes it, each with what its declaration adds
    for the settings screen, and every module as `metaform list modules` lists it, with whether it is on and its
    summary or the reason it did not load. Both were read as the command line in the folder, two processes and about
    a second on every page load (2026-10-20); they are read in this process now, which follows a module enabled or
    disabled since this server started as `module_verb` does, `refresh_modules`."""
    from metaform import loader
    chassis.refresh_modules()
    chassis.surface(folder)  # loads a module enabled since, whose settings describe then knows
    rows = cast(list[dict[str, Any]], json.loads(json.dumps(settings.describe(folder), default=str,
                                                            ensure_ascii=False)))  # as the command line prints them
    for row in rows:
        row.update(declared(row))
    modules: list[dict[str, Any]] = []
    for item in loader.discover() if listing else []:
        state = 'error' if item.problem else ('on' if item.enabled else 'off')
        summary = item.module.summary if item.module else (item.declared.summary if item.declared else None)
        text = item.problem or summary or ''
        stored = home.module_state(item.id)
        modules.append({'id': item.id, 'enabled': state == 'on' or (state == 'error' and stored is not False),
                        'place': item.place, 'summary': '' if state == 'error' else (text or ''),
                        'problem': (text or '') if state == 'error' else ''})
    return {'folder': str(folder), 'settings': rows, 'modules': modules, 'all_when_empty': list(settings.EMPTY_IS_ALL),
            'categories': [{'name': name, 'title': title, 'about': about} for name, title, about in settings.CATEGORIES]}


def declared(row: dict[str, Any]) -> dict[str, Any]:
    """What a setting's declaration says beyond what describe gives: its label and longer details, its bounds, its
    `--no-` form, and whether only the person changes it. A setting this server has not loaded, a module's in the
    project's own place, is given its label from its key and no more; the command that saves it still checks it."""
    setting = settings.SCHEMA.get(str(row.get('key')))
    if setting is None or setting.owner != row.get('owner'):
        return {'label': row.get('label') or str(row.get('key', '')).replace('_', ' ').capitalize(), 'details': '',
                'min': None, 'max': None, 'negative': None, 'person_only': None, 'exclusive': None, 'section': None}
    return {'label': setting.label, 'details': setting.details, 'min': setting.min, 'max': setting.max,
            'negative': setting.negative, 'person_only': setting.person_only, 'exclusive': setting.exclusive,
            'section': setting.section}


def switch_of(folder: Path, key: Any) -> tuple[str, str, str] | None:
    """A setting's switch, its `--no-` form and its kind, from this server's declarations, or else from the folder's
    `metaform config`, which has every module enabled now; None when the folder has no such setting."""
    if not isinstance(key, str) or not key:
        return None
    setting = settings.SCHEMA.get(key)
    if setting is not None:
        return setting.switch, setting.negative or f'--no-{setting.switch[2:]}', setting.kind
    done = metaform_cli(folder, 'config', '--show', '--json')
    if done.returncode != 0:
        raise refused(done)
    try:
        row = next((one for one in json.loads(done.stdout) if one.get('key') == key), None)
    except ValueError:
        row = None
    return None if row is None else (str(row['switch']), f'--no-{str(row["switch"])[2:]}', str(row['kind']))


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
    doing(f'{module_id} {name}')
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
    with on_base(chosen_base(given) if chosen else None):  # a module's own stores, and what it starts, on that base too
        return chassis.call(verb.run, ctx)


def merges_waiting(given: dict[str, Any]) -> dict[str, Any]:
    """Read explicit merges for the page's Review notice through `metaform dispatch merges`, in this process.
    Dispatch off the project's surface, or a store that cannot be read, means no merge waits."""
    try:
        found = module_verb(given, 'dispatch', 'merges', {}, chosen=bool(chosen_base(given)))
    except (Stop, StoreError):
        return {'merges': []}
    return cast(dict[str, Any], found) if isinstance(found, dict) else {'merges': []}


def role_choices(given: dict[str, Any]) -> dict[str, Any]:
    """Source-aware menu from public role and installed-adapter declarations; opening it starts no agent."""
    inventory = cast(dict[str, Any], module_verb(given, 'agents', 'roles', {}))
    installed: dict[str, Any]
    try:
        installed = cast(dict[str, Any], module_verb(given, 'orchestration', 'bmad', {}))
        available = True
    except Stop:
        installed = cast(dict[str, Any], {'installed': False, 'roles': [], 'problems': []})
        available = False
    bmad = {one['name']: one for one in installed.get('roles', [])}
    roles: list[dict[str, Any]] = []
    for one in inventory.get('authored', []):
        external = bmad.get(one['role'])
        source = 'BMAD' if external else 'Generated' if one['provider'] == 'agents' else 'Native'
        launch = {'gc': 'claim', 'functionality': 'assessment', 'role_creator': 'commission'}.get(one['role'], 'call')
        roles.append({**one, 'source_kind': source, 'launch': launch,
                      **({'installed': external} if external else {})})
    return {'roles': roles, 'launch_available': available, 'bmad': installed}


def call_role(given: dict[str, Any]) -> Any:
    """Use actual managed verbs, retaining independent assessment and GC-owned commissioning boundaries."""
    role = str(given['role']).removeprefix('metaform://role/')
    if role in ('gc', 'role_creator'):
        raise Stop('A GC claims a root ticket; a new role is commissioned from its recorded role request.',
                   'use the ticket start or GC commission operation')
    if role == 'functionality':
        return module_verb(given, 'orchestration', 'assess', {
            'assignment': given['assignment'], 'summary': given['task']}, chosen=True)
    arguments = {key: given[key] for key in ('assignment', 'task', 'result', 'context') if given.get(key)}
    return module_verb(given, 'orchestration', 'call', {**arguments, 'role': role}, chosen=True)


def _stage(store: Store, target: Node, condition: str) -> Any:
    """Set a part's stage on its state record, MAP-046: the node's open record with no task. Built, or none, clears it;
    a record the page made is then done, since a work record is never erased and its history says when the stage was
    set and cleared. A ticket is never a state record, so setting a stage never changes one."""
    stated = [record for record in store.work(target, None, True, limit=0).results if record.condition
              and not (record.task or '').strip() and record.node_kind == target.kind and record.node_id == target.id]
    kept = '' if condition == 'built' else condition
    if stated:
        changed = [store.finish_work(record.id, 'Built.') if not kept else store.edit_work(record.id, {'condition': kept})
                   for record in stated]  # every stated record changes; the first answers
        return changed[0]
    return store.add_work(target, kept, note='Set by the person on the page.') if kept else None


def sized(text: str) -> dict[str, Any]:
    """A text the page shows as an agent receives it, with its size in bytes and in characters."""
    return {'text': text, 'bytes': len(text.encode('utf-8')), 'chars': len(text)}


def weighed(entries: list[Any]) -> list[dict[str, Any]]:
    """Each entry of a list as the server gave it, with its size in bytes."""
    return [{'entry': entry, 'bytes': len(json.dumps(entry, ensure_ascii=False).encode('utf-8'))} for entry in entries]


def agent_cost(read: dict[str, Any]) -> dict[str, Any]:
    """What an agent pays before its first call, from what `chassis.mcp_reads` read: `tools`, each tool as tools/list
    gave it with `model_bytes`, what Claude Code sends the model for it (its `mcp__<server>__<tool>` name, description
    and input schema, annotations and _meta left out), largest first; and `paid`, with tool search, Claude Code's
    default, the connect message, the tool names and the tools marked `anthropic/alwaysLoad` in full (`deferred`), and
    without it, the connect message and every tool in full (`upfront`), each in bytes and in tokens at
    `BYTES_PER_TOKEN`; and the glossary, read once."""
    connect = str(cast(dict[str, Any], read['discover']).get('instructions') or '')
    tools: list[dict[str, Any]] = []
    for one in weighed(cast(list[Any], read['tools'])):
        entry = cast(dict[str, Any], one['entry'])
        name = str(entry.get('name') or '')
        meta = cast(dict[str, Any], entry.get('_meta') or {})
        called = f'mcp__{HOST_SERVER}__{name}'
        sent: dict[str, Any] = {'name': called, 'description': str(entry.get('description') or ''),
                                'input_schema': entry.get('inputSchema') or {}}
        tools.append({'name': name, 'description': str(entry.get('description') or ''), **one,
                      'name_bytes': len(called.encode('utf-8')),
                      'model_bytes': len(json.dumps(sent, ensure_ascii=False).encode('utf-8')),
                      'always': bool(meta.get('anthropic/alwaysLoad'))})
    for one in tools:
        one['model_tokens'] = round(int(one['model_bytes']) / BYTES_PER_TOKEN)
    tools.sort(key=lambda tool: -int(tool['model_bytes']))
    connect_bytes = len(connect.encode('utf-8'))
    deferred = connect_bytes + sum(int(one['name_bytes']) for one in tools) + sum(
        int(one['model_bytes']) for one in tools if one['always'])
    upfront = connect_bytes + sum(int(one['model_bytes']) for one in tools)
    glossary = len(cast(dict[str, str], read['texts']).get('metaform://metaform', '').encode('utf-8'))
    return {'tools': tools, 'paid': {
        'deferred': deferred, 'upfront': upfront, 'glossary': glossary, 'server': HOST_SERVER,
        'tokens': {key: round(value / BYTES_PER_TOKEN)
                   for key, value in (('deferred', deferred), ('upfront', upfront), ('glossary', glossary))}}}


def project_folder(given: dict[str, str]) -> tuple[str, Path]:
    """The registered project a read names, and its folder, whose settings and surface an agent there reads by."""
    project = home.project(given.get('project', ''))
    if project is None:
        raise StoreError(f'No project {given.get("project", "")} is registered.', 'metaform list projects')
    return project.project_id, Path(project.path)


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
    parser.add_argument('--origin', default='', help="the public origin, behind a Metaform Node's gate only")
    given = parser.parse_args(argv)
    # The gate secret is read once and taken out of the environment, so no process this server starts inherits it.
    given.gate = os.environ.pop(GATE_SECRET, '') or None
    if bool(given.origin) != bool(given.gate):
        log('--origin and METAFORM_GATE_SECRET go together: a public origin is served only behind the Node\'s gate')
        return 1
    if threading.current_thread() is threading.main_thread():  # only the main thread may set it; tests run main in one
        signal.signal(signal.SIGTERM, stopped)
    try:
        return serve(given)
    except Exception:  # noqa: BLE001  whatever ends the server is written to the log with its time
        log(f'Process {os.getpid()} stopped by an unhandled error:\n{traceback.format_exc().rstrip()}')
        return 1


def serve(given: argparse.Namespace) -> int:
    try:
        server = Server(given.bind, given.port, given.nonce, given.origin, given.gate)
    except OSError as error:
        log(f'cannot listen at {host_port(given.bind, given.port)}: {error}')
        return 1
    SERVING.append(server)
    server.record()
    # Each map.changed published in another process, a command, the MCP server or a runner, reaches every open page.
    listener = events.listen('web', server.changed)
    ready(server)
    log(f'Process {os.getpid()} started on port {server.port}, code {server.code[:12]}, schema version {SCHEMA_VERSION}')
    # The projects' services start beside the loop, not before it: `metaform web start` asks the server it was told
    # listens to answer within two seconds, and starting every project's services first left that request waiting.
    threading.Thread(target=projects_started, args=(server,), daemon=True).start()
    with listener:
        server.run()  # the stop signal ends the process; a hand-over to newer code ends `run`
    server.close_backgrounds()
    server.vouch.close()
    log(f'Process {os.getpid()} stopped')
    return 0


def projects_started(server: Server) -> None:
    """Each registered project's background services and its agent starter's first look."""
    for project in home.projects():
        server.watch_backgrounds(project.project_id)
        server.schedule_dispatch(project.project_id)


def stopped(number: int, frame: Any) -> None:
    """The stop signal, `metaform web stop`'s: write it to the log and end the process at once, as the signal's own
    default would. On Windows the signal ends the process before any handler runs, so no line is written there."""
    log(f'Process {os.getpid()} stopped by {signal.Signals(number).name}')
    for server in SERVING:  # its vouch goes with it
        server.vouch.close()
    os._exit(0)


def ready(server: Server) -> None:
    """Tell `metaform web` the server listens: one line on the pipe it inherited as standard output, which is then
    pointed at the log so nothing else is ever written to the pipe by chance, VIEW-002. Under the watchdog the pipe
    is kept, never inherited, for the server to say why it ends, `overran`; it closes as the server ends."""
    sys.stdout.write(json.dumps({'pid': os.getpid(), 'port': server.port}) + '\n')
    sys.stdout.flush()
    if server.supervisor is not None:
        server.told = os.dup(sys.stdout.fileno())
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())


if __name__ == '__main__':
    sys.exit(main())
