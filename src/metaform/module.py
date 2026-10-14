"""The module contract, BASE-035: what a module declares and what a verb receives.

A module is a folder with an `__init__.py` that sets the literals
`SUPPORTED_OS`, and optionally `DEPENDENCIES`, `SHIPS_DISABLED` and
`REMOTE_AGENT`, whether an agent on a hosted sandbox working through the CLI
has use for it, BASE-060, and `MODULE = Module(...)`. Each verb runs as `metaform <module> <verb> <nouns>
[switches]` on the CLI and as the tool `<module>_<verb>` over MCP, both built
from this one declaration. A verb's switches are settings the module declares
with `metaform.settings`.
"""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import os
import re
import sys
from collections.abc import Awaitable, Callable, Coroutine, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

from .errors import Stop

if TYPE_CHECKING:
    from .data import Node, Store, WorkRecord
    from .data.operations import Data
    from .data.tables import Tables
    from .relay import Listener

__all__ = [
    'Context',
    'Count',
    'Effect',
    'Handler',
    'Hook',
    'ItemReadHook',
    'ItemsAtHook',
    'Module',
    'NodeCountHook',
    'NodeReadHook',
    'Noun',
    'NounKind',
    'Pane',
    'Resource',
    'Status',
    'StatusHook',
    'Stop',
    'Subscription',
    'Surface',
    'ToolbarItem',
    'Verb',
    'VerbFunction',
    'WorkReadHook',
    'aliases',
    'call',
    'chassis_version',
    'child_environment',
    'code_print',
    'command_summary',
    'context',
    'contributions',
    'feedback',
    'first_line',
    'held_role',
    'instructions',
    'item_read',
    'item_text',
    'latest_item',
    'list_reports',
    'mcp_reads',
    'mcp_server',
    'module_files',
    'module_instructions',
    'node_brief',
    'node_counts',
    'node_items',
    'node_reads',
    'on_surface',
    'on_this_system',
    'project_for',
    'project_glossary',
    'read_report',
    'refresh_modules',
    'request_scope',
    'result_json',
    'save_report',
    'serve_session',
    'setting_value',
    'surface',
    'titled',
    'tool_arguments',
    'work_reads',
]

VERB_NAME = re.compile(r'^[a-z][a-z0-9_-]*$')
COMMAND = re.compile(r'\bmetaform ([a-z0-9_-]+) ([a-z0-9_-]+)')  # a module command written as a command line
NounKind = Literal['str', 'int', 'bool', 'json']
Surface = Literal['cli', 'mcp', 'web', 'a2a']  # where a call or a change was made; verbs are offered on SURFACES only
NOUN_KINDS: tuple[NounKind, ...] = ('str', 'int', 'bool', 'json')
SURFACES: tuple[Surface, ...] = ('cli', 'mcp')
# What a verb does to what it acts on, BASE-006: `read` changes nothing; `write` adds or changes and keeps what was
# there, as a new version, a history or a backup; `remove` deletes or replaces what cannot be had back from the store.
Effect = Literal['read', 'write', 'remove']
EFFECTS: tuple[Effect, ...] = ('read', 'write', 'remove')

# The module contract's callables, BASE-035. Each may be a plain function or a coroutine function, BASE-009.
VerbFunction = Callable[['Context'], Any]  # returns the verb's result, BASE-036
Handler = Callable[[dict[str, Any], 'Context'], Any]  # a subscriber: the payload and its own context, BASE-010
Hook = Callable[['Context'], Any]  # start and stop, BASE-018
StatusHook = Callable[['Context'], 'Status | Awaitable[Status]']  # what status and the instructions add
NodeReadHook = Callable[['Context', 'Node'], Any]  # what a module adds to the read of a node, or None, BASE-035
# How much a module holds at each of some element addresses, told to an agent as counts, never contents, MCP-039
NodeCountHook = Callable[['Context', tuple[str, ...]], 'Count | tuple[Count, ...] | None | Awaitable[Any]']
WorkReadHook = Callable[['Context', 'WorkRecord'], Any]  # what a module keeps on a work record, or None, BASE-035
# The one item a module wrote at an address under a number, MCP-037: its kind, title, why, body and links, or None
ItemReadHook = Callable[['Context', str, int], Any]
# The items a module numbered at an address below a number, newest first, at most a limit, MCP-037: each one's number,
# kind, title and why, read in one query, so a list of them is never one read per number
ItemsAtHook = Callable[['Context', str, 'int | None', int], Any]


@dataclass(frozen=True)
class Noun:
    """What a verb acts on. Required nouns are positional; optional ones are written name=value."""
    name: str
    help: str
    kind: NounKind = 'str'
    required: bool = True
    many: bool = False
    schema: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.kind not in NOUN_KINDS:
            raise ValueError(f'Noun {self.name}: kind must be one of {", ".join(NOUN_KINDS)}.')
        if self.kind == 'json' and self.schema is None:  # an untyped argument over MCP leaves an agent guessing
            raise ValueError(f'Noun {self.name}: a json noun declares its schema.')

    def usage(self) -> str:
        if self.many:
            return f'<{self.name}>...' if self.required else f'[{self.name}...]'
        return f'<{self.name}>' if self.required else f'[{self.name}=<{self.kind}>]'


@dataclass(frozen=True)
class Verb:
    """One command of a module. `switches` names the settings the verb reads, CLI-012.

    A `transport` verb, such as `mcp serve`, is how a host reaches Metaform rather than a command an agent runs,
    so it runs whatever the folder's command surface; the surface narrows what it serves, CLI-022 and MCP-004.

    `effect` says what the verb does to what it acts on, `write` unless declared, and `open_world` whether it reaches
    past the Metaform home and the project's map, to agents it starts or steers, or to services on the network. A host
    reads both as the tool's annotations, MCP-003, so it can tell a read from a write and a write from a removal.

    `task` marks a verb that can take long, such as one that waits on an agent or the network; the MCP server answers
    it with a task to a client that declares the tasks extension, BASE-030. `task='run'` marks a verb that returns
    `{'run': <run id>}`, a workflow run record, BASE-051, whose work the server itself advances to its end, such as an
    agent Metaform starts and steers: that run is the task, followed until it ends. A task only for work the server
    advances by itself: a host gives the model a task's result only once it ends, so a verb whose result the calling
    agent must act on, such as workflow's `assign`, declares neither. A cancel stops an `async` verb at its next
    `await`; a verb run in a thread cannot be stopped, so it finishes and its task completes with its result.
    """
    name: str
    run: VerbFunction
    summary: str
    nouns: tuple[Noun, ...] = ()
    switches: tuple[str, ...] = ()
    details: str = ''
    examples: tuple[tuple[str, str], ...] = ()
    caution: str = ''
    supported_os: tuple[str, ...] | None = None
    surfaces: tuple[Surface, ...] = SURFACES
    transport: bool = False
    effect: Effect = 'write'
    open_world: bool = False
    # The verb can take long: over MCP, a client that declares the tasks extension gets a task it polls instead of
    # waiting on the call; every other surface and client waits as for any verb, BASE-030. 'run': the task is the
    # workflow run the verb returns, which the server advances by itself.
    task: bool | Literal['run'] = False

    def __post_init__(self) -> None:
        if self.effect not in EFFECTS:
            raise ValueError(f'Verb {self.name}: effect must be one of {", ".join(EFFECTS)}.')
        if not VERB_NAME.fullmatch(self.name):
            raise ValueError(f'Verb name {self.name!r} must be lowercase letters, digits, hyphens and underscores.')
        if any(noun.many for noun in self.nouns[:-1]):
            raise ValueError(f'Verb {self.name}: only the last noun may take many words.')
        if not set(self.surfaces) <= set(SURFACES):
            raise ValueError(f'Verb {self.name}: surfaces are cli and mcp.')
        if self.task not in (False, True, 'run'):
            raise ValueError(f"Verb {self.name}: task is True, False or 'run'.")

    def usage(self, module: str) -> str:
        from . import settings
        parts = ['metaform', module, self.name, *(noun.usage() for noun in self.nouns)]
        for key in self.switches:
            setting = settings.SCHEMA.get(key)
            if setting is not None:
                parts.append(f'[{setting.switch}]' if setting.kind == 'bool' else f'[{setting.switch} <value>]')
        if self.caution:
            parts.append('[--confirm]')
        return ' '.join(parts)


