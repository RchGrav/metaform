"""MCP Apps, `io.modelcontextprotocol/ui`: the map, a node, an agent's trace and the glossary shown inside the AI
tool's conversation, MCP-037.

Four views, each a `ui://` resource of type `text/html;profile=mcp-app`:

- `ui://metaform/map`, shown by `map_where` and `map_roots`: the web GUI's own page, its 2D and 3D maps, run in the AI
  tool's sandboxed frame and focused on the address the call names. It is the page's files built into one document,
  since a frame loads nothing from elsewhere, by `scripts/build_map_view.mjs`, which the wheel build runs
  (`scripts/hatch_views.py`). The document records the files it was made of and their SHA-256; where it is missing,
  or older than the page installed beside it, the node view stands in with a line saying so.
- `ui://metaform/node`, shown by `map_item` and `map_node`: the node, what relies on it and what it relies on, with
  its numbered items (#n, title, why), each opened in place.
- `ui://metaform/trace`, shown by `dispatch_sessions` and `dispatch_start`: a ticket's agent sessions and their
  threads, asked for again while the view is on screen and read again only after a change to the ticket, `Traces`,
  so the person watches the agent work.
- `ui://metaform/glossary`, shown by `metaform_instructions` and `map_glossary`: the call's own answer, then the terms
  of metaform://metaform as written, then the tools and the rules metaform://tools gives, searchable.

All speak to their host through the official MCP Apps SDK, `@modelcontextprotocol/ext-apps`, kept here as
`ext-apps.js`, under `bridge.js`, which they share. A view reads through `metaform_view`, a tool only views call
(`visibility: ["app"]`), so the model's tool list stays as it is. The picture is shared both ways: when the person
selects a node, the view tells the agent in one line which Address they are looking at (`ui/update-model-context`);
when the agent names an Address in a call, an open view turns to it (`metaform_view`'s `focus` read), and a host that
calls a view's own tools (the draft's App-Provided Tools) can turn it directly. A host gives a view no push from the
server (ext-apps 2.0.3's App hears tool-input, tool-result, tool-cancelled and host-context changes, nothing more), so
a view on screen asks again on its clock, bridge.js `poll`; what the server does for each ask is decided by the events
it heard: `focus` is this process's own state, and `trace` reads the store only when a change to the ticket came after
the view's last read, `Traces`. A read held open until a change would end the clock, but a host that carries a view's
calls one at a time, as the check host in the tests does, would then hold every other read of the view behind it. Only an AI tool that declares the
extension is offered any of this, unless the person sets `mcp_apps_offer` to always; every other tool's result is the
full text it always was.

Sources, read 2026-10-12: github.com/modelcontextprotocol/ext-apps specification/2026-01-26/apps.mdx (stable) and
specification/draft/apps.mdx (App-Provided Tools, listing-level `_meta.ui`), the SDK's release 2.0.3; the overview at
modelcontextprotocol.io/extensions/apps/overview; the Python SDK 2.2's `mcp.server.apps`, whose constants these are.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import threading
import uuid
import weakref
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any, cast

import anyio
import anyio.lowlevel

from metaform import events

EXTENSION = 'io.modelcontextprotocol/ui'
MIME = 'text/html;profile=mcp-app'
MAP = 'ui://metaform/map'
NODE = 'ui://metaform/node'
TRACE = 'ui://metaform/trace'
GLOSSARY = 'ui://metaform/glossary'
TOOL = 'metaform_view'  # the views' own tool, hidden from the model
# The tools whose call opens each view: the map from a read of an address or of the map's entry; the node from a read
# of one item or of everything at one node; the trace from a ticket's sessions or the start of its agent; the glossary
# from the guide an agent reads first or the project's own glossary.
SHOWN_BY = {'map_where': MAP, 'map_roots': MAP, 'map_item': NODE, 'map_node': NODE,
            'dispatch_sessions': TRACE, 'dispatch_start': TRACE, 'metaform_instructions': GLOSSARY,
            'map_glossary': GLOSSARY}
NAMES = {MAP: ('Map view', 'The 2D and 3D map, focused on the address map_where reads.'),
         NODE: ('Node view', 'One node\'s brief with its numbered items, as map_item reads them.'),
         TRACE: ('Agent trace', 'A ticket\'s agent sessions and their threads, followed while the agent works.'),
         GLOSSARY: ('Glossary', 'The terms, tools and rules every agent works by, as metaform://metaform and metaform://tools hold them.')}
FILES = {NODE: 'node.html', TRACE: 'trace.html', GLOSSARY: 'glossary.html'}  # the views kept as written
# The display modes each view offers its host (MCP Apps' availableDisplayModes): the trace also floats beside the
# conversation (pip), so the person can watch an agent while they talk.
MODES = {MAP: ['inline', 'fullscreen'], NODE: ['inline', 'fullscreen'], TRACE: ['inline', 'fullscreen', 'pip'],
         GLOSSARY: ['inline', 'fullscreen']}
# What each view asks of its host's sandbox (MCP Apps UIResourceMeta): no origin at all, since every byte it runs is in
# the document and every read goes through the host; the clipboard, to copy an Address, which a view checks before it
# offers; and the border, which the map does without because it draws its own frame.
CSP: dict[str, list[str]] = {'connectDomains': [], 'resourceDomains': [], 'frameDomains': [], 'baseUriDomains': []}
# The arguments of a model's call that name the Address it is discussing, in the order they are looked for; an open
# view turns to it (`focus`).
FOCUS_ARGUMENTS = ('address', 'item', 'node', 'element', 'receiver')
CONFIG = '<script type="application/json" id="metaform-view">{}</script>'
TOKENS = '<style id="metaform-tokens"></style>'
SDK = '<script>/*sdk*/</script>'
BRIDGE = '<script>/*bridge*/</script>'
SHARED = '<style>/*view*/</style>'  # view.css, what the trace and glossary views share
BUILT = 'map.html'  # the map view as scripts/build_map_view.mjs writes it; not kept in the repository
INPUTS = re.compile(r'<script type="application/json" id="metaform-view-inputs">(.*?)</script>')


def _views() -> Traversable:
    return resources.files('metaform.modules.mcp') / 'resources' / 'views'


def meta(uri: str) -> dict[str, Any]:
    """A view's `_meta.ui` (MCP Apps UIResourceMeta), the same in the resource list, for a host that reviews it when it
    connects, and on the read, which takes precedence: its content policy, the permissions it asks for, and whether
    the host draws a border round it."""
    return {'ui': {'csp': {key: list(value) for key, value in CSP.items()},
                   'permissions': {'clipboardWrite': {}}, 'prefersBorder': uri != MAP}}


def discussed(arguments: dict[str, Any]) -> str | None:
    """The Address a model's call names, which an open view turns to: the first of `FOCUS_ARGUMENTS` given as text,
    an item's `<address>#<n>` kept whole and map_node's `element:` or `type:` taken off; None when the call names
    none, or names a join, which has no Address of its own."""
    for name in FOCUS_ARGUMENTS:
        value = arguments.get(name)
        if not isinstance(value, str) or not value.strip():
            continue
        kind, colon, rest = value.strip().partition(':')
        if not colon:
            return value.strip()
        return rest.strip() or None if kind in ('element', 'type') else None
    return None


def supported(capabilities: Any) -> bool:
    """Whether the request's client renders MCP Apps: it declares the extension with the app MIME type, as the SDK's
    `client_supports_apps` checks."""
    extensions: Any = getattr(capabilities, 'extensions', None)
    declared: Any = cast(dict[str, Any], extensions).get(EXTENSION) if isinstance(extensions, dict) else None
    mimes: Any = cast(dict[str, Any], declared).get('mimeTypes') if isinstance(declared, dict) else None
    return isinstance(mimes, list) and MIME in cast(list[Any], mimes)


def tokens() -> str:
    """The page's theme tokens: every top-level `:root` rule of the web module's app.css, so a view wears the page's
    colors, sizes and fonts. Empty when the web module's files are not installed."""
    css = resources.files('metaform.modules.web') / 'page' / 'app.css'
    if not css.is_file():
        return ''
    text = re.sub(r'/\*.*?\*/', '', css.read_text(encoding='utf-8'), flags=re.DOTALL)
    kept: list[str] = []
    depth = start = 0
    for at, char in enumerate(text):
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                rule = text[start:at + 1].strip()
                if rule.startswith(':root'):
                    kept.append(rule)
                start = at + 1
    return '\n'.join(kept)


