"""Where the code layer's symbols, calls and imports come from: a SCIP index, a code-graph MCP server, or tree-sitter.

Metaform indexes no code itself. A provider is an established tool the project already has, and each one is read
through its own published interface, read-only:

- `scip`: a SCIP index file, `index.scip`, written by any SCIP indexer (scip-python, scip-typescript, rust-analyzer,
  scip-java and the rest). It is read as the protobuf message `scip.Index` of sourcegraph/scip's `scip.proto`; only
  the fields named below are read, by their field numbers, so no generated code is needed. A symbol is named by its
  SCIP descriptors joined with dots, `kitchen.timer.Timer.tick`, the SCIP symbol string itself kept beside it. A call
  is a reference to a method or function symbol inside the `enclosing_range` of a definition, any other reference
  there a use, USAGE; an import is an occurrence with the Import role; a `Relationship` with `is_implementation` is
  INHERITS or IMPLEMENTS from a type and OVERRIDE from a method.
- `mcp`: a code-graph MCP server reached as an MCP client with the official SDK, over stdio for a command or over
  Streamable HTTP for a URL. codebase-memory-mcp is read through its `list_projects` and `query_graph` tools and its
  graph schema: Function, Method, Class and the other declaration labels, with its CALLS, USAGE, INHERITS,
  IMPLEMENTS, OVERRIDE, TESTS and IMPORTS edges. Its qualified names carry the project name, which names the folder
  it was indexed from; that prefix is removed, so the same symbol has the same name on every machine.
- `tree-sitter`: a pass over the project's files with the py-tree-sitter bindings and the grammar packages installed,
  `tree_sitter_python` and the like, through each grammar's own tags query, the convention GitHub's code navigation
  and Aider's repository map use: `@definition.<kind>`, `@reference.call` and `@name` captures. A call is resolved
  only where its scope shows what it reaches, never by a name alone: a bare call to the file's own declarations or
  to a name the file imports; a call on self, cls or this to the enclosing class and the bases it names; a call on a
  module or class the file imports to that module's or class's declaration. A call on any other receiver, a list's
  append or a pattern's match, is left out. Imports and base classes are read for Python, from its grammar's nodes.

Each provider lists the files it holds with a stamp that changes when what it holds for the file changes, and reads
the symbols and edges of the files it is asked for, so an import reads only the files that changed.
"""
from __future__ import annotations

import fnmatch
import hashlib
import importlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
from collections.abc import Callable, Generator, Iterator, Sequence
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from metaform import home


@dataclass(frozen=True)
class Symbol:
    """One declaration: its qualified name, dotted the same way whichever provider read it, its short name, its label
    as codebase-memory's graph schema names declarations (Function, Method, Class and the rest), its file, its lines,
    1-based, and its identity in the provider's own form when that differs, a SCIP symbol string."""
    qn: str
    name: str
    label: str
    path: str
    start: int
    end: int
    symbol: str = ''


@dataclass(frozen=True)
class Edge:
    """One relation in the code, as codebase-memory's graph schema names them: `CALLS` from a symbol to a symbol it
    calls, `USAGE` to one it refers to otherwise, `INHERITS` and `IMPLEMENTS` from a type to its base, `OVERRIDE` from
    a method to the one it overrides, `TESTS` from a test to what it tests, `IMPORTS` from a file to a symbol; `path`
    is the file the source is in, `line` where, 1-based, and `target_path` the file the target is in when the provider
    knows it, which tells apart two symbols of one name."""
    source: str
    target: str
    kind: str
    path: str
    line: int = 0
    target_path: str = ''


EDGE_KINDS = ('CALLS', 'USAGE', 'INHERITS', 'IMPLEMENTS', 'OVERRIDE', 'TESTS', 'IMPORTS')


class Unavailable(Exception):
    """A provider that cannot be read here, with what would make it readable."""

    def __init__(self, message: str, step: str) -> None:
        super().__init__(message)
        self.message = message
        self.step = step


class Provider(Protocol):
    tool: str
    version: str
    notices: list[str]
    refresh: str  # what brings the provider's index up to date with the files, said when it is behind them
    by_name: bool  # whether calls are resolved here, so a changed file changes the calls of the files calling it
    unresolved: dict[str, set[str]]  # with by_name: per file read, the names its calls and imports did not find

    def listing(self) -> dict[str, str]:
        """Each file the provider holds, repository-relative with forward slashes, with its stamp."""
        ...

    def read(self, paths: Sequence[str], known: Sequence[Symbol] = ()) -> tuple[list[Symbol], list[Edge]]:
        """The symbols declared in these files and the edges that start in them; an edge to code the index does not
        hold, a library's, is left out by the import. `known` is what the layer holds of the other files, which a
        provider resolving calls by name resolves them against."""
        ...


# ------------------------------------------------------------------------------------------------ the ignore list

def ignored(patterns: Sequence[str]) -> Callable[[str], bool]:
    """Whether a repository-relative path falls under the project's ignore list, `.metaform/ignore.txt`, BASE-058,
    read with gitignore's common forms: `dir/` a folder anywhere, `/dir` from the root, a pattern without a slash a
    name anywhere, `*` and `**` wildcards. Negations are not read; they would only let more in."""
    compiled: list[Callable[[str], bool]] = []
    for raw in patterns:
        pattern = raw.strip().strip('"').strip("'")
        if not pattern or pattern.startswith('!'):
            continue
        folder = pattern.endswith('/')
        pattern = pattern.strip('/')
        if not pattern:
            continue
        rooted = raw.strip().startswith('/') or '/' in pattern

        def match(path: str, pattern: str = pattern, folder: bool = folder, rooted: bool = rooted) -> bool:
            parts = path.split('/')
            if rooted:
                depth = pattern.count('/') + 1
                heads = ['/'.join(parts[:index]) for index in range(depth, len(parts) + 1)]
                return any(fnmatch.fnmatchcase(head, pattern) and (not folder or head != path)
                           for head in heads) or fnmatch.fnmatchcase(path, pattern + '/**')
            names = parts[:-1] if folder else parts
            return any(fnmatch.fnmatchcase(name, pattern) for name in names)
        compiled.append(match)
    return lambda path: any(match(path) for match in compiled)


