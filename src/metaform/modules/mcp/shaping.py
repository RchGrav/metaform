"""What a tool's result carries over MCP, MCP-039: the fields the next decision needs, in as few tokens as hold them.

A result goes to the agent's context whole, and the agent reads every field of it, so by default a module tool's result
is given lean, `view` triage: no field that holds nothing (None, empty text, an empty list or object), no `false` inside
a list's rows, where it is the default, and no internal id where an Address names the thing, a record nested in another
by its address included; a list of records comes as a table, one header line and one line a record, `a|b|c`, with a
nested record's fields as `parent.field` and a list of values as `a, b`; a list of records inside a row comes as a
table of its own after it, its rows led by the row they belong to; the rest as `key: value` lines, a nested record's
fields as `parent.field: value` and text of several lines indented under its key, so no JSON is ever read inside a
line. `view` full gives every field as compact JSON; `fields` keeps only the fields named, by name or by
`parent.field`, in the text and the structured content alike; `view` count gives no records, only how many there are
and how many hold each value of the fields named, for a question about a distribution that would otherwise be answered
by reading every record.

A list is filtered on the server, so the agent never reads the records it would discard: `must_contain` keeps the rows
that hold the text anywhere, `status_equals` those whose status, state, column or condition is the value. A list of more
than LIST_MOST records with neither filter is cut there, with how many more there are and how to narrow it. A filter,
a count or a field named that no record holds is refused with the fields the records do hold, since an answer of none
would be read as true.

The structured content keeps the same lean data as an object, for an AI tool that reads it as data.
"""
from __future__ import annotations

import dataclasses
import json
from typing import Any, cast

from metaform.data import plain

# The per-call arguments a lookup tool takes over MCP, beside its own nouns; a verb that declares a noun of one of these
# names keeps its own.
VIEW = 'view'
FIELDS = 'fields'
MUST_CONTAIN = 'must_contain'
STATUS_EQUALS = 'status_equals'
ARGUMENTS = (VIEW, FIELDS, MUST_CONTAIN, STATUS_EQUALS)
VIEWS = ('triage', 'full', 'count')
# Each said in a few words, since every lookup tool listed carries them; the triage note says how they combine.
SCHEMAS: dict[str, dict[str, Any]] = {
    VIEW: {'type': 'string', 'enum': list(VIEWS), 'description': 'triage, the default, trims; full gives every field.'},
    FIELDS: {'type': 'array', 'items': {'type': 'string'}, 'description': 'Only these fields.'},
    MUST_CONTAIN: {'type': 'string', 'description': 'Only the rows holding this text.'},
    STATUS_EQUALS: {'type': 'string', 'description': 'Only the rows of this status.'},
}
# Fields no next decision reads: how a record is kept, not what it says. The Address or the reference names the thing.
DEAD = frozenset({'node_kind', 'node_id', 'layer_id', 'is_work', 'age_seconds', 'existing', 'differs', 'orphaned',
                  'position'})
STATUS = ('status', 'state', 'column', 'condition')  # what status_equals compares
LIST_MOST = 25  # the most rows a list is given without a filter


class Unheld(ValueError):
    """A field a call names, to keep, count or filter by, that no record of its result holds."""


@dataclasses.dataclass(frozen=True)
class Shape:
    """How one call asks for its result: its view, the fields it keeps, and its filters. `given` holds True once a
    list was given trimmed in this shape, so the call can say once how to ask for more."""
    view: str = 'triage'
    fields: tuple[str, ...] = ()
    must_contain: str = ''
    status_equals: str = ''
    given: list[bool] = dataclasses.field(default_factory=list[bool], compare=False)

    @property
    def filtered(self) -> bool:
        return bool(self.must_contain or self.status_equals)


def taken(arguments: dict[str, Any], declared: set[str]) -> tuple[Shape, str | None]:
    """The shape a call asks for, its arguments taken out of `arguments` unless the verb declares a noun of that name,
    and what is wrong with them, or None. A verb's own `full` given true is view full unless the call names a view."""
    given = {key: arguments.pop(key) for key in ARGUMENTS if key in arguments and key not in declared}
    # A verb's own full=true, such as map_where's, which keeps its ids and empty fields, asks for every field
    view = given.get(VIEW, 'full' if 'full' in declared and arguments.get('full') is True else 'triage')
    if view not in VIEWS:
        return Shape(), f'view is one of {", ".join(VIEWS)}, not {view!r}.'
    fields: Any = given.get(FIELDS, ())
    if isinstance(fields, str):
        fields = [one.strip() for one in fields.split(',') if one.strip()]
    if not isinstance(fields, (list, tuple)) or not all(isinstance(one, str) for one in cast(list[Any], fields)):
        return Shape(), 'fields is a list of field names.'
    texts = {key: given.get(key, '') for key in (MUST_CONTAIN, STATUS_EQUALS)}
    if not all(isinstance(value, str) for value in texts.values()):
        return Shape(), 'must_contain and status_equals are text.'
    return Shape(str(view), tuple(cast(list[str], fields)), texts[MUST_CONTAIN], texts[STATUS_EQUALS]), None


