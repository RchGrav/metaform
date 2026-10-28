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

import hashlib
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
from metaform.data import (
    Column,
    Element,
    GraphPage,
    Item,
    Join,
    Layer,
    Node,
    Notice,
    Store,
    StoreError,
    Table,
    Tables,
    author,
)
from metaform.module import (
    Context,
    Module,
    Noun,
    Provides,
    Resource,
    Status,
    Stop,
    ToolbarItem,
    Verb,
    prepare_agent_context,
    project_for,
    save_report,
)

from .schema import ELEMENTS, IFD, NAME_LENGTH, REFS, ROLE

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False
REMOTE_AGENT = False  # a project wheel carries a map already built

RESOURCE = resources.files(__name__) / 'resources' / 'intake.xml'
SHAPE = resources.files(__name__) / 'resources' / 'metaform.xml'
SCHEMA_URI = 'metaform://intake/schema'
PROCEDURE_URI = 'metaform://intake/procedure'
VARIABLE = ('The functional map of the artifact: its elements, and each receiver\'s purpose served by a provider\'s '
            'encounter function.')

def _field_words(group: str) -> dict[str, str]:
    """The definition of each field of `group`, element or purpose record, written once in this module's prompts.xml under
    <fields>, MCP-031. The Canonical Intake is not parsed for them: it is the instruction, served as written, and a
    field's definition lives in one place that every tool taking the field shows."""
    import xml.etree.ElementTree as ET
    path = resources.files(__name__) / 'resources' / 'prompts.xml'
    found = ET.fromstring(path.read_text(encoding='utf-8')).find(f'fields/{group}')
    return {} if found is None else {child.tag: (child.text or '').strip() for child in found}


ELEMENT_WORDS, PURPOSE_WORDS = _field_words('element'), _field_words('purpose')

settings.text('intake_file', '',
              help='Optional UTF-8 instruction file for the intake task. Its contents are read as text.')


def task_component(ctx: Context, **bindings: str) -> dict[str, Any]:
    """Resolve one editable intake task prompt without interpreting its contents."""
    chosen = ctx.setting('intake_file')
    source: Any = Path(chosen).expanduser() if chosen else RESOURCE
    try:
        raw = source.read_bytes()
        text = raw.decode('utf-8')
    except OSError:
        raise Stop(f'No intake file at {source}.', 'metaform unset --intake-file') from None
    except UnicodeDecodeError:
        raise Stop(f'The intake file {source} is not UTF-8 text.',
                   'save it as UTF-8, or metaform unset --intake-file') from None
    key = ('prompt.intake:source-' + hashlib.sha256(str(source).encode()).hexdigest() + '.txt'
           if chosen else 'prompt.intake:intake.xml')
    component = prompt_files.resolve_text(key, text, **bindings)
    component['source'] = {**component['source'], 'path': str(source), 'configured_file': bool(chosen)}
    return component


def procedure_component(ctx: Context) -> dict[str, Any]:
    """The same complete instruction text used by the assigned intake task."""
    component = task_component(ctx, **{'{project}': ctx.project or ctx.folder.name})
    component['read'] = {'uri': PROCEDURE_URI}
    return component


def tool_instructions(ctx: Context, tool: str, op: str | None) -> list[dict[str, Any]]:
    """Contribute the actual procedure before intake writes through the shared instruction mechanism."""
    if tool not in ('intake_start', 'intake_element', 'intake_purpose', 'intake_remove', 'intake_finish'):
        return []
    component = procedure_component(ctx)
    return [component] if component['text'].strip() else []


def _with_request(ctx: Context, component: dict[str, Any], asked: str) -> str:
    """Append request data while leaving the selected instructions intact."""
    launch = _own_launch(ctx.store) if ctx.store is not None else None
    mode = str(launch.get('mode') or '') if launch else str(ctx.nouns.get('mode') or '')
    if mode:
        if mode not in ('fresh', 'refine', 'resume'):
            raise Stop('Intake mode is fresh, refine or resume.', 'metaform help intake prompt')
        asked = prompt_files.required(resources.files(__name__), 'selected_mode', mode=mode, request=asked)
    text = str(component['text'])
    if asked:
        text += '\n\n## Intake request\n\n' + asked + '\n'
    ignored = home.ignore_patterns(ctx.store.project().path if ctx.store is not None else ctx.folder)
    if ignored:  # the one thing added after the intake: what it must not read, from .metaform/ignore.txt
        text = (text + '\n\nDo not read these paths; they are not the project ('
                + home.IGNORE_FILE + '):\n' + '\n'.join(ignored) + '\n')
    return text


def served(ctx: Context, asked: str = '') -> str:
    """Read the editable intake task prompt and append any request data."""
    return _with_request(ctx, procedure_component(ctx), asked)


def prompt(ctx: Context) -> str:
    component = procedure_component(ctx)
    text = _with_request(ctx, component, ctx.nouns.get('text') or '')
    if component['text'].strip() and component['text'] in text:
        prepared = prepare_agent_context(ctx.folder, ctx.session, [component], project=ctx.project)
        ctx.queue_context([component], int(prepared['epoch']))
    return text


def schema(ctx: Context) -> str:
    """The shape of the metaform, served as written, so an agent can read the forms it records."""
    return prompt_files.served_text('prompt.intake:metaform.xml', SHAPE.read_text(encoding='utf-8'))


# Recording, one object per call ------------------------------------------------------------------------------

