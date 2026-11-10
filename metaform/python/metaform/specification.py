"""Layers defined in the map, and the specification layer (R-6.24 to R-6.28). Ports
`specification.rs`.

Every layer works the same way. A layer is defined by an element beneath the `layer` root scope
that has an `instruction` field. Its data sits on the receiving elements as a field named after
the definition's last segment, as a list of records: `layer.document.specification` defines the
field `specification`.

A definition may declare `format: "markdown_blocks"`. Its records are then blocks of prose,
`{"level": 1-4, "title": "...", "text": "..."}`, and the first block may be `{"text": "..."}`
alone, an intro with no heading. The tool refuses only what would break the Markdown round trip
or put records before the skeleton.

The export's element order (`scope_order`) and the lenient read of stored blocks (`stored`) are
not ported: only the specification export uses them, and this form does not offer it.
"""
from dataclasses import dataclass, replace
from typing import Any

from . import reads, refusal
from .model import Element, Fields, Map
from .names import ROOT, last_segment
from .refusal import Refusal
from .values import as_whole_number, ascii_lower, lines, trim, trim_end

# The system layers (R-6.15): defined in code, shared by every project, written by agents at an
# address without a definition in the map.
SYSTEM_LAYERS = ("skills", "memory", "sources")

# The root scope that holds layer definitions (R-3.3, R-6.24).
LAYER_SCOPE = "layer"

# The specification layer's field name at a receiving element.
LAYER = "specification"

# Where the specification layer is defined in each main map. Its last segment is `LAYER`.
DEFINITION_ADDRESS = "layer.document.specification"

# The record format whose records are Markdown blocks with enforced heading levels.
MARKDOWN_BLOCKS = "markdown_blocks"

# The deepest relative level. Element headings are `##` in the export, so level 4 is `######`,
# the deepest Markdown heading (R-6.25).
MAX_LEVEL = 4

# The largest level the Rust form holds (`u8::MAX`). A larger level is reported as this number.
_LEVEL_LIMIT = 255

# The specification layer's writing guidance: the short form of `TASTE.md` prepared for this
# layer, used as written.
INSTRUCTION = """Write each block in TASTE: Technically Accurate, Simple, Transparent English. A block adds what the map leaves out on purpose; do not repeat what the element's fields and wants already say.
- Start with what the element does or holds. Then give the detail that explains it.
- Name the element, field or command instead of starting with "it", "this" or "they". A block is often read alone.
- Use the project's terms and exact identifiers. Use one term for one thing. Put identifiers in backticks.
- Write one claim per sentence. Aim for 25 words or fewer per sentence and six sentences or fewer per paragraph. Never cut a condition, an exception or a reason to meet a length target.
- Use lowercase must, should, may, can and might with their TASTE meanings. Do not write SHALL or capitalized MUST.
- Say whether something is built, proposed or planned. Do not describe planned behavior as if it exists.
- Replace words such as simple, robust or fast with the behavior or a measurement.
- Define an abbreviation at its first use. Keep noun clusters to three nouns.
- Leave out openings such as "This section describes", repeated points, analogies and promotion.
- Prefer start, use, adjust, perform and end over kick off/launch/begin, utilize/leverage, modify/change/alter, execute/run and terminate/stop/abort, when the meaning stays the same.
- Do not put Markdown heading lines in the text. Set the block's level and title instead."""

# How records of the `markdown_blocks` format are written through the tool (R-6.25, R-6.26).
# `goto` delivers it before the definition's own instruction. `{layer}` is the field name.
MARKDOWN_FORM = 'The {layer} field is a list of blocks: {"level": 1-4, "title": "...", "text": "..."}. A titled block may also carry "code", a key that other text can cite; it is unique in the layer across the map, ignoring case. The first block may be {"text": "..."} alone, as an intro under the element\'s heading. The first titled block is level 1, and each level is at most one more than the level before it. update replaces every block at the address and is safe to repeat; add appends blocks; if an answer is lost, a retried add appends them twice. Read them with {"<address>": {"{layer}": {}}}. The root\'s blocks are in the raw dump {".": {}}, because a key that starts with a period is a raw dump. Blocks are accepted at an element that has technical_name, name and role, and at . once the map has a Definitive element.'


