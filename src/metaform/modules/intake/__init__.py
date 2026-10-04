"""intake: the Canonical Intake served by name, recorded one object at a time as it is reasoned, BASE-039.

A subagent reads `intake prompt` and records the map as it works: it starts the
intake, records each element and each purpose in its own call, a part
refining a purpose with `intake subtype`, anneals with `intake absorb`,
reads the recorded map back with `intake show`, whole or one receiver at a
time, corrects it with `intake edit` and `intake remove`, and ends with
`intake finish`. The intake layer is building until then: context reads do not
see it, and the web GUI follows it live.

The agent names what it reasoned, never what the store keeps: an element by its
namespace_address, a purpose by the element that holds it and the element
that serves it, and a part by its address inside that purpose. The code
writes them as elements, joins and subtype joins, and no id reaches the agent;
Rich, 2026-10-02: "joins are a database concept"; "It's, it's just adding a
fucking requirement. Why even use the word join?" Nothing is refused for its
content: what does not fit is stored as given and named in a notice, BASE-044.
The report and process feedback are saved at the finish, BASE-045.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any, Literal, cast

from metaform import prompt_files, settings
from metaform.data import Element, GraphPage, Join, Layer, Node, Notice, Store, Subtype
from metaform.module import Context, Module, Noun, Status, Stop, Verb, save_report

from .schema import EXTRA, NAME_LENGTH, REFS, ROLE, SUBTYPE_ROLE

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False

RESOURCE = resources.files(__name__) / 'resources' / 'Intake_2.1.md'  # Intake 2.1, the served intake, Rich 2026-10-03
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
HELD_WORDS = ELEMENT_WORDS  # the element a subtype join holds is an element

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
    return text


def prompt(ctx: Context) -> str:
    return served(ctx, ctx.nouns.get('text') or '')




# Recording, one object per call ------------------------------------------------------------------------------

Notices = list[dict[str, str]]
JOIN_TEXT = ('purpose', 'ef', 'verb')
IFD = {'type': 'string', 'enum': ['sends', 'receives', 'both']}  # Information Flow Direction, the primary flow of information
SUBTYPE_TEXT = ('ef', 'verb')
ELEMENT_FIELDS = ('name', 'name_length', 'role')  # an element is its address, name_length and role; name, STORE-009
ADDRESS = 'namespace_address'  # the element's address, named as in the Canonical Intake, MAP-040
UNMOVED = ("An element cannot be moved: its namespace_address is its identity, and another address is a different "
           "element, MAP-015. to_address was not applied; record the element at the new address with element and "
           "move its purposes to it with edit to_receiver= or to_provider=.")
ID = re.compile(r'\b[0-9a-f]{32}\b')


class Recording:
    """The intake being recorded: the store of its metaform, its building layer, and that metaform."""

    def __init__(self, store: Store, layer: Layer, metaform: str, active: bool) -> None:
        self.store, self.layer, self.metaform, self.active = store, layer, metaform, active


def _stamp() -> str:
    return datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')


def _note(notices: Notices, result: Any, words: dict[str, str] | None = None) -> None:
    """A store result's notices, each named by the field it is about; the element's address by its tool name. An id
    the store names is said in the agent's words, `words`, as an address or a purpose."""
    for notice in cast(tuple[Notice, ...], getattr(result, 'notices', ()) or ()):
        message = ID.sub(lambda match: (words or {}).get(match.group(0), match.group(0)), notice.message)
        where = {'address': ADDRESS, 'join': 'purpose', 'parent': 'purpose'}.get(notice.where, notice.where)
        notices.append({'where': where, 'message': message})


def _said(receiver: Any, provider: Any) -> str:
    return f'the purpose of {receiver} served by {provider}'


def _words(store: Store, layer: Layer | None) -> dict[str, str]:
    """What the agent calls each thing of the intake being recorded, by the id the store names it with."""
    if layer is None:
        return {}
    graph = store.layer_graph(layer.name)
    words = {placed.element.element_id: placed.element.address for placed in graph.elements}
    for held in graph.joins:
        words[held.join_id] = _said(held.receiver_address, held.provider_address)
        for item in held.subtypes:
            words[item.join_id] = f'{item.address} inside {_said(held.receiver_address, held.provider_address)}'
            words[item.element_id] = str(item.address)
    return words


