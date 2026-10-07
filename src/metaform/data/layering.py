"""Layer operations: create, finish, discard, hide, tag, select and mask, and refining the base, STORE-024.

Every function works inside one open write transaction. Nothing an agent sends
is refused for its content, BASE-044: an empty variable, a missing provenance,
a taken name, a tag or source that does not fit, are stored as given or
numbered, with a notice. An operation aimed at something that cannot change,
such as hiding a layer that is not hideable,
writes nothing and returns a notice saying why. A reference to no layer cannot
be read and raises `StoreError`, STORE-026. Every change is an op on the base's
projection, appended to the log at commit, STORE-046.
"""
from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from typing import Any

from .. import home
from ..errors import StoreError
from . import operations, rows, versions, views, writes
from .ids import LAYER_NAME, TAG, is_id, new_id
from .records import Layer, Notice, Outcome, Version
from .selection import LayerRow, all_layers
from .session import Tx
from .versions import BASE_KINDS

KINDS = ('layer', 'base', 'memory')


def _free_name(tx: Tx, name: str) -> str:
    chosen, number = name, 1
    while tx.base.layer_by_name(chosen) is not None:
        number += 1
        chosen = f'{name}-{number}'
    return chosen


def _tags(tags: Sequence[Any], notices: list[Notice]) -> list[str]:
    kept: list[str] = []
    for tag in tags:
        if not isinstance(tag, str) or not 1 <= len(tag) <= 64:
            notices.append(Notice('tags', f'{tag!r} is not a tag of 1 to 64 characters; it was not stored.'))
            continue
        if not TAG.fullmatch(tag):
            notices.append(Notice('tags', f'{tag!r} is not lowercase letters, digits, ., _ and -; it was stored as '
                                          'given.'))
        if tag not in kept:
            kept.append(tag)
    return kept


def _sources(tx: Tx, sources: Sequence[Any], notices: list[Notice]) -> list[str]:
    found: list[str] = []
    by_name = {item.name: item.id for item in all_layers(tx.base).values()}
    for source in sources:
        name = str(source)
        if name in by_name.values():
            found.append(name)
        elif name in by_name:
            found.append(by_name[name])
        else:
            notices.append(Notice('sources', f'{name} is not a layer here; it was not recorded as a source.'))
    return [source for index, source in enumerate(found) if source not in found[:index]]


def complete(tx: Tx, name: str, provenance: dict[str, Any], result_id: str | None = None) -> Outcome:
    """Fill in what a layer still being built lacks of its provenance and its result id, LAYER-010.

    What the layer holds is kept: a different value given for it is named in a notice and not stored, so the record
    of what made the layer never changes once it says something.
    """
    found = tx.base.layer_by_name(name)
    if found is None:
        raise StoreError(f'No layer {name}.', 'metaform map layers')
    notices: list[Notice] = []
    if found.ready is not None:
        return Outcome((Notice('layer', f'Layer {name} is finished; its provenance was kept as it is.'),))
    held = dict(found.provenance or {})
    given = {'model': provenance.get('model'), 'role': provenance.get('role'), 'blinded': provenance.get('blinded'),
             'id': result_id}
    changed: dict[str, Any] = {}
    for key, value in given.items():
        if value is None:
            continue
        current = found.result_id if key == 'id' else held.get(key)
        value = int(bool(value)) if key == 'blinded' else value
        if current is None:
            if key == 'id':
                changed['result_id'] = value
            else:
                held[key] = value
                changed['provenance'] = held
        elif current != value:
            shown = (bool(current), bool(value)) if key == 'blinded' else (current, value)
            notices.append(Notice(key, f'The layer holds {key} {shown[0]}; {shown[1]} was given and was not stored.'))
    if changed:
        tx.emit('change', 'layer', found.id, found.id, changed)
    return Outcome(tuple(notices))


