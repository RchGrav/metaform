"""The wheel and sdist build's step for the MCP Apps map view, MCP-037: the view is in every package built from here.

`src/metaform/modules/mcp/resources/views/map.html` is built from the web GUI's page by scripts/build_map_view.mjs and
not kept in git, so a package built from a checkout would lack it, and every AI tool that shows MCP Apps would get the
node view in its place. Before a wheel or sdist is built, this checks that the view is there and made of the files
beside it, as the MCP server checks it (`views.current`); when it is not, it builds it with Node.js. An sdist carries
the view it built, so a wheel built from that sdist needs no Node.js.

An editable install, `uv sync`, reads the view from the checkout and is left alone. Where Node.js or the build's
packages (`npm --prefix scripts ci`) are missing, the build goes on without the view and says so, so a source install
on a machine without Node.js still works; with `METAFORM_BUILD_VIEWS=1`, as a release and CI set it, it installs the
packages itself and a view it cannot build fails the build.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

REQUIRED = 'METAFORM_BUILD_VIEWS'


def _views(root: Path) -> Any:
    """The mcp module's views.py, read on its own: it imports nothing but the standard library."""
    path = root / 'src' / 'metaform' / 'modules' / 'mcp' / 'views.py'
    spec = importlib.util.spec_from_file_location('_metaform_build_views', path)
    assert spec is not None and spec.loader is not None
    views = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = views
    spec.loader.exec_module(views)
    return views


def current(root: Path) -> bool:
    """Whether the checkout's map view is built and made of the files beside it."""
    views = _views(root)
    view = root / 'src' / 'metaform' / 'modules' / 'mcp' / 'resources' / 'views' / views.BUILT
    said = views.recorded(view) if view.is_file() else None
    return said is not None and views.current(said, root / 'src' / 'metaform' / 'modules') is True


class MapView(BuildHookInterface):
    PLUGIN_NAME = 'custom'

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        if self.target_name == 'wheel' and version == 'editable':
            return
        root = Path(self.root)
        if not (root / 'scripts' / 'build_map_view.mjs').is_file() or current(root):
            return  # a package built from an sdist: the view came with it, or this is no checkout
        required = os.environ.get(REQUIRED) == '1'
        node, npm = shutil.which('node'), shutil.which('npm')
        scripts = root / 'scripts'
        if required and npm and not (scripts / 'node_modules' / 'esbuild').is_dir():
            subprocess.run([npm, '--prefix', str(scripts), 'ci'], check=True)
        if node and (scripts / 'node_modules' / 'esbuild').is_dir():
            subprocess.run([node, str(scripts / 'build_map_view.mjs')], check=True, cwd=root)
            if current(root):
                return
        said = ('The MCP Apps map view is not built, so this package serves the node view in its place. Install '
                'Node.js 20 or newer, run npm --prefix scripts ci, and build again.')
        if required:
            raise RuntimeError(f'{said} ({REQUIRED}=1 asks for it.)')
        self.app.display_warning(said)
