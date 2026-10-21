"""A ticket autoticket files closes only with proof, so a fix that did not hold never leaves the board saying all is well.

Each ticket it files is marked, `map.storage.prove_work`, to close only with proof: an agent's done lands its fix, said as
"Fix landed, watching", and the ticket stays open in its column. The proof is one of two:

- its group does not recur for `autoticket_quiet_minutes` of the project's work after the fix came into force: the
  minutes this project's background ran, in the web server that supervises it, since a fault is seen only while the
  project runs. One timer per watched ticket, set when the watch starts and cancelled when the landing goes, a real
  deadline and never a look for a change, CLAUDE.md section 1; the minutes counted are kept when the background
  closes, so a restart carries on from them;
- a test named in the resolution, `test: <file>::<name>`, a pytest node id of a file in the project, that reproduces the
  fault and passes: run once, when the watch starts, in a thread of its own with a time limit. A test whose file is not
  in the project folder is said in the ticket's note, never dropped without a word.

The watch starts when the fix runs, not on the agent's word: at once for work done in the project folder, and once its
worktree has merged for work done in one, `work.in_force` (dispatch, VIEW-044). Until then the ticket says "Fix landed,
waiting to merge" and nothing counts. A recurrence from code loaded before the fix came into force, by the fault's
`loaded`, is noted on the ticket with what puts the fix in force, `before_fix`, and does not count against it; any
other recurrence while it is watched gives the ticket back with the fix that did not hold, `faults.tell`, which clears
the landing, and the timer hears that and is cancelled. Once proven, the ticket closes, `finish_work(proven=True)`, and
its fault light, the ticket's condition broken, goes off with it; its landing and when the fix came into force are
kept, so a recurrence from old code after the close reopens nothing.

Event rules, CLAUDE.md section 2: the watch is a `project.background` service, and the web server that holds it hands
it each `map.changed` of the project, its own writes and those of other processes, `heard`; it acts only on a change of
kind ticket naming tickets, or of a merge, reads only those it filed, by key, and the landing of each.
"""
from __future__ import annotations

import calendar
import json
import os
import re
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from metaform import events
from metaform import module as chassis
from metaform.data import Store, StoreError, WorkRecord
from metaform.module import Context

from .watch import setting

TEST = re.compile(r'\btest[:=]\s*`?([\w./-]+\.py::[\w.:\[\]-]+)`?')  # a pytest node id named in a resolution
TEST_LIMIT = 600.0  # seconds a named test may run, a deadline on the one run
QUIET = 'quiet '  # a `state` row per watched ticket, `quiet <work id>`: its landing, whether it waits to merge, when
# the fix came into force, `since`, and the seconds of its window counted so far
RESTART = {'web': 'metaform web restart puts the fix in force in the web server',
           'page': 'reloading the page puts the fix in force there',
           'mcp': "the agent's MCP server takes the fix when it next starts or reconnects",
           'feedback': "the agent's MCP server takes the fix when it next starts or reconnects",
           'run': 'the next agent run takes the fix'}


def landed_of(store: Store, work_id: str) -> str | None:
    """When a ticket's fix landed while it is watched, kept by the map module, read by key; None when it is not watched
    or the map module is off."""
    try:
        with Store(store.project_id, module='map').tables(write=False) as tx:
            row = tx.get('ticket_settings', {'work_id': work_id})
    except StoreError:
        return None
    landed = dict(row).get('landed') if row is not None else None
    return str(landed) if landed else None


def named_test(resolution: str | None, folder: Path) -> tuple[str, bool] | None:
    """The pytest node id a resolution names, `test: <file>::<name>`, and whether its file is in the project folder."""
    found = TEST.search(resolution or '')
    if found is None:
        return None
    node = found.group(1)
    path = (folder / node.split('::', 1)[0]).resolve()
    return node, path.is_file() and path.is_relative_to(folder.resolve())


def in_force(folder: Path, store: Store, work_id: str) -> bool:
    """Whether a ticket's fix runs from the project folder, as each module that knows says, `work.in_force`: dispatch's
    merge of a worktree; with none, it is in force once it landed."""
    try:
        return all(check(store, work_id) for _, check in chassis.provided(folder, 'work.in_force'))
    except Exception:  # noqa: BLE001  a module that cannot say leaves the fix in force, as with none
        return True


def kept(store: Store, work_id: str) -> dict[str, Any]:
    """What the watch keeps of a ticket, its `state` row."""
    with store.tables(write=False) as tx:
        row = tx.get('state', {'name': f'{QUIET}{work_id}'})
    return cast(dict[str, Any], json.loads(str(row['value']))) if row is not None else {}


