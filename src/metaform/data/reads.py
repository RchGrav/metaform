"""The read operations of STORE-025, each answered from the base's projection inside one read transaction.

Every read in context, the default, resolves the layers that reach each place
through one `Resolver`, so select, mask, hiding and building apply on every
path, STORE-019; `raw=True` reads every stored layer. Lists are paged, and each
page resumes after the last key, STORE-005. Reads never touch SQLite for
structure, STORE-046: the graph in memory answers them.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from ..errors import StoreError
from . import operations, rows, versions, views
from .ids import is_id, prefixes
from .paging import sliced
from .projection import Version
from .records import (
    Citation,
    ContextView,
    Element,
    GraphElement,
    GraphPage,
    Item,
    Join,
    Layer,
    LayerGroup,
    Node,
    NodeView,
    Page,
    Property,
    Provenance,
    RootElement,
    RootEntry,
    Roots,
    Selection,
    Where,
)
from .records import Version as VersionRecord
from .selection import Resolver, all_layers
from .session import Tx

Row = Version
T = Any
PUNCTUATION = '"\',.;:!?()[]{}'  # what a word is read apart from, in a search and in a value


def resolver(tx: Tx, selection: Sequence[str] | None, toggled: Sequence[str]) -> Resolver:
    return Resolver(tx.base, selection, toggled)


def _page(keyed: list[tuple[str, Any]], build: Callable[[Any], Any], limit: int, after: str | None) -> Page[Any]:
    """One page of an ordered list, resumed after the last key, STORE-005; keys are compared as text."""
    results: list[Any] = []
    cursor = after
    for index, (key, value) in enumerate(keyed):
        if after is not None and key <= after:
            continue
        built = build(value)
        cursor = key
        if built is None:
            continue
        results.append(built)
        if limit and len(results) >= limit:
            return Page(tuple(results), cursor if index + 1 < len(keyed) else None)
    return Page(tuple(results), None)


def element(tx: Tx, res: Resolver | None, ref: Any) -> Element | None:
    """One element by address or id: its address, name_length, role and short name."""
    current = rows.current_element(tx, ref) if isinstance(ref, str) else None
    return None if current is None else views.element(tx, str(current['element_id']), res)


def _any_element_id(tx: Tx, ref: str) -> str | None:
    current = rows.current_element(tx, ref)
    if current is not None:
        return str(current['element_id'])
    if is_id(ref) and tx.base.kinds.get(ref) == 'element':
        return ref
    return None


def joins(tx: Tx, res: Resolver | None, ref: str, as_: str, limit: int, after: str | None) -> Page[Join]:
    """The joins an element receives, or those that hold it, as provider, each with its layer."""
    if as_ not in ('receiver', 'provider'):
        raise StoreError(f'{as_!r} is not receiver or provider.', f'metaform map joins {ref} as=receiver')
    element_id = _any_element_id(tx, ref)
    if element_id is None:
        return Page((), None)
    ids = tx.base.joins_received(element_id) if as_ == 'receiver' else tx.base.joins_holding(element_id)
    keyed = [(join_id, join_id) for join_id in sorted(ids)]

    def build(join_id: str) -> Join | None:
        current = versions.current_version(tx.base, 'join', join_id)
        return None if current is None else views.visible_join(tx, join_id, current, res)
    return _page(keyed, build, limit, after)


def join_ends(tx: Tx, join: str) -> tuple[str, str] | None:
    """One current join's receiver and the first element it holds, by address, STORE-010."""
    receiver, provider = views.join_ends(tx, join)
    return None if receiver is None or provider is None else (receiver, provider)


def where(tx: Tx, res: Resolver, raw: bool, address: str, full: bool) -> Where | None:
    """One read of an address, STORE-025: the element, what relies on it, the joins that hold it, what it relies on,
    the joins it receives, each with the elements it holds, its open work records and what the layers in context hold
    at it, the sources layer's refs among them. In context, the default, every part follows the reading context,
    LAYER-007."""
    context = None if raw else res
    element_id = tx.base.element_at(address)
    if element_id is None:
        return None
    found = views.element(tx, element_id, context)
    if found is None:
        return None
    at = node(tx, res, Node('element', found.id), raw)
    reaching = reaching_at(tx, res, address)
    provides = joins(tx, context, found.id, 'provider', 0, None).results
    receives = joins(tx, context, found.id, 'receiver', 0, None).results
    # the sources layer at each of its purpose joins, the code that realizes each purpose, so the one read an agent
    # orients from carries both halves; only that layer, so the read never fills with every layer's items, STORE-025
    held: dict[str, tuple[LayerGroup, ...]] = {}
    for one in (*provides, *receives):
        got = node(tx, res, Node('join', one.id), raw)
        code = tuple(group for group in got.layers if group.layer == 'sources') if got is not None else ()
        if code:
            held[one.id] = code
    return operations.decorate(tx, Where('element', found, None, provides, receives,
                 layers=() if at is None else at.layers, full=full, applying=reaching.applying,
                 visible=reaching.visible, join_layers=tuple(held.items())))


