"""Browser writes cannot bypass shared hold reason checks."""
import json

import pytest

from metaform.data import Node, Store
from metaform.modules.web.tests.test_ticket_detail import mapped, post, threaded, web  # noqa: F401
from metaform.modules.web.tests.test_web import api

pytestmark = pytest.mark.kind('simulation')


def test_hold_writes_reject_blank_reasons_without_partial_changes(run, web, mapped):  # noqa: F811
    store = Store('proj')
    ticket = store.add_work(Node('element', 'code.timer.kitchen'), None, task='Preserve this task.', note='General note.')
    _, detail = api(web, f'/api/ticket-detail?project=proj&work_id={ticket.id}')
    for reason in (None, '', ' \n\t '):
        for flag in ('hold', 'held'):
            fields = {flag: True, 'hold_reason': reason}
            response = post(web, work_id=ticket.id, **fields)
            assert response[0] == 400, (fields, response)
            assert post(web, work_id=ticket.id, task='Must roll back.', revision=detail['revision'], **fields)[0] == 400
            assert store.ticket(ticket.id).work.task == 'Preserve this task.'
        status, failed = api(web, '/api/move', method='POST',
                            body=json.dumps({'project': 'proj', 'work_id': ticket.id, 'column': 'backlog',
                                             'hold_reason': reason}),
                            headers={'Origin': f'http://127.0.0.1:{web}', 'Content-Type': 'application/json'})
        assert status == 400 and 'hold_reason' in failed['error']
        for flag in ('hold', 'held'):
            before = len(store.work(limit=0).results)
            status, _ = api(web, '/api/task', method='POST',
                            body=json.dumps({'project': 'proj', 'nodes': ['element:code.timer.kitchen'],
                                             'task': 'Must not be created.', flag: True, 'hold_reason': reason}),
                            headers={'Origin': f'http://127.0.0.1:{web}', 'Content-Type': 'application/json'})
            assert status == 400
            assert len(store.work(limit=0).results) == before
    assert not store.ticket(ticket.id).work.held
    assert not store.work_hold_history(ticket.id)


def test_concurrent_reason_change_after_preview_check_is_not_released(run, web, mapped, monkeypatch):  # noqa: F811
    from metaform.modules.web import server

    store = Store('proj')
    ticket = store.add_work(Node('element', 'code.timer.kitchen'), None, task='Keep deliberate hold.')
    store.set_work_hold(ticket.id, hold=True, hold_reason='Review first.')
    _, preview = api(web, '/api/held-work?project=proj')
    original = server.module_verb

    def change_before_domain(given, module, verb, arguments, **kwargs):
        if module == 'map' and verb == 'work' and arguments.get('op') == 'unhold_all':
            store.set_work_hold(ticket.id, hold=True, hold_reason='New evidence: release is unsafe.')
        return original(given, module, verb, arguments, **kwargs)

    monkeypatch.setattr(server, 'module_verb', change_before_domain)
    status, result = api(web, '/api/unhold-all', method='POST',
                         body=json.dumps({'project': 'proj', 'revision': preview['revision'],
                                          'hold_preview': preview['results']}),
                         headers={'Origin': f'http://127.0.0.1:{web}', 'Content-Type': 'application/json'})
    assert status == 200, result
    assert result == {'changed': 0, 'review_changed': 1}
    with Store('proj', module='map').tables(write=False) as tx:
        settings = tx.get('ticket_settings', {'work_id': ticket.id})
        assert settings['hold'] == 1
        assert settings['hold_reason'] == 'New evidence: release is unsafe.'
