"""Read a module's declarations without running it, BASE-015.

`SUPPORTED_OS` and `DEPENDENCIES` are literal tuples or lists of strings,
`SHIPS_DISABLED` a literal boolean and `REQUIRES_CHASSIS` a literal string. The
module's `__init__.py`, and a `manifest.py` beside it, are parsed with `ast` and
never executed. A name assigned more than once, assigned a non-literal, or
defined any other way is an error naming the declaration.
"""
from __future__ import annotations

import ast
import platform
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SYSTEMS = ('linux', 'macos', 'windows')


def canonical(name: str) -> str:
    name = name.lower()
    return 'macos' if name == 'darwin' else name


def current_os() -> str:
    return canonical(platform.system())


@dataclass(frozen=True)
class Declared:
    supported_os: tuple[str, ...] | None
    dependencies: tuple[str, ...]
    ships_disabled: bool
    requires_chassis: str | None

    @property
    def compatible(self) -> bool:
        return self.supported_os is not None and current_os() in self.supported_os

    @property
    def reason(self) -> str | None:
        if self.supported_os is None:
            return 'SUPPORTED_OS is required'
        if not self.compatible:
            return (f'Unsupported operating system {current_os()}; '
                    f'SUPPORTED_OS declares {", ".join(self.supported_os)}')
        return None


def _defines(node: ast.AST, name: str) -> bool:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name == name
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
        return node.id == name
    if isinstance(node, ast.alias):
        return (node.asname or node.name.split('.')[0]) == name
    return any(_defines(child, name) for child in ast.iter_child_nodes(node))


def _literal(tree: ast.Module, source: Path, name: str, check: Any) -> Any:
    found: list[ast.stmt] = []
    for statement in tree.body:
        if isinstance(statement, ast.ImportFrom) and statement.level == 1 and statement.module == 'manifest':
            if any(alias.name == name for alias in statement.names):
                continue
        targets = (statement.targets if isinstance(statement, ast.Assign)
                   else [statement.target] if isinstance(statement, ast.AnnAssign) else [])
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            found.append(statement)
        elif _defines(statement, name):
            raise ValueError(f'{source.name}: {name} must be one top-level literal')
    if not found:
        return None
    value_node = getattr(found[0], 'value', None)
    if len(found) != 1 or value_node is None:
        raise ValueError(f'{source.name}: {name} must be one top-level literal')
    try:
        value = ast.literal_eval(value_node)
    except (ValueError, TypeError, SyntaxError) as error:
        raise ValueError(f'{source.name}: {name} must be one top-level literal') from error
    if not check(value):
        raise ValueError(f'{source.name}: {name} has the wrong type')
    return value


def _strings(value: Any) -> bool:
    return isinstance(value, (tuple, list)) and all(isinstance(item, str) for item in value)


def read(folder: Path) -> Declared:
    """The declarations of a module folder, or the package folder of an entry point."""
    entry = folder / '__init__.py'
    with tokenize.open(entry) as stream:
        tree = ast.parse(stream.read(), filename=str(entry))
    manifest_path = folder / 'manifest.py'
    manifest = None
    if manifest_path.is_file():
        with tokenize.open(manifest_path) as stream:
            manifest = ast.parse(stream.read(), filename=str(manifest_path))

    def declared(name: str, check: Any) -> Any:
        local = _literal(tree, entry, name, check)
        other = _literal(manifest, manifest_path, name, check) if manifest is not None else None
        if local is not None and other is not None and local != other:
            raise ValueError(f'{entry.name}: {name} differs from manifest.py')
        return other if other is not None else local

    systems = declared('SUPPORTED_OS', _strings)
    dependencies = declared('DEPENDENCIES', _strings) or ()
    ships_disabled = declared('SHIPS_DISABLED', lambda value: isinstance(value, bool)) or False
    requires = declared('REQUIRES_CHASSIS', lambda value: isinstance(value, str))
    return Declared(None if systems is None else tuple(canonical(name) for name in systems), tuple(dependencies),
                    ships_disabled, requires)
