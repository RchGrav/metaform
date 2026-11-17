"""Durable, person-approved handoffs from a finished discussion to execution."""
from __future__ import annotations

import hashlib
import os
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from metaform import home, prompt_files, settings
from metaform.data import Node, Store, TableTx
from metaform.module import Context, Stop, provided

from . import follow, stored

FILES = {'research': 'research.md', 'architecture': 'architecture.md', 'intake': 'intake.md',
         'plan_review': 'plan.md', 'decomposition': 'decomposition.md', 'execution_outline': 'execution-outline.md',
         'facilitation': 'facilitation.md'}
QUESTIONS = {
    'roundtable': 'Proceed with research to formalize requirements and SDK choices?',
    'research': 'Proceed with the complete architectural design?',
    'architecture': 'Create a separate project and run intake on this design?',
    'intake': 'Proceed with the step-by-step implementation plan?',
    'plan_review': 'Review the full plan. Comment, return it for planning again, or approve decomposition.',
    'decomposition': 'Review the execution outline before facilitation.',
    'execution_outline': 'Approve this execution outline and proceed with facilitation?',
}
NEXT = {'roundtable': 'research', 'research': 'architecture', 'architecture': 'intake',
        'intake': 'plan_review', 'plan_review': 'decomposition', 'execution_outline': 'facilitation'}
ROLES = {'research': 'researcher', 'architecture': 'architect', 'plan_review': 'planner',
         'decomposition': 'decomposer', 'facilitation': 'facilitator'}


def upgrade(tx: TableTx, found: int) -> None:
    """Keep old proposal evidence without allowing its direct planning route to continue."""
    if found != 3:
        return
    for row in tx.found_rows('proposals', limit=0).results:
        tx.insert('pipelines', {'table_id': row['table_id'], 'stage': 'roundtable', 'state': 'pending',
                  'created': row['created'], 'history': [{'legacy_proposal': dict(row)}]})


def origin(ctx: Context) -> Context:
    project = str(ctx.nouns.get('origin') or ctx.require_store().project_id)
    if project == ctx.require_store().project_id:
        return ctx
    registered = home.project(project)
    if registered is None:
        raise Stop('The source project is missing.', 'metaform list projects')
    return replace(ctx, project=project, store=Store(project, module='roundtables'))


def root(ctx: Context) -> Path:
    return Path(ctx.require_store().project().path).resolve()


def lock(ctx: Context, table: str) -> Any:
    # Table ids are opaque data, never filesystem path segments supplied by a caller.
    name = hashlib.sha256(f'{ctx.require_store().project_id}:{table}'.encode()).hexdigest()
    return home.file_lock(home.projects_dir() / f'roundtable-{name}.lock')


def row(ctx: Context, table: str) -> dict[str, Any]:
    with ctx.require_store().tables(write=False) as tx:
        kept = tx.get('pipelines', {'table_id': table})
    if kept is None:
        raise Stop('This table has no follow-through yet.', 'metaform roundtables follow-through ' + table)
    return dict(kept)


def state(ctx: Context, table: str) -> dict[str, Any] | None:
    with ctx.require_store().tables(write=False) as tx:
        kept = tx.get('pipelines', {'table_id': table})
    if kept is None:
        return None
    return {key: kept.get(key) for key in ('stage', 'state', 'file', 'digest', 'revision', 'error', 'feedback',
                                          'project', 'folder', 'board', 'automate_ticket_creation')} | {
        'ticket': kept.get('work_id'), 'question': QUESTIONS.get(str(kept['stage']), '')}


def change(ctx: Context, table: str, **values: Any) -> None:
    with ctx.require_store().tables() as tx:
        tx.concern(kind=follow.CHANGE_KIND)
        tx.concern(kind=f'{follow.CHANGE_KIND}:{table}')
        tx.update('pipelines', {'table_id': table}, values)


