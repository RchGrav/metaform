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
import ctypes
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
import tempfile
import threading
import time
import uuid
from collections.abc import Callable, Sequence
from importlib import resources
from pathlib import Path
from typing import Any, cast

from metaform import events, home, prompt_files, settings
from metaform.data import Column, Index, Store, StoreError, Table, Tables, WorkRecord, status
from metaform.module import (
    Context,
    Module,
    Noun,
    Pane,
    Stop,
    Subscription,
    Surface,
    ToolbarItem,
    Verb,
    call,
    child_environment,
    context,
    held_role,
    mcp_server,
    project_for,
    surface,
    work_reads,
)

from . import registry as agent_registry  # by another name: unloading a module drops its submodules' names
from .progress import blocked as rework_blocked
from .progress import changed as progress_changed
from .signals import collect, own_store, requeued, rework_limit
from .signals import read as read_signals

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
SPEND = (Column('session_id', required=True), Column('seq', 'int', required=True),
         Column('work_id', required=True), Column('run', required=True), Column('day', required=True),
         Column('tokens', 'int', required=True), Column('cost', 'real'), Column('currency'),
         Column('input', 'int'), Column('output', 'int'), Column('cache_read', 'int'),
         Column('cache_write', 'int'), Column('thought', 'int'), Column('metered', 'bool', default=True))
TABLES = Tables(version=15, compatible_from=5, tables=(  # 5: agents do not ask; 6, 7, 10 to 15 only add
    Table('sessions', key=('session_id',),
          columns=(Column('session_id', required=True), Column('work_id', required=True), Column('agent', required=True),
                   Column('state', required=True), Column('nonce'), Column('pid', 'int'), Column('port', 'int'),
                   Column('token'), Column('how'), Column('started', required=True), Column('seq', 'int', required=True),
                   Column('runner'), Column('recovery', 'json'), Column('origin')),
          indexes=(Index(('work_id', 'seq')), Index(('seq',)))),
    Table('lines', key=('session_id', 'name'),
          columns=(Column('session_id', required=True), Column('name', required=True), Column('work_id', required=True),
                   Column('kind', required=True), Column('text', required=True), Column('seq', 'int', required=True)),
          indexes=(Index(('session_id', 'seq')), Index(('work_id', 'seq')))),
    Table('merges', place='project', key=('work_id',),
          columns=(Column('work_id', required=True), Column('branch', required=True), Column('worktree', required=True),
                   Column('state', required=True), Column('reason'), Column('ready', 'real', required=True),
                   Column('deadline', 'real', required=True), Column('seq', 'int', required=True)),
          indexes=(Index(('state',)),)),
    # An issue raised and not yet talking: waiting for its node or a slot, oldest first, or, with `started`, its
    # sentinel launched and its session not made yet, which holds a slot all the same, VIEW-045.
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
    # The supervisor's retries of a ticket's session that stopped without the person's stop, and when the next may run.
    Table('attempts', key=('work_id',),
          columns=(Column('work_id', required=True), Column('session_id', required=True),
                   Column('retries', 'int', required=True), Column('next_at', 'real', required=True),
                   Column('how'), Column('handed', 'bool', default=False), Column('seq', 'int', required=True))),
))
PRIVATE = ('port', 'token', 'pid', 'nonce', 'recovery', 'origin')  # what only this module uses to reach a session
# Dispatch's own agents, each started by default at the version the ACP Registry lists for it, claude-acp, codex-acp
# and gemini, read 2026-10-12, so every start runs the same adapter until the person pins another, P013; `dispatch
# registry` names a newer one. Any other agent of the registry is added by the person and pinned, registry.py.
AGENTS = {
    'claude': ('Claude Code', 'npx -y @agentclientprotocol/claude-agent-acp@0.89.1'),
    'codex': ('Codex', 'npx -y @agentclientprotocol/codex-acp@2.2.2'),
    'gemini': ('Gemini CLI', 'npx -y @google/gemini-cli@0.63.0 --acp'),
}
# The oldest Node.js every adapter above runs on, from their packages' engines, read 2026-10-15: claude-agent-acp
# 0.89.1 needs node >=22, gemini-cli 0.63.0 >=20, codex-acp 2.2.2 names none. A build's README asks testers for it.
NODE = '22'
# A setting that decides which agents run, how they start, what they are permitted, how they are watched or when
# their work lands is person_only: written by the person, never by an agent over MCP, CLI-011. How long one wait
# blocks only paces the agent that calls it, so it is not.
settings.boolean('dispatch_autostart', False, label='Start agents on their own', person_only=True,
                 help='Start agents on tickets that have not been tried, and resume a worker\'s session that ended '
                      'without your stop, up to dispatch_retries; a ticket whose agent stopped with it open waits for '
                      'you.',
                 category='agents', heading='Starting work', essential=20)
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


settings.choice('dispatch_agent', agent_choices, 'codex', person_only=True,
                help='The default agent: the one started when none is chosen, for a chat, an issue or an intake.',
                details='Starting an agent of another kind on a ticket leaves it as it is; the person sets it here or '
                        'from the page.',
                label='Default agent', category='agents', heading='Starting work', essential=10)
settings.choice('dispatch_recovery', ['manual', 'automatic'], 'manual', label='Dead runner recovery', person_only=True,
                help='manual leaves a dead runner ticket taken; automatic verifies death and cleans up before returning it.',
                details='Applies before Autostart selection or with dispatch recover. Older sessions or uncertain cleanup '
                        'still require manual recovery. Session reads never change ownership.',
                category='agents', heading='Starting work')
settings.number('dispatch_agents', 5, min=1, person_only=True,
                help='How many agents may work at once. The person can always summon one '
                'more; agents the person summons beyond that use the slots the agents at work leave free.',
                label='Agents at once', category='agents', heading='Starting work', unit='agents', essential=30)
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
settings.boolean('dispatch_worktrees', False, person_only=True,
                 help='Each ticket\'s agent works in a git worktree of its own, and done '
                 'work waits for review, then merges into the active dev branch, VIEW-044. Off until the dev branch '
                 'holds the work in progress, since a worktree starts from the last commit.')
settings.number('dispatch_abandoned_branch_days', 30, min=1, person_only=True, label='Abandoned branches kept',
                help='Days the branch of a ticket closed without merging is kept, its work committed, before it is '
                     'removed.',
                details='Checked with dispatch_worktrees on, before each autostart and with dispatch recover: such a '
                        'branch, with its worktree and the snapshot it began from, is removed once its last commit is '
                        'this old, and git\'s record of worktrees already gone is pruned. A branch whose merge waits '
                        'is never removed.')
settings.text('dispatch_test_command', '', person_only=True,
              help='The project\'s test command, run in a worktree before its merge is '
              'offered and again before it merges; with none, no merge is offered.')
settings.number('dispatch_review_minutes', 15, min=1, person_only=True,
                help='How long done work waits for a person\'s review before it merges by itself.')
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
settings.boolean('dispatch_stay_connected', False, person_only=True, label='Stay connected',
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
                help='How many times autostart resumes a ticket\'s session that stopped without your stop, before '
                     'handing it to you.',
                details='A retry resumes the same ACP session with session/resume or session/load, so the agent keeps '
                        'its own memory of the work; it waits 30 seconds, doubled each time. A session you '
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
STRENGTHS = {'claude': 'front-end, GUI and page work, and long reasoning over prose',
             'codex': 'back-end, system and data work, and exact code changes',
             'gemini': 'large reads across many files'}


def strengths_key(agent: str) -> str:
    return f'dispatch_{agent}_strengths'


for _agent in agent_choices():
    settings.text(strengths_key(_agent), STRENGTHS.get(_agent, ''), person_only=True,
                  label=f'What {AGENTS[_agent][0] if _agent in AGENTS else _agent} does well',
                  help=f'What {_agent} does well, in a few words; Jev reads it to choose the agent for a ticket when '
                       'jev is on and its choose_agent decision is chosen.',
                  details='Only autostart asks Jev, and only for a ticket you gave no agent: your choice on the ticket, '
                          'then its eligible agents, always win, and the model and effort you set for the ticket or the '
                          'agent win over Jev\'s. With Jev off, unsure or unreachable, the ticket\'s area picks the agent '
                          'as before. Empty, Jev is told only the agent\'s name.')
def _withheld_choices(ctx: Context) -> list[str]:
    """What an intake's server can leave out: each module, its reading tools, and each of its tools by name."""
    from metaform import loader
    found: list[str] = []
    for item in sorted((one for one in loader.discover() if one.module is not None), key=lambda one: one.id):
        assert item.module is not None
        found += [item.id, f'{item.id}:read', *(f'{item.id}_{verb.name}' for verb in item.module.verbs)]
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
                details='Checked before autostart starts or retries anything and before a worker is started; past it, '
                        'a budget signal waits for you, and nothing starts until the next day or a higher budget.',
                category='budgets', heading='Tokens', unit='tokens')
settings.number('dispatch_budget_cost_ticket', 0, min=0, person_only=True, label='Spending limit per ticket',
                help='Hundredths of the currency the agent reports (cents of USD) one ticket may cost; 0 sets no '
                     'limit.',
                details='Cost is what the agent reports in its usage updates, ACP\'s session usage: Claude Code '
                        'reports it as each turn ends, Codex not at all, which dispatch spend says. A cost budget is '
                        'held against each currency on its own, and acts when a turn ends.',
                category='budgets', heading='Spending', unit='cents')
settings.number('dispatch_budget_cost_day', 0, min=0, person_only=True, label='Daily spending limit',
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
    """A setting's choices: default, then each value the agent offered for the option at its last session here; only
    default until it has run once, or `dispatch options agent=<agent> prime=true` has asked it."""
    def choices(ctx: Context) -> list[str]:
        offered = offered_option(ctx.store, agent, key)
        return [AGENT_DEFAULT, *(value for value in (option_values(offered) if offered else []) if value != AGENT_DEFAULT)]
    return choices


def option_words(agent: str, key: str) -> Callable[[Context], dict[str, str]]:
    """Each value in the agent's own words, its name and description as it offered them."""
    def words(ctx: Context) -> dict[str, str]:
        offered = offered_option(ctx.store, agent, key) or {}
        said = {AGENT_DEFAULT: f'Leave it to {agent_label(agent)}: Metaform sends nothing for it.'}
        for choice in cast(list[dict[str, Any]], offered.get('options') or []):
            if (value := str(choice.get('value'))) != AGENT_DEFAULT:
                said[value] = ': '.join(str(part) for part in (choice.get('name'), choice.get('description')) if part)
        return said
    return words


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
                        risky=option_risky(_agent, _option),
                        choices_from=f'metaform dispatch options agent={_agent} prime=true',
                        help=f'{_name}\'s {_label.lower()} for every session it starts here: a value it offers, or '
                             f'default to leave it to {_name}.',
                        details=f'The choices are what {_name} offered at its last session in this project; until it '
                                f'has run once there is only default: start it, or run dispatch options agent={_agent} '
                                'prime=true, which starts it, reads its options and closes it without a prompt. Applied '
                                'to every session it starts, new, loaded or resumed. A ticket\'s own model and effort, '
                                'set with dispatch tune, go over these.',
                        category='agent_options')


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



def carry_strengths(ctx: Context | None = None) -> list[str]:
    """Once per home, as dispatch starts: each entry of a stored dispatch_agent_strengths list, `<agent>=<words>`,
    becomes that agent's dispatch_<agent>_strengths at the same scope, and the list is removed, settings cleanup
    2026-10-15. Only what an entry named moves: an agent the list left out now keeps its own default rather than
    being wiped, which was the defect the split fixes. An entry for no agent dispatch starts is dropped and said."""
    del ctx
    return settings.carry_once('dispatch-agent-strengths', _carry_strengths)


def _carry_strengths() -> list[str]:
    said: list[str] = []
    held: dict[str, list[str]] = {}
    for scope in dict.fromkeys(['global', *(home.path_key(record.path) for record in home.projects())]):
        with home.settings_db(scope) as db:
            rows = db.execute("SELECT scope, value FROM settings WHERE owner='dispatch' AND "
                              "key='dispatch_agent_strengths' ORDER BY scope, position").fetchall()
        for found_scope, raw in rows:
            held.setdefault(str(found_scope), []).append(str(json.loads(raw)))
    for scope, entries in held.items():
        for entry in entries:
            agent, _, words = (part.strip() for part in entry.partition('='))
            key = strengths_key(agent)
            if key not in settings.SCHEMA or not words:
                said.append(f'{scope}: {entry} has no setting to hold it and was dropped.')
            elif words != STRENGTHS.get(agent):
                home.save(scope, 'dispatch', key, [words])
                said.append(f'{scope}: {key} = {words}')
        home.clear(scope, 'dispatch', 'dispatch_agent_strengths')
        home.set_glue(scope, 'dispatch', 'dispatch_agent_strengths', False)
    return said


