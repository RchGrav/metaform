"""Finished discussions advance through assigned tasks and retain reviewed stage decisions."""
from __future__ import annotations

import hashlib
import importlib
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
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
    """Real source/target stores with deterministic task execution."""
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

    class TaskRunner:
        def __init__(self):
            self.assignments = {}
            self.launches = []
            self.intakes = []
            self.intake_active = True
            self.intake_status_calls = []

        def assignment(self, _ctx, task_id):
            return self.assignments.get(task_id)

        def get(self, _ctx, task_id):
            return self.assignments.get(task_id)

        def assign(self, ctx, _name, _component, *, request_key):
            reference = ctx.nouns['options']['roundtable']
            called = replace(ctx, nouns={**ctx.nouns, 'role': pipeline.ROLES[reference['stage']],
                                         'work': reference['work'], 'automatic': False})
            return self.start(called)

        def start(self, ctx):
            self.launches.append({'project': ctx.project, **ctx.nouns})
            result = {'task_id': f'task-{len(self.launches)}', 'state': 'working', 'role': ctx.nouns['role'],
                      'work_id': ctx.nouns['work']}
            self.assignments[result['task_id']] = result
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

    runner = TaskRunner()

    def providers(_folder, purpose):
        if purpose == 'task.lifecycle':
            return [('tasks', runner)]
        if purpose == 'dispatch.design_intake':
            return [('dispatch', runner.intake)]
        if purpose == 'dispatch.design_intake_active':
            return [('dispatch', runner.intake_status)]
        raise AssertionError(f'Unexpected provider: {purpose}')

    monkeypatch.setattr(pipeline, 'provided', providers)
    from metaform.modules.roundtables import pipeline as current_pipeline
    monkeypatch.setattr(current_pipeline, 'provided', providers)
    ctx = Context('roundtables', folder, project='source', store=store, nouns={'table': TABLE})
    return ctx, runner, record


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


def test_finished_table_is_presented_without_a_coordinator_agent(finished_table):
    ctx, runner, record = finished_table
    first = pipeline.prepare(ctx, TABLE)
    second = pipeline.prepare(ctx, TABLE)
    assert first['pipeline'] == second['pipeline']
    assert first['pipeline']['stage'] == 'roundtable' and first['pipeline']['state'] == 'awaiting'
    assert first['pipeline']['question']
    assert runner.launches == []
    assert ctx.require_store().work(limit=0).results == ()
    assert pipeline.row(ctx, TABLE)['coordinator'] is None
    assert 'output_text' not in first['pipeline']
    assert pipeline.review(ctx)['output_text'] == (record / follow.REPORT).read_text(encoding='utf-8')
    with ctx.require_store().tables(write=False) as tx:
        events = tx.rows('events', {'table_id': TABLE}, limit=0).results
    assert events[-1]['payload']['pipeline'] == first['pipeline']


