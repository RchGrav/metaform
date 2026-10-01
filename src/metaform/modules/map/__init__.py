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
from pathlib import Path
from typing import Any, cast

from metaform import outline, settings
from metaform.data import PERSPECTIVES, PLACE_KINDS, Node, Notice, Store
from metaform.module import Context, Module, Noun, NounKind, Stop, Verb

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False

settings.boolean('raw', False, help='Read every stored layer, building, hidden and masked ones included.')

REFS_SCHEMA = {'type': 'array', 'items': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 2, 'maxItems': 2}}
EF = {'type': 'string', 'enum': list(PERSPECTIVES)}
FIELDS = ('address', 'extra', 'receiver', 'provider', 'parent', 'type', 'purpose', 'ef', 'relation',
          'observation', 'non_goal', 'name', 'name_length', 'role', 'value', 'link', 'element', 'refs')


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


def where(ctx: Context) -> Any:
    """One read of an address: what relies on it and what it relies on, STORE-025; the entry with no address."""
    if not ctx.nouns['address']:
        return roots(ctx)
    return _store(ctx).where(ctx.nouns['address'], full=bool(ctx.nouns.get('full', False)), **_reading(ctx))


def markdown(ctx: Context) -> Any:
    """The map, or the part around one address, as a short Markdown document to find one's way by, MAP-052."""
    text = outline.markdown(_store(ctx), ctx.nouns.get('address') or None, **_reading(ctx))
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


def subtypes(ctx: Context) -> Any:
    return _store(ctx).subtypes(ctx.nouns['join'], **_reading(ctx), **_paging(ctx))


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
    found = _store(ctx).node(_node(ctx.nouns['node']), **_reading(ctx))
    if found is None:
        raise Stop(f'No node {ctx.nouns["node"]} in context here.', 'metaform map node <node> --raw')
    return found


def context(ctx: Context) -> Any:
    return _store(ctx).context(ctx.nouns['address'], **_paging(ctx))


def links(ctx: Context) -> Any:
    return _store(ctx).links_to(_node(ctx.nouns['node']), ctx.nouns.get('layer'), **_reading(ctx), **_paging(ctx))


def citing(ctx: Context) -> Any:
    return _store(ctx).citing(ctx.nouns['key'], ctx.nouns['value'], **_paging(ctx))


def history(ctx: Context) -> Any:
    return _store(ctx).history(ctx.nouns['id'], **_paging(ctx))


def stack(ctx: Context) -> Any:
    return _store(ctx).stack(**_paging(ctx))


def metaforms(ctx: Context) -> Any:
    return _other_project(ctx).metaforms(**_paging(ctx))


def add_metaform(ctx: Context) -> Any:
    return _other_project(ctx).add_metaform(ctx.nouns['name'])


def activate(ctx: Context) -> Any:
    return _other_project(ctx).activate_metaform(ctx.nouns['name'])


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


def _need(ctx: Context, *names: str, verb: str = 'knowledge') -> None:
    """Stop a call missing a field its record cannot be stored without at all, before anything is written, BASE-038."""
    missing = [name for name in names if name not in ctx.nouns]
    if missing:
        op = ctx.nouns.get('op')
        raise Stop(f'{verb} op={op} needs {", ".join(missing)}.', f'metaform help map {verb}')


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
    'add-element': frozenset({'address', 'name_length', 'role', 'refs', 'extra'}),
    'add-join': frozenset({'receiver', 'provider', 'name', 'purpose', 'ef', 'perspective', 'relation', 'verb',
                           'observation', 'non_goal', 'type', 'refs', 'extra'}),
    'add-subtype': frozenset({'join', 'address', 'purpose', 'ef', 'perspective', 'relation', 'verb', 'observation', 'non_goal',
                              'name', 'name_length', 'role', 'refs', 'extra'}),
    'add-property': frozenset({'element', 'value', 'refs', 'extra'}),
    'add-item': frozenset({'node', 'value', 'link', 'refs', 'extra'}),
    'add-ref': frozenset({'owner', 'key', 'value'}),
    'add-plan': frozenset({'element', 'join'}),
    'edit': frozenset({'id', *FIELDS}),
    'remove': frozenset({'id'}),
    'correct': frozenset({'id', 'reason', 'evidence', 'remove', *FIELDS}),
    'finish': frozenset(),
    'peel': frozenset(),
    'discard': frozenset(),
}

