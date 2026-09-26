"""The read operations of STORE-025, each answered through an index inside one read transaction.

Every read in context, the default, resolves the layers that reach each place
through one `Resolver`, so select, mask, hiding and building apply on every
path, STORE-019; `raw=True` reads every stored layer. Lists are paged, and each
page is one index range read resumed after the last key, STORE-005.
"""
from __future__ import annotations

import dataclasses
import sqlite3
from collections.abc import Callable, Sequence
from typing import Any

from .. import home
from ..errors import StoreError
from . import corrections, rows, views
from .ids import is_id, prefixes
from .paging import LIMIT, paged, sliced
from .records import (Citation, ContextView, Element, Finding, GraphElement, GraphJoin, GraphPage, Item, Join, Layer,
                      LayerGroup, Node, NodeView, Notice, Page, PeelPreview, Property, Provenance, Report, RootElement,
                      RootEntry, Roots, Selection, Subtype, Version, Where)
from .selection import Resolver, all_layers
from .session import Tx

Row = sqlite3.Row


def resolver(tx: Tx, selection: Sequence[str] | None, toggled: Sequence[str]) -> Resolver:
    return Resolver(tx.db, selection, toggled)


def element(tx: Tx, res: Resolver | None, ref: Any) -> Element | None:
    """One element by address or id, with its descriptors and refs."""
    current = rows.current_element(tx, ref) if isinstance(ref, str) else None
    return None if current is None else views.element(tx, str(current['element_id']), res)


def _any_element_id(tx: Tx, ref: str) -> str | None:
    current = rows.current_element(tx, ref)
    if current is not None:
        return str(current['element_id'])
    if is_id(ref) and tx.db.execute('SELECT 1 FROM element_ids WHERE element_id=?', (ref,)).fetchone():
        return ref
    return None


def joins(tx: Tx, res: Resolver | None, ref: str, as_: str, limit: int, after: str | None) -> Page[Join]:
    """The joins an element owns, or those it provides for, each with its layer."""
    if as_ not in ('receiver', 'provider'):
        raise StoreError(f'{as_!r} is not receiver or provider.', f'metaform map joins {ref} as=receiver')
    element_id = _any_element_id(tx, ref)
    if element_id is None:
        return Page((), None)

    def fetch(cursor: str | None, count: int) -> list[Row]:
        return tx.db.execute(f'SELECT c.join_id AS key, j.* FROM current_joins c JOIN joins j ON j.row = c.row '
                             f'WHERE c.{as_}=? AND c.join_id > ? ORDER BY c.join_id LIMIT ?',
                             (element_id, cursor or '', count)).fetchall()
    return paged(fetch, lambda row: views.visible_join(tx, row, res), limit, after)


def subtypes(tx: Tx, res: Resolver | None, join: str, limit: int, after: str | None) -> Page[Subtype]:
    join_row = tx.db.execute('SELECT j.* FROM current_joins c JOIN joins j ON j.row = c.row WHERE c.join_id=?',
                             (join,)).fetchone()
    if join_row is None:
        return Page((), None)
    if res is not None and views.visible_join(tx, join_row, res) is None:
        return Page((), None)
    layers = res.layers if res else all_layers(tx.db)

    def fetch(cursor: str | None, count: int) -> list[Row]:
        return tx.db.execute('SELECT c.subtype_id AS key, s.* FROM current_subtypes c JOIN subtypes s ON s.row = c.row '
                             'WHERE c.join_id=? AND c.subtype_id > ? ORDER BY c.subtype_id LIMIT ?',
                             (join, cursor or '', count)).fetchall()
    return paged(fetch, lambda row: views.subtype(tx, row, join, layers, res), limit, after)


