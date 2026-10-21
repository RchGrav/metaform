"""Recognize recurrences from code loaded before a delivered repair.

Fault completion uses map delivery evidence. No timer or background proof service runs.
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from metaform import module as chassis
from metaform.data import Store, StoreError

RESTART = {'web': 'metaform web restart puts the fix in force in the web server',
           'page': 'reloading the page puts the fix in force there',
           'mcp': "the agent's MCP server takes the fix when it next starts or reconnects",
           'feedback': "the agent's MCP server takes the fix when it next starts or reconnects",
           'run': 'the next agent run takes the fix'}


def landed_of(store: Store, work_id: str) -> str | None:
    """When a repair was submitted, kept by the map module, read by key; None when it has no result
    or the map module is off."""
    try:
        with Store(store.project_id, module='map').tables(write=False) as tx:
            row = tx.get('ticket_settings', {'work_id': work_id})
    except StoreError:
        return None
    landed = dict(row).get('landed') if row is not None else None
    return str(landed) if landed else None


def in_force(folder: Path, store: Store, work_id: str) -> bool:
    """Check the providers that know whether a repair is in use."""
    try:
        return all(check(store, work_id) for _, check in chassis.provided(folder, 'work.in_force'))
    except Exception:  # noqa: BLE001  runtime uncertainty cannot disprove the repair
        return False


def seconds(at: str) -> float:
    """A UTC store time, including fractional seconds, as seconds since the epoch."""
    return datetime.fromisoformat(at).timestamp()


def before_fix(folder: Path, store: Store, work_id: str, landed: str, loaded: float | None,
               source: str) -> str | None:
    """Report faults from a pending repair or older code without reopening the delivered repair."""
    if not in_force(folder, store, work_id):
        return 'seen while the fix waits to merge or restart: the merged fix is not in running code'
    if loaded is None or loaded >= seconds(landed):
        return None
    return (f'seen from code loaded before the fix, at {time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(loaded))}: '
            f'{RESTART.get(source, "a restart of what raised it puts the fix in force")}')