_checked: dict[str, Any] = {}  # the last check of the built map view: what it saw, and whether it was current


def recorded(view: Traversable) -> dict[str, Any] | None:
    """What a built map view records of the files it was made of: their paths under `metaform/modules`, in the order
    they were hashed, and the SHA-256; None when it records nothing."""
    with view.open('r', encoding='utf-8') as opened:
        found = INPUTS.search(opened.read(64_000))
    return None if found is None else cast(dict[str, Any], json.loads(found.group(1)))


def current(said: dict[str, Any], modules: Traversable) -> bool | None:
    """Whether the files a built map view records, read under `modules`, still hash to what it records, as
    `scripts/build_map_view.mjs` hashed them: each path, a NUL, its bytes, a NUL. None when one of them is not there,
    such as the web module's files in a wheel without it. Read by the wheel build too (scripts/hatch_views.py)."""
    names = [str(name) for name in said.get('files', [])]
    files = [modules.joinpath(*name.split('/')) for name in names]
    if not all(one.is_file() for one in files):
        return None
    digest = hashlib.sha256()
    for name, one in zip(names, files, strict=True):
        digest.update(name.encode('utf-8') + b'\0' + one.read_bytes() + b'\0')
    return digest.hexdigest() == said.get('sha256')


def built() -> bool:
    """Whether the map view is built and made of the files installed beside it, `current`; a file it names that is
    not installed is taken as it was. A view older than the page is not served, and stderr says once why, so the node
    view is never quietly replaced by a stale map."""
    view = _views() / BUILT
    if not view.is_file():
        return False
    said = recorded(view)
    if said is None:
        return _stale('it records no inputs')
    modules = resources.files('metaform.modules')
    seen = tuple((name, _stamp(modules.joinpath(*str(name).split('/')))) for name in said.get('files', []))
    seen += (('', _stamp(view)),)
    if _checked.get('seen') != seen:
        _checked.update(seen=seen, current=current(said, modules) is not False, told=False)
    return bool(_checked['current']) or _stale('the page has changed since it was built')


