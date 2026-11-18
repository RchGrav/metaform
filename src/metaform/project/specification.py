"""The specification overlay and its document: prose blocks at the elements they describe, rendered as one Markdown
document and read back from an edited copy (kickoff 2026-11-17 Phase 4, audit F06; docs/plans/specifications-overlay.md).

Ported from the Rust branch's design, built and tested there on 2026-11-09 (`core/metaform/rust/crates/metaform-core/
src/specification.rs` and `markdown.rs`), keeping the Python store's later decisions: overlays, not layers, defined
beneath `overlay`; one ref per record; no `goto`. Render, parse and render again give the same document, byte for
byte.

A block is `{level, title, text}` with an optional `code`, unique across the project ignoring case, that other text
can cite. The first block at an element may be text alone, its introduction. Levels are relative to the element's
heading: the first titled block is level 1, each next at most one deeper, none beyond 4. The tool refuses only what
would break the round trip: a skipped level, a heading line inside text, a title that is not one line, a code used
twice.

The project's root holds blocks too, the project's own description (audit F07): written at the path that is the
project's name alone, rendered between the project's heading and the first element, one Markdown level deeper than
the block's level, as `markdown.rs` renders them.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, cast

from metaform.project.forms import Refusal

KEY = 'specification'
DEFINITION_PATH = 'overlay.specification'
MAX_LEVEL = 4
PROJECT_HASHES, ELEMENT_HASHES = 1, 2
ROOT_ORDER = ('code', 'document', 'media', 'data', 'upstream', 'downstream')  # forms.ROOTS, without the overlays

# The writing guidance the Rust design gives the overlay (TASTE, prepared by its TASTE auditor), as written there.
INSTRUCTION = (
    'Write each block in TASTE: Technically Accurate, Simple, Transparent English. A block adds what the map leaves '
    "out on purpose; do not repeat what the element's fields and wants already say. Start with what the element does "
    'or holds, then the detail that explains it. Name the element, field or command instead of starting with "it", '
    '"this" or "they"; a block is often read alone. Use the project\'s terms and exact identifiers, one term for one '
    'thing, identifiers in backticks. One claim per sentence. Say whether something is built, proposed or planned. Do '
    "not put Markdown heading lines in the text: set the block's level and title instead. The first block may be text "
    'alone, an introduction; the first titled block is level 1 and each level is at most one more than the one before.')

DEFINITION: dict[str, object] = {
    'description': 'What each part of the project is for, in prose the map leaves out on purpose: the '
                   "specification's text at the elements it describes.",
    'instruction': INSTRUCTION,
    'level': {'type': 'number', 'rule': 'The heading level under the element, 1 to 4; left out for an introduction.',
              'example': 1, 'optional': True},
    'title': {'type': 'text', 'rule': 'The heading, one line; left out for an introduction.', 'example': 'Purpose',
              'optional': True},
    'text': {'type': 'text', 'rule': 'The prose under the heading, with no Markdown heading lines.',
             'example': 'The `watch` command rings each timer as it ends.', 'optional': True},
    'code': {'type': 'text', 'rule': 'A key other text can cite, unique in the project: 1 to 32 letters, digits, '
                                     "'.', '_' or '-', starting with a letter.", 'example': 'R-1.2', 'optional': True},
}


@dataclass(frozen=True)
class Block:
    level: int | None
    title: str | None
    text: str
    code: str | None = None

    def stored(self) -> dict[str, object]:
        return {name: value for name, value in (('level', self.level), ('title', self.title),
                                                 ('text', self.text or None), ('code', self.code)) if value is not None}


def digest(block: Block) -> str:
    """A short digest of a block's fields, so a document says what each block held when it was exported."""
    return hashlib.sha256(json.dumps(block.stored(), sort_keys=True).encode('utf-8')).hexdigest()[:12]


# The export's last line: each address's blocks as they were exported, [record id, digest] in order, so an import can
# tell what the person edited from what changed in the store since, and keep each block's id (review of 2026-11-18,
# F5). An HTML comment, so the rendered Markdown does not show it.
BASELINE = '<!-- metaform specification baseline: '
Baseline = dict[str, list[list[Any]]]  # each block as [record id, digest, level, title]


def baseline_line(held: Baseline) -> str:
    return f"{BASELINE}{json.dumps(held, sort_keys=True, separators=(',', ':'))} -->"


