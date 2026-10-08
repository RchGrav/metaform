"""intake: the intake served by name, recorded one object at a time as it is reasoned, BASE-039.

A subagent reads `intake prompt` and records the map as it works: it starts the
intake, records each element and each join in its own call, anneals a part as a
join one level deeper, received by the element it is part of, reads the recorded
map back with `intake show`, whole or one receiver at a time, corrects it by
recording again and with `intake remove`, and ends with `intake finish`. The
intake layer is building until then: context reads do not see it, and the web
GUI follows it live.

The map is Rich's shape, 2026-10-04: an element is its namespace_address,
name_length, name and role; a join is its type, purpose, ef and ifd, held by its
receiver, holding the elements that serve it. An element's refs go in the
sources layer while intake_sources is on. The agent names what it reasoned,
never what the store keeps: an element by its namespace_address and a join by
its receiver and an element it holds; no id reaches the agent. Nothing is
refused for its content: what does not fit is stored as given and named in a
notice, BASE-044. The report and process feedback are saved at the finish,
BASE-045.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any, Literal, cast

from metaform import home, prompt_files, settings
from metaform.data import Element, GraphPage, Item, Join, Layer, Node, Notice, Store, StoreError
from metaform.module import Context, Module, Noun, Resource, Status, Stop, Verb, save_report

from .schema import ELEMENTS, IFD, NAME_LENGTH, REFS, ROLE

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False

RESOURCE = resources.files(__name__) / 'resources' / 'Intake_2.1.md'  # Intake 2.1, the served intake, Rich 2026-10-03
SHAPE = resources.files(__name__) / 'resources' / 'metaform.axiom'  # the metaform's shape, Rich 2026-10-04
VARIABLE = ('The functional map of the artifact: its elements, and each receiver\'s purpose served by a provider\'s '
            'encounter function.')
TARGET = re.compile(r'<target\b[^>]*>')

def _field_words(group: str) -> dict[str, str]:
    """The definition of each field of `group`, element or join, written once in this module's prompts.xml under
    <fields>, MCP-031. The Canonical Intake is not parsed for them: it is the instruction, served as written, and a
    field's definition lives in one place that every tool taking the field shows."""
    import xml.etree.ElementTree as ET
    path = resources.files(__name__) / 'resources' / 'prompts.xml'
    found = ET.fromstring(path.read_text(encoding='utf-8')).find(f'fields/{group}')
    return {} if found is None else {child.tag: (child.text or '').strip() for child in found}


ELEMENT_WORDS, JOIN_WORDS = _field_words('element'), _field_words('join')

settings.text('intake_file', '', help='An intake file to serve instead of the Canonical Intake. Empty means the '
                                      'Canonical Intake.')


def _escape(text: str) -> str:
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def _fill(tag: str, name: str, value: str) -> str:
    attribute = re.compile(rf'(\s{name}=")[^"]*(")')
    if attribute.search(tag):
        return attribute.sub(lambda match: match.group(1) + _escape(value) + match.group(2), tag, count=1)
    return tag.replace('<target', f'<target {name}="{_escape(value)}"', 1)


def served(ctx: Context, asked: str = '') -> str:
    """The intake text exactly as stored, with its prompt slot filled, and its target where an intake file has one, and
    nothing beside it, BASE-039: the intake is the instruction, and what is added to it competes with it."""
    store = ctx.require_store()
    chosen = ctx.setting('intake_file')
    source: Any = Path(chosen) if chosen else RESOURCE
    try:
        text = source.read_text(encoding='utf-8')
    except OSError:
        raise Stop(f'No intake file at {source}.', 'metaform unset --intake-file') from None
    record = store.project()
    match = TARGET.search(text)
    if match is not None:
        tag = _fill(_fill(match.group(0), 'type', record.target_type), 'value', record.target_value)
        text = text[:match.start()] + tag + text[match.end():]
    text = text.replace('{project_id}', record.project_id)
    # What the person asked for, a target or a task; nothing asked leaves it empty, which the intake reads as this
    # project, BASE-039. Intake 2.1 is not XML, so it gets the words exactly as written; an XML intake file, which
    # intake_file can name, gets them escaped as an attribute value is.
    text = text.replace('{prompt}', _escape(asked) if source.name.lower().endswith('.xml') else asked, 1)
    ignored = home.ignore_patterns(record.path)
    if ignored:  # the one thing added after the intake: what it must not read, from .metaform/ignore.txt
        text = (text.rstrip('\n') + '\n\nDo not read these paths; they are not the project ('
                + home.IGNORE_FILE + '):\n' + '\n'.join(ignored) + '\n')
    return text


