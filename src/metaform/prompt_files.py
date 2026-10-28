"""Prompts authored in XML, MCP-031.

Each prompt is an element of a `resources/prompts.xml` file, the chassis's or its
module's, named for the prompt. What is between the element's tags is the prompt.
An empty element inside it marks a place the code fills with what it supplies
under that element's name. No prompt's words are written in Python.

A prompt `served` goes through the home's prompt store, STORE-044, under the
name `prompt.<owner>:<element>`, the owner a module's id or `chassis`: the text a
module ships becomes a version when it changes, and an edit saved in the store
is what is sent in its place. Each prompt served is added to the list `collect`
started in that context, so a runner knows which versions each turn carried.

A prompt is written as plain text, the way the agent reads it: every surface that edits one takes and shows it so,
with its fill places written `<name/>`, and `save_edit`, the one gate for every edit, encodes it for the file's form
before it is stored. A prompts.xml that does not read whole, as a bare `<` written by hand leaves it, still serves
every prompt it holds that reads, a broken one from the prompt store's last shipped version, and `problems` names the
file, the line and the prompt; a bare `&` is read as the character it is.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import cache
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import TYPE_CHECKING, Any
from xml.sax.saxutils import escape

if TYPE_CHECKING:
    from .data.prompts import PromptVersion

FILE = 'prompts.xml'
TRIAL = 'METAFORM_PROMPTS'  # a prompts.xml whose non-empty prompts are read before a package's own: prompts on trial, tests


@dataclass(frozen=True)
class Sent:
    """One prompt served: its store name, `prompt.<owner>:<element>` or `prompt.<owner>:<file>`, and the version sent, its number
    and id in the prompt store and whether it was the module's shipped text or an edit; a prompt on trial, read from
    the METAFORM_PROMPTS file, has no number and origin `trial`."""
    name: str
    number: int | None
    origin: str
    version_id: str | None
    selected_version_id: str | None = None
    rendered_fingerprint: str = ''
    bindings: dict[str, str] = field(default_factory=dict[str, str])
    problems: tuple[str, ...] = ()
    rendered_text: str = ''
    source: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass(frozen=True)
class Parsed:
    """A prompts.xml as read: its root, holding every element that reads; the elements that do not, by name, each with
    why, naming the file and the line; and why the elements after an unclosed one were not read at all, if so."""
    root: ET.Element
    broken: dict[str, str]
    lost: str | None


# A & that starts no character or entity reference is the character itself, as a person writing prose means it.
_BARE_AMPERSAND = re.compile(r'&(?!(?:[A-Za-z_][\w.-]*|#[0-9]+|#x[0-9A-Fa-f]+);)')
_TOP = re.compile(r'<!--.*?-->|<([A-Za-z_][\w.-]*)(?:\s[^<>]*?)?(/?)>', re.DOTALL)
_PLAIN_REASONS = {
    'not well-formed (invalid token)': 'a < that starts no fill place must be written &lt; in the file',
    'mismatched tag': 'a <word> starts a tag that is never closed: write < as &lt; in the file, or a fill place as '
                      '<name/>',
    'unclosed token': 'a < starts a tag that is never closed: write < as &lt; in the file',
    'undefined entity': 'an &name; that is no entity: write & as &amp; in the file',
}
_READ: dict[str, tuple[tuple[int, int], Parsed]] = {}  # each file read, by path, while its size and time hold
_TOLD: set[str] = set()  # the problems this process has written to stderr


def _reason(error: ET.ParseError) -> str:
    said = str(error).rsplit(': line ', 1)[0]
    return _PLAIN_REASONS.get(said, said)


def _offset(text: str, start: int, row: int, column: int) -> int:
    """The place in `text` of the parser's line and column, counted in the part of it that begins at `start`."""
    at = start
    for _ in range(row - 1):
        at = text.find('\n', at) + 1
    return at + column


def _unclosed(text: str, start: int, end: int) -> tuple[int, str] | None:
    """The first `<word>` between start and end that no `</word>` after it closes, with where it is: the < a person
    meant as text, which the parser reports only where the prompt's own closing tag no longer matches."""
    for found in _TOP.finditer(text, start, end):
        if found.group(1) is not None and not found.group(2) and f'</{found.group(1)}>' not in text[found.end():end]:
            return found.start(), found.group(0)
    return None


