"""Overlay definitions, and the check of an overlay's records against its definition.

An overlay is defined beneath the `overlay` root. The definition is the step that carries `instruction` (with
`description`); each step directly beneath it is one field of the overlay's records, carrying `type`, `rule`,
`example` and, when the field may be left out, `optional`. The overlay's key at an element is the definition's steps
after `overlay`, reversed and joined with underscores: `overlay.specifications.project` gives `project_specifications`.

The definition is the schema an agent reads, the check the tool applies, and the text of each refusal: a wrong record
is refused naming the field, quoting its rule and showing its example, and the remediation keeps every value the
command gave correctly and puts a placeholder, the field's name in angle brackets, where a value is wrong or missing.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

from metaform.project.forms import Key, Refusal, as_list, as_object, is_text, other_project, parse, refuse, replaced
from metaform.project.store import ELEMENT_FIELDS, Scalar

# Names an overlay's key cannot take: the fields of an element, the words the tool answers in their place, and the
# parts of an addressed read's answer.
RESERVED = (*ELEMENT_FIELDS, 'refs', 'uri', 'dependencies', 'providers', 'wanted_by', 'overlays', 'position', 'record',
            'revision')
WANT_ORDER = ('element', 'why', 'how', 'direction', 'ref')


@dataclass(frozen=True)
class Field:
    name: str
    type: str
    rule: str
    example: Scalar
    optional: bool

    @property
    def kind(self) -> str:
        return 'choice' if '|' in self.type else self.type

    @property
    def choices(self) -> list[str]:
        return [choice.strip() for choice in self.type.split('|')]

    @property
    def column(self) -> str:
        return {'number': 'DOUBLE', 'boolean': 'BOOLEAN'}.get(self.kind, 'STRING')

    def expected(self, project: str) -> str:
        if self.kind == 'choice':
            choices = self.choices
            return ', '.join(choices[:-1]) + ' or ' + choices[-1]
        return {'text': 'text that is not blank', 'number': 'a number', 'boolean': 'true or false',
                'address': f'the path of an element of {project}'}[self.kind]

    def accepts(self, value: object, project: str) -> bool:
        if is_placeholder(value):  # a corrected command run without its values supplied
            return False
        if self.kind == 'text':
            return is_text(value)
        if self.kind == 'number':
            return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        if self.kind == 'boolean':
            return isinstance(value, bool)
        if self.kind == 'choice':
            return isinstance(value, str) and value in self.choices
        try:
            address = parse(value)
        except Refusal:
            return False
        return address.project == project and not address.in_overlay


@dataclass
class Definition:
    address: str
    key: str
    description: str | None
    instruction: str
    fields: dict[str, Field] = field(default_factory=dict[str, Field])

    @property
    def order(self) -> list[str]:
        names = [name for name in WANT_ORDER if name in self.fields] if self.key == 'wants' else list(self.fields)
        return names if 'ref' in names else [*names, 'ref']


def key_of(address: str) -> str:
    """The overlay's key from its definition's address, without the project's name."""
    return '_'.join(reversed(address.split('.')[1:]))


def encode_example(value: Scalar) -> str | None:
    return value if isinstance(value, str) or value is None else json.dumps(value)


def decode(kind: str, value: Scalar) -> Scalar:
    """A stored value in the form its type gives it: a whole number comes back without a fraction. Text that is
    not a value of the type stays text, so the check of an example against its type still sees it."""
    if kind == 'number' and isinstance(value, str):
        try:
            number: object = json.loads(value)
        except ValueError:
            return value
        if isinstance(number, (int, float)) and not isinstance(number, bool):
            value = number
    if kind == 'boolean' and value in ('true', 'false'):
        return value == 'true'
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def definitions(parts: dict[str, dict[str, Scalar]]) -> dict[str, Definition]:
    """Every definition among the parts, by key."""
    found: dict[str, Definition] = {}
    for address, values in parts.items():
        instruction = values.get('instruction')
        if not isinstance(instruction, str) or '.' not in address:
            continue
        description = values.get('description')
        definition = Definition(address, key_of(address), description if isinstance(description, str) else None,
                                instruction)
        for child, child_values in parts.items():
            kind = child_values.get('type')
            if child.rpartition('.')[0] == address and isinstance(kind, str):
                name = child.rpartition('.')[2]
                probe = Field(name, kind, '', None, False)
                definition.fields[name] = Field(name, kind, str(child_values.get('rule') or ''),
                                                decode(probe.kind, child_values.get('example')),
                                                child_values.get('optional') is True)
        found[definition.key] = definition
    return found


def placeholder(name: str) -> str:
    """What stands in a corrected command for a value only the agent can supply: the field's name in angle brackets.
    The tool refuses it as a value, so a corrected command run as it is stores nothing the agent did not write."""
    return f'<{name}>'


def is_placeholder(value: object) -> bool:
    return isinstance(value, str) and len(value) > 2 and value[0] == '<' and value[-1] == '>' and '<' not in value[1:]