def announce(ctx: Context, table: str) -> dict[str, Any]:
    result = state(ctx, table)
    with ctx.require_store().tables() as tx:
        seq = max((int(one['seq']) for one in tx.rows('events', {'table_id': table}, limit=0).results), default=0) + 1
        tx.concern(kind=follow.CHANGE_KIND)
        tx.concern(kind=f'{follow.CHANGE_KIND}:{table}')
        tx.insert('events', {'table_id': table, 'seq': seq, 'kind': 'pipeline', 'audience': 'person',
                            'payload': {'pipeline': result}, 'at': follow.now()})
    ctx.publish(follow.TOPIC, {'table': table, 'seq': seq, 'kind': 'pipeline', 'audience': 'person',
                             'pipeline': result})
    return {'table': table, 'pipeline': result}


def path(ctx: Context, file: str) -> Path:
    found = (root(ctx) / file).resolve()
    if not found.is_relative_to(root(ctx)) or not found.is_file():
        raise Stop('The saved stage output is missing.', 'metaform roundtables status ' + str(ctx.nouns.get('table', '')))
    return found


def destination(ctx: Context, file: str) -> Path:
    found = (root(ctx) / file).resolve()
    if not found.is_relative_to(root(ctx)):
        raise Stop('Save stage outputs inside the source project.', 'metaform roundtables review')
    return found


def review(ctx: Context) -> dict[str, Any]:
    ctx = origin(ctx)
    table = str(ctx.nouns['table'])
    kept = row(ctx, table)
    result = {'table': table, 'pipeline': state(ctx, table)}
    if not kept.get('file') or not kept.get('digest'):
        return result
    body = path(ctx, str(kept['file'])).read_bytes()
    if hashlib.sha256(body).hexdigest() != kept['digest']:
        raise Stop('The output changed. Submit its current revision before review.',
                   'metaform roundtables submit ' + table)
    return {**result, 'output_text': body.decode('utf-8')}


def target(ctx: Context, kept: dict[str, Any]) -> Context:
    project = str(kept.get('project') or ctx.require_store().project_id)
    registered = home.project(project)
    if registered is None:
        raise Stop('The stage project is missing.', 'metaform list projects')
    return replace(ctx, project=project, folder=Path(registered.path), store=Store(project, module='roundtables'))


def service(ctx: Context) -> Any:
    services = [value for _, value in provided(ctx.folder, 'task.lifecycle')]
    if not services:
        raise Stop('Assigned tasks are off, so this stage cannot start.', 'metaform enable tasks')
    return services[0]


def claim(ctx: Context, table: str, role: str) -> None:
    """Keep only refused current launches in the target project's durable retry set."""
    called = target(ctx, row(ctx, table))
    key = {'origin': ctx.require_store().project_id, 'table_id': table}
    try:
        work = claim_task(ctx, table, role)
    except (Stop, OSError, ValueError):
        kept = row(ctx, table)
        if kept['state'] == 'running' and ROLES.get(str(kept['stage'])) == role:
            values = {'stage': kept['stage'], 'work_id': kept.get('work_id')}
            with called.require_store().tables() as tx:
                pending = tx.get('pending_stages', key)
                if pending is None:
                    tx.insert('pending_stages', {**key, **values})
                else:
                    values['work_id'] = kept.get('work_id') or pending.get('work_id')
                    tx.update('pending_stages', key, values)
        raise
    with called.require_store().tables() as tx:
        pending = tx.get('pending_stages', key)
        if pending and pending.get('work_id') in (None, work):
            tx.delete('pending_stages', key)


