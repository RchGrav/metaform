"""map: the data access object's map and layer operations as verbs, BASE-038.

Every verb calls `ctx.require_store()` and exactly one operation of STORE-024
or STORE-025, and returns its result, BASE-036. The fields of a record being
written are nouns: required ones positional, optional ones `name=value`. The
only switch is `--raw`, which reads every stored layer instead of the layers
in context. `knowledge` is the one read-write verb for layers, LAYER-018.
"""
from __future__ import annotations

from typing import Any

from metaform import settings
from metaform.data import PLACE_KINDS, Node, Store
from metaform.module import Context, Module, Noun, NounKind, Stop, Verb

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False

settings.boolean('raw', False, help='Read every stored layer, building, hidden and masked ones included.')

REFS_SCHEMA = {'type': 'array', 'items': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 2, 'maxItems': 2}}
FIELDS = ('address', 'extra', 'receiver', 'provider', 'type', 'purpose', 'function', 'relation', 'observation',
          'non_goal', 'name', 'name_length', 'role', 'value', 'link', 'element', 'refs')
UNNAMED = ('add-element', 'add-join', 'add-subtype', 'add-property', 'add-item')


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
    """The map's entry: the VE and the DE with their joins, and every root element, STORE-025."""
    return _store(ctx).roots(**_reading(ctx), **_paging(ctx))


def where(ctx: Context) -> Any:
    if not ctx.nouns['address']:
        return roots(ctx)
    return _store(ctx).where(ctx.nouns['address'], **_reading(ctx))


def findings(ctx: Context) -> Any:
    return _store(ctx).findings(ctx.nouns.get('flag'), ctx.nouns.get('layer'), **_reading(ctx), **_paging(ctx))


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


def _need(ctx: Context, *names: str) -> list[Any]:
    missing = [name for name in names if name not in ctx.nouns]
    if missing:
        op = ctx.nouns.get('op')
        raise Stop(f'knowledge op={op} needs {", ".join(missing)}.', 'metaform help map knowledge')
    return [ctx.nouns[name] for name in names]


def _changes(ctx: Context) -> dict[str, Any]:
    changes = {name: ctx.nouns[name] for name in FIELDS if name in ctx.nouns}
    if 'link' in changes and isinstance(changes['link'], str):
        changes['link'] = _node(changes['link'])
    if 'element' in changes:
        changes['element'] = _element(changes['element'])
    return changes


def _optional(ctx: Context, *names: str) -> dict[str, Any]:
    return {name: ctx.nouns[name] for name in names if name in ctx.nouns}


