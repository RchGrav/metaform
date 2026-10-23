"""Assignment-time runtime decisions over the installed agents' advertised choices."""
from __future__ import annotations

import difflib
import json
import math
from collections.abc import Mapping
from importlib import resources
from typing import Any, cast

from metaform import jev, prompt_files, settings
from metaform.data import WorkRecord
from metaform.module import Context

TASKS = {
    'planning': 'Build a concrete specification, plan, goal, tickets or their order.',
    'needs_plan': 'Develop a separate planning contribution for cross-workstream dependencies or consequential unresolved decisions.',
    'frontend': 'Write code for front-end visual polish or interaction presentation.',
    'coding': 'Implement requested behavior, resolving local design and verification details within the contribution.',
    'lookup': 'Research, collect information, look up documentation or perform a quick check for another agent.',
    'routing': 'Check status, route messages, move raw data or apply simple formatting without writing code.',
    'analysis': 'Investigate a complex problem, design architecture or solve a novel multi-step problem.',
    'writing': 'Write ordinary non-coding content or provide standard technical analysis.',
}
def choose(ctx: Context, record: WorkRecord | Mapping[str, Any], catalog: Mapping[str, Any],
           fallback: Mapping[str, Any] | None = None,
           overrides: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
    """Choose with Jev, or validate the Facilitator's supplied full-model decision.

    No heuristic decision replaces unavailable, failed or uncertain Jev. None asks
    the caller to commission the Facilitator without waiting for Jev to recover.
    A supplied fallback has already made that trip and never repeats Jev requests.
    """
    if fallback is not None:
        return _validated(fallback, catalog, 'facilitator', overrides)
    cfg = jev.config(ctx.folder, 'orchestration.runtime')
    if cfg is None:
        return None
    fields = record.to_dict() if isinstance(record, WorkRecord) else dict(record)
    title = fields.get('title')
    if title is None and fields.get('id'):
        from .state import own
        numbered = own(ctx).numbers_of('work', [str(fields['id'])]).get(str(fields['id']))
        title = numbered[1] if numbered else None
    state = {'title': title, 'kind': fields.get('kind'),
             'node': fields.get('address') or fields.get('receiver_address') or fields.get('node_id'),
             'task': fields.get('task'), 'strengths': strengths_of(ctx, catalog)}
    if fields.get('plan'):
        state['plan'] = fields['plan']
    with jev.within(jev.DEADLINE):
        if cfg.endpoint.name == 'openrouter' and jev.openrouter_credits()['status'] != 'available':
            return None
        classified = _pick(ctx, 'runtime_task', TASKS, state, fields.get('address'))
        if (classified is None or not classified.sure or not isinstance(classified.answer, str)
                or classified.answer not in TASKS):
            return None
        task_type = str(classified.answer)
        candidates = _candidates(catalog, task_type, overrides)
        if not candidates:
            return None
        options = {key: f"{one['agent']} / {one['model']} / {one['effort'] or 'harness default'}: "
                   f"{catalog[one['agent']]['models'][one['model']]}" for key, one in candidates.items()}
        selected = _pick(ctx, 'runtime_choice', options, {**state, 'task_type': task_type}, fields.get('address'))
        if (selected is None or not selected.sure or not isinstance(selected.answer, str)
                or selected.answer not in candidates):
            return None
        return _validated({**candidates[str(selected.answer)], 'task_type': task_type,
                           'confidence': min(classified.confidence, selected.confidence),
                           'reason': f'{classified.reason}\n{selected.reason}'}, catalog, 'jev', overrides)


def strengths_of(ctx: Context, catalog: Mapping[str, Any]) -> dict[str, str]:
    """The person's own account of what each installed agent does well, its models and its thinking levels, the
    settings dispatch_<agent>_strengths: given to the choice, Jev's or the Facilitator's, beside the advertised
    catalog, so the research the person delivered is in every decision (2026-10-21). Empty entries are left out."""
    found: dict[str, str] = {}
    for agent in catalog:
        key = f'dispatch_{agent}_strengths'
        words = str(settings.value(key, ctx.folder) or '').strip() if key in settings.SCHEMA else ''
        if words:
            found[str(agent)] = words
    return found


def _pick(ctx: Context, prompt: str, options: Mapping[str, str], state: Mapping[str, Any],
          address: Any) -> jev.Decision | None:
    question = prompt_files.served(resources.files('metaform.modules.orchestration'), prompt)
    return jev.pick_one(ctx.folder, question, options, state, title='Ticket runtime selection',
                        why='Match agent, model and thinking level to the assigned work.',
                        address=str(address) if address else None, project=ctx.project,
                        decision='orchestration.runtime')


def _candidates(catalog: Mapping[str, Any], task_type: str,
                overrides: Mapping[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """Advertised choices constrained only by explicit selections.

    Thinking controls are adapter-defined. No control means the harness default,
    while unfamiliar advertised labels remain usable without a Metaform ranking.
    Capability preferences belong in the model's decision, not candidate removal.
    """
    choices: dict[str, dict[str, Any]] = {}
    fixed = overrides or {}
    for agent, offered in catalog.items():
        if fixed.get('agent') and agent != fixed['agent']:
            continue
        for model in offered.get('models', {}):
            if fixed.get('model') and model != fixed['model']:
                continue
            advertised = cast(list[str], offered.get('efforts') or [])
            efforts: list[str | None] = ([fixed['effort']] if fixed.get('effort') in advertised
                       else [] if fixed.get('effort') else list(advertised) or [None])
            for effort in efforts:
                key = json.dumps([agent, model, effort], separators=(',', ':'))
                choices[key] = {'agent': agent, 'model': model, 'effort': effort}
    return choices


def rejection_reason(choice: Mapping[str, Any], catalog: Mapping[str, Any],
                     overrides: Mapping[str, Any] | None = None) -> str | None:
    """Explain the first invalid field using the same policy as runtime selection."""
    task_type, confidence = choice.get('task_type'), choice.get('confidence')
    if not isinstance(task_type, str) or task_type not in TASKS:
        return f"task_type: unknown value. Choose one of: {', '.join(TASKS)}."
    if (isinstance(confidence, bool) or not isinstance(confidence, (int, float))
            or not math.isfinite(confidence) or not 0 <= confidence <= 1):
        return 'confidence: expected a finite number within 0..1.'
    offered = cast(Mapping[str, Any], catalog.get(str(choice.get('agent'))) or {})
    models = list(cast(Mapping[str, Any], offered.get('models') or {}))
    if models and choice.get('model') not in models:  # a short name such as sol, or an exact value, is offered
        nearest = difflib.get_close_matches(str(choice.get('model')), models, n=1, cutoff=0.3)
        return (f"model: {choice.get('agent')} offers no {choice.get('model')}; it offers {', '.join(models)}"
                + (f'; nearest is {nearest[0]}.' if nearest else '.'))
    key = json.dumps([choice.get('agent'), choice.get('model'), choice.get('effort')], separators=(',', ':'))
    if key not in _candidates(catalog, task_type, overrides):
        return f'agent/model/effort: combination not offered for task_type {task_type} under ticket overrides.'
    if not isinstance(choice.get('reason'), str) or not choice['reason'].strip():
        return 'reason: expected non-empty text.'
    return None


def _validated(choice: Mapping[str, Any], catalog: Mapping[str, Any], decider: str,
               overrides: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
    if rejection_reason(choice, catalog, overrides) is not None:
        return None
    return {**{key: choice.get(key) for key in ('agent', 'model', 'effort')},
            'decider': decider, 'confidence': float(choice['confidence']),
            'task_type': choice['task_type'], 'reason': choice['reason']}
