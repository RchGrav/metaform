"""Each table keeps one reply limit for its prompts and discussion enforcement."""
import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from metaform.modules.roundtables.roundtable import render, runner, store
from metaform.modules.roundtables.tests.test_roundtables import Heard, opened, serve, stubbed, table  # noqa: F401

pytestmark = pytest.mark.kind('simulation')


@pytest.mark.parametrize('limit', [80, 900])
def test_saved_limit_controls_opening_turns_and_truncation(tmp_path, monkeypatch, limit):
    monkeypatch.setenv('ROUNDTABLE_HOME', str(tmp_path / 'engine'))
    number = store.opened({'subject': 'Reply limits', 'opening': 'Explore the project.', 'folder': str(tmp_path),
                           'chair_key': None, 'chair_token': 'test', 'reporter': 'agent:tester', 'rounds': 1, 'spend': 0},
                          [{'kind': 'agent', 'id': 'agent:tester', 'agent': 'tester', 'model': None}],
                          [{'name': 'topic', 'title': 'Topic', 'text': 'Discuss the project.'}], reply_limit=limit)
    found = store.discussion(number)
    assert render.reply_limit(found) == limit
    opening = render.system(found, ['Tester'], 'Tester')
    assert opening.endswith(f'Each discussion reply has a maximum of {limit} characters. '
                            'Any excess text is truncated.')
    assert '512-character limit' not in opening
    for first, spoken in [(True, False), (False, False), (False, True)]:
        prompt = render.topic_view('Topic', None, [], first, spoken, limit=limit)
        assert prompt.endswith(f'Maximum {limit} characters. Any excess text is truncated.')
    found['unjudged'] = {'position': 0, 'text': 'x' * 1100, 'original': 'x' * 1100}
    held = runner.Table(number)
    held.verdict = AsyncMock(return_value=True)
    asyncio.run(held.turn(found, store.seats(number)[0]))
    entry = held.verdict.call_args.args[2]
    assert entry['text'] == 'x' * limit
    assert entry['truncated'] is True
    assert render.reply_limit(store.discussion(number)) == limit


def test_historical_table_keeps_default_reply_length():
    assert render.reply_limit({'snapshot': None}) == 512


@pytest.mark.timeout(60)
def test_reply_limit_reaches_engine_from_module(run, table, monkeypatch):  # noqa: F811
    folder, _ = table
    stub = stubbed()
    service = serve(monkeypatch, stub)
    heard = Heard()
    answer = None
    try:
        answer = opened(run, folder, 'seats=' + json.dumps(['stub/long']), 'host=stub/long',
                        'reply_limit=700')
        assert answer['reply_limit'] == 700
        assert heard.ended.wait(35), heard.kinds()
        turns = [one['payload']['text'] for one in heard.events if one['kind'] in ('turn', 'veto')]
        assert any(512 < len(text) <= 700 for text in turns)
        system = stub.chats[0]['messages'][0]['content']
        if isinstance(system, list):
            system = system[0]['text']
        assert system.endswith('Each discussion reply has a maximum of 700 characters. Any excess text is truncated.')
    finally:
        if answer and not heard.ended.is_set():
            run('roundtables', 'end', answer['table'], cwd=folder, ok=False)
        heard.close()
        service.shutdown()