def keep(store: Store, work_id: str, value: dict[str, Any]) -> None:
    row = {'name': f'{QUIET}{work_id}', 'value': json.dumps(value)}
    with store.tables() as tx:
        if tx.update('state', {'name': row['name']}, {'value': row['value']}) is None:
            tx.insert('state', row)


def seconds(at: str) -> float:
    """A store time, `YYYY-MM-DDTHH:MM:SSZ`, as seconds since the epoch."""
    return float(calendar.timegm(time.strptime(at, '%Y-%m-%dT%H:%M:%SZ')))


def before_fix(folder: Path, store: Store, work_id: str, landed: str, loaded: float | None,
               source: str) -> str | None:
    """Why a recurrence of a ticket whose fix landed does not count against the fix, or None when it does: the fix still
    waits to merge, or the code that raised it was loaded, `loaded`, before the fix came into force. A fault that does
    not say when its code was loaded counts."""
    if not in_force(folder, store, work_id):
        return 'seen while the fix waits to merge: the quiet window starts once it is in the project folder'
    if loaded is None:
        return None
    held = kept(store, work_id)
    since = float(held['since']) if held.get('landed') == landed and held.get('since') else seconds(landed)
    if loaded >= since:
        return None
    return (f'seen from code loaded before the fix, at {time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(loaded))}: '
            f'{RESTART.get(source, "a restart of what raised it puts the fix in force")}')


def spawned(function: Callable[..., Any], *args: Any) -> None:
    threading.Thread(target=function, args=args, daemon=True, name=f'proof {args[0]}').start()


