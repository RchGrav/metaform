"""New project artifacts expose accepted discussion and public results while owner audit records stay intact."""
from __future__ import annotations

import copy
import importlib
import json
from pathlib import Path

import pytest

from metaform.modules.roundtables.tests.test_public_message_projections import discussion  # noqa: F401

pytestmark = pytest.mark.kind('simulation')


@pytest.fixture
def record(discussion):  # noqa: F811 -- real engine/project fixture
    given = discussion
    store = given.store
    participant = store.seats(given.number)[0]
    given.public_name = participant['name']
    store.record(given.number, {'round': 1, 'position': None, 'seat': 'chair', 'kind': 'chair', 'topic': 1,
                                'text': 'Chair: retain both accepted alternatives.'})
    store.record(given.number, {'round': 1, 'position': 0, 'seat': participant['id'], 'name': given.public_name,
                                'kind': 'seat', 'topic': 1, 'text': 'REJECTED_RAW_SECRET', 'accepted': False,
                                'truncated': True, 'original': 'REJECTED_ORIGINAL_SECRET', 'on_topic': .1,
                                'model': 'PRIVATE_MODEL_SECRET'})
    for stage, position, text, extra in (
            ('synthesis', store.SYNTHESIZER, 'I1. Durable records: Keep accepted context.',
             {'ideas': [{'id': 'I1', 'name': 'Durable records', 'summary': 'Keep accepted context.'}]}),
            ('ranking', 0, 'I1', {'ranking': ['I1'], 'repair': 'PRIVATE_REPAIR_SECRET'}),
            ('top_three', 0, 'Accepted context supports future work.', {}),
            ('host_summary', store.HOST, 'Keep the accepted record available.', {})):
        store.stage_record(given.number, {'topic': 0, 'stage': stage, 'position': position,
                                          'seat': participant['id'], 'name': given.public_name, 'text': text,
                                          'model': 'PRIVATE_MODEL_SECRET', 'original': 'PRIVATE_STAGE_ORIGINAL',
                                          'truncated': True, **extra})
    store.stage_record(given.number, {'topic': 0, 'stage': 'bottom_three', 'position': 0,
                                      'seat': participant['id'], 'name': given.public_name,
                                      'text': 'PRIVATE_FAILED_STAGE_SECRET', 'error': 'PRIVATE_ERROR_SECRET'})
    store.decide(given.number, {'kind': 'veto', 'topic': 1, 'request': {'text': 'PRIVATE_JUDGMENT_REQUEST'},
                                'response': {'raw': 'PRIVATE_JUDGMENT_RESPONSE'}, 'model': 'PRIVATE_JUDGE_MODEL',
                                'decision': 'vetoed'}, {'state': 'ended', 'reason': 'All public topics were summarized.'})
    store.event(given.number, 'seat_lost', 'PRIVATE_OPERATIONAL_SECRET', participant['id'])
    export = importlib.import_module('metaform.modules.roundtables.roundtable.export')
    engine_home = Path(store.config.home())
    private_report = engine_home / 'owner-report.md'
    private_report.write_text(export.mechanical(given.number), encoding='utf-8')
    store.change(given.number, mechanical=str(private_report))
    given.native = export.build(given.number)
    given.private_export = engine_home / 'owner-export.json'
    given.private_export.write_text(json.dumps(given.native), encoding='utf-8')
    given.private_report = private_report
    return given


def test_shared_projection_whitelists_public_messages_and_results_without_mutating_owner_audit(record, monkeypatch):
    export = importlib.import_module('metaform.modules.roundtables.roundtable.export')
    given = record
    native = copy.deepcopy(given.native)

    def no_engine_read(*_args, **_kwargs):
        raise AssertionError('Shared formatting must use the supplied export, not an engine home.')

    monkeypatch.setattr(given.store, 'discussion', no_engine_read)
    shared = export.safe_shared(given.native)
    markdown = export.shared_mechanical(shared)
    assert given.native == native
    assert set(shared) == {'discussion', 'seats', 'submissions', 'topics', 'summary'}
    assert [row['message_id'] for row in shared['submissions']] == ['R1-1', 'R1-2', 'R2-1', 'R2-2']
    assert [row['text'] for row in shared['submissions']] == [given.accepted['text'], given.second['text'],
        given.next_panel['text'], 'Chair: retain both accepted alternatives.']
    assert {row['name'] for row in shared['submissions']} == {given.public_name, 'Chair'}
    assert all('number' not in row and 'round' not in row and 'outcome' not in row for row in shared['submissions'])
    assert shared['discussion']['reason'] == 'All public topics were summarized.'
    assert shared['topics'][0]['synthesis']['ideas'][0]['name'] == 'Durable records'
    assert shared['topics'][0]['borda']['order'] == ['I1']
    assert shared['topics'][0]['rankings'][0]['ranking'] == ['I1']
    assert shared['topics'][0]['bottom_three'] == []
    assert shared['topics'][0]['host_summary']['text'] == 'Keep the accepted record available.'
    public = json.dumps(shared) + markdown
    for secret in ('PRIVATE_', 'REJECTED_', given.rejected['text'], 'acp:claude/opus', 'claude', 'opus',
                   'profile_key', 'reported_model', 'nouls', 'judgments', 'snapshot', 'repair_asked_about'):
        assert secret not in public
    assert 'R1-1' in markdown and given.public_name in markdown and 'Durable records' in markdown
    audit = given.private_export.read_text(encoding='utf-8')
    assert 'REJECTED_RAW_SECRET' in audit and 'PRIVATE_JUDGMENT_REQUEST' in audit and 'acp:claude/opus' in audit
    assert 'PRIVATE_FAILED_STAGE_SECRET' in audit and 'PRIVATE_STAGE_ORIGINAL' in audit


