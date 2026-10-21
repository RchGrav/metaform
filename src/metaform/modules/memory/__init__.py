"""memory: a memory graph of its own, presented at each node of the map as the MCP reference memory server, BASE-040,
LAYER-012, LAYER-013, STORE-020 and VIEW-034.

The graph is the reference server's: entities with a name, an entityType and observations, and relations between
entities, kept in the order they were made. It is kept in this module's project-level tables, STORE-045, so a clear
of the project's metaforms keeps it. A memory entity is never an element of the map and never a namespace segment.

A memory is tied to a map node by a join of type memory: a row naming the entity and the node's namespace address, an
element's address, or a map join's receiver and provider addresses. A new intake that holds the same address reconnects
it, MAP-015; a memory join whose address the active map does not hold is orphaned, kept, and listed by `orphaned`.

The nine commands carry the reference's names, argument shapes and behavior. Given `node`, a read acts on that node's
memories as the reference acts on its whole graph: the entities joined to the node and every relation with an end
among them, CTX-025; a write names an entity anywhere in the graph, and only a name the graph lacks stops it, CTX-022.
Without `node` they act on the whole graph. At a node, memory shows while the layer named memory reaches the node's
address, so select, mask and the folder's --layers turn it off. Any agent may change or delete any memory, unless the
person has locked it: a locked memory is read by all and changed by none, CTX-023.

Each node also holds one note, of at most 2048 characters, the person's: only the web page writes it, and agents read
it; it never expires.

A memory joined at a node takes the next number of that address's counter, the receiver's for a join of the map, kept
on its join, MCP-037; a new memory carries a short title and why, kept on its entity, and an agent's write without them
is refused naming which. `item_read` serves one by its number, `<address>#<n>`, with the memories it is related to.

What the memory layer held before this graph, observations, relations and the person's notes, is carried into the
graph and the notes once, by each command, and left where it was.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from importlib import resources
from typing import Any, cast

from metaform import prompt_files
from metaform.data import Column, Index, Item, Node, Store, StoreError, Table, Tables, TableTx, prompts, reference
from metaform.module import (
    Context,
    Count,
    Module,
    Noun,
    Pane,
    Provides,
    Stop,
    Subscription,
    ToolbarItem,
    Verb,
    agent_caller,
    first_line,
    titled,
)

from . import delivery
from .citations import Checker, root_of, stamp
from .watch import WATCH_OS, watch, web_started

SUPPORTED_OS = ('linux', 'macos', 'windows')
DEPENDENCIES = ()
SHIPS_DISABLED = False
REMOTE_AGENT = True  # what an agent learns at a node travels back in its working layer

VARIABLE = 'What agents have noted at this node.'
LAYER = 'memory'
NOTE_LIMIT = 2048

# Version 2 keeps no time on entities, observations, relations or joins: an entity's and a relation's `seq` is its place
# in the order they were made. Rows from version 1 take seq 0 and keep the order of their key, before every later one.
# Version 3 adds `by` to observations and joins, who wrote the row; it may be empty, so version 2 still reads and writes
# the tables, STORE-029, and a row written before it, or by version 2's code, has none.
# Version 4 adds `session` and `at` to observations and joins: the agent session that wrote the row and when, so an
# agent told the counts at its node hears which memories the last session there wrote, MCP-039. Both may be empty, so
# versions 2 and 3 still read and write the tables, and a row they write, or one written before, names no session.
# Version 5 adds an entity's `title` and `why`, and a join's `number`: the memory's number at the join's receiver
# address, from the project's counter there, MCP-037. All may be empty, so versions 2 to 4 still read and write the
# tables; the upgrade numbers the joins already held in the order they were made and titles each entity from the first
# line of its first observation. A join written by older code has no number.
# Version 6 adds the citations table: the evidence a memory cites, a file and its lines or a symbol, with what they read
# as when it was cited, so a read flags a memory whose evidence changed as stale. Older code does not read the table and
# reads and writes the rest as before.
# Version 7 adds an entity's `locked_by` and `locked_at`, empty while it is unlocked, CTX-023: a locked memory is read
# by every agent and changed by none. Older code would write past a lock it does not know, so it no longer opens the
# tables: compatible_from rises to 7, STORE-029. Every memory already held is unlocked.
# Version 8 adds a citation's `stale`, `checked_size` and `checked_mtime`: whether it holds, worked out by the citation
# watcher each time its file changes, and the file's size and time it was worked out against, so a read looks it up.
# All may be empty, a citation is then as it was cited, so version 7 still reads and writes the tables.
# Version 9 adds functional-entry revisions/encounters and withdrawn identities. Earlier writers do not maintain
# those revisions, so they must not write past the new unread-delivery contract.
# Version 10 indexes withdrawals by the identity they withdraw, so a write reads only its own memories' withdrawals. The
# upgrade applies delivery.remade to every memory held: a withdrawal of a memory deleted and made again before version
# 10, which notices and reads at two nodes passed back and forth, is dropped or made an index withdrawal. Version 9
# reads and writes the tables as before.
TABLES_VERSION = 10


def _upgrade(tx: TableTx, found: int) -> None:
    """Version 5: number every memory join at its receiver's address in the order the joins were made, those kept
    before joins had times first in the order of their entities, and title each entity from its first observation.
    Version 10: no memory that exists keeps a withdrawal under its own identity, delivery.remade."""
    if found < 10:
        delivery.remade(tx, [str(row['name']) for row in tx.rows('entities', limit=0).results])
    if found >= 5:
        return
    entities = {row['name']: row for row in tx.rows('entities', limit=0).results}
    first: dict[str, Row] = {}
    for row in tx.rows('observations', limit=0).results:
        held = first.get(row['entity'])
        if held is None or row['seq'] < held['seq']:
            first[row['entity']] = row
    for name in entities:
        title = first_line(first[name]['content'], 0) if name in first else None
        if title:
            tx.update('entities', {'name': name}, {'title': title})
    joins = list(tx.rows('joins', limit=0).results)
    joins.sort(key=lambda row: (row['at'] is not None, row['at'] or '',
                                entities[row['entity']]['seq'] if row['entity'] in entities else 0, row['join_id']))
    for row in joins:
        tx.update('joins', {'join_id': row['join_id']}, {'number': tx.number(row['receiver'])})


TABLES = Tables(version=TABLES_VERSION, compatible_from=9, upgrade=_upgrade, tables=(
    Table('entities', place='project', key=('name',),
          columns=(Column('name', required=True), Column('entity_type', required=True),
                   Column('seq', 'int', required=True, default=0), Column('title'), Column('why'),
                   Column('locked_by'), Column('locked_at')),
          indexes=(Index(('seq',)),)),
    Table('observations', place='project', key=('entity', 'content'),
          columns=(Column('entity', required=True), Column('content', required=True),
                   Column('seq', 'int', required=True), Column('by'), Column('session'), Column('at')),
          indexes=(Index(('entity', 'seq')),)),
    Table('relations', place='project', key=('source', 'target', 'relation_type'),
          columns=(Column('source', required=True), Column('target', required=True),
                   Column('relation_type', required=True), Column('seq', 'int', required=True, default=0)),
          indexes=(Index(('target',)), Index(('seq',)))),
    Table('joins', place='project', key=('join_id',),
          columns=(Column('join_id', required=True), Column('entity', required=True),
                   Column('receiver', required=True), Column('provider', required=True, default=''), Column('by'),
                   Column('session'), Column('at'), Column('number', 'int')),
          indexes=(Index(('entity', 'receiver', 'provider'), unique=True), Index(('receiver', 'provider')),
                   Index(('provider',)), Index(('receiver', 'number')))),
    Table('notes', place='project', key=('receiver', 'provider'),
          columns=(Column('receiver', required=True), Column('provider', required=True, default=''),
                   Column('text', required=True), Column('by'), Column('at', required=True))),
    Table('carried', place='project', key=('item_id',),
          columns=(Column('item_id', required=True), Column('at', required=True))),
    Table('citations', place='project', key=('entity', 'cite'),
          columns=(Column('entity', required=True), Column('cite', required=True), Column('path', required=True),
                   Column('start', 'int'), Column('end', 'int'), Column('symbol'), Column('digest'),
                   Column('size', 'int'), Column('mtime', 'int'), Column('at'), Column('stale'),
                   Column('checked_size', 'int'), Column('checked_mtime', 'int')),
          indexes=(Index(('entity',)),)),
    *delivery.TABLES,
))

Row = dict[str, Any]
# The nouns that name a node by address, MAP-005, as refine names what it changes.
NAMING = ('receiver', 'provider', 'address')


def _now() -> str:
    return datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


# ------------------------------------------------------------------------------------------------ nodes and keys

@dataclass(frozen=True)
class Key:
    """A node's namespace address: an element's address, or a map join's receiver and provider addresses. `address`
    is where the node sits, for the layers that reach it."""
    receiver: str
    provider: str = ''

    @property
    def address(self) -> str:
        return self.receiver

    def said(self) -> dict[str, str]:
        return {'receiver': self.receiver, 'provider': self.provider} if self.provider else {'address': self.receiver}


def _join_key(store: Store, node: Node) -> Key | None:
    """A map join's two ends: its receiver and the first element it holds."""
    ends = store.join_ends(node.id)
    return None if ends is None else Key(*ends)


def _key_of(store: Store, node: Node) -> Key | None:
    if node.kind == 'element':
        found = store.element(node.id, raw=True)
        return Key(found.address) if found is not None and found.address else None
    if node.kind == 'join':
        return _join_key(store, node)
    return None


def _key(store: Store, text: str) -> Key:
    """The key of the node a command names, which must be a node of the active map. A bare address names the element
    at it, as every command names things the way an agent reads them, MAP-005."""
    if ':' not in text:
        text = f'element:{text}'
    try:
        node = Node.parse(text)
    except StoreError:
        raise Stop(f'{text!r} is not a node: name an element by address, or a purpose by receiver and '
                   'provider.', 'metaform help memory read_graph') from None
    if node.kind == 'type':
        raise Stop('Memory is kept at an element or a join, not at a bare type address.',
                   f'metaform memory read_graph node=element:{node.id}')
    if store.active_base() is None:
        raise Stop(f'{text} is not a node here: the project has no metaform.', 'metaform memory orphaned')
    key = _key_of(store, node)
    if key is None:
        raise Stop(f'{text} is not a node of the map here.', 'metaform map where')
    return key


