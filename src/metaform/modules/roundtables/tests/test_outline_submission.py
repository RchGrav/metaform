"""Decomposer submission produces the board outline that the person reviews."""
from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from metaform.data import Node, Store
from metaform.modules.roundtables import pipeline
from metaform.modules.roundtables.tests.test_execution_outline import decomposed  # noqa: F401

pytestmark = pytest.mark.kind('fixture')


@pytest.mark.parametrize('new_project', [False, True])
def test_decomposer_submission_writes_complete_outline_for_person_review(
        decomposed, monkeypatch, run, tmp_path, new_project):  # noqa: F811
    ctx, expected, plan = decomposed
    project = 'outline'
    if new_project:
        project = 'target'
        folder = tmp_path / 'target'
        folder.mkdir()
        run('add', 'project', project, str(folder))
        target = Store(project, module='map')
        with target.atomic():
            target.layer('base', 'intake', 'Target map.', kind='intake', mutable=False, hideable=False,
                         provenance={'module': 'intake'}, ready=True)
            target.add_element('base', 'code.target', name_length=1, role='DE')
            work = target.add_work(Node('element', 'code.target'), None, title='Target ticket', task='Target result.')
            with target.tables() as tx:
                tx.insert('boards', {'name': 'delivery', 'created': '2026-10-22T00:00:00Z'})
                tx.insert('ticket_settings', {'work_id': work.id, 'board': 'delivery'})
        expected = [{'id': work.id, 'title': 'Target ticket', 'depends_on': [], 'expected_outcome': 'Target result.'}]
    source = plan.with_name('decomposition.md')
    source.write_text('The board is ready. Agent prose is not the execution outline.', encoding='utf-8')
    store = Store('outline', module='roundtables')
    with store.tables() as tx:
        tx.insert('tables', {'table_id': 'outline-table', 'address': 'code.delivery', 'topic': 'Deliver the plan.',
                             'opening': '.', 'seats': [], 'spend': 0.0, 'state': 'ended',
                             'created': '2026-10-22T00:00:00Z', 'followed': {'saved': 'docs'}})
        tx.insert('pipelines', {'table_id': 'outline-table', 'stage': 'decomposition', 'state': 'running',
                                'work_id': 'decomposer-ticket', 'project': project,
                                'created': '2026-10-22T00:00:00Z'})
    ctx = replace(ctx, store=store, nouns={'table': 'outline-table', 'stage': 'decomposition',
                                         'work': 'decomposer-ticket', 'file': 'docs/decomposition.md',
                                         'board': 'delivery'})

    def no_agent(*args, **kwargs):
        raise AssertionError('Generating an execution outline must not ask an agent.')

    monkeypatch.setattr(pipeline, 'provided', no_agent)
    submitted = pipeline.submit(ctx)
    assert submitted['pipeline']['stage'] == 'execution_outline'
    assert submitted['pipeline']['state'] == 'awaiting'
    assert submitted['pipeline']['file'] == 'docs/execution-outline.md'
    reviewed = pipeline.review(ctx)
    body = plan.with_name('execution-outline.md').read_bytes()
    assert reviewed['output_text'] == body.decode('utf-8')
    assert reviewed['pipeline']['digest'] == hashlib.sha256(body).hexdigest()
    snapshot = json.loads(reviewed['output_text'].split('```json\n', 1)[1].split('\n```', 1)[0])
    assert {one['id']: one for one in snapshot['tickets']} == {one['id']: one for one in expected}
    assert snapshot['plan'] == 'docs/plan.md'
    assert snapshot['board'] == 'delivery'
    assert snapshot['project'] == project
    assert plan.read_text(encoding='utf-8') == '# Reviewed plan\n'
    assert not any('Agent prose' in one['expected_outcome'] for one in snapshot['tickets'])