def test_yes_chain_runs_each_task_and_requires_execution_outline_approval(finished_table):
    ctx, runner, record = finished_table
    through_architecture(ctx)
    assert [one['role'] for one in runner.launches] == ['researcher', 'architect']
    assert decide(ctx, 'yes')['stage'] == 'intake'
    assert runner.intakes == [{'project_name': 'Delivery project', 'text': '# architecture\n\nComplete stage evidence.\n'}]
    assert pipeline.state(ctx, TABLE)['state'] == 'running'
    target = complete_intake(ctx)
    assert pipeline.state(ctx, TABLE)['stage'] == 'intake'
    assert pipeline.state(ctx, TABLE)['state'] == 'awaiting'
    assert pipeline.review(ctx)['output_text'].startswith('# Intake\n\nProject: target')
    assert decide(ctx, 'yes')['stage'] == 'plan_review'
    assert runner.launches[-1]['role'] == 'planner' and runner.launches[-1]['project'] == 'target'
    plan = '# Full plan\n\n1. Preserve every requirement.\n2. Build delivery.\n'
    ready = submit(ctx, plan)
    assert ready['stage'] == 'plan_review' and pipeline.review(ctx)['output_text'] == plan
    assert 'decomposer' not in [one['role'] for one in runner.launches]
    assert decide(ctx, 'approve')['stage'] == 'decomposition'
    assert runner.launches[-1]['role'] == 'decomposer'
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
    assert 'facilitator' not in [one['role'] for one in runner.launches]
    with pytest.raises(Stop, match='approve, no'):
        decide(ctx, 'yes')
    assert decide(ctx, 'approve')['stage'] == 'facilitation'
    assert [one['role'] for one in runner.launches] == [
        'researcher', 'architect', 'planner', 'decomposer', 'facilitator']
    stage_launches = runner.launches
    assert all(one['automatic'] is False for one in stage_launches)
    assert len({one['work'] for one in runner.launches}) == len(runner.launches)
    assert submit(ctx, '# Delivery completed\n\nPaired work passed peer review.\n')['state'] == 'completed'
    assert pipeline.review(ctx)['output_text'].startswith('# Delivery completed')
    pipeline.prepare(ctx, TABLE)
    assert len(runner.launches) == 5


@pytest.mark.parametrize('stage', ['roundtable', 'research', 'architecture', 'intake', 'plan_review'])
def test_no_stops_without_admitting_later_task(finished_table, stage):
    ctx, runner, _ = finished_table
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
    before = len(runner.launches)
    assert pipeline.state(ctx, TABLE)['stage'] == stage
    assert decide(ctx, 'no')['state'] == 'stopped'
    pipeline.prepare(ctx, TABLE)
    assert len(runner.launches) == before
    with pytest.raises(Stop, match='Review the current output'):
        decide(ctx, 'yes')


def test_plan_comments_remain_in_review_and_revision_uses_fresh_planner(finished_table):
    ctx, runner, _ = finished_table
    through_plan(ctx)
    before, old = len(runner.launches), pipeline.state(ctx, TABLE)
    with pytest.raises(Stop, match='comment, revise, approve, no'):
        decide(ctx, 'yes')
    assert decide(ctx, 'comment', comment='Name migration checks.')['state'] == 'awaiting'
    assert len(runner.launches) == before
    current = pipeline.state(ctx, TABLE)
    assert current['revision'] == old['revision'] + 1 and current['digest'] == old['digest']
    assert current['feedback'] == 'Name migration checks.'
    deciding = replace(ctx, nouns={'table': TABLE, 'action': 'approve', 'digest': old['digest'],
                                   'revision': old['revision']})
    with pytest.raises(Stop, match='Review the current output'):
        pipeline.decide(deciding)
    assert decide(ctx, 'revise', comment='Include rollback steps.')['state'] == 'running'
    assert len(runner.launches) == before + 1 and runner.launches[-1]['role'] == 'planner'
    assert runner.launches[-1]['work'] != old['ticket']
    with pytest.raises(Stop, match='Review the current output'):
        decide(ctx, 'approve')
    submit(ctx, '# Revised full plan\n\nMigration checks. Rollback steps.\n')
    assert pipeline.review(ctx)['output_text'].startswith('# Revised full plan')
    assert decide(ctx, 'approve')['stage'] == 'decomposition'


def test_decisions_bind_exact_output_bytes_and_revision(finished_table):
    ctx, runner, record = finished_table
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
    assert len(runner.launches) == 0


def test_concurrent_prepare_and_decision_reserve_one_task_per_stage(finished_table):
    ctx, runner, _ = finished_table

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
    assert len(runner.launches) == 0
    ready = pipeline.state(ctx, TABLE)
    result = race(lambda called: pipeline.decide(replace(called, nouns={
        'table': TABLE, 'action': 'yes', 'digest': ready['digest'], 'revision': ready['revision']})))
    assert sum(isinstance(one, Stop) for one in result) == 1
    assert [one['role'] for one in runner.launches] == ['researcher']
    assert len(ctx.require_store().work(limit=0).results) == 1
    pipeline.prepare(ctx, TABLE)
    assert len(runner.launches) == 1


