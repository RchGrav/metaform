"""Finished discussions advance through fresh roles only after the person's review."""
from __future__ import annotations

import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest

from metaform.data import Node, Store
from metaform.module import Context, Stop
from metaform.modules.roundtables import follow, pipeline

pytestmark = pytest.mark.kind('fixture')
TABLE = 'finished'
ADDRESS = 'code.delivery'
SAVED = 'docs/roundtables/7-delivery'


@pytest.fixture
def finished_table(run, tmp_path, monkeypatch):
    """Real source/target stores and inbox, with deterministic fresh-role admission."""
    from metaform.modules.dispatch.orchestration import TRANSPORT

    folder = tmp_path / 'source'
    folder.mkdir()
    run('add', 'project', 'source', str(folder))
    run('enable', 'dispatch', cwd=folder)
    store = Store('source', module='roundtables')
    with store.atomic():
        store.layer('base', 'intake', 'Source map.', kind='intake', mutable=False, hideable=False,
                    provenance={'module': 'intake'}, ready=True)
        store.add_element('base', ADDRESS, name_length=1, role='DE')
    record = folder / SAVED
    record.mkdir(parents=True)
    (record / follow.RECORD).write_text('{"table_record": "Complete table evidence."}\n', encoding='utf-8')
    (record / follow.REPORT).write_text('# Table answer\n\nKeep ordered handoffs.\n', encoding='utf-8')
    with store.tables() as tx:
        tx.insert('tables', {'table_id': TABLE, 'address': ADDRESS, 'topic': 'How should delivery work?',
                             'opening': '.', 'seats': ['stub/vega'], 'discussion': 7, 'spend': 0.0,
                             'state': 'ended', 'answer': 'Show saved results.', 'answered': True,
                             'created': follow.now(), 'followed': {'saved': SAVED, 'opener': 'person',
                             'result_topics': [{'number': 1, 'title': 'Delivery'}]}})

    class Roles:
        def __init__(self):
            self.assignments = {}
            self.claims = []
            self.intakes = []
            self.intake_active = True
            self.intake_status_calls = []

        def assignment(self, _ctx, *, work_id):
            return self.assignments.get(work_id)

        def claim(self, ctx):
            self.claims.append({'project': ctx.project, 'consented': ctx.consented, **ctx.nouns})
            result = {'assignment_id': f'assignment-{len(self.claims)}', 'role': ctx.nouns['role'],
                      'work_id': ctx.nouns['work']}
            self.assignments[ctx.nouns['work']] = result
            return result

        def intake_status(self, ctx):
            self.intake_status_calls.append(ctx.project)
            return self.intake_active

        def intake(self, ctx):
            self.intakes.append(dict(ctx.nouns))
            target = tmp_path / 'target'
            target.mkdir()
            run('add', 'project', 'target', str(target))
            return {'project': 'target', 'folder': str(target), 'work_id': 'intake-work'}

    roles = Roles()

    def providers(_folder, purpose):
        if purpose == 'orchestration':
            return [('orchestration', roles)]
        if purpose == 'orchestration.transport':
            return [('dispatch', TRANSPORT)]
        if purpose == 'dispatch.design_intake':
            return [('dispatch', roles.intake)]
        if purpose == 'dispatch.design_intake_active':
            return [('dispatch', roles.intake_status)]
        raise AssertionError(f'Unexpected provider: {purpose}')

    monkeypatch.setattr(pipeline, 'provided', providers)
    from metaform.modules.roundtables import pipeline as current_pipeline
    monkeypatch.setattr(current_pipeline, 'provided', providers)
    ctx = Context('roundtables', folder, project='source', store=store, nouns={'table': TABLE}, consented=True)
    return ctx, roles, record


def decide(ctx, action, **nouns):
    kept = pipeline.state(ctx, TABLE)
    return pipeline.decide(replace(ctx, nouns={'table': TABLE, 'action': action, 'digest': kept['digest'],
                                               'revision': kept['revision'], **nouns}))['pipeline']


def submit(ctx, text=None, **nouns):
    kept = pipeline.row(ctx, TABLE)
    source = ctx.folder / 'stage-output.md'
    source.write_text(text or f'# {kept["stage"]}\n\nComplete stage evidence.\n', encoding='utf-8')
    return pipeline.submit(replace(ctx, nouns={'table': TABLE, 'stage': kept['stage'], 'work': kept['work_id'],
                                               'file': source.name, **nouns}))['pipeline']


def through_architecture(ctx):
    pipeline.prepare(ctx, TABLE)
    decide(ctx, 'yes')
    submit(ctx)
    decide(ctx, 'yes')
    submit(ctx, project_name='Delivery project')


