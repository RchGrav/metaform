"""ACP compaction entities retain disclosed patches without claiming hidden context knowledge."""
from __future__ import annotations

import asyncio
import json

import pytest
from acp.connection import StreamDirection, StreamEvent

from metaform.data import Store
from metaform.module import agent_context_epoch, context
from metaform.modules.dispatch.runner import Session
from metaform.modules.dispatch.tests.test_dispatch import dispatch as dispatch  # noqa: PLC0414

pytestmark = pytest.mark.kind('simulation')


def observer(dispatch):
    session = Session(context('dispatch', dispatch.folder, project='proj'), Store('proj', module='dispatch'),
                      dispatch.ticket(), 'claude', ['true'])
    session.session_id, session.runner = 'compaction-session', 'compaction-runner'
    return session


async def send(session, *updates, child=None):
    for update in updates:
        session.observe(StreamEvent(StreamDirection.INCOMING, {'method': 'session/update', 'params': {
            'sessionId': child or session.session_id, 'update': update}}))
    await asyncio.gather(*list(session.tasks))


def lifecycle(ident, status, **patch):
    return {'sessionUpdate': 'compaction_update', 'compactionId': ident, 'status': status, **patch}


def chunk(ident, text, **patch):
    return {'sessionUpdate': 'compaction_summary_chunk', 'compactionId': ident,
            'content': {'type': 'text', 'text': text}, **patch}


def entities(session):
    return list(session.acp['compactions'].values())


def lines(session):
    with session.store.tables(write=False) as tx:
        return tx.rows('session_lines', {'session_id': session.session_id},
                       by=('session_id', 'seq'), limit=0).results


def test_patches_chunks_and_repeated_completion_update_one_timeline_entity(dispatch):
    session = observer(dispatch)

    async def scenario():
        await session.note('before', 'message', 'Earlier message.')
        await send(session, chunk('c1', 'A', _meta={'chunk': 1}), chunk('c1', 'B'))
        first = next(row for row in lines(session) if row['kind'] == 'compaction')
        assert entities(session)[0]['status'] == 'in_progress'
        assert entities(session)[0]['summary_chunk_meta'] == [{'chunk': 1}, None]
        await session.note('after', 'message', 'Later message.')
        await send(session, lifecycle('c1', 'in_progress', error='temporary', _meta={'first': 1}),
                   lifecycle('c1', 'completed'))
        assert entities(session)[0]['summary'] == [{'type': 'text', 'text': 'A'}, {'type': 'text', 'text': 'B'}]
        assert entities(session)[0]['error'] == 'temporary'
        assert agent_context_epoch(dispatch.folder, session.runner, project='proj') == 1
        await send(session, lifecycle('c1', 'completed', summary=[{'type': 'text', 'text': 'Replacement'}],
                                      error=None, _meta={'second': 2}), chunk('c1', 'C'))
        assert entities(session)[0]['summary'] == [
            {'type': 'text', 'text': 'Replacement'}, {'type': 'text', 'text': 'C'}]
        assert entities(session)[0]['error'] is None and entities(session)[0]['_meta'] == {'second': 2}
        await send(session, lifecycle('c1', 'completed', summary=[], _meta=None),
                   lifecycle('c1', 'completed', summary=None))
        assert entities(session)[0]['summary'] is None and entities(session)[0]['_meta'] is None
        assert agent_context_epoch(dispatch.folder, session.runner, project='proj') == 1
        assert session.recompacted and not session.pending
        kept = lines(session)
        compactions = [row for row in kept if row['kind'] == 'compaction']
        assert len(compactions) == 1 and compactions[0]['seq'] == first['seq']
        before = next(row for row in kept if row['name'] == 'before')
        after = next(row for row in kept if row['name'] == 'after')
        assert before['seq'] < first['seq'] < after['seq']
        assert json.loads(compactions[0]['text'])['retained_context'] == 'unknown'

    asyncio.run(scenario())