def _purpose(store: Store, layer: Layer | None, receiver: Any, provider: Any, notices: Notices) -> Join | None:
    """The one purpose of `receiver` served by `provider`, in the intake being recorded, or in the metaform when
    none is. Two that the addresses cannot tell apart are both named, with their purposes, and neither is chosen."""
    owner = store.element(str(receiver), raw=True)
    found = [] if owner is None else [
        held for held in store.joins(owner.element_id, raw=True, limit=0).results
        if held.provider_address == provider and (layer is None or held.layer_id == layer.layer_id)]
    if len(found) == 1:
        return found[0]
    if not found:
        notices.append({'where': 'purpose', 'message': f'{receiver} has no purpose served by {provider}; '
                                                           'nothing was changed.'})
    else:
        purposes = '; '.join(repr(held.purpose) for held in found)
        notices.append({'where': 'purpose', 'message': f'{receiver} has {len(found)} purposes served by '
                                                           f'{provider}, which their addresses cannot tell apart, with '
                                                           f'the purposes {purposes}; nothing was changed.'})
    return None


def _part(store: Store, layer: Layer | None, parent: Join, address: Any, notices: Notices) -> Subtype | None:
    """The part at `address` inside a purpose."""
    found = [item for item in store.subtypes(parent.join_id, raw=True, limit=0).results
             if item.address == address and (layer is None or item.layer_id == layer.layer_id)]
    if len(found) == 1:
        return found[0]
    said = _said(parent.receiver_address, parent.provider_address)
    notices.append({'where': ADDRESS, 'message': f'{said} holds {"no" if not found else len(found)} '
                                                 f'{"part" if len(found) <= 1 else "parts"} at {address}; nothing '
                                                 'was changed.'})
    return None


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


def _refs_and_extra(ctx: Context, notices: Notices) -> tuple[list[Any] | None, dict[str, Any] | None]:
    """The refs as given, for the store to read, and the extra; an extra that is not an object is kept under extra,
    BASE-044. What a ref that is not a key and a value becomes is the store's one rule for every writer, STORE-012."""
    extra, parsed = _json(ctx, 'extra')
    if extra is not None and not (parsed and isinstance(extra, dict)):
        notices.append({'where': 'extra', 'message': 'extra is not a JSON object; it was kept in the extra under '
                                                     'extra.'})
        extra = {'extra': extra}
    refs, parsed = _json(ctx, 'refs')
    if refs is None:
        return None, cast(dict[str, Any] | None, extra)
    return (cast(list[Any], refs) if parsed and isinstance(refs, list) else [refs]), cast(dict[str, Any] | None, extra)


def _whole(value: Any) -> Any:
    """name_length as a number when its text is one; anything else goes to the store as given, which names it."""
    return int(value) if isinstance(value, str) and value.isdigit() else value


def _building(store: Store) -> Recording | None:
    """The intake being recorded for this project, in whichever of its metaforms it is building."""
    page = store.intake_recording().results
    if not page:
        return None
    found = page[0]
    return Recording(Store(store.project_id, metaform=found.metaform_id), found.layer, found.metaform, found.active)


def _open(ctx: Context, store: Store, notices: Notices) -> Recording:
    """A new building intake layer: in the active metaform, or in a new one when that one has an intake."""
    active = store.active_metaform()
    target, name, is_active = store, active.name if active is not None else 'main', True
    if active is not None and store.has_intake():
        fresh = store.add_metaform(f'intake-{_stamp()}', activate=False)
        target, name, is_active = Store(store.project_id, metaform=fresh.metaform_id), fresh.name, False
        notices.append({'where': 'metaform', 'message': f'This project already has an intake in metaform '
                                                        f'{active.name}. This one is recorded in the new metaform '
                                                        f'{name}, which becomes the active one when the intake '
                                                        'finishes; the earlier one is kept whole.'})
    # No copy of the intake text is kept: the Canonical Intake's purpose never changes, STORE-016.
    provenance = {'module': 'intake', 'workflow': 'canonical-intake', 'prompt': None,
                  'model': ctx.nouns.get('model'), 'role': ctx.nouns.get('role'), 'blinded': ctx.nouns.get('blinded')}
    layer = target.layer('intake', 'intake', VARIABLE, kind='intake',
                         mutable=False, hideable=False, provenance=provenance, result_id=_text(ctx, 'id', notices))
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
        _note(notices, found.store.complete(
            found.layer.name, {name: ctx.nouns.get(name) for name in ('model', 'role', 'blinded')},
            _text(ctx, 'id', notices)))
    else:
        found = _open(ctx, store, notices)
    return {'layer': found.layer.name, 'project': store.project_id, 'metaform': found.metaform, 'notices': notices}


