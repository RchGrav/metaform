"""The code layer: the project's code symbols tied to the functionality they serve, P165 and P167.

The functional map is the base; the code is a layer on it, a CEL that can be taken off and put back like any other.
Its index, each file's symbols with their calls, uses, bases, tests and imports, comes from an established tool the
project already has, `code_index.py`, and is kept in the module's tables under the layer, so removing the layer removes
it. A symbol is known by its file and its qualified name, so two files of one module name are both held.

A link ties a symbol to the node whose purpose it provides for: the symbol is the PE, and the link is held at the node,
the RE, as every join holds what is known of the relation. At an element, the symbol serves that element's purpose
itself. At a join, it realizes the join's EF: it is the code of the join's provider named with it, or of all the join's
providers when none is, serving the receiver. So the reads credit a join's links to those providers, as their own code,
and show them at the receiver as the code serving it.

Links come three ways. The deterministic pass ties each file the sources layer cites at a node to the symbols the file
declares, narrowed by a cited line range; a cited folder is left to agents. Agents link and unlink as their work shows
them what serves what, with a why: each call is one decision, numbered at the address however many symbols it names.
A workflow skill walks the Addresses up front and proposes links, and reviews the ones the sources pass made, for the
person or an agent to accept or reject. Derived links and proposals are rows of `code_links`; a decision is also an
item of the layer at its node, so it is numbered and read like any other item.

A decided link follows its symbol only where the symbol's identity is shown to survive: the same name below its module
in the same file, as when the provider changed, or in the file git reports it was renamed to. Any other link whose
symbol is gone is orphaned, said in every read, and moved or taken off by its id.

The reads answer in the map's terms what codebase-memory's search_graph, trace_path and detect_changes and GitNexus's
context answer in the code's: the code at an Address, the Address of a symbol or file, a call path between Addresses,
a search over symbols, the Addresses a change touches, and the two gaps, code no Address claims and Addresses no code
serves.
"""
from __future__ import annotations

import fnmatch
import re
import shutil
import subprocess
import uuid
from collections import deque
from collections.abc import Callable, Iterable, Sequence
from contextlib import ExitStack, suppress
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any, cast

from metaform import home, prompt_files, settings
from metaform.data import Item, Node, Store, StoreError, Where, as_object, reference
from metaform.module import Context, Noun, Stop, Verb, surface

from .code_index import (
    EDGE_KINDS,
    Edge,
    Provider,
    Scip,
    Symbol,
    TreeSitter,
    Unavailable,
    code_graph_server,
    file_hash,
    ignored,
    local_name,
    project_files,
    server_target,
    tree_sitter_ready,
)
from .scoped import is_scoped
from .scoped import resolve as resolve_scoped

PROVIDERS = ['auto', 'scip', 'mcp', 'tree-sitter']
KINDS = ('Function', 'Method', 'Class', 'Interface', 'Struct', 'Enum', 'Trait', 'Type')
TYPES = ('Class', 'Interface', 'Struct', 'Enum', 'Trait', 'Type')
NOT_CODE = ('*.md', '*.markdown', '*.rst', '*.txt', '*.xml', '*.html', '*.htm', '*.json', '*.toml', '*.yaml', '*.yml',
            '*.ini', '*.cfg', '*.css', '*.svg', '*.csv', '*.lock')
EDGE_TYPES = tuple(kind for kind in EDGE_KINDS if kind != 'IMPORTS')  # what a trace can follow, symbol to symbol

settings.choice('code_provider', PROVIDERS, 'auto',
                help='Where map code-import reads the code: scip, a SCIP index file; mcp, a code-graph MCP server; '
                     'tree-sitter, the installed grammars; auto, the first of these the project has.')
settings.text('code_server', 'codebase-memory-mcp', person_only=True,
              help='The code-graph MCP server map code-import reads with code_provider mcp: a command started over '
                   'stdio, or an http(s) URL.')
settings.items('code_server_env', ['CBM_*'], person_only=True,
               help='The environment variables a code-graph MCP server started over stdio is given, beside HOME, PATH '
                    'and the other safe defaults the MCP SDK passes; a name ending in * passes every variable it '
                    'starts, such as CBM_* for codebase-memory-mcp\'s CBM_CACHE_DIR.')
settings.text('code_server_project', '',
              help="The project's name on the code-graph MCP server; empty finds it by the project's folder.")
settings.text('code_index', 'index.scip', help='The SCIP index file map code-import reads, relative to the project.')
settings.items('code_kinds', KINDS, choices=[*KINDS, 'Variable', 'Module'], help='The kinds of declaration map code-import keeps, as the code graph labels '
                                         'them; Variable and Module add more, and noise.')
settings.items('code_ignore', NOT_CODE,
               help='Files map code-import never reads, as gitignore patterns, beside .metaform/ignore.txt: the '
                    'documents and data a code graph also parses, whose elements and keys are not code.')

# The layer that holds the code symbols and their links to the map: one name in every project, so code-import, where
# and node reads all find it the same way. Settings cleanup 2026-10-15 made it fixed: no reader gained from another.
CODE_LAYER = 'code'
VARIABLE = 'Code symbols, each providing for the purpose of the element or join it is attached to.'
LINKED, PROPOSED, UNLINKED = 'linked', 'proposed', 'unlinked'
BY_SOURCES = 'sources'
RANGE = re.compile(r'^(?P<path>.*?)(?:#L(?P<a>\d+)(?:-L?(?P<b>\d+))?|:(?P<c>\d+)(?:-(?P<d>\d+))?)$')
# Test code, as codebase-memory's trace_path and GitNexus's impact leave it out by default: a tests folder, test_*.py,
# *_test.go, *.test.ts, *.spec.js and the like.
TESTS = re.compile(r'(^|/)(tests?|__tests__)/|(^|/)test_[^/]*$|_test\.[^/]+$|\.(test|spec)\.[^/]+$')
SHOWN = 5  # the symbols a decision's answer names; the rest are counted

Key = tuple[str, str]  # a symbol: its file and its qualified name


def _prompt(name: str, **fills: str) -> str:
    return prompt_files.text(resources.files(__package__ or 'metaform.modules.map'), name, **fills) or ''


def _layer(ctx: Context) -> str:
    return CODE_LAYER


def _root(store: Store) -> Path:
    return Path(store.project().path)


def _layer_id(store: Store, name: str) -> str | None:
    try:
        return store.layer_ref(name).id
    except StoreError:
        return None


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _plural(count: int, one: str, many: str) -> str:
    return f'{count} {one if count == 1 else many}'


def _git_quiet(root: Path, *args: str) -> str | None:
    """What git prints, or None where the project is no git repository or git fails."""
    git = shutil.which('git')
    if git is None or not (root / '.git').exists():
        return None
    done = subprocess.run([git, *args], cwd=root, capture_output=True, check=False)
    return done.stdout.decode('utf-8', 'replace') if done.returncode == 0 else None


# ------------------------------------------------------------------------------------------------ import

def _open(ctx: Context, root: Path, stack: ExitStack) -> tuple[Provider, dict[str, str], list[str]]:
    """The provider this import reads, with what it lists: the one named, or the first the project has that answers,
    in the order scip, mcp, tree-sitter. A provider is chosen by opening it and listing its files; what follows is read
    from it alone, so an error while reading is said as that provider's and never sends the import to another."""
    chosen = str(ctx.nouns.get('from') or ctx.setting('code_provider') or 'auto')
    if chosen not in PROVIDERS:
        raise Stop(f'{chosen!r} is not a code provider; one of {", ".join(PROVIDERS[1:])}.',
                   'metaform map code-import from=scip')
    index = root / str(ctx.nouns.get('index') or ctx.setting('code_index') or 'index.scip')
    server = str(ctx.setting('code_server') or '')
    kinds = [str(one) for one in cast(list[Any], ctx.setting('code_kinds') or KINDS)]
    order = [chosen] if chosen != 'auto' else [
        one for one, ready in (('scip', index.is_file()), ('mcp', _server_ready(server)),
                               ('tree-sitter', tree_sitter_ready())) if ready]
    reasons: list[Unavailable] = []
    for one in order:
        attempt = ExitStack()
        try:
            provider: Provider
            if one == 'scip':
                provider = Scip(index)
            elif one == 'tree-sitter':
                provider = TreeSitter(root, project_files(root))
            else:
                provider = attempt.enter_context(
                    code_graph_server(server, root, str(ctx.setting('code_server_project') or ''), kinds,
                                      [str(one) for one in cast(list[Any], ctx.setting('code_server_env') or ())]))
            listed = provider.listing()
        except Unavailable as reason:
            with suppress(Exception):
                attempt.close()
            reasons.append(reason)
            continue
        stack.enter_context(attempt.pop_all())
        return provider, listed, [f'{reason.message} Read with {provider.tool} instead.' for reason in reasons]
    if not reasons:
        raise Stop('The project has no SCIP index, no code-graph MCP server and no tree-sitter here.',
                   'write a SCIP index (scip-python index), install codebase-memory-mcp, or install tree-sitter with '
                   'its grammars; then metaform map code-import')
    raise Stop(' '.join(reason.message for reason in reasons), reasons[-1].step)


def _server_ready(server: str) -> bool:
    try:
        server_target(server)
    except (Unavailable, ImportError, ValueError):
        return False
    return True


def _available(ctx: Context, root: Path) -> bool:
    """Whether map code-import has a provider to read here, asked without starting one."""
    index = root / str(ctx.setting('code_index') or 'index.scip')
    return index.is_file() or _server_ready(str(ctx.setting('code_server') or '')) or tree_sitter_ready()


@dataclass
class _Read:
    provider: str
    version: str
    read: int = 0
    unchanged: int = 0
    gone: int = 0
    skipped: int = 0
    symbols: list[Symbol] = field(default_factory=list[Symbol])
    edges: list[Edge] = field(default_factory=list[Edge])
    stamps: dict[str, tuple[str, str | None]] = field(default_factory=dict[str, tuple[str, str | None]])
    changed: list[str] = field(default_factory=list[str])
    removed: list[str] = field(default_factory=list[str])
    stale: list[str] = field(default_factory=list[str])
    notices: list[str] = field(default_factory=list[str])
    unresolved: dict[str, set[str]] = field(default_factory=dict[str, set[str]])
    renamed: dict[str, str] = field(default_factory=dict[str, str])
    commit: str | None = None


def _skip(ctx: Context, root: Path) -> Callable[[str], bool]:
    """Whether a path is left out: under the project's ignore list, BASE-058, or not code, the setting code_ignore."""
    ignore = ignored(home.ignore_patterns(root))
    not_code = ignored([str(one) for one in cast(list[Any], ctx.setting('code_ignore') or ())])

    def skip(path: str) -> bool:
        return ignore(path) or not_code(path)
    return skip


def _held(row: dict[str, Any]) -> Symbol:
    return Symbol(row['qn'], row['name'], row['label'], row['path'], row['start_line'], row['end_line'])


