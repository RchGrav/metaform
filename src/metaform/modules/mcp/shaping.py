"""What a tool's result carries over MCP, MCP-039: the fields the next decision needs, in as few tokens as hold them.

A result goes to the agent's context whole, and the agent reads every field of it, so by default a module tool's result
is given lean, `view` triage: no field that holds nothing (None, empty text, an empty list or object), no `false` inside
a list's rows, where it is the default, and no internal id where an Address names the thing; a list of records comes as
a table, one header line and one line a record, `a|b|c`, with a nested record's fields as `parent.field`; the rest as
`key: value` lines, and what is nested deeper as compact JSON. `view` full gives every field as compact JSON; `fields`
keeps only the fields named; `view` count gives no records, only how many there are and how many hold each value of the
fields named, for a question about a distribution that would otherwise be answered by reading every record.

A list is filtered on the server, so the agent never reads the records it would discard: `must_contain` keeps the rows
that hold the text anywhere, `status_equals` those whose status, state, column or condition is the value. A list of more
than LIST_MOST records with neither filter is cut there, with how many more there are and how to narrow it.

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
SCHEMAS: dict[str, dict[str, Any]] = {
    VIEW: {'type': 'string', 'enum': list(VIEWS)},
    FIELDS: {'type': 'array', 'items': {'type': 'string'}},
    MUST_CONTAIN: {'type': 'string'},
    STATUS_EQUALS: {'type': 'string'},
}
# Fields no next decision reads: how a record is kept, not what it says. The Address or the reference names the thing.
DEAD = frozenset({'node_kind', 'node_id', 'layer_id', 'is_work', 'age_seconds', 'existing', 'differs', 'orphaned',
                  'position'})
STATUS = ('status', 'state', 'column', 'condition')  # what status_equals compares
LIST_MOST = 25  # the most rows a list is given without a filter


@dataclasses.dataclass(frozen=True)
class Shape:
    """How one call asks for its result: its view, the fields it keeps, and its filters. `given` holds True once a
    result was given in this shape, so the call can say once how to ask for more."""
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
    and what is wrong with them, or None."""
    given = {key: arguments.pop(key) for key in ARGUMENTS if key in arguments and key not in declared}
    view = given.get(VIEW, 'triage')
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


def lean(value: Any, *, row: bool = False) -> Any:
    """`value` without what holds nothing: None, empty text, lists and objects, the DEAD fields, and an id whose
    Address is beside it (`receiver` beside `receiver_address`); with `row`, inside a list's rows or a lookup's record,
    `false` too, the default there."""
    if isinstance(value, dict):
        given = cast(dict[str, Any], value)
        kept: dict[str, Any] = {}
        for key, one in given.items():
            if key in DEAD or given.get(f'{key}_address'):
                continue
            made = lean(one, row=row)
            if made is None or made == '' or made == [] or made == {} or (row and made is False):
                continue
            kept[key] = made
        return kept
    if isinstance(value, (list, tuple)):
        return [lean(one, row=True) for one in cast(list[Any], value)]
    return value


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


def _flat(row: dict[str, Any]) -> dict[str, Any]:
    """A row with each nested object's fields as `parent.field`, one level down."""
    found: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, dict):
            for inner, one in cast(dict[str, Any], value).items():
                found[f'{key}.{inner}'] = one
        else:
            found[key] = value
    return found


def _cell(value: Any) -> str:
    text = value if isinstance(value, str) else compact(value)
    return text.replace('\\', '\\\\').replace('|', '\\|').replace('\n', '\\n')


def table(rows: list[dict[str, Any]], fields: tuple[str, ...] = ()) -> str:
    """Records as a table: the header, the fields in the order they first appear, or those named; then a line each."""
    flat = [_flat(row) for row in rows]
    columns: list[str] = []
    for row in flat:
        columns += [key for key in row if key not in columns]
    if fields:
        columns = [key for key in columns if key in fields or key.split('.', 1)[0] in fields]
    lines = ['|'.join(columns)]
    lines += ['|'.join(_cell(row[key]) if key in row else '' for key in columns) for row in flat]
    return '\n'.join(lines)


def counted(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> dict[str, Any]:
    """How many rows there are, and for each field named, or each status field when none is, how many hold each of its
    values, the most first."""
    flat = [_flat(row) for row in rows]
    named = fields or tuple(key for key in STATUS if any(key in row for row in flat))
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
    data = lean(data, row=record)
    wrapped = not isinstance(data, dict)
    held: dict[str, Any] = {'results': data} if wrapped else cast(dict[str, Any], data)
    key = _rows_key(held)
    if key is not None and (shape.filtered or shape.view == 'count'):
        held = {**held, key: _kept(cast(list[dict[str, Any]], held[key]), shape)}
    if shape.view == 'count':
        rows = cast(list[dict[str, Any]], held.get(key, []) if key is not None else [])
        found = counted(rows, shape.fields)
        return compact(found), found
    cut = ''
    if key is not None and not shape.filtered and len(held[key]) > LIST_MOST:
        rest = len(held[key]) - LIST_MOST
        held = {**held, key: held[key][:LIST_MOST]}
        cut = more.replace('<n/>', str(rest))
    lines: list[str] = []
    for name, value in held.items():
        if name == key or (shape.fields and key is None and name not in shape.fields):
            continue
        if _records(value):  # another list of records, such as a map entry's roots beside its elements
            lines += [f'{name}:', table(cast(list[dict[str, Any]], value))]
            continue
        lines.append(f'{name}: {value if isinstance(value, (str, int, float, bool)) else compact(value)}')
    if key is not None:
        rows = cast(list[dict[str, Any]], held[key])
        if not wrapped:
            lines.append(f'{key}:')
        lines.append(table(rows, shape.fields) if rows else '(none)')
    if cut:
        lines.append(cut)
    structured = None if wrapped else held
    return '\n'.join(lines), structured
