"""Assignment-time runtime decisions over the installed agents' advertised choices."""
from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from importlib import resources
from typing import Any

from metaform import jev, prompt_files, settings
from metaform.data import WorkRecord
from metaform.module import Context

TASKS = {
    'planning': 'Build a concrete specification, plan, goal, tickets or their order.',
    'needs_plan': 'Requested coding lacks concrete behavior or acceptance evidence; return it to the Planner.',
    'frontend': 'Write code for front-end visual polish or interaction presentation.',
    'coding': 'Implement a precise ticket with concrete behavior and acceptance evidence.',
    'lookup': 'Research, collect information, look up documentation or perform a quick check for another agent.',
    'routing': 'Check status, route messages, move raw data or apply simple formatting without writing code.',
    'analysis': 'Investigate a complex problem, design architecture or solve a novel multi-step problem.',
    'writing': 'Write ordinary non-coding content or provide standard technical analysis.',
}
LEVELS = {'off': 0, 'disabled': 0, 'none': 0, 'minimal': 1, 'light': 1, 'low': 2,
          'medium': 3, 'high': 4, 'xhigh': 5, 'max': 6, 'pro': 6, 'ultra': 7}


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
        options = {key: f"{one['agent']} / {one['model']} / {one['effort']}: "
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


def _efforts(offered: Sequence[str], task_type: str) -> list[str]:
    ranked = {one: LEVELS[one.lower()] for one in offered if one.lower() in LEVELS}
    if not ranked:
        return []
    if task_type == 'routing':
        target = min(ranked.values())
    elif task_type == 'lookup':
        target = min(ranked.values(), key=lambda value: (abs(value - LEVELS['low']), value))
    elif task_type in ('planning', 'needs_plan'):
        target = max(ranked.values())
        if target < LEVELS['high']:
            return []
    else:
        floor = LEVELS['high'] if task_type == 'analysis' else LEVELS['medium']
        return [one for one, level in ranked.items() if level >= floor]
    return [one for one, level in ranked.items() if level == target]


def _candidates(catalog: Mapping[str, Any], task_type: str,
                overrides: Mapping[str, Any] | None = None) -> dict[str, dict[str, str]]:
    choices: dict[str, dict[str, str]] = {}
    fixed = overrides or {}
    for agent, offered in catalog.items():
        if fixed.get('agent') and agent != fixed['agent']:
            continue
        if not fixed.get('agent') and ((task_type == 'frontend' and agent != 'claude')
                                       or (task_type == 'coding' and agent != 'codex')):
            continue
        for model in offered.get('models', {}):
            if fixed.get('model') and model != fixed['model']:
                continue
            efforts = ([fixed['effort']] if fixed.get('effort') in offered.get('efforts', [])
                       else [] if fixed.get('effort') else _efforts(offered.get('efforts', []), task_type))
            for effort in efforts:
                key = json.dumps([agent, model, effort], separators=(',', ':'))
                choices[key] = {'agent': agent, 'model': model, 'effort': effort}
    return choices


def _validated(choice: Mapping[str, Any], catalog: Mapping[str, Any], decider: str,
               overrides: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
    task_type, confidence = choice.get('task_type'), choice.get('confidence')
    if (not isinstance(task_type, str) or task_type not in TASKS or isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))):
        return None
    if not math.isfinite(confidence) or not 0 <= confidence <= 1:
        return None
    key = json.dumps([choice.get('agent'), choice.get('model'), choice.get('effort')], separators=(',', ':'))
    candidates = _candidates(catalog, str(task_type), overrides)
    if key not in candidates or not isinstance(choice.get('reason'), str) or not choice['reason'].strip():
        return None
    return {**candidates[key], 'decider': decider, 'confidence': float(confidence),
            'task_type': task_type, 'reason': choice['reason']}
