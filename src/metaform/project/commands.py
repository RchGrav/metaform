"""The command engine of the `project` tool: one JSON command in, one JSON answer out.

`run` takes a command with exactly one key and answers it. It never raises for a bad command: a refusal comes back
as the refused command followed by `status`, a fixed `code`, a plain `message` and a `remediation` (a command, or
`None` when the tool would have to guess). A successful write answers `{"status": "ok"}` and nothing more. A store
failure is answered as `INTERNAL_ERROR` in the same form.

Every path leads with the project's name, and the tool keeps no session: each call opens the project's database,
answers, and closes it. A write is one transaction, rolled back on any refusal or failure; a project is made by its
first `add`, and the database is removed again if that first command is refused.
"""
from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any, cast

from metaform import home as metaform_home
from metaform import prompt_files
from metaform.project import forms, intake, specification, texts
from metaform.project.forms import Address, Refusal, as_object, full, parse, refuse
from metaform.project.overlays import Definition, Field, decode, definitions
from metaform.project.owner import Missing, Owner
from metaform.project.store import (
    CYPHER_SECONDS,
    ELEMENT_FIELDS,
    PART_FIELDS,
    ROOT_FIELDS,
    Scalar,
    Store,
    StoreError,
    cypher_refusal,
)
from metaform.project.store import projects as store_projects
from metaform.project.writes import Writer

OK: dict[str, object] = {'status': 'ok'}
ANSWER_KEYS = ('status', 'code', 'message', 'remediation')


def run(command: object, home: Path | None = None, caller: str = '') -> dict[str, object]:
    """Answer one command, from any process. `home` is the Metaform home whose `maps` folder holds the projects; by
    default `metaform.home.home()`. `caller` names who sent it, so the write queue serves each caller in turn.

    The command is sent to the home's single-writer service, which is started when none is running. No caller opens
    a database itself, so the writes of every process are serialized in one place."""
    from metaform.project import service
    return service.send(command, home if home is not None else metaform_home.home(), caller)


def drawn(project: str, home: Path | None = None) -> dict[str, object] | None:
    """What a display draws of a project in one read: every element with its own fields, and every want with its
    fields. None when the project has no database. This is not a command of the tool, whose `map` returns no fields
    so an agent's read stays small; a display needs each element's name and role to draw it."""
    from metaform.project import service
    if project not in store_projects(home if home is not None else metaform_home.home()):
        return None  # asked of the folder, so a project never taken in starts no service
    answer = service.send(None, home if home is not None else metaform_home.home(), 'display', drawn=project)
    return None if answer.get('status') == 'error' else answer


def stored_name(project_id: str) -> str:
    """The name a registered project has in the project store: its id, with the underscores a step is written with."""
    return project_id.lower().replace('-', '_')


def clear(project: str, home: Path | None = None) -> bool:
    """Remove a project's database, as clearing the project does. False when the project store holds none."""
    from metaform.project import service
    where = home if home is not None else metaform_home.home()
    if project not in store_projects(where):
        return False
    return service.send(None, where, 'clear', clear=project).get('status') == 'ok'


def overlay_records(project: str, key: str, home: Path | None = None) -> list[dict[str, object]] | None:
    """Every record of one overlay across a project, each with the path of the element it is at and its position
    there, for a display that lists them all, as a board lists tickets. None when the store holds no such project.
    Not a command of the tool, which reads an overlay's records with the element they are at."""
    from metaform.project import service
    where = home if home is not None else metaform_home.home()
    if project not in store_projects(where):
        return None
    answer = service.send(None, where, 'display', drawn=project, overlay=key)
    return None if answer.get('status') == 'error' else cast(list[dict[str, object]], answer['records'])


