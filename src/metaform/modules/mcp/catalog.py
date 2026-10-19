"""MCP tools belong to their declaring module; discovery never assigns synthetic categories.

The module directory publishes each active module's own summary. Sessions expose only the module they open.
Stateless clients use the catalog's direct-call path rather than receiving every module's schemas at startup.
Discovery and the user's configured authority controls remain independent.
"""
from __future__ import annotations

import os
import re
from collections.abc import Iterable
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from metaform import settings
from metaform.module import Module, Verb

CATALOG = 'metaform_catalog'
OPEN_KEY = 'catalog:module'

HELD_OPS: dict[str, tuple[str, ...]] = {'map_work': ('add', 'move', 'distribute', 'glyphs')}
HELD_ARGUMENTS: dict[str, tuple[str, ...]] = {
    'map_work': ('column', 'position', 'held', 'reviewed', 'agent', 'hold', 'glyph', 'eligible', 'after_work', 'agents',
                 'links', 'by', 'title', 'task'),
    'dispatch_handoff': ('full',)}  # the full brief, no longer sent to agents, is the person's to read

# These operations remain subject to roles_without_authority, independently of tool discovery.
RESTRICTED_STEERING_TOOLS = frozenset({
    'dispatch_start', 'dispatch_agents', 'dispatch_sessions', 'dispatch_message', 'dispatch_wait',
    'dispatch_stop', 'dispatch_talk', 'dispatch_system', 'dispatch_intake', 'dispatch_helper', 'dispatch_signals',
    'dispatch_resume', 'dispatch_interrupt', 'dispatch_cancel', 'dispatch_broadcast', 'dispatch_broadcasts',
    'dispatch_autostart', 'dispatch_stop-all', 'dispatch_propose', 'dispatch_claim', 'dispatch_claims',
    'dispatch_merges', 'dispatch_review', 'dispatch_prep', 'dispatch_fork', 'dispatch_options', 'dispatch_tune',
    'dispatch_spend', 'dispatch_registry', 'dispatch_recover', 'dispatch_reset', 'dispatch_permit',
    'dispatch_publication', 'agents_role', 'agents_sent', 'agents_override', 'agents_drop',
})


def role() -> str | None:
    """The role of the agent this server serves, from METAFORM_ROLE, which dispatch's runner sets on its agent's MCP
    server; None for the person's own sessions."""
    named = os.environ.get('METAFORM_ROLE') or ''
    return named if named and named != 'none' else None


def held(folder: Path, named: str | None) -> bool:
    """Whether the person holds the role back from steering agents and writing tickets, roles_without_authority."""
    if named is None:
        return False
    try:
        return named in (settings.value('roles_without_authority', folder) or ())
    except LookupError:
        return False


FOR_PERSON = ('system', 'sentinel')


def for_person(named: str | None = None) -> bool:
    """Whether the agent this server serves acts for the person: the person's own sessions and FOR_PERSON."""
    named = role() if named is None else named
    return named is None or named in FOR_PERSON


def held_back(folder: Path, name: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The ops and the arguments of a tool left out for the role this server serves, HELD_OPS and HELD_ARGUMENTS: both
    empty unless the person holds the role back."""
    if not held(folder, role()):
        return (), ()
    return HELD_OPS.get(name, ()), HELD_ARGUMENTS.get(name, ())


def grouped(names: Iterable[str], declared: dict[str, tuple[Module, Verb]]) -> dict[str, list[str]]:
    """Each tool occurs once, under its declared owner; chassis commands belong to metaform."""
    found: dict[str, list[str]] = {}
    for name in names:
        declaration = declared.get(name)
        owner = declaration[0].id if declaration is not None else 'metaform'
        found.setdefault(owner, []).append(name)
    return {owner: sorted(found[owner]) for owner in sorted(found)}


def in_scope(name: str, declared: dict[str, tuple[Module, Verb]], folder: Path, named: str | None = None) -> bool:
    """Preserve explicit user restrictions without using discovery groupings as authority."""
    return name not in RESTRICTED_STEERING_TOOLS or not held(folder, role() if named is None else named)


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
