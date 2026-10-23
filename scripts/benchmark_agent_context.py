"""Measure deterministic agent text delivery without model calls or installed-home reads.

Run with: uv run --with tiktoken python scripts/benchmark_agent_context.py
  --output /tmp/agent-context.json
Optional --baseline-dir holds orchestration state.py, __init__.py and prompts.xml
captured before edits. Otherwise baseline modules come from --baseline-ref.
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


def canonical(text):
    text = re.sub(r'\b[0-9a-f]{16,64}\b', lambda match: '0' * len(match.group()), text)
    return re.sub(r'\d{4}-\d\d-\d\d[T ][0-9:.+Z-]+', '2026-10-20T00:00:00Z', text)


def worker(output):
    import tiktoken

    from metaform import home, settings
    from metaform.data import Node, Store
    from metaform.loader import set_enabled
    from metaform.module import context, resolve_agent_role
    from metaform.modules.dispatch import prompt
    from metaform.modules.dispatch.runner import Session
    from metaform.modules.orchestration.state import SERVICE, own, verb
    from tests.storekit import small_map

    project = Path(os.environ['METAFORM_HOME']).parent / 'project'
    project.mkdir()
    home.add_project('agent-context-benchmark', project)
    set_enabled('dispatch', True)
    settings.put('dispatch_autostart', False, project)
    store = Store('agent-context-benchmark')
    small_map(store)
    record = store.add_work(Node('element', 'code.timer.kitchen'), None,
                            task='Preserve countdown and audible alarm.', title='Timer delivery')
    ctx = context('orchestration', project, project=store.project_id, session='benchmark-worker')
    claimed = verb(ctx, 'orchestration', 'claim', work=record.id, role='implementer', session='benchmark-worker')
    assigned = SERVICE.assignment(ctx, work_id=record.id)
    encoding = tiktoken.get_encoding('o200k_base')
    segments = []

    def add(name, value):
        raw = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
        text = canonical(raw)
        segments.append({'name': name, 'characters': len(text), 'tokens': len(encoding.encode(text)), 'text': text})

    def opening(assignment, label):
        session = Session(context('dispatch', project, project=store.project_id),
                          Store(store.project_id, module='dispatch'),
                          store.ticket(assignment['work_id']).work, 'codex', ['unused'])
        session.session_id = assignment.get('owner_session_id') or label
        session.runner = label
        session.authored_role = assignment['authored_role_uri']
        session.assignment = assignment
        text = session.handed() + '\n\n' + prompt('work_link')
        text = session.guidance(text, [])
        try:
            from metaform.modules.dispatch.channels import startup
        except ModuleNotFoundError:
            pass  # Historical revisions before channels have no channel introduction.
        else:
            text += '\n\n' + startup(session.ctx, session.session_id, session.work_id, session.role)
        text = session.rules(text)
        # Historical runners requested this diagnostic automatically; current ordinary work does not.
        if 'self.context_checkpoint' in inspect.getsource(Session.prompted):
            text = session.context_checkpoint(text)
        add(label + '_first_prompt', text)
        role = resolve_agent_role(project, session.authored_role.removeprefix('metaform://role/'), project=store.project_id)
        add(label + '_role_read', role.get('text') or '')

    add('claim_response', claimed)
    opening(assigned, 'worker')
    result = 'Countdown reaches zero once. Audible alarm rings once. Focused regression checks pass.'
    add('worker_result', result)
    SERVICE.returned(ctx, record.id, result, evidence=['Deterministic fixture.'], key='benchmark-return')
    with own(ctx).tables(write=False) as tx:
        events = [dict(one) for one in tx.rows('transitions', limit=0).results]
    for event in events:
        if event['kind'] in ('send', 'user_message'):
            add('completion_delivery', event['payload'].get('body', ''))
        if event['kind'] == 'assessment':
            reviewer = SERVICE.assessment(ctx, assigned, event['payload'].get('report') or {},
                                          event['payload']['key'])
            opening(reviewer, 'reviewer')
            add('reviewer_result', 'No functional defects found.')
    output.write_text(json.dumps({'tokenizer': 'tiktoken:o200k_base', 'segments': segments,
                                 'first_prompt': next(one for one in segments if one['name'] == 'worker_first_prompt'),
                                 'ticket_text_tokens': sum(one['tokens'] for one in segments)}, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-dir', type=Path)
    parser.add_argument('--baseline-measurement', type=Path,
                        help='Reuse a captured before measurement when unrelated source migrations prevent replay.')
    parser.add_argument('--baseline-ref', default='dbb73e61eb8102b6abcd13a824a8a5e5e7425777')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--include-text', action='store_true')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker(args.output)
        return
    root = Path(__file__).resolve().parents[1]
    baseline_ref = subprocess.check_output(['git', 'rev-parse', args.baseline_ref], cwd=root, text=True).strip()
    measurements = {}
    fingerprints = {}
    with tempfile.TemporaryDirectory(prefix='metaform-agent-context-') as folder:
        folder = Path(folder)
        for label in ('before', 'after'):
            if label == 'before' and args.baseline_measurement is not None:
                captured = json.loads(args.baseline_measurement.read_text())
                measurements[label] = captured[label]
                fingerprints[label] = captured['source_sha256'][label]
                continue
            checkout = folder / label
            if label == 'before':
                checkout.mkdir()
                archive = subprocess.check_output(['git', 'archive', baseline_ref, 'src'], cwd=root)
                with tarfile.open(fileobj=io.BytesIO(archive)) as packed:
                    packed.extractall(checkout, filter='data')
            else:
                shutil.copytree(root / 'src', checkout / 'src', ignore=shutil.ignore_patterns('__pycache__'))
            if label == 'before':
                target = checkout / 'src/metaform/modules/orchestration'
                for name in ('state.py', '__init__.py', 'prompts.xml'):
                    destination = target / ('resources' if name.endswith('.xml') else '') / name
                    if args.baseline_dir is not None:
                        shutil.copyfile(args.baseline_dir / name, destination)
                    else:
                        relative = destination.relative_to(checkout).as_posix()
                        destination.write_bytes(subprocess.check_output(
                            ['git', 'show', f'{baseline_ref}:{relative}'], cwd=root))
                relative = 'src/metaform/modules/dispatch/orchestration.py'
                original = subprocess.check_output(['git', 'show', f'{baseline_ref}:{relative}'], cwd=root)
                (checkout / relative).write_bytes(original)
                relative = 'src/metaform/modules/dispatch/resources/prompts.xml'
                (checkout / relative).write_bytes(subprocess.check_output(
                    ['git', 'show', f'{baseline_ref}:{relative}'], cwd=root))
            fingerprints[label] = {
                str(path.relative_to(checkout)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (checkout / 'src/metaform/modules/orchestration/state.py',
                             checkout / 'src/metaform/modules/orchestration/__init__.py',
                             checkout / 'src/metaform/modules/orchestration/resources/prompts.xml',
                             checkout / 'src/metaform/modules/dispatch/orchestration.py',
                             checkout / 'src/metaform/modules/dispatch/resources/prompts.xml',
                             checkout / 'src/metaform/modules/dispatch/runner.py')}
            result = checkout / 'measurement.json'
            environment = {key: value for key, value in os.environ.items() if not key.startswith('METAFORM_')}
            environment.update(METAFORM_HOME=str(checkout / 'home'),
                               PYTHONPATH=os.pathsep.join((str(checkout / 'src'), str(root))))
            subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker', '--output', str(result)],
                           cwd=checkout, env=environment, check=True)
            measurements[label] = json.loads(result.read_text())
    measurements['scope'] = ('Deterministic simulated ticket text, not actual model billed tokens. Includes claim '
        'response, worker prompt, role resource read, fixed result, completion body, optional reviewer prompt, '
        'reviewer role read and fixed reviewer result. Excludes tool schemas, host system prompts, cached context, '
        'reasoning and unspecified tool calls. No paid model calls. No installed agent logs or receipts read.')
    measurements['normalization'] = 'Random 16-64 digit hex ids zeroed, preserving character lengths. ISO timestamps normalized.'
    measurements['baseline'] = {'orchestration_override': str(args.baseline_dir) if args.baseline_dir else None,
                                'git_ref': baseline_ref}
    if args.baseline_measurement is not None:
        measurements['baseline']['captured_measurement'] = str(args.baseline_measurement)
        measurements['baseline']['replay_limit'] = (
            'Captured before counts include uncommitted startup work present when this assignment began. '
            'Current unrelated prompt-address migration prevents replaying that mixed initial tree. '
            'Pinned git-ref mode measures the coherent committed baseline instead.')
    measurements['source_sha256'] = fingerprints
    measurements['first_prompt_scope'] = (
        'Rendered ACP first text block. Includes channel startup and rules; a context checkpoint only when '
        'the examined runner requests it in its normal prompt path. '
        'Typed resource links excluded. Startup already omitted embedded tools JSON before edits.')
    measurements['billed_ticket_tokens'] = {'before': None, 'after': None,
        'reason': 'Requires model execution. Fixture measures delivered text only.'}
    before, after = measurements['before'], measurements['after']
    measurements['savings'] = {
        'first_prompt_tokens': before['first_prompt']['tokens'] - after['first_prompt']['tokens'],
        'ticket_text_tokens': before['ticket_text_tokens'] - after['ticket_text_tokens'],
        'ticket_text_percent': round(100 * (1 - after['ticket_text_tokens'] / before['ticket_text_tokens']), 2)}
    measurements['segment_savings'] = []
    for name in dict.fromkeys(one['name'] for measured in (before, after) for one in measured['segments']):
        old = sum(one['tokens'] for one in before['segments'] if one['name'] == name)
        new = sum(one['tokens'] for one in after['segments'] if one['name'] == name)
        measurements['segment_savings'].append({'name': name, 'before_tokens': old, 'after_tokens': new,
            'saved_tokens': old - new, 'saved_percent': round(100 * (1 - new / old), 2) if old else None})
    if not args.include_text:
        for measured in (before, after):
            measured['first_prompt'].pop('text', None)
            for segment in measured['segments']:
                segment.pop('text', None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(measurements, indent=2) + '\n')
    for label in ('before', 'after'):
        one = measurements[label]
        print(label, json.dumps({'first_prompt_characters': one['first_prompt']['characters'],
                                'first_prompt_tokens': one['first_prompt']['tokens'],
                                'simulated_ticket_text_tokens': one['ticket_text_tokens']}))


if __name__ == '__main__':
    main()