def prompt(ctx: Context) -> str:
    return served(ctx, ctx.nouns.get('text') or '')


def schema(ctx: Context) -> str:
    """The shape of the metaform, served as written, Rich 2026-10-04: "add this as a tool maybe just to give this
    shape"."""
    return SHAPE.read_text(encoding='utf-8')




# Recording, one object per call ------------------------------------------------------------------------------

Notices = list[dict[str, str]]
ADDRESS = 'namespace_address'  # the element's address, named as in Rich's shape, MAP-040
SOURCES = 'sources'  # the layer an element's refs go in, Rich 2026-10-04
ID = re.compile(r'\b[0-9a-f]{32}\b')

settings.boolean('intake_sources', True, label='Intake sources layer',
                 help='Whether the intake writes the refs it is given into a layer named sources. Off, refs given to '
                      'the intake are not recorded.')


class Recording:
    """The intake being recorded: the store of its metaform, its building layer, and that metaform."""

    def __init__(self, store: Store, layer: Layer, metaform: str, active: bool) -> None:
        self.store, self.layer, self.metaform, self.active = store, layer, metaform, active


def _stamp() -> str:
    return datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')


def _note(notices: Notices, result: Any, words: dict[str, str] | None = None) -> None:
    """A store result's notices, each named by the field it is about; the element's address by its tool name. An id
    the store names is said in the agent's words, `words`, as an address or a join."""
    for notice in cast(tuple[Notice, ...], getattr(result, 'notices', ()) or ()):
        message = ID.sub(lambda match: (words or {}).get(match.group(0), match.group(0)), notice.message)
        where = {'address': ADDRESS}.get(notice.where, notice.where)
        notices.append({'where': where, 'message': message})


def _said(held: Join) -> str:
    first = held.elements[0].address if held.elements else None
    return f'the join of {held.receiver_address} holding {first}'


def _words(store: Store, layer: Layer | None) -> dict[str, str]:
    """What the agent calls each thing of the intake being recorded, by the id the store names it with."""
    if layer is None:
        return {}
    graph = store.layer_graph(layer.name)
    words = {placed.element.id: placed.element.address for placed in graph.elements}
    for held in graph.joins:
        words[held.id] = _said(held)
        words.update({each.element_id: str(each.address) for each in held.elements if each.address})
    return words


def _joins_holding(store: Store, layer: Layer | None, receiver: Any, elements: list[Any]) -> list[Join]:
    """The joins of `receiver` in the intake being recorded, or in the metaform when none is, that hold any of
    `elements`."""
    owner = store.element(str(receiver), raw=True)
    if owner is None:
        return []
    return [held for held in store.joins(owner.id, raw=True, limit=0).results
            if (layer is None or held.layer_id == layer.id)
            and any(each.address in elements for each in held.elements)]


def _text(ctx: Context, name: str, notices: Notices) -> str | None:
    value = ctx.nouns.get(name)
    if value is None or isinstance(value, str):
        return value
    notices.append({'where': name, 'message': f'{name} is not text; it was stored as its JSON text.'})
    return json.dumps(value, ensure_ascii=False)