def _own(element: Element | None, layer: Layer) -> bool:
    """Whether the element's row is this intake's own, so describing it again changes it in place."""
    return element is not None and element.layer_id == layer.layer_id


def _described(element: Element) -> bool:
    """Whether an element was described with intake element, not only recorded as the end of a join."""
    return element.role is not None or element.name_length is not None or bool(element.refs)


def _describe(rec: Recording, address: str, given: dict[str, Any], refs: list[Any] | None,
              extra: dict[str, Any] | None, notices: Notices) -> str | None:
    """Record an element, or describe it again: the fields given replace the ones it had, the rest are kept.

    An element is its address, name_length and role, STORE-009. A name given for it is kept in its own name field,
    the canonical name the project uses for it, STORE-009; the project's name for a functionality goes on the join,
    MAP-020.
    """
    current = rec.store.element(address, raw=True)
    own = _own(current, rec.layer)
    role = given.get('role')
    if role is None and (not own or current is None or current.role is None):
        notices.append({'where': 'role', 'message': 'role is missing; the element was stored without a role.'})
    name = given.get('name')
    if name is None and (not own or current is None or current.name is None):
        notices.append({'where': 'name', 'message': 'name is missing; stored empty.'})
    if not own:
        made = rec.store.add_element(rec.layer.name, address, name_length=given.get('name_length'), role=role,
                                     refs=refs or (), extra=extra, name=name)
        _note(notices, made)
        if current is not None and extra is not None:
            _note(notices, rec.store.edit(current.element_id, {'extra': extra}))
        return getattr(made, 'element_id', None)
    assert current is not None
    changes: dict[str, Any] = {key: given[key] for key in ('name_length', 'name', 'role') if given.get(key) is not None}
    if refs is not None:
        changes['refs'] = refs
    if extra is not None:
        changes['extra'] = extra
    if changes:
        _note(notices, rec.store.edit(current.element_id, changes))
    return current.element_id


def element(ctx: Context) -> Any:
    """Record one element, or describe again one already recorded."""
    notices: Notices = []
    rec = _recording(ctx, notices)
    refs, extra = _refs_and_extra(ctx, notices)
    given = {name: ctx.nouns.get(name) for name in ('name', 'role')}
    given['name_length'] = _whole(ctx.nouns.get('name_length'))
    address = ctx.nouns[ADDRESS]
    made = _describe(rec, address, given, refs, extra, notices)
    _condition(ctx, rec, 'element', made, notices)
    return {ADDRESS: address, 'layer': rec.layer.name, 'notices': notices}


def _condition(ctx: Context, rec: Recording, kind: Literal['element', 'join'], thing: str | None,
               notices: Notices) -> None:
    """A condition or a note given with what was recorded is an open work record at it, MAP-046: the missing, broken
    and exclude marks of the Canonical Intake's step 2, apart from the map."""
    if thing is None or (ctx.nouns.get('condition') is None and ctx.nouns.get('note') is None):
        return
    _note(notices, rec.store.add_work(Node(kind, thing), ctx.nouns.get('condition'), note=ctx.nouns.get('note')))


def _missing(ctx: Context, names: tuple[str, ...], notices: Notices) -> None:
    for name in names:
        if ctx.nouns.get(name) is None:
            notices.append({'where': name, 'message': f'{name} is missing; stored empty.'})


def add_purpose(ctx: Context) -> Any:
    """Add one purpose: the receiver's Operative Purpose served by the provider's encounter function. The code writes it as
    a join of type purpose held by the receiver, MAP-020."""
    notices: Notices = []
    rec = _recording(ctx, notices)
    refs, extra = _refs_and_extra(ctx, notices)
    _missing(ctx, (*JOIN_TEXT, 'ifd'), notices)
    receiver, provider = ctx.nouns['receiver'], ctx.nouns['provider']
    made = rec.store.add_join(rec.layer.name, receiver, provider,
                              **{name: ctx.nouns.get(name) for name in ('name', *JOIN_TEXT, 'non_goal')},
                              refs=refs or (), extra=extra, ifd=ctx.nouns.get('ifd'))
    _note(notices, made, _words(rec.store, rec.layer))
    _condition(ctx, rec, 'join', getattr(made, 'join_id', None), notices)
    return {'receiver': receiver, 'provider': provider, 'layer': rec.layer.name, 'notices': notices}