def claim_task(ctx: Context, table: str, role: str) -> str:
    """Reserve each stage once before dispatching, including recovery after an interrupted launch."""
    kept = row(ctx, table)
    called = target(ctx, kept)
    owner = service(called)
    name = stored.held(called.require_store().project_id)  # held in the project store: stage tickets are kept there
    if name is not None and role == 'decomposer':
        stored.refuse_board(name)
    work = kept.get('work_id')
    if not work:
        with ctx.require_store().tables(write=False) as tx:
            discussion = tx.get('tables', {'table_id': table})
        assert discussion is not None
        address = str(discussion.get('address') or '') if called.project == ctx.project else ''
        address = address or follow.top_element(called.require_store())
        if not address:
            raise Stop('The stage needs a functional map location.', 'metaform help intake')
        saved = str(cast(dict[str, Any], discussion.get('followed') or {}).get('saved') or '')
        artifacts = cast(list[dict[str, Any]], kept.get('artifacts') or [])
        materials = '\n'.join(str(root(ctx) / str(one['file'])) for one in artifacts)
        task = prompt_files.required(follow.PACKAGE, 'stage_task',
                table=table, origin=str(ctx.require_store().project_id), role=role, stage=str(kept['stage']),
                question=QUESTIONS.get(str(kept['stage']), ''), request=str(discussion['topic']),
                record=str(root(ctx) / saved / follow.RECORD), materials=materials,
                output=f'{saved}/{FILES.get(str(kept["stage"]), "facilitation.md")}',
                feedback=str(kept.get('feedback') or ''),
                project=str(kept.get('project') or ctx.require_store().project_id),
                target_folder=str(kept.get('folder') or root(ctx)), board=str(kept.get('board') or ''),
                table_record=path(ctx, f'{saved}/{follow.RECORD}').read_text(encoding='utf-8'),
                preparation=prompt_files.required(follow.PACKAGE, 'approved_execution' if role == 'facilitator' else
                    'automated_preparation' if kept.get('automate_ticket_creation') else 'reviewed_preparation'))
        # These stores have separate transactions: commit the ticket before either durable reference to it.
        key = {'origin': ctx.require_store().project_id, 'table_id': table}
        with called.require_store().tables(write=False) as tx:
            pending = tx.get('pending_stages', key)
        reserved = str(pending.get('work_id') or '') if pending and pending['stage'] == kept['stage'] else ''
        if reserved:
            if not (stored.ticket(name, reserved) if name is not None
                    else called.require_store().work(ids=[reserved]).results):
                raise Stop('The reserved stage ticket is missing. It was not recreated.',
                           'metaform roundtables review ' + table)
            work = reserved
        else:
            title = f'Roundtable {table}: {role}'
            work = stored.add(name, address, title=title, task=task) if name is not None else \
                called.require_store().add_work(Node('element', address), None, kind='enhancement', title=title,
                                                task=task).id
            with called.require_store().tables() as tx:
                if pending is None:
                    tx.insert('pending_stages', {**key, 'stage': kept['stage'], 'work_id': work})
                else:
                    tx.update('pending_stages', key, {'stage': kept['stage'], 'work_id': work})
        change(ctx, table, work_id=work)
    kept = row(ctx, table)
    history = list(kept.get('history') or [])
    attempts = [one for one in history if one.get('event') == 'stage_task' and one.get('work') == work]
    attempt = attempts[-1] if attempts else None
    if attempt and attempt.get('task_id'):
        owner.get(called, str(attempt['task_id']))
        assigned = owner.assignment(called, str(attempt['task_id']))
        if assigned and (assigned['state'] == 'cancelled' or assigned.get('cancel_requested')):
            change(ctx, table, state='stopped', error=None, revision=int(kept['revision']) + 1)
            return str(work)
        if assigned and assigned['state'] not in ('completed', 'failed', 'cancelled'):
            change(ctx, table, error=None)
            return str(work)
        attempt = None
    if attempt is None:
        attempt = {'event': 'stage_task', 'stage': kept['stage'], 'work': work,
                   'request_key': f'roundtable:{ctx.project}:{table}:{work}:{len(attempts) + 1}', 'at': follow.now(),
                   'asked': attempts[0].get('asked', time.time_ns()) if attempts else next(
                       (one['asked'] for one in reversed(history) if one.get('action') in (
                           'yes', 'approve', 'revise', 'automated_preparation') and one.get('asked')), time.time_ns())}
        history.append(attempt)
        # Record the launch intent first. Replaying a lost reply uses the same task request key.
        change(ctx, table, history=history)
    if name is not None:
        one = stored.ticket(name, str(work))
        given, node = (str(one.get('task') or ''), f"element:{one['address']}") if one else ('', '')
    else:
        records = called.require_store().work(ids=[str(work)]).results
        one = records[0] if records else None
        given, node = (str(one.task), f'{one.node_kind}:{one.node_id}') if one else ('', '')
    if one is None:
        raise Stop('The stage ticket is missing.', 'metaform roundtables review ' + table)
    launch = replace(called, nouns={'text': given.replace('work=YOUR_TICKET', f'work={work}'),
        'node': node, 'options': {'requested_at': attempt.get('asked'), 'roundtable': {
            'origin': ctx.require_store().project_id, 'table': table, 'work': work, 'stage': kept['stage']}}})
    result = owner.assign(launch, 'roundtable_stage', None, request_key=str(attempt['request_key']))
    attempt['task_id'] = result['task_id']
    current = row(ctx, table)
    history = list(current.get('history') or [])
    for index, recorded in enumerate(history):
        if recorded.get('request_key') == attempt['request_key']:
            history[index] = attempt
            break
    change(ctx, table, history=history)
    if current.get('work_id') != work or current['state'] != 'running':
        return str(work)  # A fast task can publish while its launch reply is being recorded.
    assigned = owner.assignment(called, str(result['task_id']))
    if assigned and (assigned['state'] == 'cancelled' or assigned.get('cancel_requested')):
        change(ctx, table, state='stopped', error=None, revision=int(current['revision']) + 1)
        return str(work)
    if assigned and assigned['state'] in ('completed', 'failed', 'cancelled'):
        raise Stop(str(assigned.get('message') or 'The stage task ended before publishing its output.'),
                   'metaform roundtables follow-through ' + table)
    change(ctx, table, error=None)
    return str(work)


