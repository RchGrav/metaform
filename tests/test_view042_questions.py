"""VIEW-042 keeps a question and its answer with the ticket through later sessions."""

import json

import pytest

from metaform.data import Node


@pytest.mark.req('VIEW-042')
@pytest.mark.kind('fixture')
def test_question_ticket_link_survives_answer_move_and_reopen(store, run, project_folder):
    layer = store.layer('intake', 'intake', 'Fixture map.', kind='intake', ready=True,
                        mutable=False, hideable=False)
    first = store.add_element(layer.name, 'code.first', name_length=1, role='DE')
    second = store.add_element(layer.name, 'code.second', name_length=1, role='SE')
    ticket = store.add_work(Node('element', first.id), 'unbuilt', task='Build it.')
    asked = json.loads(run('map', 'ask', 'code.first', 'Which approach?',
                           f'work={ticket.id}', 'suggestions=["Use the existing approach", "Replace it"]', 'by=builder',
                           '--json', cwd=project_folder).stdout)
    assert asked['work_id'] == ticket.id
    store.reply(asked['id'], 'Use the existing approach')
    store.move_message(asked['id'], Node('element', second.id))
    [answered] = store.messages(None, 'question', False, limit=0).results
    assert answered.work_id == ticket.id and answered.answer == 'Use the existing approach'
    reopened = store.reopen(asked['id'])
    assert reopened.work_id == ticket.id and reopened.closed is None
    assert store.ticket(ticket.id).work.steps_done == 0
