"""intake: the Canonical Intake served by name, recorded one object at a time as it is reasoned, BASE-039.

A subagent reads `intake prompt` and records the map as it works: it starts the
intake, then records each element, join and subtype join in its own call,
anneals with `intake absorb`, reads the recorded map back with `intake show`,
whole or one receiver at a time, corrects it with `intake edit` and
`intake remove`, and ends with `intake finish`. The intake layer is building
until then: context reads do not see it, and the web GUI follows it live.
Every object is named by the key its recording call returned, `element_id` or
`join_id`, and an element's address is `namespace_address`, as in the
Canonical Intake. Nothing is refused for its content: what does not fit is
stored as given and named in a notice, BASE-044. The report and process
feedback are saved at the finish, BASE-045.
"""
from __future__ import annotations

import json
import re
import secrets
import sys
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any, cast

from metaform import settings
from metaform.data import Element, GraphPage, Join, Layer, Notice, Store, Subtype
from metaform.module import Context, Module, Noun, Status, Stop, Verb, save_report

from .schema import EF, EXTRA, NAME_LENGTH, REFS, ROLE, SUBTYPE_ROLE

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False

RESOURCE = resources.files(__name__) / 'resources' / 'Canonical_Intake.xml'
# What follows the intake when it is served: how its tools are used, and nothing about the work. The intake is the
# procedure. Which tool records it, how it is called and which command comes first are facts of this program, which
# the intake cannot know and the agent cannot guess.
USING = ('The intake is recorded with the intake tool. Over MCP, call the tool intake with command and arguments; called '
         'with no command it lists its commands and what each takes. On the command line the same commands are '
         'metaform intake <command>. Begin with start. Record each element with element, each join with join, and each '
         'subtype join with subtype. Read back what is recorded with show, change it with edit and remove, place a '
         'join inside its parent with absorb, and end with finish.\n')
NOTICE = ('This project has no map yet. Have a subagent perform the intake: tell it to call the intake tool with '
          'command prompt, or to run `metaform intake prompt`, and to follow what it returns.')
VARIABLE = ('The functional map of the artifact: its elements, and each receiver\'s purpose served by a provider\'s '
            'encounter function.')
TARGET = re.compile(r'<target\b[^>]*>')

settings.text('intake_file', '', help='An intake file to serve instead of the Canonical Intake. Empty means the '
                                      'Canonical Intake.')


def _escape(text: str) -> str:
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def _fill(tag: str, name: str, value: str) -> str:
    attribute = re.compile(rf'(\s{name}=")[^"]*(")')
    if attribute.search(tag):
        return attribute.sub(lambda match: match.group(1) + _escape(value) + match.group(2), tag, count=1)
    return tag.replace('<target', f'<target {name}="{_escape(value)}"', 1)


def served(ctx: Context) -> str:
    """The intake text exactly as stored, with its target filled, then how its tools are used, BASE-039. The intake
    is the procedure, and nothing about the work is added to it."""
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
    return text + ('\n' if text.endswith('\n') else '\n\n') + USING


def prompt(ctx: Context) -> str:
    return served(ctx)




# Recording, one object per call ------------------------------------------------------------------------------

Notices = list[dict[str, str]]
JOIN_TEXT = ('purpose', 'function', 'ef', 'relation', 'verb', 'observation')
SUBTYPE_TEXT = ('function', 'ef', 'relation', 'verb', 'observation')
ELEMENT_FIELDS = ('name', 'name_length', 'role')  # an element is its address, name_length and role; name, STORE-009
ADDRESS = 'namespace_address'  # the element's address, named as in the Canonical Intake, MAP-040
NAMED = ("An element is its address, name_length and role and holds no name: the project's name for a functionality "
         "goes on the join, with intake_join name. The name was kept in the element's extra.")
UNMOVED = ("An element cannot be moved: its namespace_address is its identity, and another address is a different "
           "element, MAP-015. namespace_address was not applied; record the element at the new address with "
           "element and move its joins to it with edit receiver= or provider=.")


class Recording:
    """The intake being recorded: the store of its metaform, its building layer, and that metaform."""

    def __init__(self, store: Store, layer: Layer, metaform: str, active: bool) -> None:
        self.store, self.layer, self.metaform, self.active = store, layer, metaform, active


def _stamp() -> str:
    return datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')