Notices = list[dict[str, str]]
ADDRESS = 'namespace_address'  # the element's address, named as in the metaform's shape, MAP-040
SOURCES = 'sources'  # the layer an element's refs go in
# Retain existing assessment records without exposing the retired annotation writer.
ASSESSMENTS = Tables(version=1, tables=(
    Table('assessments', key=('node_kind', 'node_id'), columns=(
        Column('node_kind', required=True), Column('node_id', required=True),
        Column('condition', required=True), Column('at', required=True), Column('by'),
        Column('source_item'), Column('evidence', 'json'))),
    Table('assessment_history', key=('id',), columns=(
        Column('id', required=True), Column('node_kind', required=True), Column('node_id', required=True),
        Column('condition', required=True), Column('at', required=True), Column('by'),
        Column('source_item'), Column('evidence', 'json'))),
))



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
    """The intake building for this project, in whichever of its metaforms, recorded now or left unfinished: the one
    the next record goes into, so an agent resumes an intake another left."""
    page = store.intake_building().results
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
                                                        f'{name}, beside it: {active.name} stays the active map '
                                                        'for the person and every agent, and once this intake is '
                                                        f'finished the person makes {name} the active one with '
                                                        f'metaform map activate {name} --confirm.'})
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
    References are items of the sources layer and can be updated without opening a new intake."""
    if _building(store) is not None or not store.has_intake():
        return None
    active = store.active_base()
    base = next((layer for layer in store.layers(limit=0).results if layer.kind in ('base', 'intake')), None)
    if active is None or base is None:
        return None
    return Recording(store, base, active.name, True)


ELEMENT_METADATA = ('block', 'within')
SHAPE_FIELDS = ('name_length', 'name', 'role', *ELEMENT_METADATA)
VERIFIED = 'intake verification pass'  # the reason a correction to the finished map is refined with
BASE_NAME = re.compile(r'[A-Za-z0-9._-]{1,64}')  # what an intake's metaform may be named, `intake start name=`


def _recording(ctx: Context, notices: Notices) -> Recording:
    """The intake being recorded; a record sent before any start starts one, and says so."""
    store = ctx.require_store()
    _refuse_beside_agent(store)
    found = _building(store)
    if found is not None:
        return _holding(found)
    made, opened = _opened(ctx, store, notices)
    if opened:
        notices.append({'where': 'intake', 'message': f'No intake was being recorded, so this call started one: '
                                                      f'layer {made.layer.name} in metaform {made.metaform}.'})
    return _holding(made)


def _agent_at_work(store: Store) -> dict[str, Any] | None:
    """The intake agent Metaform started that is at work on this project now, its runner holding `intake.agent` for as
    long as it lives, BASE-039; None when there is none, or when the caller is that agent, its own work id in
    METAFORM_WORK, which its MCP server and its shell carry."""
    held = store.intake_agent()
    if held is None or held.get('work') and held.get('work') == os.environ.get('METAFORM_WORK'):
        return None
    return held


def _refuse_beside_agent(store: Store) -> None:
    """Refuse an intake recorded, finished or discarded beside the intake agent at work, whatever surface asks, since
    the two would interleave their records in one layer or take it from under that agent, BASE-039."""
    held = _agent_at_work(store)
    if held is None:
        return
    work = held.get('work')
    raise Stop(f'An intake agent Metaform started is at work on this project now{f", work {work}" if work else ""}; '
               'one intake runs at a time. Stop it first, or let it finish.',
               f'metaform dispatch stop {work}' if work else 'metaform dispatch sessions')


def _own_launch(store: Store) -> dict[str, Any] | None:
    """The launch of the intake agent calling, when it is one Metaform started: what map the person chose it makes."""
    held = store.intake_agent()
    if held is None or not held.get('work') or held.get('work') != os.environ.get('METAFORM_WORK'):
        return None
    return held


def _holding(rec: Recording) -> Recording:
    """The intake this call records into, said to be recorded now by this agent for as long as its process lives,
    so the page shows it as being recorded only while an agent is there, BASE-039."""
    rec.store.hold_intake(rec.layer.id)
    return rec


def _folder(store: Store) -> Path:
    """The project's folder in the Metaform home, where its intake lock and its verification pass are kept."""
    folder = home.project_folder(store.project_id)
    if folder is None:
        raise Stop(f'No project {store.project_id} is registered.', 'metaform list projects')
    home.mkdir_private(folder)
    return folder


def _lock(store: Store) -> AbstractContextManager[BinaryIO]:
    """The project's intake lock, between processes: a check that no intake is being recorded and the opening of one
    are one step, and a finish is another, so two calls at once never open two, QUAL-001 and BASE-039."""
    return home.file_lock(_folder(store) / 'intake.lock')


VERIFYING = 'intake.verifying'  # an open verification pass: {"base": <id of the finished base it writes onto>,
# "added": [<ids of the elements it added to that map>]}


def _pass(store: Store) -> dict[str, Any] | None:
    """The verification pass open on the active metaform, its base id and the elements it added: intake start with no
    name on its finished map opened it, and its finish closes it. Kept in the home, so every process of the pass reads
    it. A marker holding only the base id, as written before the pass kept what it added, is a pass that added none."""
    active = store.active_base()
    if active is None:
        return None
    try:
        text = (_folder(store) / VERIFYING).read_text(encoding='utf-8')
    except OSError:
        return None
    try:
        parsed: Any = json.loads(text)
    except ValueError:
        parsed = None
    held: dict[str, Any] = cast(dict[str, Any], parsed) if isinstance(parsed, dict) else {'base': text, 'added': []}
    if held.get('base') != active.id:
        return None
    added: list[Any] = list(held.get('added') or [])
    return {'base': active.id, 'added': [str(each) for each in added]}


