"""map: the data access object's map and layer operations as verbs, BASE-038.

Every verb calls `ctx.require_store()` and exactly one operation of STORE-024
or STORE-025, and returns its result, BASE-036. The fields of a record being
written are nouns: required ones positional, optional ones `name=value`. The
only switch is `--raw`, which reads every stored layer instead of the layers
in context. `knowledge` is the one read-write verb for layers, LAYER-018.
"""
from __future__ import annotations

import dataclasses
import difflib
import json
import re
import shlex
import time
from collections.abc import Callable
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any, TypeVar, cast

from metaform import home, prompt_files, settings
from metaform.data import (
    CONDITIONS,
    PLACE_KINDS,
    Item,
    Node,
    Notice,
    Outcome,
    Page,
    Store,
    StoreError,
    WorkRecord,
    author,
    plain,
    shown_open,
)
from metaform.finish_xml import xml as map_xml
from metaform.module import (
    Context,
    Module,
    Noun,
    NounKind,
    Pane,
    Provides,
    Resource,
    Status,
    Stop,
    ToolbarItem,
    Verb,
    agent_caller,
    item_read,
    latest_item,
    node_reads,
    persons_word,
    persons_word_acted,
    project_for,
    provided,
    titled,
    work_reads,
)
from metaform.outline import markdown as map_markdown
from metaform.outline import mermaid as map_mermaid
from metaform.outline import mermaid_limits

from . import ticket_history
from .around import told
from .glossary import PANES as GLOSSARY_PANES
from .glossary import VERBS as GLOSSARY_VERBS
from .glossary import item_read as term_read
from .glossary import items_at as terms_at
from .guidance import guide
from .guidance import instructions as tool_instructions
from .scoped import is_scoped
from .scoped import resolve as resolve_scoped
from .storage import DATA, TABLES, runtime_values

SOURCES = 'sources'  # the layer an element's refs go in, naming the code that realizes a part, STORE-025

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False
REMOTE_AGENT = True  # reading and writing the map is the work a remote agent does
DATA_SOURCE = 'storage.py'

# Given on the call alone, never stored: stored, raw would unmask every read below the folder, and critic would
# silently make every blind-spot run the sighted one, LAYER-014.
settings.boolean('raw', False, per_call=True,
                 help='Read every stored layer, building, hidden and masked ones included.')
settings.boolean('critic', False, per_call=True, help='map critic: the critic also reads the code and writes tickets; '
                 'fast mode, blind to the code, when off.')
settings.boolean('tasks', True, help='Assign and track work on the map like a kanban. Turn it off when the project '
                 'keeps its own board.')
settings.number('node_summary_bytes', 2048, min=512,
                help='The bytes an agent is given about the node it works on, in map where, a ticket read and the '
                     'hand-off. What does not fit, code paths first, is counted with the call that reads it.')
# Preserve the existing web-owned key so saved cutoffs survive the shared operation.
with settings.owned_by('web'):
    settings.text('board_line', '',
                  help='The first board\'s archive cutoff. Archive done tickets retains completed work in Git.',
                  details='Tickets with completion commits leave the store at the line. Tickets without commits stay.',
                  label='Board archive cutoff', category='advanced', heading='Board')


def _check_board(name: Any, folder: Path) -> list[str] | None:
    """The active board must be a board the project has; empty is the first board, always there."""
    wanted = str(name or '').strip()
    if not wanted:
        return None
    from metaform.context import project_for
    project_id = project_for(folder)
    if project_id is None:
        raise settings.SettingError('--board names a board of a project, and this folder is not in one.',
                                    'metaform add project <id> <path>')
    with Store(project_id, module='map').tables(write=False) as tx:
        if tx.get('boards', {'name': wanted}) is None:
            raise settings.SettingError(f'There is no board named {wanted!r}.',
                                        f'metaform map boards op=add name="{wanted}"')
    return None


# The active board, the person's need of 2026-10-21: the one board the project works on. A ticket filed with no board
# lands on it, and only its tickets start by themselves, dispatch's gate; a board set aside stays aside until it is
# activated again, so Full Auto never reaches old work. Activate on the page's board sets it.
settings.text('board', '', person_only=True, label='Active board', check=_check_board, heading='Board',
              help='The board the project works on: a ticket filed with no board lands on it, and only its tickets '
                   'start by themselves. Empty is the first board.',
              details='Set it with Activate on the board. Full Auto, retries and every start the system makes by '
                      'itself leave the other boards aside; your own Start on a card still runs.')

REFS_SCHEMA = {'type': 'array', 'items': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 2, 'maxItems': 2}}
# What edit and refine change; ifd and verb among them, which were dropped before, an intake found.
FIELDS = ('address', 'extra', 'receiver', 'elements', 'type', 'purpose', 'ef', 'ifd',
          'name', 'name_length', 'role', 'value', 'link', 'element', 'refs', 'read_first', 'always_show')


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


BASE_SWITCH = ('This changes the active map for every agent and the page of the project. The previous base is kept; '
               'map activate <its name> switches back.')


def _switch_caution(ctx: Context) -> str:
    """BASE_SWITCH for this call: what the active base holds that leaves view, and the command that switches back."""
    return home.switch_caution(_other_project(ctx).project_id)


def _activate_caution(ctx: Context) -> str:
    """activate's caution for this call: nothing, said so, when the base named is the active map already."""
    return home.switch_caution(_other_project(ctx).project_id, str(ctx.nouns.get('name') or '') or None)


def _remove_caution(ctx: Context) -> str:
    """remove-base's caution for this call: the base named, with what it holds, and the copy kept."""
    return home.remove_caution(_other_project(ctx).project_id, str(ctx.nouns.get('name') or ''))


def base_holds(store: Store) -> dict[str, int]:
    """What a base holds of the map's own that a clear or a switch takes from the person: its open tickets, the held
    ones that anchor conversations left out, and its knowledge layers, the base layer left out."""
    tickets = sum(1 for record in store.work(open=True, limit=0).results if not record.held)
    layers = sum(1 for layer in store.layers(limit=0).results if layer.kind == 'layer' and layer.name != 'base')
    return {'tickets': tickets, 'layers': layers}


def _other_project(ctx: Context) -> Store:
    project = ctx.nouns.get('project')
    return Store(project) if project else _store(ctx)


PAGING = (Noun('limit', 'How many results, 0 for all.', kind='int', required=False),
          Noun('after', 'The cursor the previous page returned.', required=False))


def roots(ctx: Context) -> Any:
    """The map's entry: the CQU and the DE with their joins, and every root element, STORE-025."""
    found = _store(ctx).roots(**_reading(ctx), **_paging(ctx))
    return _kept_elsewhere(_store(ctx), found) if not found.entry and not found.elements else found


def _kept_elsewhere(store: Store, result: Any) -> Any:
    """An empty read of an empty active map, with a notice naming the base that keeps the project's map: an agent
    connecting there is otherwise left to think the project unmapped (UX review round 2, 2026-10-17, project-scope
    F4). Asked only of an empty read, so a mapped base pays nothing."""
    said = store.kept_map_said()
    return _with_notices(result, [Notice('map', said)]) if said else result


def _with_modules(ctx: Context, found: Any, node: Node) -> Any:
    """A node's read with what the modules on the surface add to it, each under its own id, BASE-035; a field the
    read holds already is never replaced."""
    added = node_reads(ctx.folder, node, project=ctx.project, layers=ctx.switches.get('layers'))
    if found is None or not added:
        return found
    data = cast(dict[str, Any], found.to_dict())
    for module, value in added.items():
        data.setdefault(module, value)
    return data


def _with_work_modules(ctx: Context, found: Any) -> Any:
    """A ticket's read, MAP-048: its fields, its node's read with the counts at it and around it once per session,
    MCP-039, each linked node by its address, and the modules' fields on the work record, BASE-035; a field the read
    holds already is never replaced. What is held at its nodes is read with the calls the counts name."""
    added = work_reads(ctx.folder, found.work, project=ctx.project)
    data = cast(dict[str, Any], found.to_dict())
    history = _store(ctx).work_hold_history(found.work.id)
    if history:
        data['hold_history'] = list(history)
    data['sources'] = list(_store(ctx).work_sources(found.work.id, contents=False))
    data['at'] = _oriented(ctx, found.at, Node.of(found.work.node_kind, found.work.node_id),
                           focus=tuple(link.address for link in found.work.links if link.address))
    data['linked'] = [None if read is None else (link.address or _compact(read.to_dict()))
                      for link, read in zip(found.work.links, found.linked)]
    for module, value in added.items():
        data.setdefault(module, value)
    return data


def _refs(groups: Any) -> list[str]:
    """The refs the sources layer holds in a small read's layers, each `key=value`: where the code is, which an agent
    reads itself, so they are pointers and not contents."""
    return list(dict.fromkeys(f"{ref['key']}={ref['value']}" for group in cast(list[dict[str, Any]], groups or [])
                              if group.get('layer') == SOURCES for item in group.get('items', [])
                              for ref in item.get('refs', [])))


LEAN = ('id', 'layer_id', 'element_id', 'existing', 'differs')  # what an agent never acts on in a read, MCP-039


def _lean(data: Any) -> Any:
    """A read as `map where` gives it by default, MCP-039: the ids and the fields an agent never acts on left out, and
    every empty field, at every depth."""
    if isinstance(data, dict):
        held = cast(dict[str, Any], data)
        return {key: _lean(value) for key, value in held.items()
                if key not in LEAN and value not in (None, '', [], {})}
    if isinstance(data, list):
        return [_lean(one) for one in cast(list[Any], data)]
    return data


