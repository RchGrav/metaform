"""Layers and knowledge of a project held in the project store (`metaform.project`): its overlays.

Kickoff 2026-11-17, Phase 3, decision t-legacy-keep: every feature of the old store is kept and moved onto the project
store. There a knowledge layer is an overlay, defined beneath `<project>.overlay`, and a knowledge item or property is
one record of it at an element. So for a project held there:

- `layers` lists its overlays; `layer` reads one overlay's records, across the map or at one element; `node` reads
  every overlay's records at one element, grouped by overlay; `context` reads the records that apply at an address,
  those held there, and those held toward the leaves from it. A record applies where it is held: the store inherits
  nothing toward the leaves and masks nothing, so these reads are whole.
- `links` lists the records that link to an element: those whose field of type address names it, the wants among
  them. A ref is the uri of an artifact, never an element of the map, so it is no link.
- `citing` finds the elements, wants and records whose one ref is the path or URL given.
- `knowledge` defines an overlay (op=create, the layer's variable its description, its fields the overlay's fields
  beside `value` and `link`), adds a record at an element (add-item, add-property), sets a record's ref (add-ref), and
  edits or removes a record by its id; each change names the record id and revision it found (F02).

What has no faithful place there is refused by name: tags, selects and masks, hiding, the re-examination mark, a
finished or discarded layer, provenance, a layer's own elements, joins and plans, a node that is a join, and an
item's read_first, always_show, task and condition. Projects not held there keep the old store's path unchanged.
"""
from __future__ import annotations

import json
from typing import Any, cast

from metaform import project as project_store
from metaform.data import Node, Notice
from metaform.module import Context, Stop

from .glossary import _clean  # pyright: ignore[reportPrivateUsage]  # within the map module

TOOL = 'the project tool'
WANTS = 'wants'
REF_KEYS = ('path', 'url', 'uri')  # a ref in the project store is one text: a path, a URL or another project's uri
LIST = 50


def _in(project: str) -> str:
    return f"{project}'s map is in the project store, where"


# The verbs with no faithful meaning on a project held in the project store, each refused with its reason by the map
# module's guard (map/__init__.py, _beside_the_store).
NO_PLACE: dict[str, str] = {
    'tag': 'an overlay has no tags: it is named by its key, which `metaform map layers` lists.',
    'untag': 'an overlay has no tags: it is named by its key, which `metaform map layers` lists.',
    'select': 'an overlay is read wherever its records are held; nothing turns it on or off at an address.',
    'mask': 'an overlay is read wherever its records are held; nothing stops it reaching an address.',
    'clear': 'an overlay has no select or mask at an address to remove.',
    'hide': 'an overlay cannot be hidden: every read shows the records held at an element.',
    'unhide': 'an overlay cannot be hidden, so none is hidden to show again.',
    'reexamined': 'an overlay carries no re-examination mark: its records are checked against the map when written.',
}


def refusal(verb: str) -> str | None:
    """The reason `map <verb>` has no faithful meaning for a project held in the project store, or None."""
    return NO_PLACE.get(verb)


def _no_place(project: str, what: str, step: str = 'metaform help map knowledge') -> Stop:
    return Stop(f'{_in(project)} {what}', step)


def _done(answer: dict[str, object], step: str = 'metaform help map knowledge') -> dict[str, object]:
    if answer.get('status') == 'error':
        raise Stop(str(answer.get('message') or 'The project store refused the change.'),
                   json.dumps(answer['remediation']) if answer.get('remediation') else step)
    return answer


def _local(project: str, path: str) -> str:
    """An element's address without the project's name, as the map verbs write it."""
    return path[len(project) + 1:] if path.startswith(project + '.') else path


def _drawn(project: str) -> dict[str, Any]:
    drawn = project_store.drawn(project)
    if drawn is None:
        raise Stop(f"{project}'s map could not be read from the project store.", f'{TOOL}: {{"map": "{project}"}}')
    return drawn


def _overlays(drawn: dict[str, Any]) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], drawn['overlays'])


def _page(ctx: Context, found: list[dict[str, Any]], **more: Any) -> dict[str, Any]:
    """One page of a list read: after= is how many came before, as the glossary pages its list."""
    start = int(ctx.nouns.get('after') or 0)
    limit = int(ctx.nouns.get('limit') or LIST)
    page = found[start:start + limit] if limit else found[start:]
    result: dict[str, Any] = {**more, 'total': len(found), 'results': page}
    if limit and start + limit < len(found):
        result['next'] = str(start + limit)
    return result


