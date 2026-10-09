"""map: the data access object's map and layer operations as verbs, BASE-038.

Every verb calls `ctx.require_store()` and exactly one operation of STORE-024
or STORE-025, and returns its result, BASE-036. The fields of a record being
written are nouns: required ones positional, optional ones `name=value`. The
only switch is `--raw`, which reads every stored layer instead of the layers
in context. `knowledge` is the one read-write verb for layers, LAYER-018.
"""
from __future__ import annotations

import dataclasses
import json
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any, TypeVar, cast

from metaform import prompt_files, settings
from metaform.data import (
    PLACE_KINDS,
    Item,
    Node,
    Notice,
    Outcome,
    Page,
    Store,
    WorkRecord,
    plain,
)
from metaform.finish_xml import xml as map_xml
from metaform.module import Context, Module, Noun, NounKind, Status, Stop, Verb, node_reads, work_reads
from metaform.outline import markdown as map_markdown

from .storage import DATA, TABLES

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False
DATA_SOURCE = 'storage.py'

settings.boolean('raw', False, help='Read every stored layer, building, hidden and masked ones included.')
settings.boolean('critic', False, help='map critic: the critic also reads the code and writes tickets; '
                 'fast mode, blind to the code, when off.')
settings.boolean('tasks', True, help='Assign and track work on the map like a kanban. Turn it off when the project '
                 'keeps its own board.')

REFS_SCHEMA = {'type': 'array', 'items': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 2, 'maxItems': 2}}
# What edit and refine change; ifd and verb among them, which were dropped before, an intake found.
FIELDS = ('address', 'extra', 'receiver', 'elements', 'type', 'purpose', 'ef', 'ifd',
          'name', 'name_length', 'role', 'value', 'link', 'element', 'refs', 'read_first', 'always_show')


def _node(text: str) -> Node:
    return Node.parse(text)


def _element(value: Any) -> Any:
    """An element noun: an address or id, or a node written `kind:<address or id>`, which is read as that node."""
    if isinstance(value, str) and value.partition(':')[0] in PLACE_KINDS and ':' in value:
        return Node.parse(value)
    return value


def _store(ctx: Context) -> Store:
    return ctx.require_store()


def _paging(ctx: Context) -> dict[str, Any]:
    return {key: ctx.nouns[key] for key in ('limit', 'after') if key in ctx.nouns}


def _reading(ctx: Context) -> dict[str, Any]:
    return {'raw': bool(ctx.setting('raw'))}


def _said(result: dict[str, Any], done: Any) -> dict[str, Any]:
    """A verb's own result with the notices of the store operation it ran, BASE-044."""
    notices = list(getattr(done, 'notices', ()))
    if notices:
        result['notices'] = notices
    return result


def _other_project(ctx: Context) -> Store:
    project = ctx.nouns.get('project')
    return Store(project) if project else _store(ctx)


PAGING = (Noun('limit', 'How many results, 0 for all.', kind='int', required=False),
          Noun('after', 'The cursor the previous page returned.', required=False))


def roots(ctx: Context) -> Any:
    """The map's entry: the CQU and the DE with their joins, and every root element, STORE-025."""
    return _store(ctx).roots(**_reading(ctx), **_paging(ctx))


def _with_modules(ctx: Context, found: Any, node: Node) -> Any:
    """A node's read with what the modules on the surface add to it, each under its own id, BASE-035; a field the
    read holds already is never replaced."""
    added = node_reads(ctx.folder, node, project=ctx.project, layers=ctx.switches.get('layers'))
    if found is None or not added:
        return found
    data = cast(dict[str, Any], found.to_dict())
    for module, value in added.items():
        data.setdefault(module, value)
    return data


def _with_work_modules(ctx: Context, found: Any) -> Any:
    """A ticket's read with modules' memories at its nodes and their fields on the work record, MAP-048 and
    BASE-035; a field the read holds already is never replaced."""
    added = work_reads(ctx.folder, found.work, project=ctx.project)
    data = cast(dict[str, Any], found.to_dict())
    data['at'] = _with_modules(ctx, found.at, Node.of(found.work.node_kind, found.work.node_id))
    data['linked'] = [_with_modules(ctx, read, Node.of(link.kind, link.id))
                      for link, read in zip(found.work.links, found.linked)]
    for module, value in added.items():
        data.setdefault(module, value)
    return data


def where(ctx: Context) -> Any:
    """One read of an address: what relies on it and what it relies on, STORE-025; the entry with no address."""
    if not ctx.nouns['address']:
        return roots(ctx)
    found = _store(ctx).where(ctx.nouns['address'], full=bool(ctx.nouns.get('full', False)), **_reading(ctx))
    return _with_modules(ctx, found, Node('element', ctx.nouns['address']))


def markdown(ctx: Context) -> Any:
    """The map, or the part around one address, as a short Markdown document to find one's way by, MAP-052."""
    text = map_markdown(_store(ctx), ctx.nouns.get('address') or None, **_reading(ctx))
    target = ctx.nouns.get('file')
    if not target:
        return text
    path = Path(target) if Path(target).is_absolute() else ctx.folder / target
    path.write_text(text, encoding='utf-8')
    return {'written': str(path)}


def xml(ctx: Context) -> Any:
    """The map, or one element and all it receives, as an XML document in the Finish shape of Intake 2.1, MAP-059."""
    text = map_xml(_store(ctx), ctx.nouns.get('address') or None, **_reading(ctx))
    target = ctx.nouns.get('file')
    if not target:
        return text
    path = Path(target) if Path(target).is_absolute() else ctx.folder / target
    path.write_text(text, encoding='utf-8')
    return {'written': str(path)}


def element(ctx: Context) -> Any:
    found = _store(ctx).element(ctx.nouns['element'], **_reading(ctx))
    if found is None:
        raise Stop(f'No element {ctx.nouns["element"]} in context here.', f'metaform map where {ctx.nouns["element"]}')
    return found


def joins(ctx: Context) -> Any:
    return _store(ctx).joins(ctx.nouns['element'], ctx.nouns.get('as', 'receiver'), **_reading(ctx), **_paging(ctx))


def identity(ctx: Context) -> Any:
    return _store(ctx).identity(ctx.nouns['element'], **_reading(ctx), **_paging(ctx))




def children(ctx: Context) -> Any:
    return _store(ctx).children(ctx.nouns['address'], **_paging(ctx))


def layers(ctx: Context) -> Any:
    return _store(ctx).layers(ctx.nouns.get('tag'), ctx.nouns.get('kind'), ctx.nouns.get('module'), **_paging(ctx))


def tag(ctx: Context) -> Any:
    store = _store(ctx)
    done = store.tag(ctx.nouns['layer'], ctx.nouns['tag'])
    tagged = ctx.nouns['tag'] in store.layer_ref(ctx.nouns['layer']).tags
    return _said({'layer': ctx.nouns['layer'], 'tag': ctx.nouns['tag'], 'tagged': tagged}, done)


def untag(ctx: Context) -> Any:
    done = _store(ctx).untag(ctx.nouns['layer'], ctx.nouns['tag'])
    return _said({'layer': ctx.nouns['layer'], 'tag': ctx.nouns['tag'], 'tagged': False}, done)


def layer(ctx: Context) -> Any:
    target = _node(ctx.nouns['node']) if 'node' in ctx.nouns else None
    return _store(ctx).layer_items(ctx.nouns['layer'], target, **_paging(ctx))


def node(ctx: Context) -> Any:
    target = _node(ctx.nouns['node'])
    found = _store(ctx).node(target, **_reading(ctx))
    if found is None:
        raise Stop(f'No node {ctx.nouns["node"]} in context here.', 'metaform map node <node> --raw')
    return _with_modules(ctx, found, target)


def context(ctx: Context) -> Any:
    return _store(ctx).context(ctx.nouns['address'], **_paging(ctx))


def links(ctx: Context) -> Any:
    return _store(ctx).links_to(_node(ctx.nouns['node']), ctx.nouns.get('layer'), **_reading(ctx), **_paging(ctx))


def citing(ctx: Context) -> Any:
    return _store(ctx).citing(ctx.nouns['key'], ctx.nouns['value'], **_paging(ctx))


def history(ctx: Context) -> Any:
    return _store(ctx).history(ctx.nouns['id'], **_paging(ctx))


def bases(ctx: Context) -> Any:
    return _other_project(ctx).bases(**_paging(ctx))


def add_base(ctx: Context) -> Any:
    return _other_project(ctx).add_base(ctx.nouns['name'])


def collapse(ctx: Context) -> Any:
    return _other_project(ctx).collapse(ctx.nouns['name'])


def activate(ctx: Context) -> Any:
    return _other_project(ctx).activate_base(ctx.nouns['name'])


def remove_base(ctx: Context) -> Any:
    from metaform import home
    return home.remove_base(_other_project(ctx).project_id, ctx.nouns['name'])


def search(ctx: Context) -> Any:
    return _store(ctx).search(ctx.nouns['text'], ctx.nouns.get('layer'), **_paging(ctx))


def select(ctx: Context) -> Any:
    done = _store(ctx).select(ctx.nouns['address'], ctx.nouns['layer'])
    return _said(_store(ctx).effective_selection(ctx.nouns['address']).to_dict(), done)


