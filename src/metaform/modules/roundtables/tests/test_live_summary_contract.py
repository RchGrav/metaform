"""The chair's synthesis stays separate from panel events and participant documents."""
from importlib import import_module

import pytest

from metaform.module import context

pytestmark = pytest.mark.kind('fixture')


@pytest.fixture
def observed_table(run, project_folder, monkeypatch):
    run('enable', 'dispatch', cwd=project_folder)
    module = import_module('metaform.modules.roundtables')
    monkeypatch.setattr(module, 'started', lambda *_: {'state': 'running'})
    monkeypatch.setattr(module, 'model_of', lambda _ctx, _agent, model: model)
    ctx = context('roundtables', project_folder, nouns={
        'topic': 'How should unresolved proposals carry forward?', 'seats': ['claude/opus'],
        'chain': 1, 'judging': False})
    ctx.nouns['table'] = module.open_table(ctx)['table']
    return module, ctx


def test_live_synthesis_is_available_independently_of_the_transcript_cursor(observed_table):
    module, ctx = observed_table
    table = ctx.nouns['table']
    materials = module.status(ctx)['materials']
    from pathlib import Path

    document = Path(materials) / 'decisions.md'
    document.write_text('The participants own this document.', encoding='utf-8')
    with ctx.require_store().tables() as tx:
        tx.insert('live_summaries', {'table_id': table, 'through_seq': 7, 'state': 'ready',
                  'text': 'The panel proposes carrying unresolved ideas into the next discussion.',
                  'updated': '2026-11-04T20:00:00Z'})
    ctx.nouns['after'] = 100
    answer = module.table_events(ctx)
    assert answer['events'] == [] and answer['latest'] == 100
    assert answer['live_summary']['through_seq'] == 7
    assert answer['live_summary']['state'] == 'ready'
    assert 'unresolved ideas' in answer['live_summary']['text']
    assert module.status(ctx)['live_summary'] == answer['live_summary']
    assert document.read_text(encoding='utf-8') == 'The participants own this document.'


def test_summary_permission_uses_the_existing_person_control_without_contacting_the_panel(
        observed_table, monkeypatch):
    module, ctx = observed_table
    ctx.nouns.update(request='summary-request', option='native-option')
    seen = []
    monkeypatch.setattr(module.live_summary, 'answer', lambda *args:
                        seen.append(args[1:]) or {'accepted': True})
    monkeypatch.setattr(module.engine, 'call', lambda *_, **__: pytest.fail('The summary owns this request.'))
    assert module.permit(ctx)['accepted'] is True
    assert seen == [(ctx.nouns['table'], 'summary-request', 'native-option')]
