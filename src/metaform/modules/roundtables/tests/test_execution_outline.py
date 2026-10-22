"""The execution outline preserves the actual board rather than an agent's reconstruction."""
from __future__ import annotations

import json
from dataclasses import replace

import pytest

from metaform.data import Node, Store
from metaform.module import Context, Stop
from metaform.modules.roundtables import execution_outline

pytestmark = pytest.mark.kind('fixture')


@pytest.fixture
def decomposed(run, tmp_path):
    folder = tmp_path / 'project'
    folder.mkdir()
    run('add', 'project', 'outline', str(folder))
    store = Store('outline', module='map')
    expected = []
    with store.atomic():
        store.layer('base', 'intake', 'Fixture map.', kind='intake', mutable=False, hideable=False,
                    provenance={'module': 'intake'}, ready=True)
        store.add_element('base', 'code.delivery', name_length=1, role='DE')
        with store.tables() as tx:
            tx.insert('boards', {'name': 'delivery', 'created': '2026-10-22T00:00:00Z'})
        # More than the usual page ensures the outline cannot silently omit later tickets.
        for number in range(53):
            title = f'Step {number}: preserve café output'
            task = f'Expected result {number}.\nKeep `depends_on` exact.'
            work = store.add_work(Node('element', 'code.delivery'), None, task=task, title=title)
            depends = [expected[-1]['id']] if expected else []
            with store.tables() as tx:
                tx.insert('ticket_settings', {'work_id': work.id, 'board': 'delivery'})
                tx.insert('after', {'work_id': work.id, 'works': depends})
            expected.append({'id': work.id, 'title': title, 'depends_on': depends, 'expected_outcome': task})
        store.add_work(Node('element', 'code.delivery'), None, task='Unrelated work.', title='Another board')
        store.edit_work(expected[0]['id'], {'held': True, 'hold_reason': 'Wait for review.'})
        store.finish_work(expected[1]['id'], 'Fixture completed.', 'Exercise completed board entries.')
    plan = folder / 'docs' / 'plan.md'
    plan.parent.mkdir()
    plan.write_text('# Reviewed plan\n', encoding='utf-8')
    ctx = Context('roundtables', folder, project='outline', store=store)
    return ctx, expected, plan


def test_decomposed_board_outline_preserves_every_ticket_and_dependency(decomposed):
    ctx, expected, plan = decomposed
    result = execution_outline.write(ctx, board='delivery', plan='docs/plan.md')
    assert result['board'] == 'delivery'
    assert result['plan'] == 'docs/plan.md'
    assert {one['id']: one for one in result['tickets']} == {one['id']: one for one in expected}
    saved = plan.with_name('execution-outline.md')
    assert ctx.folder / result['file'] == saved
    body = saved.read_text(encoding='utf-8')
    assert json.loads(body.split('```json\n', 1)[1].split('\n```', 1)[0]) == {
        'project': 'outline', 'board': 'delivery', 'plan': 'docs/plan.md', 'tickets': result['tickets']}
    assert execution_outline.write(ctx, board='delivery', plan='docs/plan.md') == result
    assert saved.read_text(encoding='utf-8') == body
    assert plan.read_text(encoding='utf-8') == '# Reviewed plan\n'


def test_outline_uses_canonical_plan_from_isolated_assignment(decomposed, tmp_path):
    ctx, _, plan = decomposed
    isolated = tmp_path / 'worker'
    isolated.mkdir()
    execution_outline.write(replace(ctx, folder=isolated), board='delivery', plan='docs/plan.md')
    assert plan.with_name('execution-outline.md').is_file()
    assert not (isolated / 'docs').exists()


@pytest.mark.parametrize('plan', ['../outside.md', 'missing.md'])
def test_outline_rejects_missing_or_external_plan(decomposed, plan):
    ctx, _, _ = decomposed
    (ctx.folder.parent / 'outside.md').write_text('Outside project.', encoding='utf-8')
    with pytest.raises(Stop, match='saved plan is missing'):
        execution_outline.write(ctx, board='delivery', plan=plan)


def test_outline_rejects_unknown_board_without_writing(decomposed):
    ctx, _, plan = decomposed
    with pytest.raises(Stop, match='named board'):
        execution_outline.write(ctx, board='absent', plan='docs/plan.md')
    assert not plan.with_name('execution-outline.md').exists()


def test_outline_never_overwrites_plan_named_like_output(decomposed):
    ctx, _, plan = decomposed
    collision = plan.with_name('execution-outline.md')
    collision.write_text('Reviewed plan must survive.', encoding='utf-8')
    with pytest.raises(Stop, match='separate files'):
        execution_outline.write(ctx, board='delivery', plan='docs/execution-outline.md')
    assert collision.read_text(encoding='utf-8') == 'Reviewed plan must survive.'


def test_target_project_board_keeps_outline_beside_source_plan(decomposed, run, tmp_path):
    ctx, _, plan = decomposed
    target = tmp_path / 'target'
    target.mkdir()
    run('add', 'project', 'target', str(target))
    store = Store('target', module='map')
    with store.atomic():
        store.layer('base', 'intake', 'New project map.', kind='intake', mutable=False, hideable=False,
                    provenance={'module': 'intake'}, ready=True)
        store.add_element('base', 'code.new', name_length=1, role='DE')
        work = store.add_work(Node('element', 'code.new'), None, title='Build target', task='Target result.')
        with store.tables() as tx:
            tx.insert('boards', {'name': 'delivery', 'created': '2026-10-22T00:00:00Z'})
            tx.insert('ticket_settings', {'work_id': work.id, 'board': 'delivery'})
    result = execution_outline.write(ctx, board='delivery', plan='docs/plan.md', project='target')
    assert result['project'] == 'target'
    assert result['tickets'] == [{'id': work.id, 'title': 'Build target', 'depends_on': [],
                                  'expected_outcome': 'Target result.'}]
    assert plan.with_name('execution-outline.md').is_file()
    assert not (target / 'docs').exists()
