"""Repository files and template versions. No source checkout of the chassis is needed."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import tokenize
import tomllib
from importlib import resources
from pathlib import Path
from typing import Any, cast

from metaform import home
from metaform.module import Stop, chassis_version

IDENTIFIER = re.compile(r'^[a-z][a-z0-9_-]*$')
SYSTEMS = ('linux', 'macos', 'windows')
PYTHONS = ('3.11', '3.14')


def template_changelog() -> str:
    return template_root().joinpath('CHANGELOG.md').read_text(encoding='utf-8')


def template_root() -> Any:
    source = resources.files('metaform').joinpath('modules/template')
    if source.joinpath('__init__.py').is_file():
        return source
    return resources.files(__package__ or 'metaform.modules.fork').joinpath('resources/template')


def dependencies(folder: Path) -> list[str]:
    """Read the module's literal dependency declaration without executing its initializer."""
    def defines(node: ast.AST) -> bool:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return node.name == 'DEPENDENCIES'
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            return node.id == 'DEPENDENCIES'
        if isinstance(node, ast.alias):
            return (node.asname or node.name.split('.')[0]) == 'DEPENDENCIES'
        return any(defines(child) for child in ast.iter_child_nodes(node))

    def declaration(path: Path) -> list[str] | tuple[str, ...] | None:
        with tokenize.open(path) as stream:
            tree = ast.parse(stream.read(), filename=str(path))
        found: list[ast.Assign | ast.AnnAssign] = []
        for statement in tree.body:
            if (isinstance(statement, ast.ImportFrom) and statement.level == 1 and statement.module == 'manifest'
                    and any(alias.name == 'DEPENDENCIES' for alias in statement.names)):
                continue
            targets = (statement.targets if isinstance(statement, ast.Assign)
                       else [statement.target] if isinstance(statement, ast.AnnAssign) else [])
            if any(isinstance(target, ast.Name) and target.id == 'DEPENDENCIES' for target in targets):
                assert isinstance(statement, (ast.Assign, ast.AnnAssign))
                found.append(statement)
            elif defines(statement):
                raise ValueError(f'{path.name}: DEPENDENCIES must be one top-level literal')
        if not found:
            return None
        if len(found) != 1 or found[0].value is None:
            raise ValueError(f'{path.name}: DEPENDENCIES must be one top-level literal')
        value = ast.literal_eval(found[0].value)
        if not isinstance(value, (tuple, list)):
            raise TypeError('DEPENDENCIES must be a literal list or tuple of requirements')
        declared = cast(list[object] | tuple[object, ...], value)
        if any(not isinstance(item, str) for item in declared):
            raise ValueError('DEPENDENCIES must contain requirement strings')
        return cast(list[str] | tuple[str, ...], declared)

    local = declaration(folder / '__init__.py')
    manifest = folder / 'manifest.py'
    other = declaration(manifest) if manifest.is_file() else None
    if local is not None and other is not None and local != other:
        raise ValueError('__init__.py: DEPENDENCIES differs from manifest.py')
    return list(other if other is not None else local or ())


def entries(text: str) -> list[tuple[str, str]]:
    """Only released changelog entries are comparable; Unreleased has no ordered version."""
    matches = list(re.finditer(r'^## ([0-9]+(?:\.[0-9]+)+)\s*$', text, re.MULTILINE))
    return [(match[1], text[match.start():matches[index + 1].start() if index + 1 < len(matches) else len(text)].strip())
            for index, match in enumerate(matches)]


def version(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split('.'))


def template_version(folder: Path) -> str:
    readme = folder / 'README.md'
    if not readme.is_file():
        raise Stop(f'{folder.name} has no README with a Template version.', 'metaform help fork upkeep')
    section = re.search(r'^## Template version\s*\n(.*?)(?=^## |\Z)',
                        readme.read_text(encoding='utf-8'), re.MULTILINE | re.DOTALL)
    match = re.search(r'\b[0-9]+(?:\.[0-9]+)+\b', section[1]) if section else None
    if match is None:
        raise Stop(f'{folder.name} has no numeric Template version.', 'metaform help fork upkeep')
    return match[0]


def modules(root: Path) -> list[Path]:
    """Immediate module folders only, in deterministic order, with no files reached through symlinks."""
    found = [item for item in sorted(root.iterdir()) if item.is_dir() and (item / '__init__.py').is_file()]
    for item in found:
        if not IDENTIFIER.fullmatch(item.name):
            raise Stop(f'{item.name} is not a module identifier.', 'metaform help fork init')
        if item.is_symlink() or any(path.is_symlink() for path in item.rglob('*')):
            raise Stop(f'{item.name} contains a symlink; its wheel must carry repository files.',
                       'metaform help fork wheel')
    if not found:
        raise Stop(f'{root} holds no module folders.', 'metaform help fork init')
    return found


def is_repository(root: Path) -> bool:
    """The scaffold's explicit marker distinguishes module repositories from unrelated registered projects."""
    try:
        config = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return False
    for key in ('tool', 'metaform', 'fork'):
        section = config.get(key)
        if not isinstance(section, dict):
            return False
        config = cast(dict[str, Any], section)
    return config.get('repository') is True


def files(folder: Path) -> list[Path]:
    return [item for item in sorted(folder.rglob('*')) if item.is_file()
            and not any(part in ('__pycache__', '.pytest_cache', '.ruff_cache', '.git')
                        for part in item.relative_to(folder).parts) and item.suffix not in ('.pyc', '.pyo')]