class _Map:
    """Whether the active map holds an address key, read once per key."""

    def __init__(self, store: Store) -> None:
        self.store = store
        self.active = store.active_base() is not None
        self._held: dict[tuple[str, str], bool] = {}

    def holds(self, key: Key) -> bool:
        found = (key.receiver, key.provider)
        if found not in self._held:
            self._held[found] = self.active and self._holds(key)
        return self._held[found]

    def _holds(self, key: Key) -> bool:
        if self.store.element(key.receiver, raw=True) is None:
            return False
        if not key.provider:
            return True
        joins = self.store.joins(key.receiver, 'receiver', raw=True, limit=0).results
        return any(held.address == key.provider for join in joins for held in join.elements)


# ------------------------------------------------------------------------------------------------ the memory layer

def _memory(store: Store, *, create: bool) -> str | None:
    """The memory layer's name, found by its kind, LAYER-012; made on the first write when the project has a
    metaform, so a memory write never makes one."""
    found = store.layers(kind='memory', limit=0).results
    if found:
        return found[0].name
    if not create or store.active_base() is None:
        return None
    return store.layer(LAYER, 'memory', VARIABLE, kind='memory', mutable=True, hideable=True, ready=True).name


def _reaches(store: Store, address: str) -> bool:
    """Whether memory shows at an address: the memory layer reaches it, with select, mask, hiding and the toggled
    layers; with no memory layer, or no metaform, unless the toggled layers leave memory out."""
    layer = _memory(store, create=False) if store.active_base() is not None else None
    if layer is None:
        return not store.toggled or LAYER in store.toggled
    return layer in store.effective_selection(address).layers


# ------------------------------------------------------------------------------------------------ the graph

@dataclass
class Graph:
    """The memory graph as read in one transaction: entities in the order they were made, each one's observations in
    the order they were added, and relations in the order they were made."""
    entities: dict[str, Row] = field(default_factory=dict[str, Row])
    observations: dict[str, list[Row]] = field(default_factory=dict[str, list[Row]])
    relations: list[Row] = field(default_factory=list[Row])
    citations: dict[str, list[Row]] = field(default_factory=dict[str, list[Row]])
    checker: Checker | None = None  # set by a read, so each memory it gives says which of its citations are stale

    @classmethod
    def read(cls, tx: TableTx, checker: Checker | None = None, names: list[str] | None = None) -> Graph:
        graph = cls(checker=checker)
        def rows(table: str, column: str) -> Any:
            return (tx.rows(table, limit=0).results if names is None
                    else tx.rows_in(table, column, names))
        for row in rows('citations', 'entity'):
            graph.citations.setdefault(row['entity'], []).append(row)
        for row in sorted(rows('entities', 'name'), key=lambda row: row['seq']):
            graph.entities[row['name']] = row
            graph.observations[row['name']] = []
        for row in rows('observations', 'entity'):
            graph.observations.setdefault(row['entity'], []).append(row)
        for observations in graph.observations.values():
            observations.sort(key=lambda row: row['seq'])
        incident = rows('relations', 'source')
        if names is not None:
            incident = [*incident, *tx.rows_in('relations', 'target', names)]
        graph.relations = sorted({(row['source'], row['target'], row['relation_type']): row
                                  for row in incident}.values(),
                                 key=lambda row: (row['seq'], row['source'], row['target'], row['relation_type']))
        return graph

    def entity(self, name: str) -> dict[str, Any]:
        row = self.entities[name]
        said: dict[str, Any] = {'name': name, 'entityType': row['entity_type'],
                                'observations': [one['content'] for one in self.observations.get(name, [])]}
        cited = self.citations.get(name)
        if cited:
            said['cites'] = [one['cite'] for one in cited]
            stale = self.stale(name)
            if stale:
                said['stale'] = stale
        return said

    def stale(self, name: str) -> list[str]:
        """Each citation of the memory whose evidence no longer holds, with why, as `<cite>: <why>`; empty when every
        one holds or the read checks none."""
        if self.checker is None:
            return []
        found = [(one['cite'], self.checker.held(one)) for one in self.citations.get(name, [])]
        return [f'{cite}: {why}' for cite, why in found if why]

    def cite(self, tx: TableTx, name: str, rows: list[Row], written: Row | None = None) -> bool:
        """Keep the citations a write gives for the memory, each once. A citation given again is kept as its file
        reads now, so a memory re-cited after its evidence changed is no longer stale; an updated one is given under
        its new path or lines. Whether any citation was written."""
        kept = self.citations.setdefault(name, [])
        held = {one['cite']: at for at, one in enumerate(kept)}
        wrote = False
        for row in rows:
            at = held.get(row['cite'])
            if at is None:
                held[row['cite']] = len(kept)
                kept.append(tx.insert('citations', {'entity': name, **row, 'at': (written or {}).get('at')}))
                wrote = True
                continue
            fields = ('path', 'start', 'end', 'symbol', 'digest', 'size', 'mtime')
            if all(kept[at].get(one) == row.get(one) for one in fields) and kept[at].get('stale') is None:
                continue  # as it was cited
            restamped = {**{one: row.get(one) for one in fields}, 'at': (written or {}).get('at'), 'stale': None,
                         'checked_size': None, 'checked_mtime': None}
            kept[at] = tx.update('citations', {'entity': name, 'cite': row['cite']}, restamped) or kept[at]
            wrote = True
        return wrote

    def locked(self, name: str) -> bool:
        """Whether the memory is locked, CTX-023: read by every agent, changed by none."""
        return bool((self.entities.get(name) or {}).get('locked_at'))

    @staticmethod
    def relation(row: Row) -> dict[str, Any]:
        return {'from': row['source'], 'to': row['target'], 'relationType': row['relation_type']}

    def made(self, tx: TableTx, name: str, kind: str, title: str | None = None, why: str | None = None) -> None:
        """A new entity, after every entity the graph holds, with its title and why when given."""
        seq = max((row['seq'] for row in self.entities.values()), default=0) + 1
        self.entities[name] = tx.insert('entities', {'name': name, 'entity_type': kind, 'seq': seq, 'title': title,
                                                     'why': why})
        self.observations[name] = []

    def title(self, name: str) -> str:
        """What a memory is called where it is listed by number: its title, else its first observation's first line,
        else its name."""
        row = self.entities.get(name) or {}
        held = self.observations.get(name) or []
        return row.get('title') or (first_line(held[0]['content'], 0) if held else None) or name

    def related(self, tx: TableTx, source: str, target: str, kind: str) -> None:
        """A new relation, after every relation the graph holds."""
        seq = max((row['seq'] for row in self.relations), default=0) + 1
        self.relations.append(tx.insert('relations', {'source': source, 'target': target, 'relation_type': kind,
                                                      'seq': seq}))


@dataclass
class View:
    """The graph an operation sees: the whole graph, or a node's memories and every relation with at least one end
    among them, so a relation across Addresses shows from both of its ends, CTX-025."""
    graph: Graph
    names: list[str]

    @property
    def known(self) -> set[str]:
        return set(self.names)

    def relations(self) -> list[Row]:
        known = self.known
        return [row for row in self.graph.relations if row['source'] in known or row['target'] in known]

    def whole(self) -> dict[str, Any]:
        return {'entities': [self.graph.entity(name) for name in self.names],
                'relations': [Graph.relation(row) for row in self.relations()]}

    def index(self, names: set[str] | None = None) -> list[Row]:
        """Titles and one-line reasons for discovery, never canonical bodies or body receipts."""
        return [{'name': name, 'entityType': self.graph.entities[name]['entity_type'],
                 'title': (first_line(self.graph.title(name), 0) or name)[:160],
                 'why': (first_line(self.graph.entities[name].get('why') or
                                    next((one['content'] for one in self.graph.observations.get(name, [])), ''), 0)
                         or '')[:160]}
                for name in self.names if names is None or name in names]

    def around(self, chosen: list[str]) -> dict[str, Any]:
        """The chosen entities, and every relation with at least one end among them, as the reference returns."""
        picked = set(chosen)
        return {'entities': [self.graph.entity(name) for name in chosen],
                'relations': [Graph.relation(row) for row in self.relations()
                              if row['source'] in picked or row['target'] in picked]}


def _joined(tx: TableTx, key: Key) -> list[Row]:
    return list(tx.rows('joins', {'receiver': key.receiver, 'provider': key.provider}, limit=0).results)


def _changed(ctx: Context, tx: TableTx, names: list[str], removed: list[Row] | None = None) -> None:
    """A graph mutation reaches every functional index of its affected memories, including incident relations, for
    every session there but the one that wrote it."""
    keys = {(str(row['receiver']), str(row['provider'])) for name in dict.fromkeys(names)
            for row in tx.rows('joins', {'entity': name}, limit=0).results}
    if removed is None:
        delivery.remade(tx, names)
    delivery.changed(tx, keys, removed, ctx.session)


def _bodies(ctx: Context, graph: Graph, names: list[str]) -> list[Row]:
    """The memories' canonical bodies as delivery receipts them, for `delivery.authored`: their citations checked, as
    a read and a notice check them, so a memory with a stale citation is the same body in each."""
    if graph.checker is None:
        graph.checker = Checker(ctx)
    return [delivery.component('entities', graph.entity(name)) for name in dict.fromkeys(names)
            if name in graph.entities]


def _view(tx: TableTx, key: Key | None, checker: Checker | None = None,
          names: list[str] | None = None) -> View:
    if key is not None:
        joined = [str(row['entity']) for row in _joined(tx, key)]
        selected = set(names) if names is not None else None
        names = [name for name in joined if selected is None or name in selected]
    graph = Graph.read(tx, checker, names)
    return View(graph, list(graph.entities))


def _by(ctx: Context) -> str | None:
    """Who writes, kept on each join and observation a write makes, so a dispatcher can tell whether its session
    recorded at its nodes and the page can show who recorded a memory: the session the serving process runs for,
    METAFORM_SESSION, or else the MCP client that called. A write from the page is the person's whatever session
    started its server, so it names no one; neither does a command line with no session."""
    if ctx.surface == 'web':
        return None
    return os.environ.get('METAFORM_SESSION') or ctx.client or None


def _written(ctx: Context) -> Row:
    """What a write keeps of who made it: `by`, the agent session that wrote it and when, MCP-039. The page's writes
    are the person's and name no session."""
    return {'by': _by(ctx), 'session': None if ctx.surface == 'web' else ctx.session, 'at': _now()}


def _join(tx: TableTx, entity: str, key: Key, written: Row | None = None) -> int | None:
    """Join the entity to the node, with the next number at the node's address, the receiver's for a join of the map,
    MCP-037; returns that number. A join already there is kept as it is, with who made it and its number."""
    held = tx.rows('joins', {'entity': entity, 'receiver': key.receiver, 'provider': key.provider}).results
    if held:
        return None
    number = tx.number(key.address)
    tx.insert('joins', {'join_id': uuid.uuid4().hex, 'entity': entity, 'receiver': key.receiver,
                        'provider': key.provider, 'number': number, **(written or {})})
    return number