def definition() -> Fields:
    """The fields of the specification layer's definition element at `DEFINITION_ADDRESS`. The
    store writes it into each main map, so `goto` always finds the layer (R-6.24)."""
    return {
        "technical_name": "specification document layer",
        "name": "Specification",
        "role": "Supportive",
        "description": "Prose that the skeleton leaves out on purpose: what each element does, how it behaves and why, as blocks with Markdown heading levels.",
        "template": "{title}: {text}",
        "format": MARKDOWN_BLOCKS,
        "instruction": INSTRUCTION,
    }


@dataclass(frozen=True)
class Definition:
    """One layer definition found in the map."""

    # The field name at receiving elements: the definition's last address segment.
    layer: str
    # The definition element's address.
    address: str
    # The record format, such as `markdown_blocks`, if the definition declares one.
    format: str | None
    # The writing guidance for the layer.
    instruction: str

    def guidance(self) -> str:
        """The guidance `goto` delivers: the format's rules, then the definition's own
        instruction."""
        if self.format == MARKDOWN_BLOCKS:
            return f"{MARKDOWN_FORM.replace('{layer}', self.layer)}\n{self.instruction}"
        return self.instruction


def definitions(map: Map) -> list[Definition]:
    """Every layer defined in the map, by field name. A write cannot create two definitions with
    the same last segment; if stored data has them, the definition whose address sorts first
    wins."""
    out: list[Definition] = []
    for address, element in map.elements():
        if not is_beneath_layer_scope(address):
            continue
        instruction = element.fields.get("instruction")
        if not isinstance(instruction, str):
            continue
        layer = last_segment(address)
        if any(d.layer == layer for d in out):
            continue
        form = element.fields.get("format")
        out.append(Definition(layer, address, form if isinstance(form, str) else None, instruction))
    return out


def definition_of(map: Map, layer: str) -> Definition | None:
    """The definition of one layer, if the map defines it."""
    return next((d for d in definitions(map) if d.layer == layer), None)


def in_layer_scope(address: str) -> bool:
    """Whether an address is the `layer` root scope or beneath it, where layer definitions live,
    outside the functional skeleton (R-3.20)."""
    return address == LAYER_SCOPE or is_beneath_layer_scope(address)


def is_beneath_layer_scope(address: str) -> bool:
    return address.startswith(LAYER_SCOPE + ".")


@dataclass(frozen=True)
class Block:
    """One block of a `markdown_blocks` layer."""

    # The relative heading level, 1 to `MAX_LEVEL`. `None` only for an intro block.
    level: int | None
    # The heading text. `None` only for an intro block.
    title: str | None
    # Markdown body text, with no heading lines. Stored with LF line ends and trimmed.
    text: str
    # An optional key that other text can cite, unique within the layer across the whole map,
    # ignoring case. Only a titled block has one.
    code: str | None = None

    def is_intro(self) -> bool:
        return self.title is None

    def to_json(self) -> dict[str, Any]:
        """The block as the tool stores and returns it."""
        if self.level is None or self.title is None:
            return {"text": self.text}
        out: dict[str, Any] = {"level": self.level}
        if self.code is not None:
            out["code"] = self.code
        out["title"] = self.title
        out["text"] = self.text
        return out


def to_json(blocks: list[Block]) -> list[Any]:
    """The blocks as the tool stores them."""
    return [block.to_json() for block in blocks]


def _filled(element: Element | None, key: str) -> bool:
    value = None if element is None else element.fields.get(key)
    return isinstance(value, str) and trim(value) != ""


def is_skeleton(element: Element) -> bool:
    """An element is part of the skeleton when intake has given it every mandatory field (R-3.4):
    `technical_name`, `name` and `role`. Only then may it hold layer records (R-6.26)."""
    return all(_filled(element, key) for key in ("technical_name", "name", "role"))


def records_allowed(map: Map, address: str) -> bool:
    """Whether layer records may sit at an address: a skeleton element outside the `layer` scope,
    or the root once the map has a Definitive element (R-6.26)."""
    if address == ROOT:
        return any(reads.is_project_definitive(at, element.fields.get("role")) for at, element in map.elements())
    element = map.element(address)
    return not in_layer_scope(address) and element is not None and is_skeleton(element)