def where(tx: Tx, res: Resolver | None, address: str) -> Where | None:
    """The element at an address, or the subtype there with the join that holds it."""
    current = tx.db.execute('SELECT element_id FROM current_elements WHERE address=?', (address,)).fetchone()
    if current is not None:
        found = views.element(tx, str(current[0]), res)
        return None if found is None else Where('element', element=found)
    row = tx.db.execute('SELECT c.join_id, s.* FROM current_subtypes c JOIN subtypes s ON s.row = c.row '
                        'WHERE c.address=?', (address,)).fetchone()
    if row is None:
        return None
    join_row = tx.db.execute('SELECT j.* FROM current_joins c JOIN joins j ON j.row = c.row WHERE c.join_id=?',
                             (row['join_id'],)).fetchone()
    if join_row is None:
        return None
    holding = views.visible_join(tx, join_row, res)
    if holding is None:
        return None
    layers = res.layers if res else all_layers(tx.db)
    return Where('subtype', subtype=views.subtype(tx, row, str(row['join_id']), layers, res), join=holding)


def children(tx: Tx, address: str, limit: int, after: str | None) -> Page[str]:
    """The next types up the tree, toward the leaves; the empty address reads the top types, which have no parent."""
    def fetch(cursor: str | None, count: int) -> list[Row]:
        return tx.db.execute('SELECT address AS key FROM types WHERE parent IS ? AND address > ? ORDER BY address '
                             'LIMIT ?', (address or None, cursor or '', count)).fetchall()
    return paged(fetch, lambda row: str(row['key']), limit, after)


def layer_items(tx: Tx, res: Resolver | None, layer: str, target: Node | None, limit: int,
                after: str | None) -> Page[Item | Property]:
    """A whole layer in row order, or a layer at one node: its items, then its properties.

    Named by the caller, the layer is read directly, hidden or masked, LAYER-008. Given a resolver, as an agent's
    context read, only what the layer reaches at its node's address is returned, STORE-019.
    """
    found = rows.layer(tx, layer)
    layers = all_layers(tx.db)

    def shown(row: Row, kind: str) -> bool:
        if res is None:
            return True
        address = (rows.address_of(tx, str(row['element_id'])) if kind == 'property'
                   else rows.node_address(tx, str(row['target_kind']), str(row['target_id'])))
        return address is not None and res.reaches(str(row['layer_id']), address)

    if target is not None:
        kind, target_id = target.kind, target.id
        if kind in ('element', 'type'):
            current = rows.current_element(tx, target.id)
            kind, target_id = 'element', (str(current['element_id']) if current else target.id)
        elif kind == 'subtype' and not is_id(target.id):
            row = tx.db.execute('SELECT subtype_id FROM current_subtypes WHERE address=?', (target.id,)).fetchone()
            target_id = str(row[0]) if row else target.id
        items: list[Item | Property] = [views.item(tx, row, layers) for row in tx.db.execute(
            'SELECT i.* FROM current_items c JOIN items i ON i.row = c.row '
            'WHERE c.target_kind=? AND c.target_id=? AND c.layer_id=? ORDER BY c.row',
            (kind, target_id, found.layer_id)) if shown(row, 'item')]
        if kind == 'element':
            items += [views.prop(tx, row, layers) for row in tx.db.execute(
                'SELECT p.* FROM current_properties c JOIN properties p ON p.row = c.row '
                'WHERE c.element_id=? AND c.layer_id=? ORDER BY c.row', (target_id, found.layer_id))
                if shown(row, 'property')]
        return Page(tuple(items), None)

    def fetch(cursor: str | None, count: int) -> list[Row]:
        phase, _, position = (cursor or 'i:0').partition(':')
        found_rows: list[Row] = []
        if phase == 'i':
            found_rows = tx.db.execute("SELECT 'i:' || c.row AS key, 'item' AS thing, i.* FROM current_items c "
                                       'JOIN items i ON i.row = c.row WHERE c.layer_id=? AND c.row > ? '
                                       'ORDER BY c.row LIMIT ?', (found.layer_id, int(position or 0), count)).fetchall()
            if len(found_rows) >= count:
                return found_rows
            position = ''
        element_id, _, property_id = position.partition(':')
        found_rows += tx.db.execute("SELECT 'p:' || c.element_id || ':' || c.property_id AS key, 'property' AS thing, "
                                    'p.* FROM current_properties c JOIN properties p ON p.row = c.row '
                                    'WHERE c.layer_id=? AND (c.element_id, c.property_id) > (?, ?) '
                                    'ORDER BY c.element_id, c.property_id LIMIT ?',
                                    (found.layer_id, element_id, property_id, count - len(found_rows))).fetchall()
        return found_rows

    def build(row: Row) -> Item | Property | None:
        if not shown(row, str(row['thing'])):
            return None
        return views.item(tx, row, layers) if row['thing'] == 'item' else views.prop(tx, row, layers)
    return paged(fetch, build, limit, after)