def _observe(tx: TableTx, graph: Graph, entity: str, contents: list[str], written: Row | None = None) -> list[str]:
    """Add each content the entity does not hold yet, in order, kept with who wrote it; returns those added."""
    held = graph.observations.setdefault(entity, [])
    added: list[str] = []
    for content in contents:
        if any(one['content'] == content for one in held):
            continue
        row = tx.insert('observations', {'entity': entity, 'content': content,
                                         'seq': (held[-1]['seq'] + 1) if held else 1, **(written or {})})
        held.append(row)
        added.append(content)
    return added


# One observation is one fact, so it can be read, cited, marked stale and corrected alone (step 5c of the memory
# prompt). The check is mechanical, never a judgement of what the fact says: text in backticks or double quotes is
# left as written, and outside it a line break, a semicolon or a second sentence marks a second fact. A sentence ends
# at . ! or ? followed by a space and a capital or a digit, after a word that is not a common abbreviation.
_QUOTED = re.compile(r'`[^`]*`|"[^"]*"|“[^”]*”')
_SENTENCE_END = re.compile(r'(\S*)[.!?]\s+[A-Z0-9]')
_ABBREVIATIONS = frozenset({'e.g', 'i.e', 'cf', 'vs', 'etc', 'approx', 'no', 'mr', 'mrs', 'ms', 'dr', 'st', 'fig'})
OBSERVATION_RULE = ('One fact per observation, in one sentence: a single fact can be read, cited, marked stale and '
                    'corrected alone.')


def _facts(content: str) -> int:
    """How many facts an observation holds, counted by its form: 1 plus each line break, semicolon and sentence end
    outside quoted text."""
    text = _QUOTED.sub('x', content.strip())
    count = 1 + text.count('\n') + text.count(';')
    for found in _SENTENCE_END.finditer(text):
        word = found.group(1).lower().rstrip('.')
        if word in _ABBREVIATIONS or (len(word) == 1 and word.isalpha()):  # e.g. X, or an initial: J. Smith
            continue
        count += 1
    return count


def _one_fact_each(ctx: Context, observations: list[tuple[str, list[str]]]) -> None:
    """Refuse a write whose observations hold more than one fact each, naming every one, before anything is written,
    so the writer splits them and sends the call again, on every surface."""
    compound = [f'{name!r}: {content[:80]!r}' + ('...' if len(content) > 80 else '')
                for name, contents in observations for content in contents if _facts(content) > 1]
    if compound:
        raise Stop(f'{len(compound)} observation(s) hold more than one fact: {"; ".join(compound)}. '
                   f'{OBSERVATION_RULE}',
                   'split each into one observation per fact (no semicolons, line breaks or second sentences) and '
                   'send the same call again')


def _forget(tx: TableTx, graph: Graph, name: str) -> None:
    """Delete an entity with its observations, its citations, every relation touching it and every join of it."""
    tx.delete('citations', {'entity': name})
    tx.delete('observations', {'entity': name})
    tx.delete('relations', {'source': name})
    tx.delete('relations', {'target': name})
    tx.delete('joins', {'entity': name})
    tx.delete('entities', {'name': name})
    graph.entities.pop(name, None)
    graph.observations.pop(name, None)
    graph.citations.pop(name, None)
    graph.relations = [row for row in graph.relations if name not in (row['source'], row['target'])]


# ------------------------------------------------------------------------------------------------ carrying over

def _text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _entity_name(key: Key) -> str:
    return f'{key.receiver} -> {key.provider}' if key.provider else key.receiver


def _carry(store: Store) -> None:
    """Carry what the memory layer held before this graph into it once: an observation becomes an observation of an
    entity named by its node's address and joined to it, a relation a relation between two such entities, and a
    person's note the node's note. Each item is carried once and left where it was. An item whose node the active map
    does not hold waits until it does."""
    if store.active_base() is None:
        return
    layer = _memory(store, create=False)
    if layer is None:
        return
    items = [item for item in store.layer_items(layer, limit=0).results if isinstance(item, Item)]
    if not items:
        return
    with store.tables(write=False) as tx:
        carried = {row['item_id'] for row in tx.rows('carried', limit=0).results}
    pending = [item for item in items if item.id not in carried]
    if not pending:
        return
    keyed: list[tuple[Item, Key, Key | None]] = []
    for item in pending:
        key = _key_of(store, item.target)
        linked = _key_of(store, item.link) if item.link is not None else None
        if key is None or (item.link is not None and linked is None):
            continue
        keyed.append((item, key, linked))
    if not keyed:
        return
    with store.tables() as tx:
        graph = Graph.read(tx)

        def entity_at(key: Key, kind: str) -> str:
            name = _entity_name(key)
            if name not in graph.entities:
                graph.made(tx, name, kind)
            _join(tx, name, key)
            return name

        for item, key, linked in keyed:
            source = entity_at(key, item.target.kind)
            if item.link is not None and linked is not None:
                target = entity_at(linked, item.link.kind)
                kind = _text(item.value)
                if not any(row['source'] == source and row['target'] == target and row['relation_type'] == kind
                           for row in graph.relations):
                    graph.related(tx, source, target, kind)
            elif (item.extra or {}).get('by') == 'user' and _noted(tx, key, _text(item.value)):
                pass
            else:
                _observe(tx, graph, source, [_text(item.value)])
            tx.insert('carried', {'item_id': item.id, 'at': _now()})


def _noted(tx: TableTx, key: Key, text: str) -> bool:
    """A person's note from the memory layer into the node's one note: the note itself when the node has none, or
    added after it on a line of its own while the whole fits; False when it does not fit, so it is kept as an
    observation instead and nothing is cut."""
    held = tx.get('notes', {'receiver': key.receiver, 'provider': key.provider})
    if held is None:
        if len(text) > NOTE_LIMIT:
            return False
        tx.insert('notes', {'receiver': key.receiver, 'provider': key.provider, 'text': text, 'by': 'user',
                            'at': _now()})
        return True
    if text in held['text'].split('\n'):
        return True
    joined = held['text'] + '\n' + text
    if len(joined) > NOTE_LIMIT:
        return False
    tx.update('notes', {'receiver': key.receiver, 'provider': key.provider}, {'text': joined, 'at': _now()})
    return True


# ------------------------------------------------------------------------------------------------ the nine commands

def _named(store: Store, nouns: dict[str, Any], notices: list[dict[str, str]]) -> Key | None:
    """The key of the node a command names by address, MAP-005: a join by its receiver and an element it holds, an
    element by its address; or the node noun as written. A node noun given beside them is
    named in a notice as not read."""
    if not any(name in nouns for name in NAMING):
        return _key(store, nouns['node']) if nouns.get('node') else None
    if 'node' in nouns:
        notices.append({'where': 'node', 'message': 'receiver, provider and address name the node; node was not read.'})
    if 'receiver' not in nouns and 'provider' not in nouns:
        return _key(store, f"element:{nouns['address']}")
    if store.active_base() is None:
        raise Stop('A purpose is not a node here: the project has no metaform.', 'metaform memory orphaned')
    found = _key_of(store, store.purpose(nouns.get('receiver'), nouns.get('provider'), nouns.get('address')))
    if found is None:
        raise Stop(f"The purpose of {nouns.get('receiver')} served by {nouns.get('provider')} is not a node of the "
                   'map here.', 'metaform map where')
    return found


def _held(store: Store, nouns: dict[str, Any], notices: list[dict[str, str]]) -> Key:
    """The key of the node note names, node first, with provider beside it, the purpose node holds
    as its receiver, and with address the element at that address the join holds, MAP-005."""
    if 'provider' not in nouns:
        if 'address' in nouns:
            notices.append({'where': 'address', 'message': 'address names an element a join holds only with provider; it was not read.'})
        return _key(store, nouns['node'])
    node = str(nouns['node'])
    receiver = node.partition(':')[2] if node.startswith('element:') else node
    found = _named(store, {'receiver': receiver, **{name: nouns[name] for name in ('provider', 'address')
                                                    if name in nouns}}, [])
    assert found is not None  # receiver and provider are given, so _named names a node or stops
    return found


def _scope(ctx: Context, notices: list[dict[str, str]], *, carry: bool = True) -> tuple[Store, Key | None]:
    """The store and the named node; a command that writes first carries what the memory layer held, and one that
    only reads writes nothing, VIEW-011."""
    store = ctx.require_store()
    if carry:
        _carry(store)
    return store, _named(store, ctx.nouns, notices)


class _Given:
    """A command's arguments read in the reference's shapes. A value that should be text and is another JSON value is
    kept as its JSON text and named in `notices`, BASE-044; only an argument that cannot be read stops the call."""

    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self.notices: list[dict[str, str]] = []

    def text(self, value: Any, where: str) -> str:
        if isinstance(value, str):
            return value
        self.notices.append({'where': where, 'message': f'{where} is text; what was sent was kept as its JSON text.'})
        return json.dumps(value, ensure_ascii=False)

    def texts(self, value: Any, where: str) -> list[str]:
        if not isinstance(value, list):
            self.notices.append({'where': where, 'message': f'{where} is an array; what was sent was kept as its '
                                                            'one member.'})
            value = [value]
        return [self.text(one, where) for one in cast(list[Any], value)]

    def objects(self, name: str, fields: tuple[str, ...]) -> list[dict[str, Any]]:
        value = self.ctx.nouns.get(name)
        members = cast(list[Any], value) if isinstance(value, list) else [value]
        found: list[dict[str, Any]] = []
        for one in members:
            if not isinstance(one, dict) or any(field_ not in one for field_ in fields):
                raise Stop(f'Each member of {name} is an object with {", ".join(fields)}.',
                           'metaform help memory')
            found.append(cast(dict[str, Any], one))
        return found

    def said(self, result: dict[str, Any]) -> dict[str, Any]:
        if self.notices:
            result['notices'] = self.notices
        return result


def _not_found(name: str) -> Stop:
    """The reference's refusal of a name the whole memory graph lacks, CTX-022 and CTX-025: a write names an entity
    anywhere in the graph, so the next step searches all of it."""
    return Stop(f'Entity with name {name} not found', f'metaform memory search_nodes {json.dumps(name)}')


def _locked(graph: Graph, names: list[str]) -> list[str]:
    """The named memories that are locked, each once, in the order named, CTX-023."""
    return [name for name in dict.fromkeys(names) if graph.locked(name)]


