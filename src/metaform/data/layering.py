"""Layer operations: create, finish, discard, hide, tag, select and mask, and refining the base, STORE-024.

Every function works inside one open write transaction. Nothing an agent sends
is refused for its content, BASE-044: an empty variable, a missing provenance,
a taken name, a tag or source that does not fit, are stored as given or
numbered, with a notice; a name that would be read as an id or is a project root
cannot name a layer and is refused, LAYER-028. An operation aimed at something that cannot change,
such as hiding a layer that is not hideable,
writes nothing and returns a notice saying why. A reference to no layer cannot
be read and raises `StoreError`, STORE-026. Every change is an op on the base's
projection, appended to the log at commit, STORE-046.
"""
from __future__ import annotations

import dataclasses
import json
from collections.abc import Sequence
from typing import Any

from .. import home
from ..errors import StoreError
from . import names, operations, rows, versions, views, writes
from .ids import LAYER_NAME, TAG, is_id, new_id
from .records import Layer, Node, Notice, Outcome, Version
from .selection import LayerRow, all_layers
from .session import Tx
from .versions import BASE_KINDS

KINDS = ('layer', 'base', 'memory')


def _root(name: str, next_step: str) -> None:
    """Refuse a layer name that is a project root: a layer's name is a namespace root, LAYER-028, and one named a
    project root would collide with the map's addresses."""
    if name in {root['name'] for root in names.roots()}:
        raise StoreError(f'{name!r} cannot be a layer name: it is a project root, and a layer\'s name is a namespace '
                         'root that would collide with the map, LAYER-028.', next_step)


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
    _root(name, 'metaform map knowledge op=create layer=<name> variable=<question>')
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
    # holds only items on the map's nodes, such as fields or refs, is discarded like any other, and so is an intake
    # still building, which no context read shows until it finishes, BASE-039.
    if found.kind in BASE_KINDS and found.finished and (of_layer('element') or of_layer('join')):
        return Outcome((Notice('layer', f'{found.name} is the base layer and is never discarded; the base '
                                        f'changes by refining: {rows.refine_step()}. Nothing changed.'),))
    if found.kind == 'memory':
        return Outcome((Notice('layer', f'{found.name} is memory and is never discarded. An agent records a '
                                        'correction with metaform memory add_observations; memories are deleted by '
                                        'the person, on the page\'s memory panel or with metaform memory '
                                        'delete_entities in their own terminal. Nothing changed.'),))
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


def rename(tx: Tx, layer: str, name: str, module: str) -> Outcome:
    """Give a layer a new name and owning module, keeping its id, items and provenance, so a module renamed keeps its
    layer's knowledge under the new names. A name already taken, or one that would be read as an id, is refused."""
    found = rows.layer(tx, layer)
    if not LAYER_NAME.fullmatch(name) or is_id(name):
        raise StoreError(f'{name!r} cannot be a layer name.', 'metaform map layers')
    _root(name, 'metaform map layers')
    if found.name == name and found.module == module:
        return Outcome()
    if found.name != name and tx.base.layer_by_name(name) is not None:
        return Outcome((Notice('name', f'A layer named {name} already exists; {found.name} was not renamed.'),))
    tx.emit('change', 'layer', found.id, found.id, {'name': name, 'module': module})
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
           evidence: Any = None, by: str | None = None) -> Version | Outcome:
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
                                     f'op=edit layer={found.name} id={thing} <field>=<value>. When it is part of '
                                     'what the project does, take it into the base, keeping its id: metaform map '
                                     f'refine {_naming(tx, kind, thing)} adopt=true reason=<why>. Nothing was '
                                     'written.'),))
    allowed = writes.base_only(kind, found, writes.split_changes(kind, given, notices), notices)
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
                            'evidence': rows.text(evidence, 'evidence', notices), 'by': by, **columns}
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