def create(tx: Tx, name: object, module: str, variable: Any, *, kind: str = 'layer', mutable: bool, hideable: bool,
           fields: Sequence[str] = (), tags: Sequence[Any] = (), provenance: dict[str, Any] | None = None,
           result_id: str | None = None, sources: Sequence[Any] = (), ready: bool = False) -> Layer:
    """Create a layer, or return the one with this name and the same declaration, STORE-024 and LAYER-002."""
    if not isinstance(name, str) or not name or is_id(name):
        raise StoreError(f'{name!r} cannot be a layer name: it would be read as an id.',
                         'metaform map knowledge op=create layer=<name> variable=<question>')
    if kind == 'intake':  # the layer the intake writes is the base, the change order of 2026-10-07
        kind = 'base'
    if kind not in KINDS:
        raise StoreError(f'{kind!r} is not a layer kind: use layer, base or memory.',
                         'metaform help map knowledge')
    notices: list[Notice] = []
    if not LAYER_NAME.fullmatch(name):
        notices.append(Notice('name', f'{name!r} is not 1 to 128 letters, digits, ., _ and -; it was stored as given.'))
    question = rows.text(variable, 'variable', notices) or ''
    if not question.strip():
        notices.append(Notice('variable', f'Layer {name} has no variable, the one question it answers; it was stored '
                                          'without one. Name it with metaform map knowledge op=create again under a '
                                          'new name, or tell the person who asked for the layer.'))
    existing = tx.base.layer_by_name(name)
    if existing is not None:
        if (existing.kind, existing.module, existing.variable, existing.mutable, existing.hideable) == (
                kind, module, question, bool(mutable), bool(hideable)):
            return views.layer(tx, existing)
        taken, name = name, _free_name(tx, name)
        notices.append(Notice('name', f'A layer named {taken} already exists with another declaration; this one was '
                                      f'named {name}.'))
    source_ids = _sources(tx, sources, notices)
    kept_tags = _tags(tags, notices)
    layer_id = new_id()
    stamp = home.now()
    record: dict[str, Any] | None = None
    if kind != 'memory':
        given = provenance or {}
        if not provenance:
            notices.append(Notice('provenance', f'Layer {name} was created without provenance; its record holds only '
                                                f'the module {module}.'))
        blinded = given.get('blinded')
        record = {'module': str(given.get('module') or module), 'workflow': given.get('workflow'),
                  'prompt': given.get('prompt'), 'model': given.get('model'), 'role': given.get('role'),
                  'blinded': None if blinded is None else int(bool(blinded))}
    tx.emit('add', 'layer', layer_id, layer_id, {
        'base_id': tx.base_id or '', 'name': name, 'module': module, 'variable': question,
        'mutable': bool(mutable), 'hideable': bool(hideable), 'result_id': result_id, 'kind': kind,
        'created': stamp, 'ready': stamp if (ready or kind == 'memory') else None,
        'fields': [str(field) for field in fields], 'tags': kept_tags, 'sources': source_ids,
        'hidden': False, 'provenance': record, 'reexamine': []})
    tx.created.add(layer_id)
    return dataclasses.replace(views.layer(tx, rows.layer(tx, layer_id)), notices=tuple(notices))


def finish(tx: Tx, layer: str) -> Layer | Outcome:
    """Mark a layer ready, STORE-024."""
    found = rows.layer(tx, layer)
    if found.finished:
        return Outcome((Notice('layer', f'Layer {found.name} is already finished; nothing changed.'),))
    tx.emit('change', 'layer', found.id, found.id, {'ready': home.now()})
    return views.layer(tx, rows.layer(tx, found.id))


