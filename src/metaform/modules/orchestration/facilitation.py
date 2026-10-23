"""The Facilitator's in-context expertise operations.

Publishing reusable instructions is distinct from accepting a commission to run
another contribution. Registry publication never returns or closes caller work.
Actual delegation and ticket launches remain owned by the existing service.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import replace
from typing import Any, cast

from metaform import home
from metaform.module import Context, Stop, held_role, provided

from . import methods
from .runtime import TASKS, choose, rejection_reason, strengths_of
from .state import SERVICE, fingerprint, own, service


def _writing(ctx: Context) -> None:
    blocked = held_role(ctx)
    if blocked:
        raise Stop(f'The configured roles_without_authority excludes {blocked} from creating or directing work.',
                   'metaform config --show')


def _registry(ctx: Context) -> Any:
    return service(ctx, 'agent.role')


def _identity(ctx: Context) -> dict[str, Any]:
    assignment = SERVICE.assignment(ctx)
    return {'method': 'facilitator', 'caller_session_id': ctx.session,
            'caller_assignment_id': (assignment or {}).get('assignment_id')}


def find(ctx: Context) -> dict[str, Any]:
    """Purpose-oriented metadata search; a query does not turn into an eligibility test."""
    entries = _registry(ctx).specialists(ctx)
    words = set(re.findall(r'\w+', str(ctx.nouns.get('query') or '').casefold()))
    if words:
        entries = sorted(entries, key=lambda one: -len(words & set(re.findall(
            r'\w+', f'{one["name"]} {one["purpose"]}'.replace('_', ' ').casefold()))))
    return {'specialists': entries, 'execution': 'current', 'body_read': 'orchestration_facilitate op=use role=NAME'}


def publish(ctx: Context) -> dict[str, Any]:
    """Create or reuse expertise directly, without manufacturing a creator assignment."""
    _writing(ctx)
    name = str(ctx.nouns.get('role') or '').removeprefix('metaform://role/')
    if not name:
        raise Stop('Name the reusable expertise.', 'metaform orchestration facilitate op=publish role=NAME')
    registry = _registry(ctx)
    # Share publication's existing per-project lock with commissioned creation.
    lock = home.home() / 'run' / 'role-publication' / f'{fingerprint(f"{ctx.project}:{name}")}.lock'
    home.mkdir_private(lock.parent)
    with home.file_lock(lock):
        resolved = registry.resolve(ctx, name)
        if not resolved.get('missing'):
            if resolved.get('problems') or not resolved.get('specialist'):
                raise Stop(f'{name} is not unambiguous registered specialist expertise.',
                           'metaform orchestration facilitate op=find')
            source = 'existing'
        else:
            duty, purpose = str(ctx.nouns.get('duty') or '').strip(), str(ctx.nouns.get('purpose') or '').strip()
            if not duty or not purpose:
                raise Stop('New expertise needs a purpose and reusable duty.',
                           'metaform orchestration facilitate op=publish role=NAME purpose=PURPOSE duty=DUTY')
            resolved = registry.publish(ctx, name, purpose, duty, source=_identity(ctx))
            source = 'created'
    return {'source': source, 'role': {key: resolved.get(key) for key in ('name', 'uri', 'purpose', 'version_id')},
            'execution': 'current', 'assignment_changed': False,
            'read': f'orchestration_facilitate op=use role={name}'}


def runtime(ctx: Context) -> dict[str, Any]:
    """A choice made by the current informed agent uses the same catalog and overrides.

    The old commissioned path remains valid. Reading a skill neither changes the
    caller's registered role nor supplies an invented commission identity.
    """
    work = str(ctx.nouns['work'])
    fallback = cast(Mapping[str, Any] | None, ctx.nouns.get('choice'))
    if fallback is None:
        return SERVICE.runtime(ctx, work)
    _writing(ctx)
    transports = [transport for _, transport in provided(ctx.folder, 'orchestration.transport')
                  if hasattr(transport, 'runtime_catalog')]
    if not transports:
        return {'state': 'unmanaged'}
    transport = transports[0]
    record = own(ctx).ticket(work).work
    kept = transport.runtime_settings(ctx, work)
    decision = cast(Mapping[str, Any], kept.get('decision') or {})
    overrides = cast(dict[str, Any], decision.get('overrides') or {})
    if not overrides and decision.get('decider') == 'person':
        overrides = {key: kept[key] for key in ('agent', 'model', 'effort') if kept.get(key)}
    if not decision and kept.get('agent'):
        overrides = {'agent': kept['agent']}
    catalog = transport.runtime_catalog(ctx, work)
    selected = choose(ctx, record, catalog, fallback=fallback, overrides=overrides)
    if selected is None:
        return {'state': 'needs_choice', 'work_id': work, 'catalog': catalog,
                'strengths': strengths_of(ctx, catalog), 'task_types': dict(TASKS),
                'reason': rejection_reason(fallback, catalog, overrides)}
    selected['task_fingerprint'] = fingerprint(record.task or '')
    selected['source'] = _identity(ctx)
    saved = transport.keep_runtime(ctx, work, selected)
    return {'state': 'selected', 'choice': saved, 'source': _identity(ctx)}


def facilitate(ctx: Context) -> dict[str, Any]:
    op = str(ctx.nouns.get('op') or 'find')
    if op == 'find':
        return find(ctx)
    if op == 'use':
        name = str(ctx.nouns.get('role') or '')
        if not name:
            raise Stop('Name the expertise to use.', 'metaform orchestration facilitate op=find')
        uri = 'metaform://role/' + name.removeprefix('metaform://role/')
        return methods.apply(replace(ctx, nouns={'name': uri, 'task': ctx.nouns.get('task')}))
    if op == 'publish':
        return publish(ctx)
    if op == 'runtime':
        if not ctx.nouns.get('work'):
            raise Stop('Runtime selection names the ticket it configures.',
                       'metaform orchestration facilitate op=runtime work=WORK')
        return runtime(ctx)
    raise Stop(f'No Facilitator operation {op}.', 'metaform help orchestration facilitate')