def _read_code(ctx: Context, store: Store, root: Path, layer_id: str | None) -> _Read:
    """What the provider holds that changed since the layer last read it, by each file's stamp and the hash of its
    bytes; every file with full=true. A file whose bytes changed while its stamp at the provider did not is one the
    provider has not indexed again: the layer keeps what it holds of it and says so. Where the calls are resolved
    here, the files calling into a changed file, and those whose calls named what a changed file now declares, are
    read again with it."""
    skip = _skip(ctx, root)
    stored: dict[str, dict[str, Any]] = {}
    if layer_id is not None:
        with store.tables(write=False) as tables:
            stored = {row['path']: row for row in tables.rows('code_files', {'layer_id': layer_id}, limit=0).results}
    full = bool(ctx.nouns.get('full'))
    with ExitStack() as stack:
        provider, listed, notices = _open(ctx, root, stack)
        try:
            kept = {path: stamp for path, stamp in listed.items() if not skip(path)}
            done = _Read(provider.tool, provider.version, skipped=len(listed) - len(kept), notices=notices)
            for path, stamp in kept.items():
                digest = file_hash(root, path)
                held = stored.get(path)
                same = held is not None and held['provider'] == provider.tool
                if held is not None and same and held['stamp'] == stamp and held['hash'] != digest:
                    done.stale.append(path)
                    digest = held['hash']
                done.stamps[path] = (stamp, digest)
                if full or held is None or not same or held['stamp'] != stamp or held['hash'] != digest:
                    done.changed.append(path)
            done.removed = [path for path in stored if path not in kept]
            held_symbols: list[dict[str, Any]] = []
            if provider.by_name and layer_id is not None and (done.changed or done.removed):
                with store.tables(write=False) as tables:
                    held_symbols = list(tables.rows('code_symbols', {'layer_id': layer_id}, limit=0).results)
                    callers = {row['path'] for path in (*done.changed, *done.removed) for row in
                               tables.rows('code_edges', {'layer_id': layer_id, 'target_path': path}, limit=0).results}
                done.changed += sorted(path for path in callers if path in kept and path not in done.changed)
            if done.changed:
                reading = set(done.changed)
                done.symbols, done.edges = provider.read(
                    done.changed, [_held(row) for row in held_symbols if row['path'] not in reading])
                names = {symbol.name for symbol in done.symbols}
                waiting = sorted(path for path, row in stored.items() if provider.by_name and path in kept
                                 and path not in reading and names & set(cast(list[str], row['unresolved'] or [])))
                if waiting:
                    reading |= set(waiting)
                    symbols, edges = provider.read(waiting, [*(_held(row) for row in held_symbols
                                                              if row['path'] not in reading), *done.symbols])
                    done.symbols += symbols
                    done.edges += edges
                    done.changed += waiting
            done.unresolved = provider.unresolved
            done.notices += provider.notices
        except Unavailable as reason:
            raise Stop(reason.message, reason.step) from None
        if done.stale:
            shown = ', '.join(done.stale[:3]) + (', ...' if len(done.stale) > 3 else '')
            done.notices.append(f'{_plural(len(done.stale), "file has", "files have")} changed since {provider.tool} '
                                f'indexed it ({shown}); the layer keeps what the index says until you '
                                f'{provider.refresh} and run map code-import again.')
    done.read, done.gone, done.unchanged = len(done.changed), len(done.removed), len(kept) - len(done.changed)
    done.commit = (_git_quiet(root, 'rev-parse', 'HEAD') or '').strip() or None
    done.renamed = _renamed(root, done.removed, stored)
    return done


def _renamed(root: Path, removed: Sequence[str], stored: dict[str, dict[str, Any]]) -> dict[str, str]:
    """The files gone from the index that git reports renamed since the commit the layer read them at, each with its
    new path, from git diff -M against that commit."""
    found: dict[str, str] = {}
    gone = set(removed)
    for commit in sorted({str(stored[path]['commit']) for path in removed if stored[path].get('commit')}):
        listed = (_git_quiet(root, 'diff', '-M', '--name-status', '-z', commit, '--') or '').split('\0')
        at = 0
        while at < len(listed) - 1:
            status = listed[at]
            if status.startswith(('R', 'C')) and at + 2 < len(listed):
                if status.startswith('R') and listed[at + 1] in gone:
                    found[listed[at + 1]] = listed[at + 2]
                at += 3
            else:
                at += 2
    return found


def _write_index(store: Store, layer_id: str, done: _Read, kinds: set[str]) -> tuple[int, set[Key]]:
    """The changed files' symbols and edges in place of what the layer held for them, in the import's transaction;
    each edge with the file its target is in, from the provider or, where only one file declares the name, from the
    index. Returns how many symbols the layer holds, and which it held before."""
    replaced = {*done.changed, *done.removed}
    with store.tables() as tables:
        before = {(row['path'], row['qn']) for row in tables.rows('code_symbols', {'layer_id': layer_id},
                                                                  limit=0).results}
        for path in replaced:
            tables.delete('code_symbols', {'layer_id': layer_id, 'path': path})
            tables.delete('code_edges', {'layer_id': layer_id, 'path': path})
            tables.delete('code_files', {'layer_id': layer_id, 'path': path})
        for path in done.removed:
            tables.delete('code_edges', {'layer_id': layer_id, 'target_path': path})
        fresh = {(symbol.path, symbol.qn): symbol for symbol in done.symbols if symbol.label in kinds}
        keys = {key for key in before if key[0] not in replaced} | set(fresh)
        where: dict[str, set[str]] = {}
        for path, qn in keys:
            where.setdefault(qn, set()).add(path)
        for symbol in fresh.values():
            tables.insert('code_symbols', {'layer_id': layer_id, 'qn': symbol.qn, 'name': symbol.name,
                                           'label': symbol.label, 'path': symbol.path, 'start_line': symbol.start,
                                           'end_line': symbol.end,
                                           'symbol': symbol.symbol if symbol.symbol != symbol.qn else None})
        held: set[tuple[str, str, str, str, str]] = set()
        for edge in done.edges:
            paths = where.get(edge.target, set())
            if edge.target_path:
                target_path = edge.target_path if edge.target_path in paths else ''
            else:
                target_path = next(iter(paths)) if len(paths) == 1 else edge.path if edge.path in paths else ''
            if not target_path or (edge.kind != 'IMPORTS' and (edge.path, edge.source) not in keys):
                continue
            key = (edge.path, edge.source, target_path, edge.target, edge.kind)
            if key in held:
                continue
            held.add(key)
            tables.insert('code_edges', {'layer_id': layer_id, 'source': edge.source, 'target': edge.target,
                                         'kind': edge.kind, 'path': edge.path, 'line': edge.line,
                                         'target_path': target_path})
        for path in done.changed:  # what the other files call in a changed file that it no longer declares
            for row in tables.rows('code_edges', {'layer_id': layer_id, 'target_path': path}, limit=0).results:
                if (path, row['target']) not in keys:
                    tables.delete('code_edges', {'layer_id': layer_id, 'path': row['path'], 'source': row['source'],
                                                 'target_path': path, 'target': row['target'], 'kind': row['kind']})
        per_file: dict[str, int] = {}
        for symbol in fresh.values():
            per_file[symbol.path] = per_file.get(symbol.path, 0) + 1
        for path in done.changed:
            stamp, digest = done.stamps[path]
            missing = sorted(done.unresolved.get(path, ()))[:400]
            tables.insert('code_files', {'layer_id': layer_id, 'path': path, 'stamp': stamp, 'hash': digest,
                                         'provider': done.provider, 'symbols': per_file.get(path, 0),
                                         'read': home.now(), 'commit': done.commit, 'unresolved': missing or None})
    return len(keys), before


def code_import(ctx: Context) -> Any:
    """Read the code into the code layer from the provider, only the files that changed; carry each decided link
    whose symbol is shown to be the same under another name; then tie each file the sources layer cites to the
    symbols it declares, at the node that cites it."""
    store = ctx.require_store()
    root, name = _root(store), _layer(ctx)
    done = _read_code(ctx, store, root, _layer_id(store, name))
    kinds = {str(one) for one in cast(list[Any], ctx.setting('code_kinds') or KINDS)}
    with store.atomic():
        layer = store.layer(name, 'map', VARIABLE, kind='layer', mutable=True, hideable=True, ready=True)
        _adopt_items(store, name, layer.id)
        total, before = _write_index(store, layer.id, done, kinds)
        carried, orphaned = _reanchor(store, layer.id, before, done.renamed)
        linked = _link_sources(store, layer.id)
    counts: dict[str, int] = {}
    with store.tables(write=False) as tables:
        for edge in tables.rows('code_edges', {'layer_id': layer.id}, limit=0).results:
            counts[edge['kind']] = counts.get(edge['kind'], 0) + 1
    result: dict[str, Any] = {
        'layer': name, 'provider': ' '.join(part for part in (done.provider, done.version) if part),
        'files': {'read': done.read, 'unchanged': done.unchanged, 'gone': done.gone, 'ignored': done.skipped,
                  **({'stale': len(done.stale)} if done.stale else {})},
        'symbols': total, 'edges': counts, 'linked': linked}
    if carried:
        result['carried'] = carried
    if orphaned:
        result['orphaned'] = orphaned
        done.notices.append(f'{_plural(orphaned, "decided link names a symbol", "decided links name symbols")} the '
                            'code no longer declares; map code-gaps lists each with its id, to move it to the symbol '
                            'that serves now or take it off.')
    result['next'] = [ctx.calls('metaform map code-gaps'), ctx.calls('metaform map code-context address=<address>')]
    if done.notices:
        result['notices'] = done.notices
    return result


# ------------------------------------------------------------------------------------------------ what is linked

@dataclass(frozen=True)
class Link:
    """One row of code_links: the node it is held at, the symbol, how it came and its state. At an element, the
    symbol serves the element's own purpose; at a join, it realizes the join's EF, the code of the provider named with
    it, or of every provider of the join when none is, serving the receiver."""
    id: str
    kind: str
    target: str
    qn: str
    name: str
    label: str
    path: str
    by: str
    state: str
    why: str | None
    item_id: str | None
    proposal: dict[str, Any] | None
    element: str | None = None
    receiver: str | None = None
    providers: tuple[str, ...] = ()
    provider: str | None = None  # the provider's Address, at a join, when the link names one
    provider_id: str | None = None

    @property
    def key(self) -> Key:
        return (self.path, self.qn)

    @property
    def at(self) -> tuple[str, ...]:
        """The Addresses whose own code the symbol is: the element, or the join's provider, or its providers."""
        if self.kind == 'element':
            return (self.element,) if self.element else ()
        return (self.provider,) if self.provider else self.providers

    @property
    def place(self) -> Any:
        """Where the link is held, as code-link names it: an Address, or a join's receiver and provider."""
        if self.kind == 'element':
            return self.element
        return {'receiver': self.receiver, 'provider': self.provider or ', '.join(self.providers)}

    @property
    def numbered_at(self) -> str | None:
        return self.element if self.kind == 'element' else self.receiver

    @property
    def decided(self) -> bool:
        """Whether an agent or the person decided it, or proposed it, rather than the sources pass alone."""
        return bool(self.item_id or self.proposal or self.by != BY_SOURCES)


@dataclass
class Code:
    """One read of the code layer: its symbols by file and qualified name, its links, and its edges when asked for."""
    name: str
    layer_id: str
    symbols: dict[Key, dict[str, Any]]
    links: list[Link]
    edges: list[dict[str, Any]]
    _at: dict[Key, list[str]] = field(default_factory=dict[Key, list[str]])
    _serves: dict[Key, list[str]] = field(default_factory=dict[Key, list[str]])

    def __post_init__(self) -> None:
        for link in self.linked():
            for address in link.at:
                if address not in self._at.setdefault(link.key, []):
                    self._at[link.key].append(address)
            if link.kind == 'join' and link.receiver and link.receiver not in self._serves.setdefault(link.key, []):
                self._serves[link.key].append(link.receiver)

    def linked(self) -> list[Link]:
        """The links in force whose symbol the code still declares."""
        return [link for link in self.links if link.state == LINKED and link.key in self.symbols]

    def at(self, key: Key) -> list[str]:
        return list(self._at.get(key, ()))

    def serves(self, key: Key) -> list[str]:
        return list(self._serves.get(key, ()))

    def orphaned(self) -> list[Link]:
        """Decided or proposed links whose symbol the code no longer declares."""
        return [link for link in self.links if link.key not in self.symbols and link.decided
                and (link.state in (LINKED, PROPOSED) or link.proposal)]

    def name_of(self, key: Key) -> str:
        return str(self.symbols.get(key, {}).get('name') or key[1])


def _source(edge: dict[str, Any]) -> Key:
    return (edge['path'], edge['source'])


def _target(edge: dict[str, Any]) -> Key:
    return (edge['target_path'] or '', edge['target'])


