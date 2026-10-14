"""The table's stage, BASE-066: the runner's own watch server and headless renderer, so a table is seen without the
person's page.

The watch server is a small standard-library HTTP server on the loopback only, started by the runner and stopped
with it. It serves the watch page, the scene module, and the three.js files and the figures (agents3d.js) of the web
module, read and never changed; `/state` is the table as the scene draws it, read fresh from the module's tables on
each poll; `/look?seat=<position>&token=<token>` is a seat's view from its own eyes, a PNG, for a seat's `look`
called in another process, the runner's token keeping it to callers that read the table's row. Its address and
token are kept on the table, `scene`, while the runner runs, and `status` shows the address.

The renderer is one headless Chromium, through Playwright, with WebGL in software (SwiftShader), started the first
time a seat looks and kept until the runner stops. It loads the stage's own render page and draws a seat's eye view
from the same state. Playwright and its Chromium are optional: without them a look gives what is in view as words.
"""
from __future__ import annotations

import base64
import json
import logging
import mimetypes
import queue
import secrets
import threading
from concurrent.futures import Future
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, urlsplit

from metaform.data import Store

from . import scene

log = logging.getLogger(__name__)

HOST = '127.0.0.1'
RENDER_WAIT = 60.0  # seconds a look waits for its picture
LAUNCH_ARGS = ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist']


def own_files() -> Path:
    return Path(str(resources.files(__name__.rpartition('.')[0]) / 'resources' / 'scene'))


def web_files() -> Path:
    """The web module's folder, whose vendored three.js and figures the stage serves, read only."""
    return Path(str(resources.files('metaform.modules.web')))


def inside(root: Path, path: str) -> Path | None:
    """A file under `root` by its path in a request, or None for one outside it or missing."""
    found = (root / path).resolve()
    return found if found.is_file() and found.is_relative_to(root.resolve()) else None


class Unseen(Exception):
    """No picture could be drawn; the message says why."""


