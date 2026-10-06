"""VIEW-043 voting remains intact, while D120 keeps unanswered questions from blocking worker dispatch."""
import json

import pytest

from metaform.modules.dispatch import consensus
from metaform.modules.dispatch.consensus import BLOCKED, CLOSED, HALTED, OPEN, TIE_REVIEW
from metaform.modules.dispatch.tests.test_dispatch import dispatch as dispatch  # noqa: PLC0414 fixture re-export
from metaform.modules.dispatch.tests.test_dispatch import eventually

pytestmark = pytest.mark.req('VIEW-043')
A, B = 'a' * 32, 'b' * 32


@pytest.mark.kind('fixture')
@pytest.mark.parametrize(('given', 'expected'), [
    ({'blocked': True, 'comment': True, 'write_in': 'x'}, (BLOCKED, None)),
    ({'comment': True, 'write_in': 'x', 'counts': {'Keep': 3}}, (HALTED, None)),
    ({'write_in': 'Split it', 'counts': {'Keep': 3}}, (CLOSED, 'Split it')),
    ({'counts': {'Keep': 2}}, (OPEN, None)),
    ({'counts': {'Keep': 2, 'Drop': 1}}, (CLOSED, 'Keep')),
    ({'counts': {'Keep': 2, 'Drop': 2}}, (OPEN, None)),
    ({'counts': {'Keep': 3, 'Drop': 1}}, (CLOSED, 'Keep')),
    ({'counts': {'Keep': 3, 'Drop': 1, 'Move': 1}}, (CLOSED, 'Keep')),
    ({'counts': {'Keep': 2, 'Drop': 1, 'Move': 1, 'Wait': 1}}, (CLOSED, 'Keep')),
    ({'counts': {'Keep': 2, 'Drop': 2, 'Move': 1}}, (TIE_REVIEW, None)),
    ({'counts': {'Keep': 1, 'Drop': 1, 'Move': 1}, 'cap': 3}, (TIE_REVIEW, None)),
])
def test_the_ticket_rule_is_the_coordinators_condition_in_its_order(given, expected):
    state, winner, _ = consensus.decide(**{'blocked': False, 'comment': False, 'write_in': None, 'counts': {},
                                           'cap': 5, **given})
    assert (state, winner) == expected


@pytest.mark.kind('fixture')
def test_the_cap_is_the_voters_up_to_eight():
    assert (consensus.cap(5), consensus.cap(8), consensus.cap(12)) == (5, 8, 8)


@pytest.mark.kind('fixture')
def test_a_voters_words_count_as_choices_write_ins_and_comments_and_nothing_is_made_up():
    queue = [{'work_id': A, 'message_id': 'm1', 'choices': ['Keep it', 'Drop it']},
             {'work_id': B, 'message_id': 'm2', 'choices': ['Yes', 'No']}]
    said = consensus.parse(f'Hello there\n{A}, keep it\n{B[:8]}, 2\n{A}, Drop it\nI think {B} is risky\n', queue)
    assert said == [(A, 'choice', 'Keep it'), (B, 'choice', 'No'), (B, 'comment', f'I think {B} is risky')]
    assert consensus.parse(f'- `{A}`: "Split it in two"', queue) == [(A, 'write-in', 'Split it in two')]
    assert consensus.parse('No ticket named here.', queue) == []


def frozen_ticket(dispatch, choices=('Keep it', 'Drop it')):
    asked = dispatch.store.ask(dispatch.node, 'Keep the store?', suggestions=list(choices), by='fake agent',
                               work=dispatch.work_id)
    return asked.message_id


def live():
    """The consensus module dispatch runs now: enabling a module loads it again, so a patch on an earlier copy would
    miss and start real agents."""
    import importlib
    return importlib.import_module('metaform.modules.dispatch.consensus')


def starter(dispatch, monkeypatch, run):
    from metaform.module import context
    from metaform.modules import dispatch as module
    run('set', '--dispatch-autostart', '--dispatch-agent', 'claude', cwd=dispatch.folder)  # the fake agent, never a real one
    started, voters = [], []
    monkeypatch.setattr(module, 'start', lambda ctx: started.append(ctx.nouns['id']) or {'work_id': ctx.nouns['id']})
    monkeypatch.setattr(live(), 'launch', lambda ctx, store, own, round_id, queue: voters.append(queue) and None)
    return (lambda: module.autostart(context('dispatch', dispatch.folder, project='proj'))), started, voters


