"""intake: the intake served by name, recorded one object at a time as it is reasoned, BASE-039.

A subagent reads `intake prompt` and records the map as it works: it starts the
intake, records each element and each purpose record in its own call, anneals a part as an
element held by a purpose record one level deeper, received by the element it is part of, reads the recorded
map back with `intake show`, whole or one receiver at a time, corrects it by
recording again and with `intake remove`, and ends with `intake finish`. The
intake layer is building until then: context reads do not see it, and the web
GUI follows it live.

The map is: an element is its namespace_address,
name_length, name and role; a purpose record is its type, purpose, ef and ifd, held by its
receiver, holding the elements that serve it. An element's refs go in the
sources layer while intake_sources is on. The agent names what it reasoned,
never what the store keeps: an element by its namespace_address and a purpose record by
its receiver and an element it holds; no id reaches the agent. Nothing is
refused for its content: what does not fit is stored as given and named in a
notice, BASE-044. The report and process feedback are saved at the finish,
BASE-045.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Sequence
from contextlib import AbstractContextManager
from dataclasses import replace
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any, BinaryIO, Literal, cast

from metaform import home, prompt_files, settings
from metaform.data import Element, GraphPage, Item, Join, Layer, Node, Notice, Store, StoreError, WorkRecord, as_object
from metaform.module import Context, Module, Noun, Resource, Status, Stop, ToolbarItem, Verb, save_report

from .schema import ELEMENTS, IFD, NAME_LENGTH, REFS, ROLE

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False
REMOTE_AGENT = False  # a project wheel carries a map already built

RESOURCE = resources.files(__name__) / 'resources' / 'intake.axiom'  # the digital typology intake, the served intake
SHAPE = resources.files(__name__) / 'resources' / 'metaform.axiom'  # the metaform's shape
SCHEMA_URI = 'metaform://intake/schema'
VARIABLE = ('The functional map of the artifact: its elements, and each receiver\'s purpose served by a provider\'s '
            'encounter function.')
TARGET = re.compile(r'<target\b[^>]*>')

def _field_words(group: str) -> dict[str, str]:
    """The definition of each field of `group`, element or purpose record, written once in this module's prompts.xml under
    <fields>, MCP-031. The Canonical Intake is not parsed for them: it is the instruction, served as written, and a
    field's definition lives in one place that every tool taking the field shows."""
    import xml.etree.ElementTree as ET
    path = resources.files(__name__) / 'resources' / 'prompts.xml'
    found = ET.fromstring(path.read_text(encoding='utf-8')).find(f'fields/{group}')
    return {} if found is None else {child.tag: (child.text or '').strip() for child in found}


ELEMENT_WORDS, PURPOSE_WORDS = _field_words('element'), _field_words('purpose')

# person_only: the file decides what every intake agent is told to do, so an agent never chooses it.
settings.text('intake_file', '', person_only=True,
              help='An intake file to serve instead of the Canonical Intake. Empty means the Canonical Intake.')


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
    except UnicodeDecodeError:
        raise Stop(f'The intake file {source} is not UTF-8 text.',
                   'save it as UTF-8, or metaform unset --intake-file') from None
    record = store.project()
    match = TARGET.search(text)
    if match is not None:
        tag = _fill(_fill(match.group(0), 'type', record.target_type), 'value', record.target_value)
        text = text[:match.start()] + tag + text[match.end():]
    text = text.replace('{project_id}', record.project_id)
    # What the person asked for, a target or a task; nothing asked leaves it empty, which the intake reads as this
    # project, BASE-039. An intake with a `{prompt}` slot gets the words there, escaped only in an XML intake file.
    # The Axiom intake declares its prompt as a parameter and has no slot, so what was asked follows it as data,
    # the way a skill's input is bound, and the script itself is served as written.
    xml = source.name.lower().endswith('.xml')
    if SCHEMA_URI not in text:  # an agent handed only the procedure is told where its schema is, MCP-009
        text = text.rstrip('\n') + '\n\n' + prompt_files.required(resources.files(__name__), 'schema_pointer') + '\n'
    if '{prompt}' in text:
        text = text.replace('{prompt}', _escape(asked) if xml else asked, 1)
    elif asked:
        text = text.rstrip('\n') + '\n\n<<DATA: Prompt>>\n' + asked + '\n<<END DATA>>\n'
    ignored = home.ignore_patterns(record.path)
    if ignored:  # the one thing added after the intake: what it must not read, from .metaform/ignore.txt
        text = (text.rstrip('\n') + '\n\nDo not read these paths; they are not the project ('
                + home.IGNORE_FILE + '):\n' + '\n'.join(ignored) + '\n')
    return text


def prompt(ctx: Context) -> str:
    return served(ctx, ctx.nouns.get('text') or '')


def schema(ctx: Context) -> str:
    """The shape of the metaform, served as written, so an agent can read the forms it records."""
    return SHAPE.read_text(encoding='utf-8')




# Recording, one object per call ------------------------------------------------------------------------------

Notices = list[dict[str, str]]
ADDRESS = 'namespace_address'  # the element's address, named as in the metaform's shape, MAP-040
SOURCES = 'sources'  # the layer an element's refs go in
# the layer a note given without a condition goes in, beside the map: the base holds RE, PE, OP and EF only, and
# everything else said about a part is critic content, Rich's rule of 2026-10-12
CRITIC = 'critic'
NOTED = 'What the intake noted beside the map'  # the critic layer's variable; the map module declares it the same way
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
    the store names is said in the agent's words, `words`, as an address or a purpose record."""
    for notice in cast(tuple[Notice, ...], getattr(result, 'notices', ()) or ()):
        message = ID.sub(lambda match: (words or {}).get(match.group(0), match.group(0)), notice.message)
        where = {'address': ADDRESS}.get(notice.where, notice.where)
        notices.append({'where': where, 'message': message})


