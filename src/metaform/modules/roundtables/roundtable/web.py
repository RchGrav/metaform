"""The web page: every table, opening one with its seats chosen from what is available, a running table live, its
stats and its data. A plain page of HTML, CSS and JavaScript in `resources/web/`, served by a Starlette app on the
loopback, `web_port` (7436), with `roundtable web` or beside MCP with `roundtable serve --http`.

The page is the person's own: its address carries the web token, `http://127.0.0.1:7436/<token>/`, and nothing
answers without it (see `config.web_token`). Requests are checked for a loopback Host and Origin, as the MCP and A2A
endpoints are. Whoever holds the address chairs every table from it, opened here or over MCP: hold, comment,
continue, advance and end, as the chair's tools do them. A table imported from Metaform is only read.

A running table is followed by server-sent events: `api/tables/<N>/events` says when the table changes, a turn
landed or its state moved, and the page reads what is new with `api/tables/<N>/turns?since=`.
"""
from __future__ import annotations

import asyncio
import hmac
import json
import time
from collections.abc import AsyncIterator
from importlib import resources
from typing import Any, cast

import anyio
from mcp.server.mcpserver.exceptions import ToolError
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, RedirectResponse, Response, StreamingResponse
from starlette.routing import Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send

from . import config, export, harness, openrouter, render, runner, server, stages, store
from .urls import http_base

PAGE = ('index.html', 'app.js', 'style.css')
TYPES = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
         '.css': 'text/css; charset=utf-8'}
MODELS_FOR = 600.0  # seconds OpenRouter's model list is kept before it is read again
LOOK = 1.0  # seconds between looks at a table for its events
_models: dict[str, Any] = {'at': 0.0, 'list': []}


def page(name: str) -> Response:
    held = resources.files(__package__ or 'roundtable') / 'resources' / 'web' / name
    return Response(held.read_bytes(), media_type=TYPES['.' + name.rpartition('.')[2]],
                    headers={'Cache-Control': 'no-store'})


def refused(error: Exception, status: int = 400) -> JSONResponse:
    return JSONResponse({'error': str(error)}, status_code=status)


def number_of(request: Request) -> int:
    return int(request.path_params['number'])


class Token:
    """Nothing answers without the web token as the first part of the path; compared in constant time."""

    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app, self.token = app, token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] == 'http':
            first = str(scope.get('path') or '/').lstrip('/').partition('/')[0]
            if not hmac.compare_digest(first.encode(), self.token.encode()):
                await PlainTextResponse('Not found.', status_code=404)(scope, receive, send)
                return
        await self.app(scope, receive, send)


# ----------------------------------------------------------------------------------------------- tables

def listed(found: dict[str, Any]) -> dict[str, Any]:
    seated = store.seats(int(found['number']))
    return {'number': found['number'], 'subject': found['subject'], 'state': found['state'],
            'reason': found['reason'], 'seats': [str(seat['name']) for seat in seated], 'round': found['round'],
            'rounds': found['rounds'], 'spend': found['spend'], 'spent': round(float(found['spent'] or 0), 6),
            'created': found['created'], 'ended': found['ended'], 'imported': bool(found.get('imported')),
            'runner': 'running' if runner.alive(found) else 'stopped', 'unpaid': bool(found['unpaid']),
            **server.topic_of(found)}


def tables(request: Request) -> Response:
    return JSONResponse({'tables': [listed(one) for one in store.discussions()]})


