"""paperclip: Metaform and a Paperclip server working the same tickets.

Paperclip (github.com/paperclipai/paperclip) runs agents in heartbeats against issues, with an org chart, budgets and
approvals. Its REST API, its issue documents, its issue monitors and its process adapter are the standard ways in, so
this module uses those and nothing of its own: `client.py` makes the calls. The design and its sources are in
artifacts/swarm-2026-10-11/PAPERCLIP-INTEGRATION.md.

Each Paperclip issue this module knows is a row of its `links` table, tied to one ticket, a work record at an Address.
`works` says which side does the work and so which side's state the other follows:
  paperclip  a Paperclip agent works it, sent there by `send` or linked by `link`; the ticket stays in doing, taken
             by Paperclip, so dispatch never starts an agent on it too; `sync` closes it when the issue closes, and
             cancels the issue when the person cancels the ticket;
  metaform   Paperclip assigned the issue to a Metaform agent and `heartbeat` took it, run by Paperclip's process
             adapter; the ticket goes to To do and dispatch's autostart is asked to start it, the issue carries an
             external_service monitor so Paperclip wakes the agent to check rather than reading the run as stuck,
             comments cross in as messages at the Address, the ticket's questions cross out as question cards whose
             answers come back as replies, and `sync` reports the ticket's end on the issue.
Where an issue's end reaches a ticket an agent works, dispatch's own verbs end its session: `cancel` for an issue
cancelled, `stop` before the close of an issue done. Other modules' verbs are called through their declarations, as
the command line calls them, so their rules hold.
The issue's document keyed `metaform` names its Address, its brief and its ticket, so any agent Paperclip runs on it,
and the person, read where in the map it works.

Tokens are never kept in Metaform's settings: `paperclip_token_env` names the environment variable that holds one.
During a heartbeat, the URL, company, agent and run id Paperclip injects (PAPERCLIP_API_URL, PAPERCLIP_COMPANY_ID,
PAPERCLIP_AGENT_ID, PAPERCLIP_RUN_ID) win over the settings, since the run's token works only with them.
"""
from __future__ import annotations

import contextlib
import json
import math
import os
import re
import signal
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime, timedelta
from importlib import resources
from pathlib import Path
from typing import Any, cast

from metaform import home, jev, prompt_files, settings
from metaform.data import Column, Index, Message, Node, Store, StoreError, Table, Tables, WorkRecord, now
from metaform.data import status as vocabulary
from metaform.module import (
    Context,
    Module,
    Noun,
    Status,
    Stop,
    Subscription,
    Verb,
    call,
    child_environment,
    context,
    first_line,
    node_brief,
    surface,
    tool_arguments,
)

from .client import Client, Opener, PaperclipError

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = True  # it needs a Paperclip server, which most projects do not run
REMOTE_AGENT = False  # it reaches a Paperclip server on the person's own machine or network

DOCUMENT = 'metaform'  # the key of the issue document naming the issue's Address, its brief and its ticket
# Paperclip's issue states (packages/shared/src/constants.ts, ISSUE_STATUSES) in the one status vocabulary,
# metaform.data.status: in_review is paused on a reviewer, person or board, and blocked waits on something named.
STATES: dict[str, vocabulary.State] = {
    'backlog': 'submitted', 'todo': 'submitted', 'in_progress': 'running', 'in_review': 'input_required',
    'blocked': 'waiting', 'done': 'completed', 'cancelled': 'cancelled'}
# A ticket's end as the Paperclip state `sync` reports. A failed ticket waits in in_review on a question card only a
# person answers: blocked needs a blocking issue or an unblock owner, and an agent may name neither the board nor a
# person (skills/paperclip/SKILL.md, Step 7), COOPERATION-DESIGN C8 P-3.
REPORTED: dict[vocabulary.State, str] = {'completed': 'done', 'cancelled': 'cancelled', 'failed': 'in_review'}
ANSWER = 'answer'  # the id of the one question on each question card this module puts on an issue
ADDRESS = re.compile(r'^\s*address:\s*(\S+)\s*$', re.IGNORECASE | re.MULTILINE)
TICKET = re.compile(r'^\s*ticket:\s*(\S+)\s*$', re.IGNORECASE | re.MULTILINE)
UUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$', re.IGNORECASE)
BRIDGE = uuid.UUID('6f1c1d2e-8a51-4c41-9a44-7d7f3c0b8e10')  # names each bridged message's clientRequestId, uuid5
CANDIDATES = 12  # the Addresses Jev chooses among when an issue names none, the best matches of its words
RESOLVED = 2000  # the most of an assignee's last comment kept as the resolution of a ticket whose issue is done
BEAT = 20  # seconds between the watcher's beats in its run file; one older than three beats is a watcher gone
WORD = re.compile(r'[a-z0-9]{3,}')
PROMPTS = resources.files(__name__)
OPENER: Opener | None = None  # what opens each request to Paperclip; urlopen when None, an in-memory server in tests

# Where Metaform calls out to and which agents it hands work to are the person's to decide, never an agent's over MCP,
# CLI-011, so every setting here is person_only; the token itself is never a setting.
settings.text('paperclip_url', 'http://localhost:3100', person_only=True, label='Paperclip URL',
              help='The Paperclip server this project works with, its origin as Paperclip writes PAPERCLIP_API_URL.',
              details='During a Paperclip heartbeat the PAPERCLIP_API_URL Paperclip injects is used instead, since '
                      'the run token works only with the server that issued it.')
settings.text('paperclip_token_env', 'PAPERCLIP_API_KEY', person_only=True, label='Paperclip token variable',
              help='The environment variable holding the bearer token for Paperclip: an agent key, a board key, or '
                   'the run token Paperclip injects during a heartbeat.',
              details='The token is read from the environment on each call and never stored by Metaform. A server '
                      'in local_trusted mode needs none.')
settings.text('paperclip_company', '', person_only=True, label='Paperclip company',
              help='The Paperclip company id issues are sent to and read from. Empty uses PAPERCLIP_COMPANY_ID.')
settings.text('paperclip_assignee', '', person_only=True, label='Paperclip assignee',
              help='The Paperclip agent send assigns a ticket to, by id or by the short name Paperclip shows in its '
                   'URL. Empty lets Jev choose among the company\'s agents when Jev is on, else sends it unassigned.')
settings.text('paperclip_project', '', person_only=True, label='Paperclip project',
              help='The Paperclip project id send files issues under, whose workspace sets the folder its agents '
                   'work in. Empty files them under none.')
settings.number('paperclip_check_minutes', 10, min=1, max=1440, person_only=True, label='Paperclip check minutes',
                help='How often Paperclip wakes the Metaform agent to check an issue a Metaform agent is working.',
                details='Each issue heartbeat takes carries an issue monitor of kind external_service, so Paperclip '
                        'reads it as held by an outside service rather than as a stuck run, and wakes the agent this '
                        'many minutes on to sync it. Each heartbeat sets the next check while the ticket is open. '
                        'paperclip watch syncs this often too.')
settings.boolean('paperclip_jev_route', True, person_only=True, label='Paperclip routing by Jev',
                 help='Let Jev choose the Address of a Paperclip issue that names none, when the setting jev is on.',
                 details='heartbeat offers Jev the Addresses whose purposes best match the issue\'s words; a sure '
                         'answer is kept at that Address and the issue is taken there. Off, or Jev off or unsure, '
                         'the issue is left for the person to link. jev_decisions does not name this decision; this '
                         'setting turns it off.')
settings.boolean('paperclip_agents_may_send', False, person_only=True, label='Agents may send to Paperclip',
                 help='Let an agent send a ticket to Paperclip over MCP, as the person can from the command line.',
                 details='Off, the default: only the person hands work to Paperclip, whose agents spend from its '
                         'budgets. On: a Metaform agent may delegate a ticket to a Paperclip agent with '
                         'paperclip_send.')