def perform_records(project: str, key: str, owned: Owner) -> dict[str, object]:
    """Answer a display's read of one overlay's records in the service."""
    def read(opened: Store) -> dict[str, object]:
        definition = definitions(opened.parts()).get(key)
        if definition is None or key not in opened.overlay_keys():
            return {'records': []}
        names = [name for name in definition.order if name != 'ref' and name in definition.fields]
        return {'records': [
            {'element': full(project, address), 'position': position,
             **{name: decode(definition.fields[name].kind, row[name]) for name in names if row[name] is not None},
             **({'ref': row['ref']} if row['ref'] is not None else {}),
             'record': row['record'], 'revision': row['revision']}
            for address, position, row in opened.all_records(key, names)]}
    try:
        return owned.read(project, read)
    except Missing:
        return refused({'records': project}, _missing(project))
    except StoreError as error:
        return refused({'records': project}, Refusal('INTERNAL_ERROR', f'the store failed: {error}'))


def perform_drawn(project: str, owned: Owner) -> dict[str, object]:
    """Answer a display's read in the service. Not reachable through the tool, which sends commands only."""
    try:
        return owned.read(project, lambda opened: _drawn(opened, project))
    except Missing:
        return refused({'drawn': project}, _missing(project))
    except StoreError as error:
        return refused({'drawn': project}, Refusal('INTERNAL_ERROR', f'the store failed: {error}'))


def perform_cypher(project: str, query: str, owned: Owner) -> dict[str, object]:
    """Answer a caller's Cypher query in the service, on a reader, inside a read-only transaction: `{'columns':
    [names], 'rows': [[values]]}`, each value as JSON holds it. Not reachable through the tool, which sends commands
    only. A query that would write, or that the engine cannot answer, is refused and changes nothing."""
    asked: dict[str, object] = {'cypher': project}
    refusal = cypher_refusal(query)
    if refusal is not None:
        return refused(asked, Refusal('QUERY_REFUSED', f'the query was refused: {refusal}.'))

    def read(opened: Store) -> dict[str, object]:
        try:
            names, rows = opened.cypher(query)
        except StoreError as error:  # answered here, so the reader does not run a refused query a second time
            said = (str(error).strip().splitlines() or ['the engine gave no reason'])[0][:300]
            if 'read-only transaction' in said:
                return refused(asked, Refusal('QUERY_REFUSED', 'the query was refused: it would change the map, '
                                              'and a query only reads.'))
            if said.rstrip('.') == 'Interrupted':
                return refused(asked, Refusal('QUERY_TIMEOUT', f'the query ran past its limit of {CYPHER_SECONDS} '
                                              'seconds and was stopped.'))
            return refused(asked, Refusal('QUERY_INVALID', f'the query was not understood: {said}'))
        return {'columns': names, 'rows': [[_plain(value) for value in row] for row in rows]}
    try:
        return owned.read(project, read)
    except Missing:
        return refused(asked, _missing(project))
    except StoreError as error:
        return refused(asked, Refusal('INTERNAL_ERROR', f'the store failed: {error}'))