def discard(tx: Tx, layer: str) -> Outcome:
    """Delete a knowledge layer's content and the layer; identity and type records stay, STORE-032."""
    found = rows.layer(tx, layer)
    base = tx.base
    layer_id = found.id

    def of_layer(kind: str) -> list[str]:
        return [ident for ident, held in base.versions.items()
                if base.kinds.get(ident) == kind and any(version.layer_id == layer_id for version in held)]

    # The base layer that made the map's elements and joins is the map itself; a layer of the base's kind that
    # holds only items on the map's nodes, such as fields or refs, is discarded like any other.
    if found.kind in BASE_KINDS and (of_layer('element') or of_layer('join')):
        return Outcome((Notice('layer', f'{found.name} is the base layer and is never discarded; the base '
                                        f'changes by refining: {rows.refine_step()}. Nothing changed.'),))
    if found.kind == 'memory':
        return Outcome((Notice('layer', f'{found.name} is memory and is never discarded; remove memories with '
                                        'metaform memory delete_entities <entityNames>. Nothing changed.'),))
    notices: list[Notice] = []
    for owner in versions.ORDER:
        for ident in of_layer(owner):
            held = base.versions.get(ident, [])
            for version in [version for version in held if version.layer_id == layer_id]:
                if owner == 'element':
                    heir = _heir(tx, ident, layer_id)
                    if heir is not None:
                        tx.emit('change', 'element', ident, heir, {'mode': 'place', 'layer_id': heir})
                        address = str(version['address'])
                        notices.append(Notice('element', f'The element at {address} was made by {found.name}, and '
                                                         f'layer {rows.layer(tx, heir).name} still holds something '
                                                         f'at it; the element was kept and now belongs to '
                                                         f'{rows.layer(tx, heir).name}.'))
                        continue
                if owner == 'item':
                    operations.cleanup(tx, 'item', ident)
                tx.emit('remove', owner, ident, layer_id, {'mode': 'place'})
    operations.cleanup(tx, 'layer', layer_id)
    tx.emit('remove', 'layer', layer_id, layer_id, {})
    return Outcome(tuple(notices))


def _heir(tx: Tx, element_id: str, leaving: str) -> str | None:
    """The first other layer that holds a property, an item or a join at the element, and no version of its own
    for it."""
    base = tx.base
    own_layers = {version.layer_id for version in base.versions.get(element_id, ())}
    address = base.address_of(element_id)
    candidates: list[tuple[int, int, str]] = []
    for ident, held in base.versions.items():
        kind = base.kinds.get(ident)
        for version in held:
            fields = version.fields
            if kind == 'property' and fields.get('element_id') == element_id:
                rank = 0
            elif kind == 'item' and ((fields.get('target_kind') == 'element' and fields.get('target_id') == element_id)
                                     or (fields.get('link_kind') == 'element' and fields.get('link_id') == element_id)):
                rank = 1
            elif kind == 'join' and (fields.get('receiver') == element_id or element_id in fields.get('held', ())
                                     or (address is not None and fields.get('element') == address)):
                rank = 2
            else:
                continue
            if version.layer_id != leaving and version.layer_id not in own_layers:
                candidates.append((rank, version.seq, version.layer_id))
    return min(candidates)[2] if candidates else None


def _held(found: LayerRow) -> Notice | None:
    """Why a layer is not hidden: it was declared not hideable."""
    if not found.hideable:
        return Notice('layer', f'Layer {found.name} is not hideable; it was declared so when it was made. Nothing '
                               'changed.')
    return None


def hide(tx: Tx, layer: str, hidden: bool) -> Outcome:
    found = rows.layer(tx, layer)
    stop = _held(found)
    if stop is not None:
        return Outcome((stop,))
    if found.hidden != hidden:
        tx.emit('change', 'layer', found.id, found.id, {'hidden': hidden})
    return Outcome()


def tag(tx: Tx, layer: str, name: Any) -> Outcome:
    found = rows.layer(tx, layer)
    notices: list[Notice] = []
    kept = [each for each in _tags([name], notices) if each not in found.tags]
    if kept:
        tx.emit('change', 'layer', found.id, found.id, {'tags': [*found.tags, *kept]})
    return Outcome(tuple(notices))


def untag(tx: Tx, layer: str, name: str) -> Outcome:
    found = rows.layer(tx, layer)
    if name in found.tags:
        tx.emit('change', 'layer', found.id, found.id, {'tags': [each for each in found.tags if each != name]})
    return Outcome()


def reexamined(tx: Tx, layer: str) -> Outcome:
    found = rows.layer(tx, layer)
    if found.reexamine:
        tx.emit('change', 'layer', found.id, found.id, {'reexamine': []})
    return Outcome()