def _given(ctx: Context, name: str, notices: Notices) -> str | None:
    """A report or feedback. On the command line a value that names a file is read from the file and `-` from
    standard input, as `metaform feedback` reads them, BASE-045; a tool is handed the text and opens no path."""
    value = _text(ctx, name, notices)
    if value is None or ctx.surface != 'cli':
        return value
    if value == '-':
        return sys.stdin.read()
    path = Path(value) if Path(value).is_absolute() else ctx.folder / value
    try:
        if path.is_file():
            return path.read_bytes().decode('utf-8')
    except (OSError, ValueError):
        return value
    return value


def _json(ctx: Context, name: str) -> tuple[Any, bool]:
    """A JSON field: the value over MCP, its text parsed on the command line. False when the text does not parse."""
    value = ctx.nouns.get(name)
    if isinstance(value, str):
        try:
            return json.loads(value), True
        except ValueError:
            return value, False
    return value, True


def _list(ctx: Context, name: str) -> list[Any] | None:
    """A list field: a JSON list, or one value given alone as a list of one."""
    value, parsed = _json(ctx, name)
    if value is None:
        return None
    return cast(list[Any], value) if parsed and isinstance(value, list) else [value]


def _whole(value: Any) -> Any:
    """name_length as a number when its text is one; anything else goes to the store as given, which names it."""
    return int(value) if isinstance(value, str) and value.isdigit() else value


def _building(store: Store) -> Recording | None:
    """The intake being recorded for this project, in whichever of its metaforms it is building."""
    page = store.intake_recording().results
    if not page:
        return None
    found = page[0]
    return Recording(Store(store.project_id, base=found.base_id), found.layer, found.base, found.active)


def _open(ctx: Context, store: Store, notices: Notices) -> Recording:
    """A new building intake layer: in the active metaform, or in a new one when that one has an intake."""
    active = store.active_base()
    target, name, is_active = store, active.name if active is not None else 'main', True
    if active is not None and store.has_intake():
        fresh = store.add_base(f'intake-{_stamp()}', activate=False)
        target, name, is_active = Store(store.project_id, base=fresh.id), fresh.name, False
        notices.append({'where': 'base', 'message': f'This project already has an intake in base '
                                                        f'{active.name}. This one is recorded in the new base '
                                                        f'{name}, which becomes the active one when the intake '
                                                        'finishes; the earlier one is kept whole.'})
    # No copy of the intake text is kept: the intake's purpose never changes, STORE-016.
    provenance = {'module': 'intake', 'workflow': 'canonical-intake', 'prompt': None,
                  'model': ctx.nouns.get('model'), 'role': ctx.nouns.get('role')}
    layer = target.layer('base', 'intake', VARIABLE, kind='intake', mutable=False, hideable=False,
                         provenance=provenance)
    return Recording(target, layer, name, is_active)


def _recording(ctx: Context, notices: Notices) -> Recording:
    """The intake being recorded; a record sent before any start starts one, and says so."""
    store = ctx.require_store()
    found = _building(store)
    if found is not None:
        return found
    made = _open(ctx, store, notices)
    notices.append({'where': 'intake', 'message': f'No intake was being recorded, so this call started one: layer '
                                                  f'{made.layer.name} in metaform {made.metaform}.'})
    return made


def start(ctx: Context) -> Any:
    """Open the intake layer the records go into, or resume the one already being recorded."""
    store = ctx.require_store()
    notices: Notices = []
    found = _building(store)
    if found is not None:
        notices.append({'where': 'intake', 'message': f'An intake is already being recorded in layer '
                                                      f'{found.layer.name} of metaform {found.metaform}; this call '
                                                      'resumes it. intake show reads back what it holds.'})
        # What the layer lacks of its provenance is filled in; what it holds is kept, LAYER-010.
        _note(notices, found.store.complete(found.layer.name, {name: ctx.nouns.get(name) for name in ('model', 'role')}))
    else:
        found = _open(ctx, store, notices)
    return {'layer': found.layer.name, 'project': store.project_id, 'base': found.metaform, 'notices': notices}


def _described(element: Element) -> bool:
    """Whether an element was described with intake element, not only named in a join."""
    return element.role is not None or element.name_length is not None


