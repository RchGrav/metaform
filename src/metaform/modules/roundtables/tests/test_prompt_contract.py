"""The actual participant wire prompt follows the owner's privacy and correction rules."""
import asyncio
import re
from unittest.mock import Mock
from xml.etree.ElementTree import fromstring

import pytest

from metaform.modules.roundtables.roundtable import budget, judge, render, runner, store
from metaform.modules.roundtables.roundtable.seat import Reply, Seat

pytestmark = pytest.mark.kind('simulation')


def test_native_turn_has_private_reason_first_one_limit_and_no_judge_identity(
        home, project_folder, run, tmp_path, monkeypatch):
    monkeypatch.setenv('ROUNDTABLE_HOME', str(tmp_path / 'engine'))
    run('enable', 'dispatch', cwd=project_folder)
    chosen = [{'kind': 'acp', 'id': 'acp:claude/opus', 'agent': 'claude', 'model': 'opus'},
              {'kind': 'acp', 'id': 'acp:codex/sol', 'agent': 'codex', 'model': 'sol'}]
    number = store.opened({'subject': 'Choose a useful next step', 'opening': 'Discuss the next useful step.',
                           'folder': str(project_folder), 'chair_key': None, 'chair_token': 'fixture',
                           'reporter': chosen[0]['id'], 'rounds': 0, 'spend': 0}, chosen,
                          [{'name': 'one', 'title': 'Next step', 'text': 'What should we do next?'}], judging=True)
    calls = []
    replies = {0: ['PRIVATE_BLOCKED_TEXT', 'PASS'], 1: ['A useful published proposal.']}

    class Native(Seat):
        kind = 'acp'

        async def exchange(self, text, seconds):
            calls.append((self.position, text))
            return Reply(replies[self.position].pop(0))

    def decide(state, criteria, **options):
        candidate = fromstring(state['xml']).find('candidate').text
        values = {'new_context': .2, 'valuable': .99, 'on_topic': .3} if candidate == 'PRIVATE_BLOCKED_TEXT' else \
            dict.fromkeys(store.CHECKS, .99)
        assert tuple(criteria) == ('new_context', 'valuable', 'on_topic')
        assert criteria['new_context']['instructions'] == (
            'Does this add anything to the discussion which has not been already stated, '
            'or does it express a position on a matter which was recently mentioned?')
        return judge.Asked(request={'state': state}, criteria=criteria, nouls=values)

    monkeypatch.setitem(runner.KINDS, 'acp', Native)
    monkeypatch.setattr(judge, 'ask', decide)
    monkeypatch.setattr(budget, 'prompt', Mock(return_value=budget.Prompt('The round is halfway through its budget.')))
    table = runner.Table(number)
    asyncio.run(table.turn(table.row(), store.seats(number)[0]))
    asyncio.run(table.turn(table.row(), store.seats(number)[1]))
    asyncio.run(table.turn(table.row(), store.seats(number)[0]))
    first, peer, correction = [text for position, text in calls]
    reason = ('Your message did not add anything new to the discussion.\n'
              'Your message was not relevant to the topic.')
    assert correction.startswith(reason + '\n\nYour limit for this turn is 512 characters.')
    assert correction.count(reason) == 1 and correction.count('Your limit for this turn is') == 1
    assert 'A useful published proposal.' in correction and 'R1-1' in correction
    assert all(text not in peer for text in ('PRIVATE_BLOCKED_TEXT', 'Your message did not', 'veto', 'T01'))
    assert all(text not in correction for text in ('PRIVATE_BLOCKED_TEXT', '0.20', '0.30', '70%'))
    assert not re.search(r'\b(?:jev|claude|codex|opus|sol)\b', first, re.IGNORECASE)
    accepted = next(row for row in store.submissions(number) if row['accepted'])
    assert render.status(accepted) == ''
    assert accepted['message_id'] == 'R1-1'
    roster = next(project_folder.rglob('participants.md')).read_text()
    assert all(seat['name'] in roster for seat in store.seats(number))
    assert not re.search(r'\b(?:claude|codex|opus|sol)\b', roster, re.IGNORECASE)