def prepare(ctx: Context, table: str) -> dict[str, Any]:
    """Release discussion seats before this call. Never wake the system agent for the result."""
    with lock(ctx, table):
        try:
            store = ctx.require_store()
            with store.tables(write=False) as tx:
                discussion = tx.get('tables', {'table_id': table})
            if discussion is None or discussion['state'] != 'ended':
                raise Stop('Follow-through needs a finished table.', 'metaform roundtables status ' + table)
            saved = str(cast(dict[str, Any], discussion.get('followed') or {}).get('saved') or '')
            file = f'{saved}/{follow.REPORT}'
            if not (root(ctx) / file).is_file():
                file = f'{saved}/{follow.RECORD}'
            body = path(ctx, file).read_bytes()
            automation = bool(cast(dict[str, Any], discussion.get('followed') or {}).get('automate_ticket_creation'))
            with store.tables() as tx:
                kept = tx.get('pipelines', {'table_id': table})
                if kept is None:
                    tx.insert('pipelines', {'table_id': table, 'stage': 'roundtable', 'state': 'pending',
                                           'created': follow.now(), 'automate_ticket_creation': automation})
            kept = row(ctx, table)
            if kept['state'] == 'pending':
                change(ctx, table, state='awaiting', file=file, digest=hashlib.sha256(body).hexdigest(), revision=1,
                       artifacts=[{'stage': 'roundtable', 'file': file, 'digest': hashlib.sha256(body).hexdigest()}])
            if kept['state'] == 'running' and kept['stage'] in ROLES:
                claim(ctx, table, ROLES[kept['stage']])
            elif kept['state'] == 'running' and kept['stage'] == 'intake' and not intake_complete(ctx, table):
                status = [value for _, value in provided(ctx.folder, 'dispatch.design_intake_active')]
                if kept.get('error') or status and not status[0](target(ctx, kept)):
                    start_intake(ctx, table)
            if kept.get('automate_ticket_creation'):
                advance_automated(ctx, table)
            return announce(ctx, table)
        except (Stop, OSError, ValueError) as error:
            if state(ctx, table) is not None:
                change(ctx, table, error=follow.named(error))
                return {**announce(ctx, table), 'error': follow.named(error)}
            return {'table': table, 'error': follow.named(error)}