def notes_beside(tx: Tx, reason: str, by: str) -> dict[str, Any]:
    """Every note a current element or join of the base still holds, written before notes went beside it, moved to
    its one item of the notes layer, layout 23: added there, or put before the note an item there already holds, and
    the base's note cleared as a new version, so its history keeps the old text. Returns the counts and the ids moved,
    never the text."""
    report: dict[str, Any] = {'notes': 0, 'added': 0, 'merged': 0, 'moved': []}
    noted = [(kind, ident, version) for kind in ('element', 'join') for ident, version in tx.base.currents(kind)
             if versions.of_base(tx.base, version.layer_id) and str(version.fields.get('note') or '').strip()]
    if not noted:
        return report
    made = create(tx, versions.NOTES_LAYER, versions.NOTES_MODULE, versions.NOTES_VARIABLE, kind='layer',
                  mutable=True, hideable=True, ready=True)
    held = {(str(version.fields['target_kind']), str(version.fields['target_id'])): (ident, version)
            for ident, version in tx.base.currents('item', layer_id=made.id)}
    for kind, ident, version in noted:
        note = str(version.fields['note'])
        beside = held.get((kind, ident))
        if beside is None:
            writes.add_item(tx, made.name, Node.of(kind, ident), note)
            report['added'] += 1
        else:
            kept = json.loads(str(beside[1].fields['value']))
            if note not in str(kept):
                writes.edit(tx, beside[0], {'value': f'{note}\n\n{kept}'})
            report['merged'] += 1
        tx.emit('change', kind, ident, version.layer_id, {
            'mode': 'version', 'reason': reason, 'evidence': None, 'by': by, **version.fields, 'note': None})
        report['moved'].append(f'{kind}:{ident}')
    report['notes'] = len(noted)
    return report


# Growing the base -----------------------------------------------------------------------------------------
#
# The base grows and is corrected after the intake under the intake's own rules, LAYER-025: what is added is an
# element (address, name_length, name, role, block and within) or a purpose record (receiver, its providing elements,
# purpose, ef and ifd), written by the same writes the intake's records go through, so the same notices hold it to the
# intake's form. The base holds RE, PE, OP and EF only, so nothing else is a field of what is added here. Every version
# written carries its reason, evidence and who wrote it. The intake's verification pass and `map refine` both grow the
# base through these functions.

ELEMENT_SHAPE = ('role', 'name')  # the element fields named when missing, as the intake names them
PURPOSE_SHAPE = ('purpose', 'ef', 'ifd')  # the purpose record fields named when missing, as the intake names them


def finished_base(tx: Tx) -> LayerRow | None:
    """The base's own layer once its intake is finished: the layer the base grows in. None while it has none."""
    return next((layer for layer in tx.base.layers.values() if layer.kind in BASE_KINDS and layer.ready is not None),
                None)


def _unfinished() -> Outcome:
    return Outcome((Notice('base', 'This map has no finished intake, so there is no base to grow; the intake records '
                                   'it first: metaform intake start. Nothing was written.'),))


def _missing(given: dict[str, Any], names: Sequence[str], notices: list[Notice]) -> None:
    for name in names:
        if given.get(name) is None:
            notices.append(Notice(name, f'{name} is missing; stored empty.'))


def _said(reason: Any, evidence: Any, by: str | None, notices: list[Notice]) -> dict[str, Any]:
    """The provenance every version of a growth carries; a missing reason is stored empty and named, BASE-044."""
    if reason is None or (isinstance(reason, str) and not reason.strip()):
        notices.append(Notice('reason', 'reason is missing; stored empty. Say why the base changes, so it can be '
                                        'explained later.'))
    return {'reason': rows.text(reason, 'reason', notices), 'evidence': rows.text(evidence, 'evidence', notices),
            'by': by}


