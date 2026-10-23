"""What a tool's result carries over MCP, MCP-039: the fields the next decision needs, in as few tokens as hold them.

Selection runs on JSON-ready typed data before presentation: validate requested fields, filter records, recursively
project fields, then render. Full preserves every selected value as compact JSON. Triage omits internal storage
metadata and unselected null defaults, but retains false, zero and empty values because they can be evidence.
Explicit fields preserve every requested value, including null and internal fields. Dotted paths traverse nested
records and lists, and a bare field name selects that name wherever it occurs.

Lists are rendered as tables in triage. Unfiltered triage lists are bounded by LIST_MOST; full and count remain
complete. Count reports how many rows hold each selected value, with missing and null distinguished. Text and
structured content carry the same selected records.
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
    VIEW: {'type': 'string', 'enum': list(VIEWS),
           'description': 'triage trims default detail; full gives all selected fields as JSON.'},
    FIELDS: {'type': 'array', 'items': {'type': 'string'}, 'description': 'Only these fields.'},
    MUST_CONTAIN: {'type': 'string', 'description': 'Only the rows holding this text.'},
    STATUS_EQUALS: {'type': 'string', 'description': 'Only the rows of this status.'},
}
# Fields no next decision reads: how a record is kept, not what it says. The Address or the reference names the thing.
DEAD = frozenset({'node_kind', 'node_id', 'layer_id', 'age_seconds', 'position'})
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
    """Default triage detail without storage metadata, redundant ids or null defaults.

    False, zero and empty values remain evidence. Explicit projections bypass this omission step.
    """
    if isinstance(value, dict):
        given = cast(dict[str, Any], value)
        kept: dict[str, Any] = {}
        for key, one in given.items():
            if key in DEAD or given.get(f'{key}_address') or (nested and key == 'id' and given.get('address')):
                continue
            made = lean(one, row=row, nested=True)
            if made is None:
                continue
            kept[key] = made
        return kept
    if isinstance(value, (list, tuple)):
        return [lean(one, row=True) for one in cast(list[Any], value)]
    return value


def _paths(value: Any, prefix: str = '') -> list[tuple[str, Any]]:
    """All held paths and values, traversing list items without adding numeric path segments."""
    found: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, one in cast(dict[str, Any], value).items():
            path = f'{prefix}.{key}' if prefix else key
            found.append((path, one))
            found.extend(_paths(one, path))
    elif isinstance(value, list):
        for one in cast(list[Any], value):
            found.extend(_paths(one, prefix))
    return found


def _held_fields(rows: list[dict[str, Any]]) -> list[str]:
    """Every raw field path held by any row, including empty containers and nested list items."""
    return list(dict.fromkeys(key for row in rows for key, _ in _paths(row)))


def _named(key: str, fields: tuple[str, ...]) -> bool:
    """A whole path, a selected ancestor path, or a bare leaf name."""
    return any(key == one or key.startswith(f'{one}.') or key.rsplit('.', 1)[-1] == one for one in fields)


def _check(rows: list[dict[str, Any]], shape: Shape) -> None:
    """Refuse an explicitly requested field or status filter absent from every raw row."""
    if not rows or not (shape.fields or shape.status_equals):
        return
    held = _held_fields(rows)
    unheld = [one for one in shape.fields if not any(_named(key, (one,)) for key in held)]
    if unheld:
        raise Unheld(f'No record here holds {", ".join(unheld)}; they hold {", ".join(held)}.')
    if shape.status_equals and not any(key in STATUS for key in held):
        raise Unheld(f'status_equals compares {", ".join(STATUS)}, which no record here holds; they hold '
                     f'{", ".join(held)}. must_contain finds a value in any field.')


def _trim(value: Any, fields: tuple[str, ...], prefix: str = '') -> Any:
    """Project the same field paths checked on raw values, preserving nested list shape."""
    if isinstance(value, list):
        return [_trim(one, fields, prefix) for one in cast(list[Any], value)]
    if not isinstance(value, dict):
        return value
    kept: dict[str, Any] = {}
    for key, one in cast(dict[str, Any], value).items():
        path = f'{prefix}.{key}' if prefix else key
        if _named(path, fields):
            kept[key] = one
        elif isinstance(one, (dict, list)) and (any(field.startswith(f'{path}.') for field in fields) or
                                               any(_named(held, fields) for held, _ in _paths(one, path))):
            kept[key] = _trim(one, fields, path)
    return kept


def _records(value: Any) -> bool:
    if not isinstance(value, list):
        return False
    items = cast(list[Any], value)
    return bool(items) and all(isinstance(one, dict) for one in items)


def _rows_key(data: dict[str, Any]) -> str | None:
    """The longest list of records, or an empty result envelope. An empty detail list is not a record set."""
    lists = [(len(cast(list[Any], one)), key) for key, one in data.items()
             if isinstance(one, list) and one and all(isinstance(item, dict) for item in cast(list[Any], one))]
    if lists:
        return max(lists)[1]
    if data.get('results') == []:
        return 'results'
    return next((key for key, one in data.items() if one == []), None) if len(data) == 1 else None


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
        if isinstance(value, dict) and value:
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
    if isinstance(value, str) and value == '':
        return '""'
    if isinstance(value, list) and value and _values(cast(list[Any], value)):
        return ', '.join(_plain(one) for one in cast(list[Any], value))
    return value if isinstance(value, str) else compact(value) if not isinstance(value, (int, float)) else str(value)


def _cell(value: Any) -> str:
    return _plain(value).replace('\\', '\\\\').replace('|', '\\|').replace('\n', '\\n')


def table(rows: list[dict[str, Any]], fields: tuple[str, ...] = (), name: str = '') -> str:
    """Records as a table: the header, the fields in the order they first appear, or those named; then a line each. A
    Nested lists retain an empty-list marker or record count in the parent table, then their own table. Each child
    row is led by a scalar parent field, or its row number when every selected parent field is a nested list."""
    flat = [_flat(row) for row in rows]
    columns: list[str] = []
    for row in flat:
        columns += [key for key in row if key not in columns]
    if fields:
        columns = [key for key in columns if _named(key, fields)]
    inner = [key for key in columns if any(_records(row.get(key)) for row in flat)]
    lines = ['|'.join(columns)]
    lines += ['|'.join(f'({len(row[key])} records)' if _records(row.get(key)) else
                      _cell(row[key]) if key in row else '' for key in columns) for row in flat]
    lead = next((key for key in columns if key not in inner), 'row')
    for key in inner:
        nested = [{lead: row.get(lead, number), **one} for number, row in enumerate(flat, 1) if _records(row.get(key))
                  for one in cast(list[dict[str, Any]], row[key])]
        lines += [f'{name}.{key}:' if name else f'{key}:', table(nested)]
    return '\n'.join(lines)


def _lines(name: str, value: Any) -> list[str]:
    """One field as the agent reads it: `name: value`; a nested record's fields as `name.field: value`; a list of
    records as `name:` and its table; text of several lines indented under `name:`."""
    if isinstance(value, dict):
        if not value:
            return [f'{name}: {{}}']
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
    """Count rows holding each value. A repeated value within a nested list counts once per outer row."""
    paths = [_paths(row) for row in rows]
    held = _held_fields(rows)
    named = tuple(dict.fromkeys(key for field in fields for key in
                               ([field] if '.' in field else
                                [key for key in held if key.rsplit('.', 1)[-1] == field] or [field]))) or \
        tuple(key for key in STATUS if key in held)
    by: dict[str, dict[str, int]] = {}
    for key in named:
        tally: dict[str, int] = {}
        for row in paths:
            values = [value for path, value in row if path == key]
            labels = {('(none)' if value is None else value if isinstance(value, str) else compact(value))
                      for value in values} if values else {'(missing)'}
            for label in labels:
                tally[label] = tally.get(label, 0) + 1
        by[key] = dict(sorted(tally.items(), key=lambda pair: (-pair[1], pair[0])))
    return {'total': len(rows), **({'by': by} if by else {})}


def shaped(result: Any, shape: Shape, more: str, *, record: bool = False) -> tuple[str, dict[str, Any] | None]:
    """Validate, filter and project typed results before applying the requested representation."""
    data = plain(result)
    wrapped = not isinstance(data, dict)
    held: dict[str, Any] = {'results': data} if wrapped else cast(dict[str, Any], data)
    key = _rows_key(held)
    rows = cast(list[dict[str, Any]], held[key]) if key is not None else [held]
    _check(rows, shape)
    if key is not None and (shape.filtered or shape.view == 'count'):
        held = {**held, key: _kept(rows, shape)}
    if shape.fields:
        held = {**held, key: _trim(held[key], shape.fields)} if key is not None else \
            cast(dict[str, Any], _trim(held, shape.fields))
    if shape.view == 'count':
        rows = cast(list[dict[str, Any]], held.get(key, []) if key is not None else [held])
        found = counted(rows, shape.fields)
        return compact(found), found
    if shape.view == 'full':
        return compact(held['results'] if wrapped else held), None if wrapped else held
    if not shape.fields:
        held = cast(dict[str, Any], lean(held, row=record))
    elif key is not None:
        selected = held[key]
        held = cast(dict[str, Any], lean(held, row=record))
        held[key] = selected  # selected rows retain nulls and ids; unselected envelope metadata stays lean
    if key == 'results' or wrapped:  # a list given trimmed, so the call says once how to ask for more; a record
        shape.given.append(True)  # with a list inside it, such as a where read's joins, is no list to narrow
    cut = ''
    if key is not None and not shape.filtered and len(held[key]) > LIST_MOST:
        rest = len(held[key]) - LIST_MOST
        held = {**held, key: held[key][:LIST_MOST]}
        cut = more.replace('<n/>', str(rest))
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