def complete_intake(ctx):
    """Build the target map, then deliver the actual map-completion payload."""
    target = Store('target', module='roundtables')
    with target.atomic():
        target.layer('base', 'intake', 'Target map.', kind='intake', mutable=False, hideable=False,
                     provenance={'module': 'intake'}, ready=True)
        target.add_element('base', ADDRESS, name_length=1, role='DE')
    called = replace(ctx, project='target', folder=Path(target.project().path), store=target, nouns={})
    pipeline.intake_finished({'project': 'target'}, called)
    return target


def through_plan(ctx):
    through_architecture(ctx)
    decide(ctx, 'yes')
    target = complete_intake(ctx)
    decide(ctx, 'yes')
    submit(ctx, '# Full plan\n\n1. Preserve every requirement.\n2. Build delivery.\n')
    return target


def test_finished_table_claims_fresh_follow_through_and_sends_one_compact_nonwaking_copy(finished_table):
    from metaform.modules.dispatch.orchestration import update_entries, user_updates

    ctx, roles, record = finished_table
    first = pipeline.prepare(replace(ctx, consented=False), TABLE)
    second = pipeline.prepare(ctx, TABLE)
    assert first['pipeline'] == second['pipeline']
    assert first['pipeline']['stage'] == 'roundtable' and first['pipeline']['state'] == 'awaiting'
    assert first['pipeline']['question']
    assert [one['role'] for one in roles.claims] == ['roundtable_follow_through'], first
    assert roles.claims[0]['automatic'] is False and roles.claims[0]['consented'] is True
    works = ctx.require_store().work(limit=0).results
    assert len(works) == 1 and works[0].id == pipeline.row(ctx, TABLE)['coordinator']
    assert 'Complete table evidence.' in works[0].task
    assert str(record / follow.RECORD) in works[0].task
    assert 'output_text' not in first['pipeline']
    assert pipeline.review(ctx)['output_text'] == (record / follow.REPORT).read_text(encoding='utf-8')
    dispatch = replace(ctx, module='dispatch', store=Store('source'))
    ident = 'roundtable-result-finished'
    assert user_updates(dispatch) == [ident]
    assert update_entries(dispatch, [ident]) == [(ident, f'Roundtable {TABLE}: {SAVED}/{follow.RECORD}', False)]


def test_yes_chain_runs_each_fresh_role_and_requires_execution_outline_approval(finished_table):
    ctx, roles, record = finished_table
    through_architecture(ctx)
    assert [one['role'] for one in roles.claims] == ['roundtable_follow_through', 'researcher', 'architect']
    assert decide(ctx, 'yes')['stage'] == 'intake'
    assert roles.intakes == [{'project_name': 'Delivery project', 'text': '# architecture\n\nComplete stage evidence.\n'}]
    assert pipeline.state(ctx, TABLE)['state'] == 'running'
    target = complete_intake(ctx)
    assert pipeline.state(ctx, TABLE)['stage'] == 'intake'
    assert pipeline.state(ctx, TABLE)['state'] == 'awaiting'
    assert pipeline.review(ctx)['output_text'].startswith('# Intake\n\nProject: target')
    assert decide(ctx, 'yes')['stage'] == 'plan_review'
    assert roles.claims[-1]['role'] == 'planner' and roles.claims[-1]['project'] == 'target'
    plan = '# Full plan\n\n1. Preserve every requirement.\n2. Build delivery.\n'
    ready = submit(ctx, plan)
    assert ready['stage'] == 'plan_review' and pipeline.review(ctx)['output_text'] == plan
    assert 'decomposer' not in [one['role'] for one in roles.claims]
    assert decide(ctx, 'approve')['stage'] == 'decomposition'
    assert roles.claims[-1]['role'] == 'decomposer'
    with target.atomic():
        work = target.add_work(Node('element', ADDRESS), None, title='Build delivery', task='Deliver exact result.')
        target.edit_work(work.id, {'held': True, 'hold_reason': 'Wait for execution outline approval.'})
        with Store('target', module='map').tables() as tx:
            tx.insert('boards', {'name': 'delivery', 'created': follow.now()})
            tx.update('ticket_settings', {'work_id': work.id}, {'board': 'delivery'})
    ready = submit(ctx, '# Decomposed\n', board='delivery')
    assert ready['stage'] == 'execution_outline' and ready['state'] == 'awaiting'
    outline = pipeline.review(ctx)['output_text']
    snapshot = json.loads(outline.split('```json\n', 1)[1].split('\n```', 1)[0])
    assert snapshot['project'] == 'target' and snapshot['tickets'] == [
        {'id': work.id, 'title': 'Build delivery', 'depends_on': [], 'expected_outcome': 'Deliver exact result.'}]
    assert (record / 'execution-outline.md').is_file()
    assert 'facilitator' not in [one['role'] for one in roles.claims]
    with pytest.raises(Stop, match='approve, no'):
        decide(ctx, 'yes')
    assert decide(ctx, 'approve')['stage'] == 'facilitation'
    assert [one['role'] for one in roles.claims] == [
        'roundtable_follow_through', 'researcher', 'architect', 'planner', 'decomposer', 'facilitator']
    stage_claims = roles.claims[1:]
    assert all(one['automatic'] is False and one['consented'] is True for one in stage_claims)
    assert len({one['work'] for one in roles.claims}) == len(roles.claims)
    assert submit(ctx, '# Delivery completed\n\nSpecialist work passed critic review.\n')['state'] == 'completed'
    assert pipeline.review(ctx)['output_text'].startswith('# Delivery completed')
    pipeline.prepare(ctx, TABLE)
    assert len(roles.claims) == 6