def mask(ctx: Context) -> Any:
    done = _store(ctx).mask(ctx.nouns['address'], ctx.nouns['layer'])
    return _said(_store(ctx).effective_selection(ctx.nouns['address']).to_dict(), done)


def clear(ctx: Context) -> Any:
    done = _store(ctx).clear(ctx.nouns['address'], ctx.nouns['layer'], ctx.nouns['kind'])
    return _said(_store(ctx).effective_selection(ctx.nouns['address']).to_dict(), done)


def hide(ctx: Context) -> Any:
    done = _store(ctx).hide(ctx.nouns['layer'])
    return _said({'layer': ctx.nouns['layer'], 'hidden': not done.notices}, done)


def unhide(ctx: Context) -> Any:
    done = _store(ctx).unhide(ctx.nouns['layer'])
    return _said({'layer': ctx.nouns['layer'], 'hidden': False}, done)


def reexamined(ctx: Context) -> Any:
    done = _store(ctx).reexamined(ctx.nouns['layer'])
    return _said({'layer': ctx.nouns['layer'], 'reexamine': False}, done)


def answer(ctx: Context) -> Any:
    link = _node(ctx.nouns['link']) if 'link' in ctx.nouns else None
    return _store(ctx).answer(ctx.nouns['challenge'], ctx.nouns['answer'], link)


def approve(ctx: Context) -> Any:
    return _store(ctx).approve(ctx.nouns['challenge'])


BLIND_SPOTS = 'The functions and encounters the design should have and does not.'
T = TypeVar('T')


def critic(ctx: Context) -> str:
    """One critic run: a new blind-spot layer, blinded by its type, and the critic prompt with the whole base,
    LAYER-014 and LAYER-015. Fast mode, blind to the code, is the default; --critic also reads the code."""
    store = _store(ctx)
    sighted = bool(ctx.setting('critic'))
    mode = 'critic' if sighted else 'fast'
    taken = {layer.name for layer in _every(lambda after: store.layers(after=after))}
    base = f'blind_spot_{mode}_{datetime.now(UTC).strftime("%Y%m%dt%H%M%Sz")}'
    name, count = base, 1
    while name in taken:
        count += 1
        name = f'{base}_{count}'
    store.layer(name, 'map', BLIND_SPOTS, mutable=False, hideable=True,
                provenance={'module': 'map', 'prompt': 'blind_spot_challenge', 'role': 'critic', 'blinded': not sighted})
    metaform = map_markdown(store, None, **_reading(ctx)).strip()
    folder = resources.files(__name__)
    return (prompt_files.required(folder, 'blind_spot_challenge') + '\n\n'
            + prompt_files.required(folder, f'critic_{mode}', layer=name, metaform=metaform))


def challenges(ctx: Context) -> str:
    """The answer prompt with each challenge of one blind-spot layer and its state, LAYER-015."""
    store = _store(ctx)
    layer = ctx.nouns['layer']
    lines: list[str] = []
    for found in _every(lambda after: store.layer_items(layer, after=after)):
        if not isinstance(found, Item):
            continue
        where = str(found.target)
        if found.target.kind == 'element':
            element = store.element(found.target.id, raw=True)
            where = f'element:{element.address}' if element is not None else where
        value = found.value if isinstance(found.value, str) else json.dumps(found.value, ensure_ascii=False)
        lines.append(f'{found.id}  {found.state or "open"}  {where}  {value}')
    return prompt_files.required(resources.files(__name__), 'answer_challenges', layer=layer, challenges='\n'.join(lines))


def _every(read: Callable[[str | None], Page[T]]) -> list[T]:
    """Every result of a paged read, page after page."""
    held: list[T] = []
    after: str | None = None
    while True:
        page = read(after)
        held.extend(page.results)
        if not page.next:
            return held
        after = page.next


def _need(ctx: Context, *names: str, verb: str = 'knowledge') -> None:
    """Stop a call missing a field its record cannot be stored without at all, before anything is written, BASE-038."""
    missing = [name for name in names if name not in ctx.nouns]
    if missing:
        op = ctx.nouns.get('op')
        said = f'{verb} op={op}' if op is not None else verb
        raise Stop(f'{said} needs {", ".join(missing)}.', f'metaform help map {verb}')


def _empty(ctx: Context, notices: list[Notice], *names: str, empty: Any = None) -> list[Any]:
    """Fields a record is stored with even when they are missing: each missing one is stored empty and named in a
    notice, BASE-044."""
    for name in names:
        if name not in ctx.nouns:
            notices.append(Notice(name, f'{name} is missing; stored empty.'))
    return [ctx.nouns.get(name, empty) for name in names]


def _changes(ctx: Context) -> dict[str, Any]:
    changes = {name: ctx.nouns[name] for name in FIELDS if name in ctx.nouns}
    if 'link' in changes and isinstance(changes['link'], str):
        changes['link'] = _node(changes['link'])
    if 'element' in changes:
        changes['element'] = _element(changes['element'])
    return changes


def _optional(ctx: Context, *names: str) -> dict[str, Any]:
    return {name: ctx.nouns[name] for name in names if name in ctx.nouns}


# The nouns each knowledge operation reads, besides op and layer.
READS: dict[str, frozenset[str]] = {
    'create': frozenset({'variable', 'mutable', 'hideable', 'kind', 'fields', 'sources', 'tags', 'module', 'workflow',
                         'prompt', 'model', 'role', 'blinded'}),
    'add-element': frozenset({'address', 'name_length', 'name', 'role', 'refs'}),  # refs go to the sources layer
    'add-join': frozenset({'receiver', 'elements', 'purpose', 'ef', 'ifd', 'type'}),
    'add-property': frozenset({'element', 'value', 'refs', 'extra'}),
    'add-item': frozenset({'node', 'value', 'link', 'refs', 'extra', 'read_first', 'always_show', 'task', 'condition'}),
    'add-ref': frozenset({'owner', 'key', 'value'}),
    'add-plan': frozenset({'element', 'join'}),
    'edit': frozenset({'id', *FIELDS}),
    'remove': frozenset({'id'}),
    'finish': frozenset(),
    'discard': frozenset(),
}

# The fields each knowledge operation cannot store its record without, besides op, BASE-038: the field that says what
# the record is, where it attaches, or which layer holds it. A call missing one stops and writes nothing.
NEEDS: dict[str, tuple[str, ...]] = {
    'create': ('layer',), 'add-element': ('address',), 'add-join': ('receiver', 'elements'),
    'add-property': ('element',), 'add-item': ('node',), 'add-ref': ('owner',),
    'add-plan': ('layer', 'element'), 'edit': ('id',), 'remove': ('id',),
    'finish': ('layer',), 'discard': ('layer',),
}
# The operations that name their thing by id, so a missing layer is named in a notice and the call goes ahead.
BY_ID = ('edit', 'remove', 'add-ref')


def _unread(ctx: Context, op: str) -> list[Notice]:
    """What the call gave that its operation does not read, BASE-044: kept in the new record's extra when the
    operation adds one, else named as ignored. Nothing given goes unmentioned."""
    unread = sorted(name for name in ctx.nouns if name not in ('op', 'layer') and name not in READS.get(op, frozenset()))
    if not unread:
        return []
    if 'extra' in READS.get(op, frozenset()) and op.startswith('add-'):
        given = ctx.nouns.get('extra')
        kept = {name: ctx.nouns.pop(name) for name in unread}
        ctx.nouns['extra'] = ({**kept, **given} if isinstance(given, dict) else
                              kept if given is None else {'value': given, **kept})
        return [Notice(name, f'op={op} does not read {name}; it was kept in the record\'s extra.') for name in unread]
    for name in unread:
        ctx.nouns.pop(name)
    return [Notice(name, f'op={op} does not read {name}; it was ignored.') for name in unread]


def _with_notices(result: Any, notices: list[Notice]) -> Any:
    """The operation's result with the call's own notices first; a record that carries none, such as a ref, is
    returned as its fields with them."""
    if not notices:
        return result
    if isinstance(result, dict):
        fields = cast(dict[str, Any], result)
        return {**fields, 'notices': [*notices, *fields.get('notices', [])]}
    if isinstance(result, Page):  # a page of a list read is no dataclass
        return {**result.to_dict(), 'notices': notices}
    if 'notices' not in {field.name for field in dataclasses.fields(result)}:
        return {**result.to_dict(), 'notices': notices}
    return dataclasses.replace(result, notices=(*notices, *getattr(result, 'notices', ())))


STORE_ID = re.compile(r'\b[0-9a-f]{32}\b')
REFINE_FIELDS = ('name', 'name_length', 'role', 'purpose', 'ef', 'ifd', 'elements')
NAMING = ('receiver', 'provider', 'address')


def _said_as(store: Store, thing: str) -> str:
    """What an agent calls a thing the store names by id: an element by its address, a join by its receiver and the
    first element it holds."""
    found = store.element(thing, raw=True)
    if found is not None:
        return found.address
    versions = store.history(thing, limit=0).results
    fields = versions[-1].fields if versions else {}
    def at(ref: Any) -> str:
        element = store.element(str(ref), raw=True) if ref else None
        return element.address if element is not None else str(ref)
    if fields.get('receiver'):
        held = fields.get('elements') or [None]
        return f"the purpose of {at(fields['receiver'])} served by {held[0]}"
    return thing


