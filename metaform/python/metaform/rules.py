"""Rules on an element's intake fields that need the map (R-3.11 to R-3.13), and the rule that a
layer's value is a list (R-6.24). `commands` applies them to every element a write touched.
Ports `rules.rs`.
"""
from typing import Any, Callable

from . import names, refusal, specification
from .model import Element, Map
from .names import ROOT
from .refusal import Refusal
from .values import copy, same, split_whitespace

# The four roles (R-3.13), spelled as a write must spell them.
ROLES = ("Definitive", "Supportive", "Notable", "Divergent")


def check(before: Map, address: str, element: Element) -> None:
    """Check one touched element: `technical_name` (R-3.11), then `role` (R-3.13). `before` is the
    map before the write.

    R-3.12 (`name` must not equal `technical_name`) is not checked. The intake procedure lets
    `name` be the standard term when the project has no name of its own for the element. The
    conflict between R-3.12 and the procedure is the owner's to settle (`SPEC.md` D-19)."""
    check_technical_name(before, address, element)
    check_role(before, address, element)
    check_system_layers(before, address, element)


def check_system_layers(before: Map, address: str, element: Element) -> None:
    """A system layer (`skills`, `memory`, `sources`) holds a list of records (R-6.15). A value
    this write set that is not a list is refused, with the value as one record in the
    remediation."""
    earlier = before.element(address)
    for layer in specification.SYSTEM_LAYERS:
        if layer not in element.fields:
            continue
        value = element.fields[layer]
        unchanged = earlier is not None and layer in earlier.fields and same(earlier.fields[layer], value)
        if not isinstance(value, list) and not unchanged:
            raise specification.not_a_list("update", layer, address, value)


def correction(before: Map, address: str, element: Element, field: str, value: str) -> dict[str, Any]:
    """The command that corrects one field. An element this write created is added again with the
    field corrected, because the refused write stored nothing; an existing one is updated."""
    if before.element(address) is not None:
        return {"update": {address: {field: value}}}
    view = copy(element.view())
    view[field] = value
    return {"add": {address: view}}


def _text(element: Element, field: str) -> str | None:
    value = element.fields.get(field)
    return value if isinstance(value, str) else None


def check_technical_name(before: Map, address: str, element: Element) -> None:
    """`technical_name` is the same number of leading words of the reversed, space-separated
    address (R-3.11). The root is the project: it has no address words and no `technical_name`."""
    technical = _text(element, "technical_name")
    if technical is None:
        return
    if address == ROOT:
        raise Refusal(
            refusal.TECHNICAL_NAME_ALIGNMENT_FAILURE,
            "'.': the root is the project and has no technical_name",
            {"update": {ROOT: {"technical_name": None}}},
        )
    reversed_words = [word for segment in reversed(address.split(".")) for word in segment.split("_")]
    words = split_whitespace(technical)
    if words and len(words) <= len(reversed_words) and words == reversed_words[: len(words)]:
        return
    # The suggestion is the reversed address without its root scope words: `code.cache.response`
    # gives "response cache".
    root_words = len(address.split(".")[0].split("_"))
    keep = max(len(reversed_words) - root_words, 1)
    suggested = " ".join(reversed_words[:keep])
    raise Refusal(
        refusal.TECHNICAL_NAME_ALIGNMENT_FAILURE,
        f"'{address}': technical_name \"{technical}\" is not the leading words of \"{' '.join(reversed_words)}\"",
        correction(before, address, element, "technical_name", suggested),
    )


def check_role(before: Map, address: str, element: Element) -> None:
    """A write that sets or changes `role` must set one of the four roles (R-3.13). A role the
    write did not change is not checked, so a stored map with older role names (`DE`, `SE`, `NE`,
    `CQU`) still accepts unrelated writes."""
    role = _text(element, "role")
    if role is None:
        return
    earlier = before.element(address)
    stored = None if earlier is None else _text(earlier, "role")
    if stored == role or role in ROLES:
        return
    raise Refusal(
        refusal.ROLE_TAXONOMY_FAILURE,
        f"'{address}': role \"{role}\" is not one of: {', '.join(ROLES)}",
        correction(before, address, element, "role", "<Definitive, Supportive, Notable or Divergent>"),
    )


def check_layer_values(map: Map, verb: str, address: str, fields: dict[str, Any]) -> None:
    """Refuse an object written where an element holds a layer's records (R-6.24). An object
    there would become an element beneath, which cannot share its name with the layer's field;
    the records stay, and the remediation gives the object as one record. `verb` is `add` or
    `update`, `address` the element the command names, `fields` what the command supplies for it,
    and `map` the map before the write."""
    defined = [d.layer for d in specification.definitions(map)]

    def is_layer(name: str) -> bool:
        return name in specification.SYSTEM_LAYERS or name in defined

    _layer_values(map, is_layer, verb, address, fields)


def _layer_values(map: Map, is_layer: Callable[[str], bool], verb: str, address: str, fields: dict[str, Any]) -> None:
    for key, value in fields.items():
        if not isinstance(value, dict):
            continue
        element = map.element(address)
        holds_records = element is not None and isinstance(element.fields.get(key), list)
        if holds_records and is_layer(key):
            raise specification.not_a_list(verb, key, address, value)
        _layer_values(map, is_layer, verb, names.join(address, key), value)