TABLES = Tables(version=2, compatible_from=1, tables=(
    # One row per Paperclip issue tied to a ticket. In the metaform beside the work records, so a clear of the
    # metaform drops the links with the tickets they tie, STORE-045. `comments_seen` is the last comment read from the
    # issue; `linked` when the tie was made, so only the Address's messages from then on cross to the issue.
    Table('links', place='metaform', key=('issue_id',),
          columns=(Column('issue_id', required=True), Column('identifier'), Column('company_id'),
                   Column('work_id', required=True), Column('address', required=True),
                   Column('works', required=True), Column('state'), Column('reported'), Column('synced'),
                   Column('comments_seen'), Column('linked')),
          indexes=(Index(('work_id',)), Index(('identifier',)))),
    # Each comment, question and card that crossed between an issue and its ticket's Address, so none crosses twice
    # and none crosses back. `comment_id` is Paperclip's id; `way` is in (a comment written as a message), note (a
    # comment this module posted itself, or `unrouted`, the one note on an issue it could not take), ask (a question
    # sent as a question card, `comment_id` the card's id), failed (the card on a failed ticket's issue), or done (a
    # card answered, withdrawn or closed, read no more).
    Table('bridged', place='metaform', key=('issue_id', 'comment_id'),
          columns=(Column('issue_id', required=True), Column('comment_id', required=True), Column('message_id'),
                   Column('way', required=True), Column('at')),
          indexes=(Index(('message_id',)),)),
))


# ---------------------------------------------------------------------------------------------- reaching Paperclip

def _client(ctx: Context) -> Client:
    url = os.environ.get('PAPERCLIP_API_URL') or str(ctx.setting('paperclip_url') or '')
    if not url:
        raise Stop('No Paperclip server is set.', 'metaform set --paperclip-url <origin, such as http://localhost:3100>')
    token = os.environ.get(str(ctx.setting('paperclip_token_env') or '')) or None
    return Client(url, token, run_id=os.environ.get('PAPERCLIP_RUN_ID'), opener=OPENER)


def _company(ctx: Context) -> str:
    company = os.environ.get('PAPERCLIP_COMPANY_ID') or str(ctx.setting('paperclip_company') or '')
    if not company:
        raise Stop('No Paperclip company is set.', 'metaform set --paperclip-company <company id>')
    return company


def _call(what: str, run: Any, *args: Any) -> Any:
    """One Paperclip call; its failure is a Stop naming the call, the server's reason and what to check."""
    try:
        return run(*args)
    except PaperclipError as error:
        step = ('metaform paperclip status' if error.status in (0, 401, 403)
                else 'read the issue in Paperclip, then run the command again')
        raise Stop(f'Paperclip refused to {what}: {error}', step) from None


def _said(name: str, **fills: str) -> str:
    """This module's prompt `name`, from its resources/prompts.xml."""
    return prompt_files.required(PROMPTS, name, **fills)


def _on_surface(ctx: Context, module_id: str) -> bool:
    return any(one.id == module_id for one in surface(ctx.folder))


def _verb(ctx: Context, module_id: str, name: str, arguments: dict[str, Any]) -> Any:
    """Run another module's declared verb on this folder's surface as the command line runs it, its arguments checked
    as the command line checks them, so that module's own rules hold: dispatch's cancel, stop, sessions and autostart,
    and map's reply. The same composition of the public base as mcp/a2a.py `_verb`."""
    found = next((one for one in surface(ctx.folder) if one.id == module_id), None)
    verb = next((one for one in found.verbs if one.name == name), None) if found is not None else None
    if verb is None:
        raise Stop(f'{module_id} {name} is not on this project\'s surface.', f'metaform enable {module_id}')
    nouns, switches, _ = tool_arguments(module_id, verb, arguments, folder=ctx.folder)
    return call(verb.run, context(module_id, ctx.folder, project=ctx.project, nouns=nouns, switches=switches,
                                  sink=lambda _text: None, surface=ctx.surface))


def _running(ctx: Context, work_id: str) -> bool:
    """Whether a dispatch session is running on the ticket, as dispatch's own sessions verb reads it."""
    if not _on_surface(ctx, 'dispatch'):
        return False
    read = _object(_verb(ctx, 'dispatch', 'sessions', {'id': work_id, 'thread': False}))
    return any(one.get('state') == 'running' for one in _objects(read.get('sessions')))


# ------------------------------------------------------------------------------------------------- the link table

def _link(store: Store, issue: str) -> dict[str, Any] | None:
    """The link for an issue named by its id or its identifier, such as PAP-12."""
    with store.tables(write=False) as tx:
        found = tx.get('links', {'issue_id': issue})
        if found is None:
            rows = tx.rows('links', {'identifier': issue}, by=('identifier',), limit=1).results
            found = rows[0] if rows else None
    return found


def _link_of_work(store: Store, work_id: str) -> dict[str, Any] | None:
    with store.tables(write=False) as tx:
        rows = tx.rows('links', {'work_id': work_id}, by=('work_id',), limit=1).results
    return rows[0] if rows else None


def _links(store: Store) -> Iterator[dict[str, Any]]:
    with store.tables(write=False) as tx:
        rows = tx.rows('links', limit=0).results
    yield from rows


def _keep(store: Store, row: dict[str, Any]) -> None:
    with store.tables() as tx:
        if tx.get('links', {'issue_id': row['issue_id']}) is None:
            tx.insert('links', {'linked': now(), **row})
        else:
            tx.update('links', {'issue_id': row['issue_id']}, {k: v for k, v in row.items() if k != 'issue_id'})


def _bridged(store: Store, issue_id: str, comment_id: str | None = None, message_id: str | None = None) -> bool:
    with store.tables(write=False) as tx:
        if comment_id is not None and tx.get('bridged', {'issue_id': issue_id, 'comment_id': comment_id}) is not None:
            return True
        if message_id is not None:
            rows = tx.rows('bridged', {'message_id': message_id}, by=('message_id',), limit=0).results
            return any(row['issue_id'] == issue_id for row in rows)
    return False


def _bridge(store: Store, issue_id: str, comment_id: str, message_id: str | None, way: str) -> None:
    with store.tables() as tx:
        if tx.get('bridged', {'issue_id': issue_id, 'comment_id': comment_id}) is None:
            tx.insert('bridged', {'issue_id': issue_id, 'comment_id': comment_id, 'message_id': message_id,
                                  'way': way, 'at': now()})


def _object(value: Any) -> dict[str, Any]:
    """A JSON object Paperclip answered with, or an empty one for anything else."""
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _objects(value: Any) -> list[dict[str, Any]]:
    """A JSON array of objects Paperclip answered with, each as an object."""
    return [_object(one) for one in cast(list[Any], value)] if isinstance(value, list) else []


def _address(record: WorkRecord) -> str:
    """Where a ticket is: its element, or for a join its receiver, since all knowledge attaches to the RE (Join)."""
    found = record.address or record.receiver_address
    if not found:
        raise Stop(f'Ticket {record.id} is at no Address.', f'metaform map work id={record.id}')
    return found


def _reference(store: Store, kind: str, item_id: str, fallback: str) -> str:
    numbered = store.numbers_of(kind, [item_id]).get(item_id)
    return numbered[0] if numbered else fallback


def _document(address: str, work_id: str) -> str:
    """The issue's `metaform` document: data, one line each, read by people, by agents and by `heartbeat`. The brief
    line is the tool call that reads it, since Paperclip's MCP gateway serves no resource templates."""
    return f'address: {address}\nbrief: map_where {address}\nticket: {work_id}\n'


def _write_document(client: Client, issue_id: str, address: str, work_id: str) -> None:
    """Write the issue's metaform document unless it already names this Address and ticket, so a repeated `link` or
    `send` repairs a document a failed call left missing."""
    held = _object(_call('read the metaform document', client.document, issue_id, DOCUMENT))
    body = held.get('body')
    if isinstance(body, str):
        named, ticket = ADDRESS.search(body), TICKET.search(body)
        if named and ticket and named.group(1) == address and ticket.group(1) == work_id:
            return
    _call('write the metaform document', client.put_document, issue_id, DOCUMENT, 'Metaform',
          _document(address, work_id), held.get('latestRevisionId'))