def _key(project: str, drawn: dict[str, Any], layer: str) -> str:
    """The key of the overlay a layer name gives: its key, or its steps beneath the overlay root."""
    steps = '.'.join(step.lower().replace('-', '_') for step in layer.split('.'))
    for one in _overlays(drawn):
        if one['key'] == layer or one['address'] == f'{project}.overlay.{steps}':
            return str(one['key'])
    raise Stop(f"{layer} is not an overlay of {project}'s map in the project store.", 'metaform map layers')


def _record(project: str, key: str, record: dict[str, Any]) -> dict[str, Any]:
    """An overlay record as a layer read shows it: its overlay, the element it is at, its id and its fields."""
    shown: dict[str, Any] = {'layer': key, 'node': _local(project, str(record['element']))}
    shown.update((name, value) for name, value in record.items() if name not in ('element', 'position'))
    return shown


def _want(project: str, want: dict[str, Any]) -> dict[str, Any]:
    """A want as a layer read shows it: the wants overlay's record at the element that holds it. A want has no record
    id: it is named by its holder, its element and its ref (F13)."""
    shown: dict[str, Any] = {'layer': WANTS, 'node': _local(project, str(want['holder'])),
                             'element': _local(project, str(want['element']))}
    shown.update((name, value) for name, value in want.items() if name not in ('holder', 'element'))
    return shown


def _records(project: str, drawn: dict[str, Any], key: str) -> list[dict[str, Any]]:
    if key == WANTS:
        return [_want(project, one) for one in cast(list[dict[str, Any]], drawn['wants'])]
    found = cast(list[dict[str, Any]], project_store.overlay_records(project, key) or [])
    return [_record(project, key, one) for one in found]


def _every(project: str, drawn: dict[str, Any]) -> list[dict[str, Any]]:
    """Every record of every overlay, overlay by overlay."""
    return [one for overlay in _overlays(drawn) for one in _records(project, drawn, str(overlay['key']))]


def _address(project: str, drawn: dict[str, Any], given: str, step: str) -> str:
    """An element's address from a node or an address: element:<address> or type:<address>. A join is no element of
    the project store, where a want is held by its element, so a node that is a join is refused by name."""
    text = given
    if ':' in given:
        node = Node.parse(given)
        if node.kind == 'join':
            raise _no_place(project, 'a record is held by an element, never by a join; read the element that holds '
                                     'the want instead.', step)
        text = node.id
    address = _local(project, text)
    if address not in {_local(project, str(one['address'])) for one in cast(list[dict[str, Any]], drawn['elements'])}:
        raise Stop(f"{given} is not an element of {project}'s map.", f'{TOOL}: {{"map": "{project}"}}')
    return address


# Reads

def layers(ctx: Context, project: str) -> Any:
    """The project's overlays, each with its key, the address of its definition and its description."""
    given = [name for name in ('tag', 'kind', 'module') if ctx.nouns.get(name)]
    if given:
        raise _no_place(project, f'an overlay has no {", ".join(given)}: list them all and name one by its key.',
                        'metaform map layers')
    found = [{'layer': one['key'], 'overlay': _local(project, str(one['address'])), 'description': one['description']}
             for one in _overlays(_drawn(project))]
    return _page(ctx, found, project=project)


def layer(ctx: Context, project: str) -> Any:
    """Every record of one overlay, or those at one element."""
    drawn = _drawn(project)
    key = _key(project, drawn, str(ctx.nouns['layer']))
    found = _records(project, drawn, key)
    if ctx.nouns.get('node'):
        at = _address(project, drawn, str(ctx.nouns['node']), 'metaform help map layer')
        found = [one for one in found if one['node'] == at]
    return _page(ctx, found, layer=key)


def node(ctx: Context, project: str) -> Any:
    """Every overlay's records at one element, grouped by overlay."""
    drawn = _drawn(project)
    at = _address(project, drawn, str(ctx.nouns['node']), 'metaform help map node')
    groups: list[dict[str, Any]] = []
    for overlay in _overlays(drawn):
        held = [one for one in _records(project, drawn, str(overlay['key'])) if one['node'] == at]
        if held:
            groups.append({'layer': overlay['key'], 'records': held})
    return {'node': at, 'layers': groups}