@pytest.mark.parametrize('failure', ['missing_provider', 'claim_error'])
def test_launch_failure_recovers_existing_ticket_and_keeps_saved_result(finished_table, monkeypatch, failure):
    ctx, runner, _ = finished_table
    pipeline.prepare(ctx, TABLE)
    providers, claim = pipeline.provided, runner.start
    if failure == 'missing_provider':
        monkeypatch.setattr(pipeline, 'provided', lambda folder, purpose: [] if purpose == 'task.lifecycle'
                            else providers(folder, purpose))
    else:
        def refused(_ctx):
            raise Stop('Role admission failed.', 'Retry this stage.')
        monkeypatch.setattr(runner, 'start', refused)
    failed = decide(ctx, 'yes')
    assert failed['error'] and failed['state'] == 'running'
    from metaform.modules.roundtables import shown
    kept = shown(ctx, follow.Follower(ctx, TABLE).row())
    assert kept['state'] == 'ended' and kept['answer'] == 'Show saved results.'
    before = pipeline.row(ctx, TABLE)['work_id']
    monkeypatch.setattr(pipeline, 'provided', providers)
    monkeypatch.setattr(runner, 'start', claim)
    recovered = pipeline.prepare(ctx, TABLE)['pipeline']
    assert recovered['error'] is None and len(runner.launches) == 1
    assert len(ctx.require_store().work(limit=0).results) == 1
    if before:
        assert runner.launches[0]['work'] == before


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


def test_releases_discussion_seats_before_automated_preparation(finished_table, monkeypatch):
    ctx, runner, _ = finished_table
    automate(ctx)
    released, token = [], object()
    claim = runner.start

    def admitted(called):
        assert released == [token]
        return claim(called)

    monkeypatch.setattr(runner, 'start', admitted)
    monkeypatch.setattr(follow.signal, 'signal', lambda *_args: None)
    monkeypatch.setattr(follow, 'hold_seats', lambda *_args: [token])
    monkeypatch.setattr(follow, 'release', lambda held: released.extend(held))
    monkeypatch.setattr(follow, 'say', lambda _answer: None)
    monkeypatch.setattr(follow.Follower, 'followed_to_end', lambda *_args: None)
    assert follow.run(ctx, TABLE) == {'followed': TABLE}
    assert released == [token] and len(runner.launches) == 1
    assert runner.launches[0]['role'] == 'researcher'


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
    ctx, runner, _ = finished_table
    through_architecture(ctx)
    starter = runner.intake
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

    monkeypatch.setattr(runner, 'intake', interrupted)
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
    assert len(runner.intakes) == 1
    with Store('target', module='roundtables').tables(write=False) as tx:
        assert len(tx.rows('intake_links', limit=0).results) == 1


def test_execution_outline_no_keeps_facilitator_unassigned(finished_table):
    ctx, runner, _ = finished_table
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
    assert 'facilitator' not in [one['role'] for one in runner.launches]
    assert target.work(ids=[work.id]).results[0].held


