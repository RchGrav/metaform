"""Isolated current-only real ACP smoke case; observations omit credential contents.

Start with --discover. A later --run reuses that isolated home after choosing an
advertised model. Only temporary artifact files and that home's records change.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path


def run_case(args):
    from metaform import home, settings
    from metaform.data import Store
    from metaform.loader import set_enabled
    from metaform.module import context, surface

    repository = Path(__file__).resolve().parents[1]
    if args.discover:
        auth = subprocess.run(['codex', 'login', 'status'], capture_output=True, text=True,
                              timeout=15, check=False)
        if auth.returncode != 0 or 'logged in' not in (auth.stdout + auth.stderr).lower():
            print(json.dumps({'status': 'unavailable', 'reason': 'Codex authentication is not established.'}))
            return
        surface(repository)
        command = str(context('dispatch', repository, project='metaform').setting('dispatch_codex'))
        root = Path(tempfile.mkdtemp(prefix='metaform-acp-live-'))
        root.chmod(0o700)
        (root / 'launch.json').write_text(json.dumps({'command': command}))
        os.chmod(root / 'launch.json', 0o600)
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith('METAFORM_') and not key.startswith('FAKE_')}
        environment.update(METAFORM_HOME=str(root / 'home'), PYTHONPATH=str(repository / 'src'))
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--setup', str(root)],
                                env=environment, capture_output=True, text=True, timeout=100, check=False)
        catalog = json.loads((root / 'catalog.json').read_text()) if (root / 'catalog.json').exists() else {}
        print(json.dumps({'isolated_root': str(root), 'setup_exit': result.returncode,
                          'advertised': [{'agent': one.get('agent'), 'version': one.get('version'),
                            'options': {item['key']: {'current': item.get('current'),
                                        'values': [value['value'] for value in item.get('choices', [])]}
                                        for item in one.get('settings', [])}} for one in catalog.get('agents', [])]}, indent=2))
        return
    root = args.setup or args.run
    folder = root / 'project'
    if args.setup:
        folder.mkdir()
        home.add_project('acp-live-audit', folder)
        set_enabled('dispatch', True)
        set_enabled('orchestration', False)
        surface(folder)
        command = json.loads((root / 'launch.json').read_text())['command']
        for key, value in {'dispatch_codex': command, 'dispatch_autostart': False,
                           'dispatch_stay_connected': False, 'dispatch_resume_chats': True,
                           'dispatch_record_on_finish': 'off', 'dispatch_prompts': 'approve-all',
                           'dispatch_elicitation': 'decline', 'orchestration_reviews': 0}.items():
            settings.put(key, value, folder)
        store = Store('acp-live-audit')
        store.layer('parts', 'test', 'Isolated ACP verification artifacts.', mutable=True, hideable=True, ready=True)
        store.add_element('parts', 'data.audit')
        (folder / 'preserved.txt').write_text('DO NOT CHANGE\n')
        completed = subprocess.run([sys.executable, '-m', 'metaform', 'dispatch', 'options', 'agent=codex',
                                    'prime=true', '--json'], cwd=folder, capture_output=True, text=True,
                                   timeout=90, check=False)
        try:
            catalog = json.loads(completed.stdout)
        except ValueError:
            catalog = {'status': 'not-json', 'exit': completed.returncode}
        (root / 'catalog.json').write_text(json.dumps(catalog, indent=2) + '\n')
        return
    set_enabled('orchestration', False)
    surface(folder)
    settings.put('dispatch_codex_model', args.model, folder)
    if args.effort is not None:
        settings.put('dispatch_codex_effort', args.effort, folder)
    from metaform.modules.dispatch import session_state, sessions

    surface(folder)
    settings.put('dispatch_codex', shlex.join([sys.executable, str(Path(__file__).resolve()),
                                            '--proxy', str(root)]), folder)
    store = Store('acp-live-audit')
    notices = threading.Event()
    ctx = context('dispatch', folder, project=store.project_id)
    listener = ctx.listen(lambda payload: notices.set() if payload.get('project') == store.project_id else None)
    advertised = json.loads((root / 'catalog.json').read_text())['agents'][0]
    cli = subprocess.run(['codex', '--version'], capture_output=True, text=True, timeout=10, check=False)
    result = {'adapter': {'name': '@agentclientprotocol/codex-acp', 'version': advertised.get('version'),
                          'codex_cli_version': cli.stdout.strip() if cli.returncode == 0 else None},
              'runtime': {'model': args.model, 'effort': args.effort},
              'isolated_root': str(root), 'contributions': [], 'provider_billing': None,
              'mode': 'direct_worker', 'runtime_provenance': 'isolated project defaults'}
    process = None
    try:
        for index in range(1):
            target = 'alpha\n'
            operation = 'Create result.txt containing exactly alpha followed by one newline.'
            source = (operation + ' Exception: do not change preserved.txt. Work only in this temporary project. '
                      'Use the existing exact request source for this work through map_work op=sources; '
                      'then perform the requested file edit and verify those two files. '
                      'This is a small local artifact change. Complete only the assigned work record through '
                      'map_work op=done with resolution and why, then return. Do not start other agents, '
                      'create extra work records or contact external services.')
            added = subprocess.run([sys.executable, '-m', 'metaform', 'map', 'work', 'op=add',
                                    'node=element:data.audit', f'title=Isolated artifact contribution {index + 1}', 'task=' + source,
                                    'source=' + json.dumps({'text': source, 'reference': 'isolated-live-acp-case'}),
                                    '--json'], cwd=folder, capture_output=True, text=True, timeout=20, check=False)
            if added.returncode:
                result['failure'] = {'stage': 'add_work', 'exit': added.returncode}
                break
            work = json.loads(added.stdout)['id']
            process = subprocess.Popen([sys.executable, '-m', 'metaform', 'dispatch', 'run', work, 'codex'],
                                       cwd=folder, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            deadline = time.monotonic() + 150
            finished = False
            while True:
                notices.clear()
                records = [one for one in sessions(store, verify=False) if one['work_id'] == work]
                if store.ticket(work).work.done and any(one['state'] == 'ended' for one in records):
                    finished = True
                    break
                if records and all(one['state'] == 'ended' for one in records):
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                notices.wait(remaining)
            artifact = (folder / 'result.txt').read_text() if (folder / 'result.txt').exists() else None
            preserved = (folder / 'preserved.txt').read_text() == 'DO NOT CHANGE\n'
            state = session_state(store, records[-1]['session_id']) if records else None
            result['contributions'].append({'work_id': work, 'done': finished, 'artifact_matches': artifact == target,
                'exception_preserved': preserved,
                'session_ids': [one['session_id'] for one in records],
                'reported_tokens': (state or {}).get('tokens'),
                'source_exact': any(one.get('text') == source for one in store.work_sources(work))})
            (root / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
            if not finished or artifact != target or not preserved:
                result['failure'] = {'stage': 'worker_outcome', 'timed_out': time.monotonic() >= deadline}
                break
    finally:
        listener.close()
        subprocess.run([sys.executable, '-m', 'metaform', 'dispatch', 'stop-all'], cwd=folder,
                       capture_output=True, text=True, timeout=30, check=False)
        if process is not None:
            if process.poll() is None:
                process.terminate()
            try:
                process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
        if (root / 'wire.jsonl').exists():
            result['wire'] = [json.loads(line) for line in (root / 'wire.jsonl').read_text().splitlines()]
        result['billing_limit'] = 'Current-only real adapter smoke, no production before/after billing inference.'
        (root / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({key: value for key, value in result.items() if key != 'wire'}, indent=2))


def proxy(root):
    """Transparent ACP transport recording metadata only, never prompt/auth bodies."""
    words = shlex.split(json.loads((root / 'launch.json').read_text())['command'])
    child = subprocess.Popen(words, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr)
    lock = threading.Lock()

    def observed(line, direction):
        try:
            message = json.loads(line)
        except ValueError:
            return
        row = {'direction': direction, 'bytes': len(line), 'method': message.get('method'), 'id': message.get('id')}
        if message.get('method') == 'session/prompt':
            row['text_bytes'] = sum(len(block.get('text', '').encode()) for block in
                                    message.get('params', {}).get('prompt', []) if block.get('type') == 'text')
        answer = message.get('result') or {}
        if isinstance(answer, dict):
            if 'agentInfo' in answer:
                row['agentInfo'] = {key: answer['agentInfo'].get(key) for key in ('name', 'version')}
            if 'usage' in answer:
                row['usage'] = answer['usage']
            if 'stopReason' in answer:
                row['stopReason'] = answer['stopReason']
        with lock, (root / 'wire.jsonl').open('a') as target:
            target.write(json.dumps(row) + '\n')

    def input_to_agent():
        for line in sys.stdin.buffer:
            observed(line, 'client_to_adapter')
            try:
                child.stdin.write(line)
                child.stdin.flush()
            except (BrokenPipeError, OSError):
                return
        child.stdin.close()

    threading.Thread(target=input_to_agent, daemon=True).start()
    for line in child.stdout:
        observed(line, 'adapter_to_client')
        sys.stdout.buffer.write(line)
        sys.stdout.buffer.flush()
    sys.exit(child.wait())



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--discover', action='store_true')
    action.add_argument('--setup', type=Path, help=argparse.SUPPRESS)
    action.add_argument('--run', type=Path)
    action.add_argument('--proxy', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--model')
    parser.add_argument('--effort')
    args = parser.parse_args()
    if args.run and not args.model:
        parser.error('--run requires an advertised --model')
    if args.run and not all((args.run / name).is_file() for name in ('launch.json', 'catalog.json')):
        parser.error('--run requires the isolated root created by --discover')
    if args.proxy:
        proxy(args.proxy)
    else:
        isolated = args.run or args.setup
        if isolated is not None:
            for key in tuple(os.environ):
                if key.startswith('METAFORM_'):
                    os.environ.pop(key)
            os.environ['METAFORM_HOME'] = str(isolated / 'home')
        run_case(args)


if __name__ == '__main__':
    main()