def _locate(tx: Tx, target: object, raw: bool) -> tuple[str, str | None, Callable[[Resolver], bool]] | None:
    """A node's identity id, the address its selection is read at, and whether it shows in context."""
    if not isinstance(target, Node):
        raise StoreError(f'{target!r} is not a node.', 'metaform help map node')
    if target.kind in ('element', 'type'):
        current = rows.current_element(tx, target.id)
        if current is None:
            if raw and is_id(target.id) and tx.db.execute('SELECT 1 FROM element_ids WHERE element_id=?',
                                                          (target.id,)).fetchone():
                return target.id, None, lambda res: False
            return None
        element_id, address = str(current['element_id']), str(current['address'])
        row = tx.db.execute('SELECT layer_id FROM elements WHERE row=?', (current['row'],)).fetchone()
        return element_id, address, lambda res: views.element_shows(res, str(row[0]), address)
    if target.kind == 'join':
        join_row = tx.db.execute('SELECT j.* FROM current_joins c JOIN joins j ON j.row = c.row WHERE c.join_id=?',
                                 (target.id,)).fetchone()
        if join_row is None:
            return None
        address = rows.address_of(tx, str(join_row['receiver']))
        return target.id, address, lambda res: views.visible_join(tx, join_row, res) is not None
    column = 'subtype_id' if is_id(target.id) else 'address'
    row = tx.db.execute(f'SELECT subtype_id, join_id, address FROM current_subtypes WHERE {column}=?',
                        (target.id,)).fetchone()
    if row is None:
        return None
    holding = tx.db.execute('SELECT j.* FROM current_joins c JOIN joins j ON j.row = c.row WHERE c.join_id=?',
                            (row['join_id'],)).fetchone()
    return (str(row['subtype_id']), str(row['address']),
            lambda res: holding is not None and views.visible_join(tx, holding, res) is not None)


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
    for row in tx.db.execute('SELECT i.* FROM current_items c JOIN items i ON i.row = c.row '
                             'WHERE c.target_kind=? AND c.target_id=? ORDER BY c.row', (kind, thing_id)):
        if raw or res.reaches(str(row['layer_id']), address):
            groups.setdefault(str(row['layer_id']), ([], []))[0].append(views.item(tx, row, res.layers))
    if kind == 'element':
        for row in tx.db.execute('SELECT p.* FROM current_properties c JOIN properties p ON p.row = c.row '
                                 'WHERE c.element_id=? ORDER BY c.row', (thing_id,)):
            if raw or res.reaches(str(row['layer_id']), address):
                groups.setdefault(str(row['layer_id']), ([], []))[1].append(views.prop(tx, row, res.layers))
    ordered = [layer_id for layer_id in res.layers if layer_id in groups]
    view = tuple(LayerGroup(layer_id, res.layers[layer_id].name, res.layers[layer_id].kind,
                            tuple(groups[layer_id][0]), tuple(groups[layer_id][1])) for layer_id in ordered)
    return NodeView(Node(kind, thing_id), address, view, orphaned=address is None)


