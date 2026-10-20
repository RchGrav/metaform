"""CTX-080: migrate persisted prompt records without changing authored text."""
from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from typing import Any, cast

from metaform import home
from metaform.data import Column, Data, DataTx, Operation, Store, StoreError, Table, TableTx

MARKER = 'prompt-terminology-7'
MARKER_TABLE = Table('migrations', key=('name',), columns=(Column('name', required=True), Column('at', required=True)))


def renamed_address(address: str) -> str:
    if address == 'logic' or address.startswith('logic.'):
        return 'prompt' + address[5:]
    if address.startswith('workflow.'):
        return 'prompt.' + address
    return address


def portable(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Convert only the declared v1 envelope; user content and variables stay exact."""
    result = copy.deepcopy(dict(payload))
    if result.get('format') != 'metaform-workflow:1':
        return result
    result['format'] = 'metaform-workflow:2'
    result['workflow']['address'] = renamed_address(result['workflow']['address'])
    result['prompt'] = result.pop('logic')
    for record in result['prompt']:
        record['prompt_id'] = record.pop('logic_id')
        if record['type'] == 'logic':
            record['type'] = 'prompt'
    return result


def _call(call: dict[str, Any]) -> None:
    if 'logic' in call:
        call['prompt'] = call.pop('logic')
        record = call['prompt']
        record['prompt_id'] = record.pop('logic_id')
        if record['type'] == 'logic':
            record['type'] = 'prompt'
    if isinstance(call.get('address'), str):
        call['address'] = renamed_address(call['address'])


def upgrade_tables(tx: TableTx, found: int) -> None:
    """Copy every saved version before the module framework drops its old table."""
    from .runs import upgrade
    if found < 3 and tx.place == 'project':
        upgrade(tx, found)
    if found >= 7:
        return
    if tx.place == 'metaform':
        for row in tx.found_rows('logic_versions', limit=0).results:
            tx.insert('prompt_versions', {'prompt_id': row['logic_id'], 'number': row['number'],
                                         'name': row['name'], 'content': row['content']})
    else:
        for row in tx.rows('runs', limit=0).results:
            changes: dict[str, Any] = {}
            # Only execution frames carry transport records. Arguments, variables and results are user data.
            for column in ('frames', 'branches'):
                value = copy.deepcopy(row[column])
                frames: list[dict[str, Any]] = cast(list[dict[str, Any]], value or []) if column == 'frames' else list(
                    cast(dict[str, dict[str, Any]], value or {}).values())
                for frame in frames or ():
                    if isinstance(frame.get('call'), dict):
                        _call(cast(dict[str, Any], frame['call']))
                if value != row[column]:
                    changes[column] = value
            if changes:
                tx.update('runs', {'run_id': row['run_id']}, changes)


def migrate(tx: DataTx) -> dict[str, int]:
    tables = tx.tables()
    if tables.get('migrations', {'name': MARKER}) is not None:
        return {'items': 0, 'joins': 0, 'elements': 0}
    counts = {'items': 0, 'joins': 0, 'elements': 0}
    reason = 'CTX-080, code.engine.workflow#15: rename stored instructions to prompt.'
    # Check all address collisions before emitting anything. The transaction also rolls back later failures.
    moves = [(ident, row, renamed_address(str(row['address'])))
             for ident, row in tx.base.currents('element')
             if renamed_address(str(row['address'])) != row['address']]
    for ident, _, address in moves:
        other = tx.base.element_at(address)
        if other is not None and other != ident:
            raise StoreError(f'Prompt migration would overwrite {address}. Nothing was changed.',
                             'resolve the address conflict before reopening workflow')
    for ident, row in list(tx.base.currents('item')):
        value: Any = json.loads(row['value']) if isinstance(row['value'], str) else row['value']
        if isinstance(value, dict) and cast(dict[str, Any], value).get('type') == 'logic' and all(
                isinstance(cast(dict[str, Any], value).get(key), str) for key in ('name', 'content')):
            tx.emit('change', 'item', ident, row.layer_id,
                    {**row.fields, 'mode': 'version', 'value': json.dumps({**cast(dict[str, Any], value), 'type': 'prompt'}),
                     'refs': row.refs, 'reason': reason, 'by': row.by})
            counts['items'] += 1
    for ident, row in list(tx.base.currents('join')):
        if row['type'] == 'logic':
            tx.emit('change', 'join', ident, row.layer_id,
                    {**row.fields, 'mode': 'version', 'type': 'prompt', 'refs': row.refs,
                     'reason': reason, 'by': row.by})
            counts['joins'] += 1
    for ident, row, address in moves:
        tx.emit('add', 'element', ident, row.layer_id,
                {**row.fields, 'mode': 'version', 'address': address, 'refs': row.refs,
                 'reason': reason, 'by': row.by})
        counts['elements'] += 1
    for address, layer_id, kind in list(tx.base.selections):
        renamed = renamed_address(address)
        if renamed != address:
            tx.emit('remove', 'selection', layer_id, layer_id,
                    {'address': address, 'layer_id': layer_id, 'kind': kind})
            tx.emit('add', 'selection', layer_id, layer_id,
                    {'address': renamed, 'layer_id': layer_id, 'kind': kind})
    tables.insert('migrations', {'name': MARKER, 'at': home.now()})
    return counts


def prepare_store(store: Store) -> None:
    """Prepare a workflow base once, using indexed marker reads thereafter."""
    if store.bound_base() is None:
        return
    with store.tables(write=False) as tx:
        if tx.get('migrations', {'name': MARKER}) is not None:
            return
    store.workflow_migrate_prompts()


DATA = Data(operations={'workflow_migrate_prompts': Operation(migrate, write=True)})