def _plain(value: object) -> object:
    """A value the engine returned, as JSON holds it: nodes, edges and paths as objects, lists as lists, and a value
    of another type, such as a date or a decimal, as its text."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _plain(held) for key, held in cast(dict[object, object], value).items()}
    if isinstance(value, (list, tuple)):
        return [_plain(held) for held in cast(list[object], value)]
    return str(value)


def _drawn(opened: Store, project: str) -> dict[str, object]:
    # Each overlay is listed by its key with the address its definition is stored at: a key cannot be turned back into
    # an address, since a step may hold an underscore (review_findings is not findings.review), F04.
    return {'elements': [{'address': full(project, address), **_fields(values)}
                         for address, values in opened.all_elements()],
            'wants': [{'holder': full(project, holder), 'element': full(project, str(want['element'])),
                       **{name: value for name, value in want.items() if name != 'element' and value is not None}}
                      for holder, want in opened.all_wants()],
            'overlays': [{'key': key, 'address': full(project, definition.address),
                          'description': definition.description or ''}
                         for key, definition in sorted(definitions(opened.parts()).items())]}


def perform(command: object, owned: Owner, caller: str = '', request: str = '') -> dict[str, object]:
    """Answer one command against the databases this process owns. The service calls this; other code calls `run`.
    `request` is the id of a write: a write whose id is already stored is answered and not done again."""
    try:
        try:
            verb, body = forms.check(command)
        except Refusal as refusal:
            raise _as_records(command, owned) or refusal from None
        return _answer(verb, body, command, owned, caller, request)
    except Refusal as refusal:
        return refused(command, refusal)
    except StoreError as error:
        stored = ('the write may or may not be stored' if error.unknown else
                  'the transaction was rolled back, so the command changed nothing')
        return refused(command, Refusal('INTERNAL_ERROR', f'the store failed: {error}; {stored}'))
    except Exception as error:  # noqa: BLE001  a fault in the tool itself is answered too, never raised
        return refused(command, Refusal('INTERNAL_ERROR', f'the tool failed: {type(error).__name__}: {error}; '
                                        'a write in progress was rolled back'))


def refused(command: object, refusal: Refusal) -> dict[str, object]:
    entries = as_object(command)
    head = dict(entries) if entries is not None and not set(entries) & set(ANSWER_KEYS) else {'command': command}
    return {**head, 'status': 'error', 'code': refusal.code, 'message': refusal.message,
            'remediation': refusal.remediation}


def _as_records(command: object, owned: Owner) -> Refusal | None:
    """An add or update the shape check refused because it gives an overlay's records as an object, which reads as a
    step beneath the element: answered as the Rust form answers it (`metaform-core/src/specification.rs`), with the
    records as the list they must be. Only an overlay the project defines counts, read once the command is already
    refused, so a name that is no overlay keeps the shape check's own answer."""
    entries = as_object(command)
    if entries is None or len(entries) != 1:
        return None
    ((verb, body),) = entries.items()
    selected = as_object(body)
    if verb not in ('add', 'update') or selected is None or len(selected) != 1:
        return None
    ((path, value),) = selected.items()
    fields = as_object(value)
    if fields is None or forms.root_of(body) is not None:
        return None
    try:
        address = parse(path)
        keys = owned.read(address.project, lambda opened: set(definitions(opened.parts())))
    except (Refusal, Missing, StoreError):
        return None

    def found(at: str, given: dict[str, object]) -> tuple[str, str, object] | None:
        for key, item in given.items():
            inner = as_object(item)
            if inner is None:
                continue
            if key in keys and key != 'wants':
                return at, key, inner
            deeper = found(f'{at}.{key}', inner)
            if deeper is not None:
                return deeper
        return None
    hit = found(address.full, fields)
    if hit is None:
        return None
    holder, key, record = hit
    return Refusal('FIELD_MISMATCH', f"'{holder}': {key}: an overlay's records are a list",
                   {verb: {holder: {key: [record]}}})


def _missing(project: str) -> Refusal:
    return Refusal('NOT_FOUND', f"the project '{project}' does not exist; add makes a project with its first element",
                   {'map': {}})


def _answer(verb: str, body: object, command: object, owned: Owner, caller: str,
            request: str) -> dict[str, object]:
    if verb == 'help':
        return _help(body)
    if verb == 'map' and body == {}:
        return {'projects': owned.projects()}
    try:
        if verb in ('map', 'orphaned'):
            project = str(body)
            return owned.read(project, lambda opened: _map(opened, project) if verb == 'map'
                              else _orphaned(opened, project))
        if verb in ('add', 'update', 'delete'):
            ((path, value),) = as_dict(body).items()
            if forms.root_of(body) is not None:
                return _write_root(verb, path, as_dict(value), owned, caller, request)
            return _write(verb, path, value, command, owned, caller, request)
        if '.' not in verb:  # the project's root: its own fields
            try:
                return owned.read(verb, lambda opened: {verb: _root(opened)})
            except Missing:  # one word that is no project may be a command written wrongly: the answer names both
                raise Refusal('NOT_FOUND', f"'{verb}' is not a command and not a project of this home: the commands "
                              f"are {', '.join(forms.COMMANDS)}, and {{\"map\": {{}}}} names the projects",
                              {'map': {}}) from None
        address = parse(verb)
        return owned.read(address.project, lambda opened: _read(opened, address, as_dict(body)))
    except Missing as missing:
        raise _missing(str(missing)) from None