def test_successful_intake_launch_resumes_after_agent_dies_without_error(finished_table, monkeypatch):
    ctx, runner, _ = finished_table
    through_architecture(ctx)
    starter = runner.intake
    calls = []

    def launched(called):
        calls.append({'project': called.project, **called.nouns})
        if len(calls) == 1:
            result = starter(called)
            Store('target').layer('base', 'intake', 'Building target map.', kind='intake', mutable=False,
                                  hideable=False, provenance={'module': 'intake'})
            return result
        return {'project': 'target', 'folder': str(Store('target').project().path), 'work_id': 'intake-work'}

    monkeypatch.setattr(runner, 'intake', launched)
    ready = decide(ctx, 'yes')
    assert ready['state'] == 'running' and ready['error'] is None
    assert pipeline.prepare(ctx, TABLE)['pipeline']['state'] == 'running'
    assert len(calls) == 1 and runner.intake_status_calls == ['target']
    runner.intake_active = False
    resumed = pipeline.prepare(ctx, TABLE)['pipeline']
    assert resumed['error'] is None and resumed['project'] == ready['project'] == 'target'
    assert resumed['folder'] == ready['folder']
    assert len(calls) == 2 and calls[1]['project'] == 'target' and calls[1]['resume'] is True
    assert 'project_name' not in calls[1]
    assert len(runner.intakes) == 1
    runner.intake_active = True
    pipeline.prepare(ctx, TABLE)
    assert len(calls) == 2
    with Store('target', module='roundtables').tables(write=False) as tx:
        assert len(tx.rows('intake_links', limit=0).results) == 1


def test_replayed_publication_keeps_review_revision_artifacts_and_events(finished_table):
    ctx, runner, _ = finished_table
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
    assert len(runner.launches) == 1


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


def test_stopping_result_needs_no_task_provider_and_prevents_later_launch(finished_table, monkeypatch):
    ctx, runner, _ = finished_table
    providers = pipeline.provided
    monkeypatch.setattr(pipeline, 'provided', lambda folder, purpose: [] if purpose == 'task.lifecycle'
                        else providers(folder, purpose))
    assert pipeline.prepare(ctx, TABLE)['pipeline']['error'] is None
    assert decide(ctx, 'no')['state'] == 'stopped'
    monkeypatch.setattr(pipeline, 'provided', providers)
    assert pipeline.prepare(ctx, TABLE)['pipeline']['state'] == 'stopped'
    assert runner.launches == []
    assert ctx.require_store().work(limit=0).results == ()


def automate(ctx):
    with ctx.require_store().tables() as tx:
        discussion = tx.get('tables', {'table_id': TABLE})
        tx.update('tables', {'table_id': TABLE}, {'followed': {
            **discussion['followed'], 'automate_ticket_creation': True}})


@pytest.fixture
def assigned_pipeline(finished_table, monkeypatch):
    """The real current task lifecycle, with only native process execution replaced."""
    from metaform import loader

    runtime = importlib.import_module('metaform.modules.tasks.runtime')
    lifecycle = runtime.Lifecycle()

    class Native:
        def __init__(self):
            self.started = []
            self.full = False

        def start(self, _ctx, task):
            if self.full:
                raise Stop('No free agent slots.', 'Wait for a slot.')
            self.started.append(deepcopy(task))
            return {'session_id': f'native-{len(self.started)}'}

        def inspect(self, _ctx, _task):
            return {'state': 'working', 'inputs': {}}

    native = Native()
    monkeypatch.setattr(runtime, 'transport', lambda _ctx: native)
    providers = pipeline.provided

    def current(folder, purpose):
        if purpose == 'task.lifecycle':
            return [('tasks', lifecycle)]
        return providers(folder, purpose)

    monkeypatch.setattr(pipeline, 'provided', current)
    monkeypatch.setattr(importlib.import_module('metaform.modules.roundtables.pipeline'), 'provided', current)
    for module in loader.enabled():
        if module.id == 'roundtables':
            for subscription in module.subscriptions:
                monkeypatch.setitem(subscription.handler.__globals__, 'provided', current)
    return finished_table[0], lifecycle, native