def started(ctx: Context | None = None) -> list[str]:
    """Dispatch's start: the one-time carries of settings that changed shape."""
    return [*migrate_agent_options(ctx), *carry_strengths(ctx)]

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
                label='Permission prompts', category='agents', heading='Permissions', essential=50)
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
                category='agents', heading='Permissions')


def prompt(name: str, **fills: str) -> str:
    """The prompt `name` of this module's resources/prompts.xml, MCP-031."""
    return prompt_files.required(resources.files(__name__), name, **fills)


def handoff_prompt(work_id: str, folder: Path) -> str:
    """The full worker's brief, read on demand only, with its line on recording what the agent learns only while the
    memory module is on the folder's surface, so an agent is never told to use a command it does not have, BASE-052."""
    memory = any(module.id == 'memory' for module in surface(folder))
    return prompt('handoff', work_id=work_id, record=f"  {prompt('record')}\n" if memory else '')


def work_line(work_id: str, folder: Path, node: str) -> str:
    """What a hand-off adds to the node brief: work the ticket with the map_work tool, whose description says how,
    and, while the memory module is on the folder's surface, the owner's sentence on recording what is learned, with
    the node it is recorded at, so no agent is told to use a tool it does not have."""
    memory = any(module.id == 'memory' for module in surface(folder))
    return prompt('work', work_id=work_id,
                  record=prompt('work_record', node=node) if memory and node else '')


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
    """End a process and every process it started: `npx` starts the agent as a grandchild."""
    if (system or os.name) == 'nt':
        subprocess.run(['taskkill', '/T', '/F', '/PID', str(pid)], capture_output=True, check=False)
        return
    try:
        os.killpg(pid, signal.SIGKILL)
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


def ticket(store: Store, work_id: str) -> WorkRecord:
    try:
        return store.ticket(work_id).work
    except StoreError as error:
        raise Stop(str(error), 'metaform map work open=true') from None


# An intake agent's session holds no ticket: its work id is this prefix and a token of its own, so the CLI and the
# page reach it as they reach any session, and nothing takes it for a ticket. Its row stays in the metaform it began
# in, which an intake into a new base leaves for the one it activates at its finish, VIEW-045 and BASE-039.
INTAKE = 'intake-'


def intake_id(work_id: Any) -> bool:
    return str(work_id).startswith(INTAKE)


def intake_store(store: Store, work_id: str) -> Store | None:
    """This module's store on the metaform an intake agent's session is kept in: the active one first, then the
    project's other metaforms; None when no metaform holds it."""
    for base in sorted(home.bases(store.project_id), key=lambda base: not base.active):
        held = Store(store.project_id, base=base.id, module='dispatch')
        try:
            with held.tables(write=False) as tx:
                if tx.rows('sessions', {'work_id': work_id}, limit=1).results:
                    return held
        except StoreError:
            continue
    return None


def session_state(store: Store, session_id: str) -> dict[str, Any] | None:
    """A session's state as its runner last kept it: what the agent can do, its settings, commands, plan, usage, the
    folder it worked in and the parts of the map it touched; None for a session that kept none."""
    try:
        with own_store(store).tables(write=False) as tx:
            found = tx.rows('lines', {'session_id': session_id, 'name': 'state'}, limit=1).results
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
            stored = tx.rows('sessions', {'session_id': session_id}, limit=1).results
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


def resume_spawn(store: Store, work_id: str, agent: str, extra: list[str], name: str) -> dict[str, Any]:
    """A runner that resumes a session in place, started only while no live runner holds it or is starting to resume
    it: the check and the start are one lock between processes, so two passes of the agent starter, two servers, or a
    Call while a server restarts never resume one ACP session twice. A held session is reused, `state` running."""
    session_id = next(word.partition('=')[2] for word in extra if word.startswith('resume='))
    marker = resuming_path(session_id)
    home.mkdir_private(marker.parent)
    with home.file_lock(marker.parent / 'resume.lock'):
        pid = holder(store, work_id, session_id)
        if pid is not None:
            return {'state': 'running', 'pid': pid}
        started = spawn(store, work_id, agent, extra, name)
        home.write_private(marker, str(started['pid']))
    return started


def sessions(store: Store, work_id: str | None = None, *, verify: bool = True,
             open_work: Sequence[WorkRecord] | None = None) -> list[dict[str, Any]]:
    """The sessions, oldest first, of one ticket or of every ticket, read through this module's own tables whatever
    module the store was opened for."""
    own = own_store(store)
    try:
        with own.tables(write=False) as tx:
            found = (tx.rows('sessions', {'work_id': work_id}, by=('work_id', 'seq'), limit=0) if work_id
                     else tx.rows('sessions', by=('seq',), limit=0)).results
            rows = [dict(row) for row in found]
    except StoreError:
        return []
    if not verify:
        return rows
    # one read of the open tickets for every running row, rather than a ticket read for each
    opened: set[str] = set()
    if any(row['state'] == 'running' for row in rows):
        opened = {record.id for record in (open_work if open_work is not None
                                               else store.work(open=True, limit=0).results)}
    # an intake agent's session holds no ticket, so no ticket's being done ends it
    return [session_status(own, row, done=row['work_id'] not in opened and not intake_id(row['work_id']))
            for row in rows]


def recorded_activity(store: Store, row: dict[str, Any]) -> str:
    """Only a final recorded end_turn supports idle activity; it says nothing about session liveness."""
    activity = 'unknown'
    # Old runners cannot report their current turn. A final recorded end_turn supports idle activity only;
    # it does not end the session, and later output makes that historical turn insufficient evidence.
    try:
        with store.tables(write=False) as tx:
            lines = tx.rows('lines', {'session_id': row['session_id']}, by=('session_id', 'seq'), limit=0).results
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
FOREIGN = 'another Metaform home started it'


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
    if how in DIED:
        return {'status': 'failed', 'reason': 'runner died'}
    if how.startswith(('it failed', 'it did not start')):
        return {'status': 'failed', 'reason': how}
    if how in ('cancelled by the person', 'stopped by the person', 'the runner was terminated'):
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
    this module uses to reach them, its signals, and its own model and effort set with dispatch tune, by ACP
    category, shown under `dispatch` in `map work id=<id>`, BASE-035; nothing on a ticket dispatch holds nothing of."""
    if ctx.store is None:
        return None
    found = sessions(ctx.store, record.id)
    from .signals import rows
    signals = rows(ctx.store, record.id)
    chosen = ticket_options(ctx.store, record.id)  # the ticket's own model and effort, P015, shown where it is read
    chosen = {**chosen, **launch_options(ctx.store, record.id)}  # and its latest launch's permissions
    if not found and not signals and not chosen:
        return None
    return {'sessions': [{**{key: value for key, value in session.items() if key not in PRIVATE},
                          **session_work_status(session, signals)} for session in found],
            'signals': signals, **({'options': chosen} if chosen else {}),
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
        raise Stop(f'{agent} is not eligible for work {record.id}; eligible agents: {", ".join(agents)}.',
                   f'metaform map work id={record.id}')


def agent_for(ctx: Context, record: WorkRecord, agent: str | None = None) -> str:
    """Use the configured agent when eligible, otherwise the first agent listed, MAP-058."""
    chosen = agent or str(ctx.setting('dispatch_agent'))
    agents = eligible_of(ctx, record)
    return agent_named(chosen if not agents or chosen in agents else agents[0])


def startable(ctx: Context, store: Store, record: WorkRecord, agent: str) -> None:
    """Refuse a ticket done, taken or already holding a session, and an occupied glyph, VIEW-039 and VIEW-040:
    tickets with one glyph are one agent's, done one at a time."""
    require_eligible(ctx, record, agent)
    if record.done:
        raise Stop(f'Work {record.id} was done at {record.done}.', 'metaform map work open=true')
    if record.taken:
        raise Stop(f'Work {record.id} is already taken by {record.taken_by or "an agent"}.',
                   'metaform map work open=true')
    if not (record.task or '').strip():
        raise Stop(f'Work {record.id} has no task: nothing for an agent to do until one is written.',
                   f'metaform map work op=edit id={record.id} task="<what it needs>"')
    lock = claimed(store, record.address or record.receiver_address, record.id)
    if lock is not None:  # work claims are the scheduling lock, LAYER-029: no ticket inside another's claim starts
        raise Stop(f'Work {record.id} is on a part of the map claimed by "{lock["name"]}" until that work has landed.',
                   'metaform dispatch claims')
    glyph = glyph_of(ctx, record)
    if glyph is not None:
        occupied = next((held for held in store.work(open=True, limit=0).results
                         if held.taken and (held.taken_by or '').startswith('dispatch starting ') and
                         held.id != record.id and glyph_of(ctx, held) == glyph), None)
        if occupied is not None:
            raise Stop(f'Agent {glyph} is at work on work {occupied.id}; the tickets with its glyph are done '
                       'one at a time.', f'metaform map work id={occupied.id}')
    for session in sessions(store, record.id if glyph is None else None):
        if session.get('state') != 'running':
            continue
        if session['work_id'] == record.id:
            raise Stop(f'Work {record.id} already has an agent session.',
                       f'metaform dispatch sessions id={record.id}')
        if glyph is not None and glyph_of(ctx, ticket(store, session['work_id'])) == glyph:
            raise Stop(f'Agent {glyph} is at work on work {session["work_id"]}; the tickets with its glyph are done one '
                       f'at a time.', f'metaform map work id={session["work_id"]}')


def next_ticket(ctx: Context, store: Store, glyph: str, *, agent: str | None = None,
                exclude: tuple[str, ...] = ()) -> WorkRecord | None:
    """The glyph's next ticket, VIEW-040: the first not done and not taken in board order, To do before Backlog, each by
    its place, a ticket with none after, as Distribute deals them; an exclude record is no ticket."""
    kept = ticket_settings(ctx)
    waiting = [record for record in store.work(open=True, limit=0).results
               if not record.taken and record.id not in exclude
               and not kept.get(record.id, {}).get('hold') and (record.task or '').strip()]  # no task: nothing to do
    waiting.sort(key=lambda record: (record.held, record.position is None, record.position or 0))
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
        return skills.served(f'logic.skill.{name}', given)
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
        with store.atomic():
            with store.tables() as tx:
                previous = tx.get('sessions', {'session_id': session_id})
                if previous is not None and (previous['work_id'] != work_id
                                             or runner and previous.get('runner') != runner):
                    return  # a late release must never end or clear permissions on the session's latest resume
                if previous is not None and previous['state'] == 'running':
                    tx.update('sessions', {'session_id': session_id}, {'state': 'ended', 'how': how})
            if took and runner and previous is not None and previous['state'] == 'running':
                from .progress import finish
                finish(store, work_id, runner, how)
    if session_id is not None or requeued:
        from .signals import clear_permissions, publish
        ctx = context('dispatch', Path(store.project().path), project=store.project_id)
        if took and runner:
            from .progress import refresh
            refresh(ctx, store, ticket(store, work_id))
        if session_id is not None:
            clear_permissions(ctx, session_id)
            # an ended session is no longer stopped and waiting; not-smooth below says what is left, BASE-057
            publish(ctx, 'stopped-open', work_id=work_id, session_id=session_id, active=False,
                    reason='the session ended')
        if not intake_id(work_id) and not ticket(store, work_id).done:
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
    if row is None:
        return {}
    return {key: str(row[field]) for key, field in (('model', 'model'), ('thought_level', 'effort')) if row[field]}


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
        held = tx.get('ticket_options', {'work_id': work_id})
        kept = {**{field: (held[field] if held else None) for field in ('model', 'effort')}, **given}
        tx.delete('ticket_options', {'work_id': work_id})
        if any(kept.values()):
            tx.insert('ticket_options', {'work_id': work_id, **kept, 'seq': time.time_ns()})


