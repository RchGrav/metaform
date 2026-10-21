"""Merged fixes reach running code before fault proof starts. No real server is interrupted."""
from __future__ import annotations

import importlib
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from metaform.data import Store
from metaform.modules.dispatch.tests.test_dispatch import dispatch as dispatch  # noqa: PLC0414
from metaform.modules.dispatch.tests.test_merge import git
from metaform.modules.dispatch.tests.test_merge import repo as repo  # noqa: PLC0414

pytestmark = pytest.mark.kind('simulation')


def activation():
    return importlib.import_module('metaform.modules.dispatch.activation')


def committed(repo, name, work_id):
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('changed\n')
    git(repo, 'add', name)
    git(repo, 'commit', '-m', f'Fix\n\nMetaform-Ticket: {work_id}')
    return git(repo, 'rev-parse', 'HEAD')


def test_runtime_activation_journals_before_restart_and_names_old_sessions(dispatch, repo, monkeypatch):
    module = activation()
    monkeypatch.setattr(module, 'runtime_root', lambda project: repo / 'src/metaform')
    commit = committed(repo, 'src/metaform/modules/web/server.py', dispatch.id)
    own = Store(dispatch.store.project_id, module='dispatch')
    monkeypatch.setattr(module, 'web_record', lambda: {'pid': 91, 'identity': 'old'})
    old = [{'source': 'mcp', 'pid': 92, 'identity': 'mcp-old', 'label': 'next MCP session start'}]
    monkeypatch.setattr(module, 'old_processes', lambda: old)
    monkeypatch.setattr(module, 'remaining', lambda held: held)
    restarts = []
    monkeypatch.setattr(module, 'web_ready', lambda held: bool(restarts))

    def restarted(project):
        journal = module.kept(own, dispatch.id)
        assert journal['commit'] == commit and journal['web']['state'] == 'pending'
        restarts.append(project)
        return {'state': 'restarted'}

    monkeypatch.setattr(module, 'restart_web', restarted)
    result = module.delivered(None, dispatch.store, own, repo, dispatch.id)
    assert result['active'] and result['restarts']['web'] == 'restarted'
    assert result['old_processes'] == old
    assert module.delivered(None, dispatch.store, own, repo, dispatch.id)['active']
    assert restarts == [repo], 'a delivery retry never restarts code already activated'


def test_pending_restart_never_claims_activation_or_starts_duplicate_restart(dispatch, repo, monkeypatch):
    module = activation()
    monkeypatch.setattr(module, 'runtime_root', lambda project: repo / 'src/metaform')
    committed(repo, 'src/metaform/modules/web/page/app.js', dispatch.id)
    monkeypatch.setattr(module, 'web_record', lambda: {'pid': 91, 'identity': 'old'})
    monkeypatch.setattr(module, 'web_ready', lambda held: False)
    restarts = []
    monkeypatch.setattr(module, 'restart_web', lambda project: (restarts.append(project), {'state': 'restarting'})[1])
    own = Store(dispatch.store.project_id, module='dispatch')
    first = module.delivered(None, dispatch.store, own, repo, dispatch.id)
    second = module.delivered(None, dispatch.store, own, repo, dispatch.id)
    assert not first['active'] and not second['active'] and len(restarts) == 1
    assert first['restarts']['web'] == 'restarting' and first['why']