def test_current_tasks_run_automated_stages_without_a_coordinator_and_wait_for_outline(assigned_pipeline, run):
    ctx, lifecycle, native = assigned_pipeline
    automate(ctx)
    assert pipeline.prepare(ctx, TABLE)['pipeline']['stage'] == 'research'
    assert len(native.started) == 1
    assert native.started[0]['name'] == 'roundtable_stage'
    assert 'work=YOUR_TICKET' not in native.started[0]['payload']['instructions']
    submit(ctx)
    submit(ctx, project_name='Delivery project')
    mapped = complete_intake(ctx)
    submit(ctx, '# Full plan\n\nBuild and verify delivery.\n')
    folder = Path(mapped.project().path)
    run('map', 'boards', 'op=add', 'name=prepared', cwd=folder)
    run('map', 'work', 'op=add', f'node=element:{ADDRESS}', 'board=prepared',
        'title=Build delivery', 'task=Build and verify delivery.', cwd=folder)
    ready = submit(ctx, '# Decomposition\n', board='prepared')
    assert ready['stage'] == 'execution_outline' and ready['state'] == 'awaiting'
    assert [one['payload']['options']['roundtable']['stage'] for one in native.started] == [
        'research', 'architecture', 'plan_review', 'decomposition']
    pipeline.prepare(ctx, TABLE)
    assert len(native.started) == 4
    decide(ctx, 'approve')
    assert len(native.started) == 5
    assert native.started[-1]['payload']['options']['roundtable']['stage'] == 'facilitation'
    assert lifecycle.assignment(ctx, native.started[-1]['task_id'])['cwd'] == str(folder)
    assert submit(ctx, '# Delivered\n\nThe planned work and peer review are complete.\n')['state'] == 'completed'


def test_lost_task_launch_reply_recovers_the_same_stage_task(assigned_pipeline, monkeypatch):
    ctx, lifecycle, native = assigned_pipeline
    automate(ctx)
    assign = lifecycle.assign

    def lost_reply(*args, **kwargs):
        assign(*args, **kwargs)
        raise OSError('The launch reply was lost.')

    monkeypatch.setattr(lifecycle, 'assign', lost_reply)
    failed = pipeline.prepare(ctx, TABLE)['pipeline']
    assert failed['stage'] == 'research' and failed['error']
    work = failed['ticket']
    monkeypatch.setattr(lifecycle, 'assign', assign)
    pipeline.change(ctx, TABLE, error=None)  # A hard crash need not leave an error before its next event.
    pipeline.tasks_changed({'project': 'source', 'tables': 'dispatch', 'kinds': ['session'], 'work_ids': ['ended']}, ctx)
    recovered = pipeline.state(ctx, TABLE)
    assert recovered['error'] is None and recovered['ticket'] == work
    assert len(native.started) == 1
    assert len(ctx.require_store().work(limit=0).results) == 1


def test_cancelled_stage_task_is_preserved_and_never_restarted(finished_table):
    ctx, runner, _ = finished_table
    automate(ctx)
    pipeline.prepare(ctx, TABLE)
    task = next(iter(runner.assignments.values()))
    task.update(state='cancelled', cancel_requested=True)
    stopped = pipeline.prepare(ctx, TABLE)['pipeline']
    assert stopped['state'] == 'stopped'
    pipeline.prepare(ctx, TABLE)
    assert len(runner.launches) == 1


def test_target_session_completion_retries_only_pending_source_pipeline_stage(assigned_pipeline):
    ctx, _lifecycle, native = assigned_pipeline
    automate(ctx)
    pipeline.prepare(ctx, TABLE)
    submit(ctx)
    submit(ctx, project_name='Delivery project')
    native.full = True
    mapped = complete_intake(ctx)
    failed = pipeline.row(ctx, TABLE)
    assert failed['stage'] == 'plan_review' and failed['error']
    work = failed['work_id']
    reopened = Store('target', module='roundtables')
    with reopened.tables(write=False) as tx:
        pending = tx.rows('pending_stages', limit=0).results
    assert len(pending) == 1 and pending[0]['work_id'] == work
    called = replace(ctx, project='target', folder=Path(mapped.project().path), store=reopened)
    native.full = False
    event = {'project': 'target', 'tables': ['dispatch.sessions'], 'kinds': ['session'],
             'work_ids': ['some-completed-task']}
    pipeline.tasks_changed(event, called)
    recovered = pipeline.row(ctx, TABLE)
    assert recovered['error'] is None and recovered['work_id'] == work
    assert native.started[-1]['payload']['options']['roundtable']['stage'] == 'plan_review'
    assert len(native.started) == 3
    pipeline.tasks_changed(event, called)
    assert len(native.started) == 3
    with reopened.tables(write=False) as tx:
        assert tx.rows('pending_stages', limit=0).results == ()