def run_test(node: str, folder: Path) -> tuple[bool, str]:
    """Run one named test in the project folder with its own interpreter, `.venv` when it has one; whether it passed,
    and the last lines it printed. The agent session's own identity is not passed on."""
    venv = folder / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    python = str(venv) if venv.is_file() else sys.executable
    env = {key: value for key, value in os.environ.items()
           if key not in ('METAFORM_ROLE', 'METAFORM_SESSION', 'METAFORM_WORK', 'METAFORM_NODE')}
    try:
        done = subprocess.run([python, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', node], cwd=folder, env=env,
                              capture_output=True, text=True, timeout=TEST_LIMIT, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, str(error)
    return done.returncode == 0, '\n'.join((done.stdout + done.stderr).strip().splitlines()[-5:])


class Quiet:
    """The quiet-window timers of one project's watched tickets, in its background. `clock`, `timer`, `test` and
    `spawn` are the monotonic clock, the timer, the test run and the thread it runs in, given in tests."""

    def __init__(self, ctx: Context, *, clock: Callable[[], float] = time.monotonic,
                 timer: Callable[..., Any] = threading.Timer,
                 test: Callable[[str, Path], tuple[bool, str]] = run_test,
                 spawn: Callable[..., None] = spawned) -> None:
        self.ctx = ctx
        self.store = ctx.require_store()
        self.clock, self.timer, self.test, self.spawn = clock, timer, test, spawn
        self.lock = threading.Lock()
        self.armed: dict[str, tuple[Any, float, str, float]] = {}  # work id: timer, armed at, landed, seconds counted
        self.closed = False
        for work_id in self.filed(None):
            self.look(work_id)

    def minutes(self) -> float:
        return float(setting('autoticket_quiet_minutes', self.ctx.folder) or 30)

    def heard(self, payload: dict[str, Any]) -> None:
        """`map.changed`: each ticket it names that autoticket filed is looked at once, on a change of its tickets or of a
        merge, which puts a fix in force; a change of another table, project or kind, or naming no ticket, concerns no
        watch; one that does not say which tickets it concerns may
        concern any, so each ticket autoticket filed is looked at once."""
        if self.closed or payload.get('project') not in (None, self.store.project_id):
            return
        tables, kinds, ids = payload.get('tables'), payload.get('kinds'), payload.get('work_ids')
        merged = 'dispatch.merges' in [*(tables if isinstance(tables, list) else ()),
                                       *cast(list[Any], payload.get('dispatch_tables') or [])]
        if not merged and tables is not None and (not isinstance(tables, list) or 'work' not in tables):
            return
        if not merged and isinstance(kinds, list) and 'ticket' not in kinds:
            return
        if isinstance(ids, list) and not ids:
            return
        named = [str(one) for one in cast(list[Any], ids)] if isinstance(ids, list) else None
        for work_id in self.filed(named):
            self.look(work_id)

    def filed(self, named: list[str] | None) -> list[str]:
        """Of these tickets, or of all when None, those autoticket filed, read by key."""
        with self.store.tables(write=False) as tx:
            if named is not None:
                return [work_id for work_id in named if tx.rows('groups', {'work_id': work_id}, limit=1).results]
            return sorted({str(row['work_id']) for row in tx.rows('groups', limit=0).results
                           if row['work_id'] and not str(row['work_id']).startswith('filing ')})

    def look(self, work_id: str) -> None:
        """Start the watch of a ticket whose fix runs, once per landing; say a fix that waits to merge; cancel the watch of
        a ticket whose landing is gone or that closed."""
        landed = landed_of(self.store, work_id)
        record = self.record(work_id)
        held = kept(self.store, work_id)
        with self.lock:
            armed = self.armed.get(work_id)
            if armed is not None and armed[2] == landed and not record.done:
                return
            if armed is not None:
                armed[0].cancel()
                del self.armed[work_id]
        if landed is None:
            if held:
                self.forget(work_id)
            return
        if record.done or self.closed:
            return
        same = held.get('landed') == landed
        if not in_force(Path(self.ctx.folder), self.store, work_id):
            if not (same and held.get('waiting')):
                keep(self.store, work_id, {'landed': landed, 'waiting': True})
                events.announced(self.ctx.folder, self.ctx.surface, self.store.step_work, work_id,
                                 'Fix landed, waiting to merge: the quiet window starts once it is in the project '
                                 'folder.')
            return
        since = float(held['since']) if same and held.get('since') else time.time()
        counted = float(held.get('counted') or 0) if same else 0.0
        if not (same and held.get('since')):
            keep(self.store, work_id, {'landed': landed, 'since': since, 'counted': counted})
            if same and held.get('waiting'):
                events.announced(self.ctx.folder, self.ctx.surface, self.store.step_work, work_id,
                                 'Fix merged, watching.')
        with self.lock:
            if self.closed or work_id in self.armed:
                return
            timer = self.timer(max(0.0, self.minutes() * 60 - counted), self.due, args=(work_id, landed))
            timer.daemon = True
            self.armed[work_id] = (timer, self.clock(), landed, counted)
            timer.start()
        named = named_test(record.resolution, Path(self.ctx.folder))
        if named is not None and named[1]:
            self.spawn(self.tried, work_id, landed, named[0])
        elif named is not None and not (same and held.get('since')):
            line = (f'The test {named[0]} named in the fix of {landed} is not in the project folder, so it was not run; '
                    'the quiet window decides.')
            events.announced(self.ctx.folder, self.ctx.surface, self.store.edit_work, work_id,
                             {'note': f'{record.note or ""}\n{line}'.strip()})

    def record(self, work_id: str) -> WorkRecord:
        return self.store.work(ids=[work_id], limit=1).results[0]

    def forget(self, work_id: str) -> None:
        with self.store.tables() as tx:
            tx.delete('state', {'name': f'{QUIET}{work_id}'})

    def due(self, work_id: str, landed: str) -> None:
        """The quiet window ran out with no recurrence: the fix held."""
        with self.lock:
            held = self.armed.get(work_id)
            if held is None or held[2] != landed:
                return
            del self.armed[work_id]
        self.proven(work_id, landed, f'its fault did not recur for {self.minutes():g} minutes of the project\'s work '
                                     f'after the fix landed at {landed}')

    def tried(self, work_id: str, landed: str, node: str) -> None:
        """Run the test the resolution names: passed, the fix is proven; failed, the quiet window still runs."""
        passed, said = self.test(node, Path(self.ctx.folder))
        if passed:
            with self.lock:
                held = self.armed.pop(work_id, None)
            if held is not None:
                held[0].cancel()
            self.proven(work_id, landed, f'the test {node} named in the resolution passed')
            return
        record = self.record(work_id)
        line = f'The test {node} named in the fix of {landed} did not pass, so the quiet window decides: {said}'
        events.announced(self.ctx.folder, self.ctx.surface, self.store.edit_work, work_id,
                         {'note': f'{record.note or ""}\n{line}'.strip()})

    def proven(self, work_id: str, landed: str, how: str) -> None:
        """Close the ticket with its proof, unless its landing changed meanwhile."""
        if landed_of(self.store, work_id) != landed:
            return
        record = self.record(work_id)
        if record.done:
            return
        resolution = f'{record.resolution or "Fixed."}\nProven: {how}.'
        events.announced(self.ctx.folder, self.ctx.surface, self.store.finish_work, work_id, resolution,
                         'The fix held: ' + how + '.', proven=True)

    def close(self) -> None:
        """Cancel each timer, keeping the seconds of its window counted so far, so the next background goes on."""
        with self.lock:
            self.closed = True
            armed, self.armed = self.armed, {}
        now = self.clock()
        for work_id, (timer, at, landed, counted) in armed.items():
            timer.cancel()
            keep(self.store, work_id, {**kept(self.store, work_id), 'landed': landed,
                                       'counted': counted + max(0.0, now - at)})


def start(ctx: Context) -> Quiet:
    return Quiet(ctx)