@pytest.mark.parametrize('stage', ['roundtable', 'research', 'architecture', 'intake', 'plan_review'])
def test_no_stops_without_admitting_later_role(finished_table, stage):
    ctx, roles, _ = finished_table
    pipeline.prepare(ctx, TABLE)
    if stage != 'roundtable':
        decide(ctx, 'yes')
        submit(ctx)
    if stage not in ('roundtable', 'research'):
        decide(ctx, 'yes')
        submit(ctx, project_name='Delivery project')
    if stage in ('intake', 'plan_review'):
        decide(ctx, 'yes')
        complete_intake(ctx)
    if stage == 'plan_review':
        decide(ctx, 'yes')
        submit(ctx)
    before = len(roles.claims)
    assert pipeline.state(ctx, TABLE)['stage'] == stage
    assert decide(ctx, 'no')['state'] == 'stopped'
    pipeline.prepare(ctx, TABLE)
    assert len(roles.claims) == before
    with pytest.raises(Stop, match='Review the current output'):
        decide(ctx, 'yes')


def test_plan_comments_remain_in_review_and_revision_uses_fresh_planner(finished_table):
    ctx, roles, _ = finished_table
    through_plan(ctx)
    before, old = len(roles.claims), pipeline.state(ctx, TABLE)
    with pytest.raises(Stop, match='comment, revise, approve, no'):
        decide(ctx, 'yes')
    assert decide(ctx, 'comment', comment='Name migration checks.')['state'] == 'awaiting'
    assert len(roles.claims) == before
    current = pipeline.state(ctx, TABLE)
    assert current['revision'] == old['revision'] + 1 and current['digest'] == old['digest']
    assert current['feedback'] == 'Name migration checks.'
    deciding = replace(ctx, nouns={'table': TABLE, 'action': 'approve', 'digest': old['digest'],
                                   'revision': old['revision']})
    with pytest.raises(Stop, match='Review the current output'):
        pipeline.decide(deciding)
    assert decide(ctx, 'revise', comment='Include rollback steps.')['state'] == 'running'
    assert len(roles.claims) == before + 1 and roles.claims[-1]['role'] == 'planner'
    assert roles.claims[-1]['work'] != old['ticket']
    with pytest.raises(Stop, match='Review the current output'):
        decide(ctx, 'approve')
    submit(ctx, '# Revised full plan\n\nMigration checks. Rollback steps.\n')
    assert pipeline.review(ctx)['output_text'].startswith('# Revised full plan')
    assert decide(ctx, 'approve')['stage'] == 'decomposition'


def test_decisions_bind_exact_output_bytes_and_revision(finished_table):
    ctx, roles, record = finished_table
    pipeline.prepare(ctx, TABLE)
    ready = pipeline.state(ctx, TABLE)
    for changes in ({'digest': 'stale'}, {'revision': ready['revision'] - 1}):
        with pytest.raises(Stop, match='Review the current output'):
            decide(ctx, 'yes', **changes)
    (record / follow.REPORT).write_text('Unsubmitted change.\n', encoding='utf-8')
    with pytest.raises(Stop, match='The output changed'):
        pipeline.review(ctx)
    with pytest.raises(Stop, match='The output changed'):
        decide(ctx, 'yes')
    assert len(roles.claims) == 1


def test_agent_cannot_supply_person_consent(finished_table):
    ctx, roles, _ = finished_table
    pipeline.prepare(ctx, TABLE)
    ready = pipeline.state(ctx, TABLE)
    with pytest.raises(Stop, match='The person must decide'):
        pipeline.decide(replace(ctx, surface='mcp', consented=False, nouns={
            'table': TABLE, 'action': 'yes', 'digest': ready['digest'], 'revision': ready['revision']}))
    assert len(roles.claims) == 1


