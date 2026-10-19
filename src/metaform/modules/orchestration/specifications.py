"""Publish an operative file or stored workflow revision and its durable routes."""
from __future__ import annotations

import os
import tempfile
from importlib import resources
from pathlib import Path
from typing import Any, cast

from metaform import prompt_files
from metaform.module import Context, Stop, agent_caller, persons_word

from .state import (
    HELP,
    Orchestration,
    current_mode,
    fingerprint,
    identity,
    now,
    own,
    requested,
    row_for,
    touch,
    transition,
    update,
    verb,
)


def specification(ctx: Context, given: Any) -> dict[str, Any]:
    spec: dict[str, Any] = dict(cast(dict[str, Any], given)) if isinstance(given, dict) else {'uri': str(given)}
    if spec.get('kind') == 'workflow':
        spec.setdefault('uri', f'workflow:{spec["address"]}:{spec["layer"]}:{spec["name"]}')
        return spec
    uri = str(spec.get('uri') or spec.get('path') or '')
    if uri.startswith('ref:'):
        reference = own(ctx).ref(uri.removeprefix('ref:'))
        if reference is None:
            raise Stop(f'No specification reference {uri}.', 'metaform map refs')
        uri = str(reference.value)
        spec['reference'] = spec['uri']
    path = Path(uri.removeprefix('file:'))
    if not path.is_absolute():
        path = ctx.folder / path
    spec.update(kind='file', path=str(path), uri=spec.get('uri') or f'file:{path}')
    return spec


def read(ctx: Context, spec: dict[str, Any]) -> tuple[str, str]:
    if spec['kind'] == 'workflow':
        versions = verb(ctx, 'workflow', 'history', address=spec['address'], layer=spec['layer'], name=spec['name'])
        if not versions:
            raise Stop('The operative workflow has no recorded revision.', HELP)
        current = versions[-1]
        return str(current['content']), str(current['number'])
    content = Path(spec['path']).read_text(encoding='utf-8')
    return content, fingerprint(content)


