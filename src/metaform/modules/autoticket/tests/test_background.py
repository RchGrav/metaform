"""A registered log is watched without a browser; unrelated events do not read storage."""
import time

import pytest

from metaform.data import Store
from metaform.module import context, surface
from metaform.modules.autoticket.background import Background
from metaform.modules.autoticket.watch import Watch
from tests.storekit import small_map

pytestmark = pytest.mark.kind('simulation')


def test_background_captures_registered_log_and_releases_it(store, project_folder, tmp_path):
    small_map(store)
    log = tmp_path / 'application.log'
    log.write_text('')
    surface(project_folder)
    ctx = context('autoticket', project_folder, project='proj', nouns={'log': str(log)})
    import importlib
    importlib.import_module('metaform.modules.autoticket').add(ctx)
    background = Background(ctx)
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            with ctx.require_store().tables(write=False) as tx:
                row = tx.get('logs', {'source': str(log)})
            if row['holder']:
                break
            time.sleep(.05)
        assert row['holder']
        with log.open('a') as output:
            output.write('ERROR: alarm output failed\n')
        deadline = time.monotonic() + 10
        groups = []
        while time.monotonic() < deadline:
            with ctx.require_store().tables(write=False) as tx:
                groups = tx.rows('groups', limit=0).results
            if groups:
                break
            time.sleep(.05)
        assert len(groups) == 1
        assert 'alarm output failed' in groups[0]['example']
    finally:
        background.close()
    assert not background.thread.is_alive()


def test_irrelevant_event_burst_does_not_wake_or_read_watcher(store, project_folder, monkeypatch):
    surface(project_folder)
    ctx = context('autoticket', project_folder, project='proj')
    watching = Watch(ctx, ctx.require_store())
    def forbidden(*args, **kwargs):
        raise AssertionError('An unrelated event read storage.')
    monkeypatch.setattr(Store, 'tables', forbidden)
    for _ in range(1000):
        watching.heard({'project': 'proj', 'tables': ['dispatch.session_lines'], 'kinds': ['line']})
        watching.heard({'project': 'elsewhere', 'tables': ['autoticket.logs']})
    assert watching.events.empty()


def test_watcher_startup_failure_is_isolated_and_has_bounded_retry(monkeypatch):
    import threading
    from types import SimpleNamespace

    reported, timers = threading.Event(), []
    def failed():
        raise OSError('project unavailable')
    def report(topic, payload):
        assert topic == 'fault.raised' and 'project unavailable' in payload['message']
        reported.set()
    def timer(delay, callback):
        held = SimpleNamespace(daemon=False, start=lambda: timers.append(delay), cancel=lambda: None)
        return held
    monkeypatch.setattr(threading, 'Timer', timer)
    background = Background(SimpleNamespace(project='unavailable', require_store=failed, publish=report))
    try:
        assert reported.wait(2), 'An unavailable project must not prevent the web server from starting.'
        background.thread.join(2)
        assert timers == [2] and background.failures == 1
    finally:
        background.close()


def test_cleanup_failure_still_closes_listener_and_schedules_recovery(monkeypatch):
    import threading
    from types import SimpleNamespace

    closed, timers, faults = [], [], []
    def failed():
        raise OSError('database temporarily unavailable')
    watching = SimpleNamespace(run=failed, release=failed, stop=lambda: None, heard=lambda payload: None)
    monkeypatch.setitem(Background.run.__globals__, 'Watch', lambda *args: watching)
    monkeypatch.setattr(threading, 'Timer', lambda delay, callback: SimpleNamespace(
        daemon=False, start=lambda: timers.append(delay), cancel=lambda: None))
    # Run synchronously so an exception in finally cannot hide as an unhandled thread warning.
    monkeypatch.setattr(Background, 'start', lambda self: None)
    background = Background(SimpleNamespace(project='proj', require_store=lambda: None,
        listen=lambda heard: SimpleNamespace(close=lambda: closed.append(True)),
        publish=lambda topic, payload: faults.append(payload)))
    background.run()
    assert closed == [True] and background.listener is None
    assert timers == [2] and background.failures == 1
    assert faults and 'database temporarily unavailable' in faults[0]['message']
    background.close()