def coordinate(dispatch, workers=0):
    """Exercise preserved voting directly, independently of the removed question-only Autostart trigger."""
    from metaform.module import context
    from metaform.modules import dispatch as module
    waiting, _ = module.unanswered(dispatch.store)
    tickets = live().frozen(dispatch.store.work(open=True, limit=0).results, waiting)
    return live().coordinate(context('dispatch', dispatch.folder, project='proj'), dispatch.store,
                             tickets, waiting, workers)


@pytest.mark.kind('simulation')
def test_a_ticket_without_a_question_gets_an_agent_and_no_voter(dispatch, monkeypatch, run):
    autostart, started, voters = starter(dispatch, monkeypatch, run)
    autostart()
    assert started == [dispatch.work_id] and voters == []


@pytest.mark.kind('simulation')
def test_unanswered_questions_get_workers_without_starting_voters(dispatch, monkeypatch, run):
    from metaform.data import Node
    frozen_ticket(dispatch)
    later = dispatch.store.add_work(Node('element', 'code.engine.linked'), 'broken', task='Fix it').work_id
    dispatch.store.ask(Node('element', 'code.engine.linked'), 'How?', suggestions=['This', 'That'], work=later)
    autostart, started, voters = starter(dispatch, monkeypatch, run)
    autostart()
    assert started == [dispatch.work_id, later] and voters == []


@pytest.mark.kind('simulation')
def test_the_coordinator_fills_five_slots_with_voters_given_the_oldest_question_first(dispatch, monkeypatch, run):
    from metaform.data import Node
    first = frozen_ticket(dispatch)
    later = dispatch.store.add_work(Node('element', 'code.engine.linked'), 'broken', task='Fix it').work_id
    dispatch.store.ask(Node('element', 'code.engine.linked'), 'How?', suggestions=['This', 'That'], work=later)
    _, started, voters = starter(dispatch, monkeypatch, run)
    coordinate(dispatch)
    assert started == [] and len(voters) == live().MAX_OPEN
    assert [item['work_id'] for item in voters[0]] == [dispatch.work_id, later]
    assert voters[0][0]['message_id'] == first and voters[0][0]['choices'] == ['Keep it', 'Drop it']


@pytest.mark.kind('simulation')
def test_a_winning_choice_answers_the_question_and_the_ticket_goes_back_to_work(dispatch, monkeypatch, run):
    from metaform.data import Store
    message_id = frozen_ticket(dispatch)
    autostart, started, _ = starter(dispatch, monkeypatch, run)
    coordinate(dispatch)
    own = Store('proj', module='dispatch')
    queue = [{'work_id': dispatch.work_id, 'message_id': message_id}]
    for voter, choice in (('v1', 'Keep it'), ('v2', 'Drop it'), ('v3', 'Keep it')):
        assert live().record(own, voter, queue, [(dispatch.work_id, 'choice', choice)]) == 1
    result = coordinate(dispatch)
    assert result['settled'][0]['state'] == CLOSED and result['settled'][0]['answer'] == 'Keep it'
    assert dispatch.questions(False)[0].answer == 'Keep it'
    told = dispatch.store.messages(dispatch.node, 'message', None, limit=0).results
    assert any('Consensus answered' in (message.text or '') for message in told)
    assert live().record(own, 'v4', queue, [(dispatch.work_id, 'choice', 'Drop it')]) == 0, 'late votes discarded'
    autostart()
    assert started == [dispatch.work_id], 'the answered ticket remains available for a worker'


