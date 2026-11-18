"""The skill layer: project skills are ordinary knowledge attached to functional nodes."""
from __future__ import annotations

import json
from typing import Any, cast
from urllib.parse import quote, unquote, urlsplit

from metaform import project as project_store
from metaform import prompt_files, skills
from metaform.data import Item, Layer, Node, NodeView, Store, StoreError
from metaform.module import Context, Stop

LAYER = 'skills'
KIND = 'project_agent_skill'


# ---- A project held in the project store: its skills are records of its `skills` overlay at an element, found from
# the element an agent arrives at and the elements its wants name or that want it (review of 2026-11-18, F3).

def _held(store: Store) -> str | None:
    name = project_store.stored_name(store.project_id)
    return name if project_store.holds(name) else None


def _definition() -> dict[str, object]:
    return {
        'description': 'The project agent skills attached at this element: each record is one skill, a SKILL.md and '
                       'its files, offered to an agent that arrives here.',
        'instruction': 'Write a skill with metaform tasks skills op=write node=<element> name=<name> text=<SKILL.md>.',
        'name': {'type': 'text', 'rule': "The skill's name, as its SKILL.md front matter gives it.",
                 'example': 'release-checklist'},
        'summary': {'type': 'text', 'rule': 'When to use it, one line: its front matter description.',
                    'example': 'Use when cutting a release.'},
        'uri': {'type': 'text', 'rule': "The skill's address, skill://skills/<element>/<name>/SKILL.md.",
                'example': 'skill://skills/code.release/release-checklist/SKILL.md'},
        'document': {'type': 'text', 'rule': 'The skill as JSON: its front matter, its files and its resources.',
                     'example': '{"frontmatter": {}, "files": {"SKILL.md": "..."}, "resources": []}'},
    }


def _stored_element(name: str, given: str) -> tuple[str, dict[str, Any]]:
    """An element's address beneath the project and its read, in one call; refused when the map holds no such
    element."""
    address = given.removeprefix('element:')
    answer = {} if address.startswith('join:') else project_store.run({f'{name}.{address}': {}})
    if not answer or answer.get('status') == 'error':
        raise Stop(f'No functional node {given}.', 'map node node=<address>')
    return address, cast(dict[str, Any], answer.get(f'{name}.{address}') or {})


def _stored_scope(name: str, given: str) -> list[str]:
    """The element arrived at, then the elements its wants name and those whose wants name it."""
    address, read = _stored_element(name, given)
    near = [str(one.get('element') or '') for one in cast(list[dict[str, Any]], read.get('wants') or [])]
    near += [str(one) for one in cast(list[Any], read.get('wanted_by') or [])]
    start = len(name) + 1
    return list(dict.fromkeys([address, *(one[start:] if one.startswith(f'{name}.') else one for one in near if one)]))


def _stored_items(name: str, addresses: list[str]) -> list[dict[str, Any]]:
    """The skills held at these elements, in their order: one element's in one selected read, several in one read of
    the overlay."""
    if len(addresses) == 1:
        return [cast(dict[str, Any], one) for one in project_store.overlay_records(name, LAYER, at=addresses[0]) or []]
    order = {f'{name}.{address}': at for at, address in enumerate(addresses)}
    held = [cast(dict[str, Any], one) for one in project_store.overlay_records(name, LAYER) or []
            if str(one['element']) in order]
    return sorted(held, key=lambda one: order[str(one['element'])])


def _stored_metadata(name: str, one: dict[str, Any]) -> dict[str, Any]:
    document = cast(dict[str, Any], json.loads(str(one.get('document') or '{}')))
    return {'id': str(one['record']), 'name': str(one.get('name') or ''),
            'description': str(one.get('summary') or ''), 'node': str(one['element'])[len(name) + 1:],
            'uri': str(one.get('uri') or ''), 'frontmatter': document.get('frontmatter') or {},
            'resources': document.get('resources') or []}