def grow_element(tx: Tx, address: Any, *, name_length: Any = None, name: Any = None, role: Any = None,
                 block: Any = None, within: Any = None, reason: Any = None, evidence: Any = None,
                 by: str | None = None) -> Any:
    """Add an element to the finished base, in its own layer, LAYER-025: written as the intake writes one, with the
    same notices, and with its reason, evidence and author. An address the base already holds is returned as it is,
    with the notices `writes.add_element` gives for the fields it did not apply."""
    found = finished_base(tx)
    if found is None:
        return _unfinished()
    notices: list[Notice] = []
    if isinstance(address, str) and rows.current_element(tx, address) is None:
        _missing({'role': role, 'name': name}, ELEMENT_SHAPE, notices)
    tx.provenance = _said(reason, evidence, by, notices)
    try:
        made = writes.add_element(tx, found.name, address, name_length=name_length, role=role, name=name,
                                  block=block, within=within)
    finally:
        tx.provenance = None
    if isinstance(made, Outcome):
        return Outcome((*notices, *made.notices))
    versions.mark(tx, found.id, made.id)
    return dataclasses.replace(made, notices=(*notices, *made.notices))


def grow_join(tx: Tx, receiver: Any, elements: Any, *, purpose: Any = None, ef: Any = None, ifd: Any = None,
              reason: Any = None, evidence: Any = None, by: str | None = None) -> Any:
    """Add a purpose record to the finished base, in its own layer, LAYER-025, as the intake writes one: an element
    it names that the map lacks is made there with it, named in a notice. Every version carries its reason, evidence
    and author."""
    found = finished_base(tx)
    if found is None:
        return _unfinished()
    notices: list[Notice] = []
    _missing({'purpose': purpose, 'ef': ef, 'ifd': ifd}, PURPOSE_SHAPE, notices)
    tx.provenance = _said(reason, evidence, by, notices)
    try:
        made = writes.add_join(tx, found.name, receiver, elements, purpose=purpose, ef=ef, ifd=ifd)
    finally:
        tx.provenance = None
    if isinstance(made, Outcome):
        return Outcome((*notices, *made.notices))
    versions.mark(tx, found.id, made.id)
    return dataclasses.replace(made, notices=(*notices, *made.notices))


def _naming(tx: Tx, kind: str, thing: str) -> str:
    """How `map refine` names a thing: an element by its address, a join by its receiver and an element it holds."""
    current = versions.current_version(tx.base, kind, thing)
    if current is None or kind not in ('element', 'join'):
        return f'id={thing}'
    if kind == 'element':
        return f'address={current.fields.get("address")}'
    held = list(current.fields.get('held') or ())
    receiver = tx.base.address_of(str(current.fields.get('receiver')))
    provider = tx.base.address_of(str(held[0])) if held else None
    return f'receiver={receiver} provider={provider}'


def _carry(tx: Tx, kind: str, thing: str, changes: dict[str, Any], said: dict[str, Any],
           layer_id: str | None = None) -> None:
    """A new version of a thing with these fields changed and every other field kept, in its own layer or in
    `layer_id`; every earlier version is kept, LAYER-025."""
    current = versions.current_version(tx.base, kind, thing)
    if current is None:
        return
    target = layer_id or current.layer_id
    data: dict[str, Any] = {'mode': 'version', **said, **current.fields, **changes}
    if kind in ('item', 'property'):
        data['refs'] = [list(pair) for pair in current.refs]
    tx.emit('change', kind, thing, target, data)
    versions.mark(tx, target, thing)


def adopt(tx: Tx, thing: str, *, reason: Any = None, evidence: Any = None, by: str | None = None) -> Outcome:
    """Take an element or purpose record a knowledge layer holds into the finished base, as its newest version there,
    keeping its id, so the tickets, knowledge and memories at it stay: a feature recorded in a knowledge layer reaches
    the base without a copy, LAYER-025. A purpose record's receiver and elements that live in knowledge layers come
    with it, so the base never depends on a layer that can be hidden."""
    found = finished_base(tx)
    if found is None:
        return _unfinished()
    kind = rows.kind_of(tx, thing)
    if kind not in ('element', 'join'):
        raise StoreError(f'{thing} is a {kind}; only an element or a purpose record is part of the base.',
                         'metaform map refine address=<address> adopt=true reason=<why>')
    current = versions.current_version(tx.base, kind, thing)
    if current is None:
        return Outcome((Notice('id', f'{thing} is not current; nothing was written. See metaform map history '
                                     f'{thing}'),))
    notices: list[Notice] = []
    said = _said(reason, evidence, by, notices)
    things = [thing]
    if kind == 'join':
        things += [str(current.fields.get('receiver')), *(str(each) for each in current.fields.get('held') or ())]
    taken = 0
    for ident in dict.fromkeys(things):
        held = versions.current_version(tx.base, rows.kind_of(tx, ident), ident)
        if held is None or rows.layer(tx, held.layer_id).kind in BASE_KINDS:
            continue
        _carry(tx, rows.kind_of(tx, ident), ident, {}, said, found.id)
        taken += 1
    if not taken:
        notices.append(Notice('id', f'{_naming(tx, kind, thing)} is in the base already; nothing was written.'))
    else:
        notices.append(Notice('adopted', f'{taken} taken into the base {found.name}, each keeping its id and every '
                                         'earlier version.'))
    return Outcome(tuple(notices))