def as_dict(value: object) -> dict[str, object]:
    entries = as_object(value)
    assert entries is not None, 'checked by forms.check'
    return entries


def _help(body: object) -> dict[str, object]:
    if body == {}:
        return {'help': {'type': 'object', 'properties': {'help': {'enum': list(texts.HELP_NAMES)}},
                         'required': ['help']}}
    # `intake` lists the sections of the intake procedure and `intake/<section>` returns one, as the Rust form answers
    # them (`metaform-core/src/contract.rs`): an agent reads a section when it needs the rules in it, and no sooner.
    if body == 'intake':
        return {'help': {'intake': intake.listing()}}
    if isinstance(body, str) and body.startswith('intake/'):
        wanted = body.removeprefix('intake/')
        found = intake.section(wanted)
        if found is None:
            raise refuse(f'the intake procedure has no section \'{wanted}\'; {{"help": "intake"}} lists its sections',
                         {'help': 'intake'})
        return {'help': {body: found.text}}
    if isinstance(body, str) and body in texts.HELP:
        answer: dict[str, object] = {**cast(dict[str, object], texts.HELP[body])}
        # The founder's pointer, 2026-11-17: a command whose rules live in sections of the intake procedure says so in
        # their words, "Must read these URI to perform ... properly", naming each section's address; an agent reads
        # an address once in a context, however many commands name it. The pointer is a Markdown prompt beside the
        # tool, `prompts/must_read_<command>.md`, so the code names no section.
        pointer = resources.files(__package__ or 'metaform.project') / 'prompts' / f'must_read_{body}.md'
        if pointer.is_file():
            answer['must_read'] = prompt_files.markdown(resources.files(__package__ or 'metaform.project'),
                                                        f'must_read_{body}')
        return {'help': {body: answer}}
    raise refuse('help takes {} or the name of a command', {'help': {}})


def _write(verb: str, path: str, value: object, command: object, owned: Owner, caller: str,
           request: str) -> dict[str, object]:
    """One write: queued for its caller, run inside a transaction on the project's writer, answered after the commit.
    `add` makes a project that does not exist; a delete in one that does not exist has nothing to do."""
    address = parse(path)

    def work(opened: Store) -> None:
        if request and opened.request_done(request):
            return  # this same write was stored before its answer reached the caller
        writer = Writer(opened, address, command, verb)
        if verb == 'delete':
            writer.delete(value)
        else:
            writer.write(path, value)
        if request:
            opened.record_request(request)  # in the write's own transaction: stored together or not at all

    try:
        owned.write(address.project, caller, work, create=verb == 'add')
    except Missing:
        if verb == 'delete':
            return dict(OK)
        raise
    return dict(OK)


def _named(values: dict[str, Scalar], names: tuple[str, ...]) -> dict[str, object]:
    return {name: values[name] for name in names if values.get(name) is not None}


def _fields(values: dict[str, Scalar]) -> dict[str, object]:
    return _named(values, ELEMENT_FIELDS)


def _write_root(verb: str, project: str, fields: dict[str, object], owned: Owner, caller: str,
                request: str) -> dict[str, object]:
    """Write the project's own fields at its root, and the records it holds: the specification's blocks, the
    project's own description (F07). `add` makes a project that does not exist."""
    own = {name: value for name, value in fields.items() if name in ROOT_FIELDS}
    held = {name: value for name, value in fields.items() if name not in ROOT_FIELDS}

    def work(opened: Store) -> None:
        if request and opened.request_done(request):
            return
        if own:
            opened.put_root({**opened.root(), **cast(dict[str, Scalar], own)})
        if held:
            Writer(opened, Address(project, ()), {verb: {project: fields}}, verb).root(held)
        if request:
            opened.record_request(request)

    owned.write(project, caller, work, create=verb == 'add')
    return dict(OK)


def _root(opened: Store) -> dict[str, object]:
    """The project's root: its own fields, and its specification blocks when it holds any, the project's own
    description (F07), brought unasked as an element's are."""
    answer = _named(opened.root(), ROOT_FIELDS)
    if specification.KEY in opened.overlay_keys() and opened.record_count(specification.KEY, ''):
        found = definitions(opened.parts()).get(specification.KEY)
        if found is not None:
            answer[specification.KEY] = _records(opened, found, '')
    return answer