def _compact(data: dict[str, Any]) -> dict[str, Any]:
    """A node's read as an agent orients from it, MCP-039: the element, and each join by its addresses with its
    purpose, from the small read STORE-025 gives, each with the sources layer's refs, which point to the code that
    realizes it. What else is held at the node is counted by `around`, not carried."""
    def kept_join(join: dict[str, Any], *pairs: tuple[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in (*pairs, ('purpose', join.get('purpose')),
                                              ('sources', _refs(join.get('layers')))) if value}
    kept: dict[str, Any] = {'kind': data['kind']}
    if 'element' in data:
        kept['element'] = data['element']
    refs = _refs(data.get('layers'))
    if refs:
        kept['sources'] = refs
    if 'join' in data:
        join = data['join']
        kept['join'] = {**kept_join(join, ('receiver', join.get('receiver')),
                                    ('providers', [held.get('address') for held in join.get('elements', [])])),
                        **({'ef': join['ef']} if join.get('ef') else {})}
    if data.get('provides'):
        kept['provides'] = [kept_join(join, ('receiver', join.get('receiver'))) for join in data['provides']]
    if data.get('receives'):
        kept['receives'] = [kept_join(join, ('providers', [held.get('address') for held in join.get('elements', [])]))
                            for join in data['receives']]
    return kept


def _prompt(name: str, **fills: str) -> str:
    return prompt_files.text(resources.files(__package__ or 'metaform.modules.map'), name, **fills) or ''


def _size(data: dict[str, Any]) -> int:
    return len(json.dumps(data, ensure_ascii=False).encode('utf-8'))


def _fitted(ctx: Context, found: Any, data: dict[str, Any], said: dict[str, Any], budget: int, *,
            calls: bool = False, focus: tuple[str, ...] = ()) -> dict[str, Any]:
    """Fit presentation detail without treating storage order as functional relevance.

    Receiver identities and operative purposes remain addressable in every compact read. Decorative counts go
    before implementation references. If the essential relationships exceed the display target, return them:
    the byte target is a presentation preference, not evidence that the first stored receiver is sufficient.
    """
    said = dict(said)
    provides = [dict(one) for one in cast(list[dict[str, Any]], data.get('provides') or [])]
    receives = [dict(one) for one in cast(list[dict[str, Any]], data.get('receives') or [])]
    join = dict(cast(dict[str, Any], data.get('join') or {}))
    own = list(cast(list[str], data.get('sources') or []))
    element = cast(dict[str, Any], data.get('element') or {})
    address = element.get('address') if data.get('kind') == 'element' else None
    left: list[str] = []
    taken: list[tuple[dict[str, Any] | None, list[str]]] = []  # the code paths taken off, from where, in order

    def drawn(calls: bool = False) -> dict[str, Any]:
        shown = {*own, *join.get('sources', ()),
                 *(ref for one in (*provides, *receives) for ref in one.get('sources', ()))}
        unshown = len([ref for ref in dict.fromkeys(left) if ref not in shown])
        sources = (f'metaform map where address={address} contents=true' if address else
                   f'metaform map node node=join:{found.join.id}' if found.join is not None else '')
        more = [_prompt('summary_sources', count=str(unshown), read=sources)] if unshown and sources else []
        kept: dict[str, Any] = {}
        for key, value in data.items():
            value = {'sources': own, 'join': join, 'provides': provides, 'receives': receives}.get(key, value)
            if value:
                kept[key] = value
        if more:
            kept['more'] = [ctx.calls(line) for line in more] if calls else more
        return {**kept, **said}

    def steps() -> Any:
        if said:
            said.clear()
            yield
        candidates = [*reversed(receives), *reversed(provides), join]
        # Existing explicit work links express selected functional context. Keep their references after
        # incidental references without inferring relevance from words or storage order.
        candidates.sort(key=lambda one: bool(set(focus) & {one.get('receiver'), *one.get('providers', ())}))
        for one in candidates:
            if one.get('sources'):
                taken.append((one, one['sources']))
                left.extend(one.pop('sources'))
                yield
        if own:
            taken.append((None, list(own)))
            left.extend(own)
            own.clear()
            yield

    if _size(drawn()) > budget:
        for _ in steps():
            if _size(drawn()) <= budget:
                break
        # Restore references that fit after decorative detail was removed, the node's own first.
        for one, refs in reversed(taken):
            if one is not None and not any(one is held for held in (*provides, *receives, join)):
                continue
            (own if one is None else one.setdefault('sources', [])).extend(refs)
            if _size(drawn()) > budget:
                del (own if one is None else one['sources'])[-len(refs):]
                if one is not None:
                    one.pop('sources')
    return drawn(calls=calls)


def _oriented(ctx: Context, found: Any, node: Node, *, contents: bool = False,
              focus: tuple[str, ...] = ()) -> Any:
    """A node's read for an agent: the element and its joins with the counts at it and around it, once per session,
    MCP-039, within the node_summary_bytes setting; with `contents`, or with full, everything held at it as well, as
    `map node` reads it, whatever its size."""
    if found is None:
        return None
    if contents or found.full:
        data = cast(dict[str, Any], plain(_with_modules(ctx, found, node)))
        return {**data, **told(ctx, found)}
    data = _compact(cast(dict[str, Any], found.to_dict()))
    budget = int(ctx.setting('node_summary_bytes'))
    said = told(ctx, found, lambda part: _size(_fitted(ctx, found, data, part, budget, focus=focus)) <= budget)
    return _fitted(ctx, found, data, said, budget, calls=True, focus=focus)


def _missing(store: Store, address: str) -> Stop:
    """Recover orientation at the map surface without changing the store's context reads."""
    found = store.where(address, raw=True)
    recording = next(iter(store.intake_building().results), None)
    if recording is not None:
        building = Store(store.project_id, base=recording.base_id)
        held = building.where(address, raw=True)
        if (held is not None and held.element is not None and held.element.layer_id == recording.layer.id
                and (found is None or found.element is not None and found.element.layer_id == recording.layer.id)):
            return Stop(f'Element {address} is in the intake being built in layer {recording.layer.name} '
                        f'of metaform {recording.base}.', f'metaform intake show receiver={address}')
    if found is not None and found.element is not None:
        return Stop(f'Element {address} is in building, hidden or masked layer {found.element.layer}.',
                    f'metaform map where {address} --raw')

    prefix = address
    children: tuple[str, ...] = ()
    while prefix:
        parent = prefix.rpartition('.')[0]
        if prefix in store.children(parent, limit=0).results:
            children = store.children(prefix, limit=0).results
            break
        prefix = parent
    addresses = [one.element.address for one in store.graph(raw=True, limit=0).elements]
    nearest = list(dict.fromkeys((*difflib.get_close_matches(address, addresses, n=5, cutoff=0.6), *children)))[:5]
    message = f'No element {address} in context here.'
    if not addresses and (kept := store.kept_map_said()):  # an empty active map beside the project's own
        return Stop(f'{message} {kept}.', 'tell the person; the switch is theirs')
    if nearest:
        return Stop(f'{message} Nearest: {", ".join(nearest)}.', f'metaform map where {nearest[0]}')
    return Stop(message, f'metaform map children address={shlex.quote(prefix)}')


@ticket_history.per_call
def where(ctx: Context) -> Any:
    """One read of an address: what relies on it and what it relies on, with the counts at it and around it,
    STORE-025 and MCP-039; the entry with no address. `<scope>@<layer>` reads what that layer holds at the scope, P165,
    `scoped.py`."""
    if not ctx.nouns['address']:  # the entry, compacted as every read here is unless full keeps what it leaves out
        entry = roots(ctx)
        return entry if ctx.nouns.get('full') else _lean(plain(entry))
    address = ctx.nouns['address']
    if is_scoped(str(address)):
        return scoped_read(ctx, str(address))
    found = _store(ctx).where(address, full=bool(ctx.nouns.get('full', False)), **_reading(ctx))
    if found is None:
        raise _missing(_store(ctx), address)
    return _oriented(ctx, found, Node('element', address), contents=bool(ctx.nouns.get('contents', False)))


def scoped_read(ctx: Context, text: str) -> Any:
    """What a layer holds at a scope, `<scope>@<layer>`, P165: the scope's element as the map gives it, its name and
    role, and what the layer holds there. A layer's items are read in context, so a mask at the address leaves them out as every read does."""
    store = _store(ctx)
    found = resolve_scoped(store, text)
    read: dict[str, Any] = {'scope': found.text, 'layer': found.layer}
    if found.address is not None:
        element = store.element(found.address)
        if element is not None:
            read['element'] = {key: value for key, value in (
                ('address', element.address), ('name', element.name), ('short_name', element.short_name),
                ('role', element.role), ('reading', element.reading)) if value}
    node: Node | None = None
    if found.address is not None and found.provider:
        try:
            node = store.purpose(found.address, found.provider)
        except StoreError as error:
            raise Stop(f'{found.text} does not resolve: {error}', f'metaform map joins element={found.address}') from None
    elif found.address is not None:
        element = store.element(found.address)
        node = Node('element', element.id) if element is not None else None
    page = store.layer_items(found.layer, node, in_context=node is not None, **_paging(ctx))
    held: list[dict[str, Any]] = []
    for one in page.results:  # each as an agent reads it: its id, to edit it by, its value, refs and link
        data = cast(dict[str, Any], plain(one))
        kept = {key: data[key] for key in ('id', 'value', 'link') if data.get(key) is not None}
        refs = [f"{ref['key']}={ref['value']}" for ref in cast(list[dict[str, Any]], data.get('refs') or [])]
        held.append({**kept, **({'refs': refs} if refs else {}), **({'kind': 'property'} if 'element_id' in data
                                                                   else {})})
    return {**read, 'items': held, **({'next': page.next} if page.next else {})}


def _document(ctx: Context, verb: str, text: str) -> Any:
    """A document printed, or written to the file the call names, a relative one in the caller's folder."""
    target = ctx.nouns.get('file')
    if not target:
        return text
    path = Path(target) if Path(target).is_absolute() else ctx.folder / target
    try:
        if home.is_home_path(path):
            home.mkdir_private(path.parent)
            home.write_private(path, text)
        else:
            path.write_text(text, encoding='utf-8')
    except OSError as error:
        raise Stop(f'The {verb} document could not be written to {path}: {error.strerror or error}.',
                   f'name a file in a folder that exists, or leave out file= and metaform map {verb} prints it') from None
    return {'written': str(path)}


def markdown(ctx: Context) -> Any:
    """The map, or the part around one address, as a short Markdown document to find one's way by, MAP-052."""
    return _document(ctx, 'markdown', map_markdown(_store(ctx), ctx.nouns.get('address') or None, **_reading(ctx)))


def mermaid(ctx: Context) -> Any:
    """The map, or one element and those one join away, as a Mermaid flowchart, P063: the writer of the web GUI's
    Mermaid export, so a diagram pasted in GitHub, VS Code, Obsidian or a chat holds the elements and joins the page's
    2D map draws, each join pointing the way its information goes, and asks for the page's ELK layout."""
    leave_out = tuple(root for root in str(ctx.nouns.get('leave_out') or '').split(',') if root)
    text = map_mermaid(_store(ctx), ctx.nouns.get('address') or None, direction=str(ctx.nouns.get('direction') or 'TB'),
                       leave_out=leave_out, labels=str(ctx.nouns.get('labels') or 'none'), **_reading(ctx))
    done = _document(ctx, 'mermaid', text)
    notice = mermaid_limits(text)
    if notice and isinstance(done, dict):  # written to a file: the notice the printed diagram carries in its comment
        return {**cast(dict[str, Any], done), 'notices': [{'where': 'mermaid', 'message': notice}]}
    return done


def xml(ctx: Context) -> Any:
    """The map, or one element and all it receives, as an XML document in the Finish shape of Intake 2.1, MAP-059."""
    return _document(ctx, 'xml', map_xml(_store(ctx), ctx.nouns.get('address') or None, **_reading(ctx)))


def element(ctx: Context) -> Any:
    found = _store(ctx).element(ctx.nouns['element'], **_reading(ctx))
    if found is None:
        raise Stop(f'No element {ctx.nouns["element"]} in context here.', f'metaform map where {ctx.nouns["element"]}')
    return found


def joins(ctx: Context) -> Any:
    return _store(ctx).joins(ctx.nouns['element'], ctx.nouns.get('as', 'receiver'), **_reading(ctx), **_paging(ctx))


def identity(ctx: Context) -> Any:
    return _store(ctx).identity(ctx.nouns['element'], **_reading(ctx), **_paging(ctx))




def children(ctx: Context) -> Any:
    found = _store(ctx).children(ctx.nouns['address'], **_paging(ctx))
    return _kept_elsewhere(_store(ctx), found) if not found.results and not ctx.nouns['address'] else found


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
    target = _node(ctx.nouns['node'])
    found = _store(ctx).node(target, **_reading(ctx))
    if found is None:
        raise Stop(f'No node {ctx.nouns["node"]} in context here.', 'metaform map node <node> --raw')
    return _with_modules(ctx, found, target)


def context(ctx: Context) -> Any:
    return _store(ctx).context(ctx.nouns['address'], **_paging(ctx))


def links(ctx: Context) -> Any:
    return _store(ctx).links_to(_node(ctx.nouns['node']), ctx.nouns.get('layer'), **_reading(ctx), **_paging(ctx))


def citing(ctx: Context) -> Any:
    store = _store(ctx)
    key, value = ctx.nouns['key'], ctx.nouns['value']
    if key == 'path':
        value = value.replace('\\', '/')
        while value.startswith('./'):
            value = value[2:]
        if Path(value).is_absolute():
            root = Path(store.project().path).resolve()
            try:
                value = Path(value).resolve().relative_to(root).as_posix()
            except ValueError:
                raise Stop(f'{value} is outside the project folder {root}.',
                           'metaform map citing key=path value=<project-relative path>') from None
    return store.citing(key, value, **_paging(ctx))


def history(ctx: Context) -> Any:
    return _store(ctx).history(ctx.nouns['id'], **_paging(ctx))


def bases(ctx: Context) -> Any:
    """The project's bases, each with whether it holds a finished map and when it was last made active, so a surface
    showing an empty one can point to the map the person last worked on (UX review round 2, 2026-10-17, project-scope
    F3)."""
    store = _other_project(ctx)
    found = store.bases(**_paging(ctx))
    when = home.activations(store.project_id)
    return found._replace(results=tuple(
        home.BaseRead(**{field.name: getattr(base, field.name) for field in dataclasses.fields(base)},
                      mapped=store.base_mapped(base), activated=when.get(base.id)) for base in found.results))


def _switched(store: Store, switch: Callable[[], home.Base]) -> home.Base:
    """A switch of the active base, with a notice naming the agents at work on the base it left: each stays on the
    base it began on, where its ticket is, and is still listed and stopped, STORE-041 and BASE-052."""
    left = store.active_base()
    made = switch()
    now = store.active_base()
    notices = list(made.notices)
    said = home.staying(store.project_id, left, now)
    if said:
        notices.append(Notice('agents', said))
    if left is not None and now is not None and left.id != now.id:
        # the tickets stay with the base they were written on, out of view until it is shown again, D111
        opened = len(Store(store.project_id, base=left.id).work(open=True, limit=0).results)
        if opened:
            notices.append(Notice('work', f'{opened} open {"ticket stays" if opened == 1 else "tickets stay"} with '
                                          f'{left.name}, out of view until it is active again: metaform map activate '
                                          f'{left.name} --confirm'))
    return dataclasses.replace(made, notices=tuple(notices)) if notices != list(made.notices) else made


def add_base(ctx: Context) -> Any:
    store = _other_project(ctx)
    return _switched(store, lambda: store.add_base(ctx.nouns['name']))


def collapse(ctx: Context) -> Any:
    store = _other_project(ctx)
    return _switched(store, lambda: store.collapse(ctx.nouns['name']))


def activate(ctx: Context) -> Any:
    store = _other_project(ctx)
    return _switched(store, lambda: store.activate_base(ctx.nouns['name']))


def remove_base(ctx: Context) -> Any:
    from metaform import home
    return home.remove_base(_other_project(ctx).project_id, ctx.nouns['name'])


def cypher(ctx: Context) -> Any:
    """A Cypher query over the base's graph in memory, for agents, STORE-046: reads only, seeing what the layers in
    view show, or the layers named. The answer is each returned column with its values in order."""
    given: Any = ctx.nouns['query']
    query = (' '.join(str(word) for word in cast(list[Any], given)) if isinstance(given, (list, tuple))
             else str(given))
    named = [name for name in str(ctx.nouns.get('layers') or '').split(',') if name]
    try:
        found = _store(ctx).cypher(query, named or None)
    except (Stop, OSError):  # the store's own refusal is said as itself
        raise
    except Exception as error:  # the query library refuses with errors of many types, its parser's and its own; each is said plainly with what usually causes it
        if type(error).__module__ == 'sqlite3':  # a failure of the store, not the query; modules import no sqlite3, BASE-004
            raise
        said = (str(error).strip().splitlines() or [type(error).__name__])[0][:300]
        raise Stop(f'The query was not understood: {said}. Strings take double quotes; edges are matched by their '
                   'kind, as [x] WHERE x.kind = "join".', 'metaform help map cypher') from None

    def scalar(value: Any) -> Any:
        return value if value is None or isinstance(value, (str, int, float, bool)) else str(value)
    columns = {str(name): [scalar(value) for value in values] for name, values in dict(found).items()}
    return {'columns': columns, 'rows': max((len(values) for values in columns.values()), default=0)}


def search(ctx: Context) -> Any:
    return _store(ctx).search(ctx.nouns['text'], ctx.nouns.get('layer'), **_paging(ctx))


def find(ctx: Context) -> Any:
    """What the map holds about some words, elements, joins and items, each by its Address, best first: the
    search an agent makes before it knows where to read, done in the store so it reads only the hits."""
    limit = ctx.nouns.get('limit')
    return {'results': _store(ctx).find(ctx.nouns['text'], limit=int(limit) if limit else 20)}


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


BLIND_SPOTS = 'The functions and encounters the design should have and does not.'
T = TypeVar('T')


def critic(ctx: Context) -> str:
    """One critic run: a new blind-spot layer, blinded by its type, and the critic prompt with the whole base,
    LAYER-014 and LAYER-015. Fast mode, blind to the code, is the default; --critic also reads the code."""
    store = _store(ctx)
    sighted = bool(ctx.setting('critic'))
    mode = 'critic' if sighted else 'fast'
    taken = {layer.name for layer in _every(lambda after: store.layers(after=after))}
    base = f'blind_spot_{mode}_{datetime.now(UTC).strftime("%Y%m%dt%H%M%Sz")}'
    name, count = base, 1
    while name in taken:
        count += 1
        name = f'{base}_{count}'
    store.layer(name, 'map', BLIND_SPOTS, mutable=False, hideable=True,
                provenance={'module': 'map', 'prompt': 'blind_spot_challenge', 'role': 'critic', 'blinded': not sighted})
    metaform = map_markdown(store, None, **_reading(ctx)).strip()
    folder = resources.files(__name__)
    return (prompt_files.required(folder, 'blind_spot_challenge') + '\n\n'
            + prompt_files.required(folder, f'critic_{mode}', layer=name, metaform=metaform))


def challenges(ctx: Context) -> str:
    """The answer prompt with each challenge of one blind-spot layer and its state, LAYER-015."""
    store = _store(ctx)
    layer = ctx.nouns['layer']
    lines: list[str] = []
    for found in _every(lambda after: store.layer_items(layer, after=after)):
        if not isinstance(found, Item):
            continue
        where = str(found.target)
        if found.target.kind == 'element':
            element = store.element(found.target.id, raw=True)
            where = f'element:{element.address}' if element is not None else where
        value = found.value if isinstance(found.value, str) else json.dumps(found.value, ensure_ascii=False)
        lines.append(f'{found.id}  {found.state or "open"}  {where}  {value}')
    return prompt_files.required(resources.files(__name__), 'answer_challenges', layer=layer, challenges='\n'.join(lines))


def _every(read: Callable[[str | None], Page[T]]) -> list[T]:
    """Every result of a paged read, page after page."""
    held: list[T] = []
    after: str | None = None
    while True:
        page = read(after)
        held.extend(page.results)
        if not page.next:
            return held
        after = page.next


def _need(ctx: Context, *names: str, verb: str = 'knowledge') -> None:
    """Stop a call missing a field its record cannot be stored without at all, before anything is written, BASE-038."""
    missing = [name for name in names if name not in ctx.nouns]
    if missing:
        op = ctx.nouns.get('op')
        said = f'{verb} op={op}' if op is not None else verb
        raise Stop(f'{said} needs {", ".join(missing)}.', f'metaform help map {verb}')


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
    'add-element': frozenset({'address', 'name_length', 'name', 'role', 'refs'}),  # refs go to the sources layer
    'add-join': frozenset({'receiver', 'elements', 'purpose', 'ef', 'ifd', 'type'}),
    'add-property': frozenset({'element', 'value', 'refs', 'extra'}),
    'link-context': frozenset({'element', 'content', 'refs'}),
    'add-item': frozenset({'node', 'value', 'link', 'refs', 'extra', 'read_first', 'always_show', 'task', 'condition'}),
    'add-ref': frozenset({'owner', 'key', 'value'}),
    'add-plan': frozenset({'element', 'join'}),
    'edit': frozenset({'id', *FIELDS}),
    'remove': frozenset({'id'}),
    'finish': frozenset(),
    'discard': frozenset(),
}

