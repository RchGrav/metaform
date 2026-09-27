"""intake: the Canonical Intake served by name, recorded one object at a time as it is reasoned, BASE-039.

A subagent reads `intake prompt` and records the map as it works: it starts the
intake, then records each element, join and subtype join in its own call, reads
the recorded map back with `intake show`, corrects it with `intake edit` and
`intake remove`, and ends with `intake finish`. The intake layer is building
until then: context reads do not see it, and the web GUI follows it live.
Nothing is refused for its content: what does not fit is stored as given and
named in a notice, BASE-044. The report and process feedback are saved at the
finish, BASE-045.
"""
from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Any, cast

from metaform import settings
from metaform.data import ROLES, Element, GraphPage, Layer, Notice, Store, Subtype
from metaform.module import Context, Module, Noun, Status, Stop, Verb, save_report

from .schema import EF, EXTRA, FLAG, NAME_LENGTH, REFS, ROLE, SUBTYPE_ROLE

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False

RESOURCE = resources.files(__name__) / 'resources' / 'Canonical_Intake.xml'
ALWAYS = ('Do not read past memories or any other details other than the material targeted for intake. Record each '
          'element as you work through the process. Use intake_start first, then intake_element, intake_join and '
          'intake_subtype, or metaform intake start, element, join and subtype on the command line. Read it back with '
          'intake_show, correct it with intake_edit and intake_remove, and end with intake_finish. If you cannot '
          'continue, stop and submit a trouble report with the feedback tool, attaching what you have in its shape '
          'field; do not retry.')
REPORT_LINE = ('Include your report on the project you examined in the report field of intake_finish: broken code, '
               'things that need fixing, anything not working or partially working.')
DEBUG_LINE = ('Include feedback on this process in the feedback field of intake_finish: bad semantics, a tool that '
              'did not match its schema, where you got stuck.')
NOTICE = ('This project has no intake yet. Have a subagent perform it. Tell the subagent to read its instructions '
          'with `metaform intake prompt`, or the `intake_prompt` tool, and to follow them.')
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


def footer(ctx: Context) -> str:
    """The recording lines: always how to record and the stop rule, then the report and feedback requests, CLI-034."""
    lines = [ALWAYS]
    if ctx.setting('report'):
        lines.append(REPORT_LINE)
    if ctx.setting('debug'):
        lines.append(DEBUG_LINE)
    return '\n'.join(lines) + '\n'


def served(ctx: Context) -> str:
    """The intake text exactly as stored, with its target filled, then the recording lines, BASE-039."""
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
    return text + ('\n' if text.endswith('\n') else '\n\n') + footer(ctx)


def prompt(ctx: Context) -> str:
    return served(ctx)




# Recording, one object per call ------------------------------------------------------------------------------

Notices = list[dict[str, str]]
JOIN_TEXT = ('purpose', 'function', 'ef', 'relation', 'verb', 'observation')
SUBTYPE_TEXT = ('function', 'ef', 'relation', 'verb', 'observation')
DESCRIPTOR = ('name', 'name_length', 'role')


class Recording:
    """The intake being recorded: the store of its metaform, its building layer, and that metaform."""

    def __init__(self, store: Store, layer: Layer, metaform: str, active: bool) -> None:
        self.store, self.layer, self.metaform, self.active = store, layer, metaform, active


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def _note(notices: Notices, result: Any) -> None:
    """A store result's notices, each named by the field it is about."""
    for notice in cast(tuple[Notice, ...], getattr(result, 'notices', ()) or ()):
        notices.append({'where': notice.where, 'message': notice.message})


def _text(ctx: Context, name: str, notices: Notices) -> str | None:
    value = ctx.nouns.get(name)
    if value is None or isinstance(value, str):
        return value
    notices.append({'where': name, 'message': f'{name} is not text; it was stored as its JSON text.'})
    return json.dumps(value, ensure_ascii=False)


def _json(ctx: Context, name: str) -> tuple[Any, bool]:
    """A JSON field: the value over MCP, its text parsed on the command line. False when the text does not parse."""
    value = ctx.nouns.get(name)
    if isinstance(value, str):
        try:
            return json.loads(value), True
        except ValueError:
            return value, False
    return value, True


def _pair(ref: Any) -> tuple[str, str] | None:
    if isinstance(ref, dict):
        given = cast(dict[str, Any], ref)
        key, value = given.get('key'), given.get('value')
    elif isinstance(ref, (list, tuple)) and len(cast(list[Any], ref)) == 2:
        key, value = cast(list[Any], ref)
    else:
        return None
    return (key, value) if isinstance(key, str) and isinstance(value, str) else None