@dataclass(frozen=True)
class Subscription:
    topic: str
    handler: Handler


@dataclass(frozen=True)
class Resource:
    """A read-only text a module serves over MCP as a resource, MCP-037: an agent reads it by its URI at
    discovery, before any tool runs. `verb` names the module verb whose result, called with no arguments, is the
    text; a module serves nothing it cannot also give on the command line. A URI holding `{field}` parts, such as
    `metaform://roundtable/discussion{discussion}/review`, is a template: listed among the resource templates, each
    field matching one path segment or part of one, and read by calling `verb` with the fields as its nouns, so
    every field names a noun of the verb."""
    uri: str
    name: str
    description: str
    verb: str
    mime_type: str = 'text/plain'

    @property
    def fields(self) -> tuple[str, ...]:
        """The template's fields, in order; none for a fixed URI."""
        return tuple(TEMPLATE_FIELD.findall(self.uri))

    def matched(self, uri: str) -> dict[str, str] | None:
        """The fields `uri` gives this template, or None when it is not one of its URIs or this is a fixed URI."""
        if not self.fields:
            return None
        pattern = TEMPLATE_FIELD.sub(lambda field: f'(?P<{field.group(1)}>[^/?#]+?)', re.escape(self.uri)
                                     .replace(r'\{', '{').replace(r'\}', '}'))
        found = re.fullmatch(pattern, uri)
        return None if found is None else found.groupdict()


TEMPLATE_FIELD = re.compile(r'\{([a-z][a-z0-9_]*)\}')  # a field of a resource template, named for a noun


# Panes and the toolbar: what a module adds to the web GUI's workspace, declared once like its verbs. The page draws a
# built-in icon by its name; a module may instead give an SVG of its own under its resources folder.
ICONS: tuple[str, ...] = (
    'archive', 'back', 'board', 'box', 'boxes', 'brief', 'chat', 'check', 'code', 'copy', 'cube', 'dock', 'download',
    'expand', 'eye', 'file', 'forward', 'gauge', 'gear', 'globe', 'keyboard', 'layers', 'lock', 'map', 'memory', 'menu',
    'move', 'pen', 'play', 'reset', 'search', 'send', 'spark', 'star', 'terminal', 'tool', 'trash')
PaneArea = Literal['left', 'main', 'right', 'bottom', 'float']
PANE_AREAS: tuple[PaneArea, ...] = ('left', 'main', 'right', 'bottom', 'float')
Placement = Literal['toolbar', 'extra']  # on the toolbar, or among the extra tools behind its last slot
PLACEMENTS: tuple[Placement, ...] = ('toolbar', 'extra')
CONTRIBUTION_ID = re.compile(r'^[a-z][a-z0-9-]*$')
QUALIFIED_ID = re.compile(r'^[A-Za-z0-9_][A-Za-z0-9_-]*\.[a-z][a-z0-9-]*$')  # `<module>.<id>`, or `chassis.<id>`
RESOURCE_PATH = re.compile(r'^resources/(?:[A-Za-z0-9_][A-Za-z0-9_.-]*/)*[A-Za-z0-9_][A-Za-z0-9_.-]*$')
PANE_FILES = ('.md', '.txt', '.html')  # what a pane shows from a file: text, Markdown, or HTML in a sandboxed frame
SHORTCUT = re.compile(r'^(?:(?:Ctrl|Alt|Shift|Meta)\+)*(?:[A-Z0-9]|F(?:[1-9]|1[0-2])|[/?.,;=\[\]-])$')
DESCRIPTION_LIMIT = 160  # a tooltip is read at a glance: one line


def _resource(path: str, what: str) -> None:
    if not RESOURCE_PATH.fullmatch(path) or '..' in path.split('/'):
        raise ValueError(f'{what}: {path!r} is not a file under the module\'s resources folder.')


def _contribution(kind: str, ident: str, title: str, description: str, icon: str) -> None:
    """What every toolbar item and pane declares: an id, a title, one line saying why a person uses it, an icon."""
    if not CONTRIBUTION_ID.fullmatch(ident):
        raise ValueError(f'{kind} id {ident!r} must be lowercase letters, digits and hyphens.')
    what = f'{kind} {ident}'
    if not title.strip():
        raise ValueError(f'{what}: a title is the name a person reads on it.')
    said = description.strip()
    if not said or '\n' in said or len(said) > DESCRIPTION_LIMIT:
        raise ValueError(f'{what}: the description is one line of at most {DESCRIPTION_LIMIT} characters saying why '
                         'a person uses it; it is the tooltip.')
    if said.rstrip('.').casefold() == title.strip().casefold():
        raise ValueError(f'{what}: the description says why a person uses it, not its title again.')
    if icon.startswith('resources/'):
        if not icon.endswith('.svg'):
            raise ValueError(f'{what}: an icon file is an SVG.')
        _resource(icon, what)
    elif icon not in ICONS:
        raise ValueError(f'{what}: icon {icon!r} is neither a built-in icon ({", ".join(ICONS)}) nor an SVG under '
                         'resources/.')


def _one_action(what: str, actions: dict[str, Any]) -> str:
    given = [name for name, value in actions.items() if value is not None]
    if len(given) != 1:
        raise ValueError(f'{what}: declare exactly one of {", ".join(actions)}.')
    return given[0]


@dataclass(frozen=True)
class ToolbarItem:
    """One tool a module puts on the web GUI's toolbar, as a Verb is one command: `id` unique in the module, shown as
    `<module>.<id>`; `title`; `description`, one line saying why a person uses it, the tooltip; `icon`, a built-in
    name from ICONS or an SVG under `resources/`.

    Its action is exactly one of: `verb`, a verb of this module run with the fixed `arguments`, which stays inside the
    home and the map, never `open_world`; `pane`, a pane to show, this module's by id or another's as `<module>.<id>`;
    `page`, a command the page itself carries, such as `search` or `export-markdown`; or `link`, an `http(s)://` or
    `metaform://` address, or a file under `resources/`. `selection` names the noun, or the page command's argument,
    that receives the selected node's address; the tool is then off while nothing is selected.

    `group` puts tools in one slot, the first shown and the rest behind it; `placement` is where it starts, on the
    `toolbar` or among the `extra` tools; `order` sorts within its place, lowest first; `shortcut` is a key such as
    `Alt+B`. The person rearranges all of it; these are only the defaults."""
    id: str
    title: str
    description: str
    icon: str = 'tool'
    verb: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict[str, Any])
    pane: str | None = None
    page: str | None = None
    link: str | None = None
    selection: str | None = None
    group: str = ''
    placement: Placement = 'toolbar'
    order: int = 100
    shortcut: str = ''

    def __post_init__(self) -> None:
        _contribution('Toolbar item', self.id, self.title, self.description, self.icon)
        what = f'Toolbar item {self.id}'
        action = _one_action(what, {'verb': self.verb, 'pane': self.pane, 'page': self.page, 'link': self.link})
        if self.arguments and action != 'verb':
            raise ValueError(f'{what}: arguments go to a verb.')
        if self.pane is not None and not (CONTRIBUTION_ID.fullmatch(self.pane) or QUALIFIED_ID.fullmatch(self.pane)):
            raise ValueError(f'{what}: pane names a pane by its id, or another module\'s as <module>.<id>.')
        if self.page is not None and not CONTRIBUTION_ID.fullmatch(self.page):
            raise ValueError(f'{what}: page names a command of the page in lowercase letters, digits and hyphens.')
        if self.link is not None:
            if self.selection is not None:
                raise ValueError(f'{what}: a link takes no selection.')
            if not self.link.startswith(('http://', 'https://', 'metaform://')):
                _resource(self.link, what)
        if self.group and not CONTRIBUTION_ID.fullmatch(self.group):
            raise ValueError(f'{what}: group is lowercase letters, digits and hyphens.')
        if self.placement not in PLACEMENTS:
            raise ValueError(f'{what}: placement is toolbar or extra.')
        if self.shortcut and not SHORTCUT.fullmatch(self.shortcut):
            raise ValueError(f'{what}: shortcut is a key with Ctrl+, Alt+, Shift+ or Meta+ before it, such as Alt+B.')

    @property
    def action(self) -> str:
        """What the tool does: verb, pane, page or link."""
        return next(name for name in ('verb', 'pane', 'page', 'link') if getattr(self, name) is not None)


