"""The map model. Ports `model.rs`.

A map is the unit: its own root and its elements. In memory the map is flat, keyed by full
address in the agent's snake_case form (R-4.12). The nested tree exists only at the edges: the
raw dump, and the store.

The Rust form keeps elements and wants in sorted maps (`BTreeMap`). This form keeps dictionaries
and sorts when it iterates, so every answer has the Rust form's order. The document functions
(`from_document`, `to_document`, `from_tree`) are not ported: only the specification export and
import use them, and this form does not offer those.
"""
from typing import Any, Iterator

from . import names
from .names import ROOT
from .values import copy, same

# An element's own fields: scalars and lists. Objects are child elements, not fields.
Fields = dict[str, Any]

# The intake fields, in R-6.15's order. They come first in an element; every other field follows,
# sorted by name. One order makes an element's JSON the same after every reload and in every
# form of Metaform, whatever order its fields were written in.
FIELD_ORDER = ("technical_name", "name", "role", "uri", "status")
# The want-record fields, in R-6.17's order, first in a want record; any other follows by name.
WANT_ORDER = ("why", "how", "direction")


def in_order(fields: Fields, first: tuple[str, ...]) -> Fields:
    """`fields` in canonical order: the names in `first`, in that order, then the rest by name."""
    out = {name: fields[name] for name in first if name in fields}
    for name in sorted(fields):
        if name not in out:
            out[name] = fields[name]
    return out


class Element:
    """One element at one address (R-3.1)."""

    __slots__ = ("fields", "wants")

    def __init__(self, fields: Fields | None = None, wants: dict[str, Fields] | None = None) -> None:
        self.fields: Fields = {} if fields is None else fields
        # Want records keyed by the address of the other element (R-3.5).
        self.wants: dict[str, Fields] = {} if wants is None else wants

    def put_in_order(self) -> None:
        """Put the fields and every want record in canonical order."""
        self.fields = in_order(self.fields, FIELD_ORDER)
        self.wants = {other: in_order(self.wants[other], WANT_ORDER) for other in sorted(self.wants)}

    def is_empty(self) -> bool:
        """An element with nothing in it: a namespace branch that a write created."""
        return not self.fields and not self.wants

    def copy(self) -> "Element":
        return Element(copy(self.fields), copy(self.wants))

    def equals(self, other: "Element | None") -> bool:
        return other is not None and same(self.fields, other.fields) and same(self.wants, other.wants)

    def wants_json(self) -> dict[str, Any]:
        """The wants as the contract writes them: one dictionary keyed by provider address."""
        return {other: dict(self.wants[other]) for other in sorted(self.wants)}

    def base_fields(self) -> Fields:
        """The fields an addressed read returns (R-5.10, R-5.21): scalar values only. Wants and
        list-valued layers come back only when a read names them."""
        return {key: value for key, value in self.fields.items() if not isinstance(value, list)}

    def view(self) -> dict[str, Any]:
        """The element's fields and wants, without child elements, in the agent's form."""
        out = dict(self.fields)
        if self.wants:
            out["wants"] = self.wants_json()
        return out


class Effect:
    """The final value of every element a write touched: the whole element, or `None` if removed.
    Applying an effect twice gives the same map."""

    def __init__(self) -> None:
        self.elements: dict[str, Element | None] = {}

    def is_empty(self) -> bool:
        return not self.elements

    def to_json(self) -> dict[str, Any]:
        """The effect in the agent's form, keyed by full address."""
        out: dict[str, Any] = {}
        for address in sorted(self.elements):
            element = self.elements[address]
            out[address] = None if element is None else element.view()
        return out


class Map:
    """One map: a root at `.` and the elements beneath it. A map is not changed after it is made."""

    def __init__(self, elements: dict[str, Element] | None = None) -> None:
        self._elements: dict[str, Element] = {ROOT: Element()} if elements is None else elements
        self._sorted: list[str] | None = None

    @staticmethod
    def from_elements(elements: dict[str, Element], ordered: bool = False) -> "Map":
        """A map from its elements, keyed by address in the agent's form. The root is added if it
        is missing. `ordered` says that every element is already in canonical order."""
        if ROOT not in elements:
            elements[ROOT] = Element()
        if not ordered:
            for element in elements.values():
                element.put_in_order()
        return Map(elements)

    def raw(self) -> dict[str, Element]:
        return self._elements

    def element(self, address: str) -> Element | None:
        """The element at an address; `.` is the root."""
        return self._elements.get(address)

    def addresses(self) -> list[str]:
        """Every address in sorted order, the root first."""
        if self._sorted is None:
            self._sorted = sorted(self._elements)
        return self._sorted

    def elements(self) -> Iterator[tuple[str, Element]]:
        """Every element, the root first, then by address."""
        for address in self.addresses():
            yield address, self._elements[address]

    def to_tree(self) -> dict[str, Any]:
        """The nested map in the agent's form, without the project name."""
        root: dict[str, Any] = {}
        for address, element in self.elements():
            node = root
            if address != ROOT:
                for segment in address.split("."):
                    node = node.setdefault(segment, {})
            node.update(copy(element.view()))
        return root

    def wanted(self) -> set[str]:
        """Every address that some element wants."""
        return {other for element in self._elements.values() for other in element.wants}


def receivers(elements: dict[str, Element], address: str) -> list[str]:
    """The addresses of the elements whose wants name `address`, in sorted order."""
    return sorted(
        holder for holder, element in elements.items() if holder != address and address in element.wants
    )


def is_want_updates(wants: dict[str, Any]) -> bool:
    """A wants update: a dictionary keyed by provider address whose values change want fields."""
    return bool(wants) and all(
        isinstance(change, dict) and any(field in change for field in WANT_ORDER)
        for change in wants.values()
    )


def read_wants(value: Any) -> dict[str, Fields] | None:
    """A value read as want records: one dictionary keyed by provider address whose values are all
    want records (the contract's and the canonical map's form), or an older list of such objects.
    Anything else named `wants` is a namespace branch, as in the stored-document schema."""

    def is_record(record: Any) -> bool:
        return isinstance(record, dict) and isinstance(record.get("why"), str) and isinstance(record.get("how"), str)

    groups: list[dict[str, Any]]
    if isinstance(value, list):
        if not all(isinstance(item, dict) for item in value):
            return None
        groups = value
    elif isinstance(value, dict) and value and all(is_record(record) for record in value.values()):
        groups = [value]
    else:
        return None
    wants: dict[str, Fields] = {}
    for group in groups:
        for other, record in group.items():
            if not isinstance(record, dict):
                return None
            wants[other] = copy(record)
    return wants


def flatten(node: dict[str, Any], address: str, out: dict[str, Element]) -> None:
    """Split a nested object into one element for each address. An object value is a child
    element."""
    element = Element()
    children: list[tuple[str, dict[str, Any]]] = []
    for key, value in node.items():
        wants = read_wants(value) if key == "wants" else None
        if wants is not None:
            element.wants = wants
        elif isinstance(value, dict):
            children.append((names.join(address, key), value))
        else:
            element.fields[key] = copy(value)
    out[address] = element
    for child_address, child in children:
        flatten(child, child_address, out)