def _refs_and_extra(ctx: Context, notices: Notices) -> tuple[list[tuple[str, str]] | None, dict[str, Any] | None]:
    """The refs as key and value pairs, and the extra; what does not fit either is kept in the extra, BASE-044."""
    extra, parsed = _json(ctx, 'extra')
    if extra is not None and not (parsed and isinstance(extra, dict)):
        notices.append({'where': 'extra', 'message': 'extra is not a JSON object; it was kept in the extra under '
                                                     'extra.'})
        extra = {'extra': extra}
    refs, parsed = _json(ctx, 'refs')
    if refs is None:
        return None, cast(dict[str, Any] | None, extra)
    pairs: list[tuple[str, str]] = []
    odd: list[Any] = []
    for ref in (cast(list[Any], refs) if parsed and isinstance(refs, list) else [refs]):
        pair = _pair(ref)
        if pair is None:
            odd.append(ref)
        else:
            pairs.append(pair)
    if odd:
        notices.append({'where': 'refs', 'message': f'A ref is a key and a value, both text; {len(odd)} '
                                                    f'{"was" if len(odd) == 1 else "were"} not, and kept in the '
                                                    'extra under refs.'})
        extra = {**cast(dict[str, Any], extra or {}), 'refs': odd}
    return pairs, cast(dict[str, Any] | None, extra)


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
    else:
        found = _open(ctx, store, notices)
    return {'layer': found.layer.name, 'project': store.project_id, 'metaform': found.metaform, 'notices': notices}


def _own_descriptor(element: Element | None, layer: Layer) -> Any:
    if element is None:
        return None
    return next((found for found in element.descriptors if found.layer_id == layer.layer_id), None)


def _describe(rec: Recording, address: str, given: dict[str, Any], refs: list[tuple[str, str]] | None,
              extra: dict[str, Any] | None, notices: Notices) -> str | None:
    """Record an element, or describe it again: the fields given replace the ones it had, the rest are kept."""
    current = rec.store.element(address, raw=True)
    own = _own_descriptor(current, rec.layer)
    role = given.get('role')
    if role is None and (own is None or own.role is None):
        notices.append({'where': 'role', 'message': 'role is missing; the element was stored without a role.'})
    if own is None:
        made = rec.store.add_element(rec.layer.name, address, name=given.get('name'),
                                     name_length=given.get('name_length'), role=role, refs=refs or (), extra=extra,
                                     flag=given.get('flag'), flag_note=given.get('flag_note'))
        _note(notices, made)
        if current is not None and extra is not None:
            _note(notices, rec.store.edit(current.element_id, {'extra': extra}))
        return getattr(made, 'element_id', None)
    assert current is not None
    if role is not None and role not in ROLES:
        notices.append({'where': 'role', 'message': f'{role!r} is not AUE, VE, DE, SE or NE; it was stored as '
                                                    'given.'})
    known = {'name': own.name, 'name_length': own.name_length, 'role': own.role}
    merged = {key: value for key, value in {**known, **{key: given[key] for key in DESCRIPTOR
                                                        if given.get(key) is not None}}.items() if value is not None}
    changes: dict[str, Any] = {'value': {'descriptor': merged}}
    if refs is not None:
        changes['refs'] = refs
    _note(notices, rec.store.edit(own.item_id, changes))
    if given.get('flag') is not None:
        _note(notices, rec.store.reflag(current.element_id, given['flag'], given.get('flag_note')))
    if extra is not None:
        _note(notices, rec.store.edit(current.element_id, {'extra': extra}))
    return current.element_id


def element(ctx: Context) -> Any:
    """Record one element, or describe again one already recorded."""
    notices: Notices = []
    rec = _recording(ctx, notices)
    refs, extra = _refs_and_extra(ctx, notices)
    given = {name: ctx.nouns.get(name) for name in ('name', 'role', 'flag', 'flag_note')}
    given['name_length'] = _whole(ctx.nouns.get('name_length'))
    address = ctx.nouns['address']
    made = _describe(rec, address, given, refs, extra, notices)
    return {'element_id': made, 'address': address, 'layer': rec.layer.name, 'notices': notices}


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
                              **{name: ctx.nouns.get(name) for name in (*JOIN_TEXT, 'non_goal')},
                              type=ctx.nouns.get('type') or 'purpose', refs=refs or (), extra=extra,
                              flag=ctx.nouns.get('flag'), flag_note=ctx.nouns.get('flag_note'))
    _note(notices, made)
    return {'join_id': getattr(made, 'join_id', None), 'receiver': receiver, 'provider': provider,
            'layer': rec.layer.name, 'notices': notices}