# The fields each knowledge operation cannot store its record without, besides op, BASE-038: the field that says what
# the record is, where it attaches, or which layer holds it. A call missing one stops and writes nothing.
NEEDS: dict[str, tuple[str, ...]] = {
    'create': ('layer',), 'add-element': ('address',), 'add-join': ('receiver', 'provider'),
    'add-subtype': ('join', 'address'), 'add-property': ('element',), 'add-item': ('node',), 'add-ref': ('owner',),
    'add-plan': ('layer', 'element'), 'edit': ('id',), 'remove': ('id',), 'correct': ('layer', 'id'),
    'finish': ('layer',), 'peel': ('layer',), 'discard': ('layer',),
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
    if 'notices' not in {field.name for field in dataclasses.fields(result)}:
        return {**result.to_dict(), 'notices': notices}
    return dataclasses.replace(result, notices=(*notices, *getattr(result, 'notices', ())))


def knowledge(ctx: Context) -> Any:
    """Create, build, edit and finish a knowledge or correction layer, one object per call, LAYER-018. Nothing is
    refused for its content; only a field in NEEDS stops a call, before anything is written, BASE-038 and BASE-044."""
    op = ctx.nouns.get('op')
    if op is None:
        raise Stop('knowledge needs op=, the operation to run.', 'metaform help map knowledge')
    if op not in READS:
        raise Stop(f'{op!r} is not a knowledge operation.', 'metaform help map knowledge')
    _need(ctx, *NEEDS.get(op, ()))
    if op == 'create' and ctx.nouns.get('kind', 'layer') not in ('layer', 'correction'):
        raise Stop('knowledge creates a knowledge layer or a correction layer: kind=layer or kind=correction.',
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
        return store.add_element(name, nouns['address'], **_optional(ctx, 'name_length', 'role', 'refs', 'extra'))
    if op == 'add-join':
        purpose, ef, relation, observation = _empty(ctx, notices, 'purpose', 'ef', 'relation',
                                                          'observation')
        return store.add_join(name, nouns['receiver'], nouns['provider'], purpose=purpose, ef=ef,
                              relation=relation, observation=observation,
                              **_optional(ctx, 'name', 'perspective', 'verb', 'non_goal', 'type', 'refs', 'extra'))
    if op == 'add-subtype':
        return store.add_subtype(name, nouns['join'], nouns['address'],
                                 **_optional(ctx, 'purpose', 'ef', 'perspective', 'relation', 'verb', 'observation', 'non_goal',
                                             'name', 'name_length', 'role', 'refs', 'extra'))
    if op == 'add-property':
        (value,) = _empty(ctx, notices, 'value')
        return store.add_property(name, _element(nouns['element']), value, **_optional(ctx, 'refs', 'extra'))
    if op == 'add-item':
        (value,) = _empty(ctx, notices, 'value')
        link = _node(nouns['link']) if 'link' in nouns else None
        return store.add_item(name, _node(nouns['node']), value, link=link, **_optional(ctx, 'refs', 'extra'))
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
    if op == 'correct':
        (reason,) = _empty(ctx, notices, 'reason')
        return store.correct(name, nouns['id'], _changes(ctx), remove=bool(nouns.get('remove')), reason=reason,
                             evidence=nouns.get('evidence'))
    if op == 'finish':
        return store.finish(name)
    if op == 'peel':
        return store.peel(name)
    if op == 'discard':
        return store.discard(name)
    raise Stop(f'{op!r} is not a knowledge operation.', 'metaform help map knowledge')


def _noun(name: str, help: str, kind: NounKind = 'str', schema: dict[str, Any] | None = None) -> Noun:
    return Noun(name, help, kind=kind, required=False, schema=schema)


KNOWLEDGE_NOUNS = (
    _noun('op', 'create, add-element, add-join, add-subtype, add-property, add-item, add-ref, add-plan, edit, remove, '
                'correct, finish, peel or discard.'),
    _noun('layer', 'The layer this call works on, by name or id. An object added without one goes to a new layer '
                   'named unnamed-<time>.'),
    _noun('variable', 'create: the one question the layer answers.'),
    _noun('mutable', 'create: whether its items change in place.', 'bool'),
    _noun('hideable', 'create: whether it can be hidden.', 'bool'),
    _noun('kind', 'create: layer, or correction.'),
    _noun('fields', 'create: the fields of the variable, a JSON list of names.', 'json', {'type': 'array'}),
    _noun('sources', 'create: the layers it is built from, a JSON list.', 'json', {'type': 'array'}),
    _noun('tags', 'create: its tags, a JSON list.', 'json', {'type': 'array'}),
    _noun('module', 'create: the module that makes the layer.'),
    _noun('workflow', 'create: the workflow within that module.'),
    _noun('prompt', 'create: the prompt the layer is made from.'),
    _noun('model', 'create: the model that makes it.'),
    _noun('role', 'create: the role of its producer; add-element and add-subtype: DE, SE, NE, CQU or AUE, the role of '
                  'the element, the one a subtype join holds included.'),
    _noun('blinded', 'create: whether the producer saw only the map.', 'bool'),
    _noun('address', 'add-element: the element\'s dotted namespace address; add-subtype: the address of the element '
                     'the subtype join holds. An element cannot be moved: edit and correct do not apply it.'),
    _noun('name', "add-join and add-subtype: the project's own name for the functionality the join names, its "
                  'canonical or informal name. An element holds no name: its name is its address read through '
                  'name_length.'),
    _noun('name_length', 'add-element and add-subtype: how many trailing segments form the element\'s short name.',
          'int'),
    _noun('refs', 'A JSON list of [key, value] pairs, in order.', 'json', REFS_SCHEMA),
    _noun('extra', 'A JSON object of further fields.', 'json', {'type': 'object'}),
    _noun('receiver', 'add-join: the element that holds the purpose; edit and correct: another receiver, which moves '
                      'the join.'),
    _noun('provider', 'add-join: the element whose function serves it; edit and correct: another provider, or on a '
                      'subtype join another element to hold.'),
    _noun('parent', 'edit and correct: the id of a join held by a receiver; the join becomes a subtype join inside '
                    'it, keeping its purpose.'),
    _noun('purpose', 'add-join and add-subtype: the Operative Purpose; a subtype join keeps its own purpose.'),
    _noun('ef', "add-join and add-subtype: the Encounter Function."),
    _noun('perspective', 'add-join and add-subtype: Function if it is the encounter of a functionality, Encounter if it is the '
                'functionality of the encounter.', schema=EF),
    _noun('relation', 'add-join and add-subtype: the relation in active voice.'),
    _noun('verb', 'add-join and add-subtype: the third-person singular present-tense active verb of the relation, '
                  'ending in -s or -es.'),
    _noun('observation', 'add-join and add-subtype: what is actually there.'),
    _noun('non_goal', 'add-join and add-subtype: what the receiver does not seek.'),
    _noun('type', 'add-join: the join type, purpose by default.'),
    _noun('join', 'add-subtype: the id of the join the subtype join sits in; add-plan: the join id.'),
    _noun('element', 'add-property and add-plan: the element, by address or id, or as a node such as type:code.'),
    _noun('value', 'add-item, add-property, edit and add-ref: the value, as JSON.', 'json', {}),
    _noun('node', 'add-item: element:<address or id> or join:<id>, a subtype join being a join.'),
    _noun('link', 'add-item: a node the item links to.'),
    _noun('owner', 'add-ref: the id of the thing the ref belongs to.'),
    _noun('key', 'add-ref: the ref key.'),
    _noun('id', 'edit, remove and correct: the id of the thing.'),
    _noun('reason', 'correct: why.'),
    _noun('evidence', 'correct: what shows it.'),
    _noun('remove', 'correct: remove the thing instead of changing it.', 'bool'),
)

# The nouns each work operation reads, besides op.
WORK_READS: dict[str, frozenset[str]] = {
    'list': frozenset({'node', 'condition', 'open', 'limit', 'after'}),
    'add': frozenset({'node', 'condition', 'note', 'task', 'held', 'reviewed'}),
    'edit': frozenset({'id', 'condition', 'note', 'task', 'held', 'reviewed'}),
    'done': frozenset({'id', 'resolution'}),
    'take': frozenset({'id', 'steps'}),
    'plan': frozenset({'id', 'steps'}),
    'step': frozenset({'id', 'said'}),
}
WORK_FIELDS = ('condition', 'note', 'task', 'held', 'reviewed')
# The field each work operation cannot store its record without, BASE-038: the object it attaches to, or the record.
WORK_NEEDS: dict[str, tuple[str, ...]] = {'list': (), 'add': ('node',), 'edit': ('id',), 'done': ('id',),
                                          'take': ('id',), 'plan': ('id', 'steps'), 'step': ('id',)}


def _work_node(value: Any) -> Node:
    """A node written `kind:<address or id>`, or a bare address or id, which names an element."""
    if isinstance(value, str) and ':' in value and value.partition(':')[0] in PLACE_KINDS:
        return Node.parse(value)
    return Node('element', str(value))


def ask(ctx: Context) -> Any:
    """Ask the user a question at a node, in plain words, with the answers you suggest, MAP-050."""
    return _store(ctx).ask(_work_node(ctx.nouns['node']), ctx.nouns['question'],
                           suggestions=ctx.nouns.get('suggestions'), by=ctx.nouns.get('by'))


def tell(ctx: Context) -> Any:
    """Leave the user a message at a node, which asks for nothing and waits to be read, MAP-050."""
    return _store(ctx).tell(_work_node(ctx.nouns['node']), ctx.nouns['message'], by=ctx.nouns.get('by'))


def reply(ctx: Context) -> Any:
    """Answer a question, or mark a message read, MAP-050."""
    return _store(ctx).reply(ctx.nouns['id'], ctx.nouns.get('answer'))


def messages(ctx: Context) -> Any:
    """The questions and messages left for the user, oldest first, MAP-050."""
    nouns = ctx.nouns
    node = _work_node(nouns['node']) if 'node' in nouns else None
    return _store(ctx).messages(node, nouns.get('kind'), nouns.get('open'), **_paging(ctx))


def work(ctx: Context) -> Any:
    """The work records: the condition of an element or a join, apart from the map, MAP-046 and STORE-042.
    op=list, the default, reads them; add, edit and done write one each. Any agent, at any time."""
    op = str(ctx.nouns.get('op', 'list'))
    if op not in WORK_READS:
        raise Stop(f'{op!r} is not a work operation: op=list, add, edit, take, plan, step or done.',
                   'metaform help map work')
    _need(ctx, *WORK_NEEDS[op], verb='work')
    unread = sorted(name for name in ctx.nouns if name != 'op' and name not in WORK_READS[op])
    notices = [Notice(name, f'op={op} does not read {name}; it was ignored.') for name in unread]
    for name in unread:
        ctx.nouns.pop(name)
    store, nouns = _store(ctx), ctx.nouns
    if op == 'list':
        node = _work_node(nouns['node']) if 'node' in nouns else None
        return _with_notices(store.work(node, nouns.get('condition'), nouns.get('open'), **_paging(ctx)), notices)
    if op == 'add':
        # A missing condition is stored empty, and the store names it in its notice, STORE-042.
        return _with_notices(store.add_work(_work_node(nouns['node']), nouns.get('condition'),
                                            **_optional(ctx, 'note', 'task', 'held', 'reviewed')), notices)
    work_id = nouns['id']
    if op == 'take':
        return _with_notices(store.take_work(work_id, nouns.get('steps')), notices)
    if op == 'plan':
        return _with_notices(store.plan_work(work_id, nouns['steps']), notices)
    if op == 'step':
        return _with_notices(store.step_work(work_id, nouns.get('said')), notices)
    if op == 'edit':
        return _with_notices(store.edit_work(work_id, {name: nouns[name] for name in WORK_FIELDS if name in nouns}),
                             notices)
    return _with_notices(store.finish_work(work_id, nouns.get('resolution')), notices)


WORK_NOUNS = (
    _noun('op', 'list, the default; add; edit; take, which says an agent has started on the task; plan, which says '
                'how many steps the agent plans; step, which says it finished one; or done.'),
    _noun('steps', 'take and plan: how many steps you plan for the task. Say it again when your plan changes.', 'int'),
    _noun('said', 'step: what you did in the step you finished, in a sentence.'),
    _noun('node', 'list and add: element:<address or id> or join:<id>, a subtype join being a join; a bare address '
                  'names an element.'),
    _noun('condition', 'add, edit, and list as a filter: missing, in the specs and not built yet; broken; or exclude, '
                       'material outside the intake scope or code conflicting with a superseding specification, '
                       'with the reason and references recorded for review.'),
    _noun('note', 'add and edit: what and where.'),
    _noun('task', 'add and edit: what it needs.'),
    _noun('held', 'add and edit: keep it waiting until agents are assigned or take it.', 'bool'),
    _noun('reviewed', 'add and edit: it has been checked for correctness before being fired off.', 'bool'),
    _noun('id', 'edit, take, plan, step and done: the work record id.'),
    _noun('resolution', 'done: how it was resolved, kept beside the record.'),
    _noun('open', 'list: true for records not done, false for those done.', 'bool'),
    *PAGING,
)

RAW = ('raw',)


MODULE = Module(
    id='map',
    status=None,
    summary="Read and write this project's functional map and its layers.",
    purpose="Reads and writes this project's functional map. Handed an address, start with where: one read of "
            'the address returns the element, what relies on it, every join it provides with the receiver and its '
            'purpose, what it relies on, every join it receives with the provider and its function, the subtype joins '
            'inside them, its open work records and what the layers in context hold at it; full=true keeps ids. With '
            "no address, start with roots: the map's entry, the CQU and the DE with their joins, and the root "
            'elements. The receiver holds the purpose, the provider delivers the function. '
            'Record what you learn at a node with the memory tools; to build or improve a knowledge layer, use '
            'knowledge, naming the layer on every call: create it, add, edit and remove its objects one at a '
            'time, and finish it when the task is done. Details: metaform help map.',
    details='Every read that returns a join shows the layer it comes from. --raw reads every stored layer.',
    verbs=(
        Verb('roots', roots, "The map's entry: the CQU and the DE with their joins, and every root element.",
             nouns=PAGING, switches=RAW),
        Verb('where', where, 'One read of an address: the element, what relies on it, what it relies on, the subtype '
                             'joins inside those joins and the one holding it, its open work records and the layers '
                             "in context at it; with an empty address, the map's entry.",
             nouns=(Noun('address', 'A dotted namespace address, or empty for the entry.'),
                    _noun('full', 'true keeps ids and empty fields, which are left out by default.', 'bool')),
             switches=RAW),
        Verb('markdown', markdown, 'The map, or the part around one address, as a short Markdown document.',
             nouns=(_noun('address', 'A dotted namespace address; without one, the whole map.'),
                    _noun('file', 'A file to write the document to; without one, it is printed.')),
             switches=RAW, surfaces=('cli',)),
        Verb('element', element, 'One element: its address, name_length, role and short name, with its refs.',
             nouns=(Noun('element', 'An address or element id.'),), switches=RAW),
        Verb('joins', joins, 'The joins an element owns, or with as=provider those it serves.',
             nouns=(Noun('element', 'An address or element id.'), _noun('as', 'receiver or provider.'), *PAGING),
             switches=RAW),
        Verb('identity', identity, 'Every join an element provides for: who receives it, why and how.',
             nouns=(Noun('element', 'An address or element id.'), *PAGING), switches=RAW),
        Verb('subtypes', subtypes, 'The subtype joins inside a join, each with the element it holds.',
             nouns=(Noun('join', 'A join id.'), *PAGING),
             switches=RAW),
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
             nouns=(Noun('node', 'element:<address or id> or join:<id>, a subtype join being a join.'),),
             switches=RAW),
        Verb('context', context, 'The properties that apply at an address, and those attached toward the leaves from '
                                 'it that are visible there.',
             nouns=(Noun('address', 'A dotted namespace address.'), *PAGING)),
        Verb('links', links, 'Items that link to a node.',
             nouns=(Noun('node', 'A node.'), _noun('layer', 'Only this layer.'), *PAGING), switches=RAW),
        Verb('citing', citing, 'Everything whose refs hold a key and value.',
             nouns=(Noun('key', 'The ref key, such as path.'), Noun('value', 'The ref value.'), *PAGING)),
        Verb('history', history, 'Every version of a thing, in stack order.', nouns=(Noun('id', 'An id.'), *PAGING)),
        Verb('stack', stack, 'The correction layers in the order they were applied.', nouns=PAGING),
        Verb('metaforms', metaforms, "The project's metaforms.", nouns=(_noun('project', 'A project id.'), *PAGING)),
        Verb('add-metaform', add_metaform, 'Start a new, empty metaform and make it active.',
             nouns=(Noun('name', 'The metaform name.'), _noun('project', 'A project id.'))),
        Verb('activate', activate, 'Make a metaform the active one.',
             nouns=(Noun('name', 'The metaform name.'), _noun('project', 'A project id.'))),
        Verb('search', search, 'Items whose value holds every word of the text.',
             nouns=(Noun('text', 'The words to find.'), _noun('layer', 'Only this layer.'), *PAGING)),
        Verb('work', work, 'The work records, the condition of an element or a join apart from the map: list them, '
                           'or add, edit or mark one done.',
             nouns=WORK_NOUNS,
             details='A work record is attached to one element or join, a subtype join included, and never changes '
                     'the map. Its '
                     'condition is missing, broken or exclude; its note says what and where, its task what it needs. '
                     'exclude records material outside the intake scope or code conflicting with a superseding '
                     'specification. The note links the affected material and the specification or scope reason '
                     'for review. Unrelated folders are excluded from functional capture; a proposed gitignore '
                     'change is recorded for review. Documents, specifications, notes and working files are '
                     'preserved. Marking a record does not remove files or change gitignore. Unneeded legacy '
                     'migration code is marked for review; a needed migration tool belongs outside the main '
                     'program as a separate tool. It is '
                     'open until op=done records its resolution, which is kept beside it. Any agent writes one at any '
                     'time, the intake agent as it maps, a critic with its findings, held=true until agents take it.',
             examples=(('metaform map work op=add node=element:code.alarm.audible condition=missing task="build it"',
                        'Record that the alarm is in the specs and not built yet.'),
                       ('metaform map work condition=broken open=true', 'List the open broken records.'),
)),
        Verb('ask', ask, 'Ask the user a question at the node it concerns, with the answers you suggest.',
             nouns=(Noun('node', 'Where the question applies: element:<address or id> or join:<id>; a bare address '
                                 'names an element.'),
                    Noun('question', 'The question, in plain words a person who has not read your context can answer.'),
                    _noun('suggestions', 'The answers you suggest, the one you recommend first, as a JSON list. The '
                                         'user answers with one click on one of them, or types another.', 'json'),
                    _noun('by', 'Who asks: your role or your name, so the user knows whose question it is.')),
             details='Ask, and carry on with what does not depend on the answer. The user answers in the web GUI, '
                     'where the node glows until they do, and the answer is kept at the node for the agent that '
                     'works there next. Read the answers with metaform map messages.',
             examples=(('metaform map ask code.alarm.audible "Is the quiet tone still wanted?" '
                        'suggestions=\'["Yes, keep it", "No, make it louder"]\'', 'Ask the user at the alarm.'),)),
        Verb('tell', tell, 'Leave the user a message at a node, which asks for nothing and waits to be read.',
             nouns=(Noun('node', 'Where the message applies: element:<address or id> or join:<id>.'),
                    Noun('message', 'What the user should know, in plain words.'),
                    _noun('by', 'Who says it: your role or your name.'))),
        Verb('reply', reply, 'Answer a question, or mark a message read.',
             nouns=(Noun('id', 'The id of the question or the message.'),
                    _noun('answer', 'The answer to a question.')),
             examples=(('metaform map reply <id> answer="No, make it louder"', 'Answer a question.'),)),
        Verb('messages', messages, 'The questions and messages left for the user, oldest first.',
             nouns=(_noun('node', 'Only those at this node.'), _noun('kind', 'question or message.'),
                    _noun('open', 'true for those that still wait, false for those answered or read.', 'bool'),
                    *PAGING)),
        Verb('knowledge', knowledge, 'Create, build, edit and finish a knowledge or correction layer.',
             nouns=KNOWLEDGE_NOUNS,
             details='Every call names its layer with layer=. op=create makes the layer; the add, edit and remove '
                     'operations change one object each; op=finish marks it ready.',
             examples=((('metaform map knowledge op=create layer=practices-cpp variable="C++ practice here." '
                         'mutable=true hideable=true'), 'Start a knowledge layer.'),)),
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
    ),
)
