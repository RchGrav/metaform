"""The commands of the `project-map` tool: `add`, `update`, `delete`, `orphaned`, `goto`, `map`,
raw dumps and addressed reads (R-5.1 to R-5.12, R-5.21 to R-5.25). Ports `commands.rs`.

A command takes a map and returns either a result, with a new map and its effect for a write, or
a refusal. The input map is never changed, so a refused command changes nothing (R-5.8).

This form has no JSON Schema check (`contract.rs`): the shape check gives every message an agent
reads (`docs/designs/sqlite-forms.md`, section 2).
"""
from typing import Any

from . import model, names, reads, refusal, rules, shape, specification
from .model import Effect, Element, Map
from .names import ROOT
from .refusal import Refusal
from .values import copy, same, trim


class Outcome:
    """What an accepted command produced: the result an agent receives and, for a write, the new
    map and the effect that turns the old map into it. For a read, `map` and `effect` are `None`."""

    def __init__(self, result: Any, map: Map | None = None, effect: Effect | None = None) -> None:
        self.result = result
        self.map = map
        self.effect = effect


def execute(map: Map, command: Any) -> Outcome:
    """Perform one command on a map. The command's shape is checked by hand (`shape`), then its
    names (R-4.11). Then it is applied to a copy of the map. A refusal is raised as `Refusal`."""
    shape.check(command)
    names.check_command(command)
    verb, body = only(command)
    if verb == "orphaned":
        return Outcome(reads.orphaned(map))
    if verb == "map":
        return Outcome(reads.shallow(map))
    if verb == "goto":
        return Outcome(reads.goto(map, body))
    if verb in ("add", "update", "delete"):
        selector, supplied = only(body)
        if verb != "delete" and isinstance(supplied, dict):
            rules.check_layer_values(map, verb, selector, supplied)
        work = Work(map)
        if verb == "add":
            work.add(selector, supplied)
        elif verb == "update":
            work.update(selector, supplied)
        else:
            work.delete(selector, supplied)
        after, effect = work.finish()
        # A successful write answers with its status alone. It does not repeat the command: the
        # agent sent it and has it. A refusal still repeats the command, so the agent sees what
        # was refused beside the reason.
        return Outcome({"status": "ok"}, after, effect)
    if verb.startswith("."):
        return Outcome(reads.raw(map, verb))
    return Outcome(reads.read(map, verb, body))


def only(value: dict[str, Any]) -> tuple[str, Any]:
    """The single entry of an object that the shape check has already checked."""
    return next(iter(value.items()))


