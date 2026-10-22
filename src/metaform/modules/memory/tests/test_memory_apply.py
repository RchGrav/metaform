"""Atomic memory projection, retries and concurrent writers."""
from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from metaform import changes
from metaform.data import Store
from metaform.module import Context, Stop
from metaform.modules import memory

pytestmark = pytest.mark.kind('fixture')
NODE = 'element:code.target'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def absent(*names):
    return digest({'node': {'receiver': 'code.target', 'provider': ''},
                   'entities': [{'name': name, 'absent': True} for name in sorted(names)],
                   'relations': [], 'joins': []})


@pytest.fixture
def target(run, tmp_path):
    folder = tmp_path / 'batch-project'
    folder.mkdir()
    run('add', 'project', 'batch-project', str(folder))
    store = Store('batch-project', module='memory')
    with store.atomic():
        layer = store.layer('intake', 'intake', 'Batch target.', kind='intake', ready=True, mutable=False, hideable=False)
        store.add_element(layer.name, 'code.target', role='DE', name_length=1)
    return folder, store


def request(*names, mutation_id='step-1', expected=None, mutations=None):
    return {'node': NODE, 'entityNames': list(names), 'expectedDigest': expected or absent(*names),
            'mutationId': mutation_id, 'mutations': mutations if mutations is not None else [
                {'op': 'create_entities', 'entities': [
                    {'name': name, 'entityType': 'fact', 'observations': ['One fact.'],
                     'why': 'Describes target behavior.'} for name in names]}]}


def apply(target, args):
    folder, store = target
    return memory.apply(Context('memory', folder, project=store.project_id, store=store, nouns=args))


def snapshot(target):
    with target[1].tables(write=False) as tx:
        return {name: list(tx.rows(name, limit=0).results) for name in
                ('entities', 'observations', 'relations', 'joins', 'apply_receipts')}


def test_memory_apply_conflict_writes_nothing_and_emits_nothing(target, monkeypatch):
    events = []
    monkeypatch.setattr(changes, 'note', lambda *args, **kwargs: events.append(args))
    with pytest.raises(Stop, match='MEMORY_CONFLICT'):
        apply(target, request('alpha', expected='0' * 64))
    assert all(not rows for rows in snapshot(target).values())
    assert events == []


def test_memory_apply_retry_returns_durable_receipt_after_later_writer(target):
    args = request('alpha')
    receipt = apply(target, args)
    assert set(receipt) == {'mutationId', 'requestHash', 'beforeDigest', 'afterDigest', 'applied', 'receiptId'}
    assert receipt['applied'] is True
    assert receipt['beforeDigest'] == absent('alpha')
    expected_state = {'node': {'receiver': 'code.target', 'provider': ''},
                      'entities': [{'name': 'alpha', 'entityType': 'fact', 'observations': ['One fact.']}],
                      'relations': [], 'joins': [{'entity': 'alpha', 'receiver': 'code.target', 'provider': ''}]}
    assert receipt['afterDigest'] == digest(expected_state)
    apply(target, request('alpha', mutation_id='step-2', expected=receipt['afterDigest'], mutations=[
        {'op': 'delete_entities', 'entityNames': ['alpha']}]))
    assert apply((target[0], Store('batch-project', module='memory')), args) == receipt
    assert snapshot(target)['entities'] == []
    assert len(snapshot(target)['apply_receipts']) == 2
    with pytest.raises(Stop, match='MEMORY_MUTATION_ID_REUSED'):
        apply(target, {**args, 'mutations': []})


def test_memory_apply_concurrent_writers_compare_under_write_lock(target):
    ready = Barrier(2)

    def writer(number):
        ready.wait(timeout=10)
        try:
            return apply((target[0], Store('batch-project', module='memory')),
                         request('alpha', mutation_id=f'step-{number}'))
        except Stop as error:
            return str(error)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(writer, (1, 2)))
    assert sum(isinstance(one, dict) for one in results) == 1
    assert sum('MEMORY_CONFLICT' in one for one in results if isinstance(one, str)) == 1
    assert len(snapshot(target)['apply_receipts']) == 1


