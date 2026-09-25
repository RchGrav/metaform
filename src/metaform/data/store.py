"""The data access object: the only code that opens a store or issues SQL, STORE-023.

`Store(project)` reads and writes the active metaform of one registered
project. Writes are STORE-024, reads are STORE-025. Every write is one
transaction; every read is one read transaction and goes through an index,
STORE-005. Selection, masking, hiding and the transitive rules of properties
are applied here, inside every read, so no caller computes or bypasses them,
STORE-019.
"""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from .. import home
from ..errors import StoreError
from . import corrections
from .ids import (check_address, check_layer_name, check_tag, decode_extra, encode_extra, encode_value, is_id,
                  new_id, prefixes, refs_list)
from .records import (ChallengeState, Citation, ContextView, Descriptor, Element, Item, Join, Layer, LayerGroup,
                      Node, NodeView, Page, Plan, Property, Provenance, Ref, Selection, Subtype, Version, Where)
from .selection import LAYER_COLUMNS, LayerRow, Resolver, all_layers, hidden_closure, layer_row, resolve_names
from .session import Session, Tx

LIMIT = 500
ROLES = ('AUE', 'VE', 'DE', 'SE', 'NE')
SUBTYPE_ROLES = ('DE', 'SE', 'NE')
METAFORM_KINDS = corrections.METAFORM_KINDS
EDITABLE = {
    'element': ('address', 'extra'),
    'join': ('provider', 'type', 'purpose', 'function', 'relation', 'observation', 'non_goal', 'extra'),
    'subtype': ('address', 'name', 'name_length', 'role', 'function', 'relation', 'observation', 'extra'),
    'item': ('value', 'link', 'extra'),
    'property': ('element', 'value', 'extra'),
}


def _correct_step(thing: str = '<id>') -> str:
    return f'metaform map knowledge op=correct layer=<correction layer> id={thing} reason=<why>'