def subtype(ctx: Context) -> Any:
    """Record one part inside a purpose, named by its receiver and provider, holding an element recorded or
    described as intake element does: the part stays one element record, MAP-030. The code writes it as a subtype
    join in that purpose's join."""
    notices: Notices = []
    rec = _recording(ctx, notices)
    refs, extra = _refs_and_extra(ctx, notices)
    receiver, provider, address = ctx.nouns['parent_receiver'], ctx.nouns['parent_provider'], ctx.nouns[ADDRESS]
    result = {'parent_receiver': receiver, 'parent_provider': provider, ADDRESS: address, 'layer': rec.layer.name,
              'notices': notices}
    parent = _purpose(rec.store, rec.layer, receiver, provider, notices)
    if parent is None:
        return result
    _missing(ctx, (*SUBTYPE_TEXT, 'ifd'), notices)
    described = {'role': ctx.nouns.get('role'), 'name_length': _whole(ctx.nouns.get('name_length')),
                 'name': ctx.nouns.get('name')}
    element_id = _describe(rec, address, described, None, None, notices)
    made = rec.store.add_subtype(rec.layer.name, parent.join_id, element_id or address,
                                 **{name: ctx.nouns.get(name) for name in (*SUBTYPE_TEXT, 'non_goal', 'name',
                                                                           'purpose')},
                                 refs=refs or (), extra=extra, ifd=ctx.nouns.get('ifd'))
    _note(notices, made, _words(rec.store, rec.layer))
    _condition(ctx, rec, 'join', getattr(made, 'join_id', None), notices)
    return result


def _target(store: Store) -> tuple[Recording | None, Store, Layer | None]:
    """The intake being recorded and its store, or the project's store when none is."""
    found = _building(store)
    return found, (found.store if found is not None else store), (found.layer if found is not None else None)


FINISHED = ('The intake is finished, so nothing was changed. The metaform changes by refining, with metaform map '
            'refine, which keeps every version, LAYER-025.')


def _finished(store: Store, found: Recording | None, named: dict[str, Any]) -> dict[str, Any] | None:
    """What edit, remove and absorb return once no intake is being recorded: they change nothing."""
    if found is not None:
        return None
    said = FINISHED if store.has_intake() else NOTHING
    return {**named, 'layer': None, 'notices': [{'where': 'intake', 'message': said}]}


def absorb(ctx: Context) -> Any:
    """Make a recorded purpose a part inside its parent's purpose, keeping every field, its purpose among
    them; any other purpose that still names the element is named and left as it is, MAP-030."""
    found, target, layer = _target(ctx.require_store())
    nouns = ctx.nouns
    done = _finished(target, found, {key: nouns[key] for key in ('receiver', 'provider', 'parent_receiver', 'parent_provider')})
    if done is not None:
        return done
    notices: Notices = []
    words = _words(target, layer)
    held = _purpose(target, layer, nouns['receiver'], nouns['provider'], notices)
    parent = _purpose(target, layer, nouns['parent_receiver'], nouns['parent_provider'], notices)
    if held is not None and parent is not None:
        _note(notices, target.edit(held.join_id, {'parent': parent.join_id}), words)
    return {'receiver': nouns['receiver'], 'provider': nouns['provider'], 'parent_receiver': nouns['parent_receiver'],
            'parent_provider': nouns['parent_provider'], 'layer': layer.name if layer is not None else None,
            'notices': notices}


def _refs(found: Any) -> list[dict[str, str]]:
    return [{'key': ref.key, 'value': ref.value} for ref in (found or ())]


def _element_entry(found: Element) -> dict[str, Any]:
    return {ADDRESS: found.address, 'short_name': found.short_name, 'name_length': found.name_length,
            'name': found.name, 'role': found.role, 'refs': _refs(found.refs), 'extra': found.extra}


def _subtype_entry(item: Subtype) -> dict[str, Any]:
    return {ADDRESS: item.address, 'short_name': item.short_name, 'role': item.role, 'name_length': item.name_length,
            'name': item.name, 'element_name': item.element_name, 'purpose': item.purpose, 'ifd': item.ifd,
            **{name: getattr(item, name) for name in (*SUBTYPE_TEXT, 'non_goal')}, 'refs': _refs(item.refs),
            'extra': item.extra}


def _purpose_entry(held: Join, inside: tuple[Subtype, ...]) -> dict[str, Any]:
    return {'receiver': held.receiver_address, 'provider': held.provider_address, 'name': held.name,
            **{name: getattr(held, name) for name in (*JOIN_TEXT, 'non_goal')}, 'ifd': held.ifd,
            'refs': _refs(held.refs), 'extra': held.extra, 'subtypes': [_subtype_entry(item) for item in inside]}


