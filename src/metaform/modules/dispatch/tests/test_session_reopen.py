"""Unavailable native sessions retain readable history without repeated failed resumes, BASE-052."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import acp
import pytest

from metaform.modules.dispatch.runner import AUTH_REQUIRED, Session

pytestmark = pytest.mark.kind('fixture')


def session(*, resume=True, error=None):
    return SimpleNamespace(
        acp={'capabilities': {'resume': resume, 'load': True}, 'resumed': None},
        resume='kept-session', work_id='kept-work', folder='/project', name='Codex', replaying=False,
        conn=SimpleNamespace(resume_session=AsyncMock(side_effect=error, return_value='resumed'),
                             load_session=AsyncMock(side_effect=error, return_value='loaded')),
        save_state=AsyncMock(), note=AsyncMock(), table=AsyncMock(), ended=asyncio.Event(), how='',
    )


@pytest.mark.req('BASE-052')
@pytest.mark.parametrize('resume', [True, False])
def test_missing_native_session_disables_resume_and_keeps_history_readable(resume):
    error = acp.RequestError.internal_error({'details': 'no rollout found for thread id kept-session'})
    kept = session(resume=resume, error=error)

    assert asyncio.run(Session.reopen(kept, [])) is None

    assert kept.acp['capabilities'] == {'resume': False, 'load': False}
    kept.save_state.assert_awaited_once()
    assert kept.ended.is_set()
    assert kept.how.startswith('session unavailable:'), 'known missing context is not an adapter crash'
    assert 'metaform dispatch talk session=kept-work:kept-session' in kept.note.await_args.args[2]
    assert kept.conn.resume_session.await_count + kept.conn.load_session.await_count == 1


@pytest.mark.req('BASE-052')
@pytest.mark.parametrize('error', [acp.RequestError(AUTH_REQUIRED, 'login'),
                                 acp.RequestError.internal_error(),
                                 acp.RequestError.internal_error({'details': 'unrelated failure'}),
                                 acp.RequestError.internal_error({'details': 'no rollout found for thread id other'}),
                                 acp.RequestError.resource_not_found('kept-session')])
def test_unclassified_resume_errors_keep_original_failure_and_capabilities(error):
    kept = session(error=error)

    with pytest.raises(acp.RequestError) as caught:
        asyncio.run(Session.reopen(kept, []))

    assert caught.value is error
    assert kept.acp['capabilities'] == {'resume': True, 'load': True}
    kept.save_state.assert_not_awaited()
    assert not kept.ended.is_set()


@pytest.mark.req('BASE-052')
@pytest.mark.parametrize('resume', [True, False])
def test_available_session_keeps_existing_resume_and_replay_behavior(resume):
    kept = session(resume=resume)

    assert asyncio.run(Session.reopen(kept, [])) == ('resumed' if resume else 'loaded')

    call = kept.conn.resume_session if resume else kept.conn.load_session
    call.assert_awaited_once_with(session_id='kept-session', cwd='/project', mcp_servers=[])
    assert kept.replaying is (not resume)
    assert kept.acp['resumed'] == ('resume' if resume else 'load')