def _verifying(store: Store) -> bool:
    """Whether a verification pass is open on the active metaform."""
    return _pass(store) is not None


def _verify(store: Store, base: str | None) -> None:
    """Open a verification pass on the base with this id, or close the one open."""
    path = _folder(store) / VERIFYING
    if base is not None:
        home.write_private(path, json.dumps({'base': base, 'added': []}))
    else:
        path.unlink(missing_ok=True)


def _onto_map(mapped: Recording | None, notices: Notices) -> None:
    """A record sent to a project whose map is finished, with no intake being recorded and no pass open, is written
    onto that map: a verification pass opens for it, as intake start with no name opens one, so a record never starts
    a separate intake in a new base, which is the person's decision, LAYER-025."""
    if mapped is None or _verifying(mapped.store):
        return
    active = mapped.store.active_base()
    if active is None:
        return
    with _lock(mapped.store):  # records sent at once open one pass, and none resets what another already added
        if _verifying(mapped.store):
            return
        _verify(mapped.store, active.id)
    notices.append({'where': 'intake', 'message': f'The map {mapped.metaform} is finished, so this was written onto '
                                                  'it in a verification pass, opened now; intake finish closes it. A '
                                                  'single change needs no pass: metaform map refine.'})


def _verified_add(store: Store, element_ids: Sequence[str]) -> None:
    """Keep the elements a verification pass added to the finished map, so its finish knows the new shape it holds;
    the caller holds the intake lock, so calls at once each keep theirs."""
    held = _pass(store)
    if held is None or not element_ids:
        return
    added = list(dict.fromkeys([*held['added'], *element_ids]))
    home.write_private(_folder(store) / VERIFYING, json.dumps({'base': held['base'], 'added': added}))


def _opened(ctx: Context, store: Store, notices: Notices, named: str = '') -> tuple[Recording, bool]:
    """The intake being recorded, asked again inside the intake lock, or a new one opened there; and whether this call
    opened it, so a call that lost the race to another records into that one."""
    with _lock(store):
        found = _building(store)
        return (found, False) if found is not None else (_open(ctx, store, notices, named), True)


def start(ctx: Context) -> Any:
    """Open the intake layer the records go into, or resume the one already being recorded."""
    store = ctx.require_store()
    _refuse_beside_agent(store)
    notices: Notices = []
    found = _building(store)
    # The map the person chose when they started this intake agent, VIEW-045 as amended 2026-10-17: a new map beside
    # the one in use, named as they named it, or the map in use checked and extended, whatever name the agent gives.
    launch = _own_launch(store)
    if launch is not None and launch.get('map') == 'new' and not ctx.nouns.get('name'):
        ctx.nouns['name'] = str(launch.get('name') or '')
    elif launch is not None and launch.get('map') == 'extend' and ctx.nouns.get('name'):
        notices.append({'where': 'name', 'message': f'The person chose to check and extend the map in use, so the '
                                                    f'name {ctx.nouns["name"]} opens no new map.'})
        ctx.nouns['name'] = None
    # a name asks for a new intake
    if found is None and (mapped := _active_map(store)) is not None and not ctx.nouns.get('name'):
        active = store.active_base()
        assert active is not None  # _active_map found it
        _verify(store, active.id)
        notices.append({'where': 'intake', 'message': f'The active metaform {mapped.metaform} has a finished intake. '
                        'What you record now is written onto it: a changed field is refined, a new element or purpose '
                        'record is added to it, keeping every version, and refs are kept with '
                        'it. A single change needs no pass: '
                        f'{"map_refine" if ctx.surface == "mcp" else "metaform map refine"} adds or corrects one '
                        'element or purpose record under the same rules.'})
        return {'layer': mapped.layer.name, 'project': store.project_id, 'base': mapped.metaform, 'notices': notices}
    opened = False
    if found is None:
        found, opened = _opened(ctx, store, notices, str(ctx.nouns.get('name') or '').strip())
        if opened:  # a separate intake ends a verification pass
            _verify(store, None)
    if not opened:
        notices.append({'where': 'intake', 'message': f'An intake is already being recorded in layer '
                                                      f'{found.layer.name} of metaform {found.metaform}; this call '
                                                      'resumes it. intake show reads back what it holds.'})
        # What the layer lacks of its provenance is filled in; what it holds is kept, LAYER-010.
        _note(notices, found.store.complete(found.layer.name, {name: ctx.nouns.get(name) for name in ('model', 'role')},
                                            result_id=str(ctx.nouns['result']) if ctx.nouns.get('result') else None))
    _holding(found)
    return {'layer': found.layer.name, 'project': store.project_id, 'base': found.metaform, 'notices': notices}


def _described(element: Element) -> bool:
    """Whether an element was described with intake element, not only named in a purpose record."""
    return element.role is not None or element.name_length is not None or element.name is not None