Held = list[tuple[Join, tuple[Subtype, ...]]]


def _held(store: Store, joins: Held, layer: Layer) -> list[Element]:
    """The elements this intake recorded that its parts hold, each one element record, MAP-030."""
    found: list[Element] = []
    for _, inside in joins:
        for item in inside:
            element = store.element(item.element_id, raw=True)
            if element is not None and element.layer_id == layer.layer_id and element not in found:
                found.append(element)
    return found


def _elements(store: Store, elements: list[Element], joins: Held, layer: Layer) -> list[Element]:
    listed = {found.element_id: found for found in [*elements, *_held(store, joins, layer)]}
    return sorted(listed.values(), key=lambda found: found.address)


def _map(store: Store, elements: list[Element], joins: Held, layer: Layer) -> dict[str, Any]:
    """The recorded map in the agent's words: every element by its address, every purpose by its receiver and
    provider with the parts it holds, and the addresses never described."""
    ordered = _elements(store, elements, joins, layer)
    return {'elements': [_element_entry(found) for found in ordered],
            'purposes': [_purpose_entry(held, inside) for held, inside in joins],
            'undescribed': [found.address for found in ordered if not _described(found)]}


def _recorded(store: Store, layer: Layer) -> tuple[list[Element], Held]:
    graph: GraphPage = store.layer_graph(layer.name)
    joins: Held = [(held, held.subtypes) for held in graph.joins]
    return _elements(store, [placed.element for placed in graph.elements], joins, layer), joins


def _whole_map(store: Store, layer: Layer) -> dict[str, Any]:
    elements, joins = _recorded(store, layer)
    return _map(store, elements, joins, layer)


def _receiver_map(store: Store, receiver: str, layer: Layer) -> dict[str, Any]:
    """One receiver's purposes in this intake and what they hold, with the elements they name, BASE-039."""
    owner = store.element(receiver, raw=True)
    if owner is None:
        return {'elements': [], 'purposes': [], 'undescribed': [], 'notices': [{'where': 'receiver', 'message': (
            f'{receiver} is not an element of this intake; nothing is recorded under it.')}]}
    joins = [(held, tuple(item for item in store.subtypes(held.join_id, raw=True, limit=0).results
                          if item.layer_id == layer.layer_id))
             for held in store.joins(owner.element_id, raw=True, limit=0).results if held.layer_id == layer.layer_id]
    named = [owner, *(store.element(held.provider, raw=True) for held, _ in joins)]
    elements = [found for found in named if found is not None and found.layer_id == layer.layer_id]
    return {**_map(store, elements, joins, layer), 'notices': []}


NOTHING = 'No intake is being recorded. intake start begins one.'


def show(ctx: Context) -> Any:
    """The intake being recorded, whole or one receiver's purposes and what they hold: to read back, proof and
    correct before finishing, without reading the whole map at once."""
    store = ctx.require_store()
    found = _building(store)
    if found is None:
        return {'layer': None, 'project': store.project_id, 'metaform': None, 'elements': [], 'purposes': [],
                'undescribed': [], 'notices': [{'where': 'intake', 'message': NOTHING}]}
    receiver = ctx.nouns.get('receiver')
    shown: dict[str, Any] = (_receiver_map(found.store, str(receiver), found.layer) if receiver
                             else {**_whole_map(found.store, found.layer), 'notices': []})
    return {'layer': found.layer.name, 'project': store.project_id, 'metaform': found.metaform, **shown}


PURPOSE_EDITS = ('name', 'purpose', 'ef', 'ifd', 'verb', 'non_goal')
MOVES = {'to_receiver': 'receiver', 'to_provider': 'provider'}


def _edit_element(ctx: Context, found: Recording | None, target: Store, current: Element,
                  refs: list[Any] | None, extra: dict[str, Any] | None, notices: Notices) -> None:
    """Describe a recorded element again; its namespace_address is its identity and never changes, MAP-015."""
    if ctx.nouns.get('to_address') is not None and ctx.nouns['to_address'] != current.address:
        notices.append({'where': 'to_address', 'message': UNMOVED})
    given = {key: ctx.nouns[key] for key in ELEMENT_FIELDS if ctx.nouns.get(key) is not None}
    if 'name_length' in given:
        given['name_length'] = _whole(given['name_length'])
    if found is not None and (given or refs is not None or extra is not None):
        _describe(found, current.address, {**given, 'role': given.get('role')}, refs, extra, notices)
        notices[:] = [notice for notice in notices if not notice['message'].startswith('role is missing')]
    elif found is None and (given or refs is not None or extra is not None):
        changes: dict[str, Any] = {key: value for key, value in given.items() if key != 'name'}
        changes.update({key: value for key, value in (('refs', refs), ('extra', extra)) if value is not None})
        _note(notices, target.edit(current.element_id, changes))


