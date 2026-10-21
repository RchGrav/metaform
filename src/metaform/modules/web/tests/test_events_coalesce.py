"""A page's events stream merges a burst of dispatch-only events and passes map events through at once, VIEW-018."""
import json
import time
from urllib.parse import parse_qs, urlsplit

import pytest

from metaform.modules.web.tests.test_web import (
    browser,  # noqa: F401  browser is a fixture
    events_on,
    live_session,
    mapped,  # noqa: F401  mapped is a fixture
    opened,
    simulated_dispatch_control,  # noqa: F401  autouse fixture for live_session
    started,
    thread_line,
    web,  # noqa: F401  web is a fixture
)

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('VIEW-018')]


def test_a_burst_of_agent_lines_wakes_the_page_a_few_times_and_a_map_event_arrives_at_once(run, home, web,  # noqa: F811
                                                                                             tmp_path):
    from metaform import relay
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    started(run)
    heard, first = events_on(web)
    lines = {'project': 'proj', 'base_id': 'm', 'tables': 'dispatch', 'dispatch_tables': ['dispatch.lines']}
    for index in range(20):
        relay.deliver('map.changed', lines if index != 10 else {**lines, 'dispatch_tables': ['dispatch.sessions']})
        time.sleep(0.0025)
    signal = {**lines, 'signal': {'signal': 'spinning-time'}}
    relay.deliver('map.changed', signal)
    work = {'project': 'proj', 'base_id': 'm', 'tables': ['work']}
    sent = time.monotonic()
    relay.deliver('map.changed', work)
    assert first.wait(5)
    deadline = time.monotonic() + 5
    while not any(event['payload'] == work for event in heard) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert time.monotonic() - sent < 0.25  # not held for the merge window
    payloads = [event['payload'] for event in heard if event['payload'].get('base_id') == 'm']
    assert 1 <= len(payloads) - 2 <= 4, payloads  # the burst merged into a handful
    assert payloads[-2:] == [signal, work]  # a signal is never merged away; the map event is unchanged
    merged = set().union(*(set(payload['dispatch_tables']) for payload in payloads[:-2]))
    assert merged == {'dispatch.lines', 'dispatch.sessions'}


@pytest.mark.req('BASE-053')
def test_merged_agent_events_name_every_ticket_and_kind_each_named():
    """A page's stream merges a burst of dispatch-only events; the merged one names the tickets, sessions and kinds
    every one of them named, so the page reads for each, and none when one of them left a field out."""
    from metaform.modules.web.server import coalesce
    def event(work, kind, **more):
        return {'topic': 'map.changed', 'payload': {'project': 'p', 'base_id': 'b', 'tables': 'dispatch',
                                                   'dispatch_tables': ['dispatch.lines'], 'work_ids': [work],
                                                   'session_ids': [], 'kinds': [kind], **more}}
    merged = coalesce(event('w1', 'line'), event('w2', 'session'))
    assert merged is not None
    assert merged['payload']['work_ids'] == ['w1', 'w2'] and merged['payload']['kinds'] == ['line', 'session']
    unknown = event('w3', 'line')
    del unknown['payload']['work_ids']
    merged = coalesce(event('w1', 'line'), unknown)
    assert merged is not None and 'work_ids' not in merged['payload']


def test_unrelated_session_burst_reads_nothing_and_shown_session_reads_only_named_ids(
        run, web, mapped, browser):  # noqa: F811
    from metaform.data import Node, Store
    run('enable', 'dispatch')
    store = Store('proj')
    worked = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='Keep this session visible')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.agentsIdle()', timeout=15000)
    page.evaluate('''async () => {
      const {mergeSessions} = await import('/page/app/agents/dispatch.js');
      mergeSessions(['unshown-session'], {sessions: [{session_id: 'unshown-session', work_id: 'unshown-work',
        state: 'ended', seq: -1}], signals: [], states: {}, subagents: []});
    }''')
    reads = []
    page.on('request', lambda sent: reads.append(sent.url) if '/api/dispatch-sessions?' in sent.url else None)
    page.evaluate('''async () => {
      const {changed} = await import('/page/app/live/stream.js');
      const {S} = await import('/page/app/core/reads.js');
      const event = {topic: 'map.changed', payload: {project: S.project, base_id: S.base,
        tables: 'dispatch', dispatch_tables: ['dispatch.sessions'], kinds: ['session'],
        work_ids: ['unshown-work'], session_ids: ['unshown-session']}};
      await Promise.all(Array.from({length: 50}, () => changed(event)));
      await changed({topic: 'map.changed', payload: {project: S.project, tables: 'dispatch', kinds: ['session']}});
    }''')
    page.wait_for_function('() => window.metaform.agentsIdle()')
    assert reads == [], 'Unrelated or unnamed events must never read the session list.'
    page.evaluate('''async work => {
      const {changed} = await import('/page/app/live/stream.js');
      const {S} = await import('/page/app/core/reads.js');
      const event = {topic: 'map.changed', payload: {project: S.project, base_id: S.base,
        tables: 'dispatch', dispatch_tables: ['dispatch.sessions'], kinds: ['session'],
        work_ids: [work], session_ids: ['shown-session']}};
      await Promise.all(Array.from({length: 50}, () => changed(event)));
    }''', worked.id)
    page.wait_for_function('() => window.metaform.agentsIdle()')
    assert len(reads) == 1, reads
    queries = [parse_qs(urlsplit(url).query) for url in reads]
    assert all(query.get('session_ids') == ['["shown-session"]'] for query in queries), queries
    assert all('id' not in query and 'ids' not in query for query in queries), queries
    reads.clear()
    page.evaluate('''async () => {
      const {changed} = await import('/page/app/live/stream.js');
      const {S} = await import('/page/app/core/reads.js');
      await changed({topic: 'map.changed', payload: {project: S.project, base_id: 'another-base',
        tables: 'dispatch', dispatch_tables: ['dispatch.sessions'], kinds: ['session'],
        work_ids: ['new-work'], session_ids: ['new-session']}});
    }''')
    page.wait_for_function('() => window.metaform.agentsIdle()')
    assert [parse_qs(urlsplit(url).query).get('session_ids') for url in reads] == [['["new-session"]']], reads
    assert problems == []


