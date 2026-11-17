"""The form of a command, checked by hand before the map is read.

`check` refuses a command that does not have the form the `project` tool takes. It reads only the command, never
the map. The first problem found gives the refusal, in this order:

1. The number of entries: a command is an object with one entry.
2. The key: `add`, `update`, `delete`, `orphaned`, `map` and `help` are commands; any other key is a path to read.
3. For `add`, `update` and `delete`, the value is an object with one entry, and its key is a path.
4. The value at the path.
5. Each field, in the order the command gives them. An object is a step beneath, and its fields are checked before
   the next field of the element above. In a want record: the record is an object, the procedure's words, its
   element, then refs or uri. The rest of a record is checked against its overlay's definition (`overlays.py`).

Every message is written by hand. A remediation is the refused command with only what the refusal names corrected,
or `None` when the tool would have to guess.
"""
from __future__ import annotations

import copy
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from metaform.project.store import ROOT_FIELDS, ROOT_OVERLAYS
from metaform.project.texts import COMMANDS, ROLE_PLACEHOLDER, ROLE_WORDS, ROLES

Key = str | int
ROOTS = ('code', 'document', 'media', 'data', 'upstream', 'downstream', 'overlay')
TEXT_FIELDS = ('technical_name', 'name', 'role', 'status')
PART_TEXT = ('description', 'instruction', 'rule')
# The earlier spellings of not built, each answered with `unbuilt`, the plain word the founder chose on 2026-11-17 and the
# page's own; `un_built` is the Rust form's spelling of it.
LEGACY_STATUS = ('missing', 'MISSING', 'BKN', 'broken', 'todo', 'TODO', 'un_built')
WANT_WORDS = ('element', 'why', 'how', 'direction')
PROCEDURE_WORDS = {'pe': 'element', 'provider': 'element', 'op': 'why', 'purpose': 'why', 'ef': 'how',
                   'ifd': 'direction'}
# A step survives storage as camelCase and back only when each underscore comes before a letter (R-4.11 of the Rust
# form, `metaform-core/src/names.rs`): `queue_2` would come back `queue2`.
STEP = re.compile(r'[a-z0-9]+(?:_[a-z][a-z0-9]*)*\Z')
ONE_ENTRY = ('a command has one entry: add, update, delete, orphaned, map, help, or a path to read, such as '
             '{"mashtrac.code.masher.widget": {}}')
REF_FORM = 'the entry point of this functionality, or a discrete reference to it'
DELETE_FORM = ('delete takes {} to delete the element, or {"wants": ["<path>"]} to remove wants; '
               '{"wants": [{"element": "<path>", "ref": "<ref>"}]} removes the one want about that artifact; '
               '{"<overlay>": [0, 2]} removes the records at those positions of another overlay\'s list, and '
               '{"<overlay>": ["r-..."]} removes records by the record ids a read gives')
STEP_FORM = ('a step is lowercase letters and digits, with single underscores between words, each before a letter, '
             'so that it survives storage')


