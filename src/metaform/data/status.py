"""One status vocabulary for work at a node, mapped to the MCP Tasks and A2A task states.

Tickets and agent sessions report these states, so
the person, an orchestrator and the agents read one set, and any of them is offered as an MCP task or an A2A task by
a lookup in this module alone.

| Metaform         | Meaning                                              | MCP Tasks        | A2A 1.0                     |
|------------------|------------------------------------------------------|------------------|-----------------------------|
| `submitted`      | received, not yet taken up                           | `working`        | `TASK_STATE_SUBMITTED`      |
| `running`        | being worked                                         | `working`        | `TASK_STATE_WORKING`        |
| `waiting`        | waiting on child work it handed out                  | `working`        | `TASK_STATE_WORKING`        |
| `input_required` | paused on the person: something only they decide     | `input_required` | `TASK_STATE_INPUT_REQUIRED` |
| `completed`      | finished, its result kept                            | `completed`      | `TASK_STATE_COMPLETED`      |
| `failed`         | finished with a named error                          | `failed`         | `TASK_STATE_FAILED`         |
| `cancelled`      | stopped by the person or its caller before it ended  | `cancelled`      | `TASK_STATE_CANCELED`       |

`waiting` and `input_required` are kept apart because they are resolved by different parties: children returning
resume a waiting run on their own, while a run paused on the person goes on only when the person answers. MCP Tasks
has no queued state, so `submitted` is `working` there, as a task is from the moment it is created.

The last three are terminal: once reached, nothing changes them, as in both standards. `TRANSITIONS` names every
other move; a move it does not name is refused by `moved`.

Sources, read 2026-10-12: the MCP Tasks extension, `io.modelcontextprotocol/tasks`, stable schema 2026-07-28,
`TaskStatus` in github.com/modelcontextprotocol/ext-tasks schema/2026-07-28/schema.ts, with `statusMessage` for any
status; A2A 1.0, section 4.1.3 `TaskState`, serialized as its ProtoJSON enum names (a2a-protocol.org/latest/specification).
A2A states that depend on who resolves the work are a reason inside a state, and `a2a` gives them:

- `input_required` with the reason `person` is `TASK_STATE_WORKING`. A2A's interrupted states ask the A2A client to
  act: input-required is answered by the client's next message on the task, auth-required by the client's
  credentials (A2A 1.0 sections 4.1.3 and 7.6). An A2A client is another agent, so work that waits on Metaform's own
  person (an agent's login, its permission or question, an agent stopped with its ticket open, a run paused on the
  person) is still being worked as that client sees it. MCP Tasks, whose elicitation reaches the person, keeps it
  `input_required`.
- `input_required` with the reason `login` is `TASK_STATE_AUTH_REQUIRED`: the state a remote agent reports when it
  needs credentials, read back as work waiting for the person to log it in. Metaform's own A2A server never sends it,
  since its client cannot log Metaform's agents in.
- `failed` with the reason `rejected` is `TASK_STATE_REJECTED`, for work refused before it starts. Nothing produces it
  today: a ticket `startable` refuses stays in To do, where the person can still start it, so it has not ended.

MCP Tasks has none of these reasons, so they keep their state's own mapping there. These follow the A2A plan's
mapping, PLAN.md section 3.6, as amended for who resolves an interrupted state.
"""
from __future__ import annotations

from typing import Literal

from ..errors import StoreError

State = Literal['submitted', 'running', 'waiting', 'input_required', 'completed', 'failed', 'cancelled']
STATES: tuple[State, ...] = ('submitted', 'running', 'waiting', 'input_required', 'completed', 'failed', 'cancelled')
TERMINAL: tuple[State, ...] = ('completed', 'failed', 'cancelled')
OPEN: tuple[State, ...] = tuple(state for state in STATES if state not in TERMINAL)

TRANSITIONS: dict[State, tuple[State, ...]] = {
    'submitted': ('running', 'cancelled'),
    'running': ('running', 'waiting', 'input_required', 'completed', 'failed', 'cancelled'),
    'waiting': ('waiting', 'running', 'cancelled'),
    'input_required': ('running', 'cancelled'),
    'completed': (), 'failed': (), 'cancelled': (),
}

MCP_TASKS: dict[State, str] = {
    'submitted': 'working', 'running': 'working', 'waiting': 'working', 'input_required': 'input_required',
    'completed': 'completed', 'failed': 'failed', 'cancelled': 'cancelled'}
A2A: dict[State, str] = {
    'submitted': 'TASK_STATE_SUBMITTED', 'running': 'TASK_STATE_WORKING', 'waiting': 'TASK_STATE_WORKING',
    'input_required': 'TASK_STATE_INPUT_REQUIRED', 'completed': 'TASK_STATE_COMPLETED', 'failed': 'TASK_STATE_FAILED',
    'cancelled': 'TASK_STATE_CANCELED'}


# A2A states that are a Metaform state with a reason, PLAN.md section 3.6: (state, reason) to the A2A state.
A2A_REASONS: dict[tuple[State, str], str] = {
    ('input_required', 'person'): 'TASK_STATE_WORKING', ('input_required', 'login'): 'TASK_STATE_AUTH_REQUIRED',
    ('failed', 'rejected'): 'TASK_STATE_REJECTED'}


def a2a(state: State, reason: str | None = None) -> str:
    """The A2A 1.0 task state of work in `state`, for the reason it is there when A2A names that reason apart."""
    return A2A_REASONS.get((state, reason or ''), A2A[state])


def known(state: str, next_step: str) -> State:
    """The state, or a refusal naming the vocabulary and the caller's next step: nothing outside it is written."""
    for one in STATES:
        if one == state:
            return one
    raise StoreError(f'{state!r} is not a status of work; the statuses are {", ".join(STATES)}.', next_step)


def moved(before: str, after: str, next_step: str) -> State:
    """The state `after`, when work in `before` may move to it; otherwise a refusal naming where it stands and the
    caller's next step."""
    start, end = known(before, next_step), known(after, next_step)
    if end not in TRANSITIONS[start]:
        allowed = ', '.join(TRANSITIONS[start]) or 'nothing, since it has ended'
        raise StoreError(f'Work that is {start} cannot become {end}; it can become {allowed}.', next_step)
    return end
