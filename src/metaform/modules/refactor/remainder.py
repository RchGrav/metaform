"""Launch ordinary, durable work for code classifications left to the reasoning agent."""
from __future__ import annotations

from dataclasses import replace
from importlib import resources
from typing import Any, cast

from metaform import prompt_files
from metaform.data import Store
from metaform.module import Context, Stop, call, context, surface


def _invoke(ctx: Context, module: str, verb: str, **nouns: Any) -> dict[str, Any]:
    found = next((one for one in surface(ctx.folder) if one.id == module), None)
    operation = next((one for one in found.verbs if one.name == verb), None) if found else None
    if operation is None:
        raise Stop(f'{module} {verb} is unavailable.', f'metaform enable {module}')
    invoked = context(module, ctx.folder, project=ctx.project, nouns=nouns, surface=ctx.surface,
                      client=ctx.client, session=ctx.session)
    bound = ctx.require_store().bound_base()
    if bound is not None:
        invoked.store = Store(ctx.require_store().project_id, base=bound.id, module=module)
    return cast(dict[str, Any], call(operation.run, invoked))


def start_remainder(ctx: Context, run_id: str, *, base_id: str, node: str = 'code') -> dict[str, Any]:
    """Reuse the run's ticket and start a normal worker, retaining waiting work when dispatch is unavailable."""
    current = ctx.require_store()
    active = current.active_base()
    if active is None or active.id != base_id:
        return {'state': 'waiting', 'run': run_id, 'base': base_id,
                'reason': 'The intake base is no longer active. Activate it to continue its remainder.'}
    store = Store(current.project_id, base=base_id)
    ctx = replace(ctx, store=store)
    marker = f'refactor remainder: {run_id}'
    work_id: str | None = None
    try:
        with store.atomic():
            ticket = next((one for one in store.work(limit=0).results if one.note == marker), None)
            if ticket is None:
                task = prompt_files.required(resources.files('metaform.modules.refactor'), 'remainder',
                                             run=run_id, base=base_id, project=store.project_id)
                _invoke(ctx, 'map', 'work', op='add', node=node, title='Place remaining code',
                        task=task, note=marker)
                ticket = next((one for one in store.work(limit=0).results if one.note == marker), None)
                if ticket is None:
                    raise Stop('The remainder ticket was not recorded.', 'metaform map work')
            work_id = ticket.id
        if ticket.done:
            return {'state': 'completed', 'work_id': work_id, 'run': run_id}
        sessions = _invoke(ctx, 'dispatch', 'sessions', id=work_id, thread=False)
        live = next((row for row in sessions.get('sessions', []) if row.get('state') == 'running'), None)
        if live is not None:
            return {**live, 'run': run_id, 'work_id': work_id}
        if ticket.taken:
            return {'state': 'waiting', 'run': run_id, 'work_id': work_id,
                    'reason': 'The remainder ticket is already reserved or being worked.'}
        agents = _invoke(ctx, 'dispatch', 'agents')
        if agents.get('room', 0) <= 0:
            return {'state': 'waiting', 'run': run_id, 'work_id': work_id,
                    'reason': 'No agent slot is available.'}
        active = current.active_base()
        if active is None or active.id != base_id:
            return {'state': 'waiting', 'run': run_id, 'work_id': work_id,
                    'reason': 'The active base changed before the remainder could start.'}
        started = _invoke(ctx, 'dispatch', 'start', id=work_id, agent=agents['default'])
        return {**started, 'run': run_id, 'work_id': work_id}
    except (Stop, OSError) as error:
        return {'state': 'waiting', 'run': run_id, 'work_id': work_id, 'reason': str(error)}
