"""The chat's MCP Apps, `io.modelcontextprotocol/ui`: the web GUI as an MCP host for the person, so a Metaform tool call
whose tool declares a view (`_meta.ui.resourceUri`) shows that view in the chat's thread, MCP-037 and VIEW-039.

  GET  /api/mcp-apps   the tools of the folder's MCP server that declare a view, {tool: {uri, visibility}}, and every
                       view it lists (its resources of type text/html;profile=mcp-app), for the chat's gallery
  GET  /api/mcp-app    one view's document, ?uri=ui://..., under the content policy its `_meta.ui.csp` asks for: shown
                       in a sandboxed frame with an opaque origin, it reaches nothing but its host, the page
  POST /api/mcp-call   {tool, arguments, work_id?, session?}: one tools/call a view asks its host for, through the
                       folder's MCP server started with the identity of the thread's agent session, as that agent's
                       own calls are made; a tool hidden from views (visibility without "app") is refused

The server is the folder's own, the one AI tools are registered with, reached through `chassis.mcp_connect`, and kept
open for a few minutes for each identity, since a view reads several times as it is used. Every request declares the
extension with its MIME type, as a host that renders the views does. Sources: the ext-apps specification
2026-01-26 (stable), its host requirements on visibility, the sandbox and the content policy.
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from metaform import home
from metaform import module as chassis
from metaform.module import Stop

if TYPE_CHECKING:
    from .server import Handler

EXTENSION = 'io.modelcontextprotocol/ui'
MIME = 'text/html;profile=mcp-app'
META = {'_meta': {'io.modelcontextprotocol/clientCapabilities': {'extensions': {EXTENSION: {'mimeTypes': [MIME]}}}}}
IDLE = 300.0  # seconds a connection with no request is kept before it is closed
LIMIT = 30.0  # seconds one request may take
PATHS = ('/api/mcp-apps', '/api/mcp-app', '/api/mcp-call')


@dataclass
class Held:
    """One open connection to the folder's MCP server for one identity, used by one request at a time."""
    session: Any
    lock: threading.Lock = field(default_factory=threading.Lock)
    used: float = field(default_factory=time.monotonic)
    tools: dict[str, dict[str, Any]] | None = None


POOL: dict[tuple[str, str], Held] = {}
POOL_LOCK = threading.Lock()


def connection(folder: Path, identity: dict[str, str]) -> Held:
    """The open connection for this folder and identity, started and discovered when there is none or it has
    stopped; connections idle longer than IDLE are closed as one is asked for."""
    key = (str(folder), json.dumps(identity, sort_keys=True))
    now = time.monotonic()
    with POOL_LOCK:
        for other, held in list(POOL.items()):
            if other != key and now - held.used > IDLE and not held.lock.locked():
                POOL.pop(other, None)
                held.session.close()
        held = POOL.get(key)
        if held is not None and held.session.process.poll() is None:
            held.used = now
            return held
        POOL.pop(key, None)
    session = chassis.mcp_connect(folder, **identity)
    try:
        session.request('server/discover', dict(META), deadline=time.monotonic() + LIMIT)
    except (OSError, ValueError, RuntimeError, TimeoutError, EOFError) as error:
        session.close()
        raise Stop(f'The MCP server did not answer: {error}.', 'metaform mcp serve') from None
    held = Held(session)
    with POOL_LOCK:
        POOL[key] = held
    return held


