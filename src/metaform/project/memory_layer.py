"""The memory layer: the MCP reference memory server's nine tools and its resource, over a project's graph.

The tools are the reference's exactly (https://github.com/modelcontextprotocol/servers/tree/main/src/memory, under
the Apache License 2.0 and, for its older contributions, the MIT License; credited in NOTICE.md): the same names, titles, descriptions, inputs, results, messages and annotations, and
the same behaviour. One thing differs, as the founder set it on 2026-11-17: every object of the project's graph is an
entity too. An element or an overlay is named by its address, such as `metaform.code.orchestrator.agent`, and it
exists while the graph holds it; observations are added to it and relations made to and from it like any entity's,
and an agent's own entities sit beside them. A memory tied to an object the graph no longer holds is hidden, not
deleted: the object's observations and every relation that touches it are left out of every read, and they show again
if the object comes back. Everything is stored in the memory layer, two tables beside the map (`store`), never in an
overlay.

`run` is called in any process and sends the call to the home's single-writer service; `perform` answers it there.
`answer` turns a result into the reference's text and structured content.
"""
from __future__ import annotations

import json
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from metaform.project.forms import Refusal, parse
from metaform.project.owner import Missing, Owner
from metaform.project.store import Store, StoreError

SEARCH_QUERY_MAX_LENGTH = 2048

_ENTITY: dict[str, Any] = {
    'type': 'object',
    'properties': {
        'name': {'type': 'string', 'description': 'The name of the entity'},
        'entityType': {'type': 'string', 'description': 'The type of the entity'},
        'observations': {'type': 'array', 'items': {'type': 'string'},
                         'description': 'An array of observation contents associated with the entity'},
    },
    'required': ['name', 'entityType', 'observations'],
}
_RELATION: dict[str, Any] = {
    'type': 'object',
    'properties': {
        'from': {'type': 'string', 'description': 'The name of the entity where the relation starts'},
        'to': {'type': 'string', 'description': 'The name of the entity where the relation ends'},
        'relationType': {'type': 'string', 'description': 'The type of the relation'},
    },
    'required': ['from', 'to', 'relationType'],
}
_OBSERVATION_LIMIT: dict[str, Any] = {
    'type': 'integer', 'minimum': 0,
    'description': ('Return at most this many observations per entity (the first ones, in the order they were added) '
                    "and add each entity's total as observationCount. Use 0 for names, types and counts only: a cheap "
                    'overview of a large graph, after which open_nodes reads the entities you need in full. Omit to '
                    'return every observation.'),
}
_READ_ENTITY: dict[str, Any] = {
    'type': 'object',
    'properties': {
        **_ENTITY['properties'],
        'observationCount': {'type': 'integer', 'minimum': 0,
                             'description': ('How many observations the entity holds in total; present only when '
                                             'observationLimit was given')},
    },
    'required': ['name', 'entityType', 'observations'],
}
_GRAPH: dict[str, Any] = {
    'type': 'object',
    'properties': {'entities': {'type': 'array', 'items': _READ_ENTITY},
                   'relations': {'type': 'array', 'items': _RELATION}},
    'required': ['entities', 'relations'],
}
_DONE: dict[str, Any] = {
    'type': 'object', 'properties': {'success': {'type': 'boolean'}, 'message': {'type': 'string'}},
    'required': ['success', 'message'],
}
_WRITES = {'readOnlyHint': False, 'destructiveHint': False, 'idempotentHint': True, 'openWorldHint': False}
_DELETES = {'readOnlyHint': False, 'destructiveHint': True, 'idempotentHint': True, 'openWorldHint': False}
_READS = {'readOnlyHint': True, 'destructiveHint': False, 'idempotentHint': True, 'openWorldHint': False}