def _issue_address(client: Client, issue_id: str) -> str | None:
    body = _object(client.document(issue_id, DOCUMENT)).get('body')
    found = ADDRESS.search(body) if isinstance(body, str) else None
    return found.group(1) if found else None


def _shown(row: dict[str, Any]) -> dict[str, Any]:
    state = str(row.get('state') or '')
    return {'issue': row.get('identifier') or row['issue_id'], 'issue_id': row['issue_id'], 'ticket': row['work_id'],
            'address': row['address'], 'brief': f"map_where {row['address']}", 'works': row['works'],
            'state': row.get('state'), 'status': STATES.get(state)}


def _agent(client: Client, company: str, named: str) -> str:
    """A Paperclip agent's id from its id or its short name, the urlKey Paperclip resolves a name to: the name
    lowercased with each run of other characters a hyphen (packages/shared/src/agent-url-key.ts). Issue create and
    checkout take only an id (packages/shared/src/validators/issue.ts), so a short name is resolved here first."""
    if UUID.fullmatch(named.strip()):
        return named.strip()
    key = re.sub(r'[^a-z0-9]+', '-', named.strip().lower()).strip('-')
    agents = _objects(_call('list the company\'s agents', client.agents, company))
    found = [one for one in agents if one.get('status') != 'terminated'
             and (one.get('urlKey') or re.sub(r'[^a-z0-9]+', '-', str(one.get('name') or '').lower()).strip('-'))
             == key]
    if len(found) != 1:
        raise Stop(f'No one Paperclip agent is named {named!r}: {len(found)} match.',
                   'metaform set --paperclip-assignee <the agent id from Paperclip>')
    return str(found[0]['id'])


# --------------------------------------------------------------------------------------------------------- verbs

def _command() -> tuple[str, list[str]]:
    """The command and arguments that run `metaform paperclip heartbeat` as Paperclip spawns it: one absolute
    executable and its arguments apart, since Paperclip runs it without a shell and looks the command up as one file
    (packages/adapter-utils/src/server-utils.ts, runChildProcess and resolveCommandPath). It is this install's own
    entry point, the script this process runs from, else this interpreter with -m metaform; never the first metaform
    on PATH, which can be another install."""
    script = Path(sys.argv[0]) if sys.argv and sys.argv[0] else None
    if script is not None and script.stem == 'metaform' and script.is_file():
        return str(script.resolve()), ['paperclip', 'heartbeat']
    # absolute, not resolved: a virtual environment's python is a link, and its target has none of its packages
    return os.path.abspath(sys.executable), ['-m', 'metaform', 'paperclip', 'heartbeat']


def status(ctx: Context) -> dict[str, Any]:
    """Which Paperclip server and company this folder uses, whether it answers, who the token speaks for, and the
    process-adapter configuration that runs this folder's heartbeat."""
    client = _client(ctx)
    variable = str(ctx.setting('paperclip_token_env') or '')
    command, args = _command()
    shown: dict[str, Any] = {'url': client.url, 'token': f'{variable} is {"set" if client.token else "not set"}',
                             'company': os.environ.get('PAPERCLIP_COMPANY_ID') or ctx.setting('paperclip_company')
                             or None,
                             'agent_config': {'adapterType': 'process',
                                              'adapterConfig': {'command': command, 'args': args,
                                                                'cwd': str(ctx.folder)}}}
    try:
        health = _object(client.health())
        shown['server'] = {key: health.get(key) for key in ('status', 'version', 'deploymentMode')}
    except PaperclipError as error:
        shown['server'] = str(error)
        return shown
    try:
        me = _object(client.me())
        shown['agent'] = {key: me.get(key) for key in ('id', 'name', 'role', 'companyId', 'budgetMonthlyCents',
                                                        'spentMonthlyCents')}
    except PaperclipError as error:
        shown['agent'] = None if error.status == 401 else str(error)  # 401 is a board caller, not an agent
    if ctx.store is not None:
        shown['links'] = sum(1 for _ in _links(ctx.store))
    return shown


def link(ctx: Context) -> dict[str, Any]:
    """Tie a Paperclip issue a Paperclip agent works to an Address: a ticket there that follows it, and the issue's
    metaform document naming the Address, its brief and the ticket."""
    store = ctx.require_store()
    issue_id, address = str(ctx.nouns['issue']), str(ctx.nouns['address'])
    held = _link(store, issue_id)
    if held is not None:
        if held['address'] != address:
            raise Stop(f"Issue {held.get('identifier') or issue_id} is linked to {held['address']} already.",
                       f"metaform map work op=edit id={held['work_id']} node={address}")
        _write_document(_client(ctx), held['issue_id'], held['address'], held['work_id'])
        return _shown(held)
    client = _client(ctx)
    issue = _object(_call('read the issue', client.issue, issue_id))
    title = str(issue.get('title') or issue_id)
    record = store.add_work(Node('element', address), None, title=title[:120],
                            task=str(issue.get('description') or title), held=True)
    record = store.take_work(record.id, by=f"paperclip {issue.get('identifier') or issue['id']}")
    row: dict[str, Any] = {'issue_id': str(issue['id']), 'identifier': issue.get('identifier'),
                           'company_id': issue.get('companyId'), 'work_id': record.id, 'address': address,
                           'works': 'paperclip', 'state': issue.get('status'), 'synced': now()}
    _keep(store, row)
    _write_document(client, row['issue_id'], address, record.id)
    return _shown(row)


def brief(ctx: Context) -> str:
    """The brief of the Address a Paperclip issue works on, the issue Paperclip woke this run for when none is
    named."""
    store = ctx.require_store()
    issue = str(ctx.nouns.get('issue') or ctx.identity.get('issue_id') or os.environ.get('PAPERCLIP_TASK_ID') or '')
    if not issue:
        raise Stop('No Paperclip issue is named, and this is not a Paperclip run.', 'metaform paperclip brief issue=<id>')
    held = _link(store, issue)
    address = held['address'] if held else _call('read the issue\'s metaform document', _issue_address,
                                                 _client(ctx), issue)
    if not address:
        raise Stop(f'Paperclip issue {issue} names no Address.', f'metaform paperclip link {issue} <address>')
    found = node_brief(ctx.folder, address)
    if found is None:
        raise Stop('The map module is not enabled here, so no brief can be read.', 'metaform enable map')
    return found if found.endswith('\n') else found + '\n'


def _chosen_assignee(ctx: Context, client: Client, company: str, record: WorkRecord, address: str,
                     title: str) -> tuple[str | None, str | None]:
    """The Paperclip agent a ticket is sent to, and the Jev decision that chose it: the one named, else the setting,
    else Jev's sure choice among the company's agents when Jev is on (choose_agent, kept at the ticket's Address),
    else none, which sends the issue to Paperclip's backlog."""
    named = str(ctx.nouns.get('assignee') or ctx.setting('paperclip_assignee') or '')
    if named:
        return _agent(client, company, named), None
    try:
        agents = _objects(client.agents(company))
    except PaperclipError:
        return None, None
    offered = {str(one['id']): ', '.join(str(one[key]) for key in ('name', 'title', 'role', 'adapterType',
                                                                    'capabilities') if one.get(key))
               for one in agents if one.get('id') and one.get('status') not in ('terminated', 'pending_approval')}
    decision = jev.choose_agent(ctx.folder, {'id': record.id, 'title': title, 'task': record.task or '',
                                             'address': address}, offered)
    if decision is None or not decision.sure:
        return None, None
    chosen = str(cast(Mapping[str, Any], decision.answer).get('agent') or '')
    return (chosen, decision.item) if chosen in offered else (None, None)