def _sources(ctx: Context, rec: Recording, element_id: str, address: str, refs: list[Any], notices: Notices) -> None:
    """The refs given with an element, written as its one item of the sources layer, replacing what that item held,
    Rich 2026-10-04: "if you want to have refs you add a sources layer". Off with intake_sources, nothing is written."""
    if not ctx.setting('intake_sources'):
        notices.append({'where': 'refs', 'message': 'intake_sources is off, so the refs were not recorded.'})
        return
    store = rec.store
    store.layer(SOURCES, 'intake', 'refs', kind='layer', mutable=True, hideable=True, ready=True)  # read at once
    held = [item for item in store.layer_items(SOURCES, Node('element', element_id), limit=0).results
            if isinstance(item, Item)]
    if held:
        _note(notices, store.edit(held[0].id, {'refs': refs}))
        for extra in held[1:]:
            _note(notices, store.remove(extra.id))
    else:
        _note(notices, store.add_item(SOURCES, Node('element', element_id), address, refs=refs))


def element(ctx: Context) -> Any:
    """Record one element, or record it again: the fields given replace the ones it had, the rest are kept. An element
    is its namespace_address, name_length, name and role, Rich's shape; its refs go in the sources layer."""
    notices: Notices = []
    rec = _recording(ctx, notices)
    address = ctx.nouns[ADDRESS]
    given = {'name_length': _whole(ctx.nouns.get('name_length')), 'name': ctx.nouns.get('name'),
             'role': ctx.nouns.get('role')}
    current = rec.store.element(address, raw=True)
    element_id: str | None
    if current is not None and current.layer_id == rec.layer.id:
        changes = {key: value for key, value in given.items() if value is not None}
        if changes:
            _note(notices, rec.store.edit(current.id, changes))
        element_id = current.id
    else:
        for field in ('role', 'name'):
            if given[field] is None:
                notices.append({'where': field, 'message': f'{field} is missing; stored empty.'})
        made = rec.store.add_element(rec.layer.name, address, **given)
        _note(notices, made)
        element_id = getattr(made, 'id', None)
    refs = _list(ctx, 'refs')
    if refs is not None and element_id is not None:
        _sources(ctx, rec, element_id, address, refs, notices)
    _condition(ctx, rec, 'element', element_id, notices)
    return {ADDRESS: address, 'layer': rec.layer.name, 'notices': notices}


def _condition(ctx: Context, rec: Recording, kind: Literal['element', 'join'], thing: str | None,
               notices: Notices) -> None:
    """A condition given with what was recorded is an open work record at it, with its note, MAP-046: the missing,
    broken and exclude marks of the intake, apart from the map. A note alone is no finding and opens nothing."""
    if ctx.nouns.get('condition') == 'exclude':  # not a judgment the intake makes: the person's ignore list
        notices.append({'where': 'condition', 'message': f'exclude is the ignore list: {home.IGNORE_FILE}'})
        return
    if thing is None or not ctx.nouns.get('condition'):  # none or empty: no finding, MAP-046
        if thing is not None and ctx.nouns.get('note'):
            notices.append({'where': 'note', 'message': 'A note goes with a condition, missing or broken; '
                                                        'without one it was not recorded.'})
        return
    # Intake 2.1 says missing for a part that is not built yet; the record holds it as the stage unbuilt.
    stage = {'missing': 'unbuilt'}.get(str(ctx.nouns['condition']), str(ctx.nouns['condition']))
    _note(notices, rec.store.add_work(Node(kind, thing), stage, note=ctx.nouns.get('note')))


JOIN_FIELDS = ('purpose', 'ef', 'ifd')