@pytest.mark.kind('simulation')
def test_a_write_in_ends_voting_for_the_person_to_read_and_the_coordinator_leaves_it(dispatch, monkeypatch, run):
    from metaform.data import Store
    message_id = frozen_ticket(dispatch)
    autostart, started, voters = starter(dispatch, monkeypatch, run)
    coordinate(dispatch)
    own = Store('proj', module='dispatch')
    queue = [{'work_id': dispatch.work_id, 'message_id': message_id}]
    live().record(own, 'v1', queue, [(dispatch.work_id, 'choice', 'Keep it')])
    assert live().record(own, 'v1', queue, [(dispatch.work_id, 'choice', 'Drop it')]) == 0, 'one vote per voter'
    live().record(own, 'v2', queue, [(dispatch.work_id, 'write-in', 'Split the store in two')])
    voters.clear()
    result = coordinate(dispatch)
    assert result['settled'][0]['state'] == CLOSED and result['settled'][0]['rule'] == 'write-in'
    assert dispatch.questions(True), 'a write-in is not applied; the person reads it'
    told = dispatch.store.messages(dispatch.node, 'message', None, limit=0).results
    assert any('Split the store in two' in (message.text or '') for message in told)
    assert coordinate(dispatch)['settled'] == [] and voters == [], 'settled questions are not voted on again'
    autostart()
    assert started == [dispatch.work_id], 'a question sent for human review still permits worker dispatch'


@pytest.mark.kind('simulation')
def test_a_voter_votes_through_acp_with_the_voter_prompt_and_its_vote_is_counted(dispatch, monkeypatch, run):
    from metaform.data import Store
    frozen_ticket(dispatch)
    run('set', '--dispatch-autostart', '--dispatch-agent', 'claude', cwd=dispatch.folder)
    for key, value in dispatch.env('vote', FAKE_ACP_VOTE='Keep it').items():
        monkeypatch.setenv(key, value)
    real, launched = live().launch, []
    monkeypatch.setattr(live(), 'launch', lambda *given: launched.append(real(*given)) if not launched else None)
    coordinate(dispatch)
    own = Store('proj', module='dispatch')

    def counted():
        with own.tables(write=False) as tx:
            voter = tx.get('voters', {'voter': launched[0]})
            votes = [dict(row) for row in tx.rows('votes', limit=0).results]
        return votes if voter['state'] == 'ended' else None
    votes = eventually(counted)
    assert [(vote['voter'], vote['kind'], vote['choice']) for vote in votes] == [(launched[0], 'choice', 'Keep it')]
    [said] = [block['text'] for message in dispatch.received('session/prompt') for block in message['params']['prompt']]
    assert said.startswith('#! AXIOM/2.0 name=voter\n@STATE_INIT: {Queue} := <<DATA: ')
    assert f'id: {dispatch.work_id}' in said and '+> Output only: id, choice.' in said


@pytest.mark.kind('simulation')
def test_unanswered_questions_get_workers_while_other_tickets_are_being_worked(dispatch, monkeypatch, run):
    from metaform.data import Node
    frozen_ticket(dispatch)
    working = dispatch.store.add_work(Node('element', 'code.engine.linked'), 'broken', task='Being worked').work_id
    dispatch.store.take_work(working, by='claude some-session')
    autostart, started, voters = starter(dispatch, monkeypatch, run)
    autostart()
    assert started == [dispatch.work_id] and voters == []


@pytest.mark.kind('simulation')
def test_the_coordinator_reserves_slots_for_workers_and_does_not_vote_on_taken_tickets(dispatch, monkeypatch, run):
    from metaform.data import Node
    frozen_ticket(dispatch)
    working = dispatch.store.add_work(Node('element', 'code.engine.linked'), 'broken', task='Being worked').work_id
    dispatch.store.ask(Node('element', 'code.engine.linked'), 'How?', suggestions=['This', 'That'], work=working)
    dispatch.store.take_work(working, by='claude some-session')
    _, started, voters = starter(dispatch, monkeypatch, run)
    coordinate(dispatch, workers=1)
    assert started == [] and len(voters) == live().MAX_OPEN - 1
    assert [item['work_id'] for item in voters[0]] == [dispatch.work_id], 'the taken ticket is not voted on'


@pytest.mark.kind('simulation')
def test_autostart_ends_an_existing_consensus_round_and_starts_questioned_work(dispatch, monkeypatch, run):
    from metaform.data import Node, Store
    frozen_ticket(dispatch)
    workable = dispatch.store.add_work(Node('element', 'code.engine.linked'), 'broken', task='Can be worked').work_id
    autostart, started, voters = starter(dispatch, monkeypatch, run)
    coordinate(dispatch)
    assert voters, 'a prior round exists before worker dispatch resumes'
    voters.clear()
    autostart()
    assert started == [dispatch.work_id, workable] and voters == []
    with Store('proj', module='dispatch').tables(write=False) as tx:
        assert tx.get('mode', {'name': 'consensus'})['ended'] is not None