def node_where(tx: Tx, res: Resolver, raw: bool, target: Node) -> Where | None:
    """The where read of a node a ticket is on or links, MAP-048: an element's is `where` of its address; a join's is
    the join with its open work, what the layers in context hold at it and its open questions and messages. None when
    the node is not current or not in context."""
    if target.kind == 'element':
        address = rows.address_of(tx, target.id)
        return None if address is None else where(tx, res, raw, address, False)
    row = rows.current_join(tx, target.id)
    if row is None:
        return None
    holding = views.visible_join(tx, target.id, row, None if raw else res)
    if holding is None:
        return None
    at = node(tx, res, Node('join', target.id), raw)
    return operations.decorate(tx, Where('join', None, holding, layers=() if at is None else at.layers))


def children(tx: Tx, address: str, limit: int, after: str | None) -> Page[str]:
    """The next types toward the leaves; the empty address reads the root types, which have no parent."""
    found = sorted(child for child, parent in tx.base.types.items() if parent == (address or None))
    return _page([(child, child) for child in found], lambda child: child, limit, after)


def layer_items(tx: Tx, res: Resolver | None, layer: str, target: Node | None, limit: int,
                after: str | None) -> Page[Item | Property]:
    """A whole layer in row order, or a layer at one node: its items, then its properties.

    Named by the caller, the layer is read directly, hidden or masked, LAYER-008. Given a resolver, as an agent's
    context read, only what the layer reaches at its node's address is returned, STORE-019.
    """
    found = rows.layer(tx, layer)
    layers = all_layers(tx.base)
    base = tx.base

    def shown(row: Row, kind: str) -> bool:
        if res is None:
            return True
        address = (rows.address_of(tx, str(row['element_id'])) if kind == 'property'
                   else rows.node_address(tx, str(row['target_kind']), str(row['target_id'])))
        return address is not None and res.reaches(row.layer_id, address)

    if target is not None:
        kind, target_id = target.kind, target.id
        if kind in ('element', 'type'):
            current = rows.current_element(tx, target.id)
            kind, target_id = 'element', (str(current['element_id']) if current else target.id)
        items: list[Item | Property] = []
        for item_id in base.items_at(kind, target_id):
            row = base.current(item_id)
            if row is not None and row.layer_id == found.id and shown(row, 'item'):
                items.append(views.item(tx, item_id, row, layers))
        if kind == 'element':
            for property_id in base.properties_of(target_id):
                row = base.current(property_id)
                if row is not None and row.layer_id == found.id and shown(row, 'property'):
                    items.append(views.prop(tx, property_id, row, layers))
        return Page(tuple(items), None)

    keyed: list[tuple[str, tuple[str, str, Row]]] = []
    for item_id, row in base.currents('item'):
        if row.layer_id == found.id:
            keyed.append((f'i:{row.seq:012d}', ('item', item_id, row)))
    props = [(f'p:{row["element_id"]}:{property_id}', ('property', property_id, row))
             for property_id, row in base.currents('property') if row.layer_id == found.id]
    keyed += sorted(props)

    def build(entry: tuple[str, str, Row]) -> Item | Property | None:
        thing, ident, row = entry
        if not shown(row, thing):
            return None
        return views.item(tx, ident, row, layers) if thing == 'item' else views.prop(tx, ident, row, layers)
    return _page(keyed, build, limit, after)


