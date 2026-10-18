"""Authored roles and one durable receipt ledger for each recipient context epoch."""
from __future__ import annotations

import hashlib
import re
import time
from collections.abc import Sequence
from typing import Any, cast

from metaform import home, prompt_files
from metaform.data import Column, Index, StoreError, Table
from metaform.module import AgentRoleDefinition, Context, Stop, context, provided

TABLES = (
    Table('definitions', place='project', key=('name',), columns=(
        Column('name', required=True), Column('purpose', required=True), Column('prompts', 'json', required=True),
        Column('source', 'json', required=True), Column('version_id', required=True), Column('at', required=True))),
    Table('definition_history', place='project', key=('name', 'seq'), columns=(
        Column('name', required=True), Column('seq', 'int', required=True), Column('purpose', required=True),
        Column('prompts', 'json', required=True), Column('source', 'json', required=True),
        Column('version_id', required=True), Column('at', required=True))),
    Table('role_sources', place='project', key=('name', 'provider'), columns=(
        Column('name', required=True), Column('provider', required=True), Column('purpose', required=True),
        Column('prompts', 'json', required=True))),
    Table('contexts', place='project', key=('session_id',), columns=(
        Column('session_id', required=True), Column('epoch', 'int', required=True), Column('reason'),
        Column('at', required=True))),
    Table('receipts', place='project', key=('session_id', 'epoch', 'name'), columns=(
        Column('session_id', required=True), Column('epoch', 'int', required=True), Column('name', required=True),
        Column('fingerprint', required=True), Column('actual_version_id'), Column('selected_version_id'),
        Column('component', 'json', required=True), Column('channel', required=True), Column('at', required=True)),
        indexes=(Index(('name',)),)),
)


def _own(ctx: Context) -> Context:
    return ctx if ctx.module == 'agents' else context('agents', ctx.folder, project=ctx.project,
                                                     session=ctx.session, identity=ctx.identity)


def generated(ctx: Context) -> tuple[AgentRoleDefinition, ...]:
    """Generated definitions are normal provider contributions; their duties remain versioned prompt-store text."""
    ctx = _own(ctx)
    if ctx.store is None:
        return ()
    with ctx.store.tables(write=False) as tx:
        rows = tx.rows('definitions', limit=0).results
    return tuple(AgentRoleDefinition(str(row['name']), str(row['purpose']), tuple(row['prompts'])) for row in rows)


def definitions(ctx: Context) -> list[tuple[str, AgentRoleDefinition]]:
    found: list[tuple[str, AgentRoleDefinition]] = []
    for owner, values in provided(ctx.folder, 'agent.roles'):
        contributed = values(context(owner, ctx.folder, project=ctx.project)) if callable(values) else values
        found.extend((owner, one) for one in cast(Sequence[Any], contributed)
                     if isinstance(one, AgentRoleDefinition))
    return found


def _fingerprint(one: dict[str, Any]) -> str:
    # Recompute from the actual body rather than trusting a caller's label for another body.
    return hashlib.sha256(str(one.get('text') or '').encode('utf-8')).hexdigest()


