"""Durable code placement runs, with map records and a review queue on their pinned base."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any, cast

from metaform import home
from metaform.data import Node, Store
from metaform.jev import Config
from metaform.module import Context, context, provided

from . import jev

LAYER = 'source_placement'  # the knowledge layer placements are recorded in


def _read(path: Path) -> Any:
    return json.loads(path.read_text())


def _write(path: Path, value: Any) -> None:
    temporary = path.with_suffix(f'.{os.getpid()}.tmp')
    text = json.dumps(value, ensure_ascii=False, allow_nan=False)
    if home.is_home_path(temporary):
        home.write_private(temporary, text)
    else:
        temporary.write_text(text)
    temporary.replace(path)


def _directory(ctx: Context, run_id: str) -> Path:
    if not re.fullmatch(r'[a-f0-9]{24}', run_id):
        raise ValueError('Invalid source placement run ID.')
    from . import runs_root
    store = ctx.require_store()
    directory = runs_root(store.project_id) / run_id
    # A run made before runs moved into the home stays in the project folder, which every home registering the
    # project shares, and is read and resumed there.
    legacy = Path(store.project().path) / '.metaform' / 'source_placement' / run_id
    return legacy if not directory.exists() and legacy.is_dir() else directory


def _load(ctx: Context, run_id: str, base_id: str | None = None) -> tuple[Path, dict[str, Any], Store]:
    directory = _directory(ctx, run_id)
    run = _read(directory / 'run.json')
    if run['project'] != ctx.require_store().project_id or (base_id and run['base_id'] != base_id):
        raise ValueError('The source placement run belongs to a different project or base.')
    if not any(base.id == run['base_id'] for base in home.bases(run['project'])):
        raise ValueError('The source placement run\'s base no longer exists in this project.')
    return directory, run, Store(run['project'], base=run['base_id'])


@contextmanager
def _lock(directory: Path) -> Generator[None]:
    # Advisory locks are released on process exit, including crashes; the lock file is never replaced, so another
    # opener cannot acquire a different lock under the same name.
    with ExitStack() as held:
        try:
            held.enter_context(home.file_lock(directory / 'lock', wait=False))
        except home.Held:
            raise ValueError('This source placement run is already being processed.') from None
        yield


def _categories(store: Store, exclude: list[str]) -> dict[str, Any]:
    providers: dict[str, list[str]] = {}
    for purpose in store.layer_graph('base').joins:
        for provider in purpose.elements:
            if (provider.address and jev.eligible_provider(provider.address)
                    and provider.address not in exclude and purpose.ef):
                texts = providers.setdefault(provider.address, [])
                if purpose.ef not in texts:
                    texts.append(purpose.ef)
    return {f'category_{index:03d}': {'provider': address, 'ef': texts}
            for index, (address, texts) in enumerate(sorted(providers.items()))}


def _paths(store: Store) -> list[str] | None:
    if not any(layer.name == 'sources' for layer in store.layers(limit=0).results):
        return None
    paths = sorted({ref.value for item in store.layer_items('sources', limit=0).results
                    for ref in item.refs if ref.key == 'path'})
    return paths or None


def prepare(ctx: Context, *, paths: list[str] | None = None, exclude: list[str] | None = None,
            confidence: int = 90) -> dict[str, Any]:
    """Discover evidence once, without billing. Identical input resumes its existing run."""
    if isinstance(confidence, bool) or not 0 <= confidence <= 100:
        raise ValueError('confidence must be a percentage between 0 and 100.')
    try:
        cfg = jev.configured(ctx.folder)
    except ValueError as error:
        return {'status': 'skipped', 'reason': str(error)}
    capabilities = provided(ctx.folder, 'code.inventory')
    if not capabilities:
        return {'status': 'skipped', 'reason': 'The code inventory MCP capability is unavailable.'}
    store = ctx.require_store()
    base = store.bound_base()
    if base is None:
        return {'status': 'skipped', 'reason': 'No intake base is available.'}
    owner, inventory = capabilities[0]
    inventory_context = context(owner, ctx.folder, project=store.project_id)
    inventory_context.store = Store(store.project_id, base=base.id)
    try:
        evidence = inventory(inventory_context, paths=paths if paths is not None else _paths(store))
    except Exception as error:  # noqa: BLE001 - optional extension cannot invalidate intake
        return {'status': 'skipped', 'reason': f'Code inventory unavailable: {error}'}
    candidates = _categories(store, exclude or [])
    if not candidates or not (evidence.get('items') or evidence.get('gaps')):
        return {'status': 'skipped', 'reason': 'No provider categories or code functions are available.',
                'coverage': evidence.get('coverage'), 'gaps': evidence.get('gaps', [])}
    root = Path(store.project().path).resolve()
    items: dict[str, Any] = {}
    files: dict[str, str] = {}
    contents: dict[str, bytes] = {}
    for index, original in enumerate(evidence.get('items', [])):
        item = dict(original)
        path = (root / item['file']).resolve()
        if not path.is_relative_to(root):
            raise ValueError('Code evidence must be inside the project.')
        item['file'] = path.relative_to(root).as_posix()
        if item['file'] not in contents:
            contents[item['file']] = path.read_bytes()
            files[item['file']] = hashlib.sha256(contents[item['file']]).hexdigest()
        raw = contents[item['file']]
        if item.get('sha256') and item['sha256'] != files[item['file']]:
            raise ValueError(f'Code inventory is stale for {item["file"]}.')
        if 'start_byte' in item and raw[item['start_byte']:item['end_byte']].decode() != item['source']:
            raise ValueError(f'Code inventory is stale for {item["file"]}.')
        items[f'function_{index:05d}'] = item
    gaps = list(evidence.get('gaps', []))
    for item_id, item in list(items.items()):
        try:
            jev.prepare_batches(_wire({item_id: item}), candidates)
        except ValueError as error:
            gaps.append({'kind': 'request_budget', 'reason': str(error), 'evidence': item})
            del items[item_id]
    identity: dict[str, Any] = {'project': store.project_id, 'base_id': base.id, 'files': files, 'items': items,
                'candidates': candidates, 'threshold': confidence / 100, 'model': cfg.model}
    if gaps:
        identity['gaps'] = gaps
    run_id = hashlib.sha256(jev.encode(identity)).hexdigest()[:24]
    directory = _directory(ctx, run_id)
    if home.is_home_path(directory):
        home.mkdir_private(directory)
    else:
        directory.mkdir(mode=0o700, exist_ok=True)
    with _lock(directory):
        if not (directory / 'run.json').exists():
            batches = jev.prepare_batches(_wire(items), candidates) if items else []
            _write(directory / 'input.json', identity)
            _write(directory / 'batches.json', batches)
            _write(directory / 'run.json', {'run_id': run_id, 'project': store.project_id, 'base_id': base.id,
                    'status': 'ready', 'threshold': confidence / 100, 'total': len(items),
                    'coverage': evidence.get('coverage'), 'gaps': gaps, 'usage': {}})
    return status(ctx, run_id)


def _wire(items: dict[str, Any]) -> dict[str, Any]:
    return {key: {'symbol': item.get('symbol') or 'anonymous', 'source': item['source']}
            for key, item in items.items()}


def _fresh(ctx: Context, inputs: dict[str, Any], store: Store) -> None:
    root = Path(store.project().path).resolve()
    for file, expected in inputs['files'].items():
        path = (root / file).resolve()
        if not path.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f'Code changed since this run was prepared: {file}. Prepare a new run.')
    current = {value['provider']: value['ef'] for value in _categories(store, []).values()}
    if any(current.get(value['provider']) != value['ef'] for value in inputs['candidates'].values()
           if jev.eligible_provider(value['provider'])):
        raise ValueError('Provider definitions changed. Prepare a new run.')


def status(ctx: Context, run_id: str, base_id: str | None = None) -> dict[str, Any]:
    _, run, _ = _load(ctx, run_id, base_id)
    return run


def _place(store: Store, run_id: str, inputs: dict[str, Any], decisions: list[dict[str, Any]],
           resolutions: dict[str, Any]) -> None:
    with store.atomic():
        if not any(layer.name == LAYER for layer in store.layers(limit=0).results):
            store.layer(LAYER, LAYER, 'Where each source function is placed on the functional map, with its confidence '
                        'and reason.', mutable=True, hideable=True, ready=True)
        existing: set[str] = set()
        for stored in store.layer_items(LAYER, limit=0).results:
            value: Any = stored.value
            if isinstance(value, dict):
                record = cast(dict[str, Any], value)
                if record.get('run_id') == run_id:
                    existing.add(str(record.get('item_id')))
        for decision in decisions:
            item_id = decision['item_id']
            resolution = resolutions.get(item_id)
            if item_id in existing or (not resolution and decision['confidence'] < inputs['threshold']):
                continue
            category = inputs['candidates'][decision['candidate_id']]
            provider = resolution['provider'] if resolution else category['provider']
            why = resolution['why'] if resolution else 'Jev selected this provider at the intake confidence threshold.'
            source = {key: value for key, value in inputs['items'][item_id].items() if key != 'source'}
            source['file_sha256'] = inputs['files'][source['file']]
            store.add_item(LAYER, Node('element', provider), {
                'kind': 'code-placement', 'run_id': run_id, 'item_id': item_id, 'source': source,
                'provider': provider, 'confidence': decision['confidence'], 'why': why,
                'method': 'validated' if resolution else 'jev', 'suggested_provider': category['provider']})
        for item_id, resolution in resolutions.items():
            if not item_id.startswith('gap_') or item_id in existing:
                continue
            store.add_item(LAYER, Node('element', resolution['provider']), {
                'kind': 'code-inventory-validation', 'run_id': run_id, 'item_id': item_id,
                'gap': inputs['gaps'][int(item_id[4:])], 'why': resolution['why'],
                'provider': resolution['provider']})


def _finish(ctx: Context, directory: Path, run: dict[str, Any], store: Store,
            inputs: dict[str, Any], decisions: list[dict[str, Any]], usage: dict[str, float]) -> dict[str, Any]:
    _fresh(ctx, inputs, store)
    if {one['item_id'] for one in decisions} != set(inputs['items']) or len(decisions) != len(inputs['items']):
        raise ValueError('Results must cover every function exactly once.')
    for decision in decisions:
        if decision['candidate_id'] not in inputs['candidates'] or not 0 <= decision['confidence'] <= 1:
            raise ValueError('Invalid category or confidence in classification results.')
    resolutions: dict[str, Any] = _read(directory / 'resolutions.json') if (directory / 'resolutions.json').exists() else {}
    _write(directory / 'decisions.json', decisions)
    _place(store, run['run_id'], inputs, decisions, resolutions)
    accepted = sum(one['confidence'] >= inputs['threshold'] for one in decisions)
    gap_count = sum(f'gap_{index:05d}' not in resolutions for index in range(len(run.get('gaps', []))))
    remaining = sum(one['confidence'] < inputs['threshold'] and one['item_id'] not in resolutions for one in decisions)
    run.update(status='review' if remaining or gap_count else 'complete', accepted=accepted,
               remaining=remaining, pending=remaining + gap_count, gap_count=gap_count, validated=len(resolutions), usage=usage)
    _write(directory / 'run.json', run)
    return run


def _probe(directory: Path, cfg: Config) -> dict[str, Any]:
    """Check the same model endpoint when every source item needs manual review."""
    checkpoint = directory / 'probe.json'
    if checkpoint.exists():
        return _read(checkpoint)
    payload = {'state': {'availability': 'ready'}, 'questions': {
        'availability': {'type': 'choice', 'instructions': 'Select the availability value from the state.',
                         'criteria': {'ready': 'The availability value is ready.'}}}}
    response = jev.send(cfg, payload)
    answer = response.get('answers', {}).get('availability', {})
    if (answer.get('type') != 'choice' or answer.get('choice') != 'ready'
            or not isinstance(answer.get('confidence'), (int, float))
            or not 0 <= answer['confidence'] <= 1 or answer.get('probabilities') != {'ready': 1}):
        raise ValueError('The model availability probe did not return the requested typed response.')
    usage = {name: amount for name, amount in response.get('usage', {}).items()
             if isinstance(amount, (int, float)) and not isinstance(amount, bool) and math.isfinite(amount)}
    result: dict[str, Any] = {'decisions': [], 'usage': usage, 'availability': True}
    _write(checkpoint, result)
    return result


def execute(ctx: Context, run_id: str, *, base_id: str | None = None) -> dict[str, Any]:
    directory, run, store = _load(ctx, run_id, base_id)
    with _lock(directory):
        inputs = _read(directory / 'input.json')
        _fresh(ctx, inputs, store)
        if run['status'] in ('review', 'complete'):
            return run
        if any(not jev.eligible_provider(value['provider']) for value in inputs['candidates'].values()):
            raise ValueError('This unfinished run includes excluded providers. Prepare a new run.')
        batches = _read(directory / 'batches.json')
        started = time.perf_counter()
        run['status'] = 'running'
        _write(directory / 'run.json', run)

        def batch(index: int, cfg: Config) -> dict[str, Any]:
            checkpoint = directory / f'batch-{index:05d}.json'
            if checkpoint.exists():
                return _read(checkpoint)
            result = jev.associate(batches[index]['state']['items'], inputs['candidates'], cfg,
                                   threshold=inputs['threshold'])
            _write(checkpoint, result)
            return result

        try:
            # A run prepared while jev was on, resumed after the person turned it off, sends nothing.
            cfg = jev.configured(ctx.folder)
            # The first useful batch also verifies credentials and model availability.
            reports = [batch(0, cfg)] if batches else [_probe(directory, cfg)]
            with ThreadPoolExecutor(max_workers=6) as pool:
                reports.extend(future.result() for future in as_completed(
                    [pool.submit(batch, index, cfg) for index in range(1, len(batches))]))
            decisions = [decision for report in reports for decision in report['decisions']]
            usage: dict[str, float] = {}
            for report in reports:
                for key, amount in report['usage'].items():
                    usage[key] = usage.get(key, 0) + amount
            run['elapsed_seconds'] = time.perf_counter() - started
            return _finish(ctx, directory, run, store, inputs, decisions, usage)
        except Exception as error:  # noqa: BLE001 - optional extension cannot invalidate intake
            run.update(status='unavailable', reason=str(error))
            _write(directory / 'run.json', run)
            return run


def pending(ctx: Context, run_id: str, base_id: str | None = None, offset: int = 0,
            limit: int = 25) -> dict[str, Any]:
    directory, run, store = _load(ctx, run_id, base_id)
    inputs = _read(directory / 'input.json')
    _fresh(ctx, inputs, store)
    if offset < 0 or not 1 <= limit <= 100:
        raise ValueError('offset must be nonnegative and limit must be between 1 and 100.')
    decisions: list[dict[str, Any]] = _read(directory / 'decisions.json') if (directory / 'decisions.json').exists() else []
    resolutions: dict[str, Any] = _read(directory / 'resolutions.json') if (directory / 'resolutions.json').exists() else {}
    remaining = [{**one, 'suggested_provider': inputs['candidates'][one['candidate_id']]['provider'],
                  'suggestion_eligible': jev.eligible_provider(inputs['candidates'][one['candidate_id']]['provider'])}
                 for one in decisions if one['confidence'] < inputs['threshold']
                 and one['item_id'] not in resolutions]
    remaining.extend({'item_id': f'gap_{index:05d}', 'gap': gap}
                     for index, gap in enumerate(run.get('gaps', [])) if f'gap_{index:05d}' not in resolutions)
    return {**run, 'categories': {key: value for key, value in inputs['candidates'].items()
                                 if jev.eligible_provider(value['provider'])}, 'remaining': len(remaining), 'offset': offset,
            'items': [{**one, **inputs['items'].get(one['item_id'], {})} for one in remaining[offset:offset + limit]]}


def resolve(ctx: Context, run_id: str, base_id: str | None, item: str, provider: str, why: str) -> dict[str, Any]:
    directory, run, store = _load(ctx, run_id, base_id)
    with _lock(directory):
        inputs = _read(directory / 'input.json')
        _fresh(ctx, inputs, store)
        decisions = _read(directory / 'decisions.json')
        if (not why.strip() or not jev.eligible_provider(provider)
                or provider not in {one['provider'] for one in inputs['candidates'].values()}):
            raise ValueError('Supply an existing provider category and the reason for the placement.')
        decision = next((one for one in decisions if one['item_id'] == item), None)
        gap_ids = {f'gap_{index:05d}' for index in range(len(run.get('gaps', [])))}
        if item not in gap_ids and (decision is None or decision['confidence'] >= inputs['threshold']):
            raise ValueError('This item is not in the review queue.')
        path = directory / 'resolutions.json'
        resolutions: dict[str, Any] = _read(path) if path.exists() else {}
        value = {'provider': provider, 'why': why}
        if item in resolutions and resolutions[item] != value:
            raise ValueError('This item has already been resolved with a different placement.')
        resolutions[item] = value
        _write(path, resolutions)
        return _finish(ctx, directory, run, store, inputs, decisions, run['usage'])


def import_results(ctx: Context, run_id: str, result_directory: Path, *,
                   base_id: str | None = None) -> dict[str, Any]:
    """Reuse a previous real-data run only when category definitions and exact code spans agree."""
    directory, run, store = _load(ctx, run_id, base_id)
    with _lock(directory):
        inputs = _read(directory / 'input.json')
        _fresh(ctx, inputs, store)
        old_items = _read(result_directory / 'items.json')
        locations = _read(result_directory / 'locations.json')
        old_candidates = _read(result_directory / 'candidates.json')
        by_provider = {value['provider']: (key, value['ef']) for key, value in inputs['candidates'].items()}
        candidate_ids: dict[str, str] = {}
        for key, value in old_candidates.items():
            match = by_provider.get(value['provider'])
            if match is None or match[1] != value['ef']:
                raise ValueError('Imported provider categories do not match this run.')
            candidate_ids[key] = match[0]
        if len(candidate_ids) != len(by_provider):
            raise ValueError('Imported category set is incomplete.')
        by_span = {(str((Path(store.project().path) / value['file']).resolve()), value.get('start_byte'), value.get('end_byte')): key
                   for key, value in inputs['items'].items()}
        item_ids: dict[str, str] = {}
        for key, value in old_items.items():
            locator = locations['locations'][key]
            match = by_span.get((str(Path(locator['file']).resolve()), locator['start_byte'], locator['end_byte']))
            if match is None or value['source'] != inputs['items'][match]['source']:
                raise ValueError('Imported code spans do not match this run.')
            old_symbol = value.get('symbol') or 'anonymous'
            new_symbol = inputs['items'][match].get('symbol') or 'anonymous'
            if old_symbol != new_symbol and {old_symbol, new_symbol} != {'anonymous', '<anonymous>'}:
                raise ValueError('Imported symbol names do not match this run.')
            if inputs['files'][inputs['items'][match]['file']] != locations['sha256']:
                raise ValueError('Imported source file is stale.')
            item_ids[key] = match
        decisions = [{**one, 'item_id': item_ids[one['item_id']],
                      'candidate_id': candidate_ids[one['candidate_id']],
                      'choice': candidate_ids[one['candidate_id']],
                      'probabilities': {candidate_ids[key]: value for key, value in one['probabilities'].items()}}
                     for one in _read(result_directory / 'decisions.json')]
        old_summary = _read(result_directory / 'summary.json')
        run.update(imported_from=str(result_directory), elapsed_seconds=old_summary['elapsed_seconds'])
        return _finish(ctx, directory, run, store, inputs, decisions, old_summary['usage'])