def subtype(ctx: Context) -> Any:
    """Record one subtype join inside its parent join: an absorbed subpart with its own encounter function."""
    notices: Notices = []
    rec = _recording(ctx, notices)
    refs, extra = _refs_and_extra(ctx, notices)
    _missing(ctx, SUBTYPE_TEXT, notices)
    address = ctx.nouns['address']
    made = rec.store.add_subtype(rec.layer.name, ctx.nouns['join'], address,
                                 **{name: ctx.nouns.get(name) for name in (*SUBTYPE_TEXT, 'name', 'role', 'purpose',
                                                                           'flag', 'flag_note')},
                                 name_length=_whole(ctx.nouns.get('name_length')), refs=refs or (), extra=extra)
    _note(notices, made)
    return {'subtype_id': getattr(made, 'subtype_id', None), 'join_id': ctx.nouns['join'], 'address': address,
            'layer': rec.layer.name, 'notices': notices}


def _refs(found: Any) -> list[dict[str, str]]:
    return [{'key': ref.key, 'value': ref.value} for ref in (found or ())]


def _map(graph: GraphPage, layer: Layer) -> dict[str, Any]:
    """The recorded map: every element, join and subtype join with its id, and the elements never described."""
    elements: list[dict[str, Any]] = []
    undescribed: list[str] = []
    for placed in graph.elements:
        found = placed.element
        own = _own_descriptor(found, layer)
        if own is None:
            undescribed.append(found.address)
        elements.append({'id': found.element_id, 'address': found.address, 'role': found.role, 'name': found.name,
                         'name_length': found.name_length, 'refs': _refs(own.refs if own else ()),
                         'flag': found.flag, 'flag_note': found.flag_note, 'extra': found.extra})
    joins = [{'id': held.join_id, 'receiver': held.receiver_address, 'provider': held.provider_address,
              'type': held.type, **{name: getattr(held, name) for name in (*JOIN_TEXT, 'non_goal')},
              'refs': _refs(held.refs), 'flag': held.flag, 'flag_note': held.flag_note, 'extra': held.extra}
             for held in graph.joins]
    inside: list[Subtype] = [item for held in graph.joins for item in held.subtypes]
    subtypes = [{'id': item.subtype_id, 'join': item.join_id, 'address': item.address, 'role': item.role,
                 'name': item.name, 'name_length': item.name_length,
                 **{name: getattr(item, name) for name in SUBTYPE_TEXT}, 'refs': _refs(item.refs), 'flag': item.flag,
                 'flag_note': item.flag_note, 'extra': item.extra} for item in inside]
    return {'elements': elements, 'joins': joins, 'subtypes': subtypes, 'undescribed': undescribed}


NOTHING = 'No intake is being recorded. intake start begins one.'


def show(ctx: Context) -> Any:
    """The intake being recorded, whole: to read back, proof and correct before finishing."""
    store = ctx.require_store()
    found = _building(store)
    if found is None:
        return {'layer': None, 'project': store.project_id, 'metaform': None, 'elements': [], 'joins': [],
                'subtypes': [], 'undescribed': [], 'notices': [{'where': 'intake', 'message': NOTHING}]}
    return {'layer': found.layer.name, 'project': store.project_id, 'metaform': found.metaform,
            **_map(found.store.layer_graph(found.layer.name), found.layer), 'notices': []}


EDITS = ('provider', 'type', 'purpose', 'function', 'ef', 'relation', 'verb', 'observation', 'non_goal', 'address',
         'name', 'role')