def split_baseline(document: str) -> tuple[str, Baseline | None]:
    """A document and its baseline: the document without its baseline line, and the baseline, or None when it has
    none or the line cannot be read."""
    lines = document.rstrip('\n').split('\n')
    if not lines or not lines[-1].startswith(BASELINE) or not lines[-1].endswith(' -->'):
        return document, None
    try:
        found = json.loads(lines[-1][len(BASELINE):-len(' -->')])
    except ValueError:
        return document, None
    if not isinstance(found, dict):
        return document, None
    body = '\n'.join(lines[:-1]).rstrip('\n') + '\n'
    return body, cast(Baseline, found)


class ParseError(Exception):
    """A document that cannot be read back, at a line, with the reason."""

    def __init__(self, line: int, reason: str) -> None:
        super().__init__(f'line {line}: {reason}')
        self.line, self.reason = line, reason


# ---- Markdown line rules (CommonMark block starts), as markdown.rs and specification.rs read them ----

def _unindented(line: str) -> str | None:
    spaces = len(line) - len(line.lstrip(' '))
    return line[spaces:] if spaces <= 3 else None


def atx_level(line: str) -> int | None:
    rest = _unindented(line)
    if rest is None:
        return None
    hashes = len(rest) - len(rest.lstrip('#'))
    after = rest[hashes:hashes + 1]
    return hashes if 1 <= hashes <= 6 and after in ('', ' ', '\t') else None


def _atx_text(line: str) -> str:
    rest = (_unindented(line) or line).lstrip('#').strip()
    closed = rest.rstrip('#')
    if len(closed) < len(rest) and (not closed or closed.endswith(' ')):
        return closed.rstrip()
    return rest


def is_code(code: str) -> bool:
    return (1 <= len(code) <= 32 and code[0].isascii() and code[0].isalpha() and code[-1].isascii()
            and code[-1].isalnum() and all(c.isascii() and (c.isalnum() or c in '._-') for c in code))


def _split_code(text: str) -> tuple[str | None, str]:
    if text.startswith('`') and '`' in text[1:]:
        code, _, title = text[1:].partition('`')
        if is_code(code):
            return code, title.strip()
    return None, text


def _opens_fence(line: str) -> tuple[str, int] | None:
    rest = _unindented(line)
    if not rest or rest[0] not in '`~':
        return None
    length = len(rest) - len(rest.lstrip(rest[0]))
    return (rest[0], length) if length >= 3 else None


def _closes_fence(line: str, mark: str, length: int) -> bool:
    rest = _unindented(line)
    if rest is None:
        return False
    run = len(rest) - len(rest.lstrip(mark))
    return run >= length and not rest[run:].strip()


def _is_paragraph_line(line: str) -> bool:
    indent = len(line) - len(line.lstrip(' '))
    body = line.strip()
    if not body or indent > 3 or body[0] in '|>' or atx_level(body) is not None:
        return False
    digits = len(body) - len(body.lstrip('0123456789'))
    listed = body[:2] in ('- ', '* ', '+ ') or (digits > 0 and body[digits:digits + 2] in ('. ', ') '))
    return not listed


def heading_in_text(text: str) -> tuple[int, str] | None:
    """The first Markdown heading line in text outside fenced code: its 0-based index and `atx` or `setext`."""
    fence: tuple[str, int] | None = None
    previous: str | None = None
    for index, line in enumerate(text.split('\n')):
        indent = len(line) - len(line.lstrip(' '))
        body = line[indent:]
        mark = body[:1] if body[:1] in ('`', '~') else ''
        run = len(body) - len(body.lstrip(mark)) if mark else 0
        if indent <= 3 and run >= 3:
            if fence is None:
                fence = (mark, run)
            elif fence[0] == mark and run >= fence[1] and set(body.rstrip()) == {mark}:
                fence = None
            previous = None
            continue
        if fence is not None:
            continue
        if indent <= 3 and atx_level(body) is not None:
            return index, 'atx'
        stripped = body.rstrip()
        if indent <= 3 and stripped and set(stripped) in ({'='}, {'-'}) and previous is not None \
                and _is_paragraph_line(previous):
            return index, 'setext'
        previous = line
    return None


def _normalize(text: str) -> str:
    return text.replace('\r\n', '\n').replace('\r', '\n').strip()


def _element_heading_form(title: str) -> bool:
    title = title.rstrip()
    return title.endswith('`)') and '(`' in title


# ---- The block rules, checked on every write that changes blocks ----