@dataclass(frozen=True)
class Pane:
    """One pane a module adds to the web GUI, which the person turns on and off, docks in an area, groups as tabs and
    floats: `id` unique in the module, shown as `<module>.<id>`; `title`, the tab's name; `description`, one line saying
    why a person opens it, the tooltip; `icon` as a ToolbarItem's.

    Its content is exactly one of: `page`, a view the page draws itself, such as `map2d` or `dock`; `verb`, a `read`
    verb of this module run with the fixed `arguments` whenever the pane shows, the selection changes or the map
    changes, its result shown as every surface shows it; or `resource`, a `.md`, `.txt` or `.html` file under
    `resources/`, an HTML file shown in a sandboxed frame. `selection` names the noun that receives the selected node's
    address; the pane then follows the selection.

    Where it starts: `area`, left, main, right, bottom or float; `group`, the tab group it joins in that area, its own
    when empty; `visible`, whether it is on; `order`, its place among the tabs or groups of its area, lowest first;
    `min_width` and `min_height` in CSS pixels. These are the defaults the person's layout and workspaces start from."""
    id: str
    title: str
    description: str
    icon: str = 'box'
    page: str | None = None
    verb: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict[str, Any])
    resource: str | None = None
    selection: str | None = None
    area: PaneArea = 'right'
    group: str = ''
    visible: bool = False
    order: int = 100
    min_width: int = 240
    min_height: int = 160

    def __post_init__(self) -> None:
        _contribution('Pane', self.id, self.title, self.description, self.icon)
        what = f'Pane {self.id}'
        content = _one_action(what, {'page': self.page, 'verb': self.verb, 'resource': self.resource})
        if self.arguments and content != 'verb':
            raise ValueError(f'{what}: arguments go to a verb.')
        if self.page is not None and not CONTRIBUTION_ID.fullmatch(self.page):
            raise ValueError(f'{what}: page names a view of the page in lowercase letters, digits and hyphens.')
        if self.resource is not None:
            _resource(self.resource, what)
            if not self.resource.endswith(PANE_FILES):
                raise ValueError(f'{what}: a pane shows a {", ".join(PANE_FILES)} file.')
            if self.selection is not None:
                raise ValueError(f'{what}: a file does not follow the selection.')
        if self.area not in PANE_AREAS:
            raise ValueError(f'{what}: area is one of {", ".join(PANE_AREAS)}.')
        if self.group and not CONTRIBUTION_ID.fullmatch(self.group):
            raise ValueError(f'{what}: group is lowercase letters, digits and hyphens.')
        if self.min_width < 0 or self.min_height < 0:
            raise ValueError(f'{what}: a minimum size is not negative.')

    @property
    def content(self) -> str:
        """Where the pane's content comes from: page, verb or resource."""
        return next(name for name in ('page', 'verb', 'resource') if getattr(self, name) is not None)


def check_workspace(module: str, verbs: tuple[Verb, ...], toolbar: tuple[ToolbarItem, ...],
                     panes: tuple[Pane, ...]) -> None:
    """A module's toolbar items and panes fit its verbs and each other: ids unique, every verb declared with the nouns
    the arguments and the selection name, a pane's verb only reads, a tool's verb stays inside the home and the map,
    and a tool's own pane declared."""
    for kind, declared in (('toolbar item', [item.id for item in toolbar]), ('pane', [pane.id for pane in panes])):
        twice = sorted({ident for ident in declared if declared.count(ident) > 1})
        if twice:
            raise ValueError(f'Module {module}: two of its {kind}s share the id {twice[0]}.')
    by_name = {verb.name: verb for verb in verbs}
    own = {pane.id for pane in panes}
    for what, name, arguments, selection in (
            *((f'toolbar item {item.id}', item.verb, item.arguments, item.selection) for item in toolbar),
            *((f'pane {pane.id}', pane.verb, pane.arguments, pane.selection) for pane in panes)):
        if name is None:
            continue
        verb = by_name.get(name)
        if verb is None:
            raise ValueError(f'Module {module}: {what} runs verb {name}, not declared.')
        nouns = {noun.name for noun in verb.nouns}
        unknown = sorted(set(arguments) - nouns) + ([selection] if selection is not None and selection not in nouns
                                                   else [])
        if unknown:
            raise ValueError(f'Module {module}: {what} gives {unknown[0]}, which verb {name} does not take.')
        if what.startswith('pane') and verb.effect != 'read':
            raise ValueError(f'Module {module}: {what} shows verb {name}, which changes something; a pane only reads.')
        if what.startswith('toolbar') and verb.open_world:
            raise ValueError(f'Module {module}: {what} runs verb {name}, which reaches agents or the network; a tool '
                             'that starts or steers agents opens the page\'s own dialog for it with page=.')
    for item in toolbar:
        if item.pane is not None and '.' not in item.pane and item.pane not in own:
            raise ValueError(f'Module {module}: toolbar item {item.id} shows pane {item.pane}, not declared.')


@dataclass(frozen=True)
class Status:
    """What a module's status hook adds: lines and a notice to status, BASE-035, and an instruction to the
    instructions agents read, after the module's own instructions prompt, MCP-031. With `at_connect` off the
    instruction is in the module's full instructions only, read on demand, and not in what every agent is handed at
    connect: a short notice of the folder's state belongs at connect, a procedure does not, MCP-037."""
    lines: tuple[str, ...] = ()
    notice: str | None = None
    instruction: str | None = None
    at_connect: bool = True


@dataclass(frozen=True)
class Count:
    """How much a module holds at element addresses, for the counts an agent is told at its node, MCP-039: the word for
    one and for several, and at each address how many there are, how many of them the last session there wrote, `new`,
    and how many this call's own session wrote, `mine`, which is never news to it. `legend` is the line under the
    counts saying what new means and the command line that reads them, with `<address>` where the address goes; the
    contents are read with that call, never sent with the counts."""
    one: str
    many: str
    at: dict[str, tuple[int, int, int]] = field(default_factory=dict[str, tuple[int, int, int]])
    legend: str = ''

    def said(self, count: int) -> str:
        return f'{count} {self.one if count == 1 else self.many}'


@dataclass(frozen=True)
class Provides:
    """Something a module offers other modules, found by its kind, so a module that uses it never imports the one that
    offers it. `kind` names the contract, such as `voice.engine`, a `VoiceEngine` another module brings to the voice
    module, or `voice`, the voice module's own speak and transcribe for a server-side caller such as a phone bridge;
    `value` is what the contract says it is. `provided(folder, kind)` finds every enabled module's."""
    kind: str
    value: Any