def test_concurrent_prepare_and_decision_reserve_one_role_per_stage(finished_table):
    ctx, roles, _ = finished_table

    def race(call):
        barrier = threading.Barrier(2)

        def invoke():
            called = replace(ctx, store=Store('source', module='roundtables'))
            barrier.wait(timeout=10)
            try:
                return call(called)
            except Stop as error:
                return error

        with ThreadPoolExecutor(max_workers=2) as workers:
            return list(workers.map(lambda _: invoke(), range(2)))

    prepared = race(lambda called: pipeline.prepare(called, TABLE))
    assert all(isinstance(one, dict) and 'error' not in one for one in prepared)
    assert len(roles.claims) == 1
    ready = pipeline.state(ctx, TABLE)
    result = race(lambda called: pipeline.decide(replace(called, nouns={
        'table': TABLE, 'action': 'yes', 'digest': ready['digest'], 'revision': ready['revision']})))
    assert sum(isinstance(one, Stop) for one in result) == 1
    assert [one['role'] for one in roles.claims] == ['roundtable_follow_through', 'researcher']
    assert len(ctx.require_store().work(limit=0).results) == 2
    pipeline.prepare(ctx, TABLE)
    assert len(roles.claims) == 2


@pytest.mark.parametrize('failure', ['missing_provider', 'claim_error'])
def test_launch_failure_recovers_existing_ticket_and_keeps_saved_result(finished_table, monkeypatch, failure):
    ctx, roles, _ = finished_table
    providers, claim = pipeline.provided, roles.claim
    if failure == 'missing_provider':
        monkeypatch.setattr(pipeline, 'provided', lambda folder, purpose: [] if purpose == 'orchestration'
                            else providers(folder, purpose))
    else:
        def refused(_ctx):
            raise Stop('Role admission failed.', 'Retry this stage.')
        monkeypatch.setattr(roles, 'claim', refused)
    failed = pipeline.prepare(ctx, TABLE)
    assert failed['error'] and failed['pipeline']['state'] == 'awaiting'
    from metaform.modules.roundtables import shown
    kept = shown(ctx, follow.Follower(ctx, TABLE).row())
    assert kept['state'] == 'ended' and kept['answer'] == 'Show saved results.'
    before = pipeline.row(ctx, TABLE)['coordinator']
    monkeypatch.setattr(pipeline, 'provided', providers)
    monkeypatch.setattr(roles, 'claim', claim)
    recovered = pipeline.prepare(ctx, TABLE)['pipeline']
    assert recovered['error'] is None and len(roles.claims) == 1
    assert len(ctx.require_store().work(limit=0).results) == 1
    if before:
        assert roles.claims[0]['work'] == before


def test_isolated_stage_publishes_canonical_output_and_denies_wrong_assignment(finished_table, tmp_path):
    ctx, _, record = finished_table
    pipeline.prepare(ctx, TABLE)
    decide(ctx, 'yes')
    kept = pipeline.row(ctx, TABLE)
    isolated = tmp_path / 'research-worktree'
    isolated.mkdir()
    source = isolated / 'research.md'
    body = '# Research\n\nSDK evidence from isolated work.\n'
    source.write_text(body, encoding='utf-8')
    called = replace(ctx, folder=isolated, nouns={'table': TABLE, 'stage': 'research', 'work': kept['work_id'],
                                                'file': 'research.md', 'origin': 'source'})
    with pytest.raises(Stop, match='not the current stage assignment'):
        pipeline.submit(replace(called, nouns={**called.nouns, 'work': 'another-ticket'}))
    ready = pipeline.submit(called)['pipeline']
    assert ready['digest'] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert (record / 'research.md').read_text(encoding='utf-8') == body
    assert pipeline.review(ctx)['output_text'] == body
    assert 'output_text' not in ready
    from metaform.modules.roundtables import shown
    assert shown(ctx, follow.Follower(ctx, TABLE).row())['pipeline'] == ready


def test_releases_discussion_seats_before_follow_through_admission(finished_table, monkeypatch):
    ctx, roles, _ = finished_table
    released, token = [], object()
    claim = roles.claim

    def admitted(called):
        assert released == [token]
        return claim(called)

    monkeypatch.setattr(roles, 'claim', admitted)
    monkeypatch.setattr(follow.signal, 'signal', lambda *_args: None)
    monkeypatch.setattr(follow, 'hold_seats', lambda *_args: [token])
    monkeypatch.setattr(follow, 'release', lambda held: released.extend(held))
    monkeypatch.setattr(follow, 'say', lambda _answer: None)
    monkeypatch.setattr(follow.Follower, 'followed_to_end', lambda *_args: None)
    assert follow.run(ctx, TABLE) == {'followed': TABLE}
    assert released == [token] and len(roles.claims) == 1
    assert roles.claims[0]['role'] == 'roundtable_follow_through'