def join(ctx: Context) -> Any:
    """Record one join, Rich's shape: the receiver's purpose, the ef and the ifd, holding the elements that serve it.
    A join of the receiver that already holds one of the elements is that join: the fields given replace its own, and
    the elements given that it does not hold are added to it."""
    notices: Notices = []
    rec = _recording(ctx, notices)
    receiver = ctx.nouns['receiver']
    elements = _list(ctx, 'elements') or []
    result = {'receiver': receiver, 'elements': elements, 'layer': rec.layer.name, 'notices': notices}
    if not elements:
        notices.append({'where': 'elements', 'message': 'elements is missing; a join holds the elements that serve '
                                                        'its purpose. A join takes receiver, elements, purpose, ef '
                                                        'and ifd. Nothing was recorded.'})
        return result
    words = _words(rec.store, rec.layer)
    found = _joins_holding(rec.store, rec.layer, receiver, elements)
    if len(found) > 1:
        notices.append({'where': 'elements', 'message': f'{receiver} has {len(found)} joins holding these elements, '
                                                        f'with the purposes {"; ".join(repr(held.purpose) for held in found)}; '
                                                        'name elements that only one of them holds. Nothing was '
                                                        'changed.'})
        return result
    if found:
        held = found[0]
        changes: dict[str, Any] = {key: ctx.nouns[key] for key in JOIN_FIELDS if ctx.nouns.get(key) is not None}
        holding = [each.address for each in held.elements]
        added = [address for address in elements if address not in holding]
        if added:
            changes['elements'] = [*holding, *added]
        if changes:
            _note(notices, rec.store.edit(held.id, changes), words)
        _condition(ctx, rec, 'join', held.id, notices)
        return result
    for field in JOIN_FIELDS:
        if ctx.nouns.get(field) is None:
            notices.append({'where': field, 'message': f'{field} is missing; stored empty.'})
    made = rec.store.add_join(rec.layer.name, receiver, elements,
                              **{field: ctx.nouns.get(field) for field in JOIN_FIELDS})
    _note(notices, made, words)
    _condition(ctx, rec, 'join', getattr(made, 'id', None), notices)
    return result


FINISHED = ('The intake is finished, so nothing was changed. The metaform changes by refining, with metaform map '
            'refine, which keeps every version, LAYER-025.')
NOTHING = 'No intake is being recorded. intake start begins one.'


def _element_entry(found: Element) -> dict[str, Any]:
    return {ADDRESS: found.address, 'short_name': found.short_name, 'name_length': found.name_length,
            'name': found.name, 'role': found.role}


def _join_entry(held: Join) -> dict[str, Any]:
    return {'receiver': held.receiver_address, 'type': held.type, 'purpose': held.purpose, 'ef': held.ef,
            'ifd': held.ifd, 'elements': [each.address for each in held.elements]}


def _findings(store: Store, elements: list[Element], joins: list[Join]) -> dict[str, dict[str, Any]]:
    """The open condition and note on each recorded element and join, by id, so an agent reads its marks back."""
    ids = {element.id for element in elements} | {held.id for held in joins}
    return {row.id: {'condition': row.condition, 'note': row.note}
            for row in store.work(open=True, limit=0).results if row.id in ids}


def _refs(store: Store, found: Element) -> list[dict[str, str]]:
    """An element's refs, the items of the sources layer at it; none when there is no sources layer."""
    try:
        held = store.layer_items(SOURCES, Node('element', found.id), limit=0).results
    except StoreError:
        return []
    return [{'key': ref.key, 'value': ref.value} for item in held if isinstance(item, Item) for ref in item.refs]


def _map(elements: list[Element], joins: list[Join], store: Store | None = None) -> dict[str, Any]:
    """The recorded map in the agent's words: every element by its address with its refs, every join by its receiver
    with the elements it holds, each with its open condition and note, and the addresses never described."""
    marks = _findings(store, elements, joins) if store is not None else {}
    listed: list[dict[str, Any]] = []
    for found in elements:
        entry = _element_entry(found)
        if store is not None:
            entry['refs'] = _refs(store, found)
        listed.append({**entry, **marks.get(found.id, {})})
    roots = [found.address for found in elements if found.role == 'AUE']
    joined = {held.receiver_address for held in joins} | {each.address for held in joins for each in held.elements}

    def under(address: str) -> bool:
        return any(address == root or address.startswith(root + '.') for root in roots)

    return {'elements': listed,
            'joins': [{**_join_entry(held), **marks.get(held.id, {})} for held in joins],
            'root': roots[0] if len(roots) == 1 else roots,
            'disconnected': [found.address for found in elements if not under(found.address)
                             and found.address not in joined],
            'undescribed': [found.address for found in elements if not _described(found)]}