# The fields each knowledge operation cannot store its record without, besides op, BASE-038: the field that says what
# the record is, where it attaches, or which layer holds it. A call missing one stops and writes nothing.
NEEDS: dict[str, tuple[str, ...]] = {
    'create': ('layer',), 'add-element': ('address',), 'add-join': ('receiver', 'elements'),
    'link-context': ('layer', 'element', 'content'),
    'add-property': ('element',), 'add-item': ('node',), 'add-ref': ('owner',),
    'add-plan': ('layer', 'element'), 'edit': ('id',), 'remove': ('id',),
    'finish': ('layer',), 'discard': ('layer',),
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
    if isinstance(result, Page):  # a page of a list read is no dataclass
        return {**result.to_dict(), 'notices': notices}
    if 'notices' not in {field.name for field in dataclasses.fields(result)}:
        return {**result.to_dict(), 'notices': notices}
    return dataclasses.replace(result, notices=(*notices, *getattr(result, 'notices', ())))


STORE_ID = re.compile(r'\b[0-9a-f]{32}\b')
REFINE_FIELDS = ('name', 'name_length', 'role', 'block', 'within', 'purpose', 'ef', 'ifd', 'elements')
NAMING = ('receiver', 'provider', 'address')


def _said_as(store: Store, thing: str) -> str:
    """What an agent calls a thing the store names by id: an element by its address, a join by its receiver and the
    first element it holds."""
    found = store.element(thing, raw=True)
    if found is not None:
        return found.address
    versions = store.history(thing, limit=0).results
    fields = versions[-1].fields if versions else {}
    def at(ref: Any) -> str:
        element = store.element(str(ref), raw=True) if ref else None
        return element.address if element is not None else str(ref)
    if fields.get('receiver'):
        held = fields.get('elements') or [None]
        return f"the purpose of {at(fields['receiver'])} served by {held[0]}"
    return thing


def _in_words(store: Store, value: Any) -> Any:
    """A result with every store id said as the agent names the thing, MAP-005."""
    if isinstance(value, str):
        return STORE_ID.sub(lambda match: _said_as(store, match.group(0)), value)
    if isinstance(value, dict):
        return {key: _in_words(store, item) for key, item in cast(dict[Any, Any], value).items()}
    if isinstance(value, (list, tuple)):
        return [_in_words(store, item) for item in cast(list[Any] | tuple[Any, ...], value)]
    return value


def _purposes(store: Store, receiver: Any, provider: Any) -> list[Any]:
    owner = store.element(str(receiver), raw=True)
    if owner is None:
        return []
    return [held for held in store.joins(owner.id, limit=0).results
            if any(each.address == provider for each in held.elements)]


def _one(found: list[Any], what: str, notices: list[Notice], purposes: bool = False) -> Any:
    if len(found) == 1:
        return found[0]
    if not found:
        notices.append(Notice('purpose', f'There is no {what} in the base; nothing was changed.'))
    else:
        named = '; '.join(repr(item.purpose) for item in found) if purposes else str(len(found))
        notices.append(Notice('purpose', f'{len(found)} of {what} cannot be told apart by their addresses, '
                                             f'with the purposes {named}; nothing was changed.'))
    return None


def promote(ctx: Context) -> Any:
    """Associate a receiver's purpose with an ordinary element, preserving its join, MAP-054."""
    _need(ctx, 'receiver', 'provider', 'address', verb='promote')
    store = _store(ctx)
    nouns = ctx.nouns
    notices: list[Notice] = []
    said = f"the purpose of {nouns['receiver']} served by {nouns['provider']}"
    held = _one(_purposes(store, nouns['receiver'], nouns['provider']), said, notices, purposes=True)
    if held is None:
        return Outcome(tuple(notices))
    return store.promote_join(held.id, nouns['address'],
                              **_optional(ctx, 'name', 'name_length', 'role', 'reason'))


ELEMENT_SHAPE = ('name', 'name_length', 'role', 'block', 'within')
JOIN_SHAPE = ('purpose', 'ef', 'ifd')  # what a purpose record of the base is besides its receiver and elements


def _grown(ctx: Context, store: Store, made: Any, notices: list[Notice], op: str) -> dict[str, Any]:
    """What a growth of the base answers: what it named, the op, the layer, and every notice, in the agent's words."""
    named = {name: ctx.nouns[name] for name in (*NAMING, 'elements', 'to_address') if name in ctx.nouns}
    told = [*notices, *getattr(made, 'notices', ())]
    return _in_words(store, {**named, 'op': op if not isinstance(made, Outcome) else None,
                             'layer': getattr(made, 'layer', None),
                             'notices': [notice.to_dict() for notice in told]})


def _move(ctx: Context, store: Store, element: Any, reason: Any, notices: list[Notice]) -> dict[str, Any]:
    """Rename an element of the base, or merge it into the one at to_address: the store moves its purpose records and
    the knowledge at it, this module its tickets and messages, and the memory module its memories, told by
    `map.moved`, so nothing at the old address is orphaned, LAYER-025."""
    new = str(ctx.nouns['to_address'])
    with store.atomic():
        made = store.move(element.id, new, reason=reason, evidence=ctx.nouns.get('evidence'), by=author(ctx.surface))
        moved = store.retarget_work(element.id, made.id) if not isinstance(made, Outcome) else None
    if moved is not None:
        notices.append(Notice('work', f"{moved['work']} tickets, {moved['messages']} questions and messages and "
                                      f"{moved['links']} ticket links moved to {new}."))
        for delivery in ctx.publish('map.moved', {'old': element.address, 'new': new}):
            result = delivery.get('result')
            if delivery.get('status') != 'completed':
                notices.append(Notice(str(delivery.get('module')), f"{delivery.get('module')} did not move what it "
                                                                   f"keeps at {element.address}: "
                                                                   f"{delivery.get('error')}"))
            elif isinstance(result, dict) and cast(dict[str, Any], result).get('said'):
                notices.append(Notice(str(delivery.get('module')), str(cast(dict[str, Any], result)['said'])))
    return _grown(ctx, store, made, notices, 'move')


def _add_call(address: str) -> str:
    return (f'metaform map refine address={address} name=<its name> name_length=<n> role=<CQU, DE, SE or NE> '
            'reason=<why> evidence=<what shows it>')


def _join_call(receiver: Any, elements: Any) -> str:
    return (f'metaform map refine receiver={receiver} elements={json.dumps(elements)} purpose=<the OP> ef=<the EF> '
            'ifd=<sends, receives or both> reason=<why> evidence=<what shows it>')


def refine(ctx: Context) -> Any:
    """Refine the base: add, change or remove one element or join as its newest version in the base's own layer,
    every earlier version kept, LAYER-025. It names what it changes by address, never by id: an element by its
    address, a join by its receiver and an element it holds, MAP-005, or by its receiver and the elements it holds.
    What the base lacks is added under the intake's rules, by the same store writes the intake's verification pass
    uses; an element renamed or merged with to_address takes its joins, knowledge, tickets and memories with it; one a
    knowledge layer holds is taken in with adopt. Each change records its reason, evidence and author. It is a verb of
    its own, apart from knowledge, because it changes the base and no knowledge layer. Nothing is refused for its
    content, BASE-044."""
    nouns = ctx.nouns
    if not any(name in nouns for name in NAMING):
        raise Stop('refine needs address, or receiver with provider or elements, to name what it adds or changes.',
                   'metaform help map refine')
    store = _store(ctx)
    notices: list[Notice] = []
    (reason,) = _empty(ctx, notices, 'reason')
    by = author(ctx.surface)
    changes: dict[str, Any] = {name: nouns[name] for name in REFINE_FIELDS if name in nouns}
    thing: str | None = None
    if 'receiver' in nouns or 'provider' in nouns:
        receiver = nouns.get('receiver')
        elements = nouns.get('elements')
        if 'provider' not in nouns and isinstance(elements, list) and elements and receiver is not None:
            held_list = cast(list[Any], elements)
            owner = store.element(str(receiver), raw=True)
            found = [] if owner is None else [one for one in store.joins(owner.id, raw=True, limit=0).results
                                              if any(each.address in held_list for each in one.elements)]
            if not found:  # a purpose record the base lacks is added, as the intake records one, LAYER-025
                fields = {name: nouns.get(name) for name in JOIN_SHAPE}
                made = store.grow_join(receiver, held_list, **fields, reason=reason, evidence=nouns.get('evidence'),
                                       by=by)
                return _grown(ctx, store, made, [], 'add')
            changes.pop('elements')
            holding = [each.address for each in found[0].elements] if len(found) == 1 else []
            added = [address for address in held_list if address not in holding]
            if added:
                changes['elements'] = [*holding, *added]
            held = _one(found, f'the purpose of {receiver} holding {", ".join(map(str, held_list))}', notices,
                        purposes=True)
        else:
            said = f"the purpose of {receiver} served by {nouns.get('provider')}"
            purposes = _purposes(store, receiver, nouns.get('provider'))
            held = _one(purposes, said, notices, purposes=True)
            if not purposes:
                notices.append(Notice('next', 'To add it: ' + _join_call(receiver, [nouns.get('provider')])))
        if held is not None:
            thing = str(held.id)
            if nouns.get('adopt'):
                return _grown(ctx, store, store.adopt(thing, reason=reason, evidence=nouns.get('evidence'), by=by),
                              notices, 'adopt')
            if 'to_receiver' in nouns:
                changes['receiver'] = nouns['to_receiver']
    else:
        address = str(nouns['address'])
        element = store.element(address, raw=True)
        if element is None and any(name in nouns for name in ELEMENT_SHAPE):
            # an element the base lacks is added, as the intake records one, LAYER-025
            made = store.grow_element(address, **{name: nouns.get(name) for name in ELEMENT_SHAPE}, reason=reason,
                                      evidence=nouns.get('evidence'), by=by)
            return _grown(ctx, store, made, [], 'add')
        if element is None:
            notices.append(Notice('address', f'{address} is not an element of the base; nothing was changed. To add '
                                             f'it: {_add_call(address)}'))
        elif nouns.get('adopt'):
            return _grown(ctx, store, store.adopt(element.id, reason=reason, evidence=nouns.get('evidence'), by=by),
                          notices, 'adopt')
        elif 'to_address' in nouns:
            return _move(ctx, store, element, reason, notices)
        else:
            thing = element.id
    named = {name: nouns[name] for name in NAMING if name in nouns}
    if thing is None:
        return {**named, 'notices': [notice.to_dict() for notice in notices]}
    made = store.refine(thing, changes, remove=bool(nouns.get('remove')), reason=reason,
                        evidence=nouns.get('evidence'), by=by)
    told = [*notices, *getattr(made, 'notices', ())]
    told = [Notice('to_address' if notice.where == 'address' and 'to_address' in nouns else notice.where,
                   notice.message) for notice in told]
    fields = cast(dict[str, Any], getattr(made, 'fields', {}))
    kept = {key: value for key, value in fields.items() if key not in ('join_id', 'element_id', 'layer_id', 'row')}
    return _in_words(store, {**named, 'op': getattr(made, 'op', None), 'layer': getattr(made, 'layer', None),
                             'fields': kept, 'notices': [notice.to_dict() for notice in told]})


def knowledge(ctx: Context) -> Any:
    """Create, build, edit and finish a knowledge layer, one object per call, LAYER-018. Nothing is
    refused for its content; only a field in NEEDS stops a call, before anything is written, BASE-038 and BASE-044."""
    op = ctx.nouns.get('op')
    if op is None:
        raise Stop('knowledge needs op=, the operation to run.', 'metaform help map knowledge')
    if op not in READS:
        raise Stop(f'{op!r} is not a knowledge operation.', 'metaform help map knowledge')
    _need(ctx, *NEEDS.get(op, ()))
    if op == 'create' and ctx.nouns.get('kind', 'layer') != 'layer':
        raise Stop('knowledge creates a knowledge layer: kind=layer.',
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
        made = store.add_element(name, nouns['address'], **_optional(ctx, 'name_length', 'role'),
                                 name=nouns.get('name'))
        if 'refs' in nouns and not isinstance(made, Outcome):
            _sources(store, made.id, made.address, nouns['refs'], notices)
        return made
    if op == 'add-join':
        purpose, ef = _empty(ctx, notices, 'purpose', 'ef')
        return store.add_join(name, nouns['receiver'], nouns['elements'], purpose=purpose, ef=ef,
                              **_optional(ctx, 'ifd', 'type'))
    if op == 'link-context':
        return store.add_property(name, _element(nouns['element']), nouns['content'],
                                  refs=nouns.get('refs', ()), extra={'knowledge_root': nouns['content']})
    if op == 'add-property':
        (value,) = _empty(ctx, notices, 'value')
        return store.add_property(name, _element(nouns['element']), value, **_optional(ctx, 'refs', 'extra'))
    if op == 'add-item':
        (value,) = _empty(ctx, notices, 'value')
        link = _node(nouns['link']) if 'link' in nouns else None
        return store.add_item(name, _node(nouns['node']), value, link=link,
                              **_optional(ctx, 'refs', 'extra', 'read_first', 'always_show', 'task', 'condition'))
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
    if op == 'finish':
        return store.finish(name)
    if op == 'discard':
        return store.discard(name)
    raise Stop(f'{op!r} is not a knowledge operation.', 'metaform help map knowledge')



def _sources(store: Store, element_id: str, address: str, refs: Any, notices: list[Notice]) -> None:
    """The refs given with an element, each linked there as a record of the sources layer, code.graph.knowledge#c,
    replacing those last linked there: the metaform holds no refs, so they live in a sources layer."""
    notices.extend(notice for notice in store.place_refs(Node('element', element_id), refs, by='map',
                                                         why=f'given with {address}')
                   if notice.where != 'linked')
    notices.append(Notice('refs', f'The refs were written to the {SOURCES} layer at {address}; the base holds none.'))


def _noun(name: str, help: str, kind: NounKind = 'str', schema: dict[str, Any] | None = None) -> Noun:
    return Noun(name, help, kind=kind, required=False, schema=schema)


KNOWLEDGE_NOUNS = (
    _noun('content', 'link-context: namespace root of meaningful knowledge in this layer; element is its attachment scope.'),
    _noun('op', 'create, link-context, add-element, add-join, add-property, add-item, add-ref, add-plan, edit, remove, finish or '
                'discard.',
          schema={'type': 'string', 'enum': ['create', 'link-context', 'add-element', 'add-join', 'add-property', 'add-item', 'add-ref',
                                             'add-plan', 'edit', 'remove', 'finish', 'discard']}),
    _noun('layer', 'Stable layer name or id. Name it for its purpose or property, such as platformer or code.cpp. '
                   'link-context explicitly attaches it to a subtree. Legacy scope@content names remain readable.'),
    _noun('variable', 'create: the one question the layer answers.'),
    _noun('mutable', 'create: whether its items change in place.', 'bool'),
    _noun('hideable', 'create: whether it can be hidden.', 'bool'),
    _noun('kind', 'create: layer.'),
    _noun('fields', 'create: the fields of the variable, a JSON list of names.', 'json',
          {'type': 'array', 'items': {'type': 'string'}}),
    _noun('sources', 'create: the layers it is built from, a JSON list of layer names or ids.', 'json',
          {'type': 'array', 'items': {'type': 'string'}}),
    _noun('tags', 'create: its tags, a JSON list.', 'json', {'type': 'array', 'items': {'type': 'string'}}),
    _noun('module', 'create: the module that makes the layer.'),
    _noun('workflow', 'create: the workflow within that module.'),
    _noun('prompt', 'create: the prompt the layer is made from.'),
    _noun('model', 'create: the model that makes it.'),
    _noun('role', 'create: the role of its producer; add-element: CQU, DE, SE or NE, the role of the element.'),
    _noun('blinded', 'create: whether the producer saw only the map.', 'bool'),
    _noun('address', 'add-element: the element\'s dotted namespace address. An element cannot be moved: edit does '
                     'not apply it.'),
    _noun('name', 'add-element: Canonical Name (Project official terminology) or Informal Name of the element.'),
    _noun('name_length', 'add-element: name_length, as defined in the intake procedure.', 'int'),
    _noun('refs', 'add-property and add-item: a JSON list of [key, value] pairs, in order; add-element: the element\'s '
                  'refs, written to the sources layer.', 'json', REFS_SCHEMA),
    _noun('extra', 'add-property and add-item: a JSON object of further fields.', 'json', {'type': 'object'}),
    _noun('receiver', 'add-join: the element that holds the purpose; edit: another receiver, which moves the join.'),
    _noun('elements', 'add-join and edit: the elements that serve the purpose, a JSON list of addresses.', 'json',
          {'type': 'array', 'items': {'type': 'string'}}),
    _noun('purpose', 'add-join: the receiver\'s purpose, the OP, as defined in the intake procedure.'),
    _noun('ef', 'add-join: the encounter function, the EF, as defined in the intake procedure.'),
    _noun('ifd', 'add-join: sends, receives or both, the information flow direction as defined in the intake procedure.',
          schema={'type': 'string', 'enum': ['sends', 'receives', 'both']}),
    _noun('type', 'add-join: the join type, purpose by default.'),
    _noun('join', 'add-plan: the join id.'),
    _noun('element', 'add-property and add-plan: the element, by address or id, or as a node such as type:code.'),
    _noun('value', 'add-item, add-property, edit and add-ref: the value, as JSON: text, a number, true or false, a list '
                   'or an object.', 'json',
          {'type': ['string', 'number', 'boolean', 'array', 'object', 'null']}),
    _noun('node', 'add-item: element:<address or id> or join:<id>.'),
    _noun('link', 'add-item: a node the item links to.'),
    _noun('read_first', 'add-item and edit: the item is read before the task.', 'bool'),
    _noun('always_show', 'add-item and edit: the item is always shown.', 'bool'),
    _noun('task', 'add-item: the item is a task; it adds a ticket at its node, and the flag is not stored on the item.',
          'bool'),
    _noun('condition', "add-item with task: the part's state, unbuilt, under-construction, built or broken, only "
                       "when the part is in that state; left out for a task on a part that exists and works."),
    _noun('owner', 'add-ref: the id of the thing the ref belongs to.'),
    _noun('key', 'add-ref: the ref key.'),
    _noun('id', 'edit and remove: the id of the thing.'),
)
# What each field means when refine changes it, apart from the knowledge operations that write it first.
REFINE_WORDS = {
    'address': "An element's address cannot change: given for an element, it is not applied.",
    'name': "The project's own name for the element or the join's functionality.",
    'name_length': 'name_length, as defined in the intake procedure.',
    'role': 'CQU, DE, SE or NE.',
    'receiver': 'Another receiver, which moves the join.',
    'elements': 'The elements the join holds, a JSON list of addresses: they replace the ones a join named by receiver '
                'and provider held; with receiver alone they name the join that holds them, or the new one to add.',
    'purpose': "The receiver's purpose, the OP, as defined in the intake procedure.",
    'ef': 'The encounter function, the EF, as defined in the intake procedure.',
    'ifd': 'sends, receives or both, the information flow direction as defined in the intake procedure.',
    'type': 'The join type.',
    'element': 'The element, by address or id.',
    'value': 'The value, as JSON.',
    'link': 'A node the item links to.',
}


def _refined_noun(noun: Noun) -> Noun:
    return Noun(noun.name, REFINE_WORDS[noun.name], kind=noun.kind, required=False, schema=noun.schema)


REFINE_NOUNS = (
    _noun('receiver', 'A join: the element that holds it, by address.'),
    _noun('provider', 'A join: an element it holds, by address.'),
    _noun('address', 'An element, by address.'),
    _noun('reason', 'Why.'),
    _noun('evidence', 'What shows it.'),
    _noun('remove', 'Remove it from the base instead of changing it; its versions are kept.', 'bool'),
    _noun('to_receiver', 'A join: its new receiver, by address; it moves and stays the same join.'),
    _noun('to_address', 'An element: its new address. It is renamed, or merged into the element already there, '
                        'and its joins, knowledge, tickets and memories go with it.'),
    _noun('adopt', 'Take an element or join a knowledge layer holds into the base, keeping its id.', 'bool'),
    _noun('block', 'An element: its numbered ICE block identifier; null clears it.', 'json',
          {'type': ['string', 'null']}),
    _noun('within', 'An element: its containing element by namespace address; null clears it.', 'json',
          {'type': ['string', 'null']}),
    *(_refined_noun(noun) for noun in KNOWLEDGE_NOUNS if noun.name in REFINE_FIELDS),
)

# The nouns each work operation reads, besides op.
WORK_READS: dict[str, frozenset[str]] = {
    'glyphs': frozenset(),
    'unhold_all': frozenset({'hold_preview'}),
    'list': frozenset({'node', 'receiver', 'provider', 'address', 'condition', 'kind', 'open', 'limit', 'after',
                       'hold', 'board'}),
    'read': frozenset({'id'}),
    'sources': frozenset({'id', 'source_id'}),
    'remove': frozenset({'id'}),
    'add': frozenset({'node', 'receiver', 'provider', 'address', 'condition', 'kind', 'note', 'task', 'held', 'reviewed',
                      'links', 'agent', 'model', 'effort', 'fast', 'hold', 'eligible', 'after_work', 'title', 'epic',
                      'agents', 'board', 'hold_reason', 'source'}),
    'edit': frozenset({'id', 'node', 'receiver', 'provider', 'address', 'condition', 'kind', 'note', 'task', 'held',
                       'reviewed', 'glyph', 'links', 'agent', 'hold', 'eligible', 'after_work', 'title',
                       'epic', 'agents', 'board', 'model', 'effort', 'fast', 'hold_reason', 'source'}),
    'done': frozenset({'id', 'resolution', 'why'}),
    'take': frozenset({'id', 'steps', 'by'}),
    'move': frozenset({'id', 'column', 'position', 'by', 'hold_reason'}),
    'plan': frozenset({'id', 'steps'}),
    'step': frozenset({'id', 'said'}),
    'distribute': frozenset({'agents'}),
}
WORK_FIELDS = ('condition', 'kind', 'note', 'task', 'held', 'reviewed')  # the chassis work record's own, STORE-042
# The long fields a list row leaves out, each read with the ticket by id=, so the list stays small, MAP-049 and MAP-053.
UNLISTED = frozenset({'said', 'resolution', 'task'})

# The agent glyphs a ticket is assigned to, VIEW-040: the seventeen characters the page draws, in the order of GLYPHS in
# the web page's agents3d.js. Tickets with the same glyph signify one agent doing them one at a time.
AGENT_GLYPHS = ('jelly', 'gearling', 'kite', 'moth', 'drone', 'snail', 'crystal', 'wisp', 'comet', 'beetle', 'slime',
                'plane', 'puffer', 'owl', 'cubebot', 'mushroom', 'seahorse')
TICKET_AGENTS = ('claude', 'codex', 'antigravity')  # the agents a ticket can prefer, as dispatch starts them
AGENT_TYPES = TICKET_AGENTS

# The map module's own tables, STORE-045: `glyphs` keeps the agent glyph each ticket is assigned to, keyed by the work
# id, beside the map as the work records are, so the chassis work table holds no glyph, BASE-046 and ticket 90430bba.
# The field each work operation cannot store its record without, BASE-038: the object it attaches to, or the record.
WORK_NEEDS: dict[str, tuple[str, ...]] = {'list': (), 'glyphs': (), 'read': ('id',), 'sources': ('id',), 'add': (), 'edit': ('id',), 'done': ('id',),
                                          'take': ('id',), 'plan': ('id', 'steps'), 'step': ('id',),
                                          'move': ('id', 'column'), 'distribute': ('agents',), 'remove': ('id',), 'unhold_all': ()}


def _work_node(value: Any) -> Node:
    """A node written `kind:<address or id>`, or a bare address or id, which names an element."""
    if isinstance(value, str) and ':' in value and value.partition(':')[0] in PLACE_KINDS:
        return Node.parse(value)
    return Node('element', str(value))


def _named(store: Store, given: dict[str, Any], notices: list[Notice]) -> Node | None:
    """The node a call names by address, MAP-005: a purpose by its receiver and provider, a part by its address
    inside it, an element by its address; or the node noun as written. A node noun given beside them is named in a
    notice as not read."""
    if 'receiver' in given or 'provider' in given or 'address' in given:
        if 'node' in given:
            notices.append(Notice('node', 'receiver, provider and address name the node; node was not read.'))
        if 'receiver' in given or 'provider' in given:
            return store.purpose(given.get('receiver'), given.get('provider'), given.get('address'))
        return Node('element', str(given['address']))
    return _work_node(given['node']) if 'node' in given else None


def _link(store: Store, value: Any) -> Node:
    """A node a ticket links: written as a node, or as an object of receiver, provider and address."""
    if isinstance(value, dict):
        found = _named(store, cast(dict[str, Any], value), [])
        if found is not None:
            return found
    return _work_node(value)


def _held(store: Store, nouns: dict[str, Any], notices: list[Notice]) -> Node:
    """The node ask and tell name, node first, an element by its address, or with provider beside it
    the purpose it holds as receiver, and with address the part at that address inside it, MAP-005."""
    if 'provider' not in nouns:
        if 'address' in nouns:
            notices.append(Notice('address', 'address names an element a join holds only with provider; it was not read.'))
        return _work_node(nouns['node'])
    node = str(nouns['node'])
    receiver = node.partition(':')[2] if node.startswith('element:') else node
    return store.purpose(receiver, nouns['provider'], nouns.get('address'))


def ask(ctx: Context) -> Any:
    """The person asks a question at a node, MAP-050, for the record and for the agent they talk to there. Agents do
    not ask: the verb is the person's, on the command line and the page. A question records a decision to be made, so
    it carries a short title and why, and takes the next number at its node, MCP-037."""
    titled(ctx, 'The question', ctx.nouns.get('title'), ctx.nouns.get('why'), why_needed=True,
           why_step='add why: one line saying why it is asked')
    store, notices = _store(ctx), list[Notice]()
    _numbering(store)
    asked = store.ask(_held(store, ctx.nouns, notices), ctx.nouns['question'], suggestions=ctx.nouns.get('suggestions'),
                      by=ctx.nouns.get('by'), work=ctx.nouns.get('work'), title=ctx.nouns.get('title'),
                      why=ctx.nouns.get('why'))
    return _with_notices(_numbered_messages(store, asked), notices)


def _numbering(store: Store) -> None:
    """Number the work records and messages written before items were numbered, the first time map reads or writes
    them after its tables reach version 10, MCP-037."""
    if not store.items_numbered():
        store.number_items()


def _numbered_messages(store: Store, result: Any) -> Any:
    """A message, or a page of them, each with its `item`, `<address>#<n>`, and `title` when it has a number."""
    page = cast(Page[Any], result) if isinstance(result, Page) else None
    records: list[Any] = list(page.results) if page is not None else [result]
    found = store.numbers_of('message', [record.id for record in records])
    if not found:
        return cast(Any, result)

    def one(record: Any) -> Any:
        if record.id not in found:
            return record
        item, title, _ = found[record.id]
        return {**record.to_dict(), 'item': item, 'title': title}
    if page is not None:
        return {**page.to_dict(), 'results': [one(record) for record in records]}
    return one(records[0])


def reply(ctx: Context) -> Any:
    """Answer a question, or mark a message read, MAP-050. Over MCP a question linked to a ticket is not answered:
    it is a dispatched agent's permission request, the person's to answer, BASE-052. This goes by surface and not by
    role on purpose: no agent answers a permission, however it was started."""
    return _store(ctx).reply(ctx.nouns['id'], ctx.nouns.get('answer'), agent=ctx.surface == 'mcp')


def reopen(ctx: Context) -> Any:
    """Reopen a question answered by mistake, so it waits again with its suggestions, MAP-050."""
    return _store(ctx).reopen(ctx.nouns['id'])


def messages(ctx: Context) -> Any:
    """List questions and messages, or move one to another node, preserving its answer and state, MAP-050."""
    nouns = ctx.nouns
    op = str(nouns.get('op', 'list'))
    if op not in ('list', 'move'):
        raise Stop(f'{op!r} is not a messages operation: op=list or move.', 'metaform help map messages')
    store, notices = _store(ctx), list[Notice]()
    reads = ({'id', 'node', 'provider', 'address'} if op == 'move'
             else {'node', 'kind', 'open', 'limit', 'after'})
    for name in sorted(nouns):
        if name != 'op' and name not in reads:
            notices.append(Notice(name, f'op={op} does not read {name}; it was ignored.'))
    _numbering(store)
    if op == 'move':
        _need(ctx, 'id', 'node', verb='messages')
        return _with_notices(_numbered_messages(store, store.move_message(nouns['id'], _held(store, nouns, notices))),
                             notices)
    node = _work_node(nouns['node']) if 'node' in nouns else None
    return _with_notices(_numbered_messages(store, store.messages(node, nouns.get('kind'), nouns.get('open'),
                                                                  **_paging(ctx))), notices)


@ticket_history.per_call
def work(ctx: Context) -> Any:
    """The work records: the condition of an element or a join, apart from the map, MAP-046 and STORE-042.
    op=list, the default, reads them, and an id with no op reads one; add, edit, take, plan, step, move and done
    write one each, and distribute gives the open tickets the glyphs of N agents, VIEW-040. A no-task stage
    records part state, separately from executable work."""
    # An id with no op reads that one ticket with what the map holds at its node and its links, MAP-048.
    op = str(ctx.nouns.get('op', 'read' if 'id' in ctx.nouns else 'list'))
    if op not in WORK_READS or op == 'read' and 'op' in ctx.nouns:
        raise Stop(f'{op!r} is not a work operation: op=list, glyphs, sources, add, edit, take, plan, step, move, distribute, done or remove; '
                   'unhold_all; with id= and '
                   'no op, the one ticket is read.', 'metaform help map work')
    _need(ctx, *WORK_NEEDS[op], verb='work')
    unread = sorted(name for name in ctx.nouns if name != 'op' and name not in WORK_READS[op])
    notices = [Notice(name, f'op={op} does not read {name}; it was ignored.') for name in unread]
    for name in unread:
        ctx.nouns.pop(name)
    store, nouns = _store(ctx), ctx.nouns
    if isinstance(nouns.get('after_work'), list):  # each as `map work` takes it: its id, or its `<address>#<n>`
        nouns['after_work'] = [_work_id(store, one) if isinstance(one, str) else one
                               for one in cast(list[Any], nouns['after_work'])]
    if op == 'unhold_all':
        from .holds import unhold_all_project, unhold_reviewed_project
        if 'hold_preview' in nouns:
            return unhold_reviewed_project(store, nouns['hold_preview'])
        return {'changed': unhold_all_project(store)}
    if op == 'glyphs':
        return {'glyphs': list(AGENT_GLYPHS)}
    if op == 'list':
        _numbering(store)
        node = _named(store, nouns, notices)
        # An element's list holds the tickets on the joins it receives or provides too, so an agent told its node
        # finds its ticket, ticket dd2a9caf.
        # Open records unless open=false asks for the done ones: the done records with their logs made the bare list
        # too large to read, MAP-049.
        found = store.work(node, nouns.get('condition'), nouns.get('open', True), **_paging(ctx), joins=True,
                           kind=nouns.get('kind'))
        if not nouns.get('hold'):  # a ticket the person holds is hidden from agents unless asked for with hold=true
            kept = _settings(store, [record.id for record in found.results])
            found = found._replace(results=tuple(record for record in found.results
                                                 if not kept.get(record.id, {}).get('hold')))
        if 'board' in nouns:  # one named board's tickets, '' the first board's
            kept = _settings(store, [record.id for record in found.results])
            wanted = str(nouns.get('board') or '')
            found = found._replace(results=tuple(record for record in found.results
                                                 if str(kept.get(record.id, {}).get('board') or '') == wanted))
        listed = plain(_glyphed(store, found))
        # Each says whether it is open or done, so a list asked for done and open records alike can be read and
        # filtered by it, where `done` is a time.
        listed['results'] = [{**{name: value for name, value in row.items() if name not in UNLISTED},
                              'status': 'done' if row.get('done') else 'open'} for row in listed['results']]
        if not listed['results'] and node is None and (kept := store.kept_map_said()):
            notices.append(Notice('map', kept))  # no ticket because the active map is empty, not because none is open
        return _with_notices(listed, notices)
    if op == 'sources':
        return list(store.work_sources(_work_id(store, str(nouns['id'])), nouns.get('source_id')))
    if op == 'add':
        node = _named(store, nouns, notices)
        if node is None:
            raise Stop('work op=add needs node, or receiver and provider.', 'metaform help map work')
        titled(ctx, 'The ticket', nouns.get('title'))  # it takes the next number at its node, MCP-037
        # Non-work stages show the part's state without assigning implementation. A marker starts from its note;
        # unknown conditions remain the store's to validate. Use the same visibility contract as the DAO.
        condition = nouns.get('condition')
        if not shown_open(condition, nouns.get('task')) and (condition in CONDITIONS or condition in (None, '', 'none')):
            raise Stop('A ticket needs a task: the task is what an agent works from, so a ticket without one never '
                       'starts.', 'add task="what it needs, and the check that shows it done"')
        _numbering(store)
        # A missing condition is stored empty, and the store names it in its notice, STORE-042.
        with store.atomic():
            added = store.add_work(node, nouns.get('condition'),
                                   links=[_link(store, link) for link in nouns.get('links') or ()],
                                   provenance=_work_provenance(ctx),
                                   **_optional(ctx, 'kind', 'note', 'task', 'held', 'reviewed', 'title', 'hold_reason'))
            # a ticket filed with no board lands on the active board, 2026-10-21; board='' names the first on purpose
            _keep(store, added.id, nouns if 'board' in nouns else {**nouns, 'board': ctx.setting('board')}, notices, ctx)
        return _on_word(ctx, _added_on_word(ctx, store, added.id, nouns.get('after_work')),
                        _written(ctx, store, added, 'add', notices))
    if op == 'distribute':
        return _with_notices(_glyphed(store, _distribute(store, nouns['agents'])), notices)
    if op == 'read':
        # Live tickets win. A shed ticket's citation reads its completed commit instead.
        try:
            work_id = _work_id(store, str(nouns['id']))
            ticket = store.ticket(work_id)
        except (Stop, StoreError):
            committed = ticket_history.resolve(store.project_id, str(nouns['id']))
            if committed is not None:
                return _with_notices(committed, notices)
            raise
        return _with_notices(_with_work_modules(ctx, ticket), notices)
    work_id = _work_id(store, str(nouns['id']))
    word = _orchestrating(ctx, store, op, work_id, nouns)
    if op == 'remove':  # the person deletes a ticket for good, 2026-10-20; an agent on it is stopped by the caller
        with store.atomic():
            removed = store.remove_work(work_id)
        return _with_notices(removed, notices)
    if op == 'take':
        with store.atomic():
            taken = store.take_work(work_id, nouns.get('steps'), nouns.get('by'))
        return _written(ctx, store, taken, 'take', notices)
    if op == 'move':
        with store.atomic():
            previous = store.ticket(work_id).work.column
            moved = store.move_work(work_id, nouns['column'], nouns.get('position'), nouns.get('by'),
                                    hold_reason=nouns.get('hold_reason'))
        if previous != 'todo' and moved.column == 'todo':
            ctx.publish('work.requeued', {'project': store.project_id, 'work_id': work_id,
                                         'previous': previous, 'revision': time.time_ns()})
        return _on_word(ctx, word, _written(ctx, store, moved, 'move', notices))
    if op == 'plan':
        return _written(ctx, store, store.plan_work(work_id, nouns['steps']), 'plan', notices)
    if op == 'step':
        return _written(ctx, store, store.step_work(work_id, nouns.get('said')), 'step', notices)
    if op == 'edit':
        changes = {name: nouns[name] for name in (*WORK_FIELDS, 'title', 'hold_reason') if name in nouns}
        node = _named(store, nouns, notices)
        if node is not None:
            changes['node'] = node
        if 'links' in nouns:
            changes['links'] = [_link(store, link) for link in nouns['links'] or ()]
        provenance = _work_provenance(ctx) if 'task' in changes or 'source' in nouns else None
        with store.atomic():
            edited = store.edit_work(work_id, changes, provenance=provenance)
            if 'glyph' in nouns:
                _assign(store, {work_id: _glyph(nouns['glyph'], notices)})
            _keep(store, work_id, nouns, notices, ctx)
        return _on_word(ctx, word, _written(ctx, store, edited, 'edit', notices))
    # A resolution records a decision, so it carries a short why, kept with the ticket's number, MCP-037.
    titled(ctx, 'The resolution', None, nouns.get('why'), why_needed=True, title_needed=False,
           why_step='add why: one line saying why it was resolved this way')
    finished = store.finish_work(work_id, nouns.get('resolution'), nouns.get('why'))
    # what the work built belongs on the map in use: each gap at the ticket's node, or where its session linked a
    # file, is said with the refine call that closes it, LAYER-025; the ticket is done either way, BASE-044
    notices += store.landing(finished.node_kind, finished.node_id, finished.id)
    # Delivery failures name the missing evidence while preserving the submitted result.
    return _written(ctx, store, finished, 'done' if finished.done else 'delivery', notices)


def _written(ctx: Context, store: Store, record: WorkRecord, op: str, notices: list[Notice]) -> Any:
    """What a ticket write answers. To an agent over MCP, one line, MCP-037: the ticket's `<address>#<n>` and title
    and what the write did, from the map module's `work_<op>` prompt, then each notice on a line of its own; the
    record is a read away, `map_work id=<id>`, so the agent is not handed back what it just sent. Elsewhere the record
    with what the map keeps on it, as every read gives it. Filing also returns its board and column."""
    board = str(_settings(store, [record.id]).get(record.id, {}).get('board') or '') if op == 'add' else ''
    if ctx.surface != 'mcp':
        if op == 'add':
            receipt = plain(_glyphed(store, record))
            receipt['column'] = record.column
            receipt['map'] = {**receipt.get('map', {}), 'board': board}
            return _with_notices(receipt, notices)
        return _with_notices(_glyphed(store, record), notices)
    numbered = _work_numbers(store, [record.id]).get(record.id, {})
    fills = {'item': str(numbered.get('item') or record.id), 'title': str(numbered.get('title') or ''),
             'id': record.id, 'by': str(record.taken_by or ''), 'column': record.column,
             'board': board or 'the first board',
             'done': str(record.steps_done), 'steps': str(record.steps or record.steps_done)}
    line = ' '.join(_prompt(f'work_{op}', **fills).split())
    # Who else is at work at the part, from the module that runs agents, when the agent starts or plans its work.
    told = [said for _, made in provided(ctx.folder, 'work.overlap') if (said := made(ctx, record.id))] \
        if op in ('take', 'plan') else []
    return '\n'.join([line, *(_prompt('work_notice', where=one.where, message=one.message)
                              for one in (*notices, *record.notices)), *told])


def _glyph(value: Any, notices: list[Notice]) -> str | None:
    """A ticket's agent glyph, VIEW-040: one of the seventeen the page draws, or none; any other name is stored as given
    with a notice, BASE-044."""
    if not value:  # none, or an empty choice, takes the glyph away
        return None
    if value in AGENT_GLYPHS:
        return value
    notices.append(Notice('glyph', f'{value!r} is not one of the agent glyphs, {", ".join(AGENT_GLYPHS)}; it was stored '
                                   'as given.'))
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _assign(store: Store, glyphs: dict[str, str | None]) -> None:
    """Give each ticket its glyph in the map module's own table, STORE-045; None takes its glyph away."""
    with store.tables() as tx:
        for work_id, glyph in glyphs.items():
            if glyph is None:
                tx.delete('glyphs', {'work_id': work_id})
            elif tx.update('glyphs', {'work_id': work_id}, {'glyph': glyph}) is None:
                tx.insert('glyphs', {'work_id': work_id, 'glyph': glyph})


def _glyphs(store: Store, work_ids: list[str]) -> dict[str, str]:
    """The glyph each of these tickets is assigned to, read in one transaction; a ticket with none is left out."""
    with store.tables(write=False) as tx:
        found = {work_id: tx.get('glyphs', {'work_id': work_id}) for work_id in work_ids}
    return {work_id: row['glyph'] for work_id, row in found.items() if row is not None}


def _settings(store: Store, work_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Each ticket's runtime choice, decision, hold and eligibility, read in one transaction; a ticket with no
    settings is left out."""
    with store.tables(write=False) as tx:
        found = {work_id: tx.get('ticket_settings', {'work_id': work_id}) for work_id in work_ids}
        eligible = {work_id: tx.get('eligible', {'work_id': work_id}) for work_id in work_ids}
        after = {work_id: tx.get('after', {'work_id': work_id}) for work_id in work_ids}
    kept = {work_id: {'agent': row['agent'], 'hold': bool(row['hold']),
                      **{field: row[field] for field in ('model', 'effort', 'fast', 'decision', 'hold_reason') if row.get(field) is not None},
                      **({'proof': True, 'landed': row['landed']} if row['proof'] else {}),
                      **({'epic': row['epic']} if row['epic'] else {}),
                      **({'board': row['board']} if row.get('board') else {}),
                      **({'agents': row['agents']} if row['agents'] else {})}
            for work_id, row in found.items() if row is not None}
    for work_id, row in eligible.items():
        if row is not None:
            kept.setdefault(work_id, {})['eligible'] = row['agents']
    for work_id, row in after.items():
        if row is not None:
            kept.setdefault(work_id, {})['after_work'] = row['works']
    return kept


def _work_provenance(ctx: Context) -> dict[str, Any]:
    """Record authenticated caller provenance and source words without converting interpretation into a user quote."""
    supplied = ctx.nouns.get('source')
    details: dict[str, Any] = dict(cast(dict[str, Any], supplied)) if isinstance(supplied, dict) else {}
    agent = ctx.session or agent_caller()
    author = 'agent' if agent or str(ctx.surface) == 'internal' else 'user'
    details.update(author=author, session_id=ctx.session, surface=ctx.surface)
    word = persons_word(ctx.folder, 'Retaining the source of a work request', ctx.project) if agent else None
    if word and not details.get('text'):
        details['text'] = word.get('text')
        details['message'] = {key: word[key] for key in ('id', 'at', 'session_id') if key in word}
        details['source_author'] = 'user'
    return details


def _orchestrating(ctx: Context, store: Store, op: str, work_id: str,
                   nouns: dict[str, Any]) -> tuple[dict[str, Any], str, list[str]] | None:
    """Retain available user-message provenance for releases and ordering without authorizing those operations.

    A missing message does not block a peer's delegated decisions. Existing coverage links remain factual
    provenance, and each change records only the ticket it actually updates.
    """
    if ctx.surface not in ('mcp', 'cli'):
        return None
    if not (op == 'edit' and (nouns.get('held') is False or nouns.get('hold') is False or 'after_work' in nouns)
            or op == 'move' and nouns.get('column') in ('todo', 'backlog')):
        return None  # decided from the call alone: most writes read nothing more
    record = store.ticket(work_id).work
    kept = _settings(store, [work_id]).get(work_id, {})
    did: list[str] = []
    tickets = [work_id]  # checked: the ticket and each it is set to wait on; the word's work grows by the ticket alone
    if op == 'edit':
        if nouns.get('held') is False and record.held:
            did.append('released it from Backlog')
        if nouns.get('hold') is False and kept.get('hold'):
            did.append('let go of its hold')
        if 'after_work' in nouns:
            waits = nouns['after_work']
            did.append(f'set it to wait on {", ".join(str(one) for one in cast(list[Any], waits))}'
                       if isinstance(waits, list) and waits else 'set it to wait on no other ticket')
            if isinstance(waits, list):  # Include cited prerequisites in the provenance lookup.
                tickets += [str(one) for one in cast(list[Any], waits) if str(one) not in tickets]
    else:
        if record.held and nouns.get('column') == 'todo':
            did.append('released it from Backlog to To do')
        if nouns.get('position') is not None and nouns.get('column') in ('todo', 'backlog'):
            did.append(f'put it at place {nouns["position"]} of {nouns["column"]}')
    if not did:
        return None
    said = f'{" and ".join(did)} on ticket {work_id}'
    joined = _joining(ctx, store, f'Setting ticket {work_id} to wait on the work', nouns.get('after_work')) \
        if op == 'edit' else None
    if joined is not None:  # Retain an existing user-message link when it covers these prerequisites.
        return joined, said, [work_id]
    word = persons_word(ctx.folder, f'Updating tickets ({said})', ctx.project, tickets)
    return None if word is None else (word, said, [work_id])


def _added_on_word(ctx: Context, store: Store, work_id: str,
                   waits: Any) -> tuple[dict[str, Any], str, list[str]] | None:
    """A ticket the person's system agent adds to wait on others, `after_work`: in a turn the person's own message
    started, the next wave of the work that message started; in any later turn, when every open ticket it waits on is
    in one work their word covers that the person has not stopped, the wave the agent plans next of that work
    (`_joining`). Either way it joins the work that word covers and is recorded in the chat with it. A ticket that
    waits on anything outside that work joins none. This cover does not add a hold or change prerequisites."""
    if ctx.surface not in ('mcp', 'cli') or not isinstance(waits, list) or not waits:
        return None
    word = persons_word(ctx.folder, f'Adding ticket {work_id} to the work', ctx.project)
    if word is None or word.get('covered'):
        word = _joining(ctx, store, f'Adding ticket {work_id} to the work', waits)
    if word is None:
        return None
    return word, f'added ticket {work_id} to wait on {", ".join(str(one) for one in cast(list[Any], waits))}', [work_id]


def _joining(ctx: Context, store: Store, what: str, waits: Any) -> dict[str, Any] | None:
    """The person's word whose work holds every open ticket of `waits`, the tickets a ticket is set to wait on, so that
    ticket joins the work as its next wave: asked of the system agent's runner with those tickets, which answers only
    when all of them are held by one cover the person has not stopped (dispatch's `covering`). None when it waits on
    no open ticket, on any outside that work, or the caller has no such word."""
    if ctx.surface not in ('mcp', 'cli') or not isinstance(waits, list) or not waits:
        return None
    opened: list[str] = []
    for one in cast(list[Any], waits):
        try:
            record = store.ticket(_work_id(store, str(one))).work
        except (Stop, StoreError):
            continue  # gone: waited on no more
        if record.done is None:
            opened.append(record.id)
    return persons_word(ctx.folder, what, ctx.project, opened) if opened else None


def _on_word(ctx: Context, word: tuple[dict[str, Any], str, list[str]] | None, result: Any) -> Any:
    """A ticket write the person's word let their system agent make, recorded in its chat with that word, and said in
    the result; any other write's result as it is."""
    if word is None:
        return result
    given, said, tickets = word
    persons_word_acted(ctx.folder, given, said, ctx.project, tickets)
    line = f'On the person\'s word, "{given.get("text")}": {said}.'
    if isinstance(result, str):
        return f'{result}\n{line}'
    if isinstance(result, dict):
        return {**cast(dict[str, Any], result), 'on_word': {'text': given.get('text'), 'at': given.get('at'),
                                                             'did': said}}
    return result


def _board(store: Store, name: Any) -> str | None:
    """A ticket's board as given: '' or none is the project's first board; a name must be a board map boards lists."""
    wanted = str(name or '').strip()
    if not wanted:
        return None
    with store.tables(write=False) as tx:
        if tx.get('boards', {'name': wanted}) is None:
            raise Stop(f'There is no board named {wanted!r}.', f'metaform map boards op=add name="{wanted}"')
    return wanted


def _shed(store: Store, name: str, line: str) -> dict[str, Any]:
    """Remove completed records only when Git retains their exact citation on dev."""
    commits = ticket_history.read(store.project_id)
    records = store.work(open=False, limit=0).results
    kept_settings = _settings(store, [record.id for record in records])
    numbers = _work_numbers(store, [record.id for record in records])
    removed: list[str] = []
    kept: list[dict[str, str]] = []
    for record in records:
        if not record.done or record.done > line or str(kept_settings.get(record.id, {}).get('board') or '') != name:
            continue
        item = str(numbers.get(record.id, {}).get('item') or record.id)
        commit = commits.tickets.get(record.id)
        target = f'{record.node_kind}:{record.address if record.node_kind == "element" else record.node_id}'
        fault = commits.fault or ('No completion commit on the active dev branch.' if commit is None else
                                 'The completion commit does not preserve this ticket number.'
                                 if commit['item'] != item else
                                 'The completion commit predates this ticket completion.'
                                 if commit['done'] < record.done else
                                 'The completion commit does not preserve this ticket resolution.'
                                 if record.resolution and not any(
                                     f'\n\n{prefix}{record.resolution}\n\n' in f'{commit["body"]}\n\n'
                                     for prefix in ('', 'Resolution: ')) else
                                 'The completion commit does not preserve this ticket attachment.'
                                 if commit['target'] != target else
                                 'The completion commit does not preserve this ticket state.'
                                 if f'\n\nTicket state:\n{store.work_snapshot(record.id)}\n\n' not in
                                 f'{commit["body"]}\n\n' else None)
        if fault:
            kept.append({'id': record.id, 'item': item, 'fault': fault})
            continue
        store.remove_work(record.id)
        removed.append(record.id)
    return {'removed': removed, 'kept': kept}


@ticket_history.per_call
def boards(ctx: Context) -> dict[str, Any]:
    """List and organize boards. The first board has no name and always remains. The archive line sheds
    completed tickets whose Git commits retain their citations, keeping records without proof. Remove requires
    an empty named board. Wipe backs up ticket-owned rows before stopping agents and deleting work; restore
    inserts those original rows beside subsequent work. Wipe backups remain available permanently."""
    store = ctx.require_store()
    op = str(ctx.nouns.get('op') or 'list')
    name = str(ctx.nouns.get('name') or '').strip()
    if op in ('wipe', 'restore'):
        # Clearing a board belongs to the person.
        if ctx.surface == 'mcp':
            raise Stop('Wipe and restore are person_only. Use the Boards select on the page.',
                       'open the board on the page')
        if 'name' not in ctx.nouns:
            raise Stop('Name the board. An empty name means the first board.',
                       f'metaform map boards op={op} name=<board>')
        return _wipe_restore_board(ctx, op, name)
    if op == 'list':
        with store.tables(write=False) as tx:
            named = [dict(row) for row in tx.rows('boards', by=('created',), limit=0).results]
            settings_rows = list(tx.rows('ticket_settings', limit=0).results)
        on = {str(row['work_id']): str(row['board'] or '') for row in settings_rows}
        records = store.work(limit=0).results
        counts: dict[str, int] = {}
        columns: dict[str, dict[str, int]] = {}
        for record in records:
            board = on.get(record.id, '')
            held_columns = columns.setdefault(board, dict.fromkeys(('backlog', 'todo', 'doing', 'done'), 0))
            held_columns[record.column] += 1
            if record.done is None:
                counts[board] = counts.get(board, 0) + 1
        active = str(ctx.setting('board') or '')  # the active board, marked so the page and the person see it
        listed: list[dict[str, Any]] = [{'name': '', 'first': True, 'open': counts.get('', 0),
                                        'line': ctx.setting('board_line'), 'active': active == ''},
                           *({'name': str(row['name']), 'first': False, 'open': counts.get(str(row['name']), 0),
                              'line': row.get('line'), 'created': row['created'], 'active': active == str(row['name'])}
                             for row in named)]
        for row in listed:
            row['columns'] = columns.get(str(row['name']), dict.fromkeys(('backlog', 'todo', 'doing', 'done'), 0))
            row['tickets'] = sum(row['columns'].values())
        current_base = store.bound_base()
        current = current_base.id if current_base else None
        return {'boards': listed, 'wipes': [one for one in home.wipe_backups(store.project_id)
                                          if one['base'] == current]}
    if op not in ('add', 'line', 'remove'):
        raise Stop(f'No op {op!r}: list, add, line, remove, wipe or restore.', 'metaform help map boards')
    if op == 'line':
        _board(store, name)
        line = str(ctx.nouns.get('line') or '').strip()
        # An empty cutoff resets visibility. Repeating a cutoff retries tickets whose commits arrived later.
        if 'line' not in ctx.nouns:
            line = home.now()
        if line:
            try:
                cutoff = datetime.fromisoformat(line)
                if cutoff.tzinfo is None:
                    raise ValueError('The cutoff needs a timezone.')
                line = cutoff.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
            except ValueError:
                raise Stop('The archive cutoff must be an ISO timestamp with a timezone.',
                           'metaform map boards op=line') from None
            ticket_history.read(store.project_id)  # Read Git before taking the store's write lock.
        with store.atomic(), store.tables() as tx:
            held = tx.get('boards', {'name': name}) if name else None
            was = held.get('line') if held else ctx.setting('board_line')
            result: dict[str, Any] = _shed(store, name, line) if line else {
                'removed': [], 'kept': []}
            if name:
                tx.update('boards', {'name': name}, {'line': line})
        if not name:
            settings.put('board_line', line, ctx.folder)
        return {'board': name, 'state': 'archived', 'line': line, 'was': was, **result}
    if not name:
        raise Stop('Name the board.', f'metaform map boards op={op} name=<name>')
    with store.tables() as tx:
        held = tx.get('boards', {'name': name})
        if op == 'add':
            if held is not None:
                raise Stop(f'There is a board named {name!r} already.', 'metaform map boards')
            tx.insert('boards', {'name': name, 'created': home.now(), 'line': None})
            return {'board': name, 'state': 'added'}
        if held is None:
            raise Stop(f'There is no board named {name!r}.', 'metaform map boards')
        if tx.rows('ticket_settings', {'board': name}, limit=1).results:
            raise Stop(f'Tickets are still on the board {name!r}: move them first with map work op=edit id= board=.',
                       f'metaform map work board="{name}"')
        tx.delete('boards', {'name': name})
    if str(ctx.setting('board') or '') == name:  # the active board removed: the first board is active again
        settings.put('board', '', ctx.folder)
    return {'board': name, 'state': 'removed'}


def _wipe_restore_board(ctx: Context, op: str, name: str) -> dict[str, Any]:
    from metaform.data import on_base, project_work_rows, restore_project_work_rows
    store = ctx.require_store()
    if op == 'restore':
        stamp = str(ctx.nouns.get('backup') or '')
        snapshot = home.read_wipe_backup(store.project_id, stamp)
        if snapshot['name'] != name:
            raise Stop('The backup names another board.', 'metaform list backups')
        bound = store.bound_base()
        if (bound.id if bound else None) != snapshot['base']:
            raise Stop('This backup belongs to another map.', 'metaform map bases')
        existing = {one.id for one in store.work(ids=snapshot['work_ids'], limit=0).results}
        restoring = [one for one in snapshot['work_ids'] if one not in existing]
        # Retained history inserts first. A failure leaves all ticket rows untouched and can be retried.
        restore_project_work_rows(store.project_id, snapshot.get('project_rows', []), restoring)
        with store.atomic():
            result = store.restore_board_rows(snapshot)
        return {'board': name, 'backup': stamp, 'state': 'restored', **result}
    _numbering(store)
    with home.halted(store.project_id, 'wipe'):
        snapshot = store.board_snapshot(name)
        snapshot['project_rows'] = project_work_rows(store.project_id, snapshot['work_ids'])
        stamp = home.wipe_backup(store.project_id, snapshot)
        stopped: list[str] = []
        stopping = next(((owner, service) for owner, service in provided(ctx.folder, 'work.stop')
                         if owner == 'dispatch'), None)
        entries = [*snapshot['rows'], *(entry for project in snapshot['project_rows'] for entry in project['rows'])]
        sessions = {str(row['session_id']): row for entry in entries if entry['module'] == 'dispatch'
                    for row in entry['rows'] if row.get('state') == 'running' and row.get('session_id')}
        if sessions and stopping is None:
            raise Stop('Running sessions need dispatch to stop them. The backup is kept.', 'metaform enable dispatch')
        if stopping is not None:
            owner, service = stopping
            with on_base(snapshot['base']):
                child = dataclasses.replace(ctx, module=owner,
                                            store=Store(store.project_id, base=snapshot['base'], module=owner))
                stopped = service(child, snapshot['work_ids'])
        with store.atomic():
            store.wipe_board_rows(snapshot)
        if name and str(ctx.setting('board') or '') == name:
            settings.put('board', '', ctx.folder)
    return {'board': name, 'backup': stamp, 'state': 'wiped', 'tickets': len(snapshot['work_ids']),
            'columns': snapshot['columns'], 'sessions_stopped': stopped}


def _keep(store: Store, work_id: str, nouns: dict[str, Any], notices: list[Notice],
          ctx: Context | None = None) -> None:
    """Write a ticket's settings, when given, in the map module's own tables, STORE-045."""
    nouns = runtime_values(nouns)
    changes: dict[str, Any] = {}
    runtime_fields = ('agent', 'model', 'effort', 'fast')
    if ctx is not None and any(field in nouns for field in runtime_fields):
        runtime = provided(ctx.folder, 'ticket.runtime.edit')
        if runtime:
            edited = cast(dict[str, Any], runtime[0][1](ctx, work_id, nouns))
            notices.extend(Notice(str(one['where']), str(one['message']))
                           for one in cast(list[dict[str, str]], edited.get('notices') or []))
        else:
            changes.update({field: nouns[field] for field in runtime_fields if field in nouns})
            changes['decision'] = {'decider': ctx.identity.get('METAFORM_TASK') or
                                   ctx.identity.get('METAFORM_SESSION') or ctx.surface,
                                   'reason': 'Runtime selected on the ticket.'}
    if 'agent' in nouns:
        agent = nouns['agent'] or None
        if agent is not None and agent not in TICKET_AGENTS:
            notices.append(Notice('agent', f'{agent!r} is not one of the agents, {", ".join(TICKET_AGENTS)}; it was '
                                           'stored as given.'))
        changes['agent'] = agent
    if 'hold' in nouns:
        store.set_work_hold(work_id, hold=bool(nouns['hold']), hold_reason=nouns.get('hold_reason'))
    if 'epic' in nouns:
        changes['epic'] = _epic(store, work_id, nouns['epic'])
    if 'board' in nouns:
        # Empty is an explicit first-board choice. NULL remains distinguishable for legacy generated tickets.
        changes['board'] = _board(store, nouns['board']) or ''
    if 'agents' in nouns:  # how many agents work on it at once; one, the default, is kept as none
        agents = nouns['agents']
        if isinstance(agents, bool) or not isinstance(agents, int) or agents < 1:
            raise Stop(f'A ticket\'s agents is how many agents work on it at once, a whole number from 1; {agents!r} '
                       'is not one.', 'metaform map work op=edit id=<id> agents=2')
        changes['agents'] = agents if agents > 1 else None
    if not changes and 'eligible' not in nouns and 'after_work' not in nouns:
        return
    with store.tables() as tx:
        if changes and tx.update('ticket_settings', {'work_id': work_id}, changes) is None:
            tx.insert('ticket_settings', {'work_id': work_id, **changes})
        if 'eligible' in nouns:
            agents = nouns['eligible']
            if agents == []:
                tx.delete('eligible', {'work_id': work_id})
            else:
                if not isinstance(agents, list) or any(name not in AGENT_TYPES for name in cast(list[Any], agents)):
                    notices.append(Notice('eligible', f'{agents!r} is not a list of agent types, '
                                          f'{", ".join(AGENT_TYPES)}; it was stored as given.'))
                values: dict[str, Any] = {'agents': agents}
                if tx.update('eligible', {'work_id': work_id}, values) is None:
                    tx.insert('eligible', {'work_id': work_id, **values})
        if 'after_work' in nouns:  # the tickets it waits on, read by the agent starter, UX review round 1 (F6)
            waits = nouns['after_work']
            if waits in ([], None, ''):
                tx.delete('after', {'work_id': work_id})
            else:
                if not isinstance(waits, list) or any(not isinstance(one, str) for one in cast(list[Any], waits)):
                    notices.append(Notice('after_work', f'{waits!r} is not a list of work ids; it was not stored.'))
                    return
                if work_id in waits:
                    notices.append(Notice('after_work', 'A ticket does not wait on itself; its own id was left out.'))
                kept = sorted({str(one) for one in cast(list[str], waits)} - {work_id})
                if tx.update('after', {'work_id': work_id}, {'works': kept}) is None:
                    tx.insert('after', {'work_id': work_id, 'works': kept})


class TicketRuntime:
    """Public access to the ticket's runtime, beside its agent and glyph."""

    @staticmethod
    def store(ctx: Context) -> Store:
        store = ctx.require_store()
        if store.module == 'map':
            return store
        bound = store.bound_base()
        return Store(store.project_id, base=bound.id if bound else None, module='map')

    def read(self, ctx: Context, work_id: str) -> dict[str, Any]:
        store = self.store(ctx)
        with store.tables(write=False) as tx:
            row = tx.get('ticket_settings', {'work_id': work_id})
            eligible = tx.get('eligible', {'work_id': work_id})
        return {**({field: row.get(field) for field in ('agent', 'model', 'effort', 'fast', 'decision')} if row else {}),
                **({'eligible': eligible['agents']} if eligible else {})}

    def save(self, ctx: Context, work_id: str, values: dict[str, Any]) -> dict[str, Any]:
        store = self.store(ctx)
        changes = runtime_values({field: values[field] for field in ('agent', 'model', 'effort', 'fast', 'decision')
                                  if field in values})
        if changes:
            with store.tables() as tx:
                tx.concern(work_id=work_id, kind='ticket')
                if tx.update('ticket_settings', {'work_id': work_id}, changes) is None:
                    tx.insert('ticket_settings', {'work_id': work_id, **changes})
        return self.read(ctx, work_id)


TICKET_RUNTIME = TicketRuntime()


def _epic(store: Store, work_id: str, given: Any) -> str | None:
    """The epic a ticket is put in, as `epic` takes it: true makes the ticket an epic itself, kept as its own id, so no
    agent starter takes it before its children are written; a work id or `<address>#<n>` makes it that epic's child;
    '', false or none takes it out. One level only: an epic is no child, and a child is no epic."""
    if given in (None, '', False, 'false'):
        return None
    if given in (True, 'true'):
        return work_id
    epic = _work_id(store, str(given))
    if epic == work_id:
        return work_id
    store.ticket(epic)  # a ticket that does not exist is refused by the store, with its own words
    with store.tables(write=False) as tx:
        held = tx.get('ticket_settings', {'work_id': epic})
        children = tx.rows('ticket_settings', {'epic': work_id}, limit=0).results
    if held is not None and held['epic'] and held['epic'] != epic:
        raise Stop(f'{given} is itself a child of epic {held["epic"]}; an epic holds tickets, not other epics.',
                   f'metaform map work op=edit id={work_id} epic={held["epic"]}')
    if any(row['work_id'] != work_id for row in children):
        raise Stop(f'Ticket {work_id} is an epic with tickets of its own, so it cannot be put in another epic.',
                   'metaform map work op=edit id=<child> epic=<another epic>')
    return epic


def _glyphed(store: Store, result: Any) -> Any:
    """A work operation's record, or page of records, with what the map module keeps on each under `map`: its glyph,
    its preferred agent and whether the person holds it, as work_read shows it in `map work id=<id>`, BASE-035; a record
    with none of these is returned as it is."""
    page = cast(Page[WorkRecord], result) if isinstance(result, Page) else None
    records = list(page.results) if page is not None else [cast(WorkRecord, result)]
    ids = [record.id for record in records]
    glyphs, settings, numbers = _glyphs(store, ids), _settings(store, ids), _work_numbers(store, ids)
    if not glyphs and not settings and not numbers:
        return page if page is not None else records[0]

    def one(record: WorkRecord) -> Any:
        kept = {**({'glyph': glyphs[record.id]} if record.id in glyphs else {}),
                **settings.get(record.id, {}), **numbers.get(record.id, {})}
        if not kept:
            return record
        data = record.to_dict()
        data.setdefault('map', kept)
        return data
    if page is not None:
        return {**page.to_dict(), 'results': [one(record) for record in records]}
    return one(records[0])


def _distribute(store: Store, agents: Any) -> Page[WorkRecord]:
    """Distribute the work over N agents, VIEW-040: the first N glyphs, given in turn to the tickets that start by
    themselves, in To do, not held for the person and waiting on no open ticket, in board order. A held ticket keeps
    no glyph from it: a dealing is no decision about each held ticket, and a glyph agent took them all after its own
    (UX review round 2, held-and-signals). A ticket taken or done keeps its glyph, so an agent at work never changes
    character; an exclude record is no ticket."""
    if isinstance(agents, bool) or not isinstance(agents, int) or not 1 <= agents <= len(AGENT_GLYPHS):
        raise Stop(f'Work is distributed over 1 to {len(AGENT_GLYPHS)} agents, one glyph each; {agents!r} is not one of '
                   'those.', 'metaform map work op=distribute agents=<n>')
    with store.atomic():
        opened = store.work(open=True, limit=0).results
        open_ids = {record.id for record in opened}
        candidates = [record for record in opened if not record.taken and not record.held and (record.task or '').strip()]
        kept = _settings(store, [record.id for record in candidates])

        def waits(record: WorkRecord) -> bool:
            own = kept.get(record.id, {})
            after: Any = own.get('after_work')
            return bool(own.get('hold')) or isinstance(after, list) and any(
                str(one) in open_ids for one in cast(list[Any], after))
        waiting = [record for record in candidates if not waits(record)]
        # the board's order: by its place, a ticket with none after, then as written
        waiting.sort(key=lambda record: (record.position is None, record.position or 0))
        _assign(store, {record.id: AGENT_GLYPHS[place % agents] for place, record in enumerate(waiting)})
    return Page(tuple(waiting), None)


def _work_numbers(store: Store, work_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Each numbered ticket's `item`, `<address>#<n>`, its title and, once resolved, its why, MCP-037."""
    found = store.numbers_of('work', work_ids)
    return {work_id: {'item': item, 'title': title, **({'why': why} if why else {})}
            for work_id, (item, title, why) in found.items()}


def work_read(ctx: Context, record: WorkRecord) -> dict[str, Any] | None:
    """The agent glyph the map module keeps on a work record, VIEW-040, and its number, title and why at its address,
    MCP-037; nothing when it keeps none. The chassis puts it under `map` in `map work id=<id>`, BASE-035."""
    if ctx.store is None:
        return None
    glyph = _glyphs(ctx.store, [record.id]).get(record.id)
    kept = {**({'glyph': glyph} if glyph else {}), **_settings(ctx.store, [record.id]).get(record.id, {}),
            **_work_numbers(ctx.store, [record.id]).get(record.id, {})}
    return kept or None


def _work_id(store: Store, given: str) -> str:
    """A ticket's id as `map work` takes it: its own id, or its handle `<address>#<n>`, as `map where` and the board
    show it, read as the ticket numbered there, MCP-037."""
    from metaform.data import parse_reference
    parsed = parse_reference(given) if '#' in given else None
    if parsed is None:
        return given
    _numbering(store)
    found = store.item_at(*parsed)
    if found is None or found.get('kind') != 'work':
        raise Stop(f'{given} is no ticket: ' + ('it holds no item.' if found is None else f'it is a {found["kind"]}.'),
                   f'metaform map work node={parsed[0]}')
    return str(found['id'])


@ticket_history.per_call
def map_item_read(ctx: Context, address: str, number: int) -> dict[str, Any] | None:
    """The work record, question, message, code link or glossary term numbered `number` at `address`, MCP-037: its
    kind, title, why, body and links; None when map holds none there."""
    if ctx.store is None:
        return None
    _numbering(ctx.store)
    stored = ctx.store.item_at(address, number) or term_read(ctx.store, address, number)
    if stored is not None:
        return stored
    committed = ticket_history.resolve(ctx.store.project_id, f'{address}#{number:x}')
    return {**committed, 'kind': 'commit', 'id': committed['hash'], 'title': committed['subject'],
            'text': committed['body'], 'address': address, 'number': number} if committed else None


def map_items_at(ctx: Context, address: str, before: int | None, limit: int) -> list[dict[str, Any]]:
    """The work records, questions, messages, code links and glossary terms numbered at `address` below `before`,
    newest first, at most `limit`, MCP-037: each one's number, kind, title and why, in one read of each."""
    if ctx.store is None:
        return []
    _numbering(ctx.store)
    merged = [*ctx.store.listed_items(address, before, limit), *terms_at(ctx.store, address, before, limit)]
    return sorted(merged, key=lambda one: -int(one['number']))[:limit]


def item(ctx: Context) -> Any:
    """One item at an address by its number, `<address>#<n>`, as `metaform://<address>#<n>` serves it, MCP-037: the
    memory, ticket, question or message any module numbered there, with its title, why, body and links."""
    from metaform.data import parse_reference
    given = str(ctx.nouns['item']).strip()
    if '#' not in given:  # an address alone: its latest number, with that item when it is still there
        latest = latest_item(ctx.folder, given, project=ctx.project)
        if latest is None:
            raise Stop(f'Nothing is numbered at {given}.', f'metaform map where {given}')
        return item_read(ctx.folder, given, latest['number'], project=ctx.project) or {
            **latest, 'notices': [{'where': 'item', 'message': f"{latest['item']} was deleted; its number is not "
                                                               'reused.'}]}
    parsed = parse_reference(given)
    if parsed is None:
        raise Stop(f'{given!r} is not an item: an item is <address>#<n>, its number in hex.',
                   'metaform map item code.manager.route#1')
    found = item_read(ctx.folder, *parsed, project=ctx.project)
    if found is None:
        latest = _store(ctx).latest_number(parsed[0])
        raise Stop(f'{given} holds no item: ' + (f'the numbers there run to #{latest:x}, and this one was never taken '
                                                  'or its item was deleted.' if latest else 'nothing is numbered there.'),
                   f'metaform map where {parsed[0]}')
    return found


WORK_NOUNS = (
    _noun('op', 'list, the default; add; edit, which, when you stop with your ticket open, sets its note to what is '
                'true now and where; take, which says an agent has started on the task; plan, which says how many '
                'meaningful stages you plan when a count helps coordination or continuation; step records a '
                'completed stage, what you did and any choice with its reason; move, which puts it in a column of the board; distribute, '
                'which gives the open tickets the glyphs of N agents; glyphs, which reads the available agent glyph '
                'names; sources reads retained exact request revisions separately from task interpretation; '
                'done, which closes it with its resolution and why once the work is complete; or remove, which '
                'deletes it for good with its steps, links and settings; unhold_all releases all open work '
                'across this project, preserving boards and prerequisites.',
          schema={'type': 'string', 'enum': ['list', 'add', 'edit', 'take', 'plan', 'step', 'move', 'distribute',
                                             'glyphs', 'sources', 'done', 'remove', 'unhold_all']}),
    _noun('steps', 'take and plan: optional stage count when useful for the task. Update it when that plan changes.', 'int'),
    _noun('said', 'step: what you did in the step you finished, in a sentence, with any choice you made and its why.'),
    _noun('node', 'list, add and edit: an element, by address; edit moves the ticket there, keeping its progress. '
                  'list gives its own records and those on the joins it receives or provides.'),
    _noun('receiver', 'list, add and edit: a join, by the address of the element that holds it, with provider.'),
    _noun('provider', 'list, add and edit: a join, by the address of an element it holds, with receiver.'),
    _noun('address', 'list, add and edit: an element, by address.'),
    _noun('condition', 'add, edit, and list as a filter: the state of the part the record is at, never the kind of '
                       'ticket. missing is intended functionality that is absent, a finding. A stage, unbuilt, under-construction or built, says where the part is on its way to '
                       'existing; built is the normal state and marks nothing. broken is a built part that does not '
                       'do its job. A task on a part that exists and works carries none. Record the state supported '
                       'by the work and its evidence. condition=none on edit clears it.',
          schema={'type': 'string', 'enum': [*CONDITIONS, 'none']}),
    _noun('kind', 'add, edit, and list as a filter: what sort of work the ticket is, never the state of the part: '
                  'broken, a fix for a part that does not do its job; flawed, a part that works but is not right; '
                  'enhancement, a part that works and could be better; or none for a plain task. kind=none on edit '
                  'clears it.',
          schema={'type': 'string', 'enum': ['broken', 'flawed', 'enhancement', 'none']}),
    _noun('links', 'add and edit: other nodes the task links for reference, a list of element addresses, and of '
                   'objects of receiver and provider, with address for a part inside, each naming a purpose.',
          'json', {'type': 'array', 'items': {'anyOf': [
              {'type': 'string'},
              {'type': 'object', 'properties': {'receiver': {'type': 'string'}, 'provider': {'type': 'string'},
                                                'address': {'type': 'string'}}}]}}),
    _noun('by', 'take and move: who takes it; on the CLI, take identifies the claiming agent by its first word, '
                'claude, codex or antigravity. Over MCP the client name identifies the agent.'),
    _noun('column', 'move: backlog, todo, doing or done. todo puts a taken task back on the queue, keeping its log.',
          schema={'type': 'string', 'enum': ['backlog', 'todo', 'doing', 'done']}),
    _noun('position', 'move: its place in the column, from 0; the end when left out.', 'int'),
    _noun('note', 'add and edit: what and where.'),
    _noun('task', 'add and edit: the current execution description, separate from exact source wording.'),
    _noun('source', 'add and edit: original source words and their reference or exact spans, retained separately '
                    'from the task interpretation. Authorship comes from the caller.', 'json',
          {'type': 'object', 'properties': {'text': {'type': 'string'}, 'reference': {'type': 'string'},
                                           'spans': {'type': 'array', 'items': {'type': 'object'}}}}),
    _noun('source_id', 'sources: one retained source id; omitted reads every retained revision.'),
    _noun('held', 'add and edit: put it in Backlog, where it waits: no agent starter starts it, Full Auto, Start '
                  'all, Distribute and an agent\'s glyph among them; release it to To do or start it '
                  'on its own. Holds are explicit choices. Reason-based unholding requires no person approval.', 'bool'),
    _noun('hold_reason', 'add, edit and move: fresh nonblank reason required for hold=true, held=true or '
                         'movement into Backlog. Explain why work waits, whether release is unsafe, and why. '
                         'Retained after release in ticket history.',
          schema={'type': 'string'}),
    _noun('hold_preview', 'unhold_all: optional reviewed ticket snapshot; concurrently changed holds stay held.',
          'json', {'type': 'array', 'items': {'type': 'object'}}),
    _noun('reviewed', 'add and edit: it has been checked for correctness before being fired off.', 'bool'),
    _noun('agent', 'add and edit: the agent this ticket prefers, claude, codex or antigravity; the person can change it '
                   'at any time, even while an agent works on it.',
          schema={'type': 'string', 'enum': ['claude', 'codex', 'antigravity']}),
    _noun('model', 'add and edit: the model this ticket uses, from dispatch options; none clears it. '
                   'The person can change it before the start.'),
    _noun('effort', 'add and edit: the thinking level this ticket uses, from dispatch options; none clears it. '
                    'The person can change it before the start.'),
    _noun('fast', 'add and edit: Fast mode, true or false; none inherits the project setting. Person only.'),
    _noun('hold', 'add and edit: true holds the ticket, hidden from agents and automatic starts until '
                  'explicitly released; list: true lists held tickets too.', 'bool'),
    _noun('glyph', 'edit: the agent glyph the ticket is assigned to; tickets with the same glyph are one agent\'s, '
                   'done one at a time.'),
    _noun('eligible', 'add and edit: the eligible agent types as a JSON list, claude, codex or antigravity; [] allows '
                     'Any agent, the default for existing and new tickets. Dispatch and agent claims honor it.', 'json',
          {'type': 'array', 'items': {'type': 'string', 'enum': ['claude', 'codex', 'antigravity']}}),
    _noun('after_work', 'add and edit: the work ids this ticket waits on, as a JSON list; no agent starts it '
                        'automatically until each of them is done. [] waits on none.', 'json',
          {'type': 'array', 'items': {'type': 'string'}}),
    _noun('agents', 'distribute: how many agents, from 1 to 17; the tickets that start by themselves, in To do, not '
                    'held, not waiting on another, are given the first that many glyphs in turn, in board order. '
                    'add and edit: how many agents work on this ticket at once, 1 by default; Full Auto starts up to '
                    'that many in its one worktree, each told of the others. On an epic, how many work on its '
                    'tickets at once.',
          'int'),
    _noun('epic', 'add and edit: true makes this ticket an epic, one request the person made: no agent works it '
                  'itself, it closes once every ticket in it is done, and those tickets share its worktree and branch, '
                  'so they are reviewed and merged together. A work id or <address>#<n> puts this ticket in that '
                  'epic; \'\' takes it out.'),
    _noun('board', 'add and edit: the named board the ticket is on, as map boards lists them; \'\' puts it back on '
                   'the project\'s first board. list: only the tickets on that board, \'\' for the first board.'),
    _noun('id', 'The work record id, for edit, take, plan, step, move and done. Given with no op, it reads that one '
                'ticket with the where read of its node and of each node it links: their refs, open work and open '
                'questions, knowledge layers and modules\' memories. '
                'past_work lists completed tickets with their age; read one with id= to see its log.'),
    _noun('resolution', 'done: how it was resolved, kept beside the record.'),
    _noun('title', 'add, required, and edit: one short line saying what the ticket is. The ticket takes the next '
                   'number at its node, shown as <address>#<n>.'),
    _noun('why', 'done, required: one short line saying why it was resolved this way.'),
    _noun('open', 'list: true, the default, for records not done; false for those done. A listed record leaves out '
                  'its task, said and resolution; read them with id=.', 'bool'),
    *PAGING,
)

RAW = ('raw',)
# ask and tell take node first; these beside it name the purpose it holds, MAP-005.
HELD = (_noun('provider', 'A purpose node holds as its receiver: the address of the element that serves it.'),
        _noun('address', 'With provider: the part at that address inside the purpose.'))


def challenged(folder: Path) -> bool:
    """Whether the folder's project holds a blind-spot layer, so the verbs that read and answer its challenges are
    listed over MCP, MCP-004."""
    project = project_for(folder)
    return project is not None and any(layer.name.startswith('blind_spot_')
                                       for layer in Store(project).layers(limit=0).results)


def reexamining(folder: Path) -> bool:
    """Whether a layer of the folder's project is marked for re-examination, so the verb that clears the mark is
    listed over MCP, MCP-004."""
    project = project_for(folder)
    return project is not None and any(layer.reexamine for layer in Store(project).layers(limit=0).results)


MODULE = Module(
    id='map',
    # The kanban lines speak to nodes, which exist once an intake is finished, MAP-048 and MCP-029.
    # The tasks instruction is read on demand with map's full instructions, not handed to every agent at connect.
    status=lambda ctx: Status(instruction=prompt_files.module('map', 'tasks') if ctx.setting('tasks') and ctx.store
                              is not None and ctx.store.has_intake() else None, at_connect=False),
    tables=TABLES,
    data=DATA,
    work_read=work_read,
    item_read=map_item_read,
    items_at=map_items_at,
    item_kinds=('work', 'question', 'message', 'term'),
    provides=(Provides('base.holds', base_holds), Provides('ticket.runtime', TICKET_RUNTIME),
              Provides('agent.tool.instructions', tool_instructions)),
    resources=(Resource('metaform://map/construction', 'Map construction guidance',
                        'Read before map construction: operation-specific Canonical Intake grammar and layer boundaries.',
                        'guide'),),
    summary="Read and write this project's functional map and its layers.",
    purpose="Reads and writes this project's functional map. Handed an address, start with where: one read of "
            'the address returns the element, what relies on it, every join it provides with its receiver and '
            'purpose, what it relies on, every join it receives with its providers and purpose, and, once per '
            'session, how much is held at it and around it, memories, open work, messages, layer items, with the '
            'call that reads each; contents=true returns what is held there in full, full=true keeps ids too. With '
            "no address, start with roots: the map's entry, the CQU and the DE with their joins, and the root "
            'elements. The receiver holds the purpose, the provider delivers the function. '
            # A draft, CTX-029, awaiting the owner's approval: memory for what happened, knowledge for what is true.
            'Record what happened in the work at a node with the memory tools, and what is now known to be true '
            'of the project with knowledge, naming the layer on every call: create it, add, edit and remove its '
            'objects one at a time, and finish it when the task is done. Details: metaform help map.',
    details='Every read that returns a join shows the layer it comes from. --raw reads every stored layer.',
    verbs=(
        Verb('guide', guide, 'Read the current map-construction guide before changing base structure or a knowledge layer.',
             effect='read', needs_project=False),
        Verb('roots', roots, "Read the map's entry: the CQU and the DE with their joins, and every root element.",
             nouns=PAGING, switches=RAW, effect='read', reads_layers=True),
        Verb('where', where, 'Read one address on the map: its element, what relies on it, and what it relies on, each '
                             'with its purpose. How much is held at it and around it is counted, with the calls that '
                             "read it; with an empty address, the map's entry.",
             nouns=(Noun('address', 'A dotted namespace address, or empty for the entry; <scope>@<layer> reads '
                                    'what that layer holds there, such as code.timer.kitchen@code.'),
                    _noun('contents', 'true returns what the layers, memories and modules hold at it in full; '
                                      'by default each is counted, with the call that reads it.', 'bool'),
                    _noun('full', 'true keeps ids and empty fields, which are left out by default, with the '
                                  'contents.', 'bool')),
             switches=RAW, effect='read', reads_layers=True),
        Verb('markdown', markdown, 'The map, or the part around one address, as a short Markdown document.',
             nouns=(_noun('address', 'A dotted namespace address; without one, the whole map.'),
                    _noun('file', 'A file to write the document to; without one, it is printed.')),
             switches=RAW, surfaces=('cli',)),
        Verb('mermaid', mermaid, 'The map, or one element and those one join away, as a Mermaid flowchart.',
             nouns=(_noun('address', 'A dotted namespace address; without one, the whole map.'),
                    _noun('direction', 'TB, top to bottom, the default, or LR, left to right.'),
                    _noun('leave_out', 'Roots whose elements are not drawn, comma-separated, such as '
                                       'upstream,downstream.'),
                    _noun('labels', 'What each edge says: none, the default; purpose, its join\'s purpose; or ef, '
                                    'its encounter function.'),
                    _noun('file', 'A file to write the flowchart to, such as map.mmd; without one, it is printed.')),
             switches=RAW, surfaces=('cli',)),
        Verb('xml', xml, 'The map, or one element and all it receives, as an XML document with every field.',
             nouns=(_noun('address', 'A dotted namespace address; without one, the whole map.'),
                    _noun('file', 'A file to write the document to; without one, it is printed.')),
             switches=RAW, surfaces=('cli',)),
        Verb('element', element, 'Read one element: its address, name_length, name, role and short name.',
             nouns=(Noun('element', 'An address or element id.'),), switches=RAW, effect='read', reads_layers=True),
        Verb('joins', joins, 'List the joins an element receives, or with as=provider the joins it provides for.',
             nouns=(Noun('element', 'An address or element id.'), _noun('as', 'receiver or provider.'), *PAGING),
             switches=RAW, effect='read', reads_layers=True),
        Verb('identity', identity, 'List every join an element provides for: the receiver, its OP, and the EF that '
                                   'serves it.',
             nouns=(Noun('element', 'An address or element id.'), *PAGING), switches=RAW, effect='read',
             reads_layers=True),
        Verb('children', children, 'List the artifact types one segment toward the leaves from an address.',
             nouns=(Noun('address', 'A dotted namespace address.'), *PAGING), effect='read', reads_layers=True),
        Verb('layers', layers, 'List the layers with their kind, tags and state, and whether each is on here.',
             nouns=(_noun('tag', 'Only layers with this tag.'), _noun('kind', 'Only layers of this kind.'),
                    _noun('module', 'Only layers of this module.'), *PAGING), effect='read'),
        Verb('tag', tag, 'Tag a layer, so it can be named by the tag wherever layers are named.',
             nouns=(Noun('layer', 'A layer.'), Noun('tag', 'The tag.'))),
        Verb('untag', untag, 'Remove a tag from a layer.', nouns=(Noun('layer', 'A layer.'), Noun('tag', 'The tag.'))),
        Verb('layer', layer, 'Read everything one layer holds, or what it holds at one node.',
             nouns=(Noun('layer', 'A layer.'), _noun('node', 'A node, such as element:code.engine.'), *PAGING),
             effect='read', reads_layers=True),
        Verb('node', node, "Read every layer's items at one node, grouped by layer.",
             nouns=(Noun('node', 'element:<address or id> or join:<id>.'),),
             switches=RAW, effect='read', reads_layers=True),
        Verb('context', context, 'Read the properties that apply at an address, and those attached toward the leaves '
                                 'that are visible there.',
             nouns=(Noun('address', 'A dotted namespace address.'), *PAGING), effect='read', reads_layers=True),
        Verb('links', links, 'List the layer items that link to a node.',
             nouns=(Noun('node', 'A node.'), _noun('layer', 'Only this layer.'), *PAGING), switches=RAW, effect='read',
             reads_layers=True),
        Verb('citing', citing, 'Find everything on the map whose refs hold a key and value, such as a file path.',
             nouns=(Noun('key', 'The ref key, such as path.'), Noun('value', 'The ref value.'), *PAGING), effect='read',
             reads_layers=True),
        Verb('history', history, 'Read every version of a thing on the map by its id, from the row that added it '
                                 'through each refinement.',
             nouns=(Noun('id', 'An id.'), *PAGING), effect='read'),
        Verb('bases', bases, "List the project's bases, the maps it keeps, and which one is active.",
             nouns=(_noun('project', 'A project id.'), *PAGING), effect='read'),
        Verb('add-base', add_base, 'Start a new, empty base for the project and make it the active map.',
             nouns=(Noun('name', 'The base name.'), _noun('project', 'A project id.')),
             caution=BASE_SWITCH, person_says=True, cautioned=_switch_caution, page='the base picker'),
        Verb('activate', activate, "Make one of the project's bases the active map.",
             nouns=(Noun('name', 'The base name.'), _noun('project', 'A project id.')),
             caution=BASE_SWITCH, person_says=True, cautioned=_activate_caution, page='the base picker'),
        Verb('remove-base', remove_base, 'Take one base out of the project; a copy of its store is kept.',
             nouns=(Noun('name', 'The base name.'), _noun('project', 'A project id.')),
             caution='Removes the base and its store; a copy is kept under backups/remove-base. The active base '
                     'is refused.', effect='remove', person_says=True, cautioned=_remove_caution,
             page='the base picker'),
        Verb('collapse', collapse, 'Rewrite the current map as a new base of one base layer and make it active; the '
                                   'old one is kept whole. Each element and join is written once, with the same ids.',
             nouns=(Noun('name', 'The new base name.'), _noun('project', 'A project id.')),
             caution=BASE_SWITCH, person_says=True, cautioned=_switch_caution),
        Verb('promote', promote, 'Give a join an element of its own at an address, keeping the join and its history, '
                                 'memories and work.',
             nouns=(_noun('receiver', 'The address of the element that holds the join.'),
                    _noun('provider', 'The address of an element the join holds.'),
                    _noun('address', 'The address of the element to create or reuse for the join.'),
                    _noun('name', 'The canonical name of the new element; an existing element keeps its name.'),
                    _noun('name_length', 'How many trailing address segments form its short name.', 'int'),
                    _noun('role', 'The intake classification of the new element: CQU, DE, SE or NE.'),
                    _noun('reason', 'Why the join needs an element.')),
             details='The join records its element by address and keeps its receiver and held elements. The '
                     'associated element receives and provides ordinary joins. An intake purpose gains a version '
                     'in its own layer; a knowledge join follows its existing edit rules. Repeating the same '
                     'association adds no version. An existing element keeps its authored fields; a different '
                     'address for an already promoted join returns a notice and writes nothing.'),
        Verb('cypher', cypher, 'Ask the map a question in Cypher: a read-only query over the graph of the layers in '
                               'view or named.',
             nouns=(_noun('layers', 'The layers to see, by name, comma separated; left out, the layers turned on.'),
                    Noun('query', 'The Cypher query: MATCH, WHERE, RETURN, ORDER BY, LIMIT; strings in double quotes.',
                         many=True)),
             details='The graph: nodes have a kind, element, join, item or property, and their fields. An element '
                     'has address, name, name_length, role and layer_id. A join has purpose, ef, ifd, receiver and '
                     'type. An item has value, target_kind, target_id and layer_id. Edges have a kind: join runs from '
                     'a receiver element to each element its join holds and carries the join\'s id, purpose, ef and '
                     'ifd; receives runs from a receiver to its join node; holds runs from a join node to each element '
                     'it holds; attached runs from an element or join to an item; property runs from an element to a '
                     'property. Match an edge by its kind in WHERE, and quote strings with double quotes. Results '
                     'come back by column. The query sees what the layers in view show, hidden layers and masks '
                     'applied, as every read does; layers=<names> picks the layers for this query alone.',
             examples=(('metaform map cypher MATCH \'(e) WHERE e.kind = "element" AND e.role = "DE" RETURN e.address, e.name\'',
                        'The defining elements.'),
                       (('metaform map cypher \'MATCH (r)-[j]->(e) WHERE r.address = "code.store" AND j.kind = "join" '
                         'RETURN e.address, j.purpose\''), 'What the store relies on, with the purpose of each join.')),
             effect='read', reads_layers=True),
        Verb('search', search, 'Find the layer items whose value holds every word of the text.',
             nouns=(Noun('text', 'The words to find.'), _noun('layer', 'Only this layer.'), *PAGING), effect='read',
             reads_layers=True),
        Verb('find', find, 'Find where the map holds something, from words for it: the elements, joins and layer items '
                           'that hold them, each by its Address, best first.',
             nouns=(Noun('text', 'The words to find; a hit holds at least half of them.'),
                    _noun('limit', 'How many hits, 20 by default.', 'int')),
             details='Elements are matched by address, name, short name and note; joins by purpose and EF, at their '
                     'receiver; layer items by value, at the node they are attached to. Each word matches a whole word '
                     'or the start of one. Only what the layers in view show is found.',
             examples=(('metaform map find cents', 'Where the map holds anything about cents.'),),
             effect='read', reads_layers=True),
        Verb('work', work, 'Work with tickets on map elements and joins: list, read, add, edit, take, finish and remove. '
                           'Use the supplied ticket and exact operative source; summaries do not replace that source. '
                           'Read id= and its source references when required details are missing or changed. '
                           'Use op=plan and op=step for meaningful stages when '
                           'decomposition, coordination or continuation benefits; update the count when that plan '
                           'changes. A direct change can proceed to op=done with its exact resolution and why. Record '
                           'material progress, decisions with reasons and blockers; when stopping with work open, '
                           'op=edit its note to say what is true now and where. A ticket never changes the map.',
             nouns=WORK_NOUNS,
             details='A work record is attached to one element or join and never changes the map. Its '
                     'condition is the state of that part, never the kind of ticket: most tasks carry none. A '
                     'stage, unbuilt, under-construction or built, says where the part is on its way to existing; '
                     'built marks nothing. broken is a built part that does not do its job. A no-task unbuilt or '
                     'under-construction record is non-work state, visible at its node and never started. '
                     'Its note says what and where, its task what it needs. Executable work stays open until '
                     'op=done records its resolution, which is kept beside it.',
             person_details='exclude records material outside the intake scope or code conflicting with a '
                            'superseding specification. The note links the affected material and the specification or '
                            'scope reason for review. Unrelated folders are excluded from functional capture; a '
                            'proposed gitignore change is recorded for review. Documents, specifications, notes and '
                            'working files are preserved. Marking a record does not remove files or change gitignore. '
                            'Unneeded legacy migration code is marked for review. A store at an earlier layout is '
                            'updated by Metaform when it opens it. The person writes one, and so do the agents that '
                            'serve them, the system agent, a talk, the sentinel and the intake. A ticket needs a task, '
                            'what its agent works from; a trouble, broken or missing marker starts from its note. '
                            'Ticket creation never adds a hold because of source, role or review status. Use an '
                            'explicit hold with its reason when work must wait. Reason-based unholding requires no '
                            'person approval.',
             examples=((('metaform map work op=add node=element:code.alarm.audible condition=unbuilt '
                         'title="Build the alarm" task="build it"'),
                        'Record that the alarm is not built yet, with the task that builds it.'),
                       ('metaform map work op=edit id=<work id> node=code.alarm.audible',
                        'Move a ticket to the alarm, keeping its progress and reference links.'),
                       ('metaform map work condition=broken open=true', 'List the parts recorded broken, with their open tasks.'),
                       ('metaform map work id=<work id>', ('Read one ticket with its node, how much is held there, '
                                                           'and the nodes it links.')),
),
             ),
        Verb('boards', boards, 'The project\'s named boards: list them with their open tickets, add one, archive a '
                               'board\'s done tickets, remove an empty board, wipe with an automatic backup, or '
                               'restore a wipe. Wipe and restore are person_only. The first board has no name. '
                               'A ticket is moved to a board with map work op=edit id=<id> board=<name>.',
             nouns=(Noun('op', 'list, the default; add; line, which puts every ticket done up to now on the board in '
                               'Git history when their commits retain their citations; remove; wipe; or restore.',
                               required=False),
                    Noun('name', 'The board\'s name. Empty names the first board for line, wipe and restore.',
                         required=False),
                    Noun('backup', 'restore: the wipe backup stamp from metaform list backups.', required=False),
                    Noun('line', 'line: the archive cutoff as an ISO timestamp, instead of now; a prior cutoff '
                                 'changes visibility without restoring shed records.', required=False))),
        Verb('ask', ask, 'Write a question at a node, for the record: the person asks, never an agent.',
             nouns=(Noun('node', 'Where the question applies: an element, by address; with provider, the purpose '
                                 'it holds as receiver.'),
                    Noun('question', 'The question.'),
                    *HELD,
                    _noun('suggestions', 'Possible answers, as a JSON list.', 'json',
                          {'type': 'array', 'items': {'type': 'string'}}),
                    _noun('by', 'Who asks.'),
                    _noun('work', 'The ticket it belongs to, by its work id.'),
                    _noun('title', 'Required: one short line saying what the question is. It takes the next number at '
                                   'the node, shown as <address>#<n>.'),
                    _noun('why', 'Required: one short line saying why it is asked.')),
             surfaces=('cli',)),
        Verb('reply', reply, 'Answer a question at a node, or mark a message read.',
             nouns=(Noun('id', 'The id of the question or the message.'),
                    _noun('answer', 'The answer to a question.')),
             examples=(('metaform map reply <id> answer="No, make it louder"', 'Answer a question.'),)),
        Verb('reopen', reopen, 'Reopen a question answered by mistake, so it waits again with its suggestions.',
             nouns=(Noun('id', 'The id of the question.'),),
             examples=(('metaform map reopen <id>', 'Clear the answer; the question waits again.'),),
             surfaces=('cli',)),
        Verb('messages', messages, 'List the questions and messages left for the person at nodes, or move one to '
                                   'another node.',
             nouns=(_noun('op', 'list, the default, oldest first; move changes one record\'s node, keeping its answer '
                               'and closed state.', schema={'type': 'string', 'enum': ['list', 'move']}),
                    _noun('id', 'move: the id of the question or message.'),
                    _noun('node', 'list: only those at this node. move: the destination element, by address; with '
                                 'provider, the purpose it holds as receiver.'),
                    *HELD, _noun('kind', 'list: question or message.'),
                    _noun('open', 'list: true for those that still wait, false for those answered or read.', 'bool'),
                    *PAGING),
             examples=(('metaform map messages op=move id=<message id> node=code.alarm.audible',
                        'Move a question or message to the alarm, keeping its suggestions and answer.'),)),
        Verb('item', item, 'One item at an address by its number, <address>#<n>: its title, why, body and links.',
             nouns=(Noun('item', 'The item, <address>#<n>, its number in hex as it is shown, such as '
                                 'code.manager.route#1f; upper case is read as well. An address alone reads the '
                                 'latest item numbered there.'),),
             examples=(('metaform map item code.manager.route#1', 'Read the first item numbered at the route manager.'),),
             effect='read', reads_layers=True),
        Verb('knowledge', knowledge, 'Build a knowledge layer, a CEL on top of the map that agents use to index and '
                                     'understand the AUE. Create it, add, edit and remove its objects one at a time, '
                                     'and finish it. Read metaform://map/construction before constructing or extending its content.',
             nouns=KNOWLEDGE_NOUNS,
             details='Every call names its layer with layer=. op=create makes the layer; the add, edit and remove '
                     'operations change one object each; op=finish marks it ready. link-context attaches content to an element and its descendants. Mark inherited items with extra.instruction=true; extra.applies_to narrows them to named descendants. Ordinary evidence stays local. Knowledge is genre, medium, '
                     'practice and the like. Valid, established functional construction follows the intake grammar '
                     'through map refine, which records its reason, evidence and author. Proposals and unresolved '
                     'design remain in an explicitly named CEL constrained to its declared question or variable.',
             examples=((('metaform map knowledge op=create layer=practices-cpp variable="C++ practice here." '
                         'mutable=true hideable=true'), 'Start a knowledge layer.'),), effect='remove'),
        Verb('refine', refine, 'Refine the map in use: add, change, rename or remove one of its elements or joins as a '
                               'new version, keeping every earlier one. Read metaform://map/construction before construction; '
                               'record only functionality satisfying its base grammar.',
             nouns=REFINE_NOUNS,
             details='The change is written in the base\'s own layer, never in a new one, LAYER-025; history '
                     'shows every version with its reason, evidence and author. An address the base lacks, given '
                     'with name, name_length or role, is added as the intake records an element; a receiver with '
                     'elements no join of it holds, with purpose, ef and ifd, is added as the intake records a '
                     'purpose record. to_address renames an element, or merges it into the one there, and its '
                     'joins, knowledge, tickets and memories go with it; adopt takes an element or join a knowledge '
                     'layer holds into the base. A project with a map is refined, never mapped again in a new intake.',
             examples=((('metaform map refine receiver=code.timer.kitchen provider=code.clock.tick '
                         'purpose="Know when each dish is done." reason="the old purpose named the clock"'),
                        'Refine one join\'s purpose, the join named by its receiver and an element it holds.'),
                       (('metaform map refine address=code.alarm.snooze name="snooze" name_length=2 role=SE '
                         'reason="built in ticket code.timer.kitchen#3" evidence=src/alarm/snooze.py'),
                        'Add a built feature\'s element to the map.'),
                       (('metaform map refine receiver=code.timer.kitchen elements=\'["code.alarm.snooze"]\' '
                         'purpose="Ring again later." ef="Delays the alarm." ifd=sends reason="built"'),
                        'Add the purpose record the new element serves.'),
                       ('metaform map refine address=code.timer.egg to_address=code.timer.kitchen reason="one timer"',
                        'Merge an element into another, carrying everything at it.'))),
        Verb('select', select, 'Turn a layer on at an address and at every address toward the leaves from it.',
             nouns=(Noun('address', 'An address.'), Noun('layer', 'A layer.'))),
        Verb('mask', mask, 'Stop a layer reaching an address and every address toward the leaves from it.',
             nouns=(Noun('address', 'An address.'), Noun('layer', 'A layer.'))),
        Verb('clear', clear, 'Remove a select or mask set at an address.',
             nouns=(Noun('address', 'An address.'), Noun('layer', 'A layer.'), Noun('kind', 'select or mask.'))),
        Verb('hide', hide, 'Hide a layer from every read in context.', nouns=(Noun('layer', 'A layer.'),),
             caution='This hides the layer, and every layer built from it, from every agent.'),
        Verb('unhide', unhide, 'Show a hidden layer again.', nouns=(Noun('layer', 'A layer.'),)),
        Verb('reexamined', reexamined, "Clear a layer's re-examination mark once its knowledge has been checked "
                                       'against the changed base.',
             nouns=(Noun('layer', 'A layer.'),), listed=reexamining),
        Verb('answer', answer, 'Answer a blind-spot challenge the critic raised: A, B or C.',
             nouns=(Noun('challenge', 'The challenge item id.'), Noun('answer', 'A, B or C.'),
                    _noun('link', 'For C: the element or join that already handles it.')), listed=challenged),
        Verb('approve', approve, 'Approve a challenge answered B, making it a plan.',
             nouns=(Noun('challenge', 'The challenge item id.'),), surfaces=('cli',)),
        Verb('critic', critic, 'Start a blind-spot critic run: a new blind-spot layer, and the critic prompt with the '
                               'whole base.',
             switches=('critic',),
             details='Fast mode by default: the critic reads the base and the specifications, not the code. '
                     '--critic also lets it read the code and write tickets. Each run creates its own blind-spot '
                     'layer, with provenance role critic and blinded true unless --critic, LAYER-014.'),
        Verb('challenges', challenges, 'Read the answer prompt with each challenge of a blind-spot layer and its '
                                       'state.',
             nouns=(Noun('layer', 'The blind-spot layer.'),), effect='read', listed=challenged),
        *GLOSSARY_VERBS,
    ),
    # The map's tools on the web GUI's toolbar. The brief and what the agent sees are what an agent reads, drawn by
    # the page from the MCP server's own reads: the node's brief with what is numbered there, and everything an agent
    # connecting here receives, counted, so the person sees what the agent sees and what it costs.
    toolbar=(
        ToolbarItem('brief', 'Node brief', 'Read the brief an agent at the selected node is handed, and the '
                    'memories, messages and work numbered there.', icon='brief', pane='brief', order=20,
                    shortcut='Alt+B'),
        ToolbarItem('agent-view', 'What the agent sees', 'See everything an agent connecting here receives, '
                    'read from the MCP server, and how much of its context that takes.', icon='eye',
                    pane='agent-view', order=30, shortcut='Alt+A'),
        ToolbarItem('layers', 'Layers', 'Choose the layers of knowledge shown on the map, and apply them to the '
                    'folder agents read.', icon='layers', page='layers', order=40, shortcut='Alt+L'),
        ToolbarItem('board', 'Board', "Prioritize the project's tickets and see which agent holds each.",
                    icon='board', pane='board', order=50, shortcut='Alt+K'),
        ToolbarItem('add-task', 'Add task', 'Write a ticket on the selected node, for an agent to take.', icon='pen',
                    page='add-task', selection='address', group='write', order=60),
        ToolbarItem('add-element', 'Add element', 'Add a part the map lacks by hand, for an agent to validate.',
                    icon='box', page='add-element', group='write', order=61),
        ToolbarItem('export-mermaid', 'Export Mermaid', 'Save the map as a Mermaid flowchart, to draw it in docs '
                    'and reviews.', icon='download', page='export-mermaid', group='export', placement='extra',
                    order=120),
        ToolbarItem('copy-mermaid', 'Copy as Mermaid', 'Copy the map as Mermaid, to paste into a document or a '
                    'chat.', icon='copy', page='copy-mermaid', group='export', placement='extra', order=121),
    ),
    # The node panel's tabs and the board. Each is read or typed into, so each starts on the right or in the main
    # area, never on the left beside the maps.
    panes=(
        Pane('object', 'Object', 'Read the selected node: its purpose, its joins, its work and its questions.',
             icon='file', page='object', area='right', group='node', visible=True, order=10, min_width=320),
        Pane('provenance', 'Provenance', 'See who recorded the selected node, when, from which prompt and layer.',
             icon='archive', page='provenance', area='right', group='node', visible=True, order=20, min_width=320),
        Pane('brief', 'Brief', 'Read the brief an agent at the selected node is handed, and the memories, messages '
             'and work numbered there.', icon='brief', page='brief', selection='address', area='right',
             group='node', visible=True, order=15, min_width=320),
        Pane('agent-view', 'What the agent sees', 'See everything an agent connecting here receives, read from the '
             'MCP server, and how much of its context that takes.', icon='eye', page='agent-view',
             selection='address', area='float', min_width=560, min_height=420),
        Pane('messages', 'Messages', 'Answer the questions agents left for you at nodes, oldest first.', icon='send',
             page='messages', area='right', group='chat', order=110, min_width=320),
        Pane('board', 'Board', "Prioritize the project's tickets and see which agent holds each.", icon='board',
             page='board', area='float', order=20, min_width=640, min_height=320),
        *GLOSSARY_PANES,
    ),
)