def _locate(tx: Tx, target: object, raw: bool) -> tuple[str, str | None, Callable[[Resolver], bool]] | None:
    """A node's identity id, the address its selection is read at, and whether it shows in context."""
    if not isinstance(target, Node):
        raise StoreError(f'{target!r} is not a node.', 'metaform help map node')
    if target.kind in ('element', 'type'):
        current = rows.current_element(tx, target.id)
        if current is None:
            if raw and is_id(target.id) and tx.base.kinds.get(target.id) == 'element':
                return target.id, None, lambda res: False
            return None
        element_id, address = str(current['element_id']), str(current['address'])
        version = tx.base.current(element_id)
        assert version is not None
        layer_id = version.layer_id
        return element_id, address, lambda res: views.element_shows(res, layer_id, address)
    join_row = rows.current_join(tx, target.id)
    if join_row is None:
        return None
    address = rows.owner_address(tx, join_row)
    return target.id, address, lambda res: views.visible_join(tx, target.id, join_row, res) is not None


def node(tx: Tx, res: Resolver, target: Node, raw: bool) -> NodeView | None:
    """Every layer's items at one node, grouped by layer; in context, only the layers that reach it."""
    located = _locate(tx, target, raw)
    if located is None:
        return None
    thing_id, address, visible = located
    if not raw and not visible(res):
        return None
    kind = 'element' if target.kind == 'type' else target.kind
    groups: dict[str, tuple[list[Item], list[Property]]] = {}
    for item_id in tx.base.items_at(kind, thing_id):
        row = tx.base.current(item_id)
        if row is None:
            continue
        # An always_show item of a finished layer shows whether or not its layer reaches the node, LAYER-021.
        if (raw or res.reaches(row.layer_id, address)
                or (row['always_show'] and res.layers[row.layer_id].finished)):
            groups.setdefault(row.layer_id, ([], []))[0].append(views.item(tx, item_id, row, res.layers))
    if kind == 'element':
        for property_id in tx.base.properties_of(thing_id):
            row = tx.base.current(property_id)
            if row is not None and (raw or res.reaches(row.layer_id, address)):
                groups.setdefault(row.layer_id, ([], []))[1].append(views.prop(tx, property_id, row, res.layers))
    ordered = [layer_id for layer_id in res.layers if layer_id in groups]
    view = tuple(LayerGroup(layer_id, res.layers[layer_id].name, res.layers[layer_id].kind,  # type: ignore[arg-type]
                            tuple(groups[layer_id][0]), tuple(groups[layer_id][1])) for layer_id in ordered)
    return NodeView(Node(kind, thing_id), address, view, orphaned=address is None)


def context(tx: Tx, res: Resolver, address: str, limit: int, after: str | None) -> ContextView:
    """The properties that apply at an address, and those attached toward the leaves from it that are visible
    there, STORE-035."""
    applying: list[Property] = []
    for prefix in prefixes(address):
        element_id = tx.base.element_at(prefix)
        if element_id is None:
            continue
        for property_id in tx.base.properties_of(element_id):
            row = tx.base.current(property_id)
            if row is not None and res.reaches(row.layer_id, address):
                applying.append(views.prop(tx, property_id, row, res.layers))
    visible: list[Property] = []
    below = [each for each in tx.base.addresses() if each.startswith(address + '.')]
    cursor = after if after is not None else address + '.'
    next_cursor: str | None = None
    for element_address in below:
        if element_address <= cursor:
            continue
        element_id = tx.base.element_at(element_address)
        assert element_id is not None
        for property_id in tx.base.properties_of(element_id):
            row = tx.base.current(property_id)
            if row is not None and res.reaches(row.layer_id, element_address):
                visible.append(views.prop(tx, property_id, row, res.layers))
        if limit and len(visible) >= limit:
            more = any(each > element_address for each in below)
            next_cursor = element_address if more else None
            break
    return ContextView(address, tuple(applying), tuple(visible), next_cursor)


def reaching_at(tx: Tx, res: Resolver, address: str) -> ContextView:
    """Every property that reaches an address, for `where`, which holds a name of its own called context."""
    return context(tx, res, address, 0, None)


def links_to(tx: Tx, res: Resolver, target: Node, layer: str | None, raw: bool, limit: int,
             after: str | None) -> Page[Item]:
    """Items that link to a node; a named layer narrows the read and never widens it, STORE-019."""
    located = _locate(tx, target, raw)
    if located is None:
        return Page((), None)
    thing_id = located[0]
    kind = 'element' if target.kind == 'type' else target.kind
    layer_id = rows.layer(tx, layer).id if layer else None
    keyed = [(item_id, item_id) for item_id in sorted(tx.base.items_linking(kind, thing_id))]

    def build(item_id: str) -> Item | None:
        row = tx.base.current(item_id)
        if row is None or (layer_id is not None and row.layer_id != layer_id):
            return None
        if not raw:
            origin = rows.node_address(tx, str(row['target_kind']), str(row['target_id']))
            if origin is None or not res.reaches(row.layer_id, origin):
                return None
        return views.item(tx, item_id, row, res.layers)
    return _page(keyed, build, limit, after)