def _recorded(store: Store, layer: Layer) -> tuple[list[Element], list[Join]]:
    """What this intake recorded: its elements, with every element its joins hold that it wrote, and its joins."""
    graph: GraphPage = store.layer_graph(layer.name)
    listed = {placed.element.id: placed.element for placed in graph.elements}
    return sorted(listed.values(), key=lambda found: found.address), list(graph.joins)


def show(ctx: Context) -> Any:
    """The intake being recorded, whole or one receiver's joins and the elements they hold: to read back, proof and
    correct before finishing, without reading the whole map at once."""
    store = ctx.require_store()
    found = _building(store)
    if found is None:
        return {'layer': None, 'project': store.project_id, 'base': None, 'elements': [], 'joins': [],
                'root': None, 'disconnected': [], 'undescribed': [],
                'notices': [{'where': 'intake', 'message': NOTHING}]}
    elements, joins = _recorded(found.store, found.layer)
    receiver = ctx.nouns.get('receiver')
    notices: Notices = []
    if receiver:
        joins = [held for held in joins if held.receiver_address == receiver]
        named = {receiver, *(each.address for held in joins for each in held.elements)}
        elements = [each for each in elements if each.address in named]
        if not elements:
            notices.append({'where': 'receiver', 'message': f'{receiver} is not an element of this intake; nothing '
                                                            'is recorded under it.'})
    return {'layer': found.layer.name, 'project': store.project_id, 'base': found.metaform,
            **_map(elements, joins, found.store), 'notices': notices}


NAMED_BY = ('Name what to remove by its addresses: namespace_address for an element, receiver and provider for the '
            'join of that receiver holding that element, and all three to take the element at namespace_address out '
            'of that join.')


def remove(ctx: Context) -> Any:
    """Remove one recorded element, one join, or one element from a join, while the intake is being recorded."""
    store = ctx.require_store()
    found = _building(store)
    named = {key: ctx.nouns[key] for key in ('receiver', 'provider', ADDRESS) if ctx.nouns.get(key) is not None}
    if found is None:
        said = FINISHED if store.has_intake() else NOTHING
        return {**named, 'layer': None, 'notices': [{'where': 'intake', 'message': said}]}
    notices: Notices = []
    words = _words(found.store, found.layer)
    if 'receiver' in named and 'provider' in named:
        held = _joins_holding(found.store, found.layer, named['receiver'], [named['provider']])
        if len(held) != 1:
            notices.append({'where': 'provider', 'message': f'{named["receiver"]} has {len(held)} joins holding '
                                                            f'{named["provider"]}; nothing was changed.'})
        elif ADDRESS in named:
            kept = [each.address for each in held[0].elements if each.address != named[ADDRESS]]
            if len(kept) == len(held[0].elements):
                notices.append({'where': ADDRESS, 'message': f'{_said(held[0])} does not hold {named[ADDRESS]}; '
                                                             'nothing was changed.'})
            else:
                _note(notices, found.store.edit(held[0].id, {'elements': kept}), words)
        else:
            _note(notices, found.store.remove(held[0].id), words)
    elif ADDRESS in named and 'receiver' not in named and 'provider' not in named:
        current = found.store.element(named[ADDRESS], raw=True)
        if current is None:
            notices.append({'where': ADDRESS, 'message': f'{named[ADDRESS]} is not an element; nothing was changed.'})
        else:
            _note(notices, found.store.remove(current.id), words)
    else:
        notices.append({'where': ADDRESS, 'message': NAMED_BY})
    return {**named, 'layer': found.layer.name, 'notices': notices}