def _lock_notice(given: _Given, locked: list[str], where: str) -> None:
    """A locked memory a write named is left unchanged and named in a notice, CTX-023."""
    if locked:
        given.notices.append({'where': where, 'message': f'Locked: {", ".join(locked)}. A locked memory is read by '
                                                         'every agent and changed by none; only the person unlocks it.'})


def _layered(store: Store) -> None:
    """The memory layer, made on the first write so the orchestrator can turn memory off, LAYER-012."""
    with store.atomic():
        _memory(store, create=True)


def _titles(ctx: Context, given: _Given, one: dict[str, Any], name: str,
            observations: list[str]) -> tuple[str | None, str | None]:
    """A new memory's title and why, MCP-037. A memory records knowledge, so it carries both; a memory whose first
    observation is one short line may leave out its title, which is that line. Refused on an agent's surface when
    either is missing; from the page, the person's, the title is the first observation's first line."""
    title = given.text(one['title'], 'title').strip() if one.get('title') is not None else None
    why = given.text(one['why'], 'why').strip() if one.get('why') is not None else None
    if not title and observations:
        title = first_line(observations[0], 0) if ctx.surface == 'web' else first_line(observations[0])
    titled(ctx, f'The memory {name!r}', title, why, why_needed=True,
           why_step='add why: one line saying why this is worth keeping, to each new entity')
    return title or None, why or None


def create_entities(ctx: Context) -> Any:
    given = _Given(ctx)
    store, key = _scope(ctx, given.notices)
    entities = [(one, given.text(one['name'], 'name'), given.text(one['entityType'], 'entityType'),
                 given.texts(one['observations'], 'observations'))
                for one in given.objects('entities', ('name', 'entityType', 'observations'))]
    made: list[dict[str, Any]] = []
    written: list[str] = []
    numbered: list[str] = []
    by = _written(ctx)
    with store.tables() as tx:
        graph = Graph.read(tx)
        # Every new memory's title and why are checked before anything is written, so a refusal writes nothing.
        fresh: dict[str, tuple[str | None, str | None]] = {}
        cited: dict[str, list[Row]] = {}
        for one, name, _, observations in entities:
            if name not in graph.entities and name not in fresh:
                fresh[name] = _titles(ctx, given, one, name, observations)
                cited[name] = _cites(ctx, one)
                _one_fact_each(ctx, [(name, observations)])
        seen: set[str] = set()
        locked = _locked(graph, [name for _, name, _, _ in entities])
        for _, name, kind, observations in entities:
            if name in locked:  # its observations, citations and joins stay as they are, CTX-023
                continue
            if name in graph.entities or name in seen:
                # Canonical create_entities skips existing names. Content extension and functional indexing have
                # their own operations, so a create cannot silently modify existing knowledge.
                continue
            seen.add(name)
            graph.made(tx, name, kind, *fresh[name])
            _observe(tx, graph, name, observations, by)
            graph.cite(tx, name, cited[name], by)
            if key is not None and (number := _join(tx, name, key, by)) is not None:
                numbered.append(f'{reference(key.address, number)}  {graph.title(name)}')
            made.append({'name': name, 'entityType': kind, 'observations': observations})
            written.append(name)
        if written:
            _changed(ctx, tx, written)
    delivery.authored(ctx, _bodies(ctx, graph, written))
    _lock_notice(given, locked, 'entities')
    _layered(store)
    if ctx.surface == 'mcp':  # to an agent, one line: what it just sent is not handed back, MCP-037
        recorded = numbered or [name for name in dict.fromkeys(written)]
        line = (_prompt('recorded', items='; '.join(numbered)) if numbered else
                _prompt('recorded_unjoined', names=', '.join(recorded)) if recorded else _prompt('recorded_nothing'))
        return _line(line, given.notices)
    # Each memory joined at the node by this call, by its number there and its title, so the agent can cite it.
    return given.said({'entities': made, **({'items': numbered} if numbered else {})})


def _cites(ctx: Context, one: dict[str, Any]) -> list[Row]:
    """The citations a write gives for one memory, `cite` as one text or a list, each checked against the project's
    files and kept as `citations.stamp` keeps it; Stop for one that names nothing the project holds."""
    given = one.get('cite')
    if given is None or given == '' or given == []:
        return []
    root = root_of(ctx)
    return [stamp(str(each), root) for each in (cast(list[Any], given) if isinstance(given, list) else [given])]


def _restamped(ctx: Context, graph: Graph, name: str, given: set[str]) -> list[Row]:
    """The memory's whole-file citations as their files read now, besides those the write gives, for a write that adds
    to the memory: its writer saw the file as it is. A cited line span is left as it was, since the same numbers may
    now hold other text, and so is a citation whose file is gone, which stays stale."""
    files = [one for one in graph.citations.get(name, [])
             if one['cite'] not in given and one.get('start') is None and not one.get('symbol')]
    if not files:
        return []
    root = root_of(ctx)
    restamped: list[Row] = []
    for one in files:
        try:
            restamped.append(stamp(str(one['cite']), root))
        except Stop:
            continue
    return restamped


def _prompt(name: str, **fills: str) -> str:
    return prompt_files.module('memory', name, **fills) or ''


def _line(line: str, notices: list[dict[str, str]]) -> str:
    """A write's one line to an agent, then each notice on a line of its own."""
    return '\n'.join([line, *(f"{one['where']}: {one['message']}" for one in notices)])


def _relations(given: _Given) -> list[tuple[str, str, str]]:
    return [(given.text(one['from'], 'from'), given.text(one['to'], 'to'),
             given.text(one['relationType'], 'relationType'))
            for one in given.objects('relations', ('from', 'to', 'relationType'))]


def create_relations(ctx: Context) -> Any:
    """Relate memories wherever each is linked, CTX-025: an end is looked up in the whole graph, and only a name the
    graph lacks stops the call, before anything is written. A relation may touch a locked memory, CTX-023."""
    given = _Given(ctx)
    store, _ = _scope(ctx, given.notices)
    relations = _relations(given)
    made: list[dict[str, Any]] = []
    with store.tables() as tx:
        graph = Graph.read(tx)
        for source, target, _ in relations:
            for end in (source, target):
                if end not in graph.entities:
                    raise _not_found(end)
        held = {(row['source'], row['target'], row['relation_type']) for row in graph.relations}
        for triple in relations:
            if triple in held:
                continue
            held.add(triple)
            graph.related(tx, *triple)
            made.append({'from': triple[0], 'to': triple[1], 'relationType': triple[2]})
        if made:
            _changed(ctx, tx, [str(one[end]) for one in made for end in ('from', 'to')])
    delivery.authored(ctx, [delivery.component('relations', one) for one in made])
    _layered(store)
    if ctx.surface == 'mcp':  # to an agent, one line, MCP-037
        return _line(_prompt('related', count=str(len(made))), given.notices)
    return given.said({'relations': made})


def add_observations(ctx: Context) -> Any:
    """Add observations to memories anywhere in the graph, whoever wrote them, CTX-022: with a node or without, only a
    name the graph lacks stops the call. A locked memory is left as it is and named, CTX-023."""
    given = _Given(ctx)
    store, _ = _scope(ctx, given.notices)
    members = given.objects('observations', ('entityName', 'contents'))
    observations = [(given.text(one['entityName'], 'entityName'), given.texts(one['contents'], 'contents'),
                     _cites(ctx, one)) for one in members]
    results: list[dict[str, Any]] = []
    changed: list[str] = []
    by = _written(ctx)
    with store.tables() as tx:
        graph = Graph.read(tx)
        for name, _, _ in observations:
            if name not in graph.entities:
                raise _not_found(name)
        _one_fact_each(ctx, [(name, contents) for name, contents, _ in observations])
        locked = _locked(graph, [name for name, _, _ in observations])
        earlier = _bodies(ctx, graph, [name for name, _, _ in observations if name not in locked])
        for name, contents, cited in observations:
            if name in locked:
                results.append({'entityName': name, 'addedObservations': []})
                continue
            added = _observe(tx, graph, name, contents, by)
            results.append({'entityName': name, 'addedObservations': added})
            if added:  # written against the files as they read now
                cited = [*cited, *_restamped(ctx, graph, name, {row['cite'] for row in cited})]
            if graph.cite(tx, name, cited, by) or added:
                changed.append(name)
        if changed:
            _changed(ctx, tx, changed)
    delivery.authored(ctx, _bodies(ctx, graph, changed), earlier)
    _lock_notice(given, locked, 'observations')
    _layered(store)
    if ctx.surface == 'mcp':  # to an agent, one line, MCP-037
        added = '; '.join(f"{one['entityName']} +{len(one['addedObservations'])}" for one in results)
        return _line(_prompt('observed', added=added), given.notices)
    return given.said({'results': results})


def _locked_said(locked: list[str]) -> str:
    return f' Locked: {", ".join(locked)}' if locked else ''


def delete_entities(ctx: Context) -> Any:
    """Delete memories anywhere in the graph, whoever wrote them, CTX-022; a locked one is kept and named, CTX-023,
    in the reference's form for a partial delete. A relation goes with its deleted end."""
    given = _Given(ctx)
    store, _ = _scope(ctx, given.notices)
    names = given.texts(ctx.nouns.get('entityNames'), 'entityNames')
    with store.tables() as tx:
        graph = Graph.read(tx)
        locked = _locked(graph, names)
        deleted = [name for name in names if name in graph.entities and name not in locked]
        not_found = [name for name in names if name not in graph.entities]
        incident = [Graph.relation(row) for row in graph.relations
                    if row['source'] in deleted or row['target'] in deleted]
        removed: list[Row] = []
        if deleted:
            removed = [delivery.component('deleted_entities', name, name=delivery.entity_name(name),
                                          requires=delivery.entity_name(name)) for name in dict.fromkeys(deleted)]
            removed += [delivery.component('deleted_relations', row, name=delivery.relation_name(row),
                                           requires=delivery.relation_name(row)) for row in incident]
            _changed(ctx, tx, [*deleted, *(str(row[end]) for row in incident for end in ('from', 'to'))], removed)
        for name in dict.fromkeys(deleted):
            _forget(tx, graph, name)
    delivery.authored(ctx, removed)
    message = ('Entities deleted successfully' if not not_found and not locked else
               f'Deleted {len(deleted)} of {len(names)} entities.' +
               (f' Not found: {", ".join(not_found)}' if not_found else '') + _locked_said(locked))
    return given.said({'success': True, 'message': message})