def _changes(ctx: Context, refs: list[Any] | None, extra: dict[str, Any] | None) -> dict[str, Any]:
    changes: dict[str, Any] = {key: ctx.nouns[key] for key in PURPOSE_EDITS if ctx.nouns.get(key) is not None}
    if refs is not None:
        changes['refs'] = refs
    if extra is not None:
        changes['extra'] = extra
    return changes


def _edit_purpose(ctx: Context, target: Store, held: Join, refs: list[Any] | None, extra: dict[str, Any] | None,
                      notices: Notices, words: dict[str, str]) -> None:
    """Change a recorded purpose; to_receiver and to_provider move it and it stays the same, MAP-003."""
    changes = _changes(ctx, refs, extra)
    changes.update({column: ctx.nouns[noun] for noun, column in MOVES.items() if ctx.nouns.get(noun) is not None})
    if changes:
        _note(notices, target.edit(held.join_id, changes), words)


def _edit_part(ctx: Context, found: Recording | None, target: Store, item: Subtype, refs: list[Any] | None,
               extra: dict[str, Any] | None, notices: Notices, words: dict[str, str]) -> None:
    """Change a recorded part; to_address gives it another element to hold, and role and name_length describe the
    element it holds."""
    changes = _changes(ctx, refs, extra)
    if ctx.nouns.get('to_address') is not None:
        changes['provider'] = ctx.nouns['to_address']
    element = {key: ctx.nouns[key] for key in ('role', 'name_length') if ctx.nouns.get(key) is not None}
    if element and found is not None and item.address is not None:
        _describe(found, item.address, {'role': element.get('role'),
                                        'name_length': _whole(element.get('name_length'))}, None, None, notices)
        notices[:] = [notice for notice in notices if not notice['message'].startswith('role is missing')]
    elif element:
        changes.update(element)
    if changes:
        _note(notices, target.edit(item.join_id, changes), words)


NAMED_BY = ('Name what to change by its addresses: namespace_address for an element, receiver and provider for a '
            'purpose, and all three for a part inside a purpose.')


def _named(ctx: Context) -> dict[str, Any]:
    return {key: ctx.nouns[key] for key in ('receiver', 'provider', ADDRESS) if ctx.nouns.get(key) is not None}


def edit(ctx: Context) -> Any:
    """Change one recorded element, purpose or part in place while the intake is being recorded."""
    found, target, layer = _target(ctx.require_store())
    named = _named(ctx)
    done = _finished(target, found, named)
    if done is not None:
        return done
    notices: Notices = []
    refs, extra = _refs_and_extra(ctx, notices)
    words = _words(target, layer)
    if 'receiver' in named or 'provider' in named:
        held = _purpose(target, layer, named.get('receiver'), named.get('provider'), notices)
        item = _part(target, layer, held, named[ADDRESS], notices) if held is not None and ADDRESS in named else None
        if item is not None:
            _edit_part(ctx, found, target, item, refs, extra, notices, words)
        elif held is not None and ADDRESS not in named:
            _edit_purpose(ctx, target, held, refs, extra, notices, words)
    elif ADDRESS in named:
        current = target.element(named[ADDRESS], raw=True)
        if current is None:
            notices.append({'where': ADDRESS, 'message': f'{named[ADDRESS]} is not an element; nothing was changed.'})
        else:
            _edit_element(ctx, found, target, current, refs, extra, notices)
    else:
        notices.append({'where': ADDRESS, 'message': NAMED_BY})
    return {**named, 'layer': layer.name if layer is not None else None, 'notices': notices}