def send(ctx: Context) -> dict[str, Any]:
    """Send an open ticket to Paperclip as an issue for its agents to work; the ticket follows the issue."""
    store = ctx.require_store()
    if ctx.surface == 'mcp' and not ctx.setting('paperclip_agents_may_send'):
        raise Stop('Only the person sends tickets to Paperclip here: paperclip_agents_may_send is off.',
                   'ask the person to run metaform paperclip send, or metaform set --paperclip-agents-may-send true')
    work_id = str(ctx.nouns['id'])
    held = _link_of_work(store, work_id)
    if held is not None:
        _write_document(_client(ctx), held['issue_id'], held['address'], work_id)
        return {**_shown(held), 'next': _follows(ctx, _ensure_watcher(store, ctx.folder))}
    record = store.ticket(work_id).work
    if record.done or record.taken:
        raise Stop(f"Ticket {work_id} is {'done' if record.done else 'taken by ' + str(record.taken_by)}; only an "
                   'open ticket nobody holds is sent.', 'metaform map work open=true')
    address = _address(record)
    numbered = store.numbers_of('work', [work_id]).get(work_id)
    title = (numbered[1] if numbered and numbered[1] else None) or first_line(record.task) or first_line(record.note) \
        or f'Ticket {work_id}'
    client = _client(ctx)
    company = _company(ctx)
    assignee, chose = _chosen_assignee(ctx, client, company, record, address, title)
    fields: dict[str, Any] = {
        'title': title[:240],
        'description': '\n\n'.join(part for part in (record.task, record.note) if part),
        'status': 'todo' if assignee else 'backlog',
        'idempotencyKey': f'metaform:{store.project_id}:{work_id}',  # a second send replays the first issue
    }
    if assignee:
        fields['assigneeAgentId'] = assignee
    if ctx.setting('paperclip_project'):
        fields['projectId'] = str(ctx.setting('paperclip_project'))
    # Reserved before the issue exists, so dispatch's autostart cannot take the ticket while it is being sent; given
    # back to its column when the issue cannot be made, and the idempotency key replays the issue on a retry.
    column = record.column
    try:
        store.take_work(work_id, by='paperclip')
    except StoreError as error:
        raise Stop(f'Ticket {work_id} was taken while it was being sent: {error.message}', error.next_step) from None
    try:
        issue = _object(_call('create the issue', client.create_issue, company, fields))
        row: dict[str, Any] = {'issue_id': str(issue['id']), 'identifier': issue.get('identifier'),
                               'company_id': company, 'work_id': work_id, 'address': address, 'works': 'paperclip',
                               'state': issue.get('status'), 'synced': now()}
        _keep(store, row)
    except BaseException:
        store.move_work(work_id, column)
        raise
    _write_document(client, row['issue_id'], address, work_id)
    shown = _shown(row)
    if chose:
        shown['assignee_chosen'] = chose
    shown['next'] = _follows(ctx, _ensure_watcher(store, ctx.folder))
    return shown


def _follows(ctx: Context, started: int | None = None) -> str:
    """How a ticket sent to Paperclip follows its issue: each sync, which the watcher runs while it runs, the one just
    `started` before it has written its record."""
    found = {'pid': started} if started is not None else _watcher(str(ctx.project)) if ctx.project else None
    if found is not None:
        return (f"the ticket follows the issue: the Paperclip watcher, process {found.get('pid')}, runs metaform "
                'paperclip sync every paperclip_check_minutes')
    return ('the ticket follows the issue each time metaform paperclip sync runs; metaform paperclip watch runs it '
            'every paperclip_check_minutes, and send and web start start the watcher while issues are open')


def _record(store: Store, work_id: str) -> WorkRecord | None:
    try:
        return store.ticket(work_id).work
    except StoreError:
        return None


def _due(issue: Mapping[str, Any]) -> bool:
    """Whether the issue's monitor needs setting: it has none, or its time has passed."""
    at = issue.get('monitorNextCheckAt')
    if not isinstance(at, str) or not at:
        return True
    try:
        return datetime.fromisoformat(at) <= datetime.now(UTC)
    except ValueError:
        return True


def _stamp(at: datetime) -> str:
    return at.isoformat(timespec='seconds').replace('+00:00', 'Z')


def _watch(ctx: Context, client: Client, issue: Mapping[str, Any], reference: str) -> None:
    """Set the issue's monitor, kind external_service, so Paperclip reads the issue as held by an outside service and
    wakes its assignee, this agent, at the next check (packages/shared/src/validators/issue.ts,
    issueExecutionMonitorPolicySchema; skills/paperclip/SKILL.md, Monitors and Watchers). Its bounds are stated, as
    SKILL.md asks: one wake, and none once a further interval has passed, since each sync sets the next check and a
    replaced monitor counts its attempts again (server/src/services/issue-monitors.ts). The issue's other execution
    policy is kept, since a PATCH replaces the policy whole."""
    minutes = int(ctx.setting('paperclip_check_minutes') or 10)
    at = datetime.now(UTC) + timedelta(minutes=minutes)
    policy = {**_object(issue.get('executionPolicy')),
              'monitor': {'nextCheckAt': _stamp(at), 'kind': 'external_service', 'serviceName': 'Metaform',
                          'externalRef': reference[:500], 'maxAttempts': 1,
                          'timeoutAt': _stamp(at + timedelta(minutes=minutes))}}
    client.update_issue(str(issue['id']), {'executionPolicy': policy})


def _unwatched(issue: Mapping[str, Any]) -> dict[str, Any] | None:
    """The issue's execution policy without its monitor, or None when it has no stages left, as Paperclip strips a
    monitor itself (server/src/services/issue-execution-policy.ts, stripMonitorFromExecutionPolicy)."""
    policy = {key: value for key, value in _object(issue.get('executionPolicy')).items() if key != 'monitor'}
    return policy if policy.get('stages') else None


def _author(comment: Mapping[str, Any]) -> str:
    if comment.get('authorAgentId'):
        return f"agent {comment['authorAgentId']}"
    return f"person {comment.get('authorUserId') or 'unknown'}"


def _comments_in(store: Store, client: Client, row: dict[str, Any]) -> int:
    """Each new comment on the issue, written as a message at the ticket's Address. Paperclip's own notices and the
    comments this module posted are left out. The last comment read is kept, so a comment is read once."""
    seen = row.get('comments_seen')
    name = str(row.get('identifier') or row['issue_id'])
    written = 0
    for comment in _objects(client.comments(row['issue_id'], seen)):
        comment_id = str(comment.get('id') or '')
        if not comment_id:
            continue
        seen = comment_id
        notice = comment.get('authorType') == 'system' or \
            _object(comment.get('presentation')).get('kind') == 'system_notice'
        if notice or _bridged(store, row['issue_id'], comment_id=comment_id) or not str(comment.get('body') or ''):
            continue
        author = _author(comment)
        said = store.tell(Node('element', row['address']), str(comment['body']), by=f'paperclip {name} {author}',
                          title=_said('comment', issue=name, author=author))
        _bridge(store, row['issue_id'], comment_id, said.id, 'in')
        written += 1
    if seen != row.get('comments_seen'):
        _keep(store, {**row, 'comments_seen': seen})
        row['comments_seen'] = seen
    return written


def _held(store: Store, address: str) -> list[Message]:
    """The questions and messages at the Address, oldest first."""
    held: list[Message] = []
    after: str | None = None
    while True:
        page = store.messages(Node('element', address), limit=100, after=after)
        held.extend(page.results)
        after = page.next
        if not after:
            return held


def _card(issue_id: str, key: str, title: str, question: dict[str, Any]) -> dict[str, Any]:
    """A question card on the issue: an ask_user_questions interaction only a person may answer, which wakes the
    assignee, this agent, when it is answered, with one question in Paperclip's question set (skills/paperclip/SKILL.md,
    Human input questions; server/src/services/connectors/slack/agent-guidance.ts). The key makes a repeat the same
    card."""
    return {'kind': 'ask_user_questions', 'idempotencyKey': f'metaform:{issue_id}:{key}'[:255], 'title': title[:240],
            'resolverPolicy': 'human_only', 'continuationPolicy': 'wake_assignee',
            'payload': {'version': 1, 'questionSet': {'schema': 'paperclip.question_set.v1',
                                                      'questions': [{'id': ANSWER, 'required': True, **question}]}}}