def _sources(ctx: Context, rec: Recording, kind: Literal['element', 'join'], element_id: str, address: str,
             refs: list[Any], notices: Notices) -> None:
    """The refs given with an element or a purpose record, each linked there as a record of the sources layer,
    code.graph.knowledge#c, replacing those last linked there: refs live in a sources layer, never in the metaform.
    Given again, as a verification pass gives them, nothing changes. Off with intake_sources, nothing is written."""
    if not ctx.setting('intake_sources'):
        notices.append({'where': 'refs', 'message': 'intake_sources is off, so the refs were not recorded.'})
        return
    for notice in rec.store.place_refs(Node(kind, element_id), refs, by='intake',
                                       why=f'given with {address} in the intake'):
        if notice.where != 'linked':
            notices.append({'where': notice.where, 'message': notice.message})


def element(ctx: Context) -> Any:
    """Record one element, or record it again: the fields given replace the ones it had, the rest are kept. An element
    is its namespace_address, name_length, name and role; its refs go in the sources layer."""
    notices: Notices = []
    address = ctx.nouns[ADDRESS]
    mapped = _active_map(ctx.require_store())
    current_map = mapped.store.element(address, raw=True) if mapped is not None else None
    if current_map is None:
        _onto_map(mapped, notices)
    if mapped is not None and current_map is None and _verifying(mapped.store):
        # a new element of a verification pass is added to the finished map, in its own layer, by the growth map
        # refine uses too, so the base grows under one set of rules, LAYER-025
        shape = {key: (_whole(ctx.nouns[key]) if key == 'name_length' else ctx.nouns[key])
                 for key in SHAPE_FIELDS if key in ctx.nouns}
        with _lock(mapped.store):
            made = mapped.store.grow_element(address, **shape, reason=VERIFIED, by=author('intake'))
            _note(notices, made)
            if isinstance(made, Element):
                _verified_add(mapped.store, [made.id])
        current_map = mapped.store.element(address, raw=True)
    if mapped is not None and current_map is not None:
        # a field changed on an element of the finished map is refined there, a new version, LAYER-025
        shape = {key: (_whole(ctx.nouns[key]) if key == 'name_length' else ctx.nouns[key])
                 for key in SHAPE_FIELDS if key in ctx.nouns}
        changed = {key: value for key, value in shape.items()
                   if (value is not None or key in ELEMENT_METADATA) and value != getattr(current_map, key)}
        if changed:
            _note(notices, mapped.store.refine(current_map.id, changed, reason=VERIFIED))
        refs = _list(ctx, 'refs')
        if refs is not None:
            _sources(ctx, mapped, 'element', current_map.id, address, refs, notices)
        return {ADDRESS: address, 'layer': mapped.layer.name, 'base': mapped.metaform, 'notices': notices}
    rec = _recording(ctx, notices)
    given = {'name_length': _whole(ctx.nouns.get('name_length')), 'name': ctx.nouns.get('name'),
             'role': ctx.nouns.get('role'),
             **{key: ctx.nouns[key] for key in ELEMENT_METADATA if key in ctx.nouns}}
    current = rec.store.element(address, raw=True)
    element_id: str | None
    if current is not None and current.layer_id == rec.layer.id:
        changes = {key: value for key, value in given.items() if value is not None or key in ELEMENT_METADATA}
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
        _sources(ctx, rec, 'element', element_id, address, refs, notices)
    return {ADDRESS: address, 'layer': rec.layer.name, 'notices': notices}


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
    notices: Notices = []
    receiver = ctx.nouns['receiver']
    elements = _list(ctx, 'elements') or []
    mapped = _active_map(ctx.require_store())
    if mapped is not None and elements:
        held_map = _joins_holding(mapped.store, mapped.layer, receiver, elements)
        holding = [each.address for each in held_map[0].elements] if len(held_map) == 1 else []
        added = [address for address in elements if address not in holding]
        if not held_map or any(mapped.store.element(str(address), raw=True) is None for address in added):
            _onto_map(mapped, notices)  # new shape is written onto the finished map, never into a new base
        verifying = _verifying(mapped.store)
        # the elements a verification pass adds to the map by naming them in a purpose record, kept for its finish
        lacking = [address for address in dict.fromkeys(str(each) for each in [receiver, *elements])
                   if mapped.store.element(address, raw=True) is None] if verifying else []
        if verifying and len(held_map) > 1:
            notices.append({'where': 'elements', 'message': f'{receiver} has {len(held_map)} purpose records holding '
                                                            'these elements, with the purposes '
                                                            f'{"; ".join(repr(held.purpose) for held in held_map)}; '
                                                            'name elements that only one of them holds. Nothing was '
                                                            'changed.'})
            return {'receiver': receiver, 'elements': elements, 'layer': mapped.layer.name, 'base': mapped.metaform,
                    'notices': notices}
        if verifying and not held_map:
            # a new purpose record of a verification pass is added to the finished map, in its own layer, by the
            # growth map refine uses too, LAYER-025
            with _lock(mapped.store):
                made = mapped.store.grow_join(receiver, elements,
                                              **{field: ctx.nouns.get(field) for field in JOIN_FIELDS},
                                              reason=VERIFIED, by=author('intake'))
            _note(notices, made, _words(mapped.store, mapped.layer))
            held_map, holding, added = [made] if isinstance(made, Join) else [], list(elements), []
        # a purpose record of the finished map is refined there, LAYER-025; an element it would hold that the map
        # lacks is new shape, added to the map in a verification pass and recorded in a new intake otherwise
        if len(held_map) == 1 and (verifying or all(mapped.store.element(str(address), raw=True) is not None
                                                    for address in added)):
            refined: dict[str, Any] = {key: ctx.nouns[key] for key in JOIN_FIELDS
                                       if ctx.nouns.get(key) is not None
                                       and ctx.nouns.get(key) != getattr(held_map[0], key)}
            if added:
                refined['elements'] = [*holding, *added]
            if refined:
                _note(notices, mapped.store.refine(held_map[0].id, refined, reason=VERIFIED),
                      _words(mapped.store, mapped.layer))
            _join_refs(ctx, mapped, held_map[0].id, receiver, notices)
            if lacking:
                with _lock(mapped.store):
                    _verified_add(mapped.store, [new.id for address in lacking
                                                 if (new := mapped.store.element(address, raw=True)) is not None])
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
        _join_refs(ctx, rec, held.id, receiver, notices)
        return result
    for field in JOIN_FIELDS:
        if ctx.nouns.get(field) is None:
            notices.append({'where': field, 'message': f'{field} is missing; stored empty.'})
    made = rec.store.add_join(rec.layer.name, receiver, elements,
                              **{field: ctx.nouns.get(field) for field in JOIN_FIELDS})
    _note(notices, made, words)
    join_id = getattr(made, 'id', None)
    if join_id is not None:
        _join_refs(ctx, rec, join_id, receiver, notices)
    return result


