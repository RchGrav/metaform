"""Refs as records of the sources layer, STORE-012, MAP-021, CTX-065 and CTX-066, code.graph.knowledge#c.

A ref is one item of the sources layer at the element or join it is linked at. Its value is its ref_id, a proper noun
for what it references, unique in the base and never a field name of a node (CTX-087): for code the code's own
qualified name, such as `metaform.modules.voice.engine`. Its refs are its key and value, such as `path` and a file of
the project, then its details, such as the lines and objects in that file. Its extra says who linked it, when, and
which place the link named. A ref is only ever written as a new version of that item: a link, a move, an edit and a
removal each add one, so its id lasts, a removed ref reads in its history, and the history keeps every place it was
linked. A ref is named `{ref_id}@{address}`; what a `:{join}` part names is open (question 25 of CTX), so a ref on a
join is named at its receiver's Address and its record says which join.

A ref is not a property: it stays at the one element or join it was linked at, never moves toward the trunk, never
inherits and applies nowhere else, code.graph.knowledge#17. The same key and value linked at another place is a second
ref there, with a name of its own. Linked again where it is, nothing changes but details added.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any

from .. import home
from ..errors import StoreError
from ..wording import count
from . import rows
from .ids import as_object, encode_extra, encode_value, is_id, new_id, refs_fit
from .projection import Projection, Version
from .records import Node, Notice, Outcome, Ref, SourceRef
from .selection import LayerRow
from .session import Tx

SOURCES = 'sources'  # the layer every ref is a record of, MAP-021
PRIMARY = 'path'  # the key that starts a ref when a list of pairs is split: the pairs after it are its details
NAME = re.compile(r'^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)*$')  # a ref_id: Address segments, either case
LINE_MARK = re.compile(r':\d+(-\d+)?(,\d+(-\d+)?)*$')  # file.py:12 names file.py
UNSAFE = re.compile(r'[^A-Za-z0-9_]+')
# The fields every node is read by on `this`, never ref names, CTX-087; whether `this`'s other names are reserved too
# is open question 19 of CTX. The `this` reader imports this list when refs read flat on it, CTX-085.
RESERVED = ('name', 'address', 'role', 'parent', 'layer', 'note', 'work', 'messages', 'memories', 'context', 'items',
            'properties', 'purpose')


Spot = tuple[str, str, str, str]  # a ref's key and value and the kind and id of the node it is linked at


@dataclass
class _Held:
    """The refs of the sources layer, read once per write: every name, current or removed, and each current ref and
    each removed one by its key and value at its place."""
    by_name: dict[str, str] = field(default_factory=dict[str, str])
    current: dict[Spot, str] = field(default_factory=dict[Spot, str])
    removed: dict[Spot, str] = field(default_factory=dict[Spot, str])


# Reading a record ---------------------------------------------------------------------------------------------

def layer(base: Projection) -> LayerRow | None:
    return base.layer_by_name(SOURCES)


def _extra(version: Version) -> dict[str, Any]:
    text = version.fields.get('extra')
    found = as_object(json.loads(text)) if isinstance(text, str) else None
    return found or {}


def is_record(version: Version) -> bool:
    """Whether an item version is a ref record: one written here says which place it was linked at. An item the
    sources layer held before layout 22, a list of refs at an element, is not."""
    return 'linked' in _extra(version)


def name_of(version: Version) -> str:
    return str(json.loads(str(version.fields['value'])))


def records(base: Projection) -> Iterator[tuple[str, list[Version]]]:
    """Every ref record of the base, current or removed, in the order it was first linked."""
    found = layer(base)
    if found is None:
        return
    for ident, held in base.versions.items():
        if held and base.kinds.get(ident) == 'item' and held[0].layer_id == found.id and is_record(held[0]):
            yield ident, held


def _held(base: Projection) -> _Held:
    made = _Held()
    for ident, held in records(base):
        made.by_name[name_of(held[0])] = ident
        newest = held[-1]
        if newest.refs:
            (made.removed if newest.op == 'remove' else made.current)[_spot_of(newest)] = ident
    return made


def _spot_of(version: Version, pair: tuple[str, str] | None = None) -> Spot:
    key, value = pair or version.refs[0]
    return key, value, str(version.fields['target_kind']), str(version.fields['target_id'])


def _place(tx: Tx, version: Version) -> tuple[str | None, str | None]:
    """The address a version sits at and its join: a join's is its receiver's."""
    kind, target = str(version.fields['target_kind']), str(version.fields['target_id'])
    return rows.node_address(tx, kind, target), (target if kind == 'join' else None)


def named(name: str, address: str | None) -> str:
    """A ref's name, `{ref_id}@{address}`, CTX-066. A ref on a join is named at its receiver's Address: what the `:`
    part names is open question 25 of CTX, so no `:` part is written; the record's `join` says which join it is."""
    return f'{name}@{address}'


