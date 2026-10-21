"""Dispatch settings writes retain registry choices across unrelated module changes."""
import http.client
import json
import threading

import pytest

from metaform import home as registry
from metaform import module as chassis
from metaform import settings
from metaform.modules.web import server

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('VIEW-042')]


def test_dispatch_settings_post_keeps_registry_choices_during_refresh(project_folder, monkeypatch):
    monkeypatch.chdir(project_folder)
    monkeypatch.setattr(chassis, 'page_caller', lambda *_: None)
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

    served = server.Server('127.0.0.1', 0, 'nonce')
    scheduled = []
    monkeypatch.setattr(served, 'schedule_dispatch', lambda *args: scheduled.append(args))
    monkeypatch.setattr(settings, 'value', refreshing_value)
    worker = threading.Thread(target=served.serve_forever, daemon=True)
    worker.start()
    connection = http.client.HTTPConnection('127.0.0.1', served.port, timeout=10)
    try:
        connection.request('GET', '/')
        page = connection.getresponse()
        page.read()
        cookie = page.getheader('Set-Cookie')
        assert cookie is not None
        connection.request('POST', '/api/dispatch-autostart',
                           body=json.dumps({'project': 'proj', 'value': False, 'agent': 'goose', 'agents': 3}),
                           headers={'Content-Type': 'application/json', 'Cookie': cookie.split(';', 1)[0],
                                    'Origin': f'http://127.0.0.1:{served.port}'})
        response = connection.getresponse()
        body = json.loads(response.read())
        assert response.status == 200, body
        assert refreshed
        assert body['value'] is False
        assert body['agent'] == 'goose'
        assert body['agents'] == 3
        assert body['most'] == settings.SCHEMA['dispatch_agents'].max
        assert value('dispatch_registry_agents', project_folder) == ['goose@1.54.0']
        assert value('dispatch_agent', project_folder) == 'goose'
        assert value('dispatch_agents', project_folder) == 3
        assert len(scheduled) == 1
        assert scheduled[0][0] == 'proj'
    finally:
        connection.close()
        served.shutdown()
        worker.join(5)
        served.server_close()
        served.vouch.close()