def _stored_read(name: str, skill: str, arrival: str | None) -> dict[str, Any]:
    uri = urlsplit(skill)
    path = uri.path.lstrip('/').split('/')
    if uri.scheme == 'skill' and uri.netloc == LAYER and len(path) == 3:
        arrival = unquote(path[0])
    if arrival is None:
        raise Stop(f'No project agent skill {skill} at the current node.', 'tasks skills node=<functional node>')
    available = _stored_items(name, _stored_scope(name, arrival))
    matches = [one for one in available if skill in (one['record'], one.get('uri'))] or [
        one for one in available if one.get('name') == skill]
    if len(matches) != 1:
        raise Stop(f'No project agent skill {skill} at the current node.' if not matches else
                   f'More than one attached skill is named {skill}; select its item ID.',
                   'tasks skills node=<functional node>')
    one = matches[0]
    metadata = _stored_metadata(name, one)
    files = cast(dict[str, str], json.loads(str(one.get('document') or '{}')).get('files') or {})
    text = str(files.get('SKILL.md') or '')
    attachment = {'layer': LAYER, 'node': metadata['node'], 'item_id': metadata['id']}
    component = prompt_files.component(metadata['uri'], text)
    component.update(origin='graph', source={'kind': 'graph', **attachment})
    return {**metadata, 'text': text, 'files': files, 'component': component, 'attachment': attachment}


def _stored_put(name: str, node: str, skill: str, text: str, description: str, skill_id: str | None,
                files: dict[str, str] | None) -> dict[str, Any]:
    address = _stored_element(name, node)[0]
    uri = f'skill://{LAYER}/{quote(address, safe="")}/{quote(skill, safe="")}/SKILL.md'
    document: dict[str, Any] = skills.document(skill, text, description=description, files=files, uri=uri)
    bodies = cast(dict[str, bytes], document['files'])
    record = {'name': skill, 'summary': str(cast(dict[str, Any], document['frontmatter']).get('description') or ''),
              'uri': uri, 'document': json.dumps({'frontmatter': document['frontmatter'],
                                                  'files': {path: body.decode('utf-8') for path, body in bodies.items()},
                                                  'resources': document['resources']}, ensure_ascii=False)}
    if not any(one.get('key') == LAYER for one in cast(list[dict[str, Any]],
                                                          (project_store.drawn(name) or {}).get('overlays') or [])):
        _stored_done(project_store.run({'add': {f'{name}.overlay.{LAYER}': _definition()}}))
    held = _stored_items(name, [address])
    existing = [one for one in held if (one['record'] == skill_id if skill_id else one.get('name') == skill)]
    if skill_id is not None and not existing:
        raise Stop(f'No project agent skill {skill_id} attached to {node}.', 'tasks skills node=<node>')
    if len(existing) > 1:
        raise Stop(f'More than one attached skill is named {skill}; select its item ID.', 'tasks skills')
    if existing:
        one = existing[0]
        _stored_done(project_store.run({'update': {f'{name}.{address}': {LAYER: [
            {'position': one['position'], 'record': one['record'], **record}]}}}))
        made = one['record']
    else:
        _stored_done(project_store.run({'add': {f'{name}.{address}': {LAYER: [record]}}}))
        made = _stored_items(name, [address])[-1]['record']
    return next(_stored_metadata(name, one) for one in _stored_items(name, [address]) if one['record'] == made)


def _stored_done(answer: dict[str, object]) -> None:
    if answer.get('status') == 'error':
        raise Stop(str(answer.get('message') or 'The skill was not written.'), f'map layer layer={LAYER}')


def _layer(store: Store) -> Layer | None:
    return next((layer for layer in store.layers(limit=0).results if layer.name == LAYER), None)


def _node(store: Store, given: str) -> NodeView:
    target = Node('join', given[5:]) if given.startswith('join:') else Node('element', given)
    found = store.node(target)
    if found is None or found.orphaned:
        raise Stop(f'No functional node {given}.', 'map node node=<address or join:id>')
    return found


def _reference(view: NodeView) -> str:
    return f'join:{view.node.id}' if view.node.kind == 'join' else str(view.address)


def _arrival(ctx: Context, node: str | None) -> str | None:
    given = node if node is not None else ctx.nouns.get('node', ctx.identity.get('METAFORM_NODE'))
    return given if isinstance(given, str) and given else None


