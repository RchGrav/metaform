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

from pathlib import Path

from metaform import home as metaform_home
from metaform.project import forms, owner, texts
from metaform.project.forms import Address, Refusal, as_object, full, parse, refuse
from metaform.project.overlays import Definition, Field, decode, definitions
from metaform.project.owner import Missing, Owner
from metaform.project.store import ELEMENT_FIELDS, PART_FIELDS, Scalar, Store, StoreError
from metaform.project.writes import Writer

OK: dict[str, object] = {'status': 'ok'}
ANSWER_KEYS = ('status', 'code', 'message', 'remediation')


def run(command: object, home: Path | None = None, caller: str = '') -> dict[str, object]:
    """Answer one command. `home` is the Metaform home whose `maps` folder holds the projects; by default
    `metaform.home.home()`. `caller` names who sent it, so the write queue serves each caller in turn."""
    try:
        verb, body = forms.check(command)
        return _answer(verb, body, command, owner.of(home if home is not None else metaform_home.home()), caller)
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


def _missing(project: str) -> Refusal:
    return Refusal('NOT_FOUND', f"the project '{project}' does not exist; add makes a project with its first element",
                   {'map': {}})


def _answer(verb: str, body: object, command: object, owned: Owner, caller: str) -> dict[str, object]:
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
            return _write(verb, path, value, command, owned, caller)
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
    if isinstance(body, str) and body in texts.HELP:
        return {'help': {body: texts.HELP[body]}}
    raise refuse('help takes {} or the name of a command', {'help': {}})


def _write(verb: str, path: str, value: object, command: object, owned: Owner, caller: str) -> dict[str, object]:
    """One write: queued for its caller, run as one transaction on the project's writer, answered after the commit.
    `add` makes a project that does not exist; a delete in one that does not exist has nothing to do."""
    address = parse(path)

    def work(opened: Store) -> None:
        with opened.transaction():
            writer = Writer(opened, address, command, verb)
            if verb == 'delete':
                writer.delete(value)
            else:
                writer.write(path, value)

    try:
        owned.write(address.project, caller, work, create=verb == 'add')
    except Missing:
        if verb == 'delete':
            return dict(OK)
        raise
    return dict(OK)


def _fields(values: dict[str, Scalar]) -> dict[str, object]:
    return {name: values[name] for name in ELEMENT_FIELDS if values.get(name) is not None}


def _read(opened: Store, address: Address, named: dict[str, object]) -> dict[str, object]:
    """An addressed read: the element's own fields, the holders whose wants name it, a count of each overlay's records
    there, and the records of each overlay the read names. Beneath `overlay`, the definition there."""
    if address.in_overlay:
        return _read_part(opened, address, named)
    at, project = address.address, address.project
    element = opened.elements([at]).get(at)
    if element is None:
        raise Refusal('NOT_FOUND', f"'{address.full}' does not exist", {'map': project})
    tables = opened.overlay_keys()
    wants = opened.wants_of(at)
    counts: dict[str, int] = {'wants': len(wants)} if wants else {}
    for key in tables:
        count = opened.record_count(key, at)
        if count:
            counts[key] = count
    answer: dict[str, object] = {**_fields(element), 'wanted_by': [full(project, holder) for holder in
                                                                    opened.holders(at)], 'overlays': counts}
    defs = definitions(opened.parts()) if named else {}
    for name in named:
        if name == 'wants':
            answer[name] = [_want(project, want) for want in wants]
        elif name in defs:
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
        answer['key'] = definition.key
        answer['fields'] = {name: _part(parts[f'{at}.{name}']) for name in definition.order
                            if name in definition.fields}
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