def _join_refs(ctx: Context, rec: Recording, join_id: str, receiver: str, notices: Notices) -> None:
    """The refs given with a purpose record, as its item of the sources layer, the same way an element's are kept."""
    refs = _list(ctx, 'refs')
    if refs is not None:
        _sources(ctx, rec, 'join', join_id, receiver, refs, notices)


FINISHED = ('The intake is finished, so nothing was changed. The metaform changes by refining, with metaform map '
            'refine, which keeps every version, LAYER-025.')
NOTHING = 'No intake is being recorded. intake start begins one.'


def _element_entry(found: Element) -> dict[str, Any]:
    """An element as the intake read-back shows it."""
    return {ADDRESS: found.address, 'short_name': found.short_name, 'name_length': found.name_length,
            'name': found.name, 'role': found.role,
            **{key: getattr(found, key) for key in ELEMENT_METADATA if getattr(found, key) is not None}}


def _join_entry(held: Join) -> dict[str, Any]:
    return {'receiver': held.receiver_address, 'type': held.type, 'purpose': held.purpose, 'ef': held.ef,
            'ifd': held.ifd, 'elements': [each.address for each in held.elements]}


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


def _map(elements: list[Element], joins: list[Join], store: Store | None = None) -> dict[str, Any]:
    """The recorded map in the agent's words: every element by its address with its refs, every purpose record by its receiver
    with the elements it holds, the CQUs whose root purpose records the map comes off,
    what those purpose records do not reach, and the addresses never described."""
    refs = _refs(store) if store is not None else {}
    listed: list[dict[str, Any]] = []
    for found in elements:
        entry = _element_entry(found)
        if store is not None:
            entry['refs'] = refs.get(('element', found.id), [])
        listed.append(entry)
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
            'purposes': [{**_join_entry(held),
                          **({'refs': refs.get(('join', held.id), [])} if store is not None else {})}
                         for held in joins],
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
    _holding(found)
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


def _discard_caution(ctx: Context) -> str:
    """What discarding would remove, counted, said before it does."""
    store = ctx.require_store()
    found = _building(store)
    if found is None:
        return ''
    parts = len(found.store.layer_graph(found.layer.id).elements)
    alone = '' if found.active else (f' The base {found.metaform}, if it was opened for this intake alone, goes too; '
                                     'a copy of its store is kept under backups/remove-base.')
    return (f'Discarding the unfinished intake in {found.metaform} removes its layer {found.layer.name} and the '
            f'{parts} {"element" if parts == 1 else "elements"} it recorded; no copy of them is kept and it is not '
            f'undone.{alone}')


def discard(ctx: Context) -> Any:
    """Drop the intake left unfinished: its building layer and the parts it recorded go, and a base opened for it
    alone goes with them, a copy kept, BASE-039. One an agent records now is refused, since that agent would go on
    recording into nothing."""
    store = ctx.require_store()
    with _lock(store):  # no record goes into the layer while it is dropped
        _refuse_beside_agent(store)
        found = _building(store)
        if found is None:
            return {'layer': None, 'project': store.project_id, 'base': None, 'parts': 0,
                    'notices': [{'where': 'intake', 'message': 'No intake is left unfinished; there is nothing to '
                                                               'discard.'}]}
        if any(one.layer.id == found.layer.id for one in store.intake_recording().results):
            raise Stop(f'An agent is recording the intake in layer {found.layer.name} of metaform {found.metaform} '
                       'now; stop that agent first, or let it finish.', 'metaform intake status')
        notices: Notices = []
        parts = len(found.store.layer_graph(found.layer.id).elements)
        _note(notices, found.store.discard(found.layer.id))
        removed = None
        if not found.active and not found.store.graph(raw=True, limit=0).elements:
            removed = home.remove_base(store.project_id, found.metaform)
            notices.append({'where': 'base', 'message': f'The base {found.metaform} was opened for this intake alone, '
                                                        'so it was removed too; a copy is kept under '
                                                        'backups/remove-base.'})
    return {'layer': found.layer.name, 'project': store.project_id, 'base': found.metaform, 'parts': parts,
            'base_removed': removed is not None, 'notices': notices}


