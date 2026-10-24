"""Canonical skill folders, independent of the consuming harness, BASE-059.

The folder is the authored artifact. Libraries are resolved from the current
prompt store when read or deployed, never maintained as another source copy.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Hashable, Mapping
from dataclasses import dataclass
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Any, cast
from urllib.parse import quote, urlsplit

import yaml

from . import home, prompt_files
from .data import prompts
from .errors import Stop

PACKAGE = resources.files('metaform') / 'skills'
PREFIX = 'ing.metaform.'
SECTIONS = ('axiom-language', 'metaform-system', 'namespace-rules', 'workflow-prompt', 'metaform-tools',
            'delexicalization-rules')
LIBS = ('lib_axiom', 'lib_metaform', 'lib_workflow', 'lib_quality')
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
    """Build one SEP-2640 entry plus relative-path raw bytes, shared by server and expertise storage.

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


@dataclass(frozen=True)
class Skill:
    name: str
    address: str
    description: str
    discover: bool
    version: str
    tier: str
    requires: tuple[str, ...]
    folder: Traversable

    def metadata(self) -> dict[str, Any]:
        return {'name': self.name, 'address': self.address, 'description': self.description,
                'discover': self.discover, 'version': self.version, 'tier': self.tier,
                'requires': list(self.requires)}


def catalog() -> list[Skill]:
    """Read authored metadata from the same folders deployed to native harnesses."""
    held: list[Skill] = []
    for folder in sorted(PACKAGE.iterdir(), key=lambda item: item.name):
        if not folder.is_dir() or not (folder / 'SKILL.md').is_file():
            continue
        lines = (folder / 'SKILL.md').read_text(encoding='utf-8').splitlines()
        frontmatter = '\n'.join(lines[1:lines.index('---', 1)])
        fields = cast(dict[str, Any], yaml.safe_load(frontmatter))
        metadata = cast(dict[str, str], fields['metadata'])
        held.append(Skill(fields['name'], metadata[PREFIX + 'address'], fields['description'],
                          metadata[PREFIX + 'discover'] == 'true', metadata[PREFIX + 'version'],
                          metadata[PREFIX + 'tier'], tuple(metadata[PREFIX + 'requires'].split()), folder))
    return held


def get(name: str) -> Skill:
    """The unversioned Address, kebab name or legacy underscore name names one skill."""
    normalized = name.replace('_', '-')
    for one in catalog():
        if normalized in (one.name, one.address):
            return one
    raise Stop(f'No skill {name}.', 'call metaform_skills with op=list')


def listing(*, discoverable: bool = False) -> list[dict[str, Any]]:
    return [one.metadata() for one in catalog() if not discoverable or one.discover]


def procedure(name: str) -> str:
    return (get(name).folder / 'references' / 'procedure.axiom').read_text(encoding='utf-8').strip()


def selected_procedure(name: str) -> str:
    """The selected procedure for a read or deployment; resolving an artifact is not an agent delivery receipt."""
    one = get(name)
    return str(prompt_files.resolve_text(prompt_files.address('skill', one.name), procedure(one.name))['text'])


def seed() -> None:
    for section in SECTIONS:
        name = prompt_files.address('skills', section)
        prompt_files.resolve(name)


def library(name: str) -> str:
    if name not in LIBS:
        raise Stop(f'No skill library {name}.', 'metaform workflow libs')
    seed()
    fills: dict[str, str] = {}
    for section in SECTIONS:
        version = prompts.prompt_version(prompt_files.address('skills', section))
        fills[section] = prompt_files.rendered(version.text) if version.format == 'xml' else version.text
        fills[f'{section}-version'] = str(version.number)
    text = prompt_files.required(PACKAGE, name, **fills)
    edited = [section for section in SECTIONS if fills[section] in text
              and fills[section] != prompt_files.rendered(prompt_files.shipped('skills', section) or '')]
    return text + (f'\n\nServed from an edit in the prompt store in place of the shipped text: {", ".join(edited)}.'
                   if edited else '')


def libraries(one: Skill) -> dict[str, str]:
    return {name: library(name) for name in one.requires}


def _files(folder: Traversable, prefix: str = '') -> dict[str, bytes]:
    held: dict[str, bytes] = {}
    for item in sorted(folder.iterdir(), key=lambda item: item.name):
        name = prefix + item.name
        if item.is_dir():
            held.update(_files(item, name + '/'))
        elif item.is_file():
            held[name] = item.read_bytes()
    return held


def deployment_files(one: Skill) -> dict[str, bytes]:
    return {**_files(one.folder), 'references/procedure.axiom': (selected_procedure(one.name) + '\n').encode('utf-8'),
            **{f'references/{name}.md': (text + '\n').encode('utf-8')
                                   for name, text in libraries(one).items()}}


def native_document(one: Skill) -> dict[str, Any]:
    """The packaged skill and its current libraries in the shared resource representation."""
    files = deployment_files(one)
    return document(one.name, files['SKILL.md'].decode('utf-8'), files=files,
                    uri=f'skill://metaform/{one.name}/SKILL.md')


def load(name: str) -> dict[str, Any]:
    one = get(name)
    libs = libraries(one)
    files = [*_files(one.folder), *(f'references/{name}.md' for name in libs)]
    return {**one.metadata(), 'files': files, 'procedure': selected_procedure(one.name), 'libs': libs}


def bound(given: str) -> str:
    """An input given to a skill, wrapped as data so it is not read as instructions."""
    return prompt_files.served(PACKAGE, 'assignment_input', input=given)


def served(name: str, given: str | None = None) -> str:
    """A skill whole, for an agent already connected: its current libs, the procedure and the input bound as data,
    with no run record. Workflow serve gives it, and dispatch sends it as the sentinel's first turn without workflow."""
    one = get(name)
    # Serve the store's selected version, STORE-044.
    skill = prompt_files.served_text(prompt_files.address('skill', one.name), procedure(one.name))
    return prompt_files.served(PACKAGE, 'served', libs='\n\n'.join(libraries(one).values()),
                               skill=skill, input=bound(given) if given else '')


def read(name: str, path: str) -> str:
    """Only files in this skill, including its current libraries, are readable."""
    one = get(name)
    relative = PurePosixPath(path)
    if relative.is_absolute() or '..' in relative.parts or '\\' in path:
        raise Stop(f'Not a skill file: {path}.', f'call metaform_skills with op=load name={one.address}')
    files = deployment_files(one)
    if path not in files:
        raise Stop(f'No file {path} in skill {one.name}.',
                   f'call metaform_skills with op=load name={one.address}')
    return files[path].decode('utf-8')
