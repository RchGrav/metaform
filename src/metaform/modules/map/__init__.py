"""map: the data access object's map and layer operations as verbs, BASE-038.

Every verb calls `ctx.require_store()` and exactly one operation of STORE-024
or STORE-025, and returns its result, BASE-036. The fields of a record being
written are nouns: required ones positional, optional ones `name=value`. The
only switch is `--raw`, which reads every stored layer instead of the layers
in context. `knowledge` is the one read-write verb for layers, LAYER-018.
"""
from __future__ import annotations

import dataclasses
import json
import os
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any, TypeVar, cast

from metaform import prompt_files, settings
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
    plain,
)
from metaform.finish_xml import xml as map_xml
from metaform.module import (
    Context,
    Module,
    Noun,
    NounKind,
    Pane,
    Provides,
    Status,
    Stop,
    ToolbarItem,
    Verb,
    held_role,
    item_read,
    latest_item,
    node_reads,
    titled,
    work_reads,
)
from metaform.outline import markdown as map_markdown
from metaform.outline import mermaid as map_mermaid
from metaform.outline import mermaid_limits

from .around import told
from .code import VERBS as CODE_VERBS
from .code import brief as code_brief
from .code import node_line as code_node_line
from .code import scoped as code_scoped
from .code import start_line as code_start_line
from .code_preparation import inventory as code_inventory
from .glossary import PANES as GLOSSARY_PANES
from .glossary import VERBS as GLOSSARY_VERBS
from .glossary import item_read as term_read
from .glossary import items_at as terms_at
from .scoped import is_scoped
from .scoped import resolve as resolve_scoped
from .storage import DATA, TABLES

SOURCES = 'sources'  # the layer an element's refs go in, naming the code that realizes a part, STORE-025

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False
REMOTE_AGENT = True  # reading and writing the map is the work a remote agent does
DATA_SOURCE = 'storage.py'

settings.boolean('raw', False, help='Read every stored layer, building, hidden and masked ones included.')
settings.boolean('critic', False, help='map critic: the critic also reads the code and writes tickets; '
                 'fast mode, blind to the code, when off.')
settings.boolean('tasks', True, help='Assign and track work on the map like a kanban. Turn it off when the project '
                 'keeps its own board.')
settings.number('node_summary_bytes', 2048, min=512,
                help='The bytes an agent is given about the node it works on, in map where, a ticket read and the '
                     'hand-off. What does not fit, code paths first, is counted with the call that reads it.')

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


def _other_project(ctx: Context) -> Store:
    project = ctx.nouns.get('project')
    return Store(project) if project else _store(ctx)


PAGING = (Noun('limit', 'How many results, 0 for all.', kind='int', required=False),
          Noun('after', 'The cursor the previous page returned.', required=False))


def roots(ctx: Context) -> Any:
    """The map's entry: the CQU and the DE with their joins, and every root element, STORE-025; while the code is not
    read into its layer, the call that reads it."""
    found = _store(ctx).roots(**_reading(ctx), **_paging(ctx))
    line = None if ctx.nouns.get('after') else code_start_line(ctx)
    return found if line is None else {**found.to_dict(), 'code': line}


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
    data['at'] = _oriented(ctx, found.at, Node.of(found.work.node_kind, found.work.node_id))
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
            calls: bool = False) -> dict[str, Any]:
    """A compact read of a node with the counts told, kept within `budget` bytes, MCP-039. What an agent needs most
    stays: the node itself and the purposes it serves, then its neighbours with their counts, then the counts at the
    node, then the code paths. So the code paths go first, those on the joins it receives, then on the joins it
    provides for, then the node's own; then the joins it receives, and the joins it provides for after the first, last
    first; and only then is the tree drawn smaller, by `told`. Code paths that fit again in the room a join left come back.
    Each kind left out is said in `more` as a count with the call that reads it, so nothing is lost, only not sent;
    with `calls`, each call as this surface names it."""
    provides = [dict(one) for one in cast(list[dict[str, Any]], data.get('provides') or [])]
    receives = [dict(one) for one in cast(list[dict[str, Any]], data.get('receives') or [])]
    join = dict(cast(dict[str, Any], data.get('join') or {}))
    own = list(cast(list[str], data.get('sources') or []))
    element = cast(dict[str, Any], data.get('element') or {})
    address = element.get('address') if data.get('kind') == 'element' else None
    left: list[str] = []
    taken: list[tuple[dict[str, Any] | None, list[str]]] = []  # the code paths taken off, from where, in order
    cut = {'provides': 0, 'receives': 0}

    def drawn(calls: bool = False) -> dict[str, Any]:
        shown = {*own, *join.get('sources', ()),
                 *(ref for one in (*provides, *receives) for ref in one.get('sources', ()))}
        unshown = len([ref for ref in dict.fromkeys(left) if ref not in shown])
        sources = (f'metaform map where address={address} contents=true' if address else
                   f'metaform map node node=join:{found.join.id}' if found.join is not None else '')
        more = [line for line in (
            _prompt('summary_sources', count=str(unshown), read=sources) if unshown and sources else '',
            _prompt('summary_provides', count=str(cut['provides']),
                    read=f'metaform map joins element={address} as=provider') if cut['provides'] else '',
            _prompt('summary_receives', count=str(cut['receives']),
                    read=f'metaform map joins element={address}') if cut['receives'] else '') if line]
        kept: dict[str, Any] = {}
        for key, value in data.items():
            value = {'sources': own, 'join': join, 'provides': provides, 'receives': receives}.get(key, value)
            if value:
                kept[key] = value
        if more:
            kept['more'] = [ctx.calls(line) for line in more] if calls else more
        return {**kept, **said}

    def steps() -> Any:
        for one in (*reversed(receives), *reversed(provides), join):
            if one.get('sources'):
                taken.append((one, one['sources']))
                left.extend(one.pop('sources'))
                yield
        if own:
            taken.append((None, list(own)))
            left.extend(own)
            own.clear()
            yield
        while receives and address:
            receives.pop()
            cut['receives'] += 1
            yield
        while len(provides) > 1 and address:
            provides.pop()
            cut['provides'] += 1
            yield

    if _size(drawn()) > budget:
        for _ in steps():
            if _size(drawn()) <= budget:
                break
        # Code paths taken off before a join went may fit again in the room it left: the node's own first.
        for one, refs in reversed(taken):
            if one is not None and not any(one is held for held in (*provides, *receives, join)):
                continue
            (own if one is None else one.setdefault('sources', [])).extend(refs)
            if _size(drawn()) > budget:
                del (own if one is None else one['sources'])[-len(refs):]
                if one is not None:
                    one.pop('sources')
    return drawn(calls=calls)


