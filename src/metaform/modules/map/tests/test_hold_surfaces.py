"""CLI and MCP use the same reason validation and project release operation."""
import json

import pytest

from metaform.data import Node, Store
from metaform.modules.map.tests.test_map import mapped as mapped  # noqa: PLC0414 fixture re-export

pytestmark = pytest.mark.kind('simulation')


@pytest.mark.parametrize('flag', ['hold', 'held', 'backlog'])
@pytest.mark.parametrize('reason', [None, '', ' \t\n '])
def test_cli_hold_requires_fresh_reason(run, mapped, flag, reason):
    work = Store('proj').add_work(Node('element', 'code.timer.kitchen'), None,
                                task='Keep timer accurate.', note='General note cannot justify a hold.')
    args = ['op=move', 'column=backlog'] if flag == 'backlog' else ['op=edit', f'{flag}=true']
    if reason is not None:
        args.append(f'hold_reason={reason}')
    failed = run('map', 'work', *args, f'id={work.id}', cwd=mapped, ok=False)
    assert failed.returncode != 0
    assert 'reason' in failed.stderr.lower()
    assert Store('proj').ticket(work.id).work.column == 'todo'


def test_cli_reason_read_and_project_release(run, mapped):
    work = Store('proj').add_work(Node('element', 'code.timer.kitchen'), None, task='Keep timer accurate.')
    run('map', 'work', 'op=edit', f'id={work.id}', 'hold=true', 'hold_reason=Await timing evidence.', cwd=mapped)
    found = json.loads(run('map', 'work', f'id={work.id}', '--json', cwd=mapped).stdout)
    assert found['map']['hold_reason'] == 'Await timing evidence.'
    released = json.loads(run('map', 'work', 'op=unhold_all', '--json', cwd=mapped).stdout)
    assert released['changed'] == 1
    found = json.loads(run('map', 'work', f'id={work.id}', '--json', cwd=mapped).stdout)
    assert found['map']['hold_reason'] == 'Await timing evidence.'
    assert not found['map']['hold']
    assert json.loads(run('map', 'work', 'op=unhold_all', '--json', cwd=mapped).stdout)['changed'] == 0