def test_proof_waits_for_its_fault_source_while_delivery_names_other_old_processes(dispatch, repo, monkeypatch):
    module = activation()
    dispatch.run('enable', 'autoticket', cwd=repo)
    own = Store(dispatch.store.project_id, module='dispatch')
    held = {'commit': 'merged', 'web': {'required': True},
            'old_processes': [{'source': 'mcp', 'pid': os.getpid(), 'identity': 'mcp-old', 'label': 'MCP'}]}
    module.keep(own, dispatch.id, held)
    autoticket = Store(dispatch.store.project_id, module='autoticket')
    with autoticket.tables() as tx:
        tx.insert('groups', {'group_id': 1, 'fingerprint': '[]', 'example': 'error', 'count': 1,
                             'first_seen': 'now', 'last_seen': 'now', 'active': '[]', 'source': 'web',
                             'work_id': dispatch.id})
    ready = []
    monkeypatch.setattr(module, 'web_ready', lambda held: bool(ready))
    monkeypatch.setattr(module, 'identity', lambda pid: 'mcp-old')
    assert not module.in_force(dispatch.store, dispatch.id), 'web proof waits for restart'
    ready.append(True)
    assert module.in_force(dispatch.store, dispatch.id), 'web proof ignores unrelated old MCP sessions'
    with autoticket.tables() as tx:
        tx.update('groups', {'group_id': 1}, {'source': 'mcp'})
    assert not module.in_force(dispatch.store, dispatch.id), 'MCP proof waits for its old session'
    monkeypatch.setattr(module, 'identity', lambda pid: None)
    assert not module.in_force(dispatch.store, dispatch.id), 'unknown liveness never proves activation'
    monkeypatch.setattr(module, 'identity', lambda pid: 'new-birth')
    assert module.in_force(dispatch.store, dispatch.id), 'PID reuse means the old session ended'


def test_missing_activation_record_blocks_runtime_fix_but_preserves_other_projects(dispatch, repo, monkeypatch):
    module = activation()
    assert module.in_force(dispatch.store, dispatch.id), 'unrelated local projects have no package runtime to restart'
    monkeypatch.setattr(module, 'runtime_root', lambda project: repo / 'src/metaform')
    committed(repo, 'src/metaform/data/reader.py', dispatch.id)
    assert not module.in_force(dispatch.store, dispatch.id), 'merge alone never establishes activation'


def test_runtime_scope_ignores_tests_and_documentation(dispatch, repo, monkeypatch):
    module = activation()
    monkeypatch.setattr(module, 'runtime_root', lambda project: repo / 'src/metaform')
    committed(repo, 'src/metaform/modules/web/tests/test_server.py', dispatch.id)
    assert module.changes(repo, dispatch.id)[1:] == (False, False)
    committed(repo, 'src/metaform/modules/web/README.md', dispatch.id)
    assert module.changes(repo, dispatch.id)[1:] == (False, False)


def test_mcp_inventory_uses_real_process_commands_without_listener_records(monkeypatch):
    from metaform.modules import dispatch
    module = activation()
    commands = {11: ['python', '-m', 'metaform', 'mcp', 'serve'],
                12: ['agent', '{"command": "python -m metaform mcp serve"}'],
                13: ['python', '-m', 'another', 'mcp', 'serve'],
                14: ['/opt/bin/metaform', 'mcp', 'serve']}
    monkeypatch.setattr(module, 'process_ids', lambda: list(commands))
    monkeypatch.setattr(dispatch, 'command_line', lambda pid: commands[pid])
    monkeypatch.setattr(dispatch, 'launches', lambda: [{'pid': 22, 'work_id': 'running-ticket'}])
    monkeypatch.setattr(module, 'identity', lambda pid: f'birth-{pid}')
    assert [(one['source'], one['pid']) for one in module.old_processes()] == [('mcp', 11), ('mcp', 14), ('run', 22)]


def test_web_activation_requires_replacement_to_answer_its_actual_health_route(home, monkeypatch):
    module = activation()
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            body = json.dumps({'pid': 99, 'home': str(home)}).encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    with HTTPServer(('127.0.0.1', 0), Handler) as server:
        monkeypatch.setattr(module, 'web_record', lambda: {'pid': 99, 'identity': 'new', 'bind': '127.0.0.1',
                                                         'port': server.server_port, 'started': '2026-10-21T12:00:01Z'})
        held = {'before': {'pid': 99, 'identity': 'new'}, 'after': '2026-10-21T12:00:00'}
        assert not module.web_ready(held), 'the old server answering never proves new code'
        held['before'] = {'pid': 91, 'identity': 'old'}
        thread = threading.Thread(target=server.handle_request)
        thread.start()
        try:
            assert module.web_ready(held)
        finally:
            thread.join(timeout=3)
    assert requests == ['/api/server']