def project_files(folder: Path) -> list[str]:
    """The project's files as git lists them, tracked and untracked but not gitignored; without git, every file
    outside hidden folders, `node_modules` and virtual environments."""
    git = shutil.which('git')
    if git is not None and (folder / '.git').exists():
        done = subprocess.run([git, 'ls-files', '-co', '--exclude-standard', '-z'], cwd=folder, capture_output=True,
                              check=False)
        if done.returncode == 0:
            return sorted(path for path in done.stdout.decode('utf-8', 'replace').split('\0') if path)
    found: list[str] = []
    for path in folder.rglob('*'):
        relative = path.relative_to(folder)
        if path.is_file() and not any(part.startswith('.') or part in ('node_modules', 'venv', '__pycache__')
                                      for part in relative.parts[:-1]):
            found.append(relative.as_posix())
    return sorted(found)


def file_hash(folder: Path, path: str) -> str | None:
    """The sha256 of a file's bytes, or None when it is not there."""
    try:
        return hashlib.sha256((folder / path).read_bytes()).hexdigest()
    except OSError:
        return None


# ------------------------------------------------------------------------------------------------ SCIP

# SymbolInformation.Kind values from scip.proto, read as the labels codebase-memory's graph uses; a kind not listed,
# a proof assistant's or a grammar's, is read from the symbol's last descriptor instead.
_SCIP_LABELS = {
    'Class': (7, 28, 62, 75, 84, 85),  # Class, Message, Contract, SingletonClass, Extension, Mixin
    'Interface': (21, 42, 56, 86),  # Interface, Protocol, TypeClass, Concept
    'Struct': (49,), 'Enum': (11,), 'Trait': (53,),
    'Type': (3, 10, 54, 55, 57, 59, 63, 73),  # AssociatedType, DataFamily, Type, TypeAlias, TypeFamily, Union, Error,
    # Delegate
    'Function': (17, 25, 34),  # Function, Macro, Operator
    # Constructor, Getter, Setter, Method, AbstractMethod, MethodSpecification, ProtocolMethod, PureVirtualMethod,
    # TraitMethod, TypeClassMethod, Accessor, MethodAlias, SingletonMethod, StaticMethod
    'Method': (9, 18, 45, 26, 66, 67, 68, 69, 70, 71, 72, 74, 76, 80),
    'Module': (16, 29, 30, 35, 36, 64),  # File, Module, Namespace, Package, PackageObject, Library
    # Constant, EnumMember, Event, Field, Property, Variable, StaticDataMember, StaticEvent, StaticField,
    # StaticProperty, StaticVariable
    'Variable': (8, 12, 13, 15, 41, 61, 77, 78, 79, 81, 82)}
SCIP_KINDS = {kind: label for label, kinds in _SCIP_LABELS.items() for kind in kinds}
DEFINITION, IMPORT = 0x1, 0x2  # SymbolRole bits


def _varint(data: bytes, at: int) -> tuple[int, int]:
    value = shift = 0
    while True:
        byte = data[at]
        at += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, at
        shift += 7


def _fields(data: bytes) -> Iterator[tuple[int, int, Any]]:
    """The fields of one protobuf message as (number, wire type, value): an int for varints and fixed widths, bytes
    for length-delimited ones, as the protobuf wire format encodes them."""
    at = 0
    while at < len(data):
        key, at = _varint(data, at)
        number, wire = key >> 3, key & 7
        if wire == 0:
            value, at = _varint(data, at)
        elif wire == 1:
            value, at = int.from_bytes(data[at:at + 8], 'little'), at + 8
        elif wire == 2:
            size, at = _varint(data, at)
            value, at = data[at:at + size], at + size
        elif wire == 5:
            value, at = int.from_bytes(data[at:at + 4], 'little'), at + 4
        else:
            raise ValueError(f'unsupported protobuf wire type {wire}')
        yield number, wire, value


def _ints(wire: int, value: Any) -> list[int]:
    """A repeated int32, packed or not."""
    if wire == 0:
        return [value]
    found: list[int] = []
    at = 0
    while at < len(value):
        one, at = _varint(value, at)
        found.append(one)
    return found


def _range(message: bytes, single: bool) -> list[int]:
    """A SingleLineRange (line, start, end) or MultiLineRange (start line, start, end line, end) as SCIP's legacy
    repeated form, which keeps three or four numbers."""
    values = {number: value for number, _, value in _fields(message)}
    return [values.get(1, 0), values.get(2, 0), values.get(3, 0)] + ([] if single else [values.get(4, 0)])


@dataclass
class _Occurrence:
    symbol: str
    roles: int
    range: list[int]
    enclosing: list[int]


def _occurrence(data: bytes) -> _Occurrence:
    found = _Occurrence('', 0, [], [])
    typed: list[int] | None = None
    enclosing: list[int] | None = None
    for number, wire, value in _fields(data):
        if number == 1:
            found.range += _ints(wire, value)
        elif number == 2:
            found.symbol = value.decode('utf-8')
        elif number == 3:
            found.roles = value
        elif number == 7:
            found.enclosing += _ints(wire, value)
        elif number in (8, 9):
            typed = _range(value, number == 8)
        elif number in (10, 11):
            enclosing = _range(value, number == 10)
    found.range = typed if typed is not None else found.range  # typed_range takes precedence, scip.proto
    found.enclosing = enclosing if enclosing is not None else found.enclosing
    return found


def _lines(numbers: list[int]) -> tuple[int, int]:
    """A SCIP range's first and last line, 0-based: three numbers keep one line, four end on the third."""
    if not numbers:
        return 0, 0
    return numbers[0], numbers[2] if len(numbers) >= 4 else numbers[0]