def blocks(address: str, records: list[dict[str, Any]]) -> list[Block]:
    """The records at an element as blocks, refused with FIELD_MISMATCH where one breaks the round trip's shape."""
    out: list[Block] = []
    for index, record in enumerate(records):
        n = index + 1

        def wrong(why: str, n: int = n) -> Refusal:
            return Refusal('FIELD_MISMATCH', f"'{address}': {KEY} block {n}: {why}")
        text = _normalize(str(record.get('text') or ''))
        title = _normalize(str(record['title'])) if record.get('title') is not None else None
        level, code = record.get('level'), record.get('code')
        if level is not None and (not isinstance(level, int) or isinstance(level, bool)):
            raise wrong(f'level must be a whole number from 1 to {MAX_LEVEL}')
        if code is not None and not (isinstance(code, str) and is_code(code)):
            raise wrong("code must be one token of 1 to 32 letters, digits, '.', '_' or '-', starting with a letter "
                        'and ending with a letter or digit, such as R-1.2')
        if code is not None and title is None:
            raise wrong('only a block with a level and title can have a code')
        if level is None and title is None:
            if index > 0:
                raise wrong('has no level and title; only the first block may be an introduction')
            if not text:
                raise wrong('is an introduction with no text')
            out.append(Block(None, None, text))
        elif level is not None and title is not None:
            if not title or '\n' in title:
                raise wrong('title must be one line of text')
            if title.startswith('`'):
                raise wrong("title must not start with a backtick; the export writes the block's code there")
            if title.startswith('#'):
                raise wrong("title must not start with '#'; the level sets the heading")
            if _element_heading_form(title):
                raise wrong('title must not end with an address in backticks inside parentheses; the export uses that '
                            'form for element headings')
            out.append(Block(level, title, text, code))
        else:
            raise wrong('a heading has both a level and a title, or neither for an introduction')
    previous = 0
    for index, block in enumerate(out):
        if block.level is None:
            continue
        allowed = min(previous + 1, MAX_LEVEL)
        if not 1 <= block.level <= allowed:
            why = (f'level {block.level} is outside 1 to {MAX_LEVEL}' if not 1 <= block.level <= MAX_LEVEL else
                   f'level {block.level}; the first titled block is level 1' if previous == 0 else
                   f'level {block.level} follows level {previous}; a level is at most one more than the level before')
            raise Refusal('HEADING_LEVEL_INVALID', f"'{address}': {KEY} block {index + 1} (\"{block.title}\"): {why}")
        previous = block.level
    for index, block in enumerate(out):
        found = heading_in_text(block.text)
        if found is not None:
            what = ('a Markdown heading line' if found[1] == 'atx' else
                    'a line of = or - under a paragraph line, which Markdown reads as a heading')
            raise Refusal('HEADING_IN_TEXT', f"'{address}': {KEY} block {index + 1}: text line {found[0] + 1} is "
                          f"{what}; set a block's level and title instead")
    return out


def check_codes(where: dict[str, list[dict[str, Any]]]) -> None:
    """No code is held by two blocks in the project, ignoring case. `where` is every element's records."""
    held: dict[str, str] = {}
    for address in sorted(where):
        for record in where[address]:
            code = record.get('code')
            if not isinstance(code, str):
                continue
            if code.lower() in held:
                raise Refusal('CODE_TAKEN', f"{KEY} code {code!r} at '{address}' is already used at "
                              f"'{held[code.lower()]}'; each code is unique across the specification, ignoring case")
            held[code.lower()] = address


# ---- The document ----

def _text(fields: dict[str, Any], key: str) -> str | None:
    value = fields.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _display_name(elements: dict[str, dict[str, Any]], address: str) -> str:
    fields = elements.get(address) or {}
    return _text(fields, 'name') or _text(fields, 'technical_name') or address


def element_heading(elements: dict[str, dict[str, Any]], address: str) -> str:
    return f"{'#' * ELEMENT_HASHES} {_display_name(elements, address)} (`{address}`)"


def _fragment(text: str) -> str:
    trimmed = text.strip().rstrip('.')
    if len(trimmed) > 1 and trimmed[0].isupper() and trimmed[1].islower():
        return trimmed[0].lower() + trimmed[1:]
    return trimmed