def _said(held: Join) -> str:
    first = held.elements[0].address if held.elements else None
    return f'the purpose record of {held.receiver_address} holding {first}'


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
    """The purpose records of `receiver` in the intake being recorded, or in the metaform when none is, that hold any of
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
        if not path.is_file():
            return value
        return path.read_bytes().decode('utf-8')
    except UnicodeDecodeError:
        notices.append({'where': name, 'message': f'{path} is not UTF-8 text, so its path was saved as the {name}; '
                                                  f'save the file as UTF-8 and finish again, or give the {name} as '
                                                  'text.'})
        return value
    except (OSError, ValueError):  # a value too long or too odd to be a path is the text itself
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


def _open(ctx: Context, store: Store, notices: Notices, named: str = '') -> Recording:
    """A new building intake layer: in the active metaform, or in a new one when that one has an intake, named
    `named` when `intake start` was given a name for what the intake is for."""
    active = store.active_base()
    target, name, is_active = store, active.name if active is not None else 'main', True
    if active is not None and store.has_intake():
        # named from what the intake is for, as the agent gives it at start, else by when it began
        if named and not BASE_NAME.fullmatch(named):
            raise Stop(f'{named!r} is not a name for an intake: use 1 to 64 letters, digits, ., _ and -.',
                       'metaform intake start name=web-interface-refactor')
        fresh = store.add_base(named or f'intake-{_stamp()}', activate=False)
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
    if ctx.nouns.get('result'):  # the result id the procedure generates and gives at start, LAYER-010
        _note(notices, target.complete(layer.name, {}, result_id=str(ctx.nouns['result'])))
    return Recording(target, layer, name, is_active)


def _active_map(store: Store) -> Recording | None:
    """The active metaform's finished intake, when nothing is being recorded: what a verification pass writes to.
    Conditions are work records and refs are items of the sources layer, both kept apart from the map's shape, so they
    are written onto the finished map without opening a new intake."""
    if _building(store) is not None or not store.has_intake():
        return None
    active = store.active_base()
    base = next((layer for layer in store.layers(limit=0).results if layer.kind in ('base', 'intake')), None)
    if active is None or base is None:
        return None
    return Recording(store, base, active.name, True)


SHAPE_FIELDS = ('name_length', 'name', 'role')  # an element's fields that are its shape
VERIFIED = 'intake verification pass'  # the reason a correction to the finished map is refined with
BASE_NAME = re.compile(r'[A-Za-z0-9._-]{1,64}')  # what an intake's metaform may be named, `intake start name=`


def _recording(ctx: Context, notices: Notices) -> Recording:
    """The intake being recorded; a record sent before any start starts one, and says so."""
    store = ctx.require_store()
    found = _building(store)
    if found is not None:
        return found
    made, opened = _opened(ctx, store, notices)
    if opened:
        notices.append({'where': 'intake', 'message': f'No intake was being recorded, so this call started one: '
                                                      f'layer {made.layer.name} in metaform {made.metaform}.'})
    return made


def _lock(store: Store) -> AbstractContextManager[BinaryIO]:
    """The project's intake lock, between processes: a check that no intake is being recorded and the opening of one
    are one step, and a finish is another, so two calls at once never open two, QUAL-001 and BASE-039."""
    folder = home.project_folder(store.project_id)
    if folder is None:
        raise Stop(f'No project {store.project_id} is registered.', 'metaform list projects')
    home.mkdir_private(folder)
    return home.file_lock(folder / 'intake.lock')


def _opened(ctx: Context, store: Store, notices: Notices, named: str = '') -> tuple[Recording, bool]:
    """The intake being recorded, asked again inside the intake lock, or a new one opened there; and whether this call
    opened it, so a call that lost the race to another records into that one."""
    with _lock(store):
        found = _building(store)
        return (found, False) if found is not None else (_open(ctx, store, notices, named), True)


def start(ctx: Context) -> Any:
    """Open the intake layer the records go into, or resume the one already being recorded."""
    store = ctx.require_store()
    notices: Notices = []
    found = _building(store)
    # a name asks for a new intake
    if found is None and (mapped := _active_map(store)) is not None and not ctx.nouns.get('name'):
        notices.append({'where': 'intake', 'message': f'The active metaform {mapped.metaform} has a finished intake. '
                        'Conditions, their notes and refs recorded on its elements and purpose records are written onto it, '
                        'and a changed field of one is refined there, keeping every version. Only a new element or '
                        'purpose record starts a new intake in a new base, kept apart until it finishes.'})
        return {'layer': mapped.layer.name, 'project': store.project_id, 'base': mapped.metaform, 'notices': notices}
    opened = False
    if found is None:
        found, opened = _opened(ctx, store, notices, str(ctx.nouns.get('name') or '').strip())
    if not opened:
        notices.append({'where': 'intake', 'message': f'An intake is already being recorded in layer '
                                                      f'{found.layer.name} of metaform {found.metaform}; this call '
                                                      'resumes it. intake show reads back what it holds.'})
        # What the layer lacks of its provenance is filled in; what it holds is kept, LAYER-010.
        _note(notices, found.store.complete(found.layer.name, {name: ctx.nouns.get(name) for name in ('model', 'role')},
                                            result_id=str(ctx.nouns['result']) if ctx.nouns.get('result') else None))
    return {'layer': found.layer.name, 'project': store.project_id, 'base': found.metaform, 'notices': notices}


def _described(element: Element) -> bool:
    """Whether an element was described with intake element, not only named in a purpose record."""
    return element.role is not None or element.name_length is not None or element.name is not None


def _sources(ctx: Context, rec: Recording, kind: Literal['element', 'join'], element_id: str, address: str,
             refs: list[Any], notices: Notices) -> None:
    """The refs given with an element or a purpose record, written as its one item of the sources layer,
    replacing what that item held:
    refs live in a sources layer, never in the metaform. Off with intake_sources, nothing is written."""
    if not ctx.setting('intake_sources'):
        notices.append({'where': 'refs', 'message': 'intake_sources is off, so the refs were not recorded.'})
        return
    store = rec.store
    store.layer(SOURCES, 'intake', 'refs', kind='layer', mutable=True, hideable=True, ready=True)  # read at once
    held = [item for item in store.layer_items(SOURCES, Node(kind, element_id), limit=0).results
            if isinstance(item, Item)]
    given = [as_object(ref) for ref in refs]
    if len(held) == 1 and not held[0].extra and [(ref.key, ref.value) for ref in held[0].refs] == [
            (each.get('key'), each.get('value')) if each is not None else None for each in given]:
        return  # the refs it holds already, as a verification pass gives them again: nothing to write
    if held:
        _note(notices, store.edit(held[0].id, {'refs': refs}))
        for extra in held[1:]:
            _note(notices, store.remove(extra.id))
    else:
        _note(notices, store.add_item(SOURCES, Node(kind, element_id), address, refs=refs))


def _noted(ctx: Context) -> str | None:
    """The note given without a condition: free text about the part, kept beside the map. A note given with a
    condition is the finding's, a work record, MAP-046."""
    note = ctx.nouns.get('note')
    return str(note) if note and not ctx.nouns.get('condition') else None


