"""The collector's committed event is wired to the existing, separately owned repair policy."""
import importlib
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.kind('simulation')


def test_capture_event_invokes_existing_policy_once(monkeypatch):
    autoticket = importlib.import_module('metaform.modules.autoticket')
    called = []
    store = SimpleNamespace(project_id='project')
    ctx = SimpleNamespace(store=store)
    monkeypatch.setattr(autoticket.faults, 'tell', lambda *args: called.append(args))
    handlers = [subscription.handler for subscription in autoticket.MODULE.subscriptions
                if subscription.topic == 'autoticket.captured']
    assert handlers == [autoticket.captured]
    for handler in handlers:
        handler({'project': 'project', 'groups': [3, 7]}, ctx)
    assert called == [(ctx, store, [3, 7], {})]


def test_capture_event_does_not_cross_projects(monkeypatch):
    autoticket = importlib.import_module('metaform.modules.autoticket')
    def unexpected(*args):
        raise AssertionError('capture policy was invoked for another project')
    monkeypatch.setattr(autoticket.faults, 'tell', unexpected)
    autoticket.captured({'project': 'other', 'groups': [3]}, SimpleNamespace(store=SimpleNamespace(project_id='project')))
    autoticket.captured({'project': 'project', 'groups': [3]}, SimpleNamespace(store=None))
