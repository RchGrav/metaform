"""Tickets drive CI review and template upkeep through dispatch's declared verbs."""
from __future__ import annotations

import inspect
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from importlib import resources
from pathlib import Path
from typing import Any

from metaform import home, prompt_files
from metaform.data import Node, WorkRecord
from metaform.module import Context, Stop, call, context, surface

from . import checks, repository


def prompt(name: str, **fills: str) -> str:
    return prompt_files.required(resources.files(__package__ or 'metaform.modules.fork'), name, **fills)


async def dispatch(ctx: Context, work_id: str, agent: str) -> Any:
    """Use the public command declaration, including the CLI-only synchronous CI runner."""
    found = next((module for module in surface(ctx.folder) if module.id == 'dispatch'), None)
    if found is None:
        raise Stop('Template upkeep and muster need dispatch enabled.', 'metaform enable dispatch')
    run = next(verb for verb in found.verbs if verb.name == 'run')
    result = run.run(context('dispatch', ctx.folder, project=ctx.project, nouns={'id': work_id, 'agent': agent},
                             switches={'dispatch_worktrees': False}))
    return await result if inspect.isawaitable(result) else result


def ticket(ctx: Context, module: Path, task: str, note: str, *, reuse: bool = False) -> WorkRecord:
    store = ctx.require_store()
    address = f'code.module.{module.name}'
    with store.atomic():
        if not any(layer.name == 'fork' for layer in store.layers(limit=0).results):
            store.layer('fork', 'fork', 'User modules and their upkeep.', mutable=True, hideable=True)
        store.add_element('fork', address, name_length=2, name=module.name, role='SE')
        if reuse:
            current = next((item for item in store.work(node=Node('element', address), limit=0).results
                            if item.note == note), None)
            if current is not None:
                return current
        return store.add_work(Node('element', address), None, note=note, task=task)


def verdict(ctx: Context, work_id: str) -> tuple[bool, str]:
    record = ctx.require_store().ticket(work_id).work
    if not record.done:
        raise Stop(f'Muster did not complete work {work_id}; no wheel was built.',
                   f'metaform map work id={work_id}')
    try:
        data = json.loads(record.resolution or '')
        if type(data['passed']) is not bool or not isinstance(data['reason'], str) or not data['reason'].strip():
            raise ValueError('the verdict needs a boolean passed and a reason')
        return data['passed'], data['reason']
    except (ValueError, KeyError, TypeError):
        raise Stop(f'Muster work {work_id} has no readable verdict; no wheel was built.',
                   f'metaform map work id={work_id}') from None


def pack(folder: Path, environment: dict[str, str]) -> tuple[Path, list[str]]:
    """Build using the running released package, with only reviewed user modules enabled in an isolated home."""
    def command(argv: list[str]) -> str:
        try:
            result = subprocess.run(argv, cwd=folder, env=environment,
                                    capture_output=True, text=True, encoding='utf-8', check=False, timeout=1800)
        except subprocess.TimeoutExpired:
            raise Stop('Wheel building timed out; no artifact was published.', 'metaform help fork wheel') from None
        except OSError as error:
            raise Stop(f'Wheel building could not start: {error}.', 'metaform help fork wheel') from None
        if result.returncode:
            raise Stop(f'Wheel building failed: {result.stderr.strip()}', 'metaform help fork wheel')
        return result.stdout
    def run(*args: str) -> str:
        return command([sys.executable, '-m', 'metaform', *args])
    approved = sorted((Path(environment['METAFORM_HOME']) / 'modules').iterdir())
    needed = sorted({requirement for item in approved for requirement in repository.dependencies(item)})
    if needed:
        command(['uv', 'pip', 'install', '--python', sys.executable, *needed])
    # List includes disabled and unsupported modules too; disable all first so no shipped default enters the wheel.
    for line in run('list', 'modules').splitlines():
        words = line.split()
        if words and repository.IDENTIFIER.fullmatch(words[0]):
            run('disable', words[0])
    for item in approved:
        run('enable', item.name)
    output = run('build')
    paths = [Path(line.removeprefix('Wheel:').strip()) for line in output.splitlines() if line.startswith('Wheel:')]
    if len(paths) != 1 or not paths[0].is_file():
        raise Stop('metaform build returned no wheel.', 'metaform help fork wheel')
    return paths[0], output.splitlines()