def delete_observations(ctx: Context) -> Any:
    """Delete observations of memories anywhere in the graph, CTX-022; a locked memory keeps every one, CTX-023."""
    given = _Given(ctx)
    store, _ = _scope(ctx, given.notices)
    deletions = [(given.text(one['entityName'], 'entityName'), given.texts(one['observations'], 'observations'))
                 for one in given.objects('deletions', ('entityName', 'observations'))]
    deleted, requested, missing = 0, 0, list[str]()
    changed: list[str] = []
    with store.tables() as tx:
        graph = Graph.read(tx)
        locked = _locked(graph, [name for name, _ in deletions])
        earlier = _bodies(ctx, graph, [name for name, _ in deletions if name not in locked])
        for name, contents in deletions:
            requested += len(contents)
            if name not in graph.entities:
                missing.append(name)
                continue
            if name in locked:
                continue
            for content in dict.fromkeys(contents):
                count = tx.delete('observations', {'entity': name, 'content': content})
                deleted += count
                if count:
                    changed.append(name)
        if changed:
            _changed(ctx, tx, changed)
            graph = Graph.read(tx)
    delivery.authored(ctx, _bodies(ctx, graph, changed), earlier)
    message = ('Observations deleted successfully' if deleted == requested else
               f'Deleted {deleted} of {requested} observations.' +
               (f' Entities not found: {", ".join(missing)}' if missing else '') + _locked_said(locked))
    return given.said({'success': True, 'message': message})


def delete_relations(ctx: Context) -> Any:
    """Delete relations anywhere in the graph, CTX-022; one that touches a locked memory is kept, CTX-023."""
    given = _Given(ctx)
    store, _ = _scope(ctx, given.notices)
    relations = _relations(given)
    deleted = 0
    removed: list[Row] = []
    with store.tables() as tx:
        graph = Graph.read(tx)
        locked = _locked(graph, [end for source, target, _ in relations for end in (source, target)])
        for source, target, kind in relations:
            if source not in locked and target not in locked:
                count = tx.delete('relations', {'source': source, 'target': target, 'relation_type': kind})
                deleted += count
                if count:
                    row = {'from': source, 'to': target, 'relationType': kind}
                    removed.append(delivery.component('deleted_relations', row, name=delivery.relation_name(row),
                                                       requires=delivery.relation_name(row)))
        if removed:
            _changed(ctx, tx, [str(one['value'][end]) for one in removed for end in ('from', 'to')], removed)
    delivery.authored(ctx, removed)
    message = ('Relations deleted successfully' if deleted == len(relations) else
               f'Deleted {deleted} of {len(relations)} relations.' +
               (_locked_said(locked) if locked else ' The rest matched nothing.'))
    return given.said({'success': True, 'message': message})


def _shown(store: Store, tx: TableTx, names: list[str]) -> list[str]:
    """The whole graph as it shows with the layers in context: an entity joined to nodes shows where memory reaches
    one of their addresses, as at a node; one joined to none shows while memory reaches the root of the namespace."""
    reach: dict[str, bool] = {}

    def reaches(address: str) -> bool:
        if address not in reach:
            reach[address] = _reaches(store, address)
        return reach[address]

    at: dict[str, list[str]] = {}
    for row in tx.rows_in('joins', 'entity', names):
        at.setdefault(row['entity'], []).append(row['receiver'])
    return [name for name in names if any(reaches(address) for address in at.get(name, ['']))]


def _read(ctx: Context, notices: list[dict[str, str]], names: list[str] | None = None) -> View | None:
    store, key = _scope(ctx, notices, carry=False)
    if key is not None and not _reaches(store, key.address):
        return None
    checker = Checker(ctx)  # a read says which citations no longer hold
    with store.tables(write=False) as tx:
        if key is not None:
            return _view(tx, key, checker, names)
        if names is None:
            names = [str(row['name']) for row in tx.rows('entities', by=('seq',), limit=0).results]
        return _view(tx, None, checker, _shown(store, tx, names))


EMPTY: dict[str, list[Any]] = {'entities': [], 'relations': []}


def _delivered(ctx: Context, whole: Row, key: Key | None = None) -> Row:
    """A canonical graph read records the exact bodies returned."""
    if ctx.session is None:
        return whole
    if key is None:
        key = _named(ctx.require_store(), ctx.nouns, [])
    prepared = delivery.prepare(ctx, whole, (key.receiver, key.provider) if key else None)
    if key is None:
        # An inspection by identity still encounters the returned memories through their functional indexes.
        # Keeping those entry points lets a later correction reach this reader without a global memory inbox.
        names = {str(one['name']) for one in whole.get('entities', [])}
        store = ctx.require_store()
        with store.tables(write=False) as tx:
            keys = {(str(row['receiver']), str(row['provider']))
                    for row in tx.rows_in('joins', 'entity', list(names))}
        for entry in sorted(keys):
            if _reaches(store, entry[0]):
                delivery.encounter(ctx, entry, epoch=int(prepared['epoch']))
    delivery.queue(ctx, prepared, all_current=True)
    return whole


def read_graph(ctx: Context) -> Any:
    given = _Given(ctx)
    view = _read(ctx, given.notices)
    return given.said(dict(EMPTY) if view is None else _delivered(ctx, view.whole()))


def _index(ctx: Context, view: View, key: Key | None = None) -> Row:
    """Discovery leaves body receipts untouched, including memories changed only through a relation."""
    if ctx.session is None:
        return {'entities': view.index(), 'relations': []}
    if key is None:
        key = _named(ctx.require_store(), ctx.nouns, [])
    prepared = delivery.prepare(ctx, view.whole(), (key.receiver, key.provider) if key else None)
    _, unread, _ = delivery.counts(prepared)
    removed = [one for one in prepared['components'] if one['kind'] not in ('entities', 'relations')]
    result: Row = {'entities': view.index(unread), 'relations': []}
    for one in removed:
        if one.get('reference'):
            result.setdefault('restored', []).append(one['reference'])
        else:
            result.setdefault(one['kind'], []).append(one['value'])
    delivery.queue(ctx, {**prepared, 'components': removed})
    return result


def read_unread(ctx: Context) -> Any:
    """List unread titles and one-line reasons; open_nodes reads selected bodies."""
    given = _Given(ctx)
    view = _read(ctx, given.notices)
    found = dict(EMPTY) if view is None else _index(ctx, view)
    refine = ctx.calls(_prompt('refine')) if found.get('entities') else ''
    if refine:  # reading what is new at a node is the moment to tidy what is there, as the arrival line asks
        given.notices.append({'where': 'refine', 'message': refine})
    return given.said(found)


def search_nodes(ctx: Context) -> Any:
    given = _Given(ctx)
    wanted = given.text(ctx.nouns.get('query'), 'query').lower()
    view = _read(ctx, given.notices)
    if view is None:
        return given.said(dict(EMPTY))
    chosen = [name for name in view.names
              if wanted in name.lower() or wanted in view.graph.entities[name]['entity_type'].lower()
              or any(wanted in one['content'].lower() for one in view.graph.observations.get(name, []))]
    return given.said(_delivered(ctx, view.around(chosen)))


def open_nodes(ctx: Context) -> Any:
    given = _Given(ctx)
    names = given.texts(ctx.nouns.get('names'), 'names')
    view = _read(ctx, given.notices, names)
    if view is None:
        return given.said(dict(EMPTY))
    return given.said(_delivered(ctx, view.around([name for name in view.names if name in names])))


# ------------------------------------------------------------------------------------------------ joins and notes

def _join_said(row: Row, held: bool) -> dict[str, Any]:
    return {'join_id': row['join_id'], 'entity': row['entity'],
            **Key(row['receiver'], row['provider']).said(), 'by': row['by'], 'orphaned': not held}


def joins(ctx: Context) -> Any:
    """The joins of type memory, at a node or of an entity, or all of them, each with whether it is orphaned."""
    store = ctx.require_store()
    notices: list[dict[str, str]] = []
    key, entity = _named(store, ctx.nouns, notices), ctx.nouns.get('entity')
    with store.tables(write=False) as tx:
        if key is not None:
            found = _joined(tx, key)
        elif entity:
            found = list(tx.rows('joins', {'entity': entity}, limit=0).results)
        else:
            found = list(tx.rows('joins', by=('receiver', 'provider'), limit=0).results)
    if key is not None and entity:
        found = [row for row in found if row['entity'] == entity]
    mapped = _Map(store)
    said: dict[str, Any] = {'joins': [_join_said(row, mapped.holds(Key(row['receiver'], row['provider'])))
                                      for row in found]}
    if notices:
        said['notices'] = notices
    return said


def join(ctx: Context) -> Any:
    """Index existing knowledge at another functional entry without duplicating or changing its entity."""
    given = _Given(ctx)
    store = ctx.require_store()
    key = _named(store, ctx.nouns, given.notices)
    if key is None:
        raise Stop('A memory index association names its functional element or join.',
                   'metaform memory join <entity> node=element:<address>')
    name = given.text(ctx.nouns.get('entity'), 'entity')
    with store.tables() as tx:
        graph = Graph.read(tx)
        if name not in graph.entities:
            raise _not_found(name)
        if graph.locked(name):
            raise Stop(f'Locked: {name}. Its functional indexes stay as they are.',
                       f'ask the person to unlock it: metaform memory unlock {json.dumps(name)}')
        number = _join(tx, name, key, _written(ctx))
        if number is not None:
            delivery.changed(tx, {(key.receiver, key.provider)})
    _layered(store)
    return given.said({'entity': name, **key.said(), 'joined': number is not None,
                       **({'item': reference(key.address, number)} if number is not None else {})})


def orphaned(ctx: Context) -> Any:
    """The memory joins whose address the active map does not hold, with what each was attached to, for the orphaned
    menu; they are kept, and a new intake that holds the address reconnects them."""
    store = ctx.require_store()
    with store.tables(write=False) as tx:
        found = list(tx.rows('joins', by=('receiver', 'provider'), limit=0).results)
    mapped = _Map(store)
    return {'joins': [_join_said(row, False) for row in found
                      if not mapped.holds(Key(row['receiver'], row['provider']))]}


def unjoin(ctx: Context) -> Any:
    """Take one memory join away by its id, an orphaned one included; the entity stays in the graph."""
    store = ctx.require_store()
    withdrawal: Row | None = None
    with store.tables() as tx:
        held = tx.get('joins', {'join_id': ctx.nouns['id']})
        name = str(held['entity']) if held is not None else ''
        entity = tx.get('entities', {'name': name}) if held is not None else None
        if entity is not None and entity.get('locked_at'):  # a locked memory keeps its joins, CTX-023
            raise Stop(f'Locked: {name}. A locked memory is read by every agent and changed by none; its join stays.',
                       f'ask the person to unlock it: metaform memory unlock {json.dumps(name)}')
        if held is not None:
            withdrawal = delivery.component('withdrawn', {'name': name, **Key(held['receiver'], held['provider']).said()},
                                             name=f'memory:index:{held["join_id"]}',
                                             requires=delivery.entity_name(name))
            delivery.changed(tx, {(held['receiver'], held['provider'])}, [withdrawal], writer=ctx.session)
        deleted = tx.delete('joins', {'join_id': ctx.nouns['id']})
    if withdrawal is not None:
        delivery.authored(ctx, [withdrawal])
    return {'deleted': deleted}