def finish(ctx: Context) -> Any:
    """Finish the intake: its layer becomes the metaform's intake, seen by every read, and cannot change in place."""
    store = ctx.require_store()
    notices: Notices = []
    report = _given(ctx, 'report', notices)
    feedback = _given(ctx, 'feedback', notices)
    with _lock(store):  # the intake finished is the one being recorded when the lock is held, and none opens meanwhile
        _refuse_beside_agent(store)  # an intake agent at work finishes its own intake, never another caller
        found = _building(store)
        held_pass = _pass(store) if found is None else None
        verified = held_pass is not None and (found := _active_map(store)) is not None
        added = set(held_pass['added']) if held_pass is not None and verified else set[str]()
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
        previous = None
        if verified:  # the map it wrote onto is finished and active already; nothing is finished or activated
            _verify(store, None)
            notices.append({'where': 'intake', 'message': f'The verification pass on {found.metaform} is finished; '
                                                          'what it recorded is on that map, and no base was opened '
                                                          'or activated.'})
        else:
            _note(notices, found.store.finish(found.layer.name))
        if not found.active:
            # A separate intake is finished beside the active map, never made active by itself: which map the
            # person and every agent work on is the person's to change, and their tickets, conversations and agents
            # at work stay where they are, STORE-041 as amended 2026-10-17.
            previous = store.active_base()
    if previous is not None:
        notices.append({'where': 'base', 'message': f'This intake was stored as the base {found.metaform}, finished '
                                                    f'beside the active map, {previous.name}, which stays active. '
                                                    f'To make {found.metaform} the active map: metaform map activate '
                                                    f'{found.metaform} --confirm'})
        if previous.name != found.metaform:
            # what the map in use until now held that this one does not, so a partial intake is seen at once
            earlier = [placed.element.address for placed in
                       Store(store.project_id, base=previous.id).graph(raw=True, limit=0).elements]
            recorded = {element.address for element in elements}
            lacking = [address for address in earlier if address not in recorded]
            if lacking:
                shown = ', '.join(lacking[:10]) + (f' and {len(lacking) - 10} more' if len(lacking) > 10 else '')
                notices.append({'where': 'elements', 'message': f'This intake holds {len(elements)} elements; '
                                                                f'the map {previous.name} holds {len(earlier)}, and '
                                                                f'{len(lacking)} of them are not in it: {shown}.'})
    for kind, text in (('report', report), ('feedback', feedback)):
        if text is not None:
            save_report(store.project_id, found.layer.id, kind, text, store=found.store,
                        layer=found.layer.id)
    # The open work records on what this intake recorded, MAP-046: the condition of an object is apart from the map.
    recorded_ids = {element.id for element in elements} | {held.id for held in joins}
    work = sum(1 for row in found.store.work(open=True, limit=0).results if row.node_id in recorded_ids)
    # A map with a code trunk is ready for the modules that work on its code, told by intake.finished.
    code = any(element.address.split('.', 1)[0] == 'code' for element in elements)
    # a verification pass finishes no layer; it sends intake.finished only when it added code elements to the map
    new_code = [element.id for element in elements
                if element.id in added and element.address.split('.', 1)[0] == 'code']
    follow_on: list[dict[str, Any]] = []
    if code and (not verified or new_code):
        base = found.store.bound_base()
        if base is not None:
            # Optional enrichment receives the committed map, even when this call resolved its project implicitly.
            # The event bus reports subscriber failures without undoing the completed intake.
            follow_on = replace(ctx, project=store.project_id).publish('intake.finished', {
                'project': store.project_id, 'base': base.id, 'layer': found.layer.id, 'code': True,
                **({'elements': new_code} if verified else {}),
            })
    # Preparation handoffs need completion for document, media and data maps too.
    # Keep intake.finished's code-enrichment contract unchanged.
    if not verified:
        replace(ctx, project=store.project_id).publish('intake.completed', {
            'project': store.project_id, 'base': found.metaform, 'layer': found.layer.id,
        })
    return {'layer': found.layer.name, 'project': store.project_id, 'base': found.metaform,
            'elements': len(elements), 'purposes': len(joins), 'work': work, 'notices': notices,
            **({'follow_on': follow_on} if follow_on else {})}


def _several(store: Store) -> str | None:
    """Every intake being recorded, when there is more than one, with how to keep the one calls record into: one each
    from calls made at once before the intake lock, QUAL-001."""
    building = store.intake_building().results
    if len(building) < 2:
        return None
    named = ', '.join(f'layer {held.layer.name} of metaform {held.base}' for held in building)
    others = list(dict.fromkeys(held.base for held in building[1:] if held.base != building[0].base))
    removal = ('; remove each other one: ' + '; '.join(f'metaform map remove-base {name}' for name in others)
               if others else '')
    return (f'{len(building)} intakes are being recorded: {named}. Calls record into and finish the first, in '
            f'metaform {building[0].base}{removal}.')


RECORDING, LEFT = 'being recorded', 'left unfinished'  # an intake building, with its agent there or gone


def _state(store: Store) -> str:
    """Whether the intake building is being recorded, its agent's process alive, or was left unfinished, BASE-039."""
    building = store.intake_building().results
    return RECORDING if building and building[0].recording else LEFT


def _busy_line(held: dict[str, Any]) -> str:
    """The intake agent at work, said in one line: its agent and work id, and since when."""
    who = f' ({held["agent"]})' if held.get('agent') else ''
    work = f', work {held["work"]}' if held.get('work') else ''
    since = f', since {held["since"]}' if held.get('since') else ''
    return f'Intake: an agent Metaform started is at work on it now{who}{work}{since}'


