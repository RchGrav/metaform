"""The MCP server: the roundtable's tools and resources, over stdio or Streamable HTTP on the loopback.

**The chair.** Whoever opens a table chairs it: comment, hold, continue and end are the chair's. MCP's July 2026 core
has no protocol sessions, so `open` returns the table's chair token, the explicit handle a chair passes back as
`chair=`; a call from the same connection that opened the table needs none (the same stdio server process, or the same
`Mcp-Session-Id` from an older HTTP client). Every other caller is refused before anything is written.

**An outside agent seat**, `agent:<name>`, reads its turn with `turn` and answers with `submit`. The first caller that
submits for a seat answers for it from then on: by its connection, or, when it has none, by the seat token its first
`submit` returns.

**Operational events**, credits run out, a hold, a seat lost, degraded or back, the runner stopped, reach the chair
in `status` and `read`, never a seat and never Jev. `status` gives each seat's availability, and `reseat` brings a
seat that is unavailable, or has left, back to the table.

Like every identity check in a local tool, this guards against an agent's mistakes, not an agent set on getting
round it.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import secrets
import shutil
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from metaform import events
from metaform.module import Context as ModuleContext

from . import a2a_server, config, export, harness, peers, render, runner, stages, store
from . import budget as phase_budget
from . import seats as seating
from .names import base as named
from .prompts import said
from .render import LIMIT
from .urls import http_base

WAIT_MOST = 600  # seconds an outside agent seat may wait for its turn in one call
CONNECTION = uuid.uuid4().hex  # this server process: over stdio, one client
READ = ToolAnnotations(read_only_hint=True, open_world_hint=False)
WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False)
PAID = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=True)

server: MCPServer[Any] = MCPServer('roundtable', title='Roundtable', instructions=said('instructions'))


def connection(ctx: Context[Any, Any] | None) -> str | None:
    """The connection a call comes from: this stdio process, or an HTTP client's Mcp-Session-Id; None for a
    stateless HTTP call."""
    if ctx is None:
        return None
    try:
        headers = ctx.headers
    except (LookupError, ValueError, AttributeError):
        headers = None
    if headers is None:
        return f'stdio:{CONNECTION}'
    found = {key.lower(): value for key, value in headers.items()}.get('mcp-session-id')
    return f'http:{found}' if found else None


def table(discussion: int) -> dict[str, Any]:
    try:
        return store.discussion(discussion)
    except store.Missing as error:
        raise ToolError(str(error)) from None


def chaired(discussion: int, chair: str | None, ctx: Context[Any, Any] | None, what: str) -> dict[str, Any]:
    """The table, when the caller is its chair; refused otherwise, before anything is written."""
    found = table(discussion)
    if chair and secrets.compare_digest(chair, str(found['chair_token'])):
        return found
    key = connection(ctx)
    if key and found['chair_key'] and key == found['chair_key']:
        return found
    raise ToolError(f'Only the chair of roundtable {discussion} can {what}: pass chair=<the token open returned>.')


def names(discussion: int) -> list[str]:
    """The seats' short names, in speaking order."""
    return [str(seat['name']) for seat in store.seats(discussion)]


def submitted(row: dict[str, Any]) -> str:
    """What a seat submitted before truncation or removal of its own turn label."""
    return str(row['original'] if row.get('original') is not None else row['text'])


def turn_of(found: dict[str, Any], held: list[dict[str, Any]]) -> str | None:
    """Who the table waits on: the seat whose turn or stage answer it is, the synthesizer or host, or Jev judging a
    topic's round once its last seat has spoken."""
    if found['state'] not in ('running', 'held') or not held or found['stage'] == 'topic_selection':
        return None
    if found['stage'] in ('synthesis', 'host_summary'):
        return str(found['synthesizer' if found['stage'] == 'synthesis' else 'host']['name'])
    if int(found['position']) >= len(held):
        return None
    return str(held[int(found['position'])]['name'])