def table(request: Request) -> Response:
    try:
        found = store.discussion(number_of(request))
    except store.Missing as error:
        return refused(error, 404)
    imported = export.imported_of(found)
    seated = store.seats(int(found['number']))
    turn = server.turn_of(found, seated)
    return JSONResponse({**listed(found), 'opening': found['opening'], 'reporter': found['reporter'],
                         'report': bool(found['report']), 'report_error': found['report_error'],
                         'export': found['export'], 'folder': found['folder'], 'turn_of': turn,
                         'events': server.told(store.events(int(found['number']))),
                         'rules': render.rules([str(seat['name']) for seat in seated], found),
                         'legend': export.legend(found),
                         'seats_detail': [{'position': seat['position'], 'name': seat['name'], 'seat': seat['id'],
                                           'kind': seat['kind'], 'file': export.file_name(seat),
                                           'availability': export.availability(seat), 'gone': seat['gone']}
                                          for seat in seated],
                         **({'imported_from': {key: imported.get(key) for key in ('from', 'number', 'what_happened',
                                                                                    'not_recorded')}}
                            if imported else {})})


def turns(request: Request) -> Response:
    number = number_of(request)
    since = int(request.query_params.get('since') or 0)
    try:
        found = store.discussion(number)
    except store.Missing as error:
        return refused(error, 404)
    rows = export.rows_of(number)
    given = [{**export.scored(row), 'turn': row.get('message_id') or render.turn(int(row['number'])), 'short': render.short(row),
              'kind': row['kind'], 'entered': render.entered(row)} for row in rows if int(row['number']) > since]
    latest = max([int(row['number']) for row in rows if not row.get('unjudged')], default=0)
    return JSONResponse({'turns': given, 'latest': latest, 'state': found['state']})


def topics(request: Request) -> Response:
    """A Roundtable 2 table's topics, each with what its stages gave, as the export holds them."""
    try:
        store.discussion(number_of(request))
        return JSONResponse({'topics': export.topics_of(number_of(request))})
    except store.Missing as error:
        return refused(error, 404)


def stats(request: Request) -> Response:
    try:
        return JSONResponse(export.stats(number_of(request)))
    except store.Missing as error:
        return refused(error, 404)


def context(request: Request) -> Response:
    try:
        return JSONResponse({'turns': export.context(number_of(request), int(request.path_params['position']))})
    except store.Missing as error:
        return refused(error, 404)


def report(request: Request) -> Response:
    try:
        found = store.discussion(number_of(request))
    except store.Missing as error:
        return refused(error, 404)
    if not found['report']:
        return PlainTextResponse(found['report_error'] or 'No report has been written yet.', status_code=404)
    return PlainTextResponse(open(found['report'], encoding='utf-8').read(), media_type='text/markdown; charset=utf-8')


def download(request: Request) -> Response:
    """A self-contained file of a table: its discussion, one seat's file, all in one, the export, or the report."""
    number, what = number_of(request), str(request.path_params['what'])
    try:
        found = store.discussion(number)
        base = f'{number}-{found["subject"]}'
        if what == 'discussion.json':
            body, name = export.discussion_file(number), f'{base}-discussion.json'
        elif what == 'all-in-one.json':
            body, name = export.all_in_one(number), f'{base}-all-in-one.json'
        elif what == 'export.json':
            body, name = export.build(number), f'{base}.json'
        elif what.startswith('seat-') and what.endswith('.json'):
            position = int(what.removeprefix('seat-').removesuffix('.json'))
            seat = next((one for one in store.seats(number) if one['position'] == position), None)
            if seat is None:
                raise store.Missing(f'No seat {position} at roundtable {number}.')
            body, name = export.seat_file(number, position), f'{base}-{export.file_name(seat)}'
        else:
            return refused(ValueError(f'No download {what}.'), 404)
    except (store.Missing, ValueError) as error:
        return refused(error, 404)
    return Response(json.dumps(body, indent=2, ensure_ascii=False) + '\n', media_type='application/json',
                    headers={'Content-Disposition': f'attachment; filename="{name}"'})