def _in_words(store: Store, value: Any) -> Any:
    """A result with every store id said as the agent names the thing, MAP-005."""
    if isinstance(value, str):
        return STORE_ID.sub(lambda match: _said_as(store, match.group(0)), value)
    if isinstance(value, dict):
        return {key: _in_words(store, item) for key, item in cast(dict[Any, Any], value).items()}
    if isinstance(value, (list, tuple)):
        return [_in_words(store, item) for item in cast(list[Any] | tuple[Any, ...], value)]
    return value


def _purposes(store: Store, receiver: Any, provider: Any) -> list[Any]:
    owner = store.element(str(receiver), raw=True)
    if owner is None:
        return []
    return [held for held in store.joins(owner.id, limit=0).results
            if any(each.address == provider for each in held.elements)]


def _one(found: list[Any], what: str, notices: list[Notice], purposes: bool = False) -> Any:
    if len(found) == 1:
        return found[0]
    if not found:
        notices.append(Notice('purpose', f'There is no {what} in the base; nothing was changed.'))
    else:
        named = '; '.join(repr(item.purpose) for item in found) if purposes else str(len(found))
        notices.append(Notice('purpose', f'{len(found)} of {what} cannot be told apart by their addresses, '
                                             f'with the purposes {named}; nothing was changed.'))
    return None


def promote(ctx: Context) -> Any:
    """Associate a receiver's purpose with an ordinary element, preserving its join, MAP-054."""
    _need(ctx, 'receiver', 'provider', 'address', verb='promote')
    store = _store(ctx)
    nouns = ctx.nouns
    notices: list[Notice] = []
    said = f"the purpose of {nouns['receiver']} served by {nouns['provider']}"
    held = _one(_purposes(store, nouns['receiver'], nouns['provider']), said, notices, purposes=True)
    if held is None:
        return Outcome(tuple(notices))
    return store.promote_join(held.id, nouns['address'],
                              **_optional(ctx, 'name', 'name_length', 'role', 'reason'))


def refine(ctx: Context) -> Any:
    """Refine the base: one element or join changed or removed as its newest version in the base's own
    layer, every earlier version kept, LAYER-025. It names what it changes by address, never by id: an element by its
    address, a join by its receiver and an element it holds, MAP-005; `elements` gives the elements a join holds. It
    is a verb of its own, apart from knowledge, because it changes the base and no knowledge layer. Nothing is
    refused for its content, BASE-044."""
    nouns = ctx.nouns
    if not any(name in nouns for name in NAMING):
        raise Stop('refine needs address, or receiver and provider, to name what it changes.',
                   'metaform help map refine')
    store = _store(ctx)
    notices: list[Notice] = []
    (reason,) = _empty(ctx, notices, 'reason')
    changes: dict[str, Any] = {name: nouns[name] for name in REFINE_FIELDS if name in nouns}
    thing: str | None = None
    if 'receiver' in nouns or 'provider' in nouns:
        said = f"the purpose of {nouns.get('receiver')} served by {nouns.get('provider')}"
        held = _one(_purposes(store, nouns.get('receiver'), nouns.get('provider')), said, notices, purposes=True)
        if held is not None:
            thing = held.id
            if 'to_receiver' in nouns:
                changes['receiver'] = nouns['to_receiver']
    else:
        element = store.element(str(nouns['address']), raw=True)
        if element is None:
            notices.append(Notice('address', f"{nouns['address']} is not an element of the base; nothing was "
                                             'changed.'))
        else:
            thing = element.id
            if 'to_address' in nouns:
                changes['address'] = nouns['to_address']
    named = {name: nouns[name] for name in NAMING if name in nouns}
    if thing is None:
        return {**named, 'notices': [notice.to_dict() for notice in notices]}
    made = store.refine(thing, changes, remove=bool(nouns.get('remove')), reason=reason,
                        evidence=nouns.get('evidence'))
    told = [*notices, *getattr(made, 'notices', ())]
    told = [Notice('to_address' if notice.where == 'address' and 'to_address' in nouns else notice.where,
                   notice.message) for notice in told]
    fields = cast(dict[str, Any], getattr(made, 'fields', {}))
    kept = {key: value for key, value in fields.items() if key not in ('join_id', 'element_id', 'layer_id', 'row')}
    return _in_words(store, {**named, 'op': getattr(made, 'op', None), 'layer': getattr(made, 'layer', None),
                             'fields': kept, 'notices': [notice.to_dict() for notice in told]})


def knowledge(ctx: Context) -> Any:
    """Create, build, edit and finish a knowledge layer, one object per call, LAYER-018. Nothing is
    refused for its content; only a field in NEEDS stops a call, before anything is written, BASE-038 and BASE-044."""
    op = ctx.nouns.get('op')
    if op is None:
        raise Stop('knowledge needs op=, the operation to run.', 'metaform help map knowledge')
    if op not in READS:
        raise Stop(f'{op!r} is not a knowledge operation.', 'metaform help map knowledge')
    _need(ctx, *NEEDS.get(op, ()))
    if op == 'create' and ctx.nouns.get('kind', 'layer') != 'layer':
        raise Stop('knowledge creates a knowledge layer: kind=layer.',
                   'metaform help map knowledge')
    notices = _unread(ctx, op)
    return _with_notices(_knowledge(ctx, op, notices), notices)


def _flag(ctx: Context, name: str, notices: list[Notice]) -> bool:
    """A new layer's mutable or hideable: false when missing, and named in a notice, BASE-044."""
    if name not in ctx.nouns:
        notices.append(Notice(name, f'{name} is missing; stored as false.'))
    return bool(ctx.nouns.get(name, False))


def _knowledge(ctx: Context, op: str, notices: list[Notice]) -> Any:
    store = _store(ctx)
    nouns = ctx.nouns
    # A write of an object sent without a layer goes to a new unnamed layer, LAYER-001; the operations that name their
    # thing by id go ahead without one; every other operation stopped in knowledge() when it named none.
    name = str(nouns.get('layer') or '')
    if not name and op in BY_ID:
        notices.append(Notice('layer', f'No layer was named; op={op} names its thing by id, so it went ahead.'))
    if op == 'create':
        mutable, hideable = _flag(ctx, 'mutable', notices), _flag(ctx, 'hideable', notices)
        provenance = {'module': nouns.get('module', 'map'),
                      **{key: nouns[key] for key in ('workflow', 'prompt', 'model', 'role', 'blinded') if key in nouns}}
        # A missing variable is stored empty, and the store names it in its own notice, LAYER-002.
        return store.layer(name, provenance['module'], nouns.get('variable'), kind=nouns.get('kind', 'layer'),
                           mutable=mutable, hideable=hideable, fields=tuple(nouns.get('fields', ())),
                           tags=tuple(nouns.get('tags', ())), provenance=provenance,
                           sources=tuple(nouns.get('sources', ())))
    if op == 'add-element':
        made = store.add_element(name, nouns['address'], **_optional(ctx, 'name_length', 'role'),
                                 name=nouns.get('name'))
        if 'refs' in nouns and not isinstance(made, Outcome):
            _sources(store, made.id, made.address, nouns['refs'], notices)
        return made
    if op == 'add-join':
        purpose, ef = _empty(ctx, notices, 'purpose', 'ef')
        return store.add_join(name, nouns['receiver'], nouns['elements'], purpose=purpose, ef=ef,
                              **_optional(ctx, 'ifd', 'type'))
    if op == 'add-property':
        (value,) = _empty(ctx, notices, 'value')
        return store.add_property(name, _element(nouns['element']), value, **_optional(ctx, 'refs', 'extra'))
    if op == 'add-item' and ctx.nouns.get('task') and ctx.surface == 'mcp':
        raise Stop('Tickets are written by the person, or by the sentinel for them; an agent at work writes what it '
                   'found in its own ticket\'s note.', 'metaform map work op=edit id=<your work id> note="..."')
    if op == 'add-item':
        (value,) = _empty(ctx, notices, 'value')
        link = _node(nouns['link']) if 'link' in nouns else None
        return store.add_item(name, _node(nouns['node']), value, link=link,
                              **_optional(ctx, 'refs', 'extra', 'read_first', 'always_show', 'task', 'condition'))
    if op == 'add-ref':
        key, value = _empty(ctx, notices, 'key', 'value', empty='')
        if not isinstance(value, str):
            notices.append(Notice('value', 'value is not text; it was stored as its JSON text.'))
            value = json.dumps(value, ensure_ascii=False)
        return store.add_ref(nouns['owner'], str(key), value)
    if op == 'add-plan':
        return store.add_plan(name, _element(nouns['element']), nouns.get('join'))
    if op == 'edit':
        return store.edit(nouns['id'], _changes(ctx))
    if op == 'remove':
        thing = nouns['id']
        return store.remove(int(thing) if str(thing).isdigit() else thing)
    if op == 'finish':
        return store.finish(name)
    if op == 'discard':
        return store.discard(name)
    raise Stop(f'{op!r} is not a knowledge operation.', 'metaform help map knowledge')


