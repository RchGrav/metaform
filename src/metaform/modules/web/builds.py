"""The build panel's endpoints, BASE-060: the four builds from the web GUI, with their progress on the page's stream.

`GET /api/build/options` gives what the panel shows: the builds, the shapes with the modules each ticks, every module
found with whether a remote agent has use for it and whether it is on at home, and the wrapper and onboarding prompts
as the prompt store serves them. `POST /api/build` checks the request, then builds in a thread of its own and answers
at once with the build's id; each stage it starts, and how it ends, is pushed to every open page as an event with the
topic `build`. `GET /api/build/<id>` is one build's state, and `GET /api/build/<id>/download` its file, sent as an
attachment so the browser saves it: the zip of a wheel build, with its README, or a Project Archive. A build is kept
while the server runs; its file also stays under the home's builds folder. A build chooses what it carries and never turns a module on or off at home.
"""
from __future__ import annotations

import os
import secrets
import shutil
import threading
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from metaform import module as chassis
from metaform.module import Stop

if TYPE_CHECKING:
    from .server import Handler, Server

build: Any = chassis.builder()  # reached through the chassis resources, BASE-004
PREFIX = '/api/build'
KINDS = {'archive': ('Project Archive', 'One zip of the project: its data and, when chosen, its files.'),
         'project': ('Project + Metaform',
                     'A zip of the wheel carrying the project, the prompt for a remote agent, and a README.'),
         'installer': ('Metaform Installer',
                       'A zip of the wheel, with the modules chosen, and a README that takes a tester through it.'),
         'full': ('Metaform Full', 'The same zip, its wheel carrying every module found.')}
SHAPES = {'remote': 'Remote agent', 'map': 'Map only', 'home': 'Same as home', 'everything': 'Everything'}
STATES = ('running', 'done', 'failed')


@dataclass
class Job:
    """One build the panel started: where it is, and what it wrote or why it stopped."""
    build_id: str
    kind: str
    project: str | None
    stages: tuple[str, ...]
    stage: str | None = None
    state: str = 'running'
    error: str | None = None
    next: str | None = None
    path: Path | None = None
    prompt: str | None = None

    def event(self) -> dict[str, Any]:
        """What each open page hears as the build moves: the stage it is at and its state, and when it stopped, the
        error and the next step."""
        return {'build_id': self.build_id, 'stage': self.stage, 'stages': list(self.stages), 'state': self.state,
                'error': self.error, 'next': self.next, 'file': self.path.name if self.path is not None else None}

    def status(self) -> dict[str, Any]:
        return {**self.event(), 'kind': self.kind, 'project': self.project, 'prompt': self.prompt,
                'size': self.path.stat().st_size if self.path is not None and self.path.is_file() else None}


_jobs: dict[str, Job] = {}
_lock = threading.Lock()


def answer(handler: Handler, method: str, path: str) -> None:
    """Route one request under /api/build. The server has checked its Host and token already."""
    if method == 'POST':
        return start(handler, path)
    if path == f'{PREFIX}/options':
        return options(handler)
    build_id, _, rest = path[len(PREFIX) + 1:].partition('/')
    with _lock:
        job = _jobs.get(build_id)
        status = job.status() if job is not None else None  # whole under the lock: a finishing build is one change
        file = job.path if job is not None else None
    if job is None or status is None or rest not in ('', 'download'):
        return handler.send(404, {'error': f'No build {build_id or "named"} on this server; a build is kept while '
                                           'the server runs.', 'next': 'Build it again from the panel.'})
    if rest == '':
        return handler.send(200, status)
    return download(handler, status, file)


def options(handler: Handler) -> None:
    try:
        found = build.choices()
        wrapper, onboarding = build.remote_prompts()
        shapes = [{'id': name, 'name': SHAPES[name], 'modules': list(build.shape(name))} for name in build.SHAPES]
    except Stop as error:
        return handler.refuse(error, 400)
    handler.send(200, {
        'kinds': [{'id': kind, 'name': KINDS[kind][0], 'summary': KINDS[kind][1], 'stages': list(build.STAGES[kind]),
                   'takes_project': kind in ('archive', 'project'), 'takes_modules': kind in ('project', 'installer'),
                   'takes_files': kind in ('archive', 'project'), 'takes_prompt': kind == 'project'}
                  for kind in build.KINDS],
        'shapes': shapes,
        'modules': [{'id': choice.id, 'summary': choice.summary, 'remote': choice.remote, 'home': choice.home,
                     'place': choice.place} for choice in found],
        'prompts': {'wrapper': {'name': wrapper.name, 'number': wrapper.number, 'text': wrapper.text},
                    'onboarding': {'name': onboarding.name, 'number': onboarding.number, 'text': onboarding.text}},
        'defaults': {'kind': 'project', 'shape': 'remote', 'files': True}})


