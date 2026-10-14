"""Refactoring intake prepares reusable inference through the existing map tools."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from dataclasses import replace
from importlib import resources
from pathlib import Path
from typing import Any, cast

from metaform import prompt_files
from metaform.data import Store
from metaform.module import Context, Module, Noun, Provides, Stop, Subscription, Verb, child_environment, provided

from .parser import SUFFIXES, parse

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ('tree-sitter>=0.25,<0.26', 'tree-sitter-javascript>=0.25,<0.26')
SHIPS_DISABLED = False
REMOTE_AGENT = False  # intake prepares project knowledge before work is assigned


def intake(ctx: Context) -> str:
    """Serve the authored procedure and optional task context without recording anything."""
    package = resources.files(__name__)
    procedure = prompt_files.required(package, 'intake')
    association = ctx.nouns.get('association', 'agent')
    if association not in ('agent', 'jev'):
        raise Stop('association must be agent or jev.', 'metaform help refactor intake')
    confidence = _confidence(ctx)
    if association == 'jev':
        procedure += '\n\n' + prompt_files.required(package, 'jev', confidence=str(confidence))
    text = ctx.nouns.get('text')
    if text:
        given = prompt_files.required(package, 'input', text=json.dumps(text, ensure_ascii=False))
        return procedure + '\n\n' + given
    return procedure


def _confidence(ctx: Context) -> int:
    value = ctx.nouns.get('confidence', 83)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
        raise Stop('confidence must be an integer percentage from 0 to 100.', 'metaform help refactor')
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
        result = jev.associate(ctx.nouns.get('items'), candidates, threshold=confidence / 100)
        return {**result, 'categories': candidates}
    except (ValueError, RuntimeError) as error:
        raise Stop(str(error), 'metaform help refactor associate') from None


def _bound(ctx: Context) -> Context:
    base = ctx.nouns.get('base')
    if base:
        ctx = replace(ctx, store=Store(ctx.require_store().project_id, base=base, module='refactor'))
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


def finished(payload: dict[str, Any], ctx: Context) -> dict[str, Any]:
    """Finish the intake independently of the optional, durable classification process."""
    if not payload.get('code'):
        return {'status': 'skipped', 'reason': 'The intake does not contain code.'}
    if not os.environ.get('OPENROUTER_API_KEY', '').strip():
        return {'status': 'skipped', 'reason': 'OPENROUTER_API_KEY is unavailable.'}
    if not provided(ctx.folder, 'code.inventory'):
        return {'status': 'skipped', 'reason': 'The code inventory provider is unavailable.'}
    project = str(payload['project'])
    base = str(payload['base'])
    store = Store(project, base=base, module='refactor')
    folder = Path(store.project().path)
    logs = folder / '.metaform' / 'refactor' / 'launches'
    logs.mkdir(parents=True, exist_ok=True)
    receipt = logs / f'{uuid.uuid4().hex}.json'
    command = [sys.executable, '-m', 'metaform', 'refactor', 'extend', f'base={base}',
               '--project', project, '--json']
    options: dict[str, Any] = ({'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
                               if os.name == 'nt' else {'start_new_session': True})
    try:
        with receipt.open('wb') as output:
            child = subprocess.Popen(command, cwd=folder, env=child_environment(), stdin=subprocess.DEVNULL,
                                     stdout=output, stderr=subprocess.STDOUT, **options)
    except OSError as error:
        return {'status': 'skipped', 'reason': str(error)}
    return {'status': 'running', 'pid': child.pid, 'base': base, 'result': str(receipt)}


RUN_NOUNS = (Noun('run', 'The saved placement run ID.'),
             Noun('base', 'The intake base ID the run belongs to.', required=False))


MODULE = Module(
    id='refactor',
    summary='Prepare reusable refactoring context on the functional map.',
    purpose='Serves a procedure for connecting functional elements to their implementation and preparing '
            'refactoring context before agents edit code. The procedure records that understanding in the '
            'refactor knowledge layer using existing map tools. Details: metaform help refactor.',
    subscriptions=(Subscription('intake.finished', finished),),
    provides=(Provides('code.functions', {'suffixes': SUFFIXES, 'parse': parse}),),
    verbs=(
        Verb('extend', extend, 'Classify code for an existing intake and start validation of the remainder.',
             nouns=(Noun('base', 'The intake base ID. Defaults to the active base.', required=False),
                    Noun('run', 'Resume a saved placement run.', required=False),
                    Noun('paths', 'Source paths. Defaults to the intake source citations.', kind='json',
                         schema={'type': 'array', 'items': {'type': 'string'}}, required=False),
                    Noun('exclude', 'Provider namespaces to omit from the categories.', kind='json',
                         schema={'type': 'array', 'items': {'type': 'string'}}, required=False),
                    Noun('confidence', 'Acceptance percentage, default 83.', kind='int', required=False)),
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
                    Noun('confidence', 'Jev match confidence percentage, default 83.', kind='int', required=False)),
             effect='read',
             examples=(('metaform refactor intake', 'Read the refactoring intake procedure.'),
                       ('metaform refactor intake text="Extract the selection callbacks."',
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
                    Noun('confidence', 'Match confidence percentage from 0 to 100, default 83.',
                         kind='int', required=False)),
             effect='read', open_world=True,
             details='Sends only supplied evidence to OpenRouter/TypeSafe using OPENROUTER_API_KEY. '
                     'Returns one category choice per item, probabilities, confidence, usage and timing. '
                     'Writes no map records. Obtain authorization for private evidence before sending.'),
    ),
)