@pytest.mark.parametrize('version', [2, 3])
def test_legacy_results_keep_evidence_without_resuming_direct_planner_route(run, tmp_path, version):
    from metaform.data import Column, Table, Tables
    from metaform.data.tables import TableTx, ensure, project_store, project_transaction
    from metaform.modules.roundtables import TABLES

    folder = tmp_path / 'legacy'
    folder.mkdir()
    run('add', 'project', 'legacy', str(folder))
    proposals = Table('proposals', place='project', key=('table_id',), columns=(
        Column('table_id', required=True), Column('state', required=True), Column('file', required=True),
        Column('work_id'), Column('digest'), Column('created', required=True)))
    legacy = Tables(version=version, tables=tuple(one for one in TABLES.tables
                                               if one.name in ('tables', 'events')) +
                    ((proposals,) if version == 3 else ()))
    file = project_store('legacy', 'roundtables')
    file.parent.mkdir(parents=True, exist_ok=True)
    with project_transaction(file, write=True) as db:
        ensure(db, file, 'roundtables', legacy, 'project')
        tx = TableTx('roundtables', legacy, write=True, opener=lambda _: (db, file, True), bound='project')
        tx.insert('tables', {'table_id': TABLE, 'topic': 'Keep completed evidence?', 'opening': '.', 'seats': [],
                             'spend': 0.0, 'state': 'ended', 'answer': 'Keep this answer.', 'answered': True,
                             'created': follow.now(), 'followed': {'saved': SAVED}})
        if version == 3:
            tx.insert('proposals', {'table_id': TABLE, 'state': 'approved', 'file': SAVED + '/proposal.md',
                                    'work_id': 'old-planner', 'digest': 'reviewed-digest', 'created': follow.now()})
        tx.insert('events', {'table_id': TABLE, 'seq': 1, 'kind': 'end', 'audience': 'person',
                             'payload': {'answer': 'Keep this answer.'}, 'at': follow.now()})
    with Store('legacy', module='roundtables').tables() as tx:
        assert tx.get('tables', {'table_id': TABLE})['answer'] == 'Keep this answer.'
        assert tx.get('events', {'table_id': TABLE, 'seq': 1})['payload'] == {'answer': 'Keep this answer.'}
        kept = tx.get('pipelines', {'table_id': TABLE})
        if version == 3:
            assert kept['stage'] == 'roundtable' and kept['state'] == 'pending'
            assert kept['work_id'] is None and kept['coordinator'] is None
            assert kept['history'][0]['legacy_proposal']['work_id'] == 'old-planner'
        else:
            assert kept is None
    with project_transaction(file, write=False) as db:
        assert db.execute('SELECT name FROM sqlite_master WHERE name=?', ('roundtables.proposals',)).fetchone() is None


def test_architecture_must_name_target_and_wrong_stage_cannot_publish(finished_table):
    ctx, _, record = finished_table
    pipeline.prepare(ctx, TABLE)
    decide(ctx, 'yes')
    submit(ctx)
    decide(ctx, 'yes')
    with pytest.raises(Stop, match='Architect must name the new project'):
        submit(ctx)
    assert not (record / 'architecture.md').exists()
    kept = pipeline.row(ctx, TABLE)
    with pytest.raises(Stop, match='not the current stage assignment'):
        pipeline.submit(replace(ctx, nouns={'table': TABLE, 'stage': 'research', 'work': kept['work_id'],
                                           'file': 'stage-output.md'}))
    assert pipeline.state(ctx, TABLE)['state'] == 'running'


def test_interrupted_intake_resumes_registered_target_without_creating_another_project(finished_table, monkeypatch):
    ctx, roles, _ = finished_table
    through_architecture(ctx)
    starter = roles.intake
    calls = []

    def interrupted(called):
        calls.append({'project': called.project, **called.nouns})
        if len(calls) == 1:
            result = starter(called)
            target = Store('target')
            target.layer('base', 'intake', 'Building target map.', kind='intake', mutable=False, hideable=False,
                         provenance={'module': 'intake'})
            return {**result, 'error': 'Intake admission interrupted.'}
        return {'project': 'target', 'folder': str(Store('target').project().path), 'work_id': 'intake-work'}

    monkeypatch.setattr(roles, 'intake', interrupted)
    assert decide(ctx, 'yes')['error'] == 'Intake admission interrupted.'
    before = pipeline.row(ctx, TABLE)
    recovered = pipeline.prepare(ctx, TABLE)['pipeline']
    assert recovered['project'] == before['project'] == 'target'
    assert recovered['folder'] == before['folder']
    assert recovered['error'] is None and recovered['state'] == 'running'
    assert len(calls) == 2
    assert calls[0]['project'] == 'source' and calls[0]['project_name'] == 'Delivery project'
    assert calls[1]['project'] == 'target' and calls[1]['resume'] is True
    assert 'project_name' not in calls[1]
    assert len(roles.intakes) == 1
    with Store('target', module='roundtables').tables(write=False) as tx:
        assert len(tx.rows('intake_links', limit=0).results) == 1


def test_noncode_intake_completion_event_presents_intake_output(finished_table, run):
    ctx, roles, _ = finished_table
    through_architecture(ctx)
    assert decide(ctx, 'yes')['state'] == 'running'
    target = Path(Store('target').project().path)
    run('intake', 'start', cwd=target)
    run('intake', 'element', 'document.delivery', 'role=DE', cwd=target)
    run('intake', 'finish', cwd=target)
    ready = pipeline.state(ctx, TABLE)
    assert ready['stage'] == 'intake' and ready['state'] == 'awaiting'
    assert ready['project'] == 'target'
    assert pipeline.review(ctx)['output_text'].startswith('# Intake\n\nProject: target')
    assert roles.claims[-1]['role'] == 'architect', 'Completion presents intake without admitting Planner.'


