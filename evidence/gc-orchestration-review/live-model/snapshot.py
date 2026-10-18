"""Read isolated live-journey records without sending a turn or altering receipt state."""
from __future__ import annotations

import datetime
import json
import os
import subprocess
from pathlib import Path

ROOT = Path('/tmp/metaform-review-live')
PROJECT = ROOT / 'project'
CLI = '/workspace/scratch/243b683ad142/metaform/.venv/bin/metaform'
ENV = {**os.environ, 'METAFORM_HOME': str(ROOT / 'home')}


def main() -> None:
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')
    folder = ROOT / 'snapshots' / stamp
    folder.mkdir(parents=True, exist_ok=True)
    saved = {}
    for name, args in (
        ('team', ['orchestration', 'team']),
        ('sessions', ['dispatch', 'sessions']),
        ('capacity', ['dispatch', 'agents']),
        ('requests', ['orchestration', 'role_requests']),
    ):
        result = subprocess.run([CLI, *args, '--json'], cwd=PROJECT, env=ENV,
                                capture_output=True, text=True, check=False, timeout=20)
        (folder / f'{name}.json').write_text(result.stdout)
        (folder / f'{name}.stderr').write_text(result.stderr)
        if result.returncode:
            raise RuntimeError(f'{args}: {result.returncode}: {result.stdout} {result.stderr}')
        saved[name] = json.loads(result.stdout)
    print(json.dumps({'snapshot': str(folder),
        'assignments': [{k: a.get(k) for k in ('assignment_id', 'work_id', 'authored_role_uri', 'state',
                                              'owner_session_id', 'parent_assignment_id', 'reviewed_assignment_id')}
                        for a in saved['team'].get('assignments', [])],
        'capacity': saved['capacity'].get('slots'),
        'requests': [{k: a.get(k) for k in ('request_id', 'caller_assignment_id', 'gc_assignment_id',
                                           'role', 'state', 'creator_assignment_id', 'child_assignment_id')}
                     for a in saved['requests']],
        'session_states': [{k: a.get(k) for k in ('session_id', 'state', 'how', 'status', 'activity')}
                           for a in saved['sessions'].get('sessions', [])],
        'recent_messages': [{'session': a['session_id'], 'text': a['text'][:2000]}
                            for a in saved['sessions'].get('lines', [])
                            if a['kind'] == 'agent_message_chunk'][-5:]}, indent=2))


if __name__ == '__main__':
    main()