def _note(notices: Notices, result: Any) -> None:
    """A store result's notices, each named by the field it is about; the element's address by its tool name."""
    for notice in cast(tuple[Notice, ...], getattr(result, 'notices', ()) or ()):
        notices.append({'where': ADDRESS if notice.where == 'address' else notice.where, 'message': notice.message})


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
    layer = target.layer(f'intake-{_stamp()}-{secrets.token_hex(3)}', 'intake', VARIABLE, kind='intake',
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

    An element is its address, name_length and role, STORE-009. A name given for it is kept in its extra with a
    notice: the project's name for a functionality goes on the join, MAP-020 and BASE-044.
    """
    current = rec.store.element(address, raw=True)
    own = _own(current, rec.layer)
    role = given.get('role')
    if role is None and (not own or current is None or current.role is None):
        notices.append({'where': 'role', 'message': 'role is missing; the element was stored without a role.'})
    name = given.get('name')
    if name is not None:
        kept = extra if extra is not None else (current.extra if own and current is not None else None)
        extra = {**(kept or {}), 'name': name}
        notices.append({'where': 'name', 'message': NAMED})
    if not own:
        made = rec.store.add_element(rec.layer.name, address, name_length=given.get('name_length'), role=role,
                                     refs=refs or (), extra=extra)
        _note(notices, made)
        if current is not None and extra is not None:
            _note(notices, rec.store.edit(current.element_id, {'extra': extra}))
        return getattr(made, 'element_id', None)
    assert current is not None
    changes: dict[str, Any] = {key: given[key] for key in ('name_length', 'role') if given.get(key) is not None}
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
    return {'element_id': made, ADDRESS: address, 'layer': rec.layer.name, 'notices': notices}


def _missing(ctx: Context, names: tuple[str, ...], notices: Notices) -> None:
    for name in names:
        if ctx.nouns.get(name) is None:
            notices.append({'where': name, 'message': f'{name} is missing; stored empty.'})


def join(ctx: Context) -> Any:
    """Record one join: the receiver's purpose served by the provider's encounter function."""
    notices: Notices = []
    rec = _recording(ctx, notices)
    refs, extra = _refs_and_extra(ctx, notices)
    _missing(ctx, JOIN_TEXT, notices)
    receiver, provider = ctx.nouns['receiver'], ctx.nouns['provider']
    made = rec.store.add_join(rec.layer.name, receiver, provider,
                              **{name: ctx.nouns.get(name) for name in ('name', *JOIN_TEXT, 'non_goal')},
                              type=ctx.nouns.get('type') or 'purpose', refs=refs or (), extra=extra)
    _note(notices, made)
    return {'join_id': getattr(made, 'join_id', None), 'receiver': receiver, 'provider': provider,
            'layer': rec.layer.name, 'notices': notices}


def subtype(ctx: Context) -> Any:
    """Record one subtype join inside its parent join, holding an element recorded or described as intake element
    does: the absorbed part stays one element record, MAP-030."""
    notices: Notices = []
    rec = _recording(ctx, notices)
    refs, extra = _refs_and_extra(ctx, notices)
    _missing(ctx, SUBTYPE_TEXT, notices)
    address = ctx.nouns[ADDRESS]
    described = {'role': ctx.nouns.get('role'), 'name_length': _whole(ctx.nouns.get('name_length'))}
    element_id = _describe(rec, address, described, None, None, notices)
    made = rec.store.add_subtype(rec.layer.name, ctx.nouns['into'], element_id or address,
                                 **{name: ctx.nouns.get(name) for name in (*SUBTYPE_TEXT, 'non_goal', 'name',
                                                                           'purpose')},
                                 refs=refs or (), extra=extra)
    _note(notices, made)
    return {'join_id': getattr(made, 'join_id', None), 'parent': ctx.nouns['into'], 'element_id': element_id,
            ADDRESS: address, 'layer': rec.layer.name, 'notices': notices}


def absorb(ctx: Context) -> Any:
    """Make a recorded join a subtype join inside its parent's purpose join, keeping every field, its purpose among
    them; any other join that still names the element is named and left as it is, MAP-030."""
    store = ctx.require_store()
    notices: Notices = []
    found = _building(store)
    target = found.store if found is not None else store
    moved = target.edit(ctx.nouns['join'], {'parent': ctx.nouns['into']})
    _note(notices, moved)
    fields = cast(dict[str, Any], getattr(moved, 'fields', {}))
    element_id = fields.get('provider')
    held = target.element(str(element_id), raw=True) if element_id else None
    return {'join_id': ctx.nouns['join'], 'parent': fields.get('parent'), 'element_id': element_id,
            ADDRESS: held.address if held is not None else None,
            'layer': found.layer.name if found is not None else None, 'notices': notices}


def _refs(found: Any) -> list[dict[str, str]]:
    return [{'key': ref.key, 'value': ref.value} for ref in (found or ())]


def _element_entry(found: Element) -> dict[str, Any]:
    return {'element_id': found.element_id, ADDRESS: found.address, 'short_name': found.short_name,
            'role': found.role, 'name_length': found.name_length, 'refs': _refs(found.refs), 'extra': found.extra}


def _subtype_entry(item: Subtype) -> dict[str, Any]:
    return {'join_id': item.join_id, 'parent': item.parent, 'element_id': item.element_id, ADDRESS: item.address,
            'short_name': item.short_name, 'role': item.role, 'name_length': item.name_length, 'name': item.name,
            'purpose': item.purpose,
            **{name: getattr(item, name) for name in (*SUBTYPE_TEXT, 'non_goal')}, 'refs': _refs(item.refs),
            'extra': item.extra}


def _join_entry(held: Join, inside: tuple[Subtype, ...]) -> dict[str, Any]:
    return {'join_id': held.join_id, 'receiver': held.receiver_address, 'provider': held.provider_address,
            'type': held.type, 'name': held.name, **{name: getattr(held, name) for name in (*JOIN_TEXT, 'non_goal')},
            'refs': _refs(held.refs), 'extra': held.extra, 'subtypes': [_subtype_entry(item) for item in inside]}


def _held(store: Store, joins: list[tuple[Join, tuple[Subtype, ...]]], layer: Layer) -> list[Element]:
    """The elements this intake recorded that its subtype joins hold, each one element record, MAP-030."""
    found: list[Element] = []
    for _, inside in joins:
        for item in inside:
            element = store.element(item.element_id, raw=True)
            if element is not None and element.layer_id == layer.layer_id and element not in found:
                found.append(element)
    return found


def _map(store: Store, elements: list[Element], joins: list[tuple[Join, tuple[Subtype, ...]]],
         layer: Layer) -> dict[str, Any]:
    """The recorded map: every element with its element_id, every join with its join_id and the subtype joins it
    holds, and the addresses never described."""
    listed = {found.element_id: found for found in [*elements, *_held(store, joins, layer)]}
    ordered = sorted(listed.values(), key=lambda found: found.address)
    return {'elements': [_element_entry(found) for found in ordered],
            'joins': [_join_entry(held, inside) for held, inside in joins],
            'undescribed': [found.address for found in ordered if not _described(found)]}


def _whole_map(store: Store, layer: Layer) -> dict[str, Any]:
    graph: GraphPage = store.layer_graph(layer.name)
    joins: list[tuple[Join, tuple[Subtype, ...]]] = [(held, held.subtypes) for held in graph.joins]
    return _map(store, [placed.element for placed in graph.elements], joins, layer)


def _receiver_map(store: Store, receiver: str, layer: Layer) -> dict[str, Any]:
    """One receiver's joins in this intake and what they hold, with the elements they name, BASE-039."""
    owner = store.element(receiver, raw=True)
    if owner is None:
        return {'elements': [], 'joins': [], 'undescribed': [], 'notices': [{'where': 'receiver', 'message': (
            f'{receiver} is not an element of this intake; nothing is recorded under it.')}]}
    joins = [(held, tuple(item for item in store.subtypes(held.join_id, raw=True, limit=0).results
                          if item.layer_id == layer.layer_id))
             for held in store.joins(owner.element_id, raw=True, limit=0).results if held.layer_id == layer.layer_id]
    named = [owner, *(store.element(held.provider, raw=True) for held, _ in joins)]
    elements = [found for found in named if found is not None and found.layer_id == layer.layer_id]
    return {**_map(store, elements, joins, layer), 'notices': []}


NOTHING = 'No intake is being recorded. intake start begins one.'


def show(ctx: Context) -> Any:
    """The intake being recorded, whole or one receiver's joins and what they hold: to read back, proof and correct
    before finishing, without reading the whole map at once."""
    store = ctx.require_store()
    found = _building(store)
    if found is None:
        return {'layer': None, 'project': store.project_id, 'metaform': None, 'elements': [], 'joins': [],
                'undescribed': [], 'notices': [{'where': 'intake', 'message': NOTHING}]}
    receiver = ctx.nouns.get('receiver')
    shown: dict[str, Any] = (_receiver_map(found.store, str(receiver), found.layer) if receiver
                             else {**_whole_map(found.store, found.layer), 'notices': []})
    return {'layer': found.layer.name, 'project': store.project_id, 'metaform': found.metaform, **shown}


JOIN_EDITS = ('receiver', 'provider', 'type', 'name', 'purpose', 'function', 'ef', 'relation', 'verb', 'observation',
              'non_goal')


def _edit_element(ctx: Context, found: Recording | None, target: Store, current: Element,
                  refs: list[Any] | None, extra: dict[str, Any] | None, notices: Notices) -> None:
    """Describe a recorded element again; its namespace_address is its identity and never changes, MAP-015."""
    if ctx.nouns.get(ADDRESS) is not None and ctx.nouns[ADDRESS] != current.address:
        notices.append({'where': ADDRESS, 'message': UNMOVED})
    given = {key: ctx.nouns[key] for key in ELEMENT_FIELDS if ctx.nouns.get(key) is not None}
    if 'name_length' in given:
        given['name_length'] = _whole(given['name_length'])
    others = {key: ctx.nouns[key] for key in JOIN_EDITS if ctx.nouns.get(key) is not None}
    if found is not None and (given or refs is not None or extra is not None):
        _describe(found, current.address, {**given, 'role': given.get('role')}, refs, extra, notices)
        notices[:] = [notice for notice in notices if not notice['message'].startswith('role is missing')]
    elif found is None and (given or refs is not None or extra is not None):
        changes: dict[str, Any] = {key: value for key, value in given.items() if key != 'name'}
        changes.update({key: value for key, value in (('refs', refs), ('extra', extra)) if value is not None})
        _note(notices, target.edit(current.element_id, changes))
    if others:
        _note(notices, target.edit(current.element_id, others))


def _edit_join(ctx: Context, found: Recording | None, target: Store, thing: str, refs: list[Any] | None,
               extra: dict[str, Any] | None, notices: Notices) -> None:
    """Change a recorded join; its receiver and provider move it, MAP-003. On a subtype join namespace_address gives it
    another element to hold, and role and name_length describe the element it holds."""
    versions = target.history(thing, limit=0).results
    fields = versions[-1].fields if versions else {}
    changes: dict[str, Any] = {key: ctx.nouns[key] for key in JOIN_EDITS if ctx.nouns.get(key) is not None}
    element = {key: ctx.nouns[key] for key in ('role', 'name_length') if ctx.nouns.get(key) is not None}
    if fields.get('parent') is not None:
        if ctx.nouns.get(ADDRESS) is not None:
            changes['provider'] = ctx.nouns[ADDRESS]
        held = target.element(str(fields.get('provider')), raw=True)
        if element and held is not None and found is not None:
            _describe(found, held.address, {'role': element.get('role'),
                                            'name_length': _whole(element.get('name_length'))}, None, None, notices)
            notices[:] = [notice for notice in notices if not notice['message'].startswith('role is missing')]
            element = {}
    elif ctx.nouns.get(ADDRESS) is not None:
        changes[ADDRESS] = ctx.nouns[ADDRESS]
    changes.update(element)
    if refs is not None:
        changes['refs'] = refs
    if extra is not None:
        changes['extra'] = extra
    if changes:
        _note(notices, target.edit(thing, changes))


def edit(ctx: Context) -> Any:
    """Change one recorded element, join or subtype join in place while the intake is being recorded."""
    store = ctx.require_store()
    notices: Notices = []
    found = _building(store)
    target = found.store if found is not None else store
    refs, extra = _refs_and_extra(ctx, notices)
    thing = ctx.nouns['id']
    current = target.element(thing, raw=True)
    if current is not None:
        _edit_element(ctx, found, target, current, refs, extra, notices)
    else:
        _edit_join(ctx, found, target, thing, refs, extra, notices)
    return {'id': thing, 'layer': found.layer.name if found is not None else None, 'notices': notices}


def remove(ctx: Context) -> Any:
    """Remove one recorded element, join or subtype join while the intake is being recorded."""
    store = ctx.require_store()
    notices: Notices = []
    found = _building(store)
    target = found.store if found is not None else store
    thing = ctx.nouns['id']
    current = target.element(thing, raw=True)
    _note(notices, target.remove(current.element_id if current is not None else thing))
    return {'id': thing, 'layer': found.layer.name if found is not None else None, 'notices': notices}


def finish(ctx: Context) -> Any:
    """Finish the intake: its layer becomes the metaform's intake, seen by every read, and cannot change in place."""
    store = ctx.require_store()
    notices: Notices = []
    report = _given(ctx, 'report', notices)
    feedback = _given(ctx, 'feedback', notices)
    found = _building(store)
    if found is None:
        return {'layer': None, 'project': store.project_id, 'metaform': None, 'elements': 0, 'joins': 0,
                'subtypes': 0, 'refs': 0, 'work': 0,
                'notices': notices + [{'where': 'intake', 'message': 'No intake is being recorded; there is nothing '
                                                                     'to finish.'}]}
    recorded = _whole_map(found.store, found.layer)
    if recorded['undescribed']:
        names = recorded['undescribed']
        notices.append({'where': 'undescribed', 'message': f'{", ".join(names)} {"was" if len(names) == 1 else "were"} '
                                                           'recorded as the end of a join but never described with '
                                                           'intake element; stored without a role or a '
                                                           'name_length.'})
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
    subtypes = [item for row in recorded['joins'] for item in row['subtypes']]
    recorded_ids = {row['element_id'] for row in recorded['elements']} | {
        row['join_id'] for row in [*recorded['joins'], *subtypes]}
    work = sum(1 for row in found.store.work(open=True, limit=0).results if row.id in recorded_ids)
    refs = sum(len(row['refs']) for row in [*recorded['elements'], *recorded['joins'], *subtypes])
    return {'layer': found.layer.name, 'project': store.project_id, 'metaform': found.metaform,
            'elements': len(recorded['elements']), 'joins': len(recorded['joins']), 'subtypes': len(subtypes),
            'refs': refs, 'work': work, 'notices': notices}


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
    if ctx.store.has_intake():
        return Status(lines=('Intake: complete', *recording, 'Start with: metaform map roots'))
    if found is not None:
        return Status(lines=recording)
    return Status(lines=('Intake: none yet',), notice=NOTICE)


def _nouns(*names: str) -> tuple[Noun, ...]:
    return tuple(NOUNS[name] for name in names)


NOUNS = {noun.name: noun for noun in (
    Noun('role', 'AUE, VE, DE, SE or NE.', required=False, schema=ROLE),
    Noun('name', 'The Canonical Name, the project\'s official terminology, or an informal name.', required=False),
    Noun('name_length', 'proper_noun_lookback_segment_count: how many segments, read from the leaf, name it.',
         required=False, schema=NAME_LENGTH),
    Noun('refs', 'Refs as a JSON array of objects with a key and a value, for type-specific or artifact-specific '
                 'references, such as key path and a relative path.', required=False, schema=REFS),
    Noun('extra', 'Any other field, as a JSON object, kept in the extra.', required=False, schema=EXTRA),
    Noun('type', 'The join type: purpose.', required=False),
    Noun('purpose', 'State the objective or standard this element or action fulfills.', required=False),
    Noun('function', 'Encounter Function of the PE within the RE context.', required=False),
    Noun('ef', 'Function if it is the encounter of a functionality, Encounter if it is the functionality of the '
               'encounter.', required=False, schema=EF),
    Noun('relation', 'Active-voice descriptive fragment starting with a third-person singular present-tense verb '
                     'ending in -s/-es; the implicit subject is the PE if ef is Function, or the RE if ef is '
                     'Encounter.', required=False),
    Noun('verb', 'The single root verb extracted from the relation (e.g., provides, tracks, restricts).',
         required=False),
    Noun('observation', 'High-value observation consisting of long-lasting, stable state.', required=False),
    Noun('non_goal', 'High-value non-goals consisting of structural constraints.', required=False),
)}
SUBTYPE_NOUNS = (
    Noun('into', 'The join_id of the parent join it sits inside, as intake join returned it.'),
    Noun(ADDRESS, 'The namespace_address of the element the subtype join holds: the absorbed element, recorded as '
                  'intake element records one when there is none.'),
    NOUNS['type'],
    NOUNS['purpose'],
    NOUNS['function'],
    NOUNS['ef'],
    NOUNS['relation'],
    NOUNS['verb'],
    NOUNS['observation'],
    NOUNS['non_goal'],
    Noun('role', 'The role of the element it holds: DE, SE or NE.', required=False, schema=SUBTYPE_ROLE),
    Noun('name', NOUNS['name'].help, required=False),
    Noun('name_length', 'proper_noun_lookback_segment_count of the element it holds: how many segments, read from the '
                        'leaf, name it.', required=False, schema=NAME_LENGTH),
    NOUNS['refs'],
    NOUNS['extra'],
)
ABSORB_NOUNS = (
    Noun('join', 'The join_id of the join where the element provides, the join to place inside its parent.'),
    Noun('into', "The join_id of the parent's purpose join it goes inside."),
)

MODULE = Module(
    id='intake',
    summary='Serve the Canonical Intake and record its result as it is reasoned.',
    purpose='Serves the Canonical Intake instructions, records the intake as it is reasoned, and tracks whether this '
            'project has an intake. The intake is agent work: a subagent reads its instructions with the command prompt '
            'and follows them. Details: metaform help intake.',
    details='The intake text is served unchanged except for its filled target. The intake is recorded as it is '
            'reasoned, one element, join or subtype join per call, into one building intake layer, annealed with '
            'absorb, read back with show, whole or one receiver at a time, and corrected with edit and remove. No '
            'other read sees it until finish; after finish it changes only through a correction layer. Nothing is '
            'refused for its content: what does not fit is stored as given and named in a notice.',
    verbs=(
        Verb('prompt', prompt, 'The Canonical Intake instructions for this project.'),
        Verb('start', start, 'Start recording an intake, or resume the one being recorded.',
             nouns=(Noun('model', 'The model that performs the intake.', required=False),
                    Noun('role', 'The role of the agent that performs it.', required=False),
                    Noun('blinded', 'Whether the agent sees only the map.', kind='bool', required=False),
                    Noun('id', "The result's generated id.", required=False))),
        Verb('element', element, 'Record one element, or describe again one already recorded.',
             nouns=(Noun(ADDRESS, "The element's namespace_address, its identity."),
                    *_nouns('role', 'name_length', 'refs', 'extra'),
                    Noun('name', "An element holds no name: it is its address, name_length and role. The project's "
                                 'name for a functionality goes on the join, with intake_join name. Given here, it is '
                                 "kept in the element's extra.", required=False))),
        Verb('join', join, "Record one join: the receiver's purpose served by the provider's encounter function.",
             nouns=(Noun('receiver', 'The namespace address of the Vested Entity whose Operative Purpose this join '
                                     'states.'),
                    Noun('provider', 'The namespace address of the Providing Element.'),
                    *_nouns('name', 'purpose', 'function', 'ef', 'relation', 'verb', 'observation', 'non_goal', 'type',
                            'refs', 'extra'))),
        Verb('subtype', subtype, 'Record one subtype join inside its parent join, holding an element.',
             nouns=SUBTYPE_NOUNS),
        Verb('absorb', absorb, "Anneal: make a recorded join a subtype join inside its parent's purpose join, keeping "
                               'every field; the element stays one element record.', nouns=ABSORB_NOUNS),
        Verb('show', show, 'The intake being recorded, whole or one receiver at a time, with the ids to edit or '
                           'remove.',
             nouns=(Noun('receiver', "An element's namespace_address: show only the joins it receives and what they "
                                     'hold.', required=False),)),
        Verb('edit', edit, 'Change one recorded element, join or subtype join; the fields given replace the ones it '
                           'had.',
             nouns=(Noun('id', "An element's namespace_address or element_id, or a join_id, a subtype join's "
                               'included.'),
                    *_nouns('purpose', 'function', 'ef', 'relation', 'verb', 'observation', 'non_goal', 'type'),
                    Noun('receiver', 'A new receiver for a join, by namespace address: the join moves and keeps its '
                                     'join_id.', required=False),
                    Noun('provider', 'A new Providing Element for a join, by namespace address.', required=False),
                    Noun(ADDRESS, 'On a subtype join, the namespace_address of another element for it to hold. An '
                                  'element cannot be moved: given for an element, it is not applied.', required=False),
                    *_nouns('role', 'name', 'name_length', 'refs', 'extra'))),
        Verb('remove', remove, 'Remove one recorded element, join or subtype join.',
             nouns=(Noun('id', "An element's namespace_address or element_id, or a join_id, a subtype join's "
                               'included.'),)),
        Verb('finish', finish, 'Finish the intake: every read sees it from now on, and it changes only through a '
                               'correction layer.',
             nouns=(Noun('report', 'Your report on the project you examined: broken code, things that need fixing, '
                                   'anything not working or partially working. On the command line a file is read '
                                   'and - is standard input.', required=False),
                    Noun('feedback', 'Feedback on the Metaform process: bad semantics, a tool that did not match its '
                                     'schema, where you got stuck.', required=False))),
        Verb('status', status_verb, 'Whether this project has an intake, and whether one is being recorded.'),
    ),
    status=status,
)