def record(tx: Tx, ident: str, version: Version, notices: Sequence[Notice] = ()) -> SourceRef:
    extra = _extra(version)
    address, join = _place(tx, version)
    name = name_of(version)
    pairs = version.refs or [('', '')]
    return SourceRef(ident, name, named(name, address), pairs[0][0], pairs[0][1],
                     tuple(Ref(key, value) for key, value in pairs[1:]),
                     Node.of(str(version.fields['target_kind']), str(version.fields['target_id'])), address, join,
                     extra.get('linked'), extra.get('by'), extra.get('at'), version.reason, version.op == 'remove',
                     tuple(notices))


def current(tx: Tx, node: Node | None = None) -> tuple[SourceRef, ...]:
    """Every current ref, or those linked at one node, by id or address, in the order each was first linked."""
    if node is not None and node.kind != 'join' and tx.base.kinds.get(node.id) != 'element':
        node = Node('element', tx.base.element_at(node.id) or node.id)
    made: list[SourceRef] = []
    for ident, held in records(tx.base):
        newest = held[-1]
        if newest.op == 'remove':
            continue
        if node is not None and (str(newest.fields['target_kind']), str(newest.fields['target_id'])) != (
                node.kind, node.id):
            continue
        made.append(record(tx, ident, newest))
    return tuple(made)


def read(tx: Tx, given: str) -> SourceRef | None:
    """A ref by its id, its ref_id, or its name `{ref_id}@{address}`, any `:` part after the Address read past, open
    question 25 of CTX. The ref_id alone is its identity: a name whose Address is not where the ref is linked answers
    with where it is, and a notice saying so, CTX-066."""
    text = given.strip()
    if is_id(text):
        held = tx.base.versions.get(text)
        if not held or tx.base.kinds.get(text) != 'item' or not is_record(held[0]):
            return None
        return record(tx, text, held[-1])
    name, _, place = text.partition('@')
    ident = _held(tx.base).by_name.get(name)
    if ident is None:
        return None
    newest = tx.base.versions[ident][-1]
    found = record(tx, ident, newest)
    notices: list[Notice] = []
    address = place.partition(':')[0]
    if address and address != found.address:
        notices.append(Notice('ref', f'{name} is not linked at {address}; it is linked at {found.address}: '
                                     f'{found.ref}.'))
    if found.removed:
        notices.append(Notice('ref', f'{name} was removed; this is its last version. Its history: metaform map history '
                                     f'{ident}'))
    return record(tx, ident, newest, notices) if notices else found


# Names --------------------------------------------------------------------------------------------------------

def _segments(text: str) -> list[str]:
    return [cleaned for cleaned in (UNSAFE.sub('_', part).strip('_') for part in text.split('.')) if cleaned]


def derived(key: str, value: str, taken: Iterable[str]) -> str:
    """A ref_id made from what a ref names, for a link that gives none and for the migration, reported for review.
    A path names its file as code does, the folders then the file's name without its extension and without a leading
    `src`: `src/metaform/data/refs.py` is `metaform.data.refs`, and a package's `__init__.py` is the package. Anything
    else is its value, made into segments. A name
    taken by another ref gets the extension, then `_2`, `_3`."""
    text = LINE_MARK.sub('', value.strip()).replace('\\', '/')
    extension = ''
    if key == PRIMARY or '/' in text:
        parts = [part for part in text.split('/') if part not in ('', '.', '..')]
        if len(parts) > 1 and parts[0] == 'src':
            parts = parts[1:]
        if parts:
            last = parts[-1]
            stem, dot, extension = last.rpartition('.')
            if dot and stem:
                parts[-1] = stem
            else:
                extension = ''
            if parts[-1] == '__init__' and len(parts) > 1:  # a package's own module is named as the package
                parts = parts[:-1]
        segments = [segment for part in parts for segment in _segments(part)]
    else:
        segments = _segments(text)
    base = '.'.join(segments) or (_segments(key) or ['ref'])[0]
    if is_id(base):
        base = f'{key}_{base}'
    held = set(taken) | set(RESERVED)
    choices = [base] + ([f'{base}_{UNSAFE.sub("_", extension)}'] if extension else [])
    for choice in choices:
        if choice not in held:
            return choice
    number = 2
    while f'{choices[-1]}_{number}' in held:
        number += 1
    return f'{choices[-1]}_{number}'