def _scope(store: Store, node: str) -> list[Node]:
    view = _node(store, node)
    targets = [view.node]
    if view.node.kind == 'element':
        for direction in ('receiver', 'provider'):
            targets.extend(Node('join', join.id) for join in store.joins(
                str(view.address), direction, limit=0).results)
    else:
        ends = store.join_ends(view.node.id)
        if ends is not None:
            targets.append(_node(store, ends[0]).node)
    return list(dict.fromkeys(targets))


def _value(item: Item) -> dict[str, Any] | None:
    raw: object = item.value
    if item.orphaned or (item.extra or {}).get('kind') != KIND or not isinstance(raw, dict):
        return None
    value = cast(dict[str, Any], raw)
    if item.target.kind == 'element':
        joined: object = value.get('joins')
        if not isinstance(joined, list):
            return None
        entries = cast(list[object], joined)
        if len(entries) != 1:
            return None
        entry = entries[0]
        if not isinstance(entry, dict):
            return None
        value = cast(dict[str, Any], entry)
    frontmatter: object = value.get('frontmatter')
    files: object = value.get('files')
    if (not isinstance(frontmatter, dict) or not isinstance(files, dict)
            or not isinstance(value.get('uri'), str)):
        return None
    header = cast(dict[str, Any], frontmatter)
    bodies = cast(dict[str, Any], files)
    if (not isinstance(header.get('name'), str) or not isinstance(header.get('description'), str)
            or not isinstance(bodies.get('SKILL.md'), str)):
        return None
    return value


def _items(store: Store, targets: list[Node]) -> list[Item]:
    if _layer(store) is None:
        return []
    return [item for target in targets for item in store.layer_items(
        LAYER, target, in_context=True, limit=0).results if isinstance(item, Item) and _value(item) is not None]


def _metadata(store: Store, item: Item) -> dict[str, Any]:
    value = _value(item)
    assert value is not None
    view = _node(store, f'join:{item.target.id}' if item.target.kind == 'join' else item.target.id)
    return {'id': item.id, 'name': value['frontmatter']['name'],
            'description': value['frontmatter']['description'], 'node': _reference(view),
            **{key: value[key] for key in ('uri', 'frontmatter', 'resources')}}


def _by_id(store: Store, skill: str) -> Item | None:
    try:
        history = store.history(skill, limit=0).results
    except StoreError:
        return None
    if not history:
        return None
    latest = history[-1]
    if latest.kind != 'item' or latest.layer != LAYER:
        return None
    fields = latest.fields
    kind, target = fields.get('target_kind'), fields.get('target_id')
    if kind not in ('element', 'join') or not isinstance(target, str):
        return None
    try:
        view = _node(store, f'join:{target}' if kind == 'join' else target)
    except Stop:
        return None
    return next((item for item in _items(store, [view.node]) if item.id == skill), None)


def _uri_arrival(store: Store, skill: str) -> str | None:
    uri = urlsplit(skill)
    path = uri.path.lstrip('/').split('/')
    if (uri.scheme != 'skill' or uri.netloc != LAYER or uri.query or uri.fragment
            or len(path) != 3 or path[-1] != 'SKILL.md'):
        return None
    target = unquote(path[0])
    if store.node(Node('join', target)) is not None:
        return f'join:{target}'
    if store.node(Node('element', target)) is not None:
        return target
    return None


def catalog(ctx: Context, node: str | None = None) -> list[dict[str, Any]]:
    """List only metadata at this arrival node and its actual functional joins."""
    arrival = _arrival(ctx, node)
    if arrival is None:
        return []
    store = ctx.require_store()
    held = _held(store)
    if held is not None:
        return [_stored_metadata(held, one) for one in _stored_items(held, _stored_scope(held, arrival))]
    return [_metadata(store, item) for item in _items(store, _scope(store, arrival))]