def _oriented(ctx: Context, found: Any, node: Node, *, contents: bool = False) -> Any:
    """A node's read for an agent: the element and its joins with the counts at it and around it, once per session,
    MCP-039, within the node_summary_bytes setting; with `contents`, or with full, everything held at it as well, as
    `map node` reads it, whatever its size."""
    if found is None:
        return None
    if contents or found.full:
        data = cast(dict[str, Any], plain(_with_modules(ctx, found, node)))
        code_line = code_brief(ctx, found)  # the code layer counted, its links read with the call it names
        return {**data, **({'code': code_line} if code_line else {}), **told(ctx, found)}
    data = _compact(cast(dict[str, Any], found.to_dict()))
    code_line = code_brief(ctx, found)  # the code layer's one line: its counts here and the call that reads them
    if code_line:
        data['code'] = code_line
    budget = int(ctx.setting('node_summary_bytes'))
    said = told(ctx, found, lambda part: _size(_fitted(ctx, found, data, part, budget)) <= budget)
    return _fitted(ctx, found, data, said, budget, calls=True)


def where(ctx: Context) -> Any:
    """One read of an address: what relies on it and what it relies on, with the counts at it and around it,
    STORE-025 and MCP-039; the entry with no address. `<scope>@<layer>` reads what that layer holds at the scope, P165,
    `scoped.py`."""
    if not ctx.nouns['address']:
        return roots(ctx)
    address = ctx.nouns['address']
    if is_scoped(str(address)):
        return scoped_read(ctx, str(address))
    found = _store(ctx).where(address, full=bool(ctx.nouns.get('full', False)), **_reading(ctx))
    if found is None:
        raise Stop(f'No element {address} in context here.', f'metaform map children {address}')
    return _oriented(ctx, found, Node('element', address), contents=bool(ctx.nouns.get('contents', False)))


def scoped_read(ctx: Context, text: str) -> Any:
    """What a layer holds at a scope, `<scope>@<layer>`, P165: the scope's element as the map gives it, its name and
    role, and what the layer holds there; for the code layer, the code at the Address, or at the join named
    `<receiver>:<provider>`, as code-context reads it, each symbol with the Address it is the code of. A layer's items
    are read in context, so a mask at the address leaves them out as every read does."""
    store = _store(ctx)
    found = resolve_scoped(store, text)
    read: dict[str, Any] = {'scope': found.text, 'layer': found.layer}
    if found.address is not None:
        element = store.element(found.address)
        if element is not None:
            read['element'] = {key: value for key, value in (
                ('address', element.address), ('name', element.name), ('short_name', element.short_name),
                ('role', element.role), ('reading', element.reading)) if value}
    if found.layer == str(ctx.setting('code_layer') or 'code'):
        if found.address is None:
            raise Stop(f'The code layer is read at an Address: {found.text} names the whole project.',
                       'metaform map code-gaps')
        return {**read, **code_scoped(ctx, found.address, found.provider)}
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
    target = _node(ctx.nouns['node'])
    found = _store(ctx).node(target, **_reading(ctx))
    if found is None:
        raise Stop(f'No node {ctx.nouns["node"]} in context here.', 'metaform map node <node> --raw')
    read = _with_modules(ctx, found, target)
    code_line = code_node_line(ctx, target)  # the code layer's links are counted, not listed: read with the call named
    if not code_line:
        return read
    data = cast(dict[str, Any], read if isinstance(read, dict) else read.to_dict())
    return {**data, 'code': code_line}


def context(ctx: Context) -> Any:
    return _store(ctx).context(ctx.nouns['address'], **_paging(ctx))


def links(ctx: Context) -> Any:
    return _store(ctx).links_to(_node(ctx.nouns['node']), ctx.nouns.get('layer'), **_reading(ctx), **_paging(ctx))


def citing(ctx: Context) -> Any:
    return _store(ctx).citing(ctx.nouns['key'], ctx.nouns['value'], **_paging(ctx))