def test_execution_outline_no_keeps_facilitator_unassigned(finished_table):
    ctx, roles, _ = finished_table
    target = through_plan(ctx)
    decide(ctx, 'approve')
    with Store('target', module='map').tables() as tx:
        tx.insert('boards', {'name': 'pending-delivery', 'created': follow.now()})
    work = target.add_work(Node('element', ADDRESS), None, title='Pending delivery', task='Pending result.')
    target.edit_work(work.id, {'held': True, 'hold_reason': 'Wait for outline approval.'})
    with Store('target', module='map').tables() as tx:
        tx.update('ticket_settings', {'work_id': work.id}, {'board': 'pending-delivery'})
    assert submit(ctx, '# Proposed tickets\n', board='pending-delivery')['stage'] == 'execution_outline'
    assert decide(ctx, 'no')['state'] == 'stopped'
    pipeline.prepare(ctx, TABLE)
    assert 'facilitator' not in [one['role'] for one in roles.claims]
    assert target.work(ids=[work.id]).results[0].held


def test_successful_intake_launch_resumes_after_agent_dies_without_error(finished_table, monkeypatch):
    ctx, roles, _ = finished_table
    through_architecture(ctx)
    starter = roles.intake
    calls = []

    def launched(called):
        calls.append({'project': called.project, **called.nouns})
        if len(calls) == 1:
            result = starter(called)
            Store('target').layer('base', 'intake', 'Building target map.', kind='intake', mutable=False,
                                  hideable=False, provenance={'module': 'intake'})
            return result
        return {'project': 'target', 'folder': str(Store('target').project().path), 'work_id': 'intake-work'}

    monkeypatch.setattr(roles, 'intake', launched)
    ready = decide(ctx, 'yes')
    assert ready['state'] == 'running' and ready['error'] is None
    assert pipeline.prepare(ctx, TABLE)['pipeline']['state'] == 'running'
    assert len(calls) == 1 and roles.intake_status_calls == ['target']
    roles.intake_active = False
    resumed = pipeline.prepare(ctx, TABLE)['pipeline']
    assert resumed['error'] is None and resumed['project'] == ready['project'] == 'target'
    assert resumed['folder'] == ready['folder']
    assert len(calls) == 2 and calls[1]['project'] == 'target' and calls[1]['resume'] is True
    assert 'project_name' not in calls[1]
    assert len(roles.intakes) == 1
    roles.intake_active = True
    pipeline.prepare(ctx, TABLE)
    assert len(calls) == 2
    with Store('target', module='roundtables').tables(write=False) as tx:
        assert len(tx.rows('intake_links', limit=0).results) == 1


def test_replayed_publication_keeps_review_revision_artifacts_and_events(finished_table):
    ctx, roles, _ = finished_table
    pipeline.prepare(ctx, TABLE)
    decide(ctx, 'yes')
    work = pipeline.row(ctx, TABLE)['work_id']
    body = '# Research\n\nPreserve the published evidence.\n'
    ready = submit(ctx, body)
    before = pipeline.row(ctx, TABLE)
    with ctx.require_store().tables(write=False) as tx:
        events = list(tx.rows('events', {'table_id': TABLE}, limit=0).results)
    called = replace(ctx, nouns={'table': TABLE, 'stage': 'research', 'work': work, 'file': 'stage-output.md'})
    assert pipeline.submit(called)['pipeline'] == ready
    after = pipeline.row(ctx, TABLE)
    assert after['revision'] == before['revision'] and after['artifacts'] == before['artifacts']
    with ctx.require_store().tables(write=False) as tx:
        assert list(tx.rows('events', {'table_id': TABLE}, limit=0).results) == events
    (ctx.folder / 'stage-output.md').write_text(body + 'Unassigned revision.\n', encoding='utf-8')
    with pytest.raises(Stop, match='not the current stage assignment'):
        pipeline.submit(called)
    assert pipeline.state(ctx, TABLE) == ready
    assert len(roles.claims) == 2


@pytest.mark.parametrize('source', ['../outside.md', 'linked.md'])
def test_stage_publication_rejects_assignment_folder_escape(finished_table, source):
    ctx, _, record = finished_table
    pipeline.prepare(ctx, TABLE)
    decide(ctx, 'yes')
    work = pipeline.row(ctx, TABLE)['work_id']
    outside = ctx.folder.parent / 'outside.md'
    outside.write_text('Outside assignment evidence.\n', encoding='utf-8')
    (ctx.folder / 'linked.md').symlink_to(outside)
    called = replace(ctx, nouns={'table': TABLE, 'stage': 'research', 'work': work, 'file': source})
    with pytest.raises(Stop, match='inside this assignment folder'):
        pipeline.submit(called)
    assert not (record / 'research.md').exists()
    assert pipeline.state(ctx, TABLE)['state'] == 'running'