def descriptors(symbol: str) -> list[tuple[str, str]]:
    """A SCIP symbol's descriptors, each its name and suffix: `/` namespace, `#` type, `.` term, `()` method, `:`
    meta, `!` macro, `[]` type parameter, `()param` parameter; the scheme, manager, package and version are passed
    over, a doubled space being an escaped one. A local symbol has none."""
    if symbol.startswith('local '):
        return []
    at, spaces = 0, 0
    while at < len(symbol) and spaces < 4:
        if symbol[at] == ' ':
            if symbol[at + 1:at + 2] == ' ':
                at += 2
                continue
            spaces += 1
        at += 1
    text = symbol[at:]
    found: list[tuple[str, str]] = []
    index = 0
    while index < len(text):
        if text[index] == '`':
            end = index + 1
            name: list[str] = []
            while end < len(text):
                if text[end] == '`' and text[end + 1:end + 2] == '`':
                    name.append('`')
                    end += 2
                elif text[end] == '`':
                    break
                else:
                    name.append(text[end])
                    end += 1
            word, index = ''.join(name), end + 1
        elif text[index] in '[(':
            close = ']' if text[index] == '[' else ')'
            end = text.find(close, index)
            word, index = text[index + 1:end], end + 1
            found.append((word, '[]' if close == ']' else '()param'))
            continue
        else:
            end = index
            while end < len(text) and (text[end].isalnum() or text[end] in '_+-$'):
                end += 1
            word, index = text[index:end], end
        if index >= len(text):
            found.append((word, ''))
            break
        suffix = text[index]
        if suffix == '(':
            end = text.find(').', index)
            found.append((word, '()'))
            index = end + 2 if end >= 0 else len(text)
        else:
            found.append((word, suffix))
            index += 1
    return found


def _scip_label(symbol: str, kind: int) -> str:
    if kind in SCIP_KINDS:
        return SCIP_KINDS[kind]
    parts = descriptors(symbol)
    if not parts:
        return 'Variable'
    suffix = parts[-1][1]
    if suffix == '()':
        return 'Method' if len(parts) > 1 and parts[-2][1] == '#' else 'Function'
    return {'#': 'Class', '/': 'Module', '!': 'Function'}.get(suffix, 'Variable')


def qualified(symbol: str) -> str:
    """A SCIP symbol as the other providers name it: its descriptors' names joined with dots, parameters and type
    parameters left out, `kitchen.timer.Timer.tick` for `scip-python python kitchen 0.1.0 `kitchen.timer`/Timer#tick().`;
    a namespace written with slashes keeps them as its indexer wrote it. A local symbol keeps its own form."""
    parts = [name for name, suffix in descriptors(symbol) if suffix not in ('()param', '[]')]
    return '.'.join(parts) if parts else symbol


def _callable(symbol: str) -> bool:
    parts = descriptors(symbol)
    return bool(parts) and parts[-1][1] == '()'


class Scip:
    """A SCIP index file, decoded once. A document's stamp is the sha256 of its encoded bytes, so a reindex that
    changes nothing in a file changes nothing here."""

    def __init__(self, path: Path) -> None:
        try:
            data = path.read_bytes()
        except OSError:
            raise Unavailable(f'No SCIP index at {path}.', 'write one with the SCIP indexer for the language, such as '
                              'scip-python index or scip-typescript index, then run map code-import again') from None
        self.tool, self.version, self.notices = 'scip', '', cast(list[str], [])
        self.by_name, self.unresolved = False, cast(dict[str, set[str]], {})
        self.documents: dict[str, bytes] = {}
        self.kinds: dict[str, int] = {}
        self.implements: dict[str, list[str]] = {}  # SymbolInformation.relationships with is_implementation
        try:
            for number, _, value in _fields(data):
                if number == 1:  # Metadata: tool_info = 2 (name = 1, version = 2)
                    for inner, _, held in _fields(value):
                        if inner == 2:
                            tool = {key: one for key, _, one in _fields(held)}
                            self.tool = tool.get(1, b'scip').decode('utf-8') or 'scip'
                            self.version = tool.get(2, b'').decode('utf-8')
                elif number == 2:
                    path_of = next((held.decode('utf-8') for inner, _, held in _fields(value) if inner == 1), '')
                    if path_of:
                        self.documents[path_of] = value
                elif number == 3:  # external_symbols: kinds of symbols defined elsewhere
                    self._information(value)
            for document in self.documents.values():
                for number, _, value in _fields(document):
                    if number == 3:
                        self._information(value)
        except (ValueError, IndexError, UnicodeDecodeError):
            raise Unavailable(f'{path} is not a SCIP index.', 'write it again with a SCIP indexer') from None
        self.refresh = (f'run {self.tool} index again' if self.tool.startswith('scip-')
                        else f'write {path.name} again with its SCIP indexer')
        self._defined: dict[str, str] | None = None

    def _information(self, data: bytes) -> None:
        """A SymbolInformation: symbol = 1, relationships = 4 (symbol = 1, is_implementation = 3), kind = 5."""
        symbol, kind, bases = '', 0, cast(list[str], [])
        for number, _, value in _fields(data):
            if number == 1:
                symbol = value.decode('utf-8')
            elif number == 4:
                related = {inner: held for inner, _, held in _fields(value)}
                if related.get(3) and isinstance(related.get(1), bytes):
                    bases.append(related[1].decode('utf-8'))
            elif number == 5:
                kind = value
        if symbol:
            self.kinds[symbol] = kind
            if bases:
                self.implements[symbol] = bases

    def listing(self) -> dict[str, str]:
        return {path: hashlib.sha256(data).hexdigest() for path, data in self.documents.items()}

    def _definitions(self) -> dict[str, str]:
        """Each symbol the index defines, with the document it is defined in."""
        if self._defined is None:
            self._defined = {}
            for path, document in self.documents.items():
                for number, _, value in _fields(document):
                    if number == 2:
                        one = _occurrence(value)
                        parts = descriptors(one.symbol) if one.roles & DEFINITION and one.symbol else []
                        if parts and parts[-1][1] not in ('()param', '[]', ':'):
                            self._defined.setdefault(one.symbol, path)
        return self._defined

    def read(self, paths: Sequence[str], known: Sequence[Symbol] = ()) -> tuple[list[Symbol], list[Edge]]:
        defined = self._definitions()
        symbols: list[Symbol] = []
        edges: list[Edge] = []
        without_extent = 0
        for path in paths:
            document = self.documents.get(path)
            if document is None:
                continue
            occurrences = [_occurrence(value) for number, _, value in _fields(document) if number == 2]
            spans: list[tuple[int, int, str]] = []
            for one in occurrences:
                if not one.roles & DEFINITION or not one.symbol or one.symbol.startswith('local '):
                    continue
                parts = descriptors(one.symbol)
                if not parts or parts[-1][1] in ('()param', '[]', ':'):
                    continue
                first, last = _lines(one.enclosing or one.range)
                label = _scip_label(one.symbol, self.kinds.get(one.symbol, 0))
                symbols.append(Symbol(qualified(one.symbol), parts[-1][0], label, path, first + 1, last + 1,
                                      one.symbol))
                if one.enclosing:
                    spans.append((first, last, one.symbol))
                elif parts[-1][1] in ('()', '#'):
                    without_extent += 1
                for base in self.implements.get(one.symbol, ()):
                    if base in defined:
                        kind = ('OVERRIDE' if label in ('Method', 'Function') else 'IMPLEMENTS'
                                if _scip_label(base, self.kinds.get(base, 0)) == 'Interface' else 'INHERITS')
                        edges.append(Edge(qualified(one.symbol), qualified(base), kind, path, first + 1,
                                          defined[base]))
            for one in occurrences:
                if one.roles & DEFINITION or not one.symbol or one.symbol.startswith('local '):
                    continue
                line = _lines(one.range)[0]
                if one.symbol not in defined:
                    continue
                if one.roles & IMPORT:
                    edges.append(Edge(path, qualified(one.symbol), 'IMPORTS', path, line + 1, defined[one.symbol]))
                    continue
                holders = [span for span in spans if span[0] <= line <= span[1] and span[2] != one.symbol]
                if not holders:
                    continue
                holder = min(holders, key=lambda span: span[1] - span[0])[2]
                edges.append(Edge(qualified(holder), qualified(one.symbol), 'CALLS' if _callable(one.symbol)
                                  else 'USAGE', path, line + 1, defined[one.symbol]))
        if without_extent:
            self.notices.append(f'{without_extent} functions and types in the index carry no enclosing_range, so the '
                                'calls made inside them are not known; an indexer that writes it gives them.')
        return symbols, list(dict.fromkeys(edges))