def _name_problem(name: str) -> str | None:
    """Why a ref_id given cannot be used, by its form only, never its sense: the store does not judge a name."""
    if not NAME.fullmatch(name) or is_id(name):
        return (f'{name!r} cannot be a ref_id: it is a proper noun of segments of letters, digits and underscores, '
                'joined by periods, such as metaform.data.refs, and not a 32-character id.')
    if name in RESERVED:
        return (f'{name} is a field every node is read by, this.{name}, so it is never a ref name, CTX-087. The '
                f'reserved names are {", ".join(RESERVED)}; give the ref another name, or leave it off to have one '
                'made from what it names.')
    return None


# Places -------------------------------------------------------------------------------------------------------

def _spot(address: str | None, join: str | None, kind: str, target: str) -> str:
    """A place as text: the address, then `:` and the join on a join; a place with no address, an orphan, by its
    kind and id."""
    if address is None:
        return f'{kind}:{target}'
    return address if join is None else f'{address}:{join}'


def _node(tx: Tx, node: Node, found: LayerRow, notices: list[Notice]) -> tuple[str, str]:
    """The kind and id of the node a ref is linked at: a node named by an id the base knows is that node, current or
    not, so a ref the migration carries from an orphan stays there; an address is resolved as an item's target is."""
    if node.kind in ('element', 'join') and tx.base.kinds.get(node.id) == node.kind:
        return node.kind, node.id
    return rows.node_at(tx, node, found, 'node', notices)


# Writing ------------------------------------------------------------------------------------------------------

def sources(tx: Tx) -> LayerRow:
    """The sources layer, made when the base has none, MAP-021."""
    found = layer(tx.base)
    if found is None:
        from . import layering
        layering.create(tx, SOURCES, 'intake', 'refs', kind='layer', mutable=True, hideable=True, ready=True)
        found = layer(tx.base)
        assert found is not None
    return found


def _write(tx: Tx, op: str, ident: str, found: LayerRow, *, name: str, kind: str, target: str,
           pairs: Sequence[tuple[str, str]], linked: str | None, by: str | None, why: str | None,
           first: bool = False) -> Version:
    """One version of a ref, every field written whole, so each version reads alone. Who linked it, when, where and
    why are in its extra, so a read of the node shows them beside the ref, CTX-065; why is its version's reason too."""
    extra = {'by': by, 'at': home.now(), 'linked': linked, 'why': why}
    made = tx.emit(op, 'item', ident, found.id, {
        'mode': 'add' if first else 'version', 'reason': why, 'evidence': None, 'target_kind': kind,
        'target_id': target, 'value': encode_value(name, 'the ref'), 'link_kind': None, 'link_id': None,
        'extra': encode_extra(extra, 'the ref'), 'read_first': 0, 'always_show': 0,
        'refs': [list(pair) for pair in pairs]})
    return next(version for version in tx.base.versions[ident] if version.seq == made.seq)


def _text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)