SOURCES = 'sources'  # the layer an element's refs go in, Rich 2026-10-04


def _sources(store: Store, element_id: str, address: str, refs: Any, notices: list[Notice]) -> None:
    """The refs given with an element, as its one item of the sources layer, replacing what that item held: the
    metaform holds no refs, Rich 2026-10-04: "if you want to have refs you add a sources layer"."""
    store.layer(SOURCES, 'intake', 'refs', kind='layer', mutable=True, hideable=True, ready=True)
    held = [item for item in store.layer_items(SOURCES, Node('element', element_id), limit=0).results
            if isinstance(item, Item)]
    if held:
        notices.extend(getattr(store.edit(held[0].id, {'refs': refs}), 'notices', ()))
    else:
        notices.extend(getattr(store.add_item(SOURCES, Node('element', element_id), address, refs=refs), 'notices', ()))
    notices.append(Notice('refs', f'The refs were written to the {SOURCES} layer at {address}; the base holds none.'))


def _noun(name: str, help: str, kind: NounKind = 'str', schema: dict[str, Any] | None = None) -> Noun:
    return Noun(name, help, kind=kind, required=False, schema=schema)


KNOWLEDGE_NOUNS = (
    _noun('op', 'create, add-element, add-join, add-property, add-item, add-ref, add-plan, edit, remove, finish or '
                'discard.',
          schema={'type': 'string', 'enum': ['create', 'add-element', 'add-join', 'add-property', 'add-item', 'add-ref',
                                             'add-plan', 'edit', 'remove', 'finish', 'discard']}),
    _noun('layer', 'The layer this call works on, by name or id. Name a new layer <scope>@<content>: the address it is '
                   'about, @, then a short adjective_noun you choose for what the prompt creates; base is the default '
                   'scope. base@best_practices holds the best practices of the whole project; code.cpp@best_practices '
                   'those of cpp code. Read in reverse with @ as "for": best practices for cpp code. A workflow layer is '
                   'named the same way. An object added without a layer goes to a new layer named unnamed-<time>.'),
    _noun('variable', 'create: the one question the layer answers.'),
    _noun('mutable', 'create: whether its items change in place.', 'bool'),
    _noun('hideable', 'create: whether it can be hidden.', 'bool'),
    _noun('kind', 'create: layer.'),
    _noun('fields', 'create: the fields of the variable, a JSON list of names.', 'json',
          {'type': 'array', 'items': {'type': 'string'}}),
    _noun('sources', 'create: the layers it is built from, a JSON list of layer names or ids.', 'json',
          {'type': 'array', 'items': {'type': 'string'}}),
    _noun('tags', 'create: its tags, a JSON list.', 'json', {'type': 'array', 'items': {'type': 'string'}}),
    _noun('module', 'create: the module that makes the layer.'),
    _noun('workflow', 'create: the workflow within that module.'),
    _noun('prompt', 'create: the prompt the layer is made from.'),
    _noun('model', 'create: the model that makes it.'),
    _noun('role', 'create: the role of its producer; add-element: DE, SE, NE, CQU or AUE, the role of the element.'),
    _noun('blinded', 'create: whether the producer saw only the map.', 'bool'),
    _noun('address', 'add-element: the element\'s dotted namespace address. An element cannot be moved: edit does '
                     'not apply it.'),
    _noun('name', 'add-element: Canonical Name (Project official terminology) or Informal Name of the element.'),
    _noun('name_length', 'add-element: how many trailing segments form the element\'s short name.', 'int'),
    _noun('refs', 'add-property and add-item: a JSON list of [key, value] pairs, in order; add-element: the element\'s '
                  'refs, written to the sources layer.', 'json', REFS_SCHEMA),
    _noun('extra', 'add-property and add-item: a JSON object of further fields.', 'json', {'type': 'object'}),
    _noun('receiver', 'add-join: the element that holds the purpose; edit: another receiver, which moves the join.'),
    _noun('elements', 'add-join and edit: the elements that serve the purpose, a JSON list of addresses.', 'json',
          {'type': 'array', 'items': {'type': 'string'}}),
    _noun('purpose', 'add-join: the Operative Purpose.'),
    _noun('ef', 'add-join: the Encounter Function.'),
    _noun('ifd', 'add-join: IFD, Information Flow Direction, the primary flow of information. sends: OP to EF. '
                 'receives: EF to OP. both: equal need.', schema={'type': 'string', 'enum': ['sends', 'receives', 'both']}),
    _noun('type', 'add-join: the join type, purpose by default.'),
    _noun('join', 'add-plan: the join id.'),
    _noun('element', 'add-property and add-plan: the element, by address or id, or as a node such as type:code.'),
    _noun('value', 'add-item, add-property, edit and add-ref: the value, as JSON: text, a number, true or false, a list '
                   'or an object.', 'json',
          {'type': ['string', 'number', 'boolean', 'array', 'object', 'null']}),
    _noun('node', 'add-item: element:<address or id> or join:<id>.'),
    _noun('link', 'add-item: a node the item links to.'),
    _noun('read_first', 'add-item and edit: the item is read before the task.', 'bool'),
    _noun('always_show', 'add-item and edit: the item is always shown.', 'bool'),
    _noun('task', 'add-item: the item is a task; it adds a ticket at its node, and the flag is not stored on the item.',
          'bool'),
    _noun('condition', "add-item with task: the part's state, unbuilt, under-construction, built or broken, only "
                       "when the part is in that state; left out for a task on a part that exists and works."),
    _noun('owner', 'add-ref: the id of the thing the ref belongs to.'),
    _noun('key', 'add-ref: the ref key.'),
    _noun('id', 'edit and remove: the id of the thing.'),
)
# What each field means when refine changes it, apart from the knowledge operations that write it first.
REFINE_WORDS = {
    'address': "An element's address cannot change: given for an element, it is not applied.",
    'name': "The project's own name for the element or the join's functionality.",
    'name_length': "How many trailing segments form the element's short name.",
    'role': 'DE, SE, NE, CQU or AUE.',
    'receiver': 'Another receiver, which moves the join.',
    'elements': 'The elements the join holds, a JSON list of addresses; they replace the ones it held.',
    'purpose': 'The Operative Purpose.',
    'ef': 'The Encounter Function.',
    'ifd': 'IFD, Information Flow Direction, the primary flow of information. sends: OP to EF. receives: EF to OP. '
           'both: equal need.',
    'type': 'The join type.',
    'element': 'The element, by address or id.',
    'value': 'The value, as JSON.',
    'link': 'A node the item links to.',
}


def _refined_noun(noun: Noun) -> Noun:
    return Noun(noun.name, REFINE_WORDS[noun.name], kind=noun.kind, required=False, schema=noun.schema)


REFINE_NOUNS = (
    _noun('receiver', 'A join: the element that holds it, by address.'),
    _noun('provider', 'A join: an element it holds, by address.'),
    _noun('address', 'An element, by address.'),
    _noun('reason', 'Why.'),
    _noun('evidence', 'What shows it.'),
    _noun('remove', 'Remove it from the base instead of changing it; its versions are kept.', 'bool'),
    _noun('to_receiver', 'A join: its new receiver, by address; it moves and stays the same join.'),
    _noun('to_address', 'An element cannot be moved: given for an element, it is not applied.'),
    *(_refined_noun(noun) for noun in KNOWLEDGE_NOUNS if noun.name in REFINE_FIELDS),
)

# The nouns each work operation reads, besides op.
WORK_READS: dict[str, frozenset[str]] = {
    'glyphs': frozenset(),
    'list': frozenset({'node', 'receiver', 'provider', 'address', 'condition', 'kind', 'open', 'limit', 'after',
                       'hold'}),
    'read': frozenset({'id'}),
    'add': frozenset({'node', 'receiver', 'provider', 'address', 'condition', 'kind', 'note', 'task', 'held', 'reviewed',
                      'links', 'agent', 'hold', 'eligible'}),
    'edit': frozenset({'id', 'node', 'receiver', 'provider', 'address', 'condition', 'kind', 'note', 'task', 'held',
                       'reviewed', 'glyph', 'links', 'agent', 'hold', 'eligible'}),
    'done': frozenset({'id', 'resolution'}),
    'take': frozenset({'id', 'steps', 'by'}),
    'move': frozenset({'id', 'column', 'position', 'by'}),
    'plan': frozenset({'id', 'steps'}),
    'step': frozenset({'id', 'said'}),
    'distribute': frozenset({'agents'}),
}
WORK_FIELDS = ('condition', 'kind', 'note', 'task', 'held', 'reviewed')  # the chassis work record's own, STORE-042
# The long fields a list row leaves out, each read with the ticket by id=, so the list stays small, MAP-049 and MAP-053.
UNLISTED = frozenset({'said', 'resolution', 'task'})

# The agent glyphs a ticket is assigned to, VIEW-040: the seventeen characters the page draws, in the order of GLYPHS in
# the web page's agents3d.js. Tickets with the same glyph signify one agent doing them one at a time.
AGENT_GLYPHS = ('jelly', 'gearling', 'kite', 'moth', 'drone', 'snail', 'crystal', 'wisp', 'comet', 'beetle', 'slime',
                'plane', 'puffer', 'owl', 'cubebot', 'mushroom', 'seahorse')