def read(ctx: Context, skill: str, node: str | None = None) -> dict[str, Any]:
    """Read one selected body, by exact scoped name or known item ID."""
    store = ctx.require_store()
    held = _held(store)
    if held is not None:
        return _stored_read(held, skill, _arrival(ctx, node))
    arrival = _uri_arrival(store, skill) or _arrival(ctx, node)
    if arrival is None:
        item = _by_id(store, skill)
        matches = [item] if item is not None else []
    else:
        available = _items(store, _scope(store, arrival))
        matches = [item for item in available if item.id == skill or (_value(item) or {}).get('uri') == skill]
        if not matches:
            matches = [item for item in available if (_value(item) or {}).get('frontmatter', {}).get('name') == skill]
    if not matches:
        raise Stop(f'No project agent skill {skill} at the current node.', 'tasks skills node=<functional node>')
    if len(matches) != 1:
        raise Stop(f'More than one attached skill is named {skill}; select its item ID.',
                   'tasks skills node=<functional node>')
    item = matches[0]
    metadata = _metadata(store, item)
    value = _value(item)
    assert value is not None
    attachment = {'layer': LAYER, 'node': metadata['node'], 'item_id': item.id}
    text = str(value['files']['SKILL.md'])
    component = prompt_files.component(str(value['uri']), text)
    component.update(origin='graph', source={'kind': 'graph', **attachment})
    return {**metadata, 'text': text, 'files': value['files'], 'component': component, 'attachment': attachment}


def put(ctx: Context, node: str, name: str, text: str, description: str = '',
        skill_id: str | None = None, files: dict[str, str] | None = None) -> dict[str, Any]:
    """Add or edit one exact skill at an existing node without changing the functional map."""
    if not name.strip() or not text.strip():
        raise Stop('A project agent skill needs its name and full instructions.', 'metaform tasks skills op=write')
    store = ctx.require_store()
    held = _held(store)
    if held is not None:
        return _stored_put(held, node, name, text, description, skill_id, files)
    view = _node(store, node)
    attachment = view.node.id if view.node.kind == 'join' else str(view.address)
    uri = f'skill://{LAYER}/{quote(attachment, safe="")}/{quote(name, safe="")}/SKILL.md'
    document: dict[str, Any] = skills.document(name, text, description=description, files=files, uri=uri)
    bodies = cast(dict[str, bytes], document['files'])
    record: dict[str, Any] = {**{key: document[key] for key in ('uri', 'frontmatter', 'resources')},
              'files': {path: body.decode('utf-8') for path, body in bodies.items()}}
    value: dict[str, Any] = {'joins': [record]} if view.node.kind == 'element' else record
    with store.atomic():
        if _layer(store) is None:
            store.layer(LAYER, 'tasks', 'The skill layer: project skills attached to functional nodes.',
                        mutable=True, hideable=True, tags=('skill',), ready=True)
        if skill_id is not None:
            existing = _by_id(store, skill_id)
            if existing is None or existing.target != view.node:
                raise Stop(f'No project agent skill {skill_id} attached to {node}.', 'tasks skills node=<node>')
        else:
            matches = [item for item in _items(store, [view.node])
                       if (_value(item) or {}).get('frontmatter', {}).get('name') == name]
            if len(matches) > 1:
                raise Stop(f'More than one attached skill is named {name}; select its item ID.', 'tasks skills')
            existing = matches[0] if matches else None
        if existing is None:
            made = store.add_item(LAYER, view.node, value, extra={'kind': KIND})
        else:
            store.edit(existing.id, {'value': value})
            made = next((item for item in _items(store, [view.node]) if item.id == existing.id), None)
        if not isinstance(made, Item) or _value(made) != record:
            raise Stop('The skill layer did not accept the skill update.', f'map layer layer={LAYER}')
        return _metadata(store, made)


def resource(ctx: Context, uri: str) -> dict[str, Any] | None:
    """Resolve one known graph skill as the shared Skills-extension document bundle."""
    if not uri.startswith(f'skill://{LAYER}/') or ctx.project is None:
        return None
    store = ctx.require_store()
    arrival = unquote(urlsplit(uri).path.lstrip('/').split('/')[0]) if _held(store) is not None else \
        _uri_arrival(store, uri)
    if arrival is None:
        return None
    try:
        loaded = read(ctx, uri, node=arrival)
    except Stop:
        return None
    return skills.document(str(loaded['name']), str(loaded['text']),
                           files=cast(dict[str, str], loaded['files']), uri=uri)