def test_open_chat_reads_its_session_and_ignores_another_session_on_the_same_ticket(
        run, web, mapped, browser):  # noqa: F811
    from metaform.data import Node, Store
    run('enable', 'dispatch')
    store = Store('proj')
    worked = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='Keep this conversation')
    live_session(worked.id)
    session = f's-{worked.id}'
    thread_line(worked.id, 1, 'The selected conversation')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.agentsIdle()', timeout=15000)
    reads = []
    page.on('request', lambda sent: reads.append(sent.url) if '/api/dispatch-sessions?' in sent.url else None)
    page.evaluate('''async ([work, session]) => {
      const {openHelpdesk} = await import('/page/app/dock/threads.js');
      openHelpdesk(work, 'Selected conversation', '', session);
    }''', [worked.id, session])
    page.wait_for_function('() => document.querySelector("#helpdesk .log").textContent'
                           '.includes("The selected conversation")')
    queries = [parse_qs(urlsplit(url).query) for url in reads]
    assert queries and all(query.get('session') == [session] for query in queries), queries
    reads.clear()
    page.evaluate('''async work => {
      const {changed} = await import('/page/app/live/stream.js');
      const {S} = await import('/page/app/core/reads.js');
      await changed({topic: 'map.changed', payload: {project: S.project, base_id: S.base,
        tables: 'dispatch', dispatch_tables: ['dispatch.lines'], kinds: ['line'],
        work_ids: [work], session_ids: ['another-session']}});
    }''', worked.id)
    page.wait_for_function('() => window.metaform.agentsIdle()')
    assert reads == [], 'Another session on the same ticket must not reread the open chat.'
    page.evaluate('''async () => {
      const {renderBoard} = await import('/page/app/board/board.js');
      document.querySelector('#board').hidden = false;
      await renderBoard();
    }''')
    queries = [parse_qs(urlsplit(url).query) for url in reads]
    shown = page.evaluate('() => [...document.querySelectorAll("#board .card")].map(card => card.dataset.id)')
    assert len(queries) == 1 and set(json.loads(queries[0]['ids'][0])) == set(shown), queries
    assert worked.id in shown
    assert 'session_ids' not in queries[0] and 'id' not in queries[0], queries
    reads.clear()
    page.evaluate('''async () => {
      const {renderAgents} = await import('/page/app/agents/dispatch.js');
      const real = window.fetch;
      window.originalSessionFetch = real;
      window.snapshotReady = false;
      const held = new Promise(done => { window.releaseSnapshot = done; });
      window.fetch = async (url, ...rest) => {
        const query = new URL(url, location.href);
        if (query.pathname !== '/api/dispatch-sessions' || query.searchParams.has('session_ids')
          || query.searchParams.has('ids') || query.searchParams.has('id')) return real(url, ...rest);
        const response = await real(url, ...rest), body = await response.json();
        window.snapshotReady = true;
        await held;
        return new Response(JSON.stringify({...body, sessions: []}), {headers: {'Content-Type': 'application/json'}});
      };
      window.pendingSessionList = renderAgents();
    }''')
    page.wait_for_function('() => window.snapshotReady')
    page.evaluate('''async ([work, session]) => {
      const {changed} = await import('/page/app/live/stream.js');
      const {S} = await import('/page/app/core/reads.js');
      await changed({topic: 'map.changed', payload: {project: S.project, base_id: S.base,
        tables: 'dispatch', dispatch_tables: ['dispatch.sessions'], kinds: ['session'],
        work_ids: [work], session_ids: [session]}});
      await new Promise(requestAnimationFrame);
    }''', [worked.id, session])
    assert not any('session_ids=' in url for url in reads), reads
    page.evaluate('() => window.releaseSnapshot()')
    page.wait_for_function('() => window.metaform.agentsIdle()')
    assert page.evaluate('''async session => (await import('/page/app/agents/dispatch.js'))
      .D.sessions.some(one => one.session_id === session)''', session)
    page.evaluate('() => { window.fetch = window.originalSessionFetch; }')
    assert problems == []