def _places(store: Store) -> tuple[dict[str, str], dict[str, tuple[str | None, tuple[str, ...]]]]:
    """Each element's address by its id, and each join's receiver and providers by the join's id, read raw so a link
    at a node out of context still names where it is."""
    graph = store.graph(raw=True, limit=0)
    elements = {one.element.id: one.element.address for one in graph.elements}
    joins = {join.id: (join.receiver_address, tuple(held.address for held in join.elements if held.address))
             for join in graph.joins}
    return elements, joins


def _link(row: dict[str, Any], elements: dict[str, str],
          joins: dict[str, tuple[str | None, tuple[str, ...]]]) -> Link:
    receiver, providers = joins.get(row['node_id'], (None, ())) if row['node_kind'] == 'join' else (None, ())
    provider_id = row.get('provider') if row['node_kind'] == 'join' else None
    return Link(row['link_id'], row['node_kind'], row['node_id'], row['qn'], row['name'] or row['qn'],
                row['label'] or '', row['path'] or '', row['by'] or '', row['state'], row['why'], row['item_id'],
                cast(dict[str, Any] | None, row['proposal']),
                elements.get(row['node_id']) if row['node_kind'] == 'element' else None, receiver, providers,
                elements.get(provider_id) if provider_id else None, provider_id)


def _links(store: Store, layer_id: str) -> list[Link]:
    with store.tables(write=False) as tables:
        rows = list(tables.rows('code_links', {'layer_id': layer_id}, limit=0).results)
    if not rows:
        return []
    elements, joins = _places(store)
    return [_link(row, elements, joins) for row in rows]


def _code(ctx: Context, store: Store, *, edges: bool = False) -> Code:
    name = _layer(ctx)
    layer_id = _layer_id(store, name)
    if layer_id is None:
        raise Stop(f'There is no code layer {name} here yet.', 'metaform map code-import')
    with store.tables(write=False) as tables:
        symbols = {(row['path'], row['qn']): row
                   for row in tables.rows('code_symbols', {'layer_id': layer_id}, limit=0).results}
        held = list(tables.rows('code_edges', {'layer_id': layer_id}, limit=0).results) if edges else []
    return Code(name, layer_id, symbols, _links(store, layer_id), held)


def _row(code: Code, key: Key, *, degree: dict[Key, tuple[int, int]] | None = None) -> dict[str, Any]:
    """A symbol as codebase-memory's search_graph rows give it, name, qn, label, file and lines, with the Addresses
    whose own code it is and those it serves through a join; one the index no longer holds is said to be gone."""
    row = code.symbols.get(key)
    if row is None:
        return {'qn': key[1], 'file': key[0], 'gone': True}
    shown: dict[str, Any] = {'name': row['name'], 'qn': key[1], 'label': row['label'], 'file': key[0],
                             'lines': f"{row['start_line']}-{row['end_line']}"}
    if degree is not None:
        shown['in'], shown['out'] = degree.get(key, (0, 0))
    shown['address'] = code.at(key)
    serves = code.serves(key)
    if serves:
        shown['serves'] = serves
    return shown


def _degrees(code: Code) -> dict[Key, tuple[int, int]]:
    counts: dict[Key, list[int]] = {}
    for edge in code.edges:
        if edge['kind'] == 'CALLS':
            counts.setdefault(_target(edge), [0, 0])[0] += 1
            counts.setdefault(_source(edge), [0, 0])[1] += 1
    return {key: (pair[0], pair[1]) for key, pair in counts.items()}


# ------------------------------------------------------------------------------------------------ the sources pass

def _cited(value: str, root: Path) -> tuple[str, tuple[int, int] | None]:
    """A path ref as a repository-relative path, with its line range when it names one: `path:12-40`, `path#L12-L40`."""
    text = value.strip().replace('\\', '/')
    lines: tuple[int, int] | None = None
    found = RANGE.match(text)
    if found and (found['a'] or found['c']):
        first = int(found['a'] or found['c'])
        lines = (first, int(found['b'] or found['d'] or first))
        text = found['path']
    if Path(text).is_absolute():
        try:
            text = Path(text).relative_to(root).as_posix()
        except ValueError:
            pass
    return text.removeprefix('./').rstrip('/'), lines


def _cites(store: Store) -> list[tuple[Node, str, tuple[int, int] | None]]:
    """Every path the sources layer cites, at the node citing it."""
    root = _root(store)
    try:
        sources = [item for item in store.layer_items('sources', limit=0).results if isinstance(item, Item)]
    except StoreError:
        return []
    return [(item.target, *_cited(ref.value, root)) for item in sources for ref in item.refs
            if ref.key == 'path' and ref.value.strip()]


LinkKey = tuple[str, str, str, str]  # a link: its node's kind and id, its symbol's file and qualified name


def _link_key(row: dict[str, Any]) -> LinkKey:
    return (row['node_kind'], row['node_id'], row['path'] or '', row['qn'])


def _where_link(layer_id: str, key: LinkKey) -> dict[str, Any]:
    return {'layer_id': layer_id, 'node_kind': key[0], 'node_id': key[1], 'path': key[2], 'qn': key[3]}


def _link_sources(store: Store, layer_id: str) -> dict[str, int]:
    """Tie each file a node's sources cite to the symbols it declares, at that node; a cited line range narrows it to
    the symbols that overlap it. A cited folder links nothing: what in it serves which purpose is for an agent to say.
    A link this pass made that its citation no longer gives is taken off; one an agent decided is left as it is."""
    with store.tables(write=False) as tables:
        symbols = tables.rows('code_symbols', {'layer_id': layer_id}, limit=0).results
        held = {_link_key(row): row for row in tables.rows('code_links', {'layer_id': layer_id}, limit=0).results}
    by_file: dict[str, list[dict[str, Any]]] = {}
    for row in symbols:
        by_file.setdefault(row['path'], []).append(row)
    wanted: dict[LinkKey, dict[str, Any]] = {}
    folders = 0
    for node, path, lines in _cites(store):
        rows = by_file.get(path)
        if rows is None:
            folders += any(one.startswith(path + '/') for one in by_file) if path else 0
            continue
        for row in rows:
            if lines is None or (row['start_line'] <= lines[1] and lines[0] <= row['end_line']):
                wanted[(node.kind, node.id, row['path'], row['qn'])] = row
    added = removed = 0
    with store.tables() as tables:
        for key, row in wanted.items():
            if key in held:
                continue
            tables.insert('code_links', {**_where_link(layer_id, key), 'link_id': _new_id(), 'name': row['name'],
                                         'label': row['label'], 'state': LINKED, 'by': BY_SOURCES})
            added += 1
        for key, link in held.items():
            if (link['by'] == BY_SOURCES and link['item_id'] is None and link['proposal'] is None
                    and link['state'] == LINKED and key not in wanted):
                tables.delete('code_links', _where_link(layer_id, key))
                removed += 1
    result = {'added': added, 'removed': removed, 'nodes': len({(kind, target) for kind, target, _, _ in wanted})}
    if folders:
        result['folders'] = folders
    return result


def _reanchor(store: Store, layer_id: str, before: set[Key], renamed: dict[str, str]) -> tuple[list[dict[str, Any]],
                                                                                              int]:
    """Carry each decided or proposed link whose symbol the import no longer finds to the symbol it is shown to be
    now: one this import brought, with the same name below its module and the same kind, in the same file, as when the
    provider changed and names modules otherwise, or in the file git reports the old one renamed to. Never to a symbol
    the layer held before, and never by a name alone: any other link is orphaned, to be moved or taken off by its id.
    Returns each link carried, from and to, and how many were orphaned."""
    with store.tables(write=False) as tables:
        symbols = {(row['path'], row['qn']): row
                   for row in tables.rows('code_symbols', {'layer_id': layer_id}, limit=0).results}
        rows = list(tables.rows('code_links', {'layer_id': layer_id}, limit=0).results)
    links = [row for row in rows if ((row['path'] or ''), row['qn']) not in symbols
             and (row['item_id'] or row['proposal'] or row['by'] != BY_SOURCES)]
    if not links:
        return [], 0
    fresh: dict[tuple[str, str], list[Key]] = {}
    for key in symbols:
        if key not in before:
            fresh.setdefault((key[0], local_name(key[1], key[0])), []).append(key)
    sharing: dict[str, int] = {}
    for row in rows:
        if row['item_id']:
            sharing[row['item_id']] = sharing.get(row['item_id'], 0) + 1
    elements, joins = _places(store)
    carried: list[dict[str, Any]] = []
    orphaned = 0
    edits: list[tuple[str, dict[str, Any]]] = []
    with store.tables() as tables:
        for link in links:
            old = link['path'] or ''
            local = local_name(link['qn'], old)
            found: Key | None = None
            for path in (old, renamed.get(old, '')):
                candidates = fresh.get((path, local), []) if path else []
                same = [key for key in candidates if symbols[key]['label'] == link['label']]
                if len(same or candidates) == 1:
                    found = (same or candidates)[0]
                    break
            if found is None:
                orphaned += link['state'] in (LINKED, PROPOSED) or link['proposal'] is not None
                continue
            symbol = symbols[found]
            there = tables.get('code_links', _where_link(layer_id, (link['node_kind'], link['node_id'], *found)))
            if there is not None:
                if there['by'] != BY_SOURCES or there['item_id'] or there['proposal']:
                    orphaned += 1  # the node holds a decision on that symbol already; this one stays to be read
                    continue
                tables.delete('code_links', _where_link(layer_id, _link_key(there)))
            tables.update('code_links', _where_link(layer_id, _link_key(link)),
                          {'qn': symbol['qn'], 'path': symbol['path'], 'name': symbol['name'],
                           'label': symbol['label']})
            if link['item_id'] and sharing.get(link['item_id']) == 1:
                edits.append((link['item_id'], {'value': _value(symbol, link['by'] or '', link['state'], link['why']),
                                                'refs': [list(pair) for pair in _refs([symbol])]}))
            moved: dict[str, Any] = {'node': _link(link, elements, joins).place, 'from': link['qn'],
                                     'to': symbol['qn'], 'file': symbol['path']}
            if symbol['path'] != old:
                moved['renamed_from'] = old
            carried.append(moved)
    for item_id, changes in edits:
        store.edit(item_id, changes)
    return carried, orphaned


def _adopt_items(store: Store, name: str, layer_id: str) -> None:
    """Links a store written before code_links held as items of the layer, read once, while code_links holds none of
    the layer: those the sources pass made are taken off, to be made again as rows; a proposal becomes a row; a
    decision keeps its item and gains its row."""
    with store.tables(write=False) as tables:
        if tables.rows('code_links', {'layer_id': layer_id}, limit=1).results:
            return
    try:
        items = [item for item in store.layer_items(name, limit=0).results if isinstance(item, Item)]
    except StoreError:
        return
    for item in items:
        qn = next((ref.value for ref in item.refs if ref.key == 'qn'), '')
        value = as_object(item.value) or {}
        if not qn or 'symbols' in value:
            continue
        by, state, why = str(value.get('by') or ''), str(value.get('state') or LINKED), value.get('why')
        row: dict[str, Any] = {'layer_id': layer_id, 'node_kind': item.target.kind, 'node_id': item.target.id,
                               'qn': qn, 'link_id': _new_id(), 'name': value.get('symbol'),
                               'label': value.get('label'), 'path': value.get('file') or '', 'state': state,
                               'by': by, 'why': why, 'item_id': item.id}
        if by == BY_SOURCES or state == PROPOSED:
            store.remove(item.id)
            if by == BY_SOURCES:
                continue
            row.update(item_id=None, proposal={'state': LINKED, 'why': why, 'by': by})
        with store.tables() as tables:
            if tables.get('code_links', _where_link(layer_id, _link_key(row))) is None:
                tables.insert('code_links', row)


def _value(row: dict[str, Any], by: str, state: str, why: Any = None) -> dict[str, Any]:
    value: dict[str, Any] = {'symbol': row['name'], 'label': row['label'], 'file': row['path'], 'by': by,
                             'state': state}
    if why:
        value['why'] = why
    return value