def knowledge(ctx: Context) -> Any:
    """Create, build, edit and finish a knowledge or correction layer, one object per call, LAYER-018."""
    store = _store(ctx)
    (op,) = _need(ctx, 'op')
    nouns = ctx.nouns
    # A write of an object sent without a layer goes to a new unnamed layer, LAYER-001; every other op names one.
    name = str(nouns.get('layer') or '') if op in UNNAMED else str(_need(ctx, 'layer')[0])
    if op == 'create':
        variable, mutable, hideable = _need(ctx, 'variable', 'mutable', 'hideable')
        kind = nouns.get('kind', 'layer')
        if kind not in ('layer', 'correction'):
            raise Stop('knowledge creates a knowledge layer or a correction layer: kind=layer or kind=correction.',
                       'metaform help map knowledge')
        provenance = {'module': nouns.get('module', 'map'),
                      **{key: nouns[key] for key in ('workflow', 'prompt', 'model', 'role', 'blinded') if key in nouns}}
        return store.layer(name, provenance['module'], variable, kind=kind, mutable=mutable, hideable=hideable,
                           fields=tuple(nouns.get('fields', ())), tags=tuple(nouns.get('tags', ())),
                           provenance=provenance, sources=tuple(nouns.get('sources', ())))
    if op == 'add-element':
        (address,) = _need(ctx, 'address')
        return store.add_element(name, address, **_optional(ctx, 'name', 'name_length', 'role', 'refs', 'extra',
                                                            'flag', 'flag_note'))
    if op == 'add-join':
        receiver, provider, purpose, function, relation, observation = _need(
            ctx, 'receiver', 'provider', 'purpose', 'function', 'relation', 'observation')
        return store.add_join(name, receiver, provider, purpose=purpose, function=function, relation=relation,
                              observation=observation, **_optional(ctx, 'non_goal', 'type', 'refs', 'extra', 'flag',
                                                                   'flag_note'))
    if op == 'add-subtype':
        join, address = _need(ctx, 'join', 'address')
        return store.add_subtype(name, join, address, **_optional(ctx, 'function', 'relation', 'observation', 'name',
                                                                  'name_length', 'role', 'refs', 'extra', 'flag',
                                                                  'flag_note'))
    if op == 'add-property':
        element_ref, value = _need(ctx, 'element', 'value')
        return store.add_property(name, _element(element_ref), value, **_optional(ctx, 'refs', 'extra'))
    if op == 'add-item':
        target, value = _need(ctx, 'node', 'value')
        link = _node(nouns['link']) if 'link' in nouns else None
        return store.add_item(name, _node(target), value, link=link, **_optional(ctx, 'refs', 'extra'))
    if op == 'add-ref':
        owner, key, value = _need(ctx, 'owner', 'key', 'value')
        if not isinstance(value, str):
            raise Stop('A ref value is text.', 'metaform help map knowledge')
        return store.add_ref(owner, key, value)
    if op == 'add-plan':
        (element_ref,) = _need(ctx, 'element')
        return store.add_plan(name, _element(element_ref), nouns.get('join'))
    if op == 'edit':
        (thing,) = _need(ctx, 'id')
        return store.edit(thing, _changes(ctx))
    if op == 'remove':
        (thing,) = _need(ctx, 'id')
        return store.remove(int(thing) if str(thing).isdigit() else thing)
    if op == 'correct':
        thing, reason = _need(ctx, 'id', 'reason')
        return store.correct(name, thing, _changes(ctx), remove=bool(nouns.get('remove')), reason=reason,
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
    _noun('role', 'create: the role of its producer; add-element and add-subtype: DE, SE, NE, VE or AUE.'),
    _noun('blinded', 'create: whether the producer saw only the map.', 'bool'),
    _noun('address', 'add-element, add-subtype and edit: a dotted namespace address.'),
    _noun('name', 'add-element and add-subtype: the informal name.'),
    _noun('name_length', 'add-element and add-subtype: how many trailing segments form the short name.', 'int'),
    _noun('refs', 'A JSON list of [key, value] pairs, in order.', 'json', REFS_SCHEMA),
    _noun('extra', 'A JSON object of further fields.', 'json', {'type': 'object'}),
    _noun('receiver', "add-join: the element that holds the purpose."),
    _noun('provider', 'add-join: the element whose function serves it.'),
    _noun('purpose', 'add-join: the Operative Purpose.'),
    _noun('function', "add-join and add-subtype: the Encounter Function."),
    _noun('relation', 'add-join and add-subtype: the relation in active voice.'),
    _noun('observation', 'add-join and add-subtype: what is actually there.'),
    _noun('non_goal', 'add-join: what the receiver does not seek.'),
    _noun('type', 'add-join: the join type, purpose by default.'),
    _noun('join', 'add-subtype and add-plan: the join id.'),
    _noun('element', 'add-property and add-plan: the element, by address or id, or as a node such as type:code.'),
    _noun('value', 'add-item, add-property, edit and add-ref: the value, as JSON.', 'json', {}),
    _noun('node', 'add-item: element:<address or id>, join:<id> or subtype:<address or id>.'),
    _noun('link', 'add-item: a node the item links to.'),
    _noun('owner', 'add-ref: the id of the thing the ref belongs to.'),
    _noun('key', 'add-ref: the ref key.'),
    _noun('id', 'edit, remove and correct: the id of the thing.'),
    _noun('reason', 'correct: why.'),
    _noun('evidence', 'correct: what shows it.'),
    _noun('remove', 'correct: remove the thing instead of changing it.', 'bool'),
    _noun('flag', 'add-element, add-join and add-subtype: missing, broken or cruft; leave it out when it works.'),
    _noun('flag_note', 'add-element, add-join and add-subtype: a short note on the flag.'),
)