class RoleService:
    """Public `agent.role` service. Resolution, binding by orchestration, and delivery are distinct operations."""

    def resolve(self, ctx: Context, name: str, *, bindings: dict[str, str] | None = None) -> dict[str, Any]:
        ctx = _own(ctx)
        name = name.removeprefix('metaform://role/')
        matched = [(owner, one) for owner, one in definitions(ctx) if one.name == name]
        result: dict[str, Any] = {'uri': f'metaform://role/{name}', 'name': name, 'provider': None,
                                  'purpose': '', 'components': [], 'problems': [], 'missing': False}
        if not matched:
            known: Sequence[dict[str, Any]] = ()
            if ctx.store:
                with ctx.store.tables(write=False) as tx:
                    known = tx.rows('role_sources', {'name': name}, limit=0).results
            result['missing'] = not bool(known)
            result['problems'] = [f'Role {name} source is unavailable: ' + ', '.join(str(one['provider']) for one in known)
                                   if known else f'No authored role {name} on this surface.']
            return result
        if len(matched) > 1:
            result['problems'] = [f'Role {name} is claimed by providers: {", ".join(owner for owner, _ in matched)}.']
            return result
        owner, definition = matched[0]
        result.update(provider=owner, purpose=definition.purpose)
        if ctx.store is not None:
            with ctx.store.tables() as tx:
                key = {'name': name, 'provider': owner}
                row = {**key, 'purpose': definition.purpose, 'prompts': list(definition.prompts)}
                previous = tx.get('role_sources', key)
                if previous is None:
                    tx.insert('role_sources', row)
                elif previous != row:
                    tx.update('role_sources', key, row)
        renderers = provided(ctx.folder, 'prompt.render')
        components: list[dict[str, Any]] = []
        problems: list[str] = []
        for reference in definition.prompts:
            fills = dict(bindings or {})
            component_owner = reference.partition(':')[0]
            for renderer_owner, renderer in renderers:
                if renderer_owner == component_owner:
                    supplied = renderer(context(renderer_owner, ctx.folder, project=ctx.project), reference, fills)
                    if supplied is not None:
                        fills.update(cast(dict[str, str], supplied))
            try:
                one = prompt_files.resolve(reference, **fills)
            except (OSError, LookupError, StoreError, ValueError) as error:
                problems.append(f'{reference}: {error}')
                continue
            components.append(one)
        result.update(components=components, problems=problems,
                      notices=[notice for one in components for notice in
                               [*one.get('notices', []), *one.get('problems', [])]],
                      text='\n\n'.join(str(one['text']) for one in components))
        return result

    def publish(self, ctx: Context, name: str, purpose: str, duty: str,
                source: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx = _own(ctx)
        name = name.removeprefix('metaform://role/')
        if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*', name):
            raise Stop('A role name must fit one resource path segment.', 'use a registered role identity')
        conflicts = [owner for owner, one in definitions(ctx) if one.name == name and owner != 'agents']
        if conflicts:
            raise Stop(f'Role {name} is already provided by {", ".join(conflicts)}.', 'inspect that role')
        # Source identity survives project reuse while generated prompt names never overwrite a shipped component.
        prompt_name = f'agents:generated_{ctx.require_store().project_id}_{name}'
        version, _ = prompt_files.save_edit(prompt_name, duty, format='text')
        references = ['orchestration:common', prompt_name]
        row = {'name': name, 'purpose': purpose, 'prompts': references, 'source': dict(source or {}),
               'version_id': version.version_id, 'at': home.now()}
        with ctx.require_store().tables() as tx:
            previous = tx.get('definitions', {'name': name})
            if previous is None:
                tx.insert('definitions', row)
            else:
                tx.update('definitions', {'name': name}, row)
            if previous is None or previous['version_id'] != version.version_id or previous['source'] != row['source']:
                tx.insert('definition_history', {**row, 'seq': time.time_ns()})
        ctx.publish('agent.role.changed', {'role': name, 'version_id': version.version_id, 'project': ctx.project})
        return {**self.resolve(ctx, name), 'version_id': version.version_id, 'source': row['source']}

    def epoch(self, ctx: Context, session: str | None) -> int:
        ctx = _own(ctx)
        if session is None or ctx.store is None:
            return 0
        with ctx.store.tables(write=False) as tx:
            row = tx.get('contexts', {'session_id': session})
        return int(row['epoch']) if row else 0

    def prepare(self, ctx: Context, session: str | None,
                components: Sequence[dict[str, Any]]) -> dict[str, Any]:
        ctx = _own(ctx)
        previous: dict[str, Any] = {}
        epoch = 0
        if session is not None and ctx.store is not None:
            with ctx.store.tables(write=False) as tx:
                row = tx.get('contexts', {'session_id': session})
                epoch = int(row['epoch']) if row else 0
                for one in components:
                    receipt = tx.get('receipts', {'session_id': session, 'epoch': epoch, 'name': one['name']})
                    if receipt:
                        previous[str(one['name'])] = receipt
        due: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for given in components:
            one = {**given, 'rendered_fingerprint': _fingerprint(given)}
            key = (str(one['name']), str(one['rendered_fingerprint']))
            if key in seen or previous.get(key[0], {}).get('fingerprint') == key[1]:
                continue
            seen.add(key)
            due.append(one)
        return {'epoch': epoch, 'components': due, 'previous': previous,
                'text': '\n\n'.join(str(one.get('text') or '') for one in due)}

    def record(self, ctx: Context, session: str | None, components: Sequence[dict[str, Any]], *,
               epoch: int | None = None, channel: str = 'turn') -> dict[str, Any]:
        ctx = _own(ctx)
        if session is None or ctx.store is None:
            return {'recorded': 0, 'epoch': epoch or 0}
        recorded = 0
        with ctx.store.tables() as tx:
            current = tx.get('contexts', {'session_id': session})
            active = int(current['epoch']) if current else 0
            epoch = active if epoch is None else epoch
            if epoch != active:
                return {'recorded': 0, 'epoch': epoch, 'current_epoch': active, 'stale': True}
            if current is None:
                tx.insert('contexts', {'session_id': session, 'epoch': epoch, 'at': home.now(), 'reason': 'first_delivery'})
            for given in components:
                one = {**given, 'rendered_fingerprint': _fingerprint(given)}
                key = {'session_id': session, 'epoch': epoch, 'name': str(one['name'])}
                row = {**key, 'fingerprint': one['rendered_fingerprint'],
                       'actual_version_id': one.get('actual_version_id'),
                       'selected_version_id': one.get('selected_version_id'), 'component': one,
                       'channel': channel, 'at': home.now()}
                before = tx.get('receipts', key)
                if before is None:
                    tx.insert('receipts', row)
                elif before['fingerprint'] != row['fingerprint']:
                    tx.update('receipts', key, row)
                else:
                    continue
                recorded += 1
        return {'recorded': recorded, 'epoch': epoch}

    def advance(self, ctx: Context, session: str | None, *, reason: str = 'compaction') -> int:
        ctx = _own(ctx)
        if session is None or ctx.store is None:
            return 0
        with ctx.store.tables() as tx:
            key = {'session_id': session}
            held = tx.get('contexts', key)
            epoch = int(held['epoch']) + 1 if held else 1
            row = {**key, 'epoch': epoch, 'reason': reason, 'at': home.now()}
            if held is None:
                tx.insert('contexts', row)
            else:
                tx.update('contexts', key, row)
        return epoch


SERVICE = RoleService()


def compacted(payload: dict[str, Any], ctx: Context) -> None:
    session = payload.get('session') or payload.get('runner') or payload.get('session_id')
    if session:
        SERVICE.advance(ctx, str(session), reason='compaction')


def resolve(ctx: Context) -> dict[str, Any]:
    return SERVICE.resolve(ctx, str(ctx.nouns['name']))


def publish(ctx: Context) -> dict[str, Any]:
    return SERVICE.publish(ctx, str(ctx.nouns['name']), str(ctx.nouns['purpose']), str(ctx.nouns['duty']),
                           cast(dict[str, Any], ctx.nouns.get('source') or {}))


def inspect_receipts(ctx: Context) -> dict[str, Any]:
    session = str(ctx.nouns['session'])
    with ctx.require_store().tables(write=False) as tx:
        rows = tx.rows('receipts', {'session_id': session}, limit=0).results
    return {'session': session, 'epoch': SERVICE.epoch(ctx, session), 'receipts': rows}


