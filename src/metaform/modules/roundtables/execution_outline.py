"""Write the person's execution outline directly from the decomposed board."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from metaform.data import Store
from metaform.module import Context, Stop

FILE = 'execution-outline.md'


def write(ctx: Context, *, board: str, plan: str, project: str | None = None) -> dict[str, Any]:
    """Snapshot every ticket, including held and completed work, without asking an agent to summarize it."""
    source = ctx.require_store()
    root = Path(source.project().path).resolve()
    planned = (root / plan).resolve()
    if not planned.is_relative_to(root) or not planned.is_file():
        raise Stop('The saved plan is missing from this project.', 'read the saved plan before decomposition')
    target = planned.with_name(FILE)
    if target == planned:
        raise Stop('The plan and execution outline need separate files.', 'save the plan under its own filename')
    if target.is_symlink():
        raise Stop('The execution outline must be a project file.', 'remove the outline symlink')
    project_id = project or source.project_id
    base = source.bound_base() if project_id == source.project_id else None
    store = Store(project_id, base=base.id if base else None, module='map')
    with store.atomic(), store.tables(write=False) as tx:
        if not board or tx.get('boards', {'name': board}) is None:
            raise Stop('Decomposition needs a named board.', 'read the Decomposer board')
        settings = tx.rows('ticket_settings', {'board': board}, limit=0).results
        ids = [str(row['work_id']) for row in settings]
        records = store.work(ids=ids, limit=0).results
        numbers = store.numbers_of('work', ids)
        dependencies = {ident: tx.get('after', {'work_id': ident}) for ident in ids}
        ordered = sorted(records, key=lambda record: (record.position is None, record.position or 0,
                                                      record.created, record.id))
        tickets = [{'id': record.id, 'title': numbers.get(record.id, ('', '', ''))[1],
                    'depends_on': list((dependencies[record.id] or {}).get('works') or []),
                    'expected_outcome': record.task or ''} for record in ordered]
    snapshot = {'project': store.project_id, 'board': board, 'plan': planned.relative_to(root).as_posix(),
                'tickets': tickets}
    # JSON preserves multiline outcomes and exact identifiers without Markdown escaping or inference.
    body = '# Execution outline\n\n```json\n' + json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n```\n'
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(mode='w', encoding='utf-8', dir=target.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(body)
        temporary.replace(target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {'file': target.relative_to(root).as_posix(), **snapshot}
