"""Source placement: tree-sitter and the existing functional map place each source function on the map."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from dataclasses import replace
from importlib import resources
from pathlib import Path
from typing import Any, cast

from metaform import home, prompt_files
from metaform.data import Store
from metaform.module import Context, Module, Noun, Provides, Stop, Subscription, Verb, child_environment, provided

from .parser import SUFFIXES, parse

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ('tree-sitter>=0.25,<0.26', 'tree-sitter-javascript>=0.25,<0.26')
SHIPS_DISABLED = False
REMOTE_AGENT = False  # intake prepares project knowledge before work is assigned
CONFIDENCE = 90  # a function is placed only at this percentage or above; the rest go to the remainder ticket


def intake(ctx: Context) -> str:
    """Serve the authored procedure and optional task context without recording anything."""
    package = resources.files(__name__)
    procedure = prompt_files.required(package, 'intake')
    association = ctx.nouns.get('association', 'agent')
    if association not in ('agent', 'jev'):
        raise Stop('association must be agent or jev.', 'metaform help source_placement intake')
    confidence = _confidence(ctx)
    if association == 'jev':
        procedure += '\n\n' + prompt_files.required(package, 'jev', confidence=str(confidence))
    text = ctx.nouns.get('text')
    if text:
        given = prompt_files.required(package, 'input', text=json.dumps(text, ensure_ascii=False))
        return procedure + '\n\n' + given
    return procedure


def _confidence(ctx: Context) -> int:
    value = ctx.nouns.get('confidence', CONFIDENCE)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
        raise Stop('confidence must be an integer percentage from 0 to 100.', 'metaform help source_placement')
    return value


def associate(ctx: Context) -> object:
    """Classify code against provider categories, leaving recording to the intake agent."""
    from . import jev
    confidence = _confidence(ctx)
    candidates = ctx.nouns.get('candidates')
    if candidates is None:
        providers: dict[str, list[str]] = {}
        for purpose in ctx.require_store().layer_graph('base').joins:
            for provider in purpose.elements:
                if provider.address and not jev.eligible_provider(provider.address):
                    continue
                if not provider.address or not purpose.ef:
                    raise Stop('A provider category is missing its namespace or EF.',
                               'Read and complete the current base before classifying code.')
                descriptions = providers.setdefault(provider.address, [])
                if purpose.ef not in descriptions:
                    descriptions.append(purpose.ef)
        candidates = {f'category_{index:03d}': {'provider': address, 'ef': descriptions}
                      for index, (address, descriptions) in enumerate(sorted(providers.items()))}
    if isinstance(candidates, dict):
        filtered: dict[str, Any] = {}
        for key, value in cast(dict[str, Any], candidates).items():
            address = cast(dict[str, Any], value).get('provider') if isinstance(value, dict) else None
            if isinstance(address, str) and not jev.eligible_provider(address):
                continue
            filtered[key] = value
        candidates = filtered
    try:
        result = jev.associate(ctx.nouns.get('items'), candidates, jev.configured(ctx.folder),
                               threshold=confidence / 100)
        return {**result, 'categories': candidates}
    except (ValueError, RuntimeError) as error:
        raise Stop(str(error), 'metaform help source_placement associate') from None


def _bound(ctx: Context) -> Context:
    base = ctx.nouns.get('base')
    if base:
        ctx = replace(ctx, store=Store(ctx.require_store().project_id, base=base, module='source_placement'))
        ctx.require_store().bound_base()
    return ctx


def extend(ctx: Context) -> object:
    """Prepare or resume an intake's placements and hand remaining evidence to ordinary work."""
    from . import pipeline
    from .remainder import start_remainder
    ctx = _bound(ctx)
    run_id = ctx.nouns.get('run')
    if not run_id:
        prepared = pipeline.prepare(ctx, paths=ctx.nouns.get('paths'), exclude=ctx.nouns.get('exclude'),
                                    confidence=_confidence(ctx))
        run_id = prepared.get('run_id')
        if not run_id:
            return prepared
    result = pipeline.execute(ctx, run_id, base_id=ctx.nouns.get('base'))
    if result.get('pending', 0):
        result['follow_up'] = start_remainder(ctx, run_id, base_id=result['base_id'])
    return result


def status(ctx: Context) -> object:
    from . import pipeline
    return pipeline.status(_bound(ctx), ctx.nouns['run'], base_id=ctx.nouns.get('base'))


def pending(ctx: Context) -> object:
    from . import pipeline
    return pipeline.pending(_bound(ctx), ctx.nouns['run'], base_id=ctx.nouns.get('base'),
                            offset=ctx.nouns.get('offset', 0), limit=ctx.nouns.get('limit', 25))