def _read(opened: Store, address: Address, named: dict[str, object]) -> dict[str, object]:
    """An addressed read: the element's own fields, its wants, the holders whose wants name it, the names of the
    other overlays that hold records there, and the records of each overlay the read names. Beneath `overlay`, the
    definition there."""
    if address.in_overlay:
        return _read_part(opened, address, named)
    at, project = address.address, address.project
    element = opened.elements([at]).get(at)
    if element is None:
        raise Refusal('NOT_FOUND', f"'{address.full}' does not exist", {'map': project})
    tables = opened.overlay_keys()
    wants = opened.wants_of(at)
    # The answer keeps the stored form's one rule: a plain value is a field and a list is an overlay. `wants`, the
    # default overlay, comes with every read. `wanted_by` lists the holders whose wants name this element, and
    # `overlays` names the other overlays that hold records here; a read that names one of them gets its records.
    answer: dict[str, object] = {
        **_fields(element),
        'wants': [_want(project, want) for want in wants],
        'wanted_by': [full(project, holder) for holder in opened.holders(at)],
        'overlays': [key for key in tables if opened.record_count(key, at)],
    }
    # The element's specification comes with every read of it, as its wants do: what the part is for, read before
    # anything at it is changed (docs/plans/specifications-overlay.md step 4; kickoff 2026-11-17 Phase 4).
    held = cast(list[str], answer['overlays'])
    defs = definitions(opened.parts()) if named or specification.KEY in held else {}
    if specification.KEY in held and specification.KEY in defs:
        answer[specification.KEY] = _records(opened, defs[specification.KEY], at)
    for name in named:
        if name == 'wants':
            continue
        if name in defs:
            answer[name] = _records(opened, defs[name], at) if name in tables else []
        else:
            raise Refusal('OVERLAY_NOT_DEFINED', f"'{name}' is not an overlay of {project}; the overlays are defined "
                          f"beneath {project}.overlay", {'map': project})
    return {address.full: answer}


def _want(project: str, want: dict[str, Scalar]) -> dict[str, object]:
    record: dict[str, object] = {'element': full(project, str(want['element']))}
    record.update((name, want[name]) for name in ('why', 'how', 'direction', 'ref') if want[name] is not None)
    return record


def _records(opened: Store, definition: Definition, at: str) -> list[dict[str, object]]:
    names = [name for name in definition.order if name != 'ref' and name in definition.fields]
    out: list[dict[str, object]] = []
    for row in opened.records(definition.key, at, names):
        record: dict[str, object] = {name: decode(definition.fields[name].kind, row[name]) for name in names
                                     if row[name] is not None}
        if row['ref'] is not None:
            record['ref'] = row['ref']
        # its identity, which an edit may name so a stale one is refused instead of landing on another record (F02)
        record.update(record=row['record'], revision=row['revision'])
        out.append(record)
    return out


def _part(values: dict[str, Scalar]) -> dict[str, object]:
    kind = Field('', str(values.get('type') or 'text'), '', None, False).kind
    return {name: decode(kind, values[name]) if name == 'example' else values[name] for name in PART_FIELDS
            if values.get(name) is not None}


def _read_part(opened: Store, address: Address, named: dict[str, object]) -> dict[str, object]:
    parts = opened.parts()
    at = address.address
    if at not in parts:
        raise Refusal('NOT_FOUND', f"'{address.full}' does not exist", {'map': address.project})
    if named:
        raise refuse(f"'{address.full}' is a part of an overlay definition, which holds no records; read it with {{}}",
                     {address.full: {}})
    answer = _part(parts[at])
    definition = next((each for each in definitions(parts).values() if each.address == at), None)
    if definition is not None:
        # Read back in the form it is written in: each field of a record is a step beneath the definition.
        answer['key'] = definition.key
        answer.update((name, _part(parts[f'{at}.{name}'])) for name in definition.order if name in definition.fields)
    return {address.full: answer}


