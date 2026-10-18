"""Prepare one isolated real-model smoke ticket through the existing public CLI."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path('/tmp/metaform-review-live')
PROJECT = ROOT / 'project'
CLI = '/workspace/scratch/243b683ad142/metaform/.venv/bin/metaform'
ENV = {**os.environ, 'METAFORM_HOME': str(ROOT / 'home')}

TASK = '''Build label_tools.py with normalize_label(text: str) -> str for callers matching configuration labels.

Functional outcome: trim surrounding whitespace, collapse each internal run of whitespace to one underscore,
lowercase the label, and preserve punctuation. Empty or whitespace-only input raises ValueError.
Acceptance examples: "  Core Switch  " becomes "core_switch"; "WAN\\t\\tUplink" becomes "wan_uplink";
"Core-Switch" becomes "core-switch"; "" and "   " each raise ValueError.
Create test_label_tools.py using Python's standard unittest module, and run python -m unittest -v.

Exercise the native GC role-creation journey on this ticket: as the GC, request the new label_normalizer
specialist yourself through orchestration_call, with its purpose, requested contribution and this context.
When that returns the missing-role request, commission that request through orchestration_commission.
The Role Creator authors and publishes the reusable duty; the original requested specialist call then
continues and its result returns to you. Use the generated specialist to implement and test the function.
On its return, independently validate the requested outcome and deliver the root with the exact candidate
files, hashes and verification evidence. The normal independent functionality assessment and user/PM
notification should follow the existing runtime continuations.

The isolated project already contains the functional location for this task: code.label.normalizer.
All work for this smoke journey belongs in this project folder.
'''


def call(*args: str) -> dict:
    result = subprocess.run([CLI, *args, '--json'], cwd=PROJECT, env=ENV,
                            text=True, capture_output=True, check=False, timeout=30)
    record = {'args': list(args), 'exit_code': result.returncode,
              'stdout': result.stdout, 'stderr': result.stderr}
    with (ROOT / 'setup-commands.jsonl').open('a') as stream:
        stream.write(json.dumps(record) + '\n')
    if result.returncode:
        raise RuntimeError(json.dumps(record))
    return json.loads(result.stdout)


def main() -> None:
    (ROOT / 'ticket-task.txt').write_text(TASK)
    call('map', 'knowledge', 'op=create', 'layer=code.label.normalizer@smoke_location',
         'variable=Which functionality is assigned in this isolated live smoke?',
         'mutable=true', 'hideable=true', 'module=map', 'role=setup', 'model=none')
    call('map', 'knowledge', 'op=add-element', 'layer=code.label.normalizer@smoke_location',
         'address=code.label.normalizer', 'name=Label normalizer', 'name_length=2', 'role=DE')
    call('map', 'knowledge', 'op=finish', 'layer=code.label.normalizer@smoke_location')
    ticket = call('map', 'work', 'op=add', 'node=element:code.label.normalizer',
                  'title=Normalize labels through a GC-created specialist', 'task=' + TASK,
                  'condition=unbuilt', 'agent=codex', 'eligible=["codex"]')
    (ROOT / 'ticket.json').write_text(json.dumps(ticket, indent=2) + '\n')
    print(json.dumps({'ticket': ticket, 'project': str(PROJECT)}, indent=2))


if __name__ == '__main__':
    main()