def _question_card(store: Store, row: dict[str, Any], message: Message) -> dict[str, Any]:
    """A question at the ticket's Address as a card: its suggested answers as the choices, with an answer of the
    person's own beside them; with fewer than two, a text answer starting from the one suggested."""
    numbered = store.numbers_of('message', [message.id]).get(message.id)
    reference = numbered[0] if numbered else row['address']
    title = (numbered[1] if numbered and numbered[1] else None) or first_line(message.text) or reference
    suggested = [one.strip()[:1000] for one in message.suggestions if one.strip()]
    question: dict[str, Any] = {'header': reference, 'prompt': str(message.text or title)[:4000]}
    if len(suggested) >= 2:
        question.update(answerMode='single_select', customAnswer={'enabled': True},
                        options=[{'id': f'o{n}', 'label': one} for n, one in enumerate(suggested)])
    else:
        question['answerMode'] = 'text'
        if suggested:
            question['initialText'] = suggested[0]
    return _card(row['issue_id'], message.id, title, question)


def _questions_out(store: Store, client: Client, row: dict[str, Any], held: list[Message]) -> int:
    """Each open question at the Address that belongs to this ticket, sent once as a question card on the issue, so
    Paperclip's people answer it: a dispatched agent's permission request, or a question the person asked with the
    ticket named. Questions about other tickets at the same Address stay here."""
    sent = 0
    for message in held:
        if message.kind != 'question' or message.work_id != row['work_id'] or message.closed:
            continue
        if _bridged(store, row['issue_id'], message_id=message.id):
            continue
        card = _object(client.ask(row['issue_id'], _question_card(store, row, message)))
        _bridge(store, row['issue_id'], str(card.get('id') or f'ask:{message.id}'), message.id, 'ask')
        sent += 1
    return sent


def _chosen(card: Mapping[str, Any]) -> tuple[list[str], str | None]:
    """The choices a person made on a card, by option id, and the text they wrote, from its result and its stored
    questions (packages/shared/src/validators/issue.ts, askUserQuestionsResultSchema; question-set.ts)."""
    answers = [one for one in _objects(_object(card.get('result')).get('answers')) if one.get('questionId') == ANSWER]
    if not answers:
        return [], None
    written = answers[0].get('otherText')
    picked = [str(one) for one in cast(list[Any], answers[0].get('optionIds') or [])]
    return picked, str(written).strip() if isinstance(written, str) and written.strip() else None


def _answer(card: Mapping[str, Any]) -> str | None:
    """A question card's answer as the text of a reply: the labels of the choices made, and the text written."""
    picked, written = _chosen(card)
    options = {str(option.get('id')): option for question in _objects(_object(card.get('payload')).get('questions'))
               for option in _objects(question.get('options'))}
    said = [str(options[one].get('label')) for one in picked if one in options and not options[one].get('freeText')]
    if written:
        said.append(written)
    return '; '.join(said) or None


def _cards(store: Store, issue_id: str) -> list[dict[str, Any]]:
    with store.tables(write=False) as tx:
        rows = tx.rows('bridged', {'issue_id': issue_id}, limit=0).results
    return [dict(row) for row in rows if row['way'] in ('ask', 'failed')]


def _closed_card(store: Store, issue_id: str, card_id: str) -> None:
    with store.tables() as tx:
        tx.update('bridged', {'issue_id': issue_id, 'comment_id': card_id}, {'way': 'done', 'at': now()})


def _answers_in(ctx: Context, store: Store, client: Client, row: dict[str, Any],
                held: list[Message]) -> dict[str, Any]:
    """Read the question cards this module put on the issue. A question answered there is answered here with map
    reply, so the answer is kept beside the question, MAP-050; one answered here first, or moved away, has its card
    withdrawn. The failed ticket's card is acted on: retry moves the issue to todo and forgets the link, so the next
    heartbeat takes it as a new ticket at the same Address; close cancels the issue."""
    waiting = _cards(store, row['issue_id'])
    if not waiting:
        return {}
    cards = {str(card.get('id')): card for card in _objects(client.interactions(row['issue_id']))}
    questions = {message.id: message for message in held}
    changed: dict[str, Any] = {}
    for kept in waiting:
        card_id = str(kept['comment_id'])
        card = cards.get(card_id)
        status = str(card.get('status') or '') if card else ''
        if kept['way'] == 'ask':
            message = questions.get(str(kept['message_id']))
            if message is None or message.closed:
                if status == 'pending':
                    client.withdraw(row['issue_id'], card_id)
                _closed_card(store, row['issue_id'], card_id)
                continue
            if card is None or status == 'pending':
                continue
            answer = _answer(card) if status == 'answered' else None
            if answer:
                _verb(ctx, 'map', 'reply', {'id': message.id, 'answer': answer})
                changed['answers_in'] = changed.get('answers_in', 0) + 1
            _closed_card(store, row['issue_id'], card_id)
            continue
        if card is None or status == 'pending':
            continue
        picked, _ = _chosen(card) if status == 'answered' else ([], None)
        _closed_card(store, row['issue_id'], card_id)
        if 'retry' in picked:
            client.update_issue(row['issue_id'], {'status': 'todo'})
            with store.tables() as tx:
                tx.delete('links', {'issue_id': row['issue_id']})
            changed['issue_now'] = 'todo'
            changed['link'] = 'forgotten, for the next heartbeat to take anew'
        elif 'close' in picked:
            client.update_issue(row['issue_id'], {'status': 'cancelled'})
            changed['issue_now'] = 'cancelled'
    return changed


def _note(store: Store, client: Client, issue_id: str, body: str, request: str | None = None) -> None:
    """A comment this module posts itself, kept so it is never read back as a comment for the agent."""
    comment = _object(client.comment(issue_id, body, request))
    if comment.get('id'):
        _bridge(store, issue_id, str(comment['id']), None, 'note')


def _last_said(store: Store, client: Client, issue: Mapping[str, Any]) -> str | None:
    """What the issue's assignee last wrote on it, cut to RESOLVED characters: the newest comment by that agent that
    is neither Paperclip's own notice nor one this module posted, or None when there is none."""
    assignee = issue.get('assigneeAgentId')
    if not assignee:
        return None
    for comment in _objects(client.comments(str(issue['id']), order='desc')):
        notice = comment.get('authorType') == 'system' or \
            _object(comment.get('presentation')).get('kind') == 'system_notice'
        body = str(comment.get('body') or '').strip()
        if notice or not body or comment.get('authorAgentId') != assignee:
            continue
        with store.tables(write=False) as tx:
            kept = tx.get('bridged', {'issue_id': str(issue['id']), 'comment_id': str(comment.get('id') or '')})
        if kept is not None and kept['way'] == 'note':
            continue
        return body[:RESOLVED]
    return None


def _close(ctx: Context, store: Store, client: Client, record: WorkRecord, name: str, state: str,
           issue: Mapping[str, Any]) -> dict[str, Any]:
    """Close a ticket whose issue Paperclip closed, ending the dispatch session on it through dispatch's own verbs:
    `cancel` for an issue cancelled, which cancels the agent's turn and closes the ticket cancelled, and `stop` before
    the close of an issue done. With dispatch off, the ticket is closed alone. An issue done is resolved with what its
    assignee last wrote on it, else with the issue's state."""
    outcome = STATES[state]
    dispatch = _on_surface(ctx, 'dispatch')
    if outcome == 'cancelled' and dispatch:
        done = _object(_verb(ctx, 'dispatch', 'cancel', {'id': record.id,
                                                         'reason': [f'{name} was cancelled in Paperclip.']}))
        return {'ticket_now': 'cancelled', **({'session': 'cancelled'} if done.get('session') else {})}
    stopped = dispatch and _running(ctx, record.id)
    if stopped:
        _verb(ctx, 'dispatch', 'stop', {'id': record.id})
    said = _last_said(store, client, issue) if state == 'done' else None
    store.finish_work(record.id, said or f'{name} is {state} in Paperclip.', f'Paperclip closed issue {name}.',
                      outcome=outcome)
    return {'ticket_now': outcome, **({'session': 'stopped'} if stopped else {})}


