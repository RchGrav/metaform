"""Standard MCP skills discovery preserves native deployment and harness provisioning, BASE-059."""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('BASE-059')]


@pytest.fixture
def skill_server(project_folder):
    # Resolve the active namespace after the home fixture resets loaded modules.
    from metaform.loader import discover
    discover()
    from metaform.modules.mcp import server, skill_extension
    return SimpleNamespace(folder=project_folder, server=server, extension=skill_extension)


def test_standard_skill_discovery_survives_disabled_workflow(skill_server, run):
    run('disable', 'workflow', cwd=skill_server.folder)
    assert 'metaform_skills' not in skill_server.server.listing(skill_server.folder)
    entries = skill_server.extension.entries(skill_server.folder)
    names = {entry['frontmatter']['name'] for entry in entries}
    assert 'write-workflow' in names and 'sentinel' not in names
    uri = 'skill://metaform/sentinel/SKILL.md'
    entry = skill_server.extension.get(skill_server.folder, uri)
    assert entry['uri'] == uri and entry['frontmatter']['name'] == 'sentinel'
    assert skill_server.extension.read(skill_server.folder, uri)[0]


def test_native_deployment_does_not_change_standard_mcp_skill_availability(skill_server, tmp_path, monkeypatch):
    from metaform import install
    user = tmp_path / 'user'
    user.mkdir()
    monkeypatch.setenv('HOME', str(user))
    monkeypatch.setenv('USERPROFILE', str(user))
    before = skill_server.extension.entries(skill_server.folder)
    tool = install.tools()['claude']
    plan = install._skill_plan(tool)
    assert plan is not None and plan.files
    install._deploy_skills(tool, plan, tmp_path / 'backups')
    assert all(path.read_bytes() == raw for path, raw in plan.files.items())
    assert install.skills_deployed('claude-code')
    assert skill_server.extension.entries(skill_server.folder) == before
    assert 'metaform_skills' not in skill_server.server.listing(skill_server.folder, 'claude-code')


@pytest.mark.req('MCP-029')
def test_connect_message_contains_links_without_a_custom_skill_index(skill_server):
    from metaform import prompt_files
    sent = skill_server.server.connect_instructions(skill_server.folder)
    assert len(sent) <= 512
    assert sent.startswith(prompt_files.module('mcp', 'connect_directive') + '\nmetaform://rules\n')
    role = skill_server.server.role_text(skill_server.folder, 'unknown-host')
    assert 'metaform_skills' not in sent + role
    assert 'Skills:' not in sent + role


@pytest.mark.req('MCP-028')
def test_unrecorded_harness_receives_native_provisioning_notice_once(skill_server, monkeypatch):
    from metaform import harness
    server = skill_server.server
    monkeypatch.setattr(server, 'TOLD', set())
    monkeypatch.setattr(harness, 'running', lambda: Path(os.path.abspath(os.sep)) / 'opt' / 'harness' / 'bin' / 'tool')
    notice = f'Notice: {harness.NOTICE}'
    assert notice not in server.connect_instructions(skill_server.folder)
    assert server.provisioning('one') == notice
    monkeypatch.setattr(server, 'served_session', lambda *args: 'one')
    assert notice in server.guidance(skill_server.folder, SimpleNamespace(), SimpleNamespace(session='one'))
    assert server.provisioning('one') is None
    harness.done(harness.running())
    assert server.provisioning('two') is None


def test_client_identity_accepts_initialize_params_and_modern_request_metadata(skill_server):
    def context(params):
        return SimpleNamespace(params=params, session=SimpleNamespace(client_params=None))
    server = skill_server.server
    assert server.client_name(context({'clientInfo': {'name': 'claude-code'}})) == 'claude-code'
    assert server.client_name(context({'_meta': {
        'io.modelcontextprotocol/clientInfo': {'name': 'codex-mcp-client'}}})) == 'codex-mcp-client'
    assert server.client_name(context({})) is None