def lean(value: Any, *, row: bool = False, nested: bool = False) -> Any:
    """`value` without what holds nothing: None, empty text, lists and objects, the DEAD fields, an id whose Address is
    beside it (`receiver` beside `receiver_address`), and the id of a record `nested` in another under a key, such as a
    where read's element, which its address names; the result's own record and a list's rows keep theirs, since a
    call names them by it. With `row`, inside a list's rows or a lookup's record, `false` too, the default there."""
    if isinstance(value, dict):
        given = cast(dict[str, Any], value)
        kept: dict[str, Any] = {}
        for key, one in given.items():
            if key in DEAD or given.get(f'{key}_address') or (nested and key == 'id' and given.get('address')):
                continue
            made = lean(one, row=row, nested=True)
            if made is None or made == '' or made == [] or made == {} or (row and made is False):
                continue
            kept[key] = made
        return kept
    if isinstance(value, (list, tuple)):
        return [lean(one, row=True) for one in cast(list[Any], value)]
    return value


def _held_fields(rows: list[dict[str, Any]]) -> list[str]:
    """Every field the rows hold, a nested record's as `parent.field`, in the order they first appear."""
    found: list[str] = []
    for row in rows:
        found += [key for key in _flat(row) if key not in found]
    return found


def _named(key: str, fields: tuple[str, ...]) -> bool:
    """Whether a field, `parent.field` for a nested one, is one of `fields`: by its whole name, its parent's or its
    own."""
    return key in fields or key.split('.', 1)[0] in fields or key.rsplit('.', 1)[-1] in fields


def _check(rows: list[dict[str, Any]], shape: Shape) -> None:
    """Refuse a field named, to keep, count or filter by, that no row holds, with the fields they do hold; rows that
    hold none of the status fields refuse status_equals and a bare count by status alike."""
    held = _held_fields(rows)
    if not rows:
        return
    unheld = [one for one in shape.fields if not any(_named(key, (one,)) for key in held)]
    if unheld:
        raise Unheld(f'No record here holds {", ".join(unheld)}; they hold {", ".join(held)}.')
    if shape.status_equals and not any(key in STATUS for key in held):
        raise Unheld(f'status_equals compares {", ".join(STATUS)}, which no record here holds; they hold '
                     f'{", ".join(held)}. must_contain finds a value in any field.')


def _trim(value: Any, fields: tuple[str, ...]) -> Any:
    """A record, or a list of them, with only the fields named, `_named`, nested records trimmed the same way."""
    if isinstance(value, list):
        return [_trim(one, fields) for one in cast(list[Any], value)]
    if not isinstance(value, dict):
        return value
    kept: dict[str, Any] = {}
    for key, one in cast(dict[str, Any], value).items():
        if key in fields:
            kept[key] = one
        elif isinstance(one, dict):
            inner = {name: held for name, held in cast(dict[str, Any], one).items()
                     if _named(f'{key}.{name}', fields)}
            if inner:
                kept[key] = inner
    return kept


def _records(value: Any) -> bool:
    if not isinstance(value, list):
        return False
    items = cast(list[Any], value)
    return bool(items) and all(isinstance(one, dict) for one in items)


def _rows_key(data: dict[str, Any]) -> str | None:
    """The key of the list of records a result is about: the longest list of objects in it."""
    lists = [(len(cast(list[Any], one)), key) for key, one in data.items()
             if isinstance(one, list) and one and all(isinstance(item, dict) for item in cast(list[Any], one))]
    return max(lists)[1] if lists else None


def _status(row: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for key in STATUS:
        one = row.get(key)
        if isinstance(one, (str, int, float, bool)):
            found.append(str(one).lower())
    return found


def _kept(rows: list[dict[str, Any]], shape: Shape) -> list[dict[str, Any]]:
    """The rows the call's filters keep."""
    asked = shape.must_contain.lower()
    status = shape.status_equals.lower()
    return [row for row in rows if (not asked or asked in compact(row).lower())
            and (not status or status in _status(row))]


def compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), default=str)


def _flat(row: dict[str, Any], prefix: str = '') -> dict[str, Any]:
    """A record with each nested record's fields as `parent.field`, all the way down."""
    found: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, dict):
            found.update(_flat(cast(dict[str, Any], value), f'{prefix}{key}.'))
        else:
            found[f'{prefix}{key}'] = value
    return found


def _values(value: list[Any]) -> bool:
    """Whether a list holds plain values only, so it reads as `a, b`."""
    return all(isinstance(one, (str, int, float, bool)) for one in value)


def _plain(value: Any) -> str:
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, list) and _values(cast(list[Any], value)):
        return ', '.join(_plain(one) for one in cast(list[Any], value))
    return value if isinstance(value, str) else compact(value) if not isinstance(value, (int, float)) else str(value)


def _cell(value: Any) -> str:
    return _plain(value).replace('\\', '\\\\').replace('|', '\\|').replace('\n', '\\n')