def _stamp(one: Traversable) -> tuple[int, int] | None:
    try:
        held = Path(str(one)).stat()
    except OSError:
        return None
    return held.st_mtime_ns, held.st_size


def _stale(why: str) -> bool:
    if not _checked.get('told'):
        _checked['told'] = True
        print(f'Metaform: the map view is not served, {why}; the node view stands in. Build it with '
              'node scripts/build_map_view.mjs.', file=sys.stderr, flush=True)
    return False


def html(uri: str, config: dict[str, Any]) -> str:
    """A view's document with its settings filled in: the map view when it is built, else the node view, which says
    so for the map; the node, trace and glossary views as written, with the page's tokens, the SDK and the bridge put
    in where they are marked."""
    folder = _views()
    filled = json.dumps(config, ensure_ascii=False).replace('</', '<\\/')
    if uri == MAP and built():
        return (folder / BUILT).read_text(encoding='utf-8').replace(CONFIG, CONFIG.replace('{}', filled), 1)
    page = (folder / FILES.get(uri, FILES[NODE])).read_text(encoding='utf-8')

    def script(name: str) -> str:
        code = re.sub(r'</(script)', r'<\\/\1', (folder / name).read_text(encoding='utf-8'), flags=re.IGNORECASE)
        return f'<script>{code}</script>'  # inline, so a closing tag in the code is escaped as the build does
    shared = (folder / 'view.css').read_text(encoding='utf-8').replace('</', '<\\/')
    return (page.replace(TOKENS, f'<style id="metaform-tokens">{tokens()}</style>', 1)
            .replace(SHARED, f'<style>{shared}</style>', 1)
            .replace(CONFIG, CONFIG.replace('{}', filled), 1)
            .replace(SDK, script('ext-apps.js'), 1)
            .replace(BRIDGE, script('bridge.js'), 1))