def edit(ctx: Context) -> Any:
    """Change one recorded element, join or subtype join in place while the intake is being recorded."""
    store = ctx.require_store()
    notices: Notices = []
    found = _building(store)
    target = found.store if found is not None else store
    refs, extra = _refs_and_extra(ctx, notices)
    thing = ctx.nouns['id']
    changes = {name: ctx.nouns[name] for name in EDITS if ctx.nouns.get(name) is not None}
    if ctx.nouns.get('name_length') is not None:
        changes['name_length'] = _whole(ctx.nouns['name_length'])
    flag, flag_note = ctx.nouns.get('flag'), ctx.nouns.get('flag_note')
    current = target.element(thing, raw=True)
    if current is not None and found is not None:
        given = {key: changes.pop(key) for key in DESCRIPTOR if key in changes}
        if given or refs is not None or flag is not None or extra is not None:
            _describe(found, current.address, {**given, 'role': given.get('role'), 'flag': flag,
                                               'flag_note': flag_note}, refs, extra, notices)
            notices[:] = [notice for notice in notices if not notice['message'].startswith('role is missing')]
        if changes:
            _note(notices, target.edit(current.element_id, changes))
    else:
        owner = current.element_id if current is not None else thing
        if refs is not None:
            changes['refs'] = refs
        if extra is not None:
            changes['extra'] = extra
        if changes or flag is None:
            _note(notices, target.edit(owner, changes))
        if flag is not None:
            _note(notices, target.reflag(owner, flag, flag_note))
    return {'id': thing, 'layer': found.layer.name if found is not None else None, 'notices': notices}


def remove(ctx: Context) -> Any:
    """Remove one recorded element, join or subtype join while the intake is being recorded."""
    store = ctx.require_store()
    notices: Notices = []
    found = _building(store)
    target = found.store if found is not None else store
    thing = ctx.nouns['id']
    current = target.element(thing, raw=True)
    if current is not None and found is not None:
        own = _own_descriptor(current, found.layer)
        if own is not None:
            target.remove(own.item_id)
    _note(notices, target.remove(current.element_id if current is not None else thing))
    return {'id': thing, 'layer': found.layer.name if found is not None else None, 'notices': notices}


def finish(ctx: Context) -> Any:
    """Finish the intake: its layer becomes the metaform's intake, seen by every read, and cannot change in place."""
    store = ctx.require_store()
    notices: Notices = []
    report = _text(ctx, 'report', notices)
    feedback = _text(ctx, 'feedback', notices)
    found = _building(store)
    if found is None:
        return {'layer': None, 'project': store.project_id, 'metaform': None, 'elements': 0, 'joins': 0,
                'subtypes': 0, 'refs': 0, 'findings': 0,
                'notices': notices + [{'where': 'intake', 'message': 'No intake is being recorded; there is nothing '
                                                                     'to finish.'}]}
    recorded = _map(found.store.layer_graph(found.layer.name), found.layer)
    if recorded['undescribed']:
        names = recorded['undescribed']
        notices.append({'where': 'undescribed', 'message': f'{", ".join(names)} {"was" if len(names) == 1 else "were"} '
                                                           'recorded as the end of a join but never described with '
                                                           'intake element; stored without a role or a name.'})
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
    findings = len(found.store.findings(layer=found.layer.name, raw=True, limit=0).results)
    refs = sum(len(row['refs']) for kind in ('elements', 'joins', 'subtypes') for row in recorded[kind])
    return {'layer': found.layer.name, 'project': store.project_id, 'metaform': found.metaform,
            'elements': len(recorded['elements']), 'joins': len(recorded['joins']),
            'subtypes': len(recorded['subtypes']), 'refs': refs, 'findings': findings, 'notices': notices}


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
    Noun('flag', 'missing, broken or cruft; leave it out for a working object.', required=False, schema=FLAG),
    Noun('flag_note', 'A short note on the finding.', required=False),
    Noun('extra', 'Any other field, as a JSON object, kept in the extra.', required=False, schema=EXTRA),
    Noun('type', 'The join type: purpose.', required=False),
    Noun('purpose', 'State the intended goal, standard, or reason why this element or action is needed.',
         required=False),
    Noun('function', "Encounter Function of the Providing Element serving this VE's OP.", required=False),
    Noun('ef', 'Function if it is the encounter of a functionality, Encounter if it is the functionality of the '
               'encounter.', required=False, schema=EF),
    Noun('relation', 'Active-voice descriptive fragment starting directly with a third-person singular present-tense '
                     'verb ending in -s/-es; its subject is the Providing Element when ef is Function, the Vested '
                     'Entity when ef is Encounter.', required=False),
    Noun('verb', 'Third-person singular present-tense active verb ending in -s or -es.', required=False),
    Noun('observation', 'State the actual real-world condition, format, layout, or limitations of what is there.',
         required=False),
    Noun('non_goal', 'State what this element or action is explicitly NOT trying to do, fix, or include.',
         required=False),
)}
SUBTYPE_NOUNS = (
    Noun('join', 'The id of the parent join it lives inside, as intake join returned it.'),
    Noun('address', 'The namespace address of the absorbed subtype.'),
    Noun('function', 'Encounter Function of the subtype within the parent.', required=False),
    NOUNS['ef'],
    Noun('relation', 'Active-voice descriptive fragment starting directly with a third-person singular present-tense '
                     'verb ending in -s/-es; its subject is the Providing Element when ef is Function, the Receiving '
                     'Entity when ef is Encounter.', required=False),
    NOUNS['verb'],
    Noun('observation', 'State the actual real-world condition, format, layout, or limitations of the subtype.',
         required=False),
    Noun('role', 'DE, SE or NE.', required=False, schema=SUBTYPE_ROLE),
    *_nouns('name', 'name_length', 'refs', 'flag', 'flag_note'),
    Noun('purpose', "A subtype join has no purpose; its parent join carries it. Given, it is kept in the subtype's "
                    'extra.', required=False),
    NOUNS['extra'],
)