def _refs(rows: Sequence[dict[str, Any]]) -> list[tuple[str, str]]:
    """A decision's refs: the files and the symbols it names, the first eight of each."""
    files = list(dict.fromkeys(str(row['path']) for row in rows))
    return [*(('path', path) for path in files[:8]), *(('qn', str(row['qn'])) for row in rows[:8])]


# ------------------------------------------------------------------------------------------------ linking

def _node(store: Store, ctx: Context) -> tuple[Node, str, str | None]:
    """The node a link is at, by its Address, an element; with provider, the join that element receives holding the
    provider. Returned with the address its items are numbered at and, at a join, the provider's id."""
    address = str(ctx.nouns.get('node') or '').strip()
    if not address:
        raise Stop('A link names its node: node=<address>.', 'metaform map code-link op=add node=<address> '
                                                             'symbol=<qn> why="<why>"')
    provider = ctx.nouns.get('provider')
    if provider:
        try:
            node = store.purpose(address, provider)
        except StoreError as error:
            raise Stop(str(error), f'metaform map joins element={address}') from None
        held = store.element(str(provider))
        return node, address, held.id if held is not None else None
    element = store.element(address)
    if element is None:
        from . import _missing  # pyright: ignore[reportPrivateUsage]  # shared within the map module
        raise _missing(store, address)
    return Node('element', element.id), element.address, None


def _symbols(ctx: Context, code: Code) -> list[Key]:
    return _resolve(code, str(ctx.nouns.get('symbol') or '').strip(), str(ctx.nouns.get('file') or '').strip())


def _resolve(code: Code, given: str, path: str = '') -> list[Key]:
    """The symbols a call names: `given`, a qn or, as search_graph and get_code_snippet take it, a short name or the
    end of a qn when only one symbol has it, in `path` when that is named too; or, with `path` alone, every symbol the
    file declares."""
    if path and not given:
        found = [key for key in code.symbols if key[0] == path]
        if not found:
            raise Stop(f'The code layer holds no symbol in {path}. If the file is new or changed, read it in first.',
                       'metaform map code-import')
        return found
    if not given:
        raise Stop('A link names its code: symbol=<qn or name>, or file=<path>.', 'metaform map code-search '
                                                                                  'query=<words>')
    keys = [key for key in code.symbols if not path or key[0] == path]
    exact = [key for key in keys if key[1] == given]
    matches = exact or [key for key in keys if code.symbols[key]['name'] == given or key[1].endswith('.' + given)]
    if len(matches) == 1:
        return matches
    if matches:
        shown = ', '.join(f'{qn} in {file}' for file, qn in matches[:5])
        raise Stop(f'{len(matches)} symbols are named {given}: {shown}. Name one by its qn, and its file with file=.',
                   f'metaform map code-search name_pattern=^{re.escape(given.rpartition(".")[2])}$')
    raise Stop(f'The code layer holds no symbol {given}{f" in {path}" if path else ""}. If you just wrote it, read '
               'the changed files in first; only the files that changed are read.', 'metaform map code-import')


def _number(store: Store, item_id: str, address: str, title: str, why: str) -> str:
    """The decision's number at its address, MCP-037: the one it has, or the next from the project's counter, with
    its title and why."""
    with store.tables(write=False) as tables:
        held = tables.get('numbered', {'kind': 'code', 'item_id': item_id})
    number = held['number'] if held is not None and held['address'] == address else store.number(address)
    with store.tables() as tables:
        key = {'kind': 'code', 'item_id': item_id}
        changes = {'address': address, 'number': number, 'title': title, 'why': why}
        if tables.update('numbered', key, changes) is None:
            tables.insert('numbered', {**key, **changes})
    return reference(address, number)


def _item_ref(store: Store, item_id: str | None) -> str | None:
    if not item_id:
        return None
    with store.tables(write=False) as tables:
        held = tables.get('numbered', {'kind': 'code', 'item_id': item_id})
    return reference(held['address'], held['number']) if held is not None else None


def _why(ctx: Context, op: str) -> str:
    why = str(ctx.nouns.get('why') or '').strip()
    if not why:
        raise Stop(f'op={op} records a decision, so it carries a why: one short line saying how the code serves the '
                   'purpose, or why it does not.', f'metaform map code-link op={op} ... why="<why>"')
    return why


def _title(ctx: Context, rows: Sequence[dict[str, Any]], address: str, state: str) -> str:
    given = str(ctx.nouns.get('title') or '').strip()
    if given:
        return given
    verb = ('provides' if len(rows) == 1 else 'provide') if state == LINKED else (
        'does not provide' if len(rows) == 1 else 'do not provide')
    files = {row['path'] for row in rows}
    named = (rows[0]['name'] if len(rows) == 1 else f"{len(rows)} symbols of {rows[0]['path']}" if len(files) == 1
             else f"{rows[0]['name']} and {len(rows) - 1} more")
    return f'{named} {verb} for {address}'


def _decision(store: Store, code: Code, node: Node, address: str, provider: str | None,
              entries: Sequence[tuple[dict[str, Any], Link | None]], state: str, by: str, why: str,
              title: str) -> dict[str, Any]:
    """One decision, a link in force or taken off for every symbol it names: one item of the layer at its node,
    numbered at the address with its title and why, and a row for each symbol pointing at that item."""
    rows = [row for row, _ in entries]
    value = _value(rows[0], by, state, why) if len(rows) == 1 else {
        'symbols': [row['name'] for row in rows[:8]], 'count': len(rows),
        'files': list(dict.fromkeys(row['path'] for row in rows))[:8], 'by': by, 'state': state, 'why': why}
    added = store.add_item(code.name, node, value, refs=_refs(rows))
    if not isinstance(added, Item):
        raise Stop(' '.join(notice.message for notice in added.notices) or 'The link was not written.',
                   f'metaform map node {node.kind}:{node.id}')
    shown: list[dict[str, Any]] = []
    with store.tables() as tables:
        for row, link in entries:
            key = _where_link(code.layer_id, (node.kind, node.id, row['path'], row['qn']))
            changes = {'state': state, 'by': by, 'why': why, 'item_id': added.id, 'proposal': None,
                       'name': row['name'], 'label': row['label'],
                       'provider': provider if node.kind == 'join' else None}
            link_id = link.id if link is not None else _new_id()
            if tables.update('code_links', key, changes) is None:
                tables.insert('code_links', {**key, **changes, 'link_id': link_id})
            if len(shown) < SHOWN:
                shown.append({'symbol': row['name'], 'qn': row['qn'], 'file': row['path'], 'id': link_id})
    result: dict[str, Any] = {'item': _number(store, added.id, address, title, why), 'title': title, 'why': why,
                              'state': state, 'count': len(rows), 'symbols': shown}
    if len(rows) > SHOWN:
        result['more'] = len(rows) - SHOWN
    return result


def _gone_row(link: Link) -> dict[str, Any]:
    """A link's symbol as the link remembers it, for a decision on a link whose symbol is gone."""
    return {'qn': link.qn, 'name': link.name, 'label': link.label, 'path': link.path}


def code_link(ctx: Context) -> Any:
    """Link code symbols to the node whose purpose they provide for, unlink them, move a link to the symbol that
    serves now, or propose links and accept or reject them; with no op, list the proposals waiting."""
    store = ctx.require_store()
    op = str(ctx.nouns.get('op') or 'list')
    if op not in OPS:
        raise Stop(f'{op!r} is not a code-link operation: {", ".join(OPS)}.', 'metaform help map code-link')
    code = _code(ctx, store)
    if op == 'list':
        address = ctx.nouns.get('node')
        waiting = [link for link in code.links if link.proposal
                   and (not address or address in (link.element, link.receiver, *link.providers))]
        return {'proposed': [{'id': link.id, 'node': link.place, 'symbol': _row(code, link.key),
                              'proposes': (link.proposal or {}).get('state'), 'why': (link.proposal or {}).get('why'),
                              'by': (link.proposal or {}).get('by')} for link in waiting]}
    if op in ('accept', 'reject'):
        return _decide(ctx, store, code, op)
    if op == 'move':
        return _move(ctx, store, code)
    by = str(ctx.nouns.get('by') or ctx.client or ctx.session or ctx.surface)
    if op == 'remove' and ctx.nouns.get('id'):
        link = _by_id(ctx, code)
        why = _why(ctx, op)
        if link.state == UNLINKED and link.item_id:
            return {'node': link.place, 'already': 1}
        with store.atomic():
            return {'node': link.place, **_decision(
                store, code, Node.of(link.kind, link.target), link.numbered_at or '', link.provider_id,
                [(code.symbols.get(link.key) or _gone_row(link), link)], UNLINKED, by, why,
                _title(ctx, [_gone_row(link)], link.numbered_at or '', UNLINKED))}
    node, address, provider = _node(store, ctx)
    keys = _symbols(ctx, code)
    why = _why(ctx, op)
    held = {link.key: link for link in code.links if link.kind == node.kind and link.target == node.id}
    unlink = op == 'remove' or (op == 'propose' and bool(ctx.nouns.get('unlink')))
    if unlink and not any(key in held and held[key].state == LINKED for key in keys):
        elsewhere = sorted({str(one.place) for one in code.links if one.key in keys and one.state == LINKED})
        raise Stop(f'No symbol named is linked at {address}' + (f'; it is linked at {"; ".join(elsewhere)}.'
                                                                  if elsewhere else '.'),
                   ctx.calls(f'metaform map code-context symbol={keys[0][1]} file={keys[0][0]}'))
    state = UNLINKED if unlink else LINKED
    with store.atomic():
        if op == 'propose':
            proposed = [_propose(store, code, node, provider, code.symbols[key], held.get(key), state, by, why)
                        for key in keys]
            made = [one for one in proposed if 'id' in one]
            result: dict[str, Any] = {'node': address, 'proposes': state, 'count': len(made), 'links': made[:SHOWN]}
            if len(made) > SHOWN:
                result['more'] = len(made) - SHOWN
            if len(made) < len(proposed):
                result['already'] = len(proposed) - len(made)
            if made:
                where = f' provider={ctx.nouns["provider"]}' if ctx.nouns.get('provider') else ''
                result['next'] = [ctx.calls(f'metaform map code-link op=accept node={address}{where}')]
            return result
        entries: list[tuple[dict[str, Any], Link | None]] = []
        already = 0
        for key in keys:
            link = held.get(key)
            if link is None and unlink:
                continue
            if link is not None and link.state == state and link.item_id and (
                    provider is None or link.provider_id == provider):
                already += 1
                continue
            entries.append((code.symbols[key], link))
        done: dict[str, Any] = {'node': address}
        if entries:
            done.update(_decision(store, code, node, address, provider, entries, state, by, why,
                                  _title(ctx, [row for row, _ in entries], address, state)))
        if already:
            done['already'] = already
        return done


def _by_id(ctx: Context, code: Code) -> Link:
    wanted = str(ctx.nouns.get('id') or '').strip()
    found = next((link for link in code.links if link.id == wanted), None)
    if found is None:
        raise Stop(f'No link {wanted!r} in the code layer.', ctx.calls('metaform map code-gaps'))
    return found