# ------------------------------------------------------------------------------------------------ an MCP server

def _cypher_text(value: str) -> str:
    return "'" + value.replace('\\', '\\\\').replace("'", "\\'") + "'"


LABEL = re.compile(r'^[A-Za-z][A-Za-z0-9_]*$')
# The relations read from a declaration, as codebase-memory's graph names them; IMPORTS starts at a File.
RELATIONS = '|'.join(kind for kind in EDGE_KINDS if kind != 'IMPORTS')


class CodeGraphServer:
    """A code-graph MCP server, read through its tools. Only codebase-memory-mcp's `query_graph` and its graph schema
    are read today; another server is named in what stops the import, so a reader for it is added, not guessed."""

    def __init__(self, call: Callable[[str, dict[str, Any]], Any], server: str, version: str, tools: Sequence[str],
                 folder: Path, project: str, labels: Sequence[str], *, index_missing: bool = False) -> None:
        self.tool, self.version, self.notices = server, version, cast(list[str], [])
        self.refresh, self.by_name = f'let {server} index the folder again with its index_repository tool', False
        self.unresolved = cast(dict[str, set[str]], {})
        if 'query_graph' not in tools or 'list_projects' not in tools:
            raise Unavailable(f'The MCP server {server} offers no query_graph and list_projects tools, so Metaform '
                              'cannot read its code graph.', 'set code_provider to scip or tree-sitter, or set '
                              'code_server to codebase-memory-mcp')
        self._call = call
        self.labels = [label for label in labels if LABEL.fullmatch(label)]
        if project:
            self.project = project
        else:
            try:
                self.project = self._project(folder)
            except Unavailable as error:
                if not index_missing or 'holds no index of' not in error.message or 'index_repository' not in tools:
                    raise
                self._json('index_repository', {'repo_path': str(folder)})
                self.project = self._project(folder)
        self.prefix = self.project + '.'

    def _json(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = self._call(tool, {**arguments, 'format': 'json'})
        structured = getattr(result, 'structured_content', None)
        if isinstance(structured, dict) and structured:
            return cast(dict[str, Any], structured)
        text = ''.join(getattr(block, 'text', '') for block in getattr(result, 'content', []) or [])
        if getattr(result, 'is_error', False):
            raise Unavailable(f'{self.tool} {tool} failed: {text[:300]}', f'run {tool} in {self.tool} to see why')
        try:
            return cast(dict[str, Any], json.loads(text))
        except json.JSONDecodeError:
            raise Unavailable(f'{self.tool} {tool} answered with no JSON: {text[:200]}',
                              f'check {self.tool} {tool} by hand') from None

    def query(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Read a provider tool's JSON evidence through the existing connected session."""
        return self._json(tool, arguments)

    def _project(self, folder: Path) -> str:
        offset, wanted = 0, home.path_key(folder)
        while True:
            page = self._json('list_projects', {'limit': 500, 'offset': offset})
            for one in cast(list[dict[str, Any]], page.get('projects', [])):
                root = one.get('root_path')
                if isinstance(root, str) and home.path_key(root) == wanted:
                    return str(one['name'])
            if not page.get('has_more'):
                break
            offset += int(page.get('returned') or 500)
        raise Unavailable(f'{self.tool} holds no index of {folder}.', f'index the folder with {self.tool}\'s '
                          'index_repository tool, or name its project in the setting code_server_project')

    def rows(self, query: str) -> list[list[Any]]:
        """Every row of a query, page by page with the server's cursor. The server reindexes as files change; a
        cursor it no longer honours starts the query again, a few times, so the rows come from one index."""
        for _ in range(4):
            found: list[list[Any]] = []
            cursor: str | None = None
            while True:
                arguments: dict[str, Any] = {'project': self.project, 'query': query, 'max_rows': 99998,
                                             'max_output_tokens': 1000000}
                if cursor:
                    arguments['cursor'] = cursor
                try:
                    page = self._json('query_graph', arguments)
                except Unavailable as stop:
                    if cursor and 'stale_cursor' in stop.message:
                        break
                    raise
                if 'rows' not in page and page.get('error'):
                    if cursor and 'stale_cursor' in str(page['error']):
                        break
                    raise Unavailable(f'{self.tool} query_graph: {page["error"]}',
                                      f'{self.refresh}, or run map code-import from=tree-sitter')
                found += cast(list[list[Any]], page.get('rows', []))
                cursor = cast(str | None, page.get('next_cursor'))
                if not page.get('has_more') or not cursor:
                    return found
        raise Unavailable(f'{self.tool} reindexed the project while it was being read, four times over.',
                          'run map code-import again once the files stop changing')

    def _bare(self, qn: str) -> str:
        return qn.removeprefix(self.prefix)

    def listing(self) -> dict[str, str]:
        return {str(path): str(stamp or '') for path, stamp in
                self.rows('MATCH (f:File) RETURN f.file_path, f.last_modified')
                if isinstance(path, str) and path and not path.startswith('<')}

    def read(self, paths: Sequence[str], known: Sequence[Symbol] = ()) -> tuple[list[Symbol], list[Edge]]:
        symbols: list[Symbol] = []
        edges: list[Edge] = []
        if not self.labels:
            return symbols, edges
        which = ' OR '.join(f'n:{label}' for label in self.labels)
        callers = ' OR '.join(f'a:{label}' for label in self.labels)
        for start in range(0, len(paths), 200):
            chunk = ', '.join(_cypher_text(path) for path in paths[start:start + 200])
            for qn, name, labels, path, first, last in self.rows(
                    f'MATCH (n) WHERE ({which}) AND n.file_path IN [{chunk}] RETURN n.qualified_name, n.name, '
                    'labels(n), n.file_path, n.start_line, n.end_line'):
                label = next((one for one in _labels(labels) if one in self.labels), 'Function')
                symbols.append(Symbol(self._bare(str(qn)), str(name), label, str(path), _int(first), _int(last),
                                      str(qn)))
            for source, target, kind, path, line, target_path in self.rows(
                    f'MATCH (a)-[r:{RELATIONS}]->(b) WHERE ({callers}) AND a.file_path IN [{chunk}] '
                    'RETURN a.qualified_name, b.qualified_name, type(r), a.file_path, r.line, b.file_path'):
                edges.append(Edge(self._bare(str(source)), self._bare(str(target)), str(kind), str(path), _int(line),
                                  str(target_path or '')))
            for path, target, target_path in self.rows(
                    f'MATCH (a:File)-[r:IMPORTS]->(b) WHERE a.file_path IN [{chunk}] '
                    'RETURN a.file_path, b.qualified_name, b.file_path'):
                edges.append(Edge(str(path), self._bare(str(target)), 'IMPORTS', str(path), 0, str(target_path or '')))
        return symbols, list(dict.fromkeys(edges))


def _labels(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(one) for one in cast(list[Any], value)]
    try:
        found = json.loads(str(value))
    except json.JSONDecodeError:
        return [str(value)]
    return [str(one) for one in cast(list[Any], found)] if isinstance(found, list) else [str(found)]


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def server_environment(names: Sequence[str]) -> dict[str, str]:
    """The environment a code-graph server started over stdio is given: the MCP SDK's safe defaults, HOME and PATH
    among them, and the variables the setting code_server_env names, a name ending in * every variable it starts. The
    SDK passes nothing else, so a server whose own configuration lives in the environment, as codebase-memory-mcp's
    CBM_CACHE_DIR does, is started as the person runs it."""
    from mcp.client.stdio import get_default_environment
    found = get_default_environment()
    for name in names:
        wanted = name.strip()
        if not wanted:
            continue
        found.update((key, value) for key, value in os.environ.items()
                     if (key.startswith(wanted[:-1]) if wanted.endswith('*') else key == wanted))
    return found


def server_target(setting: str, environment: Sequence[str] = ()) -> Any:
    """What the MCP client connects to: a URL for Streamable HTTP, or a command line started over stdio with the
    environment `server_environment` gives. Tests swap this for an in-process server."""
    from mcp.client.stdio import StdioServerParameters
    text = setting.strip()
    if text.startswith(('http://', 'https://')):
        return text
    words = shlex.split(text)
    if not words:
        raise Unavailable('No code-graph MCP server is named.', 'metaform map code-import from=scip, or set '
                          'code_server to the server\'s command or URL')
    command = shutil.which(words[0])
    if command is None:
        raise Unavailable(f'{words[0]} is not installed here.', 'install codebase-memory-mcp '
                          '(https://github.com/DeusData/codebase-memory-mcp), or set code_server to another '
                          'server\'s command or URL')
    return StdioServerParameters(command=command, args=words[1:], env=server_environment(environment))


def _cause(error: BaseException) -> BaseException:
    """The first cause inside an exception group, as an anyio task group raises what failed in it."""
    while isinstance(error, BaseExceptionGroup):
        error = cast(BaseExceptionGroup[BaseException], error).exceptions[0]
    return error


@contextmanager
def code_graph_server(setting: str, folder: Path, project: str, labels: Sequence[str],
                      environment: Sequence[str] = (), *, index_missing: bool = False) -> Generator[CodeGraphServer]:
    """A session with the code-graph MCP server for the length of the block, its async client driven from this
    thread through an anyio blocking portal. Only what the server does is said to be the server's: connecting,
    listing its tools and each tool call; an error raised by the block itself passes through as it is."""
    try:
        from anyio.from_thread import start_blocking_portal
        from mcp import Client
    except ImportError:
        raise Unavailable('The MCP SDK is not installed, so no MCP server can be read.',
                          'install metaform with the mcp module enabled') from None
    target = server_target(setting, environment)
    step = 'run it by hand to see why, or set code_provider to scip or tree-sitter'
    with start_blocking_portal() as portal:
        try:
            with ExitStack() as stack:
                try:
                    opened = Client(target, read_timeout_seconds=120)
                    client = stack.enter_context(portal.wrap_async_context_manager(opened))
                    listed = portal.call(client.list_tools)
                except Exception as error:  # noqa: BLE001  whatever stops the connection is the server's to explain
                    cause = _cause(error)
                    if isinstance(cause, Unavailable):
                        raise cause from None
                    raise Unavailable(f'The MCP server {setting} could not be read: {cause}.', step) from None
                info = getattr(client.session, 'server_info', None)
                name = str(getattr(info, 'name', '') or setting)
                version = str(getattr(info, 'version', '') or '')

                def call(tool: str, arguments: dict[str, Any]) -> Any:
                    try:
                        return portal.call(client.call_tool, tool, arguments)
                    except Exception as error:  # noqa: BLE001  a call that fails is the server's to explain
                        raise Unavailable(f'{name} {tool} could not be read: {_cause(error)}.', step) from None
                yield CodeGraphServer(call, name, version, [tool.name for tool in listed.tools], folder, project,
                                      labels, index_missing=index_missing)
        except BaseExceptionGroup as group:  # the client's task group wraps what the block raised: the first cause
            cause = _cause(group)
            raise (cause if isinstance(cause, Exception) else group) from None


# ------------------------------------------------------------------------------------------------ tree-sitter

# The grammar package and its language function per file extension; a grammar not installed is passed over.
GRAMMARS = {'.py': ('tree_sitter_python', 'language'), '.js': ('tree_sitter_javascript', 'language'),
            '.mjs': ('tree_sitter_javascript', 'language'), '.cjs': ('tree_sitter_javascript', 'language'),
            '.jsx': ('tree_sitter_javascript', 'language'), '.ts': ('tree_sitter_typescript', 'language_typescript'),
            '.tsx': ('tree_sitter_typescript', 'language_tsx'), '.go': ('tree_sitter_go', 'language'),
            '.rs': ('tree_sitter_rust', 'language'), '.java': ('tree_sitter_java', 'language'),
            '.rb': ('tree_sitter_ruby', 'language'), '.c': ('tree_sitter_c', 'language'),
            '.h': ('tree_sitter_c', 'language'), '.cpp': ('tree_sitter_cpp', 'language'),
            '.cc': ('tree_sitter_cpp', 'language'), '.hpp': ('tree_sitter_cpp', 'language'),
            '.cs': ('tree_sitter_c_sharp', 'language'), '.php': ('tree_sitter_php', 'language_php')}
TAG_LABELS = {'function': 'Function', 'method': 'Method', 'class': 'Class', 'interface': 'Interface',
              'module': 'Module', 'type': 'Type', 'struct': 'Struct', 'enum': 'Enum', 'trait': 'Trait',
              'macro': 'Function', 'constant': 'Variable', 'field': 'Variable', 'implementation': 'Class'}


def _module_name(path: str) -> str:
    """A file's module as its path names it, dotted: `kitchen/timer.py` is `kitchen.timer`, a package's `__init__.py`,
    an `index.js` or a `mod.rs` the folder."""
    stem = path.rsplit('.', 1)[0].split('/')
    if stem and stem[-1] in ('__init__', 'index', 'mod'):
        stem = stem[:-1]
    return '.'.join(stem)


def local_name(qn: str, path: str) -> str:
    """The part of a qualified name below its module, `Timer.tick`, however much of the path the provider put before
    it: `kitchen.timer.Timer.tick`, `src.kitchen.timer.Timer.tick` and a SCIP index's `timer.Timer.tick` for
    `src/kitchen/timer.py` all give `Timer.tick`, found as the longest end of the file's module path the name holds."""
    parts, module = qn.split('.'), _module_name(path).split('.')
    for size in range(len(module), 0, -1):
        tail = module[-size:]
        for start in range(len(parts) - size):
            if parts[start:start + size] == tail:
                return '.'.join(parts[start + size:])
    return qn


# Python's imports and base classes, read from its grammar's nodes, which its tags query does not capture.
PYTHON_SCOPE = """
(import_statement) @import
(import_from_statement) @import
(class_definition name: (identifier) @class superclasses: (argument_list) @bases)
"""
SELF = ('self', 'cls', 'this')


def _text(node: Any) -> str:
    return cast(bytes, node.text).decode('utf-8', 'replace')


def _receiver(call: Any) -> str | None:
    """What a call is made on, as its source writes it: `self` for `self.tick()`, `home` for `home.add()`; None for a
    bare call. The call node is the one a grammar's tags query captures, or the call around its arguments."""
    if call.type in ('argument_list', 'arguments') and call.parent is not None:
        call = call.parent
    function = call.child_by_field_name('function')
    holder = call if function is None else function
    if holder.type == 'identifier':
        return None
    for name in ('object', 'operand', 'receiver', 'value', 'expression', 'scope'):
        part = holder.child_by_field_name(name)
        if part is not None:
            return _text(part)
    return None


@dataclass
class _Scope:
    """What one file's calls are resolved in: the names it imports, each with the module and the name it comes from,
    None for a module itself; the modules it imports every name of; and its classes' bases as written."""
    binds: dict[str, tuple[str, str | None, int]]
    stars: list[str]
    bases: dict[int, list[str]]  # a class definition's start byte: its bases


def _python_scope(query: Any, matches: Callable[[Any, Any], list[tuple[int, dict[str, list[Any]]]]], root: Any,
                  module: str, package: bool) -> _Scope:
    scope = _Scope({}, [], {})
    parts = module.split('.') if module else []
    here = parts if package else parts[:-1]
    for _, captures in matches(query, root):
        for node in captures.get('import', []):
            line = node.start_point[0] + 1
            if node.type == 'import_statement':
                for name in node.children_by_field_name('name'):
                    if name.type == 'aliased_import':
                        target = name.child_by_field_name('name')
                        alias = name.child_by_field_name('alias')
                        if target is not None and alias is not None:
                            scope.binds[_text(alias)] = (_text(target), None, line)
                    else:
                        scope.binds[_text(name)] = (_text(name), None, line)
                continue
            source = node.child_by_field_name('module_name')
            if source is None:
                continue
            written = _text(source)
            if source.type == 'relative_import':
                dots = len(written) - len(written.lstrip('.'))
                rest = written[dots:]
                base = here[:len(here) - (dots - 1)] if dots - 1 <= len(here) else []
                written = '.'.join([*base, *([rest] if rest else [])])
            if any(child.type == 'wildcard_import' for child in node.children):
                scope.stars.append(written)
            for name in node.children_by_field_name('name'):
                if name.type == 'aliased_import':
                    target = name.child_by_field_name('name')
                    alias = name.child_by_field_name('alias')
                    if target is not None and alias is not None:
                        scope.binds[_text(alias)] = (written, _text(target), line)
                else:
                    scope.binds[_text(name)] = (written, _text(name), line)
        for node in captures.get('bases', []):
            if node.parent is not None:
                scope.bases[node.parent.start_byte] = [_text(child) for child in node.named_children
                                                       if child.type in ('identifier', 'attribute')]
    return scope


class _Resolver:
    """Every symbol the project declares, read now or held by the layer, by module and by the name below it, so a
    call is resolved only through the scope its file gives it."""

    def __init__(self, symbols: Sequence[Symbol]) -> None:
        self.by_path: dict[str, list[Symbol]] = {}
        self.below: dict[tuple[str, str], list[Symbol]] = {}  # (module, name below it): symbols
        for symbol in symbols:
            module = _module_name(symbol.path)
            self.by_path.setdefault(symbol.path, []).append(symbol)
            if symbol.qn.startswith(module + '.'):
                self.below.setdefault((module, symbol.qn[len(module) + 1:]), []).append(symbol)
        self.modules = {module for module, _ in self.below}
        self.bases: dict[Symbol, list[Symbol]] = {}

    def module(self, written: str) -> str | None:
        """The project's module an import names: itself, or the one module whose dotted path ends with it, as a
        src layout's `src.metaform.home` ends with `metaform.home`."""
        if written in self.modules:
            return written
        found = [one for one in self.modules if one.endswith('.' + written)]
        return found[0] if len(found) == 1 else None

    def declared(self, module: str | None, name: str) -> Symbol | None:
        found = self.below.get((module, name), []) if module is not None else []
        return found[0] if len(found) == 1 else None

    def member(self, owner: Symbol, name: str, depth: int = 0) -> Symbol | None:
        """A method of a class, its own or, through the bases it names, inherited."""
        found = [one for one in self.by_path.get(owner.path, []) if one.qn == f'{owner.qn}.{name}']
        if found:
            return found[0]
        for base in self.bases.get(owner, []) if depth < 6 else []:
            inherited = self.member(base, name, depth + 1)
            if inherited is not None:
                return inherited
        return None

    def named(self, path: str, scope: _Scope, name: str) -> Symbol | None:
        """A bare name in a file: its own top-level declaration, the one declaration of that name in it, or the
        declaration it imports under that name."""
        module = _module_name(path)
        own = [one for one in self.by_path.get(path, []) if one.name == name and one.label != 'Method']
        top = [one for one in own if one.qn == f'{module}.{name}']
        if len(top) == 1 or len(own) == 1:
            return (top or own)[0]
        if name in scope.binds:
            written, imported, _ = scope.binds[name]
            return self.declared(self.module(written), imported) if imported is not None else None
        for written in scope.stars:
            found = self.declared(self.module(written), name)
            if found is not None:
                return found
        return None

    def on(self, path: str, scope: _Scope, receiver: str, name: str) -> Symbol | None:
        """`name` called on a module or a class the file names: an imported module's declaration, or a class's
        method."""
        bound = scope.binds.get(receiver)
        if bound is not None:
            written, imported, _ = bound
            if imported is None:
                return self.declared(self.module(written), name)
            module = self.module(f'{written}.{imported}')
            if module is not None:
                return self.declared(module, name)
        owner = self.named(path, scope, receiver) if receiver.isidentifier() else None
        if owner is not None and owner.label in ('Class', 'Interface', 'Struct', 'Trait', 'Enum'):
            return self.member(owner, name)
        return None


class TreeSitter:
    """A tags-query pass over the project's files. The stamp of a file is the sha256 of its bytes."""

    def __init__(self, folder: Path, files: Sequence[str]) -> None:
        try:
            self.ts: Any = importlib.import_module('tree_sitter')
        except ImportError:
            raise Unavailable('tree-sitter is not installed here.', 'install it with its grammars, such as '
                              'uv pip install tree-sitter tree-sitter-python, or set code_provider to scip or '
                              'mcp') from None
        self.folder, self.tool, self.notices = folder, 'tree-sitter', cast(list[str], [])
        self.refresh, self.by_name = 'run map code-import again', True
        self.unresolved: dict[str, set[str]] = {}
        self.version = _version('tree-sitter')
        self._languages: dict[str, tuple[Any, Any, Any] | None] = {}
        self.files = [path for path in files if self._language(path) is not None]
        if not self.files:
            raise Unavailable('No installed tree-sitter grammar reads the files here.',
                              'install the grammar for the language, such as uv pip install tree-sitter-python')

    def _language(self, path: str) -> tuple[Any, Any, Any] | None:
        """The grammar, tags query and, for Python, scope query for a file, by its extension; None when no installed
        grammar has tags."""
        extension = Path(path).suffix
        grammar = GRAMMARS.get(extension)
        if grammar is None:
            return None
        if extension not in self._languages:
            try:
                module = importlib.import_module(grammar[0])
                tags = getattr(module, 'TAGS_QUERY', None)
                language = self.ts.Language(getattr(module, grammar[1])())
                scope = self.ts.Query(language, PYTHON_SCOPE) if extension == '.py' else None
                self._languages[extension] = (language, self.ts.Query(language, tags), scope) if tags else None
            except Exception:  # noqa: BLE001  a grammar that does not load is a grammar not installed
                self._languages[extension] = None
        return self._languages[extension]

    def listing(self) -> dict[str, str]:
        return {path: stamp for path in self.files if (stamp := file_hash(self.folder, path)) is not None}

    def _matches(self, query: Any, root: Any) -> list[tuple[int, dict[str, list[Any]]]]:
        cursor = getattr(self.ts, 'QueryCursor', None)
        if cursor is not None:
            return cast(list[tuple[int, dict[str, list[Any]]]], cursor(query).matches(root))
        return cast(list[tuple[int, dict[str, list[Any]]]], query.matches(root))

    def read(self, paths: Sequence[str], known: Sequence[Symbol] = ()) -> tuple[list[Symbol], list[Edge]]:
        symbols: list[Symbol] = []
        calls: list[tuple[str, str, str | None, int, int]] = []  # path, name called, receiver, byte offset, line
        spans: dict[str, list[tuple[int, int, Symbol]]] = {}
        scopes: dict[str, _Scope] = {}
        for path in paths:
            found = self._language(path)
            if found is None:
                continue
            language, query, scope_query = found
            try:
                source = (self.folder / path).read_bytes()
            except OSError:
                continue
            tree = self.ts.Parser(language).parse(source)
            module = _module_name(path)
            scopes[path] = (_python_scope(scope_query, self._matches, tree.root_node, module,
                                          Path(path).stem == '__init__')
                            if scope_query is not None else _Scope({}, [], {}))
            definitions: list[tuple[int, int, str, str, Any]] = []
            for _, captures in self._matches(query, tree.root_node):
                names = captures.get('name') or []
                for capture, nodes in captures.items():
                    kind, _, tag = capture.partition('.')
                    if not names or not nodes:
                        continue
                    node, name = nodes[0], _text(names[0])
                    if kind == 'definition':
                        definitions.append((node.start_byte, node.end_byte, name, TAG_LABELS.get(tag, 'Function'),
                                            node))
                    elif kind == 'reference' and tag == 'call':
                        calls.append((path, name, _receiver(node), node.start_byte, node.start_point[0] + 1))
            definitions.sort(key=lambda one: (one[0], -one[1]))
            held = cast(list[tuple[int, int, Symbol]], [])
            for start, end, name, label, node in definitions:
                outer = [one for one in held if one[0] <= start and end <= one[1]]
                parent = outer[-1][2] if outer else None
                qn = f'{parent.qn}.{name}' if parent is not None else f'{module}.{name}' if module else name
                if label == 'Function' and parent is not None and parent.label == 'Class':
                    label = 'Method'
                symbol = Symbol(qn, name, label, path, node.start_point[0] + 1, node.end_point[0] + 1)
                held.append((start, end, symbol))
                symbols.append(symbol)
            spans[path] = held
        # Resolved against every symbol the project declares: these files' and what the layer holds of the rest.
        reading = set(paths)
        resolver = _Resolver([*symbols, *(one for one in known if one.path not in reading)])
        edges: list[Edge] = []
        for path, held in spans.items():
            scope = scopes[path]
            for start, _, symbol in held:
                bases = [self._base(resolver, path, scope, written) for written in scope.bases.get(start, [])]
                resolver.bases[symbol] = [base for base in bases if base is not None]
                edges += [Edge(symbol.qn, base.qn, 'INHERITS', path, symbol.start, base.path)
                          for base in resolver.bases[symbol]]
            for name, (written, imported, line) in scope.binds.items():
                target = resolver.declared(resolver.module(written), imported) if imported is not None else None
                if target is not None:
                    edges.append(Edge(path, target.qn, 'IMPORTS', path, line, target.path))
                elif imported is not None and resolver.module(f'{written}.{imported}') is None:
                    self.unresolved.setdefault(path, set()).add(imported)
        for path, name, receiver, offset, line in calls:
            holders = [one for one in spans.get(path, []) if one[0] <= offset < one[1]]
            if not holders:
                continue
            caller = min(holders, key=lambda one: one[1] - one[0])[2]
            scope = scopes[path]
            if receiver is None:
                target = resolver.named(path, scope, name)
            elif receiver in SELF:
                owner = next((one[2] for one in sorted(holders, key=lambda one: one[1] - one[0])
                              if one[2].label in ('Class', 'Interface', 'Struct', 'Trait')), None)
                target = resolver.member(owner, name) if owner is not None else None
            else:
                target = resolver.on(path, scope, receiver, name)
            if target is None:
                if receiver is None or receiver in scope.binds:
                    self.unresolved.setdefault(path, set()).add(name)
                continue
            if target.qn != caller.qn or target.path != caller.path:
                edges.append(Edge(caller.qn, target.qn, 'CALLS', path, line, target.path))
        return symbols, list(dict.fromkeys(edges))

    @staticmethod
    def _base(resolver: _Resolver, path: str, scope: _Scope, written: str) -> Symbol | None:
        receiver, _, name = written.rpartition('.')
        return resolver.on(path, scope, receiver, name) if receiver else resolver.named(path, scope, name)


def _version(package: str) -> str:
    from importlib import metadata
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return ''


def tree_sitter_ready() -> bool:
    """Whether the py-tree-sitter bindings are installed, which the automatic choice of provider asks."""
    return importlib.util.find_spec('tree_sitter') is not None
