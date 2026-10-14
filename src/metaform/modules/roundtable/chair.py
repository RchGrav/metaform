"""Who may chair a table, and how its turns reach the head agent, BASE-066.

A table is opened, and its chair controls used, only by the person or by the head agent: the agent inside Metaform
the person talks to that is not a worker, dispatch's system agent, VIEW-045. The person is the web page, and the
command line with no agent session. The head agent is a call made from the session dispatch started with
`system=true`: its runner gives that session's agent and its MCP server METAFORM_ROLE `system`, METAFORM_SESSION, the
runner's own id for the session, and METAFORM_WORK, the held ticket the person's system agent chat hangs on,
BASE-052; the call is the head agent's only when dispatch has that session running on that ticket under that runner
id. Any other agent session, a worker among them, and any call over MCP from no such session, is refused before
anything is written, with one next step, MCP-006. Like every role check in Metaform this guards against an agent's
mistakes, not an agent set on getting round it, since an agent can change its own environment.

Each turn reaches the head agent, when it chairs, through dispatch's `message` verb, as a person's message reaches a
running session: in order, waiting its turn behind the agent's own, credited to the roundtable, BASE-052. The
roundtable runner's own role is `roundtable`, so the thread never shows a turn as the person's.
"""
from __future__ import annotations

import os
from typing import Any, cast

from metaform.module import Context, Stop, call, context, surface

ROLE = 'roundtable'  # the role the runner sends the head agent its turns under, BASE-052


def verb_call(ctx: Context, module: str, verb: str, nouns: dict[str, Any]) -> Any:
    """Another module's verb, run in this process for this project through the module's own declaration, so the
    roundtable never imports it; a Stop when the module is not on the folder's surface."""
    found = next((one for one in surface(ctx.folder) if one.id == module), None)
    declared = None if found is None else next((one for one in found.verbs if one.name == verb), None)
    if declared is None:
        raise Stop(f'The {module} module is not enabled here, so {module} {verb} cannot run.',
                   f'metaform enable {module}')
    return call(declared.run, context(module, ctx.folder, project=ctx.project, nouns=nouns, surface='cli'))


def head_session(ctx: Context) -> dict[str, str] | None:
    """The head agent's ticket and dispatch session when this call comes from it, else None."""
    if os.environ.get('METAFORM_ROLE') != 'system':
        return None
    runner, work = os.environ.get('METAFORM_SESSION'), os.environ.get('METAFORM_WORK')
    if not runner or not work:
        return None
    try:
        found: Any = verb_call(ctx, 'dispatch', 'sessions', {'id': work, 'thread': False})
    except Stop:
        return None
    held: Any = cast(dict[str, Any], found).get('sessions') if isinstance(found, dict) else None
    rows = cast(list[dict[str, Any]], held) if isinstance(held, list) else []
    row = next((one for one in rows if one.get('runner') == runner and one.get('state') == 'running'), None)
    return None if row is None else {'work': work, 'session': str(row['session_id'])}


def caller(ctx: Context, what: str) -> dict[str, str]:
    """Who makes a chair call: `{'chair': 'person'}`, or the head agent with its ticket and session. Every other caller
    is refused, naming `what` it tried."""
    if ctx.surface == 'web':
        return {'chair': 'person'}
    role = os.environ.get('METAFORM_ROLE')
    if not role and not os.environ.get('METAFORM_SESSION') and ctx.surface == 'cli':
        return {'chair': 'person'}
    found = head_session(ctx)
    if found is not None:
        return {'chair': 'head', **found}
    if role and role != 'system':
        raise Stop(f'A {role} agent cannot {what}: only the person and their head agent chair a roundtable. A worker '
                   'takes part as a seat when the chair seats it.', 'metaform roundtable list')
    raise Stop(f'Only the person, on the page or the command line, and their head agent can {what}; this call comes '
               'from neither.', 'ask the person, or their head agent, to do it')


def person(ctx: Context, what: str) -> None:
    """Refuse every caller but the person."""
    if caller(ctx, what)['chair'] != 'person':
        raise Stop(f'Only the person can {what}.', 'metaform roundtable status <discussion>')


def deliver(ctx: Context, work: str, session: str, text: str) -> None:
    """One message into the head agent's running session, as dispatch's `message` sends a person's; a Stop when the
    session is not running, so the caller keeps its cursor and tries again. The runner runs with METAFORM_ROLE
    `roundtable`, so dispatch credits the message to it and never to the person."""
    verb_call(ctx, 'dispatch', 'message', {'id': work, 'session': session, 'text': [text]})