@pytest.mark.kind('simulation')
def test_the_results_show_each_question_its_votes_the_voters_words_and_what_came_of_it(dispatch, monkeypatch, run):
    from metaform.data import Store
    message_id = frozen_ticket(dispatch)
    starter(dispatch, monkeypatch, run)
    coordinate(dispatch)
    own = Store('proj', module='dispatch')
    queue = [{'work_id': dispatch.work_id, 'message_id': message_id}]
    for voter, choice in (('v1', 'Keep it'), ('v2', 'Keep it'), ('v3', 'Drop it')):
        live().record(own, voter, queue, [(dispatch.work_id, 'choice', choice)])
    coordinate(dispatch)
    [shown] = json.loads(run('dispatch', 'results', '--json', cwd=dispatch.folder).stdout)['results']
    assert (shown['outcome'], shown['answer'], shown['votes']) == ('answered', 'Keep it', 3)
    assert shown['choices'] == [{'choice': 'Keep it', 'votes': 2}, {'choice': 'Drop it', 'votes': 1}]
    assert shown['question'] == 'Keep the store?' and shown['still_applied'] is True


@pytest.mark.kind('simulation')
def test_help_me_answer_starts_three_helpers_for_one_question_and_applies_nothing(dispatch, monkeypatch, run):
    """Help me answer is the person's: it refuses until its prompt is written, then three helpers each say what the
    question means and what they would answer; the count and the recommendation are shown and the question stays
    open for the person to answer."""
    from pathlib import Path

    from metaform.data import Node
    asked = dispatch.store.ask(Node('element', 'code.engine'), 'Keep the cache or drop it?',
                               suggestions=['Keep it', 'Drop it'], work=dispatch.work_id)
    run('set', '--dispatch-agent', 'claude', cwd=dispatch.folder)
    for key, value in dispatch.env('vote', FAKE_ACP_VOTE='2').items():
        monkeypatch.setenv(key, value)
    unwritten = run('dispatch', 'recommend', asked.message_id, cwd=dispatch.folder, ok=False)
    assert 'This needs its prompt written:' in unwritten.stderr and 'prompts.xml recommend' in unwritten.stderr
    monkeypatch.setenv('METAFORM_PROMPTS', str(Path(__file__).with_name('trial_prompts.xml')))
    started = json.loads(run('dispatch', 'recommend', asked.message_id, '--json', cwd=dispatch.folder).stdout)
    assert len(started['helpers']) == 3

    def said():
        found = json.loads(run('dispatch', 'advice', asked.message_id, '--json', cwd=dispatch.folder).stdout)
        return found if len(found['advice']) == 3 and not found['reading'] else None
    found = eventually(said)
    assert found['counts'] == {'Drop it': 3} and found['recommendation'] == 'Drop it'
    assert {one['meaning'] for one in found['advice']} == {'The fake meaning.'}, found
    assert {one['reason'] for one in found['advice']} == {'The fake reason.'}
    assert dispatch.store.messages(None, 'question', None, limit=0).results[0].closed is None, 'nothing is applied'
    prompts = [block['text'] for message in dispatch.received('session/prompt') for block in message['params']['prompt']]
    assert all('Test recommend prompt. Question: Keep the cache or drop it?' in text and '2. Drop it' in text
               for text in prompts)


@pytest.mark.kind('fixture')
def test_a_helpers_reply_is_read_as_meaning_answer_and_reason():
    reply = 'Meaning: It asks whether to keep the cache.\n**Answer:** Keep it\nReason: It is faster.\nMore reason.'
    assert consensus.advise(reply, ['Keep it', 'Drop it']) == {
        'kind': 'choice', 'choice': 'Keep it', 'meaning': 'It asks whether to keep the cache.',
        'reason': 'It is faster.\nMore reason.'}
    assert consensus.advise('answer: 2. Drop it', ['Keep it', 'Drop it'])['choice'] == 'Drop it'
    assert consensus.advise('answer: Split it in two', ['Keep it'])['kind'] == 'write-in'
    assert consensus.advise('I think it is fine.', ['Keep it']) is None