def remove(ctx: Context) -> Any:
    """Remove one recorded element, purpose or part while the intake is being recorded."""
    found, target, layer = _target(ctx.require_store())
    named = _named(ctx)
    done = _finished(target, found, named)
    if done is not None:
        return done
    notices: Notices = []
    words = _words(target, layer)
    thing: str | None = None
    if 'receiver' in named or 'provider' in named:
        held = _purpose(target, layer, named.get('receiver'), named.get('provider'), notices)
        if held is not None and ADDRESS in named:
            item = _part(target, layer, held, named[ADDRESS], notices)
            thing = item.join_id if item is not None else None
        elif held is not None:
            thing = held.join_id
    elif ADDRESS in named:
        current = target.element(named[ADDRESS], raw=True)
        thing = current.element_id if current is not None else None
        if current is None:
            notices.append({'where': ADDRESS, 'message': f'{named[ADDRESS]} is not an element; nothing was changed.'})
    else:
        notices.append({'where': ADDRESS, 'message': NAMED_BY})
    if thing is not None:
        _note(notices, target.remove(thing), words)
    return {**named, 'layer': layer.name if layer is not None else None, 'notices': notices}


def finish(ctx: Context) -> Any:
    """Finish the intake: its layer becomes the metaform's intake, seen by every read, and cannot change in place."""
    store = ctx.require_store()
    notices: Notices = []
    report = _given(ctx, 'report', notices)
    feedback = _given(ctx, 'feedback', notices)
    found = _building(store)
    if found is None:
        return {'layer': None, 'project': store.project_id, 'metaform': None, 'elements': 0, 'purposes': 0,
                'subtypes': 0, 'refs': 0, 'work': 0,
                'notices': notices + [{'where': 'intake', 'message': 'No intake is being recorded; there is nothing '
                                                                     'to finish.'}]}
    elements, joins = _recorded(found.store, found.layer)
    undescribed = [element.address for element in elements if not _described(element)]
    if undescribed:
        notices.append({'where': 'undescribed', 'message': f'{", ".join(undescribed)} '
                                                           f'{"was" if len(undescribed) == 1 else "were"} named in a '
                                                           'purpose but never described with intake element; '
                                                           'stored without a role or a name_length.'})
    _note(notices, found.store.finish(found.layer.name))
    if not found.active:
        previous = store.active_metaform()
        store.activate_metaform(found.metaform)
        if previous is not None:
            notices.append({'where': 'metaform', 'message': f'This intake was stored as the new active metaform '
                                                            f'{found.metaform}; the earlier one, {previous.name}, is '
                                                            'kept whole. To switch back: metaform activate metaform '
                                                            f'{previous.name}'})
    for kind, text in (('report', report), ('feedback', feedback)):
        if text is not None:
            save_report(store.project_id, found.layer.layer_id, kind, text, store=found.store,
                        layer=found.layer.layer_id)
    # The open work records on what this intake recorded, MAP-046: the condition of an object is apart from the map.
    parts = [item for _, inside in joins for item in inside]
    recorded_ids = {element.element_id for element in elements} | {
        held.join_id for held in [*(held for held, _ in joins), *parts]}
    work = sum(1 for row in found.store.work(open=True, limit=0).results if row.id in recorded_ids)
    refs = sum(len(row.refs) for row in [*elements, *(held for held, _ in joins), *parts])
    return {'layer': found.layer.name, 'project': store.project_id, 'metaform': found.metaform,
            'elements': len(elements), 'purposes': len(joins), 'subtypes': len(parts), 'refs': refs,
            'work': work, 'notices': notices}


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


def _nouns(*names: str) -> tuple[Noun, ...]:
    return tuple(NOUNS[name] for name in names)


E, J, H = ELEMENT_WORDS.get, JOIN_WORDS.get, HELD_WORDS.get
NOUNS = {noun.name: noun for noun in (
    Noun('role', E('role', ''), required=False, schema=ROLE),
    Noun('name', E('name', ''), required=False),
    Noun('name_length', E('name_length', ''), required=False, schema=NAME_LENGTH),
    Noun('refs', J('refs', ''), required=False, schema=REFS),
    Noun('extra', E('extra', ''), required=False, schema=EXTRA),
    Noun('condition', E('condition', ''), required=False),
    Noun('note', E('note', ''), required=False),
    Noun('ifd', J('ifd', ''), required=False, schema=IFD),
    *(Noun(field, J(field, ''), required=False) for field in ('purpose', 'ef', 'verb', 'non_goal')),
)}
PURPOSE = (Noun('receiver', J('receiver', '')), Noun('provider', J('provider', '')))
SUBTYPE_NOUNS = (
    Noun('parent_receiver', J('parent_receiver', '')),
    Noun('parent_provider', J('parent_provider', '')),
    Noun(ADDRESS, H(ADDRESS, '')),
    *_nouns('purpose', 'ef', 'ifd', 'verb', 'non_goal'),
    Noun('role', H('role', ''), required=False, schema=SUBTYPE_ROLE),
    Noun('name', H('name', ''), required=False),
    Noun('name_length', H('name_length', ''), required=False, schema=NAME_LENGTH),
    Noun('refs', H('refs', ''), required=False, schema=REFS),
    NOUNS['extra'],
    *_nouns('condition', 'note'),
)
ABSORB_NOUNS = (
    *PURPOSE,
    Noun('parent_receiver', J('parent_receiver', '')),
    Noun('parent_provider', J('parent_provider', '')),
)
NAMING = (
    Noun('receiver', J('receiver', ''), required=False),
    Noun('provider', J('provider', ''), required=False),
    Noun(ADDRESS, E(ADDRESS, ''), required=False),
)

