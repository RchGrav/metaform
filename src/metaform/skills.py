"""Canonical skill folders, independent of the consuming harness, BASE-059.

The folder is the authored artifact. Libraries are resolved from the current
prompt store when read or deployed, never maintained as another source copy.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import PurePosixPath
from typing import Any, cast

import yaml

from . import prompt_files
from .data import prompts
from .errors import Stop

PACKAGE = resources.files('metaform') / 'skills'
PREFIX = 'ing.metaform.'
SECTIONS = ('axiom-language', 'metaform-system', 'namespace-rules', 'workflow-logic', 'metaform-tools',
            'delexicalization-rules')
LIBS = ('lib_axiom', 'lib_metaform', 'lib_workflow', 'lib_quality')


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


def seed() -> None:
    for section in SECTIONS:
        prompts.shipped(section, 'text', prompt_files.required(PACKAGE, section))


def library(name: str) -> str:
    if name not in LIBS:
        raise Stop(f'No skill library {name}.', 'metaform workflow libs')
    seed()
    fills: dict[str, str] = {}
    for section in SECTIONS:
        version = prompts.prompt_version(section)
        fills[section] = version.text
        fills[f'{section}-version'] = str(version.number)
    text = prompt_files.required(PACKAGE, name, **fills)
    edited = [section for section in SECTIONS if fills[section] in text
              and fills[section] != prompt_files.required(PACKAGE, section)]
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
    return {**_files(one.folder), **{f'references/{name}.md': (text + '\n').encode('utf-8')
                                   for name, text in libraries(one).items()}}


def load(name: str) -> dict[str, Any]:
    one = get(name)
    libs = libraries(one)
    files = [*_files(one.folder), *(f'references/{name}.md' for name in libs)]
    return {**one.metadata(), 'files': files, 'procedure': procedure(one.name), 'libs': libs}


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