def context(tx: Tx, res: Resolver, address: str, limit: int, after: str | None) -> ContextView:
    """The properties that apply at an address, and those visible there from above, STORE-035."""
    applying: list[Property] = []
    for prefix in prefixes(address):
        found = tx.db.execute('SELECT element_id FROM current_elements WHERE address=?', (prefix,)).fetchone()
        if found is None:
            continue
        for row in tx.db.execute('SELECT p.* FROM current_properties c JOIN properties p ON p.row = c.row '
                                 'WHERE c.element_id=? ORDER BY c.row', (found[0],)):
            if res.reaches(str(row['layer_id']), address):
                applying.append(views.prop(tx, row, res.layers))
    visible: list[Property] = []
    cursor = after if after is not None else address + '.'
    upper = address + '/'
    next_cursor: str | None = None
    while True:
        found_rows = tx.db.execute('SELECT element_id, address FROM current_elements WHERE address > ? AND address < ? '
                                   'ORDER BY address LIMIT ?', (cursor, upper, LIMIT)).fetchall()
        if not found_rows:
            break
        for element_id, element_address in found_rows:
            cursor = str(element_address)
            for row in tx.db.execute('SELECT p.* FROM current_properties c JOIN properties p ON p.row = c.row '
                                     'WHERE c.element_id=? ORDER BY c.row', (element_id,)):
                if res.reaches(str(row['layer_id']), str(element_address)):
                    visible.append(views.prop(tx, row, res.layers))
            if limit and len(visible) >= limit:
                more = tx.db.execute('SELECT 1 FROM current_elements WHERE address > ? AND address < ? LIMIT 1',
                                     (element_address, upper)).fetchone()
                next_cursor = str(element_address) if more else None
                break
        if next_cursor is not None or (limit and len(visible) >= limit):
            break
    return ContextView(address, tuple(applying), tuple(visible), next_cursor)


def links_to(tx: Tx, res: Resolver, target: Node, layer: str | None, raw: bool, limit: int,
             after: str | None) -> Page[Item]:
    """Items that link to a node; a named layer narrows the read and never widens it, STORE-019."""
    located = _locate(tx, target, raw)
    if located is None:
        return Page((), None)
    thing_id = located[0]
    kind = 'element' if target.kind == 'type' else target.kind
    layer_id = rows.layer(tx, layer).layer_id if layer else None

    def fetch(cursor: str | None, count: int) -> list[Row]:
        sql = ('SELECT c.item_id AS key, i.* FROM current_items c JOIN items i ON i.row = c.row '
               'WHERE c.link_kind=? AND c.link_id=?')
        params: list[Any] = [kind, thing_id]
        if layer_id is not None:
            sql += ' AND c.layer_id=?'
            params.append(layer_id)
        sql += ' AND c.item_id > ? ORDER BY c.item_id LIMIT ?'
        return tx.db.execute(sql, (*params, cursor or '', count)).fetchall()

    def build(row: Row) -> Item | None:
        if not raw:
            origin = rows.node_address(tx, str(row['target_kind']), str(row['target_id']))
            if origin is None or not res.reaches(str(row['layer_id']), origin):
                return None
        return views.item(tx, row, res.layers)
    return paged(fetch, build, limit, after)


def citing(tx: Tx, key: str, value: str, limit: int, after: str | None) -> Page[Citation]:
    """Every current element, join, subtype, property and item whose refs hold this key and value, MAP-021."""
    layers = all_layers(tx.db)
    seen: set[tuple[str, str]] = set()

    def fetch(cursor: str | None, count: int) -> list[Row]:
        return tx.db.execute('SELECT ref_id AS key, owner, owner_row FROM refs WHERE key=? AND value=? AND ref_id > ? '
                             'ORDER BY ref_id LIMIT ?', (key, value, int(cursor or 0), count)).fetchall()

    def build(row: Row) -> Citation | None:
        spec = corrections.KINDS[str(row['owner'])]
        current = tx.db.execute(f'SELECT {spec.id_column} FROM {spec.current} WHERE row=?',
                                (row['owner_row'],)).fetchone()
        if current is None or (str(row['owner']), str(current[0])) in seen:
            return None
        seen.add((str(row['owner']), str(current[0])))
        version_row = tx.db.execute(f'SELECT layer_id FROM {spec.table} WHERE row=?', (row['owner_row'],)).fetchone()
        address = None
        if row['owner'] in ('element', 'subtype'):
            address = rows.node_address(tx, str(row['owner']), str(current[0]))
        return Citation(str(row['owner']), str(current[0]), address, layers[version_row[0]].name)
    return paged(fetch, build, limit, after)