def wanted_options(ctx: Context, store: Store, agent: str, work_id: str | None) -> dict[str, str]:
    """The settings a session of the agent is given: its dispatch_<agent>_<option> settings, then its ticket's own."""
    return {**chosen_options(ctx, agent), **(ticket_options(store, work_id) if work_id and not intake_id(work_id) else {})}


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
            if os.environ.get('METAFORM_ROLE') not in (None, '', 'none'):
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
        unit = 'billable tokens' if found['measure'] == 'tokens' else f'hundredths of {found.get("currency") or "cost"}'
        raise Stop(f'The {"token" if found["measure"] == "tokens" else "cost"} budget per {found["budget"]} is '
                   f'reached: {found["spent"]} of {found["limit"]} {unit}.', str(found['next']))


# address words of front-end work; the page reads this list from harnesses, so it keeps no copy
FRONTEND = frozenset({'gui', 'web', 'page', 'viewer', 'view', 'board', 'ui', 'frontend', 'graphical', 'interface',
                      'graphic', 'display', 'render', 'speech', 'voice'})


def ticket_settings(ctx: Context) -> dict[str, dict[str, Any]]:
    """What the map module keeps on each open ticket, read once: its glyph, its preferred agent and whether the person
    holds it, held tickets included."""
    if not any(module.id == 'map' for module in surface(ctx.folder)):
        return {}
    store = ctx.require_store()
    own = Store(store.project_id, module='map')
    with own.tables(write=False) as tx:
        kept: dict[str, dict[str, Any]] = {
            str(row['work_id']): {'glyph': row['glyph']} for row in tx.rows('glyphs', limit=0).results}
        for row in tx.rows('ticket_settings', limit=0).results:
            kept.setdefault(str(row['work_id']), {}).update(agent=row['agent'], hold=bool(row['hold']))
        for row in tx.rows('eligible', limit=0).results:
            kept.setdefault(str(row['work_id']), {})['eligible'] = row['agents']
    return kept


def jev_choices(ctx: Context, store: Store) -> dict[str, dict[str, str]]:
    """Jev's choice for each waiting ticket the person gave no agent, H23: its agent, and that agent's model and
    thinking level where Jev is sure of them, among the agents installed here, each described by
    its dispatch_<agent>_strengths, and the options each offered at its last session. Asked for at most dispatch_agents
    tickets, the next in board order, within one bounded wait. Empty with Jev off, unsure, unreachable or failing:
    autostart then chooses as it always has."""
    from metaform import jev
    try:
        if jev.config(ctx.folder, 'choose_agent') is None:
            return {}
        kept = ticket_settings(ctx)
        waiting = sorted((record for record in store.work(open=True, limit=0).results
                          if not record.taken and (record.task or '').strip() and not kept.get(record.id, {}).get('hold')
                          and not kept.get(record.id, {}).get('agent')),
                         key=lambda record: (record.held, record.position is None, record.position or 0))
        waiting = waiting[:int(ctx.setting('dispatch_agents'))]
        strengths = {agent: str(ctx.setting(strengths_key(agent)) or '').strip() for agent in agent_choices()
                     if strengths_key(agent) in settings.SCHEMA}
        agents = {agent: strengths.get(agent) or agent_label(agent) for agent in agent_choices()
                  if found_command(ctx, agent) is not None}
        if not waiting or not agents:
            return {}
        rows = catalog_rows(store)
        offered: dict[str, dict[str, dict[str, str | None]]] = {}
        for agent in agents:
            for setting in cast(list[dict[str, Any]], (rows.get(agent) or {}).get('settings') or []):
                category = setting.get('category')
                if category in jev.CATEGORIES:
                    offered.setdefault(agent, {})[str(category)] = {
                        str(choice.get('value')): cast(str | None, choice.get('name'))
                        for choice in cast(list[dict[str, Any]], setting.get('options') or [])}
        tickets = {record.id: {'id': record.id, 'task': record.task or '', 'note': record.note or '',
                               'address': record.address or record.receiver_address or ''} for record in waiting}
        with jev.within(jev.DEADLINE):
            got = jev.choose_agents(ctx.folder, tickets, agents, offered, project=ctx.project)
    except Exception as error:  # noqa: BLE001  a decision that fails leaves autostart as it always was
        sys.stderr.write(f'Jev did not choose agents: {error}\n')
        return {}
    if got is None:
        return {}
    return {work_id: {key: str(value) for key, value in cast(dict[str, Any], decision.answer).items() if value}
            for work_id, decision in got.decisions.items() if decision.sure}