def changes(found: dict[str, Any]) -> dict[str, Any]:
    """What the page watches of a table: a change in any of it is an event."""
    rows = store.submissions(int(found['number']), 0)
    from . import topics as next_topics

    return {'state': found['state'], 'reason': found['reason'], 'round': found['round'],
            'topic_selection': next_topics.progress(found) if found['stage'] == 'topic_selection' else None,
            'position': found['position'], 'stage': found['stage'], 'topic': found['topic'],
            'staged': len(store.staged(int(found['number']))) if found['stage'] else 0, 'latest': rows[-1]['number'] if rows else 0,
            'spent': round(float(found['spent'] or 0), 6), 'report': bool(found['report']),
            'runner': 'running' if runner.alive(found) else 'stopped', 'unpaid': bool(found['unpaid']),
            'events': len(store.events(int(found['number']))),
            'seats': [(seat['availability'], seat['gone'], seat['reseated'])
                      for seat in store.seats(int(found['number']))]}


async def events(request: Request) -> Response:
    """Server-sent events of one table: `change` whenever a turn lands or its state moves, a comment line every 15
    seconds to keep the connection open, and an end once the table has ended with its report or export written."""
    number = number_of(request)

    async def stream() -> AsyncIterator[str]:
        last: dict[str, Any] | None = None
        quiet = time.monotonic()
        while not await request.is_disconnected():
            try:
                found = await anyio.to_thread.run_sync(store.discussion, number)
                now = await anyio.to_thread.run_sync(changes, found)
            except store.Missing as error:
                yield f'event: gone\ndata: {json.dumps(str(error))}\n\n'
                return
            if now != last:
                last, quiet = now, time.monotonic()
                yield f'event: change\ndata: {json.dumps(now)}\n\n'
            elif time.monotonic() - quiet > 15:
                quiet = time.monotonic()
                yield ': still here\n\n'
            if found['state'] == 'ended' and (found['export'] or found['report'] or found.get('imported')):
                return
            await asyncio.sleep(LOOK)

    return StreamingResponse(stream(), media_type='text/event-stream',
                             headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})


# ----------------------------------------------------------------------------------------------- the chair

async def chair(request: Request) -> Response:
    """hold, continue, advance, end, reseat or comment, as the chair's tools do them; an imported table is only
    read."""
    number, action = number_of(request), str(request.path_params['action'])
    try:
        found = store.discussion(number)
    except store.Missing as error:
        return refused(error, 404)
    if found.get('imported'):
        return refused(ValueError(f'Roundtable {number} was imported from Metaform; its record is only read.'))
    given: dict[str, Any] = await request.json() if action in ('comment', 'reseat') else {}
    act = {'hold': server.held, 'continue': server.continued, 'advance': server.advanced,
           'end': server.ended}.get(action)
    try:
        if action == 'comment':
            answer = await anyio.to_thread.run_sync(server.commented, found, str(given.get('text') or ''))
        elif action == 'reseat':
            answer = await anyio.to_thread.run_sync(server.reseated, found, str(given.get('seat') or ''))
        elif act is not None:
            answer = await anyio.to_thread.run_sync(act, found)
        else:
            return refused(ValueError(f'No action {action}.'), 404)
    except ToolError as error:
        return refused(error)
    return JSONResponse(answer)


async def open_table(request: Request) -> Response:
    """A table opened from the page, its seats in the order given; the page chairs it."""
    given: dict[str, Any] = await request.json()

    def number(key: str, kind: type) -> Any:
        value = given.get(key)
        return None if value in (None, '') else kind(value)

    topics: Any = given.get('topics')  # absent or null: the Roundtable 2 topics; a list, those; [] none
    try:
        answer = await server.opened(str(given.get('opening') or ''), [str(one) for one in cast(list[Any], given.get('seats') or [])],
                                     str(given.get('subject') or '') or None,
                                     number('spend', float), str(given.get('reporter') or '') or None,
                                     str(given.get('folder') or '') or None, 'web',
                                     [str(one) for one in cast(list[Any], topics)] if isinstance(topics, list) else None,
                                     str(given.get('host') or '') or None, str(given.get('synthesizer') or '') or None,
                                     given.get('seat_mcp'), judging=given.get('judging'))
    except (ToolError, ValueError) as error:
        return refused(error)
    return JSONResponse(answer)