@dataclass(frozen=True)
class VoiceEngine:
    """A speech engine a module brings to the voice module, which offers it as a choice beside its own engines.

    `name` is the choice, in voice_engine for one that `transcribe`s and voice_tts for one that `speak`s; `sends` says
    plainly where the person's audio or text goes, shown beside the choice, empty when nothing leaves the machine.
    `transcribe(ctx, path, language)` returns `{'text': ..., 'segments': [...]}` for an audio file; `speak(ctx, text,
    character, format)` returns an iterator of audio chunks, `format` being 'page', 'phone' or one of `formats`; a speak
    that also takes the keyword `voice`, a voice id of the engine's own, is given it when a caller names one, in place of
    the character's voice, and one that does not take it speaks with the character's; `output(ctx, format)` is the
    format those chunks are in, such as pcm_22050 or mp3_44100_128; `ready(ctx)` is None when the engine can be used
    now, else why not, with the next step. Each raises `Stop` with the next step when it refuses.
    The module that provides it owns its settings and its keys; enabling or disabling that module offers or withdraws
    the engine."""
    name: str
    summary: str
    sends: str = ''
    transcribe: Callable[..., dict[str, Any]] | None = None
    speak: Callable[..., Any] | None = None
    ready: Callable[..., str | None] | None = None
    formats: tuple[str, ...] = ()
    output: Callable[..., str] | None = None


@dataclass(frozen=True)
class Module:
    id: str
    summary: str
    purpose: str
    verbs: tuple[Verb, ...] = ()
    subscriptions: tuple[Subscription, ...] = ()
    details: str = ''
    start: Hook | None = None
    stop: Hook | None = None
    status: StatusHook | None = None
    default: str | None = None  # the verb `metaform <id>` runs when no verb follows, BASE-035
    tables: Tables | None = None  # the module's own tables, reached through ctx.store.tables(), STORE-045
    data: Data | None = None  # module-owned DAO operations, record contributions and cleanup
    node_read: NodeReadHook | None = None  # what the module adds to `map where` and `map node` of a node, BASE-035
    node_count: NodeCountHook | None = None  # how much it holds at addresses, as counts an agent is told, MCP-039
    work_read: WorkReadHook | None = None  # what the module keeps on a work record, shown in `map work id=`, BASE-035
    item_read: ItemReadHook | None = None  # the item it numbered at an address, read as `<address>#<n>`, MCP-037
    items_at: ItemsAtHook | None = None  # the items it numbered at an address, newest first, a page at a time, MCP-037
    item_kinds: tuple[str, ...] = ()  # the kinds of item it numbers, so a list of other kinds skips it; () for any
    mcp_server: str | None = None  # this module's verb serving MCP over stdio, used by install and provision
    resources: tuple[Resource, ...] = ()  # read-only texts served over MCP as resources, MCP-037
    toolbar: tuple[ToolbarItem, ...] = ()  # the tools it adds to the web GUI's toolbar
    panes: tuple[Pane, ...] = ()  # the panes it adds to the web GUI's workspace
    provides: tuple[Provides, ...] = ()  # what it offers other modules by kind, found with provided(folder, kind)

    def __post_init__(self) -> None:
        names = {verb.name for verb in self.verbs}
        for resource in self.resources:
            if resource.verb not in names:
                raise ValueError(f'Module {self.id}: resource {resource.uri} reads verb {resource.verb}, not declared.')
            verb = next(one for one in self.verbs if one.name == resource.verb)
            unknown = [field for field in resource.fields if field not in {noun.name for noun in verb.nouns}]
            if unknown:
                raise ValueError(f'Module {self.id}: resource {resource.uri} fills {", ".join(unknown)}, not a noun '
                                 f'of verb {resource.verb}.')
        check_workspace(self.id, self.verbs, self.toolbar, self.panes)