def preferred(record: WorkRecord, kept: dict[str, Any] | None) -> str:
    """The agent a ticket prefers: the one the person chose, or by default Claude for front-end and GUI work and Codex
    for back-end and system work, by the element's Address or, for a purpose record, its receiver's."""
    agent = (kept or {}).get('agent')
    if agent in agent_choices():
        return str(agent)
    return 'claude' if FRONTEND & set((record.address or record.receiver_address or '').split('.')) else 'codex'


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
    `stay_connected`; nothing else restarts by itself."""
    from .recovery import recover
    recovered = recover(ctx)
    store = ctx.require_store()
    start_raised(ctx, store)  # the person raised these, so they start whether Autostart agents is checked or not
    connected = stay_connected(ctx, store)  # the person's own, whether Autostart agents is checked or not
    started = start_work(ctx, store, recovered)
    due = [one for one in (started.get('retry_due'), connected.pop('retry_due', None)) if one is not None]
    return {**started, **connected, **({'retry_due': min(due)} if due else {})}


MARKERS = {'trouble': 'This part is marked trouble: it does not do its job. Fix it as the note says.',
           'broken': 'This part is marked broken: it does not do its job. Fix it as the note says.',
           'missing': 'This part is marked missing: it should exist and does not. Build it as the note says.'}


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


def start_work(ctx: Context, store: Store, recovered: dict[str, Any]) -> dict[str, Any]:
    """The tickets the agent starter starts and the workers' sessions the supervisor resumes, `autostart`, only while
    Autostart agents is checked."""
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
    # Jev's choice of agent, model and effort for the tickets the person gave no agent, asked before the transaction
    # below, so no network call is ever made inside it; nothing when Jev is off, H23.
    picks = jev_choices(ctx, store)
    from .progress import refresh
    for record in store.work(open=True, limit=0).results:
        refresh(ctx, store, record)
    reserved: list[tuple[WorkRecord, str, str]] = []
    # Counting and reserving are one write transaction on the work store, so two checks at once, the page's and a
    # runner's, never both see the same free slot. Inside it the map's and dispatch's own tables are only read, and
    # nothing here takes their write lock before the work store's; the runners start after it commits.
    with store.atomic():
        kept = ticket_settings(ctx)
        opened = store.work(open=True, limit=0).results
        open_work = [record for record in opened
                     if not kept.get(record.id, {}).get('hold')]
        candidates = [record for record in open_work
                      if not record.taken and ((record.task or '').strip() or record.condition in MARKERS)]
        active = [row for row in sessions(store, open_work=opened) if row['state'] == 'running']
        editing = {row['work_id'] for row in active if editor(row)}  # the person's editor sessions take no slot
        workers = [row for row in active if not summoned(row) and not editor(row)]
        candidates.sort(key=lambda record: (record.held, record.position is None, record.position or 0))
        glyph = {work_id: held.get('glyph') for work_id, held in kept.items()}
        occupied = {glyph.get(row['work_id']) for row in active} - {None}
        busy = {row['work_id'] for row in active}
        taken = [record for record in open_work
                 if record.taken and (record.taken_by or '').startswith('dispatch starting ')]
        # A reservation whose runner never made its session is a start that died: it goes back to the queue, so a
        # crashed start never holds a slot for good.
        stale = [record for record in taken if record.id not in busy
                 and time.time() - _seconds(record.taken) > STALE_START]
        for record in stale:
            store.move_work(record.id, 'backlog' if record.held else 'todo', record.position)
        taken = [record for record in taken if record not in stale]
        occupied.update(glyph.get(record.id) for record in taken)
        # An agent at work always holds its ticket, so the tickets in motion are the agents at work: a runner on its
        # glyph's next ticket, or one too busy to answer a status check, is counted all the same. The tickets the
        # person's summoned chats hold are not workers; the first summoned is the +1, and the rest take slots, as
        # `extra`.
        chatting = {row['work_id'] for row in active if summoned(row)}
        in_motion = {record.id for record in opened if record.taken and not record.done} - chatting - editing
        extra = max(0, sum(1 for row in active if summoned(row)) - 1)  # summoned beyond the first hold worker slots
        capacity = max(0, int(ctx.setting('dispatch_agents')) - extra -
                       len(in_motion | {row['work_id'] for row in workers} | {record.id for record in taken}))
        for record in candidates:
            if capacity == 0:
                break
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
            chosen = preferred(record, kept.get(record.id))  # the ticket's own choice, else by its area
            picked = picks.get(record.id, {}).get('agent')  # else Jev's, when it is sure and the agent eligible
            if picked and not kept.get(record.id, {}).get('agent') and (not agents or picked in agents):
                chosen = picked
            try:
                agent = agent_named(chosen if not agents or chosen in agents else agents[0])
            except Stop:
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
            capacity -= 1
            if mark:
                occupied.add(mark)
    retried = retry(ctx, store, opened)  # the open tickets as read once above
    for record in stale:
        publish(ctx, 'not-smooth', work_id=record.id, key=record.taken_by or '', reason='startup reservation expired')
        publish(ctx, 'requeue', work_id=record.id, key=record.taken_by or '', reason='startup reservation expired')
    started: list[dict[str, Any]] = []
    failed: OSError | None = None
    for record, agent, reservation in reserved:
        try:
            given = {key: value for key, value in picks.get(record.id, {}).items()
                     if key != 'agent' and picks[record.id].get('agent') == agent}
            started.append(run_reserved(context('dispatch', ctx.folder, project=ctx.project,
                                         nouns={'id': record.id, 'agent': agent,
                                                **({'chosen': json.dumps(given)} if given else {})}), reservation))
        except OSError as error:  # its ticket is given back; the others still start
            failed = failed or error
    if failed is not None:
        raise failed
    return {'started': started, 'recovery': recovered, **retried}


# How a session ends that the person ended, or that ended with its work: never retried, P012. A runner ended with
# SIGTERM is counted as stopped, since nothing in Metaform sends it: the person or their system did.
PERSON_ENDS = ('stopped by the person', 'cancelled by the person', 'the ticket is done', 'the runner was terminated')


def retry(ctx: Context, store: Store, opened: Sequence[WorkRecord] | None = None) -> dict[str, Any]:
    """The supervisor, P012: a worker's session that ended without the person's stop, its ticket still open and still
    its own, is resumed in place, so the agent keeps its memory of the work, after RETRY_SECONDS, doubled for
    each retry before it, up to dispatch_retries times; then, or when its agent can neither resume nor load, it is
    handed to the person with a handed-over signal. Never a session the person stopped. Returns the sessions resumed
    and, while one waits, the time the next is due, so the runner that saw its session end can come back for it."""
    from .signals import publish
    limit, wait = int(ctx.setting('dispatch_retries')), float(RETRY_SECONDS)
    rows = sessions(store, verify=False)
    latest = {(row['work_id'], row['session_id']): row for row in rows}
    resumed: list[dict[str, Any]] = []
    due: float | None = None
    for record in opened if opened is not None else store.work(open=True, limit=0).results:
        agent, _, session_id = (record.taken_by or '').partition(' ')
        row = latest.get((record.id, session_id))
        if agent not in agent_choices() or row is None or row['state'] != 'ended' or str(row.get('how') or '') in PERSON_ENDS:
            continue
        if foreign(row):  # another home's session, in a store copied here: that home's to resume, never this one's
            continue
        if rework_blocked(ctx, store, record):
            continue
        with own_store(store).tables() as tx:
            held = tx.get('attempts', {'work_id': record.id})
            if held is not None and held['session_id'] != session_id:  # another session's count is not this one's
                tx.delete('attempts', {'work_id': record.id})
                held = None
            if held is None:
                held = tx.insert('attempts', {'work_id': record.id, 'session_id': session_id, 'retries': 0,
                                              'next_at': time.time() + wait, 'how': row.get('how'),
                                              'seq': time.time_ns()})
        if held['handed']:
            continue
        caps = cast(dict[str, Any], (session_state(store, session_id) or {}).get('capabilities') or {})
        reason = (None if caps.get('resume') or caps.get('load') else 'its agent can neither resume nor load it')
        reason = reason or ('its agent needs a login, which only you can give' if logged_out(store, record.id,
                                                                                            session_id, row) else None)
        reason = reason or (f'it was retried {held["retries"]} times' if held['retries'] >= limit else None)
        if reason is not None:
            with own_store(store).tables() as tx:
                tx.update('attempts', {'work_id': record.id}, {'handed': True})
            publish(ctx, 'handed-over', work_id=record.id, session_id=session_id, key=session_id,
                    reason=f'The session stopped ({row.get("how")}) and {reason}.',
                    next=f'metaform dispatch resume {record.id} session={session_id}')
            continue
        if time.time() < float(held['next_at']):
            due = min(due or float(held['next_at']), float(held['next_at']))
            continue
        if over_budget(ctx, store, work_id=record.id) is not None or runnable_or_none(ctx, agent) is None:
            continue
        retries = int(held['retries']) + 1
        with own_store(store).tables() as tx:
            tx.update('attempts', {'work_id': record.id},
                      {'retries': retries, 'next_at': time.time() + wait * 2 ** retries, 'how': row.get('how')})
        run = run_of(store, session_id)  # the retry spends against the run it goes on, so the run budget holds, M01
        started = resume_spawn(store, record.id, agent,
                               [f'resume={session_id}', 'retry=true', *([f'run={run}'] if run else [])], 'retry')
        resumed.append({'work_id': record.id, 'agent': agent, 'session_id': session_id, 'retry': retries, **started})
    return {'retried': resumed, **({'retry_due': due} if due is not None else {})}


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


def system_sessions(store: Store, work_id: str) -> list[dict[str, Any]]:
    """The person's system agent's sessions on the held ticket it hangs on, oldest first: those about the system, not
    the conversations about a node that hang on the same ticket."""
    about: dict[str, Any] = {}
    found: list[dict[str, Any]] = []
    for row in sessions(store, work_id):
        session_id = str(row['session_id'])
        if session_id not in about:
            about[session_id] = (session_state(store, session_id) or {}).get('about')
        if about[session_id] == 'system':
            found.append(row)
    return found


def stay_connected(ctx: Context, store: Store) -> dict[str, Any]:
    """dispatch_stay_connected, VIEW-045: the person's system agent kept running, run by every pass of the agent
    starter, which runs as the web GUI starts, as a page opens the project and as dispatch's tables change. With none
    running it is started: the person's last conversation with it resumed in place, as Call does, or a new one. One
    that ended without the person's stop is resumed in place after RETRY_SECONDS, doubled for each retry
    before, up to dispatch_retries, counted in `attempts` on its held ticket; then, or at once when its agent needs a
    login, it is handed to the person, who brings it back with Call. One whose agent can neither resume nor load starts
    a new conversation, and the person is told once. It is the one agent the person can always summon, so it takes no
    slot from the agents at work. Returns what it started and, while a retry waits, when it is due."""
    if not ctx.setting('dispatch_stay_connected'):
        return {}
    try:
        held = anchor(ctx, store)
    except Stop:  # a map with no element yet holds no conversation: it starts once there is one
        return {}
    mine = system_sessions(store, held.id)
    own = own_store(store)
    with own.tables(write=False) as tx:
        kept = tx.get('attempts', {'work_id': held.id})
    now = time.time()
    last = mine[-1] if mine else None
    # a runner that outlived the server that started it, or one started to resume it that has not written its row yet,
    # is running whatever a status read says: it is never resumed again or replaced
    if any(row['state'] == 'running' for row in mine) or last is not None and not (last.get('origin') and foreign(last)) \
            and holder(store, held.id, str(last['session_id'])) is not None:
        if kept is not None and (kept['handed'] or now >= float(kept['next_at'])):
            with own.tables() as tx:  # it outlived its wait, or the person brought it back: the count starts again
                tx.delete('attempts', {'work_id': held.id})
        return {}
    from .signals import publish
    if last is not None and not last.get('origin'):
        # recorded before sessions kept their origin: it may be another home's in a copied store, so nothing resumes
        # it by itself; the person is told once that their Call resumes it, which stamps it as this home's
        publish(ctx, 'handed-over', work_id=held.id, session_id=str(last['session_id']), key=str(last['session_id']),
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
            tx.delete('attempts', {'work_id': held.id})
            tx.insert('attempts', {'work_id': held.id, 'session_id': session_id, 'retries': 0, 'next_at': now + wait,
                                   'how': how or None, 'seq': time.time_ns()})
        agent = str(ctx.setting('dispatch_agent'))
        try:
            agent = agent_named(agent)
            again = resumed_conversation(ctx, store, held.id, agent, 'system') \
                if last is not None and ctx.setting('dispatch_resume_chats') else None
            return {'connected': again or converse(ctx, store, held.id, agent, [])}
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
        held_count = tx.get('attempts', {'work_id': held.id})
        if held_count is None or held_count['session_id'] != session_id:
            # a new end: a session the supervisor started fresh goes on with its count, any other starts one
            carried = int(held_count['retries']) if held_count is not None and not held_count['handed'] else 0
            tx.delete('attempts', {'work_id': held.id})
            held_count = tx.insert('attempts', {'work_id': held.id, 'session_id': session_id, 'retries': carried,
                                                'next_at': now + wait * 2 ** carried, 'how': how, 'seq': 0})
        if held_count['handed']:
            return {}
        if now < float(held_count['next_at']):
            return {'retry_due': float(held_count['next_at'])}
        reason = ('its agent needs a login, which only you can give' if logged_out(store, held.id, session_id, last)
                  else f'it was resumed {held_count["retries"]} times' if held_count['retries'] >= limit else None)
        if reason is None:
            retries = int(held_count['retries']) + 1
            tx.update('attempts', {'work_id': held.id}, {'retries': retries, 'next_at': now + wait * 2 ** retries,
                                                         'how': how, 'seq': time.time_ns()})
        else:
            tx.update('attempts', {'work_id': held.id}, {'handed': True})
    if reason is not None:
        publish(ctx, 'handed-over', work_id=held.id, session_id=session_id, key=session_id,
                reason=f'Your system agent stopped ({how}) and {reason}.', next='metaform dispatch system')
        return {}
    try:
        if lost is None:  # resumed in place: it keeps its memory and waits for the person's next message
            started = resume_spawn(store, held.id, agent, [f'resume={session_id}', 'system=true'], 'resume')
            return {'connected': {'state': 'starting', 'work_id': held.id, 'agent': agent, 'session_id': session_id,
                                  'retry': retries, **started, 'conversation': True}}
        started = converse(ctx, store, held.id, agent_named(str(ctx.setting('dispatch_agent'))), [])
    except (Stop, OSError) as error:
        return {'connected': {'state': 'failed', 'error': str(error)}}
    # told once: one signal for the conversation that was lost, keyed by its session
    publish(ctx, 'new-conversation', work_id=held.id, session_id=session_id, key=session_id,
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


def recover(ctx: Context) -> dict[str, Any]:
    from .recovery import recover as recovering
    return recovering(ctx)


def reset(ctx: Context) -> dict[str, Any]:
    """Put the agent bookkeeping back in order after crashes: every ticket taken with no live agent behind it goes back
    to the queue, every session recorded as running whose runner is gone is recorded as ended.
    Live agents and their tickets are left alone; nothing is deleted."""
    store = ctx.require_store()
    own = Store(store.project_id, module='dispatch')
    alive = {row['work_id'] for row in sessions(store) if row['state'] == 'running'}  # verified against the runner
    with own.tables(write=False) as tx:
        recorded = [dict(row) for row in tx.rows('sessions', limit=0).results if row['state'] == 'running']
    ended: list[str] = []
    for row in recorded:
        if row['work_id'] not in alive:
            with own.atomic():
                with own.tables() as tx:
                    latest = tx.get('sessions', {'session_id': row['session_id']})
                    if latest != row:
                        continue
                    tx.update('sessions', {'session_id': row['session_id']},
                              {'state': 'ended', 'how': 'its runner was gone; ended by dispatch reset'})
                from .progress import finish
                finish(own, row['work_id'], str(row.get('runner') or ''), 'its runner was gone; ended by dispatch reset')
            ended.append(row['work_id'])
            from .progress import refresh
            if not intake_id(row['work_id']):
                refresh(ctx, own, ticket(own, row['work_id']))
            from .signals import clear_permissions, publish
            clear_permissions(ctx, row['session_id'])
            publish(ctx, 'not-smooth', work_id=row['work_id'], session_id=row['session_id'],
                    reason='its runner was gone; ended by dispatch reset')
    released: list[str] = []
    for record in store.work(open=True, limit=0).results:
        if record.taken and record.id not in alive:
            store.move_work(record.id, 'backlog' if record.held else 'todo', record.position)
            released.append(record.id)
            from .signals import publish
            publish(ctx, 'requeue', work_id=record.id, key=record.taken_by or '', reason='dispatch reset')
    return {'released': released, 'sessions_ended': ended, 'still_working': sorted(alive)}


def merges(ctx: Context) -> dict[str, Any]:
    """The merges waiting for review, VIEW-044, the soonest first."""
    from .merge import due
    return {'merges': due(ctx.require_store())}


def review(ctx: Context) -> dict[str, Any]:
    """The person takes a waiting merge over: its countdown is cancelled for good, VIEW-044."""
    from .merge import review as taking
    if not taking(ctx.require_store(), str(ctx.nouns['id'])):
        raise Stop(f'No merge of work {ctx.nouns["id"]} is waiting for review.', 'metaform dispatch merges')
    return {'work_id': ctx.nouns['id'], 'state': 'review'}


def merge(ctx: Context) -> dict[str, Any]:
    """Merge a waiting worktree whose review time is up, after both checks pass again, VIEW-044."""
    from .merge import merge_due
    return merge_due(ctx, ctx.require_store(), str(ctx.nouns['id']))


def _running_or_stop(store: Store, work_id: str, session_id: str | None = None) -> dict[str, Any]:
    # Stop and message must still reach older runners and runners finishing a completed ticket, and an intake agent
    # whatever metaform has become active since it began.
    held = (intake_store(store, work_id) or store) if intake_id(work_id) else store
    found = [row for row in sessions(held, work_id, verify=False) if row.get('state') == 'running']
    if session_id:
        # One session of several on a ticket, as editor sessions share theirs, BASE-062: that one, checked live, so a
        # row a killed process left is never taken for it.
        chosen = next((row for row in found if row['session_id'] == session_id), None)
        if chosen is None or session_status(own_store(held), chosen, done=False)['state'] != 'running':
            raise Stop('The chat session is no longer the running session on this ticket.',
                       f'metaform dispatch sessions id={work_id}')
        return chosen
    # The latest session that is running still, BASE-062: a row a killed process left is passed over for a live one
    # before it, as editor sessions share their ticket; one whose pid runs this ticket is reached even unanswering.
    session = next((row for row in reversed(found)
                    if session_status(own_store(held), row, done=False)['state'] == 'running'), None)
    if session is None:
        session = next((row for row in reversed(found) if runner_of(row.get('pid')) == work_id), None)
    if session is None:
        raise Stop(f'No agent is running on work {work_id}.', f'metaform dispatch start {work_id} <agent>')
    return session


def _told(row: dict[str, Any], op: str, **given: Any) -> dict[str, Any]:
    """`tell`, with a session that stopped listening between the read and the request said as a Stop."""
    try:
        return tell(row, op, **given)
    except OSError as error:
        raise Stop(f'Session {row["session_id"]} of work {row["work_id"]} did not answer: {error}.',
                   f'metaform dispatch sessions id={row["work_id"]}') from None


def editor(row: dict[str, Any]) -> bool:
    """A session an editor runs through `dispatch serve`, BASE-062: shown and steered on the page, and never one of
    the agents dispatch counts against `dispatch_agents`, since the person started it in their editor."""
    return runner_of(row.get('pid')) == SERVED


def may_steer(ctx: Context) -> None:
    """An agent whose role the person holds back, a worker and a merge preparation by default, starts, stops, messages
    or steers no agent, BASE-052: it would assign work or override the person's direction of another agent. The page
    is the person's and is never held; the person lifts this with `roles_without_authority`, MAP-050."""
    role = held_role(ctx)
    if role is not None:
        raise Stop(f'A {role} agent starts, stops and messages no agent: that is for the person and the agents that '
                   'serve them. Write what you found in your own ticket\'s note.',
                   'metaform map work op=edit id=<your work id> note="..."')


def sender(ctx: Context) -> str | None:
    """The role of the agent a message comes from, None for the person: on the page always the person, elsewhere the
    role the runner gave the calling agent, BASE-052."""
    return os.environ.get('METAFORM_ROLE') or None if ctx.surface in ('mcp', 'cli') else None


