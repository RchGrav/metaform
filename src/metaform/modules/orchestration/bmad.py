"""Optional installed BMAD roles on the normal provider, prompt and managed-call paths.

The installed source is the authority for its activation and menu. This bridge
neither installs BMAD nor supplies a second scheduler or a copy of its roles.
"""
from __future__ import annotations

import csv
import hashlib
import re
import tomllib
from pathlib import Path
from typing import Any, cast

import yaml

from metaform.data import prompts
from metaform.module import AgentRoleDefinition, Context

BRIDGE = '''This assignment uses an installed BMAD specialty. Its source, source directory, installation metadata,
and exact source fingerprint accompany the duty. Follow the installed activation, menu and referenced resources;
resolve relative resources from that source directory and {project-root} from the recorded project folder.
The immediate caller's requested contribution and supplied menu selection are the input to that activation.
Do not stop to ask for a menu selection already supplied in the assignment. When an installed procedure needs
missing human input, record the actual requirement and retained work through the assignment's normal return or
blocker continuation. Return the contribution and evidence to the recorded caller.
Native C(T), mode, delivery ownership and user direction continue to apply. Any additional agent this procedure
needs uses the available managed specialist call so configured capacity and its return route remain effective.
An installed command, script or adapter capability that is unavailable is a reported limitation, never invented.
'''

SKILL_DIRECTORIES = ('.agents/skills', '.claude/skills', '.cline/skills', '.bob/skills', '.agent/skills', '.adal/skills')


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _name(value: str) -> str:
    return re.sub(r'[^A-Za-z0-9_.-]+', '_', value).strip('._-')


def _frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith('---\n'):
        return {}
    header, separator, _ = text[4:].partition('\n---')
    if not separator:
        return {}
    loaded = yaml.safe_load(header)
    return cast(dict[str, Any], loaded) if isinstance(loaded, dict) else {}


def _menu(text: str) -> str | None:
    xml = re.search(r'<menu(?:\s[^>]*)?>.*?</menu>', text, re.DOTALL)
    if xml:
        return xml.group()
    markdown = re.search(r'^#{1,4}\s+.*\bmenu\b[^\n]*\n.*?(?=^#{1,4}\s|\Z)',
                         text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
    return markdown.group().strip() if markdown else None


def _metadata(folder: Path, problems: list[str]) -> dict[str, Any]:
    for relative in ('_bmad/_config/manifest.yaml', '_bmad/config.toml'):
        path = folder / relative
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding='utf-8')
            loaded = tomllib.loads(text) if path.suffix == '.toml' else yaml.safe_load(text)
            data = cast(dict[str, Any], loaded) if isinstance(loaded, dict) else {}
            installation = data.get('installation')
            version = cast(dict[str, Any], installation).get('version') if isinstance(installation, dict) else None
            return {'file': str(path), 'fingerprint': _hash(text), 'version': version or data.get('version')}
        except (OSError, ValueError, yaml.YAMLError) as error:
            problems.append(f'{path}: {error}')
    return {'file': None, 'fingerprint': None, 'version': None}


def discover(ctx: Context) -> dict[str, Any]:
    """Read only known installed entry points on this project; nothing scans the user's home or starts a process."""
    folder = ctx.folder.resolve()
    problems: list[str] = []
    installation = _metadata(folder, problems)
    sources: list[tuple[str, str, Path, str]] = []
    manifest = folder / '_bmad/_config/agent-manifest.csv'
    if manifest.is_file():
        try:
            with manifest.open(encoding='utf-8-sig', newline='') as stream:
                for row in csv.DictReader(stream):
                    name, module, given = row.get('name') or '', row.get('module') or 'core', row.get('path') or ''
                    if not name or not given:
                        problems.append(f'{manifest}: an agent row needs name and path.')
                        continue
                    source = Path(given.replace('{project-root}', str(folder)))
                    if not source.is_absolute():
                        source = folder / source
                        if not source.is_file() and not given.startswith('_bmad/'):
                            source = folder / '_bmad' / given
                    sources.append((f'bmad.{_name(module)}.{_name(name)}',
                                    row.get('title') or row.get('role') or name, source, 'agent-manifest'))
        except (OSError, csv.Error) as error:
            problems.append(f'{manifest}: {error}')
    for relative in SKILL_DIRECTORIES:
        directory = folder / relative
        if directory.is_dir():
            for path in sorted(directory.glob('bmad-agent-*/SKILL.md')):
                name = path.parent.name.removeprefix('bmad-agent-')
                sources.append((f'bmad.skill.{_name(name)}', name, path, 'installed-skill'))
    roles: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for name, purpose, path, kind in sources:
        try:
            source = path.resolve()
            text = source.read_text(encoding='utf-8')
            fingerprint = _hash(text)
            if (name, fingerprint) in seen:
                continue
            seen.add((name, fingerprint))
            metadata = _frontmatter(text)
            roles.append({'name': name, 'purpose': metadata.get('description') or purpose,
                'source': str(source), 'source_directory': str(source.parent), 'source_fingerprint': fingerprint,
                'installed_version': installation['version'] or metadata.get('version'), 'installation': installation,
                'format': kind, 'menu': _menu(text), 'text': text, 'project_root': str(folder)})
        except (OSError, ValueError, yaml.YAMLError) as error:
            problems.append(f'{path}: {error}')
    return {'installed': bool(sources or (folder / '_bmad').is_dir()), 'roles': roles, 'problems': problems,
            'invocation': 'Installed duty supplied to a managed ACP assignment; its recorded task/menu is the input.',
            'limitations': [('Only project-local manifest and skill entry points are detected. Global/plugin-only '
                             'installations need their own public provider.'),
                            'Referenced BMAD scripts, menus and external tools retain their installed requirements.']}


def _definition(ctx: Context, record: dict[str, Any]) -> AgentRoleDefinition:
    project = _hash(f'{ctx.project}:{ctx.folder.resolve()}')[:16]
    source_id = _hash(record['source'])[:12]
    reference = f'prompt.orchestration:bmad_{project}_{record["name"]}_{source_id}'
    provenance = '\n'.join(f'{key}: {record[key]}' for key in (
        'source', 'source_directory', 'project_root', 'installed_version', 'source_fingerprint'))
    prompts.shipped('prompt.orchestration:bmad_bridge', 'text', BRIDGE)
    selected = prompts.shipped(reference, 'text', provenance + '\n\n' + record['text'])
    definition = AgentRoleDefinition(record['name'], str(record['purpose']),
                                     ('prompt.orchestration:common', 'prompt.orchestration:bmad_bridge', reference))
    record.update(uri=definition.uri, prompt=reference, selected_version_id=selected.version_id,
                  actual_version_id=selected.version_id, selected_origin=selected.origin,
                  rendered_fingerprint=_hash(selected.text), source_menu=record['menu'], menu=_menu(selected.text),
                  call={'verb': 'orchestration call', 'role': record['name'],
                        'task': 'The requested contribution, including its installed menu selection.'})
    return definition


def definitions(ctx: Context) -> tuple[AgentRoleDefinition, ...]:
    return tuple(_definition(ctx, record) for record in discover(ctx)['roles'])


def inspect(ctx: Context) -> dict[str, Any]:
    found = discover(ctx)
    for record in found['roles']:
        _definition(ctx, record)
    return {**found, 'roles': [{key: value for key, value in one.items() if key != 'text'} for one in found['roles']]}