def test_intake_completion_filters_unrelated_project_bursts_before_reads(finished_table, monkeypatch):
    ctx, _, _ = finished_table
    reads = []
    original = Store.tables

    def counted(self, *args, **kwargs):
        reads.append(self.project_id)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Store, 'tables', counted)
    for payload in [{'project': 'other-project'}, {}, {'project': None}] * 100:
        assert pipeline.intake_finished(payload, ctx) is None
    assert reads == []


def test_no_after_failed_presentation_prevents_recovery_launch(finished_table, monkeypatch):
    ctx, roles, _ = finished_table
    providers = pipeline.provided
    monkeypatch.setattr(pipeline, 'provided', lambda folder, purpose: [] if purpose == 'orchestration'
                        else providers(folder, purpose))
    assert pipeline.prepare(ctx, TABLE)['error']
    assert decide(ctx, 'no')['state'] == 'stopped'
    monkeypatch.setattr(pipeline, 'provided', providers)
    assert pipeline.prepare(ctx, TABLE)['pipeline']['state'] == 'stopped'
    assert roles.claims == []
    assert ctx.require_store().work(limit=0).results == ()


def automate(ctx):
    with ctx.require_store().tables() as tx:
        discussion = tx.get('tables', {'table_id': TABLE})
        tx.update('tables', {'table_id': TABLE}, {'followed': {
            **discussion['followed'], 'automate_ticket_creation': True}})


def test_automated_preparation_populates_inactive_board_without_starting_execution(finished_table, run):
    from metaform import settings
    from metaform.module import context
    from metaform.modules import dispatch

    ctx, roles, record = finished_table
    automate(ctx)
    ready = pipeline.prepare(ctx, TABLE)['pipeline']
    assert ready['automate_ticket_creation'] is True
    assert ready['stage'] == 'research' and ready['state'] == 'running'
    assert submit(ctx)['stage'] == 'architecture'
    assert submit(ctx, project_name='Delivery project')['stage'] == 'intake'
    target = complete_intake(ctx)
    assert pipeline.state(ctx, TABLE)['stage'] == 'plan_review'
    assert submit(ctx, '# Full plan\n\nBuild delivery. Verify delivery.\n')['stage'] == 'decomposition'
    folder = Path(target.project().path)
    active = settings.value('board', folder)
    run('map', 'boards', 'op=add', 'name=prepared', cwd=folder)
    first = json.loads(run('map', 'work', 'op=add', f'node=element:{ADDRESS}', 'board=prepared',
                           'title=Build delivery', 'task=Build exact result.', '--json', cwd=folder).stdout)['id']
    second = json.loads(run('map', 'work', 'op=add', f'node=element:{ADDRESS}', 'board=prepared',
                            'title=Verify delivery', 'task=Verify exact result.', f'after_work=["{first}"]',
                            '--json', cwd=folder).stdout)['id']
    ready = submit(ctx, '# Decomposed\n', board='prepared')
    assert ready['stage'] == 'execution_outline' and ready['state'] == 'awaiting'
    assert ready['board'] == 'prepared' and settings.value('board', folder) == active != 'prepared'
    outline = json.loads((record / 'execution-outline.md').read_text().split('```json\n')[1].split('\n```')[0])
    assert {ticket['id'] for ticket in outline['tickets']} == {first, second}
    assert next(ticket for ticket in outline['tickets'] if ticket['id'] == second)['depends_on'] == [first]
    assert [one['role'] for one in roles.claims] == [
        'roundtable_follow_through', 'researcher', 'architect', 'planner', 'decomposer']
    target_dispatch = context('dispatch', folder, project='target')
    run('set', '--dispatch-autostart', cwd=folder)
    for work in (first, second):
        assert not target.work(ids=[work]).results[0].held
        with pytest.raises(dispatch.Refused, match='set aside'):
            dispatch.admit(target_dispatch, target, work, 'worker', agent='codex', auto=True)
    assert dispatch.sessions(target) == []
    before = len(roles.claims)
    pipeline.prepare(ctx, TABLE)
    assert len(roles.claims) == before
    tasks = [work.task for store in [ctx.require_store(), target] for work in store.work(limit=0).results]
    assert any('Automate Ticket Creation is enabled' in task for task in tasks)
    assert decide(ctx, 'approve')['stage'] == 'facilitation'
    assigned = target.work(ids=[roles.claims[-1]['work']]).results[0].task
    assert 'The person approved the execution outline.' in assigned
    assert 'Automate Ticket Creation is enabled' not in assigned


