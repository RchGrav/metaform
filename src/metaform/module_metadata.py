"""Read module platform declarations without executing their entrypoint."""
import ast
from pathlib import Path
import platform
import tokenize


class UnsupportedPlatformError(ValueError):
    """A module explicitly excludes this operating system."""


def _canonical(name):
    name = name.lower()
    return 'macos' if name == 'darwin' else name


def current_os():
    return _canonical(platform.system())


def _declares(node, name):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name == name
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
        return node.id == name
    if isinstance(node, ast.alias):
        return (node.asname or node.name) == name
    return any(_declares(child, name) for child in ast.iter_child_nodes(node))


def _literal(tree, entry, name, *, manifest=False):
    declarations = []
    for statement in tree.body:
        if (manifest and isinstance(statement, ast.ImportFrom)
                and statement.level == 1 and statement.module == 'manifest'
                and any(alias.name == name and alias.asname in {None, name} for alias in statement.names)):
            continue
        targets = (statement.targets if isinstance(statement, ast.Assign)
                   else [statement.target] if isinstance(statement, (ast.AnnAssign, ast.AugAssign)) else [])
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            declarations.append(statement)
        elif _declares(statement, name):
            raise ValueError(f'{entry}: {name} must be a top-level literal tuple or list of strings')
    value = None
    if declarations:
        message = f'{entry}: {name} must be one literal tuple or list of strings'
        if len(declarations) != 1 or isinstance(declarations[0], ast.AugAssign):
            raise ValueError(message)
        try:
            value = ast.literal_eval(declarations[0].value)
        except (ValueError, TypeError, SyntaxError) as error:
            raise ValueError(message) from error
        if not isinstance(value, (tuple, list)) or not all(isinstance(name, str) for name in value):
            raise ValueError(message)
    return value



def read(source):
    """Read literal metadata from a file or a package's entrypoint/manifest.py.

    SUPPORTED_OS is required. A module without it is not compatible and is not loaded.
    Invalid declarations raise ValueError; no module code is imported or executed.
    """
    source = Path(source)
    entry = source / '__init__.py' if source.is_dir() else source
    with tokenize.open(entry) as stream:
        tree = ast.parse(stream.read(), filename=str(entry))
    manifest = entry.parent / 'manifest.py' if entry.name == '__init__.py' else None
    manifest_tree = None
    if manifest is not None and manifest.is_file():
        with tokenize.open(manifest) as stream:
            manifest_tree = ast.parse(stream.read(), filename=str(manifest))
    def declaration(name):
        local = _literal(tree, entry, name, manifest=manifest_tree is not None)
        declared = _literal(manifest_tree, manifest, name) if manifest_tree is not None else None
        if local is not None and declared is not None and local != declared:
            raise ValueError(f'{entry}: {name} conflicts with manifest.py')
        return declared if declared is not None else local
    declared = declaration('SUPPORTED_OS')
    supported_os = None if declared is None else [_canonical(name) for name in declared]
    dependencies = declaration('DEPENDENCIES') or []
    operating_system = current_os()
    compatible = supported_os is not None and operating_system in supported_os
    reason = None
    if supported_os is None:
        reason = 'SUPPORTED_OS is required'
    elif not compatible:
        reason = f'Unsupported operating system {operating_system}; SUPPORTED_OS declares {supported_os!r}'
    return {'supported_os': supported_os, 'compatible': compatible, 'compatibility_reason': reason, 'dependencies': list(dependencies)}


def supported(source):
    return read(source)['compatible']