RAW = ('raw',)

MODULE = Module(
    id='map',
    summary="Read and write this project's functional map and its layers.",
    purpose="Reads and writes this project's functional map. Start with map_roots: it returns the map's entry, the "
            'VE and the DE with their joins, and the root elements. Before changing a part, read it with map_where or '
            'map_element and follow its joins: the receiver holds the purpose, the provider delivers the function. '
            'Record what you learn at a node with the memory tools; to build or improve a knowledge layer, use '
            'map_knowledge, naming the layer on every call: create it, add, edit and remove its objects one at a '
            'time, and finish it when the task is done. Details: metaform help map.',
    details='Every read that returns a join shows the layer it comes from. --raw reads every stored layer.',
    verbs=(
        Verb('roots', roots, "The map's entry: the VE and the DE with their joins, and every root element.",
             nouns=PAGING, switches=RAW),
        Verb('where', where, 'The element at an address, or the subtype there with its join; with an empty '
                             "address, the map's entry.",
             nouns=(Noun('address', 'A dotted namespace address, or empty for the entry.'),), switches=RAW),
        Verb('element', element, 'One element with its descriptors and refs.',
             nouns=(Noun('element', 'An address or element id.'),), switches=RAW),
        Verb('joins', joins, 'The joins an element owns, or with as=provider those it serves.',
             nouns=(Noun('element', 'An address or element id.'), _noun('as', 'receiver or provider.'), *PAGING),
             switches=RAW),
        Verb('identity', identity, 'Every join an element provides for: who receives it, why and how.',
             nouns=(Noun('element', 'An address or element id.'), *PAGING), switches=RAW),
        Verb('subtypes', subtypes, 'The subtypes inside a join.', nouns=(Noun('join', 'A join id.'), *PAGING),
             switches=RAW),
        Verb('children', children, 'The next types up the tree, toward the leaves.',
             nouns=(Noun('address', 'A dotted namespace address.'), *PAGING)),
        Verb('layers', layers, 'The layers, with their kind, tags, state and whether each is on here.',
             nouns=(_noun('tag', 'Only layers with this tag.'), _noun('kind', 'Only layers of this kind.'),
                    _noun('module', 'Only layers of this module.'), *PAGING)),
        Verb('tag', tag, 'Add a tag to a layer.', nouns=(Noun('layer', 'A layer.'), Noun('tag', 'The tag.'))),
        Verb('untag', untag, 'Remove a tag from a layer.', nouns=(Noun('layer', 'A layer.'), Noun('tag', 'The tag.'))),
        Verb('layer', layer, 'Everything one layer holds, or what it holds at one node.',
             nouns=(Noun('layer', 'A layer.'), _noun('node', 'A node, such as element:code.engine.'), *PAGING)),
        Verb('node', node, "Every layer's items at one node, grouped by layer.",
             nouns=(Noun('node', 'element:<address or id>, join:<id> or subtype:<address or id>.'),), switches=RAW),
        Verb('context', context, 'The properties that apply at an address, and those visible there from above.',
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
        Verb('findings', findings, 'The objects the intake flagged missing, broken or cruft.',
             nouns=(_noun('flag', 'missing, broken or cruft.'), _noun('layer', 'Only this layer.'), *PAGING),
             switches=RAW),
        Verb('knowledge', knowledge, 'Create, build, edit and finish a knowledge or correction layer.',
             nouns=KNOWLEDGE_NOUNS,
             details='Every call names its layer with layer=. op=create makes the layer; the add, edit and remove '
                     'operations change one object each; op=finish marks it ready.',
             examples=(('metaform map knowledge op=create layer=practices-cpp variable="C++ practice here." '
                        'mutable=true hideable=true', 'Start a knowledge layer.'),)),
        Verb('select', select, 'Turn a layer on at an address and above it.',
             nouns=(Noun('address', 'An address.'), Noun('layer', 'A layer.'))),
        Verb('mask', mask, 'Stop a layer flowing into an address and above it.',
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