def resolve(ctx: Context) -> object:
    from . import pipeline
    return pipeline.resolve(_bound(ctx), ctx.nouns['run'], base_id=ctx.nouns.get('base'),
                            item=ctx.nouns['item'], provider=ctx.nouns['provider'], why=ctx.nouns['why'])


def runs_root(project_id: str) -> Path:
    """Where a project's placement runs and launch receipts are kept: in the Metaform home beside the project's
    stores, never in the person's project folder. Made 0700, as the home's other folders are."""
    folder = home.project_folder(project_id)
    if folder is None:
        raise ValueError(f'No project {project_id} is registered.')
    root = folder / 'source_placement'
    home.mkdir_private(root)
    return root


def finished(payload: dict[str, Any], ctx: Context) -> dict[str, Any]:
    """Finish the intake independently of the optional, durable classification process, which starts only when the
    person has turned jev on."""
    from . import jev
    if not payload.get('code'):
        return {'status': 'skipped', 'reason': 'The intake does not contain code.'}
    try:
        jev.configured(ctx.folder)
    except ValueError as error:
        return {'status': 'skipped', 'reason': str(error)}
    if not provided(ctx.folder, 'code.inventory'):
        return {'status': 'skipped', 'reason': 'The code inventory provider is unavailable.'}
    project = str(payload['project'])
    base = str(payload['base'])
    store = Store(project, base=base, module='source_placement')
    folder = Path(store.project().path)
    logs = runs_root(project) / 'launches'
    home.mkdir_private(logs)
    receipt = logs / f'{uuid.uuid4().hex}.json'
    command = [sys.executable, '-m', 'metaform', 'source_placement', 'extend', f'base={base}',
               '--project', project, '--json']
    options: dict[str, Any] = ({'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
                               if os.name == 'nt' else {'start_new_session': True})
    try:
        descriptor = os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, 'wb') as output:
            child = subprocess.Popen(command, cwd=folder, env=child_environment(), stdin=subprocess.DEVNULL,
                                     stdout=output, stderr=subprocess.STDOUT, **options)
    except OSError as error:
        return {'status': 'skipped', 'reason': str(error)}
    return {'status': 'running', 'pid': child.pid, 'base': base, 'result': str(receipt)}


OLD_ID = 'refactor'  # this module's id until Rich renamed it, 2026-10-14: it places code at the map, it does not refactor


def _renamed(key: str, member: Any) -> Any:
    if key == 'jev_decisions' and isinstance(member, str) and member.startswith(f'{OLD_ID}.'):
        return f'source_placement.{member[len(OLD_ID) + 1:]}'
    return 'source_placement' if member == OLD_ID else member


