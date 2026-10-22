"""One bounded compare/write on the memory module's project store."""
# Canonical helpers are internal to this package, shared with its command handlers.
# pyright: reportPrivateUsage=false
from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import Any, cast

from metaform.data import TableTx
from metaform.module import Context, Stop, project_for

from . import (
    APPLY_MUTATION,
    NAMES,
    Graph,
    Key,
    Row,
    _bodies,
    _changed,
    _cites,
    _forget,
    _Given,
    _join,
    _key,
    _layered,
    _not_found,
    _observe,
    _one_fact_each,
    _restamped,
    _titles,
    _written,
    delivery,
)

MAX_BYTES = 262144
MAX_ITEMS = 1000
MAX_NAMES = 256
MAX_MUTATIONS = 128


OPERATIONS: dict[str, Row] = {one['properties']['op']['enum'][0]: one for one in APPLY_MUTATION['oneOf']}


def _error(code: str, message: str) -> Stop:
    return Stop(f'{code}: {message}', 'metaform help memory apply')


def canonical(value: Any) -> bytes:
    """UTF-8 JSON, sorted keys, no insignificant whitespace, literal Unicode, no non-JSON numbers."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _hash(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _validate(value: Any, schema: Row, path: str) -> int:
    """Strict canonical shapes, including nested members; return collection item count."""
    kind = schema['type']
    if kind == 'string':
        if not isinstance(value, str) or not value.strip():
            raise _error('MEMORY_INVALID', f'{path} must be nonempty text.')
        return 0
    if kind == 'array':
        if not isinstance(value, list):
            raise _error('MEMORY_INVALID', f'{path} must be an array.')
        items = cast(list[Any], value)
        if len(items) > MAX_ITEMS:
            raise _error('MEMORY_LIMIT', f'{path} exceeds {MAX_ITEMS} items.')
        return len(items) + sum(_validate(one, schema['items'], f'{path}[]') for one in items)
    if not isinstance(value, dict):
        raise _error('MEMORY_INVALID', f'{path} must be an object.')
    obj = cast(Row, value)
    properties = schema['properties']
    if set(obj) - set(properties) or set(schema['required']) - set(obj):
        raise _error('MEMORY_INVALID', f'{path} has unknown or missing fields.')
    return sum(_validate(one, properties[name], f'{path}.{name}') for name, one in obj.items())


def _request(ctx: Context) -> tuple[list[str], str, str, list[Row], str]:
    nouns = ctx.nouns
    fields = {'node', 'entityNames', 'expectedDigest', 'mutationId', 'mutations'}
    if set(nouns) != fields:
        raise _error('MEMORY_INVALID', 'Expected node, entityNames, expectedDigest, mutationId, mutations.')
    for name in ('node', 'expectedDigest', 'mutationId'):
        _validate(nouns[name], {'type': 'string'}, name)
    expected = str(nouns['expectedDigest'])
    mutation_id = str(nouns['mutationId'])
    if re.fullmatch('[0-9a-f]{64}', expected) is None:
        raise _error('MEMORY_INVALID', 'expectedDigest must be lowercase SHA-256 hex.')
    try:
        mutation_bytes = mutation_id.encode('utf-8')
    except UnicodeError:
        raise _error('MEMORY_INVALID', 'mutationId must be valid UTF-8.') from None
    if len(mutation_bytes) > 256:
        raise _error('MEMORY_LIMIT', 'mutationId exceeds 256 UTF-8 bytes.')
    count = _validate(nouns['entityNames'], NAMES, 'entityNames')
    names = cast(list[str], nouns['entityNames'])
    if not names or len(names) > MAX_NAMES:
        raise _error('MEMORY_LIMIT', f'entityNames must contain 1..{MAX_NAMES} names.')
    if len(names) != len(set(names)):
        raise _error('MEMORY_INVALID', 'entityNames contains duplicate names.')
    if not isinstance(nouns['mutations'], list):
        raise _error('MEMORY_INVALID', 'mutations must be an array.')
    mutations: list[Row] = []
    raw_mutations = cast(list[Any], nouns['mutations'])
    if len(raw_mutations) > MAX_MUTATIONS:
        raise _error('MEMORY_LIMIT', f'mutations exceeds {MAX_MUTATIONS} operations.')
    count += len(raw_mutations)
    for value in raw_mutations:
        if not isinstance(value, dict):
            raise _error('MEMORY_INVALID', 'Each mutation must be an object.')
        one = cast(Row, value)
        if not isinstance(one.get('op'), str) or one['op'] not in OPERATIONS:
            raise _error('MEMORY_INVALID', 'Unknown canonical mutation operation.')
        count += _validate(one, OPERATIONS[one['op']], 'mutations[]')
        mutations.append(one)
    if count > MAX_ITEMS:
        raise _error('MEMORY_LIMIT', f'Batch exceeds {MAX_ITEMS} collection items.')
    try:
        encoded = canonical(nouns)
    except (ValueError, UnicodeError, TypeError):
        raise _error('MEMORY_INVALID', 'Request must be valid UTF-8 JSON.') from None
    if len(encoded) > MAX_BYTES:
        raise _error('MEMORY_LIMIT', f'Batch exceeds {MAX_BYTES} UTF-8 bytes.')
    # Preserve operation and content order in request identity; only the target name set is unordered.
    request_hash = _hash({**nouns, 'entityNames': sorted(names)})
    return sorted(names), expected, mutation_id, mutations, request_hash


def target_digest(tx: TableTx, key: Key, names: list[str]) -> str:
    """Exact named set, absent names included, with incident relations and every functional association."""
    graph = Graph.read(tx, names=names)
    entities: list[Row] = []
    for name in sorted(names):
        if name not in graph.entities:
            entities.append({'name': name, 'absent': True})
            continue
        entity = graph.entity(name)
        entity['observations'] = sorted(entity['observations'])
        if 'cites' in entity:
            entity['cites'] = sorted(entity['cites'])
        entities.append(entity)
    relations = sorted((Graph.relation(row) for row in graph.relations),
                       key=lambda row: (row['from'], row['to'], row['relationType']))
    joins = sorted(({'entity': row['entity'], 'receiver': row['receiver'], 'provider': row['provider']}
                    for row in tx.rows_in('joins', 'entity', names)),
                   key=lambda row: (row['entity'], row['receiver'], row['provider']))
    return _hash({'node': {'receiver': key.receiver, 'provider': key.provider},
                  'entities': entities, 'relations': relations, 'joins': joins})


def _names(tx: TableTx, mutation: Row, key: Key) -> list[str]:
    op = mutation['op']
    if op == 'create_entities':
        return [one['name'] for one in mutation['entities']]
    if op == 'delete_entities':
        return cast(list[str], mutation['entityNames'])
    if op in ('create_relations', 'delete_relations'):
        return [one[end] for one in mutation['relations'] for end in ('from', 'to')]
    if op == 'add_observations':
        return [one['entityName'] for one in mutation['observations']]
    if op == 'delete_observations':
        return [one['entityName'] for one in mutation['deletions']]
    if op == 'join':
        return [mutation['entity']]
    held = tx.get('joins', {'join_id': mutation['id']})
    if held is None:
        return []
    if (held['receiver'], held['provider']) != (key.receiver, key.provider):
        raise _error('MEMORY_SCOPE', 'unjoin must name an association at node.')
    return [held['entity']]


def _mutate(ctx: Context, tx: TableTx, key: Key, mutation: Row) -> list[Row]:
    """Canonical graph helpers on the caller's transaction; delivery acknowledgments follow commit."""
    op = mutation['op']
    graph = Graph.read(tx)
    names = _names(tx, mutation, key)
    # Canonical relation creation permits locked endpoints. All other mutations preserve their locks.
    if op != 'create_relations' and any(graph.locked(name) for name in names):
        raise _error('MEMORY_LOCKED', 'A target memory is locked.')
    by = _written(ctx)
    changed: list[str] = []
    removed: list[Row] = []
    authored_relations: list[Row] = []
    if op == 'create_entities':
        given = _Given(ctx)
        for one in mutation['entities']:
            name = one['name']
            if name in graph.entities:
                continue
            title, why = _titles(ctx, given, one, name, one['observations'])
            _one_fact_each(ctx, [(name, one['observations'])])
            graph.made(tx, name, one['entityType'], title, why)
            _observe(tx, graph, name, one['observations'], by)
            graph.cite(tx, name, _cites(ctx, one), by)
            _join(tx, name, key, by)
            changed.append(name)
    elif op == 'add_observations':
        for one in mutation['observations']:
            name = one['entityName']
            if name not in graph.entities:
                raise _not_found(name)
            _one_fact_each(ctx, [(name, one['contents'])])
            cited = _cites(ctx, one)
            added = _observe(tx, graph, name, one['contents'], by)
            if added:
                cited += _restamped(ctx, graph, name, {row['cite'] for row in cited})
            if graph.cite(tx, name, cited, by) or added:
                changed.append(name)
    elif op == 'delete_observations':
        for one in mutation['deletions']:
            if sum(tx.delete('observations', {'entity': one['entityName'], 'content': content})
                   for content in dict.fromkeys(one['observations'])):
                changed.append(one['entityName'])
        graph = Graph.read(tx)
    elif op in ('create_relations', 'delete_relations'):
        for one in mutation['relations']:
            source, target, kind = one['from'], one['to'], one['relationType']
            identity = {'source': source, 'target': target, 'relation_type': kind}
            if op == 'create_relations':
                for name in (source, target):
                    if name not in graph.entities:
                        raise _not_found(name)
                if tx.get('relations', identity) is None:
                    graph.related(tx, source, target, kind)
                    changed.extend((source, target))
                    authored_relations.append(delivery.component('relations', one))
            elif tx.delete('relations', identity):
                changed.extend((source, target))
                removed.append(delivery.component('deleted_relations', one, name=delivery.relation_name(one),
                                                  requires=delivery.relation_name(one)))
    elif op == 'delete_entities':
        deleted = [name for name in dict.fromkeys(names) if name in graph.entities]
        removed = [delivery.component('deleted_entities', name, name=delivery.entity_name(name),
                                      requires=delivery.entity_name(name)) for name in deleted]
        incident = [Graph.relation(row) for row in graph.relations
                    if row['source'] in deleted or row['target'] in deleted]
        removed += [delivery.component('deleted_relations', row, name=delivery.relation_name(row),
                                       requires=delivery.relation_name(row)) for row in incident]
        if deleted:
            _changed(ctx, tx, [*deleted, *(row[end] for row in incident for end in ('from', 'to'))], removed)
        for name in deleted:
            _forget(tx, graph, name)
    elif op == 'join':
        name = mutation['entity']
        if name not in graph.entities:
            raise _not_found(name)
        if _join(tx, name, key, by) is not None:
            delivery.changed(tx, {(key.receiver, key.provider)}, writer=ctx.session)
    elif op == 'unjoin':
        held = tx.get('joins', {'join_id': mutation['id']})
        if held is not None:
            name = held['entity']
            removed = [delivery.component('withdrawn', {'name': name, **key.said()},
                                          name=f'memory:index:{held["join_id"]}', requires=delivery.entity_name(name))]
            tx.delete('joins', {'join_id': mutation['id']})
            delivery.changed(tx, {(key.receiver, key.provider)}, removed, writer=ctx.session)
    if changed:
        _changed(ctx, tx, changed, removed or None)
    return [*removed, *authored_relations,
            *(_bodies(ctx, graph, changed) if op not in ('create_relations', 'delete_relations') else [])]