def rekey(ctx: Context) -> Any:
    """Transfer memory attachments and notes at an exact address, including either end of a map join. The old
    address may already be absent from the map; existing unique keys make a collision roll the whole transfer back. A
    memory whose address changes takes the next number at the new one, MCP-037; its old number is not reused. A locked
    memory's joins stay where they are and are named, CTX-023."""
    return _rekey(ctx.require_store(), str(ctx.nouns['old']), str(ctx.nouns['new']))


def _rekey(store: Store, old: str, new: str, *, merge: bool = False) -> dict[str, Any]:
    """Move the memory joins and notes at `old` to `new`. A collision rolls the whole transfer back, unless `merge`:
    an element of the map merged into another keeps one join of a memory already joined at both, and the two notes
    joined as paragraphs, so a merge orphans nothing and copies nothing."""
    counts = {'joins': 0, 'notes': 0}
    locked: list[str] = []
    if old != new:
        with store.tables() as tx:
            held = {row['name'] for row in tx.rows('entities', limit=0).results if row.get('locked_at')}
            for table, key in (('joins', ('join_id',)), ('notes', ('receiver', 'provider'))):
                for row in tx.rows(table, limit=0).results:
                    changes: dict[str, Any] = {end: new for end in ('receiver', 'provider') if row[end] == old}
                    if not changes:
                        continue
                    if table == 'joins' and row['entity'] in held:
                        locked.append(row['entity'])
                        continue
                    where = {name: row[name] for name in key}
                    moved = {end: changes.get(end, row[end]) for end in ('receiver', 'provider')}
                    if merge and table == 'joins' and tx.rows('joins', {'entity': row['entity'], **moved},
                                                              limit=1).results:
                        tx.delete('joins', where)  # the memory is joined at the element it was merged into already
                        counts[table] += 1
                        continue
                    if merge and table == 'notes' and (kept := tx.get('notes', moved)) is not None:
                        tx.update('notes', moved, {'text': f"{kept['text']}\n\n{row['text']}"})
                        tx.delete('notes', where)
                        counts[table] += 1
                        continue
                    if table == 'joins' and 'receiver' in changes:  # moved to a new address, it takes its next number
                        changes['number'] = tx.number(new)
                    try:
                        tx.update(table, where, changes)
                    except StoreError as error:  # the destination already holds this key; the transaction rolls back
                        said = f'join of {row["entity"]}' if table == 'joins' else 'note'
                        first = (f'unjoin one of the two joins metaform memory joins entity={row["entity"]} lists'
                                 if table == 'joins' else f'clear the note at {new} on the web page once what it '
                                                          'holds is kept')
                        raise Stop(f'{new} already holds a memory {said} that this one would replace: {error} '
                                   'Nothing was changed.', f'{first}, then run metaform memory rekey {old} {new} '
                                                           'again') from None
                    counts[table] += 1
    return {'old': old, 'new': new, **counts, **({'locked': list(dict.fromkeys(locked))} if locked else {})}


def map_moved(payload: dict[str, Any], ctx: Context) -> dict[str, Any]:
    """An element of the map renamed or merged into another, `map.moved` from `map refine to_address=`: its memories
    go with it, so none is orphaned at the address the map no longer holds and none is copied, LAYER-025."""
    old, new = str(payload.get('old') or ''), str(payload.get('new') or '')
    if not old or not new:
        return {'said': ''}
    moved = _rekey(ctx.require_store(), old, new, merge=True)
    said = f"{moved['joins']} memory joins and {moved['notes']} notes moved to {new}."
    if moved.get('locked'):
        said += f" Locked memories stay at {old}: {', '.join(moved['locked'])}; the person moves them."
    return {**moved, 'said': said}


def graph(ctx: Context) -> Any:
    """The whole graph with every join, for a browser of it. Each join also says whether its entity shows at its node
    as a read of the node shows it: the join is not orphaned and memory reaches the node's address in the call's
    layers, VIEW-031."""
    store = ctx.require_store()
    with store.tables(write=False) as tx:
        whole = Graph.read(tx)
        rows = list(tx.rows('joins', by=('receiver', 'provider'), limit=0).results)
    mapped = _Map(store)
    reach: dict[str, bool] = {}

    def said(row: Row) -> dict[str, Any]:
        key = Key(row['receiver'], row['provider'])
        held = mapped.holds(key)
        if held and key.address not in reach:
            reach[key.address] = _reaches(store, key.address)
        return {**_join_said(row, held), 'shows': held and reach[key.address]}
    return {'entities': [{'name': name, 'entityType': row['entity_type'],
                          'observations': [{'content': one['content'], 'by': one['by']}
                                           for one in whole.observations.get(name, [])],
                          **({'locked': _lock_said(row)} if whole.locked(name) else {})}
                         for name, row in whole.entities.items()],
            'relations': [Graph.relation(row) for row in whole.relations],
            'joins': [said(row) for row in rows]}


def _note_said(row: Row | None) -> dict[str, Any] | None:
    return None if row is None else {'text': row['text'], 'by': row['by'], 'at': row['at']}


def person_note(project: str, node: Node) -> str | None:
    """The person's note at a node, whole, or None: what the person wrote there for the agents that work at it,
    offered to other modules as `memory.note`, so a ticket's hand-off carries it, code.graph.knowledge#d. One row
    read."""
    store = Store(project, module='memory')
    if store.active_base() is None:
        return None
    key = _key_of(store, node)
    if key is None:
        return None
    with store.tables(write=False) as tx:
        row = tx.get('notes', {'receiver': key.receiver, 'provider': key.provider})
    return None if row is None else str(row['text'])


def note(ctx: Context) -> Any:
    """The node's one note: read it, or, from the web page only, write it in place of what it held; empty text clears
    it. The note is the person's, not the agents'. An agent reads the note and never writes it."""
    store = ctx.require_store()
    notices: list[dict[str, str]] = []
    key = _held(store, ctx.nouns, notices)
    text = ctx.nouns.get('text')
    where = {'receiver': key.receiver, 'provider': key.provider}
    if text is not None and ctx.surface != 'web':
        raise Stop('The note is written only from the web page.', f'metaform memory note {ctx.nouns["node"]}')
    if text is None:
        with store.tables(write=False) as tx:
            return {**key.said(), 'note': _note_said(tx.get('notes', where)), **({'notices': notices} if notices else {})}
    _carry(store)
    if len(text) > NOTE_LIMIT:
        raise Stop(f'A note holds at most {NOTE_LIMIT} characters; this one has {len(text)}.',
                   f'shorten the note to at most {NOTE_LIMIT} characters and save it again')
    with store.tables() as tx:
        if text == '':
            tx.delete('notes', where)
            return {**key.said(), 'note': None, **({'notices': notices} if notices else {})}
        changes = {'text': text, 'by': ctx.nouns.get('by'), 'at': _now()}
        row = tx.update('notes', where, changes) or tx.insert('notes', {**where, **changes})
    return {**key.said(), 'note': _note_said(row), **({'notices': notices} if notices else {})}


# ------------------------------------------------------------------------------------------------ the lock

def _lock_said(row: Row) -> dict[str, Any]:
    return {'by': row.get('locked_by'), 'at': row.get('locked_at')}


def _set_lock(ctx: Context, locked: bool) -> Any:
    """Lock or unlock one memory, CTX-023. Only the person does, from the page or a command line no agent runs: a
    command an agent runs is known by the identity its runner sets and by the processes that started it,
    `metaform.caller`. Over MCP the verbs are not offered at all."""
    if ctx.surface == 'mcp' or (ctx.surface == 'cli' and agent_caller()):
        raise Stop('Only the person locks and unlocks a memory, from the page or the command line.',
                   'ask the person to do it')
    given = _Given(ctx)
    name = given.text(ctx.nouns['name'], 'name')
    store = ctx.require_store()
    _carry(store)
    with store.tables() as tx:
        if tx.get('entities', {'name': name}) is None:
            raise _not_found(name)
        changes = {'locked_by': 'person', 'locked_at': _now()} if locked else {'locked_by': None, 'locked_at': None}
        row = tx.update('entities', {'name': name}, changes)
    return given.said({'name': name, 'locked': _lock_said(row) if locked and row is not None else None})


def lock(ctx: Context) -> Any:
    return _set_lock(ctx, True)


def unlock(ctx: Context) -> Any:
    return _set_lock(ctx, False)


# ------------------------------------------------------------------------------------------------ the memory prompt

PACKAGE = resources.files(__name__)
PROMPT = 'memory:instructions'
# The Axiom instructions this element held until 2026-10-15, as a version holds them, never sent, CTX-026 and CTX-029.
EARLIER = 'instructions-2026-10-11.axiom'


def _earlier() -> None:
    """Keep the Axiom instructions this element held until 2026-10-15 as its version 1 in the prompt store, once, on a
    home that never served the element, so they stay readable as the earlier version, CTX-026."""
    try:
        prompts.prompt_version(PROMPT)
        return
    except StoreError:
        pass
    try:
        prompts.add_prompt(PROMPT, 'xml', (PACKAGE / 'resources' / EARLIER).read_text(encoding='utf-8'),
                           origin='shipped')
    except StoreError:  # another process kept it first
        pass


def memory_prompt(project: str, address: str | None = None) -> str:
    """The owner's memory prompt, CTX-026, as the prompt store serves it as memory:instructions, so an edit the person
    saved is what is sent, filled as CTX-027 says: {project} with the project's id and {element} with the address of
    the element the agent is assigned. {this} is left alone: it names the subject a prompt or workflow is linked to,
    and an assignment links nothing. With no assigned element, or one the map no longer holds, the bullet that names
    {element} is swapped whole for the instructions_unassigned element. Offered to other modules as `memory.prompt`,
    so dispatch sends it in a worker's first turn, CTX-028."""
    _earlier()
    text = prompt_files.served(PACKAGE, 'instructions').replace('{project}', project)
    if address:
        store = Store(project, module='memory')
        if store.active_base() is not None and store.element(address, raw=True) is not None:
            return text.replace('{element}', address)
    unassigned = prompt_files.served(PACKAGE, 'instructions_unassigned')
    kept: list[str] = []
    for line in text.split('\n'):
        if '{element}' not in line:
            kept.append(line)
        elif unassigned:  # the whole bullet, never words in it
            kept.append(line[:len(line) - len(line.lstrip(' -'))] + unassigned)
    return '\n'.join(kept)