def _request(given: dict[str, Any]) -> Any:
    """The build a page asks for, each field checked for its type; what it means is checked by `build.plan`."""
    kind, project, shape, task = given.get('kind'), given.get('project'), given.get('shape'), given.get('prompt')
    modules, files = given.get('modules'), given.get('files', True)
    if not isinstance(kind, str):
        raise Stop('A build names its kind: archive, project, installer or full.', 'send kind')
    for name, value in (('project', project), ('shape', shape), ('prompt', task)):
        if value is not None and not isinstance(value, str):
            raise Stop(f'{name} is text.', f'send {name} as text, or leave it out')
    if modules is not None and (not isinstance(modules, list)
                                or not all(isinstance(item, str) for item in cast(list[Any], modules))):
        raise Stop('modules is a list of module ids.', 'send modules as a list of ids, or leave it out')
    if not isinstance(files, bool):
        raise Stop('files is true or false.', 'send files as true or false')
    return build.Request(kind=kind, project=cast(str | None, project) or None,
                         modules=tuple(cast(list[str], modules)) if modules is not None else None,
                         shape=cast(str | None, shape) or None, files=files, task=cast(str | None, task))


def start(handler: Handler, path: str) -> None:
    """Start one build from the GUI's own page only, with the same check every write of the server makes: the
    request's Origin is the server's own address, and its body is JSON."""
    if not handler.same_origin():
        return handler.send(403, {'error': "A write is taken only from the web GUI's own page."})
    if (handler.headers.get('Content-Type') or '').split(';')[0].strip().lower() != 'application/json':
        return handler.send(415, {'error': 'A write takes a JSON body.'})
    if path != PREFIX:
        return handler.send(404, {'error': f'No such write: {path}.'})
    try:
        body: Any = handler.json_body()
    except ValueError:
        return handler.send(400, {'error': 'The body is not JSON.'})
    given = cast(dict[str, Any], body) if isinstance(body, dict) else {}
    try:
        request = _request(given)
        chosen = build.plan(request)
    except Stop as error:
        return handler.refuse(error, 400)
    job = Job(secrets.token_hex(8), chosen.kind, chosen.project, chosen.stages)
    with _lock:
        _jobs[job.build_id] = job
    server = handler.gui
    threading.Thread(target=_run, args=(server, job, request), name=f'build-{job.build_id}', daemon=True).start()
    handler.send(200, {'build_id': job.build_id, 'stages': list(job.stages)})


def _push(server: Server, job: Job) -> None:
    with _lock:
        event = job.event()
    server.push({'topic': 'build', 'payload': event})


def _run(server: Server, job: Job, request: Any) -> None:
    """Build in this thread, pushing each stage as it starts and then how the build ended. A job changes under the
    lock, and its state last, so no reader sees it done before its file is set."""
    def progress(stage: str) -> None:
        with _lock:
            job.stage = stage
        _push(server, job)

    try:
        with chassis.request_scope(fresh=True):
            chassis.refresh_modules()
            built = build.make(request, None, progress)
    except Stop as error:
        with _lock:
            job.error, job.next, job.state = str(error), error.next_step, 'failed'
    except Exception as error:  # noqa: BLE001  a build that breaks is reported on the page and in the log
        from .server import log
        log(f'Build {job.build_id} failed:\n{traceback.format_exc().rstrip()}')
        with _lock:
            job.error = f'{type(error).__name__}: {error}'
            job.next = f'metaform build kind={job.kind} in a terminal, which prints the whole error'
            job.state = 'failed'
    else:
        with _lock:
            job.path, job.prompt, job.state = built.bundle or built.path, built.prompt, 'done'
    _push(server, job)


def download(handler: Handler, status: dict[str, Any], path: Path | None) -> None:
    """The build's file as an attachment, so the browser saves it, sent from the open file a part at a time, since a
    project wheel carrying the project's files can be large."""
    if status['state'] != 'done' or path is None:
        return handler.send(409, {'error': f'Build {status["build_id"]} is {status["state"]}; it has no file to '
                                           'download.',
                                  'next': 'Wait for the build to finish.' if status['state'] == 'running'
                                  else 'Build it again from the panel.'})
    try:
        held = path.open('rb')
    except OSError:
        return handler.send(404, {'error': f'The file {path} is no longer there.',
                                  'next': 'Build it again from the panel.'})
    with held:
        handler.send_response(200)
        handler.send_header('Content-Type', 'application/zip' if path.suffix == '.zip' else 'application/octet-stream')
        handler.send_header('Content-Length', str(os.fstat(held.fileno()).st_size))
        handler.send_header('X-Content-Type-Options', 'nosniff')
        handler.send_header('Content-Disposition', f'attachment; filename="{path.name}"')
        handler.send_header('Cache-Control', 'no-store')
        handler.end_headers()
        shutil.copyfileobj(held, handler.wfile)