def _report(store: Store, client: Client, row: dict[str, Any], record: WorkRecord,
            issue: Mapping[str, Any]) -> str:
    """Report a ticket's end on its issue, once, with its resolution: done, cancelled, or in_review with a question
    card for a failed ticket. Once, since Paperclip's review stages may move the issue on from the state given, and
    that is theirs."""
    outcome = cast(vocabulary.State, record.outcome or 'completed')
    reference = _reference(store, 'work', record.id, record.id)
    resolution = str(record.resolution or 'no resolution was given')
    state = REPORTED.get(outcome, 'done')
    fields: dict[str, Any] = {'status': state,
                              'comment': _said('ended', ticket=reference, outcome=outcome, resolution=resolution)}
    if state == 'in_review':  # the card first: Paperclip refuses in_review with no path that wakes anyone
        question = {'prompt': _said('failed/ask', ticket=reference, address=row['address'],
                                    resolution=resolution)[:4000],
                    'answerMode': 'single_select',
                    'options': [{'id': 'retry', 'label': _said('failed/retry')},
                                {'id': 'close', 'label': _said('failed/close')}]}
        card = _object(client.ask(row['issue_id'], _card(row['issue_id'], f'{record.id}:failed',
                                                         _said('failed/title', ticket=reference), question)))
        _bridge(store, row['issue_id'], str(card.get('id') or f'failed:{record.id}'), None, 'failed')
        fields['executionPolicy'] = _unwatched(issue)
    client.update_issue(row['issue_id'], fields)
    return state


def _sync_one(ctx: Context, store: Store, client: Client, row: dict[str, Any]) -> dict[str, Any] | None:
    """Bring one link's two sides together; what changed, or None. The side that does the work leads. What was said
    crosses first, so a ticket's last question reaches the issue before its end is reported."""
    record = _record(store, row['work_id'])
    if record is None:
        return None
    issue = _object(client.issue(row['issue_id']))
    state = str(issue.get('status') or '')
    name = str(row.get('identifier') or row['issue_id'])
    ended = STATES.get(state) in vocabulary.TERMINAL
    changed: dict[str, Any] = {}
    if row['works'] == 'paperclip' and not record.done:
        # what the Paperclip agent says on the issue is knowledge of the Address it works, so it is kept there, up to
        # the sync that closes the ticket
        heard = _comments_in(store, client, row)
        if heard:
            changed['comments_in'] = heard
    if row['works'] == 'metaform' and not ended:
        held = _held(store, row['address'])
        if not record.done:
            heard = _comments_in(store, client, row)
            if heard:
                changed['comments_in'] = heard
        asked = _questions_out(store, client, row, held)
        if asked:
            changed['questions_out'] = asked
        changed.update(_answers_in(ctx, store, client, row, held))
        if 'link' in changed:
            return {'issue': name, 'ticket': record.id, **changed}
        if changed.get('issue_now'):
            state, ended = str(changed['issue_now']), True
    if not record.done and ended:
        changed.update(_close(ctx, store, client, record, name, state, issue))
    elif record.done and not row.get('reported') and not ended and (
            row['works'] == 'metaform' or record.outcome == 'cancelled'):
        # a Metaform agent's ticket ended, or the person cancelled a ticket a Paperclip agent works
        state = _report(store, client, row, record, issue)
        row = {**row, 'reported': record.outcome or 'completed'}
        changed['issue_now'] = state
    elif row['works'] == 'metaform' and not record.done and not ended and _due(issue) and \
            state in ('in_progress', 'in_review'):  # a monitor fires only in these (SKILL.md)
        _watch(ctx, client, issue, _reference(store, 'work', record.id, row['address']))
        changed['next_check'] = 'set'
    _keep(store, {**row, 'state': state, 'synced': now()})
    return {'issue': name, 'ticket': record.id, **changed} if changed else None


def sync(ctx: Context) -> dict[str, Any]:
    """Bring every linked issue and its ticket together: an issue closed in Paperclip closes its ticket and ends the
    agent's session on it; for a ticket a Metaform agent works, comments come in as messages at the Address, its
    questions go out as question cards and their answers come back as replies; a ticket a Metaform agent ended, or
    the person cancelled, is reported on its issue."""
    store = ctx.require_store()
    client = _client(ctx)
    changed: list[dict[str, Any]] = []
    failed: list[str] = []
    for row in list(_links(store)):
        try:
            one = _sync_one(ctx, store, client, row)
        except (PaperclipError, Stop, StoreError) as error:  # one link's fault is reported, never the heartbeat's
            failed.append(f"{row.get('identifier') or row['issue_id']}: {getattr(error, 'message', None) or error}")
            continue
        if one:
            changed.append(one)
    return {'changed': changed, 'failed': failed}


# ------------------------------------------------------------------------------------------------------ the watcher

def run_file(project: str) -> Path:
    """The running watcher's record for a project, its pid and its last beat."""
    return home.home() / 'run' / 'paperclip' / f'{project}.json'


def _watcher(project: str) -> dict[str, Any] | None:
    """The watcher running for a project: its record, while it beats; None when there is none or it has gone."""
    try:
        found: Any = json.loads(run_file(project).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    record = cast(dict[str, Any], found) if isinstance(found, dict) else {}
    return record if time.time() - float(record.get('beat') or 0) <= 3 * BEAT else None


def _followed(store: Store, row: dict[str, Any]) -> bool:
    """Whether sync has work left on a link a Paperclip agent works: its ticket open, or cancelled here and not yet
    reported on the issue."""
    record = _record(store, row['work_id']) if row['works'] == 'paperclip' else None
    if record is None:
        return False
    return not record.done or (record.outcome == 'cancelled' and not row.get('reported')
                               and STATES.get(str(row.get('state') or '')) not in vocabulary.TERMINAL)


def _left(ctx: Context, store: Store) -> bool:
    """Whether the watcher has work left: paperclip on this folder's surface and a link sync still follows."""
    return _on_surface(ctx, 'paperclip') and any(_followed(store, row) for row in _links(store))


def _idle(ctx: Context, store: Store, project: str) -> bool:
    """Whether the watcher ends: nothing is left to follow. Its record goes before the links are read again, so a
    ticket sent in between, whose send saw this watcher live and started none, keeps this one going; another watcher
    started meanwhile follows it instead."""
    if _left(ctx, store):
        return False
    with contextlib.suppress(OSError, ValueError):
        if json.loads(run_file(project).read_text(encoding='utf-8')).get('pid') == os.getpid():
            run_file(project).unlink(missing_ok=True)
    return not _left(ctx, store) or _watcher(project) is not None


def watch(ctx: Context) -> dict[str, Any]:
    """Run sync every paperclip_check_minutes, so each ticket follows its issue with no one running it, until stopped
    or nothing is left to follow."""
    store = ctx.require_store()
    project = str(store.project_id)
    live = _watcher(project)
    if live is not None:
        raise Stop(f"The Paperclip watcher already runs here, process {live.get('pid')}.", 'metaform paperclip links')
    _client(ctx)  # no server set is said now, not at the first sync
    home.mkdir_private(run_file(project).parent)
    record = {'pid': os.getpid(), 'project': project, 'folder': str(ctx.folder), 'started': now()}

    def beat() -> None:
        home.write_private(run_file(project), json.dumps({**record, 'beat': time.time()}))

    def stopped(number: int, frame: Any) -> None:
        raise KeyboardInterrupt  # SIGTERM, from a process manager, stops it as Ctrl-C does, so the record goes too

    previous: Any = None
    with contextlib.suppress(ValueError):  # only the main thread can take signals
        previous = signal.signal(signal.SIGTERM, stopped)
    reconfigure = getattr(sys.stdout, 'reconfigure', None)
    if callable(reconfigure):  # its log is a file, so each line is written as it is said, not at exit
        reconfigure(line_buffering=True)
    syncs = 0
    try:
        while True:
            beat()
            done = sync(ctx)
            syncs += 1
            for one in done['changed']:
                ctx.say(f"{now()} {one['issue']}, ticket {one['ticket']}: " + ', '.join(
                    f'{key} {value}' for key, value in one.items() if key not in ('issue', 'ticket')))
            for one in done['failed']:
                ctx.say(f'{now()} failed {one}')
            if _idle(ctx, store, project):
                return {'state': 'idle', 'syncs': syncs}
            due = time.monotonic() + 60 * int(ctx.setting('paperclip_check_minutes') or 10)
            while (left := due - time.monotonic()) > 0:
                beat()
                time.sleep(min(BEAT, left))
    except KeyboardInterrupt:
        pass
    finally:
        with contextlib.suppress(OSError, ValueError):
            if json.loads(run_file(project).read_text(encoding='utf-8')).get('pid') == os.getpid():
                run_file(project).unlink(missing_ok=True)
        if previous is not None:
            with contextlib.suppress(ValueError):
                signal.signal(signal.SIGTERM, previous)
    return {'state': 'stopped', 'syncs': syncs}


def web_started(payload: dict[str, Any], ctx: Context) -> dict[str, Any] | None:
    """Start the watcher of each registered project with paperclip on whose issues a Paperclip agent works are open
    and none runs, wherever the web GUI was started, since it serves every project."""
    started: dict[str, int] = {}
    for project in home.projects():
        try:
            there = context('paperclip', Path(project.path), project=project.project_id)
            if there.store is None or not _on_surface(there, 'paperclip'):
                continue
            pid = _ensure_watcher(there.store, there.folder)
        except (OSError, Stop, StoreError):  # one project's fault leaves the others watched
            continue
        if pid is not None:
            started[project.project_id] = pid
    return {'paperclip': 'watching', 'started': started} if started else None


def _ensure_watcher(store: Store, folder: Path) -> int | None:
    """Start a project's watcher when a link a Paperclip agent works is followed and none runs, detached, so it runs
    on after the call that started it: the process id, or None when there was nothing to start."""
    if _watcher(str(store.project_id)) is not None:
        return None
    if not any(_followed(store, row) for row in _links(store)):
        return None
    log = run_file(str(store.project_id)).with_suffix('.log')
    home.mkdir_private(log.parent)
    options: dict[str, Any] = {'start_new_session': True} if os.name != 'nt' else \
        {'creationflags': getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0) | getattr(subprocess, 'DETACHED_PROCESS', 0)}
    descriptor = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, 'ab') as written:
        process = subprocess.Popen([sys.executable, '-m', 'metaform', 'paperclip', 'watch'], cwd=folder,
                                   stdin=subprocess.DEVNULL, stdout=written, stderr=written, env=child_environment(),
                                   **options)
    return process.pid


