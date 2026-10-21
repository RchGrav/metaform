"""Every word the roundtable sends, from `resources/prompts.xml`: one element per prompt, sent exactly as written; an
empty element inside a prompt marks a place the code fills in; comments are never sent."""
from __future__ import annotations

import functools
from importlib import resources
from typing import Any
from xml.etree import ElementTree


@functools.cache
def tree() -> ElementTree.Element:
    held = resources.files(__package__ or 'roundtable') / 'resources' / 'prompts.xml'
    return ElementTree.fromstring(held.read_bytes())


def said(name: str, **fills: Any) -> str:
    """The prompt `name` with its places filled; KeyError naming a place left unfilled."""
    found = tree().find(name)
    if found is None:
        raise KeyError(f'No prompt {name} in prompts.xml.')
    parts = [found.text or '']
    for place in found:
        if place.tag not in fills:
            raise KeyError(f'The prompt {name} has a place {place.tag} that was not filled.')
        parts += [str(fills[place.tag]), place.tail or '']
    return ''.join(parts)