class Store:
    """Reads and writes one project's active metaform."""

    def __init__(self, project: str, *, toggled: Sequence[str] | None = None) -> None:
        record = home.project(project)
        if record is None:
            raise StoreError(f'No project {project} is registered.', 'metaform list projects')
        self._record = record
        self._session = Session(record.project_id)
        self.toggled: tuple[str, ...] = tuple(toggled or ())

    # ------------------------------------------------------------------ plumbing

    @property
    def project_id(self) -> str:
        return self._record.project_id

    @contextmanager
    def atomic(self) -> Iterator[None]:
        """Every write inside the block commits together, or none does, STORE-024."""
        with self._session.atomic():
            yield

    @contextmanager
    def _write(self) -> Iterator[Tx]:
        try:
            with self._session.write() as tx:
                yield tx
        except sqlite3.IntegrityError as error:
            raise StoreError(f'The write does not fit the store: {error}.', 'metaform help map knowledge') from None

    @contextmanager
    def _read(self) -> Iterator[Tx]:
        with self._session.read() as tx:
            yield tx

    def _layer(self, tx: Tx, ref: str) -> LayerRow:
        if not isinstance(ref, str) or not ref:
            raise StoreError('Every write names its layer.', 'metaform map layers')
        column = 'layer_id' if is_id(ref) else 'name'
        row = tx.db.execute(f'SELECT {LAYER_COLUMNS} FROM layers WHERE {column}=?', (ref,)).fetchone()
        if row is None:
            raise StoreError(f'No layer {ref}.', 'metaform map layers')
        return layer_row(row)

    def _layer_name(self, tx: Tx, layer_id: str) -> str:
        row = tx.db.execute('SELECT name FROM layers WHERE layer_id=?', (layer_id,)).fetchone()
        return str(row[0]) if row else layer_id

    def _writable(self, tx: Tx, layer: LayerRow) -> None:
        """Writes into a layer are refused only for the intake and a finished correction layer, STORE-032."""
        if layer.kind == 'intake' and layer.layer_id not in tx.created:
            raise StoreError(f'{layer.name} is the intake layer; the metaform changes only through a correction '
                             'layer.', _correct_step())
        if layer.kind == 'correction' and layer.finished:
            raise StoreError(f'Correction layer {layer.name} is finished; only the top correction layer can be '
                             'peeled and changed.', _correct_step())

    @staticmethod
    def _top(tx: Tx) -> int:
        return corrections.top_position(tx.db)

    @staticmethod
    def _types(tx: Tx, address: str) -> None:
        parent = None
        for prefix in prefixes(address):
            tx.db.execute('INSERT OR IGNORE INTO types(address, parent) VALUES (?, ?)', (prefix, parent))
            parent = prefix

    @staticmethod
    def _identity(tx: Tx, thing_id: str, kind: str) -> None:
        tx.db.execute('INSERT INTO identities(id, kind) VALUES (?, ?)', (thing_id, kind))

    @staticmethod
    def _write_refs(tx: Tx, owner: str, row: int, refs: Iterable[tuple[str, str]], start: int = 0) -> None:
        tx.db.executemany('INSERT INTO refs(owner, owner_row, position, key, value) VALUES (?, ?, ?, ?, ?)',
                          [(owner, row, start + index, key, value) for index, (key, value) in enumerate(refs)])

    @staticmethod
    def _refs(db: sqlite3.Connection, owner: str, row: int) -> tuple[Ref, ...]:
        return tuple(Ref(ref['key'], ref['value']) for ref in db.execute(
            'SELECT key, value FROM refs WHERE owner=? AND owner_row=? ORDER BY position', (owner, row)))

    # ----------------------------------------------------------- resolving refs

    def _current_element(self, tx: Tx, ref: str) -> sqlite3.Row | None:
        column = 'element_id' if is_id(ref) else 'address'
        return tx.db.execute(f'SELECT element_id, row, address, moved FROM current_elements WHERE {column}=?',
                             (ref,)).fetchone()

    def _element_id(self, tx: Tx, ref: Any, layer: LayerRow, what: str) -> str:
        """An element named by address or id: current, or written in this building correction layer."""
        if isinstance(ref, Node):
            if ref.kind != 'element':
                raise StoreError(f'{ref} is a {ref.kind}; {what} must be an element.', 'metaform map where <address>')
            ref = ref.id
        if not isinstance(ref, str) or not ref:
            raise StoreError(f'{what} must name an element by address or id.', 'metaform map where <address>')
        current = self._current_element(tx, ref)
        if current is not None:
            return str(current['element_id'])
        if layer.kind == 'correction':
            column = 'element_id' if is_id(ref) else 'address'
            row = tx.db.execute(f"SELECT element_id FROM elements WHERE {column}=? AND layer_id=? AND op != 'remove'",
                                (ref, layer.layer_id)).fetchone()
            if row is not None:
                return str(row[0])
        if self._is_subtype(tx, ref):
            raise StoreError(f'{ref} is a subtype, reached only through its join; a subtype is never a join end or '
                             'an element.', f'metaform map where {ref}')
        raise StoreError(f'{ref} is not an element in this project.',
                         f'metaform map knowledge op=add-element layer={layer.name} address={ref}')

    @staticmethod
    def _is_subtype(tx: Tx, ref: str) -> bool:
        if is_id(ref):
            return tx.db.execute('SELECT 1 FROM subtype_ids WHERE subtype_id=?', (ref,)).fetchone() is not None
        return tx.db.execute('SELECT 1 FROM current_subtypes WHERE address=?', (ref,)).fetchone() is not None

    def _node_id(self, tx: Tx, node: Node, layer: LayerRow | None = None) -> str:
        """The identity id of a node that exists now."""
        if not isinstance(node, Node):
            raise StoreError(f'{node!r} is not a node: give element:, join: or subtype:.', 'metaform help map node')
        if node.kind == 'element':
            current = self._current_element(tx, node.id)
            if current is not None:
                return str(current['element_id'])
        elif node.kind == 'join':
            if is_id(node.id):
                if tx.db.execute('SELECT 1 FROM current_joins WHERE join_id=?', (node.id,)).fetchone():
                    return node.id
                if layer is not None and tx.db.execute('SELECT 1 FROM joins WHERE join_id=? AND layer_id=?',
                                                       (node.id, layer.layer_id)).fetchone():
                    return node.id
        else:
            column = 'subtype_id' if is_id(node.id) else 'address'
            row = tx.db.execute(f'SELECT subtype_id FROM current_subtypes WHERE {column}=?', (node.id,)).fetchone()
            if row is not None:
                return str(row[0])
        if node.kind == 'element':
            step = f'metaform map knowledge op=add-element layer={layer.name if layer else "<layer>"} address={node.id}'
        else:
            step = f'metaform map where {node.id}'
        raise StoreError(f'{node} is not a current {node.kind} in this project.', step)

    def _kind_of(self, tx: Tx, thing: str) -> str:
        """A bare id's kind, STORE-033: identities first, then properties, which have no identity row."""
        if not isinstance(thing, str) or not is_id(thing):
            raise StoreError(f'{thing!r} is not an id.', 'metaform map where <address>')
        row = tx.db.execute('SELECT kind FROM identities WHERE id=?', (thing,)).fetchone()
        if row is not None:
            return str(row[0])
        if tx.db.execute('SELECT 1 FROM properties WHERE property_id=? LIMIT 1', (thing,)).fetchone():
            return 'property'
        raise StoreError(f'No element, join, subtype, property or item has the id {thing}.',
                         'metaform map where <address>')

    def _own_row(self, tx: Tx, kind: str, thing: str) -> tuple[sqlite3.Row, LayerRow]:
        """The row a thing was added with, and the layer that added it."""
        spec = corrections.KINDS[kind]
        rows = tx.db.execute(f'SELECT * FROM {spec.table} WHERE {spec.id_column}=?', (thing,)).fetchall()
        added = [row for row in rows if row['op'] == 'add']
        if not added:
            raise StoreError(f'No {kind} has the id {thing}.', 'metaform map where <address>')
        row = added[-1]
        return row, self._layer(tx, row['layer_id'])

    # ------------------------------------------------------------------ layers

    def layer(self, name: str, module: str, variable: str, *, kind: str = 'layer', mutable: bool, hideable: bool,
              fields: Sequence[str] = (), tags: Sequence[str] = (), provenance: dict[str, Any] | None = None,
              result_id: str | None = None, sources: Sequence[str] = (), ready: bool = False) -> Layer:
        """Create a layer, or return the one with this name and the same declaration, STORE-024."""
        check_layer_name(name)
        if kind not in ('layer', 'intake', 'memory', 'correction'):
            raise StoreError(f'{kind!r} is not a layer kind: use layer, intake, memory or correction.',
                             'metaform help map knowledge')
        if not isinstance(variable, str) or not variable.strip():
            raise StoreError(f'Layer {name} needs its variable: the one question it answers.',
                             f'metaform map knowledge op=create layer={name} variable=<question> mutable=true '
                             'hideable=true')
        if kind != 'memory' and not provenance:
            raise StoreError(f'Layer {name} needs its provenance: module, workflow, prompt, model, role, blinded.',
                             f'metaform map knowledge op=create layer={name} module=<module> prompt=<prompt>')
        if kind == 'correction' and (mutable or hideable):
            raise StoreError('A correction layer is immutable and never hideable.',
                             f'metaform map knowledge op=create layer={name} kind=correction mutable=false '
                             'hideable=false')
        for tag in tags:
            check_tag(tag)
        with self._write() as tx:
            existing = tx.db.execute(f'SELECT {LAYER_COLUMNS} FROM layers WHERE name=?', (name,)).fetchone()
            if existing is not None:
                found = layer_row(existing)
                if (found.kind, found.module, found.variable, found.mutable, found.hideable) == (
                        kind, module, variable, bool(mutable), bool(hideable)):
                    return self._layer_record(tx, found)
                raise StoreError(f'Layer {name} exists with a different declaration.', 'metaform map layers')
            source_ids = resolve_names(tx.db, all_layers(tx.db), sources) if sources else []
            layer_id = new_id()
            stamp = home.now()
            tx.db.execute('INSERT INTO layers(layer_id, metaform_id, name, module, variable, mutable, hideable, '
                          'result_id, kind, created, ready) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                          (layer_id, tx.metaform_id, name, module, variable, int(bool(mutable)), int(bool(hideable)),
                           result_id, kind, stamp, stamp if (ready or kind == 'memory') else None))
            if provenance and kind != 'memory':
                blinded = provenance.get('blinded')
                tx.db.execute('INSERT INTO provenance(layer_id, module, workflow, prompt, model, role, blinded) '
                              'VALUES (?, ?, ?, ?, ?, ?, ?)',
                              (layer_id, str(provenance.get('module') or module), provenance.get('workflow'),
                               provenance.get('prompt'), provenance.get('model'), provenance.get('role'),
                               None if blinded is None else int(bool(blinded))))
            tx.db.executemany('INSERT INTO layer_fields(layer_id, position, name) VALUES (?, ?, ?)',
                              [(layer_id, index, field) for index, field in enumerate(fields)])
            tx.db.executemany('INSERT OR IGNORE INTO layer_tags(layer_id, tag) VALUES (?, ?)',
                              [(layer_id, tag) for tag in tags])
            tx.db.executemany('INSERT OR IGNORE INTO layer_sources(layer_id, source_layer_id) VALUES (?, ?)',
                              [(layer_id, source) for source in source_ids])
            tx.created.add(layer_id)
            return self._layer_record(tx, self._layer(tx, layer_id))

    def finish(self, layer: str) -> Layer:
        """Mark a layer ready; a correction layer is also applied on top of the stack, STORE-017."""
        with self._write() as tx:
            found = self._layer(tx, layer)
            if found.finished:
                raise StoreError(f'Layer {found.name} is already finished.', 'metaform map layers')
            if found.kind == 'correction':
                corrections.apply(tx.db, found.layer_id, found.name)
            tx.db.execute('UPDATE layers SET ready=? WHERE layer_id=?', (home.now(), found.layer_id))
            return self._layer_record(tx, self._layer(tx, found.layer_id))

    def discard(self, layer: str) -> None:
        """Delete a knowledge layer's content and the layer; identity and type rows stay, STORE-032."""
        with self._write() as tx:
            found = self._layer(tx, layer)
            if found.kind in ('intake', 'memory'):
                raise StoreError(f'Layer {found.name} is the {found.kind} layer and is never discarded.',
                                 _correct_step() if found.kind == 'intake' else 'metaform memory delete-entities <node>')
            if found.kind == 'correction' and tx.db.execute('SELECT 1 FROM correction_stack WHERE layer_id=?',
                                                            (found.layer_id,)).fetchone():
                raise StoreError(f'Correction layer {found.name} is on the stack.',
                                 f'metaform map knowledge op=peel layer={found.name}')
            db = tx.db
            layer_id = found.layer_id
            owners = {'element': 'elements', 'join': 'joins', 'subtype': 'subtypes', 'property': 'properties',
                      'item': 'items'}
            for owner, table in owners.items():
                spec = corrections.KINDS[owner]
                for row in db.execute(f'SELECT row, {spec.id_column} FROM {table} WHERE layer_id=?',
                                      (layer_id,)).fetchall():
                    db.execute('DELETE FROM refs WHERE owner=? AND owner_row=?', (owner, row[0]))
                    db.execute(f'DELETE FROM {spec.current} WHERE row=?', (row[0],))
                    if owner == 'item':
                        db.execute('DELETE FROM challenge_states WHERE item_id=?', (row[1],))
                    db.execute(f'DELETE FROM {table} WHERE row=?', (row[0],))
                    if owner == 'item':
                        # item_ids names the item's layer, so it goes with the layer; identities keeps the id.
                        db.execute('DELETE FROM item_ids WHERE item_id=? AND layer_id=?', (row[1], layer_id))
            db.execute('DELETE FROM plans WHERE layer_id=?', (layer_id,))
            db.execute('DELETE FROM selections WHERE layer_id=?', (layer_id,))
            for table in ('hidden_layers', 'layer_tags', 'layer_fields', 'provenance'):
                db.execute(f'DELETE FROM {table} WHERE layer_id=?', (layer_id,))
            db.execute('DELETE FROM layer_sources WHERE layer_id=?', (layer_id,))
            db.execute('DELETE FROM layer_sources WHERE source_layer_id=?', (layer_id,))
            for other in all_layers(db):
                db.execute('DELETE FROM reexamine WHERE layer_id=? AND correction_layer_id=?', (other, layer_id))
            db.execute('DELETE FROM reexamine WHERE layer_id=?', (layer_id,))
            db.execute('DELETE FROM layers WHERE layer_id=?', (layer_id,))

    def hide(self, layer: str) -> None:
        with self._write() as tx:
            found = self._hideable(tx, layer)
            tx.db.execute('INSERT OR IGNORE INTO hidden_layers(layer_id) VALUES (?)', (found.layer_id,))

    def unhide(self, layer: str) -> None:
        with self._write() as tx:
            found = self._hideable(tx, layer)
            tx.db.execute('DELETE FROM hidden_layers WHERE layer_id=?', (found.layer_id,))

    def _hideable(self, tx: Tx, layer: str) -> LayerRow:
        found = self._layer(tx, layer)
        if not found.hideable:
            raise StoreError(f'Layer {found.name} is not hideable.', f'metaform map layers kind={found.kind}')
        return found

    def tag(self, layer: str, tag: str) -> None:
        check_tag(tag)
        with self._write() as tx:
            found = self._layer(tx, layer)
            tx.db.execute('INSERT OR IGNORE INTO layer_tags(layer_id, tag) VALUES (?, ?)', (found.layer_id, tag))

    def untag(self, layer: str, tag: str) -> None:
        with self._write() as tx:
            found = self._layer(tx, layer)
            tx.db.execute('DELETE FROM layer_tags WHERE layer_id=? AND tag=?', (found.layer_id, tag))

    def reexamined(self, layer: str) -> None:
        with self._write() as tx:
            found = self._layer(tx, layer)
            tx.db.execute('DELETE FROM reexamine WHERE layer_id=?', (found.layer_id,))

    def _selectable(self, tx: Tx, layer: str) -> LayerRow:
        found = self._layer(tx, layer)
        if found.kind == 'correction':
            raise StoreError(f'{found.name} is a correction layer; correction layers are always applied and are '
                             'never selected, masked or hidden.', 'metaform map stack')
        return found

    def select(self, address: str, layer: str) -> None:
        self._selection(address, layer, 'select')

    def mask(self, address: str, layer: str) -> None:
        self._selection(address, layer, 'mask')

    def _selection(self, address: str, layer: str, kind: str) -> None:
        check_address(address)
        with self._write() as tx:
            found = self._selectable(tx, layer)
            self._types(tx, address)
            tx.db.execute('INSERT OR IGNORE INTO selections(address, layer_id, kind) VALUES (?, ?, ?)',
                          (address, found.layer_id, kind))

    def clear(self, address: str, layer: str, kind: str) -> None:
        if kind not in ('select', 'mask'):
            raise StoreError(f'{kind!r} is not select or mask.', f'metaform map clear {address} {layer} mask')
        with self._write() as tx:
            found = self._selectable(tx, layer)
            tx.db.execute('DELETE FROM selections WHERE address=? AND kind=? AND layer_id=?',
                          (address, kind, found.layer_id))

    # ---------------------------------------------------------------- the map

    def add_element(self, layer: str, address: str, *, name: str | None = None, name_length: int | None = None,
                    role: str | None = None, refs: Iterable[Any] = (), extra: dict[str, Any] | None = None) -> Element:
        """Write an element, or return the one already at the address, STORE-009."""
        pairs = refs_list(refs)
        with self._write() as tx:
            found = self._layer(tx, layer)
            self._writable(tx, found)
            check_address(address, found.name)
            encoded_extra = encode_extra(extra, address)
            descriptor = {key: value for key, value in (('name', name), ('name_length', name_length),
                                                        ('role', role)) if value is not None}
            current = self._current_element(tx, address)
            if current is not None:
                element_id = str(current['element_id'])
                differs = self._descriptor_differs(tx, element_id, descriptor)
                if (descriptor or pairs) and not self._has_descriptor(tx, element_id, found.layer_id):
                    self._write_descriptor(tx, found, element_id, descriptor, pairs)
                record = self._element_record(tx, element_id, None)
                assert record is not None
                return _replace(record, existing=True, differs=differs)
            if self._is_subtype(tx, address):
                raise StoreError(f'{address} is held by a subtype; an address holds one element or one subtype.',
                                 f'metaform map where {address}')
            element_id = self._reused_element(tx, found, address) or new_id()
            if tx.db.execute('SELECT 1 FROM element_ids WHERE element_id=?', (element_id,)).fetchone() is None:
                tx.db.execute('INSERT INTO element_ids(element_id) VALUES (?)', (element_id,))
                self._identity(tx, element_id, 'element')
            self._types(tx, address)
            cursor = tx.db.execute('INSERT INTO elements(element_id, layer_id, address, extra) VALUES (?, ?, ?, ?)',
                                   (element_id, found.layer_id, address, encoded_extra))
            if found.kind != 'correction':
                tx.db.execute('INSERT INTO current_elements(element_id, row, address, moved) VALUES (?, ?, ?, 0)',
                              (element_id, cursor.lastrowid, address))
            if descriptor or pairs:
                self._write_descriptor(tx, found, element_id, descriptor, pairs)
            if found.kind == 'correction':
                return Element(element_id, address, found.layer_id, found.name,
                               descriptor.get('name'), descriptor.get('name_length'), descriptor.get('role'),
                               extra=extra)
            record = self._element_record(tx, element_id, None)
            assert record is not None
            return record

    def _reused_element(self, tx: Tx, layer: LayerRow, address: str) -> str | None:
        """A correction layer's add at an address whose element was removed reuses that element, STORE-017."""
        if layer.kind != 'correction':
            return None
        rows = tx.db.execute("SELECT element_id, row FROM elements WHERE address=? AND op='remove' ORDER BY row DESC",
                             (address,)).fetchall()
        for row in rows:
            if tx.db.execute('SELECT 1 FROM current_elements WHERE element_id=?', (row[0],)).fetchone() is None:
                return str(row[0])
        return None

    def _has_descriptor(self, tx: Tx, element_id: str, layer_id: str) -> bool:
        for row in tx.db.execute('SELECT i.value FROM current_items c JOIN items i ON i.row = c.row '
                                 "WHERE c.target_kind='element' AND c.target_id=? AND c.layer_id=?",
                                 (element_id, layer_id)):
            value = json.loads(row[0])
            if isinstance(value, dict) and 'descriptor' in value:
                return True
        return False

    def _descriptor_differs(self, tx: Tx, element_id: str, descriptor: dict[str, Any]) -> bool:
        if not descriptor:
            return False
        for row in tx.db.execute('SELECT i.value FROM current_items c JOIN items i ON i.row = c.row '
                                 "WHERE c.target_kind='element' AND c.target_id=?", (element_id,)):
            value = json.loads(row[0])
            if isinstance(value, dict) and isinstance(value.get('descriptor'), dict):
                known = value['descriptor']
                return any(known.get(key) != given for key, given in descriptor.items())
        return True

    def _write_descriptor(self, tx: Tx, layer: LayerRow, element_id: str, descriptor: dict[str, Any],
                          pairs: list[tuple[str, str]]) -> None:
        self._insert_item(tx, layer, 'element', element_id, {'descriptor': descriptor}, None, None, pairs, None)

    def add_join(self, layer: str, receiver: Any, provider: Any, *, purpose: str | None, function: str | None,
                 relation: str | None, observation: str | None, non_goal: str | None = None, type: str = 'purpose',
                 refs: Iterable[Any] = (), extra: dict[str, Any] | None = None) -> Join:
        """Write one join, owned by its receiver and served by its provider, STORE-010."""
        pairs = refs_list(refs)
        with self._write() as tx:
            found = self._layer(tx, layer)
            self._writable(tx, found)
            receiver_id = self._element_id(tx, receiver, found, 'The receiver')
            provider_id = self._element_id(tx, provider, found, 'The provider')
            if receiver_id == provider_id:
                raise StoreError(f'A join runs from a receiver to a different provider; {receiver} cannot serve '
                                 'itself.', 'metaform help map knowledge')
            if not isinstance(type, str) or not type:
                raise StoreError('A join needs a type.', 'metaform help map knowledge')
            if type != 'purpose':
                check_address(type, found.name)
            encoded_extra = encode_extra(extra, 'the join')
            join_id = new_id()
            tx.db.execute('INSERT INTO join_ids(join_id, receiver) VALUES (?, ?)', (join_id, receiver_id))
            self._identity(tx, join_id, 'join')
            cursor = tx.db.execute(
                'INSERT INTO joins(join_id, layer_id, type, receiver, provider, purpose, function, relation, '
                'observation, non_goal, extra, stack_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (join_id, found.layer_id, type, receiver_id, provider_id, purpose, function, relation, observation,
                 non_goal, encoded_extra, self._top(tx)))
            row = int(cursor.lastrowid or 0)
            if found.kind != 'correction':
                tx.db.execute('INSERT INTO current_joins(join_id, row, receiver, provider) VALUES (?, ?, ?, ?)',
                              (join_id, row, receiver_id, provider_id))
            self._write_refs(tx, 'join', row, pairs)
            return self._join_record(tx, tx.db.execute('SELECT * FROM joins WHERE row=?', (row,)).fetchone(),
                                     all_layers(tx.db))

    def add_subtype(self, layer: str, join: str, address: str, *, function: str | None = None,
                    relation: str | None = None, observation: str | None = None, name: str | None = None,
                    name_length: int | None = None, role: str | None = None, refs: Iterable[Any] = (),
                    extra: dict[str, Any] | None = None, purpose: str | None = None) -> Subtype:
        """Write a subtype inside the one join it shares with its parent; it has no purpose, STORE-011."""
        pairs = refs_list(refs)
        with self._write() as tx:
            found = self._layer(tx, layer)
            self._writable(tx, found)
            if purpose is not None:
                raise StoreError(f'Subtype {address} has a purpose; a subtype has none of its own. A part with its '
                                 'own purpose is its own element with its own join.',
                                 f'metaform map knowledge op=add-element layer={found.name} address={address}')
            check_address(address, found.name)
            if role is not None and role not in SUBTYPE_ROLES:
                raise StoreError(f'{role!r} is not a subtype role: use DE, SE or NE.', 'metaform help map knowledge')
            join_id = self._node_id(tx, Node('join', join), found) if is_id(join) else None
            if join_id is None:
                raise StoreError(f'{join} is not a join in this project.', 'metaform map joins <element>')
            if tx.db.execute('SELECT 1 FROM current_subtypes WHERE address=?', (address,)).fetchone() or \
                    self._current_element(tx, address) is not None:
                raise StoreError(f'{address} is already held by an element or a subtype.', f'metaform map where {address}')
            encoded_extra = encode_extra(extra, address)
            subtype_id = new_id()
            tx.db.execute('INSERT INTO subtype_ids(subtype_id, join_id) VALUES (?, ?)', (subtype_id, join_id))
            self._identity(tx, subtype_id, 'subtype')
            self._types(tx, address)
            cursor = tx.db.execute(
                'INSERT INTO subtypes(subtype_id, layer_id, address, name, name_length, role, function, relation, '
                'observation, extra) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (subtype_id, found.layer_id, address, name, name_length, role, function, relation, observation,
                 encoded_extra))
            row = int(cursor.lastrowid or 0)
            if found.kind != 'correction':
                tx.db.execute('INSERT INTO current_subtypes(subtype_id, row, join_id, address) VALUES (?, ?, ?, ?)',
                              (subtype_id, row, join_id, address))
            self._write_refs(tx, 'subtype', row, pairs)
            return self._subtype_record(tx, tx.db.execute('SELECT * FROM subtypes WHERE row=?', (row,)).fetchone(),
                                        join_id, all_layers(tx.db))

    def add_ref(self, owner: str, key: str, value: str) -> Ref:
        """Add one ref to a thing's current version in a knowledge or mutable layer, STORE-012."""
        (key, value), = refs_list([(key, value)])
        with self._write() as tx:
            kind = self._kind_of(tx, owner)
            spec = corrections.KINDS[kind]
            current = tx.db.execute(f'SELECT row FROM {spec.current} WHERE {spec.id_column}=?', (owner,)).fetchone()
            if current is None:
                raise StoreError(f'{owner} has no current version.', 'metaform map where <address>')
            layer_id = tx.db.execute(f'SELECT layer_id FROM {spec.table} WHERE row=?', (current[0],)).fetchone()[0]
            found = self._layer(tx, layer_id)
            if found.kind in METAFORM_KINDS and not (found.kind == 'intake' and found.layer_id in tx.created):
                raise StoreError(f'{owner} belongs to {found.name}; its refs change only through a correction layer.',
                                 _correct_step(owner))
            last = tx.db.execute('SELECT MAX(position) FROM refs WHERE owner=? AND owner_row=?',
                                 (kind, current[0])).fetchone()[0]
            self._write_refs(tx, kind, current[0], [(key, value)], start=(last + 1) if last is not None else 0)
            return Ref(key, value)

    # ---------------------------------------------------------------- items

    def _insert_item(self, tx: Tx, layer: LayerRow, target_kind: str, target_id: str, value: Any,
                     link_kind: str | None, link_id: str | None, pairs: list[tuple[str, str]],
                     extra: dict[str, Any] | None) -> str:
        encoded = encode_value(value, f'{target_kind}:{target_id}')
        encoded_extra = encode_extra(extra, 'the item')
        item_id = new_id()
        tx.db.execute('INSERT INTO item_ids(item_id, layer_id) VALUES (?, ?)', (item_id, layer.layer_id))
        self._identity(tx, item_id, 'item')
        cursor = tx.db.execute('INSERT INTO items(item_id, layer_id, target_kind, target_id, value, link_kind, link_id, '
                               'extra) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                               (item_id, layer.layer_id, target_kind, target_id, encoded, link_kind, link_id,
                                encoded_extra))
        row = int(cursor.lastrowid or 0)
        if layer.kind != 'correction':
            tx.db.execute('INSERT INTO current_items(item_id, row, layer_id, target_kind, target_id, link_kind, '
                          'link_id) VALUES (?, ?, ?, ?, ?, ?, ?)',
                          (item_id, row, layer.layer_id, target_kind, target_id, link_kind, link_id))
        self._write_refs(tx, 'item', row, pairs)
        return item_id

    def add_item(self, layer: str, target: Node, value: Any, *, link: Node | None = None, refs: Iterable[Any] = (),
                 extra: dict[str, Any] | None = None) -> Item:
        """Attach one value of the layer's variable at one node, with an optional link to another, STORE-015."""
        pairs = refs_list(refs)
        with self._write() as tx:
            found = self._layer(tx, layer)
            self._writable(tx, found)
            target_id = self._node_id(tx, target, found)
            link_id = self._node_id(tx, link, found) if link is not None else None
            item_id = self._insert_item(tx, found, target.kind, target_id, value,
                                        link.kind if link is not None else None, link_id, pairs, extra)
            return self._item_by_id(tx, item_id)

    def add_property(self, layer: str, element: Any, value: Any, *, refs: Iterable[Any] = (),
                     extra: dict[str, Any] | None = None) -> Property:
        """Attach a property to an element; it travels the namespace and has no join, STORE-039."""
        pairs = refs_list(refs)
        with self._write() as tx:
            found = self._layer(tx, layer)
            self._writable(tx, found)
            element_id = self._element_id(tx, element, found, 'A property')
            encoded = encode_value(value, f'the property of {element}')
            encoded_extra = encode_extra(extra, 'the property')
            property_id = new_id()
            cursor = tx.db.execute('INSERT INTO properties(property_id, layer_id, element_id, value, extra) '
                                   'VALUES (?, ?, ?, ?, ?)', (property_id, found.layer_id, element_id, encoded,
                                                              encoded_extra))
            row = int(cursor.lastrowid or 0)
            if found.kind != 'correction':
                tx.db.execute('INSERT INTO current_properties(property_id, row, layer_id, element_id) '
                              'VALUES (?, ?, ?, ?)', (property_id, row, found.layer_id, element_id))
            self._write_refs(tx, 'property', row, pairs)
            return self._property_record(tx, tx.db.execute('SELECT * FROM properties WHERE row=?', (row,)).fetchone(),
                                         all_layers(tx.db))

    def update_item(self, item: str, value: Any) -> Item:
        """Change a memory in place, with no history, STORE-018."""
        with self._write() as tx:
            row, found = self._memory_item(tx, item)
            tx.db.execute('UPDATE items SET value=? WHERE row=?', (encode_value(value, item), row['row']))
            return self._item_by_id(tx, item)

    def delete_item(self, item: str) -> None:
        with self._write() as tx:
            row, _ = self._memory_item(tx, item)
            tx.db.execute('DELETE FROM refs WHERE owner=? AND owner_row=?', ('item', row['row']))
            tx.db.execute('DELETE FROM current_items WHERE item_id=?', (item,))
            tx.db.execute('DELETE FROM items WHERE row=?', (row['row'],))

    def _memory_item(self, tx: Tx, item: str) -> tuple[sqlite3.Row, LayerRow]:
        if self._kind_of(tx, item) != 'item':
            raise StoreError(f'{item} is not an item.', 'metaform memory open-nodes <node>')
        row, found = self._own_row(tx, 'item', item)
        if found.kind != 'memory':
            raise StoreError(f'{item} is in {found.name}, which is not memory; change it with edit or remove.',
                             f'metaform map knowledge op=edit layer={found.name} id={item} value=<value>')
        return row, found

    # ------------------------------------------------------------- edit, remove

    def edit(self, thing: str, changes: dict[str, Any]) -> Version:
        """Change a thing of a knowledge layer, or of a building correction layer, in place, STORE-032."""
        with self._write() as tx:
            kind = self._kind_of(tx, thing)
            row, found = self._own_row(tx, kind, thing)
            self._editable(tx, found, thing)
            self._allowed(kind, changes)
            spec = corrections.KINDS[kind]
            columns = self._changed_columns(tx, kind, row, changes, found)
            refs = changes.get('refs')
            if columns:
                assignments = ', '.join(f'{column}=?' for column in columns)
                tx.db.execute(f'UPDATE {spec.table} SET {assignments} WHERE row=?', (*columns.values(), row['row']))
            if refs is not None:
                tx.db.execute('DELETE FROM refs WHERE owner=? AND owner_row=?', (kind, row['row']))
                self._write_refs(tx, kind, row['row'], refs_list(refs))
            if tx.db.execute(f'SELECT 1 FROM {spec.current} WHERE row=?', (row['row'],)).fetchone():
                updated = tx.db.execute(f'SELECT * FROM {spec.table} WHERE row=?', (row['row'],)).fetchone()
                tx.db.execute(f'DELETE FROM {spec.current} WHERE row=?', (row['row'],))
                corrections.insert_current(tx.db, kind, thing, updated, self._moved(tx, kind, thing))
            return self._version(tx, kind, tx.db.execute(f'SELECT * FROM {spec.table} WHERE row=?',
                                                         (row['row'],)).fetchone(), {})

    @staticmethod
    def _moved(tx: Tx, kind: str, thing: str) -> int:
        if kind != 'element':
            return 0
        row = tx.db.execute('SELECT moved FROM current_elements WHERE element_id=?', (thing,)).fetchone()
        return int(row[0]) if row else 0

    def _editable(self, tx: Tx, found: LayerRow, thing: str) -> None:
        if found.kind == 'memory':
            raise StoreError(f'{thing} is a memory; change it with the memory operations.',
                             'metaform memory open-nodes <node>')
        if found.kind == 'intake' or (found.kind == 'correction' and found.finished):
            raise StoreError(f'{thing} belongs to {found.name}; the metaform changes only through a correction layer.',
                             _correct_step(thing))

    @staticmethod
    def _allowed(kind: str, changes: dict[str, Any]) -> None:
        if not isinstance(changes, dict) or not changes:
            raise StoreError('Name at least one field to change.', 'metaform help map knowledge')
        for key in changes:
            if key != 'refs' and key not in EDITABLE[kind]:
                raise StoreError(f'{key} cannot be changed on a {kind}; the fields are '
                                 f'{", ".join(EDITABLE[kind])} and refs.', 'metaform help map knowledge')

    def _changed_columns(self, tx: Tx, kind: str, row: sqlite3.Row, changes: dict[str, Any],
                         layer: LayerRow) -> dict[str, Any]:
        columns: dict[str, Any] = {}
        for key, value in changes.items():
            if key == 'refs':
                continue
            if key == 'extra':
                columns['extra'] = encode_extra(value, kind)
            elif key == 'value':
                columns['value'] = encode_value(value, kind)
            elif key == 'address':
                check_address(value, layer.name)
                self._types(tx, value)
                columns['address'] = value
            elif key == 'provider':
                columns['provider'] = self._element_id(tx, value, layer, 'The provider')
            elif key == 'element':
                columns['element_id'] = self._element_id(tx, value, layer, 'A property')
            elif key == 'link':
                if value is None:
                    columns['link_kind'], columns['link_id'] = None, None
                else:
                    link = value if isinstance(value, Node) else Node.parse(str(value))
                    columns['link_kind'], columns['link_id'] = link.kind, self._node_id(tx, link, layer)
            elif key == 'role' and value is not None and value not in SUBTYPE_ROLES:
                raise StoreError(f'{value!r} is not a subtype role: use DE, SE or NE.', 'metaform help map knowledge')
            else:
                columns[key] = value
        return columns

    def remove(self, thing: str | int) -> None:
        """Delete a row a knowledge layer or a building correction layer wrote, with its refs, STORE-024."""
        with self._write() as tx:
            if isinstance(thing, int):
                self._remove_ref(tx, thing)
                return
            kind = self._kind_of(tx, thing)
            row, found = self._own_row(tx, kind, thing)
            self._editable(tx, found, thing)
            self._unused(tx, kind, thing, found)
            spec = corrections.KINDS[kind]
            tx.db.execute('DELETE FROM refs WHERE owner=? AND owner_row=?', (kind, row['row']))
            tx.db.execute(f'DELETE FROM {spec.current} WHERE row=?', (row['row'],))
            if kind == 'item':
                tx.db.execute('DELETE FROM challenge_states WHERE item_id=?', (thing,))
            tx.db.execute(f'DELETE FROM {spec.table} WHERE row=?', (row['row'],))

    def _remove_ref(self, tx: Tx, ref_id: int) -> None:
        ref = tx.db.execute('SELECT owner, owner_row FROM refs WHERE ref_id=?', (ref_id,)).fetchone()
        if ref is None:
            raise StoreError(f'No ref {ref_id}.', 'metaform map where <address>')
        table = corrections.KINDS[ref['owner']].table
        layer_id = tx.db.execute(f'SELECT layer_id FROM {table} WHERE row=?', (ref['owner_row'],)).fetchone()[0]
        self._editable(tx, self._layer(tx, layer_id), str(ref_id))
        tx.db.execute('DELETE FROM refs WHERE ref_id=?', (ref_id,))

    def _unused(self, tx: Tx, kind: str, thing: str, layer: LayerRow) -> None:
        """A row still used by another current row of the same layer is not removed."""
        db = tx.db
        users: list[sqlite3.Row] = []
        if kind == 'element':
            users += db.execute('SELECT c.join_id FROM current_joins c JOIN joins j ON j.row = c.row '
                                'WHERE c.receiver=? AND j.layer_id=?', (thing, layer.layer_id)).fetchall()
            users += db.execute('SELECT c.join_id FROM current_joins c JOIN joins j ON j.row = c.row '
                                'WHERE c.provider=? AND j.layer_id=?', (thing, layer.layer_id)).fetchall()
            users += db.execute('SELECT property_id FROM current_properties WHERE element_id=? AND layer_id=?',
                                (thing, layer.layer_id)).fetchall()
        if kind == 'join':
            users += db.execute('SELECT c.subtype_id FROM current_subtypes c JOIN subtypes s ON s.row = c.row '
                                'WHERE c.join_id=? AND s.layer_id=?', (thing, layer.layer_id)).fetchall()
        if kind in ('element', 'join', 'subtype'):
            users += db.execute('SELECT item_id FROM current_items WHERE target_kind=? AND target_id=? AND layer_id=?',
                                (kind, thing, layer.layer_id)).fetchall()
        if users:
            raise StoreError(f'{thing} is still used by {users[0][0]} in {layer.name}; remove that first.',
                             f'metaform map knowledge op=remove layer={layer.name} id={users[0][0]}')

    # -------------------------------------------------------------- corrections

    def correct(self, layer: str, thing: str, changes: dict[str, Any] | None = None, *, remove: bool = False,
                reason: str, evidence: str | None = None) -> Version:
        """Write a change or removal of a thing of the metaform into a building correction layer, STORE-017."""
        with self._write() as tx:
            found = self._layer(tx, layer)
            if found.kind != 'correction' or found.finished:
                raise StoreError(f'{found.name} is not a correction layer that is still building.',
                                 'metaform map knowledge op=create layer=<name> kind=correction mutable=false '
                                 'hideable=false')
            changes = dict(changes or {})
            if 'receiver' in changes:
                raise StoreError('A join keeps its receiver for life; remove it and add a new join instead.',
                                 f'metaform map knowledge op=correct layer={found.name} id={thing} remove=true '
                                 'reason=<why>')
            kind = self._kind_of(tx, thing)
            if not remove:
                self._allowed(kind, changes)
            spec = corrections.KINDS[kind]
            current = tx.db.execute(f'SELECT row FROM {spec.current} WHERE {spec.id_column}=?', (thing,)).fetchone()
            if current is None:
                raise StoreError(f'{thing} is not current in the metaform.', 'metaform map stack')
            base = tx.db.execute(f'SELECT * FROM {spec.table} WHERE row=?', (current[0],)).fetchone()
            if self._layer(tx, base['layer_id']).kind not in METAFORM_KINDS:
                raise StoreError(f'{thing} belongs to a knowledge layer; a correction never changes a knowledge '
                                 'layer, which is edited in place.',
                                 f'metaform map knowledge op=edit layer={self._layer_name(tx, base["layer_id"])} '
                                 f'id={thing} <field>=<value>')
            columns = {key: base[key] for key in base.keys() if key not in ('row', 'layer_id', 'op', 'reason',
                                                                                'evidence')}
            if not remove:
                columns.update(self._changed_columns(tx, kind, base, changes, found))
            if kind == 'join':
                columns['stack_at'] = self._top(tx)
            columns.update({'layer_id': found.layer_id, 'op': 'remove' if remove else 'change', 'reason': reason,
                            'evidence': evidence})
            previous = tx.db.execute(f'SELECT row FROM {spec.table} WHERE {spec.id_column}=? AND layer_id=?',
                                     (thing, found.layer_id)).fetchone()
            if previous is not None:
                tx.db.execute('DELETE FROM refs WHERE owner=? AND owner_row=?', (kind, previous[0]))
                tx.db.execute(f'DELETE FROM {spec.table} WHERE row=?', (previous[0],))
            names = ', '.join(columns)
            marks = ', '.join('?' for _ in columns)
            cursor = tx.db.execute(f'INSERT INTO {spec.table}({names}) VALUES ({marks})', tuple(columns.values()))
            row = int(cursor.lastrowid or 0)
            if 'refs' in changes and not remove:
                self._write_refs(tx, kind, row, refs_list(changes['refs']))
            else:
                self._write_refs(tx, kind, row, [(ref.key, ref.value) for ref in self._refs(tx.db, kind, current[0])])
            return self._version(tx, kind, tx.db.execute(f'SELECT * FROM {spec.table} WHERE row=?', (row,)).fetchone(),
                                 {})

    def peel(self, layer: str) -> Layer:
        """Take the top correction layer off the stack and return it to building, STORE-017."""
        with self._write() as tx:
            found = self._layer(tx, layer)
            if found.kind != 'correction':
                raise StoreError(f'{found.name} is not a correction layer.', 'metaform map stack')
            top = tx.db.execute('SELECT layer_id FROM correction_stack ORDER BY position DESC LIMIT 1').fetchone()
            if top is None or top[0] != found.layer_id:
                name = self._layer_name(tx, top[0]) if top else 'none'
                raise StoreError(f'{found.name} is not on top of the stack; the top correction layer is {name}.',
                                 f'metaform map knowledge op=peel layer={name}')
            corrections.peel(tx.db, found.layer_id)
            tx.db.execute('UPDATE layers SET ready=NULL WHERE layer_id=?', (found.layer_id,))
            return self._layer_record(tx, self._layer(tx, found.layer_id))

    # --------------------------------------------------------- challenges, plans

    def answer(self, item_id: str, state: str, link: Node | None = None) -> ChallengeState:
        """Record a challenge's answer beside the critic's layer, STORE-040."""
        with self._write() as tx:
            if state not in ('A', 'B', 'C'):
                raise StoreError(f'{state!r} is not an answer: use A, B or C.', f'metaform map answer {item_id} A')
            if self._kind_of(tx, item_id) != 'item':
                raise StoreError(f'{item_id} is not a challenge.', 'metaform map layers')
            _, found = self._own_row(tx, 'item', item_id)
            if found.kind != 'layer':
                raise StoreError(f'{item_id} is in {found.name}, which is not a blind-spot layer.',
                                 'metaform map layers')
            existing = tx.db.execute('SELECT state FROM challenge_states WHERE item_id=?', (item_id,)).fetchone()
            if existing is not None and existing[0] == 'plan':
                raise StoreError(f'Challenge {item_id} is already approved as a plan.', f'metaform map node <node>')
            link_kind = link_id = None
            if state == 'C':
                if link is None or link.kind not in ('element', 'join'):
                    raise StoreError('A C answer names the element or join that already handles the challenge.',
                                     f'metaform map answer {item_id} C link=element:<address>')
                link_kind, link_id = link.kind, self._node_id(tx, link)
            stamp = home.now()
            tx.db.execute('INSERT INTO challenge_states(item_id, state, link_kind, link_id, answered) '
                          'VALUES (?, ?, ?, ?, ?) ON CONFLICT(item_id) DO UPDATE SET state=excluded.state, '
                          'link_kind=excluded.link_kind, link_id=excluded.link_id, answered=excluded.answered',
                          (item_id, state, link_kind, link_id, stamp))
            return ChallengeState(item_id, state, Node(link_kind, link_id) if link_kind and link_id else None,
                                  stamp, None)

    def approve(self, item_id: str) -> ChallengeState:
        """A person approves a B answer; it becomes a plan with the element and join it carries, STORE-040."""
        with self._write() as tx:
            existing = tx.db.execute('SELECT state, answered FROM challenge_states WHERE item_id=?',
                                     (item_id,)).fetchone()
            if existing is None or existing[0] != 'B':
                state = 'open' if existing is None else existing[0]
                raise StoreError(f'Challenge {item_id} is {state}; only a challenge answered B is approved.',
                                 f'metaform map answer {item_id} B')
            item, found = self._own_row(tx, 'item', item_id)
            stamp = home.now()
            tx.db.execute("UPDATE challenge_states SET state='plan', approved=? WHERE item_id=?", (stamp, item_id))
            if item['target_kind'] == 'element':
                element_id = item['target_id']
                added = tx.db.execute('SELECT 1 FROM elements WHERE element_id=? AND layer_id=? AND op=?',
                                      (element_id, found.layer_id, 'add')).fetchone()
                if added is not None:
                    tx.db.execute('INSERT OR IGNORE INTO plans(element_id, join_id, layer_id, source, item_id) '
                                  'VALUES (?, ?, ?, ?, ?)',
                                  (element_id, self._join_in_layer(tx, element_id, found.layer_id), found.layer_id,
                                   'approved', item_id))
            return ChallengeState(item_id, 'plan', None, existing[1], stamp)

    @staticmethod
    def _join_in_layer(tx: Tx, element_id: str, layer_id: str) -> str | None:
        for column in ('provider', 'receiver'):
            row = tx.db.execute(f'SELECT c.join_id FROM current_joins c JOIN joins j ON j.row = c.row '
                                f'WHERE c.{column}=? AND j.layer_id=? ORDER BY c.row LIMIT 1',
                                (element_id, layer_id)).fetchone()
            if row is not None:
                return str(row[0])
        return None

    def add_plan(self, layer: str, element: Any, join: str | None) -> Plan:
        """An agent adds a plan directly; it needs no approval, STORE-040."""
        with self._write() as tx:
            found = self._layer(tx, layer)
            element_id = self._element_id(tx, element, found, 'A plan')
            join_id = self._node_id(tx, Node('join', join), found) if join else None
            tx.db.execute('INSERT INTO plans(element_id, join_id, layer_id, source, item_id) VALUES (?, ?, ?, ?, NULL) '
                          'ON CONFLICT(element_id) DO UPDATE SET join_id=excluded.join_id, layer_id=excluded.layer_id, '
                          "source='direct', item_id=NULL", (element_id, join_id, found.layer_id, 'direct'))
            return Plan(element_id, join_id, found.layer_id, found.name, 'direct', None)

    # ================================================================== reads

    def _resolver(self, tx: Tx, selection: Sequence[str] | None) -> Resolver:
        return Resolver(tx.db, selection, self.toggled)

    def _element_record(self, tx: Tx, element_id: str, res: Resolver | None,
                        layers: dict[str, LayerRow] | None = None) -> Element | None:
        """An element with its descriptors; in context, only when its layer reaches its address."""
        current = tx.db.execute('SELECT c.address, e.* FROM current_elements c JOIN elements e ON e.row = c.row '
                                'WHERE c.element_id=?', (element_id,)).fetchone()
        if current is None:
            return None
        layers = layers or (res.layers if res else all_layers(tx.db))
        address = current['address']
        if res is not None and not self._element_shows(res, current['layer_id'], address):
            return None
        descriptors = []
        for row in tx.db.execute('SELECT c.item_id, i.* FROM current_items c JOIN items i ON i.row = c.row '
                                 "WHERE c.target_kind='element' AND c.target_id=?", (element_id,)):
            value = json.loads(row['value'])
            if not (isinstance(value, dict) and isinstance(value.get('descriptor'), dict)):
                continue
            if res is not None and not res.reaches(row['layer_id'], address):
                continue
            given = value['descriptor']
            descriptors.append(Descriptor(row['item_id'], row['layer_id'], layers[row['layer_id']].name,
                                          given.get('name'), given.get('name_length'), given.get('role'),
                                          self._refs(tx.db, 'item', row['row'])))
        descriptors.sort(key=lambda item: layers[item.layer_id].kind != 'intake')
        first = descriptors[0] if descriptors else None
        plan = tx.db.execute('SELECT 1 FROM plans WHERE element_id=?', (element_id,)).fetchone()
        return Element(element_id, address, current['layer_id'], layers[current['layer_id']].name,
                       first.name if first else None, first.name_length if first else None,
                       first.role if first else None, tuple(descriptors), self._refs(tx.db, 'element', current['row']),
                       decode_extra(current['extra']), state='plan' if plan else None)

    @staticmethod
    def _element_shows(res: Resolver, layer_id: str, address: str) -> bool:
        """An element of the metaform is always a node; one a knowledge layer created shows where its layer does."""
        layer = res.layers.get(layer_id)
        if layer is not None and layer.kind in METAFORM_KINDS:
            return layer.finished
        return res.reaches(layer_id, address)

    def _address_of(self, tx: Tx, element_id: str) -> str | None:
        row = tx.db.execute('SELECT address FROM current_elements WHERE element_id=?', (element_id,)).fetchone()
        return None if row is None else str(row[0])

    def _join_orphaned(self, tx: Tx, row: sqlite3.Row, layers: dict[str, LayerRow]) -> bool:
        """A join with an end that is not current, or a knowledge join whose end moved after it, STORE-017."""
        ends = [tx.db.execute('SELECT moved FROM current_elements WHERE element_id=?', (end,)).fetchone()
                for end in (row['receiver'], row['provider'])]
        if any(end is None for end in ends):
            return True
        if layers[row['layer_id']].kind in METAFORM_KINDS:
            return False
        return any(int(end[0]) > int(row['stack_at']) for end in ends if end is not None)

    def _join_record(self, tx: Tx, row: sqlite3.Row, layers: dict[str, LayerRow], orphaned: bool = False) -> Join:
        plan = None
        for end in (row['provider'], row['receiver']):
            found = tx.db.execute('SELECT join_id FROM plans WHERE element_id=?', (end,)).fetchone()
            if found is not None and found[0] == row['join_id']:
                plan = 'plan'
        return Join(row['join_id'], row['layer_id'], layers[row['layer_id']].name, row['type'], row['receiver'],
                    self._address_of(tx, row['receiver']), row['provider'], self._address_of(tx, row['provider']),
                    row['purpose'], row['function'], row['relation'], row['observation'], row['non_goal'],
                    self._refs(tx.db, 'join', row['row']), decode_extra(row['extra']), plan, orphaned)

    def _visible_join(self, tx: Tx, row: sqlite3.Row, res: Resolver | None) -> Join | None:
        orphaned = self._join_orphaned(tx, row, res.layers if res else all_layers(tx.db))
        if res is None:
            return self._join_record(tx, row, all_layers(tx.db), orphaned)
        if orphaned or not res.reaches(row['layer_id'], self._address_of(tx, row['receiver'])):
            return None
        return self._join_record(tx, row, res.layers)

    def _subtype_record(self, tx: Tx, row: sqlite3.Row, join_id: str, layers: dict[str, LayerRow]) -> Subtype:
        join_row = tx.db.execute('SELECT j.layer_id FROM current_joins c JOIN joins j ON j.row = c.row '
                                 'WHERE c.join_id=?', (join_id,)).fetchone()
        layer_id = join_row[0] if join_row is not None else row['layer_id']
        return Subtype(row['subtype_id'], join_id, layer_id, layers[layer_id].name, row['address'], row['name'],
                       row['name_length'], row['role'], row['function'], row['relation'], row['observation'],
                       self._refs(tx.db, 'subtype', row['row']), decode_extra(row['extra']))

    def _target_current(self, tx: Tx, kind: str, thing: str) -> bool:
        spec = corrections.KINDS[kind]
        return tx.db.execute(f'SELECT 1 FROM {spec.current} WHERE {spec.id_column}=?', (thing,)).fetchone() is not None

    def _item_record(self, tx: Tx, row: sqlite3.Row, layers: dict[str, LayerRow]) -> Item:
        state_row = tx.db.execute('SELECT state FROM challenge_states WHERE item_id=?', (row['item_id'],)).fetchone()
        orphaned = not self._target_current(tx, row['target_kind'], row['target_id'])
        return Item(row['item_id'], row['layer_id'], layers[row['layer_id']].name,
                    Node(row['target_kind'], row['target_id']), json.loads(row['value']),
                    Node(row['link_kind'], row['link_id']) if row['link_kind'] else None,
                    self._refs(tx.db, 'item', row['row']), decode_extra(row['extra']),
                    state_row[0] if state_row else None, orphaned)

    def _item_by_id(self, tx: Tx, item_id: str) -> Item:
        row = tx.db.execute('SELECT i.* FROM current_items c JOIN items i ON i.row = c.row WHERE c.item_id=?',
                            (item_id,)).fetchone()
        if row is None:
            row = tx.db.execute('SELECT * FROM items WHERE item_id=? ORDER BY row DESC LIMIT 1', (item_id,)).fetchone()
        return self._item_record(tx, row, all_layers(tx.db))

    def _property_record(self, tx: Tx, row: sqlite3.Row, layers: dict[str, LayerRow]) -> Property:
        address = self._address_of(tx, row['element_id'])
        return Property(row['property_id'], row['layer_id'], layers[row['layer_id']].name, row['element_id'],
                        address, json.loads(row['value']), self._refs(tx.db, 'property', row['row']),
                        decode_extra(row['extra']), address is None)

    def _layer_record(self, tx: Tx, found: LayerRow, *, toggled: frozenset[str] | None = None,
                      hidden: set[str] | None = None, provenance: bool = False) -> Layer:
        db = tx.db
        layer_id = found.layer_id
        position = db.execute('SELECT position FROM correction_stack WHERE layer_id=?', (layer_id,)).fetchone()
        record = Layer(
            layer_id, found.metaform_id, found.name, found.module, found.variable, found.kind, found.mutable,
            found.hideable, found.result_id, found.created, found.ready,
            tuple(row[0] for row in db.execute('SELECT name FROM layer_fields WHERE layer_id=? ORDER BY position',
                                               (layer_id,))),
            tuple(row[0] for row in db.execute('SELECT tag FROM layer_tags WHERE layer_id=? ORDER BY tag', (layer_id,))),
            tuple(self._layer_name(tx, row[0]) for row in db.execute(
                'SELECT source_layer_id FROM layer_sources WHERE layer_id=?', (layer_id,))),
            layer_id in (hidden if hidden is not None else hidden_closure(db)),
            (layer_id in toggled) if toggled is not None else False,
            db.execute('SELECT 1 FROM reexamine WHERE layer_id=? LIMIT 1', (layer_id,)).fetchone() is not None,
            position[0] if position else None,
            self._provenance(tx, layer_id) if provenance else None)
        return record

    @staticmethod
    def _provenance(tx: Tx, layer_id: str) -> Provenance | None:
        row = tx.db.execute('SELECT * FROM provenance WHERE layer_id=?', (layer_id,)).fetchone()
        if row is None:
            return None
        return Provenance(row['layer_id'], row['module'], row['workflow'], row['prompt'], row['model'], row['role'],
                          None if row['blinded'] is None else bool(row['blinded']))

    def _version(self, tx: Tx, kind: str, row: sqlite3.Row, positions: dict[str, int]) -> Version:
        spec = corrections.KINDS[kind]
        fields = {key: row[key] for key in row.keys()
                  if key not in ('row', spec.id_column, 'layer_id', 'op', 'reason', 'evidence')}
        for key in ('extra',):
            if key in fields:
                fields[key] = decode_extra(fields[key])
        if 'value' in fields and fields['value'] is not None:
            fields['value'] = json.loads(fields['value'])
        return Version(row[spec.id_column], kind, row['layer_id'], self._layer_name(tx, row['layer_id']),
                       positions.get(row['layer_id']), row['op'], row['reason'], row['evidence'], fields,
                       self._refs(tx.db, kind, row['row']))

    # ----------------------------------------------------------- read operations

    def element(self, ref: str, *, selection: Sequence[str] | None = None, raw: bool = False) -> Element | None:
        """One element by address or id, with its descriptors and refs."""
        with self._read() as tx:
            current = self._current_element(tx, ref) if isinstance(ref, str) else None
            if current is None:
                return None
            return self._element_record(tx, current['element_id'], None if raw else self._resolver(tx, selection))

    def joins(self, element: str, as_: str = 'receiver', *, selection: Sequence[str] | None = None,
              raw: bool = False, limit: int = LIMIT, after: str | None = None) -> Page[Join]:
        """The joins an element owns, or those it provides for, each with its layer."""
        if as_ not in ('receiver', 'provider'):
            raise StoreError(f'{as_!r} is not receiver or provider.', f'metaform map joins {element} as=receiver')
        with self._read() as tx:
            element_id = self._any_element_id(tx, element)
            if element_id is None:
                return Page((), None)
            res = None if raw else self._resolver(tx, selection)

            def fetch(cursor: str | None, count: int) -> list[sqlite3.Row]:
                return tx.db.execute(f'SELECT c.join_id AS key, j.* FROM current_joins c JOIN joins j ON j.row = c.row '
                                     f'WHERE c.{as_}=? AND c.join_id > ? ORDER BY c.join_id LIMIT ?',
                                     (element_id, cursor or '', count)).fetchall()
            return _paged(fetch, lambda row: self._visible_join(tx, row, res), limit, after)

    def _any_element_id(self, tx: Tx, ref: str) -> str | None:
        current = self._current_element(tx, ref)
        if current is not None:
            return str(current['element_id'])
        if is_id(ref) and tx.db.execute('SELECT 1 FROM element_ids WHERE element_id=?', (ref,)).fetchone():
            return ref
        return None

    def identity(self, element: str, *, selection: Sequence[str] | None = None, raw: bool = False,
                 limit: int = LIMIT, after: str | None = None) -> Page[Join]:
        """Every current join the element provides for: who receives it, why, and how, STORE-010."""
        return self.joins(element, 'provider', selection=selection, raw=raw, limit=limit, after=after)

    def subtypes(self, join: str, *, selection: Sequence[str] | None = None, raw: bool = False,
                 limit: int = LIMIT, after: str | None = None) -> Page[Subtype]:
        with self._read() as tx:
            join_row = tx.db.execute('SELECT j.* FROM current_joins c JOIN joins j ON j.row = c.row WHERE c.join_id=?',
                                     (join,)).fetchone()
            if join_row is None:
                return Page((), None)
            res = None if raw else self._resolver(tx, selection)
            if res is not None and self._visible_join(tx, join_row, res) is None:
                return Page((), None)
            layers = res.layers if res else all_layers(tx.db)

            def fetch(cursor: str | None, count: int) -> list[sqlite3.Row]:
                return tx.db.execute('SELECT c.subtype_id AS key, s.* FROM current_subtypes c '
                                     'JOIN subtypes s ON s.row = c.row WHERE c.join_id=? AND c.subtype_id > ? '
                                     'ORDER BY c.subtype_id LIMIT ?', (join, cursor or '', count)).fetchall()
            return _paged(fetch, lambda row: self._subtype_record(tx, row, join, layers), limit, after)

    def where(self, address: str, *, selection: Sequence[str] | None = None, raw: bool = False) -> Where | None:
        """The element at an address, or the subtype there with the join that holds it."""
        with self._read() as tx:
            res = None if raw else self._resolver(tx, selection)
            current = tx.db.execute('SELECT element_id FROM current_elements WHERE address=?', (address,)).fetchone()
            if current is not None:
                element = self._element_record(tx, current[0], res)
                return None if element is None else Where('element', element=element)
            row = tx.db.execute('SELECT c.join_id, s.* FROM current_subtypes c JOIN subtypes s ON s.row = c.row '
                                'WHERE c.address=?', (address,)).fetchone()
            if row is None:
                return None
            join_row = tx.db.execute('SELECT j.* FROM current_joins c JOIN joins j ON j.row = c.row WHERE c.join_id=?',
                                     (row['join_id'],)).fetchone()
            if join_row is None:
                return None
            join = self._visible_join(tx, join_row, res)
            if join is None:
                return None
            layers = res.layers if res else all_layers(tx.db)
            return Where('subtype', subtype=self._subtype_record(tx, row, row['join_id'], layers), join=join)

    def children(self, address: str, *, limit: int = LIMIT, after: str | None = None) -> Page[str]:
        """The next types up the tree, toward the leaves."""
        with self._read() as tx:
            def fetch(cursor: str | None, count: int) -> list[sqlite3.Row]:
                return tx.db.execute('SELECT address AS key FROM types WHERE parent=? AND address > ? '
                                     'ORDER BY address LIMIT ?', (address, cursor or '', count)).fetchall()
            return _paged(fetch, lambda row: str(row['key']), limit, after)

    def layer_items(self, layer: str, target: Node | None = None, *, limit: int = LIMIT,
                    after: str | None = None) -> Page[Item | Property]:
        """A whole layer in row order, or a layer at one node: its items, then its properties."""
        with self._read() as tx:
            found = self._layer(tx, layer)
            layers = all_layers(tx.db)
            if target is not None:
                target_id = self._node_id(tx, target)
                items: list[Item | Property] = [self._item_record(tx, row, layers) for row in tx.db.execute(
                    'SELECT i.* FROM current_items c JOIN items i ON i.row = c.row '
                    'WHERE c.target_kind=? AND c.target_id=? AND c.layer_id=? ORDER BY c.row',
                    (target.kind, target_id, found.layer_id))]
                if target.kind == 'element':
                    items += [self._property_record(tx, row, layers) for row in tx.db.execute(
                        'SELECT p.* FROM current_properties c JOIN properties p ON p.row = c.row '
                        'WHERE c.element_id=? AND c.layer_id=? ORDER BY c.row', (target_id, found.layer_id))]
                return Page(tuple(items), None)

            def fetch(cursor: str | None, count: int) -> list[sqlite3.Row]:
                phase, _, position = (cursor or 'i:0').partition(':')
                rows: list[sqlite3.Row] = []
                if phase == 'i':
                    rows = tx.db.execute("SELECT 'i:' || c.row AS key, 'item' AS thing, i.* FROM current_items c "
                                         'JOIN items i ON i.row = c.row WHERE c.layer_id=? AND c.row > ? '
                                         'ORDER BY c.row LIMIT ?', (found.layer_id, int(position or 0),
                                                                    count)).fetchall()
                    if len(rows) >= count:
                        return rows
                    position = ''
                rows += tx.db.execute("SELECT 'p:' || c.element_id || ':' || c.property_id AS key, 'property' AS thing, "
                                      'p.* FROM current_properties c JOIN properties p ON p.row = c.row '
                                      'WHERE c.layer_id=? AND c.element_id || c.property_id > ? '
                                      'ORDER BY c.element_id, c.property_id LIMIT ?',
                                      (found.layer_id, position.replace(':', ''), count - len(rows))).fetchall()
                return rows

            def build(row: sqlite3.Row) -> Item | Property:
                if row['thing'] == 'item':
                    return self._item_record(tx, row, layers)
                return self._property_record(tx, row, layers)
            return _paged(fetch, build, limit, after)

    def node(self, target: Node, *, selection: Sequence[str] | None = None, raw: bool = False) -> NodeView | None:
        """Every layer's items at one node, grouped by layer; in context, only the layers that reach it."""
        with self._read() as tx:
            res = self._resolver(tx, selection)
            located = self._locate(tx, target, raw)
            if located is None:
                return None
            thing_id, address, visible = located
            if not raw and not visible(res):
                return None
            groups: dict[str, tuple[list[Item], list[Property]]] = {}
            for row in tx.db.execute('SELECT i.* FROM current_items c JOIN items i ON i.row = c.row '
                                     'WHERE c.target_kind=? AND c.target_id=? ORDER BY c.row',
                                     (target.kind, thing_id)):
                if raw or res.reaches(row['layer_id'], address):
                    groups.setdefault(row['layer_id'], ([], []))[0].append(self._item_record(tx, row, res.layers))
            if target.kind == 'element':
                for row in tx.db.execute('SELECT p.* FROM current_properties c JOIN properties p ON p.row = c.row '
                                         'WHERE c.element_id=? ORDER BY c.row', (thing_id,)):
                    if raw or res.reaches(row['layer_id'], address):
                        groups.setdefault(row['layer_id'], ([], []))[1].append(
                            self._property_record(tx, row, res.layers))
            ordered = [layer_id for layer_id in res.layers if layer_id in groups]
            view = tuple(LayerGroup(layer_id, res.layers[layer_id].name, res.layers[layer_id].kind,
                                    tuple(groups[layer_id][0]), tuple(groups[layer_id][1])) for layer_id in ordered)
            return NodeView(Node(target.kind, thing_id), address, view, orphaned=address is None)

    def _locate(self, tx: Tx, target: Node, raw: bool) -> tuple[str, str | None,
                                                                   Callable[[Resolver], bool]] | None:
        """A node's identity id, the address its selection is read at, and whether it shows in context."""
        if not isinstance(target, Node):
            raise StoreError(f'{target!r} is not a node.', 'metaform help map node')
        if target.kind == 'element':
            current = self._current_element(tx, target.id)
            if current is None:
                if raw and is_id(target.id) and tx.db.execute('SELECT 1 FROM element_ids WHERE element_id=?',
                                                              (target.id,)).fetchone():
                    return target.id, None, lambda res: False
                return None
            element_id, address = str(current['element_id']), str(current['address'])
            row = tx.db.execute('SELECT layer_id FROM elements WHERE row=?', (current['row'],)).fetchone()
            return element_id, address, lambda res: self._element_shows(res, row[0], address)
        if target.kind == 'join':
            row = tx.db.execute('SELECT j.* FROM current_joins c JOIN joins j ON j.row = c.row WHERE c.join_id=?',
                                (target.id,)).fetchone()
            if row is None:
                return None
            address = self._address_of(tx, row['receiver'])
            return target.id, address, lambda res: self._visible_join(tx, row, res) is not None
        column = 'subtype_id' if is_id(target.id) else 'address'
        row = tx.db.execute(f'SELECT subtype_id, join_id, address FROM current_subtypes WHERE {column}=?',
                            (target.id,)).fetchone()
        if row is None:
            return None
        join_row = tx.db.execute('SELECT j.* FROM current_joins c JOIN joins j ON j.row = c.row WHERE c.join_id=?',
                                 (row['join_id'],)).fetchone()
        return (str(row['subtype_id']), str(row['address']),
                lambda res: join_row is not None and self._visible_join(tx, join_row, res) is not None)

    def context(self, address: str, *, selection: Sequence[str] | None = None, limit: int = LIMIT,
                after: str | None = None) -> ContextView:
        """The properties that apply at an address, and those visible there from above, STORE-035."""
        check_address(address)
        with self._read() as tx:
            res = self._resolver(tx, selection)
            applying: list[Property] = []
            for prefix in prefixes(address):
                element = tx.db.execute('SELECT element_id FROM current_elements WHERE address=?', (prefix,)).fetchone()
                if element is None:
                    continue
                for row in tx.db.execute('SELECT p.* FROM current_properties c JOIN properties p ON p.row = c.row '
                                         'WHERE c.element_id=? ORDER BY c.row', (element[0],)):
                    if res.reaches(row['layer_id'], address):
                        applying.append(self._property_record(tx, row, res.layers))
            visible: list[Property] = []
            cursor = after if after is not None else address + '.'
            upper = address + '/'
            next_cursor: str | None = None
            while True:
                rows = tx.db.execute('SELECT element_id, address FROM current_elements WHERE address > ? AND address < ? '
                                     'ORDER BY address LIMIT ?', (cursor, upper, LIMIT)).fetchall()
                if not rows:
                    break
                for element_id, element_address in rows:
                    cursor = element_address
                    for row in tx.db.execute('SELECT p.* FROM current_properties c JOIN properties p ON p.row = c.row '
                                             'WHERE c.element_id=? ORDER BY c.row', (element_id,)):
                        if res.reaches(row['layer_id'], element_address):
                            visible.append(self._property_record(tx, row, res.layers))
                    if limit and len(visible) >= limit:
                        more = tx.db.execute('SELECT 1 FROM current_elements WHERE address > ? AND address < ? LIMIT 1',
                                             (element_address, upper)).fetchone()
                        next_cursor = element_address if more else None
                        break
                if next_cursor is not None or (limit and len(visible) >= limit):
                    break
            return ContextView(address, tuple(applying), tuple(visible), next_cursor)

    def links_to(self, target: Node, layer: str | None = None, *, selection: Sequence[str] | None = None,
                 raw: bool = False, limit: int = LIMIT, after: str | None = None) -> Page[Item]:
        """Items in any layer, or one layer, that link to a node."""
        with self._read() as tx:
            located = self._locate(tx, target, raw)
            if located is None:
                return Page((), None)
            thing_id = located[0]
            res = self._resolver(tx, selection)
            layer_id = self._layer(tx, layer).layer_id if layer else None

            def fetch(cursor: str | None, count: int) -> list[sqlite3.Row]:
                sql = ('SELECT c.item_id AS key, i.* FROM current_items c JOIN items i ON i.row = c.row '
                       'WHERE c.link_kind=? AND c.link_id=?')
                params: list[Any] = [target.kind, thing_id]
                if layer_id is not None:
                    sql += ' AND c.layer_id=?'
                    params.append(layer_id)
                sql += ' AND c.item_id > ? ORDER BY c.item_id LIMIT ?'
                return tx.db.execute(sql, (*params, cursor or '', count)).fetchall()

            def build(row: sqlite3.Row) -> Item | None:
                if raw or layer_id is not None:
                    return self._item_record(tx, row, res.layers)
                origin = self._node_address(tx, row['target_kind'], row['target_id'])
                if origin is None or not res.reaches(row['layer_id'], origin):
                    return None
                return self._item_record(tx, row, res.layers)
            return _paged(fetch, build, limit, after)

    def _node_address(self, tx: Tx, kind: str, thing_id: str) -> str | None:
        if kind == 'element':
            return self._address_of(tx, thing_id)
        if kind == 'join':
            row = tx.db.execute('SELECT receiver FROM current_joins WHERE join_id=?', (thing_id,)).fetchone()
            return None if row is None else self._address_of(tx, row[0])
        row = tx.db.execute('SELECT address FROM current_subtypes WHERE subtype_id=?', (thing_id,)).fetchone()
        return None if row is None else str(row[0])

    def citing(self, key: str, value: str, *, limit: int = LIMIT, after: str | None = None) -> Page[Citation]:
        """Every current element, join, subtype, property and item whose refs hold this key and value, MAP-021."""
        with self._read() as tx:
            layers = all_layers(tx.db)

            def fetch(cursor: str | None, count: int) -> list[sqlite3.Row]:
                return tx.db.execute('SELECT ref_id AS key, owner, owner_row FROM refs WHERE key=? AND value=? '
                                     'AND ref_id > ? ORDER BY ref_id LIMIT ?',
                                     (key, value, int(cursor or 0), count)).fetchall()

            seen: set[tuple[str, str]] = set()

            def build(row: sqlite3.Row) -> Citation | None:
                spec = corrections.KINDS[row['owner']]
                current = tx.db.execute(f'SELECT {spec.id_column} FROM {spec.current} WHERE row=?',
                                        (row['owner_row'],)).fetchone()
                if current is None or (row['owner'], current[0]) in seen:
                    return None
                seen.add((row['owner'], current[0]))
                version = tx.db.execute(f'SELECT layer_id FROM {spec.table} WHERE row=?', (row['owner_row'],)).fetchone()
                address = None
                if row['owner'] in ('element', 'subtype'):
                    address = self._node_address(tx, row['owner'], current[0])
                return Citation(row['owner'], str(current[0]), address, layers[version[0]].name)
            return _paged(fetch, build, limit, after, key=lambda row: str(row['key']))

    def history(self, thing: str, *, limit: int = LIMIT, after: str | None = None) -> Page[Version]:
        """Every version of a thing: the row that added it, then each stacked correction's row, in order."""
        with self._read() as tx:
            kind = self._kind_of(tx, thing)
            spec = corrections.KINDS[kind]
            positions = corrections.stack_positions(tx.db)
            kinds = corrections.layer_kinds(tx.db)
            ordered = sorted((row for row in tx.db.execute(f'SELECT * FROM {spec.table} WHERE {spec.id_column}=?',
                                                           (thing,))
                              if kinds[row['layer_id']] != 'correction' or row['layer_id'] in positions),
                             key=lambda row: positions.get(row['layer_id'], 0))
            versions = tuple(self._version(tx, kind, row, positions) for row in ordered)
            return _slice(versions, limit, after)

    def stack(self, *, limit: int = LIMIT, after: str | None = None) -> Page[Layer]:
        """The correction layers in the order they were applied, each with its provenance."""
        with self._read() as tx:
            layers = tuple(self._layer_record(tx, self._layer(tx, row[0]), provenance=True)
                           for row in tx.db.execute('SELECT layer_id FROM correction_stack ORDER BY position'))
            return _slice(layers, limit, after)

    def layers(self, tag: str | None = None, kind: str | None = None, module: str | None = None, *,
               limit: int = LIMIT, after: str | None = None) -> Page[Layer]:
        """The layers with their declaration, tags, state, hidden and toggled flags, LAYER-019."""
        with self._read() as tx:
            res = self._resolver(tx, None)
            chosen = list(res.layers.values())
            if tag is not None:
                tagged = {row[0] for row in tx.db.execute('SELECT layer_id FROM layer_tags WHERE tag=?', (tag,))}
                chosen = [layer for layer in chosen if layer.layer_id in tagged]
            chosen = [layer for layer in chosen if (kind is None or layer.kind == kind)
                      and (module is None or layer.module == module)]
            records = tuple(self._layer_record(tx, layer, toggled=res.start, hidden=res.hidden) for layer in chosen)
            return _slice(records, limit, after)

    def provenance(self, layer: str) -> Provenance | None:
        with self._read() as tx:
            return self._provenance(tx, self._layer(tx, layer).layer_id)

    def effective_selection(self, address: str, root: Sequence[str] | None = None) -> Selection:
        """The layers that reach an address, and any select or mask rows that cannot apply, STORE-035."""
        check_address(address)
        with self._read() as tx:
            res = self._resolver(tx, root)
            ids = tuple(layer_id for layer_id in res.layers if layer_id in res.at(address))
            return Selection(address, ids, tuple(res.layers[layer_id].name for layer_id in ids),
                             tuple(res.unresolved(address)))

    def search(self, text: str, layer: str | None = None, *, selection: Sequence[str] | None = None,
               limit: int = LIMIT, after: str | None = None) -> Page[Item]:
        """Items whose value holds every word of the text, STORE-020."""
        words = [word for word in str(text).split() if word]
        if not words:
            return Page((), None)
        query = ' '.join('"' + word.replace('"', '""') + '"' for word in words)
        with self._read() as tx:
            res = self._resolver(tx, selection)
            layer_id = self._layer(tx, layer).layer_id if layer else None

            def fetch(cursor: str | None, count: int) -> list[sqlite3.Row]:
                start = int(cursor or 0)
                rows = tx.db.execute('SELECT c.item_id, i.* FROM item_text JOIN current_items c ON c.row = item_text.rowid '
                                     'JOIN items i ON i.row = c.row WHERE item_text MATCH ? ORDER BY rank LIMIT ? OFFSET ?',
                                     (query, count, start)).fetchall()
                return [_Keyed(row, str(start + index + 1)) for index, row in enumerate(rows)]  # type: ignore[misc]

            def build(row: Any) -> Item | None:
                if layer_id is not None:
                    return self._item_record(tx, row.row, res.layers) if row.row['layer_id'] == layer_id else None
                if row.row['layer_id'] not in res.start:
                    return None
                return self._item_record(tx, row.row, res.layers)
            return _paged(fetch, build, limit, after, key=lambda row: row.key)

    def has_intake(self) -> bool:
        with self._read() as tx:
            return tx.db.execute("SELECT 1 FROM layers WHERE kind='intake' AND ready IS NOT NULL LIMIT 1").fetchone() \
                is not None

    def metaforms(self, *, limit: int = LIMIT, after: str | None = None) -> Page[home.Metaform]:
        return _slice(home.metaforms(self.project_id), limit, after)

    def active_metaform(self) -> home.Metaform | None:
        return home.active_metaform(self.project_id)

    def add_metaform(self, name: str) -> home.Metaform:
        return home.add_metaform(self.project_id, name)

    def activate_metaform(self, name: str) -> home.Metaform:
        return home.activate_metaform(self.project_id, name)

    def project(self) -> home.Project:
        record = home.project(self.project_id)
        if record is None:
            raise StoreError(f'Project {self.project_id} is no longer registered.', 'metaform list projects')
        return record