def applies(map: Map, address: str) -> bool:
    """Whether the specification layer applies at an address: the map defines it, and records are
    allowed there."""
    return definition_of(map, LAYER) is not None and records_allowed(map, address)


ATX = "atx"
SETEXT = "setext"


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def heading_in_text(text: str) -> tuple[int, str] | None:
    """The first Markdown heading line in `text` outside fenced code, as a 0-based line index and
    its kind, `ATX` or `SETEXT`. For a setext heading the index is the underline's; the heading
    text is the line before."""
    fence: tuple[str, int] | None = None
    previous: str | None = None
    for index, line in enumerate(lines(text)):
        indent = _indent(line)
        body = line[indent:]
        mark = fence_mark(body) if indent <= 3 else None
        if mark is not None:
            if fence is None:
                fence = mark
            elif fence[0] == mark[0] and mark[1] >= fence[1] and all(c == mark[0] for c in trim_end(body)):
                fence = None
            previous = None
            continue
        if fence is not None:
            continue
        if indent <= 3 and is_atx(body):
            return index, ATX
        if indent <= 3 and is_underline(body) and previous is not None and is_paragraph_line(previous):
            return index, SETEXT
        previous = line
    return None


def fence_mark(body: str) -> tuple[str, int] | None:
    """A fence opener or closer: three or more backticks or tildes."""
    if not body or body[0] not in "`~":
        return None
    mark = body[0]
    run = len(body) - len(body.lstrip(mark))
    return (mark, run) if run >= 3 else None


def is_atx(body: str) -> bool:
    hashes = len(body) - len(body.lstrip("#"))
    return 1 <= hashes <= 6 and (len(body) == hashes or body[hashes] in " \t")


def is_underline(body: str) -> bool:
    body = trim_end(body)
    return body != "" and (all(c == "=" for c in body) or all(c == "-" for c in body))


def is_paragraph_line(line: str) -> bool:
    """A line that a setext underline would turn into a heading: not blank, not indented as code,
    and not a list item, table row or heading."""
    indent = _indent(line)
    body = trim(line)
    if body == "" or indent > 3 or body.startswith("|") or body.startswith(">") or is_atx(body):
        return False
    if body.startswith(("- ", "* ", "+ ")):
        return False
    digits = 0
    while digits < len(body) and "0" <= body[digits] <= "9":
        digits += 1
    return not (digits > 0 and body[digits:].startswith((". ", ") ")))


def is_element_heading_form(title: str) -> bool:
    """Whether a title has the form the export reserves for element headings: it ends with an
    address in backticks inside parentheses, such as "Name (`code.engine`)"."""
    title = trim_end(title)
    return title.endswith("`)") and "(`" in title


def example(layer: str, address: str) -> dict[str, Any]:
    """An example of valid blocks, given as the remediation of a malformed block."""
    return {"update": {address: {layer: [
        {"text": "<intro prose, optional>"},
        {"level": 1, "title": "<heading>", "text": "<prose>"},
        {"level": 2, "title": "<subheading>", "text": "<prose>"},
    ]}}}


