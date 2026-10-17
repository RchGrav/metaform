"""A runner writes every line at once and announces a burst of them as a few `dispatch.session_lines` events,
BASE-052."""
import asyncio
import time
from types import SimpleNamespace

import pytest

from metaform.data import Store
from metaform.modules.dispatch.tests.test_dispatch import dispatch  # noqa: F401  a fixture

pytestmark = [pytest.mark.kind('simulation'), pytest.mark.req('BASE-052'), pytest.mark.req('VIEW-018')]


def test_a_burst_of_lines_is_written_row_by_row_and_announced_a_few_times(dispatch):  # noqa: F811
    from metaform.modules.dispatch.runner import LINES_EVERY, Session
    published = []

    async def publish_async(topic, payload):
        published.append(payload)

    def announced():
        return [payload for payload in published if 'dispatch.session_lines' in (payload.get('dispatch_tables') or [])]

    async def exercise():
        store = Store('proj', module='dispatch')
        held = Session(SimpleNamespace(publish_async=publish_async, nouns={}), store, dispatch.ticket(), 'claude', [])
        held.session_id = 'burst'
        began = time.monotonic()
        for index in range(20):
            await held.note(None, 'agent_message_chunk', f'chunk {index}')
        took = time.monotonic() - began
        with store.tables() as tx:
            assert len(tx.rows('session_lines', {'session_id': 'burst'}, limit=0).results) == 20  # every row is there at once
        burst = len(announced())
        assert 1 <= burst <= 1 + took / LINES_EVERY  # the first at once, then one per LINES_EVERY at most
        await asyncio.sleep(LINES_EVERY + 0.1)
        assert len(announced()) - burst <= 1 and held.lines_due is None  # the burst's last lines announced once
        await asyncio.sleep(LINES_EVERY)
        before = len(announced())
        await held.note(None, 'agent_message_chunk', 'after a pause')
        assert len(announced()) == before + 1  # a line after a quiet spell is announced at once
        await held.note(None, 'agent_message_chunk', 'and one more')
        await held.changed(tables='dispatch')  # a state change announces the waiting line with it
        published.clear()
        await asyncio.sleep(LINES_EVERY + 0.1)
        assert published == []
    asyncio.run(exercise())