def test_memory_apply_concurrent_identical_retry_applies_once(target):
    ready = Barrier(2)

    def writer(_):
        ready.wait(timeout=10)
        return apply((target[0], Store('batch-project', module='memory')), request('alpha'))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(writer, (1, 2)))
    assert results[0] == results[1]
    assert len(snapshot(target)['observations']) == 1
    assert len(snapshot(target)['apply_receipts']) == 1


def test_memory_apply_rolls_back_prior_operations_and_receipt_failure(target, monkeypatch):
    from metaform.data import TableTx
    before = snapshot(target)
    events = []
    monkeypatch.setattr(changes, 'note', lambda *args, **kwargs: events.append(args))
    args = request('alpha', 'missing')
    args['mutations'] = [args['mutations'][0],
                         {'op': 'add_observations', 'observations': [
                             {'entityName': 'unknown', 'contents': ['Another fact.']}]}]
    # Outside the declared set fails before any write.
    with pytest.raises(Stop, match='MEMORY_SCOPE'):
        apply(target, args)
    original = TableTx.insert

    def fail_receipt(self, table, row):
        if table == 'apply_receipts':
            raise RuntimeError('receipt failure')
        return original(self, table, row)

    monkeypatch.setattr(TableTx, 'insert', fail_receipt)
    with pytest.raises(RuntimeError, match='receipt failure'):
        apply(target, request('alpha'))
    assert snapshot(target) == before
    assert events == []


def test_memory_apply_reuses_canonical_operations_and_preserves_existing_create(target):
    first = apply(target, request('alpha', 'beta'))
    args = request('alpha', 'beta', mutation_id='next', expected=first['afterDigest'], mutations=[
        {'op': 'create_entities', 'entities': [
            {'name': 'alpha', 'entityType': 'ignored', 'observations': ['Ignored.']}]},
        {'op': 'add_observations', 'observations': [{'entityName': 'alpha', 'contents': ['Second fact.']}]},
        {'op': 'delete_observations', 'deletions': [{'entityName': 'alpha', 'observations': ['One fact.']}]},
        {'op': 'create_relations', 'relations': [{'from': 'alpha', 'to': 'beta', 'relationType': 'uses'}]},
        {'op': 'delete_relations', 'relations': [{'from': 'alpha', 'to': 'beta', 'relationType': 'uses'}]},
        {'op': 'join', 'entity': 'alpha'}])
    apply(target, args)
    state = snapshot(target)
    assert {row['entity_type'] for row in state['entities']} == {'fact'}
    assert [row['content'] for row in state['observations'] if row['entity'] == 'alpha'] == ['Second fact.']
    assert state['relations'] == []
    assert len(state['joins']) == 2


@pytest.mark.parametrize('patch,code', [
    ({'mutations': [{'op': 'lock', 'entity': 'alpha'}]}, 'MEMORY_INVALID'),
    ({'mutations': [{'op': 'join', 'entity': 'alpha', 'project': 'other'}]}, 'MEMORY_INVALID'),
    ({'entityNames': 'alpha'}, 'MEMORY_INVALID'),
    ({'mutations': [{'op': 'delete_entities', 'entityNames': ['other']}]}, 'MEMORY_SCOPE'),
    ({'mutationId': 'x' * 300}, 'MEMORY_LIMIT'),
    ({'mutations': [{'op': 'join', 'entity': 'alpha'}] * 129}, 'MEMORY_LIMIT'),
    ({'mutations': [{'op': 'add_observations', 'observations': [
        {'entityName': 'alpha', 'contents': ['x' * 262144]}]}]}, 'MEMORY_LIMIT'),
    ({'entityNames': [f'name-{i}' for i in range(257)]}, 'MEMORY_LIMIT'),
    ({'mutations': [{'op': 'add_observations', 'observations': [
        {'entityName': 'alpha', 'contents': ['Fact.'] * 1001}]}]}, 'MEMORY_LIMIT'),
])
def test_memory_apply_validates_bounds_and_scope(target, patch, code):
    with pytest.raises(Stop, match=code):
        apply(target, {**request('alpha'), **patch})
    assert all(not rows for rows in snapshot(target).values())