class Renderer:
    """One headless Chromium in its own thread, drawing eye views one at a time."""

    def __init__(self, url: str) -> None:
        self.url = url
        self.jobs: queue.Queue[tuple[dict[str, Any], int, Future[str]] | None] = queue.Queue()
        self.thread: threading.Thread | None = None
        self.failed: str | None = None
        self.lock = threading.Lock()

    def shot(self, state: dict[str, Any], position: int) -> str:
        """The seat's eye view as base64 PNG; Unseen when it cannot be drawn."""
        with self.lock:
            if self.failed:
                raise Unseen(self.failed)
            if self.thread is None:
                self.thread = threading.Thread(target=self.work, daemon=True, name='roundtable-renderer')
                self.thread.start()
        done: Future[str] = Future()
        self.jobs.put((state, position, done))
        try:
            return done.result(RENDER_WAIT)
        except TimeoutError:
            raise Unseen(f'the picture took longer than {int(RENDER_WAIT)} seconds') from None

    def work(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.fail('Playwright is not installed, so the table draws no pictures: pip install playwright, then '
                      'playwright install chromium.')
            return
        try:
            with sync_playwright() as driver:
                browser = driver.chromium.launch(args=LAUNCH_ARGS)
                page = browser.new_page(viewport={'width': scene.EYE_SIZE[0], 'height': scene.EYE_SIZE[1]})
                page.goto(f'{self.url}/render.html')
                page.wait_for_function('window.ready === true', timeout=30_000)
                while True:
                    job = self.jobs.get()
                    if job is None:
                        break
                    state, position, done = job
                    try:
                        drawn = str(page.evaluate('([state, position]) => window.shot(state, position)',
                                                  [state, position]))
                        done.set_result(drawn.partition(',')[2])
                    except Exception as error:  # noqa: BLE001  one failed picture, told to the seat that looked
                        done.set_exception(Unseen(str(error).splitlines()[0]))
                browser.close()
        except Exception as error:  # noqa: BLE001  no browser: every look gives words only
            self.fail(f'the headless browser did not start: {str(error).splitlines()[0] if str(error) else error}')

    def fail(self, why: str) -> None:
        log.warning('Roundtable renderer: %s', why)
        self.failed = why
        while True:
            try:
                job = self.jobs.get_nowait()
            except queue.Empty:
                return
            if job is not None:
                job[2].set_exception(Unseen(why))

    def stop(self) -> None:
        if self.thread is not None:
            self.jobs.put(None)
            self.thread.join(10)


class Stage:
    """The watch server and the renderer of one table's runner."""

    def __init__(self, held: Store, number: int) -> None:
        self.held = held
        self.number = number
        self.token = secrets.token_hex(12)
        stage = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                return

            def do_GET(self) -> None:
                stage.answer(self)

        self.server = ThreadingHTTPServer((HOST, 0), Handler)
        self.server.daemon_threads = True
        self.url = f'http://{HOST}:{self.server.server_address[1]}'
        self.renderer = Renderer(self.url)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True, name='roundtable-stage')

    def start(self) -> dict[str, str]:
        self.thread.start()
        return {'url': self.url, 'token': self.token}

    def stop(self) -> None:
        self.renderer.stop()
        self.server.shutdown()
        self.server.server_close()

    def look(self, position: int) -> str:
        """A seat's eye view, base64 PNG, drawn from the table as it is now; Unseen when none can be drawn."""
        return self.renderer.shot(scene.state(self.held, self.number), position)

    # ------------------------------------------------------------------------------------------- requests

    def answer(self, request: BaseHTTPRequestHandler) -> None:
        split = urlsplit(request.path)
        path = split.path
        try:
            if path in ('/', '/index.html'):
                self.send(request, (own_files() / 'watch.html').read_bytes(), 'text/html; charset=utf-8')
            elif path == '/render.html':
                self.send(request, (own_files() / 'render.html').read_bytes(), 'text/html; charset=utf-8')
            elif path == '/scene.js':
                self.send(request, (own_files() / 'scene.js').read_bytes(), 'text/javascript')
            elif path == '/state':
                body = json.dumps(scene.state(self.held, self.number)).encode()
                self.send(request, body, 'application/json')
            elif path == '/look':
                self.answer_look(request, parse_qs(split.query))
            elif path == '/page/agents3d.js':
                self.send(request, (web_files() / 'page' / 'agents3d.js').read_bytes(), 'text/javascript')
            elif path.startswith('/vendor/') and (found := inside(web_files() / 'vendor', path[len('/vendor/'):])):
                kind = 'text/javascript' if found.suffix in ('.js', '.mjs') else (
                    mimetypes.guess_type(found.name)[0] or 'application/octet-stream')
                self.send(request, found.read_bytes(), kind)
            else:
                self.send(request, b'Not found.', 'text/plain', status=404)
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as error:  # noqa: BLE001  a failed request is answered and the stage goes on
            log.warning('Roundtable %s stage: %s failed: %s', self.number, path, error)
            self.send(request, str(error).encode(), 'text/plain', status=500)

    def answer_look(self, request: BaseHTTPRequestHandler, query: dict[str, list[str]]) -> None:
        if query.get('token', [''])[0] != self.token:
            self.send(request, b'Not this table\'s token.', 'text/plain', status=403)
            return
        try:
            picture = self.look(int(query.get('seat', ['-1'])[0]))
        except Unseen as error:
            self.send(request, str(error).encode(), 'text/plain', status=503)
            return
        self.send(request, base64.b64decode(picture), 'image/png')

    @staticmethod
    def send(request: BaseHTTPRequestHandler, body: bytes, kind: str, status: int = 200) -> None:
        request.send_response(status)
        request.send_header('Content-Type', kind)
        request.send_header('Content-Length', str(len(body)))
        request.send_header('Cache-Control', 'no-store')
        request.end_headers()
        request.wfile.write(body)


def fetch_look(given: Any, position: int) -> str:
    """A seat's eye view from the table's runner, in another process: base64 PNG; Unseen when the runner is not
    running or draws none."""
    import urllib.error
    import urllib.request
    held = cast(dict[str, Any], given) if isinstance(given, dict) else {}
    if not held.get('url'):
        raise Unseen('the table\'s runner is not running, so no picture was drawn')
    address = f'{held["url"]}/look?seat={position}&token={held.get("token") or ""}'
    direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # the loopback, never through a proxy
    try:
        with direct.open(address, timeout=RENDER_WAIT + 5) as answer:
            return base64.b64encode(answer.read()).decode()
    except urllib.error.HTTPError as error:
        raise Unseen(error.read(400).decode(errors='replace') or f'HTTP {error.code}') from None
    except OSError as error:
        raise Unseen(f'the table\'s runner did not answer: {error}') from None