def _beside(rec: Recording, kind: Literal['element', 'join'], thing_id: str, note: str, notices: Notices) -> None:
    """A note given with an element or a purpose record, as its one item of the critic layer, replacing what that item
    held: the base holds RE, PE, OP and EF only, so a note is kept beside it, never in it."""
    store = rec.store
    made = store.layer(CRITIC, 'intake', NOTED, kind='layer', mutable=True, hideable=True, ready=True)  # read at once
    held = [item for item in store.layer_items(made.name, Node(kind, thing_id), limit=0).results
            if isinstance(item, Item)]
    if held:
        if held[0].value != note:
            _note(notices, store.edit(held[0].id, {'value': note}))
        for extra in held[1:]:
            _note(notices, store.remove(extra.id))
    else:
        _note(notices, store.add_item(made.name, Node(kind, thing_id), note))


MARKS = {'MISS': 'missing', 'BKN': 'trouble', 'OK': 'ok', 'BROKEN': 'trouble'}  # the procedure's words, any case
INTAKE_MARKS = ('missing', 'trouble', 'ok')


def _checked_condition(ctx: Context) -> None:
    """The intake marks a part missing or trouble, or ok, and nothing else; a mark outside them, or trouble with no
    note saying what is wrong and what corrects it, as the procedure asks of BKN, is refused before anything is
    recorded, so a call is never half kept. The served procedure's conditions are taken as written: MISS, BKN and OK."""
    given = ctx.nouns.get('condition')
    if isinstance(given, str) and given.strip().upper() in MARKS:
        given = ctx.nouns['condition'] = MARKS[given.strip().upper()]
    if given == 'trouble' and not str(ctx.nouns.get('note') or '').strip():
        raise Stop('trouble needs a note saying what is wrong and what corrects it.', 'send it again with note')
    if given in (None, '', 'exclude') or given in INTAKE_MARKS:
        return
    raise Stop(f'{given!r} is not an intake condition: missing, trouble or ok; an exclusion is a note, '
               '"exclude: <why>".', 'send it again with one of those words')


def element(ctx: Context) -> Any:
    """Record one element, or record it again: the fields given replace the ones it had, the rest are kept. An element
    is its namespace_address, name_length, name and role; its refs go in the sources layer."""
    _checked_condition(ctx)
    notices: Notices = []
    address = ctx.nouns[ADDRESS]
    mapped = _active_map(ctx.require_store())
    current_map = mapped.store.element(address, raw=True) if mapped is not None else None
    if mapped is not None and current_map is not None:
        # a field changed on an element of the finished map is refined there, a new version, LAYER-025
        shape = {key: _whole(ctx.nouns.get(key)) for key in SHAPE_FIELDS}
        changed = {key: value for key, value in shape.items()
                   if value is not None and value != getattr(current_map, key)}
        if changed:
            _note(notices, mapped.store.refine(current_map.id, changed, reason=VERIFIED))
        refs = _list(ctx, 'refs')
        if refs is not None:
            _sources(ctx, mapped, 'element', current_map.id, address, refs, notices)
        _condition(ctx, mapped, 'element', current_map.id, notices)
        if (note := _noted(ctx)) is not None:
            _beside(mapped, 'element', current_map.id, note, notices)
        return {ADDRESS: address, 'layer': mapped.layer.name, 'base': mapped.metaform, 'notices': notices}
    rec = _recording(ctx, notices)
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
    if (note := _noted(ctx)) is not None and element_id is not None:
        _beside(rec, 'element', element_id, note, notices)
    refs = _list(ctx, 'refs')
    if refs is not None and element_id is not None:
        _sources(ctx, rec, 'element', element_id, address, refs, notices)
    _condition(ctx, rec, 'element', element_id, notices)
    return {ADDRESS: address, 'layer': rec.layer.name, 'notices': notices}


FIX = {'trouble': 'The intake found this part does not do its job: fix it as the note says.',
       'missing': 'The intake found this part should exist and does not: build it as the note says.'}