def _move(ctx: Context, store: Store, code: Code) -> Any:
    """Point a decided or proposed link at the symbol that serves now, keeping its number, with a why: the way out for
    a link whose symbol is gone."""
    link = _by_id(ctx, code)
    if not link.decided:
        raise Stop('That link is the sources pass\'s: it follows the file its node cites, so change the citation, or '
                   'take the link off.', ctx.calls(f'metaform map code-link op=remove id={link.id} why="<why>"'))
    keys = _symbols(ctx, code)
    if len(keys) != 1:
        raise Stop('A link moves to one symbol: symbol=<qn>, with file= where two files declare it.',
                   'metaform map code-search query=<words>')
    row = code.symbols[keys[0]]
    why = _why(ctx, 'move')
    with store.atomic(), store.tables() as tables:
        target = _where_link(code.layer_id, (link.kind, link.target, row['path'], row['qn']))
        there = tables.get('code_links', target)
        if there is not None and (there['item_id'] or there['proposal'] or there['by'] != BY_SOURCES):
            raise Stop(f"{row['qn']} is already linked at {link.place}.",
                       ctx.calls(f'metaform map code-link op=remove id={link.id} why="<why>"'))
        if there is not None:
            tables.delete('code_links', target)
        tables.update('code_links', _where_link(code.layer_id, (link.kind, link.target, link.path, link.qn)),
                      {'qn': row['qn'], 'path': row['path'], 'name': row['name'], 'label': row['label'], 'why': why})
        numbered = tables.get('numbered', {'kind': 'code', 'item_id': link.item_id}) if link.item_id else None
        if numbered is not None:
            tables.update('numbered', {'kind': 'code', 'item_id': link.item_id},
                          {'why': f"{numbered['why'] or ''} Moved from {link.qn} to {row['qn']}: {why}".strip()})
    return {'id': link.id, 'node': link.place, 'from': link.qn, 'to': row['qn'], 'file': row['path'], 'why': why,
            **({'item': _item_ref(store, link.item_id)} if link.item_id else {})}


def _propose(store: Store, code: Code, node: Node, provider: str | None, row: dict[str, Any], link: Link | None,
             wanted: str, by: str, why: str) -> dict[str, Any]:
    """A proposal waits on its link for the person or another agent: a new link, a link the sources pass made to be
    kept as a decision, or a link to be taken off."""
    said = {'symbol': row['name'], 'qn': row['qn'], 'file': row['path']}
    if link is None and wanted == UNLINKED:
        return said
    if link is not None and link.item_id and link.state == wanted:
        return said
    proposal = {'state': wanted, 'why': why, 'by': by}
    key = _where_link(code.layer_id, (node.kind, node.id, row['path'], row['qn']))
    with store.tables() as tables:
        if link is None:
            link_id = _new_id()
            tables.insert('code_links', {**key, 'link_id': link_id, 'name': row['name'], 'label': row['label'],
                                         'state': PROPOSED, 'by': by, 'proposal': proposal,
                                         'provider': provider if node.kind == 'join' else None})
        else:
            link_id = link.id
            tables.update('code_links', key, {'proposal': proposal})
    return {**said, 'id': link_id}


def _decide(ctx: Context, store: Store, code: Code, op: str) -> Any:
    """Accept proposals, which makes each node's one decision numbered at its address with the proposals' why, or
    reject them, which leaves the links as they were; named by id, or every proposal at a node, narrowed by symbol or
    file."""
    if ctx.nouns.get('id'):
        chosen = [_by_id(ctx, code)]
    else:
        node, _, provider = _node(store, ctx)
        chosen = [link for link in code.links if link.kind == node.kind and link.target == node.id
                  and (provider is None or link.provider_id in (None, provider))]
        if ctx.nouns.get('symbol') or ctx.nouns.get('file'):
            keys = set(_symbols(ctx, code))
            chosen = [link for link in chosen if link.key in keys]
    chosen = [link for link in chosen if link.proposal]
    if not chosen:
        raise Stop('No proposal waits there.', ctx.calls('metaform map code-link op=list'))
    with store.atomic():
        if op == 'reject':
            with store.tables() as tables:
                for link in chosen:
                    key = _where_link(code.layer_id, (link.kind, link.target, link.path, link.qn))
                    if link.state == PROPOSED:
                        tables.delete('code_links', key)
                    else:
                        tables.update('code_links', key, {'proposal': None})
            return {'rejected': len(chosen), 'symbols': [link.name for link in chosen[:8]]}
        gone = [link for link in chosen if link.key not in code.symbols]
        if gone:
            raise Stop(f'{gone[0].qn} is no longer in the code, so its proposal cannot be accepted.',
                       ctx.calls(f'metaform map code-link op=reject id={gone[0].id}'))
        groups: dict[tuple[str, str, str | None, str], list[Link]] = {}
        for link in chosen:
            state = str((link.proposal or {}).get('state') or LINKED)
            groups.setdefault((link.kind, link.target, link.provider_id, state), []).append(link)
        decided: list[dict[str, Any]] = []
        for (kind, target, provider_id, state), links in groups.items():
            whys = list(dict.fromkeys(str((link.proposal or {}).get('why') or '').strip() for link in links))
            why = str(ctx.nouns.get('why') or '').strip() or '; '.join(one for one in whys if one)[:600]
            if not why:
                why = _why(ctx, op)
            bys = list(dict.fromkeys(str((link.proposal or {}).get('by') or link.by) for link in links))
            address = links[0].numbered_at or ''
            rows = [code.symbols[link.key] for link in links]
            decided.append({'node': links[0].place, **_decision(
                store, code, Node.of(kind, target), address, provider_id, list(zip(rows, links, strict=True)), state,
                ', '.join(bys), why, _title(ctx, rows, address, state))})
    return {'decided': decided}


# ------------------------------------------------------------------------------------------------ reads

def _calls(code: Code, keys: set[Key], limit: int) -> dict[str, Any]:
    """The calls into and out of a set of symbols, each with the Addresses at its other end, as trace_path's first
    hop gives them."""
    into = [edge for edge in code.edges if edge['kind'] == 'CALLS' and _target(edge) in keys
            and _source(edge) not in keys]
    out = [edge for edge in code.edges if edge['kind'] == 'CALLS' and _source(edge) in keys
           and _target(edge) not in keys]

    def shown(edge: dict[str, Any], inward: bool) -> dict[str, Any]:
        other, mine = (_source(edge), _target(edge)) if inward else (_target(edge), _source(edge))
        return {'from' if inward else 'to': code.name_of(other), 'qn': other[1], 'address': code.at(other),
                'via': code.name_of(mine), 'at': f"{edge['path']}:{edge['line']}"}
    said: dict[str, Any] = {'calls_in': [shown(edge, True) for edge in into[:limit]],
                            'calls_out': [shown(edge, False) for edge in out[:limit]]}
    if len(into) > limit or len(out) > limit:
        said['more'] = {'calls_in': max(0, len(into) - limit), 'calls_out': max(0, len(out) - limit)}
    return said


def _stale(store: Store, layer_id: str, paths: Iterable[str]) -> list[str]:
    """The files whose bytes changed since the layer read them."""
    root = _root(store)
    found: list[str] = []
    with store.tables(write=False) as tables:
        for path in sorted(set(paths)):
            row = tables.get('code_files', {'layer_id': layer_id, 'path': path})
            if row is not None and row['hash'] != file_hash(root, path):
                found.append(path)
    return found


def _shown(store: Store, code: Code, link: Link) -> dict[str, Any]:
    """A link as code-context lists it: the symbol, how it came, its why and number when decided, its id, and the
    join it is held at."""
    row = _row(code, link.key)
    row.pop('address', None)
    row.pop('serves', None)
    if row.get('gone'):
        row.update(name=link.name, label=link.label)
    row['by'] = link.by
    if link.why:
        row['why'] = link.why
    item = _item_ref(store, link.item_id)
    if item:
        row['item'] = item
    row['id'] = link.id
    if link.kind == 'join':
        row['at'] = link.place
    return row


def _orphans(ctx: Context, links: Iterable[Link]) -> list[dict[str, Any]]:
    """Links whose symbol is gone, each with its id and the two calls that settle it."""
    return [{'id': link.id, 'node': link.place, 'symbol': link.name, 'qn': link.qn, 'file': link.path,
             'then': [ctx.calls(f'metaform map code-link op=move id={link.id} symbol=<qn> why="<why>"'),
                      ctx.calls(f'metaform map code-link op=remove id={link.id} why="<why>"')]} for link in links]


def code_context(ctx: Context) -> Any:
    """The code at an Address, as GitNexus's context gives a symbol's: its own symbols and files, those of the joins
    it provides for among them, the calls in and out with the Addresses at their other end, and apart from them the
    code serving it through the joins it receives; or, given a symbol or a file, its Addresses."""
    store = ctx.require_store()
    code = _code(ctx, store, edges=True)
    limit = int(ctx.nouns.get('limit') or 25)
    address = str(ctx.nouns.get('address') or '').strip()
    if ctx.nouns.get('symbol') or ctx.nouns.get('file'):
        return _of_code(ctx, store, code, limit)
    if not address:
        raise Stop('Name what to read: address=, symbol= or file=.', 'metaform map code-context address=<address>')
    provider: str | None = None
    if is_scoped(address):  # `<scope>@<layer>`, P165: the code layer's view of an Address or of a join
        found = resolve_scoped(store, address)
        if found.layer != code.name or found.address is None:
            raise Stop(f'{address} is not the code layer {code.name} at an Address.',
                       f'metaform map where address={address}')
        address, provider = found.address, found.provider
    return _context(ctx, store, code, address, provider, limit)


def scoped(ctx: Context, address: str, provider: str | None = None) -> dict[str, Any]:
    """The code layer at `<address>@<layer>`, or at the join `<address>:<provider>@<layer>`, P165, as code-context
    reads it: what map where gives for a scoped address in the code layer."""
    store = ctx.require_store()
    return _context(ctx, store, _code(ctx, store, edges=True), address, provider, int(ctx.nouns.get('limit') or 25))


def _context(ctx: Context, store: Store, code: Code, address: str, provider: str | None, limit: int) -> dict[str, Any]:
    """The code at an Address; with `provider`, at the join the Address receives from it: the code of that provider
    realizing the join's EF, linked at the join."""
    element = store.element(address)
    if element is None:
        from . import _missing  # pyright: ignore[reportPrivateUsage]  # shared within the map module
        raise _missing(store, address)
    if provider is not None:
        own = [link for link in code.links if link.kind == 'join' and link.receiver == address and provider in link.at]
        serving: list[Link] = []
    else:
        own = [link for link in code.links if address in link.at]
        serving = [link for link in code.links if link.kind == 'join' and link.receiver == address]
    linked = [link for link in own if link.state == LINKED and link.key in code.symbols]
    symbols = [_shown(store, code, link) for link in linked]
    keys = {link.key for link in linked}
    files: dict[str, int] = {}
    for path, _ in keys:
        files[path] = files.get(path, 0) + 1
    stale = set(_stale(store, code.layer_id, files))
    result: dict[str, Any] = {
        'address': address, **({'provider': provider} if provider else {}), 'layer': code.name,
        'scope': f'{address}:{provider}@{code.name}' if provider else f'{address}@{code.name}',
        'symbols': symbols[:limit],
        'files': [{'file': path, 'symbols': count, **({'stale': True} if path in stale else {})}
                  for path, count in sorted(files.items())],
        **_calls(code, keys, limit)}
    if len(symbols) > limit:
        result['more_symbols'] = len(symbols) - limit
    groups: dict[str, list[str]] = {}
    for link in serving:
        if link.state == LINKED and link.key in code.symbols:
            groups.setdefault(', '.join(link.at), []).append(code.name_of(link.key))
    if groups:
        result['serving'] = [{'provider': provider, 'symbols': names[:limit], 'count': len(names)}
                             for provider, names in sorted(groups.items())]
    if stale:
        result['stale'] = len(stale)
        result['notices'] = [(f'{_plural(len(stale), "file", "files")} changed since the layer read them; the lines '
                              'shown may have moved until map code-import reads them again.')]
    proposed = [{'id': link.id, 'symbol': _row(code, link.key), 'proposes': (link.proposal or {}).get('state'),
                 'why': (link.proposal or {}).get('why')} for link in (*own, *serving) if link.proposal]
    if proposed:
        result['proposed'] = proposed[:limit]
    lost = [link for link in code.orphaned() if link in own or link in serving]
    if lost:
        result['orphaned'] = _orphans(ctx, lost[:limit])
    if not symbols and not groups:
        link = f'node={address}' + (f' provider={provider}' if provider else '')
        result['next'] = [ctx.calls(f'metaform map code-search query=<words of {address}>'),
                          ctx.calls(f'metaform map code-link op=add {link} symbol=<qn> why="<why>"')]
    return result