def intake_complete(ctx: Context, table: str) -> bool:
    kept = row(ctx, table)
    if kept['stage'] != 'intake' or kept['state'] != 'running' or not kept.get('project'):
        return False
    mapped = target(ctx, kept).require_store()
    if mapped.intake_building().results or not follow.top_element(mapped):
        return False
    name = stored.held(mapped.project_id)  # a map in the project store is named by the project's name there
    base = None if name is not None else mapped.bound_base()
    held = f'{name} in the project store' if name is not None else base.id if base else ''
    text = f'# Intake\n\nProject: {mapped.project_id}\nFolder: {kept["folder"]}\nMap: {held}\n'
    file = str(Path(str(kept['file'])).with_name(FILES['intake']))
    destination(ctx, file).write_text(text, encoding='utf-8')
    digest = hashlib.sha256(text.encode()).hexdigest()
    artifacts = list(kept.get('artifacts') or []) + [{'stage': 'intake', 'file': file, 'digest': digest}]
    change(ctx, table, state='awaiting', file=file, digest=digest, artifacts=artifacts,
           revision=int(kept['revision']) + 1, error=None)
    if kept.get('automate_ticket_creation'):
        advance_automated(ctx, table)
    return True


def intake_finished(payload: dict[str, Any], ctx: Context) -> dict[str, Any] | None:
    # Named topic and exact project first. Unrelated map bursts cause no reads.
    if not payload.get('project') or payload['project'] != ctx.require_store().project_id:
        return None
    with ctx.require_store().tables(write=False) as tx:
        links = list(tx.rows('intake_links', limit=0).results)
    for link in links:
        source = origin(replace(ctx, nouns={'origin': link['origin'], 'table': link['table_id']}))
        with lock(source, str(link['table_id'])):
            if intake_complete(source, str(link['table_id'])):
                announce(source, str(link['table_id']))
    return None


def tasks_changed(payload: dict[str, Any], ctx: Context) -> None:
    """A native session change can free a slot for a previously refused stage launch."""
    if payload.get('project') != ctx.project or not payload.get('work_ids'):
        return
    tables, kinds = payload.get('tables'), payload.get('kinds')
    if tables != 'dispatch' and not (isinstance(tables, list) and any(
            str(one).startswith('dispatch.') for one in cast(list[Any], tables))):
        return
    if not isinstance(kinds, list) or not {'session', 'worker-idle'} & set(cast(list[str], kinds)):
        return
    with ctx.require_store().tables(write=False) as tx:
        pending = [dict(one) for one in tx.rows('pending_stages', limit=0).results]
    for reference in pending:
        source, table = str(reference['origin']), str(reference['table_id'])
        try:
            called = origin(replace(ctx, nouns={'origin': source, 'table': table}))
            kept = row(called, table)
        except Stop:
            with ctx.require_store().tables() as tx:
                tx.delete('pending_stages', {'origin': source, 'table_id': table})
            continue  # A removed source project/table no longer has preparation to recover.
        if kept['state'] == 'running' and kept.get('work_id') in (None, reference['work_id']) \
                and kept['stage'] == reference['stage']:
            prepare(called, table)
        else:
            with ctx.require_store().tables() as tx:
                tx.delete('pending_stages', {'origin': source, 'table_id': table})


def start_intake(ctx: Context, table: str) -> None:
    kept = row(ctx, table)
    starters = [value for _, value in provided(ctx.folder, 'dispatch.design_intake')]
    if not starters:
        raise Stop('Dispatch is off, so intake cannot start.', 'metaform enable dispatch')
    design = path(ctx, str(kept['file'])).read_text(encoding='utf-8')
    retry = bool(kept.get('project'))
    launch = target(ctx, kept) if retry else ctx
    nouns: dict[str, Any] = {'text': design} if retry else {'project_name': kept['project_name'], 'text': design}
    if retry and launch.require_store().intake_building().results:
        nouns['resume'] = True
    result = starters[0](replace(launch, nouns=nouns))
    project = str(kept['project'] if retry else result['project'])
    folder = str(kept['folder'] if retry else result['folder'])
    change(ctx, table, project=project, folder=folder, work_id=result.get('work_id'),
           error=result.get('error'))
    with Store(project, module='roundtables').tables() as tx:
        key = {'origin': ctx.require_store().project_id, 'table_id': table}
        if tx.get('intake_links', key) is None:
            tx.insert('intake_links', key)
    intake_complete(ctx, table)  # Covers an intake that finished before its origin link was recorded.