def test_memory_apply_failure_after_valid_write_rolls_back(target, monkeypatch):
    args = request('alpha', 'missing')
    args['mutations'] = [request('alpha')['mutations'][0],
                         {'op': 'add_observations', 'observations': [
                             {'entityName': 'missing', 'contents': ['One fact.']}]}]
    events = []
    monkeypatch.setattr(changes, 'note', lambda *args, **kwargs: events.append(args))
    with pytest.raises(Stop, match='not found'):
        apply(target, args)
    assert all(not rows for rows in snapshot(target).values())
    assert events == []


def test_memory_apply_rejects_project_override(target):
    folder, _ = target
    with pytest.raises(Stop, match='MEMORY_SCOPE'):
        memory.apply(Context('memory', folder, project='other', store=Store('batch-project', module='memory'),
                             nouns=request('alpha')))


def test_memory_apply_canonical_locks_are_preserved(target):
    first = apply(target, request('alpha'))
    with target[1].tables() as tx:
        tx.update('entities', {'name': 'alpha'}, {'locked_at': 'now', 'locked_by': 'user'})
    with pytest.raises(Stop, match='MEMORY_LOCKED'):
        apply(target, request('alpha', mutation_id='next', expected=first['afterDigest'], mutations=[
            {'op': 'delete_entities', 'entityNames': ['alpha']}]))
    assert len(snapshot(target)['entities']) == 1
    assert len(snapshot(target)['apply_receipts']) == 1


def test_memory_apply_catalog_discovers_and_executes_receipt_contract(target):
    import asyncio
    from types import SimpleNamespace

    from mcp import types

    from metaform.modules.mcp.server import build, module_tools_text, run_catalog, verb_schema

    folder, _ = target
    error, blocks = run_catalog(folder, {'search': 'memory_apply'}, None)
    assert not error and any('memory_apply' in one for one in blocks)
    assert 'memory_apply' in module_tools_text(folder, 'memory')
    verb = next(one for one in memory.MODULE.verbs if one.name == 'apply')
    assert verb.effect == 'remove'
    schema = verb_schema(verb, folder)
    assert set(schema['required']) == {'node', 'entityNames', 'expectedDigest', 'mutationId', 'mutations'}
    assert len(schema['properties']['mutations']['items']['oneOf']) == 8
    server, _, _ = build(folder)
    handler = server.get_request_handler('tools/call').handler
    ctx = SimpleNamespace(request=None, params={}, protocol_version='2026-07-28',
                          session=SimpleNamespace(client_params=None, client_capabilities=types.ClientCapabilities()))
    args = request('alpha')
    params = types.CallToolRequestParams(name='metaform_catalog', arguments={'tool': 'memory_apply', 'arguments': args})
    result = asyncio.run(handler(ctx, params))
    assert not result.is_error, result
    assert result.structured_content['mutationId'] == 'step-1'
    assert result.structured_content['applied'] is True
    assert result.structured_content['beforeDigest'] == absent('alpha')
    assert result.structured_content['receiptId'] == snapshot(target)['apply_receipts'][0]['receipt']['receiptId']


def test_memory_apply_success_notifies_only_after_receipt_commit(target, monkeypatch):
    seen = []
    original = changes.note

    def noted(project, base, written, *args, **kwargs):
        if 'memory.changed' in (kwargs.get('about') or {}).get('kinds', []):
            # A new connection must already see the mutation and receipt when notifications are noted.
            state = snapshot((target[0], Store(project, module='memory')))
            assert len(state['entities']) == len(state['apply_receipts']) == 1
            seen.append(kwargs['about'])
        return original(project, base, written, *args, **kwargs)

    monkeypatch.setattr(changes, 'note', noted)
    apply(target, request('alpha'))
    assert len(seen) == 1
    assert 'memory:code.target' in seen[0]['kinds']
    before = len(seen)
    apply(target, request('alpha'))
    assert len(seen) == before