def _parse(where: str, raw: str) -> Parsed:
    """A prompts file's text, read element by element when it does not read whole, so one prompt written wrong leaves
    every other one served; each element that does not read is named with the file, its line and column, and why."""
    written = _BARE_AMPERSAND.sub('&amp;', raw)
    try:
        return Parsed(ET.fromstring(written), {}, None)
    except ET.ParseError as error:
        whole = error
    root = ET.Element('prompts')
    broken: dict[str, str] = {}
    lost: str | None = None
    opened = written.find('<prompts')
    at = written.find('>', opened) + 1 if opened >= 0 else 0
    while (found := _TOP.search(written, at)) is not None:
        tag = found.group(1)
        if tag is None:  # a comment between prompts
            at = found.end()
            continue
        line = written.count('\n', 0, found.start()) + 1
        if found.group(2):
            end = found.end()
        else:
            close = written.find(f'</{tag}>', found.end())
            if close < 0:
                lost = (f'{where}: line {line}, in <{tag}>: <{tag}> is never closed with </{tag}>, so it and the '
                        "prompts after it are served from the prompt store's last shipped versions")
                broken[tag] = lost
                break
            end = close + len(tag) + 3
        try:
            root.append(ET.fromstring(written[found.start():end]))
        except ET.ParseError as error:
            reason = _reason(error)
            opened_at = _unclosed(written, found.end(), end - len(tag) - 3)
            if opened_at is not None:  # the tag left open, not the closing tag the parser stopped at
                start, token = opened_at
                reason = f'{token} starts a tag that is never closed: write < as &lt; in the file, or a fill place ' \
                         'as <name/>'
            else:
                row, column = getattr(error, 'position', (1, 0))
                start = _offset(written, found.start(), row, column)
            row_at = written.count('\n', 0, start) + 1
            column_at = start - (written.rfind('\n', 0, start) + 1) + 1
            broken[tag] = (f'{where}: line {row_at}, column {column_at}, in <{tag}>: {reason}; its last shipped '
                           'version is served until it is corrected')
        at = end
    if not broken and lost is None:
        row, column = getattr(whole, 'position', (1, 0))
        lost = f'{where}: line {row}, column {column + 1}: {_reason(whole)}'
    return Parsed(root, broken, lost)


def _parsed(path: Traversable) -> Parsed | None:
    """A prompts file as read, or None when there is none; read again only when the file has changed."""
    if not path.is_file():
        return None
    if isinstance(path, Path):
        try:
            stat = path.stat()
        except OSError:
            return None
        key, mark = str(path), (stat.st_mtime_ns, stat.st_size)
        held = _READ.get(key)
        if held is not None and held[0] == mark:
            return held[1]
        parsed = _parse(key, path.read_text(encoding='utf-8'))
        _READ[key] = (mark, parsed)
        return parsed
    return _parse(str(path), path.read_text(encoding='utf-8'))


def problems(folder: Traversable) -> list[str]:
    """What keeps prompts of this package folder's prompts.xml from reading, each naming the file, the line and the
    prompt; none when it reads whole."""
    parsed = _parsed(folder / 'resources' / FILE)
    if parsed is None:
        return []
    said = list(parsed.broken.values())
    return said + [parsed.lost] if parsed.lost and parsed.lost not in said else said


def module_problems(identifier: str) -> list[str]:
    """`problems` of the loaded module `identifier`, `chassis` or `skills`."""
    folder = _folder(identifier)
    return [] if folder is None else problems(folder)


def problem_of(identifier: str, name: str) -> str | None:
    """Why the prompt `name` of `identifier` does not read from its file, or None when it does."""
    folder = _folder(identifier)
    parsed = None if folder is None else _parsed(folder / 'resources' / FILE)
    if parsed is None:
        return None
    return parsed.broken.get(name) or (parsed.lost if parsed.lost and parsed.root.find(name) is None else None)


_EDITS: list[tuple[tuple[str, tuple[int, int] | None, tuple[int, int] | None], dict[str, str]]] = []  # the store's edits, while it holds