def skeleton_facts(elements: dict[str, dict[str, Any]], wants: dict[str, list[dict[str, Any]]],
                   address: str) -> list[str]:
    """An element's role line and its wants, each want the sentence the project tool gives (`want_sentence`)."""
    fields = elements.get(address) or {}
    details = [f'{label}: {value}.' for key, label in (('role', 'Role'), ('technical_name', 'Technical name'),
                                                       ('status', 'Status')) if (value := _text(fields, key))]
    out = [' '.join(details)] if details else []
    name = _display_name(elements, address)
    lines = [f"- `{address}` ({name}) requires `{want['element']}` ({_display_name(elements, want['element'])}) in "
             f"order to {_fragment(str(want.get('why') or ''))}, which {_fragment(str(want.get('how') or ''))}."
             for want in wants.get(address, [])]
    if lines:
        out.append('\n'.join(lines))
    return out


def _skeleton(fields: dict[str, Any]) -> bool:
    return all(_text(fields, key) for key in ('technical_name', 'name', 'role'))


def _order(address: str) -> tuple[int, list[str]]:
    steps = address.split('.')
    root = steps[1] if len(steps) > 1 else ''
    return (ROOT_ORDER.index(root) + 1 if root in ROOT_ORDER else len(ROOT_ORDER) + 1, steps)


def document_addresses(elements: dict[str, dict[str, Any]], held: dict[str, list[Block]]) -> list[str]:
    """The elements the document holds, in tree order: every skeleton element, and any other still holding blocks."""
    return sorted((address for address, fields in elements.items() if _skeleton(fields) or held.get(address)),
                  key=_order)


def _paragraphs(found: list[Block], base: int) -> list[str]:
    """Blocks as document paragraphs, each heading `base` plus its level in hashes."""
    parts: list[str] = []
    for block in found:
        if block.level is not None and block.title is not None:
            parts.append(f"{'#' * (base + block.level)} {f'`{block.code}` ' if block.code else ''}{block.title}")
        if block.text:
            parts.append(block.text)
    return parts


def render(project: str, elements: dict[str, dict[str, Any]], wants: dict[str, list[dict[str, Any]]],
           held: dict[str, list[Block]]) -> str:
    """The map's specification as one Markdown document: the project's heading and the root's blocks, its own
    description, then each element's heading, its skeleton facts and its blocks. Addresses are full, with the
    project's name, as the project tool writes them; the root's is the project's name."""
    parts = [f"{'#' * PROJECT_HASHES} {project}", *_paragraphs(held.get(project, []), PROJECT_HASHES)]
    for address in document_addresses(elements, held):
        parts.append(element_heading(elements, address))
        parts.extend(skeleton_facts(elements, wants, address))
        parts.extend(_paragraphs(held.get(address, []), ELEMENT_HASHES))
    return '\n\n'.join(parts) + '\n'


def parse(document: str, project: str, elements: dict[str, dict[str, Any]],
          wants: dict[str, list[dict[str, Any]]], held: dict[str, list[Block]]) -> dict[str, list[Block]]:
    """A document made by `render`, edited, read back as blocks by address: every section it holds, an empty list
    for one with no blocks, and the root's blocks, the text before the first element heading, under the project's
    name when it holds or held any. The map supplies the skeleton: an element heading must name an element exactly as
    `render` writes it, followed by its facts as the map holds them, or the document is stale and refused."""
    lines = document.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    title = f"{'#' * PROJECT_HASHES} {project}"
    first = next((index for index, line in enumerate(lines) if line.strip()), None)
    if first is None or lines[first] != title:
        raise ParseError((first or 0) + 1, f"the document must start with the project heading '{title}'")
    sections: list[tuple[str, int, list[tuple[int, str]]]] = []
    root_body: list[tuple[int, str]] = []
    fence: tuple[str, int] | None = None
    fence_line = 0
    for index in range(first + 1, len(lines)):
        line, at = lines[index], index + 1
        if fence is not None:
            if _closes_fence(line, *fence):
                fence = None
        elif (opened := _opens_fence(line)) is not None:
            fence, fence_line = opened, at
        elif atx_level(line) == ELEMENT_HASHES and (address := _heading_address(_atx_text(line))) is not None:
            if address not in elements:
                raise ParseError(at, f"'{address}' is not an element of the map; add it through intake first")
            if any(section[0] == address for section in sections):
                raise ParseError(at, f"'{address}' has more than one section; keep one")
            expected = element_heading(elements, address)
            if line != expected:
                raise ParseError(at, f"the heading for '{address}' must read '{expected}'; names change through "
                                     'intake, not through the prose')
            sections.append((address, at, []))
            continue
        (sections[-1][2] if sections else root_body).append((at, line))
    if fence is not None:
        raise ParseError(fence_line, 'a code fence opens here and is not closed')
    named = {section[0] for section in sections}
    missing = next((address for address in document_addresses(elements, held)
                    if address not in named and held.get(address)), None)
    if missing is not None:
        raise ParseError(len(lines), f"'{missing}' holds specification text, but the document has no section for it. "
                                     f"To remove the text, keep the heading '{element_heading(elements, missing)}' "
                                     'and delete the text under it.')
    out: dict[str, list[Block]] = {}
    codes: dict[str, tuple[str, int]] = {}
    for address, heading_line, body in [(project, first + 1, root_body), *sections]:
        root = address == project
        rest = body if root else _strip_facts(elements, wants, address, heading_line, body)
        found, starts = _read_blocks(address, heading_line, rest, PROJECT_HASHES if root else ELEMENT_HASHES)
        for block, at in zip(found, starts, strict=True):
            if block.code is None:
                continue
            if block.code.lower() in codes:
                first_address, first_line = codes[block.code.lower()]
                raise ParseError(at, f"code '{block.code}' is already used at line {first_line}, under "
                                     f"'{first_address}'; each code must be unique across the specification")
            codes[block.code.lower()] = (address, at)
        if root and not found and not held.get(project):
            continue
        out[address] = found
    return out