def start(ctx: Context) -> dict[str, Any]:
    """Start the runner for one ticket as a process detached from the terminal, and return at once."""
    may_steer(ctx)
    store = ctx.require_store()
    agent, work_id = agent_named(ctx.nouns['agent']), ctx.nouns['id']
    command = argv(start_command(ctx, agent))
    if shutil.which(command[0]) is None:
        raise Stop(f'{command[0]}, the start command of {agent}, is not found on this system.',
                   f'metaform set --dispatch-{agent} "<command>"')
    folder = store.project().path
    mcp_server(Path(folder))  # a server the runner could not choose is refused here, the ticket left in To do, BASE-052
    budget_stop(ctx, store, str(work_id))  # a reached token budget is the person's to raise, M01
    given, notices = launch_permissions(ctx, store, agent)
    reservation = 'dispatch starting ' + secrets.token_hex(16)
    with store.atomic():
        record = ticket(store, work_id)
        startable(ctx, store, record, agent)
        store.take_work(work_id, by=reservation)
    started = run_reserved(ctx, reservation, given)
    return {**started, **{field: value for field, value in given.items() if value},
            **({'notices': notices} if notices else {})}


def run_reserved(ctx: Context, reservation: str, given: dict[str, str | None] | None = None) -> dict[str, Any]:
    """Start the runner of a ticket reserved for it, as a process detached from the terminal, and return at once; a
    runner that cannot be started gives the ticket back where it waited. `given` is the launch's own permissions; a
    launch without them, autostart's, leaves them to the project's settings."""
    store = ctx.require_store()
    agent, work_id = str(ctx.nouns['agent']), str(ctx.nouns['id'])
    folder = store.project().path
    keep_launch(store, work_id, given or {'prompts': None, 'mode': None})
    log = os.path.join(tempfile.gettempdir(), f'metaform-dispatch-{work_id}.log')
    try:
        with (os.fdopen(os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600), 'ab')
              if home.is_home_path(Path(log)) else open(log, 'ab')) as written:
            process = subprocess.Popen([sys.executable, '-m', 'metaform', 'dispatch', 'run', work_id, agent,
                                        'reservation=' + reservation,
                                        *([f'chosen={ctx.nouns["chosen"]}'] if ctx.nouns.get('chosen') else []),
                                        '--project', store.project_id],
                                       cwd=folder, stdin=subprocess.DEVNULL, stdout=written, stderr=written,
                                       env=child_environment(), **group_options())
    except OSError:
        with store.atomic():
            record = ticket(store, work_id)
            if record.taken_by == reservation:
                store.move_work(work_id, 'backlog' if record.held else 'todo', record.position)
        raise
    return {'state': 'starting', 'work_id': work_id, 'agent': agent, 'pid': process.pid, 'log': log}


def prep(ctx: Context) -> dict[str, Any]:
    """Start an agent in a merge's worktree to prepare its code for the person's review, VIEW-044; it takes no ticket
    and stays to talk with the person until stopped. It is an agent the person summons, VIEW-045."""
    store = ctx.require_store()
    work_id = str(ctx.nouns['id'])
    from .merge import worktree_of
    worktree_of(store, work_id)  # refuses a ticket with no merge
    record = ticket(store, work_id)
    kept = work_reads(ctx.folder, record, project=ctx.project).get('map')  # a done ticket's own, as it shows it
    agent = preferred(record, cast(dict[str, Any], kept) if isinstance(kept, dict) else None)
    if found_command(ctx, agent) is None:
        raise Stop(f'The start command of {agent} is not found on this system.', f'metaform set --dispatch-{agent} "<command>"')
    log = os.path.join(tempfile.gettempdir(), f'metaform-dispatch-prep-{work_id}.log')
    with (os.fdopen(os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600), 'ab')
          if home.is_home_path(Path(log)) else open(log, 'ab')) as written:
        process = subprocess.Popen([sys.executable, '-m', 'metaform', 'dispatch', 'run', work_id, agent, 'prep=true',
                                    '--project', store.project_id],
                                   cwd=store.project().path, stdin=subprocess.DEVNULL, stdout=written, stderr=written,
                                   env=child_environment(), **group_options())
    return {'state': 'starting', 'work_id': work_id, 'agent': agent, 'pid': process.pid, 'log': log}


SYSTEM_TASK = 'Conversation with the system agent'  # the ticket that anchors the person's system agent chat; held, so no agent works it


def anchor(ctx: Context, store: Store, at: str | None = None, task: str = SYSTEM_TASK) -> WorkRecord:
    """The held ticket the person's conversations hang on when what they talk about has no ticket of its own: the system
    agent, a node, an ended agent's thread; with `task`, another held ticket of the person's, such as the one the
    sessions an editor runs through `dispatch serve` hang on, BASE-062. Held, so no agent works it; made at the DE the
    first time."""
    def anchored() -> WorkRecord | None:
        return next((record for record in store.work(open=True, limit=0).results if record.task == task), None)
    found = anchored()
    if found is None:
        roots = store.roots(limit=1)
        root = next((entry.element for entry in roots.entry if entry.element.role == 'DE'), None) \
            or next((entry.element for entry in roots.entry), None) or next(iter(roots.elements), None)
        node = root.address if root is not None else at  # a map with no roles yet: the node talked about holds it
        if node is None:
            raise Stop('Talking with an agent needs a map with one element at least.', 'metaform intake prompt')
        map_work(ctx, op='add', node=node, task=task, title=task,
                 note='Held for the person\'s conversations with agents; no agent works this ticket.', held=True, hold=True)
        found = anchored()
        if found is None:
            raise Stop('The conversation ticket was not made.', 'metaform map work')
    return found


def converse(ctx: Context, store: Store, work_id: str, agent: str, extra: Sequence[str]) -> dict[str, Any]:
    """Start a conversation agent on a ticket without taking it: an agent the person summons, one always and more in the
    slots the agents at work leave free, VIEW-045. It never takes, reopens or closes the ticket, and lasts until the person stops it."""
    if any(word.startswith('talk=') for word in extra):
        prompt_written('talk')
    if found_command(ctx, agent) is None:
        raise Stop(f'The start command of {agent} is not found on this system.', f'metaform set --dispatch-{agent} "<command>"')
    log = os.path.join(tempfile.gettempdir(), f'metaform-dispatch-talk-{work_id}.log')
    with (os.fdopen(os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600), 'ab')
          if home.is_home_path(Path(log)) else open(log, 'ab')) as written:
        process = subprocess.Popen([sys.executable, '-m', 'metaform', 'dispatch', 'run', work_id, agent, 'system=true',
                                    *extra, '--project', store.project_id],
                                   cwd=store.project().path, stdin=subprocess.DEVNULL, stdout=written, stderr=written,
                                   env=child_environment(), **group_options())
    return {'state': 'starting', 'work_id': work_id, 'agent': agent, 'pid': process.pid, 'log': log, 'session_id': None,
            'conversation': True}


def system(ctx: Context) -> dict[str, Any]:
    """Start the person's system agent, the one agent they may summon besides the agents at work: it talks with them
    about anything in the project, from the project's folder, and stays until stopped. A running one is reused. The
    person's Call starts the supervisor's count of its ends again, `stay_connected`."""
    store = ctx.require_store()
    held = anchor(ctx, store)
    forget_ends(store, held.id)
    found = sessions(store, held.id)
    # running as read, or held by a live runner whatever a status read says, such as one that outlived the server
    # that started it: reused, never resumed a second time
    live = next((row for row in found if row['state'] == 'running'), None) or next(
        (row for row in reversed(found) if not (row.get('origin') and foreign(row))
         and holder(store, held.id, str(row['session_id'])) is not None), None)
    if live is not None:
        return {'state': 'running', 'work_id': held.id, 'agent': live['agent'], 'session_id': live['session_id']}
    agent = agent_named(str(ctx.nouns.get('agent') or ctx.setting('dispatch_agent')))
    again = resumed_conversation(ctx, store, held.id, agent, 'system', person=True) \
        if ctx.setting('dispatch_resume_chats') else None
    return again or converse(ctx, store, held.id, agent, [])


def forget_ends(store: Store, work_id: str) -> None:
    """The person acted on their system agent: the supervisor's count of its ends, `attempts`, starts again."""
    own = own_store(store)
    with own.tables(write=False) as tx:  # read first, so a Call with nothing counted writes nothing
        counted = tx.get('attempts', {'work_id': work_id}) is not None
    if counted:
        with own.tables() as tx:
            tx.delete('attempts', {'work_id': work_id})


def disconnect(ctx: Context, store: Store, row: dict[str, Any]) -> bool:
    """The person stops their system agent, as Dismiss in the chat dock does: dispatch_stay_connected is turned off
    for the project until they turn it on again, so it does not come straight back, VIEW-045. Only the person's own
    stop, on the page or the command line: an agent may stop it, but never changes a setting of the person's. Returns
    whether it was turned off, done before the stop so no pass of the agent starter in between brings it back."""
    if ctx.surface == 'mcp' or sender(ctx) is not None or not ctx.setting('dispatch_stay_connected'):
        return False
    if intake_id(row['work_id']) or ticket(store, str(row['work_id'])).task != SYSTEM_TASK or \
            (session_state(store, str(row['session_id'])) or {}).get('about') != 'system':
        return False
    settings.put('dispatch_stay_connected', False, Path(store.project().path))
    forget_ends(store, str(row['work_id']))
    return True


def resumed_conversation(ctx: Context, store: Store, work_id: str, agent: str, about: str, *,
                         person: bool = False) -> dict[str, Any] | None:
    """The person's last conversation about this with this agent, resumed in place so the agent keeps its memory of it;
    None when there is none, or its agent can neither load nor resume it, or its folder is gone, and a new one starts.
    `person` is the person's own Call or talk: it resumes a conversation recorded before sessions kept their origin,
    which nothing automatic does; one stamped by another home is never resumed here."""
    for row in reversed(sessions(store, work_id)):
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
        started = resume_spawn(store, work_id, agent, extra, 'resume')
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
        waiting = {row['work_id'] for row in tx.rows('merges', limit=0).results if row['state'] != 'merged'}
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
    return next((claim for claim in claim_rows(store) if claim['state'] == 'active' and address in claim['nodes']
                 and work_id not in claim['work']), None)


def in_use(store: Store, node: str) -> list[str]:
    """What is using a node: the tickets in motion on it, taken by an agent and not done, and any active work claim
    that reserves it, LAYER-029."""
    using = [record.id for record in store.work(open=True, limit=0).results if record.taken and not record.done
             and node in (record.address, record.receiver_address, record.provider_address)]
    found = claimed(store, node)
    return using + ([f'claim {found["name"]}'] if found else [])


def summon_room(ctx: Context, store: Store) -> int:
    """How many more agents the person may summon now: one is always theirs, and beyond it the agent slots the agents
    at work leave free, up to `dispatch_agents`."""
    opened = store.work(open=True, limit=0).results
    active = [row for row in sessions(store, open_work=opened) if row['state'] == 'running']
    called = [row for row in active if summoned(row)]
    editing = {row['work_id'] for row in active if editor(row)}  # the person's editor sessions take no slot
    chatting = {row['work_id'] for row in called} | editing
    made = {row['work_id'] for row in sessions(store)}  # a launch holds its slot until its session is made
    with Store(store.project_id, module='dispatch').tables(write=False) as tx:
        launching = [row for row in tx.rows('raised', by=('seq',), limit=0).results if row['started'] is not None
                     and row['work_id'] not in made and time.time() - row['started'] < STALE_START]
    working = ({record.id for record in opened if record.taken and not record.done} - chatting) | {
        row['work_id'] for row in active if not summoned(row) and not editor(row)}
    free = max(0, int(ctx.setting('dispatch_agents')) - len(working))
    return max(0, 1 + free - len(called) - len(launching))