def finish(ctx: Context) -> Any:
    """Finish the intake: its layer becomes the metaform's intake, seen by every read, and cannot change in place."""
    store = ctx.require_store()
    notices: Notices = []
    report = _given(ctx, 'report', notices)
    feedback = _given(ctx, 'feedback', notices)
    found = _building(store)
    if found is None:
        return {'layer': None, 'project': store.project_id, 'base': None, 'elements': 0, 'joins': 0, 'work': 0,
                'notices': notices + [{'where': 'intake', 'message': 'No intake is being recorded; there is nothing '
                                                                     'to finish.'}]}
    elements, joins = _recorded(found.store, found.layer)
    undescribed = [element.address for element in elements if not _described(element)]
    if undescribed:
        notices.append({'where': 'undescribed', 'message': f'{", ".join(undescribed)} '
                                                           f'{"was" if len(undescribed) == 1 else "were"} named in a '
                                                           'join but never described with intake element; stored '
                                                           'without a role or a name_length.'})
    _note(notices, found.store.finish(found.layer.name))
    if not found.active:
        previous = store.active_base()
        store.activate_base(found.metaform)
        if previous is not None:
            notices.append({'where': 'base', 'message': f'This intake was stored as the new active base '
                                                        f'{found.metaform}; the earlier one, {previous.name}, is '
                                                        'kept whole. To switch back: metaform map activate '
                                                        f'{previous.name}'})
    for kind, text in (('report', report), ('feedback', feedback)):
        if text is not None:
            save_report(store.project_id, found.layer.id, kind, text, store=found.store,
                        layer=found.layer.id)
    # The open work records on what this intake recorded, MAP-046: the condition of an object is apart from the map.
    recorded_ids = {element.id for element in elements} | {held.id for held in joins}
    work = sum(1 for row in found.store.work(open=True, limit=0).results if row.node_id in recorded_ids)
    return {'layer': found.layer.name, 'project': store.project_id, 'base': found.metaform,
            'elements': len(elements), 'joins': len(joins), 'work': work, 'notices': notices}


def status_verb(ctx: Context) -> str:
    store = ctx.require_store()
    found = _building(store)
    lines: list[str] = []
    if store.has_intake():
        latest = store.layers(kind='intake', limit=0).results[-1]
        lines.append(f'This project has an intake. Latest intake layer: {latest.name}')
    if found is not None:
        lines.append(f'An intake is being recorded in layer {found.layer.name} of metaform {found.metaform}.')
    if not lines:
        lines.append('No intake yet. Read the instructions with metaform intake prompt.')
    return '\n'.join(lines) + '\n'


def status(ctx: Context) -> Status:
    if ctx.store is None:
        return Status()
    found = _building(ctx.store)
    recording = (f'Intake: being recorded in layer {found.layer.name} of metaform {found.metaform}',) \
        if found is not None else ()
    # The instructions agents read name an intake started and not finished, or else a project with no intake, MCP-009.
    unfinished = prompt_files.required(resources.files(__name__), 'unfinished') if found is not None else None
    if ctx.store.has_intake():
        return Status(lines=('Intake: complete', *recording), instruction=unfinished)
    if found is not None:
        return Status(lines=recording, instruction=unfinished)
    return Status(lines=('Intake: none yet',), instruction=prompt_files.required(resources.files(__name__), 'no_intake'))


E, J = ELEMENT_WORDS.get, JOIN_WORDS.get
CONDITION = (Noun('condition', E('condition', ''), required=False,
                  schema={'type': 'string', 'enum': ['missing', 'broken', 'unbuilt', 'under-construction', 'built']}),
             Noun('note', E('note', ''), required=False))