MODULE = Module(
    id='intake',
    summary='Serve the Canonical Intake and record its result as it is reasoned.',
    purpose='Serves the Canonical Intake instructions, records the intake as it is reasoned, and tracks whether this '
            'project has an intake. The intake is agent work: a subagent reads its instructions with the command prompt '
            'and follows them. Details: metaform help intake.',
    details='The intake text is served as stored, with its prompt slot filled. The intake is recorded as it is '
            'reasoned, one element, purpose or part per call, into one building intake layer, annealed with '
            'absorb, read back with show, whole or one receiver at a time, and corrected with edit and remove. An '
            'element is named by its namespace_address, a purpose by its receiver and provider, and a part by '
            'its address inside that purpose. No '
            'other read sees it until finish; after finish the metaform changes by refining, metaform map refine, '
            'in the same layer. Nothing is '
            'refused for its content: what does not fit is stored as given and named in a notice.',
    verbs=(
        Verb('prompt', prompt, 'The Canonical Intake instructions for this project.',
             nouns=(Noun('text', 'path to the target for the intake process; leaving this blank means this project', required=False),)),
        Verb('start', start, 'Resume the intake being recorded, or start a fresh one. If the active metaform already '
                            'has an intake, creates a separate intake-<UTC timestamp> metaform, keeping the earlier '
                            'one untouched. Returns its name; the existing web GUI follows it live.',
             nouns=(Noun('model', 'The model that performs the intake.', required=False),
                    Noun('role', 'The role of the agent that performs it.', required=False),
                    Noun('blinded', 'Whether the agent sees only the map.', kind='bool', required=False),
                    Noun('id', "The result's generated id.", required=False))),
        Verb('element', element, 'Record one element, or describe again one already recorded.',
             nouns=(Noun(ADDRESS, E(ADDRESS, '')),
                    *_nouns('name_length'),
                    Noun('name', E('name', ''), required=False),
                    *_nouns('role'),
                    Noun('refs', E('refs', ''), required=False, schema=REFS),
                    NOUNS['extra'],
                    *_nouns('condition', 'note'))),
        Verb('add_purpose', add_purpose, "Add one purpose: the receiver's Operative Purpose served by the provider's "
                                         'encounter function.',
             nouns=(*PURPOSE,
                    *_nouns('name', 'purpose', 'ef', 'ifd', 'verb', 'non_goal', 'refs', 'extra', 'condition',
                            'note'))),
        Verb('subtype', subtype, 'Record one part inside a purpose, named by its receiver and provider, holding '
                                 'an element.', nouns=SUBTYPE_NOUNS),
        Verb('absorb', absorb, "Anneal: make a recorded purpose a part inside its parent's purpose, keeping "
                               'every field; the element stays one element record.', nouns=ABSORB_NOUNS),
        Verb('show', show, 'The intake being recorded, whole or one receiver at a time.',
             nouns=(Noun('receiver', J('receiver', ''), required=False),)),
        Verb('edit', edit, 'Change one recorded element, purpose or part, named by its addresses; the fields '
                           'given replace the ones it had.',
             nouns=(*NAMING,
                    *_nouns('purpose', 'ef', 'ifd', 'verb', 'non_goal'),
                    Noun('to_receiver', J('to_receiver', ''), required=False),
                    Noun('to_provider', J('to_provider', ''), required=False),
                    Noun('to_address', E('to_address', ''), required=False),
                    *_nouns('role', 'name', 'name_length', 'refs', 'extra'))),
        Verb('remove', remove, 'Remove one recorded element, purpose or part, named by its addresses.',
             nouns=NAMING),
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
)