def start_raised(ctx: Context, store: Store) -> list[str]:
    """Start the sentinel of each queued issue whose node is no longer in use, oldest first, while there is room to
    summon an agent, VIEW-045."""
    own = Store(store.project_id, module='dispatch')
    with own.tables(write=False) as tx:  # read first: a pass with nothing queued writes nothing, so it never makes a
        held = [dict(row) for row in tx.rows('raised', by=('seq',), limit=0).results]  # cleared project's base again
    if not held:
        return []
    made = {row['work_id'] for row in sessions(store)}
    done = [row['work_id'] for row in held if row['started'] is not None
            and (row['work_id'] in made or time.time() - row['started'] >= STALE_START)]
    if done:  # a launch whose session is made, or that never made one, is done waiting
        with own.tables() as tx:
            for work_id in done:
                tx.delete('raised', {'work_id': work_id})
    waiting = [row for row in held if row['started'] is None]
    started: list[str] = []
    for row in waiting:
        if summon_room(ctx, store) <= 0:
            break
        if in_use(store, row['node']):
            continue
        launch(ctx, store, row['work_id'], row['node'], row['agent'])
        started.append(row['work_id'])
    return started


def launch(ctx: Context, store: Store, work_id: str, node: str, agent: str) -> dict[str, Any]:
    """Start an issue's sentinel, holding its slot in `raised` until its session is made."""
    with Store(store.project_id, module='dispatch').tables() as tx:
        tx.delete('raised', {'work_id': work_id})
        tx.insert('raised', {'work_id': work_id, 'node': node, 'agent': agent, 'started': time.time(),
                             'seq': time.time_ns()})
    return converse(ctx, store, work_id, agent, [f'sentinel={node}'])


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
    kept; no worker takes it. An issue on a node other work is using, or raised when every agent slot is taken,
    waits; its sentinel starts when the work is complete and a slot is free."""
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
    if busy or summon_room(ctx, store) <= 0:
        with Store(store.project_id, module='dispatch').tables() as tx:
            tx.insert('raised', {'work_id': work_id, 'node': node, 'agent': agent, 'seq': time.time_ns()})
        return {'state': 'queued', 'work_id': work_id, 'node': node,
                'waiting_on': busy or 'a free agent slot', 'conversation': True}
    return launch(ctx, store, work_id, node, agent)


def talk(ctx: Context) -> dict[str, Any]:
    """Talk with an agent about anything the person clicks, VIEW-042: a ticket, open or done, a node, or an ended
    agent's session. An agent at work on it is talked to directly; otherwise a conversation agent starts, told
    what it is about. One summoned agent is always the person's; more use the agent slots left free, and past them
    a chat is refused until a slot frees."""
    store = ctx.require_store()
    given = {key: str(ctx.nouns[key]) for key in ('id', 'node', 'session') if ctx.nouns.get(key)}
    if len(given) != 1:
        raise Stop('Talk names one thing: id=<work id>, node=<address>, question=<message id> or '
                   'session=<work id>:<session id>.', 'metaform help dispatch talk')
    (kind, ref), = given.items()
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
        work_id, about = anchor(ctx, store, ref).id, f'node:{ref}'
    if kind in ('id', 'session'):  # an agent at work on it is talked to directly, never restarted
        working = next((row for row in reversed(running) if row['work_id'] == work_id and not summoned(row)), None)
        if working is not None and (kind != 'session' or working['session_id'] == ref.partition(':')[2]):
            return {key: working[key] for key in ('work_id', 'agent', 'session_id', 'state')}
    talking = next((row for row in running if summoned(row) and row['work_id'] == work_id
                    and f'talk={about}' in command_line(row['pid'])), None)
    if talking is not None:  # the chat about this is already open: it is reused
        return {key: talking[key] for key in ('work_id', 'agent', 'session_id', 'state')}
    if summon_room(ctx, store) <= 0:
        raise Stop(f'Every agent slot is in use: {ctx.setting("dispatch_agents")} besides the one you can always '
                   'summon. A chat opens when an agent finishes or one is stopped.', 'metaform dispatch sessions')
    agent = agent_for(ctx, ticket(store, work_id), ctx.nouns.get('agent'))
    again = resumed_conversation(ctx, store, work_id, agent, about, person=True) \
        if ctx.setting('dispatch_resume_chats') else None
    return again or converse(ctx, store, work_id, agent, [f'talk={about}'])


async def run(ctx: Context) -> dict[str, Any]:
    from .runner import dispatch
    return await dispatch(ctx)


def message(ctx: Context) -> dict[str, Any]:
    """Carry a person's message to the agent working a ticket, as session/prompt; one an agent sends carries its role,
    so its thread never shows it as the person's, BASE-052."""
    may_steer(ctx)
    store = ctx.require_store()
    given: Any = ctx.nouns['text']
    words = [str(word) for word in cast(list[Any], given)] if isinstance(given, (list, tuple)) else [str(given)]
    text = ' '.join(words)
    given_by: dict[str, Any] = {'by': role} if (role := sender(ctx)) else {}
    if ctx.nouns.get('audio'):  # the person's recording, sent beside its transcript where the agent takes audio
        audio = Path(str(ctx.nouns['audio'])).expanduser().resolve()
        if given_by or audio.parent != (home.home() / 'run' / 'voice' / 'clips').resolve() or not audio.is_file():
            raise Stop('A recording goes with a person\'s own message, as a clip the web GUI kept.',
                       f'metaform dispatch message {ctx.nouns["id"]} -- "<text>"')
        given_by['audio'] = str(audio)
    if ctx.nouns.get('image'):  # a frame the person sent, beside their words where the agent takes images
        image = Path(str(ctx.nouns['image'])).expanduser().resolve()
        if role or image.parent != (home.home() / 'run' / 'captures').resolve() or not image.is_file():
            raise Stop('A frame goes with a person\'s own message, as one the web GUI kept.',
                       f'metaform dispatch message {ctx.nouns["id"]} -- "<text>"')
        given_by['image'] = str(image)
    return _told(_running_or_stop(store, ctx.nouns['id'], ctx.nouns.get('session')), 'message', text=text, **given_by)


def fork(ctx: Context) -> dict[str, Any]:
    """Fork a running agent's session with ACP's session/fork, where its agent offers it, P030: a side conversation
    that starts with everything the session knows, given the same Metaform server and identity, kept as a child thread
    of the session; with text, that is its first turn, and a later message to it names it with fork=<id>."""
    may_steer(ctx)
    store = ctx.require_store()
    given: Any = ctx.nouns.get('text') or []
    text = ' '.join(str(word) for word in cast(list[Any], given)) if isinstance(given, (list, tuple)) else str(given)
    row = _running_or_stop(store, ctx.nouns['id'], ctx.nouns.get('session'))
    if ctx.nouns.get('fork'):
        return _told(row, 'message', text=text, fork=str(ctx.nouns['fork']))
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
    given_by: dict[str, Any] = {'by': role} if (role := sender(ctx)) else {}
    caller = os.environ.get('METAFORM_SESSION') if given_by else None  # an agent's broadcast does not tell itself
    running = [row for row in sessions(store) if row['state'] == 'running'
               and not (caller and row.get('runner') == caller)]
    system = {str(row['session_id']) for row in running
              if (session_state(store, str(row['session_id'])) or {}).get('about') == 'system'}
    told = [row for row in running if ctx.nouns.get('system') is True or str(row['session_id']) not in system]
    if not told:
        raise Stop('No agent is working on this project.' if not running else
                   'Only your chat agent is working on this project; broadcast with system=true to tell it.',
                   'metaform dispatch sessions thread=false')
    sent_id = secrets.token_hex(8)

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
            rows: Sequence[dict[str, Any]] = tx.rows('lines', {'session_id': BROADCASTS}, by=('session_id', 'seq'),
                                                     limit=0).results
    except StoreError:
        rows = ()
    found = [json.loads(str(row['text'])) for row in reversed(rows) if row['kind'] == 'broadcast']
    limit = ctx.nouns.get('limit')
    return {'broadcasts': found[:limit] if isinstance(limit, int) and limit > 0 else found}


TIMER_MOST = 86400  # seconds an agent's timer may run, a day


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
    result = _told(row, 'interrupt')
    if result.get('error'):
        raise Stop(str(result['error']), f'metaform dispatch stop {ctx.nouns["id"]}')
    return result


def stop(ctx: Context) -> dict[str, Any]:
    """Stop the agent working a ticket: session/cancel, then its process group ends. The person stopping their system
    agent turns dispatch_stay_connected off for the project, `disconnect`, and the result says so."""
    may_steer(ctx)
    store = ctx.require_store()
    row = _running_or_stop(store, ctx.nouns['id'], ctx.nouns.get('session'))
    off = disconnect(ctx, store, row)
    result = _told(row, 'stop')
    if result.get('error'):  # a session that ends elsewhere, such as in the person's editor, BASE-062
        if off:  # it still runs, so it stays connected
            settings.put('dispatch_stay_connected', True, Path(store.project().path))
        raise Stop(str(result['error']), f'metaform dispatch sessions id={ctx.nouns["id"]}')
    return {**result, 'stay_connected': False} if off else result


# What `wait` waits for: a ticket done; its agent stopped with it open, idle at a turn's end or its session ended; or
# any signal on it, BASE-057. A ticket's stopped is a signal of its latest session, so one an earlier session left
# does not wake a wait on the agent at work now.
UNTIL = ('done', 'stopped', 'signal')
STOPPED = ('stopped-open', 'not-smooth')
STAMP = '%Y-%m-%dT%H:%M:%SZ'  # the form of a ticket's done time and a signal's time, compared as text


def ended(record: WorkRecord) -> str:
    """How a closed ticket reads to a wait: done when it was completed, or its outcome, cancelled or failed, P232."""
    return 'done' if (record.outcome or 'completed') == 'completed' else str(record.outcome)


def awaited(store: Store, until: str, work_id: str | None, since: str | None) -> list[dict[str, Any]]:
    """The tickets that meet `until`, each with the time it met it, oldest first. With a work id, that ticket as it
    is now, and a done one ends any wait since nothing comes after it; with none, every ticket of the project that met
    it at or after `since`."""
    from .signals import rows
    if until == 'done':
        records = [ticket(store, work_id)] if work_id else store.work(open=False, limit=0).results
        return sorted(({'work_id': record.id, 'state': ended(record), 'at': record.done,
                        **ticket_work_status(record, (), ())} for record in records
                       if record.done and (work_id or record.done >= str(since))), key=lambda found: found['at'])
    if work_id:
        record = ticket(store, work_id)
        if record.done:
            return [{'work_id': record.id, 'state': ended(record), 'at': record.done,
                     **ticket_work_status(record, (), ())}]
        open_ids = {record.id}
    else:
        open_ids = {record.id for record in store.work(open=True, limit=0).results}
    latest = {row['work_id']: row['session_id'] for row in sessions(store, work_id, verify=False)}
    held: dict[str, list[dict[str, Any]]] = {}
    for row in rows(store, work_id):
        if row.get('work_id') not in open_ids or (since and row['at'] < since):
            continue
        if until == 'stopped' and (row['signal'] not in STOPPED
                                   or (row.get('session_id') or '') != latest.get(row['work_id'], '')):
            continue
        held.setdefault(row['work_id'], []).append(row)
    return sorted(({'work_id': found, 'state': until, 'at': signals[-1]['at'], 'signals': signals,
                    **ticket_work_status(ticket(store, found), sessions(store, found), rows(store, found))}
                   for found, signals in held.items()), key=lambda found: found['at'])


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

    def told(payload: dict[str, Any]) -> None:
        # the thread lines a runner streams change no ticket and no signal, so they wake nothing; a wait on one ticket
        # wakes only for a change that names it, or does not say which tickets it concerns
        named: Any = payload.get('work_ids')
        if payload.get('project') != store.project_id or payload.get('tables') == 'dispatch' \
                and payload.get('dispatch_tables') == ['dispatch.lines'] and 'signal' not in payload \
                or work_id and isinstance(named, list) and work_id not in named:
            return
        loop.call_soon_threadsafe(heard.set)
    limit = float(ctx.setting('dispatch_wait_seconds'))
    deadline = loop.time() + limit
    with ctx.listen(told):
        while True:
            heard.clear()  # before the read, so a change during it wakes the wait again
            read = time.strftime(STAMP, time.gmtime())
            woke = await asyncio.to_thread(awaited, store, until, work_id, since)
            if woke:
                closed = work_id is not None and woke[0]['state'] in ('done', 'cancelled', 'failed')
                return {'state': woke[0]['state'], 'until': until, 'work_id': woke[0]['work_id'], 'woke': woke,
                        'since': since, 'next': None if closed else waiting_call(until, work_id, read)}
            try:
                await asyncio.wait_for(heard.wait(), max(deadline - loop.time(), 0))
            except TimeoutError:
                break
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
    node = str(read.get('address') or ' and '.join(
        f'{name}={value}' for name, value in (('receiver', read.get('receiver_address')),
                                              ('provider', read.get('provider_address'))) if value))
    return f"{work_line(work_id, ctx.folder, node)}\n\n" + '\n'.join(lines) + '\n', links


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