def history(ctx: Context) -> Any:
    return _store(ctx).history(ctx.nouns['id'], **_paging(ctx))


def bases(ctx: Context) -> Any:
    return _other_project(ctx).bases(**_paging(ctx))


def add_base(ctx: Context) -> Any:
    return _other_project(ctx).add_base(ctx.nouns['name'])


def collapse(ctx: Context) -> Any:
    return _other_project(ctx).collapse(ctx.nouns['name'])


def activate(ctx: Context) -> Any:
    return _other_project(ctx).activate_base(ctx.nouns['name'])


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
REFINE_FIELDS = ('name', 'name_length', 'role', 'purpose', 'ef', 'ifd', 'elements')
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


def refine(ctx: Context) -> Any:
    """Refine the base: one element or join changed or removed as its newest version in the base's own
    layer, every earlier version kept, LAYER-025. It names what it changes by address, never by id: an element by its
    address, a join by its receiver and an element it holds, MAP-005; `elements` gives the elements a join holds. It
    is a verb of its own, apart from knowledge, because it changes the base and no knowledge layer. Nothing is
    refused for its content, BASE-044."""
    nouns = ctx.nouns
    if not any(name in nouns for name in NAMING):
        raise Stop('refine needs address, or receiver and provider, to name what it changes.',
                   'metaform help map refine')
    store = _store(ctx)
    notices: list[Notice] = []
    (reason,) = _empty(ctx, notices, 'reason')
    changes: dict[str, Any] = {name: nouns[name] for name in REFINE_FIELDS if name in nouns}
    thing: str | None = None
    if 'receiver' in nouns or 'provider' in nouns:
        said = f"the purpose of {nouns.get('receiver')} served by {nouns.get('provider')}"
        held = _one(_purposes(store, nouns.get('receiver'), nouns.get('provider')), said, notices, purposes=True)
        if held is not None:
            thing = held.id
            if 'to_receiver' in nouns:
                changes['receiver'] = nouns['to_receiver']
    else:
        element = store.element(str(nouns['address']), raw=True)
        if element is None:
            notices.append(Notice('address', f"{nouns['address']} is not an element of the base; nothing was "
                                             'changed.'))
        else:
            thing = element.id
            if 'to_address' in nouns:
                changes['address'] = nouns['to_address']
    named = {name: nouns[name] for name in NAMING if name in nouns}
    if thing is None:
        return {**named, 'notices': [notice.to_dict() for notice in notices]}
    made = store.refine(thing, changes, remove=bool(nouns.get('remove')), reason=reason,
                        evidence=nouns.get('evidence'))
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
    if op == 'add-property':
        (value,) = _empty(ctx, notices, 'value')
        return store.add_property(name, _element(nouns['element']), value, **_optional(ctx, 'refs', 'extra'))
    if op == 'add-item' and ctx.nouns.get('task'):
        _may_write_ticket(ctx)
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
    """The refs given with an element, as its one item of the sources layer, replacing what that item held: the
    metaform holds no refs, so they live in a sources layer."""
    store.layer(SOURCES, 'intake', 'refs', kind='layer', mutable=True, hideable=True, ready=True)
    held = [item for item in store.layer_items(SOURCES, Node('element', element_id), limit=0).results
            if isinstance(item, Item)]
    if held:
        notices.extend(getattr(store.edit(held[0].id, {'refs': refs}), 'notices', ()))
    else:
        notices.extend(getattr(store.add_item(SOURCES, Node('element', element_id), address, refs=refs), 'notices', ()))
    notices.append(Notice('refs', f'The refs were written to the {SOURCES} layer at {address}; the base holds none.'))


def _noun(name: str, help: str, kind: NounKind = 'str', schema: dict[str, Any] | None = None) -> Noun:
    return Noun(name, help, kind=kind, required=False, schema=schema)


KNOWLEDGE_NOUNS = (
    _noun('op', 'create, add-element, add-join, add-property, add-item, add-ref, add-plan, edit, remove, finish or '
                'discard.',
          schema={'type': 'string', 'enum': ['create', 'add-element', 'add-join', 'add-property', 'add-item', 'add-ref',
                                             'add-plan', 'edit', 'remove', 'finish', 'discard']}),
    _noun('layer', 'The layer this call works on, by name or id. Name a new layer <scope>@<content>: the address it is '
                   'about, @, then a short adjective_noun you choose for what the prompt creates; base is the default '
                   'scope. base@best_practices holds the best practices of the whole project; code.cpp@best_practices '
                   'those of cpp code. Read in reverse with @ as "for": best practices for cpp code. A workflow layer is '
                   'named the same way. An object added without a layer goes to a new layer named unnamed-<time>.'),
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
    'elements': 'The elements the join holds, a JSON list of addresses; they replace the ones it held.',
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
    _noun('to_address', 'An element cannot be moved: given for an element, it is not applied.'),
    *(_refined_noun(noun) for noun in KNOWLEDGE_NOUNS if noun.name in REFINE_FIELDS),
)

