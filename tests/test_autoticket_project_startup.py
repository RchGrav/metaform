"""Project startup tolerates fault groups whose map tickets were removed."""
from __future__ import annotations

import threading

import pytest

from metaform import module as chassis
from metaform.data import Store
from metaform.modules.autoticket.tests.test_autoticket import mapped, tickets, web_fault

pytestmark = pytest.mark.kind('fixture')


def test_project_startup_skips_removed_fault_tickets(run, tmp_path, monkeypatch):
    run('enable', 'autoticket')
    project = tmp_path / 'proj'
    project.mkdir()
    run('add', 'project', 'proj', str(project))
    store = mapped(project)
    web_fault(project)
    [record] = tickets(store)
    store.remove_work(record.id)
    providers = [(owner, start) for owner, start in chassis.provided(project, 'project.background')
                 if owner == 'autoticket']
    assert providers
    original = Store.__getattr__

    def read(self, name):
        assert name != 'work', 'Project startup must not scan fault tickets.'
        return original(self, name)

    def timer(*args, **kwargs):
        pytest.fail('Project startup must not schedule fault proof timers.')

    monkeypatch.setattr(Store, '__getattr__', read)
    monkeypatch.setattr(threading, 'Timer', timer)
    for owner, start in providers:
        ctx = chassis.context(owner, project, switches={'autoticket_watch': False})
        service = start(ctx)
        try:
            assert service is None
        finally:
            if service is not None:
                service.close()
