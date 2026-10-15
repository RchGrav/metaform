"""Prompts authored in XML, MCP-031.

Each prompt is an element of a `resources/prompts.xml` file, the chassis's or its
module's, named for the prompt. What is between the element's tags is the prompt.
An empty element inside it marks a place the code fills with what it supplies
under that element's name. No prompt's words are written in Python.

A prompt `served` goes through the home's prompt store, STORE-044, under the
name `<owner>:<element>`, the owner a module's id or `chassis`: the text a
module ships becomes a version when it changes, and an edit saved in the store
is what is sent in its place. Each prompt served is added to the list `collect`
started in that context, so a runner knows which versions each turn carried.
"""
from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET
from contextvars import ContextVar
from dataclasses import dataclass
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from xml.sax.saxutils import escape

FILE = 'prompts.xml'
TRIAL = 'METAFORM_PROMPTS'  # a prompts.xml whose non-empty prompts are read before a package's own: prompts on trial, tests


@dataclass(frozen=True)
class Sent:
    """One prompt served: its store name, `<owner>:<element>` or `<owner>:<file>`, and the version sent, its number
    and id in the prompt store and whether it was the module's shipped text or an edit; a prompt on trial, read from
    the METAFORM_PROMPTS file, has no number and origin `trial`."""
    name: str
    number: int | None
    origin: str
    version_id: str | None


_SENT: ContextVar[list[Sent] | None] = ContextVar('metaform_prompts_sent', default=None)
# the list the process last started, for a prompt served in a context `collect` never reached: a callback another
# thread scheduled on the loop, such as a runner's handler of a change made elsewhere
_LAST: list[list[Sent]] = []


def text(folder: Traversable, name: str, **fills: str) -> str | None:
    """The prompt `name` in the `resources/prompts.xml` of this package folder, or None when there is none; a prompt
    on trial under the same name, in the file `METAFORM_PROMPTS` names, is read first."""
    trial = os.environ.get(TRIAL)
    found = None
    if trial and os.path.isfile(trial):
        found = ET.fromstring(Path(trial).read_text(encoding='utf-8')).find(name)
        if found is not None and not (found.text or '').strip() and not len(found):
            found = None
    path = folder / 'resources' / FILE
    if found is None:
        if not path.is_file():
            return None
        found = ET.fromstring(path.read_text(encoding='utf-8')).find(name)
    if found is None:
        return None
    return ((found.text or '') + ''.join(fills.get(child.tag, '') + (child.tail or '') for child in found)).strip()


def required(folder: Traversable, name: str, **fills: str) -> str:
    """The prompt `name` of a package whose prompt file ships with it, so a missing prompt is a defect."""
    got = text(folder, name, **fills)
    if got is None:
        raise LookupError(f'{folder / "resources" / FILE} has no prompt {name}.')
    return got


def chassis(name: str, **fills: str) -> str:
    """The chassis's prompt `name`."""
    return required(resources.files('metaform'), name, **fills)


def module(identifier: str, name: str, **fills: str) -> str | None:
    """The prompt `name` of the loaded module `identifier`, or None when it has none."""
    from . import loader
    found = loader.get(identifier)
    return None if found is None else text(found.path, name, **fills)


def owner(folder: Traversable) -> str:
    """Who ships the prompts of this package folder, as the prompt store and `metaform prompts review` name them: the
    module's id, its folder's name, or `chassis` for Metaform's own."""
    return 'chassis' if folder.name == 'metaform' else folder.name


def _element(folder: Traversable, name: str) -> ET.Element | None:
    path = folder / 'resources' / FILE
    return ET.fromstring(path.read_text(encoding='utf-8')).find(name) if path.is_file() else None


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


def shipped(identifier: str, name: str) -> str | None:
    """The text the loaded module `identifier`, `chassis` or `skills` (the skill registry's) ships for its prompt
    `name` as a version holds it: an element of its prompts.xml, or a file under its resources/ for a name with a dot,
    such as intake.axiom. None when the module is not loaded or ships no such prompt."""
    if identifier == 'chassis':
        folder: Traversable = resources.files('metaform')
    elif identifier == 'skills':
        folder = resources.files('metaform') / 'skills'
    else:
        from . import loader
        found = loader.get(identifier)
        if found is None:
            return None
        folder = found.path
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


def served(folder: Traversable, name: str, /, **fills: str) -> str:
    """The prompt `name` of this package folder as the prompt store serves it, STORE-044: the shipped element is
    registered as a version when its text changed, and the newest version is sent, an edit saved in the store in its
    place. A prompt on trial is read first and never stored. A missing element is a defect, as for `required`. An edit
    that is not well formed is not sent: the shipped text is, and the reason goes to stderr, for `agents show` names
    it on the role."""
    key = f'{owner(folder)}:{name}'
    trial = os.environ.get(TRIAL)
    if trial and os.path.isfile(trial):
        tried = ET.fromstring(Path(trial).read_text(encoding='utf-8')).find(name)
        if tried is not None and ((tried.text or '').strip() or len(tried)):
            _noted(Sent(key, None, 'trial', None))
            return required(folder, name, **fills)
    found = _element(folder, name)
    if found is None:
        raise LookupError(f'{folder / "resources" / FILE} has no prompt {name}.')
    from .data import prompts
    text = body(found)
    version = prompts.shipped(key, 'xml', text)
    _noted(Sent(key, version.number, version.origin, version.version_id))
    try:
        return rendered(version.text, **fills)
    except ValueError as error:
        sys.stderr.write(f'Prompt {key} version {version.number} is {error}; its shipped text is sent.\n')
        return rendered(text, **fills)


def served_text(name: str, text: str) -> str:
    """A prompt kept whole in a file, read by the caller as `text`, as the prompt store serves it under `name`, the
    name `metaform prompts review` gives it (`intake:intake.axiom`, `skill:<name>`), STORE-044: the text when it is
    the newest version, else the edit saved in its place. The caller fills it as it fills the file."""
    from .data import prompts
    version = prompts.shipped(name, 'text', text)
    _noted(Sent(name, version.number, version.origin, version.version_id))
    return version.text


def module_commands(identifier: str) -> list[tuple[str, dict[str, str], str, str, bool]]:
    """The slash commands of the loaded module `identifier`, as `commands` reads them, or none when it is not found."""
    from . import loader
    found = loader.get(identifier)
    return [] if found is None else commands(found.path)


def commands(folder: Traversable) -> list[tuple[str, dict[str, str], str, str, bool]]:
    """The slash commands this package folder declares, MCP-032: each child of `<commands>` in its prompts.xml, by
    name, with its attributes, the verb it runs among them, its text before and after an empty `<result/>`, and
    whether it holds one."""
    path = folder / 'resources' / FILE
    if not path.is_file():
        return []
    found = ET.fromstring(path.read_text(encoding='utf-8')).find('commands')
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
    if not path.is_file():
        return []
    found = ET.fromstring(path.read_text(encoding='utf-8')).find('rules')
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