TICKET_AGENTS = ('claude', 'codex', 'gemini')  # the agents a ticket can prefer, as dispatch starts them
AGENT_TYPES = TICKET_AGENTS

# The map module's own tables, STORE-045: `glyphs` keeps the agent glyph each ticket is assigned to, keyed by the work
# id, beside the map as the work records are, so the chassis work table holds no glyph, BASE-046 and ticket 90430bba.
# The field each work operation cannot store its record without, BASE-038: the object it attaches to, or the record.
WORK_NEEDS: dict[str, tuple[str, ...]] = {'list': (), 'glyphs': (), 'read': ('id',), 'add': (), 'edit': ('id',), 'done': ('id',),
                                          'take': ('id',), 'plan': ('id', 'steps'), 'step': ('id',),
                                          'move': ('id', 'column'), 'distribute': ('agents',)}


def _work_node(value: Any) -> Node:
    """A node written `kind:<address or id>`, or a bare address or id, which names an element."""
    if isinstance(value, str) and ':' in value and value.partition(':')[0] in PLACE_KINDS:
        return Node.parse(value)
    return Node('element', str(value))


def _named(store: Store, given: dict[str, Any], notices: list[Notice]) -> Node | None:
    """The node a call names by address, MAP-005: a purpose by its receiver and provider, a part by its address
    inside it, an element by its address; or the node noun as written. A node noun given beside them is named in a
    notice as not read."""
    if 'receiver' in given or 'provider' in given or 'address' in given:
        if 'node' in given:
            notices.append(Notice('node', 'receiver, provider and address name the node; node was not read.'))
        if 'receiver' in given or 'provider' in given:
            return store.purpose(given.get('receiver'), given.get('provider'), given.get('address'))
        return Node('element', str(given['address']))
    return _work_node(given['node']) if 'node' in given else None


def _link(store: Store, value: Any) -> Node:
    """A node a ticket links: written as a node, or as an object of receiver, provider and address."""
    if isinstance(value, dict):
        found = _named(store, cast(dict[str, Any], value), [])
        if found is not None:
            return found
    return _work_node(value)


def _held(store: Store, nouns: dict[str, Any], notices: list[Notice]) -> Node:
    """The node ask and tell name, node first, Rich 2026-10-03: an element by its address, or with provider beside it
    the purpose it holds as receiver, and with address the part at that address inside it, MAP-005."""
    if 'provider' not in nouns:
        if 'address' in nouns:
            notices.append(Notice('address', 'address names an element a join holds only with provider; it was not read.'))
        return _work_node(nouns['node'])
    node = str(nouns['node'])
    receiver = node.partition(':')[2] if node.startswith('element:') else node
    return store.purpose(receiver, nouns['provider'], nouns.get('address'))


def ask(ctx: Context) -> Any:
    """The person asks a question at a node, MAP-050, for the record and for the agent they talk to there. Agents do
    not ask: the verb is the person's, on the command line and the page."""
    store, notices = _store(ctx), list[Notice]()
    asked = store.ask(_held(store, ctx.nouns, notices), ctx.nouns['question'], suggestions=ctx.nouns.get('suggestions'),
                      by=ctx.nouns.get('by'), work=ctx.nouns.get('work'))
    return _with_notices(asked, notices)


def reply(ctx: Context) -> Any:
    """Answer a question, or mark a message read, MAP-050."""
    return _store(ctx).reply(ctx.nouns['id'], ctx.nouns.get('answer'))


def reopen(ctx: Context) -> Any:
    """Reopen a question answered by mistake, so it waits again with its suggestions, MAP-050."""
    return _store(ctx).reopen(ctx.nouns['id'])


def messages(ctx: Context) -> Any:
    """List questions and messages, or move one to another node, preserving its answer and state, MAP-050."""
    nouns = ctx.nouns
    op = str(nouns.get('op', 'list'))
    if op not in ('list', 'move'):
        raise Stop(f'{op!r} is not a messages operation: op=list or move.', 'metaform help map messages')
    store, notices = _store(ctx), list[Notice]()
    reads = ({'id', 'node', 'provider', 'address'} if op == 'move'
             else {'node', 'kind', 'open', 'limit', 'after'})
    for name in sorted(nouns):
        if name != 'op' and name not in reads:
            notices.append(Notice(name, f'op={op} does not read {name}; it was ignored.'))
    if op == 'move':
        _need(ctx, 'id', 'node', verb='messages')
        return _with_notices(store.move_message(nouns['id'], _held(store, nouns, notices)), notices)
    node = _work_node(nouns['node']) if 'node' in nouns else None
    return _with_notices(store.messages(node, nouns.get('kind'), nouns.get('open'), **_paging(ctx)), notices)


def work(ctx: Context) -> Any:
    """The work records: the condition of an element or a join, apart from the map, MAP-046 and STORE-042.
    op=list, the default, reads them, and an id with no op reads one; add, edit, take, plan, step, move and done
    write one each, and distribute gives the open tickets the glyphs of N agents, VIEW-040. A ticket is written by
    the person, or by the sentinel and the system agent for them on the command line, never by a worker over the
    agents' tool, MAP-050, Rich 2026-10-08: work is planned before a ticket exists."""
    # An id with no op reads that one ticket with what the map holds at its node and its links, MAP-048.
    op = str(ctx.nouns.get('op', 'read' if 'id' in ctx.nouns else 'list'))
    if op == 'add' and ctx.surface == 'mcp':
        raise Stop('Tickets are written by the person, or by the sentinel for them; an agent at work writes what it '
                   'found in its own ticket\'s note.', 'metaform map work op=edit id=<your work id> note="..."')
    if op not in WORK_READS or op == 'read' and 'op' in ctx.nouns:
        raise Stop(f'{op!r} is not a work operation: op=list, glyphs, add, edit, take, plan, step, move, distribute or done; '
                   'with id= and '
                   'no op, the one ticket is read.', 'metaform help map work')
    _need(ctx, *WORK_NEEDS[op], verb='work')
    unread = sorted(name for name in ctx.nouns if name != 'op' and name not in WORK_READS[op])
    notices = [Notice(name, f'op={op} does not read {name}; it was ignored.') for name in unread]
    if op == 'edit' and 'condition' in ctx.nouns and ctx.surface == 'mcp':  # the part's state is not a worker's to set
        ctx.nouns.pop('condition')
        notices.append(Notice('condition', 'The state of a part is set by the intake and the person, not by an agent '
                                           'at work; it was ignored. Say what you found in the note.'))
    if op == 'edit' and 'kind' in ctx.nouns and ctx.surface == 'mcp':  # what sort of ticket it is was decided with it
        ctx.nouns.pop('kind')
        notices.append(Notice('kind', 'A ticket\'s kind is set by whoever wrote it, not by an agent at work; it was '
                                      'ignored. Say what you found in the note.'))
    for name in unread:
        ctx.nouns.pop(name)
    store, nouns = _store(ctx), ctx.nouns
    if op == 'glyphs':
        return {'glyphs': list(AGENT_GLYPHS)}
    if op == 'list':
        node = _named(store, nouns, notices)
        # An element's list holds the tickets on the joins it receives or provides too, so an agent told its node
        # finds its ticket, ticket dd2a9caf.
        # Open records unless open=false asks for the done ones: the done records with their logs made the bare list
        # too large to read, MAP-049.
        found = store.work(node, nouns.get('condition'), nouns.get('open', True), **_paging(ctx), joins=True,
                           kind=nouns.get('kind'))
        if not nouns.get('hold'):  # a ticket the person holds is hidden from agents unless asked for with hold=true
            kept = _settings(store, [record.id for record in found.results])
            found = found._replace(results=tuple(record for record in found.results
                                                 if not kept.get(record.id, {}).get('hold')))
        listed = plain(_glyphed(store, found))
        listed['results'] = [{name: value for name, value in row.items() if name not in UNLISTED}
                             for row in listed['results']]
        return _with_notices(listed, notices)
    if op == 'add':
        node = _named(store, nouns, notices)
        if node is None:
            raise Stop('work op=add needs node, or receiver and provider.', 'metaform help map work')
        # A missing condition is stored empty, and the store names it in its notice, STORE-042.
        with store.atomic():
            added = store.add_work(node, nouns.get('condition'),
                                   links=[_link(store, link) for link in nouns.get('links') or ()],
                                   **_optional(ctx, 'kind', 'note', 'task', 'held', 'reviewed'))
            _keep(store, added.id, nouns, notices)
        return _with_notices(_glyphed(store, added), notices)
    if op == 'distribute':
        return _with_notices(_glyphed(store, _distribute(store, nouns['agents'])), notices)
    work_id = nouns['id']
    if op == 'read':
        return _with_notices(_with_work_modules(ctx, store.ticket(work_id)), notices)
    if op == 'take':
        with store.atomic():
            _claim(ctx, store, work_id, nouns.get('by'))
            taken = store.take_work(work_id, nouns.get('steps'), nouns.get('by'))
        return _with_notices(_glyphed(store, taken), notices)
    if op == 'move':
        with store.atomic():
            previous = store.ticket(work_id).work.column
            moved = store.move_work(work_id, nouns['column'], nouns.get('position'), nouns.get('by'))
        if previous != 'todo' and moved.column == 'todo':
            ctx.publish('work.requeued', {'project': store.project_id, 'work_id': work_id,
                                         'previous': previous, 'revision': time.time_ns()})
        return _with_notices(_glyphed(store, moved), notices)
    if op == 'plan':
        return _with_notices(_glyphed(store, store.plan_work(work_id, nouns['steps'])), notices)
    if op == 'step':
        return _with_notices(_glyphed(store, store.step_work(work_id, nouns.get('said'))), notices)
    if op == 'edit':
        changes = {name: nouns[name] for name in WORK_FIELDS if name in nouns}
        node = _named(store, nouns, notices)
        if node is not None:
            changes['node'] = node
        if 'links' in nouns:
            changes['links'] = [_link(store, link) for link in nouns['links'] or ()]
        with store.atomic():
            edited = store.edit_work(work_id, changes)
            if 'glyph' in nouns:
                _assign(store, {work_id: _glyph(nouns['glyph'], notices)})
            _keep(store, work_id, nouns, notices)
        return _with_notices(_glyphed(store, edited), notices)
    return _with_notices(_glyphed(store, store.finish_work(work_id, nouns.get('resolution'))), notices)


