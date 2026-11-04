"""Dispatch settings writes retain registry choices across unrelated module changes."""
import pytest

from metaform import home as registry
from metaform import module as chassis
from metaform import settings
from metaform.modules.web import server

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('VIEW-042')]


def test_manual_default_agent_update_keeps_registry_choices_during_refresh(project_folder, monkeypatch):
    monkeypatch.chdir(project_folder)
    registry.set_module_state('dispatch', True)
    chassis.surface(project_folder)
    settings.put('dispatch_registry_agents', ['goose@1.54.0'], project_folder)
    value = settings.value
    refreshed = False

    def refreshing_value(key, folder):
        nonlocal refreshed
        if key == 'dispatch_registry_agents' and not refreshed:
            refreshed = True
            registry.set_module_state('hello', True)
            chassis.refresh_modules()
        return value(key, folder)

    monkeypatch.setattr(settings, 'value', refreshing_value)
    readbacks, failures = [], []
    request = object.__new__(server.Handler)
    request.dispatch_agents = lambda given: readbacks.append(given)
    request.send = lambda status, body: failures.append((status, body))
    request.set_dispatch_agent({'project': 'proj', 'default': 'goose'})
    assert failures == []
    assert refreshed
    assert value('dispatch_registry_agents', project_folder) == ['goose@1.54.0']
    assert value('dispatch_agent', project_folder) == 'goose'
    assert readbacks == [{'project': 'proj'}]