def _cited_by(store: Store, path: str) -> list[str]:
    """The Addresses whose sources cite a file by its path."""
    return sorted({citation.address for citation in store.citing('path', path, limit=0).results
                   if citation.address and citation.layer == 'sources'})


def _of_code(ctx: Context, store: Store, code: Code, limit: int) -> Any:
    """The Addresses whose own code a symbol, or the symbols a file declares, is, and those it serves through a
    join, with the Addresses whose sources cite its file; a symbol with its calls in and out."""
    path = str(ctx.nouns.get('file') or '').strip()
    if path and not ctx.nouns.get('symbol'):
        rows = [_row(code, key) for key in code.symbols if key[0] == path]
        result: dict[str, Any] = {'file': path, 'address': sorted({one for row in rows for one in row['address']})}
        serves = sorted({one for row in rows for one in row.get('serves', [])})
        if serves:
            result['serves'] = serves
        return {**result, 'cited_by': _cited_by(store, path), 'symbols': rows[:limit],
                **({'stale': True} if _stale(store, code.layer_id, [path]) else {})}
    key = _symbols(ctx, code)[0]
    row = _row(code, key, degree=_degrees(code))
    return {**row, 'cited_by': _cited_by(store, key[0]), **_calls(code, {key}, limit)}


def code_search(ctx: Context) -> Any:
    """Symbols by words, a name or qn pattern, a file pattern or a label, as codebase-memory's search_graph finds
    them, each with the Addresses it is the code of; paged by limit and the cursor next gives."""
    store = ctx.require_store()
    code = _code(ctx, store, edges=True)
    words = [word.lower() for word in str(ctx.nouns.get('query') or '').split()]
    patterns: list[tuple[str, re.Pattern[str]]] = []
    for key in ('name_pattern', 'qn_pattern'):
        given = ctx.nouns.get(key)
        if given:
            try:
                patterns.append((key, re.compile(str(given))))
            except re.error as error:
                raise Stop(f'{key} is not a regular expression: {error}.', 'metaform help map code-search') from None
    files, label = ctx.nouns.get('file_pattern'), ctx.nouns.get('label')
    found: list[tuple[int, Key]] = []
    for key, row in code.symbols.items():
        if label and row['label'] != label:
            continue
        if files and not fnmatch.fnmatchcase(key[0], str(files)):
            continue
        if any(not pattern.search(row['name'] if which == 'name_pattern' else key[1]) for which, pattern in patterns):
            continue
        score = 0
        if words:
            name, text = row['name'].lower(), f'{key[1]} {key[0]}'.lower()
            if not all(word in text for word in words):
                continue
            score = -sum(3 if word == name else 2 if word in name else 1 for word in words)
        found.append((score, key))
    found.sort(key=lambda one: (one[0], one[1][0], code.symbols[one[1]]['start_line']))
    start = int(ctx.nouns.get('after') or 0)
    limit = int(ctx.nouns.get('limit') or 50)
    page = found[start:start + limit] if limit else found[start:]
    degree = _degrees(code)
    result: dict[str, Any] = {'total': len(found), 'results': [_row(code, key, degree=degree) for _, key in page]}
    if limit and start + limit < len(found):
        result['next'] = str(start + limit)
    return result


def _start(ctx: Context, store: Store, code: Code, given: str) -> tuple[set[Key], str, set[str]]:
    """The symbols a trace starts or ends at, with the Addresses they are the code of: those of an Address, or one
    symbol."""
    if store.element(given) is not None:
        keys = {link.key for link in code.linked() if given in link.at}
        if not keys:
            raise Stop(f'No code is linked at {given}.', ctx.calls(f'metaform map code-context address={given}'))
        return keys, given, {given}
    key = _resolve(code, given)[0]
    return {key}, key[1], set(code.at(key))


def _edge_types(ctx: Context, store: Store, code: Code) -> tuple[set[str], list[str]]:
    """The edges a trace follows, CALLS unless named, with a notice for each named that the layer does not hold."""
    given = ctx.nouns.get('edge_types')
    if not given:
        return {'CALLS'}, []
    listed = cast(list[Any], given) if isinstance(given, list) else str(given).split(',')
    named = [str(one).strip() for one in listed]
    unknown = [one for one in named if one not in EDGE_TYPES]
    if unknown:
        raise Stop(f'{unknown[0]!r} is not an edge type here: {", ".join(EDGE_TYPES)}.', 'metaform help map code-trace')
    held = {edge['kind'] for edge in code.edges}
    absent = [one for one in named if one not in held]
    with store.tables(write=False) as tables:
        providers = sorted({str(row['provider']) for row in tables.rows('code_files', {'layer_id': code.layer_id},
                                                                         limit=0).results if row['provider']})
    notices = [f'The code layer holds no {one} edges: {", ".join(providers) or "its provider"} gave none.'
               for one in absent]
    return set(named), notices


def _is_test(key: Key) -> bool:
    return bool(TESTS.search(key[0]))


def code_trace(ctx: Context) -> Any:
    """A call path traced between Addresses, as trace_path takes it: from an Address or a symbol to another, the
    shortest path; with no `to`, the Addresses reached within `depth` calls, each at the first hop that reaches it,
    both ways by default. Test code is left out unless include_tests."""
    store = ctx.require_store()
    code = _code(ctx, store, edges=True)
    direction = str(ctx.nouns.get('direction') or 'both')
    if direction not in ('outbound', 'inbound', 'both'):
        raise Stop(f'{direction!r} is not a direction: outbound, inbound or both.', 'metaform help map code-trace')
    depth = max(1, min(int(ctx.nouns.get('depth') or 3), 15))
    types, notices = _edge_types(ctx, store, code)
    tests = bool(ctx.nouns.get('include_tests'))
    starts, named, start_at = _start(ctx, store, code, str(ctx.nouns['from']))
    ahead: dict[Key, set[Key]] = {}
    for edge in code.edges:
        source, target = _source(edge), _target(edge)
        if edge['kind'] not in types or (not tests and (_is_test(source) or _is_test(target))):
            continue
        if direction in ('outbound', 'both'):
            ahead.setdefault(source, set()).add(target)
        if direction in ('inbound', 'both'):
            ahead.setdefault(target, set()).add(source)
    said: dict[str, Any] = {'notices': notices} if notices else {}
    to = ctx.nouns.get('to')
    if to:
        ends, _, _ = _start(ctx, store, code, str(to))
        came: dict[Key, Key | None] = dict.fromkeys(starts)
        queue = deque((key, 0) for key in sorted(starts))
        while queue:
            key, hop = queue.popleft()
            if key in ends and key not in starts:
                path = [key]
                while came[path[-1]] is not None:
                    path.append(cast(Key, came[path[-1]]))
                path.reverse()
                hops = [_row(code, one) for one in path]
                addresses: list[str] = []
                for row in hops:
                    for address in row.get('address') or ['(no address)']:
                        if not addresses or addresses[-1] != address:
                            addresses.append(address)
                return {'from': named, 'to': to, 'found': True, 'addresses': addresses, 'path': hops, **said}
            if hop >= max(depth, 6):
                continue
            for other in sorted(ahead.get(key, ())):
                if other not in came:
                    came[other] = key
                    queue.append((other, hop + 1))
        return {'from': named, 'to': to, 'found': False, **said,
                'next': [ctx.calls(f'metaform map code-trace from={named} to={to} depth={min(depth + 3, 15)}')]}
    seen = set(starts)
    frontier = set(starts)
    listed = set(start_at)
    hops: list[dict[str, Any]] = []
    for hop in range(1, depth + 1):
        reached: dict[str, list[str]] = {}
        unclaimed = within = 0
        nxt: set[Key] = set()
        for key in sorted(frontier):
            for other in sorted(ahead.get(key, ())):
                if other in seen:
                    continue
                nxt.add(other)
                there = code.at(other)
                if not there:
                    unclaimed += 1
                    continue
                if set(there) & set(code.at(key)):
                    within += 1  # a call inside one Address
                for address in there:
                    if address not in listed:
                        reached.setdefault(address, []).append(f'{code.name_of(key)} -> {code.name_of(other)}')
        seen |= nxt
        frontier = nxt
        if not nxt:
            break
        listed |= set(reached)
        hops.append({'hop': hop, 'addresses': [{'address': address, 'via': via[:5], 'calls': len(via)}
                                               for address, via in sorted(reached.items())],
                     **({'within': within} if within else {}), **({'unclaimed': unclaimed} if unclaimed else {})})
    return {'from': named, 'direction': direction, 'depth': depth, 'hops': hops, **said}


def _skill_on(ctx: Context) -> bool:
    try:
        return any(module.id == 'workflow' for module in surface(ctx.folder))
    except Exception:  # noqa: BLE001  a surface that cannot be read offers no skill
        return False


def code_gaps(ctx: Context) -> Any:
    """The gaps between the map and the code: code without a purpose, the symbols no Address claims, by file, test
    code counted apart unless include_tests; purpose without code, the Addresses of the code trunk, or whose sources
    cite code, that no symbol is the code of; the links the sources pass made that no one has reviewed; and decided
    links whose symbol is gone. Paged as every page is: the cursor under next, passed back as after."""
    store = ctx.require_store()
    code = _code(ctx, store)
    side = str(ctx.nouns.get('side') or 'both')
    if side not in ('code', 'purpose', 'both'):
        raise Stop(f'{side!r} is not a side: code, purpose or both.', 'metaform map code-gaps side=both')
    limit = int(ctx.nouns.get('limit') or 25)
    start = int(ctx.nouns.get('after') or 0)
    tests = bool(ctx.nouns.get('include_tests'))
    more = False

    def page(listed: list[Any]) -> list[Any]:
        nonlocal more
        more = more or len(listed) > start + limit
        return listed[start:start + limit]
    result: dict[str, Any] = {'layer': code.name}
    claimed = {link.key for link in code.links if link.state in (LINKED, PROPOSED)}
    if side in ('code', 'both'):
        files: dict[str, list[str]] = {}
        in_tests = 0
        for key, row in code.symbols.items():
            if key in claimed:
                continue
            if not tests and TESTS.search(key[0]):
                in_tests += 1
                continue
            files.setdefault(key[0], []).append(row['name'])
        ordered = sorted(files.items(), key=lambda one: (-len(one[1]), one[0]))
        result['code_without_purpose'] = {
            'symbols': sum(len(names) for names in files.values()), 'of': len(code.symbols), 'files': len(files),
            **({'tests': in_tests} if in_tests else {}),
            'by_file': page([{'file': path, 'count': len(names), 'symbols': names[:8]} for path, names in ordered])}
    if side in ('purpose', 'both'):
        graph = store.graph(limit=0)
        served = {address for link in code.linked() for address in link.at}
        # A cite at an element is its own; one at a join is its providers', whose code realizes the join's EF.
        holders = {one.element.id: [one.element.address] for one in graph.elements}
        holders.update((join.id, [held.address for held in join.elements if held.address]) for join in graph.joins)
        cites: dict[str, list[str]] = {}
        for node, path, _ in _cites(store):
            for address in holders.get(node.id, []):
                cites.setdefault(address, []).append(path)
        serving: dict[str, int] = {}  # a ghost served through the joins it receives says so
        for link in code.linked():
            if link.kind == 'join' and link.receiver:
                serving[link.receiver] = serving.get(link.receiver, 0) + 1
        ghosts = [{'address': one.element.address,
                   **({'cites': cites[one.element.address][:3]} if cites.get(one.element.address) else {}),
                   **({'served_by': serving[one.element.address]} if serving.get(one.element.address) else {})}
                  for one in graph.elements if one.element.address not in served
                  and (one.element.address.split('.', 1)[0] == 'code' or cites.get(one.element.address))]
        result['purpose_without_code'] = {'addresses': len(ghosts), 'ghosts': page(ghosts)}
        unreviewed: dict[str, dict[str, int]] = {}  # by the Address whose own code they are, and by file
        for link in code.linked():
            if link.by == BY_SOURCES and not link.item_id and not link.proposal:
                for address in link.at:
                    by_file = unreviewed.setdefault(address, {})
                    by_file[link.path] = by_file.get(link.path, 0) + 1
        if unreviewed:
            result['unreviewed'] = {'links': sum(sum(one.values()) for one in unreviewed.values()), 'addresses': page(
                [{'address': address, 'links': sum(by_file.values()),
                  'files': [{'file': path, 'links': count} for path, count in sorted(by_file.items())][:8]}
                 for address, by_file in sorted(unreviewed.items())])}
    lost = code.orphaned()
    if lost:
        result['orphaned'] = {'links': len(lost), 'at': _orphans(ctx, lost[:limit])}
    if more:
        result['next'] = str(start + limit)
    result['then'] = [ctx.calls('metaform workflow skill code_links') if _skill_on(ctx) else
                      ctx.calls('metaform map code-link op=propose node=<address> file=<path> why="<why>"'),
                      ctx.calls('metaform map code-link op=add node=<address> symbol=<qn> why="<why>"')]
    return result