def _candidates(store: Store, words: set[str]) -> dict[str, str]:
    """The Addresses whose own words and the purposes of the joins they receive best match an issue's, each with what
    it is for, at most CANDIDATES of them; the purposes are the RE's, by the Join rule. A word counts by how rare it is
    across the map, and one that most Addresses hold, such as `the`, not at all, so long purposes do not crowd out
    the Address the issue names."""
    held: dict[str, list[str]] = {}
    after: str | None = None
    while True:
        page = store.graph(after=after)
        for one in page.elements:
            held.setdefault(one.element.address, [one.element.reading or one.element.short_name or ''])
        for join in page.joins:
            if join.receiver_address:
                held.setdefault(join.receiver_address, ['']).append(' '.join(
                    part for part in (join.purpose, join.ef) if part))
        after = page.next
        if not after:
            break
    texts = {address: set(WORD.findall((address.replace('.', ' ').replace('_', ' ') + ' ' + ' '.join(parts)).lower()))
             for address, parts in held.items()}
    count = len(texts)
    spread: dict[str, int] = {}
    for found in texts.values():
        for word in found:
            spread[word] = spread.get(word, 0) + 1
    scored: list[tuple[float, str]] = []
    for address, found in texts.items():
        weight = sum(math.log((count + 1) / spread[word]) for word in words & found
                     if count < 4 or spread[word] * 2 <= count)
        if weight > 0:
            scored.append((-weight, address))
    return {address: '; '.join(part for part in held[address] if part)[:300] or address
            for _, address in sorted(scored)[:CANDIDATES]}


def _routed(ctx: Context, store: Store, issue: Mapping[str, Any], name: str) -> tuple[str | None, str | None]:
    """The Address Jev chooses for an issue that names none, and the decision kept there, or (None, None) when the
    setting is off, Jev is off or unsure, no Address shares a word with the issue, or it answers none."""
    if not ctx.setting('paperclip_jev_route'):
        return None, None
    title, description = str(issue.get('title') or ''), str(issue.get('description') or '')
    options = _candidates(store, set(WORD.findall(f'{title} {description}'.lower())))
    if not options:
        return None, None
    choices: dict[str, str | None] = {**options, 'none': _said('jev_route/none')}
    state = {'issue': {'title': title, 'description': description[:4000]}, 'addresses': options}
    question, title_of, why = _said('jev_route/ask'), _said('jev_route/title', issue=name), _said('jev_route/why')
    found = jev.pick_one(ctx.folder, question, choices, state, title=title_of, why=why)
    if found is None or not found.sure or found.answer not in options:
        return None, None
    # asked again with the Address to keep it there: the same question over the same state is answered from Jev's
    # cache, never paid twice, and kept as one numbered item, metaform://<address>#<n>
    kept = jev.pick_one(ctx.folder, question, choices, state, title=title_of, why=why, address=str(found.answer))
    return str(found.answer), (kept.item if kept is not None else None)


def _autostarts(ctx: Context) -> bool:
    """Whether dispatch is on this folder's surface with Autostart on, so heartbeat asks it to start what it took."""
    if not _on_surface(ctx, 'dispatch'):
        return False
    try:
        return bool(settings.value('dispatch_autostart', ctx.folder))
    except KeyError:
        return False


def _assigned(client: Client, company: str, agent: str) -> list[dict[str, Any]]:
    """The issues assigned to this agent in todo or in_progress, from the compact inbox Paperclip's heartbeat
    procedure prefers (skills/paperclip/SKILL.md, Step 3), or for a board caller the company's issue list."""
    try:
        found = _objects(client.inbox())
    except PaperclipError as error:
        if error.status != 401:
            raise
        found = _objects(client.issues(company, status='todo,in_progress', assignee=agent))
    return [one for one in found if one.get('id') and one.get('status') in ('todo', 'in_progress')]


def _unrouted(store: Store, client: Client, issue_id: str, name: str) -> None:
    """The one comment on an assigned issue heartbeat cannot take for want of an Address, so the run woken for it
    leaves word on it, as Paperclip asks (server/src/services/heartbeat/queue.ts), and its people know what to add."""
    if _bridged(store, issue_id, comment_id='unrouted'):
        return
    _note(store, client, issue_id, _said('unrouted', issue=name), str(uuid.uuid5(BRIDGE, f'{issue_id}:unrouted')))
    _bridge(store, issue_id, 'unrouted', None, 'note')


