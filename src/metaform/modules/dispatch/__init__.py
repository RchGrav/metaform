"""dispatch: Metaform starts an agent on a ticket through ACP, BASE-052.

`start` runs `run` as a process of its own, detached from the terminal, and returns at once. `run` is the ACP client
for one ticket: it starts the agent's ACP adapter in the project's folder, makes one session with Metaform's MCP
server, takes the ticket for the agent and hands it one prompt, then follows the session until it ends. Its notes, its
session record is on the map, at the ticket's node.

A ticket with an agent glyph, VIEW-040, is one of that agent's: the runner started on it works the glyph's tickets one
after another in board order, a session for each, and no ticket of a glyph whose agent is at work is started.

`message` and `stop` reach a running session over its loopback control port, kept in the session's record in this
module's `sessions` table. The runner hears each `map.changed` published in another process through the base's
listener, `ctx.listen`, and reads its open questions, QUAL-015 and BASE-053.

The ACP SDK is imported only by `runner`, so only the runner process loads it.
"""
from __future__ import annotations

import asyncio
import contextlib
import contextvars
import ctypes
import difflib
import hashlib
import inspect
import json
import mimetypes
import os
import re
import secrets
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable, Collection, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from importlib import resources
from pathlib import Path
from typing import Any, cast

from metaform import events, home, prompt_files, settings
from metaform.data import (
    BASE_VARIABLE,
    Column,
    Index,
    NewerStore,
    Node,
    Store,
    StoreError,
    Table,
    Tables,
    WorkRecord,
    status,
)
from metaform.module import (
    Context,
    Module,
    Noun,
    Pane,
    PersonsDecision,
    Provides,
    Stop,
    Subscription,
    Surface,
    ToolbarItem,
    Verb,
    agent_caller,
    call,
    child_environment,
    context,
    held_role,
    mcp_server,
    on_persons_word,
    project_for,
    provided,
    record_shown,
    request_scope,
    surface,
    work_reads,
)
from metaform.module import (
    persons_word as word_of,
)

from . import registry as agent_registry  # by another name: unloading a module drops its submodules' names
from .board import changed as board_changed
from .board import waiting as board_waiting
from .hold_review import HOLD_REVIEW_TABLES
from .hold_review import changed as hold_review_changed
from .hold_review import reconcile as review_holds
from .names import is_name
from .progress import SOURCE as PROGRESS
from .progress import blocked as rework_blocked
from .progress import changed as progress_changed
from .signals import collect, own_store, requeued, rework_limit
from .signals import read as read_signals
from .signals import read_rows as signal_rows
from .signals import rows as read_signal_rows

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ('agent-client-protocol>=0.12.1,<0.13',)
SHIPS_DISABLED = True
REMOTE_AGENT = False  # it launches agents on this machine, which a hosted sandbox does not have

# A dispatched agent's session and its transcript are this module's own tables, beside the metaform the ticket is in,
# STORE-045, and nothing of them is on the map: a node holds one note, and what an agent learns is a memory, VIEW-034.
# A line is one thing in the session's thread: the agent's words or thinking, a tool call, its plan, a turn's end, a
# prompt Metaform answered, or the person's message; `name` is what a line is kept for, so it changes in place.
# Version 8 adds `runner` to sessions, the id its runner gave the agent's session as METAFORM_SESSION, BASE-052; it may
# be empty, so version 5's code still reads and writes the tables, STORE-029, and a row written before it has none.
# Version 9 adds `recovery` to sessions, the process births and resources automatic recovery verifies, MAP-049, and
# `asked` to raised, what the person asked an intake agent for until its runner reads it; both may be empty, so
# version 5's code still reads and writes the tables. `nonce` is no longer written; a row written before 9 keeps it.
# Version 10 only adds tables: `catalog`, what each agent offered at its last session/new, per agent and version;
# `ticket_options`, a ticket's own model and effort; `spend`, the tokens each turn used; `attempts`, the supervisor's
# retries of a session that stopped without the person's stop.
# Version 11 counts spend in what is billed: each turn's tokens by kind, `tokens` the billable sum of them, and the cost
# each usage update added, never the session's running total; a cancelled ticket is the map's own outcome, so version
# 10's `outcomes` is gone; version 10 was never released. The new columns may be empty, so version 5's code still
# reads and writes the tables.
# Version 12 adds `prompts` and `mode` to ticket_options, a launch's own permissions; both may be empty, so version 5's
# code still reads and writes the tables.
# Version 13 adds `origin` to sessions, the machine and Metaform home whose runner started the session, `origin()`: a
# store copied into another home holds sessions that home never started, and nothing resumes them there. It may be
# empty, so version 5's code still reads and writes the tables; a row written before it has none and is no home's.
# Version 14 keeps spend in the project's store, `spending`, so removing a metaform never takes its spend out of the
# budgets. The chassis refuses to move a table between stores under one name, so the per-metaform `spend` stays
# declared, for version 5's code, which still reads and writes the tables, and for carry_spend() to move its rows.
# Version 16 only adds an index on lines by kind, then ticket: the agents key read every line of every thread to find
# the signals, and each session's state line in a read of its own, code.dispatcher.agent#3b. No row is rewritten, so
# version 5's code still reads and writes the tables.
# Version 17 keeps the conversations with agents in the project's store, apart from every map: `agent_sessions`,
# `session_lines` and `session_attempts`, so a clear, a restore, a new base or a switch of bases never takes them,
# PROJ-026. What stays beside each metaform's map is the map's own: a ticket's progress and the signals in `lines`, and
# the launches waiting in `raised`, whose tickets and intakes are the map's. As with spend, the per-metaform tables stay
# declared under their names, for version 5's code and for carry_conversations() to move their rows. A session row
# also says the metaform its runner is pinned to, `base`, the one active when it started, so it is stopped, resumed and
# read with its ticket there whichever metaform is made active since; a row with none is a conversation on no map or
# one written before.
# Version 18 only adds a table, `word_covers`: the work the person's word started, kept by their system agent's
# runner for its session, so a runner restarted or a session resumed carries that work on without asking the person
# again. Version 5's code still reads and writes the tables.
SESSION = (Column('session_id', required=True), Column('work_id', required=True), Column('agent', required=True),
           Column('state', required=True), Column('nonce'), Column('pid', 'int'), Column('port', 'int'),
           Column('token'), Column('how'), Column('started', required=True), Column('seq', 'int', required=True),
           Column('runner'), Column('recovery', 'json'), Column('origin'), Column('base'), Column('ended', default=''))
LINE = (Column('session_id', required=True), Column('name', required=True), Column('work_id', required=True),
        Column('kind', required=True), Column('text', required=True), Column('seq', 'int', required=True))
ATTEMPT = (Column('work_id', required=True), Column('session_id', required=True),
           Column('retries', 'int', required=True), Column('next_at', 'real', required=True),
           Column('how'), Column('handed', 'bool', default=False), Column('seq', 'int', required=True))
SPEND = (Column('session_id', required=True), Column('seq', 'int', required=True),
         Column('work_id', required=True), Column('run', required=True), Column('day', required=True),
         Column('tokens', 'int', required=True), Column('cost', 'real'), Column('currency'),
         Column('input', 'int'), Column('output', 'int'), Column('cache_read', 'int'),
         Column('cache_write', 'int'), Column('thought', 'int'), Column('metered', 'bool', default=True))
# Version 18 keeps the signals in the project's store too, `signals`, each saying the metaform it was raised on, so a
# permission request of an agent at work on a metaform no longer active still reaches the person after a switch, and
# nothing raised on an agent is lost when the map shown changes (UX review round 2, 2026-10-17, combined F4). The
# signals `lines` still holds, written by runners on older code, are carried into it by carry_conversations(); only a
# table is added, so version 5's code still reads and writes the tables.
TABLES = Tables(version=23, compatible_from=5, tables=(  # additive feature-commit verification evidence
    # The conversations with agents, the project's whatever its maps: each session and the lines of its thread.
    Table('agent_sessions', place='project', key=('session_id',), columns=SESSION,
          indexes=(Index(('work_id', 'seq')), Index(('seq',)), Index(('state', 'ended', 'seq')))),
    Table('session_lines', place='project', key=('session_id', 'name'), columns=LINE,
          indexes=(Index(('session_id', 'seq')), Index(('work_id', 'seq')), Index(('kind', 'work_id', 'seq')),
                   Index(('session_id', 'kind', 'seq')))),
    # What the agents and the modules raise for the person, the project's whatever map is shown: one line per signal,
    # its text the signal with the metaform it was raised on, `base`, signals.py.
    Table('signals', place='project', key=('session_id', 'name'), columns=LINE,
          indexes=(Index(('kind', 'work_id', 'seq')),)),
    # Sessions and their lines as versions before 17 kept them, beside each metaform's map; carry_conversations()
    # moves their rows into the two above. `lines` still keeps what is the map's: a ticket's progress, progress.py,
    # and the signals raised on tickets and sessions, signals.py.
    Table('sessions', key=('session_id',), columns=SESSION, indexes=(Index(('work_id', 'seq')), Index(('seq',)))),
    Table('lines', key=('session_id', 'name'), columns=LINE,
          on_remove=(('work', 'work_id', 'delete'),),
          indexes=(Index(('session_id', 'seq')), Index(('work_id', 'seq')), Index(('kind', 'work_id', 'seq')))),
    Table('merges', place='project', key=('work_id',),
          columns=(Column('work_id', required=True), Column('branch', required=True), Column('worktree', required=True),
                   Column('state', required=True), Column('reason'), Column('ready', 'real', required=True),
                   Column('deadline', 'real', required=True), Column('seq', 'int', required=True), Column('head'),
                   Column('evidence', 'json')),
          indexes=(Index(('state',)),)),
    Table('activations', place='project', key=('work_id',),
          columns=(Column('work_id', required=True), Column('value', 'json', required=True))),
    # An issue waiting for its node, oldest first, or, with `started`, its sentinel launched before its
    # session is made, VIEW-045.
    Table('raised', key=('work_id',),
          columns=(Column('work_id', required=True), Column('node', required=True), Column('agent', required=True),
                   Column('started', 'real'), Column('seq', 'int', required=True), Column('asked')),
          indexes=(Index(('seq',)),)),
    # A work claim, LAYER-029: the part of the map a chosen proposal reserves while its tickets are built, the
    # addresses of the elements it touches as a JSON list, and the tickets it covers in claim_work.
    Table('claims', key=('claim_id',),
          columns=(Column('claim_id', required=True), Column('name', required=True), Column('nodes', required=True),
                   Column('issue'), Column('seq', 'int', required=True)),
          indexes=(Index(('seq',)),)),
    Table('claim_work', key=('work_id',),
          columns=(Column('work_id', required=True), Column('claim_id', required=True)),
          indexes=(Index(('claim_id',)),)),
    # A sentinel's proposals for the issue it was raised on, as a JSON list, for the page to present, VIEW-045.
    Table('proposals', key=('issue',),
          columns=(Column('issue', required=True), Column('text', required=True), Column('seq', 'int', required=True)),
          indexes=(Index(('seq',)),)),
    # What an agent offered the last time a session of it was made, by agent and the version its initialize answer
    # named: its settings as the page shows them (config options and modes), its auth methods and its extensions. It
    # is the project's, since every metaform of the project starts the same agents.
    Table('catalog', place='project', key=('agent', 'version'),
          columns=(Column('agent', required=True), Column('version', required=True), Column('name'),
                   Column('settings', 'json'), Column('auth', 'json'), Column('extensions', 'json'),
                   Column('seen', required=True), Column('seq', 'int', required=True)),
          indexes=(Index(('agent', 'seq')),)),
    # A ticket's own choices for the agent that works it, applied over dispatch_<agent>_<option>: model and effort, the
    # ACP categories `model` and `thought_level`; and the permissions of its latest launch, `prompts` over
    # dispatch_prompts and the harness's own `mode`, written by each start, so they last for that launch and its
    # retries and the next start sets them again or leaves them to the project's settings.
    Table('ticket_options', key=('work_id',),
          columns=(Column('work_id', required=True), Column('model'), Column('effort'), Column('prompts'),
                   Column('mode'), Column('seq', 'int', required=True))),
    # What a session spent, one row per report: a turn's tokens as the agent reported them at its end, each kind
    # apart, `tokens` their billable sum (billable() says how), or the cost a usage update added since the one before,
    # in its currency. `metered` is false for a turn that ended with no usage at all, so a session whose agent
    # reports none reads as unmetered rather than as free. Summed per ticket, per run (a runner and the retries of
    # its sessions) and per UTC day against the budgets, M01. It is the project's, since a budget is the project's.
    Table('spending', place='project', key=('session_id', 'seq'), columns=SPEND,
          indexes=(Index(('work_id',)), Index(('run',)), Index(('day',)))),
    # Spend as versions before 14 kept it, beside each metaform's map; carry_spend() moves its rows into `spending`.
    Table('spend', key=('session_id', 'seq'), columns=SPEND,
          indexes=(Index(('work_id',)), Index(('run',)), Index(('day',)))),
    # The supervisor's retries of a session that stopped without the person's stop, and when the next may run: a
    # ticket's worker's, and the person's system agent's, which needs no map, so they are the project's.
    Table('session_attempts', place='project', key=('work_id',), columns=ATTEMPT),
    # Retries as versions before 16 kept them, beside each metaform's map; carry_conversations() moves their rows.
    Table('attempts', key=('work_id',), columns=ATTEMPT),
    # The work the person's word started, one row per word of a system agent's session: the word itself (`id`, `text`,
    # `at`), the tickets it covers and those of it the person stopped, `Session.covers` in runner.py. Written only by
    # that session's runner, and taken out when that work is done or the person stops the session.
    *HOLD_REVIEW_TABLES,
    Table('word_covers', place='project', key=('session_id', 'word_id'),
          columns=(Column('session_id', required=True), Column('word_id', required=True),
                   Column('word', 'json', required=True), Column('tickets', 'json', required=True),
                   Column('stopped', 'json'), Column('seq', 'int', required=True))),
))
PRIVATE = ('port', 'token', 'pid', 'nonce', 'recovery', 'origin')  # what only this module uses to reach a session
# Dispatch's own agents, each started by default at the version the ACP Registry lists for it, claude-acp, codex-acp
# and antigravity-acp, read 2026-10-21, so every start runs the same adapter until the person pins another, P013; `dispatch
# registry` names a newer one. Any other agent of the registry is added by the person and pinned, registry.py.
AGENTS = {
    'claude': ('Claude Code', 'npx -y @agentclientprotocol/claude-agent-acp@0.89.1'),
    'codex': ('Codex', 'npx -y @agentclientprotocol/codex-acp@2.2.2'),
    'antigravity': ('Google Antigravity', 'metaform dispatch adapter antigravity-acp@1.4.1'),
}
# The oldest Node.js every adapter above runs on, from their packages' engines, read 2026-10-15: claude-agent-acp
# 0.89.1 needs node >=22, codex-acp 2.2.2 names none. Antigravity uses Google's native binary.
NODE = '22'
# A setting that decides which agents run, how they start, what they are permitted, how they are watched or when
# their work lands is person_only: written by the person, never by an agent over MCP, CLI-011; Full Auto is
# also set by the person's own system agent on their word, `on_persons_word`. How long one wait blocks only paces the
# agent that calls it, so it is not. On by default, so a new install's board clears itself: the tickets go to agents,
# and the system agent is given a turn for what needs it, `board_changed` (the person's decision, 2026-10-18).
settings.boolean('dispatch_autostart', True, label='Full Auto', person_only=True, on_persons_word=True,
                 help='Start agents on tickets that have not been tried, and resume a worker\'s session that ended '
                      'without your stop, up to dispatch_retries; a ticket whose agent stopped with it open waits for '
                      'you. Turned on after Stop all, it resumes the work Stop all stopped; a ticket you stopped on '
                      'its own stays stopped.',
                 details='On, the default, your system agent is also given a turn when the board needs it: a ticket '
                         'filed with no task or repeating an open one, a ticket whose agent died, and a ticket an '
                         'agent finished, whose work may clear fault lights; one is started for it when none runs, '
                         'unless you stopped yours.',
                 category='automation', heading='Dispatch and capacity', essential=20)
settings.boolean('dispatch_pause_on_stop', True, label='Pause the project queue when I stop a worker',
                 person_only=True, category='automation', heading='User control',
                 help='Your stopped assignment stays stopped either way. Turn this off to let unrelated queued '
                      'work continue after your stop.')
settings.items('dispatch_registry_agents', [], scope='global', person_only=True, label='Agents from the ACP Registry',
               check=agent_registry.check_pins,
               help='Agents of the ACP Registry dispatch may start beside its own, each pinned as <id>@<version>, '
                    'such as goose@1.54.0.',
               details='metaform dispatch registry add=<id> pins the version the registry lists now, installs a '
                       'binary agent in the Metaform home after checking its sha256, and adds it here; the agent then '
                       'starts at that version until you pin another, whatever the registry lists later. Removing an '
                       'entry stops dispatch from starting it.')
settings.text('dispatch_registry_url', agent_registry.URL, scope='global', person_only=True, label='ACP Registry',
              help='Where the ACP Registry is read: its URL, or a file of the same form for a private mirror.')
# Hours a read of the ACP Registry is kept before dispatch registry reads it again; refresh=true reads it at once. A
# cache's age has one right answer, so settings cleanup 2026-10-15 made it fixed (it was dispatch_registry_hours).
REGISTRY_HOURS = 24


def registry_pins() -> dict[str, str]:
    """The registry agents the person added, {id: pinned version}; the setting is global, so no folder decides it."""
    return agent_registry.parse_pins(settings.value('dispatch_registry_agents', Path.cwd()))


def agent_choices(ctx: Any = None) -> list[str]:
    """Every agent dispatch starts: its own, then the registry agents the person pinned."""
    del ctx
    return [*AGENTS, *(agent for agent in registry_pins() if agent not in AGENTS)]


def agent_label(agent: str) -> str:
    """An agent's name: its own for dispatch's agents, the registry entry's for one the person pinned."""
    if agent in AGENTS:
        return AGENTS[agent][0]
    version = registry_pins().get(agent)
    held = agent_registry.snapshot(agent, version) if version else None
    return str(cast(dict[str, Any], (held or {}).get('entry') or {}).get('name') or agent)


def start_command(ctx: Context, agent: str) -> str:
    """The command that starts an agent: its dispatch_<agent> setting, or a registry agent's pinned command."""
    if agent in AGENTS:
        return str(ctx.setting(f'dispatch_{agent}'))
    version = registry_pins().get(agent)
    if version is None:
        raise Stop(f'{agent} is not an agent dispatch starts: {", ".join(agent_choices())}.',
                   f'metaform dispatch registry add={agent}')
    return agent_registry.command(agent, version)


def start_environment(agent: str) -> dict[str, str]:
    """What a registry agent's pinned entry sets in its environment, such as its default model; none for dispatch's
    own agents."""
    version = None if agent in AGENTS else registry_pins().get(agent)
    return agent_registry.environment(agent, version) if version else {}


# Conversations and tickets with unknown areas use this default. Ticket areas select their specialist.
settings.choice('dispatch_agent', agent_choices, 'claude', person_only=True,
                help='The default agent: the one started when none is chosen, for a ticket with unknown area, a chat, '
                     'an issue or an intake.',
                details='A ticket uses its chosen agent, else Claude for frontend work or Codex for other known areas. The '
                        'person sets it here or from the page.',
                label='Default agent', category='agents', heading='Starting work', essential=10)

# Whether each agent working a ticket is told to take out the code its change makes obsolete: on by default, so a
# design that changes leaves no dead code beside the new (the person's decision, 2026-10-18).
settings.boolean('dispatch_remove_superseded', True, label='Agents remove superseded code', category='agents',
                 help='Tell each agent working a ticket to delete the code, tests and text its change replaces.',
                 details='On, the default: an agent working a ticket is sent dispatch\'s remove_superseded prompt in '
                         'its first turn. Off: nothing is said, and old code is removed only when a ticket asks.')
settings.choice('dispatch_recovery', ['manual', 'automatic'], 'automatic', label='Dead runner recovery', person_only=True,
                help='What happens to a ticket whose runner died: manual keeps it with its session, which the '
                     'supervisor resumes in place up to dispatch_retries while Full Auto is checked; automatic '
                     'returns it to To do once its processes are verified stopped.',
                details='Applies before Full Auto selection or with dispatch recover. Neither starts more agents than '
                        'dispatch_agents and dispatch_machine_agents allow: a resume waits for a free slot. Older '
                        'sessions or uncertain cleanup still require manual recovery. Session reads never change '
                        'ownership.',
                category='automation', heading='Dispatch and capacity')
# The most agents one project may run at once, the number of agent glyphs the page draws, VIEW-040: the page offered 17
# and the server took any number (UX review round 1, 2026-10-17, settings-govern-behavior F7), and one slot is a
# runner, the agent's adapter and its own Metaform MCP server, about half a gigabyte or more.
AGENTS_MOST = 17
settings.number('dispatch_agents', 5, min=1, max=AGENTS_MOST, person_only=True,
                help='How many ticket workers Full Auto may start in this project; a ticket you start runs whatever '
                     'the count.',
                details='Full Auto, the queue, worker retries, recovery and agents\' own forks start a worker only '
                        'while fewer than this many run. A ticket you start, or your system agent starts at your '
                        'word, runs whatever the count, within the day\'s budget, your stops and '
                        'dispatch_machine_agents, and counts toward the total Full Auto sees. Triage, conversations, '
                        'intake and temporary role creation use separate capacity.',
                label='Workers Full Auto may start', category='automation', heading='Dispatch and capacity', unit='workers',
                essential=30)
# The ceiling across every project of this Metaform home, UX review round 1, 2026-10-17 (dispatch-concurrency F4,
# runaway-and-load F2): each project's dispatch_agents counted only its own, so two projects ran twice the agents, and
# 46 agents locked the person's machine up on 2026-10-16. It is global, since the machine is one.
MACHINE_AGENTS_MOST = 64
settings.number('dispatch_machine_agents', 8, min=1, max=MACHINE_AGENTS_MOST, scope='global', person_only=True,
                help='Maximum simultaneous ticket workers across every project on this machine.',
                details='Counted at the one place every agent is started, with each project\'s dispatch_agents: a '
                        'start past either waits, said with what holds the slots. Raise it when the machine has room.',
                label='Max workers on this machine', category='automation', heading='Dispatch and capacity', unit='workers')
settings.number('dispatch_spin_calls', 40, min=1, person_only=True,
                help='Tool calls without a completed ticket step before raising a spinning signal.')
settings.number('dispatch_spin_minutes', 10, min=1, person_only=True,
                help='Minutes without a completed step before the next session event raises a spinning signal.')
settings.number('dispatch_repeat_failures', 3, min=2, person_only=True,
                help='Consecutive failures of the same tool input before raising a repeated-failure signal.')
settings.number('dispatch_rework_limit', 3, min=0, person_only=True, label='Rework limit',
                help='Consecutive worker attempts ending without a completed ticket step before automatic work pauses. '
                     '0 disables the limit.',
                details='Counts worker runners that send a prompt and end with the ticket open. Person stops and idle '
                        'resumes do not count. A completed step or ticket clears the streak. Explicit starts and '
                        'resumes remain available; dispatch.rework-limit announces the pause.')
# Each ticket saves its own feature commit. Candidate cleanup remains separate from completion.
settings.boolean('dispatch_worktrees', True, person_only=True,
                 help='Each ticket\'s agent works in its own git worktree. Save feature commits with either choice. '
                 'Full Auto integrates locally. Publishing requires an explicit request.')
settings.number('dispatch_abandoned_branch_days', 30, min=1, person_only=True, label='Abandoned branches kept',
                help='Days the branch of a ticket closed without merging is kept, its work committed, before it is '
                     'removed.',
                details='Checked with dispatch_worktrees on, before each autostart and with dispatch recover: such a '
                        'branch, with its worktree and the snapshot it began from, is removed once its last commit is '
                        'this old, and git\'s record of worktrees already gone is pruned. A branch whose merge waits '
                        'is never removed.')
settings.text('dispatch_test_command', '', person_only=True,
              help='The project\'s test command, run before saving a worktree feature commit and during explicit '
              'integration. Without a command, completion retains the worker\'s verification report.')
# How long one wait blocks paces only the agent that calls it, so it is given on that call and never stored: settings
# cleanup 2026-10-15, which found it a switch of wait alone and made it per_call rather than fixed, so a caller keeps
# its choice of a shorter wait.
settings.number('dispatch_wait_seconds', 50, min=1, per_call=True,
                help='The longest one dispatch wait blocks before it answers pending with the call to make next.',
                details='Kept below the tool timeout of the agent that calls it, about 60 s for Codex, so the agent '
                        'gets an answer rather than a timed-out call.')
settings.choice('dispatch_record_on_finish', ['off', 'when-missing', 'always'], 'when-missing', person_only=True,
                label='Record on finish',
                help='When a worker closes its ticket, give it one more turn to record what it learned at the '
                     'ticket\'s node: off, when-missing or always.',
                details='when-missing sends the turn only when the session wrote no memory join or observation at the '
                        'node; always sends it every time. The turn is the on_ticket_done prompt, and an empty one '
                        'sends nothing whatever the setting.')
settings.boolean('dispatch_resume_chats', True, person_only=True, label='Resume chats',
                 help='Call and Chat go on with your last conversation about the same thing, so the agent keeps its '
                      'memory of it; off starts a new conversation each time.',
                 details='A conversation is resumed in place with session/resume or session/load, as dispatch resume '
                         'does, when its agent is the one chosen and offers either; otherwise a new one starts. The '
                         'checkbox beside Call in the chat dock sets it too.')
# The person's system agent kept running, VIEW-045: the companion that is always there to talk to, and their mascot's
# mind while they have one. Off by default: a running agent holds a login and a process the person did not ask for.
settings.boolean('dispatch_stay_connected', False, person_only=True, label='Keep triage connected',
                 category='automation', heading='User control',
                 help='Keep your system agent running: it starts when the web GUI starts or a page opens the project, '
                      'and comes back in place, with its memory, when it ends without your stop.',
                 details='Each pass of the agent starter, as the web GUI starts, as a page opens the project and as '
                         'agents change, starts it when none runs, resuming your last conversation in place where its '
                         'agent can. One that ended without your stop is resumed after 30 seconds, doubled '
                         'each time, up to dispatch_retries, then waits for your Call; one whose agent can neither '
                         'resume nor load starts a new conversation, and you are told once. Stopping it yourself, as '
                         'Dismiss in the chat dock does, turns this off for the project until you turn it on again; '
                         'closing the chat never stops it. It is the one agent you can always summon, so it takes no '
                         'slot from the agents at work. The checkbox beside Call in the chat dock sets it too.')

settings.choice('dispatch_record_on_stop', ['off', 'when-missing', 'always'], 'off', person_only=True,
                label='Record on stop',
                help='When a worker stops with its ticket open, give it one more turn, once, to record what it learned '
                     'at the ticket\'s node: off, when-missing or always.',
                details='As dispatch_record_on_finish, with the on_stopped_open prompt: when-missing sends it only when '
                        'the session wrote nothing at the node. The stopped-open signal is raised when that turn ends, '
                        'and the session then waits for you as before. Off by default: the turn costs a turn of the '
                        'agent\'s at the moment it waits for you, and holds the signal back until it ends.')
settings.choice('dispatch_record_on_failure', ['off', 'when-missing', 'always'], 'off', person_only=True,
                label='Record on failure',
                help='When a worker\'s turn ends in an error and its agent still runs, give it one more turn, once, to '
                     'record what it learned at the ticket\'s node: off, when-missing or always.',
                details='The on_failure prompt. An agent whose process has ended cannot take it, so nothing is sent then.')
settings.number('dispatch_silence_seconds', 300, min=1, person_only=True, label='Silent turn',
                help='Seconds a turn may pass with no word from the agent before a silent signal is raised.',
                details='The clock runs only while a turn is in flight, starts again on every update the agent sends, '
                        'so a turn silent twice is signalled twice, and stops while a permission request or a '
                        'question waits for you. The signal names the interrupt call.')
settings.number('dispatch_retries', 2, min=0, person_only=True, label='Retries',
                category='automation', heading='Recovery',
                help='How many times autostart resumes a ticket\'s session that stopped without your stop, including '
                     'sessions whose runner died, as after a crash, before handing it to you.',
                details='A retry resumes the same ACP session with session/resume or session/load, so the agent keeps '
                        'its own memory of the work; it waits 30 seconds, doubled each time, and for a free agent '
                        'slot, oldest first, so a crash never brings every agent back at once. A session you '
                        'stopped, or one whose agent can neither resume nor load, is never retried. 0 retries none.')
# Seconds before the first retry of a session that stopped without the person's stop; each later retry waits twice as
# long. A backoff base has one right answer, so settings cleanup 2026-10-15 made it fixed (dispatch_retry_seconds).
RETRY_SECONDS = 30
# What the runner offers the agent as its ACP client, P019: files and terminals of its own, so every file an agent
# reads or writes and every command it runs passes through Metaform, confined to the session's folder, placed on the
# map and kept in the thread. ACP lets an agent use them only when the client advertises them, protocol/file-system
# and protocol/terminals; an agent that does not still works in its folder on its own.
settings.boolean('dispatch_client_files', True, person_only=True, label='Files through Metaform',
                 help='Offer agents ACP\'s file reads and writes, confined to the session\'s folder; off, they read '
                      'and write on their own.',
                 details='A read or write outside the folder the agent works in, its worktree when it has one, is '
                         'refused and said in its thread; a write into a part of the map another ticket\'s claim '
                         'reserves is refused too. Each file is placed on the map through the sources layer and kept '
                         'in the session\'s state. Applies to the sessions started after the change.')
settings.boolean('dispatch_client_terminal', True, person_only=True, label='Terminals through Metaform',
                 help='Offer agents ACP\'s terminals, run in the session\'s folder with their output kept in its '
                      'thread; off, they run commands on their own.',
                 details='Each terminal runs in a process group of its own in the session\'s folder or below it, and '
                         'ends with the session. Applies to the sessions started after the change.')
# The intake's own guards, M04: an intake agent records what it examines as it goes, and works from the AUE itself,
# never from conclusions an earlier agent drew.
settings.number('dispatch_intake_first_record', 180, min=0, person_only=True, label='Intake first record',
                help='Seconds an intake agent may work before its first Metaform call; past it, it is steered once '
                     'to record what it has examined. 0 never steers.',
                details='The clock starts with its first turn. Until its first record the session reads as waiting '
                        'for first record, on the page and in dispatch sessions, and how long the first call and the '
                        'first record took is kept in its state. The steer is the intake_first_record prompt.')
# What each agent does well, one setting for each agent dispatch starts, dispatch_<agent>_strengths, so setting one
# never wipes another's, settings cleanup 2026-10-15 (it was the one list dispatch_agent_strengths, P199's rule). A
# registry agent the person pins later has its own once the process starts again.
# What each agent does well, its models and its thinking levels, as the default of dispatch_<agent>_strengths: Jev reads
# it when it chooses the agent, model and thinking level for a ticket. From the research the person delivered on
# 2026-10-20, kept whole in docs/reference/choosing-agents-models-effort.md.
STRENGTHS = {
    'claude': 'Front-end, GUI and page work; document-heavy and long-context work, nuanced writing, and complex '
              'multi-file repository coding, done carefully and structured. Models: Opus for the hardest knowledge work '
              'and coding; Fable for demanding agentic, multi-step work; Sonnet or Haiku for everyday speed at lower '
              'cost. Thinking level: low for quick syntax fixes, boilerplate and direct lookups; medium for everyday tasks '
              'and familiar refactoring; high or max for multi-file design, hard debugging and long-horizon planning.',
    'codex': 'Back-end, system and data work, exact code changes, rapid prototyping, and broad flexible workflows. '
             'Models: GPT-6 Astra or GPT-5.2 Thinking for the most demanding multi-step reasoning, architecture and hard '
             'coding; GPT-6.1 Sol as the balanced daily driver; GPT-6 Luna for high-volume, cost-sensitive automated '
             'tasks; lighter variants for quick turns. Thinking level: low for pattern matching, formatting and minor '
             'adjustments; medium for everyday bugs, clear features and routine refactors; high or max for deep '
             'algorithmic complexity, multi-file codebases and hard-to-reproduce bugs.',
    'antigravity': 'multi-step reasoning, multi-file editing and tool calling'}


def strengths_key(agent: str) -> str:
    return f'dispatch_{agent}_strengths'


for _agent in agent_choices():
    settings.text(strengths_key(_agent), STRENGTHS.get(_agent, ''), person_only=True,
                  label=f'What {AGENTS[_agent][0] if _agent in AGENTS else _agent} does well',
                  help=f'What {_agent} does well, its models and its thinking levels; read when a ticket\'s agent, '
                       'model and thinking level are chosen at assignment, by Jev or by the Facilitator.',
                  details='Your own account of the agent, given to the choice beside the advertised models and levels. '
                          'Your choice on the ticket always wins over the choice made for it. Empty, the choice is '
                          'told only the agent\'s name and what it advertises.')


def _withheld_choices(ctx: Context) -> list[str]:
    """What an intake's server can leave out: each module, its reading tools, and each of its tools by name."""
    from metaform.module import installed
    found: list[str] = []
    for module in installed():
        found += [module.id, f'{module.id}:read', *(f'{module.id}_{verb.name}' for verb in module.verbs)]
    return found


settings.items('dispatch_intake_withheld', ['memory', 'map:read'], person_only=True, label='Withheld from the intake',
               choices=_withheld_choices,
               help='The tools an intake agent\'s Metaform server leaves out, so it maps the AUE from its source and '
                    'not from what earlier agents concluded.',
               details='Each entry is a module (memory), a module\'s reading tools (map:read) or one tool (map_node). '
                       'A call that reaches for them anyway, through the command line or by reading a report, review, '
                       'log or notes file, raises the intake-conclusions signal at the session. Empty withholds '
                       'nothing.')
# The spend budgets, M01, measured as what is billed rather than what is read: tokens are a turn's input, output and
# cache writes, with cache reads at a tenth, since an agentic turn rereads its whole context on every model call and a
# raw total would count it dozens of times; cost is what the agent itself reports, the only measure that knows the
# price. Each is off at 0 until the person sets it: the numbers are the person's to choose.
settings.number('dispatch_budget_ticket', 0, min=0, person_only=True, label='Tokens per ticket',
                help='Billable tokens the agents may spend on one ticket; 0 sets no limit.',
                details='Billable tokens are an estimate from what each agent reports at the end of each turn: input, '
                        'output and cache writes, with cache reads counted at a tenth, summed over every session of '
                        'the ticket; no provider bills exactly so, and cost, where the agent reports it, is exact. Past '
                        'it, nothing starts or retries on the ticket and its agent gets no further turn of '
                        'Metaform\'s own; a budget signal says so, and your own message still reaches it. An agent '
                        'that reports no usage is shown as unmetered by dispatch spend.',
                category='budgets', heading='Tokens', unit='tokens')
settings.number('dispatch_budget_run', 0, min=0, person_only=True, label='Tokens per run',
                help='Billable tokens one run may spend over the tickets it works in turn; 0 sets no limit.',
                details='A run is one `dispatch run`, the ticket it was started on and the tickets of the same agent '
                        'glyph it goes on to, with every retry the supervisor makes of its sessions. Past it, the '
                        'runner takes no further ticket.',
                category='budgets', heading='Tokens', unit='tokens')
settings.number('dispatch_budget_day', 0, min=0, person_only=True, label='Tokens per day',
                help='Billable tokens every agent of the project may spend in one UTC day; 0 sets no limit.',
                details='Checked where every agent is started, whatever starts it: a worker, a retry, a chat, an '
                        'issue, an intake or a merge preparation; past it, a budget signal waits for you, and nothing '
                        'starts until the next day or a higher budget. Your own message still reaches an agent '
                        'already running.',
                category='budgets', heading='Tokens', unit='tokens')
def unheld_by_cost(value: Any, folder: Path) -> list[str] | None:
    """The notice a cost budget gives as it is set: an agent that reports no cost is not held by it, so the person
    learns it where they set the limit, not in dispatch spend. UX review round 1, 2026-10-17, settings-govern-behavior
    F6."""
    if not value:
        return None
    return [('Codex reports no cost, so a spending limit does not hold Codex agents; Tokens per day '
             '(dispatch_budget_day) bounds every agent.')]


settings.number('dispatch_budget_cost_ticket', 0, min=0, person_only=True, label='Spending limit per ticket',
                check=unheld_by_cost,
                help='Hundredths of the currency the agent reports (cents of USD) one ticket may cost; 0 sets no '
                     'limit.',
                details='Cost is what the agent reports in its usage updates, ACP\'s session usage: Claude Code '
                        'reports it as each turn ends, Codex not at all, which dispatch spend says. A cost budget is '
                        'held against each currency on its own, and acts when a turn ends.',
                category='budgets', heading='Spending', unit='cents')
settings.number('dispatch_budget_cost_day', 0, min=0, person_only=True, label='Daily spending limit',
                check=unheld_by_cost,
                help='Hundredths of the currency the agent reports (cents of USD) the project\'s agents may cost in '
                     'one UTC day; 0 sets no limit.',
                category='budgets', heading='Spending', unit='cents', essential=40)
settings.choice('dispatch_budget_action', ['signal', 'interrupt'], 'signal', person_only=True,
                label='When a budget is reached',
                help='signal raises the budget signal and lets the turn in flight finish; interrupt also cancels it.',
                details='Either way nothing more starts or retries past the budget. Budgets are checked at each '
                        'turn\'s end, when the agents report what a turn used, and the token budgets also during a '
                        'turn, against an estimate from the context the agent reports in use after each model call; '
                        'so interrupt can stop a runaway turn part way on tokens, and on cost only once it ends.',
                category='budgets', heading='Spending')

REPLY_LIMIT = 30.0  # the one wait for a running session to answer `message`, `stop` or a change
# How long a consent card waits for the person before the call it asks for is answered cancel: a time limit on one
# request, as an MCP form's sealed state has, never a clock that looks for a change.
CONSENT_WAIT = 600.0
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000

for _agent, (_name, _command) in AGENTS.items():
    settings.text(f'dispatch_{_agent}', _command, person_only=True,
                  help=f'The command that starts {_name} as an ACP agent.',
                  details=f'metaform dispatch start <work id> {_agent} runs it in the project folder. It runs your own '
                          f'installed {_name} under your own login; Metaform never reads or stores credentials.')


# The categories ACP reserves for a session config option, session-config-options#option-categories: an option of
# one is named by it, so a choice holds across agent versions that rename the option; any other by its own id.
CATEGORIES = ('mode', 'model', 'model_config', 'thought_level')


def catalog_rows(store: Store | None) -> dict[str, dict[str, Any]]:
    """What each agent offered at the latest session made of it, by agent: its version, settings, auth methods and
    extensions; none for an agent that has not run in this project yet."""
    if store is None:
        return {}
    try:
        with Store(store.project_id, module='dispatch').tables(write=False) as tx:
            rows = [dict(row) for row in tx.rows('catalog', by=('agent', 'seq'), limit=0).results]
    except StoreError:
        return {}
    return {row['agent']: row for row in rows}  # in seq order, so the latest of each agent is kept


def option_key(setting: dict[str, Any]) -> str:
    """How dispatch's settings name one of an agent's options: by its ACP category when it has a reserved one,
    or else by its id."""
    category = setting.get('category')
    return str(category) if category in CATEGORIES else str(setting.get('id'))


def option_values(setting: dict[str, Any]) -> list[str]:
    if setting.get('type') == 'boolean':
        return ['true', 'false']
    return [str(choice.get('value')) for choice in cast(list[dict[str, Any]], setting.get('options') or [])]


# A versioned id ending in its family's word, as Codex names its models: gpt-6.1-sol is version 6.1 of sol.
VERSIONED = re.compile(r'-(\d+(?:\.\d+)*)-([a-z]+)$')


def short_names(setting: dict[str, Any]) -> dict[str, str]:
    """Each short name a person writes for one of an agent's choices and the value it means now, in the agent's order:
    a one-word value is the agent's own alias, as Claude's opus is, and means itself; the word that ends versioned ids
    names the newest of them, as sol names gpt-6.1-sol until gpt-6.2-sol is offered. Read from the agent's current
    choices each time, so a new release is picked up with no change here. Only a model has them."""
    if option_key(setting) != 'model':
        return {}
    values = [value for value in option_values(setting) if value != AGENT_DEFAULT]
    found = {value: value for value in values if value.isalpha() and value.islower()}
    newest: dict[str, tuple[int, ...]] = {}
    for value in values:
        if (versioned := VERSIONED.search(value)) and versioned[2] not in found.keys() - newest.keys():
            version = tuple(int(part) for part in versioned[1].split('.'))
            if versioned[2] not in newest or version > newest[versioned[2]]:
                found[versioned[2]], newest[versioned[2]] = value, version
    return found


def resolve_choice(setting: dict[str, Any], given: str) -> str | None:
    """The value a person's word means among an agent's choices: the value itself, a short name, or the choice's own
    name, such as Opus 5.5; None when it means none of them."""
    text = given.strip()
    choices = cast(list[dict[str, Any]], setting.get('options') or [])
    if any(str(choice.get('value')) == text for choice in choices):
        return text
    folded = text.casefold()
    shorts = {name.casefold(): value for name, value in short_names(setting).items()}
    if folded in shorts:
        return shorts[folded]
    return next((str(choice.get('value')) for choice in choices if str(choice.get('name') or '').casefold() == folded),
                None)


def unknown_choice(agent: str, setting: dict[str, Any], given: str) -> str:
    """Why a word means none of an agent's choices: what it offers, short names first, and the nearest valid one."""
    shorts = short_names(setting)
    known = [*shorts, *(value for value in option_values(setting) if value not in shorts)]
    text = given.strip()
    nearest = difflib.get_close_matches(text, known, n=1, cutoff=0.3) or \
        [value for value in known if text.casefold() in value.casefold()][:1]
    families = [short for short, value in shorts.items() if short != value]
    return (f'{agent_label(agent)} offers {str(setting.get("name") or option_key(setting)).lower()} '
            f'{", ".join(known) or "none"}, not {text}'
            + (f'; {", ".join(families)} each mean the newest release of their family' if families else '')
            + (f'; nearest is {nearest[0]}' + (f', now {shorts[nearest[0]]}' if shorts.get(nearest[0], nearest[0])
                                               != nearest[0] else '') if nearest else '') + '.')


def model_for(store: Store | None, agent: str, given: str) -> str | None:
    """The exact model a person's word means for one of the agents now, as `dispatch.models` offers it to the
    roundtables module: a short name such as sol is its family's newest release, a value or the model's own name is
    itself. None when the agent has not run in this project, so nothing can be checked; a word that means none of its
    models is refused with what it offers and the nearest one."""
    offered = offered_option(store, agent, 'model')
    if offered is None:
        return None
    found = resolve_choice(offered, given)
    if found is None:
        raise Stop(unknown_choice(agent, offered, given), f'metaform dispatch options agent={agent}')
    return found


def picker_entries(setting: dict[str, Any]) -> list[dict[str, Any]]:
    """One of an agent's selects as every picker lists it: Default first with what it resolves to, then each short
    name with what it means now, then every exact value under Specific version, each by its own name. `value` is what
    is stored: a short name, so a stored choice follows the family's newest release."""
    choices = cast(list[dict[str, Any]], setting.get('options') or [])
    named = {str(choice.get('value')): str(choice.get('name') or choice.get('value')) for choice in choices}
    own = next((choice for choice in choices if str(choice.get('value')) == AGENT_DEFAULT), None)
    current = named.get(str(setting.get('current')))
    if own is not None:  # the agent's own default, by its name and what it says it is, as Default (recommended)
        name, said = str(own.get('name') or 'Default'), str(own.get('description') or '')
        resolved = said if name.casefold().startswith('default') else name
        label = name if name.casefold().startswith('default') else 'Default'
    else:
        label, resolved = 'Default', current or ''
    entries = [{'value': AGENT_DEFAULT, 'label': f'{label} — {resolved}' if resolved else label, 'group': None,
                'description': None}]
    shorts = short_names(setting)
    for short, value in shorts.items():
        resolved = named.get(value, value) + (f' ({value})' if value != short and named.get(value) != value else '')
        entries.append({'value': short, 'label': f'{short} — {resolved}', 'group': None,
                        'description': next((choice.get('description') for choice in choices
                                             if str(choice.get('value')) == value), None)})
    for choice in choices:
        value = str(choice.get('value'))
        if value != AGENT_DEFAULT and value not in shorts:
            pinned = bool(shorts)  # beside short names, an exact value pins one version
            entries.append({'value': value, 'label': f'{named[value]} ({value})' if pinned and named[value] != value
                            else named[value], 'group': 'Specific version' if pinned else None,
                            'description': choice.get('description')})
    return entries


# Each agent's own default for one of its options is a setting of its own, dispatch_<agent>_<name>, so setting one
# never touches another, P199, Rich 2026-10-14: (name, label, the option's ACP category, or its id when it has none).
# Every agent has the four categories; an option with no category is a setting only where it is named here.
AGENT_OPTIONS = (('mode', 'Mode', 'mode'), ('model', 'Model', 'model'), ('effort', 'Effort', 'thought_level'),
                 ('fast', 'Fast mode', 'model_config'))
OWN_OPTIONS = {'claude': (('agent', 'Agent', 'agent'),),
               'codex': (('collaboration_mode', 'Collaboration mode', 'collaboration_mode'),)}
AGENT_DEFAULT = 'default'  # the value of each that sends nothing, leaving the agent's own


def option_settings(agent: str) -> list[tuple[str, str, str]]:
    """The settings that hold an agent's options: (setting key, label, the option's category or id)."""
    return [(f'dispatch_{agent}_{name}', label, key) for name, label, key in (*AGENT_OPTIONS, *OWN_OPTIONS.get(agent, ()))]


def offered_option(store: Store | None, agent: str, key: str) -> dict[str, Any] | None:
    """The option an agent offered at its last session here under a category or id, or None."""
    row = catalog_rows(store).get(agent)
    return next((one for one in cast(list[dict[str, Any]], (row or {}).get('settings') or [])
                 if option_key(one) == key), None)


def option_choices(agent: str, key: str) -> Callable[[Context], list[str]]:
    """A setting's choices: default, then each short name and each value the agent offered for the option at its last
    session here, as its pickers list them; only default until it has run once, or `dispatch options agent=<agent>
    prime=true` has asked it."""
    def choices(ctx: Context) -> list[str]:
        offered = offered_option(ctx.store, agent, key)
        return [one['value'] for one in picker_entries(offered)] if offered else [AGENT_DEFAULT]
    return choices


def option_words(agent: str, key: str) -> Callable[[Context], dict[str, str]]:
    """Each value in the agent's own words, its name and description as it offered them."""
    def words(ctx: Context) -> dict[str, str]:
        offered = offered_option(ctx.store, agent, key) or {}
        said = {AGENT_DEFAULT: f'Leave it to {agent_label(agent)}: Metaform sends nothing for it.'}
        described: dict[str, str] = {}
        for choice in cast(list[dict[str, Any]], offered.get('options') or []):
            if (value := str(choice.get('value'))) != AGENT_DEFAULT:
                said[value] = ': '.join(str(part) for part in (choice.get('name'), choice.get('description')) if part)
                described[value] = str(choice.get('description') or '')
        for short, value in short_names(offered).items():
            if short != value:
                said[short] = f'The newest {short}, now {value}; a newer release is used once {agent_label(agent)} ' \
                              f'offers it. {described.get(value, "")}'.strip()
        return said
    return words


def option_names(agent: str, key: str) -> Callable[[Context], dict[str, str]]:
    """Each choice by the name its pickers show, `picker_entries`."""
    def names(ctx: Context) -> dict[str, str]:
        offered = offered_option(ctx.store, agent, key)
        return {one['value']: one['label'] for one in picker_entries(offered)} if offered else {}
    return names


def option_groups(agent: str, key: str) -> Callable[[Context], dict[str, str]]:
    """The heading each choice sits under in its pickers, Specific version for an exact value beside short names."""
    def groups(ctx: Context) -> dict[str, str]:
        offered = offered_option(ctx.store, agent, key)
        return {one['value']: one['group'] for one in picker_entries(offered) if one['group']} if offered else {}
    return groups


# A value that lets the agent act without asking, named so by the agents that offer one, as bypassPermissions, yolo or
# full access are: choosing it as the agent's default is confirmed on every surface, as the page's session bar confirms
# it for one session, VIEW-039.
SKIPS_PROMPTS = re.compile(r'bypass|yolo|full[-_ ]?access|danger|skip[-_ ]?perm|no[-_ ]?approv|never[-_ ]?ask|'
                           r'without[-_ ]?ask', re.IGNORECASE)


def option_risky(agent: str, key: str) -> Callable[[Context], list[str]]:
    """The values the agent offered for the option that skip its own permission prompts."""
    def risky(ctx: Context) -> list[str]:
        offered = offered_option(ctx.store, agent, key) or {}
        return [str(choice.get('value')) for choice in cast(list[dict[str, Any]], offered.get('options') or [])
                if SKIPS_PROMPTS.search(f'{choice.get("value")} {choice.get("name")}')]
    return risky


def chosen_options(ctx: Context, agent: str) -> dict[str, str]:
    """An agent's options as its settings give them, by category or id; one left at default is left out."""
    found: dict[str, str] = {}
    for key, _, option in option_settings(agent):
        value = ctx.setting(key) if key in settings.SCHEMA else None
        if value and value != AGENT_DEFAULT:
            found[option] = str(value)
    return found


for _agent, (_name, _command) in AGENTS.items():
    for _key, _label, _option in option_settings(_agent):
        settings.choice(_key, option_choices(_agent, _option), AGENT_DEFAULT, person_only=True, label=_label,
                        section=f'Agent options/{_name}', choice_help=option_words(_agent, _option),
                        choice_names=option_names(_agent, _option), choice_groups=option_groups(_agent, _option),
                        risky=option_risky(_agent, _option),
                        choices_from=f'metaform dispatch options agent={_agent} prime=true',
                        help=f'{_name}\'s {_label.lower()} for every session it starts here: a value it offers, '
                             + ('a short name such as opus or sol, which means the newest release of its family, '
                                if _option == 'model' else '') + f'or default to leave it to {_name}.',
                        details=f'The choices are what {_name} offered at its last session in this project; until it '
                                f'has run once there is only default: start it, or run dispatch options agent={_agent} '
                                'prime=true, which starts it, reads its options and closes it without a prompt. Applied '
                                'to every session it starts, new, loaded or resumed. A ticket\'s own model and effort, '
                                'set with dispatch tune, go over these.',
                        category='agents')  # under Agents: a thinking level found nowhere else made no sense (2026-10-20)


def system_agent_choices(ctx: Any = None) -> list[str]:
    """An agent for one purpose: default, the default agent, or any agent dispatch starts."""
    return [AGENT_DEFAULT, *agent_choices(ctx)]


# An agent per purpose, the person's decision of 2026-10-20: setting the default agent for tickets changed who triaged
# for them too, which is not what they meant. Assignment orchestration chooses ordinary tickets' runtimes;
# these settings choose the agents for conversations and system work.
settings.choice('dispatch_system_agent', system_agent_choices, 'claude', person_only=True,
                help='The agent that is your system agent, the one you talk to in the chat and that triages for you: '
                     'Claude unless you choose another installed here, or default to follow the default agent. The '
                     'intake agent is chosen on the intake bar, else the default agent.',
                details='Kept apart from the default agent, so changing which agent works tickets never changes who '
                        'triages for you. The chat picker on the page chooses the agent of one conversation; this one '
                        'starts when none is chosen, and when Stay connected brings your system agent back.',
                label='System agent', category='agents', heading='Starting work', essential=11)
# The system healing itself: a ticket of kind or condition broken, filed by autoticket from a fault the system saw or
# marked by the person. Its agent thinks at the highest level its AI tool offers, under the person's own choice for the
# ticket or the agent, and no other ticket starts while one is being healed; healing tickets start first. A fault
# healed at a low thinking level, with other agents starting around it, made the system worse (2026-10-20).
HEALING_EFFORT = 'xhigh'
settings.choice('dispatch_healing_agent', system_agent_choices, AGENT_DEFAULT, person_only=True,
                help='The agent that heals a fault the system found in itself, a ticket of kind broken: one installed '
                     'here, or default to use the ticket\'s own agent, else the default agent.',
                details='A healing ticket starts before any other and alone: no other ticket starts while it is being '
                        'worked. The agent set on the ticket itself still wins.',
                label='Healing agent', category='agents', heading='Starting work', essential=12)
settings.text('dispatch_healing_effort', HEALING_EFFORT, person_only=True,
              help='The thinking level asked of the agent healing a fault of the system\'s own, as that agent names its '
                   'levels; empty leaves the agent\'s own default.',
              details='Applied under the thinking level set on the ticket itself and the agent\'s own effort setting, so '
                      'your choices for either still win. A level the agent does not offer is said once in its thread '
                      'and left.',
              label='Healing thinking level', category='agents', heading='Starting work', essential=13)


def system_agent(ctx: Context) -> str:
    """The agent the person's system agent runs on: dispatch_system_agent, else the default agent."""
    chosen = str(ctx.setting('dispatch_system_agent') or AGENT_DEFAULT)
    return chosen if chosen != AGENT_DEFAULT else str(ctx.setting('dispatch_agent'))


def migrate_agent_options(ctx: Context | None = None) -> list[str]:
    """Once per home, as dispatch starts: each stored dispatch_agent_options entry, `<agent>.<category or id>=<value>`,
    becomes the value of its own setting at the same scope, and the old setting is removed, Rich 2026-10-14. An entry
    with no setting to hold it is dropped and said. A marker in the home, listing what moved, keeps it from running
    again."""
    del ctx
    marker = home.home() / 'migrated-dispatch-agent-options'
    if marker.exists():
        return []
    said: list[str] = []
    held: dict[str, list[str]] = {}
    unread = False
    for scope in dict.fromkeys(['global', *(home.path_key(record.path) for record in home.projects())]):
        try:
            with home.settings_db(scope) as db:
                rows = db.execute("SELECT scope, value FROM settings WHERE owner='dispatch' AND "
                                  "key='dispatch_agent_options' ORDER BY scope, position").fetchall()
        except Exception as error:  # noqa: BLE001  a project that cannot be read is said and left for the next start
            said.append(f'{scope}: not read, {error}')
            unread = True
            continue
        for found_scope, raw in rows:
            held.setdefault(str(found_scope), []).append(str(json.loads(raw)))
    moved: dict[str, dict[str, str]] = {}
    for scope, entries in held.items():
        for entry in entries:
            named, _, value = entry.partition('=')
            agent, _, option = named.strip().partition('.')
            key = next((key for key, _, one in option_settings(agent) if one == option.strip()), None)
            if key is None or not value.strip():
                said.append(f'{scope}: {entry} has no setting to hold it and was dropped.')
                continue
            moved.setdefault(scope, {})[key] = value.strip()
    for scope in held:
        # A folder's list hid every entry of the lists above it, so what only those set is default here, as it was
        above = {key for over in held if over != scope and (over == 'global' or (scope != 'global'
                                                                                and Path(scope).is_relative_to(over)))
                 for key in moved.get(over, {})}
        for key, value in {**dict.fromkeys(above - set(moved.get(scope, {})), AGENT_DEFAULT),
                           **moved.get(scope, {})}.items():
            home.save(scope, 'dispatch', key, [value])
            said.append(f'{scope}: {key} = {value}')
        home.clear(scope, 'dispatch', 'dispatch_agent_options')
        home.set_glue(scope, 'dispatch', 'dispatch_agent_options', False)
    if not unread:  # the home is its owner's alone, so the marker is made 0600
        with os.fdopen(os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w', encoding='utf-8') as out:
            out.write('\n'.join(said) + '\n')
    return said



def started(ctx: Context | None = None) -> list[str]:
    """Dispatch's one-time carry of agent settings that changed shape."""
    from .migration import migrate_settings
    return [*migrate_settings(AGENTS['antigravity'][1]), *migrate_agent_options(ctx)]

# How an agent's interactive prompts are answered, as the administrator sets it, read at each request so a change
# reaches agents already running: approve-all answers each with its allow option; approve-reads answers a read or a
# search and asks for anything else; ask_all asks every one as a question at the ticket's node, BASE-052.
PROMPTS = ['approve-all', 'approve-reads', 'ask_all']
READS = ('read', 'search')  # the tool kinds of ACP that only read
settings.choice('dispatch_prompts', PROMPTS, 'ask_all', person_only=True, risky=('approve-all',),
                help='How an agent\'s permission prompts are answered: approve-all, approve-reads or ask_all.',
                choice_help={
                    'approve-all': 'Allow everything without asking: the agent runs commands, edits and deletes files '
                                   'on its own. Fastest; nothing stops a wrong or harmful action.',
                    'approve-reads': 'Allow reading and searching without asking; ask you before anything else. '
                                     'Reads cannot change files, but the agent can read any file it can reach.',
                    'ask_all': 'Ask you before every action, reads included. Safest; the agent waits on you at '
                               'each prompt.'},
                details='approve-all answers every prompt with its allow option; approve-reads answers a read or a '
                        'search and asks for anything else; ask_all asks every prompt as a question at the ticket\'s '
                        'node. It is read at each prompt, so a change reaches agents already running. A question the '
                        'agent asks you is not a prompt: dispatch_elicitation decides it.',
                label='Permission prompts', category='automation', heading='Permissions', essential=50)
# An agent's own question to the person, ACP's elicitation: Claude Code's AskUserQuestion, Codex's request for input,
# or an MCP server's form or sign-in page. Asked at the ticket's node and on the page, as a permission prompt is, or
# declined at once, the agent going on without the answer.
settings.choice('dispatch_elicitation', ['ask', 'decline'], 'ask', person_only=True, label='Agent questions',
                help='A question the sentinel or your system agent asks you, a form or a page to open: ask puts it to '
                     'you at the ticket\'s node and on the page; decline answers no at once. A worker never asks.',
                details='ACP\'s elicitation, advertised in both of its modes. A form\'s answer is checked against what '
                        'it asks for; a page to open, such as an MCP server\'s sign-in, is never opened by Metaform: '
                        'you open it, and answering accept is your consent. dispatch_prompts never answers a '
                        'question. Read at each question, so a change reaches agents already running.',
                category='automation', heading='Permissions')


def prompt(name: str, **fills: str) -> str:
    """The prompt `name` of this module's resources/prompts.xml, MCP-031, as the prompt store serves it as
    `dispatch:<name>`: the shipped text, or an edit saved in its place, STORE-044."""
    return prompt_files.served(resources.files(__name__), name, **fills)


def handoff_prompt(work_id: str, folder: Path) -> str:
    """The full worker's brief, read on demand only, with its line on recording what the agent learns only while the
    memory module is on the folder's surface, so an agent is never told to use a command it does not have, BASE-052."""
    memory = any(module.id == 'memory' for module in surface(folder))
    return prompt('handoff', work_id=work_id, record=f"  {prompt('record')}\n" if memory else '')


def memory_text(folder: Path, project: str | None, address: str | None) -> str:
    """The owner's memory prompt, CTX-026, filled with the project and the element at `address`, or in its unassigned
    form without one, CTX-027, as the memory module offers it while it is on the folder's surface; empty otherwise,
    so a folder with memory off is sent none, CTX-028."""
    if not project:
        return ''
    return '\n\n'.join(text for _, made in provided(folder, 'memory.prompt') if (text := made(project, address)))


def work_line(work_id: str, folder: Path, node: str) -> str:
    """What a hand-off adds to the node brief: work the ticket with the map_work tool, whose description says how,
    and, while the memory module is on the folder's surface, the owner's sentence on recording what is learned, with
    the node it is recorded at, so no agent is told to use a tool it does not have. The request to link entry-point
    files is not here: the runner adds work_link to a ticket worker's first prompt, CTX-060."""
    memory = any(module.id == 'memory' for module in surface(folder))
    if not memory or not node:
        return prompt('work', work_id=work_id, record='')
    named = node.replace(' and ', ' ') if node.startswith('receiver=') else f'node={node}'
    return prompt('work', work_id=work_id, record=prompt('work_record', node=node,
                                                         call=f'memory_create_entities {named}'))


# The mascot's body: the web module's verbs that move it and let it see, each the MCP tool web_<verb>.
MASCOT_VERBS = ('say', 'go', 'point', 'emote', 'look', 'see', 'turn', 'come')
# A conversation agent's place on the map: a body, its eyes, where the person looks, and coming up before their view.
EYES_VERBS = frozenset({'embody', 'look', 'see', 'viewing', 'capture', 'come'})


def eyes_line(folder: Path) -> str:
    """The one line that tells an agent the person talks with about something how it can be on the map with them,
    VIEW-005, while the web module on the folder's surface has every one of those tools; empty otherwise, so the
    agent is never told to use a tool it does not have."""
    web = next((module for module in surface(folder) if module.id == 'web'), None)
    if web is None or not EYES_VERBS <= {verb.name for verb in web.verbs}:
        return ''
    line = prompt('eyes')
    return f'  {line}' if line else ''


def mascot_line(folder: Path) -> str:
    """The one sentence that tells the person's system agent it speaks as their mascot, VIEW-005, while the person has
    chosen one, web_mascot, and the web module is on; empty otherwise. It says where the character's persona is
    written, for the agent to read when it needs it, and names the mascot's tools that are on the folder's surface, so
    the agent is never told to use a tool it does not have. Nothing more of the mascot is pushed."""
    try:
        chosen = settings.value('web_mascot', folder)
    except Exception:  # noqa: BLE001  the web module is off, and its settings with it: there is no mascot
        return ''
    web = next((module for module in surface(folder) if module.id == 'web'), None)
    if not chosen or chosen == 'none' or web is None:
        return ''
    offered = {verb.name for verb in web.verbs}
    tools = [f'web_{name}' for name in MASCOT_VERBS if name in offered]
    if not tools:
        return ''
    try:  # the web module as it is loaded, wherever it was found
        written: Any = Path(inspect.getfile(web.verbs[0].run)).parent / 'resources' / prompt_files.FILE
    except TypeError:
        written = resources.files('metaform.modules.web') / 'resources' / prompt_files.FILE
    line = prompt('mascot', character=str(chosen), persona=f'persona_{chosen} of {written}',
                  tools=', '.join(tools[:-1]) + (f' and {tools[-1]}' if len(tools) > 1 else tools[0]))
    return f'  {line}' if line else ''


def prompt_written(name: str) -> None:
    """Refuse a feature whose prompt is not written yet: the element ships empty until it is."""
    if not prompt(name):
        raise Stop(f'This needs its prompt written: {resources.files(__name__) / "resources" / "prompts.xml"} {name}',
                   'write the prompt, then try again')


def argv(command: str, system: str | None = None) -> list[str]:
    """A start command as the arguments to run, its first word found on PATH, so `npx` is `npx.cmd` on Windows."""
    windows = (system or os.name) == 'nt'
    parts = shlex.split(command, posix=not windows)
    if windows:
        parts = [part[1:-1] if len(part) > 1 and part[0] == part[-1] == '"' else part for part in parts]
    if not parts:
        raise Stop('The start command is empty.', 'metaform help dispatch')
    found = shutil.which(parts[0])
    return [found or parts[0], *parts[1:]]


def group_options(system: str | None = None) -> dict[str, Any]:
    """How a process starts in a process group of its own, so stopping it ends what it started too."""
    if (system or os.name) == 'nt':
        return {'creationflags': CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW}
    return {'start_new_session': True}


def end_group(pid: int, system: str | None = None) -> None:
    """End a process and every process it started: `npx` starts the agent as a grandchild. A process that leads no
    group of its own is ended alone: the group it is in is its starter's, perhaps the caller's own."""
    if (system or os.name) == 'nt':
        subprocess.run(['taskkill', '/T', '/F', '/PID', str(pid)], capture_output=True, check=False)
        return
    try:
        leads = os.getpgid(pid) == pid
    except ProcessLookupError:
        leads = True  # its leader is gone and the group it led can live on; no other group has its id
    except PermissionError:
        return
    try:
        if leads:
            os.killpg(pid, signal.SIGKILL)
        else:
            os.kill(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def command_line(pid: int) -> list[str]:
    """The words of a process's command line; none for a process that has ended or cannot be read."""
    try:
        if sys.platform == 'win32':
            return [word.strip('"') for word in (_windows_command_line(pid) or '').split()]
        if sys.platform.startswith('linux'):
            with open(f'/proc/{pid}/cmdline', 'rb') as found:
                return [os.fsdecode(word) for word in found.read().split(b'\0') if word]
        said = subprocess.run(['ps', '-ww', '-o', 'command=', '-p', str(pid)], capture_output=True, text=True,
                              check=False)
        return said.stdout.split() if said.returncode == 0 else []
    except (OSError, ValueError):
        return []


def _windows_command_line(pid: int) -> str | None:
    """A Windows process's command line through its process handle, ProcessCommandLineInformation, Windows 8.1 on."""
    from ctypes import wintypes

    class Text(ctypes.Structure):
        _fields_ = [('Length', wintypes.USHORT), ('MaximumLength', wintypes.USHORT), ('Buffer', ctypes.c_void_p)]

    # WinDLL is present only on Windows; its CDLL base carries the shared ctypes interface for type checking.
    kernel = cast(ctypes.CDLL, getattr(ctypes, 'WinDLL')('kernel32', use_last_error=True))  # noqa: B009 -- WinDLL exists only on Windows.
    ntdll = cast(ctypes.CDLL, getattr(ctypes, 'WinDLL')('ntdll'))  # noqa: B009 -- WinDLL exists only on Windows.
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetExitCodeProcess.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    ntdll.NtQueryInformationProcess.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.ULONG,
                                                ctypes.POINTER(wintypes.ULONG)]
    ntdll.NtQueryInformationProcess.restype = wintypes.LONG
    handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    try:
        code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value != 259:  # STILL_ACTIVE
            return None
        size = wintypes.ULONG(0)
        ntdll.NtQueryInformationProcess(handle, 60, None, 0, ctypes.byref(size))  # ProcessCommandLineInformation
        if not size.value:
            return None
        held = ctypes.create_string_buffer(size.value)
        if ntdll.NtQueryInformationProcess(handle, 60, held, size, ctypes.byref(size)) != 0:
            return None
        text = Text.from_buffer(held)
        return ctypes.wstring_at(text.Buffer, text.Length // 2) if text.Buffer else None
    finally:
        kernel.CloseHandle(handle)


SERVED = 'serve'  # what runner_of names a `dispatch serve` process by: it records an editor's sessions, BASE-062


def runner_of(pid: Any) -> str | None:
    """The work id a process runs as `dispatch run <work id>`, or SERVED for `dispatch serve`, which records the
    sessions an editor runs through it and answers for them on their control ports, BASE-062; none for a pid that is
    no runner, since a recorded pid can outlive its runner and be given to another process. A runner on a glyph goes
    on to the glyph's other tickets in the same process, so the work id is the one it started on."""
    if not isinstance(pid, int) or pid <= 0:
        return None
    words = command_line(pid)
    if any(words[at:at + 2] == ['dispatch', 'serve'] for at in range(len(words) - 1)):
        return SERVED
    return next((words[at + 2] for at in range(len(words) - 2) if words[at:at + 2] == ['dispatch', 'run']), None)


def agent_named(name: str) -> str:
    if name not in AGENTS and name not in registry_pins():
        raise Stop(f'{name} is not an agent dispatch starts: {", ".join(agent_choices())}.',
                   'metaform help dispatch start')
    return name


def pinned(store: Store) -> dict[str, str]:
    """The environment that pins a runner to the metaform `store` reads, the active one unless one is bound: every
    runner, its agent and that agent's MCP server stay on the metaform their ticket or conversation began in, whichever
    is made active since, so a switch of the map never takes a running agent's ticket from under it, BASE-052. None
    with no metaform yet: a conversation on no map follows the first one made."""
    bound = store.bound_base()
    return {BASE_VARIABLE: bound.id} if bound is not None else {}


def base_store(store: Store, row: dict[str, Any]) -> Store:
    """Dispatch's store on the metaform a session's runner is pinned to, its row's `base`, where its ticket is: the one
    given when that is it, or when the row names none, or one the project no longer holds."""
    base = row.get('base')
    bound = store.bound_base()
    if not base or bound is not None and bound.id == base or home.base_by_id(store.project_id, str(base)) is None:
        return own_store(store)
    return Store(store.project_id, base=str(base), module='dispatch')


def ticket(store: Store, work_id: str) -> WorkRecord:
    """Read the work record alone, without rebuilding the context of its node and linked nodes."""
    try:
        # A runner callback is a fresh request: validate once, then share it across this one read.
        with request_scope(fresh=True):
            found = store.work(ids=[work_id], limit=1).results
        if not found:
            raise StoreError(f'No work record has the id {work_id}.', 'metaform map work open=true')
        return found[0]
    except NewerStore:
        raise  # a runner tells a store its code is older than from any other refusal, STORE-029
    except StoreError as error:
        raise Stop(str(error), 'metaform map work open=true') from None


# An intake agent's session holds no ticket: its work id is this prefix and a token of its own, so the CLI and the
# page reach it as they reach any session, and nothing takes it for a ticket. Its row is the project's, as every
# session's is since version 17, so an intake into a new base, and that base once the person activates it, both reach
# it, VIEW-045 and BASE-039.
INTAKE = 'intake-'
# The person's conversations hang on a held ticket of the map, `anchor`; with no map yet, or none since a clear, they
# hang on this work id, which is never a ticket either, so the person always talks with their own agent and an intake
# is offered, never required first, VIEW-045.
CONVERSATION = 'conversation-'
# A helper the person's system agent starts with a brief, `helper`, holds no ticket either: its work id is this prefix
# and a token of its own, and its record is its session, its brief kept in the session's state and its work in its
# thread, read afterwards as any session's is.
HELPER = 'helper-'


def intake_id(work_id: Any) -> bool:
    return str(work_id).startswith(INTAKE)


def helper_id(work_id: Any) -> bool:
    return str(work_id).startswith(HELPER)


def helper_item(work_id: Any) -> str:
    """How a helper is named where a ticket would be named by its item: `helper` and the first of its token."""
    return 'helper ' + str(work_id)[len(HELPER):][:8]


def ticketless(work_id: Any) -> bool:
    """Whether a work id names no ticket by what it is: an intake's, a helper's or a conversation held on no map."""
    return intake_id(work_id) or helper_id(work_id) or str(work_id).startswith(CONVERSATION)


def held_ticket(store: Store, work_id: str) -> WorkRecord | None:
    """The ticket a session hangs on, or None: a work id that is no ticket, or one this map does not hold, as every
    ticket of a map cleared since the session began, PROJ-026."""
    if ticketless(work_id):
        return None
    try:
        return store.ticket(work_id).work
    except NewerStore:
        raise
    except StoreError:
        return None


def intake_store(store: Store, work_id: str) -> Store | None:
    """This module's store for an intake agent's session: the project holds every session, so it is the store given
    when the project holds that one, and None when it does not."""
    try:
        with own_store(store).tables(write=False) as tx:
            if tx.rows('agent_sessions', {'work_id': work_id}, limit=1).results:
                return own_store(store)
    except StoreError:
        pass
    return None


def named_session(store: Store, name: str) -> dict[str, Any]:
    """The latest session of the project with this name, the name dispatch gave it when it started, names.py: its
    row, for a verb that takes a name where it takes a session id. Refused when no session has the name."""
    from .names import latest
    found: dict[str, Any] | None = None
    with contextlib.suppress(StoreError), own_store(store).tables(write=False) as tx:
        found = latest(tx, name)
    if found is None:
        raise Stop(f'No agent session is called {name}.', 'metaform dispatch sessions thread=false')
    return found


def session_state(store: Store, session_id: str) -> dict[str, Any] | None:
    """A session's state as its runner last kept it: what the agent can do, its settings, commands, plan, usage, the
    folder it worked in and the parts of the map it touched; None for a session that kept none."""
    try:
        with own_store(store).tables(write=False) as tx:
            found = tx.rows('session_lines', {'session_id': session_id, 'name': 'state'}, limit=1).results
    except StoreError:
        return None
    if not found:
        return None
    try:
        value: Any = json.loads(str(found[0]['text']))
    except ValueError:
        return None
    return cast(dict[str, Any], value) if isinstance(value, dict) else None


def located(command: str) -> str | None:
    """Where a start command's first word is found on this system, by PATH and, on Windows, PATHEXT; None when it is
    not, or the command cannot be read."""
    try:
        return shutil.which(argv(command)[0])
    except (Stop, ValueError):
        return None


def found_command(ctx: Context, agent: str) -> str | None:
    """Where an agent's start command is found on this system; None when it is not, or a registry agent is not
    installed here."""
    try:
        return located(start_command(ctx, agent))
    except Stop:
        return None


def runnable(ctx: Context, agent: str) -> None:
    """Refuse an agent whose start command is not found, before anything is written."""
    if found_command(ctx, agent) is None:
        raise Stop(f'The start command of {agent} is not found on this system.',
                   f'metaform set --dispatch-{agent} "<command>"' if agent in AGENTS else
                   f'metaform dispatch registry add={agent}')


def origin() -> str:
    """The machine and Metaform home a runner started here records on its session, as `sessions.origin`."""
    return f'{socket.gethostname()}:{home.home().resolve()}'


def foreign(row: dict[str, Any]) -> bool:
    """Whether a session row is not this home's: started on another machine or by another home, such as the home a
    copied store came from, or recorded before sessions kept their origin. Nothing resumes it by itself here."""
    return row.get('origin') != origin()


def resuming_path(session_id: str) -> Path:
    """The file naming the runner last started to resume a session, written before its row says so."""
    return home.home() / 'run' / 'dispatch' / f'resuming-{hashlib.sha256(session_id.encode()).hexdigest()[:32]}'


def holder(store: Store, work_id: str, session_id: str, *, besides: int | None = None) -> int | None:
    """The pid of a live runner that holds a session or was started to resume it, whatever its parent is now: a runner
    outlives the server, page or command that started it, so it is found by its stored row and the file its start
    left, then its command line, never by who started it or a status reply. None when none does; `besides` is the
    asking runner's own pid."""
    try:
        with own_store(store).tables(write=False) as tx:
            stored = tx.rows('agent_sessions', {'session_id': session_id}, limit=1).results
    except StoreError:
        stored = []
    pids: list[Any] = [stored[0]['pid']] if stored and stored[0]['state'] == 'running' else []
    try:
        started = int(resuming_path(session_id).read_text(encoding='utf-8').strip())
    except (OSError, ValueError):
        started = None
    for pid in pids:
        if pid != besides and runner_of(pid) == work_id:
            return int(pid)
    if started is not None and started != besides and runner_of(started) == work_id \
            and f'resume={session_id}' in command_line(started):
        return started
    return None


def resume_spawn(store: Store, work_id: str, agent: str, extra: list[str], name: str, *,
                 besides: int | None = None, ctx: Context | None = None, asked: int | None = None,
                 auto: bool = False, subject: str | None = None) -> dict[str, Any]:
    """A runner that resumes a session in place, started only while no live runner holds it or is starting to resume
    it: the check and the start are one lock between processes, so two passes of the agent starter, two servers, or a
    Call while a server restarts never resume one ACP session twice. A held session is reused, `state` running.
    `besides` is a runner handing its own session over, `hand_over`, which still runs while it starts the next, so
    the gate does not count it. A start the gate refuses raises its Stop, and nothing is written."""
    session_id = next(word.partition('=')[2] for word in extra if word.startswith('resume='))
    marker = resuming_path(session_id)
    home.mkdir_private(marker.parent)
    with home.file_lock(marker.parent / 'resume.lock'):
        pid = holder(store, work_id, session_id, besides=besides)
        if pid is not None:
            return {'state': 'running', 'pid': pid}
        started = spawn(store, work_id, agent, extra, name, ctx=ctx, besides=besides, asked=asked, auto=auto,
                        subject=subject)
        if started.get('reused'):  # a runner about the same subject already starting: that one is the answer
            return started
        home.write_private(marker, str(started['pid']))
    return started


def holding(store: Store, work_id: str, rows: Sequence[dict[str, Any]]) -> tuple[dict[str, Any], int] | None:
    """The latest of a ticket's sessions, as session_status reads them, that a live runner holds or was started to
    resume whatever its status read says, with that runner's pid; None when none is. A row stamped by another home is
    passed over. Only a row read as ended for its runner's reply, or one a start file names, can be held, so the
    others cost no read."""
    for row in reversed(rows):
        session_id = str(row['session_id'])
        if row['state'] == 'running' or row.get('origin') and foreign(row) or \
                row.get('how') not in SILENT and not resuming_path(session_id).exists():
            continue
        # each row's own ticket: the system agent's sessions may hang on the held tickets of maps cleared since
        pid = holder(store, str(row.get('work_id') or work_id), session_id)
        if pid is not None:
            return row, pid
    return None


def silent(row: dict[str, Any], pid: Any) -> bool:
    """Whether the live runner `pid` that holds a session is the one its row says took it, read as ended because it
    does not answer: never resumed again, and ended only by the person's stop. One found by the file its start left is
    starting."""
    return pid == row.get('pid') and row.get('how') in SILENT


def held_session(row: dict[str, Any], pid: int) -> dict[str, Any]:
    """A session its live runner holds and does not answer, said with the runner's pid and the stop that ends it."""
    return {'state': 'held', 'work_id': row['work_id'], 'agent': row['agent'], 'session_id': row['session_id'],
            'pid': pid, 'reason': f'Its runner, process {pid}, is alive but does not answer.',
            'next': f'metaform dispatch stop {row["work_id"]} session={row["session_id"]}'}


HANDED = 'restarted on updated code'  # how a runner the store's layout outgrew ends; its session goes on in a new one


def handed_path(session_id: str) -> Path:
    """The file a runner handing its session over leaves for the runner that takes it: what it was given and could
    not record, `hand_over`."""
    return home.home() / 'run' / 'dispatch' / f'handed-{hashlib.sha256(session_id.encode()).hexdigest()[:32]}.json'


def hand_over(store: Store, work_id: str, agent: str, session_id: str, runner: str | None, pid: int,
              extra: list[str], carried: list[dict[str, Any]]) -> dict[str, Any]:
    """A runner whose code the store moved past, STORE-029, gives its session to a runner on the code on disk. Run
    in a new process with that code, after the old runner's agent has ended: the session's row ends as handed over,
    its ticket stays taken by the session, what the old runner was sent and could not record waits in
    `handed_path` for the next, and a runner resuming that same session starts. A late hand-over, once the row
    belongs to another runner, starts nothing."""
    held = own_store((intake_store(store, work_id) or store) if intake_id(work_id) else store)
    with held.tables() as tx:
        previous = tx.get('agent_sessions', {'session_id': session_id})
        if previous is None or previous['work_id'] != work_id or runner and previous.get('runner') != runner:
            return {'state': 'gone'}
        if previous['state'] == 'running':
            tx.update('agent_sessions', {'session_id': session_id}, {'state': 'ended', 'how': HANDED,
                                                                   'ended': home.now()})
    path = handed_path(session_id)
    home.mkdir_private(path.parent)
    home.write_private(path, json.dumps({'carried': carried}))
    return resume_spawn(held, work_id, agent, [f'resume={session_id}', *extra], 'resume', besides=pid)


def sessions(store: Store, work_id: str | None = None, *, verify: bool = True,
             open_work: Sequence[WorkRecord] | None = None) -> list[dict[str, Any]]:
    """The sessions, oldest first, of one ticket or of every ticket, read through this module's own tables whatever
    module the store was opened for: the project's, with what a metaform's store still held of them carried first."""
    own = own_store(store)
    try:
        carry_conversations(own)
    except StoreError:  # a metaform that cannot be read now keeps what it holds of them until one can carry it
        pass
    try:
        with own.tables(write=False) as tx:
            found = (tx.rows('agent_sessions', {'work_id': work_id}, by=('work_id', 'seq'), limit=0) if work_id
                     else tx.rows('agent_sessions', by=('seq',), limit=0)).results
            rows = [dict(row) for row in found]
    except StoreError:
        return []
    return verified(store, rows, open_work) if verify else rows


def base_holds(store: Store) -> dict[str, int]:
    """What a base holds of dispatch's that a clear or a switch takes from the person: the agents at work on it now,
    pinned to it, each checked with its runner, as `agents_at_work` names them. The conversations with agents are the
    project's, kept through a clear or a switch of bases, PROJ-026, so none is counted as the base's."""
    bound = store.bound_base()
    if bound is None:
        return {}
    return {'agents': len(agents_at_work(store.project_id, bound.id, False))}


def verified(store: Store, rows: Sequence[dict[str, Any]],
             open_work: Sequence[WorkRecord] | None = None) -> list[dict[str, Any]]:
    """Stored session rows as session_status reads them, in order: a running row is checked with its runner."""
    own = own_store(store)
    asked = [row for row in rows if row['state'] == 'running']
    if not asked:
        return [session_status(own, row) for row in rows]
    # One read of the open tickets for every running row, rather than a ticket read for each, made while each running
    # row's runner is asked for its status, all at once rather than in turn: a read waits for the slowest of them, not
    # their sum, code.dispatcher.agent#3b. Each ask runs in a copy of this context, sharing the caller's registry
    # validation; a reply for a ticket found done is not used.
    with ThreadPoolExecutor(max_workers=len(asked)) as pool:
        replies = {id(row): pool.submit(contextvars.copy_context().run, session_status, own, row, done=False)
                   for row in asked}
        opened = {record.id for record in (open_work if open_work is not None
                                           else store.work(open=True, limit=0).results)}
        # a runner pinned to another metaform, made active before or since, works a ticket of that one, BASE-052
        bound = store.bound_base()
        for base in sorted({str(row['base']) for row in asked if row.get('base')} - {bound.id if bound else ''}):
            if home.base_by_id(store.project_id, base) is not None:
                try:
                    opened |= {record.id for record in Store(store.project_id, base=base).work(open=True,
                                                                                               limit=0).results}
                except StoreError:
                    continue
        found: list[dict[str, Any]] = []
        for row in rows:
            # a session on no ticket, an intake's or a conversation's, is ended by no ticket's being done
            done = row['work_id'] not in opened and not ticketless(row['work_id'])
            found.append(replies[id(row)].result() if id(row) in replies and not (done and not summoned(row))
                         else session_status(own, row, done=done))
        return found


def recorded_activity(store: Store, row: dict[str, Any]) -> str:
    """Only a final recorded end_turn supports idle activity; it says nothing about session liveness."""
    activity = 'unknown'
    # Old runners cannot report their current turn. A final recorded end_turn supports idle activity only;
    # it does not end the session, and later output makes that historical turn insufficient evidence.
    try:
        with store.tables(write=False) as tx:
            lines = tx.rows('session_lines', {'session_id': row['session_id']}, by=('session_id', 'seq'),
                            limit=0).results
        latest = [line for line in lines if line['seq'] == lines[-1]['seq']] if lines else []
        if len(latest) == 1 and latest[0]['kind'] == 'turn' and latest[0]['text'] == 'The turn ended: end_turn.':
            activity = 'idle'
    except StoreError:
        pass
    return activity


def session_status(store: Store, row: dict[str, Any], *, done: bool | None = None) -> dict[str, Any]:
    """A stored running row is a claim: check the ticket, that its pid is a runner, and the runner's authenticated
    reply, including its adapter; a runner that cannot reply is that ticket's only when its pid runs that work id.
    `done` is whether the ticket is done when the caller has read it already. Reads preserve the row and transcript."""
    if row['state'] != 'running':
        return {**row, 'activity': 'idle'}
    if (done if done is not None else ticket(store, row['work_id']).done) and not summoned(row):
        return {**row, 'state': 'ended', 'how': 'the ticket is done', 'activity': 'idle'}
    if row.get('origin') and foreign(row):  # its pid and port are another home's, even when they answer
        return {**row, 'state': 'ended', 'how': FOREIGN, 'activity': 'idle'}
    runner = runner_of(row.get('pid'))
    if runner is None:
        return {**row, 'state': 'ended', 'how': 'the runner is no longer running', 'activity': 'idle'}
    try:
        answer = tell(row, 'status', limit=1.0)
    except ConnectionRefusedError:
        return {**row, 'state': 'ended', 'how': 'the runner is no longer listening', 'activity': 'idle'}
    except (OSError, ValueError, TypeError, KeyError):
        answer = {}
    if answer.get('session_id') not in (None, row['session_id']):
        return {**row, 'state': 'ended', 'how': 'its port answers for another session', 'activity': 'idle'}
    if answer.get('state') not in ('running', 'ended'):  # an older runner, with no status to give, or a late reply
        # only the session's own reply shows a runner went on to this ticket; a serve's pid answers for every editor
        # session it holds, whatever their ticket, BASE-062
        if runner not in (row['work_id'], SERVED):
            return {**row, 'state': 'ended', 'how': 'its pid runs the runner of another ticket', 'activity': 'idle'}
        return {**row, 'activity': recorded_activity(store, row)}
    reported = answer.get('activity')
    return {**row, 'state': answer['state'], 'how': answer.get('how'),
            'interrupting': answer.get('interrupting') is True,
            'waiting_on': answer.get('waiting_on') if answer.get('waiting_on') in ('question', 'permission') else None,
            # an intake waiting for its first record, M04, beside its activity
            **({'phase': str(answer['phase'])} if answer.get('phase') else {}),
            # how its permission requests are answered now, and whose choice that is: session, launch or project
            **({'prompts': str(answer['prompts']), 'prompts_from': str(answer.get('prompts_from') or 'project')}
               if answer.get('prompts') in PROMPTS else {}),
            'activity': reported if reported in ('working', 'waiting', 'idle') else recorded_activity(store, row)}


# Sessions and tickets in the one status vocabulary of work, metaform.data.status, H02: the state, and why it is
# there when that says more, the same reasons A2A reads a ticket by. A session that waits on the person is
# input_required with what for: a login, a permission, a question, or its agent stopped with its ticket open; one
# whose runner died is told apart from one that ended with its work, and a cancel from a completion.
WAITS = {'login-needed': 'login', 'permission-waiting': 'permission', 'question-waiting': 'question'}
DIED = ('the runner is no longer running', 'the runner is no longer listening', 'its port answers for another session',
        'its pid runs the runner of another ticket')
# how a row reads when its pid is a live runner that does not answer for its session, `silent`
SILENT = ('the runner is no longer listening', 'its port answers for another session')
FOREIGN ='another Metaform home started it'


def session_work_status(row: dict[str, Any], raised: Sequence[dict[str, Any]] = ()) -> dict[str, str | None]:
    """A session, as session_status reads it, in the status vocabulary, with the signals raised on its ticket."""
    own = {str(one.get('signal')) for one in raised if one.get('session_id') in (None, '', row.get('session_id'))}
    if row.get('state') == 'running':
        waits = next((why for signal, why in WAITS.items() if signal in own), None)
        if waits or row.get('waiting_on'):
            return {'status': 'input_required', 'reason': waits or str(row.get('waiting_on'))}
        if row.get('phase'):  # an intake waiting for its first record, M04
            return {'status': 'running', 'reason': str(row['phase'])}
        if row.get('activity') == 'working':
            return {'status': 'running', 'reason': None}
        return {'status': 'input_required', 'reason': 'stopped' if 'stopped-open' in own else 'person'}
    how = str(row.get('how') or '')
    if how == HANDED:  # a runner on the code on disk is taking it up
        return {'status': 'running', 'reason': HANDED}
    if how in DIED:
        return {'status': 'failed', 'reason': 'runner died'}
    if how.startswith(('it failed', 'it did not start')):
        return {'status': 'failed', 'reason': how}
    if how in ('cancelled by the person', 'the runner was terminated') or how.startswith('stopped by '):
        return {'status': 'cancelled', 'reason': how}
    return {'status': 'completed', 'reason': how or None}


def ticket_work_status(record: WorkRecord, found: Sequence[dict[str, Any]],
                       raised: Sequence[dict[str, Any]]) -> dict[str, str | None]:
    """A ticket in the status vocabulary: done as its outcome says, completed, cancelled or failed, P232; waiting on
    the person for a login, a permission, a question, its agent stopped with it open, or a runner that died holding
    it; running while its agent works; otherwise submitted, held or not."""
    if record.done:
        return {'status': status.known(record.outcome or 'completed', f'metaform map work id={record.id}'),
                'reason': None}
    signals = {str(one.get('signal')) for one in raised}
    waits = next((why for signal, why in WAITS.items() if signal in signals), None)
    if waits:
        return {'status': 'input_required', 'reason': waits}
    if record.taken:
        latest = found[-1] if found else None
        if latest is None or latest.get('state') == 'running':
            return session_work_status(latest, raised) if latest else {'status': 'running', 'reason': 'starting'}
        if str(latest.get('how') or '') in DIED:
            return {'status': 'input_required', 'reason': 'runner died'}
        return {'status': 'input_required', 'reason': 'stopped'}
    return {'status': 'submitted', 'reason': 'held' if record.held else None}


def work_read(ctx: Context, record: WorkRecord) -> dict[str, Any] | None:
    """What dispatch keeps on a work record: the sessions of agents dispatched on it, oldest first, without what only
    this module uses to reach them, its signals, and its assignment or manually selected model and effort, by ACP
    category, shown under `dispatch` in `map work id=<id>`, BASE-035; nothing on a ticket dispatch holds nothing of."""
    if ctx.store is None:
        return None
    # A work hook can supply scheduling metadata inside a reservation. Socket probes belong before its write lock.
    found = sessions(ctx.store, record.id, verify=not ctx.store.in_atomic)
    from .signals import rows
    signals = rows(ctx.store, record.id)
    chosen = ticket_options(ctx.store, record.id)  # the ticket's own model and effort, P015, shown where it is read
    chosen = {**chosen, **launch_options(ctx.store, record.id)}  # and its latest launch's permissions
    with Store(ctx.store.project_id, module='dispatch').tables(write=False) as tx:
        completion = tx.get('merges', {'work_id': record.id})
    if not found and not signals and not chosen and completion is None:
        return None
    return {'sessions': [{**{key: value for key, value in session.items() if key not in PRIVATE},
                          **session_work_status(session, signals)} for session in found],
            'signals': signals, **({'options': chosen} if chosen else {}),
            **({'completion': dict(completion)} if completion is not None else {}),
            **ticket_work_status(record, found, signals)}


def running(store: Store, work_id: str) -> dict[str, Any] | None:
    found = [row for row in sessions(store, work_id) if row.get('state') == 'running']
    return found[-1] if found else None


def tell(session: dict[str, Any], op: str, limit: float = REPLY_LIMIT, **given: Any) -> dict[str, Any]:
    """Send one request to a running session's control port and return its one reply."""
    held = session
    with socket.create_connection(('127.0.0.1', int(held['port'])), timeout=limit) as connection:
        connection.sendall(json.dumps({'token': held.get('token'), 'op': op, **given}).encode('utf-8') + b'\n')
        with connection.makefile('rb') as answers:
            line = answers.readline()
    found: Any = json.loads(line) if line else None
    return cast(dict[str, Any], found) if isinstance(found, dict) else {}


def glyph_of(ctx: Context, record: WorkRecord) -> str | None:
    """The agent glyph a ticket is assigned to, VIEW-040, as the map module shows it on the work record under `map`,
    BASE-035; None when it has none or the map module is not on the surface."""
    kept = work_reads(ctx.folder, record, project=ctx.project).get('map')
    glyph = cast(dict[str, Any], kept).get('glyph') if isinstance(kept, dict) else None
    return str(glyph) if glyph else None


def eligible_of(ctx: Context, record: WorkRecord) -> list[str]:
    """The eligible agents map serves on a ticket, MAP-058; an absent choice means Any."""
    kept = work_reads(ctx.folder, record, project=ctx.project).get('map')
    agents: Any = cast(dict[str, Any], kept).get('eligible', []) if isinstance(kept, dict) else []
    if not isinstance(agents, list) or any(not isinstance(agent, str) for agent in cast(list[Any], agents)):
        raise Stop(f'Work {record.id} has an unreadable eligible agents choice: {agents!r}.',
                   f'metaform map work id={record.id}')
    return cast(list[str], agents)


def require_eligible(ctx: Context, record: WorkRecord, agent: str) -> None:
    agents = eligible_of(ctx, record)
    if agents and agent not in agents:
        store = ctx.require_store()
        raise Stop(f'{agent} is not eligible for {called(store, [record.id])[record.id]}; eligible agents: '
                   f'{", ".join(agents)}.', f'metaform map work id={handle(store, record.id)}')


def agent_for(ctx: Context, record: WorkRecord | None, agent: str | None = None) -> str:
    """Use the explicit agent or ticket preference when eligible, otherwise the first listed, MAP-058."""
    chosen = agent or (preferred(record, ticket_settings(ctx).get(record.id), str(ctx.setting('dispatch_agent')),
                                 store=ctx.store) if record is not None else str(ctx.setting('dispatch_agent')))
    agents = eligible_of(ctx, record) if record is not None else []
    return agent_named(chosen if not agents or chosen in agents else agents[0])


def called(store: Store, work_ids: Sequence[str]) -> dict[str, str]:
    """Each ticket as the person reads it, `<address>#<n> "<title>"`, MCP-037, read in one pass; a ticket with no number
    by its id's first characters. A refusal names tickets so, never by their 32-hex ids, which the person cannot tell
    apart (UX review round 2, held-and-signals F6)."""
    found: dict[str, tuple[str, str | None, str | None]] = {}
    try:
        found = store.numbers_of('work', [one for one in work_ids if not ticketless(one)])
    except StoreError:
        pass
    named: dict[str, str] = {}
    for work_id in work_ids:
        if ticketless(work_id):
            named[work_id] = 'the intake' if intake_id(work_id) else helper_item(work_id) if helper_id(work_id) \
                else 'a conversation'
            continue
        item, title, _ = found.get(work_id) or (None, None, None)
        named[work_id] = (f'{item} "{title}"' if title else str(item)) if item else f'ticket {work_id[:8]}'
    return named


def handle(store: Store, work_id: str) -> str:
    """A ticket's own `<address>#<n>`, as `map work id=` takes it, for a next step; its id when it has no number."""
    try:
        found = store.numbers_of('work', [work_id]).get(work_id)
    except StoreError:
        found = None
    return found[0] if found else work_id


def startable(ctx: Context, store: Store, record: WorkRecord, agent: str, *,
              checked_sessions: Sequence[dict[str, Any]] | None = None) -> None:
    """Refuse a ticket done, taken or already holding a session, and an occupied glyph, VIEW-039 and VIEW-040:
    tickets with one glyph are one agent's, done one at a time. Each refusal names the tickets by their handle and
    title. Reservation callers verify sessions before taking the write lock, then recheck their stored identities
    here. A new or changed running row remains occupied until it can be verified outside the transaction."""
    require_eligible(ctx, record, agent)
    this = called(store, [record.id])[record.id]
    if record.done:
        raise Stop(f'{this} was done at {record.done}.', 'metaform map work open=true')
    if record.taken:
        raise Stop(f'{this} is already taken by {record.taken_by or "an agent"}.',
                   'metaform map work open=true')
    if not (record.task or '').strip():
        raise Stop(f'{this} has no task: nothing for an agent to do until one is written.',
                   f'metaform map work op=edit id={handle(store, record.id)} task="<what it needs>"')
    blocking = waiting_on(after_of(store, record.id), {other.id for other in store.work(open=True, limit=0).results})
    if blocking:  # the plan's order, `after_work`: UX review round 1, orchestrator F6
        names = called(store, blocking)
        raise Stop(f'{this} waits on {", ".join(names[one] for one in blocking)}, not done yet; it starts once '
                   f'{"that is" if len(blocking) == 1 else "they are"} done.',
                   f'metaform map work id={handle(store, blocking[0])}')
    lock = claimed(store, record.address or record.receiver_address, record.id)
    if lock is not None:  # work claims are the scheduling lock, LAYER-029: no ticket inside another's claim starts
        raise Stop(f'{this} is on a part of the map claimed by "{lock["name"]}" until that work has landed.',
                   'metaform dispatch claims')
    glyph = glyph_of(ctx, record)
    if glyph is not None:
        occupied = next((held for held in store.work(open=True, limit=0).results
                         if held.taken and (held.taken_by or '').startswith('dispatch starting ') and
                         held.id != record.id and glyph_of(ctx, held) == glyph), None)
        if occupied is not None:
            raise Stop(f'Agent {glyph} is at work on {called(store, [occupied.id])[occupied.id]}; the tickets with its '
                       'glyph are done one at a time.', f'metaform map work id={handle(store, occupied.id)}')
    found = sessions(store, record.id if glyph is None else None) if checked_sessions is None else sessions(
        store, record.id if glyph is None else None, verify=False)
    checked = {row['session_id']: row for row in checked_sessions or ()}
    for session in found:
        previous = checked.get(session['session_id'])
        if session.get('state') == 'running' and previous is not None and all(
                session.get(key) == previous.get(key) for key in ('runner', 'pid', 'port', 'token', 'seq')):
            checked_work = held_ticket(store, session['work_id']) if previous.get('how') == 'the ticket is done' else None
            if checked_work is None or checked_work.done:
                session = previous
        if session.get('state') != 'running':
            continue
        if session['work_id'] == record.id:
            raise Stop(f'{this} already has an agent session.',
                       f'metaform dispatch sessions id={record.id}')
        other = held_ticket(store, session['work_id']) if glyph is not None else None
        if other is not None and glyph_of(ctx, other) == glyph:
            raise Stop(f'Agent {glyph} is at work on {called(store, [other.id])[other.id]}; the tickets with its glyph '
                       'are done one at a time.', f'metaform map work id={handle(store, other.id)}')


def starts_held(ctx: Context) -> str | None:
    """The caution of a start of a ticket held for the person, `Verb.person_decides`: held in Backlog, or held from
    agents with hold. Starting one releases it, so it is the person's decision on every surface: their card's Start,
    or their own terminal; an agent's start of it waits on their answer (UX review round 2, held-and-signals F4: an
    intake agent started a held ticket in one call). A conversation, a merge's preparation, a resume, a retry or a
    launch `start` reserved already starts nothing held."""
    nouns = ctx.nouns
    if not ctx.setting('agents_ask_first'):
        return None  # the person lets their agents start and release work without asking
    if any(nouns.get(word) for word in ('reservation', 'system', 'talk', 'sentinel', 'intake', 'prep', 'resume',
                                        'retry')):
        return None
    work_id = str(nouns.get('id') or '')
    if not work_id or ticketless(work_id):
        return None
    store = ctx.require_store()
    record = ticket(store, work_id)
    if record.done or record.taken:
        return None
    hold = not record.held and bool(ticket_settings(ctx).get(record.id, {}).get('hold'))
    if not (record.held or hold):
        return None
    # the person's word in their system agent's turn is their decision, `start` records it; at the command line a
    # dispatched agent with none is told why too, and over MCP its call waits on the person's card
    what, why = f'Starting an agent on ticket {record.id}', ''
    if ctx.surface == 'cli':
        try:
            word = on_persons_word(ctx, what, [record.id])
        except PersonsDecision as refused:
            word, why = None, f' {refused.message}'
    else:
        word = word_of(ctx.folder, what, ctx.project, [record.id])
    if word is not None:
        return None
    return (f'Starting an agent on {called(store, [record.id])[record.id]} releases it: it is '
            f'{"held in Backlog" if record.held else "held from agents"} for the person.{why}')


def next_ticket(ctx: Context, store: Store, glyph: str, *, agent: str | None = None,
                exclude: tuple[str, ...] = ()) -> WorkRecord | None:
    """The glyph's next ticket, VIEW-040: the first not done and not taken in To do's board order, by its place, a
    ticket with none after, as Distribute deals them; an exclude record is no ticket. A held ticket is never taken
    next, whatever its glyph: the person releases it (UX review round 2, held-and-signals F3: a glyph agent finished
    its ticket and then worked every held one, agents' follow-ups and merge release logs among them); nor is one
    waiting on a ticket still open (UX review round 1, orchestrator F6)."""
    kept = ticket_settings(ctx)
    opened = store.work(open=True, limit=0).results
    open_ids = {record.id for record in opened}
    waiting = [record for record in opened
               if not record.taken and not record.held and record.id not in exclude
               and not waiting_on(kept.get(record.id), open_ids)
               and not kept.get(record.id, {}).get('hold') and (record.task or '').strip()]  # no task: nothing to do
    waiting.sort(key=lambda record: (record.position is None, record.position or 0))
    chosen = agent or ctx.nouns.get('agent') or str(ctx.setting('dispatch_agent'))
    for record in waiting:
        if kept.get(record.id, {}).get('glyph') != glyph:
            continue
        try:
            require_eligible(ctx, record, chosen)
        except Stop:
            continue
        if rework_blocked(ctx, store, record):
            continue
        return record
    return None


def map_work(ctx: Context, *, session: str | None = None, on: Surface | None = None, **nouns: Any) -> Any:
    """Use the map's public verb without importing its implementation, on the caller's surface or the one named `on`,
    and for its agent session, or the one named, so what the read tells that session is recorded as told to it,
    MCP-039."""
    found = next((module for module in surface(ctx.folder) if module.id == 'map'), None)
    if found is None:
        raise Stop('The map module is not active.', 'metaform enable map')
    verb = next(verb for verb in found.verbs if verb.name == 'work')
    return verb.run(context('map', ctx.folder, project=ctx.project, nouns=nouns, surface=on or ctx.surface,
                            client=ctx.client, session=session or ctx.session))


def workflow_skill(ctx: Context, name: str, given: str) -> str:
    """A skill served whole with an input, for a purpose agent's first turn, VIEW-045: by workflow serve while the
    workflow module is on the folder's surface, else from the skill registry by its address, BASE-059."""
    found = next((module for module in surface(ctx.folder) if module.id == 'workflow'), None)
    if found is None:
        from metaform import skills
        return skills.served(f'prompt.skill.{name}', given)
    verb = next(verb for verb in found.verbs if verb.name == 'serve')
    return str(verb.run(context('workflow', ctx.folder, project=ctx.project, nouns={'name': name, 'input': given})))


def memory_read(folder: Path, project: str | None, verb: str, **nouns: Any) -> Any:
    """What a read verb of the memory module answers, run without importing it; None when it is not on the folder's
    surface, BASE-004."""
    found = next((module for module in surface(folder) if module.id == 'memory'), None)
    if found is None:
        return None
    run = next(one for one in found.verbs if one.name == verb)
    return run.run(context('memory', folder, project=project, nouns=nouns))


def module_read(folder: Path, project: str | None, module_id: str, verb: str, **nouns: Any) -> Any:
    """What a read verb of another module answers, run without importing it; None when that module is not on the
    folder's surface, BASE-004."""
    found = next((module for module in surface(folder) if module.id == module_id), None)
    run = next((one for one in found.verbs if one.name == verb and one.effect == 'read'), None) if found else None
    return None if run is None else call(run.run, context(module_id, folder, project=project, nouns=nouns))


def intake_prompt(ctx: Context, asked: str) -> str:
    """The intake exactly as the intake module serves it, with what the person asked for in its prompt slot, for an
    intake agent's first turn: the intake is the instruction, and nothing is added to it, BASE-039."""
    found = next((module for module in surface(ctx.folder) if module.id == 'intake'), None)
    if found is None:
        raise Stop('The intake module is not active; it serves the intake the agent follows.', 'metaform enable intake')
    verb = next(verb for verb in found.verbs if verb.name == 'prompt')
    return str(verb.run(context('intake', ctx.folder, project=ctx.project, nouns={'text': asked} if asked else {})))


def release(store: Store, work_id: str, by: str, took: bool, session_id: str | None, how: str,
            runner: str | None = None) -> None:
    """What an ending session leaves: its session row says it ended. A ticket it took and did not finish stays taken,
    with the agent's last note on it, until the person puts it back on the board: nothing restarts by itself. A
    runner whose own code cannot reach the store runs this in a new process, with the code on disk."""
    requeued = False
    if session_id is not None:
        # with the ticket's progress when it took one; a conversation on no map writes no metaform, so none is made
        with store.atomic() if took else contextlib.nullcontext():
            with store.tables() as tx:
                previous = tx.get('agent_sessions', {'session_id': session_id})
                if previous is not None and (previous['work_id'] != work_id
                                             or runner and previous.get('runner') != runner):
                    return  # a late release must never end or clear permissions on the session's latest resume
                if previous is not None and previous['state'] == 'running':
                    tx.concern(work_id=work_id, session_id=session_id, kind='session')
                    tx.update('agent_sessions', {'session_id': session_id}, {'state': 'ended', 'how': how,
                                                                           'ended': home.now()})
            if took and runner and previous is not None and previous['state'] == 'running':
                from .progress import finish
                finish(store, work_id, runner, how)
    if session_id is not None or requeued:
        from .signals import clear_permissions, publish
        ctx = context('dispatch', Path(store.project().path), project=store.project_id)
        record = held_ticket(store, work_id)
        if took and runner and record is not None:
            from .progress import refresh
            refresh(ctx, store, record)
        if session_id is not None:
            clear_permissions(ctx, session_id)
            # an ended session is no longer stopped and waiting; not-smooth below says what is left, BASE-057
            publish(ctx, 'stopped-open', work_id=work_id, session_id=session_id, active=False,
                    reason='the session ended')
        if record is not None and not record.done and how != 'orchestration suspended':
            publish(ctx, 'not-smooth', work_id=work_id, session_id=session_id or '', key=by, reason=how)
            if requeued:
                publish(ctx, 'requeue', work_id=work_id, session_id=session_id or '', key=by, reason=how)


def ticket_row(store: Store, work_id: str) -> dict[str, Any] | None:
    """The ticket's row of ticket_options, or None."""
    try:
        with own_store(store).tables(write=False) as tx:
            return tx.get('ticket_options', {'work_id': work_id})
    except StoreError:
        return None


def ticket_options(store: Store, work_id: str) -> dict[str, str]:
    """A ticket's own model and effort, by the ACP category each sets: `model` and `thought_level`."""
    row = ticket_row(store, work_id)
    try:
        bound = store.bound_base()
        with Store(store.project_id, base=bound.id if bound else None, module='map').tables(write=False) as tx:
            runtime = tx.get('ticket_settings', {'work_id': work_id})
    except StoreError:
        runtime = None
    # A map decision makes its nullable fields authoritative, including a person's explicit clearing of a value.
    # Older manual tunes remain readable until their next edit or assignment carries them into the map.
    chosen = runtime if runtime is not None and runtime.get('decision') else {
        **(dict(row) if row is not None else {}),
        **({field: runtime[field] for field in ('model', 'effort') if runtime.get(field)} if runtime else {})}
    return {key: str(chosen[field]) for key, field in (('model', 'model'), ('thought_level', 'effort'))
            if chosen.get(field)}


def runtime_provider(ctx: Context) -> Any:
    found = provided(ctx.folder, 'ticket.runtime')
    return found[0][1] if found else None


def runtime_settings(ctx: Context, work_id: str) -> dict[str, Any]:
    """Saved assignment runtime plus manual choices made before the map owned model and effort."""
    owner = runtime_provider(ctx)
    kept: dict[str, Any] = owner.read(ctx, work_id) if owner is not None else {}
    if not kept.get('decision'):
        row = ticket_row(ctx.require_store(), work_id) or {}
        kept = {**kept, **{field: kept.get(field) or row.get(field) for field in ('model', 'effort')}}
        overrides = {field: kept[field] for field in ('agent', 'model', 'effort') if kept.get(field)}
        if overrides:
            kept['decision'] = {'decider': 'person', 'confidence': 1.0, 'task_type': None,
                                'reason': 'Runtime fields selected on the ticket.', 'overrides': overrides}
    decision = cast(dict[str, Any], kept.get('decision') or {})
    if decision.get('decider') == 'person' and 'overrides' not in decision:
        kept['decision'] = {**decision, 'overrides': {
            field: kept[field] for field in ('agent', 'model', 'effort') if kept.get(field)}}
    return kept


def keep_runtime(ctx: Context, work_id: str, choice: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    """Persist a validated assignment choice without replacing existing ticket choices or project defaults."""
    owner = runtime_provider(ctx)
    if owner is None:
        raise Stop('The map must be enabled to save a ticket runtime.', 'metaform enable map')
    held = runtime_settings(ctx, work_id)
    previous = cast(dict[str, Any], held.get('decision') or {})
    overrides = cast(dict[str, Any], previous.get('overrides') or {})
    refined = bool(choice.get('task_fingerprint')
                   and choice.get('task_fingerprint') != previous.get('task_fingerprint'))
    preserve = not refined and all(held.get(field) for field in ('agent', 'model', 'effort')) and bool(previous)
    values = {field: held[field] if preserve else overrides.get(field) or choice.get(field)
              for field in ('agent', 'model', 'effort')}
    agent = str(values.get('agent') or '')
    offered = catalog.get(agent)
    if offered is None or values['model'] not in offered['models'] or values['effort'] not in offered['efforts']:
        raise Stop('The ticket runtime must use installed, eligible agents and their offered model and effort.',
                   f'metaform dispatch options agent={agent or "codex"}')
    if preserve:
        values['decision'] = held['decision']
    elif all(overrides.get(field) for field in ('agent', 'model', 'effort')):
        values['decision'] = {**previous, 'task_type': choice.get('task_type'),
                              'task_fingerprint': choice.get('task_fingerprint')}
    else:
        confidence = choice.get('confidence')
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
            raise Stop('Runtime confidence must be between 0 and 1.', 'metaform orchestration route')
        if choice.get('decider') not in ('jev', 'facilitator'):
            raise Stop('Runtime decider must be jev or facilitator.', 'metaform orchestration route')
        values['decision'] = {field: choice.get(field) for field in
                              ('decider', 'confidence', 'task_type', 'reason', 'task_fingerprint')}
        values['decision']['overrides'] = overrides
    return owner.save(ctx, work_id, values)


def edit_runtime(ctx: Context, work_id: str, given: dict[str, Any], *, agent: str | None = None) -> dict[str, Any]:
    """The person's card or tune edit, validated against the same catalog and recorded with personal provenance."""
    fields = ('agent', 'model', 'effort')
    if any(field in given for field in ('model', 'effort')):
        persons_own(ctx, 'A ticket\'s model and effort')
    store = ctx.require_store()
    record = ticket(store, work_id)
    owner = runtime_provider(ctx)
    if owner is None:
        raise Stop('The map must be enabled to save a ticket runtime.', 'metaform enable map')
    kept = runtime_settings(ctx, work_id)
    previous = cast(dict[str, Any], kept.get('decision') or {})
    overrides = cast(dict[str, Any], previous.get('overrides') or {})
    values = {field: kept.get(field) for field in fields}
    values.update({field: None if str(given[field] or '').strip() in ('', 'none') else str(given[field]).strip()
                   for field in fields if field in given})
    agent = agent or str(values.get('agent') or agent_for(ctx, record))
    if 'agent' in given and values.get('agent') != kept.get('agent'):
        for field in ('model', 'effort'):
            if field not in given:
                offered = offered_values(store, agent, 'model' if field == 'model' else 'thought_level')
                if offered is None or values[field] not in offered:
                    values[field] = None
                    overrides = {key: value for key, value in overrides.items() if key != field}
    notices: list[dict[str, str]] = []
    for field in ('model', 'effort'):
        if field not in given or values[field] is None:
            continue
        offered = offered_values(store, agent, 'model' if field == 'model' else 'thought_level')
        if offered is None:
            notices.append({'where': field, 'message': f'{agent} has not run here; {field} is kept unchecked.'})
        elif values[field] not in offered:
            raise Stop(unknown_choice(agent, offered_option(store, agent, 'model' if field == 'model'
                                                            else 'thought_level') or {}, str(values[field])),
                       f'metaform dispatch options agent={agent}')
    overrides = {**overrides, **{field: values[field] for field in fields if field in given}}
    overrides = {field: value for field, value in overrides.items() if value is not None}
    values['decision'] = {'decider': 'person', 'confidence': 1.0, 'task_type': previous.get('task_type'),
                          'task_fingerprint': previous.get('task_fingerprint'),
                          'reason': 'Runtime changed on the ticket.', 'overrides': overrides}
    result = owner.save(ctx, work_id, values)
    # Retire the former model/effort source on an edit. Launch permissions retain their original row and authority.
    held = ticket_row(store, work_id)
    if held is not None and (held.get('model') or held.get('effort')):
        with own_store(store).tables() as tx:
            tx.concern(work_id=work_id, kind='ticket')
            tx.update('ticket_options', {'work_id': work_id}, {'model': None, 'effort': None, 'seq': time.time_ns()})
    return {**result, **({'notices': notices} if notices else {})}


def launch_options(store: Store, work_id: str) -> dict[str, str]:
    """The permissions the ticket's latest launch was given, `prompts` over dispatch_prompts and `mode` over
    dispatch_<agent>_<option>; each left out when the launch left it to the project's settings. Only the agent that
    launch started on the ticket takes them, never a conversation about it."""
    row = ticket_row(store, work_id)
    if row is None:
        return {}
    return {field: str(row[field]) for field in ('prompts', 'mode') if row.get(field)
            and (field != 'prompts' or row[field] in PROMPTS)}


def launch_permissions(ctx: Context, store: Store, agent: str) -> tuple[dict[str, str | None], list[dict[str, str]]]:
    """The permissions a start gives its launch, `prompts` and `mode`, checked: prompts one of dispatch_prompts' own,
    mode one the agent offered at its last session here, or kept unchecked with a notice when it has not run here.
    The person's own, since they decide what the agent may do without asking."""
    given = {field: str(ctx.nouns.get(field) or '').strip() or None for field in ('prompts', 'mode')}
    notices: list[dict[str, str]] = []
    if not any(given.values()):
        return given, notices
    persons_own(ctx, 'An agent\'s permissions')
    if given['prompts'] is not None and given['prompts'] not in PROMPTS:
        raise Stop(f'prompts is one of {", ".join(PROMPTS)}, not {given["prompts"]}.', 'metaform help dispatch start')
    if given['mode'] is not None:
        offered = offered_values(store, agent, 'mode')
        if offered is None:
            notices.append({'where': 'mode', 'message': f'{agent} has not run in this project yet, so mode='
                            f'{given["mode"]} is kept unchecked; metaform dispatch options agent={agent} prime=true '
                            'lists what it offers.'})
        elif given['mode'] not in offered:
            raise Stop(f'{agent_label(agent)} offers mode {", ".join(offered) or "none"} at its last session here, '
                       f'not {given["mode"]}.', f'metaform dispatch options agent={agent}')
    return given, notices


def keep_launch(store: Store, work_id: str, given: dict[str, str | None]) -> None:
    """Write a launch's permissions over the previous launch's, keeping the ticket's own model and effort."""
    with own_store(store).tables() as tx:
        tx.concern(work_id=work_id, kind='ticket')  # its event names the ticket, BASE-053
        held = tx.get('ticket_options', {'work_id': work_id})
        kept = {**{field: (held[field] if held else None) for field in ('model', 'effort')}, **given}
        tx.delete('ticket_options', {'work_id': work_id})
        if any(kept.values()):
            tx.insert('ticket_options', {'work_id': work_id, **kept, 'seq': time.time_ns()})


def wanted_options(ctx: Context, store: Store, agent: str, work_id: str | None) -> dict[str, str]:
    """The settings a session of the agent is given: its dispatch_<agent>_<option> settings, then its ticket's own."""
    chosen: dict[str, str] = {}
    if work_id and not intake_id(work_id):
        runtime = runtime_settings(ctx, work_id)
        if not runtime.get('agent') or runtime['agent'] == agent:
            chosen = ticket_options(store, work_id)
    return {**chosen_options(ctx, agent), **chosen}


def today() -> str:
    return time.strftime('%Y-%m-%d', time.gmtime())


def billable(counts: dict[str, int | None]) -> int:
    """A turn's tokens as billed rather than read: input, output and cache writes, with cache reads at a tenth, the
    rate both adapters' providers charge for them. Both adapters report input without the cached part, and output
    with the thinking in it, so thought tokens are not added again: claude-agent-acp 0.89.1 and codex-acp 2.2.2."""
    def count(key: str) -> int:
        return int(counts.get(key) or 0)
    return count('input') + count('output') + count('cache_write') + -(-count('cache_read') // 10)


_CARRIED: dict[tuple[str, str], tuple[tuple[int, int] | None, ...]] = {}
"""Each metaform's store file and write-ahead log, (st_mtime_ns, st_size) or None when absent, as they were when
carry_spend last left it holding no `spend`, by (project id, base id)."""


def _store_stamp(path: Path) -> tuple[tuple[int, int] | None, ...]:
    def stat(file: Path) -> tuple[int, int] | None:
        try:
            found = file.stat()
        except FileNotFoundError:
            return None
        return found.st_mtime_ns, found.st_size
    return stat(path), stat(path.with_name(path.name + '-wal'))


def carry_spend(store: Store) -> None:
    """Move the spend a metaform of the project still holds beside its map, written there before version 14 or by a
    runner started before it, into the project's `spending`, then delete it there. A row held already is skipped, so
    a carry cut short is finished by the next one. A metaform whose store file and log are as the last carry left
    them is not opened again; one written since is. A metaform that cannot be read raises: its spend is not left out
    of the budgets without a word."""
    for base in Store(store.project_id).bases(limit=0).results:
        key, path = (store.project_id, base.id), home.store_file(store.project_id, base.name)
        if key in _CARRIED and _CARRIED[key] == _store_stamp(path):
            continue
        held = Store(store.project_id, base=base.id, module='dispatch')
        with held.tables(write=False) as tx:
            rows = [dict(row) for row in tx.rows('spend', limit=0).results]
        if rows:
            with own_store(store).tables() as tx:
                for row in rows:
                    if tx.get('spending', {'session_id': row['session_id'], 'seq': row['seq']}) is None:
                        tx.insert('spending', row)
            with held.tables() as tx:
                for row in rows:
                    tx.delete('spend', {'session_id': row['session_id'], 'seq': row['seq']})
        _CARRIED[key] = _store_stamp(path)


_TALKED: dict[tuple[str, str], tuple[tuple[int, int] | None, ...]] = {}
"""Each metaform's store file and write-ahead log as carry_conversations last left it holding no conversation, by
(project id, base id), as `_CARRIED` is for spend."""
# What a metaform's store still holds of the conversations, by the table it is carried to: the sessions, their thread
# lines and the supervisor's retries. A ticket's progress and the signals stay in `lines`: they are the map's.
_CONVERSATION = (('sessions', 'agent_sessions', ('session_id',)), ('lines', 'session_lines', ('session_id', 'name')),
                 ('attempts', 'session_attempts', ('work_id',)))


def _conversation_line(row: dict[str, Any]) -> bool:
    return row['session_id'] != PROGRESS and not str(row['name']).startswith('signal:')


def carry_conversations(store: Store) -> None:
    """Move the conversations a metaform of the project still holds beside its map, written there before version 17,
    by a runner started before it, or brought back by a restore of a backup made before it, into the project's own
    tables, then delete them there, PROJ-026. A row the project holds already is kept as it is, being the one written
    since, and the metaform's copy goes, so a carry cut short is finished by the next one and a restore merges what its
    backup held with what was said since, never losing a row. A metaform whose store file and log are as the last
    carry left them is not opened again. Inside an `atomic()` block nothing is carried, so no other store's lock is
    taken while one is held; the next read outside one carries. A metaform that cannot be read raises: a conversation
    is not left out without a word."""
    if own_store(store).in_atomic:
        return
    for base in Store(store.project_id).bases(limit=0).results:
        key, path = (store.project_id, base.id), home.store_file(store.project_id, base.name)
        if key in _TALKED and _TALKED[key] == _store_stamp(path):
            continue
        held = Store(store.project_id, base=base.id, module='dispatch')
        with held.tables(write=False) as tx:
            found = {source: [dict(row) for row in tx.rows(source, limit=0).results
                              if source != 'lines' or _conversation_line(dict(row))]
                     for source, _, _ in _CONVERSATION}
            raised = [dict(row) for row in tx.rows('lines', {'kind': 'signal'}, by=('kind',), limit=0).results
                      if str(row['name']).startswith('signal:')]
        if raised:  # the signals a runner on older code raised there, the project's since version 18
            with own_store(store).tables() as tx:
                for row in raised:
                    if tx.get('signals', {'session_id': row['session_id'], 'name': row['name']}) is None:
                        tx.insert('signals', {**row, 'text': based(str(row['text']), base.id)})
            with held.tables() as tx:
                for row in raised:
                    tx.delete('lines', {'session_id': row['session_id'], 'name': row['name']})
        for source, target, keys in _CONVERSATION:
            if not found[source]:
                continue
            with own_store(store).tables() as tx:
                for row in found[source]:
                    if tx.get(target, {name: row[name] for name in keys}) is None:
                        tx.insert(target, row)
            with held.tables() as tx:
                for row in found[source]:
                    tx.delete(source, {name: row[name] for name in keys})
        _TALKED[key] = _store_stamp(path)


def based(text: str, base_id: str) -> str:
    """A signal's stored text with the metaform it was raised on, when it does not say one."""
    try:
        value: Any = json.loads(text)
    except ValueError:
        return text
    if isinstance(value, dict) and not cast(dict[str, Any], value).get('base'):
        return json.dumps({**cast(dict[str, Any], value), 'base': base_id}, ensure_ascii=False)
    return text


def carry_project(project_id: str) -> None:
    """The chassis's carrier for dispatch, `home.CARRIERS`: the project's conversations carried out of its metaforms'
    stores before a clear, a restore or a removal takes them, and after a restore brings stores back. With dispatch
    no longer loaded it carries nothing, and what the stores hold of them stays in the clear's backup."""
    project = home.project(project_id)
    if project is None or not any(module.id == 'dispatch' for module in surface(Path(project.path))):
        return
    carry_conversations(Store(project_id, module='dispatch'))


home.CARRIERS['dispatch'] = carry_project


def agents_at_work(project_id: str, base_id: str | None, stop: bool) -> tuple[str, ...]:
    """The chassis's AT_WORK for dispatch: the agents running on the project's metaforms, on `base_id` alone when
    given, one line each, and with `stop` each ended as the person's stop ends it, so a clear or the removal of a
    metaform leaves none at work on a map that is gone, PROJ-025. A runner is on the metaform it was pinned to, its
    row's `base`; one with none, from before, on the active one. The person's own agent is never among them: it is
    theirs to talk with whatever the map holds, VIEW-045. Nor is a session an editor runs, which ends in the editor."""
    project = home.project(project_id)
    if project is None or not any(module.id == 'dispatch' for module in surface(Path(project.path))):
        return ()
    store = Store(project_id, module='dispatch')
    rows = [row for row in sessions(store) if row['state'] == 'running' and not editor(row)]
    theirs = {row['session_id'] for row in system_sessions(store, rows)}
    active = home.active_base(project_id)
    said: list[str] = []
    for row in rows:
        on = str(row.get('base') or (active.id if active is not None else ''))
        if row['session_id'] in theirs or base_id is not None and on != base_id:
            continue
        work_id = str(row['work_id'])
        line = f'{agent_label(str(row["agent"]))} on {named_work(project_id, on, work_id)}'
        if stop:
            try:
                ended = ended_by_person(store, row)
                line += f' (not stopped: {ended["error"]})' if ended.get('error') else ''
            except (Stop, OSError) as error:
                line += f' (not stopped: {error})'
        said.append(line)
    # an intake agent still starting is at work too, on the metaform active when it was launched, VIEW-045
    starting = intake_under_way(store, rows)
    if starting is not None and starting['state'] == 'starting' and \
            (base_id is None or active is not None and base_id == active.id):
        said.append(f'{agent_label(str(starting["agent"])) if starting["agent"] else "An agent"} starting on an intake')
        if stop:
            ended_launch(store, starting)
    # and so is every other runner the gate started that has made no session yet: a ticket's agent an autostart pass
    # launched a moment before, a chat or a sentinel, on the metaform it was pinned to (ux-verify-combined F1)
    made = {row.get('pid') for row in rows}
    seated: set[int] = set()
    for entry in launches():
        if entry.get('project') != project_id or entry['pid'] in made or intake_id(entry.get('work_id')) \
                or entry['pid'] == os.getpid() or entry.get('subject') == 'system':  # the person's own, starting
            continue
        if entry.get('seat'):  # a roundtable belongs to the project: a metaform's clear or removal leaves it at work
            if base_id is None and entry['pid'] not in seated:
                seated.add(entry['pid'])
                said.append(f'A roundtable, {str(entry.get("work_id") or "").removeprefix("roundtables-")}')
                if stop:
                    stopped_seats(int(entry['pid']))
            continue
        on = entry.get('base') or (active.id if active is not None else None)
        if base_id is not None and on != base_id:
            continue
        said.append(f'{agent_label(str(entry.get("agent") or ""))} starting on '
                    f'{named_work(project_id, str(on or ""), str(entry.get("work_id")))}')
        if stop:  # its reservation first, so the stop is not counted as a start that failed
            reservation = entry.get('reservation')
            if isinstance(reservation, str) and reservation:
                with contextlib.suppress(StoreError, Stop):
                    given_back_reservation(Store(project_id), str(entry.get('work_id')), reservation)
            ended_launch_group(int(entry['pid']))
    return tuple(said)


home.AT_WORK['dispatch'] = agents_at_work


def named_work(project_id: str, base_id: str, work_id: str) -> str:
    """What an agent works on, as a person reads it: its ticket's title in quotes, read in the metaform its runner is
    on, or the intake; the work id only when the ticket cannot be read (UX review round 2, 2026-10-17, project-scope
    F5: a switch named agents by 32-character ids)."""
    if intake_id(work_id):
        return 'an intake'
    try:
        record = Store(project_id, base=base_id or None).ticket(work_id).work
    except (StoreError, Stop):
        return f'work {work_id}'
    title = (record.task or '').strip()
    return f"'{title}'" if title else f'work {work_id}'


def agents_following(project_id: str) -> tuple[str, ...]:
    """Navigation never retargets running agents, including the user's advisor."""
    return ()


home.FOLLOWERS['dispatch'] = agents_following



def spend_rows(store: Store, where: dict[str, str]) -> list[dict[str, Any]]:
    """The project's spend matching the filters, whichever metaform it was spent on, that one removed since included."""
    carry_spend(store)
    with own_store(store).tables(write=False) as tx:
        return [dict(row) for row in tx.rows('spending', where, limit=0).results]


def spent(store: Store, *, work_id: str | None = None, run: str | None = None,
          day: str | None = None) -> dict[str, Any]:
    """What was spent on a ticket, by a run or on a UTC day: the billable tokens the agents reported at each turn's
    end, an estimate, billable(); the cost their usage updates added, by currency, `costs`, never summed across
    currencies (`cost` and `currency` are given when there is one); and, per measure, the sessions no budget of it
    can see, `unmetered`: under tokens those whose agent reported no usage at all, under cost those whose agent
    reports tokens but no cost, as codex-acp does."""
    where = {key: value for key, value in (('work_id', work_id), ('run', run), ('day', day)) if value}
    rows = spend_rows(store, where)
    sessions = {str(row['session_id']) for row in rows}
    tokened = {str(row['session_id']) for row in rows if row['cost'] is None and row['metered'] in (None, True, 1)}
    costed = {str(row['session_id']) for row in rows if row['cost'] is not None}
    costs: dict[str, float] = {}
    for row in rows:
        if row['cost'] is not None:
            currency = str(row['currency'] or '?')
            costs[currency] = round(costs.get(currency, 0.0) + float(row['cost']), 6)
    single = next(iter(costs.items())) if len(costs) == 1 else None
    return {'tokens': sum(int(row['tokens'] or 0) for row in rows),
            'cost': single[1] if single else 0.0 if not costs else None,
            'currency': single[0] if single else None, 'costs': costs,
            'unmetered': {'tokens': sorted(sessions - tokened - costed), 'cost': sorted(sessions - costed)}}


def session_cost(store: Store, session_id: str) -> float:
    """The cost a session's rows of `spending` hold already, from which a runner counts what its next reading adds."""
    try:
        return sum(float(row['cost'] or 0) for row in spend_rows(store, {'session_id': session_id}))
    except StoreError:
        return 0.0


# Each budget: its setting, what it is summed by, its name, and its measure, billable tokens or hundredths of cost.
BUDGETS = (('dispatch_budget_ticket', 'work_id', 'ticket', 'tokens'), ('dispatch_budget_run', 'run', 'run', 'tokens'),
           ('dispatch_budget_day', 'day', 'day', 'tokens'), ('dispatch_budget_cost_ticket', 'work_id', 'ticket', 'cost'),
           ('dispatch_budget_cost_day', 'day', 'day', 'cost'))


def over_budget(ctx: Context, store: Store, *, work_id: str | None = None, run: str | None = None,
                pending: int = 0) -> dict[str, Any] | None:
    """The first budget a ticket, a run or today has reached, with what was spent; None while all have room. A budget
    of 0 sets no limit, M01. `pending` is a turn's provisional token estimate, counted on the token budgets. A cost
    budget is held against each currency's own sum, never a sum across currencies."""
    given = {'work_id': work_id, 'run': run, 'day': today()}
    totals: dict[str, dict[str, Any]] = {}
    for key, field, name, measure in BUDGETS:
        limit, value = int(ctx.setting(key) or 0), given[field]
        if not limit or not value:
            continue
        if field not in totals:
            totals[field] = spent(store, **{field: value})
        held = totals[field]
        currency = None
        if measure == 'tokens':
            used = int(held['tokens']) + pending
        else:
            costs = cast(dict[str, float], held['costs'])
            currency = max(costs, key=lambda one: costs[one], default=None)
            used = round(costs[currency] * 100) if currency is not None else 0
        if used >= limit:
            next_step = f'metaform set --{key.replace("_", "-")}=<{"tokens" if measure == "tokens" else "cents"}>'
            if agent_caller():
                next_step = 'metaform map work op=edit id=<your work id> note="..."'
            return {'budget': name, 'measure': measure, 'setting': key, 'limit': limit, 'spent': used,
                    **({'currency': currency} if measure == 'cost' else {}),
                    **({'provisional': pending} if measure == 'tokens' and pending else {}),
                    'next': next_step}
    return None


def budget_stop(ctx: Context, store: Store, work_id: str) -> None:
    """Refuse to start a worker on a ticket or on a day whose budget is reached, saying which, M01."""
    found = over_budget(ctx, store, work_id=work_id)
    if found is not None:
        raise budget_refusal(found)


def budget_refusal(found: dict[str, Any]) -> Stop:
    """A reached budget, as `over_budget` found it, said as the refusal of a start."""
    unit = 'billable tokens' if found['measure'] == 'tokens' else f'hundredths of {found.get("currency") or "cost"}'
    return Stop(f'The {"token" if found["measure"] == "tokens" else "cost"} budget per {found["budget"]} is '
                f'reached: {found["spent"]} of {found["limit"]} {unit}.', str(found['next']))


def ticket_settings(ctx: Context) -> dict[str, dict[str, Any]]:
    """What the map keeps on each ticket: its glyph, runtime choice, decision, eligibility, order and holds."""
    if not any(module.id == 'map' for module in surface(ctx.folder)):
        return {}
    store = ctx.require_store()
    bound = store.bound_base()
    own = Store(store.project_id, base=bound.id if bound else None, module='map')
    with own.tables(write=False) as tx:
        kept: dict[str, dict[str, Any]] = {
            str(row['work_id']): {'glyph': row['glyph']} for row in tx.rows('glyphs', limit=0).results}
        for row in tx.rows('ticket_settings', limit=0).results:
            kept.setdefault(str(row['work_id']), {}).update(agent=row['agent'], hold=bool(row['hold']),
                                                            epic=row['epic'], agents=row['agents'],
                                                            board=row.get('board') or '', model=row.get('model'),
                                                            effort=row.get('effort'), decision=row.get('decision'))
        for row in tx.rows('eligible', limit=0).results:
            kept.setdefault(str(row['work_id']), {})['eligible'] = row['agents']
        for row in tx.rows('after', limit=0).results:
            kept.setdefault(str(row['work_id']), {})['after_work'] = row['works']
    return kept


def active_board(ctx: Context) -> str | None:
    """The map setting `board`, the one board the project works on, '' for the first; None where the map module and
    its boards are not on the surface, so nothing is set aside."""
    if 'board' not in settings.SCHEMA:
        return None
    return str(settings.value('board', ctx.folder) or '')


def set_aside(ctx: Context, work_id: str, kept: dict[str, dict[str, Any]] | None = None) -> str | None:
    """Where a ticket is when it is not on the active board, 2026-10-21: 'the board <name>' or 'the first board';
    None when it is on the active board. Boards set work aside, so only the active board's tickets start by
    themselves."""
    active = active_board(ctx)
    if active is None:
        return None
    on = str(((kept if kept is not None else ticket_settings(ctx)).get(str(work_id)) or {}).get('board') or '')
    if on == active:
        return None
    return f'the board {on!r}' if on else 'the first board'


def after_of(store: Store, work_id: str) -> dict[str, Any]:
    """One ticket's `after_work` as the map module keeps it, read alone; nothing where the map keeps none."""
    try:
        with Store(store.project_id, module='map').tables(write=False) as tx:
            row = tx.get('after', {'work_id': work_id})
    except StoreError:
        return {}
    return {'after_work': row['works']} if row is not None else {}


def epic_of(store: Store, work_id: str) -> str | None:
    """The epic a ticket belongs to, whose worktree and branch it shares, as the map module keeps it; None for a
    ticket in none, for an epic itself, or where the map keeps nothing."""
    try:
        with Store(store.project_id, module='map').tables(write=False) as tx:
            row = tx.get('ticket_settings', {'work_id': work_id})
    except StoreError:
        return None
    epic = str(row['epic']) if row is not None and row['epic'] else None
    return epic if epic != work_id else None


def agents_of(store: Store, work_id: str) -> int:
    """How many agents work on a ticket at once, as the map module keeps it: one where it keeps none."""
    try:
        with Store(store.project_id, module='map').tables(write=False) as tx:
            row = tx.get('ticket_settings', {'work_id': work_id})
    except StoreError:
        return 1
    return int(row['agents'] or 1) if row is not None else 1


def epics(kept: dict[str, dict[str, Any]]) -> set[str]:
    """The epics among the tickets `ticket_settings` read: each marked so, or named by a child. No agent works an epic
    itself; its work is its children."""
    return {str(held['epic']) for held in kept.values() if held.get('epic')}


def fix_in_force(store: Store, work_id: str) -> bool:
    """Whether a ticket's work runs from the project folder: worked there, or its worktree merged into it, VIEW-044. A fix
    in a worktree is not in force until it merges."""
    from .merge import in_force
    return in_force(store, work_id)


def work_over(store: Store, record: WorkRecord) -> bool:
    """Whether repair work is submitted: done, or pending delivery with a recorded result.

    Dispatch can save a verified feature commit while the ticket remains open for delivery.
    """
    if record.done:
        return True
    try:
        with Store(store.project_id, module='map').tables(write=False) as tx:
            row = tx.get('ticket_settings', {'work_id': record.id})
    except StoreError:
        return False
    return row is not None and bool(dict(row).get('landed'))


def waiting_on(kept: dict[str, Any] | None, opened: Iterable[str]) -> list[str]:
    """The tickets a ticket waits on, `after_work`, that are still open: none is started by an agent starter while
    any is, so a plan's order holds (UX review round 1, orchestrator F6). A ticket done, or gone, is waited on no more;
    a ticket's done is a `map.changed` naming it, so the next pass starts what it freed."""
    raw: Any = (kept or {}).get('after_work')
    if not isinstance(raw, list):
        return []
    open_ids = opened if isinstance(opened, (set, frozenset)) else set(opened)
    return [str(one) for one in cast(list[Any], raw) if str(one) in open_ids]


def waits(record: WorkRecord, kept: dict[str, Any] | None, opened: Iterable[str]) -> bool:
    """Whether no agent starter starts this ticket now: it is held in Backlog, which the person releases, or it waits
    on a ticket still open. UX review round 1 (orchestrator F5): `held` held nothing, and autostart started held
    Backlog tickets after To do."""
    return bool(record.held) or bool(waiting_on(kept, opened))


FRONTEND = frozenset({'gui', 'web', 'page', 'viewer', 'view', 'board', 'ui', 'frontend', 'graphical', 'interface',
                      'graphic', 'display', 'render', 'css', 'figures', 'figure', 'chat', 'dock', 'map2d', 'map3d'})


def preferred(record: WorkRecord, kept: dict[str, Any] | None, default: str, *,
              store: Store | None = None) -> str:
    """Ticket choice wins, then its functional area, then the default when its area is unknown."""
    agent = (kept or {}).get('agent')
    if agent in agent_choices():
        return str(agent)
    address = record.address or record.receiver_address or ''
    paths = (kept or {}).get('paths') or ()
    if store is not None:
        paths = [ref.value for ref in store.refs(Node.of(record.node_kind, record.node_id)) if ref.key == 'path']
    if (FRONTEND.intersection(address.split('.'))
            or address == 'code.assistant.navigation' or address.startswith('code.assistant.navigation.')
            or any(str(path).replace('\\', '/').startswith('src/metaform/modules/web/page/') for path in paths)):
        return 'claude'
    return 'codex' if address or paths else default


def summoned(row: dict[str, Any]) -> bool:
    """A session the person summoned to chat about a question: its runner was started with question=."""
    pid = row.get('pid')
    return isinstance(pid, int) and any(word.startswith(('question=', 'prep=', 'system=')) for word in command_line(pid))


STALE_START = 180  # seconds a start may take before its reservation is taken for a start that died


def _seconds(stamp: str | None) -> float:
    """An ISO time as seconds since the epoch; none or unreadable reads as now, so it is never taken for stale."""
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(stamp)).timestamp()
    except ValueError:
        return time.time()


def autostart(ctx: Context) -> dict[str, Any]:
    """The agent starter, VIEW-042: start the tickets that have not been tried, in board order, up to
    `dispatch_agents` at once besides the one summoned to chat, one at a time per glyph, each with the agent it
    prefers. A ticket the person holds is left out; one whose agent stopped with it open stays taken until the person
    acts. A worker's session that ended without the person's stop is resumed by the supervisor, `retry`, up to
    dispatch_retries, then handed to the person; so is the person's system agent while they keep it connected,
    `stay_connected`; nothing else restarts by itself. A session whose runner is verifiably gone, as after a crash, is
    first written as ended, `settle`, so the supervisor sees it."""
    from .recovery import recover, settle
    asked = time.time_ns()  # every start this pass makes is asked for now: a halt written since refuses it
    store = ctx.require_store()
    stopped = halted(store.project_id, None, pinned(store).get(BASE_VARIABLE))
    if stopped is not None:  # a clear or a removal under way: its own stops wake this pass, which starts nothing
        return {'started': [], 'halted': stopped['by']}
    recovered = recover(ctx)
    settle(ctx)  # after recover, which under automatic recovery returns such a ticket to the queue instead
    from .orchestration import drain, service
    owner = service(ctx)
    routed: list[dict[str, Any]] = owner.route_pending(ctx) if owner is not None else []
    continued = drain(ctx)  # restart/reconnect reconciliation of explicitly recorded continuations
    start_raised(ctx, store, asked)  # the person raised these, so they start whether Full Auto is checked or not
    hold_review_due = review_holds(ctx)
    connected = stay_connected(ctx, store, asked)  # the person's own, whether Full Auto is checked or not
    started = start_work(ctx, store, recovered, asked)
    due = [one for one in (started.get('retry_due'), connected.pop('retry_due', None), hold_review_due) if one is not None]
    return {**started, **connected,
            'more': bool(started.get('more') or owner is not None and owner.routing_waiting(ctx)),
            **({'specialist_routing': {
                state: sum(one.get('state') == state for one in routed)
                for state in ('selected', 'creating', 'triage', 'held')}}
                if routed else {}),
            **({'continuations': continued} if continued else {}),
            **({'retry_due': min(due)} if due else {})}


MARKERS = {'trouble': 'This part is marked trouble: it does not do its job. Fix it as the note says.',
           'broken': 'This part is marked broken: it does not do its job. Fix it as the note says.',
           'missing': 'This part is marked missing: it should exist and does not. Build it as the note says.'}


def healing(record: WorkRecord) -> bool:
    """Whether a ticket is the system healing a fault of its own, which starts first, alone, at `HEALING_EFFORT`."""
    return record.condition == 'broken' or record.kind == 'broken'


def marker_task(record: WorkRecord) -> str:
    """The task of a marker that came with none, MAP-046's amendment of 2026-10-14: its note, then what to do."""
    note = (record.note or '').strip()
    return f'{note}\n\n{MARKERS[record.condition]}' if note else MARKERS[record.condition]


def one_node(a: WorkRecord, b: WorkRecord) -> bool:
    """Whether two work records are at one node: the same element or purpose record, or an element and a purpose
    record that holds it or that it holds."""
    if (a.node_kind, a.node_id) == (b.node_kind, b.node_id):
        return True
    for element, join in ((a, b), (b, a)):
        if element.node_kind == 'element' and join.node_kind == 'join' and \
                element.address in (join.receiver_address, join.provider_address):
            return True
    return False


def may_start(ctx: Context, store: Store, opened: Sequence[WorkRecord],
              backoff: dict[str, dict[str, Any]]) -> bool:
    """Whether a pass of the agent starter can write anything, decided from reads alone: a reservation old enough to
    have gone stale, or a ticket it could start and an agent slot free for it. False means `start_work` takes no
    write lock; True only lets it count again inside its transaction, where every rule is checked. A ticket whose
    starts failed waits out its backoff, `backoff`, as `start_work` does."""
    now = time.time()
    if any(record.taken and (record.taken_by or '').startswith('dispatch starting ')
           and now - _seconds(record.taken) > STALE_START for record in opened):
        return True
    kept = ticket_settings(ctx)
    open_ids = {record.id for record in opened}
    if not any(not record.taken and not kept.get(record.id, {}).get('hold')
               and ((record.task or '').strip() or record.condition in MARKERS)
               and not waits(record, kept.get(record.id), open_ids) and not backing_off(backoff.get(record.id), now)
               for record in opened):
        return False
    return free_slots(ctx, store) > 0  # the gate's own count, `slots`


def start_work(ctx: Context, store: Store, recovered: dict[str, Any], asked: int | None = None) -> dict[str, Any]:
    """The tickets the agent starter starts and the workers' sessions the supervisor resumes, `autostart`, only while
    Full Auto is checked. `asked` is when the pass began: a halt written since refuses its starts. A ticket
    whose starts failed waits RETRY_SECONDS doubled for each failure, and is left to the person past dispatch_retries,
    `start_failed`; an agent that keeps failing starts no ticket by itself, `failing_agent`. The earliest wait's end is
    returned as `retry_due`, so the one timer that waits for it brings the next pass."""
    asked = time.time_ns() if asked is None else asked
    if not ctx.setting('dispatch_autostart'):
        return {'started': [], 'recovery': recovered}
    try:
        may_steer(ctx)
        mcp_server(Path(store.project().path))  # a server the runner could not choose leaves every ticket in To do
    except Stop:
        return {'started': [], 'recovery': recovered}
    from .signals import publish
    reached = over_budget(ctx, store)  # the day's budget, M01: nothing starts or retries past it
    if reached is not None:
        publish(ctx, 'budget', key=f'day:{today()}', **reached)
        return {'started': [], 'recovery': recovered, 'budget': reached}
    # Read first: a pass that finds nothing it could start and no reservation gone stale writes nothing, so the
    # changes that start no work cost one read, never the write lock every agent's writes wait on (UX review round
    # 1, runaway F3: each pass reconciled every open ticket's progress in a write transaction first, 93% of a core
    # under a burst of note edits). A ticket's progress is reconciled where its change is heard, progress.changed.
    opened = store.work(open=True, limit=0).results
    paused = resume_paused(ctx, store, opened)  # the work the person's Stop all paused, first, as retries go first
    backoff = start_backoff(store)
    now = time.time()
    ends = [float(row['next_at']) for row in backoff.values() if not row['handed'] and float(row['next_at']) > now]
    start_due = min(ends) if ends else None
    if not may_start(ctx, store, opened, backoff):
        return {'started': [], 'recovery': recovered,
                'capacity_waiting': bool(opened) and slots(ctx, store)['machine_free'] == 0,
                **merged_due(retry(ctx, store, opened, asked), start_due), **paused}
    # Assignment routing records runtime choices before dispatch starts a ticket. Starting never makes a new
    # model decision or waits on a decision service.
    from .orchestration import service
    owner = service(ctx)
    eligible_roles = None if owner is None else {
        record.id for record in opened if not record.taken and not record.held and
        owner.selected_specialist(ctx, record.id)}
    if owner is not None:
        owner.queue_routing(ctx, [record.id for record in opened
                                  if not record.taken and not record.held and record.id not in (eligible_roles or ())])
    # The supervisor's retries first, so a session it resumes takes its slot before a new ticket does, and both share
    # the one count of the gate. UX review round 1, 2026-10-17 (dispatch-concurrency F7): a retry handed over in the
    # same pass left its slot to the next pass, which nothing then brought. A ticket's progress is reconciled where its
    # change is heard, progress.changed, never in a sweep here (runaway F3).
    retried = merged_due(retry(ctx, store, opened, asked), start_due)  # the open tickets as read once above
    failing: dict[str, bool] = {}  # each agent's failing record, read once for the pass
    default = str(ctx.setting('dispatch_agent'))
    reserved: list[tuple[WorkRecord, str, str]] = []
    # Counting and reserving are one write transaction on the work store, so two checks at once, the page's and a
    # runner's, never both see the same free slot. Inside it the map's and dispatch's own tables are only read, and
    # nothing here takes their write lock before the work store's; the runners start after it commits.
    with store.atomic():
        kept = ticket_settings(ctx)
        opened = store.work(open=True, limit=0).results
        open_work = [record for record in opened
                     if not kept.get(record.id, {}).get('hold')]
        open_ids = {record.id for record in opened}
        # held in Backlog, or waiting on a ticket still open: never started here, UX review round 1 (orchestrator F5
        # and F6)
        candidates = [record for record in open_work
                      if not record.taken and ((record.task or '').strip() or record.condition in MARKERS)
                      and (eligible_roles is None or record.id in eligible_roles)
                      and not waits(record, kept.get(record.id), open_ids)
                      and set_aside(ctx, record.id, kept) is None  # only the active board's tickets, 2026-10-21
                      and not backing_off(backoff.get(record.id), now)]
        # stored rows and live pids alone: a status read inside this transaction would ask every runner from a pool
        # of threads, which crashed on the transaction's connection under concurrent starts (dispatch-concurrency F2)
        rows = [row for row in sessions(store, verify=False)
                if row['state'] != 'running' or runner_of(row.get('pid')) in (row['work_id'], SERVED)]
        active = [row for row in rows if row['state'] == 'running']
        candidates.sort(key=lambda record: (not healing(record), *board_order(record)))  # healing first
        glyph = {work_id: held.get('glyph') for work_id, held in kept.items()}
        occupied = {glyph.get(row['work_id']) for row in active} - {None}
        busy = {row['work_id'] for row in active}
        taken = [record for record in open_work
                 if record.taken and (record.taken_by or '').startswith('dispatch starting ')]
        # A reservation whose runner never made its session and runs no more is a start that died: it goes back to the
        # queue, so a crashed start never holds its ticket for good. One whose runner is still starting is left.
        launching = {entry.get('work_id') for entry in launches() if entry.get('project') == store.project_id}
        stale = [record for record in taken if record.id not in busy and record.id not in launching
                 and time.time() - _seconds(record.taken) > STALE_START]
        for record in stale:
            store.move_work(record.id, 'backlog' if record.held else 'todo', kept=True)
        taken = [record for record in taken if record not in stale]
        occupied.update(glyph.get(record.id) for record in taken)
        # the system is healing a fault of its own: no other ticket starts until that ticket is done
        mending = any(healing(record) for record in open_work if record.id in busy or record in taken)
        # The slots as the gate counts them, the runners that run now in the project and on the machine, less the
        # reservations another pass made that have not started their runner yet, so two passes at once reserve one
        # slot once; the gate counts again at each start, so a start reserved past them gives its ticket back.
        held_slots = slots(ctx, store)
        capacity = max(0, int(held_slots['free']) - sum(1 for record in taken if record.id not in launching))
        if ctx.nouns.get('batch'):
            capacity = min(capacity, max(1, int(ctx.nouns['batch'])))
        # Helpers, the Facilitator that gives a ticket its specialist among them, have their own room, `HELPERS_MOST`,
        # as the start gate counts them, `capacity_kind`: a full worker queue never keeps a ticket from getting the
        # specialist it needs before it is active (the owner's ruling, 2026-10-20).
        room = max(0, int(held_slots['room']))
        for record in candidates:
            if capacity == 0 and room == 0:
                break
            helper = capacity_kind(ctx, record.id, 'worker') == 'helper'
            if (room if helper else capacity) == 0:
                continue
            if mending and not healing(record):
                continue  # work waits while the system heals itself
            mark = glyph.get(record.id)
            if mark is not None and mark in occupied:
                continue
            # A marker waits behind a ticket held or taken at its node, and its node starts one marker at a time,
            # MAP-046's amendment of 2026-10-14.
            if record.condition in MARKERS and (
                    any(other.id != record.id and one_node(record, other) and (
                        (other.taken and other not in stale) or other.held or kept.get(other.id, {}).get('hold'))
                        for other in opened)
                    or any(one_node(record, other) for other, _, _ in reserved if other.condition in MARKERS)):
                continue
            raw: Any = kept.get(record.id, {}).get('eligible', [])
            if not isinstance(raw, list) or any(not isinstance(agent, str) for agent in cast(list[Any], raw)):
                continue  # unreadable eligibility is refused, as by the individual start check
            agents = cast(list[str], raw)
            chosen = preferred(record, kept.get(record.id), default, store=store)  # the ticket's own choice, else its area
            healer = str(ctx.setting('dispatch_healing_agent') or AGENT_DEFAULT) if healing(record) else AGENT_DEFAULT
            if healer != AGENT_DEFAULT and not kept.get(record.id, {}).get('agent'):
                chosen = healer  # the agent chosen for healing, over the area's; the ticket's own still wins
            try:
                agent = agent_named(chosen if not agents or chosen in agents else agents[0])
            except Stop:
                continue
            if agent not in failing:
                failing[agent] = failing_agent(ctx, store.project_id, agent) is not None
            if failing[agent]:  # it failed on ticket after ticket: the person starts it again, or changes its command
                continue
            # what `startable` checks that the reads above have not: the agent is installed, no claim holds the
            # ticket's part of the map, and no session runs on it
            if (found_command(ctx, agent) is None or record.id in busy
                    or claimed(store, record.address or record.receiver_address, record.id) is not None):
                continue
            if over_budget(ctx, store, work_id=record.id) is not None:  # its own budget spent, M01
                continue
            if rework_blocked(ctx, store, record):
                continue
            reservation = 'dispatch starting ' + secrets.token_hex(16)
            if not (record.task or '').strip():  # a marker with no task, from the person or a critic
                store.edit_work(record.id, {'task': marker_task(record)})
            store.take_work(record.id, by=reservation)
            reserved.append((record, agent, reservation))
            if helper:
                room -= 1
            else:
                capacity -= 1
            if mark:
                occupied.add(mark)
            if healing(record):
                mending = True  # the rest of this pass starts no other work either
    for record in stale:
        publish(ctx, 'not-smooth', work_id=record.id, key=record.taken_by or '', reason='startup reservation expired')
        publish(ctx, 'requeue', work_id=record.id, key=record.taken_by or '', reason='startup reservation expired')
    started: list[dict[str, Any]] = []
    failed: OSError | None = None
    refused: Stop | None = None
    for record, agent, reservation in reserved:
        if refused is not None:  # the gate found the slots full: the rest go back to wait, untried
            given_back_reservation(store, record.id, reservation)
            continue
        try:
            given: dict[str, str] = {}
            level = str(ctx.setting('dispatch_healing_effort') or '').strip() if healing(record) else ''
            if level and not ticket_options(store, record.id).get('thought_level'):
                given['thought_level'] = level  # a saved ticket choice still wins
            started.append(run_reserved(context('dispatch', ctx.folder, project=ctx.project,
                                         nouns={'id': record.id, 'agent': agent,
                                                **({'chosen': json.dumps(given)} if given else {})}), reservation,
                                        asked=asked, auto=True))
        except Stop as error:  # its ticket is given back by the gate
            refused = error
        except OSError as error:  # its ticket is given back; the others still start
            failed = failed or error
    if failed is not None:
        raise failed
    return {'started': started, 'recovery': recovered, 'capacity_waiting': bool(candidates),
            'more': bool(ctx.nouns.get('batch') and started and len(candidates) > len(reserved)), **retried, **paused}


def board_order(record: WorkRecord) -> tuple[bool, bool, int]:
    """Where a ticket stands in the board's order, the order the agent starter takes tickets in."""
    return record.held, record.position is None, record.position or 0


def resume_paused(ctx: Context, store: Store, opened: Sequence[WorkRecord]) -> dict[str, Any]:
    """The work the person's Stop all paused, resumed in place now that Full Auto is on again, VIEW-042: Stop all
    turns Full Auto off and lists each assignment it stopped in the project's halt, `keep_paused`, so the first pass
    of the agent starter after the person turns Full Auto on is their word to go again. Each is resumed as their own
    restart resumes it, `reopen`, keeping its session and its work so far, in the board's order and only as many as
    the agent slots have room for; the rest stay listed for the passes the next free slot brings. Work restarted,
    stopped on its own, done or gone since is dropped from the list, never resumed: a stop the person gave one ticket
    lasts until they restart it. Costs the one read of the halt when nothing is paused. Found 2026-10-19: after Stop
    all on the machine, Full Auto turned on again started none of the 16 assignments it had stopped."""
    entry = _read_json(halt_path(store.project_id))
    listed = [str(one) for one in cast(list[Any], (entry or {}).get('paused') or [])]
    if entry is None or not listed:
        return {}
    from .orchestration import drain, service
    owner = service(ctx)
    if owner is None:
        return {}
    rank = {record.id: place for place, record in enumerate(sorted(opened, key=board_order))}
    room = free_slots(ctx, store)
    kept: list[str] = []
    resumed: list[str] = []
    for work_id in sorted((one for one in listed if one in rank), key=rank.__getitem__):
        held = owner.assignment(ctx, work_id=work_id)
        if held is None or not cast(dict[str, Any], held.get('stop') or {}).get('every'):
            continue
        if room <= 0:
            kept.append(work_id)
            continue
        try:
            owner.reopen(ctx, work_id, queue=True)
        except Stop:
            continue
        resumed.append(work_id)
        room -= 1
    keep_paused(store.project_id, entry, kept)
    if resumed:
        drain(ctx, resumed)  # their launches, through the gate; one the gate refuses waits queued for the next drain
    return {'resumed': resumed, **({'paused_waiting': kept} if kept else {})}


# How a session ends that the person ended, or that ended with its work: never retried, P012. A runner ended with
# SIGTERM is counted as stopped, since nothing in Metaform sends it: the person or their system did.
PERSON_ENDS = ('stopped by the person', 'cancelled by the person', 'the ticket is done', 'the runner was terminated')


def left_waiting(store: Store, opened: Sequence[WorkRecord], rows: Sequence[dict[str, Any]]) -> set[str]:
    """The open tickets still taken by a session that ended and that nothing starts again: the person ended it, or the
    supervisor handed it to them, `retry`. A ticket holds an agent slot only while its agent is alive or something
    will start it again; these wait for the person, so they hold none. One the supervisor will still resume keeps its
    slot, as does one whose runner died, which `settle` writes as ended for the supervisor. Found 2026-10-15: four
    tickets the person had stopped held four of five slots, so with no agent at work every resume was refused."""
    latest = {(row['work_id'], row['session_id']): row for row in rows}
    with own_store(store).tables(write=False) as tx:
        handed = {(row['work_id'], row['session_id']) for row in tx.rows('session_attempts', limit=0).results if row['handed']}
    waiting: set[str] = set()
    for record in opened:
        if not record.taken or record.done:
            continue
        session_id = (record.taken_by or '').partition(' ')[2]
        row = latest.get((record.id, session_id))
        if row is None or row['state'] != 'ended':
            continue
        if stop_end(str(row.get('how') or '')) or (record.id, session_id) in handed:
            waiting.add(record.id)
    return waiting


def retry(ctx: Context, store: Store, opened: Sequence[WorkRecord] | None = None,
          asked: int | None = None) -> dict[str, Any]:
    """The supervisor, P012: a worker's session that ended without the person's stop, its ticket still open and still
    its own, is resumed in place, so the agent keeps its memory of the work, after RETRY_SECONDS, doubled for
    each retry before it, up to dispatch_retries times; then, or when its agent can neither resume nor load, it is
    handed to the person with a handed-over signal. Never a session the person stopped. Returns the sessions resumed
    and, while one waits, the time the next is due, so the runner that saw its session end can come back for it.

    A retry is a start like any other: it resumes no more sessions than the agent slots have room for, the oldest end
    first, and the rest wait, their count and their time unchanged, for the next pass a runner's end or a session
    change brings, `waiting`. UX review round 1, 2026-10-17 (interrupt-failure-recovery F1, settings-govern-behavior
    F1, runaway-and-load F1, orchestrator-system-agent F3): after a crash every dead session was resumed in the same
    pass, whatever dispatch_agents said, so a crash with 46 agents would bring 46 back at once."""
    from .signals import publish
    limit, wait = int(ctx.setting('dispatch_retries')), float(RETRY_SECONDS)
    rows = sessions(store, verify=False)
    latest = {(row['work_id'], row['session_id']): row for row in rows}
    resumed: list[dict[str, Any]] = []
    waiting: list[str] = []
    due: float | None = None
    room: int | None = None  # counted once, at the first session due, then spent as each resumes
    with own_store(store).tables(write=False) as tx:
        ended_at = {row['work_id']: row['seq'] for row in tx.rows('session_attempts', limit=0).results}
    choices = agent_choices()  # read once, not once per open ticket: each read is the registry's (runaway F3)
    candidates = [(record, store) for record in (opened if opened is not None
                                                   else store.work(open=True, limit=0).results)]
    # A worker pinned to a metaform no longer active is retried there, with its ticket, as on the active one: only the
    # metaforms that a session which ended by itself names are read (UX review round 2, 2026-10-17, project-scope F7).
    ended_alone = [row for row in latest.values() if row['state'] == 'ended' and not ticketless(row['work_id'])
                   and not stop_end(str(row.get('how') or ''))]
    for at, name in pinned_bases(store, ended_alone):
        if name is not None:
            candidates += [(record, at) for record in at.work(open=True, limit=0).results]
    candidates.sort(key=lambda pair: (ended_at.get(pair[0].id) is None, ended_at.get(pair[0].id) or 0))
    for record, at in candidates:
        agent, _, session_id = (record.taken_by or '').partition(' ')
        row = latest.get((record.id, session_id))
        if agent not in choices or row is None or row['state'] != 'ended' or stop_end(str(row.get('how') or '')):
            continue
        if foreign(row):  # another home's session, in a store copied here: that home's to resume, never this one's
            continue
        if rework_blocked(ctx, at, record):
            continue
        with own_store(store).tables(write=False) as tx:  # read first: a count already kept is not written again
            held = tx.get('session_attempts', {'work_id': record.id})
        if held is None or held['session_id'] != session_id:
            with own_store(store).tables() as tx:
                held = tx.get('session_attempts', {'work_id': record.id})
                if held is not None and held['session_id'] != session_id:  # another session's count is not this one's
                    tx.delete('session_attempts', {'work_id': record.id})
                    held = None
                if held is None:
                    held = tx.insert('session_attempts', {'work_id': record.id, 'session_id': session_id,
                                                          'retries': 0, 'next_at': time.time() + wait,
                                                          'how': row.get('how'), 'seq': time.time_ns()})
        if held['handed']:
            continue
        caps = cast(dict[str, Any], (session_state(store, session_id) or {}).get('capabilities') or {})
        reason = (None if caps.get('resume') or caps.get('load') else 'its agent can neither resume nor load it')
        reason = reason or ('its agent needs a login, which only you can give' if logged_out(store, record.id,
                                                                                            session_id, row) else None)
        reason = reason or (f'it was retried {held["retries"]} times' if held['retries'] >= limit else None)
        if reason is not None:
            with own_store(store).tables() as tx:
                tx.update('session_attempts', {'work_id': record.id}, {'handed': True})
            publish(ctx, 'handed-over', work_id=record.id, session_id=session_id, key=session_id,
                    reason=f'The session stopped ({row.get("how")}) and {reason}.',
                    next=f'metaform dispatch resume {record.id} session={session_id}')
            continue
        if time.time() < float(held['next_at']):
            due = min(due or float(held['next_at']), float(held['next_at']))
            continue
        if over_budget(ctx, at, work_id=record.id) is not None or runnable_or_none(ctx, agent) is None:
            continue
        if room is None:
            room = free_slots(ctx, store)
        if room <= 0:  # it waits for a slot, as a new ticket does; its count and its time stay as they are
            waiting.append(record.id)
            continue
        retries = int(held['retries']) + 1
        with own_store(store).tables() as tx:
            tx.update('session_attempts', {'work_id': record.id},
                      {'retries': retries, 'next_at': time.time() + wait * 2 ** retries, 'how': row.get('how')})
        run = run_of(store, session_id)  # the retry spends against the run it goes on, so the run budget holds, M01
        try:
            started = resume_spawn(at, record.id, agent,
                                   [f'resume={session_id}', 'retry=true', *([f'run={run}'] if run else [])], 'retry',
                                   ctx=ctx, asked=asked, auto=True)
        except Stop:  # the gate found no room after all, another start having taken it: it waits, uncounted
            with own_store(store).tables() as tx:
                tx.update('session_attempts', {'work_id': record.id},
                          {'retries': held['retries'], 'next_at': held['next_at']})
            room = 0
            waiting.append(record.id)
            continue
        room -= 1
        resumed.append({'work_id': record.id, 'agent': agent, 'session_id': session_id, 'retry': retries, **started})
    return {'retried': resumed, **({'retry_waiting': waiting} if waiting else {}),
            **({'retry_due': due} if due is not None else {})}


def logged_out(store: Store, work_id: str, session_id: str, row: dict[str, Any]) -> bool:
    """Whether a session ended with its agent logged out: its login-needed signal still raised, or its end saying it
    needs a login. A retry cannot clear that, so it goes to the person at once."""
    from .signals import rows
    return 'needs a login' in str(row.get('how') or '') or any(
        one['signal'] == 'login-needed' and one.get('session_id') == session_id for one in rows(store, work_id))


# How the person's system agent ends at their own hand: Dismiss in the chat dock, dispatch stop or cancel. A runner
# ended by SIGTERM is not one of them here, unlike a worker's: a machine shutting down sends it too, and an agent the
# person keeps connected comes back after a restart.
SYSTEM_STOPS = ('stopped by the person', 'cancelled by the person')


_ABOUT: dict[tuple[str, str], tuple[Any, Any]] = {}
"""What each session is about and what its agent is, its state line's `about` and `role`, by (project id, session
id): set when the session is made and never changed, so they are read once."""


def system_sessions(store: Store, rows: Sequence[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """The person's system agent's sessions, oldest first, whatever they hang on: the held ticket of this map, one of
    a map cleared or restored since, or the work id of no ticket a conversation with no map hangs on, PROJ-026. Those
    about the system, not the conversations about a node that hang on the same ticket. `rows` are the sessions read
    already."""
    found = list(rows) if rows is not None else sessions(store)
    unknown = [str(row['session_id']) for row in found if (store.project_id, str(row['session_id'])) not in _ABOUT]
    if unknown:
        try:
            with own_store(store).tables(write=False) as tx:
                for session_id in unknown:
                    line = tx.get('session_lines', {'session_id': session_id, 'name': 'state'})
                    try:
                        value: Any = json.loads(str(line['text'])) if line is not None else None
                    except ValueError:
                        value = None
                    if isinstance(value, dict):  # a session with no state yet is read again next time
                        state = cast(dict[str, Any], value)
                        _ABOUT[(store.project_id, session_id)] = (state.get('about'), state.get('role'))
        except StoreError:
            pass
    tickets: dict[str, WorkRecord | None] = {}

    def mine(row: dict[str, Any]) -> bool:
        about, role = _ABOUT.get((store.project_id, str(row['session_id'])), (None, None))
        work_id = str(row['work_id'])
        if about != 'system' or intake_id(work_id):
            return False
        if role:  # recorded since version 17
            return role == 'system'
        # Before it, an intake and a sentinel were about the system too: the system agent's hang on its held ticket,
        # or on one this map no longer holds, the map it was made on having been cleared.
        if work_id not in tickets:
            tickets[work_id] = held_ticket(store, work_id)
        record = tickets[work_id]
        return record is None or record.task == SYSTEM_TASK
    return [row for row in found if mine(row)]


def stay_connected(ctx: Context, store: Store, asked: int | None = None) -> dict[str, Any]:
    """dispatch_stay_connected, VIEW-045: the person's system agent kept running, run by every pass of the agent
    starter, which runs as the web GUI starts, as a page opens the project and as dispatch's tables change. With none
    running it is started: the person's last conversation with it resumed in place, as Call does, or a new one. One
    that ended without the person's stop is resumed in place after RETRY_SECONDS, doubled for each retry
    before, up to dispatch_retries, counted in `session_attempts` on the work id it hangs on; then, or at once when
    its agent needs a login, it is handed to the person, who brings it back with Call. One whose agent can neither
    resume nor load starts a new conversation, and the person is told once. It is the one agent the person can always
    summon, so it takes no slot from the agents at work. Returns what it started and, while a retry waits, when it is
    due. While Full Auto is on and something the board needs waits for it, `board`, it is started the same way with
    dispatch_stay_connected off, unless the person stopped it: then what waits is taken by their next Call."""
    kept_on = bool(ctx.setting('dispatch_stay_connected'))
    if not kept_on and not (ctx.setting('dispatch_autostart') and board_waiting(store)):
        return {}
    held = anchor(ctx, store)  # with no map, a work id that is no ticket: the person's agent needs no intake first
    mine = system_sessions(store)
    if not kept_on and mine and str(mine[-1].get('how') or '') in SYSTEM_STOPS \
            and mine[-1]['state'] != 'running':
        return {}  # the person's stop is kept: nothing but their own Call starts it again
    own = own_store(store)
    with own.tables(write=False) as tx:
        kept = tx.get('session_attempts', {'work_id': held})
    now = time.time()
    last = mine[-1] if mine else None
    # a runner that outlived the server that started it, or one started to resume it that has not written its row yet,
    # is running whatever a status read says: it is never resumed again or replaced. Every system session is checked,
    # not only the last: an older conversation's live runner keeps a newer ended one from being resumed beside it.
    # One that does not answer is left too; the person's Call says it is held, and their stop ends it.
    if any(row['state'] == 'running' for row in mine) or holding(store, held, mine) is not None:
        if kept is not None and (kept['handed'] or now >= float(kept['next_at'])):
            with own.tables() as tx:  # it outlived its wait, or the person brought it back: the count starts again
                tx.delete('session_attempts', {'work_id': held})
        return {}
    from .signals import publish
    if last is not None and not last.get('origin'):
        # recorded before sessions kept their origin: it may be another home's in a copied store, so nothing resumes
        # it by itself; the person is told once that their Call resumes it, which stamps it as this home's
        publish(ctx, 'handed-over', work_id=held, session_id=str(last['session_id']), key=str(last['session_id']),
                reason='Your system agent was not reconnected by itself: its conversation was recorded before Metaform '
                       'kept which home started a session. Call resumes it.', next='metaform dispatch system')
        return {'legacy': str(last['session_id']), 'next': 'metaform dispatch system'}
    if last is not None and foreign(last):  # another home's conversation, in a store copied here: neither resumed
        return {}                          # nor replaced by a new one; the person's Call starts one here
    session_id, how = (str(last['session_id']), str(last.get('how') or '')) if last is not None else ('', '')
    limit, wait = int(ctx.setting('dispatch_retries')), float(RETRY_SECONDS)
    if last is None or how in SYSTEM_STOPS:
        # none yet, or the person stopped it and has since turned this on again: it starts as their Call starts it,
        # once for what it finds; a start that never ran waits for their Call
        if kept is not None and kept['session_id'] == session_id and kept['seq']:
            return {}
        with own.tables() as tx:
            tx.delete('session_attempts', {'work_id': held})
            tx.insert('session_attempts', {'work_id': held, 'session_id': session_id, 'retries': 0,
                                           'next_at': now + wait, 'how': how or None, 'seq': time.time_ns()})
        agent = system_agent(ctx)
        try:
            agent = agent_named(agent)
            again = resumed_conversation(ctx, store, held, agent, 'system', asked=asked) \
                if last is not None and ctx.setting('dispatch_resume_chats') else None
            return {'connected': again or converse(ctx, store, held, agent, [], asked=asked, auto=True)}
        except (Stop, OSError) as error:
            return {'connected': {'state': 'failed', 'error': str(error)}}
    agent = str(last['agent'])
    state = session_state(store, session_id) or {}
    caps, cwd = cast(dict[str, Any], state.get('capabilities') or {}), state.get('cwd')
    lost = (f'{agent_label(agent)} can neither resume nor load its conversation' if not (caps.get('resume')
                                                                                         or caps.get('load'))
            else f'the folder it worked in, {cwd}, is gone' if not isinstance(cwd, str) or not os.path.isdir(cwd)
            else f'{agent_label(agent)} is not found on this system' if agent not in agent_choices()
            or found_command(ctx, agent) is None else None)
    retries = 0
    with own.tables() as tx:
        held_count = tx.get('session_attempts', {'work_id': held})
        if held_count is None or held_count['session_id'] != session_id:
            # a new end: a session the supervisor started fresh goes on with its count, any other starts one
            carried = int(held_count['retries']) if held_count is not None and not held_count['handed'] else 0
            tx.delete('session_attempts', {'work_id': held})
            held_count = tx.insert('session_attempts', {'work_id': held, 'session_id': session_id,
                                                        'retries': carried, 'next_at': now + wait * 2 ** carried,
                                                        'how': how, 'seq': 0})
        if held_count['handed']:
            return {}
        if now < float(held_count['next_at']):
            return {'retry_due': float(held_count['next_at'])}
        reason = ('its agent needs a login, which only you can give'
                  if logged_out(store, str(last['work_id']), session_id, last)
                  else f'it was resumed {held_count["retries"]} times' if held_count['retries'] >= limit else None)
        if reason is None:
            retries = int(held_count['retries']) + 1
            tx.update('session_attempts', {'work_id': held}, {'retries': retries,
                                                              'next_at': now + wait * 2 ** retries, 'how': how,
                                                              'seq': time.time_ns()})
        else:
            tx.update('session_attempts', {'work_id': held}, {'handed': True})
    if reason is not None:
        publish(ctx, 'handed-over', work_id=held, session_id=session_id, key=session_id,
                reason=f'Your system agent stopped ({how}) and {reason}.', next='metaform dispatch system')
        return {}
    try:
        if lost is None:  # resumed in place: it keeps its memory and waits for the person's next message
            started = resume_spawn(store, held, agent, [f'resume={session_id}', 'system=true'], 'resume', ctx=ctx,
                                   asked=asked, auto=True, subject='system')
            return {'connected': {'state': 'starting', 'work_id': held, 'agent': agent, 'session_id': session_id,
                                  'retry': retries, **started, 'conversation': True}}
        started = converse(ctx, store, held, agent_named(str(ctx.setting('dispatch_agent'))), [], asked=asked,
                           auto=True)
    except (Stop, OSError) as error:
        return {'connected': {'state': 'failed', 'error': str(error)}}
    # told once: one signal for the conversation that was lost, keyed by its session
    publish(ctx, 'new-conversation', work_id=held, session_id=session_id, key=session_id,
            reason=f'Your system agent stopped ({how}) and {lost}, so a new conversation started; it does not '
                   'remember the last one.')
    return {'connected': {**started, 'retry': retries}}


def run_of(store: Store, session_id: str) -> str | None:
    """The run a session spent against, from its latest row of `spending`; None when it spent nothing yet."""
    try:
        found = spend_rows(store, {'session_id': session_id})
    except StoreError:
        return None
    return str(max(found, key=lambda one: int(one['seq']))['run']) if found else None


def runnable_or_none(ctx: Context, agent: str) -> str | None:
    return found_command(ctx, agent)


def pinned_bases(store: Store, rows: Sequence[dict[str, Any]]) -> list[tuple[Store, str | None]]:
    """The metaforms whose tickets the project's sessions may hold, each with its name when it is not the active one:
    the active one first, then each other the project still holds that a session row names as its runner's, `base`.
    A metaform no session names costs no read."""
    found: list[tuple[Store, str | None]] = [(store, None)]
    active = store.active_base()
    seen: set[str] = {active.id} if active is not None else set()
    for row in rows:
        base = row.get('base')
        if not base or base in seen:
            continue
        seen.add(str(base))
        held = home.base_by_id(store.project_id, str(base))
        if held is not None:
            found.append((Store(store.project_id, base=held.id, module=store.module), held.name))
    return found


def recover(ctx: Context) -> dict[str, Any]:
    from .recovery import recover as recovering
    return recovering(ctx)


def reset(ctx: Context) -> dict[str, Any]:
    """Put the agent bookkeeping back in order after crashes: every session recorded as running whose runner is gone is
    recorded as ended, and what its runner left running, its agent's processes and its terminals, is ended first;
    every ticket taken with no live agent behind it goes back to the queue. Live agents and their tickets are left
    alone, and so is a ticket whose agent the person stopped, or the supervisor handed to them, which waits for them
    as before, `kept_for_you`; a ticket whose leftover processes cannot be verified ended stays taken, `deferred`; a
    ticket with a submitted result closes independently of delivery.
    Nothing is deleted. UX review round 1, 2026-10-17: reset released the tickets the person had stopped, which
    autostart then started again (web-gui-controls F7), and left a dead runner's agent's children running while a new
    agent took its ticket (interrupt-failure-recovery F3, dispatch-concurrency F6)."""
    from .recovery import swept
    store = ctx.require_store()
    own = Store(store.project_id, module='dispatch')
    alive = {row['work_id'] for row in sessions(store) if row['state'] == 'running'}  # verified against the runner
    with own.tables(write=False) as tx:
        stored = [dict(row) for row in tx.rows('agent_sessions', limit=0).results]
    recorded = [row for row in stored if row['state'] == 'running']
    takers = {(record.id, (record.taken_by or '').partition(' ')[2])
              for record in store.work(open=True, limit=0).results if record.taken}
    deferred: list[dict[str, str]] = []
    unswept: set[str] = set()
    for row in stored:  # what each dead runner left running is ended before its ticket moves
        raw: Any = row.get('recovery')
        held = cast(dict[str, Any], raw) if isinstance(raw, dict) else None
        if held is None or row['work_id'] in alive or foreign(row) or held.get('session_id') != row['session_id'] \
                or row['state'] != 'running' and (row['work_id'], row['session_id']) not in takers:
            continue
        try:
            swept(held)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            if row['state'] == 'running' or not stop_end(str(row.get('how') or '')):
                unswept.add(str(row['work_id']))
                deferred.append({'work_id': str(row['work_id']), 'reason': str(error),
                                 'next': f'metaform map work op=move id={row["work_id"]} column=todo'})
    ended: list[str] = []
    for row in recorded:
        if row['work_id'] not in alive:
            # its ticket is in the metaform its runner was pinned to, whichever is active now (UX review round 2,
            # 2026-10-17, project-scope F7)
            at = base_store(own, row)
            record = held_ticket(at, row['work_id'])  # a session on no ticket of this map ends with no map write
            with at.atomic() if record is not None else contextlib.nullcontext():
                with at.tables() as tx:
                    latest = tx.get('agent_sessions', {'session_id': row['session_id']})
                    if latest != row:
                        continue
                    tx.update('agent_sessions', {'session_id': row['session_id']},
                              {'state': 'ended', 'how': 'its runner was gone; ended by dispatch reset',
                               'ended': home.now()})
                if record is not None:
                    from .progress import finish
                    finish(at, row['work_id'], str(row.get('runner') or ''),
                           'its runner was gone; ended by dispatch reset')
            ended.append(row['work_id'])
            from .progress import refresh
            if record is not None:
                refresh(ctx, at, record)
            from .signals import clear_permissions, publish
            clear_permissions(ctx, row['session_id'])
            publish(ctx, 'not-smooth', work_id=row['work_id'], session_id=row['session_id'],
                    reason='its runner was gone; ended by dispatch reset')
    released: list[str] = []
    elsewhere: dict[str, str] = {}  # each ticket released or kept on a metaform not active now, with its name
    every = sessions(store, verify=False)
    launching = {entry.get('work_id') for entry in launches() if entry.get('project') == store.project_id}
    kept: list[str] = []
    for at, name in pinned_bases(store, every):
        opened = at.work(open=True, limit=0).results
        yours = left_waiting(at, opened, every)
        for record in opened:
            if record.taken and record.id not in alive and work_over(at, record):
                at.complete_delivery(record.id)
            elif record.taken and record.id not in alive and record.id not in yours and record.id not in unswept \
                    and record.id not in launching:
                at.move_work(record.id, 'backlog' if record.held else 'todo', kept=True)
                released.append(record.id)
                from .signals import publish
                publish(ctx, 'requeue', work_id=record.id, key=record.taken_by or '', reason='dispatch reset')
            elif record.id in yours and record.id not in alive:
                kept.append(record.id)
            else:
                continue
            if name is not None:
                elsewhere[record.id] = name
    return {'released': released, 'sessions_ended': ended, 'still_working': sorted(alive),
            'kept_for_you': sorted(kept), 'deferred': deferred,
            **({'on_bases': elsewhere} if elsewhere else {})}


def merges(ctx: Context) -> dict[str, Any]:
    """The merges waiting for review, VIEW-044, the soonest first."""
    from .merge import due
    return {'merges': due(ctx.require_store())}


def review(ctx: Context) -> dict[str, Any]:
    """Retain the person's ownership of a candidate's explicit review, VIEW-044."""
    from .merge import review as taking
    if not taking(ctx.require_store(), str(ctx.nouns['id'])):
        raise Stop(f'No merge of work {ctx.nouns["id"]} is waiting for review.', 'metaform dispatch merges')
    return {'work_id': ctx.nouns['id'], 'state': 'review'}


def merge(ctx: Context) -> dict[str, Any]:
    """Integrate locally, publishing only when explicitly requested, VIEW-044."""
    from .merge import merge_due
    return merge_due(ctx, ctx.require_store(), str(ctx.nouns['id']), publish=bool(ctx.nouns.get('publish')))


def _running_or_stop(store: Store, work_id: str, session_id: str | None = None, *,
                     gone_ok: bool = False) -> dict[str, Any]:
    """The running session a steer or a stop reaches. With `gone_ok`, a stop's, a session the store holds as running
    whose runner is gone is returned marked `gone`, so the stop says it had ended already rather than failing
    (intake-single-flight F1: Stop on a dead intake answered 400 and the bar stayed)."""
    # Stop and message must still reach older runners and runners finishing a completed ticket, and an intake agent
    # whatever metaform has become active since it began.
    held = (intake_store(store, work_id) or store) if intake_id(work_id) else store
    found = [row for row in sessions(held, work_id, verify=False) if row.get('state') == 'running']
    if session_id:
        # One session of several on a ticket, as editor sessions share theirs, BASE-062: that one, checked live, so a
        # row a killed process left is never taken for it.
        # One whose pid runs this ticket is reached even unanswering, as below, so the stop a held session names works.
        chosen = next((row for row in found if row['session_id'] == session_id), None)
        if chosen is not None and gone_ok and runner_of(chosen.get('pid')) != work_id \
                and session_status(own_store(held), chosen, done=False)['state'] != 'running':
            return {**chosen, 'gone': True}
        if chosen is None or session_status(own_store(held), chosen, done=False)['state'] != 'running' \
                and runner_of(chosen.get('pid')) != work_id:
            raise Stop('The chat session is no longer the running session on this ticket.',
                       f'metaform dispatch sessions id={work_id}')
        return chosen
    # The latest session that is running still, BASE-062: a row a killed process left is passed over for a live one
    # before it, as editor sessions share their ticket; one whose pid runs this ticket is reached even unanswering.
    session = next((row for row in reversed(found)
                    if session_status(own_store(held), row, done=False)['state'] == 'running'), None)
    if session is None:
        session = next((row for row in reversed(found) if runner_of(row.get('pid')) == work_id), None)
    if session is None and gone_ok and found:
        return {**found[-1], 'gone': True}
    if session is None and gone_ok:  # its death written already, by the watch that heard it: the stop says so
        latest = sessions(held, work_id, verify=False)
        if latest and latest[-1]['state'] == 'ended' and str(latest[-1].get('how') or '') in DIED:
            return {**latest[-1], 'gone': True}
    if session is None:
        # an intake is no ticket: what starts one again is `dispatch intake`, never a start on its work id
        raise Stop(f'No agent is running on work {work_id}.', 'metaform dispatch intake' if intake_id(work_id)
                   else f'metaform dispatch sessions id={work_id}' if helper_id(work_id)
                   else f'metaform dispatch start {work_id} <agent>')
    return session


def _told(row: dict[str, Any], op: str, **given: Any) -> dict[str, Any]:
    """`tell`, with a session that stopped listening between the read and the request said as a Stop."""
    try:
        return tell(row, op, **given)
    except OSError as error:
        raise unanswered(row, error) from None


def unanswered(row: dict[str, Any], error: OSError) -> Stop:
    """A session that did not answer a request: one whose live runner still holds it, such as a runner under load, is
    held, said with the runner's pid and the stop that ends it; the person cannot otherwise reach it."""
    session_id, work_id, pid = row['session_id'], row['work_id'], row.get('pid')
    if runner_of(pid) == work_id:
        return Stop(f'Session {session_id} of work {work_id} is held by its runner, process {pid}, which is alive '
                    f'but did not answer: {error}.', f'metaform dispatch stop {work_id} session={session_id}')
    return Stop(f'Session {session_id} of work {work_id} did not answer: {error}.',
                f'metaform dispatch sessions id={work_id}')


def editor(row: dict[str, Any]) -> bool:
    """A session an editor runs through `dispatch serve`, BASE-062: shown and steered on the page, and never one of
    the agents dispatch counts against `dispatch_agents`, since the person started it in their editor."""
    return runner_of(row.get('pid')) == SERVED


def may_steer(ctx: Context) -> None:
    """Honor the person's configured operational-role restrictions, BASE-052 and MAP-050.

    Authored swarm responsibilities do not override this dynamic blacklist. Ordinary peer delivery uses its own
    public note path; GC ownership is additionally checked before an agent broadcasts or interrupts a member.
    """
    if person_asks(ctx):
        return
    role = held_role(ctx)
    if role is not None:
        raise Stop(f'The configured roles_without_authority holds back {role} agents from directing agents. '
                   'Record the requested contribution and context for your GC.',
                   'metaform map work op=edit id=<your work id> note="..."')


def sender(ctx: Context) -> str | None:
    """The role of the agent a message comes from, None for the person: on the page always the person, elsewhere the
    role the runner gave the calling agent, BASE-052."""
    from metaform.module import page_vouched
    if ctx.surface == 'cli' and page_vouched():
        return None
    return (os.environ.get('METAFORM_ROLE') or ('agent' if os.environ.get('METAFORM_SESSION') else None)) \
        if ctx.surface in ('mcp', 'cli') else None


def start(ctx: Context) -> dict[str, Any]:
    """Start the runner for one ticket as a process detached from the terminal, and return at once. A dispatched
    agent starts one only in a turn of the person's own system agent that the person's message started, and the
    start is recorded in its chat with that message, `on_persons_word`."""
    may_steer(ctx)
    store = ctx.require_store()
    agent, work_id = agent_named(ctx.nouns['agent']), ctx.nouns['id']
    # one Start all run: every start of it is asked for when the run was first seen, so a halt in the middle of the
    # run refuses the rest of it (ux-verify-combined F1)
    asked = batch_asked(str(ctx.nouns['batch'])) if ctx.nouns.get('batch') else time.time_ns()
    word = on_persons_word(ctx, f'Starting an agent on ticket {work_id}', [str(work_id)])
    automatic = not persons_start(ctx, word)
    if not automatic:
        runnable(ctx, agent)
    folder = store.project().path
    mcp_server(Path(folder))  # a server the runner could not choose is refused here, the ticket left in To do, BASE-052
    budget_stop(ctx, store, str(work_id))  # a reached token budget is the person's to raise, M01
    from .orchestration import service
    owner = service(ctx)
    if owner is not None:
        runtime = runtime_settings(ctx, str(work_id))
        if not automatic and runtime.get('agent') != agent:
            edit_runtime(ctx, str(work_id), {'agent': agent})
        record = ticket(store, str(work_id))
        if not automatic and record.held and not record.taken:
            startable(ctx, store, record, agent)
            admit(ctx, store, str(work_id), 'worker', asked=asked, agent=agent, auto=False)
            store.move_work(str(work_id), 'todo', kept=True)
        selected = owner.route(ctx, str(work_id))
        held = owner.assignment(ctx, work_id=str(work_id))
        if not automatic and held is not None:
            # Admission precedes persistent personal launch authority, including required fallback descendants.
            admit(ctx, store, str(work_id), 'worker', asked=asked, agent=agent, auto=False)
            owner.reopen(ctx, str(work_id))
            held = owner.ensure(ctx, str(work_id), persons=True)
        if not selected.get('role'):
            return {'state': 'needs_specialist', 'work_id': work_id, 'reason': selected.get('reason')}
        if held is None and selected.get('role'):
            held = owner.ensure(ctx, str(work_id), role=str(selected['role']), persons=not automatic)
        if held is not None and not owner.prepare_runtime(ctx, held):
            return {'state': 'queued', 'work_id': work_id, 'reason': 'The Facilitator is preparing the ticket runtime.'}
        runtime = runtime_settings(ctx, str(work_id))
        agent = agent_named(str(runtime.get('agent') or agent))
        ctx.nouns['agent'] = agent
    command = argv(start_command(ctx, agent))
    if shutil.which(command[0]) is None:
        raise Stop(f'{command[0]}, the start command of {agent}, is not found on this system.',
                   f'metaform set --dispatch-{agent} "<command>"')
    given, notices = launch_permissions(ctx, store, agent)
    reservation = 'dispatch starting ' + secrets.token_hex(16)
    # Admission can carry legacy spend across stores. The spawn gate repeats it under its own capacity lock.
    admit(ctx, store, str(work_id), 'worker', asked=asked, agent=agent, auto=automatic)
    record = ticket(store, str(work_id))
    checked_sessions = sessions(store, record.id if glyph_of(ctx, record) is None else None)
    with store.atomic():
        record = ticket(store, work_id)
        if not automatic and record.taken and record.taken_by == f'Specialist {work_id}':
            # the sessionless specialist owner holds a ticket while its role is made; the person's own start takes
            # it over now, and the role follows when it is published (2026-10-20: their Start was refused as taken)
            store.move_work(str(work_id), 'backlog' if record.held else 'todo', kept=True)
            record = ticket(store, work_id)
        startable(ctx, store, record, agent, checked_sessions=checked_sessions)
        if not automatic and owner is not None:
            owner.reopen(ctx, str(work_id))
        store.take_work(work_id, by=reservation)
    started = run_reserved(ctx, reservation, given, asked=asked, auto=automatic)
    return {**started, **{field: value for field, value in given.items() if value},
            **({'notices': notices} if notices else {}),
            **on_word(ctx, word, f'started {agent_label(agent)} on ticket {ticket_label(store, str(work_id))}',
                      [str(work_id)])}


def run_reserved(ctx: Context, reservation: str, given: dict[str, str | None] | None = None, *,
                 asked: int | None = None, auto: bool = False) -> dict[str, Any]:
    """Start the runner of a ticket reserved for it, as a process detached from the terminal, and return at once; a
    runner that cannot be started gives the ticket back where it waited. `given` is the launch's own permissions; a
    launch without them, autostart's, leaves them to the project's settings."""
    store = ctx.require_store()
    agent, work_id = str(ctx.nouns['agent']), str(ctx.nouns['id'])
    from .orchestration import service
    owner = service(ctx)
    if owner is not None and (held := owner.assignment(ctx, work_id=work_id)) is not None:
        if not auto:
            held = owner.ensure(ctx, work_id, persons=True)
        if not owner.prepare_runtime(ctx, held):
            given_back_reservation(store, work_id, reservation)
            return {'state': 'queued', 'work_id': work_id, 'reason': 'The Facilitator is preparing the ticket runtime.'}
        agent = agent_named(str(runtime_settings(ctx, work_id).get('agent') or agent))
        ctx.nouns['agent'] = agent
    keep_launch(store, work_id, given or {'prompts': None, 'mode': None})
    started = start_runner(ctx, store, work_id, agent,
                           ['reservation=' + reservation,
                            *([f'chosen={ctx.nouns["chosen"]}'] if ctx.nouns.get('chosen') else []),
                            *([] if auto else ['persons=true'])],  # the person's own start: it runs, whatever routing says
                           'work', reservation=reservation, asked=asked, auto=auto)
    return {'state': 'starting', 'work_id': work_id, 'agent': agent, **started}


def prep(ctx: Context) -> dict[str, Any]:
    """Start an agent in a merge's worktree to prepare its code for the person's review, VIEW-044; it takes no ticket
    and stays to talk with the person until stopped. It is an agent the person summons, VIEW-045."""
    store = ctx.require_store()
    work_id = str(ctx.nouns['id'])
    from .merge import worktree_of
    worktree_of(store, work_id)  # refuses a ticket with no merge
    record = ticket(store, work_id)
    kept = work_reads(ctx.folder, record, project=ctx.project).get('map')  # a done ticket's own, as it shows it
    agent = preferred(record, cast(dict[str, Any], kept) if isinstance(kept, dict) else None,
                      str(ctx.setting('dispatch_agent')), store=store)
    if found_command(ctx, agent) is None:
        raise Stop(f'The start command of {agent} is not found on this system.', f'metaform set --dispatch-{agent} "<command>"')
    started = start_runner(ctx, store, work_id, agent, ['prep=true'], 'prep')  # a summoned agent, through the gate
    return {'state': 'starting', 'work_id': work_id, 'agent': agent, **started}


SYSTEM_TASK = 'Conversation with the system agent'  # the ticket that anchors the person's system agent chat; held, so no agent works it


def conversation_id(task: str) -> str:
    """The work id a held ticket's conversations hang on while the map holds no element: the system agent's,
    `conversation-system`, or another held ticket's, by its task's words. It is no ticket."""
    return CONVERSATION + ('system' if task == SYSTEM_TASK else re.sub(r'[^a-z0-9]+', '-', task.lower()).strip('-'))


def anchor(ctx: Context, store: Store, at: str | None = None, task: str = SYSTEM_TASK) -> str:
    """The work id the person's conversations hang on when what they talk about has no ticket of its own: the system
    agent, a node, an ended agent's thread; with `task`, another held ticket of the person's, such as the one the
    sessions an editor runs through `dispatch serve` hang on, BASE-062. It is a held ticket, so no agent works it, made
    at the DE the first time. A map with no element, never made or cleared since, has nowhere to hold one: the
    conversation then hangs on `conversation_id`, which is no ticket, and nothing is written to the map, so the person
    talks with their own agent before any intake, which is offered and never required, VIEW-045."""
    def anchored() -> WorkRecord | None:
        return next((record for record in store.work(open=True, limit=0).results if record.task == task), None)
    found = anchored()
    if found is None:
        roots = store.roots(limit=1)
        root = next((entry.element for entry in roots.entry if entry.element.role == 'DE'), None) \
            or next((entry.element for entry in roots.entry), None) or next(iter(roots.elements), None)
        node = root.address if root is not None else at  # a map with no roles yet: the node talked about holds it
        if node is None:
            return conversation_id(task)
        map_work(ctx, op='add', node=node, task=task, title=task,
                 note='Held for the person\'s conversations with agents; no agent works this ticket.', held=True, hold=True)
        found = anchored()
        if found is None:
            raise Stop('The conversation ticket was not made.', 'metaform map work')
    return found.id


def subject_of(extra: Sequence[str]) -> str:
    """What a summoned agent is about, as its words say: the talk's subject, the sentinel's node, or the system."""
    for word in extra:
        if word.startswith(('talk=', 'sentinel=')):
            return word
    return 'system'


def converse(ctx: Context, store: Store, work_id: str, agent: str, extra: Sequence[str], *,
             asked: int | None = None, auto: bool = False) -> dict[str, Any]:
    """Start a conversation agent on a ticket without taking it: an agent the person summons, one always and more in the
    slots the agents at work leave free, VIEW-045. It never takes, reopens or closes the ticket, and lasts until the person stops it.
    One conversation per subject: a runner already starting or running about it is the answer, the gate's own check
    under its lock, so a double click, two tabs, or the person and an agent at once start one (UX review round 2,
    spawn-gate F2: eight talks at once on one ticket started three agents writing one log)."""
    if any(word.startswith('talk=') for word in extra):
        prompt_written('talk')
    if found_command(ctx, agent) is None:
        raise Stop(f'The start command of {agent} is not found on this system.', f'metaform set --dispatch-{agent} "<command>"')
    started = start_runner(ctx, store, work_id, agent, ['system=true', *extra], 'talk', asked=asked, auto=auto,
                           subject=subject_of(extra))
    return {'state': 'starting', 'work_id': work_id, 'agent': agent, **started, 'session_id': None,
            'conversation': True}


def system(ctx: Context) -> dict[str, Any]:
    """Start the person's system agent, the one agent they may summon besides the agents at work: it talks with them
    about anything in the project, from the project's folder, and stays until stopped. A running one is reused, except
    with `fresh`, /new on My agent: then the running one ends as the person's stop ends it, changing no setting, and a
    new one starts resuming nothing, so /new always gives a new conversation. The person's Call starts the
    supervisor's count of its ends again, `stay_connected`. It needs no map and no intake: with no element on the map
    it talks on a work id that is no ticket, `anchor`, VIEW-045, and their earlier conversation with it is found
    whatever it hangs on, a map cleared, restored or switched for another since among them, PROJ-026."""
    store = ctx.require_store()
    held = anchor(ctx, store)
    forget_ends(store, held)
    everyone = sessions(store)
    theirs = {row['session_id'] for row in system_sessions(store, everyone)}
    found = [row for row in everyone if row['work_id'] == held or row['session_id'] in theirs]
    fresh = bool(ctx.nouns.get('fresh'))
    # running as read, or held by a live runner whatever a status read says, such as one that outlived the server
    # that started it: reused, never resumed a second time. One that does not answer is held: said with its pid and
    # the stop that ends it, since the person cannot talk to it
    live = next((row for row in found if row['state'] == 'running'), None)
    if live is None and (holds := holding(store, held, found)) is not None:
        live, pid = holds
        if silent(live, pid) and not fresh:
            return held_session(live, pid)
    agent = agent_named(str(ctx.nouns.get('agent') or system_agent(ctx))) if live is None or fresh else ''
    if live is not None and fresh:
        if found_command(ctx, agent) is None:  # checked before the running one ends, so a refused start leaves it
            raise Stop(f'The start command of {agent} is not found on this system.',
                       f'metaform set --dispatch-{agent} "<command>"')
        ended = ended_by_person(store, live)
        if ended.get('error'):
            raise Stop(str(ended['error']), f'metaform dispatch sessions id={live["work_id"]}')
        live = None
    active = store.active_base()
    if live and live.get('base'):
        active = next((one for one in home.bases(store.project_id) if one.id == live['base']), active)
    reads = {'base': active.name if active is not None else None}
    if live is not None:
        return {'state': 'running', 'work_id': live['work_id'], 'agent': live['agent'],
                'session_id': live['session_id'], **reads}
    again = resumed_conversation(ctx, store, held, agent, 'system', person=True) \
        if ctx.setting('dispatch_resume_chats') and not fresh else None
    return {**(again or converse(ctx, store, held, agent, [])), **reads}


def forget_ends(store: Store, work_id: str) -> None:
    """The person acted on their system agent: the supervisor's count of its ends, `session_attempts`, starts
    again."""
    own = own_store(store)
    with own.tables(write=False) as tx:  # read first, so a Call with nothing counted writes nothing
        counted = tx.get('session_attempts', {'work_id': work_id}) is not None
    if counted:
        with own.tables() as tx:
            tx.delete('session_attempts', {'work_id': work_id})


def disconnect(ctx: Context, store: Store, row: dict[str, Any]) -> bool:
    """The person stops their system agent, as Dismiss in the chat dock does: dispatch_stay_connected is turned off
    for the project until they turn it on again, so it does not come straight back, VIEW-045. Only the person's own
    stop, on the page or the command line: an agent may stop it, but never changes a setting of the person's. Returns
    whether it was turned off, done before the stop so no pass of the agent starter in between brings it back."""
    if ctx.surface == 'mcp' or sender(ctx) is not None or not ctx.setting('dispatch_stay_connected'):
        return False
    if not system_sessions(store, [row]):  # their system agent, whatever ticket or map it hangs on
        return False
    settings.put('dispatch_stay_connected', False, Path(store.project().path))
    forget_ends(store, str(row['work_id']))
    return True


def resumed_session(ctx: Context, store: Store, row: dict[str, Any], about: str, *,
                    asked: int | None = None) -> dict[str, Any] | None:
    """The very session the person named, ended, resumed in place with its own agent as a conversation, so they can
    ask it what happened: the person speaks to any past context, an intake's included, since without it understanding
    a problem takes deep investigation (the person's rule, 2026-10-20). None when its agent can neither load nor resume
    it, its folder is gone, or another home started it; a new conversation about the thread starts then."""
    kept = session_state(store, str(row['session_id'])) or {}
    caps = cast(dict[str, Any], kept.get('capabilities') or {})
    cwd = kept.get('cwd')
    if not (caps.get('resume') or caps.get('load')) or not isinstance(cwd, str) or not os.path.isdir(cwd) \
            or (foreign(row) and row.get('origin')):
        return None
    agent = str(row['agent'])
    runnable(ctx, agent)
    session_id, work_id = str(row['session_id']), str(row['work_id'])
    extra = [f'resume={session_id}', 'system=true', f'talk={about}']
    started = resume_spawn(store, work_id, agent, extra, 'resume', ctx=ctx, asked=asked, auto=False,
                           subject=subject_of(extra[1:]))
    if started.get('state') == 'running' and silent(row, started.get('pid')):
        return held_session(row, int(started['pid']))
    return {'state': 'starting', 'work_id': work_id, 'agent': agent, 'session_id': session_id, **started,
            'conversation': True}


def resumed_conversation(ctx: Context, store: Store, work_id: str, agent: str, about: str, *,
                         person: bool = False, asked: int | None = None) -> dict[str, Any] | None:
    """The person's last conversation about this with this agent, resumed in place so the agent keeps its memory of it;
    None when there is none, or its agent can neither load nor resume it, or its folder is gone, and a new one starts.
    `person` is the person's own Call or talk: it resumes a conversation recorded before sessions kept their origin,
    which nothing automatic does; one stamped by another home is never resumed here. The system agent's last
    conversation is found whatever it hung on, and is resumed on `work_id`, the one it hangs on now, PROJ-026."""
    for row in reversed(system_sessions(store) if about == 'system' else sessions(store, work_id)):
        kept = session_state(store, str(row['session_id'])) or {}
        if row['state'] == 'running' or kept.get('about') != about or row['agent'] != agent or (
                foreign(row) and not (person and not row.get('origin'))):
            continue
        caps = cast(dict[str, Any], kept.get('capabilities') or {})
        cwd = kept.get('cwd')
        if not (caps.get('resume') or caps.get('load')) or not isinstance(cwd, str) or not os.path.isdir(cwd):
            return None
        runnable(ctx, agent)
        session_id = str(row['session_id'])
        extra = [f'resume={session_id}', 'system=true', *([] if about == 'system' else [f'talk={about}'])]
        started = resume_spawn(store, work_id, agent, extra, 'resume', ctx=ctx, asked=asked, auto=not person,
                               subject=subject_of(extra[1:]))
        if started.get('state') == 'running' and silent(row, started.get('pid')):
            return held_session(row, int(started['pid']))
        return {'state': 'starting', 'work_id': work_id, 'agent': agent, 'session_id': session_id, **started,
                'conversation': True}
    return None


def json_list(value: Any, name: str) -> list[str]:
    """A list argument: a JSON list of text, or one value alone."""
    if isinstance(value, str):
        try:
            value = json.loads(value) if value.strip().startswith('[') else [value]
        except ValueError:
            raise Stop(f'{name} is a JSON list, such as ["code.alarm.audible"].', 'metaform help dispatch') from None
    if not isinstance(value, list) or any(not isinstance(one, str) for one in cast(list[Any], value)):
        raise Stop(f'{name} is a list of text.', 'metaform help dispatch')
    return cast(list[str], value)


def claim_rows(store: Store) -> list[dict[str, Any]]:
    """Every work claim with its nodes, its tickets and its state, LAYER-029: proposed until a ticket of it is taken,
    active from then, and ended when every ticket is done and nothing of it waits to merge."""
    own = Store(store.project_id, module='dispatch')
    with own.tables(write=False) as tx:
        claims = [dict(row) for row in tx.rows('claims', by=('seq',), limit=0).results]
        members = [dict(row) for row in tx.rows('claim_work', limit=0).results]
    with own.tables(write=False) as tx:  # merges are in the project's store, a transaction of their own, STORE-006
        waiting = {row['work_id'] for row in tx.rows('merges', limit=0).results
                   if row['state'] not in ('committed', 'merged')}
    for claim in claims:
        claim['nodes'] = json.loads(claim['nodes'])
        claim['work'] = [row['work_id'] for row in members if row['claim_id'] == claim['claim_id']]
        held: list[WorkRecord] = []
        for work_id in claim['work']:
            try:
                held.append(store.ticket(work_id).work)
            except StoreError:
                continue
        started = any(record.taken or record.done for record in held)
        landed = bool(held) and all(record.done and record.id not in waiting for record in held)
        claim['state'] = 'ended' if started and landed else 'active' if started else 'proposed'
    return claims


def claimed(store: Store, address: str | None, work_id: str | None = None) -> dict[str, Any] | None:
    """The active claim reserving an address that the work is not part of, or None."""
    if not address:
        return None
    found = [claim for claim in claim_rows(store) if claim['state'] == 'active' and address in claim['nodes']
             and work_id not in claim['work']]
    if work_id and found:
        from .orchestration import service
        ctx = runner_context(store)
        owner = service(ctx)
        if owner is not None:
            found = [claim for claim in found if not any(owner.same_team(ctx, work_id, str(other))
                                                        for other in claim['work'])]
    return next(iter(found), None)


def in_use(store: Store, node: str) -> list[str]:
    """What is using a node: the tickets in motion on it, taken by an agent and not done, and any active work claim
    that reserves it, LAYER-029."""
    using = [record.id for record in store.work(open=True, limit=0).results if record.taken and not record.done
             and node in (record.address, record.receiver_address, record.provider_address)]
    found = claimed(store, node)
    return using + ([f'claim {found["name"]}'] if found else [])


# ------------------------------------------------------------------ the one admission gate
# Every agent Metaform starts is a `dispatch run` runner, and every runner is started through `start_runner`, the one
# place an agent process is spawned: Start, Start all, autostart, /new, a chat, the system agent, a sentinel, an
# intake, a merge preparation, a resume, the supervisor's retry and a runner handing its session over. The gate counts
# the runners that run now, in the home's ledger, and refuses past the project's dispatch_agents, the machine's
# dispatch_machine_agents across every project of the home, or a reached day's budget; the count, the start and the
# ledger entry are one lock between processes, so two starts at once never take one slot. A runner started any other
# way, by hand or by a process on older code, admits itself at its start, `admit_self`, before any agent runs. UX
# review round 1, 2026-10-17 (forensic cause 3, dispatch-concurrency F2 F3 F4 F7, settings-govern-behavior F1 F4,
# runaway-and-load F1 F2, orchestrator-system-agent F3): each start path checked its own count, or none, so a crash
# recovery, a burst of chats or two projects ran past the limit, and the count itself crashed under concurrent starts.
SUMMONS = ('question=', 'prep=', 'system=')  # the words of a runner the person summons, as `summoned` reads them


def ledger() -> Path:
    """The home's ledger of runners started through the gate: one private file for each, named by its pid."""
    return home.home() / 'run' / 'dispatch' / 'agents'


def _runs(pid: int, born: str) -> bool:
    """Whether the process `pid` is still the one born `born`, and not a zombie waiting for its parent; one that cannot
    be inspected counts as running, so the gate never takes it for gone."""
    from .recovery import identity
    now = identity(pid)
    if now is None:
        return True
    if not now or now != born:
        return False
    if sys.platform.startswith('linux'):
        try:
            return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0] != 'Z'
        except (OSError, IndexError):
            return False
    return True


def launches() -> list[dict[str, Any]]:
    """The runners of every project of this home that the gate started and that still run; an entry whose runner has
    ended is removed as it is read, so the ledger needs no sweep of its own."""
    found: list[dict[str, Any]] = []
    try:
        paths = sorted(ledger().glob('*.json'))
    except OSError:
        return found
    for path in paths:
        try:
            raw: Any = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        entry = cast(dict[str, Any], raw) if isinstance(raw, dict) else {}
        pid, born = entry.get('pid'), entry.get('born')
        if not isinstance(pid, int) or not isinstance(born, str) or not _runs(pid, born):
            with contextlib.suppress(OSError):
                path.unlink()
            continue
        subject = str(entry.get('subject') or '')
        if subject.startswith('sentinel='):
            entry['kind'] = 'sentinel'
        elif subject == 'system':
            entry['kind'] = 'advisor'
        found.append(entry)
    return found


def primary_advisor(words: Sequence[str]) -> bool:
    """The user's triage has its own admission, independently of its pinned project/base."""
    return 'system=true' in words and not any(word.startswith(('talk=', 'sentinel=', 'intake=', 'prep='))
                                             for word in words)


def launch_kind(words: Sequence[str]) -> str:
    """Sentinels and the person's advisor have independent admission; other chats are summoned, tickets workers."""
    if any(word.startswith('sentinel=') for word in words):
        return 'sentinel'
    if primary_advisor(words):
        return 'advisor'
    return 'summoned' if any(word.startswith(SUMMONS) for word in words) else 'worker'


def capacity_kind(ctx: Context, work_id: str, kind: str) -> str:
    """Only recorded role-creation assignments and the helpers the system agent starts, `helper`, are exempt helpers;
    ordinary delegated work consumes slots. dispatch_agents bounds what Full Auto starts by itself, and a helper is
    started on purpose, to get round a full queue when it has to (the owner's ruling, 2026-10-19)."""
    if ctx.nouns.get('sentinel'):
        return 'sentinel'
    if ctx.nouns.get('system') and not any(ctx.nouns.get(key) for key in ('talk', 'intake', 'prep')):
        return 'advisor'
    if helper_id(work_id):
        return 'helper'
    if kind != 'worker':
        return kind
    from .orchestration import assignment
    held = assignment(ctx, work_id)
    return 'helper' if held and held['authored_role_uri'] in (
        'metaform://role/facilitator', 'metaform://role/role_creator') else kind


HELPERS_MOST = 8  # separate bounded helper capacity; the deduplicated user advisor remains reachable


def slots(ctx: Context, store: Store, *, besides: int | None = None) -> dict[str, Any]:
    """Project and machine worker capacity, plus the project's independent temporary helper bound.

    Sentinels and triage have separate admission. Unledgered runners count from verified live session rows.
    `besides` excludes the runner handing over or admitting itself. `room` is the remaining helper capacity.
    """
    entries = [entry for entry in launches() if entry['pid'] != besides]
    known = {entry['pid'] for entry in entries}
    own = [entry for entry in entries if entry.get('project') == store.project_id]
    for row in sessions(store, verify=False):
        pid = row.get('pid')
        if row['state'] == 'running' and isinstance(pid, int) and pid not in known and pid != besides \
                and runner_of(pid) == row['work_id']:
            known.add(pid)
            unledgered = {'pid': pid, 'project': store.project_id, 'work_id': row['work_id'],
                          'kind': 'helper' if helper_id(row['work_id']) else launch_kind(command_line(pid))}
            own.append(unledgered)
            entries.append(unledgered)
    workers = [entry for entry in own if entry.get('kind') == 'worker']
    called = [entry for entry in own if entry.get('kind') not in ('worker', 'sentinel', 'advisor')]
    limit, most = int(ctx.setting('dispatch_agents')), int(ctx.setting('dispatch_machine_agents'))
    used = len(workers)
    machine_used = sum(entry.get('kind') == 'worker' for entry in entries)
    machine_free = max(0, most - machine_used)
    return {'limit': limit, 'used': used, 'workers': len(workers), 'summoned': len(called),
            'free': min(max(0, limit - used), machine_free),
            'room': max(0, HELPERS_MOST - len(called)), 'own_room': 1,
            'machine_limit': most, 'machine_used': machine_used, 'machine_free': machine_free,
            'helpers': len(called), 'helper_limit': HELPERS_MOST,
            'projects': len({entry.get('project') for entry in entries}),
            'holding': [str(entry.get('work_id')) for entry in workers]}


def launch_holds(store: Store, row: dict[str, Any]) -> bool:
    """Whether a launch whose session is not made yet still holds its slot: an intake's for as long as its runner lives,
    `intake_under_way`, however long its agent takes to start; a sentinel's for STALE_START."""
    if intake_id(row['work_id']):
        busy = intake_under_way(store)
        return busy is not None and busy['work_id'] == row['work_id']
    return time.time() - row['started'] < STALE_START


def free_slots(ctx: Context, store: Store) -> int:
    """How many more tickets may start now, as the gate counts, `slots`. Found 2026-10-16: Start all on the board
    started every ticket it offered, 46 with six slots, since only autostart counted."""
    return int(slots(ctx, store)['free'])


class Refused(Stop):
    """A start the gate refused: no slot, the budget, a halt or an agent that keeps failing. It is no failure of the
    agent's, so it counts toward no retry, `start_failed`."""


def _agents(count: int) -> str:
    return f'{count} agent{"" if count == 1 else "s"}'


def what_follows(ctx: Context, kind: str) -> str:
    """What happens next to a start the slots refused, as the settings make it: a summoned agent is asked for again, a
    worker starts by itself only while Full Auto is checked. UX review round 1 (spawn-gate F4): every refusal
    promised a start that never came."""
    if kind != 'worker':
        return 'Ask again when one is free.'
    if ctx.setting('dispatch_autostart'):
        return 'It stays in To do and starts by itself when a slot frees.'
    return 'It stays in To do until you start it, or check Full Auto.'


def admit(ctx: Context, store: Store, work_id: str, kind: str, *, besides: int | None = None,
          asked: int | None = None, agent: str | None = None, auto: bool = False, persons_own: bool = False,
          limited: bool = False) -> None:
    """Apply the gate against current settings, including calls made inside a long-lived runner."""
    with home.registry_scope(fresh=True):
        _admit(ctx, store, work_id, kind, besides=besides, asked=asked, agent=agent, auto=auto,
               persons_own=persons_own, limited=limited)


def _admit(ctx: Context, store: Store, work_id: str, kind: str, *, besides: int | None = None,
           asked: int | None = None, agent: str | None = None, auto: bool = False,
           persons_own: bool = False, limited: bool = False) -> None:
    """Refuse a start the gate has no room for, saying which limit binds and what follows: a halt newer than the start
    was asked for, `halted`; an agent that keeps failing, for an automatic start, `failing_agent`; the machine's
    agents, dispatch_machine_agents; the project's slots, dispatch_agents, for an automatic or `limited` start; the
    day's budget. Run under the gate's
    lock, `start_runner` and `admit_self`, so a halt written under it is seen by every start after it."""
    stopped = halted(store.project_id, asked, pinned(store).get(BASE_VARIABLE))
    if stopped is not None:
        raise Refused(halt_refusal(stopped, called(store, [work_id])[work_id]), 'metaform dispatch sessions')
    # Full Auto off: running agents continue, but no ticket worker or role creator starts automatically:
    # a retry or the queue (2026-10-18: with it off, every stopped agent was replaced by a GC launch at once)
    kind = capacity_kind(ctx, work_id, kind)
    if auto and kind in ('worker', 'helper') and not ctx.setting('dispatch_autostart'):
        raise Refused(f'Full Auto is off, so {called(store, [work_id])[work_id]} does not start by itself. '
                      'Start it yourself, or check Full Auto.', 'metaform dispatch autostart')
    # Only the active board is worked, 2026-10-21: a start the system makes by itself for a ticket on a board set
    # aside is refused, Full Auto on or off, so old boards stay aside; the person's own start of it still runs. A
    # helper, the Facilitator's commission among them, serves a ticket already admitted and is never set aside: with
    # commissions refused, every routing sat at 'Facilitator is selecting expertise' and no Start could take a ticket.
    if auto and kind == 'worker':
        aside = set_aside(ctx, str(work_id))
        if aside is not None:
            raise Refused(f'{called(store, [work_id])[work_id]} is on {aside}, which is set aside: only the active '
                          'board runs by itself. Start it yourself, or activate its board.', 'metaform map boards')
    if auto and agent is not None:
        failing = failing_agent(ctx, store.project_id, agent)
        if failing is not None:
            raise Refused(f'{agent_label(agent)} did not start on {len(failing["tickets"])} tickets in a row: '
                          f'{failing["reason"]}. Nothing starts it by itself until its start command, '
                          f'dispatch_{agent}, changes, or you start a ticket yourself.', 'metaform dispatch signals')
    held = slots(ctx, store, besides=besides)
    # the person can always summon their own system agent: background work fills at most dispatch_machine_agents, and
    # their agent may take one place beyond it, so their chat is never refused for work running elsewhere (2026-10-18:
    # Full Auto filled all eight and the person's chat in another project bounced)
    if kind == 'worker' and held['machine_free'] <= 0:
        raise Refused(f'{_agents(held["machine_used"])} {"is" if held["machine_used"] == 1 else "are"} running on '
                      f'this machine across {held["projects"]} project{"" if held["projects"] == 1 else "s"}, the most '
                      f'dispatch_machine_agents allows ({held["machine_limit"]}). {what_follows(ctx, kind)}',
                      'metaform dispatch sessions')
    # dispatch_agents is how many workers Full Auto may start: a start the person makes, or their system agent makes at
    # their word, runs whatever the count and still counts toward it (2026-10-19: the person had to raise the limit to
    # start one emergency ticket). `limited` binds a start nobody asked for that is not Full Auto's.
    if kind == 'worker' and (auto or limited) and held['free'] <= 0:
        names = called(store, [*held['holding'][:5], work_id])
        holders = ', '.join(names[one] for one in held['holding'][:5]) or 'agents the person summoned'
        raise Refused(f'Every slot Full Auto may fill is in use: dispatch_agents lets it start '
                      f'{_agents(held["limit"])} at once, held by {holders}. {names[work_id]}: '
                      f'{what_follows(ctx, kind)}{" Starting it yourself runs it now." if auto else ""}',
                      'metaform dispatch sessions')
    if kind not in ('worker', 'sentinel', 'advisor') and not persons_own and held['room'] <= 0:
        raise Refused(f'The project has {HELPERS_MOST} helpers active. Wait for a helper to finish; worker limits '
                      'do not block the advisor.', 'metaform dispatch sessions')
    found = over_budget(ctx, store, work_id=work_id if kind == 'worker' and not ticketless(work_id) else None)
    if found is not None:
        refusal = budget_refusal(found)
        raise Refused(refusal.message, refusal.next_step)


def runner_context(store: Store) -> Context:
    """A context for the project a store is of, for a start made with none, such as a resume a runner hands over."""
    return context('dispatch', Path(store.project().path), project=store.project_id)


def runner_log(store: Store, name: str, work_id: str) -> Path:
    """Where a runner's output goes: in the home, private to its owner, named for the project, the kind of start and
    the ticket. UX review round 1, 2026-10-17 (dispatch-concurrency F8, interrupt-failure-recovery F8): it was the
    shared temporary folder, readable by every user and shared by every home, and cleared at boot, when a crash's
    account is needed."""
    folder = home.home() / 'run' / 'dispatch' / 'logs'
    home.mkdir_private(folder)
    return folder / f'{store.project_id}-{name}-{work_id}.log'


def _recorded(pid: int, entry: dict[str, Any]) -> None:
    """A runner's ledger entry, written whole: a reader never meets one half written."""
    folder = ledger()
    home.mkdir_private(folder)
    temporary = folder / f'.{pid}.tmp'
    home.write_private(temporary, json.dumps(entry))
    os.replace(temporary, folder / f'{pid}.json')


LEASE_VARIABLE = 'METAFORM_RUNNER_LEASE'  # the lease a runner holds for as long as it lives, `RunnerWatch`


def _leased() -> tuple[str, Path, int | None]:
    """A new lease for a runner about to start: its token, its lock file and, where a lock passes to a child, the
    descriptor holding it, which the runner inherits so it holds the lease from its first instruction. The lease file
    holds the runner's ledger entry too, written once the runner is started, `lease_note`, so a watch reads what it
    watches from the lease alone, whatever reads of the ledger have removed since."""
    token = secrets.token_hex(16)
    folder = lease_folder()
    home.mkdir_private(folder)
    path = folder / f'{token}.lock'
    if os.name == 'nt':  # a lock is not inherited there: the runner takes it as it starts, `hold_lease`
        home.write_private(path, '')
        return token, path, None
    import fcntl
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return token, path, descriptor


def start_runner(ctx: Context | None, store: Store, work_id: str, agent: str, words: Sequence[str], name: str, *,
                 reservation: str | None = None, kept: bool = False, besides: int | None = None,
                 asked: int | None = None, auto: bool = False, subject: str | None = None) -> dict[str, Any]:
    """Start a runner detached from the terminal in the project's folder, through the one admission gate: under the
    home's lock the slots and the day's budget are counted, `admit`, the runner is started and its ledger entry
    written, so the slot is held from the moment it starts. A start refused or failing gives its ticket's
    `reservation` back where it waited, and leaves no entry. `kept` for a launch whose caller waits on it,
    `launched`; `besides` is a runner handing its session over, which still runs as it starts the next.

    `asked` is when the start was asked for, time.time_ns, by default now: a halt written since refuses it. `auto` is
    a start nothing the person did just now asked for, autostart's, the supervisor's, a sentinel's, the connected
    system agent's: an agent that keeps failing is not started that way. `subject` is what a summoned agent is about,
    one chat per subject: a live runner already about it is reused, under the same lock, so two calls at once start
    one agent. The runner holds a lease for as long as it lives, `RunnerWatch`, and the entry names who started it,
    `by`: the calling agent's runner, or None for the person."""
    from .recovery import identity
    asked = time.time_ns() if asked is None else asked
    ctx = ctx if ctx is not None else runner_context(store)
    kind = capacity_kind(ctx, work_id, launch_kind(words))
    env = child_environment(**pinned(store))
    log = runner_log(store, name, work_id)
    by = os.environ.get('METAFORM_SESSION') if sender(ctx) is not None else None
    home.mkdir_private(ledger())
    try:
        with home.file_lock(admit_lock()):
            if subject is not None:
                for entry in launches():
                    if entry.get('project') == store.project_id and entry.get('work_id') == work_id \
                            and entry.get('subject') == subject:
                        return {'pid': entry['pid'], 'log': str(log), 'reused': True}
            admit(ctx, store, work_id, kind, besides=besides, asked=asked, agent=agent, auto=auto,
                  persons_own=primary_advisor(words))
            token, lease, held = _leased()
            try:
                with os.fdopen(os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600), 'ab') as written:
                    process = subprocess.Popen([sys.executable, '-m', 'metaform', 'dispatch', 'run', work_id, agent,
                                                *words, '--project', store.project_id],
                                               cwd=store.project().path, stdin=subprocess.DEVNULL, stdout=written,
                                               stderr=written, pass_fds=(held,) if held is not None else (),
                                               env={**env, LEASE_VARIABLE: str(lease)},
                                               **group_options())
            except OSError:
                with contextlib.suppress(OSError):
                    lease.unlink()
                raise
            finally:
                if held is not None:
                    os.close(held)  # the runner holds it now, through the descriptor it inherited
            try:
                entry = {'pid': process.pid, 'born': identity(process.pid) or '', 'project': store.project_id,
                         'work_id': work_id, 'agent': agent, 'kind': kind, 'started': time.time(), 'asked': asked,
                         'lease': token, 'by': by, 'subject': subject, 'reservation': reservation,
                         'base': pinned(store).get(BASE_VARIABLE)}
                lease_note(lease, entry)
                _recorded(process.pid, entry)
            except OSError:
                end_group(process.pid)  # a runner the ledger cannot hold is no slot anyone can count
                raise
    except (Stop, OSError):
        if reservation is not None:
            given_back_reservation(store, work_id, reservation)
        raise
    if kept:
        RUNNERS[process.pid] = process
    return {'pid': process.pid, 'log': str(log)}


def admit_self(ctx: Context, store: Store, work_id: str, kind: str) -> None:
    """A runner's own check before its agent starts: one the gate started is in the ledger already, and is refused
    only by a halt written after it was asked for; one started any other way, by hand or by a process on older code,
    is counted and entered here, or refused, BASE-052."""
    from .recovery import identity
    kind = capacity_kind(ctx, work_id, kind)
    home.mkdir_private(ledger())
    with home.file_lock(admit_lock()):
        own = next((entry for entry in launches() if entry['pid'] == os.getpid()), None)
        if own is not None:
            stopped = halted(store.project_id, int(own.get('asked') or own.get('started', 0) * 1e9),
                             own.get('base') if isinstance(own.get('base'), str) else None)
            if stopped is not None:
                raise Refused(halt_refusal(stopped, called(store, [work_id])[work_id]), 'metaform dispatch sessions')
            return
        personal = bool(ctx.nouns.get('system')) and not any(ctx.nouns.get(key) for key in ('talk', 'sentinel', 'intake', 'prep'))
        # started outside the gate, so nothing says the person asked for it
        admit(ctx, store, work_id, kind, besides=os.getpid(), persons_own=personal, limited=True)
        _recorded(os.getpid(), {'pid': os.getpid(), 'born': identity(os.getpid()) or '', 'project': store.project_id,
                                'work_id': work_id, 'agent': str(ctx.nouns.get('agent') or ''), 'kind': kind,
                                'started': time.time(), 'asked': time.time_ns(),
                                'reservation': ctx.nouns.get('reservation')})


def lease_note(path: Path, entry: dict[str, Any]) -> None:
    """Write a runner's entry into its lease file in place: the file stays the one locked, so no lock is lost. A lease
    another holds where locks are mandatory, Windows, is left as it is."""
    with contextlib.suppress(OSError):
        descriptor = os.open(path, os.O_WRONLY | getattr(os, 'O_BINARY', 0))
        try:
            os.ftruncate(descriptor, 0)
            os.write(descriptor, json.dumps(entry).encode('utf-8'))
        finally:
            os.close(descriptor)


def note_agent(pid: int, lease: Path | None = None) -> None:
    """The runner's agent started, in a process group of its own: its pid and birth go in the runner's ledger entry
    and its lease, so a stop of the runner still starting, or the death of the runner, ends the agent's group too."""
    from .recovery import identity
    path = ledger() / f'{os.getpid()}.json'
    with home.file_lock(admit_lock()):
        entry = _read_json(path)
        if entry is not None:
            entry = {**entry, 'agent_pgid': pid, 'agent_born': identity(pid) or ''}
            _recorded(os.getpid(), entry)
            if lease is not None:
                lease_note(lease, entry)


def ended_launch_group(pid: int) -> None:
    """End a runner still starting and its agent's own process group, read from the runner's ledger entry first,
    since the runner's end no longer reaches an agent in a group of its own."""
    from .recovery import identity
    entry = _read_json(ledger() / f'{pid}.json') or {}
    end_group(pid)
    agent, born = entry.get('agent_pgid'), entry.get('agent_born')
    if isinstance(agent, int) and isinstance(born, str) and born and identity(agent) == born:
        end_group(agent)


def stopped_seats(pid: int) -> None:
    """A roundtable's follower, which holds its seats' slots, asked to stop with SIGTERM: it ends its table and follows
    it until the engine has closed the seats, and gives the slots back only then. Its group is never killed, which
    would free the slots and leave the engine's seats at work."""
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.kill(pid, signal.SIGTERM)


def leave_ledger() -> None:
    """A runner whose agent has ended gives its slot back: its ledger entry goes, though the process may still wait to
    run the queue, `moved_on`."""
    with contextlib.suppress(OSError):
        (ledger() / f'{os.getpid()}.json').unlink()
    for path in ledger().glob(f'{os.getpid()}-fork-*.json'):
        with contextlib.suppress(OSError):
            path.unlink()


def fork_capacity(ctx: Context, store: Store, work_id: str, agent: str) -> Path:
    """Reserve an active ACP fork through the same machine-wide admission lock as a managed runner.

    A fork shares its adapter process and inherited context, but can execute beside its parent. Its active turn
    therefore counts separately. The reservation lives until that turn ends, or the parent adapter ends; a dead
    runner's reservations are pruned by the ordinary ledger read, with no polling or separate capacity policy.
    """
    from .recovery import identity
    with home.file_lock(admit_lock()):
        admit(ctx, store, work_id, 'worker', agent=agent, limited=True)  # the agent's own fork, never the person's
        token = secrets.token_hex(16)
        path = ledger() / f'{os.getpid()}-fork-{token}.json'
        temporary = path.with_suffix('.tmp')
        home.write_private(temporary, json.dumps({'pid': os.getpid(), 'born': identity(os.getpid()) or '',
            'project': store.project_id, 'work_id': work_id, 'agent': agent, 'kind': 'worker',
            'started': time.time(), 'asked': time.time_ns(), 'fork': token}))
        os.replace(temporary, path)
        return path


def seat_slots(project_id: str, work_id: str, count: int) -> list[Path]:
    """Hold one worker slot for each of a roundtable's `count` seats through the one admission gate, for as long as the
    calling process lives, offered to the roundtables module as `dispatch.seats`: a seat is an agent at work, so a
    table never runs past dispatch_agents or dispatch_machine_agents, and a ticket never starts past the seats a table
    holds. Refused, with the limit that binds, when fewer slots are free than seats; then nothing is held. Removing the
    returned entries gives the slots back, as the end of the process does."""
    from .recovery import identity
    store = Store(project_id, module='dispatch')
    ctx = runner_context(store)
    home.mkdir_private(ledger())
    made: list[Path] = []
    with home.file_lock(admit_lock()):
        held = slots(ctx, store)
        if count > held['free']:
            binding = 'dispatch_machine_agents' if held['machine_free'] < count else 'dispatch_agents'
            raise Refused(f'A table of {count} seat{"" if count == 1 else "s"} needs {count} free agent '
                          f'slot{"" if count == 1 else "s"} and {held["free"]} '
                          f'{"is" if held["free"] == 1 else "are"} free: {binding} allows '
                          f'{held["machine_limit"] if binding == "dispatch_machine_agents" else held["limit"]}, and '
                          f'{held["machine_used"] if binding == "dispatch_machine_agents" else held["used"]} '
                          'are at work. Seat fewer, or wait for agents to finish.', 'metaform dispatch sessions')
        try:
            for _ in range(count):
                admit(ctx, store, work_id, 'worker')  # a halt or the day's budget refuses a seat as it does a start
                path = ledger() / f'{os.getpid()}-seat-{secrets.token_hex(8)}.json'
                temporary = path.with_suffix('.tmp')
                home.write_private(temporary, json.dumps({'pid': os.getpid(), 'born': identity(os.getpid()) or '',
                    'project': project_id, 'work_id': work_id, 'agent': 'roundtable seat', 'kind': 'worker',
                    'seat': True, 'started': time.time(), 'asked': time.time_ns()}))
                os.replace(temporary, path)
                made.append(path)
        except BaseException:
            for path in made:
                with contextlib.suppress(OSError):
                    path.unlink()
            raise
    return made


def given_back_reservation(store: Store, work_id: str, reservation: str) -> None:
    """A ticket reserved for a start that did not happen goes back where it waited, To do, or the backlog when the
    person holds it."""
    with store.atomic():
        record = ticket(store, work_id)
        if record.taken_by == reservation:
            store.move_work(work_id, 'backlog' if record.held else 'todo', kept=True)


# ------------------------------------------------------------------ the gate's memory
# The gate counts the runners alive at the moment it is asked, and it also remembers. A halt, written by the person's
# Stop all, a clear and the removal of a metaform, refuses every start asked for before it, so a Start all half done,
# an autostart pass that reserved its tickets a moment before, or a launch waiting on the gate's lock never starts
# after the person stopped everything; while the clear or removal runs, it refuses every start, so the passes its own
# stops wake start nothing on a map being deleted. A failed start is recorded on its ticket, `session_attempts` with
# session START_ATTEMPT, and on its agent, so the supervisor's policy, P012 (dispatch_retries, RETRY_SECONDS doubled
# for each, then the person), holds for a start as it holds for a session, and the reason reaches the card and the
# signals. A runner's lease, a lock its process holds for as long as it lives, makes its death an event: a waiter
# blocked on the lease, `RunnerWatch`, is woken by the system when the runner ends, however it ends. UX review round 2,
# 2026-10-17 (ux-verify-combined F1 F2 F5, held-sweeps F1, spawn-gate F1 F2 F3 F4, intake-single-flight F1 F3):
# Stop all during Start all left three agents running, a clear with Full Auto on started four on the map it deleted,
# and a runner failing before its session was started again about once a second, 111 runners in 100 s, unsaid.
START_ATTEMPT = 'start'  # the session id of a ticket's count of failed starts in `session_attempts`
BATCH_WORD = re.compile(r'[A-Za-z0-9-]{8,64}')  # a Start all run's token, as the page makes it
BATCH_KEPT = 86400  # seconds a batch's first sight is kept; older ones go as a new batch is first seen
HALTS = {'stop-all': 'Stop all', 'clear': 'The clear of this project', 'remove-base': 'The removal of its map',
         'stop': 'Stop all'}


def admit_lock() -> Path:
    """The lock the gate counts, starts and halts under: one for the home."""
    return ledger().parent / 'admit.lock'


def halt_path(project_id: str) -> Path:
    return ledger().parent / 'halt' / f'{project_id}.json'


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        raw: Any = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return cast(dict[str, Any], raw) if isinstance(raw, dict) else None


def _write_json(path: Path, value: dict[str, Any]) -> None:
    """A small record written whole, so a reader never meets one half written."""
    home.mkdir_private(path.parent)
    temporary = path.with_name(f'.{path.name}.{os.getpid()}.tmp')
    home.write_private(temporary, json.dumps(value))
    os.replace(temporary, path)


def halt(project_id: str, by: str, *, base_id: str | None = None, held: bool = False) -> dict[str, Any]:
    """Write the project's halt under the gate's lock, so every start the gate admits after it sees it: `by` is what
    halted it, `base_id` the one metaform it halts, or every one; `held` refuses every start, whenever asked, for as
    long as the halt's own process lives and has not let it go, `let_go`. The work a Stop all paused, `paused`, is
    kept from the halt before it until Full Auto brings it back, `resume_paused`."""
    from .recovery import identity
    home.mkdir_private(ledger())
    with home.file_lock(admit_lock()):
        before = _read_json(halt_path(project_id)) or {}
        entry = {'at': time.time_ns(), 'by': by, 'base': base_id, 'pid': os.getpid(),
                 'born': identity(os.getpid()) or '', 'held': held, 'paused': list(before.get('paused') or [])}
        _write_json(halt_path(project_id), entry)
    return entry


def keep_paused(project_id: str, entry: dict[str, Any], work_ids: Sequence[str]) -> None:
    """The work paused under the halt `entry`: written into it while it is still the project's halt, so the person's
    Full Auto, turned on again, finds the work their Stop all stopped, and only that work."""
    with home.file_lock(admit_lock()):
        kept = _read_json(halt_path(project_id))
        if kept is not None and kept.get('at') == entry['at'] and kept.get('pid') == entry['pid'] \
                and kept.get('paused') != list(work_ids):
            _write_json(halt_path(project_id), {**kept, 'paused': list(work_ids)})


def let_go(project_id: str, entry: dict[str, Any]) -> None:
    """A held halt is over: starts asked for after it are admitted again; those asked before it stay refused."""
    with home.file_lock(admit_lock()):
        kept = _read_json(halt_path(project_id))
        if kept is not None and kept.get('at') == entry['at'] and kept.get('pid') == entry['pid']:
            _write_json(halt_path(project_id), {**kept, 'held': False})


@contextlib.contextmanager
def halting(project_id: str, by: str, base_id: str | None = None) -> Any:
    """A halt held for the block: what a clear and the removal of a metaform run under, through home.HALTS."""
    entry = halt(project_id, by, base_id=base_id, held=True)
    try:
        yield entry
    finally:
        let_go(project_id, entry)


home.HALTS['dispatch'] = halting


def halted(project_id: str, asked: int | None, base: str | None = None) -> dict[str, Any] | None:
    """The project's halt when it refuses a start asked for at `asked` (time.time_ns) on metaform `base`: one held
    while its process lives, or one written after the start was asked for; None when it refuses nothing. A halt of
    one metaform concerns only the starts on it."""
    entry = _read_json(halt_path(project_id))
    if entry is None or entry.get('base') and entry['base'] != base:
        return None
    pid, born = entry.get('pid'), entry.get('born')
    if entry.get('held') and isinstance(pid, int) and isinstance(born, str) and _runs(pid, born):
        return entry
    if asked is not None and asked < int(entry.get('at') or 0):
        return entry
    return None


def halt_refusal(entry: dict[str, Any], named: str) -> str:
    """Why a halt refuses a start, naming what it would have started, `named`, as the person reads it (`called`)."""
    what = HALTS.get(str(entry.get('by')), 'A stop')
    if entry.get('held'):
        return f'{what} is under way, so nothing starts on it now; {named} is not started.'
    return (f'{what} came after this start was asked for, so {named} is not started; start it again if you '
            'still want it.')


def batch_asked(batch: str) -> int:
    """When a batch of starts, one Start all run, was first seen: every start of the run counts as asked for then, so
    a halt in the middle of the run refuses the rest of it."""
    if not BATCH_WORD.fullmatch(batch):
        raise Stop('batch is the token of one Start all run: 8 to 64 letters, digits or dashes.',
                   'metaform help dispatch start')
    folder = ledger().parent / 'batch'
    home.mkdir_private(folder)
    path = folder / batch
    now = time.time_ns()
    try:
        made = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        try:
            return int(path.read_text(encoding='utf-8').strip() or now)
        except (OSError, ValueError):
            return now
    with os.fdopen(made, 'w', encoding='utf-8') as written:
        written.write(str(now))
    for old in folder.iterdir():  # a new run's first sight is the one time the old ones are looked at
        with contextlib.suppress(OSError):
            if old != path and now / 1e9 - old.stat().st_mtime > BATCH_KEPT:
                old.unlink()
    return now


def person_asks(ctx: Context) -> bool:
    """Whether a call is the person's own: the page, or the command line with no agent's role that carries the
    person's consent, `metaform.caller`; an identity left unset never gives it (integration of gate-memory with
    consent-authority, 2026-10-17)."""
    return ctx.consented or (ctx.surface != 'mcp' and sender(ctx) is None
                             and not (ctx.surface == 'cli' and agent_caller()))


def persons_start(ctx: Context, word: dict[str, Any] | None = None, *, recorded: bool | None = None) -> bool:
    """Whether this start is the person's, using the same boundary as `on_persons_word`.

    The page or an explicitly consented call is the person's. A CLI or MCP call outside dispatch is also theirs,
    including their own AI tool: `caller.dispatched()` is None, so the word guard lets it through without a word.
    A dispatched agent's call is automatic unless it carries the person's word or explicit consent; permission
    to act without asking does not supply either. Full Auto holds only automatic starts; halts still hold all starts.

    Orchestration supplies `recorded` from the originating assignment, since a later launch's caller can differ
    from the caller who started that delivery. A recorded False stays automatic regardless of the launch context.
    """
    if recorded is not None:
        return recorded
    from metaform import caller
    return ctx.surface not in ('mcp', 'cli') or ctx.consented or word is not None or caller.dispatched() is None


def failing_path(project_id: str, agent: str) -> Path:
    return ledger().parent / 'failing' / f'{project_id}-{agent}.json'


def failing_agent(ctx: Context, project_id: str, agent: str) -> dict[str, Any] | None:
    """The record of an agent whose starts keep failing in this project, while its start command is the one that
    failed; None when it is not failing."""
    entry = _read_json(failing_path(project_id, agent))
    if entry is None or not entry.get('failing'):
        return None
    try:
        command = start_command(ctx, agent)
    except Stop:
        return None
    return entry if entry.get('command') == command else None


FAILED_TICKETS = 2  # the different tickets an agent fails to start on, for the same reason, before it is failing


def start_failed(ctx: Context, store: Store, work_id: str, agent: str, reason: str, *,
                 reservation: str | None = None) -> dict[str, Any]:
    """A start that failed, before or after its agent made a session, without its session recorded: counted on its
    ticket when it was reserved for this start, so the agent starter waits RETRY_SECONDS doubled for each failure
    before it tries again and, past dispatch_retries, hands it to the person; its reservation is given back after
    the count is written, so the pass the give-back wakes sees it; and counted on its agent, which, failing for the
    same reason on FAILED_TICKETS different tickets, nothing starts by itself again until its start command changes
    or the person starts one. Each failure raises not-smooth on its ticket with the reason; a hand-over raises
    handed-over, an agent found failing raises setup-not-working for the person's system agent and the page."""
    from .signals import SETUP_NOT_WORKING, publish
    said = (reason.strip().splitlines() or ['it failed with no reason given'])[0][:300]
    limit, now = int(ctx.setting('dispatch_retries')), time.time()
    result: dict[str, Any] = {'work_id': work_id, 'agent': agent, 'reason': said}
    counts = reservation is not None and not ticketless(work_id) and not intake_id(work_id)
    if counts:
        try:
            record = held_ticket(store, work_id)
        except Stop:
            record = None
        if record is None or record.taken_by != reservation:  # it made its session, or a stop gave it back
            return result
    # The agent's record first, a file: a store too busy to take the ticket's count still ends the agent's loop.
    try:
        command = start_command(ctx, agent)
    except Stop:
        command = ''
    path = failing_path(store.project_id, agent)
    home.mkdir_private(path.parent)
    with home.file_lock(path.parent / 'failing.lock'):
        kept = _read_json(path) or {}
        same = kept.get('command') == command and kept.get('reason') == said
        tickets = sorted({*(cast(list[str], kept.get('tickets') or []) if same else []), work_id})
        failing = len(tickets) >= FAILED_TICKETS
        newly = failing and not (same and kept.get('failing'))
        _write_json(path, {'agent': agent, 'command': command, 'reason': said, 'tickets': tickets,
                           'failing': failing, 'at': now})
    retries, handed = 0, False
    if counts:
        try:
            with own_store(store).tables() as tx:
                held = tx.get('session_attempts', {'work_id': work_id})
                counted = int(held['retries']) if held is not None and held['session_id'] == START_ATTEMPT else 0
                retries = counted + 1
                handed = retries > limit
                value = {'work_id': work_id, 'session_id': START_ATTEMPT, 'retries': retries,
                         'next_at': now + RETRY_SECONDS * 2 ** (retries - 1), 'how': f'it did not start: {said}',
                         'seq': time.time_ns(), 'handed': handed}
                if held is not None:
                    tx.delete('session_attempts', {'work_id': work_id})
                tx.insert('session_attempts', value)
                tx.concern(work_id=work_id, kind='session')
            result.update(retries=retries, handed=handed, next_at=value['next_at'])
        except Exception as error:  # noqa: BLE001  a busy or locked store: given back all the same, its agent counted
            result['uncounted'] = str(error)
            retries = 0
        given_back_reservation(store, work_id, str(reservation))
    with contextlib.suppress(Exception):  # what the person is told never undoes what was counted
        if retries:
            publish(ctx, 'not-smooth', work_id=work_id, key=f'start:{retries}', reason=f'it did not start: {said}',
                    next=f'metaform dispatch start {work_id} {agent}')
        if handed:
            publish(ctx, 'handed-over', work_id=work_id, key=f'start:{retries}',
                    reason=f'{agent_label(agent)} did not start on it {retries} times: {said}. It waits for you.',
                    next=f'metaform dispatch start {work_id} {agent}')
        if newly:
            key = f'dispatch:{agent}'
            publish(ctx, SETUP_NOT_WORKING, session_id='producer:dispatch', key=key, signal_key=key,
                    feature=f'{agent_label(agent)} as an agent', set_up=f'dispatch_{agent}: {command}',
                    look='metaform dispatch signals; the runner logs under run/dispatch/logs in the Metaform home',
                    report={'reason': said, 'tickets': tickets})
    result['failing'] = failing
    return result


def started_well(store: Store, work_id: str, agent: str) -> None:
    """A session was made and recorded: the ticket's count of failed starts and its agent's failing record go, read
    first so a start with neither writes nothing."""
    own = own_store(store)
    with own.tables(write=False) as tx:
        held = tx.get('session_attempts', {'work_id': work_id})
    if held is not None and held['session_id'] == START_ATTEMPT:
        with own.tables() as tx:
            again = tx.get('session_attempts', {'work_id': work_id})
            if again is not None and again['session_id'] == START_ATTEMPT:
                tx.delete('session_attempts', {'work_id': work_id})
    with contextlib.suppress(OSError):
        failing_path(store.project_id, agent).unlink()


def start_backoff(store: Store) -> dict[str, dict[str, Any]]:
    """Each ticket's count of failed starts, read once for a pass of the agent starter."""
    with own_store(store).tables(write=False) as tx:
        return {str(row['work_id']): dict(row) for row in tx.rows('session_attempts', limit=0).results
                if row['session_id'] == START_ATTEMPT}


def merged_due(found: dict[str, Any], due: float | None) -> dict[str, Any]:
    """A pass's result with the earlier of its retry due and `due`, the end of a failed start's wait."""
    if due is None:
        return found
    held = found.get('retry_due')
    return {**found, 'retry_due': min(float(held), due) if held is not None else due}


def backing_off(row: dict[str, Any] | None, now: float) -> bool:
    """Whether a ticket's failed starts keep the agent starter from it now: handed to the person, or its wait not
    over."""
    return row is not None and (bool(row['handed']) or float(row['next_at']) > now)


def lease_folder() -> Path:
    return ledger().parent / 'leases'


class RunnerWatch:
    """Hear each runner of the home end, however it ends, at once: one thread per runner blocks on the runner's lease,
    a lock its process holds for as long as it lives, and the system wakes it when the process ends. Nothing polls; a
    runner that ended cleanly has removed its lease, and its own writes said it. On a death, `gone` is called with the
    runner's ledger entry, once. `arm` reads the ledger only when its folder changed since the last arm, one stat, so
    it can be called on every change heard. `only` keeps the watch to the runners of one project or one ticket."""

    def __init__(self, gone: Callable[[dict[str, Any]], None], *, project: str | None = None,
                 work_id: str | None = None) -> None:
        self.gone = gone
        self.project = project
        self.work_id = work_id
        self.watched: set[str] = set()
        self.lock = threading.Lock()
        self.seen: set[str] = set()  # the leases' file names read already
        self.closed = False

    def arm(self) -> None:
        try:
            names = os.listdir(lease_folder())
        except OSError:
            return
        with self.lock:
            if self.closed:
                return
            fresh = [name for name in names if name.endswith('.lock') and name not in self.seen]
            self.seen = set(names)
        for name in fresh:
            entry = _read_json(lease_folder() / name)
            if entry is None or not isinstance(entry.get('pid'), int):  # not written yet: read at the next arm
                with self.lock:
                    self.seen.discard(name)
                continue
            lease = str(entry.get('lease') or name.removesuffix('.lock'))
            if self.project is not None and entry.get('project') != self.project \
                    or self.work_id is not None and entry.get('work_id') != self.work_id:
                continue
            with self.lock:
                if lease in self.watched:
                    continue
                self.watched.add(lease)
            threading.Thread(target=self.wait, args=({**entry, 'lease': lease},), daemon=True,
                             name=f'runner {entry["pid"]}').start()

    def close(self) -> None:
        with self.lock:
            self.closed = True

    def wait(self, entry: dict[str, Any]) -> None:
        path = lease_folder() / f'{entry["lease"]}.lock'
        try:
            if not path.exists():  # ended cleanly before the watch began
                return
            try:  # free at once: the runner holds it no more, or not yet; its process says which
                with home.file_lock(path, wait=False):
                    ended = not _runs(int(entry['pid']), str(entry['born']))
            except home.Held:  # the runner holds it: the system's own wait, until its process lets go by ending,
                with home.file_lock(path):  # which it does only as it ends, so no look at the process is needed;
                    ended = True  # one taken at the very moment of its end can still read as alive
            if not ended:  # it had not taken its lease yet, as on Windows: the next arm watches it again
                with self.lock:
                    self.watched.discard(str(entry['lease']))
                    self.seen.discard(path.name)
                return
            entry = {**entry, **(_read_json(path) or {})}  # what the runner added since, its agent's group
            if not path.exists():  # it removed its lease on its way out: its own writes said it ended
                return
            with self.lock:
                if self.closed:
                    return
            self.gone(entry)
        except OSError:
            return


def runner_gone(entry: dict[str, Any]) -> dict[str, Any] | None:
    """What a runner's death leaves, ended at once by the process that heard it, `RunnerWatch`: its agent's process
    group, which runs in a group of its own, when it outlived the runner; its ledger entry and lease; and, for a ticket
    still reserved for it, a failed start, `start_failed`, so its ticket goes back to wait with the reason and the
    supervisor's count. Returns what the change concerns, for its `map.changed`; None for a project no longer here."""
    from .recovery import identity
    agent_pid, agent_born = entry.get('agent_pgid'), entry.get('agent_born')
    if isinstance(agent_pid, int) and isinstance(agent_born, str) and agent_born and identity(agent_pid) == agent_born:
        end_group(agent_pid)
    with contextlib.suppress(OSError):
        (ledger() / f'{entry["pid"]}.json').unlink()
    with contextlib.suppress(OSError):
        (lease_folder() / f'{entry["lease"]}.lock').unlink()
    project = home.project(str(entry.get('project') or ''))
    if project is None:
        return None
    work_id = str(entry.get('work_id') or '')
    reservation = entry.get('reservation')
    if isinstance(reservation, str) and reservation:
        try:
            store = Store(project.project_id)
            record = held_ticket(store, work_id)
            if record is not None and record.taken_by == reservation:
                start_failed(context('dispatch', Path(project.path), project=project.project_id), store, work_id,
                             str(entry.get('agent') or ''),
                             'its runner ended before its agent made a session, with no word of why',
                             reservation=reservation)
        except (Stop, OSError):
            pass
    # Its session, the one row it held, is written as ended by its runner's death, as `settle` writes it, so no read
    # that follows takes it for running while the process is still being taken down; the supervisor resumes it.
    from .recovery import DEAD
    try:
        own = Store(project.project_id, module='dispatch')
        with own.tables() as tx:
            for row in tx.rows('agent_sessions', {'work_id': work_id}, limit=0).results:
                if row['state'] == 'running' and row.get('pid') == entry.get('pid'):
                    tx.update('agent_sessions', {'session_id': row['session_id']},
                              {'state': 'ended', 'how': DEAD, 'ended': home.now()})
                    tx.concern(work_id=work_id, session_id=str(row['session_id']), kind='session')
    except (StoreError, OSError):
        pass
    return {'project': project.project_id, 'work_ids': [work_id], 'kinds': ['session', 'ticket']}


def watch_deaths(told: Callable[[dict[str, Any]], None]) -> RunnerWatch:
    """What dispatch provides a long-running process, `dispatch.deaths`, the web GUI's server: a watch on every runner
    of the home that cleans up after a death, `runner_gone`, and tells `told` what the change concerns, so it announces
    it to every surface. The caller arms it on each change it hears; it reads the ledger only when that changed."""
    def gone(entry: dict[str, Any]) -> None:
        about = runner_gone(entry)
        if about is not None:
            told(about)
    watch = RunnerWatch(gone)
    watch.arm()
    return watch


_HEARING: list[Callable[[dict[str, Any]], None]] = []  # this process's callers waiting to hear a runner's death
_HEARD: list[RunnerWatch] = []  # this process's one watch for them, made at the first


def _heard(entry: dict[str, Any]) -> None:
    for told in _HEARING[:]:  # a copy: a wait may end while it is told
        with contextlib.suppress(Exception):
            told(entry)


@contextlib.contextmanager
def deaths_heard(told: Callable[[dict[str, Any]], None]) -> Any:
    """Hear each runner of the home end while the block runs, for a wait in this process, `wait`: one watch for the
    process, whatever the number of waits, armed again whenever the caller hears a change. It cleans up nothing;
    the process whose watch announces it, the web GUI's, does."""
    if not _HEARD:
        _HEARD.append(RunnerWatch(_heard))
    _HEARING.append(told)
    _HEARD[0].arm()
    try:
        yield _HEARD[0]
    finally:
        _HEARING.remove(told)


def footprint(store: Store) -> dict[str, int] | None:
    """What the project's agents use of this machine's memory now: each runner with every process it started, read
    once from /proc; None where there is no /proc. UX review round 1, 2026-10-17, orchestrator-system-agent F8: the
    person set Agents at once with no idea what one costs."""
    if not sys.platform.startswith('linux'):
        return None
    runners = {int(entry['pid']) for entry in launches() if entry.get('project') == store.project_id}
    if not runners:
        return {'agents': 0, 'kb': 0, 'per_agent_kb': 0}
    parent: dict[int, int] = {}
    resident: dict[int, int] = {}
    for folder in Path('/proc').iterdir():
        if not folder.name.isdigit():
            continue
        try:
            status = (folder / 'status').read_text()
        except OSError:
            continue
        fields = dict(line.split(':', 1) for line in status.splitlines() if ':' in line)
        with contextlib.suppress(KeyError, ValueError):
            parent[int(folder.name)] = int(fields['PPid'].strip())
            resident[int(folder.name)] = int(fields.get('VmRSS', '0 kB').split()[0])
    total = 0
    for pid, kb in resident.items():
        walk, seen = pid, 0
        while walk not in runners and walk in parent and seen < 64:
            walk, seen = parent[walk], seen + 1
        if walk in runners:
            total += kb
    return {'agents': len(runners), 'kb': total, 'per_agent_kb': total // len(runners)}


def start_raised(ctx: Context, store: Store, asked: int | None = None) -> list[str]:
    """Start each queued sentinel whose node is no longer in use, oldest first, VIEW-045."""
    own = Store(store.project_id, module='dispatch')
    with own.tables(write=False) as tx:  # read first: a pass with nothing queued writes nothing, so it never makes a
        held = [dict(row) for row in tx.rows('raised', by=('seq',), limit=0).results]  # cleared project's base again
    if not held:
        return []
    made = {row['work_id'] for row in sessions(store)}
    done = [row['work_id'] for row in held if row['started'] is not None
            and (row['work_id'] in made or not launch_holds(store, row))]
    if done:  # a launch whose session is made, or that never made one, is done waiting
        with own.tables() as tx:
            for work_id in done:
                tx.delete('raised', {'work_id': work_id})
    waiting = [row for row in held if row['started'] is None]
    started: list[str] = []
    for row in waiting:
        if in_use(store, row['node']):
            continue
        try:
            launch(ctx, store, row['work_id'], row['node'], row['agent'], asked=asked)
        except Stop:  # a halt, failing agent or reached budget waits for the next pass
            break
        started.append(row['work_id'])
    return started


def launch(ctx: Context, store: Store, work_id: str, node: str, agent: str, *,
           asked: int | None = None) -> dict[str, Any]:
    """Start an issue's sentinel, its row in `raised` marked started until its session is made; one the gate refuses
    goes back to wait in the queue."""
    with Store(store.project_id, module='dispatch').tables() as tx:
        tx.delete('raised', {'work_id': work_id})
        tx.insert('raised', {'work_id': work_id, 'node': node, 'agent': agent, 'started': time.time(),
                             'seq': time.time_ns()})
    try:
        return converse(ctx, store, work_id, agent, [f'sentinel={node}'], asked=asked, auto=asked is not None)
    except (Stop, OSError):
        with Store(store.project_id, module='dispatch').tables() as tx:
            tx.update('raised', {'work_id': work_id}, {'started': None})
        raise


def claim(ctx: Context) -> dict[str, Any]:
    """Record a work claim, LAYER-029: the part of the map a chosen proposal reserves and the tickets it covers. It
    is active from the first of its tickets being taken until the last has landed; while active, no other ticket on
    its nodes starts, and an issue raised on them waits."""
    store = ctx.require_store()
    name = str(ctx.nouns['name']).strip()
    nodes = json_list(ctx.nouns.get('nodes') or [], 'nodes')
    work = json_list(ctx.nouns.get('work') or [], 'work')
    if not name or not nodes:
        raise Stop('A claim has a name and the addresses it reserves.', 'metaform dispatch claim "<name>" nodes=\'["<address>"]\'')
    for work_id in work:
        ticket(store, work_id)
    claim_id = uuid.uuid4().hex
    with Store(store.project_id, module='dispatch').tables() as tx:
        tx.insert('claims', {'claim_id': claim_id, 'name': name, 'nodes': json.dumps(nodes),
                             'issue': ctx.nouns.get('issue'), 'seq': time.time_ns()})
        for work_id in work:
            tx.delete('claim_work', {'work_id': work_id})
            tx.insert('claim_work', {'work_id': work_id, 'claim_id': claim_id})
    return next(one for one in claim_rows(store) if one['claim_id'] == claim_id)


def claims(ctx: Context) -> dict[str, Any]:
    """The work claims with their state, and the proposals sentinels have made, for the page, VIEW-045."""
    store = ctx.require_store()
    with Store(store.project_id, module='dispatch').tables(write=False) as tx:
        proposals = {row['issue']: json.loads(row['text']) for row in tx.rows('proposals', by=('seq',), limit=0).results}
    return {'claims': claim_rows(store), 'proposals': proposals}


def propose(ctx: Context) -> dict[str, Any]:
    """A sentinel's proposals for its issue, kept for the page to present beside what each reserves, VIEW-045: each
    a title, its grounds, its disruption with the addresses it reserves as reach, its benefit and its trade-off,
    and, where the sentinel made one, a link to its own explanation as view."""
    store = ctx.require_store()
    issue = ticket(store, str(ctx.nouns['issue'])).id
    given: Any = ctx.nouns.get('proposals')
    if isinstance(given, str):
        try:
            given = json.loads(given)
        except ValueError:
            raise Stop('proposals is a JSON list of objects.', 'metaform help dispatch propose') from None
    if not isinstance(given, list) or not given or any(not isinstance(one, dict) or not cast(dict[str, Any], one).get('title')
                                                      for one in cast(list[Any], given)):
        raise Stop('proposals is a JSON list of objects, each with a title.', 'metaform help dispatch propose')
    for one in cast(list[dict[str, Any]], given):
        one['reach'] = json_list(one.get('reach') or [], 'reach')
    with Store(store.project_id, module='dispatch').tables() as tx:
        tx.delete('proposals', {'issue': issue})
        tx.insert('proposals', {'issue': issue, 'text': json.dumps(given), 'seq': time.time_ns()})
    return {'issue': issue, 'proposals': given}


def raise_issue(ctx: Context) -> dict[str, Any]:
    """The person raises an issue on a node, a sentinel starts on it with their words, investigates,
    and brings proposals to the page's chat; the person chooses one or talks it through, and the chosen one becomes
    held tickets. The issue is held on a ticket of its own at the node, so the chat has a place and the report is
    kept; no worker takes it. An issue on a node other work is using waits until that work is complete.
    Agent capacity never delays its sentinel."""
    store = ctx.require_store()
    given: Any = ctx.nouns['text']
    words = [str(word) for word in cast(list[Any], given)] if isinstance(given, (list, tuple)) else [str(given)]
    text = ' '.join(words).strip()
    if not text:
        raise Stop('An issue says what is wrong, in the person\'s words.', 'metaform dispatch raise <node> -- "<what is wrong>"')
    node = str(ctx.nouns['node'])
    agent = str(ctx.nouns.get('agent') or ctx.setting('dispatch_agent'))
    if found_command(ctx, agent) is None:  # checked before anything is written
        raise Stop(f'The start command of {agent} is not found on this system.', f'metaform set --dispatch-{agent} "<command>"')
    first = text.splitlines()[0][:120]
    made = map_work(ctx, op='add', node=node, task=f'Issue raised by the person: {first}', title=f'Issue: {first}',
                    note=text, held=True, hold=True)
    work_id = str(cast(dict[str, Any], made)['id'] if isinstance(made, dict) else made.id)
    busy = in_use(store, node)
    if busy:
        with Store(store.project_id, module='dispatch').tables() as tx:
            tx.insert('raised', {'work_id': work_id, 'node': node, 'agent': agent, 'seq': time.time_ns()})
        return {'state': 'queued', 'work_id': work_id, 'node': node,
                'waiting_on': busy, 'conversation': True}
    try:
        return launch(ctx, store, work_id, node, agent)
    except Stop as error:  # a halt, failing agent or reached budget leaves the issue queued
        return {'state': 'queued', 'work_id': work_id, 'node': node, 'waiting_on': str(error), 'conversation': True}


def talk(ctx: Context) -> dict[str, Any]:
    """Talk with an agent about anything the person clicks, VIEW-042: a ticket, open or done, a node, or an ended
    agent's session. An agent at work on it is talked to directly; otherwise a conversation agent starts, told
    what it is about. One summoned agent is always the person's; more use the agent slots left free, and past them
    a chat is refused until a slot frees. An agent whose role the person holds back starts no agent, may_steer, and
    talks to an agent at work only by a note, which never starts one."""
    if (held := held_role(ctx)) is not None:
        raise Stop(f'A {held} agent starts and talks to no agent: a conversation is for the person and the agents that '
                   'serve them, and it can start an agent. A note reaches an agent at work without starting one.',
                   'metaform dispatch note to=<the ticket of the agent you want to reach> text="<what you want to say>"')
    store = ctx.require_store()
    given = {key: str(ctx.nouns[key]) for key in ('id', 'node', 'session') if ctx.nouns.get(key)}
    if len(given) != 1:
        raise Stop('Talk names one thing: id=<work id>, node=<address>, question=<message id> or '
                   'session=<work id>:<session id> or <agent name>.', 'metaform help dispatch talk')
    (kind, ref), = given.items()
    if kind == 'session' and is_name(ref):  # an agent's name: its latest session
        held = named_session(store, ref)
        ref = f'{held["work_id"]}:{held["session_id"]}'
    everyone = sessions(store)
    running = [row for row in everyone if row['state'] == 'running']
    if kind == 'id':
        work_id, about = ticket(store, ref).id, f'ticket:{ref}'
    elif kind == 'session':
        work_id, _, session_id = ref.partition(':')
        if not any(row['work_id'] == work_id and row['session_id'] == session_id for row in everyone):
            raise Stop(f'No agent session {ref}.', 'metaform dispatch sessions thread=false')
        about = f'thread:{session_id}'
    else:
        work_id, about = anchor(ctx, store, ref), f'node:{ref}'
    if kind in ('id', 'session'):  # an agent at work on it is talked to directly, never restarted
        working = next((row for row in reversed(running) if row['work_id'] == work_id and not summoned(row)), None)
        if working is not None and (kind != 'session' or working['session_id'] == ref.partition(':')[2]):
            return {key: working[key] for key in ('work_id', 'agent', 'session_id', 'state')}
    talking = next((row for row in running if summoned(row) and row['work_id'] == work_id
                    and f'talk={about}' in command_line(row['pid'])), None)
    if talking is not None:  # the chat about this is already open: it is reused
        return {key: talking[key] for key in ('work_id', 'agent', 'session_id', 'state')}
    if kind == 'session':  # the very context the person named, ended: resumed in place, so they can ask it
        named = next(row for row in everyone if row['work_id'] == work_id and row['session_id'] == ref.partition(':')[2])
        if named['state'] != 'running' and (again := resumed_session(ctx, store, named, about)) is not None:
            return again
    # the slots are counted by the gate alone, under its lock, which names the limit that binds (spawn-gate F4); one
    # starting about this already is reused there too
    # a thread whose ticket went with a cleared map is talked about all the same, on no ticket
    agent = agent_for(ctx, held_ticket(store, work_id), ctx.nouns.get('agent'))
    again = resumed_conversation(ctx, store, work_id, agent, about, person=True) \
        if ctx.setting('dispatch_resume_chats') else None
    return again or converse(ctx, store, work_id, agent, [f'talk={about}'])


async def run(ctx: Context) -> dict[str, Any]:
    from .runner import dispatch
    return await dispatch(ctx)


def message(ctx: Context) -> dict[str, Any]:
    """Carry a person's message to the agent working a ticket, as session/prompt; one an agent sends carries its role,
    so its thread never shows it as the person's, BASE-052."""
    if sender(ctx):
        # Agent messages are ordinary peer notes, with authenticated session provenance and no steering.
        from dataclasses import replace

        from .peering import send
        text: Any = ctx.nouns['text']
        words = ' '.join(str(one) for one in cast(list[Any], text)) if isinstance(text, (list, tuple)) else str(text)
        made = send(replace(ctx, nouns={'to': ctx.nouns.get('session') or ctx.nouns['id'],
                                        'target_project': ctx.nouns.get('target_project')}),
                    ctx.require_store(), words, 0)
        return {key: value for key, value in made.items() if not key.startswith('_')}
    may_steer(ctx)
    from .peering import destination
    ctx = destination(ctx, ctx.nouns.get('target_project'))
    store = ctx.require_store()
    given: Any = ctx.nouns['text']
    words = [str(word) for word in cast(list[Any], given)] if isinstance(given, (list, tuple)) else [str(given)]
    text = ' '.join(words)
    given_by: dict[str, Any] = {'by': role} if (role := sender(ctx)) else {}
    if not given_by and ctx.surface == 'cli' and agent_caller() is None:
        # the person's own message, sent from the page with its key or at their own terminal: the turn it starts in
        # their system agent carries their word, `metaform.module.persons_word`; no other sender's does
        given_by['word'] = True
    if ctx.nouns.get('audio'):  # the person's recording, sent beside its transcript where the agent takes audio
        audio = Path(str(ctx.nouns['audio'])).expanduser().resolve()
        clips = (home.home() / 'run' / 'voice' / 'clips').resolve()
        if 'by' in given_by or audio.parent != clips or not audio.is_file():
            raise Stop('A recording goes with a person\'s own message, as a clip the web GUI kept.',
                       f'metaform dispatch message {ctx.nouns["id"]} -- "<text>"')
        given_by['audio'] = str(audio)
    if ctx.nouns.get('image'):  # a frame the person sent, beside their words where the agent takes images
        image = Path(str(ctx.nouns['image'])).expanduser().resolve()
        if role or image.parent != (home.home() / 'run' / 'captures').resolve() or not image.is_file():
            raise Stop('A frame goes with a person\'s own message, as one the web GUI kept.',
                       f'metaform dispatch message {ctx.nouns["id"]} -- "<text>"')
        given_by['image'] = str(image)
    from .orchestration import service
    owner = service(ctx)
    try:
        row = _running_or_stop(store, ctx.nouns['id'], ctx.nouns.get('session'))
    except Stop:
        kept = None if ctx.nouns.get('session') or 'audio' in given_by or 'image' in given_by \
            else _kept_for_start(ctx, owner, str(ctx.nouns['id']), text)
        if kept is None:
            raise
        return kept
    if owner is not None and owner.assignment(ctx, session_id=row['session_id']) is not None:
        owner.directed(ctx, row['session_id'], {'kind': 'user_direction', 'id': secrets.token_hex(16),
                                               'text': text, 'at': home.now(), 'from': {'kind': 'user'}})
    return _told(row, 'message', text=text, **given_by)


def _kept_for_start(ctx: Context, owner: Any, work_id: str, text: str) -> dict[str, Any] | None:
    """A person's message to a ticket whose agent has no session yet, a specialist owner's or one reserved and not
    started: kept on its assignment as the person's direction, which its session takes as their own message when it
    starts, the runner's `peer_note`, as a note to an agent between sessions waits for it. None when no assignment
    holds the ticket open, so the message has no session to wait for."""
    if owner is None:
        return None
    held = owner.assignment(ctx, work_id=work_id)
    if held is None or held.get('stop') or held['state'] in ('returned', 'delivered', 'failed', 'stopped',
                                                              'superseded'):
        return None
    note_id = secrets.token_hex(16)
    events.announced(ctx.folder, ctx.surface, owner.queue_message, ctx, held['assignment_id'],
                     {'id': note_id, 'kind': 'user_direction', 'text': text, 'at': home.now(),
                      'from': {'kind': 'user'}}, key=note_id)
    return {'held': True, 'work_id': work_id, 'assignment_id': held['assignment_id'], 'note': note_id,
            'said': 'Kept on the ticket: its agent reads this when its session starts.'}


def fork(ctx: Context) -> dict[str, Any]:
    """Fork a running agent's session with ACP's session/fork, where its agent offers it, P030: a side conversation
    that starts with everything the session knows, given the same Metaform server and identity, kept as a child thread
    of the session; with text, that is its first turn. fork=<id> messages an existing child, with native subagents
    reached through their parent's native messaging tool."""
    may_steer(ctx)
    store = ctx.require_store()
    given: Any = ctx.nouns.get('text') or []
    text = ' '.join(str(word) for word in cast(list[Any], given)) if isinstance(given, (list, tuple)) else str(given)
    row = _running_or_stop(store, ctx.nouns['id'], ctx.nouns.get('session'))
    if ctx.nouns.get('fork'):
        answer = _told(row, 'message', text=text, fork=str(ctx.nouns['fork']))
    else:
        answer = _told(row, 'fork', text=text)
    if answer.get('error'):
        raise Stop(str(answer['error']), f'metaform dispatch sessions id={ctx.nouns["id"]}')
    return answer


BROADCASTS = 'broadcasts'  # the session and work id the kept broadcasts are lines of; no session or ticket has it


def broadcast(ctx: Context) -> dict[str, Any]:
    """One message to every agent session running on the project, each told as `message` tells one, so it reaches each
    agent as the person's own and the steering rules are the same, BASE-052: ticket workers, intake agents and the
    other chats, and the person's system agent only with system=true. The sessions are told at once, so one slow
    agent holds no other. Each thread keeps the message under `broadcast:<id>`, so it reads as a broadcast, and the
    project keeps one line of it, its text, time and recipients, read with `dispatch broadcasts`."""
    may_steer(ctx)
    store = ctx.require_store()
    given: Any = ctx.nouns['text']
    words = [str(word) for word in cast(list[Any], given)] if isinstance(given, (list, tuple)) else [str(given)]
    text = ' '.join(words).strip()
    if not text:
        raise Stop('A broadcast says something.', 'metaform dispatch broadcast -- "<message>"')
    if sender(ctx) or ctx.nouns.get('team'):
        from .orchestration import broadcast as team_broadcast
        return team_broadcast(ctx, text, ctx.nouns.get('team'))
    given_by: dict[str, Any] = {'by': role} if (role := sender(ctx)) else {}
    caller = os.environ.get('METAFORM_SESSION') if given_by else None  # an agent's broadcast does not tell itself
    running = [row for row in sessions(store) if row['state'] == 'running'
               and not (caller and row.get('runner') == caller)]
    # the person's own agent, by what it is: never an intake agent, which every broadcast reaches (UX review round 2,
    # 2026-10-17, combined F3)
    system = {str(row['session_id']) for row in system_sessions(store, running)}
    told = [row for row in running if ctx.nouns.get('system') is True or str(row['session_id']) not in system]
    if not told:
        raise Stop('No agent is working on this project.' if not running else
                   'Only your chat agent is working on this project; broadcast with system=true to tell it.',
                   'metaform dispatch sessions thread=false')
    sent_id = secrets.token_hex(8)
    from .orchestration import service
    owner = service(ctx)
    if owner is not None:
        for row in told:
            if owner.assignment(ctx, session_id=row['session_id']) is not None:
                owner.directed(ctx, row['session_id'], {'kind': 'user_direction', 'id': sent_id, 'text': text,
                                                       'at': home.now(), 'from': {'kind': 'user'}})

    def one(row: dict[str, Any]) -> dict[str, Any]:
        said = {key: row[key] for key in ('work_id', 'session_id', 'agent')}
        try:
            answer = tell(row, 'message', text=text, broadcast=sent_id, **given_by)
        except OSError as error:
            return {**said, 'delivered': False, 'reason': f'it did not answer: {error}'}
        if not answer.get('sent'):
            return {**said, 'delivered': False, 'reason': str(answer.get('error') or 'it did not take the message')}
        return {**said, 'delivered': True, 'steered': bool(answer.get('steered'))}

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=len(told)) as pool:
        recipients = list(pool.map(one, told))
    kept = {'id': sent_id, 'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'text': text,
            **({'by': role} if role else {}), 'recipients': recipients,
            'left_out': [{key: row[key] for key in ('work_id', 'session_id', 'agent')}
                         for row in running if row not in told]}
    from .signals import add_line
    with own_store(store).tables() as tx:
        add_line(tx, BROADCASTS, BROADCASTS, f'broadcast:{sent_id}', 'broadcast', json.dumps(kept, ensure_ascii=False))
    return kept


def broadcasts(ctx: Context) -> dict[str, Any]:
    """The broadcasts kept on the project, newest first: each one's text, time, and every session it went to with
    whether it was delivered."""
    try:
        with own_store(ctx.require_store()).tables(write=False) as tx:
            rows: Sequence[dict[str, Any]] = tx.rows('session_lines', {'session_id': BROADCASTS},
                                                     by=('session_id', 'seq'), limit=0).results
    except StoreError:
        rows = ()
    found = [json.loads(str(row['text'])) for row in reversed(rows) if row['kind'] == 'broadcast']
    limit = ctx.nouns.get('limit')
    return {'broadcasts': found[:limit] if isinstance(limit, int) and limit > 0 else found}


TIMER_MOST = 86400  # seconds an agent's timer may run, a day


def ask_consent(store: Store, message: str, *, tool: str, command: str, caution: str, wait: float = CONSENT_WAIT,
                work: str | None = None, runner: str | None = None) -> dict[str, Any]:
    """Ask the person for their consent to one call of a dispatched agent that is their decision, and wait for it:
    the agent's runner, found as its timer is, shows a consent card in its chat on the page, op `consent`, and the
    answer comes back as `action`, accept, decline or cancel; `error` says why it could not be asked (UX review,
    person-consent F5). The wait ends at the person's answer, or at `wait` seconds. The session is the calling agent's,
    METAFORM_WORK and METAFORM_SESSION, unless `work` and `runner` name it."""
    work, runner = work or os.environ.get('METAFORM_WORK'), runner or os.environ.get('METAFORM_SESSION')
    if not work or not runner:
        return {'action': 'cancel', 'error': 'This call does not come from a dispatched agent\'s session.'}
    held = (intake_store(store, work) or store) if intake_id(work) else store
    row = next((one for one in sessions(held, work, verify=False)
                if one.get('runner') == runner and one.get('state') == 'running'), None)
    if row is None:
        return {'action': 'cancel', 'error': 'Your session is not running here, so no card can be shown in its chat.'}
    try:
        answer = tell(row, 'consent', limit=wait + REPLY_LIMIT, message=message, tool=tool, command=command,
                      caution=caution, wait=wait)
    except OSError as error:
        return {'action': 'cancel', 'error': f'Your session\'s runner could not be reached: {error}.'}
    return answer if answer.get('action') else {'action': 'cancel', 'error': 'Your session\'s runner did not answer.'}


def own_session(store: Store, work: str | None = None, runner: str | None = None) -> dict[str, Any] | None:
    """The running session of the calling agent, METAFORM_WORK and METAFORM_SESSION unless `work` and `runner` name
    it, found as its timer is; None when the call comes from no dispatched agent's running session."""
    work, runner = work or os.environ.get('METAFORM_WORK'), runner or os.environ.get('METAFORM_SESSION')
    if not work or not runner:
        return None
    held = (intake_store(store, work) or store) if intake_id(work) else store
    return next((one for one in sessions(held, work, verify=False)
                 if one.get('runner') == runner and one.get('state') == 'running'), None)


def persons_word(store: Store, what: str, tickets: Sequence[str] = (), *, work: str | None = None,
                 runner: str | None = None) -> dict[str, Any] | None:
    """The person's word the calling agent's turn in flight acts on, as its runner keeps it, op `word`: only the
    person's own system agent has one, when the person's message in its chat (from the page with its key, or their
    own terminal) started the turn or was steered into it, or, in any of its turns, when every one of `tickets` is in
    the work it started, released or ordered on an earlier such message (`'covered': True`), until that work is done
    or the person stops it. None for any other turn, any other agent, or a runner that cannot be reached. `what` is
    the action asked, which the runner does not act on. When no word holds them and the person stopped the work every
    one of `tickets` was in, `{'stopped': True}`, so the refusal gives that reason."""
    row = own_session(store, work, runner)
    if row is None:
        return None
    try:
        answer = tell(row, 'word', what=what, tickets=list(tickets))
    except OSError:
        return None
    word = answer.get('word')
    if isinstance(word, dict):
        return cast(dict[str, Any], word)
    return {'stopped': True} if answer.get('stopped') is True else None  # the person stopped that work


def persons_word_acted(store: Store, word: dict[str, Any], said: str, tickets: Sequence[str] = (),
                       widen: bool = True, *, work: str | None = None, runner: str | None = None) -> None:
    """Record in the calling system agent's chat what it did on the person's word, op `acted`: the runner writes it as
    a notice of the thread with the message that authorized it. On the message the turn carries, and with `widen` (a
    start, a release, an order or a ticket added to wait on others; not a stop), the runner keeps `tickets`, with the
    tickets that wait on them and the open tickets the work waits on (`plan_of`), as the work that word covers, so the
    later waves of that work start in later turns with no second ask. On a word that covers earlier work, `plan` is
    instead the open tickets `tickets` wait on: the runner adds `tickets` to that work only when every one of those is
    in it, the next wave the agent planned of it."""
    row = own_session(store, work, runner)
    if row is None:
        return
    widen = widen and bool(tickets)
    if not widen:
        plan: list[str] = []
    elif word.get('covered'):
        plan = sorted(waited_on(store, tickets) - set(tickets))
    else:
        plan = sorted(plan_of(store, tickets) - set(tickets))
    with contextlib.suppress(OSError):
        tell(row, 'acted', word=str(word.get('id') or ''), said=said, tickets=list(tickets), plan=plan, widen=widen)


def plan_of(store: Store, tickets: Iterable[str]) -> set[str]:
    """The work the person's word covers for the tickets it acted on: `tickets`; every open ticket that waits on them
    (`after_work`), in turn, the later waves; and every open ticket any of those waits on, in turn, an earlier wave
    that must run first. It never walks from a ticket waited on to its other followers, and never through a ticket
    done or gone, so two plans that once waited on the same ticket stay two. Read in one transaction of the map's
    `after` table and one read of the open tickets."""
    found = {str(one) for one in tickets}
    try:
        with Store(store.project_id, module='map').tables(write=False) as tx:
            rows = tx.rows('after', limit=0).results
        opened = {record.id for record in store.work(open=True, limit=0).results}
    except StoreError:
        return found
    waits: dict[str, set[str]] = {}
    followers: dict[str, set[str]] = {}
    for row in rows:
        raw: Any = row['works']
        for before in ([str(one) for one in cast(list[Any], raw)] if isinstance(raw, list) else []):
            waits.setdefault(str(row['work_id']), set()).add(before)
            followers.setdefault(before, set()).add(str(row['work_id']))
    for edges in (followers, waits):  # the later waves first, then what any of the work waits on
        reach = [one for one in found if one in opened]
        while reach:
            for one in edges.get(reach.pop(), ()):
                if one in opened and one not in found:
                    found.add(one)
                    reach.append(one)
    return found


def waited_on(store: Store, tickets: Iterable[str]) -> set[str]:
    """The open tickets any of `tickets` waits on directly, `after_work`: one read of the map's `after` table per
    ticket and one of each ticket waited on."""
    found: set[str] = set()
    for work_id in tickets:
        raw: Any = after_of(store, work_id).get('after_work')
        for before in ([str(one) for one in cast(list[Any], raw)] if isinstance(raw, list) else []):
            try:
                if not ticket(store, before).done:
                    found.add(before)
            except (Stop, StoreError):
                continue
    return found


def waiting_in(store: Store, stopped: Iterable[str], among: Iterable[str]) -> set[str]:
    """Of `among`, the tickets that wait on one of `stopped`, in turn through `among`: read in one transaction of the
    map's `after` table. A part the person stopped takes with it only what waits on it."""
    held, found = set(among), set(stopped)
    try:
        with Store(store.project_id, module='map').tables(write=False) as tx:
            rows = tx.rows('after', limit=0).results
    except StoreError:
        return set()
    followers: dict[str, set[str]] = {}
    for row in rows:
        raw: Any = row['works']
        if str(row['work_id']) in held and isinstance(raw, list):
            for before in cast(list[Any], raw):
                followers.setdefault(str(before), set()).add(str(row['work_id']))
    reach, taken = list(found), set[str]()
    while reach:
        for one in followers.get(reach.pop(), ()):
            if one not in found:
                found.add(one)
                taken.add(one)
                reach.append(one)
    return taken


def persons_stopped(store: Store, tickets: Sequence[str] | None) -> None:
    """The person stopped work, Stop on these tickets or Stop all (None): their system agent's runner lets go of those
    tickets, and the tickets of the same work that wait on them, from each work their word started, op `uncover`, so
    that word starts nothing more of that part; the rest goes on. Stop all ends every such work."""
    try:
        found = system_sessions(store, sessions(store, verify=False))
    except StoreError:
        return
    for row in found:
        if row.get('state') == 'running' and row.get('port'):
            with contextlib.suppress(OSError):
                tell(row, 'uncover', tickets=None if tickets is None else list(tickets))


def ticket_label(store: Store, work_id: str) -> str:
    """A ticket as a record of what was done to it names it: its id and where it is."""
    try:
        record = ticket(store, work_id)
    except (Stop, StoreError):
        return work_id
    at = record.address or ' and '.join(end for end in (record.receiver_address, record.provider_address) if end)
    return f'{work_id} at {at}' if at else work_id


def on_word(ctx: Context, word: dict[str, Any] | None, said: str, tickets: Sequence[str] = (),
            widen: bool = True) -> dict[str, Any]:
    """After an action the person's word let their system agent take, `on_persons_word`: the record in its chat, with
    the tickets it acted on (`persons_word_acted`), and what the result says of it; nothing when the action needed no
    word."""
    if word is None:
        return {}
    with contextlib.suppress(Stop, StoreError):
        persons_word_acted(ctx.require_store(), word, said, tickets, widen)
    return {'on_word': {'text': word.get('text'), 'at': word.get('at'), 'did': said}}


def timer(ctx: Context) -> dict[str, Any]:
    """An agent's own timer, VIEW-005: set with seconds and a note, its session's runner wakes that session with the
    note as a turn when it is due; cancel=<id> takes one back; with neither, the timers set. It is the agent's own,
    found by the work and runner its session was started with, so it wakes no other session, and it ends with the
    session, since its runner holds it."""
    work, runner = os.environ.get('METAFORM_WORK'), os.environ.get('METAFORM_SESSION')
    if not work or not runner:
        raise Stop("A timer is an agent's own: it is set from an agent's session, for that session.",
                   'metaform help dispatch timer')
    store = ctx.require_store()
    held = (intake_store(store, work) or store) if intake_id(work) else store
    row = next((one for one in sessions(held, work, verify=False)
                if one.get('runner') == runner and one.get('state') == 'running'), None)
    if row is None or session_status(own_store(held), row, done=False)['state'] != 'running':
        raise Stop('Your session is not running here, so no timer can wake it.', f'metaform dispatch sessions id={work}')
    if ctx.nouns.get('cancel'):
        return _told(row, 'timer', cancel=str(ctx.nouns['cancel']))
    given: Any = ctx.nouns.get('text') or []
    note = ' '.join(str(word) for word in cast(list[Any], given)) if isinstance(given, (list, tuple)) else str(given)
    if ctx.nouns.get('seconds') in (None, ''):
        if note.strip():
            raise Stop('A timer is set with its seconds and what it wakes you for.', 'metaform dispatch timer seconds=60 -- "<note>"')
        return _told(row, 'timer')
    try:
        seconds = float(str(ctx.nouns['seconds']))
    except ValueError:
        seconds = -1.0
    if not 1 <= seconds <= TIMER_MOST or not note.strip():
        raise Stop(f'A timer runs from 1 to {TIMER_MOST} seconds and says what it wakes you for.',
                   'metaform dispatch timer seconds=60 -- "look where the person points"')
    return _told(row, 'timer', seconds=seconds, text=note.strip())


async def note(ctx: Context) -> dict[str, Any]:
    """A note to the agents working other open tickets, peer notes, `peering`: information, never steering."""
    from .peering import note as sent
    return await sent(ctx)


def notes(ctx: Context) -> dict[str, Any]:
    """The caller's peer notes with their delivery states, `peering`."""
    from .peering import notes as kept
    return kept(ctx)


def peers(ctx: Context) -> dict[str, Any]:
    """Who is at work where, and who else is in a part or file, `peering`."""
    from .peering import peers as present
    return present(ctx)


ATTACH_MOST = 25 * 1024 * 1024  # the largest file an agent attaches to its chat, as the person's own attachments
PUBLISHED = 'published'  # under the project's folder in the Metaform home: <session>/<id>/<name> and meta.json


def link(ctx: Context) -> dict[str, Any]:
    """A file linked to the element whose functionality it realizes, code.dispatcher.agent#3d: a ref of the sources
    layer naming its path, a record with an id that lasts, code.graph.knowledge#c, the refs the runner places files
    by, so the file is placed exactly from then on. The ref is
    named `ref`, a proper noun for what the file is, or from its path, and records who linked it and why. A file
    linked already at another place is a second ref here, with a name of its own; no ref moves. A ref is not an
    element and linking never makes one: an Address no element has is refused, with the call that adds the element
    to the map in use first, map refine, which grows the base under the intake's rules (LAYER-025); one a building,
    hidden or masked layer holds is named with the call that takes it into the base.
    The sources layer is made when the project has none. Linking it again where it is changes nothing."""
    from metaform.data import Node, Outcome
    store = ctx.require_store()
    root = Path(store.project().path).resolve()
    given = str(ctx.nouns['file']).strip().replace('\\', '/')
    address = str(ctx.nouns['node']).strip()
    named = given
    if Path(given).expanduser().is_absolute():
        found = Path(given).expanduser().resolve()
        here = Path.cwd().resolve()  # a worktree's file is named from the worktree, as the runner names it
        base = here if found.is_relative_to(here) and here.is_relative_to(root) else root
        if not found.is_relative_to(base):
            raise Stop(f'{given} is outside the project, {root}; only a file of the project is linked.',
                       'metaform dispatch link file=<a path from the project folder> node=<Address>')
        named = found.relative_to(base).as_posix()
    while named.startswith('./'):
        named = named[2:]
    named = named.rstrip('/')
    if not named or named == '.' or named.startswith('../'):
        raise Stop(f'{given} names no file of the project.', 'metaform dispatch link file=<path> node=<Address>')
    element = store.element(address)
    if element is None:
        held = store.element(address, raw=True)
        if held is not None:
            raise Stop(f'{address} is held by layer {held.layer}, which is building, hidden or masked, so {named} '
                       'cannot be linked there. When it is part of what the project does, take it into the map in use '
                       'first.', f'metaform map refine address={address} adopt=true reason=<why>')
        raise Stop(f'No element is at {address}, so {named} cannot be linked there; linking never makes an element. '
                   'Link the file to the element whose functionality it realizes, or add that element to the map in '
                   'use first, with the purpose record it serves.',
                   f'metaform map refine address={address} name=<its name> name_length=<n> role=<CQU, DE, SE or NE> '
                   'reason=<why>; then metaform map refine receiver=<its RE> elements=["' + address + '"] '
                   'purpose=<the OP> ef=<the EF> ifd=<sends, receives or both> reason=<why>')
    work, session = os.environ.get('METAFORM_WORK'), os.environ.get('METAFORM_SESSION')
    by = ' '.join(part for part in (f'work {work}' if work else '', f'session {session}' if session else '') if part)
    written = store.link_ref('path', named, Node('element', element.id), name=ctx.nouns.get('ref') or None,
                             by=by or ctx.surface, why=ctx.nouns.get('why') or None)
    if isinstance(written, Outcome):  # a name taken or reserved: nothing written, said as a result, BASE-044, CTX-066
        return {'file': named, 'node': address, 'ref': None, 'id': None, 'linked': False,
                'said': ' '.join(notice.message for notice in written.notices) or f'{named} was not linked.'}
    if any(notice.where == 'linked' for notice in written.notices):
        return {'file': named, 'node': address, 'ref': written.ref, 'id': written.id, 'linked': False,
                'said': f'{named} was already linked as {written.ref}.'}
    noted = [notice.message for notice in written.notices if notice.where == 'ref']
    return {'file': named, 'node': address, 'ref': written.ref, 'id': written.id, 'linked': True,
            'said': ' '.join([f'{named} is linked as {written.ref}.', *noted])}


def attach(ctx: Context) -> dict[str, Any]:
    """A file an agent made, attached to its own chat for the person to download, VIEW-039. It is the agent's own,
    found as its timer is, so it reaches only the thread of the session that published it. The file is read from the
    project's folder, a worktree in it among them, and copied whole under the project's folder in the Metaform home,
    by the session and an id of its own, so a later file of the same name, or a change to this one, never replaces
    what was attached; the page serves it by that session and id alone, never by a path."""
    work, runner = os.environ.get('METAFORM_WORK'), os.environ.get('METAFORM_SESSION')
    if not work or not runner:
        raise Stop("An attachment is an agent's own: it is published from an agent's session, into that session's "
                   'chat.', 'metaform help dispatch attach')
    store = ctx.require_store()
    held = (intake_store(store, work) or store) if intake_id(work) else store
    row = next((one for one in sessions(held, work, verify=False)
                if one.get('runner') == runner and one.get('state') == 'running'), None)
    if row is None or session_status(own_store(held), row, done=False)['state'] != 'running':
        raise Stop('Your session is not running here, so there is no chat to attach the file to; nothing was '
                   'attached.', f'metaform dispatch sessions id={work}')
    root = Path(store.project().path).resolve()
    given = Path(str(ctx.nouns['path'])).expanduser()
    source = (given if given.is_absolute() else Path.cwd() / given).resolve()
    if not source.is_relative_to(root) and not given.is_absolute():
        source = (root / given).resolve()
    if not source.is_relative_to(root):
        raise Stop(f'{given} is outside the project, {root}; only a file of the project is attached.',
                   'write the file in the project, such as under artifacts/, and attach it from there')
    if not source.is_file():
        raise Stop(f'No file at {source}; nothing was attached.', 'metaform dispatch attach path=<a file of the project>')
    size = source.stat().st_size
    if size > ATTACH_MOST:
        raise Stop(f'{source.name} is {size // 1024 // 1024} MB; an attachment is at most '
                   f'{ATTACH_MOST // 1024 // 1024} MB.', 'attach a smaller file, or say where it is')
    folder = home.project_folder(store.project_id)
    if folder is None:
        raise Stop(f'No project {store.project_id} is registered.', 'metaform list projects')
    name = str(ctx.nouns.get('name') or source.name)
    safe = ''.join(char if char.isalnum() or char in '._-' else '_' for char in Path(name).name).lstrip('.') or 'file'
    ident = secrets.token_hex(8)
    session_id = str(row['session_id'])
    target = folder / PUBLISHED / ''.join(char for char in session_id if char.isalnum() or char in '_-') / ident
    home.mkdir_private(target)
    data = source.read_bytes()
    home.write_private(target / safe, data)
    meta = {'id': ident, 'name': safe, 'size': len(data), 'type': mimetypes.guess_type(safe)[0] or
            'application/octet-stream', 'sha256': hashlib.sha256(data).hexdigest(),
            'source': source.relative_to(root).as_posix(), 'work_id': work, 'session_id': session_id,
            'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    home.write_private(target / 'meta.json', json.dumps(meta, ensure_ascii=False))
    def taken_back() -> None:  # a file the chat did not take leaves nothing behind
        shutil.rmtree(target, ignore_errors=True)
        try:
            target.parent.rmdir()
        except OSError:
            pass  # the session has other attachments

    try:
        told = _told(row, 'attach', attachment=meta)
    except Stop:
        taken_back()
        raise
    if told.get('error') or not told.get('attached'):
        taken_back()
        raise Stop(f'Your chat did not take the file: {told.get("error") or "no answer"}; nothing was attached.',
                   f'metaform dispatch sessions id={work}')
    return {'attached': meta, 'said': f'{safe} is attached to your chat, {len(data)} bytes; the person downloads it '
                                      'there.'}


def interrupt(ctx: Context) -> dict[str, Any]:
    """Cancel the current turn while keeping the session reachable and queued messages in order."""
    may_steer(ctx)
    row = _running_or_stop(ctx.require_store(), ctx.nouns['id'], ctx.nouns.get('session'))
    direction = str(ctx.nouns.get('direction') or '')
    envelope: dict[str, Any] | None = None
    if sender(ctx):
        from .orchestration import identity, service
        owner = service(ctx)
        mine, actual = identity(ctx)
        if owner is None or not owner.owns(ctx, str(mine['session_id']), str(row['session_id'])):
            raise Stop('Only the recorded GC can interrupt a member of its own swarm.',
                       'metaform dispatch note to=<session> -- "<message>"')
        envelope = {'kind': 'gc_direction', 'from': actual, 'body': direction,
                    'id': secrets.token_hex(16), 'at': home.now()}
        owner.interrupted(ctx, str(row['session_id']), envelope)
    elif direction:
        from .orchestration import service
        owner = service(ctx)
        envelope = {'kind': 'user_direction', 'from': {'agent': 'person'}, 'body': direction,
                    'id': secrets.token_hex(16), 'at': home.now()}
        if owner is not None and owner.assignment(ctx, session_id=str(row['session_id'])):
            owner.interrupted(ctx, str(row['session_id']), envelope)
    result = _told(row, 'interrupt', direction=envelope)
    if result.get('error'):
        raise Stop(str(result['error']), f'metaform dispatch stop {ctx.nouns["id"]}')
    return result


def stop(ctx: Context) -> dict[str, Any]:
    """Stop the agent working a ticket: session/cancel, then its process group ends. A runner that holds the session
    and does not answer, such as one under load, has its process group ended here and its session recorded as stopped,
    so the next Call or resume starts it once. The person stopping their system agent turns dispatch_stay_connected
    off for the project, `disconnect`, and the result says so; the person stopping any other agent while Full Auto
    agents is checked turns that off, `paused`, so no waiting ticket starts in its place, and the result says so. A
    dispatched agent stops one only on the person's word, as `start`."""
    may_steer(ctx)
    store = ctx.require_store()
    word = stop_word(ctx, [str(ctx.nouns['id'])])
    acting = person_asks(ctx) or word is not None
    if intake_id(ctx.nouns['id']) and not ctx.nouns.get('session'):
        starting = intake_under_way(store)
        if starting is not None and starting['state'] == 'starting' and starting['work_id'] == ctx.nouns['id']:
            if word is None:
                may_stop(ctx, starting)
            return ended_launch(store, starting)
    from .orchestration import service
    owner = service(ctx)
    try:
        row = _running_or_stop(store, ctx.nouns['id'], ctx.nouns.get('session'), gone_ok=True)
    except Stop:
        starting = [entry for entry in launches() if entry.get('project') == store.project_id
                    and entry.get('work_id') == ctx.nouns['id']] if not ctx.nouns.get('session') else []
        if acting and starting:
            work_id = str(ctx.nouns['id'])
            persons_stopped(store, [work_id])
            if owner is not None:
                owner.stopped(ctx, work_id=work_id, by='user')
            paused(ctx, store, None)
            record = held_ticket(store, work_id)
            if record is not None and (record.taken_by or '').startswith('dispatch starting '):
                given_back_reservation(store, work_id, str(record.taken_by))
            for entry in starting:
                ended_launch_group(int(entry['pid']))
            for session in sessions(store, work_id, verify=False):
                if session.get('pid') in {entry['pid'] for entry in starting} and session['state'] == 'running':
                    ended_gone(store, session, None)
            return {'stopped': True, 'work_id': work_id, 'session_id': None, 'starting': True,
                    'how': 'stopped while starting'}
        # At capacity one a waiting GC has ended its adapter. The user's Stop still names the delivery ticket,
        # including a not-yet-launched assignment, and must cancel its descendants and recorded continuations.
        assignment = owner.assignment(ctx, work_id=str(ctx.nouns['id'])) if owner is not None else None
        if not acting or assignment is None or owner is None:
            raise
        stopped_work = owner.stopped(ctx, work_id=str(ctx.nouns['id']), by='user')
        persons_stopped(store, stopped_work)
        # a ticket the sessionless specialist owner held, waiting for its role, goes back to wait: the person's stop
        # ended that delivery, so nothing holds it (2026-10-20)
        for work in stopped_work:
            record = ticket(store, work)
            if record.taken and record.taken_by == f'Specialist {work}' and not record.done:
                store.move_work(work, 'backlog' if record.held else 'todo', kept=True)
        held = paused(ctx, store, None)
        ended: list[dict[str, Any]] = []
        for child in sessions(store, verify=False):
            if child['work_id'] in stopped_work and child['state'] == 'running':
                ended.append(ended_by_person(store, child, None if acting else stopper(ctx)))
        for launch in launches():
            if launch.get('project') == ctx.project and launch.get('work_id') in stopped_work:
                ended.append(ended_launch(store, launch))
        return {'stopped': True, 'work_id': str(ctx.nouns['id']), 'assignments': stopped_work,
                'sessions': ended, **(QUEUE_PAUSED if held else {})}
    if word is None:  # on the person's word their system agent stops what it did not start
        may_stop(ctx, row)
    if word is None or not word.get('covered'):  # the person's stop, or one their message asked: the work it is part
        # of starts no more on their earlier word, before this agent's end can wake their system agent
        persons_stopped(store, [str(row['work_id'])])
    stopped_work: list[str] = owner.stopped(ctx, work_id=str(row['work_id']),
        by='user' if acting else stopper(ctx)) if owner is not None else []
    for child in sessions(store, verify=False) if len(stopped_work) > 1 else []:
        if child['work_id'] in stopped_work and child['session_id'] != row['session_id'] and child['state'] == 'running':
            ended_by_person(store, child, None if acting else stopper(ctx))
    if row.get('gone'):  # its runner had ended already: nothing to stop, and the person is told so
        return ended_gone(store, row, None if acting else stopper(ctx))
    off = disconnect(ctx, store, row)
    held = paused(ctx, store, row)
    result = ended_by_person(store, row, None if acting else stopper(ctx))
    if result.get('error'):  # a session that ends elsewhere, such as in the person's editor, BASE-062
        if off:  # it still runs, so it stays connected
            settings.put('dispatch_stay_connected', True, Path(store.project().path))
        if held:  # nothing was stopped, so the queue goes on as it was
            settings.put('dispatch_autostart', True, Path(store.project().path))
        raise Stop(str(result['error']), f'metaform dispatch sessions id={ctx.nouns["id"]}')
    return {**result, **({'stay_connected': False} if off else {}), **(QUEUE_PAUSED if held else {}),
            **on_word(ctx, word, f'stopped the agent on ticket {ticket_label(store, str(row["work_id"]))}',
                      [str(row['work_id'])], widen=False)}


def stop_work(ctx: Context, work_ids: Sequence[str]) -> list[str]:
    """Stop every session or admitted launch on selected tickets through the canonical stop."""
    from dataclasses import replace
    if not work_ids:
        return []
    store = ctx.require_store()
    selected = set(work_ids)
    running = [row for row in sessions(store, verify=False)
               if row['work_id'] in selected and row['state'] == 'running']
    stopped: list[str] = []
    for row in running:
        stop(replace(ctx, nouns={'id': row['work_id'], 'session': row['session_id']}))
        stopped.append(str(row['session_id']))
    # The gate may have admitted a runner before the wipe's halt, before its ACP session exists.
    for entry in launches():
        if entry.get('project') == store.project_id and entry.get('work_id') in selected:
            if any(row.get('pid') == entry['pid'] for row in running):
                continue
            result = stop(replace(ctx, nouns={'id': entry['work_id']}))
            stopped.append(str(result.get('session_id') or f'starting:{entry["pid"]}'))
    return stopped


# What a stop by the person that turned Full Auto off says. UX review round 1, 2026-10-17
# (interrupt-failure-recovery F6): each stop with Full Auto on started the next waiting ticket in its place, so a
# person stopping agents on a machine at its limit was refilled as fast as they stopped.
QUEUE_PAUSED = {'autostart': False,
                'notice': 'Full Auto is now off for this project, so no waiting ticket starts in the place of '
                          'what you stopped; check it to start the queue again.'}


def paused(ctx: Context, store: Store, row: dict[str, Any] | None) -> bool:
    """The person's own stop of an agent, on the page or the command line, turns Full Auto off for the project
    before the stop, so no pass of the agent starter in between starts another, as `disconnect` does for the system
    agent, which takes no slot and is left to it. An agent's stop changes no setting of the person's. Returns whether
    it was turned off."""
    if not person_asks(ctx) or not ctx.setting('dispatch_autostart') or not ctx.setting('dispatch_pause_on_stop'):
        return False
    if row is not None and system_sessions(store, [row]):
        return False
    settings.put('dispatch_autostart', False, Path(store.project().path))
    return True


def stopper(ctx: Context) -> str | None:
    """Who a stop is by, as the session's end records it: None for the person, else the calling agent by its role and
    its runner, so the board never blames the person for an agent's stop (ux-verify-combined F5)."""
    if person_asks(ctx):
        return None
    runner = os.environ.get('METAFORM_SESSION') or ''
    return f'{sender(ctx) or "an"} agent{f" {runner[:8]}" if runner else ""}'


def started_by_caller(row: dict[str, Any]) -> bool:
    """Whether the calling agent started the runner of a session, as the gate's ledger names its starter, or the
    session is the caller's own."""
    me = os.environ.get('METAFORM_SESSION')
    if not me:
        return False
    if row.get('runner') == me:
        return True
    pid = row.get('pid')
    entry = _read_json(ledger() / f'{pid}.json') if isinstance(pid, int) else None
    return entry is not None and entry.get('by') == me


def stop_word(ctx: Context, tickets: Sequence[str] = ()) -> dict[str, Any] | None:
    """A user's delegated stop, independent of whether routine autonomous work asks for approval.

    The runner authenticates the direction; a role prompt or an approve-all policy cannot impersonate the user.
    """
    if person_asks(ctx):
        return None
    from metaform.module import persons_word as user_word
    return user_word(ctx.folder, 'Stopping agents', ctx.project, tickets)


def may_stop(ctx: Context, row: dict[str, Any]) -> None:
    """An agent stops only the agents it started, and itself; every other agent is the person's to stop, CLI-011."""
    if person_asks(ctx) or started_by_caller(row):
        return
    raise PersonsDecision(f'An agent stops only the agents it started; the agent on work {row["work_id"]} is the '
                          "person's to stop.", f'metaform dispatch stop {row["work_id"]}')


def stop_all(ctx: Context) -> dict[str, Any]:
    """Stop every agent of the project, or with home=true of every project of this Metaform home: Full Auto
    is turned off first, and Stay connected too at the person's own call, so nothing starts in their place; then each
    running session ends as the person's stop ends it, all at once, so none is retried; then each runner still starting
    is ended, and the ticket it was reserved goes back to To do. A session the person's editor runs is left to the
    editor, and an agent calling it is never stopped by its own call. UX review round 1, 2026-10-17
    (dispatch-concurrency F5, interrupt-failure-recovery F6, settings-govern-behavior F3, runaway-and-load F4,
    web-gui-controls F5): nothing stopped every agent at once, so a machine at its limit needed one stop per agent,
    each of which started the next waiting ticket.

    The person's Stop all is a halt, `halt`, held while it stops and kept after it: every start asked for before it
    is refused, a Start all half done or an autostart pass that reserved its tickets a moment before among them. An
    agent's call stops only the agents it started, in its own project, changes no setting and halts nothing; home=true
    is the person's alone (UX review round 2: ux-verify-combined F1 and F5, spawn-gate F1). A dispatched agent stops
    them all only on the person's word, as `start`, and then stops as the person does, turning Full Auto off."""
    may_steer(ctx)
    word = stop_word(ctx)
    person = person_asks(ctx)
    if not person and word is None and not os.environ.get('METAFORM_SESSION'):
        # neither the person nor an agent that could have started a runner: refused whole, never half run
        raise PersonsDecision("Stopping every agent of this project is the person's decision; this call carries neither "
                              "the person's consent nor an agent's session.", 'metaform dispatch stop-all')
    if ctx.nouns.get('home') and not person and word is None:
        raise PersonsDecision("Stopping every agent on this machine is the person's decision; an agent stops only the "
                              'agents it started.', 'metaform dispatch stop-all home=true')
    by = stopper(ctx)
    halts: list[tuple[str, dict[str, Any]]] = []
    if ctx.nouns.get('home'):
        for project in home.projects():  # written before the ledger is read, so no runner starts unseen after it
            with contextlib.suppress(OSError):
                halts.append((project.project_id, halt(project.project_id, 'stop-all', held=True)))
        busy = {str(entry.get('project')) for entry in launches()}
        found = [project for project in home.projects() if project.project_id in busy or project.project_id == ctx.project]
    else:
        store = ctx.require_store()
        found = [project for project in home.projects() if project.project_id == store.project_id]
        if person or word is not None:
            halts.append((store.project_id, halt(store.project_id, 'stop-all', held=True)))
    try:
        return stopped_all(ctx, found, person, by, word, dict(halts))
    finally:
        for project_id, entry in halts:
            with contextlib.suppress(OSError):
                let_go(project_id, entry)


def stopped_all(ctx: Context, found: Sequence[Any], person: bool, by: str | None,
                word: dict[str, Any] | None = None, halts: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """`stop_all`'s stops, under its halt. On the person's word, `word`, their system agent stops every agent but
    itself and turns Full Auto off, as their own Stop all does. Stop all is a pause of the whole machine: each
    assignment it stops is marked as stopped by it, `every`, and listed in the project's halt, `halts`, so Full Auto
    turned on again resumes it, `resume_paused`; a stop the person gave one ticket on its own is never listed."""
    acting = person or word is not None
    me = os.environ.get('METAFORM_SESSION') if not person else None
    own_work = os.environ.get('METAFORM_WORK') if not person else None
    stopped: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    turned_off: list[str] = []
    for project in found:
        folder = Path(project.path)
        try:
            held = Store(project.project_id)
            # Full Auto off and Stay connected off at the person's own call alone, as their stop of the system agent
            # does, `disconnect`: an agent's stop changes no setting of the person's, VIEW-042 (spawn-gate F1)
            for key in (('dispatch_autostart', 'dispatch_stay_connected') if person
                        else ('dispatch_autostart',) if acting else ()):
                if settings.value(key, folder):
                    settings.put(key, False, folder)
                    turned_off.append(f'{project.project_id}:{key}')
            if acting:
                persons_stopped(held, None)  # Stop all: no work the person's word started goes on
                from .orchestration import service
                project_ctx = context('dispatch', folder, project=project.project_id)
                owner = service(project_ctx)
                if owner is not None:
                    for assignment in owner.assignments(project_ctx):
                        if not assignment.get('stop'):
                            owner.stopped(project_ctx, work_id=assignment['work_id'], by='user', every=True)
                    entry = (halts or {}).get(project.project_id)
                    if entry is not None:  # the work it paused: what was live, never work already ended
                        paused = [one['work_id'] for one in owner.assignments(project_ctx)
                                  if one['state'] == 'stopped' and cast(dict[str, Any], one.get('stop') or {}).get('every')]
                        with contextlib.suppress(OSError):
                            keep_paused(project.project_id, entry, list(dict.fromkeys([*entry['paused'], *paused])))
            rows = [row for row in sessions(held, verify=False) if row['state'] == 'running'
                    and runner_of(row.get('pid')) == row['work_id'] and (me is None or row.get('runner') != me)
                    and (acting or started_by_caller(row))]
        except (StoreError, Stop, settings.SettingError) as error:
            failed.append({'project': project.project_id, 'error': str(error)})
            continue
        with ThreadPoolExecutor(max_workers=max(1, min(len(rows), 16))) as pool:
            ends = [(row, pool.submit(ended_by_person, held, row, by)) for row in rows]
        for row, future in ends:
            try:
                result = future.result()
            except (Stop, OSError) as error:
                failed.append({'project': project.project_id, 'work_id': row['work_id'], 'error': str(error)})
                continue
            if result.get('error'):
                failed.append({'project': project.project_id, 'work_id': row['work_id'], 'error': result['error']})
            else:
                stopped.append({'project': project.project_id, 'work_id': row['work_id'],
                                'session_id': row['session_id']})
        made = {row.get('pid') for row in rows}
        ended_starting: list[int] = []
        seated: set[int] = set()
        for entry in launches():  # a runner the gate started that has not made its session yet
            if entry.get('project') != project.project_id or entry['pid'] in made or entry['pid'] == os.getpid():
                continue
            if own_work and entry.get('work_id') == own_work:  # the caller's own runner, never ended by its own call
                continue
            if not acting and (me is None or entry.get('by') != me):  # neither the person nor its starter
                continue
            if entry.get('seat'):  # a roundtable's seats, held by its follower, which ends its table when asked
                if entry['pid'] not in seated:
                    seated.add(entry['pid'])
                    stopped_seats(int(entry['pid']))
                    stopped.append({'project': project.project_id, 'work_id': entry.get('work_id'), 'table': True})
                continue
            # its reservation first, so the start the stop ends is not counted as a start that failed, `start_failed`
            with contextlib.suppress(StoreError, Stop):
                record = held_ticket(held, str(entry.get('work_id')))
                if record is not None and (record.taken_by or '').startswith('dispatch starting '):
                    given_back_reservation(held, record.id, str(record.taken_by))
            # then the runner and its agent's own group: a runner still waiting on its agent's first answer cannot end
            # it, so a stop while starting left the agent running (intake-single-flight F3)
            ended_launch_group(int(entry['pid']))
            ended_starting.append(int(entry['pid']))
            stopped.append({'project': project.project_id, 'work_id': entry.get('work_id'), 'starting': True})
        if ended_starting:
            # a runner that made its session after the sessions were read: that session ends as this stop, by the
            # person or the agent `by` names, never as a runner that died, so its card tells the truth and it stays
            # resumable (UX combined replay, 2026-10-17)
            with contextlib.suppress(StoreError, Stop, OSError):
                for row in sessions(held, verify=False):
                    if row.get('pid') in ended_starting and (row['state'] == 'running'
                                                             or str(row.get('how') or '') in DIED):
                        ended_gone(held, row, by)
    return {'stopped': stopped, 'failed': failed, 'turned_off': turned_off,
            **({'notice': 'Full Auto is off, so nothing starts again until you check it.'}
               if turned_off else {}),
            **(on_word(ctx, word, f'stopped every agent ({len(stopped)}) and turned Full Auto off')
               if word is not None else {})}


def ended_launch(store: Store, starting: dict[str, Any]) -> dict[str, Any]:
    """The person's stop of an intake agent still starting, before its session is made, VIEW-045: its runner's process
    group ends, which lets go of `intake.agent`, and its launch's row and record go, so no session is ever made."""
    work_id = str(starting['work_id'])
    pid = starting.get('pid')
    held = store.intake_agent()
    if held is not None and held.get('work') == work_id:
        pid = held.get('pid', pid)
    if isinstance(pid, int) and runner_of(pid) == work_id:
        ended_launch_group(pid)  # and its agent's own group, started already or not (intake-single-flight F3)
    with Store(store.project_id, module='dispatch').tables() as tx:
        tx.delete('raised', {'work_id': work_id})
        tx.concern(work_id=work_id, kind='session')
    store.forget_intake_launch(work_id)
    return {'work_id': work_id, 'session_id': None, 'stopped': True, 'pid': pid, 'how': 'stopped while starting'}


def ended_gone(store: Store, row: dict[str, Any], by: str | None) -> dict[str, Any]:
    """A stop of a session whose runner had ended already, by a kill or a crash: what the runner left running, its
    agent's group and its terminals, is ended where its record says, its row is written as ended by the stop, so no
    surface shows it at work and the supervisor does not resume it, and the stop says it was gone."""
    from .recovery import swept
    raw: Any = row.get('recovery')
    if isinstance(raw, dict):
        with contextlib.suppress(OSError, ValueError, subprocess.SubprocessError):
            swept(cast(dict[str, Any], raw))
    work_id, session_id = str(row['work_id']), str(row['session_id'])
    held = base_store((intake_store(store, work_id) or store) if intake_id(work_id) else store, row)
    if row['state'] == 'ended':  # written as a death already: now as the stop, so the supervisor leaves it
        with own_store(held).tables() as tx:
            kept = tx.get('agent_sessions', {'session_id': session_id})
            if kept is not None and kept['state'] == 'ended' and str(kept.get('how') or '') in DIED:
                tx.update('agent_sessions', {'session_id': session_id}, {'how': stopped_how(by)})
                tx.concern(work_id=work_id, session_id=session_id, kind='session')
        return {'work_id': work_id, 'session_id': session_id, 'stopped': True, 'gone': True,
                'how': 'it had ended already: its runner is no longer running'}
    taker = f'{row["agent"]} {session_id}'
    record = None if intake_id(work_id) else held_ticket(held, work_id)
    release(held, work_id, taker, record is not None and record.taken_by == taker, session_id, stopped_how(by),
            row.get('runner'))
    return {'work_id': work_id, 'session_id': session_id, 'stopped': True, 'gone': True,
            'how': 'it had ended already: its runner is no longer running'}


def stopped_how(by: str | None) -> str:
    """How a stop ends a session: by the person, or by the agent `by` names."""
    return f'stopped by {by}' if by else 'stopped by the person'


def stop_end(how: str) -> bool:
    """Whether a session ended at someone's word, the person's or an agent's, or with its work: never retried, P012."""
    return how in PERSON_ENDS or how.startswith('stopped by ') or how == 'orchestration suspended'


def ended_held(store: Store, row: dict[str, Any], by_agent: str | None = None) -> dict[str, Any]:
    """End a runner that holds a session and does not answer, as its own stop would: its process group, then its row
    and its ticket through `release`."""
    pid, work_id, session_id = int(row['pid']), str(row['work_id']), str(row['session_id'])
    end_group(pid)
    held = base_store((intake_store(store, work_id) or store) if intake_id(work_id) else store, row)
    by = f'{row["agent"]} {session_id}'
    record = None if intake_id(work_id) else held_ticket(held, work_id)  # its ticket in the metaform it is pinned to
    took = record is not None and record.taken_by == by
    how = stopped_how(by_agent)
    release(held, work_id, by, took, session_id, how, row.get('runner'))
    return {'work_id': work_id, 'session_id': session_id, 'stopped': True, 'pid': pid, 'how': how}


def ended_by_person(store: Store, row: dict[str, Any], by: str | None = None) -> dict[str, Any]:
    """The person's stop of one running session, or with `by` an agent's: its runner ends it and answers once its row
    says it ended; a runner that holds it and does not answer is ended here, `ended_held`. An `error` in the result is
    a session that ends elsewhere, such as in the person's editor, BASE-062."""
    try:
        return tell(row, 'stop', REPLY_LIMIT, by=by) if by else tell(row, 'stop')
    except OSError as error:
        if runner_of(row.get('pid')) != row['work_id']:  # only a pid whose command line is this ticket's runner
            raise unanswered(row, error) from None
        return ended_held(store, row, by)


def new(ctx: Context) -> dict[str, Any]:
    """A new conversation with the agent on a ticket, /new and /clear in the chat dock, code.interface.graphical#9b: its
    session ends as the person's stop ends it, and one starts in the same role with nothing resumed, whatever
    dispatch_resume_chats says: the person's system agent, a chat they summoned about something, or the agent working
    the ticket, which takes it again. The ended session stays readable as a closed thread. Unlike stop it changes no
    setting, since the person goes on talking: dispatch_stay_connected stays as it is. Everything a start needs is
    checked before the session ends, so a refused start leaves it running."""
    may_steer(ctx)
    store = ctx.require_store()
    work_id = str(ctx.nouns['id'])
    if intake_id(work_id):
        raise Stop('An intake agent goes on with the intake being recorded; stop it and start the intake again.',
                   f'metaform dispatch stop {work_id}')
    row = _running_or_stop(store, work_id, ctx.nouns.get('session'))
    if editor(row):
        raise Stop('A session your editor runs starts again in your editor.', f'metaform dispatch sessions id={work_id}')
    agent, session_id = str(row['agent']), str(row['session_id'])
    about = (session_state(store, session_id) or {}).get('about')
    worker = not summoned(row)
    if not worker and not about:  # a merge preparation or a question's agent: a role with nothing to start again
        raise Stop(f'Session {session_id} is not a conversation or a ticket\'s agent; stop it instead.',
                   f'metaform dispatch stop {work_id} session={session_id}')
    if worker:
        if shutil.which(argv(start_command(ctx, agent))[0]) is None:
            raise Stop(f'The start command of {agent} is not found on this system.',
                       f'metaform set --dispatch-{agent} "<command>"')
        mcp_server(Path(store.project().path))
        budget_stop(ctx, store, work_id)
    elif found_command(ctx, agent) is None:
        raise Stop(f'The start command of {agent} is not found on this system.', f'metaform set --dispatch-{agent} "<command>"')
    ended = ended_by_person(store, row)
    if ended.get('error'):
        raise Stop(str(ended['error']), f'metaform dispatch sessions id={work_id}')
    if not worker:
        if about == 'system':
            forget_ends(store, work_id)  # the person acted on their system agent, as a Call does
        return {**converse(ctx, store, work_id, agent, [] if about == 'system' else [f'talk={about}']),
                'ended': session_id}
    reservation = 'dispatch starting ' + secrets.token_hex(16)
    record = ticket(store, work_id)
    checked_sessions = sessions(store, record.id if glyph_of(ctx, record) is None else None)
    with store.atomic():  # the ticket the ended session held is taken again at once, so no other start takes it between
        if ticket(store, work_id).taken_by == f'{agent} {session_id}':
            store.move_work(work_id, 'todo', kept=True)  # taken again at once: no place changes
        startable(ctx, store, ticket(store, work_id), agent, checked_sessions=checked_sessions)
        store.take_work(work_id, by=reservation)
    ctx.nouns['agent'] = agent
    given: dict[str, str | None] = {'prompts': None, 'mode': None, **launch_options(store, work_id)}
    return {**run_reserved(ctx, reservation, given), 'ended': session_id}


# What `wait` waits for: a ticket done; its agent stopped with it open, idle at a turn's end or its session ended; or
# any signal on it, BASE-057. A ticket's stopped is a signal of its latest session, so one an earlier session left
# does not wake a wait on the agent at work now.
UNTIL = ('done', 'stopped', 'signal')
STOPPED = ('stopped-open', 'not-smooth')
STAMP = '%Y-%m-%dT%H:%M:%SZ'  # the form of a ticket's done time and a signal's time, compared as text


def ended(record: WorkRecord) -> str:
    """How a closed ticket reads to a wait: done when it was completed, or its outcome, cancelled or failed, P232."""
    return 'done' if (record.outcome or 'completed') == 'completed' else str(record.outcome)


def named_tickets(store: Store, work_ids: Collection[str]) -> list[WorkRecord]:
    """The tickets among `work_ids` that exist, each read alone; an intake session's id, or a ticket since removed,
    names none."""
    found: list[WorkRecord] = []
    for work_id in sorted(work_ids):
        if intake_id(work_id):
            continue
        try:
            found.append(store.ticket(work_id).work)
        except NewerStore:
            raise
        except StoreError:
            continue
    return found


def awaited(store: Store, until: str, work_id: str | None, since: str | None,
            named: Collection[str] | None = None) -> list[dict[str, Any]]:
    """The tickets that meet `until`, each with the time it met it, oldest first. With a work id, that ticket as it
    is now, and a done one ends any wait since nothing comes after it; with none, every ticket of the project that met
    it at or after `since`, or with `named`, only those tickets: the ones the changes a wait heard named, `awaits`."""
    from .signals import rows
    if until == 'done':
        records = [ticket(store, work_id)] if work_id else named_tickets(store, named) if named is not None \
            else store.work(open=False, limit=0).results
        return sorted(({'work_id': record.id, 'state': ended(record), 'at': record.done,
                        **ticket_work_status(record, (), ())} for record in records
                       if record.done and (work_id or record.done >= str(since))), key=lambda found: found['at'])
    if work_id:
        record = ticket(store, work_id)
        if record.done:
            return [{'work_id': record.id, 'state': ended(record), 'at': record.done,
                     **ticket_work_status(record, (), ())}]
        open_ids = {record.id}
    elif named is not None:
        open_ids = {record.id for record in named_tickets(store, named) if not record.done}
    else:
        open_ids = {record.id for record in store.work(open=True, limit=0).results}
    # one ticket's rows, those of the tickets named, or every ticket's; the sessions only for until=stopped
    scope: list[str | None] = [work_id] if work_id else [*sorted(open_ids)] if named is not None else [None]
    latest = {row['work_id']: row['session_id'] for one in scope for row in sessions(store, one, verify=False)} \
        if until == 'stopped' else {}
    held: dict[str, list[dict[str, Any]]] = {}
    for row in (row for one in scope for row in rows(store, one)):
        if row.get('work_id') not in open_ids or (since and row['at'] < since):
            continue
        if until == 'stopped' and (row['signal'] not in STOPPED
                                   or (row.get('session_id') or '') != latest.get(row['work_id'], '')):
            continue
        held.setdefault(row['work_id'], []).append(row)
    return sorted(({'work_id': found, 'state': until, 'at': signals[-1]['at'], 'signals': signals,
                    **ticket_work_status(ticket(store, found), sessions(store, found), rows(store, found))}
                   for found, signals in held.items()), key=lambda found: found['at'])


def awaits(payload: dict[str, Any], project_id: str, until: str, work_id: str | None) -> bool:
    """Whether a `map.changed` from another process can change what a wait answers, decided from the change alone,
    BASE-053: one of its project that names its ticket, or, waiting on every ticket, names some ticket, or does not
    say which; and that wrote a ticket, for until=done or a wait on one ticket, which that ticket's done ends, or a
    signal otherwise. What it wrote is read from its `kinds`, else its tables; a change that says neither may have
    written anything. Thread lines, memories and map writes that close no ticket wake nothing."""
    if payload.get('project') != project_id:
        return False
    named: Any = payload.get('work_ids')
    if isinstance(named, list) and (work_id not in named if work_id else not named):
        return False
    tickets, signals = until == 'done' or work_id is not None, until != 'done'
    kinds: Any = payload.get('kinds')
    if isinstance(kinds, list):
        return tickets and 'ticket' in kinds or signals and 'signal' in kinds
    tables: Any = payload.get('tables')
    if tables == 'dispatch':  # a runner's own tables, which hold no ticket; a signal it raises is said with them
        return not isinstance(payload.get('dispatch_tables'), list) or signals and 'signal' in payload
    if isinstance(tables, list):
        return tickets and 'work' in tables or signals and any(str(table).startswith('dispatch.')
                                                               for table in cast(list[Any], tables))
    return True


def waiting_call(until: str, work_id: str | None, since: str | None) -> str:
    """The call that waits again, in the command line's order: the required noun first."""
    return ' '.join(['metaform dispatch wait', f'until={until}', *([f'id={work_id}'] if work_id else []),
                     *([f'since={since}'] if since else [])])


async def wait(ctx: Context) -> dict[str, Any]:
    """Block until a ticket is done, its agent stopped with it open, or a signal is raised on it, for at most
    dispatch_wait_seconds, so an orchestrator drives start, wait and read, BASE-052. With no id it waits on every
    ticket of the project and names the ones that woke it, so one call serves every worker. Each answer's `next` is
    the call that hears what comes after it: from the second the answer was read, or, when pending, from the same
    `since`, so a ticket that changes between two calls is not lost; one that changed in that very second may be named
    again. It wakes on map changes from other processes, BASE-053, never on a timer, and the limit ends the one wait,
    QUAL-015; a change made in this same process is heard only at the next change or the limit."""
    store = ctx.require_store()
    until = str(ctx.nouns['until'])
    if until not in UNTIL:
        raise Stop(f'until is one of {", ".join(UNTIL)}, not {until}.', 'metaform help dispatch wait')
    work_id = str(ctx.nouns.get('id') or '') or None
    given = ctx.nouns.get('since')
    since = str(given) if given else None if work_id else time.strftime(STAMP, time.gmtime())
    if since is not None:
        try:
            time.strptime(since, STAMP)
        except ValueError:
            raise Stop(f'since is a UTC time as 2026-10-11T04:18:04Z, not {since}.',
                       'metaform help dispatch wait') from None
    if work_id:
        await asyncio.to_thread(ticket, store, work_id)  # an unknown ticket is refused before anything waits
    loop = asyncio.get_running_loop()
    heard = asyncio.Event()
    named: set[str] | None = set()  # the tickets the changes heard since the last read name; None when one did not say

    def note(work_ids: list[str] | None) -> None:
        nonlocal named
        named = None if work_ids is None or named is None else named | set(work_ids)
        heard.set()

    def told(payload: dict[str, Any]) -> None:
        # decided from the change alone, `awaits`, so one that is not this wait's reads nothing; a wait on every ticket
        # reads again only the tickets the changes name, and those heard while a read runs merge into the next one
        if awaits(payload, store.project_id, until, work_id):
            given: Any = payload.get('work_ids')
            loop.call_soon_threadsafe(note, [str(one) for one in cast(list[Any], given)] if isinstance(given, list)
                                      else None)
    def died(entry: dict[str, Any]) -> None:
        # a runner of this project that ended without a word, killed or crashed: heard at once, from its lease
        if entry.get('project') == store.project_id and (work_id is None or entry.get('work_id') == work_id):
            loop.call_soon_threadsafe(note, [str(entry.get('work_id') or '')])

    limit = float(ctx.setting('dispatch_wait_seconds'))
    deadline = loop.time() + limit
    scope: set[str] | None = None  # the first read is of every ticket
    with ctx.listen(told), deaths_heard(died) as deaths:
        while True:
            heard.clear()  # before the read, so a change during it wakes the wait again
            read = time.strftime(STAMP, time.gmtime())
            woke = await asyncio.to_thread(awaited, store, until, work_id, since, scope)
            if woke:
                closed = work_id is not None and woke[0]['state'] in ('done', 'cancelled', 'failed')
                return {'state': woke[0]['state'], 'until': until, 'work_id': woke[0]['work_id'], 'woke': woke,
                        'since': since, 'next': None if closed else waiting_call(until, work_id, read)}
            try:
                await asyncio.wait_for(heard.wait(), max(deadline - loop.time(), 0))
            except TimeoutError:
                break
            scope, named = named, set()
            await asyncio.to_thread(deaths.arm)  # a runner started since is watched too; one stat when none was
    return {'state': 'pending', 'until': until, 'work_id': work_id, 'woke': [], 'since': since, 'waited': limit,
            'next': waiting_call(until, work_id, since)}


def _purposes(store: Store, read: dict[str, Any]) -> list[str]:
    """What the node a ticket is at is for, from the joins it receives as RE, each its OP and EF, at most three; a
    ticket on a join, that join's own. The rest of the node is in its brief."""
    at = read.get('at')
    if not isinstance(at, dict):
        return []
    held = cast(dict[str, Any], at)
    if 'join' in held:
        join = cast(dict[str, Any], held['join'])
        pairs = [(join.get('purpose'), join.get('ef'))]
    else:
        address = str(cast(dict[str, Any], held.get('element') or {}).get('address') or '')
        found = store.where(address) if address else None
        pairs = [(join.purpose, join.ef) for join in (found.receives if found is not None else ())][:3]
    return [(f'OP: {purpose}' if purpose else '') + (f'  EF: {ef}' if ef else '') for purpose, ef in pairs
            if purpose or ef]


def handoff_text(ctx: Context, work_id: str, *, session: str | None = None, on: Surface = 'mcp') -> str:
    """The hand-off of a ticket as text, handoff_parts."""
    return handoff_parts(ctx, work_id, session=session, on=on)[0]


def handoff_parts(ctx: Context, work_id: str, *, session: str | None = None,
                  on: Surface = 'mcp') -> tuple[str, list[dict[str, str]]]:
    """The hand-off of a ticket, BASE-050 and MCP-039: the work line, then the ticket as its fields, what its node is
    for, the node's brief as it reads on the surface `on`, MCP by default since that is how the agent it is handed to
    calls Metaform, with the calls that read the counts there, and the `metaform://` links of the node and the ticket,
    never what they hold; and those links as ACP resource links, name, uri and title, which a runner sends beside the
    text, ACP's `resource_link` content block every agent takes in session/prompt. How to work a ticket is on the
    map_work tool, read when the agent uses it, so it is not pushed here. The counts are told once to the agent
    session they are for: the session reading it, or the one named, which is the session a runner starts its agent
    in."""
    store = ctx.require_store()
    try:
        read = cast(dict[str, Any], map_work(ctx, session=session, on=on, id=work_id))
    except StoreError as error:
        raise Stop(str(error), 'metaform map work open=true') from None
    fields: list[tuple[str, Any]] = [('ticket', work_id), ('kind', read.get('kind')),
                                     ('condition', read.get('condition')), ('task', read.get('task')),
                                     ('note', read.get('note'))]
    if ctx.project and read.get('node_kind') and read.get('node_id'):  # what the person wrote at the node, whole
        node = Node.of(str(read['node_kind']), str(read['node_id']))
        fields += [("the person's note here", text) for _, person_note in provided(ctx.folder, 'memory.note')
                   if (text := person_note(ctx.project, node))]
    if read.get('steps'):
        fields.append(('steps', f"{read.get('steps_done') or 0} of {read['steps']} done"))
    linked = [one if isinstance(one, str) else '' for one in cast(list[Any], read.get('linked') or [])]
    fields.append(('linked', ', '.join(one for one in linked if one)))
    first = cast(list[Any], read.get('read_first') or [])
    if first:
        call = f'map_work id={work_id}' if on == 'mcp' else f'metaform map work id={work_id}'
        fields.append(('read_first', f'{len(first)} items to read before the task: {call}'))
    lines = [f'{name}: {value}' for name, value in fields if value]
    lines += _purposes(store, read)
    at = read.get('at')
    around = cast(dict[str, Any], at).get('around') if isinstance(at, dict) else None
    if around:
        lines.append(str(around))
    address = str(read.get('address') or read.get('receiver_address') or '')
    item = cast(dict[str, Any], read.get('map') or {}).get('item') if isinstance(read.get('map'), dict) else None
    links: list[dict[str, str]] = []
    if address:
        links.append({'name': address, 'uri': f'metaform://{address}', 'title': f'The brief of {address}'})
    if item:
        at, _, number = str(item).rpartition('#')
        links.append({'name': str(item), 'uri': f'metaform://{at}/items/{number}' if at and number else
                      f'metaform://{item}', 'title': f'Ticket {item}'})
    if links:
        lines.append('Links: ' + '  '.join(one['uri'] for one in links))
    if on == 'mcp' and (peered := peers_line(ctx, store, work_id, session)):
        lines.append(peered)
    node = str(read.get('address') or ' and '.join(
        f'{name}={value}' for name, value in (('receiver', read.get('receiver_address')),
                                              ('provider', read.get('provider_address'))) if value))
    opening = work_line(work_id, ctx.folder, node)
    if read.get('condition') == 'broken' or read.get('kind') == 'broken':  # the system healing itself, `healing`
        opening = f"{prompt('heal')}\n\n{opening}"
    return f"{opening}\n\n" + '\n'.join(lines) + '\n', links


def peers_line(ctx: Context, store: Store, work_id: str, session: str | None) -> str:
    """The hand-off's line on the other agents at work, `peers_at_work`, once a session: only while another agent is
    at work on an open ticket, since the agent can then collide with it and needs the tools that reach it; empty when
    it works alone, was told already, or who is at work cannot be read."""
    from .peering import working
    try:
        others = [entry for entry in working(ctx, store) if entry['work_id'] != work_id]
    except Exception:  # noqa: BLE001  who is at work is a pointer; the hand-off is given without it
        return ''
    if not others or record_shown(session or ctx.session, 'announce:peers', len(others)) is not None:
        return ''
    return prompt('peers_at_work', n=str(len(others)))


def overlap(ctx: Context, work_id: str) -> str:
    """The line a ticket's take or plan answers with over MCP, `peers_overlap`, once a session for its part: the other
    agents at work at that part, inside it or around it, since the moment an agent starts or plans its work is the
    moment it can collide with theirs, and the hand-off's line came before they may have started. Empty when none is,
    when it was said for that part already, or when who is at work cannot be read."""
    from .peering import addresses, working
    store = ctx.require_store()
    try:
        mine = addresses(store.ticket(work_id).work)
        others = [entry for entry in working(ctx, store) if entry['work_id'] != work_id and any(
            one == theirs or one.startswith(theirs + '.') or theirs.startswith(one + '.')
            for one in mine for theirs in addresses(entry['_record']))]
    except Exception:  # noqa: BLE001  who is at work is a pointer; the write is answered without it
        return ''
    at = ' and '.join(mine)
    if not others or record_shown(ctx.session, f'announce:overlap:{at}', len(others)) is not None:
        return ''
    return prompt('peers_overlap', at=at, who=', '.join(f'{entry["agent"]} on {entry["item"]}' for entry in others))


def handoff(ctx: Context) -> str:
    """The hand-off of a ticket: what an agent the work is handed to by its id reads, BASE-050, the same text an agent
    dispatch starts over ACP is sent as its first turn, with its reads named for the caller's surface; with full=true,
    the full worker's brief ahead of it, the text that is no longer sent."""
    text = handoff_text(ctx, str(ctx.nouns['id']), on='mcp' if ctx.surface == 'mcp' else 'cli')
    return f"{handoff_prompt(str(ctx.nouns['id']), ctx.folder)}\n\n{text}" if ctx.nouns.get('full') else text


def threaded(lines: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """A thread as the page reads it: each tool call's line carries its detail as `data`, each permission line its
    request, each question the agent asked its fields and state, and each notice of the agent its severity, title and
    description, as `data`; each session's state is taken out of the thread, by session id."""
    states: dict[str, dict[str, Any]] = {}
    details: dict[tuple[str, str], Any] = {}
    kept: list[dict[str, Any]] = []
    for line in lines:
        kind = line['kind']
        if kind == 'unlisted':  # serve's mark of a session an editor deleted from its list, BASE-062: no line of it
            continue
        if kind in ('state', 'tool_detail', 'permission', 'subagent', 'elicitation', 'agent_notice', 'attachment',
                    'peer'):
            try:
                value: Any = json.loads(str(line['text']))
            except ValueError:
                value = None
            if kind == 'state':
                if isinstance(value, dict):
                    states[str(line['session_id'])] = cast(dict[str, Any], value)
                continue
            if kind == 'tool_detail':
                details[(str(line['session_id']), str(line['name'])[len('detail:'):])] = value
                continue
            line = {**line, 'data': value}
        kept.append(line)
    for line in kept:
        name = str(line['name'])
        if name.startswith('tool:'):
            found = details.get((str(line['session_id']), name[len('tool:'):]))
            if found is not None:
                line['data'] = found
    return kept, states


ENDED_STATE = ('about', 'brief', 'intake', 'notification', 'title', 'role', 'authored_role_uri', 'assignment_id', 'team_id',
               'latest_message_id', 'latest_message_text', 'updated_at', 'name')
# What the agents key keeps of an ended session's assignment: the fields its state and the Agents menu name it by.
ENDED_ASSIGNMENT = ('assignment_id', 'authored_role_uri', 'team_id', 'gc_assignment_id', 'root_work_id',
                    'parent_assignment_id', 'reviewed_assignment_id', 'state', 'work_id')
def held_here(row: dict[str, Any]) -> bool:
    """Whether a stored session row is recorded running by this home, so its runner may still be at work on it; one
    another home started reads as ended here, session_status."""
    return row['state'] == 'running' and not (row.get('origin') and foreign(row))


def session_page(tx: Any, given: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    """Select before hydrating: named sessions or tickets, live sessions, or one cursor page of old ended sessions.
    Unknown legacy end times sort into history. The cursor fixes the hour boundary throughout a history walk."""
    work_id, session_id = given.get('id'), given.get('session')
    if 'session_ids' in given:
        rows = tx.rows_in('agent_sessions', 'session_id', given['session_ids'])
    elif 'ids' in given:
        rows = tx.rows_in('agent_sessions', 'work_id', given['ids'], by=('work_id', 'seq'))
    elif session_id:
        row = tx.get('agent_sessions', {'session_id': session_id})
        rows = (row,) if row is not None and (not work_id or row['work_id'] == work_id) else ()
    elif work_id:
        row = tx.get('agent_sessions', {'session_id': work_id})
        rows = (row,) if row is not None else tx.rows('agent_sessions', {'work_id': work_id},
                                                     by=('work_id', 'seq'), limit=0).results
    else:
        cutoff = (datetime.now(UTC) - timedelta(hours=1)).strftime(STAMP)
        after = given.get('after')
        cursor = None
        if after:
            try:
                decoded = json.loads(after)
                cutoff, cursor = decoded['cutoff'], decoded['after']
                datetime.strptime(cutoff, STAMP).replace(tzinfo=UTC)
                if cursor is not None and (not isinstance(cursor, list) or len(cast(list[Any], cursor)) != 3
                                           or not isinstance(cursor[0], str) or not isinstance(cursor[1], int)
                                           or not isinstance(cursor[2], str)):
                    raise ValueError
            except (ValueError, TypeError, KeyError):
                raise Stop('Invalid session history cursor.', 'metaform dispatch sessions history=true') from None
        history = given.get('history') is True or bool(after)
        if history:
            limit = int(given['limit']) if 'limit' in given else 50
            if not 1 <= limit <= 500:
                raise Stop('Session page limit must be from 1 to 500.', 'metaform dispatch sessions history=true')
            page = tx.rows('agent_sessions', {'state': 'ended'}, by=('state', 'ended', 'seq'),
                           limit=limit, after=json.dumps(cursor) if cursor is not None else None)
            rows = tuple(row for row in page.results if str(row.get('ended') or '') < cutoff)
            next_key = json.loads(page.next) if page.next and len(rows) == len(page.results) else None
        else:
            active = tx.rows_in('agent_sessions', 'state', ('running', 'waiting', 'starting'),
                                by=('state', 'ended', 'seq'))
            recent = tx.rows('agent_sessions', {'state': 'ended'}, by=('state', 'ended', 'seq'),
                             after=json.dumps([cutoff, -1, '']), limit=0).results
            rows = (*active, *recent)
            next_key = None
        probe = tx.rows('agent_sessions', {'state': 'ended'}, by=('state', 'ended', 'seq'), limit=1,
                        after=json.dumps(next_key) if next_key is not None else None).results
        more = (not history or next_key is not None) and bool(probe) and str(probe[0].get('ended') or '') < cutoff
        next_page = json.dumps({'cutoff': cutoff, 'after': next_key}) if more else None
        selected = [dict(row) for row in rows]
        return (selected if history else sorted(selected, key=lambda row: (row['seq'], row['session_id']))), next_page
    found = sorted((dict(row) for row in rows), key=lambda row: (row['seq'], row['session_id']))
    if given.get('latest') and found:
        found = [max(found, key=lambda row: (row['state'] in ('running', 'waiting'), row['seq'], row['session_id']))]
    return found, None


def read_sessions(ctx: Context) -> dict[str, Any]:
    """Live sessions by default, a cursor page of ended history on request, or the named tickets and sessions.
    Detail reads retain complete threads; thread=false supplies metadata for the agents key and board.
    Each session's state is under `states` by its session id, so a session row reads the same on every surface, and
    a tool call's or a permission request's line carries its structure as `data`. What only reaches a running session
    is left out. An intake agent's session is found in whatever metaform it is kept in; every conversation is the project's,
    whichever map is active, PROJ-026."""
    store = ctx.require_store()
    work_id = ctx.nouns.get('id') or None
    only: str | None = None  # an agent's name: its latest session alone
    if work_id and is_name(work_id):
        by_name = named_session(store, str(work_id))
        work_id, only = str(by_name['work_id']), str(by_name['session_id'])
    if work_id and intake_id(work_id):
        store = intake_store(store, str(work_id)) or store
    lines: list[dict[str, Any]] = []
    states: dict[str, dict[str, Any]] = {}
    stored: list[dict[str, Any]] = []
    raised: list[dict[str, Any]] = []
    since = ctx.nouns.get('since')
    agents_key = ctx.nouns.get('thread') is False and not work_id and not ctx.nouns.get('session')
    next_page: str | None = None
    # One transaction reads the session rows, the lines wanted of them and the signals, before any runner is asked for
    # its status, code.dispatcher.agent#3b; what a row recorded running needs is read for it, and dropped below for
    # one whose runner turns out to be gone.
    own = own_store(store)
    try:
        carry_conversations(own)
    except StoreError:  # a metaform that cannot be read now keeps what it holds of them until one can carry it
        pass
    try:
        with own.tables(write=False) as tx:
            # a name resolved above to its ticket and session: the page is read for those, not for the name (2026-10-21)
            stored, next_page = session_page(tx, {**ctx.nouns, 'id': work_id, 'session': only} if only else ctx.nouns)
            if work_id and len(stored) == 1 and stored[0]['session_id'] == work_id:
                work_id = str(stored[0]['work_id'])
            wanted = [str(session['session_id']) for session in stored]
            if wanted and (ctx.nouns.get('thread') is False or since is not None):
                lines += [dict(row) for row in tx.rows_in('session_lines', 'session_id', wanted,
                                                         where={'name': 'state'})]
            if ctx.nouns.get('thread') is not False and since is None:
                lines += [dict(row) for row in tx.rows_in('session_lines', 'session_id', wanted,
                                                         by=('session_id', 'seq'))]
            elif ctx.nouns.get('thread') is False:
                live_ids = [str(session['session_id']) for session in stored if held_here(session)]
                lines += [dict(row) for row in tx.rows_in('session_lines', 'session_id', live_ids,
                                                         where={'kind': 'subagent'}, by=('session_id', 'kind', 'seq'))]
            for session in stored:
                if ctx.nouns.get('thread') is not False and since is not None:
                    # Only the lines begun after `since`, one range of the (session_id, seq) index read from the
                    # cursor at that seq, for a caller that polls a thread; a line grown in place keeps the seq it
                    # began with. Its state line is read above, so `states` stays whole.
                    lines += [dict(row) for row in tx.rows('session_lines', {'session_id': session['session_id']},
                                                           by=('session_id', 'seq'), limit=0,
                                                           after=json.dumps([int(since), ''])).results
                              if int(row['seq']) > int(since) and row['name'] != 'state']
            requested_work = [str(work_id)] if work_id else ctx.nouns.get('ids') or []
            raised = signal_rows(tx, work_id, session_ids=wanted,
                                 work_ids=sorted({*requested_work, *(str(session['work_id']) for session in stored)}))
    except StoreError:
        raised = read_signal_rows(store, work_id)  # as before: a store that cannot be read says so here
    open_work: list[WorkRecord] = list(store.work(open=True, limit=0).results) \
        if agents_key and any(held_here(row) for row in stored) else []
    found = verified(store, stored, open_work if agents_key else None)
    if ctx.nouns.get('thread') is False:  # the subagents only of sessions whose runner holds them
        live = {session['session_id'] for session in found if session.get('state') == 'running'}
        lines = [line for line in lines if line['kind'] != 'subagent' or line['session_id'] in live]
    lines, states = threaded(lines)
    if agents_key:
        # The agents key's read of every ticket, done on each change it hears: an ended session keeps only what names
        # it in the Agents menu, not its commands, capabilities and options, which made this read megabytes.
        running = {session['session_id'] for session in found if session.get('state') == 'running'}
        states = {key: state if key in running else {name: state[name] for name in ENDED_STATE if name in state}
                  for key, state in states.items()}
    # A subagent the agent started, when it advertises them, is a child session of its own, P016: its line in the
    # parent's thread names it, and its own thread is kept under its session id, read here with it.
    children: list[dict[str, Any]] = []
    for line in lines:
        held = line.get('data')
        if line['kind'] != 'subagent' or not isinstance(held, dict):
            continue
        child = cast(dict[str, Any], held)
        own_lines: list[dict[str, Any]] = []
        if ctx.nouns.get('thread') is not False:
            try:
                with own.tables(write=False) as tx:
                    own_lines = [dict(row) for row in tx.rows('session_lines', {'session_id': child.get('session_id')},
                                                              by=('session_id', 'seq'), limit=0).results]
            except StoreError:
                pass
        children.append({**child, 'parent': line['session_id'], 'lines': threaded(own_lines)[0]})
    if ctx.nouns.get('thread') is False:
        lines = []
    # An intake agent launched and not yet in session is listed as starting, from the one record of an intake under
    # way, so every surface that lists the sessions sees it, whichever surface launched it, VIEW-045.
    starting: list[dict[str, Any]] = []
    if not work_id or intake_id(work_id):
        busy = intake_under_way(store, found)
        if busy is not None and busy['state'] == 'starting' and (not work_id or busy['work_id'] == work_id):
            starting = [{**{key: value for key, value in busy.items() if key not in PRIVATE}, 'how': None,
                         'status': 'submitted', 'reason': 'starting'}]
    from .orchestration import service
    owner = service(ctx)
    if owner is not None:
        if work_id:
            # A ticket-scoped event reads only that assignment and its actual relationship targets. Its opened
            # thread includes pending continuation delivery; the compact Agents menu needs no transition bodies.
            scoped = owner.context(ctx, work_id=str(work_id)) if ctx.nouns.get('thread') is not False else \
                owner.assignment(ctx, work_id=str(work_id))
            assignments = [scoped] if scoped is not None else []
        else:
            assignments = [assigned for ref in sorted({str(session['work_id']) for session in found})
                           if (assigned := owner.assignment(ctx, work_id=ref)) is not None]
        by_work = {str(one['work_id']): one for one in assignments}
        by_id = {str(one['assignment_id']): one for one in assignments}
        if work_id and assignments:
            for key in ('parent_assignment_id', 'reviewed_assignment_id'):
                related = assignments[0].get(key)
                if related and related not in by_id:
                    held = owner.assignment(ctx, assignment_id=str(related))
                    if held is not None:
                        by_id[str(related)] = held
        for session in found:
            assigned = by_work.get(str(session['work_id']))
            if assigned is None:
                continue
            parent: dict[str, Any] = by_id.get(str(assigned.get('parent_assignment_id'))) or {}
            reviewed: dict[str, Any] = by_id.get(str(assigned.get('reviewed_assignment_id'))) or {}
            directions: list[dict[str, Any]] = assigned.get('pending_direction') or []
            if agents_key and session.get('state') != 'running':
                # An ended session in the agents key: what names it in the Agents menu, its responsibility and
                # delivery, not its assignment's record and directions, which made this read megabytes (4.4 MB for
                # 462 sessions, 2026-10-19), read and parsed on each change the page hears. Its thread's read has them.
                assigned = {key: assigned.get(key) for key in ENDED_ASSIGNMENT}
                directions = []
            sid = str(session['session_id'])
            states[sid] = {**states.get(sid, {}),
                'orchestration': assigned, 'authored_role_uri': assigned['authored_role_uri'],
                'assignment_id': assigned['assignment_id'], 'team_id': assigned['team_id'],
                'owner_gc_id': assigned['gc_assignment_id'], 'root_work_id': assigned['root_work_id'],
                'parent_assignment_id': assigned.get('parent_assignment_id'),
                'parent_session_id': parent.get('owner_session_id'), 'parent_work_id': parent.get('work_id'),
                'delivery_state': assigned['state'], 'pending_direction': directions,
                'latest_direction': directions[-1] if directions else None,
                'assessment_work_id': assigned['work_id'] if reviewed else None,
                'reviewed_work_id': reviewed.get('work_id'), 'reviewed_session_id': reviewed.get('owner_session_id'),
                'reviewed_gc_id': reviewed.get('assignment_id')}
    if only is not None:
        found = [session for session in found if session['session_id'] == only]
        lines = [line for line in lines if line['session_id'] == only]
        states = {key: state for key, state in states.items() if key == only}
        children = [child for child in children if child['parent'] == only]
    return {'sessions': [*({**{key: value for key, value in session.items() if key not in PRIVATE},
                            **session_work_status(session, [one for one in raised
                                                            if one.get('work_id') == session['work_id']])}
                           for session in found), *starting],
            'lines': lines, 'signals': raised, 'states': states, 'subagents': children, 'next': next_page}


def harnesses(ctx: Context) -> dict[str, Any]:
    """The agents dispatch starts, for the person to choose from: each with its name, its start command, whether that
    command is found on this system, and which is the default; with a project, how many more agents the person may
    summon now."""
    default = str(ctx.setting('dispatch_agent'))
    known = catalog_rows(ctx.store)  # what each offered at its last session here, P199: its version and settings
    found: list[dict[str, Any]] = []
    for agent in agent_choices():
        label = agent_label(agent)
        try:
            command = start_command(ctx, agent)
        except Stop:
            command = ''
        path = located(command) if command else None
        row = known.get(agent)
        found.append({'agent': agent, 'label': label, 'command': command, 'available': path is not None,
                      'path': path, 'default': agent == default,
                      'version': row['version'] if row else None,
                      'settings': len(cast(list[Any], row.get('settings') or [])) if row else None,
                      'pinned': registry_pins().get(agent),
                      'next': None if path else f'metaform set --dispatch-{agent} "<command>"' if agent in AGENTS
                      else f'metaform dispatch registry add={agent}'})
    result: dict[str, Any] = {'agents': found, 'default': default}
    if ctx.store is not None:
        held = slots(ctx, ctx.store)  # the gate's own count, so what the page offers is what starts
        result['room'] = held['room']
        result['free'] = held['free']  # how many tickets may start now, for Start all
        result['slots'] = {key: held[key] for key in ('limit', 'used', 'workers', 'summoned', 'machine_limit',
                                                       'machine_used', 'machine_free', 'projects')}
        result['footprint'] = footprint(ctx.store)  # what one agent costs this machine, beside the number
    return result


def registry_read(ctx: Context) -> dict[str, Any]:
    """`dispatch registry`: the agents of the ACP Registry, P013 and P030, each with its version, how it is
    distributed, whether it can run on this system and the version pinned here; dispatch's own agents with the
    registry's version of each beside the command set for it. add=<id> pins an agent at the version listed now and
    installs it, remove=<id> drops its pin, upgrade=true pins each added agent at the version listed now; these are
    the person's, since they decide what runs. agent=<id> reads one entry whole."""
    adding, removing = ctx.nouns.get('add'), ctx.nouns.get('remove')
    upgrading = bool(ctx.nouns.get('upgrade'))
    if adding or removing or upgrading:
        persons_own(ctx, 'Which agents dispatch starts')
    url = str(ctx.setting('dispatch_registry_url'))
    read = agent_registry.read(url, max_age=3600 * REGISTRY_HOURS,
                         refresh=bool(ctx.nouns.get('refresh')) or upgrading or bool(adding))
    found = agent_registry.entries(read)
    pins = registry_pins()
    changed: list[dict[str, Any]] = []

    def keep(pinned: dict[str, str]) -> None:
        settings.put('dispatch_registry_agents', [f'{agent}@{version}' for agent, version in sorted(pinned.items())],
                     ctx.folder)

    if removing:
        if str(removing) not in pins:
            raise Stop(f'{removing} is not pinned.', 'metaform dispatch registry')
        changed.append({'agent': str(removing), 'removed': pins.pop(str(removing))})
        keep(pins)
    if adding:
        wanted = str(adding)
        if wanted in ('antigravity', agent_registry.BUILTIN['antigravity']):
            entry = found.get(agent_registry.BUILTIN['antigravity'])
            if entry is None:
                raise Stop('The ACP Registry lists no Google Antigravity adapter.', 'metaform dispatch registry')
            held = agent_registry.pin(entry)
            command = agent_registry.builtin_command('antigravity', entry)
            settings.put('dispatch_antigravity', command, ctx.folder)
            changed.append({'agent': 'antigravity', 'pinned': entry['version'], 'kind': held['kind'],
                            'command': command, 'verified': held.get('verified')})
            adding = None
    if adding:
        wanted = str(adding)
        if wanted in AGENTS or wanted in agent_registry.BUILTIN.values():
            mine = next((agent for agent, entry in agent_registry.BUILTIN.items() if wanted in (agent, entry)), wanted)
            raise Stop(f"{wanted} is dispatch's own {AGENTS[mine][0]}; its command is the dispatch_{mine} setting.",
                       f'metaform set --dispatch-{mine} "<command>"')
        entry = found.get(wanted)
        if entry is None:
            raise Stop(f'The ACP Registry lists no agent {wanted}.', 'metaform dispatch registry')
        held = agent_registry.pin(entry)
        pins[wanted] = str(entry['version'])
        keep(pins)
        changed.append({'agent': wanted, 'pinned': pins[wanted], 'kind': held['kind'],
                        'command': agent_registry.command(wanted, pins[wanted]), 'verified': held.get('verified')})
    if upgrading:
        for agent, version in sorted(pins.items()):
            entry = found.get(agent)
            if entry is None or str(entry.get('version')) == version:
                continue
            agent_registry.pin(entry)
            changed.append({'agent': agent, 'from': version, 'pinned': str(entry['version'])})
            pins[agent] = str(entry['version'])
        keep(pins)
    named = ctx.nouns.get('agent')
    if named:
        entry = found.get(str(named))
        if entry is None:
            raise Stop(f'The ACP Registry lists no agent {named}.', 'metaform dispatch registry')
        chosen = agent_registry.way(entry)
        return {'registry': url, 'agent': entry, 'runs_here': chosen[0] if chosen else None,
                'pinned': pins.get(str(named)),
                'next': None if str(named) in pins else f'metaform dispatch registry add={named}'}
    own: list[dict[str, Any]] = []
    for agent, entry_id in agent_registry.BUILTIN.items():
        entry = found.get(entry_id)
        listed = agent_registry.builtin_command(agent, entry) if entry else None
        current = str(ctx.setting(f'dispatch_{agent}'))
        own.append({'agent': agent, 'registry_id': entry_id, 'version': entry.get('version') if entry else None,
                    'command': current, 'registry_command': listed,
                    'next': (f'metaform dispatch registry add={entry_id}' if agent == 'antigravity' else
                             f'metaform set --dispatch-{agent} "{listed}"') if listed and listed != current else None})
    agents: list[dict[str, Any]] = []
    for agent_id, entry in sorted(found.items()):
        chosen = agent_registry.way(entry)
        agents.append({'agent': agent_id, 'name': entry.get('name'), 'version': entry.get('version'),
                       'ways': sorted(cast(dict[str, Any], entry.get('distribution') or {})),
                       'runs_here': chosen[0] if chosen else None, 'pinned': pins.get(agent_id)})
    return {'registry': url, 'read': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(float(read['fetched']))),
            **({'stale': read.get('error')} if read.get('stale') else {}), 'platform': agent_registry.platform(),
            'own': own, 'agents': agents, **({'changed': changed} if changed else {})}


def adapter(ctx: Context) -> None:
    """The native ACP adapter launcher. Replaces this process, preserving ACP's standard streams and signals."""
    agent_registry.adapter(str(ctx.nouns['pin']))


def publication(ctx: Context) -> dict[str, Any]:
    """`dispatch publication`: the ACP Registry entry that would publish `metaform dispatch serve`, with its icon and
    what keeps it from passing the registry's checks, written to out=<folder> as <id>/agent.json and <id>/icon.svg
    for review. Nothing is sent: publishing is a pull request to github.com/agentclientprotocol/registry."""
    from importlib import metadata
    try:
        installed = metadata.version('metaform')
    except metadata.PackageNotFoundError:
        installed = ''
    agent_id = str(ctx.nouns.get('id') or 'metaform')
    built = agent_registry.publication(
        agent_id=agent_id, name=str(ctx.nouns.get('name') or 'Metaform'),
        version=str(ctx.nouns.get('version') or installed),
        description=str(ctx.nouns.get('description') or "Functional maps that give agents a project's purpose "
                        'before they work on it, served to an editor as an ACP agent that passes through to yours.'),
        package=str(ctx.nouns.get('package') or 'metaform'), repository=ctx.nouns.get('repository'),
        license_name=ctx.nouns.get('license'), license_url=ctx.nouns.get('license_url'))
    result: dict[str, Any] = {**built, 'unchecked': [
        "that the package exists on PyPI at this version, which the registry's CI checks over the network",
        'that the agent returns authMethods with an agent or terminal method, which its CI checks by running it']}
    out = ctx.nouns.get('out')
    if out:
        folder = Path(str(out)).expanduser() / agent_id
        if home.is_home_path(folder):
            home.mkdir_private(folder)
            home.write_private(folder / 'agent.json', json.dumps(built['entry'], indent=2) + '\n')
            home.write_private(folder / 'icon.svg', built['icon'])
        else:
            folder.mkdir(parents=True, exist_ok=True)
            (folder / 'agent.json').write_text(json.dumps(built['entry'], indent=2) + '\n', encoding='utf-8')
            (folder / 'icon.svg').write_text(built['icon'], encoding='utf-8')
        result['written'] = [str(folder / 'agent.json'), str(folder / 'icon.svg')]
    return result


def permit(ctx: Context) -> dict[str, Any]:
    """The person's choice for an agent's waiting permission request, by the option's id or name: it answers the
    agent at once, and closes the request's question at the node with the option's name. Only the person gives it:
    it is not offered to agents over MCP, and nothing approves beyond dispatch_prompts. An agent's own command is
    refused, so no agent answers its own request or consent card (UX review, person-consent)."""
    persons_answer(ctx, "An answer to an agent's permission request or question")
    work_id = str(ctx.nouns['id'])
    given: Any = ctx.nouns['option']
    option = ' '.join(str(word) for word in cast(list[Any], given)) if isinstance(given, (list, tuple)) else str(given)
    result = tell(_running_or_stop(ctx.require_store(), work_id), 'permit', request=str(ctx.nouns['request']),
                  option=option.strip())
    if result.get('error'):
        raise Stop(str(result['error']), f'metaform dispatch sessions id={work_id}')
    return result


def configure(ctx: Context) -> dict[str, Any]:
    """Set one of a running session's settings, as the agent offers them in the session's state: its mode, its model
    or any other config option, by the setting's id and the value or name of a choice, or on or off. The agent takes
    it from its next step. Only the person sets it: it is not offered to agents over MCP, and an agent's own command
    is refused."""
    persons_answer(ctx, "A running session's setting")
    work_id = str(ctx.nouns['id'])
    given: Any = ctx.nouns['value']
    value = ' '.join(str(word) for word in cast(list[Any], given)) if isinstance(given, (list, tuple)) else str(given)
    result = tell(_running_or_stop(ctx.require_store(), work_id), 'configure', setting=str(ctx.nouns['setting']),
                  value=value.strip())
    if result.get('error'):
        raise Stop(str(result['error']), f'metaform dispatch sessions id={work_id}')
    return result


def session_prompts(ctx: Context) -> dict[str, Any]:
    """How one running session's permission requests are answered from now on, one of dispatch_prompts' choices for
    that session alone, over its launch's and the project's: its later requests at once, and each request waiting now
    that the choice approves. The person's own, since they decide what the agent may do without asking; approve-all
    lets it act without asking, so it is given with confirm=true."""
    persons_own(ctx, 'How an agent\'s permission requests are answered')
    work_id, how = str(ctx.nouns['id']), str(ctx.nouns['prompts']).strip()
    if how not in PROMPTS:
        raise Stop(f'prompts is one of {", ".join(PROMPTS)}, not {how}.', 'metaform help dispatch prompts')
    if how == 'approve-all' and not ctx.nouns.get('confirm'):
        raise Stop('approve-all lets the agent run any tool in this session without asking you, including ones that '
                   'change or delete files; give confirm=true to choose it.',
                   f'metaform dispatch prompts {work_id} approve-all confirm=true')
    wanted = str(ctx.nouns['session']) if ctx.nouns.get('session') else None
    result = tell(_running_or_stop(ctx.require_store(), work_id, wanted), 'prompts', prompts=how)
    if result.get('error'):
        raise Stop(str(result['error']), f'metaform dispatch sessions id={work_id}')
    return result


def spawn(store: Store, work_id: str, agent: str, extra: list[str], name: str, *, kept: bool = False,
          ctx: Context | None = None, besides: int | None = None, asked: int | None = None, auto: bool = False,
          subject: str | None = None) -> dict[str, Any]:
    """A runner started detached from the terminal in the project's folder through the one admission gate,
    `start_runner`, its output in the log named for it; `kept` for a launch whose caller waits on it, `launched`,
    which hears the runner exit."""
    return start_runner(ctx, store, work_id, agent, extra, name, kept=kept, besides=besides, asked=asked, auto=auto,
                        subject=subject)


RUNNERS: dict[int, subprocess.Popen[Any]] = {}  # the runners started for a wait, `launched`, by pid


def resume(ctx: Context) -> dict[str, Any]:
    """Resume an ended agent session in place, with the agent's own memory of it, where its agent can load or resume
    a session: its thread goes on where it ended. A worker whose ticket is still its own goes on as that ticket's
    worker; any other session comes back as a conversation the person summoned. It waits for the person's next
    message. An agent that can do neither is refused, with a fresh agent that reads the thread as the next step."""
    may_steer(ctx)
    store = ctx.require_store()
    work_id = str(ctx.nouns['id'])
    wanted = ctx.nouns.get('session')
    for name in (str(one) for one in (work_id, wanted) if one and is_name(one)):  # an agent's name: its latest session
        by_name = named_session(store, name)
        work_id, wanted = str(by_name['work_id']), str(by_name['session_id'])
    held = (intake_store(store, work_id) or store) if intake_id(work_id) else store
    found = sessions(held, work_id)
    row = next((one for one in reversed(found) if one['session_id'] == wanted), None) if wanted else \
        (found[-1] if found else None)
    if row is None:
        raise Stop(f'No agent session {wanted} on work {work_id}.' if wanted else f'No agent session on work {work_id}.',
                   f'metaform dispatch sessions id={work_id} thread=false')
    session_id, agent = str(row['session_id']), agent_named(str(row['agent']))
    said = {'work_id': work_id, 'agent': agent, 'session_id': session_id}
    if row['state'] == 'running':  # it is there already: talked to as it is
        return {**said, 'state': 'running'}
    if intake_id(work_id):  # one intake agent at a time, BASE-039: not beside another starting or at work
        refuse_second_intake(store, work_id)
    fresh = f'metaform dispatch talk session={work_id}:{session_id}'
    kept = session_state(held, session_id) or {}
    caps = cast(dict[str, Any], kept.get('capabilities') or {})
    if not (caps.get('resume') or caps.get('load')):
        raise Stop(f'{agent_label(agent)} did not offer to resume its sessions, so session {session_id} cannot go on; '
                   'a new agent can read its thread instead.', fresh)
    cwd = kept.get('cwd')
    if not isinstance(cwd, str) or not os.path.isdir(cwd):
        raise Stop(f'The folder session {session_id} worked in, {cwd}, is gone.', fresh)
    runnable(ctx, agent)
    held = base_store(held, row)  # its ticket is in the metaform its runner was pinned to, and it goes on there
    record = None if intake_id(work_id) else held_ticket(held, work_id)
    worker = record is not None and not record.done and record.taken_by == f'{agent} {session_id}'
    from .orchestration import service
    owner = service(ctx)
    assignment = owner.assignment(ctx, work_id=work_id) if owner is not None else None
    if assignment and assignment.get('owner_session_id') == session_id and record is not None and not record.done:
        worker = True
    if worker and running(store, work_id) is not None:
        raise Stop(f'Another agent is at work on work {work_id}.', f'metaform dispatch sessions id={work_id}')
    # an agent's resume without the person's word is automatic, as its start is, so dispatch_agents binds it; the
    # word is only read here, an agent's resume needing none
    try:
        word = on_persons_word(ctx, f'Resuming the agent on ticket {work_id}', [work_id])
    except PersonsDecision:
        word = None
    automatic = not persons_start(ctx, word)
    # a worker's resume and a conversation's alike go through the gate, which refuses past the slots, VIEW-039
    if assignment and owner is not None and not automatic:
        admit(ctx, held, work_id, 'worker' if worker else 'summoned', agent=agent)
        owner.reopen(ctx, work_id)
    started = resume_spawn(held, work_id, agent, [f'resume={session_id}', *([] if worker else ['system=true'])], 'resume',
                           ctx=ctx, auto=automatic)
    if started.get('state') == 'running' and silent(row, started.get('pid')):
        return held_session(row, int(started['pid']))
    return {**said, 'state': 'starting', **started, 'conversation': not worker,
            **(on_word(ctx, word, f'resumed {agent_label(agent)} on ticket {ticket_label(held, work_id)}', [work_id])
               if word else {})}


def intake(ctx: Context) -> dict[str, Any]:
    """Start an agent on this project's intake, VIEW-045 and BASE-039: its first turn is the intake as `intake prompt`
    serves it, with what the person asked for filled in, and it works in the project's folder with Metaform's MCP
    server, recording the map as it reasons it, so an open page follows it. It takes no ticket and counts against the
    agent slots as a summoned agent does, staying to talk until the person stops it. One intake runs at a time."""
    store = ctx.require_store()
    agent = agent_named(str(ctx.nouns.get('agent') or ctx.setting('dispatch_agent')))  # the intake picker's, else the default
    runnable(ctx, agent)
    if not any(module.id == 'intake' for module in surface(ctx.folder)):
        raise Stop('The intake module is not active; it serves the intake the agent follows.', 'metaform enable intake')
    chosen = intake_map_choice(ctx)
    given: Any = ctx.nouns.get('text') or []
    words = ' '.join(str(word) for word in cast(list[Any], given)) if isinstance(given, (list, tuple)) else str(given)
    work_id = INTAKE + secrets.token_hex(16)
    # One intake at a time, BASE-039 and VIEW-045: every check and the launch are one step under the project's intake
    # lock, the one intake's own verbs take, and the launch is noted there before the lock is let go. Its runner then
    # holds `intake.agent` for as long as it lives, so a second start is refused for the whole life of the first,
    # however long its agent takes to start, never for a window of time. The person's words reach the runner in the
    # launch's row, never in an argument; the runner takes them before its session is made.
    with home.file_lock(intake_folder(store) / 'intake.lock'):
        refuse_second_intake(store)
        building = store.intake_building().results
        if building and building[0].recording:
            held = building[0]
            raise Stop(f'An agent Metaform did not start is recording the intake in layer {held.layer.name} of '
                       f'metaform {held.base} now; two agents would interleave their records in it.',
                       'metaform intake status')
        if building and not ctx.nouns.get('resume'):
            held = building[0]
            raise Stop(f'An intake was left unfinished in layer {held.layer.name} of metaform {held.base}, with '
                       f'{held.parts} parts; no agent is recording it. Start the intake agent with resume=true and it '
                       'resumes that intake.', 'metaform dispatch intake resume=true')
        # the slots are counted by the gate, which names the limit that binds (spawn-gate F4)
        with Store(store.project_id, module='dispatch').tables() as tx:
            tx.insert('raised', {'work_id': work_id, 'node': '', 'agent': agent, 'started': time.time(),
                                 'seq': time.time_ns(), 'asked': words.strip() or None})
        try:
            started = spawn(store, work_id, agent, ['system=true', 'intake=true'], 'intake',
                            kept=bool(ctx.nouns.get('wait')), ctx=ctx)
        except (Stop, OSError):  # refused by the gate or not started: its launch holds nothing
            with Store(store.project_id, module='dispatch').tables() as tx:
                tx.delete('raised', {'work_id': work_id})
            raise
        store.note_intake_launch({'work': work_id, 'agent': agent, 'pid': started['pid'], 'since': home.now(),
                                  **chosen})
    said = {'state': 'starting', 'work_id': work_id, 'agent': agent, **started, 'session_id': None,
            'conversation': True, 'intake': True, **chosen}
    if not ctx.nouns.get('wait'):
        return said
    # said once the launch is noted, before the wait for its session: every surface reads it as starting from here, so
    # `metaform start` opens the page at this line and the page shows it starting, never an intake still to start
    ctx.say(f'The intake agent is launched, work {work_id}; waiting for it to make its session.')
    return {**said, **launched(store, work_id, started['pid'])}


def helper(ctx: Context) -> dict[str, Any]:
    """Start a helper agent with a brief and no ticket, for quick work the person's system agent needs done while it
    stays reachable in the chat: a diagnosis, a small fix, a check. It runs through the one gate and runner like any
    agent, so it is a figure on the map, listed with the agents, its thread live in the chat, counted in spend, steered
    and stopped from the page, and ended by stop-all; a harness's own background subagents are none of these. It takes
    the helper capacity, never a worker slot: dispatch_agents bounds what Full Auto starts by itself, and a helper is
    started on purpose. Only the person and their system agent start one. When its brief's turns are done it puts one
    line in the system agent's inbox and ends; its record is its session, read with `dispatch sessions id=<work id>`."""
    if not person_asks(ctx) and sender(ctx) != 'system':
        raise Stop("A helper is started by the person or their system agent; an agent at work asks the system agent "
                   'for one with a note.', 'metaform dispatch note to=system -- "<what you need done>"')
    may_steer(ctx)
    store = ctx.require_store()
    agent = agent_named(str(ctx.nouns.get('agent') or ctx.setting('dispatch_agent')))
    runnable(ctx, agent)
    given: Any = ctx.nouns.get('text') or []
    brief = (' '.join(str(word) for word in cast(list[Any], given)) if isinstance(given, (list, tuple))
             else str(given)).strip()
    if not brief:
        raise Stop('A helper is given a brief: what to do and what to report back.',
                   'metaform dispatch helper -- "<the brief>"')
    work_id = HELPER + secrets.token_hex(16)
    # The brief reaches the runner in the launch's row, never in an argument, as an intake's words do; the runner takes
    # it before its session is made and keeps it in the session's state.
    with Store(store.project_id, module='dispatch').tables() as tx:
        tx.insert('raised', {'work_id': work_id, 'node': '', 'agent': agent, 'started': time.time(),
                             'seq': time.time_ns(), 'asked': brief})
    try:
        started = spawn(store, work_id, agent, [], 'helper', kept=bool(ctx.nouns.get('wait')), ctx=ctx)
    except (Stop, OSError):  # refused by the gate or not started: its launch holds nothing
        with Store(store.project_id, module='dispatch').tables() as tx:
            tx.delete('raised', {'work_id': work_id})
        raise
    said = {'state': 'starting', 'work_id': work_id, 'agent': agent, **started, 'session_id': None, 'helper': True}
    if not ctx.nouns.get('wait'):
        return said
    return {**said, **launched(store, work_id, started['pid'])}


MAP_NAME = re.compile(r'[A-Za-z0-9._-]{1,64}')  # a base's name, as `intake start name=` takes it


def new_map_asked(ctx: Context) -> str | None:
    """`dispatch intake map=new` on a project with a map is the person's decision: a new map beside the one in use is
    never how an update is recorded; the map in use is refined."""
    if ctx.nouns.get('map') != 'new' or not ctx.require_store().intake_bases():
        return None
    return ('This starts an intake agent on a separate map beside the one in use; the map in use is not changed, its '
            'knowledge layers stay with it, and memories at addresses the new map lacks are orphaned until rekeyed. '
            'An update to the map in use never needs it: map=extend refines it.')


def intake_map_choice(ctx: Context) -> dict[str, Any]:
    """The map the person chose an intake makes on a project mapped already, VIEW-045 as amended 2026-10-17: `map=extend`
    checks and extends the map in use, `map=new` starts a separate map beside it, named `name` or by its date. The
    intake agent's `intake start` follows it, whatever the agent reads in the person's words; none chosen on a mapped
    project is extend, since a project with a map is refined unless the person asks for a new one."""
    chosen, name = ctx.nouns.get('map'), str(ctx.nouns.get('name') or '').strip()
    if chosen in (None, ''):
        if name:
            raise Stop('A name is for a new map: give map=new with it.', f'metaform dispatch intake map=new name={name}')
        # a project with a map is refined unless the person asks for a new one (refinement first, 2026-10-17)
        return {'map': 'extend'} if ctx.require_store().intake_bases() else {}
    if chosen not in ('extend', 'new'):
        raise Stop('map is extend, to check and extend the map in use, or new, to start a separate map beside it.',
                   'metaform help dispatch intake')
    if chosen == 'extend':
        if name:
            raise Stop('A name is for a new map; map=extend writes onto the map in use.', 'metaform dispatch intake '
                                                                                         'map=extend')
        return {'map': 'extend'}
    if name and not MAP_NAME.fullmatch(name):
        raise Stop(f'{name!r} is not a name for a map: use 1 to 64 letters, digits, ., _ and -.',
                   'metaform dispatch intake map=new name=web-interface-refactor')
    return {'map': 'new', 'name': name or 'intake-' + time.strftime('%Y-%m-%d-%H%M%S', time.gmtime())}


def intake_folder(store: Store) -> Path:
    """The project's folder in the Metaform home, where its intake lock and the record of its intake agent are kept."""
    folder = home.project_folder(store.project_id)
    if folder is None:
        raise Stop(f'No project {store.project_id} is registered.', 'metaform list projects')
    home.mkdir_private(folder)
    return folder


def intake_under_way(store: Store, rows: Sequence[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """The one record of an intake agent at work in this project, BASE-039 and VIEW-045, that every surface reads: the
    page, `dispatch sessions`, `intake status` and the connect notice, `metaform start`, and a second start refused.
    It is `starting` from its launch until its agent's session is made, then `running`, for as long as its runner lives
    and holds `intake.agent`; a launch whose runner has not taken it yet is known by the pid its launcher noted. None
    when no intake agent is at work. `rows`, the project's sessions when the caller has read them."""
    held = store.intake_agent()
    if held is None:
        noted = store.intake_launch()
        if noted is not None and runner_of(noted.get('pid')) == noted.get('work'):
            held = noted
    found = [row for row in (rows if rows is not None else sessions(store)) if intake_id(row['work_id'])]
    running = [row for row in found if row['state'] == 'running']
    work = str(held['work']) if held is not None and held.get('work') else None
    if work is None:
        if running:  # a runner from before the record, or one whose record is lost: its session says it
            row = running[-1]
            return {'work_id': row['work_id'], 'agent': row['agent'], 'state': 'running',
                    'session_id': row['session_id'], 'started': row.get('started'), 'activity': row.get('activity')}
        return None if held is None else {'work_id': None, 'agent': None, 'state': 'running', 'session_id': None,
                                          'started': None, 'activity': None}
    assert held is not None  # it names the work
    own = [row for row in found if row['work_id'] == work]
    live = [row for row in own if row['state'] == 'running']
    choice: dict[str, Any] = {key: held[key] for key in ('map', 'name') if held.get(key)}
    if live:
        row = live[-1]
        return {'work_id': work, 'agent': row['agent'], 'state': 'running', 'session_id': row['session_id'],
                'started': row.get('started'), 'activity': row.get('activity'), **choice}
    if own:  # its session has ended, and its runner is on its way out
        return None
    return {'work_id': work, 'agent': held.get('agent'), 'state': 'starting', 'session_id': None,
            'started': held.get('since'), 'activity': None, 'pid': held.get('pid'), **choice}


def refuse_second_intake(store: Store, work_id: str | None = None) -> None:
    """Refuse an intake agent while another is at work in the project, whatever surface asks: the record every surface
    reads, `intake_under_way`, and the runner's hold itself, which a resumed session holds too. `work_id`: the intake
    asking, which is not refused for itself."""
    busy = intake_under_way(store)
    if busy is None:
        raw = store.intake_agent()
        busy = {'work_id': raw.get('work'), 'agent': raw.get('agent'), 'state': 'running'} if raw is not None else None
    if busy is None or work_id is not None and busy['work_id'] == work_id:
        return
    who = agent_label(str(busy['agent'])) if busy.get('agent') else 'An agent'
    since = f' since {busy["started"]}' if busy.get('started') else ''
    doing = 'is starting on' if busy['state'] == 'starting' else 'is at work on'
    raise Stop(f'{who} {doing} the intake of this project{since}; one intake runs at a time.',
               f'metaform dispatch stop {busy["work_id"]}' if busy.get('work_id') else 'metaform dispatch sessions')


def launch_concerns(payload: dict[str, Any], project_id: str, work_id: str) -> bool:
    """Whether a `map.changed` from another process can be the session row a launch waits for, decided from the change
    alone, BASE-053: one of its project, an intake's metaform being of the same project, that names its ticket or does
    not say which, and that wrote a session row or does not say what it wrote."""
    named: Any = payload.get('work_ids')
    if payload.get('project') != project_id or isinstance(named, list) and work_id not in named:
        return False
    kinds: Any = payload.get('kinds')
    if isinstance(kinds, list):
        return 'session' in kinds
    tables: Any = payload.get('tables')
    if tables == 'dispatch':
        written: Any = payload.get('dispatch_tables')
        return not isinstance(written, list) or 'dispatch.agent_sessions' in written or 'dispatch.sessions' in written
    return not isinstance(tables, list) or 'dispatch.agent_sessions' in tables or 'dispatch.sessions' in tables


def launched(store: Store, work_id: str, pid: int) -> dict[str, Any]:
    """How a launch came out: running with its session once the agent made one, or failed with why, read from the
    session row its runner writes either way. The rows are read again only when the runner says it wrote one for this
    ticket, its `map.changed` heard through the base's listener, BASE-053, or when it exits; nothing polls. The
    runner's own start limit bounds the wait; a runner that ends without a row failed too."""
    from .runner import START_LIMIT
    heard = threading.Event()

    def told(payload: dict[str, Any]) -> None:
        if launch_concerns(payload, store.project_id, work_id):
            heard.set()
    process = RUNNERS.pop(pid, None)
    if process is not None:
        threading.Thread(target=lambda: (process.wait(), heard.set()), name='metaform-launch', daemon=True).start()
    deadline = time.monotonic() + START_LIMIT
    with events.listen('dispatch', told):
        while True:
            heard.clear()  # before the read, so a change during it wakes the wait again
            ended = process.poll() is not None if process is not None else runner_of(pid) != work_id
            held = intake_store(store, work_id) if intake_id(work_id) else store
            rows = sessions(held, work_id, verify=False) if held is not None else []
            if rows:
                row = rows[-1]
                if row['state'] == 'running':
                    return {'state': 'running', 'session_id': row['session_id']}
                return {'state': 'failed', 'reason': str(row.get('how') or 'the runner ended')}
            if ended:  # read after it ended, so a row it wrote on its way out is in this read
                return {'state': 'failed', 'reason': 'its runner ended before the agent started; its log says why'}
            if not heard.wait(max(deadline - time.monotonic(), 0)):
                return {'state': 'failed', 'reason': 'its runner did not start the agent in time; its log says why'}


async def options(ctx: Context) -> dict[str, Any]:
    """What each agent offered at its last session in this project, P199: its settings with their names and choices,
    `picks`, the list every picker shows (`picker_entries`), the value dispatch_<agent>_<option> gives each, its auth methods and its extensions. An agent that has not run has
    none yet, and its next step primes it: prime=true starts it, makes one session with no MCP server and no prompt,
    reads what session/new answered, and closes it, so no tokens are spent."""
    store = ctx.require_store()
    named = str(ctx.nouns['agent']) if ctx.nouns.get('agent') else None
    if ctx.nouns.get('prime'):
        may_steer(ctx)
        if named is None:
            raise Stop('prime=true starts one agent; name it.', 'metaform dispatch options agent=claude prime=true')
        runnable(ctx, agent_named(named))
        from .runner import prime
        await prime(ctx, store, named)
    rows = await asyncio.to_thread(catalog_rows, store)
    chosen = {agent: chosen_options(ctx, agent) for agent in agent_choices()}
    listed: list[dict[str, Any]] = []
    for agent in [agent_named(named)] if named else agent_choices():
        row = rows.get(agent)
        offered = cast(list[dict[str, Any]], (row or {}).get('settings') or [])
        listed.append({
            'agent': agent, 'label': agent_label(agent), 'version': row['version'] if row else None,
            'seen': row['seen'] if row else None,
            'settings': [{'key': option_key(one), 'id': one.get('id'), 'name': one.get('name'),
                          'category': one.get('category'), 'type': one.get('type'), 'current': one.get('current'),
                          'choices': [{key: choice.get(key) for key in ('value', 'name', 'description')}
                                      for choice in cast(list[dict[str, Any]], one.get('options') or [])],
                          'picks': picker_entries(one) if one.get('type') != 'boolean' else [],
                          'chosen': chosen.get(agent, {}).get(option_key(one)),
                          'setting': next((key for key, _, option in option_settings(agent)
                                           if option == option_key(one)), None)} for one in offered],
            'unmatched': {key: value for key, value in chosen.get(agent, {}).items()
                          if key not in {option_key(one) for one in offered}},
            'auth': row['auth'] if row else None, 'extensions': row['extensions'] if row else None,
            'next': None if row else f'metaform dispatch options agent={agent} prime=true'})
    return {'agents': listed}


def persons_own(ctx: Context, what: str) -> None:
    """Refuse an agent over MCP or its CLI what only the person decides, as a person-only setting is refused: a change
    to a ticket's intended outcome or to what it costs, spec 04 D119. The person lets agents do it by turning
    agents_may_set_control on."""
    may_steer(ctx)
    if (ctx.surface == 'mcp' or ctx.surface == 'cli' and agent_caller()) \
            and not settings.value('agents_may_set_control', ctx.folder):
        said, step = settings.asking(ctx.folder)
        raise PersonsDecision(f'{what} is the person\'s decision, made on the page or in their own terminal, never an '
                              f'agent\'s. {said}', f'{step}do it on the page or in {settings.TERMINAL}')


def persons_answer(ctx: Context, what: str) -> None:
    """Refuse what only the person's own answer gives, an answer to an agent's permission request or consent card:
    over MCP always, and on the command line unless it carries the person's consent, from their terminal or the
    page, `metaform.caller`. agents_may_set_control never lets an agent answer itself (UX review, person-consent)."""
    if ctx.surface == 'mcp' or ctx.surface == 'cli' and agent_caller():
        raise PersonsDecision(f'{what} is the person\'s own answer, given on the page, never an agent\'s.',
                              'ask the person in chat; they answer it on the page')


def offered_values(store: Store, agent: str, key: str) -> list[str] | None:
    """The values an agent offered for one of its settings at its last session, by ACP category or id, then a model's
    short names; None when it has not run in this project, so nothing can be checked."""
    row = catalog_rows(store).get(agent)
    if row is None:
        return None
    for setting in cast(list[dict[str, Any]], row.get('settings') or []):
        if option_key(setting) == key:
            values = option_values(setting)
            return [*values, *(short for short in short_names(setting) if short not in values)]
    return []


def tune(ctx: Context) -> dict[str, Any]:
    """A ticket's own model and effort, P015, kept with its map settings and applied over dispatch_<agent>_<option>
    to its sessions; a running one takes them at once through session/set_config_option. Without the map provider,
    dispatch's original ticket_options still serves a manual tune. The person's
    own, since it changes what the ticket costs. A value the ticket's agent did not offer at its last session is
    refused with the values it offers; one for an agent that has not run here is kept with a notice."""
    persons_own(ctx, 'A ticket\'s model and effort')
    store = ctx.require_store()
    record = ticket(store, str(ctx.nouns['id']))
    given = {field: ctx.nouns.get(field) for field in ('model', 'effort') if field in ctx.nouns}
    if not given:
        raise Stop('Give model=, effort= or both; none clears one.', 'metaform dispatch options')
    live = running(store, record.id)
    agent = str(live['agent']) if live is not None else agent_for(  # the agent autostart would start on it
        ctx, record, preferred(record, ticket_settings(ctx).get(record.id), str(ctx.setting('dispatch_agent')), store=store))
    if runtime_provider(ctx) is not None:
        kept = edit_runtime(ctx, record.id, given, agent=agent)
        edited: dict[str, Any] = {'work_id': record.id, **kept, 'agent': agent}
        if live is not None:
            edited['applied'] = tell(live, 'tune')
        return edited
    notices: list[dict[str, str]] = []  # a write that does not fit is kept, with its notice, BASE-044
    for field, value in given.items():
        said = str(value).strip()
        if said in ('', 'none'):
            continue
        key = 'model' if field == 'model' else 'thought_level'
        offered = offered_values(store, agent, key)
        if offered is None:
            notices.append({'where': field, 'message': f'{agent} has not run in this project yet, so {field}={said} '
                            f'is kept unchecked; metaform dispatch options agent={agent} prime=true lists what it '
                            'offers.'})
        elif said not in offered:
            raise Stop(unknown_choice(agent, offered_option(store, agent, key) or {}, said),
                       f'metaform dispatch options agent={agent}')
    with own_store(store).tables() as tx:
        tx.concern(work_id=record.id, kind='ticket')  # its event names the ticket, BASE-053
        held = tx.get('ticket_options', {'work_id': record.id})
        kept = {field: (held[field] if held else None) for field in ('model', 'effort', 'prompts', 'mode')}
        kept.update({field: None if str(value).strip() in ('', 'none') else str(value).strip()
                     for field, value in given.items()})
        tx.delete('ticket_options', {'work_id': record.id})
        if any(kept.values()):
            tx.insert('ticket_options', {'work_id': record.id, **kept, 'seq': time.time_ns()})
    result: dict[str, Any] = {'work_id': record.id, 'agent': agent,
                              **{field: kept[field] for field in ('model', 'effort')},
                              **({'notices': notices} if notices else {})}
    if live is not None:
        result['applied'] = tell(live, 'tune')
    return result


def cancel(ctx: Context) -> dict[str, Any]:
    """Cancel a ticket, P232: the agent working it, if any, has its turn cancelled with session/cancel and its session
    ended, as the person's own stop, so nothing retries it; then the ticket is closed with the reason as its
    resolution and its outcome `cancelled`, the terminal state of the one status vocabulary, so every read of it,
    the work list and the board among them, shows it cancelled and never completed. The person's own: it changes the
    ticket's intended outcome."""
    persons_own(ctx, 'Cancelling a ticket')
    store = ctx.require_store()
    work_id = str(ctx.nouns['id'])
    record = ticket(store, work_id)
    if record.done:
        raise Stop(f'Work {work_id} was done at {record.done}.', f'metaform map work id={work_id}')
    given: Any = ctx.nouns.get('reason') or []
    reason = (' '.join(str(word) for word in cast(list[Any], given)) if isinstance(given, (list, tuple))
              else str(given)).strip()
    stopped: dict[str, Any] | None = None
    live = next((row for row in reversed(sessions(store, work_id)) if row['state'] == 'running'), None)
    if live is not None:
        stopped = tell(live, 'cancel')
    store.finish_work(work_id, f'Cancelled: {reason}' if reason else 'Cancelled.', reason or 'cancelled by the person',
                      outcome='cancelled')
    return {'work_id': work_id, 'state': 'cancelled', 'reason': reason or None, 'session': stopped}


async def login(ctx: Context) -> dict[str, Any]:
    """Log an agent in through ACP, P031, only when the person asks: its auth methods are read from initialize; an
    agent-run method is called with authenticate, a terminal method runs the agent's own login in this terminal when
    there is one, and an env_var method names the variable to set. Metaform never reads or stores a credential."""
    may_steer(ctx)
    agent = agent_named(str(ctx.nouns['agent']))
    runnable(ctx, agent)
    from .runner import login as logging_in
    return await logging_in(ctx, agent, str(ctx.nouns['method']) if ctx.nouns.get('method') else None)


def spend_read(ctx: Context) -> dict[str, Any]:
    """What agents spent today, on a ticket when one is named, and by each run today, each against its budgets, M01:
    billable tokens, cost where the agent reports it, and the sessions that reported no usage, `unmetered`, which no
    budget can see."""
    store = ctx.require_store()
    day = today()
    runs = sorted({str(row['run']) for row in spend_rows(store, {'day': day})})

    def budgets(*keys: str) -> dict[str, int]:
        return {key.removeprefix('dispatch_budget_'): int(ctx.setting(key) or 0) for key in keys}
    result: dict[str, Any] = {
        'day': day, 'today': {**spent(store, day=day), 'budgets': budgets('dispatch_budget_day',
                                                                          'dispatch_budget_cost_day')},
        'runs': [{'run': run, **spent(store, run=run)} for run in runs],
        'run_budget': int(ctx.setting('dispatch_budget_run') or 0),
        'measure': 'tokens are an estimate of what is billed: input, output and cache writes, cache reads at a '
                   'tenth; cost is what the agent reports, in its currency, budgets in its hundredths'}
    if ctx.nouns.get('id'):
        work_id = ticket(store, str(ctx.nouns['id'])).id
        result['ticket'] = {'work_id': work_id, **spent(store, work_id=work_id),
                            'budgets': budgets('dispatch_budget_ticket', 'dispatch_budget_cost_ticket')}
    notices = [f'{len(blind)} session{"s" if len(blind) != 1 else ""} {where} reported no cost, which the cost budget '
               'cannot see; its agent may report none, as Codex does.'
               for where, part, key in (('today', 'today', 'dispatch_budget_cost_day'),
                                        ('on this ticket', 'ticket', 'dispatch_budget_cost_ticket'))
               if part in result and int(ctx.setting(key) or 0)
               and (blind := cast(dict[str, list[str]], result[part]['unmetered'])['cost'])]
    if notices:
        result['notices'] = notices
    return result


# dispatch serve, BASE-062: imported after what it uses, and as the module loads, so its settings are declared
from .serve import serve as serve_editor


def session_live(folder: Path) -> bool:
    """Whether an agent session runs in the folder's project, so the verbs that steer or stop one are listed over
    MCP, MCP-004."""
    project = project_for(folder)
    # an intake agent still starting is stopped by the same verb, VIEW-045
    return project is not None and (any(row['state'] == 'running' for row in sessions(Store(project), verify=False))
                                    or Store(project).intake_agent() is not None)


def in_session(folder: Path) -> bool:
    """Whether the call comes from a dispatched agent's own session, METAFORM_SESSION, so the verbs only such an agent
    uses are listed over MCP, MCP-004."""
    return bool(os.environ.get('METAFORM_SESSION'))


def merge_waits(folder: Path) -> bool:
    """Whether a merge waits for review in the folder's project, so the verbs that take one over are listed over MCP,
    MCP-004."""
    from .merge import due
    project = project_for(folder)
    return project is not None and bool(due(Store(project)))


from .orchestration import TRANSPORT, plan_changed
from .orchestration import changed as orchestration_changed
from .orchestration import render as render_prompt

MODULE = Module(
    id='dispatch',
    summary='Start an agent on a ticket through ACP, follow it, message it and stop it.',
    purpose='Starts Claude Code, Codex or Google Antigravity on one ticket through the Agent Client Protocol, one session per '
            "ticket, in the project's folder with Metaform's MCP server. What the agent does shows as notes at the "
            "ticket's own window, and each permission it asks for is a question at the ticket's node. Details: metaform "
            'help dispatch.',
    details='Each agent runs your own installed command under your own login: --dispatch-claude, --dispatch-codex and '
            '--dispatch-antigravity set them. Metaform never reads or stores credentials.',
    verbs=(
        Verb('adapter', adapter, 'Run the pinned native ACP adapter over standard input and output.',
             nouns=(Noun('pin', 'The exact native adapter pin, antigravity-acp@1.4.1.'),),
             surfaces=('cli',), needs_project=False, transport=True),
        Verb('signals', read_signals,
             'Read the signals raised on agent sessions, such as an agent that stopped with its ticket open. With '
             'active=false, the cleared ones too.',
             nouns=(Noun('id', 'A work id; omit for every ticket.', required=False),
                    Noun('active', 'true reads waiting signals, false reads cleared signals.', kind='bool', required=False)),
             open_world=True),  # with jev on and its triage chosen, the waiting signals go to Jev, spending credit
        Verb('wait', wait, 'Wait until a ticket is done, its agent stops with it open, or a signal is raised on it. '
                           'With no id, until any ticket of the project is, naming which. It answers pending with the '
                           'call to make next after dispatch_wait_seconds.',
             nouns=(Noun('until', 'done, stopped or signal.'),
                    Noun('id', 'The work id of the ticket; none for every ticket of the project.', required=False),
                    Noun('since', 'A UTC time as 2026-10-11T04:18:04Z: only what happened at or after it wakes the '
                                  'wait. Each answer\'s next call carries it; with no id it is the time of the call.',
                         required=False)),
             switches=('dispatch_wait_seconds',),
             examples=(('metaform dispatch wait until=done id=198452e1...', 'Answers done once the ticket is done.'),
                       ('metaform dispatch wait until=stopped', 'Names the first tickets whose agents stop.')), effect='read'),
        Verb('autostart', autostart, 'Start agents on the waiting tickets in board order, while the person has '
                                     'Full Auto checked. Held tickets are left out, and at most dispatch_agents '
                                     'run at once.',
             nouns=(Noun('batch', 'Maximum new workers admitted in this pass; the server rotates projects between passes.',
                         kind='int', required=False),),
             switches=('dispatch_autostart', 'dispatch_agent', 'dispatch_agents', 'dispatch_recovery',
                       'dispatch_rework_limit'), open_world=True),
        Verb('recover', recover, 'Return the tickets of dead agent runners to the queue, while the dispatch_recovery '
                                 'setting is automatic. Cleanup it cannot be sure of leaves the work taken.',
             switches=('dispatch_recovery',), open_world=True),
        Verb('start', start, 'Start an agent on a ticket; it returns at once, and the map shows the agent at work. On '
                             "a ticket with an agent glyph, the agent then works the glyph's other tickets in turn.",
             nouns=(Noun('id', 'The work id of the ticket.'), Noun('agent', 'claude, codex or antigravity.'),
                    Noun('prompts', 'For this launch only, how its permission prompts are answered: approve-all, '
                                    'approve-reads or ask_all; dispatch_prompts when none is given. The person\'s own.',
                         required=False),
                    Noun('mode', 'For this launch only, the agent\'s own mode, a value dispatch options lists for it; '
                                 'dispatch_<agent>_<option> when none is given. The person\'s own.', required=False),
                    Noun('batch', 'The token of one Start all run, the same for each of its starts: a Stop all in '
                                  'the middle of the run refuses the rest of it.', required=False)),
             switches=('dispatch_claude', 'dispatch_codex', 'dispatch_antigravity'),
             examples=(('metaform dispatch start 198452e1... claude', 'Starts Claude Code on the ticket.'),
                       ('metaform dispatch start 198452e1... claude prompts=approve-reads mode=acceptEdits',
                        'Starts it allowing reads and its own edits without asking, for this launch only.')),
             open_world=True, person_decides=starts_held, page="the ticket's Start agent on the board"),
        Verb('reset', reset, 'Put agent bookkeeping back in order after a crash, returning tickets no live agent holds '
                             'to the queue. Dead sessions are recorded as ended; live agents are left alone.',
             examples=(('metaform dispatch reset', 'Release every ticket a dead agent still holds.'),)),
        Verb('merges', merges, "List the agents' merges waiting for the person's review, the soonest first.",
             switches=('dispatch_worktrees', 'dispatch_test_command'), effect='read'),
        Verb('review', review, "Hold a waiting candidate for the person's explicit review.",
             nouns=(Noun('id', 'The work id of the ticket whose merge waits.'),), listed=merge_waits),
        Verb('merge', merge, 'Integrate a ticket candidate locally. Push only with publish=true.',
             nouns=(Noun('id', 'The work id of the ticket whose merge waits.'),
                    Noun('publish', 'true explicitly requests publishing after local integration.',
                         kind='bool', required=False)), surfaces=('cli',)),
        Verb('system', system, "Start the person's system agent, who talks with them about anything in the project, or "
                               'reuse the running one.',
             nouns=(Noun('agent', 'claude, codex or antigravity; the default agent, dispatch_agent, when none is given.',
                         required=False),
                    Noun('fresh', 'true: start a new conversation, resuming none whatever dispatch_resume_chats says.',
                         kind='bool', required=False)), open_world=True),
        Verb('agents', harnesses, 'List the agents dispatch can start, the default among them, how many more may '
                                  'be summoned and how many tickets may start now. Each comes with its name, its start '
                                  'command, and whether that command is found on this system.',
             switches=('dispatch_agent', 'dispatch_claude', 'dispatch_codex', 'dispatch_antigravity'),
             examples=(('metaform dispatch agents', 'Lists Claude Code, Codex and Google Antigravity with what each needs.'),
                       ('metaform set --dispatch-agent claude', 'Makes Claude Code the default agent.')), effect='read',
             needs_project=False),
        Verb('registry', registry_read, 'List the agents of the ACP Registry dispatch can start, each with its version '
                                        'and whether it runs here, and pin one: add=<id> installs the version listed '
                                        'now and dispatch starts that version until you pin another.',
             nouns=(Noun('agent', 'A registry id, to read its entry whole.', required=False),
                    Noun('add', 'A registry id to pin at the version listed now and install; the person\'s.',
                         required=False),
                    Noun('remove', 'A pinned registry id to stop starting; the person\'s.', required=False),
                    Noun('upgrade', 'true: pin every added agent at the version listed now; the person\'s.',
                         kind='bool', required=False),
                    Noun('refresh', 'true: read the registry again rather than the copy kept.', kind='bool',
                         required=False)),
             switches=('dispatch_registry_url',),
             examples=(('metaform dispatch registry', 'Lists the registry\'s agents and what is pinned.'),
                       ('metaform dispatch registry add=goose',
                        'Pins and installs goose; then dispatch start <work id> goose starts it.')),
             open_world=True, needs_project=False),
        Verb('publication', publication, "Write the ACP Registry entry that would publish Metaform's dispatch serve "
                                         'for review, checked against the registry\'s schema; nothing is sent.',
             nouns=(Noun('out', 'A folder to write <id>/agent.json and <id>/icon.svg in.', required=False),
                    Noun('id', 'The registry id; metaform when none is given.', required=False),
                    Noun('version', 'The version, x.y.z; the installed version when none is given.', required=False),
                    Noun('package', 'The PyPI package uvx runs; metaform when none is given.', required=False),
                    Noun('name', 'The display name.', required=False),
                    Noun('description', 'One line on what it is.', required=False),
                    Noun('repository', 'The source repository URL.', required=False),
                    Noun('license', 'The SPDX license id.', required=False),
                    Noun('license_url', 'The URL of the license text, which the registry requires.',
                         required=False)),
             surfaces=('cli',)),
        Verb('intake', intake, "Start an agent on this project's intake, recording the map as it follows the intake "
                               'prompt. An open page follows it. It counts as a summoned agent; one intake runs at a '
                               'time.',
             nouns=(Noun('agent', 'claude, codex or antigravity; the default agent, dispatch_agent, when none is given.',
                         required=False),
                    Noun('resume', 'true: start it although an intake is being recorded that no agent of Metaform\'s '
                                   'started, to resume that intake once no agent is still recording it.',
                         kind='bool', required=False),
                    Noun('map', 'On a project mapped already: extend, the default, checks and refines the map in use; '
                                'new, only when the person asks for it, starts a separate map beside it, which stays '
                                'apart until the person makes it active.', required=False,
                         schema={'type': 'string', 'enum': ['extend', 'new']}),
                    Noun('name', 'With map=new, the new map\'s name: 1 to 64 letters, digits, ., _ and -; its date '
                                 'when none is given.', required=False),
                    Noun('wait', 'true: answer once the agent has made its session, state running, or with why it '
                                 'did not start, state failed; the agent\'s own start limit bounds the wait.',
                         kind='bool', required=False),
                    Noun('text', 'What the intake is for, a target or a request, as `intake prompt` takes it; '
                                 'nothing means this project.', required=False, many=True)),
             switches=('dispatch_agent', 'dispatch_claude', 'dispatch_codex', 'dispatch_antigravity'),
             examples=(('metaform dispatch intake agent=claude', 'Starts Claude Code on the intake of this project.'),
                       ('metaform dispatch intake -- "src/engine only"',
                        'Starts the default agent on an intake of what is asked.')), open_world=True,
             person_decides=new_map_asked),
        Verb('helper', helper, "Start a helper agent with a brief and no ticket, for the person's system agent: a "
                               'figure on the map, steered and stopped like any agent, outside the worker slots. It '
                               "reports one line to the system agent's inbox when done and ends.",
             nouns=(Noun('agent', 'claude, codex or antigravity; the default agent, dispatch_agent, when none is given.',
                         required=False),
                    Noun('wait', 'true: answer once the agent has made its session, state running, or with why it '
                                 'did not start, state failed.', kind='bool', required=False),
                    Noun('text', 'The brief: what to do, where, and what to report back.', many=True)),
             switches=('dispatch_agent', 'dispatch_claude', 'dispatch_codex', 'dispatch_antigravity'),
             examples=(('metaform dispatch helper -- "Find why the page freezes on a node click; report the cause."',
                        'Starts the default agent on the brief; its thread reads with dispatch sessions id=<work id>.'),),
             open_world=True),
        Verb('resume', resume, 'Resume an ended agent session in place, so the agent keeps its memory and its thread '
                               'goes on. It works where the agent can load or resume a session, and waits for your '
                               'next message.',
             nouns=(Noun('id', 'The work id of the session\'s ticket, an intake agent\'s work id, or an agent\'s name, '
                               'for the latest session of that name.'),
                    Noun('session', 'The session id or the agent\'s name; the latest session of the ticket when none is '
                                    'given.', required=False)),
             examples=(('metaform dispatch resume 198452e1... session=4f2c...', 'Resumes that session.'),
                       ('metaform dispatch resume cosmic-argon', 'Resumes the latest session called cosmic-argon.')),
             open_world=True),
        Verb('permit', permit, 'Answer an agent\'s waiting permission request with one of its options, by its id or '
                               'its name, or its waiting question with your answer, as the person chooses it.',
             nouns=(Noun('id', 'The work id of the agent\'s ticket, or an intake agent\'s work id.'),
                    Noun('request', 'The permission request or question, as its line in the session\'s thread names it.'),
                    Noun('option', 'The option\'s id or name; for a question, the answer, or decline.', many=True)),
             examples=(('metaform dispatch permit 198452e1... 7c1e... -- allow', 'Answers with the option allow.'),),
             surfaces=('cli',), open_world=True),
        Verb('configure', configure, 'Set one of a running agent session\'s settings as its agent offers them: its '
                                     'mode, its model or another option, by the setting\'s id.',
             nouns=(Noun('id', 'The work id of the agent\'s ticket, or an intake agent\'s work id.'),
                    Noun('setting', 'The setting\'s id, as the session\'s state lists it under settings.'),
                    Noun('value', 'A choice\'s value or name, or on or off for a switch.', many=True)),
             examples=(('metaform dispatch configure 198452e1... model -- opus', 'Sets the session\'s model.'),
                       ('metaform dispatch configure 198452e1... mode -- plan', 'Sets the session\'s mode.')),
             surfaces=('cli',), open_world=True),
        Verb('prompts', session_prompts, 'Choose how one running agent session\'s permission requests are answered '
                                         'from now on: ask_all, approve-reads or approve-all, for that session alone.',
             nouns=(Noun('id', 'The work id of the agent\'s ticket, or an intake agent\'s work id.'),
                    Noun('prompts', 'ask_all, approve-reads or approve-all, as dispatch_prompts takes them.'),
                    Noun('session', 'The session, when several run on the ticket; the newest running one if left out.',
                         required=False),
                    Noun('confirm', 'true to choose approve-all, which lets the agent act without asking.',
                         kind='bool', required=False)),
             examples=(('metaform dispatch prompts 198452e1... approve-reads',
                        'Reads and searches are approved; the rest are asked.'),
                       ('metaform dispatch prompts 198452e1... approve-all confirm=true',
                        'Every request of the session is approved, the one waiting now too.')),
             surfaces=('cli',), open_world=True),
        Verb('raise', raise_issue, 'Raise an issue on a node: a sentinel investigates it and brings proposals to the chat; '
                                   'the person chooses one, and it becomes held tickets.',
             nouns=(Noun('node', 'The address of the part the issue is about.'),
                    Noun('agent', 'claude, codex or antigravity; the configured agent by default.', required=False),
                    Noun('text', 'What is wrong, in the person\'s words.', many=True)),
             examples=(('metaform dispatch raise code.alarm.audible -- "The alarm plays twice when the timer ends."',
                        'Starts the sentinel on the alarm with that report.'),),
             surfaces=('cli',), open_world=True),
        Verb('propose', propose, "Record a sentinel's proposals for the issue it was raised on, for the person to "
                                 'choose one on the page. Each is presented beside the part of the map it reserves.',
             nouns=(Noun('issue', 'The work id of the issue the sentinel was raised on.'),
                    Noun('proposals', 'A JSON list, each {"title", "grounds", "disruption", "reach": [addresses], '
                                      '"benefit", "tradeoff", "view": an optional link to its own explanation}.')),
                                      listed=in_session),
        Verb('claim', claim, 'Reserve the part of the map a chosen proposal touches, so no other ticket there starts '
                             'until its tickets land.',
             nouns=(Noun('name', 'What the work is called.'),
                    Noun('nodes', 'The addresses it reserves, as a JSON list.'),
                    Noun('work', 'The work ids of its tickets, as a JSON list.', required=False),
                    Noun('issue', 'The work id of the issue it answers.', required=False)),
             examples=(('metaform dispatch claim "Quieter alarm" nodes=\'["code.alarm.audible"]\' work=\'["<work id>"]\'',
                        'Reserves the alarm for those tickets.'),)),
        Verb('claims', claims, 'List the work claims reserving parts of the map, with their state, and the proposals '
                               'sentinels made.', effect='read'),
        Verb('talk', talk, "Talk with an agent about a ticket, a node, or an ended agent's session. The ticket may be "
                           'open or done; an agent at work on it is talked to directly.',
             nouns=(Noun('id', 'The work id of a ticket, open or done.', required=False),
                    Noun('node', 'The address of a node.', required=False),
                    Noun('session', 'An agent session, as <work id>:<session id>, or an agent\'s name for the latest '
                                    'session of that name.', required=False),
                    Noun('agent', 'claude, codex or antigravity.', required=False)), open_world=True),
        Verb('prep', prep, "Start an agent in a merge's worktree to prepare its code for the person's review.",
             nouns=(Noun('id', 'The work id of the ticket whose merge is under review.'),), open_world=True,
             listed=merge_waits),
        Verb('run', run, 'Run one ticket\'s ACP session in this process until it ends. start runs it detached.',
             nouns=(Noun('id', 'The work id of the ticket.'), Noun('agent', 'claude, codex or antigravity.'),
                    Noun('prep', 'true: help the person prepare a merge under review, in its worktree, VIEW-044.',
                         kind='bool', required=False),
                    Noun('system', 'true: the person\'s system agent, a conversation with no ticket work.',
                         kind='bool', required=False),
                    Noun('talk', 'What a conversation agent talks about: ticket:<id>, node:<address> or '
                                 'thread:<session id>.', required=False),
                    Noun('sentinel', 'The address of the node the person raised an issue on; the ticket holds the '
                                     'report, and the sentinel prompt is served.', required=False),
                    Noun('reservation', 'The startup reservation made by start.', required=False),
                    Noun('persons', "true: the person's own start, or their system agent's at their word, which runs "
                                    'now whatever the routing says of a specialist.', kind='bool', required=False),
                    Noun('assignment', 'The recorded authored assignment this managed launch continues.', required=False),
                    Noun('resume', 'The ended session to go on with, loaded or resumed through ACP.', required=False),
                    Noun('intake', 'true: an intake agent, whose work id names no ticket and whose first turn is the '
                                   'intake, with what the person asked for kept in its launch\'s row.', kind='bool',
                         required=False),
                    Noun('retry', 'true: the supervisor resumes the session to go on with its ticket, with the retry '
                                  'prompt as its next turn.', kind='bool', required=False),
                    Noun('run', 'The run whose budget it spends against, a retry\'s the run of the session it resumes.',
                         required=False),
                    Noun('chosen', 'Jev\'s choice of model and effort, as JSON by ACP category, applied under the '
                                   'person\'s own.', required=False)),
             switches=('dispatch_claude', 'dispatch_codex', 'dispatch_antigravity'), surfaces=('cli',), open_world=True,
             person_decides=starts_held, page="the ticket's Start agent on the board"),
        Verb('message', message, 'Send a person\'s message to the agent working a ticket.',
             nouns=(Noun('target_project', 'Registered destination project; defaults to this project. Replies retain their original project.', required=False),
                    Noun('id', 'The work id of the ticket.'),
                    Noun('session', 'The chat session id, for one of several sessions on the ticket; the latest when '
                                    'none is given.', required=False),
                    Noun('audio', 'A wav recording of the message, sent beside it as an ACP audio block when the '
                                  "agent's session declares audio; removed once read.", required=False),
                    Noun('image', 'A frame the web GUI kept, sent beside the message as an ACP image block when the '
                                  "agent's session declares images; removed once read.", required=False),
                    Noun('text', 'The message.', many=True)),
             examples=(('metaform dispatch message 198452e1... "also run the tests"', 'Sends it as session/prompt.'),
                       ('metaform dispatch message 198452e1... -- "--json"',
                        'Sends --json as written; after --, every word is the message, CLI-003.')), open_world=True,
                        listed=session_live),
        Verb('fork', fork, 'Fork a running agent\'s session into a side conversation that keeps everything it knows, '
                           'where its agent offers session/fork, or message an existing child with fork=<id>. '
                           'Native subagents receive messages through their parent.',
             nouns=(Noun('id', 'The work id of the ticket.'),
                    Noun('session', 'The session id, for one of several on the ticket; the latest when none is given.',
                         required=False),
                    Noun('fork', 'An existing child session to receive the text; native subagents are reached '
                                 'through their parent.', required=False),
                    Noun('text', 'A new fork\'s first turn, or a message to the child named by fork.',
                         required=False, many=True)),
             examples=(('metaform dispatch fork 198452e1... -- "What else did you consider?"',
                        'Asks a fork of the session, leaving the session itself at its work.'),), open_world=True,
                        listed=session_live),
        Verb('broadcast', broadcast, "Send a person's message to every agent running on the project at once, and keep "
                                     'it with whom it reached.',
             nouns=(Noun('team', 'A GC broadcasts to its recorded swarm, including descendants and waiting members.',
                         required=False),
                    Noun('system', "true: tell the person's own system agent too; it is left out otherwise.",
                         kind='bool', required=False),
                    Noun('text', 'The message.', many=True)),
             examples=(('metaform dispatch broadcast -- "stop and commit what you have"',
                        'Tells every agent at work, each at its next turn as from the person.'),), open_world=True),
        Verb('broadcasts', broadcasts, 'List the broadcasts kept on the project, newest first, each with whom it '
                                       'reached.',
             nouns=(Noun('limit', 'How many, the newest; all when none is given.', kind='int', required=False),),
             effect='read'),
        Verb('timer', timer, 'Set a timer that wakes your own session later with a note, cancel one, or list yours.',
             nouns=(Noun('seconds', 'How long until it wakes you, from 1 to 86400.', required=False),
                    Noun('cancel', 'The id of one of your timers, to take it back.', required=False),
                    Noun('text', 'What it wakes you for, said to you when it is due.', many=True, required=False)),
             examples=(('metaform dispatch timer seconds=30 -- "see if the person looked at the figure"',
                        'Wakes this session in 30 seconds with that note.'),
                       ('metaform dispatch timer cancel=1a2b3c4d', 'Takes that timer back.')), open_world=True,
                       listed=in_session),
        Verb('note', note, 'Send a note to other registered agents, by session, ticket, a project\'s system agent '
                           '(to=system, kept for its next session when none runs), part of the map, file or topic: '
                           'information each reads at its next turn, kept on every ticket it touches; it never '
                           'steers. With wait=<seconds> it is a question, and the call waits for the replies. With '
                           'decision=true, the person\'s own system agent relays their decision, which each recipient '
                           'takes as the person\'s direction.',
             nouns=(Noun('target_project', 'Registered destination project; defaults to this project. Replies retain their original project.', required=False),
                    Noun('to', 'One agent: its session id, work id, or ticket number, <address>#<n>; or system, the '
                               'person\'s system agent of this project or of target_project, which takes the note '
                               'in its next session when none runs now.', required=False),
                    Noun('at', 'A part of the map, by Address: every agent at work at it or inside it, so a trunk '
                               'Address reaches a whole area.', required=False),
                    Noun('file', 'A file or folder, from the project folder: every agent whose tool calls touched it.',
                         required=False),
                    Noun('topic', 'Words: every agent whose open ticket\'s title holds them all.', required=False),
                    Noun('reply', 'The id of a note sent to you, to answer it; the answer is threaded to it.',
                         required=False),
                    Noun('wait', 'Seconds, 1 to 120, to wait for the replies, which the call returns; it says plainly '
                                 'who did not answer.', kind='int', required=False),
                    Noun('decision', 'true when the note relays the person\'s decision from their message in this turn: '
                                     'each recipient gets it as the person\'s direction, with that message. Only the '
                                     'person\'s own system agent sends one.', kind='bool', required=False),
                    Noun('summary', 'One sentence saying what the note is and what it needs. Every message works like an '
                                    'inbox: the receiver\'s turn carries one line, your agent and ticket, your '
                                    'ticket\'s title and this sentence, and it reads the whole with dispatch notes '
                                    'note=<id> only when it needs more. Without one, the note\'s first sentence stands '
                                    'in; either is cut to 200 characters.', required=False),
                    Noun('text', 'The note.', many=True)),
             examples=((('metaform dispatch note file=src/metaform/modules/web/page/app/core/dom.js wait=60 -- "I am '
                         'about to change css(); anything I should know?"'),
                        'Asks every agent that touched dom.js, and waits up to a minute for their replies.'),
                       ('metaform dispatch note reply=3f9a0c1d2e4b5a6c -- "Go ahead; I am done with it."',
                        'Answers the note 3f9a0c1d2e4b5a6c, threaded to it.'),
                       (('metaform dispatch note target_project=flask to=system -- "Your app factory raises on import; '
                         'please file it there."'),
                        'Tells the flask project\'s system agent, now or in its next session.')), open_world=True),
        Verb('notes', notes, 'List your notes, sent and received, with where each stands for each receiver: queued, '
                             'delivered, read or replied; note=<id> for one note and its replies.',
             nouns=(Noun('note', 'A note\'s id, for it and the replies threaded to it.', required=False),
                    Noun('limit', 'How many, the latest first; 20 by default.', kind='int', required=False)),
             effect='read'),
        Verb('peers', peers, 'See registered agents, their assignments and conversations, Addresses, files touched '
                             'and what it said last. With at=, file= or topic=, who else is in that part or file, with '
                             'a note ready to ask them before you edit.',
             nouns=(Noun('target_project', 'Registered destination project; defaults to this project. Replies retain their original project.', required=False),
                    Noun('at', 'A part of the map, by Address: those at work at it or inside it.', required=False),
                    Noun('file', 'A file or folder, from the project folder: those whose tool calls touched it.',
                         required=False),
                    Noun('topic', 'Words that the titles of their tickets hold.', required=False)),
             effect='read'),
        Verb('attach', attach, 'Attach a file you made to your own chat, for the person to download there.',
             nouns=(Noun('path', 'The file, in the project; a path from the project folder or your working folder.'),
                    Noun('name', 'The name the person sees and downloads it as; the file\'s own when none is given.',
                         required=False)),
             examples=(('metaform dispatch attach artifacts/brief.txt',
                        'Shows brief.txt in your chat as an attachment with Download.'),), open_world=False,
                        listed=in_session),
        Verb('link', link, 'Link a file to the element whose functionality it realizes: its path added to the '
                           "element's refs in the sources layer, which places it on the map.",
             nouns=(Noun('file', 'The file, a path from the project folder or your working folder.'),
                    Noun('node', 'The Address of the element it realizes; an Address no element has yet is made.'),
                    Noun('ref', "The ref's name, a proper noun for what the file is, unique in the project: for code its "
                                'qualified name, such as engine.run. Made from the path when left out.', required=False),
                    Noun('why', 'Why the file realizes that element, kept with the link.', required=False)),
             examples=(('metaform dispatch link file=src/engine/run.py node=code.engine.runner',
                        'Links run.py to code.engine.runner as engine.run@code.engine.runner.'),)),
        Verb('interrupt', interrupt, 'Interrupt the turn of the agent working a ticket, keeping its conversation open.',
             nouns=(Noun('id', 'The work id of the ticket.'),
                    Noun('session', 'The chat session id, to avoid interrupting a replacement session.', required=False),
                    Noun('direction', 'New direction retained before cancellation and delivered on the next turn.',
                         required=False)),
             examples=(('metaform dispatch interrupt 198452e1...', 'Requests cancellation; the session stays available.'),), open_world=True,
             listed=session_live),
        Verb('stop', stop, 'Stop the agent working a ticket.',
             nouns=(Noun('id', 'The work id of the ticket.'),
                    Noun('session', 'The session id, for one of several on the ticket; the latest when none is given.',
                         required=False)), open_world=True, listed=session_live),
        Verb('stop-all', stop_all, 'Stop every agent of the project, or of every project with home=true, and turn '
                                   'Full Auto off, so nothing starts in their place; an agent stops only the '
                                   'agents it started.',
             nouns=(Noun('home', 'true: every project of this Metaform home, not only this one.', kind='bool',
                         required=False),),
             examples=(('metaform dispatch stop-all', 'Stops every agent of this project and turns Full Auto off.'),
                       ('metaform dispatch stop-all home=true', 'Stops every agent on this machine.')),
             open_world=True, needs_project=False),
        Verb('new', new, 'End the conversation of the agent on a ticket and start a new one in the same role, '
                         'resuming nothing: the system agent, a summoned chat, or the ticket\'s agent.',
             nouns=(Noun('id', 'The work id of the ticket.'),
                    Noun('session', 'The session id, for one of several on the ticket; the latest when none is given.',
                         required=False)), surfaces=('cli',), open_world=True),
        Verb('sessions', read_sessions, 'Read live sessions, named sessions or tickets, or a cursor page of history.',
             nouns=(Noun('id', 'The work id of the ticket, or an agent\'s name for the latest session of that name '
                               'alone; none for every ticket.', required=False),
                    Noun('session', 'One session of the named ticket.', required=False),
                    Noun('ids', 'Only these ticket ids.', kind='json', required=False,
                         schema={'type': 'array', 'items': {'type': 'string'}}),
                    Noun('session_ids', 'Only these session ids.', kind='json', required=False,
                         schema={'type': 'array', 'items': {'type': 'string'}}),
                    Noun('latest', 'Only the newest running session, otherwise the newest session.',
                         kind='bool', required=False),
                    Noun('history', 'Read one page of sessions ended before the live hour.', kind='bool', required=False),
                    Noun('limit', 'History page size, from 1 to 500; 50 by default.', kind='int', required=False),
                    Noun('after', 'The next cursor from the preceding read.', required=False),
                    Noun('thread', 'false leaves the threads out, for a list of the sessions only.', kind='bool',
                         required=False),
                    Noun('since', "Only each thread's lines after this seq; all by default.",
                         kind='int', required=False)), effect='read'),
        Verb('handoff', handoff, 'Read a ticket handed to you by its id: the ticket, the node it is at and the counts '
                                 'there with the calls that read them, and one line saying to work it with map_work.',
             nouns=(Noun('id', 'The work id of the ticket handed on.'),
                    Noun('full', 'true: the full worker\'s brief ahead of it, which is no longer sent to agents.',
                         kind='bool', required=False)),
             examples=(('metaform dispatch handoff id=198452e1...',
                        'Prints the ticket\'s hand-off for the agent it is handed to.'),
                       ('metaform dispatch handoff id=198452e1... full=true',
                        'Prints the full worker\'s brief, then the hand-off.')),
             effect='read', listed=in_session),
        Verb('options', options, 'List the settings each agent offers, its model, effort, mode and the rest, as it '
                                 'offered them at its last session in this project, and the ones dispatch_<agent>_<option> '
                                 'gives it. prime=true starts the agent once to read them, with no prompt.',
             nouns=(Noun('agent', 'claude, codex or antigravity; every agent when none is given.', required=False),
                    Noun('prime', 'true: start the agent, read its options from session/new, and close it.',
                         kind='bool', required=False)),
             examples=(('metaform dispatch options', 'Lists what each agent offered, or how to find out.'),
                       ('metaform dispatch options agent=claude prime=true', 'Starts Claude Code once to read its options.'),
                       ('metaform set --dispatch-claude-model opus --dispatch-codex-effort high',
                        'Gives each agent its default model or effort.')), open_world=True),
        Verb('tune', tune, 'Set the model and effort the agent working a ticket uses, over dispatch_<agent>_<option>; the '
                           'person\'s own. A running session takes them at once.',
             nouns=(Noun('id', 'The work id of the ticket.'),
                    Noun('model', 'A model value its agent offers, as dispatch options lists it; none clears it.',
                         required=False),
                    Noun('effort', 'A thought level its agent offers, as dispatch options lists it; none clears it.',
                         required=False)),
             examples=(('metaform dispatch tune 198452e1... model=opus effort=high', 'Sets both for this ticket.'),),
             open_world=True, listed=session_live),
        Verb('cancel', cancel, 'Cancel a ticket, the person\'s own: its agent\'s turn is cancelled with session/cancel, '
                               'its session ends, and the ticket is closed with the outcome cancelled, never completed.',
             nouns=(Noun('id', 'The work id of the ticket.'),
                    Noun('reason', 'Why it is cancelled, kept as its resolution.', required=False, many=True)),
             examples=(('metaform dispatch cancel 198452e1... -- "No longer needed"', 'Cancels the ticket.'),),
             effect='remove', open_world=True),
        Verb('login', login, 'Log an agent in through ACP authenticate, with the login method it offers; the person '
                             'only. With no method, it lists the methods.',
             nouns=(Noun('agent', 'claude, codex or antigravity.'),
                    Noun('method', 'The id of one of the agent\'s auth methods.', required=False)),
             examples=(('metaform dispatch login codex', 'Lists the ways Codex can log in, or uses its only one.'),),
             surfaces=('cli',), open_world=True),
        Verb('spend', spend_read, 'Read what agents have spent today, on a ticket and by run, in billable tokens and '
                                  'reported cost, against the budgets; sessions that report no usage are named.',
             nouns=(Noun('id', 'A work id, for that ticket\'s spend too.', required=False),),
             switches=('dispatch_budget_ticket', 'dispatch_budget_run', 'dispatch_budget_day',
                       'dispatch_budget_cost_ticket', 'dispatch_budget_cost_day', 'dispatch_budget_action'),
             effect='read'),
        Verb('serve', serve_editor, 'Serve Metaform to an editor as an ACP agent over standard input and output: '
                                    "Zed, JetBrains IDEs and other ACP clients mount it. With an agent behind it, the "
                                    "conversation passes through with Metaform's MCP server added and is recorded, so "
                                    "the page shows and steers it; alone, it answers Metaform's commands.",
             nouns=(Noun('agent', 'claude, codex or antigravity to pass through, none for Metaform alone; '
                                  'dispatch_serve_agent when none is given.', required=False),
                    Noun('command', 'An ACP adapter command to pass through instead, after --.', required=False,
                         many=True)),
             switches=('dispatch_serve_agent',),
             details='The editor runs it in the project folder. Its slash commands are the MCP tools, such as '
                     '/map_read; session/list and session/load reach the dispatch sessions of the project. Register '
                     'it with metaform install zed or metaform install jetbrains.',
             examples=(('metaform dispatch serve', 'Serves the agent dispatch_serve_agent names.'),
                       ('metaform dispatch serve agent=none', 'Serves Metaform alone, starting no model.'),
                       ('metaform dispatch serve -- npx -y @agentclientprotocol/claude-agent-acp',
                        'Passes the conversation through to that adapter.')),
             surfaces=('cli',), transport=True, open_world=True),
    ),
    # The agents' tools on the web GUI. Starting and steering agents runs as the command line runs it, in the
    # person's environment, BASE-052, so each tool opens the page's own dialog for it rather than running a verb.
    toolbar=(
        ToolbarItem('chat', 'Chat', 'Talk with your system agent or any agent at work, and answer what it asks.',
                    icon='chat', pane='dock', order=70, shortcut='Alt+C'),
        ToolbarItem('agent-on-node', 'Agent on this node', 'Start an agent on a ticket at the selected node, with '
                    'the node as its brief.', icon='play', page='dispatch-node', selection='address', order=71),
        ToolbarItem('agents', 'Agents', 'Set how many agents work at once, the default agent and how prompts are '
                    'answered.', icon='terminal', page='agents', placement='extra', order=300),
    ),
    panes=(
        Pane('dock', 'Chat', 'Talk with your system agent or any agent at work, and answer what it asks.',
             icon='chat', page='dock', area='right', group='chat', order=100, min_width=320,
             min_height=240),
    ),
    tables=TABLES,
    subscriptions=(Subscription('work.requeued', requeued), Subscription('dispatch.rework-limit', rework_limit),
                   Subscription('signal.raised', collect), Subscription('map.changed', progress_changed),
                   Subscription('map.changed', orchestration_changed), Subscription('map.changed', board_changed),
                   Subscription('map.changed', hold_review_changed), Subscription('map.changed', plan_changed)),
    work_read=work_read,
    # person.consent: ask_consent, the consent card in a dispatched agent's chat its MCP server asks the person through
    # person.word and person.word.acted: the person's message that started the system agent's turn in flight, and the
    # record in its chat of what it did on it, `metaform.module.persons_word`
    provides=(Provides('base.holds', base_holds), Provides('dispatch.deaths', watch_deaths),
              Provides('person.consent', ask_consent), Provides('work.overlap', overlap), Provides('work.stop', stop_work),
              Provides('person.word', persons_word), Provides('person.word.acted', persons_word_acted),
              Provides('orchestration.transport', TRANSPORT), Provides('prompt.render', render_prompt),
              Provides('dispatch.seats', seat_slots), Provides('dispatch.models', model_for),
              Provides('work.in_force', fix_in_force)),
    start=started,
    stop=None,
    status=None,
)