def history(tx: Tx, thing: str, limit: int, after: str | None) -> Page[Version]:
    """Every version of a thing: the row that added it, then each stacked correction's row, in order."""
    kind = rows.kind_of(tx, thing)
    spec = corrections.KINDS[kind]
    positions = corrections.stack_positions(tx.db)
    kinds = corrections.layer_kinds(tx.db)
    ordered = sorted((row for row in tx.db.execute(f'SELECT * FROM {spec.table} WHERE {spec.id_column}=?', (thing,))
                      if kinds[row['layer_id']] != 'correction' or row['layer_id'] in positions),
                     key=lambda row: positions.get(str(row['layer_id']), 0))
    return sliced(tuple(views.version(tx, kind, row, positions) for row in ordered), limit, after)


def stack(tx: Tx, limit: int, after: str | None) -> Page[Layer]:
    """The correction layers in the order they were applied, each with its provenance."""
    found = tuple(views.layer(tx, rows.layer(tx, str(row[0])), with_provenance=True)
                  for row in tx.db.execute('SELECT layer_id FROM correction_stack ORDER BY position'))
    return sliced(found, limit, after)


def layers(tx: Tx, res: Resolver, tag: str | None, kind: str | None, module: str | None, limit: int,
           after: str | None) -> Page[Layer]:
    """The layers with their declaration, tags, state, hidden and toggled flags, LAYER-019."""
    chosen = list(res.layers.values())
    if tag is not None:
        tagged = {str(row[0]) for row in tx.db.execute('SELECT layer_id FROM layer_tags WHERE tag=?', (tag,))}
        chosen = [item for item in chosen if item.layer_id in tagged]
    chosen = [item for item in chosen if (kind is None or item.kind == kind) and (module is None or item.module == module)]
    return sliced(tuple(views.layer(tx, item, toggled=res.start, hidden=res.hidden) for item in chosen), limit, after)


def provenance(tx: Tx, layer: str) -> Provenance | None:
    return views.provenance(tx, rows.layer(tx, layer).layer_id)


def effective_selection(tx: Tx, res: Resolver, address: str) -> Selection:
    """The layers that reach an address, and any select or mask rows that cannot apply, STORE-035.

    An address out of form is read as given, since a select or mask there is stored as given, STORE-008.
    """
    ids = tuple(layer_id for layer_id in res.layers if layer_id in res.at(address))
    return Selection(address, ids, tuple(res.layers[layer_id].name for layer_id in ids),
                     tuple(res.unresolved(address)))


def search(tx: Tx, res: Resolver, text: str, layer: str | None, raw: bool, limit: int,
           after: str | None) -> Page[Item]:
    """Items whose value holds every word of the text, STORE-020, in rank order with a stable cursor.

    In context an item is found only where its layer reaches the node it is attached to; a named layer narrows
    the search and never widens it; `raw=True` finds every stored item. The cursor is the last match's rank and
    row, so a page resumes where the previous one ended, STORE-005.
    """
    words = [word for word in str(text).split() if word]
    if not words:
        return Page((), None)
    query = ' '.join('"' + word.replace('"', '""') + '"' for word in words)
    layer_id = rows.layer(tx, layer).layer_id if layer else None

    def fetch(cursor: str | None, count: int) -> list[Row]:
        sql = ('SELECT item_text.rank AS score, item_text.rowid AS fts, i.* FROM item_text '
               'JOIN current_items c ON c.row = item_text.rowid JOIN items i ON i.row = c.row '
               'WHERE item_text MATCH ?')
        params: list[Any] = [query]
        if cursor is not None:
            score, _, fts = cursor.partition('|')
            sql += ' AND (item_text.rank > ? OR (item_text.rank = ? AND item_text.rowid > ?))'
            params += [float(score), float(score), int(fts)]
        sql += ' ORDER BY item_text.rank, item_text.rowid LIMIT ?'
        return tx.db.execute(sql, (*params, count)).fetchall()

    def build(row: Row) -> Item | None:
        if layer_id is not None and row['layer_id'] != layer_id:
            return None
        if not raw:
            origin = rows.node_address(tx, str(row['target_kind']), str(row['target_id']))
            if origin is None or not res.reaches(str(row['layer_id']), origin):
                return None
        return views.item(tx, row, res.layers)
    return paged(fetch, build, limit, after, key=lambda row: f'{float(row["score"])!r}|{row["fts"]}')


