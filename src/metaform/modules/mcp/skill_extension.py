"""The stable MCP Skills extension: complete manifests and individually readable skill files.

Source: modelcontextprotocol/ext-skills, specification/stable/skills.mdx. The originating MCP connection supplies
server identity. Listings contain reusable skills. Known documents from module providers are resolved only by URI.
"""
from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote, urlsplit, urlunsplit

import anyio
from mcp import types
from mcp.shared.exceptions import MCPError

from metaform import skills
from metaform.module import context, provided

EXTENSION = 'io.modelcontextprotocol/skills'
PAGE_SIZE = 50
TTL_MS = 0
CACHE_SCOPE = 'private'
NATIVE = 'skill://metaform/'


def _entry(bundle: dict[str, Any]) -> dict[str, Any]:
    return {key: bundle[key] for key in ('uri', 'frontmatter', 'resources')}


def entries(folder: Path) -> list[dict[str, Any]]:
    """Complete entries, without raw file bodies."""
    return sorted(skills.reusable_catalog(), key=lambda entry: str(entry['uri']))


def _provided(folder: Path, uri: str) -> dict[str, Any] | None:
    """Resolve one known document through public module services without enumerating their content."""
    for owner, resolve in provided(folder, 'skill.document'):
        bundle = resolve(context(owner, folder, surface='mcp'), uri)
        if bundle is not None and bundle['uri'] == uri:
            return cast(dict[str, Any], bundle)
    return None


def get(folder: Path, uri: str) -> dict[str, Any] | None:
    """Resolve a served skill independently of whether a listing includes it."""
    try:
        parsed = urlsplit(uri)
    except ValueError:
        return None
    if parsed.query or parsed.fragment or not parsed.path.endswith('/SKILL.md'):
        return None
    try:
        found = skills.reusable(uri)
    except ValueError:
        found = None
    if found is not None and found['uri'] == uri:
        return _entry(found)
    supplied = _provided(folder, uri)
    return None if supplied is None else _entry(supplied)


def resources(folder: Path) -> list[dict[str, Any]]:
    """Ordinary resource metadata for each enumerated SKILL.md, without exposing its body."""
    return [{'uri': entry['uri'], 'name': entry['frontmatter']['name'],
             'description': entry['frontmatter']['description'], 'mime_type': 'text/markdown'}
            for entry in entries(folder)]


def read(folder: Path, uri: str) -> tuple[bytes, str] | None:
    """Exact bytes of a served file; unknown and malformed paths are left to resources/read's unknown-resource error."""
    try:
        parsed = urlsplit(uri)
    except ValueError:
        return None
    if not parsed.scheme or parsed.query or parsed.fragment:
        return None
    bundles: list[dict[str, Any]] = []
    try:
        authored = skills.reusable(f'skill://{parsed.netloc}/SKILL.md')
    except ValueError:
        authored = None
    if authored is not None:
        bundles.append(authored)
    found = _file(bundles, uri)
    if found is not None:
        return found
    # Ask only for ancestor SKILL.md documents of this exact file. This is bounded by URI depth and never scans a map.
    parent = parsed.path.rpartition('/')[0]
    while True:
        candidate = urlunsplit((parsed.scheme, parsed.netloc, parent + '/SKILL.md', '', ''))
        bundle = _provided(folder, candidate)
        if bundle is not None and (found := _file([bundle], uri)) is not None:
            return found
        if not parent or parsed.path.endswith('/SKILL.md'):
            break
        parent = parent.rpartition('/')[0]
    return None


def _file(bundles: list[dict[str, Any]], uri: str) -> tuple[bytes, str] | None:
    for bundle in bundles:
        root = str(bundle['uri']).removesuffix('SKILL.md')
        for relative, raw in cast(dict[str, bytes], bundle['files']).items():
            if uri == root + quote(relative, safe='/'):
                mime = 'text/markdown' if relative.endswith('.md') else \
                    mimetypes.guess_type(relative)[0] or 'application/octet-stream'
                return raw, mime
    return None


def register(server: Any, folder: Path) -> None:
    """Register the extension's required methods; directory reads are not advertised."""
    class ListParams(types.PaginatedRequestParams):
        pass

    class GetParams(types.RequestParams):
        uri: str

    async def listing(ctx: Any, params: Any) -> dict[str, Any]:
        cursor = params.cursor
        if cursor is not None and (not cursor.isascii() or not cursor.isdecimal() or len(cursor) > 12):
            raise MCPError(-32602, 'Invalid skills cursor')
        offset = int(cursor) if cursor is not None else 0
        found = await anyio.to_thread.run_sync(entries, folder)
        if offset > len(found):
            raise MCPError(-32602, 'Invalid skills cursor')
        end = offset + PAGE_SIZE
        return {'resultType': 'complete', 'skills': found[offset:end], 'ttlMs': TTL_MS, 'cacheScope': CACHE_SCOPE,
                **({'nextCursor': str(end)} if end < len(found) else {})}

    async def getting(ctx: Any, params: Any) -> dict[str, Any]:
        found = await anyio.to_thread.run_sync(get, folder, params.uri)
        if found is None:
            raise MCPError(-32602, 'Skill not found')
        return {'resultType': 'complete', 'skill': found, 'ttlMs': TTL_MS, 'cacheScope': CACHE_SCOPE}

    server.extensions[EXTENSION] = {}
    server.add_request_handler('skills/list', ListParams, listing)
    server.add_request_handler('skills/get', GetParams, getting)
