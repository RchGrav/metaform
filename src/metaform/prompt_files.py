"""Prompts authored in XML, MCP-031.

Each prompt is an element of a `resources/prompts.xml` file, the chassis's or its
module's, named for the prompt. What is between the element's tags is the prompt.
An empty element inside it marks a place the code fills with what it supplies
under that element's name. No prompt's words are written in Python.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from importlib import resources
from importlib.resources.abc import Traversable

FILE = 'prompts.xml'


def text(folder: Traversable, name: str, **fills: str) -> str | None:
    """The prompt `name` in the `resources/prompts.xml` of this package folder, or None when there is none."""
    path = folder / 'resources' / FILE
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


def commands(folder: Traversable) -> list[tuple[str, dict[str, str], str, str, bool]]:
    """The slash commands this package folder declares, MCP-032: each child of `<commands>` in its prompts.xml, by
    name, with its attributes, the verb it runs among them, its text before and after an empty `<result/>`, and
    whether it holds one."""
    path = folder / 'resources' / FILE
    if not path.is_file():
        return []
    found = ET.fromstring(path.read_text(encoding='utf-8')).find('commands')
    held: list[tuple[str, dict[str, str], str, str, bool]] = []
    for element in found if found is not None else []:
        mark = element.find('result')
        before = element.text or ''
        after = (mark.tail or '') if mark is not None else ''
        held.append((element.tag, dict(element.attrib), before, after, mark is not None))
    return held