def roots(tx: Tx, res: Resolver | None, limit: int, after: str | None) -> Roots:
    """The map's entry: the VE and DE with the joins they receive, and every root element, one page, STORE-025."""
    intake = tx.db.execute("SELECT layer_id FROM layers WHERE kind='intake' AND ready IS NOT NULL LIMIT 1").fetchone()
    if intake is None:
        return Roots((), (), None)
    layer_id = str(intake[0])
    entry: list[RootEntry] = []
    if after is None:
        for element_id, _role in tx.db.execute("SELECT element_id, role FROM element_roles WHERE layer_id=? AND role "
                                               "IN ('VE', 'DE') ORDER BY role DESC, element_id",
                                               (layer_id,)).fetchall():
            found = views.element(tx, str(element_id), res)
            if found is None:
                continue
            received = tx.db.execute('SELECT c.join_id AS key, j.* FROM current_joins c JOIN joins j ON j.row = c.row '
                                     'WHERE c.receiver=? ORDER BY c.join_id', (element_id,)).fetchall()
            held = [join for join in (views.visible_join(tx, row, res) for row in received) if join is not None]
            entry.append(RootEntry(found, tuple(held)))

    def fetch(cursor: str | None, count: int) -> list[Row]:
        return tx.db.execute('SELECT element_id AS key, role FROM element_roles WHERE layer_id=? AND element_id > ? '
                             'ORDER BY element_id LIMIT ?', (layer_id, cursor or '', count)).fetchall()

    def build(row: Row) -> RootElement | None:
        found = views.element(tx, str(row['key']), res)
        if found is None:
            return None
        return RootElement(found.element_id, found.address, str(row['role']), found.name)
    page = paged(fetch, build, limit, after)
    return Roots(tuple(entry), page.results, page.next)


def findings(tx: Tx, res: Resolver | None, flag: str | None, layer: str | None, limit: int,
             after: str | None) -> Page[Finding]:
    """Flagged objects, by flag, each with its address or its join's ends, STORE-042."""
    known = res.layers if res else all_layers(tx.db)
    layer_id = rows.layer(tx, layer).layer_id if layer else None

    def fetch(cursor: str | None, count: int) -> list[Row]:
        if flag is not None:
            return tx.db.execute('SELECT row AS key, * FROM findings WHERE flag=? AND row > ? ORDER BY row LIMIT ?',
                                 (flag, int(cursor or 0), count)).fetchall()
        return tx.db.execute('SELECT row AS key, * FROM findings WHERE row > ? ORDER BY row LIMIT ?',
                             (int(cursor or 0), count)).fetchall()

    def build(row: Row) -> Finding | None:
        if layer_id is not None and row['layer_id'] != layer_id:
            return None
        return views.found_flag(tx, row, known, res)
    return paged(fetch, build, limit, after)


def reports(tx: Tx, kind: str | None, layer: str | None, limit: int, after: str | None) -> Page[Report]:
    """The report, feedback and shape files of this metaform, oldest first, STORE-043."""
    if layer is not None:
        layer_id = rows.layer(tx, layer).layer_id
        found = tuple(views.report(tx, row) for row in tx.db.execute(
            'SELECT * FROM reports WHERE layer_id=? ORDER BY kind, report_id', (layer_id,))
            if kind is None or row['kind'] == kind)
        return sliced(found, limit, after)

    def fetch(cursor: str | None, count: int) -> list[Row]:
        created, _, name = (cursor or '|').partition('|')
        return tx.db.execute("SELECT created || '|' || report_id AS key, * FROM reports "
                             'WHERE (created, report_id) > (?, ?) ORDER BY created, report_id LIMIT ?',
                             (created, name, count)).fetchall()
    return paged(fetch, lambda row: views.report(tx, row) if kind is None or row['kind'] == kind else None,
                 limit, after)