def _input(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {'type': 'object', 'properties': properties, 'required': required}


# The nine tools as the reference registers them: name, title, description, input and output schemas, annotations.
TOOLS: tuple[dict[str, Any], ...] = (
    {'name': 'create_entities', 'title': 'Create Entities',
     'description': ('Create multiple new entities in the knowledge graph. An entity whose name already exists, or '
                     'repeats an earlier entity in the same call, is skipped and its observations are not added; the '
                     'result lists the skipped names in `skipped`. Use add_observations to add observations to an '
                     'existing entity.'),
     'inputSchema': _input({'entities': {'type': 'array', 'items': _ENTITY,
                                         'description': 'The entities to create, each with a name unique in the graph'}},
                           ['entities']),
     'outputSchema': {'type': 'object', 'properties': {'entities': {'type': 'array', 'items': _ENTITY},
                                                       'skipped': {'type': 'array', 'items': {'type': 'string'}}},
                      'required': ['entities']},
     'annotations': _WRITES},
    {'name': 'create_relations', 'title': 'Create Relations',
     'description': ('Create multiple new relations between entities in the knowledge graph. Relations should be in '
                     'active voice'),
     'inputSchema': _input({'relations': {'type': 'array', 'items': _RELATION,
                                          'description': ('The relations to create. Both ends must name existing '
                                                          'entities; a relation already in the graph is not added '
                                                          'again')}},
                           ['relations']),
     'outputSchema': {'type': 'object', 'properties': {'relations': {'type': 'array', 'items': _RELATION}},
                      'required': ['relations']},
     'annotations': _WRITES},
    {'name': 'add_observations', 'title': 'Add Observations',
     'description': 'Add new observations to existing entities in the knowledge graph',
     'inputSchema': _input({'observations': {
         'type': 'array',
         'items': {'type': 'object',
                   'properties': {'entityName': {'type': 'string',
                                                 'description': 'The name of the entity to add the observations to'},
                                  'contents': {'type': 'array', 'items': {'type': 'string'},
                                               'description': 'An array of observation contents to add'}},
                   'required': ['entityName', 'contents']},
         'description': ('The observations to add, grouped by entity. Each entity must already exist; an observation '
                         'it already has is not added again')}}, ['observations']),
     'outputSchema': {'type': 'object', 'properties': {'results': {'type': 'array', 'items': {
         'type': 'object', 'properties': {'entityName': {'type': 'string'},
                                          'addedObservations': {'type': 'array', 'items': {'type': 'string'}}},
         'required': ['entityName', 'addedObservations']}}}, 'required': ['results']},
     'annotations': _WRITES},
    {'name': 'delete_entities', 'title': 'Delete Entities',
     'description': ('Delete whole entities from the knowledge graph, together with every relation that points to or '
                     'from them and all their observations. Use it only to remove an entity entirely; to remove a '
                     'link between two entities and keep both, use delete_relations, and to remove facts from an '
                     'entity, use delete_observations. Cannot be undone.'),
     'inputSchema': _input({'entityNames': {'type': 'array', 'items': {'type': 'string'},
                                            'description': 'An array of entity names to delete'}}, ['entityNames']),
     'outputSchema': _DONE, 'annotations': _DELETES},
    {'name': 'delete_observations', 'title': 'Delete Observations',
     'description': 'Delete specific observations from entities in the knowledge graph',
     'inputSchema': _input({'deletions': {
         'type': 'array',
         'items': {'type': 'object',
                   'properties': {'entityName': {'type': 'string',
                                                 'description': 'The name of the entity containing the observations'},
                                  'observations': {'type': 'array', 'items': {'type': 'string'},
                                                   'description': 'An array of observations to delete'}},
                   'required': ['entityName', 'observations']},
         'description': 'The observations to delete, grouped by entity, each matched by its exact text'}},
         ['deletions']),
     'outputSchema': _DONE, 'annotations': _DELETES},
    {'name': 'delete_relations', 'title': 'Delete Relations',
     'description': ('Delete specific relations (from, to, relationType) from the knowledge graph and keep the '
                     'entities they connect. Each relation must match an existing one exactly on all three fields; '
                     'if unsure, call open_nodes (or search_nodes) first to read the stored relationType. Use it to '
                     'remove a link between two entities; to remove an entity itself, use delete_entities. Cannot be '
                     'undone.'),
     'inputSchema': _input({'relations': {'type': 'array', 'items': _RELATION,
                                          'description': 'An array of relations to delete'}}, ['relations']),
     'outputSchema': _DONE, 'annotations': _DELETES},
    {'name': 'read_graph', 'title': 'Read Graph',
     'description': ('Read the entire knowledge graph: every entity with its observations, and every relation. The '
                     'result grows with the graph, so use this only when you need everything; prefer search_nodes to '
                     'find entities by keyword and open_nodes to read entities whose names you know.'),
     'inputSchema': _input({'entityTypes': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1,
                                            'description': ('Return only entities whose entityType is one of these '
                                                            '(exact match), and only the relations that touch one of '
                                                            'them. Omit to return every entity.')},
                            'observationLimit': _OBSERVATION_LIMIT}, []),
     'outputSchema': _GRAPH, 'annotations': _READS},
    {'name': 'search_nodes', 'title': 'Search Nodes',
     'description': ('Search the knowledge graph for entities whose name, type or observations contain the query '
                     '(case-insensitive). Use this when you have a keyword, a topic or part of a name but not the '
                     'exact entity names. Prefer open_nodes when you already know the exact names, and use read_graph '
                     'only when you need the whole graph. Returns the matching entities and every relation that '
                     'touches one of them.'),
     'inputSchema': _input({'query': {'type': 'string', 'maxLength': SEARCH_QUERY_MAX_LENGTH,
                                      'description': ('The search query to match against entity names, types, and '
                                                      'observation content')},
                            'limit': {'type': 'integer', 'minimum': 1,
                                      'description': ('Return at most this many matching entities (the first matches, '
                                                      'in stored order), with the relations that touch them. Omit to '
                                                      'return every match.')},
                            'observationLimit': _OBSERVATION_LIMIT}, ['query']),
     'outputSchema': _GRAPH, 'annotations': _READS},
    {'name': 'open_nodes', 'title': 'Open Nodes',
     'description': ('Retrieve specific entities by their exact names, with every relation that touches one of them. '
                     'Use this when you already know the names (from the conversation, or from an earlier '
                     'search_nodes or read_graph result); it is the cheapest way to read entities you can name. '
                     'Prefer search_nodes when you only have a keyword or part of a name. Names that do not exist are '
                     'skipped.'),
     'inputSchema': _input({'names': {'type': 'array', 'items': {'type': 'string'},
                                      'description': 'An array of entity names to retrieve'},
                            'observationLimit': _OBSERVATION_LIMIT}, ['names']),
     'outputSchema': _GRAPH, 'annotations': _READS},
)
NAMES = tuple(tool['name'] for tool in TOOLS)
MUTATIONS = NAMES[:6]