def advance_automated(ctx: Context, table: str) -> None:
    """Advance saved preparation only. Execution always needs a later person decision."""
    kept = row(ctx, table)
    stage = str(kept['stage'])
    if not kept.get('automate_ticket_creation') or kept['state'] != 'awaiting' or stage == 'execution_outline':
        return
    next_stage = NEXT.get(stage)
    if next_stage is None or next_stage == 'facilitation':
        return
    history = list(kept.get('history') or []) + [{'stage': stage, 'action': 'automated_preparation',
               'digest': kept['digest'], 'revision': kept['revision'], 'at': follow.now(), 'asked': time.time_ns()}]
    change(ctx, table, stage=next_stage, state='running', work_id=None, error=None, history=history,
           revision=int(kept['revision']) + 1)
    try:
        if next_stage == 'intake':
            start_intake(ctx, table)
        else:
            claim(ctx, table, ROLES[next_stage])
    except (Stop, OSError, ValueError) as error:
        change(ctx, table, error=follow.named(error))


def decide(ctx: Context) -> dict[str, Any]:
    ctx = origin(ctx)
    table, action = str(ctx.nouns['table']), str(ctx.nouns['action'])
    with lock(ctx, table):
        kept = row(ctx, table)
        review(ctx)
        if kept['state'] != 'awaiting' or ctx.nouns.get('digest') != kept['digest'] \
                or ctx.nouns.get('revision') != kept['revision']:
            raise Stop('Review the current output before deciding.', 'metaform roundtables review ' + table)
        stage = str(kept['stage'])
        allowed = ('comment', 'revise', 'approve', 'no') if stage == 'plan_review' else \
                  ('approve', 'no') if stage == 'execution_outline' else ('yes', 'no')
        if action not in allowed:
            raise Stop('This stage requires ' + ', '.join(allowed) + '.', 'metaform roundtables review ' + table)
        comment = str(ctx.nouns.get('comment') or '').strip()
        if action in ('comment', 'revise') and not comment:
            raise Stop('Provide comments on the plan.', 'metaform roundtables review ' + table)
        history = list(kept.get('history') or []) + [{'stage': stage, 'action': action, 'digest': kept['digest'],
                    'revision': kept['revision'], 'comment': comment, 'at': follow.now(), 'asked': time.time_ns()}]
        change(ctx, table, history=history, feedback='\n'.join(filter(None, [kept.get('feedback'), comment])))
        if action == 'comment':
            change(ctx, table, revision=int(kept['revision']) + 1)
        elif action == 'no':
            change(ctx, table, state='stopped', revision=int(kept['revision']) + 1)
            with target(ctx, kept).require_store().tables() as tx:
                tx.delete('pending_stages', {'origin': ctx.project, 'table_id': table})
        else:
            next_stage = 'plan_review' if action == 'revise' else NEXT[stage]
            change(ctx, table, stage=next_stage, state='running', work_id=None, error=None,
                   revision=int(kept['revision']) + 1)
            try:
                if next_stage == 'intake':
                    start_intake(ctx, table)
                else:
                    claim(ctx, table, ROLES[next_stage])
            except (Stop, OSError, ValueError) as error:
                # Accepted consent stays durable. Recovery retries its existing ticket, never a later stage.
                change(ctx, table, error=follow.named(error))
        return announce(ctx, table)