def apply(ctx: Context) -> Row:
    names, expected, mutation_id, mutations, request_hash = _request(ctx)
    store = ctx.require_store()
    if store.project_id != ctx.project or project_for(ctx.folder) != ctx.project:
        raise _error('MEMORY_SCOPE', 'Batch must remain in the calling folder project.')
    # A committed receipt survives later map changes, including removal of the target or its base.
    with store.tables(write=False) as reading:
        held = reading.get('apply_receipts', {'mutation_id': mutation_id})
    if held is not None:
        if held['request_hash'] != request_hash:
            raise _error('MEMORY_MUTATION_ID_REUSED', 'mutationId already names different content.')
        return cast(Row, held['receipt'])
    if store.bound_base() is None:
        raise _error('MEMORY_SCOPE', 'Batch target needs an existing map.')
    authored: list[Row] = []
    # Project tables have their own transaction. Keep one TableTx for the comparison, every graph/index write and
    # receipt. Store.atomic serializes map resolution; nesting canonical command handlers would commit separately.
    with store.atomic():
        key = _key(store, ctx.nouns['node'])
        with store.tables() as tx:
            held = tx.get('apply_receipts', {'mutation_id': mutation_id})
            if held is not None:
                if held['request_hash'] != request_hash:
                    raise _error('MEMORY_MUTATION_ID_REUSED', 'mutationId already names different content.')
                return cast(Row, held['receipt'])
            named = set(names)
            for one in mutations:
                if set(_names(tx, one, key)) - named:
                    raise _error('MEMORY_SCOPE', 'Mutation names an entity outside entityNames.')
            before = target_digest(tx, key, names)
            if before != expected:
                raise _error('MEMORY_CONFLICT', f'Expected {expected}, current digest is {before}.')
            earlier = _bodies(ctx, Graph.read(tx, names=names), names)
            for one in mutations:
                authored.extend(_mutate(ctx, tx, key, one))
            receipt = {'mutationId': mutation_id, 'requestHash': request_hash, 'beforeDigest': before,
                       'afterDigest': target_digest(tx, key, names), 'applied': True, 'receiptId': uuid.uuid4().hex}
            tx.insert('apply_receipts', {'mutation_id': mutation_id, 'request_hash': request_hash, 'receipt': receipt})
            # Receipt metadata concerns no memory reader. Graph changes have already supplied precise concerns.
            if not tx.about:
                tx.concern(kind='memory.apply.receipt')
    delivery.authored(ctx, list({one['name']: one for one in authored}.values()), earlier)
    _layered(store)
    return receipt
