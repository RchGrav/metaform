"""The repository wheel's dependencies: the chassis's own, then every shipped module's, BASE-022 and BASE-041.

The repository wheel carries every repo module, so it must require what each of them declares, or an installed
release carries a module it cannot run. A module's requirements live only in its own `DEPENDENCIES` literal,
read without running the module, BASE-015, so this hook reads them with the chassis's own reader.
"""
from __future__ import annotations

import importlib.util
import sys
import tomllib
from pathlib import Path
from typing import Any

from hatchling.metadata.plugin.interface import MetadataHookInterface


def _reader(root: Path) -> Any:
    path = root / 'src' / 'metaform' / 'module_metadata.py'
    spec = importlib.util.spec_from_file_location('_metaform_build_module_metadata', path)
    assert spec is not None and spec.loader is not None
    reader = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = reader  # dataclasses looks its module up while the file runs
    spec.loader.exec_module(reader)
    return reader


def requirements(root: Path) -> list[str]:
    """`[tool.metaform] chassis-dependencies`, then each module folder's `DEPENDENCIES` by module id, duplicates
    removed, the order `metaform build` writes."""
    project = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))
    ordered = list(project['tool']['metaform']['chassis-dependencies'])
    reader = _reader(root)
    modules = root / 'src' / 'metaform' / 'modules'
    for folder in sorted(modules.iterdir(), key=lambda item: item.name):
        if folder.is_dir() and (folder / '__init__.py').is_file():
            for requirement in reader.read(folder).dependencies:
                if requirement not in ordered:
                    ordered.append(requirement)
    return ordered


class ModuleDependencies(MetadataHookInterface):
    def update(self, metadata: dict[str, Any]) -> None:
        metadata['dependencies'] = requirements(Path(self.root))
