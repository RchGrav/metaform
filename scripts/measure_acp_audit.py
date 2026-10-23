"""Compare observable hold reviews in isolated homes, without paid model calls.

uv run python scripts/measure_acp_audit.py --baseline /tmp/metaform-acp-baseline \
    --output docs/reviews/acp-audit-measurements-holds.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from unittest.mock import patch


def summarize_trace(path: Path) -> dict:
    """Count fake adapter observations, keeping model billing explicitly unknown."""
    entries = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    messages = [entry['message'] for entry in entries if isinstance(entry.get('message'), dict)]
    methods = Counter(message.get('method') for message in messages if message.get('method'))
    prompts = [message for message in messages if message.get('method') == 'session/prompt']
    texts = [[block['text'] for block in message.get('params', {}).get('prompt', [])
              if block.get('type') == 'text'] for message in prompts]
    seen: set[str] = set()
    repeated = 0
    for blocks in texts:
        current = [paragraph for block in blocks for paragraph in block.split('\n\n') if paragraph]
        repeated += sum(len(paragraph.encode()) for paragraph in current if paragraph in seen)
        seen.update(current)
    return {
        'trace_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'adapter_process_starts': sum('pid' in entry for entry in entries),
        'acp_methods': dict(sorted(methods.items())),
        'acp_new_sessions': methods['session/new'],
        'acp_loads': methods['session/load'],
        'acp_resumes': methods['session/resume'],
        'acp_prompt_requests': len(prompts),
        'prompt_text_utf8_bytes': sum(len(text.encode()) for blocks in texts for text in blocks),
        'repeated_exact_paragraph_utf8_bytes': repeated,
        'completed_fake_work': sum(entry.get('done') == 0 for entry in entries if 'done' in entry),
        'actual_model_invocations': None,
        'billed_tokens': None,
        'billing_cost': None,
        'limits': 'Fake adapter wire observations only. ACP prompt requests are not provider model calls. '
                  'Repeated paragraphs match exact text in preceding prompt requests and exclude blank separators. '
                  'No inference about hidden native context, replay billing or token cost.',
    }


def worker(repository: Path, output: Path) -> None:
    sys.path[:0] = [str(repository / 'src'), str(repository)]
    from metaform import home, settings
    from metaform.data import Node, Store
    from metaform.loader import set_enabled
    from metaform.module import context
    from metaform.modules.dispatch import hold_review, signals
    from tests.storekit import small_map

    folder = Path(os.environ['METAFORM_HOME']).parent / 'project'
    folder.mkdir()
    home.add_project('measurement', folder)
    set_enabled('dispatch', True)
    settings.put('dispatch_autostart', False, folder)
    store = Store('measurement')
    small_map(store)
    ticket = store.add_work(Node('element', 'code.timer.kitchen'), None,
                            task='Replace failed alarm hardware.', held=True,
                            hold_reason='Wait for replacement hardware delivery.')
    ctx = context('dispatch', folder, project=store.project_id)
    emitted = []
    deadlines = []
    clock = [1000.0]
    with patch.object(ctx, 'setting', lambda name: name == 'dispatch_autostart'), \
            patch.object(hold_review.time, 'time', lambda: clock[0]), \
            patch.object(hold_review, 'announce', lambda _ctx, value: emitted.append(value)):
        for moment in (1000.0, 1900.0, 2800.0, 3700.0):
            clock[0] = moment
            deadlines.append(hold_review.reconcile(ctx))
            for value in signals.rows(store):
                if str(value.get('signal_key', '')).startswith('hold-review:'):
                    assert signals.taken(store, value)
    assert store.ticket(ticket.id).work.held
    result = {
        'scenario': 'Same justified hardware wait, reviewed at t=1000,1900,2800,3700 seconds.',
        'held_outcome_preserved': True,
        'actionable_review_signals': len(emitted),
        'scheduled_review_deadlines': deadlines,
        'delivered_signal_text_utf8_bytes': sum(len(value['said'].encode()) for value in emitted),
        'actual_model_invocations': None,
        'billed_tokens': None,
        'billing_cost': None,
        'limits': 'Signals are actionable wake requests. No liaison or paid model was run. '
                  'Signal text bytes exclude tool schemas, hidden context and provider billing.',
        'source_sha256': hashlib.sha256((repository / 'src/metaform/modules/dispatch/hold_review.py').read_bytes()).hexdigest(),
    }
    output.write_text(json.dumps(result, indent=2) + '\n')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--revised', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline-acp-log', type=Path)
    parser.add_argument('--revised-acp-log', type=Path)
    parser.add_argument('--worker', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker is not None:
        worker(args.worker.resolve(), args.output)
        return
    if args.baseline is None:
        parser.error('--baseline is required')
    result = {'scope': 'Matched hold behavior and optional supplied fake-ACP traces, isolated homes, no paid model execution.'}
    with tempfile.TemporaryDirectory(prefix='metaform-acp-hold-measure-') as temporary:
        for label, repository in (('baseline', args.baseline), ('revised', args.revised)):
            target = Path(temporary) / label
            target.mkdir()
            environment = {name: value for name, value in os.environ.items() if not name.startswith('METAFORM_')}
            environment['METAFORM_HOME'] = str(target / 'home')
            output = target / 'measurement.json'
            subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker', str(repository),
                            '--output', str(output)], cwd=repository, env=environment, check=True)
            result[label] = json.loads(output.read_text())
    for label in ('baseline', 'revised'):
        trace = getattr(args, label + '_acp_log')
        if trace is not None:
            result[label]['acp_trace'] = summarize_trace(trace)
    result['baseline_commit'] = subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=args.baseline, text=True).strip()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