MODULE = Module(
    id='intake',
    summary='Serve the intake and record its result as it is reasoned.',
    purpose='Serves the intake instructions, records the intake as it is reasoned, and tracks whether this project '
            'has an intake. The intake is agent work: a subagent reads its instructions with the command prompt and '
            'follows them. Details: metaform help intake.',
    details='The intake text is served as stored, with its prompt slot filled. The intake is recorded as it is '
            "reasoned, one element or join per call, in Rich's shape: an element is its namespace_address, "
            'name_length, name and role; a join is the receiver\'s purpose, the ef and the ifd, holding the elements '
            'that serve it. An element\'s refs go in the sources layer while intake_sources is on. It is read back '
            'with show, whole or one receiver at a time, and corrected by recording again and with remove. No other '
            'read sees it until finish; after finish the metaform changes by refining, metaform map refine, in the '
            'same layer. Nothing is refused for its content: what does not fit is stored as given and named in a '
            'notice.',
    verbs=(
        Verb('prompt', prompt, 'The intake instructions for this project.',
             nouns=(Noun('text', 'path to the target for the intake process; leaving this blank means this project',
                         required=False),)),
        Verb('schema', schema, 'The shape of the metaform: the namespace roots, the upstream and downstream links, '
                               'and the element and join forms the intake records.'),
        Verb('start', start, 'Resume the intake being recorded, or start a fresh one. If the active metaform already '
                            'has an intake, creates a separate intake-<UTC timestamp> metaform, keeping the earlier '
                            'one untouched. Returns its name; the existing web GUI follows it live.',
             nouns=(Noun('model', 'The model that performs the intake.', required=False),
                    Noun('role', 'The role of the agent that performs it.', required=False))),
        Verb('element', element, 'Record one element, or record it again; the fields given replace the ones it had.',
             nouns=(Noun(ADDRESS, E(ADDRESS, '')),
                    Noun('name_length', E('name_length', ''), required=False, schema=NAME_LENGTH),
                    Noun('name', E('name', ''), required=False),
                    Noun('role', E('role', ''), required=False, schema=ROLE),
                    Noun('refs', E('refs', ''), required=False, schema=REFS),
                    *CONDITION)),
        Verb('join', join, "Record one join: the receiver's purpose served by the elements it holds. Recorded again "
                           'with an element it holds, the fields given replace its own and new elements are added. An '
                           'annealed part is a join one level deeper: record it with the element it is part of as the '
                           'receiver.',
             nouns=(Noun('receiver', J('receiver', '')),
                    Noun('elements', J('elements', ''), schema=ELEMENTS),
                    Noun('purpose', J('purpose', ''), required=False),
                    Noun('ef', J('ef', ''), required=False),
                    Noun('ifd', J('ifd', ''), required=False, schema=IFD),
                    *CONDITION)),
        Verb('show', show, 'The intake being recorded, whole or one receiver at a time.',
             nouns=(Noun('receiver', J('receiver', ''), required=False),)),
        Verb('remove', remove, 'Remove one recorded element, one join, or one element from a join, named by addresses.',
             nouns=(Noun('receiver', J('receiver', ''), required=False),
                    Noun('provider', J('provider', ''), required=False),
                    Noun(ADDRESS, E(ADDRESS, ''), required=False))),
        Verb('finish', finish, 'Finish and activate the recorded metaform, keeping the earlier one whole. Switch '
                               'back with metaform map activate <previous-name>. After finish the metaform changes '
                               'by refining: metaform map refine.',
             nouns=(Noun('report', 'Your report on the project you examined: broken code, things that need fixing, '
                                   'anything not working or partially working. On the command line a file is read '
                                   'and - is standard input.', required=False),
                    Noun('feedback', 'Feedback on the Metaform process: bad semantics, a tool that did not match its '
                                     'schema, where you got stuck.', required=False))),
        Verb('status', status_verb, 'Whether this project has an intake, and whether one is being recorded.'),
    ),
    status=status,
    resources=(
        Resource('metaform://intake/procedure', 'Intake procedure',
                 'The intake instructions for this project, the procedure an intake follows. Read before intake start.',
                 'prompt'),
        Resource('metaform://intake/schema', 'Intake forms',
                 'The shape of the metaform: the namespace roots, the links, and the element and join forms intake '
                 'element and intake join record.', 'schema'),
    ),
)