def heartbeat(ctx: Context) -> dict[str, Any]:
    """One Paperclip heartbeat of an agent whose adapter is `process` running this command: sync every link, then take
    each issue assigned to this agent whose metaform document names an Address, or whose Address Jev chooses, as a
    ticket there in To do, with a comment and a monitor on the issue, and ask dispatch's autostart to start them when
    Autostart is on. An issue no Address is found for gets one comment saying what to add."""
    store = ctx.require_store()
    agent = os.environ.get('PAPERCLIP_AGENT_ID')
    if not agent:
        raise Stop('This is not a Paperclip heartbeat: PAPERCLIP_AGENT_ID is not set.',
                   'metaform paperclip status, and use its agent_config for a Paperclip agent with the process '
                   'adapter')
    client, company = _client(ctx), _company(ctx)
    reported = sync(ctx)
    inbox = _call('list the assigned issues', _assigned, client, company, agent)
    starts = _autostarts(ctx)
    taken: list[dict[str, Any]] = []
    left: list[dict[str, str]] = []
    for listed in inbox:
        issue_id = str(listed['id'])
        name = str(listed.get('identifier') or issue_id)
        if _link(store, issue_id) is not None:
            continue
        chose: str | None = None
        try:
            issue = {**listed, **_object(client.issue(issue_id))}  # the inbox has no description or policy
            address = _issue_address(client, issue_id)
            if not address:
                address, chose = _routed(ctx, store, issue, name)
            if not address:
                _unrouted(store, client, issue_id, name)
                left.append({'issue': name, 'why': f'its {DOCUMENT} document names no address, and Jev chose none'})
                continue
            checked = _object(client.checkout(issue_id, agent, ('todo', 'backlog', 'blocked', 'in_review',
                                                                'in_progress')))
        except PaperclipError as error:
            left.append({'issue': name, 'why': 'another agent owns it' if error.owned_elsewhere else str(error)})
            continue
        title = str(issue.get('title') or name)
        try:
            record = store.add_work(Node('element', address), None, title=title[:120],
                                    task=str(issue.get('description') or title))
        except StoreError as error:  # the Address holds no element: the claim is given back
            left.append({'issue': name, 'why': str(error)})
            try:
                client.release(issue_id)
            except PaperclipError as failed:
                left.append({'issue': name, 'why': f'it stays checked out here: {failed}'})
            continue
        row: dict[str, Any] = {'issue_id': issue_id, 'identifier': issue.get('identifier'), 'company_id': company,
                               'work_id': record.id, 'address': address, 'works': 'metaform', 'state': 'in_progress',
                               'synced': now()}
        _keep(store, row)
        reference = _reference(store, 'work', record.id, address)
        try:
            _write_document(client, issue_id, address, record.id)
            _note(store, client, issue_id, _said('taken', ticket=reference, address=address,
                                                 state=_said('taken_state/started' if starts else 'taken_state/waiting'),
                                                 minutes=str(ctx.setting('paperclip_check_minutes'))))
            _watch(ctx, client, {**issue, **checked, 'id': issue_id}, reference)
            _comments_in(store, client, row)  # what was said on the issue before, for the agent dispatch starts
        except (Stop, PaperclipError) as error:
            left.append({'issue': name, 'why': f'taken, but {getattr(error, "message", None) or error}'})
        shown = _shown(row)
        if chose:
            shown['address_chosen'] = chose
        taken.append(shown)
    result: dict[str, Any] = {'reported': reported, 'taken': taken, 'left': left}
    if taken:
        result['dispatch'] = _start(ctx) if starts else 'waiting: dispatch_autostart is off, so the tickets wait in ' \
                                                        'To do for the person'
    return result


def _start(ctx: Context) -> Any:
    """Ask dispatch's autostart to start the waiting tickets, through its declared verb, as A2A does; it starts none
    past its slots or its budget, and says so."""
    try:
        started = _object(_verb(ctx, 'dispatch', 'autostart', {}))
    except Stop as error:
        return f'not started: {error.message}'
    return {key: started[key] for key in ('started', 'budget') if started.get(key) is not None}


def links(ctx: Context) -> list[dict[str, Any]]:
    """The Paperclip issues tied to tickets here, as last synced."""
    return [_shown(row) for row in _links(ctx.require_store())]


# ------------------------------------------------------------------------------------------------------ the hooks

def work_read(ctx: Context, record: WorkRecord) -> dict[str, Any] | None:
    """The Paperclip issue a ticket is tied to, under `paperclip` in `map work id=<id>`, BASE-035."""
    if ctx.store is None:
        return None
    row = _link_of_work(ctx.store, record.id)
    return None if row is None else {key: value for key, value in _shown(row).items() if key != 'ticket'}


def module_status(ctx: Context) -> Status:
    if ctx.store is None:
        return Status()
    rows = list(_links(ctx.store))
    open_rows = [row for row in rows if STATES.get(str(row.get('state') or '')) not in vocabulary.TERMINAL]
    return Status(lines=(f'Paperclip: {len(open_rows)} open issues linked',)) if open_rows else Status()


ISSUE = Noun('issue', 'The Paperclip issue, by its id or its identifier, such as PAP-12.')

MODULE = Module(
    id='paperclip',
    summary='Work Paperclip issues as tickets at Addresses, and send tickets to Paperclip\'s agents.',
    purpose='Ties Paperclip issues to tickets at Addresses in the map, both ways: Paperclip\'s agents read the brief '
            'of the Address their issue works on, tickets are sent to Paperclip\'s agents, and an agent Paperclip '
            'runs with the process adapter hands its issues to dispatch, with comments, questions and answers '
            'crossing between the issue and the Address.',
    details='Enable map and paperclip, set paperclip_url and paperclip_company, and put a Paperclip token in the '
            'variable paperclip_token_env names. status checks the connection and prints the process-adapter '
            'configuration for a Paperclip agent that hands its issues to Metaform. An issue\'s Address is named by '
            'its document keyed metaform, a line address: <address>; link and send write it.',
    verbs=(
        Verb('status', status, 'Show the Paperclip server and company used here, whether it answers, and the '
                               'agent configuration that runs heartbeat.',
             effect='read', open_world=True),
        Verb('brief', brief, 'Read the brief of the Address a Paperclip issue works on.',
             nouns=(Noun('issue', 'The Paperclip issue, by id or identifier; when omitted, the gateway\'s '
                                  'x-paperclip-issue-id, then PAPERCLIP_TASK_ID from a local coding agent\'s run.',
                         required=False),),
             effect='read', open_world=True),
        Verb('links', links, 'List the Paperclip issues tied to tickets here.', effect='read'),
        Verb('link', link, 'Tie a Paperclip issue a Paperclip agent works to an Address, with a ticket there that '
                           'follows it.',
             nouns=(ISSUE, Noun('address', 'The Address the issue works on.')),
             examples=(('metaform paperclip link PAP-12 code.alarm.audible',
                        'Tie PAP-12 to code.alarm.audible; its agents read that brief.'),),
             surfaces=('cli',), open_world=True),
        Verb('send', send, 'Send an open ticket to Paperclip as an issue for its agents to work.',
             nouns=(Noun('id', 'The ticket\'s work id.'),
                    Noun('assignee', 'The Paperclip agent, by id or short name; paperclip_assignee when omitted, '
                                     'else Jev\'s choice when Jev is on.', required=False)),
             switches=('paperclip_assignee', 'paperclip_project'),
             details='Over MCP only when the person has turned on paperclip_agents_may_send.',
             open_world=True),
        Verb('sync', sync, 'Bring linked issues and tickets together: ends, comments, questions and answers.',
             surfaces=('cli',), open_world=True),
        Verb('watch', watch, 'Run sync every paperclip_check_minutes until stopped, so tickets follow their issues.',
             details='web start starts it, detached, while issues a Paperclip agent works are open here. Its process '
                     'and last beat are kept in the Metaform home, run/paperclip/<project>.json, and its log beside.',
             surfaces=('cli',), open_world=True),
        Verb('heartbeat', heartbeat, 'Run one Paperclip heartbeat: sync, then take the assigned issues as tickets at '
                                     'their Addresses for dispatch.',
             details='Paperclip runs it as the command of an agent with the process adapter, set as status prints it: '
                     'command the absolute path of metaform, args paperclip and heartbeat, cwd the project folder. '
                     'Paperclip injects PAPERCLIP_AGENT_ID, PAPERCLIP_COMPANY_ID, PAPERCLIP_API_URL, '
                     'PAPERCLIP_API_KEY and PAPERCLIP_RUN_ID. With dispatch_autostart on it asks dispatch to start the '
                     'tickets it took; off, they wait in To do for the person.',
             surfaces=('cli',), open_world=True),
    ),
    subscriptions=(Subscription('web.started', web_started),),
    status=module_status,
    tables=TABLES,
    work_read=work_read,
    settings_category='integrations',
)