class MemoryError(Exception):
    """A call the reference would answer with an error: its message is the answer's text."""


# ---- the arguments, checked as the reference's schemas check them --------------------------------------------------

def _bad(tool: str, where: str, problem: str) -> MemoryError:
    return MemoryError(f'Input validation error: Invalid arguments for tool {tool}: {where}: {problem}')


def _texts(tool: str, where: str, value: object) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(one, str) for one in cast(list[object], value)):
        raise _bad(tool, where, 'expected an array of strings')
    return cast(list[str], value)


def _objects(tool: str, where: str, value: object, fields: dict[str, bool]) -> list[dict[str, Any]]:
    """An array of objects, each with these fields: a field marked True is an array of strings, else a string. Other
    keys are dropped, as the reference's schemas drop them."""
    if not isinstance(value, list):
        raise _bad(tool, where, 'expected an array')
    out: list[dict[str, Any]] = []
    for index, item in enumerate(cast(list[object], value)):
        if not isinstance(item, dict):
            raise _bad(tool, f'{where}.{index}', 'expected an object')
        given = cast(dict[str, object], item)
        kept: dict[str, Any] = {}
        for name, listed in fields.items():
            at = f'{where}.{index}.{name}'
            if listed:
                kept[name] = _texts(tool, at, given.get(name))
            elif not isinstance(given.get(name), str):
                raise _bad(tool, at, 'expected a string')
            else:
                kept[name] = given[name]
        out.append(kept)
    return out


def _whole(tool: str, where: str, value: object, least: int) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or \
            int(value) != value:
        raise _bad(tool, where, 'expected an integer')
    if value < least:
        raise _bad(tool, where, f'expected a number at least {least}')
    return int(value)


_RELATION_FIELDS = {'from': False, 'to': False, 'relationType': False}