def record(ctx: Context, address: str, entities: list[dict[str, Any]]) -> Any:
    """Another module's own record of what happened at an Address, written as create_entities writes it: each new
    entity joined to the element at `address`, under every rule an agent's write keeps (a title and a why, one fact
    per observation, citations of project files). Offered as `memory.record`, so roundtables keeps a table's outcome
    where it was asked; the writer named on it is the calling module."""
    store = Store(ctx.require_store().project_id, module='memory')
    return create_entities(replace(ctx, module='memory', store=store, client=ctx.client or ctx.module,
                                   nouns={'entities': entities, 'node': f'element:{address}'}))


# ------------------------------------------------------------------------------------------------ the node read

def node_read(ctx: Context, node: Node) -> Any:
    """What memory adds to the read of a node, BASE-035: its note, and while memory shows at the node, the entities
    joined to it with the relations between them, and for an element, the memories on the joins it receives and
    provides."""
    store = ctx.store
    if store is None or store.active_base() is None:
        return None
    key = _key_of(store, node)
    if key is None:
        return None
    found: dict[str, Any] = {}
    shows = _reaches(store, key.address)
    around: dict[tuple[str, str], list[str]] = {}
    with store.tables(write=False) as tx:
        held = _note_said(tx.get('notes', {'receiver': key.receiver, 'provider': key.provider}))
        if held is not None:
            found['note'] = held
        if not shows:
            return found or None
        names = [str(row['entity']) for row in _joined(tx, key)]
        if node.kind == 'element':
            for row in [*tx.rows('joins', {'receiver': key.receiver}, by=('receiver', 'provider'), limit=0).results,
                        *tx.rows('joins', {'provider': key.receiver}, limit=0).results]:
                if row['provider']:
                    around.setdefault((row['receiver'], row['provider']), []).append(row['entity'])
        graph = Graph.read(tx, Checker(ctx), list(dict.fromkeys(
            [*names, *(name for members in around.values() for name in members)])))
        view = View(graph, [name for name in graph.entities if name in names])
    shown = _index(ctx, view, key) if ctx.session is not None else _delivered(ctx, view.whole(), key)
    if any(shown.values()):
        found.update(shown)
    sent: set[str] = {str(one['name']) for one in shown.get('entities', [])} if ctx.session is not None else set()
    joined: list[Row] = []
    for (receiver, provider), names in around.items():
        joined_view = View(graph, [name for name in names if name in graph.entities and name not in sent])
        bodies = (_index(ctx, joined_view, Key(receiver, provider)) if ctx.session is not None
                  else _delivered(ctx, joined_view.whole(), Key(receiver, provider)))
        if bodies.get('entities'):
            sent.update(one['name'] for one in bodies['entities'])
            joined.append({'receiver': receiver, 'provider': provider, 'entities': bodies['entities']})
        if bodies.get('restored'):
            joined.append({'receiver': receiver, 'provider': provider, 'restored': bodies['restored']})
    if joined:
        found['joins'] = joined
    return found or None


def node_count(ctx: Context, addresses: tuple[str, ...]) -> tuple[Count, ...] | None:
    """Count applicable memories by shared identity and actual unread revision, without acknowledging bodies."""
    store = ctx.store
    if store is None or store.active_base() is None:
        return None
    at: dict[str, tuple[int, int, int]] = {}
    notes: dict[str, tuple[int, int, int]] = {}
    stale: dict[str, tuple[int, int, int]] = {}
    revisions: dict[str, str] = {}
    updates: dict[str, int] = {}
    snapshots: dict[str, Row] = {}
    checker = Checker(ctx)
    with store.tables(write=False) as tx:
        joined = {address: [str(row['entity']) for row in tx.rows(
            'joins', {'receiver': address, 'provider': ''}, limit=0).results]
                  for address in dict.fromkeys(addresses) if _reaches(store, address)}
        graph = Graph.read(tx, checker, list(dict.fromkeys(name for names in joined.values() for name in names)))
        for address in dict.fromkeys(addresses):
            if tx.get('notes', {'receiver': address, 'provider': ''}) is not None:
                notes[address] = (1, 0, 0)
            if address not in joined:
                continue
            names = {name for name in joined[address] if name in graph.entities}
            # A memory whose cited evidence no longer holds is counted as stale, never passed on as sound.
            flagged = sum(1 for name in names if any(checker.held(row) for row in tx.rows(
                'citations', {'entity': name}, limit=0).results))
            if flagged:
                stale[address] = (flagged, 0, 0)
            snapshots[address] = View(graph, [name for name in graph.entities if name in names]).whole()
            revision = tx.get('entry_revisions', {'receiver': address, 'provider': ''})
            revisions[address] = str(revision['revision']) if revision else ''
    for address, whole in snapshots.items():
        prepared = delivery.prepare(ctx, whole, (address, ''))
        total, unread, updated = delivery.counts(prepared)
        if ctx.session is None:
            unread.clear()
            updated.clear()
        at[address] = (len(total), len(unread), 0)
        updates[address] = len(updated)
    # the arrival line names the node read, the first address, and only its unread: the neighbours' counts stand in the
    # tree, and the map gives the line only while that node holds memory unread, `around.Around.tree`
    focus = at.get(addresses[0], (0, 0, 0))[1] if addresses else 0
    legend = _prompt('counts', unread=str(focus),
                     read_unread='metaform memory read_unread node=element:<address>')
    return (Count('memory', 'memories', at, legend=legend, revisions=revisions, updated=updates),
            Count('note', 'notes', notes, legend=prompt_files.module('memory', 'note_counts') or ''),
            Count(_prompt('stale_one'), _prompt('stale_many'), stale, legend=_prompt('stale_counts')))


def _cited(tx: TableTx, graph: Graph, name: str, address: str) -> str:
    """How a memory is cited from another: `<address>#<n>  <title>` by its join at this address when it has a numbered
    one, else its first numbered join; by its name when no join of it has a number."""
    joins = [row for row in tx.rows('joins', {'entity': name}, limit=0).results if row['number']]
    if not joins:
        return name
    chosen = min(joins, key=lambda row: (row['receiver'] != address, row['number']))
    return f"{reference(chosen['receiver'], chosen['number'])}  {graph.title(name)}"


def item_read(ctx: Context, address: str, number: int) -> dict[str, Any] | None:
    """The memory numbered `number` at `address`, read as `<address>#<n>`, MCP-037: its title, why, its name and type
    with its observations, and the memories it is related to, each cited by number and title. None when no memory
    holds that number there, or memory does not show there, LAYER-012."""
    store = ctx.store
    if store is None or not _reaches(store, address):
        return None
    with store.tables(write=False) as tx:
        found = list(tx.rows('joins', {'receiver': address, 'number': number}, limit=0).results)
        if not found:
            return None
        graph = Graph.read(tx, Checker(ctx))
        name = found[0]['entity']
        if name not in graph.entities:
            return None
        row = graph.entities[name]
        observations = [one['content'] for one in graph.observations.get(name, [])]
        cites = [one['cite'] for one in graph.citations.get(name, [])]
        stale = graph.stale(name)
        links = [f"{relation['relation_type']} → {_cited(tx, graph, relation['target'], address)}"
                 for relation in graph.relations if relation['source'] == name]
        links += [f"{relation['relation_type']} ← {_cited(tx, graph, relation['source'], address)}"
                  for relation in graph.relations if relation['target'] == name]
    locked = graph.locked(name)
    body = '\n'.join([f"{name} ({row['entity_type']})", *(f'- {one}' for one in observations),
                      *([_prompt('cites', cites=', '.join(cites))] if cites else []),
                      *(_prompt('stale', stale=one) for one in stale),
                      *([_prompt('locked_read')] if locked else [])])
    if ctx.session is not None:
        prepared = delivery.prepare(ctx, {'entities': [graph.entity(name)], 'relations': []},
                                    (address, str(found[0]['provider'])))
        for one in prepared['current']:
            one['delivered_value'] = body
        delivery.queue(ctx, prepared, all_current=True)
    return {'kind': 'memory', 'title': graph.title(name), 'why': row.get('why'), 'body': body, 'links': links,
            'name': name, 'entityType': row['entity_type'], 'observations': observations,
            **({'cites': cites} if cites else {}), **({'stale': stale} if stale else {}),
            **({'locked': _lock_said(row)} if locked else {}),
            **({'provider': found[0]['provider']} if found[0]['provider'] else {})}


def items_at(ctx: Context, address: str, before: int | None, limit: int) -> list[dict[str, Any]]:
    """The memories numbered at `address` below `before`, newest first, at most `limit`, as items are listed, MCP-037:
    each one's number, title and why, titled as `item_read` titles it, from one read of the address's joins. Empty when
    memory does not show there, LAYER-012."""
    store = ctx.store
    if store is None or not _reaches(store, address):
        return []
    found: list[dict[str, Any]] = []
    with store.tables(write=False) as tx:
        joins = [row for row in tx.rows('joins', {'receiver': address}, by=('receiver', 'number'), limit=0).results
                 if row['number'] and (before is None or row['number'] < before)]
        for row in reversed(joins):
            if len(found) >= limit:
                break
            entity = tx.get('entities', {'name': row['entity']})
            if entity is None:
                continue
            first = tx.rows('observations', {'entity': row['entity']}, by=('entity', 'seq'), limit=1).results
            title = entity.get('title') or (first_line(first[0]['content'], 0) if first else None) or row['entity']
            found.append({'number': int(row['number']), 'kind': 'memory', 'title': title, 'why': entity.get('why')})
    return found


# ------------------------------------------------------------------------------------------------ the declaration

NODE = ('The map element whose memories the command acts on, element:<address>. Without node, receiver, provider or '
        'address the command acts on the whole memory graph.')
RECEIVER = 'A purpose whose memories the command acts on: the address of the element that holds it, with provider.'
PROVIDER = 'A purpose whose memories the command acts on: the address of the element that serves it, with receiver.'
ADDRESS = 'An element, by address; with receiver and provider, the element at that address the join holds.'
NAMED = (Noun('receiver', RECEIVER, required=False), Noun('provider', PROVIDER, required=False),
         Noun('address', ADDRESS, required=False))