def test_failed_cancelled_and_unknown_statuses_preserve_disclosed_state_without_epoch_change(dispatch):
    session = observer(dispatch)

    async def scenario():
        for status in ('failed', 'cancelled', 'future_status', '_adapter_state'):
            await send(session, chunk(status, 'Partial summary.'), lifecycle(status, status, error='reported error'))
        assert {one['status'] for one in entities(session)} == {
            'failed', 'cancelled', 'future_status', '_adapter_state'}
        assert all(one['summary'] == [{'type': 'text', 'text': 'Partial summary.'}] for one in entities(session))
        assert all(one['error'] == 'reported error' and not one['completed_observed'] for one in entities(session))
        assert agent_context_epoch(dispatch.folder, session.runner, project='proj') == 0
        assert not session.recompacted and not session.pending

    asyncio.run(scenario())


def test_resumed_compaction_identity_and_replay_do_not_reset_parent_context(dispatch):
    session = observer(dispatch)

    async def scenario():
        await send(session, lifecycle('completed-once', 'completed', summary=[{'type': 'text', 'text': 'Visible.'}]))
        first_seq = next(row['seq'] for row in lines(session) if row['kind'] == 'compaction')
        resumed = observer(dispatch)
        resumed.continue_thread()
        assert entities(resumed)[0]['completed_observed']
        resumed.replaying = True
        await send(resumed, lifecycle('completed-once', 'completed'),
                   lifecycle('replay-only', 'completed', summary=[{'type': 'text', 'text': 'Historical.'}]))
        resumed.replaying = False
        await send(resumed, lifecycle('completed-once', 'completed'), lifecycle('replay-only', 'completed'))
        assert agent_context_epoch(dispatch.folder, resumed.runner, project='proj') == 1
        assert not resumed.recompacted
        kept = [row for row in lines(resumed) if row['kind'] == 'compaction']
        assert len(kept) == 2 and kept[0]['seq'] == first_seq
        # Identical IDs in a child session belong to that child's observation, never the parent's epoch.
        await send(resumed, lifecycle('completed-once', 'completed'), child='child-session')
        assert len(entities(resumed)) == 3
        assert len([row for row in lines(resumed) if row['kind'] == 'compaction']) == 2
        with resumed.store.tables(write=False) as tx:
            child_rows = tx.rows('session_lines', {'session_id': 'child-session'}, limit=0).results
        assert len(child_rows) == 1 and child_rows[0]['kind'] == 'compaction'
        assert agent_context_epoch(dispatch.folder, resumed.runner, project='proj') == 1
        assert not resumed.pending

    asyncio.run(scenario())


def test_replay_replacement_and_chunks_follow_same_patch_semantics(dispatch):
    session = observer(dispatch)

    async def scenario():
        await send(session, chunk('summary', 'Old'), lifecycle('summary', 'completed'))
        session.replaying = True
        await send(session, lifecycle('summary', 'completed', summary=[{'type': 'text', 'text': 'Replacement'}]),
                   chunk('summary', 'Tail'))
        assert entities(session)[0]['summary'] == [
            {'type': 'text', 'text': 'Replacement'}, {'type': 'text', 'text': 'Tail'}]
        assert agent_context_epoch(dispatch.folder, session.runner, project='proj') == 1
        assert len([row for row in lines(session) if row['kind'] == 'compaction']) == 1

    asyncio.run(scenario())


def test_v2_metadata_patches_only_top_level_keys_and_null_clears(dispatch):
    session = observer(dispatch)
    session.acp['protocol_version'] = 2

    async def scenario():
        await send(session, lifecycle('meta', 'in_progress', _meta={'a': {'nested': 1, 'keep': 2}, 'b': 2}),
                   lifecycle('meta', 'in_progress', _meta={}),
                   lifecycle('meta', 'failed', _meta={'a': {'nested': None}, 'b': None}))
        assert entities(session)[0]['_meta'] == {'a': {'nested': None}}
        await send(session, lifecycle('meta', 'failed', _meta=None))
        assert entities(session)[0]['_meta'] is None
        assert agent_context_epoch(dispatch.folder, session.runner, project='proj') == 0

    asyncio.run(scenario())


def test_legacy_missing_id_is_labeled_and_does_not_claim_a_context_inventory(dispatch):
    session = observer(dispatch)

    async def scenario():
        await send(session, {'sessionUpdate': 'compaction_update', 'status': 'completed'})
        assert entities(session)[0]['legacy'] and entities(session)[0]['compaction_id'] is None
        assert entities(session)[0]['retained_context'] == 'unknown'
        assert not session.pending

    asyncio.run(scenario())