# ------------------------------------------------------------------------------------------------ changes

HUNK = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')


def _git(root: Path, *args: str) -> str:
    git = shutil.which('git')
    if git is None or not (root / '.git').exists():
        raise Stop('The project is not a git repository here, so its changes cannot be read.',
                   'metaform map code-context file=<path>')
    done = subprocess.run([git, *args], cwd=root, capture_output=True, check=False)
    if done.returncode != 0:
        raise Stop(f'git {args[0]} failed: {done.stderr.decode("utf-8", "replace").strip()[:300]}',
                   'metaform map code-changes since=HEAD')
    return done.stdout.decode('utf-8', 'replace')


def _hunks(root: Path, since: str) -> dict[str, tuple[list[tuple[int, int]], list[tuple[int, int]]]]:
    """Each changed file with the line ranges changed, before and after, from git diff against `since`; a file git
    does not track yet changed whole."""
    found: dict[str, tuple[list[tuple[int, int]], list[tuple[int, int]]]] = {}
    old_path = new_path = ''
    for line in _git(root, 'diff', '--no-color', '--no-ext-diff', '--unified=0', since, '--').splitlines():
        if line.startswith('--- '):
            old_path = line[4:].removeprefix('a/') if line[4:] != '/dev/null' else ''
        elif line.startswith('+++ '):
            new_path = line[4:].removeprefix('b/') if line[4:] != '/dev/null' else ''
        elif line.startswith('@@'):
            match = HUNK.match(line)
            if match is None:
                continue
            path = new_path or old_path
            before, after = found.setdefault(path, ([], []))
            first, count = int(match[1]), int(match[2] if match[2] is not None else 1)
            before.append((max(first, 1), max(first, 1) + max(count, 1) - 1))
            first, count = int(match[3]), int(match[4] if match[4] is not None else 1)
            after.append((max(first, 1), max(first, 1) + max(count, 1) - 1))
    for path in _git(root, 'ls-files', '-o', '--exclude-standard', '-z').split('\0'):
        if path:
            found[path] = ([], [(1, 1 << 30)])
    return found


def _members(code: Code) -> dict[Key, list[Key]]:
    """Each type's members, the symbols below it in its file, which a type that inherits it inherits."""
    by_path: dict[str, list[Key]] = {}
    for key in code.symbols:
        by_path.setdefault(key[0], []).append(key)
    found: dict[Key, list[Key]] = {}
    for key, row in code.symbols.items():
        if row['label'] in TYPES:
            found[key] = [one for one in by_path[key[0]] if one[1].startswith(key[1] + '.')]
    return found


def code_changes(ctx: Context) -> Any:
    """The Addresses a change touches, as codebase-memory's detect_changes and GitNexus's impact give its symbols:
    git's changed lines since a ref, or since the merge base with a branch, the innermost symbols they fall in, the
    Addresses those are the code of and those they serve, within depth the Addresses of their callers and of the types
    and methods that inherit or override them, and the tests that reach them."""
    store = ctx.require_store()
    code = _code(ctx, store, edges=True)
    root = _root(store)
    base = str(ctx.nouns.get('base') or '').strip()
    since = str(ctx.nouns.get('since') or 'HEAD').strip()
    for ref in (since, base):
        if ref.startswith('-'):
            raise Stop(f'{ref!r} is not a git ref.', 'metaform map code-changes since=HEAD')
    merge_base = _git(root, 'merge-base', base, 'HEAD').strip() if base else None
    given = ctx.nouns.get('depth')
    depth = max(0, min(2 if given is None else int(given), 5))
    direction = str(ctx.nouns.get('direction') or 'inbound')
    if direction not in ('inbound', 'outbound', 'both'):
        raise Stop(f'{direction!r} is not a direction: inbound, outbound or both.', 'metaform help map code-changes')
    tests = bool(ctx.nouns.get('include_tests'))
    limit = int(ctx.nouns.get('limit') or 50)
    skip = _skip(ctx, root)
    by_file: dict[str, list[Key]] = {}
    for key in code.symbols:
        by_file.setdefault(key[0], []).append(key)
    with store.tables(write=False) as tables:
        hashes = {row['path']: row['hash'] for row in tables.rows('code_files', {'layer_id': code.layer_id},
                                                                  limit=0).results}
    changed: dict[str, list[Key]] = {}
    unread: list[str] = []
    kinds = {Path(path).suffix for path in hashes}  # a file of a kind the layer holds is code it has not read yet
    for path, (before, after) in sorted(_hunks(root, merge_base or since).items()):
        if skip(path):
            continue
        if path not in hashes:
            if Path(path).suffix in kinds and (root / path).is_file():
                unread.append(path)
            continue
        # The layer's lines are the file as it was read: the lines after the change when it was read since, before
        # it otherwise.
        ranges = after if hashes[path] == file_hash(root, path) else before
        rows = [(key, code.symbols[key]) for key in by_file.get(path, [])]
        hit: set[Key] = set()
        for first, last in ranges:
            over = [(key, row) for key, row in rows if row['start_line'] <= last and first <= row['end_line']]
            hit |= {key for key, row in over if not any(
                other is not row and row['start_line'] <= other['start_line'] and other['end_line'] <= row['end_line']
                and (other['start_line'], other['end_line']) != (row['start_line'], row['end_line'])
                for _, other in over)}
        changed[path] = sorted(hit, key=lambda key: code.symbols[key]['start_line'])
    seeds = {key for keys in changed.values() for key in keys}
    addresses: dict[str, dict[str, Any]] = {}

    def credit(address: str, how: str, name: str, hop: int) -> None:
        held = addresses.setdefault(address, {'address': address, 'how': how, 'hop': hop, 'symbols': []})
        if name not in held['symbols']:
            held['symbols'].append(name)
    unclaimed = 0
    for key in sorted(seeds):
        at, serves = code.at(key), code.serves(key)
        unclaimed += not at and not serves
        for address in at:
            credit(address, 'changed', code.name_of(key), 0)
        for address in serves:
            if address not in addresses:
                credit(address, 'served', code.name_of(key), 0)
    # Inbound: a caller, or a type or method inheriting or overriding what changed, with every member of a changed
    # type's descendants; outbound: what the changed code calls.
    ahead: dict[Key, set[tuple[Key, str]]] = {}
    members = _members(code)
    reaching: dict[Key, list[str]] = {}  # a changed symbol's tests
    for edge in code.edges:
        source, target, kind = _source(edge), _target(edge), edge['kind']
        if kind == 'TESTS' or (kind == 'CALLS' and TESTS.search(source[0])):
            if target in seeds:
                reaching.setdefault(target, []).append(source[0])
            if kind == 'TESTS':
                continue
        if kind == 'CALLS':
            if direction in ('inbound', 'both'):
                ahead.setdefault(target, set()).add((source, 'caller'))
            if direction in ('outbound', 'both'):
                ahead.setdefault(source, set()).add((target, 'callee'))
        elif kind in ('INHERITS', 'IMPLEMENTS', 'OVERRIDE') and direction in ('inbound', 'both'):
            ahead.setdefault(target, set()).add((source, 'inherits'))
            for member in members.get(target, []):
                ahead.setdefault(member, set()).add((source, 'inherits'))
    seen, frontier = set(seeds), set(seeds)
    for hop in range(1, depth + 1):
        nxt: dict[Key, str] = {}
        for key in frontier:
            for other, how in ahead.get(key, ()):
                if other not in seen and (tests or not TESTS.search(other[0])):
                    nxt.setdefault(other, how)
        for key in sorted(nxt):
            for address in code.at(key):
                if address not in addresses or addresses[address]['hop'] == hop:
                    credit(address, nxt[key], code.name_of(key), hop)
        seen |= set(nxt)
        frontier = set(nxt)
    ordered = sorted(addresses.values(), key=lambda one: (one['hop'], one['how'] != 'changed', one['address']))
    for one in ordered:
        one['symbols'] = one['symbols'][:8]
    result: dict[str, Any] = {
        'since': since, **({'base': base, 'merge_base': merge_base} if merge_base else {}),
        'changed_files': [{'file': path, 'symbols': [code.name_of(key) for key in keys][:limit]}
                          for path, keys in changed.items()][:limit],
        'changed_symbols': len(seeds), 'addresses': ordered[:limit]}
    if len(ordered) > limit:
        result['more_addresses'] = len(ordered) - limit
    if reaching:
        result['tests'] = [{'symbol': code.name_of(key), 'files': sorted(set(files))[:8]}
                           for key, files in sorted(reaching.items())][:limit]
    if unclaimed:
        result['unclaimed'] = unclaimed
    if unread:
        result['unread'] = unread[:limit]
        result['next'] = [ctx.calls('metaform map code-import')]
    return result


# ------------------------------------------------------------------------------------------------ the brief

@dataclass
class _Counts:
    symbols: int = 0
    files: int = 0
    into: int = 0
    out: int = 0
    serving: int = 0
    stale: int = 0
    orphaned: int = 0


def _count(store: Store, layer_id: str, own: Sequence[tuple[str, str]], serving: Sequence[tuple[str, str]]) -> _Counts:
    """The code at a node and serving it, read from the code tables by node and by file, never symbol by symbol: the
    links of each node, the symbols each of their files still declares, the calls starting in and reaching those
    files, and the decided links whose symbol is gone."""
    root = _root(store)
    counts = _Counts()
    with store.tables(write=False) as tables:
        def rows(nodes: Sequence[tuple[str, str]]) -> list[dict[str, Any]]:
            return [row for kind, ident in nodes for row in tables.rows(
                'code_links', {'layer_id': layer_id, 'node_kind': kind, 'node_id': ident}, limit=0).results]
        mine = [row for row in rows(own) if row['state'] in (LINKED, PROPOSED)]
        theirs = [row for row in rows(serving) if row['state'] == LINKED]
        present: set[Key] = set()
        for path in {row['path'] for row in (*mine, *theirs) if row['path']}:
            present |= {(path, row['qn']) for row in tables.rows('code_symbols', {'layer_id': layer_id, 'path': path},
                                                                 limit=0).results}
        keys = {(row['path'], row['qn']) for row in mine if row['state'] == LINKED} & present
        counts.orphaned = sum(1 for row in mine if (row['path'], row['qn']) not in present
                              and (row['item_id'] or row['proposal'] or row['by'] != BY_SOURCES))
        files = {path for path, _ in keys}
        for path in files:
            counts.out += sum(1 for row in tables.rows('code_edges', {'layer_id': layer_id, 'path': path},
                                                       limit=0).results
                              if row['kind'] == 'CALLS' and (path, row['source']) in keys
                              and (row['target_path'], row['target']) not in keys)
            counts.into += sum(1 for row in tables.rows('code_edges', {'layer_id': layer_id, 'target_path': path},
                                                        limit=0).results
                               if row['kind'] == 'CALLS' and (path, row['target']) in keys
                               and (row['path'], row['source']) not in keys)
            held = tables.get('code_files', {'layer_id': layer_id, 'path': path})
            counts.stale += held is not None and held['hash'] != file_hash(root, path)
        counts.symbols, counts.files = len(keys), len(files)
        counts.serving = len({(row['path'], row['qn']) for row in theirs} & present - keys)
    return counts