def context(ctx: Context, project: str) -> Any:
    """The records that apply at an address, those its element holds, and those held toward the leaves from it."""
    drawn = _drawn(project)
    address = _local(project, str(ctx.nouns['address']))
    every = _every(project, drawn)
    applying = [one for one in every if one['node'] == address]
    below = sorted((one for one in every if str(one['node']).startswith(address + '.')),
                   key=lambda one: str(one['node']))
    return _page(ctx, below, address=address, applying=applying)


def links(ctx: Context, project: str) -> Any:
    """The records that link to an element: each whose field of type address names it, its wants among them."""
    drawn = _drawn(project)
    at = _address(project, drawn, str(ctx.nouns['node']), 'metaform help map links')
    only = _key(project, drawn, str(ctx.nouns['layer'])) if ctx.nouns.get('layer') else None
    found: list[dict[str, Any]] = []
    for overlay in _overlays(drawn):
        key = str(overlay['key'])
        if only is not None and key != only:
            continue
        if key == WANTS:
            found += [one for one in _records(project, drawn, key) if one['element'] == at]
            continue
        definition = cast(dict[str, Any], project_store.run({str(overlay['address']): {}}).get(str(overlay['address']))
                          or {})
        named = [name for name, spec in definition.items()
                 if isinstance(spec, dict) and cast(dict[str, Any], spec).get('type') == 'address']
        if named:
            found += [one for one in _records(project, drawn, key)
                      if any(_local(project, str(one.get(name) or '')) == at for name in named)]
    return _page(ctx, found, node=at)


def _same_ref(key: str, ref: object, value: str) -> bool:
    if not isinstance(ref, str):
        return False
    if key == 'path':
        ref = ref.replace('\\', '/')
        while ref.startswith('./'):
            ref = ref[2:]
    return ref == value


def citing(ctx: Context, project: str, key: str, value: str) -> Any:
    """The elements, wants and records whose one ref is this path or URL, each with the element it is at."""
    if key not in REF_KEYS:
        raise _no_place(project, f'a ref is one text, a path, a URL or another project\'s uri, with no key {key}: '
                                 'cite it with key=path, key=url or key=uri.', 'metaform help map citing')
    drawn = _drawn(project)
    found: list[dict[str, Any]] = [
        {'owner': 'element', 'node': _local(project, str(one['address'])), 'ref': one['ref']}
        for one in cast(list[dict[str, Any]], drawn['elements']) if _same_ref(key, one.get('ref'), value)]
    found += [{'owner': 'want', **one} for one in _records(project, drawn, WANTS) if _same_ref(key, one.get('ref'), value)]
    found += [{'owner': 'record', **one} for overlay in _overlays(drawn) if overlay['key'] != WANTS
              for one in _records(project, drawn, str(overlay['key'])) if _same_ref(key, one.get('ref'), value)]
    return _page(ctx, found, key=key, value=value)


# Knowledge

INSTRUCTION = ('Add one record for each item this layer holds about the element it is at: its value, or the layer\'s '
               'own fields, and link for an element it links to. Change one by its record id.')
# What each operation has no faithful place for in the project store, and why.
NO_OPERATION = {
    'link-context': ('an overlay is not attached to a subtree: each record applies at the element that holds it. Add '
                     'the record at each element it applies to with op=add-property.'),
    'add-element': ("an overlay holds no elements of its own: an element is added to the map with the project tool's "
                    'add, or with metaform map refine.'),
    'add-join': ("an overlay holds no joins of its own: a want is added to the map with the project tool's add, or "
                 'with metaform map refine.'),
    'add-plan': 'an overlay holds no plans: work at an element is a ticket, metaform map work op=add.',
    'finish': ('an overlay has no finished state: each record is in use once it is written, so there is nothing to '
               'mark.'),
    'discard': ("an overlay is never unfinished, so there is no draft to discard; removing an overlay and its records "
                "is done with the project tool's delete, record by record, then its definition."),
}
NO_CREATE = ('sources', 'tags', 'module', 'workflow', 'prompt', 'model', 'role', 'blinded')
NO_ITEM = ('read_first', 'always_show', 'task', 'condition')


def _text(name: str, value: object, notices: list[Notice]) -> str:
    """A value as an overlay field holds it: text; any other JSON is stored as its JSON text, and said so."""
    if isinstance(value, str):
        return value
    notices.append(Notice(name, f'{name} is not text; it was stored as its JSON text.'))
    return json.dumps(value, ensure_ascii=False)


