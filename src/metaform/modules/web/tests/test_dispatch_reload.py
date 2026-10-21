"""Unrelated module changes preserve dispatch requests already using their declarations."""
import http.client
import json
import threading
from types import SimpleNamespace

import pytest

from metaform import home as registry
from metaform import module as chassis
from metaform import settings
from metaform.modules.web import server

pytestmark = pytest.mark.kind('fixture')


@pytest.mark.parametrize('surface', ['module', 'http'])
def test_dispatch_settings_survive_unrelated_module_refresh(project_folder, monkeypatch, surface):
    monkeypatch.chdir(project_folder)
    registry.set_module_state('dispatch', True)
    chassis.surface(project_folder)
    settings.put('dispatch_agents', 3, project_folder)
    value = settings.value
    refreshed = False

    def refreshing_value(key, folder):
        nonlocal refreshed
        if key == 'dispatch_agents' and not refreshed:
            refreshed = True
            registry.set_module_state('hello', True)
            chassis.refresh_modules()
        return value(key, folder)

    monkeypatch.setattr(settings, 'value', refreshing_value)
    replies = []
    request = SimpleNamespace(send=lambda status, body: replies.append((status, body)))
    if surface == 'module':
        server.Handler.dispatch_autostart(request, {'project': 'proj'})
    else:
        served = server.Server('127.0.0.1', 0, 'nonce')
        worker = threading.Thread(target=served.serve_forever, daemon=True)
        worker.start()
        connection = http.client.HTTPConnection('127.0.0.1', served.port, timeout=10)
        try:
            connection.request('GET', '/api/dispatch-autostart?project=proj')
            response = connection.getresponse()
            replies.append((response.status, json.loads(response.read())))
        finally:
            connection.close()
            served.shutdown()
            worker.join(5)
            served.server_close()
            served.vouch.close()
    assert refreshed
    assert replies[0][0] == 200
    assert replies[0][1]['agents'] == 3
    assert value('dispatch_registry_agents', project_folder) == []


def test_agent_choices_survive_unrelated_module_refresh(project_folder, monkeypatch):
    monkeypatch.chdir(project_folder)
    registry.set_module_state('dispatch', True)
    chassis.surface(project_folder)
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
    assert 'codex' in settings.SCHEMA['dispatch_agent'].options(project_folder)
    assert refreshed


@pytest.mark.parametrize('surface', ['module', 'http'])
def test_merges_keeps_its_package_through_unrelated_refresh(store, project_folder, monkeypatch, surface):
    monkeypatch.chdir(project_folder)
    registry.set_module_state('dispatch', True)
    chassis.surface(project_folder)
    call = chassis.call
    refreshed = False

    def refreshing_call(function, *args):
        nonlocal refreshed
        if function.__name__ == 'merges' and not refreshed:
            refreshed = True
            registry.set_module_state('hello', True)
            chassis.refresh_modules()
        return call(function, *args)

    monkeypatch.setattr(chassis, 'call', refreshing_call)
    if surface == 'module':
        assert server.module_verb({'project': 'proj'}, 'dispatch', 'merges', {}) == {'merges': []}
    else:
        served = server.Server('127.0.0.1', 0, 'nonce')
        worker = threading.Thread(target=served.serve_forever, daemon=True)
        worker.start()
        connection = http.client.HTTPConnection('127.0.0.1', served.port, timeout=10)
        try:
            connection.request('GET', '/api/merges?project=proj')
            response = connection.getresponse()
            body = json.loads(response.read())
            assert response.status == 200, body
            assert body == {'merges': []}
        finally:
            connection.close()
            served.shutdown()
            worker.join(5)
            served.server_close()
            served.vouch.close()
    assert refreshed