def table(rows: list[dict[str, Any]], fields: tuple[str, ...] = (), name: str = '') -> str:
    """Records as a table: the header, the fields in the order they first appear, or those named; then a line each. A
    field that holds a list of records in some row is no column: it comes after the table as a table of its own,
    `<name>.<field>:`, each of its rows led by the first column of the row it belongs to."""
    flat = [_flat(row) for row in rows]
    columns: list[str] = []
    for row in flat:
        columns += [key for key in row if key not in columns]
    if fields:
        columns = [key for key in columns if _named(key, fields)]
    inner = [key for key in columns if any(_records(row.get(key)) for row in flat)]
    columns = [key for key in columns if key not in inner]
    lines = ['|'.join(columns)]
    lines += ['|'.join(_cell(row[key]) if key in row else '' for key in columns) for row in flat]
    lead = columns[0] if columns else ''
    for key in inner:
        nested = [{lead: row.get(lead, ''), **one} for row in flat if _records(row.get(key))
                  for one in cast(list[dict[str, Any]], row[key])]
        lines += [f'{name}.{key}:' if name else f'{key}:', table(nested)]
    return '\n'.join(lines)


def _lines(name: str, value: Any) -> list[str]:
    """One field as the agent reads it: `name: value`; a nested record's fields as `name.field: value`; a list of
    records as `name:` and its table; text of several lines indented under `name:`."""
    if isinstance(value, dict):
        found: list[str] = []
        for key, one in cast(dict[str, Any], value).items():
            found += _lines(f'{name}.{key}', one)
        return found
    if _records(value):
        return [f'{name}:', table(cast(list[dict[str, Any]], value), name=name)]
    said = _plain(value)
    if '\n' in said:
        return [f'{name}:', *('  ' + line for line in said.split('\n'))]
    return [f'{name}: {said}']


def counted(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> dict[str, Any]:
    """How many rows there are, and for each field named, or each status field when none is, how many hold each of its
    values, the most first."""
    flat = [_flat(row) for row in rows]
    held = _held_fields(rows)
    named = tuple(next((key for key in held if _named(key, (one,))), one) for one in fields) or \
        tuple(key for key in STATUS if key in held)
    by: dict[str, dict[str, int]] = {}
    for key in named:
        tally: dict[str, int] = {}
        for row in flat:
            value = row.get(key)
            label = '(none)' if value is None or value == '' else value if isinstance(value, str) else compact(value)
            tally[label] = tally.get(label, 0) + 1
        by[key] = dict(sorted(tally.items(), key=lambda pair: (-pair[1], pair[0])))
    return {'total': len(rows), **({'by': by} if by else {})}


def shaped(result: Any, shape: Shape, more: str, *, record: bool = False) -> tuple[str, dict[str, Any] | None]:
    """A module tool's result as the call asked for it: the text the agent reads, and the structured content. `more`
    is the line said when a list is cut at LIST_MOST, with <n/> for how many more. `record`: a lookup's result, whose
    own `false` fields are defaults too; a write's are kept, since there `false` may be what it did."""
    data = plain(result)
    if shape.view == 'full':
        return compact(data), cast(dict[str, Any], data) if isinstance(data, dict) else None
    listed = data if not isinstance(data, dict) else cast(dict[str, Any], data).get('results')
    data = lean(data, row=record)
    wrapped = not isinstance(data, dict)
    held: dict[str, Any] = {'results': data} if wrapped else cast(dict[str, Any], data)
    key = _rows_key(held)
    if key is None and isinstance(listed, list) and not listed:  # a list with nothing in it says so
        empty: list[dict[str, Any]] = []
        held, key = {**held, 'results': empty}, 'results'
    _check(cast(list[dict[str, Any]], held[key]) if key is not None else [held], shape)
    if key is not None and (shape.filtered or shape.view == 'count'):
        held = {**held, key: _kept(cast(list[dict[str, Any]], held[key]), shape)}
    if shape.view == 'count':
        rows = cast(list[dict[str, Any]], held.get(key, []) if key is not None else [])
        found = counted(rows, shape.fields)
        return compact(found), found
    if key == 'results' or wrapped:  # a list given trimmed, so the call says once how to ask for more; a record
        shape.given.append(True)  # with a list inside it, such as a where read's joins, is no list to narrow
    cut = ''
    if key is not None and not shape.filtered and len(held[key]) > LIST_MOST:
        rest = len(held[key]) - LIST_MOST
        held = {**held, key: held[key][:LIST_MOST]}
        cut = more.replace('<n/>', str(rest))
    if shape.fields:  # the structured content keeps what the text keeps: the rows' fields named, or the record's
        held = {**held, key: _trim(held[key], shape.fields)} if key is not None else \
            cast(dict[str, Any], _trim(held, shape.fields))
    lines: list[str] = []
    for name, value in held.items():
        if name == key:
            continue
        lines += _lines(name, value)
    if key is not None:
        rows = cast(list[dict[str, Any]], held[key])
        if not wrapped:
            lines.append(f'{key}:')
        lines.append(table(rows, name=key) if rows else '(none)')
    if cut:
        lines.append(cut)
    structured = None if wrapped else held
    return '\n'.join(lines), structured
