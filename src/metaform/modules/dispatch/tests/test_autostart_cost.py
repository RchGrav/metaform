"""Autostart reads selection inputs once and preserves ticket selection rules."""
from collections import Counter

import pytest

from metaform.modules.dispatch.tests.test_dispatch import dispatch  # noqa: F401 -- fixture

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('VIEW-042')]


def test_autostart_reads_work_once_and_uses_bulk_settings(dispatch, run, monkeypatch):  # noqa: F811
    from metaform.data import Store
    from metaform.module import context
    from metaform.modules import dispatch as module
    from metaform.modules.dispatch import recovery

    run('set', '--dispatch-autostart', '--dispatch-agents=2', cwd=dispatch.folder)
    first = dispatch.id
    second = dispatch.store.add_work(dispatch.node, 'unbuilt', task='Second ticket').id
    held = dispatch.store.add_work(dispatch.node, 'unbuilt', task='Held ticket').id
    run('map', 'work', 'op=edit', f'id={held}', 'hold=true', cwd=dispatch.folder)
    run('map', 'work', 'op=edit', f'id={first}', 'eligible=["claude"]', 'glyph=kite', cwd=dispatch.folder)
    run('map', 'work', 'op=edit', f'id={second}', 'eligible=["gemini"]', cwd=dispatch.folder)
    calls = Counter()
    get = Store.__getattr__

    def counted(self, name):
        method = get(self, name)
        if name != 'work':
            return method
        def work(*args, **kwargs):
            calls['work'] += 1
            return method(*args, **kwargs)
        return work

    def start(ctx):
        calls['starts'] += 1
        return dict(ctx.nouns)

    monkeypatch.setattr(Store, '__getattr__', counted)
    monkeypatch.setattr(module, 'start', start)
    monkeypatch.setattr(recovery, 'recover', lambda ctx: {'released': []})
    result = module.autostart(context('dispatch', dispatch.folder, project='proj'))
    assert result['started'] == [{'id': first, 'agent': 'claude'}, {'id': second, 'agent': 'gemini'}]
    assert calls['work'] == 1, 'selection must not reread work to obtain map settings'


def test_session_verification_reuses_the_unfiltered_open_work_snapshot(dispatch, monkeypatch):  # noqa: F811
    from metaform.data import Store
    from metaform.modules import dispatch as module

    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('sessions', {'session_id': 'live', 'work_id': dispatch.id, 'agent': 'codex',
                               'state': 'running', 'started': '2026-10-05', 'pid': 1, 'port': 1, 'token': 'test',
                               'nonce': '1234567', 'seq': 1})
    opened = dispatch.store.work(open=True, limit=0).results
    seen = []
    monkeypatch.setattr(module, 'session_status', lambda store, row, *, done: seen.append(done) or row)
    monkeypatch.setattr(dispatch.store, 'work', lambda *args, **kwargs: pytest.fail('work was read again'))
    assert module.sessions(dispatch.store, open_work=opened)[0]['session_id'] == 'live'
    assert seen == [False]
