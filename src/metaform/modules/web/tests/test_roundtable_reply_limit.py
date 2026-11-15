"""Roundtable creation forwards the person's character limit before opening any agents."""
import pytest

from metaform.modules.web import server
from metaform.modules.web.tests.test_web import _Handler

pytestmark = pytest.mark.kind('simulation')


@pytest.mark.parametrize('compression', [None, False, True])
def test_roundtable_forwards_reply_limit(monkeypatch, compression):
    calls = []
    monkeypatch.setattr(server, 'module_verb', lambda given, owner, verb, arguments:
                        calls.append(arguments) or {'table': 'created'})
    handler = _Handler()
    server.Handler.roundtable_open(handler, {'topic': 'Discuss the project', 'reply_limit': 1200, 'judging': False,
                                          **({'compress_between_topics': compression}
                                             if compression is not None else {})})
    assert handler.answers == [(200, {'table': 'created'})]
    assert calls[0]['reply_limit'] == 1200
    assert calls[0]['judging'] is False
    assert calls[0]['compress_between_topics'] is (compression is True)


@pytest.mark.parametrize('invalid', ['false', 0, 1, None])
def test_roundtable_rejects_invalid_compression_before_launch(monkeypatch, invalid):
    monkeypatch.setattr(server, 'module_verb', lambda *args: pytest.fail('Invalid compression must not start a table.'))
    handler = _Handler()
    server.Handler.roundtable_open(handler, {'topic': 'Discuss', 'compress_between_topics': invalid})
    assert handler.answers[0][0] == 400


@pytest.mark.parametrize('invalid', ['false', 0, 1])
def test_roundtable_rejects_invalid_judging(monkeypatch, invalid):
    monkeypatch.setattr(server, 'module_verb', lambda *args: pytest.fail('Invalid judging must not start a table.'))
    handler = _Handler()
    server.Handler.roundtable_open(handler, {'topic': 'Discuss', 'judging': invalid})
    assert handler.answers[0][0] == 400


@pytest.mark.parametrize('invalid', [0, -1, 1.5, True, '100', None])
def test_roundtable_rejects_invalid_reply_limit(monkeypatch, invalid):
    monkeypatch.setattr(server, 'module_verb', lambda *args: pytest.fail('Invalid input must not start a table.'))
    handler = _Handler()
    server.Handler.roundtable_open(handler, {'topic': 'Discuss the project', 'reply_limit': invalid})
    assert handler.answers[0][0] == 400