def test_memory_apply_missing_map_does_not_invent_base(run, tmp_path):
    from metaform import home

    folder = tmp_path / 'unmapped'
    folder.mkdir()
    run('add', 'project', 'unmapped', str(folder))
    store = Store('unmapped', module='memory')
    assert home.active_base('unmapped') is None
    with pytest.raises(Stop, match='MEMORY_SCOPE'):
        apply((folder, store), request('alpha'))
    assert home.active_base('unmapped') is None


def test_memory_apply_replays_receipt_without_target_map(target):
    args = request('alpha')
    receipt = apply(target, args)
    store = target[1]
    base = store.bound_base()
    store.withdraw_base(base.id)
    assert store.bound_base() is None
    assert apply(target, args) == receipt


def test_memory_apply_unicode_validation_is_typed(target):
    with pytest.raises(Stop, match='MEMORY_INVALID'):
        apply(target, {**request('alpha'), 'mutationId': '\ud800'})


def test_memory_apply_preserves_unread_facts_and_authors_new_relations(target):
    from dataclasses import replace

    folder, store = target
    first = apply(target, request('alpha', 'beta'))
    ctx = Context('memory', folder, project=store.project_id, store=store, session='caller', nouns=request(
        'alpha', 'beta', mutation_id='next', expected=first['afterDigest'], mutations=[
            {'op': 'add_observations', 'observations': [{'entityName': 'alpha', 'contents': ['Second fact.']}]},
            {'op': 'create_relations', 'relations': [{'from': 'alpha', 'to': 'beta', 'relationType': 'uses'}]}]))
    memory.apply(ctx)
    from metaform.modules.memory import read_unread
    unread = read_unread(replace(ctx, nouns={'node': NODE}))
    assert {one['name'] for one in unread['entities']} == {'alpha', 'beta'}
    # Relations written by this session have their own receipts, without acknowledging endpoint bodies.
    from metaform.modules.memory import delivery
    relation = {'from': 'alpha', 'to': 'beta', 'relationType': 'uses'}
    assert delivery.prepare(ctx, {'entities': [], 'relations': [relation]})['components'] == []


def test_memory_apply_unjoin_digest_and_multiple_observation_deletions(target):
    first = apply(target, request('alpha'))
    second = apply(target, request('alpha', mutation_id='second', expected=first['afterDigest'], mutations=[
        {'op': 'add_observations', 'observations': [{'entityName': 'alpha', 'contents': ['Second fact.']}]}]))
    join_id = snapshot(target)['joins'][0]['join_id']
    third = apply(target, request('alpha', mutation_id='third', expected=second['afterDigest'], mutations=[
        {'op': 'delete_observations', 'deletions': [{'entityName': 'alpha',
                                                   'observations': ['One fact.', 'Second fact.']}]},
        {'op': 'unjoin', 'id': join_id}]))
    state = snapshot(target)
    assert len(state['entities']) == 1
    assert state['observations'] == state['joins'] == []
    assert third['beforeDigest'] != third['afterDigest']


def test_memory_apply_detects_incident_relation_changes(target):
    from dataclasses import replace

    from metaform.modules.memory.batch import target_digest

    apply(target, request('alpha', 'beta'))
    folder, store = target
    ctx = Context('memory', folder, project=store.project_id, store=store)
    with store.tables(write=False) as tx:
        before = target_digest(tx, memory.Key('code.target'), ['alpha'])
    from metaform.modules.memory import create_relations
    create_relations(replace(ctx, nouns={'relations': [
        {'from': 'alpha', 'to': 'beta', 'relationType': 'uses'}]}))
    with pytest.raises(Stop, match='MEMORY_CONFLICT'):
        apply(target, request('alpha', mutation_id='next', expected=before, mutations=[]))
    assert len(snapshot(target)['apply_receipts']) == 1