def checked(tool: str, arguments: object) -> dict[str, Any]:
    """The arguments of a call as the tool reads them, or the reference's validation error."""
    given = cast(dict[str, object], arguments) if isinstance(arguments, dict) else {}
    if tool == 'create_entities':
        return {'entities': _objects(tool, 'entities', given.get('entities'),
                                     {'name': False, 'entityType': False, 'observations': True})}
    if tool in ('create_relations', 'delete_relations'):
        return {'relations': _objects(tool, 'relations', given.get('relations'), _RELATION_FIELDS)}
    if tool == 'add_observations':
        return {'observations': _objects(tool, 'observations', given.get('observations'),
                                         {'entityName': False, 'contents': True})}
    if tool == 'delete_entities':
        return {'entityNames': _texts(tool, 'entityNames', given.get('entityNames'))}
    if tool == 'delete_observations':
        return {'deletions': _objects(tool, 'deletions', given.get('deletions'),
                                      {'entityName': False, 'observations': True})}
    limit = _whole(tool, 'observationLimit', given.get('observationLimit'), 0)
    if tool == 'read_graph':
        types = given.get('entityTypes')
        if types is not None and not _texts(tool, 'entityTypes', types):
            raise _bad(tool, 'entityTypes', 'expected an array of at least 1 item')
        return {'entityTypes': types, 'observationLimit': limit}
    if tool == 'search_nodes':
        query = given.get('query')
        if not isinstance(query, str):
            raise _bad(tool, 'query', 'expected a string')
        if len(query) > SEARCH_QUERY_MAX_LENGTH:
            raise _bad(tool, 'query', f'expected a string of at most {SEARCH_QUERY_MAX_LENGTH} characters')
        return {'query': query, 'limit': _whole(tool, 'limit', given.get('limit'), 1), 'observationLimit': limit}
    if tool == 'open_nodes':
        return {'names': _texts(tool, 'names', given.get('names')), 'observationLimit': limit}
    raise MemoryError(f'Tool {tool} not found')


# ---- the calls, in any process --------------------------------------------------------------------------------------

def run(project: str, tool: str, arguments: object, home: Path | None = None, caller: str = '') -> dict[str, object]:
    """Call one memory tool on a project: `{"status": "ok", "result": ...}`, or `{"status": "error", "message": ...}`
    with the reference's text. The call goes to the home's single-writer service, which holds the databases."""
    from metaform import home as metaform_home
    from metaform.project import service
    try:
        given = checked(tool, arguments)
    except MemoryError as error:
        return {'status': 'error', 'message': str(error)}
    return service.send(None, home if home is not None else metaform_home.home(), caller,
                        memory={'project': project, 'tool': tool, 'arguments': given})


def answer(tool: str, arguments: dict[str, Any], result: Any) -> tuple[list[str], dict[str, Any]]:
    """A result as the reference returns it: its text items and its structured content."""
    def shown(value: object) -> str:
        return json.dumps(value, indent=2, ensure_ascii=False)

    if tool == 'create_entities':
        created, skipped = result['entities'], result['skipped']
        texts = [shown(created)]
        if skipped:
            one = len(skipped) == 1
            texts.append(f"Skipped {len(skipped)} {'entity that already exists' if one else 'entities that already exist'}"
                         f": {', '.join(skipped)}. {'Its' if one else 'Their'} observations were not added; use "
                         'add_observations for existing entities.')
        return texts, {'entities': created, 'skipped': skipped} if skipped else {'entities': created}
    if tool == 'create_relations':
        return [shown(result)], {'relations': result}
    if tool == 'add_observations':
        return [shown(result)], {'results': result}
    if tool == 'delete_entities':
        asked = arguments['entityNames']
        message = ('Entities deleted successfully' if not result['notFound'] else
                   f"Deleted {len(result['deleted'])} of {len(asked)} entities. Not found: "
                   f"{', '.join(result['notFound'])}")
        return [message], {'success': True, 'message': message}
    if tool == 'delete_observations':
        requested = sum(len(one['observations']) for one in arguments['deletions'])
        count, missing = result['deletedCount'], result['missingEntities']
        message = ('Observations deleted successfully' if count == requested else
                   f'Deleted {count} of {requested} observations.' +
                   (f" Entities not found: {', '.join(missing)}" if missing else ''))
        return [message], {'success': True, 'message': message}
    if tool == 'delete_relations':
        count, asked = result['deletedCount'], len(arguments['relations'])
        message = ('Relations deleted successfully' if count == asked else
                   f'Deleted {count} of {asked} relations. The rest matched nothing.')
        return [message], {'success': True, 'message': message}
    return [shown(result)], dict(result)


# ---- the calls, answered in the service -----------------------------------------------------------------------------