def test_slot_release_wake_runs_after_the_actual_runner_ledger_is_removed(assigned_pipeline, monkeypatch):
    import asyncio

    from metaform import settings
    from metaform.module import context
    from metaform.modules import dispatch
    from metaform.modules.dispatch import runner
    from metaform.modules.dispatch.recovery import identity

    ctx, _, native = assigned_pipeline
    settings.put('dispatch_machine_agents', 1, ctx.folder)
    dispatch.ledger().mkdir(parents=True, exist_ok=True)
    entry = dispatch.ledger() / f'{os.getpid()}.json'
    entry.write_text(json.dumps({'pid': os.getpid(), 'born': identity(os.getpid()), 'project': 'source',
                                'work_id': 'ending-task', 'agent': 'codex', 'kind': 'summoned'}))
    start = native.start

    def admitted(called, task):
        admission = context('dispatch', called.folder, project='source', nouns={'prep': True})
        dispatch.admit(admission, admission.require_store(), task['work_id'], 'summoned', agent='codex',
                       asked=task['payload']['options']['requested_at'])
        return start(called, task)

    monkeypatch.setattr(native, 'start', admitted)
    automate(ctx)
    assert pipeline.prepare(ctx, TABLE)['pipeline']['error']
    assert native.started == []
    observations = []
    deliveries = []
    publish = Context.publish_async

    async def observed_publish(called, topic, payload=None):
        result = await publish(called, topic, payload)
        deliveries.append(result)
        return result

    monkeypatch.setattr(Context, 'publish_async', observed_publish)

    async def ended(called):
        observations.append(entry.exists())
        await called.publish_async('map.changed', {'project': 'source', 'tables': 'dispatch',
                                                  'kinds': ['session'], 'work_ids': ['ending-task']})
        assert native.started == [], 'Session end alone has not released runner capacity.'
        return {'ended': 'completed'}

    monkeypatch.setattr(runner, 'sessions_run', ended)
    monkeypatch.setattr(runner, 'hold_lease', lambda: None)
    monkeypatch.setattr(runner, 'let_lease_go', lambda _lease: observations.append(entry.exists()))
    called = context('dispatch', ctx.folder, project='source', nouns={'id': 'ending-task'})
    asyncio.run(runner.dispatch(called))
    assert observations == [True, False]
    assert len(native.started) == 1 and pipeline.row(ctx, TABLE)['error'] is None, pipeline.row(ctx, TABLE)['error']


def test_slot_retry_preserves_a_later_user_halt(assigned_pipeline, monkeypatch):
    from metaform.module import context
    from metaform.modules import dispatch

    ctx, _, native = assigned_pipeline
    automate(ctx)
    native.full = True
    assert pipeline.prepare(ctx, TABLE)['pipeline']['error']
    original = pipeline.row(ctx, TABLE)['history'][-1]['asked']
    stopped = dispatch.halt('source', 'stop_all')
    assert stopped['at'] > original
    native.full = False
    start = native.start

    def admitted(called, task):
        admission = context('dispatch', called.folder, project='source', nouns={'prep': True})
        dispatch.admit(admission, admission.require_store(), task['work_id'], 'summoned', agent='codex',
                       asked=task['payload']['options']['requested_at'])
        return start(called, task)

    monkeypatch.setattr(native, 'start', admitted)
    pipeline.tasks_changed({'project': 'source', 'tables': 'dispatch', 'kinds': ['session'], 'work_ids': ['ended']}, ctx)
    assert native.started == []
    kept = pipeline.row(ctx, TABLE)
    assert 'came after this start was asked for' in kept['error']
    assert {one['asked'] for one in kept['history'] if one.get('event') == 'stage_task'} == {original}


