"""A page's events stream merges a burst of dispatch-only events and passes map events through at once, VIEW-018."""
import time

import pytest

from metaform.modules.web.tests.test_web import events_on, started, web  # noqa: F401  web is a fixture

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('VIEW-018')]


def test_a_burst_of_agent_lines_wakes_the_page_a_few_times_and_a_map_event_arrives_at_once(run, home, web,  # noqa: F811
                                                                                             tmp_path):
    from metaform import relay
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    started(run)
    heard, first = events_on(web)
    lines = {'project': 'proj', 'metaform_id': 'm', 'tables': 'dispatch', 'dispatch_tables': ['dispatch.lines']}
    for index in range(20):
        relay.deliver('map.changed', lines if index != 10 else {**lines, 'dispatch_tables': ['dispatch.sessions']})
        time.sleep(0.0025)
    signal = {**lines, 'signal': {'signal': 'spinning-time'}}
    relay.deliver('map.changed', signal)
    work = {'project': 'proj', 'metaform_id': 'm', 'tables': ['work']}
    sent = time.monotonic()
    relay.deliver('map.changed', work)
    assert first.wait(5)
    deadline = time.monotonic() + 5
    while not any(event['payload'] == work for event in heard) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert time.monotonic() - sent < 0.25  # not held for the merge window
    payloads = [event['payload'] for event in heard]
    assert 1 <= len(payloads) - 2 <= 4, payloads  # the burst merged into a handful
    assert payloads[-2:] == [signal, work]  # a signal is never merged away; the map event is unchanged
    merged = set().union(*(set(payload['dispatch_tables']) for payload in payloads[:-2]))
    assert merged == {'dispatch.lines', 'dispatch.sessions'}