SUBAGENTS_READ = 50  # the most of a running session's subagents the agents key reads, for their figures
ENDED_STATE = ('about', 'intake')  # what the agents key keeps of an ended session's state: its conversation, intake


def read_sessions(ctx: Context) -> dict[str, Any]:
    """The sessions of one ticket or of every ticket, each with the lines of its thread in order, for the page's agent
    window and a node's work history, VIEW-036 and VIEW-039; with thread=false, the sessions alone, for the agents key.
    Each session's state is under `states` by its session id, so a session row reads the same on every surface, and
    a tool call's or a permission request's line carries its structure as `data`. What only reaches a running session
    is left out. An intake agent's session is found in whatever metaform it is kept in."""
    store = ctx.require_store()
    work_id = ctx.nouns.get('id') or None
    if work_id and intake_id(work_id):
        store = intake_store(store, str(work_id)) or store
    found = sessions(store, work_id)
    lines: list[dict[str, Any]] = []
    states: dict[str, dict[str, Any]] = {}
    since = ctx.nouns.get('since')
    try:
        with store.tables(write=False) as tx:
            for session in found:
                if ctx.nouns.get('thread') is not False and since is not None:
                    # Only the lines begun after `since`, one range of the (session_id, seq) index read from the
                    # cursor at that seq, for a caller that polls a thread; a line grown in place keeps the seq it
                    # began with. Its state line is read too, so `states` stays whole.
                    lines += [dict(row) for row in tx.rows('lines', {'session_id': session['session_id']},
                                                           by=('session_id', 'seq'), limit=0,
                                                           after=json.dumps([int(since), ''])).results
                              if int(row['seq']) > int(since)]
                    lines += [dict(row) for row in tx.rows('lines', {'session_id': session['session_id'],
                                                                     'name': 'state'}, limit=1).results]
                elif ctx.nouns.get('thread') is not False:
                    lines += [dict(row) for row in tx.rows('lines', {'session_id': session['session_id']},
                                                           by=('session_id', 'seq'), limit=0).results]
                else:
                    lines += [dict(row) for row in tx.rows('lines', {'session_id': session['session_id'],
                                                                     'name': 'state'}, limit=1).results]
                    if session.get('state') == 'running':  # its subagents' lines, for their figures, VIEW-035
                        lines += [dict(row) for row in tx.rows('lines', {'session_id': session['session_id']},
                                                               after=json.dumps(['subagent:']),
                                                               limit=SUBAGENTS_READ).results
                                  if str(row['name']).startswith('subagent:')]
    except StoreError:
        pass
    lines, states = threaded(lines)
    if ctx.nouns.get('thread') is False and not work_id:
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
                with store.tables(write=False) as tx:
                    own_lines = [dict(row) for row in tx.rows('lines', {'session_id': child.get('session_id')},
                                                              by=('session_id', 'seq'), limit=0).results]
            except StoreError:
                pass
        children.append({**child, 'parent': line['session_id'], 'lines': threaded(own_lines)[0]})
    if ctx.nouns.get('thread') is False:
        lines = []
    from .signals import rows
    raised = rows(store, work_id)
    return {'sessions': [{**{key: value for key, value in session.items() if key not in PRIVATE},
                          **session_work_status(session, [one for one in raised
                                                          if one.get('work_id') == session['work_id']])}
                         for session in found],
            'lines': lines, 'signals': raised, 'states': states, 'subagents': children}


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
    result: dict[str, Any] = {'agents': found, 'default': default, 'frontend': sorted(FRONTEND)}
    if ctx.store is not None:
        result['room'] = summon_room(ctx, ctx.store)
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
                    'next': f'metaform set --dispatch-{agent} "{listed}"' if listed and listed != current else None})
    agents: list[dict[str, Any]] = []
    for agent_id, entry in sorted(found.items()):
        chosen = agent_registry.way(entry)
        agents.append({'agent': agent_id, 'name': entry.get('name'), 'version': entry.get('version'),
                       'ways': sorted(cast(dict[str, Any], entry.get('distribution') or {})),
                       'runs_here': chosen[0] if chosen else None, 'pinned': pins.get(agent_id)})
    return {'registry': url, 'read': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(float(read['fetched']))),
            **({'stale': read.get('error')} if read.get('stale') else {}), 'platform': agent_registry.platform(),
            'own': own, 'agents': agents, **({'changed': changed} if changed else {})}


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
    it is not offered to agents over MCP, and nothing approves beyond dispatch_prompts."""
    may_steer(ctx)
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
    it from its next step. Only the person sets it: it is not offered to agents over MCP."""
    may_steer(ctx)
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


def spawn(store: Store, work_id: str, agent: str, extra: list[str], name: str, *, kept: bool = False) -> dict[str, Any]:
    """A runner started detached from the terminal in the project's folder, its output in the log named for it;
    `kept` for a launch whose caller waits on it, `launched`, which hears the runner exit."""
    log = os.path.join(tempfile.gettempdir(), f'metaform-dispatch-{name}-{work_id}.log')
    with (os.fdopen(os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600), 'ab')
          if home.is_home_path(Path(log)) else open(log, 'ab')) as written:
        process = subprocess.Popen([sys.executable, '-m', 'metaform', 'dispatch', 'run', work_id, agent, *extra,
                                    '--project', store.project_id],
                                   cwd=store.project().path, stdin=subprocess.DEVNULL, stdout=written, stderr=written,
                                   env=child_environment(), **group_options())
    if kept:
        RUNNERS[process.pid] = process
    return {'pid': process.pid, 'log': log}


RUNNERS: dict[int, subprocess.Popen[Any]] = {}  # the runners started for a wait, `launched`, by pid


def resume(ctx: Context) -> dict[str, Any]:
    """Resume an ended agent session in place, with the agent's own memory of it, where its agent can load or resume
    a session: its thread goes on where it ended. A worker whose ticket is still its own goes on as that ticket's
    worker; any other session comes back as a conversation the person summoned. It waits for the person's next
    message. An agent that can do neither is refused, with a fresh agent that reads the thread as the next step."""
    may_steer(ctx)
    store = ctx.require_store()
    work_id = str(ctx.nouns['id'])
    held = (intake_store(store, work_id) or store) if intake_id(work_id) else store
    found = sessions(held, work_id)
    wanted = ctx.nouns.get('session')
    row = next((one for one in reversed(found) if one['session_id'] == wanted), None) if wanted else \
        (found[-1] if found else None)
    if row is None:
        raise Stop(f'No agent session {wanted} on work {work_id}.' if wanted else f'No agent session on work {work_id}.',
                   f'metaform dispatch sessions id={work_id} thread=false')
    session_id, agent = str(row['session_id']), agent_named(str(row['agent']))
    said = {'work_id': work_id, 'agent': agent, 'session_id': session_id}
    if row['state'] == 'running':  # it is there already: talked to as it is
        return {**said, 'state': 'running'}
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
    record = None if intake_id(work_id) else ticket(store, work_id)
    worker = record is not None and not record.done and record.taken_by == f'{agent} {session_id}'
    if worker and running(store, work_id) is not None:
        raise Stop(f'Another agent is at work on work {work_id}.', f'metaform dispatch sessions id={work_id}')
    if not worker and summon_room(ctx, store) <= 0:
        raise Stop(f'Every agent slot is in use: {ctx.setting("dispatch_agents")} besides the one you can always '
                   'summon. A session resumes when an agent finishes or one is stopped.', 'metaform dispatch sessions')
    started = resume_spawn(held, work_id, agent, [f'resume={session_id}', *([] if worker else ['system=true'])], 'resume')
    return {**said, 'state': 'starting', **started, 'conversation': not worker}


def intake(ctx: Context) -> dict[str, Any]:
    """Start an agent on this project's intake, VIEW-045 and BASE-039: its first turn is the intake as `intake prompt`
    serves it, with what the person asked for filled in, and it works in the project's folder with Metaform's MCP
    server, recording the map as it reasons it, so an open page follows it. It takes no ticket and counts against the
    agent slots as a summoned agent does, staying to talk until the person stops it. One intake runs at a time."""
    store = ctx.require_store()
    agent = agent_named(str(ctx.nouns.get('agent') or ctx.setting('dispatch_agent')))
    runnable(ctx, agent)
    if not any(module.id == 'intake' for module in surface(ctx.folder)):
        raise Stop('The intake module is not active; it serves the intake the agent follows.', 'metaform enable intake')
    for base in sorted(home.bases(store.project_id), key=lambda base: not base.active):
        for row in sessions(Store(store.project_id, base=base.id, module='dispatch')):
            if intake_id(row['work_id']) and row['state'] == 'running':
                raise Stop(f'An intake agent is already at work in this project: {row["agent"]}, session '
                           f'{row["session_id"]}.', f'metaform dispatch stop {row["work_id"]}')
    building = store.intake_building().results
    if building and building[0].recording:
        held = building[0]
        raise Stop(f'An agent Metaform did not start is recording the intake in layer {held.layer.name} of metaform '
                   f'{held.base} now; two agents would interleave their records in it.', 'metaform intake status')
    if building and not ctx.nouns.get('resume'):
        held = building[0]
        raise Stop(f'An intake was left unfinished in layer {held.layer.name} of metaform {held.base}, with '
                   f'{held.parts} parts; no agent is recording it. Start the intake agent with resume=true and it '
                   'resumes that intake.', 'metaform dispatch intake resume=true')
    if summon_room(ctx, store) <= 0:
        raise Stop(f'Every agent slot is in use: {ctx.setting("dispatch_agents")} besides the one you can always '
                   'summon. An intake starts when an agent finishes or one is stopped.', 'metaform dispatch sessions')
    given: Any = ctx.nouns.get('text') or []
    words = ' '.join(str(word) for word in cast(list[Any], given)) if isinstance(given, (list, tuple)) else str(given)
    work_id = INTAKE + secrets.token_hex(16)
    # The launch holds its slot until its session is made, as a sentinel's does. The check for another intake
    # starting and the reservation are one write, so two starts at once cannot both pass. The person's words reach the
    # runner in the launch's own row, never in an argument; the runner takes them before its session is made, while
    # the row still holds its slot.
    made = {row['work_id'] for row in sessions(store)}
    with Store(store.project_id, module='dispatch').tables() as tx:
        if any(intake_id(row['work_id']) and row['started'] is not None and row['work_id'] not in made
               and time.time() - row['started'] < STALE_START for row in tx.rows('raised', limit=0).results):
            raise Stop('An intake agent is starting in this project.', 'metaform dispatch sessions thread=false')
        tx.insert('raised', {'work_id': work_id, 'node': '', 'agent': agent, 'started': time.time(),
                             'seq': time.time_ns(), 'asked': words.strip() or None})
    started = spawn(store, work_id, agent, ['system=true', 'intake=true'], 'intake', kept=bool(ctx.nouns.get('wait')))
    said = {'state': 'starting', 'work_id': work_id, 'agent': agent, **started, 'session_id': None,
            'conversation': True, 'intake': True}
    return {**said, **launched(store, work_id, started['pid'])} if ctx.nouns.get('wait') else said


def launched(store: Store, work_id: str, pid: int) -> dict[str, Any]:
    """How a launch came out: running with its session once the agent made one, or failed with why, read from the
    session row its runner writes either way. The rows are read again only when the runner says it wrote one for this
    ticket, its `map.changed` heard through the base's listener, BASE-053, or when it exits; nothing polls. The
    runner's own start limit bounds the wait; a runner that ends without a row failed too."""
    from .runner import START_LIMIT
    heard = threading.Event()

    def told(payload: dict[str, Any]) -> None:
        named: Any = payload.get('work_ids')
        if not isinstance(named, list) or work_id in named:
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
    the value dispatch_<agent>_<option> gives each, its auth methods and its extensions. An agent that has not run has
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
    if (ctx.surface == 'mcp' or os.environ.get('METAFORM_ROLE') not in (None, '', 'none')) \
            and not settings.value('agents_may_set_control', ctx.folder):
        raise Stop(f'{what} is the person\'s decision, made on the command line or the page, never an agent\'s. Say '
                   'what you need in your ticket\'s note.', 'metaform map work op=edit id=<your work id> note="..."')