def move(tx: Tx, thing: str, address: Any, *, reason: Any = None, evidence: Any = None,
         by: str | None = None) -> Any:
    """Rename an element of the base, or merge it into the element at `address`. An address is an element's identity,
    MAP-015, so the element at the new address takes the old one's place: it is made in the base with the old one's
    name_length, name, role, block and within when the base holds none there. Every purpose record that receives or
    holds the old element moves to it, as does every item and property of a knowledge layer at it, each as a new
    version that keeps every earlier one. Children whose explicit within names the old address name the new one
    instead, keeping their earlier versions, and the old element is removed. Refs of the sources layer never move:
    each stays where it was linked and is named, with the call that links its file at the new place. Tickets and
    memories are moved by the modules that keep them. Returns the element at the new address, with what moved in its
    notices."""
    found = finished_base(tx)
    if found is None:
        return _unfinished()
    old = versions.current_version(tx.base, 'element', thing)
    if old is None or rows.layer(tx, old.layer_id).kind not in BASE_KINDS:
        return Outcome((Notice('address', f'{thing} is not an element of the base; nothing was moved.'),))
    if not isinstance(address, str) or not address:
        raise StoreError(f'{address!r} is not an address.', 'metaform map refine address=<old> to_address=<new>')
    old_address = str(old.fields.get('address'))
    if address == old_address:
        return Outcome((Notice('to_address', f'{address} is where the element is; nothing was moved.'),))
    notices: list[Notice] = []
    said = _said(reason, evidence, by, notices)
    target = rows.current_element(tx, address)
    if target is None:
        tx.provenance = said
        try:
            made = writes.add_element(tx, found.name, address, name_length=old.fields.get('name_length'),
                                      role=old.fields.get('role'), name=old.fields.get('name'),
                                      block=old.fields.get('block'), within=old.fields.get('within'))
        finally:
            tx.provenance = None
        assert not isinstance(made, Outcome)
        notices += made.notices
        target_id = made.id
    else:
        target_id = str(target['element_id'])
        notices.append(Notice('to_address', f'{old_address} was merged into the element at {address}, which keeps '
                                            'its own name, name_length, role, block and within.'))
    children = [ident for ident, current in tx.base.currents('element')
                if ident not in (thing, target_id) and current.fields.get('within') == old_address]
    for child_id in children:
        _carry(tx, 'element', child_id, {'within': address}, said)
    joins = sorted(set(tx.base.joins_received(thing)) | set(tx.base.joins_holding(thing)))
    for join_id in joins:
        current = versions.current_version(tx.base, 'join', join_id)
        if current is None:
            continue
        receiver = target_id if current.fields.get('receiver') == thing else current.fields.get('receiver')
        held = list(dict.fromkeys(target_id if each == thing else each for each in current.fields.get('held') or ()))
        if receiver in held:
            notices.append(Notice('elements', f'A purpose record now holds its own receiver, {address}; it was moved '
                                              'as given, D82.'))
        _carry(tx, 'join', join_id, {'receiver': receiver, 'held': held}, said)
    carried = 0
    sources = tx.base.layer_by_name('sources')
    for item_id in tx.base.items_at('element', thing):
        current = versions.current_version(tx.base, 'item', item_id)
        if current is None:
            continue
        if sources is not None and current.layer_id == sources.id:
            notices.append(Notice('refs', f'A ref stays where it was linked, at {old_address}: refs never move. Link '
                                          f'its file at the new place: metaform dispatch link file=<path> '
                                          f'node={address}'))
            continue
        _carry(tx, 'item', item_id, {'target_id': target_id}, said)
        carried += 1
    for item_id in tx.base.items_linking('element', thing):
        _carry(tx, 'item', item_id, {'link_id': target_id}, said)
        carried += 1
    for property_id in tx.base.properties_of(thing):
        _carry(tx, 'property', property_id, {'element_id': target_id}, said)
        carried += 1
    tx.emit('remove', 'element', thing, old.layer_id, {'mode': 'version', **said, **old.fields})
    versions.mark(tx, old.layer_id, thing)
    notices.append(Notice('moved', f'{old_address} -> {address}: {len(joins)} purpose records and {carried} items and '
                                   'properties of knowledge layers moved with it.'))
    record = views.element(tx, target_id, None)
    assert record is not None
    return dataclasses.replace(record, notices=tuple(notices))