def status_verb(ctx: Context) -> str:
    store = ctx.require_store()
    found = _building(store)
    lines: list[str] = []
    if store.has_intake():
        latest = store.layers(kind='intake', limit=0).results[-1]
        lines.append(f'This project has an intake. Latest intake layer: {latest.name}')
    if (agent := _agent_at_work(store)) is not None:  # starting, or reading before its first record, BASE-039
        lines.append(_busy_line(agent) + (f'; metaform dispatch stop {agent["work"]} stops it.' if agent.get('work')
                                          else '.'))
    if found is not None:
        state = _state(store)
        lines.append(f'An intake is {state} in layer {found.layer.name} of metaform {found.metaform}.'
                     + ('' if state == RECORDING else ' Resume it with intake start, finish it with intake finish, '
                                                       'or discard it with metaform intake discard --confirm.'))
    if (several := _several(store)) is not None:
        lines.append(several)
    if not store.has_intake() and (elsewhere := _mapped_elsewhere(store)):
        # the project was mapped: its active base is empty, or new, and the map it had is kept, MCP-009
        lines.insert(0, elsewhere)
    if not lines:
        lines.append('No intake yet. Read the instructions with metaform intake prompt.')
    return '\n'.join(lines) + '\n'


def _mapped_elsewhere(store: Store) -> str | None:
    """That the project has a finished intake in another metaform than the active one, which has none, with the
    command that makes one of them active; None when no other has one, MCP-009."""
    others = store.intake_bases()
    # the one named to go back to is the map the person last made active, as the page's empty base and an empty map
    # read name it, never merely the newest, such as a trial intake never worked on (UX review round 2, 2026-10-17,
    # project-scope F3)
    kept = store.kept_map()
    if not others or kept is None:
        return None
    active = store.active_base()
    return (f'Intake: none in the active map {active.name if active is not None else "(none yet)"}; this project has '
            f'a finished intake in {", ".join(others)}. To work on it again: metaform map activate {kept.name} '
            '--confirm')


def status(ctx: Context) -> Status:
    here = resources.files(__name__)
    if os.environ.get('METAFORM_SESSION'):
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
    state = _state(ctx.store) if found is not None else None
    recording = (f'Intake: {state} in layer {found.layer.name} of metaform {found.metaform}',
                 *((several,) if several is not None else ())) if found is not None else ()
    # An intake agent at work now, started from any surface and before its first record too, BASE-039: the agent is
    # told only that, never to start an intake or that one was aborted, UX review round 1 (2026-10-17) F4.
    agent = _agent_at_work(ctx.store)
    busy = (_busy_line(agent),) if agent is not None and found is None else ()
    # The instructions agents read name an intake started and left unfinished, its agent gone, or else a project with
    # no intake, MCP-009; neither while an agent is at work on one.
    unfinished = prompt_files.required(here, 'unfinished') if found is not None and state == LEFT else None
    if ctx.store.has_intake():
        return Status(lines=('Intake: complete', *busy, *recording), instruction=unfinished)
    if found is not None:
        return Status(lines=recording, instruction=unfinished)
    if busy:
        return Status(lines=busy)
    # A project whose finished intake is in another metaform than the active one has been analysed: no agent is told
    # it is a first run, which would send the person's own agent to map it again, MCP-009 as amended 2026-10-17.
    if (elsewhere := _mapped_elsewhere(ctx.store)) is not None:
        return Status(lines=(elsewhere,))
    return Status(lines=('Intake: none yet',), instruction=prompt_files.required(here, 'no_intake'))



def first_run(ctx: Context) -> str | None:
    """Intake's first-run text, `no_intake`, while the project has no intake and none is being recorded, with the
    register step while the folder is no registered project, as `status` gives it at connect; None otherwise, and to an
    agent a runner started. Offered as `intake.first_run`, so the MCP server serves it whole as metaform://firstrun."""
    got = status(ctx)
    if not got.at_connect or not got.instruction:
        return None
    return None if got.instruction == prompt_files.required(resources.files(__name__), 'unfinished') else got.instruction

E, P = ELEMENT_WORDS.get, PURPOSE_WORDS.get

def recording(folder: Path) -> bool:
    """Whether an intake is being recorded in the folder's project, or a verification pass is open on its map, so
    the verbs that record, read or end it are listed over MCP, MCP-004."""
    project = project_for(folder)
    if project is None:
        return False
    store = Store(project)
    return _building(store) is not None or _verifying(store)