def test_committed_target_reservation_recovers_a_lost_source_pointer(assigned_pipeline, monkeypatch):
    ctx, _, native = assigned_pipeline
    automate(ctx)
    pipeline.prepare(ctx, TABLE)
    submit(ctx)
    submit(ctx, project_name='Delivery project')
    change = pipeline.change

    def interrupted(called, table, **values):
        if values.get('work_id') and pipeline.row(called, table)['stage'] == 'plan_review':
            raise OSError('Source pointer commit interrupted.')
        return change(called, table, **values)

    monkeypatch.setattr(pipeline, 'change', interrupted)
    mapped = complete_intake(ctx)
    assert pipeline.row(ctx, TABLE)['work_id'] is None
    with mapped.tables(write=False) as tx:
        reserved = tx.rows('pending_stages', limit=0).results[0]['work_id']
    assert mapped.work(ids=[reserved]).results
    before = len(mapped.work(limit=0).results)
    monkeypatch.setattr(pipeline, 'change', change)
    called = replace(ctx, project='target', folder=Path(mapped.project().path), store=mapped)
    pipeline.tasks_changed({'project': 'target', 'tables': 'dispatch', 'kinds': ['session'], 'work_ids': ['ended']}, called)
    kept = pipeline.row(ctx, TABLE)
    assert kept['work_id'] == reserved and kept['error'] is None
    assert len(mapped.work(limit=0).results) == before and len(native.started) == 3


def test_unrelated_events_do_not_read_pipeline_or_task_stores(finished_table, monkeypatch):
    ctx, _, _ = finished_table

    def unexpected(*_args, **_kwargs):
        raise AssertionError('An unrelated event must be ignored before reading.')

    monkeypatch.setattr(Store, 'tables', unexpected)
    for payload in ({}, {'project': 'other', 'tables': 'dispatch', 'kinds': ['session'], 'work_ids': ['task']},
                    {'project': 'source', 'tables': ['map.work'], 'kinds': ['ticket'], 'work_ids': ['task']},
                    {'project': 'source', 'tables': 'dispatch', 'kinds': ['session']},
                    {'project': 'source', 'tables': 'dispatch', 'kinds': ['spend'], 'work_ids': ['task']}):
        pipeline.tasks_changed(payload, ctx)


def test_stopped_pipeline_drops_pending_launch_and_cannot_be_revived(finished_table):
    ctx, runner, _ = finished_table
    pipeline.prepare(ctx, TABLE)
    with ctx.require_store().tables() as tx:
        tx.insert('pending_stages', {'origin': 'source', 'table_id': TABLE, 'stage': 'research', 'work_id': 'old'})
    assert decide(ctx, 'no')['state'] == 'stopped'
    with ctx.require_store().tables(write=False) as tx:
        assert tx.rows('pending_stages', limit=0).results == ()
    pipeline.tasks_changed({'project': 'source', 'tables': 'dispatch', 'kinds': ['session'], 'work_ids': ['task']}, ctx)
    assert runner.launches == [] and pipeline.row(ctx, TABLE)['state'] == 'stopped'