# The nouns each work operation reads, besides op.
WORK_READS: dict[str, frozenset[str]] = {
    'glyphs': frozenset(),
    'list': frozenset({'node', 'receiver', 'provider', 'address', 'condition', 'kind', 'open', 'limit', 'after',
                       'hold'}),
    'read': frozenset({'id'}),
    'add': frozenset({'node', 'receiver', 'provider', 'address', 'condition', 'kind', 'note', 'task', 'held', 'reviewed',
                      'links', 'agent', 'hold', 'eligible', 'title'}),
    'edit': frozenset({'id', 'node', 'receiver', 'provider', 'address', 'condition', 'kind', 'note', 'task', 'held',
                       'reviewed', 'glyph', 'links', 'agent', 'hold', 'eligible', 'title'}),
    'done': frozenset({'id', 'resolution', 'why'}),
    'take': frozenset({'id', 'steps', 'by'}),
    'move': frozenset({'id', 'column', 'position', 'by'}),
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
TICKET_AGENTS = ('claude', 'codex', 'gemini')  # the agents a ticket can prefer, as dispatch starts them
AGENT_TYPES = TICKET_AGENTS

# The map module's own tables, STORE-045: `glyphs` keeps the agent glyph each ticket is assigned to, keyed by the work
# id, beside the map as the work records are, so the chassis work table holds no glyph, BASE-046 and ticket 90430bba.
# The field each work operation cannot store its record without, BASE-038: the object it attaches to, or the record.
WORK_NEEDS: dict[str, tuple[str, ...]] = {'list': (), 'glyphs': (), 'read': ('id',), 'add': (), 'edit': ('id',), 'done': ('id',),
                                          'take': ('id',), 'plan': ('id', 'steps'), 'step': ('id',),
                                          'move': ('id', 'column'), 'distribute': ('agents',)}


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


def work(ctx: Context) -> Any:
    """The work records: the condition of an element or a join, apart from the map, MAP-046 and STORE-042.
    op=list, the default, reads them, and an id with no op reads one; add, edit, take, plan, step, move and done
    write one each, and distribute gives the open tickets the glyphs of N agents, VIEW-040. A ticket is written by
    the person, by the agents that serve them and by a session the person runs outside dispatch; the roles the
    person's `roles_without_authority` names, a worker and a merge preparation by default, write none, MAP-050:
    work is planned before a ticket exists."""
    # An id with no op reads that one ticket with what the map holds at its node and its links, MAP-048.
    op = str(ctx.nouns.get('op', 'read' if 'id' in ctx.nouns else 'list'))
    if op == 'add':
        _may_write_ticket(ctx)
    if op not in WORK_READS or op == 'read' and 'op' in ctx.nouns:
        raise Stop(f'{op!r} is not a work operation: op=list, glyphs, add, edit, take, plan, step, move, distribute or done; '
                   'with id= and '
                   'no op, the one ticket is read.', 'metaform help map work')
    _need(ctx, *WORK_NEEDS[op], verb='work')
    unread = sorted(name for name in ctx.nouns if name != 'op' and name not in WORK_READS[op])
    notices = [Notice(name, f'op={op} does not read {name}; it was ignored.') for name in unread]
    role = held_role(ctx) if op == 'edit' else None
    if role and 'condition' in ctx.nouns:  # the part's state is not a worker's to set
        ctx.nouns.pop('condition')
        notices.append(Notice('condition', f'The state of a part is set by the intake and the person, not by a {role} '
                                           'agent; it was ignored. Say what you found in the note.'))
    if role and 'kind' in ctx.nouns:  # what sort of ticket it is was decided with it
        ctx.nouns.pop('kind')
        notices.append(Notice('kind', f'A ticket\'s kind is set by whoever wrote it, not by a {role} agent; it was '
                                      'ignored. Say what you found in the note.'))
    for name in unread:
        ctx.nouns.pop(name)
    store, nouns = _store(ctx), ctx.nouns
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
        listed = plain(_glyphed(store, found))
        listed['results'] = [{name: value for name, value in row.items() if name not in UNLISTED}
                             for row in listed['results']]
        return _with_notices(listed, notices)
    if op == 'add':
        node = _named(store, nouns, notices)
        if node is None:
            raise Stop('work op=add needs node, or receiver and provider.', 'metaform help map work')
        titled(ctx, 'The ticket', nouns.get('title'))  # it takes the next number at its node, MCP-037
        _numbering(store)
        # A missing condition is stored empty, and the store names it in its notice, STORE-042.
        with store.atomic():
            added = store.add_work(node, nouns.get('condition'),
                                   links=[_link(store, link) for link in nouns.get('links') or ()],
                                   **_optional(ctx, 'kind', 'note', 'task', 'held', 'reviewed', 'title'))
            _keep(store, added.id, nouns, notices)
        return _written(ctx, store, added, 'add', notices)
    if op == 'distribute':
        return _with_notices(_glyphed(store, _distribute(store, nouns['agents'])), notices)
    work_id = nouns['id']
    if op == 'read':
        return _with_notices(_with_work_modules(ctx, store.ticket(work_id)), notices)
    if op == 'take':
        with store.atomic():
            _claim(ctx, store, work_id, nouns.get('by'))
            taken = store.take_work(work_id, nouns.get('steps'), nouns.get('by'))
        return _written(ctx, store, taken, 'take', notices)
    if op == 'move':
        with store.atomic():
            previous = store.ticket(work_id).work.column
            moved = store.move_work(work_id, nouns['column'], nouns.get('position'), nouns.get('by'))
        if previous != 'todo' and moved.column == 'todo':
            ctx.publish('work.requeued', {'project': store.project_id, 'work_id': work_id,
                                         'previous': previous, 'revision': time.time_ns()})
        return _written(ctx, store, moved, 'move', notices)
    if op == 'plan':
        return _written(ctx, store, store.plan_work(work_id, nouns['steps']), 'plan', notices)
    if op == 'step':
        return _written(ctx, store, store.step_work(work_id, nouns.get('said')), 'step', notices)
    if op == 'edit':
        changes = {name: nouns[name] for name in (*WORK_FIELDS, 'title') if name in nouns}
        node = _named(store, nouns, notices)
        if node is not None:
            changes['node'] = node
        if 'links' in nouns:
            changes['links'] = [_link(store, link) for link in nouns['links'] or ()]
        with store.atomic():
            edited = store.edit_work(work_id, changes)
            if 'glyph' in nouns:
                _assign(store, {work_id: _glyph(nouns['glyph'], notices)})
            _keep(store, work_id, nouns, notices)
        return _written(ctx, store, edited, 'edit', notices)
    # A resolution records a decision, so it carries a short why, kept with the ticket's number, MCP-037.
    titled(ctx, 'The resolution', None, nouns.get('why'), why_needed=True, title_needed=False,
           why_step='add why: one line saying why it was resolved this way')
    return _written(ctx, store, store.finish_work(work_id, nouns.get('resolution'), nouns.get('why')), 'done',
                    notices)


def _written(ctx: Context, store: Store, record: WorkRecord, op: str, notices: list[Notice]) -> Any:
    """What a ticket write answers. To an agent over MCP, one line, MCP-037: the ticket's `<address>#<n>` and title
    and what the write did, from the map module's `work_<op>` prompt, then each notice on a line of its own; the
    record is a read away, `map_work id=<id>`, so the agent is not handed back what it just sent. Elsewhere the record
    with what the map keeps on it, as every read gives it."""
    if ctx.surface != 'mcp':
        return _with_notices(_glyphed(store, record), notices)
    numbered = _work_numbers(store, [record.id]).get(record.id, {})
    fills = {'item': str(numbered.get('item') or record.id), 'title': str(numbered.get('title') or ''),
             'id': record.id, 'by': str(record.taken_by or ''), 'column': record.column,
             'done': str(record.steps_done), 'steps': str(record.steps or record.steps_done)}
    line = ' '.join(_prompt(f'work_{op}', **fills).split())
    return '\n'.join([line, *(_prompt('work_notice', where=one.where, message=one.message)
                              for one in (*notices, *record.notices))])


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
    """Each ticket's preferred agent, hold and eligibility, read in one transaction; a ticket with no
    settings is left out."""
    with store.tables(write=False) as tx:
        found = {work_id: tx.get('ticket_settings', {'work_id': work_id}) for work_id in work_ids}
        eligible = {work_id: tx.get('eligible', {'work_id': work_id}) for work_id in work_ids}
    kept = {work_id: {'agent': row['agent'], 'hold': bool(row['hold'])} for work_id, row in found.items()
            if row is not None}
    for work_id, row in eligible.items():
        if row is not None:
            kept.setdefault(work_id, {})['eligible'] = row['agents']
    return kept


def _may_write_ticket(ctx: Context) -> None:
    """A ticket is not written by an agent whose role the person holds back, MAP-050; on the page it always is. A
    worker may open a child of the ticket it holds, BASE-061: the branch waits for `op=add` to read `parent`, so until
    BASE-061 is built no call reaches it."""
    role = held_role(ctx)
    if role is None:
        return
    parent = ctx.nouns.get('parent')
    if 'parent' in WORK_READS['add'] and parent and parent == os.environ.get('METAFORM_WORK'):
        return
    raise Stop(f'A {role} agent writes no ticket: tickets are written by the person and the agents that serve them. '
               'Write what you found in your own ticket\'s note.',
               'metaform map work op=edit id=<your work id> note="..."')


def _claim(ctx: Context, store: Store, work_id: str, by: Any) -> None:
    """A restricted claim uses the transport's client name, or the CLI owner's first word, never the environment, which
    an agent's harness may have mixed with its runner's. Ticket authority does read the runner's role from it,
    `held_role`, since that guards against an agent's mistakes and is no boundary, MAP-050."""
    kept = _settings(store, [work_id]).get(work_id, {})
    if 'eligible' not in kept:
        return
    eligible = kept['eligible']
    if eligible == []:
        return
    agent = None
    if ctx.client is not None:
        agent = next((name for name in AGENT_TYPES if ctx.client.lower().startswith(name)), None)
    elif ctx.surface != 'mcp' and isinstance(by, str):
        words = by.split()
        agent = words[0] if words and words[0] in AGENT_TYPES else None
    if isinstance(eligible, list) and agent is not None and agent in eligible:
        return
    names = ', '.join(str(name) for name in cast(list[Any], eligible)) if isinstance(eligible, list) else str(eligible)
    raise Stop(f'Work {work_id} is restricted to eligible agents: {names}; '
               f'{agent or "an unidentified agent"} cannot claim it.', f'metaform map work id={work_id}')


def _keep(store: Store, work_id: str, nouns: dict[str, Any], notices: list[Notice]) -> None:
    """Write a ticket's settings, when given, in the map module's own tables, STORE-045."""
    changes: dict[str, Any] = {}
    if 'agent' in nouns:
        agent = nouns['agent'] or None
        if agent is not None and agent not in TICKET_AGENTS:
            notices.append(Notice('agent', f'{agent!r} is not one of the agents, {", ".join(TICKET_AGENTS)}; it was '
                                           'stored as given.'))
        changes['agent'] = agent
    if 'hold' in nouns:
        changes['hold'] = 1 if nouns['hold'] else 0
    if not changes and 'eligible' not in nouns:
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
    """Distribute the work over N agents, VIEW-040: the first N glyphs, given in turn to the tickets not done and not
    taken, To do first and then Backlog, each in its board order. A ticket taken or done keeps its glyph, so an agent
    at work never changes character; an exclude record is no ticket."""
    if isinstance(agents, bool) or not isinstance(agents, int) or not 1 <= agents <= len(AGENT_GLYPHS):
        raise Stop(f'Work is distributed over 1 to {len(AGENT_GLYPHS)} agents, one glyph each; {agents!r} is not one of '
                   'those.', 'metaform map work op=distribute agents=<n>')
    with store.atomic():
        waiting = [record for record in store.work(open=True, limit=0).results
                   if not record.taken and (record.task or '').strip()]
        # the board's order: To do before Backlog, each by its place, a ticket with none after, then as written
        waiting.sort(key=lambda record: (record.held, record.position is None, record.position or 0))
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


def map_item_read(ctx: Context, address: str, number: int) -> dict[str, Any] | None:
    """The work record, question, message, code link or glossary term numbered `number` at `address`, MCP-037: its
    kind, title, why, body and links; None when map holds none there."""
    if ctx.store is None:
        return None
    _numbering(ctx.store)
    return ctx.store.item_at(address, number) or term_read(ctx.store, address, number)


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
                'steps you plan, first, and again when the plan changes; step, which says you finished one, with what '
                'you did and any choice you made and why; move, which puts it in a column of the board; distribute, '
                'which gives the open tickets the glyphs of N agents; glyphs, which reads the available agent glyph '
                'names; or done, which closes it with its resolution and why once the work is complete.',
          schema={'type': 'string', 'enum': ['list', 'add', 'edit', 'take', 'plan', 'step', 'move', 'distribute',
                                             'glyphs', 'done']}),
    _noun('steps', 'take and plan: how many steps you plan for the task. Say it again when your plan changes.', 'int'),
    _noun('said', 'step: what you did in the step you finished, in a sentence, with any choice you made and its why.'),
    _noun('node', 'list, add and edit: an element, by address; edit moves the ticket there, keeping its progress. '
                  'list gives its own records and those on the joins it receives or provides.'),
    _noun('receiver', 'list, add and edit: a join, by the address of the element that holds it, with provider.'),
    _noun('provider', 'list, add and edit: a join, by the address of an element it holds, with receiver.'),
    _noun('address', 'list, add and edit: an element, by address.'),
    _noun('condition', 'add, edit, and list as a filter: the state of the part the record is at, never the kind of '
                       'ticket. missing is intended functionality that is absent, a finding. A stage, unbuilt, under-construction or built, says where the part is on its way to '
                       'existing; built is the normal state and marks nothing. broken is a built part that does not '
                       'do its job. A task on a part that exists and works carries none. The intake and the person '
                       'set it; an agent at work leaves it alone. condition=none on edit clears it.',
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
                'claude, codex or gemini. Over MCP the client name identifies the agent.'),
    _noun('column', 'move: backlog, todo, doing or done. todo puts a taken task back on the queue, keeping its log.',
          schema={'type': 'string', 'enum': ['backlog', 'todo', 'doing', 'done']}),
    _noun('position', 'move: its place in the column, from 0; the end when left out.', 'int'),
    _noun('note', 'add and edit: what and where.'),
    _noun('task', 'add and edit: what it needs.'),
    _noun('held', 'add and edit: keep it waiting until agents are assigned or take it.', 'bool'),
    _noun('reviewed', 'add and edit: it has been checked for correctness before being fired off.', 'bool'),
    _noun('agent', 'add and edit: the agent this ticket prefers, claude, codex or gemini; the person can change it at any '
                   'time, even while an agent works on it.', schema={'type': 'string', 'enum': ['claude', 'codex', 'gemini']}),
    _noun('hold', 'add and edit: true holds the ticket, hidden from agents and automatic starts until '
                  'the person lets it go; list: true lists held tickets too.', 'bool'),
    _noun('glyph', 'edit: the agent glyph the ticket is assigned to; tickets with the same glyph are one agent\'s, '
                   'done one at a time.'),
    _noun('eligible', 'add and edit: the eligible agent types as a JSON list, claude, codex or gemini; [] allows '
                     'Any agent, the default for existing and new tickets. Dispatch and agent claims honor it.', 'json',
          {'type': 'array', 'items': {'type': 'string', 'enum': ['claude', 'codex', 'gemini']}}),
    _noun('agents', 'distribute: how many agents, from 1 to 17; the tickets not done and not taken are given the first '
                    'that many glyphs in turn, To do first and then Backlog.', 'int'),
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