def link(tx: Tx, key: Any, value: Any, node: Node, *, name: str | None = None,
         details: Iterable[tuple[str, str]] = (), by: str | None = None, why: str | None = None,
         held: _Held | None = None) -> SourceRef | Outcome:
    """Link a ref at a node: a new ref there, or the ref already naming this key and value at this node linked again,
    which adds the details it lacks. The same key and value linked at another node is a ref of its own; no ref moves.
    A ref_id taken by another ref is refused with that ref named; so is a ref_id given for a key and value another ref
    at this node already names. A removed ref linked again at its node comes back under its own id."""
    key, value = _text(key).strip(), _text(value).strip()
    if not key or not value:
        return Outcome((Notice('ref', 'A ref is a key and a value, both given; nothing was linked.'),))
    if name is not None:
        name = name.strip()
        problem = _name_problem(name)
        if problem is not None:
            return Outcome((Notice('name', problem + ' Nothing was linked.'),))
    found = sources(tx)
    notices: list[Notice] = []
    kind, target = _node(tx, node, found, notices)
    address = rows.node_address(tx, kind, target)
    join = target if kind == 'join' else None
    known = held if held is not None else _held(tx.base)
    pair = (key, value)
    spot = (key, value, kind, target)
    ident = known.current.get(spot) or known.removed.get(spot)
    if name is not None:
        holder = known.by_name.get(name)
        if holder is not None and holder != ident:
            other = record(tx, holder, tx.base.versions[holder][-1])
            return Outcome((Notice('name', f'{name} is taken: it names {other.key}={other.value}, at {other.ref}'
                                           f'{" (removed)" if other.removed else ""}. Nothing was linked; give '
                                           'another name.'),))
        if ident is not None and holder != ident:
            other = record(tx, ident, tx.base.versions[ident][-1])
            return Outcome((Notice('name', f'{key}={value} is already linked here as {other.ref}; link it by that '
                                           'name, or leave the name off. Nothing was linked.'),))
    given = [(str(one[0]), str(one[1])) for one in details]
    place = _spot(address, join, kind, target)
    if ident is None:
        name = name or derived(key, value, known.by_name)
        ident = new_id()
        version = _write(tx, 'add', ident, found, name=name, kind=kind, target=target, pairs=[pair, *given],
                         linked=place, by=by, why=why, first=True)
        known.by_name[name] = ident
        known.current[spot] = ident
        return record(tx, ident, version, notices)
    newest = tx.base.versions[ident][-1]
    name = name_of(newest)
    if newest.op == 'remove':
        version = _write(tx, 'change', ident, found, name=name, kind=kind, target=target, pairs=[pair, *given],
                         linked=place, by=by, why=why or 'linked again after it was removed')
        known.removed.pop(spot, None)
        known.current[spot] = ident
        return record(tx, ident, version, notices)
    merged = list(newest.refs) + [one for one in given if one not in newest.refs]
    if merged == list(newest.refs):  # linked again where it is: nothing changes
        return record(tx, ident, newest, [*notices, Notice('linked', f'{name} is linked at {place} already; '
                                                                     'nothing changed.')])
    version = _write(tx, 'change', ident, found, name=name, kind=kind, target=target, pairs=merged, linked=place,
                     by=by, why=why or 'details added')
    return record(tx, ident, version, notices)


def groups(pairs: Iterable[tuple[str, str]]) -> list[list[tuple[str, str]]]:
    """A list of pairs as refs: a path starts a ref and the pairs after it, up to the next path, are its details; a
    pair before any path is a ref of its own."""
    made: list[list[tuple[str, str]]] = []
    for pair in pairs:
        if pair[0] == PRIMARY or not made or made[-1][0][0] != PRIMARY:
            made.append([pair])
        else:
            made[-1].append(pair)
    return made


def link_all(tx: Tx, node: Node, given: Iterable[Any], *, by: str | None = None,
             why: str | None = None) -> tuple[list[SourceRef], list[Notice]]:
    """Every ref in a list of pairs linked at one node, split by `groups`. A ref that is not a key and a value, both
    text, is never refused, STORE-026: a key or value that is not text is linked as its JSON text, as `add_ref` takes
    it, an object of one entry is that key and value, and anything else is linked under the key `ref` as its JSON."""
    pairs: list[tuple[str, str]] = []
    odd = 0
    for one in given:
        fit, _ = refs_fit([one])
        if fit:
            pairs += fit
            continue
        odd += 1
        mapping = as_object(one)
        if mapping is not None and 'key' in mapping and 'value' in mapping:
            pairs.append((_text(mapping['key']), _text(mapping['value'])))
        elif mapping is not None and len(mapping) == 1:
            [(key, value)] = mapping.items()
            pairs.append((str(key), _text(value)))
        elif isinstance(one, (list, tuple)) and len(one) == 2:  # type: ignore[arg-type]
            pairs.append((_text(one[0]), _text(one[1])))  # type: ignore[index]
        else:
            pairs.append(('ref', _text(one)))
    notices = [Notice('refs', f'A ref is a key and a value, both text; {count(odd)} {"was" if odd == 1 else "were"} '
                              'not, and linked as text.')] if odd else []
    made: list[SourceRef] = []
    for group in groups(pairs):
        result = link(tx, group[0][0], group[0][1], node, details=group[1:], by=by, why=why)
        notices += list(result.notices)
        if isinstance(result, SourceRef):
            made.append(result)
    return made, notices


def place(tx: Tx, node: Node, given: Iterable[Any], *, by: str | None = None, why: str | None = None) -> list[Notice]:
    """The refs given for a node, as the intake and an element's write give them, replacing what was linked there:
    each linked, and each ref at this node that is not among them removed."""
    linked, notices = link_all(tx, node, given, by=by, why=why)
    keep = {one.id for one in linked}
    kind, target = _node(tx, node, sources(tx), notices)
    here = _spot(rows.node_address(tx, kind, target), target if kind == 'join' else None, kind, target)
    for one in current(tx, Node.of(kind, target)):
        if one.id not in keep:
            notices += list(unlink(tx, one.id, by=by, why=why or f'not among the refs given for {here}').notices)
    return notices


