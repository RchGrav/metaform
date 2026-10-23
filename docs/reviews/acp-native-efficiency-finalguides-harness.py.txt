"""Matched native ACP workload, metadata-only observations, no credential output.

--run CHECKOUT --label LABEL --output FILE creates a private three-card project.
Prepared runtime provenance is 'benchmark', never person or Facilitator.
Pass --launch-config PRIVATE_JSON containing the registered ACP command as
{"command": "..."}. Existing adapter authentication is used without being read
or printed. --model and --effort default to the measured gpt-6-luna/low pair.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from pathlib import Path

MODEL = 'gpt-6-luna'
EFFORT = 'low'


def safe_update_metadata(update):
    kind = update.get('sessionUpdate')
    if kind not in ('tool_call', 'compaction', 'compaction_update', 'compaction_summary_chunk'):
        return {}
    result = {'update_kind': kind}
    if kind != 'tool_call':
        result['compaction'] = {key: update[key] for key in ('compactionId', 'status', 'subagentSessionId')
                                if key in update}
    return result


def descendants(pid):
    found = []
    pending = [pid]
    while pending:
        parent = pending.pop()
        try:
            children = Path(f'/proc/{parent}/task/{parent}/children').read_text().split()
        except OSError:
            continue
        for child in children:
            ident = int(child)
            try:
                words = Path(f'/proc/{ident}/cmdline').read_bytes().split(b'\0')
                name = Path(words[0].decode(errors='replace')).name
            except OSError:
                continue
            role = ('native_app_server' if b'app-server' in words else
                    'metaform_mcp' if b'metaform' in words and b'mcp' in words and b'serve' in words else
                    'adapter' if any(b'codex-acp' in word for word in words) else 'child')
            found.append({'pid': ident, 'parent': parent, 'executable': name, 'role': role})
            pending.append(ident)
    return found


def proxy(root):
    command = json.loads((root / 'launch.json').read_text())['command']
    child = subprocess.Popen(shlex.split(command), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr)
    lock = threading.Lock()

    def observed(line, direction):
        try:
            message = json.loads(line)
        except ValueError:
            return
        method = message.get('method')
        row = {'time': time.time(), 'direction': direction, 'method': method, 'id': message.get('id'),
               'bytes': len(line), 'proxy_pid': os.getpid(), 'adapter_pid': child.pid}
        params = message.get('params') or {}
        if method == 'session/prompt':
            row['text_bytes'] = sum(len(b.get('text', '').encode()) for b in params.get('prompt', [])
                                    if b.get('type') == 'text')
        if method in ('session/new', 'session/load', 'session/resume', 'session/prompt'):
            row['processes'] = descendants(os.getpid())
            row['session_id'] = params.get('sessionId')
        if method == 'session/set_config_option':
            row['configuration'] = {key: params.get(key) for key in ('configId', 'value')}
        answer = message.get('result') or {}
        if isinstance(answer, dict):
            for key in ('sessionId', 'usage', 'stopReason', 'agentInfo'):
                if key in answer:
                    row[key] = answer[key]
        update = params.get('update') or {}
        if method == 'session/update':
            kept = safe_update_metadata(update)
            if kept:
                row.update(kept)
                row['session_id'] = params.get('sessionId')
                row['processes'] = descendants(os.getpid())
        with lock, (root / 'wire.jsonl').open('a') as output:
            output.write(json.dumps(row) + '\n')

    def send_input():
        for line in sys.stdin.buffer:
            observed(line, 'client_to_adapter')
            try:
                child.stdin.write(line)
                child.stdin.flush()
            except (BrokenPipeError, OSError):
                return
        child.stdin.close()

    threading.Thread(target=send_input, daemon=True).start()
    for line in child.stdout:
        observed(line, 'adapter_to_client')
        sys.stdout.buffer.write(line)
        sys.stdout.buffer.flush()
    sys.exit(child.wait())


def native_summary(session_ids, first_work):
    sessions = []
    unique = {}
    source_reads = []
    for session in dict.fromkeys(session_ids):
        matches = list(Path.home().joinpath('.codex/sessions').glob(f'**/*{session}*.jsonl'))
        if len(matches) != 1:
            sessions.append({'id': session, 'log_status': 'unavailable'})
            continue
        path = matches[0]
        result = {'id': session, 'log_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                  'turn_contexts': [], 'events': Counter(), 'event_message_types': Counter(), 'message_bytes_by_role': Counter(),
                  'custom_tool_calls': 0, 'tool_output_bytes': 0, 'compaction_events': [], 'requests': [],
                  'instruction_messages': [], 'tool_calls': []}
        current_turn = None
        for ordinal, line in enumerate(path.open()):
            item = json.loads(line)
            data = item.get('payload') or {}
            result['events'][item.get('type')] += 1
            if item.get('type') == 'event_msg':
                result['event_message_types'][str(data.get('type'))] += 1
            if item.get('type') == 'session_meta':
                base = data.get('base_instructions') or {}
                text = str(base.get('text') or '') if isinstance(base, dict) else str(base)
                result['metadata'] = {key: data.get(key) for key in ('id', 'cli_version', 'originator', 'model_provider', 'cwd')}
                result['base_instruction_utf8_bytes'] = len(text.encode())
                result['base_instruction_sha256'] = hashlib.sha256(text.encode()).hexdigest()
            if item.get('type') == 'turn_context':
                current_turn = data.get('turn_id')
                result['turn_contexts'].append({key: data.get(key) for key in ('turn_id', 'root_turn_id', 'model', 'effort')})
            if 'compact' in str(item.get('type')).lower() or 'compact' in str(data.get('type')).lower():
                result['compaction_events'].append({'ordinal': ordinal, 'type': item.get('type'), 'kind': data.get('type')})
            if item.get('type') == 'token_usage_record':
                key = (data.get('thread_id'), data.get('response_id'))
                if not all(key):
                    continue
                usage = data['usage']
                if key in unique:
                    assert unique[key] == usage, 'Conflicting duplicate response usage'
                    continue
                unique[key] = usage
                result['requests'].append({'response_id': key[1], 'turn_id': data.get('turn_id'), 'usage': usage})
                result['last_thread_cumulative_usage'] = data.get('thread_token_usage')
            if item.get('type') == 'response_item' and data.get('type') == 'message':
                body = json.dumps(data.get('content')).encode()
                role = data.get('role')
                result['message_bytes_by_role'][role] += len(body)
                if role in ('developer', 'system', 'user'):
                    text = '\n'.join(part.get('text', '') for part in data.get('content', []) if isinstance(part, dict))
                    skills = re.search(r'<skills_instructions>(.*?)</skills_instructions>', text, re.DOTALL)
                    result['instruction_messages'].append({'ordinal': ordinal, 'turn_id': current_turn,
                        'role': role, 'content_json_bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest(),
                        'text_utf8_bytes': len(text.encode()), 'text_sha256': hashlib.sha256(text.encode()).hexdigest(),
                        'mentions_agents_md': 'AGENTS.md' in text, 'environment_block': 'environment_context' in text,
                        'skills_catalog': skills is not None,
                        'skill_entry_count': len(re.findall(r'^- [a-zA-Z0-9_:.-]+:', skills[1], re.MULTILINE)) if skills else None,
                        'gateway_guidance': ('Metaform is extended by named modules.' in text or
                                             "Use the host-advertised handle for Metaform's metaform_catalog gateway" in text),
                        'first_design_body_present': 'Product design for later sequence/report functions' in text})
            if data.get('type') == 'custom_tool_call':
                result['custom_tool_calls'] += 1
                text = str(data.get('input') or '')
                tools = re.findall(r'''["']?tool["']?\s*:\s*["']([a-zA-Z_]+)["']''', text)
                functions = re.findall(r'tools\.([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', text)
                operations = re.findall(r'''["']?op["']?\s*:\s*["']([a-zA-Z_]+)["']''', text)
                result['tool_calls'].append({'ordinal': ordinal, 'turn_id': current_turn,
                    'functions': functions, 'catalog_tools': tools, 'operations': operations,
                    'discovery_query': 'ALL_TOOLS' in text, 'input_utf8_bytes': len(text.encode())})
                if first_work in text and ('map_work' in text or 'map work' in text):
                    targeted = bool(re.search(r'''["']?id["']?\s*:\s*["']''' + re.escape(first_work), text))
                    source_reads.append({'session_id': session, 'turn_id': current_turn, 'ordinal': ordinal, 'call_id': data.get('call_id'),
                                         'targeted_first_work': targeted,
                                         'explicit_source_retrieval': targeted and (not operations or
                                                                                   any(op in ('read', 'sources') for op in operations))})
            if data.get('type') == 'custom_tool_call_output':
                result['tool_output_bytes'] += len(str(data.get('output') or '').encode())
        result['events'] = dict(result['events'])
        result['event_message_types'] = dict(result['event_message_types'])
        result['message_bytes_by_role'] = dict(result['message_bytes_by_role'])
        turns = {}
        for request in result['requests']:
            turn = turns.setdefault(request['turn_id'], {'request_count': 0, 'usage_sums': Counter(),
                'first_request_usage': request['usage'], 'custom_tool_calls': 0})
            turn['request_count'] += 1
            turn['usage_sums'].update(request['usage'])
            turn['last_request_usage'] = request['usage']
        for call in result['tool_calls']:
            if call['turn_id'] in turns:
                turns[call['turn_id']]['custom_tool_calls'] += 1
        result['turn_summaries'] = {key: {**value, 'usage_sums': dict(value['usage_sums'])} for key, value in turns.items()}
        session_usage = Counter()
        for request in result['requests']:
            session_usage.update(request['usage'])
        result['summed_requests_match_last_thread_usage'] = dict(session_usage) == result.get('last_thread_cumulative_usage')
        sessions.append(result)
    totals = Counter()
    for usage in unique.values():
        totals.update(usage)
    return {'sessions': sessions, 'unique_model_response_count': len(unique), 'usage_sums': dict(totals),
            'first_design_source_tool_references': source_reads,
            'scope': 'Native per-response usage deduplicated by thread_id/response_id; cumulative turn/thread fields never summed. Provider billing unknown.'}


def wire_observations(path):
    raw = path.read_bytes()
    rows = [json.loads(line) for line in raw.splitlines()]
    lifecycle = {'initialize', 'session/new', 'session/load', 'session/resume', 'session/set_config_option',
                 'session/prompt', 'session/close', 'session/delete'}
    kept = [row for row in rows if row.get('method') in lifecycle or row.get('update_kind') or
            any(key in row for key in ('sessionId', 'usage', 'stopReason', 'agentInfo'))]
    counts = Counter((row['direction'], row.get('method') or 'response') for row in rows)
    metadata = {'raw_sha256': hashlib.sha256(raw).hexdigest(), 'raw_bytes': len(raw),
                'raw_event_count': len(rows), 'retained_event_count': len(kept),
                'method_counts': [{'direction': direction, 'method': method, 'count': count}
                                  for (direction, method), count in sorted(counts.items())],
                'retention': 'Lifecycle/config/prompt/results and tool-call/compaction process snapshots retained; repetitive streaming chunk metadata aggregated.'}
    methods = dict(Counter(row['method'] for row in rows if row['direction'] == 'client_to_adapter' and row.get('method')))
    return kept, metadata, methods


def accounting_reconciliation(arm):
    usage = arm['native']['usage_sums']
    rows = arm['reported_spending_rows']
    expected = {'input': usage.get('input_tokens', 0) - usage.get('cached_input_tokens', 0),
                'cache_read': usage.get('cached_input_tokens', 0), 'output': usage.get('output_tokens', 0)}
    return {'application_rows': len(rows),
            'application_totals_match_native': all(all(row.get(key) is not None for row in rows) and
                sum(row[key] for row in rows) == count for key, count in expected.items()),
            'application_cost_fields': 'absent' if all(row.get('cost') is None for row in rows) else 'reported',
            'provider_billing': 'unknown'}


def worker(args):
    sys.path[:0] = [str(args.run / 'src'), str(args.run)]
    from metaform import home, settings
    from metaform.data import Node, Store
    from metaform.loader import set_enabled
    from metaform.module import context, provided, surface
    from metaform.modules.dispatch import own_store, session_state, sessions
    from metaform.modules.orchestration.state import SERVICE

    root = args.case
    harness_bytes = Path(__file__).read_bytes()
    (root / 'measured-harness.py').write_bytes(harness_bytes)
    source_patch = subprocess.check_output(['git', 'diff', 'HEAD', '--binary', '--', 'src'], cwd=args.run)
    (root / 'source.patch').write_bytes(source_patch)
    source_snapshot = {'base_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=args.run, text=True).strip(),
                       'tracked_src_patch_sha256': hashlib.sha256(source_patch).hexdigest(),
                       'tracked_src_patch_bytes': len(source_patch),
                       'harness_sha256': hashlib.sha256(harness_bytes).hexdigest(),
                       'changed_source_files': {}}
    changed = subprocess.check_output(['git', 'diff', 'HEAD', '--name-only', '--', 'src'], cwd=args.run, text=True).splitlines()
    for name in changed:
        path = args.run / name
        source_snapshot['changed_source_files'][name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
    folder = root / 'project'
    folder.mkdir()
    home.add_project('native-efficiency', folder)
    set_enabled('dispatch', True)
    set_enabled('orchestration', True)
    surface(folder)
    command = shlex.join([sys.executable, str(Path(__file__).resolve()), '--proxy', str(root)])
    for key, value in {'dispatch_codex': command, 'dispatch_agent': 'codex', 'dispatch_autostart': True,
                       'dispatch_stay_connected': False, 'dispatch_resume_chats': True, 'dispatch_worktrees': False,
                       'dispatch_record_on_finish': 'off', 'dispatch_prompts': 'approve-all',
                       'dispatch_elicitation': 'decline', 'orchestration_reviews': 0}.items():
        settings.put(key, value, folder)
    store = Store('native-efficiency')
    store.layer('parts', 'test', 'Prepared label formatting functionality.', mutable=True, hideable=True, ready=True)
    store.add_element('parts', 'code.formatter')
    (folder / 'formatter.py').write_text('def label(value):\n    return str(value)\n')
    (folder / 'preserved.cfg').write_bytes(b'preserve-this-exactly\n')
    prime = subprocess.run([sys.executable, '-m', 'metaform', 'dispatch', 'options', 'agent=codex', 'prime=true', '--json'],
                           cwd=folder, capture_output=True, text=True, timeout=90, check=False)
    assert prime.returncode == 0, 'Native catalog prime failed'
    catalog = json.loads(prime.stdout)['agents'][0]
    settings.put('dispatch_codex_model', MODEL, folder)
    settings.put('dispatch_codex_effort', EFFORT, folder)
    assert any(MODEL in [c['value'] for c in s['choices']] for s in catalog['settings'] if s['key'] == 'model')
    ctx = context('orchestration', folder, project=store.project_id)
    runtime = provided(folder, 'ticket.runtime')[0][1]
    wake = threading.Event()
    listener = ctx.listen(lambda p: wake.set() if p.get('project') == store.project_id else None)
    arms = {'label': args.label, 'checkout': str(args.run), 'commit': subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=args.run, text=True).strip(), 'model': MODEL, 'effort': EFFORT,
        'prepared_runtime_decider': 'benchmark', 'scope': 'Selector/planner overhead excluded by identical prepared role/runtime in all arms.',
        'cards': [], 'billing': None, 'source_snapshot': source_snapshot}
    tasks = [
        ('Implement label(value): None displays as an empty string; other values use str(value).strip(). '
        'Product design for later sequence/report functions: only None items are omitted. Empty and whitespace-only '
        'strings are intentional blank separators and must remain entries after normalization. Actual zero and False '
        'remain visible data. Do not add unrequested sequence/report features yet. Add focused unittest coverage.'),
        ('Add labels(values), applying the established product handling of missing items and blank separators in '
        'original order. Support generators and do not mutate a list input. Reuse label and extend focused unittest coverage.'),
        ('Add render(values), using the established product handling to join labels with newline separators and no extra '
        'trailing newline. Keep ordered blank separators. Reuse existing functions and extend focused unittest coverage.')
    ]
    checks = [
        "assert m.label(None)==''; assert m.label(' x ')== 'x'; assert m.label(0)=='0'; assert m.label(False)=='False'",
        "x=[None,'',0,False,' x ']; assert m.labels(x)==['','0','False','x']; assert x==[None,'',0,False,' x ']; assert m.labels(iter(x))==['','0','False','x']",
        "assert m.render([None,'',0,False,' x '])=='\\n0\\nFalse\\nx'; assert m.render([])==''"
    ]
    first = None
    previous = None
    session_ids = []
    try:
        for index, task in enumerate(tasks):
            receipt = f' Original design source receipt: work {first}; use its existing map_work view if needed.' if first else ''
            task = 'In formatter.py: ' + task
            task += receipt + ' Exception: do not modify preserved.cfg. Work only in this isolated project. '
            task += 'This is a local implementation contribution with role/runtime already prepared. Complete the assigned '
            task += 'work record through map_work op=done with resolution and why after focused verification. Do not start other agents.'
            work = store.add_work(Node('element', 'code.formatter'), None, task=task, title=f'Label contribution {index + 1}').id
            first = first or work
            runtime.save(ctx, work, {'agent': 'codex', 'model': MODEL, 'effort': EFFORT,
                'decision': {'decider': 'benchmark', 'confidence': 1.0,
                             'reason': 'User-authorized matched native experiment; fixed advertised runtime.'}})
            call_ctx = context('orchestration', folder, project=store.project_id, nouns={
                'work': work, 'role': 'implementer', **({'continue_from': previous} if previous and hasattr(SERVICE, 'episode') else {})})
            SERVICE.claim(call_ctx)
            launched = SERVICE.drain(call_ctx, [work])
            assert launched, 'Prepared contribution did not launch'
            began = time.monotonic()
            complete = False
            deadline = began + 240
            while True:
                wake.clear()
                rows = [r for r in sessions(store, verify=False) if r['work_id'] == work]
                if store.ticket(work).work.done and any(r['state'] == 'ended' for r in rows):
                    complete = True
                    break
                if rows and all(r['state'] == 'ended' for r in rows):
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                wake.wait(remaining)
            current_ids = [r['session_id'] for r in rows]
            session_ids += current_ids
            test = subprocess.run([sys.executable, '-c', 'import formatter as m; ' + checks[index]],
                                  cwd=folder, capture_output=True, timeout=10, check=False)
            unittest = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-q'], cwd=folder,
                                      capture_output=True, timeout=20, check=False)
            record = {'work_id': work, 'done': complete, 'session_ids': current_ids,
                      'elapsed_seconds': time.monotonic() - began, 'acceptance_passed': test.returncode == 0,
                      'worker_unittest_passed': unittest.returncode == 0,
                      'exception_preserved': (folder / 'preserved.cfg').read_bytes() == b'preserve-this-exactly\n',
                      'source_task_sha256': hashlib.sha256(task.encode()).hexdigest(),
                      'artifact_sha256': hashlib.sha256((folder / 'formatter.py').read_bytes()).hexdigest()}
            arms['cards'].append(record)
            (root / 'progress.json').write_text(json.dumps(arms, indent=2) + '\n')
            print(json.dumps({'label': args.label, 'card': index + 1, **record}), flush=True)
            if not all(record[k] for k in ('done', 'acceptance_passed', 'worker_unittest_passed', 'exception_preserved')):
                break
            previous = work
    finally:
        listener.close()
        subprocess.run([sys.executable, '-m', 'metaform', 'dispatch', 'stop-all'], cwd=folder,
                       capture_output=True, timeout=30, check=False)
        arms['native'] = native_summary(session_ids, first or '')
        arms['wire'], arms['wire_observation'], arms['acp_methods'] = wire_observations(root / 'wire.jsonl')
        arms['session_final_states'] = [{'session_id': r['session_id'], 'state': r['state'],
            'runtime': {s['id']: s.get('current') for s in (session_state(store, r['session_id']) or {}).get('settings', [])
                        if s['id'] in ('model', 'reasoning_effort', 'mode', 'fast-mode')}}
            for r in sessions(store, verify=False)]
        with own_store(store).tables(write=False) as tx:
            arms['reported_spending_rows'] = [dict(r) for r in tx.rows('spending', limit=0).results]
        arms['accounting_reconciliation'] = accounting_reconciliation(arms)
        args.output.write_text(json.dumps(arms, indent=2) + '\n')
        print(json.dumps({'label': args.label, 'model_responses': arms['native']['unique_model_response_count'],
                          'usage': arms['native']['usage_sums'], 'acp_methods': arms['acp_methods']}), flush=True)


def main():
    global MODEL, EFFORT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path)
    parser.add_argument('--case', type=Path)
    parser.add_argument('--label')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--proxy', type=Path)
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--launch-config', type=Path,
                        help='Private JSON with the registered ACP adapter command under command; never published.')
    parser.add_argument('--model', default=MODEL)
    parser.add_argument('--effort', default=EFFORT)
    args = parser.parse_args()
    MODEL, EFFORT = args.model, args.effort
    if args.proxy:
        proxy(args.proxy)
        return
    if args.worker:
        worker(args)
        return
    assert args.run and args.label and args.output and args.launch_config
    args.run = args.run.resolve()
    args.output = args.output.resolve()
    root = Path(tempfile.mkdtemp(prefix=f'metaform-native-{args.label}-'))
    root.chmod(0o700)
    source = args.launch_config.resolve()
    (root / 'launch.json').write_bytes(source.read_bytes())
    os.chmod(root / 'launch.json', 0o600)
    environment = {k: v for k, v in os.environ.items() if not k.startswith('METAFORM_') and not k.startswith('FAKE_')}
    environment.update(METAFORM_HOME=str(root / 'home'), PYTHONPATH=os.pathsep.join((str(args.run / 'src'), str(args.run))))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    print(json.dumps({'label': args.label, 'private_root': str(root)}), flush=True)
    result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker', '--run', str(args.run),
                             '--case', str(root), '--label', args.label, '--output', str(args.output),
                             '--model', MODEL, '--effort', EFFORT], env=environment,
                            cwd=args.run, check=False)
    sys.exit(result.returncode)


if __name__ == '__main__':
    main()
