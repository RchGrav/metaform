"""Consent the person gives in their AI tool: MCP elicitation, CLI-011 and MCP-006.

Two kinds of call need the person, not the agent, to say yes: a call that carries a caution, such as
metaform_clear_project, and a change to a setting only the person sets. Where the AI tool can show the person a form
and `mcp_consent` is `ask`, the server asks the person there, by the standard each wire uses: on MCP 2026-07-28 the
call answers with an `input_required` result holding the form, and the client calls again with the person's answer
(multi round-trip requests, SEP-2322); on the 2025 handshake the server sends `elicitation/create` while the call
waits. The form carries the choices and why each is asked. No person sits at a dispatched agent's client, so it is
never asked a form; what is the person's decision is asked of them on a consent card in the agent's chat on the page
instead, and the call waits for their answer (the server's `carded`, dispatch's `ask_consent`; UX review round 2,
person-consent F5). Elsewhere the call keeps the plain rule, `confirm=true` for a caution and a refusal with its next
step for a person-only setting, except for what is the person's decision (a verb declared `person_says`,
metaform_clear_project, metaform_restore_project and a save of a prompt Metaform sends its agents): that runs only on
the person's answer, and is refused otherwise with the caution, told to ask the person in chat, and given the command
the person pastes (UX review rounds 1 and 2, 2026-10-17). An agent that runs its own MCP client against this server
can answer the form itself: that is a deliberate attack the command sandbox stops, `metaform.caller`.

Sources, read 2026-10-12: the 2026-07-28 changelog and the multi round-trip request pattern,
modelcontextprotocol.io/specification/2026-07-28/basic/patterns/mrtr; elicitation, form mode and its restricted
schema, modelcontextprotocol.io/specification/2026-07-28/client/elicitation; the Python SDK 2.2's
`RequestStateBoundary`, which seals the state echoed on the retry and binds it to the call and its arguments.
"""
from __future__ import annotations

import os
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from metaform import prompt_files, settings

FORM = 'consent'  # the key of the one input request a call asks
GO = 'go'  # the form's one field for a caution
DISPATCHED = ('METAFORM_ROLE', 'METAFORM_WORK')  # set by the runner on a dispatched agent and its MCP server, BASE-052
STATE = 'consent:'  # the request state's prefix, followed by a single-use token
EXPIRES_S = 600  # how long a form's sealed state is good for: the Python SDK's request-state default


def _prompt(name: str, **fills: str) -> str:
    return prompt_files.module('mcp', name, **fills) or ''


def dispatched() -> bool:
    """Whether this server serves a dispatched agent: its runner set the agent's role and ticket on it, BASE-052.
    Such an agent asks the person through a consent card in its chat on the page, never a form."""
    return any(os.environ.get(key) for key in DISPATCHED)


def can_ask(capabilities: Any, folder: Path) -> bool:
    """Whether this call can ask the person: `mcp_consent` is ask, the client shows forms, and no dispatched agent is
    behind it. A client that declares elicitation with no mode takes forms, as the 2025-11-25 revision says."""
    if settings.value('mcp_consent', folder) != 'ask' or dispatched():
        return False
    elicitation = getattr(capabilities, 'elicitation', None)
    if elicitation is None:
        return False
    return getattr(elicitation, 'form', None) is not None or getattr(elicitation, 'url', None) is None


@dataclass
class Ask:
    """One form for the person: what it says, its restricted JSON Schema, whether it carries a caution to tick, and for
    each person-only setting it asks about, the setting."""
    message: str
    schema: dict[str, Any]
    caution: bool = False
    kinds: dict[str, settings.Setting] = field(default_factory=dict[str, settings.Setting])

    def accepted(self, action: str, content: dict[str, Any] | None) -> dict[str, Any] | None:
        """The settings the person accepted, by key and typed as each setting takes it, with the caution ticked when
        there is one; None when they declined, dismissed the form or left the caution unticked."""
        if action != 'accept' or content is None or (self.caution and content.get(GO) is not True):
            return None
        values: dict[str, Any] = {}
        for key, setting in self.kinds.items():
            given = content.get(key)
            if given is None:
                continue
            if setting.kind == 'list' and isinstance(given, str):
                given = [part.strip() for part in given.split(',') if part.strip()]
            values[key] = given
        return values


