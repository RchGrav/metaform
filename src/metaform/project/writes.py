"""The writes of the project tool: `add`, `update` and `delete`, on elements and on overlay definitions.

A write reads what it needs, checks everything, and only then writes, inside the one transaction `commands.run`
holds; a refusal raised at any point rolls the transaction back, so a refused command changes nothing. The checks
that need the map come in this order: the overlays the command writes are defined and their records match their
definitions, wants merge into complete wants, records sit at elements, and no name is both a field and a step beneath.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from metaform.project.forms import (
    Address,
    Key,
    Refusal,
    as_list,
    as_object,
    full,
    is_text,
    parse,
    refuse,
    replaced,
    technical_name,
)
from metaform.project.overlays import (
    RESERVED,
    Definition,
    Field,
    Records,
    corrected_record,
    decode,
    definitions,
    encode_example,
    is_placeholder,
    key_of,
)
from metaform.project.store import ELEMENT_FIELDS, PART_FIELDS, Scalar, Store
from metaform.project.texts import ROLE_PLACEHOLDER

FIELD_PARTS = ('type', 'rule', 'example', 'optional')
LOCKED = 'overlay.wants'


@dataclass
class Change:
    """What a command gives for one element: its fields, the overlays it writes, and its wants."""
    address: Address
    keys: list[Key]
    top: bool
    fields: dict[str, Scalar] = field(default_factory=dict[str, Scalar])
    overlays: dict[str, list[object] | None] = field(default_factory=dict[str, 'list[object] | None'])
    wants: list[object] | None = None


def flatten(values: dict[str, object], address: Address, keys: list[Key], top: bool, out: list[Change]) -> None:
    change = Change(address, keys, top)
    out.append(change)
    for key, value in values.items():
        nested = as_object(value)
        if nested is not None:
            flatten(nested, address.child(key), [*keys, key], False, out)
        elif key == 'wants':
            change.wants = as_list(value)
        elif key in ELEMENT_FIELDS or key in PART_FIELDS:
            change.fields[key] = cast(Scalar, value)
        else:
            change.overlays[key] = as_list(value)


def prefixes(address: str) -> list[str]:
    steps = address.split('.')
    return ['.'.join(steps[:end]) for end in range(1, len(steps) + 1)]


def _kind(node: dict[str, Scalar]) -> str:
    if any(node.get(name) is not None for name in FIELD_PARTS):
        return 'field'
    if node.get('instruction') is not None or node.get('description') is not None:
        return 'definition'
    return 'branch'


class Writer:
    def __init__(self, store: Store, address: Address, command: object, verb: str) -> None:
        self.store = store
        self.address = address
        self.project = address.project
        self.command = command
        self.verb = verb

    def full(self, address: str) -> str:
        return full(self.project, address)

    def write(self, path: str, value: object) -> None:
        changes: list[Change] = []
        flatten(cast(dict[str, object], value), self.address, [self.verb, path], True, changes)
        if self.address.in_overlay:
            self.parts(changes)
        else:
            self.elements(changes)

    # Elements

    def elements(self, changes: list[Change]) -> None:
        defs = definitions(self.store.parts())
        tables = set(self.store.overlay_keys())
        overlay_writes: list[tuple[Change, str, list[dict[str, Scalar]] | None]] = []
        placed: list[tuple[Change, str, list[tuple[int, dict[str, Scalar]]]]] = []
        want_writes: list[tuple[Change, list[dict[str, Scalar]]]] = []
        for change in changes:
            where = change.address.full
            for key, records in change.overlays.items():
                definition = defs.get(key)
                if definition is None:
                    raise Refusal('OVERLAY_NOT_DEFINED', f"'{key}' at '{where}' is not an overlay. A list can be "
                                  f"written only to an overlay defined beneath {self.project}.overlay, such as "
                                  f"{self.project}.overlay.wants.", {'map': self.project})
                checked = None
                if records is not None and self.verb == 'update' and key != 'wants' and any(
                        'position' in (as_object(record) or {}) for record in records):
                    placed.append((change, key, self.placed(definition, change, key, records, key in tables)))
                    continue
                if records is not None:
                    checked = Records(definition, where, self.project, [*change.keys, key], self.command).check(
                        records, False)
                    if checked and key not in tables:
                        raise refuse(f"'{key}' at '{where}': the overlay {key} has no fields yet; its definition "
                                     f"needs a field beneath it before it holds records",
                                     {self.full(definition.address): {}})
                overlay_writes.append((change, key, checked))
            if change.wants is not None:
                checked = Records(defs['wants'], where, self.project, [*change.keys, 'wants'], self.command).check(
                    change.wants, self.verb == 'update' and change.top)
                want_writes.append((change, checked))
        needed: set[str] = set()
        for change in changes:
            needed.update(prefixes(change.address.address))
        for _, records in want_writes:
            for record in records:
                needed.update(prefixes(parse(record['element']).address))
        existing = self.store.elements(sorted(needed))
        after = {address: dict(existing.get(address) or dict.fromkeys(ELEMENT_FIELDS)) for address in needed}
        for change in changes:
            after[change.address.address].update(change.fields)
        changed_wants = self.merge_wants(want_writes, existing, defs['wants'])
        self.check_skeleton(overlay_writes, want_writes, after)
        self.check_collisions(changes, overlay_writes, want_writes, after, existing, defs, tables)
        for address in sorted(needed):
            if address not in existing or after[address] != existing[address]:
                self.store.put_element(address, after[address])
        for (holder, element, ref), want in changed_wants.items():
            self.store.remove_wants(holder, element, ref)
            self.store.add_want(holder, element, want)
        for change, key, changed in placed:
            for position, record in changed:
                self.store.replace_record(key, change.address.address, position, record)
        for change, key, records in overlay_writes:
            address = change.address.address
            if key in tables and (self.verb == 'update' or records is None):
                self.store.delete_records(key, address)
            start = self.store.next_position(key, address) if records and self.verb == 'add' else 0
            for offset, record in enumerate(records or []):
                self.store.insert_record(key, address, start + offset, record)

    def current_records(self, definition: Definition, address: str) -> list[dict[str, object]]:
        """The overlay's records at an address, as a read gives them."""
        names = [name for name in definition.order if name != 'ref' and name in definition.fields]
        out: list[dict[str, object]] = []
        for row in self.store.records(definition.key, address, names):
            record: dict[str, object] = {name: decode(definition.fields[name].kind, row[name]) for name in names
                                         if row[name] is not None}
            if row['ref'] is not None:
                record['ref'] = row['ref']
            out.append(record)
        return out

    def placed(self, definition: Definition, change: Change, key: str, records: list[object],
               stored: bool) -> list[tuple[int, dict[str, Scalar]]]:
        """An update whose records each give a `position` changes those records and leaves the rest of the list as it
        is: the fields given are laid over the record at that position, null removing one, and the result is checked
        whole. No corrected command is offered for these, since a corrected list without positions would replace the
        whole list."""
        where = change.address.full
        current = self.current_records(definition, change.address.address) if stored else []
        merged: dict[int, dict[str, object]] = {}
        for record in records:
            given = as_object(record)
            position = given.get('position') if given is not None else None
            if given is None or 'position' not in given:
                raise refuse(f"update of {key} at '{where}': give a position in every record to change those "
                             'records, or in none to replace the whole list')
            if not isinstance(position, int) or isinstance(position, bool) or not 0 <= position < len(current):
                held = (f'positions 0 to {len(current) - 1}' if current else 'no records')
                raise refuse(f"position {position!r} of {key} at '{where}' is not a record there: the list holds "
                             f'{held}')
            if position in merged:
                raise refuse(f"update of {key} at '{where}' names position {position} more than once")
            laid = {**current[position], **{name: value for name, value in given.items() if name != 'position'}}
            merged[position] = {name: value for name, value in laid.items() if value is not None}
        order = sorted(merged)
        try:
            checked = Records(definition, where, self.project, [*change.keys, key], self.command).check(
                [merged[position] for position in order], False)
        except Refusal as refusal:
            raise Refusal(refusal.code, refusal.message) from None
        return list(zip(order, checked))

    def merge_wants(self, want_writes: list[tuple[Change, list[dict[str, Scalar]]]],
                    existing: dict[str, dict[str, Scalar]], definition: Definition,
                    ) -> dict[tuple[str, str, str | None], dict[str, Scalar]]:
        """Each record changes the holder's want with the same element and ref, or adds one; the result must hold
        why, how and direction."""
        changed: dict[tuple[str, str, str | None], dict[str, Scalar]] = {}
        for change, records in want_writes:
            holder = change.address.address
            current = self.store.wants_of(holder) if holder in existing else []
            for record in records:
                element = parse(record['element']).address
                ref = record.get('ref')
                found = next((want for want in current if want['element'] == element and want['ref'] == ref), None)
                merged: dict[str, Scalar] = {**(found or {'ref': ref}), **record, 'element': element}
                missing = [name for name in ('why', 'how', 'direction')
                           if not is_text(merged.get(name)) or is_placeholder(merged.get(name))]
                if missing:
                    shown = {**{name: value for name, value in merged.items() if value is not None},
                             'element': self.full(element)}
                    rules = ' '.join(f'{name}: {definition.fields[name].rule}' for name in missing)
                    raise Refusal('WANT_INCOMPLETE', f"'{change.address.full}' wants '{self.full(element)}': the want "
                                  f"has no {', '.join(missing)}. {rules}", {'update': {change.address.full: {
                                      'wants': [corrected_record(definition, cast(dict[str, object], shown),
                                                               tuple(missing))]}}})
                if found is not None:
                    current.remove(found)
                current.append(merged)
                changed[(holder, element, cast(str | None, ref))] = merged
        return changed

    def check_skeleton(self, overlay_writes: list[tuple[Change, str, list[dict[str, Scalar]] | None]],
                       want_writes: list[tuple[Change, list[dict[str, Scalar]]]],
                       after: dict[str, dict[str, Scalar]]) -> None:
        """Records sit only at an element: an address with technical_name, name and role."""
        holding = [(change, key) for change, key, records in overlay_writes if records]
        holding += [(change, 'wants') for change, records in want_writes if records]
        for change, key in holding:
            fields = after[change.address.address]
            missing = [name for name in ('technical_name', 'name', 'role') if fields[name] is None]
            if not missing:
                continue
            remedy = self.command
            for name in missing:
                value = {'technical_name': technical_name(change.address, '') or '<technical_name>',
                         'name': '<name>', 'role': ROLE_PLACEHOLDER}[name]
                remedy = replaced(remedy, [*change.keys, name], value)
            raise Refusal('ELEMENT_NOT_IN_SKELETON', f"'{change.address.full}': {key} records need an element with "
                          "technical_name, name and role; intake has not placed it in the skeleton yet", remedy)

    def check_collisions(self, changes: list[Change],
                         overlay_writes: list[tuple[Change, str, list[dict[str, Scalar]] | None]],
                         want_writes: list[tuple[Change, list[dict[str, Scalar]]]],
                         after: dict[str, dict[str, Scalar]], existing: dict[str, dict[str, Scalar]],
                         defs: dict[str, Definition], tables: set[str]) -> None:
        """No name is both a field (or an overlay's records) and a step beneath the same element."""
        held: dict[str, set[str]] = {}
        for change in changes:
            address = change.address.address
            held.setdefault(address, set()).update(name for name, value in after[address].items() if value is not None)
        for change, key, records in overlay_writes:
            if records:
                held[change.address.address].add(key)
        for change, records in want_writes:
            if records:
                held[change.address.address].add('wants')
        for address in sorted(set(after) - set(existing)):
            held.setdefault(address, set()).update(name for name, value in after[address].items() if value is not None)
        candidates = sorted(f'{address}.{name}' for address, names in held.items() for name in names)
        found = set(self.store.elements(candidates)) | (set(candidates) & set(after))
        clash = next(((address, name) for address, names in sorted(held.items()) for name in sorted(names)
                      if f'{address}.{name}' in found), None)
        for created in sorted(set(after) - set(existing)):
            parent, _, step = created.rpartition('.')
            if clash is not None:
                break
            if not parent:
                continue
            if after[parent].get(step) is not None or step in held.get(parent, set()) or (step == 'wants' and self.store.wants_of(parent)) or (
                    step in defs and step in tables and self.store.record_count(step, parent)):
                clash = (parent, step)
        if clash is not None:
            raise Refusal('FIELD_ELEMENT_COLLISION',
                          f"'{self.full(clash[0])}': '{clash[1]}' cannot be both a field and an element beneath it")

    # Overlay definitions

    def parts(self, changes: list[Change]) -> None:
        before = self.store.parts()
        after = {address: dict(values) for address, values in before.items()}
        touched: list[str] = []
        keys_of: dict[str, list[Key]] = {}
        for change in changes:
            address = change.address.address
            for prefix in prefixes(address):
                if prefix not in after:
                    after[prefix] = dict.fromkeys(PART_FIELDS)
                    touched.append(prefix)
            for name, value in change.fields.items():
                after[address][name] = encode_example(value) if name == 'example' else value
            touched.append(address)
            keys_of[address] = change.keys
        changed = [address for address in dict.fromkeys(touched) if after.get(address) != before.get(address)]
        if not changed:
            return
        for address in changed:
            if address == LOCKED or address.startswith(LOCKED + '.'):
                raise Refusal('OVERLAY_DEFINITION_LOCKED', f"'{self.full(LOCKED)}' is defined by the tool; agents write "
                              "wants records at elements, not its definition")
        if any(value is not None for value in after['overlay'].values()):
            raise refuse(f"'{self.full('overlay')}' is the overlay root and holds no fields; an overlay is defined at a "
                         f"step beneath it, such as {self.full('overlay.specifications.project')}")
        self.check_structure(changed, after, keys_of)
        defs_before, defs_after = definitions(before), definitions(after)
        self.check_keys(changed, after)
        tables = set(self.store.overlay_keys())
        plan: list[tuple[str, str, str, str]] = []
        for key, definition in defs_after.items():
            columns = {name: spec.column for name, spec in definition.fields.items() if name != 'ref'}
            if key not in tables:
                if definition.fields:
                    plan.append(('create', key, '', ''))
                continue
            old = defs_before[key].fields if key in defs_before else {}
            for name, column in columns.items():
                if name not in old:
                    plan.append(('add', key, name, column))
                elif old[name].column != column:
                    if self.store.field_in_use(key, name):
                        raise refuse(f"'{self.full(definition.address)}.{name}': its type cannot change from "
                                     f"{old[name].type} to {definition.fields[name].type} while {key} records hold "
                                     "this field")
                    plan += [('drop', key, name, ''), ('add', key, name, column)]
        for address in changed:
            self.store.put_part(address, after[address])
        for action, key, name, column in plan:
            if action == 'create':
                self.store.create_overlay(key, {name: spec.column for name, spec in defs_after[key].fields.items()
                                                if name != 'ref'})
            elif action == 'add':
                self.store.add_column(key, name, column)
            else:
                self.store.drop_column(key, name)

    def check_structure(self, changed: list[str], after: dict[str, dict[str, Scalar]],
                        keys_of: dict[str, list[Key]]) -> None:
        """A definition carries description and instruction and is beneath no definition; each step beneath it is a
        field with type, rule and example, and holds nothing beneath it."""
        nearby: set[str] = set()
        for address in changed:
            nearby.update([address, address.rpartition('.')[0]])
            nearby.update(other for other in after if other.rpartition('.')[0] == address)

        def placeholders(address: str, missing: list[str]) -> object:
            if address not in keys_of:
                return None
            remedy = self.command
            for name in missing:
                value = '<text, number, boolean, address, or a choice written a | b | c>' if name == 'type' else \
                    f'<{name}>'
                remedy = replaced(remedy, [*keys_of[address], name], value)
            return remedy

        for address in sorted(nearby):
            if address in ('', 'overlay') or address not in after:
                continue
            node, path = after[address], self.full(address)
            kind, parent = _kind(node), address.rpartition('.')[0]
            parent_kind = _kind(after[parent]) if parent != 'overlay' else 'branch'
            if kind == 'definition':
                missing = [name for name in ('description', 'instruction') if node[name] is None]
                if missing:
                    raise refuse(f"'{path}': an overlay definition needs description and instruction; it has no "
                                 f"{', '.join(missing)}", placeholders(address, missing))
                above = next((step for step in prefixes(address)[1:-1] if _kind(after[step]) == 'definition'), None)
                if above is not None:
                    raise refuse(f"'{path}' is beneath the overlay definition '{self.full(above)}'; each step beneath a "
                                 "definition is one field of its records, with type, rule and example")
            elif kind == 'field':
                if node['description'] is not None or node['instruction'] is not None:
                    raise refuse(f"'{path}' carries the fields of a definition and of a field of one: a definition "
                                 "takes description and instruction, and each field beneath it takes type, rule, "
                                 "example and optional")
                if parent_kind != 'definition':
                    raise refuse(f"'{path}' is a field of an overlay, and '{self.full(parent)}' is not an overlay "
                                 "definition: a definition carries description and instruction")
                missing = [name for name in ('type', 'rule', 'example') if node[name] is None]
                if missing:
                    raise refuse(f"'{path}': a field of an overlay needs type, rule and example; it has no "
                                 f"{', '.join(missing)}", placeholders(address, missing))
                if any(other.startswith(address + '.') for other in after):
                    raise refuse(f"'{path}' is a field of an overlay and holds no steps beneath it")
                name, kind_text = address.rpartition('.')[2], str(node['type'])
                if name == 'ref' and kind_text != 'text':
                    raise refuse(f"'{path}': ref is a record's own one text, so its type is text",
                                 replaced(self.command, [*keys_of[address], 'type'], 'text')
                                 if address in keys_of else None)
                spec = Field(name, kind_text, '', None, False)
                example = decode(spec.kind, node['example'])
                if not spec.accepts(example, self.project):
                    raise refuse(f"example at '{path}' must be {spec.expected(self.project)}, because its type is "
                                 f"{kind_text}")
            elif parent_kind == 'definition':
                raise refuse(f"'{path}' is beneath the overlay definition '{self.full(parent)}', so it is a field of "
                             "its records and needs type, rule and example", placeholders(address, list(FIELD_PARTS[:3])))

    def check_keys(self, changed: list[str], after: dict[str, dict[str, Scalar]]) -> None:
        """An overlay's key is unique, and is not a name an element or a read already uses."""
        defining = sorted(address for address, node in after.items() if _kind(node) == 'definition')
        for address in defining:
            if address not in changed:
                continue
            key, path = key_of(address), self.full(address)
            if key in RESERVED or (key == 'wants' and address != LOCKED):
                raise Refusal('OVERLAY_NAME_COLLISION', f"'{path}' would define the overlay {key}, a name that every "
                              "element already uses; an overlay's key is its steps after overlay, reversed and joined "
                              "with underscores")
            other = next((each for each in defining if each != address and key_of(each) == key), None)
            if other is not None:
                raise Refusal('OVERLAY_NAME_COLLISION', f"'{path}' would define the overlay {key}, which "
                              f"'{self.full(other)}' already defines; an overlay's key is its steps after overlay, "
                              "reversed and joined with underscores, and must be unique")

    # Deleting

    def delete(self, value: object) -> None:
        fields = cast(dict[str, object], value)
        address = self.address.address
        if self.address.in_overlay:
            self.delete_part(address, bool(fields))
            return
        if address not in self.store.elements([address]):
            return
        if fields and 'wants' not in fields:
            ((key, positions),) = fields.items()
            definition = definitions(self.store.parts()).get(key)
            if definition is None:
                raise Refusal('OVERLAY_NOT_DEFINED', f"'{key}' at '{self.address.full}' is not an overlay of "
                              f'{self.project}', {'map': self.project})
            held = self.store.record_count(key, address) if key in self.store.overlay_keys() else 0
            wrong = [position for position in cast(list[int], positions) if position >= held]
            if wrong:
                raise refuse(f"position {wrong[0]} of {key} at '{self.address.full}' is not a record there: the list "
                             f"holds {f'positions 0 to {held - 1}' if held else 'no records'}")
            self.store.delete_records_at(key, address, cast(list[int], positions))
            return
        if fields:
            targets: list[str] = []
            current = self.store.wants_of(address)
            for item in cast(list[object], fields['wants']):
                named = as_object(item)
                element = parse(named['element'] if named is not None else item).address
                ref = cast(str | None, named.get('ref')) if named is not None else None
                if any(want['element'] == element and (named is None or want['ref'] == ref) for want in current):
                    self.store.remove_wants(address, element, ref, every=named is None)
                    targets.append(element)
            for target in targets:
                self.prune(target)
            return
        holders = [holder for holder in self.store.holders(address) if holder != address]
        if holders:
            message = (f"cannot delete '{self.address.full}': these elements still want it: "
                       f"{', '.join(repr(self.full(holder)) for holder in holders)}. Remove their wants first."
                       if len(holders) > 1 else
                       f"cannot delete '{self.address.full}': '{self.full(holders[0])}' still wants it. Remove that "
                       "want first.")
            raise Refusal('DEPENDENCY_LOCK', message,
                          {'delete': {self.full(holders[0]): {'wants': [self.address.full]}}})
        beneath = self.store.beneath(address)
        if beneath:
            deepest = max(reversed(beneath), key=lambda each: each.count('.'))
            raise Refusal('ELEMENTS_BENEATH', f"cannot delete, '{self.address.full}', has elements beneath it",
                          {'delete': {self.full(deepest): {}}})
        wanted = [str(want['element']) for want in self.store.wants_of(address)]
        self.store.delete_element(address, self.store.overlay_keys())
        for target in [address.rpartition('.')[0], *wanted]:
            self.prune(target)

    def prune(self, address: str) -> None:
        """Remove an element left with nothing: no fields, no wants either way, nothing beneath it and no records;
        then each branch above it left the same way."""
        keys = self.store.overlay_keys()
        at = address
        while at:
            element = self.store.elements([at]).get(at)
            if element is None or any(value is not None for value in element.values()):
                return
            if self.store.wants_of(at) or self.store.holders(at) or self.store.beneath(at):
                return
            if any(self.store.record_count(key, at) for key in keys):
                return
            self.store.delete_element(at, [])
            at = at.rpartition('.')[0]

    def delete_part(self, address: str, wants: bool) -> None:
        if address == LOCKED or address.startswith(LOCKED + '.'):
            raise Refusal('OVERLAY_DEFINITION_LOCKED', f"'{self.full(LOCKED)}' is defined by the tool; agents write "
                          "wants records at elements, not its definition")
        parts = self.store.parts()
        if address not in parts or wants:
            return
        beneath = sorted(other for other in parts if other.startswith(address + '.'))
        if beneath:
            deepest = max(reversed(beneath), key=lambda each: each.count('.'))
            raise Refusal('ELEMENTS_BENEATH', f"cannot delete, '{self.address.full}', has elements beneath it",
                          {'delete': {self.full(deepest): {}}})
        parent, _, name = address.rpartition('.')
        owner = next((each for each in definitions(parts).values() if each.address == parent and name in each.fields),
                     None)
        if owner is not None and owner.key in self.store.overlay_keys():
            records, places = self.store.held(owner.key)
            if records:
                # No corrected command: the only one would remove records, which this delete did not ask for.
                raise Refusal('DEPENDENCY_LOCK', f"cannot delete '{self.address.full}': it is a field of the "
                              f"{owner.key} overlay, which holds {records} {'record' if records == 1 else 'records'} "
                              f"at {places} {'address' if places == 1 else 'addresses'}. A field is removed only "
                              'from an overlay that holds no records.')
            if len(owner.fields) == 1:
                self.store.drop_overlay(owner.key)
            elif name != 'ref':
                self.store.drop_column(owner.key, name)
        self.store.delete_part(address)
        del parts[address]
        at = parent
        while at and at != 'overlay' and all(value is None for value in parts[at].values()) and not any(
                other.startswith(at + '.') for other in parts):
            self.store.delete_part(at)
            del parts[at]
            at = at.rpartition('.')[0]


def give_standing_overlays(store: Store, project: str) -> None:
    """Define, in a project that lacks them, the overlays every project is given: tickets and memories. Called inside
    the writer's transaction each time a database is opened, so a project made before one of them existed gains it."""
    from metaform.project import texts
    defined = store.parts()
    for path, definition in texts.standing_overlays().items():
        if path not in defined:
            whole = full(project, path)
            Writer(store, parse(whole), {'add': {whole: definition}}, 'add').write(whole, definition)

