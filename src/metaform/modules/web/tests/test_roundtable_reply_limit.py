"""Roundtable creation forwards the person's character limit before opening any agents."""
import pytest

from metaform.modules.web import server
from metaform.modules.web.tests.test_web import _Handler

pytestmark = pytest.mark.kind('simulation')


def test_roundtable_forwards_reply_limit(monkeypatch):
    calls = []
    monkeypatch.setattr(server, 'module_verb', lambda given, owner, verb, arguments:
                        calls.append(arguments) or {'table': 'created'})
    handler = _Handler()
    server.Handler.roundtable_open(handler, {'topic': 'Discuss the project', 'reply_limit': 1200})
    assert handler.answers == [(200, {'table': 'created'})]
    assert calls[0]['reply_limit'] == 1200


@pytest.mark.parametrize('invalid', [0, -1, 1.5, True, '100', None])
def test_roundtable_rejects_invalid_reply_limit(monkeypatch, invalid):
    monkeypatch.setattr(server, 'module_verb', lambda *args: pytest.fail('Invalid input must not start a table.'))
    handler = _Handler()
    server.Handler.roundtable_open(handler, {'topic': 'Discuss the project', 'reply_limit': invalid})
    assert handler.answers[0][0] == 400