def blocks_of(layer: str, address: str, value: Any) -> list[Block]:
    """Read and normalize the blocks of a `markdown_blocks` layer value. The value must be a
    list; each block must have the block shape. Line ends become LF and title and text are
    trimmed, so the stored form is the form the export writes and the import reads back."""

    def mismatch(why: str) -> Refusal:
        return Refusal(refusal.FIELD_MISMATCH, f"'{address}': {layer}: {why}", example(layer, address))

    if not isinstance(value, list):
        raise mismatch("must be a list of blocks")
    out: list[Block] = []
    for index, item in enumerate(value):
        n = index + 1
        if not isinstance(item, dict):
            raise mismatch(f"block {n} must be an object")
        for key in item:
            if key not in ("level", "title", "text", "code"):
                raise mismatch(f"block {n} does not take: {key}")
        text = ""
        if "text" in item:
            if not isinstance(item["text"], str):
                raise mismatch(f"block {n}: text must be a string")
            text = normalize(item["text"])
        title: str | None = None
        if "title" in item:
            if not isinstance(item["title"], str):
                raise mismatch(f"block {n}: title must be a string")
            title = normalize(item["title"])
        level: int | None = None
        if "level" in item:
            level = as_whole_number(item["level"])
            if level is None:
                raise mismatch(f"block {n}: level must be a whole number from 1 to {MAX_LEVEL}")
        code: str | None = None
        if "code" in item:
            code = item["code"]
            if not isinstance(code, str) or not is_code(code):
                raise mismatch(
                    f"block {n}: code must be one token of 1 to 32 letters, digits, '.', '_' or '-', starting with a letter and ending with a letter or digit, such as R-1.2"
                )
        if code is not None and title is None:
            raise mismatch(f"block {n}: only a block with a level and title can have a code")
        if level is None and title is None:
            if index > 0:
                raise mismatch(f"block {n} has no level and title; only the first block may be an intro")
            if text == "":
                raise mismatch("block 1 is an intro with no text")
            out.append(Block(None, None, text))
        elif level is not None and title is not None:
            if title == "" or "\n" in title:
                raise mismatch(f"block {n}: title must be one line of text")
            if title.startswith("`"):
                raise mismatch(
                    f"block {n}: title must not start with a backtick; the export writes the block's code there"
                )
            if title.startswith("#"):
                raise mismatch(f"block {n}: title must not start with '#'; the level sets the heading")
            if is_element_heading_form(title):
                raise mismatch(
                    f"block {n}: title must not end with an address in backticks inside parentheses; the export uses that form for element headings"
                )
            out.append(Block(min(level, _LEVEL_LIMIT), title, text, code))
        else:
            raise mismatch(f"block {n} needs both level and title, or neither for an intro")
    return out


def is_code(code: str) -> bool:
    """A block code: a letter, then up to 31 letters, digits, `.`, `_` or `-`, ending with a
    letter or digit. It has no spaces or backticks, so it survives the Markdown export."""
    raw = code.encode("utf-8")

    def letter(byte: int) -> bool:
        return 65 <= byte <= 90 or 97 <= byte <= 122

    def letter_or_digit(byte: int) -> bool:
        return letter(byte) or 48 <= byte <= 57

    return (
        1 <= len(raw) <= 32
        and letter(raw[0])
        and letter_or_digit(raw[-1])
        and all(letter_or_digit(byte) or byte in b"._-" for byte in raw)
    )


def check_codes(map: Map, address: str, layer: str, blocks: list[Block]) -> None:
    """Refuse a code in `blocks` (just written at `address`) that another block of the same layer
    already holds, anywhere in the map after the write, ignoring case. The remediation is the
    same update with that block's code removed."""
    held: list[tuple[str, str, int]] = []
    for holder, element in map.elements():
        if holder == address:
            continue
        # Read codes from the stored JSON, not parsed blocks, so a holder whose blocks predate
        # the rules still counts.
        stored = element.fields.get(layer)
        if not isinstance(stored, list):
            continue
        for index, record in enumerate(stored):
            code = record.get("code") if isinstance(record, dict) else None
            if isinstance(code, str):
                held.append((ascii_lower(code), holder, index + 1))
    for index, block in enumerate(blocks):
        if block.code is None:
            continue
        key = ascii_lower(block.code)
        found: tuple[str, int] | None = None
        for i, earlier in enumerate(blocks[:index]):
            if earlier.code is not None and ascii_lower(earlier.code) == key:
                found = (address, i + 1)
                break
        if found is None:
            found = next(((holder, n) for k, holder, n in held if k == key), None)
        if found is not None:
            holder, n = found
            fixed = list(blocks)
            fixed[index] = replace(block, code=None)
            raise Refusal(
                refusal.CODE_NOT_UNIQUE,
                f"'{address}': {layer} block {index + 1} has code {block.code}, which '{holder}' block {n} already holds; a code is unique in the {layer} layer, ignoring case",
                {"update": {address: {layer: to_json(fixed)}}},
            )


def normalize(text: str) -> str:
    return trim(text.replace("\r\n", "\n").replace("\r", "\n"))


def clamp_levels(blocks: list[Block]) -> list[Block]:
    """The blocks with each level brought into the rules: the first titled block at 1, each next
    block at most one deeper, and none beyond `MAX_LEVEL`."""
    previous = 0
    out: list[Block] = []
    for block in blocks:
        if block.level is not None:
            fixed = max(1, min(block.level, min(previous + 1, MAX_LEVEL)))
            block = replace(block, level=fixed)
            previous = fixed
        out.append(block)
    return out