def _line(ctx: Context, counts: _Counts, read: str) -> str | None:
    said = _prompt('brief_code', symbols=str(counts.symbols), files=str(counts.files), into=str(counts.into),
                   out=str(counts.out),
                   serving=_prompt('brief_code_serving', symbols=str(counts.serving)) if counts.serving else '',
                   stale=_prompt('brief_code_stale', files=str(counts.stale)) if counts.stale else '',
                   orphaned=_prompt('brief_code_orphaned', links=str(counts.orphaned)) if counts.orphaned else '',
                   read=read)
    return ctx.calls(said) or None


def _holds_code(store: Store, layer_id: str, found: Where) -> bool:
    """Whether a node is one the code should serve: under the code trunk, or citing a file the code layer holds."""
    assert found.element is not None
    if found.element.address.split('.', 1)[0] == 'code':
        return True
    root = _root(store)
    groups = [*found.layers, *(group for _, held in found.join_layers for group in held)]
    paths = {_cited(ref.value, root)[0] for group in groups if group.layer == 'sources' for item in group.items
             for ref in item.refs if ref.key == 'path'}
    with store.tables(write=False) as tables:
        return any(tables.get('code_files', {'layer_id': layer_id, 'path': path}) is not None for path in paths)


def brief(ctx: Context, found: Where) -> str | None:
    """The one line a node's brief gives its code: its own symbols, those of the joins it provides for among them, in
    how many files, the calls in and out, the code serving it through the joins it receives, the files changed since
    the layer read them, the decided links whose symbol is gone, and the call that reads them; or, at a node the code
    should serve and none is linked, the call that links it; or, before the code is read, at a node whose sources cite
    files and while a provider is there, the call that reads it, so the import is found where the code is worked on."""
    if found.element is None or ctx.store is None:
        return None
    layer_id = _layer_id(ctx.store, _layer(ctx))
    address = found.element.address
    if layer_id is None:  # at a node whose sources cite code, the call that reads the code, while a provider is there
        groups = [*found.layers, *(group for _, held in found.join_layers for group in held)]
        if not any(ref.key == 'path' for group in groups if group.layer == 'sources' for item in group.items
                   for ref in item.refs):
            return None
        try:
            ready = _available(ctx, _root(ctx.store))
        except (StoreError, OSError):
            return None
        return ctx.calls(_prompt('code_start', read='metaform map code-import')) or None if ready else None
    counts = _count(ctx.store, layer_id, [('element', found.element.id), *(('join', join.id) for join in found.provides)],
                    [('join', join.id) for join in found.receives])
    if counts.symbols or counts.serving or counts.orphaned:
        return _line(ctx, counts, f'metaform map code-context address={address}')
    if not _holds_code(ctx.store, layer_id, found):
        return None
    return ctx.calls(_prompt('brief_code_none', read=f'metaform map code-link op=add node={address}')) or None


def node_line(ctx: Context, node: Node) -> str | None:
    """The code layer's line in a read of one node, map node: what is linked at it, counted, with the call that reads
    it, in place of the layer's items."""
    store = ctx.store
    if store is None:
        return None
    layer_id = _layer_id(store, _layer(ctx))
    if layer_id is None:
        return None
    if node.kind == 'element':
        element = store.element(node.id, raw=True)
        if element is None:
            return None
        provides = store.joins(element.id, 'provider', raw=True, limit=0).results
        receives = store.joins(element.id, raw=True, limit=0).results
        counts = _count(store, layer_id, [('element', element.id), *(('join', join.id) for join in provides)],
                        [('join', join.id) for join in receives])
        read = element.address
    else:
        counts = _count(store, layer_id, [('join', node.id)], [])
        ends = store.join_ends(node.id)
        read = ends[1] if ends else ''
    if not counts.symbols and not counts.serving and not counts.orphaned:
        return None
    return _line(ctx, counts, f'metaform map code-context address={read}')


def start_line(ctx: Context) -> str | None:
    """The line the map's entry gives while the code is not read into its layer and a provider is there to read it:
    the call that reads it."""
    store = ctx.store
    if store is None or _layer_id(store, _layer(ctx)) is not None:
        return None
    try:
        if 'code' not in store.children('', limit=0).results or not _available(ctx, _root(store)):
            return None
    except (StoreError, OSError):
        return None
    return ctx.calls(_prompt('code_start', read='metaform map code-import')) or None


# ------------------------------------------------------------------------------------------------ the verbs

def _noun(name: str, help: str, kind: Any = 'str', schema: dict[str, Any] | None = None) -> Noun:
    return Noun(name, help, kind=kind, required=False, schema=schema)


OPS = ('list', 'add', 'remove', 'move', 'propose', 'accept', 'reject')
LIMIT = _noun('limit', 'How many to show; the rest are counted.', 'int')
TESTS_NOUN = _noun('include_tests', 'true follows test code too; left out by default.', 'bool')
DIRECTIONS = {'type': 'string', 'enum': ['outbound', 'inbound', 'both']}
VERBS = (
    Verb('code-import', code_import, "Read the project's code into the code layer, symbols with their calls, uses, "
                                     'bases and imports, from SCIP, a code-graph MCP server or tree-sitter, and link '
                                     'each file the sources cite to its node.',
         nouns=(_noun('from', 'scip, mcp or tree-sitter; the setting code_provider when left out.',
                      schema={'type': 'string', 'enum': PROVIDERS[1:]}),
                _noun('index', 'The SCIP index file, relative to the project; the setting code_index when left out.'),
                _noun('full', 'true reads every file again, changed or not.', 'bool')),
         details='The code is a layer, named code: a CEL over the map that is taken off '
                 'with map knowledge op=discard like any other, its index with it. The base never changes. Files under '
                 '.metaform/ignore.txt and the setting code_ignore are never read. A file is read again when its stamp '
                 'at the provider changes; one whose bytes changed while its stamp did not is said to be stale, and '
                 'kept as the index has it. Each cited file is linked at the node citing it; a cited folder is left to '
                 'agents. A decided link whose symbol is gone is carried only to a new symbol with the same name below '
                 'its module, in the same file or in the file git reports it renamed to, and listed under carried; '
                 'any other is orphaned, for code-link op=move or op=remove by its id.',
         examples=(('metaform map code-import from=scip', 'Read index.scip into the code layer.'),
                   ('metaform map code-import from=mcp',
                    'Read the code graph codebase-memory-mcp holds for this folder.')),
         open_world=True),
    Verb('code-link', code_link, 'Link code symbols to the Address whose purpose they provide for, with a why, as '
                                 'your work shows it; or unlink, move, propose, accept or reject.',
         nouns=(_noun('op', 'add links, remove unlinks, move re-points a link by its id; propose writes proposals, '
                            'accept and reject decide them; list, the default, shows those waiting.',
                      schema={'type': 'string', 'enum': list(OPS)}),
                _noun('node', 'The Address whose purpose the code provides for, an element.'),
                _noun('provider', 'With node: the join that element receives from this provider; the code is that '
                                  "provider's and realizes the join's EF."),
                _noun('symbol', 'The symbol: its qn, or a name only one symbol has.'),
                _noun('file', 'Every symbol the file declares; with symbol, the file it is in.'),
                _noun('why', 'Required to add, remove, move and propose: one short line on how the code serves the '
                             'purpose, or why it does not.'),
                _noun('unlink', 'propose: true proposes taking the link off.', 'bool'),
                _noun('title', 'A short title; <symbol> provides for <node> when left out.'),
                _noun('id', 'remove, move, accept, reject: the link, by the id code-context, code-gaps or op=list '
                            'gives; accept and reject also take node=, every proposal there.'),
                _noun('by', 'Who links it; the client when left out.')),
         details='The symbol is the PE and the node the RE: a link at an element is that element\'s own code; a link '
                 'at a join realizes its EF, the named provider\'s code serving the receiver. Each add, remove, move '
                 'or accept is one decision, however many symbols it names: one item of the code layer at the node, '
                 'numbered at the address as <address>#<n> with its title and why. The sources pass never links again '
                 'what was unlinked.',
         examples=(('metaform map code-link op=add node=code.timer.kitchen symbol=tick why="counts the time down"',
                    'Link the tick method to the kitchen timer.'),
                   (('metaform map code-link op=remove node=code.timer.kitchen provider=code.alarm.audible '
                     'symbol=ring why="the display rings now"'),
                    'Unlink ring from the join the timer receives from the alarm.'),
                   ('metaform map code-link op=accept node=code.display.digit',
                    'Accept every proposal waiting at the display, as one decision.'))),
    Verb('code-context', code_context, 'Read the code at an Address: its symbols and files, the calls in and out with '
                                       'the Address at the other end, and the code serving it; or the Addresses of a '
                                       'symbol or a file.',
         nouns=(_noun('address', 'An Address on the map.'), _noun('symbol', 'Instead: a symbol, its qn or name.'),
                _noun('file', 'Instead: a file, repository-relative; with symbol, the file it is in.'), LIMIT),
         effect='read'),
    Verb('code-search', code_search, 'Find code symbols by words, a name or qn pattern, a file pattern or a label, each '
                                     'with the Addresses it is the code of.',
         nouns=(_noun('query', 'Words the name, qn or file holds.'),
                _noun('name_pattern', 'A regular expression the name matches.'),
                _noun('qn_pattern', 'A regular expression the qn matches.'),
                _noun('file_pattern', 'A glob the file matches, such as src/**/*.py.'),
                _noun('label', 'Function, Method, Class and the other kinds.'), LIMIT,
                _noun('after', 'The cursor the previous page returned as next.')),
         effect='read'),
    Verb('code-trace', code_trace, 'Trace calls between Addresses: the shortest call path from one Address or symbol '
                                   'to another, or every Address reached within depth calls.',
         nouns=(Noun('from', 'An Address or a symbol.'), _noun('to', 'An Address or a symbol to reach.'),
                _noun('direction', 'both, the default, as trace_path; outbound follows the calls made, inbound the '
                                   'callers.', schema=DIRECTIONS),
                _noun('depth', 'How many calls to follow, 3 by default, at most 15.', 'int'),
                _noun('edge_types', 'The edges followed, CALLS by default; USAGE, INHERITS, IMPLEMENTS, OVERRIDE and '
                                    'TESTS where the provider gave them.', 'json',
                      schema={'type': 'array', 'items': {'type': 'string', 'enum': list(EDGE_TYPES)}}),
                TESTS_NOUN),
         effect='read'),
    Verb('code-changes', code_changes, 'Find the Addresses a change touches: the symbols git\'s changed lines fall in, '
                                       'their Addresses, and the Addresses of their callers and subclasses.',
         nouns=(_noun('since', 'The git ref to compare the files with; HEAD, the default, reads the uncommitted '
                               'change.'),
                _noun('base', 'Instead of since: a branch, such as main; the change since the merge base with it, as '
                              "detect_changes's base_branch."),
                _noun('depth', 'How many calls away to follow, 2 by default as detect_changes; 0 reads the changed '
                               'code only.', 'int'),
                _noun('direction', 'inbound, the default, the callers and what inherits; outbound what the changed '
                                   'code calls; both.', schema=DIRECTIONS),
                TESTS_NOUN, LIMIT),
         details='The changed lines are read from git diff against the lines the code layer holds: the lines after the '
                 'change for a file read since, before it otherwise. The tests that reach a changed symbol are listed '
                 'under tests. A file the layer has not read is listed as unread, with map code-import to read it.',
         effect='read'),
    Verb('code-gaps', code_gaps, 'Find code without a purpose, the symbols no Address claims, and purpose without '
                                 'code, the Addresses no symbol serves.',
         nouns=(_noun('side', 'code, purpose or both, the default.',
                      schema={'type': 'string', 'enum': ['both', 'code', 'purpose']}), TESTS_NOUN, LIMIT,
                _noun('after', 'The cursor the previous page returned as next.')),
         effect='read'),
)