def migrate_names(ctx: Context | None = None) -> list[str]:
    """Once per home, as the module starts: what was stored under the old id `refactor` is kept under
    `source_placement`, Rich 2026-10-14. That is the module's enabled state; the members of the modules, layers and
    jev_decisions settings, and of aliases, that name it; the refactor layer of every base, renamed in place with its
    items. A marker in the home lists what moved; a scope or base that cannot be read is said, and the migration runs
    again at the next start. A project folder's old run folder is renamed in place at every start (`_rename_runs`),
    since that folder is shared by every home that registers it. A run whose base is gone is removed at every start
    (`_drop_orphaned_runs`)."""
    del ctx
    moved = _rename_runs() + _drop_orphaned_runs()
    marker = home.home() / 'migrated-source-placement'
    if marker.exists():
        return moved
    said: list[str] = moved
    unread = False
    state = home.module_state(OLD_ID)
    if state is not None:
        if home.module_state('source_placement') is None:
            home.set_module_state('source_placement', state)
            said.append(f'module state: {"enabled" if state else "disabled"}')
        home.set_module_state(OLD_ID, None)
    projects = home.projects()
    for scope in dict.fromkeys(['global', *(home.path_key(record.path) for record in projects)]):
        try:
            with home.settings_db(scope) as db:
                rows = db.execute("SELECT scope, owner, key, value FROM settings WHERE key IN ('modules', 'layers', "
                                  "'jev_decisions') ORDER BY scope, owner, key, position").fetchall()
                aliases = (db.execute('SELECT path_key, name, module FROM aliases ORDER BY path_key, name, position')
                           .fetchall() if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND "
                                                     "name='aliases'").fetchone() else [])
        except Exception as error:  # noqa: BLE001  a scope that cannot be read is said and left for the next start
            said.append(f'{scope}: not read, {error}')
            unread = True
            continue
        held: dict[tuple[str, str, str], list[Any]] = {}
        for found_scope, owner, key, raw in rows:
            held.setdefault((str(found_scope), str(owner), str(key)), []).append(json.loads(raw))
        for (found_scope, owner, key), members in held.items():
            moved = [_renamed(key, member) for member in members]
            if moved != members:
                home.save(found_scope, owner, key, moved)
                said.append(f'{found_scope}: {key} = {", ".join(map(str, moved))}')
        named: dict[tuple[str, str], list[str]] = {}
        for path, name, module in aliases:
            named.setdefault((str(path), str(name)), []).append(str(module))
        for (path, name), modules in named.items():
            if OLD_ID in modules:
                home.save_alias(Path(path), name, [_renamed('modules', module) for module in modules])
                said.append(f'{path}: alias {name}')
    for record in projects:
        for base in home.bases(record.project_id):
            try:
                store = Store(record.project_id, base=base.id, module='source_placement')
                if any(layer.name == OLD_ID and layer.module == OLD_ID for layer in store.layers(limit=0).results):
                    notices = store.rename_layer(OLD_ID, 'source_placement', 'source_placement').notices
                    said.append(f'{record.project_id} {base.name}: layer refactor '
                                + (notices[0].message if notices else 'is now source_placement'))
                    unread = unread or bool(notices)
            except Exception as error:  # noqa: BLE001  a base that cannot be read is said and left for the next start
                said.append(f'{record.project_id} {base.name}: not read, {error}')
                unread = True
    if not unread:  # the home is its owner's alone, so the marker is made 0600
        with os.fdopen(os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w', encoding='utf-8') as out:
            out.write('\n'.join(said) + '\n')
    return said


def _rename_runs() -> list[str]:
    """At every start: what this module kept in a project folder's .metaform/refactor before the rename is renamed in
    place to .metaform/source_placement, where pipeline._directory still reads and resumes it. The project folder is
    shared by every home that registers it, so nothing leaves the folder and no home keeps a marker: the rename gives
    the same result whichever home runs it. A name already under source_placement is left where it is and said. A
    renamed run that can still place functions has a saved threshold below CONFIDENCE raised to it, so a resumed run
    never places a function under 90%."""
    said: list[str] = []
    for record in home.projects():
        hidden = Path(record.path) / '.metaform'
        old, new = hidden / OLD_ID, hidden / 'source_placement'
        if not old.is_dir():
            continue
        try:
            if home.is_home_path(new):
                home.mkdir_private(new)
            else:
                new.mkdir(exist_ok=True)
            for entry in sorted(old.iterdir()):
                target = new / entry.name
                if target.exists():
                    said.append(f'{entry}: left in place, {target} already exists')
                    continue
                entry.rename(target)
                said.append(f'{entry}: now {target}')
                if re.fullmatch(r'[a-f0-9]{24}', entry.name) and (target / 'run.json').is_file():
                    _raise_threshold(target)
            if not any(old.iterdir()):
                old.rmdir()
        except (OSError, ValueError) as error:  # a folder that cannot be read or renamed is said; the next start retries
            said.append(f'{old}: not renamed, {error}')
    return said


def _drop_orphaned_runs() -> list[str]:
    """At every start: a run in a registered project's home folder whose base the project no longer has can never
    resume, so it is removed with the launch receipts naming that base. A clear deletes every base and a remove deletes
    them with the registration; registering the source again takes the same home folder back, and this is what keeps
    those runs from coming back with it. Only the home's own folder is touched, never the project folder another home
    may share. An entry that cannot be read or removed is said and left for the next start."""
    said: list[str] = []
    for record in home.projects():
        folder = home.project_folder(record.project_id)
        root = folder / 'source_placement' if folder is not None else None
        if root is None or not root.is_dir():
            continue
        bases = {base.id for base in home.bases(record.project_id)}
        for entry in sorted(root.iterdir()):
            if not (entry.is_dir() and re.fullmatch(r'[a-f0-9]{24}', entry.name)):
                continue
            try:
                base = json.loads((entry / 'run.json').read_text())['base_id']
                if base in bases:
                    continue
                shutil.rmtree(entry)
                said.append(f'{entry}: removed, its base {base} is gone')
            except (OSError, ValueError, KeyError, TypeError) as error:
                said.append(f'{entry}: left, {error}')
        launches = root / 'launches'
        for receipt in sorted(launches.glob('*.json')) if launches.is_dir() else []:
            try:
                written: Any = json.loads(receipt.read_text())
                base = cast(dict[str, Any], written).get('base_id') if isinstance(written, dict) else None
                if base is None or base in bases:
                    continue
                receipt.unlink()
                said.append(f'{receipt}: removed, its base {base} is gone')
            except (OSError, ValueError) as error:
                said.append(f'{receipt}: left, {error}')
    return said


def _raise_threshold(run: Path) -> None:
    """A run from before the rename was prepared at 83%. One still able to place functions, not yet in review or
    complete, keeps its run id and evidence and is raised to CONFIDENCE; a finished run keeps the threshold its counts
    and placements were made at."""
    if json.loads((run / 'run.json').read_text()).get('status') in ('review', 'complete'):
        return
    for name in ('run.json', 'input.json'):
        path = run / name
        if not path.is_file():
            continue
        saved: Any = json.loads(path.read_text())
        if isinstance(saved, dict) and cast(dict[str, Any], saved).get('threshold', 1) < CONFIDENCE / 100:
            saved['threshold'] = CONFIDENCE / 100
            if home.is_home_path(path):
                home.write_private(path, json.dumps(saved, ensure_ascii=False))
            else:
                path.write_text(json.dumps(saved, ensure_ascii=False))


RUN_NOUNS =(Noun('run', 'The saved placement run ID.'),
             Noun('base', 'The intake base ID the run belongs to.', required=False))


MODULE = Module(
    id='source_placement',
    summary='Uses tree-sitter plus the existing functional map, and derives function placement into the map at a '
            '90% confidence level.',
    purpose='Uses tree-sitter plus the existing functional map, and derives function placement into the map at a '
            '90% confidence level. Placements are recorded in the source_placement knowledge layer at the provider '
            'element; a function below the threshold goes to the Place remaining code ticket. Details: metaform '
            'help source_placement.',
    subscriptions=(Subscription('intake.finished', finished),),
    start=migrate_names,
    provides=(Provides('code.functions', {'suffixes': SUFFIXES, 'parse': parse}),),
    verbs=(
        Verb('extend', extend, 'Classify code for an existing intake and start validation of the remainder.',
             nouns=(Noun('base', 'The intake base ID. Defaults to the active base.', required=False),
                    Noun('run', 'Resume a saved placement run.', required=False),
                    Noun('paths', 'Source paths. Defaults to the intake source citations.', kind='json',
                         schema={'type': 'array', 'items': {'type': 'string'}}, required=False),
                    Noun('exclude', 'Provider namespaces to omit from the categories.', kind='json',
                         schema={'type': 'array', 'items': {'type': 'string'}}, required=False),
                    Noun('confidence', 'Acceptance percentage, default 90.', kind='int', required=False)),
             effect='write', open_world=True, task=True),
        Verb('status', status, 'Read saved classification counts, cost, gaps and progress.',
             nouns=RUN_NOUNS, effect='read'),
        Verb('pending', pending, 'Read remaining placements with their source and category suggestions.',
             nouns=(*RUN_NOUNS, Noun('offset', 'Queue offset.', kind='int', required=False),
                    Noun('limit', 'Page size, default 25.', kind='int', required=False)), effect='read'),
        Verb('resolve', resolve, 'Record a validated category placement with its reason.',
             nouns=(RUN_NOUNS[0], Noun('item', 'The pending code item ID.'),
                    Noun('provider', 'The selected provider namespace.'),
                    Noun('why', 'The source evidence supporting this placement.'), RUN_NOUNS[1]), effect='write'),
        Verb('intake', intake, 'Read the procedure for preparing refactoring context.',
             nouns=(Noun('text', 'The refactoring target, intended outcome, or task context.', required=False),
                    Noun('association', 'Association pass: agent (default) or optional bulk jev.', required=False),
                    Noun('confidence', 'Jev match confidence percentage, default 90.', kind='int', required=False)),
             effect='read',
             examples=(('metaform source_placement intake', 'Read the refactoring intake procedure.'),
                       ('metaform source_placement intake text="Extract the selection callbacks."',
                        'Read the procedure with the task context supplied as data.'))),
        Verb('associate', associate, 'Ask Jev which provider category each code item belongs to, in bulk.',
             nouns=(Noun('items', 'Named evidence records with exact file/symbol, source and graph context.',
                         kind='json', schema={'type': 'object', 'additionalProperties': {'type': 'object'}}),
                    Noun('candidates', 'Named records with provider namespace and ef text or text list. '
                         'Defaults to every provider in the current base.', required=False,
                         kind='json', schema={'type': 'object', 'additionalProperties': {
                             'type': 'object', 'required': ['provider', 'ef'], 'properties': {
                                 'provider': {'type': 'string'},
                                 'ef': {'oneOf': [{'type': 'string'}, {'type': 'array',
                                                                  'items': {'type': 'string'}}]}}}}),
                    Noun('confidence', 'Match confidence percentage from 0 to 100, default 90.',
                         kind='int', required=False)),
             effect='write', open_world=True,
             details='Sends nothing unless the person has turned on jev. Then sends only supplied evidence to the '
                     'endpoint jev_endpoint names, OpenRouter or TypeSafe, with its key from the environment. '
                     'Returns one category choice per item, probabilities, confidence, usage and timing. '
                     'Writes no map records. Obtain authorization for private evidence before sending.'),
    ),
)
