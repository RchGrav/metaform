"""MCP tools belong to their declaring module; discovery never assigns synthetic categories.

The module directory publishes each active module's own summary. Sessions expose only the module they open.
Stateless clients use the catalog's direct-call path rather than receiving every module's schemas at startup.
Discovery follows the enabled module surface without organizational role policy.
"""
from __future__ import annotations

import os
import re
from collections.abc import Iterable
from difflib import SequenceMatcher
from typing import Any

from metaform.module import Module, Verb

CATALOG = 'metaform_catalog'
OPEN_KEY = 'catalog:module'

def task() -> str | None:
    """The name of the task the agent this server serves runs, `user_agent`, `composer`, `intake` and the rest, from
    METAFORM_TASK_NAME, which dispatch's runner sets on a task session's MCP server; None for a session no task names:
    the person's own, or one a runner started on a ticket, a talk or a brief, whose first turn is its instructions."""
    return os.environ.get('METAFORM_TASK_NAME') or None


def dispatched() -> bool:
    """Whether a runner started the agent this server serves: METAFORM_SESSION names its runner. False for the
    person's own sessions."""
    return bool(os.environ.get('METAFORM_SESSION'))


FOR_PERSON = ('user_agent',)


def for_person() -> bool:
    """Whether the agent this server serves acts for the person: the person's own sessions and the tasks FOR_PERSON
    names, the person's own agent."""
    return not dispatched() or task() in FOR_PERSON


def grouped(names: Iterable[str], declared: dict[str, tuple[Module, Verb]]) -> dict[str, list[str]]:
    """Each tool occurs once, under its declared owner; chassis commands belong to metaform."""
    found: dict[str, list[str]] = {}
    for name in names:
        declaration = declared.get(name)
        owner = declaration[0].id if declaration is not None else 'metaform'
        found.setdefault(owner, []).append(name)
    return {owner: sorted(found[owner]) for owner in sorted(found)}


def signature(schema: dict[str, Any]) -> str:
    """A tool's arguments as an agent plans a call from them: each name, required ones bare and the rest with `?`."""
    properties: dict[str, Any] = schema.get('properties') or {}
    required: set[str] = {str(one) for one in schema.get('required') or ()}
    return ', '.join(name if name in required else f'{name}?' for name in properties)


WORD = re.compile(r'[a-z0-9]+')


def words(text: str) -> set[str]:
    return set(WORD.findall(text.lower()))


def ranked(query: str, described: dict[str, str], homes: dict[str, str],
           purposes: dict[str, str] | None = None) -> list[str]:
    """Find commands by their own descriptions and their declaring module's published purpose."""
    asked = words(query)
    if not asked:
        return []
    scored: list[tuple[float, str]] = []
    for name, said in described.items():
        owner = homes.get(name, '')
        held = words(f'{name.replace("_", " ")} {said} {owner} {(purposes or {}).get(owner, "")}')
        score = 0.0
        for word in asked:
            if word in held:
                score += 4.0 + (2.0 if word in words(name) else 0.0)
            elif any(one.startswith(word) for one in held):
                score += 3.0
            elif len(word) >= 4:
                # Short tokens are too ambiguous to correct. Compare similarly sized words only.
                nearby = (one for one in held if abs(len(one) - len(word)) <= 2)
                similarity = max((SequenceMatcher(None, word, one).ratio() for one in nearby), default=0.0)
                if similarity >= 0.75:
                    score += similarity
        if score:
            scored.append((-score, name))
    return [name for _, name in sorted(scored)]