def _glyph(value: Any, notices: list[Notice]) -> str | None:
    """A ticket's agent glyph, VIEW-040: one of the seventeen the page draws, or none; any other name is stored as given
    with a notice, BASE-044."""
    if not value:  # none, or an empty choice, takes the glyph away
        return None
    if value in AGENT_GLYPHS:
        return value
    notices.append(Notice('glyph', f'{value!r} is not one of the agent glyphs, {", ".join(AGENT_GLYPHS)}; it was stored '
                                   'as given.'))
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _assign(store: Store, glyphs: dict[str, str | None]) -> None:
    """Give each ticket its glyph in the map module's own table, STORE-045; None takes its glyph away."""
    with store.tables() as tx:
        for work_id, glyph in glyphs.items():
            if glyph is None:
                tx.delete('glyphs', {'work_id': work_id})
            elif tx.update('glyphs', {'work_id': work_id}, {'glyph': glyph}) is None:
                tx.insert('glyphs', {'work_id': work_id, 'glyph': glyph})


def _glyphs(store: Store, work_ids: list[str]) -> dict[str, str]:
    """The glyph each of these tickets is assigned to, read in one transaction; a ticket with none is left out."""
    with store.tables(write=False) as tx:
        found = {work_id: tx.get('glyphs', {'work_id': work_id}) for work_id in work_ids}
    return {work_id: row['glyph'] for work_id, row in found.items() if row is not None}