def _orphaned(opened: Store, project: str) -> dict[str, object]:
    return {full(project, address): _fields(values) for address, values in opened.orphans()}


def _map(opened: Store, project: str) -> dict[str, object]:
    # The base map alone: an overlay's definition is read at its own address, and `overlays` names the ones defined.
    # A bare branch on the way to an element is left out: the addresses beneath it already spell it.
    elements = opened.all_elements()
    pairs = opened.pairs()
    named = {address for pair in pairs for address in pair}
    every = sorted(address for address, _ in elements)
    above = {address.rsplit('.', 1)[0] for address in every if '.' in address}
    kept = [address for address, values in sorted(elements)
            if _fields(values) or address in named or address not in above]
    return {
        'addresses': [full(project, address) for address in kept],
        'overlays': sorted(definitions(opened.parts())),
        'wants': [[full(project, holder), full(project, wanted)] for holder, wanted in pairs],
        'defining': [full(project, address) for address, values in elements
                     if values['role'] == 'Defining Element' and address.split('.')[0] not in ('upstream', 'downstream')],
    }


def _specification_inputs(opened: Store, project: str) -> tuple[dict[str, dict[str, Any]],
                                                                 dict[str, list[dict[str, Any]]],
                                                                 dict[str, list[specification.Block]]]:
    """The map as the specification document reads it, every address full: each element's fields, each holder's
    wants, and each element's blocks."""
    drawn = _drawn(opened, project)
    elements = {str(row['address']): row for row in cast(list[dict[str, Any]], drawn['elements'])}
    wants: dict[str, list[dict[str, Any]]] = {}
    for want in cast(list[dict[str, Any]], drawn['wants']):
        wants.setdefault(str(want['holder']), []).append(want)
    held: dict[str, list[specification.Block]] = {}
    found = definitions(opened.parts()).get(specification.KEY)
    if found is not None and specification.KEY in opened.overlay_keys():
        names = [name for name in found.order if name != 'ref' and name in found.fields]
        rows: dict[str, list[dict[str, Any]]] = {}
        for address, _, row in opened.all_records(specification.KEY, names):
            rows.setdefault(full(project, address), []).append(
                {name: decode(found.fields[name].kind, row[name]) for name in names if row[name] is not None})
        held = {address: specification.blocks(address, records) for address, records in rows.items()}
    return elements, wants, held


def perform_specification(project: str, document: str | None, owned: Owner, caller: str = '') -> dict[str, object]:
    """The specification document of a project (kickoff 2026-11-17 Phase 4, F06). With no document, its export: the
    map and its blocks as one Markdown document. With a document, its import: the document is read against the map
    as it is now and every changed element's blocks are written, all in one transaction, so a stale or broken document
    changes nothing. Export, edit, import and export again gives the edited document."""
    try:
        if document is None:
            return {'document': owned.read(project, lambda opened: specification.render(
                project, *_specification_inputs(opened, project)))}

        def work(opened: Store) -> list[str]:
            elements, wants, held = _specification_inputs(opened, project)
            read = specification.parse(document, project, elements, wants, held)
            changed = [address for address, found in read.items() if found != held.get(address, [])]
            for address in changed:
                path = address
                value: dict[str, object] = {specification.KEY: [block.stored() for block in read[address]]}
                if path == project:  # the root's blocks, the project's own description (F07)
                    Writer(opened, Address(project, ()), {'update': {path: value}}, 'update').root(value)
                else:
                    Writer(opened, parse(path), {'update': {path: value}}, 'update').write(path, value)
            return changed

        return {'status': 'ok', 'changed': owned.write(project, caller, work)}
    except specification.ParseError as error:
        return refused({'specification': project}, Refusal('DOCUMENT_REFUSED', str(error)))
    except Refusal as refusal:
        return refused({'specification': project}, refusal)
    except Missing:
        return refused({'specification': project}, _missing(project))
    except StoreError as error:
        return refused({'specification': project}, Refusal('INTERNAL_ERROR', f'the store failed: {error}'))