def test_automated_preparation_populates_inactive_board_without_starting_execution(finished_table, run):
    from metaform import settings
    ctx, runner, record = finished_table
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
    assert [one['role'] for one in runner.launches] == [
        'researcher', 'architect', 'planner', 'decomposer']
    for work in (first, second):
        assert not target.work(ids=[work]).results[0].held
    assert settings.value('board', folder) != 'prepared'
    before = len(runner.launches)
    pipeline.prepare(ctx, TABLE)
    assert len(runner.launches) == before
    tasks = [work.task for store in [ctx.require_store(), target] for work in store.work(limit=0).results]
    assert any('Automate Ticket Creation is enabled' in task for task in tasks)
    assert decide(ctx, 'approve')['stage'] == 'facilitation'
    assigned = target.work(ids=[runner.launches[-1]['work']]).results[0].task
    assert 'The person approved the execution outline.' in assigned
    assert 'Automate Ticket Creation is enabled' not in assigned


def test_automated_launch_failure_recovers_existing_stage(finished_table, monkeypatch):
    ctx, runner, _ = finished_table
    automate(ctx)
    claim = runner.start

    def refuse_research(called):
        if called.nouns['role'] == 'researcher':
            raise Stop('Admission unavailable.', 'Retry preparation.')
        return claim(called)

    monkeypatch.setattr(runner, 'start', refuse_research)
    failed = pipeline.prepare(ctx, TABLE)['pipeline']
    assert failed['stage'] == 'research' and failed['state'] == 'running' and failed['error']
    work = pipeline.row(ctx, TABLE)['work_id']
    monkeypatch.setattr(runner, 'start', claim)
    ready = pipeline.prepare(ctx, TABLE)['pipeline']
    assert ready['error'] is None and pipeline.row(ctx, TABLE)['work_id'] == work
    assert [one['role'] for one in runner.launches] == ['researcher']


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
    ctx, runner, _ = finished_table
    automate(ctx)
    pipeline.prepare(ctx, TABLE)
    work = pipeline.row(ctx, TABLE)['work_id']
    ready = submit(ctx, '# Research\n\nComplete findings.\n')
    assert ready['stage'] == 'architecture'
    before = pipeline.row(ctx, TABLE)
    called = replace(ctx, nouns={'table': TABLE, 'stage': 'research', 'work': work, 'file': 'stage-output.md'})
    assert pipeline.submit(called)['pipeline'] == ready
    assert pipeline.row(ctx, TABLE) == before
    assert len(runner.launches) == 2


@pytest.mark.parametrize('invalid', ['active', 'empty'])
def test_automated_submission_refuses_active_or_empty_board(finished_table, run, invalid):
    ctx, runner, _ = finished_table
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
    assert 'facilitator' not in [one['role'] for one in runner.launches]


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


def test_version_five_upgrade_preserves_pipeline_and_adds_only_pending_launch_storage(run, tmp_path):
    from metaform.data import Tables
    from metaform.data.tables import TableTx, ensure, project_store, project_transaction
    from metaform.modules.roundtables import TABLES

    folder = tmp_path / 'version-five'
    folder.mkdir()
    run('add', 'project', 'version-five', str(folder))
    legacy = Tables(version=5, compatible_from=5, tables=tuple(
        table for table in TABLES.tables if table.name != 'pending_stages'))
    file = project_store('version-five', 'roundtables')
    file.parent.mkdir(parents=True, exist_ok=True)
    artifacts = [{'stage': 'research', 'file': 'research.md', 'digest': 'unchanged'}]
    with project_transaction(file, write=True) as db:
        ensure(db, file, 'roundtables', legacy, 'project')
        tx = TableTx('roundtables', legacy, write=True, opener=lambda _: (db, file, True), bound='project')
        tx.insert('pipelines', {'table_id': TABLE, 'stage': 'research', 'state': 'awaiting',
                               'digest': 'unchanged', 'revision': 7, 'artifacts': artifacts, 'created': follow.now()})
    with Store('version-five', module='roundtables').tables(write=False) as tx:
        kept = tx.get('pipelines', {'table_id': TABLE})
        assert tx.rows('pending_stages', limit=0).results == ()
    assert kept['artifacts'] == artifacts and kept['digest'] == 'unchanged' and kept['revision'] == 7
