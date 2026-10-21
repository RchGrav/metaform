"""Put merged code into use before fault proof counts time.

Web restarts use the CLI's existing outliving restart. Agent runners and MCP servers keep their current sessions,
so their process births are retained and reported. Fault proof waits only for old processes of its own source.
"""
from __future__ import annotations

import csv
import http.client
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, cast

from metaform import home
from metaform import module as chassis
from metaform.data import Store

from .merge import TRAILER, git
from .recovery import identity


def runtime_root(project: Path) -> Path | None:
    """Only changes to the running editable package need activation here."""
    root = Path(chassis.__file__).resolve().parent
    return root if root.is_relative_to(project.resolve()) else None


def changes(project: Path, work_id: str) -> tuple[str, bool, bool]:
    root = runtime_root(project)
    if root is None:
        return '', False, False
    found = git(project, 'log', '-1', '--format=%H', '--fixed-strings', '--grep', f'{TRAILER}: {work_id}')
    commit = found.stdout.strip()
    if found.returncode or not commit:
        raise ValueError('The merged ticket commit could not be identified for runtime activation.')
    diff = git(project, 'diff-tree', '--root', '--no-commit-id', '--name-only', '-r', '-z', commit)
    if diff.returncode:
        raise ValueError('The merged ticket paths could not be read for runtime activation.')
    files = [Path(name) for name in diff.stdout.split('\0') if name]
    prefix = root.relative_to(project.resolve())
    runtime = [name.relative_to(prefix) for name in files if name.is_relative_to(prefix)
               and 'tests' not in name.parts and name.suffix not in ('.md', '.pyc')]
    python = any(name.suffix == '.py' or 'resources' in name.parts for name in runtime)
    return commit, bool(runtime), python


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        found: Any = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return None
    if not isinstance(found, dict):
        raise TypeError(f'Invalid runtime process record: {path.name}')
    return cast(dict[str, Any], found)


def process(source: str, pid: int, label: str = '') -> dict[str, Any] | None:
    born = identity(pid)
    if born == '':
        return None
    if born is None:
        raise ValueError(f'Cannot establish the identity of {source} process {pid}.')
    return {'source': source, 'pid': pid, 'identity': born, 'label': label}


def web_record() -> dict[str, Any] | None:
    found = read_json(home.home() / 'run' / 'web.json')
    if found is None:
        return None
    held = process('web', int(found['pid']))
    return {**found, **held} if held is not None else None


def old_processes() -> list[dict[str, Any]]:
    """One snapshot of MCP command lines and runner launches. No session is interrupted."""
    from . import command_line, launches
    found: dict[int, dict[str, Any]] = {}
    for pid in process_ids():
        words = command_line(pid)
        mcp = any(words[index:index + 4] == ['-m', 'metaform', 'mcp', 'serve']
                  for index in range(len(words) - 3))
        direct = any(Path(words[index]).stem == 'metaform' and words[index + 1:index + 3] == ['mcp', 'serve']
                     for index in range(len(words) - 2))
        if mcp or direct:
            held = process('mcp', pid, 'next MCP session start')
            if held is not None:
                found[pid] = held
    for record in launches():
        held = process('run', int(record['pid']), str(record.get('work_id') or 'next runner start'))
        if held is not None:
            found[int(held['pid'])] = held
    return list(found.values())


def process_ids() -> list[int]:
    """Read only PIDs from the system, so unrelated credential-bearing command lines are never printed."""
    if sys.platform.startswith('linux'):
        found: list[int] = []
        for path in Path('/proc').iterdir():
            try:
                if path.name.isdecimal() and path.stat().st_uid == os.getuid():
                    found.append(int(path.name))
            except FileNotFoundError:  # a process ended during the one snapshot
                continue
        return found
    if os.name == 'nt':
        done = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, text=True,
                              timeout=5, check=True)
        return [int(row[1]) for row in csv.reader(done.stdout.splitlines()) if len(row) > 1 and row[1].isdecimal()]
    done = subprocess.run(['ps', '-axo', 'pid='], capture_output=True, text=True, timeout=5, check=True)
    return [int(value) for value in done.stdout.split() if value.isdecimal()]


def remaining(held: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """An unknown identity remains pending. PID reuse never extends an old process's lifetime."""
    found: list[dict[str, Any]] = []
    for one in held:
        pid = int(one['pid'])
        current = identity(pid)
        if current is None:
            found.append(one)
        elif current == one['identity']:
            if sys.platform.startswith('linux'):
                try:
                    if Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0] == 'Z':
                        continue  # a zombie cannot execute old code while its parent waits to reap it
                except FileNotFoundError:
                    continue
            found.append(one)
    return found