def offered_values(store: Store, agent: str, key: str) -> list[str] | None:
    """The values an agent offered for one of its settings at its last session, by ACP category or id; None when it
    has not run in this project, so nothing can be checked."""
    row = catalog_rows(store).get(agent)
    if row is None:
        return None
    for setting in cast(list[dict[str, Any]], row.get('settings') or []):
        if option_key(setting) == key:
            return option_values(setting)
    return []


def tune(ctx: Context) -> dict[str, Any]:
    """A ticket's own model and effort, P015, kept in this module's tables and applied over dispatch_<agent>_<option>
    to every session of the ticket; a running one takes them at once through session/set_config_option. The person's
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
        ctx, record, preferred(record, ticket_settings(ctx).get(record.id)))
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
            raise Stop(f'{agent_label(agent)} offers {field} {", ".join(offered) or "none"} at its last session here, '
                       f'not {said}.', f'metaform dispatch options agent={agent}')
    with own_store(store).tables() as tx:
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
    return project is not None and any(row['state'] == 'running'
                                       for row in sessions(Store(project), verify=False))


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


MODULE = Module(
    id='dispatch',
    summary='Start an agent on a ticket through ACP, follow it, message it and stop it.',
    purpose='Starts Claude Code, Codex or Gemini CLI on one ticket through the Agent Client Protocol, one session per '
            "ticket, in the project's folder with Metaform's MCP server. What the agent does shows as notes at the "
            "ticket's own window, and each permission it asks for is a question at the ticket's node. Details: metaform "
            'help dispatch.',
    details='Each agent runs your own installed command under your own login: --dispatch-claude, --dispatch-codex and '
            '--dispatch-gemini set them. Metaform never reads or stores credentials.',
    verbs=(
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
                                     'Autostart agents checked. Held tickets are left out, and at most dispatch_agents '
                                     'run at once.',
             switches=('dispatch_autostart', 'dispatch_agent', 'dispatch_agents', 'dispatch_recovery',
                       'dispatch_rework_limit'), open_world=True),
        Verb('recover', recover, 'Return the tickets of dead agent runners to the queue, while the dispatch_recovery '
                                 'setting is automatic. Cleanup it cannot be sure of leaves the work taken.',
             switches=('dispatch_recovery',), open_world=True),
        Verb('start', start, 'Start an agent on a ticket; it returns at once, and the map shows the agent at work. On '
                             "a ticket with an agent glyph, the agent then works the glyph's other tickets in turn.",
             nouns=(Noun('id', 'The work id of the ticket.'), Noun('agent', 'claude, codex or gemini.'),
                    Noun('prompts', 'For this launch only, how its permission prompts are answered: approve-all, '
                                    'approve-reads or ask_all; dispatch_prompts when none is given. The person\'s own.',
                         required=False),
                    Noun('mode', 'For this launch only, the agent\'s own mode, a value dispatch options lists for it; '
                                 'dispatch_<agent>_<option> when none is given. The person\'s own.', required=False)),
             switches=('dispatch_claude', 'dispatch_codex', 'dispatch_gemini'),
             examples=(('metaform dispatch start 198452e1... claude', 'Starts Claude Code on the ticket.'),
                       ('metaform dispatch start 198452e1... claude prompts=approve-reads mode=acceptEdits',
                        'Starts it allowing reads and its own edits without asking, for this launch only.')),
             open_world=True),
        Verb('reset', reset, 'Put agent bookkeeping back in order after a crash, returning tickets no live agent holds '
                             'to the queue. Dead sessions are recorded as ended; live agents are left alone.',
             examples=(('metaform dispatch reset', 'Release every ticket a dead agent still holds.'),)),
        Verb('merges', merges, "List the agents' merges waiting for the person's review, the soonest first.",
             switches=('dispatch_worktrees', 'dispatch_test_command', 'dispatch_review_minutes'), effect='read'),
        Verb('review', review, "Hold a waiting merge for the person's review, cancelling its automatic merge for good.",
             nouns=(Noun('id', 'The work id of the ticket whose merge waits.'),), listed=merge_waits),
        Verb('merge', merge, 'Merge a waiting worktree whose review time is up, after its checks pass again.',
             nouns=(Noun('id', 'The work id of the ticket whose merge waits.'),), surfaces=('cli',)),
        Verb('system', system, "Start the person's system agent, who talks with them about anything in the project, or "
                               'reuse the running one.',
             nouns=(Noun('agent', 'claude, codex or gemini; the default agent, dispatch_agent, when none is given.',
                         required=False),), open_world=True),
        Verb('agents', harnesses, 'List the agents dispatch can start, the default among them, and how many more may '
                                  'be summoned now. Each comes with its name, its start command, and whether that '
                                  'command is found on this system.',
             switches=('dispatch_agent', 'dispatch_claude', 'dispatch_codex', 'dispatch_gemini'),
             examples=(('metaform dispatch agents', 'Lists Claude Code, Codex and Gemini CLI with what each needs.'),
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
             nouns=(Noun('agent', 'claude, codex or gemini; the default agent, dispatch_agent, when none is given.',
                         required=False),
                    Noun('resume', 'true: start it although an intake is being recorded that no agent of Metaform\'s '
                                   'started, to resume that intake once no agent is still recording it.',
                         kind='bool', required=False),
                    Noun('wait', 'true: answer once the agent has made its session, state running, or with why it '
                                 'did not start, state failed; the agent\'s own start limit bounds the wait.',
                         kind='bool', required=False),
                    Noun('text', 'What the intake is for, a target or a request, as `intake prompt` takes it; '
                                 'nothing means this project.', required=False, many=True)),
             switches=('dispatch_agent', 'dispatch_claude', 'dispatch_codex', 'dispatch_gemini'),
             examples=(('metaform dispatch intake agent=claude', 'Starts Claude Code on the intake of this project.'),
                       ('metaform dispatch intake -- "src/engine only"',
                        'Starts the default agent on an intake of what is asked.')), open_world=True),
        Verb('resume', resume, 'Resume an ended agent session in place, so the agent keeps its memory and its thread '
                               'goes on. It works where the agent can load or resume a session, and waits for your '
                               'next message.',
             nouns=(Noun('id', 'The work id of the session\'s ticket, or an intake agent\'s work id.'),
                    Noun('session', 'The session id; the latest session of the ticket when none is given.',
                         required=False)),
             examples=(('metaform dispatch resume 198452e1... session=4f2c...', 'Resumes that session.'),), open_world=True),
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
                    Noun('agent', 'claude, codex or gemini; the configured agent by default.', required=False),
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
                    Noun('session', 'An agent session, as <work id>:<session id>.', required=False),
                    Noun('agent', 'claude, codex or gemini.', required=False)), open_world=True),
        Verb('prep', prep, "Start an agent in a merge's worktree to prepare its code for the person's review.",
             nouns=(Noun('id', 'The work id of the ticket whose merge is under review.'),), open_world=True,
             listed=merge_waits),
        Verb('run', run, 'Run one ticket\'s ACP session in this process until it ends. start runs it detached.',
             nouns=(Noun('id', 'The work id of the ticket.'), Noun('agent', 'claude, codex or gemini.'),
                    Noun('prep', 'true: help the person prepare a merge under review, in its worktree, VIEW-044.',
                         kind='bool', required=False),
                    Noun('system', 'true: the person\'s system agent, a conversation with no ticket work.',
                         kind='bool', required=False),
                    Noun('talk', 'What a conversation agent talks about: ticket:<id>, node:<address> or '
                                 'thread:<session id>.', required=False),
                    Noun('sentinel', 'The address of the node the person raised an issue on; the ticket holds the '
                                     'report, and the sentinel prompt is served.', required=False),
                    Noun('reservation', 'The startup reservation made by start.', required=False),
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
             switches=('dispatch_claude', 'dispatch_codex', 'dispatch_gemini'), surfaces=('cli',), open_world=True),
        Verb('message', message, 'Send a person\'s message to the agent working a ticket.',
             nouns=(Noun('id', 'The work id of the ticket.'),
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
                           'where its agent offers session/fork; its thread is a child of the session\'s.',
             nouns=(Noun('id', 'The work id of the ticket.'),
                    Noun('session', 'The session id, for one of several on the ticket; the latest when none is given.',
                         required=False),
                    Noun('fork', 'A fork already made, to send it the text as its next turn.', required=False),
                    Noun('text', 'The fork\'s first turn, or its next with fork=<id>.', required=False, many=True)),
             examples=(('metaform dispatch fork 198452e1... -- "What else did you consider?"',
                        'Asks a fork of the session, leaving the session itself at its work.'),), open_world=True,
                        listed=session_live),
        Verb('broadcast', broadcast, "Send a person's message to every agent running on the project at once, and keep "
                                     'it with whom it reached.',
             nouns=(Noun('system', "true: tell the person's own system agent too; it is left out otherwise.",
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
        Verb('note', note, 'Send a short note to the agents working other open tickets, by ticket, part of the map, file '
                           'or topic: information each reads at its next turn, kept on every ticket it touches; it never '
                           'steers. With wait=<seconds> it is a question, and the call waits for the replies.',
             nouns=(Noun('to', 'One ticket: its work id, or its number, <address>#<n>.', required=False),
                    Noun('at', 'A part of the map, by Address: every agent at work at it or inside it, so a trunk '
                               'Address reaches a whole area.', required=False),
                    Noun('file', 'A file or folder, from the project folder: every agent whose tool calls touched it.',
                         required=False),
                    Noun('topic', 'Words: every agent whose open ticket\'s title holds them all.', required=False),
                    Noun('reply', 'The id of a note sent to you, to answer it; the answer is threaded to it.',
                         required=False),
                    Noun('wait', 'Seconds, 1 to 120, to wait for the replies, which the call returns; it says plainly '
                                 'who did not answer.', kind='int', required=False),
                    Noun('text', 'The note, at most 1,000 characters.', many=True)),
             examples=((('metaform dispatch note file=src/metaform/modules/web/page/app/core/dom.js wait=60 -- "I am '
                         'about to change css(); anything I should know?"'),
                        'Asks every agent that touched dom.js, and waits up to a minute for their replies.'),
                       ('metaform dispatch note reply=3f9a0c1d2e4b5a6c -- "Go ahead; I am done with it."',
                        'Answers the note 3f9a0c1d2e4b5a6c, threaded to it.')), open_world=True),
        Verb('notes', notes, 'List your notes, sent and received, with where each stands for each receiver: queued, '
                             'delivered, read or replied; note=<id> for one note and its replies.',
             nouns=(Noun('note', 'A note\'s id, for it and the replies threaded to it.', required=False),
                    Noun('limit', 'How many, the latest first; 20 by default.', kind='int', required=False)),
             effect='read'),
        Verb('peers', peers, 'See who is at work where: each agent on an open ticket, its Address, the files it touched '
                             'and what it said last. With at=, file= or topic=, who else is in that part or file, with '
                             'a note ready to ask them before you edit.',
             nouns=(Noun('at', 'A part of the map, by Address: those at work at it or inside it.', required=False),
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
        Verb('interrupt', interrupt, 'Interrupt the turn of the agent working a ticket, keeping its conversation open.',
             nouns=(Noun('id', 'The work id of the ticket.'),
                    Noun('session', 'The chat session id, to avoid interrupting a replacement session.', required=False)),
             examples=(('metaform dispatch interrupt 198452e1...', 'Requests cancellation; the session stays available.'),), open_world=True,
             listed=session_live),
        Verb('stop', stop, 'Stop the agent working a ticket.',
             nouns=(Noun('id', 'The work id of the ticket.'),
                    Noun('session', 'The session id, for one of several on the ticket; the latest when none is given.',
                         required=False)), open_world=True, listed=session_live),
        Verb('sessions', read_sessions, 'List the agent sessions of a ticket, or of every ticket, each with its '
                                        'thread.',
             nouns=(Noun('id', 'The work id of the ticket; none for every ticket.', required=False),
                    Noun('thread', 'false leaves the threads out, for a list of the sessions only.', kind='bool',
                         required=False),
                    Noun('since', "Only each thread's lines after this seq, for a caller that polls; all by default.",
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
             nouns=(Noun('agent', 'claude, codex or gemini; every agent when none is given.', required=False),
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
             nouns=(Noun('agent', 'claude, codex or gemini.'),
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
             nouns=(Noun('agent', 'claude, codex or gemini to pass through, none for Metaform alone; '
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
                   Subscription('signal.raised', collect), Subscription('map.changed', progress_changed)),
    work_read=work_read,
    start=started,
    stop=None,
    status=None,
)
