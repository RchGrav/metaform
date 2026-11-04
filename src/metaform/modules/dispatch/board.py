"""Factual project notifications for runner failures, without board execution policy."""
from __future__ import annotations

from metaform.module import Context


def died(ctx: Context, work_id: str, session_id: str, what: str) -> None:
    """Keep recovery's observed runner failure in project notifications without waking an agent."""
    from .orchestration import TRANSPORT
    message_id = f'runner-died:{session_id}'
    TRANSPORT.notify_user(ctx, {'message_id': message_id, 'kind': 'runner_died', 'state': 'ended',
                               'work_id': work_id, 'session_id': session_id,
                               'text': f'{work_id}: runner {session_id} died; {what}.'}, message_id)