class _Graph:
    """The memory layer of one project as one call sees it: its stored entities and relations, and which objects of
    the graph the names it meets are."""

    def __init__(self, store: Store, project: str) -> None:
        self.store = store
        self.project = project
        self.rows: dict[str, tuple[str | None, list[str]]] = {
            name: (kind, observations) for name, kind, observations in store.memory_entities()}
        self.order = list(self.rows)
        self.relations = store.memory_relations()
        self._present: dict[str, str] = {}  # address of an object the graph holds -> the type its memory reports
        self._asked: set[str] = set()
        self._look([name for name, (kind, _) in self.rows.items() if kind is None])

    def address(self, name: str) -> str | None:
        """The address within the project that a name gives, when the name is an address of this project's graph."""
        try:
            found = parse(name)
        except Refusal:
            return None
        return found.address if found.project == self.project else None

    def _look(self, names: list[str]) -> None:
        wanted = {address for name in names if (address := self.address(name)) is not None} - self._asked
        if wanted:
            self._asked |= wanted
            self._present.update(self.store.objects(sorted(wanted)))

    def exists(self, name: str) -> bool:
        """Whether the name is an entity now: one of the layer's own, or an object the graph holds."""
        address = self.address(name)
        if address is None:
            return name in self.rows
        self._look([name])
        return address in self._present

    def type_of(self, name: str) -> str:
        kind = self.rows[name][0] if name in self.rows else None
        return kind if kind is not None else self._present[cast(str, self.address(name))]

    def visible(self) -> list[str]:
        """The stored entities every read shows, in the order they were made: an object's only while it is there."""
        return [name for name in self.order if self.rows[name][0] is not None or self.exists(name)]

    def shown_relations(self, names: set[str]) -> list[tuple[str, str, str]]:
        return [relation for relation in self.relations if relation[0] in names and relation[1] in names]

    def held(self, name: str) -> None:
        """An object takes a row of its own the first time it holds memory."""
        if name not in self.rows:
            self.store.put_memory_entity(name, None, [])
            self.rows[name] = (None, [])
            self.order.append(name)

    def prune(self) -> None:
        """An object's row that holds nothing any more, no observation and no relation, is removed."""
        ends = {name for start, end, _ in self.store.memory_relations() for name in (start, end)}
        empty = [name for name, kind, observations in self.store.memory_entities()
                 if kind is None and not observations and name not in ends]
        if empty:
            self.store.delete_memory_entities(empty)


def _entity(graph: _Graph, name: str, limit: int | None) -> dict[str, Any]:
    observations = graph.rows[name][1] if name in graph.rows else []
    out: dict[str, Any] = {'name': name, 'entityType': graph.type_of(name),
                           'observations': observations if limit is None else observations[:limit]}
    if limit is not None:
        out['observationCount'] = len(observations)
    return out


def _shown(graph: _Graph, names: list[str], limit: int | None, touching: bool = True) -> dict[str, Any]:
    """Entities and the relations that touch one of them, among the relations every read shows."""
    every = set(graph.visible())
    chosen = set(names)
    relations = [relation for relation in graph.shown_relations(every)
                 if not touching or relation[0] in chosen or relation[1] in chosen]
    return {'entities': [_entity(graph, name, limit) for name in names],
            'relations': [{'from': start, 'to': end, 'relationType': kind} for start, end, kind in relations]}


def _create_entities(graph: _Graph, given: dict[str, Any]) -> dict[str, Any]:
    created: list[dict[str, Any]] = []
    skipped: list[str] = []
    seen: set[str] = set()
    for entity in given['entities']:
        name = entity['name']
        if name in seen or graph.exists(name):
            skipped.append(name)
            continue
        address = graph.address(name)
        if address is not None:
            raise MemoryError(f'Entity with name {name} not found: it is an address of {graph.project}, and the map '
                              'holds nothing there; an object of the map is an entity while the map holds it')
        graph.store.put_memory_entity(name, entity['entityType'], entity['observations'])
        graph.rows[name] = (entity['entityType'], entity['observations'])
        graph.order.append(name)
        seen.add(name)
        created.append(entity)
    return {'entities': created, 'skipped': skipped}


def _create_relations(graph: _Graph, given: dict[str, Any]) -> list[dict[str, str]]:
    relations = given['relations']
    for relation in relations:
        for name in (relation['from'], relation['to']):
            if not graph.exists(name):
                raise MemoryError(f'Entity with name {name} not found')
    stored = set(graph.relations)
    made: list[dict[str, str]] = []
    for relation in relations:
        triple = (relation['from'], relation['to'], relation['relationType'])
        if triple in stored:
            continue
        stored.add(triple)
        graph.held(triple[0])
        graph.held(triple[1])
        graph.store.add_memory_relation(*triple)
        made.append(relation)
    return made