def _settings(store: Store, work_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Each ticket's preferred agent, hold and eligibility, read in one transaction; a ticket with no
    settings is left out."""
    with store.tables(write=False) as tx:
        found = {work_id: tx.get('ticket_settings', {'work_id': work_id}) for work_id in work_ids}
        eligible = {work_id: tx.get('eligible', {'work_id': work_id}) for work_id in work_ids}
    kept = {work_id: {'agent': row['agent'], 'hold': bool(row['hold'])} for work_id, row in found.items()
            if row is not None}
    for work_id, row in eligible.items():
        if row is not None:
            kept.setdefault(work_id, {})['eligible'] = row['agents']
    return kept


def _claim(ctx: Context, store: Store, work_id: str, by: Any) -> None:
    """A restricted claim uses the transport's client name, or the CLI owner's first word, never the environment."""
    kept = _settings(store, [work_id]).get(work_id, {})
    if 'eligible' not in kept:
        return
    eligible = kept['eligible']
    if eligible == []:
        return
    agent = None
    if ctx.client is not None:
        agent = next((name for name in AGENT_TYPES if ctx.client.lower().startswith(name)), None)
    elif ctx.surface != 'mcp' and isinstance(by, str):
        words = by.split()
        agent = words[0] if words and words[0] in AGENT_TYPES else None
    if isinstance(eligible, list) and agent is not None and agent in eligible:
        return
    names = ', '.join(str(name) for name in cast(list[Any], eligible)) if isinstance(eligible, list) else str(eligible)
    raise Stop(f'Work {work_id} is restricted to eligible agents: {names}; '
               f'{agent or "an unidentified agent"} cannot claim it.', f'metaform map work id={work_id}')


def _keep(store: Store, work_id: str, nouns: dict[str, Any], notices: list[Notice]) -> None:
    """Write a ticket's settings, when given, in the map module's own tables, STORE-045."""
    changes: dict[str, Any] = {}
    if 'agent' in nouns:
        agent = nouns['agent'] or None
        if agent is not None and agent not in TICKET_AGENTS:
            notices.append(Notice('agent', f'{agent!r} is not one of the agents, {", ".join(TICKET_AGENTS)}; it was '
                                           'stored as given.'))
        changes['agent'] = agent
    if 'hold' in nouns:
        changes['hold'] = 1 if nouns['hold'] else 0
    if not changes and 'eligible' not in nouns:
        return
    with store.tables() as tx:
        if changes and tx.update('ticket_settings', {'work_id': work_id}, changes) is None:
            tx.insert('ticket_settings', {'work_id': work_id, **changes})
        if 'eligible' in nouns:
            agents = nouns['eligible']
            if agents == []:
                tx.delete('eligible', {'work_id': work_id})
            else:
                if not isinstance(agents, list) or any(name not in AGENT_TYPES for name in cast(list[Any], agents)):
                    notices.append(Notice('eligible', f'{agents!r} is not a list of agent types, '
                                          f'{", ".join(AGENT_TYPES)}; it was stored as given.'))
                values: dict[str, Any] = {'agents': agents}
                if tx.update('eligible', {'work_id': work_id}, values) is None:
                    tx.insert('eligible', {'work_id': work_id, **values})


def _glyphed(store: Store, result: Any) -> Any:
    """A work operation's record, or page of records, with what the map module keeps on each under `map`: its glyph,
    its preferred agent and whether the person holds it, as work_read shows it in `map work id=<id>`, BASE-035; a record
    with none of these is returned as it is."""
    page = cast(Page[WorkRecord], result) if isinstance(result, Page) else None
    records = list(page.results) if page is not None else [cast(WorkRecord, result)]
    ids = [record.id for record in records]
    glyphs, settings = _glyphs(store, ids), _settings(store, ids)
    if not glyphs and not settings:
        return page if page is not None else records[0]

    def one(record: WorkRecord) -> Any:
        kept = {**({'glyph': glyphs[record.id]} if record.id in glyphs else {}),
                **settings.get(record.id, {})}
        if not kept:
            return record
        data = record.to_dict()
        data.setdefault('map', kept)
        return data
    if page is not None:
        return {**page.to_dict(), 'results': [one(record) for record in records]}
    return one(records[0])


def _distribute(store: Store, agents: Any) -> Page[WorkRecord]:
    """Distribute the work over N agents, VIEW-040: the first N glyphs, given in turn to the tickets not done and not
    taken, To do first and then Backlog, each in its board order. A ticket taken or done keeps its glyph, so an agent
    at work never changes character; an exclude record is no ticket."""
    if isinstance(agents, bool) or not isinstance(agents, int) or not 1 <= agents <= len(AGENT_GLYPHS):
        raise Stop(f'Work is distributed over 1 to {len(AGENT_GLYPHS)} agents, one glyph each; {agents!r} is not one of '
                   'those.', 'metaform map work op=distribute agents=<n>')
    with store.atomic():
        waiting = [record for record in store.work(open=True, limit=0).results
                   if not record.taken and (record.task or '').strip()]
        # the board's order: To do before Backlog, each by its place, a ticket with none after, then as written
        waiting.sort(key=lambda record: (record.held, record.position is None, record.position or 0))
        _assign(store, {record.id: AGENT_GLYPHS[place % agents] for place, record in enumerate(waiting)})
    return Page(tuple(waiting), None)


def work_read(ctx: Context, record: WorkRecord) -> dict[str, Any] | None:
    """The agent glyph the map module keeps on a work record, VIEW-040; nothing when it keeps none. The chassis puts
    it under `map` in `map work id=<id>`, BASE-035."""
    if ctx.store is None:
        return None
    glyph = _glyphs(ctx.store, [record.id]).get(record.id)
    kept = {**({'glyph': glyph} if glyph else {}), **_settings(ctx.store, [record.id]).get(record.id, {})}
    return kept or None


WORK_NOUNS = (
    _noun('op', 'list, the default; add; edit; take, which says an agent has started on the task; plan, which says '
                'how many steps the agent plans; step, which says it finished one; move, which puts it in a column '
                'of the board; distribute, which gives the open tickets the glyphs of N agents; glyphs, which reads '
                'the available agent glyph names; or done.',
          schema={'type': 'string', 'enum': ['list', 'add', 'edit', 'take', 'plan', 'step', 'move', 'distribute',
                                             'glyphs', 'done']}),
    _noun('steps', 'take and plan: how many steps you plan for the task. Say it again when your plan changes.', 'int'),
    _noun('said', 'step: what you did in the step you finished, in a sentence.'),
    _noun('node', 'list, add and edit: an element, by address; edit moves the ticket there, keeping its progress. '
                  'list gives its own records and those on the joins it receives or provides.'),
    _noun('receiver', 'list, add and edit: a join, by the address of the element that holds it, with provider.'),
    _noun('provider', 'list, add and edit: a join, by the address of an element it holds, with receiver.'),
    _noun('address', 'list, add and edit: an element, by address.'),
    _noun('condition', 'add, edit, and list as a filter: the state of the part the record is at, never the kind of '
                       'ticket. A stage, unbuilt, under-construction or built, says where the part is on its way to '
                       'existing; built is the normal state and marks nothing. broken is a built part that does not '
                       'do its job. A task on a part that exists and works carries none. The intake and the person '
                       'set it; an agent at work leaves it alone. condition=none on edit clears it.',
          schema={'type': 'string', 'enum': ['unbuilt', 'under-construction', 'built', 'broken', 'none']}),
    _noun('kind', 'add, edit, and list as a filter: what sort of work the ticket is, never the state of the part: '
                  'broken, a fix for a part that does not do its job; flawed, a part that works but is not right; '
                  'enhancement, a part that works and could be better; or none for a plain task. kind=none on edit '
                  'clears it.',
          schema={'type': 'string', 'enum': ['broken', 'flawed', 'enhancement', 'none']}),
    _noun('links', 'add and edit: other nodes the task links for reference, a list of element addresses, and of '
                   'objects of receiver and provider, with address for a part inside, each naming a purpose.',
          'json', {'type': 'array', 'items': {'anyOf': [
              {'type': 'string'},
              {'type': 'object', 'properties': {'receiver': {'type': 'string'}, 'provider': {'type': 'string'},
                                                'address': {'type': 'string'}}}]}}),
    _noun('by', 'take and move: who takes it; on the CLI, take identifies the claiming agent by its first word, '
                'claude, codex or gemini. Over MCP the client name identifies the agent.'),
    _noun('column', 'move: backlog, todo, doing or done. todo puts a taken task back on the queue, keeping its log.',
          schema={'type': 'string', 'enum': ['backlog', 'todo', 'doing', 'done']}),
    _noun('position', 'move: its place in the column, from 0; the end when left out.', 'int'),
    _noun('note', 'add and edit: what and where.'),
    _noun('task', 'add and edit: what it needs.'),
    _noun('held', 'add and edit: keep it waiting until agents are assigned or take it.', 'bool'),
    _noun('reviewed', 'add and edit: it has been checked for correctness before being fired off.', 'bool'),
    _noun('agent', 'add and edit: the agent this ticket prefers, claude, codex or gemini; the person can change it at any '
                   'time, even while an agent works on it.', schema={'type': 'string', 'enum': ['claude', 'codex', 'gemini']}),
    _noun('hold', 'add and edit: true holds the ticket, hidden from agents and automatic starts until '
                  'the person lets it go; list: true lists held tickets too.', 'bool'),
    _noun('glyph', 'edit: the agent glyph the ticket is assigned to; tickets with the same glyph are one agent\'s, '
                   'done one at a time.'),
    _noun('eligible', 'add and edit: the eligible agent types as a JSON list, claude, codex or gemini; [] allows '
                     'Any agent, the default for existing and new tickets. Dispatch and agent claims honor it.', 'json',
          {'type': 'array', 'items': {'type': 'string', 'enum': ['claude', 'codex', 'gemini']}}),
    _noun('agents', 'distribute: how many agents, from 1 to 17; the tickets not done and not taken are given the first '
                    'that many glyphs in turn, To do first and then Backlog.', 'int'),
    _noun('id', 'The work record id, for edit, take, plan, step, move and done. Given with no op, it reads that one '
                'ticket with the where read of its node and of each node it links: their refs, open work and open '
                'questions, knowledge layers and modules\' memories. Review the knowledge layers first; other '
                'agents\' memories are attached there, and record your own memories at the nodes you work on. '
                'past_work lists completed tickets with their age; read one with id= to see its log.'),
    _noun('resolution', 'done: how it was resolved, kept beside the record.'),
    _noun('open', 'list: true, the default, for records not done; false for those done. A listed record leaves out '
                  'its task, said and resolution; read them with id=.', 'bool'),
    *PAGING,
)

RAW = ('raw',)
# ask and tell take node first; these beside it name the purpose it holds, Rich 2026-10-03, MAP-005.
HELD = (_noun('provider', 'A purpose node holds as its receiver: the address of the element that serves it.'),
        _noun('address', 'With provider: the part at that address inside the purpose.'))


MODULE = Module(
    id='map',
    # The kanban lines speak to nodes, which exist once an intake is finished, MAP-048 and MCP-029.
    # The tasks instruction is read on demand with map's full instructions, not handed to every agent at connect,
    # Rich 2026-10-07.
    status=lambda ctx: Status(instruction=prompt_files.module('map', 'tasks') if ctx.setting('tasks') and ctx.store
                              is not None and ctx.store.has_intake() else None, at_connect=False),
    tables=TABLES,
    data=DATA,
    work_read=work_read,
    summary="Read and write this project's functional map and its layers.",
    purpose="Reads and writes this project's functional map. Handed an address, start with where: one read of "
            'the address returns the element, what relies on it, every join it provides with the receiver and its '
            'purpose, what it relies on, every join it receives with the elements it holds and its function, its '
            'open work records and what the layers in context hold at it, the sources layer\'s refs among them; '
            'full=true keeps ids. With '
            "no address, start with roots: the map's entry, the CQU and the DE with their joins, and the root "
            'elements. The receiver holds the purpose, the provider delivers the function. '
            'Record what you learn at a node with the memory tools; to build or improve a knowledge layer, use '
            'knowledge, naming the layer on every call: create it, add, edit and remove its objects one at a '
            'time, and finish it when the task is done. Details: metaform help map.',
    details='Every read that returns a join shows the layer it comes from. --raw reads every stored layer.',
    verbs=(
        Verb('roots', roots, "The map's entry: the CQU and the DE with their joins, and every root element.",
             nouns=PAGING, switches=RAW),
        Verb('where', where, 'One read of an address: the element, what relies on it, what it relies on, its open '
                             "work records and the layers in context at it; with an empty address, the map's entry.",
             nouns=(Noun('address', 'A dotted namespace address, or empty for the entry.'),
                    _noun('full', 'true keeps ids and empty fields, which are left out by default.', 'bool')),
             switches=RAW),
        Verb('markdown', markdown, 'The map, or the part around one address, as a short Markdown document.',
             nouns=(_noun('address', 'A dotted namespace address; without one, the whole map.'),
                    _noun('file', 'A file to write the document to; without one, it is printed.')),
             switches=RAW, surfaces=('cli',)),
        Verb('xml', xml, 'The map, or one element and all it receives, as an XML document with every field.',
             nouns=(_noun('address', 'A dotted namespace address; without one, the whole map.'),
                    _noun('file', 'A file to write the document to; without one, it is printed.')),
             switches=RAW, surfaces=('cli',)),
        Verb('element', element, 'One element: its address, name_length, name, role and short name.',
             nouns=(Noun('element', 'An address or element id.'),), switches=RAW),
        Verb('joins', joins, 'The joins an element receives, or with as=provider those that hold it.',
             nouns=(Noun('element', 'An address or element id.'), _noun('as', 'receiver or provider.'), *PAGING),
             switches=RAW),
        Verb('identity', identity, 'Every join an element provides for: who receives it, why and how.',
             nouns=(Noun('element', 'An address or element id.'), *PAGING), switches=RAW),
        Verb('children', children, 'The next types toward the leaves.',
             nouns=(Noun('address', 'A dotted namespace address.'), *PAGING)),
        Verb('layers', layers, 'The layers, with their kind, tags, state and whether each is on here.',
             nouns=(_noun('tag', 'Only layers with this tag.'), _noun('kind', 'Only layers of this kind.'),
                    _noun('module', 'Only layers of this module.'), *PAGING)),
        Verb('tag', tag, 'Add a tag to a layer.', nouns=(Noun('layer', 'A layer.'), Noun('tag', 'The tag.'))),
        Verb('untag', untag, 'Remove a tag from a layer.', nouns=(Noun('layer', 'A layer.'), Noun('tag', 'The tag.'))),
        Verb('layer', layer, 'Everything one layer holds, or what it holds at one node.',
             nouns=(Noun('layer', 'A layer.'), _noun('node', 'A node, such as element:code.engine.'), *PAGING)),
        Verb('node', node, "Every layer's items at one node, grouped by layer.",
             nouns=(Noun('node', 'element:<address or id> or join:<id>.'),),
             switches=RAW),
        Verb('context', context, 'The properties that apply at an address, and those attached toward the leaves from '
                                 'it that are visible there.',
             nouns=(Noun('address', 'A dotted namespace address.'), *PAGING)),
        Verb('links', links, 'Items that link to a node.',
             nouns=(Noun('node', 'A node.'), _noun('layer', 'Only this layer.'), *PAGING), switches=RAW),
        Verb('citing', citing, 'Everything whose refs hold a key and value.',
             nouns=(Noun('key', 'The ref key, such as path.'), Noun('value', 'The ref value.'), *PAGING)),
        Verb('history', history, 'Every version of a thing, in the order it was written.',
             nouns=(Noun('id', 'An id.'), *PAGING)),
        Verb('bases', bases, "The project's bases.", nouns=(_noun('project', 'A project id.'), *PAGING)),
        Verb('add-base', add_base, 'Start a new, empty base and make it active.',
             nouns=(Noun('name', 'The base name.'), _noun('project', 'A project id.'))),
        Verb('activate', activate, 'Make a base the active one.',
             nouns=(Noun('name', 'The base name.'), _noun('project', 'A project id.'))),
        Verb('remove-base', remove_base, 'Take one base out of the project; a copy of its store is kept.',
             nouns=(Noun('name', 'The base name.'), _noun('project', 'A project id.')),
             caution='Removes the base and its store; a copy is kept under backups/remove-base. The active base '
                     'is refused.'),
        Verb('collapse', collapse, 'Write the current map as a new base of one base layer, each element and '
                                   'join once with the same ids, and make it active; the old one is kept whole.',
             nouns=(Noun('name', 'The new base name.'), _noun('project', 'A project id.'))),
        Verb('promote', promote, 'Give a join an ordinary element by address, keeping the original join and its '
                                 'history, memories and work.',
             nouns=(_noun('receiver', 'The address of the element that holds the join.'),
                    _noun('provider', 'The address of an element the join holds.'),
                    _noun('address', 'The address of the element to create or reuse for the join.'),
                    _noun('name', 'The canonical name of the new element; an existing element keeps its name.'),
                    _noun('name_length', 'How many trailing address segments form its short name.', 'int'),
                    _noun('role', 'The intake classification of the new element: DE, SE, NE, CQU or AUE.'),
                    _noun('reason', 'Why the join needs an element.')),
             details='The join records its element by address and keeps its receiver and held elements. The '
                     'associated element receives and provides ordinary joins. An intake join gains a version '
                     'in its own layer; a knowledge join follows its existing edit rules. Repeating the same '
                     'association adds no version. An existing element keeps its authored fields; a different '
                     'address for an already promoted join returns a notice and writes nothing.'),
        Verb('search', search, 'Items whose value holds every word of the text.',
             nouns=(Noun('text', 'The words to find.'), _noun('layer', 'Only this layer.'), *PAGING)),
        Verb('work', work, 'The work records, the condition of an element or a join apart from the map: list them, '
                           'read one by its id, add or edit one, take one, plan its steps and report each, move it '
                           'on the board, or mark it done.',
             nouns=WORK_NOUNS,
             details='A work record is attached to one element or join and never changes the map. Its '
                     'condition is the state of that part, never the kind of ticket: most tasks carry none. A '
                     'stage, unbuilt, under-construction or built, says where the part is on its way to existing; '
                     'built marks nothing. broken is a built part that does not do its job. The intake and the '
                     'person set it; an agent at work leaves it alone. Its note says what and where, its task what '
                     'it needs. '
                     'exclude records material outside the intake scope or code conflicting with a superseding '
                     'specification. The note links the affected material and the specification or scope reason '
                     'for review. Unrelated folders are excluded from functional capture; a proposed gitignore '
                     'change is recorded for review. Documents, specifications, notes and working files are '
                     'preserved. Marking a record does not remove files or change gitignore. Unneeded legacy '
                     'migration code is marked for review. A store at an earlier layout is updated by Metaform '
                     'when it opens it. It is '
                     'open until op=done records its resolution, which is kept beside it. Any agent writes one at any '
                     'time, the intake agent as it maps, a critic with its findings, held=true until agents take it.',
             examples=(('metaform map work op=add node=element:code.alarm.audible condition=unbuilt task="build it"',
                        'Record that the alarm is not built yet, with the task that builds it.'),
                       ('metaform map work op=edit id=<work id> node=code.alarm.audible',
                        'Move a ticket to the alarm, keeping its progress and reference links.'),
                       ('metaform map work condition=broken open=true', 'List the parts recorded broken, with their open tasks.'),
                       ('metaform map work id=<work id>', ('Read one ticket with what the map holds at its node and '
                                                           'at each node it links.')),
)),
        Verb('ask', ask, 'Write a question at a node, for the record: the person asks, never an agent.',
             nouns=(Noun('node', 'Where the question applies: an element, by address; with provider, the purpose '
                                 'it holds as receiver.'),
                    Noun('question', 'The question.'),
                    *HELD,
                    _noun('suggestions', 'Possible answers, as a JSON list.', 'json',
                          {'type': 'array', 'items': {'type': 'string'}}),
                    _noun('by', 'Who asks.'),
                    _noun('work', 'The ticket it belongs to, by its work id.')),
             surfaces=('cli',)),
        Verb('reply', reply, 'Answer a question, or mark a message read.',
             nouns=(Noun('id', 'The id of the question or the message.'),
                    _noun('answer', 'The answer to a question.')),
             examples=(('metaform map reply <id> answer="No, make it louder"', 'Answer a question.'),)),
        Verb('reopen', reopen, 'Reopen a question answered by mistake, so it waits again with its suggestions.',
             nouns=(Noun('id', 'The id of the question.'),),
             examples=(('metaform map reopen <id>', 'Clear the answer; the question waits again.'),),
             surfaces=('cli',)),
        Verb('messages', messages, 'List the questions and messages left for the user, or move one to another node.',
             nouns=(_noun('op', 'list, the default, oldest first; move changes one record\'s node, keeping its answer '
                               'and closed state.', schema={'type': 'string', 'enum': ['list', 'move']}),
                    _noun('id', 'move: the id of the question or message.'),
                    _noun('node', 'list: only those at this node. move: the destination element, by address; with '
                                 'provider, the purpose it holds as receiver.'),
                    *HELD, _noun('kind', 'list: question or message.'),
                    _noun('open', 'list: true for those that still wait, false for those answered or read.', 'bool'),
                    *PAGING),
             examples=(('metaform map messages op=move id=<message id> node=code.alarm.audible',
                        'Move a question or message to the alarm, keeping its suggestions and answer.'),)),
        Verb('knowledge', knowledge, 'Create, build, edit and finish a knowledge layer.',
             nouns=KNOWLEDGE_NOUNS,
             details='Every call names its layer with layer=. op=create makes the layer; the add, edit and remove '
                     'operations change one object each; op=finish marks it ready. The base grows by the add '
                     'operations with layer=intake; it changes by refine.',
             examples=((('metaform map knowledge op=create layer=practices-cpp variable="C++ practice here." '
                         'mutable=true hideable=true'), 'Start a knowledge layer.'),)),
        Verb('refine', refine, 'Refine the base: change or remove one of its elements or joins as a new version, '
                               'keeping every earlier one.',
             nouns=REFINE_NOUNS,
             details='The change is written in the base\'s own layer, never in a new one, LAYER-025; history '
                     'shows every version.',
             examples=((('metaform map refine id=<join id> purpose="Know when each dish is done." '
                         'reason="the old purpose named the clock"'), 'Refine one join\'s purpose.'),)),
        Verb('select', select, 'Turn a layer on at an address and at every address toward the leaves from it.',
             nouns=(Noun('address', 'An address.'), Noun('layer', 'A layer.'))),
        Verb('mask', mask, 'Stop a layer flowing into an address and every address toward the leaves from it.',
             nouns=(Noun('address', 'An address.'), Noun('layer', 'A layer.'))),
        Verb('clear', clear, 'Remove a select or mask.',
             nouns=(Noun('address', 'An address.'), Noun('layer', 'A layer.'), Noun('kind', 'select or mask.'))),
        Verb('hide', hide, 'Hide a layer from every read in context.', nouns=(Noun('layer', 'A layer.'),),
             caution='This hides the layer, and every layer built from it, from every agent.'),
        Verb('unhide', unhide, 'Show a hidden layer again.', nouns=(Noun('layer', 'A layer.'),)),
        Verb('reexamined', reexamined, 'Clear the re-examination mark of a layer.',
             nouns=(Noun('layer', 'A layer.'),)),
        Verb('answer', answer, 'Answer a blind-spot challenge: A, B or C.',
             nouns=(Noun('challenge', 'The challenge item id.'), Noun('answer', 'A, B or C.'),
                    _noun('link', 'For C: the element or join that already handles it.'))),
        Verb('approve', approve, 'Approve a challenge answered B, making it a plan.',
             nouns=(Noun('challenge', 'The challenge item id.'),), surfaces=('cli',)),
        Verb('critic', critic, 'Start a blind-spot critic run: a new blind-spot layer, and the critic prompt with the '
                               'whole base.',
             switches=('critic',),
             details='Fast mode by default: the critic reads the base and the specifications, not the code. '
                     '--critic also lets it read the code and write tickets. Each run creates its own blind-spot '
                     'layer, with provenance role critic and blinded true unless --critic, LAYER-014.'),
        Verb('challenges', challenges, "The answer prompt with each challenge of a blind-spot layer and its state.",
             nouns=(Noun('layer', 'The blind-spot layer.'),)),
    ),
)