def _mark(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size


def _edits() -> dict[str, str]:
    """The prompt store's edits by name, read again only when its file or its write-ahead log has changed, so a prompt
    read from a file costs a stat while nobody saves an edit; none while there is no store."""
    from .data import prompts
    path = prompts.store_path()
    mark = (str(path), _mark(path), _mark(path.with_name(path.name + '-wal')))
    if mark[1] is None:
        return {}
    if _EDITS and _EDITS[0][0] == mark:
        return _EDITS[0][1]
    try:
        found = prompts.edits()
    except Exception:  # noqa: BLE001  a store this code cannot read sends the files' text
        found = {}
    for name in found:
        try:
            merged = merge_selected_updates(name)
            if merged is not None and merged['state'] == 'applied':
                found[name] = prompts.prompt_version(name).text
        except Exception as error:  # noqa: BLE001  a migration fault cannot discard the person's selected edit
            notice = f'{name}: its selected update could not be merged ({error}); the selected edit is retained.'
            if notice not in _TOLD:
                _TOLD.add(notice)
                sys.stderr.write(notice + '\n')
    _EDITS[:] = [(mark, found)]
    return found


@cache
def prompt_updates() -> dict[str, dict[str, Any]]:
    """The shipped exact-anchor migrations keyed by existing component identity, including selected skill files."""
    manifest = json.loads((resources.files('metaform') / 'resources' / 'prompt_updates.json').read_text('utf-8'))
    return {one['name']: {'baseline': manifest['baseline'],
                         'reviewed_baseline': manifest['reviewed_baseline'], **one} for one in manifest['updates']}


_MERGED: dict[tuple[str, str], dict[str, Any]] = {}


def merge_selected_updates(name: str, *, retry: bool = False) -> dict[str, Any] | None:
    """Merge the requested shipped change into a selected edit using its actual source/version, once.

    An exact, unique old anchor is replaced; an exact new anchor is already integrated. Missing or ambiguous
    anchors keep the entire selected edit intact and report the mismatch. Later user edits are never auto-replaced.
    """
    update = prompt_updates().get(name)
    if update is None:
        return None
    from .data import prompts
    key = str(prompts.store_path()), update['id']
    if not retry and key in _MERGED:
        return _MERGED[key]

    def transform(version: PromptVersion) -> tuple[str, list[str]]:
        # Older prompt review saved whole skill files with format=xml, though their consumers read them literally.
        # Follow that actual source contract instead of parsing legacy library sections as XML.
        xml = version.format == 'xml' and not name.startswith('prompt.skill.') and not update.get('source_component')
        if xml:
            try:
                rendered(version.text)
            except ValueError as error:
                return version.text, [f'{name} version {version.number}: {error}; the selected edit is retained.']
        source = plain(version.text) if xml else version.text
        text = source
        conflicts: list[str] = []
        for number, edit in enumerate(update['edits'], 1):
            old, new = str(edit['old']), str(edit['new'])
            before, after = text.count(old), text.count(new)
            if before == 1 and after == 0:
                text = text.replace(old, new, 1)
            elif before == 0 and after == 1:
                continue
            else:
                conflicts.append(f'{name} version {version.number}: update anchor {number} '
                                 f'has {before} old and {after} new matches; the selected edit is retained.')
        if conflicts:
            return version.text, conflicts
        declared = (set(places(version.text)) | set(places(_source(name) or ''))
                    | {place for edit in update['edits'] for place in _PLACE.findall(str(edit['new']))})
        stored = encode(text, declared) if xml else text
        return stored, []

    merged = prompts.merge_selected(name, str(update['id']), transform,
        source={key: update[key] for key in ('source', 'baseline', 'reviewed_baseline')}, retry=retry)
    _MERGED[key] = merged
    return merged


def _selected_update(version: PromptVersion) -> tuple[PromptVersion, list[str]]:
    from .data import prompts
    merged = merge_selected_updates(version.name)
    if merged is None:
        return version, []
    if merged['after_number'] > version.number:
        version = prompts.prompt_version(version.name)
    notices: list[str] = merged['conflicts'] if merged['state'] == 'conflict' and merged['before_version_id'] == version.version_id else []
    return version, notices


def _last_shipped(key: str, name: str) -> ET.Element | None:
    """The prompt store's last shipped version of a prompt whose element does not read, as an element."""
    from .data import prompts
    try:
        versions = prompts.prompt_versions(key)
    except Exception:  # noqa: BLE001  no store, or no version of it: nothing to serve in its place
        return None
    last = next((one.text for one in versions if one.origin == 'shipped'), None)
    if last is None:
        return None
    try:
        return ET.fromstring(f'<{name}>{last}</{name}>')
    except ET.ParseError:
        return None


_SENT: ContextVar[list[Sent] | None] = ContextVar('metaform_prompts_sent', default=None)
# the list the process last started, for a prompt served in a context `collect` never reached: a callback another
# thread scheduled on the loop, such as a runner's handler of a change made elsewhere
_LAST: list[list[Sent]] = []


def text(folder: Traversable, name: str, **fills: str) -> str | None:
    """The prompt `name` in the `resources/prompts.xml` of this package folder, or None when there is none; a prompt
    on trial under the same name, in the file `METAFORM_PROMPTS` names, is read first, and an edit saved in the prompt
    store under `prompt.<owner>:<name>` is sent in place of the file's text, so an edit of any prompt reaches its agents."""
    trial = os.environ.get(TRIAL)
    found = None
    if trial and os.path.isfile(trial):
        tried = _parsed(Path(trial))
        found = None if tried is None else tried.root.find(name)
        if found is not None and not (found.text or '').strip() and not len(found):
            found = None
    if found is None:
        found = _element(folder, name)
        edit = None if found is None else _edits().get(address(owner(folder), name))
        if edit is not None:  # an edit saved in the store is sent in place of the file's text, STORE-044
            try:
                return rendered(edit, **fills)
            except ValueError:
                pass  # saved before edits were checked; `agents role` names it, and the file's text is sent
    if found is None:
        return None
    return ((found.text or '') + ''.join(fills.get(child.tag, '') + (child.tail or '') for child in found)).strip()


def required(folder: Traversable, name: str, **fills: str) -> str:
    """The prompt `name` of a package whose prompt file ships with it, so a missing prompt is a defect."""
    got = text(folder, name, **fills)
    if got is None:
        parsed = _parsed(folder / 'resources' / FILE)
        why = None if parsed is None else parsed.broken.get(name) or parsed.lost
        raise LookupError(why or f'{folder / "resources" / FILE} has no prompt {name}.')
    return got


def chassis(name: str, **fills: str) -> str:
    """The chassis's prompt `name`."""
    return required(resources.files('metaform'), name, **fills)


def module(identifier: str, name: str, **fills: str) -> str | None:
    """The prompt `name` of the loaded module `identifier`, or None when it has none."""
    from . import loader
    found = loader.get(identifier)
    return None if found is None else text(found.path, name, **fills)


def address(identifier: str, name: str) -> str:
    """A module prompt or skill procedure's canonical store address, CTX-082."""
    return f'prompt.skill.{name}' if identifier == 'skill' else f'prompt.{identifier}:{name}'


def split_address(name: str) -> tuple[str, str]:
    """Read a canonical prompt address without accepting retired module names."""
    if name.startswith('prompt.skill.'):
        return 'skill', name[len('prompt.skill.'):]
    if not name.startswith('prompt.'):
        return '', ''
    identifier, separator, element = name[len('prompt.'):].partition(':')
    return (identifier, element) if separator else ('', '')


def owner(folder: Traversable) -> str:
    """Who ships the prompts of this package folder, as the prompt store and `metaform prompts review` name them: the
    module's id, its folder's name, or `chassis` for Metaform's own."""
    return 'chassis' if folder.name == 'metaform' else folder.name


def _element(folder: Traversable, name: str) -> ET.Element | None:
    """The element `name` of this package folder's prompts.xml; for one that does not read, the prompt store's last
    shipped version of it, so a prompt written wrong in the file is still sent as it last read."""
    parsed = _parsed(folder / 'resources' / FILE)
    if parsed is None:
        return None
    found = parsed.root.find(name)
    if found is None and (name in parsed.broken or parsed.lost):
        why = parsed.broken.get(name) or parsed.lost
        if why is not None and why not in _TOLD:
            _TOLD.add(why)
            sys.stderr.write(f'{why}.\n')
        found = _last_shipped(address(owner(folder), name), name)
    return found


def _folder(identifier: str) -> Traversable | None:
    if identifier == 'chassis':
        return resources.files('metaform')
    if identifier == 'skills':
        return resources.files('metaform') / 'skills'
    from . import loader
    found = loader.get(identifier)
    return None if found is None else found.path


def body(found: ET.Element) -> str:
    """An element's prompt as written, its fill places kept as empty elements: the text a version holds."""
    return (escape(found.text or '') + ''.join(ET.tostring(child, encoding='unicode') for child in found)).strip()


def rendered(text: str, /, **fills: str) -> str:
    """A version's text with its fill places filled, as `text` fills an element; ValueError when it is not well
    formed, as an edit saved by hand may be."""
    try:
        found = ET.fromstring(f'<prompt>{text}</prompt>')
    except ET.ParseError as error:
        raise ValueError(f'not well-formed XML: {error}') from None
    return ((found.text or '') + ''.join(fills.get(child.tag, '') + (child.tail or '') for child in found)).strip()


_PLACE = re.compile(r'<([A-Za-z_][\w.-]*)\s*/>')
_TAG_LIKE = re.compile(r'</?([A-Za-z_][\w.-]*)\s*/?>')


def places(stored: str) -> list[str]:
    """The fill places of a version's text, each once, in the order written; none when it does not read."""
    try:
        found = ET.fromstring(f'<prompt>{stored}</prompt>')
    except ET.ParseError:
        return []
    return list(dict.fromkeys(child.tag for child in found))


def _structured(stored: str) -> bool:
    try:
        found = ET.fromstring(f'<prompt>{stored}</prompt>')
    except ET.ParseError:
        return False
    return any(len(child) or child.text or child.attrib for child in found)


def plain(stored: str) -> str:
    """A version's text as the person reads and writes it: the characters the agent is sent, each fill place written
    `<name />`. A text that does not read, as a version saved before edits were checked may not, and a structured one
    whose elements hold text, are given as stored."""
    try:
        found = ET.fromstring(f'<prompt>{stored}</prompt>')
    except ET.ParseError:
        return stored
    if _structured(stored):
        return stored
    return (found.text or '') + ''.join(f'<{child.tag} />' + (child.tail or '') for child in found)


def encode(text: str, declared: list[str] | set[str]) -> str:
    """Plain text in the form a version holds: every &, < and > is the character itself, except `<name/>` or
    `<name />` for a fill place the prompt declares, which stays its fill place. The inverse of `plain`."""
    kept = set(declared)
    out: list[str] = []
    at = 0
    for found in _PLACE.finditer(text):
        if found.group(1) in kept:
            out.append(escape(text[at:found.start()]))
            out.append(f'<{found.group(1)} />')
            at = found.end()
    out.append(escape(text[at:]))
    return ''.join(out)


def checked(name: str, text: str, shipped_text: str) -> tuple[str, list[str]]:
    """An edit of the prompt `name`, written as plain text, in the form its version holds, with what the person should
    know of it: a fill place the module ships that the edit leaves out, and a word written like a fill place that is
    none, sent as written. It always reads, so what is saved is what is sent. A prompt whose elements hold text of
    their own, such as a schema's fields, is structured XML rather than prose: its edit is kept as written, and
    ValueError says why when it does not read, so it is never saved to go unsent."""
    if _structured(shipped_text):
        try:
            rendered(text.strip())
        except ValueError as error:
            raise ValueError(f'{name} is structured XML, written as its file holds it, and the edit is {error}; write '
                             '& as &amp; and < as &lt; in its text') from None
        return text.strip(), []
    declared = places(shipped_text)
    stored = encode(text.strip(), declared)
    rendered(stored)  # encoded, it always reads; a ValueError here is a defect of encode
    used = set(places(stored))
    notices: list[str] = []
    lost = [one for one in declared if one not in used]
    if lost:
        notices.append(f"The edit leaves out the fill place(s) {', '.join(f'<{one}/>' for one in lost)}, which the "
                       'module fills; what it fills there is no longer sent.')
    literal: list[str] = []
    for found in _TAG_LIKE.finditer(text):  # a word written like a fill place: `<word/>`, or one of its names
        token, word = found.group(0), found.group(1)
        if word in declared and _PLACE.fullmatch(token):
            continue
        if (word in declared or token.endswith('/>')) and token not in literal:
            literal.append(token)
    if literal:
        some = ', '.join(f'<{one}/>' for one in declared)
        notices.append(f"{', '.join(literal)} {'is' if len(literal) == 1 else 'are'} sent as written, for no fill "
                       f'place of {name} is written so' + (f'; its fill places are {some}.' if some else
                                                          '; it has none.'))
    return stored, notices


def save_edit(name: str, text: str, *, parent: int | None = None, format: str = 'text',
              shipped_text: str | None = None) -> tuple[PromptVersion, list[str]]:
    """Save an edit of the prompt `name` as its next version, the one gate every surface saves through: for a prompt a
    module ships in its prompts.xml, `prompt.<owner>:<element>`, the plain text is encoded for that form, so it is always
    sent as written, and the shipped text is registered first, so the edit has it as its parent, STORE-044. Any
    other prompt is stored as given. Returns the version, with the store's own notices, and the gate's notices for
    the person, as sentences.
    `shipped_text` is the element's text as a version holds it, for a prompt whose module is not loaded here."""
    from .data import prompts
    source = shipped_text if shipped_text is not None else _source(name)
    if source is None:
        update = prompt_updates().get(name)
        if update is not None:
            source_component = update.get('source_component')
            if source_component:
                selected_source = _source(str(source_component))
                if selected_source is not None:
                    _selected_update(prompts.shipped(name, 'text', rendered(selected_source)))
            elif name.startswith('prompt.skill.'):
                file = resources.files('metaform').joinpath(*str(update['source']).split('/')[2:])
                if file.is_file():
                    _selected_update(prompts.shipped(name, format, file.read_text('utf-8').strip()))
        return prompts.save_prompt(name, text, format=format, parent=parent), []
    stored, notices = checked(name, text, source)
    # Consume requested source migrations before this explicit edit, so its newer instructions remain selected.
    _selected_update(prompts.shipped(name, 'xml', source))
    return prompts.save_prompt(name, stored, format='xml', parent=parent), notices


def newest_id(name: str) -> str:
    """The id of the newest version the prompt store holds of `name`; StoreError when it holds none."""
    from .data import prompts
    return prompts.prompt_version(name).version_id


def _source(name: str) -> str | None:
    """The text a module ships for `prompt.<owner>:<element>` as a version holds it, the form `save_edit` encodes an edit
    for; None for any other name, or one whose module is not loaded here."""
    owner_, element = split_address(name)
    if not (owner_ and element) or owner_ == 'skill' or '.' in element:
        return None
    try:
        return shipped(owner_, element)
    except (OSError, LookupError):
        return None


def written_plain(name: str) -> bool:
    """Whether the prompt `name` is read and written as plain text, `plain` and `encode`: one a module ships in its
    prompts.xml as prose with fill places; any other is read and saved as stored."""
    source = _source(name)
    return source is not None and not _structured(source)


def readable(version: PromptVersion) -> str:
    """A stored version's text as the person reads and edits it: `plain` for a prompt written as plain text, so that
    saving it back through `save_edit` gives the same version; any other as stored."""
    return plain(version.text) if version.format == 'xml' and written_plain(version.name) else version.text


def shipped(identifier: str, name: str) -> str | None:
    """The text the loaded module `identifier`, `chassis` or `skills` (the skill registry's) ships for its prompt
    `name` as a version holds it: an element of its prompts.xml, or a file under its resources/ for a name with a dot,
    such as intake.xml. None when the module is not loaded or ships no such prompt."""
    folder = _folder(identifier)
    if folder is None:
        return None
    if '.' in name:
        file = folder / 'resources' / name
        return file.read_text(encoding='utf-8') if file.is_file() else None
    element = _element(folder, name)
    return None if element is None else body(element)


def collect() -> list[Sent]:
    """Start a list of the prompts served from here on in this context, and in the tasks and threads it starts, and
    return it; the caller takes what is in it as it sends each turn. A prompt served where no list was started in its
    context goes to the list this process started last."""
    held: list[Sent] = []
    _SENT.set(held)
    _LAST[:] = [held]
    return held


def release(held: list[Sent]) -> None:
    """The caller is done with the list `collect` gave it: a prompt served after this in a context without a list of
    its own is added to none."""
    if _LAST and _LAST[0] is held:
        _LAST.clear()


def _noted(sent: Sent) -> None:
    held = _SENT.get()
    if held is None and _LAST:
        held = _LAST[0]
    if held is not None:
        held.append(sent)


def component(name: str, text: str, *, version_id: str | None = None,
              bindings: dict[str, str] | None = None) -> dict[str, Any]:
    """One exact rendered context component; constructing it establishes no delivery."""
    for marker, value in (bindings or {}).items():
        if marker.startswith('{') and marker.endswith('}'):
            text = text.replace(marker, value)
    return {'name': name, 'text': text, 'actual_version_id': version_id,
            'selected_version_id': version_id, 'number': None, 'origin': 'generated',
            'rendered_fingerprint': hashlib.sha256(text.encode('utf-8')).hexdigest(),
            'bindings': dict(bindings or {}), 'problems': [],
            'source': {'kind': 'generated', 'path': None, 'shipped_identity': None}}


def resolve(name: str, /, **fills: str) -> dict[str, Any]:
    """Resolve a shipped or generated prompt-store component without claiming an agent received it.

    Generated duties need no XML element. An invalid override is identified separately from the actual fallback;
    when current shipped text has no stored version yet, its content identity names that source snapshot honestly.
    """
    identifier, element = split_address(name)
    folder = _folder(identifier)
    if folder is not None and element and '.' not in element and _element(folder, element) is not None:
        return _resolved(folder, element, **fills)
    from .data import prompts
    shipped_text = shipped(identifier, element) if folder is not None and element else None
    selected = prompts.shipped(name, 'text', shipped_text) if shipped_text is not None else prompts.prompt_version(name)
    selected, notices = _selected_update(selected)
    text = rendered(selected.text, **fills) if selected.format == 'xml' else selected.text
    return {**component(name, text, version_id=selected.version_id, bindings=fills),
            'number': selected.number, 'origin': selected.origin, 'notices': notices,
            'source': {'kind': 'selected_edit' if selected.origin == 'edited' else 'shipped',
                       'path': str(folder / 'resources' / element) if folder is not None else None,
                       'shipped_identity': hashlib.sha256(shipped_text.encode()).hexdigest()
                           if shipped_text is not None else None}}


def _resolved(folder: Traversable, name: str, /, **fills: str) -> dict[str, Any]:
    key = address(owner(folder), name)
    trial = os.environ.get(TRIAL)
    if trial and os.path.isfile(trial):
        held = _parsed(Path(trial))
        tried = None if held is None else held.root.find(name)
        if tried is not None and ((tried.text or '').strip() or len(tried)):
            packaged = _parsed(folder / 'resources' / FILE)
            original = None if packaged is None else packaged.root.find(name)
            return {**component(key, rendered(body(tried), **fills), bindings=fills), 'origin': 'trial',
                    'source': {'kind': 'trial', 'path': str(Path(trial).resolve()),
                               'shipped_path': str(folder / 'resources' / FILE),
                               'shipped_identity': hashlib.sha256(body(original).encode()).hexdigest()
                                   if original is not None else None}}
    found = _element(folder, name)
    if found is None:
        raise LookupError(f'{folder / "resources" / FILE} has no prompt {name}.')
    from .data import prompts
    source = body(found)
    parsed = _parsed(folder / 'resources' / FILE)
    source_problem = None if parsed is None else parsed.broken.get(name) or (
        parsed.lost if parsed.root.find(name) is None else None)
    source_info = {'kind': 'fallback' if source_problem else 'shipped',
                   'path': str(folder / 'resources' / FILE),
                   'shipped_identity': hashlib.sha256(source.encode()).hexdigest(),
                   'source_problem': source_problem}
    from .errors import StoreError
    try:
        existing = prompts.prompt_version(key)
    except StoreError:
        existing = None
    if existing is not None and existing.format != 'xml':
        selected = prompts.shipped(key, existing.format, rendered(source))
    else:
        selected = prompts.shipped(key, 'xml', source)
    selected, notices = _selected_update(selected)
    try:
        text = rendered(selected.text, **fills) if selected.format == 'xml' else selected.text
    except ValueError as error:
        problem = f'Prompt {key} version {selected.number} is {error}; its shipped text is sent.'
        actual = next((one for one in prompts.prompt_versions(key)
                       if one.origin == 'shipped' and one.text == source), None)
        source_id = actual.version_id if actual else 'shipped:' + hashlib.sha256(source.encode()).hexdigest()
        return {**component(key, rendered(source, **fills), version_id=source_id, bindings=fills),
                'selected_version_id': selected.version_id, 'selected_number': selected.number,
                'number': actual.number if actual else None, 'origin': 'shipped', 'problems': [problem],
                'notices': notices, 'source': {**source_info, 'kind': 'fallback'}}
    return {**component(key, text, version_id=selected.version_id, bindings=fills),
            'number': selected.number, 'origin': selected.origin, 'notices': notices,
            'source': {**source_info, 'kind': 'selected_edit' if selected.origin == 'edited' else source_info['kind']}}


def served(folder: Traversable, name: str, /, **fills: str) -> str:
    """The prompt `name` of this package folder as the prompt store serves it, STORE-044: the shipped element is
    registered as a version when its text changed, and the newest version is sent, an edit saved in the store in its
    place. A prompt on trial is read first and never stored. A missing element is a defect, as for `required`. An edit
    that is not well formed is not sent: the shipped text is, and the reason goes to stderr, for `agents show` names
    it on the role."""
    resolved = resolve(address(owner(folder), name), **fills) if '.' in name else _resolved(folder, name, **fills)
    for problem in [*resolved['problems'], *resolved.get('notices', [])]:
        sys.stderr.write(str(problem) + '\n')
    _noted(Sent(resolved['name'], resolved['number'], resolved['origin'], resolved['actual_version_id'],
                resolved['selected_version_id'], resolved['rendered_fingerprint'], resolved['bindings'],
                tuple(resolved['problems']), str(resolved['text']), dict(resolved.get('source') or {})))
    return str(resolved['text'])


def resolve_text(name: str, text: str, **fills: str) -> dict[str, Any]:
    """Resolve a whole authored file's selected version without claiming it was delivered to any agent.

    Such files are read literally, including historical skill edits labeled XML by an older review surface.
    Deployment and direct serving therefore use the same text and exact selected version. Optional bindings replace
    only explicit literal markers through the shared component renderer.
    """
    from .data import prompts
    version, notices = _selected_update(prompts.shipped(name, 'text', text))
    return {**component(name, version.text, version_id=version.version_id, bindings=fills),
            'number': version.number, 'origin': version.origin, 'notices': notices,
            'source': {'kind': 'selected_edit' if version.origin == 'edited' else 'shipped', 'path': None,
                       'shipped_identity': hashlib.sha256(text.encode()).hexdigest()}}


def served_text(name: str, text: str) -> str:
    """A prompt kept whole in a file, read by the caller as `text`, as the prompt store serves it under `name`, the
    name `metaform prompts review` gives it (`prompt.intake:intake.xml`, `prompt.skill.<name>`), STORE-044: the text when it is
    the newest version, else the edit saved in its place. The caller fills it as it fills the file."""
    resolved = resolve_text(name, text)
    for notice in resolved['notices']:
        sys.stderr.write(notice + '\n')
    _noted(Sent(name, resolved['number'], resolved['origin'], resolved['actual_version_id'],
                resolved['selected_version_id'], resolved['rendered_fingerprint'], rendered_text=resolved['text'],
                source=dict(resolved.get('source') or {})))
    return str(resolved['text'])


def module_commands(identifier: str) -> list[tuple[str, dict[str, str], str, str, bool]]:
    """The slash commands of the loaded module `identifier`, as `commands` reads them, or none when it is not found."""
    from . import loader
    found = loader.get(identifier)
    return [] if found is None else commands(found.path)


def commands(folder: Traversable) -> list[tuple[str, dict[str, str], str, str, bool]]:
    """The slash commands this package folder declares, MCP-032: each child of `<commands>` in its prompts.xml, by
    name, with its attributes, the verb it runs among them, its text before and after an empty `<result/>`, and
    whether it holds one."""
    parsed = _parsed(folder / 'resources' / FILE)
    if parsed is None:
        return []
    found = parsed.root.find('commands')
    held: list[tuple[str, dict[str, str], str, str, bool]] = []
    if found is None:
        return held
    for element in found:
        mark = element.find('result')
        before = element.text or ''
        after = (mark.tail or '') if mark is not None else ''
        held.append((element.tag, dict(element.attrib), before, after, mark is not None))
    return held


def rules(folder: Traversable) -> list[tuple[str, str]]:
    """The rules this package folder declares, MCP-031: each `<rule why="...">` of `<rules>` in its prompts.xml, as its
    one sentence and its why, in the order written. A rule is kept only with its reason, so a later reader can apply it
    to a case it does not name: a rule with no sentence or no why raises ValueError naming it, and the loader refuses
    the module, as it refuses any other faulty declaration."""
    path = folder / 'resources' / FILE
    parsed = _parsed(path)
    if parsed is None:
        return []
    found = parsed.root.find('rules')
    held: list[tuple[str, str]] = []
    if found is None:
        return held
    for element in found:
        if element.tag != 'rule':
            raise ValueError(f'{path}: <rules> holds only <rule> elements, not <{element.tag}>.')
        said = ' '.join(''.join(element.itertext()).split())
        why = ' '.join(element.get('why', '').split())
        if not said:
            raise ValueError(f'{path}: a <rule> has no sentence.')
        if not why:
            raise ValueError(f'{path}: the rule "{said}" has no why; write <rule why="the reason">.')
        held.append((said, why))
    return held


def module_rules(identifier: str) -> list[tuple[str, str]]:
    """The rules of the loaded module `identifier`, as `rules` reads them, or none when it is not found."""
    from . import loader
    found = loader.get(identifier)
    return [] if found is None else rules(found.path)
