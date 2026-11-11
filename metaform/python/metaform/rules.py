"""Rules on an element's intake fields that need the map (R-3.11 to R-3.13), and the rule that a
layer's value is a list (R-6.24). `commands` applies them to every element a write touched.
The grammar of a want's `why` and `how` (R-3.17, R-6.17) is checked here too, for the parts a
write sets. Ports `rules.rs`.
"""
from typing import Any, Callable

from . import names, refusal, specification
from .model import Element, Map
from .names import ROOT
from .refusal import Refusal
from .values import ascii_lower, copy, is_space, same, split_whitespace, trim

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


# The rule text that ends the message of every grammar refusal. The message is the only place an
# agent learns the rule, so it states the whole rule and is the same in every form of Metaform.
# The faults of the refused want come before it (`grammar_fault`).
GRAMMAR_RULE = "why is one fragment that starts with a base verb; how is one fragment that starts with a verb ending in -s. No leading 'to', no subject, no '-ing' verb, no values. Detail belongs in a knowledge layer."

# The text an agent must replace in the remediation of a grammar refusal.
WHY_PLACEHOLDER = "<base verb phrase, as: drain raw frames from the network interface card>"
HOW_PLACEHOLDER = "<verb phrase ending in -s, as: holds descriptor pointers across contiguous memory segments>"

# Base verbs that end in `ing`. A `why` may start with one; any other first word that ends in
# `ing` is taken as an `-ing` verb form.
ING_BASE_VERBS = (
    "bring", "cling", "ding", "fling", "ping", "ring", "sing", "sling", "spring", "sting", "string", "swing",
    "wring", "zing",
)

# First words that make the text a clause with a subject, not a verb phrase.
SUBJECT_WORDS = ("the", "a", "an", "this", "that", "these", "those", "it", "its", "we", "they", "each", "every")

_DIGITS = "0123456789"


def _first_word(text: str) -> str:
    """The first word of the text: the characters before the first white space, with A to Z
    lowered and any trailing `.,;:!?` removed."""
    words = split_whitespace(text)
    return ascii_lower(words[0]).rstrip(".,;:!?") if words else ""


def _has_many_fragments(text: str) -> bool:
    """Whether the text holds more than one fragment: `.`, `!`, `?` or `;` followed by white
    space and then more text. One trailing full stop is not a second fragment."""
    trimmed = trim(text)
    return any(a in ".!?;" and is_space(b) for a, b in zip(trimmed, trimmed[1:]))


def _is_letter(character: str) -> bool:
    """A letter, for the number rule: A to Z in either case, or any character outside ASCII. The
    three forms of Metaform use this one definition, so they decide the same."""
    return "a" <= character <= "z" or "A" <= character <= "Z" or ord(character) > 127


def _has_lone_number(text: str) -> bool:
    """Whether the text holds a number that stands alone: a run of digits 0 to 9, with an
    optional decimal part, that is not part of a word. The run is part of a word when a letter
    follows it directly, or when a letter directly precedes it or precedes the digits, `/`, `-`
    and `_` that join it to the word. `S256`, `OAuth2`, `utf-8`, `HTTP/2` and `x86-64` are words;
    `5` and `3.9` stand alone. A want states what happens without tunable values (R-3.17)."""

    def digit(at: int) -> bool:
        return at < len(text) and text[at] in _DIGITS

    at = 0
    while at < len(text):
        if not digit(at):
            at += 1
            continue
        start = at
        while digit(at):
            at += 1
        if at < len(text) and text[at] == "." and digit(at + 1):
            at += 1
            while digit(at):
                at += 1
        letter_after = at < len(text) and _is_letter(text[at])
        word_start = start
        while word_start > 0 and (text[word_start - 1] in _DIGITS or text[word_start - 1] in "/-_"):
            word_start -= 1
        letter_before = word_start > 0 and _is_letter(text[word_start - 1])
        if not letter_after and not letter_before:
            return True
    return False


def grammar_fault(field: str, text: str) -> str | None:
    """The first fault of a `why` or a `how` against the grammar of its field (R-3.17, R-6.17),
    in the words of the refusal message, or None when the text follows the rule. `field` is
    `why` or `how`. The checks have a fixed order, the same in every form of Metaform. For a
    `how` the subject check comes before the `-s` check, so `The router stores` is reported as a
    subject. The case of the first letter, one trailing full stop, length, and words ending in
    `-ing` after the first word are not checked (`SPEC.md` D-14)."""
    first = _first_word(text)
    subject = first in SUBJECT_WORDS
    if field == "why":
        if first == "to":
            return "starts with 'to'"
        if first.endswith("ing") and first not in ING_BASE_VERBS:
            return "starts with an '-ing' verb"
        if subject:
            return "starts with a subject"
    else:
        if subject:
            return "starts with a subject"
        if not first.endswith("s"):
            return "does not start with a verb ending in -s"
    if _has_many_fragments(text):
        return "holds more than one fragment"
    if _has_lone_number(text):
        return "holds a value"
    return None


def check_want_grammar(
    before: Map, elements: dict[str, Element], holder: str, other: str, written: list[str]
) -> None:
    """Check the `why` and `how` that a command wrote in one want. `written` names the parts the
    command wrote; a part it did not write is not checked, so a stored want with older text still
    accepts an unrelated write. `elements` is the map as the command would leave it.

    The refusal follows the documentation set, module 6.4. The message names each part that
    broke the rule and its first fault, `why` before `how`, and then states the rule. The tested
    sentence is the wants sentence of R-6.17 with the texts as written, without their trailing
    full stop. The remediation updates the want with a placeholder in each part that broke the rule. For a want
    that `before` holds, it has only those parts. For a want this command made, it has the whole
    want, because the refused command stored nothing and a want needs all of its fields (R-5.6)."""
    element = elements.get(holder)
    record = None if element is None else element.wants.get(other)
    if record is None:
        return

    def text(key: str) -> str:
        value = record.get(key)
        return value if isinstance(value, str) else ""

    broken: dict[str, Any] = {}
    faults: list[str] = []
    for key, placeholder in (("why", WHY_PLACEHOLDER), ("how", HOW_PLACEHOLDER)):
        if key not in written or trim(text(key)) == "":
            continue
        fault = grammar_fault(key, text(key))
        if fault is not None:
            broken[key] = placeholder
            faults.append(f"{key} {fault}")
    if not broken:
        return
    earlier = before.element(holder)
    stored = earlier is not None and other in earlier.wants
    parts = broken if stored else {**copy(record), **broken}

    def named(address: str) -> str:
        at = elements.get(address)
        name = None if at is None else _text(at, "name")
        return f"{address} ({name})" if name is not None and trim(name) != "" else address

    def part(key: str) -> str:
        return trim(text(key)).rstrip(".")

    refused = Refusal(
        refusal.GRAMMAR_CONSTRAINT_VIOLATION,
        f"{'; '.join(faults)}. {GRAMMAR_RULE}",
        {"update": {holder: {"wants": {other: parts}}}},
    )
    refused.sentence = f"{named(holder)} requires {named(other)} in order to {part('why')}, which {part('how')}."
    raise refused