def report(tx: Tx, name: str) -> Report | None:
    row = tx.db.execute('SELECT * FROM reports WHERE report_id=?', (name,)).fetchone()
    return None if row is None else views.report(tx, row)


def save_report(tx: Tx, name: str, run_id: str, kind: str, size: int, layer: str | None) -> Report:
    """Record one report, feedback or shape file, or its new size after an append, STORE-043."""
    layer_id = rows.layer(tx, layer).layer_id if layer else None
    tx.db.execute('INSERT INTO reports(report_id, run_id, layer_id, kind, created, size) VALUES (?, ?, ?, ?, ?, ?) '
                  'ON CONFLICT(report_id) DO UPDATE SET size=MAX(size, excluded.size)',
                  (name, run_id, layer_id, kind, home.now(), size))
    return views.report(tx, tx.db.execute('SELECT * FROM reports WHERE report_id=?', (name,)).fetchone())


def has_intake(tx: Tx) -> bool:
    return tx.db.execute("SELECT 1 FROM layers WHERE kind='intake' AND ready IS NOT NULL LIMIT 1").fetchone() \
        is not None


def peel_preview(tx: Tx, layer: str) -> PeelPreview:
    """What removing a correction layer would change, and whether it is the top one, VIEW-014."""
    found = rows.layer(tx, layer)
    if found.kind != 'correction':
        return PeelPreview(found.name, False, notices=(
            Notice('layer', f'{found.name} is not a correction layer; only a correction layer is removed from the stack.'),))
    top = tx.db.execute('SELECT layer_id FROM correction_stack ORDER BY position DESC LIMIT 1').fetchone()
    stacked = tx.db.execute('SELECT 1 FROM correction_stack WHERE layer_id=?', (found.layer_id,)).fetchone()
    if stacked is None:
        return PeelPreview(found.name, False, notices=(
            Notice('layer', f'{found.name} is not on the stack; it changes nothing yet.'),))
    return PeelPreview(found.name, top is not None and top[0] == found.layer_id,
                       tuple(corrections.preview(tx.db, found.layer_id)))


def graph(tx: Tx, res: Resolver | None, limit: int, after: str | None) -> GraphPage:
    """A page of the map in address order, VIEW-005 and VIEW-010: each element in context with its nearest parent
    element in context, and each join it receives, in context, with its subtypes. One read; every lookup by index."""
    found = tx.db.execute('SELECT element_id, address FROM current_elements WHERE address > ? ORDER BY address '
                          'LIMIT ?', (after or '', limit + 1 if limit else -1)).fetchall()
    more = bool(limit) and len(found) > limit
    found = found[:limit] if limit else found
    shown: dict[str, bool] = {}

    def in_context(address: str) -> bool:
        if address not in shown:
            current = tx.db.execute('SELECT element_id FROM current_elements WHERE address=?', (address,)).fetchone()
            shown[address] = current is not None and views.element(tx, str(current[0]), res) is not None
        return shown[address]

    elements: list[GraphElement] = []
    held: list[GraphJoin] = []
    for row in found:
        element_view = views.element(tx, str(row['element_id']), res)
        shown[str(row['address'])] = element_view is not None
        if element_view is None:
            continue
        parent = next((prefix for prefix in reversed(prefixes(element_view.address)[:-1]) if in_context(prefix)), None)
        elements.append(GraphElement(element_view, parent))
        for join in joins(tx, res, element_view.element_id, 'receiver', 0, None).results:
            fields = {item.name: getattr(join, item.name) for item in dataclasses.fields(join)}
            held.append(GraphJoin(**fields, subtypes=subtypes(tx, res, join.join_id, 0, None).results))
    return GraphPage(tuple(elements), tuple(held), str(found[-1]['address']) if more else None)