class _Keyed:
    """A row with the cursor key it would be resumed after."""

    def __init__(self, row: sqlite3.Row, key: str) -> None:
        self.row = row
        self.key = key


def _replace(record: Element, **changes: Any) -> Element:
    import dataclasses
    return dataclasses.replace(record, **changes)


def _paged(fetch: Callable[[str | None, int], list[Any]], build: Callable[[Any], Any], limit: int,
           after: str | None, *, key: Callable[[Any], str] | None = None) -> Page[Any]:
    """Fill one page from index range reads, skipping rows the build step leaves out, STORE-025."""
    key = key or (lambda row: str(row['key']))
    results: list[Any] = []
    cursor = after
    batch = limit if limit else LIMIT
    while True:
        rows = fetch(cursor, batch)
        for row in rows:
            cursor = key(row)
            built = build(row)
            if built is None:
                continue
            results.append(built)
            if limit and len(results) >= limit:
                return Page(tuple(results), cursor if fetch(cursor, 1) else None)
        if len(rows) < batch:
            return Page(tuple(results), None)


def _slice(values: tuple[Any, ...], limit: int, after: str | None) -> Page[Any]:
    start = int(after or 0)
    if not limit:
        return Page(values[start:], None)
    end = start + limit
    return Page(values[start:end], str(end) if end < len(values) else None)