def selection(tx: Tx, address: str, layer: str, kind: str) -> Outcome:
    """A select or mask row at an address, STORE-019."""
    found = rows.layer(tx, layer)
    notices: list[Notice] = []
    if not rows.address_form(address):
        notices.append(Notice('address', f'{address!r} is not in the address form; the {kind} was stored as given.'))
    if (address, found.id, kind) not in tx.base.selections:
        tx.emit('add', 'selection', f'{address}|{kind}|{found.id}', found.id,
                {'address': address, 'layer_id': found.id, 'kind': kind})
    return Outcome(tuple(notices))


def clear(tx: Tx, address: str, layer: str, kind: str) -> Outcome:
    if kind not in ('select', 'mask'):
        raise StoreError(f'{kind!r} is not select or mask.', f'metaform map clear {address} {layer} mask')
    found = rows.layer(tx, layer)
    if (address, found.id, kind) in tx.base.selections:
        tx.emit('remove', 'selection', f'{address}|{kind}|{found.id}', found.id,
                {'address': address, 'layer_id': found.id, 'kind': kind})
    return Outcome()


# Refining the base ---------------------------------------------------------------------------------------

def refine(tx: Tx, thing: str, changes: dict[str, Any] | None = None, *, remove: bool = False, reason: Any,
           evidence: Any = None) -> Version | Outcome:
    """Write a change or removal of a thing of the base as its newest version, in the base's own layer,
    LAYER-025. Every earlier version is kept.

    A key a refinement may not change, such as an element's address, is named in a notice and not applied; the rest
    is written, STORE-034. A join's receiver moves it, MAP-003, and `elements` gives the elements it holds; a change
    that does not name them keeps the ones it held. What a removal leaves pointing at the removed thing is orphaned
    and named, and the layers built from the base are marked for re-examination, STORE-036.
    """
    kind = rows.kind_of(tx, thing)
    notices: list[Notice] = []
    given = {str(key): value for key, value in (changes or {}).items()}
    current = versions.current_version(tx.base, kind, thing)
    if current is None:
        writes.split_changes(kind, given, notices)
        return Outcome((*notices, Notice('id', f'{thing} is not current in the base; nothing was written. See '
                                               f'metaform map history {thing}')))
    found = rows.layer(tx, current.layer_id)
    if found.kind not in BASE_KINDS:
        return Outcome((Notice('id', f'{thing} belongs to the knowledge layer {found.name}, not to the base; a '
                                     'knowledge layer is edited in place: metaform map knowledge '
                                     f'op=edit layer={found.name} id={thing} <field>=<value>. Nothing was '
                                     'written.'),))
    allowed = writes.split_changes(kind, given, notices)
    if not remove and given and not allowed:
        return Outcome(tuple(notices))
    columns: dict[str, Any] = dict(current.fields)
    split: list[tuple[str, Any]] = []
    if not remove:
        changed, split = writes.changed_columns(tx, kind, allowed, found, notices, current)
        held = changed.pop(writes.HELD, None)
        columns.update(changed)
        if kind == 'join':
            columns['held'] = held if held is not None else list(current.fields.get('held', ()))
    data: dict[str, Any] = {'mode': 'version', 'reason': rows.text(reason, 'reason', notices),
                            'evidence': rows.text(evidence, 'evidence', notices), **columns}
    if kind in ('item', 'property'):
        data['refs'] = [list(pair) for pair in current.refs]
    made = tx.emit('remove' if remove else 'change', kind, thing, found.id, data)
    if remove:
        notices += versions.orphaned_by(tx.base, kind, thing)
    versions.mark(tx, found.id, thing)
    if split:
        notices.append(Notice('extra', 'A refinement keeps no list of records in its extra; those records were not '
                                       'written.'))
    written = next(version for version in tx.base.versions[thing] if version.seq == made.seq)
    record = views.version(tx, kind, thing, written)
    return dataclasses.replace(record, notices=tuple(notices))