def _task(condition: str | None, note: str | None) -> str | None:
    """The task a trouble or missing finding carries, so the agent starter starts an agent on it, MAP-046's amendment
    of 2026-10-14: its note, then what to do. The note comes first, so the ticket's title is still the finding."""
    if condition not in FIX:
        return None
    return f'{note.strip()}\n\n{FIX[condition]}' if note and note.strip() else FIX[condition]


def _finding(row: WorkRecord) -> bool:
    """A work record the intake wrote: no task, or the task built from its own condition and note. Once someone
    rewrites the task it is their ticket, and a condition recorded again leaves it alone."""
    return not row.task or row.task == _task(row.condition, row.note)


def _condition(ctx: Context, rec: Recording, kind: Literal['element', 'join'], thing: str | None,
               notices: Notices, ends: Sequence[str] = ()) -> None:
    """A condition given with what was recorded is an open work record at it, with its note, MAP-046: the missing,
    broken and exclude marks of the intake, apart from the map. A note alone is no finding and opens nothing. Trouble
    and missing carry a task built from the note, so they are tickets an agent starts on. A finding already open with
    the same condition and note on an element and a purpose record it holds or receives, at `ends` of a purpose record,
    is not written twice."""
    if ctx.nouns.get('condition') == 'exclude':  # not a judgment the intake makes: the person's ignore list
        notices.append({'where': 'condition', 'message': f'exclude is the ignore list: {home.IGNORE_FILE}'})
        return
    if thing is None or not ctx.nouns.get('condition'):  # none or empty: no finding; a note is kept on the object
        return
    condition, note = str(ctx.nouns['condition']), ctx.nouns.get('note')
    task = _task(condition, note)
    # A part has one condition: recorded again, as verification does once it has read the source, the new one
    # replaces the last, which closes, so the read-back shows what was found most recently. The same condition
    # recorded again on a finding not yet taken is that finding, kept in place with its id and place on the board.
    # A finding an agent has taken, and a ticket at the part, outlive a new condition recorded there.
    # Read at this one part, not every open record of the project, so an intake's calls stay linear in its size.
    same: list[WorkRecord] = []
    for row in rec.store.work(Node(kind, thing), open=True, limit=0).results:
        if not _finding(row):
            continue
        if row.condition == condition:
            same.append(row)
        elif not row.taken:
            rec.store.finish_work(row.id, f'Replaced by {condition}.')
    if any(row.taken for row in same):
        notices.append({'where': 'condition', 'message': f'{condition} is open here and an agent has taken it; '
                                                         'nothing was added.'})
        return
    if same:
        # a note this ticket already holds, as one a purpose record's marker joined, is kept with what joined it
        if not (note and note.strip() and note.strip() in (same[0].note or '')) and \
                (same[0].note, same[0].task) != (note, task):
            _note(notices, rec.store.edit_work(same[0].id, {'note': note, 'task': task}))
        return
    if kind == 'element':
        around = [row for row in rec.store.work(Node(kind, thing), open=True, limit=0, joins=True).results
                  if row.node_kind == 'join']
    else:
        found = [rec.store.element(address, raw=True) for address in ends]
        around = [row for each in found if each is not None
                  for row in rec.store.work(Node('element', each.id), open=True, limit=0).results]
    # A merged note still holds each original finding, even after an agent takes its ticket.
    for row in around:
        exact = row.condition == condition and row.note == note
        held = task is not None and note and note.strip() and row.condition in FIX and note.strip() in (row.note or '')
        if _finding(row) and (exact or held):
            if row.taken:
                notices.append({'where': 'condition', 'message': f'{condition} is open here and an agent has taken it; '
                                                                 'nothing was added.'})
            elif exact:
                notices.append({'where': 'condition', 'message': 'The same condition and note are open on the element '
                                                                 'and on its purpose record; the finding is kept once.'})
            else:
                notices.append({'where': 'condition', 'message': 'A marker is open on the element and its purpose '
                                                                 f'record; this one is kept in {row.id}.'})
            return
    # An element and its purpose record are one node: a marker there joins the open marker ticket no agent has taken,
    # its note added, so the node has one ticket. One already taken stays as it is, and this one waits behind it.
    joined = next((row for row in around if task is not None and _finding(row) and row.condition in FIX
                   and not row.taken), None)
    if joined is not None:
        if note and note.strip() and note.strip() not in (joined.note or ''):
            merged = f'{joined.note.strip()}\n\n{note.strip()}' if joined.note and joined.note.strip() else note
            _note(notices, rec.store.edit_work(joined.id, {'note': merged, 'task': _task(joined.condition, merged)}))
        notices.append({'where': 'condition', 'message': f'A marker is open on the element and its purpose record; '
                                                         f'this one is kept in {joined.id}.'})
        return
    _note(notices, rec.store.add_work(Node(kind, thing), condition, note=note, task=task))


def _close_work(store: Store, things: set[str], resolution: str) -> None:
    """Close every open work record at these elements and purpose records, which are being removed."""
    for row in store.work(open=True, limit=0).results:
        if row.node_id in things:
            store.finish_work(row.id, resolution)


JOIN_FIELDS = ('purpose', 'ef', 'ifd')