def test_follower_saves_only_public_artifacts_and_reuses_identical_bytes_without_rewriting_history(record):
    export = importlib.import_module('metaform.modules.roundtables.roundtable.export')
    given = record
    private_bytes = given.private_export.read_bytes(), given.private_report.read_bytes()

    class Page:
        def __init__(self):
            self.reads = 0

        def get(self, path):
            assert path == f'/tables/{given.number}/download/export.json'
            self.reads += 1
            return given.native

    page = Page()
    follower = given.follow.Follower(given.ctx, 'projection')
    saved = follower.saved(page, given.number)
    root = Path(given.ctx.require_store().project().path)
    folder = root / saved
    record_file, report_file = folder / 'export.json', folder / 'mechanical-report.md'
    assert json.loads(record_file.read_text()) == export.safe_shared(given.native)
    assert report_file.read_text() == export.shared_mechanical(export.safe_shared(given.native))
    stamps = record_file.stat().st_mtime_ns, report_file.stat().st_mtime_ns
    assert follower.saved(page, given.number) == saved and page.reads == 1
    retry = given.follow.Follower(given.ctx, 'projection')
    assert retry.saved(page, given.number) == saved
    assert (record_file.stat().st_mtime_ns, report_file.stat().st_mtime_ns) == stamps
    record_file.write_text('Existing user record stays exactly as written.\n', encoding='utf-8')
    again = given.follow.Follower(given.ctx, 'projection')
    new_saved = again.saved(page, given.number)
    assert new_saved != saved
    assert record_file.read_text() == 'Existing user record stays exactly as written.\n'
    assert json.loads((root / new_saved / 'export.json').read_text()) == export.safe_shared(given.native)
    assert (given.private_export.read_bytes(), given.private_report.read_bytes()) == private_bytes
    assert any(row['text'] == 'REJECTED_RAW_SECRET' for row in given.store.submissions(given.number))


def test_historical_public_labels_are_preserved_while_private_names_are_replaced():
    export = importlib.import_module('metaform.modules.roundtables.roundtable.export')
    native = {'discussion': {'subject': 'Historical discussion', 'reason': 'claude/opus finished.'},
              'seats': [{'seat': 'claude/opus', 'name': 'Opus', 'model': 'opus', 'agent': 'claude'}],
              'submissions': [{'turn': 'T11', 'number': 11, 'seat': 'claude/opus', 'name': 'Opus',
                               'outcome': 'kept', 'text': 'Retain the historical citation.'},
                              {'turn': 'T12', 'number': 12, 'outcome': 'vetoed', 'text': 'PRIVATE_REJECTION'},
                              {'turn': 'T15', 'number': 15, 'seat': 'claude/opus', 'outcome': 'kept',
                               'text': 'Retain another citation.'}]}
    shared = export.safe_shared(native)
    assert [row['message_id'] for row in shared['submissions']] == ['T11', 'T15']
    assert shared['seats'] == [{'name': 'Participant 1'}]
    assert shared['discussion']['reason'] == 'Participant 1 finished.'
    assert 'opus' not in json.dumps(shared).lower() and 'claude' not in json.dumps(shared).lower()


def test_new_records_never_turn_unlabeled_phase_directives_into_private_attempt_references(record):
    export = importlib.import_module('metaform.modules.roundtables.roundtable.export')
    native = copy.deepcopy(record.native)
    assert native['discussion']['snapshot']['message_ids'] is True
    native['submissions'].extend([
        {'number': 911, 'turn': 'T911', 'kind': 'chair', 'outcome': 'comment',
         'text': 'UNLABELED_PHASE_DIRECTIVE'},
        {'number': 912, 'turn': 'T912', 'kind': 'handoff', 'outcome': 'handoff',
         'text': 'PRIVATE_HANDOFF_CONTEXT'},
        {'number': 913, 'turn': 'T913', 'kind': 'seat', 'outcome': 'vetoed', 'text': 'PRIVATE_VETO_ATTEMPT'},
    ])
    shared = export.safe_shared(native)
    assert [row['message_id'] for row in shared['submissions']] == ['R1-1', 'R1-2', 'R2-1', 'R2-2']
    public = json.dumps(shared) + export.shared_mechanical(shared)
    assert not any(secret in public for secret in ('T911', 'T912', 'T913', 'UNLABELED_PHASE_DIRECTIVE',
                                                    'PRIVATE_HANDOFF_CONTEXT', 'PRIVATE_VETO_ATTEMPT'))
