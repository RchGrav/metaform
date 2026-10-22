"""Durable, person-approved handoffs from a finished discussion to execution."""
from __future__ import annotations

import hashlib
import os
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from metaform import home, prompt_files, settings
from metaform.data import Node, Store, TableTx
from metaform.module import Context, Stop, agent_caller, provided

from . import follow

FILES = {'research': 'research.md', 'architecture': 'architecture.md', 'intake': 'intake.md',
         'plan_review': 'plan.md', 'decomposition': 'decomposition.md', 'execution_outline': 'execution-outline.md',
         'facilitation': 'facilitation.md'}
QUESTIONS = {
    'roundtable': 'Proceed with research to formalize requirements and SDK choices?',
    'research': 'Proceed with the complete architectural design?',
    'architecture': 'Create a separate project and run intake on this design?',
    'intake': 'Proceed with the step-by-step implementation plan?',
    'plan_review': 'Review the full plan. Comment, return it to Planner, or approve decomposition.',
    'decomposition': 'Review the execution outline before facilitation.',
    'execution_outline': 'Approve this execution outline and proceed with facilitation?',
}
NEXT = {'roundtable': 'research', 'research': 'architecture', 'architecture': 'intake',
        'intake': 'plan_review', 'plan_review': 'decomposition', 'execution_outline': 'facilitation'}
ROLES = {'research': 'researcher', 'architecture': 'architect', 'plan_review': 'planner',
         'decomposition': 'decomposer', 'facilitation': 'facilitator'}


def upgrade(tx: TableTx, found: int) -> None:
    """Keep old proposal evidence without allowing its direct Planner route to continue."""
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
    services = [value for _, value in provided(ctx.folder, 'orchestration')]
    if not services:
        raise Stop('Orchestration is off, so this stage cannot start.', 'metaform enable orchestration')
    return services[0]


def claim(ctx: Context, table: str, role: str, *, coordinator: bool = False) -> None:
    """Reserve each stage once before dispatching, including recovery after an interrupted launch."""
    kept = row(ctx, table)
    called = ctx if coordinator else target(ctx, kept)
    owner = service(called)
    key = 'coordinator' if coordinator else 'work_id'
    work = kept.get(key)
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
        task = prompt_files.required(follow.PACKAGE, 'follow_through_task' if coordinator else 'stage_task',
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
        # Work and reservation share a transaction when they belong to the source project.
        with called.require_store().atomic():
            created = called.require_store().add_work(Node('element', address), None, kind='enhancement',
                        title=f'Roundtable {table}: {"follow-through" if coordinator else role}', task=task)
            work = created.id
            change(ctx, table, **{key: work})
    # Creation authorizes presentation and its selected preparation mode.
    # Reviewed launches carry the exact persisted person decision.
    nouns: dict[str, Any] = {'work': str(work), 'role': role, 'automatic': False,
             'result': 'Publish only the assigned output. The durable pipeline controls later stages.'}
    if role == 'facilitator' and not coordinator:
        nouns['specification'] = {'approved_board': kept['board'], 'source_project': ctx.require_store().project_id,
                                  'table': table, 'reviewed_digest': kept['digest']}
    launch = replace(called, nouns=nouns, consented=True)
    if owner.assignment(launch, work_id=str(work)) is None:
        try:
            owner.claim(launch)
        except Stop:
            if owner.assignment(launch, work_id=str(work)) is None:
                raise
    change(ctx, table, error=None)


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
            for _, transport in provided(ctx.folder, 'orchestration.transport'):
                ident = f'roundtable-result-{table}'
                record = f'{saved}/{follow.RECORD}'
                transport.notify_user(ctx, {'message_id': ident, 'kind': 'roundtable_result',
                                      'table': table, 'record': record, 'text': f'Roundtable {table}: {record}'}, ident)
                break
            if kept['stage'] == 'roundtable' and kept['state'] in ('pending', 'awaiting'):
                claim(ctx, table, 'roundtable_follow_through', coordinator=True)
            elif kept['state'] == 'running' and kept['stage'] in ROLES:
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
    base = mapped.bound_base()
    text = f'# Intake\n\nProject: {mapped.project_id}\nFolder: {kept["folder"]}\nMap: {base.id if base else ""}\n'
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
               'digest': kept['digest'], 'revision': kept['revision'], 'at': follow.now()}]
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
    if not ctx.consented and (ctx.surface == 'mcp' or (ctx.surface == 'cli' and agent_caller() is not None)):
        raise Stop('The person must decide from the page or their own terminal.', 'metaform roundtables review')
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
            raise Stop('Provide comments for Planner.', 'metaform roundtables review ' + table)
        history = list(kept.get('history') or []) + [{'stage': stage, 'action': action, 'digest': kept['digest'],
                    'revision': kept['revision'], 'comment': comment, 'at': follow.now()}]
        change(ctx, table, history=history, feedback='\n'.join(filter(None, [kept.get('feedback'), comment])))
        if action == 'comment':
            change(ctx, table, revision=int(kept['revision']) + 1)
        elif action == 'no':
            change(ctx, table, state='stopped', revision=int(kept['revision']) + 1)
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
