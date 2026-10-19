"""Authored roles and one durable receipt ledger for each recipient context epoch."""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time
from collections.abc import Sequence
from typing import Any, cast

from metaform import home, prompt_files
from metaform.data import Column, Index, StoreError, Table
from metaform.module import AgentRoleDefinition, Context, Stop, context, forget_shown, provided

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
        indexes=(Index(('name',)), Index(('session_id', 'epoch', 'fingerprint')))),
    Table('delivered_text', place='project', key=('session_id', 'epoch', 'fingerprint'), columns=(
        Column('session_id', required=True), Column('epoch', 'int', required=True),
        Column('fingerprint', required=True), Column('at', required=True))),
    Table('context_checks', place='project', key=('session_id',), columns=(
        Column('session_id', required=True), Column('epoch', 'int', required=True),
        Column('checkpoint', required=True), Column('marker', required=True),
        Column('pending', 'bool', required=True), Column('confirmed', 'bool', required=True))),
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

    def specialists(self, ctx: Context) -> list[dict[str, Any]]:
        """Only reusable expertise, with no duty bodies or operational roles in the selection context."""
        declared = definitions(_own(ctx))
        counts: dict[str, int] = {}
        for _, one in declared:
            counts[one.name] = counts.get(one.name, 0) + 1
        return [{'name': one.name, 'purpose': one.purpose, 'uri': f'metaform://role/{one.name}', 'provider': owner}
                for owner, one in declared if one.specialist and counts[one.name] == 1]

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
        result.update(provider=owner, purpose=definition.purpose, specialist=definition.specialist)
        if ctx.store is not None:
            with ctx.store.tables() as tx:
                key = {'name': name, 'provider': owner}
                row = {**key, 'purpose': definition.purpose, 'prompts': list(definition.prompts)}
                previous = tx.get('role_sources', key)
                if previous is None:
                    tx.insert('role_sources', row)
                elif previous != row:
                    tx.update('role_sources', key, row)
        generated_row = None
        if owner == 'agents' and ctx.store is not None:
            with ctx.store.tables(write=False) as tx:
                generated_row = tx.get('definitions', {'name': name})
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
                if generated_row and reference.startswith('agents:generated_') and \
                        'duty' in generated_row['source']:
                    one = prompt_files.component(reference, generated_row['source']['duty'])
                    one.update(actual_version_id=generated_row['version_id'],
                               selected_version_id=generated_row['version_id'])
                else:
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
        row = {'name': name, 'purpose': purpose, 'prompts': references, 'source': {**(source or {}), 'duty': duty},
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
        known: set[str] = set()
        epoch = 0
        if session is not None and ctx.store is not None:
            with ctx.store.tables(write=False) as tx:
                row = tx.get('contexts', {'session_id': session})
                epoch = int(row['epoch']) if row else 0
                for one in components:
                    receipt = tx.get('receipts', {'session_id': session, 'epoch': epoch, 'name': one['name']})
                    if receipt:
                        previous[str(one['name'])] = receipt
                    fingerprint = _fingerprint(one)
                    where = {'session_id': session, 'epoch': epoch, 'fingerprint': fingerprint}
                    # The old receipt table supplies evidence for homes predating the content ledger.
                    if tx.get('delivered_text', where) or tx.rows('receipts', where, limit=1).results:
                        known.add(fingerprint)
        due: list[dict[str, Any]] = []
        seen: set[str] = set()
        for given in components:
            one = {**given, 'rendered_fingerprint': _fingerprint(given)}
            key = str(one['rendered_fingerprint'])
            if key in seen:
                continue
            seen.add(key)
            if key in known:
                before = cast(dict[str, Any] | None, previous.get(str(one['name'])))
                if before is None:
                    continue
                previous_component = cast(dict[str, Any], before.get('component') or {})
                active = str(previous_component.get('active_fingerprint') or before['fingerprint'])
                if active == key:
                    continue
                # A -> B -> A changes which retained instruction is active. Send a reference to A, not A's body,
                # and remember that activation only when the reference actually reaches the recipient.
                reference: dict[str, Any] = {'name': one['name'], 'fingerprint': key,
                                            'version': one.get('actual_version_id'), 'after': before['at']}
                text = prompt_files.module('agents', 'restore_context', component_name=str(one['name']),
                    fingerprint=key, version=str(one.get('actual_version_id') or 'unversioned'),
                    after=str(before['at'])) or ''
                one.update(text=text, active_fingerprint=key, reference=reference)
                if 'delivered_value' in one:
                    one['delivered_value'] = reference
                one['rendered_fingerprint'] = _fingerprint(one)
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
                content_key = {'session_id': session, 'epoch': epoch, 'fingerprint': one['rendered_fingerprint']}
                if tx.get('delivered_text', content_key) is None:
                    tx.insert('delivered_text', {**content_key, 'at': home.now()})
                key = {'session_id': session, 'epoch': epoch, 'name': str(one['name'])}
                row = {**key, 'fingerprint': one['rendered_fingerprint'],
                       'actual_version_id': one.get('actual_version_id'),
                       'selected_version_id': one.get('selected_version_id'), 'component': one,
                       'channel': channel, 'at': home.now()}
                before = tx.get('receipts', key)
                # Preserve the legacy receipt before replacing it: A -> B -> A must not resend A after upgrade.
                if before is not None:
                    old_key = {**content_key, 'fingerprint': before['fingerprint']}
                    if tx.get('delivered_text', old_key) is None:
                        tx.insert('delivered_text', {**old_key, 'at': before['at']})
                if before is None:
                    tx.insert('receipts', row)
                elif before['fingerprint'] != row['fingerprint']:
                    tx.update('receipts', key, row)
                else:
                    continue
                recorded += 1
        return {'recorded': recorded, 'epoch': epoch}

    def begin_check(self, ctx: Context, session: str | None) -> dict[str, Any]:
        """A startup/resume challenge. Only the runner receives the key; a retained context already has it."""
        ctx = _own(ctx)
        if session is None or ctx.store is None:
            return {}
        with ctx.store.tables() as tx:
            key = {'session_id': session}
            current = tx.get('contexts', key)
            epoch = int(current['epoch']) if current else 0
            prior = tx.get('context_checks', key)
            marker = prior['marker'] if prior and prior['epoch'] == epoch else secrets.token_hex(12)
            row = {**key, 'epoch': epoch, 'checkpoint': secrets.token_hex(8), 'marker': marker,
                   'pending': True, 'confirmed': False}
            if prior:
                tx.update('context_checks', key, row)
            else:
                tx.insert('context_checks', row)
        return row

    def finish_check(self, ctx: Context, session: str | None, checkpoint: str,
                     *, marker: str | None = None) -> dict[str, Any]:
        """An absent/incorrect proof makes context eligible once, without pushing it or scheduling a turn.

        A supplied marker confirms a pending check. A stale reply cannot confirm a newer startup or invalidate
        context twice; completed compaction already made the old check obsolete.
        """
        ctx = _own(ctx)
        if session is None or ctx.store is None:
            return {}
        with ctx.store.tables() as tx:
            key = {'session_id': session}
            check = tx.get('context_checks', key)
            current = tx.get('contexts', key)
            epoch = int(current['epoch']) if current else 0
            if not check or check['checkpoint'] != checkpoint or check['epoch'] != epoch:
                return {'confirmed': False, 'stale': True, 'epoch': epoch}
            if not check['pending']:
                return {'confirmed': bool(check['confirmed']), 'epoch': epoch}
            confirmed = marker is not None and hmac.compare_digest(str(check['marker']), marker)
            tx.update('context_checks', key, {'pending': False, 'confirmed': confirmed})
            if confirmed:
                return {'confirmed': True, 'epoch': epoch}
            epoch += 1
            row = {**key, 'epoch': epoch, 'reason': 'retention_unconfirmed', 'at': home.now()}
            if current:
                tx.update('contexts', key, row)
            else:
                tx.insert('contexts', row)
        return {'confirmed': False, 'epoch': epoch, 'eligible': True}

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
    # An inspection must not become another route for dumping delivered bodies or revealing a retention key.
    return {'session': session, 'epoch': SERVICE.epoch(ctx, session),
            'receipts': [{key: value for key, value in row.items() if key != 'component'} for row in rows]}


def confirm_context(ctx: Context) -> dict[str, Any]:
    """Only the actual caller can acknowledge its retained key; a tool argument cannot choose another session."""
    if not ctx.session:
        raise Stop('A context check belongs to the calling agent session.', 'run this from the assigned agent')
    result = SERVICE.finish_check(ctx, ctx.session, str(ctx.nouns['checkpoint']),
                                   marker=str(ctx.nouns['key']) if ctx.nouns.get('key') else None)
    if result.get('eligible'):
        forget_shown(ctx.session)
    return result


