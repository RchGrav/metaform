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


@pytest.mark.req('MCP-029')
def test_connect_message_contains_links_without_a_custom_skill_index(skill_server):
    from metaform import prompt_files
    sent = skill_server.server.connect_instructions(skill_server.folder)
    assert len(sent) <= 512
    assert sent.startswith(prompt_files.module('mcp', 'connect_directive') + '\nmetaform://rules\n')
    task = skill_server.server.task_text(skill_server.folder, 'unknown-host')
    assert 'metaform_skills' not in sent + task
    assert 'Skills:' not in sent + task


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