def submit(ctx: Context) -> dict[str, Any]:
    source = ctx.folder.resolve()
    ctx = origin(ctx)
    table = str(ctx.nouns['table'])
    with lock(ctx, table):
        kept = row(ctx, table)
        stage = str(ctx.nouns['stage'])
        work_matches = str(ctx.nouns['work']) == kept.get('work_id')
        if not work_matches or (stage != kept['stage'] and not (
                stage == 'decomposition' and kept['stage'] == 'execution_outline')):
            previous = next((one for one in reversed(kept.get('artifacts') or [])
                             if one['stage'] == stage and one.get('work') == str(ctx.nouns['work'])), None)
            incoming = (source / str(ctx.nouns['file'])).resolve()
            if previous is not None and incoming.is_relative_to(source) and incoming.is_file() and \
                    hashlib.sha256(incoming.read_bytes()).hexdigest() == previous['digest']:
                return {'table': table, 'pipeline': state(ctx, table)}
            raise Stop('This is not the current stage assignment.', 'metaform roundtables review ' + table)
        if stage not in FILES or stage in ('intake', 'execution_outline'):
            raise Stop('This stage publishes through its system handler.', 'metaform roundtables review ' + table)
        with ctx.require_store().tables(write=False) as tx:
            discussion = tx.get('tables', {'table_id': table})
        assert discussion is not None
        saved = str(cast(dict[str, Any], discussion['followed'])['saved'])
        file = f'{saved}/{FILES[stage]}'
        incoming = (source / str(ctx.nouns['file'])).resolve()
        if not incoming.is_relative_to(source) or not incoming.is_file():
            raise Stop('Save the output inside this assignment folder.', 'metaform roundtables status ' + table)
        body = incoming.read_bytes()
        if not body.strip():
            raise Stop('The stage output is empty.', 'metaform roundtables status ' + table)
        body.decode('utf-8')
        digest = hashlib.sha256(body).hexdigest()
        if kept['state'] != 'running':
            previous = next((one for one in reversed(kept.get('artifacts') or []) if one['stage'] == stage), None)
            if previous is not None and previous['digest'] == digest:
                return {'table': table, 'pipeline': state(ctx, table)}
            raise Stop('This is not the current stage assignment.', 'metaform roundtables review ' + table)
        project_name = str(ctx.nouns.get('project_name') or kept.get('project_name') or '').strip()
        if stage == 'architecture' and not project_name:
            raise Stop('Architect must name the new project.', 'metaform roundtables submit ' + table)
        output = destination(ctx, file)
        temporary = output.with_suffix('.tmp')
        temporary.write_bytes(body)
        os.replace(temporary, output)
        artifacts = list(kept.get('artifacts') or []) + [{'stage': stage, 'file': file, 'digest': digest,
                                                       'work': str(ctx.nouns['work'])}]
        board = str(ctx.nouns.get('board') or kept.get('board') or '')
        if stage == 'decomposition':
            if kept.get('automate_ticket_creation') and board == settings.value('board', target(ctx, kept).folder):
                raise Stop('The prepared board must remain inactive.', 'select the fresh inactive board')
            if not board:
                raise Stop('Decomposer must name its fresh board.', 'metaform roundtables submit ' + table)
            from . import execution_outline
            outline = execution_outline.write(ctx, board=board, plan=f'{saved}/{FILES["plan_review"]}',
                                              project=str(kept.get('project') or ctx.require_store().project_id))
            if kept.get('automate_ticket_creation') and not outline['tickets']:
                raise Stop('The prepared board has no tickets.', 'populate the fresh board before submission')
            file = f'{saved}/{FILES["execution_outline"]}'
            digest = hashlib.sha256(path(ctx, file).read_bytes()).hexdigest()
            stage = 'execution_outline'
            artifacts.append({'stage': stage, 'file': file, 'digest': digest})
        change(ctx, table, stage=stage, state='completed' if stage == 'facilitation' else 'awaiting',
               file=file, digest=digest, artifacts=artifacts, board=board,
               project_name=project_name, revision=int(kept['revision']) + 1, error=None)
        if kept.get('automate_ticket_creation'):
            advance_automated(ctx, table)
        return announce(ctx, table)