def _write(ctx: Context, spec: dict[str, Any], content: str, change_id: str) -> str:
    if spec['kind'] == 'workflow':
        verb(ctx, 'workflow', 'add_logic', address=spec['address'], layer=spec['layer'], name=spec['name'],
             content=content, provenance={'orchestration_change': change_id})
        return read(ctx, spec)[1]
    path = Path(spec['path'])
    previous_mode = path.stat().st_mode
    descriptor, filename = tempfile.mkstemp(prefix=f'.{path.name}.', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(filename, previous_mode)
        os.replace(filename, path)
    finally:
        if os.path.exists(filename):
            os.unlink(filename)
    return fingerprint(content)


def change(ctx: Context, runtime: Orchestration) -> dict[str, Any]:
    target = ctx.nouns.get('assessment') or ctx.nouns.get('assignment')
    caller = ctx.session or os.environ.get('METAFORM_SESSION')
    instruction = ctx.nouns.get('user_instruction')
    word = persons_word(ctx.folder, 'Applying a new user specification instruction', ctx.project) if instruction else None
    person = ctx.consented or ctx.surface not in ('mcp', 'cli') or \
        (ctx.surface == 'cli' and agent_caller() is None)
    source = 'user' if instruction and (person or word is not None) else 'agent'
    if source == 'user':
        assessment = runtime.assignment(ctx, assignment_id=target, session_id=caller)
        if assessment is None or assessment.get('stop'):
            raise Stop('The user instruction needs an active recorded assignment.', HELP)
    else:
        assessment = requested(ctx, target)
    if ctx.nouns.get('key'):
        with own(ctx).tables(write=False) as tx:
            previous = tx.get('changes', {'change_id': identity('change', assessment['assignment_id'],
                                                               str(ctx.nouns['key']))})
        if previous:
            return previous
    spec = specification(ctx, ctx.nouns.get('specification') or ctx.nouns.get('spec') or
                         assessment.get('specification'))
    content, revision = read(ctx, spec)
    base = str(ctx.nouns.get('base') or spec.get('revision') or revision)
    if base != revision:
        raise Stop(f'Specification advanced from {base} to {revision}; reconcile this operative revision.', HELP)
    proposed = str(ctx.nouns['content'])
    key = str(ctx.nouns.get('key') or identity(assessment['assignment_id'], spec['uri'], base,
                                            fingerprint(proposed)))
    change_id = identity('change', assessment['assignment_id'], key)
    store = own(ctx)
    with store.tables() as tx:
        existing = tx.get('changes', {'change_id': change_id})
        if existing:
            return existing
        current = row_for(tx, assignment_id=assessment['assignment_id']) or assessment
        mode = current_mode(tx, current)
        roots = ctx.nouns.get('affected_work_ids') or [
            (row_for(tx, assignment_id=current.get('gc_assignment_id')) or current)['work_id']]
        state = 'recommendation' if mode == 'strict' and source != 'user' else 'publishing'
        made = tx.insert('changes', {'change_id': change_id, 'assessment_assignment_id': assessment['assignment_id'],
            'specification': spec, 'previous_revision': revision, 'current_revision': None,
            'before_content': content, 'content': proposed, 'reason': str(ctx.nouns['reason']),
            'observed_limitation': str(ctx.nouns.get('observed_limitation') or ''),
            'affected_work_ids': list(dict.fromkeys(roots)), 'mode_at_publication': mode, 'source': source,
            'user_instruction': {'text': instruction, 'word': word, 'session_id': caller} if source == 'user' else None,
            'state': state, 'user_message_state': 'pending', 'created': now(), 'updated': now()})
        touch(tx, assessment, 'change')
        if state == 'recommendation':
            _routes(ctx, tx, runtime, made, recommendation=True)
        else:
            transition(tx, assessment, 'publish', {'change_id': change_id}, change_id)
    if state == 'publishing':
        finish_publication(ctx, runtime, change_id)
    with store.tables(write=False) as tx:
        return tx.get('changes', {'change_id': change_id}) or made


def _routes(ctx: Context, tx: Any, runtime: Orchestration, change_record: dict[str, Any], *,
            recommendation: bool = False) -> None:
    change_id = change_record['change_id']
    assessment = row_for(tx, assignment_id=change_record['assessment_assignment_id'])
    if assessment is None:
        raise Stop('The assessment assignment is unavailable.', HELP)
    published_revision = change_record['current_revision'] or change_record['previous_revision']
    source = change_record['specification']
    operative_content, operative_revision = read(ctx, source)
    spec = {**source, 'revision': published_revision if recommendation else operative_revision}
    superseded = not recommendation and operative_revision != published_revision
    body = prompt_files.served(resources.files('metaform.modules.orchestration'), 'user_adaptation',
        specification=f'{spec["uri"]} revision {published_revision}', change=change_record['content'],
        reason=change_record['reason'], affected=', '.join(change_record['affected_work_ids']))
    if recommendation:
        body = f'Strict-mode recommendation; operative revision {spec["revision"]} retained.\n{body}'
    elif superseded:
        body += f'\nThe specification has since advanced to operative revision {operative_revision}. ' \
                f'The current assignment uses this later content:\n{operative_content}'
    envelope = {'kind': 'recommendation' if recommendation else 'change_order', 'change_id': change_id,
        'specification': spec, 'previous_revision': change_record['previous_revision'],
        'current_revision': spec['revision'], 'body': body, 'reason': change_record['reason'],
        'published_revision': published_revision, 'operative_content': operative_content,
        'source': change_record['source'], 'superseded': superseded, 'operative_revision': operative_revision,
        'sender_assignment_id': assessment['assignment_id'],
        'sender_session_id': assessment['owner_session_id'], 'origin_assessment_id': assessment['assignment_id']}
    recipients: set[str] = set()
    for work_id in change_record['affected_work_ids']:
        root = row_for(tx, work_id=work_id)
        if root is None:
            continue
        gc = row_for(tx, assignment_id=root.get('gc_assignment_id')) or root
        if gc['assignment_id'] in recipients:
            continue
        recipients.add(gc['assignment_id'])
        if not recommendation:
            for member in tx.rows('assignments', {'team_id': gc['team_id']}, limit=0).results:
                directions = list(member['pending_direction'] or [])
                if not any(one.get('change_id') == change_id for one in directions):
                    directions.append(envelope)
                update(tx, member, specification=spec, pending_direction=directions)
            update(tx, assessment, specification=spec)
        transition(tx, gc, 'send', envelope, change_id)
        runtime.wake(tx, gc, change_id)
    transition(tx, assessment, 'user_message', {**envelope, 'kind': 'specification_recommendation' if
               recommendation else 'specification_adaptation'}, change_id)


def finish_publication(ctx: Context, runtime: Orchestration, change_id: str) -> dict[str, Any]:
    """Recover the same proposed write and routes; never invent a second adaptation."""
    store = own(ctx)
    with store.atomic(), store.tables() as tx:
        record = tx.get('changes', {'change_id': change_id})
        if record is None:
            raise Stop(f'No specification change {change_id}.', HELP)
        if record['state'] in ('published', 'recommendation'):
            return {'state': 'completed', 'change_id': change_id}
        assessment = row_for(tx, assignment_id=record['assessment_assignment_id'])
        if assessment is None:
            raise Stop('The assessment assignment is unavailable.', HELP)
        spec = record['specification']
        if record['state'] != 'operative':
            current, revision = read(ctx, spec)
            already_written = current == record['content'] and current != record['before_content']
            if not already_written and revision != record['previous_revision']:
                raise Stop(f'Specification {spec["uri"]} changed during publication; current revision {revision}.', HELP)
            mode = current_mode(tx, assessment)
            if not already_written and mode == 'strict' and record['source'] != 'user':
                retained = tx.update('changes', {'change_id': change_id}, {
                    'state': 'recommendation', 'mode_at_publication': mode, 'updated': now()})
                assert retained is not None
                _routes(ctx, tx, runtime, retained, recommendation=True)
                return {'state': 'completed', 'change_id': change_id, 'recommendation': True}
            new_revision = revision if already_written else _write(ctx, spec, record['content'], change_id)
            record = tx.update('changes', {'change_id': change_id}, {'state': 'operative',
                'current_revision': new_revision,
                'mode_at_publication': record['mode_at_publication'] if already_written else mode, 'updated': now()})
            assert record is not None
            touch(tx, assessment, 'change')
    # The operative specification is committed before its project-level workflow continuation changes.
    # Recovery repeats this stable successor operation and the pending routes, without rewriting the spec.
    new_revision = record['current_revision']
    operative_revision = read(ctx, spec)[1]
    if spec['kind'] == 'workflow' and spec.get('run'):
        continuation_change = change_id if operative_revision == new_revision else \
            identity(change_id, 'operative-source', operative_revision)
        successor = verb(ctx, 'workflow', 'revise', run=spec['run'], change=continuation_change,
                         address=spec['address'], layer=spec['layer'], name=spec['name'], revision=operative_revision)
        spec = {**spec, 'previous_run': spec['run'], 'run': successor['run'], 'revision': operative_revision,
                'continuation_state': successor.get('continuation', 'successor')}
    with store.atomic(), store.tables() as tx:
        if spec['kind'] == 'workflow' and spec.get('run') and read(ctx, spec)[1] != operative_revision:
            # The source changed between the two stores' commits. Keep the completed successor link and
            # signal one more recorded attempt; that attempt follows its successor instead of a cancelled run.
            tx.update('changes', {'change_id': change_id}, {'specification': spec, 'updated': now()})
            touch(tx, assessment, 'change')
            return {'state': 'queued', 'change_id': change_id, 'reason': 'The workflow source advanced during routing.'}
        written = tx.update('changes', {'change_id': change_id}, {'state': 'published',
            'specification': spec, 'updated': now()})
        assert written is not None
        _routes(ctx, tx, runtime, written)
        touch(tx, assessment, 'change')
        for event in tx.rows('transitions', {'assignment_id': assessment['assignment_id']}, limit=0).results:
            if event['kind'] == 'publish' and event['payload'].get('change_id') == change_id:
                tx.update('transitions', {'transition_id': event['transition_id']}, {
                    'state': 'delivered', 'delivery': {'state': 'completed', 'revision': new_revision},
                    'updated': now()})
    return {'state': 'completed', 'change_id': change_id, 'revision': new_revision}


def inspect_change(ctx: Context) -> dict[str, Any] | list[dict[str, Any]] | None:
    with own(ctx).tables(write=False) as tx:
        if ctx.nouns.get('change'):
            return tx.get('changes', {'change_id': str(ctx.nouns['change'])})
        return list(tx.rows('changes', limit=0).results)