def _ref(project: str, refs: object) -> str | None:
    """The one ref a record holds, from the [key, value] pairs given."""
    pairs = cast(list[Any], refs) if isinstance(refs, list) else []
    if not pairs:
        return None
    if len(pairs) > 1:
        raise _no_place(project, f'a record holds one ref, and {len(pairs)} were given: give the one it is about.')
    key, value = (cast(list[Any], pairs[0]) + [None, None])[:2]
    if key not in REF_KEYS or not isinstance(value, str) or not value.strip():
        raise _no_place(project, f'a ref is one text, a path, a URL or another project\'s uri, with no key {key}: '
                                 'give refs=\'[["path", "<path>"]]\'.')
    return value


def _fields(ctx: Context, project: str, drawn: dict[str, Any], notices: list[Notice]) -> dict[str, Any]:
    """The fields of a record from value, extra, link and refs."""
    nouns = ctx.nouns
    fields: dict[str, Any] = {}
    value = nouns.get('value')
    if isinstance(value, dict):  # the layer's own fields
        fields.update((str(name), _text(str(name), one, notices)) for name, one in cast(dict[str, Any], value).items())
    elif value is not None:
        fields['value'] = _text('value', value, notices)
    extra = nouns.get('extra')
    if isinstance(extra, dict):
        clash = sorted(set(cast(dict[str, Any], extra)) & set(fields))
        if clash:
            raise Stop(f'{", ".join(clash)} is given in both value and extra.', 'metaform help map knowledge')
        fields.update((str(name), _text(str(name), one, notices)) for name, one in cast(dict[str, Any], extra).items())
    if nouns.get('link'):
        fields['link'] = f'{project}.{_address(project, drawn, str(nouns["link"]), "metaform help map knowledge")}'
    if 'refs' in nouns:
        ref = _ref(project, nouns['refs'])
        if ref is not None:
            fields['ref'] = ref
    return fields


def _find(project: str, drawn: dict[str, Any], ident: str, layer: str | None) -> tuple[str, dict[str, Any]]:
    """The overlay and record a record id names, with the record's element and position as the store reads them."""
    if not ident.startswith('r-'):
        raise Stop(f'{ident} is not the id of a record in the project store, where {project}\'s map is kept: a '
                   'record id is r- and 16 hex digits.', 'metaform map layer layer=<overlay>')
    keys = [_key(project, drawn, layer)] if layer else [str(one['key']) for one in _overlays(drawn)]
    for key in keys:
        if key == WANTS:
            continue
        for one in cast(list[dict[str, Any]], project_store.overlay_records(project, key) or []):
            if one.get('record') == ident:
                return key, one
    raise Stop(f'No record {ident} is held in {project}\'s overlays; it may have been removed.', 'metaform map layers')


def _written(project: str, key: str, path: str, ident: str | None) -> dict[str, Any]:
    """The record as it is stored now: the one named, or the last at its element."""
    held = cast(list[dict[str, Any]], cast(dict[str, Any], project_store.run({path: {key: {}}}).get(path) or {})
                .get(key) or [])
    found = next((one for one in held if one.get('record') == ident), None) if ident else (held[-1] if held else None)
    return {'layer': key, 'node': _local(project, path), **(found or {})}