CITE = {'type': 'array', 'items': {'type': 'string'},
        'description': 'Optional: the evidence, path:line, path:start-end or path:symbol relative to the project; a '
                       'read flags the memory stale once it no longer matches.'}
ENTITY = {'type': 'object', 'properties': {
    'name': {'type': 'string', 'description': 'The name of the entity'},
    'entityType': {'type': 'string', 'description': 'The type of the entity'},
    'observations': {'type': 'array', 'items': {'type': 'string'},
                     'description': f'The observations, one fact each. {OBSERVATION_RULE}'},
    'title': {'type': 'string', 'description': 'A new entity: one line saying what this memory is. Left out, it is '
                                               'the first observation when that is one short line.'},
    'why': {'type': 'string', 'description': 'A new entity, required: one line saying why this is worth keeping.'},
    'cite': CITE},
    'required': ['name', 'entityType', 'observations']}
RELATION = {'type': 'object', 'properties': {
    'from': {'type': 'string', 'description': 'The name of the entity where the relation starts'},
    'to': {'type': 'string', 'description': 'The name of the entity where the relation ends'},
    'relationType': {'type': 'string', 'description': 'The type of the relation'}},
    'required': ['from', 'to', 'relationType']}
OBSERVATIONS = {'type': 'array', 'items': {'type': 'object', 'properties': {
    'entityName': {'type': 'string', 'description': 'The name of the entity to add the observations to'},
    'contents': {'type': 'array', 'items': {'type': 'string'},
                 'description': f'The observations to add, one fact each. {OBSERVATION_RULE}'},
    'cite': CITE},
    'required': ['entityName', 'contents']}}
DELETIONS = {'type': 'array', 'items': {'type': 'object', 'properties': {
    'entityName': {'type': 'string', 'description': 'The name of the entity containing the observations'},
    'observations': {'type': 'array', 'items': {'type': 'string'}, 'description': 'An array of observations to delete'}},
    'required': ['entityName', 'observations']}}
NAMES = {'type': 'array', 'items': {'type': 'string'}}


EXAMPLE = ('metaform memory create_entities \'[{"name":"route ejection","entityType":"behavior",'
           '"observations":["Routes are ejected, never packed on delete."],'
           '"why":"Packing on delete lost routes."}]\' node=element:code.manager.route')


def _at(*nouns: Noun) -> tuple[Noun, ...]:
    return (*nouns, Noun('node', NODE, required=False), *NAMED)


MODULE = Module(
    id='memory',
    summary='A memory graph, presented at each node of the map as the MCP reference memory server.',
    purpose='A graph of entities, observations and relations, the MCP reference memory server\'s, kept apart from the '
            'map and indexed at functional entry points. Give node to maintain applicable project knowledge '
            'at a node of the map; leave it out to inspect the whole graph. Read unread contents through those '
            'functional entry points and maintain entities, atomic observations and directed relations. '
            'Details: metaform help memory.',
    details='The nine commands take the reference memory server\'s arguments and return its results. With node, the '
            'reads act on the entities joined to that node and every relation with an end among them; create_entities '
            'joins what it makes to the node; the other writes name an entity anywhere in the graph, and only a name '
            'the graph lacks stops them. Any agent may change or delete any memory, unless the person has locked it. '
            'A memory join is keyed by the node\'s namespace address, so a clear keeps it and a new '
            'intake with the same address reconnects it; orphaned lists those the map no longer holds. '
            'rekey <old-address> <new-address> transfers attachments and notes when an address is replaced. The reads at '
            'a node show nothing while the layer named memory is turned off there, with select, mask or --layers. Each '
            'node also holds one note of at most 2048 characters.',
    verbs=(
        Verb('create_entities', create_entities, 'Create new memory entities, one fact per observation, indexed at '
                                                 'the given functional node. Existing names are skipped; extend them '
                                                 'with add_observations and index them with join. Without node, new '
                                                 'entities have no functional index association.',
             nouns=_at(Noun('entities', 'The entities to create; each observation is one fact.', kind='json',
                            schema={'type': 'array', 'items': ENTITY})),
             examples=((EXAMPLE, 'Create an entity in the memories of the route manager.'),)),
        Verb('create_relations', create_relations,
             'Relate memory entities to one another, at a node or in the whole memory graph. Relations should be in '
             'active voice.',
             nouns=_at(Noun('relations', 'The relations to create.', kind='json',
                            schema={'type': 'array', 'items': RELATION}))),
        Verb('add_observations', add_observations, 'Add observations, each one fact in one sentence, to memory '
                                                   'entities that already exist, at a node or in the whole memory '
                                                   'graph.',
             nouns=_at(Noun('observations', 'The observations to add, by entity; each is one fact.', kind='json',
                            schema=OBSERVATIONS))),
        Verb('delete_entities', delete_entities,
             'Delete memory entities and their relations, at a node or in the whole memory graph.',
             nouns=_at(Noun('entityNames', 'An array of entity names to delete', kind='json', schema=NAMES)),
             effect='remove'),
        Verb('delete_observations', delete_observations,
             'Delete observations from memory entities, at a node or in the whole memory graph.',
             nouns=_at(Noun('deletions', 'The observations to delete, by entity.', kind='json', schema=DELETIONS)),
             effect='remove'),
        Verb('delete_relations', delete_relations, 'Delete relations between memory entities, at a node or in the '
                                                   'whole memory graph.',
             nouns=_at(Noun('relations', 'An array of relations to delete', kind='json',
                            schema={'type': 'array', 'items': RELATION})), effect='remove'),
        Verb('read_graph', read_graph, 'Read the memories at a node of the map, or the whole memory graph without one.',
             nouns=_at(), effect='read'),
        Verb('read_unread', read_unread, 'List unread memory titles and one-line reasons without reading bodies; '
                                       'use open_nodes for selected memories.',
             nouns=_at(), effect='read'),
        Verb('search_nodes', search_nodes, 'Search memory entities by name, type and observation text, at a node or in '
                                           'the whole memory graph.',
             nouns=_at(Noun('query', 'The search query to match against entity names, types, and observation '
                                     'content')), effect='read'),
        Verb('open_nodes', open_nodes, 'Read memory entities by name, at a node or in the whole memory graph.',
             nouns=_at(Noun('names', 'An array of entity names to retrieve', kind='json', schema=NAMES)), effect='read'),
        Verb('note', note, "Read the person's one note at a node of the map; only the web page writes it.",
             nouns=(Noun('node', 'An element, element:<address>; with provider, the purpose it holds as receiver.'),
                    Noun('provider', 'A purpose node holds as its receiver: the address of the element that serves '
                                     'it.', required=False),
                    Noun('address', 'With provider: the element at that address the join holds.', required=False),
                    Noun('text', f'The note, at most {NOTE_LIMIT} characters; only the web page writes it.', required=False),
                    Noun('by', 'Who wrote it.', required=False)),
             examples=(('metaform memory note element:code.manager.route', "Read the route manager's note."),), effect='read'),
        Verb('joins', joins, 'List the memory joins that tie entities to map nodes: at a node, of an entity, or all. '
                             'Each comes with who made it and whether it is orphaned.',
             nouns=(Noun('node', 'element:<address>.', required=False), *NAMED,
                    Noun('entity', 'An entity name.', required=False)), effect='read'),
        Verb('join', join, 'Index an existing memory entity at a functional element or join without copying it.',
             nouns=_at(Noun('entity', 'An existing memory entity name.'))),
        Verb('orphaned', orphaned, 'List the memory joins whose address the active map no longer holds, with what each '
                                   'was attached to.', effect='read'),
        Verb('unjoin', unjoin, 'Detach one memory join from its node by its id; the entity stays in the memory graph.',
             nouns=(Noun('id', 'The join id joins or orphaned gives.'),), effect='remove'),
        Verb('rekey', rekey, 'Move the memory joins and notes at an old address to the address that replaced it.',
             nouns=(Noun('old', 'The exact old namespace address, including one no longer held by the map.'),
                    Noun('new', 'The replacement namespace address.')),
             details='Replaces the exact address in receivers and providers of memory joins and notes in one '
                     'transaction. Keeps join ids, note text, author and time, and the memory graph. A destination '
                     'key collision rolls back the whole transfer. Returns the number of joins and notes changed.',
             examples=(('metaform memory rekey code.manager.route code.manager.table',
                        'Transfer the route manager\'s memory to its replacement address.'),)),
        Verb('graph', graph, 'Read the whole memory graph with its joins to the map: who wrote each, and whether each '
                             'shows at its node.', effect='read'),
        Verb('lock', lock, 'Lock a memory: every agent still reads it, and none can change or delete it.',
             nouns=(Noun('name', 'The memory entity\'s name.'),), surfaces=('cli',),
             examples=(('metaform memory lock "route ejection"', 'Keep the route ejection memory as it is.'),)),
        Verb('unlock', unlock, 'Unlock a memory, so agents may change and delete it again.',
             nouns=(Noun('name', 'The memory entity\'s name.'),), surfaces=('cli',),
             examples=(('metaform memory unlock "route ejection"', 'Let agents change it again.'),)),
        Verb('watch', watch, 'Work out whether each memory\'s citations hold each time a cited file changes, until '
                             'stopped, so a read looks it up.',
             details='web start starts it, detached, for each project whose memories cite files. Its process is kept '
                     'in the Metaform home, run/memory/<project>.json, with its lock and log beside. While none runs, '
                     'a read works out the citations whose files changed itself.',
             surfaces=('cli',), supported_os=WATCH_OS),
    ),
    subscriptions=(Subscription('web.started', web_started), Subscription('map.moved', map_moved)),
    node_read=node_read,
    node_count=node_count,
    provides=(Provides('memory.note', person_note), Provides('memory.prompt', memory_prompt),
              Provides('memory.record', record),
              Provides('memory.revision', delivery.revision)),
    item_read=item_read,
    items_at=items_at,
    item_kinds=('memory',),
    tables=TABLES,
    # What agents learned at a node, read beside the node it belongs to: knowledge attaches to the receiving element.
    toolbar=(
        ToolbarItem('memories', 'Memories', 'Read what agents learned at the selected node: its entities, '
                    'observations and relations.', icon='memory', pane='memories', order=80, shortcut='Alt+M'),
        ToolbarItem('orphaned', 'Orphaned memories', 'Find the memories whose node the map no longer holds, and '
                    'move or detach them.', icon='memory', page='orphaned', placement='extra', order=400),
    ),
    panes=(
        Pane('memories', 'Memories', 'Read what agents learned at the selected node: its entities, observations and '
             'relations.', icon='memory', verb='read_graph', selection='node', area='right', group='node',
             order=60, min_width=320),
    ),
)