def ask(held: Held, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """One request on a held connection; a connection that fails is dropped, so the next request starts afresh."""
    with held.lock:
        held.used = time.monotonic()
        try:
            return held.session.request(method, {**META, **(params or {})}, deadline=time.monotonic() + LIMIT)
        except (OSError, ValueError, TimeoutError, EOFError) as error:
            with POOL_LOCK:
                for key, one in list(POOL.items()):
                    if one is held:
                        POOL.pop(key, None)
            held.session.close()
            raise Stop(f'The MCP server did not answer: {error}.', 'metaform mcp serve') from None
        except RuntimeError as error:  # the server's own error for this request; the connection stays
            raise Stop(str(error), 'metaform help mcp') from None


def every(held: Held, method: str, key: str) -> list[dict[str, Any]]:
    listed: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:  # a server may list in pages, each naming the next
        got = ask(held, method, {'cursor': cursor} if cursor else {})
        listed += cast(list[dict[str, Any]], got.get(key) or [])
        cursor = cast(str | None, got.get('nextCursor'))
        if not cursor:
            return listed


def tools(held: Held) -> dict[str, dict[str, Any]]:
    """The server's tools by name, read once per connection."""
    if held.tools is None:
        held.tools = {str(one.get('name')): one for one in every(held, 'tools/list', 'tools')}
    return held.tools


def ui_of(tool: dict[str, Any]) -> dict[str, Any]:
    meta = cast(dict[str, Any], tool.get('_meta') or {})
    return cast(dict[str, Any], meta.get('ui') or {})


def folder_of(given: dict[str, Any]) -> Path:
    project = home.project(str(given.get('project') or ''))
    if project is None:
        raise Stop(f'No project {given.get("project") or ""} is registered.', 'metaform list projects')
    return Path(project.path)


def identity(given: dict[str, Any]) -> dict[str, str]:
    """The METAFORM_* names of the thread's agent session, as its runner gave them to its own MCP server, so a view's
    call is made as that agent's would be: its runner's id, its ticket and its role. With no thread, none: the view
    then reads as the person's page does. A session that is not the ticket's is refused."""
    work, session = str(given.get('work_id') or ''), str(given.get('session') or '')
    if not work:
        return {}
    from .server import module_verb
    found = cast(dict[str, Any], module_verb({'project': str(given.get('project') or '')}, 'dispatch', 'sessions',
                                             {'id': work, 'thread': False}))
    rows = cast(list[dict[str, Any]], found.get('sessions') or [])
    row = next((one for one in rows if one.get('session_id') == session), None) if session else (rows[-1] if rows else None)
    if row is None:
        raise Stop('That session is not one of this ticket\'s.', f'metaform dispatch sessions id={work}')
    state = cast(dict[str, Any], cast(dict[str, Any], found.get('states') or {}).get(str(row['session_id'])) or {})
    about = state.get('about')
    # the role its runner gave it: an intake, the person's system agent, a talk, or else a worker, whose authority
    # the person may hold back (roles_without_authority), so a view of its thread is held back alike
    role = 'intake' if work.startswith('intake-') else 'system' if about == 'system' else 'talk' if about else 'worker'
    return {'METAFORM_ROLE': role, 'METAFORM_WORK': work,
            **({'METAFORM_SESSION': str(row['runner'])} if row.get('runner') else {})}


def policy(meta: dict[str, Any]) -> str:
    """The content policy a view asks for in `_meta.ui.csp`, and nothing more: its own inline code, the domains it
    names for resources, connections, frames and its base, and no other origin, not even the page's."""
    csp = cast(dict[str, Any], cast(dict[str, Any], meta.get('ui') or {}).get('csp') or {})

    def named(key: str) -> str:
        found = [str(one) for one in cast(list[Any], csp.get(key) or []) if str(one).startswith('https://')
                 and not any(char in str(one) for char in " ;'\"")]
        return ' '.join(found)

    resources, connect, frames, base = (named(key) for key in ('resourceDomains', 'connectDomains', 'frameDomains',
                                                               'baseUriDomains'))
    return '; '.join([
        "default-src 'none'", f"script-src 'unsafe-inline' blob: {resources}".strip(),
        f"style-src 'unsafe-inline' {resources}".strip(), f'img-src data: blob: {resources}'.strip(),
        f'font-src data: {resources}'.strip(), f'media-src data: blob: {resources}'.strip(),
        f"connect-src {connect or chr(39) + 'none' + chr(39)}", 'worker-src blob:',
        f"frame-src {frames or chr(39) + 'none' + chr(39)}", f"base-uri {base or chr(39) + 'none' + chr(39)}",
        "form-action 'none'"])


def answer(handler: Handler, method: str, path: str, query: dict[str, list[str]]) -> None:
    given: dict[str, Any] = {key: values[-1] for key, values in query.items() if key != 't'}
    try:
        if path == '/api/mcp-apps' and method == 'GET':
            return listed(handler, given)
        if path == '/api/mcp-app' and method == 'GET':
            return document(handler, given)
        if path == '/api/mcp-call' and method == 'POST':
            if not handler.same_origin():
                return handler.send(403, {'error': "A view's call is taken only from the web GUI's own page."})
            body: Any = handler.json_body()
            if not isinstance(body, dict):
                raise ValueError(body)
            return call(handler, cast(dict[str, Any], body))
        return handler.send(404, {'error': f'Nothing at {path} for {method}.'})
    except Stop as error:
        handler.send(400, {'error': str(error), 'next': error.next_step})
    except ValueError:
        handler.send(400, {'error': 'The body is not what this endpoint takes.'})


def listed(handler: Handler, given: dict[str, Any]) -> None:
    """The views the folder's server offers: each tool that declares one, and each view, for the gallery."""
    held = connection(folder_of(given), {})
    shown = {name: {'uri': ui_of(tool).get('resourceUri'), 'visibility': ui_of(tool).get('visibility') or ['model', 'app'],
                    'title': tool.get('title') or name}
             for name, tool in tools(held).items() if ui_of(tool).get('resourceUri')}
    views: list[dict[str, Any]] = [{'uri': one.get('uri'), 'name': one.get('name'),
                                    'description': one.get('description') or '', 'meta': one.get('_meta') or {}}
             for one in every(held, 'resources/list', 'resources')
             if str(one.get('uri', '')).startswith('ui://') and str(one.get('mimeType', '')).startswith('text/html')]
    handler.send(200, {'tools': shown, 'views': views})


def document(handler: Handler, given: dict[str, Any]) -> None:
    """One view's document, as resources/read gives it, served under the policy it asks for, to a sandboxed frame."""
    uri = str(given.get('uri') or '')
    if not uri.startswith('ui://'):
        raise Stop('A view is read by its ui:// address.', 'GET /api/mcp-apps lists them')
    held = connection(folder_of(given), {})
    contents = cast(list[dict[str, Any]], ask(held, 'resources/read', {'uri': uri}).get('contents') or [])
    found = next((one for one in contents if str(one.get('mimeType', '')).startswith('text/html')), None)
    if found is None or not isinstance(found.get('text'), str):
        raise Stop(f'{uri} is not a view: it has no HTML.', 'GET /api/mcp-apps lists the views')
    body = str(found['text']).encode('utf-8')
    handler.reply(200, body, 'text/html; charset=utf-8', {
        'Content-Security-Policy': policy(cast(dict[str, Any], found.get('_meta') or {})),
        'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer'})


def call(handler: Handler, given: dict[str, Any]) -> None:
    """A view's tools/call, made as the thread's agent session through the folder's server. The tool is one the server
    lists and does not keep from views; its result goes back to the view as the server gave it."""
    name, given_arguments = given.get('tool'), cast(Any, given.get('arguments') or {})
    if not isinstance(name, str) or not name:
        raise Stop('A view calls a tool by its name.', 'GET /api/mcp-apps')
    if not isinstance(given_arguments, dict):
        raise Stop('A tool\'s arguments are an object.', 'GET /api/mcp-apps')
    arguments = cast(dict[str, Any], given_arguments)
    held = connection(folder_of(given), identity(given))
    tool = tools(held).get(name)
    if tool is None:
        return handler.send(404, {'error': f'The MCP server here offers no tool {name}.', 'next': 'GET /api/mcp-apps'})
    if 'app' not in cast(list[Any], ui_of(tool).get('visibility') or ['model', 'app']):
        return handler.send(403, {'error': f'{name} is not offered to views.', 'next': 'call it from the agent'})
    handler.send(200, ask(held, 'tools/call', {'name': name, 'arguments': arguments}))
