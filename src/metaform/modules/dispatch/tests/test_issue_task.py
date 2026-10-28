"""Issue reports use durable assigned tasks without held tickets."""
from __future__ import annotations

import hashlib
from copy import deepcopy

import pytest

from metaform.data import Node
from metaform.module import Stop, context, provided
from metaform.modules import dispatch, tasks

pytestmark = pytest.mark.kind('fixture')


@pytest.fixture
def project(project_folder, monkeypatch):
    ctx = context('dispatch', project_folder, session='caller-session',
                  identity={'METAFORM_SESSION': 'caller-session', 'METAFORM_WORK': 'caller-work'})
    store = ctx.require_store()
    base = store.layer('functional-map', 'map', 'The functional map.', kind='base',
                       mutable=False, hideable=False)
    for address in ('code', 'code.receiver', 'code.provider'):
        store.add_element(base.name, address, name=address, role='SE')
    joined = store.add_join(base.name, 'code.receiver', ['code.provider'], purpose='Receive a result.',
                            ef='Return the provided result.')
    store.finish(base.name)
    owner, lifecycle = provided(project_folder, 'task.lifecycle')[0]
    started = []

    class Transport:
        def start(self, called, row):
            # Persistence must precede the transport, including when the node is already busy.
            assert lifecycle.assignment(called, row['task_id']) == row
            started.append((called, deepcopy(row)))
            return {'session_id': 'issue-native-session', 'agent': row['agent']}

    monkeypatch.setitem(lifecycle.assign.__func__.__globals__, 'transport', lambda called: Transport())
    monkeypatch.setattr(dispatch, 'in_use', lambda *args: pytest.fail('Node ownership must not gate an issue.'))
    monkeypatch.setattr(dispatch, 'map_work', lambda *args, **kwargs: pytest.fail('An issue must not create a ticket.'))
    return ctx, store, joined, lifecycle, started, owner


def test_issue_keeps_raw_report_exact_task_and_context_without_ticket(project, project_folder):
    ctx, store, _, lifecycle, started, owner = project
    folder = project_folder / 'working folder'
    folder.mkdir()
    report = '  Alarm repeats.\nKeep these  spaces and <exact> details.\n\n'
    ctx.nouns.update(node='code.receiver', text=report, agent='explicit-adapter', folder=str(folder))
    before = store.work(limit=0).results
    result = dispatch.raise_issue(ctx)
    assert result['node'] == 'code.receiver'
    assert result['conversation'] is True
    assert result['agent'] == 'explicit-adapter'
    assert result['work_id'].startswith('task-')
    assert result['state'] == 'starting'
    assert store.work(limit=0).results == before
    called, launched = started[0]
    assert called.module == owner
    assert called.folder == ctx.folder
    assert called.project == ctx.project
    assert called.session == ctx.session
    assert called.identity == ctx.identity
    row = lifecycle.assignment(called, result['task_id'])
    assert row['name'] == 'user_agent'
    assert row['cwd'] == str(folder)
    assert row['payload']['input'] == report
    assert row['payload']['node'] == 'code.receiver'
    assert row['payload']['skills'] == []
    assert row['payload']['interactive'] is True
    canonical = (tasks.PACKAGE / 'resources' / 'user_agent.txt').read_text(encoding='utf-8')
    expected = canonical.replace('{project}', 'proj')
    assert row['payload']['instructions'] == expected
    assert row['payload']['component']['text'] == expected
    assert row['payload']['component']['rendered_fingerprint'] == hashlib.sha256(expected.encode()).hexdigest()
    assert row['payload']['component']['source']['shipped_identity'] == hashlib.sha256(canonical.encode()).hexdigest()
    assert launched['payload'] == row['payload']


def test_issue_accepts_existing_join_and_single_raw_cli_argument(project):
    ctx, store, joined, lifecycle, started, _ = project
    report = '  Request fails\nwith exact spacing.  '
    node = f'join:{joined.id}'
    assert store.node(Node('join', joined.id)) is not None
    ctx.nouns.update(node=node, text=[report], agent='codex')
    result = dispatch.raise_issue(ctx)
    row = lifecycle.assignment(started[0][0], result['task_id'])
    assert row['payload']['input'] == report
    assert row['payload']['node'] == node


def test_issue_rejects_missing_node_before_any_assignment(project):
    ctx, _, _, _, started, _ = project
    ctx.nouns.update(node='code.missing', text='An actual report.', agent='codex')
    with pytest.raises(Stop, match='No node code.missing'):
        dispatch.raise_issue(ctx)
    assert started == []


def test_issue_rejects_blank_report_before_any_assignment(project):
    ctx, _, _, _, started, _ = project
    ctx.nouns.update(node='code.receiver', text=' \n ', agent='codex')
    with pytest.raises(Stop, match='An issue says what is wrong'):
        dispatch.raise_issue(ctx)
    assert started == []


def test_issue_verb_uses_standard_assigned_session_bridge():
    verb = next(one for one in dispatch.MODULE.verbs if one.name == 'raise')
    assert verb.task == 'session'
    assert 'mcp' in verb.surfaces
