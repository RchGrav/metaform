"""Reusable skills: SKILL.md documents with their files, published and read by name or skill:// URI, BASE-059."""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Hashable, Mapping
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Any, cast
from urllib.parse import quote, urlsplit

import yaml

from . import home

MAX_SKILL_FILES = 512
MAX_SKILL_BYTES = 16 * 1024 * 1024
_SKILL_NAME = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')
_URI_SEGMENT = re.compile(r"[A-Za-z0-9._~!$&'()*+,;=-]+")


class _SkillLoader(yaml.SafeLoader):
    def construct_mapping(self, node: yaml.Node, deep: bool = False) -> dict[Hashable, Any]:
        if not isinstance(node, yaml.MappingNode):
            raise TypeError('Skill frontmatter must contain YAML mappings.')
        self.flatten_mapping(node)
        keys: set[str] = set()
        for key_node, _ in node.value:
            if not isinstance(key_node, yaml.ScalarNode) or key_node.tag != 'tag:yaml.org,2002:str':
                raise TypeError('Skill frontmatter mapping keys must be strings.')
            if key_node.value in keys:
                raise ValueError(f'Duplicate skill frontmatter key: {key_node.value}.')
            keys.add(key_node.value)
        return super().construct_mapping(node, deep)


def _valid_name(name: str) -> None:
    if not 1 <= len(name) <= 64 or not _SKILL_NAME.fullmatch(name):
        raise ValueError('Skill name must be 1–64 lowercase letters, digits or single separating hyphens.')


def _skill_uri(name: str, uri: str | None) -> str:
    value = uri if uri is not None else f'skill://{name}/SKILL.md'
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise ValueError('Invalid skill URI.') from exc
    segments = (parsed.netloc + parsed.path).split('/')
    if (not value.startswith('skill://') or parsed.scheme != 'skill' or parsed.geturl() != value
            or parsed.query or parsed.fragment
            or len(segments) < 2 or segments[-1] != 'SKILL.md' or segments[-2] != name
            or any(not _URI_SEGMENT.fullmatch(part) or part in ('.', '..') for part in segments)):
        raise ValueError('Skill URI must name its SKILL.md in a directory matching the skill name.')
    return value


def _relative_file(path: str) -> None:
    if (not path or path.startswith('/') or '\\' in path or '%' in path
            or any(ord(char) < 32 or ord(char) == 127 for char in path)
            or any(part in ('', '.', '..') for part in path.split('/')) or urlsplit(path).scheme):
        raise ValueError(f'Not a relative skill file: {path}.')


def _frontmatter(name: str, text: str, description: str) -> tuple[dict[str, Any], bytes]:
    lines = text.splitlines(keepends=True)
    if lines and lines[0].rstrip('\r\n') == '---':
        end = next((i for i, line in enumerate(lines[1:], 1) if line.rstrip('\r\n') == '---'), None)
        if end is None:
            raise ValueError('Skill YAML frontmatter has no closing delimiter.')
        try:
            fields = yaml.load(''.join(lines[1:end]), Loader=_SkillLoader)
        except (yaml.YAMLError, TypeError) as exc:
            raise ValueError('Invalid skill YAML frontmatter.') from exc
        if not isinstance(fields, dict):
            raise ValueError('Skill YAML frontmatter must be a mapping.')
        frontmatter = cast(dict[str, Any], fields)
        raw = text.encode('utf-8')
    else:
        frontmatter = {'name': name, 'description': description}
        raw = ('---\n' + yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False) + '---\n' + text).encode('utf-8')
    if frontmatter.get('name') != name:
        raise ValueError('Skill frontmatter name does not match the supplied name.')
    authored_description = frontmatter.get('description')
    if not isinstance(authored_description, str) or not authored_description.strip() or len(authored_description) > 1024:
        raise ValueError('Skill frontmatter requires a nonempty description of at most 1024 characters.')
    try:
        if json.loads(json.dumps(frontmatter, allow_nan=False)) != frontmatter:
            raise ValueError('Skill frontmatter must preserve its values as a JSON object.')
    except (TypeError, ValueError) as exc:
        raise ValueError('Skill frontmatter must contain JSON-compatible values.') from exc
    return frontmatter, raw