def knowledge(ctx: Context, project: str, op: str, notices: list[Notice]) -> Any:
    """`map knowledge` on a project held in the project store: its layers are overlays and its items records."""
    if op in NO_OPERATION:
        raise _no_place(project, f'op={op} has no place: {NO_OPERATION[op]}')
    nouns = ctx.nouns
    drawn = _drawn(project)
    name = _clean(nouns.get('layer'))
    if op == 'create':
        return _create(ctx, project, drawn, name)
    if op in ('add-item', 'add-property'):
        given = [one for one in NO_ITEM if nouns.get(one)]
        if given:
            raise _no_place(project, f'a record has no {", ".join(given)}: the store neither orders, shows apart nor '
                                     'tasks a record. Leave them out; a task is a ticket, metaform map work op=add.')
        if not name:
            raise _no_place(project, 'an overlay is named: give the layer the record goes in with layer=.')
        key = _key(project, drawn, name)
        if key == WANTS:
            raise _no_place(project, "a want is written with the project tool's add, or with metaform map refine.")
        at = _address(project, drawn, str(nouns['node' if op == 'add-item' else 'element']), 'metaform help map '
                      'knowledge')
        fields = _fields(ctx, project, drawn, notices)
        path = f'{project}.{at}'
        _done(project_store.run({'add': {path: {key: [fields]}}}))
        return _written(project, key, path, None)
    ident = str(nouns['id'] if op != 'add-ref' else nouns['owner'])
    key, record = _find(project, drawn, ident, name or None)
    path = str(record['element'])
    named = {'position': record['position'], 'record': record['record'], 'revision': record['revision']}
    if op == 'remove':
        _done(project_store.run({'delete': {path: {key: [ident]}}}))
        return {'layer': key, 'node': _local(project, path), 'record': ident, 'removed': True}
    if op == 'add-ref':
        ref_key, value = str(nouns.get('key') or ''), nouns.get('value')
        ref = _ref(project, [[ref_key, value]])
        if record.get('ref') not in (None, ref):
            raise _no_place(project, f'a record holds one ref, and {ident} holds {record["ref"]} already: change it '
                                     'with op=edit refs=\'[["path", "<path>"]]\'.')
        if record.get('ref') != ref:
            _done(project_store.run({'update': {path: {key: [{**named, 'ref': ref}]}}}))
        return _written(project, key, path, ident)
    other = sorted(one for one in nouns if one in ('address', 'receiver', 'elements', 'type', 'purpose', 'ef', 'ifd',
                                                   'name', 'name_length', 'role', 'element', *NO_ITEM))
    if other:
        raise _no_place(project, f'a record has no {", ".join(other)}: edit changes its value, extra, link or refs; '
                                 'an element or want is refined with metaform map refine.')
    fields = _fields(ctx, project, drawn, notices)
    if not fields:
        raise Stop('edit changes value, extra, link or refs; none was given.', 'metaform help map knowledge')
    _done(project_store.run({'update': {path: {key: [{**named, **fields}]}}}))
    return _written(project, key, path, ident)


def _create(ctx: Context, project: str, drawn: dict[str, Any], name: str) -> Any:
    """A knowledge layer as an overlay defined beneath the project's overlay root: its variable the description, and
    its fields, with value and link, the fields of its records."""
    nouns = ctx.nouns
    given = [one for one in NO_CREATE if nouns.get(one)]
    if given:
        raise _no_place(project, f'an overlay keeps no {", ".join(given)}: its definition holds a description, an '
                                 'instruction and its fields. Leave them out.')
    if nouns.get('hideable'):
        raise _no_place(project, 'an overlay cannot be hidden. Leave hideable out.')
    if 'mutable' in nouns and not nouns['mutable']:
        raise _no_place(project, 'every overlay record changes in place by its record id, so none is kept '
                                 'immutable. Leave mutable out.')
    variable = _clean(nouns.get('variable'))
    if not variable:
        raise Stop(f'{_in(project)} a layer is an overlay, and its definition needs a description: give the one '
                   'question the layer answers with variable=.', 'metaform help map knowledge')
    steps = '.'.join(step.lower().replace('-', '_') for step in name.split('.'))
    path = f'{project}.overlay.{steps}'
    if any(one['address'] == path for one in _overlays(drawn)):
        raise Stop(f'{name} is an overlay of {project} already.', f'metaform map layer layer={name}')
    definition: dict[str, Any] = {'description': variable, 'instruction': INSTRUCTION}
    for field in cast(list[Any], nouns.get('fields') or []):
        definition[str(field)] = {'type': 'text', 'rule': f'The {field} of the item, as the layer\'s question asks.',
                                  'example': f'The {field} this layer records here.', 'optional': True}
    definition.setdefault('value', {'type': 'text', 'rule': 'The value the layer records at this element.',
                                    'example': 'C++17, built with CMake.', 'optional': True})
    definition.setdefault('link', {'type': 'address', 'rule': 'An element of the map this record links to.',
                                   'example': f'{project}.code.engine', 'optional': True})
    _done(project_store.run({'add': {path: definition}}))
    key = next(str(one['key']) for one in _overlays(_drawn(project)) if one['address'] == path)
    return {'layer': key, 'overlay': _local(project, path), 'description': variable,
            'fields': [one for one in definition if one not in ('description', 'instruction')]}
