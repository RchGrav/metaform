"""What an agent is told when it connects: one line, then a link to the rules it works by and a link to its task.

Nothing else is linked or served at connect. A module's commands, and how each is used, are in `metaform help`,
which an agent reads in its shell when its work calls for one; the project's map is read with the `project` tool.

- `metaform://rules` is the mcp module's `connect_rules` prompt, exactly as written.
- `metaform://task/person` is for the person's own session: what Metaform is for here and how its commands are run.
- `metaform://task/intake` is for an agent a runner started on the intake: one line naming the tool it records with.
  Every other started agent's task is its first turn, so no block repeats it. An agent on the intake is linked its
  task alone: a procedure is run with the procedure and nothing beside it.
- `metaform://firstrun` is linked to the person's own session while the project has no map: the intake module's
  first-run text.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from metaform import prompt_files
from metaform.data import StoreError
from metaform.module import Stop, context, project_for, provided, startup_notices

RULES_URI = 'metaform://rules'
FIRSTRUN_URI = 'metaform://firstrun'
TASK_URI = 'metaform://task/'
PERSON = 'person'  # the name in metaform://task/<name> for the person's own sessions, which no runner started
INTAKE = 'intake'


def task() -> str | None:
    """The name of the task the agent this server serves runs, from METAFORM_TASK_NAME, which dispatch's runner sets
    on a task session's server; None for a session no task names."""
    return os.environ.get('METAFORM_TASK_NAME') or None


def dispatched() -> bool:
    """Whether a runner started the agent this server serves: METAFORM_SESSION names its runner. False for the
    person's own sessions."""
    return bool(os.environ.get('METAFORM_SESSION'))


@dataclass(frozen=True)
class Agent:
    """Who the links are decided for: the folder its server serves, the name of the task it runs, None for a session
    no task names, and whether the session is the person's own, which no runner started."""
    folder: Path
    task: str | None
    own: bool


def served_agent(folder: Path) -> Agent:
    """The agent this server serves, as its runner's environment names it."""
    return Agent(folder, task(), not dispatched())


def dispatched_agent(folder: Path, named: str | None) -> Agent:
    """An agent a runner started, on the task named `named` or on none, for the runner asking what opens its session."""
    return Agent(folder, named, False)


def first_run_text(folder: Path) -> str | None:
    """The intake module's first-run text while the project has no map, `intake.first_run`; None otherwise or with
    the intake module off."""
    for module_id, given in provided(folder, 'intake.first_run'):
        try:
            said = given(context(module_id, folder, surface='mcp'))
        except (Stop, StoreError):
            said = None
        if said:
            return said
    return None


def task_link(named: str | None, own: bool) -> str | None:
    """The task's link: metaform://task/person for the person's own session and metaform://task/intake for the intake
    task; None for every other agent a runner started, whose first turn is its instructions."""
    return TASK_URI + PERSON if own else TASK_URI + INTAKE if named == INTAKE else None


def task_text(folder: Path, agent: Agent | None = None) -> str:
    """The task block. To the person's own session: what Metaform is for here, how its commands are run, the
    project's name and the folder's notices. To the intake task: the one line naming the tool it records with."""
    agent = agent or served_agent(folder)
    if not agent.own:
        return prompt_files.module('mcp', f'task_{agent.task}') or ''
    project = project_for(folder)
    first_run = first_run_text(folder)
    lines = [prompt_files.module('mcp', 'connect_use'), prompt_files.module('mcp', 'connect_catalog'),
             prompt_files.module('mcp', 'connect_here', project=project) if project is not None else None,
             *(one for one in startup_notices(folder, project) if one != first_run)]
    return '\n\n'.join(line for line in lines if line)


def links(agent: Agent) -> list[str]:
    """The links that apply to `agent` now: its rules, the first-run text while it applies, and its task. An agent a
    runner started on the intake is linked its task alone."""
    if agent.task == INTAKE and not agent.own:
        return [TASK_URI + INTAKE]
    return [link for link in (RULES_URI, FIRSTRUN_URI if agent.own and first_run_text(agent.folder) else None,
                              task_link(agent.task, agent.own)) if link]


def opening(agent: Agent) -> str:
    """What opens an agent's session and its first turn after each compaction: mcp's `connect_directive`, then one
    line for each link."""
    directive = prompt_files.module('mcp', 'connect_directive') or ''
    return '\n'.join(line for line in (directive, *links(agent)) if line)


def connect_instructions(folder: Path) -> str:
    """The connect message of the server serving `folder`: `opening` for the agent it serves."""
    return opening(served_agent(folder))


def block_text(folder: Path, uri: str) -> str | None:
    """The text at one of the links, exactly as its prompt holds it; None when the link is not one this server
    serves the agent now."""
    agent = served_agent(folder)
    if uri == RULES_URI:
        return prompt_files.module('mcp', 'connect_rules') or ''
    if uri == FIRSTRUN_URI:
        return first_run_text(folder)
    if uri == task_link(agent.task, agent.own):
        return task_text(folder, agent)
    return None


NAMES = {RULES_URI: ('Rules', 'Read first: the rules every agent works by.'),
         FIRSTRUN_URI: ('First run', 'What to do first: this project has no map yet.')}


def listed(folder: Path) -> list[tuple[str, str, str]]:
    """The resources the server lists: each link that applies now, with its name and description."""
    return [(uri, *NAMES.get(uri, ('Task', 'What your task is and how Metaform\'s commands are run.')))
            for uri in links(served_agent(folder))]