def document(name: str, text: str, description: str = '', files: Mapping[str, str | bytes] | None = None,
             uri: str | None = None) -> dict[str, Any]:
    """Build one SEP-2640 entry plus relative-path raw bytes, shared by the server and the skill layer.

    An authored SKILL.md is retained byte for byte. A plain body requires an explicit description and receives
    a YAML header without changing the body. No content is read from another skill or origin.
    """
    _valid_name(name)
    address = _skill_uri(name, uri)
    frontmatter, source = _frontmatter(name, text, description)
    held: dict[str, bytes] = {'SKILL.md': source}
    for path, value in (files or {}).items():
        _relative_file(path)
        raw = value.encode('utf-8') if isinstance(value, str) else value
        if path == 'SKILL.md' and raw != source:
            raise ValueError('Conflicting SKILL.md content in skill files.')
        held[path] = raw
    if len(held) > MAX_SKILL_FILES or sum(len(value) for value in held.values()) > MAX_SKILL_BYTES:
        raise ValueError('A skill may contain at most 512 files and 16 MiB of file content.')
    for path in held:
        if any(str(parent) in held for parent in PurePosixPath(path).parents if str(parent) != '.'):
            raise ValueError(f'Skill file is also used as a directory: {path}.')
    root = address.removesuffix('SKILL.md')
    manifest = [{'uri': root + quote(path, safe='/'), 'digest': 'sha256:' + hashlib.sha256(raw).hexdigest(),
                 'size': len(raw)} for path, raw in sorted(held.items())]
    return {'uri': address, 'frontmatter': frontmatter, 'resources': manifest, 'files': held}


def _reusable_root() -> Path:
    root = home.home() / 'skills'
    if root.is_symlink():
        raise ValueError('Reusable skill storage must not be a symbolic link.')
    return root


def publish(name: str, text: str, description: str = '',
            files: Mapping[str, str | bytes] | None = None) -> dict[str, Any]:
    """Publish a complete authored reusable skill in the Metaform home, replacing its prior file set."""
    bundle = document(name, text, description, files)
    authored = cast(dict[str, bytes], bundle['files'])
    root = _reusable_root()
    root.mkdir(parents=True, exist_ok=True)
    destination = root / name
    with home.file_lock(root / f'.{name}.lock'), TemporaryDirectory(prefix=f'.{name}-', dir=root) as temporary:
        if destination.is_symlink() or destination.exists() and not destination.is_dir():
            raise ValueError('A reusable skill must be stored in an ordinary directory.')
        staging = Path(temporary) / 'content'
        staging.mkdir()
        for relative, raw in authored.items():
            path = staging / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        previous = Path(temporary) / 'previous'
        if destination.exists():
            destination.replace(previous)
        try:
            staging.replace(destination)
        except OSError:
            if previous.exists():
                previous.replace(destination)
            raise
    return bundle


def reusable(name_or_uri: str) -> dict[str, Any] | None:
    """Read one authored reusable skill by exact name or canonical URI, without loading other origins."""
    name = name_or_uri
    if name_or_uri.startswith('skill:'):
        name = name_or_uri.removesuffix('/SKILL.md').removeprefix('skill://')
        _valid_name(name)
        if name_or_uri != _skill_uri(name, None):
            raise ValueError('Not an authored reusable skill URI.')
    else:
        _valid_name(name)
    root = _reusable_root()
    if not root.exists():
        return None
    with home.file_lock(root / f'.{name}.lock'):
        folder = root / name
        if folder.is_symlink():
            raise ValueError('A reusable skill directory must not be a symbolic link.')
        if not folder.exists():
            return None
        held: dict[str, bytes] = {}
        total = 0
        for path in sorted(folder.rglob('*')):
            if path.is_symlink():
                raise ValueError('Reusable skill files must not contain symbolic links.')
            if not path.is_file():
                continue
            relative = path.relative_to(folder).as_posix()
            _relative_file(relative)
            total += path.stat().st_size
            if len(held) >= MAX_SKILL_FILES or total > MAX_SKILL_BYTES:
                raise ValueError('A skill may contain at most 512 files and 16 MiB of file content.')
            held[relative] = path.read_bytes()
        if 'SKILL.md' not in held:
            raise ValueError(f'Reusable skill {name} has no SKILL.md.')
        try:
            text = held['SKILL.md'].decode('utf-8')
        except UnicodeDecodeError as exc:
            raise ValueError('SKILL.md must contain UTF-8 text.') from exc
        return document(name, text, files=held)


def reusable_catalog() -> list[dict[str, Any]]:
    """List complete reusable skill entries without returning their instruction bodies or supporting bytes."""
    root = _reusable_root()
    if not root.exists():
        return []
    entries: list[dict[str, Any]] = []
    for folder in sorted(root.iterdir()):
        if folder.name.startswith('.') or not folder.is_dir():
            continue
        bundle = reusable(folder.name)
        if bundle is not None:
            entries.append({key: bundle[key] for key in ('uri', 'frontmatter', 'resources')})
    return entries