# ----------------------------------------------------------------------------------------------- what can sit

def limits(request: Request) -> Response:
    """What the open form needs: the configured limits a table may lower, the reporter setting, the bar, and
    whether OpenRouter's key is set."""
    return JSONResponse({'judging': bool(config.value('judging')), 'spend': float(config.value('spend')),
                         'reporter': config.value('reporter'), 'keep': config.keep(),
                         'topics': [{'name': one['name'], 'title': one['title']} for one in stages.topics_of(None)],
                         'host': stages.HOST,
                         'openrouter_key': bool(config.openrouter_key()), 'folder': harness.folder_of(None),
                         'peers': sorted(config.peers())})


def agents(request: Request) -> Response:
    """Each harness agent this server starts, whether it is found on this machine, and the models it offered when
    last read over ACP."""
    found: list[dict[str, Any]] = []
    with store.connect() as db:
        updated = {str(row[0]): str(row[1]) for row in db.execute('SELECT agent, updated FROM offered')}
    for agent, command in sorted(config.agents().items()):
        found.append({'agent': agent, 'command': command, 'found': harness.found(agent),
                      'models': store.offered(agent), 'read': updated.get(agent)})
    return JSONResponse({'agents': found})


async def agent_models(request: Request) -> Response:
    """The models an agent offers, read from it now over ACP."""
    agent = str(request.path_params['agent'])
    if agent not in config.agents():
        return refused(ValueError(f'{agent} is not an agent this server starts.'), 404)
    if not harness.found(agent):
        return refused(ValueError(f'{agent} is not found on this machine.'))
    try:
        listed = await harness.offers(agent)
    except harness.Gone as error:
        return refused(error)
    return JSONResponse({'agent': agent, 'models': listed, 'read': store.stamp()})


def models(request: Request) -> Response:
    """OpenRouter's model list, kept for ten minutes; `?fresh=1` reads it again."""
    if request.query_params.get('fresh') or time.time() - _models['at'] > MODELS_FOR or not _models['list']:
        try:
            _models.update(at=time.time(), list=openrouter.models())
        except openrouter.Silent as error:
            return refused(error, 502)
    return JSONResponse({'models': _models['list'], 'read': _models['at']})


def app() -> Starlette:
    """The page and its API under `/<web token>/`, behind the loopback guard and the token."""
    from .a2a_server import Loopback
    token = config.web_token()

    def index(request: Request) -> Response:
        return page('index.html')

    def part(request: Request) -> Response:
        name = str(request.path_params['name'])
        return page(name) if name in PAGE else PlainTextResponse('Not found.', status_code=404)

    def slash(request: Request) -> Response:
        return RedirectResponse(f'/{token}/')

    api = [Route('/tables', tables), Route('/tables/{number:int}', table),
           Route('/tables/{number:int}/turns', turns), Route('/tables/{number:int}/stats', stats),
           Route('/tables/{number:int}/topics', topics),
           Route('/tables/{number:int}/events', events),
           Route('/tables/{number:int}/seats/{position:int}/context', context),
           Route('/tables/{number:int}/report', report),
           Route('/tables/{number:int}/download/{what}', download),
           Route('/tables/{number:int}/{action}', chair, methods=['POST']),
           Route('/open', open_table, methods=['POST']), Route('/limits', limits), Route('/agents', agents),
           Route('/agents/{agent}/models', agent_models, methods=['POST']), Route('/models', models)]
    routes = [Route(f'/{token}', slash),
              Mount(f'/{token}', routes=[Route('/', index), Mount('/api', routes=api), Route('/{name}', part)])]
    return Starlette(routes=routes, middleware=[Middleware(Loopback), Middleware(Token, token=token)])


def address(host: str, port: int) -> str:
    return f'{http_base(host, port)}/{config.web_token()}/'