ADD_ELEMENT = ('metaform map refine address={address} name=<its name> name_length=<n> role=<CQU, DE, SE or NE> '
               'reason=<why> evidence=<what shows it>')
ADD_PURPOSE = ('metaform map refine receiver=<its RE> elements=["{address}"] purpose=<the OP> ef=<the EF> '
               'ifd=<sends, receives or both> reason=<why>')


def _in_base(tx: Tx, kind: str, ident: str) -> bool | None:
    """Whether a thing's current version is in the base: None when it is not current at all."""
    current = versions.current_version(tx.base, kind, ident)
    if current is None:
        return None
    return rows.layer(tx, current.layer_id).kind in BASE_KINDS


def landing(tx: Tx, kind: str, ident: str, work_id: str | None = None) -> tuple[Notice, ...]:
    """Whether a finished ticket's work is on the map in use, LAYER-025: its node, and every place its session linked
    a file at, each an element of the base that serves a purpose record of the base, or a purpose record of the base.
    Each gap is a notice with the refine call that closes it; nothing is refused, BASE-044. Reads the ticket's node and
    its own refs alone."""
    if finished_base(tx) is None:
        return ()
    places: list[tuple[str, str]] = [(kind, ident)]
    if work_id:
        from . import refs as ref_records
        places += [(ref.node.kind, ref.node.id) for ref in ref_records.current(tx)
                   if ref.by and f'work {work_id}' in ref.by]
    notices: list[Notice] = []
    for place_kind, place in dict.fromkeys(places):
        if place_kind == 'join':
            if not _in_base(tx, 'join', place):
                notices.append(Notice('map', f'The purpose record this work is at is not on the map in use. Put it '
                                             f'there: metaform map refine {_naming(tx, "join", place)} adopt=true '
                                             'reason=<why>, or add it: ' + ADD_PURPOSE.format(address='<element>')))
            continue
        in_base = _in_base(tx, 'element', place)
        address = tx.base.address_of(place) or (place if not is_id(place) else None)
        if address is None:
            continue
        if in_base is None:
            notices.append(Notice('map', f'{address} is not on the map in use, so what this work built there is not '
                                         'either. Add it, then the purpose record it serves: '
                                         f'{ADD_ELEMENT.format(address=address)}; then '
                                         f'{ADD_PURPOSE.format(address=address)}'))
        elif not in_base:
            notices.append(Notice('map', f'{address} is held by a knowledge layer, not the map in use. Take it in, '
                                         f'keeping its id: metaform map refine address={address} adopt=true '
                                         'reason=<why>'))
        elif not any(_in_base(tx, 'join', join_id) for join_id in
                     (*tx.base.joins_received(place), *tx.base.joins_holding(place))):
            notices.append(Notice('map', f'{address} is on the map in use but serves no purpose record there. Add the '
                                         f'one it serves: {ADD_PURPOSE.format(address=address)}'))
    return tuple(notices)