def split_headings(blocks: list[Block]) -> list[Block]:
    """The blocks with each heading line in a text moved out into a block of its own, one level
    deeper than the block it was in. This is the remediation for `HEADING_IN_TEXT`."""
    out: list[Block] = []
    for block in blocks:
        rest = block
        while True:
            found = heading_in_text(rest.text)
            if found is None:
                out.append(rest)
                break
            index, kind = found
            source = lines(rest.text)
            title_line, body_from = (index, index + 1) if kind == ATX else (index - 1, index + 1)
            title = trim(trim(trim(source[title_line]).lstrip("#")).rstrip("#"))
            level = 1 if rest.level is None else min(rest.level + 1, MAX_LEVEL)
            before = trim("\n".join(source[:title_line]))
            after = trim("\n".join(source[body_from:]))
            rest = replace(rest, text=before)
            if not (rest.is_intro() and rest.text == ""):
                out.append(rest)
            rest = Block(level, title if title else "<heading>", after)
    return clamp_levels(out)


def not_a_list(verb: str, layer: str, address: str, value: Any) -> Refusal:
    """The refusal for a layer value that is not a list. The remediation is the same write with
    the value as the one record of a list."""
    return Refusal(
        refusal.FIELD_MISMATCH,
        f"'{address}': {layer}: a layer's value must be a list of records",
        {verb: {address: {layer: [value]}}},
    )


def records(layer: str, address: str, value: Any) -> list[Any]:
    """The records of any defined layer: the value must be a list (R-6.24)."""
    if not isinstance(value, list):
        raise not_a_list("update", layer, address, value)
    return value


def check_allowed(map: Map, address: str, layer: str) -> None:
    """Refuse records of any layer at an address where records are not allowed (R-6.26). `map` is
    the map after the write."""
    if records_allowed(map, address):
        return
    # No command lets a layer definition hold records, so that refusal has no remediation.
    remediation: Any
    if address == ROOT:
        remediation = {"update": {"<definitive address>": {"role": "Definitive"}}}
        reason = f"'.': {layer} records at the root need a Definitive element in the map first"
    elif in_layer_scope(address):
        remediation = None
        reason = f"'{address}': {layer} records do not go on layer definitions"
    else:
        element = map.element(address)
        fix = {key: f"<{key}>" for key in ("technical_name", "name", "role") if not _filled(element, key)}
        remediation = {"update": {address: fix}}
        reason = f"'{address}': {layer} records need an element with technical_name, name and role; intake has not placed it in the skeleton yet"
    raise Refusal(refusal.ELEMENT_NOT_IN_SKELETON, reason, remediation)


def check_blocks(address: str, layer: str, blocks: list[Block]) -> None:
    """Check the blocks of a `markdown_blocks` layer written at an address (R-6.25)."""
    previous = 0
    for index, block in enumerate(blocks):
        level = block.level
        if level is None:
            continue
        allowed = min(previous + 1, MAX_LEVEL)
        if level < 1 or level > allowed:
            if not 1 <= level <= MAX_LEVEL:
                why = f"level {level} is outside 1 to {MAX_LEVEL}"
            elif previous == 0:
                why = f"level {level}; the first titled block is level 1"
            else:
                why = f"level {level} follows level {previous}; a level is at most one more than the level before it"
            raise Refusal(
                refusal.HEADING_LEVEL_INVALID,
                f"'{address}': {layer} block {index + 1} (\"{block.title or ''}\"): {why}",
                {"update": {address: {layer: to_json(clamp_levels(blocks))}}},
            )
        previous = level
    for index, block in enumerate(blocks):
        found = heading_in_text(block.text)
        if found is not None:
            line, kind = found
            what = (
                "a Markdown heading line"
                if kind == ATX
                else "a line of = or - under a paragraph line, which Markdown reads as a heading"
            )
            raise Refusal(
                refusal.HEADING_IN_TEXT,
                f"'{address}': {layer} block {index + 1}: text line {line + 1} is {what}; set a block's level and title instead",
                {"update": {address: {layer: to_json(split_headings(blocks))}}},
            )