def corrected_record(definition: Definition, record: dict[str, object] | None = None,
                     wrong: tuple[str, ...] = ()) -> dict[str, object]:
    """A whole record for a corrected command: the values the record gives correctly, and a placeholder for every
    field that is wrong or missing. An example value is never put in: it belongs to the message, where it is read
    and not stored."""
    given = record or {}
    out: dict[str, object] = {name: placeholder(name) if name in wrong else value for name, value in given.items()}
    for name in definition.order:
        if name not in out and name in definition.fields and (not definition.fields[name].optional or not given):
            out[name] = placeholder(name)
    return out


@dataclass
class Records:
    """The records of one overlay at one element in a command, where they sit in the command, and the holder."""
    definition: Definition
    holder: str
    project: str
    keys: list[Key]
    command: object

    def place(self, index: int, record: dict[str, object]) -> str:
        if self.definition.key == 'wants':
            return f"the want '{record.get('element')}' at '{self.holder}'"
        return f"{self.definition.key} record {index} at '{self.holder}'"

    def fixed(self, index: int, record: dict[str, object], wrong: tuple[str, ...]) -> object:
        return replaced(self.command, [*self.keys, index], corrected_record(self.definition, record, wrong))

    def rules(self, names: list[str]) -> str:
        return ' '.join(f'{name}: {self.definition.fields[name].rule} Example: {self.definition.fields[name].example!r}.'
                        for name in names if name in self.definition.fields)

    def check(self, records: list[object], partial: bool) -> list[dict[str, Scalar]]:
        """Each record, in order: an object, its ref, the names it takes, each field in the command's order, then the
        fields it lacks. `partial` is true for the wants of the element an update names, where a record gives its
        key and only the fields to change. Returns the records, each value in its stored form."""
        out: list[dict[str, Scalar]] = []
        definition = self.definition
        for index, item in enumerate(records):
            record = as_object(item)
            if record is None:
                raise refuse(f"{definition.key} record {index} at '{self.holder}' must be an object of fields: "
                             f"{', '.join(definition.order)}", self.fixed(index, {}, ()))
            # a record's identity is the store's own (F02): a record sent back as it was read is taken, and its
            # record and revision are never stored from what is sent
            record = {name: value for name, value in record.items() if name not in ('record', 'revision')}
            self.ref(index, record)
            place = self.place(index, record)
            extra = [name for name in record if name not in definition.fields and name != 'ref']
            if extra:
                kept = {name: value for name, value in record.items() if name not in extra}
                raise refuse(f"{place} does not take: {', '.join(extra)}; a {definition.key} record takes "
                             f"{', '.join(definition.order)}", self.fixed(index, kept, ()))
            for name, value in record.items():
                if name == 'ref':
                    continue
                spec = definition.fields[name]
                if spec.optional and value is None:
                    continue
                if not spec.accepts(value, self.project):
                    if spec.kind == 'address' and isinstance(value, str) and _other(value, self.project):
                        raise other_project(value, self.project, place)
                    remedy = self.fixed(index, record, (name,))
                    if name == 'direction' and value in ('sends', 'receives'):
                        remedy = replaced(self.command, [*self.keys, index, name], str(value)[:-1])
                    raise refuse(f'{name} at {place} must be {spec.expected(self.project)}. {self.rules([name])}',
                                 remedy)
            missing = [name for name, spec in definition.fields.items() if not spec.optional and name not in record]
            if partial:
                if all(name in ('element', 'ref') or name not in record for name in definition.fields):
                    raise refuse(f'{place} has no fields; give why, how or direction',
                                 self.fixed(index, record, ()))
            elif missing:
                ordered = [name for name in definition.order if name in missing]
                if definition.key == 'wants':
                    raise Refusal('WANT_INCOMPLETE', f"'{self.holder}' wants '{record.get('element')}': the want has "
                                  f"no {', '.join(ordered)}. {self.rules(ordered)}", self.fixed(index, record, ()))
                raise refuse(f'{place} has no {", ".join(ordered)}. {self.rules(ordered)}',
                             self.fixed(index, record, ()))
            out.append({name: _stored(value) for name, value in record.items()})
        return out

    def ref(self, index: int, record: dict[str, object]) -> None:
        """A record's own single ref. Wants answer refs and uri with one want per artifact (`forms.py`)."""
        place = self.place(index, record)
        for name in ('refs', 'uri'):
            if name in record and name not in self.definition.fields:
                items = as_list(record[name])
                found = items if items is not None else [record[name]]
                message = f'{name} at {place} is not a field; ref holds the one text the record is about'
                if len(found) > 1:
                    raise refuse(f'{message}; the list holds {len(found)} items, and the tool does not choose which one')
                one = found[0] if found and is_text(found[0]) else '<ref>'
                fixed = replaced(replaced(self.command, [*self.keys, index, name]), [*self.keys, index, 'ref'], one)
                raise refuse(message, fixed)
        if record.get('ref') is None or is_text(record['ref']):
            return
        items = as_list(record['ref'])
        if items is not None and len(items) > 1:
            raise refuse(f'ref at {place} is one text, not a list; the list holds {len(items)} items, and the tool '
                         'does not choose which one')
        one = items[0] if items and is_text(items[0]) else '<ref>'
        raise refuse(f'ref at {place} must be one text that is not blank', replaced(
            self.command, [*self.keys, index, 'ref'], one))


def _other(text: str, project: str) -> bool:
    try:
        return parse(text).project != project
    except Refusal:
        return False


def _stored(value: object) -> Scalar:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return json.dumps(value)
