import pytest

from metaform.modules.web.tests.test_web import browser, mapped, opened, started, web  # noqa: F401


@pytest.mark.browser
@pytest.mark.kind("fixture")
def test_diag(run, web, mapped, browser, monkeypatch, tmp_path):
    monkeypatch.setenv('FAKE_ACP_LOG', str(tmp_path / 'acp.log'))
    monkeypatch.setenv('FAKE_ACP_MODE', 'hold')
    from metaform import relay
    from metaform.data import Node, Store
    store = Store('proj')
    run('enable', 'dispatch')
    run('set', '--dispatch-autostart')
    worked = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='a quieter tone')
    store.take_work(worked.id, steps=2, by='claude')
    started(run)
    statuses = []

    def answered(r):
        if r.status >= 400:
            statuses.append(r)
    page, problems, _ = opened(browser, web)
    page.on('response', answered)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.agentsIdle()', timeout=15000)
    base = store.active_base().id
    reads = []
    page.on('request', lambda sent: reads.append(sent.url))
    session = {'project': 'proj', 'base_id': base, 'tables': 'dispatch', 'dispatch_tables': ['dispatch.sessions'],
               'kinds': ['session'], 'work_ids': [worked.id]}
    for _ in range(50):
        relay.deliver('map.changed', session)
    relay.deliver('map.changed', {**session, 'dispatch_tables': ['dispatch.merges'], 'kinds': ['merge']})
    drawn = {'project': 'proj', 'base_id': base, 'tables': ['objects', 'ops'], 'seq': store.sequence(),
             'kinds': ['map'], 'work_ids': []}
    for _ in range(50):
        relay.deliver('map.changed', drawn)
    run('map', 'work', 'op=step', f'id={worked.id}', 'said=Found the gain.', cwd=mapped)
    import time
    time.sleep(8)
    print('READS', [url.split('/api/')[1] for url in reads if '/api/' in url])
    print('STATUSES', [(r.status, r.url, r.text()[:1500]) for r in statuses])
    print('PROBLEMS', problems)
    import glob
    for path in glob.glob(str(mapped.parent / 'home' / '**' / '*.log'), recursive=True):
        print('LOG', path)
        print(open(path, encoding='utf-8', errors='replace').read()[-3000:])