def web_ready(held: dict[str, Any]) -> bool:
    current = web_record()
    if current is None:
        return False
    raw: Any = held.get('before')
    previous = cast(dict[str, Any], raw) if isinstance(raw, dict) else {}
    if previous and current['pid'] == previous.get('pid') \
            and current['identity'] == previous.get('identity'):
        return False
    # A replacement must have started after this fix landed, including a server started by someone else.
    started = str(current.get('started') or '')
    if not started or started < str(held['after']):
        return False
    bind = str(current.get('bind') or '127.0.0.1')
    address = '127.0.0.1' if bind == '0.0.0.0' else '::1' if bind == '::' else bind
    connection = http.client.HTTPConnection(address, int(current['port']), timeout=2)
    token_path = home.home() / 'run' / 'web-token'
    token = token_path.read_text(encoding='utf-8').strip() if token_path.exists() else ''
    try:
        connection.request('GET', '/api/server', headers={'X-Metaform-Token': token})
        response = connection.getresponse()
        result: Any = json.loads(response.read()) if response.status == 200 else None
        server = cast(dict[str, Any], result) if isinstance(result, dict) else {}
        return server.get('pid') == current['pid'] and server.get('home') == str(home.home())
    finally:
        connection.close()


def kept(own: Store, work_id: str) -> dict[str, Any] | None:
    with own.tables(write=False) as tx:
        row = tx.get('activations', {'work_id': work_id})
    return cast(dict[str, Any], row['value']) if row is not None else None


def keep(own: Store, work_id: str, value: dict[str, Any]) -> None:
    with own.tables() as tx:
        tx.concern(work_id=work_id, kind='ticket')
        if tx.update('activations', {'work_id': work_id}, {'value': value}) is None:
            tx.insert('activations', {'work_id': work_id, 'value': value})


def restart_web(project: Path) -> dict[str, Any]:
    """The CLI hands off to restart.py before stopping web, so the page survives caller exit."""
    env = {key: value for key, value in os.environ.items()
           if key not in ('METAFORM_ROLE', 'METAFORM_SESSION', 'METAFORM_WORK', 'METAFORM_NODE')}
    done = subprocess.run([sys.executable, '-m', 'metaform', 'web', 'restart', '--json'], cwd=project,
                          env=env, capture_output=True, text=True, timeout=130, check=False)
    if done.returncode:
        raise ValueError((done.stdout + done.stderr).strip()[-500:] or 'Web restart failed.')
    result: Any = json.loads(done.stdout)
    status = cast(dict[str, Any], result) if isinstance(result, dict) else {}
    if status.get('state') not in ('restarted', 'started', 'running', 'restarting'):
        raise ValueError('The web restart did not confirm its state.')
    return status


def delivered(ctx: Any, store: Store, own: Store, project: Path, work_id: str) -> dict[str, Any]:
    """After push: journal activation, restart web, report retained MCP/runner identities.

    `active` is delivery readiness. Named old agent processes do not block ordinary completion. `in_force` separately
    gates a fault's proof on processes of its source. A pending or failed web restart is never reported complete.
    """
    try:
        held = kept(own, work_id)
        commit, web, python = changes(project, work_id)
        if held is None or held.get('commit') != commit:
            before = web_record() if web else None
            held = {'commit': commit, 'web': {'required': web, 'before': before,
                                            'after': time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime()),
                                            'state': 'pending' if before is not None else 'not running'},
                    'old_processes': old_processes() if python else [], 'error': ''}
            keep(own, work_id, held)  # durable before restart can stop the process that called us
        status = cast(dict[str, Any], held['web'])
        if status['required'] and status.get('before') is not None and status['state'] != 'restarting' \
                and not web_ready(status):
            status['state'] = str(restart_web(project)['state'])
        ready = not status['required'] or status['state'] == 'not running' or web_ready(status)
        old = remaining(cast(list[dict[str, Any]], held['old_processes']))
        held['error'] = '' if ready else 'Web restart is pending. Fault proof waits for the new server.'
        keep(own, work_id, held)
        return {'active': ready, 'restarts': {'web': status['state'], 'mcp': 'next session', 'run': 'next session'},
                'old_processes': old, 'why': held['error']}
    except Exception as error:  # noqa: BLE001  runtime uncertainty must never start fault proof
        return {'active': False, 'restarts': {'web': 'failed'}, 'old_processes': [], 'why': str(error)}


def in_force(store: Store, work_id: str) -> bool:
    """The fault's source has current code. No activation record preserves non-runtime project compatibility."""
    try:
        held = kept(Store(store.project_id, module='dispatch'), work_id)
        if held is None:
            # A current-package commit needs activation evidence even if a crash preceded its activation journal.
            _, web, _ = changes(Path(store.project().path), work_id)
            return not web
        if not held['web']['required'] and not held['old_processes']:
            return True
        with Store(store.project_id, module='autoticket').tables(write=False) as tx:
            sources = {str(row['source']) for row in tx.rows('groups', {'work_id': work_id}, limit=0).results}
        web = cast(dict[str, Any], held['web'])
        if web['required'] and sources.intersection(('web', 'page')) and not web_ready(web):
            return False
        relevant = {'mcp' if source == 'feedback' else source for source in sources}
        return not any(one['source'] in relevant for one in remaining(held['old_processes']))
    except Exception:  # noqa: BLE001  missing process or activation evidence leaves proof waiting
        return False
