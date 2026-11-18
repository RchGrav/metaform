"""The writes of the project tool: `add`, `update` and `delete`, on elements and on overlay definitions.

A write reads what it needs, checks everything, and only then writes, inside the one transaction `commands.run`
holds; a refusal raised at any point rolls the transaction back, so a refused command changes nothing. The checks
that need the map come in this order: the overlays the command writes are defined and their records match their
definitions, wants merge into complete wants, records sit at elements, and no name is both a field and a step beneath.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import cast

from metaform.project import specification
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
    placeholder,
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
        self.completing: list[tuple[str, str, str]] = []  # (overlay, address, record id) to complete after the edits
        # (overlay, address, record id, position or None for the end of the list) to reopen
        self.reopened: list[tuple[str, str, str, int | None]] = []
        # A specification import writes many elements and checks the block rules once, after them all, so a valid
        # change across elements, a swap of two codes, is never refused at a step between (review of 2026-11-18, F5).
        self.deferred: set[str] | None = None  # the addresses whose blocks wait for that check, when deferring

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
        named: dict[tuple[str, str], list[object]] = {}  # the record ids a written list gives, by element and overlay
        for change in changes:
            where = change.address.full
            for key, records in change.overlays.items():
                definition = defs.get(key)
                if definition is None:
                    raise Refusal('OVERLAY_NOT_DEFINED', f"'{key}' at '{where}' is not an overlay. A list can be "
                                  f"written only to an overlay defined beneath {self.project}.overlay, such as "
                                  f"{self.project}.overlay.wants.", {'map': self.project})
                checked = None
                if key != 'wants' and self.reopens(records):
                    self.reopening(definition, change, key, cast(list[object], records))
                    continue
                if records is not None and self.verb == 'update' and key != 'wants' and any(
                        'position' in (as_object(record) or {}) for record in records):
                    placed.append((change, key, self.placed(definition, change, key, records, key in tables)))
                    continue
                if records is not None:
                    named[(change.address.address, key)] = [(as_object(record) or {}).get('record')
                                                            for record in records]
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
        self.lifecycle()
        for change, key, records in overlay_writes:
            address = change.address.address
            self.put_records(key, address, records, named.get((address, key), []), key in tables)
        if any(key == 'tickets' for _, key, _ in [*overlay_writes, *placed]) or any(
                key == 'tickets' for key, *_ in self.reopened):
            self.check_ticket_ids()
        touched = sorted({change.address.address for change, key, _ in [*overlay_writes, *placed]
                          if key == specification.KEY} | self.lifecycle_touched(specification.KEY))
        if touched and self.deferred is not None:
            self.deferred.update(touched)
        elif touched:
            self.check_specification(touched, defs[specification.KEY])

    def reopens(self, records: list[object] | None) -> bool:
        """Whether an update's list reopens completed records: each record names its id with completed: false."""
        return records is not None and self.verb == 'update' and bool(records) and all(
            (as_object(record) or {}).get('completed') is False for record in records)

    def lifecycle(self) -> None:
        """Complete and reopen the records this command named, after its edits by position, since each closes up the
        list or opens a place in it. One path for an element's records and the root's (review of 2026-11-18, F2)."""
        when = datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
        for key, address, ident in self.completing:
            self.store.complete_record(key, address, ident, when)
        for key, address, ident, position in self.reopened:
            self.store.reopen_record(key, address, ident, position)

    def lifecycle_touched(self, key: str) -> set[str]:
        """The addresses whose records of one overlay this command completes or reopens."""
        return {address for named, address, *_ in [*self.completing, *self.reopened] if named == key}

    def put_records(self, key: str, address: str, records: list[dict[str, Scalar]] | None, given: list[object],
                    stored: bool) -> None:
        """Store an overlay's checked records at an address: `add` appends, `update` replaces the list, and null
        removes it. A list written back from a read keeps each record's id (F02): a record that names an id held at
        this address now keeps it, at its next revision; one that names none, or another, is a new record."""
        kept: dict[str, Scalar] = {}
        if stored and self.verb == 'update' and records:
            kept = {str(row['record']): row['revision'] for row in self.store.records(key, address, [])}
        if stored and (self.verb == 'update' or records is None):
            self.store.delete_records(key, address)
        start = self.store.next_position(key, address) if records and self.verb == 'add' else 0
        for offset, record in enumerate(records or []):
            ident = given[offset] if offset < len(given) else None
            if isinstance(ident, str) and ident in kept:
                revision = kept.pop(ident)
                self.store.insert_record(key, address, start + offset, record, ident,
                                         int(revision) + 1 if isinstance(revision, int) else 1)
            else:
                self.store.insert_record(key, address, start + offset, record)

    def root(self, overlays: dict[str, object]) -> None:
        """The records the project's root holds (F07): the specification's blocks, the project's own description,
        written as an element's are: checked against the overlay's definition, a list by position changing only those
        records, and the block rules checked after the write, in its transaction. `self.address` is the root, whose
        store address is `''`."""
        defs = definitions(self.store.parts())
        tables = set(self.store.overlay_keys())
        for key, value in overlays.items():
            definition = defs.get(key)
            if definition is None:
                raise Refusal('OVERLAY_NOT_DEFINED', f"'{key}' at '{self.project}' is not an overlay of "
                              f'{self.project}', {'map': self.project})
            records = as_list(value)
            change = Change(self.address, [self.verb, self.project], True)
            if self.reopens(records):
                self.reopening(definition, change, key, cast(list[object], records))
            elif records is not None and self.verb == 'update' and any(
                    'position' in (as_object(record) or {}) for record in records):
                for position, record in self.placed(definition, change, key, records, key in tables):
                    self.store.replace_record(key, '', position, record)
            else:
                checked = Records(definition, self.project, self.project, [self.verb, self.project, key],
                                  self.command).check(records, False) if records is not None else None
                self.put_records(key, '', checked, [(as_object(record) or {}).get('record')
                                                    for record in records or []], key in tables)
        # the root's records complete and reopen as an element's do, before the block rules are checked
        self.lifecycle()
        if specification.KEY in overlays and self.deferred is not None:
            self.deferred.add('')
        elif specification.KEY in overlays:
            self.check_specification([''], defs[specification.KEY])

    def check_specification(self, touched: list[str], definition: Definition) -> None:
        """The specification's blocks at each element written keep the round trip whole (kickoff 2026-11-17 Phase 4,
        F06): an introduction only first, levels from 1 with no skipped level, one-line titles, no heading line in
        text; and no code is held twice in the project. Checked after the command's writes, in its transaction, so a
        command that would break them is refused whole."""
        for address in touched:
            specification.blocks(self.full(address), self.current_records(definition, address))
        names = [name for name in definition.order if name != 'ref' and name in definition.fields]
        every: dict[str, list[dict[str, object]]] = {}
        for address, _, row in self.store.all_records(specification.KEY, names, completed=True):
            every.setdefault(self.full(address), []).append({name: row[name] for name in names})
        specification.check_codes(every)

    def check_ticket_ids(self) -> None:
        """A ticket's id names one ticket in the project (F09, kickoff 2026-11-17): the tickets overlay is the tool's
        own, and the board, the command line and an agent's assignment find a ticket by its id. Checked after the
        command's writes, in its transaction, so a command that would leave an id on two tickets is refused whole and
        nothing changes. Other overlays may hold the same value twice."""
        where: dict[str, list[str]] = {}
        for address, position, row in self.store.all_records('tickets', ['id'], completed=True):
            if row['id'] is not None:
                where.setdefault(str(row['id']), []).append(f"'{self.full(address)}' position {position}")
        twice = next(((ident, places) for ident, places in sorted(where.items()) if len(places) > 1), None)
        if twice is not None:
            raise Refusal('TICKET_ID_TAKEN', f"ticket id {twice[0]!r} would name {len(twice[1])} tickets: "
                          f"{', '.join(twice[1])}. A ticket's id names one ticket in {self.project}; give this one "
                          'another id.')

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
        identity = [(str(row['record']), row['revision']) for row in self.store.records(
            definition.key, change.address.address, [])] if stored else []
        merged: dict[int, dict[str, object]] = {}
        for index, record in enumerate(records):
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
            self.check_identity(key, where, change, index, given, position, identity)
            done = given.get('completed')
            if done is not None and done is not True:
                raise refuse(f"completed at position {position} of {key} at '{where}' is true, to complete the record; "
                             'a completed record is reopened by its record id with completed: false, and a position '
                             'to say where it comes back')
            if done is True:  # completed after any fields it gives are written (the person's rule, 2026-11-17)
                self.completing.append((key, change.address.address, identity[position][0]))
            fields = {name: value for name, value in given.items()
                      if name not in ('position', 'record', 'revision', 'completed')}
            if done is True and not fields:
                continue
            laid = {**current[position], **fields}
            merged[position] = {name: value for name, value in laid.items() if value is not None}
        order = sorted(merged)
        try:
            checked = Records(definition, where, self.project, [*change.keys, key], self.command).check(
                [merged[position] for position in order], False)
        except Refusal as refusal:
            raise Refusal(refusal.code, refusal.message) from None
        return list(zip(order, checked))

    def reopening(self, definition: Definition, change: Change, key: str, records: list[object]) -> None:
        """Records named by their id with completed: false are reopened: back at the `position` given, the records
        from there on moving down one, or at the end of the list. One that is not a completed record of this holder is
        refused, and nothing changes. Where order has meaning, as in a specification, the rules are checked after the
        reopen, in the command's transaction, so a reopen that would break them is refused whole (review of
        2026-11-18, F12)."""
        where = change.address.full
        held = len(self.store.records(definition.key, change.address.address, []))
        for record in records:
            given = cast(dict[str, object], as_object(record))
            ident, position = given.get('record'), given.get('position')
            extra = [name for name in given if name not in ('record', 'completed', 'position')]
            if not isinstance(ident, str) or extra:
                raise refuse(f"reopening a {key} record at '{where}' names it by its record id, and a position if "
                             'it comes back anywhere but the end: {"record": "r-...", "completed": false, '
                             '"position": 0}')
            if position is not None and (not isinstance(position, int) or isinstance(position, bool)
                                         or not 0 <= position <= held):
                raise refuse(f"position {position!r} for the reopened {key} record {ident!r} at '{where}' is not a "
                             f'place in the list: give 0 to {held}')
            if self.store.completed_record(definition.key, change.address.address, ident, []) is None:
                raise Refusal('RECORD_GONE', f"{key} record {ident!r} at '{where}' is not a completed record there; "
                              'find it with the find command.', {where: {key: {}}})
            self.reopened.append((key, change.address.address, ident, position))
            held += 1

    def check_identity(self, key: str, where: str, change: Change, index: int, given: dict[str, object],
                       position: int, identity: list[tuple[str, Scalar]]) -> None:
        """An edit by position that names the `record` it read, and the `revision` it read, lands only on that record
        as it was read (F02, kickoff 2026-11-17). Otherwise it is refused and nothing changes: RECORD_MOVED when the
        record is now at another position, with the command corrected to it; RECORD_GONE when it is no longer
        there; RECORD_CHANGED when it changed since it was read. An edit that names neither is taken by position."""
        named, expected = given.get('record'), given.get('revision')
        ident, revision = identity[position]
        read: dict[str, object] = {where: {key: {}}}
        if named is not None and named != ident:
            now = next((at for at, (other, _) in enumerate(identity) if other == named), None)
            if now is None:
                raise Refusal('RECORD_GONE', f"{key} record {named!r} at '{where}' is no longer there; position "
                              f'{position} now holds {ident!r}. Read the list again.', read)
            raise Refusal('RECORD_MOVED', f"{key} record {named!r} at '{where}' is now at position {now}, not "
                          f'{position}', replaced(self.command, [*change.keys, key, index, 'position'], now))
        if expected is not None and expected != revision:
            raise Refusal('RECORD_CHANGED', f"{key} record {ident!r} at '{where}' is at revision {revision}, not "
                          f'{expected}: it changed since it was read. Read it again.', read)

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
        self.check_compatible(defs_before, defs_after, tables)
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

    def check_compatible(self, defs_before: dict[str, Definition], defs_after: dict[str, Definition],
                         tables: set[str]) -> None:
        """A definition change that would leave stored records outside it is refused, and nothing changes (F03,
        kickoff 2026-11-17, OVERLAY_CONTRACT section 3): narrowed choices, a field made required or added as required,
        or a field's logical type changed while records hold values it does not accept. The column type alone does
        not show this, since text, address and every choice are stored as STRING. The refusal names the records and
        their fields, and the update that fixes the first; no value is invented and no record is changed. An
        instruction, description, rule or example edit, or a new optional field, leaves every record valid."""
        for key, definition in defs_after.items():
            old = defs_before.get(key)
            if old is None or key not in tables or {name: (spec.type, spec.optional) for name, spec in
                                                     definition.fields.items()} == {
                    name: (spec.type, spec.optional) for name, spec in old.fields.items()}:
                continue
            names = [name for name in old.order if name != 'ref' and name in old.fields]
            broken: list[tuple[str, int, list[str]]] = []
            for address, position, row in self.store.all_records(key, names, completed=True):
                record = {name: decode(old.fields[name].kind, row[name]) for name in names if row[name] is not None}
                wrong = [name for name in definition.order if name != 'ref' and name in definition.fields and (
                    (record.get(name) is None and not definition.fields[name].optional)
                    or (record.get(name) is not None and not definition.fields[name].accepts(record[name],
                                                                                             self.project)))]
                if wrong:
                    broken.append((address, position, wrong))
            if not broken:
                continue
            shown = '; '.join(f"'{self.full(address)}' position {position} ({', '.join(wrong)})"
                              for address, position, wrong in broken[:5])
            more = f' and {len(broken) - 5} more' if len(broken) > 5 else ''
            address, position, wrong = broken[0]
            new = [name for name in wrong if name not in old.fields]
            if new:  # a field the records cannot be given until it is defined: defined optional first, then required
                field = definition.fields[new[0]]
                raise Refusal('DEFINITION_INCOMPATIBLE',
                              f"'{self.full(definition.address)}': the change would leave {len(broken)} {key} records "
                              f'without {new[0]}, a new required field: {shown}{more}. Add it as optional first, give '
                              'those records a value, then make it required.',
                              {'update': {self.full(definition.address): {new[0]: {
                                  'type': field.type, 'rule': field.rule, 'example': field.example,
                                  'optional': True}}}})
            raise Refusal('DEFINITION_INCOMPATIBLE',
                          f"'{self.full(definition.address)}': the change would leave {len(broken)} {key} records "
                          f'outside the definition: {shown}{more}. Update those records first so they meet the new '
                          'definition, or leave the definition as it is.',
                          {'update': {self.full(address): {key: [
                              {'position': position, **{name: placeholder(name) for name in wrong}}]}}})

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
            named = [item for item in cast(list[object], positions) if isinstance(item, str)]
            if named:  # record ids, each the position its record holds now (F02)
                ids = [str(row['record']) for row in self.store.records(key, address, [])] if held else []
                gone = [ident for ident in named if ident not in ids]
                if gone:
                    raise Refusal('RECORD_GONE', f"{key} record {gone[0]!r} at '{self.address.full}' is no longer "
                                  'there; nothing was deleted. Read the list again.',
                                  {self.address.full: {key: {}}})
                positions = [ids.index(item) if isinstance(item, str) else item
                             for item in cast(list[object], positions)]
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
    """Define, in a project that lacks them, the overlays every project is given: tickets, memories and the
    specification. Called inside the writer's transaction each time a database is opened, which is how a new project
    gets them. A definition the project already holds is left as it is: the product is unreleased, and no older
    definition is patched (review of 2026-11-18, F15)."""
    from metaform.project import texts
    defined = store.parts()
    for path, definition in texts.standing_overlays().items():
        if path not in defined:
            whole = full(project, path)
            Writer(store, parse(whole), {'add': {whole: definition}}, 'add').write(whole, definition)