MODULE = Module(
    id='intake',
    tables=ASSESSMENTS,
    summary='Serve the intake and record its result as it is reasoned.',
    purpose='Serves the intake instructions, records the intake as it is reasoned, and tracks whether this project '
            'has an intake. The intake is agent work: a subagent reads its instructions with the command prompt and '
            'follows them. Details: metaform help intake.',
    details='The intake text is served as stored, with its prompt slot filled. The intake is recorded as it is '
            "reasoned, one element or purpose record per call, in the metaform's shape: an element is its namespace_address, "
            'name_length, name and role; a purpose record is the receiver\'s purpose, the ef and the ifd, holding the elements '
            'that serve it. An element\'s refs go in the sources layer while intake_sources is on. It is read back '
            'with show, whole or one receiver at a time, and corrected by recording again and with remove. No other '
            'read sees it until finish; after finish the metaform grows and changes by refining, metaform map refine, '
            'in the same layer, under the same rules, or by a verification pass, intake start with no name, which '
            'writes onto it. A new base is opened only when the person asks for a new map. Nothing is refused for its '
            'content: what does not fit is stored as given and named in a notice.',
    verbs=(
        Verb('prompt', prompt, "Read the intake instructions an agent follows to record this project's map.",
             nouns=(Noun('text', 'path to the target for the intake process; leaving this blank means this project',
                         required=False),
                    Noun('mode', 'Selected analysis: fresh surveys artifacts into a separate map, refine updates the '
                                 'current map, resume continues an unfinished intake. Dispatched intakes retain '
                                 'their launch choice.', required=False,
                         schema={'type': 'string', 'enum': ['fresh', 'refine', 'resume']})), effect='read'),
        Verb('schema', schema, 'Read the shape the intake records: namespace roots, Upstream and Downstream links, '
                               'element and purpose forms.', effect='read', needs_project=False),
        Verb('start', start, "Start or resume this project's intake; on a mapped project, a verification pass that "
                             'refines and extends the map in use. Changed fields are refined, new elements and purpose '
                             'records are added to it, refs are written onto it, and intake '
                             'finish closes the pass. One change to the map needs no pass: metaform map refine. '
                             'Returns its name.',
             nouns=(Noun('result', 'The result id the intake procedure generates and gives at start, kept with the intake.', required=False),
                    Noun('name', 'Only when the person asks for a new map beside the one in use: its name, 1 to 64 '
                                 'letters, digits, ., _ and -; on a mapped project it is their decision. A new '
                                 'feature, a correction or a check is recorded with no name, which refines the map '
                                 'in use.',
                         required=False),
                    Noun('model', 'The model that performs the intake.', required=False),
                    Noun('role', 'The role of the agent that performs it.', required=False)),
             person_details='A web GUI that runs follows the intake live.'),
        Verb('element', element, 'Record one element of the intake at its address; recording it again replaces the '
                                 'fields given.',
             nouns=(Noun(ADDRESS, E(ADDRESS, '')),
                    Noun('name_length', E('name_length', ''), required=False, schema=NAME_LENGTH),
                    Noun('name', E('name', ''), required=False),
                    Noun('role', E('role', ''), required=False, schema=ROLE),
                    Noun('block', E('block', ''), kind='json', required=False,
                         schema={'type': ['string', 'null']}),
                    Noun('within', E('within', ''), kind='json', required=False,
                         schema={'type': ['string', 'null']}),
                    Noun('refs', E('refs', ''), required=False, schema=REFS)), listed=recording),
        Verb('purpose', purpose, "Record one purpose record: a receiver's OP and the elements that serve it, with its EF. "
                                 'Recorded again with an element it holds, the fields given replace its own and new '
                                 'elements are added.',
             nouns=(Noun('receiver', P('receiver', '')),
                    Noun('elements', P('elements', ''), schema=ELEMENTS),
                    Noun('purpose', P('purpose', ''), required=False),
                    Noun('ef', P('ef', ''), required=False),
                    Noun('ifd', P('ifd', ''), required=False, schema=IFD),
                    Noun('refs', P('refs', ''), required=False, schema=REFS)), listed=recording),
        Verb('show', show, 'Read the intake being recorded, whole or one receiver at a time.',
             nouns=(Noun('receiver', P('receiver', ''), required=False),), effect='read', listed=recording),
        Verb('remove', remove, 'Remove one element, one purpose record, or one element from a purpose record, from '
                               'the intake being recorded. Each is named by addresses.',
             nouns=(Noun('receiver', P('receiver', ''), required=False),
                    Noun('provider', P('provider', ''), required=False),
                    Noun(ADDRESS, E(ADDRESS, ''), required=False)), effect='remove', listed=recording),
        Verb('finish', finish, 'Finish the intake. One recorded in a base of its own is finished beside the active '
                               'map, which stays active: metaform map activate <its name> --confirm makes it the '
                               'active one. A verification pass is closed on the map it wrote onto, activating nothing. After finish the metaform '
                               'grows and changes by refining, metaform map refine, or by a verification pass, '
                               'intake start with no name.',
             nouns=(Noun('report', 'Your report on the project you examined: broken code, things that need fixing, '
                                   'anything not working or partially working. On the command line a file is read '
                                   'and - is standard input.', required=False),
                    Noun('feedback', 'Feedback on the Metaform process: bad semantics, a tool that did not match its '
                                     'schema, where you got stuck.', required=False)),
             listed=recording),
        Verb('status', status_verb, 'Say whether this project has an intake, and whether one is being recorded.',
             effect='read'),
        # The person's choice for an intake left unfinished, beside resuming and finishing it; never an agent's, so it
        # is not a tool.
        Verb('discard', discard, 'Discard the intake left unfinished: its layer and the parts it recorded are removed, '
                                 'and a base opened for it alone goes too, a copy kept.',
             caution='Discarding the unfinished intake removes every part it recorded; it is not undone.',
             surfaces=('cli',), effect='remove', listed=recording, cautioned=_discard_caution),
    ),
    status=status,
    provides=(Provides('intake.first_run', first_run), Provides('agent.tool.instructions', tool_instructions)),
    resources=(
        Resource(PROCEDURE_URI, 'Intake procedure',
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