def purpose(ctx: Context) -> Any:
    """Record one purpose record: the receiver's purpose, the ef and the ifd, holding the elements that serve it.
    A purpose record of the receiver that already holds one of the elements is that record: the fields given replace
    its own, and the elements given that it does not hold are added to it."""
    _checked_condition(ctx)
    notices: Notices = []
    receiver = ctx.nouns['receiver']
    elements = _list(ctx, 'elements') or []
    mapped = _active_map(ctx.require_store())
    if mapped is not None and elements:
        held_map = _joins_holding(mapped.store, mapped.layer, receiver, elements)
        holding = [each.address for each in held_map[0].elements] if len(held_map) == 1 else []
        added = [address for address in elements if address not in holding]
        # a purpose record of the finished map is refined there, LAYER-025; an element it would hold that the map
        # lacks is new shape, recorded in a new intake
        if len(held_map) == 1 and all(mapped.store.element(str(address), raw=True) is not None for address in added):
            refined: dict[str, Any] = {key: ctx.nouns[key] for key in JOIN_FIELDS
                                       if ctx.nouns.get(key) is not None
                                       and ctx.nouns.get(key) != getattr(held_map[0], key)}
            if added:
                refined['elements'] = [*holding, *added]
            if refined:
                _note(notices, mapped.store.refine(held_map[0].id, refined, reason=VERIFIED),
                      _words(mapped.store, mapped.layer))
            _join_refs(ctx, mapped, held_map[0].id, receiver, notices)
            if (note := _noted(ctx)) is not None:
                _beside(mapped, 'join', held_map[0].id, note, notices)
            _condition(ctx, mapped, 'join', held_map[0].id, notices, [receiver, *elements])
            return {'receiver': receiver, 'elements': elements, 'layer': mapped.layer.name, 'base': mapped.metaform,
                    'notices': notices}
    if not elements:  # checked before an intake is started or a base opened, since nothing is recorded
        building = _building(ctx.require_store())
        notices.append({'where': 'elements', 'message': 'elements is missing; a purpose record holds the elements '
                                                        'that serve its purpose. A purpose record takes receiver, '
                                                        'elements, purpose, ef and ifd. Nothing was recorded.'})
        return {'receiver': receiver, 'elements': elements,
                'layer': building.layer.name if building is not None else None, 'notices': notices}
    rec = _recording(ctx, notices)
    result = {'receiver': receiver, 'elements': elements, 'layer': rec.layer.name, 'notices': notices}
    words = _words(rec.store, rec.layer)
    found = _joins_holding(rec.store, rec.layer, receiver, elements)
    if len(found) > 1:
        notices.append({'where': 'elements', 'message': f'{receiver} has {len(found)} purpose records holding these elements, '
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
        if (note := _noted(ctx)) is not None:
            _beside(rec, 'join', held.id, note, notices)
        _join_refs(ctx, rec, held.id, receiver, notices)
        _condition(ctx, rec, 'join', held.id, notices, [receiver, *elements])
        return result
    for field in JOIN_FIELDS:
        if ctx.nouns.get(field) is None:
            notices.append({'where': field, 'message': f'{field} is missing; stored empty.'})
    made = rec.store.add_join(rec.layer.name, receiver, elements,
                              **{field: ctx.nouns.get(field) for field in JOIN_FIELDS})
    _note(notices, made, words)
    join_id = getattr(made, 'id', None)
    if join_id is not None and (note := _noted(ctx)) is not None:
        _beside(rec, 'join', join_id, note, notices)
    if join_id is not None:
        _join_refs(ctx, rec, join_id, receiver, notices)
    _condition(ctx, rec, 'join', join_id, notices, [receiver, *elements])
    return result


def _join_refs(ctx: Context, rec: Recording, join_id: str, receiver: str, notices: Notices) -> None:
    """The refs given with a purpose record, as its item of the sources layer, the same way an element's are kept."""
    refs = _list(ctx, 'refs')
    if refs is not None:
        _sources(ctx, rec, 'join', join_id, receiver, refs, notices)


FINISHED = ('The intake is finished, so nothing was changed. The metaform changes by refining, with metaform map '
            'refine, which keeps every version, LAYER-025.')
NOTHING = 'No intake is being recorded. intake start begins one.'


def _element_entry(found: Element, note: str | None = None) -> dict[str, Any]:
    """An element as the read-back shows it, with its note from the critic layer, or the one a base written before
    notes went beside it still holds."""
    entry = {ADDRESS: found.address, 'short_name': found.short_name, 'name_length': found.name_length,
             'name': found.name, 'role': found.role}
    note = note or found.note
    return {**entry, **({'note': note} if note else {})}


def _join_entry(held: Join, note: str | None = None) -> dict[str, Any]:
    entry = {'receiver': held.receiver_address, 'type': held.type, 'purpose': held.purpose, 'ef': held.ef,
             'ifd': held.ifd, 'elements': [each.address for each in held.elements]}
    note = note or held.note
    return {**entry, 'note': note} if note else entry


def _findings(store: Store, elements: list[Element], joins: list[Join]) -> dict[str, dict[str, Any]]:
    """The open condition and note on each recorded element and purpose record, by id, so an agent reads its marks back."""
    ids = {element.id for element in elements} | {held.id for held in joins}
    return {row.node_id: {'condition': row.condition, 'note': row.note}
            for row in store.work(open=True, limit=0).results if row.node_id in ids}


def _refs(store: Store) -> dict[tuple[str, str], list[dict[str, str]]]:
    """Every element's and purpose record's refs, the items of the sources layer at it, by its kind and id, read in one pass
    rather than one read per element; none when there is no sources layer."""
    try:
        held = store.layer_items(SOURCES, limit=0).results
    except StoreError:
        return {}
    found: dict[tuple[str, str], list[dict[str, str]]] = {}
    for item in held:
        if isinstance(item, Item):
            found.setdefault((item.target.kind, item.target.id), []).extend(
                {'key': ref.key, 'value': ref.value} for ref in item.refs)
    return found


def _notes(store: Store) -> dict[tuple[str, str], str]:
    """Every element's and purpose record's note, its item of the critic layer, by its kind and id, read in one pass;
    none when there is no critic layer."""
    try:
        held = store.layer_items(CRITIC, limit=0).results
    except StoreError:
        return {}
    return {(item.target.kind, item.target.id): str(item.value) for item in held
            if isinstance(item, Item) and item.value}


def _map(elements: list[Element], joins: list[Join], store: Store | None = None) -> dict[str, Any]:
    """The recorded map in the agent's words: every element by its address with its refs, every purpose record by its receiver
    with the elements it holds, each with its open condition and note, the CQUs whose root purpose records the map comes off,
    what those purpose records do not reach, and the addresses never described."""
    marks = _findings(store, elements, joins) if store is not None else {}
    refs = _refs(store) if store is not None else {}
    notes = _notes(store) if store is not None else {}
    listed: list[dict[str, Any]] = []
    for found in elements:
        entry = _element_entry(found, notes.get(('element', found.id)))
        if store is not None:
            entry['refs'] = refs.get(('element', found.id), [])
        listed.append({**entry, **marks.get(found.id, {})})
    serves: dict[str, set[str]] = {}  # each receiver, and the elements its purpose records hold
    for held in joins:
        if held.receiver_address is not None:  # an orphaned purpose record's receiver is gone, so it reaches nothing
            serves.setdefault(held.receiver_address, set()).update(each.address for each in held.elements
                                                                   if each.address is not None)
    # the map comes off the root purpose records, each a CQU receiving from the DE; what they do not reach is disconnected
    roots = [found.address for found in elements if found.role == 'CQU' and found.address in serves]
    reached, waiting = set(roots), list(roots)
    while waiting:
        for address in serves.get(waiting.pop(), ()):
            if address not in reached:
                reached.add(address)
                waiting.append(address)

    return {'elements': listed,
            'purposes': [{**_join_entry(held, notes.get(('join', held.id))),
                          **({'refs': refs.get(('join', held.id), [])} if store is not None else {}),
                          **marks.get(held.id, {})} for held in joins],
            'roots': roots,
            'disconnected': [found.address for found in elements if found.address not in reached],
            'undescribed': [found.address for found in elements if not _described(found)]}


def _recorded(store: Store, layer: Layer) -> tuple[list[Element], list[Join]]:
    """What this intake recorded: its elements, with every element its purpose records hold that it wrote,
    and its purpose records."""
    graph: GraphPage = store.layer_graph(layer.name)
    listed = {placed.element.id: placed.element for placed in graph.elements}
    return sorted(listed.values(), key=lambda found: found.address), list(graph.joins)


def show(ctx: Context) -> Any:
    """The intake being recorded, whole or one receiver's purpose records and the elements they hold: to read back, proof and
    correct before finishing, without reading the whole map at once."""
    store = ctx.require_store()
    found = _building(store)
    notices: Notices = []
    if found is None and (found := _active_map(store)) is not None:
        notices.append({'where': 'intake', 'message': f'No intake is being recorded; this is the active metaform '
                                                      f'{found.metaform}, whose intake is finished.'})
    if found is None:
        return {'layer': None, 'project': store.project_id, 'base': None, 'elements': [], 'purposes': [],
                'roots': [], 'disconnected': [], 'undescribed': [],
                'notices': [{'where': 'intake', 'message': NOTHING}]}
    elements, joins = _recorded(found.store, found.layer)
    receiver = ctx.nouns.get('receiver')
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
            'purpose record of that receiver holding that element, and all three to take the element at namespace_address out '
            'of that purpose record.')


def remove(ctx: Context) -> Any:
    """Remove one recorded element, one purpose record, or one element from a purpose record,
    while the intake is being recorded."""
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
            notices.append({'where': 'provider', 'message': f'{named["receiver"]} has {len(held)} purpose records holding '
                                                            f'{named["provider"]}; nothing was changed.'})
        elif ADDRESS in named:
            kept = [each.address for each in held[0].elements if each.address != named[ADDRESS]]
            if len(kept) == len(held[0].elements):
                notices.append({'where': ADDRESS, 'message': f'{_said(held[0])} does not hold {named[ADDRESS]}; '
                                                             'nothing was changed.'})
            else:
                _note(notices, found.store.edit(held[0].id, {'elements': kept}), words)
        else:
            _close_work(found.store, {held[0].id}, 'Its purpose record was removed from the intake.')
            _note(notices, found.store.remove(held[0].id), words)
    elif ADDRESS in named and 'receiver' not in named and 'provider' not in named:
        current = found.store.element(named[ADDRESS], raw=True)
        if current is None:
            notices.append({'where': ADDRESS, 'message': f'{named[ADDRESS]} is not an element; nothing was changed.'})
        else:
            # what held it lets it go, and its marks close with it, so nothing is left orphaned or open; a purpose record
            # left holding nothing is removed, and its marks close too
            gone = {current.id}
            for held in _recorded(found.store, found.layer)[1]:
                if any(each.address == named[ADDRESS] for each in held.elements):
                    kept = [each.address for each in held.elements if each.address != named[ADDRESS]]
                    if not kept:
                        gone.add(held.id)
                    _note(notices, found.store.edit(held.id, {'elements': kept}) if kept
                          else found.store.remove(held.id), words)
            _close_work(found.store, gone, 'Its element was removed from the intake.')
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
    with _lock(store):  # the intake finished is the one being recorded when the lock is held, and none opens meanwhile
        found = _building(store)
        if found is None:
            return {'layer': None, 'project': store.project_id, 'base': None, 'elements': 0, 'purposes': 0, 'work': 0,
                    'notices': notices + [{'where': 'intake', 'message': 'No intake is being recorded; there is '
                                                                         'nothing to finish.'}]}
        elements, joins = _recorded(found.store, found.layer)
        undescribed = [element.address for element in elements if not _described(element)]
        if undescribed:
            notices.append({'where': 'undescribed', 'message': f'{", ".join(undescribed)} '
                                                               f'{"was" if len(undescribed) == 1 else "were"} named in '
                                                               'a purpose record but never described with intake '
                                                               'element; stored without a role or a name_length.'})
        _note(notices, found.store.finish(found.layer.name))
        previous = None
        if not found.active:
            previous = store.active_base()
            store.activate_base(found.metaform)
    if previous is not None:
        notices.append({'where': 'base', 'message': f'This intake was stored as the new active base '
                                                    f'{found.metaform}; the earlier one, {previous.name}, is '
                                                    'kept whole. To switch back: metaform map activate '
                                                    f'{previous.name}'})
        if previous.name != found.metaform:
            # what the map in use until now held that this one does not, so a partial intake is seen at once
            earlier = [placed.element.address for placed in
                       Store(store.project_id, base=previous.id).graph(raw=True, limit=0).elements]
            recorded = {element.address for element in elements}
            lacking = [address for address in earlier if address not in recorded]
            if lacking:
                shown = ', '.join(lacking[:10]) + (f' and {len(lacking) - 10} more' if len(lacking) > 10 else '')
                notices.append({'where': 'elements', 'message': f'This intake holds {len(elements)} elements; '
                                                                f'the map {previous.name} held {len(earlier)}, and '
                                                                f'{len(lacking)} of them are not in it: {shown}.'})
    for kind, text in (('report', report), ('feedback', feedback)):
        if text is not None:
            save_report(store.project_id, found.layer.id, kind, text, store=found.store,
                        layer=found.layer.id)
    # The open work records on what this intake recorded, MAP-046: the condition of an object is apart from the map.
    recorded_ids = {element.id for element in elements} | {held.id for held in joins}
    work = sum(1 for row in found.store.work(open=True, limit=0).results if row.node_id in recorded_ids)
    # A map with a code trunk is ready for its code: the map module reads it into its own layer, P167.
    code = any(element.address.split('.', 1)[0] == 'code' for element in elements)
    follow_on: list[dict[str, Any]] = []
    if code:
        base = found.store.bound_base()
        if base is not None:
            # Optional enrichment receives the committed map, even when this call resolved its project implicitly.
            # The event bus reports subscriber failures without undoing the completed intake.
            follow_on = replace(ctx, project=store.project_id).publish('intake.finished', {
                'project': store.project_id, 'base': base.id, 'layer': found.layer.id, 'code': True,
            })
    return {'layer': found.layer.name, 'project': store.project_id, 'base': found.metaform,
            'elements': len(elements), 'purposes': len(joins), 'work': work, 'notices': notices,
            **({'follow_on': follow_on} if follow_on else {}),
            **({'next': [ctx.calls('metaform map code-import')]} if code else {})}


def _several(store: Store) -> str | None:
    """Every intake being recorded, when there is more than one, with how to keep the one calls record into: one each
    from calls made at once before the intake lock, QUAL-001."""
    building = store.intake_recording().results
    if len(building) < 2:
        return None
    named = ', '.join(f'layer {held.layer.name} of metaform {held.base}' for held in building)
    others = list(dict.fromkeys(held.base for held in building[1:] if held.base != building[0].base))
    removal = ('; remove each other one: ' + '; '.join(f'metaform map remove-base {name}' for name in others)
               if others else '')
    return (f'{len(building)} intakes are being recorded: {named}. Calls record into and finish the first, in '
            f'metaform {building[0].base}{removal}.')


def status_verb(ctx: Context) -> str:
    store = ctx.require_store()
    found = _building(store)
    lines: list[str] = []
    if store.has_intake():
        latest = store.layers(kind='intake', limit=0).results[-1]
        lines.append(f'This project has an intake. Latest intake layer: {latest.name}')
    if found is not None:
        lines.append(f'An intake is being recorded in layer {found.layer.name} of metaform {found.metaform}.')
    if (several := _several(store)) is not None:
        lines.append(several)
    if not lines:
        lines.append('No intake yet. Read the instructions with metaform intake prompt.')
    return '\n'.join(lines) + '\n'


def status(ctx: Context) -> Status:
    here = resources.files(__name__)
    if os.environ.get('METAFORM_ROLE') not in (None, '', 'none'):
        # An agent a dispatch runner started has its work, given as its first turn: the intake's onboarding, which
        # asks an agent to handle it first, is for the person's own agent, never for one dispatched, BASE-052.
        if ctx.store is None:
            return Status()
        return Status(lines=('Intake: complete' if ctx.store.has_intake() else 'Intake: none yet',))
    if ctx.store is None:
        # A folder not registered yet gets the onboarding too, with registering as its first step: the instructions
        # are sent once at connect, so a notice that waited for registration would never arrive, MCP-009.
        step = '   ' + prompt_files.required(here, 'register_step') + '\n'
        return Status(instruction=prompt_files.required(here, 'no_intake', register=step))
    found = _building(ctx.store)
    several = _several(ctx.store)
    recording = (f'Intake: being recorded in layer {found.layer.name} of metaform {found.metaform}',
                 *((several,) if several is not None else ())) if found is not None else ()
    # The instructions agents read name an intake started and not finished, or else a project with no intake, MCP-009.
    unfinished = prompt_files.required(here, 'unfinished') if found is not None else None
    if ctx.store.has_intake():
        return Status(lines=('Intake: complete', *recording), instruction=unfinished)
    if found is not None:
        return Status(lines=recording, instruction=unfinished)
    return Status(lines=('Intake: none yet',), instruction=prompt_files.required(here, 'no_intake'))


E, P = ELEMENT_WORDS.get, PURPOSE_WORDS.get
def _condition_nouns(words: Any) -> tuple[Noun, Noun]:
    """The condition and the note an element or a purpose record is recorded with, each in that command's own words."""
    return (Noun('condition', words('condition', ''), required=False,
                 schema={'type': 'string', 'enum': ['MISS', 'BKN', 'OK', 'broken', *INTAKE_MARKS]}),  # the procedure's word or its stored one
            Noun('note', words('note', ''), required=False))

MODULE = Module(
    id='intake',
    summary='Serve the intake and record its result as it is reasoned.',
    purpose='Serves the intake instructions, records the intake as it is reasoned, and tracks whether this project '
            'has an intake. The intake is agent work: a subagent reads its instructions with the command prompt and '
            'follows them. Details: metaform help intake.',
    details='The intake text is served as stored, with its prompt slot filled. The intake is recorded as it is '
            "reasoned, one element or purpose record per call, in the metaform's shape: an element is its namespace_address, "
            'name_length, name and role; a purpose record is the receiver\'s purpose, the ef and the ifd, holding the elements '
            'that serve it. An element\'s refs go in the sources layer while intake_sources is on. It is read back '
            'with show, whole or one receiver at a time, and corrected by recording again and with remove. No other '
            'read sees it until finish; after finish the metaform changes by refining, metaform map refine, in the '
            'same layer, or by another intake, which writes conditions, notes and refs onto it and opens a new base '
            'only for new shape. Nothing is refused for its content: what does not fit is stored as given and named '
            'in a notice.',
    verbs=(
        Verb('prompt', prompt, "Read the intake instructions an agent follows to record this project's map.",
             nouns=(Noun('text', 'path to the target for the intake process; leaving this blank means this project',
                         required=False),), effect='read'),
        Verb('schema', schema, 'Read the shape the intake records: namespace roots, Upstream and Downstream links, '
                               'element and purpose forms.', effect='read'),
        Verb('start', start, "Start recording this project's intake, or resume the one being recorded. On a project "
                             'whose intake is finished it stays on that map: conditions, notes and refs are written '
                             'onto it, and recording a new element or purpose record opens a separate intake-<UTC timestamp> '
                             'metaform, keeping the earlier one untouched. Returns its name; the existing web GUI '
                             'follows it live.',
             nouns=(Noun('result', 'The result id the intake procedure generates and gives at start, kept with the intake.', required=False),
                    Noun('name', "On a project that has an intake already, the new intake's metaform is named for what it is "
                                 "for, from the person's request, such as web-interface-refactor: 1 to 64 letters, digits, "
                                 "., _ and -. Given, it opens that new intake at once; with none, intake-<UTC timestamp>.",
                         required=False),
                    Noun('model', 'The model that performs the intake.', required=False),
                    Noun('role', 'The role of the agent that performs it.', required=False))),
        Verb('element', element, 'Record one element of the intake at its address; recording it again replaces the '
                                 'fields given.',
             nouns=(Noun(ADDRESS, E(ADDRESS, '')),
                    Noun('name_length', E('name_length', ''), required=False, schema=NAME_LENGTH),
                    Noun('name', E('name', ''), required=False),
                    Noun('role', E('role', ''), required=False, schema=ROLE),
                    Noun('refs', E('refs', ''), required=False, schema=REFS),
                    *_condition_nouns(E))),
        Verb('purpose', purpose, "Record one purpose record: a receiver's OP and the elements that serve it, with its EF. "
                                 'Recorded again with an element it holds, the fields given replace its own and new '
                                 'elements are added.',
             nouns=(Noun('receiver', P('receiver', '')),
                    Noun('elements', P('elements', ''), schema=ELEMENTS),
                    Noun('purpose', P('purpose', ''), required=False),
                    Noun('ef', P('ef', ''), required=False),
                    Noun('ifd', P('ifd', ''), required=False, schema=IFD),
                    Noun('refs', P('refs', ''), required=False, schema=REFS),
                    *_condition_nouns(P))),
        Verb('show', show, 'Read the intake being recorded, whole or one receiver at a time.',
             nouns=(Noun('receiver', P('receiver', ''), required=False),), effect='read'),
        Verb('remove', remove, 'Remove one element, one purpose record, or one element from a purpose record, from '
                               'the intake being recorded. Each is named by addresses.',
             nouns=(Noun('receiver', P('receiver', ''), required=False),
                    Noun('provider', P('provider', ''), required=False),
                    Noun(ADDRESS, E(ADDRESS, ''), required=False)), effect='remove'),
        Verb('finish', finish, 'Finish the intake and make its base the active map, keeping the earlier one whole. '
                               'Switch back with metaform map activate <previous-name>. After finish the metaform '
                               'changes by refining, metaform map refine, or by another intake.',
             nouns=(Noun('report', 'Your report on the project you examined: broken code, things that need fixing, '
                                   'anything not working or partially working. On the command line a file is read '
                                   'and - is standard input.', required=False),
                    Noun('feedback', 'Feedback on the Metaform process: bad semantics, a tool that did not match its '
                                     'schema, where you got stuck.', required=False)),
             open_world=True),  # its intake.finished subscriber, source_placement's, can start a run that sends to Jev
        Verb('status', status_verb, 'Say whether this project has an intake, and whether one is being recorded.',
             effect='read'),
    ),
    status=status,
    resources=(
        Resource('metaform://intake/procedure', 'Intake procedure',
                 'The intake instructions for this project, the procedure an intake follows. Read before intake start.',
                 'prompt'),
        Resource('metaform://intake/schema', 'Intake forms',
                 'The shape of the metaform: the namespace roots, the links, and the element and purpose forms intake '
                 'element and intake purpose record.', 'schema'),
    ),
    # A map starts with an intake and is checked against the project with another; the page's dialog starts it.
    toolbar=(
        ToolbarItem('intake', 'Run an intake', 'Start an agent recording the map as it reads the project, or checking '
                    'the map against it.', icon='spark', page='intake', order=90),
    ),
)
