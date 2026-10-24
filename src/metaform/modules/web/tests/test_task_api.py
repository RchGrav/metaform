"""Task discovery and assignment handlers run without an HTTP server or agent process."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from metaform import home, loader
from metaform.module import Stop
from metaform.modules import tasks
from metaform.modules.web import server

pytestmark = pytest.mark.kind('fixture')


class Handler:
    def __init__(self):
        self.answers = []
        self.headers = []

    def reply(self, status, body, kind, headers):
        assert kind == 'application/json'
        self.answers.append((status, json.loads(body)))
        self.headers.append(headers)

    def refuse(self, error, status):
        self.answers.append((status, {'error': str(error)}))


@pytest.fixture
def isolated_project(tmp_path, monkeypatch):
    """Keep module discovery and prompt receipts out of the person's home, with no background services."""
    monkeypatch.setenv('METAFORM_HOME', str(tmp_path / 'home'))
    loader.reset()
    folder = tmp_path / 'project'
    folder.mkdir()
    home.add_project('task-api', folder)
    yield {'project': 'task-api'}
    loader.reset()


def test_task_catalog_reads_only_named_task_and_skill_metadata(isolated_project):
    handler = Handler()
    server.Handler.task_definitions(handler, isolated_project)
    status, body = handler.answers[0]
    assert status == 200
    assert [task['name'] for task in body['tasks']] == ['user_agent']
    assert body['tasks'][0]['uri'] == 'metaform://tasks/definitions/user_agent'
    assert isinstance(body['skills'], list)
    assert all('name' in skill and 'description' in skill and 'text' not in skill for skill in body['skills'])
    assert handler.headers == [{'Cache-Control': 'no-store'}]
    assert 'roles' not in body and 'assignments' not in body


def test_task_definition_retains_exact_source_and_project_substitution(isolated_project):
    handler = Handler()
    given = {**isolated_project, 'name': 'user_agent', 'project_name': 'Current & <Project>'}
    server.Handler.task_definitions(handler, given, one=True)
    status, body = handler.answers[0]
    canonical = (tasks.PACKAGE / 'resources' / 'user_agent.txt').read_text(encoding='utf-8')
    expected = canonical.replace('{project}', given['project_name'])
    assert status == 200
    assert body['instructions'] == body['component']['text'] == expected
    assert body['component']['bindings'] == {'{project}': given['project_name']}
    assert handler.headers == [{'Cache-Control': 'no-store'}]


@pytest.mark.parametrize('name', [None, 'user_agent'])
def test_task_assignment_preserves_exact_text_and_selected_skills_without_role_or_ticket(monkeypatch, name):
    calls = []
    created = {'task_id': 'assigned-task', 'work_id': 'task-assigned-task', 'state': 'starting'}

    def invoke(given, owner, verb, arguments):
        calls.append((given, owner, verb, arguments))
        return created

    monkeypatch.setattr(server, 'module_verb', invoke)
    given = {'project': 'project-id', 'text': '  Investigate the supplied example.\nKeep these exact words.\n',
             'skills': ['selected.skill'], 'agent': 'codex', 'folder': '/explicit/project',
             'project_name': 'Working Project'}
    if name:
        given['name'] = name
    handler = Handler()
    server.Handler.assign_task(handler, given)
    assert handler.answers == [(200, created)]
    assert calls == [(given, 'tasks', 'assign', {key: value for key, value in given.items() if key != 'project'})]
    assert not {'assignment', 'role', 'ticket', 'commission', 'team'} & calls[0][3].keys()


def test_named_task_assignment_does_not_require_additional_text(monkeypatch):
    calls = []
    monkeypatch.setattr(server, 'module_verb', lambda given, owner, verb, arguments:
                        calls.append((owner, verb, arguments)) or {'task_id': 'named-task'})
    handler = Handler()
    server.Handler.assign_task(handler, {'project': 'project-id', 'name': 'user_agent', 'skills': []})
    assert calls == [('tasks', 'assign', {'name': 'user_agent', 'skills': []})]
    assert handler.answers == [(200, {'task_id': 'named-task'})]


def test_task_assignment_reports_domain_validation_errors(monkeypatch):
    def invalid(*args):
        raise Stop('Give a task definition or an explicit assignment.', 'metaform tasks list')

    monkeypatch.setattr(server, 'module_verb', invalid)
    handler = Handler()
    server.Handler.assign_task(handler, {'project': 'project-id'})
    assert handler.answers == [(400, {'error': 'Give a task definition or an explicit assignment.'})]


def test_removed_role_routes_and_launch_helpers_are_not_exposed():
    handler_source = Path(server.__file__).read_text(encoding='utf-8')
    for route in ('/api/agent-roles', '/api/agent-role', '/api/orchestration-call'):
        assert route not in handler_source
        assert route not in server.DISPATCH_ROUTES
        assert route not in server.PERSONS_WRITES
    assert '/api/task-assign' in server.DISPATCH_ROUTES
    for helper in ('role_choices', 'call_role'):
        assert not hasattr(server, helper)