def topic_of(found: dict[str, Any]) -> dict[str, Any]:
    """Where a table with topics is: its stage, and its open topic by number, name and title, of how many; and its
    host and synthesizer. Nothing for a table that discusses its opening alone."""
    if not found['stage']:
        return {}
    listed = store.topics(int(found['number']))
    at = min(int(found['topic']), len(listed) - 1)
    from . import topics as next_topics

    return {'stage': found['stage'],
            **({'topic_selection': next_topics.progress(found)} if found['stage'] == 'topic_selection' else {}),
            'topic': {'number': at + 1, 'of': len(listed), 'name': listed[at]['name'], 'title': listed[at]['title']},
            'topics': [{'number': int(one['topic']) + 1, 'name': one['name'], 'title': one['title'],
                        **({'advanced_by': one['advanced_by'], 'why': one['why']} if one['advanced_by'] else {})}
                       for one in listed],
            'host': found['host']['id'], 'synthesizer': found['synthesizer']['id'],
            **({'advance_asked': True} if found['advance_asked'] else {})}


def told(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Operational events as the chair reads them."""
    return [{'number': row['number'], 'kind': row['kind'], 'text': row['text'], 'created': row['created'],
             **({'seat': row['seat']} if row['seat'] else {})} for row in rows]


def status_of(found: dict[str, Any]) -> dict[str, Any]:
    held = store.seats(int(found['number']))
    latest = store.submissions(int(found['number']))
    return {'discussion': found['number'], 'subject': found['subject'], 'state': found['state'],
            'reason': found['reason'], **topic_of(found), 'round': found['round'], 'turn_of': turn_of(found, held),
            'latest': latest[-1]['number'] if latest else 0, 'judging': render.judging(found), 'spend': found['spend'],
            'reply_limit': render.reply_limit(found),
            'token_budget': int(render.captured(found).get('token_budget') or 0),
            'token_basis': phase_budget.basis(found),
            'phase_budget': phase_budget.progress(found),
            'spent': round(float(found['spent'] or 0), 4), 'reporter': found['reporter'], 'report': found['report'],
            'export': found['export'], **({'report_error': found['report_error']} if found['report_error'] else {}),
            'runner': 'running' if runner.alive(found) else 'stopped', 'folder': found['folder'],
            **({'unpaid': True} if found['unpaid'] else {}),
            'a2a': {'context_id': found['context_id'], 'task_id': found['task_id']},
            'seats': [{'seat': seat['id'], 'name': seat['name'], 'kind': seat['kind'], 'kept': seat['kept'],
                       'taken': seat['taken'], 'submitted': seat['submitted'],
                       'availability': export.availability(seat), **({'gone': seat['gone']} if seat['gone'] else {}),
                       **({'session': seat['session']} if seat['kind'] == 'acp' else {}),
                       **({'reported_model': seat['reported']} if seat['reported'] else {})} for seat in held],
            'events': told(store.events(int(found['number'])))}


# ----------------------------------------------------------------------------------------------- the chair's tools

async def opened(opening: str | None, seats: list[str] | str, subject: str | None,
                 spend: float | None, reporter: str | None, folder: str | None, chair_key: str | None,
                 topics: list[str] | None = None, host: str | None = None,
                 synthesizer: str | None = None, seat_mcp: Any = None, reply_limit: int = LIMIT,
                 judging: bool | None = None, session: dict[str, Any] | None = None,
                 permissions: dict[str, dict[str, str]] | None = None,
                 token_budget: int = 0, token_basis: str = 'uncached') -> dict[str, Any]:
    """A table opened and its runner started, for `open` and the web page alike; ToolError says why it cannot be.
    With topics, the three Roundtable 2 topics unless others are given, it runs the Roundtable 2 protocol, its
    opening the Roundtable 2 opening unless one is given; with `topics=[]` it discusses its opening alone."""
    if judging is not None and type(judging) is not bool:
        raise ToolError('judging is true or false.')
    if type(reply_limit) is not int or reply_limit < 1:
        raise ToolError('reply_limit is a positive whole number of characters.')
    if type(token_budget) is not int or not 0 <= token_budget <= 9007199254740991:
        raise ToolError('token_budget is a non-negative whole number; zero disables it.')
    if token_basis not in phase_budget.BASES:
        raise ToolError('token_basis is uncached, output, or all.')
    if permissions is not None and (type(permissions) is not dict or any(
                agent not in config.AGENTS or type(values) is not dict or any(
                    key not in ('prompts', 'mode') or type(value) is not str or
                    (key == 'prompts' and value not in ('approve-all', 'approve-reads', 'ask_all'))
                    for key, value in values.items()) for agent, values in permissions.items())):
        raise ToolError('permissions maps ACP agent names to their prompts and mode choices.')
    listed = stages.topics_of(topics)
    opening = (opening or '').strip() or (said('rt2_opening') if listed else '')
    if not opening:
        raise ToolError('A table opens with its opening message.')
    roles: dict[str, dict[str, str]] = {}
    try:
        chosen, notices = seating.chosen(seats)
        writer, notice = seating.reporter(reporter, chosen)
        where = harness.folder_of(folder)
        servers = harness.seat_servers(seat_mcp, chosen)
        if any(one.get('position') is None for one in servers) and any(seat['kind'] != 'acp' for seat in chosen):
            notices.append('seat_mcp reaches the ACP seats only; the other seats stay text-only.')
        if listed:
            roles['host'], roles['synthesizer'], told = stages.roles(host, synthesizer)
            notices += [one for one in told if one not in notices]
    except (seating.Refused, ValueError) as error:
        raise ToolError(str(error)) from None
    if notice:
        notices.append(notice)
    for seat in [*chosen, *roles.values()]:  # each A2A card read now, so a peer that cannot be reached is said first
        if seat['kind'] == 'a2a':
            try:
                seat['label'] = (await peers.card(peers.resolve(seat['agent'] or seat['model']))).name
            except peers.Refused as error:
                raise ToolError(f'{seat["id"]}: {error}') from None
    for one in roles.values():  # a host or synthesizer goes by its name, an A2A one by its card's
        one['name'] = named(one)
    if any(seat['kind'] == 'openrouter' for seat in [*chosen, *roles.values()]) and not config.openrouter_key():
        raise ToolError(f'{config.KEY} is not set where this server runs, and a model seat is called through '
                        'OpenRouter.')
    judging = bool(config.value('judging')) if judging is None else judging
    if judging and not config.openrouter_key():
        raise ToolError(f'{config.KEY} is not set where this server runs, and Jev judges every submission through '
                        'OpenRouter.')
    if session and int(session.get('total') or 1) > 1 and len(chosen) > 1 and not config.openrouter_key():
        raise ToolError(f'{config.KEY} is not set where this server runs, and private next-topic selection '
                        'requires the judging service for a multi-participant session.')
    most_spend = float(config.value('spend'))
    if spend is not None and not 0 <= spend <= most_spend:
        raise ToolError(f'spend is 0 to ${most_spend:g}, the configured most; only the person raises it.')
    token = secrets.token_urlsafe(18)
    number = store.opened({'subject': render.slug(subject or opening), 'opening': opening, 'folder': where,
                           'chair_key': chair_key, 'chair_token': token, 'reporter': writer,
                           'rounds': 0, 'spend': most_spend if spend is None else spend,
                           **({'seat_mcp': servers} if servers else {}), **roles}, chosen, listed, reply_limit, judging,
                          session, permissions, token_budget, token_basis)
    pid = runner.spawn(number)
    found = store.discussion(number)
    return {'discussion': number, 'chair': token, 'a2a': {'context_id': found['context_id'],
                                                          'task_id': found['task_id']}, 'seats': [{'seat': seat['id'], 'name': seat['name']}
                                                            for seat in store.seats(number)],
            'reporter': writer, 'reply_limit': reply_limit,
            'token_budget': token_budget, 'token_basis': token_basis,
            'judging': judging, 'spend': most_spend if spend is None else spend,
            **({'topics': [one['title'] for one in listed], 'host': roles['host']['id'],
                'synthesizer': roles['synthesizer']['id']} if listed else {}),
            'runner': pid, 'privacy': said('privacy'), **({'notices': notices} if notices else {}),
            'next': f'read discussion={number} since=0 to follow it; status discussion={number}'}


@server.tool(annotations=PAID)
async def open(seats: list[str], opening: str | None = None, topics: list[str] | None = None,
               host: str | None = None, synthesizer: str | None = None, subject: str | None = None,
               spend: float | None = None, reporter: str | None = None,
               folder: str | None = None, seat_mcp: list[dict[str, Any]] | None = None,
               ctx: Context[Any, Any] | None = None, reply_limit: int = LIMIT,
               judging: bool | None = None, session: dict[str, Any] | None = None,
               permissions: dict[str, dict[str, str]] | None = None,
               token_budget: int = 0, token_basis: str = 'uncached') -> dict[str, Any]:
    """Open a roundtable with its seats, in speaking order; you chair it.

    Seats: acp:<claude|codex|antigravity>/<model> (the agent on the person's own login through ACP), an OpenRouter model id
    such as deepseek/deepseek-v4.1-flash, a2a:<peer name or card URL> for a remote A2A agent the person names, or
    agent:<name> for an outside agent that submits its own turns.
    topics are discussed one at a time, in order, each followed by a synthesis, every seat's ranking and
    explanations, and the host's summary: 01_WORLD, 02_OBJECTS, 03_COLLABORATION (the default) or any topic's text;
    topics=[] discusses the opening alone. opening defaults to the Roundtable 2 opening when there are topics.
    host summarizes each topic's rankings (default acp:codex/gpt-6 when Codex offers it); synthesizer names its
    ideas (default the host). spend (US dollars) may lower the configured budget.
    judging=false keeps every substantive reply without Jev or its credential. reply_limit sets the maximum characters in each discussion reply (default 512).
    reporter is the seat that writes the report (default: the configured reporter when it is
    seated). folder is where ACP seats read; the server's own folder by default. seat_mcp names MCP servers for the
    ACP seats, [{name, url, headers, seat?}]: given in each seat's session, never a config file, its tools allowed;
    seat (a 1-based place in speaking order) gives one to that seat alone, as for a playground body's own endpoint
    and token. Other seats stay text-only. Returns the table's number and the chair token."""
    return await opened(opening, seats, subject, spend, reporter, folder, connection(ctx), topics, host,
                        synthesizer, seat_mcp, reply_limit, judging, session, permissions, token_budget, token_basis)


# The chair's actions on a table already found to be the caller's: the MCP tools check the chair first, the web page
# is the person's own.

def commented(found: dict[str, Any], text: str) -> dict[str, Any]:
    if found['state'] == 'ended':
        raise ToolError(f'Roundtable {found["number"]} has ended; status shows its report.')
    if not text.strip():
        raise ToolError('A comment says something.')
    store.wait_comment(int(found['number']), text.strip())
    runner.spawn(int(found['number']))
    return {'discussion': found['number'], 'comment': 'waiting for the next gap between turns'}


def held(found: dict[str, Any]) -> dict[str, Any]:
    if found['state'] == 'ended':
        raise ToolError(f'Roundtable {found["number"]} has ended; status shows its report.')
    if found['state'] == 'running' or found['unpaid']:  # a hold for want of credits becomes the chair's own
        found = store.change(int(found['number']), state='held', reason=said('held_by_chair'), unpaid=False)
    return status_of(found)


def continued(found: dict[str, Any], spend: float | None = None) -> dict[str, Any]:
    if spend is not None:
        most = float(config.value('spend'))
        if not 0 <= spend <= most:
            raise ToolError(f'spend must be from 0 to ${most:g}, the configured maximum.')
        found = store.change(int(found['number']), spend=spend)
    if found['state'] == 'ended':
        summaries = [one for one in store.staged(int(found['number']))
                     if one['stage'] == 'host_summary' and one['text']]
        if not summaries:
            raise ToolError('The completed table has no saved host summary to continue from.')
        if runner.alive(found):
            raise ToolError('The previous runner is still closing. Continue once it stops.')
        store.reopen(int(found['number']), str(summaries[-1]['text']))
        found = table(int(found['number']))
    if found['state'] == 'held':
        found = store.change(int(found['number']), state='running', reason=None, unpaid=False)
    runner.spawn(int(found['number']))
    return status_of(found)


def wake_runner(found: dict[str, Any]) -> None:
    """Wake an existing runner's event wait, or start its replacement when none is running."""
    number = int(found['number'])
    events.publish('map.changed', {'tables': ['roundtables.tables'], 'kinds': [f'roundtables:control:{number}']},
                   ModuleContext(module='roundtables', folder=Path(found['folder']), surface='mcp'))
    runner.spawn(number)


def advanced(found: dict[str, Any]) -> dict[str, Any]:
    """Explicitly finish the topic discussion, retaining completed work."""
    if found['state'] == 'ended':
        raise ToolError(f'Roundtable {found["number"]} has ended; status shows its report.')
    if found['stage'] and found['stage'] != 'discussion':
        raise ToolError(said('advance_after_discussion', topic=int(found['topic']) + 1,
                            stage=str(found['stage']).replace('_', ' ')))
    found = store.change(int(found['number']), advance_asked=True, state='running', reason=None, unpaid=False)
    wake_runner(found)
    return status_of(found)


def ended(found: dict[str, Any]) -> dict[str, Any]:
    if found['state'] == 'ended' and found['report'] and not found['report_error']:
        return status_of(found)
    if found['state'] == 'ended' and str(found['reason'] or '') == said('aborted_by_chair'):
        return status_of(found)  # an aborted table stays ended: no runner, no report, nothing spent
    reason = found['reason'] if found['state'] == 'ended' else said('ended_by_chair')
    found = store.change(int(found['number']), state='ending', reason=reason, unpaid=False)
    wake_runner(found)
    return status_of(found)


def reseated(found: dict[str, Any], seat: str) -> dict[str, Any]:
    """A seat brought back: active, its failures forgotten, asked on its next turn; one that left the table, an ACP
    seat whose session ended, starts a fresh session holding the whole discussion."""
    if found['state'] == 'ended':
        raise ToolError(f'Roundtable {found["number"]} has ended; status shows its report.')
    number = int(found['number'])
    wanted = seat.strip().lower()
    held = next((one for one in store.seats(number) if wanted in (str(one['id']).lower(), str(one['name']).lower())),
                None)
    if held is None:
        raise ToolError(f'No seat {seat} at roundtable {number}; status lists them by seat and name.')
    store.reseat(number, int(held['position']), fresh=bool(held['gone']))
    store.event(number, 'seat_restored', said('event_seat_reseated', seat=held['name']), seat=held['id'])
    runner.spawn(number)
    return status_of(store.discussion(number))


@server.tool(annotations=WRITE)
def budget(discussion: int, token_budget: int, chair: str | None = None,
           ctx: Context[Any, Any] | None = None, token_basis: str | None = None) -> dict[str, Any]:
    """Set reported tokens per participant per panel and collaboration; zero disables it.

    Counters reset when each panel or collaboration starts, not when this limit changes.
    Warn at 50% and 80%, request closing statements at 100%, and advance at 120%.
    token_basis may explicitly select uncached input plus output, output only, or all processed tokens.
    Changing it requires a stopped runner and recounts the current phase from saved usage. Omitting it preserves it.
    """
    found = chaired(discussion, chair, ctx, 'set its token budget')
    if type(token_budget) is not int or not 0 <= token_budget <= 9007199254740991:
        raise ToolError('token_budget is a non-negative whole number; zero disables it.')
    if token_basis is not None and token_basis not in phase_budget.BASES:
        raise ToolError('token_basis is uncached, output, or all.')
    if found['state'] in ('ending', 'ended'):
        raise ToolError('This roundtable is ending or ended; its token budget cannot be changed.')
    if runner.alive(found) and found.get('budget_runner') != found['runner']:
        raise ToolError('Hold this roundtable, wait until its runner stops, then Continue to load token-budget support.')
    if token_basis is not None and token_basis != phase_budget.basis(found) and runner.alive(found):
        raise ToolError('Hold this roundtable and wait until its runner stops before changing token accounting.')
    try:
        found = phase_budget.configure(found, token_budget, token_basis)
    except ValueError as error:
        raise ToolError(str(error)) from None
    events.publish('map.changed', {'tables': ['roundtables.tables'],
                                   'kinds': [f'roundtables:control:{discussion}']},
                   ModuleContext(module='roundtables', folder=Path(found['folder']), surface='mcp'))
    if found['state'] == 'running':
        runner.spawn(discussion)
    return status_of(found)


@server.tool(annotations=WRITE)
def comment(discussion: int, text: str, chair: str | None = None,
            ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """As the chair, comment at a table: entered inline at the next gap between turns, unjudged, with no limit."""
    return commented(chaired(discussion, chair, ctx, 'comment'), text)


@server.tool(annotations=WRITE)
def hold(discussion: int, chair: str | None = None, ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """As the chair, hold a table after the turn in flight, until it is continued."""
    return held(chaired(discussion, chair, ctx, 'hold it'))


@server.tool(name='continue', annotations=PAID)
def resume(discussion: int, chair: str | None = None, ctx: Context[Any, Any] | None = None,
           spend: float | None = None) -> dict[str, Any]:
    """As the chair, continue a held table, judging first a submission Jev left unjudged."""
    return continued(chaired(discussion, chair, ctx, 'continue it'), spend)


@server.tool(annotations=PAID)
def advance(discussion: int, chair: str | None = None, ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """As the chair, end discussion at the next gap: its synthesis, every seat's
    ranking and explanations and the host's summary follow, then the next topic."""
    return advanced(chaired(discussion, chair, ctx, 'advance its topic'))


@server.tool(annotations=PAID)
def reseat(discussion: int, seat: str, chair: str | None = None,
           ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """As the chair, bring a seat back to the table, by its seat id or name: one degraded or unavailable after its
    failures, or out of credits, is asked again on its next turn; one that left, an ACP seat whose session ended,
    starts a fresh session holding the whole discussion."""
    return reseated(chaired(discussion, chair, ctx, 'reseat its seats'), seat)


@server.tool(annotations=WRITE)
def permit(discussion: int, request: str, option: str) -> dict[str, Any]:
    """Return the person's selected ACP permission option to the waiting agent."""
    from . import permissions
    try:
        answer = permissions.answer(discussion, request, option)
    except ValueError as error:
        raise ToolError(str(error)) from None
    found = table(discussion)
    events.publish('map.changed', {'tables': ['roundtables.permissions'], 'kinds': [permissions.topic(discussion)]},
                   ModuleContext(module='roundtables', folder=Path(found['folder']), surface='mcp'))
    return answer


@server.tool(annotations=WRITE)
def abort(discussion: int, chair: str | None = None, ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """As the chair, abort a table at once: it is ended now, its runner is stopped and every seat's agent with it,
    so the turn in flight ends too, no report is written and nothing more is spent."""
    found = chaired(discussion, chair, ctx, 'abort it')
    from . import permissions
    permissions.cancel_all(discussion)
    if found['state'] != 'ended':
        found = store.change(int(found['number']), state='ended', reason=said('aborted_by_chair'),
                             ended=store.stamp(), unpaid=False)
    runner.stop_runner(int(found['number']))  # hard stop: the turn in flight and every seat end now
    return {**status_of(found), 'archived': str(put_aside(int(found['number'])))}


def put_aside(number: int) -> Path:
    """An aborted table's files moved out of the engine's live folders into one folder, aborted/<number>, for the
    caller to archive: its report, export and record, its seats' folders and its logs."""
    home = config.home()
    held = home / 'aborted' / str(number)
    held.mkdir(parents=True, exist_ok=True)
    for path in [*config.reports().glob(f'{number}-*'), *(home / 'seats').glob(f'{number}-*'),
                 *(home / 'logs').glob(f'table-{number}.log'), *(home / 'logs').glob(f'table-{number}-*.log')]:
        with contextlib.suppress(OSError):
            shutil.move(str(path), str(held / path.name))
    return held


@server.tool(annotations=PAID)
def end(discussion: int, chair: str | None = None, ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """As the chair, end a table: the reporter seat writes its report and the record is exported. On an ended table
    whose report failed, asks for it again."""
    return ended(chaired(discussion, chair, ctx, 'end it'))


# ----------------------------------------------------------------------------------------------- reading a table

@server.tool(annotations=READ)
def status(discussion: int) -> dict[str, Any]:
    """A table: its state, whose turn it is, its limits and spend, each seat's kept against taken, the report, and
    its operational events: credits, holds, seats lost, degraded or back, the runner stopped."""
    return status_of(table(discussion))


@server.tool(name='list', annotations=READ)
def list_tables() -> dict[str, Any]:
    """Every table, newest first."""
    return {'discussions': [{'discussion': row['number'], 'subject': row['subject'], 'state': row['state'],
                             'created': row['created'], 'report': row['report']} for row in store.discussions()]}


@server.tool(annotations=READ)
def read(discussion: int, since: int = 0, events_since: int = 0) -> dict[str, Any]:
    """Every turn after a cursor, as the seats see it, with its nouls, outcome and what it cost; a vetoed turn with
    its text too; and the operational events after events_since, which no seat sees. Pass latest back as since=
    and latest_event as events_since= to read only what is new."""
    found = table(discussion)
    rows = store.submissions(discussion, since)
    events = store.events(discussion, events_since)
    turns = [{'number': row['number'], 'turn': row.get('message_id') or render.turn(int(row['number'])),
              **({'message_id': row['message_id']} if row.get('message_id') else {}), 'seat': render.who(row),
              **({'topic': int(row['topic']) + 1} if row['topic'] is not None else {}),
              'outcome': render.outcome(row), 'shown': render.entry(row, links=True),
              **({'truncated': True} if row['truncated'] else {}),
              **({'text': row['text']} if not render.entered(row) and row['text'] else {}),
              'nouls': store.nouls(row), 'link': render.link(discussion, int(row['number'])),
              **{key: row[key] for key in ('cached_tokens', 'prompt_tokens', 'cost', 'jev_cost')
                 if row[key] is not None}} for row in rows]
    return {'discussion': discussion, 'state': found['state'], 'reason': found['reason'], **topic_of(found),
            'round': found['round'], **({'opening': found['opening']} if since == 0 else {}), 'turns': turns,
            'latest': rows[-1]['number'] if rows else since, 'events': told(events),
            'latest_event': events[-1]['number'] if events else events_since}


@server.tool(annotations=READ)
def review(discussion: int) -> str:
    """The full review: the four questions and the array's order, then every submission with its four nouls."""
    return render.review(table(discussion), store.submissions(discussion), names(discussion),
                         store.topics(discussion))


@server.tool(annotations=READ)
def submission(discussion: int, number: int) -> str:
    """The text one seat submitted, whole even when it was truncated, and nothing else."""
    try:
        return submitted(store.submission(discussion, number))
    except store.Missing as error:
        raise ToolError(str(error)) from None


# ----------------------------------------------------------------------------------------------- an outside agent seat

def agent_seat(discussion: int, seat: str) -> tuple[dict[str, Any], dict[str, Any]]:
    found = table(discussion)
    try:
        named = seating.parse(seat)['id']
    except seating.Refused as error:
        raise ToolError(str(error)) from None
    held = next((one for one in store.seats(discussion) if one['id'] == named), None)
    if held is None or held['kind'] != 'agent':
        raise ToolError(f'{named} is not an agent seat at roundtable {discussion}.')
    return found, held


def answers_for(held: dict[str, Any], who: str | None) -> None:
    if held['owner'] and held['owner'] != who:
        raise ToolError(f'{held["id"]} is answered by another agent; pass the seat_token its first submit returned.')


def mine(held: dict[str, Any]) -> bool:
    return bool(held['pending']) and not held['reply']


@server.tool(annotations=READ)
async def turn(discussion: int, seat: str, wait: int = 0, seat_token: str | None = None,
               ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """As an outside agent seat (agent:<name>), read your turn: what happened since your last reply. With wait, up
    to that many seconds (at most 600) for your turn to come."""
    who = f'token:{seat_token}' if seat_token else connection(ctx)
    found, held = agent_seat(discussion, seat)
    answers_for(held, who)
    end_at = time.time() + min(max(wait, 0), WAIT_MOST)
    while not mine(held) and found['state'] != 'ended' and time.time() < end_at:
        await asyncio.sleep(0.5)
        found, held = agent_seat(discussion, seat)
    if not mine(held):
        return {'discussion': discussion, 'seat': held['id'], 'your_turn': False, 'state': found['state']}
    return {'discussion': discussion, 'seat': held['id'], 'your_turn': True, 'turn': held['pending'],
            'next': f'submit discussion={discussion} seat={held["id"]} text=<at most {render.reply_limit(found)} characters>'}


@server.tool(annotations=WRITE)
def submit(discussion: int, seat: str, text: str, seat_token: str | None = None,
           ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
    """As an outside agent seat, submit your turn within the discussion's reply_limit characters.
    Anything longer is truncated to that limit, and only the truncated part is judged."""
    who = f'token:{seat_token}' if seat_token else connection(ctx)
    found, held = agent_seat(discussion, seat)
    answers_for(held, who)
    if not mine(held):
        raise ToolError(f'It is not {held["id"]}\'s turn at roundtable {found["number"]}; turn wait=300 waits for it.')
    text = text.strip()
    if not text:
        raise ToolError('A submission says something.')
    minted = None
    if who is None:
        minted = secrets.token_urlsafe(18)
        who = f'token:{minted}'
    given = {'seat_token': minted} if minted else {}
    store.seat_change(discussion, held['position'], reply={'text': text}, owner=held['owner'] or who)
    return {'discussion': discussion, 'seat': held['id'], 'submitted': True, **given,
            **({'truncated_to': render.reply_limit(found)} if len(text) > render.reply_limit(found) else {})}


# ----------------------------------------------------------------------------------------------- resources

@server.resource('roundtable://discussion{discussion}/submission{number}', name='submission',
                 title='A roundtable submission', mime_type='text/plain',
                 description='The text a seat submitted, and nothing else.')
def submission_resource(discussion: str, number: str) -> str:
    return submitted(store.submission(int(discussion), int(number)))


@server.resource('roundtable://discussion{discussion}/review', name='review', title='A roundtable review',
                 mime_type='text/plain', description='Every submission in short form with its four nouls '
                 '[new, valuable, relevant, keep] and its link.')
def review_resource(discussion: str) -> str:
    return render.review(store.discussion(int(discussion)), store.submissions(int(discussion)), names(int(discussion)),
                         store.topics(int(discussion)))


@server.resource('roundtable://discussion{discussion}/export', name='export', title='A roundtable export',
                 mime_type='application/json', description='The whole record as JSON: the discussion, seats with '
                 'their reported models, submissions with outcome, nouls and cache and cost per turn, and a summary.')
def export_resource(discussion: str) -> str:
    return json.dumps(export.build(int(discussion)), indent=2, ensure_ascii=False)


def serve(http: bool = False, host: str | None = None, port: int | None = None) -> None:
    """MCP over stdio; or, with `http`, MCP at /mcp and A2A beside it on the same loopback port: the Agent Card at
    /.well-known/agent-card.json, JSON-RPC at /a2a and HTTP+JSON under /a2a/rest; and the web page on `web_port`."""
    if not http:
        server.run('stdio')
        return
    import uvicorn

    from . import web
    host = loopback(host)
    port = port or int(config.value('port'))
    app = server.streamable_http_app(host=host)
    app.router.routes.extend(a2a_server.routes(host, port))
    if not config.a2a_tokens():
        print(f'A2A: no token is set in {config.value("a2a_tokens")}, so only the public Agent Card answers.',
              file=sys.stderr)
    web_port = int(config.value('web_port'))
    base = http_base(host, port)
    print(f'MCP at {base}/mcp; A2A card at {base}/.well-known/agent-card.json; '
          f'the web page at {web.address(host, web_port)}', file=sys.stderr)

    async def both() -> None:
        await asyncio.gather(uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level='warning')).serve(),
                             web_server(host, web_port).serve())
    asyncio.run(both())


def loopback(host: str | None) -> str:
    found = host or config.value('host')
    if found not in ('127.0.0.1', 'localhost', '::1'):
        raise SystemExit('roundtable serves HTTP on the loopback only: 127.0.0.1, localhost or ::1.')
    return found


def web_server(host: str, port: int) -> Any:
    """The web page's server; a stream left open delays its stop by two seconds at most."""
    import uvicorn

    from . import web
    return uvicorn.Server(uvicorn.Config(web.app(), host=host, port=port, log_level='warning',
                                         timeout_graceful_shutdown=2))


def serve_web(host: str | None = None, port: int | None = None) -> None:
    """The web page alone, on `web_port`."""
    from . import web
    host = loopback(host)
    port = port or int(config.value('web_port'))
    print(f'The web page at {web.address(host, port)}', file=sys.stderr)
    web_server(host, port).run()
