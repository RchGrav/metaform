"""Source inventory offered to intake through ``code.inventory``.

The graph supplies indexed declarations. Enabled modules can supply source parsers
for function bodies that declaration indexes omit. Locators and coverage remain local evidence, not classification prompts.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from metaform import home
from metaform.module import Context, provided

from .code import KINDS
from .code_index import CodeGraphServer, Symbol, Unavailable, code_graph_server, ignored, project_files

MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_SOURCE_BYTES = 64 * 1024


def _local(root: Path, written: str) -> str | None:
    try:
        path = Path(written)
        return (path if path.is_absolute() else root / path).resolve().relative_to(root).as_posix()
    except (OSError, ValueError):
        return None


def _parsed(path: str, source: bytes, symbols: list[Symbol],
            parser: Callable[[str, bytes], dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    result = parser(path, source)
    items = result['items']
    for item in items:
        matches = [symbol for symbol in symbols if symbol.start == item['start_line']
                   and symbol.end == item['end_line'] and symbol.name == item['symbol']]
        if len(matches) == 1:
            item['qualified_name'] = matches[0].qn
    return items, result['gaps']


def _coverage(server: CodeGraphServer, paths: list[str]) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    for start in range(0, len(paths), 100):
        chunk = paths[start:start + 100]
        try:
            pages.append(server.query('check_index_coverage', {'project': server.project,
                         'paths': chunk, 'path_limit': 100, 'diagnostics': 'full'}))
        except Unavailable as error:
            # Some providers reject an absent path. Keep the unfinished evidence local rather than failing intake.
            pages.append({'error': error.message, 'requested_paths': chunk})
    return pages


def _current_paths(coverage: list[dict[str, Any]]) -> set[str]:
    """Only explicit, current coverage may justify slicing source by graph line ranges.

    A syntactically valid old range can point at entirely different code. Missing or stale coverage is therefore
    a manual-review gap, while source parsing remains independent of those ranges.
    """
    current: set[str] = set()
    for page in coverage:
        raw = page.get('metadata')
        metadata = cast(dict[str, Any], raw) if isinstance(raw, dict) else {}
        if (page.get('error') or metadata.get('generation_matches') is not True or
                metadata.get('recording_status') != 'complete'):
            continue
        rows = page.get('paths')
        if not isinstance(rows, list):
            continue
        for raw_row in cast(list[Any], rows):
            if not isinstance(raw_row, dict):
                continue
            row = cast(dict[str, Any], raw_row)
            if (row.get('status') == 'no_recorded_issue' and row.get('freshness') == 'metadata_match'
                    and not row.get('coverage')):
                current.add(str(row.get('requested_path') or row.get('path') or ''))
    return current


def inventory(ctx: Context, paths: list[str] | None = None) -> dict[str, Any]:
    """Read all requested source declarations, retaining explicit gaps rather than silently dropping them.

    ``paths=None`` means project scope. Explicit paths must be inside the registered project and outside
    its ignore policy. Returns local source locators and hashes, plus graph/AST coverage evidence.
    """
    root = Path(ctx.require_store().project().path).resolve()
    skip = ignored([*home.ignore_patterns(root), *(ctx.setting('code_ignore') or [])])
    gaps: list[dict[str, Any]] = []
    requested: set[str] | None = None
    if paths is not None:
        requested = set()
        for written in paths:
            path = _local(root, written)
            if path is None or skip(path):
                gaps.append({'file': written, 'reason': 'outside_project_or_ignored'})
            else:
                requested.add(path)
    parsers: dict[str, Callable[[str, bytes], dict[str, Any]]] = {}
    for _, capability in provided(ctx.folder, 'code.functions'):
        for suffix in capability['suffixes']:
            parsers.setdefault(suffix, capability['parse'])
    kinds = list(ctx.setting('code_kinds') or KINDS)
    with code_graph_server(str(ctx.setting('code_server') or 'codebase-memory-mcp'), root,
                           str(ctx.setting('code_server_project') or ''), kinds,
                           list(ctx.setting('code_server_env') or []), index_missing=True) as server:
        status = server.query('index_status', {'project': server.project})
        listed = server.listing()
        graph_paths = {path for written in listed if (path := _local(root, written)) is not None and not skip(path)}
        selected = requested if requested is not None else graph_paths | {
            path for path in project_files(root) if Path(path).suffix in parsers and not skip(path)}
        safe = sorted(path for path in selected if _local(root, path) == path)
        coverage = _coverage(server, safe)
        symbols, _ = server.read([path for path in safe if path in graph_paths])
        provider, version, project = server.tool, server.version, server.project
    current = _current_paths(coverage)
    items: list[dict[str, Any]] = []
    for path in safe:
        own = [s for s in symbols if s.path == path]
        if path not in current:
            gaps.append({'file': path, 'reason': 'structural_coverage_unverified',
                         'action': 'Read source to place manually, or refresh this file in the index.'})
            own = []
        try:
            with (root / path).open('rb') as stream:
                data = stream.read(MAX_FILE_BYTES + 1)
            if len(data) > MAX_FILE_BYTES:
                gaps.append({'file': path, 'reason': 'file_too_large'})
                continue
            text = data.decode('utf-8')
        except (OSError, UnicodeDecodeError) as error:
            gaps.append({'file': path, 'reason': 'source_unreadable', 'detail': str(error)})
            continue
        digest = hashlib.sha256(data).hexdigest()
        found: list[dict[str, Any]] = []
        ast_used = False
        parser = parsers.get(Path(path).suffix)
        if parser is not None and any(kind in kinds for kind in ('Function', 'Method')):
            try:
                found, partial = _parsed(path, data, own, parser)
            except ImportError:
                gaps.append({'file': path, 'reason': 'source_parser_unavailable'})
            else:
                gaps.extend(partial)
                ast_used = True
                found = [item for item in found if item['label'] in kinds]
        lines = text.splitlines(keepends=True)
        for symbol in own:
            if ast_used and symbol.label in ('Function', 'Method'):
                continue
            locator = {'file': path, 'symbol': symbol.name, 'qualified_name': symbol.qn,
                       'label': symbol.label, 'start_line': symbol.start, 'end_line': symbol.end}
            if not 1 <= symbol.start <= symbol.end <= len(lines):
                gaps.append({**locator, 'reason': 'invalid_source_range'})
                continue
            found.append({**locator, 'source': ''.join(lines[symbol.start - 1:symbol.end])})
        if path not in graph_paths:
            gaps.append({'file': path, 'reason': 'not_in_graph'})
        if not found:
            gaps.append({'file': path, 'reason': 'no_declarations'})
        for item in found:
            item['sha256'] = digest
            if len(item['source'].encode('utf-8')) > MAX_SOURCE_BYTES:
                gaps.append({key: value for key, value in item.items() if key != 'source'} |
                            {'reason': 'source_too_large'})
            else:
                items.append(item)
    duplicates = Counter((item['file'], item['qualified_name']) for item in items)
    for item in items:
        item['unique_identity'] = duplicates[item['file'], item['qualified_name']] == 1
        if not item['unique_identity']:
            gaps.append({key: item[key] for key in ('file', 'qualified_name', 'start_line', 'end_line')} |
                        {'reason': 'duplicate_symbol_identity'})
    return {'provider': provider, 'version': version, 'project': project, 'generation': status.get('indexed_at'),
            'items': items, 'gaps': gaps, 'coverage': coverage, 'scope': safe,
            'coverage_basis': 'Indexed declarations supplemented by enabled source parser modules.'}