MODULE = Module(
    id='map',
    provides=(Provides('code.inventory', code_inventory),),
    # The kanban lines speak to nodes, which exist once an intake is finished, MAP-048 and MCP-029.
    # The tasks instruction is read on demand with map's full instructions, not handed to every agent at connect.
    status=lambda ctx: Status(instruction=prompt_files.module('map', 'tasks') if ctx.setting('tasks') and ctx.store
                              is not None and ctx.store.has_intake() else None, at_connect=False),
    tables=TABLES,
    data=DATA,
    work_read=work_read,
    item_read=map_item_read,
    items_at=map_items_at,
    item_kinds=('work', 'question', 'message', 'code', 'term'),
    summary="Read and write this project's functional map and its layers.",
    purpose="Reads and writes this project's functional map. Handed an address, start with where: one read of "
            'the address returns the element, what relies on it, every join it provides with its receiver and '
            'purpose, what it relies on, every join it receives with its providers and purpose, and, once per '
            'session, how much is held at it and around it, memories, open work, messages, layer items, with the '
            'call that reads each; contents=true returns what is held there in full, full=true keeps ids too. With '
            "no address, start with roots: the map's entry, the CQU and the DE with their joins, and the root "
            'elements. The receiver holds the purpose, the provider delivers the function. '
            'Record what you learn at a node with the memory tools; to build or improve a knowledge layer, use '
            'knowledge, naming the layer on every call: create it, add, edit and remove its objects one at a '
            'time, and finish it when the task is done. Details: metaform help map.',
    details='Every read that returns a join shows the layer it comes from. --raw reads every stored layer.',
    verbs=(
        Verb('roots', roots, "Read the map's entry: the CQU and the DE with their joins, and every root element.",
             nouns=PAGING, switches=RAW, effect='read'),
        Verb('where', where, 'Read one address on the map: its element, what relies on it, and what it relies on, each '
                             'with its purpose. How much is held at it and around it is counted, with the calls that '
                             "read it; with an empty address, the map's entry.",
             nouns=(Noun('address', 'A dotted namespace address, or empty for the entry; <scope>@<layer> reads '
                                    'what that layer holds there, such as code.timer.kitchen@code.'),
                    _noun('contents', 'true returns what the layers, memories and modules hold at it in full; '
                                      'by default each is counted, with the call that reads it.', 'bool'),
                    _noun('full', 'true keeps ids and empty fields, which are left out by default, with the '
                                  'contents.', 'bool')),
             switches=RAW, effect='read'),
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
             nouns=(Noun('element', 'An address or element id.'),), switches=RAW, effect='read'),
        Verb('joins', joins, 'List the joins an element receives, or with as=provider the joins it provides for.',
             nouns=(Noun('element', 'An address or element id.'), _noun('as', 'receiver or provider.'), *PAGING),
             switches=RAW, effect='read'),
        Verb('identity', identity, 'List every join an element provides for: the receiver, its OP, and the EF that '
                                   'serves it.',
             nouns=(Noun('element', 'An address or element id.'), *PAGING), switches=RAW, effect='read'),
        Verb('children', children, 'List the artifact types one segment toward the leaves from an address.',
             nouns=(Noun('address', 'A dotted namespace address.'), *PAGING), effect='read'),
        Verb('layers', layers, 'List the layers with their kind, tags and state, and whether each is on here.',
             nouns=(_noun('tag', 'Only layers with this tag.'), _noun('kind', 'Only layers of this kind.'),
                    _noun('module', 'Only layers of this module.'), *PAGING), effect='read'),
        Verb('tag', tag, 'Tag a layer, so it can be named by the tag wherever layers are named.',
             nouns=(Noun('layer', 'A layer.'), Noun('tag', 'The tag.'))),
        Verb('untag', untag, 'Remove a tag from a layer.', nouns=(Noun('layer', 'A layer.'), Noun('tag', 'The tag.'))),
        Verb('layer', layer, 'Read everything one layer holds, or what it holds at one node.',
             nouns=(Noun('layer', 'A layer.'), _noun('node', 'A node, such as element:code.engine.'), *PAGING), effect='read'),
        Verb('node', node, "Read every layer's items at one node, grouped by layer.",
             nouns=(Noun('node', 'element:<address or id> or join:<id>.'),),
             switches=RAW, effect='read'),
        Verb('context', context, 'Read the properties that apply at an address, and those attached toward the leaves '
                                 'that are visible there.',
             nouns=(Noun('address', 'A dotted namespace address.'), *PAGING), effect='read'),
        Verb('links', links, 'List the layer items that link to a node.',
             nouns=(Noun('node', 'A node.'), _noun('layer', 'Only this layer.'), *PAGING), switches=RAW, effect='read'),
        Verb('citing', citing, 'Find everything on the map whose refs hold a key and value, such as a file path.',
             nouns=(Noun('key', 'The ref key, such as path.'), Noun('value', 'The ref value.'), *PAGING), effect='read'),
        Verb('history', history, 'Read every version of a thing on the map by its id, from the row that added it '
                                 'through each refinement.',
             nouns=(Noun('id', 'An id.'), *PAGING), effect='read'),
        Verb('bases', bases, "List the project's bases, the maps it keeps, and which one is active.",
             nouns=(_noun('project', 'A project id.'), *PAGING), effect='read'),
        Verb('add-base', add_base, 'Start a new, empty base for the project and make it the active map.',
             nouns=(Noun('name', 'The base name.'), _noun('project', 'A project id.'))),
        Verb('activate', activate, "Make one of the project's bases the active map.",
             nouns=(Noun('name', 'The base name.'), _noun('project', 'A project id.'))),
        Verb('remove-base', remove_base, 'Take one base out of the project; a copy of its store is kept.',
             nouns=(Noun('name', 'The base name.'), _noun('project', 'A project id.')),
             caution='Removes the base and its store; a copy is kept under backups/remove-base. The active base '
                     'is refused.', effect='remove'),
        Verb('collapse', collapse, 'Rewrite the current map as a new base of one base layer and make it active; the '
                                   'old one is kept whole. Each element and join is written once, with the same ids.',
             nouns=(Noun('name', 'The new base name.'), _noun('project', 'A project id.'))),
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
                         'RETURN e.address, j.purpose\''), 'What the store relies on, with the purpose of each join.')), effect='read'),
        Verb('search', search, 'Find the layer items whose value holds every word of the text.',
             nouns=(Noun('text', 'The words to find.'), _noun('layer', 'Only this layer.'), *PAGING), effect='read'),
        Verb('work', work, 'Work with tickets, the work records on map elements and joins: list, read, add, edit, take '
                           'and finish them. To work a ticket handed to you: read it with id=; op=plan with the steps '
                           'you plan; op=step as each finishes, saying what you did and any choice you made with its '
                           'why; op=done with a resolution and a why when it is complete; when you stop with it open, '
                           'op=edit its note to say what is true now and where. A ticket never changes the map, and it '
                           'moves across the board as it is worked.',
             nouns=WORK_NOUNS,
             details='A work record is attached to one element or join and never changes the map. Its '
                     'condition is the state of that part, never the kind of ticket: most tasks carry none. A '
                     'stage, unbuilt, under-construction or built, says where the part is on its way to existing; '
                     'built marks nothing. broken is a built part that does not do its job. The intake and the '
                     'person set it; an agent at work leaves it alone. Its note says what and where, its task what '
                     'it needs. '
                     'exclude records material outside the intake scope or code conflicting with a superseding '
                     'specification. The note links the affected material and the specification or scope reason '
                     'for review. Unrelated folders are excluded from functional capture; a proposed gitignore '
                     'change is recorded for review. Documents, specifications, notes and working files are '
                     'preserved. Marking a record does not remove files or change gitignore. Unneeded legacy '
                     'migration code is marked for review. A store at an earlier layout is updated by Metaform '
                     'when it opens it. It is '
                     'open until op=done records its resolution, which is kept beside it. The person writes one, or '
                     'the sentinel and the system agent for them on the command line, held=true until agents take '
                     'it; over the agents\' tool op=add is refused, and an agent at work says what it found in its '
                     'own ticket\'s note.',
             examples=((('metaform map work op=add node=element:code.alarm.audible condition=unbuilt '
                         'title="Build the alarm" task="build it"'),
                        'Record that the alarm is not built yet, with the task that builds it.'),
                       ('metaform map work op=edit id=<work id> node=code.alarm.audible',
                        'Move a ticket to the alarm, keeping its progress and reference links.'),
                       ('metaform map work condition=broken open=true', 'List the parts recorded broken, with their open tasks.'),
                       ('metaform map work id=<work id>', ('Read one ticket with its node, how much is held there, '
                                                           'and the nodes it links.')),
)),
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
             effect='read'),
        Verb('knowledge', knowledge, 'Build a knowledge layer, a CEL on top of the map that agents use to index and '
                                     'understand the AUE. Create it, add, edit and remove its objects one at a time, '
                                     'and finish it.',
             nouns=KNOWLEDGE_NOUNS,
             details='Every call names its layer with layer=. op=create makes the layer; the add, edit and remove '
                     'operations change one object each; op=finish marks it ready. The base grows by the add '
                     'operations with layer=base; it changes by refine.',
             examples=((('metaform map knowledge op=create layer=practices-cpp variable="C++ practice here." '
                         'mutable=true hideable=true'), 'Start a knowledge layer.'),), effect='remove'),
        Verb('refine', refine, 'Refine the base: change or remove one of its elements or joins as a new version, '
                               'keeping every earlier one.',
             nouns=REFINE_NOUNS,
             details='The change is written in the base\'s own layer, never in a new one, LAYER-025; history '
                     'shows every version.',
             examples=((('metaform map refine receiver=code.timer.kitchen provider=code.clock.tick '
                         'purpose="Know when each dish is done." reason="the old purpose named the clock"'),
                        'Refine one join\'s purpose, the join named by its receiver and an element it holds.'),)),
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
             nouns=(Noun('layer', 'A layer.'),)),
        Verb('answer', answer, 'Answer a blind-spot challenge the critic raised: A, B or C.',
             nouns=(Noun('challenge', 'The challenge item id.'), Noun('answer', 'A, B or C.'),
                    _noun('link', 'For C: the element or join that already handles it.'))),
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
             nouns=(Noun('layer', 'The blind-spot layer.'),), effect='read'),
        *CODE_VERBS,
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
        # The code layer at the selected node, `<address>@code`, P165: its symbols, the calls in and out with the
        # Address at the other end, and the code serving it, as code-context reads it.
        Pane('code', 'Code', 'Read the code that serves the selected node, and the Addresses its calls reach.',
             icon='code', verb='code-context', selection='address', area='right', group='node', order=25,
             min_width=320),
        *GLOSSARY_PANES,
    ),
)