def digest(folder: Path) -> str:
    """Bind checks and review to both paths and bytes, including the module's behavior tests."""
    hashed = hashlib.sha256()
    for item in files(folder):
        name = item.relative_to(folder).as_posix().encode()
        data = item.read_bytes()
        hashed.update(len(name).to_bytes(8, 'big') + name + len(data).to_bytes(8, 'big') + data)
    return hashed.hexdigest()


def resource(name: str) -> str:
    return resources.files(__package__ or 'metaform.modules.fork').joinpath('resources', name).read_text(encoding='utf-8')


def _mkdir(path: Path, *, exist_ok: bool = False) -> None:
    if home.is_home_path(path):
        home.mkdir_private(path.parent)
        path.mkdir(mode=0o700, exist_ok=exist_ok)
    else:
        path.mkdir(parents=True, exist_ok=exist_ok)


def _write(path: Path, content: str | bytes) -> None:
    if home.is_home_path(path):
        home.write_private(path, content)
    elif isinstance(content, str):
        path.write_text(content, encoding='utf-8')
    else:
        path.write_bytes(content)


def init(root: Path, name: str, agent: str, secret: str) -> dict[str, str]:
    """Scaffold into a new or empty directory, never overwrite a user's existing repository."""
    if not IDENTIFIER.fullmatch(name):
        raise Stop(f'{name} is not a module identifier.', 'metaform help fork init')
    if not re.fullmatch(r'[A-Z][A-Z0-9_]*', secret):
        raise Stop('The CI secret name must be an uppercase environment variable name.', 'metaform help fork init')
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise Stop(f'{root} is not an empty folder; no files were changed.', 'metaform help fork init')
    _mkdir(root, exist_ok=True)
    target = root / name
    source = template_root()
    def copy(item: Any, destination: Path) -> None:
        if item.is_dir():
            _mkdir(destination, exist_ok=True)
            for child in item.iterdir():
                # Template's tests check the shipped hello/template pair in the chassis repository.
                if child.name not in ('tests', '__pycache__', '.github'):
                    copy(child, destination / child.name)
        else:
            _write(destination, item.read_bytes())
    copy(source, target)
    entry = target / '__init__.py'
    _write(entry, entry.read_text(encoding='utf-8').replace("id='template'", f"id='{name}'"))
    prompt_file = target / 'resources' / 'prompts.xml'
    _write(prompt_file, prompt_file.read_text(encoding='utf-8').replace('template', name))
    _mkdir(target / 'tests')
    _write(target / 'tests' / 'README.md', 'Add tests of this module\'s requirements before implementing them.\n')
    releases = entries(template_changelog())
    if releases:
        readme = target / 'README.md'
        _write(readme, re.sub(r'(## Template version\s*\n).*?(?=\n## )',
                             lambda match: match[1] + releases[0][0] + '\n',
                             readme.read_text(encoding='utf-8'), count=1, flags=re.DOTALL))
    workflow = root / '.github' / 'workflows' / 'metaform.yml'
    _mkdir(workflow.parent)
    _write(workflow, resource('metaform.yml').replace('@AGENT@', agent).replace('@SECRET@', secret))
    _write(root / 'pyproject.toml', resource('project.toml.template').replace('@VERSION@', chassis_version()))
    _write(root / 'README.md', resource('repository.md').replace('@SECRET@', secret).replace('@AGENT@', agent))
    _write(root / '.gitignore', '.venv/\n.metaform/\ndist/\n__pycache__/\n.pytest_cache/\n.ruff_cache/\n')
    return {'repository': str(root), 'module': name, 'secret': secret}


def save_report(path: Path, data: dict[str, Any]) -> None:
    _mkdir(path.parent, exist_ok=True)
    _write(path, json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def copy_module(source: Path, target: Path) -> None:
    ignore = shutil.ignore_patterns('__pycache__', '.pytest_cache', '.ruff_cache', '.git')
    if home.is_home_path(target):
        _mkdir(target)
        ignored = ignore(str(source), [entry.name for entry in source.iterdir()])
        for entry in source.iterdir():
            if entry.name in ignored:
                continue
            if entry.is_dir():
                copy_module(entry, target / entry.name)
            else:
                home.write_private(target / entry.name, entry.read_bytes())
    else:
        shutil.copytree(source, target, ignore=ignore)


def update_worktree(root: Path, work_id: str) -> Path:
    """A separate branch per upkeep ticket, retained until its PR is completed or resumed."""
    target = root / '.metaform' / 'upkeep' / work_id
    if (target / '.git').is_file():
        return target
    def git(*args: str) -> str:
        try:
            result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True,
                                    encoding='utf-8', timeout=60, check=False,
                                    umask=0o077 if os.name != 'nt' and home.is_home_path(target) else -1)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise Stop(f'Template upkeep cannot prepare its branch: {error}.', 'metaform help fork upkeep') from None
        if result.returncode:
            raise Stop(f'Template upkeep cannot prepare its branch: {result.stderr.strip()}.',
                       'metaform help fork upkeep')
        return result.stdout.strip()
    if git('status', '--porcelain'):
        raise Stop('Commit your module repository changes before template upkeep.', 'metaform help fork upkeep')
    _mkdir(target.parent, exist_ok=True)
    git('worktree', 'add', '-b', f'metaform-template-{work_id}', str(target), 'HEAD')
    return target