def citing(tx: Tx, key: str, value: str, limit: int, after: str | None) -> Page[Citation]:
    """Every current item and property whose refs hold this key and value, the sources layer's among them, with the
    address it sits at, MAP-021."""
    layers = all_layers(tx.base)
    keyed: list[tuple[str, tuple[str, str, Row]]] = []
    for owner in ('item', 'property'):
        for ident, row in tx.base.currents(owner):
            positions = [index for index, pair in enumerate(row.refs) if pair == (key, value)]
            if positions:
                keyed.append((f'{row.seq:012d}:{positions[0]:06d}', (owner, ident, row)))
    keyed.sort()

    def build(entry: tuple[str, str, Row]) -> Citation | None:
        owner, ident, row = entry
        if owner == 'item':
            address = rows.node_address(tx, str(row['target_kind']), str(row['target_id']))
        else:
            address = rows.address_of(tx, str(row['element_id']))
        return Citation(owner, ident, address, layers[row.layer_id].name)
    return _page(keyed, build, limit, after)


def history(tx: Tx, thing: str, limit: int, after: str | None) -> Page[VersionRecord]:
    """Every version of a thing in the order it was written: the version that added it, then each refinement."""
    kind = rows.kind_of(tx, thing)
    ordered = sorted(tx.base.versions.get(thing, ()), key=lambda version: version.seq)
    return sliced(tuple(views.version(tx, kind, thing, row) for row in ordered), limit, after)


def layers(tx: Tx, res: Resolver, tag: str | None, kind: str | None, module: str | None, limit: int,
           after: str | None) -> Page[Layer]:
    """The layers with their declaration, tags, state, hidden and toggled flags, LAYER-019."""
    chosen = list(res.layers.values())
    if tag is not None:
        chosen = [item for item in chosen if tag in item.tags]
    if kind == 'intake':  # the base layer's old name, LAYER-025
        kind = 'base'
    chosen = [item for item in chosen if (kind is None or item.kind == kind) and (module is None or item.module == module)]
    return sliced(tuple(views.layer(tx, item, toggled=res.start, hidden=res.hidden) for item in chosen), limit, after)


def provenance(tx: Tx, layer: str) -> Provenance | None:
    return views.provenance(tx, rows.layer(tx, layer).id)


def effective_selection(tx: Tx, res: Resolver, address: str) -> Selection:
    """The layers that reach an address, and any select or mask rows that cannot apply, STORE-035.

    An address out of form is read as given, since a select or mask there is stored as given, STORE-008.
    """
    ids = tuple(layer_id for layer_id in res.layers if layer_id in res.at(address))
    return Selection(address, ids, tuple(res.layers[layer_id].name for layer_id in ids),
                     tuple(res.unresolved(address)))


def search(tx: Tx, res: Resolver, text: str, layer: str | None, raw: bool, limit: int,
           after: str | None) -> Page[Item]:
    """Items whose value holds every word of the text, STORE-020, the best match first, with a stable cursor.

    In context an item is found only where its layer reaches the node it is attached to; a named layer narrows
    the search and never widens it; `raw=True` finds every stored item. The match is over the graph in memory,
    STORE-046: every word, as a whole word or a prefix, case apart; the items with the most matches first, then the
    older first.
    """
    words = [word.lower().strip(PUNCTUATION) for word in str(text).split()]
    words = [word for word in words if word]
    if not words:
        return Page((), None)
    layer_id = rows.layer(tx, layer).id if layer else None
    keyed: list[tuple[str, tuple[str, Row]]] = []
    for item_id, row in tx.base.currents('item'):
        held = str(row['value']).lower()
        tokens = [token.strip(PUNCTUATION) for token in held.split()]
        hits = sum(1 for word in words if any(token == word or token.startswith(word) for token in tokens))
        if hits < len(words):
            continue
        score = sum(held.count(word) for word in words)
        keyed.append((f'{10**6 - score:07d}|{row.seq:012d}', (item_id, row)))
    keyed.sort()

    def build(entry: tuple[str, Row]) -> Item | None:
        item_id, row = entry
        if layer_id is not None and row.layer_id != layer_id:
            return None
        if not raw:
            origin = rows.node_address(tx, str(row['target_kind']), str(row['target_id']))
            if origin is None or not res.reaches(row.layer_id, origin):
                return None
        return views.item(tx, item_id, row, res.layers)
    return _page(keyed, build, limit, after)