def _add_observations(graph: _Graph, given: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for one in given['observations']:
        name = one['entityName']
        if not graph.exists(name):
            raise MemoryError(f'Entity with name {name} not found')
        graph.held(name)
        kind, observations = graph.rows[name]
        added = [content for content in dict.fromkeys(one['contents']) if content not in observations]
        if added:
            graph.rows[name] = (kind, [*observations, *added])
            graph.store.set_observations(name, graph.rows[name][1])
        results.append({'entityName': name, 'addedObservations': added})
    return results


def _delete_entities(graph: _Graph, given: dict[str, Any]) -> dict[str, list[str]]:
    names = given['entityNames']
    deleted = [name for name in names if graph.exists(name)]
    not_found = [name for name in names if not graph.exists(name)]
    stored = [name for name in dict.fromkeys(deleted) if name in graph.rows]
    if stored:
        graph.store.delete_memory_entities(stored)
        graph.prune()
    return {'deleted': deleted, 'notFound': not_found}


def _delete_observations(graph: _Graph, given: dict[str, Any]) -> dict[str, Any]:
    count, missing = 0, cast(list[str], [])
    for deletion in given['deletions']:
        name = deletion['entityName']
        if not graph.exists(name):
            missing.append(name)
            continue
        if name not in graph.rows:
            continue
        kind, observations = graph.rows[name]
        kept = [observation for observation in observations if observation not in deletion['observations']]
        count += len(observations) - len(kept)
        if len(kept) != len(observations):
            graph.rows[name] = (kind, kept)
            graph.store.set_observations(name, kept)
    graph.prune()
    return {'deletedCount': count, 'missingEntities': missing}


def _delete_relations(graph: _Graph, given: dict[str, Any]) -> dict[str, int]:
    asked = {(one['from'], one['to'], one['relationType']) for one in given['relations']}
    gone = [relation for relation in graph.shown_relations(set(graph.visible())) if relation in asked]
    for relation in gone:
        graph.store.delete_memory_relation(*relation)
    if gone:
        graph.prune()
    return {'deletedCount': len(gone)}


def _read_graph(graph: _Graph, given: dict[str, Any]) -> dict[str, Any]:
    names = graph.visible()
    types = given['entityTypes']
    if types is None:
        return _shown(graph, names, given['observationLimit'], touching=False)
    return _shown(graph, [name for name in names if graph.type_of(name) in types], given['observationLimit'])


def _search_nodes(graph: _Graph, given: dict[str, Any]) -> dict[str, Any]:
    query = given['query'].lower()
    found = [name for name in graph.visible()
             if query in name.lower() or query in graph.type_of(name).lower()
             or any(query in observation.lower() for observation in graph.rows[name][1])]
    return _shown(graph, found[:given['limit']] if given['limit'] is not None else found, given['observationLimit'])


def _open_nodes(graph: _Graph, given: dict[str, Any]) -> dict[str, Any]:
    names = given['names']
    stored = [name for name in graph.visible() if name in names]
    # an object of the graph is an entity whether or not it holds memory yet, so it opens with no observations
    objects = [name for name in dict.fromkeys(names)
               if name not in graph.rows and graph.address(name) is not None and graph.exists(name)]
    return _shown(graph, [*stored, *objects], given['observationLimit'])


_CALLS: dict[str, Callable[[_Graph, dict[str, Any]], Any]] = {
    'create_entities': _create_entities, 'create_relations': _create_relations,
    'add_observations': _add_observations, 'delete_entities': _delete_entities,
    'delete_observations': _delete_observations, 'delete_relations': _delete_relations,
    'read_graph': _read_graph, 'search_nodes': _search_nodes, 'open_nodes': _open_nodes,
}


def perform(request: dict[str, Any], owned: Owner, caller: str = '') -> dict[str, object]:
    """Answer one memory call in the service: a read on a reading connection, a write queued as a memory write."""
    project, tool, given = str(request['project']), str(request['tool']), cast(dict[str, Any], request['arguments'])
    call = _CALLS.get(tool)
    if call is None:
        return {'status': 'error', 'message': f'Tool {tool} not found'}
    try:
        if tool in MUTATIONS:
            result = owned.write(project, caller, lambda opened: call(_Graph(opened, project), given), kind='memory')
        else:
            result = owned.read(project, lambda opened: call(_Graph(opened, project), given))
    except MemoryError as error:
        return {'status': 'error', 'message': str(error)}
    except Missing:
        return {'status': 'error', 'message': f'The project store holds no map of {project}; its memory is kept with '
                                              'its map, which an intake makes'}
    except StoreError as error:
        return {'status': 'error', 'message': f'The store failed: {error}'}
    return {'status': 'ok', 'result': result}