def unlink(tx: Tx, ident: str, *, by: str | None = None, why: str | None = None) -> Outcome:
    """Remove a ref: a version that removes it, so its history keeps it."""
    held = tx.base.versions.get(ident)
    if not held or not is_record(held[0]):
        raise StoreError(f'No ref has the id {ident}.', 'metaform map node node=element:<address>')
    newest = held[-1]
    if newest.op == 'remove':
        return Outcome((Notice('ref', f'{name_of(newest)} was already removed.'),))
    found = sources(tx)
    _write(tx, 'remove', ident, found, name=name_of(newest), kind=str(newest.fields['target_kind']),
           target=str(newest.fields['target_id']), pairs=newest.refs, linked=_extra(newest).get('linked'), by=by,
           why=why)
    return Outcome()


def edit(tx: Tx, ident: str, changes: dict[str, Any], *, by: str | None = None) -> SourceRef | Outcome:
    """Change a ref's key, value or details as a new version, its id kept: `refs` gives them whole, its key and value
    first. Its ref_id is its identity and is not changed, and its place never changes."""
    held = tx.base.versions.get(ident)
    if not held or not is_record(held[0]):
        raise StoreError(f'No ref has the id {ident}.', 'metaform map node node=element:<address>')
    newest = held[-1]
    if newest.op == 'remove':
        return Outcome((Notice('ref', f'{name_of(newest)} was removed; link it again to change it.'),))
    notices: list[Notice] = []
    for key in changes:
        if key not in ('refs', 'reason'):
            notices.append(Notice(key, f'{key} is not changed on a ref: its ref_id is its identity, and it stays where '
                                       'it was linked; link it elsewhere with metaform dispatch link. Give refs, its '
                                       'key and value first.'))
    pairs, _ = refs_fit(changes.get('refs') or ())
    if not pairs:
        return Outcome((*notices, Notice('refs', 'No refs were given; nothing was written.')))
    other = _held(tx.base).current.get(_spot_of(newest, pairs[0]))
    if other is not None and other != ident:
        found = record(tx, other, tx.base.versions[other][-1])
        return Outcome((*notices, Notice('refs', f'{pairs[0][0]}={pairs[0][1]} is linked already as {found.ref}; '
                                                 'nothing was written.')))
    if pairs == list(newest.refs):
        return record(tx, ident, newest, notices)
    reason = changes.get('reason')
    version = _write(tx, 'change', ident, sources(tx), name=name_of(newest), kind=str(newest.fields['target_kind']),
                     target=str(newest.fields['target_id']), pairs=pairs, linked=_extra(newest).get('linked'), by=by,
                     why=str(reason) if reason is not None else 'edited')
    return record(tx, ident, version, notices)


# The migration, layout 22 ---------------------------------------------------------------------------------------

def migrate(tx: Tx, by: str = 'layout 22') -> dict[str, Any]:
    """Every current item the sources layer held before layout 22, a list of refs at an element or a join, written
    as ref records by `groups`, each at the place its item was, in the order they were written, and then removed, so
    its history keeps it. Returns the counts before and after, and each ref's name and place, for review."""
    found = layer(tx.base)
    report: dict[str, Any] = {'items': 0, 'pairs': 0, 'refs': 0, 'versions': 0, 'names': {}, 'unlinked': 0}
    if found is None:
        return report
    old = [(ident, version) for ident, version in tx.base.currents('item')
           if version.layer_id == found.id and not is_record(version)]
    known = _held(tx.base)
    before = tx.base.seq
    for ident, version in old:
        report['items'] += 1
        report['pairs'] += len(version.refs)
        node = Node.of(str(version.fields['target_kind']), str(version.fields['target_id']))
        for group in groups(version.refs):
            result = link(tx, group[0][0], group[0][1], node, details=group[1:], by=by,
                          why='layout 22: a ref of the sources item at this place became a record', held=known)
            if not isinstance(result, SourceRef):
                report['unlinked'] += 1
                continue
            report['names'][result.ref] = f'{result.key}={result.value}'
        tx.emit('remove', 'item', ident, found.id, {
            'mode': 'version', 'reason': 'layout 22: its refs are records of the sources layer now', 'evidence': None,
            **version.fields, 'refs': [list(pair) for pair in version.refs]})
    report['refs'] = len(report['names'])
    report['versions'] = tx.base.seq - before
    return report
