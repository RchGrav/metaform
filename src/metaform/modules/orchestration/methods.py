"""Load a contribution's method without creating or transferring an assignment.

Discovery groups are descriptive. Any registered responsibility or expertise can
be read; the assignment and dispatch operations continue to own execution.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from metaform import prompt_files, skills
from metaform.module import Context, Stop, agent_context_collecting, prepare_agent_context, record_agent_context

from .state import SERVICE, service

# A family is one discovery entry, with methods selected separately when useful.
# These describe authored responsibilities, not authority or a closed specialty list.
FAMILIES = {
    'shape-work': ('interviewer', 'requirements', 'architect', 'designer', 'planner', 'decomposer'),
    'investigate-work': ('investigator', 'researcher', 'synthesizer'),
    'deliver-work': ('specialist', 'implementer', 'integrator', 'release'),
    'evaluate-work': ('verifier', 'reviewer', 'dogfood'),
}
RESPONSIBILITIES = ('triage', 'gc', 'functionality', 'harsh_critic', 'roundtable_follow_through')


def listing(ctx: Context) -> dict[str, Any]:
    """List methods without reading their bodies, changing duties or starting work."""
    return {'execution': {
                'current': 'Apply a method or expertise in the current conversation and assignment.',
                'continued': 'Continue related assigned work through an existing ACP episode.',
                'separate': 'Delegate for useful parallelism, requested independence or isolation.'},
            'families': [{'name': name, 'methods': list(names)} for name, names in FAMILIES.items()],
            'responsibilities': list(RESPONSIBILITIES),
            'expertise': {'entry': 'facilitator', 'read': 'orchestration_facilitate op=find'},
            'assignment': (SERVICE.assignment(ctx) or {}).get('assignment_id')}


def deliver(ctx: Context, components: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Use the existing content ledger and acknowledge only complete delivered bodies.

    MCP's collector checks response shaping before it records these snapshots.
    CLI output is the complete return, as with existing functional memory reads.
    """
    prepared = prepare_agent_context(ctx.folder, ctx.session, [dict(one) for one in components], project=ctx.project)
    due = cast(list[dict[str, Any]], prepared['components'])
    instructions: list[dict[str, Any]] = []
    for one in due:
        text = str(one.get('text') or '')
        one['delivered_value'] = text
        instructions.append({key: one[key] for key in (
            'name', 'text', 'actual_version_id', 'selected_version_id', 'source', 'reference', 'problems', 'notices')
            if key in one})
    epoch = int(prepared['epoch'])
    if ctx.surface == 'mcp' or agent_context_collecting():
        ctx.queue_context(due, epoch)
    else:
        record_agent_context(ctx.folder, ctx.session, due, project=ctx.project, epoch=epoch, channel='cli')
    return {'epoch': epoch, 'instructions': instructions,
            'unchanged': len(components) - len(due)}


def apply(ctx: Context) -> dict[str, Any]:
    """Apply exact selected instructions; session identity and ownership stay intact."""
    given = str(ctx.nouns['name'])
    name = given.removeprefix('metaform://role/')
    assigned = SERVICE.assignment(ctx)
    pinned = cast(dict[str, Any], (assigned or {}).get('role_snapshot') or {})
    skill = None
    if not given.startswith('metaform://role/'):
        try:
            skill = skills.get(name)
        except Stop:
            pass
    if skill is not None:
        selected = skills.components(skill.name)
        origin = 'selected_skill'
    else:
        if assigned and assigned.get('authored_role_uri') == f'metaform://role/{name}' and pinned:
            resolved = pinned
            origin = 'assignment_snapshot'
        else:
            resolved = service(ctx, 'agent.role').resolve(ctx, name)
            origin = 'selected_role'
        if resolved.get('missing') or resolved.get('problems'):
            raise Stop(f'Cannot read {name}: {resolved.get("problems") or "not registered"}.',
                       'metaform orchestration methods')
        selected = cast(list[dict[str, Any]], resolved.get('components') or [])
        # Supplemental technique does not silently replace the active assignment's shared instructions.
        shared = {one['name']: one for one in pinned.get('components', [])
                  if one['name'] in ('prompt.orchestration:common', 'prompt.orchestration:specialist')}
        selected = [shared.get(one['name'], one) for one in selected]
    frame = prompt_files.resolve('prompt.orchestration:apply_method')
    received = deliver(ctx, [frame, *selected])
    return {'execution': 'current', 'state': 'instructions_available', 'method': name, 'source': origin,
            'assignment': (assigned or {}).get('assignment_id'),
            'task': ctx.nouns.get('task'), **received}