def wheel(ctx: Context) -> dict[str, Any]:
    """Checks and agent review precede every build. Agent credentials remain in its inherited environment."""
    secret = str(ctx.setting('fork_secret'))
    if not os.environ.get(secret):
        raise Stop(f'Missing CI secret {secret}: set it as a repository secret; muster is required before a wheel '
                   'can be built.', 'metaform help fork wheel')
    candidates = repository.modules(ctx.folder)
    failures = checks.evidence(ctx.folder, candidates)
    approved: list[Path] = []
    excluded: dict[str, str] = {}
    snapshots = {item.name: repository.digest(item) for item in candidates}
    for item in candidates:
        record = ticket(ctx, item, prompt('muster', module=str(item),
                                         standard=repository.resource('quality.md'),
                                         checks=failures.get(item.name, 'All six matrix jobs passed.')),
                        f'CI muster of {item.name}, source {snapshots[item.name]}.')
        ctx.publish('map.changed', {'project': ctx.project})
        call(dispatch, ctx, record.id, str(ctx.setting('fork_agent')))
        passed, reason = verdict(ctx, record.id)
        reason = failures.get(item.name, reason)
        if passed and item.name not in failures:
            approved.append(item)
        else:
            excluded[item.name] = reason
            print(f'{item.name}: left out: {reason}', file=sys.stderr)
    # Review is read-only. Refuse changed sources, including an earlier candidate altered by a later review.
    if any(repository.digest(item) != snapshots[item.name] for item in candidates):
        raise Stop('A module changed during muster; no wheel was built.', 'metaform help fork wheel')
    if not approved:
        raise Stop('No modules passed muster; no wheel was built.', 'metaform help fork wheel')
    with tempfile.TemporaryDirectory(prefix='metaform-fork-') as temporary:
        build_home = Path(temporary) / 'home'
        for item in approved:
            repository.copy_module(item, build_home / 'modules' / item.name)
        environment = {**os.environ, 'METAFORM_HOME': str(build_home)}
        # The isolated home has no credentials to provision or wheel stage to run.
        environment.pop('METAFORM_WHEEL', None)
        environment.pop(secret, None)
        built, notes = pack(ctx.folder, environment)
        with zipfile.ZipFile(built) as archive:
            carried = {parts[2] for name in archive.namelist() if len(parts := name.split('/')) > 3
                       and parts[:2] == ['metaform', 'modules']}
        if carried != {item.name for item in approved}:
            raise Stop('The built wheel does not hold exactly the approved modules.', 'metaform help fork wheel')
        output = ctx.folder / 'dist' / built.name
        if home.is_home_path(output):
            home.mkdir_private(output.parent)
            home.write_private(output, built.read_bytes())
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(built, output)
    return {'wheel': str(output), 'approved': [item.name for item in approved], 'excluded': excluded, 'notes': notes}


def upkeep(ctx: Context) -> dict[str, Any]:
    releases = repository.entries(repository.template_changelog())
    if not releases:
        return {'tickets': [], 'template_version': None}
    latest = max(releases, key=lambda item: repository.version(item[0]))[0]
    records: list[str] = []
    for item in repository.modules(ctx.folder):
        current = repository.template_version(item)
        newer = [text for number, text in releases if repository.version(number) > repository.version(current)]
        if not newer:
            continue
        record = ticket(ctx, item, prompt('upkeep', module=str(item), current=current, latest=latest,
                                         changelog='\n\n'.join(newer)),
                        f'Template upkeep of {item.name} from {current} to {latest}.', reuse=True)
        records.append(record.id)
        ctx.publish('map.changed', {'project': ctx.project})
        # A caller retries an interrupted ticket but never starts another session on a taken one.
        if not record.done and not record.taken:
            worktree = repository.update_worktree(ctx.folder, record.id)
            ctx.require_store().edit_work(record.id, {'task': prompt(
                'upkeep', module=str(worktree / item.name), current=current, latest=latest,
                changelog='\n\n'.join(newer))})
            call(dispatch, ctx, record.id, str(ctx.setting('fork_agent')))
    return {'tickets': records, 'template_version': latest}