FIND_SPLIT = str.maketrans({'.': ' ', '_': ' ', '-': ' ', '/': ' '})


def find(tx: Tx, res: Resolver, text: str, limit: int) -> list[dict[str, Any]]:
    """What the map holds about some words, in context, best match first: elements by their address, name,
    short name and note; joins by their purpose and EF, at their receiver; layer items by their value, at the node they
    are attached to. Each hit is its Address, its kind and the line it matched, so an agent finds where to read without
    reading the map whole. A hit holds at least half of the words, each as a whole word or a prefix; the most words
    first, then elements, joins and items, then by address."""
    words = [word.lower().strip(PUNCTUATION) for word in str(text).split()]
    words = [word for word in words if word]
    if not words:
        return []
    least = max(1, (len(words) + 1) // 2)

    def hits(held: str) -> int:
        tokens = [token.strip(PUNCTUATION) for token in held.lower().translate(FIND_SPLIT).split()]
        return sum(1 for word in words if any(token == word or token.startswith(word) for token in tokens))
    found: list[tuple[int, int, str, dict[str, Any]]] = []
    for element_id, _row in tx.base.currents('element'):
        made = views.element(tx, element_id, res)
        if made is None:
            continue
        said = made.name or made.short_name
        count = hits(f'{made.address} {said} {made.short_name} {made.note or ""}')
        if count >= least:
            found.append((-count, 0, made.address, {'address': made.address, 'kind': 'element', 'what': said}))
    for _join_id, row in tx.base.currents('join'):
        address = rows.address_of(tx, str(row['receiver']))
        if address is None or not res.reaches(row.layer_id, address):
            continue
        purpose, ef = str(row['purpose'] or ''), str(row['ef'] or '')
        count = hits(f'{purpose} {ef}')
        if count >= least:
            found.append((-count, 1, address, {'address': address, 'kind': 'join',
                                                'what': purpose + (f' EF: {ef}' if ef else '')}))
    for _item_id, row in tx.base.currents('item'):
        origin = rows.node_address(tx, str(row['target_kind']), str(row['target_id']))
        if origin is None or not res.reaches(row.layer_id, origin):
            continue
        value = str(row['value'])
        count = hits(value)
        if count >= least:
            found.append((-count, 2, origin, {'address': origin, 'kind': 'item', 'what': value.strip('"')[:160]}))
    found.sort(key=lambda one: one[:3])
    return [hit for *_, hit in found[:limit]]


def roots(tx: Tx, res: Resolver | None, limit: int, after: str | None) -> Roots:
    """The map's entry: the CQU and DE with the joins they receive, and every root element, one page, STORE-025.

    The role is on the element, STORE-009; a root element is one with a role. Empty until the intake has finished.
    """
    if not has_intake(tx):
        return Roots((), (), None)
    entry: list[RootEntry] = []
    current = [(element_id, row) for element_id, row in tx.base.currents('element')]
    if after is None:
        for element_id, _row in sorted((pair for pair in current if pair[1]['role'] in ('CQU', 'DE')),
                                       key=lambda pair: (pair[1]['role'] != 'DE', pair[0])):
            found = views.element(tx, element_id, res)
            if found is None:
                continue
            held: list[Join] = []
            for join_id in tx.base.joins_received(element_id):
                version = versions.current_version(tx.base, 'join', join_id)
                shown = views.visible_join(tx, join_id, version, res) if version is not None else None
                if shown is not None:
                    held.append(shown)
            entry.append(RootEntry(found, tuple(held)))
    keyed = sorted((element_id, (element_id, row)) for element_id, row in current if row['role'] is not None)

    def build(pair: tuple[str, Row]) -> RootElement | None:
        element_id, row = pair
        found = views.element(tx, element_id, res)
        if found is None:
            return None
        return RootElement(found.id, found.address, str(row['role']), found.short_name)
    page = _page(keyed, build, limit, after)
    return Roots(tuple(entry), page.results, page.next)


def has_intake(tx: Tx) -> bool:
    return any(layer.kind in versions.BASE_KINDS and layer.ready is not None for layer in tx.base.layers.values())


def graph(tx: Tx, res: Resolver | None, limit: int, after: str | None) -> GraphPage:
    """A page of the map in address order, VIEW-005 and VIEW-010: each element in context, with its nearest parent
    element in context, and each join it receives, in context, with the elements it holds."""
    addresses = [address for address in tx.base.addresses() if after is None or address > after]
    more = bool(limit) and len(addresses) > limit
    found = addresses[:limit] if limit else addresses
    shown: dict[str, bool] = {}

    def in_context(address: str) -> bool:
        if address not in shown:
            element_id = tx.base.element_at(address)
            shown[address] = element_id is not None and views.element(tx, element_id, res) is not None
        return shown[address]

    elements: list[GraphElement] = []
    held: list[Join] = []
    for address in found:
        element_id = tx.base.element_at(address)
        assert element_id is not None
        element_view = views.element(tx, element_id, res)
        shown[address] = element_view is not None
        if element_view is None:
            continue
        parent = element_view.within if element_view.within and in_context(element_view.within) else next(
            (prefix for prefix in reversed(prefixes(element_view.address)[:-1]) if in_context(prefix)), None)
        elements.append(GraphElement(element_view, parent))
        held += joins(tx, res, element_view.id, 'receiver', 0, None).results
    return GraphPage(tuple(elements), tuple(held), found[-1] if more else None)


def layer_graph(tx: Tx, layer: str) -> GraphPage:
    """One layer's own elements and the joins it wrote, building or finished, BASE-039 and VIEW-005.

    The intake agent reads its work back with it while it records, and the viewer follows it live. It is not a
    context read: it shows what one layer wrote and reaches nothing through the selection.
    """
    found = rows.layer(tx, layer)
    written = sorted((str(row['address']), element_id) for element_id, row in tx.base.currents('element')
                     if row.layer_id == found.id)
    addresses = {address for address, _ in written}
    elements: list[GraphElement] = []
    held: list[Join] = []
    for _address, element_id in written:
        element_view = views.element(tx, element_id, None)
        if element_view is None:
            continue
        parent = element_view.within if element_view.within in addresses else next(
            (prefix for prefix in reversed(prefixes(element_view.address)[:-1]) if prefix in addresses), None)
        elements.append(GraphElement(element_view, parent))
        held += [join for join in joins(tx, None, element_view.id, 'receiver', 0, None).results
                 if join.layer_id == found.id]
    return GraphPage(tuple(elements), tuple(held))


def cypher(tx: Tx, query: str, selection: Sequence[str] | None = None) -> Any:
    """A Cypher query over the base's graph, for agents and tools, STORE-046, seeing only what the layers in view show:
    the selection given, or else the layers turned on, with hidden layers and the select and mask rows at each
    address applied, as every other read is. A query names its own layers to hide or show them on
    the fly."""
    import networkx
    res = resolver(tx, selection, tx.toggled)
    graph = tx.base.graph
    nodes = graph.nodes

    def address_of(node_id: Any) -> str | None:
        found = nodes.get(node_id) if node_id is not None else None
        if not found:
            return None
        if found.get('kind') == 'element':
            return found.get('address')
        if found.get('kind') == 'join':
            return address_of(found.get('receiver'))
        if found.get('kind') == 'item':
            return address_of(found.get('target_id'))
        if found.get('kind') == 'property':
            return address_of(found.get('element_id'))
        return None

    def shows(node_id: Any) -> bool:
        found = nodes[node_id]
        kind = found.get('kind')
        if not kind or found.get('current') is False:
            return False
        layer_id = str(found.get('layer_id') or '')
        if kind == 'element':  # the base's elements are always nodes, as in every read, views.element_shows
            return views.element_shows(res, layer_id, str(found.get('address')))
        return res.reaches(layer_id, address_of(node_id))

    def shows_edge(source: Any, target: Any, key: Any) -> bool:
        """An edge belongs to the object that drew it, a join, item or property, and shows where its layer reaches
        the place the edge starts from, so no edge carries a layer out of view between two nodes in view."""
        return res.reaches(str(graph.edges[source, target, key].get('layer_id') or ''), address_of(source))

    view = networkx.subgraph_view(graph, filter_node=shows, filter_edge=shows_edge)
    return tx.base.cypher(query, view)