def _heading_address(text: str) -> str | None:
    if not text.endswith('`)') or '(`' not in text:
        return None
    address = text[:-2][text[:-2].rfind('(`') + 2:]
    return address if address and '`' not in address else None


def _strip_facts(elements: dict[str, dict[str, Any]], wants: dict[str, list[dict[str, Any]]], address: str,
                 heading_line: int, body: list[tuple[int, str]]) -> list[tuple[int, str]]:
    expected = [line for paragraph in skeleton_facts(elements, wants, address) for line in paragraph.split('\n')]
    rest = [(at, line) for at, line in body if line.strip()]
    consumed = heading_line
    for index, fact in enumerate(expected):
        if index >= len(rest):
            raise ParseError(consumed, f"'{address}' is missing the skeleton fact '{fact}'")
        at, line = rest[index]
        if line != fact:
            raise ParseError(at, f"'{address}' must show its skeleton facts as the map holds them: expected '{fact}', "
                                 f"found '{line}'. The skeleton changes through intake, not through the prose")
        consumed = at
    return [(at, line) for at, line in body if at > consumed]


def _read_blocks(address: str, heading_line: int, body: list[tuple[int, str]],
                 base: int) -> tuple[list[Block], list[int]]:
    """A section's body as blocks, each heading `base` plus its level in hashes: the root's under the project's
    heading, an element's under its own."""
    found: list[dict[str, Any]] = []
    starts: list[int] = []
    open_: dict[str, Any] | None = None
    fence: tuple[str, int] | None = None

    def close() -> None:
        if open_ is None:
            return
        text = '\n'.join(open_['text']).strip()
        if open_['level'] is not None or text:
            found.append({key: value for key, value in (('level', open_['level']), ('title', open_['title']),
                                                        ('text', text or None), ('code', open_['code']))
                          if value is not None})
            starts.append(open_['line'])
    for at, line in body:
        heading = atx_level(line) if fence is None else None
        if fence is not None:
            if _closes_fence(line, *fence):
                fence = None
        elif (opened := _opens_fence(line)) is not None:
            fence = opened
        if heading is not None and base < heading <= base + MAX_LEVEL:
            close()
            code, title = _split_code(_atx_text(line))
            open_ = {'line': at, 'level': heading - base, 'code': code, 'title': title, 'text': []}
        elif heading is not None:
            allowed = f"{'#' * (base + 1)} to {'#' * (base + MAX_LEVEL)}"
            element_form = ('; an element heading ends with its address, such as (`code.api`)'
                            if heading == ELEMENT_HASHES else '')
            raise ParseError(at, f"a heading under '{address}' must use {allowed}{element_form}")
        elif open_ is not None:
            open_['text'].append(line)
        else:
            open_ = {'line': at, 'level': None, 'code': None, 'title': None, 'text': [line]}
    close()
    try:
        return blocks(address, found), starts
    except Refusal as refusal:
        raise ParseError(body[0][0] if body else heading_line, refusal.message) from None