def form(tool: str, said: str | None, asked: dict[str, Any], folder: Path) -> Ask | None:
    """The form a call needs, or None when it needs none: the caution it carries, with one box to tick, and one field
    for each person-only setting it asks to change, with its choices, the agent's value filled in and the setting's
    help as the reason it is the person's."""
    if not said and not asked:
        return None
    lines: list[str] = []
    properties: dict[str, Any] = {}
    if said:
        lines.append(_prompt('consent_caution', tool=tool, caution=said) or said)
        properties[GO] = {'type': 'boolean', 'title': _prompt('consent_go') or 'Go ahead', 'description': said,
                          'default': False}
    kinds = {key: settings.SCHEMA[key] for key in asked}
    if kinds:
        lines.append(_prompt('consent_settings'))
        properties.update({key: _field(setting, asked[key], folder) for key, setting in kinds.items()})
    return Ask(' '.join(line for line in lines if line), {'type': 'object', 'properties': properties,
                                                          **({'required': [GO]} if said else {})}, bool(said), kinds)


def _field(setting: settings.Setting, asked: Any, folder: Path) -> dict[str, Any]:
    """A setting as one field of the form, in the primitive types a form takes, the agent's value filled in and the
    setting's help as the reason it is the person's."""
    now = settings.value(setting.key, folder)
    said = f'{setting.help} Now: {_shown(now)}.'.strip()
    base = {'title': setting.label or setting.key, 'description': said}
    if setting.kind == 'bool':
        return {**base, 'type': 'boolean', 'default': bool(asked)}
    if setting.kind == 'int':
        bounds = {key: value for key, value in (('minimum', setting.min), ('maximum', setting.max)) if value is not None}
        return {**base, 'type': 'integer', **bounds, **({'default': asked} if isinstance(asked, int) else {})}
    try:
        choices = setting.options(folder) if setting.choices is not None else []
    except Exception:  # noqa: BLE001  a module's failing choices function leaves the field free text
        choices = []
    if setting.kind == 'select' and choices:
        return {**base, 'type': 'string', 'enum': choices, **({'default': asked} if asked in choices else {})}
    if setting.kind == 'list' and choices:
        listed = [str(one) for one in cast(list[Any], asked)] if isinstance(asked, list) else []
        return {**base, 'type': 'array', 'items': {'type': 'string', 'enum': choices},
                'default': [one for one in listed if one in choices]}
    if setting.kind == 'list':
        listed = cast(list[Any], asked) if isinstance(asked, list) else [asked]
        return {**base, 'type': 'string', 'default': ', '.join(str(one) for one in listed)}
    return {**base, 'type': 'string', 'default': '' if asked is None else str(asked)}


def _shown(value: Any) -> str:
    if isinstance(value, list):
        return ', '.join(str(one) for one in cast(list[Any], value)) or 'none'
    return 'unset' if value is None else str(value)


def held(arguments: dict[str, Any], folder: Path) -> dict[str, Any]:
    """The person-only settings among a call's arguments, unless the person lets agents set them."""
    if settings.value('agents_may_set_control', folder):
        return {}
    return {key: value for key, value in arguments.items()
            if (setting := settings.SCHEMA.get(key)) is not None and setting.person_only}


class Tokens:
    """The single-use tokens of the forms this server has asked and not yet seen answered. A token is spent by the
    answer that carries it, so an answer cannot be replayed to run the call again; the SDK's request-state boundary
    already binds it to this call's tool, its arguments and an expiry of `EXPIRES_S`, so a token older than that can
    never be spent and is dropped whenever another is minted or spent: a server that runs for days keeps only the
    forms still open."""

    def __init__(self) -> None:
        self._open: dict[str, float] = {}

    def _prune(self) -> None:
        oldest = time.monotonic() - EXPIRES_S
        for token in [token for token, minted in self._open.items() if minted < oldest]:
            del self._open[token]

    def mint(self) -> str:
        self._prune()
        token = secrets.token_urlsafe(16)
        self._open[token] = time.monotonic()
        return STATE + token

    def spend(self, state: str | None) -> bool:
        self._prune()
        if not state or not state.startswith(STATE):
            return False
        return self._open.pop(state[len(STATE):], None) is not None