# ---------------------------------------------------------------------------------------------------- trace marks

# What a trace is read from, `trace_view`: the ticket, its steps and questions, and dispatch's sessions and threads.
TRACE_TABLES = frozenset({'work', 'work_steps', 'work_links', 'messages', 'map.question_work', 'dispatch'})


def traced(payload: dict[str, Any], project: str, work_id: str) -> bool:
    """Whether a `map.changed` can change what the trace view of a ticket shows, decided from the change alone: the
    project's, and it names the ticket; or it names no tickets or sessions and wrote what a trace is read from, or did
    not say what it wrote. With no ticket the view lists every session without its thread, so a change only to the
    agents' thread lines changes nothing there."""
    if payload.get('project') not in (None, '', project):
        return False
    tables: Any = payload.get('tables')
    if not work_id and tables in ('dispatch', ['dispatch']) and payload.get('dispatch_tables') == ['dispatch.lines'] \
            and not payload.get('signal'):
        return False
    named: Any = payload.get('work_ids')
    sessions: Any = payload.get('session_ids')
    if work_id and isinstance(named, list) and work_id in named:
        return True
    if work_id and (isinstance(named, list) or isinstance(sessions, list)):
        return False
    written = [tables] if isinstance(tables, str) else tables
    if not isinstance(written, list) or not written:
        return True
    return any(str(table) in TRACE_TABLES or str(table).startswith('dispatch.')
               for table in cast(list[Any], written))


class Traces:
    """The tickets open trace views follow, each with a count of the changes heard for it: a view's read gives the
    count it read at as its `mark`, and its next read reads the store only once the count has moved, so a change
    between two reads is never missed and an unchanged ticket is never read. Changes come from other processes through `events.listen`, BASE-053, and from this one
    through the mcp module's subscription, `heard`; each is matched to the tickets from what it says alone, on the
    thread that heard it."""

    def __init__(self) -> None:
        self.run = uuid.uuid4().hex[:8]  # this process's, so a mark another process gave is never taken for its own
        self.counts: dict[tuple[str, str], int] = {}
        self.keys: frozenset[tuple[str, str]] = frozenset()  # the tickets followed, for the hearing thread
        self.listener: Any = None
        self.token: Any = None
        self.thread: int | None = None
        HUBS.add(self)

    def track(self, project: str, work_id: str) -> str:
        """Follow the ticket's changes from now, in the server's loop; returns its mark, taken before it is read."""
        self.token, self.thread = anyio.lowlevel.current_token(), threading.get_ident()
        if (project, work_id) not in self.counts:
            self.counts[(project, work_id)] = 0
            self.keys = frozenset(self.counts)
        if self.listener is None:
            self.listener = events.listen('mcp', self.heard)
        return self.mark(project, work_id)

    def mark(self, project: str, work_id: str) -> str:
        return f'{self.run}:{self.counts.get((project, work_id), 0)}'

    def heard(self, payload: dict[str, Any]) -> None:
        """A change, on any thread: the tickets it concerns count it. One that concerns none costs the server's loop
        nothing."""
        loop = self.token
        if loop is None or not any(traced(payload, project, work_id) for project, work_id in self.keys):
            return
        if threading.get_ident() == self.thread:
            self._wake(payload)
            return
        try:
            anyio.from_thread.run_sync(self._wake, payload, token=loop)
        except Exception:  # noqa: BLE001, S110  a loop that has stopped has no read left to answer
            pass

    def _wake(self, payload: dict[str, Any]) -> None:
        for key in list(self.counts):
            if traced(payload, *key):
                self.counts[key] += 1

    def stop(self) -> None:
        if self.listener is not None:
            self.listener.close()
            self.listener = None
        self.token = None


HUBS: weakref.WeakSet[Traces] = weakref.WeakSet()


def heard(payload: dict[str, Any]) -> None:
    """A `map.changed` published in this process: the mcp module's subscription hands it to every server here."""
    for hub in list(HUBS):
        hub.heard(payload)