class Refusal(Exception):
    def __init__(self, code: str, message: str, remediation: object = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.remediation = remediation


def refuse(message: str, remediation: object = None) -> Refusal:
    return Refusal('FIELD_MISMATCH', message, remediation)


def as_object(value: object) -> dict[str, object] | None:
    if isinstance(value, dict) and all(isinstance(key, str) for key in cast(dict[object, object], value)):
        return cast(dict[str, object], value)
    return None


def as_list(value: object) -> list[object] | None:
    return cast(list[object], value) if isinstance(value, list) else None


def is_text(value: object) -> bool:
    """Text that is not blank."""
    return isinstance(value, str) and bool(value.strip())


def is_name(value: object) -> bool:
    return isinstance(value, str) and STEP.match(value) is not None


def fixed_name(text: str) -> str | None:
    """The nearest name that survives storage, as the Rust form suggests it (`suggest_segment`): lowercased, single
    underscores, a word that starts with a digit joined to the word before it; None when that is no name."""
    fixed = ''
    for word in (part for part in text.lower().split('_') if part):
        fixed += ('_' if fixed and word[0].isalpha() else '') + word
    return fixed if fixed != text and STEP.match(fixed) else None


@dataclass(frozen=True)
class Address:
    project: str
    steps: tuple[str, ...]

    @property
    def address(self) -> str:
        """The address without the project's name, as the store keys it."""
        return '.'.join(self.steps)

    @property
    def full(self) -> str:
        return full(self.project, self.address)

    @property
    def in_overlay(self) -> bool:
        return self.steps[0] == 'overlay'

    def child(self, step: str) -> Address:
        return Address(self.project, (*self.steps, step))


def full(project: str, address: str) -> str:
    """The path of a store address: the project's name and the address, or the name alone for the root, `''`."""
    return f'{project}.{address}' if address else project


def parse(text: object, rename: Callable[[str], object] | None = None) -> Address:
    """A path: the project's name, a root, and the steps beneath it. `rename` builds the command with the path
    corrected, for a path that only needs lowercase letters or single underscores."""
    steps = text.split('.') if isinstance(text, str) else []
    if not all(is_name(step) for step in steps) or len(steps) == 0:
        fixed = [fixed_name(step) or step for step in steps]
        suggestion = '.'.join(fixed) if steps and all(is_name(step) for step in fixed) else None
        corrected = rename(suggestion) if rename and suggestion else None
        # a name the store would not give back exactly, with the name it would, is the Rust form's round-trip refusal
        raise Refusal('NAME_ROUND_TRIP_FAILURE' if corrected is not None else 'FIELD_MISMATCH',
                      f"'{text}' is not a path: a path is the project's name and then steps, joined by periods, such "
                      f"as mashtrac.code.masher.widget; {STEP_FORM}", corrected)
    if len(steps) == 1:
        raise Refusal('ROOT_SCOPE_NOT_ALLOWED', f"'{text}' names a project and no root: after the project's name a "
                      f"path takes one of: {', '.join(ROOTS)}")
    if steps[0] in ROOTS:  # the project's name left off: every path leads with it, since the tool keeps no session
        raise Refusal('ROOT_SCOPE_NOT_ALLOWED', f"'{text}' starts at the root '{steps[0]}' with no project named: a "
                      f"path leads with the project's name, such as mashtrac.{text}; "
                      '{"map": {}} lists the projects')
    if steps[1] not in ROOTS:
        raise Refusal('ROOT_SCOPE_NOT_ALLOWED',
                      f"'{text}': the root scope '{steps[1]}' is not one of: {', '.join(ROOTS)}")
    return Address(steps[0], tuple(steps[1:]))


def other_project(text: str, project: str, place: str) -> Refusal:
    other = text.split('.')[0]
    return refuse(f"'{text}' is in the project '{other}', and {place} names an element of '{project}'; a link to "
                  f"another project is a ref of project://{other} on an element")


_REMOVE = object()


def replaced(command: object, keys: list[Key], value: object = _REMOVE) -> object:
    """The command with the value at `keys` replaced, or removed when no value is given."""
    out = copy.deepcopy(command)
    at = out
    for key in keys[:-1]:
        at = cast(dict[str, object], at)[key] if isinstance(key, str) else cast(list[object], at)[key]
    last = keys[-1]
    if isinstance(last, int):
        cast(list[object], at)[last] = value
    elif value is _REMOVE:
        cast(dict[str, object], at).pop(last, None)
    else:
        cast(dict[str, object], at)[last] = value
    return out


def renamed(command: object, keys: list[Key], new: str) -> object:
    """The command with the key at `keys` renamed, its place in the object kept."""
    above = keys[:-1]
    holder = command
    for key in above:
        holder = cast(dict[str, object], holder)[key] if isinstance(key, str) else cast(list[object], holder)[key]
    items = cast(dict[str, object], holder)
    out = {new if name == keys[-1] else name: value for name, value in items.items()}
    return replaced(command, above, copy.deepcopy(out)) if above else out


def check(command: object) -> tuple[str, object]:
    """Refuse a command that does not have the tool's form; return its key and value."""
    entries = as_object(command)
    if entries is None or len(entries) != 1:
        raise refuse(ONE_ENTRY)
    ((key, body),) = entries.items()
    if key == 'map':
        if body != {} and not isinstance(body, str):
            raise refuse('map takes the name of a project, or {} for the names of the projects', {'map': {}})
        if isinstance(body, str):
            project_name(body, 'map')
    elif key == 'orphaned':
        if not isinstance(body, str):
            raise refuse('orphaned takes the name of a project, such as {"orphaned": "mashtrac"}',
                         {'orphaned': '<project>'})
        project_name(body, 'orphaned')
    elif key == 'help':
        if body != {} and not (isinstance(body, str) and body):
            raise refuse('help takes {} or the name of a command', {'help': {}})
    elif key in ('add', 'update', 'delete'):
        if root_of(body) is not None:
            root_write(key, body)
        else:
            Form(command).write(key, body)
    elif key == 'goto':
        target = body if isinstance(body, str) else None
        remedy: object = None
        if target is not None and _parses(target):
            remedy = {target: {}}
        raise refuse('there is no goto: a read of a path returns its fields, wanted_by and its overlays, such as '
                     '{"mashtrac.code.masher.widget": {}}', remedy)
    elif is_name(key) and key not in ROOTS:
        if body != {}:
            raise refuse(f"a read of the project's root takes {{}}, such as {{\"{key}\": {{}}}}", {key: {}})
    elif '.' not in key:
        raise refuse(f"'{key}' is not a command or a path: the commands are {', '.join(COMMANDS)}, and a path to read "
                     "starts with the project's name, such as mashtrac.code.masher.widget", {'help': {}})
    else:
        read(key, body)
    return key, body


def root_of(body: object) -> str | None:
    """The project a write names when its one path is the project's root, the name alone."""
    entries = as_object(body)
    if entries is None or len(entries) != 1:
        return None
    path = next(iter(entries))
    return path if is_name(path) and path not in ROOTS else None


def root_write(verb: str, body: object) -> None:
    """A write to the project's root, which holds the project's own id, name and project, each a text, and the
    records of the overlays `ROOT_OVERLAYS` names, each a list: the specification's blocks, the project's own
    description (F07). Any other overlay is held at an element, and is refused here by name."""
    ((project, value),) = cast(dict[str, object], body).items()
    takes = (f"the root of a project takes {', '.join(ROOT_FIELDS)}, and the records of {', '.join(ROOT_OVERLAYS)}; "
             f"an element is written at its own path, such as {project}.code.masher.widget")
    if verb == 'delete':
        raise refuse(f"'{project}' is the root of the project and cannot be deleted")
    fields = as_object(value)
    if not fields:
        raise refuse(f"{verb} needs at least one field at '{project}': {takes}")
    for name, given in fields.items():
        if name == 'technical_name':  # as the Rust form answers it (`metaform-core/src/rules.rs`): the root is the project
            raise Refusal('TECHNICAL_NAME_ALIGNMENT_FAILURE', f"'{project}': the root is the project and has no "
                          'technical_name', {'update': {project: {'technical_name': None}}})
        if name in ROOT_OVERLAYS:
            if as_list(given) is None and not (given is None and verb == 'update'):
                raise refuse(f"{name} at '{project}' is a list of records", {verb: {project: {name: [given]}}})
            continue
        if as_list(given) is not None:
            raise Refusal('OVERLAY_NOT_AT_ROOT', f"'{name}' at '{project}': the root of a project holds records of "
                          f"{', '.join(ROOT_OVERLAYS)} only, the project's own description. Write {name} records at "
                          f"an element, such as {project}.code.masher.widget")
        if name not in ROOT_FIELDS:
            raise refuse(f"'{name}' at '{project}': {takes}")
        if given is None and verb == 'update':
            continue
        if not is_text(given):
            raise refuse(f"{name} at '{project}' must be text that is not blank")


def _parses(text: str) -> bool:
    try:
        parse(text)
    except Refusal:
        return False
    return True


def accepted(command: object) -> object:
    """The command, if this check accepts it; a remediation is never refused in turn."""
    try:
        check(command)
    except Refusal:
        return None
    return command


def project_name(text: str, key: str) -> None:
    if not is_name(text):
        fixed = fixed_name(text)
        raise refuse(f"'{text}' is not a project name: a project's name is one step; {STEP_FORM}",
                     {key: fixed} if fixed else None)


def read(key: str, body: object) -> None:
    """An addressed read: a path, and each overlay it names with {} as its value."""
    address = parse(key, lambda fixed: {fixed: body})
    form = f'a read names each overlay with {{}} as its value, such as {{"{address.full}": {{"wants": {{}}}}}}'
    named = as_object(body)
    if named is None:
        raise refuse(form, {key: {}})
    for name, value in named.items():
        if not is_name(name):
            raise refuse(f"'{name}' is not an overlay name: an overlay's name is one step, such as wants")
        if value != {}:
            corrected: dict[str, object] = {each: {} for each in named}
            raise refuse(form, accepted({key: corrected}))


def technical_name(address: Address, value: str) -> str | None:
    """The corrected technical_name, if this one is not a leading run of the address's words read in reverse."""
    reversed_words = [word for step in reversed(address.steps) for word in step.split('_')]
    words = value.split()
    if words and len(words) <= len(reversed_words) and words == reversed_words[:len(words)]:
        return None
    keep = max(len(reversed_words) - len(address.steps[0].split('_')), 1)
    return ' '.join(reversed_words[:keep])


class Form:
    """The checks of one write. A remediation is this command with one value corrected."""

    def __init__(self, command: object) -> None:
        self.command = command

    def fix(self, keys: list[Key], value: object = _REMOVE) -> object:
        return replaced(self.command, keys, value)

    def write(self, verb: str, body: object) -> None:
        entries = as_object(body)
        if entries is None or len(entries) != 1:
            first = next(iter(entries.items()), None) if entries else None
            raise refuse(f'{verb} takes one path; send one command for each element',
                         accepted({verb: {first[0]: first[1]}}) if first else None)
        ((path, value),) = entries.items()
        address = parse(path, lambda fixed: renamed(self.command, [verb, path], fixed))
        if verb == 'delete':
            self.delete(address, value, [verb, path])
            return
        fields = as_object(value)
        if fields is None:
            raise refuse(f"{verb} takes an object of fields at '{address.full}'")
        if not fields:
            raise refuse(f"{verb} needs at least one field at '{address.full}'")
        if address.in_overlay:
            self.part(fields, address, [verb, path], verb == 'update')
        else:
            self.fields(fields, address, [verb, path], verb == 'update')

    def name(self, key: str, address: Address, keys: list[Key]) -> None:
        if not is_name(key):
            fixed = fixed_name(key)
            raise Refusal('NAME_ROUND_TRIP_FAILURE' if fixed else 'FIELD_MISMATCH',
                          f"'{key}' at '{address.full}' is not a field name: {STEP_FORM}",
                          renamed(self.command, keys, fixed) if fixed else None)

    def fields(self, fields: dict[str, object], address: Address, keys: list[Key], update: bool) -> None:
        """The fields of one element, in the command's order; an object is a step beneath."""
        where = address.full
        for key, value in fields.items():
            here = [*keys, key]
            self.name(key, address, here)
            if key == 'wants':
                self.wants(value, address, here)
            elif key == 'dependencies':
                listed = as_list(value)
                records = [in_tool_words(record) for record in listed] if listed is not None else (
                    keyed_records(value) or value)
                moved = replaced(self.fix(here), [*keys, 'wants'], records)
                raise refuse(f"dependencies at '{where}' is not a field; wants holds what the procedure calls "
                             "dependency records", moved)
            elif key in ('uri', 'refs'):
                one, several = single(value)
                message = f"{key} at '{where}' is not a field; ref holds one text: {REF_FORM}"
                if several:
                    raise refuse(f'{message}; the list holds {several} items, and the tool does not choose which one')
                raise refuse(message, replaced(self.fix(here), [*keys, 'ref'], one or '<ref>'))
            elif as_object(value) is not None:
                self.fields(cast(dict[str, object], value), address.child(key), here, update)
            elif key == 'ref':
                self.ref(value, where, here, update)
            elif value is None and not update:
                if key in TEXT_FIELDS:
                    self.text(key, value, address, here)
                raise refuse(f"{key} at '{where}' cannot be null in add; update removes a field, or an overlay's "
                             "records, with null")
            elif value is None:
                continue
            elif key in TEXT_FIELDS:
                self.text(key, value, address, here)
            elif key in WANT_WORDS or key in PROCEDURE_WORDS:
                record = {'element': '<path>', 'why': '<why>', 'how': '<how>', 'direction': '<direction>'}
                for name, given in fields.items():
                    word = PROCEDURE_WORDS.get(name, name)
                    if word in WANT_WORDS and isinstance(given, str):
                        record[word] = given
                raise refuse(f"{key} at '{where}' is not a field of an element; element, why, how and direction "
                             "belong in a want", {'update': {where: {'wants': [record]}}})
            elif key == 'providers':
                raise refuse(f"providers at '{where}' can hold only elements beneath it; wants holds what an element "
                             "wants")
            elif as_list(value) is None:
                raise refuse(f"'{key}' at '{where}' is not a field of an element: an element takes technical_name, "
                             "name, role, ref and status, a list under a name is an overlay's records, and an object "
                             "is a step beneath")

    def text(self, key: str, value: object, address: Address, here: list[Key]) -> None:
        where = address.full
        if not isinstance(value, str) or not value.strip():
            placeholder = ROLE_PLACEHOLDER if key == 'role' else f'<{key}>'
            raise refuse(f"{key} at '{where}' must be text that is not blank", self.fix(here, placeholder))
        if key == 'status' and value in LEGACY_STATUS:
            raise refuse(f"status at '{where}' cannot be \"{value}\"; use unbuilt for functionality that is not built",
                         self.fix(here, 'unbuilt'))
        if key == 'role' and value not in ROLES:
            raise Refusal('ROLE_TAXONOMY_FAILURE', f"'{where}': role \"{value}\" is not one of: {', '.join(ROLES)}",
                          self.fix(here, ROLE_WORDS.get(value, ROLE_PLACEHOLDER)))
        if key == 'technical_name':
            corrected = technical_name(address, value)
            if corrected is not None:
                words = ' '.join(word for step in reversed(address.steps) for word in step.split('_'))
                raise Refusal('TECHNICAL_NAME_ALIGNMENT_FAILURE',
                              f"'{where}': technical_name \"{value}\" is not the leading words of \"{words}\"",
                              self.fix(here, corrected))

    def ref(self, value: object, where: str, here: list[Key], update: bool) -> None:
        if is_text(value) or (value is None and update):
            return
        one, several = single(value)
        if as_list(value) is not None:
            if several:
                raise refuse(f"ref at '{where}' is one text, not a list; the list holds {several} items, and the tool "
                             "does not choose which one")
            raise refuse(f"ref at '{where}' is one text, not a list", self.fix(here, one or '<ref>'))
        raise refuse(f"ref at '{where}' must be text that is not blank: {REF_FORM}", self.fix(here, '<ref>'))

    def part(self, fields: dict[str, object], address: Address, keys: list[Key], update: bool) -> None:
        """The fields of a part of an overlay definition: description and instruction on a definition, type, rule,
        example and optional on each field beneath it."""
        where = address.full
        for key, value in fields.items():
            here = [*keys, key]
            self.name(key, address, here)
            if as_object(value) is not None:
                words = {'position': "a record's place in its list", 'record': "a record's id, kept for its life",
                         'revision': "how many times a record has changed"}  # the store's own, F02
                if key in words:
                    raise refuse(f"'{key}' at '{where}' cannot name a field or an overlay: it is the tool's word "
                                 f'for {words[key]}')
                self.part(cast(dict[str, object], value), address.child(key), here, update)
            elif as_list(value) is not None:
                raise Refusal('ELEMENT_NOT_IN_SKELETON', f"'{where}': {key} records do not go on overlay definitions")
            elif key not in ('description', 'instruction', 'type', 'rule', 'example', 'optional'):
                raise refuse(f"'{key}' at '{where}' is not a field of an overlay definition: a definition takes "
                             "description and instruction, and each field beneath it takes type, rule, example and "
                             'optional. {"help": "overlay"} gives an example', {'help': 'overlay'})
            elif value is None:
                if not update:
                    raise refuse(f"{key} at '{where}' cannot be null in add; update removes a field with null")
            elif key in PART_TEXT and not is_text(value):
                raise refuse(f"{key} at '{where}' must be text that is not blank", self.fix(here, f'<{key}>'))
            elif key == 'type' and type_problem(value) is not None:
                raise refuse(f"type at '{where}' {type_problem(value)}",
                             self.fix(here, '<text, number, boolean, address, or a choice written a | b | c>'))
            elif key == 'optional' and not isinstance(value, bool):
                raise refuse(f"optional at '{where}' must be true or false", self.fix(here, True))
            elif key == 'example' and not isinstance(value, (str, int, float)):
                raise refuse(f"example at '{where}' must be one value: text, a number, or true or false",
                             self.fix(here, '<example>'))

    def wants(self, value: object, address: Address, here: list[Key]) -> None:
        """The value of `wants`: a list of want records, each naming its element in this project."""
        holder = address.full
        listed = keyed_records(value)
        if listed is not None:
            raise refuse(f"wants at '{holder}' must be a list of want records; each record names the element it wants "
                         "in element", self.fix(here, listed))
        records = as_list(value)
        if not records:
            raise refuse(f"wants at '{holder}' must be a list of want records, each with element, why, how and "
                         "direction", self.fix(here, [placeholder_want()]))
        for index, record in enumerate(records):
            self.want(record, address, [*here, index])

    def want(self, record: object, address: Address, here: list[Key]) -> None:
        """The parts of a want record that are the tool's own; the rest is checked against overlay.wants."""
        holder = address.full
        fields = as_object(record)
        if fields is None:
            raise refuse(f"a want at '{holder}' must be a record with element, why, how and direction",
                         self.fix(here, placeholder_want()))
        used = [name for name in fields if name in PROCEDURE_WORDS]
        if used:
            raise refuse(f"a want at '{holder}' takes element, why, how and direction; the command used "
                         f"{', '.join(used)}", self.fix(here, in_tool_words(fields)))
        element = fields.get('element')
        if not isinstance(element, str) or not element:
            raise refuse(f"a want at '{holder}' must name the element it wants in element",
                         self.fix([*here, 'element'], '<path>'))
        wanted = parse(element, lambda fixed: self.fix([*here, 'element'], fixed))
        place = f"the want '{element}' at '{holder}'"
        if wanted.project != address.project:
            raise other_project(element, address.project, place)
        if wanted.in_overlay:
            raise refuse(f"{place} names a part of an overlay definition; a want names an element")
        uris = next((fields[name] for name in ('refs', 'uri') if name in fields), None)
        if uris is None and as_list(fields.get('ref')) is not None:
            uris = fields['ref']
        if uris is not None:
            given = as_list(uris)
            found = [uri for uri in (given if given is not None else [uris]) if isinstance(uri, str)] or ['<uri>']
            base = {name: item for name, item in fields.items() if name not in ('refs', 'uri', 'ref')}
            *above, index = here
            items = list(cast(list[object], _at(self.command, above)))
            position = cast(int, index)
            items[position:position + 1] = [{**base, 'ref': uri} for uri in found]
            raise refuse(f"{place} is about one artifact; give its uri in ref, and write one want for each artifact",
                         self.fix(above, items))

    def delete(self, address: Address, value: object, keys: list[Key]) -> None:
        fields = as_object(value)
        if fields is None:
            raise refuse(DELETE_FORM)
        if not fields:
            return
        if len(fields) == 1 and 'wants' not in fields:
            # Records of another overlay, each by its position in the list at this element or by its record id as a
            # read gives it, so a delete made from a stale read cannot remove another record (F02).
            ((key, positions),) = fields.items()
            items = as_list(positions)
            if not is_name(key) or not items or not all(
                    (isinstance(item, int) and not isinstance(item, bool) and item >= 0)
                    or (isinstance(item, str) and item.startswith('r-')) for item in items) or len(
                    set(cast(list[int | str], items))) != len(items):
                raise refuse(DELETE_FORM)
            return
        if list(fields) != ['wants']:
            raise refuse(DELETE_FORM)
        path = keys[-1]

        def remove(items: list[object]) -> object:
            return {'delete': {path: {'wants': items}}}

        wants = fields['wants']
        items = as_list(wants)
        if isinstance(wants, str) and _parses(wants):
            raise refuse(DELETE_FORM, remove([wants]))
        if not items:
            raise refuse(DELETE_FORM, remove(['<path>']))
        seen: list[tuple[str, object]] = []
        for index, item in enumerate(items):
            named = as_object(item)
            if named is not None:
                if 'element' not in named or not set(named) <= {'element', 'ref'}:
                    raise refuse(DELETE_FORM)
                element, ref = named['element'], named.get('ref')
                if ref is not None and not is_text(ref):
                    raise refuse(f"ref of a want to remove at '{address.full}' must be text that is not blank")
            else:
                element, ref = item, '*'
            if not isinstance(element, str):
                raise refuse(DELETE_FORM, remove(['<path>']))
            at: list[Key] = [*keys, 'wants', index, *(['element'] if named is not None else [])]
            wanted = parse(element, lambda fixed, at=at: self.fix(at, fixed))
            if wanted.project != address.project:
                raise other_project(element, address.project, f"the want to remove at '{address.full}'")
            if (element, ref) in seen:
                once: list[object] = []
                for each in items:
                    if each not in once:
                        once.append(each)
                raise refuse(f"delete names the want '{element}' more than once", accepted(remove(once)))
            seen.append((element, ref))


def _at(command: object, keys: list[Key]) -> object:
    at = command
    for key in keys:
        at = cast(dict[str, object], at)[key] if isinstance(key, str) else cast(list[object], at)[key]
    return at


def single(value: object) -> tuple[str | None, int]:
    """The one text a ref-like value gives, and the number of items when a list gives several."""
    items = as_list(value)
    if items is None:
        return (value if isinstance(value, str) and value.strip() else None), 0
    if len(items) > 1:
        return None, len(items)
    first = items[0] if items else None
    return (first if isinstance(first, str) and first.strip() else None), 0


def type_problem(value: object) -> str | None:
    if not isinstance(value, str):
        return 'must be text: text, number, boolean, address, or a choice written a | b | c'
    if value in ('text', 'number', 'boolean', 'address'):
        return None
    choices = [choice.strip() for choice in value.split('|')]
    if '|' not in value or not all(choices) or len(set(choices)) != len(choices):
        return (f'"{value}" is not a type: a type is text, number, boolean, address, or a choice of two or more '
                'distinct values written a | b | c')
    return None


def placeholder_want() -> dict[str, object]:
    return {'element': '<path>', 'why': '<why>', 'how': '<how>', 'direction': '<direction>'}


def keyed_records(value: object) -> list[object] | None:
    """Want records keyed by the wanted element, as the list of records that name it in element; None if the value
    is not an object whose every value holds why, how or direction as plain text."""
    keyed = as_object(value)
    if not keyed:
        return None
    listed: list[object] = []
    for element, record in keyed.items():
        fields = as_object(record)
        if fields is None or not any(name in fields and as_object(fields[name]) is None and
                                     as_list(fields[name]) is None for name in ('why', 'how', 'direction')):
            return None
        listed.append({'element': element, **fields})
    return listed


def in_tool_words(record: object) -> object:
    """A want record with each of the procedure's words replaced by the tool's word; a word the record already gives
    in the tool's form is kept, and the procedure's form of it dropped."""
    fields = as_object(record)
    if fields is None:
        return record
    out: dict[str, object] = {}
    for name, value in fields.items():
        word = PROCEDURE_WORDS.get(name, name)
        if word == name or word not in fields:
            if word == 'direction' and value in ('sends', 'receives'):
                value = cast(str, value)[:-1]
            out[word] = value
    return out
