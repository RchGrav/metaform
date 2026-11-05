"""Public accepted-message references survive the engine, follower and saved owner record."""
import importlib
import json
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.kind('simulation')


@pytest.fixture
def discussion(run, tmp_path, monkeypatch, request):
    folder = tmp_path / 'project'
    folder.mkdir()
    run('add', 'project', 'message-projections', str(folder))
    run('enable', 'dispatch', cwd=folder)
    from metaform.module import context

    follow = importlib.import_module('metaform.modules.roundtables.follow')
    store = importlib.import_module('metaform.modules.roundtables.roundtable.store')
    monkeypatch.setenv('ROUNDTABLE_HOME', str(tmp_path / 'engine'))
    seats = [{'kind': 'acp', 'id': 'acp:claude/opus', 'agent': 'claude', 'model': 'opus'}]
    role = {**seats[0], 'name': 'Alpha'}
    number = store.opened({'subject': 'Public message references', 'opening': 'Keep the original question.',
                           'folder': str(folder), 'chair_key': None, 'chair_token': 'fixture',
                           'reporter': seats[0]['id'], 'host': role, 'synthesizer': role, 'rounds': 1, 'spend': 0},
                          seats, [{'title': 'First panel', 'text': 'Consider the first question.', 'name': 'first'},
                                  {'title': 'Second panel', 'text': 'Consider the second question.', 'name': 'second'}],
                          judging=getattr(request, 'param', True))

    def record(text, **changes):
        return store.record(number, {'round': 1, 'position': 0, 'seat': seats[0]['id'], 'name': 'Alpha',
                                     'kind': 'seat', 'topic': 0, 'text': text, 'accepted': True,
                                     'new_context': .99, 'valuable': .99, 'on_topic': .99, **changes})

    rejected = record('A rejected submission stays in the owner audit.', accepted=False, on_topic=.1)
    passed = record('PASS', kind='pass')
    accepted = record('Keep the first accepted proposal.')
    second = record('Keep the second accepted proposal.')
    store.change(number, topic=1)
    next_panel = record('Keep the next panel proposal.', topic=1)
    store.seat_change(number, 0, messages=[{'role': 'user', 'content': 'First request.'},
        {'role': 'assistant', 'content': accepted['text']}, {'role': 'user', 'content': 'Second request.'},
        {'role': 'assistant', 'content': second['text']}])
    ctx = context('roundtables', folder)
    with ctx.require_store().tables() as tx:
        tx.insert('tables', {'table_id': 'projection', 'topic': 'Public message references', 'opening': '.',
                             'seats': [seats[0]['id']], 'spend': 0, 'state': 'running', 'discussion': number,
                             'created': follow.now()})
    return SimpleNamespace(number=number, store=store, ctx=ctx, follow=follow,
                           rejected=rejected, passed=passed, accepted=accepted, second=second, next_panel=next_panel)


def test_real_record_ids_reach_owner_exports_and_follower_while_audit_cursors_remain_private(discussion):
    export = importlib.import_module('metaform.modules.roundtables.roundtable.export')
    server = importlib.import_module('metaform.modules.roundtables.roundtable.server')
    web = importlib.import_module('metaform.modules.roundtables.roundtable.web')
    given = discussion
    assert given.accepted['message_id'] == 'R1-1' and given.second['message_id'] == 'R1-2'
    assert given.next_panel['message_id'] == 'R2-1'
    assert not given.rejected.get('message_id') and not given.passed.get('message_id')

    exported = export.build(given.number)
    rows = {row['number']: row for row in exported['submissions']}
    accepted = rows[given.accepted['number']]
    assert accepted['message_id'] == accepted['turn'] == 'R1-1'
    assert accepted['number'] > 1 and accepted['link'].endswith(f'/submission{accepted["number"]}')
    assert not rows[given.rejected['number']].get('message_id')
    assert rows[given.rejected['number']]['text'] == given.rejected['text']
    transcript = export.discussion_file(given.number)['transcript']
    assert [(row['n'], row['message_id']) for row in transcript if row.get('message_id')] == [
        (given.accepted['number'], 'R1-1'), (given.second['number'], 'R1-2'), (given.next_panel['number'], 'R2-1')]
    assert [row['message_id'] for row in export.context(given.number, 0) if row.get('message_id')] == ['R1-1', 'R1-2']
    assert any(row.get('message_id') == 'R2-1' for row in export.stats(given.number)['per_turn'])
    read = server.read(given.number, since=given.accepted['number'])
    assert read['latest'] == given.next_panel['number']
    assert [row['turn'] for row in read['turns']] == ['R1-2', 'R2-1']
    assert server.submission(given.number, given.accepted['number']) == given.accepted['text']

    class Page:
        def get(self, path, **kwargs):
            assert path == f'/tables/{given.number}/turns'
            request = SimpleNamespace(path_params={'number': str(given.number)},
                                      query_params={'since': str(kwargs.get('since', 0))})
            return json.loads(web.turns(request).body)

    follower = given.follow.Follower(given.ctx, 'projection')
    follower.turns(Page(), given.number)
    with given.ctx.require_store().tables(write=False) as tx:
        events = [dict(one) for one in tx.rows('events', {'table_id': 'projection'}, limit=0).results]
    payloads = [row['payload'] for row in events if row['payload'].get('message_id')]
    assert [(row['n'], row['message_id'], row['turn']) for row in payloads] == [
        (given.accepted['number'], 'R1-1', 'R1-1'), (given.second['number'], 'R1-2', 'R1-2'),
        (given.next_panel['number'], 'R2-1', 'R2-1')]
    veto = next(row for row in events if row['kind'] == 'veto')
    assert veto['payload']['n'] == given.rejected['number']
    assert not veto['payload'].get('message_id')
    assert veto['payload']['text'] == given.rejected['text']
    assert follower.followed['turns'] == given.next_panel['number']
    follower.turns(Page(), given.number)
    with given.ctx.require_store().tables(write=False) as tx:
        assert len(tx.rows('events', {'table_id': 'projection'}, limit=0).results) == len(events)


@pytest.mark.parametrize('discussion', [False], indirect=True)
def test_unjudged_discussion_exports_public_ids_without_inventing_criterion_exclusions(discussion):
    export = importlib.import_module('metaform.modules.roundtables.roundtable.export')
    given = discussion
    assert given.store.discussion(given.number)['snapshot']['judging'] is False
    exported = export.discussion_file(given.number)
    assert [row['message_id'] for row in exported['transcript'] if row.get('message_id')] == ['R1-1', 'R1-2', 'R2-1']
    assert all(seat['excluded_by'] == {} for seat in exported['summary']['by_seat'].values())
    assert export.all_in_one(given.number)['transcript'] == exported['transcript']
