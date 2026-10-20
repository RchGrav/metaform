"""Move a frozen run to an operative successor without losing its call/return state."""
from __future__ import annotations

import copy
import time
import uuid
from typing import Any, cast

from metaform.data import Column, Index, Store, Table, status
from metaform.module import Context, Stop

TABLE = Table('revisions', place='project', key=('change_id', 'previous_run'), columns=(
    Column('change_id', required=True), Column('previous_run', required=True),
    Column('successor_run', required=True), Column('address', required=True), Column('name', required=True),
    Column('revision', required=True), Column('created', required=True)),
    indexes=(Index(('successor_run',), unique=True),))


def revise(ctx: Context) -> dict[str, Any]:
    """One change creates one successor; original frames remain inspectable history.

    Active children now return to the successor and the original caller waits for
    that successor. Completed progress, local variables and genuine user pauses
    are carried unchanged; only the named frozen prompt receives its new content.
    """
    from .catalog import at_revision
    store = ctx.require_store()
    base = store.bound_base()
    owned = Store(store.project_id, module='workflow', base=None if base is None else base.id,
                  toggled=store.toggled)
    run_id, change_id = str(ctx.nouns['run']), str(ctx.nouns['change'])
    address, name = str(ctx.nouns['address']), str(ctx.nouns['name'])
    key = {'change_id': change_id, 'previous_run': run_id}
    successor = uuid.uuid5(uuid.NAMESPACE_URL, f'metaform:workflow:revision:{run_id}:{change_id}').hex
    timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    with owned.tables() as tx:
        existing = tx.get('revisions', key)
        if existing:
            return {'run': existing['successor_run'], 'previous_run': run_id, 'change_id': change_id,
                    'revision': existing['revision']}
        prompt = at_revision(owned, address, name, str(ctx.nouns['revision']), ctx.nouns.get('layer'))
        previous = tx.get('runs', {'run_id': run_id})
        seen: set[str] = set()
        while previous is not None and previous['state'] == 'cancelled' and previous.get('result'):
            result = previous['result']
            next_run = cast(dict[str, Any], result).get('successor') if isinstance(result, dict) else None
            if not next_run or str(next_run) in seen:
                break
            seen.add(str(next_run))
            previous = tx.get('runs', {'run_id': str(next_run)})
        if previous is None:
            raise Stop('The workflow continuation is unavailable.', 'metaform workflow runs')
        if previous['kind'] != 'call':
            raise Stop('This run is a skill assignment and holds no frozen workflow call.', 'metaform workflow runs')
        if previous['state'] not in status.OPEN:
            # A later assessment can adapt the specification after delivery. Completed execution is retained
            # as history; the next corrective assignment starts from the newly selected definition.
            return {'run': None, 'previous_run': previous['run_id'], 'change_id': change_id,
                    'revision': str(ctx.nouns['revision']), 'state': previous['state'], 'continuation': 'closed'}
        previous_id = previous['run_id']
        frames = copy.deepcopy(previous['frames'])
        matched = False
        changed = False
        for frame in frames:
            frozen = frame['call']
            if frozen['address'] == address and frozen['prompt']['prompt_id'] == prompt.prompt_id:
                changed = changed or frozen['prompt']['content'] != prompt.content
                frozen['prompt'] = prompt.to_dict()
                matched = True
        if not matched:
            raise Stop(f'Run {run_id} is not executing {address}.{name}.', f'metaform workflow resume run={run_id}')
        if previous_id != run_id and not changed:
            return {'run': previous_id, 'previous_run': run_id, 'change_id': change_id,
                    'revision': str(ctx.nouns['revision']), 'continuation': 'current'}
        made = {**previous, 'run_id': successor, 'frames': frames, 'created': timestamp, 'updated': timestamp,
                'seq': time.time_ns(), 'closed': None, 'result': None}
        tx.insert('runs', made)
        parent_id = previous.get('parent')
        if parent_id:
            parent = tx.get('runs', {'run_id': parent_id})
            if parent and parent['state'] in status.OPEN:
                waiting = [successor if one == previous_id else one
                           for one in cast(list[str], parent.get('waiting') or [])]
                branches = copy.deepcopy(parent.get('branches'))
                if branches and previous_id in branches:
                    branches[successor] = branches.pop(previous_id)
                    branches[successor]['call'] = copy.deepcopy(frames[-1]['call'])
                tx.update('runs', {'run_id': parent_id}, {'waiting': waiting, 'branches': branches,
                                                         'updated': timestamp})
        for child in tx.rows('runs', {'parent': previous_id}, limit=0).results:
            if child['state'] in status.OPEN:
                tx.update('runs', {'run_id': child['run_id']}, {'parent': successor, 'updated': timestamp})
        tx.update('runs', {'run_id': previous_id}, {'state': 'cancelled', 'closed': timestamp, 'updated': timestamp,
            'message': f'Superseded by {successor} for specification change {change_id}.',
            'result': {'successor': successor, 'change_id': change_id}})
        tx.insert('revisions', {**key, 'successor_run': successor, 'address': address, 'name': name,
                               'revision': str(ctx.nouns['revision']), 'created': timestamp})
        tx.concern(work_id=previous.get('ticket'), session_id=previous.get('session'), kind='workflow.revision')
    return {'run': successor, 'previous_run': run_id, 'change_id': change_id, 'revision': str(ctx.nouns['revision'])}