class Work:
    """A copy of the map being changed, and the addresses the change touched.

    The copy shares its elements with the map. An element is copied the first time the work
    adjusts it, so the map before the write stays as it was.
    """

    def __init__(self, before: Map) -> None:
        self.before = before
        self.elements: dict[str, Element] = dict(before.raw())
        self.touched: set[str] = set()
        self.own: set[str] = set()

    def ensure(self, address: str) -> None:
        """Create the address and every missing branch above it (R-5.4)."""
        for prefix in names.prefixes(address):
            if prefix not in self.elements:
                names.check_scope(prefix)
                self.elements[prefix] = Element()
                self.own.add(prefix)
                self.touched.add(prefix)

    def element_mut(self, address: str) -> Element:
        self.touched.add(address)
        if address not in self.own:
            self.elements[address] = self.elements[address].copy()
            self.own.add(address)
        return self.elements[address]

    def write_want(self, holder: str, other: str, change: Any) -> None:
        """Write a want. Supplied fields change the current record; the result needs every field
        (R-5.6). The element the want names is created if it is not there (R-5.4)."""
        record: dict[str, Any] = copy(self.elements[holder].wants.get(other, {}))
        if isinstance(change, dict):
            record.update(copy(change))
        missing = [
            key
            for key in ("why", "how", "direction")
            if not (isinstance(record.get(key), str) and trim(record[key]) != "")
        ]
        if missing:
            complete = dict(record)
            for key in missing:
                complete[key] = f"<{key}>"
            raise Refusal(
                refusal.WANT_INCOMPLETE,
                f"'{holder}' wants '{other}': the want has no {', '.join(missing)}",
                {"update": {holder: {"wants": {other: complete}}}},
            )
        self.ensure(other)
        self.element_mut(holder).wants[other] = record

    def write_wants(self, holder: str, wants: dict[str, Any]) -> None:
        for other, change in wants.items():
            self.write_want(holder, other, change)

    def add(self, address: str, supplied: dict[str, Any]) -> None:
        """`add` keeps what is there: lists grow, and other values are written (R-5.5)."""
        supplied_elements: dict[str, Element] = {}
        model.flatten(supplied, address, supplied_elements)
        for at in sorted(supplied_elements):
            self.ensure(at)
            element = self.element_mut(at)
            for key, value in supplied_elements[at].fields.items():
                current = element.fields.get(key)
                if value is None:
                    element.fields.pop(key, None)
                elif isinstance(current, list) and isinstance(value, list):
                    current.extend(copy(value))
                else:
                    element.fields[key] = copy(value)
        for at in sorted(supplied_elements):
            wants = supplied_elements[at].wants
            for other in sorted(wants):
                self.write_want(at, other, wants[other])

    def update(self, address: str, supplied: dict[str, Any]) -> None:
        """`update` writes to a path; `null` removes a field (R-5.5)."""
        self.ensure(address)
        for key, value in supplied.items():
            if isinstance(value, dict) and key == "wants" and model.is_want_updates(value):
                self.write_wants(address, value)
            elif value is None:
                self.element_mut(address).fields.pop(key, None)
            elif isinstance(value, dict):
                self.update(names.join(address, key), value)
            else:
                self.element_mut(address).fields[key] = copy(value)

    def delete(self, address: str, supplied: Any) -> None:
        """`delete` removes the named wants, or the element. An element that something still
        wants is refused, with the command that removes the want (R-5.7, R-5.25)."""
        if address not in self.elements:
            return
        wants = supplied.get("wants") if isinstance(supplied, dict) else None
        if isinstance(wants, list):
            for other in wants:
                if isinstance(other, str) and other in self.elements[address].wants:
                    del self.element_mut(address).wants[other]
                    self.prune(other)
            return
        receivers = model.receivers(self.elements, address)
        if receivers:
            first = receivers[0]
            if len(receivers) > 1:
                listed = ", ".join(f"'{receiver}'" for receiver in receivers)
                message = f"cannot delete '{address}': these elements still want it: {listed}. Remove their wants first."
            else:
                message = f"cannot delete '{address}': '{first}' still wants it. Remove that want first."
            raise Refusal(refusal.DEPENDENCY_LOCK, message, {"delete": {first: {"wants": [address]}}})
        # The deepest element beneath; of several at one depth, the one that sorts last.
        deepest: str | None = None
        for child in sorted(self.elements):
            if names.is_beneath(child, address) and (deepest is None or child.count(".") >= deepest.count(".")):
                deepest = child
        if deepest is not None:
            raise Refusal(
                refusal.ELEMENTS_BENEATH,
                f"cannot delete, '{address}', has elements beneath it",
                {"delete": {deepest: {}}},
            )
        wanted = list(self.elements[address].wants)
        self.remove(address)
        parent = names.parent(address)
        if parent is not None:
            self.prune(parent)
        for other in wanted:
            self.prune(other)

    def prune(self, address: str) -> None:
        """Remove an element that a deletion left with nothing in it, and then each branch above
        it that is left the same way: no fields, no wants, nothing beneath it and nothing that
        wants it. A write creates the element a want names (R-5.4); when the last want that names
        it is gone and it was never filled in, it goes too, so no empty address stays in the map."""
        branch: str | None = address
        while branch is not None and branch != ROOT:
            element = self.elements.get(branch)
            empty = element is not None and element.is_empty()
            has_children = any(names.is_beneath(child, branch) for child in self.elements)
            if not empty or has_children or model.receivers(self.elements, branch):
                break
            self.remove(branch)
            branch = names.parent(branch)

    def remove(self, address: str) -> None:
        self.elements.pop(address, None)
        self.touched.add(address)

    def finish(self) -> tuple[Map, Effect]:
        """Check every touched element against the rules that read the map, then build the
        effect."""
        self.normalize_specifications()
        touched = sorted(self.touched)
        for address in touched:
            if address in self.elements:
                self.element_mut(address).put_in_order()
        defined = [d.layer for d in specification.definitions(Map(dict(self.elements)))]
        for address in touched:
            element = self.elements.get(address)
            if element is None:
                continue
            self.check_layers_defined(address, element, defined)
            rules.check(self.before, address, element)
            self.check_collisions(address, element)
        self.check_definitive()
        effect = Effect()
        for address in touched:
            after = self.elements.get(address)
            earlier = self.before.element(address)
            if after is None:
                if earlier is not None:
                    effect.elements[address] = None
            elif not after.equals(earlier):
                effect.elements[address] = after
        return Map.from_elements(self.elements, ordered=True), effect

    def normalize_specifications(self) -> None:
        """Check the layer records a write changed, for every layer the map defines (R-6.24 to
        R-6.26). Records must be a list and sit where records are allowed. Records of a
        `markdown_blocks` layer are normalized and their heading rules checked; an empty list
        removes the field. Records the write did not change are not checked again, so an intake
        correction elsewhere is never refused because of them. The code-defined specification
        layer definition can only be written as `specification.definition()` (R-6.11, R-6.22)."""
        at = specification.DEFINITION_ADDRESS
        if at in self.touched:
            after_element = self.elements.get(at)
            earlier = self.before.element(at)
            changed = (after_element is None) != (earlier is None) or (
                after_element is not None and not after_element.equals(earlier)
            )
            if changed and (
                after_element is None
                or not same(after_element.fields, specification.definition())
                or after_element.wants
            ):
                raise Refusal(
                    refusal.LAYER_DEFINITION_LOCKED,
                    f"'{at}' is defined by the server; agents write its records at receiving elements, not its definition",
                )
        after = Map(dict(self.elements))
        touched = sorted(self.touched)

        def defines(address: str, element: Element | None) -> bool:
            return (
                element is not None
                and isinstance(element.fields.get("instruction"), str)
                and specification.in_layer_scope(address)
            )

        # A layer's field name is its key at every receiving element, so two definitions may not
        # share a last segment (R-6.24).
        for address in touched:
            if not defines(address, self.elements.get(address)):
                continue
            layer = names.last_segment(address)
            for existing, element in after.elements():
                if existing != address and names.last_segment(existing) == layer and defines(existing, element):
                    raise Refusal(
                        refusal.LAYER_NAME_COLLISION,
                        f"'{address}' would define the layer {layer}, which '{existing}' already defines; a layer's last segment is its field name and must be unique",
                        {"update": {address: {"instruction": None}}},
                    )
        definitions = specification.definitions(after)
        blocks: list[tuple[str, str, list[specification.Block]]] = []
        for address in touched:
            element = self.elements.get(address)
            if element is None:
                continue
            earlier = self.before.element(address)
            for definition in definitions:
                layer = definition.layer
                if layer not in element.fields:
                    continue
                value = element.fields[layer]
                if earlier is not None and layer in earlier.fields and same(earlier.fields[layer], value):
                    continue
                records = specification.records(layer, address, value)
                if records:
                    specification.check_allowed(after, address, layer)
                if definition.format == specification.MARKDOWN_BLOCKS:
                    found = specification.blocks_of(layer, address, value)
                    specification.check_blocks(address, layer, found)
                    specification.check_codes(after, address, layer, found)
                    blocks.append((address, layer, found))
                elif not records:
                    blocks.append((address, layer, []))
        for address, layer, found in blocks:
            fields = self.element_mut(address).fields
            if not found:
                fields.pop(layer, None)
            else:
                fields[layer] = specification.to_json(found)

    def check_layers_defined(self, address: str, element: Element, defined: list[str]) -> None:
        """A list at an element is a layer's records, so its name must be a layer: one defined
        beneath `layer` (R-6.24) or a system layer (R-6.15). Only lists this write changed are
        checked, so older data never blocks an unrelated write."""
        earlier = self.before.element(address)
        for name, value in element.fields.items():
            if (
                not isinstance(value, list)
                or name in specification.SYSTEM_LAYERS
                or name in defined
                or (earlier is not None and name in earlier.fields and same(earlier.fields[name], value))
            ):
                continue
            raise Refusal(
                refusal.LAYER_NOT_REGISTERED,
                f"'{name}' at '{address}' is not a layer. A list can be written only to a layer defined beneath the layer root, such as layer.document.specification, or to skills, memory or sources.",
                {"map": {}},
            )

    def check_collisions(self, address: str, element: Element) -> None:
        """The stored map nests fields and child elements in one object, so a field cannot share a
        name with a child element."""
        clash: tuple[str, str] | None = None
        field_over_child = next((key for key in element.fields if names.join(address, key) in self.elements), None)
        if field_over_child is not None:
            clash = (address, field_over_child)
        else:
            above = names.parent(address)
            segment = names.last_segment(address)
            if above is not None and above in self.elements and segment in self.elements[above].fields:
                clash = (above, segment)
        if clash is None:
            return
        holder, key = clash
        raise Refusal(
            refusal.FIELD_ELEMENT_COLLISION,
            f"'{holder}': '{key}' cannot be both a field and an element beneath it",
            {"update": {holder: {key: None}}},
        )

    def check_definitive(self) -> None:
        """A project has one Definitive element (R-3.13). A write that would make a second is
        refused. Elements under a root prefix do not count, because those prefixes are outside
        the project (R-3.3, R-3.7)."""
        definitive = [
            address
            for address in sorted(self.elements)
            if reads.is_project_definitive(address, self.elements[address].fields.get("role"))
        ]
        if len(definitive) < 2:
            return
        existing = next((address for address in definitive if address not in self.touched), definitive[0])
        added = next((address for address in definitive if address != existing), definitive[1])
        # The remediation gives the new element another role. It never removes the role of the
        # element that is Definitive already: an agent that followed it would lose the one
        # element that says what the project is.
        other_role = "<Supportive, Notable or Divergent>"
        element = self.elements.get(added)
        if self.before.element(added) is None and element is not None:
            view = copy(element.view())
            view["role"] = other_role
            remediation = {"add": {added: view}}
        else:
            remediation = {"update": {added: {"role": other_role}}}
        raise Refusal(
            refusal.ROLE_TAXONOMY_FAILURE,
            f"'{added}' cannot be Definitive: '{existing}' already is, and a map has one Definitive element",
            remediation,
        )