@dataclass
class Context:
    """What one verb call, event delivery or tool call receives. Nothing else carries context, BASE-028."""
    module: str
    folder: Path
    project: str | None = None
    store: Store | None = None
    nouns: dict[str, Any] = field(default_factory=dict[str, Any])
    switches: dict[str, Any] = field(default_factory=dict[str, Any])
    sink: Callable[[str], None] | None = None
    surface: Surface = 'cli'
    client: str | None = None  # the MCP client name, supplied by the transport rather than tool arguments
    session: str | None = None  # the agent session the call is made in, MCP-039; None for a person's command line

    def seen(self, key: str, value: Any) -> Any:
        """What this call's session was last shown under `key`, or None the first time, recording `value` as shown
        now, so an agent is told a thing once and then only what changed, MCP-039. With no session, always None."""
        from . import shown
        return shown.swap(self.session, key, value)

    def calls(self, text: str) -> str:
        """Text naming module commands as command lines, `metaform <module> <verb>`, with each named as this surface
        calls it: over MCP its tool, `<module>_<verb>`, MCP-038; elsewhere as written."""
        if self.surface != 'mcp':
            return text
        verbs = {module.id: {verb.name for verb in module.verbs} for module in surface(self.folder)}

        def named(match: re.Match[str]) -> str:
            module, verb = match.group(1), match.group(2)
            return f'{module}_{verb}' if verb in verbs.get(module, ()) else match.group(0)
        return COMMAND.sub(named, text)

    def say(self, text: str) -> None:
        """A message for a person. The data an agent needs back is the verb's return value, BASE-036."""
        if self.sink is not None:
            self.sink(text)
        else:
            sys.stdout.write(text + '\n')

    def setting(self, key: str) -> Any:
        """The value passed on this call, otherwise the stored or default value for this folder, CLI-011."""
        if key in self.switches:
            return self.switches[key]
        from . import settings
        return settings.value(key, self.folder)

    def require_store(self) -> Store:
        """This call's store; with no project, the one next step is to register or to select one, PROJ-005."""
        if self.store is None:
            from . import home
            registered = home.projects()
            raise Stop('No project for this folder.', 'metaform add project <id> <path>' + (
                ' for this folder, or metaform set --project <id> for a registered one' if registered else ''))
        return self.store

    def publish(self, topic: str, payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        from . import events
        return events.publish(topic, payload or {}, self)

    async def publish_async(self, topic: str, payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Publish from an async verb; subscribers run without blocking this loop, BASE-009."""
        from . import events
        return await events.publish_async(topic, payload or {}, self)

    def listen(self, handler: Callable[[dict[str, Any]], Any]) -> Listener:
        """Hear each `map.changed` published in another process of this home, in this module's long-running process;
        the handler runs in the listener's own thread. Close the listener when the process is done, BASE-053."""
        from . import events
        return events.listen(self.module, handler)

    def spawn(self, coroutine: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        """Start a task owned by this module; unload, reload and shutdown cancel it, BASE-018."""
        from . import loader
        return loader.spawn(self.module, coroutine)


def on_this_system(verb: Verb) -> bool:
    """Whether a verb runs on this system: its own systems when it narrows them, BASE-016."""
    from .module_metadata import current_os
    return verb.supported_os is None or current_os() in verb.supported_os


def call(function: Callable[..., Any], *args: Any) -> Any:
    """Run a function or a coroutine function the same way from synchronous code, BASE-009.

    Inside a running loop a coroutine is refused: waiting for it there would block that loop. Await it, or run
    the synchronous caller in a worker thread.
    """
    result = function(*args)
    if inspect.isawaitable(result):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(_await(result))
        if inspect.iscoroutine(result):
            result.close()
        raise RuntimeError(f'{getattr(function, "__qualname__", function)} is async and was called from inside a '
                           'running event loop; await it there instead, BASE-009.')
    return result


async def _await(awaitable: Any) -> Any:
    return await awaitable


# The chassis resources every module may use, BASE-004: the module registry, the command surface, the
# composed instructions and the per-call Context. The mcp module serves tools through these alone, MCP-001.

def surface(folder: Path) -> list[Module]:
    """The loaded modules on this folder's command surface, in module id order, CLI-022, less what is withheld from
    the session this process serves, `withheld`."""
    from . import instructions as composed
    return withheld(composed.surfaced(folder), os.environ.get(WITHHELD, ''))


# What a session's runner withholds from the agent it starts, named in its MCP server's environment: a session that
# must not lean on earlier conclusions, an intake, is served without the tools that read them, dispatch's
# dispatch_intake_withheld. Like the session's identity, it describes one session, so no process it starts carries it.
WITHHELD = 'METAFORM_WITHHELD'


def withheld(modules: list[Module], named: str) -> list[Module]:
    """The modules less what `named` withholds, a comma list of entries: `<module>`, the whole module; `<module>:read`,
    its verbs that only read; `<module>_<verb>`, one tool. Nothing withheld leaves the list as it is."""
    entries = {entry.strip() for entry in named.split(',') if entry.strip()}
    if not entries:
        return modules
    import copy
    kept: list[Module] = []
    for module in modules:
        if module.id in entries:
            continue
        verbs = tuple(verb for verb in module.verbs
                      if f'{module.id}_{verb.name}' not in entries
                      and not (f'{module.id}:read' in entries and verb.effect == 'read'))
        if len(verbs) == len(module.verbs):
            kept.append(module)
            continue
        # the same module with fewer tools: copied rather than declared again, so its panes, which may run a verb
        # withheld here, still stand as the module declared them
        served = copy.copy(module)
        object.__setattr__(served, 'verbs', verbs)
        kept.append(served)
    return kept


def instructions(folder: Path, project: str | None = None, *, surface: str = 'cli') -> str:
    """The composed instructions for agents working from this folder, MCP-007; `surface` is where they are served,
    `mcp` only for the MCP server, so their opening line is true where they are read."""
    from . import instructions as composed
    return composed.compose(folder, project, surface=surface)


def startup_instructions(folder: Path, project: str | None = None) -> str:
    """What the MCP server sends when an agent connects: the order to read metaform://metaform and the project's own
    glossary, then the notices the folder's state calls for, such as running the intake, MCP-007."""
    from . import instructions as composed
    return composed.startup(folder, project)


def module_instructions(folder: Path, identifier: str, project: str | None = None) -> str | None:
    """One surfaced module's full instructions, or None when it is not on this folder's surface, MCP-029."""
    from . import instructions as composed
    return composed.module_text(folder, identifier, project)


def on_surface(group: str, folder: Path) -> bool:
    """Whether a command group, a module id or `chassis`, is on this folder's command surface, CLI-022."""
    from . import instructions as composed
    return composed.on_surface(group, folder)


def aliases(folder: Path) -> dict[str, list[Module]]:
    """Each alias on this folder's command surface with the loaded modules it stands for, CLI-039."""
    from . import aliases as named
    return named.shown(folder)


def command_summary(name: str) -> str | None:
    """The summary of the chassis command `name`, or None when the chassis has no such command."""
    from . import docs
    record = docs.COMMANDS.get(name)
    return None if record is None else record.summary


def builder() -> Any:
    """The chassis build, BASE-060: the builds, shapes and modules the web GUI's build panel offers, and the build
    it runs; a build chooses what it carries and never turns a module on or off."""
    from . import build
    return build

def serve_session() -> None:
    """Make this process one agent session of its own, for a server a host starts for one conversation, such as the
    MCP server over stdio: what its calls tell the agent is told once, MCP-039. METAFORM_SESSION, when set, names it."""
    from . import shown
    shown.serving()


def chassis_version() -> str:
    """The version of the running chassis, BASE-020."""
    from . import __version__
    return __version__


def child_environment(**own: str) -> dict[str, str]:
    """The environment for a process a module starts: this one's without any session identity, then `own`, BASE-052."""
    from . import harness
    return harness.child_environment(**own)


def held_role(ctx: Context) -> str | None:
    """The role of the agent this call runs for, when the person's `roles_without_authority` holds it back from
    writing tickets and steering agents; None when the call may, MAP-050 and BASE-052. The page is the person's and is
    never held. The role is read from this process's environment, which the runner sets on its agent and that agent's
    MCP server and every spawner clears: a guard against an agent's mistakes, not a boundary, since an agent can change
    its own environment."""
    if ctx.surface not in ('mcp', 'cli'):
        return None
    role = os.environ.get('METAFORM_ROLE')
    return role if role and role != 'none' and role in (ctx.setting('roles_without_authority') or ()) else None


def mcp_server(folder: Path) -> list[str] | None:
    """The command of the MCP server the folder's `install_server` setting selects among the enabled providers, as AI
    tools are registered with it, MCP-010; None when no module provides one. It stops when several do and none is
    chosen, naming the setting."""
    from . import install
    return install.server(folder)


def mcp_connect(folder: Path, **identity: str) -> Any:
    """A connection to the folder's own MCP server, MCP-010, for a surface that is an MCP host for the person, as the
    web GUI's chat is for an MCP App view: the server AI tools are registered with, run by this Python in the folder
    with `identity`, the METAFORM_* names of the agent session its calls are made for, or with none. The caller keeps
    it and closes it with `close()`; `request(method, params, deadline=)` sends one request with the per-request
    `_meta`, whose client capabilities the caller may give. Stops when no enabled module serves MCP or the server does
    not start."""
    from . import probe
    command = mcp_server(folder)
    if command is None:
        raise Stop('No enabled module serves MCP here, so an agent has nothing to connect to.', 'metaform enable mcp')
    started = [sys.executable, '-m', 'metaform', *command[1:]] if command[0] == 'metaform' else command
    try:
        return probe.Session(started, cwd=folder, env=child_environment(**identity))
    except OSError as error:
        raise Stop(f'The MCP server did not start here: {error}.', 'metaform mcp serve') from None


def mcp_reads(folder: Path, uris: tuple[str, ...] = (), *, limit: float = 30.0) -> dict[str, Any]:
    """What an agent connecting to the folder's own MCP server receives, read over MCP as that agent reads it, for a
    surface that shows it to the person, as the MCP Inspector shows a server: `discover`, the server/discover result,
    its capabilities and the instructions sent at connect; `tools`, `resources`, `templates` and `prompts`, every entry
    tools/list, resources/list, resources/templates/list and prompts/list give, each followed through its pages and
    asked only when discover names its capability; and `texts`, each URI's text by resources/read. The server is the
    one AI tools are registered with, MCP-010, run by this Python in the folder with no session identity, so nothing it
    reads is counted as shown to an agent; it stops once read. Stops when no enabled module serves MCP, or the server
    does not answer."""
    import time

    from . import probe
    command = mcp_server(folder)
    if command is None:
        raise Stop('No enabled module serves MCP here, so an agent has nothing to connect to.', 'metaform enable mcp')
    started = [sys.executable, '-m', 'metaform', *command[1:]] if command[0] == 'metaform' else command
    try:
        session = probe.Session(started, cwd=folder, env=child_environment())
    except OSError as error:
        raise Stop(f'The MCP server did not start here: {error}.', 'metaform mcp serve') from None
    try:
        found = probe.discover(session, limit)
        deadline = time.monotonic() + limit
        offered = cast(dict[str, Any], found.get('capabilities') or {})

        def every(method: str, key: str, capability: str) -> list[Any]:
            if capability not in offered:
                return []
            listed: list[Any] = []
            cursor: str | None = None
            while True:  # a server may list in pages, each naming the next
                got = session.request(method, {'cursor': cursor} if cursor else {}, deadline=deadline)
                listed += cast(list[Any], got.get(key) or [])
                cursor = cast(str | None, got.get('nextCursor'))
                if not cursor:
                    return listed

        tools = every('tools/list', 'tools', 'tools')
        resources = every('resources/list', 'resources', 'resources')
        templates = every('resources/templates/list', 'resourceTemplates', 'resources')
        prompts = every('prompts/list', 'prompts', 'prompts')
        texts: dict[str, str] = {}
        for uri in uris:
            got = session.request('resources/read', {'uri': uri}, deadline=deadline)
            contents = cast(list[dict[str, Any]], got.get('contents') or [])
            texts[uri] = ''.join(str(one.get('text') or '') for one in contents)
    except (OSError, ValueError, RuntimeError, TimeoutError, EOFError) as error:
        session.close()  # its last words are kept once it has stopped
        said = ' '.join(line.strip() for line in session.errors[-2:] if not line.startswith('Notice:'))
        raise Stop(f'The MCP server did not answer: {error}' + (f'. It said: {said}' if said else '.'),
                   'metaform mcp serve') from None
    finally:
        session.close()
    return {'discover': found, 'tools': tools, 'resources': resources, 'templates': templates, 'prompts': prompts,
            'texts': texts}


def project_for(folder: Path, named: str | None = None) -> str | None:
    """The project a call is about: `named` when given, which must be registered, otherwise the folder's project, or
    None when it has none."""
    from . import context as contexts
    return contexts.project_for(folder, named)


def refresh_modules() -> None:
    """Follow module enablement and the selected project in a long-running process, BASE-037."""
    from . import loader
    loader.follow_enabled()


def code_print() -> str:
    """Identify the package's code on disk, so long-running surfaces can detect a replacement, STORE-029.

    This reads file metadata only, creates no state, and works for installed and editable packages alike.
    """
    found = hashlib.sha256()
    for path in sorted(Path(__file__).parent.rglob('*.py')):
        try:
            state = path.stat()
        except OSError:  # removed since it was listed
            continue
        found.update(f'{path}\0{state.st_mtime_ns}\0{state.st_size}\n'.encode())
    return found.hexdigest()


@contextmanager
def request_scope(*, fresh: bool = False) -> Generator[None, None, None]:
    """Share the chassis registry across the reads and writes of one request, BASE-037."""
    from . import loader
    with loader.request_scope(fresh=fresh):
        yield


def context(module: str, folder: Path, *, project: str | None = None, nouns: dict[str, Any] | None = None,
            switches: dict[str, Any] | None = None, sink: Callable[[str], None] | None = None,
            surface: Surface = 'cli', client: str | None = None, session: str | None = None) -> Context:
    """A Context for one call, with the project and store resolved for its folder, BASE-028; `session` names the agent
    session the call is made for when it is not this process's own, MCP-039."""
    from . import context as contexts
    return contexts.build(module, folder, project=project, nouns=nouns, switches=switches, sink=sink, surface=surface,
                          client=client, session=session)


def provided(folder: Path, kind: str) -> list[tuple[str, Any]]:
    """What the modules on this folder's surface provide of `kind`, as `(module id, value)` in module id order; a
    disabled module provides nothing, so turning it off withdraws what it offered."""
    return [(module.id, one.value) for module in surface(folder) for one in module.provides if one.kind == kind]


def node_counts(folder: Path, addresses: tuple[str, ...], *, project: str | None = None,
                layers: list[str] | None = None, session: str | None = None) -> dict[str, Count]:
    """How much each module on the folder's command surface holds at the addresses, in module id order, MCP-039: a
    module's one `Count` under its id, and when it counts several kinds, each after the first under `<id>.<many>`. Each
    hook gets a context of its own module with the call's project, toggled layers and session. A hook that raises, or
    returns None, adds nothing: counts are a pointer, and a read names what failed."""
    from . import context as contexts
    found: dict[str, Count] = {}
    for module in surface(folder):
        if module.node_count is None:
            continue
        try:
            ctx = contexts.build(module.id, folder, project=project, session=session,
                                 switches={'layers': list(layers)} if layers else None)
            got = call(module.node_count, ctx, addresses)
        except Exception:  # noqa: BLE001, S112  a failing count is left out; the module's own read reports it
            continue
        many = cast(tuple[Any, ...], got) if isinstance(got, tuple) else (got,)
        counted = [one for one in many if isinstance(one, Count)]
        for index, count in enumerate(counted):
            found[module.id if index == 0 else f'{module.id}.{count.many}'] = count
    return found


def node_reads(folder: Path, node: Node, *, project: str | None = None,
               layers: list[str] | None = None) -> dict[str, Any]:
    """What each module on the folder's command surface adds to the read of a node, under the module's id, in module
    id order, BASE-035. Each hook gets a context of its own module with the call's project and toggled layers, and
    returns plain data or None for nothing. A hook that raises adds `{'failed': '<ExceptionType>: <message>'}` and the
    read goes on."""
    from . import context as contexts
    found: dict[str, Any] = {}
    for module in surface(folder):
        if module.node_read is None:
            continue
        try:
            ctx = contexts.build(module.id, folder, project=project,
                                 switches={'layers': list(layers)} if layers else None)
            got = call(module.node_read, ctx, node)
        except Exception as error:  # noqa: BLE001  a failing hook is named in the read, which goes on
            got = {'failed': f'{type(error).__name__}: {error}'}
        if got is not None:
            found[module.id] = got
    return found


def contributions(folder: Path) -> list[tuple[str, tuple[ToolbarItem, ...], tuple[Pane, ...]]]:
    """What the web GUI's workspace offers from this folder: the chassis's own toolbar items and panes while the chassis
    is on the folder's command surface, then each module's on it, in module id order, as `(owner, toolbar, panes)`. A
    disabled module, or one the folder's `modules` setting leaves out, adds nothing, so its tools and panes go."""
    from . import panes
    found: list[tuple[str, tuple[ToolbarItem, ...], tuple[Pane, ...]]] = []
    if on_surface('chassis', folder):
        found.append(('chassis', panes.TOOLBAR, panes.PANES))
    found += [(module.id, module.toolbar, module.panes) for module in surface(folder) if module.toolbar or module.panes]
    return found


def module_files(identifier: str) -> Any:
    """The files of a loaded module's package, a Traversable, so a surface serves the icons and pane files its
    declaration names; None when no module of that id is loaded."""
    import importlib.resources

    from . import loader
    found = loader.get(identifier)
    if found is None or found.module is None:
        return None
    return importlib.resources.files(found.import_name)


def resource_problems(module: Module, root: Any) -> list[str]:
    """The files a module's toolbar items and panes name under `resources/` that `root`, its package's files, does not
    hold, each as the sentence the loader refuses it with."""
    named = [(f'toolbar item {item.id}', path) for item in module.toolbar for path in (item.icon, item.link or '')
             if path.startswith('resources/')]
    named += [(f'pane {pane.id}', path) for pane in module.panes for path in (pane.icon, pane.resource or '')
              if path.startswith('resources/')]
    return [f'{what} names {path}, which is not in the module.' for what, path in named
            if not root.joinpath(*path.split('/')).is_file()]


def work_reads(folder: Path, record: WorkRecord, *, project: str | None = None) -> dict[str, Any]:
    """What each module on the folder's command surface keeps on one work record, under the module's id, in module
    id order, BASE-035. A module keeps its fields in its own tables keyed by the work id, STORE-045, so the work
    table's layout never changes for them. Each hook gets a context of its own module with the call's project and
    returns plain data or None for nothing. A hook that raises adds `{'failed': '<ExceptionType>: <message>'}` and
    the read goes on."""
    from . import context as contexts
    found: dict[str, Any] = {}
    for module in surface(folder):
        if module.work_read is None:
            continue
        try:
            got = call(module.work_read, contexts.build(module.id, folder, project=project), record)
        except Exception as error:  # noqa: BLE001  a failing hook is named in the read, which goes on
            got = {'failed': f'{type(error).__name__}: {error}'}
        if got is not None:
            found[module.id] = got
    return found


TITLE_LIMIT = 120  # the longest line taken as a title when the write's text is that one short line


def first_line(text: Any, limit: int = TITLE_LIMIT) -> str | None:
    """The first line of a text that holds something, stripped, or None; with `limit`, only when the text is that one
    line of at most `limit` characters, as a short single-line memory observation gives its own title."""
    if not isinstance(text, str):
        return None
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return None
    if limit and (len(lines) > 1 or len(lines[0]) > limit):
        return None
    return lines[0]


WHY_STEP = 'add why: one line saying why'


def titled(ctx: Context, what: str, title: Any, why: Any = None, *, why_needed: bool = False,
           title_needed: bool = True, why_step: str = WHY_STEP) -> None:
    """Refuse a write at an address that has no short `title`, or, when it records knowledge or a decision, no `why`,
    MCP-037: the one-line next step says which is missing. `title_needed` off checks the why alone, for a write that
    decides an item already titled, as a ticket's resolution. Every surface an agent calls refuses it; the page is the
    person's, whose forms give the text alone, so there the module takes the title from the text's first line."""
    if ctx.surface == 'web':
        return
    given = {name: isinstance(value, str) and bool(value.strip()) for name, value in (('title', title), ('why', why))}
    needed = {'title': title_needed, 'why': why_needed}
    missing = [name for name in ('title', 'why') if not given[name] and needed[name]]
    if not missing:
        return
    steps = {'title': 'add title: one line saying what this is', 'why': why_step}
    raise Stop(f'{what} has no {" and no ".join(missing)}.', '; '.join(steps[name] for name in missing))


def item_read(folder: Path, address: str, number: int, *, project: str | None = None) -> dict[str, Any] | None:
    """The one item numbered `number` at `address`, MCP-037 and BASE-035: the first module on the folder's command
    surface, in module id order, whose `item_read` hook holds it. The hook returns plain data, at least `kind`,
    `title`, `why`, `body` and `links`, or None; it is returned with `item`, its reference `<address>#<n>`, and
    `module`, the module that wrote it. A hook that raises is passed over, so one module's fault does not hide another's
    item. A decision the chassis's Jev service kept there, CHANGE-ORDER-2026-10-07 item 6 (P185), is read last, with
    `module` jev. None when nothing holds one: the number was never taken there, or its item was deleted."""
    from . import context as contexts
    from . import jev
    from .data import reference
    for module in surface(folder):
        if module.item_read is None:
            continue
        try:
            got = call(module.item_read, contexts.build(module.id, folder, project=project), address, number)
        except Exception:  # noqa: BLE001, S112  another module may hold the item; a fault is the module's own read's
            continue
        if isinstance(got, dict):
            return {'item': reference(address, number), 'module': module.id, **cast(dict[str, Any], got)}
    decided = jev.item(folder, address, number, project=project)
    return None if decided is None else {'item': reference(address, number), 'module': 'jev', **decided}


ITEMS_PAGE = 40  # the items listed at an address at a time, newest first, when the caller names no limit


def node_items(folder: Path, address: str, *, before: int | None = None, limit: int = ITEMS_PAGE,
               kinds: tuple[str, ...] = (), project: str | None = None) -> dict[str, Any]:
    """The items numbered at an address below `before`, newest first, at most `limit`, MCP-037: each with its
    reference `item`, `number`, `module`, `kind`, `title` and `why`; the rest is read by `item_read` on opening it.
    With `kinds`, only items of those kinds, paged through the whole list, a module whose `item_kinds` holds none of
    them not read at all. Each module's `items_at` hook answers a page in one query and the pages are merged by
    number, a number held twice going to the first module in id order as `item_read` gives it, and a decision the
    chassis's Jev service kept there last. A module with `item_read` and no `items_at` is read number by number, the
    slow way, so it still lists. A hook that raises is passed over. Returns `items`, `has_more` and `next_before`, the
    number to pass as `before` for the next page, None on the last; `items_page` pages it as MCP pages a list."""
    import heapq
    from collections.abc import Iterator

    from . import context as contexts
    from . import jev
    from .data import reference
    limit = max(1, int(limit))

    def paged(module_id: str, fetch: Callable[[int | None, int], Any]) -> Iterator[dict[str, Any]]:
        cursor = before
        while True:
            try:
                page = [cast(dict[str, Any], one) for one in cast(list[Any], fetch(cursor, limit) or [])
                        if isinstance(one, dict)]
            except Exception:  # noqa: BLE001  another module may hold items; a fault is the module's own read's
                return
            for one in page:
                yield {'item': reference(address, int(one['number'])), 'number': int(one['number']),
                       'module': module_id, 'kind': one.get('kind'), 'title': one.get('title'), 'why': one.get('why')}
            if len(page) < limit:
                return
            cursor = int(page[-1]['number'])

    def walked(module: Module, ctx: Context) -> Iterator[dict[str, Any]]:
        top = ctx.store.latest_number(address) if ctx.store is not None else 0
        for number in range(min(top + 1, before or top + 1) - 1, 0, -1):
            try:
                got = call(cast(ItemReadHook, module.item_read), ctx, address, number)
            except Exception:  # noqa: BLE001, S112  as item_read passes over a hook that raises
                continue
            if isinstance(got, dict):
                one = cast(dict[str, Any], got)
                yield {'item': reference(address, number), 'number': number, 'module': module.id,
                       'kind': one.get('kind'), 'title': one.get('title'), 'why': one.get('why')}

    def wanted(held: tuple[str, ...]) -> bool:  # a source numbering only other kinds is not read at all
        return not kinds or not held or bool(set(held) & set(kinds))

    sources: list[Iterator[dict[str, Any]]] = []
    for module in surface(folder):
        if module.items_at is None and module.item_read is None or not wanted(module.item_kinds):
            continue
        ctx = contexts.build(module.id, folder, project=project)
        if module.items_at is not None:
            hook = module.items_at
            sources.append(paged(module.id, lambda cursor, size, hook=hook, ctx=ctx: call(hook, ctx, address, cursor,
                                                                                          size)))
        else:
            sources.append(walked(module, ctx))
    if wanted(jev.ITEM_KINDS):
        sources.append(paged('jev', lambda cursor, size: jev.items_at(folder, address, cursor, size,
                                                                      project=project)))
    merged = heapq.merge(*sources, key=lambda one: -one['number'])  # stable: the first source wins a tie
    items: list[dict[str, Any]] = []
    seen: set[int] = set()
    more = False
    for one in merged:
        if one['number'] in seen:
            continue
        seen.add(one['number'])
        if kinds and one['kind'] not in kinds:
            continue
        if len(items) == limit:
            more = True
            break
        items.append(one)
    return {'items': items, 'has_more': more, 'next_before': items[-1]['number'] if more else None}


def latest_item(folder: Path, address: str, *, project: str | None = None) -> dict[str, Any] | None:
    """The last number taken at an address with its item's title, for the brief of a node, MCP-037: `number`, `item`
    and `title`, the title None when that item has been deleted. None when no number has been taken there."""
    from . import context as contexts
    from .data import reference
    store = contexts.build('map', folder, project=project).store
    if store is None:
        return None
    number = store.latest_number(address)
    if not number:
        return None
    found = item_read(folder, address, number, project=project)
    return {'number': number, 'item': reference(address, number), 'title': found.get('title') if found else None}


def last_session_range(folder: Path, address: str, *, project: str | None = None) -> dict[str, Any] | None:
    """What the last agent session to number items at an address took there, as the brief's line under the node says
    it, MCP-037: `session`, the `first` and `last` numbers and `count`, so every surface that shows the brief shows the
    same range; None when no session is known to have taken one there."""
    from . import context as contexts
    store = contexts.build('map', folder, project=project).store
    found = store.last_session(address) if store is not None else None
    if found is None:
        return None
    session, first, end, count = found
    return {'session': session, 'first': first, 'last': end, 'count': count}


def node_brief(folder: Path, address: str, *, client: str | None = None) -> str | None:
    """A node's brief, `metaform://<address>`, MCP-037: the map module's `where` read of the address as it gives it the
    first time an agent session reads the node, with the counts at it and around it and each read named as a tool
    call. A brief is asked for, so it is given whole every time, and the map module's own read is called, never copied:
    the MCP server serves it and the web GUI shows it, so the person sees what the agent reads. None when no map is on
    the folder's surface; Stop when the address holds no element."""
    found = next((module for module in surface(folder) if module.id == 'map'), None)
    if found is None:
        return None
    verb = next(verb for verb in found.verbs if verb.name == 'where')
    ctx = context('map', folder, nouns={'address': address}, surface='mcp', client=client)
    ctx.session = None  # with no session the read is a first read, every time, MCP-039
    result = call(verb.run, ctx)
    return result if isinstance(result, str) else result_json(result)


def project_glossary(folder: Path, *, client: str | None = None) -> str | None:
    """The project's own glossary, `metaform://<project>`, Phase 1c: the map module's `glossary` read as an agent reads
    it, the register standard then the project's terms in the form of Metaform's own glossary, with each call named as
    a tool. Called, never copied, so the MCP server and the page give the same text. None when no map is on the
    folder's surface; Stop when the folder has no project."""
    found = next((module for module in surface(folder) if module.id == 'map'), None)
    if found is None:
        return None
    verb = next((verb for verb in found.verbs if verb.name == 'glossary'), None)
    if verb is None:
        return None
    result = call(verb.run, context('map', folder, surface='mcp', client=client))
    return result if isinstance(result, str) else result_json(result)


def items_page(folder: Path, address: str, *, cursor: str | None = None, kinds: tuple[str, ...] = (),
               limit: int = ITEMS_PAGE, project: str | None = None) -> dict[str, Any]:
    """One page of `node_items`, paged as MCP pages a list: `cursor` is the `nextCursor` the page before gave, passed
    back unchanged, and `nextCursor` is there only when a next page is. The cursor is opaque to the caller; it is the
    number the next page starts below, in hex. Stop for a cursor no page gave, as MCP refuses an invalid cursor.
    https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/pagination"""
    before = None
    if cursor is not None:
        try:
            before = int(cursor, 16)
        except ValueError:
            before = 0
        if before <= 0:
            raise Stop(f'{cursor!r} is not a cursor this list gave.', 'pass back the nextCursor the last page gave, '
                                                                      'unchanged, or leave cursor out for the first')
    listed = node_items(folder, address, before=before, limit=limit, kinds=kinds, project=project)
    page: dict[str, Any] = {'items': listed['items']}
    if listed['has_more']:
        page['nextCursor'] = f"{listed['next_before']:x}"
    return page


def node_view(folder: Path, address: str, *, cursor: str | None = None, kinds: tuple[str, ...] = (),
              limit: int = ITEMS_PAGE, project: str | None = None) -> dict[str, Any]:
    """A node's brief as the person and the agents see it, MCP-037, the one answer the web GUI's /api/brief and the MCP
    map view's `brief` read give: `text`, the brief exactly as an agent reads it at `metaform://<address>`, `brief` the
    same parsed when it is JSON, its `bytes` against `budget`, the folder's node_summary_bytes; `latest`, the last
    number taken there, and `last_session`, the range the last session numbered there; and a page of the items numbered
    there, newest first, of the `kinds` named, as `items_page` pages them. Stop when the address is empty, holds no element, or no map is served."""
    import json

    from . import settings
    address = address.strip()
    if not address:
        raise Stop('A brief is of one address.', 'select a node on the map')
    text = node_brief(folder, address)
    if text is None:
        raise Stop(f'No map is served here, so {address} does not resolve.', 'metaform enable map')
    parsed: Any = None
    if text.startswith('{'):
        try:
            parsed = json.loads(text)
        except ValueError:
            parsed = None
    return {'address': address, 'uri': f'metaform://{address}', 'text': text, 'brief': parsed,
            'bytes': len(text.encode('utf-8')), 'budget': settings.value('node_summary_bytes', folder),
            'latest': latest_item(folder, address, project=project),
            'last_session': last_session_range(folder, address, project=project), 'kinds': list(kinds),
            **items_page(folder, address, cursor=cursor, kinds=kinds, limit=limit, project=project)}


def item_view(folder: Path, ref: str, *, project: str | None = None) -> dict[str, Any]:
    """One item as the person and the agents see it, MCP-037, the one answer the web GUI's /api/item and the MCP views'
    `item` read give: what `item_read` gives, its `address` and `number`, and `text`, the item exactly as an agent
    reads it at `metaform://<address>#<n>`. Stop when `ref` is not `<address>#<n>` or nothing holds it."""
    from .data import parse_reference, reference
    parsed = parse_reference(ref)
    if parsed is None:
        raise Stop(f'{ref!r} is not an item: an item is <address>#<n>, its number in hex.',
                   'choose an item in the brief')
    found = item_read(folder, *parsed, project=project)
    if found is None:
        raise Stop(f'No item {reference(*parsed)} here: its number was never taken there, or its item was deleted.',
                   f'read the brief of {parsed[0]}')
    return {**found, 'address': parsed[0], 'number': parsed[1], 'text': item_text(found)}


def item_text(item: dict[str, Any]) -> str:
    """One item as an agent reads it at `metaform://<address>#<n>`: its reference and title, its kind and why, its body,
    and its links, each `<address>#<n>  <title>` when the linked item has a number."""
    lines = [f"{item['item']}  {item.get('title') or ''}".rstrip()]
    kind = str(item.get('kind') or '')
    lines.append(f'{kind} · why: {item["why"]}' if item.get('why') else kind)
    body = str(item.get('body') or '').strip()
    if body:
        lines += ['', body]
    links = [str(link) for link in cast(list[Any], item.get('links') or [])]
    if links:
        lines += ['', 'Links:', *(f'  {link}' for link in links)]
    return '\n'.join(lines) + '\n'


def result_json(result: Any) -> str:
    """A verb's result as the JSON every surface shows, BASE-036."""
    from . import results
    return results.as_json(result)


def tool_arguments(module: str, verb: Verb, arguments: dict[str, Any], *, ignore: tuple[str, ...] = (),
                   folder: Path | None = None) -> tuple[dict[str, Any], dict[str, Any], list[tuple[str, str]]]:
    """A tool call's nouns and switches, checked as the command line checks them, and a notice per name it does
    not know: kept in the record's `extra` when the verb takes one, BASE-043, otherwise ignored."""
    from . import grammar
    parsed = grammar.from_json(module, verb, arguments, ignore=ignore, folder=folder)
    notices = grammar.keep_fields(module, verb, parsed.nouns, {key: arguments[key] for key in parsed.unknown})
    return parsed.nouns, parsed.switches, parsed.notices + notices


def setting_value(key: str, value: Any, folder: Path, notices: list[tuple[str, str]] | None = None) -> Any:
    """A setting's value from its JSON form, checked as `metaform set` checks it, CLI-027; a text setting sent another
    kind is read as its JSON text and named in `notices`, BASE-044."""
    from . import grammar, settings
    setting = settings.SCHEMA.get(key)
    if setting is None:
        raise Stop(f'{key} is not a setting.', 'metaform help switches')
    try:
        return grammar.switch_value(setting, value, folder, notices)
    except settings.SettingError as error:
        raise Stop(str(error), error.next_step or f'metaform help {setting.switch}') from None


def feedback(folder: Path, text: str, *, layer: str | None = None, report: str | None = None,
             shape: str | None = None, project: str | None = None) -> dict[str, Any]:
    """Save feedback on the Metaform process, with a report and a shape when given, BASE-045."""
    from . import reports
    return reports.feedback(folder, text, layer=layer, report=report, shape=shape, project=project)


def save_report(project: str, run: str, kind: str, text: str, *, store: Store | None = None,
                layer: str | None = None) -> str:
    """Write one report, feedback or shape file for a run and record it, BASE-045. Returns the file name."""
    from . import reports
    return reports.write(project, run, kind, text, store=store, layer=layer)


def list_reports(folder: Path, *, project: str | None = None, kind: str | None = None, layer: str | None = None,
                 limit: int = 500, after: str | None = None) -> Any:
    """The report, feedback and shape files for the folder's project, BASE-045."""
    from . import reports
    return reports.list_reports(folder, project=project, kind=kind, layer=layer, limit=limit, after=after)


def read_report(folder: Path, name: str, *, project: str | None = None) -> str:
    """One listed report file's text exactly, BASE-045."""
    from . import reports
    return reports.read_report(folder, name, project=project)
