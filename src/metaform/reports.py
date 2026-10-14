"""Process feedback, intake reports and saved shapes: files in the home, one row each, BASE-045 and STORE-043.

The files live in `projects/<project id>/reports/` under the home, or in
`reports/` when no project is known, never in a project folder, STORE-001.
Each file of a project has one row in the `reports` table of the project's
active metaform, and a row with a layer is that layer's provenance ref. A
file is named `<run id>-report.md`, `<run id>-feedback.md` or
`<run id>-shape.txt`; a second write for the same run and kind appends a
section headed by its UTC time, so nothing is overwritten. Nothing an agent
submits here is refused for its content, BASE-044.
"""
from __future__ import annotations

import os
import re
import secrets
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import context, home, sqlite
from .data import Notice, Page, Report, Store, StoreError
from .errors import Stop

FILES = {'report': 'report.md', 'feedback': 'feedback.md', 'shape': 'shape.txt'}
NAME = re.compile(r'^[A-Za-z0-9._-]+-(report\.md|feedback\.md|shape\.txt)$')
KIND_OF = {suffix: kind for kind, suffix in FILES.items()}


_THREADS = threading.Lock()  # writers in this process; the file lock below keeps processes apart


def folder(project_id: str | None) -> Path:
    """Where a project's report files live, or the home's own reports folder when there is no project."""
    root = home.home()
    if project_id:
        folder = home.project_folder(project_id)
        if folder is not None:
            return folder / 'reports'
    return root / 'reports'


def run_id() -> str:
    """A run id for files that belong to no layer: the UTC time and six random hex characters."""
    return datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(3)


def write(project_id: str | None, run: str, kind: str, text: str, *, store: Store | None = None,
          layer: str | None = None) -> str:
    """Write one file, or append a section to it, and record its row. Returns the file name."""
    name = f'{run}-{FILES[kind]}'
    target = folder(project_id) / name
    home.mkdir_private(target.parent)
    with _THREADS, sqlite.file_lock(target) as stream:
        # Writes to one file take turns, so none replaces another: the first writes the text, each later one a
        # section. On Windows an append is not one step, so the lock is what keeps them apart, BASE-045.
        stream.seek(0, os.SEEK_END)
        stream.write((text if stream.tell() == 0 else f'\n\n## {home.now()}\n\n{text}').encode('utf-8'))
    if store is not None and hasattr(store, 'save_report'):
        store.save_report(name, run, kind, target.stat().st_size, layer)
    return name


def feedback(where: Path, text: str, *, layer: str | None = None, report: str | None = None,
             shape: str | None = None, project: str | None = None) -> dict[str, Any]:
    """Save feedback on the Metaform process, and a report and a shape when given, BASE-045."""
    project_id = context.project_for(where, project)
    store = Store(project_id) if project_id else None
    notices: list[Notice] = []
    layer_id: str | None = None
    if layer is not None:
        if store is None:
            notices.append(Notice('layer', f'There is no project here to hold layer {layer}; the files were saved '
                                           'without a layer.'))
        else:
            try:
                layer_id = store.layer_ref(layer).id
            except StoreError:
                notices.append(Notice('layer', f'No layer {layer} in this project; the files were saved without a '
                                               'layer.'))
    run = layer_id or run_id()
    files = [write(project_id, run, 'feedback', text, store=store, layer=layer_id)]
    for kind, given in (('report', report), ('shape', shape)):
        if given is not None:
            files.append(write(project_id, run, kind, given, store=store, layer=layer_id))
    return {'project': project_id, 'run': run, 'files': files, 'notices': notices}


def _loose(project_id: str | None) -> list[Report]:
    """The files of the home's reports folder, which has no store, read by their names, STORE-043."""
    found: list[Report] = []
    place = folder(project_id)
    if not place.is_dir():
        return found
    for path in sorted(place.iterdir(), key=lambda item: (item.stat().st_mtime, item.name)):
        match = NAME.fullmatch(path.name)
        if match is None or not path.is_file():
            continue
        stamp = datetime.fromtimestamp(path.stat().st_mtime, UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
        found.append(Report(path.name, path.name[:-len(match.group(1)) - 1], None, None, KIND_OF[match.group(1)],
                            stamp, path.stat().st_size))
    return found


def list_reports(where: Path, *, project: str | None = None, kind: str | None = None, layer: str | None = None,
                 limit: int = 500, after: str | None = None) -> Page[Report]:
    """The report, feedback and shape files for the folder's project, or the home's when it has none."""
    project_id = context.project_for(where, project)
    store = Store(project_id) if project_id is not None else None
    if store is not None and hasattr(store, 'save_report'):
        return store.reports(kind, layer, limit=limit, after=after)
    rows = tuple(row for row in _loose(project_id) if kind is None or row.kind == kind)
    start = int(after or 0)
    end = start + limit if limit else len(rows)
    return Page(rows[start:end], str(end) if end < len(rows) else None)


def read_report(where: Path, name: str, *, project: str | None = None) -> str:
    """One file's text exactly. Only a listed report is read; a path is never followed."""
    project_id = context.project_for(where, project)
    missing = Stop(f'No report {name}.', 'metaform list reports')
    if Path(name).name != name or NAME.fullmatch(name) is None:
        raise missing
    store = Store(project_id) if project_id is not None else None
    if store is not None and hasattr(store, 'save_report') and store.report(name) is None:
        raise missing
    target = folder(project_id) / name
    if not target.is_file():
        raise missing
    return target.read_bytes().decode('utf-8')
