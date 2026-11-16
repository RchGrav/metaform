"""offered: what each harness answered when dispatch asked it, kept in the Metaform home by harness.

An ACP harness says what it is in `initialize`, its name, version, capabilities and logins, and what a session of it
can be set to in `session/new`, its config options with their choices (agentclientprotocol.com, session-config-options,
read 2026-11-16). Those follow the harness's version and the account logged in on this machine, so they are the
home's: one file per harness, `<home>/agents/_offered/<harness>.json`, beside the registry's pinned entries. Every
project reads the same record, a cleared project loses nothing, and a new one starts with the pickers filled.

A record's `state` says how the asking went: `ready`, it answered with its settings; `needs login`, it refused a
session until the person logs in, with the logins it offers; `cannot start`, with the reason. Each session a harness
makes writes its own answer over the record, so it follows the harness as it changes.
"""
from __future__ import annotations

import json
import os
import re
import secrets
from pathlib import Path
from typing import Any, cast

from metaform import home
from metaform.module import request_cached

from . import registry

FOLDER = '_offered'  # under the home's agents folder; a registry id starts with a letter, so no harness is named it
STATES = ('ready', 'needs login', 'cannot start')
NAME = re.compile(r'^[a-z][a-z0-9_-]*$')


def folder() -> Path:
    return home.home() / registry.FOLDER / FOLDER


def path(agent: str) -> Path:
    if not NAME.match(agent):
        raise ValueError(f'{agent} is not a harness name.')
    return folder() / f'{agent}.json'


def _read(file: Path) -> dict[str, Any] | None:
    try:
        held: Any = json.loads(file.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None  # absent or unreadable: the harness is asked again
    if not isinstance(held, dict):
        return None
    row = cast(dict[str, Any], held)
    return row if row.get('agent') == file.stem else None


def records() -> dict[str, dict[str, Any]]:
    """Every harness's record, by harness, read once in a request: every option of every harness asks for it."""
    root = folder()

    def read() -> dict[str, dict[str, Any]]:
        try:
            files = sorted(root.glob('*.json'))
        except OSError:
            return {}
        found = {file.stem: _read(file) for file in files}
        return {agent: row for agent, row in found.items() if row is not None}
    return cast(dict[str, dict[str, Any]], request_cached(('dispatch.offered', str(root)), read))


def record(agent: str) -> dict[str, Any] | None:
    return records().get(agent)


def keep(agent: str, row: dict[str, Any]) -> dict[str, Any]:
    """Write a harness's record whole, so a reader sees the one before or this one, never part of it. A record that
    is not `ready` and names no settings keeps those last known, since a login lapsing or a start failing does not
    change what the harness offers."""
    if row.get('state') not in STATES:
        raise ValueError(f'A harness is {", ".join(STATES)}, not {row.get("state")}.')
    file = path(agent)
    held = _read(file)
    kept = {**row, 'agent': agent}
    if kept['state'] != 'ready' and held is not None and held.get('settings') and not kept.get('settings'):
        kept['settings'] = held['settings']
    home.mkdir_private(file.parent)
    partial = file.with_name(f'.{file.name}.{secrets.token_hex(4)}')
    home.write_private(partial, json.dumps(kept, ensure_ascii=False, indent=1))
    os.replace(partial, file)
    cached = records()  # the request's own read, when it has one, follows the write
    cached[agent] = kept
    return kept


def forget(agent: str) -> None:
    """Drop a harness's record, as when the person removes the harness."""
    try:
        path(agent).unlink()
    except FileNotFoundError:
        pass
    records().pop(agent, None)