MODULE = Module(
    id='intake',
    summary='Serve the Canonical Intake and record its result as it is reasoned.',
    purpose='Serves the Canonical Intake instructions, records the intake as it is reasoned, and tracks whether this '
            'project has an intake. The intake is agent work: a subagent reads its instructions with intake_prompt '
            'and follows them. Details: metaform help intake.',
    details='The intake text is served unchanged except for its filled target. The intake is recorded as it is '
            'reasoned, one element, join or subtype join per call, into one building intake layer, read back with '
            'show and corrected with edit and remove. No other read sees it until finish; after finish it changes '
            'only through a correction layer. Nothing is refused for its content: what does not fit is stored as '
            'given and named in a notice.',
    verbs=(
        Verb('prompt', prompt, 'The Canonical Intake instructions for this project.', switches=('report', 'debug')),
        Verb('start', start, 'Start recording an intake, or resume the one being recorded.',
             nouns=(Noun('model', 'The model that performs the intake.', required=False),
                    Noun('role', 'The role of the agent that performs it.', required=False),
                    Noun('blinded', 'Whether the agent sees only the map.', kind='bool', required=False),
                    Noun('id', "The result's generated id.", required=False))),
        Verb('element', element, 'Record one element, or describe again one already recorded.',
             nouns=(Noun('address', "The element's namespace address, its identity."),
                    *_nouns('role', 'name', 'name_length', 'refs', 'flag', 'flag_note', 'extra'))),
        Verb('join', join, "Record one join: the receiver's purpose served by the provider's encounter function.",
             nouns=(Noun('receiver', 'The namespace address of the Vested Entity whose Operative Purpose this join '
                                     'states.'),
                    Noun('provider', 'The namespace address of the Providing Element.'),
                    *_nouns('purpose', 'function', 'ef', 'relation', 'verb', 'observation', 'non_goal', 'type',
                            'refs', 'flag', 'flag_note', 'extra'))),
        Verb('subtype', subtype, 'Record one subtype join inside its parent join.', nouns=SUBTYPE_NOUNS),
        Verb('show', show, 'The intake being recorded, whole, with the ids to edit or remove.'),
        Verb('edit', edit, 'Change one recorded element, join or subtype join; the fields given replace the ones it '
                           'had.',
             nouns=(Noun('id', 'An element address or id, a join id or a subtype id.'),
                    *_nouns('purpose', 'function', 'ef', 'relation', 'verb', 'observation', 'non_goal', 'type'),
                    Noun('provider', 'A new Providing Element, by namespace address.', required=False),
                    Noun('address', 'A new namespace address for an element or a subtype.', required=False),
                    *_nouns('role', 'name', 'name_length', 'refs', 'flag', 'flag_note', 'extra'))),
        Verb('remove', remove, 'Remove one recorded element, join or subtype join.',
             nouns=(Noun('id', 'An element address or id, a join id or a subtype id.'),)),
        Verb('finish', finish, 'Finish the intake: every read sees it from now on, and it changes only through a '
                               'correction layer.',
             nouns=(Noun('report', 'Your report on the project you examined: broken code, things that need fixing, '
                                   'anything not working or partially working.', required=False),
                    Noun('feedback', 'Feedback on the Metaform process: bad semantics, a tool that did not match its '
                                     'schema, where you got stuck.', required=False))),
        Verb('status', status_verb, 'Whether this project has an intake, and whether one is being recorded.'),
    ),
    status=status,
)