def test_automated_launch_failure_recovers_existing_stage(finished_table, monkeypatch):
    ctx, roles, _ = finished_table
    automate(ctx)
    claim = roles.claim

    def refuse_research(called):
        if called.nouns['role'] == 'researcher':
            raise Stop('Admission unavailable.', 'Retry preparation.')
        return claim(called)

    monkeypatch.setattr(roles, 'claim', refuse_research)
    failed = pipeline.prepare(ctx, TABLE)['pipeline']
    assert failed['stage'] == 'research' and failed['state'] == 'running' and failed['error']
    work = pipeline.row(ctx, TABLE)['work_id']
    monkeypatch.setattr(roles, 'claim', claim)
    ready = pipeline.prepare(ctx, TABLE)['pipeline']
    assert ready['error'] is None and pipeline.row(ctx, TABLE)['work_id'] == work
    assert [one['role'] for one in roles.claims] == ['roundtable_follow_through', 'researcher']


@pytest.mark.parametrize('enabled', [None, False, True])
def test_creation_persists_explicit_option_defaulting_off(finished_table, run, monkeypatch, enabled):
    from metaform.modules import roundtables

    ctx, _, _ = finished_table
    run('set', '--jev', cwd=ctx.folder)
    monkeypatch.setattr(roundtables, 'started', lambda _ctx, _table: {'opened': True})
    nouns = {'topic': 'Prepare delivery.', 'seats': ['stub/vega']}
    if enabled is not None:
        nouns['automate_ticket_creation'] = enabled
    result = roundtables.open_table(replace(ctx, surface='web', nouns=nouns))
    with ctx.require_store().tables(write=False) as tx:
        kept = tx.get('tables', {'table_id': result['table']})
    assert kept['followed']['automate_ticket_creation'] is (enabled is True)
    assert kept['followed']['opener'] == 'person'


def test_automated_replayed_output_preserves_next_assignment(finished_table):
    ctx, roles, _ = finished_table
    automate(ctx)
    pipeline.prepare(ctx, TABLE)
    work = pipeline.row(ctx, TABLE)['work_id']
    ready = submit(ctx, '# Research\n\nComplete findings.\n')
    assert ready['stage'] == 'architecture'
    before = pipeline.row(ctx, TABLE)
    called = replace(ctx, nouns={'table': TABLE, 'stage': 'research', 'work': work, 'file': 'stage-output.md'})
    assert pipeline.submit(called)['pipeline'] == ready
    assert pipeline.row(ctx, TABLE) == before
    assert len(roles.claims) == 3


@pytest.mark.parametrize('invalid', ['active', 'empty'])
def test_automated_submission_refuses_active_or_empty_board(finished_table, run, invalid):
    ctx, roles, _ = finished_table
    automate(ctx)
    pipeline.prepare(ctx, TABLE)
    submit(ctx)
    submit(ctx, project_name='Delivery project')
    target = complete_intake(ctx)
    submit(ctx)
    folder = Path(target.project().path)
    run('map', 'boards', 'op=add', 'name=prepared', cwd=folder)
    if invalid == 'active':
        run('set', '--board', 'prepared', cwd=folder)
    with pytest.raises(Stop, match='remain inactive' if invalid == 'active' else 'has no tickets'):
        submit(ctx, board='prepared')
    assert pipeline.state(ctx, TABLE)['stage'] == 'decomposition'
    assert 'facilitator' not in [one['role'] for one in roles.claims]


def test_version_four_pipeline_keeps_manual_mode_after_upgrade(run, tmp_path):
    from metaform.data import Tables
    from metaform.data.tables import TableTx, ensure, project_store, project_transaction
    from metaform.modules.roundtables import TABLES

    folder = tmp_path / 'version-four'
    folder.mkdir()
    run('add', 'project', 'version-four', str(folder))
    legacy = Tables(version=4, compatible_from=4, tables=tuple(
        replace(table, columns=tuple(column for column in table.columns if column.name != 'automate_ticket_creation'))
        for table in TABLES.tables))
    file = project_store('version-four', 'roundtables')
    file.parent.mkdir(parents=True, exist_ok=True)
    with project_transaction(file, write=True) as db:
        ensure(db, file, 'roundtables', legacy, 'project')
        tx = TableTx('roundtables', legacy, write=True, opener=lambda _: (db, file, True), bound='project')
        tx.insert('pipelines', {'table_id': TABLE, 'stage': 'plan_review', 'state': 'awaiting',
                               'work_id': 'existing-planner', 'digest': 'reviewed-plan', 'revision': 6,
                               'created': follow.now()})
    with Store('version-four', module='roundtables').tables(write=False) as tx:
        kept = tx.get('pipelines', {'table_id': TABLE})
    assert kept['automate_ticket_creation'] is False
    assert kept['stage'] == 'plan_review' and kept['state'] == 'awaiting'
    assert kept['work_id'] == 'existing-planner' and kept['revision'] == 6 and kept['digest'] == 'reviewed-plan'
